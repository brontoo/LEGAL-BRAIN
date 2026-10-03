import type { Meta, StoryObj } from "@storybook/nextjs-vite";
import { Search, Send } from "lucide-react";

import {
  InputGroup,
  InputGroupAddon,
  InputGroupButton,
  InputGroupInput,
  InputGroupText,
  InputGroupTextarea,
} from "./input-group";

/**
 * مجموعة الإدخال — تجمع حقلاً مع إضافات (أيقونة، زر، نص مساعد).
 *
 * ⚠️ مثل القائمة المنسدلة، هذا المكوّن غير مستخدم في أي صفحة بعد.
 *    وهو مركّب من مكتبتين مختلفتين: react-aria-components (Group، Input،
 *    Textarea) و @base-ui/react (الزر) — أي أنه أكثر مكوّن يحتمل أن يكشف
 *    تعارضاً بين المكتبتين، وهذه قيمته الأساسية كاختبار.
 */

function SearchGroup({ className = "w-80" }: { className?: string }) {
  return (
    <InputGroup className={className}>
      <InputGroupAddon align="inline-start">
        <InputGroupText>
          <Search className="h-4 w-4" />
        </InputGroupText>
      </InputGroupAddon>
      <InputGroupInput placeholder="ابحث في الأرشيف والمكتبة..." />
    </InputGroup>
  );
}

function PromptGroup({
  className = "w-96",
  disabled = false,
}: {
  className?: string;
  disabled?: boolean;
}) {
  return (
    <InputGroup className={className}>
      <InputGroupTextarea
        rows={3}
        disabled={disabled}
        placeholder="اكتب طلبك القانوني هنا..."
      />
      <InputGroupAddon align="block-end" className="justify-end">
        <InputGroupText>‏جرّب: صغ إنذاراً بالإخلاء</InputGroupText>
        <InputGroupButton variant="default" size="sm" disabled={disabled}>
          <Send className="h-4 w-4" />
          إرسال
        </InputGroupButton>
      </InputGroupAddon>
    </InputGroup>
  );
}

const meta = {
  title: "المكوّنات/مجموعة الإدخال",
  component: SearchGroup,
  tags: ["autodocs"],
  parameters: {
    layout: "centered",
    docs: {
      description: {
        component:
          "حقل مع إضافات في البداية أو النهاية أو أعلى/أسفل الحقل. " +
          "الموضع يُضبط بـ align: inline-start · inline-end · block-start · block-end.",
      },
    },
  },
  argTypes: {
    className: { control: "text" },
  },
  args: { className: "w-80" },
} satisfies Meta<typeof SearchGroup>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Search_: Story = {
  name: "بحث بأيقونة",
  args: { className: "w-80" },
};

export const Prompt: Story = {
  name: "صندوق طلب مع زر إرسال",
  render: () => <PromptGroup />,
};

export const PromptDisabled: Story = {
  name: "صندوق الطلب أثناء الصياغة (معطَّل)",
  render: () => <PromptGroup disabled />,
};

export const AllAlignments: Story = {
  name: "كل مواضع الإضافات",
  render: () => (
    <div className="flex w-[30rem] flex-col gap-5">
      <div>
        <p className="mb-2 text-xs text-slate-500">inline-start</p>
        <SearchGroup className="w-full" />
      </div>
      <div>
        <p className="mb-2 text-xs text-slate-500">block-end (زر أسفل الحقل)</p>
        <PromptGroup className="w-full" />
      </div>
    </div>
  ),
};

export const LongArabicValue: Story = {
  name: "قيمة عربية طويلة (اختبار الفائض)",
  render: () => (
    <InputGroup className="w-80">
      <InputGroupAddon align="inline-start">
        <InputGroupText>العميل</InputGroupText>
      </InputGroupAddon>
      <InputGroupInput defaultValue="شركة أفق للمقاولات العامة ذ.م.م — فرع دبي" />
    </InputGroup>
  ),
};
