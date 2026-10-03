import type { Meta, StoryObj } from "@storybook/nextjs-vite";

import { Input } from "./input";

/**
 * حقل الإدخال — مبني على react-aria-components/Input.
 *
 * ملاحظة: هذا المكوّن غير مستخدم حالياً في أي صفحة من التطبيق (الصفحات
 * تستخدم عناصر HTML مباشرة)، فالقصص هنا أول اختبار حقيقي له فعلياً.
 */
const meta = {
  title: "المكوّنات/حقل الإدخال",
  component: Input,
  tags: ["autodocs"],
  parameters: {
    layout: "centered",
    docs: {
      description: {
        component:
          "حقل إدخال نصي مبني على react-aria-components. يدعم كل حالات ARIA " +
          "(aria-invalid، disabled) المنسّقة في الأنماط.",
      },
    },
  },
  argTypes: {
    disabled: { control: "boolean" },
    placeholder: { control: "text" },
    type: {
      control: "select",
      options: ["text", "email", "password", "number", "search", "tel", "url"],
    },
  },
  args: {
    placeholder: "اكتب هنا...",
    disabled: false,
    type: "text",
  },
} satisfies Meta<typeof Input>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = { name: "افتراضي" };

export const WithValue: Story = {
  name: "بقيمة مُدخلة",
  args: { defaultValue: "شركة أفق للمقاولات" },
};

export const Disabled: Story = {
  name: "معطَّل",
  args: { disabled: true, defaultValue: "غير قابل للتعديل" },
};

export const Invalid: Story = {
  name: "حالة خطأ (aria-invalid)",
  args: { defaultValue: "قيمة غير صحيحة", "aria-invalid": true },
};

export const Types: Story = {
  name: "الأنواع المدعومة",
  render: () => (
    <div className="w-80 space-y-3">
      <Input type="text" placeholder="نص" />
      <Input type="email" placeholder="بريد إلكتروني" />
      <Input type="number" placeholder="مبلغ بالدرهم" />
      <Input type="search" placeholder="بحث" />
      <Input type="password" placeholder="كلمة المرور" />
    </div>
  ),
};

export const WithLabel: Story = {
  name: "مع تسمية (الطريقة الصحيحة للوصولية)",
  render: () => (
    <div className="w-80 space-y-2">
      <label htmlFor="client-name" className="text-sm font-medium text-slate-300">
        اسم العميل
      </label>
      <Input id="client-name" placeholder="مثال: شركة أفق للمقاولات" />
      <p className="text-xs text-slate-500">
        التسمية مرتبطة بالحقل عبر htmlFor — وهذا ما يفحصه فحص الوصولية.
      </p>
    </div>
  ),
};

export const LongArabicValue: Story = {
  name: "قيمة عربية طويلة (اختبار القصّ)",
  args: {
    defaultValue:
      "شركة أفق للمقاولات العامة ذ.م.م — فرع دبي، ممثلةً بمديرها القانوني",
  },
};

export const InContext: Story = {
  name: "داخل سياق حقيقي",
  render: () => (
    <div className="w-96 rounded-xl border border-slate-800 bg-slate-900 p-6">
      <label className="mb-2 block text-sm font-medium text-slate-300">
        رقم القضية
      </label>
      <Input placeholder="مثال: 2026/1234" className="bg-slate-950" />
    </div>
  ),
};
