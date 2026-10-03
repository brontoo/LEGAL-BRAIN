import type { Meta, StoryObj } from "@storybook/nextjs-vite";

import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectSeparator,
  SelectTrigger,
  SelectValue,
} from "./select";

/**
 * القائمة المنسدلة — مبنية على @base-ui/react/select.
 *
 * ⚠️ هذا المكوّن غير مستخدم في أي صفحة: مساحة الصياغة تستخدم عنصر <select>
 *    من HTML مباشرة. فالقصص هنا أول تشغيل حقيقي له، ومن المرجّح أن تكشف
 *    مشاكل لم تظهر بعد (خصوصاً في تموضع القائمة باتجاه RTL).
 *
 * سبب استخدام غلاف محلّي بدل تمرير المكوّن مباشرة: Select مكوّن مركّب عام
 * (generic compound)، وتمريره إلى Storybook مباشرة يُنتج أنواعاً معقّدة.
 * الغلاف يعطي typing واضحاً ووثائق أوضح.
 */

const DOCUMENT_TYPES: { value: string; label: string }[] = [
  { value: "lawsuit", label: "لائحة دعوى تجارية" },
  { value: "notice", label: "إنذار قانوني" },
  { value: "poa", label: "وكالة قانونية خاصة" },
  { value: "memo", label: "مذكرة دفاع" },
];

function DocumentTypeSelect({
  className = "w-64",
  placeholder = "اختر نوع المستند",
  disabled = false,
  defaultValue,
}: {
  className?: string;
  placeholder?: string;
  disabled?: boolean;
  defaultValue?: string;
}) {
  return (
    <Select items={DOCUMENT_TYPES} defaultValue={defaultValue} disabled={disabled}>
      <SelectTrigger className={className}>
        <SelectValue placeholder={placeholder} />
      </SelectTrigger>
      <SelectContent>
        <SelectGroup>
          <SelectLabel>المستندات القانونية</SelectLabel>
          {DOCUMENT_TYPES.map((item) => (
            <SelectItem key={item.value} value={item.value}>
              {item.label}
            </SelectItem>
          ))}
        </SelectGroup>
        <SelectSeparator />
        <SelectItem value="other">أخرى</SelectItem>
      </SelectContent>
    </Select>
  );
}

const meta = {
  title: "المكوّنات/القائمة المنسدلة",
  component: DocumentTypeSelect,
  tags: ["autodocs"],
  parameters: {
    layout: "centered",
    docs: {
      description: {
        component:
          "قائمة منسدلة لاختيار نوع المستند. تمرير `items` إلى الجذر هو ما يجعل " +
          "الزر يعرض التسمية العربية بدل القيمة الخام (lawsuit مثلاً).",
      },
    },
  },
  argTypes: {
    placeholder: { control: "text" },
    disabled: { control: "boolean" },
    defaultValue: {
      control: "select",
      options: [undefined, ...DOCUMENT_TYPES.map((t) => t.value), "other"],
    },
  },
  args: {
    placeholder: "اختر نوع المستند",
    disabled: false,
  },
} satisfies Meta<typeof DocumentTypeSelect>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = { name: "افتراضي (بلا اختيار)" };

export const WithSelection: Story = {
  name: "باختيار مسبق",
  args: { defaultValue: "notice" },
};

export const Disabled: Story = {
  name: "معطَّل",
  args: { disabled: true, defaultValue: "lawsuit" },
};

export const Sizes: Story = {
  name: "الحجمان المتاحان",
  render: () => (
    <div className="flex flex-col items-start gap-4">
      <DocumentTypeSelect className="w-64" />
      <DocumentTypeSelect className="h-7 w-64 rounded-[min(var(--radius-md),10px)]" />
      <p className="text-xs text-slate-500">
        الحجم يُضبط عبر الأصناف، والفرق بينهما 4 بكسل في الارتفاع.
      </p>
    </div>
  ),
};

export const InContext: Story = {
  name: "داخل سياق حقيقي (مساحة الصياغة)",
  render: () => (
    <div className="w-96 rounded-xl border border-slate-800 bg-slate-900 p-6">
      <label className="mb-2 block text-sm font-medium text-slate-300">
        نوع المستند
      </label>
      <DocumentTypeSelect className="w-full" />
      <p className="mt-3 text-xs text-slate-500">
        القائمة تُفتح فوق الزر لتحاذي النص المختار — وهذا سلوك Base UI الافتراضي.
      </p>
    </div>
  ),
};
