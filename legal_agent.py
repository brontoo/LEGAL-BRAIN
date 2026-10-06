import contextlib
import contextvars
import os
from typing import Annotated, Iterator, Optional

from dotenv import load_dotenv
from supabase import create_client, Client
from sentence_transformers import SentenceTransformer
import threading
from typing_extensions import TypedDict
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition

from citations import (
    CITATIONS_BEGIN,
    CITATIONS_END,
    Evidence,
    RefAllocator,
    format_evidence_block,
)
# قواعد احتساب المستحقات العمالية تُستورد **دالّةً** لا نصّاً محفوظاً، فتُبنى من
# جدول `labour_rules.RULES` عند الإقلاع، فلا يفترق الموجّه عن الجدول: من عدّل
# قاعدةً في الجدول عدّلها في الموجّه بلا أن يتذكّر. وهذا هو أصل العيب الذي جاء
# `labour_rules` لمنعه — قاعدة تعيش في مكان ولا تصل إلى النموذج.
from labour_rules import rules_block

load_dotenv()

# ==============================================================================
# تهيئة كسولة (Lazy) لـ Supabase ونموذج التضمين
# ==============================================================================
# كان هذان السطران يُنفَّذان عند **استيراد** الوحدة، وترتّب على ذلك:
#   1) إقلاع الخادم ينتظر تحميل نموذج 2.2 GB — 11 ثانية في تجربة فعلية.
#   2) يستحيل استيراد الوحدة في اختبار بلا شبكة وبلا نموذج.
#   3) يفشل الاستيراد كله إن نقص متغيّر بيئة، برسالة غامضة من مكتبة خارجية
#      لا تذكر أيّ متغيّر هو الناقص.
# الآن يُهيَّأ كل شيء عند أول استخدام فعلي، ويُحتفظ به بعد ذلك.

EMBEDDING_MODEL_NAME = "intfloat/multilingual-e5-large"

_supabase: Optional[Client] = None
_model: Optional[SentenceTransformer] = None

#: ⚠️ **قفل على التحميل — وهو إصلاح عطب حقيقي.**
#:
#: كان الحرس `if _model is None` وحده. والأدوات تُنادى **معاً** (نداء أدوات
#: متوازٍ في LangChain)، فدخل خيطان الحرس قبل أن يكتب أيٌّ منهما `_model`،
#: **فحمّل كلٌّ نسخته**: نموذج ٢.٢ غ.ب يُقرأ من القرص **مرتين**، وتُهدَر
#: **١٢ ثانية** في كل توليد، **وتُشغَل ٤.٤ غ.ب من الذاكرة بدل ٢.٢**.
#:
#: وقد ظهر ذلك في طرفية المستخدم سطرين متتاليين:
#:     Loading weights: 391/391 [00:11]
#:     Loading weights: 391/391 [00:12]
#:
#: ⚠️ والقفل المزدوج (فحصٌ بلا قفل، ثم فحصٌ بقفل) **مقصود**: القراءة الأولى
#: تُجنّب كل نداء لاحق أخذ القفل أصلاً — والقفل لا يُؤخَذ إلا مرة واحدة في
#: عمر العملية.
_model_lock = threading.Lock()


def get_supabase() -> Client:
    """اتصال Supabase — يُنشأ مرة واحدة عند أول استخدام."""
    global _supabase
    if _supabase is None:
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_KEY")
        missing = [n for n, v in (("SUPABASE_URL", url), ("SUPABASE_KEY", key)) if not v]
        if missing:
            raise RuntimeError(
                "متغيّرات بيئة ناقصة: "
                + ", ".join(missing)
                + "\n  أضفها إلى ملف .env — انظر .env.example"
            )
        _supabase = create_client(url, key)
    return _supabase


