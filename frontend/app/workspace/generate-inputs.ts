/* ==============================================================================
   مدخلات الفحوص الأربعة — **وموضعها وُجد ليُملأ، لا ليُكتب فيه اليوم**.

   ⚠️ **ولماذا ملفٌّ ثالثٌ لا `page.tsx` وحده؟** لأن الحساب هنا **لا JSX فيه
   ولا React**: حالة النموذج تدخل، وحملُ الطلب يخرج. وفصله يُتيح تشغيله في
   Node بلا متصفّح (`scripts/check-generate-inputs.mjs`)، فيُقاس شكلُ الحمل
   **بالتشغيل** لا بالقراءة. ولو كُتب في `page.tsx` لمُحي معه ولم يبقَ منه
   ما يُقاس.

   ⚠️⚠️ **والتصنيفات هنا نسخٌ حرفيّة من وحدات الخادم — لا تُخترع ولا تُترجم.**
   `Stage` و`Party` و`DisputeAxis` في `claims.py` · و`SourceKind` في
   `authority.py` · و`Unit` في `deadlines.py` · و`RuleFamily` في `rules.py` ·
   و`DisputeType` و`CaseStage` في `case_file.py`. وثلاثةُ أعطابٍ متتالية في هذا
   المشروع كانت **من الشكل نفسه: حقلُ تعديدٍ يُرسَل نصّاً حرّاً أو `None`** —
   والخادم يردّه ٤٠٠. فالقيمة المرسلة **عضوٌ من التعديد**، والعربية **تسميةٌ
   للعرض** لا قيمةٌ مرسلة.
   ============================================================================== */

/** خيار تعديد: **المفتاح الآلي يُرسَل**، والعربية تُعرَض على المحامي. */
export type EnumOption = {
  /** القيمة المرسلة — عضو التعديد `.value` في وحدة الخادم. */
  value: string;
  /** التسمية العربية — للعرض وحده، **ولا تُرسَل أبداً**. */
  label: string;
};

/** `Stage` في `claims.py` — وغيابها يعني «لم يُفحَص الترتيب» لا «سليم». */
export const STAGE_OPTIONS: EnumOption[] = [
  { value: "first_instance", label: "ابتدائي" },
  { value: "appeal", label: "استئناف" },
  { value: "cassation", label: "تمييز" },
  { value: "reconsideration", label: "تعقيب / التماس إعادة نظر" },
  { value: "execution", label: "تنفيذ" },
  { value: "arbitration", label: "تحكيم" },
];

/** `Party` في `case_file.py` — لا قيمة محايدة فيها، فمن لا يعرف صفته لا يكتب. */
export const PARTY_OPTIONS: EnumOption[] = [
  { value: "claimant", label: "مدّعٍ (موكّلنا)" },
  { value: "defendant", label: "مدّعى عليه (موكّلنا)" },
];

/** `DisputeAxis` في `claims.py` — والسؤال يفرّق بين المحاور عند الخلط. */
export const AXIS_OPTIONS: EnumOption[] = [
  { value: "existence", label: "أصل الاستحقاق — هل هو ثابت أصلاً؟" },
  { value: "quantum", label: "المقدار — الاستحقاق قائم، فكم؟" },
  { value: "due", label: "حلول الاستحقاق — وهل صار مستحقّاً؟" },
  { value: "proof", label: "الإثبات — وهل يمكن إثباته؟" },
];

/** `SourceKind` في `authority.py` — وسابعها نصٌّ وثامنها تعليق لا يُقتبس كنصّ. */
export const SOURCE_KIND_OPTIONS: EnumOption[] = [
  { value: "federal_law", label: "قانون اتحادي" },
  { value: "federal_decree_law", label: "مرسوم بقانون اتحادي" },
  { value: "cabinet_decision", label: "قرار مجلس الوزراء" },
  { value: "local_law", label: "قانون محلّي" },
  { value: "ministerial_decision", label: "قرار وزاري" },
  { value: "free_zone_regulation", label: "لائحة منطقة حرّة" },
  { value: "judicial", label: "حكم أو مبدأ قضائي" },
  { value: "secondary", label: "تعليق أو ملخّص — لا يُقتبس كنصّ" },
  { value: "unknown", label: "غير مصنَّف — يُصنَّف ولا يُبنى عليه" },
];

/** `Unit` في `deadlines.py`. */
export const UNIT_OPTIONS: EnumOption[] = [
  { value: "days", label: "أيام" },
  { value: "weeks", label: "أسابيع" },
  { value: "months", label: "أشهر" },
  { value: "years", label: "سنوات" },
];

