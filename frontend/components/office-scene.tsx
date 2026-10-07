"use client";

/**
 * مشهد «فريق المكتب» — تمثيل بصري حقيقي لمراحل الصياغة.
 * ============================================================================
 * الفريق **أسماء موجودة في النظام نفسه** لا مخترعة هنا:
 *
 *   smart_office.py  →  «أمين المكتبة» · «مُسوَدَّة أفندي» · «المفتش ثُغرة»
 *                       · «سيبويه المُكشّر»
 *   office_test.py   →  «المعلم أبو الختم»
 *
 * ⚠️ وملاحظة صريحة: تلك الأسماء في `smart_office.py` — وهو **سكربت مستقلّ لا
 * يستدعيه `/generate`**. فـ«سيبويه» و«المفتش ثُغرة» لم يراجعا مستنداً واحداً
 * أنتجه الموقع قبل هذا التغيير. وقد مُنحا هنا عملاً حقيقياً في المسار الفعلي:
 * المفتش يتحقّق من الأسانيد (`citations.py`)، وسيبويه يدقّق الصياغة
 * (`language_audit.py`) — وكلاهما فحص حتمي لا نموذج.
 *
 * ⚠️ **ولا شيء في هذا المشهد تجميلي.**
 * كل شخصية مرتبطة بمفتاح مرحلة يبثّه الخادم، والمفاتيح تأتي من مراحل وقعت
 * فعلاً. فإن لم تُستدعَ أداة العقود مثلاً، لا يُوهم المشهد بأن أحداً بحث فيها.
 * ولو حُرِّك بمؤقّت زمني لصار مسرحاً يخفي ما يجري — وهو النمط المضادّ نفسه
 * الذي رأيناه في مشروع «محاكاة التفاوض»: قيود في الموجّه ولا فحص في الكود.
 */

import { useEffect, useState } from "react";
import { motion, useReducedMotion } from "motion/react";
import {
  Archive,
  Clock,
  Coffee,
  FileText,
  PenTool,
  ShieldAlert,
  Stamp,
} from "lucide-react";

/** موظّف واحد في المكتب. */
type Worker = {
  /** مفتاح الشخصية — وتُشتقّ مفاتيح مراحله من `STAGE_CHARACTER` */
  key: string;
  name: string;
  role: string;
  icon: typeof Archive;
  color: string;
  glow: string;
};

/**
 * الفريق — خمسة بأسمائهم في النظام.
 *
 * وأربعة منهم **نكات قانونية حقيقية** وضعها صاحب المكتب:
 * «مُسوَدَّة أفندي» و«المفتش ثُغرة» و«سيبويه المُكشّر» و«المعلم أبو الختم».
 */
const TEAM: Worker[] = [
  {
    key: "library",
    name: "أمين المكتبة",
    role: "البحث في الأرشيف",
    icon: Archive,
    color: "#2dd4bf",
    glow: "rgba(45,212,191,0.35)",
  },
  {
    key: "drafter",
    name: "مُسوَدَّة أفندي",
    role: "وكيل الصياغة",
    icon: PenTool,
    color: "#f59e0b",
    glow: "rgba(245,158,11,0.35)",
  },
  {
    key: "inspector",
    name: "المفتش ثُغرة",
    role: "المدقق القانوني",
    icon: ShieldAlert,
    color: "#4ade80",
    glow: "rgba(74,222,128,0.35)",
  },
  {
    key: "polisher",
    name: "سيبويه المُكشّر",
    role: "المدقق اللغوي",
    icon: FileText,
    color: "#a78bfa",
    glow: "rgba(167,139,250,0.35)",
  },
  {
    key: "sealer",
    name: "المعلم أبو الختم",
    role: "الاعتماد والختم",
    icon: Stamp,
    color: "#f472b6",
    glow: "rgba(244,114,182,0.35)",
  },
];

/**
 * من مفتاح المرحلة إلى الشخصية التي تعمل فيها.
 *
 * ⚠️ هذا الجدول هو **العقد بين الخادم والواجهة**، ويُفحص في `tests/test_main.py`
 * (`TestOfficeSceneContract`). ولو أُضيفت مرحلة في `main.py` ولم تُضف هنا، لما
 * ظهر خطأ — تبقى الشخصية نائمة أبداً. وهو الانحراف الصامت نفسه الذي أصلحناه في
 * الأدوات الخمس حين سقطت أداة التشريعات من نسخة موجّه واحدة.
 *
 * و«أمين المكتبة» يغطّي سبع مراحل: الاستقبال، والأدوات الخمس، وتسليم المقاطع.
 * والسبب أنه هو من يعمل فيها كلها فعلاً — والنصّ المعروض تحته يقول أيّ رفّ
 * يبحث فيه. فشخصية واحدة صادقة خير من سبع شخصيات وهمية.
 */
