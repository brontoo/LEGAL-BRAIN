"use client";

/**
 * الأرشيف والمكتبة — أداة بحث حقيقية على المستندات والمقاطع.
 * ============================================================================
 * ⚠️ ما كان هنا قبل هذا التغيير: سبعة مستندات **مكتوبة في الملف** بأسماء
 * وتواريخ (٢٠٢٦-٠٩-٢٥) وحالات (مكتمل · قيد المراجعة · مسودة).
 *
 * ⚠️ والحالات كانت الخطأ الأكبر: «مكتمل» و«قيد المراجعة» أوصاف **مستندات
 *    مصوغة**، وهذا الجدول يعرض **مصادر مستوردة** للأرشيف. والمصدر المستورد
 *    لا يكون «قيد المراجعة» — هو مفهرس أو غير مفهرس.
 *
 * ⚠️ والأزرار الثلاثة كانت **لا تفعل شيئاً**: عرضٌ وتحميلٌ وحذف. وزرّ لا يعمل
 *    أسوأ من غيابه، لأنه يوعد بقدرة غير موجودة. فحُذفت.
 *
 * ⚠️ والنقص الذي بقي بعد ذلك: الجدول كان يعرض المستند **ولا يفتحه**. فيعرف
 *    المستخدم أن «اتفاقية كذا» في الأرشيف، ولا سبيل لقراءة مقطع واحد منها
 *    إلا بفتح Supabase. وهذه الصفحة الآن تجيب السؤال الذي جاء المستخدم من
 *    أجله: **ماذا يقول المصدر في هذه المسألة؟**
 *
 *    ولذلك **وضعان** لا صفحتان: «المستندات» للعرض والتصفية، و«المقاطع»
 *    للقراءة. والصفّ في الجدول **يُضغط** فينقل إلى مقاطع ذلك المستند — فلا
 *    يبقى الانتقال بين الوضعين إجراءً يبحث عنه المستخدم في مكان آخر.
 *
 * ⚠️ ثم بقي نقصٌ ثالث، وهو أخفى الثلاثة: **المقطع ليس المستند**. من يفتح
 *    «اتفاقية كذا» يقرأ عشرين بطاقة منفصلة، كلٌّ منها بحدّها وعنوانها، وعليه
 *    أن يجمعها في ذهنه ليعرف **ما تقوله الاتفاقية**. والوثيقة القانونية
 *    تُقرأ **متّصلة** — فقرة ثم فقرة — كما تُقرأ على الورق.
 *
 *    ولهذا صار لفتح المستند **ثلاثة أوجه**: «النصّ الكامل» (وهو الافتراضي،
 *    لأن فتح المستند طلبُ قراءةٍ لا طلبُ تصفّح) · «المقاطع» للبطاقات
 *    المفردة وظلّ البحث · «المستندات» للجدول.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Search, Filter, X } from "lucide-react";
import { EngravedIcon } from "@/components/engraved-icon";
import { Letterhead, Najma } from "@/components/letterhead";
import { Card } from "@/components/ui/card";
import {
  InputGroup,
  InputGroupAddon,
  InputGroupInput,
  InputGroupText,
} from "@/components/ui/input-group";
import { DataNotice } from "@/components/data-notice";

const API_URL = "/api";

/**
 * ⚠️ ولماذا سقفٌ عالٍ (٢٠٠) لا ترقيم صفحات؟
 *
 * لأن هذا **أرشيف بحث** لا قائمة تصفُّح: المستخدم يضيّق بالبحث أو بالعائلة
 * حتى تصغر النتيجة، ولا يتنقّل بين صفحات. ومع ذلك يبقى القَصّ **مُعلَناً** في
 * سطر أسفل القائمة — فالرقم الذي يُعرض بلا إعلان القَصّ يوهم أنه الكل.
 *
 * ⚠️ ولا ثابتَ لعدد أسطر الطيّ: العدد يعيش في الصنف `line-clamp-6` وحده.
 * وثابتٌ في TS لا يغيّر الصنف، فيصيرا مصدرَي حقيقة يفترقان بصمت.
 */
const PAGE_SIZE = 200;

/** عتبةُ إظهار «عرض المزيد». الحرف العربي أضيق من اللاتيني، وهذا تقدير
 *  محافظ يكفي لأن يقرّر الزر: ٢٤٠ حرفاً لا تبلغ ستة أسطر في بطاقة بعرض
 *  الصفحة عادةً، وما زاد عليها قد يبلغها — فالزر يظهر ولا يضرّ ظهوره. */
const CLAMP_HINT_CHARS = 240;

/** مدة «نُسخ» الظاهرة بعد النسخ. قصيرة لأنها إقرار بفعل وقع، لا حالة تُراقب. */
const COPIED_MS = 2000;

type Mode = "documents" | "chunks";

/**
 * وجه العرض — **منفصل عن `mode` عن قصد**.
 *
 * ⚠️ `mode` يقرّر **أي نداء يُطلق**، وله نوعان لأن الخادم له نقطتان.
 *    أما الأوجه فثلاثة، واثنان منها («النصّ الكامل» و«المقاطع») يقرآن
 *    **الردّ نفسه**: مقاطع المستند الواحد. فلو حُشرت الثلاثة في `mode`
 *    لصار تبديل الوجه **نداءً جديداً إلى الخادم** — وهو إبطاء بلا سبب وإبطال
 *    للبيانات التي بين اليدين.
 */
type View = "documents" | "chunks" | "text";

type Family = {
  key: string;
  label: string;
  documents: number;
  chunks: number;
  latest_added: string | null;
};

type ArchiveDocument = {
  document_name: string;
  document_type: string;
  family: string;
  family_label: string;
  chunks: number;
  added_at: string | null;
};

type ArchiveChunk = {
  id: number;
  document_name: string;
  document_type: string;
  family: string;
  family_label: string;
  content: string;
  source_file: string;
  chunk_index: number | null;
  created_at: string | null;
};

/** ما يشترك فيه الردّان: العدد وسقف الطلب وعلم القَصّ. */
type Envelope = { count: number; limit: number; truncated: boolean };

