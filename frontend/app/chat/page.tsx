"use client";

/**
 * المحادثة القانونية — سؤالٌ يُسأل، وجوابٌ يُعرَض **بما له من سند**.
 * ============================================================================
 * ⚠️ ما يبنيه هذا الملف، ولماذا بهذا الترتيب:
 *
 *   • **الشريط العلوي**: عنوان الصفحة وأثر الجلسة الجارية. الجلسة معرّف
 *     تُحفظ به المحاورة عند الخادم (`_get_history` في main.py)، فمن أعاد فتح
 *     الصفحة تابع المحاورة نفسها ولم يبدأ من الصفر.
 *
 *   • **السؤال يُكتب في شريط مثبَّت أسفل الشاشة** — كما في كل محادثة، ولأنّ
 *     السؤال التالي هو الفعل المتوقَّع دائماً فلا يجوز أن يُطلب بالتمرير إلى
 *     أعلى. **ولهذا الموضع سبب ثانٍ**: حال الانتظار تبدو في الشريط نفسه الذي
 *     كتب فيه السؤال (الحقل يُعطَّل، والزرّ يصير «يتوقّف»، وسطر الحال تحته)،
 *     فلا يبدو الحقل خاملاً والخادم يعمل.
 *
 *   • **والجواب وما استُند إليه في `components/chat-answer.tsx`** — القاعدة
 *     التي تحكم الفرق بين مسنود وبلا سند هناك في موضع واحد، والملف هنا للحالة
 *     والطلب لا للحكم.
 *
 * ⚠️ **ولا بثّ هنا**: `/chat` يُرجع ردّاً واحداً كاملاً (بخلاف `/generate`)،
 *    ولهذا لا مراحل تُعرَض ولا نسبة تقدّم — **حالٌ واحدة صادقة** تقول إنّ
 *    المنصّة تبحث في المكتبة. واختلاق تقدّم في نداءٍ لا يُبلغ عن تقدّمه كذبٌ
 *    صغير في صفحةٍ كل قيمتها الصدق.
 *
 * ⚠️ **والطلبات كلها عبر `/api`** — الوسيط في `app/api/[...path]/route.ts`
 *    وحده يعرف `BACKEND_URL` ويضيف `API_TOKEN` على الخادم. ولا `NEXT_PUBLIC_`
 *    هنا ولا في أي موضع: كل قيمة حاملة لها تُحزَّم في جافاسكربت المتصفح.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { AlertTriangle, Loader2, Send, Square } from "lucide-react";
import { EngravedIcon } from "@/components/engraved-icon";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { DataNotice } from "@/components/data-notice";
import { ChatAnswerView, readAnswer, type ChatAnswer } from "@/components/chat-answer";

/** الوسيط على نفس الأصل — انظر `app/api/[...path]/route.ts`. */
const API_URL = "/api";

/**
 * سقف الانتظار — **نفس رقم مساحة الصياغة لا رقمٌ أقصر مُخترع هنا**.
 *
 * ⚠️ وسبب رفع مساحة الصياغة له إلى عشر دقائق موثَّق هناك (`app/workspace/page.tsx`):
 *    كانت ثلاث دقائق فانتهت **قبل أن يُتمّ الخادم عمله**، فقُرئ عملٌ ناجح
 *    فاشلاً وأُعيد النداء. وسؤال المحادثة يمرّ بالمسار نفسه من الاسترجاع
 *    والصياغة والتحقّق، فلا معنى لمهلة أقصر منه.
 */
const CHAT_TIMEOUT_MS = 600_000;

/**
 * مفتاح الجلسة — **مؤطَّر باسم الصفحة** كي لا يتصادم مع تفضيلات غيرها من
 * الصفحات (القاعدة نفسها في `library.view`).
 *
 * ⚠️ وهو **ليس سرّاً**: معرّف جلسة عشوائي يعيش في متصفّح صاحبه ويُرسل إلى
 *    الخادم ليصل الجواب بالسياق. ولو كان سرّاً لكان موضعه `.env.local` بلا
 *    بادئة `NEXT_PUBLIC_` — ولا يُخزَّن سرٌّ في `localStorage` أصلاً.
 */
const SESSION_KEY = "chat.session_id";

type Turn = {
  id: string;
  question: string;
  /** `null` ما دام السؤال بلا جواب بعد. */
  answer: ChatAnswer | null;
};

/** معرّف جلسة عشوائي — `crypto.randomUUID` كما في مساحة الصياغة، وباحتياط. */
function newSessionId(): string {
  return typeof crypto !== "undefined" && typeof crypto.randomUUID === "function"
    ? crypto.randomUUID()
    : `s-${Date.now()}`;
}

