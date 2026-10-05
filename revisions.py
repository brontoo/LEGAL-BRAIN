"""
جمع تصحيحات المحامي — المادة الخام لتقليد أسلوبه.
=============================================================================

المشكلة
-------
هدف هذا المشروع المُعلَن أن يكتب الوكيل **بأسلوب صاحب المكتب نفسه**. لكن
تقليد الأسلوب يحتاج مادة خام: أزواج (ما كتبه النموذج ← ما اعتمده المحامي
فعلاً). وكل تصحيح يُجريه المحامي **يضيع** إن لم يُسجَّل — فيبقى الأسلوب في
الموجّه تخميناً لا تعلّماً.

الحلّ
-----
يُحفظ كل زوج مع قياس واحد بسيط: **نسبة التعديل**.

وهي مفيدة لثلاثة أمور، لا لقياس الجودة وحده:

1. **مؤشّر جودة فوري.** مسودّة يُعدّلها المحامي ٨٠٪ أسوأ من أخرى يُعدّلها ٥٪ —
   وهذا رقم يظهر بعد كل مسودّة بلا استبيان ولا تخمين.
2. **ترتيب الأمثلة لاحقاً.** الأزواج الأكثر تعديلاً هي الأغنى بالدروس عن
   الأسلوب؛ فترتيبها بالنسبة يعطي أنفع الأمثلة أولاً عند بناء الموجّه.
3. **قياس التقدّم.** «٢٠٠ زوج» رقم قابل للمتابعة، بخلاف «تحسين الأسلوب» الذي
   لا يُقاس.

⚠️ حدّان صريحان
--------------
**١) هذا الجدول ليس جزءاً من قاعدة المعرفة، ولا يدخل الاسترجاع أبداً.**
السبب أن المقطع المولَّد قد يحوي مادة قانونية مؤلَّفة. ولو دخل الاسترجاع لعاد
في جولة لاحقة كـ«سياق موثوق» — فتتحوّل الهلوسة إلى حقيقة مؤرشفة. وهي أسوأ من
الهلوسة العابرة، لأنها تترسّخ وتتكرّر.

وهذا هو المبدأ نفسه الذي يقوم عليه `collect_evidence`: **الحقيقة ما قاله
المحامي، لا ما قاله النموذج.**

**٢) نسبة التعديل تقيس الكمّ لا الجودة.** نسبة منخفضة تعني «شابه أسلوبه»، لا
«صحيح قانوناً». وقد تكون مسودّة قريبة من أسلوبه وفيها مادة مؤلَّفة. ولذلك
التحقّق من الأسانيد (`citations.py`) منفصل عن هذا القياس ولا يُغني أحدُهما
عن الآخر.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import asdict, dataclass
from typing import Iterable, Optional, Sequence

# ==============================================================================
# الثوابت
# ==============================================================================

#: الهدف المعلن لعدد الأزواج المحفوظة قبل أن يصير تقليد الأسلوب مسألة هندسية.
#: رقم مبدئي قابل للتعديل — الغرض أن يكون التقدّم مرئياً لا مجرّد أمنية.
STYLE_TARGET = 200

#: الفراغات المتعدّدة (بما فيها أسطر Word) تُطوى إلى فراغ واحد قبل المقارنة.
_WHITESPACE = re.compile(r"\s+")

#: حدود تصنيف نسبة التعديل — تصاعدياً.
_BANDS: tuple[tuple[float, str], ...] = (
    (0.05, "مطابق تقريباً"),
    (0.20, "تعديل طفيف"),
    (0.50, "تعديل جوهري"),
)


# ==============================================================================
# المقارنة
# ==============================================================================


def normalize_for_diff(text: Optional[str]) -> str:
    """
    يوحّد الفراغات فقط — لا التطبيع العربي.

    السبب مقصود: هذه مقارنة **أسلوب** لا مقارنة مطابقة. فلو طبّعنا الألف
    والتاء المربوطة والتشكيل، لَما احتُسبت إضافة المحامي للتشكيل تعديلاً —
    وهي تعديل أسلوبي حقيقي يجب أن يُقاس.

    أما الفراغات فتُطبَّع لأن النصّ يُنسخ من Word وإليه، وتتغيّر فيه فواصل
    الأسطر بلا أن تتغيّر كلمة واحدة. فلو لم نطبّعها لظهرت نسبة تعديل ضخمة
    وهمية لمجرّد اختلاف التنسيق.
    """
    if not text:
        return ""
    return _WHITESPACE.sub(" ", text).strip()


def _words(text: Optional[str]) -> list[str]:
    normalized = normalize_for_diff(text)
    return normalized.split(" ") if normalized else []


def edit_ratio(generated: Optional[str], corrected: Optional[str]) -> float:
    """
    نسبة الكلمات التي تغيّرت بين المسودّة والنسخة المعتمدة (من 0.0 إلى 1.0).

    المقارنة على **الكلمات** لا المحارف: النتيجة أسرع وأقرب إلى المعنى —
    «١٢٪ من الكلمات تغيّرت» مفهومة، بخلاف «٣٪ من المحارف».

    >>> edit_ratio("على المستأجر سداد الأجرة", "على المستأجر سداد الأجرة")
    0.0
    >>> edit_ratio("", "نصّ جديد")
    1.0
    >>> round(edit_ratio("أ ب ج د", "أ ب ج ه"), 2)
    0.25
    """
    left = _words(generated)
    right = _words(corrected)

    if not left and not right:
        return 0.0
    # أحدهما فارغ والآخر لا: تغيير كامل، لا «صفر»
    if not left or not right:
        return 1.0

    # ⚠️ `autojunk=False` ضروري هنا.
    #
    # الافتراضي في difflib هو اعتبار العناصر الشائعة «نفايات» في المتتاليات
    # الطويلة (أكثر من 200 عنصر). والنصّ القانوني العربي مليء بكلمات متكرّرة
    # («المادة»، «على»، «من»، «التي»)، فيُستبعد كثير منها من المقارنة **فتنتفخ
    # نسبة التعديل** ويظهر تعديل ٤٠٪ على مسودّة شبه مطابقة.
    #
    # والثمن زمن أطول في الأسوأ، وهو محتمل هنا: المستندات قانونية بطبيعتها،
    # وطولها آلاف الكلمات لا ملايينها.
    similarity = difflib.SequenceMatcher(None, left, right, autojunk=False).ratio()
    return round(1.0 - similarity, 4)


def quality_band(ratio: float) -> str:
    """
    تصنيف مقروء لنسبة التعديل — يُعرض للمحامي بدل رقم مجرّد.

    >>> quality_band(0.01)
    'مطابق تقريباً'
    >>> quality_band(0.8)
    'إعادة كتابة'
    """
    for limit, label in _BANDS:
        if ratio < limit:
            return label
    return "إعادة كتابة"


# ==============================================================================
# السجلّ
# ==============================================================================


@dataclass(frozen=True)
class RevisionRecord:
    """
    زوج واحد: ما كتبه النموذج، وما اعتمده المحامي.

    الحقول تطابق أعمدة `draft_revisions` في `schema.sql` (القسم ١٠).
    """

    generated_text: str
    corrected_text: str
    edit_ratio: float
    word_count: int
    quality_band: str
    doc_type: Optional[str] = None
    prompt: Optional[str] = None
    session_id: Optional[str] = None

    def to_row(self) -> dict:
        """يحوّله إلى صفّ للإدراج في Supabase."""
        row = asdict(self)
        # الحقول المشتقّة وجودها في القاعدة مفيد للفلترة، لكن `quality_band`
        # تُحسب دائماً من `edit_ratio` فلا داعي لتخزينها (تجنّباً لتناقض محتمل).
        row.pop("quality_band", None)
        return row


class RevisionRejected(ValueError):
    """تصحيح غير صالح للحفظ — والسبب مذكور في الرسالة."""


def build_revision(
    generated_text: str,
    corrected_text: str,
    *,
    doc_type: Optional[str] = None,
    prompt: Optional[str] = None,
    session_id: Optional[str] = None,
) -> RevisionRecord:
    """
    يبني سجلاً من زوج نصّيين، بعد التحقّق من صلاحيته.

    يرفض ثلاث حالات، ولكلٍّ سبب مكتوب:

    1. **المسودّة فارغة** — لا شيء يُقارَن به.
    2. **التصحيح فارغ** — لا شيء يُتعلَّم منه.
    3. **لا تغيير إطلاقاً** — لا معلومة جديدة. وحفظه يُضخّم العدّاد بلا فائدة،
       فيوهم بأن المكتب جمع ٢٠٠ زوج وهو لم يجمع شيئاً.

    >>> rec = build_revision("نصّ المسودّة", "نصّ المسودّة المعدّل")
    >>> rec.word_count > 0
    True
    """
    if not normalize_for_diff(generated_text):
        raise RevisionRejected("المسودّة فارغة — لا يوجد ما يُقارَن به.")
    if not normalize_for_diff(corrected_text):
        raise RevisionRejected("النسخة المصحَّحة فارغة — لا يوجد ما يُتعلَّم منه.")

    ratio = edit_ratio(generated_text, corrected_text)
    if ratio == 0.0:
        raise RevisionRejected(
            "لا فرق بين المسودّة ونسختك — لا معلومة جديدة تُحفظ."
        )

    return RevisionRecord(
        generated_text=generated_text,
        corrected_text=corrected_text,
        edit_ratio=ratio,
        word_count=len(_words(corrected_text)),
        quality_band=quality_band(ratio),
        doc_type=doc_type,
        prompt=prompt,
        session_id=session_id,
    )


# ==============================================================================
# الإحصاء
# ==============================================================================


def _median(values: Sequence[float]) -> float:
    """الوسيط بلا numpy — ليبقى الملف بلا تبعيات."""
    if not values:
        return 0.0
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return round(ordered[middle], 4)
    return round((ordered[middle - 1] + ordered[middle]) / 2, 4)


def summarize(ratios: Iterable[float]) -> dict:
    """
    ملخّص تقدّم الأسلوب من قائمة نسب تعديل.

    المتوسّط وحده مضلِّل: مسودّة واحدة أُعيدت كتابتها بالكامل ترفع المتوسّط
    فتُخفي أن البقية شبه مطابقة. فالوسيط والتوزيع يُعرضان معه.

    >>> s = summarize([0.02, 0.02, 0.9])
    >>> s["count"], s["median_edit_ratio"]
    (3, 0.02)
    """
    values = [float(value) for value in ratios if value is not None]
    if not values:
        return {
            "count": 0,
            "average_edit_ratio": 0.0,
            "median_edit_ratio": 0.0,
            "distribution": {label: 0 for _limit, label in _BANDS} | {"إعادة كتابة": 0},
            "target": STYLE_TARGET,
            "progress_percent": 0.0,
        }

    distribution = {label: 0 for _limit, label in _BANDS}
    distribution["إعادة كتابة"] = 0
    for value in values:
        distribution[quality_band(value)] += 1

    return {
        "count": len(values),
        "average_edit_ratio": round(sum(values) / len(values), 4),
        "median_edit_ratio": _median(values),
        "distribution": distribution,
        # التقدّم نحو هدف تقليد الأسلوب — رقم يراه المحامي فيتقدّم فعلاً
        "target": STYLE_TARGET,
        "progress_percent": round(min(len(values) / STYLE_TARGET, 1.0) * 100, 1),
    }
