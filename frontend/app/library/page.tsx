"use client";

import { useState } from "react";
import { Search, Filter, Download, Eye, MoreHorizontal, FileText, Trash2 } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  InputGroup,
  InputGroupAddon,
  InputGroupInput,
  InputGroupText,
} from "@/components/ui/input-group";

// بيانات تجريبية تعكس طبيعة المستندات القانونية
const initialDocs = [
  { id: 1, title: "لائحة دعوى مطالبة مالية - شركة أفق", type: "لائحة تجارية", date: "2026-09-25", status: "مكتمل" },
  { id: 2, title: "مذكرة رد على منازعة عمالية", type: "مذكرة دفاع", date: "2026-09-24", status: "مكتمل" },
  { id: 3, title: "اتفاقية بيع عقار (إمارة دبي)", type: "عقود عقارية", date: "2026-09-23", status: "مكتمل" },
  { id: 4, title: "مذكرة دفاع ابتدائية - محاكم دبي", type: "مذكرة دفاع", date: "2026-09-22", status: "قيد المراجعة" },
  { id: 5, title: "إنذار قانوني بالإخلاء للسداد", type: "إنذار عدلي", date: "2026-09-20", status: "مكتمل" },
  { id: 6, title: "عقد تأسيس شركة ذات مسؤولية محدودة", type: "عقود تجارية", date: "2026-09-18", status: "مسودة" },
  { id: 7, title: "وكالة خاصة ببيع عقار (دبي مارينا)", type: "توكيل رسمي", date: "2026-09-15", status: "مكتمل" },
];

export default function Library() {
  const [searchTerm, setSearchTerm] = useState("");
  const [docs, setDocs] = useState(initialDocs);

  // دالة تصفية المستندات بناءً على البحث
  const filteredDocs = docs.filter(doc => 
    doc.title.includes(searchTerm) || doc.type.includes(searchTerm)
  );

  return (
    <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-700 ease-out">
      
      {/* الترويسة وشريط البحث */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div>
          <h1 className="text-3xl font-bold text-white tracking-tight">الأرشيف والمكتبة</h1>
          <p className="text-slate-400 mt-1">تصفح، ابحث، وقم بإدارة كافة مستنداتك القانونية المصاغة.</p>
        </div>
        
        <div className="flex w-full md:w-auto items-center gap-3">
          {/*
            كان هنا حقل بحث مكتوب يدوياً: div + أيقونة بموضع مطلق + input خام،
            بأصناف Tailwind خاصة به. استُبدل بـ InputGroup من components/ui —
            وهو مكوّن كان مبنياً وجاهزاً ولم يكن مستخدَماً في أي صفحة.

            الفائدة: حدود وزوايا وتباعد موحّدة مع بقية النظام، وحالات
            focus/disabled/aria-invalid معالجة في مكان واحد بدل تكرارها.
          */}
          <InputGroup className="w-full md:w-80">
            <InputGroupAddon align="inline-start">
              <InputGroupText>
                <Search className="size-5" />
              </InputGroupText>
            </InputGroupAddon>
            <InputGroupInput
              type="text"
              // التسمية للقارئات الشاشة: العنصر بلا <label> مرئي، والـ placeholder
              // وحده لا يكفي — وهي مخالفة WCAG معروفة لأن النص يختفي عند الكتابة.
              aria-label="ابحث في المستندات"
              placeholder="ابحث عن مستند أو تصنيف..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
            />
          </InputGroup>
          <Button variant="outline" className="bg-slate-900 border-slate-800 text-slate-300 hover:bg-slate-800 hover:text-white shrink-0">
            <Filter className="w-5 h-5 ml-2" />
            تصفية
          </Button>
        </div>
      </div>

      {/* جدول المستندات */}
      <Card className="bg-slate-900 border-slate-800 shadow-xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-right border-collapse">
            <thead>
              <tr className="bg-slate-950/50 border-b border-slate-800 text-slate-400">
                <th className="p-4 font-medium">اسم المستند</th>
                <th className="p-4 font-medium">التصنيف</th>
                <th className="p-4 font-medium">تاريخ الإنشاء</th>
                <th className="p-4 font-medium">الحالة</th>
                <th className="p-4 font-medium text-left">الإجراءات</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800">
              {filteredDocs.length > 0 ? (
                filteredDocs.map((doc) => (
                  <tr key={doc.id} className="hover:bg-slate-800/50 transition-colors group">
                    <td className="p-4">
                      <div className="flex items-center gap-3">
                        <div className="p-2 bg-slate-950 rounded-md border border-slate-800 group-hover:border-amber-500/50 transition-colors">
                          <FileText className="w-5 h-5 text-amber-500" />
                        </div>
                        <span className="font-medium text-slate-200">{doc.title}</span>
                      </div>
                    </td>
                    <td className="p-4 text-slate-400">{doc.type}</td>
                    <td className="p-4 text-slate-400 font-mono text-sm">{doc.date}</td>
                    <td className="p-4">
                      <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border ${
                        doc.status === 'مكتمل' 
                          ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' 
                          : doc.status === 'مسودة'
                          ? 'bg-slate-500/10 text-slate-400 border-slate-500/20'
                          : 'bg-amber-500/10 text-amber-400 border-amber-500/20'
                      }`}>
                        {doc.status}
                      </span>
                    </td>
                    <td className="p-4 text-left">
                      <div className="flex items-center justify-end gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                        <button className="p-2 text-slate-400 hover:text-white hover:bg-slate-700 rounded-md transition-colors" title="عرض">
                          <Eye className="w-4 h-4" />
                        </button>
                        <button className="p-2 text-slate-400 hover:text-white hover:bg-slate-700 rounded-md transition-colors" title="تحميل">
                          <Download className="w-4 h-4" />
                        </button>
                        <button className="p-2 text-slate-400 hover:text-red-400 hover:bg-slate-700 rounded-md transition-colors" title="حذف">
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                      <div className="flex items-center justify-end group-hover:hidden text-slate-600">
                        <MoreHorizontal className="w-5 h-5" />
                      </div>
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={5} className="p-8 text-center text-slate-500">
                    لم يتم العثور على مستندات تطابق بحثك.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}