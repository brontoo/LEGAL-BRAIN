/**
 * أيقونة منقوشة — من game-icons.net
 * ============================================================================
 * ⚠️ ولماذا قناع CSS لا `<img>` ولا SVG مضمَّن؟
 *
 * لأن `<img src="…svg">` **لا يرث `currentColor`**: تبقى الأيقونة بلون الملف
 * ولا تتلوّن مع النصّ ولا مع `hover` ولا مع البند الفعّال في الفهرس. والقناع
 * (`mask-image` + `background-color: currentColor`) يحلّ ذلك **بلا جافاسكربت**.
 * والبديل — تضمين ١٤ ملفاً كـJSX — يعني تحويلها إلى مكوّنات وتكرارها.
 *
 * ⚠️ والرخصة **CC BY 3.0**، ونصّها الملزم: `Icons made by {author}`.
 *    **والإسناد في `/credits` شرط للرخصة، لا زيادة تجميلية.** من حذفه فقد
 *    خالف الترخيص، وهو أمر يخصّ المكتب لا الكود.
 *
 * ⚠️ والانتقاء يدوي: المجموعة فيها ٤١٣٣ أيقونة، ومنها مئات أيقونات العنف
 *    والسحر (`guillotine` · `skull`). ولا تُسحب آلياً أبداً.
 *
 * ⚠️ وقد استُبعدت أيقونات **تتحوّل إلى عجينة عند ١٦ بكسل** لفرط تفاصيلها:
 *    `magnifying-glass` · `wax-seal` · `empty-hourglass` · `wax-tablet` ·
 *    `tribunal-jury`. ولذلك بقي `Search` و`Filter` من Lucide: **أيقونات
 *    الواجهة الصغيرة رقيقة ونظيفة، وأيقونات المعنى منقوشة.** وهو نظام
 *    أيقونات من طبقتين عن قصد، لا خليط.
 */

/** الأسماء المتاحة — نوع صريح يمنع الخطأ المطبعي وقت الفحص. */
export type EngravedIconName =
  | "tied-scroll"
  | "quill-ink"
  | "open-book"
  | "papers"
  | "book-cover"
  | "checked-shield"
  | "hazard-sign"
  | "gavel"
  | "scales"
  | "stamper"
  | "coffee-cup"
  | "briefcase"
  | "diploma"
  | "strongbox";

export function EngravedIcon({
  name,
  className = "size-4",
}: {
  name: EngravedIconName;
  className?: string;
}) {
  const url = `url(/icons/${name}.svg)`;
  return (
    <span
      aria-hidden="true"
      className={`engraved-icon shrink-0 ${className}`}
      style={{ maskImage: url, WebkitMaskImage: url }}
    />
  );
}

/** الفنّانان المستخدمان — وصفحة `/credits` تقرأ منهما فلا تنحرف. */
export const ICON_CREDITS = [
  {
    author: "Lorc",
    url: "http://lorcblog.blogspot.com",
    icons: [
      "tied-scroll",
      "quill-ink",
      "open-book",
      "papers",
      "checked-shield",
      "hazard-sign",
      "gavel",
      "scales",
    ],
  },
  {
    author: "Delapouite",
    url: "http://delapouite.com",
    icons: [
      "book-cover",
      "stamper",
      "coffee-cup",
      "briefcase",
      "diploma",
      "strongbox",
    ],
  },
] as const;
