import Link from "next/link";
import { Letterhead } from "@/components/letterhead";

/**
 * الصفحة الرئيسية — «غلاف الملف».
 * ============================================================================
 * ⚠️ وما كان هنا قبل هذا التغيير، ولماذا حُذف:
 *
 *   • **أربع بطاقات إحصاء** (مستندات · مقاطع · تصحيحات · حالة الخادم)
 *   • **رسم بياني** (Recharts) لتوزيع الأرشيف على العائلات
 *
 * وكلها **أرقام**. والرقم في لوحة قيادة يقول «هذا نظام يُقاس» — وهو **منطق
 * مُشغِّل خدمة لا مكتب محامٍ**. والمحامي لا يفتح مكتبه ليقرأ عدّادات؛ يفتحه
 * **ليبدأ عملاً**.
 *
 * ⚠️ والبديل مأخوذ من الشيء نفسه: **الصفحة الأولى في ملف القضية**.
 *    ترويسة، ثم تاريخ، ثم سطر يبدأ منه العمل، ثم فهرس. **بلا رقم واحد.**
 *
 * ⚠️ ولهذا صار `recharts` **غير مستخدم في المشروع كله**. ولم أحذفه من
 *    `package.json` عن قصد: حذفه من الملف وحده **يُبقي ملف القفل غير متوافق**
 *    فيفشل `npm ci`. والصواب أن تنفّذ أنت:
 *
 *        cd frontend && npm uninstall recharts
 *
 *    فيتولّى npm تحديث الاثنين معاً، **ويوفّر مساحة** — وهي حاجة قائمة عندك.
 *
 * ⚠️ وهي **مكوّنة خادم** (بلا `"use client"`): لا حالة ولا تفاعل. و
 *    `force-dynamic` يجعل التاريخ يُحسب **عند كل طلب** لا عند البناء، فلا
 *    يتجمّد على يوم النشر.
 */

export const dynamic = "force-dynamic";

/** المداخل الثلاثة — كفهرس ملف، لا كأزرار. */
const PLACES = [
  {
    index: "٠١",
    href: "/workspace",
    title: "مساحة الصياغة",
    note: "اكتب الوقائع، ويصوغ الفريق المستند",
  },
  {
    index: "٠٢",
    href: "/library",
    title: "الأرشيف والمكتبة",
    note: "ما يستند إليه الفريق في الصياغة",
  },
  {
    index: "٠٣",
    href: "/credits",
    title: "الإسناد والرخص",
    note: "ما نستخدمه من أعمال غيرنا",
  },
];

/** التاريخ بالعربية — يُحسب عند الطلب، ولا يُخترع ولا يُخزَّن. */
function todayInArabic(): string {
  return new Intl.DateTimeFormat("ar-AE", {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
  }).format(new Date());
}

export default function Home() {
  return (
    <div className="mx-auto max-w-3xl">
      {/*
        الورقة — سطح واحد بحدّ رفيع، لا بطاقات متجاورة.

        ⚠️ وهو الفرق بين «صفحة» و«لوحة»: اللوحة تُقسَّم إلى مربّعات متجاورة،
        والصفحة **سطح متّصل** يُقرأ من أعلى إلى أسفل.
      */}
      <article className="border border-slate-800 bg-slate-900">
        {/* ── الترويسة ── */}
        <header className="border-b border-slate-800 px-10 py-9">
          <Letterhead />
        </header>

        {/* ── ما يُبدأ منه العمل ── */}
        <section className="relative border-b border-slate-800 py-10 pe-10 ps-14">
          {/*
            ⚠️ الهامش — وهو من **الورق المسطّر القانوني**، حيث يفصل خطّ رأسي
            الحاشية عن متن الورقة.

            وبلون الختم `seal` لا بالأحمر الدلالي: فهو **حدّ ورقة** لا تنبيه.
            وبشفافية عالية لأن الهامش **يُحسّ ولا يُقرأ** — ولو ظهر لصار زينة.
          */}
          <span
            className="absolute inset-y-6 start-7 w-px bg-seal/25"
            aria-hidden="true"
          />

          <p className="font-heading text-sm text-slate-500">{todayInArabic()}</p>

          <h1 className="mt-6 font-heading text-2xl leading-relaxed text-slate-100">
            ابدأ الصياغة
          </h1>
          <p className="mt-3 max-w-md text-sm leading-relaxed text-slate-400">
            اكتب الوقائع، ويصوغ الفريق المستند كاملاً مسنداً إلى أرشيفك — مع
            التحقّق من كل سند قبل التسليم.
          </p>

          <Link
            href="/workspace"
            className="mt-7 inline-flex items-center gap-2 border border-amber-500/40 px-5 py-2.5 text-sm text-amber-500 transition-colors hover:border-amber-500 hover:bg-amber-500/10"
          >
            ابدأ الصياغة
            {/* السهم في اتجاه القراءة — RTL */}
            <span aria-hidden="true">←</span>
          </Link>
        </section>

        {/* ── الفهرس ── */}
        <nav className="relative py-2 pe-10 ps-14">
          <span
            className="absolute inset-y-4 start-7 w-px bg-seal/25"
            aria-hidden="true"
          />

          <ul>
            {PLACES.map((place) => (
              <li key={place.href}>
                <Link
                  href={place.href}
                  className="group flex items-baseline gap-4 border-b border-slate-800/60 py-4 last:border-0"
                >
                  <span className="font-mono text-[11px] tabular-nums text-slate-600">
                    {place.index}
                  </span>
                  <span className="flex-1">
                    <span className="block text-base text-slate-200 transition-colors group-hover:text-amber-500">
                      {place.title}
                    </span>
                    <span className="mt-0.5 block text-xs text-slate-500">
                      {place.note}
                    </span>
                  </span>
                  <span
                    className="text-slate-700 transition-colors group-hover:text-amber-500"
                    aria-hidden="true"
                  >
                    ←
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        </nav>

        {/* ── ذيل الورقة — بلا رقم واحد ── */}
        <footer className="border-t border-slate-800 px-10 py-5">
          <p className="text-[11px] tracking-[0.15em] text-slate-600">
            الأرشيف جاهز · الفريق في مقاعده
          </p>
        </footer>
      </article>
    </div>
  );
}
