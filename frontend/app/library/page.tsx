"use client";

/**
 * الأرشيف والمكتبة — فهرسُ ملفٍّ، لا لوحةَ قياس.
 * ============================================================================
 * ⚠️ ما تغيّر في هذه الجولة، ولماذا:
 *
 *   • **البحث صار الحقل الأبرز** بعرض الصفحة كلها تحت العنوان. كان في طرف
 *     سطرٍ مع القائمة المنسدلة، والحقلُ الذي يُبحث به دائماً لا يجوز أن يكون
 *     أضعف عنصر في الصفحة.
 *
 *   • **مستندٌ واحد يُفتح في لوحة جانبية** — كما في Drive — لا في صفحة أخرى
 *     ولا في وجهٍ يستبدل الجدول. والسبب عملي: القارئ يقارن مستنداً بآخر،
 *     والوجه الذي يُخفي الجدول يفقده موضعه في الفهرس.
 *
 *   • **آثار التنقّل (breadcrumb) ظاهرة دائماً**: الأرشيف › العائلة › المستند.
 *     وفي أرشيفٍ بعائلات متشابهة الأسماء، هذه هي الوسيلة الوحيدة لمعرفة
 *     «أين أنا» قبل «ماذا أرى».
 *
 *   • **والعائلات صارت شرائح (chips)** في سطر واحد: القائمة المنسدلة كانت
 *     تُخفي خيارات التصفية خلف نقرة، والتصفية هي ثاني أكثر فعلٍ بعد البحث.
 *
 * ⚠️ وما بقي كما هو عن قصد: مقاطع المستند تُعرض **مرتّبةً بترتيب فقراته**
 *    (`orderChunks`)، والورقة الكريمية بترويستها الفاتحة (`PaperLetterhead`)،
 *    وظلٌّ واحد عليها وحدها، وتشخيص تواريخ متطابقة، وتلميح قسم `schema.sql`.
 *    فهذه كلها صحيحة، وتغييرُها تغييرٌ لا إصلاح.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Search,
  X,
  ArrowUp,
  ArrowDown,
  List,
  LayoutGrid,
  Copy,
} from "lucide-react";
import { EngravedIcon } from "@/components/engraved-icon";
import { Najma } from "@/components/letterhead";
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
 * حتى تصغر النتيجة، ولا يتنقّل بين صفحات. ومع ذلك يبقى القَصّ **مُعلَناً** أسفل
 * القائمة — فالرقم الذي يُعرض بلا إعلان القَصّ يوهم أنه الكل.
 *
 * ⚠️ ولا ثابتَ لعدد أسطر الطيّ: العدد يعيش في الصنف `line-clamp-6` وحده.
 * وثابتٌ في TS لا يغيّر الصنف، فيصيرا مصدرَي حقيقة يفترقان بصمت.
 */
const PAGE_SIZE = 200;

/** عتبةُ إظهار «عرض المزيد». الحرف العربي أضيق من اللاتيني، وهذا تقدير
 *  محافظ يكفي لأن يقرّر الزر: ٢٤٠ حرفاً لا تبلغ ستة أسطر في بطاقة بعرض
 *  اللوحة عادةً، وما زاد عليها قد يبلغها — فالزر يظهر ولا يضرّ ظهوره. */
const CLAMP_HINT_CHARS = 240;

/** مدة «نُسخ» الظاهرة بعد النسخ. قصيرة لأنها إقرار بفعل وقع، لا حالة تُراقب. */
const COPIED_MS = 2000;

/** التأجيل نفسه الذي كان في النسخة السابقة — لا يُمسّ: ٣٥٠ مللي ثانية هي
 *  الحدّ الذي يمنع عشرة طلبات عند كتابة كلمة، ولا يُحسّ بها القارئ. */
const DEBOUNCE_MS = 350;

/**
 * ⚠️ مفتاح `localStorage` **مؤطَّر باسم الصفحة** (`library`) لا باسم عام.
 * المفتاح العام (`view`) يُتصادم مع أي صفحة أخرى تكتب تفضيلاً بالاسم نفسه،
 * فيصير تبديل ترتيب في صفحةٍ مبدّلاً لها هنا. والتفضيل يبقى بعد إغلاق التبويب
 * لأن اختيار «قائمة/شبكة» ليس حالة جلسة، بل طريقةَ عمل.
 */
const VIEW_KEY = "library.view";

type Mode = "documents" | "chunks";

/** أعمدة الترتيب الثلاثة — وهي **مصدر حقيقة واحد** لزرّ القائمة ولمعالج رأس
 *  العمود معاً. ولو صار للاثنين حالتان لافترقا: يختار المستخدم «الاسم» في
 *  القائمة، ويبقى رأس العمود يعلن «الأحدث» — وهو أسوأ من غياب المؤشّر. */
type SortKey = "recent" | "name" | "chunks";

/**
 * وجه اللوحة الجانبية — **حالةٌ ثالثة مستقلة** عن `mode` (أي نداء) وعن
 * `view` (قائمة أم شبكة).
 *
 * ⚠️ ولماذا لا تُحفظ في `localStorage` كحالة العرض؟ لأن الافتراضي «النصّ
 *    الكامل» هو الصواب في كل مرة: من فتح مستنداً أراد أن **يقرأه**، لا أن
 *    يرى أنه مُقطَّع. والوجه المفضَّل محفوظاً يجعل أول ما يراه القارئ بعد
 *    أسبوع هو آخر ما تركه — وهو غالباً تفصيلٌ عارض لا الغرض.
 */
type PanelTab = "text" | "chunks" | "meta";

const TABS: { key: PanelTab; label: string }[] = [
  { key: "text", label: "النصّ الكامل" },
  { key: "chunks", label: "المقاطع" },
  { key: "meta", label: "بيانات المستند" },
];

/**
 * تعريف الأعمدة — وفي `index` سببان:
 *   ١) الرقم يعطي العين مرساةً في صفٍّ طويل، كما في فهرس ملفٍّ مطبوع — وهو
 *      النمط نفسه في `app/page.tsx` (رقم المدخل بخطٍّ ثابت قبل العنوان).
 *   ٢) ومن لا يميّز الألوان يجد في العمود نفسه علامةً على الترتيب الفعّال،
 *      لا لوناً وحده.
 */
const COLUMNS: { key: string; label: string; index: string; sort: SortKey | null }[] = [
  { key: "name", label: "اسم المستند", index: "٠١", sort: "name" },
  { key: "type", label: "التصنيف", index: "٠٢", sort: null },
  { key: "family", label: "العائلة", index: "٠٣", sort: null },
  { key: "chunks", label: "المقاطع", index: "٠٤", sort: "chunks" },
  { key: "date", label: "أُضيف في", index: "٠٥", sort: "recent" },
];

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

/** الشكل المشترك للردّين — يُفحص مرة واحدة في `readEnvelope`. */
type RawEnvelope = { count: number; limit: number; truncated: boolean; rows: Record<string, unknown>[] };

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

/**
 * قراءة المغلّف مع صفوفه.
 *
 * ⚠️ ولماذا الفحص بحرفيّته؟ لأن الردّ يأتي من دالّة SQL تُضاف على التوازي،
 * وقد يعود بشكل مختلف عمّا وُصف. والقراءة العمياء (`data.documents.map`)
 * تُسقط الصفحة كلها — شاشة بيضاء بدل رسالة. والفحص هنا يحوّل «شكلاً غير
 * متوقّع» إلى خطأ يُقال، ويُبقي حقولَ الصفّ ناقصةً بـ«—» بدل `undefined`.
 */
function readEnvelope(raw: unknown, key: "documents" | "chunks"): RawEnvelope {
  const source = isRecord(raw) ? raw : {};
  return {
    count: typeof source.count === "number" ? source.count : 0,
    limit: typeof source.limit === "number" ? source.limit : PAGE_SIZE,
    truncated: source.truncated === true,
    rows: Array.isArray(source[key]) ? (source[key] as unknown[]).filter(isRecord) : [],
  };
}

function readText(value: unknown): string {
  return typeof value === "string" ? value : "";
}

