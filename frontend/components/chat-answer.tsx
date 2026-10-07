"use client";

/**
 * جواب المحادثة وسنوده — **المكوّن الذي يحمل قاعدة الأمانة**.
 * ============================================================================
 * ⚠️ لماذا مكوّن منفصل عن الصفحة؟
 *
 * لأن الفرق بين «جواب مسنود» و«جواب بلا سند» **هو الميزة نفسها**، لا زينة
 * حولها. ولو كُتب ذلك الفرق وسط ملف الصفحة لضاع بين الحالة والطلب والإلغاء،
 * ولصار أوّل ما يُبسَّط عند أي تعديل. فالقاعدة هنا في موضع واحد يُقرأ وحده.
 *
 * ⚠️ **والقاعدتان اللتان لا تُخالَفان في هذا الملف:**
 *
 *   ١) **لا Markdown.** الجواب يُعرض نصّاً عادياً (`whitespace-pre-line`) داخل
 *      الورقة الكريمية وحدها — لا HTML ولا `dangerouslySetInnerHTML`. والوسوم
 *      الزائدة تُنزع بـ`stripMarkdownArtifacts` **المستوردة من وحدتها**
 *      (`lib/strip-markdown.ts`) — طبقة دفاعية قائمة يُعاد استعمالها، ولا
 *      تُنسخ نسخةٌ ثانية تنحرف عنها، ولا تُجرّ صفحةٌ كاملة لأجل دالّة نصّية.
 *
 *   ٢) **والسند يسبق المتن.** من قرأ أوّل سطر يجب أن يعرف: هذا مسنودٌ من
 *      المكتبة، أو هذا كلامُ النموذج وحده. فالترتيب مقصود: الحكم ← النصّ ←
 *      المصادر.
 *
 * ⚠️ **والحال الثالثة التي لا تُدمج في غيرها**: استُرجعَ من المكتبة شيء،
 *    ولم يثبت اقتباسٌ واحد (مرفوض أو غير مذكور). هي ليست «لم يُسترجع شيء»
 *    وليست «مسنود» — والمكتبة **تُسمّى فيها** كي يعرف المحامي أنّ التغطية
 *    ناقصة، لا أنّ الاسترجاع لم يجرِ.
 */

import { AlertTriangle, Quote as QuoteGlyph, ShieldAlert } from "lucide-react";
import { EngravedIcon } from "@/components/engraved-icon";
import { Card } from "@/components/ui/card";
import { stripMarkdownArtifacts } from "@/lib/strip-markdown";

/** سند أثبت الخادم أنه منقول حرفياً من مقطعٍ في الأرشيف — انظر `_verify_round`. */
export type VerifiedCitation = {
  ref: string;
  document_name: string;
  chunk_id: string;
  quoted_span: string;
  similarity: number | null;
};

/** اقتباسٌ ادّعاه النموذج ولم يثبت — يُعرض بسببه، ولا يُسقَط. */
export type RejectedCitation = { ref: string; quoted_span: string; reason: string };

/**
 * تقرير الأسانيد كما يصل في `citations` من `/chat` (وهو `_verify_round` في
 * `main.py`). **والحقول كلها تُقرأ بلا افتراض**: الخادم قد يضيف حقلاً، وقد
 * يغيب حقل — والغائب يُقرأ «غير معروف» لا صفراً.
 */
export type CitationReport = {
  summary: string;
  has_evidence: boolean;
  evidence_count: number;
  has_citation_block: boolean;
  verified: VerifiedCitation[];
  rejected: RejectedCitation[];
  unbacked_articles: { surface: string; number: string }[];
  malformed_lines: string[];
  attribution: { summary: string; error_count: number; notice_count: number } | null;
};

