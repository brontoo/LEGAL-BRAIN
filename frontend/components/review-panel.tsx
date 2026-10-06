/**
 * لوحة المراجعة الثانية — ما أُخذ به الكاتب قبل التسليم.
 * ============================================================================
 * «المفتش ثُغرة» يقرأ المسودّة **خصماً لا كاتباً**: يواجهها بالموجز وبما
 * استُرجع من الأرشيف، ويُعدّد ما يُؤخذ به الكاتب. انظر `review.py`، ومنه
 * يأتي هذا الشكل كما هو بلا اجتهاد في الواجهة.
 *
 * ⚠️ الفرق الذي تقوم عليه اللوحة كلها: **«تعذّرت المراجعة» ليست «لا اعتراض»**.
 * ============================================================================
 * مراجعة لم تحدث، ومراجعة لم تجد شيئاً، **واقعتان مختلفتان** يجب أن تختلفا
 * في الشكل. ولو عُرضتا بلون واحد لصار الفشل علامةً على السلامة — وهو أسوأ من
 * عدم عرض اللوحة أصلاً، لأن المحامي يتعلّم أن يقرأها.
 *
 * ⚠️ و`failed` في الشكل يصل `true` ومعه `clean: true` و`error_count: 0`
 * (انظر `_review_round` في main.py): الخادم لا يُسقط التوليد إذا فشل المُراجع،
 * لكنه يعلنه. فقراءة `clean` وحدها هنا **تكذب على المحامي بصدق** — وهذا
 * بالضبط ما يمنعه تقديم `failed` على `clean` في هذا الملف.
 *
 * ⚠️ و`dropped` هو **أمانة اللوحة**: عدد الاعتراضات التي أُسقطت لأن نصّها لم
 * يثبت في المسودّة ولا في الموجز. وهو مقياس ما حاول المُراجع أن يؤلّفه، فلا
 * يُطوى في سطر ثانوي. وفي `review.py`: «أداة تُنذر دائماً لا تُنذر أبداً» —
 * ولهذا لا يُعرض هذا الرقم كعيب، بل كحدّ يعرف المحامي عنده مقدار ما فُحص.
 *
 * ⚠️ وكل نصّ هنا (`message` · `quote` · `basis` · `summary`) يأتي من مخرج
 * النموذج ومن المسودّة، ويُعرض محتوى React عادياً. ولا
 * `dangerouslySetInnerHTML` في هذا الملف: الاقتباس نصّ يُقرأ، لا HTML يُنفَّذ.
 *
 * وألوانه على هوية المشروع: `slate-*` للورق والحبر، و`amber-*` للنحاس
 * (الملاحظات)، و`seal` — شمع الختم الأحمر — للأخطاء التي تمنع التسليم.
 *
 * ⚠️ ودرجة النحاس `amber-700` لا `amber-500` في حال الملاحظات وحدها: هذا
 * السطح **فاتح** (`bg-slate-50`)، و`amber-500` نحاس مشرق صُمِّم للنصّ على
 * السطح الداكن. وهو نفسه الخيار الذي وقعت عليه لوحة التدقيق اللغوي في
 * `app/workspace/page.tsx` لملاحظاتها، فيتشابه السطحان ولا يفترقان بلا سبب.
 */

import {
  AlertTriangle,
  FileText,
  ShieldAlert,
  ShieldCheck,
} from "lucide-react";

/* ==============================================================================
   الأنواع — تطابق `summarize()` في review.py حقلاً بحقل.
   ============================================================================== */

/** نوع الاعتراض — القيم الممكنة هي `KINDS` في review.py. */
type ReviewKind = "fact" | "omission" | "unsupported" | "arithmetic" | "strength";

/** درجة الخطورة — `SEVERITIES` في review.py. */
type ReviewSeverity = "error" | "notice";

/** اعتراض واحد **بعد أن أثبت الخادم نصّه** — ما لم يثبت لا يصل إلى هنا. */
export type ReviewFinding = {
  kind: ReviewKind;
  severity: ReviewSeverity;
  message: string;
  quote: string;
  basis: string;
};

/** تقرير المراجعة الثانية كما يبثّه `_review_round` في main.py. */
export type ReviewReport = {
  summary: string;
  clean: boolean;
  error_count: number;
  notice_count: number;
  dropped: number;
  /** `true` حين لم يستطع المُراجع أن يعمل أصلاً — و`summary` تحمل السبب. */
  failed: boolean;
  findings: ReviewFinding[];
};

/* ==============================================================================
   الخرائط — تُفتح بالمفتاح الآلي لا بالنصّ العربي.
   ============================================================================== */

