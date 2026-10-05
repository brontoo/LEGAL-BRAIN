"use client";

/**
 * الأرشيف والمكتبة — المستندات الحقيقية في قاعدة المعرفة.
 * ============================================================================
 * ⚠️ ما كان هنا قبل هذا التغيير: سبعة مستندات **مكتوبة في الملف** بأسماء
 * وتواريخ (٢٠٢٦-٠٩-٢٥) وحالات (مكتمل · قيد المراجعة · مسودة).
 *
 * ⚠️ والحالات كانت الخطأ الأكبر: «مكتمل» و«قيد المراجعة» أوصاف **مستندات
 *    مصوغة**، وهذا الجدول يعرض **مصادر مستوردة** للأرشيف. والمصدر المستورد
 *    لا يكون «قيد المراجعة» — هو مفهرس أو غير مفهرس.
 *
 * ⚠️ والأزرار الثلاثة كانت **لا تفعل شيئاً**: عرضٌ وتحميلٌ وحذف. وزرّ لا يعمل
 *    أسوأ من غيابه، لأنه يوعد بقدرة غير موجودة. فحُذفت، وبقي ما يعمل فعلاً:
 *    البحث والتصفية — وكلاهما يجري في قاعدة البيانات لا في المتصفح.
 */

import { useCallback, useEffect, useState } from "react";
import { Search, Filter, FileText, Layers } from "lucide-react";
import { Card } from "@/components/ui/card";
import {
  InputGroup,
  InputGroupAddon,
  InputGroupInput,
  InputGroupText,
} from "@/components/ui/input-group";
import { DataNotice } from "@/components/data-notice";

const API_URL = "/api";
const PAGE_SIZE = 200;

type Family = { key: string; label: string; documents: number; chunks: number };

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