def get_model() -> SentenceTransformer:
    """نموذج التضمين — يُحمَّل مرة واحدة عند أول استخدام (~2.2 GB)."""
    global _model
    if _model is None:
        with _model_lock:
            # ⚠️ والفحص الثاني **لازم**: خيط آخر قد يكون حمّله بينما انتظرنا.
            if _model is None:
                _model = SentenceTransformer(EMBEDDING_MODEL_NAME)
    return _model


def encode_query(text: str) -> list:
    """
    يُضمّن نص الاستعلام.

    البادئة "query: " ليست تجميلية: نموذج e5 دُرِّب على التمييز بين الاستعلام
    والمقطع، وإغفالها يُفسد جودة الاسترجاع. (المقابل "passage: " يُستخدم عند
    التخزين في سكربتات الاستيعاب.)
    """
    return get_model().encode(f"query: {text}").tolist()

# ==============================================================================
# جامع الأدلة — يربط ما استُرجع بما سيقتبسه النموذج
# ==============================================================================
# الغرض: أن نعرف **بالضبط** ما أُعطي للنموذج في هذه الجولة، لنحقّق استشهاداته.
# فبدون هذا السجلّ لا يمكن التحقّق: «هل اقتبس النموذج ممّا استرجعناه؟» سؤال
# لا جواب له إن لم نحتفظ بما استرجعناه.
#
# ⚠️ لماذا `ContextVar` لا متغيّر عام؟
# لأن `main.py` يُشغّل الوكيل في **خيط منفصل لكل طلب**. والمتغيّر العام يخلط
# أدلّة الطلبات المتزامنة، فيُقبل استشهاد مسودّة بمقطع من مسودّة أخرى — وهو
# خطأ يمرّ بصمت لأنه يبدو تحقّقاً ناجحاً.
#
# و`ContextVar` معزول لكل خيط ولكل مهمّة asyncio، فالطلب لا يرى أدلّة غيره.

_current_collector: contextvars.ContextVar[Optional["EvidenceCollector"]] = (
    contextvars.ContextVar("legal_agent_evidence", default=None)
)


class EvidenceCollector:
    """
    يجمع أدلّة جولة واحدة، ويملك توزيع المراجع عليها.

    الملكية هنا مقصودة: لو وزّع كل نداء أداة مراجعه بنفسه لبدأ كلٌّ منها من
    ``L1``، فيرى النموذج مقطعين مختلفين بالمرجع نفسه — وهذا يُفسد الاقتباس
    ويُفسد التحقّق معه.
    """

    def __init__(self) -> None:
        self.allocator = RefAllocator()
        self._evidence: list[Evidence] = []

    def add(self, items: list[Evidence]) -> None:
        """يُضيف مقاطع أداة واحدة إلى سجلّ الجولة."""
        self._evidence.extend(items)

    @property
    def evidence(self) -> list[Evidence]:
        """نسخة من الأدلّة — حتى لا يُعدّلها مستدعٍ بالخطأ."""
        return list(self._evidence)

    def __len__(self) -> int:
        return len(self._evidence)


def current_collector() -> Optional[EvidenceCollector]:
    """الجامع النشط في هذا الخيط/المهمّة، أو `None` إن لم يُفتح مسار تحقّق."""
    return _current_collector.get()


@contextlib.contextmanager
def collect_evidence() -> Iterator[EvidenceCollector]:
    """
    يفتح جامعاً لجولة واحدة، ويضمن إغلاقه::

        with collect_evidence() as collected:
            ... تشغيل الوكيل ...
        print(len(collected.evidence))

    الاستخدام كسياق مقصود لا تجميلي: لو بقي الجامع مفتوحاً بعد الجولة لتسرّبت
    أدلّته إلى الجولة التالية، فيُقبل فيها اقتباس من مستند لم يُسترجَع فيها.
    """
    collector = EvidenceCollector()
    token = _current_collector.set(collector)
    try:
        yield collector
    finally:
        _current_collector.reset(token)