/**
 * نتيجة واحدة للوضعين — فلا تتفرّع حالة التحميل والخطأ على أربع حالات.
 *
 * ⚠️ و`key` هو `mode`: معه لا يمكن أن تُعرض مستندات بينما الوضع «مقاطع»
 *    (بقايا ردّ سبق تبديل الوضع) — وهي أسوأ من التحميل، لأنها تبدو صحيحة.
 */
type Result =
  | { key: "documents"; envelope: Envelope; documents: ArchiveDocument[] }
  | { key: "chunks"; envelope: Envelope; chunks: ArchiveChunk[] };

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

/**
 * تحويل الردّ الخام إلى نتيجة مفحوصة.
 *
 * ⚠️ ولماذا الفحص بحرفيّته؟ لأن الردّ يأتي من دالّة SQL تُضاف على التوازي،
 * وقد يعود بشكل مختلف عمّا وُصف. والقراءة العمياء (`data.documents.map`)
 * تُسقط الصفحة كلها — شاشة بيضاء بدل رسالة. والفحص هنا يحوّل «شكلاً غير
 * متوقّع» إلى خطأ يُقال، ويُبقي حقولَ الصفّ ناقصةً بـ«—» بدل `undefined`.
 */
function normalizeResult(mode: Mode, raw: unknown): Result {
  const source = isRecord(raw) ? raw : {};
  const envelope: Envelope = {
    count: typeof source.count === "number" ? source.count : 0,
    limit: typeof source.limit === "number" ? source.limit : PAGE_SIZE,
    truncated: source.truncated === true,
  };

  const text = (value: unknown): string => (typeof value === "string" ? value : "");
  const rows = (value: unknown): Record<string, unknown>[] =>
    Array.isArray(value) ? value.filter(isRecord) : [];

  if (mode === "documents") {
    return {
      key: "documents",
      envelope,
      documents: rows(source.documents).map((row) => ({
        document_name: text(row.document_name),
        document_type: text(row.document_type),
        family: text(row.family),
        family_label: text(row.family_label),
        chunks: typeof row.chunks === "number" ? row.chunks : 0,
        added_at: typeof row.added_at === "string" ? row.added_at : null,
      })),
    };
  }

  return {
    key: "chunks",
    envelope,
    chunks: rows(source.chunks).map((row, index) => ({
      /* `id` هو مفتاح React. وإن غاب من ردٍّ غير متوقّع فالترتيب يكفي مؤقّتاً
         — خيرٌ من `undefined` في المفتاح، وهو ما يُفقد React التتبّع. */
      id: typeof row.id === "number" ? row.id : index,
      document_name: text(row.document_name),
      document_type: text(row.document_type),
      family: text(row.family),
      family_label: text(row.family_label),
      content: text(row.content),
      source_file: text(row.source_file),
      chunk_index: typeof row.chunk_index === "number" ? row.chunk_index : null,
      created_at: typeof row.created_at === "string" ? row.created_at : null,
    })),
  };
}

/**
 * ⚠️ `detail` من الخادم يُعرض **حرفياً**: هو الذي يقول أي قسم من `schema.sql`
 *    يجب تنفيذه، وإعادة صياغته تُفقد المستخدم الرقم الذي يحتاجه.
 *
 * وردّ الوسيط عند تعذّر الوصول إلى FastAPI **نصٌّ عربي** لا JSON — ولهذا
 * يُقرأ النصّ ويُفحص أولاً، ولا يُفترض JSON.
 */
async function readError(response: Response): Promise<string> {
  const raw = await response.text();
  try {
    const parsed: unknown = JSON.parse(raw);
    if (isRecord(parsed) && typeof parsed.detail === "string" && parsed.detail) {
      return parsed.detail;
    }
  } catch {
    /* ليس JSON — يُعرض النصّ كما هو */
  }
  return raw.trim().slice(0, 500) || `HTTP ${response.status}`;
}

/**
 * هل يذكر الخطأ قسماً من `schema.sql`؟
 *
 * ⚠️ والفحص للرقم **العربي والهندي** معاً: رسالة الخادم تقول «القسم ١١»
 *    بالأرقام الهندية (`١١`)، والبحث عن `11` وحدها لا يجدها فيبقى التلميح
 *    مخفياً عن المستخدم الذي يحتاجه بالضبط. وكان هذا خطأً قائماً في النسخة
 *    السابقة، فلا يتكرّر.
 */
function schemaSectionHint(detail: string): string | undefined {
  if (!detail.includes("schema.sql")) return undefined;
  const section = detail.match(/القسم\s+([0-9٠-٩]+)/)?.[1];
  if (!section) return undefined;
  return `-- افتح schema.sql وانسخ «القسم ${section}» كاملاً ثم نفّذه في Supabase ← SQL Editor\nselect * from archive_overview();\nselect * from archive_chunks(null, null, null, 5);`;
}

/**
 * تقسيم النصّ عند كلمة البحث لتظليلها.
 *
 * ⚠️ ولماذا التقسيم لا `dangerouslySetInnerHTML`؟ لأن محتوى المقطع **نصّ
 *    مستخدم** خرج من ملف رفعه هو. وأي إدخال في HTML يعني حقنَ سكربت من ملف
 *    مرفوع. والتقسيم يُنتج عناصر React — والوسم `<mark>` يبقى وسم React لا
 *    نصّاً مُفسَّراً، فلا حقن.
 *
 * ⚠️ والبحث لا يتراجع عن التطبيع ولا عن التشكيل: لو طبّعنا (أ/إ/آ ← ا) أو
 *    نزعنا التشكيل لَما وقع الظلّ على النصّ الأصلي. فالمطابقة حرفية غير حسّاسة
 *    لحالة الأحرف فقط — وهي كافية للعربية.
 */
