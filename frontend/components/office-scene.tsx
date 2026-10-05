"use client";

/**
 * مشهد «فريق المكتب» — تمثيل بصري حقيقي لمراحل الصياغة.
 * ============================================================================
 * الفكرة: بدل انتظار فراغ، يرى المحامي فريقه يعمل: كل شخص على مكتبه، واسمه
 * تحته، ومهمته. ولمن يعمل شاشة مضيئة وحركة، ولمن ينتظر فنجان قهوة.
 *
 * ⚠️ **والأهم أنه ليس رسوماً متحركة تجميلية.**
 * كل شخصية مرتبطة بمفتاح مرحلة **حقيقي** يبثّه الخادم (`stage` في إطار SSE)،
 * وهذا المفتاح يأتي من المرحلة الفعلية: أي أداة استرجاع نُفِّذت فعلاً، ومتى
 * بدأ التوليد، ومتى جرى التحقّق. فإن لم تُستدعَ أداة الوكالات مثلاً، تبقى
 * ليلى على قهوتها ولا تُوهم بأنها عملت.
 *
 * وهذا مقصود: لو حُرِّك المشهد بمؤقّت زمني لصار مسرحاً يخفي ما يجري فعلاً —
 * وهو النمط المضادّ نفسه الذي رأيناه في مشروع «محاكاة التفاوض»: قيود مكتوبة
 * في الموجّه ولا فحص واحد في الكود.
 *
 * والمفتاح آلي ثابت لا نصّ عربي، لأن ربط الواجهة بالنصّ ينكسر بصمت عند أول
 * تعديل صياغة.
 */

import { useEffect, useState } from "react";
import { motion } from "motion/react";
import {
  AlertTriangle,
  Archive,
  Briefcase,
  Clock,
  Coffee,
  FileText,
  PenTool,
  Scale,
  ShieldCheck,
  Stamp,
  Users,
} from "lucide-react";

/** موظّف واحد في المكتب — يقابل مرحلة حقيقية من الخادم. */
type Worker = {
  /** مفتاح المرحلة كما يبثّه الخادم (`main.py`) */
  key: string;
  name: string;
  role: string;
  icon: typeof Scale;
  /** لون البدلة والهالة — يميّز الشخص بصرياً */
  color: string;
  glow: string;
};

/**
 * الفريق — والمفاتيح هنا يجب أن تطابق `main.py` حرفياً:
 * `TOOL_STAGE_KEYS` و`KEY_INTAKE` و`KEY_EVIDENCE` و`KEY_DRAFTING` و`KEY_VERIFYING`.
 */
const TEAM: Worker[] = [
  {
    key: "intake",
    name: "أ. سليم",
    role: "مدير المكتب",
    icon: Users,
    color: "#f59e0b",
    glow: "rgba(245,158,11,0.35)",
  },
  {
    key: "evidence",
    name: "حسن",
    role: "أمين الأرشيف",
    icon: Archive,
    color: "#2dd4bf",
    glow: "rgba(45,212,191,0.35)",
  },
  {
    key: "legislation",
    name: "نورا",
    role: "التشريعات والأحكام",
    icon: Scale,
    color: "#38bdf8",
    glow: "rgba(56,189,248,0.35)",
  },
  {
    key: "drafts",
    name: "سامي",
    role: "أسلوب المذكرات",
    icon: FileText,
    color: "#a78bfa",
    glow: "rgba(167,139,250,0.35)",
  },
  {
    key: "contracts",
    name: "ريم",
    role: "بنود العقود",
    icon: Briefcase,
    color: "#34d399",
    glow: "rgba(52,211,153,0.35)",
  },
  {
    key: "notices",
    name: "خالد",
    role: "صيغ الإنذارات",
    icon: AlertTriangle,
    color: "#fb923c",
    glow: "rgba(251,146,60,0.35)",
  },
  {
    key: "poa",
    name: "ليلى",
    role: "صيغ الوكالات",
    icon: Stamp,
    color: "#f472b6",
    glow: "rgba(244,114,182,0.35)",
  },
  {
    key: "drafting",
    name: "ماهر",
    role: "الكاتب القانوني",
    icon: PenTool,
    color: "#facc15",
    glow: "rgba(250,204,21,0.35)",
  },
  {
    key: "verifying",
    name: "أ. منى",
    role: "تدقيق الأسانيد",
    icon: ShieldCheck,
    color: "#4ade80",
    glow: "rgba(74,222,128,0.35)",
  },
];

