"""
حلقة المراجعة والإعادة — خطأٌ يُصلَح، ثم يُعاد الفحص، ثم يُعرَض ما بقي.
================================================================================

المشكلة التي يحلّها
------------------
الفحوص قائمة وتعمل، وكلٌّ منها يكتب تقريره:

* `citations.py`      — هل الاقتباس موجود حرفياً في مقطع استرجعناه؟
* `attribution.py`    — هل هذا النصّ نصُّ المادة التي نُسب إليها؟
* `facts.py`          — هل المسودّة أمينة على سجلّ الوقائع؟
* `review.py`         — ماذا يُؤخذ على المسودّة من وجه الموجز والمقتطفات؟
* `language_audit.py` — هل الصياغة خالية من عيوب التحرير؟

**وكلّها تُبلّغ ولا تُصلح.** فالمسودّة تخرج من `main.py::_stream_agent` بكلّ ما
رُصد فيها، ويُترك الإصلاح للمحامي — أو يُعاد التوليد من أوّله بلا حدّ. والحلقة
بين «الفحص» و«الإصلاح» كانت تعيش في رأس إنسان أو في محادثة، وقد سجّل
`briefing.py` ثمن ذلك: **ثلاث مراجعات مستقلّة وصفت مذكرات بالاكتمال وهي تحمل
أساس أجرٍ خاطئاً، وتاريخاً خاطئاً، ومادة منسوبة إلى غير مادّتها، وواقعة مُغيَّرة
ثلاث مرّات.**

فهذا الملف يجعل تلك الحلقة **مساراً واحداً محدوداً**: يُجمع ما رصدته الفحوص في
قائمة واحدة، ثم يُعاد الصياغة للإصلاح، ثم يُعاد الفحص، ثم يتوقّف — **ويعرض ما
بقي بدل أن يخفيه.**

ثلاث قواعد تحمل الملف كله
-------------------------
**١) قائمة واحدة، بشكل واحد، وأنواع الوحدات نفسها.** لا مفردات ثانية للأخطاء
   (انظر `LoopError.kind`)، ولا فحص يُخترع لم يُشغَّل.

**٢) الحلقة محدودة ومتقاربة.** سقف معلن، وتوقّف مبكّر حين لا يبقى قابل للإصلاح،
   وتوقّف ثانٍ حين لا تنقص الأخطاء — **فالمحاولة التي لا تُنقص خطأً إنفاقٌ من وقت
   المحامي ومال الموكّل بلا مقابل.**

**٣) الباقي يُعرَض.** `material_remaining` لا تفرغ لأن المحاولات نفدت، و
   `describe` يقوله بالعربية. ⚠️ **ولا رقم ثقة ولا نسبة ولا متوسّط في هذا الملف**:
   الأرقام تُغري بالاعتماد على ما لا تحمله. وتقدير النموذج لنفسه ليس دليلاً —
   فالذي يُبنى عليه هنا **وجود الخطأ أو غيابه**، وهو أمر يُقاس بقواعد معلنة لا
   بتقدير. (ولذلك `is_fixable` دالّة صافية من الخطأ نفسه، لا من عدّ ولا من درجة.)

⚠️ **والحدّ الأوّل، معلناً لا مخفيّاً:** هذا الملف **لا يفحص نصّاً عربياً بنفسه**،
ولا يحكم على صواب المسودّة قانوناً. هو يجمع مخرجات الفحوص ويرتّب قرارها ويعيد
النداء. والحكم القانوني للمحامي.

⚠️ **والحدّ الثاني:** `can_be_called_verified` **ليست شهادة على المستند** — هي
أقصى ما يبلغه هذا التشغيل، وشرطها أن تكون الفحوص الأربعة قد جرت وأن لا يبقى خطأ
مادّي وأن يكون الإيقاف لخلوص الفحص لا لنفاد المحاولات. وفي أفضل حالاتها تبقى
تقريراً عن الفحوص. **ولا يوجد في هذا الملف مدخل يُنتج عبارةً معناها أن المستند
صالح للتسليم** (انظر `NEVER_SAY`).

كيف يُختبر بلا نموذج ولا شبكة
-----------------------------
**`redraft` و`collect` يُمرَّران وسيطين لا يُستدعيان من هذا الملف.** والحلقة التي
لا يمكن اختبارها إلا بنداء نموذج **حلقة لا يختبرها أحد**: بلا شبكة، وبلا مفتاح،
وبلا قرص، وبلا حالة. وهذا شرط لا تحسين — وهو المبدأ نفسه المكتوب في صدر
`citations.py` و`facts.py`.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable, Sequence

# الأنواع والمفردات تُستورد ولا يُعاد تعريف شيء منها: `kind` في هذا الملف هو
# **نوع الوحدة الأمّ نفسه**، ودرجات الخطورة هي درجاتها، وحالات الإسناد هي
# حالاتها. ولو كتب هذا الملف مفرداته لصار للمشروع قاموسان للأخطاء نفسها.
from attribution import (
    ERROR_STATUSES,
    STATUS_ABSENT,
    STATUS_MATCHED,
    STATUS_MISMATCHED,
    Attribution,
    AttributionOutcome,
)

# `normalize` يُستورد ولا يُعاد كتابته، على القاعدة المكتوبة في `review.py`
# و`facts.py`: تطبيعان في مشروع واحد يفترقان عند أول تعديل، فيُقرأ الخطأ نفسه
# مرّة «أُصلح» ومرّة «لم يُصلح». وهو ما يقرّر عدّ `fixed` أدناه.
from citations import normalize
from facts import FactShift
from language_audit import LanguageFinding, LanguageReport
from review import ReviewFinding, ReviewOutcome

# ==============================================================================
# ١. المصادر — أسماء الوحدات كما تُكتب في `LoopError.source`
# ==============================================================================
# أسماء لا نصوص حرّة: تُقارَن في الاختبار وفي `sources_checked`، والنصّ الحرّ
# يُكتب مرة «fidelity» ومرة «facts» فلا يُطابق شيء.

SOURCE_REVIEW = "review"
SOURCE_FIDELITY = "fidelity"
SOURCE_ATTRIBUTION = "attribution"
SOURCE_LANGUAGE = "language"

#: مصادر الخطأ **بترتيبها الثابت** — وهو ترتيب العرض أيضاً.
#:
#: ⚠️ **والترتيب جزء من العقد لا من المدخلات**: لو رُتّبت القائمة على ترتيب
#: الوسائط الممرَّرة لتغيّر شكل التقرير بتغيّر ترتيب النداء، ولتغيّر بين نداءين
#: بالمدخلات نفسها — وهو ما يمنعه `test_the_same_inputs_give_the_same_outcome`.
SOURCES: tuple[str, ...] = (
    SOURCE_REVIEW,
    SOURCE_FIDELITY,
    SOURCE_ATTRIBUTION,
    SOURCE_LANGUAGE,
)

#: أسماء المصادر بالعربية — **للعرض وحده**.
#:
#: ⚠️ وهي ليست نسخاً لأسماء `briefing.py`: تلك صفوف تقرير داخلي بعدّادات، وهذه
#: عناوين بنود خطأ في حلقة إصلاح. والقيمة الآلية تبقى `LoopError.source` بلا ترجمة.
SOURCE_LABELS: dict[str, str] = {
    SOURCE_REVIEW: "المراجعة الثانية",
    SOURCE_FIDELITY: "أمانة الوقائع",
    SOURCE_ATTRIBUTION: "نسبة النصوص إلى موادها",
    SOURCE_LANGUAGE: "التدقيق اللغوي",
}

#: درجتا الخطورة — **نفس مفردات `review.py` و`language_audit.py` حرفاً بحرف**.
#:
#: ⚠️ ولا يُعرَّف ثالث: الخطورة التي لا تمنع التسليم ولا تُطلب من المحامي لا معنى
#: لها. والاختبار `test_the_severity_vocabulary_is_the_project_vocabulary` يثبّت
#: أن هاتين هما درجتا `review.SEVERITIES` المُعلَنتان.
SEVERITY_ERROR = "error"
SEVERITY_NOTICE = "notice"

SEVERITY_LABELS: dict[str, str] = {
    SEVERITY_ERROR: "يمنع التسليم",
    SEVERITY_NOTICE: "للعلم",
}

#: ⚠️ **عبارات لا تظهر في مخرجات هذا الملف بحال.**
#:
#: وهذا ليس تلطّفاً في الصياغة بل حارس على أعلى ما يستطيع الملف أن يقوله.
#: `briefing.py` تعلّم الدرس نفسه: أعلى درجاته تقول «هذا تقرير عن الفحوص لا شهادة
#: بصحّة المستند»، ولا مدخل فيه يُنتج وصفاً بالجاهزية. ولو كتب هذا الملف «المسودّة
#: صالحة للإيداع» بعد حلقة نظيفة، لكان قد شهد بما لا يملكه: الفحوص تغطّي ما
#: تُغطّيه، والحكم القانوني للمحامي.
#:
#: والاختبار `test_describe_never_says_ready_to_file` يمرّ على كل شكل مُنتَج.
NEVER_SAY: tuple[str, ...] = (
    "جاهز",
    "صالح للإيداع",
    "صالح للتسليم",
    "يمكن إيداعه",
    "مكتمل",
    "تمّ التحقّق",
    "متحقَّق منه بالكامل",
    "ready to file",
)

#: نصوص السياسة التي تُلحَق برسائل الأخطاء التي لا تُصلحها إعادة الصياغة.
#:
#: ⚠️ **ووجودها نصّاً صريحاً مقصود**: المحامي يقرأ «لماذا لا تُصلحه محاولة أخرى»
#: لا «هذا خطأ» فقط. والنصّ نفسه يُختبَر (`test_an_arithmetic_finding_is_not_fixed_by_rewriting`).

#: يُلحَق باعتراض `arithmetic` من `review.py`.
#:
#: و`review.py` يمنع المراجع من الحساب صراحةً («ولا تحسب: لا تجمع ولا تطرح ولا
#: تُحوّل»)، فكل اعتراض `arithmetic` هو بالبناء على رقم **لم تحتسبه المسودّة**.
#: ولذلك لا يُصلحه نداء ثانٍ: إعادة كتابة الرقم تُنتج رقماً آخر لا سند له، والمطلوب
#: أن يُحتسب بأداة أو يُمرَّر من بيانات الملف.
ARITHMETIC_MUST_BE_COMPUTED = (
    "الرقم لا يُصحَّح بإعادة الصياغة: يجب أن يُحتسب بأداة أو يُمرَّر من بيانات "
    "الملف، ثم يُكتب في المسودّة كما احتُسب. وإعادة كتابته تخميناً تُنتج رقماً "
    "آخر لا سند له."
)

#: يُلحَق بحالة `absent` في `attribution.py`.
ARCHIVE_DOES_NOT_HOLD = (
    "المادة ليست في المقاطع المسترجَعة، فلا يُنشئها نداءُ صياغة: يُطلب استرجاعها، "
    "أو يُذكر في المستند صراحةً أنها لم تُتوفَّر، ويُنظر في السند بدلاً منها."
)


# ==============================================================================
# ٢. القرار — ثلاثة، لا أكثر
# ==============================================================================


class LoopAction(str, Enum):
    """
    ما يُفعل بالخطأ داخل الحلقة.

    ⚠️ **والفرق بين `report_only` و`stop` ليس فرقاً في الاحتمال بل في السبب**:
    الأول خطأ معروف أن إصلاحه **خارج نصّ المسودّة** (المادة ليست في الأرشيف،
    والرقم يحتاج أداة)، والثاني خطأ **جوهري لا تُنفَق عليه محاولة** لأن إصلاحه
    قرار أو لأن هذا الملف لا يعلن له قاعدة إصلاح. وكلاهما يُعرَض على المحامي،
    وكلاهما لا يُمرَّر إلى `redraft`.

    و`stop` **لا يوقف الحلقة بنفسه**: الحلقة تتوقّف حين لا يبقى خطأ بـ`redraft`.
    فالاسم وصفٌ للخطأ («لا تُهدر عليه محاولة») لا أمرٌ بإيقاف المسار — وقد كان
    الخطأ في أوّل تصوّر أن يُقرأ الأمر على أنه إيقاف، فيتوقّف المسار عند خطأ
    مادّي **وخطأ آخر قابل للإصلاح بجانبه** كان يمكن أن يُصلح.
    """

    #: خطأ قابل للإصلاح بإعادة صياغة.
    REDRAFT = "redraft"
    #: لا يُصلح بإعادة الصياغة — يُعرَض على المحامي.
    REPORT_ONLY = "report_only"
    #: خطأ جوهري — لا تُهدر محاولة عليه.
    STOP = "stop"


@dataclass(frozen=True)
class LoopError:
    """
    خطأ واحد في قائمة واحدة، **مأخوذ من الوحدة التي رصدته**.

    Attributes:
        source: أيّ وحدة رصدته: ``review`` · ``fidelity`` · ``attribution`` ·
                ``language``.
        kind:   **نوع الوحدة الأمّ نفسه، بلا تغيير** (``fact`` · ``reworded`` ·
                ``mismatched`` · ``markdown`` …).
        severity: ``error`` يمنع التسليم، أو ``notice`` للعلم.
        message: الخطأ بالعربية، كما كتبته الوحدة، **مع نصّ السياسة إن كان لا
                يُصلح بإعادة الصياغة**.
        quote:  النصّ من المسودّة الذي يقف عليه الخطأ، أو ``""`` إن لم يكن له
                نصّ (واقعة غائبة، أو إسناد إلى مادة لم تُسترجَع).
        action: ماذا تفعل الحلقة به.
        fixable_by_redraft: هل تُصلحه محاولة أخرى؟ ⚠️ **وهو مشتقّ من `action`**،
                ويُحسب بالقاعدة نفسها (`is_fixable`)، فلا يفترق الحقلان.

    ⚠️ **ولماذا `kind` نوع الوحدة الأمّ لا مفردات جديدة لهذا الملف؟**
    لأن القاموس الثاني **ينحرف عن الأول**: تُضاف في `review.py` خمسة أنواع،
    فيبقى هذا الملف يعرف أربعة، فيقع خطأ `arithmetic` في خانة «غير معروف» أو
    يُترجم إلى «رقم» فيُقرأ نوعاً آخر. **وهذا المشروع دفع ثمن «شيئين لشيء واحد»
    مرّتين، ومسجَّلتان**:

    * جدول أرقام ثانٍ في `facts.py` (`_DIGIT_TRANSLATION`: عشرون محرفاً مقابل
      عشرة) رفع `ValueError` عند الاستيراد، **ولا شيء كان يستورد الوحدة، فالسويت
      الأخضر لم يقل شيئاً** — ووُلد `tests/test_module_health.py` من ذلك العطب.
    * و`review.py` يستورد `MIN_QUOTE_CHARS` ويشرح السبب: عتبتان لعبارة واحدة
      تعني أن تُقبل العبارة في ملف وتُرفض في آخر — **والفرق صامت**.

    فالنوع يُمرَّر كما هو، والقارئ يعرف من `source` أيّ قاموس يفتح.
    """

    source: str
    kind: str
    severity: str
    message: str
    quote: str
    action: LoopAction
    fixable_by_redraft: bool


# ==============================================================================
# ٣. من الخطأ إلى القرار — القواعد المعلنة
# ==============================================================================
# الجدولان أدناه هما **نصّ القاعدة**، لا شرحاً لها: كل نوع مذكور فيهما له حكم
# معلن، وما ليس فيهما له حكم صريح أيضاً (`LoopAction.STOP`) فلا يمرّ صامتاً.
#
# ⚠️ **والسبب في تمييز الأنواع عن «الخطورة» وحدها:** الخطورة تقول «هل يمنع
# التسليم؟»، ولا تقول «هل ينفعه نداء آخر؟». وقد يكون خطأ مانع لا ينفعه نداء
# (الرقم، والمادة الغائبة)، وملاحظة لا تمنع ولا ينفعها نداء. فالخطورة للعرض،
# وهذا الجدول للقرار.

#: الأنواع التي **تُصلحها إعادة الصياغة** — وفيها إصلاحها ممكن بنصّ جديد.
_REDRAFT_KINDS: dict[str, frozenset[str]] = {
    # مخالفة الموجز، والإغفال، وغياب السند، وحجّة لم تُجب: كلّها تُصلح بنصّ.
    # ولا `arithmetic` هنا، ولا `strength` (الأخير تقدير قوّة حجّة لا نصّ).
    SOURCE_REVIEW: frozenset({"fact", "omission", "unsupported"}),
    # الواقعة القُلبت أو أُعيدت صياغتها: نصّ جديد يردّها إلى السجلّ.
    # ⚠️ ولا `missing`: انظر `_action_for` — غياب الواقعة قرار المحامي.
    SOURCE_FIDELITY: frozenset({"contradicted", "reworded"}),
    # نصّ صحيح منسوب إلى مادة ليست له: يُنقل إلى مادّته فيُصلح.
    SOURCE_ATTRIBUTION: frozenset({STATUS_MISMATCHED}),
    # ⚠️ و`markdown` وحده من أنواع `language_audit.py` هنا، على ما نُصّ عليه.
    # و`preamble` — افتتاح حواري — خارج الجدول فيقع في `STOP`: صياغته تُصلح
    # بنصّ جديد، لكن قاعدة إصلاحه لم تُعلَن في هذا الملف، **فلا يُدَّعى له حكم
    # لم يُكتب**، ويُعرَض على المحامي. ومن أراد إدخاله فليكتبه هنا صريحاً
    # وليُتبعه باختباره — لا أن يُترك للفهم الضمني.
    SOURCE_LANGUAGE: frozenset({"markdown"}),
}

#: الأنواع التي **لا تُصلحها إعادة الصياغة، وإصلاحها خارج نصّ المسودّة**.
_REPORT_ONLY_KINDS: dict[str, frozenset[str]] = {
    # المادة ليست في الأرشيف: نداء الصياغة لا يُنشئ نصّاً غير موجود.
    SOURCE_ATTRIBUTION: frozenset({STATUS_ABSENT}),
    # الرقم يحتاج أداة حساب، لا نصّاً جديداً.
    SOURCE_REVIEW: frozenset({"arithmetic"}),
}


def _action_for(source: str, kind: str, severity: str) -> LoopAction:
    """
    الحكم على خطأ واحد — **القاعدة الواحدة في هذا الملف**.

    وترتيب الفحص مقصود:

    1. **الملاحظة لا تُصلَح بإعادة صياغة أبداً.** ولو أُعيدت الصياغة لأجلها
       لأنفقت الحلقة محاولات على ما لا يمنع التسليم، **فيتعلّم المحامي ألّا يقرأ
       التقرير** — وهو الدرس المدفوع الثمن في `language_audit.py` (أحد عشر
       سلوكاً صحيحاً وُسمت أخطاءً، فصار التقرير جداراً أحمر).
    2. **الأنواع المعلَنة قابلة للإصلاح** ⇒ `redraft`.
    3. **وما إصلاحه خارج المسودّة** ⇒ `report_only` بنصّ السياسة الملحق.
    4. **وما بقي**: نوع مجهول، أو `missing`، أو `strength`، أو `preamble` ⇒
       `stop`. وهذا هو الموضع الذي يمنع أخطر ما يمكن أن يقع: أن يُقرأ **غياب
       قاعدة** على أنه «خطأ بسيط يُصلحه نداء». **والجهل يُعلَن، ولا يُخمَّن.**
    """
    if severity != SEVERITY_ERROR:
        return LoopAction.REPORT_ONLY
    if kind in _REDRAFT_KINDS.get(source, frozenset()):
        return LoopAction.REDRAFT
    if kind in _REPORT_ONLY_KINDS.get(source, frozenset()):
        return LoopAction.REPORT_ONLY
    return LoopAction.STOP


def is_fixable(error: LoopError) -> bool:
    """
    هل يُبرّر هذا الخطأ محاولة إعادة صياغة أخرى؟

    ⚠️ **دالّة صافية من الخطأ وحده — لا من عدّ، ولا من نسبة، ولا من درجة.**

    وهذا هو جواب هذا الملف على الشرط الذي بُني عليه الطلب: **لا يُعتمد على
    تقدير النموذج لنفسه ولا على رقم ثقة لإثبات الصواب.** فالسؤال «هل نحاول
    مرّة أخرى؟» يُجاب عنه بنوع الخطأ ومصدره ودرجته — ثلاثة حقول منظورة — ولا
    يُجاب عنه بـ«الثقة ٠٫٧ فنتوقّف». والرقم يُغري بالاعتماد عليه: يُقرأ «٠٫٩»
    فيُسلَّم مستند لم يُفحص، ويُقرأ «٠٫٤» فيُعاد العمل على مستند سليم.

    ⚠️ **والحكم يُعاد حسابه هنا ولا يُقرأ من `error.fixable_by_redraft`**: الحقل
    مشتقّ، ومشتقٌّ يُكتب بيده في اختبار أو في مسار آخر قد يخالف القاعدة. فالقراءة
    من القاعدة تُبقي حكم الحلقة صحيحاً وإن أُسيء بناء `LoopError` يدوياً.

    والقواعد المعلنة، بترتيبها:

    * `mismatched` (إسناد)، و`contradicted` و`reworded` (واقعة)، و`fact`
      و`omission` و`unsupported` (مراجعة ثانية)، و`markdown` (صياغة) ⇒ **نعم**.
    * ``severity == "notice"`` ⇒ **لا**: الملاحظة لا تُنفق عليها محاولة.
    * `absent` (مادة ليست في الأرشيف) ⇒ **لا**: إعادة الصياغة لا تُنشئ نصّاً.
    * `arithmetic` (رقم) ⇒ **لا**: الرقم يُحتسب بأداة أو يُمرَّر، ولا يُعاد كتابته.
    * وما عدا ذلك — `missing`، و`strength`، ونوع مجهول — ⇒ **لا**: قاعدة إصلاحه
      غير معلَنة، والجهل يُعرَض على المحامي ولا يُخمَّن عليه.

    >>> error = LoopError(
    ...     source=SOURCE_REVIEW, kind="fact", severity=SEVERITY_ERROR,
    ...     message="خ", quote="اقتباس", action=LoopAction.REDRAFT,
    ...     fixable_by_redraft=True,
    ... )
    >>> is_fixable(error)
    True
    >>> is_fixable(
    ...     LoopError(
    ...         source=SOURCE_REVIEW, kind="arithmetic", severity=SEVERITY_ERROR,
    ...         message="خ", quote="اقتباس", action=LoopAction.REPORT_ONLY,
    ...         fixable_by_redraft=False,
    ...     )
    ... )
    False
    """
    return _action_for(error.source, error.kind, error.severity) is LoopAction.REDRAFT


# ==============================================================================
# ٤. الجمع — قائمة واحدة من عدة مصادر
# ==============================================================================


def _loop_error(source: str, kind: str, severity: str, message: str, quote: str) -> LoopError:
    """
    يبني `LoopError` **والحقلان المشتقّان من دالّة واحدة**.

    ⚠️ وهذا هو موضع منع «شيئين لشيء واحد»: `action` و`fixable_by_redraft` يُكتبان
    هنا معاً من `_action_for`، فلا يصير في المشروع موضعان يحكمان على الخطأ نفسه
    بحكمين. والاختبار `test_the_derived_fields_are_one_decision` يمسح كل خطأ مُنتَج
    ويتحقّق من التطابق.
    """
    action = _action_for(source, kind, severity)
    return LoopError(
        source=source,
        kind=kind,
        severity=severity,
        message=message,
        quote=quote,
        action=action,
        fixable_by_redraft=action is LoopAction.REDRAFT,
    )


def _review_errors(findings: Sequence[ReviewFinding]) -> list[LoopError]:
    """
    اعتراضات `review.py` بعينها — ونوعها ودرجتها يمرّان كما هما.

    ⚠️ و`arithmetic` يُلحَق بنصّ السياسة: الاعتراض يبقى كما كتبه المراجع (فيه
    الرقم المشكوك فيه ولماذا)، ويُضاف إليه أن إصلاحه ليس في الصياغة. ولو
    استُبدلت رسالته لضاع موضع الشكّ الذي يحتاجه المحامي ليُحتسب الرقم.
    """
    errors: list[LoopError] = []
    for finding in findings:
        message = finding.message
        if finding.kind == "arithmetic":
            message = f"{message}\n{ARITHMETIC_MUST_BE_COMPUTED}"
        errors.append(
            _loop_error(
                source=SOURCE_REVIEW,
                kind=finding.kind,
                severity=finding.severity,
                message=message,
                quote=finding.quote,
            )
        )
    return errors


def _fidelity_errors(shifts: Sequence[FactShift]) -> list[LoopError]:
    """
    افتراقات `facts.check_fidelity` — ونوعها كما هو (``missing`` · ``reworded`` ·
    ``contradicted``).

    ⚠️ **والدرجة ``error`` للثلاثة، والسبب مكتوب هنا لأنه محلّ خلاف ظاهر.**
    `FactShift` لا يحمل درجة، وعتبات `check_fidelity` **معروفة بأنها تُنذر على
    إعادة الصياغة المشروعة** (وذلك مصرَّح به في `facts.py`: «الإنذار الكاذب
    المعلن»). فلو جُعل `reworded` ملاحظةً لما حرّك محاولةً أبداً — وقد نُصّ على
    أنه **قابل للإصلاح بإعادة الصياغة**، والملاحظة لا تحرّك محاولة. فوسمُه خطأً
    هو الثمن المعلن، **وحدّه أن الحلقة تتوقّف إذا لم تنقص الأخطاء**
    (``STOP_NO_PROGRESS``): فمحاولة على إنذار كاذب لا تتكرّر مرّتين.

    ⚠️ **ونصّ الواقعة يُذكر في الرسالة** لأن الافتراق لا يُراجَع بطرف واحد:
    «لم تُذكر» بلا نصّها لا يقول للمحامي ما الذي سقط.
    """
    errors: list[LoopError] = []
    for shift in shifts:
        message = (
            f"[{shift.fact_key}] {shift.note} "
            f"والواقعة في السجلّ: «{shift.fact_statement}»."
        )
        errors.append(
            _loop_error(
                source=SOURCE_FIDELITY,
                kind=shift.kind,
                severity=SEVERITY_ERROR,
                message=message,
                quote=shift.draft_text,
            )
        )
    return errors


def _attribution_errors(outcome: AttributionOutcome) -> list[LoopError]:
    """
    نتائج `attribution.verify_attributions` — والمطابق **لا يُنتج خطأً**.

    ⚠️ **والباقي مُكمَّل بقوّة الحصيلة نفسها**: الحالات التي تنقض صراحةً هي
    ``attribution.ERROR_STATUSES``، فيُقرأ منها. ولو كتب هذا الملف
    ``status == "mismatched"`` بنفسه لكان حكماً ثانياً على الحالة نفسها —
    ولو أُضيفت حالة مانعة في `attribution.py` لما رآها هذا الملف.

    ⚠️ **و`found_in` لا يُهمَل**: «النصّ صحيح لكنه في مادة أخرى» و«النصّ غير
    موجود في أيّ مقطع» عيبان مختلفان، وإصلاح الأول **نقل** والثاني **حذف أو
    تصحيح سند**. فالنصّان يُكتبان في الرسالة كما هما.
    """
    errors: list[LoopError] = []
    for check in outcome.checks:
        if check.status == STATUS_MATCHED:
            continue
        severity = (
            SEVERITY_ERROR if check.status in ERROR_STATUSES else SEVERITY_NOTICE
        )
        if check.status == STATUS_MISMATCHED:
            message = f"النصّ المنسوب إلى «{check.reference}» ليس نصّ هذه المادة."
            if check.found_in:
                message += (
                    f" والنصّ موجود في المقطع {check.found_in} — يُنقل إلى مادّته "
                    "بدل أن يُحذف."
                )
            else:
                message += (
                    " ولم يُوجد النصّ في أيّ مقطع مسترجَع — يُحذف أو يُصحَّح سنده."
                )
        else:
            message = (
                f"الإسناد إلى «{check.reference}»: المادة غير موجودة في المقاطع "
                f"المسترجَعة. {ARCHIVE_DOES_NOT_HOLD}"
            )
        errors.append(
            _loop_error(
                source=SOURCE_ATTRIBUTION,
                kind=check.status,
                severity=severity,
                message=message,
                quote=check.quote,
            )
        )
    return errors


def _language_errors(findings: Sequence[LanguageFinding]) -> list[LoopError]:
    """
    ملاحظات `language_audit.audit_language` — ونوعها ودرجتها كما هما.

    و`sample` يُنقل إلى `quote`: هو مقتطف من المستند نفسه (وقد يُقلَّم بطرفيه
    «…» للعرض)، وهو أقرب ما في ذلك التقرير إلى نصّ المسودّة.
    """
    errors: list[LoopError] = []
    for finding in findings:
        message = finding.message
        if finding.line is not None:
            message = f"{message} (السطر {finding.line})"
        errors.append(
            _loop_error(
                source=SOURCE_LANGUAGE,
                kind=finding.kind,
                severity=finding.severity,
                message=message,
                quote=finding.sample,
            )
        )
    return errors


def sources_checked(
    *,
    review_outcome: ReviewOutcome | None = None,
    fidelity_shifts: Sequence[FactShift] | None = (),
    attribution_outcome: AttributionOutcome | None = None,
    language_report: LanguageReport | None = None,
) -> tuple[str, ...]:
    """
    أيّ الفحوص **جرت فعلاً** — لمن أراد أن يعرف قبل أن يُبنى على القائمة حكم.

    ⚠️ **وهذه الدالّة هي مانع العطب الذي وُلد `briefing.py` لمنعه:** «الفحص
    الغائب والفحص الذي لم يجد شيئاً حقيقتان مختلفتان». فقائمة الأخطاء وحدها لا
    تُفرّق بين «فُحصت المسودّة فلم يُوجد عيب» و«لم يُفحص شيء» — **وكلتاهما قائمة
    فارغة.** فمن أراد الحكم على النظافة يجب أن يسأل هذه الدالّة، لا أن يقرأ فراغاً.

    ⚠️ **و`fidelity_shifts=None` هي طريقة القول «لم أُشغّل `check_fidelity`»**؛
    وأمّا الافتراضي `()` فمعناه «شُغّل ولم يُنتج افتراقاً» — لأن `check_fidelity`
    تُعيد مجموعة الافتراقات، وفراغها نتيجةٌ لا غياب. ومن لم يُشغّلها فليمرّر
    `None` صريحاً؛ **والافتراض هنا ليس شهادةً بالسلامة بل بيانٌ بما أُعطي.**

    >>> sources_checked(review_outcome=ReviewOutcome(), fidelity_shifts=None)
    ('review',)
    >>> sources_checked(review_outcome=ReviewOutcome())
    ('review', 'fidelity')
    """
    checked: list[str] = []
    if review_outcome is not None:
        checked.append(SOURCE_REVIEW)
    if fidelity_shifts is not None:
        checked.append(SOURCE_FIDELITY)
    if attribution_outcome is not None:
        checked.append(SOURCE_ATTRIBUTION)
    if language_report is not None:
        checked.append(SOURCE_LANGUAGE)
    return tuple(checked)


def collect_errors(
    draft: str,
    *,
    review_outcome: ReviewOutcome | None = None,
    fidelity_shifts: Sequence[FactShift] | None = (),
    attribution_outcome: AttributionOutcome | None = None,
    language_report: LanguageReport | None = None,
) -> tuple[LoopError, ...]:
    """
    يجمع مخرجات الفحوص في **قائمة واحدة بشكل واحد**، بلا اختراع فحص لم يُشغَّل.

    ⚠️ **والمكوّن الممرَّر `None` لا يُسهم بشيء ولا يُقرأ نظيفاً.** فالغياب لا
    يُترجم إلى «لا خطأ» بأيّ حال: لا يُضاف خطأ ولا تُضاف ملاحظة، **ويسأل المستدعي
    `sources_checked` ليعرف ما جرى.** والقاعدة صريحة في `briefing.py`، وهذا
    الملف يلتزمها ولا يخترع لها بديلاً.

    ⚠️ **و`draft` تُمرَّر ولا تُقرأ هنا.** وهذا مقصود ومعلن: **هذا الملف لا يفحص
    نصّاً عربياً بنفسه** — الحكم كلّه للوحدات المذكورة في `source`، ولو فحص هنا
    لصار في المشروع حاكمان على النصّ نفسه يفترقان. ووجود الوسيط في التوقيع مقصود:
    هو الموضع الوحيد الذي يصل إليه نصّ المسودّة، فأيُّ فحص حتمي مستقبلي يقرأ النصّ
    يجد بابه هنا بدل أن تُغيَّر التواقيع كلها.

    والترتيب حتمي: المصادر بترتيب `SOURCES`، وداخل كل مصدر بترتيب ورود نتائجه
    — **فالترتيب جزء من العقد**، والاختبار
    `test_the_same_inputs_give_the_same_outcome` يثبّته.

    >>> from review import ReviewFinding
    >>> finding = ReviewFinding(
    ...     kind="fact", severity="error", message="مخالفة للموجز",
    ...     quote="تأخّر المستأجر عن سداد الأجرة",
    ... )
    >>> errors = collect_errors("مسودّة", review_outcome=ReviewOutcome([finding]))
    >>> errors[0].source, errors[0].kind, errors[0].severity
    ('review', 'fact', 'error')
    >>> errors[0].action.value
    'redraft'
    >>> collect_errors("مسودّة")
    ()
    """
    errors: list[LoopError] = []

    if review_outcome is not None:
        errors.extend(_review_errors(review_outcome.findings))
    if fidelity_shifts is not None:
        errors.extend(_fidelity_errors(fidelity_shifts))
    if attribution_outcome is not None:
        errors.extend(_attribution_errors(attribution_outcome))
    if language_report is not None:
        errors.extend(_language_errors(language_report.findings))

    return tuple(errors)


# ==============================================================================
# ٥. الحلقة
# ==============================================================================

#: أكواد الإيقاف — **قيمة آلية تُقارَن**، ونصّها العربي في `STOP_MESSAGES`.
#:
#: ⚠️ ولماذا كود ونصّ؟ لأن النصّ العربي يُعرض على المحامي فيُحرَّر ويُطوَّل، ولا
#: يجوز أن يتوقّف منطق `can_be_called_verified` على صياغته. والقيمة الآلية تُقارَن
#: بلا هشاشة. وهذا هو الفرق نفسه الذي فُرض في `briefing.py` بين درجة السلامة
#: (`SAFETY_RANK`) ونصّها المعروض.
STOP_CLEAN = "clean"
STOP_NOTHING_FIXABLE = "nothing_fixable"
STOP_CEILING = "ceiling"
STOP_NO_PROGRESS = "no_progress"
STOP_REDRAFT_FAILED = "redraft_failed"

#: أسباب الإيقاف بالعربية — **وهي التي تُعرَض في `describe`**.
STOP_MESSAGES: dict[str, str] = {
    STOP_CLEAN: "لم يبقَ خطأ في آخر فحص — فلا محاولة تُنفَق على مسودّة نظيفة.",
    STOP_NOTHING_FIXABLE: (
        "لا خطأ قابلاً للإصلاح بإعادة الصياغة: ما بقي إمّا ملاحظة، وإمّا خطأ "
        "إصلاحه خارج نصّ المسودّة أو قرار المحامي — ولا تُنفَق عليه محاولة."
    ),
    STOP_CEILING: (
        "استُنفدت المحاولات المحدودة قبل أن تنقى المسودّة — والخطأ الباقي "
        "معروض أدناه، ولم يُزَل بعرضه."
    ),
    STOP_NO_PROGRESS: (
        "إعادة الصياغة لم تُنقص عدد الأخطاء، فأُوقفت المحاولات بدل إنفاق ما بقي "
        "منها على مسودّة لا تتقارب."
    ),
    STOP_REDRAFT_FAILED: (
        "إعادة الصياغة لم تُنتج نصّاً صالحاً، فبقيت آخر مسودّة مفحوصة كما هي "
        "بدل استبدالها بفراغ."
    ),
}

#: سقف المحاولات الافتراضي.
#:
#: ⚠️ **والحدّ ليس تفصيلاً تنفيذياً:** حلقة بلا سقف هي **إنفاق غير محدود من وقت
#: المحامي ومال الموكّل**، ولا يقول أحد للمحامي إنها ما زالت تدور. وثلاث محاولات
#: كافية لأن الحلقة تتوقّف قبلها حين لا تتقارب.
DEFAULT_MAX_ATTEMPTS = 3

# ⚠️ **ولا مصدر اصطناعي في هذا الملف** (لا ``source="loop"`` ولا ما يشبهه):
# الخطأ بلا وحدة راصدة لا يُخترع له مصدر، لأن `source` هو ما يُبنى عليه `kind`،
# ونوعٌ بلا وحدة أمّ يصير مفردات ثانية — وهو ما يمنعه صدر الملف.

#: توقيعات الدوالّ المحقونة — تُكتب صراحةً ليقين المستدعي.
Redraft = Callable[[str, tuple[LoopError, ...], int], str]
Collect = Callable[[str, int], tuple[LoopError, ...]]
Progress = Callable[["Attempt"], None]


@dataclass(frozen=True)
class Attempt:
    """
    محاولة واحدة **بعد فحصها**: المسودّة التي كانت قيد الفحص، وما رُصد فيها.

    Attributes:
        number:    رقم المحاولة، يبدأ من ١. والأولى هي المسودّة الواردة نفسها.
        draft:     المسودّة **كما فُحصت** (لا كما أُعيدت صياغتها بعد الفحص).
        errors:    ما رُصد في هذه المسودّة، بالترتيب نفسه الذي تُنتجه
                   `collect_errors`.
        fixed:     كم خطأً من المحاولة السابقة **لم يعد قائماً** في هذه
                   (``0`` في المحاولة الأولى، فلا سابقة لها).
        remaining: عدد ما رُصد في هذه المحاولة — أي ``len(errors)``، مكتوباً
                   صريحاً ليكون في السجلّ بلا حساب.

    ⚠️ **ولماذا تُحفظ المسودّة في كل محاولة؟** لأن الحلقة بلا سجلّ محاولات
    تُقرأ نتيجتها بلا سياق: «بقي خطأ واحد» لا تقول أكان في مسودّة لم تُلمس أم في
    مسودّة أُصلح فيها أربعة. والمسودّات محفوظة، فمن أراد أن يقابل بينها قابَل.
    """

    number: int
    draft: str
    errors: tuple[LoopError, ...]
    fixed: int
    remaining: int


@dataclass(frozen=True)
class LoopResult:
    """
    حصيلة الحلقة كاملة — **بما بقي، لا بما أُصلح وحده**.

    Attributes:
        attempts:      المحاولات بترتيبها.
        final_draft:   آخر مسودّة **فُحصت** — وهي التي تُسلَّم بعد الحلقة.
                       ⚠️ ولا تكون مسودّةً لم تُفحص أبداً: إعادة الصياغة لا تصير
                       نهائية إلا بعد فحصها في المحاولة التالية.
        stopped_reason: سبب الإيقاف **بالعربية** — يُعرَض كما هو.
        stop_code:     السبب قيمةً آلية (``STOP_CLEAN`` …) لمنطق الحكم.
        material_remaining: **الخطأ المادّي الباقي** الذي يمنع التسليم. ⚠️ وهو
                       لا يفرغ لأن المحاولات نفدت: نفاد المحاولات سببُ عرضٍ لا
                       سببُ إخفاء.
        attempts_used: عدد المحاولات المنفَقة فعلاً.
        remaining:     **كل** ما بقي في آخر فحص، أخطاءً وملاحظات — فلا تُطوى
                       الملاحظة لأنها لا تمنع. و`material_remaining` جزءٌ منه.
        notices_remaining: الملاحظات الباقية وحدها.
        checked_sources: الفحوص التي **أُعلن** أنها جرت، بترتيب `SOURCES`.
                       ⚠️ ولا يعرفها `run_loop` بنفسه: هو ينادي `collect` ولا
                       يرى داخلها. فتُمرَّر صريحاً (ومن `sources_checked` عادةً)،
                       **وافتراضها الفراغ يعني «لم يُعلَن» — فيبقى الحكم متحفّظاً
                       ولا يُوصف المستند بأنه مُتحقَّق منه.**

    ⚠️ **ولا حقل ثقة ولا نسبة في هذا الصنف، ولا يُحسب منه شيء من هذا القبيل.**
    """

    attempts: tuple[Attempt, ...]
    final_draft: str
    stopped_reason: str
    material_remaining: tuple[LoopError, ...]
    attempts_used: int
    stop_code: str = STOP_CLEAN
    remaining: tuple[LoopError, ...] = ()
    notices_remaining: tuple[LoopError, ...] = ()
    checked_sources: tuple[str, ...] = ()

    @property
    def unrun_sources(self) -> tuple[str, ...]:
        """
        الفحوص التي **لم تُعلَن** أنها جرت.

        ⚠️ وغيابها **يُعرَض ولا يُقرأ سلامة**: هي الحدّ الذي يمنع أن يُقرأ فراغُ
        قائمة الأخطاء على أنه شهادة نظافة.
        """
        return tuple(
            source for source in SOURCES if source not in self.checked_sources
        )

    @property
    def fixed_total(self) -> int:
        """مجموع ما أُصلح خلال الحلقة كلها (مجموع `fixed` على المحاولات)."""
        return sum(attempt.fixed for attempt in self.attempts)

    @property
    def can_be_called_verified(self) -> bool:
        """
        هل بلغ هذا التشغيل حدّاً يجوز معه أن يُقال «مُتحقَّق منه»؟ — **لا، في كل
        حال إلا حالة واحدة، وهي ليست شهادة على المستند.**

        ⚠️ **وهي `False` في كل حال إلا إذا اجتمع ثلاثة:**

        1. **الفحوص الأربعة كلها أُعلن أنها جرت** — فغياب فحص يمنع الحكم، **لأن
           ما لم يُفحص لا يُشهد له** (وهو نصّ القاعدة في `briefing.py`).
        2. **ولا خطأ مادّي باقٍ** — والباقي يُعرَض ولا يُطوى.
        3. **وكان الإيقاف لخلوص الفحص** (`STOP_CLEAN`)، لا لنفاد محاولات ولا
           لتقاربٍ متوقّف. فالتوقّف لسبب آخر **ليس نجاحاً**، ولو خلا آخر فحص من
           خطأ مادّي.

        ⚠️ **ولا يُقاس شيء من هذا برقم**: لا نسبة ثقة، ولا متوسّط، ولا تقدير
        النموذج لنفسه. الأرقام تُغري بالاعتماد على ما لا تحمله — والمطلوب حكمٌ
        يُبنى على ما جرى فعلاً.

        ⚠️ **وحتى في هذه الحالة فالحدّ باقٍ:** `verified` هنا تعني «الفحوص
        المعروفة جرت ولم تُبلّغ عن خطأ»، لا «المستند صحيح قانوناً». ولذلك لا
        يوجد في الملف مدخل يُنتج وصفاً بالجاهزية (انظر `NEVER_SAY`) — وهذا ما
        يثبّته `test_describe_never_says_ready_to_file`.
        """
        if self.unrun_sources:
            return False
        if self.material_remaining:
            return False
        if self.stop_code != STOP_CLEAN:
            return False
        return True


def _identity(error: LoopError) -> tuple[str, str, str]:
    """
    هويّة الخطأ في العدّ: (المصدر، النوع، نصّه المطبَّع).

    ⚠️ **والرسالة لا تدخل الهوية** حيث يوجد نصّ: المراجع الثاني يُعيد صياغة
    اعتراضه نفسه بكلمات أخرى في الفحص التالي، فلو كانت الهوية بالنصّ الكامل
    لَحُسب الخطأ الذي أُصلح **جديداً** — وهو إفشاء لرقم كاذب في تقرير المحامي.

    ⚠️ **والتطبيع من `citations.normalize`** لا من تطبيع خاص: الهوية تُبنى على
    النصّ نفسه الذي يُبنى عليه فحص المطابقة، فلا يُقرأ الخطأ نفسه خطأين لاختلاف
    تشكيل أو رقم هندي.

    وإذا كان نصّ الخطأ فارغاً (واقعة غائبة، أو إسناد إلى مادة لم تُسترجَع) فالرسالة
    تقوم مقامه — وإلا لتشابهت وقائع غائبة مختلفة في هويّة واحدة.
    """
    return (error.source, error.kind, normalize(error.quote) or error.message)


def _fixed_count(
    previous: tuple[LoopError, ...], current: tuple[LoopError, ...]
) -> int:
    """
    كم خطأً من الفحص السابق لم يعد قائماً في الفحص الحالي.

    والمقابلة **بعدد لا بمجموعة**: خطأان بهويّة واحدة (واقعتان غائبتان بالنوع
    نفسه) يُقابَلان بخطأين، فلا يُحسب أحدهما مُصلَحاً لأن الآخر بقي.
    """
    if not previous:
        return 0
    remaining = [_identity(error) for error in current]
    fixed = 0
    for error in previous:
        key = _identity(error)
        if key in remaining:
            remaining.remove(key)
        else:
            fixed += 1
    return fixed


def _stop_text(code: str, max_attempts: int, used: int, detail: str = "") -> str:
    """
    نصّ سبب الإيقاف بالعربية، ومع السقف يُذكر العدد فلا يبقى الرقم مجهولاً.

    و``detail`` تفصيلٌ يُلحَق عند الحاجة (نوع استثناء نداء إعادة الصياغة مثلاً)،
    **لأن الإيقاف يُعلَن بسببه**: سببٌ مجهول لا يستطيع المحامي أن يتصرّف فيه.
    """
    text = STOP_MESSAGES[code]
    if code == STOP_CEILING:
        text = f"{text} (السقف المعلن: {max_attempts} محاولة · المستنفد: {used}.)"
    if detail:
        text = f"{text} {detail}"
    return text


def run_loop(
    draft: str,
    redraft: Redraft,
    collect: Collect,
    *,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    on_progress: Progress | None = None,
    checked_sources: Sequence[str] | None = None,
) -> LoopResult:
    """
    يشغّل الحلقة: يفحص، فإن بقي خطأ قابل للإصلاح أعاد الصياغة وفحص من جديد —
    **بحدّ معلن، وبلا إنفاق محاولة على ما لا يُصلحه نداء.**

    والوسيطان `redraft` و`collect` **محقونان لا مستدعيان من هنا**:

    * `collect(draft, attempt)` — يعيد قائمة `LoopError` للمسودّة. و`attempt`
      عدد المحاولات المنفَقة قبله (يبدأ من ٠)، فيعرف الفاحص أيّ جولة هذه.
    * `redraft(draft, errors, attempt)` — يعيد مسودّة جديدة. **و`errors` هي
      الأخطاء القابلة للإصلاح وحدها** (`is_fixable`)، ولا تُمرَّر إليها الأخطاء
      التي لا يُصلحها نداء: أن تُعطى لدالّة إعادة الصياغة أخطاءُ لا تستطيع
      إصلاحها هو أن تُطلب منها أن تتظاهر بإصلاحها.

    ⚠️ **ولماذا الحقن؟** لأن الحلقة التي لا يمكن اختبارها إلا بنداء نموذج
    **حلقة لا يختبرها أحد**: بلا شبكة، وبلا مفتاح API، وبلا قرص، وبلا نموذج.
    وهذا المبدأ نفسه المكتوب في صدر `citations.py` و`facts.py` — وما لا يُشغَّل
    في الاختبار لا يُعوَّل عليه.

    ⚠️ **والسقف مفروض لا موعود:** `max_attempts` أقلّ من ١ يرفع `ValueError`.
    حلقة بلا سقف **إنفاق غير محدود من وقت المحامي ومال الموكّل**، ولا أحد يقول
    للمحامي إنها ما زالت تدور. والقيمة الافتراضية ٣.

    ⚠️ **والتوقّفات خمسة**، وكلٌّ منها يُقال بالعربية في `stopped_reason`
    وتُقابله قيمة آلية في `stop_code`:

    * خلوص الفحص: لا خطأ في آخر فحص (`STOP_CLEAN`).
    * لا خطأ قابلاً للإصلاح: ما بقي ملاحظة أو قرار محامٍ (`STOP_NOTHING_FIXABLE`)
      — **ولا تُنفَق محاولة لأن ملاحظات بقيت**.
    * نفاد السقف (`STOP_CEILING`).
    * **عدم التقارب**: عدد الأخطاء لم ينقص بعد إعادة الصياغة
      (`STOP_NO_PROGRESS`) — فيتوقّف المسار ولا يُنفق ما بقي من محاولات على
      مسودّة لا تتقارب.
    * وإعادة صياغة لم تُنتج نصّاً — لفراغٍ أو لاستثناء في النداء
      (`STOP_REDRAFT_FAILED`) — فتُبقى آخر مسودّة **مفحوصة** بدل استبدالها
      بفراغ أو بإسقاط التوليد كلّه.

    ⚠️ **والاستثناء في نداء إعادة الصياغة لا يُسقِط ما بُني، لكنه يُعلَن.** وهذا
    هو سلوك `main.py::_review_round` نفسه: «الفشل هنا لا يُسقط التوليد أبداً —
    لكنه يُعلَن ولا يُسكَت عنه». فالمحامي يستلم آخر مسودّة مفحوصة **ومعها أخطاؤها
    وسبب التوقّف**، وهو خيرٌ من انقطاع بعد جولات، ومن صمتٍ يُقرأ نجاحاً.

    ⚠️ **وحدّ هذا الباب معلن:** `collect` **لا يُلتقط استثناؤه هنا** — هو نداء
    الفحص، وصاحبه هو من يُعلن فشله (كما يفعل `main.py::_review_round` بـ
    ``failed: True``). فلو التقطناه لأنتجنا حصيلةً لا تعرف حالة المسودّة، وقائمةً
    فارغة قد تُقرأ نظافة. والفشل الذي لا يُعرف موضعه لا يُخترع له حكم.

    ⚠️ **ولا طباعة ولا إدخال/إخراج هنا**: من أراد بثّ إطار في الواجهة يمرّر
    `on_progress`، فيُنادى بالمحاولة بعد تسجيلها ليبثّ ما يشاء. والحلقة نفسها
    صامتة، فتُستدعى من اختبار ومن خدمة بالشكل نفسه.

    >>> def collect(draft, attempt):
    ...     if draft == "مسودّة معطوبة":
    ...         return collect_errors(
    ...             draft, review_outcome=ReviewOutcome([
    ...                 ReviewFinding(
    ...                     kind="fact", severity="error", message="مخالفة",
    ...                     quote="نصّ المسودّة",
    ...                 ),
    ...             ]),
    ...         )
    ...     return ()
    >>> def redraft(draft, errors, attempt):
    ...     return "مسودّة مصحّحة"
    >>> result = run_loop("مسودّة معطوبة", redraft, collect)
    >>> result.attempts_used, result.stopped_reason == STOP_MESSAGES[STOP_CLEAN]
    (2, True)
    >>> result.final_draft, result.material_remaining
    ('مسودّة مصحّحة', ())
    >>> result.can_be_called_verified
    False
    """
    if isinstance(max_attempts, bool) or not isinstance(max_attempts, int):
        raise ValueError(
            f"max_attempts يجب أن يكون عدداً صحيحاً، وجاء {max_attempts!r}."
        )
    if max_attempts < 1:
        raise ValueError(
            f"max_attempts يجب أن يكون ١ على الأقلّ، وجاء {max_attempts} — "
            "فالحلقة بلا محاولة ليست حلقة، والتي بلا سقف إنفاق غير محدود."
        )
    if not isinstance(draft, str):
        raise ValueError(f"المسودّة يجب أن تكون نصاً، وجاء {type(draft).__name__}.")

    declared = tuple(checked_sources) if checked_sources is not None else ()

    attempts: list[Attempt] = []
    current = draft
    previous: tuple[LoopError, ...] = ()
    stop_code = STOP_NOTHING_FIXABLE
    detail = ""
    number = 0

    while True:
        errors = tuple(collect(current, number))
        number += 1

        attempt = Attempt(
            number=number,
            draft=current,
            errors=errors,
            fixed=_fixed_count(previous, errors),
            remaining=len(errors),
        )
        attempts.append(attempt)
        if on_progress is not None:
            on_progress(attempt)

        fixable = tuple(error for error in errors if is_fixable(error))

        if not errors:
            # خلوص الفحص: لا شيء يُصلح ولا شيء يُعرض. وهو التوقّف الوحيد الذي
            # يسمح بالحكم بأن الفحوص التي جرت لم تُبلغ عن خطأ.
            stop_code = STOP_CLEAN
            break

        if not fixable:
            # ما بقي لا يُصلحه نداء: ملاحظة، أو رقم، أو مادة غائبة، أو نوع لم
            # تُعلَن قاعدة إصلاحه. **ولا تُنفَق محاولة لأن ملاحظات بقيت.**
            stop_code = STOP_NOTHING_FIXABLE
            break

        if number >= max_attempts:
            # السقف. ⚠️ والخروج هنا **بعد** الفحص وقبل إعادة الصياغة: فلا نداء
            # نموذج يقع ثم تُهمَل نتيجته، ولا مسودّة تُبنى ولا تُفحص.
            stop_code = STOP_CEILING
            break

        if previous and len(errors) >= len(previous):
            # لم تنقص الأخطاء: المسودّة لا تتقارب، وإعادة النداء إنفاق بلا
            # مقابل. والفحص بعد المحاولة الأولى فقط (`previous` غير فارغة).
            stop_code = STOP_NO_PROGRESS
            break

        # إعادة الصياغة: **الموضع الوحيد الذي ينفق محاولة**. ونتيجتها لا تصير
        # نهائية هنا، بل تُفحص في الجولة التالية — فلا مسودّة تُسلَّم بلا فحص.
        try:
            new_draft = redraft(current, fixable, number)
        except Exception as exc:  # noqa: BLE001
            # ⚠️ وفشلُ النداء لا يُسقِط ما بُني، **لكنه يُعلَن بنوعه**: سببٌ
            # مجهول لا يستطيع المحامي أن يتصرّف فيه. والمسودّة الباقية هي آخر
            # مسودّة **فُحصت**، ومعها أخطاؤها — لا فراغ ولا انقطاع.
            stop_code = STOP_REDRAFT_FAILED
            detail = f"السبب: {type(exc).__name__}."
            break

        if not isinstance(new_draft, str) or not new_draft.strip():
            # إعادة صياغة فارغة أو غير نصّية: تُبقى آخر مسودّة **مفحوصة**، لأن
            # تسليم فراغ أسوأ من تسليم مسودّة فيها خطأ معروف ومُعلَن.
            stop_code = STOP_REDRAFT_FAILED
            break

        previous = errors
        current = new_draft

    final = attempts[-1]
    material = tuple(
        error for error in final.errors if error.severity == SEVERITY_ERROR
    )
    notices = tuple(
        error for error in final.errors if error.severity != SEVERITY_ERROR
    )

    return LoopResult(
        attempts=tuple(attempts),
        final_draft=final.draft,
        stopped_reason=_stop_text(stop_code, max_attempts, len(attempts), detail),
        stop_code=stop_code,
        material_remaining=material,
        attempts_used=len(attempts),
        remaining=final.errors,
        notices_remaining=notices,
        checked_sources=declared,
    )


# ==============================================================================
# ٦. العرض — ما جرى، وما بقي، وما لم يُفحص
# ==============================================================================


def _verification_blockers(result: LoopResult) -> list[str]:
    """
    أسباب منع وصف المستند بأنه مُتحقَّق منه — **بالعربية، سبباً سبباً**.

    ⚠️ وذكرُ الأسباب لا يكفي فيها إشارة إلى `can_be_called_verified`: القارئ
    يحتاج أن يعرف **ما الذي ينقص بالتحديد** ليعالجه. و«مُتحقَّق منه: لا» بلا
    سبب تُقرأ حكماً مبهماً، و«لم يُشغَّل فحص الإسناد» تُقرأ عملاً مطلوباً.
    """
    reasons: list[str] = []
    for source in result.unrun_sources:
        reasons.append(
            f"فحص لم يُشغَّل: {SOURCE_LABELS.get(source, source)} — "
            "وغيابه ليس سلامة، ولا نتيجة تُقرأ منه."
        )
    if result.material_remaining:
        reasons.append(
            f"خطأ مادّي باقٍ: {len(result.material_remaining)} — معروض أعلاه ولا "
            "يُخفى."
        )
    if result.stop_code != STOP_CLEAN:
        reasons.append(
            "سبب الإيقاف ليس خلوص الفحص: "
            f"{STOP_MESSAGES.get(result.stop_code, result.stop_code)}"
        )
    if result.remaining and not result.material_remaining:
        reasons.append(
            f"ملاحظات باقية: {len(result.remaining)} — تُعرَض ولا تمنع، ولا "
            "تُقرأ نظافة."
        )
    if not reasons:
        # لا يُبلَغ هذا الفرع إلا بحصيلة متناقضة بُنيت يدوياً. والصمت هنا كان
        # سيقول «لا مانع» عن حالة يدّعي فيها الحقلان غير المتّفقين شيئين.
        reasons.append(
            "الحصيلة متناقضة: لا سبب معلن، و`can_be_called_verified` ليست صحيحة "
            "— فيُعاد الفحص بدل الاعتماد على حصيلة لا تُقرأ."
        )
    return reasons


def describe(result: LoopResult) -> str:
    """
    تقرير عربي: ما جُرّب، وما أُصلح، وما بقي، **وأيّ فحص لم يُشغَّل**.

    ⚠️ **ولا يقول هذا النصّ إن المستند صالح للتسليم، في أيّ حال** — ولا في أفضل
    حالاتها. وهذا شرط لا صياغة: الملف الذي يقول «انتهى» عن مستند لم يُفحص كلّه
    هو بعينه العطب الذي وُلد `briefing.py` لمنعه (مذكرات وُصفت بالاكتمال وفيها
    أساس أجرٍ خاطئ). والاختبار `test_describe_never_says_ready_to_file` يمرّ على
    كل شكل مُنتَج، **ومنها الأحسن**.

    ⚠️ **ونصوص الفحوص تُنقل كما هي، ولا تُنقّى.** فلو قال فحصٌ «المستند جاهز»
    لظهرت عبارته منسوبةً إليه، لأن تنقيتها **إخفاء** — والإخفاء ممنوع في هذا
    الملف أشدّ من منع عبارة. والقاعدة المحفوظة أن يعرف القارئ **من قالها**.

    >>> result = LoopResult(
    ...     attempts=(), final_draft="مسودّة", stopped_reason="سبب",
    ...     material_remaining=(), attempts_used=0,
    ... )
    >>> "لا يُوصف هذا المستند" in describe(result)
    True
    >>> "جاهز" in describe(result)
    False
    """
    lines: list[str] = ["حلقة المراجعة والإعادة — ما جرى وما بقي", ""]

    lines.append(
        f"المحاولات: {result.attempts_used} · أُصلح خلال الحلقة: "
        f"{result.fixed_total} · بقي في آخر فحص: {len(result.remaining)} "
        f"(منها ما يمنع التسليم: {len(result.material_remaining)})."
    )
    lines.append(f"سبب الإيقاف: {result.stopped_reason}")

    if result.checked_sources:
        lines.append(
            "الفحوص التي جرت: "
            + " · ".join(
                SOURCE_LABELS.get(source, source) for source in result.checked_sources
            )
            + "."
        )
    else:
        lines.append("الفحوص التي جرت: لا شيء أُعلن — فلا فحص يُنسب إليه هذا التقرير.")

    unrun = result.unrun_sources
    if unrun:
        lines.append(
            "الفحوص التي لم تُشغَّل: "
            + " · ".join(SOURCE_LABELS.get(source, source) for source in unrun)
            + " — وغياب الفحص ليس سلامة، ولا يُقرأ سكوتاً عن خطأ."
        )
    else:
        lines.append("الفحوص التي لم تُشغَّل: لا شيء — الفحوص الأربعة أُعلن أنها جرت.")

    if result.remaining:
        lines.append("")
        lines.append("ما بقي معروضاً عليك، ولا يُخفى:")
        for index, error in enumerate(result.remaining, 1):
            label = SEVERITY_LABELS.get(error.severity, error.severity)
            lines.append(
                f"  {index}. [{SOURCE_LABELS.get(error.source, error.source)} · "
                f"{error.kind} · {label}] {error.message}"
            )
            if error.quote.strip():
                lines.append(f"     الاقتباس: «{error.quote.strip()}»")
    else:
        lines.append("")
        lines.append("لم يبقَ خطأ في آخر فحص — لا مادّي ولا ملاحظة.")

    lines.append("")
    if result.can_be_called_verified:
        lines.append(
            "الحكم: الفحوص الأربعة جرت ولم يبقَ خطأ مادّي، ولم يتوقّف المسار إلا "
            "لخلوص الفحص. وهذا تقرير عن الفحوص لا شهادة بصحّة المستند، والقرار "
            "للمحامي."
        )
    else:
        lines.append("الحكم: لا يُوصف هذا المستند بأنه مُتحقَّق منه قبل التسليم:")
        lines.extend(
            f"  • {reason}" for reason in _verification_blockers(result)
        )

    return "\n".join(lines)