# ==============================================================================
# إعداد أدوات الاسترجاع الخمس
# ==============================================================================
# كانت هذه الأدوات **نسخاً شبه حرفية** من بعضها: نفس النداء ونفس التنسيق ونفس
# الاقتطاع، ويختلف اسم دالة RPC والعتبة والحدّ ووسم العرض فقط.
#
# وقد كلّفنا هذا التكرار خطأً فعلياً: أداة التشريعات سقطت من نسخة الموجّه في
# `main.py` وحدها، فلم يعد الوكيل يستشهد بالتشريعات من تلك الواجهة.
#
# فجُمعت في جدول واحد ومسار واحد: تغيير عتبة أو تنسيق صار في موضع واحد، ولا
# يمكن أن تنحرف أداة عن أخواتها بصمت.

#: لكل أداة: (دالة RPC, عتبة التشابه, عدد المقاطع, وسم العرض في التنسيق القديم)
_TOOL_CONFIG: dict[str, tuple[str, float, int, str]] = {
    "legislation": ("match_legal_documents", 0.75, 3, ""),
    "drafts": ("match_legal_drafts", 0.70, 2, "هيكلة من: "),
    "contracts": ("match_legal_contracts", 0.70, 4, "بند من: "),
    "notices": ("match_legal_notices", 0.70, 3, "قسم من: "),
    "poa": ("match_legal_poa", 0.70, 3, "صلاحية من: "),
}

#: الرسالة المعروضة عند عدم وجود نتائج — لكل أداة صيغتها.
_EMPTY_RESULTS: dict[str, str] = {
    "legislation": "لا توجد نصوص قانونية مطابقة.",
    "drafts": "لا توجد مذكرات مطابقة.",
    "contracts": "لا توجد بنود عقود مطابقة.",
    "notices": "لا توجد إنذارات مطابقة.",
    "poa": "لا توجد وكالات مطابقة.",
}

_TOOL_ICONS: dict[str, str] = {
    "legislation": "🔍",
    "drafts": "📝",
    "contracts": "📄",
    "notices": "⚠️",
    "poa": "✍️",
}

_TOOL_LOG_LABELS: dict[str, str] = {
    "legislation": "Searching Legislation for",
    "drafts": "Searching Drafting Style for",
    "contracts": "Searching Contracts for",
    "notices": "Searching Legal Notices for",
    "poa": "Searching POAs for",
}

#: سقف ما يُعرض للنموذج من **كل مقطع** — لتقليل الرموز.
#:
#: ⚠️ كان السقف 1800 محرفاً على **مجموع** المقاطع، وكان يقطع في منتصف مقطع
#: ويُسقط المقاطع التي تليه بالكامل. صار السقف لكل مقطع على حدة، فلا يضيع
#: مقطع بسبب طول الذي قبله.
MAX_CHARS_PER_CHUNK = 1800


def _legacy_context(tool_key: str, rows: list[dict]) -> str:
    """
    التنسيق القديم بلا مراجع — يُستخدم عند غياب جامع الأدلة.

    أُبقي **حرفياً** كما كان، ليبقى سلوك المسارات التي لا تتحقّق (سطر الأوامر،
    Chainlit، Swarmmy) كما هو بالضبط. راجع `collect_evidence`.
    """
    label = _TOOL_CONFIG[tool_key][3]
    context = "".join(
        f"\n- {label}{row['document_name']}: {row['chunk_content']}\n" for row in rows
    )
    return context[:1800] + "\n... (تم الاقتطاع)" if len(context) > 1800 else context


def _build_evidence(
    tool_key: str, rows: list[dict], allocator: RefAllocator
) -> list[Evidence]:
    """يحوّل صفوف RPC إلى أدلّة مرقّمة، مع تطبيق سقف الطول."""
    evidence: list[Evidence] = []
    for row in rows:
        text = str(row.get("chunk_content") or "")
        if len(text) > MAX_CHARS_PER_CHUNK:
            text = text[:MAX_CHARS_PER_CHUNK] + "\n... (تم الاقتطاع)"
        evidence.append(
            Evidence(
                ref=allocator.next_ref(tool_key),
                chunk_id=str(row.get("id", "")),
                document_name=str(row.get("document_name") or ""),
                text=text,
                similarity=row.get("similarity"),
                tool=tool_key,
            )
        )
    return evidence


