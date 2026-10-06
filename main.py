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
    data: {"type": "stage", "message": "..."}    مرحلة جارية
    data: {"type": "done",  "document": "..."}   المستند النهائي
    data: {"type": "error", "message": "..."}    فشل

سجلّ التغييرات عن النسخة السابقة:
  * أُضيف POST /generate مع بثّ SSE حقيقي — كان مُعلَناً في الـ commit ولكنه غائب.
  * الذاكرة لم تعد متغيّراً عامّاً مشتركاً بين كل المستخدمين؛ صارت لكل جلسة.
  * أُضيفت أداة التشريعات (search_uae_legislation) إلى موجّه التوجيه — كانت
    مُسقطة، فكان التطبيق عاجزاً عن الاستشهاد بالسند القانوني.
  * أُضيف CORS قابل للضبط من متغيّرات البيئة.
  * حُذف server.py لأنه كان نسخة مكررة حرفياً من هذا الملف.
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
from typing import Any, AsyncIterator, Optional

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from citations import (
    parse_citations,
    strip_citations_block,
    unbacked_article_refs,
    verify_citations,
)
from legal_agent import SYSTEM_PROMPT_CITED, agent, collect_evidence, get_supabase, llm
from language_audit import audit_language
from language_audit import summarize as summarize_language_audit
from review import build_review_prompt, parse_review
from review import summarize as summarize_review
from revisions import RevisionRejected, build_revision, summarize

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


class GenerateRequest(BaseModel):
    prompt: str = Field(..., min_length=1, description="الوقائع والمعطيات")
    doc_type: str = Field("مستند قانوني", description="نوع المستند المطلوب")
    session_id: Optional[str] = None


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


def _build_messages(prompt: str, doc_type: Optional[str] = None) -> list:
    """يبني الرسائل، مع حقن نوع المستند وتلميح الأداة المناسبة."""
    user_content = prompt
    if doc_type:
        hint = DOC_TYPE_TOOL_HINT.get(doc_type.strip())
        hint_line = f"\n(الأداة الأنسب لهذا النوع: {hint})" if hint else ""
        user_content = (
            f"نوع المستند المطلوب: {doc_type}{hint_line}\n\n"
            f"الوقائع والمعطيات:\n{prompt}"
        )
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
    }
    return clean, report


def _stream_agent(messages: list):
    """
    يولّد أحداث الوكيل خطوة بخطوة.

    يُنتج أزواجاً (kind, payload):
        ("stage", "نص المرحلة")   عند بدء استدعاء أداة أو انتهائه
        ("citations", {...})      تقرير التحقّق من الأسانيد
        ("final", "نص المستند")   عند اكتمال الصياغة — بلا كتلة الأسانيد

    ⚠️ جامع الأدلة يُفتح **هنا** لا في المستدعي. السبب: هذه الدالة تُنفَّذ داخل
    الخيط العامل حيث تجري الأدوات، و`ContextVar` معزول لكل خيط. ولو فُتح الجامع
    في حلقة الأحداث لما رآه الخيط العامل أصلاً، فتُسجَّل الأدلّة في سياق فارغ
    ويصير التحقّق بلا معنى.
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
        clean, report = _verify_round(final_text, evidence)
        yield ("citations", report)

        # سيبويه المُكشّر — تدقيق لغوي حتمي بلا نموذج (انظر language_audit.py)
        yield ("stage", StageEvent(KEY_POLISH, STAGE_POLISHING))
        yield ("language", summarize_language_audit(audit_language(clean)))

        # المفتش ثُغرة — القراءة الثانية. وقبل الختم، فلا يُختم إلا بعد مراجعة.
        yield ("stage", StageEvent(KEY_REVIEW, STAGE_REVIEWING))
        yield ("review", _review_round(_brief_from(messages), clean, _evidence_text(evidence)))

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


def _review_round(brief: str, draft: str, evidence_text: str) -> dict:
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
    """
    if not draft.strip():
        return {}

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
        }

    report = summarize_review(outcome.findings, outcome.dropped)
    report["failed"] = False
    print(f"\n[Review] 🛡️ اعتراضات: {report['error_count']} · ملاحظات: {report['notice_count']}")
    return report


def _run_agent_collect(messages: list) -> tuple[str, dict, dict]:
    """ينفّذ الوكيل ويُرجع (النصّ, تقرير الأسانيد, تقرير الصياغة) — لـ /chat."""
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


async def _sse_generator(messages: list) -> AsyncIterator[str]:
    """
    يحوّل مُولِّد الوكيل المتزامن (blocking) إلى بثّ غير متزامن.

    agent.stream يستدعي الشبكة ويحجب حلقة الأحداث، لذا ننفّذه في خيط منفصل
    ونمرّر الأحداث إلى طابور asyncio عبر call_soon_threadsafe.
    """
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue()
    sentinel = object()

    def emit(item: dict) -> None:
        loop.call_soon_threadsafe(queue.put_nowait, item)

    def worker() -> None:
        try:
            for kind, payload in _stream_agent(messages):
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
    """
    messages = _build_messages(req.prompt, req.doc_type)
    return StreamingResponse(
        _sse_generator(messages),
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