/**
 * أسماء الأنواع بالعربية.
 *
 * ⚠️ والمفتاح قيمة آلية (`fact`) لا النصّ العربي، لأن النصّ يُحرَّر ويُعاد
 * صياغته، والقيمة ثابتة في `KINDS`. ولو فُتحت الخريطة بالنصّ العربي لانكسر
 * العرض بصمت في أول تعديل تحريري على التسمية — والقاعدة في هذا المشروع أن
 * الواجهة تربط بالمفاتيح.
 *
 * ⚠️ والترتيب هنا بترتيب `KINDS` نفسه لا أبجدياً: من مخالفة الموجز، إلى
 * الإغفال، إلى غياب السند، إلى الحساب، إلى تقدير قوّة الدفع.
 */
const KIND_LABELS: Record<ReviewKind, string> = {
  fact: "مخالفة للوقائع",
  omission: "إغفال",
  unsupported: "بلا سند",
  arithmetic: "حساب مشكوك فيه",
  strength: "دفاع ضعيف",
};

/** الدرجات بالعربية — تُطبع داخل الشارة، فالفرق لا يقوم على اللون وحده. */
const SEVERITY_LABELS: Record<ReviewSeverity, string> = {
  error: "خطأ",
  notice: "ملاحظة",
};

/**
 * اسم النوع، ويُسقَط إلى أضعف الدعاوى لكل قيمة لا تُعرف.
 *
 * ⚠️ والسقوط هنا على `unsupported` لا على `fact`: الخادم نفسه يُطبّع أي تصنيف
 * مجهول إلى `DEFAULT_KIND` («بلا سند» في review.py). فلو خمّنت الواجهة نوعاً
 * أعلى ممّا خمّنه الخادم لادّعت على الكاتب مخالفةً لم تُثبت. والجهل يُقال
 * بأضيق حدّه لا بأوسعه.
 */
function kindLabel(kind: string): string {
  return kind in KIND_LABELS ? KIND_LABELS[kind as ReviewKind] : KIND_LABELS.unsupported;
}

/** اسم الدرجة، ويُسقَط إلى `notice` للأسباب نفسها: لا نُعلن خطأً لم يُعلنه الخادم. */
function severityLabel(severity: string): string {
  return severity in SEVERITY_LABELS
    ? SEVERITY_LABELS[severity as ReviewSeverity]
    : SEVERITY_LABELS.notice;
}

/**
 * وسم الخطورة — **يحمل الفرق بالكلمة والشكل لا باللون وحده**.
 *
 * ⚠️ ولماذا لا اللون فقط؟ لأن الأحمر والأخضر يفترقان في عمى الألوان، ولأن
 * المستند قد يُطبع على ورق أبيض وأسود. وفي الحالتين يجب أن يبقى «ما يمنع
 * التسليم» ممّا لا يمنعه: الكلمة («خطأ» · «ملاحظة»)، والأيقونة، وسمك الحدّ
 * الجانبي — وكلّها تنجو من فقدان اللون. واللون يبقى تأكيداً لا دليلاً.
 */
function SeverityTag({ severity }: { severity: string }) {
  const isError = severity === "error";
  return (
    <span
      className={
        isError
          ? "inline-flex items-center gap-1 border border-seal px-2 py-0.5 text-xs font-bold text-seal"
          : "inline-flex items-center gap-1 border border-amber-700/40 px-2 py-0.5 text-xs font-semibold text-amber-700"
      }
    >
      {isError ? (
        <ShieldAlert className="w-3.5 h-3.5" />
      ) : (
        <FileText className="w-3.5 h-3.5" />
      )}
      {severityLabel(severity)}
    </span>
  );
}