def _search(tool_key: str, query: str) -> str:
    """
    المسار الواحد لكل أدوات الاسترجاع الخمس.

    إن كان جامع أدلة نشطاً (انظر `collect_evidence`) سُجّلت المقاطع بمراجع
    قصيرة وأُعيد نصّ مرقَّم يستطيع النموذج الاقتباس منه — وعندها يمكن التحقّق.
    وإن لم يكن، أُعيد التنسيق القديم كما كان بالضبط.
    """
    rpc_name, threshold, count, _label = _TOOL_CONFIG[tool_key]
    print(f"\n[Agent Tool] {_TOOL_ICONS[tool_key]} {_TOOL_LOG_LABELS[tool_key]}: {query}")

    response = get_supabase().rpc(
        rpc_name,
        {
            "query_embedding": encode_query(query),
            "match_threshold": threshold,
            "match_count": count,
        },
    ).execute()

    rows = response.data or []
    if not rows:
        return _EMPTY_RESULTS[tool_key]

    collector = current_collector()
    if collector is None:
        return _legacy_context(tool_key, rows)

    evidence = _build_evidence(tool_key, rows, collector.allocator)
    collector.add(evidence)
    return format_evidence_block(evidence)


# 1. أداة التشريعات والأحكام
@tool
def search_uae_legislation(query: str) -> str:
    """استخدم هذه الأداة للبحث عن السند القانوني والتشريعات والأحكام."""
    return _search("legislation", query)

# 2. أداة المذكرات والمسودات
@tool
def search_drafting_style(query: str) -> str:
    """استخدم هذه الأداة حصراً عند طلب صياغة (مذكرة دفاع، لائحة دعوى، طعن، تعقيب)."""
    return _search("drafts", query)

# 3. أداة العقود
@tool
def search_contract_clauses(query: str) -> str:
    """استخدم هذه الأداة حصراً عند طلب صياغة (عقد، اتفاقية، ملحق تعديل)."""
    return _search("contracts", query)

# 4. أداة الإنذارات
@tool
def search_legal_notices(query: str) -> str:
    """استخدم هذه الأداة حصراً عند طلب صياغة (إنذار قانوني، إنذار عدلي، إشعار، رد على إنذار)."""
    return _search("notices", query)

# 5. أداة الوكالات
@tool
def search_poa_clauses(query: str) -> str:
    """استخدم هذه الأداة حصراً عند طلب صياغة (وكالة، توكيل خاص، توكيل عام، تفويض)."""
    return _search("poa", query)

# ==============================================================================
# موجّه التوجيه الموحّد — مصدر واحد لكل الواجهات
# ==============================================================================
# يُستورَد في: main.py · app_chainlit.py · smart_office.py
# ويُستخدم هنا في __main__.
#
# سبب التوحيد: كان هذا الموجّه منسوخاً حرفياً في أربعة ملفات، فأي تعديل على
# قواعد التوجيه أو التنسيق كان يحتاج أربع تعديلات ويُنسى أحدها — وهذا ما حدث
# فعلاً: أداة التشريعات كانت مُسقطة من نسخة main.py وحدها.
# ==============================================================================

ROUTING_RULES = (
    "قواعد التوجيه:\n"
    "1. مذكرات ولوائح ومحاكم -> 'search_drafting_style'.\n"
    "2. عقود واتفاقيات وملاحق -> 'search_contract_clauses'.\n"
    "3. إنذارات وإشعارات -> 'search_legal_notices'.\n"
    "4. وكالات وتوكيلات وتفويض -> 'search_poa_clauses'.\n"
    "5. السند القانوني والتشريعات والأحكام -> 'search_uae_legislation'. "
    "استدعِ هذه الأداة أيضاً كلما احتجت مادة قانونية تستند إليها.\n"
    "التزم بأداة أسلوب واحدة تتناسب مع نوع الطلب، مع أداة التشريعات عند الحاجة. "
    "لا تستدعِ الأداة نفسها مرتين.\n"
)

