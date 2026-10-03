<!-- BEGIN:nextjs-agent-rules -->

# This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` (resolved from this file's directory; in monorepos the `next` package may not be visible from the repo root) before writing any code. Heed deprecation notices.

This block is written and re-added by `next dev` — verify at `node_modules/next/dist/server/lib/generate-agent-files.js`. Removing it from a diff only re-creates the uncommitted change; committing it with your work keeps the tree clean.

<!-- END:nextjs-agent-rules -->

<!-- ============================================================================
     ما تحت هذا السطر يكتبه الإنسان ولا يمسّه `next dev` (فهو يولّد الكتلة
     المحصورة بين BEGIN و END أعلاه فقط).
     ============================================================================ -->

## قبل أن تبني مكوّناً واجهياً جديداً

المشروع يجمع **أربعة** مصادر لمكوّنات الواجهة، وأسهل خطأ هو إضافة مصدر خامس:

| المصدر | أمثلة |
|---|---|
| `components/ui/` | `Button` · `Card` · `Input` · `Textarea` · `InputGroup` |
| `@base-ui/react` | أساس `Button` و`Select` |
| `react-aria-components` | أساس `Input` و`Textarea` و`InputGroup` |
| `cn` + `class-variance-authority` | دمج الأصناف ومتغيّراتها |

**تحقّق أولاً مما هو موجود في `components/ui/`.** وهناك مكوّن مبني ولم يُستخدم
حتى الآن: **`Select`** (القائمة المنسدلة) — فلا تبنِ قائمة جديدة قبل النظر إليه.
و`InputGroup` كان مثله حتى استُخدم فعلاً في `app/library/page.tsx`.

## ثوابت هذا المشروع — لا تُخالَف

- **العربية و RTL إلزاميان.** كل نص عربي، و`dir="rtl"` و`lang="ar"` مفروضان على
  `<html>` في `app/layout.tsx`. انتبه لاتجاه الأيقونات والأصناف المنطقية.

- **التطبيق داكن فقط.** `className="dark"` مثبَّت في `app/layout.tsx` ولا يوجد
  مبدّل ثيم في المشروع كله. لا تكتب أنماط وضع فاتح ولا تفترض وجوده.

- **لا Markdown في مخرجات المستندات القانونية.** الموجّه في `legal_agent.py`
  يمنع `**` و`#` و`>` صراحةً، لأن المستند يُنسخ إلى Word. وتوجد طبقة تنظيف
  دفاعية في `app/workspace/page.tsx`.

- **لا تخاطب FastAPI مباشرة من الواجهة.** كل النداءات تمرّ عبر الوسيط
  `app/api/[...path]/route.ts` على المسار `/api/*`. السبب: رمز المصادقة
  (`API_TOKEN`) يُضاف على الخادم، ولا يجوز أن يصل إلى المتصفح.

- **⛔ لا تستخدم بادئة `NEXT_PUBLIC_` لأي قيمة حسّاسة.** كل متغيّر يحملها
  يُحزَّم داخل جافاسكربت المتصفح ويقرأه أي زائر من مصدر الصفحة. ولذلك
  `API_TOKEN` و`BACKEND_URL` في `frontend/.env.local` **بلا** بادئة.

- **الخطوط:** Tajawal عبر `next/font/google` في `app/layout.tsx`.
