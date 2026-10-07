"""
المخرج الثاني — تقرير داخلي للمحامي، مفصولٌ عن المذكرة الموجَّهة إلى المحكمة.
=============================================================================

المشكلة التي يحلّها
------------------
`citations.py` يتحقّق من الأسانيد، و`attribution.py` من نسبة النصّ إلى مادّته،
و`review.py` من مخالفة المسودّة للموجز، و`language_audit.py` من الصياغة. أربعة
فحوص، ولكلٍّ منها تقريره.

ومع ذلك وقع ما وقع: **ثلاث مراجعات مستقلّة وجدت أن مذكرات هذا المشروع وُصفت
بالاكتمال وهي تحمل أساس أجرٍ خاطئاً، وتاريخاً خاطئاً، ومادة منسوبة إلى غير
مادّتها، وواقعة مُغيَّرة ثلاث مرّات.** والفحوص كانت تعمل. والعيب لم يكن في
الصياغة وحدها، بل في **عرض عملٍ لم يُتحقَّق منه على أنه منتهٍ**.

فالملف الذي بين يديك لا يفحص شيئاً. وظيفته أن يجمع ما أبلغت به الفحوص، ويعرضه
على المحامي **مفصولاً عن المستند**: ما ينقص، وما يخطر، وما يتعارض، وما يحتاج
مراجعة بشرية، وحالة التحقّق وما بقي مطلوباً. والقرار قراره.

القاعدة المركزية: **الفحص الذي لم يجرِ ليس فحصاً نجح**
--------------------------------------------------------
هذا هو سبب وجود الملف، ومنه جاء `Source.present`.

الفحص الغائب والفحص الذي لم يجد شيئاً **حقيقتان مختلفتان**، وخلطهما هو جوهر
العيب الذي وُلد هذا الملف ليمنعه. والكودبيس تعلّم هذا الدرس مرّة في
`frontend/components/review-panel.tsx`: كان الشكل يصل `failed: True` ومعه
`clean: True` و`error_count: 0` (انظر `_review_round` في `main.py`)، فكان
تقديم `clean` على `failed` يُنتج لوحةً تقول «سليمة» عن مراجعة **لم تحدث قطّ**.
ولذلك — وهذا مكتوب في تعليق ذلك الملف — قُدِّم فحص `failed` على فحص `clean`.

وهنا يُمنع الخلط من جهتين:

* **كل نوع متوقَّع يظهر في التقرير سواء أُرسل أم لم يُرسَل.** فلا يقرأ المحامي
  تقريراً عن ثلاثة فحوص ويظنّ أن الرابع سليم لأنه ليس فيه.
* **الغائب يُعدّ ثغرةً بمستوى خطأ** لا ملاحظة، لأنه يمنع الحكم بالسلامة. وهذا
  هو الفرق بين «فُحص فلم يُوجد عيب» و«لم يُفحص»: الأول يبني عليه المحامي،
  والثاني لا.

وما يقوله هذا الملف في الغائب نصّاً: «لم يُشغَّل هذا الفحص»، لا «لا خطأ».

لا عبارة تعني الجاهزية للإيداع
-------------------------------
`readiness` لا تُعيد إلا واحدة من ثلاث: ``verified`` أو ``partly_verified`` أو
``unverified``. ولا يوجد مدخل يُنتج عبارةً معناها أن المستند صار جاهزاً
للاكتتاب أو للإيداع. وأقصى ما يقوله التقرير في أنظف حالة: ما الذي تُحقّق منه،
وما الذي لم يُتحقَّق منه، وما بقي مطلوباً. والقرار للمحامي.
(والاختبار `test_nothing_is_ever_reported_ready_to_file` يُثبّت هذا المنع.)

⚠️ **والدرجات مرتّبة رتبةً معلنة** في :data:`SAFETY_RANK` و:func:`safety_rank`:
الفحص الغائب يجعل الدرجة **أدنى** من درجة مدخلٍ كلُّ فحوصه جرت ونظفت، لا
مجرّد **مختلفة** عنها في النصّ. ولو تساوتا في الرتبة لصار التقرير يوصي بمسودّة
ناقصة الفحص كما يوصي بمكتملة الفحص — وهو عين العيب الذي وُلد الملف لمنعه.

⛔ **العطب الثاني — وهو الذي كُشف بالتشغيل لا بالقراءة، فيُقرأ قبل أي تعديل**
--------------------------------------------------------------------------------
القاعدة أعلاه كانت **مكتوبة في هذا الملف وصحيحة، ومعطَّلة في التنفيذ**، واختباره
كان يمرّ. والسبب أن الاختبار بنى مدخلاته **قاموساً بيده** بمفاتيح لا يُنتجها أي
مستدعٍ: قائمة ``SPECS`` تضمّ ستّة أنواع، والعربتان ``case_file`` و``facts``
تُصنَّفان فيها فحوصاً يمنع غيابها الدرجة العليا. فصار كل نداء حقيقي — و`main.py`
لا يمرّر إلا الأربعة التي له ملخّصات فعلية — يُقرأ «ناقص الفحص» أبداً:

    كل الفحوص حاضرة ونظيفة      -> partly_verified (رتبة ١)
    بلا أسانيد                  -> partly_verified (رتبة ١)
    بلا نسبة                    -> partly_verified (رتبة ١)
    بلا مراجعة                  -> partly_verified (رتبة ١)
    بلا تدقيق لغوي              -> partly_verified (رتبة ١)

فالغائب والنظيف **متساويان في الرتبة** — وهو العيب الذي وُلد الملف لمنعه —
و``verified`` **لا تُبلَغ أبداً** لأن ملف الدعوى والوقائع لا يمرّرهما مستدعٍ
(لا ``summarize`` في `case_file.py`، و`facts.py::summarize` لا يُنتج
``error_count`` أصلاً). أي أنّ الدرجة العليا في التوقيع كانت **وعداً لا يُوفى**،
والاختبار كان **يشهد لعطبٍ لا وجود له** لأنه اختبر شكلاً متخيَّلاً.

⚠️ **والدرس مسجَّل هنا كما سُجِّل في `test_module_health.py`**: اختبارٌ يبني
مدخلاته بيده يختبر نفسه، فيبقى الشكل الحقيقي غير مختبر حتى يُشغَّل في الخدمة.
ولذلك صار في `tests/test_briefing.py` مساعدٌ واحد يبني ملخّص الأسانيد **بمفاتيح
`_verify_round` نفسها**، وكل اختبار يستدعيه.

والعلاج المعلن: **الفحص والمدخل صنفان لا صنف واحد.** الفحوص أربعة لها
``summarize`` حقيقية في المشروع (``CHECK_KINDS``)، وهي وحدها تحكم الدرجة.
أما ملف الدعوى والوقائع فمدخلان يُبلَّغ عن غيابهما في «ما ينقص» و«المصادر» ولا
يُقاس عليهما حكم التحقّق، لأن لا وحدة تُنتجهما ولا عدّ يُقرأ منهما.

الحدّ المعلن
-----------
هذا الملف **لا يعيد حساب** شيء ولا يفسّر شيئاً: كل رقم يعرضه مأخوذ من ملخّص
أرسلته وحدة أخرى. فإن أبلغت وحدةٌ عن ثلاثة أخطاء، عرض ثلاثة؛ وإن لم تُبلغ عن
رقم، عرض ``—`` ولم يكتب صفراً. والقاعدة المستقرّة في هذا الكودبيس: **الرقم
الذي لا يُحسب لا يُعرض** — وعرضُ ``0`` مكان ``—`` كذبٌ صغير يُبنى عليه قرار.

و``conflicts`` و``alternatives`` لا ينتجهما أي فحص قائم، فلا يُختلق لهما محتوى:
تبقيان فارغتين حتى يمرّرهما المستدعي في ``notes``.

الملف بلا تبعية خارجية وبلا حالة وبلا إدخال/إخراج وبلا شبكة وبلا طباعة: مكتبة
بايثون القياسية وحدها، فيعمل اختباره بلا نموذج وبلا أرشيف وبلا مفتاح API.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

# ==============================================================================
# ١. الثوابت — الترتيب والأسماء
# ==============================================================================

#: درجات السلامة الثلاث. أسماء لا نصوص حرّة، لأنها تُقارَن في الاختبار وفي أي
#: مسار يستدعي :func:`readiness`، والنصّ الحرّ يُكتب مرة «verified» ومرة
#: «Verified» فلا يُطابق شيء.
#:
#: ⚠️ **وليس فيها درجة معناها أن المستند صار صالحاً للتسليم، وهذا مقصود**:
#: أعلى درجة تقول «كل ما جريناه لم يُبلّغ عن خطأ»، ولا تقول إن المستند مقبول.
#: والقرار حكمٌ قانوني لا يُنتجه هذا الملف.
SAFETY_VERIFIED = "verified"
SAFETY_PARTLY = "partly_verified"
SAFETY_UNVERIFIED = "unverified"

SAFETY_LEVELS: tuple[str, ...] = (SAFETY_VERIFIED, SAFETY_PARTLY, SAFETY_UNVERIFIED)

#: رتبة كل درجة — **الأصغر أقوى**. وتُستعمل للمقارنة الصريحة: «درجة أدنى من»
#: لا تُقاس بمقارنة النصوص أبجدياً، ولا تُقاس بطول كلمة.
#:
#: ⚠️ وتُصدَّر لأن المقارنة **خاصية في العقد لا في الاختبار**: من أراد أن يعرف
#: أدرجتان متساويتان أم إحداهما أدنى وجب أن يجد الرتبة هنا، لا أن يخمّنها من
#: ترتيب الثوابت في ملف.
SAFETY_RANK: Mapping[str, int] = {
    level: index for index, level in enumerate(SAFETY_LEVELS)
}


def safety_rank(level: str) -> int:
    """
    رتبة درجة السلامة: ``0`` للدرجة العليا، و``2`` للأدنى. الأصغر أقوى.

    ⚠️ تُستعمل للمقارنة الصريحة بين درجتين (``safety_rank(a) < safety_rank(b)``
    تعني أن ``a`` **أقوى**). ولا تُقارن الدرجات كمقارنة نصوص: ``"unverified"``
    تسبق ``"verified"`` أبجدياً، والمقارنة الأبجدية تعطي عكس الصواب.

    >>> safety_rank(SAFETY_VERIFIED) < safety_rank(SAFETY_PARTLY)
    True
    >>> safety_rank(SAFETY_UNVERIFIED) > safety_rank(SAFETY_PARTLY)
    True
    """
    return SAFETY_RANK.get(level, len(SAFETY_LEVELS))

#: ما يُعرض بدل الرقم الذي لم يُرسَل.
#:
#: ⚠️ وصفرةٌ هنا كانت ستكون **كذباً صغيراً يُبنى عليه قرار**: «0 خطأ» تعني أن
#: الفحص جرى ولم يجد، و«—» تعني أننا لا نعلم. والفرق بينهما هو الفرق بين
#: الشهادة بالسلامة والصمت عنها.
DASH = "—"

#: الرتبة الثابتة للمجموعات في ``to_markdown`` — لا تُغيَّر بلا تغيير الاختبار
#: الذي يثبّتها. والترتيب مقصود: الثغرات أولاً (ما ينقص ليكتمل الفحص)، ثم ما
#: يخطر، ثم ما يتعارض، ثم البدائل، ثم ما يحتاج نظر إنسان، ثم المصادر، ثم ما
#: بقي مفتوحاً — وهو ترتيب **القراءة** لا ترتيب الإنشاء.
GROUP_ORDER: tuple[str, ...] = (
    "gaps",
    "risks",
    "conflicts",
    "alternatives",
    "needs_review",
)

#: عناوين المجموعات في التقرير العربي.
GROUP_TITLES: Mapping[str, str] = {
    "gaps": "ما ينقص",
    "risks": "المخاطر",
    "conflicts": "التعارضات",
    "alternatives": "البدائل",
    "needs_review": "ما يحتاج مراجعة بشرية",
}

#: مفاتيح ``notes`` التي تُمرَّر كما هي.
#:
#: ولا يُختلق لهما محتوى حين تغيب، لأن كاتباً لا يعرف إلا ما أُبلغ به: تقرير
#: فيه تعارضات مؤلَّفة أسوأ من تقرير يقول «لا تعارض مبلَّغ عنه».
NOTE_KEYS: tuple[str, ...] = ("conflicts", "alternatives")


def _dash_if(count: int | None) -> str:
    """يُنسّق عدداً للعرض، ويعرض ``—`` حيث لا عدد. (المنطق كلّه في ``DASH``.)"""
    return DASH if count is None else str(count)


def _count(value: object) -> int | None:
    """
    يقرأ عدداً من ملخّص وحدة أخرى، ويعيد ``None`` إن **لم يُبلَّغ به**.

    ⚠️ **و``None`` غير ``0``**: الأول «لم يُبلَّغ عن رقم»، والثاني «أُبلغ عن
    صفر». وخلطهما يجعل تقريراً عن فحص لم يُشغَّل يُقرأ كشهادة سلامة.

    وتُقرأ الأعداد من صورتين، لأن الوحدات تُبلغ بالصورتين:

    * **عدد صريح** — ``error_count`` في `review.py` و`attribution.py`.
    * **قائمة مُبلَّغ بها** — ``rejected`` و``unbacked_articles`` و
      ``malformed_lines`` في ملخّص `main.py::_verify_round`، و``dropped``
      عدده صريح. و**قائمة بطول ن** إبلاغٌ عن ن: ``[]`` صفرٌ مُبلَّغ به، لا
      غيابُ رقم.

    ⚠️ **وإسقاط صورة القائمة كان عيباً فعلياً في أول نسخة من هذا الملف**:
    حُسب كلُّ ملخّص الأسانيد ``None`` (لأن `citations.py` لا تُنتج عدّادات
    أصلاً)، فغاب الفرق بين «لا سند مرفوض» و«لم يُفحص السند» — وعاد التقرير
    يقول عن المدخل النظيف ما يقوله عن مدخل ناقص، **وهو العيب الذي جاء الملف
    لمنعه**. فأُضيفت هذه الصورة، وأُضيف لها اختبار
    ``test_a_number_carried_in_a_list_is_a_number_not_a_gap``.

    والقيمة المنطقية تُرفض وحدها: ``True`` مفتاح حالة لا عدد، وعدّه ``1``
    يخترع رقماً من لا رقم. وكذلك النصّ غير الرقمي — ولو كان أرقاماً، لأن نصّاً
    عربياً-هندياً («٣») يحتاج جدول تحويل، وجدولُ تحويل ثانٍ في المشروع يُنتج
    جدولين يفترقان.
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, (list, tuple)):
        return len(value)
    return None


