"""
التدقيق اللغوي — فحص حتمي لصياغة المستند النهائي.
=============================================================================

لماذا هذا الملف
---------------
في `smart_office.py` يوجد مدقّق لغوي اسمه **«سيبويه المُكشّر»** مهمّته «ضبط
الصياغة». لكن ذلك الملف **سكربت مستقلّ لا يستدعيه `/generate`**، فسيبويه لم
يراجع مستنداً واحداً أنتجه الموقع.

وهذا الملف يمنحه عملاً حقيقياً في المسار الفعلي — على النمط نفسه الذي يقوم
عليه `citations.py`:

> **النموذج يروي، والخادم يُقرّر.** وكل ما يمكن فحصه بقاعدة ثابتة لا يُترَك
> لنموذج يقرّر.

ما يفحصه — كلّه عيوب وقعت فعلاً أو تُفسد المستند
------------------------------------------------
**١) مخلفات Markdown — وهي عيب وقع في هذا المشروع بالذات.**
   ظهرت في مستند مولَّد علامات حرفية: ``** لائحة دعوى تجارية **`` و``### موضوع
   الدعوى:``. والموجّه يمنعها صراحةً، والمستند يُنسخ إلى Word، فتظهر العلامات
   في المستند القانوني إن لم يلتقطها أحد.

**٢) افتتاح حواري.** الموجّه يمنع المقدمات، لكن النموذج يبدأ أحياناً بـ
   «بالتأكيد، إليك المستند…». وفي مستند قانوني هذا عيب لا ذوق.

**٣) حقل لم يُملأ.** قالب فيه ``[اسم المدعي]`` أو ``XXX`` أو شرطات سفلية
   فارغة. وهو **أخطرها**: مستند قانوني يخرج وفي مكان اسم الطرف فراغ.

**٤) كلمات لاتينية داخل نصّ عربي.** غالباً أسماء شركات أو مصطلحات تقنية
   مشروعة، فتأتي **ملاحظة لا خطأً** — تُعرَض ليقرّر المحامي.

**٥) أسطر مكرّرة حرفياً.** أثر لصق مزدوج.

⚠️ وحدّ صريح
-----------
هذا فحص **شكلي**: يمنع عيوب الصياغة والتحرير، ولا يحكم على القيمة القانونية
لجملة. وقد يكون مستند سليم التنسيق تماماً وهو خطأ قانوناً. ولذلك هو منفصل عن
`citations.py` ولا يُغني عنه.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional, Sequence

#: «سيبويه» يشترط أن يبدأ المستند بالوقائع أو بالديباجة، لا بمجاملة.
_PREAMBLE = re.compile(
    r"^(?:بالتأكيد|بكل تأكيد|بالطبع|حسناً|حسنا|إليك|اليك|تفضل|هذا هو|هذه هي|"
    r"كما طلبت|بناءً على طلبك|بناء على طلبك|سأقوم|سوف أقوم|فيما يلي|أدناه|"
    r"يمكنني|إليك المستند|تفضل المستند)\b"
)

#: حقل قالب لم يُملأ. ``X{3,}`` و``_{3,}`` مقصودان بعدّاد لا بنجمة.
_PLACEHOLDER = re.compile(r"\[[^\]\n]{0,60}\]|\{\{[^}\n]{0,60}\}\}|_{3,}|X{3,}")

#: تسلسل لاتيني — ملاحظة لا خطأ.
#:
#: يقبض على **التسلسل كاملاً** لا كلمةً كلمة: «Alpha Trading LLC» ملاحظة واحدة
#: لا ثلاث. وثلاث ملاحظات لاسم شركة واحدة ضجيج يُغرق التقرير فيُتجاهَل.
_LATIN = re.compile(r"[A-Za-z]{3,}(?:\s+[A-Za-z]{2,})*")

#: مخلفات Markdown سطراً سطراً.
#:
#: ⚠️ لاحظ عدم التماثل بين `**` و`__`، وهو مقصود:
#:   * `**` وحدها تُوسَم دائماً — ولا موضع شرعي لها في نصّ قانوني عربي. والعيب
#:     الذي وقع فعلاً كان ``** لائحة دعوى تجارية **``، وفيه `**` يليها فراغ.
#:     فلو شرطنا محتوى بعدها لفوّتنا العيب الواقع.
#:   * أما `__` فتشترط محتوى بعدها (`(?=[^_\s])`) لأن `___` **فراغ لملء**
#:     مشروع في قالب، لا تسميكاً. ولولا هذا الشرط لصُنّف الفراغ خطأ Markdown
#:     بدل «حقل لم يُملأ» — وهو التصنيف الصحيح والأخطر.
_MARKDOWN_RULES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\*\*"), "تسميك Markdown (**)"),
    (re.compile(r"__(?=[^_\s])"), "تسميك Markdown (__)"),
    (re.compile(r"^\s{0,3}#{1,6}\s"), "وسم عنوان (#)"),
    (re.compile(r"^\s{0,3}>\s"), "علامة اقتباس (> في بداية السطر)"),
    (re.compile(r"^\s*[-*_]{3,}\s*$"), "خط أفقي (---)"),
    (re.compile(r"^\s*[-*+]\s+\S"), "تعداد بنجمة أو شرطة"),
    (re.compile(r"^\s*\|.*\|\s*$"), "صفّ جدول (|)"),
)

#: أقلّ طول لسطر يُعتدّ به في فحص التكرار — الأسطر القصيرة تتكرّر بحقّ.
_MIN_REPEAT_LINE = 40


@dataclass(frozen=True)
class LanguageFinding:
    """ملاحظة واحدة من سيبويه."""

    kind: str          # markdown | preamble | placeholder | latin | repetition
    severity: str      # error | notice
    message: str
    sample: str
    line: Optional[int] = None


@dataclass
class LanguageReport:
    """حصيلة التدقيق اللغوي كاملة."""

    findings: list[LanguageFinding] = field(default_factory=list)

    @property
    def errors(self) -> list[LanguageFinding]:
        return [item for item in self.findings if item.severity == "error"]

    @property
    def notices(self) -> list[LanguageFinding]:
        return [item for item in self.findings if item.severity == "notice"]

    @property
    def clean(self) -> bool:
        """هل خرج المستند بلا عيب شكلي؟"""
        return not self.errors

    def summary(self) -> str:
        """سطر عربي موجز للعرض."""
        if not self.findings:
            return "الصياغة سليمة — لا ملاحظة."
        if self.clean:
            return f"الصياغة سليمة · {len(self.notices)} ملاحظة للعلم."
        return (
            f"{len(self.errors)} عيب في الصياغة"
            + (f" · {len(self.notices)} ملاحظة" if self.notices else "")
        )


def _excerpt(text: str, match: re.Match) -> str:
    """مقتطف قصير حول موضع الملاحظة — للعرض لا للتخزين."""
    start = max(0, match.start() - 20)
    end = min(len(text), match.end() + 20)
    return ("…" if start else "") + text[start:end].replace("\n", " ").strip() + (
        "…" if end < len(text) else ""
    )


def _check_markdown(lines: Sequence[str]) -> list[LanguageFinding]:
    found: list[LanguageFinding] = []
    seen: set[str] = set()
    for number, line in enumerate(lines, 1):
        for pattern, label in _MARKDOWN_RULES:
            match = pattern.search(line)
            if match and label not in seen:
                seen.add(label)
                found.append(
                    LanguageFinding(
                        kind="markdown",
                        severity="error",
                        message=f"مخلّف Markdown: {label} — يُفسد النسخ إلى Word.",
                        sample=line.strip()[:70],
                        line=number,
                    )
                )
    return found


def _check_preamble(lines: Sequence[str]) -> list[LanguageFinding]:
    """الافتتاح الحواري — يُفحص أول سطر غير فارغ فقط."""
    for number, line in enumerate(lines, 1):
        stripped = line.strip().lstrip("#>*-• ").strip()
        if not stripped:
            continue
        match = _PREAMBLE.match(stripped)
        if match:
            return [
                LanguageFinding(
                    kind="preamble",
                    severity="error",
                    message=(
                        "افتتاح حواري — الموجّه يمنع المقدمات، والمستند يبدأ "
                        "بالوقائع أو بالديباجة."
                    ),
                    sample=stripped[:70],
                    line=number,
                )
            ]
        return []  # أول سطر فعليّ ليس افتتاحاً — فلا حاجة لفحص ما بعده
    return []


def _check_placeholders(text: str) -> list[LanguageFinding]:
    return [
        LanguageFinding(
            kind="placeholder",
            severity="error",
            message="حقل قالب لم يُملأ — لا يجوز أن يخرج مستند بمكان فارغ.",
            sample=match.group(0)[:70],
        )
        for match in _PLACEHOLDER.finditer(text)
    ]


def _check_latin(text: str) -> list[LanguageFinding]:
    """ملاحظة فقط: أسماء الشركات والمصطلحات التقنية مشروعة."""
    return [
        LanguageFinding(
            kind="latin",
            severity="notice",
            message="كلمة لاتينية داخل النصّ العربي — تحقّق أنها اسم علم لا خطأ.",
            sample=match.group(0)[:70],
        )
        for match in _LATIN.finditer(text)
    ]


def _check_repetition(lines: Sequence[str]) -> list[LanguageFinding]:
    counts: dict[str, int] = {}
    for line in lines:
        key = line.strip()
        if len(key) >= _MIN_REPEAT_LINE:
            counts[key] = counts.get(key, 0) + 1
    return [
        LanguageFinding(
            kind="repetition",
            severity="notice",
            message=f"سطر مكرّر {count} مرات — أثر لصق مزدوج غالباً.",
            sample=key[:70],
        )
        for key, count in counts.items()
        if count > 1
    ]


def audit_language(document: Optional[str]) -> LanguageReport:
    """
    يفحص صياغة المستند فحصاً حتمياً بلا نموذج ولا شبكة.

    الترتيب مقصود: الأخطاء أولاً لأنها تمنع التسليم، ثم الملاحظات للعلم.

    >>> report = audit_language("البند الأول: يلتزم الطرف الثاني بالسداد.")
    >>> report.clean
    True
    >>> audit_language("** لائحة دعوى **").errors[0].kind
    'markdown'
    """
    report = LanguageReport()
    if not document or not document.strip():
        return report

    lines = document.splitlines()

    report.findings.extend(_check_markdown(lines))
    report.findings.extend(_check_preamble(lines))
    report.findings.extend(_check_placeholders(document))
    # فحص اللاتينية على النصّ **بعد** إزالة حقول القالب: وإلا أُبلغ عن `XXX`
    # مرتين — مرة «حقل لم يُملأ» ومرة «كلمة لاتينية». والتصنيف الأول هو
    # الصحيح، والثاني ضجيج.
    report.findings.extend(_check_latin(_PLACEHOLDER.sub(" ", document)))
    report.findings.extend(_check_repetition(lines))

    # الأخطاء أولاً، ثم الملاحظات — وكلٌّ بترتيبه الأصلي
    report.findings.sort(key=lambda item: 0 if item.severity == "error" else 1)
    return report


def summarize(report: LanguageReport) -> dict:
    """
    يحوّل التقرير إلى قاموس صالح للبثّ كـ JSON.

    المقتطفات مقطوعة عند 70 محرفاً: الغرض أن يرى المحامي موضع العيب لا أن
    تُبَثّ المسودّة كاملة داخل الإشعار.
    """
    return {
        "summary": report.summary(),
        "clean": report.clean,
        "error_count": len(report.errors),
        "notice_count": len(report.notices),
        "findings": [
            {
                "kind": item.kind,
                "severity": item.severity,
                "message": item.message,
                "sample": item.sample,
                "line": item.line,
            }
            for item in report.findings
        ],
    }