/** ⚠️ صفوف المستند بلا افتراض: التاريخ الغائب `null` لا سلسلة فارغة، لأن
 *  الفراغ سلسلةٌ صحيحة الشكل تعني «لا تاريخ» و«تاريخ فارغ» معاً. */
function readDocuments(raw: unknown): Result {
  const envelope = readEnvelope(raw, "documents");
  return {
    key: "documents",
    envelope: {
      count: envelope.count,
      limit: envelope.limit,
      truncated: envelope.truncated,
    },
    documents: envelope.rows.map((row) => ({
      document_name: readText(row.document_name),
      document_type: readText(row.document_type),
      family: readText(row.family),
      family_label: readText(row.family_label),
      chunks: typeof row.chunks === "number" ? row.chunks : 0,
      added_at: typeof row.added_at === "string" ? row.added_at : null,
    })),
  };
}

function readChunks(raw: unknown): Result {
  const envelope = readEnvelope(raw, "chunks");
  return {
    key: "chunks",
    envelope: {
      count: envelope.count,
      limit: envelope.limit,
      truncated: envelope.truncated,
    },
    chunks: envelope.rows.map((row, index) => ({
      /* `id` فريد **داخل جدوله وحده**: `legal_drafts.id = 24` و
         `legal_contracts.id = 24` كلاهما موجود. ولهذا لا يُستعمل وحده مفتاحاً
         في React — المفتاح دائماً `family-id` (انظر `chunkKey`). */
      id: typeof row.id === "number" ? row.id : index,
      document_name: readText(row.document_name),
      document_type: readText(row.document_type),
      family: readText(row.family),
      family_label: readText(row.family_label),
      content: readText(row.content),
      source_file: readText(row.source_file),
      chunk_index: typeof row.chunk_index === "number" ? row.chunk_index : null,
      created_at: typeof row.created_at === "string" ? row.created_at : null,
    })),
  };
}

/**
 * ⚠️ **المفتاح الوحيد الصحيح للمقطع.**
 *
 * المعرّف في الأرشيف فريدٌ داخل جدوله لا في الردّ كله. وقد وقع الخطأ فعلاً:
 * مفتاحٌ بالمعرّف وحده جعل React يظنّ مقطعاً في جدولٍ هو نفسه مقطعٌ في جدول
 * آخر، فأبقى نصّ الأول في موضع الثاني — **فعُرض نصّ مستند مكان نصّ مستند**.
 * وهذا لا يُكتشف إلا بقراءة النصّ، فهو أخطر أنواع الأخطاء هنا.
 */
