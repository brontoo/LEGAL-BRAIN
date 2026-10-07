"use client";

import { useRef, useState } from "react";
import { motion, AnimatePresence } from "motion/react";
import {
  Send,
  FileText,
  Loader2,
  CheckCircle,
  Scale,
  AlertTriangle,
  ShieldCheck,
  ShieldAlert,
  Unlink,
  // مدخلات الفحوص الأربعة: طيّ المجموعات وإضافة البنود وحذفها.
  ChevronDown,
  Plus,
  Trash2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { OfficeScene, TeamStrip } from "@/components/office-scene";
import { ReviewPanel, type ReviewReport } from "@/components/review-panel";
// ⚠️ منظّف مخلفات Markdown — وحدة مستقلّة، لأن جواب `/chat` يستعمله أيضاً.
// انظر التعليق عند موضع الاستدعاء أدناه.
import { stripMarkdownArtifacts } from "@/lib/strip-markdown";
// مدخلات الفحوص الأربعة — الحساب هناك بلا JSX ليُقاس بالتشغيل، والعرض هنا.
import {
  AXIS_OPTIONS,
  CASE_STAGE_OPTIONS,
  CONVENTION_OPTIONS,
  DISPUTE_TYPE_OPTIONS,
  PARTY_OPTIONS,
  RULE_FAMILY_OPTIONS,
  SOURCE_KIND_OPTIONS,
  STAGE_OPTIONS,
  UNIT_OPTIONS,
  buildGeneratePayload,
  describeInputProblems,
  emptyAuthority,
  emptyDeadlineRule,
  emptyDefence,
  emptyGenerateInputs,
  emptyMatrixItem,
  emptyRule,
  type AuthorityForm,
  type DeadlineRuleForm,
  type DefenceForm,
  type EnumOption,
  type GenerateInputsState,
  type MatrixItemForm,
  type RuleForm,
} from "./generate-inputs";

// كل النداءات تمر عبر وسيط Next.js على /api — انظر app/api/[...path]/route.ts
//
// لماذا وسيط وليس عنوان الخادم مباشرة؟
//   ١) رمز المصادقة (API_TOKEN) يبقى على الخادم ولا يصل إلى المتصفح إطلاقاً.
//      لو وضعناه في متغيّر NEXT_PUBLIC_ لرآه أي زائر في مصدر الصفحة.
//   ٢) المتصفح يخاطب نفس الأصل، فتختفي مشكلة CORS كلياً.
//   ٣) عنوان الخادم الحقيقي لم يعد جزءاً من حزمة الواجهة.
const API_URL = "/api";

// مهلة قصوى لتوليد المستند (المستندات الطويلة تستغرق وقتاً)
/*
 * ⚠️ **والمهلة ارتفعت من ٣ دقائق إلى ١٠ — بعد أن صارت المراجعة الثانية جزءاً
 * من المسار.**
 *
 * وكانت ١٨٠٠٠٠ مللي بالضبط، والتوليد استغرق **٣.٠ دقيقة بالضبط** — فانتهت
 * المهلة **قبل أن يكتمل الختم**، وظهر للمستخدم «تعذّر إتمام الصياغة» **بعد أن
 * كان الخادم قد أنجز العمل فعلاً** (`POST /generate 200 OK`).
 *
 * ⚠️ وهو أسوأ خطأ في تجربة الاستخدام: **العمل ينجح ويُعرَض فاشلاً** — فيُعيد
 * المحامي المحاولة فيُهدر نداءين لا واحداً.
 *
 * ⚠️ والعلاج الصحيح ليس رفع الرقم بل **إعادة ضبط المهلة عند كل إطار يصل**
 * (فالخادم يُرسل مرحلة كل ثوانٍ). وهذا يحتاج تعديلاً في موضع الاستماع للبثّ،
 * **ويُترك لخطوة تالية** — ورفع السقف يُغلق الأثر الآن.
 */
const GENERATION_TIMEOUT_MS = 600_000;

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

/** ملاحظة واحدة من «سيبويه المُكشّر» — التدقيق اللغوي. */
type LanguageFinding = {
  kind: string;
  severity: "error" | "notice";
  message: string;
  sample: string;
  line: number | null;
};

/** تقرير التدقيق اللغوي — فحص حتمي لا نموذج (انظر language_audit.py). */
type LanguageReport = {
  summary: string;
  clean: boolean;
  error_count: number;
  notice_count: number;
  findings: LanguageFinding[];
};

/* ==============================================================================
   الأنواع — تُقرأ من `main.py` حقلاً بحقل، لا تُخمَّن.
   ============================================================================== */

/**
 * ملف القضية — إطار `case`، **أول إطار يُبثّ**.
 *
 * انظر `_case_frame` في main.py، و`CaseFile.summary` في case_file.py.
 *
 * ⚠️ و`established` هو مفتاح الحال الثلاثي، والأهمّ في الإطار كله: الخادم
 * يُرسله `false` حين لا يُبنى ملف أصلاً (بلا حمل، أو حمل لا يكفي)، ومعناه
 * **لم يُفحص** لا **فُحص فسلم** — وهذا الفرق هو كل الفائدة.
 *
 * ⚠️ و`confirmed` و`missing` **مفاتيح آلية** (`"dispute_type"` · `"claims"`)
 * لا نصوص عربية، فتُترجم للعرض في `FIELD_LABELS` أدناه، ويُربط بها لا بالنصّ.
 */
type CaseField = string;

type CaseFrame = {
  /** `false` ⇒ لم يُبنَ ملف قضية: لا يُعرض «مكتمل» ولا «ناقص»، بل «لم يُفحص». */
  established: boolean;
  requested: boolean;
  /** سبب الغياب كما صاغه الخادم (`CASE_BLOCK_ABSENT` أو `…_UNBUILDABLE`). */
  message: string;
  case: CaseSummary | null;
  confirmed: CaseField[];
  missing: CaseField[];
  is_complete: boolean;
  questions: CaseQuestion[];
  regime_notes: CaseRegimeNote[];
  summary: CaseSummary | null;
};

/** سؤال ناقص ينتظر جواب المحامي — `question` · `why` · `blocking`. */
type CaseQuestion = {
  field: string;
  question: string;
  why: string;
  /** حقل مانع: نقصه يوقف الصياغة (`BLOCKING_FIELDS` في case_file.py). */
  blocking: boolean;
};

/**
 * ملاحظة نظام من `regime_notes` — تُعرض بـ`note` و`source` و`limit` **لا
 * بـ`area` و`trigger`**: المفتاحان الآليان (`free_zone` · إلخ) للربط، وهما
 * مصطلح داخلي لا يُقحم في نصّ يُقرأ.
 */
type CaseRegimeNote = {
  area: string;
  trigger: string;
  note: string;
  source: string;
  limit: string;
};

/** ملخّص الملف كما يُبثّ — `CaseFile.summary` في case_file.py حرفياً. */
type CaseSummary = {
  country: string;
  emirate: string;
  emirate_key: string;
  forum: string;
  forum_key: string;
  dispute_type: string;
  stage: string;
  our_party: string;
  claims: string[];
  /** أزواج `[التسمية، القيمة]` — كما بُنيت في الوحدة، بلا إعادة ترتيب. */
  key_dates: string[][];
  likely_law: string[];
  has_arbitration_clause: boolean | null;
  has_choice_of_law: boolean | null;
  confirmed: string[];
  missing: string[];
  blocking_missing: string[];
  complete: boolean;
};

/** واقعة واحدة في السجلّ — `_fact_payload` في facts.py. */
type FactEntry = {
  key: string;
  statement: string;
  source: string;
  locus: string;
  date: string;
  asserted_by: string;
  /** قيمة آلية من `Standing`: `agreed` · `claimed` · `disputed` · `inferred` · `uncertain`. */
  standing: string;
  /** التسمية العربية التي أرسلها الخادم مع المفتاح — لا تُعاد صياغتها. */
  standing_label: string;
  quote: string;
  subject: string;
  version: string;
};

/**
 * افتراق واقعة عن المسودّة — **أخطر ما يعرضه إطار `facts`**، `FactShift`
 * في facts.py.
 *
 * ⚠️ و`kind` قيمة آلية (`missing` · `reworded` · `contradicted`) تُترجم في
 * `SHIFT_LABELS`، ولا يُبنى العرض على `note` العربية لأنها تُحرَّر.
 */
type FactShift = {
  fact_key: string;
  kind: string;
  draft_text: string;
  fact_statement: string;
  note: string;
};

/** سجلّ الوقائع ونتيجة الفحص — `facts.summarize` كما يُبثّ. */
type FactsLedgerPayload = {
  summary: string;
  fact_count: number;
  by_standing: Record<string, number>;
  conflict_count: number;
  conflicts: {
    subject: string;
    first: FactEntry;
    second: FactEntry;
  }[];
  version_conflict_count: number;
  version_conflicts: {
    document: string;
    note: string;
    versions: {
      version: string;
      date: string;
      signed: boolean | null;
      implied: boolean | null;
      note: string;
    }[];
  }[];
  needs_verification: FactEntry[];
  unquoted: string[];
  shifts: FactShift[];
  rules: {
    client_statement_is_not_proof: string;
    opponent_pleading_is_not_evidence: string;
  };
};

/**
 * إطار `facts` — `_facts_frame` في main.py.
 *
 * ⚠️ و`ran` هو المفتاح: `false` تعني أنّ السجلّ **لم يُرسل مع الطلب**، فلم
 * يقابل الفحصُ المسودّةَ بشيء. و`ledger: null` معها — والشكل نفسه يقول
 * «لم يُشغَّل» فلا يُرسم سجلّ فارغ يُقرأ نظافة.
 */
type FactsFrame = {
  ran: boolean;
  /** نصّ `FACTS_NOT_RUN` من الخادم حين لم يُشغَّل — يُعرض بنصّه لا بإعادة كتابة. */
  message: string;
  ledger: FactsLedgerPayload | null;
  shifts: FactShift[];
};

/**
 * مصدر واحد في التقرير الداخلي — `Source` في briefing.py.
 *
 * ⚠️ و`errors` و`notices` **قد تكون `null`**: «لم يُبلَّغ عن عدد» غير «صفر
 * خطأ». فالواجهة تعرض «—» ولا تعرض صفراً لم يُبلَّغ به الخادم.
 */
type BriefingSource = {
  kind: string;
  label: string;
  /** `false` ⇒ الفحص **لم يُشغَّل**، وهو الحال الثالث الذي لا يُقرأ سلامة. */
  present: boolean;
  summary: string;
  errors: number | null;
  notices: number | null;
};

/**
 * إطار `briefing` — التقرير الداخلي، **أحد سلَمَي المنتج**.
 *
 * ⚠️ والنصّ `markdown` هو الذي يُعرض، لا القاموس: `to_markdown` في briefing.py
 * هي الموضع الوحيد الذي يُبنى فيه الشكل، وإعادة بناءه في جافاسكربت تُنتج
 * **تنسيقين ينحرفان بصمت** عند أوّل تعديل. والقاموس يُقرأ لشيء واحد لا يحمله
 * النصّ: حال كل مصدر (`present`) لأعرف ما **لم يُشغَّل** بمفتاحه الآلي.
 */
type BriefingFrame = {
  report: {
    /** `verified` · `partly_verified` · `unverified` — مفاتيح `readiness`. */
    safety: string;
    headline: string;
    gaps: string[];
    risks: string[];
    conflicts: string[];
    alternatives: string[];
    needs_review: string[];
    unverified_claims: number;
    open_questions: string[];
    generated_at: string | null;
    sources: BriefingSource[];
  };
  markdown: string;
};

/**
 * خطأ واحد في قائمة `revision` — **خمسة حقول نصّية لا كائن مُنمَّط**.
 *
 * ⚠️ وسبب بقائه نصّاً هو `_revision_frame` في main.py: الإطار يُسلسل إلى JSON
 * ليُبثّ عبر SSE، فحُوّل الخام إلى حقول قبل البناء. ولذلك لا يوجد هنا
 * `action` ولا `fixable_by_redraft` — وكلاهما قرار الحلقة لا عرضٌ للمحامي،
 * ولو استُنتجا في الواجهة لصار في المشروع حاكمان يفترقان.
 *
 * ⚠️ و`source` و`kind` و`severity` **مفاتيح آليّة تُعرض كما هي**: لا تُترجم
 * إلى عبارة عربية يُبنى عليها حكم. فالترجمة تنكسر بصمت في أول تعديل تحريري،
 * والقاعدة نفسها معلنة في `FIELD_LABELS` أعلاه.
 */
type LoopError = {
  source: string;
  kind: string;
  severity: string;
  message: string;
  quote: string;
};

/** إطار `revision` — قائمة الأخطاء المُوحَّدة، وما إذا جُمِعت أصلاً. */
type RevisionFrame = {
  errors: LoopError[];
  checked_sources: string[];
  redrafted: boolean;
  collected: boolean;
  message: string;
  /**
   * ⚠️ **الحقول الثلاثة أدناه وصلت مع المراجعة الثانية، وأثرها في اللوحة أثرٌ
   * لا يُسكَت عنه**:
   *
   *  • `redrafted: true` تعني **أُنتج نصٌّ ثانٍ** — لا أنّ الخطأ زال. فالفحوص
   *    أعلاه تصف مسودّةً **لم تعد المعروضة**، والإعادة **تُفحَص ولا تُفترَض**
   *    (انظر التعليق على `final_draft` في `main.py`).
   *  • `stop_code` و`stopped_reason` يقولان **لماذا وقفت الحلقة**، ومنه بلوغ
   *    سقف المحاولات (`redraft_attempts`) — وهو موضع يُقرأ فيه «توقّف» لا «نجح».
   *
   * ⚠️ وكلها اختيارية في النوع لأن إطاراً قادماً من خادم أقدم لا يحملها،
   * **وغيابها لا يُترجم إلى «لم تُجرَ محاولة»** بل إلى «لم يُبلَّغ» (القاعدة
   * نفسها في `BriefingSource`: الغائب «—» لا صفر).
   */
  /** عدد المحاولات التي استُهلكت — و`> 1` هي التي تعني «أُنتج نصٌّ ثانٍ». */
  redraft_attempts?: number | null;
  stop_code?: string | null;
  stopped_reason?: string | null;
};

/* ==============================================================================
   الإطارات الأربعة التي كانت تُبثّ وتُسقَط — أنواعها من بواني `main.py` حقلاً بحقل.
   ============================================================================== */

/**
 * نتيجة فحص واحد في إطار `claims` — `_flat` في `_claims_frame`.
 *
 * ⚠️ **ولا كائن مُنمَّط هنا**: الإطار يُسلسل إلى JSON للبثّ عبر SSE، فحُوّل
 * ُالخام إلى حقول نصّية. و`kind` و`code` مفتاحان آليّان يُعرضان كما هما (القاعدة
 * نفسها في `LoopError`).
 *
 * ⚠️ و`note` **قد تكون `null`**: تُعرض إن وُجدت، ولا يُخترع لها نصّ.
 */
type FindingEntry = {
  code: string;
  severity: string;
  message: string;
  item_key: string;
  kind: string;
  note: string | null;
};

/** ملخّص المصفوفة — `summarize` في claims.py، **يُعرض بمفاتيحه التي أرسلها الخادم**. */
type ClaimsSummary = Record<string, string | number | null>;

/**
 * إطار `claims` — مصفوفة الطلبات والدفوع، `_claims_frame` في main.py.
 *
 * ⚠️ **و`built` هو المفتاح، لا القائمة**: `false` تعني أنّ المصفوفة **لم تُبنَ**
 * (لا حمل، أو فشل بناء)، والقائمة الفارغة حينها **ليست «لا أخطاء»** — وهو
 * الفرق نفسه الذي وُلدت له `collected` في `RevisionFrame`، وقد تكرّر خطؤه.
 *
 * ⚠️ و`stage` **قد تكون `null`**: ومصفوفةٌ بلا مرحلة تُبنى **ويُعلَن أن فحص
 * المخالفة لم يجرِ** — خيرٌ من ادّعاء انطباق بلا مرحلة.
 */
type ClaimsFrame = {
  built: boolean;
  message: string;
  /** `null` حين لا ملخّص — لا `{}` يُقرأ «صفر». */
  summary: ClaimsSummary | null;
  errors: FindingEntry[];
  notices: FindingEntry[];
  stage: string | null;
  checked_sources: string[];
};

/** فحص انطباق سند واحد — `checks[]` في `_authority_frame`. */
type AuthorityCheck = {
  key: string;
  instrument: string;
  article: string;
  /** `applicable` · `inapplicable` · `unverified` — و`unverified` تعني **لم يُفحَص**. */
  status: string;
  reason: string;
  conditions: string[];
  /** **قد يكون غائباً**: يُملأ في مسار الفحص فقط، وغيابه ليس «كلها مستوفاة». */
  unmet?: string[];
};

/**
 * خطأ أو ملاحظة في إطارات `authority` · `deadlines` · `rules`.
 *
 * ⚠️ **وثلاثة أحكام في `authority` لا تُدمج، والتمييز بينها هو فائدة الإطار:**
 *   • `out_of_force` — سندٌ لم يكن سارياً في تاريخ الإيداع: **خطأ**.
 *   • `secondary_as_primary` — مصدرٌ ثانويّ عُومل معاملة النصّ: **خطأ**.
 *   • `unsourced` — سندٌ بلا مصدر رسمي: **ملاحظة**، تُعلَن ولا تُعرض كأنها محقَّقة.
 * ولذلك تُعرض الخطورة **بالقائمة التي ورد فيها العنصر** (errors أو notices) وبـ`kind`
 * الآلي — ولا تُستنتج من نصّ عربي.
 *
 * ⚠️ **وكل حقل عدا `kind` اختياري بقصد**: الإطارات الثلاثة تُنتج أشكالاً مختلفة
 * (`a`/`b` للتعارض · `quote`/`why` للتمييز · `key` للملاحظة)، **والحقل الغائب
 * لا يُعرض** بدل أن يُخترع له موضع أو قيمة. والقارئ لا يفترض شكلاً واحداً.
 */
type FrameEntry = {
  /** المفتاح الآلي للتصنيف — يُعرض كما هو ولا يُترجم. */
  kind: string;
  message?: string;
  key?: string;
  instrument?: string;
  article?: string;
  source?: string;
  /** طرفا تعارض قاعدتين في `rules` — **ولا يُختار بينهما تلقائياً**. */
  a?: string;
  b?: string;
  /** موضع الخلل من المسودّة في `rules`, يُعرض كما هو ليُقابله المحامي بنصّه. */
  quote?: string;
  why?: string;
};

/** إطار `authority` — الفحص الزمنيّ وشروط الانطباق، `_authority_frame` في main.py. */
type AuthorityFrame = {
  built: boolean;
  message: string;
  summary: ClaimsSummary | null;
  checks: AuthorityCheck[];
  errors: FrameEntry[];
  notices: FrameEntry[];
  checked_sources: string[];
};

/** موعد محسوب واحد — `items[]` في `_deadlines_frame`. */
type DeadlineItem = {
  key: string;
  label: string;
  /** `YYYY-MM-DD` — يُعرض `dir="ltr"` لنفس سبب `key`. */
  due: string;
  from: string;
  amount: number;
  unit: string;
  convention: string;
  source: string;
  described: string;
};

/** إطار `deadlines` — العدّ الذي لا يُخترع، `_deadlines_frame` في main.py. */
type DeadlinesFrame = {
  built: boolean;
  message: string;
  items: DeadlineItem[];
  /** ⚠️ في هذه الدالة `errors` **تُبنى فارغةً دائماً** — فلا يُقرأ فراغها سلامة. */
  errors: FrameEntry[];
  notices: FrameEntry[];
  checked_sources: string[];
};

/** قاعدة واحدة في السجلّ — `rules[]` في `_rules_frame`. */
type RuleItem = {
  key: string;
  statement: string;
  source: string;
  in_force_from: string;
};

/** ملاحظة تمييز في المسودّة — `findings[]` في `_rules_frame`. */
type RuleFinding = { kind: string; quote: string };

/** إطار `rules` — ما ينطبق وما يتعارض وما يستلزم مراجعة، `_rules_frame` في main.py. */
type RulesFrame = {
  built: boolean;
  message: string;
  rules: RuleItem[];
  summary: ClaimsSummary | null;
  conflicts: { a: string; b: string }[];
  must_review: RuleItem[];
  findings: RuleFinding[];
  errors: FrameEntry[];
  notices: FrameEntry[];
  checked_sources: string[];
};

type StreamEvent =
  | { type: "stage"; stage?: string; message: string }
  | { type: "case"; report: CaseFrame }
  | { type: "citations"; report: CitationsReport }
  | { type: "language"; report: LanguageReport }
  | { type: "review"; report: ReviewReport }
  | { type: "facts"; report: FactsFrame }
  // ⚠️ الأربعة أدناه تُبثّ **بعد `facts` وقبل `revision`**، وهي ترتيب
  // `_stream_agent` في main.py: الوقائع ← المصفوفة ← الأسانيد ← المواعيد ←
  // القواعد ← قائمة الأخطاء الموحّدة ← التقرير. وكانت تُبثّ وتُسقَط هنا بصمت.
  | { type: "claims"; report: ClaimsFrame }
  | { type: "authority"; report: AuthorityFrame }
  | { type: "deadlines"; report: DeadlinesFrame }
  | { type: "rules"; report: RulesFrame }
  | { type: "briefing"; report: BriefingFrame["report"]; markdown: string }
  | { type: "revision"; report: RevisionFrame }
  | { type: "done"; document: string }
  | { type: "error"; message: string };

/**
 * ⚠️ **وقد بُنيت المدخلات — فانتَقل الحمل وبناؤه إلى `./generate-inputs`.**
 *
 * وسببُ نقله من هنا: أن **يُقاس بالتشغيل لا بالقراءة**. فالحساب هناك بلا JSX
 * وبلا React، فيُشغَّل في Node مباشرة (`scripts/check-generate-inputs.mjs`)
 * ويُقاس شكلُ الحمل: المفاتيح الأربعة بأسماء مُحوِّلات `main.py`، وقيمُ
 * التعديد بأعضاء وحدات الخادم، **وغيابُ المفتاح عند الفراغ**.
 *
 * ⚠️ وحقول كل بند — من `_item` و`_authority_from` و`_deadline_from`
 * و`_rule_from` في main.py، وهي مرجعٌ لا يُخالَف:
 *
 *  • الطلب/الدفاع: `key` · `label` · `claimed_by` · `elements` ·
 *    `supporting_facts` · `opposing_facts` · `evidence` · `axes_in_dispute` ·
 *    `response` · `outcome_sought` · `documents_required` · `is_procedural`
 *    (و`burden` يُبنى `UNKNOWN` في الخادم ولا يُرسَل).
 *  • السند: `key` · `instrument` · `article` · `kind` · `official_source` ·
 *    `in_force_from` · `in_force_to` · `amended_by` · `retrieved_from` ·
 *    `conditions` · `exceptions`.
 *  • قاعدة الموعد: `key` · `label` · `amount` · `unit` · `convention_key` ·
 *    `source` · `note`.
 *  • القاعدة: `key` · `statement` · `family` · `subject` · `applies_to` ·
 *    `stages` · `source` · `in_force_from` · `supersedes` · `note`.
 */

/** ما يُرجعه `POST /revisions` بعد حفظ التصحيح. */
type RevisionSaveResult = {
  saved: boolean;
  edit_ratio: number;
  quality_band: string;
  word_count: number;
};

/*
 * ⚠️ **ونُقل المنظّف إلى `lib/strip-markdown.ts` — والسبب تبعية لا ترتيب.**
 *
 * صار للمنظّف مستدعيان: هذه الصفحة وجواب `/chat`. وبقاؤه هنا كان يجعل المحادثة
 * **تستورد صفحة مساحة الصياغة كلها** (ومعها `office-scene` و`review-panel`)
 * لأجل دالّة نصّية — أي حزمة متصفّح منتفخة بلا سبب. والاستيراد من هناك يجعل
 * الاستدعاء واحداً والتبعيات نظيفة. والتنفيذ نفسه في تلك الوحدة، فلا نسختان.
 */

/* ==============================================================================
   لوحة ملف القضية — ما ثبت، وما لم يُسجَّل بعد، والأسئلة المفتوحة.
   ============================================================================== */

/**
 * أسماء حقول الملف بالعربية — **تُفتح بالمفتاح الآلي لا بالنصّ**.
 *
 * ⚠️ وسبب وجودها أن `missing` و`confirmed` في `case_file.py` قائمتان
 * **مفاتيح**: `"dispute_type"` و`"emirate"` و`"has_arbitration_clause"`. وهي
 * ثابتة في `ESTABLISHED_FIELDS`، فلو عرضناها كما هي لقرأ المحامي اسم متغيّر،
 * ولو بنينا العرض على الترجمة لانكسر بصمت في أول تعديل تحريري. فالمفتاح هو
 * المدخل، والعربية تسميةٌ له (القاعدة نفسها في `review-panel.tsx`).
 *
 * ⚠️ والقيمة غير المعروفة تُعرض **بمفتاحها** لا بتسمية مخترعة: مفتاح جديد في
 * الخادم يُقرأ كما هو، ولا ندّعي له اسماً لم نضعه.
 */
const FIELD_LABELS: Record<string, string> = {
  dispute_type: "نوع النزاع",
  emirate: "الإمارة",
  forum: "الجهة",
  our_party: "صفتنا في النزاع",
  claims: "الطلبات",
  country: "الدولة",
  likely_law: "القانون المرجَّح",
  key_dates: "التواريخ الجوهرية",
  has_arbitration_clause: "شرط التحكيم في العقد",
  has_choice_of_law: "اتفاق على قانون مختار",
};

/** اسم الحقل: تسميته العربية إن عُرفت، وإلا مفتاحه الآلي بلا اختراع اسم. */
function fieldLabel(field: string): string {
  return FIELD_LABELS[field] ?? field;
}

/**
 * القيمة أو «—».
 *
 * ⚠️ **ولا تُعرض `undefined` ولا `null` ولا `NaN` ولا صفرٌ لم يُبلَّغ به**: رقم
 * لا يُحسب يُقال «—» (وهو نصّ `DASH` في briefing.py نفسه). ولو مرّ `undefined`
 * إلى JSX لمُحي بلا أثر، فيُقرأ السطر «لا شيء» وهو «لا يعرف».
 */
function orDash(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "number") return Number.isFinite(value) ? String(value) : "—";
  const text = String(value).trim();
  return text === "" ? "—" : text;
}