/**
 * مفاتيح `Convention` في `deadlines.py` — **والعدّ لا يُخترع**.
 *
 * ⚠️ و`_deadline_from` ترفض قاعدةً بلا `convention_key` معروف، فالاختيار
 * **إلزامي** لا افتراضي: العدّ قرارٌ قانونيّ في القاعدة لا عرفٌ في الكود.
 */
export const CONVENTION_OPTIONS: EnumOption[] = [
  {
    value: "calendar_exclusive",
    label: "العدّ التقويمي — ويوم النهاية حدٌّ لا يُحسب",
  },
  {
    value: "calendar_inclusive_end",
    label: "العدّ التقويمي — ويوم النهاية محسوب",
  },
  {
    value: "working_days",
    label: "أيام العمل — بلا عطلات نهاية الأسبوع والعطلات المورَّدة",
  },
  {
    value: "months_whole",
    label: "أشهر تقويمية كاملة — لا ثلاثين يوماً",
  },
];

/**
 * `RuleFamily` في `rules.py` — **وهي أوّل سؤال يُسأل عن كل سطر**.
 *
 * ⚠️ **وهي التي تُقرّر حكم التاريخ:** الفحص بلا تاريخ، والموضوعي بتاريخه.
   والخادم يفرض الأمرين معاً في البناء.
 */
export const RULE_FAMILY_OPTIONS: EnumOption[] = [
  { value: "verification", label: "فحصٌ عامّ على الوثيقة — ولا تاريخ له" },
  { value: "substantive", label: "حكمٌ موضوعي — بتاريخ نفاذ لازم" },
];

/** `DisputeType` في `case_file.py` — لأنواع النزاع التي تخصّها القاعدة. */
export const DISPUTE_TYPE_OPTIONS: EnumOption[] = [
  { value: "civil", label: "مدني" },
  { value: "commercial", label: "تجاري" },
  { value: "labour", label: "عمالي" },
  { value: "real_estate", label: "عقاري" },
  { value: "lease", label: "إيجاري" },
  { value: "administrative", label: "إداري" },
  { value: "criminal", label: "جزائي" },
  { value: "personal_status", label: "أحوال شخصية" },
  { value: "execution", label: "تنفيذ" },
  { value: "arbitration", label: "تحكيم" },
];

/** `CaseStage` في `case_file.py` — لمراحل التقاضي التي تسري فيها القاعدة. */
export const CASE_STAGE_OPTIONS: EnumOption[] = [
  { value: "first_instance", label: "ابتدائي" },
  { value: "appeal", label: "استئناف" },
  { value: "cassation", label: "تمييز" },
  { value: "reconsideration", label: "تعقيب / التماس إعادة نظر" },
  { value: "execution", label: "تنفيذ" },
  { value: "arbitration", label: "تحكيم" },
];

/* ==============================================================================
   حالة النموذج — والحقول هي **حقول مُحوِّلات main.py حرفياً**.
   ============================================================================== */

/** بند قائمة: الحقول المشتركة بين الطلب والدفاع (`_item`). */
export type MatrixItemForm = {
  /** معرّف آلي ثابت — به تُربط المطالبة في التقرير. */
  key: string;
  /** نصّ الطلب أو الدفع كما يُكتب في المذكرة. */
  label: string;
  /** `claimed_by` — من `Party`. */
  claimedBy: string;
  /** `axes_in_dispute` — **مجموعة لا قيمة**: الطلب يُنازَع فيه على أكثر من محور. */
  axes: string[];
  /** عناصر الاستحقاق أو أركان الدفع — سطر لكل عنصر. */
  elements: string;
  /** `supporting_facts` — مفاتيح وقائع، سطر لكل مفتاح. */
  supportingFacts: string;
  /** `opposing_facts` — مفاتيح وقائع الخصم. */
  opposingFacts: string;
  /** `evidence` — أسماء المستندات التي بين أيدينا. */
  evidence: string;
  /** `response` — الردّ القانوني على هذا البند وحده. */
  response: string;
  /** `outcome_sought` — والغياب يُقرأ تسليماً أو إغفالاً. */
  outcomeSought: string;
  /** `documents_required` — ما يلزم لإثبات ما تمسّكنا به. */
  documentsRequired: string;
};

