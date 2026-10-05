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

**٣) فراغ في المستند.** ``[..]`` أو ``[اسم المدعي]`` أو ``XXX`` أو شرطات سفلية.
   و**ملاحظة لا خطأً** — صحّحنا هذا التصنيف بعد تشغيل حقيقي، فراجع
   `_check_placeholders`: النموذج لا يعرف اسم الطرف، فتركه فراغاً هو الصواب.

**٤) كلمات لاتينية داخل نصّ عربي.** غالباً أسماء شركات أو مصطلحات تقنية
   مشروعة، فتأتي **ملاحظة لا خطأً** — تُعرَض ليقرّر المحامي.

**٥) أسطر مكرّرة حرفياً.** أثر لصق مزدوج.

⚠️ وحدّان صريحان
----------------
**الأول:** هذا فحص **شكلي**: يمنع عيوب الصياغة والتحرير، ولا يحكم على القيمة
القانونية لجملة. وقد يكون مستند سليم التنسيق تماماً وهو خطأ قانوناً. ولذلك هو
منفصل عن `citations.py` ولا يُغني عنه.

**والثاني، وهو الأهمّ:** **الخطأ يمنع التسليم، والملاحظة لا تمنعه.** والحدّ
بينهما **لا يُوضع بالحدس**. فأول تشغيل حقيقي وسم **أحد عشر سلوكاً صحيحاً**
كأخطاء حمراء (فراغات توقيع في إنذار)، ولو بقي ذلك لَما قرأ المحامي التقرير
بعد يومين — **ولضاع معه العيب الحقيقي حين يظهر**. فأداة تُنذر دائماً لا تُنذر
أبداً.
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

#: أقصى مسافة بين تكرارين ليُعدّا «لصقاً مزدوجاً». وما تباعد أكثر فبنية مستند.
_REPEAT_DISTANCE = 3


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


def _group_matches(pattern: re.Pattern[str], text: str) -> list[tuple[str, int, int]]:
    """
    يجمع المطابقات المتطابقة: (القيمة، عددها، رقم سطر أول ظهور).

    ⚠️ ولماذا التجميع؟ لأن أول تشغيل حقيقي أنتج **أحد عشر خطأً متطابقاً** كلها
    `[..]` — فراغات توقيع مشروعة في إنذار. فصار التقرير جداراً أحمر لا يُقرأ،
    **والضجيج يُغرِق العيب الحقيقي** حين يظهر.
    """
    found: dict[str, list[int]] = {}
    for match in pattern.finditer(text):
        line = text.count("\n", 0, match.start()) + 1
        found.setdefault(match.group(0), []).append(line)
    return [(value, len(lines), lines[0]) for value, lines in found.items()]


def _check_placeholders(text: str) -> list[LanguageFinding]:
    """
    الفراغات في المستند — **ملاحظة لا خطأً**.

    ⚠️ وهذا التصنيف صُحِّح بعد تشغيل حقيقي، وكان **خطأً في أوّل نسخة**.

    الحقيقة أن النموذج **لا يعرف اسم الشركة المُنذَرة ولا التوقيع** — فليسا في
    الموجز. وترك فراغٍ ليملأه المحامي هو **السلوك الصحيح**، لا سهواً. فوسمُه
    خطأً يمنع التسليم كان **وسمَ الصحّ بالخطأ**.

    ويبقى الفراغ جديراً بالتنبيه: مستند يخرج وفيه `[..]` لم يُملأ عيبٌ حقيقي.
    فهو **ملاحظة تذكّر المحامي**، لا خطأ يمنعه.

    وحدس التمييز الذي جرّبناه — «فراغ مجرّد (`[..]` · `___`) مشروع» مقابل
    «حقل مسمّى (`[اسم المدعي]`) خطأ» — **لم يصمد**: فالنموذج لا يعرف الاسم في
    الحالتين. والفرق ليس في الشكل بل في **هل كانت المعلومة متاحة في الموجز**،
    وذلك لا يعرفه هذا الملف. فلا يُدّعى.
    """
    return [
        LanguageFinding(
            kind="placeholder",
            severity="notice",
            message=(
                "فراغ في المستند — يملؤه المحامي قبل الإرسال"
                + (f" (تكرّر {count} مرّات)" if count > 1 else "")
            ),
            sample=value[:70],
            line=line,
        )
        for value, count, line in _group_matches(_PLACEHOLDER, text)
    ]


def _check_latin(text: str) -> list[LanguageFinding]:
    """ملاحظة فقط: أسماء الشركات والمصطلحات التقنية مشروعة."""
    return [
        LanguageFinding(
            kind="latin",
            severity="notice",
            message=(
                "كلمة لاتينية داخل النصّ العربي — تحقّق أنها اسم علم لا خطأ"
                + (f" (تكرّر {count} مرّات)" if count > 1 else "")
            ),
            sample=value[:70],
            line=line,
        )
        for value, count, line in _group_matches(_LATIN, text)
    ]


def _check_repetition(lines: Sequence[str]) -> list[LanguageFinding]:
    """
    الأسطر المكرّرة — **المتجاورة فقط**.

    ⚠️ و«المتجاورة» ليست تفصيلاً، بل هي **جوهر الفحص**. وسّعناها بعد تشغيل
    حقيقي ثانٍ، لأن أول نسخة عدّت **كل تكرار في المستند**.

    والمستند الذي كشفها إنذار قانوني فيه **كتلتا عنوان**: عنوان المنذَر إليه،
    وعنوان المنذِر. فتكرّرت فيه هذه الأسطر:

        العنوان: .......................
        رقم الهاتف: ....................
        البريد الإلكتروني: .............

    **مرّتين — وهو الصواب.** فالمستند القانوني يضع عنوان الطرفين، ولا سبيل
    لكتابته بغير التكرار. فوسمُه «أثر لصق مزدوج» كان **وسمَ الصيغة القانونية
    السليمة بالعطب**.

    والفرق أن عيب اللصق المزدوج حقيقته **تجاور**: السطر يُلصق مرّتين متتاليتين.
    والتكرار المتباعد في مستند منظّم **بنية لا عطب**. فالفحص الآن يقيس المسافة
    بين التكرارين، لا وجودهما.
    """
    positions: dict[str, list[int]] = {}
    for number, line in enumerate(lines, 1):
        key = line.strip()
        if len(key) >= _MIN_REPEAT_LINE:
            positions.setdefault(key, []).append(number)

    findings: list[LanguageFinding] = []
    for key, numbers in positions.items():
        nearby = [
            (first, second)
            for first, second in zip(numbers, numbers[1:])
            if second - first <= _REPEAT_DISTANCE
        ]
        if nearby:
            first, second = nearby[0]
            findings.append(
                LanguageFinding(
                    kind="repetition",
                    severity="notice",
                    message=(
                        f"سطر مكرّر في سطرين متجاورين (السطران {first} و{second}) "
                        "— أثر لصق مزدوج غالباً."
                    ),
                    sample=key[:70],
                    line=first,
                )
            )
    return findings


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
