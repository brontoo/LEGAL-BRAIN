"""
LEGAL-BRAIN — خادم الـ API (FastAPI)
================================================================================
نقطة الدخول الوحيدة للنظام. يخدم:

    GET  /            صفحة اختبار بسيطة للتحقق من البث الحي (SSE)
    GET  /health      فحص صحة الخادم وجاهزية الأدوات
    POST /generate    توليد مستند ببثّ حيّ (Server-Sent Events)  ← تستخدمه Next.js
    POST /chat        محادثة عادية بردّ JSON كامل (متوافق مع الإصدار السابق)

التشغيل:
    uvicorn main:app --reload --port 8000

عقد البث (SSE) الذي تتوقّعه الواجهة في frontend/app/workspace/page.tsx:
    data: {"type": "case",      "report": {...}}                    ملف القضية — **أول إطار**
    data: {"type": "stage",     "stage": "...", "message": "..."}    مرحلة جارية
    data: {"type": "citations", "report": {...}}                    تقرير الأسانيد
    data: {"type": "language",  "report": {...}}                    تقرير التدقيق اللغوي
    data: {"type": "review",    "report": {...}}                    تقرير المراجعة الثانية
    data: {"type": "facts",     "report": {...}}                    فحص أمانة الوقائع
    data: {"type": "briefing",  "report": {...}, "markdown": "..."}  التقرير الداخلي
    data: {"type": "done",      "document": "..."}                  المستند النهائي
    data: {"type": "error",     "message": "..."}                   فشل

وترتيب إطارات التقارير ثابت، وهو ترتيب بناء ما تُبلِّغ عنه:
    case ← المراحل (وكل مرحلة تُبثّ **قبل** نتيجتها) ← citations ← language
    ← review ← facts ← briefing ← مرحلة الختم ← done

⚠️ **و`facts` قبل الختم عن قصد**: الواقعة المُغيَّرة تُرى **قبل** أن يُعتمد
المستند لا بعده — وهذا هو العيب الذي تكرّر في ثلاث مسودّات.
⚠️ **و`briefing` آخر إطار تقرير**: لا يُبنى بعده شيء، لأن «لا عمل بعد الختم إلا
التسليم» — فلا يُحسب تقرير بعد أن يُختم المستند.

سجلّ التغييرات عن النسخة السابقة:
  * أُضيف POST /generate مع بثّ SSE حقيقي — كان مُعلَناً في الـ commit ولكنه غائب.
  * الذاكرة لم تعد متغيّراً عامّاً مشتركاً بين كل المستخدمين؛ صارت لكل جلسة.
  * أُضيفت أداة التشريعات (search_uae_legislation) إلى موجّه التوجيه — كانت
    مُسقطة، فكان التطبيق عاجزاً عن الاستشهاد بالسند القانوني.
  * أُضيف CORS قابل للضبط من متغيّرات البيئة.
  * حُذف server.py لأنه كان نسخة مكررة حرفياً من هذا الملف.
  * وُصل `facts.py` و`briefing.py` بالمسار الحيّ: الأول يحكم على **أمانة
    الوقائع في المسودّة** (وكان العيب الذي تكرّر ثلاث مرّات)، والثاني يُخرج
    **تقرير المحامي الداخلي**. وكانا مبنيَّين ومختبرَين ولا يُناديان من أيّ
    موضع — فكانا يوجدان ولا يُغيّران شيئاً، كحال `case_file.py` قبلهما.
================================================================================
"""

import asyncio
import json
import os
import secrets
import threading
from collections import OrderedDict
from dataclasses import dataclass
from functools import partial
from typing import Any, AsyncIterator, Mapping, Optional, Sequence

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from pydantic import BaseModel, Field

import case_file as case_file_module
from case_file import CaseFile, CaseStage, DisputeType, Party
from citations import (
    parse_citations,
    strip_citations_block,
    unbacked_article_refs,
    verify_citations,
)
from attribution import summarize as summarize_attribution
from attribution import verify_attributions
from legal_agent import SYSTEM_PROMPT_CITED, agent, collect_evidence, get_supabase, llm
from language_audit import audit_language
from language_audit import summarize as summarize_language_audit
from review import build_review_prompt, parse_review
from review import summarize as summarize_review
from revisions import RevisionRejected, build_revision, summarize

# ⚠️ **و`facts` و`briefing` يُستوردان في صدر الملف لا داخل دالّة.** وليس ذلك
# ترتيباً شكلياً: كلاهما مكتبة بايثون القياسية وحدها (لا شبكة ولا قرص ولا نموذج)،
# فاستيرادهما لا يكلّف شيئاً ولا يفشل في التشغيل. والاستيراد داخل دالّة **يُخفي
# عطب الاستيراد إلى لحظة الطلب** — وهو صنف العطب الذي وُلد `test_module_health.py`
# لأجله: وحدة كانت ترفع `ValueError` عند الاستيراد فلم يعلم أحد لأن لا مسار
# يستوردها. فالاستيراد هنا يُفشل الإقلاع **إن فشل**، وهو الموضع الذي يُصلَح فيه.
import briefing
from facts import (
    Fact,
    FactLedger,
    Standing,
    SystemOverclaimError,
    assert_system_does_not_agree,
    check_fidelity,
)
from facts import summarize as summarize_facts

# ⚠️ **وَ`revision_loop` يُستورد في صدر الملف لا داخل دالّة** — وللعلّة نفسها
# المكتوبة أعلاه في `facts` و`briefing`: استيرادٌ داخل دالّة **يُخفي عطب
# الاستيراد إلى لحظة الطلب**، فيبقى العطب صامتاً حتى يقع في وجه محامٍ.
# وهذه الوحدة مكتبة بايثون القياسية وحدها: لا شبكة ولا قرص ولا نموذج.
import revision_loop

import claims as claims_module
load_dotenv()

# ==============================================================================
# ١. الإعداد
# ==============================================================================

MAX_HISTORY_TURNS = int(os.environ.get("MAX_HISTORY_TURNS", "6"))
MAX_SESSIONS = 100  # حد أعلى لعدد الجلسات المحفوظة في الذاكرة

# حد أقصى لعدد خطوات الوكيل (chatbot → tools → chatbot ...) لمنع الحلقات اللانهائية
AGENT_RECURSION_LIMIT = 12

# ------------------------------------------------------------------------------
# مصادقة الـ API
# ------------------------------------------------------------------------------
# إن ضُبط API_TOKEN، تُلزَم نقاط النهاية الحسّاسة بترويسة:
#     Authorization: Bearer <API_TOKEN>
# وإن لم يُضبط، يعمل الخادم بلا مصادقة (وضع التطوير) مع تحذير عند الإقلاع.
#
# ⚠️ يجب ضبطه قبل أي نشر عام: بدونه أي زائر يصل إلى أرشيفك القانوني ويستهلك
#    رصيد Gemini على حسابك.
#
# ⚠️ ولا تضعه في متغيّر يبدأ بـ NEXT_PUBLIC_ إطلاقاً — فذلك يُحزّمه داخل
#    جافاسكربت المتصفح فيصبح الرمز علنياً وتصبح المصادقة بلا معنى. الواجهة
#    ترسله من خادم Next.js عبر الوسيط frontend/app/api/[...path]/route.ts.
API_TOKEN = os.environ.get("API_TOKEN", "").strip()


async def require_token(authorization: Optional[str] = Header(default=None)) -> None:
    """يفرض API_TOKEN إن كان مُعرَّفاً، ويسمح بالمرور إن لم يكن (وضع التطوير)."""
    if not API_TOKEN:
        return

    expected = f"Bearer {API_TOKEN}"
    provided = authorization or ""

    # مقارنة بزمن ثابت (constant-time) بدل == العادية: تمنع تسريب طول الرمز
    # أو بادئته عبر فروق زمن التنفيذ. نقارن bytes لأن compare_digest مع str
    # يشترط محارف ASCII فقط، وترويسة الطلب قد تحمل غير ذلك.
    if not secrets.compare_digest(provided.encode("utf-8"), expected.encode("utf-8")):
        raise HTTPException(
            status_code=401,
            detail="مصادقة مطلوبة: أضف الترويسة Authorization: Bearer <API_TOKEN>",
            headers={"WWW-Authenticate": "Bearer"},
        )


if not API_TOKEN:
    print(
        "\n"
        "⚠️  تحذير أمني: API_TOKEN غير مُعرَّف — الخادم يعمل بلا مصادقة.\n"
        "    أي شخص يصل إلى هذا العنوان يستطيع استخدام أرشيفك القانوني\n"
        "    واستهلاك رصيد Gemini على حسابك.\n"
        "    اضبطه في .env قبل أي نشر عام. انظر .env.example\n"
    )

# ------------------------------------------------------------------------------
# موجّه التوجيه: يُستورَد من legal_agent.py — مصدر واحد لكل الواجهات.
# كان منسوخاً هنا حرفياً، ولهذا سقطت منه أداة التشريعات وحدها بينما بقيت في
# بقية النسخ، فكان التطبيق المخدوم عاجزاً عن الاستشهاد بالسند القانوني.
# وقواعد منع Markdown (FORMATTING_RULES) مُضمَّنة فيه أيضاً.
# ------------------------------------------------------------------------------

# أنسب أداة أسلوب لكل نوع مستند — يُستخدم كتلميح صريح في الطلب
DOC_TYPE_TOOL_HINT = {
    "لائحة دعوى تجارية": "search_drafting_style",
    "لائحة دعوى": "search_drafting_style",
    "مذكرة دفاع": "search_drafting_style",
    "إنذار قانوني": "search_legal_notices",
    "وكالة قانونية خاصة": "search_poa_clauses",
    "وكالة": "search_poa_clauses",
    "عقد": "search_contract_clauses",
    "اتفاقية": "search_contract_clauses",
}

# رسالة المرحلة المعروضة للمستخدم عند استدعاء كل أداة
TOOL_STAGE_LABELS = {
    "search_uae_legislation": "جاري البحث في التشريعات والأحكام الاتحادية...",
    "search_drafting_style": "جاري استرجاع أسلوب مذكراتك ولوائحك المعتمدة...",
    "search_contract_clauses": "جاري استرجاع بنود عقودك المعتمدة...",
    "search_legal_notices": "جاري استرجاع صيغ إنذاراتك المعتمدة...",
    "search_poa_clauses": "جاري استرجاع صيغ وكالاتك المعتمدة...",
}

STAGE_ANALYSING = "جاري تحليل الطلب وتحديد المسار القانوني..."
STAGE_EVIDENCE_FOUND = "تم استرجاع السند من أرشيفك — جاري الصياغة..."
STAGE_DRAFTING = "الفريق القانوني يصوغ المستند الآن..."
STAGE_VERIFYING = "المفتش ثُغرة يراجع كل سند قبل التسليم..."
STAGE_POLISHING = "سيبويه المُكشّر يضبط الصياغة..."
STAGE_SEALING = "المعلم أبو الختم يعتمد المستند ويختمه..."
STAGE_REVIEWING = "المفتش ثُغرة يقرأ المسودّة كخصم قبل التسليم..."


# ------------------------------------------------------------------------------
# مفاتيح المراحل — معرّفات آلية ثابتة تُرسل مع كل حدث `stage`
# ------------------------------------------------------------------------------
# ⚠️ لماذا مفتاح آلي **مع** النصّ العربي، لا النصّ وحده؟
#
# لأن الواجهة تبني عليها مشهد «فريق المكتب»: أي شخصية تعمل الآن وأيّها انتهى.
# ولو ربطت الواجهة على **النصّ العربي** لانكسر المشهد بصمت عند أول تعديل
# صياغة — وهو النوع نفسه من العطب الذي أصلحناه في الأدوات الخمس (انحراف نسخة
# عن أخرى بلا خطأ ظاهر).
#
# فالمفتاح ثابت لا يتغيّر أبداً، والنصّ المعروض يتغيّر متى شئنا.

KEY_INTAKE = "intake"
KEY_EVIDENCE = "evidence"
KEY_DRAFTING = "drafting"
KEY_VERIFYING = "verifying"
KEY_POLISH = "polish"
KEY_SEAL = "seal"
KEY_REVIEW = "review"

#: من اسم الأداة إلى مفتاح الشخصية التي تشتغل.
TOOL_STAGE_KEYS = {
    "search_uae_legislation": "legislation",
    "search_drafting_style": "drafts",
    "search_contract_clauses": "contracts",
    "search_legal_notices": "notices",
    "search_poa_clauses": "poa",
}


@dataclass(frozen=True)
class StageEvent:
    """
    مرحلة واحدة: مفتاح آلي ثابت + نصّ عربي يُعرض للمستخدم.

    الفصل بينهما مقصود: الواجهة تقرّر **بالمفتاح**، وتعرض **النصّ**.
    """

    key: str
    message: str

# ==============================================================================
# ٢. التطبيق و CORS
# ==============================================================================

app = FastAPI(
    title="Legal Brain API",
    description="العقل القانوني الإماراتي — واجهة توليد المستندات القانونية",
    version="2.0.0",
)