def _sum_counts(summary: Mapping[str, Any], keys: Sequence[str]) -> int | None:
    """
    مجموع عدّادات من الملخّص — **فقط** إن أُرسلت كلّها.

    ⚠️ **وغياب أحدها يعني ``None`` لا صفراً**: مجموعٌ ناقصٌ يُعرَض كرقم كامل
    أسوأ من عدم عرض رقم، لأن القارئ لا يستطيع أن يعرف أنّه ناقص.
    """
    total = 0
    for key in keys:
        number = _count(summary.get(key))
        if number is None:
            return None
        total += number
    return total


def _first_count(summary: Mapping[str, Any], keys: Sequence[str]) -> int | None:
    """أول عدّاد مُرسَل من المفاتيح المرشّحة، أو ``None`` إن لم يُرسَل أيٌّ منها."""
    for key in keys:
        number = _count(summary.get(key))
        if number is not None:
            return number
    return None


# ==============================================================================
# ٢. المصادر المتوقَّعة — شبكة الأنواع ومفاتيحها الحقيقية
# ==============================================================================
# ⚠️ المفاتيح أدناه **مقروءة من الوحدات نفسها، لا مُخترَعة**. ومصدر كلٍّ منها:
#
#   * `review.py::summarize`        → summary · clean · error_count ·
#                                     notice_count · dropped · findings
#                                     و`main.py::_review_round` يضيف `failed`
#                                     حين يفشل النداء (وهو يصل ومعه clean: True).
#   * `attribution.py::summarize`   → summary · clean · error_count ·
#                                     notice_count · total · checks
#   * `language_audit.py::summarize`→ summary · clean · error_count ·
#                                     notice_count · findings
#   * `citations.py`                → **لا يوجد فيها `summarize`**. شكل ملخّصها
#                                     يُبنى في `main.py::_verify_round`، ومفاتيحه:
#                                     summary · has_evidence · evidence_count ·
#                                     has_citation_block · verified · rejected ·
#                                     unbacked_articles · malformed_lines · attribution
#                                     (و«unbacked_articles» عددُ مواد ذُكرت في
#                                      المتن ولم ترد في أي مقطع، و«malformed_lines»
#                                      أسطرُ أسانيد لم تُقرأ). ولا مفاتيح عدّ فيها
#                                      لغير أطوال القوائم، فالأعداد تُشتقّ منها.
#   * `case_file` و`facts`          → لا وحدة لهما في المشروع اليوم. يُتوقّعان
#                                     لأن المحامي يقرأ ملف الدعوى والوقائع، ويُبلَّغ
#                                     عنهما «لم يُشغَّل» ما لم يُمرَّرا.


