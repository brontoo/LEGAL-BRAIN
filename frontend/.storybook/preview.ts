import type { Preview } from "@storybook/nextjs-vite";

// استيراد أنماط التطبيق — بدونها تُرسم المكوّنات بلا تنسيق إطلاقاً.
// Vite يمرّر هذا الملف عبر postcss.config.mjs، فيعمل Tailwind v4 تلقائياً.
import "../app/globals.css";

/**
 * الإعداد العام للقصص.
 *
 * ملاحظة عن RTL والثيم: لا نضعهما هنا عبر decorator، بل في
 * preview-head.html — لأن وضعهما على عنصر <html> نفسه هو ما يفعله
 * تطبيقك الحقيقي في app/layout.tsx:
 *
 *     <html lang="ar" dir="rtl" className="dark">
 *
 * وهذا يضمن أن ما تراه في Storybook مطابق لما تراه في المتصفح، بما في ذلك
 * أنماط `@layer base` التي تستهدف body و html.
 */
const preview: Preview = {
  parameters: {
    // توسيط المكوّن في منتصف اللوحة — مناسب لعناصر الواجهة المفردة
    layout: "centered",

    // لوحة التحكم بالخصائص (مدمجة في نواة Storybook 10)
    controls: {
      matchers: {
        color: /(background|color)$/i,
        date: /Date$/i,
      },
    },

    // إعداد فحص الوصولية
    a11y: {
      // "todo" تُظهر المخالفات في اللوحة دون إسقاط الاختبار — مناسبة للبداية
      // مع مشروع قائم لم يُفحص من قبل. بعد معالجة المخالفات اجعلها "error".
      test: "todo",
    },
  },
};

export default preview;
