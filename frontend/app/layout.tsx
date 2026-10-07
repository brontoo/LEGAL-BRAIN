import type { Metadata } from "next";
import { Amiri, Noto_Kufi_Arabic } from "next/font/google";
import "./globals.css";
import { SiteNav } from "@/components/site-nav";
import { Letterhead } from "@/components/letterhead";
// ⚠️ غلاف تفضيل الحركة — مكوّن عميل لأن `MotionConfig` سياقٌ في React،
// و`layout.tsx` مكوّن خادم. وهو يلفّ الشجرة كما هي بلا تغيير في بنيتها.
import { MotionPreference } from "@/components/motion-preference";

/**
 * الترويسة والإطار العام — هوية «المحفوظات».
 * ============================================================================
 * ⚠️ ما تغيّر عن التصميم السابق، ولماذا:
 *
 *   ١) **الخط.** كان `Tajawal` — وهو خطّ هندسي حديث يُقرأ كخطّ تطبيق تقني.
 *      والبديل: **`Amiri`** للعناوين، وهو إحياء خطّ **مطبعة بولاق** التي طبعت
 *      بها الحكومة المصرية — أي **خطّ الوثيقة القانونية المطبوعة نفسها**. و
 *      **`Noto Kufi Arabic`** لواجهة الاستخدام: زواياه الهندسية تُقرأ كنقش لا
 *      كتطبيق.
 *
 *   ٢) **الزجاجية.** كان في الشريط العلوي `backdrop-blur-md` — وهي من أوضح
 *      بصمات واجهات SaaS. أُزيلت: الشريط مصمت ومفصول بخطّ.
 *
 *   ٣) **الزوايا الدائرية** في الشعار والصورة الرمزية والجرس → قائمة، كما في
 *      الورقة والمصنّف.
 *
 *   ٤) **الشعار** صار أقرب إلى **ترويسة خطاب**: رمز نحاسي صغير، ثم الاسم بخطّ
 *      العرض، ثم خطّ رفيع تحته — بدل أيقونة برتقالية داخل مربّع.
 *
 * وكل الألوان تأتي من `globals.css` وحده (تجاوز `slate` و`amber`)، فلا لون
 * مكتوب في هذا الملف.
 */

// خطّ الوثيقة — مطبعة بولاق
const amiri = Amiri({
  subsets: ["arabic"],
  weight: ["400", "700"],
  variable: "--font-amiri",
  display: "swap",
});

// خطّ الواجهة — كوفي هندسي
const kufi = Noto_Kufi_Arabic({
  subsets: ["arabic"],
  weight: ["300", "400", "500", "700"],
  variable: "--font-kufi",
  display: "swap",
});

export const metadata: Metadata = {
  title: "أحمد عيد · العقل القانوني",
  description: "مساحة عمل قانونية شخصية — صياغة مستندات مسندة إلى الأرشيف",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="ar"
      dir="rtl"
      className={`dark ${amiri.variable} ${kufi.variable}`}
    >
      <body
        className={`${kufi.className} bg-slate-950 text-slate-50 antialiased flex h-screen overflow-hidden`}
      >
        {/*
          ⚠️ **وتفضيل الحركة يُعلَن هنا مرّة واحدة** — انظر
          `components/motion-preference.tsx` لسبب كونه في الجذر لا في كل موضع،
          ولحدّه المعلن (`animate-spin` و`transition-colors` خارج حكمه).
          وهو غلافٌ شفّاف: لا يُنتج عنصراً في الشجرة ولا يغيّر شيئاً لمن لم
          يُعطّل الحركة في نظامه.
        */}
        <MotionPreference>
        {/* القائمة الجانبية — مصنّف الملفات */}
        <aside className="flex w-72 flex-col border-s border-slate-800 bg-slate-900">
          {/*
            ⚠️ الترويسة صارت **مكوّناً** لا أسطراً مكتوبة هنا.

            والسبب أن الترويسة ستُستعمل في موضعين: رأس القائمة الجانبية،
            **و** رأس المستند المُصدَّر. ونسختان من نفس الترويسة **تنحرفان** —
            وهو العطب الذي تكرّر في هذا المشروع أكثر من غيره.
          */}
          <div className="border-b border-slate-800 px-5 py-6">
            <Letterhead compact />
          </div>

          <SiteNav />
        </aside>

        {/* المساحة الرئيسية */}
        <main className="flex h-screen flex-1 flex-col overflow-hidden">
          <header className="z-10 flex h-16 shrink-0 items-center justify-between border-b border-slate-800 bg-slate-950 ps-8 pe-8">
            <div className="font-heading text-sm text-slate-500">
              مرحباً بك، أستاذ أحمد
            </div>
            <div className="flex items-center gap-4">
              <button
                type="button"
                aria-label="التنبيهات"
                className="relative border border-slate-800 px-2.5 py-1.5 text-slate-500 transition-colors hover:border-slate-700 hover:text-slate-300"
              >
                <span className="text-[11px] tracking-wider">تنبيهات</span>
                <span className="absolute -top-1 -end-1 h-1.5 w-1.5 bg-amber-500" />
              </button>
              {/*
                ⚠️ الصورة الرمزية — مربّع بزوايا قائمة، كختم على مستند.

                و«البديل الفريد» في دليل الأنماط (`avatar`) هو هذا بعينه: لا صورة
                للمستخدم، فالأحرف الأولى **بدلٌ عنها** لا زينةٌ ناقصة. وما ينقص
                البديلَ في الدليل شيئان، وكلاهما لا يعتمد على الاتجاه:

                  • «Describes the image in alternate text» — فكان المربّع `div`
                    فيه حرفان، يقرؤهما قارئ الشاشة **«أ.ع» وحدها**: حرفان بلا
                    اسم. و`role="img"` + `aria-label` يجعلانه يُنطق صورةً لها
                    اسم («أحمد عيد») لا نصّاً مقطوعاً.
                  • وموضع النقطة (`-end-1`) منطقيّ لا `-right-1`، فيصحّ في RTL.

                ⚠️ وما **لم** يُنقل من الدليل: توليد لونٍ فريد من اسم المستخدم،
                و«Expose multiple sizes». الأول يحتاج مكتبة تجزئة أو دالّة تجزئة
                تُكتب هنا، والثاني يحتاج حجمين — والمنصة **لمستخدم واحد** ولها
                موضع واحد لهذه الصورة. فمكوّنٌ بواجهة `size` و`hash` لا يُستدعى
                بها إلا في موضعٍ واحد هو تعقيدٌ بلا مقابل، وهو خلاف قاعدة
                «أربعة مصادر ولا مصدر خامس» بروحها لا بنصّها.
              */}
              <div
                role="img"
                aria-label="أحمد عيد"
                className="flex h-9 w-9 items-center justify-center border border-slate-700 bg-slate-900 font-heading text-sm text-amber-500"
              >
                أ.ع
              </div>
            </div>
          </header>

          <div className="flex-1 overflow-y-auto p-8">{children}</div>
        </main>
        </MotionPreference>
      </body>
    </html>
  );
}