/** دفع: بنية الطلب نفسها **وفرقٌ واحد** (`is_procedural`) — كما في `Defence`. */
export type DefenceForm = MatrixItemForm & {
  /** `is_procedural` — حكمٌ على الترتيب: الإجرائي يُقدَّم. */
  isProcedural: boolean;
};

/** سند في سجلّ الأسانيد (`_authority_from`). */
export type AuthorityForm = {
  key: string;
  /** `instrument` — اسم النظام، وبلا اسمٍ لا يُعرَف السند. */
  instrument: string;
  article: string;
  /** `kind` — من `SourceKind`. */
  kind: string;
  officialSource: string;
  /** `in_force_from` — وغيابه يعني «لم يُفحَص النفاذ» لا «نافذ». */
  inForceFrom: string;
  inForceTo: string;
  amendedBy: string;
  retrievedFrom: string;
  /** `conditions` — سطر لكل شرط. */
  conditions: string;
  /** `exceptions` — سطر لكل استثناء. */
  exceptions: string;
};

/** قاعدة موعد (`_deadline_from`). */
export type DeadlineRuleForm = {
  key: string;
  label: string;
  /** `amount` — عدد صحيح موجب، ويُرسَل رقماً لا نصّاً. */
  amount: string;
  /** `unit` — من `Unit`. */
  unit: string;
  /** `convention_key` — من `Convention`، **وإلزامي**. */
  conventionKey: string;
  source: string;
  note: string;
};

/** قاعدة (`_rule_from`). */
export type RuleForm = {
  key: string;
  /** `statement` — نصّ القاعدة، وبلا نصّ لا تُطبَّق على شيء. */
  statement: string;
  /** `family` — من `RuleFamily`، **وهي التي تحكم التاريخ**. */
  family: string;
  subject: string;
  /** `applies_to` — مفاتيح `DisputeType`، والفراغ يعني: كل الأنواع. */
  appliesTo: string[];
  /** `stages` — مفاتيح `CaseStage`، والفراغ يعني: كل المراحل. */
  stages: string[];
  source: string;
  /** `in_force_from` — **لازم للموضوعي، وممنوع على الفحص** (`rules.py`). */
  inForceFrom: string;
  /** `supersedes` — مفاتيح القواعد التي حلّت هذه محلّها. */
  supersedes: string;
  note: string;
};

/** حالة النموذج كاملاً — تُقرأ في `buildGeneratePayload` وحده. */
export type GenerateInputsState = {
  stage: string;
  ourParty: string;
  claims: MatrixItemForm[];
  defences: DefenceForm[];
  authorities: AuthorityForm[];
  deadlines: DeadlineRuleForm[];
  rules: RuleForm[];
};

/** صفٌّ فارغ — والقيم الافتراضية **معلنة** لا صامتة. */
export function emptyMatrixItem(): MatrixItemForm {
  return {
    key: "",
    label: "",
    // ⚠️ والافتراضي `claimant` **معلنٌ في النموذج** لا مُخمَّن في الكود:
    // الحقل لا يُرسَل `None` أبداً، فالسقوط على `_party_of` لا يقع.
    claimedBy: "claimant",
    axes: [],
    elements: "",
    supportingFacts: "",
    opposingFacts: "",
    evidence: "",
    response: "",
    outcomeSought: "",
    documentsRequired: "",
  };
}

export function emptyDefence(): DefenceForm {
  return { ...emptyMatrixItem(), isProcedural: false };
}

export function emptyAuthority(): AuthorityForm {
  return {
    key: "",
    instrument: "",
    article: "",
    // ⚠️ والافتراضي `UNKNOWN` («لم يُصنَّف») لا `SECONDARY` — وهي تُعرَض في
    // `unsourced` لتُصنَّف، ولا يُبنى على تصنيف غائب حكم.
    kind: "unknown",
    officialSource: "",
    inForceFrom: "",
    inForceTo: "",
    amendedBy: "",
    retrievedFrom: "",
    conditions: "",
    exceptions: "",
  };
}

export function emptyDeadlineRule(): DeadlineRuleForm {
  return {
    key: "",
    label: "",
    amount: "",
    unit: "days",
    // ⚠️ ولا افتراض للعدّ: المحامي يختاره، والإفراغ يُوقف الإرسال بنصّ صريح.
    conventionKey: "",
    source: "",
    note: "",
  };
}