function splitHighlighted(
  content: string,
  term: string
): { text: string; hit: boolean }[] {
  const parts: { text: string; hit: boolean }[] = [];
  if (!term) {
    parts.push({ text: content, hit: false });
    return parts;
  }

  const haystack = content.toLowerCase();
  const needle = term.toLowerCase();
  if (!needle) {
    parts.push({ text: content, hit: false });
    return parts;
  }

  let cursor = 0;
  while (cursor <= content.length) {
    const at = haystack.indexOf(needle, cursor);
    if (at === -1) {
      if (cursor < content.length) parts.push({ text: content.slice(cursor), hit: false });
      break;
    }
    if (at > cursor) parts.push({ text: content.slice(cursor, at), hit: false });
    parts.push({ text: content.slice(at, at + term.length), hit: true });
    cursor = at + term.length;
  }

  return parts;
}

/**
 * ⚠️ `key` هنا ترتيب الوقوع لا محتوى المقطع: قد يتكرّر النصّ نفسه في مقطعين
 *    (تداخل chunks)، فيتكرّر المفتاح وتشكو React. الترتيب فريد دائماً.
 */
function HighlightedText({ content, term }: { content: string; term: string }) {
  const parts = useMemo(() => splitHighlighted(content, term), [content, term]);
  return (
    <>
      {parts.map((part, index) =>
        part.hit ? (
          <mark
            key={index}
            className="bg-amber-500/25 text-amber-200 px-0.5"
          >
            {part.text}
          </mark>
        ) : (
          <span key={index}>{part.text}</span>
        )
      )}
    </>
  );
}

/**
 * هل كل التواريخ المعروضة متطابقة؟
 *
 * ⚠️ وهذا ليس تلمّيحاً تجميلياً بل تشخيص لحالة حقيقية: جدولان أُنشئا قبل
 * إضافة عمود `created_at`، فأخذت صفوفهما **كلها لحظة إضافة العمود**. فتاريخ
 * واحد لثلاثمئة مستند ليس مصادفة — بل أثر ترقية.
 *
 * والفحص على **اليوم** لا اللحظة الكاملة: فمستندان رُفعا في اليوم نفسه
 * بحقّ، ولا يجوز أن يُوسَما.
 */
function allDatesIdentical(documents: ArchiveDocument[]): boolean {
  if (documents.length < 3) return false;
  const days = new Set(
    documents.map((doc) => (doc.added_at ? doc.added_at.slice(0, 10) : ""))
  );
  return days.size === 1 && !days.has("");
}

/**
 * ترتيب مقاطع المستند الواحد — **فقرةً فقرة**.
 *
 * ⚠️ والقاعدة التي تحميها هذه الدالّة: **لا يُعاد ترتيب ما لا ترتيب له.**
 *
 * الخادم يُعيد مقاطع المستند مرتّبةً أصلاً (`chunk_index` تصاعدياً ثم
 * `created_at` ثم المعرّف). فإن كانت **كل** الفهارس غائبة (`null`) فالترتيب
 * القادم هو ترتيب الملفّ نفسه، وإعادة الترتيب حينها **تُفسد المستند**:
 * مقارنةُ `null` بـ`null` بلا حاكم تُبقي الترتيب في V8، لكنها **ضمانٌ
 * لتنفيذٍ لا لقاعدة** — والقاعدة أن نُبقي ما جاءنا إذا لم يكن لنا ما نُرتّب به.
 *
 * ⚠️ وإذا وُجد فهرسٌ ولو واحد، صار للترتيب معنى: تُقدَّم المفهرسة بـ
 *    `chunk_index`، وترتيب الخادم يفصل بين المتساويات (مقطعين بنفس الرقم
 *    ازدواجٌ واقعي في الأرشيف)، والغائبةُ فهرساً **أخيراً** — لأن `null` ليس
 *    صفراً: تركه في المقدّمة يُقدّم مقطعاً لا نعرف موضعه على مقطعٍ نعرفه.
 */
function orderChunks(chunks: ArchiveChunk[]): ArchiveChunk[] {
  if (!chunks.some((chunk) => chunk.chunk_index !== null)) return chunks;

  return chunks
    .map((chunk, position) => ({ chunk, position }))
    .sort((a, b) => {
      const left = a.chunk.chunk_index;
      const right = b.chunk.chunk_index;
      if (left === null && right === null) return a.position - b.position;
      if (left === null) return 1;
      if (right === null) return -1;
      if (left !== right) return left - right;
      return a.position - b.position;
    })
    .map((entry) => entry.chunk);
}

/**
 * ترويسة الورقة المطبوعة — **نسخة فاتحة من `Letterhead`**.
 *
 * ⚠️ ولماذا نسخةٌ هنا لا خاصية `tone` في `letterhead.tsx`؟
 *
 * لأن ذلك الملف **مستعمل في ثلاثة مواضع على خلفية داكنة** (الغلاف، ومساحة
 * الصياغة، والقائمة الجانبية). وإضافة بديلٍ فاتح إليه تُدخل على كل مستدعٍ
 * سؤالاً لم يكن له، وتجعل مكوّناً واحداً يعرف لون سطحين. والنسخة هنا
 * **تُتركّب من الأجزاء المُصدَّرة نفسها** (`Najma`)، فلا يتفرّع الرمز ولا
 * يُرسم مرّتين.
 *
 * ⚠️ والبنية مطابقة لبنية الأصل حرفياً (نجمة · اسم · خطّ بنجمة · القب ·
 *    السطر اللاتيني) ومقاساتها كذلك — فلو غُيّر الأصل بقي الفرق **مقروءاً**
 *    لا مكتشفاً بالعين. وألوان الحبر هنا هي وحدها المختلفة، وهذا هو المقصود.
 */
function PaperLetterhead() {
  return (
    <div className="text-center">
      <Najma className="mx-auto size-7 text-seal" />

      <p className="mt-2.5 font-heading text-3xl leading-none text-[#16130F]">
        أحمد عيد
      </p>

      {/*
        ⚠️ والخطّ بـ`bg` لا بـ`border-t` — اتباعاً للأصل في `letterhead.tsx`
        (`bg-slate-700`). فالاثنان يرسمان السطر نفسه، والاختلاف بينهما اختلاف
        سمك الحدّ بين المتصفّحات، وهو ما لا يُخاطر به في عنصر بارتفاع بكسل.
      */}
      <div className="mt-3 flex items-center gap-2" aria-hidden="true">
        <span className="h-px flex-1 bg-seal/30" />
        <Najma className="size-2.5 text-seal" />
        <span className="h-px flex-1 bg-seal/30" />
      </div>

      <p className="mt-2.5 text-[10px] tracking-[0.25em] text-seal">
        المستشار القانوني
      </p>

      <p dir="ltr" className="mt-1.5 text-[9px] tracking-[0.3em] text-seal">
        AHMED EID
      </p>
    </div>
  );
}

