"use client";

/**
 * لوحة القيادة — أرقام حقيقية من قاعدة البيانات.
 * ============================================================================
 * ⚠️ ما كان هنا قبل هذا التغيير:
 *
 *   «إجمالي المستندات ١٢٤٨»        ← رقم مكتوب بخط اليد
 *   «الأسانيد المستخرجة ٨٥٣٠»      ← رقم مكتوب بخط اليد، **ووصفه خطأ واقعي**:
 *                                    «من أرشيف Qdrant» والأرشيف في Supabase/pgvector
 *   «متوسط وقت الصياغة ١٤ ثانية»   ← **لا يمكن حسابه**: لا شيء في المشروع يقيس الزمن
 *   «حالة السرب — Gemini 3.8 Flash» ← «السرب» مكتبة `smart_office.py` **غير مستخدَمة
 *                                    في المنتج**، واسم النموذج غير صحيح
 *   الرسم البياني وقائمة المستندات  ← مصفوفتان مكتوبتان في الملف
 *
 * فالأرقام كلها لا أصل لها. وهذه الصفحة تعرض الآن:
 *   • مستندات الأرشيف ومقاطعه — من `archive_overview()`
 *   • التصحيحات المحفوظة       — من `GET /revisions/stats` (المادة الخام للأسلوب)
 *   • حالة الخادم              — من `GET /health` فعلاً
 *
 * ⚠️ و«متوسط وقت الصياغة» **حُذف ولم يُستبدل برقم مثله**: لا يوجد ما يقيسه.
 *    فإبقاؤه بقيمة مخترعة أسوأ من حذفه.
 */

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { FileText, Layers, ClipboardCheck, Activity } from "lucide-react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { DataNotice, MetricValue } from "@/components/data-notice";

const API_URL = "/api";

/**
 * ما يُعرض حين تكون دوالّ الأرشيف غير منشأة بعد.
 *
 * ولا نُدرج الدوالّ كاملة هنا: هي نحو ثمانين سطراً في `schema.sql`، ونسخة
 * ثانية منها في الواجهة **تنحرف عن الأصل** — وهو العطب الذي تكرّر في هذا
 * المشروع أكثر من غيره. فنُحيل إلى المصدر الواحد.
 */
const SELECT_ARCHIVE_SQL = `-- افتح schema.sql وانسخ القسم ١١ كاملاً
--   archive_overview()  ·  archive_documents(...)
-- ثم نفّذه في Supabase ← SQL Editor

-- وللتحقّق بعد التنفيذ (يجب أن يعيد خمسة صفوف):
select * from archive_overview();`;

/** عائلة واحدة من الأرشيف — مفتاح آلي ووسم عربي معاً. */
type Family = {
  key: string;
  label: string;
  documents: number;
  chunks: number;
  latest_added: string | null;
};

type Overview = { documents: number; chunks: number; families: Family[] };

type ArchiveDocument = {
  document_name: string;
  document_type: string;
  family: string;
  family_label: string;
  chunks: number;
  added_at: string | null;
};

type DocumentsPayload = {
  count: number;
  limit: number;
  truncated: boolean;
  documents: ArchiveDocument[];
};

type RevisionStats = {
  count: number;
  median_edit_ratio: number;
  target: number;
  progress_percent: number;
};

type Health = {
  status: string;
  version: string;
  tools: string[];
  auth_required: boolean;
  citation_verification: boolean;
  revision_capture: boolean;
};

/** رسالة خطأ موحّدة من ردّ الخادم — تُعرض كما هي لأنها تحمل الخطوة المطلوبة. */
async function failureOf(response: Response): Promise<string> {
  const text = await response.text();
  try {
    const parsed = JSON.parse(text) as { detail?: string };
    return parsed.detail || `HTTP ${response.status}`;
  } catch {
    return text.slice(0, 300) || `HTTP ${response.status}`;
  }
}

const SQL_HINT = "نفّذ القسم ١١ من schema.sql في Supabase SQL Editor";

function whenLabel(iso: string | null): string {
  if (!iso) return "—";
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "—";
  const minutes = Math.floor((Date.now() - then) / 60000);
  if (minutes < 1) return "الآن";
  if (minutes < 60) return `منذ ${minutes} دقيقة`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `منذ ${hours} ساعة`;
  const days = Math.floor(hours / 24);
  return days === 1 ? "أمس" : `منذ ${days} يوماً`;
}