export function emptyRule(): RuleForm {
  return {
    key: "",
    statement: "",
    // ⚠️ والافتراضي `verification` **موافقٌ لسقوط `_family_of`** — فلا يفترق
    // ما يعرضه النموذج عمّا يبنيه الخادم عند الغياب.
    family: "verification",
    subject: "",
    appliesTo: [],
    stages: [],
    source: "",
    inForceFrom: "",
    supersedes: "",
    note: "",
  };
}

export function emptyGenerateInputs(): GenerateInputsState {
  return {
    stage: "",
    ourParty: "",
    claims: [],
    defences: [],
    authorities: [],
    deadlines: [],
    rules: [],
  };
}

/* ==============================================================================
   من الحالة إلى حمل الطلب — **والحكم على المدخل لا على المخرج**.
   ============================================================================== */

/** حمل `POST /generate` كما يقرأه `_matrix_from_payload` وأخواتها في main.py. */
export type GeneratePayload = {
  /** `_matrix_from_payload` — وإحدى القائمتين على الأقل لازمة وإلا رُدّ الطلب ٤٠٠. */
  claims?: {
    claims?: Record<string, unknown>[];
    defences?: Record<string, unknown>[];
    /** القيمة من `Stage` — **وغيابها يعني «لم يُفحَص» لا «سليم»**. */
    stage?: string;
    our_party?: string;
  };
  /** `_register_from_payload` — قائمة لازمة غير فارغة. */
  authority?: { authorities?: Record<string, unknown>[] };
  /** `_deadlines_from_payload` — القواعد يكتبها المحامي، والمنصّة تحسب ولا تخترع. */
  deadlines?: { rules?: Record<string, unknown>[] };
  /** `_rules_from_payload` — والسجلّ الفارغ يُعلَن فارغاً لا ناجحاً. */
  rules?: { rules?: Record<string, unknown>[] };
};

/** نتيجة البناء: حملٌ، أو نصُّ سببٍ يمنع الإرسال. */
export type BuildResult =
  | { ok: true; payload: GeneratePayload }
  | { ok: false; message: string };

/** سطور غير فارغة — **والفراغ لا يُنتج عنصراً فارغاً في قائمة**. */
function lines(value: string): string[] {
  return value
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
}

/** مصفوفة نصّية، أو الغياب إن فرغت — وهي صورة `_tokens` في main.py. */
function list(value: string): string[] | undefined {
  const items = lines(value);
  return items.length ? items : undefined;
}

const trimmed = (value: string): string => value.trim();

/** مفتاح الحذف: هل الحقل فارغاً؟ (يُستعمل للتشذيب والتحقّق معاً) */
const has = (value: string): boolean => trimmed(value).length > 0;

/** صيغة التاريخ المعتمدة في `rules.py`: `DATE_FORMAT` = ISO-8601. */
const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;

/**
 * هل يصلح هذا البند للإرسال؟ **وعند الصلاح ينفرد `_item` بالقرار**.
 *
 * ⚠️ والشرطان هما شرطا `_item` حرفياً: مفتاحٌ ونصّ. ولو أُرسل ناقصاً لرُدّ
 * الطلب ٤٠٠ **بعد** أن يُدفع ثمنُ نداء نموذج… بل قبل التوليد، لكن بعد أن
 * يكتب المحامي وقائعه — فالرفض المحلّي أهون من ٤٠٠ بعد كتابة.
 */
function itemReady(item: MatrixItemForm): boolean {
  return has(item.key) && has(item.label);
}

/** صفٌّ بدأه المحامي ولم يكمله — **وهو الذي يُوقف الإرسال بنصّ**. */
function itemPartial(item: MatrixItemForm): boolean {
  return (has(item.key) || has(item.label)) && !itemReady(item);
}

function authorityReady(a: AuthorityForm): boolean {
  return has(a.key) && has(a.instrument);
}

function deadlineReady(d: DeadlineRuleForm): boolean {
  if (!has(d.key) || !has(d.label) || !has(d.unit) || !has(d.conventionKey)) {
    return false;
  }
  return /^\d+$/.test(d.amount.trim()) && Number(d.amount) > 0;
}

/** تاريخ النفاذ: يُفحص هنا **بالصيغة** لأن `rules.py` يرفض غير ISO في البناء. */
function ruleReady(r: RuleForm): boolean {
  if (!has(r.key) || !has(r.statement) || !has(r.family)) return false;
  if (r.family === "substantive") return ISO_DATE.test(r.inForceFrom.trim());
  return true;
}

