import os
from dotenv import load_dotenv
from supabase import create_client, Client
from sentence_transformers import SentenceTransformer
from typing import Annotated, Optional
from typing_extensions import TypedDict
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition

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

# 1. أداة التشريعات والأحكام
@tool
def search_uae_legislation(query: str) -> str:
    """استخدم هذه الأداة للبحث عن السند القانوني والتشريعات والأحكام."""
    print(f"\n[Agent Tool] 🔍 Searching Legislation for: {query}")
    query_vector = encode_query(query)
    response = get_supabase().rpc('match_legal_documents', {'query_embedding': query_vector, 'match_threshold': 0.75, 'match_count': 3}).execute()
    if not response.data: return "لا توجد نصوص قانونية مطابقة."
    context = "".join([f"\n- {res['document_name']}: {res['chunk_content']}\n" for res in response.data])
    return context[:1800] + "\n... (تم الاقتطاع)" if len(context) > 1800 else context

# 2. أداة المذكرات والمسودات
@tool
def search_drafting_style(query: str) -> str:
    """استخدم هذه الأداة حصراً عند طلب صياغة (مذكرة دفاع، لائحة دعوى، طعن، تعقيب)."""
    print(f"\n[Agent Tool] 📝 Searching Drafting Style for: {query}")
    query_vector = encode_query(query)
    response = get_supabase().rpc('match_legal_drafts', {'query_embedding': query_vector, 'match_threshold': 0.70, 'match_count': 2}).execute()
    if not response.data: return "لا توجد مذكرات مطابقة."
    context = "".join([f"\n- هيكلة من: {res['document_name']}: {res['chunk_content']}\n" for res in response.data])
    return context[:1800] + "\n... (تم الاقتطاع)" if len(context) > 1800 else context

# 3. أداة العقود
@tool
def search_contract_clauses(query: str) -> str:
    """استخدم هذه الأداة حصراً عند طلب صياغة (عقد، اتفاقية، ملحق تعديل)."""
    print(f"\n[Agent Tool] 📄 Searching Contracts for: {query}")
    query_vector = encode_query(query)
    response = get_supabase().rpc('match_legal_contracts', {'query_embedding': query_vector, 'match_threshold': 0.70, 'match_count': 4}).execute()
    if not response.data: return "لا توجد بنود عقود مطابقة."
    context = "".join([f"\n- بند من: {res['document_name']}: {res['chunk_content']}\n" for res in response.data])
    return context[:1800] + "\n... (تم الاقتطاع)" if len(context) > 1800 else context

# 4. أداة الإنذارات
@tool
def search_legal_notices(query: str) -> str:
    """استخدم هذه الأداة حصراً عند طلب صياغة (إنذار قانوني، إنذار عدلي، إشعار، رد على إنذار)."""
    print(f"\n[Agent Tool] ⚠️ Searching Legal Notices for: {query}")
    query_vector = encode_query(query)
    response = get_supabase().rpc('match_legal_notices', {'query_embedding': query_vector, 'match_threshold': 0.70, 'match_count': 3}).execute()
    if not response.data: return "لا توجد إنذارات مطابقة."
    context = "".join([f"\n- قسم من: {res['document_name']}: {res['chunk_content']}\n" for res in response.data])
    return context[:1800] + "\n... (تم الاقتطاع)" if len(context) > 1800 else context

# 5. أداة الوكالات
@tool
def search_poa_clauses(query: str) -> str:
    """استخدم هذه الأداة حصراً عند طلب صياغة (وكالة، توكيل خاص، توكيل عام، تفويض)."""
    print(f"\n[Agent Tool] ✍️ Searching POAs for: {query}")
    query_vector = encode_query(query)
    response = get_supabase().rpc('match_legal_poa', {'query_embedding': query_vector, 'match_threshold': 0.70, 'match_count': 3}).execute()
    if not response.data: return "لا توجد وكالات مطابقة."
    context = "".join([f"\n- صلاحية من: {res['document_name']}: {res['chunk_content']}\n" for res in response.data])
    return context[:1800] + "\n... (تم الاقتطاع)" if len(context) > 1800 else context

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