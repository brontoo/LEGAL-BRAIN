/** Preview-only fixtures. No database, model, request-body reads or outbound calls. */
const stamp = "2026-01-15T09:00:00Z";
const families = [
  { key: "contracts", label: "عقود واتفاقيات" },
  { key: "drafts", label: "مذكرات ولوائح" },
  { key: "notices", label: "إنذارات" },
  { key: "poa", label: "وكالات" },
  { key: "documents", label: "تشريعات وأحكام" },
];
const names = ["عقد تعاون خيالي — للعرض فقط", "مذكرة خيالية — للعرض فقط", "إخطار خيالي — للعرض فقط", "وكالة خيالية — للعرض فقط", "سجل مرجعي خيالي — ليس تشريعاً"];
const chunks = families.flatMap((family, index) => [0, 1].map((part) => ({
  id: index * 2 + part + 1,
  document_name: names[index],
  document_type: family.label,
  family: family.key,
  family_label: family.label,
  content: part === 0
    ? "بيانات خيالية للمعاينة البصرية فقط. الأطراف: شركة المدار التجريبية وشركة الأفق التجريبية. لا يمثل هذا النص مستنداً حقيقياً أو رأياً قانونياً."
    : "مثال لفقرة ثانية توضح عرض مقاطع المستند وترتيبها في المكتبة. لم تُسترجع مصادر قانونية ولم يتم التحقق من أي سند أو نفاذ قانوني.",
  source_file: `fictional-preview-${index + 1}.txt`,
  chunk_index: part,
    created_at: `2026-01-${15 + index}T09:00:00Z`,
})));
const documents = families.map((family, index) => ({
  document_name: names[index], document_type: family.label, family: family.key,
  family_label: family.label, chunks: 2, added_at: `2026-01-${15 + index}T09:00:00Z`,
}));
const sample = "مسودّة خيالية — Demo Preview\n\nهذا مثال ثابت مكتوب مسبقاً لعرض واجهة الصياغة، وليس ناتج ذكاء اصطناعي أو رأياً قانونياً أو مستنداً معتمداً.\n\nالأطراف الخيالية\nشركة المدار التجريبية وشركة الأفق التجريبية.\n\nموضوع المثال\nتعاون افتراضي لعرض تنسيق الفقرات داخل المنصّة. لا تنشأ عن هذا المثال التزامات ولا يجوز استخدامه كوثيقة قانونية.\n\nلم يُجرَ بحث أو تدقيق أو تحقق من المصادر. لا يتم حفظ المدخلات أو إرسالها إلى Gemini أو Supabase.";

const headers = { "cache-control": "no-store", "x-legal-brain-mode": "demo" };
function json(value: unknown, status = 200) {
  return Response.json(value, { status, headers });
}

export function demoResponse(request: Request, path: string[]): Response {
  const route = path.join("/");
  const url = new URL(request.url);
  if (request.method === "GET" && route === "health") {
    return json({ status: "demo", backend_connected: false, fictional: true });
  }
  if (request.method === "GET" && route === "archive/overview") {
    return json({ families: families.map((f) => ({ ...f, documents: 1, chunks: 2, latest_added: stamp })), fictional: true });
  }
  if (request.method === "GET" && ["archive/documents", "archive/chunks"].includes(route)) {
    const key = route.endsWith("documents") ? "documents" : "chunks";
    const family = url.searchParams.get("family");
    const document = url.searchParams.get("document");
    const search = (url.searchParams.get("search") ?? "").slice(0, 200).toLowerCase();
    const requested = Number(url.searchParams.get("limit") ?? 200);
    const limit = Number.isFinite(requested) ? Math.max(1, Math.min(200, Math.floor(requested))) : 200;
    const source = key === "documents" ? documents : chunks;
    const rows = source.filter((row) => (!family || row.family === family) && (!document || row.document_name === document)
      && (!search || `${row.document_name} ${"content" in row ? row.content : ""}`.toLowerCase().includes(search)));
    return json({ [key]: rows.slice(0, limit), count: rows.length, limit, truncated: rows.length > limit, fictional: true });
  }
  // Fixed display samples only: never read, reflect, store or forward caller data.
  if (request.method === "POST" && route === "generate") {
    return new Response(`data: ${JSON.stringify({ type: "done", document: sample, demo: true })}\n\n`, {
      headers: { ...headers, "content-type": "text/event-stream; charset=utf-8", "x-accel-buffering": "no" },
    });
  }
  if (request.method === "POST" && route === "chat") {
    return json({ response: "Demo Preview — إجابة خيالية ثابتة لعرض الواجهة فقط. لم يُستدعَ نموذج ذكاء اصطناعي ولم يُجرَ بحث أو تحقق من المصادر. لاستكشاف العرض، افتح المكتبة الخيالية أو مساحة الصياغة. لا توجد مشورة قانونية في هذا المثال.",
      citations: { has_evidence: false, evidence_count: 0, verified: [], rejected: [], summary: "لم يُجرَ تحقق — مثال بصري فقط" }, demo: true });
  }
  // All writes, uploads, exports, revisions and unknown routes terminate here.
  return json({ detail: "Demo Preview: هذه العملية معطلة. لا يوجد اتصال بخدمات خلفية أو حفظ للبيانات." }, 403);
}
