"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "motion/react";
import { Send, FileText, Loader2, CheckCircle, Bot, User, Scale } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";

export default function Workspace() {
  const [prompt, setPrompt] = useState("");
  const [docType, setDocType] = useState("لائحة دعوى تجارية");
  const [status, setStatus] = useState("idle"); // idle, processing, done, error
  const [liveMessage, setLiveMessage] = useState("");
  const [finalDocument, setFinalDocument] = useState("");

  const handleGenerate = async () => {
    if (!prompt.trim()) return;
    
    setStatus("processing");
    setLiveMessage("جاري إيقاظ فريق العقل القانوني...");
    setFinalDocument("");

    try {
      // نستخدم fetch لعمل POST request وقراءة البث الحي (SSE)
      const response = await fetch("https://studious-train-94vrq4qj9937r4j-8000.app.github.dev/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt, doc_type: docType }),
      });

      if (!response.body) throw new Error("لا يوجد استجابة من الخادم");

      const reader = response.body.getReader();
      const decoder = new TextDecoder();

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value);
        const lines = chunk.split("\n\n");

        for (const line of lines) {
          if (line.startsWith("data: ")) {
            const data = JSON.parse(line.replace("data: ", ""));
            
            if (data.type === "stage") {
              setLiveMessage(data.message);
            } else if (data.type === "done") {
              setFinalDocument(data.document);
              setStatus("done");
            } else if (data.type === "error") {
              setLiveMessage(`خطأ: ${data.message}`);
              setStatus("error");
            }
          }
        }
      }
    } catch (error) {
      console.error(error);
      setLiveMessage("حدث خطأ في الاتصال بالخادم.");
      setStatus("error");
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
                  <Button variant="outline" size="sm" onClick={() => navigator.clipboard.writeText(finalDocument)}>
                    نسخ المستند
                  </Button>
                </div>
                <div className="p-8 prose prose-slate max-w-none whitespace-pre-wrap font-serif text-lg leading-relaxed">
                  {finalDocument}
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

      </div>
    </div>
  );
}