/**
 * نصّ التراجع الذي يصوغه الخادم في `/chat` حين لا يُنتج ردّاً أصلاً
 * (`main.py` عند `if not answer:`).
 *
 * ⚠️ ولماذا يُكتشف بنصّه؟ لأنّ الردّ في تلك الحال يصل **بلا أسانيد وبلا تقرير
 *    لغة** — أي أنّه لا يُفرَّق عن جوابٍ بلا سند إلا بهذا النصّ. ووسمه يجعل
 *    الصفحة تقول «تعذّر» بدل أن تُلبسه ثوب جواب. والنصّ من الخادم يُعرض كما
 *    هو، ولا يُعاد صياغته.
 */
export const NO_ANSWER_NOTICE = "لم أتمكّن من إنتاج ردّ";

/** ردّ الخادم بعد القراءة — ما تعرضه الصفحة، بعد التطبيع. */
export type ChatAnswer = {
  /** المتن كما أرسله الخادم (بعد نزع مخلفات Markdown) — لا يُعاد ترتيبه. */
  text: string;
  hasCitations: boolean;
  /** عدد المقاطع المسترجَعة — يفرّق «لم يُسترجع شيء» من «استُرجع ولم يُقتبس». */
  retrieved: number;
  verified: VerifiedCitation[];
  rejected: RejectedCitation[];
  /** ملخّص الخادم حرفياً، أو `""` حين لا تقرير. */
  summary: string;
  attributionSummary: string;
  malformed: number;
  unbacked: number;
  languageSummary: string;
  /** هل هذا نصّ التراجع المعلن من الخادم؟ */
  noAnswer: boolean;
};

/* ==============================================================================
   أدوات قراءة الردّ — بلا افتراض، فالغائب لا يصير صفراً
   ============================================================================== */

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function readText(value: unknown): string {
  return typeof value === "string" ? value : "";
}

function readCount(value: unknown): number {
  return typeof value === "number" && Number.isFinite(value) ? value : 0;
}

function readVerified(raw: unknown): VerifiedCitation[] {
  if (!Array.isArray(raw)) return [];
  return raw.filter(isRecord).map((row) => ({
    ref: readText(row.ref),
    document_name: readText(row.document_name),
    /* المعرّف يُعرض نصّاً لا عدداً: قد يكون `"12"` أو `"L3-12"`، فتحويله
       رقماً يُفقد شكله الذي يُقابله المحامي في الأرشيف. */
    chunk_id: typeof row.chunk_id === "string" ? row.chunk_id : String(row.chunk_id ?? ""),
    quoted_span: readText(row.quoted_span),
    similarity: typeof row.similarity === "number" ? row.similarity : null,
  }));
}

function readRejected(raw: unknown): RejectedCitation[] {
  if (!Array.isArray(raw)) return [];
  return raw.filter(isRecord).map((row) => ({
    ref: readText(row.ref),
    quoted_span: readText(row.quoted_span),
    reason: readText(row.reason),
  }));
}

/**
 * يقرأ ردّ `/chat` ويبني ما تعرضه الصفحة.
 *
 * ⚠️ الحكم على `has_evidence` **مع** طول `verified`، لا على أحدهما: الأول كلمة
 *    الخادم والثاني ما نستطيع عرضه، ولو اختلفا كان العرض أضعف من الحكم أو
 *    أقوى منه. فالسند المعروض هو `verified`، والحكم يُبنى على الاثنين معاً.
 */
export function readAnswer(payload: unknown): ChatAnswer {
  const source = isRecord(payload) ? payload : {};
  const report = isRecord(source.citations) ? source.citations : {};
  const language = isRecord(source.language) ? source.language : {};

  const verified = readVerified(report.verified);
  const rejected = readRejected(report.rejected);
  const raw = readText(source.response);

  return {
    text: stripMarkdownArtifacts(raw),
    hasCitations: report.has_evidence === true && verified.length > 0,
    retrieved: readCount(report.evidence_count),
    verified,
    rejected,
    summary: readText(report.summary),
    attributionSummary: isRecord(report.attribution)
      ? readText(report.attribution.summary)
      : "",
    malformed: Array.isArray(report.malformed_lines) ? report.malformed_lines.length : 0,
    unbacked: Array.isArray(report.unbacked_articles) ? report.unbacked_articles.length : 0,
    languageSummary: readText(language.summary),
    noAnswer: raw.includes(NO_ANSWER_NOTICE),
  };
}