@dataclass(frozen=True)
class _KindSpec:
    """وصف نوع مصدر متوقَّع: اسمه العربي، وكيف تُقرأ أعداده من ملخّصه."""

    kind: str
    label: str
    #: مفاتيح عدّ الأخطاء — أول مفتاح مُرسَل يُستهلك، وإلا تُشتقّ الأعداد من
    #: ``derive_errors``. ولا مفتاح اصطناعي إن غاب الاثنان: يصير العدد ``None``.
    error_keys: tuple[str, ...] = ()
    #: مفاتيح عدّ الملاحظات — `absent` في `attribution.py` ملاحظة لا خطأ،
    #: ولذلك تُقرأ هنا، وتُعرَض على المحامي ولا تمنع. وكذلك ``malformed_lines``
    #: في ملخّص الأسانيد: سطر سند لم يُقرأ نقصٌ في القراءة لا خطأ في المسودّة.
    notice_keys: tuple[str, ...] = ()
    #: مفاتيح تُشتقّ منها الأخطاء عند غياب عدّ صريح، **بشرط إرسالها كلّها**.
    #: وموضعها هنا لأن `citations.py` لا تُنتج عدّادات: أخطاؤها هي ما رُفض من
    #: الاقتباسات وما ذُكر في المتن بلا سند — وهما قائمتان لا رقم.
    derive_errors: tuple[str, ...] = ()
    #: تُقرأ فقط لبناء «ما يحتاج مراجعة بشرية» بندًا بندًا، لا للعدّ.
    detail_keys: tuple[str, ...] = ()
    #: هل **يحكم** هذا النوع الدرجة؟ ``True`` للفحوص التي لها ``summarize``
    #: في المشروع، و``False`` للمدخلات التي لا وحدة تُنتجها.
    #:
    #: ⛔ **وهذا الحقل هو علاج العطب المسجَّل في صدر الملف.** قبل وجوده كانت
    #: ``case_file`` و``facts`` تحكمان الدرجة، ولا مستدعٍ يمرّرهما (فلا وحدة
    #: تُنتجهما)، فصار كل نداء حقيقي «ناقص الفحص»، وتساوى الغائب والنظيف في
    #: الرتبة، وصارت ``verified`` غير قابلة للبلوغ. فالغياب الذي لا يُنتجه
    #: المستدعي لا يُقاس عليه حكم — **وإلا صار العيب الدائم قاعدة**.
    gates_readiness: bool = True


