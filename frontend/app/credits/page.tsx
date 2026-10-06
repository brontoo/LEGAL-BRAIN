import Link from "next/link";
import { ICON_CREDITS } from "@/components/engraved-icon";

/**
 * الإسناد والرخص.
 * ============================================================================
 * ⚠️ وهذه الصفحة **شرط ترخيص لا زيادة تجميلية**.
 *
 * أيقونات الواجهة من `game-icons.net` برخصة **CC BY 3.0**، ونصّ الرخصة في
 * `license.txt` بالمستودع يقول حرفياً:
 *
 *     Please, include a mention "Icons made by {author}" in your derivative work.
 *
 * فحذف هذه الصفحة، أو إزالة اسم فنّان منها، **مخالفة للترخيص** — وهي مسألة
 * تخصّ المكتب لا الكود. ولذلك تُقرأ القائمة من `engraved-icon.tsx` نفسه
 * (المصدر الواحد)، فلا تنحرف عمّا هو مستخدم فعلاً.
 *
 * والخطوط أيضاً برخصة حرة، ويُذكران هنا للأمانة نفسها.
 */
export default function Credits() {
  return (
    <div className="max-w-3xl space-y-8">
      <div>
        <h1 className="font-heading text-3xl text-slate-100">الإسناد والرخص</h1>
        <p className="mt-2 text-sm text-slate-500">
          ما يستخدمه هذا المكتب من أعمال غيره، ومن صنعه، وبأي رخصة.
        </p>
      </div>

      <section className="border border-slate-800 bg-slate-900 p-6">
        <h2 className="font-heading text-xl text-slate-100">أيقونات الواجهة</h2>
        <p className="mt-2 text-sm leading-relaxed text-slate-400">
          <span className="text-slate-200">Icons made by Lorc and Delapouite</span> —
          من <span dir="ltr">game-icons.net</span>، برخصة{" "}
          <span dir="ltr">Creative Commons Attribution 3.0 (CC BY 3.0)</span>.
        </p>

        <div className="mt-5 space-y-5">
          {ICON_CREDITS.map((entry) => (
            <div key={entry.author} className="border-s-2 border-s-amber-500/40 ps-4">
              <p className="text-sm text-slate-200">
                {entry.author}{" "}
                <a
                  href={entry.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  dir="ltr"
                  className="text-xs text-amber-500 underline underline-offset-2 hover:text-amber-400"
                >
                  {entry.url}
                </a>
              </p>
              <p className="mt-1 font-mono text-[11px] leading-relaxed text-slate-500" dir="ltr">
                {entry.icons.join(" · ")}
              </p>
            </div>
          ))}
        </div>
      </section>

      <section className="border border-slate-800 bg-slate-900 p-6">
        <h2 className="font-heading text-xl text-slate-100">الخطوط</h2>
        <ul className="mt-3 space-y-2 text-sm text-slate-400">
          <li>
            <span className="text-slate-200">Amiri</span> — إحياء خطّ مطبعة بولاق.
            برخصة <span dir="ltr">SIL Open Font License 1.1</span>.
          </li>
          <li>
            <span className="text-slate-200">Noto Kufi Arabic</span> — من مشروع Noto.
            برخصة <span dir="ltr">SIL Open Font License 1.1</span>.
          </li>
        </ul>
      </section>

      <Link
        href="/"
        className="inline-block border border-slate-800 px-4 py-2 text-sm text-slate-400 transition-colors hover:border-slate-700 hover:text-slate-200"
      >
        رجوع إلى لوحة القيادة
      </Link>
    </div>
  );
}
