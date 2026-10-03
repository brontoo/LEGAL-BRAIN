import type { NextRequest } from "next/server";

/**
 * وسيط من الواجهة إلى خادم FastAPI.
 * ============================================================================
 * المتصفح يخاطب  /api/generate  على نفس أصل الواجهة، وهذا الملف يمرّر الطلب
 * إلى خادم FastAPI الحقيقي. ثلاث فوائد، وكلها جوهرية:
 *
 *   ١) رمز المصادقة (API_TOKEN) يُضاف **هنا على الخادم**، فلا يصل إلى المتصفح
 *      إطلاقاً. لو وضعناه في متغيّر NEXT_PUBLIC_ لرآه أي زائر في مصدر الصفحة،
 *      ولأصبحت المصادقة بلا معنى.
 *
 *   ٢) المتصفح يخاطب نفس الأصل، فتختفي مشكلة CORS كلياً — ولم تبقَ حاجة إلى
 *      ضبط ALLOWED_ORIGINS عند تغيير النطاق.
 *
 *   ٣) عنوان الخادم الحقيقي (BACKEND_URL) يبقى متغيّراً من جهة الخادم فقط،
 *      فيمكن أن يكون http://127.0.0.1:8000 داخل الحاوية بلا كشف منفذ عام.
 *
 * ⚠️ لا تضف بادئة NEXT_PUBLIC_ إلى BACKEND_URL ولا إلى API_TOKEN.
 */

const BACKEND_URL = (process.env.BACKEND_URL ?? "http://127.0.0.1:8000").replace(
  /\/+$/,
  ""
);

const API_TOKEN = process.env.API_TOKEN ?? "";

// بلا تخزين مؤقت: كل نداء يجب أن يصل إلى الخادم فعلاً
export const dynamic = "force-dynamic";

// بيئة Node صراحةً — البثّ الطويل وقراءة متغيّرات البيئة أوضح هنا
export const runtime = "nodejs";

type Context = { params: Promise<{ path: string[] }> };

async function proxy(request: NextRequest, context: Context): Promise<Response> {
  const { path } = await context.params;
  const target = `${BACKEND_URL}/${path.join("/")}`;

  const headers = new Headers();
  const contentType = request.headers.get("content-type");
  if (contentType) headers.set("content-type", contentType);
  headers.set("accept", request.headers.get("accept") ?? "*/*");

  // ← الرمز يُضاف على الخادم. لا يعبر إلى المتصفح أبداً.
  if (API_TOKEN) headers.set("authorization", `Bearer ${API_TOKEN}`);

  const hasBody = request.method !== "GET" && request.method !== "HEAD";

  let upstream: Response;
  try {
    upstream = await fetch(target, {
      method: request.method,
      headers,
      body: hasBody ? await request.text() : undefined,
      cache: "no-store",
      redirect: "manual",
    });
  } catch (error) {
    // الخادم متوقف أو العنوان خاطئ. نرجع نصاً عربياً واضحاً بدل أن يرى
    // المستخدم "Failed to fetch" الغامضة من المتصفح.
    const detail = error instanceof Error ? error.message : "خطأ غير معروف";
    return new Response(
      `تعذّر الوصول إلى خادم FastAPI على ${BACKEND_URL}\n` +
        `تأكد من أنه يعمل (./dev.sh يشغّل الاثنين معاً).\n\n${detail}`,
      { status: 502, headers: { "content-type": "text/plain; charset=utf-8" } }
    );
  }

  // نمرّر البثّ كما هو — بلا قراءة كاملة ولا تجميع — مع ترويسات تمنع أي
  // وسيط بيننا وبين المتصفح من حجب بثّ الـ SSE.
  return new Response(upstream.body, {
    status: upstream.status,
    headers: {
      "content-type": upstream.headers.get("content-type") ?? "application/json",
      "cache-control": "no-cache, no-transform",
      "x-accel-buffering": "no",
    },
  });
}

export const GET = proxy;
export const POST = proxy;
export const PUT = proxy;
export const PATCH = proxy;
export const DELETE = proxy;
