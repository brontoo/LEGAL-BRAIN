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
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { OfficeScene, TeamStrip } from "@/components/office-scene";
import { ReviewPanel, type ReviewReport } from "@/components/review-panel";

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

type StreamEvent =
  | { type: "stage"; stage?: string; message: string }
  | { type: "case"; report: CaseFrame }
  | { type: "citations"; report: CitationsReport }
  | { type: "language"; report: LanguageReport }
  | { type: "review"; report: ReviewReport }
  | { type: "facts"; report: FactsFrame }
  | { type: "briefing"; report: BriefingFrame["report"]; markdown: string }
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
        <div className="whitespace-pre-wrap border border-red-200 bg-red-50 p-3 text-sm text-red-700">
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
          } else if (event.type === "briefing") {
            // ⚠️ القاموس والنصّ معاً، والنصّ هو المعروض. ولماذا الاثنان؟
            // لأن `report.sources[].present` هو الوحيد الذي يقول أيّ فحص
            // **لم يُشغَّل**، ولا يحمله النصّ بمفتاح آلي.
            setBriefingFrame({
              report: event.report,
              markdown: event.markdown,
            });
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
                {/* والتقرير الداخلي آخر اللوحات — لأنه آخر إطار تقرير يُبنى،
                    ولأنه ورقة عمل تُقرأ بعد الفحوص لا قبلها. */}
                <BriefingPanel frame={briefingFrame} />
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