export default function Library() {
  const [search, setSearch] = useState("");
  const [family, setFamily] = useState("");
  const [families, setFamilies] = useState<Family[]>([]);
  const [payload, setPayload] = useState<DocumentsPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  /* العائلات تُجلب مرة واحدة لبناء قائمة التصفية — فلا تُكتب في الواجهة. */
  useEffect(() => {
    let alive = true;
    fetch(`${API_URL}/archive/overview`)
      .then((response) => (response.ok ? response.json() : Promise.reject(response)))
      .then((data: { families: Family[] }) => {
        if (alive) setFamilies(data.families);
      })
      .catch(() => {
        /* فشل القائمة لا يُسقط الجدول — التصفية تبقى بلا خيارات فقط */
      });
    return () => {
      alive = false;
    };
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    const params = new URLSearchParams({ limit: String(PAGE_SIZE) });
    if (search.trim()) params.set("search", search.trim());
    if (family) params.set("family", family);

    try {
      const response = await fetch(`${API_URL}/archive/documents?${params}`);
      if (!response.ok) {
        const text = await response.text();
        let detail = `HTTP ${response.status}`;
        try {
          detail = (JSON.parse(text) as { detail?: string }).detail || detail;
        } catch {
          detail = text.slice(0, 300) || detail;
        }
        throw new Error(detail);
      }
      setPayload((await response.json()) as DocumentsPayload);
    } catch (e) {
      setError(e instanceof Error ? e.message : "تعذّر قراءة الأرشيف.");
      setPayload(null);
    } finally {
      setLoading(false);
    }
  }, [search, family]);

  /*
   * البحث في قاعدة البيانات لا في المتصفح — ولذلك يُؤجَّل ٣٥٠ مللي ثانية.
   *
   * وكان البحث السابق في مصفوفة داخل الملف، وهو يعمل بلا تأجيل. أما الآن فكل
   * حرف يُنشئ طلباً إلى الخادم، والتأجيل يمنع عشرة طلبات عند كتابة كلمة.
   */
  useEffect(() => {
    const timer = setTimeout(() => void load(), 350);
    return () => clearTimeout(timer);
  }, [load]);

  const documents = payload?.documents ?? [];

  return (
    <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-700 ease-out">
      {/* الترويسة وشريط البحث */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div>
          <h1 className="text-3xl font-bold text-white tracking-tight">الأرشيف والمكتبة</h1>
          <p className="text-slate-400 mt-1">
            المستندات المفهرسة التي يستند إليها الفريق في الصياغة.
          </p>
        </div>

        <div className="flex w-full md:w-auto items-center gap-3">
          <InputGroup className="w-full md:w-80">
            <InputGroupAddon align="inline-start">
              <InputGroupText>
                <Search className="size-5" />
              </InputGroupText>
            </InputGroupAddon>
            <InputGroupInput
              type="text"
              aria-label="ابحث في المستندات"
              placeholder="ابحث باسم المستند أو تصنيفه..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </InputGroup>

          {/*
            القائمة `<select>` أصليّة، على النمط نفسه المستخدم في
            `app/workspace/page.tsx:636` — لا مكوّن `components/ui/select`.

            ⚠️ و`ui/select` **مبنيّ وغير مستخدَم في المشروع كله**. وتوجيه
            المشروع يفضّل استخدامه، ولكن تحويل واحدة من القائمتين دون الأخرى
            يُنشئ inconsistency، وتحويلهما معاً يحتاج بناءً حقيقياً للتأكّد من
            واجهة `@base-ui/react/select` (دلالة القيمة الفارغة، وشكل
            `onValueChange`) — وأنا لا أستطيع بناء الواجهة هنا.

            والقرار: تبقى القائمتان على النمط القائم حتى يُنقل الاثنان في خطوة
            واحدة مُتحقَّق منها.
          */}
          <div className="relative shrink-0">
            <Filter className="pointer-events-none absolute end-3 top-1/2 size-4 -translate-y-1/2 text-slate-500" />
            <select
              aria-label="تصفية بالعائلة"
              value={family}
              onChange={(e) => setFamily(e.target.value)}
              className="h-10 appearance-none rounded-lg border border-slate-800 bg-slate-900 pe-9 ps-3 text-sm text-slate-300 hover:bg-slate-800 focus:outline-none focus:ring-2 focus:ring-amber-500/40"
            >
              <option value="">كل العائلات</option>
              {families.map((item) => (
                <option key={item.key} value={item.key}>
                  {item.label} ({item.documents.toLocaleString("ar-AE")})
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {error && (
        <DataNotice
          tone="error"
          title="تعذّر قراءة الأرشيف"
          detail={error}
          action={
            error.includes("القسم ١١")
              ? "-- افتح schema.sql وانسخ القسم ١١ كاملاً ثم نفّذه في Supabase ← SQL Editor\nselect * from archive_overview();"
              : undefined
          }
        />
      )}

      {!error && loading && !payload && <DataNotice tone="loading" title="جاري قراءة الأرشيف..." />}

      {!error && payload && documents.length === 0 && (
        <DataNotice
          tone="empty"
          title={search || family ? "لا مستندات تطابق بحثك." : "الأرشيف فارغ."}
          detail={
            search || family
              ? "جرّب كلمة أخرى أو أزل التصفية."
              : "ارفع مستنداتك عبر أدوات الاستيعاب (ingesters) لتظهر هنا ويستند إليها الفريق."
          }
        />
      )}

      {!error && documents.length > 0 && (
        <>
          <Card className="bg-slate-900 border-slate-800 shadow-xl overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-right border-collapse">
                <thead>
                  <tr className="bg-slate-950/50 border-b border-slate-800 text-slate-400">
                    <th className="p-4 font-medium">اسم المستند</th>
                    <th className="p-4 font-medium">التصنيف</th>
                    <th className="p-4 font-medium">العائلة</th>
                    <th className="p-4 font-medium">المقاطع</th>
                    <th className="p-4 font-medium">أُضيف في</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800">
                  {documents.map((doc, index) => (
                    <tr
                      key={`${doc.family}-${doc.document_name}-${index}`}
                      className="hover:bg-slate-800/50 transition-colors group"
                    >
                      <td className="p-4">
                        <div className="flex items-center gap-3">
                          <div className="p-2 bg-slate-950 rounded-md border border-slate-800 group-hover:border-amber-500/50 transition-colors shrink-0">
                            <FileText className="w-5 h-5 text-amber-500" />
                          </div>
                          <span className="font-medium text-slate-200 break-words">
                            {doc.document_name || "بلا اسم"}
                          </span>
                        </div>
                      </td>
                      <td className="p-4 text-slate-400">{doc.document_type || "—"}</td>
                      <td className="p-4">
                        <span className="inline-flex items-center rounded-full border border-amber-500/20 bg-amber-500/10 px-2.5 py-0.5 text-xs font-medium text-amber-400">
                          {doc.family_label || "—"}
                        </span>
                      </td>
                      <td className="p-4 text-slate-400 font-mono text-sm">
                        <span className="inline-flex items-center gap-1.5">
                          <Layers className="w-3.5 h-3.5 text-slate-600" />
                          {doc.chunks.toLocaleString("ar-AE")}
                        </span>
                      </td>
                      <td className="p-4 text-slate-400 font-mono text-sm" dir="ltr">
                        {doc.added_at ? doc.added_at.slice(0, 10) : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>

          {/* ⚠️ القَصّ يُعلَن: بلا هذا السطر تُوهم الصفحة أن ما تراه هو الأرشيف كله */}
          <p className="text-xs text-slate-500">
            {payload?.truncated
              ? `تُعرض أول ${documents.length.toLocaleString("ar-AE")} مستنداً — يوجد غيرها. استخدم البحث أو التصفية.`
              : `${documents.length.toLocaleString("ar-AE")} مستنداً — الأرشيف كاملاً.`}
          </p>
        </>
      )}
    </div>
  );
}
