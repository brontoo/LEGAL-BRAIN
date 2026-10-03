import type { Meta, StoryObj } from "@storybook/nextjs-vite";
import { FileText, Scale } from "lucide-react";

import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "./card";

/**
 * البطاقة — الحاوية الأساسية في التطبيق (لوحة القيادة، مساحة الصياغة، المكتبة).
 */
const meta = {
  title: "المكوّنات/البطاقة",
  component: Card,
  tags: ["autodocs"],
  parameters: {
    layout: "centered",
    docs: {
      description: {
        component:
          "حاوية مركّبة من سبعة أجزاء (Card · Header · Title · Description · " +
          "Action · Content · Footer). في التطبيق تُستخدم بأصناف Tailwind " +
          "مباشرة لضبط الثيم الداكن.",
      },
    },
  },
} satisfies Meta<typeof Card>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = {
  name: "افتراضي",
  render: () => (
    <Card className="w-80 bg-slate-900 text-white">
      <CardHeader>
        <CardTitle>مساحة الصياغة</CardTitle>
        <CardDescription className="text-slate-400">
          حدد نوع المستند وأدخل المعطيات والوقائع.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <p className="text-sm text-slate-300">محتوى البطاقة هنا.</p>
      </CardContent>
      <CardFooter>
        <span className="text-xs text-slate-500">آخر تحديث: أمس</span>
      </CardFooter>
    </Card>
  ),
};

export const KpiCards: Story = {
  name: "بطاقات المؤشرات (لوحة القيادة)",
  render: () => (
    <div className="grid w-[52rem] grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-4">
      <Card className="border-slate-800 bg-slate-900 text-white">
        <CardHeader className="flex flex-row items-center justify-between pb-2">
          <CardTitle className="text-lg font-medium text-slate-300">
            إجمالي المستندات
          </CardTitle>
          <FileText className="h-5 w-5 text-amber-500" />
        </CardHeader>
        <CardContent>
          <div className="text-4xl font-bold">1,248</div>
          <p className="mt-2 text-sm text-emerald-400">‎+12% عن الشهر الماضي</p>
        </CardContent>
      </Card>

      <Card className="border-slate-800 bg-slate-900 text-white">
        <CardHeader className="flex flex-row items-center justify-between pb-2">
          <CardTitle className="text-lg font-medium text-slate-300">
            الأسانيد المستخرجة
          </CardTitle>
          <Scale className="h-5 w-5 text-amber-500" />
        </CardHeader>
        <CardContent>
          <div className="text-4xl font-bold">8,530</div>
          <p className="mt-2 text-sm text-slate-400">من أرشيف قاعدة المعرفة</p>
        </CardContent>
      </Card>
    </div>
  ),
};

export const WithAction: Story = {
  name: "مع إجراء في الترويسة",
  render: () => (
    <Card className="w-96 bg-slate-900 text-white">
      <CardHeader>
        <CardTitle>أحدث المستندات</CardTitle>
        <CardDescription className="text-slate-400">
          آخر ما صاغه الفريق
        </CardDescription>
        <CardAction>
          <span className="text-xs text-slate-500">عرض الكل</span>
        </CardAction>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          <div className="flex items-start justify-between border-b border-slate-800 pb-4">
            <div className="space-y-1">
              <p className="text-base leading-none font-medium text-slate-200">
                لائحة دعوى مطالبة مالية
              </p>
              <p className="text-sm text-slate-400">لائحة تجارية</p>
            </div>
            <span className="rounded-md bg-emerald-500/10 px-2 py-1 text-xs text-emerald-500">
              مكتمل
            </span>
          </div>
          <div className="flex items-start justify-between">
            <div className="space-y-1">
              <p className="text-base leading-none font-medium text-slate-200">
                مذكرة دفاع عمالية - استئناف
              </p>
              <p className="text-sm text-slate-400">مذكرة دفاع</p>
            </div>
            <span className="rounded-md bg-amber-500/10 px-2 py-1 text-xs text-amber-500">
              قيد المراجعة
            </span>
          </div>
        </div>
      </CardContent>
    </Card>
  ),
};

export const LongArabicContent: Story = {
  name: "محتوى عربي طويل (اختبار الفوضى البصرية)",
  render: () => (
    <Card className="w-[36rem] bg-slate-900 text-white">
      <CardHeader>
        <CardTitle>موضوع الدعوى</CardTitle>
      </CardHeader>
      <CardContent>
        <p className="leading-loose text-slate-300">
          طلب الحكم بفسخ وإنهاء عقد الإيجار المؤرخ ٢٥/١١/٢٠٢٥ واتفاقية الخدمات
          المرتبطة به، واعتبار العلاقة منتهية اعتباراً من تاريخ إخلاء العين في
          ٣٠/٠٤/٢٠٢٦ وتسليم مفاتيحها، وإلزام المدعى عليهم كلٌّ في حدود صفته وما
          قبضه من مبالغ برد مبلغ إجمالي قدره ٢٦٠٩٧٣٫٥١ درهماً.
        </p>
      </CardContent>
    </Card>
  ),
};