/* ==============================================================================
   الورقة واللوحة
   ============================================================================== */

/**
 * متن الجواب — **نصّ عادي لا Markdown**.
 *
 * ⚠️ ولا مكوّن Markdown ولا `dangerouslySetInnerHTML`: محتوى الجواب نصّ يولّده
 *    نموذج، وأي تفسير لوسومه يعني تمرير نصٍّ مولَّد إلى HTML. و`whitespace-pre-line`
 *    وحدها تكفي لتحترم فواصل الأسطر كما كتبها الخادم.
 *
 * ⚠️ واللونان من الورقة نفسها التي في `app/library/page.tsx` — الجواب ورقة،
 *    فحبرُه حبرُها، والاستثناء الوحيد أنّ هذه ورقةٌ **بلا ترويسة**: الجواب ليس
 *    مستنداً مُصدَّراً، ووضع اسم المكتب عليه يجعله يبدو كذلك.
 */
function AnswerBody({ text, onPaper }: { text: string; onPaper: boolean }) {
  if (!text) {
    return <p className={onPaper ? "text-[#5c5344]" : "text-slate-500"}>—</p>;
  }

  return (
    <p
      dir="auto"
      className={
        onPaper
          ? "whitespace-pre-line break-words font-heading text-[15px] leading-loose text-[#16130F]"
          : "whitespace-pre-line break-words text-sm leading-relaxed text-slate-300"
      }
    >
      {text}
    </p>
  );
}

/**
 * بطاقة سند واحد — **اسم المستند أولاً**، لأنّه ما يحتاجه المحامي ليذهب ويقرأ.
 *
 * ⚠️ ولا سطر «الصفحة»: تقرير الخادم يحمل `chunk_id` لا رقم صفحة، وطباعة رقم
 *    مخترع في موضع الإسناد أسوأ من غيابه. فالمعروض ثلاثة حقول حقيقية: المرجع
 *    (`ref`) والمعرّف (`chunk_id`) والنصّ المنقول حرفياً.
 */
function CitationCard({ citation }: { citation: VerifiedCitation }) {
  return (
    <Card
      size="sm"
      className="gap-3 border border-slate-800 bg-slate-900 py-4 ring-0"
    >
      <div className="flex flex-wrap items-start justify-between gap-3 px-4">
        <div className="flex min-w-0 items-center gap-2">
          <EngravedIcon name="papers" className="size-4 text-amber-500" />
          <span className="break-words font-medium text-slate-200">
            {citation.document_name || "بلا اسم"}
          </span>
        </div>

        <span className="flex shrink-0 items-center gap-2 text-[11px] text-slate-500">
          {citation.ref && (
            <span className="border border-amber-500/25 px-2 py-0.5 tracking-[0.15em] text-amber-500">
              {citation.ref}
            </span>
          )}
          {citation.chunk_id && (
            <span className="font-mono" dir="ltr">
              #{citation.chunk_id}
            </span>
          )}
        </span>
      </div>

      {citation.quoted_span ? (
        <p
          dir="auto"
          className="border-s-2 border-amber-500/30 px-4 ps-3 text-sm leading-relaxed text-slate-300"
        >
          {citation.quoted_span}
        </p>
      ) : (
        <p className="px-4 text-xs text-slate-500">
          لم يُرفق نصّ مقتبس مع هذا السند — راجعه في المستند نفسه.
        </p>
      )}
    </Card>
  );
}

/** سند مرفوض — يُعرض بالسبب الذي كتبه الخادم، فلا يبقى الرفض سرّاً. */
function RejectedRow({ citation }: { citation: RejectedCitation }) {
  return (
    <li className="border border-slate-800 bg-slate-950/60 p-3 space-y-1">
      <div className="flex flex-wrap items-center gap-2 text-[11px] text-slate-500">
        {citation.ref && (
          <span className="border border-slate-700 px-2 py-0.5 tracking-[0.15em]">
            {citation.ref}
          </span>
        )}
        <span className="text-seal">لم يثبت</span>
      </div>
      {citation.quoted_span && (
        <p dir="auto" className="text-xs leading-relaxed text-slate-500 line-through">
          {citation.quoted_span}
        </p>
      )}
      <p dir="auto" className="text-xs leading-relaxed text-slate-400">
        {citation.reason || "لم يذكر الخادم سبباً للرفض."}
      </p>
    </li>
  );
}