#: الأنواع المتوقَّعة **بترتيبها الثابت** — وهو نفس ترتيبها في التقرير.
#:
#: ⚠️ **ولا يُشتقّ هذا الترتيب من `reports`**: لو رُتِّب التقرير على ترتيب
#: مفاتيح قاموس المدخل لتغيّر شكل التقرير بتغيّر ترتيب الإدخال، ولتغيّر بين
#: نداءين بالمدخل نفسه. والترتيب جزء من التقرير لا من المدخل.
SPECS: tuple[_KindSpec, ...] = (
    _KindSpec(
        kind="citation",
        label="الأسانيد",
        # لا عدّادات للأخطاء في `main.py::_verify_round`: الأخطاء مشتقّة من
        # القائمتين. ⚠️ و``malformed_lines`` **ملاحظة** لا خطأ، وسطر السند
        # الضائع يُعرض في «ما ينقص» كي لا يُقرأ الفحص نظيفاً وهو لم يقرأ كل
        # سند. وقبل إضافتها هنا كان عدد الملاحظات ``None`` دائماً في هذا
        # النوع — فيُعرض ``—`` عن صفر مُبلَّغ به بـ``[]``.
        derive_errors=("rejected", "unbacked_articles"),
        notice_keys=("malformed_lines",),
        detail_keys=("rejected", "unbacked_articles", "malformed_lines"),
    ),
    _KindSpec(
        kind="attribution",
        label="نسبة النصوص إلى موادها",
        error_keys=("error_count",),
        notice_keys=("notice_count",),
        detail_keys=("checks",),
    ),
    _KindSpec(
        kind="review",
        label="المراجعة الثانية",
        error_keys=("error_count",),
        notice_keys=("notice_count",),
        detail_keys=("findings",),
    ),
    _KindSpec(
        kind="language",
        label="التدقيق اللغوي",
        error_keys=("error_count",),
        notice_keys=("notice_count",),
        detail_keys=("findings",),
    ),
    # ---- مدخلان لا فحصان ----
    #
    # ملف الدعوى والوقائع: يُتوقّعان في التقرير لأن المحامي يقرأهما، ويظهران
    # «لم يُشغَّل» ما لم يُمرَّرا، ويُسجَّل غيابهما ثغرةً في «ما ينقص» وعلى
    # قائمة المراجعة البشرية.
    #
    # ⛔ **ولا يحكمان الدرجة** (``gates_readiness=False``)، وهذا هو العلاج:
    # لا ``summarize`` في `case_file.py` تُنتج ملخّصهما، و``facts.py::summarize``
    # لا يُنتج ``error_count`` أصلاً — فليس لهما «حال نظيفة» تُبنى من وحدات
    # المشروع. ولو حكما الدرجة لكان كل نداء حقيقي ناقصاً أبداً، **وهو ما كان**.
    _KindSpec(
        kind="case_file",
        label="ملف الدعوى",
        gates_readiness=False,
    ),
    _KindSpec(
        kind="facts",
        label="الوقائع",
        gates_readiness=False,
    ),
)

EXPECTED_KINDS: tuple[str, ...] = tuple(spec.kind for spec in SPECS)

#: الأنواع التي **تحكم** الدرجة: ما له وحدة تُنتج ملخّصه اليوم.
#:
#: ⚠️ **والدرجة العليا لا تُبلَغ إلا باجتماعها كلّها**، ولذلك حرّاسها في
#: الاختبار يمرّون على هذه القائمة لا على :data:`EXPECTED_KINDS`: النوعان
#: الآخران مدخلان لا يُنتجهما مستدعٍ، فلا يُقاس عليهما حكم.
CHECK_KINDS: tuple[str, ...] = tuple(spec.kind for spec in SPECS if spec.gates_readiness)

#: الأنواع التي تُعرَض ولا تحكم — المدخلات التي يُبلَّغ عن غيابها ولا يُقاس عليها.
INPUT_KINDS: tuple[str, ...] = tuple(
    spec.kind for spec in SPECS if not spec.gates_readiness
)

_SPEC_BY_KIND: Mapping[str, _KindSpec] = {spec.kind: spec for spec in SPECS}

#: مفاتيح ``failed`` التي يضعها `main.py::_review_round` حين يفشل نداء المراجعة.
#:
#: ⚠️ **وهذا المفتاح يُفحص قبل أي شيء آخر**، على قاعدة `review-panel.tsx`:
#: الملخّص الفاشل يصل ومعه ``clean: True`` و``error_count: 0``، فلو قرأنا
#: `clean` لحسبناه فحصاً نجح. وهو **فشل** لا نجاح.
FAILED_KEYS: tuple[str, ...] = ("failed", "error")


def _is_failed(summary: Mapping[str, Any]) -> bool:
    """
    هل الملخّص يُعلن أن الفحص **لم يجرِ**؟

    ⚠️ و``failed`` هنا تُقرأ **أولاً**، ولا يُنظر إلى ``clean`` ولا إلى
    ``error_count`` قبلها. وهذا هو الترتيب نفسه الذي فُرض في `review-panel.tsx`
    بعد أن أنتجت الواجهة لوحةً تقول «سليمة» عن مراجعة لم تحدث.
    """
    return summary.get("failed") is True or summary.get("error") is True


# ==============================================================================
# ٣. جمع المصادر
# ==============================================================================


@dataclass(frozen=True)
class Source:
    """
    مصدر واحد من مصادر التحقّق، بحالته كما أُبلغ عنها.

    Attributes:
        kind:    نوع المصدر (``citation`` · ``attribution`` · ``review`` ·
                 ``language`` · ``case_file`` · ``facts``).
        label:   اسمه بالعربية، كما يُعرض على المحامي.
        present: هل أُرسل ملخّصه؟ و``False`` تعني **لم يُشغَّل الفحص**، لا أنه
                 خلا من العيب. وهذا الحقل هو سبب وجود الملف كلّه.
        summary: السطر العربي الموجز الذي أنتجته الوحدة نفسها (``summarize``
                 فيها، أو نصّ «لم يُشغَّل» هنا).
        errors:  عدد الأخطاء كما أُبلغ، أو ``None`` إن **لم يُبلَّغ بعدد**.
                 ⚠️ و``None`` غير ``0``: الأول لا يُعرض إلا ``—``، والثاني
                 يُعرض ``0``. وخلطهما يُكذب على القارئ.
        notices: عدد الملاحظات، أو ``None``. والملاحظة لا تمنع.
    """

    kind: str
    label: str
    present: bool
    summary: str
    errors: int | None = None
    notices: int | None = None


def _source_for(spec: _KindSpec, report: Mapping[str, Any] | None) -> Source:
    """يبني مصدراً واحداً من ملخّصه، أو مصدراً غائباً إن لم يُرسَل."""
    if report is None:
        # ⚠️ النصّ هنا محسوم: «لم يُشغَّل هذا الفحص». ولو كتبنا «لا خطأ» لكان
        # أخطر سطر في الملف: يقرأ المحامي سلامةً لم يشهد بها أحد.
        return Source(
            kind=spec.kind,
            label=spec.label,
            present=False,
            summary="لم يُشغَّل هذا الفحص — فغيابه ليس سلامة.",
        )

    if _is_failed(report):
        return Source(
            kind=spec.kind,
            label=spec.label,
            present=False,
            summary="تعذّر إتمام هذا الفحص — لا نتيجة تُقرأ.",
        )

    raw_summary = report.get("summary")
    summary = raw_summary.strip() if isinstance(raw_summary, str) and raw_summary.strip() else ""

    errors = _first_count(report, spec.error_keys) if spec.error_keys else None
    if errors is None and spec.derive_errors:
        errors = _sum_counts(report, spec.derive_errors)
    notices = _first_count(report, spec.notice_keys) if spec.notice_keys else None

    return Source(
        kind=spec.kind,
        label=spec.label,
        present=True,
        summary=summary or "لم يُرفق سطر موجز لهذا الفحص.",
        errors=errors,
        notices=notices,
    )