_allowed_origins = [
    o.strip()
    for o in os.environ.get(
        "ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
    ).split(",")
    if o.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==============================================================================
# ٣. النماذج
# ==============================================================================


class ChatRequest(BaseModel):
    prompt: str = Field(..., min_length=1, description="طلب المستخدم")
    session_id: Optional[str] = Field(
        None, description="معرّف الجلسة لعزل ذاكرة كل مستخدم"
    )


class CasePayload(BaseModel):
    """
    ملف القضية كما يصل من الواجهة — **كل حقل فيه اختياري على مستوى النقل**.

    ⚠️ **والحمل الفارغ مقبول عن قصد، والفراغ ليس قيمة مفترضة:** هو «لم يُقل»
    فيُقرأ في ``CaseFile.missing()`` ويُسأل عنه. والقاعدة التي تمنع الجواب
    المفترض في `case_file.py` لا في هذا النموذج — فالتحقّق هنا **نقلٌ لا حكم**:
    يترجم الحقول، ويردّ ما يرفضه الملف برسالة الملف نفسها.

    ⚠️ **ولماذا لا تُشترط الحقول هنا؟** لو شُترطت لصار الملف الناقص — وهو
    الواقع في كل قضية قبل مراجعة المحامي — **طلَباً مرفوضاً** بدل أن يُبثّ
    تقريرُ نقصه. والملف الناقص **لا يوقف الصياغة**، بل يُبثّ ويُسأل عنه.

    ⚠️ **والحقول بلا ``Field`` عن قصد، وبلا افتراضي غير ``None``:** الغياب
    يجب أن يصل **غائباً** إلى ``CaseFile``، فحقوله بلا افتراضي هناك. ووصفُ
    الحقل في `Field` لا يُقرأ في هذا المشروع (الواجهة تحدّد شكلها)، ووهميّ
    `BaseModel` في الاختبار **لا يفكّ ``Field`` إلى قيمته الافتراضية** — فلو
    كُتبت لصار الحقل الغائب علامةً داخليّة تُمرَّر إلى الملف وتُقرأ نصّاً.

    Attributes:
        emirate: نصّ الإمارة كما كتبه المحامي — يقبل صورته العربية
            («أبوظبي»، «أبو ظبي»، «إمارة دبي») واللاتينية («dubai»).
        dispute_type: قيمة آلية من ``DisputeType`` — ولا تُستنبط من نصّ الوقائع.
        stage: قيمة آلية من ``CaseStage``.
        our_party: صفتنا من ``Party`` — ولا قيمة محايدة فيها.
        key_dates: أزواج (وصف التاريخ، التاريخ) — والتاريخ **نصّ** كما ورد،
            فلا يُحوَّل هنا ولا يُقرَّب: التحويل موضع عدّ المدّة وحده.
    """

    country: Optional[str] = None
    emirate: Optional[str] = None
    forum: Optional[str] = None
    dispute_type: Optional[str] = None
    stage: Optional[str] = None
    our_party: Optional[str] = None
    claims: Optional[list] = None
    key_dates: Optional[list] = None
    likely_law: Optional[list] = None
    # ⚠️ ``None`` تعني **لم يُنظر**، لا «لا». والفرق يُسأل عنه في
    # `open_regime_questions` — ولو قُرئت ``None`` بمعنى النفي لسقط السؤال.
    has_arbitration_clause: Optional[bool] = None
    has_choice_of_law: Optional[bool] = None


class FactPayload(BaseModel):
    """
    واقعة واحدة كما تصل من الواجهة — **وكل حقل فيها اختياري على مستوى النقل**.

    ⚠️ **ولا يُحكم هنا على الواقعة، بل يُنقل شكلها إلى `facts.py` وحده.**
    والسبب أن الوحدة هي التي تعرف معنى «مفتاح» و«درجة» و«نصّ» — ونسخةٌ ثانية
    من الحكم هنا **تنحرف عنها بصمت**، فيُقبل ما ترفضه أو يُرفض ما تقبله.

    ⚠️ **والحقل الغائب يبقى غائباً**: لا افتراضي يُخترع لدرجة ولا لمصدر. والفرق
    أن درجة الواقعة (`standing`) **يُردّ الطلب بغيابها** لأنها وزن الواقعة في
    المذكرة وافتراضُها حكمٌ لم يكتبه أحد؛ أما `quote` فيجوز أن يغيب — وتُسجَّل
    الواقعة بلا نصّ، ويُعلَن ذلك في ``unquoted`` من الوحدة.

    Attributes:
        key:      معرّف آلي ثابت — به تُنادى الواقعة وبه تُقارَن.
        statement: الواقعة بالعربية، جملةً واحدة.
        source:   اسم المستند الذي جاءت منه.
        locus:    الموضع (صفحة أو بند).
        date:     تاريخ الواقعة كما ورد، أو ``None`` — **ولا يُحوَّل هنا**.
        asserted_by: من يتمسّك بها.
        standing: قيمة آلية من ``Standing`` — ولا تُستنبط من نصّ الواقعة.
        quote:    النصّ الذي تستند إليه حرفياً، أو ``None`` لما لا نصّ له.
    """

    key: Optional[str] = None
    statement: Optional[str] = None
    source: Optional[str] = None
    locus: Optional[str] = None
    date: Optional[str] = None
    asserted_by: Optional[str] = None
    standing: Optional[str] = None
    quote: Optional[str] = None


class GenerateRequest(BaseModel):
    prompt: str = Field(..., min_length=1, description="الوقائع والمعطيات")
    doc_type: str = Field("مستند قانوني", description="نوع المستند المطلوب")
    session_id: Optional[str] = None
    #: ملف القضية — **كل حقوله اختياريّة، والحمل الفارغ يعني «لم يُقل».**
    #: وغيابه الكامل يعني «لم يُنشأ ملف قضية»، وهو ما يُقال صراحةً في الرسالة
    #: وفي إطار `case` — فالغياب معلومة، لا فراغ يُسكت عنه.
    #: ⚠️ والتصنيف **نصّاً لا كائناً** (كما في `_sessions` أعلاه): لا نُقيّم
    #: ``Optional[CasePayload]`` عند التعريف، فيعمل الملف على أي إصدار بايثون.
    case: Optional["CasePayload"] = None
    #: سجلّ وقائع القضية — **قائمة وقائع، وليس فيها حقل مطلوب على مستوى النقل**.
    #: وغيابه الكامل يعني «لم يُرسل سجلّ»، وهو ما يُقال صراحةً في إطار `facts`:
    #: **فحصٌ لم يُشغَّل، لا فحصٌ ناجح.**
    #: ⚠️ **ولا يُبتلع السجلّ الفاسد**: `FactLedger` يرفضه فيُردّ الطلب ٤٠٠
    #: برسالته هو، **قبل أن يُستدعى نموذج واحد** — لأن سجلّاً فاسداً يُتجاهَل
    #: صامتاً يُوهم المستدعي أنّ وقائعه قُوبلت، فتُبنى المسودّة على غير ما أرسل.
    #: ⚠️ والعنصر الواحد `FactPayload` — والتحقّق **شكلُ نقلٍ لا حكم**: الحكم
    #: على معنى الواقعة في `facts.py` وحده.
    facts: Optional[list["FactPayload"]] = None


class RevisionRequest(BaseModel):
    """
    زوج (مسودّة ← نسخة المحامي المعتمدة).

    ⚠️ `corrected_text` هو **ما اعتمده المحامي** بعد تعديله، لا ما أنتجه النموذج.
    وهذا الفرق هو ما يجعل السجلّ ذا قيمة: الحقيقة ما قاله المحامي.
    """

    generated_text: str = Field(..., min_length=1, description="ما أنتجه النموذج")
    corrected_text: str = Field(..., min_length=1, description="نسختك المعتمدة")
    prompt: Optional[str] = Field(None, description="الوقائع التي أدخلتها")
    doc_type: Optional[str] = None
    session_id: Optional[str] = None


#: جدول التصحيحات — **ليس جزءاً من قاعدة المعرفة** ولا يدخل الاسترجاع.
#: انظر القسم ١٠ في `schema.sql` لسبب غياب عمود embedding عنه عمداً.
REVISIONS_TABLE = "draft_revisions"


def _revision_storage_error(exc: Exception) -> str:
    """
    رسالة مفهومة عند فشل حفظ التصحيح.

    وأشيع سببه أن الجدول غير موجود بعد. و«relation does not exist» وحدها لا
    تدلّ على المطلوب، فنسمّي القسم الدقيق في `schema.sql`.
    """
    message = str(exc)
    if (
        REVISIONS_TABLE in message
        or "42P01" in message
        or "does not exist" in message
        or "Could not find the table" in message
    ):
        return (
            f"جدول {REVISIONS_TABLE} غير موجود في قاعدة البيانات. "
            "نفّذ القسم ١٠ من schema.sql في Supabase SQL Editor مرة واحدة."
        )
    return f"تعذّر حفظ التصحيح: {message}"


# ------------------------------------------------------------------------------
# الأرشيف — دوالّ القسم ١١ في schema.sql
# ------------------------------------------------------------------------------
# ⚠️ مفتاح آلي **و** وسم عربي، كما في مفاتيح المراحل: الواجهة تقرّر بالمفتاح
#    وتعرض الوسم. فلو رُبطت بالوسم لانكسرت التصفية بصمت عند أول تعديل صياغة.
ARCHIVE_FAMILIES: tuple[tuple[str, str], ...] = (
    ("legislation", "التشريعات والأحكام"),
    ("drafts", "المذكرات واللوائح"),
    ("contracts", "العقود والاتفاقيات"),
    ("notices", "الإنذارات"),
    ("poa", "الوكالات"),
)

ARCHIVE_OVERVIEW_RPC = "archive_overview"
ARCHIVE_DOCUMENTS_RPC = "archive_documents"
ARCHIVE_CHUNKS_RPC = "archive_chunks"

#: سقف صفوف قائمة المستندات — مطابق لسقف دالة SQL نفسها (دفاعٌ مزدوج).
ARCHIVE_MAX_ROWS = 500

#: وسقف المقاطع أقلّ: نصّ المقطع أطول بكثير من اسم مستند، فـ٢٠٠ مقطع تعني
#: حمولة قد تبلغ ميغابايتات. والسقف في القاعدة أيضاً.
ARCHIVE_MAX_CHUNK_ROWS = 200

#: أوامر الفرز المسموحة: مفتاح آلي ← ما تفهمه دالّة SQL.
#: ⚠️ والتحقّق **برفض ما ليس هنا (400)** لا بتجاهله: فرز مجهول يُتجاهَل
#:    صامتاً **يُعيد النتيجة نفسها** فيظنّ المستخدم أن الزرّ لا يعمل.
ARCHIVE_SORTS: dict[str, str] = {
    "recent": "recent",
    "name": "name",
    "size": "size",
}


def _archive_sort(value: str) -> str:
    """
    يتحقّق من أمر الفرز — ويرفض المجهول بدل تجاهله.

    ⚠️ ويقبل صيغة key:dir مثل 
ame:asc التي تُرسلها الواجهة عند النقر على
    رأس عمود. **والاتجاه يُتحقَّق منه ولا يُطبَّق** — فدالّة SQL تطبّق اتجاهاً
    ثابتاً لكل مفتاح (الاسم تصاعدياً، والحجم والأحدث تنازلياً). فالنقر على رأس
    العمود **يرتّب به** ✅ لكن لا يقلبه.

    ⚠️ **وكان رفضُ key:dir بـ400 عطباً حقيقياً**: الواجهة تُرسلها، فيظهر خطأ
    عند النقر على أي رأس عمود. والقبول مع تجاهل الاتجاه **أسوأ** — يُظهر الزرّ
    كأنه يعمل. فأُقبل الآن، **ويُقال الحدّ صراحةً** في سطر تحت شريط الأدوات،
    ويُطبَّق الاتجاه حين تُضاف لاحقته إلى دالّة SQL.
    """
    raw = (value or "recent").strip().lower()
    key, _, direction = raw.partition(":")
    key = key or "recent"
    if key not in ARCHIVE_SORTS:
        raise HTTPException(
            status_code=400,
            detail=f"ترتيب غير معروف: {value!r} — المتاح: {sorted(ARCHIVE_SORTS)}",
        )
    if direction and direction not in ("asc", "desc"):
        raise HTTPException(
            status_code=400,
            detail=f"اتجاه غير معروف: {direction!r} — المتاح: ['asc', 'desc']",
        )
    return ARCHIVE_SORTS[key]


def _archive_storage_error(exc: Exception) -> str:
    """
    رسالة مفهومة عند غياب دوالّ الأرشيف.

    و«function does not exist» وحدها لا تدلّ على المطلوب، فنسمّي القسم الدقيق.

    ⚠️ **والقسم يختلف بحسب الدالّة**: `archive_overview` و`archive_documents`
    في القسم ١١، و`archive_chunks` في **١٢**. ولو قيل «١١» دائماً لبحث
    المستخدم في القسم الخطأ. (وهو خطأ وقع فعلاً حين أُضيفت المقاطع.)
    """
    message = str(exc)
    section = "١٢" if "archive_chunks" in message else "١١"
    if (
        "archive_overview" in message
        or "archive_documents" in message
        or "archive_chunks" in message
        or "PGRST202" in message  # PostgREST: الدالة غير موجودة في المخطّط
        or "42P01" in message     # Postgres: العلاقة غير موجودة
        or "does not exist" in message
        or "Could not find the function" in message
    ):
        return (
            f"دوالّ الأرشيف غير موجودة في قاعدة البيانات. "
            f"نفّذ القسم {section} من schema.sql في Supabase SQL Editor مرة واحدة."
        )
    return f"تعذّر قراءة الأرشيف: {message}"


# ==============================================================================
# ٤. ذاكرة المحادثة — معزولة لكل جلسة
# ==============================================================================
# النسخة السابقة استخدمت متغيّراً عامّاً واحداً لكل المستخدمين، فكانت محادثة
# عميل تتسرّب إلى محادثة عميل آخر، وتنمو بلا حد حتى تتجاوز نافذة السياق.
# هنا: قاموس محدود الحجم + اقتطاع لآخر N دور.

_sessions: "OrderedDict[str, list]" = OrderedDict()


def _get_history(session_id: str) -> list:
    """يجلب (أو ينشئ) سجل الجلسة، مع تطبيق سياسة الإخلاء LRU."""
    history = _sessions.get(session_id)
    if history is None:
        history = [SystemMessage(content=SYSTEM_PROMPT_CITED)]
        _sessions[session_id] = history
    _sessions.move_to_end(session_id)
    while len(_sessions) > MAX_SESSIONS:
        _sessions.popitem(last=False)
    return history


def _trim_history(history: list) -> list:
    """يبقي رسالة النظام + آخر MAX_HISTORY_TURNS دور محادثة."""
    return [history[0]] + history[1:][-(MAX_HISTORY_TURNS * 2):]


# ==============================================================================
# ٥. تشغيل الوكيل — منطق مشترك بين /chat و /generate
# ==============================================================================


def _extract_text(message: Any) -> str:
    """يوحّد محتوى الرسالة: نص عادي أو قائمة كتل محتوى (كما يفعل Gemini أحياناً)."""
    content = getattr(message, "content", None)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
        return "".join(parts)
    return ""


# ==============================================================================
# ٥.٠ ملف القضية — ما يُثبَت قبل الصياغة، وما يُسأل عنه
# ==============================================================================
# ⚠️ **لماذا هنا، وما العطب الذي وُجد هذا القسم لمنعه؟**
#
# البنية كانت تصوغ من **الوقائع السائبة** وحدها: نصّ يكتبه المحامي، ثم مذكرة.
# ولا يُسأل في أيّ إمارة القضية، ولا أمام أيّ جهة، ولا في أيّ مرحلة، ولا عن
# أيّ طلبات — فتُبنى المسودّة على افتراضات **لم يكتبها أحد**. والافتراض
# الصامت أخطر من الخطأ الصريح: الخطأ يُرى ولا يُسلَّم، والافتراض يمضي.
#
# و`case_file.py` بُني لذلك واختُبر — **ولم يكن يُنادى من أيّ موضع**، فلم
# يُغيّر شيئاً. وهذا القسم هو الوصل: يحوّل الحمل إلى ملف، ويبثّه، ويدخله
# الرسالة. **ولا يُعاد فيه شيء من منطق `case_file`** — لا اشتقاق مفتاح، ولا
# تعريف «ناقص»، ولا قائمة أسئلة، ولا ترتيب: كلها تُنادى من الملف. وأيُّ نسخة
# ثانية هنا **تنحرف عنه بصمت**، وهو العيب نفسه الذي أُصلح في مطابقة الجهة
# (مفتاح لاتيني قِيس على نصّ عربي فصار التقاطع فراغاً يُقرأ سلامة).

#: نصّ الصياغة عند غياب ملف القضية أصلاً.
#:
#: ⚠️ **ولا يُسكَت عن الغياب.** غياب الملف ليس «لا مشكلة» بل **«لم يُفحَص»**،
#: وهما ليسا سواءً: الأول يُبنى عليه، والثاني لا. والقاعدة في هذا المشروع
#: (`briefing.py`) أن **الفحص غير المُشغَّل ليس فحصاً ناجحاً** — فالفراغ يُقال
#: صراحةً في الرسالة وفي إطار `case`، ولا يُفهم من سكوته أن الاختصاص مضبوط.
CASE_BLOCK_ABSENT = """\
ملف القضية: **لم يُنشأ ملف قضية لهذا الطلب.**

⚠️ وغيابه **فحصٌ لم يُشغَّل، لا فحصٌ ناجح**: كل ما في المسودّة يتوقّف على
الاختصاص أو التقادم أو المرحلة الإجرائية فهو **غير متحقَّق منه**، لأنه لا
إمارة مسجَّلة ولا جهة ولا مرحلة ولا صفة. فصرّح بذلك في موضع الحاجة، ولا
تُكمل النقص من عندك."""

#: رأس كتلة القضية المُثبَتَة.
CASE_BLOCK_HEADER = "ملف القضية (الحقول المُثبَتَة قبل الصياغة):"

#: نصّ الأسئلة المفتوحة — وهو **أهمّ ما في الكتلة**.
CASE_BLOCK_QUESTIONS_HEADER = (
    "⚠️ **أسئلة لم يُجَب عنها بعد — والتي يتفرّع عليها القانون:**"
)

CASE_BLOCK_RULES = """\
⚠️ **قواعد الصياغة عليها:**
١. لا تفترض جواباً لأيّ سؤال منها — لا اختصاصاً ولا ميعاداً ولا صفةً ولا
   طلباً. والافتراض الصامت أخطر من الخطأ الصريح: الخطأ يُرى، وهذا يمضي.
٢. اصوغ الأجزاء التي **لا تتوقّف** على هذه الأسئلة ومضِ فيها؛ فالسؤال لا
   يوقف العمل، لكنه يمنع الجزم بما لا يُجزم به.
٣. حيث يمسّ سؤالٌ مفتوح جوهرَ الحكم أو الدفع أو الميعاد، فقُل في موضعه إنّ
   الأمر موقوف على بيان لم يُسجَّل — ولا تُكمل النقص من عندك."""

#: ما يُقال إن كان الملف قائماً. الترتيب هو ترتيب `BLOCKING_FIELDS` المانعة
#: عمداً، على قاعدة «الحقول المانعة أولاً» في `case_file.py`.
CASE_BLOCK_NO_QUESTIONS = (
    "لا أسئلة مفتوحة: كل حقوق الملف مُثبَتة — فصرّح بما ثبت، ولا تُضف واقعة "
    "لم تُسجَّل فيه."
)


#: الحقول التي **لا ملف بلاها** من `case_file.py`، وهي ثلاثة من ``BLOCKING_FIELDS``.
#:
#: ⚠️ **ولماذا هذه الثلاثة وحدها تُمنع من الغياب؟** لأن حقول ``CaseFile``
#: **بلا افتراضي عن قصد**، ومنها ثلاثة **غير نصّية**: ``dispute_type``
#: و``stage`` و``our_party`` أعضاء تصنيفات مغلقة. أما ``emirate`` و``forum``
#: و``claims`` فنصّها الفارغ هو «لم يُسجَّل» **في الملف نفسه** (``missing()``).
#: فحملٌ لا يحمل هذه الثلاثة **لا يُبنى منه ملف**، ولا تُخترع له قيمة —
#: والقيمة المخترعة هنا هي عين **الافتراض الصامت** الذي وُجد الملف لمنعه.
#:
#: ⚠️ **والترتيب هو ترتيب ``BLOCKING_FIELDS``** لا ترتيب نكتبه هنا، ولا
#: ترتيب الدارج في تلك القائمة: ``our_party`` يتقدّم ``stage`` لأن ترتيب
#: الملف هكذا — فلا يُفرز الناتج فرزاً ثانياً.
CASE_SHAPE_FIELDS: tuple[str, ...] = tuple(
    name
    for name in case_file_module.BLOCKING_FIELDS
    if name in ("dispute_type", "stage", "our_party")
)

#: ما يُقال حين يصل حملٌ لا يكفي لبناء ملف — **ولا يُسكَت عن حقوله.**
#:
#: ⚠️ **وهذا ليس رفضاً للطلب** (لا يُردّ ٤٠٠ ولا يوقف التوليد)، بل **إعلان**
#: أنّ ما أُرسل لم يُبنَ منه ملف. والفرق جوهري: حملٌ يُتجاهَل صامتاً **أسوأ من
#: حملٍ غائب**، لأن المستدعي يظنّ أن قيمته مرّت فتُبنى المسودّة على غير ما طلب.
CASE_BLOCK_UNBUILDABLE = (
    "⚠️ **وصل حمل ملف قضية، لكنه لم يكفِ لبناء ملف**: الحقول اللازمة لبنائه "
    "لم تُرسَل ({fields})، وحقول ``CaseFile`` بلا قيمة افتراضية عن قصد — "
    "فلا قيمة تُخترع لها. فاعتبر ملف القضية **غير منشأ**، وكل ما يتوقّف على "
    "الاختصاص أو التقادم أو المرحلة الإجرائية **غير متحقَّق منه**، ولا "
    "تُكمل النقص من عندك."
)


def _payload_case_value(payload: object, name: str) -> object:
    """
    يقرأ حقل ملف القضية من الحمل، أو ``None`` إن لم يُرسَل.

    ⚠️ **الغياب يُعاد ``None`` ولا يُمنح قيمة مفترضة**: الحقل بلا افتراضي في
    ``CaseFile`` عن قصد، فيجب أن يبقى الغائب غائباً حتى يُسأل عنه.
    """
    return getattr(payload, name, None)


def _case_enum(raw: object, enum_class, label: str):
    """
    يحوّل قيمة آلية إلى عضو التصنيف، **ويرفض المجهول باسم القيم المتاحة**.

    ⚠️ ولماذا لا يُمرَّر النصّ إلى `CaseFile` كما هو؟ لأن التصنيفات **مغلقة**
    في الملف: `dispute_type` و`stage` و`our_party` أعضاء `Enum` لا نصوص. فلو
    مرّ نصّ مجهول لَما صار خطأً ظاهراً بل قيمةً لا تُطابق شيئاً في الجدول —
    **فيسأل الملف عن نقص لا وجود له**، أو أسوأ: يقبل نوعاً لم يُقصد.

    ⚠️ **والرفض ٤٠٠ لا ٥٠٠**: الطلب نفسه غير صالح، لا الخادم. والأسوأ من
    الاثنين أن يُبتلع الخطأ: **حملٌ يُتجاهَل صامتاً أسوأ من حملٍ غائب**، لأن
    المستدعي يظنّ أنه مرّ فتُبنى المسودّة على غير ما طلب.
    """
    if raw is None:
        return None
    if isinstance(raw, enum_class):
        return raw
    if isinstance(raw, str):
        try:
            return enum_class(raw.strip())
        except ValueError:
            pass
    raise HTTPException(
        status_code=400,
        detail=(
            f"{label} غير معروف: {raw!r} — المتاح: "
            f"{[member.value for member in enum_class]}"
        ),
    )


def _case_text_list(raw: object, label: str) -> tuple[str, ...]:
    """
    يحوّل قائمةً نصّية: الطلبات، أو القانون المرجَّح.

    ⚠️ **والعنصر الواحد يُبقي قائمةً** ولا يُدمج في نصّ: الطلب وحدةُ حكمٍ
    ومطالبةٍ ودفع، فالدمج يُفقد القدرة على تتبّع أيّ طلبٍ أُجيب وأيّها أُغفل.
    """
    if raw is None:
        return ()
    if isinstance(raw, (str, bytes)) or not isinstance(raw, (list, tuple)):
        raise HTTPException(
            status_code=400,
            detail=f"{label} يجب أن تكون قائمة، ووصل: {type(raw).__name__}",
        )
    return tuple(str(item).strip() for item in raw if str(item).strip())


def _case_key_dates(raw: object) -> tuple[tuple[str, str], ...]:
    """
    يحوّل التواريخ إلى أزواج (الوصف، التاريخ) — **بلا تحويلٍ للتاريخ**.

    ⚠️ والتاريخ يبقى **نصّاً** كما ورد، على قاعدة `labour_rules.py`: العدّ في
    موضع واحد ويجري على ``date`` بعد تحقّق. فالتواريخ تصل هجريةً وميلاديةً
    ومنقولةً بالعربية، وتحويلها هنا يعني **تقريباً صامتاً** في الحقل الذي يقوم
    عليه عدّ المدّة — وقد وقع فعلاً: ١٢٧٨ يوماً والصحيح ١٣٠٧.
    """
    if raw is None:
        return ()
    if isinstance(raw, dict):
        pairs = list(raw.items())
    elif isinstance(raw, (list, tuple)):
        pairs = list(raw)
    else:
        raise HTTPException(
            status_code=400,
            detail=(
                "key_dates يجب أن تكون قائمة أزواج [الوصف, التاريخ]، "
                f"ووصل: {type(raw).__name__}"
            ),
        )

    dates: list[tuple[str, str]] = []
    for item in pairs:
        if isinstance(item, (list, tuple)) and len(item) == 2:
            label, value = item
        else:
            raise HTTPException(
                status_code=400,
                detail=(
                    "كل تاريخ يجب أن يكون زوجاً [الوصف, التاريخ]، ووصل: "
                    f"{item!r}"
                ),
            )
        dates.append((str(label), str(value)))
    return tuple(dates)


@dataclass(frozen=True)
class _CaseInput:
    """
    ما وصل من حمل ملف القضية بعد التحقّق: الملف — أو سببُ تعذّر بنائه.

    ⚠️ **وهذا الصنف وُجد لعطبٍ صامت، فاقرأه قبل أن تُبسّطه.** حقول
    ``CaseFile`` **بلا افتراضي عن قصد**، ومنها ثلاثة **غير نصّية**
    (``dispute_type`` و``stage`` و``our_party``). فحملٌ يرسل الإمارة ويُسقط
    نوع النزاع **لا يُبنى منه ملف** — ولو بنيناه بقيمة مخترعة لكان ذلك
    الافتراض الصامت بعينه؛ ولو أسقطناه صامتاً لَظنّ المستدعي أن إمارته مرّت
    **وهي لم تمرّ**. فالحالتان مرفوضتان، والثالثة هي هذه: **يُقال ما وصل وما
    لم يصل**، ويُبثّ الإطار، **ويمضي التوليد** — فلا يُوقف نقصٌ العمل، ولا
    يُسكَت عنه.

    Attributes:
        requested: هل أُرسل حمل أصلاً؟ (وهو ما يفرّق «لم يُنشأ ملف» عن «وصل
            حمل لا يكفي» — والاثنان يُقالان، لكن لا يُقالان بعبارة واحدة).
        case: الملف المبني، أو ``None`` إن لم يكفِ الحمل لبنائه.
        unbuildable: أسماء الحقول التي منعت البناء — **من ``BLOCKING_FIELDS``
            بترتيبها**، فلا يُكتب ترتيب ثانٍ.
    """

    requested: bool
    case: Optional[CaseFile]
    unbuildable: tuple[str, ...] = ()

    def absent(self) -> bool:
        """هل لم يُرسل حمل، أو أُرسل ولم يُبنَ منه ملف؟ — الحالتان تُقالان."""
        return self.case is None


def _case_from_payload(payload: object) -> _CaseInput:
    """
    يحوّل حمل النقل إلى `CaseFile` — أو يُعلن ما منع بنائه.

    ⚠️ **والبناء مرة واحدة، قبل أن يجري الوكيل** — لا داخل البثّ: فالحمل
    الفاسد يجب أن يُردّ **قبل أن يُستدعى نموذج واحد**، وإلا كان ٤٠٠ بعد أن
    دُفع ثمن التوليد. وهذا فحص `test_an_invalid_case_never_starts_generation`.

    ⚠️ **ورسالة الملف تبقى رسالة الملف.** `CaseFile.__post_init__` يرفع
    ``ValueError`` على نصّ إمارة لا مفتاح له في ``EMIRATE_ALIASES`` — وهي
    الرسالة التي تسمّي الموضع الذي تُضاف فيه الصورة. ولو ترجمناها إلى نصّ من
    عندنا لضاع اسم الجدول، **وصار الإصلاح تخميناً**. فتُنقل كما هي، ويتغيّر
    رمز الحالة وحده: ٤٠٠ لا ٥٠٠ — لأن العطب في الطلب لا في الخادم.

    ⚠️ **والقيَم تُترجم هنا مرة واحدة**: التصنيفات تُرفض إن كانت مجهولة
    (`_case_enum`)، والقوائم تُفحَص، والتواريخ تبقى **نصّاً** كما وردت.
    """
    if payload is None:
        return _CaseInput(requested=False, case=None)

    # ⚠️ الحقول تُقرأ مرة واحدة هنا، فلا يُقرأ الحمل مرتين بمعنيين مختلفين.
    raw: dict[str, object] = {
        name: _payload_case_value(payload, name)
        for name in (
            "country",
            "emirate",
            "forum",
            "dispute_type",
            "stage",
            "our_party",
            "claims",
            "key_dates",
            "likely_law",
            "has_arbitration_clause",
            "has_choice_of_law",
        )
    }

    # ⚠️ والتصنيفات تُتحقَّق **قبل** فحص الشكل: قيمة مجهولة تُردّ ٤٠٠ برسالتها
    # (وهي صريحة)، ولا تُبتلع في «حمل لا يكفي» فيقرأ المستدعي سبباً غير سببه.
    dispute_type = _case_enum(raw["dispute_type"], DisputeType, "نوع النزاع")
    stage = _case_enum(raw["stage"], CaseStage, "المرحلة")
    our_party = _case_enum(raw["our_party"], Party, "الصفة")

    # ⚠️ **ولا قيمة تُخترع**: بلا هذه الثلاثة لا ملف. والقوائم تُفحَص هنا
    # أيضاً فيُردّ المشوّه منها ٤٠٠ ولو لم يُبنَ الملف — فالحمل الفاسد فاسد.
    claims = _case_text_list(raw["claims"], "الطلبات")
    key_dates = _case_key_dates(raw["key_dates"])
    likely_law = _case_text_list(raw["likely_law"], "القانون المرجَّح")

    try:
        case = CaseFile(
            country=str(raw["country"] or ""),
            emirate=str(raw["emirate"] or ""),
            forum=str(raw["forum"] or ""),
            # ⚠️ والحقول الثلاثة تُملأ هنا بقيمة **معلَنة** حين تغيب، لا
            # لتُستعمل: ``CaseFile`` يفحص الإمارة في ``__post_init__`` وحدها،
            # فيجب أن يمرّ البناء ليُفحَص نصّ الإمارة. والحمل الذي لا يكفي
            # **لا يُعاد منه ملف** (انظر أسفل) — فالقيمة لا تصل إلى مستدعٍ.
            dispute_type=dispute_type or DisputeType.CIVIL,
            stage=stage or CaseStage.FIRST_INSTANCE,
            our_party=our_party or Party.CLAIMANT,
            claims=claims,
            key_dates=key_dates,
            likely_law=likely_law,
            has_arbitration_clause=raw["has_arbitration_clause"],
            has_choice_of_law=raw["has_choice_of_law"],
        )
    except ValueError as exc:
        # رسالة `case_file` بنصّها — انظر أعلاه لماذا لا تُترجم.
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    shape = {
        "dispute_type": dispute_type,
        "stage": stage,
        "our_party": our_party,
    }
    unbuildable = tuple(name for name in CASE_SHAPE_FIELDS if shape[name] is None)
    if unbuildable:
        # ⚠️ **ولا يُعاد الملف**: القيم المعلَنة أعلاه لم تكن إلا لتمرّ رسالة
        # الإمارة من الفحص. وحملٌ بلا نوع نزاع **لا يُبنى منه ملف بقيمة
        # مخترعة** — بل يُقال ما نقص، ويمضي التوليد، ويُسأل المحامي.
        return _CaseInput(requested=True, case=None, unbuildable=unbuildable)

    return _CaseInput(requested=True, case=case)


def _case_absent_message(case_input: _CaseInput) -> str:
    """
    نصّ «لا ملف» — **بعبارتين لا بعبارة واحدة**.

    ⚠️ **والفرق مقصود:** «لم يُرسل حمل» حالةٌ، و«أُرسل حمل ولم يُبنَ منه ملف»
    حالةٌ أخرى **أخطر**: المستدعي أرسل قيماً يظنّها مرّت. فلو قيلت العبارة
    الأولى في الثانية لَقُرأ حملُه مُهمَلاً وهو كذلك فعلاً — لكن بلا أن يعرف
    سبباً، فيُعيد الكرّة بالخطأ نفسه.
    """
    if not case_input.requested:
        return CASE_BLOCK_ABSENT
    return CASE_BLOCK_UNBUILDABLE.format(
        fields="، ".join(case_input.unbuildable)
    )


def _case_frame(case_input: _CaseInput) -> dict:
    """
    إطار `case` كما يُبثّ — **بقيم الوحدة وحدها، بلا إعادة حساب**.

    والأسئلة **لا تُفرز هنا**: ترتيبها هو ترتيب ``QUESTIONS`` في `case_file.py`
    (المانع أولاً)، وهو **مصدر الترتيب الوحيد**. ولو فُرزت على `BLOCKING_FIELDS`
    هنا لصار للترتيب مصدران يفترقان عند أول تعديل — وهو التعليل نفسه المكتوب
    في ``questions_for``.

    ⚠️ **والأسئلة أسئلة النقص وحدها، ولا تُخترع لحقل لم يُسجَّل**: سؤال مخترع
    يُجاب، وجوابُ سؤالٍ لم يُقصد يُكتب في المسودّة فيصير **افتراضاً صامتاً**.

    ⚠️ **والغياب لا يُسكَت عنه**: بلا ملف تُبثّ إطارات ولا ``questions`` —
    والواجهة تقرأ ``established: False`` فتعرف أن الفحص **لم يُشغَّل**، لا أنه
    نجا. و«لم يُفحص» و«فُحص فسلم» ليسا سواءً، وهذا الفرق هو كل الفائدة.
    """
    case = case_input.case
    if case is None:
        return {
            "established": False,
            "requested": case_input.requested,
            "message": _case_absent_message(case_input),
            "case": None,
            "confirmed": [],
            "missing": [],
            "is_complete": False,
            "questions": [],
            "regime_notes": [],
            "summary": None,
        }

    # ⚠️ والأسئلة **صنفان لا صنف**: أسئلة حقول الملف الناقصة، وأسئلة الجدول
    # التي **لم يُنظر فيها بعد** (``None``) — لا التي أُجيب عنها بنفي. والخلط
    # بينهما يجعل السؤال يُطرح على من أجاب فيُهمَل، ثم يُهمَل معه السؤال
    # الحقيقي حين يظهر. والملف نفسه هو الذي يفرّق (`open_regime_questions`).
    questions = tuple(case.questions_for_missing()) + tuple(
        case.open_regime_questions()
    )
    summary = case.summary()
    # ⚠️ والوسم من الملف نفسه (`blocking_missing` المحسوب في `summary`)، لا من
    # إعادة تعريف عندنا: حقلٌ مانع يُحسب في موضعين يفترقان عند أول تعديل.
    blocking = set(summary["blocking_missing"])

    return {
        "established": True,
        "requested": True,
        "message": "",
        "case": summary,
        "confirmed": list(case.confirmed()),
        "missing": list(case.missing()),
        "is_complete": case.is_complete(),
        "questions": [
            {
                "field": question.field,
                "question": question.question,
                "why": question.why,
                "blocking": question.field in blocking,
            }
            for question in questions
        ],
        "regime_notes": case_file_module.notes_summary(
            case_file_module.regime_notes(case)
        ),
        "summary": summary,
    }


def _case_facts_block(case: CaseFile) -> str:
    """
    الوقائع المُثبَتَة في صورة تُقرأ — **بلا آلية داخليّة**.

    ⚠️ ولا يُعرَض ``emirate_key`` ولا ``forum_key`` ولا ``blocking_missing``:
    مفاتيح لمطابقة الجدول لا لواقعة، وعرضُها في نصّ الصياغة يُقحم مصطلحات لم
    يكتبها المحامي. وهي **باقية في إطار `case` للواجهة** — كل مخرَج في موضعه.
    """
    parts: list[str] = []
    if case.country.strip():
        parts.append(f"الدولة: {case.country}")
    if case.emirate.strip():
        parts.append(f"الإمارة: {case.emirate}")
    if case.forum.strip():
        parts.append(f"الجهة: {case.forum}")
    parts.append(f"نوع النزاع: {case.dispute_type.value}")
    parts.append(f"المرحلة: {case.stage.value}")
    parts.append(f"صفتنا: {case.our_party.value}")
    if case.claims:
        parts.append("الطلبات: " + "؛ ".join(case.claims))
    if case.key_dates:
        parts.append(
            "التواريخ: "
            + "؛ ".join(f"{label}: {value}" for label, value in case.key_dates)
        )
    if case.likely_law:
        parts.append("القانون المرجَّح: " + "؛ ".join(case.likely_law))
    # ⚠️ ``False`` تُقال و``None`` تُسكت: من قال «لا شرط تحكيم» فقد أجاب
    # فيُكتب جوابه، ومن لم يُنظر يُبقى سؤالاً في القسم الذي تحته.
    if case.has_arbitration_clause is not None:
        parts.append(
            "شرط التحكيم في العقد: "
            + ("نعم" if case.has_arbitration_clause else "لا")
        )
    if case.has_choice_of_law is not None:
        parts.append(
            "اتّفاق على قانون مختار: "
            + ("نعم" if case.has_choice_of_law else "لا")
        )
    return "\n".join(f"- {part}" for part in parts)


def _case_prompt_block(case_input: Optional[_CaseInput]) -> str:
    """
    كتلة ملف القضية في الرسالة — **الأسئلة المفتوحة أهمّ ما فيها**.

    ⚠️ **ولماذا تُبنى دائماً، ولا تُحذف عند غياب الملف؟** لأن حذفها **يُقرأ
    موافقةً صامتة**: النموذج يكتب عن الاختصاص والتقادم بلا تنبيه أن أحداً لم
    يُسأل عنهما. فالغياب نفسه معلومة تُقال (`CASE_BLOCK_ABSENT`) — وهذا هو
    الأصل الذي يقوم عليه `briefing.py`: **الفحص غير المُشغَّل ليس فحصاً ناجحاً.**

    ⚠️ **وحملٌ لا يكفي لبناء ملف يُقال فيه إنه لا يكفي**، ولا تُبنى له كتلة
    وقائع — فبناء كتلة من حملٍ نصفه غائب يُنتج مسودّة تُقرأ تامة وهي مبنية
    على نصف استمارة.

    ⚠️ **والأسئلة تُكتب بـ``why`` معها**: سؤال بلا سبب يُقرأ استيفاءً لشكليات،
    وبسببه يُقرأ توقّياً لعيب — وهو التعليل المكتوب في ``Question`` نفسها.
    """
    if case_input is None or case_input.case is None:
        return _case_absent_message(case_input or _CaseInput(requested=False, case=None))

    case = case_input.case
    # ⚠️ والأسئلة **صنفان لا صنف**: أسئلة حقول الملف الناقصة، وأسئلة الجدول
    # التي **لم يُنظر فيها بعد** (``None``) — لا التي أُجيب عنها بنفي. والخلط
    # بينهما يجعل السؤال يُطرح على من أجاب فيُهمَل، ثم يُهمَل معه السؤال
    # الحقيقي حين يظهر. والملف نفسه هو الذي يفرّق (`open_regime_questions`).
    questions = tuple(case.questions_for_missing()) + tuple(
        case.open_regime_questions()
    )
    lines = [CASE_BLOCK_HEADER, _case_facts_block(case)]
    if questions:
        lines.append(CASE_BLOCK_QUESTIONS_HEADER)
        lines.extend(
            f"- [{question.field}] {question.question}\n  لماذا: {question.why}"
            for question in questions
        )
        lines.append(CASE_BLOCK_RULES)
    else:
        lines.append(CASE_BLOCK_NO_QUESTIONS)
    return "\n".join(lines)


def _build_messages(
    prompt: str,
    doc_type: Optional[str] = None,
    case_input: Optional[_CaseInput] = None,
) -> list:
    """
    يبني الرسائل، مع حقن نوع المستند وتلميح الأداة، **وقضية الملف**.

    ⚠️ و``case_input=None`` **لا تعني حذف الكتلة**، بل كتلة تقول إن الملف لم
    يُنشأ — انظر `_case_prompt_block`.
    """
    user_content = prompt
    if doc_type:
        hint = DOC_TYPE_TOOL_HINT.get(doc_type.strip())
        hint_line = f"\n(الأداة الأنسب لهذا النوع: {hint})" if hint else ""
        user_content = (
            f"نوع المستند المطلوب: {doc_type}{hint_line}\n\n"
            f"الوقائع والمعطيات:\n{prompt}"
        )
    user_content = f"{user_content}\n\n{_case_prompt_block(case_input)}"
    return [SystemMessage(content=SYSTEM_PROMPT_CITED), HumanMessage(content=user_content)]


def _verify_round(final_text: str, evidence: list) -> tuple[str, dict]:
    """
    يحكم على استشهادات الجولة، ويُرجع (المستند النظيف, تقرير الأسانيد).

    المستند النظيف = المتن بلا كتلة الأسانيد، فهو ما يُعرض ويُنسخ إلى Word.
    والتقرير يُبثّ للواجهة ليرى المحامي ما ثبت وما رُفض — بالتفصيل لا بالعدد.
    """
    parsed = parse_citations(final_text)
    outcome = verify_citations(parsed.citations, evidence)
    clean = strip_citations_block(final_text)
    unbacked = unbacked_article_refs(clean, evidence)

    report = {
        "summary": outcome.summary(),
        "has_evidence": outcome.has_evidence,
        "evidence_count": len(evidence),
        "has_citation_block": parsed.has_block,
        "verified": [
            {
                "ref": item.ref,
                "document_name": item.document_name,
                "chunk_id": item.chunk_id,
                "quoted_span": item.quoted_span,
                "similarity": item.similarity,
            }
            for item in outcome.verified
        ],
        "rejected": [
            {
                "ref": item.ref,
                "quoted_span": item.quoted_span,
                "reason": item.reason,
            }
            for item in outcome.rejected
        ],
        # مواد ذُكرت في المتن ولم ترد في أي مقطع مسترجَع — بلا سند.
        "unbacked_articles": [
            {"surface": ref.surface, "number": ref.number} for ref in unbacked
        ],
        # أسطر أسانيد لم تُقرأ: سند ضائع، ويُعرَض للتشخيص لا يُسقَط.
        "malformed_lines": parsed.malformed,
        # ⚠️ **وهذا فحصٌ ثالث لا يقيسه `verify_citations` ولا `unbacked_article_refs`.**
        #
        # الأول يسأل: هل النصّ المقتبس موجود في المقاطع؟ والثاني: هل المادة
        # مذكورة في المقاطع أصلاً؟ **ولا واحد منهما يسأل: هل هذا النصّ هو نصّ
        # المادة التي نُسب إليها؟**
        #
        # وقد وقع ذلك فعلاً: مذكرة قالت «المادة ٤٣/٢ تنصّ على…» ونقلت عبارة
        # تعود إلى عقد محدد المدة، والمادة الحالية لا تحملها. **فمرّ الاقتباس
        # من كل فحوصنا سالماً وهو ينسب إلى القانون ما ليس منه** — وقد قالها
        # المُقيِّم بجملة تُثبَّت: **«إسناد صياغة غير صحيحة إلى مادة أخطر من عدم
        # ذكر المادة أصلاً».**
        #
        # ⚠️ و`mismatched` خطأ و`absent` ملاحظة، والفرق مقصود: الأول **قولٌ
        # خاطئ عن القانون**، والثاني **ثغرةٌ في الأرشيف** — ولا يُعاقَب المحامي
        # على ما لم يُنتجه الاسترجاع.
        "attribution": summarize_attribution(
            verify_attributions(clean, evidence, lambda row: getattr(row, "text", "") or "")
        ),
    }
    return clean, report


# ==============================================================================
# ٥.١ سجلّ الوقائع والتقرير الداخلي — ما يُبنى **بعد** وجود المسودّة
# ==============================================================================
# ⚠️ **لماذا هنا، وما العطب الذي وُجد هذا القسم لمنعه؟**
#
# `facts.py` بُني ليمنع عيباً تكرّر في **ثلاث مسودّات متعاقبة**: واقعةٌ غُيِّرت،
# فانقلب مَن عليه الخطأ — «رفض التوقيع على مخالصة متضمّنة تنازلاً» صارت «رفض
# استلام المبلغ». و`briefing.py` بُني ليُخرج تقرير المحامي **مفصولاً عن المذكرة**.
# والاثنان كانا مبنيَّين ومختبرَين **ولا يُناديان من أيّ موضع** — فكانا يوجدان
# ولا يُغيّران شيئاً، كحال `case_file.py` قبلهما. وهذا القسم هو الوصل.
#
# ⚠️ **ولا يُعاد هنا شيء من منطق الوحدة**: لا حساب افتراق، ولا درجة سلامة، ولا
# بناء مجموعات التقرير — كلُّ ذلك يُنادى من `check_fidelity` و`summarize` و`build`.
# ونسخةٌ ثانية هنا **تنحرف عن الوحدة بصمت**، وهو العيب نفسه في صورة أخرى.
#
# ⚠️ **والسجلّ يُبنى قبل الوكيل ويُفحَص بعده**: بناءُ السجلّ من الحمل يجب أن
# يسبق استدعاء النموذج (فحملُه الفاسد يُردّ ٤٠٠ **قبل** أن يُدفع ثمن التوليد)،
# أما **الفحص** فلا معنى له قبل أن تُكتب المسودّة — فلا شيء يُقابَل بالسجلّ.

#: نصّ «لم يُشغَّل فحص الوقائع» — **وهو أهمّ سطر في هذا القسم**.
#:
#: ⚠️ **ولا يُحذف إطار `facts` عند غياب السجلّ.** حذفُه يُقرأ سكوتاً، والسكوت في
#: موضع فحصٍ يُقرأ سلامة — وهو الخلط نفسه الذي وُلد `briefing.py` لمنعه:
#: **الفحص الذي لم يُشغَّل ليس فحصاً نجح.** فلا يُقال «لا افتراق» عمّا لم يُقابَل
#: بشيء، لأن الواقعة المُغيَّرة **لا يكشفها** فحص الأسانيد ولا التدقيق اللغوي ولا
#: المراجعة الثانية: كلها تقرأ المسودّة في نفسها ولا تقابلها بسجلّ.
FACTS_NOT_RUN = (
    "لم يُجرِ فحص أمانة الوقائع: لم يُرسل سجلّ وقائع مع الطلب، فلا شيء قابَل "
    "المسودّة. ⚠️ وغيابه **فحصٌ لم يُشغَّل، لا فحصٌ ناجح**: واقعةٌ غُيِّرت في "
    "المسودّة — وهي العيب الذي تكرّر ثلاث مرّات — لا يكشفها فحصُ الأسانيد ولا "
    "التدقيق اللغوي ولا المراجعة."
)

#: ما يُقال عند غياب درجة الواقعة.
#:
#: ⚠️ **ولا تُفترض درجة**: الدرجة هي **وزن الواقعة في المذكرة** (انظر
#: `Standing`)، فافتراضها يُنشئ من عندنا حكماً لم يكتبه أحد — وهو **الافتراض
#: الصامت** بعينه. ولو مُرّرت ``None`` إلى الوحدة لانكسر ``by_standing`` عند
#: أوّل عرض، فالرفض هنا **إعلانٌ لموضع الإصلاح** لا عقوبة.
FACT_STANDING_MISSING = (
    "درجة الواقعة غير مسجَّلة: كل واقعة تُسجَّل بدرجتها — ولا تُفترض لها درجة."
)


def _fact_field(item: object, name: str) -> object:
    """
    يقرأ حقل واقعة من الحمل — كائن نقلٍ كان أو قاموساً، أو ``None`` إن غاب.

    ⚠️ **والغياب يُعاد ``None`` ولا يُمنح قيمة مفترضة**: الوحدة هي التي ترفض
    الواقعة بلا مفتاح أو بلا نصّ **برسالته هو**، فلا نُكرّر شرطه هنا.
    """
    if isinstance(item, dict):
        return item.get(name)
    return getattr(item, name, None)


def _fact_text(item: object, name: str) -> str:
    """حقل واقعة نصّاً — والغائب فراغ، ولا يُخترع له نصّ."""
    value = _fact_field(item, name)
    return str(value).strip() if value is not None else ""


def _fact_standing(raw: object) -> Standing:
    """
    درجة الواقعة — **ورسالة الوحدة تُنقل كما هي مع القيم المتاحة**.

    ⚠️ **ولا تُترجم الرسالة**: `Standing` ترفع ``ValueError`` بنصّها، وهي
    الرسالة التي تسمّي القيمة المرفوضة. وتُضاف إليها **القيم المتاحة من
    التصنيف نفسه** — لا من قائمة نكتبها هنا، فقائمةٌ ثانية تفترق عن التصنيف
    عند أوّل إضافة درجة، فيصير الإصلاح تخميناً.
    """
    accepted = [member.value for member in Standing]
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        raise HTTPException(
            status_code=400,
            detail=f"{FACT_STANDING_MISSING} المتاح: {accepted}",
        )
    try:
        return Standing(str(raw).strip())
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"درجة الواقعة: {exc} — المتاح: {accepted}",
        ) from exc