/** حالة الموظّف — تُشتقّ من المفاتيح التي وصلت فعلاً. */
type Phase = "waiting" | "working" | "done";

function phaseOf(worker: Worker, activeKey: string, completed: Set<string>): Phase {
  if (worker.key === activeKey) return "working";
  if (completed.has(worker.key)) return "done";
  return "waiting";
}

/** عدّاد الوقت — يريح الانتظار ويُظهر أن العمل جارٍ فعلاً. */
function ElapsedClock({ startedAt }: { startedAt: number }) {
  const [seconds, setSeconds] = useState(0);

  useEffect(() => {
    const tick = () => setSeconds(Math.max(0, Math.floor((Date.now() - startedAt) / 1000)));
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [startedAt]);

  const minutes = Math.floor(seconds / 60);
  const rest = seconds % 60;

  return (
    <span className="inline-flex items-center gap-1 font-mono tabular-nums">
      <Clock className="h-3.5 w-3.5" />
      {minutes > 0
        ? `${minutes}:${String(rest).padStart(2, "0")} دقيقة`
        : `${rest} ثانية`}
    </span>
  );
}

/** مكتب واحد: الشخص، ومنضدته، واسمه، وحالته. */
function Desk({
  worker,
  phase,
}: {
  worker: Worker;
  phase: Phase;
}) {
  const working = phase === "working";
  const done = phase === "done";
  const Icon = worker.icon;

  return (
    <motion.div
      className="flex flex-col items-center"
      animate={working ? { y: [0, -3, 0] } : { y: 0 }}
      transition={working ? { repeat: Infinity, duration: 1.4, ease: "easeInOut" } : {}}
    >
      <div className="relative h-24 w-24 sm:h-28 sm:w-28">
        {/* هالة العمل — أوضح إشارة على من يشتغل الآن */}
        {working && (
          <motion.div
            className="absolute inset-0 rounded-full"
            style={{
              background: `radial-gradient(circle, ${worker.glow} 0%, transparent 70%)`,
            }}
            animate={{ opacity: [0.4, 0.9, 0.4] }}
            transition={{ repeat: Infinity, duration: 1.8, ease: "easeInOut" }}
          />
        )}

        {/* الرأس — أيقونة الدور بدل وجه، لتفادي تمثيل أشخاص بعينهم */}
        <motion.div
          className="absolute start-1/2 top-2 flex h-10 w-10 -translate-x-1/2 items-center justify-center rounded-full border-2 bg-slate-900"
          style={{
            borderColor: working ? worker.color : "#334155",
            boxShadow: working ? `0 0 14px ${worker.glow}` : "none",
          }}
          animate={working ? { rotate: [-5, 5, -5] } : { rotate: 0 }}
          transition={working ? { repeat: Infinity, duration: 1.1, ease: "easeInOut" } : {}}
        >
          <Icon
            className="h-5 w-5 transition-colors"
            style={{ color: working ? worker.color : done ? "#64748b" : "#475569" }}
          />
        </motion.div>

        {/* الكتفان */}
        <div
          className="absolute bottom-5 start-1/2 h-7 w-14 -translate-x-1/2 rounded-t-2xl transition-colors"
          style={{ background: working ? worker.color : "#334155", opacity: working ? 0.9 : 0.5 }}
        />

        {/* المنضدة */}
        <div className="absolute bottom-0 inset-x-0 h-2.5 rounded-md bg-slate-700" />

        {/* الشاشة — تومض عند العمل */}
        <motion.div
          className="absolute bottom-2.5 start-1/2 h-1.5 w-9 -translate-x-1/2 rounded-sm"
          style={{ background: working ? worker.color : "#1e293b" }}
          animate={working ? { opacity: [1, 0.35, 1] } : { opacity: 1 }}
          transition={working ? { repeat: Infinity, duration: 0.85, ease: "easeInOut" } : {}}
        />

        {/* فنجان القهوة — لمن ينتظر دوره */}
        {phase === "waiting" && (
          <Coffee className="absolute bottom-3 end-2 h-3.5 w-3.5 text-slate-600" />
        )}
      </div>

      <div className="mt-1.5 text-center leading-tight">
        <div
          className="text-[13px] font-bold transition-colors"
          style={{ color: working ? worker.color : done ? "#cbd5e1" : "#64748b" }}
        >
          {worker.name}
        </div>
        <div className="text-[11px] text-slate-500">{worker.role}</div>
      </div>

      <div className="mt-1 text-[11px] h-4">
        {working ? (
          <span style={{ color: worker.color }}>● يعمل الآن</span>
        ) : done ? (
          <span className="text-green-500">✓ أنجز مهمته</span>
        ) : (
          <span className="text-slate-600">ينتظر دوره</span>
        )}
      </div>
    </motion.div>
  );
}

/**
 * المشهد الكامل — يُعرض أثناء الصياغة.
 *
 * @param activeKey   مفتاح المرحلة الجارية الآن (من الخادم)
 * @param completedKeys كل المفاتيح التي انتهت
 * @param message     نصّ المرحلة كما وصل من الخادم
 * @param startedAt   وقت بدء الطلب (Date.now)
 */
export function OfficeScene({
  activeKey,
  completedKeys,
  message,
  startedAt,
}: {
  activeKey: string;
  completedKeys: string[];
  message: string;
  startedAt: number;
}) {
  const completed = new Set(completedKeys);

  return (
    <div className="relative overflow-hidden rounded-xl border border-slate-800 bg-slate-900 p-6 shadow-2xl">
      {/* جدار المكتب: نافذة ونبات — تفاصيل صغيرة تصنع المكان */}
      <div className="pointer-events-none absolute inset-0 opacity-[0.07]">
        <div className="absolute start-6 top-6 h-20 w-32 rounded-t-full border-4 border-slate-400" />
        <div className="absolute start-10 top-10 h-0.5 w-24 bg-slate-400" />
        <div className="absolute start-20 top-6 h-20 w-0.5 bg-slate-400" />
        <div className="absolute end-8 bottom-8 h-16 w-6 rounded-t-full bg-green-400" />
      </div>

      {/* ترويسة المكتب */}
      <div className="relative mb-6 flex flex-wrap items-center justify-between gap-3 border-b border-slate-800 pb-4">
        <div>
          <h3 className="text-lg font-bold text-amber-500">مكتب العقل القانوني</h3>
          <p className="text-xs text-slate-500">
            الفريق يعمل على مستندك الآن — كل شخص ومهمته
          </p>
        </div>
        <div className="rounded-full border border-slate-700 bg-slate-950 px-3 py-1 text-xs text-slate-400">
          <ElapsedClock startedAt={startedAt} />
        </div>
      </div>

      {/* المكتب: شبكة تتوسّع إلى صفّين على الشاشات الواسعة */}
      <div className="relative grid grid-cols-2 gap-x-2 gap-y-6 sm:grid-cols-3 lg:grid-cols-5">
        {TEAM.map((worker) => (
          <Desk key={worker.key} worker={worker} phase={phaseOf(worker, activeKey, completed)} />
        ))}
      </div>

      {/* فقاعة الكلام: ما يفعله المكتب الآن */}
      <div className="relative mt-6 flex items-start gap-3 rounded-lg border border-slate-700 bg-slate-950 p-4">
        <motion.span
          className="mt-1 h-2 w-2 shrink-0 rounded-full bg-amber-500"
          animate={{ opacity: [1, 0.25, 1] }}
          transition={{ repeat: Infinity, duration: 1.3 }}
        />
        <p className="text-sm leading-relaxed text-amber-200">{message}</p>
      </div>
    </div>
  );
}

/**
 * شريط الفريق بعد انتهاء العمل — من شارك فعلاً ومن لم يُستدعَ.
 *
 * الفائدة الحقيقية أنه **صادق**: يرى المحامي أن أداة الوكالات لم تُستعمل في
 * هذه المسودّة، فيعرف أن ما فيها من صلاحيات لم يُستند فيه إلى أرشيفه.
 */
export function TeamStrip({ workedKeys }: { workedKeys: string[] }) {
  const worked = new Set(workedKeys);
  const participants = TEAM.filter((worker) => worked.has(worker.key));

  if (participants.length === 0) return null;

  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-2 border-t border-slate-200 bg-slate-50 px-6 py-4">
      <span className="text-xs font-semibold text-slate-600">من عمل على هذا المستند:</span>
      {participants.map((worker) => {
        const Icon = worker.icon;
        return (
          <span
            key={worker.key}
            className="inline-flex items-center gap-1.5 text-xs text-slate-600"
          >
            <Icon className="h-3.5 w-3.5" style={{ color: worker.color }} />
            {worker.name}
            <span className="text-slate-400">({worker.role})</span>
          </span>
        );
      })}
    </div>
  );
}
