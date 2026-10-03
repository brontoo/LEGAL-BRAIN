<!-- BEGIN:nextjs-agent-rules -->

# This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` (resolved from this file's directory; in monorepos the `next` package may not be visible from the repo root) before writing any code. Heed deprecation notices.

This block is written and re-added by `next dev` — verify at `node_modules/next/dist/server/lib/generate-agent-files.js`. Removing it from a diff only re-creates the uncommitted change; committing it with your work keeps the tree clean.

<!-- END:nextjs-agent-rules -->

<!-- ============================================================================
     Storybook MCP — أدوات المكوّنات للوكلاء
     ============================================================================
     ما تحت هذا السطر يكتبه الإنسان ولا يمسّه `next dev` (فهو يولّد الكتلة
     المحصورة بين BEGIN و END أعلاه فقط).
     ============================================================================ -->

## قبل كتابة أي واجهة: استعلم عن Storybook

هذا المشروع يشغّل خادم **Storybook MCP**. اسم مجموعة الأدوات: `legal-brain-sb-mcp`.

**القاعدة الأولى: لا تكتب مكوّن واجهة من الصفر قبل أن تستعلم عمّا هو موجود.**
المشروع يجمع ثلاث مكتبات واجهة متداخلة — `@base-ui/react` و`react-aria-components`
و`shadcn` و`cn` — ومكوّن جديد بلا داعٍ يزيد الفوضى. وهناك مكوّنان مبنيان
(`Select` و`InputGroup`) **غير مستخدمَين في أي صفحة**، فتحقّق قبل أن تبني بديلاً.

### عنوان الخادم

| البيئة | العنوان |
|---|---|
| محلي | `http://localhost:6006/mcp` |
| Codespaces | `https://<اسم-الكودسبيس>-<المنفذ>.app.github.dev/mcp` |

⚠️ **لا تفترض رقم المنفذ.** في تجربة فعلية ظهر خادم MCP على منفذ مستقل
(**45541**) لا على منفذ Storybook (6006) — أي أنه قد يبدأ على منفذ خاص به.
**خُذ العنوان من شريط عنوان المتصفح** بعد فتح صفحة `/mcp`، أو من تبويب PORTS.

⚠️ **ويجب أن يكون المنفذ Public**، وإلا أُعيد توجيه الطلبات إلى تسجيل دخول
GitHub — وعندها يفشل أي وكيل يعمل على جهازك لأنه لا يملك جلسة Codespaces.

اسم الكودسبيس والمنفذ يتغيّران، فلا تُثبّت العنوان في أي ملف مُتتبَّع.

### سير العمل المطلوب

1. **اعرف ما هو موجود** — استعلم عن بيان المكوّنات قبل أن تخطّط للتنفيذ.
2. **أعد الاستخدام** — إن وُجد مكوّن يفي بالغرض فاستخدمه ولا تُنشئ بديلاً.
3. **اكتب قصة** — لكل مكوّن جديد أو معدَّل، أضف `*.stories.tsx` بجانبه مع اسم
   عرض عربي عبر `name` (أبقِ معرّف التصدير بالإنجليزية).
4. **شغّل الفحوص** — فحص الوصولية (a11y) وفحوص التفاعل على القصة.
5. **صحّح نفسك** — إن ظهرت مخالفة وصولية فأصلحها وأعد الفحص حتى تنجح.

### اقتراحات المراجعة البصرية

لعرض النتيجة في المحادثة، استخدم أداة القصة التي تُرجع معاينة حية بدل وصف
الكود نصاً.

## ثوابت هذا المشروع — لا تُخالَف

- **العربية و RTL إلزاميان.** كل نص عربي، و`dir="rtl"` و`lang="ar"` مفروضان على
  `<html>` في `app/layout.tsx`. انتبه لاتجاه الأيقونات والأصناف المنطقية.
- **التطبيق داكن فقط.** `className="dark"` مثبَّت في `app/layout.tsx` ولا يوجد
  مبدّل ثيم في المشروع كله. لا تكتب أنماط وضع فاتح ولا تفترض وجوده.
- **لا Markdown في مخرجات المستندات القانونية.** الموجّه في `legal_agent.py`
  يمنع `**` و`#` و`>` صراحةً، لأن المستند يُنسخ إلى Word. وتوجد طبقة تنظيف
  دفاعية في `app/workspace/page.tsx`.
- **الخطوط:** Tajawal عبر `next/font/google`. في Storybook يأتي من
  `.storybook/preview-head.html` لأن `next/font` لا يعمل داخل Storybook.
- **لا أسرار في الواجهة.** كل متغيّر يبدأ بـ `NEXT_PUBLIC_` يُحزَّم في جافاسكربت
  المتصفح. مفاتيح Supabase وGemini تعيش في `.env` على الخادم فقط.