def _facts_from_payload(payload: object) -> Optional[FactLedger]:
    """
    يحوّل حمل الوقائع إلى `FactLedger` — أو يردّه ٤٠٠ **برسالة الوحدة**.

    ⚠️ **والبناء مرة واحدة، قبل بناء الرسائل وقبل الخيط** — كما في ملف القضية:
    فحملٌ يرفضه `FactLedger` يجب أن يُردّ **قبل أن يُستدعى نموذج واحد**، وإلا
    كان الـ٤٠٠ بعد أن دُفع ثمن التوليد. وهذا فحص
    ``test_a_malformed_ledger_never_starts_generation``.

    ⚠️ **وسجلٌّ فاسد يُتجاهَل صامتاً أسوأ من سجلٍّ غائب**: المستدعي يظنّ أنّ
    وقائعه قُوبلت، فتُبنى المسودّة على غير ما أرسل — وهو العيب الذي جاء
    `facts.py` لمنعه. فلا تُبتلع رسالة الوحدة، ويتغيّر رمز الحالة وحده: ٤٠٠ لا
    ٥٠٠ — لأن العطب في الطلب لا في الخادم.

    ⚠️ **و``None`` تعني «لم يُرسل سجلّ»** فتُبثّ في إطار `facts` صريحةً. أما
    ``[]`` فسجلٌّ فارغ **يُبنى ويُفحَص**، ويقول ملخّصه ``fact_count: 0`` — فما
    أُعلن فراغه ليس غائباً.
    """
    if payload is None:
        return None

    if isinstance(payload, (str, bytes)) or not isinstance(payload, (list, tuple)):
        raise HTTPException(
            status_code=400,
            detail=(
                "الوقائع يجب أن تكون قائمة وقائع، ووصل: "
                f"{type(payload).__name__}"
            ),
        )

    built: list[Fact] = []
    for item in payload:
        built.append(
            Fact(
                key=_fact_text(item, "key"),
                statement=_fact_text(item, "statement"),
                source=_fact_text(item, "source"),
                locus=_fact_text(item, "locus"),
                date=_fact_text(item, "date"),
                asserted_by=_fact_text(item, "asserted_by"),
                standing=_fact_standing(_fact_field(item, "standing")),
                quote=_fact_text(item, "quote"),
            )
        )

    # ⚠️ **والحارس يُنادى قبل بناء السجلّ، وأخطرُ ما في الحمل يُقال أولاً.**
    # واقعة `AGREED` وصلت من هذا المسار تعني أنّ **المنظومة أنشأت «متفقاً عليه»**
    # — وهي الحالة التي ترفع فيها الوحدة استثناءً لا تحذيراً، لأن التحذير يُطبع
    # وتمضي الواقعة المصنوعة إلى المذكرة. فتُنقل رسالتها (وفيها القاعدة) ويُردّ
    # الطلب ٤٠٠، ولا تُرقّى درجةٌ ولا تُنزل.
    try:
        assert_system_does_not_agree(tuple(built))
    except SystemOverclaimError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        return FactLedger(tuple(built))
    except ValueError as exc:
        # ⚠️ رسالة `FactLedger` بنصّها: مفتاح مكرّر، أو واقعة بلا مفتاح أو بلا
        # نصّ. وهي الرسالة التي تسمّي الموضع، فلا تُترجم إلى نصّ من عندنا.
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _facts_frame(draft: str, ledger: Optional[FactLedger]) -> dict:
    """
    إطار `facts`: نتيجة فحص الأمانة على المسودّة، أو إعلان أنّه لم يُشغَّل.

    ⚠️ **و`check_fidelity` حتميّة وبلا نموذج وبلا شبكة وبلا قرص** (انظر صدر
    `facts.py`)، فيُشغَّل **دائماً** متى وُجد سجلّ: لا يُترك لخيار، ولا يُعلَّق
    على توفيق نداء. وهذا شرط لا تحسين — **الضمانة التي تحتاج نداءً لا تُختبر،
    وما لا يُختبر لا يُعوَّل عليه**، وقد دفع المشروع ثمن ذلك ثلاث مرّات.

    ⚠️ **ولا تُنادى على مسودّة غير موجودة**: `_stream_agent` لا يبني هذا الإطار
    في مسار «لا نصّ»، لأن كلّ واقعة كانت ستُوسم ``missing`` — لا لأنها سقطت من
    مسودّة، بل لأنه لا مسودّة. والوسم حينها كذبٌ لا إنذار.

    ⚠️ **والافتراقات تُصعَّد مع الملخّص**: ``shifts`` موجودة داخل ``summarize``
    **وهي هنا أيضاً** لأن الواجهة تحتاج الافتراق وحده ولا تحتاج سجلّ الوقائع
    كلّه — والاعتماد على مفتاح متداخل يُشيع القراءة الخاطئة حين يتغيّر الشكل.
    """
    if ledger is None:
        return {
            "ran": False,
            "message": FACTS_NOT_RUN,
            "ledger": None,
            "shifts": [],
        }

    shifts = check_fidelity(draft, ledger)
    payload = summarize_facts(ledger, shifts)
    return {
        "ran": True,
        "message": "",
        # ⚠️ مخرَج الوحدة كما هو — **ونفسه يُمرَّر إلى التقرير الداخلي** (فيه
        # ``summary`` و``fact_count`` و``shifts``)، فلا نسخة ثانية للسجلّ.
        "ledger": payload,
        "shifts": payload["shifts"],
    }


