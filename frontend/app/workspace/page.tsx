"use client";

import { useRef, useState } from "react";
import { motion, AnimatePresence } from "motion/react";
import {
  Send,
  FileText,
  Loader2,
  CheckCircle,
  Bot,
  Scale,
  AlertTriangle,
  ShieldCheck,
  ShieldAlert,
  Unlink,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";

// كل النداءات تمر عبر وسيط Next.js على /api — انظر app/api/[...path]/route.ts
//
// لماذا وسيط وليس عنوان الخادم مباشرة؟
//   ١) رمز المصادقة (API_TOKEN) يبقى على الخادم ولا يصل إلى المتصفح إطلاقاً.
//      لو وضعناه في متغيّر NEXT_PUBLIC_ لرآه أي زائر في مصدر الصفحة.
//   ٢) المتصفح يخاطب نفس الأصل، فتختفي مشكلة CORS كلياً.
//   ٣) عنوان الخادم الحقيقي لم يعد جزءاً من حزمة الواجهة.
const API_URL = "/api";

// مهلة قصوى لتوليد المستند (المستندات الطويلة تستغرق وقتاً)
const GENERATION_TIMEOUT_MS = 180_000;

type Status = "idle" | "processing" | "done" | "error";

/** سند أثبت الخادم أنه منقول حرفياً من الأرشيف. */
type VerifiedCitation = {
  ref: string;
  document_name: string;
  chunk_id: string;
  quoted_span: string;
  similarity: number | null;
};

/** سند رُفض، مع سبب مقروء بالعربية. */
type RejectedCitation = {
  ref: string;
  quoted_span: string;
  reason: string;
};

/** مادة ذُكرت في المتن ولم ترد في أي مقطع مسترجَع من الأرشيف. */
type UnbackedArticle = { surface: string; number: string };

/**
 * تقرير التحقّق الذي يبثّه الخادم مع كل مسودّة — انظر `_verify_round` في main.py.
 *
 * الخادم يتحقّق حتمياً أن كل سند منقول حرفياً من مقطع استُرجع فعلاً (انظر
 * citations.py)، ويُرسل النتيجة كي يراها المحامي قبل أن يعتمد المستند.
 */
type CitationsReport = {
  summary: string;
  has_evidence: boolean;
  evidence_count: number;
  has_citation_block: boolean;
  verified: VerifiedCitation[];
  rejected: RejectedCitation[];
  unbacked_articles: UnbackedArticle[];
  malformed_lines: string[];
};

type StreamEvent =
  | { type: "stage"; message: string }
  | { type: "citations"; report: CitationsReport }
  | { type: "done"; document: string }
  | { type: "error"; message: string };

/** ما يُرجعه `POST /revisions` بعد حفظ التصحيح. */
type RevisionSaveResult = {
  saved: boolean;
  edit_ratio: number;
  quality_band: string;
  word_count: number;
};

/**
 * ينظّف مخلفات Markdown من نص المستند المولَّد.
 *
 * الغرض دفاعي لا أساسي: الموجّه في legal_agent.py يمنع Markdown صراحةً، لكن
 * النماذج تخالفه أحياناً. وقد ظهر فعلاً في مستند مولَّد علامات حرفية:
 *     ** لائحة دعوى تجارية **      ### ** موضوع الدعوى: **
 * والسبب أن هذه الصفحة تعرض النص كما هو (نص عادي لا HTML)، والمستند يُنسخ إلى Word.
 *
 * الحذر في ما نزيله: النص العربي القانوني لا يستخدم # ولا > ولا ** استخداماً
 * شرعياً، فإزالتها آمنة. ولم نمسّ الشرطة المفردة (-) لأنها تظهر في التواريخ
 * والنطاقات الرقمية.
 */
function stripMarkdownArtifacts(text: string): string {
  return (
    text
      .split("\n")
      // وسم عنوان في بداية السطر: # ## ### ...
      .map((line) => line.replace(/^\s{0,3}#{1,6}\s*/, ""))
      // علامة اقتباس في بداية السطر: >
      .map((line) => line.replace(/^\s{0,3}>\s?/, ""))
      .join("\n")
      // خط أفقي (--- أو *** أو ___) — يصبح سطراً فارغاً فيصلح فاصلاً
      .replace(/^[ \t]*[-*_]{3,}[ \t]*$/gm, "")
      // التسميك والتعريف: ** و __
      .replace(/\*\*/g, "")
      .replace(/__/g, "")
      // إزالة الخط الأفقي تُبقي أسطراً فارغة متتالية — نطويها إلى فاصل واحد
      .replace(/\n{3,}/g, "\n\n")
      .trim()
  );
}

/**
 * لوحة الأسانيد — تُعرض بعد كل مسودة.
 *
 * الغرض أن يرى المحامي **قبل أن يعتمد** المستند: ما ثبت أنه منقول حرفياً من
 * أرشيفه، وما رُفض ولماذا، وما ذُكر من مواد بلا سند إطلاقاً.
 *
 * ⚠️ وكل نصّ من النموذج يمرّ كمحتوى React عادي، ولا `dangerouslySetInnerHTML`
 * في هذا الملف. السبب أن الاقتباسات تأتي من مخرج النموذج، وإدراجها كـ HTML
 * يجعلها قابلة للحقن.
 */
function CitationsPanel({ report }: { report: CitationsReport | null }) {
  if (!report) return null;

  const nothingVerified = !report.has_evidence;

  return (
    <div className="border-t border-slate-200 bg-slate-50 p-6 space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        {nothingVerified ? (
          <ShieldAlert className="w-5 h-5 text-red-600" />
        ) : (
          <ShieldCheck className="w-5 h-5 text-green-600" />
        )}
        <h3 className="font-bold text-slate-900">
          {nothingVerified ? "لا سند موثَّق" : "الأسانيد الموثَّقة"}
        </h3>
        <span className="text-sm text-slate-500">({report.summary})</span>
      </div>

      {nothingVerified && (
        <p className="text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg p-3 leading-relaxed">
          لم يثبت أن أي مادة في هذه المسودّة منقولة من أرشيفك. راجع كل استناد
          قانوني فيها قبل الاعتماد عليها.
        </p>
      )}

      {report.verified.map((c, i) => (
        <div
          key={`v-${i}`}
          className="rounded-lg border border-green-200 bg-white p-3 text-sm"
        >
          <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500 mb-1">
            <span className="font-mono font-bold text-green-700">[{c.ref}]</span>
            <span>{c.document_name}</span>
            {c.similarity != null && (
              <span className="text-slate-400">
                تشابه {c.similarity.toFixed(2)}
              </span>
            )}
          </div>
          <p className="text-slate-800 leading-relaxed" dir="auto">
            «{c.quoted_span}»
          </p>
        </div>
      ))}

      {report.rejected.length > 0 && (
        <div className="space-y-2">
          <h4 className="flex items-center gap-1 text-sm font-semibold text-red-700">
            <Unlink className="w-4 h-4" />
            أسانيد مرفوضة
          </h4>
          {report.rejected.map((c, i) => (
            <div
              key={`r-${i}`}
              className="rounded-lg border border-red-200 bg-white p-3 text-sm"
            >
              <div className="text-xs text-red-600 mb-1">
                <span className="font-mono font-bold">[{c.ref}]</span> {c.reason}
              </div>
              <p
                className="text-slate-700 leading-relaxed line-through decoration-red-300"
                dir="auto"
              >
                «{c.quoted_span}»
              </p>
            </div>
          ))}
        </div>
      )}

      {report.unbacked_articles.length > 0 && (
        <div className="rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm space-y-1">
          <div className="font-semibold text-amber-900">
            مواد مذكورة في المستند ولم ترد في أرشيفك
          </div>
          {report.unbacked_articles.map((a, i) => (
            <div key={`a-${i}`} className="text-amber-900" dir="auto">
              {a.surface}
            </div>
          ))}
        </div>
      )}

      {report.malformed_lines.length > 0 && (
        <div className="rounded-lg border border-slate-300 bg-white p-3 text-xs text-slate-600 space-y-1">
          <div className="font-semibold">أسطر أسانيد لم تُقرأ</div>
          {report.malformed_lines.map((line, i) => (
            <div key={`m-${i}`} dir="auto" className="font-mono">
              {line}
            </div>
          ))}
        </div>
      )}

      {report.evidence_count > 0 && (
        <p className="text-xs text-slate-400">
          استُرجع {report.evidence_count} مقطعاً من أرشيفك في هذه الجولة.
        </p>
      )}
    </div>
  );
}

/**
 * شريط حفظ التصحيح — المادة الخام لتقليد أسلوب المحامي.
 *
 * الفكرة: بعد أن يعدّل المحامي المسودّة (هنا أو في Word ثم يلصقها)، يحفظها
 * فيُخزَّن زوج (ما كتبه النموذج ← ما اعتمده المحامي) ويُقاس بفرق بسيط. وكل
 * تصحيح لا يُسجَّل يضيع، فيبقى الأسلوب في الموجّه تخميناً لا تعلّماً.
 *
 * ⚠️ والتصحيحات تُخزَّن **منفصلة تماماً** عن أرشيف الاسترجاع — انظر القسم ١٠
 * في schema.sql. السبب أن المسودّة المولَّدة قد تحوي مادة مؤلَّفة، ولو دخلت
 * الاسترجاع لعادت في جولة لاحقة كـ«سياق موثوق» فتصير الهلوسة حقيقة مؤرشفة.
 */
function RevisionBar({
  generatedText,
  docType,
  sessionId,
}: {
  generatedText: string;
  docType: string;
  sessionId: string;
}) {
  const [editing, setEditing] = useState(false);
  const [editedText, setEditedText] = useState("");
  const [state, setState] = useState<"idle" | "saving" | "saved" | "error">("idle");
  const [result, setResult] = useState<RevisionSaveResult | null>(null);
  const [error, setError] = useState("");

  const startEditing = () => {
    setEditedText(generatedText);
    setEditing(true);
    setState("idle");
    setError("");
  };

  const cancel = () => {
    setEditing(false);
    setState("idle");
    setError("");
  };

  const save = async () => {
    setState("saving");
    setError("");
    try {
      const response = await fetch(`${API_URL}/revisions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          generated_text: generatedText,
          corrected_text: editedText,
          doc_type: docType,
          session_id: sessionId,
        }),
      });
      if (!response.ok) {
        const detail = await response.text();
        throw new Error(detail.slice(0, 300) || `HTTP ${response.status}`);
      }
      setResult((await response.json()) as RevisionSaveResult);
      setState("saved");
      setEditing(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : "تعذّر حفظ التصحيح.");
      setState("error");
    }
  };

  return (
    <div className="border-t border-slate-200 bg-white p-6 space-y-3">
      {state === "saved" && result ? (
        <div className="flex flex-wrap items-center gap-2 rounded-lg border border-green-200 bg-green-50 p-3 text-sm text-green-800">
          <CheckCircle className="w-4 h-4 shrink-0" />
          <span className="font-semibold">حُفظ تصحيحك.</span>
          <span>
            عدّلتَ {(result.edit_ratio * 100).toFixed(1)}٪ من المسودّة
            ({result.quality_band}) — {result.word_count} كلمة.
          </span>
        </div>
      ) : !editing ? (
        <div className="flex flex-wrap items-center gap-3">
          <Button variant="outline" size="sm" onClick={startEditing}>
            <FileText className="ms-2 w-4 h-4" />
            عدّل واحفظ نسختك
          </Button>
          <span className="text-xs text-slate-500">
            كل تصحيح تحفظه يقرّب المنصّة من الكتابة بأسلوبك لا بأسلوب عام.
          </span>
        </div>
      ) : (
        <>
          <p className="text-sm text-slate-700">
            عدّل المسودّة هنا، أو الصق نسختك النهائية من Word. وإن كانت سليمة
            فاتركها — لا فائدة من حفظ تصحيح بلا تغيير.
          </p>
          <Textarea
            value={editedText}
            onChange={(e) => setEditedText(e.target.value)}
            className="min-h-[320px] text-base leading-loose"
            dir="auto"
            aria-label="نسختك المعتمدة من المستند"
          />
          <div className="flex flex-wrap items-center gap-3">
            <Button size="sm" onClick={save} disabled={state === "saving"}>
              {state === "saving" ? (
                <>
                  <Loader2 className="ms-2 w-4 h-4 animate-spin" />
                  جاري الحفظ...
                </>
              ) : (
                "احفظ التصحيح"
              )}
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={cancel}
              disabled={state === "saving"}
            >
              إلغاء
            </Button>
          </div>
        </>
      )}

      {state === "error" && error && (
        <div className="whitespace-pre-wrap rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          {error}
        </div>
      )}
    </div>
  );
}

export default function Workspace() {
  const [prompt, setPrompt] = useState("");
  const [docType, setDocType] = useState("لائحة دعوى تجارية");
  const [status, setStatus] = useState<Status>("idle");
  const [liveMessage, setLiveMessage] = useState("");
  const [finalDocument, setFinalDocument] = useState("");
  const [errorMessage, setErrorMessage] = useState("");
  const [citationReport, setCitationReport] = useState<CitationsReport | null>(null);

  // معرّف الجلسة يُولَّد **عند الإرسال** لا عند العرض.
  // السبب: `crypto.randomUUID()` لا يعمل على الخادم، وتوليده أثناء العرض يُنتج
  // قيمة مختلفة على الخادم والعميل فيكسر الترطيب (hydration mismatch).
  const sessionIdRef = useRef("");

  // المستند بعد التنظيف — يُستخدم للعرض والنسخ معاً حتى لا يختلف ما تراه عمّا تنسخه
  const cleanDocument = stripMarkdownArtifacts(finalDocument);

  const handleGenerate = async () => {
    if (!prompt.trim()) return;

    setStatus("processing");
    setLiveMessage("جاري إيقاظ فريق العقل القانوني...");
    setFinalDocument("");
    setErrorMessage("");
    setCitationReport(null);

    // معرّف الجلسة: يُثبَّت مرة واحدة ليُربط التصحيح بمسودّته
    if (!sessionIdRef.current) {
      sessionIdRef.current =
        typeof crypto !== "undefined" && typeof crypto.randomUUID === "function"
          ? crypto.randomUUID()
          : `s-${Date.now()}`;
    }

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), GENERATION_TIMEOUT_MS);

    try {
      const response = await fetch(`${API_URL}/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt, doc_type: docType }),
        signal: controller.signal,
      });

      if (!response.ok) {
        const detail = await response.text();
        throw new Error(`الخادم أعاد الخطأ ${response.status} — ${detail.slice(0, 300)}`);
      }
      if (!response.body) {
        throw new Error("الخادم لم يُرجع بثّاً صالحاً");
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();

      // مخزن مؤقت: حدث SSE واحد قد يصل مقسّماً على أكثر من قطعة شبكية.
      // النسخة السابقة قسّمت كل قطعة على "\n\n" مباشرة، فكان أي حدث ينقسم
      // بين قطعتين يُسقَط بصمت ويبقى المستخدم عالقاً في شاشة التحميل.
      let buffer = "";
      // هل وصل حدث ختامي (done/error)؟ إن لا، فالخادم قطع البثّ في المنتصف.
      let sawTerminal = false;

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        let boundary: number;
        while ((boundary = buffer.indexOf("\n\n")) !== -1) {
          const rawEvent = buffer.slice(0, boundary);
          buffer = buffer.slice(boundary + 2);

          const dataLine = rawEvent.split("\n").find((l) => l.startsWith("data: "));
          if (!dataLine) continue;

          let event: StreamEvent;
          try {
            event = JSON.parse(dataLine.slice(6)) as StreamEvent;
          } catch {
            continue; // حدث مشوّه — نتجاهله بدل إسقاط البثّ كله
          }

          if (event.type === "stage") {
            setLiveMessage(event.message);
          } else if (event.type === "citations") {
            // يصل قبل "done" — فالتقرير جاهز حين يُعرض المستند
            setCitationReport(event.report);
          } else if (event.type === "done") {
            setFinalDocument(event.document);
            setStatus("done");
            sawTerminal = true;
          } else if (event.type === "error") {
            setErrorMessage(event.message);
            setStatus("error");
            sawTerminal = true;
          }
        }
      }

      if (!sawTerminal) {
        setErrorMessage("انقطع البثّ قبل اكتمال المستند. تحقّق من سجلّات الخادم.");
        setStatus("error");
      }
    } catch (error) {
      const aborted = error instanceof DOMException && error.name === "AbortError";
      setErrorMessage(
        aborted
          ? "انتهت المهلة (3 دقائق) قبل اكتمال الصياغة."
          : error instanceof Error
            ? error.message
            : "حدث خطأ غير متوقع في الاتصال بالخادم."
      );
      setStatus("error");
    } finally {
      clearTimeout(timeoutId);
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-50 p-8 font-sans" dir="rtl">
      <header className="mb-8 flex items-center gap-3">
        <Scale className="w-8 h-8 text-amber-500" />
        <h1 className="text-3xl font-bold tracking-tight text-white">العقل القانوني</h1>
      </header>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        
        {/* العمود الأيمن: لوحة الإدخال */}
        <div className="lg:col-span-1">
          <Card className="bg-slate-900 border-slate-800 text-white shadow-xl">
            <CardHeader>
              <CardTitle>مساحة الصياغة</CardTitle>
              <CardDescription className="text-slate-400">
                حدد نوع المستند وأدخل المعطيات والوقائع ليبدأ الفريق عمله.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="space-y-2">
                <label className="text-sm font-medium text-slate-300">نوع المستند</label>
                <select 
                  className="w-full p-3 rounded-md bg-slate-950 border border-slate-800 text-white focus:ring-amber-500"
                  value={docType}
                  onChange={(e) => setDocType(e.target.value)}
                >
                  <option value="لائحة دعوى تجارية">لائحة دعوى تجارية</option>
                  <option value="إنذار قانوني">إنذار قانوني</option>
                  <option value="وكالة قانونية خاصة">وكالة قانونية خاصة</option>
                  <option value="مذكرة دفاع">مذكرة دفاع</option>
                </select>
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium text-slate-300">الوقائع والمعطيات</label>
                <Textarea 
                  placeholder="مثال: مطالبة مالية بقيمة 20,000 درهم عن فواتير غير مسددة..." 
                  className="min-h-[200px] bg-slate-950 border-slate-800 focus-visible:ring-amber-500 text-white resize-none"
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                />
              </div>

              <Button 
                onClick={handleGenerate} 
                disabled={status === "processing" || !prompt.trim()}
                className="w-full bg-amber-600 hover:bg-amber-700 text-white py-6 text-lg transition-all"
              >
                {status === "processing" ? (
                  <><Loader2 className="ml-2 h-5 w-5 animate-spin" /> جاري الصياغة...</>
                ) : (
                  <><Send className="ml-2 h-5 w-5" /> ابدأ الصياغة</>
                )}
              </Button>
            </CardContent>
          </Card>
        </div>

        {/* العمود الأيسر: المكتب الذكي والمستند النهائي */}
        <div className="lg:col-span-2">
          <AnimatePresence mode="wait">
            {status === "idle" && (
              <motion.div 
                key="empty"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="h-full min-h-[500px] flex flex-col items-center justify-center border-2 border-dashed border-slate-800 rounded-xl text-slate-500"
              >
                <FileText className="w-16 h-16 mb-4 opacity-50" />
                <p className="text-lg">المستند النهائي سيظهر هنا</p>
              </motion.div>
            )}

            {status === "processing" && (
              <motion.div 
                key="processing"
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -20 }}
                className="h-full min-h-[500px] flex flex-col items-center justify-center bg-slate-900 border border-slate-800 rounded-xl p-8 shadow-2xl"
              >
                <div className="relative w-32 h-32 mb-8 flex items-center justify-center">
                  <motion.div 
                    animate={{ rotate: 360 }}
                    transition={{ repeat: Infinity, duration: 3, ease: "linear" }}
                    className="absolute inset-0 rounded-full border-t-2 border-amber-500 border-opacity-50"
                  />
                  <Bot className="w-12 h-12 text-amber-500" />
                </div>
                <h3 className="text-2xl font-bold text-white mb-2">المكتب الذكي يعمل الآن</h3>
                <p className="text-amber-400 text-lg animate-pulse">{liveMessage}</p>
              </motion.div>
            )}

            {status === "error" && (
              <motion.div 
                key="error"
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -20 }}
                className="h-full min-h-[500px] flex flex-col items-center justify-center bg-slate-900 border border-red-900/50 rounded-xl p-8 shadow-2xl"
              >
                <AlertTriangle className="w-16 h-16 mb-6 text-red-500" />
                <h3 className="text-2xl font-bold text-white mb-3">تعذّر إتمام الصياغة</h3>
                <p className="text-red-300 text-center leading-relaxed max-w-lg mb-6" dir="auto">
                  {errorMessage}
                </p>
                <p className="text-slate-500 text-sm text-center max-w-lg">
                  تأكد من أن خادم FastAPI يعمل على {API_URL} — راجع{" "}
                  <code className="text-slate-400">.env.local</code>
                </p>
              </motion.div>
            )}

            {status === "done" && (
              <motion.div 
                key="done"
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                className="bg-white text-slate-900 rounded-xl shadow-2xl overflow-hidden"
              >
                <div className="bg-slate-100 p-4 border-b flex justify-between items-center">
                  <div className="flex items-center gap-2 text-green-600 font-semibold">
                    <CheckCircle className="w-5 h-5" />
                    تمت الصياغة والاعتماد
                  </div>
                  <Button variant="outline" size="sm" onClick={() => navigator.clipboard.writeText(cleanDocument)}>
                    نسخ المستند
                  </Button>
                </div>
                <div className="p-8 max-w-none whitespace-pre-wrap text-lg leading-loose text-slate-900">
                  {cleanDocument}
                </div>
                <CitationsPanel report={citationReport} />
                <RevisionBar
                  generatedText={cleanDocument}
                  docType={docType}
                  sessionId={sessionIdRef.current}
                />
              </motion.div>
            )}
          </AnimatePresence>
        </div>

      </div>
    </div>
  );
}