/**
 * نصّ المنع — أو `null` إن صلحت المدخلات كلها.
 *
 * ⚠️ **ولا يُبنى هنا حكمٌ قانونيّ، بل يُمنع ما يردّه الخادم بعينه**: بندٌ ناقص
 * (مفتاحٌ بلا نصّ) · عدّ غير مختار · مقدارٌ ليس عدداً موجباً · حكمٌ موضوعي بلا
 * تاريخ نفاذ — **وفحصٌ بتاريخ نفاذ** (وهو ممنوع في `rules.py` صراحةً).
 */
export function describeInputProblems(state: GenerateInputsState): string | null {
  const problems: string[] = [];

  const partialClaims = state.claims.filter(itemPartial).length;
  const partialDefences = state.defences.filter(itemPartial).length;
  if (partialClaims + partialDefences > 0) {
    problems.push(
      "طلبٌ أو دفعٌ بلا مفتاح أو بلا نصّ — والخادم يردّه: المفتاح هو ما يُربط به الدفع، والنصّ هو ما يُقرأ في المصفوفة."
    );
  }

  for (const a of state.authorities) {
    const started = has(a.key) || has(a.instrument);
    if (started && !authorityReady(a)) {
      problems.push(
        `سندٌ بلا مفتاح أو بلا اسم نظام («${trimmed(a.key) || "—"}») — وبلا اسمٍ لا يُعرَف السند.`
      );
    }
  }

  for (const d of state.deadlines) {
    const started =
      has(d.key) || has(d.label) || has(d.amount) || has(d.conventionKey);
    if (!started) continue;
    if (!has(d.conventionKey)) {
      problems.push(
        `قاعدة الموعد «${trimmed(d.key) || "—"}»: العدّ غير مختار — ولا يُخترع عدّ.`
      );
    } else if (!deadlineReady(d)) {
      problems.push(
        `قاعدة الموعد «${trimmed(d.key) || "—"}»: مفتاحٌ ونصّ ومقدارٌ صحيحٌ موجب ووحدة، كلّها لازمة.`
      );
    }
  }

  for (const r of state.rules) {
    const started =
      has(r.key) || has(r.statement) || has(r.inForceFrom) || has(r.family);
    if (!started) continue;
    if (r.family === "substantive" && !has(r.inForceFrom)) {
      problems.push(
        `القاعدة «${trimmed(r.key) || "—"}»: حكمٌ موضوعي بلا تاريخ نفاذ — والحكم الذي لا تاريخ له يصير قانوناً ملغى يبدو سارياً.`
      );
    } else if (r.family !== "substantive" && has(r.inForceFrom)) {
      problems.push(
        `القاعدة «${trimmed(r.key) || "—"}»: فحصٌ بتاريخ نفاذ — والفحص لا يتبدّل إذا تبدّل التشريع، فالتاريخ عليه يوهم بأنه سيُراجَع.`
      );
    } else if (!ruleReady(r)) {
      problems.push(
        `القاعدة «${trimmed(r.key) || "—"}»: مفتاحٌ ونصّ وعائلة، كلّها لازمة، وتاريخ النفاذ بصيغة YYYY-MM-DD.`
      );
    }
  }

  return problems.length ? problems.join(" · ") : null;
}

/** الطلب أو الدفع — **بأسماء `_item` حرفياً**. */
function matrixItemBody(item: MatrixItemForm): Record<string, unknown> {
  const body: Record<string, unknown> = {
    key: trimmed(item.key),
    label: trimmed(item.label),
    claimed_by: item.claimedBy,
  };
  // ⚠️ وغياب القائمة **لا يعني قائمة فارغة**: الحقل الفارغ لا يُرسَل، فـ`_tokens`
  // تُعيد `()` للغياب كما تُعيدها للنصّ الفارغ بلا فرق، لكن الحقل الذي لم
  // يُدخَل لا يُوهم بأنه أُدخِل فارغاً في سجلّ الطلب.
  const axes = item.axes.filter(Boolean);
  if (axes.length) body.axes_in_dispute = axes;
  const fields: [string, string][] = [
    ["elements", item.elements],
    ["supporting_facts", item.supportingFacts],
    ["opposing_facts", item.opposingFacts],
    ["evidence", item.evidence],
    ["documents_required", item.documentsRequired],
  ];
  for (const [name, value] of fields) {
    const items = list(value);
    if (items) body[name] = items;
  }
  const response = trimmed(item.response);
  if (response) body.response = response;
  const outcome = trimmed(item.outcomeSought);
  if (outcome) body.outcome_sought = outcome;
  return body;
}

