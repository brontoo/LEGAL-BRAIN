"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "motion/react";
import { Send, FileText, Loader2, CheckCircle, Bot, Scale, AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";

// عنوان خادم FastAPI. قابل للضبط من .env.local — انظر .env.local.example
// لاحظ: كان الرابط مُثبَّتاً داخل الكود على نطاق GitHub Codespaces مؤقت ينتهي
// صلاحيته، فكانت الصفحة تفشل دائماً بعد إغلاق الجلسة.
const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(
  /\/+$/,
  ""
);

// مهلة قصوى لتوليد المستند (المستندات الطويلة تستغرق وقتاً)
const GENERATION_TIMEOUT_MS = 180_000;

type Status = "idle" | "processing" | "done" | "error";

type StreamEvent =
  | { type: "stage"; message: string }
  | { type: "done"; document: string }
  | { type: "error"; message: string };

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

export default function Workspace() {
  const [prompt, setPrompt] = useState("");
  const [docType, setDocType] = useState("لائحة دعوى تجارية");
  const [status, setStatus] = useState<Status>("idle");
  const [liveMessage, setLiveMessage] = useState("");
  const [finalDocument, setFinalDocument] = useState("");
  const [errorMessage, setErrorMessage] = useState("");

  // المستند بعد التنظيف — يُستخدم للعرض والنسخ معاً حتى لا يختلف ما تراه عمّا تنسخه
  const cleanDocument = stripMarkdownArtifacts(finalDocument);

  const handleGenerate = async () => {
    if (!prompt.trim()) return;

    setStatus("processing");
    setLiveMessage("جاري إيقاظ فريق العقل القانوني...");
    setFinalDocument("");
    setErrorMessage("");

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
              </motion.div>
            )}
          </AnimatePresence>
        </div>

      </div>
    </div>
  );
}
