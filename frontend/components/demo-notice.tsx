import { DEMO_MODE } from "@/lib/preview";

export function DemoNotice() {
  if (!DEMO_MODE) return null;
  return (
    <div role="note" className="border-b border-amber-500/30 bg-slate-900 px-4 py-2 text-xs leading-relaxed text-amber-500">
      <strong lang="en">Demo Preview</strong> — بيانات وأمثلة خيالية فقط؛ لا توليد فعلي ولا تحقق قانوني. الحفظ والنسخ والتصدير معطلة. لا تدخل معلومات سرية.
    </div>
  );
}