/** `buildGeneratePayload` — **والفراغ يبقى غائباً لا كائناً فارغاً**.
 *
 * ⚠️⚠️ **وهذا هو الفرق الذي يمنع ٤٠٠**: `{}` في `claims` يعني «حملُ مصفوفة»
 * بلا طلبات ولا دفوع، فيرفضه `_matrix_from_payload` برسالته. أما **غياب
 * المفتاح** فيعني «لم يُدخَل»، فتُبنى اللوحة بـ`built: false` **وتقول ذلك**.
 * وهو الصدق نفسه: «لم تُبنَ» لا «فُحصت فسلمت».
 */
export function buildGeneratePayload(state: GenerateInputsState): BuildResult {
  const problems = describeInputProblems(state);
  if (problems) return { ok: false, message: problems };

  const payload: GeneratePayload = {};

  const claims = state.claims.filter(itemReady).map(matrixItemBody);
  const defences = state.defences.filter(itemReady).map((d) => ({
    ...matrixItemBody(d),
    is_procedural: d.isProcedural,
  }));
  if (claims.length || defences.length) {
    const matrix: NonNullable<GeneratePayload["claims"]> = {};
    if (claims.length) matrix.claims = claims;
    if (defences.length) matrix.defences = defences;
    // ⚠️ والمرحلة والصفة **لا تُرسَلان فارغتين**: الغياب يعني «لم يُفحَص
    // الترتيب» و«لم تُعرَف الصفة» — وهما معلومتان في الخادم، لا نصٌّ فارغ.
    if (has(state.stage)) matrix.stage = state.stage;
    if (has(state.ourParty)) matrix.our_party = state.ourParty;
    payload.claims = matrix;
  }

  const authorities = state.authorities.filter(authorityReady).map((a) => {
    const body: Record<string, unknown> = {
      key: trimmed(a.key),
      instrument: trimmed(a.instrument),
      kind: a.kind,
    };
    const texts: [string, string][] = [
      ["article", a.article],
      ["official_source", a.officialSource],
      ["in_force_from", a.inForceFrom],
      ["in_force_to", a.inForceTo],
      ["amended_by", a.amendedBy],
      ["retrieved_from", a.retrievedFrom],
    ];
    for (const [name, value] of texts) {
      const text = trimmed(value);
      if (text) body[name] = text;
    }
    const conditions = list(a.conditions);
    if (conditions) body.conditions = conditions;
    const exceptions = list(a.exceptions);
    if (exceptions) body.exceptions = exceptions;
    return body;
  });
  if (authorities.length) payload.authority = { authorities };

  const deadlines = state.deadlines.filter(deadlineReady).map((d) => ({
    key: trimmed(d.key),
    label: trimmed(d.label),
    // ⚠️ **رقمٌ لا نصّ**: `_deadline_from` تنادي `int(raw.get("amount"))`،
    // ونصٌّ عربيٌّ بأرقام عربية-هندية يرفع `ValueError`.
    amount: Number(d.amount),
    unit: d.unit,
    convention_key: d.conventionKey,
    ...(has(d.source) ? { source: trimmed(d.source) } : {}),
    ...(has(d.note) ? { note: trimmed(d.note) } : {}),
  }));
  if (deadlines.length) payload.deadlines = { rules: deadlines };

  const rules = state.rules.filter(ruleReady).map((r) => {
    const body: Record<string, unknown> = {
      key: trimmed(r.key),
      statement: trimmed(r.statement),
      family: r.family,
    };
    if (has(r.subject)) body.subject = trimmed(r.subject);
    if (r.appliesTo.length) body.applies_to = r.appliesTo.filter(Boolean);
    if (r.stages.length) body.stages = r.stages.filter(Boolean);
    if (has(r.source)) body.source = trimmed(r.source);
    // ⚠️ والتاريخ يُرسَل **للموضوعي وحده**: إرساله على فحصٍ يرفعه `rules.py`
    // في البناء، وإسقاطه عن موضوعي يرفعه أيضاً — والحرسان واحد.
    if (r.family === "substantive" && has(r.inForceFrom)) {
      body.in_force_from = trimmed(r.inForceFrom);
    }
    const supersedes = list(r.supersedes);
    if (supersedes) body.supersedes = supersedes;
    if (has(r.note)) body.note = trimmed(r.note);
    return body;
  });
  if (rules.length) payload.rules = { rules };

  return { ok: true, payload };
}