# ------------------------------------------------------------------------------
# قواعد التنسيق
# ------------------------------------------------------------------------------
# أُضيفت بعد أن ظهرت علامات Markdown حرفياً في مستند مولَّد فعلاً:
#     **لائحة دعوى تجارية**      ### **موضوع الدعوى:**
# والسبب أن الواجهة تعرض النص كما هو، والمستند يُنسخ مباشرة إلى Word.
# ------------------------------------------------------------------------------
FORMATTING_RULES = (
    "تنسيق المخرج (إلزامي): اكتب نصاً عربياً عادياً بلا أي ترميز Markdown، "
    "لأن المستند سيُنسخ مباشرة إلى محرر نصوص مثل Word.\n"
    "يُمنع استخدام النجوم للتسميك أو التعريف: لا ** ولا * ولا __ .\n"
    "يُمنع استخدام وسم العنوان: لا # ولا ## ولا ### .\n"
    "يُمنع استخدام الشرطة أو النجمة في بداية السطر كتعداد، ولا علامة الاقتباس > "
    "ولا الجداول ولا الخطوط الأفقية --- .\n"
    "استخدم بدلاً من ذلك: للعناوين سطراً عادياً ينتهي بنقطتين مثل 'الوقائع:' أو "
    "'أولاً: الوقائع'، وللتعداد أرقاماً مثل '1.' و'2.' أو 'أولاً' و'ثانياً'.\n"
)

SYSTEM_PROMPT = (
    "أنت مستشار قانوني إماراتي خبير. مهمتك صياغة المستندات بناءً على أسلوب "
    "المستخدم المخزن في قواعد البيانات.\n"
    + ROUTING_RULES
    + FORMATTING_RULES
    + "اكتب المخرج النهائي مباشرة مقلداً أسلوب المستخدم، دون مقدمات أو تعليقات "
    "جانبية أو شرح لما تفعله. إن لم تجد سنداً في السياق المسترجع، اكتب المستند "
    "واعتمد على القواعد القانونية الإماراتية العامة دون تأليف نصوص مواد."
)

# ------------------------------------------------------------------------------
# قواعد توثيق الأسانيد
# ------------------------------------------------------------------------------
# تُضاف إلى الموجّه **فقط** في الواجهات التي تفتح جامع أدلة (`collect_evidence`)،
# لأنها الوحيدة التي تستطيع التحقّق فعلاً. فمطالبة النموذج بالاقتباس في واجهة
# لا تتحقّق منه تُنتج أسانيد لا يفحصها أحد — وهي أسوأ من غيابها، لأنها تُوهم
# المحامي بأن المسودّة موثَّقة.
#
# ولذلك `SYSTEM_PROMPT` نفسها لم تُعدَّل: بقيت Chainlit وSwarmmy وسطر الأوامر
# على سلوكها السابق بالضبط.
# ------------------------------------------------------------------------------
CITATION_RULES = (
    "توثيق الأسانيد (إلزامي):\n"
    "المقاطع المسترجعة تأتي مرقّمة بمراجع مثل [L1] و[C2] و[N1].\n"
    "1. كل استناد إلى حكم أو مادة أو بند في المتن يجب أن يقابله سند في كتلة "
    "الأسانيد.\n"
    "2. السند اقتباس **حرفي** من نصّ المقطع: انسخ العبارة كما وردت بلا إعادة "
    "صياغة ولا اختصار ولا تصرّف في الألفاظ.\n"
    "3. اكتب كل سند في سطر مستقل: المرجع، ثم الفاصل ::، ثم الاقتباس. وضع "
    "الأسطر كلها بين هذين الوسمين في آخر المستند:\n"
    f"{CITATIONS_BEGIN}\n"
    "L1 :: العبارة الحرفية كما وردت في المقطع\n"
    f"{CITATIONS_END}\n"
    "4. ضع الكتلة مرة واحدة في آخر المستند، ولا تشرحها ولا تعلّق عليها ولا "
    "تكرّرها.\n"
    "5. لا تذكر رقم مادة لم يرد في المقاطع المسترجعة. وإن لم تجد سنداً لحكمٍ "
    "تريد ذكره فاحذفه.\n"
    "6. الاقتباس القصير لا يُقبل: انقل عبارة كاملة ذات معنى، لا كلمة أو "
    "كلمتين.\n"
)

