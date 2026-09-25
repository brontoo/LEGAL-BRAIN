"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { FileText, Scale, Clock, Activity } from "lucide-react";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";

const activityData = [
  { name: "السبت", المستندات: 4 },
  { name: "الأحد", المستندات: 7 },
  { name: "الإثنين", المستندات: 5 },
  { name: "الثلاثاء", المستندات: 12 },
  { name: "الأربعاء", المستندات: 8 },
  { name: "الخميس", المستندات: 15 },
];

const recentDocs = [
  { id: 1, title: "لائحة دعوى مطالبة مالية - شركة أفق", type: "لائحة تجارية", date: "منذ ساعتين", status: "مكتمل" },
  { id: 2, title: "إنذار قانوني بالإخلاء للسداد", type: "إنذار عدلي", date: "منذ 5 ساعات", status: "مكتمل" },
  { id: 3, title: "وكالة خاصة ببيع عقار (دبي مارينا)", type: "توكيل رسمي", date: "أمس", status: "مكتمل" },
  { id: 4, title: "مذكرة دفاع عمالية - استئناف", type: "مذكرة دفاع", date: "أمس", status: "قيد المراجعة" },
];

export default function Dashboard() {
  return (
    <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-700 ease-out">
      
      {/* البطاقات العلوية */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <Card className="bg-slate-900 border-slate-800 text-white">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-lg font-medium text-slate-300">إجمالي المستندات</CardTitle>
            <FileText className="w-5 h-5 text-amber-500" />
          </CardHeader>
          <CardContent>
            <div className="text-4xl font-bold">1,248</div>
            <p className="text-sm text-emerald-400 mt-2">+12% عن الشهر الماضي</p>
          </CardContent>
        </Card>

        <Card className="bg-slate-900 border-slate-800 text-white">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-lg font-medium text-slate-300">الأسانيد المستخرجة</CardTitle>
            <Scale className="w-5 h-5 text-amber-500" />
          </CardHeader>
          <CardContent>
            <div className="text-4xl font-bold">8,530</div>
            <p className="text-sm text-slate-400 mt-2">من أرشيف Qdrant</p>
          </CardContent>
        </Card>

        <Card className="bg-slate-900 border-slate-800 text-white">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-lg font-medium text-slate-300">متوسط وقت الصياغة</CardTitle>
            <Clock className="w-5 h-5 text-amber-500" />
          </CardHeader>
          <CardContent>
            <div className="text-4xl font-bold">14<span className="text-xl text-slate-400 ml-1">ثانية</span></div>
            <p className="text-sm text-emerald-400 mt-2">أسرع بـ 4 ثوانٍ</p>
          </CardContent>
        </Card>

        <Card className="bg-slate-900 border-slate-800 text-white">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-lg font-medium text-slate-300">حالة السرب (Swarm)</CardTitle>
            <Activity className="w-5 h-5 text-emerald-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-emerald-500">متصل وجاهز</div>
            <p className="text-sm text-slate-400 mt-2">Gemini 3.8 Flash (Active)</p>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* الرسم البياني */}
        <Card className="col-span-2 bg-slate-900 border-slate-800 text-white">
          <CardHeader>
            <CardTitle className="text-xl">نشاط الصياغة الأسبوعي</CardTitle>
          </CardHeader>
          <CardContent className="h-[350px]">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={activityData} margin={{ top: 20, right: 30, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />
                <XAxis dataKey="name" stroke="#64748b" tick={{ fill: '#64748b', fontSize: 14 }} />
                <YAxis stroke="#64748b" tick={{ fill: '#64748b' }} />
                <Tooltip 
                  cursor={{ fill: '#1e293b' }}
                  contentStyle={{ backgroundColor: '#0f172a', borderColor: '#1e293b', borderRadius: '8px', color: '#fff' }}
                />
                <Bar dataKey="المستندات" fill="#f59e0b" radius={[4, 4, 0, 0]} barSize={40} />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        {/* قائمة أحدث المستندات */}
        <Card className="bg-slate-900 border-slate-800 text-white">
          <CardHeader>
            <CardTitle className="text-xl">أحدث المستندات</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-6">
              {recentDocs.map((doc) => (
                <div key={doc.id} className="flex items-start justify-between border-b border-slate-800 pb-4 last:border-0 last:pb-0">
                  <div className="space-y-1">
                    <p className="text-base font-medium leading-none text-slate-200">{doc.title}</p>
                    <p className="text-sm text-slate-400">{doc.type}</p>
                  </div>
                  <div className="flex flex-col items-end gap-1">
                    <span className="text-xs text-slate-500">{doc.date}</span>
                    <span className={`text-xs px-2 py-1 rounded-md ${doc.status === 'مكتمل' ? 'bg-emerald-500/10 text-emerald-500' : 'bg-amber-500/10 text-amber-500'}`}>
                      {doc.status}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}