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
import { LayoutDashboard, FileSignature, LibrarySquare } from "lucide-react";

const ITEMS = [
  { href: "/", index: "٠١", label: "لوحة القيادة", icon: LayoutDashboard },
  { href: "/workspace", index: "٠٢", label: "مساحة الصياغة", icon: FileSignature },
  { href: "/library", index: "٠٣", label: "الأرشيف والمكتبة", icon: LibrarySquare },
] as const;

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
          const Icon = item.icon;

          return (
            <li key={item.href}>
              <Link
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={`group flex items-baseline gap-3 border-b border-slate-800/50 px-5 py-3.5 transition-colors ${
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
                <Icon className={`w-4 h-4 shrink-0 ${active ? "text-amber-500" : ""}`} />
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
      */}
      <p className="px-5 py-4 text-[11px] leading-relaxed text-slate-700">
        الإعدادات غير متاحة بعد.
      </p>
    </nav>
  );
}