/** معرّف دورٍ داخل الشاشة — مفتاح React لا علاقة له بمعرّف الجلسة عند الخادم. */
function newTurnId(): string {
  return typeof crypto !== "undefined" && typeof crypto.randomUUID === "function"
    ? crypto.randomUUID()
    : `t-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

/** خطأ الإلغاء ليس فشلاً — لا يُعرض للمستخدم (وهو ما تفعله المكتبة أيضاً). */
function isAbort(error: unknown): boolean {
  return error instanceof DOMException && error.name === "AbortError";
}

/**
 * قراءة رسالة الخطأ.
 *
 * ⚠️ وردّ الوسيط عند تعذّر الوصول إلى FastAPI **نصٌّ عربي لا JSON** — فيُقرأ
 *    النصّ ويُفحص، ولا يُفترض JSON. و`detail` من الخادم يُعرض حرفياً كما هو
 *    (القاعدة نفسها في `library/page.tsx`).
 */
async function readError(response: Response): Promise<string> {
  const raw = await response.text();
  try {
    const parsed: unknown = JSON.parse(raw);
    if (
      typeof parsed === "object" &&
      parsed !== null &&
      typeof (parsed as { detail?: unknown }).detail === "string" &&
      (parsed as { detail: string }).detail
    ) {
      return (parsed as { detail: string }).detail;
    }
  } catch {
    /* ليس JSON — يُعرض النصّ كما هو */
  }
  return raw.trim().slice(0, 500) || `HTTP ${response.status}`;
}

export default function Chat() {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  /** الحال المعروضة أثناء الانتظار — تُبنى من مراحل النداء لا من مؤقّت وهمي. */
  const [notice, setNotice] = useState("");

  /**
   * ⚠️ **معرّف الجلسة في `useRef` لا في `useState`.**
   *
   * لأنّه لا يُرسم: تغيّره لا يستدعي إعادة عرض، وإبقاؤه في الحالة يجعل كل
   * تحديث له إعادة رسم لا معنى لها. وهو **يُقرأ من `localStorage` بعد التركيب
   * لا قبله**: القراءة في `useState` الأولي تُنتج اختلافاً بين ما رسمه الخادم
   * وما يرسمه المتصفّح — وهو خطأ الترطيب الذي يُسقط الشجرة كلها.
   */
  const sessionRef = useRef("");

  /** إلغاء الطلب الجاري — يُستعمل للخروج من الصفحة ولزرّ التوقّف معاً. */
  const abortRef = useRef<AbortController | null>(null);

  const bottomRef = useRef<HTMLDivElement | null>(null);

  /* استرجاع جلسة سابقة — بعد التركيب وحده (انظر التعليق على `sessionRef`). */
  useEffect(() => {
    try {
      const stored = window.localStorage.getItem(SESSION_KEY);
      if (stored) sessionRef.current = stored;
    } catch {
      /* التخزين قد يكون معطّلاً (وضع خاص/سياسة) — تُبدأ جلسة جديدة بلا خطأ */
    }
  }, []);

  /**
   * ⚠️ **وإلغاء الطلب عند الخروج من الصفحة ليس تجميلاً**: الطلب يبقى دقائق،
   *    وتركه حيّاً بعد الانتقال يُبقي الاتصال ويُربك الحالة عند العودة.
   *    والإلغاء هنا لا يُلغي العمل عند الخادم (لا سبيل لذلك)، لكنه يُنهي
   *    الانتظار عندنا.
   */
  useEffect(() => {
    return () => abortRef.current?.abort();
  }, []);

  /* التمرير إلى آخر دور — عند وصول جواب وعند بدء سؤال جديد. */
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ block: "end" });
  }, [turns.length, sending]);

  /**
   * إرسال سؤال.
   *
   * ⚠️ **والسؤال يُقيَّد بالجلسة لا بالسؤال وحده**: الخادم يحفظ المحاورة في
   *    `_sessions` بمفتاح `session_id`، وإرسال المعرّف نفسه هو وحده ما يجعل
   *    السؤال الثاني يُقرأ على أنه **تكملة** لا سؤالاً مبتدئاً بلا سياق.
   *
   * ⚠️ **والمعرّف يُخزَّن بعد نجاح أول ردّ** لا قبله: جلسةٌ تُكتب في التخزين
   *    ثم يفشل الطلب تبقى معلّقة بلا محاورة، فيبدأ المستخدم من سياق لا وجود له.
   */
  const send = useCallback(async () => {
    const question = draft.trim();
    if (!question || sending) return;

    const turnId = newTurnId();
    setTurns((current) => [...current, { id: turnId, question, answer: null }]);
    setDraft("");
    setError("");
    setSending(true);
    setNotice("أبحث في المكتبة وصياغة الجواب...");

    const controller = new AbortController();
    abortRef.current = controller;
    let timedOut = false;
    const timeoutId = window.setTimeout(() => {
      timedOut = true;
      controller.abort();
    }, CHAT_TIMEOUT_MS);

    try {
      const response = await fetch(`${API_URL}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          prompt: question,
          /**
           * ⚠️ والفراغ يعني «جلسة جديدة»: الخادم يفهم `None` فيولّد `"default"`
           *    — وهي جلسة **مشتركة بين كل من لم يُرسل معرّفاً**، فيرى أحدهم
           *    محاورة غيره. ولهذا يُولَّد المعرّف هنا قبل أول إرسال ولا يُترك
           *    للخادم.
           */
          session_id: sessionRef.current || (sessionRef.current = newSessionId()),
        }),
        signal: controller.signal,
        cache: "no-store",
      });

      if (!response.ok) throw new Error(await readError(response));

      const payload: unknown = await response.json();
      const answer = readAnswer(payload);

      /* الجلسة الفعلية كما أعادها الخادم — قد تكون هي ما أرسلناه، وقد تكون
         معرّفاً أرسله هو؛ وفي الحالين هي التي تُكمل المحاورة. */
      const returned =
        typeof payload === "object" &&
        payload !== null &&
        typeof (payload as { session_id?: unknown }).session_id === "string"
          ? (payload as { session_id: string }).session_id
          : "";
      if (returned) sessionRef.current = returned;

      try {
        if (sessionRef.current) {
          window.localStorage.setItem(SESSION_KEY, sessionRef.current);
        }
      } catch {
        /* ⚠️ فشل الحفظ **لا يُترجم** إلى فشل الجواب: الجواب وصل في هذه
           الجلسة فعلاً، وإظهار خطأ هنا يقول للمستخدم إنّ شيئاً لم يحدث. */
      }

      setTurns((current) =>
        current.map((turn) => (turn.id === turnId ? { ...turn, answer } : turn))
      );
      setNotice("");
    } catch (e) {
      if (isAbort(e)) {
        /**
         * ⚠️ **والتوقّف يُقال سببُه**: مهلة أم إلغاء المستخدم — وهما حالان
         *    مختلفان، وترك السؤال بلا جواب صامتاً يُقرأ خطأً في المنصّة.
         */
        if (timedOut) {
          setError(
            "انتهت مدة الانتظار قبل أن يصل الجواب. الخادم قد يكون ما زال يعمل — أعد الإرسال أو اختصر السؤال."
          );
        } else {
          setError("أُوقف الطلب قبل وصول الجواب. لم يُحفظ في المحاورة شيء.");
        }
        /* السؤال بلا جواب: يُرفع من الشاشة بدل أن يُترك معلّقاً بلا نهاية. */
        setTurns((current) => current.filter((turn) => turn.id !== turnId));
        setNotice("");
      } else {
        setError(e instanceof Error ? e.message : "تعذّر الوصول إلى المنصّة.");
        setNotice("");
        setTurns((current) => current.filter((turn) => turn.id !== turnId));
      }
    } finally {
      window.clearTimeout(timeoutId);
      if (abortRef.current === controller) abortRef.current = null;
      setSending(false);
    }
  }, [draft, sending]);

  /** كتابة جديدة ثم إرسال — والجلسة هي نفسها، فالمحاورة تستمرّ. */
  const onKeyDown = useCallback(
    (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
      /* ⚠️ Enter يُرسل وShift+Enter يُنزل سطراً: سؤال المحامي قد يكون فقرة،
         وإرساله عند كل سطر يقطعه. والعكس (الإرسال بـCtrl) غير معتاد عربياً. */
      if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        void send();
      }
    },
    [send]
  );

  /** بدء محاورة جديدة — لا يمسح شيئاً من الأرشيف، ويسقط السياق وحده. */
  const startNewSession = useCallback(() => {
    abortRef.current?.abort();
    sessionRef.current = "";
    try {
      window.localStorage.removeItem(SESSION_KEY);
    } catch {
      /* الحفظ قد يكون معطّلاً — والبدء الجديد يحصل في هذه الجلسة على أي حال */
    }
    setTurns([]);
    setError("");
    setNotice("");
  }, []);

  const hasTurns = turns.length > 0;

  return (
    <div className="space-y-6">
      {/* ── ١ · الترويسة وحال الجلسة ───────────────────────────────────── */}
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="font-heading text-3xl tracking-tight text-slate-100">
            المحادثة القانونية
          </h1>
          <p className="mt-1 text-sm leading-relaxed text-slate-400">
            اسأل سؤالك، ويأتي الجواب ومعه ما استُند إليه من الأرشيف: اسم المستند
            والنصّ المنقول منه حرفياً. وما لا سند له يُقال عنه ذلك صراحةً.
          </p>
        </div>

        {/* زرّ المحاورة الجديدة — يظهر حين توجد محاورة، فلا زرّ لا يفعل شيئاً. */}
        {hasTurns && (
          <button
            type="button"
            onClick={startNewSession}
            title="ابدأ محاورة جديدة بسياق فارغ"
            className="border border-slate-800 px-4 py-2 text-xs text-slate-300 transition-colors hover:border-amber-500/40 hover:text-amber-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-500/40"
          >
            محاورة جديدة
          </button>
        )}
      </header>

      {/* ── ٢ · المحاورة ──────────────────────────────────────────────── */}
      {!hasTurns && !error && (
        <Card className="gap-4 border border-slate-800 bg-slate-900 p-8 ring-0">
          <EngravedIcon name="quill-ink" className="size-7 text-amber-500" />
          <p className="font-heading text-xl text-slate-100">لا محاورة بعد.</p>
          <p className="max-w-2xl text-sm leading-relaxed text-slate-400">
            اكتب سؤالك في الشريط أسفل الشاشة. يعمل الفريق على الأرشيف المستوعب
            وحده: ما وُجد فيه يُنقل نصّه ويُعرض مع اسم مستنده، وما لم يوجد يُقال
            إنّه من معرفة النموذج العامة ولا يُعتمد مرجعاً.
          </p>
        </Card>
      )}

      {turns.map((turn) => (
        <section key={turn.id} className="space-y-4">
          {/* السؤال — كتلة واحدة تُقرأ كمدخل في ملف، لا فقاعة محادثة */}
          <div className="border border-slate-800 bg-slate-900/60 p-4">
            <p className="text-[10px] tracking-[0.2em] text-slate-600">السؤال</p>
            <p className="mt-2 whitespace-pre-line break-words text-sm leading-relaxed text-slate-100">
              {turn.question}
            </p>
          </div>

          {turn.answer ? (
            <ChatAnswerView answer={turn.answer} />
          ) : (
            <div className="border border-slate-800 bg-slate-900 p-4">
              <p className="flex items-center gap-2 text-xs text-slate-400">
                <Loader2 className="size-3.5 animate-spin text-amber-500" aria-hidden="true" />
                {notice || "في الانتظار..."}
              </p>
            </div>
          )}
        </section>
      ))}

      {error && (
        <DataNotice
          tone="error"
          title="تعذّر إتمام الطلب"
          detail={error}
        />
      )}

      <div ref={bottomRef} />

      {/* ── ٣ · شريط السؤال — مثبَّت أسفل الشاشة، وهو حال الانتظار نفسه ── */}
      <div className="sticky bottom-0 -mx-8 border-t border-slate-800 bg-slate-950 px-8 py-4">
        {/*
          ⚠️ **والحقل يُعطَّل أثناء الانتظار** — لا يبقى قابلاً للكتابة فوق
          سؤالٍ لم يُجب عنه. وهذا هو ما يمنع أن يبدو الإدخال خاملاً والخادم
          يعمل: التعطيل ظاهر، والزرّ يعلن «إيقاف»، والسطر تحته يقول ما يجري.
        */}
        <Textarea
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={onKeyDown}
          disabled={sending}
          rows={3}
          aria-label="اكتب سؤالك القانوني"
          placeholder="اكتب سؤالك... (Enter للإرسال · Shift+Enter لسطر جديد)"
          className="min-h-[84px] resize-none border-slate-800 bg-slate-900 text-slate-100 focus-visible:border-amber-500/40"
        />

        <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
          <p
            role="status"
            className={`flex items-center gap-2 text-xs ${
              sending ? "text-amber-500" : "text-slate-500"
            }`}
          >
            {sending ? (
              <>
                <Loader2 className="size-3.5 animate-spin" aria-hidden="true" />
                {notice || "المنصّة تعمل على سؤالك..."}
                <span className="text-slate-500">
                  — الطلب قد يستغرق دقائق، والشاشة ستبقى على هذه الحال حتى يصل.
                </span>
              </>
            ) : (
              <>
                <AlertTriangle className="size-3.5 text-slate-600" aria-hidden="true" />
                الجواب يُعرض بما ثبت له من سند فقط؛ وما لا سند له يُوسم.
              </>
            )}
          </p>

          {sending ? (
            <Button
              type="button"
              variant="outline"
              size="lg"
              onClick={() => abortRef.current?.abort()}
              className="border-slate-700 px-5 text-slate-200"
            >
              <Square className="size-3.5" aria-hidden="true" />
              إيقاف الانتظار
            </Button>
          ) : (
            <Button
              type="button"
              size="lg"
              onClick={() => void send()}
              disabled={!draft.trim()}
              className="bg-amber-600 px-6 text-white hover:bg-amber-700"
            >
              <Send className="size-4" aria-hidden="true" />
              أرسل السؤال
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