export default function Dashboard() {
  const [overview, setOverview] = useState<Overview | null>(null);
  const [recent, setRecent] = useState<DocumentsPayload | null>(null);
  const [revisions, setRevisions] = useState<RevisionStats | null>(null);
  const [health, setHealth] = useState<Health | null>(null);

  const [loading, setLoading] = useState(true);
  const [archiveError, setArchiveError] = useState("");
  const [revisionsError, setRevisionsError] = useState("");
  const [healthError, setHealthError] = useState("");

  useEffect(() => {
    let alive = true;

    const load = async () => {
      /*
       * `allSettled` لا `all`: فلو كان جدول التصحيحات غير منشأ (القسم ١٠)، لا
       * يجوز أن تُفرغ الصفحة كلها. كل بطاقة تُخطئ وحدها.
       */
      const [overviewResult, recentResult, revisionsResult, healthResult] =
        await Promise.allSettled([
          fetch(`${API_URL}/archive/overview`),
          fetch(`${API_URL}/archive/documents?limit=5`),
          fetch(`${API_URL}/revisions/stats`),
          fetch(`${API_URL}/health`),
        ]);

      if (!alive) return;

      if (overviewResult.status === "fulfilled" && overviewResult.value.ok) {
        setOverview((await overviewResult.value.json()) as Overview);
      } else if (overviewResult.status === "fulfilled") {
        setArchiveError(await failureOf(overviewResult.value));
      } else {
        setArchiveError("تعذّر الوصول إلى الخادم.");
      }

      if (recentResult.status === "fulfilled" && recentResult.value.ok) {
        setRecent((await recentResult.value.json()) as DocumentsPayload);
      }

      if (revisionsResult.status === "fulfilled" && revisionsResult.value.ok) {
        setRevisions((await revisionsResult.value.json()) as RevisionStats);
      } else if (revisionsResult.status === "fulfilled") {
        setRevisionsError(await failureOf(revisionsResult.value));
      } else {
        setRevisionsError("تعذّر الوصول إلى الخادم.");
      }

      if (healthResult.status === "fulfilled" && healthResult.value.ok) {
        setHealth((await healthResult.value.json()) as Health);
      } else {
        setHealthError("الخادم لا يستجيب.");
      }

      setLoading(false);
    };

    void load();
    return () => {
      alive = false;
    };
  }, []);

  const families = overview?.families ?? [];
  const chartData = families.map((item) => ({ name: item.label, المقاطع: item.chunks }));
  const archiveIsEmpty = !loading && !archiveError && (overview?.chunks ?? 0) === 0;

  return (
    <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-700 ease-out">
      {archiveError && (
        <DataNotice
          tone="error"
          title="تعذّر قراءة الأرشيف"
          detail={archiveError}
          action={archiveError.includes("القسم ١١") ? SELECT_ARCHIVE_SQL : undefined}
        />
      )}

      {/* البطاقات العلوية — كلها من بيانات حقيقية */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <Card className="bg-slate-900 border-slate-800 text-white">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-lg font-medium text-slate-300">مستندات الأرشيف</CardTitle>
            <FileText className="w-5 h-5 text-amber-500" />
          </CardHeader>
          <CardContent>
            <MetricValue value={overview?.documents ?? 0} loading={loading} failed={!!archiveError} />
            <p className="text-sm text-slate-400 mt-2">
              {archiveError ? "غير متاح" : `في ${families.length || 5} عائلات قانونية`}
            </p>
          </CardContent>
        </Card>

        <Card className="bg-slate-900 border-slate-800 text-white">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-lg font-medium text-slate-300">المقاطع المفهرسة</CardTitle>
            <Layers className="w-5 h-5 text-amber-500" />
          </CardHeader>
          <CardContent>
            <MetricValue value={overview?.chunks ?? 0} loading={loading} failed={!!archiveError} />
            <p className="text-sm text-slate-400 mt-2">Supabase · pgvector · ١٠٢٤ بُعداً</p>
          </CardContent>
        </Card>

        <Card className="bg-slate-900 border-slate-800 text-white">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-lg font-medium text-slate-300">التصحيحات المحفوظة</CardTitle>
            <ClipboardCheck className="w-5 h-5 text-amber-500" />
          </CardHeader>
          <CardContent>
            <MetricValue
              value={revisions?.count ?? 0}
              loading={loading}
              failed={!!revisionsError}
            />
            <p className="text-sm text-slate-400 mt-2">
              {revisionsError
                ? revisionsError.slice(0, 60)
                : revisions
                  ? `${revisions.progress_percent}٪ من هدف ${revisions.target} زوجاً`
                  : "—"}
            </p>
          </CardContent>
        </Card>

        <Card className="bg-slate-900 border-slate-800 text-white">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-lg font-medium text-slate-300">حالة الخادم</CardTitle>
            <Activity className={`w-5 h-5 ${healthError ? "text-red-500" : "text-emerald-500"}`} />
          </CardHeader>
          <CardContent>
            <div className={`text-2xl font-bold ${healthError ? "text-red-400" : "text-emerald-500"}`}>
              {loading ? "—" : healthError ? "غير متصل" : "متصل وجاهز"}
            </div>
            <p className="text-sm text-slate-400 mt-2">
              {health
                ? [
                    `${health.tools.length} أدوات`,
                    health.citation_verification ? "تحقّق الأسانيد مُفعَّل" : "التحقّق معطّل",
                    health.auth_required ? "المصادقة مُفعَّلة" : "⚠️ بلا مصادقة",
                  ].join(" · ")
                : "—"}
            </p>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* الرسم البياني — توزيع الأرشيف الحقيقي على العائلات */}
        <Card className="col-span-2 bg-slate-900 border-slate-800 text-white">
          <CardHeader>
            <CardTitle className="text-xl">توزيع الأرشيف على العائلات</CardTitle>
          </CardHeader>
          <CardContent className="h-[350px]">
            {archiveIsEmpty ? (
              <div className="flex h-full items-center justify-center">
                <p className="text-sm text-slate-500">
                  الأرشيف فارغ — ارفع مستنداتك عبر أدوات الاستيعاب ليظهر توزيعها هنا.
                </p>
              </div>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                {/* أعمدة أفقية: أوصاف العائلات عربية طويلة، والمحور الرأسي يقرؤها */}
                <BarChart
                  data={chartData}
                  layout="vertical"
                  margin={{ top: 10, right: 30, left: 10, bottom: 10 }}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" horizontal={false} />
                  <XAxis type="number" stroke="#64748b" tick={{ fill: "#64748b" }} />
                  <YAxis
                    type="category"
                    dataKey="name"
                    width={150}
                    stroke="#64748b"
                    tick={{ fill: "#94a3b8", fontSize: 13 }}
                  />
                  <Tooltip
                    cursor={{ fill: "#1e293b" }}
                    contentStyle={{
                      backgroundColor: "#0f172a",
                      borderColor: "#1e293b",
                      borderRadius: "8px",
                      color: "#fff",
                    }}
                  />
                  <Bar dataKey="المقاطع" fill="#f59e0b" radius={[0, 4, 4, 0]} barSize={26} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>

        {/* أحدث ما أُضيف للأرشيف */}
        <Card className="bg-slate-900 border-slate-800 text-white">
          <CardHeader>
            <CardTitle className="text-xl">أحدث ما أُضيف للأرشيف</CardTitle>
          </CardHeader>
          <CardContent>
            {loading ? (
              <p className="text-sm text-slate-500">…</p>
            ) : (recent?.documents.length ?? 0) === 0 ? (
              <p className="text-sm text-slate-500">لا مستندات بعد.</p>
            ) : (
              <div className="space-y-5">
                {recent?.documents.map((doc, index) => (
                  <div
                    key={`${doc.document_name}-${index}`}
                    className="flex items-start justify-between gap-3 border-b border-slate-800 pb-4 last:border-0 last:pb-0"
                  >
                    <div className="space-y-1 min-w-0">
                      <p className="text-sm font-medium leading-snug text-slate-200 break-words">
                        {doc.document_name}
                      </p>
                      <p className="text-xs text-slate-500">
                        {doc.family_label || doc.document_type || "بلا تصنيف"} · {doc.chunks} مقطعاً
                      </p>
                    </div>
                    <span className="shrink-0 text-xs text-slate-500">
                      {whenLabel(doc.added_at)}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