def gather(reports: Mapping[str, Mapping | None] | None) -> tuple[Source, ...]:
    """
    يجمع ملخّصات الفحوص في مصادر مرتّبة، وتظهر فيه **كل** الأنواع المتوقَّعة.

    ⚠️ **قاعدة الملف**: نوع متوقَّع لم يُرسل ملخّصه يظهر ``present=False``،
    ويُعدّ في :func:`build` **ثغرةً بمستوى خطأ**. والفحص الغائب والفحص الذي لم
    يجد شيئاً حقيقتان مختلفتان، وخلطهما هو العيب الذي جاء هذا الملف لمنعه.

    >>> gathered = gather({"language": {"summary": "الصياغة سليمة.", "error_count": 0}})
    >>> [(item.kind, item.present) for item in gathered][:2]
    [('citation', False), ('attribution', False)]
    """
    supplied = reports or {}
    return tuple(
        _source_for(spec, supplied.get(spec.kind)) for spec in SPECS
    )


# ==============================================================================
# ٤. السلامة — الحارس على «جاهز»
# ==============================================================================


def _blocked(
    sources: Sequence[Source], unverified_claims: int, questions: Sequence[str] = ()
) -> list[str]:
    """
    أسباب عدم بلوغ درجة ``verified``، بالعربية — **على الفحوص وحدها**.

    ⚠️ **وأي سبب هنا كافٍ**: مصدر غائب، أو فحص تعذّر، أو خطأ مُبلَّغ عنه، أو
    عددٌ لم يُرسَل (فلا يُشهد بسلامة ما لا يُعرف عدده)، أو دعوى غير موثَّقة، أو
    سؤال مفتوح. والدرجة العليا لا تُمنح بقائمة أسباب فارغة.

    ⛔ **ولا تدخل المدخلات في هذا الحساب** (``_SPEC_BY_KIND[kind].gates_readiness``).
    وغيابها **يُسجَّل** في «ما ينقص» وعلى قائمة المراجعة البشرية، فلا يُخفى،
    **ولا يخفض الدرجة**: لا وحدة تُنتج لهما «حالاً نظيفة» تُقاس بها. وقد كان
    إدخالهما هنا هو العطب الذي جعل كل نداء حقيقي «ناقص الفحص» أبداً، فساوى
    الغائبُ النظيفَ في الرتبة وصارت ``verified`` غير قابلة للبلوغ.
    """
    reasons: list[str] = []
    for source in sources:
        if not _SPEC_BY_KIND[source.kind].gates_readiness:
            continue
        if not source.present:
            reasons.append(f"{source.label}: لم يُشغَّل الفحص.")
            continue
        if source.errors is None:
            reasons.append(f"{source.label}: لم يُبلَّغ عن عدد الأخطاء.")
        elif source.errors:
            reasons.append(f"{source.label}: {source.errors} خطأ مُبلَّغ عنه.")

    if unverified_claims:
        reasons.append(f"دعاوى غير موثَّقة: {unverified_claims}.")
    if questions:
        for question in questions:
            reasons.append(f"سؤال مفتوح: {question}")
    return reasons


def readiness(
    sources: Sequence[Source],
    unverified_claims: int,
    open_questions: Sequence[str] = (),
) -> str:
    """
    درجة السلامة: ``verified`` أو ``partly_verified`` أو ``unverified``.

    ⚠️ **ولا يوجد مدخل يُنتج عبارةً معناها أن المستند انتهى وصار صالحاً
    للتسليم.** أعلى ما تقوله الدرجة العليا: كل فحص **جرى**، ولم يُبلّغ عن خطأ،
    ولا دعوى غير موثَّقة، ولا سؤال مفتوح. وذلك **تقرير عن الفحوص لا شهادة عن
    المستند**: الفحوص تغطّي ما تُغطّيه وحدها، وحكم القيمة القانونية للمحامي.

    والدرجات:

    * ``verified``        — كل **فحص** حاضر، وكل عدد أُرسل، ولا خطأ، ولا دعوى
      غير موثَّقة، ولا سؤال مفتوح. (والمدخلات الغائبة لا تمنعها: انظر
      :data:`CHECK_KINDS` و:data:`INPUT_KINDS`.)
    * ``unverified``      — **لا فحص واحد جرت له نتيجة تُقرأ** (كلها غائبة أو
      متعذّرة)، أو وُجدت دعوى غير موثَّقة والحال أن لا فحص يُقرأ. فلا شيء
      يُبنى عليه.
    * ``partly_verified`` — ما بينهما: بعض الفحوص جرت وأبلغت، وبعضها غاب أو
      أبلغ عن خطأ أو عن عدد ناقص.

    ⚠️ **والفحص الغائب أدنى رتبةً من الفحص الذي جرى ونظف**، لا مختلفٌ عنه في
    النصّ وحده — وهذا ما يقيسه ``SAFETY_RANK``، وله حارسه في الاختبار.

    >>> gathered = gather({"language": {"summary": "سليمة.", "error_count": 0}})
    >>> readiness(gathered, 0)
    'partly_verified'
    """
    checks = [source for source in sources if _SPEC_BY_KIND[source.kind].gates_readiness]
    present_checks = [source for source in checks if source.present]
    if not present_checks:
        return SAFETY_UNVERIFIED

    questions = [
        str(question) for question in (open_questions or ()) if str(question).strip()
    ]
    if unverified_claims and all(source.errors is None for source in present_checks):
        # دعاوى بلا توثيق ولا فحص واحد أبلغ عن عدد: لا شيء يُقاس عليه.
        return SAFETY_UNVERIFIED

    if _blocked(sources, unverified_claims, questions):
        return SAFETY_PARTLY

    return SAFETY_VERIFIED