def _case_open_questions(case_frame: Optional[dict]) -> tuple[str, ...]:
    """
    أسئلة ملف القضية المفتوحة — **بنصّ الوحدة، وبترتيبها، وبلا إعادة صياغة**.

    ⚠️ **ولماذا تُمرَّر إلى التقرير الداخلي؟** لأن `readiness` تعتبر السؤال
    المفتوح مانعاً للدرجة العليا، فلو لم تُمرَّر لقال التقرير في نعته العلوي
    **«ولم يبقَ سؤال مفتوح»** وإطار `case` فوقه يعرض ثلاثة أسئلة لم تُجب. وهذا
    **طمأنة كاذبة** من الصنف الذي وُلدت هذه الوحدة لمنعه.
    """
    if not case_frame:
        return ()
    questions: list[str] = []
    for question in case_frame.get("questions") or ():
        text = str((question or {}).get("question", "")).strip()
        if text:
            questions.append(text)
    return tuple(questions)


def _briefing_frame(
    reports: Mapping[str, Any],
    open_questions: Sequence[str] = (),
) -> dict:
    """
    إطار `briefing`: التقرير الداخلي — بقاموسه **ونصّه** معاً.

    ⚠️ **ولا يُحسب هنا رقم، ولا يُفسَّر شيء**: `briefing.build` تُنادى بملخّصات
    الفحوص **كما أُبلغت**، وهي وحدها تعرف أن الغائب ثغرةٌ بمستوى خطأ، وأن
    ``failed: True`` معه ``clean: True`` **ليست نظافة**. ولو جمعنا هنا ملخّصاً
    «نظيفاً» عن فحص لم يجرِ، أو قدّمنا ``clean`` على ``failed``، لَعاد العيب
    الذي وُلد الملف لمنعه — وهو العيب الذي وقع فعلاً في `review-panel.tsx`.

    ⚠️ **ونصّ التقرير يُرسل مع قاموسه** لأن الواجهة لا يجوز أن تُعيد بناءه:
    نصٌّ ثانٍ في جافاسكربت ينحرف عن `to_markdown` عند أوّل تعديل، وهو الانحراف
    الصامت نفسه الذي أُصلح في الأدوات الخمس.

    ⚠️ **ولا طابع زمني يُمرَّر**، وهذا مقصود: `build` لا تقرأ الساعة بنفسها
    (لتكون دالّةً نقيّة تعطي المدخل نفسه المخرج نفسه)، وقراءتُها هنا تجعل
    تشغيلين بالمدخل نفسه يفترقان — والاختبار الذي لا يُعاد فيه إنتاج الناتج
    لا يشهد على شيء.
    """
    report = briefing.build(reports, open_questions=open_questions)
    return {"report": report.to_dict(), "markdown": report.to_markdown()}