/** اعتراض واحد — الرسالة، ثم الاقتباس من المسودّة، ثم سنده. */
function FindingCard({ finding }: { finding: ReviewFinding }) {
  const isError = finding.severity === "error";
  return (
    <div
      className={
        isError
          ? "border border-seal/40 border-s-4 bg-white p-3 space-y-2"
          : "border border-amber-700/30 border-s-2 bg-white p-3 space-y-2"
      }
    >
      <div className="flex flex-wrap items-center gap-2">
        <span
          className={
            isError
              ? "border border-seal/40 bg-seal/10 px-2 py-0.5 text-xs font-bold text-seal"
              : "border border-amber-700/40 bg-amber-700/10 px-2 py-0.5 text-xs font-semibold text-amber-700"
          }
        >
          {kindLabel(finding.kind)}
        </span>
        <SeverityTag severity={finding.severity} />
      </div>

      {/* الاعتراض نفسه — أهمّ نصّ في البطاقة، فيُعرض بخطّ عادي لا بخطّ ثابت. */}
      <p className="text-sm font-medium leading-relaxed text-slate-900" dir="auto">
        {finding.message}
      </p>

      {/*
        الاقتباس من المسودّة. والقوسان العربيان (`«…»`) يأتيان من العرض لا من
        النصّ: هما علامة على أنه منقول حرفاً بحرف، ولا يجوز أن يُخلطا بنصّ
        الاقتباس نفسه فيصيرا جزءاً منه. و`dir="auto"` يترك الاتجاه للسياق لا
        للقيمة الافتراضية.
      */}
      <div className="border-s-2 border-slate-300 ps-3">
        <div className="text-xs text-slate-500">من المسودّة</div>
        <p className="text-sm leading-relaxed text-slate-700" dir="auto">
          «{finding.quote}»
        </p>
      </div>

      {/*
        ⚠️ والسند الفارغ يُقال صراحةً: **«لا سند نصّي»**. وترك هذا الموضع فارغاً
        كان سيقرأ كسطر ناقص أو كخطأ عرض، والمعنى الحقيقي أهمّ من ذلك: الاعتراض
        يقوم على المسودّة وحدها، ولا نصّ في الموجز ولا في المقتطفات يسنده.
        وهذا **مشروع ومقصود** في review.py، لا عيب — فيُعلن ولا يُخفى.
      */}
      <div className="border-s-2 border-slate-300 ps-3">
        <div className="text-xs text-slate-500">السند</div>
        {finding.basis ? (
          <p className="text-sm leading-relaxed text-slate-600" dir="auto">
            «{finding.basis}»
          </p>
        ) : (
          <p className="text-sm text-slate-500">
            لا سند نصّي — الاعتراض على المسودّة وحدها.
          </p>
        )}
      </div>
    </div>
  );
}

/* ==============================================================================
   اللوحة
   ============================================================================== */