/**
 * جواب واحد — حكمه ثم نصّه ثم مصادره.
 *
 * ⚠️ **والورقة تُعطى للمسنود وحده.** هذا هو الفرق الذي وُجد هذا المكوّن لأجله:
 *    ما ثبت له سندٌ يُعرض على ورقٍ بترويسة ومتنٍ بحبر الوثيقة (اللغة البصرية
 *    نفسها التي يتعلّمها القارئ من `/library`)، وما لا سند له يُعرض على سطحٍ
 *    داكن محاطاً بحدّ الختم الأحمر ونصّ صريح. فالاثنان **لا يُخطَآن** حتى في
 *    صورة مصغَّرة أو بلون واحد.
 */
export function ChatAnswerView({ answer }: { answer: ChatAnswer }) {
  const cited = answer.hasCitations;

  /**
   * الحال الثالثة: استُرجع شيء ولم يثبت اقتباس.
   *
   * ⚠️ والفرق يُقال صراحةً، لأنّ الطرفين يُقرآن سنداً وهما ليسا سنداً: من رأى
   *    «لم يُسترجع شيء» يعرف أنّ السؤال خارج تغطية المكتبة، ومن رأى «استُغني
   *    عن الاقتباس» يعرف أنّ المكتبة تغطّيه لكنّ الجواب لم يُسند إليه.
   */
  const retrievalOnly = answer.retrieved > 0 && !cited;

  const verdict = cited ? (
    <div className="flex items-start gap-2 border border-amber-500/40 bg-slate-900 p-3">
      <EngravedIcon name="checked-shield" className="mt-0.5 size-4 text-amber-500" />
      <div className="min-w-0 space-y-1">
        <p className="text-sm font-medium text-amber-500">
          مسنود: {answer.verified.length.toLocaleString("ar-AE")} سندٌ منقول حرفياً
          من المكتبة.
        </p>
        {answer.summary && (
          <p dir="auto" className="text-xs text-slate-400">
            {answer.summary}
          </p>
        )}
      </div>
    </div>
  ) : (
    <div className="flex items-start gap-2 border border-seal bg-seal/10 p-3">
      <ShieldAlert className="mt-0.5 size-4 shrink-0 text-seal" />
      <div className="min-w-0 space-y-1">
        <p className="text-sm font-bold text-seal">
          {retrievalOnly
            ? "بلا سند: لم يثبت اقتباسٌ واحد من المكتبة."
            : "بلا سند: لم يُسترجَع شيء من المكتبة."}
        </p>
        <p className="text-sm leading-relaxed text-slate-200">
          الجواب مبنيّ على معرفة النموذج العامة وحدها، فلا يُعتمد مرجعاً ولا
          يُنقل منه إلى مستند.
        </p>
        {retrievalOnly && (
          <p className="text-xs leading-relaxed text-slate-400">
            المكتبة أُنتجت منها{" "}
            <span className="font-mono tabular-nums text-slate-300">
              {answer.retrieved.toLocaleString("ar-AE")}
            </span>{" "}
            مقطعاً لهذا السؤال، لكنّ الجواب لم يقتبس منها ما يثبت — فقد تغطّي
            السؤال ولا تقرّره.
          </p>
        )}
      </div>
    </div>
  );

  const hasCitationsBlock = cited || answer.rejected.length > 0 || retrievalOnly;

  return (
    <div className="space-y-4">
      {answer.noAnswer && (
        <div className="border border-amber-900/60 bg-amber-950/30 p-6">
          <div className="flex items-start gap-3 text-amber-300">
            <AlertTriangle className="mt-0.5 size-5 shrink-0" />
            <div className="min-w-0 space-y-2">
              <p className="font-medium">لم يُنتج الخادم جواباً — والنصّ الآتي نصّه هو.</p>
              <p dir="auto" className="text-sm leading-relaxed opacity-90">
                {answer.text || "—"}
              </p>
              <p className="text-xs opacity-80">
                هذا تعذّرٌ في الإنتاج لا جوابٌ مختصر: لا يُقرأ إجابةً ولا يُبنى عليه.
              </p>
            </div>
          </div>
        </div>
      )}

      {verdict}

      {!answer.noAnswer && (
        <article
          className={`relative border p-6 ${
            cited
              ? "border-slate-700 bg-[#F2EADA] shadow-2xl"
              : "border-slate-800 bg-slate-900"
          }`}
        >
          {cited && (
            <span
              className="absolute inset-y-5 start-4 w-px bg-seal/25"
              aria-hidden="true"
            />
          )}
          <div className={cited ? "ps-4" : ""}>
            <AnswerBody text={answer.text} onPaper={cited} />
          </div>

          {/* ما جرى على المتن من فحوص حتمية — يُعلَن ولا يُسكَت عنه: غيابه
              يُقرأ سلامة، وهو فحصٌ قد لا يكون جرى. */}
          {(answer.languageSummary || answer.attributionSummary) && (
            <div
              className={`mt-5 space-y-1 border-t pt-3 text-xs ${
                cited ? "border-[#16130F]/15 text-[#5c5344]" : "border-slate-800 text-slate-500"
              }`}
            >
              {answer.languageSummary && (
                <p dir="auto">التدقيق اللغوي: {answer.languageSummary}</p>
              )}
              {answer.attributionSummary && (
                <p dir="auto">نسبة النصوص إلى موادّها: {answer.attributionSummary}</p>
              )}
            </div>
          )}
        </article>
      )}

      {hasCitationsBlock && (
        <section className="space-y-3">
          <h3 className="flex items-center gap-2 text-[11px] tracking-[0.2em] text-slate-500">
            <QuoteGlyph className="size-3.5" aria-hidden="true" />
            ما استُند إليه في الأرشيف
          </h3>

          {cited ? (
            answer.verified.map((citation, index) => (
              <CitationCard key={`${citation.ref}-${citation.chunk_id}-${index}`} citation={citation} />
            ))
          ) : (
            <p className="border border-slate-800 bg-slate-900 p-4 text-xs leading-relaxed text-slate-400">
              {retrievalOnly
                ? "لا سند مكتوب يمكن عرضه: المقاطع التي استُرجعت لم يُنقل منها نصٌّ يثبت. اقرأ المصادر مباشرة في الأرشيف قبل الاعتماد على الجواب."
                : "لا شيء: لم تُسترجَع من المكتبة أيّة مقاطع لهذا السؤال، فلا مصدر يُعرض ولا مصدر يُقرأ."}
            </p>
          )}

          {answer.malformed > 0 && (
            <p className="text-xs text-amber-500">
              أسطر أسانيد لم يُقرأ منها{" "}
              {answer.malformed.toLocaleString("ar-AE")} — سندٌ ضائع، راجعه في المستند.
            </p>
          )}

          {answer.unbacked > 0 && (
            <p className="text-xs text-seal">
              موادّ ذُكرت في المتن ولم ترد في أيّ مقطع مسترجَع:{" "}
              {answer.unbacked.toLocaleString("ar-AE")} — أي أنّ أرقامها لا سند لها
              في المكتبة.
            </p>
          )}

          {answer.rejected.length > 0 && (
            <div className="space-y-2">
              <h4 className="text-xs font-semibold text-slate-400">
                اقتباسات لم تثبت — ولم تُحسب في الجواب
              </h4>
              <ul className="space-y-2">
                {answer.rejected.map((citation, index) => (
                  <RejectedRow key={`${citation.ref}-${index}`} citation={citation} />
                ))}
              </ul>
            </div>
          )}
        </section>
      )}
    </div>
  );
}