#: نصّ إطار `revision` — **وفي صدره إعلانُ أنّ إعادة الصياغة لم تقع، وعلّتها**.
#:
#: ⚠️ **والجملة ليست تبريراً شكلياً بل شرط سلامة**: قائمة الأخطاء تُبنى من فحوص
#: **وقعت على هذه المسوّدة بعينها**، وإعادة الصياغة **تُنتج نصّاً آخر** لم تجرِ
#: عليه الفحوص — فيصير المستند وفحوصه **يصفان نصّين مختلفين**، وهو أسوأ من ترك
#: الخطأ ظاهراً. فمن وصل الحلقة لاحقاً **يجب أن يغيّر هذه الجملة بقصد**، لا أن
#: يجد إطاراً يقرأ «تمّت» فيُصدّق.
REVISION_NOT_REDRAFTED = (
    "هذه قائمة ما وجدته الفحوص مجتمعةً. "
    "ولم تُجرَ إعادة صياغة: الحلقة لم تُوصَل بعد، "
    "وإعادة الصياغة بلا إعادة تشغيل الفحوص "
    "تترك المستند وفحوصه يصفان نصّين مختلفين."
)

#: نصّ الفشل — **إعلانٌ لا سكوت، وليس درجةً تُقرأ نظافة**.
#:
#: ⚠️ **ولا يُبتلع الفشل بقائمة فارغة**: إطارٌ بلا أخطاء يُقرأ «لا عيب»، وهو
#: الكذب نفسه الذي يمنعه `briefing.py` — فالفحص الذي **لم يجرِ** ليس فحصاً نجح.
REVISION_COLLECT_FAILED = (
    "تعذّر جمع قائمة الأخطاء: لم تُبنَ القائمة أصلاً، "
    "وغيابُ القائمة ليس سلامة — الفحوص التي جرت لم تُعرَض، "
    "والفحص الذي لم يجرِ ليس فحصاً نجح."
)


def _revision_frame(
    draft: str,
    *,
    review_outcome: Optional[object],
    fidelity_shifts: Optional[Sequence] = None,
    attribution_outcome: Optional[object] = None,
    language_report: Optional[object] = None,
) -> dict:
    """
    إطار `revision`: **قائمة الأخطاء المُوحَّدة** من المصادر الأربعة، قبل الختم.

    ⚠️ **وثلاثة من المصادر تُحسَب موضعياً ولا تُبَثّ، والرابع لا يُعاد بلا ثمن.**
    وهذا ما أثبته التشغيل لا ما قُدِّر:

      • ``fidelity``: ``check_fidelity(clean, ledger)`` **خالصة** — لا نموذج ولا
        شبكة ولا قرص — و``ledger`` مُعاملٌ في المولّد، فتُعاد هنا بلا كلفة.
        ولهذا لا تُقرأ من إطار `facts`: **ذاك يحمل افتراقاتٍ مُلخَّصة لا كائنات
        ``FactShift``**، و``collect_errors`` تصل إلى **خصائص** الكائن
        (``shift.fact_key``) — فالمعلومة تُفقد عند الملخّص، وبناءها منه مستحيل.
      • و``attribution`` و``language``: فحصان حتميان، مدخلاتهما (``clean``
        والأدلّة) في النطاق، فيُعاد تشغيلهما كما يُعاد الأول.
      • و``review`` وحده **نداءُ نموذج** — لا يُعاد بلا ثمن، فيُبَثّ من
        ``_review_round`` ككائنٍ خام.

    ⚠️ **ولا كائن مُنمَّط يدخل هذا الإطار**: الإطار يُسلسل إلى JSON ليُبثّ عبر
    SSE، ووضع ``FactShift`` في مفتاح أسقط أربعة اختبارات — أحدها اسمه
    ``test_the_frame_is_json_serializable``. فالخام يُستهلك هنا **ويُهدم أثره**
    قبل البناء، ويُبَثّ من الحقول نصّاً لا كائناً.

    ⚠️ **وَ``None`` مقابل ``()`` هو تصميم الوحدة كلّه، ويُحترم كما هو**:
    ``fidelity_shifts=None`` تعني «لم يُشغَّل الفحص» فتُمرَّر كما هي ولا يُدرَج
    المصدر في ``checked_sources``؛ و``()`` تعني «شُغّل ولم يُنتج افتراقاً».
    فتمرير ``()`` عن فحص لم يقع **يجعل النظام يشهد بفحص لم يحدث** — وهو العطب
    الذي وُلد `briefing.py` لمنعه.

    ⚠️ **والفشل هنا يُعلَن ولا يُبتلع**، والمرجع ``None`` لا قائمةٌ فارغة.
    """
    # ⚠️ والاستدعاء داخل `try` **بلا ابتلاع**: النجاح وحده يُبنى، والفشل يُقال.
    try:
        errors = revision_loop.collect_errors(
            draft,
            review_outcome=review_outcome,
            fidelity_shifts=fidelity_shifts,
            attribution_outcome=attribution_outcome,
            language_report=language_report,
        )
        checked = revision_loop.sources_checked(
            review_outcome=review_outcome,
            fidelity_shifts=fidelity_shifts,
            attribution_outcome=attribution_outcome,
            language_report=language_report,
        )
    except Exception as exc:  # noqa: BLE001 — الفشل يُعلَن ولا يُسقط التوليد
        print(f"\n[Revision] ⚠️ تعذّر جمع قائمة الأخطاء: {type(exc).__name__}: {exc}")
        return {
            "errors": [],
            "checked_sources": [],
            "redrafted": False,
            "collected": False,
            "message": REVISION_COLLECT_FAILED,
        }

    # ⚠️ الخام يُترجم إلى **حقول نصّية** هنا، فلا يعبر كائنٌ إلى الإطار.
    return {
        "errors": [
            {
                "source": error.source,
                "kind": error.kind,
                "severity": error.severity,
                "message": error.message,
                "quote": error.quote,
            }
            for error in errors
        ],
        "checked_sources": list(checked),
        "redrafted": False,
        "collected": True,
        "message": REVISION_NOT_REDRAFTED,
    }