function chunkKey(chunk: ArchiveChunk): string {
  return `${chunk.family}-${chunk.id}`;
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

/** خطأ الإلغاء ليس فشلاً — لا يُقال للمستخدم ولا يُعرض. */
function isAbort(error: unknown): boolean {
  return error instanceof DOMException && error.name === "AbortError";
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
 * ⚠️ ترتيب الطلب يعتمد على الوضع، لا على الاختيار وحده.
 *
 * `sort=size` مقبول في `/archive/documents` وحدها؛ وفي المقاطع يُقبل
 * `recent|name` فقط. وإرسال `size` هناك يعني `400` — أي أن **اختياراً بريئاً
 * في القائمة يُفشل الطلب كله**. فالاختيار يبقى كما هو في الواجهة (فلا
 * يتبدّل تحت يد المستخدم)، ويُنزل إلى `recent` في الطلب، وتُقال الحقيقة في
 * سطر تحت شريط الأدوات بدل أن تُخفى.
 */
function sortQuery(mode: Mode, sort: { key: SortKey; dir: "asc" | "desc" }): string {
  const key = mode === "chunks" && sort.key === "chunks" ? "recent" : sort.key;
  return sort.dir === "asc" ? `${key}:asc` : key;
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
          <mark key={index} className="bg-amber-500/25 text-amber-200 px-0.5">
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
 *    السطر اللاتيني) ومقاساتها كذلك — فلو غُيِّر الأصل بقي الفرق **مقروءاً**
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

/**
 * بطاقة مقطع — مكوّن مستقلّ حتى لا يختلط الطيّ ببعضه عند كل إعادة رسم.
 *
 * ⚠️ ولا سقفَ على البطاقة نفسها: النقر عليها يفتح اللوحة على «النصّ الكامل»،
 *    وهناك يُقرأ المستند كاملاً بلا طيّ. فالبطاقة مدخلٌ لا مستند.
 */
function ChunkCard({
  chunk,
  term,
  selected,
  onOpen,
}: {
  chunk: ArchiveChunk;
  term: string;
  selected: boolean;
  onOpen: () => void;
}) {
  const [expanded, setExpanded] = useState(false);

  /* ⚠️ إعادة ضبط الطيّ عند تغيّر المقطع: بطاقة طُوّيت في بحث سابق كانت تفتح
     على نصّ آخر مطويّ — وهو إرباك بلا سبب. والمفتاح المركّب `family-id` هو
     الذي يجعل React يعرف أنه مقطع آخر لا المقطع نفسه. */
  useEffect(() => {
    setExpanded(false);
  }, [chunk.family, chunk.id]);

  const long = chunk.content.length > CLAMP_HINT_CHARS;

  return (
    <Card
      size="sm"
      className={`bg-slate-900 border ring-0 gap-3 py-4 ${
        selected ? "border-amber-500/40" : "border-slate-800"
      }`}
    >
      <div className="px-4 flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          {/* ⚠️ الضغط هنا لا يقود إلى «مقاطع هذا المستند» كما كان، بل يفتح
              اللوحة على المستند نفسه: المقاطع المفردة صارت وجهاً **داخلها**،
              فلا معنى لوجهٍ خارجي يقود إلى وجهٍ داخلي. */}
          <button
            type="button"
            onClick={onOpen}
            title="افتح المستند كاملاً في اللوحة"
            className="flex items-center gap-2 text-start font-medium text-slate-200 transition-colors hover:text-amber-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-500/40"
          >
            <EngravedIcon name="papers" className="size-4 text-amber-500" />
            <span className="break-words">{chunk.document_name || "بلا اسم"}</span>
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

        {/* ⚠️ ولا رقم لموضع البطاقة هنا: رقمُ الموضع في نتيجةٍ متغيّرة ليس
            بياناً عن المستند، وقد يُقرأ خطأً كرقم مقطع. ورقم المقطع الحقيقي
            (`#chunk_index`) معروضٌ في السطر الذي فوقه، وهو الوحيد الصادق. */}
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

/** رأسان لعمودين — الاتجاه نفسه بمسطرتين، ويُقلب في RTL آلياً. */
function SortIndicator({ dir }: { dir: "asc" | "desc" | null }) {
  const Icon = dir === "asc" ? ArrowUp : ArrowDown;
  return (
    <span className="inline-block size-3.5 shrink-0">
      {dir && <Icon className="size-3.5 text-amber-500" aria-hidden="true" />}
    </span>
  );
}

/**
 * زرّ مبدّل — نمط واحد للثلاثة (الوضع · العرض · اللوحة) حتى لا تتعلّم العين
 * ثلاث لغات في سطر واحد. و`aria-pressed` هو الإعلان، لا اللون وحده.
 */
function ToggleButton({
  label,
  active,
  title,
  onClick,
}: {
  label: string;
  active: boolean;
  title: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      title={title}
      className={`border px-3 py-2 text-xs transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-500/40 ${
        active
          ? "border-amber-500/40 text-amber-500"
          : "border-slate-800 text-slate-400 hover:border-slate-700 hover:text-slate-200"
      }`}
    >
      {label}
    </button>
  );
}

/** زرّ عرض بأيقونة وحدها — والشرح في `title` و`aria-label` معاً، لأن الأولى
 *  لا يقرأها قارئ الشاشة والثانية لا تُعرض للمبصر. */
function IconToggle({
  icon: Icon,
  label,
  active,
  onClick,
}: {
  icon: typeof List;
  label: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      aria-label={label}
      title={label}
      className={`flex size-9 items-center justify-center border transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-500/40 ${
        active
          ? "border-amber-500/40 text-amber-500"
          : "border-slate-800 text-slate-400 hover:border-slate-700 hover:text-slate-200"
      }`}
    >
      <Icon className="size-4" aria-hidden="true" />
    </button>
  );
}

/**
 * صفوف الهيكل العظمي — **ساكنة لا نابضة**.
 *
 * ⚠️ ولماذا لا `animate-pulse`؟ لأن الحركة الزخرفية ممنوعة في هذا المشروع:
 *    الفراغُ الذي يخفق يقول «انظر إليّ»، والصفّ الذي ينتظر يقول «مكانك محفوظ».
 *    والمستطيل الباهت يقول الثاني بلا ضجيج.
 */
function SkeletonRows({ rows }: { rows: number }) {
  return (
    <div className="divide-y divide-slate-800 border border-slate-800 bg-slate-900" aria-hidden="true">
      {Array.from({ length: rows }, (_, index) => (
        <div key={index} className="flex h-11 items-center gap-4 px-4">
          <span className="h-3 w-4 shrink-0 bg-slate-800" />
          <span className="h-3 flex-1 bg-slate-800/70" />
          <span className="hidden h-3 w-24 bg-slate-800/50 sm:block" />
          <span className="hidden h-3 w-16 bg-slate-800/50 md:block" />
          <span className="h-3 w-10 shrink-0 bg-slate-800/50" />
        </div>
      ))}
    </div>
  );
}

function SkeletonTiles({ tiles }: { tiles: number }) {
  return (
    <div
      className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4"
      aria-hidden="true"
    >
      {Array.from({ length: tiles }, (_, index) => (
        <div
          key={index}
          className="flex flex-col items-center gap-3 border border-slate-800 bg-slate-900 px-4 py-6"
        >
          <span className="size-9 bg-slate-800/70" />
          <span className="h-3 w-3/4 bg-slate-800/60" />
          <span className="h-2.5 w-1/2 bg-slate-800/40" />
        </div>
      ))}
    </div>
  );
}

export default function Library() {
  const [mode, setMode] = useState<Mode>("documents");
  /** ⚠️ «قائمة/شبكة» تفضيلُ عملٍ لا حالة جلسة: من رتّب مكتبه على الشبكة
   *  يريدها شبكةً في كل زيارة. ولهذا تُخزَّن، وتُقرأ بعد التركيب لا قبله. */
  const [view, setView] = useState<"list" | "grid">("list");
  const [search, setSearch] = useState("");
  const [family, setFamily] = useState("");
  /** المستند المفتوح في اللوحة — `""` يعني لا لوحة. */
  const [documentName, setDocumentName] = useState("");
  const [panelTab, setPanelTab] = useState<PanelTab>("text");
  /** الترتيب: المفتاح **والاتجاه** معاً في حالة واحدة، فلا يفترق مؤشّر الرأس
   *  عن قيمة القائمة المنسدلة. والاتجاه في الواجهة لا في الطلب وحده. */
  const [sort, setSort] = useState<{ key: SortKey; dir: "asc" | "desc" }>({
    key: "recent",
    dir: "desc",
  });
  const [families, setFamilies] = useState<Family[]>([]);

  /** نتيجة القائمة المعروضة، ونتيجة **اللوحة** منفصلة عنها: اللوحة تسأل عن
   *  مستند واحد والقائمة تسأل عن الأرشيف، وخلطهما في حالة واحدة يجعل فتح
   *  مستندٍ يمسح نتائج البحث تحت اللوحة. */
  const [result, setResult] = useState<Result | null>(null);
  const [panelResult, setPanelResult] = useState<Result | null>(null);
  const [loading, setLoading] = useState(true);
  const [panelLoading, setPanelLoading] = useState(false);
  const [error, setError] = useState("");
  const [panelError, setPanelError] = useState("");

  /** النصّ الذي جرى به البحث فعلاً — لا ما هو مكتوب الآن في الحقل. */
  const [appliedSearch, setAppliedSearch] = useState("");

  /**
   * ⚠️ عيّنة تواريخ **تبقى بعد فتح مستند**، لتشخيص التواريخ المتطابقة.
   *
   * التشخيص يحتاج قائمة المستندات كاملة، والقائمة تُستبدل بمقاطع المستند
   * عند فتحه (لأن المستند الواحد لا يحمل صفّه إن كان خارج أول ٢٠٠). فآخر
   * قائمة مستندات **بلا تصفية بحث** تُحفظ هنا، ومنها يُقرأ التشخيص. وهو
   * محفوظٌ لا معروض، فلا يوهم أحداً بأنه نتائج البحث الحالية.
   */
  const [dateSample, setDateSample] = useState<ArchiveDocument[]>([]);

  /** حالة زرّ النسخ في اللوحة: `""` لا شيء · `"done"` نُسخ · وإلا نصّ الفشل. */
  const [copyState, setCopyState] = useState("");
  const copyTimer = useRef<number | null>(null);

  /* العائلات تُجلب مرة واحدة لبناء شرائح التصفية — فلا تُكتب في الواجهة. */
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

  /**
   * ⚠️ تصفير إقرار النسخ عند تبديل المستند، وإلغاء مؤقّته.
   *
   * بلا هذا يبقى «نُسخ» معلّقاً على مستندٍ آخر بعد التبديل — وهو كذبٌ صغير
   * لكنه في المكان الوحيد الذي يثق فيه المستخدم بأن نصّاً صار في حافظته.
   * والتنظيف عند مغادرة الصفحة داخل المؤثّر نفسه فلا يُكرَّر.
   */
  useEffect(() => {
    return () => {
      if (copyTimer.current !== null) window.clearTimeout(copyTimer.current);
      setCopyState("");
    };
  }, [documentName]);

  /**
   * قراءة تفضيل العرض — **بعد التركيب**.
   *
   * ⚠️ ولو قُرئ في `useState` الأولي لنشأ اختلافٌ بين ما رسمه الخادم
   *    («قائمة») وما يرسمه المتصفّح («شبكة») — وهو خطأ الترطيب (hydration)
   *    الذي يُسقط الشجرة كلها. فالقراءة في مؤثّر، والوميض ثمنٌ أرخص بكثير.
   */
  useEffect(() => {
    try {
      const stored = window.localStorage.getItem(VIEW_KEY);
      if (stored === "grid" || stored === "list") setView(stored);
    } catch {
      /* التخزين قد يكون معطّلاً (وضع خاص/سياسة) — الافتراضي «قائمة» يكفي */
    }
  }, []);

  const changeView = useCallback((next: "list" | "grid") => {
    setView(next);
    try {
      window.localStorage.setItem(VIEW_KEY, next);
    } catch {
      /* ⚠️ الفشل في الحفظ **لا يُترجم** إلى فشل في التبديل: العرض تبدّل فعلاً
         في هذه الجلسة، وإظهار خطأ هنا يقول للمستخدم إن شيئاً لم يحدث. */
    }
  }, []);

  /**
   * جلب القائمة المعروضة (مستندات أو مقاطع).
   *
   * - `document` في وضع المقاطع يسبق `search`: الخادم يتجاهل البحث عند وجود
   *   اسم مستند، فنرسل الاسم وحده بدل بحثٍ لن يُقرأ.
   * - ويُؤجَّل ٣٥٠ مللي ثانية: البحث في قاعدة البيانات، فكل حرف طلب.
   * - و`AbortController`: نتيجة بحث قديم تصل بعد أحدث كانت تطمس الأحدث.
   *
   * ⚠️ والوجه المستهدف `mode` هنا **مشتقٌّ من المستند المفتوح** لا من حالة
   *    `mode`: فتحُ مستند يعني مقاطعه، حتى لو كان الوضع المعروض في شريط
   *    الأدوات «مستندات» (لأن زرّ «مستندات» يمسح المستند المفتوح أولاً).
   *    ولو أُخذ من الحالة لطُلب المستند من نقطة المستندات — وهي لا تعرف
   *    `document` أصلاً، فيُعرض الأرشيف كله تحت لوحة مستندٍ واحد.
   */
  useEffect(() => {
    const target: Mode = documentName ? "chunks" : mode;
    const endpoint = target === "documents" ? "archive/documents" : "archive/chunks";
    const term = search.trim();
    const controller = new AbortController();

    const timer = setTimeout(async () => {
      setLoading(true);
      setError("");

      const params = new URLSearchParams({
        limit: String(PAGE_SIZE),
        sort: sortQuery(target, sort),
      });
      if (family) params.set("family", family);
      if (target === "documents") {
        if (term) params.set("search", term);
      } else if (documentName) {
        params.set("document", documentName);
      } else if (term) {
        params.set("search", term);
      }

      try {
        const response = await fetch(`${API_URL}/${endpoint}?${params}`, {
          signal: controller.signal,
          cache: "no-store",
        });
        if (!response.ok) throw new Error(await readError(response));
        const raw = await response.json();

        if (target === "documents") {
          const next = readDocuments(raw);
          setResult(next);
          setAppliedSearch("");
          if (!term) {
            setDateSample(next.key === "documents" ? next.documents : []);
          }
        } else {
          setResult(readChunks(raw));
          setAppliedSearch(documentName ? "" : term);
        }
      } catch (e) {
        if (isAbort(e)) return;
        setError(e instanceof Error ? e.message : "تعذّر قراءة الأرشيف.");
        setResult(null);
        setAppliedSearch("");
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    }, DEBOUNCE_MS);

    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [search, family, documentName, mode, sort]);

  /**
   * جلب مقاطع المستند المفتوح — للّوحة وحدها.
   *
   * ⚠️ ولماذا نداءٌ ثانٍ لا مشاركةُ نتيجة القائمة؟ لأن القائمة في وضع
   *    «المستندات» لا تحمل مقاطع بحكم شكل ردّها، واللوحة تُفتح من الشبكة
   *    ومن القائمة على السواء. والنداء الثاني صغير (مقاطع مستند واحد) وأصدق
   *    من تمرير حالةٍ عبر وضعين.
   */
  useEffect(() => {
    if (!documentName) {
      setPanelResult(null);
      setPanelError("");
      setPanelLoading(false);
      return;
    }

    const controller = new AbortController();
    setPanelLoading(true);
    setPanelError("");

    const params = new URLSearchParams({
      limit: String(PAGE_SIZE),
      document: documentName,
      /* ⚠️ و`sort` لا يُرسل هنا: مقاطع المستند الواحد يعيدها الخادم بترتيب
         فقراته دائماً، و`orderChunks` تحترم ذلك. فإرسال ترتيب لا يُقرأ يوهم
         أنه طُبّق. */
    });

    fetch(`${API_URL}/archive/chunks?${params}`, {
      signal: controller.signal,
      cache: "no-store",
    })
      .then(async (response) => {
        if (!response.ok) throw new Error(await readError(response));
        setPanelResult(readChunks(await response.json()));
      })
      .catch((e: unknown) => {
        if (isAbort(e)) return;
        setPanelError(e instanceof Error ? e.message : "تعذّر قراءة المستند.");
        setPanelResult(null);
      })
      .finally(() => {
        if (!controller.signal.aborted) setPanelLoading(false);
      });

    return () => controller.abort();
  }, [documentName]);

  /** قفل تمرير الخلفية والاستماع لـ`Escape` — ما دامت اللوحة مفتوحة.
   *  ⚠️ والقفل لا يُخفى على المستخدم: اللوحة تغطّي الشاشة على الجوّال،
   *  فتمريرُ خلفها يوهم أن شيئاً آخر قابل للاستعمال. */
  useEffect(() => {
    if (!documentName) return;

    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setDocumentName("");
    };
    window.addEventListener("keydown", onKeyDown);

    return () => {
      document.body.style.overflow = previous;
      window.removeEventListener("keydown", onKeyDown);
    };
  }, [documentName]);

  /**
   * فتح مستند.
   *
   * ⚠️ ولماذا يُمسح البحث هنا؟ لأن اللوحة تُعرض **بلا** ظلّ بحث: الخادم يتجاهل
   *    البحث عند وجود اسم مستند. فحقلٌ مكتوب فيه كلمة بلا ظلّ يوهم أن الكلمة
   *    طُبّقت. والمسح يجعل المرئي هو الحقيقة — ومن أراد البحث داخل المستند
   *    نفسه فليكتبه ثانية.
   */
  const openDocument = useCallback((name: string) => {
    setDocumentName(name);
    setSearch("");
    setAppliedSearch("");
    setPanelTab("text");
  }, []);

  /** إغلاق اللوحة — والنتيجة تبقى مكانها، فالإغلاق ليس تصفيراً للبحث. */
  const closePanel = useCallback(() => setDocumentName(""), []);

  /** رمي تصفية المستند وحدها — زرُّ الرقاقة في آثار التنقّل. */
  const clearDocumentScope = useCallback(() => {
    setDocumentName("");
    setPanelResult(null);
    setPanelError("");
  }, []);

  /** العودة إلى جذر الأرشيف: رمي العائلة **والمستند** معاً، والبحث يُبقى
   *  لأن المستخدم لم يطلبه — إسقاطُه معه مفاجأة لا مساعدة. */
  const clearToArchive = useCallback(() => {
    setFamily("");
    clearDocumentScope();
  }, [clearDocumentScope]);

  /** إزالة كل ما ضيّق النتيجة — وهو ما تعرضه حالةُ «لا نتائج». */
  const clearAllFilters = useCallback(() => {
    setSearch("");
    setFamily("");
    clearDocumentScope();
    setMode("documents");
  }, [clearDocumentScope]);

  const documents = result?.key === "documents" ? result.documents : [];
  const chunks = result?.key === "chunks" ? result.chunks : [];
  const shown = result?.key === "documents" ? documents.length : chunks.length;
  const truncated = result?.envelope.truncated === true;
  const hasFilter = Boolean(search.trim() || family || documentName);
  const hint = error ? schemaSectionHint(error) : undefined;
  const panelHint = panelError ? schemaSectionHint(panelError) : undefined;

  /** ⚠️ أدوات الترتيب تظهر في وضع «المقاطع» العام فقط: عندما يكون مستندٌ
   *  مفتوحاً فالمقاطع مرتّبةٌ بترتيب فقراتها بحكم الخادم، وترتيبٌ في الواجهة
   *  لا يغيّر شيئاً. وإظهاره هناك وعدٌ لا يُوفى. */
  const showSort = !documentName;
  /** ⚠️ والحقيقة هنا عن **الطلب** لا عن `mode`: فتحُ مستند يذهب إلى نقطة
   *  المقاطع وإن كان `mode` «مستندات» — والخادم لا يعرف `size` هناك. */
  const listMode: Mode = documentName ? "chunks" : mode;
  const sortDegraded = listMode === "chunks" && sort.key === "chunks";

  /**
   * صفّ المستند المفتوح من القائمة — يملأ اسم العائلة والتصنيف وعدد المقاطع
   * في رأس اللوحة وتبويب البيانات. وقد **لا يوجد**: فالمفتوح قد لا يكون داخل
   * أول ٢٠٠ مستند، أو أن القائمة مُصفّاة بعائلة أخرى. وحينها «—» لا رقمٌ
   * مخترع — وهذا عين ما يمنعه `data-notice`.
   */
  const openDocumentMeta = documentName
    ? documents.find((doc) => doc.document_name === documentName)
    : undefined;

  /** مقاطع اللوحة بترتيب فقراتها — نسخة واحدة تخدم الورقة والمقاطع والنسخ. */
  const panelChunks = panelResult?.key === "chunks" ? panelResult.chunks : [];
  const orderedChunks = useMemo(() => orderChunks(panelChunks), [panelChunks]);

  /** النصّ المجموع للنسخ: فقرة، سطر خالٍ، فقرة. */
  const plainText = useMemo(
    () =>
      orderedChunks
        .map((chunk) => chunk.content.trim())
        .filter(Boolean)
        .join("\n\n"),
    [orderedChunks]
  );

  const panelFamilyLabel =
    openDocumentMeta?.family_label || orderedChunks[0]?.family_label || "—";
  const panelDocumentType =
    openDocumentMeta?.document_type || orderedChunks[0]?.document_type || "";
  const panelSourceFile = useMemo(
    () => orderedChunks.find((chunk) => chunk.source_file)?.source_file || "",
    [orderedChunks]
  );
  /** ⚠️ «—» بلا رقم مخترع: عدد المقاطع معروفٌ من الفهرس أو لا يُقال. */
  const panelDeclaredChunks = openDocumentMeta
    ? openDocumentMeta.chunks.toLocaleString("ar-AE")
    : "—";

  /* ⚠️ التشخيص من العيّنة لا من القائمة المعروضة: فتح مستند يُفرغ القائمة من
     صفوف المستندات، والتشخيص يجب أن يبقى صادقاً بعد الفتح. والعيّنة بلا
     تصفية بحث فقط — فالعائلة لا تخلط عائلات، والبحث يعرض مجموعةً مختارة
     تواريخُها تتطابق لأنها مختارة، لا لأن العمود أُضيف في لحظة واحدة.
     ⚠️ ولا يُعرض التنبيه حين يكون البحث فعّالاً: الصفوف المعروضة حينها مجموعةٌ
     منتقاة، والحكم على تواريخها بالتشابه حكمٌ على الانتقاء لا على الأرشيف. */
  const identicalDates = !search.trim() && allDatesIdentical(dateSample);

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

    if (!plainText) {
      done("لا نصّ بعد لينسخ");
      return;
    }

    if (typeof navigator === "undefined" || !navigator.clipboard?.writeText) {
      done("الحافظة غير متاحة في هذا المتصفّح");
      return;
    }

    navigator.clipboard
      .writeText(plainText)
      .then(() => done("done"))
      .catch((e: unknown) => done(e instanceof Error ? e.message : "تعذّر النسخ"));
  }, [plainText]);

  /**
   * المعالج الواحد لرؤوس الأعمدة.
   *
   * ⚠️ والنقر على العمود الفعّال **يقلب الاتجاه فقط**، والنقر على غيره يبدأ
   *    بـ`asc` — إلا التاريخ فيبدأ بالأنزل: من رتّب بالتاريخ يريد الأحدث
   *    أولاً في تسعة أعشار المرات، وإرغامه على نقرة ثانية عبث. والقاعدة
   *    صريحة لا مُستنتجة من نصّ العمود.
   */
  const onSortColumn = useCallback((key: SortKey) => {
    setSort((current) =>
      current.key === key
        ? { key, dir: current.dir === "asc" ? "desc" : "asc" }
        : { key, dir: key === "recent" ? "desc" : "asc" }
    );
  }, []);

  /** اتجاه المؤشّر لعمودٍ ما — `null` يعني غير مرتَّب به. */
  const sortDirFor = (key: SortKey | null): "asc" | "desc" | null =>
    key !== null && sort.key === key ? sort.dir : null;

  const skeleton = loading && !error;

  /** آثار التنقّل — تُبنى من التصفية الفعلية، فلا تظهر خطوةٌ بلا مدلول. */
  const crumbs: { label: string; action: (() => void) | null }[] = [
    { label: "الأرشيف", action: family || documentName ? clearToArchive : null },
  ];
  if (family) {
    const label = families.find((item) => item.key === family)?.label || "عائلة مقيَّدة";
    crumbs.push({ label, action: documentName ? clearDocumentScope : null });
  }
  if (documentName) crumbs.push({ label: documentName, action: null });

  return (
    <div className="space-y-6">
      {/* ── ١ · الترويسة والبحث ─────────────────────────────────────────── */}
      <header>
        <h1 className="font-heading text-3xl tracking-tight text-slate-100">
          الأرشيف والمكتبة
        </h1>
        <p className="mt-1 text-sm leading-relaxed text-slate-400">
          فهرس المستندات المفهرسة لكل عائلة: ابحث بالاسم أو بنصّ المقطع، ثم
          افتح المستند لتقرأه كاملاً كما هو في المصدر.
        </p>

        <p className="mt-6 text-[11px] tracking-[0.2em] text-slate-500">
          البحث في الأرشيف
        </p>
        {/* ⚠️ الحقل **بعرض الصفحة** لا في طرف سطر: هذا أوّل فعلٍ في الصفحة
            وآخره معاً، وحقلٌ يشارك سطراً مع أدوات أخرى يُقرأ أداةً ثانوية. */}
        <InputGroup className="mt-2 h-12 w-full">
          <InputGroupAddon align="inline-start">
            <InputGroupText>
              <Search className="size-5" />
            </InputGroupText>
          </InputGroupAddon>
          <InputGroupInput
            type="text"
            aria-label="ابحث في الأرشيف"
            placeholder="ابحث باسم المستند أو بنصّ داخل المقاطع..."
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
        </InputGroup>
      </header>

      {/* ── ٢ · آثار التنقّل — تبقى ظاهرة حتى في الجذر ──────────────────── */}
      <nav aria-label="مسار التصفية" className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
        {crumbs.map((crumb, index) => (
          <span key={`${crumb.label}-${index}`} className="flex min-w-0 items-center gap-2">
            {index > 0 && (
              <span aria-hidden="true" className="text-slate-700">
                ‹
              </span>
            )}
            {crumb.action ? (
              <button
                type="button"
                onClick={crumb.action}
                title="أزل هذا المستوى من التصفية"
                className="max-w-[22rem] truncate text-start text-slate-400 underline-offset-4 transition-colors hover:text-amber-500 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-500/40"
              >
                {crumb.label}
              </button>
            ) : (
              <span
                aria-current="page"
                title={crumb.label}
                className="max-w-[22rem] truncate text-slate-200"
              >
                {crumb.label}
              </span>
            )}
          </span>
        ))}
      </nav>

      {/* ── ٣ · شريط الأدوات — صفٌّ واحد: الشرائح يميناً والأدوات يساراً ── */}
      <div className="space-y-3 border-y border-slate-800 py-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          {/* العائلات — شرائح لا قائمة منسدلة: التصفية ثاني أكثر فعل، ولا
              يجوز أن تُخبَّأ خلف نقرة. وتلتفّ على الشاشات الضيّقة. */}
          <div className="flex min-w-0 flex-wrap items-center gap-2">
            <span className="text-[10px] tracking-[0.2em] text-slate-600">
              <span className="me-2 font-mono tabular-nums text-slate-700">٠١</span>
              العائلات
            </span>
            <button
              type="button"
              onClick={() => setFamily("")}
              aria-pressed={family === ""}
              className={`border px-3 py-1.5 text-xs transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-500/40 ${
                family === ""
                  ? "border-amber-500/40 text-amber-500"
                  : "border-slate-800 text-slate-400 hover:border-slate-700 hover:text-slate-200"
              }`}
            >
              كل العائلات
            </button>
            {families.map((item) => {
              const active = family === item.key;
              return (
                <button
                  key={item.key}
                  type="button"
                  onClick={() => setFamily(item.key)}
                  aria-pressed={active}
                  title={`${item.label} — ${item.documents.toLocaleString("ar-AE")} مستنداً`}
                  className={`border px-3 py-1.5 text-xs transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-500/40 ${
                    active
                      ? "border-amber-500/40 text-amber-500"
                      : "border-slate-800 text-slate-400 hover:border-slate-700 hover:text-slate-200"
                  }`}
                >
                  {item.label}
                  <span className="ms-2 font-mono text-[10px] text-slate-600">
                    {item.documents.toLocaleString("ar-AE")}
                  </span>
                </button>
              );
            })}
          </div>

          <div className="flex flex-wrap items-center gap-3">
            {showSort && (
              <div className="flex items-center gap-2">
                <label
                  htmlFor="archive-sort"
                  className="text-[11px] tracking-[0.15em] text-slate-500"
                >
                  ترتيب:
                </label>
                {/*
                  قائمة أصلية، على النمط المستخدم في `app/workspace/page.tsx:636`
                  — لا مكوّن `components/ui/select`: ذاك **مبنيّ وغير مستعمل في
                  المشروع كله**، وتحويل قائمةٍ هنا وحدها يُنشئ نمطين، وتحويل
                  الاثنين معاً يحتاج بناءً للتحقّق من واجهة `@base-ui/react/select`
                  — ولا سبيل للبناء هنا. فيبقى النمط القائم حتى يُنقل الاثنان
                  في خطوة واحدة مُتحقَّق منها.
                */}
                <select
                  id="archive-sort"
                  value={sort.key}
                  onChange={(event) => {
                    const next = event.target.value as SortKey;
                    setSort((current) => ({
                      key: next,
                      dir: next === "recent" ? "desc" : "asc",
                    }));
                  }}
                  className="h-9 appearance-none border border-slate-800 bg-slate-900 px-3 text-xs text-slate-300 transition-colors hover:bg-slate-800 focus:outline-none focus:ring-2 focus:ring-amber-500/40"
                >
                  <option value="recent">الأحدث</option>
                  <option value="name">الاسم</option>
                  <option value="chunks">الأكثر مقاطع</option>
                </select>
              </div>
            )}

            {/* ما يبحث فيه الأرشيف: مستنداتٌ مفهرسة، أو مقاطعُ النصّ نفسها */}
            <div className="flex items-center gap-2">
              <ToggleButton
                label="المستندات"
                active={mode === "documents" && !documentName}
                title="ابحث في أسماء المستندات"
                onClick={() => {
                  clearDocumentScope();
                  setMode("documents");
                }}
              />
              <ToggleButton
                label="المقاطع"
                active={mode === "chunks" && !documentName}
                title="ابحث داخل نصوص المقاطع"
                onClick={() => {
                  clearDocumentScope();
                  setMode("chunks");
                }}
              />
            </div>

            {/*
              ⚠️ وفي وضع المقاطع يبدّل الزرّان **ترتيب البطاقات** لا شكلها:
              عمودٌ واحد يُقرأ، أو عمودان تُمسح بهما العين. والمقاطع لا تصير
              جدولاً — الجدولُ لسطور المستندات لا لِفقرات النصّ.
            */}
            <div className="flex items-center gap-1">
              <IconToggle
                icon={List}
                label="عرض قائمة"
                active={view === "list"}
                onClick={() => changeView("list")}
              />
              <IconToggle
                icon={LayoutGrid}
                label="عرض شبكة"
                active={view === "grid"}
                onClick={() => changeView("grid")}
              />
            </div>
          </div>
        </div>

        {/* ⚠️ الحقيقة عن الترتيب المطلوب: `size` غير مدعوم في نقطة المقاطع،
            والاختيار يبقى معروضاً كما اختاره المستخدم. فالسطر يقول ما جرى
            بدل أن يُبدَّل الاختيار تحت يده بلا سبب. */}
        {sortDegraded && !error && (
          <p className="text-[11px] text-slate-500">
            «الأكثر مقاطع» ترتيبٌ للمستندات؛ وفي المقاطع تُعرض النتائج بالأحدث.
          </p>
        )}
      </div>

      {error && (
        <DataNotice
          tone="error"
          title="تعذّر قراءة الأرشيف"
          detail={error}
          action={hint}
        />
      )}

      {!error && skeleton && (
        <div className="space-y-3">
          <p role="status" className="text-[11px] tracking-[0.2em] text-slate-500">
            جاري قراءة الأرشيف...
          </p>
          {/* ⚠️ الهيكل يشبه ما سيأتي: مستنداتٌ في جدول أو بلاطات، ومقاطعٌ في
              بطاقات. وهيكلٌ لا يشبه نتيجته يجعل الظهور قفزةً لا استقراراً. */}
          {listMode === "chunks" ? (
            <div
              className={
                view === "grid" ? "grid grid-cols-1 gap-3 lg:grid-cols-2" : "space-y-3"
              }
            >
              <SkeletonRows rows={5} />
              <SkeletonRows rows={5} />
            </div>
          ) : view === "list" ? (
            <SkeletonRows rows={7} />
          ) : (
            <SkeletonTiles tiles={8} />
          )}
        </div>
      )}

      {/* ── ٧ · الفراغ: «الأرشيف فارغ» ليست «لا نتائج لبحثك» ─────────────── */}
      {!error && !loading && result && shown === 0 && (
        <div className="space-y-3">
          <DataNotice
            tone="empty"
            title={
              hasFilter
                ? "لا شيء يطابق ما ضيّقت به."
                : mode === "chunks"
                  ? "لا مقاطع في الأرشيف."
                  : "الأرشيف فارغ."
            }
            detail={
              hasFilter
                ? "جرّب كلمة أخرى، أو أزل التصفية لتعود إلى الأرشيف كله."
                : "ارفع مستنداتك عبر أدوات الاستيعاب (ingesters) لتظهر هنا ويستند إليها الفريق."
            }
          />
          {hasFilter && (
            <button
              type="button"
              onClick={clearAllFilters}
              className="border border-slate-800 px-4 py-2 text-xs text-slate-300 transition-colors hover:border-amber-500/40 hover:text-amber-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-500/40"
            >
              {search.trim()
                ? `امسح البحث${family || documentName ? " والتصفية" : ""}`
                : "امسح التصفية"}
            </button>
          )}
        </div>
      )}

      {/* ── ٤ · القائمة: مستندات أو مقاطع ───────────────────────────────── */}
      {!error && !skeleton && result && shown > 0 && (
        <section className="space-y-4">
          {result.key === "documents" &&
            (view === "list" ? (
              <DocumentTable
                documents={documents}
                sort={sort}
                sortDirFor={sortDirFor}
                onSortColumn={onSortColumn}
                selectedName={documentName}
                onOpen={openDocument}
              />
            ) : (
              <DocumentGrid
                documents={documents}
                selectedName={documentName}
                onOpen={openDocument}
              />
            ))}

          {result.key === "chunks" && (
            /* ⚠️ والشبكة هنا **عمودان لا أربعة**: بطاقة المقطع نصٌّ يُقرأ لا
               بلاطة تُمسح، وعمودٌ ضيّق يجعل `line-clamp-6` يقصّ ما لا يقصّه
               في العرض العريض — فيتبدّل المعنى بتبدّل العرض. */
            <div
              className={
                view === "grid" ? "grid grid-cols-1 gap-3 lg:grid-cols-2" : "space-y-3"
              }
            >
              {chunks.map((chunk) => (
                <ChunkCard
                  key={chunkKey(chunk)}
                  chunk={chunk}
                  term={appliedSearch}
                  selected={documentName === chunk.document_name}
                  onOpen={() => openDocument(chunk.document_name)}
                />
              ))}
            </div>
          )}

          {/* ⚠️ القَصّ يُعلَن: بلا هذا السطر تُوهم الصفحة أن ما تراه هو الأرشيف
              كله. ولا يُذكر «من N» هنا: `count` في الردّ **عددُ الصفوف المُعادة**
              عند السقف لا الإجمالي، فذكرُه كإجمالي رقمٌ مُخترع — وهو أسوأ من
              الصمت. فيُقال المعروض، وأنّ غيره موجود. */}
          <p className="text-xs text-slate-500">
            {result.key === "documents"
              ? truncated
                ? `تُعرض أول ${shown.toLocaleString("ar-AE")} مستنداً — ويوجد غيرها. استخدم البحث أو التصفية.`
                : `${shown.toLocaleString("ar-AE")} مستنداً — الأرشيف كاملاً.`
              : truncated
                ? `تُعرض أول ${shown.toLocaleString("ar-AE")} مقطعاً — ويوجد غيرها. ضيّق البحث أو اختر عائلة.`
                : `${shown.toLocaleString("ar-AE")} مقطعاً — كل النتائج.`}
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
          {identicalDates && (
            <p className="text-xs text-amber-500/80">
              كل التواريخ متطابقة لأنها وقت إضافة عمود التاريخ نفسه، لا وقت رفع
              المستند. وتصبح دقيقة للمستندات المرفوعة من الآن فصاعداً.
            </p>
          )}
        </section>
      )}

      {/* ── ٥ · لوحة المستند ────────────────────────────────────────────── */}
      {documentName && (
        <>
          {/* ⚠️ الحجاب بلا ضبابٍ ولا حركة: وظيفته أن يقول «ما تحته ليس الآن»,
              وأن يُرجع النقر إلى الإغلاق. */}
          <div
            className="fixed inset-0 z-40 bg-slate-950/70"
            onClick={closePanel}
            aria-hidden="true"
          />

          <aside
            role="dialog"
            aria-modal="true"
            aria-label={`المستند: ${documentName}`}
            className="fixed inset-y-0 end-0 z-50 flex w-full max-w-[520px] flex-col border-s border-slate-800 bg-slate-950"
          >
            <header className="shrink-0 border-b border-slate-800 px-5 py-4">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="font-mono text-[10px] tracking-[0.2em] text-slate-600">
                    المستند
                  </p>
                  <h2
                    title={documentName}
                    className="mt-1 truncate font-heading text-lg text-slate-100"
                  >
                    {documentName || "بلا اسم"}
                  </h2>
                  <p className="mt-1 flex flex-wrap items-center gap-2 text-[11px] text-slate-500">
                    <span className="inline-flex items-center border border-amber-500/25 px-2 py-0.5 tracking-[0.15em] text-amber-500">
                      {panelFamilyLabel}
                    </span>
                    {panelDocumentType && <span>{panelDocumentType}</span>}
                  </p>
                </div>

                <button
                  type="button"
                  onClick={closePanel}
                  aria-label="أغلق اللوحة"
                  title="أغلق (Escape)"
                  className="shrink-0 border border-slate-800 p-1.5 text-slate-400 transition-colors hover:border-slate-700 hover:text-amber-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-500/40"
                >
                  <X className="size-4" />
                </button>
              </div>

              <button
                type="button"
                onClick={copyDocument}
                disabled={panelLoading || !plainText}
                title={plainText ? "انسخ نصّ المستند كاملاً" : "لا نصّ بعد لينسخ"}
                className="mt-3 flex items-center gap-2 border border-slate-800 px-3 py-2 text-xs text-slate-300 transition-colors hover:border-amber-500/40 hover:text-amber-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-500/40 disabled:cursor-not-allowed disabled:border-slate-800/60 disabled:text-slate-600 disabled:hover:border-slate-800/60 disabled:hover:text-slate-600"
              >
                <Copy className="size-3.5" aria-hidden="true" />
                نسخ النصّ
                {/* ⚠️ والمعطَّل **حماية لا زينة**: الورقة تُرسم قبل وصول
                    المقاطع بلحظة، وضغطةٌ في تلك اللحظة تنسخ **نصاً فارغاً** ثم
                    تقول «نُسخ» — وهذا أسوأ كذبة في الصفحة، لأنها تُقنع
                    المستخدم بأن المستند في حافظته وهو ليس فيها. */}
                {copyState && (
                  <span
                    role="status"
                    className={
                      copyState === "done" ? "text-amber-500" : "text-red-300"
                    }
                  >
                    {copyState === "done" ? "نُسخ" : copyState}
                  </span>
                )}
              </button>
            </header>

            {/* التبويبات — ثلاثة وجوه لمستند واحد، ولا نداء جديد عند تبديلها */}
            <div
              role="tablist"
              aria-label="أوجه المستند"
              className="flex shrink-0 border-b border-slate-800"
            >
              {TABS.map((tab) => (
                <button
                  key={tab.key}
                  type="button"
                  role="tab"
                  aria-selected={panelTab === tab.key}
                  onClick={() => setPanelTab(tab.key)}
                  className={`border-b-2 px-4 py-2.5 text-xs transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-500/40 ${
                    panelTab === tab.key
                      ? "border-amber-500 text-amber-500"
                      : "border-transparent text-slate-400 hover:text-slate-200"
                  }`}
                >
                  {tab.label}
                </button>
              ))}
            </div>

            <div className="min-h-0 flex-1 overflow-y-auto px-5 py-5">
              {panelError && (
                <div className="space-y-4">
                  <DataNotice
                    tone="error"
                    title="تعذّر قراءة المستند"
                    detail={panelError}
                    action={panelHint}
                  />
                  <button
                    type="button"
                    onClick={clearDocumentScope}
                    className="border border-slate-800 px-4 py-2 text-xs text-slate-300 transition-colors hover:border-amber-500/40 hover:text-amber-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-500/40"
                  >
                    أزل تصفية المستند
                  </button>
                </div>
              )}

              {!panelError && panelLoading && (
                <div className="space-y-3">
                  <p role="status" className="text-[11px] tracking-[0.2em] text-slate-500">
                    جاري قراءة المستند...
                  </p>
                  <SkeletonTiles tiles={3} />
                </div>
              )}

              {/* ── النصّ الكامل: الورقة ── */}
              {!panelError && !panelLoading && panelTab === "text" && (
                <div className="space-y-4">
                  {/*
                    ⚠️ والقَصّ يُعلَن **قبل** الورقة لا بعدها: معاينةٌ تعرض
                    جزءاً من مستند وتصمت أسوأ من ألّا تعرض شيئاً — لأنها تُقرأ
                    كاملةً.
                  */}
                  {panelResult?.key === "chunks" && panelResult.envelope.truncated && (
                    <DataNotice
                      tone="empty"
                      title={`تُعرض أول ${orderedChunks.length.toLocaleString("ar-AE")} مقطعاً من هذا المستند — وبقيتها غير معروضة.`}
                      detail="المعاينة مقصوصة عند سقف الطلب (٢٠٠ مقطع)، وما تراه هنا ليس المستند كاملاً."
                    />
                  )}

                  {/*
                    ⚠️ وظلٌّ واحد في الصفحة كلها — وهو **مبرَّر فيزيائياً**:
                    الورقة موضوعة **على** سطحٍ داكن، ولا تقع ورقة على مكتب
                    بلا ظلّ. والظلّ حيث لا سطح تحته زينةٌ لا ضوء. ولا ظلّ على
                    اللوحة نفسها: هي حدٌّ لا ورقة.
                  */}
                  <article className="relative border border-slate-700 bg-[#F2EADA] p-8 text-[#16130F] shadow-2xl">
                    <span
                      className="absolute inset-y-6 start-5 w-px bg-seal/25"
                      aria-hidden="true"
                    />

                    <div className="ps-5">
                      <PaperLetterhead />

                      {orderedChunks.length > 0 ? (
                        /*
                          المتن — كما في المطبوع: خطّ الوثيقة، وتباعد أسطر
                          واسع، بلا أي عنوان لا وجود له في البيانات. كل مقطع
                          فقرةٌ قائمة بذاتها **بلا سقف ولا طيّ**.
                        */
                        <div className="mt-10">
                          {orderedChunks.map((chunk) => (
                            <p
                              key={chunkKey(chunk)}
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

              {/* ── المقاطع: البطاقات وظلّ البحث ── */}
              {!panelError && !panelLoading && panelTab === "chunks" && (
                <div className="space-y-3">
                  {orderedChunks.length > 0 ? (
                    orderedChunks.map((chunk) => (
                      <ChunkCard
                        key={chunkKey(chunk)}
                        chunk={chunk}
                        /* ⚠️ بلا ظلّ بحث هنا: المستند يُفتح بلا كلمة بحث
                           (والخادم يتجاهلها عند وجود اسم المستند)، فتمرير
                           كلمةٍ للظلّ يوهم أنها طُبّقت داخل المستند. */
                        term=""
                        selected={false}
                        onOpen={() => setPanelTab("text")}
                      />
                    ))
                  ) : (
                    <DataNotice
                      tone="empty"
                      title="لا مقاطع لهذا المستند."
                      detail="إمّا أنه لم يُفهرس بعد، أو أن استيعابه لم يُنتج مقاطع."
                    />
                  )}
                </div>
              )}

              {/* ── بيانات المستند: قائمة تعريف ── */}
              {!panelError && !panelLoading && panelTab === "meta" && (
                <dl className="divide-y divide-slate-800 border-y border-slate-800 text-sm">
                  <MetaRow label="اسم المستند" value={documentName} mono={false} />
                  <MetaRow label="التصنيف" value={panelDocumentType} mono={false} />
                  <MetaRow label="العائلة" value={panelFamilyLabel} mono={false} />
                  <MetaRow
                    label="عدد المقاطع"
                    value={panelDeclaredChunks}
                    mono
                  />
                  <MetaRow
                    label="أُضيف في"
                    value={
                      openDocumentMeta?.added_at
                        ? openDocumentMeta.added_at.slice(0, 10)
                        : ""
                    }
                    mono
                  />
                  <MetaRow
                    label="ملفّ المصدر"
                    value={panelSourceFile}
                    mono
                    ltr
                  />
                </dl>
              )}
            </div>
          </aside>
        </>
      )}
    </div>
  );
}

/**
 * جدول المستندات — «قائمة Drive».
 *
 * ⚠️ والصفّ كله **منطقة نقر** لأن المستخدم يرى اسماً فيريد فتحه، ولا يبحث عن
 *    رابط صغير في آخر السطر. والتركيز ولوحة المفاتيح على **زرّ داخل خلية
 *    الاسم** لا على `<tr>`: الصفّ في HTML ليس إجراءً، ولا يقبل التركيز ولا
 *    يُقرأ كذلك لقارئ الشاشة. والزرّ مرسوم **فوق الخليّة** (`after:inset-0`)
 *    فيبقى تركيزه صحيحاً ويصير الصفّ كله هدفاً بلا `<tr onClick>`.
 */
function DocumentTable({
  documents,
  sort,
  sortDirFor,
  onSortColumn,
  selectedName,
  onOpen,
}: {
  documents: ArchiveDocument[];
  sort: { key: SortKey; dir: "asc" | "desc" };
  sortDirFor: (key: SortKey | null) => "asc" | "desc" | null;
  onSortColumn: (key: SortKey) => void;
  selectedName: string;
  onOpen: (name: string) => void;
}) {
  return (
    <Card className="overflow-hidden border-slate-800 bg-slate-900 ring-0">
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-start">
          <caption className="sr-only">
            مستندات الأرشيف — الأعمدة القابلة للترتيب: الاسم والمقاطع والتاريخ
          </caption>
          <thead>
            <tr className="border-b border-slate-800 text-slate-500">
              {COLUMNS.map((column) => {
                const dir = sortDirFor(column.sort);
                const active = column.sort !== null && sort.key === column.sort;
                return (
                  <th
                    key={column.key}
                    scope="col"
                    aria-sort={
                      column.sort === null
                        ? undefined
                        : active
                          ? sort.dir === "asc"
                            ? "ascending"
                            : "descending"
                          : "none"
                    }
                    className="px-4 py-2 text-start align-middle"
                  >
                    {column.sort === null ? (
                      <span className="flex items-center gap-2 text-[10px] font-normal tracking-[0.2em]">
                        <span className="font-mono tabular-nums text-slate-700">
                          {column.index}
                        </span>
                        {column.label}
                      </span>
                    ) : (
                      <button
                        type="button"
                        onClick={() => onSortColumn(column.sort as SortKey)}
                        aria-label={`رتّب حسب ${column.label}`}
                        className={`flex items-center gap-2 text-[10px] tracking-[0.2em] transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-500/40 ${
                          active ? "text-amber-500" : "hover:text-slate-200"
                        }`}
                      >
                        <span className="font-mono tabular-nums text-slate-700">
                          {column.index}
                        </span>
                        {column.label}
                        <SortIndicator dir={dir} />
                      </button>
                    )}
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800">
            {documents.map((doc) => {
              const selected = doc.document_name === selectedName;
              return (
                <tr
                  key={`${doc.family}-${doc.document_name}`}
                  className={`relative h-11 transition-colors hover:bg-slate-800/50 ${
                    selected ? "bg-slate-800/70" : ""
                  }`}
                >
                  <td className="px-4 py-1">
                    <button
                      type="button"
                      onClick={() => onOpen(doc.document_name)}
                      title={doc.document_name || "بلا اسم"}
                      className="flex items-center gap-2 text-start text-sm text-slate-200 transition-colors after:absolute after:inset-0 after:content-[''] hover:text-amber-500 focus-visible:text-amber-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-500/40"
                    >
                      <EngravedIcon name="papers" className="size-4 text-amber-500" />
                      <span className="min-w-0 max-w-[26rem] truncate">
                        {doc.document_name || "بلا اسم"}
                      </span>
                      {selected && (
                        <span className="sr-only">المستند المفتوح الآن</span>
                      )}
                    </button>
                  </td>
                  <td className="px-4 py-1 text-sm text-slate-400">
                    {doc.document_type || "—"}
                  </td>
                  <td className="px-4 py-1">
                    <span className="inline-flex items-center border border-amber-500/25 px-2 py-0.5 text-[10px] tracking-[0.15em] text-amber-500">
                      {doc.family_label || "—"}
                    </span>
                  </td>
                  <td className="px-4 py-1 font-mono text-sm tabular-nums text-slate-400">
                    {doc.chunks.toLocaleString("ar-AE")}
                  </td>
                  <td
                    dir="ltr"
                    className="px-4 py-1 text-start font-mono text-sm tabular-nums text-slate-400"
                  >
                    {doc.added_at ? doc.added_at.slice(0, 10) : "—"}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

/**
 * شبكة المستندات — «بلاطات Scribd».
 *
 * ⚠️ والبلاطة **ورقةٌ لا بطاقة**: مستطيلٌ فاتح قليلًا (برفع `slate-900` درجة)
 *    لأن المستند في هذا الأرشيف ورقة، والبلاطة تُمثّله. ولا ظلّ عليها — الظلّ
 *    واحد على الورقة المقروءة وحدها.
 */
function DocumentGrid({
  documents,
  selectedName,
  onOpen,
}: {
  documents: ArchiveDocument[];
  selectedName: string;
  onOpen: (name: string) => void;
}) {
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
      {documents.map((doc) => {
        const selected = doc.document_name === selectedName;
        return (
          <button
            key={`${doc.family}-${doc.document_name}`}
            type="button"
            onClick={() => onOpen(doc.document_name)}
            title={doc.document_name || "بلا اسم"}
            className={`flex flex-col items-center gap-3 border px-4 py-6 text-center transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-500/40 ${
              selected
                ? "border-amber-500/40 bg-slate-800"
                : "border-slate-800 bg-slate-900 hover:bg-slate-800/60"
            }`}
          >
            <span className="flex w-full justify-center border-b border-slate-800 pb-4">
              <EngravedIcon name="papers" className="size-9 text-slate-600" />
            </span>
            <span className="line-clamp-2 min-h-[2.5rem] w-full break-words text-sm text-slate-200">
              {doc.document_name || "بلا اسم"}
            </span>
            <span className="mt-auto flex w-full flex-wrap items-center justify-between gap-2 text-[10px] tracking-[0.15em] text-amber-500">
              <span className="truncate">{doc.family_label || "—"}</span>
              <span className="shrink-0 font-mono tabular-nums text-slate-500">
                {doc.chunks.toLocaleString("ar-AE")} مقطعاً
              </span>
            </span>
          </button>
        );
      })}
    </div>
  );
}

/** سطر في قائمة تعريف بيانات المستند — والقيمة الغائبة «—» لا فراغ. */
function MetaRow({
  label,
  value,
  mono = false,
  ltr = false,
}: {
  label: string;
  value: string;
  mono?: boolean;
  ltr?: boolean;
}) {
  return (
    <div className="flex items-start justify-between gap-4 py-3">
      <dt className="shrink-0 text-[11px] tracking-[0.15em] text-slate-500">
        {label}
      </dt>
      <dd
        dir={ltr ? "ltr" : undefined}
        className={`min-w-0 break-words text-start text-slate-200 ${
          mono ? "font-mono text-xs" : "text-sm"
        }`}
      >
        {value || "—"}
      </dd>
    </div>
  );
}