/**
 * لوحة ملف القضية.
 *
 * ⚠️ **والنواقص قائمة عمل لا قائمة أخطاء**: نقص حقل ليس عيباً في المسودّة بل
 * سؤالاً لم يُطرح بعد، فيُعرض بلون الورق لا بلون الختم. وأما الحقل **المانع**
 * فيُوسم لأنه يوقف الصياغة فعلاً — والوسم من `blocking` في السؤال نفسه، لا من
 * إعادة حساب عندنا.
 *
 * ⚠️ **وحال «لم يُفحص» حالةٌ ثالثة**: حين لا يُبنى الملف (`established: false`)
 * لا يُقال «ناقص» — لأن الناقص يفترض ملفاً يُقاس، ولا ملف. فهناك **لا نجاح ولا
 * نقص**: لا فحص. وهذا ما يفترق عن لوحة تقول «لا نواقص» عن فحص لم يجرِ.
 */
function CasePanel({ frame }: { frame: CaseFrame | null }) {
  if (!frame) return null;

  // ⚠️ المفتاح الآلي: ملف لم يُبنَ ≠ ملف بلا نواقص.
  const established = frame.established === true;
  const summary = frame.case ?? frame.summary;
  const missing = frame.missing ?? [];
  const confirmed = frame.confirmed ?? [];
  const questions = frame.questions ?? [];
  const notes = frame.regime_notes ?? [];
  const blocking = new Set(
    questions.filter((item) => item.blocking).map((item) => item.field)
  );

  const keyDates = (summary?.key_dates ?? []).filter(
    (pair) => Array.isArray(pair) && pair.length >= 2
  );
  const likelyLaw = summary?.likely_law ?? [];
  const claims = summary?.claims ?? [];

  return (
    <div className="space-y-4 border-t border-slate-200 bg-slate-50 p-6">
      <div className="flex flex-wrap items-center gap-2">
        {established ? (
          <FileText className="w-5 h-5 text-slate-600" />
        ) : (
          <AlertTriangle className="w-5 h-5 text-slate-500" />
        )}
        <h3 className="font-bold text-slate-900">ملف القضية</h3>
        {established && (
          <span className="text-sm text-slate-500" dir="auto">
            ({confirmed.length > 0
              ? `ثبت ${confirmed.map(fieldLabel).join(" · ")}`
              : "لم يثبت حقل بعد"})
          </span>
        )}
      </div>

      {!established ? (
        <div className="flex items-start gap-2 border border-slate-300 border-s-4 border-s-slate-500 bg-white p-3">
          <AlertTriangle className="mt-0.5 w-5 h-5 shrink-0 text-slate-500" />
          <div className="space-y-1 min-w-0">
            <p className="font-bold text-slate-700">
              لم يُفحَص ملف القضية — لا يُبنى عليه حكم.
            </p>
            {/*
              السبب بنصّ الخادم: يفرّق بين «لم يُرسل حمل» و«أُرسل حمل ولم
              يُبنَ منه ملف» — والثانية أخطر لأن المستدعي يظنّ قيمه مرّت.
            */}
            <p className="text-sm text-slate-600 leading-relaxed" dir="auto">
              {orDash(frame.message)}
            </p>
            <p className="text-xs text-slate-500">
              هذا ليس نقصاً في الملف ولا سلامةً فيه: الملف لم يُفحص أصلاً.
            </p>
          </div>
        </div>
      ) : (
        <>
          {/* النواقص — القائمة الأولى، وبترتيب الوحدة (المانع أولاً). */}
          {missing.length > 0 && (
            <div className="space-y-2">
              <h4 className="text-sm font-semibold text-slate-700">
                ما لم يُسجَّل بعد — قائمة عمل لا قائمة أخطاء
              </h4>
              <div className="flex flex-wrap gap-2">
                {missing.map((field) => (
                  <span
                    key={field}
                    className={
                      blocking.has(field)
                        ? "border border-amber-700/40 border-s-4 border-s-amber-700 bg-white px-3 py-1 text-sm font-semibold text-amber-800"
                        : "border border-slate-300 bg-white px-3 py-1 text-sm text-slate-700"
                    }
                  >
                    {fieldLabel(field)}
                    {blocking.has(field) && (
                      <span className="text-xs font-normal text-amber-700">
                        {" "}
                        — يوقف الصياغة
                      </span>
                    )}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* الأسئلة المفتوحة — سؤال بلا سببه يُقرأ استيفاءً لشكليات. */}
          {questions.length > 0 && (
            <div className="space-y-2">
              <h4 className="text-sm font-semibold text-slate-700">
                أسئلة تنتظر جوابك
              </h4>
              {questions.map((question, index) => (
                <div
                  key={`${question.field}-${index}`}
                  className="border border-slate-200 border-s-4 border-s-slate-300 bg-white p-3 space-y-1"
                >
                  <p className="text-sm font-medium leading-relaxed text-slate-900" dir="auto">
                    {question.question}
                  </p>
                  {question.why && (
                    <p className="text-xs leading-relaxed text-slate-500" dir="auto">
                      لماذا: {question.why}
                    </p>
                  )}
                  {question.blocking && (
                    <p className="text-xs font-semibold text-amber-700">
                      هذا الحقل مانع — نقصه يوقف الصياغة.
                    </p>
                  )}
                </div>
              ))}
            </div>
          )}

          {/* الملاحظات النظامية — تُقال بحكمها ومصدرها وحدّها. */}
          {notes.length > 0 && (
            <div className="space-y-2">
              <h4 className="text-sm font-semibold text-slate-700">
                ملاحظات النظام المنطبق
              </h4>
              {notes.map((note, index) => (
                <div
                  key={`note-${index}`}
                  className="border border-slate-200 border-s-slate-400 bg-white p-3 space-y-1"
                >
                  <p className="text-sm leading-relaxed text-slate-800" dir="auto">
                    {note.note}
                  </p>
                  {note.trigger && (
                    <p className="text-xs text-slate-500" dir="auto">
                      موضع الانطباق: {note.trigger}
                    </p>
                  )}
                  <p className="text-xs text-slate-500" dir="auto">
                    المصدر: {orDash(note.source)}
                    {" · "}
                    الحدّ: {orDash(note.limit)}
                  </p>
                </div>
              ))}
            </div>
          )}

          {/* ما ثبت — عرضاً لا فخراً: الحقل وقيمته من الملخّص نفسه. */}
          {(claims.length > 0 || likelyLaw.length > 0 || keyDates.length > 0) && (
            <div className="border border-slate-200 bg-white p-3 text-sm space-y-2">
              {claims.length > 0 && (
                <div>
                  <div className="text-xs font-semibold text-slate-500">الطلبات</div>
                  <ul className="mt-1 space-y-1">
                    {claims.map((claim, index) => (
                      <li key={`claim-${index}`} className="text-slate-800 leading-relaxed" dir="auto">
                        {claim}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {likelyLaw.length > 0 && (
                <div>
                  <div className="text-xs font-semibold text-slate-500">
                    القانون المرجَّح
                  </div>
                  <p className="text-slate-800 leading-relaxed" dir="auto">
                    {likelyLaw.join(" · ")}
                  </p>
                </div>
              )}
              {keyDates.length > 0 && (
                <div>
                  <div className="text-xs font-semibold text-slate-500">
                    التواريخ الجوهرية
                  </div>
                  <ul className="mt-1 space-y-1">
                    {keyDates.map((pair, index) => (
                      <li key={`date-${index}`} className="text-slate-700" dir="auto">
                        {orDash(pair[0])}: {orDash(pair[1])}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}

          {/*
            ⚠️ ولا كلمة عن الجاهزية: «اكتُمل الملف» هنا تعني **اكتمل ما يُسجَّل**،
            لا أن المسودّة صالحة للإيداع — والحكم على المستند للمحامي.
          */}
          <p className="text-xs text-slate-500">
            {missing.length === 0
              ? "كل الحقول المسجَّلة حاضرة — وهذا حكم على الملف لا على المستند."
              : "الحقول الناقصة أعلاه لا تمنع الصياغة، لكنها تمنع الحكم على المستند."}
          </p>
        </>
      )}
    </div>
  );
}

/* ==============================================================================
   لوحة الوقائع — درجة كل واقعة، والافتراقات أوّلاً.
   ============================================================================== */

/**
 * أسماء أنواع الافتراق بالعربية — **بالقيمة الآلية** (`kind` في `FactShift`).
 *
 * ⚠️ والترتيب تصاعدي في الخطورة: «لم تُذكر» إغفالٌ يُعالج بإضافة، و«أُعيدت
 * بصياغة» تحريفٌ يُعالج بمراجعة، و«نُقضت» انقلابُ معنى — وهو أخطرها.
 */
const SHIFT_LABELS: Record<string, string> = {
  missing: "لم تُذكر في المسودّة",
  reworded: "أُعيدت بصياغة تغيّر المعنى",
  contradicted: "المسودّة تنقضها",
};

/**
 * اسم نوع الافتراق، ويُسقَط إلى أضعف الدعاوى لكل قيمة لا تُعرف.
 *
 * ⚠️ والسقوط على `missing` لا على `contradicted`: لا نُعلن على الكاتب نقضاً لم
 * يُعلنه الخادم. والجهل يُقال بأضيق حدّه لا بأوسعه (كما في `kindLabel` في
 * `review-panel.tsx`).
 */
function shiftLabel(kind: string): string {
  return SHIFT_LABELS[kind] ?? SHIFT_LABELS.missing;
}

/**
 * واقعة واحدة في السجلّ — بنصّها ودرجتها ومصدرها.
 *
 * ⚠️ والدرجة تُعرض **بالعربية التي أرسلها الخادم** (`standing_label`) ويُحفظ
 * المفتاح الآلي في `title` للربط والتشخيص؛ والفرق لا يقوم على اللون وحده:
 * الكلمة هي الدليل واللون تأكيد.
 */
function FactRow({ fact }: { fact: FactEntry }) {
  return (
    <div className="border border-slate-200 border-s-4 border-s-slate-300 bg-white p-3 space-y-1">
      <div className="flex flex-wrap items-center gap-2">
        <span
          title={`حال: ${fact.standing}`}
          className="border border-slate-300 bg-slate-50 px-2 py-0.5 text-xs font-semibold text-slate-700"
        >
          {orDash(fact.standing_label)}
        </span>
        <span className="text-xs text-slate-500" dir="auto">
          {orDash(fact.key)}
        </span>
      </div>
      <p className="text-sm leading-relaxed text-slate-900" dir="auto">
        {fact.statement}
      </p>
      {fact.quote && (
        <p className="border-s-2 border-slate-200 ps-3 text-xs leading-relaxed text-slate-600" dir="auto">
          «{fact.quote}»
        </p>
      )}
      <p className="text-xs text-slate-500">
        المصدر: {orDash(fact.source)}
        {" · "}
        الموضع: {orDash(fact.locus)}
        {" · "}
        التاريخ: {orDash(fact.date)}
        {" · "}
        القائل: {orDash(fact.asserted_by)}
      </p>
    </div>
  );
}

/** عدّاد معروض — والغائب «—» لا صفر. */
function CountLine({ label, value }: { label: string; value: number | null }) {
  return (
    <span className="text-xs text-slate-600">
      {label}:{" "}
      <span className="font-semibold tabular-nums">{orDash(value)}</span>
    </span>
  );
}

/**
 * لوحة الوقائع — **أخطر لوحة في المسار**.
 *
 * ⚠️ **والافتراق هو صدر اللوحة لا ذيلها**: واقعةٌ أُعيدت في المسودّة على غير
 * ما في السجلّ هي العيب الذي تكرّر ثلاث مرّات، وهو **لا يكشفه** فحص الأسانيد
 * ولا التدقيق اللغوي ولا المراجعة الثانية — كلها تقرأ المسودّة في نفسها ولا
 * تقابلها بسجلّ. فمن قرأ أول سطرين في اللوحة يجب أن يكون قد رآه.
 *
 * ⚠️ **وحال «لم يُشغَّل» لا يُرسم فيها سجلّ**: حين لا يُرسل سجلّ مع الطلب
 * (`ran: false` و`ledger: null`) لا يوجد ما قوبلت به المسودّة، فلا يُعرض
 * «صفر افتراقات» — فهذا يقرأ نظافةً عن فحص لم يجرِ. يُقال النصّ صراحةً.
 */
function FactsPanel({ frame }: { frame: FactsFrame | null }) {
  if (!frame) return null;

  // ⚠️ المفتاح الآلي: `ran` ثم وجود السجلّ — والاثنان ليسا نظافة.
  const ran = frame.ran === true && frame.ledger !== null;
  const ledger = frame.ledger;
  const shifts = frame.shifts ?? ledger?.shifts ?? [];

  if (!ran || !ledger) {
    return (
      <div className="space-y-3 border-t border-slate-200 bg-slate-50 p-6">
        <div className="flex flex-wrap items-center gap-2">
          <AlertTriangle className="w-5 h-5 text-slate-500" />
          <h3 className="font-bold text-slate-900">أمانة الوقائع</h3>
          <span className="text-sm font-semibold text-slate-600">لم يُشغَّل</span>
        </div>
        <div className="flex items-start gap-2 border border-slate-300 border-s-4 border-s-slate-500 bg-white p-3">
          <AlertTriangle className="mt-0.5 w-5 h-5 shrink-0 text-slate-500" />
          <div className="space-y-1 min-w-0">
            {/* السبب بنصّ الخادم (`FACTS_NOT_RUN`) بلا إعادة كتابة. */}
            <p className="text-sm text-slate-700 leading-relaxed" dir="auto">
              {orDash(frame.message)}
            </p>
            <p className="text-xs text-slate-500">
              هذه ليست سلامةً في المسودّة: لم يُقابَل نصّها بسجلّ وقائع أصلاً،
              فلا شيء يقال عن أمانتها — لا وجوداً ولا عدماً.
            </p>
          </div>
        </div>
      </div>
    );
  }

  const facts = ledger.needs_verification ?? [];
  const conflicts = ledger.conflicts ?? [];
  const versionConflicts = ledger.version_conflicts ?? [];
  const unquoted = ledger.unquoted ?? [];

  return (
    <div className="space-y-4 border-t border-slate-200 bg-slate-50 p-6">
      <div className="flex flex-wrap items-center gap-2">
        {shifts.length > 0 ? (
          <ShieldAlert className="w-5 h-5 text-seal" />
        ) : (
          <ShieldCheck className="w-5 h-5 text-amber-700" />
        )}
        <h3 className="font-bold text-slate-900">أمانة الوقائع</h3>
        {/* حكم اللوحة كما صاغه الخادم (`_summary_line` في facts.py). */}
        <span className="text-sm text-slate-500" dir="auto">
          ({orDash(ledger.summary)})
        </span>
      </div>

      {/*
        ✦ الافتراقات — **أعلى اللوحة وأثقلها**، ولا تُطوى في قائمة ثانوية.
        والحكم واحد: ما دام في المسودّة نصّ يخالف السجلّ، فالعين هنا.
      */}
      {shifts.length > 0 && (
        <div className="border-2 border-seal bg-white">
          <div className="flex flex-wrap items-center gap-2 border-b border-seal/40 bg-seal/10 px-3 py-2">
            <ShieldAlert className="w-5 h-5 shrink-0 text-seal" />
            <span className="font-bold text-seal">
              افتراقات بين المسودّة وسجلّ الوقائع
            </span>
          </div>
          <div className="space-y-3 p-3">
            {shifts.map((shift, index) => (
              <div
                key={`${shift.fact_key}-${index}`}
                className="border border-seal/40 border-s-4 border-s-seal bg-white p-3 space-y-2"
              >
                <div className="flex flex-wrap items-center gap-2">
                  <span className="border border-seal/40 bg-seal/10 px-2 py-0.5 text-xs font-bold text-seal">
                    {shiftLabel(shift.kind)}
                  </span>
                  <span className="text-xs text-slate-600" dir="auto">
                    {orDash(shift.fact_key)}
                  </span>
                </div>
                <div className="grid gap-2 sm:grid-cols-2">
                  <div className="border-s-2 border-slate-300 ps-3">
                    <div className="text-xs text-slate-500">في المسودّة</div>
                    <p className="text-sm leading-relaxed text-slate-800" dir="auto">
                      {shift.draft_text ? `«${shift.draft_text}»` : "لم يرد لها نصّ."}
                    </p>
                  </div>
                  <div className="border-s-2 border-slate-300 ps-3">
                    <div className="text-xs text-slate-500">في السجلّ</div>
                    <p className="text-sm leading-relaxed text-slate-800" dir="auto">
                      {shift.fact_statement ? `«${shift.fact_statement}»` : "—"}
                    </p>
                  </div>
                </div>
                {/*
                  السبب بالأرقام كما كتبته الوحدة: الوسم **إنذار لا حكم** —
                  إعادة صياغة قد تكون مشروعة، والقرار للمحامي.
                */}
                <p
                  className="border-s-2 border-slate-200 ps-3 text-xs leading-relaxed text-slate-600"
                  dir="auto"
                >
                  {shift.note}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}

      {conflicts.length > 0 && (
        <div className="space-y-2">
          <h4 className="text-sm font-semibold text-slate-800">
            وقائع متناقضة داخل السجلّ
          </h4>
          {conflicts.map((conflict, index) => (
            <div
              key={`conflict-${index}`}
              className="border border-amber-700/40 border-s-4 border-s-amber-700 bg-white p-3 space-y-2"
            >
              <div className="text-xs font-semibold text-amber-800" dir="auto">
                {orDash(conflict.subject)}
              </div>
              <FactRow fact={conflict.first} />
              <FactRow fact={conflict.second} />
            </div>
          ))}
        </div>
      )}

      {versionConflicts.length > 0 && (
        <div className="space-y-2">
          <h4 className="text-sm font-semibold text-slate-800">
            مستندات بنسخ متعدّدة
          </h4>
          {versionConflicts.map((conflict, index) => (
            <div
              key={`version-${index}`}
              className="border border-amber-700/40 border-s-4 border-s-amber-700 bg-white p-3 space-y-1"
            >
              <div className="text-sm font-semibold text-slate-800" dir="auto">
                {orDash(conflict.document)}
              </div>
              <p className="text-xs leading-relaxed text-slate-600" dir="auto">
                {conflict.note}
              </p>
              <ul className="space-y-0.5">
                {(conflict.versions ?? []).map((version, versionIndex) => (
                  <li key={`v-${versionIndex}`} className="text-xs text-slate-600" dir="auto">
                    نسخة {orDash(version.version)} — التاريخ: {orDash(version.date)}
                    {" · "}
                    موقّعة: {version.signed === true ? "نعم" : version.signed === false ? "لا" : "—"}
                    {" · "}
                    ضمنية: {version.implied === true ? "نعم" : version.implied === false ? "لا" : "—"}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      )}

      {facts.length > 0 && (
        <div className="space-y-2">
          <h4 className="text-sm font-semibold text-slate-800">
            وقائع تحتاج تحقّقاً
          </h4>
          {facts.map((fact, index) => (
            <FactRow key={`${fact.key}-${index}`} fact={fact} />
          ))}
        </div>
      )}

      {unquoted.length > 0 && (
        <div className="border border-slate-300 bg-white p-3 text-sm space-y-1">
          <div className="font-semibold text-slate-700">
            وقائع بلا نصّ مقتبس — لا يستطيع مسار الأسانيد أن يقتبس لها شيئاً
          </div>
          <ul className="space-y-0.5">
            {unquoted.map((key, index) => (
              <li key={`u-${index}`} className="text-xs text-slate-600 font-mono" dir="auto">
                {key}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* قاعدتا الوحدة — تُعرضان مع التقرير لا في تعليق في الكود. */}
      {(ledger.rules?.client_statement_is_not_proof ||
        ledger.rules?.opponent_pleading_is_not_evidence) && (
        <div className="border-s-2 border-slate-400 ps-3 space-y-1">
          {ledger.rules?.client_statement_is_not_proof && (
            <p className="text-xs leading-relaxed text-slate-600" dir="auto">
              {ledger.rules.client_statement_is_not_proof}
            </p>
          )}
          {ledger.rules?.opponent_pleading_is_not_evidence && (
            <p className="text-xs leading-relaxed text-slate-600" dir="auto">
              {ledger.rules.opponent_pleading_is_not_evidence}
            </p>
          )}
        </div>
      )}

      {/* وقائع السجلّ — آخر اللوحة: تُقرأ بعد ما فيها من اعتراض. */}
      <div className="border border-slate-200 bg-white p-3 space-y-2">
        <div className="flex flex-wrap items-center gap-3">
          <CountLine label="وقائع السجلّ" value={ledger.fact_count ?? null} />
          <CountLine label="متناقضات" value={ledger.conflict_count ?? null} />
          <CountLine
            label="نسخ متعدّدة"
            value={ledger.version_conflict_count ?? null}
          />
        </div>
        <p className="text-xs text-slate-500">
          أعداد السجلّ كما أبلغها الفحص — لا تُحسب هنا ولا تُعرض إن لم تصل.
        </p>
      </div>

      {/*
        ⚠️ ولا شهادة ولا «جاهز»: الفحص يقول إنّ الوقائع قُوبلت، ولا يقول إنّ
        المستند صالح للإيداع — والقرار قرار المحامي.
      */}
      <p className="text-xs text-slate-500">
        {shifts.length === 0
          ? "جرى الفحص ولم يجد افتراقاً بين المسودّة والسجلّ — وهذا حكم على المقابلة، لا شهادة بصحّة المستند."
          : "اعتُرض على المسودّة أعلاه، ولم يُصحَّح شيء تلقائياً — التصحيح عملك."}
      </p>
    </div>
  );
}

/* ==============================================================================
   لوحة التقرير الداخلي — نصّ الوحدة كما هو.
   ============================================================================== */

/**
 * حالة التحقّق بالعربية — **بالمفتاح الآلي** (`safety` في briefing.py).
 *
 * ⚠️ ولا واحدة منها تعني «جاهز للإيداع»: `SAFETY_VERIFIED` في الوحدة نفسها
 * تقول «هذا تقرير عن الفحوص لا شهادة بصحّة المستند».
 */
const SAFETY_LABELS: Record<string, string> = {
  verified: "كل فحص متوقَّع جرى",
  partly_verified: "التحقّق ناقص",
  unverified: "لم يجرِ فحص يُقرأ",
};

/** اسم حالة التحقّق، ويُسقَط إلى `unverified` لكل قيمة لا تُعرف: لا ندّعي تحقّقاً. */
function safetyLabel(safety: string): string {
  return SAFETY_LABELS[safety] ?? SAFETY_LABELS.unverified;
}

/**
 * عدّاد مصدر: العدد أو «—».
 *
 * ⚠️ **و`null` ليست صفراً**: `errors: null` تعني أن الفحص **لم يُبلّغ عن عدد**
 * — ولو عُرضت صفراً لقرأ المحامي «لا خطأ» عن فحص لم يعدّ شيئاً.
 */
function SourceState({ source }: { source: BriefingSource }) {
  return (
    <div
      className={
        source.present
          ? "border border-slate-200 border-s-slate-400 bg-white px-3 py-1.5 text-xs text-slate-700"
          : "border border-slate-300 border-s-4 border-s-slate-500 bg-slate-100 px-3 py-1.5 text-xs text-slate-700"
      }
    >
      <span className="font-semibold">{orDash(source.label)}</span>
      {" · "}
      <span className={source.present ? "text-slate-500" : "font-semibold text-slate-700"}>
        {source.present ? "جرى" : "لم يُشغَّل"}
      </span>
      {" · "}
      <span className="text-slate-600">
        أخطاء: <span className="tabular-nums">{orDash(source.errors)}</span>
      </span>
      {" · "}
      <span className="text-slate-600">
        ملاحظات: <span className="tabular-nums">{orDash(source.notices)}</span>
      </span>
    </div>
  );
}

/**
 * لوحة التقرير الداخلي — **أحد سلَمَي المنتج**.
 *
 * ⚠️ **والنصّ يُعرض كما بنته الوحدة** (`to_markdown` في briefing.py) ولا يُعاد
 * بناؤه في جافاسكربت: إعادة البناء تُنتج **تنسيقين ينحرفان بصمت** عند أوّل
 * تعديل في الوحدة، وهي العلّة نفسها التي أُصلحت في الأدوات الخمس. والقاموس
 * (`report`) لا يُقرأ إلا لِما لا يحمله النصّ: **حال كل مصدر** (`present`) —
 * فذلك هو الفحص الذي لم يُشغَّل، وهو الحال الثالث الذي لا يُقرأ سلامة.
 *
 * ⚠️ **والسطر يُرسم في `div` مستقلّ بلا تفسير Markdown**: التقرير يُنسخ إلى
 * Word، والعرض «كما هو» يحفظ له ذلك — والوسوم القليلة (`#` · `-` · `|`) تُقرأ
 * كما كتبها الخادم، ونصّ الخادم هو الحجّة.
 */
function BriefingPanel({ frame }: { frame: BriefingFrame | null }) {
  if (!frame) return null;

  const report = frame.report;
  // تقرير بلا قاموس ولا نصّ: لا شيء يُقال، فلا يُرسم إطار فارغ.
  if (!report && !frame.markdown) return null;

  const sources = report?.sources ?? [];
  const missingSources = sources.filter((source) => source.present !== true);
  const ran = sources.length > 0 && missingSources.length === 0;
  const safety = report?.safety ?? "unverified";

  return (
    <div className="space-y-4 border-t border-slate-200 bg-slate-50 p-6">
      <div className="flex flex-wrap items-center gap-2">
        {safety === "verified" && ran ? (
          <FileText className="w-5 h-5 text-amber-700" />
        ) : (
          <AlertTriangle className="w-5 h-5 text-slate-600" />
        )}
        <h3 className="font-bold text-slate-900">التقرير الداخلي</h3>
        <span
          className={
            safety === "verified" && ran
              ? "border border-amber-700/40 bg-amber-700/10 px-2 py-0.5 text-xs font-semibold text-amber-800"
              : "border border-slate-400 bg-slate-200 px-2 py-0.5 text-xs font-semibold text-slate-700"
          }
        >
          {safetyLabel(safety)}
        </span>
        <span className="text-sm text-slate-500">
          ورقة عمل داخلية — لا تُرسل إلى الخصم.
        </span>
      </div>

      {/* الفحوص التي لم تُشغَّل — قبل النصّ، لأنها تُقرأ خطأً كسلامة. */}
      {missingSources.length > 0 && (
        <div className="flex items-start gap-2 border border-slate-300 border-s-4 border-s-slate-500 bg-white p-3">
          <AlertTriangle className="mt-0.5 w-5 h-5 shrink-0 text-slate-500" />
          <div className="min-w-0 space-y-1">
            <p className="font-bold text-slate-700">
              لم تُشغَّل فحوص ({missingSources.length} من {sources.length}) —
              وغيابها ليس نظافة.
            </p>
            <p className="text-xs text-slate-500">
              الفحص الذي لم يجرِ لا يمنع التسليم ولا يجيزه: يمنع الاعتماد على
              صمتٍ لم يُقل.
            </p>
          </div>
        </div>
      )}

      {/*
        ✦ النصّ — قابل للفصل والنسخ: إطار مغلق وأسطر مستقلة، لأن المحامي ينسخ
        منه إلى ورقة عمله، ولأن التقرير **مفصول عن المذكرة** بقصد الوحدة.
      */}
      {frame.markdown && (
        <div className="border border-slate-300 bg-white">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200 bg-slate-100 px-3 py-2">
            <span className="text-xs font-semibold text-slate-700">
              نصّ التقرير كما بنته الوحدة ({orDash(report?.generated_at)})
            </span>
            <Button
              variant="outline"
              size="sm"
              onClick={() =>
                navigator.clipboard.writeText(
                  `${report?.headline ? report.headline + "\n\n" : ""}${frame.markdown}`
                )
              }
            >
              نسخ التقرير
            </Button>
          </div>
          <div className="space-y-0.5 p-4" dir="rtl">
            {frame.markdown
              .split("\n")
              .map((line) => line.trim())
              .filter((line) => line.length > 0)
              .map((line, index) => (
                <div
                  key={`md-${index}`}
                  dir="auto"
                  className={
                    line.startsWith("#")
                      ? "pt-2 text-sm font-bold text-slate-900 whitespace-pre-wrap"
                      : line.startsWith("-")
                        ? "ps-3 text-sm leading-relaxed text-slate-700 whitespace-pre-wrap"
                        : "text-sm leading-relaxed text-slate-700 whitespace-pre-wrap font-mono"
                  }
                >
                  {line}
                </div>
              ))}
          </div>
        </div>
      )}

      {/* حال كل مصدر بالمفتاح: `present: false` ⇒ لم يُشغَّل، ويُعرض مختلفاً. */}
      {sources.length > 0 && (
        <div className="space-y-2">
          <h4 className="text-sm font-semibold text-slate-700">
            الفحوص — ما جرى منها وما لم يُشغَّل
          </h4>
          <div className="grid gap-2 sm:grid-cols-2">
            {sources.map((source, index) => (
              <SourceState key={`${source.kind}-${index}`} source={source} />
            ))}
          </div>
        </div>
      )}

      {/*
        ⚠️ ولا «جاهز» ولا «مكتمل» في هذا السطر: التقرير ورقة عمل تقول ما لم
        يُتحقَّق منه — والختم للمحامي لا للواجهة.
      */}
      {report?.headline && (
        <p className="border-s-2 border-slate-400 ps-3 text-sm leading-relaxed text-slate-700" dir="auto">
          {report.headline}
        </p>
      )}
    </div>
  );
}

/**
 * تسميات المصادر الأربعة — **المفتاح هو المدخل والعربية تسميةٌ له**.
 *
 * ⚠️ والقيمة غير المعروفة تُعرض **بمفتاحها** لا بتسمية مخترعة (القاعدة نفسها في
 * `FIELD_LABELS` و`fieldLabel`): مفتاح جديد في الخادم يُقرأ كما هو، ولا ندّعي
 * له اسماً لم نضعه.
 */
const SOURCE_LABELS: Record<string, string> = {
  review: "المراجعة",
  fidelity: "مطابقة الوقائع",
  attribution: "العزو",
  language: "اللغة",
};

/** اسم المصدر: تسميته العربية إن عُرفت، وإلا مفتاحه الآلي بلا اختراع اسم. */
function sourceLabel(source: string): string {
  return SOURCE_LABELS[source] ?? source;
}

/**
 * لوحة إعادة الصياغة وقائمة الأخطاء.
 *
 * ⚠️ **وفائدتها كلّها في التمييز الذي لا تحمله قائمة الأخطاء وحدها**: فُحصت
 * المسودّة فلم يُوجد عيب، ولم يُفحص شيء — **كلتاهما قائمة فارغة** في الإطار.
 * وهذا نصّ `sources_checked` في revision_loop.py، وله وُلدت. فالحكم هنا على
 * `collected` وحدها، وهي التي تقول: أَجُمِعت القائمة أم تعذّر جمعها.
 *
 * ⚠️ **و`collected: false` مع `errors: []` لا يُعرض «لا أخطاء» أبداً** — وهو
 * العطب الوحيد الذي وُجدت هذه اللوحة لمنعه. فالقائمة الفارغة هناك ليست نتيجة
 * فحص بل أثر انهيار في `collect_errors`، والقول «لا أخطاء» عنها **شهادة سلامة
 * لم تُمنح**: الفحص الذي لم يجرِ ليس فحصاً نجح. فيُعرض نصّ الخادم وحده، ولا
 * يُقرأ الفراغ.
 *
 * ⚠️ **والحكم على الخطورة بالمفتاح الآلي `severity`**: `"error"` خطأ، وما سواه
 * ملاحظة (`"notice"` في مراجعة المشروع). ولا يُبنى الحكم على نصّ عربي — فالعربية
 * عرضٌ للنتيجة لا مدخلٌ للحكم عليها. والمفتاح المجهول يُعرض بمفتاحه.
 *
 * ⚠️ **ولا «جاهز» ولا «مكتمل» في هذه اللوحة**: هي قائمة ما وجدته الفحوص، والختم
 * للمحامي لا للواجهة. ولا شريط تقدّم ولا نسبة ولا درجة ثقة — كلّها أرقام لا
 * تُحسب من هذا الإطار، وما لا يُحسب يُقال «—» أو لا يُقال.
 *
 * ⚠️ **والفقرة التي تحمل `message` من الخادم لا تُصاغ هنا**: جملة «لم تُجرَ
 * إعادة صياغة» شرطُ سلامة عند الخادم — إعادة الصياغة تُنتج نصّاً آخر لم تجرِ
 * عليه الفحوص، فيصير المستند وفحوصه يصفان نصّين مختلفين. فمن أعاد الصياغة
 * لاحقاً **يجب أن يغيّر جملة الخادم بقصد**، لا أن يجد واجهةً تقول «تمّت».
 */
function RevisionPanel({ frame }: { frame: RevisionFrame | null }) {
  if (!frame) return null;

  // ⚠️ المفتاح هو `collected` — لا القائمة. وغيابه يُقرأ «لم تُجمع» لا «جُمِعت».
  const collected = frame.collected === true;
  const errors = frame.errors ?? [];
  // والتصنيف بالمفتاح: `"error"` خطأ يمنع، وما سواه ملاحظة. والمجهول ملاحظة.
  const blocking = errors.filter((item) => item.severity === "error");
  const notices = errors.filter((item) => item.severity !== "error");
  const checkedSources = frame.checked_sources ?? [];

  /** سطر خطأ واحد: النصّ ثم الاقتباس، وكلاهما محتوى React لا HTML. */
  const renderError = (item: LoopError, index: number, kind: "blocking" | "notice") => (
    <div
      key={`${kind}-${item.source}-${item.kind}-${index}`}
      className={
        kind === "blocking"
          ? "space-y-1 border border-red-200 border-s-4 border-s-red-400 bg-white p-3"
          : "space-y-1 border border-slate-300 border-s-4 border-s-slate-400 bg-white p-3"
      }
    >
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs font-semibold text-slate-500">{sourceLabel(item.source)}</span>
        {/* المفتاح الآلي في وسم اتجاهه محدد: خيط لاتيني داخل سطر عربي */}
        <span className="font-mono text-[11px] text-slate-400" dir="ltr">
          {item.kind}
        </span>
        <span
          className={
            kind === "blocking"
              ? "border border-red-300 bg-red-50 px-1.5 py-0.5 font-mono text-[11px] font-semibold text-red-700"
              : "border border-slate-300 bg-slate-100 px-1.5 py-0.5 font-mono text-[11px] font-semibold text-slate-600"
          }
          dir="ltr"
        >
          {item.severity}
        </span>
      </div>
      <p className="text-sm leading-relaxed text-slate-700" dir="auto">
        {item.message}
      </p>
      {/* الاقتباس موضع الخلل من المسودّة — يُعرض كما هو ليُقابله المحامي بنصّه. */}
      {item.quote && (
        <p
          className="whitespace-pre-wrap border-s-2 border-slate-300 bg-slate-50 ps-3 text-xs leading-relaxed text-slate-600"
          dir="auto"
        >
          {item.quote}
        </p>
      )}
    </div>
  );

  return (
    <div className="space-y-4 border-t border-slate-200 bg-slate-50 p-6">
      <div className="flex flex-wrap items-center gap-2">
        {collected ? (
          <FileText className="w-5 h-5 text-slate-600" />
        ) : (
          <AlertTriangle className="w-5 h-5 text-slate-500" />
        )}
        <h3 className="font-bold text-slate-900">قائمة الأخطاء الموحّدة</h3>
      </div>

      {/*
        ⚠️ «أيّ فحص جرى» **قبل** الأخطاء، وللسبب نفسه الذي جعل BriefingPanel
        يقدّم الفحوص الغائبة على النصّ: الغياب يُقرأ خطأً نظافة. فالفحص الذي لم
        يُشغَّل لا يمنع التسليم ولا يجيزه — يمنع الاعتماد على صمتٍ لم يُقل.
      */}
      <div className="space-y-2">
        {/* العنوان بالمفتاح لا بالدعوى: عند تعذّر الجمع لا يُقال «جرت فحوص». */}
        <h4 className="text-sm font-semibold text-slate-700">
          {collected ? "الفحوص المُبلَّغ عنها" : "الفحوص المُبلَّغ عنها — والقائمة لم تُجمع"} —{" "}
          {orDash(checkedSources.length)}
        </h4>
        {checkedSources.length > 0 ? (
          <div className="flex flex-wrap gap-2">
            {checkedSources.map((source, index) => (
              <span
                key={`${source}-${index}`}
                className="border border-slate-400 bg-slate-200 px-2 py-0.5 text-xs font-semibold text-slate-700"
              >
                {sourceLabel(source)}
                {/* المفتاح الآلي بجانب تسميته: العرض لا يخفي المصدر الحقيقي. */}
                <span className="ms-2 font-mono text-[11px] text-slate-500" dir="ltr">
                  {source}
                </span>
              </span>
            ))}
          </div>
        ) : (
          <p className="text-sm text-slate-500" dir="auto">
            {collected
              ? "لم يُبلَّغ عن أيّ فحص جرى — وغيابُه ليس نظافة."
              : "لم يُبلَّغ عن فحوص، لأن القائمة لم تُجمع أصلاً."}
          </p>
        )}
      </div>

      {/* الحالة الأولى — لم تُجمع القائمة، فلا يُذكر «لا أخطاء» إطلاقاً. */}
      {!collected ? (
        <div className="flex items-start gap-2 border border-slate-300 border-s-4 border-s-slate-500 bg-white p-3">
          <AlertTriangle className="mt-0.5 w-5 h-5 shrink-0 text-slate-500" />
          <div className="min-w-0 space-y-1">
            <p className="font-bold text-slate-700">{frame.message}</p>
            <p className="text-xs text-slate-500">
              تُعرض قائمة الأخطاء وحدها، فالقائمة الفارغة هنا ليست نتيجة فحص:
              الفحص الذي لم يجرِ ليس فحصاً نجح.
            </p>
          </div>
        </div>
      ) : (
        <>
          {/* الحالة الثانية — شُغّلت الفحوص ولم تجد شيئاً. */}
          {errors.length === 0 && (
            <div className="flex items-start gap-2 border border-slate-300 border-s-4 border-s-slate-500 bg-white p-3">
              <FileText className="mt-0.5 w-5 h-5 shrink-0 text-slate-600" />
              <div className="min-w-0 space-y-1">
                {/* «جرت» بالمفتاح: بلوغ هذا الفرع يعني `collected: true`. */}
                <p className="font-bold text-slate-700">جرت الفحوص أعلاه ولم تجد ما يُدرج.</p>
                <p className="text-xs text-slate-500" dir="auto">
                  {frame.message}
                </p>
              </div>
            </div>
          )}

          {/* الحالة الثالثة — أخطاء وملاحظات. والخطأ هو `severity: "error"`. */}
          {blocking.length > 0 && (
            <div className="space-y-2">
              <h4 className="text-sm font-semibold text-red-700">أخطاء تمنع الاعتماد</h4>
              {blocking.map((item, index) => renderError(item, index, "blocking"))}
            </div>
          )}

          {notices.length > 0 && (
            <div className="space-y-2">
              <h4 className="text-sm font-semibold text-slate-600">ملاحظات — تُعرَض ولا تمنع</h4>
              {notices.map((item, index) => renderError(item, index, "notice"))}
            </div>
          )}
        </>
      )}

      {/*
        ⚠️ النصّ من الخادم (وحدة `revision_loop.py`)، ولا نصّ من عندنا في موضعه:
        الجملة تحمل سبب الامتناع عن إعادة الصياغة، فصياغتها هنا تُفقدها سلطتها.
      */}
      <div className="space-y-1 border-t border-slate-200 pt-3">
        <h4 className="text-sm font-semibold text-slate-700">إعادة الصياغة</h4>
        {frame.redrafted === true ? (
          <>
            {/*
              ⚠️ **«أُنتج نصٌّ ثانٍ» لا «أُصلح الخطأ».**
              الإعادة تعني أن ما فُحص لم يعد هو المعروض، **والنصّ الجديد يُفحَص
              ولا يُفترَض** (انظر `final_draft` في main.py). فمن قرأ هنا «تمّ
              الإصلاح» فقد قرأ شهادةً لم تُمنح — وهذا موضع انزلاق هذا المشروع.
            */}
            <p className="text-xs text-slate-500" dir="auto">
              أُنتج نصٌّ ثانٍ — ولم تعد الفحوص أعلاه وصفاً للنصّ المعروض،
              وهي تصف ما فُحص قبل الإعادة.
            </p>
            <p className="text-xs text-slate-600" dir="auto">
              إعادة الصياغة ليست إصلاحاً مُثبَتاً: النصّ الجديد يُفحَص من جديد،
              فإن زال العيب فذلك، وإلا فهو باقٍ — يُفحَص ولا يُفترَض.
            </p>
          </>
        ) : (
          <p className="text-xs text-slate-500" dir="auto">
            لم تُجرَ إعادة صياغة.
          </p>
        )}

        {/*
          ⚠️ **وعدد المحاولات يُعرض رقمُه أو «لم يُبلَّغ به»** — ولا يُقرأ غيابه
          صفراً: «لم يُبلَّغ» و«لم تُجرَ محاولة» ليسا شيئاً واحداً (القاعدة نفسها
          في `BriefingSource`). وبلوغ السقف يُقال «توقّف» لا «نجح».
        */}
        <p className="text-xs text-slate-500" dir="auto">
          عدد محاولات الإعادة: {orNotReported(frame.redraft_attempts)}
          {frame.stop_code ? (
            <>
              {" · "}
              توقّفت الحلقة عند:{" "}
              <span className="font-mono text-[11px] text-slate-500" dir="ltr">
                {frame.stop_code}
              </span>
            </>
          ) : null}
        </p>

        {/*
          ⚠️ **ونصّ سبب التوقّف من الخادم بنصّه**: هو الذي يقول إن السقف بُلغ،
          وصياغتُه عندنا تُفقد الجملة سلطتها — وهو نصّ القاعدة المعلنة أعلاه.
        */}
        {frame.stopped_reason && (
          <p className="text-sm leading-relaxed text-slate-700" dir="auto">
            سبب التوقّف: {frame.stopped_reason}
          </p>
        )}

        <p className="text-sm leading-relaxed text-slate-700" dir="auto">
          {orDash(frame.message)}
        </p>
      </div>
    </div>
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
          className="border border-green-200 bg-white p-3 text-sm"
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
              className="border border-red-200 bg-white p-3 text-sm"
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
        <div className="border border-amber-300 bg-amber-50 p-3 text-sm space-y-1">
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
        <div className="border border-slate-300 bg-white p-3 text-xs text-slate-600 space-y-1">
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
 * لوحة التدقيق اللغوي — عمل «سيبويه المُكشّر».
 *
 * فحص حتمي لا نموذج: مخلفات Markdown، وافتتاح حواري، وحقول قالب لم تُملأ،
 * وكلمات لاتينية، وأسطر مكرّرة. انظر `language_audit.py`.
 *
 * والأخطاء تمنع التسليم، والملاحظات للعلم فقط — ولذلك يختلف لونهما.
 */
function LanguagePanel({ report }: { report: LanguageReport | null }) {
  if (!report) return null;
  if (report.findings.length === 0) {
    return (
      <div className="flex items-center gap-2 border-t border-slate-200 bg-slate-50 px-6 py-3 text-sm text-green-700">
        <ShieldCheck className="w-4 h-4" />
        <span className="font-semibold">التدقيق اللغوي:</span>
        <span>{report.summary}</span>
      </div>
    );
  }

  const errors = report.findings.filter((item) => item.severity === "error");
  const notices = report.findings.filter((item) => item.severity === "notice");

  return (
    <div className="space-y-3 border-t border-slate-200 bg-slate-50 p-6">
      <div className="flex flex-wrap items-center gap-2">
        {report.clean ? (
          <ShieldCheck className="w-5 h-5 text-green-600" />
        ) : (
          <ShieldAlert className="w-5 h-5 text-red-600" />
        )}
        <h3 className="font-bold text-slate-900">التدقيق اللغوي</h3>
        <span className="text-sm text-slate-500">({report.summary})</span>
      </div>

      {errors.length > 0 && (
        <div className="space-y-2">
          <h4 className="text-sm font-semibold text-red-700">يجب إصلاحها قبل التسليم</h4>
          {errors.map((item, index) => (
            <div
              key={`e-${index}`}
              className="border border-red-200 bg-white p-3 text-sm"
            >
              <div className="text-xs text-red-600 mb-1">
                {item.message}
                {item.line != null && <span className="text-slate-400"> — سطر {item.line}</span>}
              </div>
              <p className="font-mono text-xs text-slate-700" dir="auto">
                {item.sample}
              </p>
            </div>
          ))}
        </div>
      )}

      {notices.length > 0 && (
        <div className="space-y-2">
          <h4 className="text-sm font-semibold text-amber-700">ملاحظات للعلم</h4>
          {notices.map((item, index) => (
            <div
              key={`n-${index}`}
              className="border border-amber-200 bg-white p-3 text-sm"
            >
              <div className="text-xs text-amber-700 mb-1">{item.message}</div>
              <p className="font-mono text-xs text-slate-600" dir="auto">
                {item.sample}
              </p>
            </div>
          ))}
        </div>
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
        <div className="flex flex-wrap items-center gap-2 border border-green-200 bg-green-50 p-3 text-sm text-green-800">
          <CheckCircle className="w-4 h-4 shrink-0" />
          <span className="font-semibold">حُفظ تصحيحك.</span>
          {/* ⚠️ **ولا نسبة ولا عدد كلمات هنا — وهذا مقصود.**
              كان هذا الموضع يعرض «عدّلتَ ١٢.٣٪ من المسودّة … ٤٥٠ كلمة»،
              **وهما إحصاء ونسبة، وقد طُلب صراحةً ألّا يُعرضا.** وصياغةُ حفظٍ
              لا تحتاج رقماً لتُفهَم: من حفظ تصحيحه يعرف أنه حفظه، **والرقم
              هنا يمنح «تقدّماً» لا يعني المحامي في شيء** — فالتصحيح يقيس
              أسلوب المنصّة، لا جودة العمل القانوني. */}
          <span>
            وسيُقاس عليه أسلوب الكتابة في المرّات القادمة.
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
        <div className="whitespace-pre-wrap border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          {error}
        </div>
      )}
    </div>
  );
}

/* ==============================================================================
   اللوحات الأربعة التي كانت تُبثّ وتُسقَط — على قالب `RevisionPanel` نفسه.
   ============================================================================== */

/**
 * القيمة أو **«لم يُبلَّغ به»** — للخلية التي يغيب مفتاحها عن الإطار.
 *
 * ⚠️ **ولا تُقرأ «—» هنا صفراً**: عددُ محاولات إعادة الصياغة الغائب ليس صفر
 * محاولات، بل «لم يُبلَّغ» — والفرق بينهما هو كلّ الفرق (القاعدة نفسها في
 * `BriefingSource`: `errors: null` ليست صفر خطأ). و`orDash` وحدها تُرجع «—»
 * وهي قرينة على «لا قيمة»، وهذا النصّ يقول **لماذا** لا قيمة.
 */
function orNotReported(value: unknown): string {
  const text = orDash(value);
  return text === "—" ? "لم يُبلَّغ به" : text;
}

/**
 * تسمية المفتاح الآلي بحالته العربية — **والحدّ هو ما يُكتب عربياً، لا الحكم**.
 *
 * ⚠️ **و`kind` يُعرض نصّاً ولا يُترجم**: الخادم هو الذي يصنّف (`out_of_force` ·
 * `secondary_as_primary` · `unsourced`)، والترجمة تنكسر بصمت في أول تعديل
 * تحريري — وهي القاعدة المعلنة في `LoopError` أعلاه. فالمفتاح يبقى معروضاً في
 * وسمه، والعربية في اللوحة تشرح **حدّ الحكم** (خطأ يمنع / ملاحظة لا تمنع).
 */

/**
 * صفّ المصادر المفحوصة — مشترك بين اللوحات الأربعة، ومصدرُه `checked_sources`.
 *
 * ⚠️ وتسمياته عربية، **والمفتاح الغريب عن هذا الجدول يُعرض بمفتاحه**: مفتاح
 * جديد في الخادم يُقرأ كما هو، ولا ندّعي له اسماً لم نضعه (القاعدة نفسها في
 * `FIELD_LABELS` و`SOURCE_LABELS`).
 */
const CHECKED_SOURCES_LABELS: Record<string, string> = {
  facts: "مقابلة الطلبات بسجلّ الوقائع",
  draft: "المسودّة — الطلبات التي لم يُجب عنها",
  stage: "مخالفة المرحلة",
  in_force_on: "النفاذ الزمنيّ في تاريخ الإيداع",
  secondary_as_primary: "مصدر ثانويّ عُومل معاملة النصّ",
  unsourced: "سندٌ بلا مصدر رسمي",
  add_period: "إضافة المدّة إلى تاريخ البدء",
  convention_for: "عدّ المدّة (طبيعي/عمل)",
  source: "مصدر القاعدة",
  check_distinctions: "التمييز في المسودّة",
  conflicts: "تعارض القواعد",
  must_review: "قواعد تستلزم مراجعة",
};

/**
 * المصادر المفحوصة — **تُعرض قبل الأخطاء، وللسبب نفسه في `RevisionPanel`**:
 * «أيّ فحص جرى» قبل نتيجته، لأن الغياب يُقرأ خطأً نظافة.
 */
function CheckedSources({
  sources,
  missingNote,
}: {
  sources: string[];
  /** نصّ يُقال حين لا يُبلَّغ عن فحص — يختلف بحال البناء، ويُمرَّر من اللوحة. */
  missingNote: string;
}) {
  return (
    <div className="space-y-2">
      <h4 className="text-sm font-semibold text-slate-700">
        الفحوص المُبلَّغ عنها — {orDash(sources.length)}
      </h4>
      {sources.length > 0 ? (
        <div className="flex flex-wrap gap-2">
          {sources.map((source, index) => (
            <span
              key={`${source}-${index}`}
              className="border border-slate-400 bg-slate-200 px-2 py-0.5 text-xs font-semibold text-slate-700"
            >
              {CHECKED_SOURCES_LABELS[source] ?? "فحص بلا تسمية عندنا"}
              {/* المفتاح الآلي بجانب تسميته: العرض لا يخفي المصدر الحقيقي. */}
              <span className="ms-2 font-mono text-[11px] text-slate-500" dir="ltr">
                {source}
              </span>
            </span>
          ))}
        </div>
      ) : (
        <p className="text-sm text-slate-500" dir="auto">
          {missingNote}
        </p>
      )}
    </div>
  );
}

/** صفّ «لم يُبنَ» — الحالة الثالثة، وهي التي لا تُقرأ سلامةً ولا نقصاً. */
function NotBuiltNotice({ message, why }: { message: string; why: string }) {
  return (
    <div className="flex items-start gap-2 border border-slate-300 border-s-4 border-s-slate-500 bg-white p-3">
      <AlertTriangle className="mt-0.5 w-5 h-5 shrink-0 text-slate-500" />
      <div className="min-w-0 space-y-1">
        <p className="font-bold text-slate-700">لم يُبنَ — فلا فحص جرى هنا.</p>
        {/* نصّ الخادم بنصّه: سببُ غياب البناء معلومة لا نُصيغها نحن. */}
        <p className="text-sm leading-relaxed text-slate-600" dir="auto">
          {orDash(message)}
        </p>
        <p className="text-xs text-slate-500">{why}</p>
      </div>
    </div>
  );
}

/** عنوان لوحة بمفتاح الحال — والمفتاح هو المُدخل لا النصّ. */
function PanelHeading({
  built,
  title,
  detail,
}: {
  built: boolean;
  title: string;
  detail: string;
}) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      {built ? (
        <FileText className="w-5 h-5 text-slate-600" />
      ) : (
        <AlertTriangle className="w-5 h-5 text-slate-500" />
      )}
      <h3 className="font-bold text-slate-900">{title}</h3>
      <span className="text-sm text-slate-500" dir="auto">
        {detail}
      </span>
    </div>
  );
}

/**
 * لوحة المصفوفة — إطار `claims`، `_claims_frame` في main.py.
 *
 * ⚠️ **وما تعرضه اللوحة ليس «لا أخطاء» بل ما وُجد**: مخالفةُ المرحلة (وهي
 * **خطأ** لا ملاحظة — فالاستئناف يطعن في الحكم أو الإجراء، والنقض في القانون،
 * **والطعن في تقدير الدليل غير مقبول في النقض**)، والطلبُ الذي لم يُجب عنه،
 * والدفعُ الذي لا واقعة تسنده.
 *
 * ⚠️ **و`built: false` لا يُعرض كفحصٍ نجح**: القائمة الفارغة هناك أثرُ عدم بناءٍ
 * لا نتيجةَ فحص، فتُقال الحال بنصّ الخادم ولا يُقرأ الفراغ.
 */
function ClaimsPanel({ frame }: { frame: ClaimsFrame | null }) {
  if (!frame) return null;

  // ⚠️ المفتاح `built` — لا القائمة. وغيابه يُقرأ «لم تُبنَ» لا «بُنيت».
  const built = frame.built === true;
  const errors = frame.errors ?? [];
  const notices = frame.notices ?? [];
  const checkedSources = frame.checked_sources ?? [];
  const stage = frame.stage ?? null;

  const renderFinding = (
    item: FindingEntry,
    index: number,
    kind: "error" | "notice"
  ) => (
    <div
      key={`${kind}-${item.code}-${item.item_key}-${index}`}
      className={
        kind === "error"
          ? "space-y-1 border border-red-200 border-s-4 border-s-red-400 bg-white p-3"
          : "space-y-1 border border-slate-300 border-s-4 border-s-slate-400 bg-white p-3"
      }
    >
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs font-semibold text-slate-500">
          البند: {orNotReported(item.item_key)}
        </span>
        {/* المفتاح الآلي في وسم اتجاهه محدد: خيط لاتيني داخل سطر عربي */}
        <span className="font-mono text-[11px] text-slate-400" dir="ltr">
          {item.code}
        </span>
        <span
          className={
            kind === "error"
              ? "border border-red-300 bg-red-50 px-1.5 py-0.5 font-mono text-[11px] font-semibold text-red-700"
              : "border border-slate-300 bg-slate-100 px-1.5 py-0.5 font-mono text-[11px] font-semibold text-slate-600"
          }
          dir="ltr"
        >
          {item.kind}
        </span>
        <span className="font-mono text-[11px] text-slate-400" dir="ltr">
          {item.severity}
        </span>
      </div>
      <p className="text-sm leading-relaxed text-slate-700" dir="auto">
        {item.message}
      </p>
      {/* ملاحظة الوحدة — تُعرض إن وُجدت، ولا يُخترع لها نصّ. */}
      {item.note && (
        <p className="border-s-2 border-slate-300 bg-slate-50 ps-3 text-xs leading-relaxed text-slate-600" dir="auto">
          {item.note}
        </p>
      )}
    </div>
  );

  return (
    <div className="space-y-4 border-t border-slate-200 bg-slate-50 p-6">
      <PanelHeading
        built={built}
        title="مصفوفة الطلبات والدفوع"
        detail={
          built
            ? `أخطاء تمنع: ${orDash(errors.length)} · ملاحظات: ${orDash(notices.length)}`
            : "لم تُبنَ المصفوفة — لا يُقرأ فراغها سلامة."
        }
      />

      {/* ⚠️ والمرحلة قبل الأخطاء: بغيابها **لا يُدّعى فحصُ المخالفة**، ولو جاءت
          القائمة فارغة. */}
      <div className="space-y-2">
        <h4 className="text-sm font-semibold text-slate-700">مرحلة النزاع</h4>
        {stage ? (
          <p className="text-sm text-slate-700" dir="auto">
            <span className="font-mono text-[11px] text-slate-500" dir="ltr">
              {stage}
            </span>
            {" — "}
            وفُحصت الطلبات والدفوع عليها.
          </p>
        ) : (
          <p className="text-sm text-slate-500" dir="auto">
            لا مرحلة في الطلب — ففحص المخالفة لم يجرِ، ولا يُقال إن الطلبات
            موافقةٌ للمرحلة.
          </p>
        )}
      </div>

      <CheckedSources
        sources={checkedSources}
        missingNote={
          built
            ? "لم يُبلَّغ عن أيّ فحص جرى — وغيابه ليس نظافة."
            : "لم يُبلَّغ عن فحوص، لأن المصفوفة لم تُبنَ أصلاً."
        }
      />

      {!built ? (
        <NotBuiltNotice
          message={frame.message}
          why="تُعرض المصفوفة وحدها، فغيابُها ليس مصفوفةً فارغة: المصفوفة التي لم تُبنَ ليست مصفوفةً سليمة."
        />
      ) : (
        <>
          {/* شُغّل الفحص ولم يجد شيئاً — وهنا فقط تُقال السلامة، وبالمفتاح. */}
          {errors.length === 0 && notices.length === 0 && (
            <div className="flex items-start gap-2 border border-slate-300 border-s-4 border-s-slate-500 bg-white p-3">
              <FileText className="mt-0.5 w-5 h-5 shrink-0 text-slate-600" />
              <div className="min-w-0 space-y-1">
                <p className="font-bold text-slate-700">
                  بُنيت المصفوفة على ما أُدخل، ولم يُدرج فيها عيب.
                </p>
                <p className="text-xs text-slate-500">
                  وهذا حكمٌ على المصفوفة المُدخلة، لا على المسودّة ولا على الطلبات
                  نفسها: ما لم يُدخَل لم يُفحص.
                </p>
              </div>
            </div>
          )}

          {errors.length > 0 && (
            <div className="space-y-2">
              <h4 className="text-sm font-semibold text-red-700">
                أخطاء تمنع الاعتماد — ومخالفة المرحلة منها
              </h4>
              {errors.map((item, index) => renderFinding(item, index, "error"))}
            </div>
          )}

          {notices.length > 0 && (
            <div className="space-y-2">
              <h4 className="text-sm font-semibold text-slate-600">
                ملاحظات — تُعرَض ولا تمنع
              </h4>
              {notices.map((item, index) => renderFinding(item, index, "notice"))}
            </div>
          )}
        </>
      )}
    </div>
  );
}

/**
 * لوحة الأسانيد — إطار `authority`، `_authority_frame` في main.py.
 *
 * ⚠️ **وثلاثة أحكام لا تُدمج، وهي كلّ فائدة اللوحة:**
 *   • إخفاق زمنيّ (سندٌ لم يكن سارياً في تاريخ الإيداع) — **خطأ**.
 *   • مصدرٌ ثانويّ عُومل معاملة النصّ — **خطأ**.
 *   • سندٌ بلا مصدر رسمي — **ملاحظة**، تُعلَن ولا تُعرض كأنها محقَّقة.
 * والفصل يقع بالمفتاحين: القائمة (`errors` / `notices`) و`kind` الآلي.
 *
 * ⚠️ **وبلا تاريخ إيداع لا يُدّعى انطباق**: الفحص يُبنى بحال `unverified` ونصّ
 * «لم يُفحَص النفاذ»، **فلا تُقرأ شارةُ الفحص شهادةَ انطباق**.
 */
function AuthorityPanel({ frame }: { frame: AuthorityFrame | null }) {
  if (!frame) return null;

  const built = frame.built === true;
  const checks = frame.checks ?? [];
  const errors = frame.errors ?? [];
  const notices = frame.notices ?? [];
  const checkedSources = frame.checked_sources ?? [];

  const renderFinding = (
    item: FrameEntry,
    index: number,
    kind: "error" | "notice"
  ) => (
    <div
      key={`${kind}-${item.kind}-${item.key}-${index}`}
      className={
        kind === "error"
          ? "space-y-1 border border-red-200 border-s-4 border-s-red-400 bg-white p-3"
          : "space-y-1 border border-slate-300 border-s-4 border-s-slate-400 bg-white p-3"
      }
    >
      <div className="flex flex-wrap items-center gap-2">
        <span
          className={
            kind === "error"
              ? "border border-red-300 bg-red-50 px-1.5 py-0.5 font-mono text-[11px] font-semibold text-red-700"
              : "border border-slate-300 bg-slate-100 px-1.5 py-0.5 font-mono text-[11px] font-semibold text-slate-600"
          }
          dir="ltr"
        >
          {item.kind}
        </span>
        <span className="text-xs font-semibold text-slate-500" dir="auto">
          {orNotReported(item.instrument)}
        </span>
        {item.article && (
          <span className="text-xs text-slate-500" dir="auto">
            المادة: {item.article}
          </span>
        )}
        <span className="font-mono text-[11px] text-slate-400" dir="ltr">
          {item.key}
        </span>
      </div>
      <p className="text-sm leading-relaxed text-slate-700" dir="auto">
        {orDash(item.message)}
      </p>
      {item.source && (
        <p className="text-xs text-slate-500" dir="auto">
          المصدر: {item.source}
        </p>
      )}
    </div>
  );

  return (
    <div className="space-y-4 border-t border-slate-200 bg-slate-50 p-6">
      <PanelHeading
        built={built}
        title="فحص الأسانيد"
        detail={
          built
            ? `أخطاء تمنع: ${orDash(errors.length)} · ملاحظات: ${orDash(notices.length)} · فُحص ${orDash(checks.length)} سنداً`
            : "لم يُبنَ سجلّ الأسانيد — لا يُقرأ فراغه سلامة."
        }
      />

      <CheckedSources
        sources={checkedSources}
        missingNote={
          built
            ? "لم يُبلَّغ عن أيّ فحص جرى — وغيابه ليس نظافة."
            : "لم يُبلَّغ عن فحوص، لأن السجلّ لم يُبنَ أصلاً."
        }
      />

      {!built ? (
        <NotBuiltNotice
          message={frame.message}
          why="الإطار يُبثّ دائماً — ولا يُحذف: حذفُه يُقرأ سكوتاً، والسكوت في موضع فحصٍ يُقرأ سلامة."
        />
      ) : (
        <>
          {checks.length > 0 && (
            <div className="space-y-2">
              <h4 className="text-sm font-semibold text-slate-700">
                حال كل سند — والشرط غير المستوفى يُقال
              </h4>
              {checks.map((check, index) => (
                <div
                  key={`${check.key}-${index}`}
                  className="space-y-1 border border-slate-200 border-s-4 border-s-slate-300 bg-white p-3"
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-xs font-semibold text-slate-500" dir="auto">
                      {orNotReported(check.instrument)}
                    </span>
                    {check.article && (
                      <span className="text-xs text-slate-500" dir="auto">
                        المادة: {check.article}
                      </span>
                    )}
                    <span className="font-mono text-[11px] text-slate-400" dir="ltr">
                      {check.key}
                    </span>
                    {/* الحال مفتاح آلي: `unverified` تعني لم يُفحَص، واللون لا يفرد. */}
                    <span
                      className={
                        check.status === "applicable"
                          ? "border border-slate-300 bg-slate-100 px-1.5 py-0.5 font-mono text-[11px] font-semibold text-slate-600"
                          : check.status === "unverified"
                            ? "border border-amber-300 bg-amber-50 px-1.5 py-0.5 font-mono text-[11px] font-semibold text-amber-800"
                            : "border border-red-300 bg-red-50 px-1.5 py-0.5 font-mono text-[11px] font-semibold text-red-700"
                      }
                      dir="ltr"
                    >
                      {check.status}
                    </span>
                  </div>
                  <p className="text-sm leading-relaxed text-slate-700" dir="auto">
                    {orDash(check.reason)}
                  </p>
                  {/* ⚠️ «غير مستوفى» تُعرض من `unmet` وحدها حين تكون الحال
                      `applicable`: ولائحة فارغة في سندٍ لم يُفحَص ليست استيفاءً. */}
                  {check.status === "applicable" && (check.unmet ?? []).length > 0 && (
                    <p className="text-xs font-semibold text-red-700" dir="auto">
                      شرط غير مستوفى: {(check.unmet ?? []).join(" · ")}
                    </p>
                  )}
                  {check.status === "applicable" && (check.unmet ?? []).length === 0 && (
                    <p className="text-xs text-slate-500" dir="auto">
                      كل شروط الانطباق قائمة.
                    </p>
                  )}
                  {(check.conditions ?? []).length > 0 && (
                    <p className="text-xs text-slate-500" dir="auto">
                      الشروط المُعلَنة: {check.conditions.join(" · ")}
                    </p>
                  )}
                </div>
              ))}
            </div>
          )}

          {errors.length > 0 && (
            <div className="space-y-2">
              <h4 className="text-sm font-semibold text-red-700">
                أخطاء تمنع الاعتماد — إخفاقٌ زمنيّ أو مصدرٌ ثانويّ عُومل كنصّ
              </h4>
              {errors.map((item, index) => renderFinding(item, index, "error"))}
            </div>
          )}

          {notices.length > 0 && (
            <div className="space-y-2">
              <h4 className="text-sm font-semibold text-slate-600">
                ملاحظات — ومنها سندٌ بلا مصدر رسمي: يُعلَن ولا يُعرض كأنه محقَّق
              </h4>
              {notices.map((item, index) => renderFinding(item, index, "notice"))}
            </div>
          )}

          {checks.length === 0 && errors.length === 0 && notices.length === 0 && (
            <p className="text-sm text-slate-500" dir="auto">
              بُني السجلّ ولم يُدرج فيه سند — فلا سند فُحص، وهذا ليس سلامة أسانيد.
            </p>
          )}
        </>
      )}
    </div>
  );
}

/**
 * لوحة المواعيد — إطار `deadlines`، `_deadlines_frame` في main.py.
 *
 * ⚠️ **والمنصّة تحسب ولا تخترع**: القواعد يكتبها المحامي بمصادرها، والعدّ
 * يُختار من `Convention` ولا يُخمَّن. فكل موعد هنا **منسوبٌ إلى قاعدته** —
 * التسمية والقاعدة والمصدر والعدّ — لأن موعداً بلا قاعدته رقمٌ لا يُبنى عليه إجراء.
 *
 * ⚠️ **وبلا تاريخ في ملف القضية يُعلَن أن الحساب لم يجرِ** (`no_date`) — **وهو
 * خيرٌ من موعدٍ مُخترع يتساقط به الإجراء**. والقاعدة بلا مصدر ملاحظةٌ تُعلَن.
 */
function DeadlinesPanel({ frame }: { frame: DeadlinesFrame | null }) {
  if (!frame) return null;

  const built = frame.built === true;
  const items = frame.items ?? [];
  const errors = frame.errors ?? [];
  const notices = frame.notices ?? [];
  const checkedSources = frame.checked_sources ?? [];

  return (
    <div className="space-y-4 border-t border-slate-200 bg-slate-50 p-6">
      <PanelHeading
        built={built}
        title="المواعيد المحسوبة"
        detail={
          built
            ? `حُسب ${orDash(items.length)} موعداً — ومنسوبةٌ إلى قواعدها`
            : "لم تُحسَب المواعيد — ولا يُدّعى موعد."
        }
      />

      <CheckedSources
        sources={checkedSources}
        missingNote={
          built
            ? "لم يُبلَّغ عن أيّ عملية حساب جرى — وغيابُها ليس موعداً."
            : "لم يُبلَّغ عن حساب، لأن قواعد المواعيد لم تُدخَل أصلاً."
        }
      />

      {!built ? (
        <NotBuiltNotice
          message={frame.message}
          why="لا موعد بلا قاعدة يكتبها المحامي ولا بلا تاريخ في ملف القضية — والحساب لا يُخترع."
        />
      ) : (
        <>
          {items.length > 0 && (
            <div className="space-y-2">
              <h4 className="text-sm font-semibold text-slate-700">
                المواعيد — كل موعد بقاعدته ومصدره
              </h4>
              {items.map((item, index) => (
                <div
                  key={`${item.key}-${index}`}
                  className="space-y-1 border border-slate-200 border-s-4 border-s-slate-300 bg-white p-3"
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-sm font-semibold text-slate-900" dir="auto">
                      {orDash(item.label)}
                    </span>
                    {/* ⚠️ التاريخ بالميلادي بأرقام لاتينية — والتاريخ قرار إجراء لا زينة. */}
                    <span className="font-mono text-sm font-semibold text-slate-800" dir="ltr">
                      {orDash(item.due)}
                    </span>
                    <span className="font-mono text-[11px] text-slate-400" dir="ltr">
                      {item.key}
                    </span>
                  </div>
                  <p className="text-xs leading-relaxed text-slate-600" dir="auto">
                    {orDash(item.described)}
                  </p>
                  <p className="text-xs text-slate-500" dir="auto">
                    من: <span className="font-mono" dir="ltr">{orDash(item.from)}</span>
                    {" · "}
                    المدّة: <span className="font-mono" dir="ltr">{orDash(item.amount)}</span>{" "}
                    <span className="font-mono" dir="ltr">{orDash(item.unit)}</span>
                    {" · "}
                    العدّ: <span className="font-mono" dir="ltr">{orDash(item.convention)}</span>
                  </p>
                  <p className="text-xs text-slate-500" dir="auto">
                    المصدر: {orDash(item.source)}
                  </p>
                </div>
              ))}
            </div>
          )}

          {notices.length > 0 && (
            <div className="space-y-2">
              <h4 className="text-sm font-semibold text-slate-600">
                ملاحظات — تُعرَض ولا تمنع
              </h4>
              {notices.map((item, index) => (
                <div
                  key={`${item.kind}-${item.key ?? index}-${index}`}
                  className="space-y-1 border border-slate-300 border-s-4 border-s-slate-400 bg-white p-3"
                >
                  <span
                    className="border border-slate-300 bg-slate-100 px-1.5 py-0.5 font-mono text-[11px] font-semibold text-slate-600"
                    dir="ltr"
                  >
                    {item.kind}
                  </span>
                  <p className="text-sm leading-relaxed text-slate-700" dir="auto">
                    {orDash(item.message)}
                  </p>
                </div>
              ))}
            </div>
          )}

          {/*
            ⚠️ **ولا يُقال «لا مواعيد مستحقة» هنا.** الحساب الذي بلغ هذا الفرع لم
            يُنتج بنداً، **ومعناه أن القاعدة لم تُدخَل أو أن التاريخ غاب** — لا أن
            الإجراء سليم. ولذلك يُعلَن الفراغ بحدّه ولا يُقرأ سلامة.
          */}
          {items.length === 0 && (
            <p className="text-sm text-slate-500" dir="auto">
              بُنيت القواعد ولم يُحسَب موعد — إمّا بغياب تاريخ في ملف القضية
              (وهو المُعلَن في الملاحظات أعلاه)، أو لأن المدخل لم يُنتج بنداً.
              وهذا ليس «لا مواعيد»: هذا «لم يُحسَب».
            </p>
          )}

          {/* `errors` تُبنى فارغةً في هذه الدالة دائماً — فالفارغ هنا يُقرأ بعدم
              الحساب لا بسلامة المواعيد، ولا نعرض له قسماً أصلاً. */}
          {errors.length > 0 && (
            <div className="space-y-2">
              <h4 className="text-sm font-semibold text-red-700">
                أخطاء تمنع الاعتماد
              </h4>
              {errors.map((item, index) => (
                <div
                  key={`${item.kind}-${item.key ?? index}-${index}`}
                  className="space-y-1 border border-red-200 border-s-4 border-s-red-400 bg-white p-3"
                >
                  <span
                    className="border border-red-300 bg-red-50 px-1.5 py-0.5 font-mono text-[11px] font-semibold text-red-700"
                    dir="ltr"
                  >
                    {item.kind}
                  </span>
                  <p className="text-sm leading-relaxed text-slate-700" dir="auto">
                    {orDash(item.message)}
                  </p>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}

/**
 * لوحة القواعد المتخصّصة — إطار `rules`، `_rules_frame` في main.py.
 *
 * ⚠️ **وقاعدتان لا تُخلطان**: ما يُفحص في المسودّة (`check_distinctions`)، وما
 * يتغيّر بتغيّر التشريع (`conflicts` و`must_review`). والخلط بينهما هو العطب
 * الذي بُنيت الوحدة لمنعه.
 *
 * ⚠️ **والسجلّ الفارغ يُعلَن فارغاً** (`empty_register`) — **ولا يُعرض كأنه فحصٌ
 * تمّ**: فلا قاعدة تُطبَّق، وهذا ليس فحصاً ناجحاً.
 */
function RulesPanel({ frame }: { frame: RulesFrame | null }) {
  if (!frame) return null;

  const built = frame.built === true;
  const rules = frame.rules ?? [];
  const conflicts = frame.conflicts ?? [];
  const mustReview = frame.must_review ?? [];
  const findings = frame.findings ?? [];
  const errors = frame.errors ?? [];
  const notices = frame.notices ?? [];
  const checkedSources = frame.checked_sources ?? [];

  const renderEntry = (
    item: FrameEntry,
    index: number,
    kind: "error" | "notice"
  ) => (
    <div
      key={`${kind}-${item.kind}-${item.key ?? item.a ?? index}-${index}`}
      className={
        kind === "error"
          ? "space-y-1 border border-red-200 border-s-4 border-s-red-400 bg-white p-3"
          : "space-y-1 border border-slate-300 border-s-4 border-s-slate-400 bg-white p-3"
      }
    >
      <div className="flex flex-wrap items-center gap-2">
        <span
          className={
            kind === "error"
              ? "border border-red-300 bg-red-50 px-1.5 py-0.5 font-mono text-[11px] font-semibold text-red-700"
              : "border border-slate-300 bg-slate-100 px-1.5 py-0.5 font-mono text-[11px] font-semibold text-slate-600"
          }
          dir="ltr"
        >
          {item.kind}
        </span>
        {/* طرفا التعارض بالمفتاحين — ولا يُختار بينهما تلقائياً. */}
        {item.a && item.b && (
          <span className="font-mono text-[11px] text-slate-500" dir="ltr">
            {item.a} ↔ {item.b}
          </span>
        )}
        {item.key && (
          <span className="font-mono text-[11px] text-slate-400" dir="ltr">
            {item.key}
          </span>
        )}
      </div>
      {item.message && (
        <p className="text-sm leading-relaxed text-slate-700" dir="auto">
          {item.message}
        </p>
      )}
      {item.quote && (
        <p
          className="whitespace-pre-wrap border-s-2 border-slate-300 bg-slate-50 ps-3 text-xs leading-relaxed text-slate-600"
          dir="auto"
        >
          {item.quote}
        </p>
      )}
      {item.why && (
        <p className="text-xs leading-relaxed text-slate-500" dir="auto">
          لماذا: {item.why}
        </p>
      )}
    </div>
  );

  return (
    <div className="space-y-4 border-t border-slate-200 bg-slate-50 p-6">
      <PanelHeading
        built={built}
        title="القواعد المتخصّصة"
        detail={
          built
            ? `قواعد: ${orDash(rules.length)} · تعارض: ${orDash(conflicts.length)} · تستلزم مراجعة: ${orDash(mustReview.length)}`
            : "لم يُبنَ سجلّ القواعد — ولا قاعدة تُطبَّق."
        }
      />

      <CheckedSources
        sources={checkedSources}
        missingNote={
          built
            ? "لم يُبلَّغ عن أيّ فحص جرى — وغيابه ليس نظافة."
            : "لم يُبلَّغ عن فحوص، لأن السجلّ لم يُبنَ أصلاً."
        }
      />

      {!built ? (
        <NotBuiltNotice
          message={frame.message}
          why="القواعد يُدخلها المحامي بمصادرها — والمنصّة تطبّقها ولا تخترعها. فغيابُ السجلّ ليس سجلّاً فارغاً."
        />
      ) : (
        <>
          {rules.length > 0 && (
            <div className="space-y-2">
              <h4 className="text-sm font-semibold text-slate-700">
                ما ينطبق — كل قاعدة بنصّها ومصدرها
              </h4>
              {rules.map((rule, index) => (
                <div
                  key={`${rule.key}-${index}`}
                  className="space-y-1 border border-slate-200 border-s-4 border-s-slate-300 bg-white p-3"
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-mono text-[11px] text-slate-400" dir="ltr">
                      {rule.key}
                    </span>
                    {rule.in_force_from && (
                      <span className="text-xs text-slate-500" dir="auto">
                        سارٍ من: <span className="font-mono" dir="ltr">{rule.in_force_from}</span>
                      </span>
                    )}
                  </div>
                  <p className="text-sm leading-relaxed text-slate-900" dir="auto">
                    {rule.statement}
                  </p>
                  <p className="text-xs text-slate-500" dir="auto">
                    المصدر: {orDash(rule.source)}
                  </p>
                </div>
              ))}
            </div>
          )}

          {/* ⚠️ والقاعدة بلا مصدر **ملاحظة** (`unsourced` في الإطار) لا خطأ —
              وهي تُعرض في قسم الملاحظات أدناه بمفتاحها. */}

          {mustReview.length > 0 && (
            <div className="space-y-2">
              <h4 className="text-sm font-semibold text-amber-700">
                تستلزم مراجعة — تغيّر التشريع
              </h4>
              {mustReview.map((rule, index) => (
                <div
                  key={`review-${rule.key}-${index}`}
                  className="space-y-1 border border-amber-300 border-s-4 border-s-amber-400 bg-white p-3"
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-mono text-[11px] text-slate-400" dir="ltr">
                      {rule.key}
                    </span>
                    {rule.in_force_from && (
                      <span className="text-xs text-slate-500" dir="auto">
                        سارٍ من: <span className="font-mono" dir="ltr">{rule.in_force_from}</span>
                      </span>
                    )}
                  </div>
                  <p className="text-sm leading-relaxed text-slate-800" dir="auto">
                    {rule.statement}
                  </p>
                  {rule.source && (
                    <p className="text-xs text-slate-500" dir="auto">
                      المصدر: {rule.source}
                    </p>
                  )}
                </div>
              ))}
            </div>
          )}

          {findings.length > 0 && (
            <div className="space-y-2">
              <h4 className="text-sm font-semibold text-slate-700">
                التمييز في المسودّة
              </h4>
              {findings.map((finding, index) => (
                <div
                  key={`finding-${finding.kind}-${index}`}
                  className="space-y-1 border border-slate-200 border-s-slate-300 bg-white p-3"
                >
                  <span className="font-mono text-[11px] text-slate-400" dir="ltr">
                    {finding.kind}
                  </span>
                  {finding.quote && (
                    <p
                      className="whitespace-pre-wrap border-s-2 border-slate-300 bg-slate-50 ps-3 text-xs leading-relaxed text-slate-600"
                      dir="auto"
                    >
                      {finding.quote}
                    </p>
                  )}
                </div>
              ))}
            </div>
          )}

          {errors.length > 0 && (
            <div className="space-y-2">
              <h4 className="text-sm font-semibold text-red-700">
                أخطاء تمنع الاعتماد — تعميمٌ أو تناقض أو تعارض قاعدتين
              </h4>
              {errors.map((item, index) => renderEntry(item, index, "error"))}
            </div>
          )}

          {notices.length > 0 && (
            <div className="space-y-2">
              <h4 className="text-sm font-semibold text-slate-600">
                ملاحظات — ومنها سجلٌّ فارغ: يُعلَن ولا يُقرأ فحصاً ناجحاً
              </h4>
              {notices.map((item, index) => renderEntry(item, index, "notice"))}
            </div>
          )}

          {rules.length === 0 && errors.length === 0 && notices.length === 0 && (
            <p className="text-sm text-slate-500" dir="auto">
              سجلّ القواعد فارغ — فلا قاعدة تُطبَّق. وهذا ليس فحصاً ناجحاً.
            </p>
          )}
        </>
      )}
    </div>
  );
}

/* ==============================================================================
   مدخلات الفحوص الأربعة — **الطلبات والدفوع · الأسانيد · المواعيد · القواعد**.

   ⚠️ **وهي طبقة إدخالٍ لا استنتاج.** ولا يُستنتج حملُ فحصٍ من إطار عرض: استنتاجُ
   مدخلات فحصٍ من مخرجات مسودّة يعني **حاكمَين يفترقان**، والخادم هو موضع
   التحقّق. فالإطارات تُعرَض، وهذه الحقول تُدخَل، و`buildGeneratePayload` تجمع.

   ⚠️ **والفراغ يبقى غياباً لا كائناً فارغاً** (`generate-inputs.ts`): اللوحة
   تقول «لم تُبنَ»، **وهو الصدق نفسه** — لا «فُحصت فسلمت».

   ⚠️ **وكل قيمة تعديد هنا عضوٌ من وحدة الخادم** (`stage` · `claimed_by` ·
   `kind` · `unit` · `convention_key` · `family`)، ويُرسَل المفتاح الآلي وحده.
   والعربية تسميةٌ للعرض. فثلاثة أعطابٍ متتالية في هذا المشروع كانت من **إرسال
   حقل تعديدٍ نصّاً حرّاً**، والخادم يردّه ٤٠٠.
   ============================================================================== */

/** حقل نصّي بعنوان — على نمط `label` + `Input` في نموذج الصياغة القائم. */
function Field({
  label,
  value,
  onChange,
  placeholder,
  className,
  dir,
  type,
  min,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  className?: string;
  dir?: "rtl" | "ltr";
  type?: string;
  min?: number;
}) {
  return (
    <div className="space-y-1">
      <label className="text-xs font-medium text-slate-400">{label}</label>
      <Input
        className={`h-auto py-2 bg-slate-950 border-slate-800 text-white text-sm focus-visible:ring-amber-500 ${className ?? ""}`}
        dir={dir}
        type={type}
        min={min}
        placeholder={placeholder}
        value={value}
        onChange={(e) => onChange(e.target.value)}
      />
    </div>
  );
}

/** مساحة نصّية بعدّة أسطر — لحقول القوائم («سطر لكل عنصر»). */
function LinesField({
  label,
  hint,
  value,
  onChange,
  placeholder,
}: {
  label: string;
  hint?: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
}) {
  return (
    <div className="space-y-1">
      <label className="text-xs font-medium text-slate-400">
        {label}
        {hint ? <span className="text-slate-600"> — {hint}</span> : null}
      </label>
      <Textarea
        className="min-h-[64px] bg-slate-950 border-slate-800 focus-visible:ring-amber-500 text-white text-sm resize-y"
        placeholder={placeholder}
        value={value}
        onChange={(e) => onChange(e.target.value)}
      />
    </div>
  );
}

/**
 * قائمة تعديد — **والقيم أعضاء وحدات الخادم لا نصوص**.
 *
 * ⚠️ ونمط `<select>` هو نمط نموذج الصياغة القائم («نوع المستند») بعينه: لا
 * مصدر خامس للمكوّنات، ولا قائمة تُبنى بغير ما هو موجود.
 */
function EnumField({
  label,
  value,
  onChange,
  options,
  emptyLabel,
  className,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: EnumOption[];
  /** نصّ الخيار الفارغ — **والغياب يعني «لم يُفحَص» لا «سليم»**. */
  emptyLabel?: string;
  className?: string;
}) {
  return (
    <div className="space-y-1">
      <label className="text-xs font-medium text-slate-400">{label}</label>
      <select
        className={`w-full p-2 bg-slate-950 border border-slate-800 text-white text-sm focus:ring-amber-500 ${className ?? ""}`}
        value={value}
        onChange={(e) => onChange(e.target.value)}
      >
        {/* ⚠️ الخيار الفارغ قيمته `""` لا عضواً مُخمَّناً: الاختيار الفارغ يعني
            «لم يُدخَل»، وترجمتُه إلى عضوٍ افتراضيّ **تصنع حكماً لم يقله المحامي**
            («نافذ» أو «ليس محلّ نزاع» — وكلاهما ادّعاء). */}
        {emptyLabel !== undefined ? <option value="">{emptyLabel}</option> : null}
        {options.map((option) => (
          // ⚠️ `value` هو عضو التعديد، والنصّ المعروض عربي — ولا يُرسَل النصّ.
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </div>
  );
}

/** اختيار متعدّد الأزرار — للمحاور (وهي **مجموعة**) وأنواع النزاع والمراحل. */
function ToggleGroup({
  label,
  hint,
  values,
  onChange,
  options,
}: {
  label: string;
  hint?: string;
  values: string[];
  onChange: (values: string[]) => void;
  options: EnumOption[];
}) {
  return (
    <div className="space-y-1">
      <label className="text-xs font-medium text-slate-400">
        {label}
        {hint ? <span className="text-slate-600"> — {hint}</span> : null}
      </label>
      <div className="flex flex-wrap gap-1">
        {options.map((option) => {
          const chosen = values.includes(option.value);
          return (
            <button
              key={option.value}
              type="button"
              aria-pressed={chosen}
              onClick={() =>
                onChange(
                  chosen
                    ? values.filter((v) => v !== option.value)
                    : [...values, option.value]
                )
              }
              className={`border px-2 py-1 text-xs transition-colors ${
                chosen
                  ? "border-amber-600 bg-amber-600/20 text-amber-200"
                  : "border-slate-800 bg-slate-950 text-slate-400 hover:border-slate-700"
              }`}
            >
              {option.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}

/** ترقيم البنود في المدخلات — والتسمية عربية لأنها للقارئ لا للحقل. */
const INPUT_ORDINALS = "الأول الثاني الثالث الرابع الخامس السادس السابع الثامن".split(" ");

/**
 * المجموعة المفتوحة في النموذج.
 *
 * ⚠️ **وهي القوائم الأربعة وحدها لا مفاتيح الحالة كلها**: `stage` و`ourParty`
 * ليسا مجموعةً تُطوى، بل حقلان في رأس مجموعة الطلبات. فلو كُتب النوع
 * `keyof GenerateInputsState` لَما طابق `"authorities"` (اسم القائمة) ولا
 * `"claims"` بمعنى المجموعة — وهو فخّ يظهر في `tsc` لا في العين.
 */
type InputGroupKey = "claims" | "authority" | "deadlines" | "rules";

function ordinal(index: number): string {
  return INPUT_ORDINALS[index] ?? `رقم ${index + 1}`;
}

/** مجموعة قابلة للطيّ — لأن أربع مجموعات مفتوحة تُغرِق النموذج. */
function InputGroupBox({
  title,
  note,
  count,
  open,
  onToggle,
  children,
}: {
  title: string;
  note: string;
  count: number;
  open: boolean;
  onToggle: () => void;
  children: React.ReactNode;
}) {
  return (
    <div className="border border-slate-800">
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={open}
        className="flex w-full items-center justify-between gap-2 bg-slate-950/60 px-3 py-2 text-right hover:bg-slate-950"
      >
        <span className="text-sm font-medium text-amber-300">{title}</span>
        <span className="flex items-center gap-2 text-xs text-slate-500">
          {count > 0 ? <span className="text-amber-400">{count} مُدخَل</span> : null}
          <ChevronDown
            className={`h-4 w-4 transition-transform ${open ? "rotate-180" : ""}`}
          />
        </span>
      </button>
      {open ? (
        <div className="space-y-3 border-t border-slate-800 p-3">
          <p className="text-xs leading-relaxed text-slate-500">{note}</p>
          {children}
        </div>
      ) : null}
    </div>
  );
}

/** زرّا الإضافة والحذف — بنمط `Button` القائم لا بزرٍّ جديد. */
function AddRowButton({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <Button
      type="button"
      variant="outline"
      size="sm"
      onClick={onClick}
      className="w-full border-dashed border-slate-700 bg-transparent text-slate-300 hover:bg-slate-900"
    >
      <Plus className="ml-1 h-4 w-4" /> {label}
    </Button>
  );
}

function RemoveRowButton({ onClick, title }: { onClick: () => void; title: string }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={title}
      title={title}
      className="shrink-0 border border-slate-800 p-1 text-slate-500 transition-colors hover:border-red-900 hover:text-red-400"
    >
      <Trash2 className="h-4 w-4" />
    </button>
  );
}

/** إطار بند واحد: رأسه رقمٌ وزرّ حذف، وجسمه الحقول. */
function ItemBox({
  title,
  onRemove,
  removeTitle,
  children,
}: {
  title: string;
  onRemove: () => void;
  removeTitle: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-2 border border-slate-800/70 bg-slate-950/40 p-2">
      <div className="flex items-center justify-between gap-2">
        <span className="text-xs font-semibold text-slate-400">{title}</span>
        <RemoveRowButton onClick={onRemove} title={removeTitle} />
      </div>
      {children}
    </div>
  );
}

/**
 * حقول الطلب أو الدفع — **وهي حقول `_item` في main.py حرفياً**.
 *
 * ⚠️ و`is_procedural` يُعرَض على الدفع وحده، لأنه **حكمٌ على الترتيب** لا وصفٌ
 * للشكل: الإجرائي يُقدَّم لأن ما بعده لا يُبحث قبل استقراره (claims.py).
 * و`burden` **لا يُعرَض ولا يُرسَل** — يُبنى `UNKNOWN` في الخادم.
 */
function MatrixItemFields({
  item,
  onChange,
  prefixes,
}: {
  item: MatrixItemForm;
  onChange: (patch: Partial<MatrixItemForm>) => void;
  prefixes: string[];
}) {
  return (
    <>
      <div className="grid grid-cols-2 gap-2">
        <Field
          label="المفتاح الآلي"
          value={item.key}
          onChange={(key) => onChange({ key })}
          placeholder="notice_pay"
          dir="ltr"
        />
        <EnumField
          label="من يتمسّك به"
          value={item.claimedBy}
          onChange={(claimedBy) => onChange({ claimedBy })}
          options={PARTY_OPTIONS}
        />
      </div>
      <Field
        label="النصّ كما يُكتب في المذكرة"
        value={item.label}
        onChange={(label) => onChange({ label })}
        placeholder="مكافأة نهاية الخدمة عن مدّة الخدمة كاملة"
      />
      <ToggleGroup
        label="محاور النزاع"
        hint="مجموعة لا قيمة — والطلب الواحد قد يُنازَع فيه على أكثر من محور"
        values={item.axes}
        onChange={(axes) => onChange({ axes })}
        options={AXIS_OPTIONS}
      />
      <LinesField
        label="عناصر الاستحقاق / أركان الدفع"
        hint="سطر لكل عنصر، وكل عنصر موضعُ دفعٍ مستقلّ"
        value={item.elements}
        onChange={(elements) => onChange({ elements })}
        placeholder={prefixes[0]}
      />
      <div className="grid grid-cols-1 gap-2">
        <LinesField
          label="وقائع مؤيِّدة"
          hint="مفاتيح وقائع من السجلّ، سطر لكل مفتاح"
          value={item.supportingFacts}
          onChange={(supportingFacts) => onChange({ supportingFacts })}
          placeholder={prefixes[1]}
        />
        <LinesField
          label="وقائع الخصم"
          hint="تُذكر لأنّ ذكرها يمنع أن يُبنى عليها بلا وعي بها"
          value={item.opposingFacts}
          onChange={(opposingFacts) => onChange({ opposingFacts })}
          placeholder={prefixes[2]}
        />
        <LinesField
          label="المستندات بين أيدينا"
          hint="سطر لكل مستند"
          value={item.evidence}
          onChange={(evidence) => onChange({ evidence })}
          placeholder={prefixes[3]}
        />
        <LinesField
          label="ما يلزم لإثبات ما تمسّكنا به"
          hint="سطر لكل مطلوب"
          value={item.documentsRequired}
          onChange={(documentsRequired) => onChange({ documentsRequired })}
          placeholder={prefixes[4]}
        />
      </div>
      <Field
        label="الردّ القانوني على هذا البند"
        value={item.response}
        onChange={(response) => onChange({ response })}
      />
      <Field
        label="النتيجة المطلوبة"
        value={item.outcomeSought}
        onChange={(outcomeSought) => onChange({ outcomeSought })}
        placeholder="إلزام المدّعى عليه بالمبلغ"
      />
    </>
  );
}

/** مدخلات الفحوص الأربعة كاملةً — حالةٌ مرفوعة، وعرضٌ هنا فقط. */
function GenerateInputsSection({
  inputs,
  setInputs,
  openGroup,
  setOpenGroup,
}: {
  inputs: GenerateInputsState;
  setInputs: React.Dispatch<React.SetStateAction<GenerateInputsState>>;
  openGroup: InputGroupKey | null;
  setOpenGroup: (key: InputGroupKey | null) => void;
}) {
  const toggleGroup = (key: InputGroupKey) =>
    setOpenGroup(openGroup === key ? null : key);

  const setClaims = (claims: MatrixItemForm[]) =>
    setInputs((state) => ({ ...state, claims }));
  const setDefences = (defences: DefenceForm[]) =>
    setInputs((state) => ({ ...state, defences }));
  const setAuthorities = (authorities: AuthorityForm[]) =>
    setInputs((state) => ({ ...state, authorities }));
  const setDeadlines = (deadlines: DeadlineRuleForm[]) =>
    setInputs((state) => ({ ...state, deadlines }));
  const setRules = (rules: RuleForm[]) => setInputs((state) => ({ ...state, rules }));

  const patchAt = <T,>(
    list: T[],
    index: number,
    patch: Partial<T>
  ): T[] => list.map((item, i) => (i === index ? { ...item, ...patch } : item));

  return (
    <div className="space-y-3">
      <div className="space-y-1">
        <p className="text-sm font-medium text-slate-300">مدخلات الفحوص الأربعة</p>
        <p className="text-xs leading-relaxed text-slate-500">
          تُدخَل هنا لأن المنصّة **لا تخترعها**: لا طلبَ ولا سندَ ولا قاعدةَ موعدٍ
          ولا قاعدةَ تُبنى من المسودّة. وما تُتركه فارغاً **يبقى غائباً**، فتقول
          لوحته «لم تُبنَ» — وهو الصدق نفسه، لا «فُحصت فسلمت».
        </p>
      </div>

      {/* ── الطلبات والدفوع — `_matrix_from_payload` ─────────────────────── */}
      <InputGroupBox
        title="الطلبات والدفوع"
        note="مصفوفة الدعوى: كل طلب ودفع بمفتاحه ونصّه ومحاوره. ولا تُبنى من الوقائع بل تُدخَل — وإحدى القائمتين على الأقل لازمة، وتركُ المجموعة فارغةٍ يعني «لم تُفحَص»."
        count={inputs.claims.length + inputs.defences.length}
        open={openGroup === "claims"}
        onToggle={() => toggleGroup("claims")}
      >
        <div className="grid grid-cols-2 gap-2">
          <EnumField
            label="المرحلة"
            value={inputs.stage}
            onChange={(stage) => setInputs((state) => ({ ...state, stage }))}
            options={STAGE_OPTIONS}
            emptyLabel="لم تُحدَّد — يُعلَن أن فحص المرحلة لم يجرِ"
          />
          <EnumField
            label="صفتنا في النزاع"
            value={inputs.ourParty}
            onChange={(ourParty) => setInputs((state) => ({ ...state, ourParty }))}
            options={PARTY_OPTIONS}
            emptyLabel="لم تُحدَّد"
          />
        </div>

        {inputs.claims.map((item, index) => (
          <ItemBox
            key={index}
            title={`طلب ${ordinal(index)}`}
            onRemove={() => setClaims(inputs.claims.filter((_, i) => i !== index))}
            removeTitle="حذف الطلب"
          >
            <MatrixItemFields
              item={item}
              onChange={(patch) => setClaims(patchAt(inputs.claims, index, patch))}
              prefixes={[
                "إثبات علاقة العمل",
                "عقد العمل الموقَّع",
                "إشعار إنهاء بلا سبب",
                "كشف الرواتب",
                "شهادة شاهد",
              ]}
            />
          </ItemBox>
        ))}
        <AddRowButton
          label="إضافة طلب"
          onClick={() => setClaims([...inputs.claims, emptyMatrixItem()])}
        />

        {inputs.defences.map((item, index) => (
          <ItemBox
            key={index}
            title={`دفع ${ordinal(index)}`}
            onRemove={() => setDefences(inputs.defences.filter((_, i) => i !== index))}
            removeTitle="حذف الدفع"
          >
            <MatrixItemFields
              item={item}
              onChange={(patch) =>
                setDefences(patchAt<DefenceForm>(inputs.defences, index, patch))
              }
              prefixes={[
                "ميعادٌ سارٍ ولم يتحقّق سببٌ يقطعه",
                "كتاب المطالبة",
                "إقرار بالاستلام",
                "سند التمكين",
                "صحيفة الدعوى السابقة",
              ]}
            />
            <label className="flex items-center gap-2 text-xs text-slate-400">
              <input
                type="checkbox"
                className="accent-amber-600"
                checked={item.isProcedural}
                onChange={(e) =>
                  setDefences(
                    patchAt<DefenceForm>(inputs.defences, index, {
                      isProcedural: e.target.checked,
                    })
                  )
                }
              />
              دفعٌ إجرائيّ (اختصاص · قبول · تقادم · صفة · إجراء) — ويُقدَّم في الترتيب
            </label>
          </ItemBox>
        ))}
        <AddRowButton
          label="إضافة دفع"
          onClick={() => setDefences([...inputs.defences, emptyDefence()])}
        />
      </InputGroupBox>

      {/* ── سجلّ الأسانيد — `_register_from_payload` ─────────────────────── */}
      <InputGroupBox
        title="سجلّ الأسانيد"
        note="كل سند بمفتاحه واسم نظامه ونوعه. وغيابُ تاريخ النفاذ يعني «لم يُفحَص النفاذ» — لا «نافذ». وتركُ المجموعة فارغةً يعني أن سجلّ الأسانيد لم يُبنَ."
        count={inputs.authorities.length}
        open={openGroup === "authority"}
        onToggle={() => toggleGroup("authority")}
      >
        {inputs.authorities.map((item, index) => (
          <ItemBox
            key={index}
            title={`سند ${ordinal(index)}`}
            onRemove={() =>
              setAuthorities(inputs.authorities.filter((_, i) => i !== index))
            }
            removeTitle="حذف السند"
          >
            <div className="grid grid-cols-2 gap-2">
              <Field
                label="المفتاح الآلي"
                value={item.key}
                onChange={(key) =>
                  setAuthorities(patchAt(inputs.authorities, index, { key }))
                }
                placeholder="labour_law_33"
                dir="ltr"
              />
              <Field
                label="المادة"
                value={item.article}
                onChange={(article) =>
                  setAuthorities(patchAt(inputs.authorities, index, { article }))
                }
                placeholder="المادة ٣٣"
              />
            </div>
            <Field
              label="اسم النظام"
              value={item.instrument}
              onChange={(instrument) =>
                setAuthorities(patchAt(inputs.authorities, index, { instrument }))
              }
              placeholder="قانون تنظيم علاقات العمل"
            />
            <EnumField
              label="نوع السند"
              value={item.kind}
              onChange={(kind) =>
                setAuthorities(patchAt(inputs.authorities, index, { kind }))
              }
              options={SOURCE_KIND_OPTIONS}
            />
            <Field
              label="المصدر الرسمي"
              value={item.officialSource}
              onChange={(officialSource) =>
                setAuthorities(patchAt(inputs.authorities, index, { officialSource }))
              }
              placeholder="الجريدة الرسمية — العدد ٥٨٧"
            />
            <div className="grid grid-cols-2 gap-2">
              <Field
                label="نافذ من"
                value={item.inForceFrom}
                onChange={(inForceFrom) =>
                  setAuthorities(patchAt(inputs.authorities, index, { inForceFrom }))
                }
                dir="ltr"
                type="date"
              />
              <Field
                label="نافذ إلى"
                value={item.inForceTo}
                onChange={(inForceTo) =>
                  setAuthorities(patchAt(inputs.authorities, index, { inForceTo }))
                }
                dir="ltr"
                type="date"
              />
            </div>
            <div className="grid grid-cols-2 gap-2">
              <Field
                label="عُدِّل بـ"
                value={item.amendedBy}
                onChange={(amendedBy) =>
                  setAuthorities(patchAt(inputs.authorities, index, { amendedBy }))
                }
              />
              <Field
                label="مصدر النقل"
                value={item.retrievedFrom}
                onChange={(retrievedFrom) =>
                  setAuthorities(patchAt(inputs.authorities, index, { retrievedFrom }))
                }
              />
            </div>
            <LinesField
              label="شروط الانطباق"
              hint="سطر لكل شرط"
              value={item.conditions}
              onChange={(conditions) =>
                setAuthorities(patchAt(inputs.authorities, index, { conditions }))
              }
            />
            <LinesField
              label="الاستثناءات"
              hint="سطر لكل استثناء"
              value={item.exceptions}
              onChange={(exceptions) =>
                setAuthorities(patchAt(inputs.authorities, index, { exceptions }))
              }
            />
          </ItemBox>
        ))}
        <AddRowButton
          label="إضافة سند"
          onClick={() => setAuthorities([...inputs.authorities, emptyAuthority()])}
        />
      </InputGroupBox>

      {/* ── قواعد المواعيد — `_deadlines_from_payload` ───────────────────── */}
      <InputGroupBox
        title="قواعد المواعيد"
        note="القواعد يكتبها المحامي والمنصّة تحسب ولا تخترع. والعدّ **إلزاميّ**: العدّ قرارٌ قانونيّ في القاعدة، لا عرفٌ في الكود. وتاريخ البداية يأتي من ملف القضية لا من هنا."
        count={inputs.deadlines.length}
        open={openGroup === "deadlines"}
        onToggle={() => toggleGroup("deadlines")}
      >
        {inputs.deadlines.map((item, index) => (
          <ItemBox
            key={index}
            title={`قاعدة موعد ${ordinal(index)}`}
            onRemove={() =>
              setDeadlines(inputs.deadlines.filter((_, i) => i !== index))
            }
            removeTitle="حذف قاعدة الموعد"
          >
            <div className="grid grid-cols-2 gap-2">
              <Field
                label="المفتاح الآلي"
                value={item.key}
                onChange={(key) =>
                  setDeadlines(patchAt(inputs.deadlines, index, { key }))
                }
                placeholder="appeal_window"
                dir="ltr"
              />
              <Field
                label="النصّ"
                value={item.label}
                onChange={(label) =>
                  setDeadlines(patchAt(inputs.deadlines, index, { label }))
                }
                placeholder="ميعاد الاستئناف"
              />
            </div>
            <div className="grid grid-cols-2 gap-2">
              <Field
                label="المقدار"
                value={item.amount}
                onChange={(amount) =>
                  setDeadlines(patchAt(inputs.deadlines, index, { amount }))
                }
                type="number"
                min={1}
                dir="ltr"
                placeholder="30"
              />
              <EnumField
                label="الوحدة"
                value={item.unit}
                onChange={(unit) =>
                  setDeadlines(patchAt(inputs.deadlines, index, { unit }))
                }
                options={UNIT_OPTIONS}
              />
            </div>
            <EnumField
              label="العدّ (الاتفاقية)"
              value={item.conventionKey}
              onChange={(conventionKey) =>
                setDeadlines(patchAt(inputs.deadlines, index, { conventionKey }))
              }
              options={CONVENTION_OPTIONS}
              emptyLabel="لم يُختَر — والعدّ لا يُخترع"
            />
            <Field
              label="المصدر"
              value={item.source}
              onChange={(source) =>
                setDeadlines(patchAt(inputs.deadlines, index, { source }))
              }
              placeholder="المادة ١٥٩ من قانون الإجراءات المدنية"
            />
            <Field
              label="ملاحظة"
              value={item.note}
              onChange={(note) => setDeadlines(patchAt(inputs.deadlines, index, { note }))}
            />
          </ItemBox>
        ))}
        <AddRowButton
          label="إضافة قاعدة موعد"
          onClick={() => setDeadlines([...inputs.deadlines, emptyDeadlineRule()])}
        />
      </InputGroupBox>

      {/* ── القواعد — `_rules_from_payload` ──────────────────────────────── */}
      <InputGroupBox
        title="القواعد"
        note="العائلة أوّل سؤال: فحصٌ ثابت لا تاريخ له، أو حكمٌ موضوعي **لا يوجد بلا تاريخ نفاذ** — والخادم يفرض الأمرين. وإرسال تاريخ على فحصٍ يرفعه كما يرفع حكماً بلا تاريخ."
        count={inputs.rules.length}
        open={openGroup === "rules"}
        onToggle={() => toggleGroup("rules")}
      >
        {inputs.rules.map((item, index) => (
          <ItemBox
            key={index}
            title={`قاعدة ${ordinal(index)}`}
            onRemove={() => setRules(inputs.rules.filter((_, i) => i !== index))}
            removeTitle="حذف القاعدة"
          >
            <div className="grid grid-cols-2 gap-2">
              <Field
                label="المفتاح الآلي"
                value={item.key}
                onChange={(key) => setRules(patchAt(inputs.rules, index, { key }))}
                placeholder="notice.basis"
                dir="ltr"
              />
              <Field
                label="الموضوع"
                value={item.subject}
                onChange={(subject) =>
                  setRules(patchAt(inputs.rules, index, { subject }))
                }
                placeholder="notice"
                dir="ltr"
              />
            </div>
            <LinesField
              label="نصّ القاعدة"
              hint="سطر أو سطران بالعربية — وهو ما يُعرض ويُقارَن"
              value={item.statement}
              onChange={(statement) =>
                setRules(patchAt(inputs.rules, index, { statement }))
              }
            />
            <EnumField
              label="العائلة"
              value={item.family}
              onChange={(family) =>
                setRules(patchAt(inputs.rules, index, { family, inForceFrom: "" }))
              }
              options={RULE_FAMILY_OPTIONS}
            />
            <div className="grid grid-cols-2 gap-2">
              {/* ⚠️ والتاريخ يُعرَض للموضوعي وحده: عرضُه على الفحص يدعو إلى
                  كتابته، وكتابتُه عليه ترفعه `rules.py` في البناء. */}
              {item.family === "substantive" ? (
                <Field
                  label="نافذ من (YYYY-MM-DD)"
                  value={item.inForceFrom}
                  onChange={(inForceFrom) =>
                    setRules(patchAt(inputs.rules, index, { inForceFrom }))
                  }
                  type="date"
                  dir="ltr"
                />
              ) : (
                <div className="space-y-1">
                  <label className="text-xs font-medium text-slate-400">
                    تاريخ النفاذ
                  </label>
                  <p className="border border-slate-800/70 bg-slate-950/60 px-2 py-2 text-xs text-slate-500">
                    لا تاريخ لفحصٍ ثابت — وإرسالُ تاريخ عليه يوهم بأنه سيُراجَع.
                  </p>
                </div>
              )}
              <Field
                label="السند"
                value={item.source}
                onChange={(source) => setRules(patchAt(inputs.rules, index, { source }))}
                placeholder="المادة ٥ من قانون المعاملات المدنية"
              />
            </div>
            <ToggleGroup
              label="أنواع النزاع التي تخصّها"
              hint="والفراغ يعني: لا تخصّ نوعاً بعينه فتسري على كل الأنواع"
              values={item.appliesTo}
              onChange={(appliesTo) =>
                setRules(patchAt(inputs.rules, index, { appliesTo }))
              }
              options={DISPUTE_TYPE_OPTIONS}
            />
            <ToggleGroup
              label="المراحل التي تسري فيها"
              hint="والفراغ يعني: كل المراحل"
              values={item.stages}
              onChange={(stages) => setRules(patchAt(inputs.rules, index, { stages }))}
              options={CASE_STAGE_OPTIONS}
            />
            <LinesField
              label="نسخت القواعد"
              hint="مفاتيح القواعد التي حلّت هذه محلّها — والاتّجاه لا يُعكس"
              value={item.supersedes}
              onChange={(supersedes) =>
                setRules(patchAt(inputs.rules, index, { supersedes }))
              }
            />
            <Field
              label="ملاحظة"
              value={item.note}
              onChange={(note) => setRules(patchAt(inputs.rules, index, { note }))}
            />
          </ItemBox>
        ))}
        <AddRowButton
          label="إضافة قاعدة"
          onClick={() => setRules([...inputs.rules, emptyRule()])}
        />
      </InputGroupBox>
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
  const [languageReport, setLanguageReport] = useState<LanguageReport | null>(null);
  // تقرير المراجعة الثانية («المفتش ثُغرة») — يصل قبل "done" كتقريرَي الأسانيد
  // واللغة، فيكون جاهزاً حين يُعرض المستند. انظر `_review_round` في main.py.
  const [reviewReport, setReviewReport] = useState<ReviewReport | null>(null);
  // ⚠️ وثلاثة إطارات كانت يُبثّها الخادم وتُهمَل هنا بصمت — فكان عمل
  // `case_file.py` و`facts.py` و`briefing.py` يصل ثم يُسقَط، واثنان من سلَم
  // المنتج (التقرير الداخلي وتقرير الوقائع) لا يبلغان المحامي أصلاً.
  // وترتيب وصولها هو ترتيب `_stream_agent`: case ← … ← facts ← briefing ← done.
  const [caseFrame, setCaseFrame] = useState<CaseFrame | null>(null);
  const [factsFrame, setFactsFrame] = useState<FactsFrame | null>(null);
  const [briefingFrame, setBriefingFrame] = useState<BriefingFrame | null>(null);
  // ⚠️ وإطار رابع كان يُبثّ (نوع `revision`) ويُهمَل هنا بصمت، فقائمة الأخطاء
  // الموحّدة تصل ثم تُسقَط. وترتيبه في `_stream_agent` قبل `briefing`، لأنّه
  // يُبنى بعد الفحوص وقبل التقرير الذي يجمعها.
  const [revisionFrame, setRevisionFrame] = useState<RevisionFrame | null>(null);
  // ⚠️ وأربعة إطارات تُبثّ **بين `facts` و`revision`** وتُهمَل هنا بصمت:
  // `claims` ثم `authority` ثم `deadlines` ثم `rules` (ترتيب `_stream_agent`).
  // وكانت تصل ثم تُسقَط، فلا يرى المحامي عبء الإثبات ولا الفحص الزمنيّ ولا
  // المواعيد المحسوبة ولا القواعد المنطبقة — وهي عملُ أربع وحدات كاملة.
  const [claimsFrame, setClaimsFrame] = useState<ClaimsFrame | null>(null);
  const [authorityFrame, setAuthorityFrame] = useState<AuthorityFrame | null>(null);
  const [deadlinesFrame, setDeadlinesFrame] = useState<DeadlinesFrame | null>(null);
  const [rulesFrame, setRulesFrame] = useState<RulesFrame | null>(null);

  // ⚠️ ومدخلات الفحوص الأربعة **حالةٌ مرفوعة هنا** لا داخل النموذج: يُقرأ منها
  // `buildGeneratePayload` عند الإرسال، ويُعرض منها النموذج في العمود الأيمن.
  // وموضعها في هذه الدالّة مقصود — فحالتها تعيش ما دامت الصفحة، ولا تُصفَّر مع
  // كل جولة (المحامي يُصلح مسودّةً ويُعيد الإرسال بالمدخلات نفسها).
  const [generateInputs, setGenerateInputs] = useState<GenerateInputsState>(
    emptyGenerateInputs
  );
  // المجموعة المفتوحة في النموذج — واحدةٌ في الوقت (طيّ لا نموذجٌ مُغرِق).
  const [openInputGroup, setOpenInputGroup] = useState<InputGroupKey | null>(null);
  // ⚠️ **ونصّ المنع يُحسَب من المدخلات لا يُنتظر من الخادم**: ما يردّه الخادم
  // ٤٠٠ (بندٌ بلا نصّ · عدٌّ غير مختار · حكمٌ موضوعي بلا تاريخ · فحصٌ بتاريخ)
  // يُقال هنا قبل الإرسال. والحكم نفسه في `generate-inputs.ts`، وهي القراءة
  // الوحيدة للحالة — فلا حاكمان يفترقان.
  const inputProblem = describeInputProblems(generateInputs);

  // مراحل العمل — تُشغّل مشهد «فريق المكتب».
  // ⚠️ المفاتيح تأتي من الخادم (`stage` في إطار SSE) ولا تُخمَّن هنا. فالمشهد
  // يعكس ما جرى فعلاً: أي أداة استُدعيت، ومن لم يُستدعَ يبقى على قهوته.
  const [activeStage, setActiveStage] = useState("");
  const [completedStages, setCompletedStages] = useState<string[]>([]);
  const [startedAt, setStartedAt] = useState(0);

  // آخر مرحلة عملت — للمقارنة عند وصول مرحلة جديدة.
  // المرجع (ref) لا حالة: القيمة تُقرأ وتُكتب داخل معالج البثّ بلا حاجة لإعادة
  // رسم، واستخدام حالة هنا كان سيقرأ قيمة قديمة داخل الحلقة.
  const lastStageRef = useRef("");

  // معرّف الجلسة يُولَّد **عند الإرسال** لا عند العرض.
  // السبب: `crypto.randomUUID()` لا يعمل على الخادم، وتوليده أثناء العرض يُنتج
  // قيمة مختلفة على الخادم والعميل فيكسر الترطيب (hydration mismatch).
  const sessionIdRef = useRef("");

  // المستند بعد التنظيف — يُستخدم للعرض والنسخ معاً حتى لا يختلف ما تراه عمّا تنسخه
  const cleanDocument = stripMarkdownArtifacts(finalDocument);

  const handleGenerate = async () => {
    if (!prompt.trim()) return;

    // ⚠️ **والحمل يُبنى هنا لا عند العرض**، ونتيجته تُقرأ لا تُفترض: مدخلٌ
    // ناقصٌ يردّه الخادم ٤٠٠ («طلبٌ بلا نصّ» · «حكمٌ موضوعي بلا تاريخ») — فلو
    // أُرسل، كُتبت الوقائع ثم ضاع النداء. فيُوقف هنا بنصٍّ صريح.
    const built = buildGeneratePayload(generateInputs);
    if (!built.ok) {
      setErrorMessage(`تعذّر إرسال المدخلات: ${built.message}`);
      setStatus("error");
      return;
    }

    setStatus("processing");
    setLiveMessage("جاري إيقاظ فريق العقل القانوني...");
    setFinalDocument("");
    setErrorMessage("");
    setCitationReport(null);
    setLanguageReport(null);
    setReviewReport(null);
    // ⚠️ وتُصفَّر معها إطارات الجولة السابقة: تقرير قضيةٍ سابقة معروضاً فوق
    // مستندٍ جديد **أسوأ من غيابه**، لأن المحامي يقرأ نواقص قد سُدّت.
    setCaseFrame(null);
    setFactsFrame(null);
    setBriefingFrame(null);
    // ⚠️ وتُصفَّر معها قائمة الجولة السابقة: أخطاء مسودّة قديمة معروضةً فوق
    // مستندٍ جديد أسوأ من غيابها، لأن المحامي يقرأ عيوباً قد أُصلحت.
    setRevisionFrame(null);
    // ⚠️ وتُصفَّر معها الإطارات الأربعة للسبب نفسه: عبءُ إثباتٍ أو موعدٌ من
    // جولة سابقة معروضاً فوق مسودّة جديدة **أسوأ من غيابه** — يُقرأ إقراراً
    // بأن الفحص جرى على هذا النصّ.
    setClaimsFrame(null);
    setAuthorityFrame(null);
    setDeadlinesFrame(null);
    setRulesFrame(null);

    // تصفير مشهد المكتب — وإلا ظهر الفريق وقد «أنجز» عمل الطلب السابق
    setActiveStage("");
    setCompletedStages([]);
    lastStageRef.current = "";
    // وقت البدء يُضبط هنا (معالج حدث على العميل) لا أثناء العرض، تفادياً
    // لاختلاف قيمة الوقت بين الخادم والعميل.
    setStartedAt(Date.now());

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
        body: JSON.stringify({
          prompt,
          doc_type: docType,
          // ⚠️ وحملُ الفحوص الأربعة يُضمّ إلى الطلب من موضعٍ واحد معلوم
          // (`buildGeneratePayload` في `./generate-inputs`)، **والمفاتيح الأربعة
          // تغيب إذا لم تُدخَل**: الغياب يعني «لم يُبنَ»، فتقول اللوحة «لم تُبنَ»
          // بنصّ الخادم. ⚠️ ولا يُرسَل كائنٌ فارغ — `{}` في `claims` يعني «حملُ
          // مصفوفة بلا طلبات»، وهو ٤٠٠ لا «لم يُفحَص».
          ...built.payload,
        }),
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

            // مشهد المكتب يتحرّك بالمفاتيح الحقيقية القادمة من الخادم.
            // ومن كان يعمل ثم جاءت مرحلة جديدة فقد أنجز مهمته.
            const stageKey = event.stage;
            if (stageKey) {
              const previous = lastStageRef.current;
              if (previous && previous !== stageKey) {
                setCompletedStages((list) =>
                  list.includes(previous) ? list : [...list, previous]
                );
              }
              lastStageRef.current = stageKey;
              setActiveStage(stageKey);
            }
          } else if (event.type === "case") {
            // ⚠️ أول إطار يُبثّ (انظر `_sse_generator` في main.py)، ويصل قبل
            // أول مرحلة. وربطه بالمفتاح لا بالنصّ: `established: false` تعني
            // أنّ الملف **لم يُبنَ** — فلا تُعرض «لا نواقص» عن فحص لم يجرِ.
            setCaseFrame(event.report);
          } else if (event.type === "citations") {
            // يصل قبل "done" — فالتقرير جاهز حين يُعرض المستند
            setCitationReport(event.report);
          } else if (event.type === "language") {
            setLanguageReport(event.report);
          } else if (event.type === "review") {
            // ⚠️ يصل بصمتٍ لا إطار فشل: فشل المُراجع لا يُسقط التوليد (انظر
            // main.py)، بل يُعلَن داخل التقرير نفسه (`failed`) فتعرضه اللوحة.
            setReviewReport(event.report);
          } else if (event.type === "facts") {
            // ⚠️ ويصل **دائماً** حتى حين لا يُرسل سجلّ — بنصّ «لم يُشغَّل» لا
            // بحذف اللوحة (انظر `_facts_frame` في main.py): حذفُها يُقرأ
            // سكوتاً، والسكوت في موضع فحصٍ يُقرأ سلامة.
            setFactsFrame(event.report);
          } else if (event.type === "claims") {
            // ⚠️ **والحكم على `built` وحده**: `false` تعني أن المصفوفة **لم
            // تُبنَ** — فلا يُقرأ فراغ `errors` سلامةً، بل يُعرض نصّ الخادم.
            setClaimsFrame(event.report);
          } else if (event.type === "authority") {
            // ⚠️ والإطار يُبثّ **دائماً** ولو غاب السجلّ (انظر `_authority_frame`):
            // حذفُه يُقرأ سكوتاً، والسكوت في موضع فحصٍ يُقرأ سلامة.
            setAuthorityFrame(event.report);
          } else if (event.type === "deadlines") {
            // ⚠️ وموعدٌ مُخترع يُبنى عليه إجراء يتساقط؛ فبغياب التاريخ يُقال
            // «لم يُحسَب» ولا يُدّعى موعد.
            setDeadlinesFrame(event.report);
          } else if (event.type === "rules") {
            // ⚠️ والسجلّ الفارغ يُعلَن فارغاً — **ولا يُعرض كأنه فحصٌ تمّ**.
            setRulesFrame(event.report);
          } else if (event.type === "briefing") {
            // ⚠️ القاموس والنصّ معاً، والنصّ هو المعروض. ولماذا الاثنان؟
            // لأن `report.sources[].present` هو الوحيد الذي يقول أيّ فحص
            // **لم يُشغَّل**، ولا يحمله النصّ بمفتاح آلي.
            setBriefingFrame({
              report: event.report,
              markdown: event.markdown,
            });
          } else if (event.type === "revision") {
            // ⚠️ **والحكم على `collected` وحده**: الإطار يحمل قائمة الأخطاء
            // معاً، والقائمة الفارغة فيه لا تفرّق بين «فُحص فلم يُوجد عيب» و«لم
            // يُفحص شيء» — وكلتاهما فارغة. ولا يُقرأ الفراغ سلامةً: اللوحة
            // تعرض نصّ الخادم عند تعذّر الجمع، ولا تقول «لا أخطاء» أبداً.
            setRevisionFrame(event.report);
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
          <Card className="bg-slate-900 border-slate-800 text-white">
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
                  className="w-full p-3 bg-slate-950 border border-slate-800 text-white focus:ring-amber-500"
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

              {/* ⚠️ **ومدخلات الفحوص الأربعة قبل زرّ الإرسال**، لأنها مدخلات
                  الطلب لا ملحقٌ به: من كتب وقائعه ثم أرسل بلا مصفوفةٍ ولا سندٍ
                  يقرأ في اللوحات «لم تُبنَ» — وهو صحيح، لكنه يُدخِلها الآن. */}
              <GenerateInputsSection
                inputs={generateInputs}
                setInputs={setGenerateInputs}
                openGroup={openInputGroup}
                setOpenGroup={setOpenInputGroup}
              />

              {/* ⚠️ **والمنع معلنٌ قبل الإرسال لا بعده**: المدخل الذي يردّه
                  الخادم ٤٠٠ يُقال هنا بنصّه («حكمٌ موضوعي بلا تاريخ نفاذ» ·
                  «العدّ غير مختار») — فلا يكتب المحامي وقائعه ثم يضيع النداء. */}
              {inputProblem ? (
                <p
                  className="border border-amber-900/60 bg-amber-950/30 p-3 text-xs leading-relaxed text-amber-300"
                  dir="auto"
                >
                  {inputProblem}
                </p>
              ) : null}

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
              >
                {/* الفريق حاضر من البداية: يرى المحامي من سيعمل على مستنده
                    قبل أن يكتب حرفاً. والوضع الافتراضي ليس فراغاً. */}
                <OfficeScene />
                <div className="mt-4 flex flex-col items-center justify-center border-2 border-dashed border-slate-800 py-8 text-slate-500">
                  <FileText className="w-8 h-8 mb-2 opacity-50" />
                  <p className="text-sm">المستند النهائي سيظهر هنا</p>
                </div>
              </motion.div>
            )}

            {status === "processing" && (
              <motion.div
                key="processing"
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -20 }}
              >
                <OfficeScene
                  activeStage={activeStage}
                  completedKeys={completedStages}
                  message={liveMessage}
                  startedAt={startedAt}
                />
              </motion.div>
            )}

            {status === "error" && (
              <motion.div 
                key="error"
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -20 }}
                className="h-full min-h-[500px] flex flex-col items-center justify-center bg-slate-900 border border-red-900/50 p-8"
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
                className="bg-white text-slate-900 overflow-hidden"
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
                {/* من عمل فعلاً على هذا المستند — ومن لم يُستدعَ يغيب عن الشريط */}
                <TeamStrip
                  stageKeys={[...completedStages, activeStage].filter(Boolean)}
                />
                {/* ⚠️ وترتيب اللوحات هو **ترتيب العمل** في `_stream_agent` لا
                    ترتيب كتابتها: ملف القضية (قبل الوكيل) ← الأسانيد ← اللغة
                    ← المراجعة ← الوقائع ← التقرير الداخلي. والوقائع **قبل**
                    التقرير بقصد: الافتراق يُرى قبل التقرير الذي يجمعه، لا
                    بعده. */}
                <CasePanel frame={caseFrame} />
                <CitationsPanel report={citationReport} />
                <LanguagePanel report={languageReport} />
                <ReviewPanel report={reviewReport} />
                {/* ⚠️ الوقائع آخر لوحة **حاكمة** على المسودّة، وآخر ما يجب أن
                    يُقرأ قبل اعتمادها: هي الوحيدة التي تقابل النصّ بسجلّ. */}
                <FactsPanel frame={factsFrame} />
                {/* ⚠️ وترتيب الأربعة هو ترتيب بثّها في `_stream_agent`: المصفوفة
                    ← الأسانيد ← المواعيد ← القواعد. وعبءُ الإثبات **قبل**
                    الأسانيد لأن الفحص الزمنيّ للأسانيد يُقرأ على طلباتٍ عُرفت. */}
                <ClaimsPanel frame={claimsFrame} />
                <AuthorityPanel frame={authorityFrame} />
                <DeadlinesPanel frame={deadlinesFrame} />
                <RulesPanel frame={rulesFrame} />
                {/* والتقرير الداخلي آخر اللوحات — لأنه آخر إطار تقرير يُبنى،
                    ولأنه ورقة عمل تُقرأ بعد الفحوص لا قبلها. */}
                <BriefingPanel frame={briefingFrame} />
                {/* ⚠️ وقائمة الأخطاء الموحّدة بعد التقرير: هي حكم الفحوص على
                    المسودّة مجتمعةً، وآخر ما يُقرأ قبل قرار الاعتماد. */}
                <RevisionPanel frame={revisionFrame} />
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
