"use client";

/**
 * فهرس التنقّل — كصفحة محتويات في ملف قضية.
 * ============================================================================
 * ⚠️ ولماذا مكوّن منفصل؟ لأن تمييز الصفحة الحالية يحتاج `usePathname`، وهو
 *    خاص بالعميل. و`layout.tsx` مكوّن خادم.

 * ⚠️ وهذا ليس تجميلاً: النسخة السابقة **لم تكن تُظهر أي مؤشّر للصفحة الحالية**
 *    — الروابط الثلاثة متطابقة تماماً، فلا يعرف المستخدم أين هو. وهو نقص حقيقي
 *    كشفه إعادة التصميم.

 * والفكرة البصرية: بدل «أزرار تنقّل» دائرية الزوايا، **فهرس مرقّم بخطّ فاصل**
 * كفهرس ملف ورقي: رقم، ثم سطر، ثم عنوان. والشريط النحاسي على الحافة اليمنى
 * (البداية في RTL) يعلّم البند الفعّال، كما يعلّم اللسانُ الصفحةَ في المصنّف.
 */

import Link from "next/link";
import { usePathname } from "next/navigation";
import { EngravedIcon, type EngravedIconName } from "@/components/engraved-icon";

/**
 * ⚠️ والأيقونات **منقوشة** لا مسطّحة: من `game-icons.net` برخصة **CC BY 3.0**،
 *    والإسناد في `/credits` **شرط للرخصة**. والانتقاء من الأيقونات النظيفة عند
 *    ١٦ بكسل وحدها — استُبعدت أيقونات تتحوّل إلى عجينة لفرط تفاصيلها.
 */
const ITEMS: {
  href: string;
  index: string;
  label: string;
  icon: EngravedIconName;
}[] = [
  { href: "/", index: "٠١", label: "لوحة القيادة", icon: "tied-scroll" },
  { href: "/workspace", index: "٠٢", label: "مساحة الصياغة", icon: "quill-ink" },
  { href: "/library", index: "٠٣", label: "الأرشيف والمكتبة", icon: "open-book" },
];

export function SiteNav() {
  const pathname = usePathname();

  return (
    <nav className="flex-1 overflow-y-auto">
      <div className="border-b border-slate-800 px-5 py-2.5">
        <span className="text-[10px] tracking-[0.25em] text-slate-600">الفهرس</span>
      </div>

      <ul>
        {ITEMS.map((item) => {
          const active = pathname === item.href;

          return (
            <li key={item.href}>
              <Link
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={`group flex items-center gap-3 border-b border-slate-800/50 px-5 py-3.5 transition-colors ${
                  active
                    ? "border-s-2 border-s-amber-500 bg-slate-900 text-slate-100"
                    : "border-s-2 border-s-transparent text-slate-400 hover:bg-slate-900/50 hover:text-slate-200"
                }`}
              >
                <span
                  className={`font-mono text-[11px] tabular-nums ${
                    active ? "text-amber-500" : "text-slate-600 group-hover:text-slate-500"
                  }`}
                >
                  {item.index}
                </span>
                {/* الأيقونة ترث لون النصّ عبر القناع — فلا صنف لون منفصل */}
                <EngravedIcon name={item.icon} className="size-[18px]" />
                <span className="text-base leading-none">{item.label}</span>
              </Link>
            </li>
          );
        })}
      </ul>

      {/*
        ⚠️ الإعدادات **ليست** في الفهرس: صفحتها غير موجودة بعد (`/settings` بلا
        ملف)، فالرابط يوعد بما لا يوجد. وهو نفس ما حذفناه من أزرار الأرشيف
        (عرض · تحميل · حذف) — **زرّ لا يعمل أسوأ من غيابه**.

        ⚠️ و`/credits` ليست في الفهرس لأنها **ليست مهمّة عمل**، لكن الرابط
        لازم لأن رخصة الأيقونات (CC BY 3.0) **تشترط الإسناد**.
      */}
      <div className="px-5 py-4">
        <Link
          href="/credits"
          className="text-[11px] text-slate-600 underline underline-offset-2 transition-colors hover:text-slate-400"
        >
          الإسناد والرخص
        </Link>
      </div>
    </nav>
  );
}