def _headline(safety: str) -> str:
    """
    جملة واحدة تصف حال التحقّق — بلا أن تدّعي جاهزية.

    ⚠️ **والنصّ محسوم هنا ولا يُكتب في ``to_markdown``**: لو كُتب الجملة في
    موضع العرض لصار تغييرها في مكانين، ولأمكن أن يُضاف إليها وصفُ جاهزية في
    موضع واحد لا يراه الاختبار.
    """
    if safety == SAFETY_VERIFIED:
        return (
            "كل فحص متوقَّع جرى ولم يُبلّغ عن خطأ، ولم تبقَ دعوى غير موثَّقة ولا "
            "سؤال مفتوح. هذا تقرير عن الفحوص لا شهادة بصحّة المستند، والقرار "
            "قرار المحامي."
        )
    if safety == SAFETY_UNVERIFIED:
        return "لم يجرِ فحص واحد بنتيجة تُقرأ — لا يُبنى على هذه المسودّة حكم."
    return "بعض الفحوص جرت، وبعضها لم يُشغَّل أو أبلغ عن خطأ — التحقّق ناقص."


# ==============================================================================
# ٥. التقرير
# ==============================================================================


@dataclass(frozen=True)
class InternalReport:
    """
    التقرير الداخلي: ما لم يُتحقَّق منه، وما يبقى على المحامي.

    ⚠️ وهو **مفصول عن المذكرة الموجَّهة إلى المحكمة**، وهذا سبب وجوده: المذكرة
    نصّ يقرأه الخصم، والتقرير ورقة عمل تقرأها أنت. وخلطُهما هو ما جعل مسودّات
    تُسلَّم وفيها أساس حساب خاطئ: الخلل يُكتب في الورقة الموجَّهة للخصم بصفته
    اكتمالاً، بدل أن يُكتب في ورقة العمل بصفته ثغرة.

    Attributes:
        safety:            ``verified`` أو ``partly_verified`` أو ``unverified``.
        headline:          جملة عربية تصف حال التحقّق.
        gaps:              ما ينقص: فحوص لم تُشغَّل، وأعداد لم تُبلَّغ، وأسطر
                           أسانيد لم تُقرأ.
        risks:             المخاطر: سطر لكل نوع خطأ **باسمه** لا بعدده وحده.
        conflicts:         التعارضات — ما مرّره المستدعي في ``notes`` وحده.
        alternatives:      البدائل — كذلك.
        needs_review:      ما يجب أن ينظر فيه إنسان.
        sources:           المصادر المتوقَّعة كلها، حاضرةً وغائبة.
        unverified_claims: عدد الدعاوى التي لم تُثبت (اقتباس مرفوض · مادة بلا
                           سند · سطر سند لم يُقرأ).
        open_questions:    الأسئلة المفتوحة كما أُرسلت.
        generated_at:      طابع زمني، أو ``None`` إن لم يُمرَّر. و``to_dict``
                           يُعيده ``None`` (صالح للـ JSON)، و``to_markdown``
                           لا يطبعه أصلاً — فالطابع الزمني في تقرير يُرسل إلى
                           نموذج أو يُخزَّن ليس من عمل هذا الملف.
    """

    safety: str
    headline: str
    gaps: tuple[str, ...]
    risks: tuple[str, ...]
    conflicts: tuple[str, ...]
    alternatives: tuple[str, ...]
    needs_review: tuple[str, ...]
    sources: tuple[Source, ...]
    unverified_claims: int
    open_questions: tuple[str, ...] = ()
    generated_at: str | None = None

    def to_dict(self) -> dict:
        """
        يحوّل التقرير إلى قاموس صالح للبثّ كـ JSON إلى الواجهة.

        ⚠️ ولا يُضاف حقل مشتقّ هنا يُعاد حسابه في موضع آخر: ``safety`` تُحفظ
        كما حسبها :func:`readiness`، فلا يفترق ما يراه المحامي عمّا حُسب.
        """
        return {
            "safety": self.safety,
            "headline": self.headline,
            "gaps": list(self.gaps),
            "risks": list(self.risks),
            "conflicts": list(self.conflicts),
            "alternatives": list(self.alternatives),
            "needs_review": list(self.needs_review),
            "unverified_claims": self.unverified_claims,
            "open_questions": list(self.open_questions),
            "generated_at": self.generated_at,
            "sources": [
                {
                    "kind": source.kind,
                    "label": source.label,
                    "present": source.present,
                    "summary": source.summary,
                    # ⚠️ ``None`` لا صفر: الواجهة تعرض ``—``، ولو بُثّ صفر
                    # لقرأه المحامي «لا خطأ» عن فحص لم يُبلَّغ عن عدده.
                    "errors": source.errors,
                    "notices": source.notices,
                }
                for source in self.sources
            ],
        }

    def to_markdown(self) -> str:
        """
        يرسم التقرير نصّاً عربياً مرتّباً — بلا وسوم Markdown تُفسد النسخ.

        والترتيب ثابت لا يتغيّر: العنوان، ثم سطر السلامة، ثم مجموعة لكل غير
        فارغ بترتيب :data:`GROUP_ORDER`، ثم جدول المصادر، ثم الأسئلة المفتوحة.
        والقسم الفارغ لا يُرسم أصلاً — سياجٌ فارغ يُقرأ نقصاً لا انتفاءً.

        ⚠️ **وكل رقم من الملخّص المُرسَل، والغائب يُعرض ``—``** (انظر ``DASH``).
        ولا يظهر في المخرج ``None`` ولا ``{}``.
        """
        lines: list[str] = ["# تقرير داخلي للمحامي", "", f"حالة التحقّق: {self.safety}", ""]
        lines.append(self.headline)
        lines.append("")

        groups: Mapping[str, tuple[str, ...]] = {
            "gaps": self.gaps,
            "risks": self.risks,
            "conflicts": self.conflicts,
            "alternatives": self.alternatives,
            "needs_review": self.needs_review,
        }
        for key in GROUP_ORDER:
            items = groups[key]
            if not items:
                continue
            lines.append(f"## {GROUP_TITLES[key]}")
            lines.append("")
            lines.extend(f"- {item}" for item in items)
            lines.append("")

        lines.append("## المصادر")
        lines.append("")
        lines.append("| النوع | الحال | الأخطاء | الملاحظات | الملخّص |")
        lines.append("| --- | --- | --- | --- | --- |")
        for source in self.sources:
            state = "جرى" if source.present else "لم يُجرِ الفحص"
            summary = source.summary.replace("|", "/").replace("\n", " ").strip()
            lines.append(
                f"| {source.label} | {state} | {_dash_if(source.errors)} "
                f"| {_dash_if(source.notices)} | {summary} |"
            )
        lines.append("")

        if self.open_questions:
            lines.append("## أسئلة مفتوحة")
            lines.append("")
            lines.extend(f"- {question}" for question in self.open_questions)
            lines.append("")

        facts = [
            f"- دعاوى غير موثَّقة: {self.unverified_claims}.",
            f"- مصادر لم تُشغَّل: {sum(1 for source in self.sources if not source.present)}"
            f" من {len(self.sources)}.",
        ]
        lines.append("## وقائع الوحدة")
        lines.append("")
        lines.extend(facts)
        lines.append("")

        return "\n".join(lines).strip() + "\n"