/** بطاقة مقطع — مكوّن مستقلّ حتى لا يختلط الطيّ ببعضه عند كل إعادة رسم. */
function ChunkCard({
  chunk,
  term,
  onOpenDocument,
}: {
  chunk: ArchiveChunk;
  term: string;
  onOpenDocument: (name: string) => void;
}) {
  const [expanded, setExpanded] = useState(false);

  /* ⚠️ إعادة ضبط الطيّ عند تغيّر النتيجة: بطاقة طُوّيت في بحث سابق كانت
     تفتح على نصّ آخر مطويّ — وهو إرباك بلا سبب. و`key` بحسب المعرّف في
     القائمة يجعل React ينشئ البطاقة من جديد، لكن الضبط هنا أصرح. */
  useEffect(() => {
    setExpanded(false);
  }, [chunk.id]);

  const long = chunk.content.length > CLAMP_HINT_CHARS;

  return (
    <Card
      size="sm"
      className="bg-slate-900 border border-slate-800 ring-0 gap-3 py-4"
    >
      <div className="px-4 flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <button
            type="button"
            onClick={() => onOpenDocument(chunk.document_name)}
            title="اعرض مقاطع هذا المستند وحده"
            className="flex items-center gap-2 text-start font-medium text-slate-200 transition-colors hover:text-amber-500"
          >
            <EngravedIcon name="papers" className="size-4 text-amber-500" />
            <span className="break-words">
              {chunk.document_name || "بلا اسم"}
            </span>
          </button>
          <p className="mt-1 flex flex-wrap items-center gap-2 text-[11px] text-slate-500">
            <span className="inline-flex items-center border border-amber-500/25 px-2 py-0.5 tracking-[0.15em] text-amber-500">
              {chunk.family_label || "—"}
            </span>
            {chunk.document_type && <span>{chunk.document_type}</span>}
            {chunk.chunk_index !== null && (
              <span className="font-mono" dir="ltr">
                #{chunk.chunk_index}
              </span>
            )}
          </p>
        </div>
      </div>

      <p
        className={`px-4 whitespace-pre-line break-words text-sm leading-relaxed text-slate-300 ${
          expanded ? "" : "line-clamp-6"
        }`}
      >
        {chunk.content ? (
          <HighlightedText content={chunk.content} term={term} />
        ) : (
          "—"
        )}
      </p>

      {long && (
        <div className="px-4">
          <button
            type="button"
            onClick={() => setExpanded((value) => !value)}
            aria-expanded={expanded}
            className="text-xs text-amber-500 transition-colors hover:text-amber-400"
          >
            {expanded ? "عرض أقل" : "عرض المزيد"}
          </button>
        </div>
      )}
    </Card>
  );
}

/**
 * زرّ وجه — نفس صنف زرّ الوضع القائم حرفياً (حدّ رفيع، والفعّال نحاسي).
 *
 * ⚠️ و`aria-pressed` أُبقي كما كان، وأُضيف `disabled` **وشرحُه**: الوجهان
 *    «النصّ الكامل» و«المقاطع» لا معنى لهما بلا مستند. وزرٌّ يبدو فعّالاً ثم
 *    لا يفعل شيئاً هو الخطأ الذي وُجد هذا الملف لتلافيه — فالمعطَّل يبقى
 *    ظاهراً (فيُعرف أنه ممكن) لكنه **يقول لماذا لا يعمل الآن**.
 */
function ViewButton({
  label,
  active,
  disabled,
  title,
  onClick,
}: {
  label: string;
  active: boolean;
  disabled?: boolean;
  title?: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      disabled={disabled}
      title={title}
      className={`font-heading border px-4 py-2 text-sm transition-colors ${
        active
          ? "border-amber-500/40 bg-slate-900 text-amber-500"
          : "border-slate-800 text-slate-400 hover:bg-slate-900"
      } disabled:cursor-not-allowed disabled:border-slate-800/60 disabled:text-slate-600 disabled:hover:bg-transparent`}
    >
      {label}
    </button>
  );
}

