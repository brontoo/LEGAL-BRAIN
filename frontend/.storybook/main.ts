import type { StorybookConfig } from "@storybook/nextjs-vite";

/**
 * إعداد Storybook للعقل القانوني.
 *
 * الإطار: @storybook/nextjs-vite (وليس @storybook/nextjs)
 *   المشروع لا يستخدم Webpack ولا Babel مخصّصاً، والنسخة المبنية على Vite أسرع
 *   وتدعم إضافات الاختبار بشكل كامل — وهي الموصى بها رسمياً لمشاريع Next.js.
 *   كما أن Vite يحمّل postcss.config.mjs تلقائياً، فيعمل Tailwind v4 بلا إعداد.
 */
const config: StorybookConfig = {
  stories: [
    // قصص مكوّنات الواجهة — النمط الوحيد الموجود حالياً.
    //
    // لو أضفت لاحقاً صفحات توثيق MDX أو قصصاً لصفحات التطبيق، أضف الأنماط
    // التالية. تُركت مُعلَّقة لأن Storybook يطبع تحذيراً عند كل تشغيل على نمط
    // لا يطابق شيئاً، والتحذيرات الكاذبة تُخفي الأخطاء الحقيقية.
    //   "../components/**/*.mdx",
    //   "../app/**/*.mdx",
    //   "../app/**/*.stories.@(js|jsx|mjs|ts|tsx)",
    "../components/**/*.stories.@(js|jsx|mjs|ts|tsx)",
  ],

  addons: [
    // التوثيق التلقائي: يحوّل التعليقات وargTypes إلى صفحة وثائق لكل مكوّن
    "@storybook/addon-docs",
    // فحص الوصولية بـ axe-core — مهم جداً لواجهة عربية RTL
    "@storybook/addon-a11y",

    // ────────────────────────────────────────────────────────────────────────
    // المستوى ٤ (MCP للوكلاء) — مُعطَّل عن قصد في البداية.
    //
    // بعد التأكد من أن Storybook يعمل، أزل التعليق عن السطر التالي، ثم:
    //     npm install -D @storybook/addon-mcp
    //
    // السبب في تأجيله: لو تعطّل تحميل أي إضافة فلن يبدأ Storybook أصلاً،
    // فنضمن أولاً أن الأساس سليم ثم نضيف الطبقة الذكية.
    // ────────────────────────────────────────────────────────────────────────
    // "@storybook/addon-mcp",
  ],

  framework: {
    name: "@storybook/nextjs-vite",
    options: {},
  },

  // ملفات public (الأيقونات والشعارات) تبقى متاحة داخل القصص
  staticDirs: ["../public"],
};

export default config;