def _stream_agent(
    messages: list,
    case_frame: Optional[dict] = None,
    ledger: Optional[FactLedger] = None,
    claims_matrix=None,

):
    """
    يولّد أحداث الوكيل خطوة بخطوة.

    يُنتج أزواجاً (kind, payload):
        ("stage", StageEvent)     عند بدء استدعاء أداة أو انتهائه
        ("citations", {...})      تقرير التحقّق من الأسانيد
        ("language", {...})       تقرير التدقيق اللغوي
        ("review", {...})         تقرير المراجعة الثانية
        ("facts", {...})          فحص أمانة الوقائع — أو إعلان أنّه لم يُشغَّل
        ("revision", {...})       قائمة الأخطاء المُوحَّدة — أو إعلان تعذّر جمعها
        ("briefing", {...})       التقرير الداخلي: قاموسه ونصّه
        ("final", "نص المستند")   عند اكتمال الصياغة — بلا كتلة الأسانيد

    ⚠️ جامع الأدلة يُفتح **هنا** لا في المستدعي. السبب: هذه الدالة تُنفَّذ داخل
    الخيط العامل حيث تجري الأدوات، و`ContextVar` معزول لكل خيط. ولو فُتح الجامع
    في حلقة الأحداث لما رآه الخيط العامل أصلاً، فتُسجَّل الأدلّة في سياق فارغ
    ويصير التحقّق بلا معنى.

    ⚠️ **وَ``case_frame`` و``ledger`` يُمرَّران لا يُقرآن من حالة عامّة**:
    إطار `case` يُبنى في `generate` قبل الخيط (فحملُه الفاسد يُردّ قبل الوكيل)،
    وسجلّ الوقائع كذلك. والمعرَّفان هنا لأن **إطاري `facts` و`briefing` يُبنيان
    بعد وجود المسودّة** — فلا يمكن بناؤهما في النقطة كما يُبنى إطار `case`.
    و``None`` في كليهما مقصود: «لم يُرسل حمل» معلومة تُقال، لا فراغ يُسكت عنه.
    """
    yield ("stage", StageEvent(KEY_INTAKE, STAGE_ANALYSING))

    config = {"recursion_limit": AGENT_RECURSION_LIMIT}
    final_text = ""
    invoked_any_tool = False
    evidence: list = []

    with collect_evidence() as collected:
        for event in agent.stream(
            {"messages": messages}, config=config, stream_mode="updates"
        ):
            for node, update in event.items():
                if not isinstance(update, dict):
                    continue
                new_messages = update.get("messages") or []
                if not new_messages:
                    continue
                last = new_messages[-1]

                if node == "chatbot":
                    tool_calls = getattr(last, "tool_calls", None) or []
                    if tool_calls:
                        for call in tool_calls:
                            name = (call or {}).get("name", "")
                            label = TOOL_STAGE_LABELS.get(
                                name, f"جاري البحث باستخدام {name}..."
                            )
                            # المفتاح من اسم الأداة؛ وأداة غير مسجّلة تحصل على
                            # مفتاحها الخاص بدل أن تُسقَط المرحلة.
                            yield (
                                "stage",
                                StageEvent(TOOL_STAGE_KEYS.get(name, name), label),
                            )
                        continue
                    text = _extract_text(last)
                    if text:
                        final_text = text

                elif node == "tools":
                    invoked_any_tool = True
                    yield ("stage", StageEvent(KEY_EVIDENCE, STAGE_EVIDENCE_FOUND))

        # نقرأ الأدلّة **داخل** السياق: خارجه يكون الجامع قد أُغلق.
        evidence = collected.evidence

    if invoked_any_tool and final_text:
        yield ("stage", StageEvent(KEY_DRAFTING, STAGE_DRAFTING))

    if final_text:
        # ترتيب المراجعة يتبع فريق `smart_office.py` نفسه:
        #   مُسوَدَّة أفندي (الصياغة) ← المفتش ثُغرة (الأسانيد)
        #   ← سيبويه المُكشّر (الصياغة اللغوية) ← أبو الختم (الاعتماد والختم)
        #
        # وكل مرحلة **تُبثّ قبل** نتيجتها: فيرى المحامي المدقّق يعمل ثم يستلم
        # تقريره، بدل أن يظهر التقرير من العدم.
        yield ("stage", StageEvent(KEY_VERIFYING, STAGE_VERIFYING))
        clean, citation_report = _verify_round(final_text, evidence)
        yield ("citations", citation_report)

        # سيبويه المُكشّر — تدقيق لغوي حتمي بلا نموذج (انظر language_audit.py)
        yield ("stage", StageEvent(KEY_POLISH, STAGE_POLISHING))
        language_report = summarize_language_audit(audit_language(clean))
        yield ("language", language_report)

        # المفتش ثُغرة — القراءة الثانية. وقبل الختم، فلا يُختم إلا بعد مراجعة.
        yield ("stage", StageEvent(KEY_REVIEW, STAGE_REVIEWING))
        # ⚠️ **والزوج مقصود**: الإطار للمحامي كما كان (فلا ينكسر تسلسله إلى
        # JSON)، **والحصيلة الخام تعبر معه** — لأن `collect_errors` تصل إلى
        # خصائص الكائن، والملخّص لا يحمل كائناً. فالمعلومة تُلتقط عند مَن
        # يملكها، ولا يُعاد بناءها من ملخّص فُقدت فيه.
        review_report, review_outcome = _review_round(
            _brief_from(messages), clean, _evidence_text(evidence)
        )
        yield ("review", review_report)

        # ------------------------------------------------------------------
        # أمانة الوقائع — **بعد وجود المسودّة، وقبل الختم**
        # ------------------------------------------------------------------
        # ⚠️ **وموضعه هنا هو فائدته**: الواقعة المُغيَّرة تُرى **قبل** أن يُعتمد
        # المستند لا بعده. ولو بُثّ بعد الختم لَما كان إنذاراً بل تقريراً عن
        # مستندٍ انتهى — وهو عين العيب الذي تكرّر ثلاث مرّات: أن يُسلَّم عملٌ
        # وفيه واقعة مقلوبة.
        # ⚠️ **ويُفحَص النصّ النظيف** (`clean`) — وهو المستند الذي يقرأه المحامي،
        # لا نصّ النموذج بكتلة أسانيده: فكتلة الأسانيد رموزٌ لا من المذكرة،
        # وإدخالها في المقابلة يرفع التغطية زوراً.
        facts_frame = _facts_frame(clean, ledger)
        yield ("facts", facts_frame)
        yield (
            "claims",
            _claims_frame(clean, claims_matrix, ledger, case_frame),
        )

        # ------------------------------------------------------------------
        # قائمة الأخطاء المُوحَّدة — **بعد `review` وقبل `briefing`**
        # ------------------------------------------------------------------
        # ⚠️ **وثلاثة من المصادر تُحسَب هنا في النطاق، ولا تُبَثّ من بعيد:**
        #  • ``fidelity``: ``check_fidelity`` خالصة (بلا نموذج وبلا شبكة وبلا
        #    قرص)، و``ledger`` مُعاملٌ في هذا المولّد. ⚠️ **ولا تُقرأ من إطار
        #    `facts`** — ذاك يحمل افتراقات **مُلخَّصة** لا كائنات ``FactShift``،
        #    و``collect_errors`` تقرأ خصائص الكائن — فالمعلومة تُفقد قبل هنا.
        #  • و``attribution`` و``language``: فحصان حتميان، مدخلاتهما (``clean``
        #    والأدلّة) في النطاق، فيُعاد تشغيلهما من الوحدة نفسها — **بلا نسخة
        #    ثانية للحكم**، وهو العيب الذي حذّرت منه الوحدات مراراً.
        #  • و``review`` وحده نداءُ نموذج، فلا يُعاد: يعبر خاماً من الزوج أعلاه.
        #
        # ⚠️ **وَ``None`` هنا ليست ``()``**: `check_fidelity` تُشغَّل فقط متى
        # وُجد سجلّ؛ وبغيابه تُمرَّر ``None`` = «لم يُشغَّل» — **فلا يُدرَج
        # المصدر في ``checked_sources``**. ولو مُرّرت ``()`` لَقيل «شُغّل ولم
        # يجد شيئاً»، **ولَشهد النظام بفحص لم يقع**.
        raw_shifts = (
            tuple(check_fidelity(clean, ledger)) if ledger is not None else None
        )
        attribution_outcome = verify_attributions(
            clean, evidence, lambda row: getattr(row, "text", "") or ""
        )
        language_outcome = audit_language(clean)
        yield (
            "revision",
            _revision_frame(
                clean,
                review_outcome=review_outcome,
                fidelity_shifts=raw_shifts,
                attribution_outcome=attribution_outcome,
                language_report=language_outcome,
            ),
        )

        # ------------------------------------------------------------------
        # التقرير الداخلي — **آخر إطار تقرير، وقبل الختم**
        # ------------------------------------------------------------------
        # ⚠️ **وهنا سبب وجود `briefing.py`**: عرضُ عملٍ ناقص التحقّق على أنه
        # منتهٍ. فالفحص الذي لم يجرِ يُمرَّر ``None`` **لا ملخّصاً نظيفاً**:
        #  • ``facts`` غائبٌ سجلُّه ⇒ ``facts_frame["ledger"]`` هو ``None``،
        #    فيقول التقرير «لم يُشغَّل» ولا يقول «لا افتراق».
        #  • والمراجعة تمرّ **كما هي**: وإن وصلت ``failed: True`` ومعه
        #    ``clean: True`` فالتقرير يعرف ترتيبها (`FAILED_KEYS` في الوحدة)،
        #    ولا نُصلحها هنا — إصلاحها هنا يُخفي أن النداء لم يجرِ.
        #  • و``attribution`` **جرى داخل `_verify_round`**، فتمريره ليس تبرّعاً:
        #    تركُه يجعل التقرير يشهد أنّه لم يُشغَّل وهو قد جرى.
        #  • وملف القضية يُمرَّر بما أثبته إطاره؛ فإن لم يُبنَ فهو ``None``.
        # ⚠️ **ولا يُبنى بعد الختم**: «لا عمل بعد الختم إلا التسليم»، والتقرير
        # عملٌ يُحسب — فلا يُحسب بعد أن يُعتمد المستند.
        yield (
            "briefing",
            _briefing_frame(
                reports={
                    "citation": citation_report,
                    "attribution": citation_report.get("attribution"),
                    "review": review_report,
                    "language": language_report,
                    "facts": facts_frame["ledger"],
                    "case_file": (case_frame or {}).get("case"),
                },
                open_questions=_case_open_questions(case_frame),
            ),
        )

        # المعلم أبو الختم — لا عمل بعد الختم إلا التسليم
        yield ("stage", StageEvent(KEY_SEAL, STAGE_SEALING))
        yield ("final", clean)
    else:
        yield ("final", "")


def _evidence_text(evidence: list) -> str:
    """
    نصّ المقاطع كاملاً — وهو **سند المُراجع**.

    ⚠️ ولا يُرسَل مع حقل التشابه ولا المُعرّف: المُراجع يحتاج أن ينقل نصّاً
    حرفياً من سند، **فلا يُعطى إلا النصّ**.
    """
    parts = []
    for item in evidence:
        text = getattr(item, "text", "") or ""
        if text.strip():
            parts.append(f"[{getattr(item, 'ref', '')}] {text}")
    return "\n\n".join(parts)


def _brief_from(messages: list) -> str:
    """
    موجز المحامي — آخر رسالة بشرية في المحاورة.

    ⚠️ وهو **مرجع المُراجع**: به يحكم على المسودّة، وإليه يعود كل سند ينقله.
    ⚠️ ويُقرأ من `messages` لا كمتغيّر منفصل، **لأن `/chat` يرسل المحاورة كلها
    وتكون آخر رسالة هي السؤال الأحدث** — وهو الموجز في الحالتين.
    """
    for message in reversed(messages or []):
        if isinstance(message, (tuple, list)) and len(message) == 2:
            role, text = message
            if str(role).lower() not in ("system",):
                return str(text)
            continue
        # رسالة LangChain: نستبعد رسائل النظام وحدها
        if type(message).__name__ in ("SystemMessage",):
            continue
        maybe = _message_text(message)
        if maybe.strip():
            return maybe
    return ""


def _message_text(message) -> str:
    """يستخرج نصّ رسالة LangChain بصيغةٍ واحدة."""
    content = getattr(message, "content", message)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        chunks = []
        for part in content:
            if isinstance(part, str):
                chunks.append(part)
            elif isinstance(part, dict) and isinstance(part.get("text"), str):
                chunks.append(part["text"])
        return "".join(chunks)
    return str(content or "")


def _review_round(
    brief: str, draft: str, evidence_text: str
) -> tuple[dict, Optional[object]]:
    """
    المراجعة الثانية — «المفتش ثُغرة» يقرأ المسودّة **كخصم لا كصديق**.

    ⚠️ وهذا الفريق الذي بُني في `smart_office.py` **ولم يكن مستخدماً**: مسوَدَّة
    أفندي يكتب، ثم مُدقّق يقرأ. والكتابة بلا قارئ ثانٍ هي ما جعل مسودّة كريم
    منصور تمرّ وفيها تاريخ خاطئ وأساس حساب خاطئ ومادة مُغفَلة.

    ⚠️ **والأمانة التقنية كلها في `review.py`**: كل اعتراض يجب أن يحمل نصّاً
    منقولاً حرفياً من المسودّة وسنداً منقولاً حرفياً من الموجز أو المقاطع،
    **والخادم يتحقّق من الاثنين** (`quote_in_text`). فاعتراض لا يُثبت نصّه
    **يُطرح ولا يُعرض على المحامي**.

    ⚠️ **والفشل هنا لا يُسقط التوليد أبداً** — لكنه **يُعلَن** (`failed: True`)
    ولا يُسكَت عنه. فمسودّة بلا مراجعة أفضل من توليد منقطع، **ومراجعة تُوهم
    أنها جرت أسوأ من الاثنين**.

    ⚠️ **وتُعيد زوجاً: (الإطار, الحصيلة الخام أو ``None``)** — والسبب أنّ
    ``collect_errors`` في `revision_loop` تصل إلى **خصائص** الحصيلة
    (`finding.message`)، والملخّص `summarize_review` **لا يحمل كائناً** —
    فبناء الحصيلة من الإطار مستحيل، والمعلومة تُفقد عند الباب. فالخام يعبر من
    هنا، **والإطار يبقى كما هو فلا يُكسر تسلسله إلى JSON**.

    ⚠️ **و``None`` في الموضع الثاني ليست تفصيلاً**: هي القول «المراجعة **لم
    تجرِ**» — فرع الاستثناء، والمسوّدة الفارغة. ولا تُستبدل بقائمة فارغة
    (``()``) أبداً: ``()`` تعني «جرت ولم تجد شيئاً»، وتمريرها عن فحصٍ لم يقع
    **يجعل النظام يشهد بفحص لم يحدث** — وهذا موضع ``sources_checked`` نفسه.
    """
    if not draft.strip():
        return {}, None

    try:
        raw = _message_text(llm.invoke(build_review_prompt(brief, draft, evidence_text)))
        outcome = parse_review(raw, draft, brief, evidence_text)
    except Exception as exc:  # noqa: BLE001
        print(f"\n[Review] ⚠️ تعذّرت المراجعة الثانية: {type(exc).__name__}: {exc}")
        return {
            "summary": f"تعذّرت المراجعة الثانية: {type(exc).__name__}",
            "clean": True,
            "error_count": 0,
            "notice_count": 0,
            "dropped": 0,
            "findings": [],
            "failed": True,
        }, None

    report = summarize_review(outcome.findings, outcome.dropped)
    report["failed"] = False
    print(f"\n[Review] 🛡️ اعتراضات: {report['error_count']} · ملاحظات: {report['notice_count']}")
    return report, outcome


def _run_agent_collect(messages: list) -> tuple[str, dict, dict]:
    """
    ينفّذ الوكيل ويُرجع (النصّ, تقرير الأسانيد, تقرير الصياغة) — لـ /chat.

    ⚠️ **ولا يمرّ ملف القضية من هنا، ولا يتغيّر شكل الثلاثي.**

    وهذا قرار مقصود عند وصل `case_file`: `/chat` محادثة، ولا مدخل فيها لملف
    قضية — فلا يُعاد تشكيل ثابتٍ يُبنى عليه مسارٌ لم يُطلب فيه ملف. ولو
    مُرِّر الملف من هنا لصار الثلاثي رباعياً، **فانكسر كل مستدعٍ له بصمت** —
    وهو العطب الذي يمنعه `test_run_agent_collect_shape_is_unchanged`.

    ⚠️ **وإطار `case` لا يُنتج من هنا** بل من `_sse_generator` — لأن `/chat`
    لا يبثّ SSE أصلاً. ولو أُنتج هنا لكان إطاره يُهمَل في `/chat` ويُبثّ في
    `/generate` من موضعين يفترقان.

    ⚠️ **وأُبقي الشكل ثلاثياً عند وصل `facts` و`briefing` — والخيار مكتوب هنا.**
    البديل كان إضافة إطارَي الوقائع والتقرير الداخلي إلى المُعاد، وهو يهدم
    عقداً قائماً على ثلاثة **ويجعل لـ`/chat` شكلَ بثٍّ ثانياً**: أي أن ما يُختبر
    في `/generate` لا يُختبر في `/chat` والعكس. أما الإطارات الجديدة فتُهمَل هنا
    كما يُهمَل إطار `review` القائم — **لأن `/chat` لا يبثّ SSE أصلاً**، فإطار
    التقرير الداخلي لا موضع له في ردّ محادثة، وفحص الوقائع لا سجلّ له فيها.
    ⚠️ **ولا تُبنى الإطارات مرّتين**: `_stream_agent` يبنيها في الحالين، ويُهمَل
    في `/chat` ما لا يُعاد. وثمنُ ذلك حسابٌ حتمي بلا نموذج ولا شبكة — أرخص من
    مسارين يفترقان.
    """
    final_text = ""
    report: dict = {}
    language: dict = {}
    for kind, payload in _stream_agent(messages):
        if kind == "citations":
            report = payload
        elif kind == "language":
            language = payload
        elif kind == "final":
            final_text = payload
    return final_text, report, language


# ==============================================================================
# ٦. نقاط النهاية
# ==============================================================================


@app.get("/health")
async def health():
    """فحص صحة الخادم — يفيد في مراقبة النشر."""
    return {
        "status": "ok",
        "service": "legal-brain-api",
        "version": app.version,
        "tools": list(TOOL_STAGE_LABELS.keys()),
        "active_sessions": len(_sessions),
        "allowed_origins": _allowed_origins,
        # مفيد للتشخيص: هل المصادقة مُفعَّلة على هذا الخادم؟
        "auth_required": bool(API_TOKEN),
        # هل يتحقّق الخادم من الأسانيد؟ (دائماً نعم منذ ربط citations.py)
        "citation_verification": True,
        # هل يستقبل الخادم تصحيحات المحامي؟ (يحتاج جدول draft_revisions)
        "revision_capture": True,
    }


