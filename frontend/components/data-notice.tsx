"use client";

/**
 * إشعار بيانات موحّد — للخطأ والفراغ والتحميل.
 * ============================================================================
 * لماذا مكوّن مشترك؟ لأن الصفحتين (لوحة القيادة والأرشيف) تحتاجانه، ونسختين
 * منفصلتين تنحرفان: إحداهما تُصلَح والأخرى تُنسى.
 *
 * ⚠️ والقاعدة التي يحميها هذا المكوّن: **لا يُعرض رقم لا يمكن حسابه.**
 * كان في الصفحتين أرقام مكتوبة بخط اليد (١٢٤٨ مستنداً · ٨٥٣٠ سنداً · ١٤ ثانية)
 * لا أصل لها في قاعدة البيانات. والصواب أن يُقال «تعذّر الجلب» أو «لا يوجد
 * بعد» — لا أن يُخترع رقم يبدو حقيقياً.
 */

import { AlertTriangle, Inbox, Loader2 } from "lucide-react";

type Tone = "loading" | "empty" | "error";

const TONES: Record<Tone, { icon: typeof AlertTriangle; ring: string; text: string; bg: string }> = {
  loading: { icon: Loader2, ring: "border-slate-800", text: "text-slate-400", bg: "bg-slate-900" },
  empty: { icon: Inbox, ring: "border-slate-800", text: "text-slate-400", bg: "bg-slate-900" },
  error: { icon: AlertTriangle, ring: "border-red-900/60", text: "text-red-300", bg: "bg-red-950/30" },
};

export function DataNotice({
  tone,
  title,
  detail,
  action,
}: {
  tone: Tone;
  title: string;
  /** نصّ إضافي — غالباً رسالة الخادم التشخيصية كما هي، بلا إعادة صياغة. */
  detail?: string;
  /** أمر أو خطوة مقترحة — تُعرض بخطّ ثابت لأنها تُنسخ عادةً. */
  action?: string;
}) {
  const style = TONES[tone];
  const Icon = style.icon;

  return (
    <div className={`rounded-xl border ${style.ring} ${style.bg} p-6`}>
      <div className={`flex items-start gap-3 ${style.text}`}>
        <Icon className={`w-5 h-5 mt-0.5 shrink-0 ${tone === "loading" ? "animate-spin" : ""}`} />
        <div className="space-y-2 min-w-0">
          <p className="font-medium">{title}</p>
          {detail && <p className="text-sm opacity-80 break-words">{detail}</p>}
          {action && (
            <pre
              dir="ltr"
              className="mt-2 overflow-x-auto rounded-lg border border-slate-800 bg-slate-950 p-3 text-start text-xs text-amber-200"
            >
              {action}
            </pre>
          )}
        </div>
      </div>
    </div>
  );
}

/** قيمة بطاقة: تُظهر «—» أثناء التحميل وعند الفشل، لا صفراً ولا رقماً وهمياً. */
export function MetricValue({
  value,
  unit,
  loading,
  failed,
}: {
  value: number | string;
  unit?: string;
  loading: boolean;
  failed: boolean;
}) {
  if (loading || failed) {
    return <div className="text-4xl font-bold text-slate-600">—</div>;
  }
  return (
    <div className="text-4xl font-bold">
      {typeof value === "number" ? value.toLocaleString("ar-AE") : value}
      {unit && <span className="text-xl text-slate-400 ms-1">{unit}</span>}
    </div>
  );
}
