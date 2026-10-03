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
import threading
from collections import OrderedDict
from typing import Any, AsyncIterator, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from legal_agent import agent

load_dotenv()

# ==============================================================================
# ١. الإعداد
# ==============================================================================

MAX_HISTORY_TURNS = int(os.environ.get("MAX_HISTORY_TURNS", "6"))
MAX_SESSIONS = 100  # حد أعلى لعدد الجلسات المحفوظة في الذاكرة

# حد أقصى لعدد خطوات الوكيل (chatbot → tools → chatbot ...) لمنع الحلقات اللانهائية
AGENT_RECURSION_LIMIT = 12

# ------------------------------------------------------------------------------
# موجّه التوجيه — يشمل الأدوات الخمس كلها، ومنها التشريعات.
# البند الرابع (السند القانوني) هو الفرق الجوهري عن النسخة السابقة.
# ------------------------------------------------------------------------------
SYSTEM_PROMPT = (
    "أنت مستشار قانوني إماراتي خبير. مهمتك صياغة المستندات بناءً على أسلوب "
    "المستخدم المخزن في قواعد البيانات.\n"
    "قواعد التوجيه:\n"
    "1. مذكرات ولوائح ومحاكم -> 'search_drafting_style'.\n"
    "2. عقود واتفاقيات وملاحق -> 'search_contract_clauses'.\n"
    "3. إنذارات وإشعارات -> 'search_legal_notices'.\n"
    "4. وكالات وتوكيلات وتفويض -> 'search_poa_clauses'.\n"
    "5. السند القانوني والتشريعات والأحكام -> 'search_uae_legislation'. "
    "استدعِ هذه الأداة أيضاً كلما احتجت مادة قانونية تستند إليها.\n"
    "التزم بأداة أسلوب واحدة تتناسب مع نوع الطلب، مع أداة التشريعات عند الحاجة. "
    "لا تستدعِ الأداة نفسها مرتين.\n"
    "اكتب المخرج النهائي مباشرة مقلداً أسلوب المستخدم، دون مقدمات أو تعليقات "
    "جانبية أو شرح لما تفعله. إن لم تجد سنداً في السياق المسترجع، اكتب المستند "
    "واعتمد على القواعد القانونية الإماراتية العامة دون تأليف نصوص مواد."
)

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
        history = [SystemMessage(content=SYSTEM_PROMPT)]
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
    return [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=user_content)]


def _stream_agent(messages: list):
    """
    يولّد أحداث الوكيل خطوة بخطوة.

    يُنتج أزواجاً (kind, payload):
        ("stage", "نص المرحلة")   عند بدء استدعاء أداة أو انتهائه
        ("final", "نص المستند")   عند اكتمال الصياغة
    """
    yield ("stage", STAGE_ANALYSING)

    config = {"recursion_limit": AGENT_RECURSION_LIMIT}
    final_text = ""
    invoked_any_tool = False

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
                        yield ("stage", label)
                    continue
                text = _extract_text(last)
                if text:
                    final_text = text

            elif node == "tools":
                invoked_any_tool = True
                yield ("stage", STAGE_EVIDENCE_FOUND)

    if invoked_any_tool and final_text:
        yield ("stage", STAGE_DRAFTING)
    yield ("final", final_text)


def _run_agent_collect(messages: list) -> str:
    """ينفّذ الوكيل ويُرجع النص النهائي فقط — يُستخدم في /chat."""
    final_text = ""
    for kind, payload in _stream_agent(messages):
        if kind == "final":
            final_text = payload
    return final_text


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
                    emit({"type": "stage", "message": payload})
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


@app.post("/generate")
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


@app.post("/chat")
async def chat_endpoint(req: ChatRequest):
    """محادثة بردّ JSON كامل — متوافق مع الاستخدام السابق، مع عزل الجلسات."""
    session_id = req.session_id or "default"
    history = _get_history(session_id)
    history.append(HumanMessage(content=req.prompt))

    try:
        answer = await asyncio.to_thread(_run_agent_collect, _trim_history(history))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"{type(exc).__name__}: {exc}")

    if not answer:
        answer = (
            "لم أتمكّن من إنتاج ردّ. تحقّق من صحة مفاتيح الـ API ومن وجود "
            "بيانات مستوعَبة في قاعدة المعرفة."
        )

    history.append(AIMessage(content=answer))
    return {"response": answer, "session_id": session_id}


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
<br>
<button id="go" onclick="run()">ابدأ الصياغة</button>

<div id="stage"></div>
<div id="err"></div>
<div id="doc"></div>

<script>
async function run() {
  const go = document.getElementById('go');
  const stage = document.getElementById('stage');
  const err = document.getElementById('err');
  const doc = document.getElementById('doc');

  go.disabled = true;
  err.textContent = '';
  doc.style.display = 'none';
  doc.textContent = '';
  stage.textContent = 'جاري الإرسال...';

  try {
    const res = await fetch('/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
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
