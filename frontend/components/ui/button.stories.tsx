import type { Meta, StoryObj } from "@storybook/nextjs-vite";
import { Copy, Loader2, Send, Trash2 } from "lucide-react";

import { Button } from "./button";

/**
 * الزر — أكثر مكوّن استخداماً في التطبيق.
 *
 * ملاحظة على التسمية: معرّفات التصدير (Default, Variants...) إنجليزية لأن
 * معرّفات JavaScript لا يُستحسن أن تكون عربية، بينما الاسم الظاهر في القائمة
 * الجانبية عربي عبر خاصية `name`.
 */
const meta = {
  title: "المكوّنات/الزر",
  component: Button,
  tags: ["autodocs"],
  parameters: {
    layout: "centered",
    docs: {
      description: {
        component:
          "زر مبني على @base-ui/react/button مع متغيّرات الشكل والحجم عبر " +
          "class-variance-authority. يدعم كل حالات ARIA التي تولّدها المكتبة " +
          "(focus-visible، aria-invalid، aria-expanded).",
      },
    },
  },
  argTypes: {
    variant: {
      control: "select",
      options: ["default", "outline", "secondary", "ghost", "destructive", "link"],
      description: "الشكل البصري",
      table: { defaultValue: { summary: "default" } },
    },
    size: {
      control: "select",
      options: [
        "default",
        "xs",
        "sm",
        "lg",
        "icon",
        "icon-xs",
        "icon-sm",
        "icon-lg",
      ],
      description: "الحجم",
      table: { defaultValue: { summary: "default" } },
    },
    disabled: { control: "boolean", description: "تعطيل الزر" },
    children: { control: "text", description: "نص الزر" },
  },
  args: {
    children: "ابدأ الصياغة",
    variant: "default",
    size: "default",
    disabled: false,
  },
} satisfies Meta<typeof Button>;

export default meta;
type Story = StoryObj<typeof meta>;

// ── الحالات الأساسية ─────────────────────────────────────────────────────────

export const Default: Story = { name: "افتراضي" };

export const AllVariants: Story = {
  name: "كل الأشكال",
  render: () => (
    <div className="flex flex-wrap items-center gap-3">
      <Button variant="default">افتراضي</Button>
      <Button variant="outline">محدَّد</Button>
      <Button variant="secondary">ثانوي</Button>
      <Button variant="ghost">شفّاف</Button>
      <Button variant="destructive">حذف</Button>
      <Button variant="link">رابط</Button>
    </div>
  ),
};

export const AllSizes: Story = {
  name: "كل الأحجام",
  render: () => (
    <div className="flex flex-wrap items-center gap-3">
      <Button size="xs">صغير جداً</Button>
      <Button size="sm">صغير</Button>
      <Button size="default">افتراضي</Button>
      <Button size="lg">كبير</Button>
    </div>
  ),
};

// ── حالات التطبيق الحقيقية ───────────────────────────────────────────────────

export const PrimaryAction: Story = {
  name: "الإجراء الرئيسي (ابدأ الصياغة)",
  args: { children: "ابدأ الصياغة", variant: "default", size: "lg" },
  render: (args) => (
    <Button {...args} className="py-6 text-lg">
      <Send className="ml-2 h-5 w-5" />
      {args.children}
    </Button>
  ),
};

export const Loading: Story = {
  name: "قيد التنفيذ (معطَّل)",
  render: () => (
    <Button disabled className="py-6 text-lg">
      <Loader2 className="ml-2 h-5 w-5 animate-spin" />
      جاري الصياغة...
    </Button>
  ),
};

export const WithIcon: Story = {
  name: "مع أيقونة",
  render: () => (
    <div className="flex flex-wrap items-center gap-3">
      <Button variant="outline">
        <Copy className="ml-2 h-4 w-4" />
        نسخ المستند
      </Button>
      <Button variant="destructive">
        <Trash2 className="ml-2 h-4 w-4" />
        حذف
      </Button>
    </div>
  ),
};

export const IconOnly: Story = {
  name: "أيقونة فقط",
  render: () => (
    <div className="flex flex-wrap items-center gap-3">
      <Button size="icon" aria-label="نسخ">
        <Copy />
      </Button>
      <Button size="icon" variant="outline" aria-label="إرسال">
        <Send />
      </Button>
      <Button size="icon" variant="destructive" aria-label="حذف">
        <Trash2 />
      </Button>
    </div>
  ),
};

// ── الحالات الحدّية التي تكشف مشاكل RTL ──────────────────────────────────────

export const Disabled: Story = {
  name: "معطَّل",
  args: { disabled: true, children: "غير متاح" },
};

export const LongArabicText: Story = {
  name: "نص عربي طويل (اختبار RTL)",
  render: () => (
    <div className="w-80 space-y-3">
      <Button className="w-full whitespace-normal py-6 text-center leading-relaxed">
        إصدار إشعار دائن ضريبي واسترداد الشيكات وإلغاؤها والتعويض التأخيري
      </Button>
      <Button variant="outline" className="w-full whitespace-normal py-6 text-center leading-relaxed">
        طلب الحكم بفسخ وإنهاء عقد الإيجار المؤرخ ٢٥/١١/٢٠٢٥
      </Button>
    </div>
  ),
};

export const InContext: Story = {
  name: "داخل سياق حقيقي",
  render: () => (
    <div className="w-96 rounded-xl border border-slate-800 bg-slate-900 p-6">
      <p className="mb-4 text-sm text-slate-400">
        حدد نوع المستند وأدخل المعطيات ليبدأ الفريق عمله.
      </p>
      <div className="flex items-center justify-between gap-3">
        <Button variant="ghost">إلغاء</Button>
        <Button>
          <Send className="ml-2 h-4 w-4" />
          ابدأ الصياغة
        </Button>
      </div>
    </div>
  ),
};