# ==============================================================================
# ٦. اشتقاق مجموعات التقرير
# ==============================================================================

#: أسماء أنواع الأخطاء المعروضة في «المخاطر» — بالعربية، ولكل مفتاح حقيقي.
#:
#: ⚠️ **ووجود هذا الجدول هو سبب وجود القسم**: «3 أخطاء» لا تقول للمحامي شيئاً،
#: و«اقتباسات مرفوضة: 2 · أسطر أسانيد لم تُقرأ: 1» تقول له أين ينظر. والقاعدة
#: نفسها التي جعلت `language_audit.py` يُجمّع المطابقات المتطابقة: العدّ وحده
#: يُغرِق العيب، والتسمية تُبرزه.
_RISK_LABELS: Mapping[str, str] = {
    "error_count": "أخطاء مُبلَّغ عنها",
    "rejected": "اقتباسات مرفوضة: لم يثبت نصّها في المقاطع",
    "unbacked_articles": "مواد ذُكرت في المتن ولا سند لها في المسترجَع",
    "malformed_lines": "أسطر أسانيد لم تُقرأ — سند ضائع",
    "dropped": "اعتراضات أُسقطت: لم يثبت نصّها",
    "mismatched": "نصوص منسوبة إلى غير مادّتها",
}


def _risk_items(source: Source, report: Mapping[str, Any]) -> list[str]:
    """
    أسطر الخطر لمصدر واحد.

    ⚠️ **وسطر الخطر يسمّي النوع لا يعدّه وحده.** ولا يُعرض سطر «0» إطلاقاً:
    الخطر الذي لم يقع لا يُكتب، وإلا صار القسم ضجيجاً يُغرِق الخطر الحقيقي.

    ⛔ **ولا يُسأل المدخل عن عدّ لم يُبلَّغ به**: غياب عدّ ملف الدعوى ليس خطراً
    ولا نقصاً يُشكى منه — لا وحدة تُنتجه. ولو كُتب له سطر «لا عددَ أخطاء
    مُبلَّغاً عنه» لصار في تقرير نظيف سطرا خطر عن مدخلين سليمين، فيُقرأ القسم
    ضجيجاً ويُهمَل معه الخطر الحقيقي.
    """
    items: list[str] = []
    detailed = any(
        _count(report.get(key)) for key in _RISK_LABELS if key != "error_count"
    )

    for key, label in _RISK_LABELS.items():
        number = _count(report.get(key))
        if number is None or not number:
            continue
        # ``error_count`` يُذكر **فقط** إن لم يكن في الملخّص تفصيل مسمّى: ذكره
        # مع التفصيل يُظهر الرقم نفسه مرّتين، فيقرأ المحامي خطأً واحداً خطأين.
        if key == "error_count" and detailed:
            continue
        items.append(f"{source.label}: {label} — {number}.")

    if (
        not items
        and source.errors is None
        and _SPEC_BY_KIND[source.kind].gates_readiness
    ):
        # ⚠️ الكلمات هنا محسومة: «لا عددَ أخطاء مُبلَّغاً عنه». ولو كتبنا «صفر
        # أخطاء» لكان الرقم المخترع الذي يمنعه صدر الملف.
        items.append(f"{source.label}: لا عددَ أخطاء مُبلَّغاً عنه — لم يُفحص.")

    return items


def _unverified_claims(by_kind: Mapping[str, Mapping[str, Any]]) -> int:
    """
    عدد الدعاوى التي لم تُثبت، من ملخّص الأسانيد.

    والثلاث كلّها دعاوى بلا توثيق: اقتباس رُفض، ومادة ذُكرت في المتن ولم ترد
    في أي مقطع مسترجَع، وسطر سند لم يُقرأ. وكلٌّ منها **لا يُعرض على المحكمة
    بحال** حتى يُصلحه المحامي.

    ⚠️ ولا تُخترع أرقام: ما لم يُرسل يُعدّ صفراً **في هذا العدّ وحده** لأن
    الدلالة هنا «عدد ما ثبت أنه غير موثَّق» لا «عدد أخطاء الفحص»، والحقل
    المعروض في التقرير يبقى عدداً صحيحاً لا ``None``. وهذا هو موضع الفرق بين
    هذا العدّ وأعداد المصادر (تلك تُعرض ``—`` حيث لا تُعرف).
    """
    report = by_kind.get("citation") or {}
    return sum(
        _count(report.get(key)) or 0
        for key in ("rejected", "unbacked_articles", "malformed_lines")
    )


def _gaps(sources: Sequence[Source], by_kind: Mapping[str, Mapping[str, Any]]) -> list[str]:
    """
    «ما ينقص»: فحوص لم تُشغَّل، وأعداد لم تُبلَّغ، وأسطر سند لم تُقرأ.

    ⚠️ وسطر الفحص الغائب يقول **«لم يُشغَّل»** صراحةً. وهذا هو موضع القاعدة
    المركزية في الملف: القارئ لا يجوز أن يستنتج سلامةً من فراغ.

    ⛔ **وسطر «لم يُبلَّغ عن عدد» للفحوص وحدها.** المدخل — ملف الدعوى والوقائع —
    لا عدّ له في المشروع أصلاً، فطلبُ عدّه يُنتج سطرين في كل تقرير عن مدخلين
    لا يُقاس عليهما شيء. وغيابه يُسجَّل (سطر «لم يُشغَّل» حين يغيب)، ولا
    يُسجَّل ما لا وجود له.
    """
    gaps: list[str] = []
    for source in sources:
        if not source.present:
            gaps.append(f"{source.label}: لم يُشغَّل الفحص — لا نتيجة تُقرأ.")
            continue
        report = by_kind.get(source.kind) or {}
        if _SPEC_BY_KIND[source.kind].gates_readiness:
            if source.errors is None:
                gaps.append(f"{source.label}: لم يُبلَّغ عن عدد الأخطاء.")
            if source.notices is None:
                gaps.append(f"{source.label}: لم يُبلَّغ عن عدد الملاحظات.")
        if source.kind == "citation":
            malformed = _count(report.get("malformed_lines"))
            if malformed:
                gaps.append(f"أسطر أسانيد لم تُقرأ: {malformed} — سند ضائع.")
    return gaps