const STAGE_CHARACTER: Record<string, string> = {
  intake: "library",
  legislation: "library",
  drafts: "library",
  contracts: "library",
  notices: "library",
  poa: "library",
  evidence: "library",
  drafting: "drafter",
  verifying: "inspector",
  polish: "polisher",
  seal: "sealer",
};

/** مفاتيح المراحل التي تخصّ كل شخصية — معكوسة من الجدول أعلاه. */
const CHARACTER_STAGES: Record<string, string[]> = Object.entries(
  STAGE_CHARACTER
).reduce<Record<string, string[]>>((acc, [stage, character]) => {
  (acc[character] ??= []).push(stage);
  return acc;
}, {});

/** حالة الموظّف — تُشتقّ من مفاتيح المراحل التي وصلت فعلاً. */
type Phase = "waiting" | "working" | "done";

function phaseOf(worker: Worker, activeStage: string, completed: Set<string>): Phase {
  // النشِط أولاً: أمين المكتبة يعمل في سبع مراحل متتالية، ولو فُحص «المنتهي»
  // قبله لظهر «أنجز مهمته» وهو ما زال يبحث.
  if (STAGE_CHARACTER[activeStage] === worker.key) return "working";
  const stages = CHARACTER_STAGES[worker.key] ?? [];
  if (stages.some((stage) => completed.has(stage))) return "done";
  return "waiting";
}

