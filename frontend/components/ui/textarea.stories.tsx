import type { Meta, StoryObj } from "@storybook/nextjs-vite";

import { Textarea } from "./textarea";

/**
 * منطقة النص — العنصر الذي يكتب فيه المحامي وقائع الدعوى.
 *
 * هذا أهم مكوّن لاختبار تجربة الكتابة بالعربية: النص الطويل، والأرقام،
 * والاتجاه RTL، وسلوك min-h مع field-sizing-content.
 */
const meta = {
  title: "المكوّنات/منطقة النص",
  component: Textarea,
  tags: ["autodocs"],
  parameters: {
    layout: "centered",
    docs: {
      description: {
        component:
          "منطقة نص متعدّدة الأسطر. تستخدم field-sizing-content فتنمو تلقائياً " +
          "مع المحتوى في المتصفحات الداعمة.",
      },
    },
  },
  argTypes: {
    disabled: { control: "boolean" },
    placeholder: { control: "text" },
    rows: { control: "number" },
  },
  args: {
    placeholder: "مثال: مطالبة مالية بقيمة 20,000 درهم عن فواتير غير مسددة...",
    disabled: false,
  },
} satisfies Meta<typeof Textarea>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = { name: "افتراضي" };

export const Disabled: Story = {
  name: "معطَّل",
  args: { disabled: true, defaultValue: "لا يمكن التعديل أثناء الصياغة" },
};

export const Invalid: Story = {
  name: "حالة خطأ (aria-invalid)",
  args: { defaultValue: "وقائع ناقصة", "aria-invalid": true },
};

/**
 * اختبار واقعي: نفس نص الوقائع الذي أدخله المستخدم فعلاً في التطبيق.
 * الغرض كشف أخطاء الاتجاه والالتفاف في النص القانوني العربي.
 */
export const RealLegalFacts: Story = {
  name: "وقائع دعوى حقيقية (النص الفعلي المستخدم)",
  args: {
    rows: 12,
    className: "w-[34rem]",
    defaultValue: `دعوى يطلب الحكم بفسخ وإنهاء عقد الإيجار المؤرخ 25/11/2025 واتفاقية الخدمات المرتبطة به، واعتبار العلاقة منتهية اعتباراً من تاريخ إخلاء العين في 30/04/2026 وتسليم مفاتيحها إلى إدارة المعسكر، وإلزام المدعى عليهم كلٌّ في حدود صفته وما قبضه من مبالغ، برد مبلغ إجمالي قدره 260,973.51 درهماً، مع رد أو إلغاء أية شيكات تخص المدة اللاحقة للإنهاء، وإصدار إشعار دائن ضريبي عن الخدمات التي لم تُقدَّم.`,
  },
};

export const LongUnbrokenText: Story = {
  name: "نص طويل جداً بلا فواصل (اختبار الفائض)",
  args: {
    rows: 8,
    className: "w-[28rem]",
    defaultValue:
      "بموجب عقد الإيجار المؤرخ 25/11/2025 واتفاقية الخدمات المرتبطة به والمبرمة بين الطرفين والمتضمنة بنوداً تفصيلية بشأن الالتزامات المتبادلة وضمانات التنفيذ وشروط الإنهاء والتعويض التأخيري بواقع 5% سنوياً عن المدد المتأخرة في التسليم.",
  },
};

export const InContext: Story = {
  name: "داخل سياق حقيقي",
  render: () => (
    <div className="w-96 rounded-xl border border-slate-800 bg-slate-900 p-6">
      <label className="mb-2 block text-sm font-medium text-slate-300">
        الوقائع والمعطيات
      </label>
      <Textarea
        rows={6}
        className="resize-none bg-slate-950"
        placeholder="مثال: مطالبة مالية بقيمة 20,000 درهم عن فواتير غير مسددة..."
      />
    </div>
  ),
};