#: الموجّه الموحّد **مع** قواعد التوثيق **وقواعد احتساب المستحقات العمالية** —
#: للواجهات التي تفتح جامع أدلة.
#:
#: ⚠️ وقواعد الاحتساب تُلحَق هنا ولا تُلحَق بـ `SYSTEM_PROMPT`: الذي لا يتحقّق من
#: الأسانيد لا يحتاج قواعد الحساب، والقواعد تُضاف حيث يوجد مسار يتحقّق فعلاً —
#: وهو المبدأ نفسه الذي بُنيت عليه `CITATION_RULES`.
#:
#: ولماذا في **الموجّه** لا في المحادثة؟ لأن تشغيلاً حقيقياً أنتج مذكرة عمالية
#: حُسب فيها بدل الإجازة على الأجر الشامل (٨٠٠٠) بدل الأساسي (٥٠٠٠)، **وقد كان
#: المراجع القانوني قد أبلغ النموذج بالعيب في محادثة صريحة، فعاد العيب في التشغيل
#: التالي**. فالتصحيح الذي يعيش في حوار لا يصل إلى المسار؛ والقاعدة التي تعيش في
#: الموجّه تصل إلى كل تشغيل. والتفصيل في صدر `labour_rules.py`.
SYSTEM_PROMPT_CITED = SYSTEM_PROMPT + CITATION_RULES + rules_block()


class State(TypedDict):
    messages: Annotated[list, add_messages]

# إعداد النموذج مع ربط جميع الأدوات
llm = ChatGoogleGenerativeAI(
    model="gemini-3.8-flash",
    google_api_key=os.environ.get("GOOGLE_API_KEY"),
    temperature=0.3,
)
tools = [
    search_uae_legislation, 
    search_drafting_style, 
    search_contract_clauses, 
    search_legal_notices, 
    search_poa_clauses
]
llm_with_tools = llm.bind_tools(tools)

def chatbot_node(state: State):
    return {"messages": [llm_with_tools.invoke(state["messages"])]}

graph_builder = StateGraph(State)
graph_builder.add_node("chatbot", chatbot_node)
graph_builder.add_node("tools", ToolNode(tools=tools))
graph_builder.add_edge(START, "chatbot")
graph_builder.add_conditional_edges("chatbot", tools_condition)
graph_builder.add_edge("tools", "chatbot")

agent = graph_builder.compile()

if __name__ == "__main__":
    # سؤال اختبار للإنذارات كمثال:
    question = "اكتب لي إنذار قانوني موجه من شركة عقارية إلى مستأجر متأخر عن سداد الإيجار لمدة 3 أشهر، طالبه بالسداد أو الإخلاء. استخدم صيغة إنذاراتي السابقة المعتمدة."
    print(f"المستخدم: {question}")
    
    # الموجّه الموحّد — معرَّف مرة واحدة أعلى هذا الملف
    events = agent.stream({"messages": [("system", SYSTEM_PROMPT), ("user", question)]}, stream_mode="values")
    
    for event in events:
        message = event["messages"][-1]
        if message.content:
            print(f"\n⚖️ العقل القانوني:\n{message.content}")