/** عدّاد الوقت — يريح الانتظار ويُظهر أن العمل جارٍ فعلاً. */
function ElapsedClock({ startedAt }: { startedAt: number }) {
  const [seconds, setSeconds] = useState(0);

  useEffect(() => {
    const tick = () =>
      setSeconds(Math.max(0, Math.floor((Date.now() - startedAt) / 1000)));
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [startedAt]);

  const minutes = Math.floor(seconds / 60);
  const rest = seconds % 60;

  return (
    <span className="inline-flex items-center gap-1 font-mono tabular-nums">
      <Clock className="h-3.5 w-3.5" />
      {minutes > 0 ? `${minutes}:${String(rest).padStart(2, "0")} دقيقة` : `${rest} ثانية`}
    </span>
  );
}

/**
 * الامتدادات المجرَّبة بالترتيب.
 *
 * ⚠️ ولماذا امتدادان؟ لأن صور الفريق التي وُلِّدت فعلاً **JPEG بأسماء
 * `.png`** — والامتداد الكاذب ليس تفصيلاً شكلياً: الخادم يعلن `image/png`
 * والمحتوى JPEG، ومع ترويسة `X-Content-Type-Options: nosniff` **يرفض المتصفح
 * رسمها**. فأُعيدت تسميتها إلى `.jpg` الصحيحة.
 *
 * ويُجرَّب الامتدادان معاً لأن الصور المولَّدة مستقبلاً قد تكون PNG حقيقية.
 * والترتيب مقصود: `.jpg` أولاً لأنها الصيغة الموجودة، فلا يُطلَق طلب فاشل
 * عند كل تحميل للصفحة.
 */
const ART_EXTENSIONS = ["jpg", "png"] as const;

/** مكتب واحد: الشخص، ومنضدته، واسمه، وحالته. */
function Desk({ worker, phase }: { worker: Worker; phase: Phase }) {
  const working = phase === "working";
  const done = phase === "done";
  const Icon = worker.icon;

  /*
   * ⚠️ **وهنا موضع `motion` في دليل الأنماط: تفضيل المستخدم.**
   *
   * نصّ الدليل: «In most operating systems, users may opt out of motion from
   * their accessibility settings… it is crucial to respect the choice of the
   * user».
   *
   * و`MotionConfig reducedMotion="user"` في `components/motion-preference.tsx`
   * يوقف **الانتقالات الموضعية** (`y`)، وهما الانتقالان أدناه. لكن **الهالة
   * النابضة ليست انتقالاً موضعياً**: هي `opacity` متكرّرة إلى ما لا نهاية،
   * وهي **الحركة الوحيدة المستمرّة في المشروع كلّه**. وهي بالضبط ما تصفه
   * الحجّة في الدليل («can even trigger physical reactions such as nausea and
   * dizziness») — نبضٌ لا ينقطع في زاوية النظر.
   *
   * ⚠️ ولا تُحذف الهالة عند تعطيل الحركة: **ثباتها هو الحلّ لا غيابها**.
   * فالهالة هي العلامة على «من يعمل الآن» حين تتشابه صور الفريق (وهو سببها
   * المعلن في التعليق أدناه)؛ فتُثبَّت عند وهجٍ متوسّط ثابت بدل أن تُطفأ —
   * فيبقى المعنى ويزول النبض.
   */
  const reduceMotion = useReducedMotion();

  // هل توجد صورة مولَّدة لهذا الموظّف؟
  //
  // نحاول `/agents/<key>.jpg` ثم `.png`، وإن فشل الاثنان نرجع إلى الأيقونة.
  // فبمجرد أن تُسقط الصور في `frontend/public/agents/` تعمل بلا تعديل في الكود.
  const [attempt, setAttempt] = useState(0);
  const artExtension = ART_EXTENSIONS[attempt];

  return (
    <motion.div
      className="flex flex-col items-center"
      /*
       * ⚠️ ولا بوب متصل هنا — وهذا أهمّ إصلاح في المشهد.
       *
       * كان كل مكتب يهتزّ رأسياً بلا توقّف ما دام صاحبه يعمل، **وخمسة مكاتب
       * بخمسة إيقاعات متوازية** (٠.٨٥ و١.١ و١.٤ و١.٨ ثانية). وهذا بالذات ما
       * جعل المشهد يبدو رخيصاً: لا هو ساكن فيُقرأ، ولا هو متحرّك فيُفهم — بل
       * **مضطرب**، والعين لا تجد شيئاً ترتاح إليه.
       *
       * والبديل **حالة منفصلة** على نمط محرّكات الروايات البصرية: انتقال واحد
       * عند تغيّر الحالة ثم ثبات. و`key={phase}` يُجبر React على إعادة التركيب
       * فيُشغَّل الانتقال **مرة واحدة لكل تغيّر** لا في حلقة لا تنتهي.
       *
       * ⚠️ **ولماذا بقي `spring` بلا مدّة مكتوبة؟** لأن الدليل يستثني النوابض
       * من المدّة صراحةً: «motion in general does not adhere to the concept of
       * durations and curves, but rather physical properties such as mass and
       * tension». فكتابة `duration` على نابضٍ **تناقض نوعه** وتُلغي السبب الذي
       * وُجد له. والإيقاع هنا مضبوط بالصلابة والتخميد لا بالزمن.
       */
      key={phase}
      initial={{ opacity: 0.4, y: -6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ type: "spring", stiffness: 260, damping: 26 }}
    >
      <div className="relative h-24 w-24 sm:h-28 sm:w-28">
        {/* هالة العمل — أوضح إشارة على من يشتغل الآن */}
        {working && (
          <motion.div
            className="absolute inset-0 rounded-full"
            style={{
              background: `radial-gradient(circle, ${worker.glow} 0%, transparent 70%)`,
            }}
            /*
             * ⚠️ الحركة المستمرّة **الوحيدة** الباقية في المشهد كله.
             *
             * وسببها وظيفي لا تجميلي: هي العلامة على «من يعمل الآن» حين
             * تتشابه الصور. ولذلك **واحدة، وبطيئة (٢.٨ ثانية)، وعلى العنصر
             * الفعّال وحده** — بخلاف اثنتَي عشرة حركة متوازية.
             *
             * ⚠️ وعند تعطيل الحركة تُثبَّت عند وهجٍ متوسّط `0.55` — أي منتصف
             * المدى `0.35↔0.75` — بدل أن تختفي: المعنى يبقى والنبض يزول.
             */
            animate={reduceMotion ? { opacity: 0.55 } : { opacity: [0.35, 0.75, 0.35] }}
            transition={
              reduceMotion
                ? { duration: 0 }
                : { repeat: Infinity, duration: 2.8, ease: "easeInOut" }
            }
          />
        )}

        {/* الشخص: صورة مولَّدة إن وُجدت، وإلا أيقونة الدور.
            والشرط `!artExtension` لأن الفرعين مرتَّبان: الأيقونة أولاً
            (حالة «لا صورة»)، والصورة ثانياً (الحالة الغالبة). */}
        {!artExtension ? (
          <>
            {/* الرأس — أيقونة الدور بدل وجه، لتفادي تمثيل أشخاص بعينهم */}
            <div
              className="absolute start-1/2 top-2 flex h-10 w-10 -translate-x-1/2 items-center justify-center rounded-full border-2 bg-slate-900"
              style={{
                borderColor: working ? worker.color : "#334155",
                boxShadow: working ? `0 0 14px ${worker.glow}` : "none",
              }}
            >
              <Icon
                className="h-5 w-5 transition-colors"
                style={{ color: working ? worker.color : done ? "#64748b" : "#475569" }}
              />
            </div>

            {/* الكتفان */}
            <div
              className="absolute bottom-5 start-1/2 h-7 w-14 -translate-x-1/2 rounded-t-2xl transition-colors"
              style={{
                background: working ? worker.color : "#334155",
                opacity: working ? 0.9 : 0.5,
              }}
            />
          </>
        ) : (
          /*
           * الصورة: صدر الشخص فقط بلا منضدة — فالمنضدة والشاشة تُرسمان هنا
           * بـ CSS فوقها، فتتّسق التركيبة مع الفريق كله سواء وُجدت صورهم أم لا.
           * (ولهذا تطلب موجّهات التوليد «chest-up, no desk»).
           *
           * و`<img>` لا `next/image` عن قصد: الصور تُضاف بعد البناء، و
           * `next/image` يطلب أبعاداً معروفة وقت البناء.
           */
          // eslint-disable-next-line @next/next/no-img-element
          <motion.img
            // المفتاح يُجبر React على إعادة تركيب العنصر عند تغيّر الامتداد،
            // فيُطلَق طلب جديد بدل إعادة استخدام الصورة الفاشلة.
            key={artExtension}
            src={`/agents/${worker.key}.${artExtension}`}
            alt=""
            aria-hidden="true"
            onError={() => setAttempt((value) => value + 1)}
            className="absolute inset-x-0 bottom-2.5 mx-auto h-[72px] w-auto object-contain sm:h-[84px]"
            /*
             * ⚠️ التعتيم بـ `opacity` لا بـ `brightness` — وهذا حساب لا تفضيل.
             *
             * كان هنا `saturate(0.55) brightness(0.75)`. و`brightness` تضرب
             * **الصورة كلها** في 0.75 — ومنها خلفيتها. فخلفية الصورة
             * `(15,21,37)` تصير `(11,16,28)`، أي **أغمق من خلفية المشهد**،
             * فيظهر حول كل منتظر **مستطيل داكن باهت**. والعيب لا يُنتج خطأً بل
             * إطاراً — فيمرّ صامتاً.
             *
             * أما `opacity` فمضبوطة رياضياً: خلفية الصورة **بلون خلفية المشهد
             * نفسه**، فـ ‎0.7×(15,21,37) + 0.3×(15,21,37) = (15,21,37)‎ —
             * فالخلفية **لا تتغيّر إطلاقاً**، ولا يتعتّم إلا الشخص.
             *
             * ولهذا لا تُصلحها `saturate` ولا `grayscale`: كلتاهما تغيّر لون
             * الخلفية نفسها ولو قليلاً.
             */
            style={{
              opacity: working ? 1 : 0.7,
              filter: working ? `drop-shadow(0 0 10px ${worker.glow})` : "none",
            }}
          />
        )}

        {/* المنضدة */}
        <div className="absolute bottom-0 inset-x-0 h-2.5 rounded-md bg-slate-700" />

        {/*
          الشاشة المضيئة — **ثابتة لا وامضة**.

          كانت تنبض ٠.٨٥ ثانية، وهي **أسرع حركة في المشهد** ومع ذلك أضعفها
          معنى: خمس شاشات تومض بإيقاعات مختلفة تُنتج وميضاً لا يُقرأ. واللون
          وحده يقول «تعمل» أو «لا تعمل» — فلا حاجة إلى نبض.
        */}
        <div
          className="absolute bottom-2.5 start-1/2 h-1.5 w-9 -translate-x-1/2 rounded-sm"
          style={{ background: working ? worker.color : "#1e293b" }}
        />

        {/* فنجان القهوة — لمن ينتظر دوره */}
        {phase === "waiting" && (
          <Coffee className="absolute bottom-3 end-2 h-3.5 w-3.5 text-slate-600" />
        )}
      </div>

      <div className="mt-1.5 text-center leading-tight">
        <div
          className="text-[12px] font-bold transition-colors"
          style={{ color: working ? worker.color : done ? "#cbd5e1" : "#64748b" }}
        >
          {worker.name}
        </div>
        <div className="text-[11px] text-slate-500">{worker.role}</div>
      </div>

      <div className="mt-1 h-4 text-[11px]">
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
 * @param activeStage   مفتاح المرحلة الجارية الآن (من الخادم)
 * @param completedKeys كل مفاتيح المراحل التي انتهت
 * @param message       نصّ المرحلة كما وصل من الخادم
 * @param startedAt     وقت بدء الطلب (Date.now)
 */
/* === الحالتان في مكوّنة واحدة ==============================================
   `activeStage` و`startedAt` اختياريان عن قصد: تُستدعى هذه المكوّنة مرّتين —
   في **الوضع الافتراضي** (الفريق في مقاعده، لا مرحلة ولا ساعة) وأثناء
   **الصياغة**. فالمكوّنة الواحدة تخدم الحالتين، ولا تُبنى نسخة ثانية تنحرف
   عن الأولى بعد شهر.

   و«الخمول» يُشتقّ من `startedAt <= 0` لا من خاصية منفصلة: فحالة واحدة لا
   تتناقض مع نفسها، بدل خاصيّتين قد تختلفان.
   ========================================================================= */
export function OfficeScene({
  activeStage = "",
  completedKeys = [],
  message = "الفريق في مقاعده. اكتب الوقائع، وسيبدأون فوراً.",
  startedAt = 0,
}: {
  activeStage?: string;
  completedKeys?: string[];
  message?: string;
  startedAt?: number;
}) {
  const completed = new Set(completedKeys);
  const idle = startedAt <= 0;

  return (
    /*
     * ⚠️ لون الخلفية `#0F1525` لا `slate-900` (`#0F172A`)، والفرق مقصود.
     *
     * الصور المولَّدة جاءت بخلفية `(15,21,37)` = `#0F1525` — أي أخفض من
     * `slate-900` بمقدار درجتين في الأخضر وخمس في الأزرق. والفرق طفيف لكنه
     * **حدّ صريح**: مستطيل داكن باهت حول كل شخص.
     *
     * فطابقنا خلفية المشهد بها، فاندمجت الصور بلا إطار. وتغيير اللون بمقدار
     * ٢/٢٥٥ لا تراه العين، أما الحدّ فتراه.
     */
    <div className="relative overflow-hidden border border-slate-800 bg-[#0f1525] p-6">
      {/* جدار المكتب: نافذة ونبتة — تفاصيل صغيرة تصنع المكان */}
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
            {idle
              ? "الفريق في مقاعده — بانتظار موجزك"
              : "الفريق يعمل على مستندك الآن — كل شخص ومهمته"}
          </p>
        </div>
        <div className="border border-slate-700 bg-slate-950 px-3 py-1 text-[10px] tracking-[0.15em] text-slate-500">
          {/* وفي الخمول لا ساعة: عدّاد وقت بلا عمل يوهم بأن شيئاً يجري */}
          {idle ? (
            <span className="inline-flex items-center gap-1">
              <Coffee className="h-3.5 w-3.5" />
              بانتظار الموجز
            </span>
          ) : (
            <ElapsedClock startedAt={startedAt} />
          )}
        </div>
      </div>

      {/* المكتب: خمسة مكاتب في صفّ واحد على الشاشات الواسعة */}
      <div className="relative grid grid-cols-2 gap-x-3 gap-y-6 sm:grid-cols-3 lg:grid-cols-5">
        {TEAM.map((worker) => (
          <Desk key={worker.key} worker={worker} phase={phaseOf(worker, activeStage, completed)} />
        ))}
      </div>

      {/* فقاعة الكلام: ما يفعله المكتب الآن */}
      <div className="relative mt-6 flex items-start gap-3 border border-slate-700 bg-slate-950 p-4">
        {/* مربّع لا نقطة، وثابت لا نابض — فحالة «جارٍ» يقولها النصّ نفسه */}
        <span className="mt-1.5 h-2 w-2 shrink-0 bg-amber-500" aria-hidden="true" />
        <p className="text-sm leading-relaxed text-amber-200">{message}</p>
      </div>
    </div>
  );
}

/**
 * شريط الفريق بعد انتهاء العمل — من شارك فعلاً.
 *
 * الفائدة الحقيقية أنه **صادق**: يرى المحامي أن أداة الوكالات لم تُستعمل في
 * هذه المسودّة، فيعرف أن ما فيها من صلاحيات لم يُستند فيه إلى أرشيفه.
 */
export function TeamStrip({ stageKeys }: { stageKeys: string[] }) {
  const worked = new Set(
    stageKeys.map((stage) => STAGE_CHARACTER[stage]).filter(Boolean)
  );
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