export default function Library() {
  const [mode, setMode] = useState<Mode>("documents");
  const [view, setView] = useState<View>("documents");
  const [search, setSearch] = useState("");
  const [family, setFamily] = useState("");
  /** تصفية مستند بعينه — تُملأ من ضغط صفّ أو من ضغط اسم مستند داخل مقطع. */
  const [documentName, setDocumentName] = useState("");
  const [families, setFamilies] = useState<Family[]>([]);

  const [result, setResult] = useState<Result | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  /** النصّ الذي جرى به البحث فعلاً — لا ما هو مكتوب الآن في الحقل. */
  const [appliedSearch, setAppliedSearch] = useState("");

  /** حالة زرّ النسخ: `""` لا شيء · `"done"` نُسخ · وإلا فهي نصّ الفشل. */
  const [copyState, setCopyState] = useState("");
  const copyTimer = useRef<number | null>(null);

  /* العائلات تُجلب مرة واحدة لبناء قائمة التصفية — فلا تُكتب في الواجهة. */
  useEffect(() => {
    let alive = true;
    fetch(`${API_URL}/archive/overview`)
      .then((response) => (response.ok ? response.json() : Promise.reject(response)))
      .then((data: { families?: Family[] }) => {
        if (!alive) return;
        setFamilies(Array.isArray(data.families) ? data.families : []);
      })
      .catch(() => {
        /* فشل القائمة لا يُسقط الجدول — التصفية تبقى بلا خيارات فقط */
      });
    return () => {
      alive = false;
    };
  }, []);

  /** إلغاء مؤقّت «نُسخ» عند مغادرة الصفحة — فلا يوقظ مكوّناً ذهب. */
  useEffect(() => {
    return () => {
      if (copyTimer.current !== null) window.clearTimeout(copyTimer.current);
    };
  }, []);

  /**
   * الجلب.
   *
   * - وضع «المستندات» ← `/archive/documents`.
   * - وضع «المقاطع» ← `/archive/chunks`، و`document` **يسبق** `search` لأن
   *   الخادم يتجاهل البحث عند وجود اسم مستند (سلوك موصوف). فنُرسل الاسم وحده
   *   بدل إرسال بحث لن يُقرأ — الطلب الأوضح أسهل في التشخيص.
   * - ويُؤجَّل ٣٥٠ مللي ثانية: البحث الآن في قاعدة البيانات، فكل حرف طلبٌ إلى
   *   الخادم، والتأجيل يمنع عشرة طلبات عند كتابة كلمة.
   * - و`AbortController`: نتيجة بحث قديم تصل بعد بحث أحدث كانت تطمس الأحدث.
   *
   * ⚠️ و`view` **ليس في التبعيات ولا في الطلب**: تبديل الوجه بين «النصّ
   *    الكامل» و«المقاطع» يقرأ الردّ نفسه، فلا نداء ثانياً ولا وميض تحميل.
   */
  const load = useCallback(
    async (signal: AbortSignal) => {
      setLoading(true);
      setError("");

      const term = search.trim();
      const params = new URLSearchParams({ limit: String(PAGE_SIZE) });
      if (family) params.set("family", family);
      if (mode === "documents") {
        if (term) params.set("search", term);
      } else if (documentName) {
        params.set("document", documentName);
      } else if (term) {
        params.set("search", term);
      }

      const endpoint =
        mode === "documents" ? "archive/documents" : "archive/chunks";

      try {
        const response = await fetch(`${API_URL}/${endpoint}?${params}`, {
          signal,
          cache: "no-store",
        });
        if (!response.ok) throw new Error(await readError(response));
        const normalized = normalizeResult(mode, await response.json());
        setResult(normalized);
        setAppliedSearch(mode === "chunks" && !documentName ? term : "");
      } catch (e) {
        if (e instanceof DOMException && e.name === "AbortError") return;
        setError(e instanceof Error ? e.message : "تعذّر قراءة الأرشيف.");
        setResult(null);
        setAppliedSearch("");
      } finally {
        if (!signal.aborted) setLoading(false);
      }
    },
    [mode, search, family, documentName]
  );

  useEffect(() => {
    const controller = new AbortController();
    const timer = setTimeout(() => void load(controller.signal), 350);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [load]);

  /**
   * فتح مستند بعينه.
   *
   * ⚠️ ولماذا يُمسح البحث هنا؟ لأن المقاطع تُعرض **بلا** ظلّ البحث في هذا
   *    الوضع (الخادم يتجاهل البحث عند وجود المستند) — فحقلٌ مكتوب فيه كلمة
   *    بلا ظلّ يوهم أن الكلمة طُبّقت. والمسح يجعل المرئي هو الحقيقة. ومن أراد
   *    البحث داخل المستند نفسه فليكتبه ثانية: سيُرسَل حينها بحثاً فعلياً.
   *
   * ⚠️ والوجه الافتراضي هو **النصّ الكامل** لا المقاطع: من ضغط صفّاً في
   *    الجدول أراد أن **يقرأ المستند**، لا أن يرى أنه مُقطَّعٌ في عشرين بطاقة.
   *    ومن أراد البطاقات فزرُّها على بعد نقرة — أما الافتراضي فيجب أن يكون
   *    الغرض، لأن أكثر المستخدمين لا يبدّلون.
   */
  const openDocument = useCallback((name: string) => {
    setDocumentName(name);
    setMode("chunks");
    setView("text");
    setSearch("");
  }, []);

  /** الوجوه الثلاثة — لا معنى لاثنين منها بلا مستند مفتوح. */
  const changeView = useCallback((next: View) => {
    if (next === "documents") {
      setMode("documents");
      setDocumentName("");
    } else {
      setMode("chunks");
    }
    setView(next);
  }, []);

  const documents = result?.key === "documents" ? result.documents : [];
  const chunks = result?.key === "chunks" ? result.chunks : [];
  const shown = result?.key === "documents" ? documents.length : chunks.length;
  const truncated = result?.envelope.truncated === true;
  const hasFilter = Boolean(search.trim() || family || documentName);
  const hint = error ? schemaSectionHint(error) : undefined;
  const busy = loading && !result;

  /** مستندٌ مفتوح، والردّ الحاضر هو ردّ مقاطعه — وإلا فالمعروض ليس مستنداً. */
  const documentOpen = Boolean(documentName) && mode === "chunks" && !error;
  const paperView = documentOpen && view === "text";

  /**
   * صفّ المستند المفتوح من الجدول — يملأ اسم العائلة وعدد المقاطع في رأس
   * الورقة. وقد **لا يوجد**: فالمفتوح ليس بالضرورة داخل أول ٢٠٠ مستند
   * (الجدول مقصوص)، أو أن الجدول مُصفّى بعائلةٍ أخرى. وحينها يُعرض «—» لا
   * رقمٌ مخترع — وهذا عين ما يمنعه `data-notice`.
   */
  const openDocumentMeta = documentName
    ? documents.find((doc) => doc.document_name === documentName)
    : undefined;

  /** مقاطع المستند بترتيب فقراته — نسخة واحدة تخدم الورقة والنسخ معاً. */
  const orderedChunks = useMemo(() => orderChunks(chunks), [chunks]);

  /** النصّ المجموع للنسخ: فقرة، سطر خالٍ، فقرة. */
  const plainText = useMemo(
    () =>
      orderedChunks
        .map((chunk) => chunk.content.trim())
        .filter(Boolean)
        .join("\n\n"),
    [orderedChunks]
  );

  /**
   * النسخ إلى الحافظة.
   *
   * ⚠️ والحافظة **قد لا تكون متاحة**: تحتاج سياقاً آمناً (`https` أو
   *    `localhost`) وإذناً من المستخدم. والفشل هنا لا يجوز أن **يرمي** —
   *    فمستخدم على `http` داخلي سيضغط الزرّ فلا يحدث شيء وتبقى الصفحة سليمة،
   *    وهو أسوأ من رسالة. ولذلك يُفحص وجود الواجهة أولاً، ويُقال الخطأ نصّاً.
   */
  const copyDocument = useCallback(() => {
    if (copyTimer.current !== null) window.clearTimeout(copyTimer.current);

    const done = (message: string) => {
      setCopyState(message);
      copyTimer.current = window.setTimeout(() => setCopyState(""), COPIED_MS);
    };

    if (typeof navigator === "undefined" || !navigator.clipboard?.writeText) {
      done("الحافظة غير متاحة في هذا المتصفّح");
      return;
    }

    navigator.clipboard
      .writeText(plainText)
      .then(() => done("done"))
      .catch((e: unknown) =>
        done(e instanceof Error ? e.message : "تعذّر النسخ")
      );
  }, [plainText]);

  /** عائلة المستند: من الجدول إن وُجد، وإلا من أوّل مقطع — فالحقل مشترك. */
  const familyLabel =
    openDocumentMeta?.family_label || chunks[0]?.family_label || "—";
  const documentType = openDocumentMeta?.document_type || chunks[0]?.document_type || "";

  /** ⚠️ رأسٌ بلا رقم مخترع: عدد المقاطع «—» إن لم يُعرف المستند في الجدول. */
  const declaredChunks = openDocumentMeta
    ? openDocumentMeta.chunks.toLocaleString("ar-AE")
    : "—";

  return (
    <div className="space-y-6">
      {/* الترويسة وشريط البحث */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div>
          <h1 className="font-heading text-3xl text-slate-100 tracking-tight">
            الأرشيف والمكتبة
          </h1>
          <p className="text-slate-400 mt-1">
            ابحث في المستندات المفهرسة، وافتح المستند لتقرأ مقاطعه كما هي في
            المصدر.
          </p>
        </div>

        <div className="flex w-full md:w-auto items-center gap-3">
          <InputGroup className="w-full md:w-80">
            <InputGroupAddon align="inline-start">
              <InputGroupText>
                <Search className="size-5" />
              </InputGroupText>
            </InputGroupAddon>
            <InputGroupInput
              type="text"
              aria-label="ابحث في الأرشيف"
              placeholder={
                documentName
                  ? "اكتب للبحث في كل المقاطع..."
                  : "ابحث باسم المستند أو بنصّ المقطع..."
              }
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
          </InputGroup>

          {/*
            القائمة `<select>` أصليّة، على النمط نفسه المستخدم في
            `app/workspace/page.tsx:636` — لا مكوّن `components/ui/select`.

            ⚠️ و`ui/select` **مبنيّ وغير مستخدَم في المشروع كله**. وتحويل
            قائمة هنا وحدها يُنشئ inconsistency، وتحويلهما معاً يحتاج بناءً
            حقيقياً للتأكّد من واجهة `@base-ui/react/select` (دلالة القيمة
            الفارغة، وشكل `onValueChange`) — ولا سبيل للبناء هنا. والقرار:
            يبقى النمط القائم حتى يُنقل الاثنان في خطوة واحدة مُتحقَّق منها.
          */}
          <div className="relative shrink-0">
            <Filter className="pointer-events-none absolute end-3 top-1/2 size-4 -translate-y-1/2 text-slate-500" />
            <select
              aria-label="تصفية بالعائلة"
              value={family}
              onChange={(event) => setFamily(event.target.value)}
              className="h-10 appearance-none border border-slate-800 bg-slate-900 pe-9 ps-3 text-sm text-slate-300 hover:bg-slate-800 focus:outline-none focus:ring-2 focus:ring-amber-500/40"
            >
              <option value="">كل العائلات</option>
              {families.map((item) => (
                <option key={item.key} value={item.key}>
                  {item.label} ({item.documents.toLocaleString("ar-AE")})
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {/* مبدّل الوجه — ثلاثة أزرار، واثنان لا معنى لهما بلا مستند مفتوح */}
      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <ViewButton
            label="المستندات"
            active={view === "documents"}
            onClick={() => changeView("documents")}
          />
          <ViewButton
            label="المقاطع"
            active={view === "chunks"}
            disabled={!documentOpen}
            title={documentOpen ? "مقاطع المستند المفتوح" : "افتح مستنداً من الجدول أولاً"}
            onClick={() => changeView("chunks")}
          />
          <ViewButton
            label="النصّ الكامل"
            active={view === "text"}
            disabled={!documentOpen}
            title={documentOpen ? "المستند كاملاً على ورقة" : "افتح مستنداً من الجدول أولاً"}
            onClick={() => changeView("text")}
          />
        </div>

        {!documentOpen && (
          <p className="text-xs text-slate-500">
            «النصّ الكامل» و«المقاطع» يُتاحان عند فتح مستند من الجدول.
          </p>
        )}
      </div>

      {/* شريحة المستند المفتوح — تبقى ظاهرة حتى تُمسح */}
      {mode === "chunks" && documentName && (
        <div className="flex items-center justify-between gap-3 border border-amber-500/25 bg-slate-900 px-4 py-2">
          <span className="min-w-0 flex items-center gap-2 text-sm text-slate-300">
            <EngravedIcon name="papers" className="size-4 text-amber-500" />
            <span className="truncate">
              المستند: <span className="text-slate-100">{documentName}</span>
            </span>
          </span>
          <button
            type="button"
            onClick={() => {
              // ⚠️ والمسح يعود إلى «المقاطع»: وجهٌ اسمه «النصّ الكامل» بلا
              // مستندٍ هو تناقض في العنوان لا في الحالة، فيُصلح معها.
              setDocumentName("");
              setView("chunks");
            }}
            aria-label="إزالة تصفية المستند"
            title="إزالة تصفية المستند"
            className="shrink-0 text-slate-500 transition-colors hover:text-amber-500"
          >
            <X className="size-4" />
          </button>
        </div>
      )}

      {error && (
        <DataNotice
          tone="error"
          title="تعذّر قراءة الأرشيف"
          detail={error}
          action={hint}
        />
      )}

      {!error && busy && <DataNotice tone="loading" title="جاري قراءة الأرشيف..." />}

      {!error && result && shown === 0 && (
        <DataNotice
          tone="empty"
          title={
            hasFilter
              ? mode === "documents"
                ? "لا مستندات تطابق بحثك."
                : "لا مقاطع تطابق بحثك."
              : mode === "documents"
                ? "الأرشيف فارغ."
                : "لا مقاطع في الأرشيف."
          }
          detail={
            hasFilter
              ? "جرّب كلمة أخرى أو أزل التصفية."
              : "ارفع مستنداتك عبر أدوات الاستيعاب (ingesters) لتظهر هنا ويستند إليها الفريق."
          }
        />
      )}

      {/* ── وجه النصّ الكامل: المستند على ورقة ── */}
      {!error && paperView && (
        <div className="space-y-4">
          {/*
            ما فوق الورقة: **على سطح المكتب الداكن لا على الورق**. فالاسم
            والعائلة والعدد بياناتُ فهرسةٍ لا متنٌ قانوني — ولو طُبعت على
            الورقة لاختلط كلام المكتب بكلام المستند، وهو الخلط الذي يمنعه
            هذا الفصل.
          */}
          <div className="flex flex-wrap items-end justify-between gap-4">
            <div className="min-w-0">
              <h2 className="font-heading text-xl break-words text-slate-100">
                {documentName || "بلا اسم"}
              </h2>
              <p className="mt-1.5 flex flex-wrap items-center gap-2 text-[11px] text-slate-500">
                <span className="inline-flex items-center border border-amber-500/25 px-2 py-0.5 tracking-[0.15em] text-amber-500">
                  {familyLabel}
                </span>
                {documentType && <span>{documentType}</span>}
                <span>·</span>
                {/* ⚠️ الرقمان معاً لا رقم واحد: «المعروض» ما بين اليدين فعلاً،
                    و«الفهرس» ما يقوله الجدول عن المستند. وإظهار المعروض وحده
                    يجعل المستند المقصوص يبدو كاملاً — وهو أسوأ ما في معاينة. */}
                <span dir="ltr" className="font-mono">
                  {shown.toLocaleString("ar-AE")} / {declaredChunks}
                </span>
                <span>مقطعاً هنا من إجمالي المستند في الفهرس</span>
              </p>
            </div>

            <div className="flex items-center gap-3">
              {copyState && (
                <span
                  role="status"
                  className={`text-xs ${
                    copyState === "done" ? "text-amber-500" : "text-red-300"
                  }`}
                >
                  {copyState === "done" ? "نُسخ" : copyState}
                </span>
              )}
              {/*
                ⚠️ والمعطَّل هنا **حماية لا زينة**: الورقة تُرسم قبل وصول
                المقاطع بلحظة، وضغطةٌ في تلك اللحظة تنسخ **نصاً فارغاً** ثم
                تقول «نُسخ» — وهذا أسوأ كذبة في الصفحة، لأنها تُقنع المستخدم
                بأن المستند في حافظته وهو ليس فيها.
              */}
              <button
                type="button"
                onClick={copyDocument}
                disabled={loading || !plainText}
                title={
                  plainText
                    ? "انسخ نصّ المستند كاملاً"
                    : "لا نصّ بعد لينسخ"
                }
                className="font-heading shrink-0 border border-slate-800 px-4 py-2 text-sm text-slate-300 transition-colors hover:border-amber-500/40 hover:text-amber-500 disabled:cursor-not-allowed disabled:border-slate-800/60 disabled:text-slate-600 disabled:hover:border-slate-800/60 disabled:hover:text-slate-600"
              >
                نسخ النصّ
              </button>
            </div>
          </div>

          {/*
            ⚠️ والقَصّ يُعلَن **قبل** الورقة لا بعدها: معاينةٌ تعرض جزءاً من
            مستند وتصمت أسوأ من ألّا تعرض شيئاً — لأنها تُقرأ كاملةً. ومن
            رأى «بقيّة المستند غير معروضة» قبل أن يبدأ القراءة لا يُبنى على
            نصٍّ ناقص، بخلاف من يقرأ ثلاثين فقرة ثم يكتشف أن هناك ثلاثين غيرها.
          */}
          {truncated && (
            <DataNotice
              tone="empty"
              title={`تُعرض أول ${shown.toLocaleString("ar-AE")} مقطعاً من هذا المستند — وبقيتها غير معروضة.`}
              detail="المعاينة مقصوصة عند سقف الطلب (٢٠٠ مقطع)، وما تراه هنا ليس المستند كاملاً."
            />
          )}

          {/*
            ⚠️ وظلٌّ واحد في الصفحة كلها — وهو **مبرَّر فيزيائياً**: الورقة
            موضوعة **على** سطحٍ داكن، ولا تقع ورقة على مكتب بلا ظلّ. وكل ظلٍّ
            آخر في الواجهة يُحذف، لأن الظلّ حيث لا سطح تحته زينةٌ لا ضوء.
          */}
          <article className="relative border border-slate-700 bg-[#F2EADA] p-10 text-[#16130F] shadow-2xl sm:p-14">
            {/*
              هامش الورقة المسطّرة — خطّ رأسي يفصل الحاشية عن المتن، كما في
              `app/page.tsx` وبلون الختم نفسه (`seal`): حدُّ ورقةٍ لا تنبيه.
              وهو داخل الورقة وخارج المتن، فلا يُحسب من عرض المتن.
            */}
            <span
              className="absolute inset-y-8 start-6 w-px bg-seal/25"
              aria-hidden="true"
            />

            <div className="ps-6">
              <PaperLetterhead />

              {orderedChunks.length > 0 ? (
                /*
                  المتن — كما في المطبوع: خطّ الوثيقة، وتباعد أسطر واسع، بلا
                  أي عنوان لا وجود له في البيانات. كل مقطع فقرةٌ قائمة بذاتها
                  **بلا سقف ولا طيّ**: هذا هو المستند، ويجب أن يُقرأ كاملاً.
                */
                <div className="mt-10">
                  {orderedChunks.map((chunk) => (
                    <p
                      key={chunk.id}
                      className="mt-5 whitespace-pre-line break-words font-heading text-[15px] leading-loose text-[#16130F]"
                    >
                      {chunk.content || "—"}
                    </p>
                  ))}
                </div>
              ) : (
                /* الورقة تُعرض فارغةً بترويسةٍ لا بلا شيء: النقص يُقال في متنها */
                <p className="mt-10 font-heading text-[15px] text-[#16130F]">
                  لا مقاطع معروضة لهذا المستند — أو لم يُفهرس بعد.
                </p>
              )}
            </div>
          </article>
        </div>
      )}

      {/* ── وضع المستندات ── */}
      {!error && mode === "documents" && documents.length > 0 && (
        <>
          <Card className="bg-slate-900 border-slate-800 overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-right border-collapse">
                <thead>
                  <tr className="bg-slate-950/50 border-b border-slate-800 text-slate-400">
                    <th className="p-4 font-medium">اسم المستند</th>
                    <th className="p-4 font-medium">التصنيف</th>
                    <th className="p-4 font-medium">العائلة</th>
                    <th className="p-4 font-medium">المقاطع</th>
                    <th className="p-4 font-medium">أُضيف في</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800">
                  {/*
                    ⚠️ والصفّ كله **زرّ فتح**: المستخدم يرى اسم مستند فيريد
                    أن يقرأه، ولا يبحث عن رابط صغير في آخر السطر. ومع ذلك
                    يبقى داخل الخلية رابطٌ نصّي (`button`) لأن جمهور هذه
                    الصفحة يستخدم لوحة المفاتيح وقارئ الشاشة، والصفّ وحده
                    (`onClick` على `<tr>`) لا يقبل التركيز ولا يُقرأ كإجراء.
                  */}
                  {documents.map((doc) => (
                    <tr
                      key={`${doc.family}-${doc.document_name}`}
                      onClick={() => openDocument(doc.document_name)}
                      className="cursor-pointer transition-colors hover:bg-slate-800/50"
                    >
                      <td className="p-4">
                        <button
                          type="button"
                          onClick={(event) => {
                            event.stopPropagation();
                            openDocument(doc.document_name);
                          }}
                          title="اعرض هذا المستند كاملاً"
                          className="flex items-center gap-3 text-start transition-colors hover:text-amber-500"
                        >
                          <EngravedIcon name="papers" className="size-4 text-amber-500" />
                          <span className="font-medium text-slate-200 break-words">
                            {doc.document_name || "بلا اسم"}
                          </span>
                        </button>
                      </td>
                      <td className="p-4 text-slate-400">{doc.document_type || "—"}</td>
                      <td className="p-4">
                        <span className="inline-flex items-center border border-amber-500/25 px-2 py-0.5 text-[10px] tracking-[0.15em] text-amber-500">
                          {doc.family_label || "—"}
                        </span>
                      </td>
                      <td className="p-4 text-slate-400 font-mono text-sm">
                        <span className="inline-flex items-center gap-1.5">
                          <EngravedIcon name="papers" className="size-3.5 text-slate-600" />
                          {doc.chunks.toLocaleString("ar-AE")}
                        </span>
                      </td>
                      <td className="p-4 text-slate-400 font-mono text-sm" dir="ltr">
                        {doc.added_at ? doc.added_at.slice(0, 10) : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>

          {/* ⚠️ القَصّ يُعلَن: بلا هذا السطر تُوهم الصفحة أن ما تراه هو الأرشيف كله */}
          <p className="text-xs text-slate-500">
            {truncated
              ? `تُعرض أول ${shown.toLocaleString("ar-AE")} مستنداً — يوجد غيرها. استخدم البحث أو التصفية.`
              : `${shown.toLocaleString("ar-AE")} مستنداً — الأرشيف كاملاً.`}
          </p>

          {/*
            ⚠️ وتنبيه على التواريخ المتطابقة.

            في أربع عائلات من خمس، التواريخ **كلها لحظة واحدة** — وقت إضافة
            العمود بـ`alter table` — لأن الجداول أُنشئت قبل إضافته. ولا سبيل
            لاستعادة التاريخ الأصلي: `metadata` لا يحمل تاريخاً (تُحقّق منه
            فعلاً، وفيه `chunk_index` و`source_file` و`document_type` فقط).

            والعمود يبقى لأن **يصير دقيقاً للمستندات المرفوعة من الآن**، ويُقال
            ذلك صراحةً بدل ترك تاريخ واحد يوهم بأن كل شيء أُضيف في يوم واحد.
          */}
          {allDatesIdentical(documents) && (
            <p className="text-xs text-amber-500/80">
              كل التواريخ متطابقة لأنها وقت إضافة عمود التاريخ نفسه، لا وقت رفع
              المستند. وتصبح دقيقة للمستندات المرفوعة من الآن فصاعداً.
            </p>
          )}
        </>
      )}

      {/* ── وجه المقاطع: بطاقات المستند الواحد، أو نتائج البحث ── */}
      {!error && mode === "chunks" && view === "chunks" && chunks.length > 0 && (
        <>
          <div className="space-y-3">
            {chunks.map((chunk) => (
              <ChunkCard
                key={chunk.id}
                chunk={chunk}
                term={appliedSearch}
                onOpenDocument={openDocument}
              />
            ))}
          </div>

          <p className="text-xs text-slate-500">
            {truncated
              ? `تُعرض أول ${shown.toLocaleString("ar-AE")} مقطعاً — يوجد غيرها. ضيّق البحث أو اختر مستنداً بعينه أو عائلة.`
              : `${shown.toLocaleString("ar-AE")} مقطعاً — كل النتائج.`}
          </p>
        </>
      )}
    </div>
  );
}