def _needs_review(
    sources: Sequence[Source],
    by_kind: Mapping[str, Mapping[str, Any]],
    open_questions: Sequence[str],
) -> list[str]:
    """
    «ما يحتاج مراجعة بشرية»: بندٌ لكل ما لا يُصلحه كود.

    أربعة مصادر للبند هنا، وكلّها ممّا **أبلغت به** الوحدات لا ممّا اخترعه هذا
    الملف:

    1. مصدر غائب — لا يعلم أحد ما فيه.
    2. كل إسناد ``mismatched`` — نسبة نصّ إلى مادة ليست له، وهي خطأ لا ملاحظة
       في `attribution.py`. وتُذكر ``reference`` بعينها لأنها موضع الإصلاح في
       المسودّة: يُنقل النصّ إلى مادّته أو يُحذف.
    3. كل اقتباس مُرفض، وكل مادة بلا سند، وكل اعتراض أُسقط — بذكر مراجعه حيث
       أُرسلت، لأن «اقتباس مرفوض» بلا موضع لا يُراجع.
    4. الأسئلة المفتوحة كما أُرسلت.
    """
    items: list[str] = []
    for source in sources:
        if not source.present:
            items.append(f"مراجعة بشرية مطلوبة: {source.label} لم يُشغَّل.")

    attribution = by_kind.get("attribution") or {}
    mismatched = attribution.get("mismatched")
    if _count(mismatched) is None:
        # لا مفتاح ``mismatched`` في `attribution.py::summarize` — فيه ``checks``
        # بحالاتها. فتُقرأ الحالات من ``checks`` بدل أن يُخترع مفتاح لا وجود له.
        checks = attribution.get("checks")
        if isinstance(checks, Sequence) and not isinstance(checks, (str, bytes)):
            for check in checks:
                if isinstance(check, Mapping) and check.get("status") == "mismatched":
                    reference = check.get("reference")
                    label = reference if isinstance(reference, str) else "مرجع غير مقروء"
                    items.append(
                        f"إسناد منسوب إلى غير مادّته: {label} — يُنقل النصّ إلى "
                        "مادّته أو يُحذف."
                    )
    else:
        for _index in range(_count(mismatched) or 0):
            items.append("إسناد منسوب إلى غير مادّته — راجع ``checks`` في تقرير الإسناد.")

    citation = by_kind.get("citation") or {}
    rejected = citation.get("rejected")
    if isinstance(rejected, Sequence) and not isinstance(rejected, (str, bytes)):
        for entry in rejected:
            if isinstance(entry, Mapping):
                ref = entry.get("ref")
                label = ref if isinstance(ref, str) and ref.strip() else "اقتباس بلا مرجع"
                items.append(f"اقتباس مرفوض لم يثبت نصّه: {label}.")

    unbacked = citation.get("unbacked_articles")
    if isinstance(unbacked, Sequence) and not isinstance(unbacked, (str, bytes)):
        for entry in unbacked:
            if isinstance(entry, Mapping):
                number = entry.get("number")
                label = number if isinstance(number, str) and number.strip() else "بلا رقم"
                items.append(f"مادة ذُكرت في المتن ولا سند لها في المسترجَع: {label}.")

    malformed = _count(citation.get("malformed_lines"))
    if malformed:
        items.append(f"أسطر أسانيد لم تُقرأ: {malformed} — تُراجع يدوياً.")

    review = by_kind.get("review") or {}
    dropped = _count(review.get("dropped"))
    if dropped:
        items.append(
            f"اعتراضات أُسقطت لأن نصّها لم يثبت: {dropped} — المراجع اتّهم ولم يُثبت، "
            "وهو فرقٌ عن أن يسكت راضياً."
        )

    items.extend(
        f"سؤال مفتوح: {question}" for question in open_questions if str(question).strip()
    )
    return items


# ==============================================================================
# ٧. البناء
# ==============================================================================


def build(
    reports: Mapping[str, Mapping | None] | None,
    open_questions: Sequence[str] = (),
    notes: Mapping[str, Sequence[str]] | None = None,
    generated_at: str | None = None,
) -> InternalReport:
    """
    يبني التقرير الداخلي من ملخّصات الفحوص.

    ⚠️ **و``conflicts`` و``alternatives`` لا يُختلق لهما محتوى.** لا وحدة في
    المشروع تُنتجهما اليوم، فتبقيان فارغتين حتى يمرّرهما المستدعي في ``notes``.
    وتقريرٌ فيه تعارضات مؤلَّفة أسوأ من تقرير يقول «لا تعارض مبلَّغ عنه»، لأن
    الأول يُفقد الثقة في التقرير كلّه حين يُكتشف.

    ⚠️ **ولا يُحسب هنا رقم واحد**: كل عدد يُقرأ من الملخّص كما أُرسل، وما لم
    يُرسل يُعرض ``—``.

    >>> report = build({"language": {"summary": "الصياغة سليمة.", "error_count": 0}})
    >>> report.safety
    'partly_verified'
    """
    delivered = reports or {}
    sources = gather(delivered)
    # ⚠️ ملخّص فاشل (`failed: True`) لا يُستهلك في الاشتقاق: قوائمه فارغة
    # وعدّاداته أصفار، فقراءتها تُنتج «لا شيء» عن فحص لم يجرِ. ويُعالَج في
    # ``gather`` بأنه غائب، فلا يُقرأ هنا أصلاً.
    by_kind: dict[str, Mapping[str, Any]] = {
        kind: report
        for kind, report in delivered.items()
        if isinstance(report, Mapping) and not _is_failed(report)
    }

    unverified_claims = _unverified_claims(by_kind)
    questions = tuple(str(question) for question in (open_questions or ()))

    gaps = tuple(_gaps(sources, by_kind))

    risks: list[str] = []
    for source in sources:
        if not source.present:
            continue
        report = by_kind.get(source.kind)
        if report is None:
            continue
        risks.extend(_risk_items(source, report))

    supplied_notes = notes or {}
    conflicts = tuple(str(item) for item in supplied_notes.get("conflicts", ()) or ())
    alternatives = tuple(str(item) for item in supplied_notes.get("alternatives", ()) or ())

    needs_review = tuple(_needs_review(sources, by_kind, questions))
    safety = readiness(sources, unverified_claims, questions)

    return InternalReport(
        safety=safety,
        headline=_headline(safety),
        gaps=gaps,
        risks=tuple(risks),
        conflicts=conflicts,
        alternatives=alternatives,
        needs_review=needs_review,
        sources=sources,
        unverified_claims=unverified_claims,
        open_questions=questions,
        generated_at=generated_at,
    )


def now_stamp() -> str:
    """
    طابع زمني UTC بصيغة ثابتة — **يُمرَّر إلى** :func:`build` ولا يُقرأ داخلها.

    ⚠️ والسبب: ``build`` يجب أن تكون **دالّة نقية** فتعطي المدخل نفسه المخرج
    نفسه (واختبار ``test_ordering_is_fixed_and_stable`` يعتمد على ذلك). وقراءة
    الساعة داخل البناء تجعل تقريرين من مدخل واحد مختلفين، وهو عين ما يمنعه
    ``review.py`` في صدره حين رفض حالةً على مستوى الوحدة.
    """
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def to_json(report: InternalReport) -> str:
    """
    يُسلسل التقرير JSON بلا تشفير ASCII — فالعربية تُقرأ في الواجهة والسجل.
    """
    return json.dumps(report.to_dict(), ensure_ascii=False, indent=2)
