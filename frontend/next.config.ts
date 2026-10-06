import type { NextConfig } from "next";

/**
 * إعداد Next.js — وسبب وجود سطر واحد فيه.
 * ============================================================================
 * ⚠️ `turbopackFileSystemCacheForDev: false` — **وهذا إصلاح عطب حقيقي لا تفضيل**.
 *
 * الافتراضي في Next 16 هو **`true`**: يخزّن Turbopack عمله بين تشغيلات
 * `next dev` في `.next/dev/cache/turbopack`. والوثيقة الرسمية:
 *   https://nextjs.org/docs/app/api-reference/config/next-config-js/turbopackFileSystemCache
 *
 * ⚠️ **والمخزون ينمو بلا سقف ولا تنقية.** وقد امتلأ القرص فعلاً على Codespaces:
 *
 *     failed to write to `…/.next/dev/cache/turbopack/v16.3.6-…/00000184.sst`
 *     No space left on device (os error 28)
 *
 * والرقم `00000184` يعني **مئات ملفات المخزون** — وكل جلسة تطوير تضيف إليها،
 * حتى توقّف البناء ولم تعد الصفحة تُفتح.
 *
 * ⚠️ **والكلفة أقلّ من الفائدة بكثير:** هذا تطبيق بتسع صفحات، وTurbopack يعلن
 *    `✓ Ready in 456ms`. فإعادة البناء من الصفر كل مرة **أرخص من أن يمتلئ
 *    القرص في منتصف العمل**. وقيمة المخزون الحقيقية في المشاريع الضخمة.
 *
 * ⚠️ ولماذا لم أُعطّل مخزون **البناء** (`turbopackFileSystemCacheForBuild`)؟
 *    لأنه في `.next/cache`، وVercel **تحفظه بين عمليات النشر** فتُسرّعها فعلاً.
 *    والعطب وقع في مخزون **التطوير** وحده — فلا يُعطَّل ما ينفع.
 *
 * ⚠️ وإن أردت تفعيله يوماً: اجعله `true`، ونظّف عند الحاجة بـ
 *    `./scripts/reclaim-space.sh`.
 * ============================================================================
 */
const nextConfig: NextConfig = {
  experimental: {
    // ⚠️ مُعطَّل عن قصد — انظر الشرح أعلاه. ولا تُفعّله بلا سبب.
    turbopackFileSystemCacheForDev: false,
  },
};

export default nextConfig;