async def _sse_generator(
    messages: list,
    case_frame: Optional[dict] = None,
    ledger: Optional[FactLedger] = None,
) -> AsyncIterator[str]:
    """
    يحوّل مُولِّد الوكيل المتزامن (blocking) إلى بثّ غير متزامن.

    agent.stream يستدعي الشبكة ويحجب حلقة الأحداث، لذا ننفّذه في خيط منفصل
    ونمرّر الأحداث إلى طابور asyncio عبر call_soon_threadsafe.

    ⚠️ **وإطار `case` يُبثّ هنا أولاً، قبل أول مرحلة** — في الخيط العامل نفسه
    وبنفس `emit`، فلا يسبقه شيء ولا يفترق شكله عن بقية الإطارات.

    ⚠️ **ولماذا لا يُبثّ في `generate` قبل إرجاع البثّ؟** لأن `generate` يُرجع
    ``StreamingResponse`` ولا يكتب فيه شيئاً؛ فالإطار الأول لا يُسلَّم إلا حين
    يبدأ استهلاك المولّد — فلو بُثّ هناك لكان ترتيبه غير مضمون بالنسبة للمراحل.

    ⚠️ **وَ``ledger`` يُمرَّر إلى ``_stream_agent`` ولا يُقرأ من حالة عامّة**:
    إطار `facts` يُبنى **بعد وجود المسودّة**، فلا يمكن بناؤه في `generate` كما
    يُبنى إطار `case`. والسجلّ نفسُه بُني في `generate` قبل الخيط (فحملُه الفاسد
    يُردّ ٤٠٠ قبل أن يُستدعى نموذج)، فلا يُعاد بناؤه هنا.
    """
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue()
    sentinel = object()

    def emit(item: dict) -> None:
        loop.call_soon_threadsafe(queue.put_nowait, item)

    def worker() -> None:
        try:
            if case_frame is not None:
                emit({"type": "case", "report": case_frame})

            for kind, payload in _stream_agent(messages, case_frame, ledger, None):
                if kind == "stage":
                    # مفتاح المرحلة مع النصّ: الواجهة تقرّر بالمفتاح وتعرض النصّ
                    emit(
                        {
                            "type": "stage",
                            "stage": payload.key,
                            "message": payload.message,
                        }
                    )
                elif kind == "citations":
                    emit({"type": "citations", "report": payload})
                elif kind == "language":
                    emit({"type": "language", "report": payload})
                elif kind == "review":
                    emit({"type": "review", "report": payload})
                elif kind == "facts":
                    emit({"type": "facts", "report": payload})
                elif kind == "claims":
                    emit({"type": "claims", "report": payload})
                elif kind == "revision":
                    # ⚠️ **ولا كائن مُنمَّط في هذا الإطار**: قائمة الأخطاء تُبثّ
                    # حقولاً نصّية (المصدر والنوع والخطورة والنصّ والاقتباس)،
                    # **بلا `action` وبلا `fixable_by_redraft`** — وكلاهما قرارُ
                    # الحلقة لا عرضٌ للمحامي. ووضع ``FactShift`` في الإطار
                    # أسقط أربعة اختبارات، لأن الإطار يُسلسل JSON.
                    emit({"type": "revision", "report": payload})
                elif kind == "briefing":
                    # ⚠️ النصّ يُبثّ مع القاموس: الواجهة تعرض التقرير كما بنته
                    # الوحدة، ولا تُعيد بناءه — ونصٌّ ثانٍ ينحرف بصمت.
                    emit(
                        {
                            "type": "briefing",
                            "report": payload["report"],
                            "markdown": payload["markdown"],
                        }
                    )
                elif kind == "final":
                    if payload:
                        emit({"type": "done", "document": payload})
                    else:
                        emit(
                            {
                                "type": "error",
                                "message": (
                                    "لم يُنتج النموذج أي نص. تحقّق من صحة "
                                    "GOOGLE_API_KEY ومن وجود بيانات في قاعدة المعرفة."
                                ),
                            }
                        )
        except Exception as exc:  # noqa: BLE001 — نُبلّغ العميل بأي فشل
            emit({"type": "error", "message": f"{type(exc).__name__}: {exc}"})
        finally:
            loop.call_soon_threadsafe(queue.put_nowait, sentinel)

    threading.Thread(target=worker, daemon=True).start()

    while True:
        item = await queue.get()
        if item is sentinel:
            break
        # ensure_ascii=False ضروري ليصل النص العربي مقروءاً لا مُرمَّزاً
        yield f"data: {json.dumps(item, ensure_ascii=False)}\n\n"


@app.post("/generate", dependencies=[Depends(require_token)])
async def generate(req: GenerateRequest):
    """
    توليد مستند قانوني ببثّ حيّ.

    هذه هي النقطة التي كانت غائبة تماماً: الواجهة كانت تنتظر بثّ SSE من
    عنوان لا وجود له، فلم يكن المستند يظهر أبداً.

    ⚠️ **و`case_file` كان مبنياً ومختبراً ولا يُنادى من أيّ موضع** — فكان
    يوجد ولا يُغيّر شيئاً. وهو يُنادى الآن **مرة واحدة هنا، قبل أن يجري
    الوكيل**: فالحمل الذي يرفضه الملف يُردّ ٤٠٠ **قبل أن يُستدعى نموذج واحد**،
    ولا يُبتلع صامتاً — لأن **حملاً يُتجاهَل أسوأ من حملٍ غائب**: المستدعي
    يظنّ أن ملفه مرّ، فتُبنى المسودّة على غير ما طلب.

    ⚠️ **والملف الناقص لا يوقف التوليد.** المطلوب أن يُسأل عن النواقص
    **ويُكمل ما لا يتوقّف عليها** — فالنقص يُبثّ في إطار `case` ويُدخل في
    الرسالة، ولا يُردّ الطلب. والردّ محصورٌ في حملٍ **يرفضه الملف** (إمارة لا
    مفتاح لها، أو قيمة تصنيف مجهولة).

    ⚠️ **والبناء قبل بناء الرسائل وقبل الخيط**: أي فشل هنا يرتفع من النقطة
    نفسها فيردّه FastAPI ٤٠٠، ولا يُفتح بثّ ولا يُستدعى الوكيل.

    ⚠️ **وسجلّ الوقائع يُبنى هنا أيضاً، وقبل الخيط** — `facts.py` كان مبنياً
    ومختبراً ولا يُنادى من أيّ موضع، كحال `case_file` قبله. وسجلٌّ يرفضه
    `FactLedger` (مفتاح مكرّر، أو واقعة بلا مفتاح أو نصّ، أو درجة مجهولة، أو
    واقعة `AGREED` أنشأها المسار) **يُردّ ٤٠٠ برسالة الوحدة، قبل أن يُستدعى
    نموذج واحد** — لأن سجلّاً فاسداً يُتجاهَل صامتاً يُوهم المستدعي أنّ وقائعه
    قُوبلت، فتُبنى المسودّة على غير ما أرسل.
    ⚠️ **والفاسد لا يُبتلع ولا يُوقف العمل الصحيح**: غياب السجلّ كليّاً لا يردّ
    الطلب، بل يُبثّ إطار `facts` يقول صراحةً إنّ الفحص **لم يُشغَّل**.
    """
    case_input = _case_from_payload(req.case)
    ledger = _facts_from_payload(req.facts)
    messages = _build_messages(req.prompt, req.doc_type, case_input)
    return StreamingResponse(
        _sse_generator(messages, _case_frame(case_input), ledger),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            # يمنع الوسيط العكسي (nginx / Codespaces) من تجميع البثّ وحجبه
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/chat", dependencies=[Depends(require_token)])
async def chat_endpoint(req: ChatRequest):
    """محادثة بردّ JSON كامل — متوافق مع الاستخدام السابق، مع عزل الجلسات."""
    session_id = req.session_id or "default"
    history = _get_history(session_id)
    history.append(HumanMessage(content=req.prompt))

    try:
        answer, citations, language = await asyncio.to_thread(
            _run_agent_collect, _trim_history(history)
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"{type(exc).__name__}: {exc}")

    if not answer:
        answer = (
            "لم أتمكّن من إنتاج ردّ. تحقّق من صحة مفاتيح الـ API ومن وجود "
            "بيانات مستوعَبة في قاعدة المعرفة."
        )

    history.append(AIMessage(content=answer))
    return {
        "response": answer,
        "session_id": session_id,
        "citations": citations,
        "language": language,
    }


@app.post("/revisions", dependencies=[Depends(require_token)])
async def save_revision(req: RevisionRequest):
    """
    يحفظ زوجاً (مسودّة ← نسخة المحامي المعتمدة).

    الغرض بناء مادة خام لتقليد أسلوب صاحب المكتب: كل تصحيح لا يُسجَّل يضيع،
    فيبقى الأسلوب في الموجّه تخميناً لا تعلّماً. و`revisions.py` يحسب نسبة
    التعديل، وهي مؤشّر جودة يُرى بعد كل مسودّة بلا استبيان.

    ⚠️ ولا يدخل هذا الجدول الاسترجاع أبداً — انظر القسم ١٠ في `schema.sql`.
    """
    try:
        record = await asyncio.to_thread(
            partial(
                build_revision,
                req.generated_text,
                req.corrected_text,
                doc_type=req.doc_type,
                prompt=req.prompt,
                session_id=req.session_id,
            )
        )
    except RevisionRejected as exc:
        # ٤٠٠ لا ٥٠٠: الطلب نفسه غير صالح (فارغ، أو بلا أي تغيير) لا الخادم
        raise HTTPException(status_code=400, detail=str(exc))

    try:
        await asyncio.to_thread(
            lambda: get_supabase().table(REVISIONS_TABLE).insert(record.to_row()).execute()
        )
    except Exception as exc:  # noqa: BLE001 — نُبلّغ بسبب مفهوم لا بأثر مكدّس
        raise HTTPException(status_code=503, detail=_revision_storage_error(exc))

    return {
        "saved": True,
        "edit_ratio": record.edit_ratio,
        "quality_band": record.quality_band,
        "word_count": record.word_count,
    }


@app.get("/revisions/stats", dependencies=[Depends(require_token)])
async def revision_stats():
    """
    تقدّم تقليد الأسلوب: كم زوجاً حُفظ، وما متوسّط ووسيط نسبة التعديل.

    الوسيط يُعرض مع المتوسّط لأن الأخير وحده مضلِّل: مسودّة واحدة أُعيدت
    كتابتها بالكامل ترفعه فتُخفي أن البقية شبه مطابقة.

    ملاحظة أداء: يجلب عمود `edit_ratio` وحده لا النصوص. فعشرات الآلاف من
    الأرقام تبقى حمولة صغيرة، بخلاف جلب المسودّات كاملة.
    """
    try:
        response = await asyncio.to_thread(
            lambda: get_supabase().table(REVISIONS_TABLE).select("edit_ratio").execute()
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=_revision_storage_error(exc))

    rows = response.data or []
    return summarize([row.get("edit_ratio") for row in rows])


@app.get("/archive/overview", dependencies=[Depends(require_token)])
async def archive_overview():
    """
    أرقام الأرشيف الحقيقية — لكل عائلة من العائلات الخمس.

    ⚠️ ولماذا دالّة SQL؟ لأن `count(distinct document_name)` و`group by` لا
    يدعمهما PostgREST. وكان يمكن جلب الأسماء كلها وجمعها في بايثون، لكنه يعني
    تنزيل آلاف الصفوف في كل فتح للصفحة. فالعمل يجري حيث البيانات.

    والعائلات الخمس تُعاد **كلها** حتى لو كانت فارغة: فلوحة القيادة يجب أن
    تُظهر «٠» لا أن تُخفي العائلة. وإخفاؤها يُوهم أن الأرشيف لا يغطّيها.
    """
    try:
        response = await asyncio.to_thread(
            lambda: get_supabase().rpc(ARCHIVE_OVERVIEW_RPC, {}).execute()
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=_archive_storage_error(exc))

    found = {row.get("family_key"): row for row in (response.data or [])}
    families = [
        {
            "key": key,
            "label": label,
            "documents": int((found.get(key) or {}).get("documents") or 0),
            "chunks": int((found.get(key) or {}).get("chunks") or 0),
            "latest_added": (found.get(key) or {}).get("latest_added"),
        }
        for key, label in ARCHIVE_FAMILIES
    ]

    return {
        "documents": sum(item["documents"] for item in families),
        "chunks": sum(item["chunks"] for item in families),
        "families": families,
    }


@app.get("/archive/documents", dependencies=[Depends(require_token)])
async def archive_documents(
    search: str = "",
    family: str = "",
    sort: str = "recent",
    limit: int = 200,
):
    """
    مستندات الأرشيف مجموعةً بالاسم — لصفحة الأرشيف والمكتبة.

    و`family` تُرفض إن كانت مجهولة (400) ولا تُتجاهَل: فتصفية خاطئة تُعاد
    بنتيجة كاملة تبدو **صحيحة**، وهي أسوأ من خطأ صريح.
    """
    known = {key for key, _ in ARCHIVE_FAMILIES}
    if family and family not in known:
        raise HTTPException(
            status_code=400,
            detail=f"عائلة غير معروفة: {family!r} — المتاح: {sorted(known)}",
        )

    bounded = max(1, min(limit, ARCHIVE_MAX_ROWS))

    try:
        response = await asyncio.to_thread(
            lambda: get_supabase()
            .rpc(
                ARCHIVE_DOCUMENTS_RPC,
                {
                    "search_term": search.strip() or None,
                    "family_filter": family or None,
                    "sort_order": _archive_sort(sort),
                    "max_rows": bounded,
                },
            )
            .execute()
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=_archive_storage_error(exc))

    labels = dict(ARCHIVE_FAMILIES)
    documents = [
        {
            "document_name": row.get("document_name") or "",
            "document_type": row.get("document_type") or "",
            "family": row.get("family_key") or "",
            "family_label": labels.get(row.get("family_key") or "", ""),
            "chunks": int(row.get("chunks") or 0),
            "added_at": row.get("added_at"),
        }
        for row in (response.data or [])
    ]

    return {
        "count": len(documents),
        "limit": bounded,
        # صريح: هل قُصَّت النتيجة عند السقف؟ فالواجهة تقول «يوجد غيرها» بدل
        # أن تُوهم أن هذا الأرشيف كله.
        "truncated": len(documents) >= bounded,
        "documents": documents,
    }


@app.get("/archive/chunks", dependencies=[Depends(require_token)])
async def archive_chunks(
    search: str = "",
    family: str = "",
    document: str = "",
    sort: str = "recent",
    limit: int = 50,
):
    """
    المقاطع نفسها — لفتح مستند بفقراته، أو للبحث النصّي في المتن.

    ⚠️ وثلاث حالات في نداء واحد، والفصل مقصود:

      • `document` مُعطى  → **كل مقاطع ذلك المستند**، بترتيب فقراته.
        وهو «فتح المستند» الذي يطلبه المحامي ليقرأ ما يستند إليه الفريق.
      • `search` مُعطى    → بحث نصّي في المتن وفي اسم المستند.
      • لا هذا ولا ذاك    → أحدث المقاطع.

    ⚠️ **والبحث نصّي لا دلالي، وهو اختيار لا نقص.** البحث الدلالي يحتاج تحميل
    نموذج التضمين (٢.٢ غ.ب) وتشفير السؤال، وهو متاح في أدوات الوكيل الخمس حيث
    يُحتاج فعلاً. أما هنا فالمحامي يبحث عن **نصّ بعينه** — «أين وردت المادة
    ٤٨؟» — والبحث النصّي أدقّ في ذلك وأسرع: بلا نموذج وبلا انتظار.
    """
    known = {key for key, _ in ARCHIVE_FAMILIES}
    if family and family not in known:
        raise HTTPException(
            status_code=400,
            detail=f"عائلة غير معروفة: {family!r} — المتاح: {sorted(known)}",
        )

    bounded = max(1, min(limit, ARCHIVE_MAX_CHUNK_ROWS))

    try:
        response = await asyncio.to_thread(
            lambda: get_supabase()
            .rpc(
                ARCHIVE_CHUNKS_RPC,
                {
                    "search_term": search.strip() or None,
                    "family_filter": family or None,
                    "document_filter": document.strip() or None,
                    "sort_order": _archive_sort(sort),
                    "max_rows": bounded,
                },
            )
            .execute()
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=_archive_storage_error(exc))

    labels = dict(ARCHIVE_FAMILIES)
    chunks = [
        {
            "id": row.get("id"),
            "document_name": row.get("document_name") or "",
            "document_type": row.get("document_type") or "",
            "family": row.get("family_key") or "",
            "family_label": labels.get(row.get("family_key") or "", ""),
            "content": row.get("chunk_content") or "",
            "source_file": row.get("source_file") or "",
            "chunk_index": row.get("chunk_index"),
            "created_at": row.get("created_at"),
        }
        for row in (response.data or [])
    ]

    return {
        "count": len(chunks),
        "limit": bounded,
        "truncated": len(chunks) >= bounded,
        "chunks": chunks,
    }


@app.get("/", response_class=HTMLResponse)
async def index():
    """
    صفحة اختبار مستقلة للتحقق من البثّ الحي دون تشغيل واجهة Next.js.
    مفيدة لتشخيص الـ SSE بمعزل عن أي طبقة أخرى.
    """
    return """<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<title>اختبار العقل القانوني — البثّ الحي</title>
<style>
  body { font-family: Tahoma, sans-serif; background:#0f172a; color:#f1f5f9;
         margin:0; padding:24px; }
  h1 { color:#f59e0b; font-size:20px; margin:0 0 4px; }
  .hint { color:#64748b; font-size:13px; margin-bottom:18px; }
  select, textarea, button { font-family:inherit; font-size:15px; border-radius:8px;
         border:1px solid #1e293b; background:#020617; color:#f1f5f9; padding:10px; }
  textarea { width:100%; min-height:120px; resize:vertical; margin-top:10px; }
  button { background:#d97706; border:0; color:#fff; font-weight:700; cursor:pointer;
           padding:12px 22px; margin-top:12px; }
  button:disabled { opacity:.5; cursor:not-allowed; }
  #stage { color:#fbbf24; margin-top:18px; min-height:22px; }
  #doc { white-space:pre-wrap; background:#fff; color:#0f172a; padding:22px;
         border-radius:10px; margin-top:12px; line-height:1.9; display:none; }
  #err { color:#f87171; margin-top:12px; white-space:pre-wrap; }
  #cites { margin-top:16px; display:none; }
  #cites h3 { color:#f59e0b; font-size:15px; margin:0 0 8px; }
  .cite { background:#1e293b; border-inline-start:4px solid #22c55e; padding:10px 12px;
          border-radius:8px; margin:6px 0; font-size:14px; line-height:1.7; }
  .cite.bad { border-inline-start-color:#ef4444; }
  .cite .meta { color:#94a3b8; font-size:12px; margin-bottom:4px; }
  .warn { background:#422006; border-inline-start:4px solid #f59e0b; padding:10px 12px;
          border-radius:8px; margin:6px 0; font-size:14px; color:#fde68a; line-height:1.7; }
</style>
</head>
<body>
<h1>⚖️ اختبار البثّ الحي (SSE)</h1>
<div class="hint">اختبار مباشر لنقطة <code>POST /generate</code> دون واجهة Next.js.</div>

<label>نوع المستند</label><br>
<select id="docType">
  <option>لائحة دعوى تجارية</option>
  <option>إنذار قانوني</option>
  <option>وكالة قانونية خاصة</option>
  <option>مذكرة دفاع</option>
</select>

<textarea id="prompt" placeholder="اكتب الوقائع والمعطيات هنا...">صغ لائحة دعوى تجارية (مطالبة مالية) أمام محاكم دبي. المبلغ 20,000 درهم عن فواتير غير مسددة.</textarea>
<label>رمز المصادقة — اتركه فارغاً إن لم تضبط API_TOKEN في .env</label><br>
<input id="token" type="password" placeholder="API_TOKEN" style="width:100%;max-width:420px;margin-top:6px">
<br>
<button id="go" onclick="run()">ابدأ الصياغة</button>

<div id="stage"></div>
<div id="err"></div>
<div id="doc"></div>
<div id="cites"></div>

<script>
// يبني عنصراً بأمان: النصّ يمرّ عبر textContent لا innerHTML.
// ضروري لأن نصّ الاقتباس يأتي من النموذج — و innerHTML يجعله قابلًا للحقن.
function el(tag, cls, text) {
  const node = document.createElement(tag);
  if (cls) node.className = cls;
  if (text !== undefined) node.textContent = text;
  return node;
}

function renderCitations(report) {
  const box = document.getElementById('cites');
  box.textContent = '';
  if (!report) return;

  box.appendChild(el('h3', null, 'الأسانيد — ' + (report.summary || '')));

  (report.verified || []).forEach(function (c) {
    const card = el('div', 'cite');
    card.appendChild(el('div', 'meta',
      '[' + c.ref + '] ' + c.document_name +
      (c.similarity != null ? ' — تشابه ' + c.similarity.toFixed(2) : '')));
    card.appendChild(el('div', null, '«' + c.quoted_span + '»'));
    box.appendChild(card);
  });

  (report.rejected || []).forEach(function (c) {
    const card = el('div', 'cite bad');
    card.appendChild(el('div', 'meta', '[' + c.ref + '] مرفوض — ' + c.reason));
    card.appendChild(el('div', null, '«' + c.quoted_span + '»'));
    box.appendChild(card);
  });

  (report.unbacked_articles || []).forEach(function (a) {
    box.appendChild(el('div', 'warn',
      '⚠️ ' + a.surface + ' — لم ترد في أي مقطع مسترجَع من أرشيفك'));
  });

  (report.malformed_lines || []).forEach(function (line) {
    box.appendChild(el('div', 'warn', '⚠️ سند لم يُقرأ: ' + line));
  });

  if (!report.has_evidence) {
    box.appendChild(el('div', 'warn',
      '⚠️ لا سند موثَّق في هذه المسودّة — راجع كل مادة قانونية فيها قبل الاعتماد عليها.'));
  }

  box.style.display = 'block';
}

async function run() {
  const go = document.getElementById('go');
  const stage = document.getElementById('stage');
  const err = document.getElementById('err');
  const doc = document.getElementById('doc');

  go.disabled = true;
  err.textContent = '';
  doc.style.display = 'none';
  doc.textContent = '';
  const cites = document.getElementById('cites');
  cites.style.display = 'none';
  cites.textContent = '';
  stage.textContent = 'جاري الإرسال...';

  const token = document.getElementById('token').value.trim();
  const headers = { 'Content-Type': 'application/json' };
  if (token) headers['Authorization'] = 'Bearer ' + token;

  try {
    const res = await fetch('/generate', {
      method: 'POST',
      headers: headers,
      body: JSON.stringify({
        prompt: document.getElementById('prompt').value,
        doc_type: document.getElementById('docType').value,
      }),
    });
    if (!res.ok) throw new Error('HTTP ' + res.status + ' — ' + await res.text());

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    // محلّل SSE صحيح: الحدث قد يُقسَّم على أكثر من قطعة شبكية
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      let idx;
      while ((idx = buffer.indexOf('\\n\\n')) !== -1) {
        const raw = buffer.slice(0, idx);
        buffer = buffer.slice(idx + 2);
        const line = raw.split('\\n').find(l => l.startsWith('data: '));
        if (!line) continue;

        const evt = JSON.parse(line.slice(6));
        if (evt.type === 'stage') {
          stage.textContent = evt.message;
        } else if (evt.type === 'citations') {
          renderCitations(evt.report);
        } else if (evt.type === 'done') {
          stage.textContent = '✅ تمت الصياغة';
          doc.textContent = evt.document;
          doc.style.display = 'block';
        } else if (evt.type === 'error') {
          err.textContent = '❌ ' + evt.message;
          stage.textContent = '';
        }
      }
    }
  } catch (e) {
    err.textContent = '❌ ' + e.message;
    stage.textContent = '';
  } finally {
    go.disabled = false;
  }
}
</script>
</body>
</html>"""


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))