export function ReviewPanel({ report }: { report: ReviewReport | null }) {
  // لا تقرير = لا مراجعة في هذه الجولة — ولا نرسم صندوقاً فارغاً يوهم بأنها جرت.
  if (!report) return null;

  /*
   * ⚠️ وترتيب الفحص مقصود: `failed` **أولاً**، قبل `clean`.
   *
   * لأن الخادم يُرسل `clean: true` و`error_count: 0` مع الفشل، فلو قُرئت
   * `clean` أولاً لعُرض الفشل كمسودّة سليمة — وهي الكذبة الوحيدة التي يمنعها
   * هذا الملف. و«تعذّرت المراجعة» حالةٌ ثالثة لا نظير لها في `clean`.
   */
  const failed = report.failed === true;
  const findings = Array.isArray(report.findings) ? report.findings : [];
  const errors = findings.filter((item) => item.severity === "error");
  const notices = findings.filter((item) => item.severity === "notice");
  const dropped = report.dropped ?? 0;

  /*
   * ⚠️ والعدّان المعروضان هما عدّان **الخادم** (`error_count` · `notice_count`)
   * لا `errors.length`، لأن الخادم هو من يحكم على الخطورة (`summarize` في
   * review.py)، وعرض رقم محسوب هنا يجعل الواجهة تحكم بدلاً منه — ولو اختلفا
   * لصدّقت الواجهة نفسها. والصفّان (`errors` · `notices`) يُستخدمان للفرز
   * والعرض فقط، وهما مشتقّان من نفس المصفوفة فلا يخالفان العدّادين.
   */
  const errorCount = report.error_count ?? errors.length;
  const noticeCount = report.notice_count ?? notices.length;

  // تقرير فارغ تماماً: لا فشل يُعلن، ولا حكم يُقال، ولا ملاحظة تُعرض.
  if (!failed && findings.length === 0 && !report.summary) return null;

  const clean = !failed && report.clean === true && findings.length === 0;

  return (
    <div className="border-t border-slate-200 bg-slate-50 p-6 space-y-4">
      {/*
        ⚠️ والحالات الثلاث العليا تفترق **بنصّها وأيقونتها أولاً**، ثم بلونها:
        رمادي هادئ للفشل، ونحاسي مغلق للسلامة، وأحمر الختم للخطأ الذي يمنع
        التسليم. وفشل المُراجع ليس خطأً في المسودّة ولا سلامةً فيها — فلا
        يُلبَس لون واحد منهما.
      */}
      {failed ? (
        <div className="flex items-start gap-2 border border-slate-300 border-s-4 border-s-slate-500 bg-white p-3">
          <AlertTriangle className="mt-0.5 w-5 h-5 shrink-0 text-slate-500" />
          <div className="space-y-1 min-w-0">
            <p className="font-bold text-slate-700">
              تعذّرت المراجعة الثانية — لم تُقرأ هذه المسودّة بعين خصم.
            </p>
            {/* السبب يأتي من `summary` كما صاغه الخادم، بلا إعادة كتابة. */}
            <p className="text-sm text-slate-600 leading-relaxed" dir="auto">
              {report.summary}
            </p>
            <p className="text-xs text-slate-500">
              هذه ليست سلامةً في المسودّة: المراجعة لم تجرِ أصلاً، فلا شيء يقال
              عن اعتراضاتها — لا وجوداً ولا عدماً.
            </p>
          </div>
        </div>
      ) : (
        <>
          <div className="flex flex-wrap items-center gap-2">
            {errors.length > 0 ? (
              <ShieldAlert className="w-5 h-5 text-seal" />
            ) : (
              <ShieldCheck className="w-5 h-5 text-amber-700" />
            )}
            <h3 className="font-bold text-slate-900">المراجعة الثانية</h3>
            {/* حكم اللوحة كما صاغه الخادم — لا يُعاد تركيبه في الواجهة. */}
            <span className="text-sm text-slate-500" dir="auto">
              ({report.summary})
            </span>
          </div>

          {/*
            ✦ الحالة التي تهمّ: أخطاء تمنع التسليم.
            والعدد هو العنوان — أكبر نصّ في اللوحة، فلا يُقرأ التقرير ليعرف
            المحامي أن فيه مانعاً. ولا يُزخرف ولا يُهلَّل: مانعٌ يُقال بحجمه.
          */}
          {errors.length > 0 && (
            <div className="space-y-3">
              <div className="flex flex-wrap items-baseline gap-2">
                <span className="text-3xl font-bold leading-none text-seal tabular-nums">
                  {errorCount.toLocaleString("ar-AE")}
                </span>
                <span className="font-bold text-slate-900">
                  {errorCount === 1
                    ? "اعتراض يمنع التسليم"
                    : "اعتراضات تمنع التسليم"}
                </span>
              </div>
              {errors.map((finding, index) => (
                <FindingCard key={`e-${index}`} finding={finding} />
              ))}
            </div>
          )}

          {/* ✦ ملاحظات للعلم — أهدأ: لا تمنع التسليم، فلا تُعرض بحجم الموانع. */}
          {notices.length > 0 && (
            <div className="space-y-2">
              <h4 className="text-sm font-semibold text-amber-700">
                ملاحظات للعلم — لا تمنع التسليم ({noticeCount.toLocaleString("ar-AE")})
              </h4>
              {notices.map((finding, index) => (
                <FindingCard key={`n-${index}`} finding={finding} />
              ))}
            </div>
          )}

          {/*
            ✦ سلامة المسودّة: مراجعة جرت ولم تجد ما يؤخذ به الكاتب.
            وهذا **نتيجة طيّبة** لا انتصار، فتُقال بهدوء: مُراجع يعترض دائماً
            مُراجع لا يُقرأ، وحين يظهر العيب الحقيقي يمرّ. فلا احتفال ولا
            «ممتاز» — جملة واحدة في سطر واحد.
          */}
          {clean && (
            <div className="flex flex-wrap items-center gap-2 border border-slate-200 bg-white px-3 py-2 text-sm text-slate-600">
              {/* ⚠️ أيقونة ورقية محايدة لا علامة صحّ خضراء: «لم يجد اعتراضاً»
                  نتيجة طيّبة تُقال بهدوء، لا نجاح يُحتفل به. */}
              <FileText className="w-4 h-4 shrink-0 text-amber-500" />
              <span className="font-semibold text-slate-700">
                لم يجد المُراجع اعتراضاً.
              </span>
              <span>لا ما يمنع التسليم ولا ما يستحقّ النظر.</span>
            </div>
          )}
        </>
      )}

      {/*
        ✦ الاعتراضات المُسقَطة — تُعرض في الحالتين (فشلٍ ونجاح)، لأنها وصف
        لِما فعله المُراجع لا لِما وجده. ولا تُطوى لأنها قد تُظهر مسودّة
        `clean` ليست كمسودّة لم يُعترض عليها أصلاً: هل سكت المُراجع لأنه رضي،
        أم لأنه اتّهم ولم يُثبت؟ والسطر يجيب.
      */}
      {dropped > 0 && (
        <p className="border-s-2 border-slate-400 ps-3 text-xs text-slate-600 leading-relaxed">
          أُسقط {dropped.toLocaleString("ar-AE")}{" "}
          {dropped === 1 ? "اعتراض" : "اعتراضات"} لعدم ثبوت نصّه في المسودّة أو
          في الموجز —{" "}
          <span className="line-through decoration-slate-400">
            لم يُعرض على المحامي
          </span>
          ، ويُعدّ عدّاً لا يُخفى.
        </p>
      )}
    </div>
  );
}