#: نصّ «لم تُبنَ المصفوفة» — **ولا يُحذف الإطار عند غيابه.**
#: ⚠️ حذفُه يُقرأ سكوتاً، والسكوتُ في موضع فحصٍ يُقرأ سلامة.
CLAIMS_NOT_BUILT = (
    "لم تُبنَ مصفوفة الطلبات والدفوع: لا حملَ وارد في الطلب. "
    "والطلبات والدفوع يُدخلها المحامي — والمنصّة لا تخترعها. "
    "وغيابُ المصفوفة ليس سلامة: لم يُفحَص شيء."
)


def _claims_frame(
    draft: str,
    payload,
    ledger,
    case_frame,
) -> dict:
    """
    إطار `claims`: مصفوفة الطلبات والدفوع، بأخطائها واقتراحاتها.

    ⚠️ **ولا كائن مُنمَّط هنا.** الإطار يُسلسل إلى JSON للبثّ عبر SSE،
    ووضع كائن في مفتاح أسقط أربعة اختبارات مرّة — أحدها اسمه
    ``test_the_frame_is_json_serializable``. فالحقول نصّية محضة،
    على نمط ``_revision_frame``.

    ⚠️ **ومخالفة المرحلة خطأ لا ملاحظة.** `validate_for_stage` موجودة لأن
    الاستئناف يطعن في الحكم أو الإجراء، والنقض في القانون، **والطعن في
    تقدير الدليل غير مقبول في النقض.**

    ⚠️ **والدفوع الجاهزة اقتراحٌ لا مصفوفة.** دفاعٌ بلا وقائع يسقط من أول
    جولة **ويُسقط معه الدفوع السليمة**، فلا يدخل المصفوفة.
    """
    if payload is None:
        return {
            "built": False,
            "message": CLAIMS_NOT_BUILT,
            "summary": {},
            "errors": [],
            "notices": [],
            "stage": None,
            "checked_sources": [],
        }

    try:
        matrix = _matrix_from_payload(payload)
        stage = matrix.stage
        if stage is None and case_frame:
            stage = case_frame.get("stage")

        findings = ()
        checked = []
        if ledger is not None:
            findings = findings + tuple(
                claims_module.cross_check_facts(matrix, ledger)
            )
            checked.append("facts")
        if draft.strip():
            findings = findings + tuple(
                claims_module.unanswered(matrix, draft)
            )
            checked.append("draft")
        if stage is not None:
            violations = tuple(
                v
                for item in (tuple(matrix.claims) + tuple(matrix.defences))
                for v in claims_module.validate_for_stage(item, stage)
            )
            # ⚠️ **والمخالفة تُرفع إلى «خطأ»** — وهي `Finding` بمعنى الوحدة،
            # فتُحوَّل إلى حقول نصّية هنا لا كائن.
            findings = findings + tuple(
                claims_module.Finding(
                    code=claims_module.CODE_STAGE_GROUND,
                    severity=claims_module.SEVERITY_ERROR,
                    message=v.message,
                    item_key=v.item_key,
                    kind=v.kind,
                    note=v.note,
                )
                for v in violations
            )
            checked.append("stage")

        suggestions = (
            claims_module.suggested_only(matrix, stage) if stage else ()
        )
        summary = claims_module.summarize(
            matrix,
            findings,
            ledger=ledger,
            draft=draft.strip(),
            stage=stage,
            suggestions=suggestions,
        )
    except Exception as exc:  # noqa: BLE001 — الفشل يُعلَن ولا يُبتلع
        print(f"\n[Claims] ⚠️ تعذّر بناء المصفوفة: {type(exc).__name__}: {exc}")
        return {
            "built": False,
            "message": (
                f"تعذّر بناء المصفوفة: {type(exc).__name__}. "
                "وغيابُ المصفوفة ليس سلامة."
            ),
            "summary": {},
            "errors": [],
            "notices": [],
            "stage": None,
            "checked_sources": [],
        }

    def _flat(f):
        return {
            "code": f.code,
            "severity": f.severity,
            "message": f.message,
            "item_key": f.item_key,
            "kind": f.kind,
            "note": f.note,
        }

    return {
        "built": True,
        "message": "",
        "summary": summary,
        "errors": [_flat(f) for f in findings
                   if f.severity == claims_module.SEVERITY_ERROR],
        "notices": [_flat(f) for f in findings
                    if f.severity != claims_module.SEVERITY_ERROR],
        "stage": stage.value if hasattr(stage, "value") else stage,
        "checked_sources": checked,
    }



# ==============================================================================
# حمل المصفوفة — يُبنى من الطلب، ويُرفض فاسدُه قبل أي نداء نموذج
# ==============================================================================

#: محاور النزاع المُعلَنة في الوحدة — وكلُّ محور خارجها يُردّ.
_AXES = {a.value for a in claims_module.DisputeAxis}


def _axis(name):
    """يحوّل نصّاً إلى ``DisputeAxis``، أو يرفع برسالة الوحدة."""
    key = claims_module.normalize(name or "")
    for axis in claims_module.DisputeAxis:
        if axis.value == key:
            return axis
    raise ValueError(
        f"محور نزاع غير معروف: «{name}». والمقبول: "
        + " · ".join(sorted(_AXES))
    )


def _item(raw, cls, label):
    """
    يبني ``Claim`` أو ``Defence`` من قاموس، **أو يرفع برسالة صريحة**.

    ⚠️ **والحمل الفاسد يُردّ ٤٠٠ قبل أن يُدفع ثمن التوليد** — وحملٌ يُسكت
    أسوأ من غيابه، **لأن المُتّصل يظنّه طُبِّق.**
    """
    if not isinstance(raw, dict):
        raise ValueError(f"كل {label} يجب أن يكون قاموساً.")
    key = claims_module.normalize(raw.get("key") or "")
    if not key:
        raise ValueError(f"{label} بلا مفتاح. والمفتاح هو ما يُربط به الدفع والطلب.")
    statement = (raw.get("label") or "").strip()
    if not statement:
        raise ValueError(f"{label} «{key}» بلا نصّ. والنصّ هو ما يُقرأ في المصفوفة.")

    def _tokens(field):
        value = raw.get(field)
        if value is None:
            return ()
        if isinstance(value, str):
            return (value.strip(),) if value.strip() else ()
        if isinstance(value, (list, tuple)):
            return tuple(str(v).strip() for v in value if str(v).strip())
        raise ValueError(f"{label} «{key}»: الحقل «{field}» يجب أن يكون نصّاً أو قائمة.")

    axes = tuple(_axis(a) for a in _tokens("axes_in_dispute"))

    if cls is claims_module.Defence:
        return cls(
            key=key,
            label=statement,
            claimed_by=raw.get("claimed_by") or "",
            elements=_tokens("elements"),
            supporting_facts=_tokens("supporting_facts"),
            opposing_facts=_tokens("opposing_facts"),
            evidence=_tokens("evidence"),
            axes_in_dispute=axes,
            burden=raw.get("burden") or None,
            response=raw.get("response") or "",
            outcome_sought=raw.get("outcome_sought") or "",
            documents_required=_tokens("documents_required"),
            is_procedural=bool(raw.get("is_procedural")),
        )
    return cls(
        key=key,
        label=statement,
        claimed_by=raw.get("claimed_by") or "",
        elements=_tokens("elements"),
        supporting_facts=_tokens("supporting_facts"),
        opposing_facts=_tokens("opposing_facts"),
        evidence=_tokens("evidence"),
        axes_in_dispute=axes,
        burden=raw.get("burden") or None,
        response=raw.get("response") or "",
        outcome_sought=raw.get("outcome_sought") or "",
        documents_required=_tokens("documents_required"),
    )


def _matrix_from_payload(payload):
    """
    يبني ``ClaimMatrix`` من حمل الطلب.

    ⚠️ **وتُنادى مرّة عند رأس النقطة قبل أي نداء نموذج**، فالفاسد يُردّ ٤٠٠
    **قبل** أن يُدفع ثمن التوليد. وهذا هو موضع التحقّق، **لا داخل المولّد.**

    ⚠️ **والمرحلة ``None`` مقبولة** — فمصفوفةٌ بلا مرحلة تُبنى، **ويُعلَن أن
    فحص المرحلة لم يجرِ** — **وهو خير من ادّعاء انطباق بلا مرحلة.**
    """
    if payload is None:
        return None
    if not isinstance(payload, dict):
        raise ValueError("حمل المصفوفة يجب أن يكون كائناً.")

    claims_raw = payload.get("claims") or ()
    defences_raw = payload.get("defences") or ()
    if not isinstance(claims_raw, (list, tuple)) or not isinstance(
        defences_raw, (list, tuple)
    ):
        raise ValueError("«claims» و«defences» يجب أن يكونا قائمتَين.")

    if not claims_raw and not defences_raw:
        raise ValueError(
            "حمل المصفوفة بلا طلبات ولا دفوع. والمنصّة لا تخترعها: "
            "الطلبات والدفوع يُدخلها المحامي."
        )

    stage = None
    if payload.get("stage"):
        for candidate in claims_module.Stage:
            if candidate.value == claims_module.normalize(payload["stage"]):
                stage = candidate
                break
        if stage is None:
            raise ValueError(
                f"مرحلة غير معروفة: «{payload['stage']}». والمقبول: "
                + " · ".join(s.value for s in claims_module.Stage)
            )

    our_party = None
    if payload.get("our_party"):
        for candidate in claims_module.Party:
            if candidate.value == claims_module.normalize(payload["our_party"]):
                our_party = candidate
                break
        if our_party is None:
            raise ValueError(
                f"صفة غير معروفة: «{payload['our_party']}». والمقبول: "
                + " · ".join(p.value for p in claims_module.Party)
            )

    return claims_module.ClaimMatrix(
        claims=tuple(
            _item(raw, claims_module.Claim, "طلب") for raw in claims_raw
        ),
        defences=tuple(
            _item(raw, claims_module.Defence, "دفاع") for raw in defences_raw
        ),
        stage=stage,
        our_party=our_party,
    )
