"""
فصل النقل الحرفي عن الصياغة القانونية — أهذا نصُّ القانون أم صياغة الكاتب؟
=============================================================================

السؤال الثالث
-------------
`citations.py` يجيب سؤالاً واحداً: **«هل هذا النصّ موجود في ما استرجعناه؟»** —
فيمنع **التأليف**. و`attribution.py` يجيب سؤالاً ثانياً: **«أهذا نصُّ المادة
التي نُسب إليها؟»** — فيمنع **النسبة الكاذبة**. وهذا الملف يجيب سؤالاً ثالثاً
لم يجب عنه واحدٌ منهما:

    **أهذا نقلٌ حرفيّ أصلاً، أم صياغةٌ للكاتب؟**

`attribution.py` يسأل **لمن** هذا النصّ. وهذا الملف يسأل **أهو نصّ منقول**
أم عملُ الكاتب — وأيّ تغيير في النقل يغيّر المعنى. والسؤالان لا يتداخلان: نصّ
مؤلَّف من الكاتب قد يُنسب إلى مادة صحيحة فيمرّ من `attribution.py` (المقطع
يحمل المادة، والنصّ موجود فيه إن كان الكاتب نقل حرفاً)، ونصّ حرفيّ ١٠٠٪ قد
يُنسب إلى المادة الخطأ فيمسكه `attribution.py` وحده.

العيبان اللذان وُلد هذا الملف منهما
-----------------------------------
**العيب الأول — مطابقة متسامحة تسمح بتغيير المعنى.**

`quote_in_text` في `citations.py` يُطبّع النصّين بـ`normalize`، و`normalize`
**يمحو الترقيم كله** ويطوي الألف والياء والتاء المربوطة. وقد سُجّل هذا حدّاً
مقبولاً هناك (انظر `review.py`: «حدّ في المطابقة نفسها»). والعيب **مُشاهَد
بالتشغيل**، لا مفترض:

    quote_in_text("لا يفسخ العقد للمالك فوراً", "…لا، يفسخ العقد للمالك فوراً")
    == True

والفاصلة مُحيَت، **والفاصلة قد تقلب المعنى**: «لا، يفسخ» ليست «لا يفسخ».
فالأولى نفيٌ للفسخ، والثانية إثباتٌ له مع أداة نفي معلَّقة على ما قبلها. فالفحص
القائم يمنع التأليف ولا يمنع **القراءة الخاطئة** — وهذا الملف هو محلّ القاعدة
الأشدّ، كما نصّ `review.py` نفسه.

**العيب الثاني — صياغة الكاتب تُقدَّم على أنها نصّ المادة.**

كتبت مذكرة أن مادةً «تنصّ على كذا وكذا» **بكلمات الكاتب**، بلا علامات اقتباس.
والقارئ لا سبيل له إلى معرفة: أهذا نصّ المادة أم ملخّص الكاتب؟ والمستند يبدو
موثَّقاً في الحالتين، لأن الشكل واحد. والنصّ الواجب ليس منع التلخيص — فالتلخيص
مشروع بل مطلوب — بل **منع تقديم كلام الكاتب على أنه كلام القانون**.

المبدأ التصميمي — كـ`citations.py` و`attribution.py` و`review.py`
-----------------------------------------------------------------
> **النموذج يروي، والخادم يُقرّر.**

- **بلا تبعية خارجية** — مكتبة بايثون القياسية وحدها، **ولا استيراد من
  `citations`**. والسبب مكتوب في موضعه: التطبيع الذي نحتاجه هنا هو **نقيض**
  التطبيع هناك (انظر القسم ٢).
- **بلا حالة وبلا إدخال/إخراج وبلا شبكة وبلا طبع** — دوالّ نقية تُختبر مباشرة.
- **بلا أرشيف وبلا نموذج**: النصّ الذي يُطابَق به الاقتباس يُمرَّر **مُحقوناً**
  في `source_of`، فتعمل الوحدة في أي مسار (API، أو سكربت، أو اختبار).

ما يقبله الملف وما يرفضه — القاعدة في سطر
-----------------------------------------
> **لا يجوز أن يختلف الاقتباس عن مصدره إلا في المسافات، وفي التشكيل
> والكشيدة، وفي صور أرقامه. وكل اختلاف آخر يُبلَّغ عنه ولا يُمحى صامتاً.**

فالتشكيل والكشيدة والأرقام **زخرفة ورسم** لا كلمات، والمسافات فواصل أسطر في
الاستخراج. أما **الترقيم فليس زخرفة**: الفاصلة وعلامة النفي قد تحملان المعنى،
فهما **يُقارنان ولا يُمحيان**، واختلافهما `PUNCTUATION_CHANGED` لا يُقبل.
واختلاف أيّ كلمة `WORD_CHANGED` لا يُقبل، ويُسمّى المتغيّر بعينه.

حدود معلنة — تُقرأ مع النتيجة
-----------------------------
١. **حدود الكلمات لا تُفحص:** الشرط أن تكون **حروف** الاقتباس متّصلة في المصدر،
   لا أن تبدأ الكلمة الأولى عند حدّ كلمة في المصدر. فاقتباسٌ يبدأ داخل كلمة
   أطول يُقبل إن كانت حروفه متّصلة. وهذا مقصود: الشائع في الصياغة القانونية أن
   يُقتطع الاقتباس بعد واو العطف المتّصلة («ويجب…» ← «يجب…»)، ورفضه يُنذر عن
   اقتباس أمين — **وأداة تُنذر دائماً لا تُقرأ**. والثمن **تسامح** في حدّ الكلمة
   لا اتّهام كاذب، وهو الاتّجاه المقبول في هذا المشروع (`attribution.py`، الحدّ
   الثالث). ومن أراد تشديده فليشدّده في الموجّه: **يُطلب إلى النموذج أن يبدأ
   الاقتباس عند حدّ كلمة**.
٢. **تسمية الكلمات المخالفة تقريبية حين تتفرّق الكلمات المتطابقة.** التسمية
   تُبنى على **أطول مقطع متطابق** كمرساة، ثم تُقارَن نافذة من المصدر بطول
   الاقتباس. والحكم (رفض) لا يتغيّر — التسمية للبيان لا للحكم.
٣. **`WORD_CHANGED` يشترط تطابق نصف كلمات الاقتباس** (واثنتين على الأقل).
   فما دون ذلك لا تُعرف له مقابلة في المصدر، فيُقال `MISSING` («غير موجود»).
   والفرق **في التفسير لا في النتيجة**: الحالتان مرفوضتان معاً، ولا يُنسب إلى
   الاقتباس مقابلٌ لم يثبت.
٤. **الاقتباس غير المغلَق لا يُعدّ اقتباساً:** «بلا » لا تُقرأ اقتباساً، لأن كل
   ما بعدها يصير منقولاً إلى آخر المستند. والنتيجة **تغطية ناقصة** لا اتهام.
٥. **القرن بين الاقتباس والمرجع جوارٌ لا فهم.** يُقرن كل اقتباس بأقرب مرجع إليه
   **في جملته** (المرور الأول)، ثم بأقرب مرجع متبقٍّ على أيّ حال (المرور
   الثاني). فإن تنازع اقتباسان مرجعاً واحداً في جملة واحدة أخذه أقربهما،
   وتُرِك الآخر **بلا مرجع** — يُعرَض ملاحظةً ولا يُطابَق بمصدر قد لا يكون له.
   والعلاج في الموجّه: **اقتباس واحد لكل مرجع**.
٦. **`source_of` يحقن النصّ الذي رآه النموذج**، لا النصّ الكامل للمقطع. وهذا
   مبدأ `citations.py` نفسه: السؤال «هل اقتبس ممّا أُعطي؟» لا «هل هذا في
   القاعدة؟». وما يُحقن هنا هو ما يُحاكَم عليه، فلا يُوسَّع ولا يُضيَّق.
"""

from __future__ import annotations

import difflib
import math
import re
import unicodedata
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Optional, Sequence

# ==============================================================================
# ١. أنواع المطابقة
# ==============================================================================


class MatchKind(str, Enum):
    """
    حصيلة مقارنة اقتباس بمصدره — أسماء ثوابت لا نصوص حرّة، لأنها تُقارَن في
    `summarize` وفي أي مسار يستدعي الوحدة. والنصّ الحرّ يُكتب مرة `punctuation`
    ومرة `punctuations` فلا يُطابق شيء.
    """

    #: مطابق بعد توحيد المسافات وصور العرض (NFKC) وحدهما — لم يُغيَّر حرف.
    EXACT = "exact"
    #: الفرق محصور في التشكيل أو الكشيدة أو صور الأرقام — رسمٌ لا كلمة.
    FORMATTING_ONLY = "formatting_only"
    #: الكلمات هي هي، والترقيم تغيّر — يُراجَع، ولا يُقبل.
    PUNCTUATION_CHANGED = "punctuation_changed"
    #: كلمة أو أكثر تغيّرت — لا يُقبل.
    WORD_CHANGED = "word_changed"
    #: لا مقابلة للاقتباس في المصدر — لا يُقبل.
    MISSING = "missing"


#: ما يُقبل من الحالات: الفرق الجائز وحده. وكل ما عداه **يُبلَّغ عنه**.
_ACCEPTED_KINDS = frozenset({MatchKind.EXACT, MatchKind.FORMATTING_ONLY})


@dataclass(frozen=True)
class StrictMatch:
    """
    حصيلة مطابقة صارمة واحدة.

    Attributes:
        kind:        نوع الفرق — انظر `MatchKind`.
        quote:       الاقتباس **كما أُعطي**، لا مطبَّعاً: ما يُعرض على المحامي
                     يجب أن يكون ما في مسودّته ليجده فيها.
        source_span: ما قابل الاقتباس في المصدر، أو ``""`` إن لم يوجد. وهو
                     **موضع المصدر**، فيرى المحامي بمَ قُوبل الاقتباس.
        changed:     ما تغيّر بعينه، بالعربية: الكلمات المخالفة أو الترقيم
                     المخالف. ولا يُترك فارغاً في حالة رفض يُنسب فيها تغيير.
    """

    kind: MatchKind
    quote: str
    source_span: str = ""
    changed: tuple[str, ...] = ()

    def accepted(self) -> bool:
        """
        أيُقبل هذا الاقتباس نقلٌ حرفيّ؟

        >>> strict_match("المادة 246", "المادة ٢٤٦").accepted()
        True
        >>> strict_match("لا يفسخ العقد", "لا، يفسخ العقد").accepted()
        False
        """
        return self.kind in _ACCEPTED_KINDS


# ==============================================================================
# ٢. التطبيع الصارم — ولماذا لا يُستورد `normalize` من `citations.py`
# ==============================================================================
# ⚠️ **هذا الملف لا يستورد `normalize` ولا يستدعيه، ولا يجوز أن يتقاربا.**
#
# `normalize` هناك غايته **أن يمحو** ما نحن هنا مطالبون **بحفظه**: يطوي «أ/ا»
# و«ة/ه» و«ى/ي»، ويستبدل **كل ترقيم** بفراغ. وذاك صواب في موضعه: التحقّق من
# وجود سند لا يجوز أن يبطل باختلاف رسم. أما هنا فالسؤال ليس «هل وُجد؟» بل
# «هل نُقل كما هو؟» — والجواب على السؤال الثاني يقتضي **ألّا يُمحى الفرق قبل
# الحكم عليه**، لأنه هو نفسه الدليل.
#
# ⚠️ ولو استُدعي `normalize` هنا لصار العيب الذي جاء هذا الملف له يمرّ من هذا
# الملف أيضاً: الفاصلة تُمحى فيعود `PUNCTUATION_CHANGED` إلى `EXACT` — أي أن
# وحدتين في مشروع واحد تعطيان حكماً **متعاكساً** على العبارة نفسها. والاختبار
# `test_strict_match_and_quote_in_text_disagree_on_the_comma_case` يُثبّت
# اختلافهما **باسمه**، فمن حاول جمعهما يوماً رأى الفشل لا الصمت.
#
# ⚠️ **ولا تُطبَّق هنا فروق الرسم التي يطويها `normalize`** (أ/ا · ة/ه · ى/ي):
# هي — بخلاف التشكيل والأرقام — قد تكون **فرق كلمة**، فلا تُطوى، بل تُقارَن.
# وما كان منها فرق رسم في نظر القارئ يبلغ عنه المحامي ويتصرّف.

#: التشكيل وعلامات الضبط — زخرفة لا حروف.
_MARKS = re.compile(r"[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED]")

#: الكشيدة (التطويل) — حشو بصري لا قيمة له.
_TATWEEL = "\u0640"

#: صور الأرقام العربية-الهندية والمشرقية والمغربية إلى اللاتينية. جدول واحد
#: في هذا الملف، مكتوب مرّة واحدة: تكرار الجدول يُنتج جدولين يفترقان عند أول
#: تعديل، فيُطابَق «٤» بـ«٤» ولا يُطابَق بـ«4» بلا سبب ظاهر.
_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")

#: محارف التحكّم غير المرئية (تأتي من الاستخراج من PDF) — لا يُنقل منها شيء.
_CONTROL = re.compile(r"[\u200b-\u200f\u202a-\u202e\u2066-\u2069\ufeff]")

#: كل ما ليس حرفاً ولا رقماً ولا فراغاً = **ترقيم**. ووجوده هنا **للقارنة** لا
#: للمحو، بخلاف `_NOT_WORD` في `citations.py`.
_PUNCT_CHAR = re.compile(r"[^\w\s]", re.UNICODE)

#: الكلمات والترقيم — وحدتان تُقارَنان وحدةً وحدة.
_TOKEN = re.compile(r"\w+|[^\w\s]", re.UNICODE)

#: الفراغات المتعدّدة تُطوى إلى فراغ واحد.
_WHITESPACE = re.compile(r"\s+")


@dataclass(frozen=True)
class _Folded:
    """
    نصّ بعد الطيّ المسموح، مع خريطة إزاحات إلى المصدر.

    Attributes:
        text:  النصّ المطويّ الذي تجري عليه المقارنة.
        index: `index[k]` = موضع المحرف `k` في `base`، وطولها ``len(text)+1``
               (الأخير حدّ النهاية). بها يُستخرج من المصدر **الرسم الخام** لما
               قابله الاقتباس، لا النصّ المطويّ.
        base:  المصدر بعد NFKC — الإزاحات تُقاس عليه. ولو أُزيحت هذه الخريطة
               لَعُرض على المحامي موضعٌ غير الذي قُوبل فعلاً، وهو أسوأ من عدم
               عرض الموضع.
    """

    text: str
    index: tuple[int, ...]
    base: str


def _next_significant(base: str, start: int, *, drop_marks: bool) -> str:
    """
    أول محرف ذي دلالة بعد `start` — أي بعد إسقاط ما سيُسقطه الطيّ.

    والغرض: معرفة هل الفراغ ملاصق **لترقيم** من جهة اليمين. ومحارف الزخرفة
    تُتخطّى في السؤال، لأنها ستُحذف من النصّ المطويّ فلا تفصل بين شيء.
    """
    position = start
    while position < len(base):
        char = base[position]
        if _CONTROL.match(char):
            position += 1
            continue
        if drop_marks and (_MARKS.match(char) or char == _TATWEEL):
            position += 1
            continue
        return char
    return ""


def _fold(text: str, *, drop_marks: bool) -> _Folded:
    """
    يطوي نصّاً بالمسموح وحده، ويعيد معه خريطة الإزاحات.

    المسموح، بالترتيب:

    1. **NFKC** — صور العرض العربية (ﻻ، ﺁ …) التي ينتجها استخراج PDF.
    2. حذف محارف التحكّم غير المرئية (علامات الاتجاه والفراغ الصفري).
    3. طيّ الفراغات إلى فراغ واحد، وحذف الأطراف.
    4. **إسقاط الفراغ الملاصق لترقيم** — فرقُ فراغٍ حول فاصلة `formatting` لا
       كلمة، فلو لم يُسقط لخرج `PUNCTUATION_CHANGED` على «لا، يفسخ» مقابل
       «لا،يفسخ» — **إنذار كاذب عن مسافة**. (وهذا لا يمسّ الفاصلة نفسها: هي
       تبقى وتُقارَن.)
    5. **إن `drop_marks`:** حذف التشكيل والكشيدة، وطيّ صور الأرقام.

    ⚠️ **ولا يُحذف ترقيم أبداً**، ولا تُطوى صور الألف والياء والتاء المربوطة —
    فذلك فرقُ كلمةٍ يُبلَّغ عنه، لا زخرفة.

    >>> _fold("المُستَأجِر  عن\\nسداد", drop_marks=True).text
    'المستأجر عن سداد'
    >>> _fold("لا، يفسخ", drop_marks=True).text
    'لا،يفسخ'
    """
    base = unicodedata.normalize("NFKC", text or "")
    out: list[str] = []
    index: list[int] = []
    position, length = 0, len(base)

    while position < length:
        char = base[position]

        if _CONTROL.match(char):
            position += 1
            continue

        if char.isspace():
            end = position
            while end < length and base[end].isspace():
                end += 1
            if out:
                following = _next_significant(base, end, drop_marks=drop_marks)
                touches_punctuation = bool(_PUNCT_CHAR.match(out[-1])) or bool(
                    following and _PUNCT_CHAR.match(following)
                )
                if not touches_punctuation:
                    out.append(" ")
                    index.append(position)
            position = end
            continue

        if drop_marks and (_MARKS.match(char) or char == _TATWEEL):
            position += 1
            continue

        out.append(char.translate(_DIGITS) if drop_marks else char)
        index.append(position)
        position += 1

    if out and out[-1] == " ":
        out.pop()
        index.pop()
    index.append(length)
    return _Folded(text="".join(out), index=tuple(index), base=base)


def _span(folded: _Folded, start: int, end: int) -> str:
    """
    الرسم الخام للمصدر بين موضعين في النصّ المطويّ.

    ⚠️ والمأخوذ من `base` (أي بعد NFKC)، فقد تختلف فيه صور العرض عن الرسم
    الخام: «ﻻ» تصير «لا». وهذا مقصود — «لا» و«ﻻ» صورتان لحرف واحد، وما يُعرض
    على المحامي هو **الموضع** برسمه الموحَّد.
    """
    return folded.base[folded.index[start] : folded.index[end]].strip()


@dataclass(frozen=True)
class _Token:
    """وحدة مقارنة: كلمة أو محرف ترقيم، وموضعها في النصّ المطويّ."""

    text: str
    start: int
    end: int
    word: bool


def _tokenize(folded: _Folded) -> tuple[_Token, ...]:
    """
    يقسّم النصّ المطويّ إلى كلمات وترقيم.

    والتقسيم **لا يُسقط الترقيم**: هو نصف المقارنة. وكل محرف ترقيم وحدة قائمة
    بذاتها، فيُسمّى بعينه حين يختلف («،» ليست «؛»).
    """
    tokens: list[_Token] = []
    for match in _TOKEN.finditer(folded.text):
        piece = match.group(0)
        tokens.append(
            _Token(
                text=piece,
                start=match.start(),
                end=match.end(),
                word=_PUNCT_CHAR.match(piece) is None,
            )
        )
    return tuple(tokens)


def _render(pieces: Sequence[str]) -> str:
    """يعرض مقاطع متغيّرة نصّاً مقروءاً في رسالة عربية."""
    return " ".join(pieces)


def _diff_entries(left: Sequence[str], right: Sequence[str]) -> tuple[str, ...]:
    """
    يسمّي ما اختلف بين تسلسلين (كلمات أو ترقيم)، بالعربية وبعينه.

    والاتجاهان مسمّيان صراحةً — «زيادة في الاقتباس» و«زيادة في المصدر» —
    لأن **الفرق بين زيادة ونقص هو الفرق بين ما زاده الكاتب وما أسقطه**، وهو
    أوّل ما يسأل عنه المحامي.
    """
    entries: list[str] = []
    matcher = difflib.SequenceMatcher(None, list(left), list(right), autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        ours = _render(left[i1:i2])
        theirs = _render(right[j1:j2])
        if tag == "delete":
            entries.append(f"في الاقتباس زيادة على المصدر: «{ours}»")
        elif tag == "insert":
            entries.append(f"في المصدر زيادة على الاقتباس: «{theirs}»")
        else:
            entries.append(f"اختلاف: «{ours}» في الاقتباس مقابل «{theirs}» في المصدر")
    return tuple(entries)


# ==============================================================================
# ٣. المطابقة الصارمة
# ==============================================================================

#: أقلّ عدد كلمات متطابقة تُعرف به مقابلة الاقتباس بالمصدر (%٥٠ من كلماته).
#: فما دونها لا تُنسب إلى الاقتباس مخالفةٌ بعينها، لأنه لا مقابل لها أصلاً.
_ANCHOR_FRACTION = 0.5

#: وأقلّ عدد مطلق — فلا يُبنى حكمٌ على تطابق كلمة واحدة عابرة.
_MIN_ANCHOR_WORDS = 1


def _match_by_words(quote: str, quote_folded: _Folded, source_folded: _Folded) -> StrictMatch:
    """
    يحكم حين لم توجد حروف الاقتباس متّصلة في المصدر: أهي كلماتٌ تغيّرت، أم
    ترقيمٌ تغيّر، أم لا مقابلة أصلاً؟

    والترتيب مقصود: **التطابق التامّ للكلمات يقدَّم على كل شيء**، فإن تطابقت
    الكلمات كلها فالفرق في الترقيم وحده — وهذا هو موضع العيب الأول في هذا
    الملف («لا يفسخ» مقابل «لا، يفسخ»).
    """
    tokens_q = _tokenize(quote_folded)
    tokens_s = _tokenize(source_folded)

    words_q = [token for token in tokens_q if token.word]
    words_s = [token for token in tokens_s if token.word]
    if not words_q or not words_s:
        return StrictMatch(MatchKind.MISSING, quote)

    texts_q = [token.text for token in words_q]
    texts_s = [token.text for token in words_s]
    matcher = difflib.SequenceMatcher(None, texts_q, texts_s, autojunk=False)
    blocks = matcher.get_matching_blocks()
    matched = sum(block.size for block in blocks)

    word_token_positions = [i for i, token in enumerate(tokens_s) if token.word]

    # (أ) كل كلمات الاقتباس موجودة متتابعة → الفرق في الترقيم وحده.
    if matched == len(texts_q):
        first = matcher.find_longest_match(0, len(texts_q), 0, len(texts_s))
        if first.size == len(texts_q):
            first_word = next(i for i, token in enumerate(tokens_q) if token.word)
            last_word = max(i for i, token in enumerate(tokens_q) if token.word)
            source_from = word_token_positions[first.b]
            source_to = word_token_positions[first.b + first.size - 1]

            # ⚠️ ترقيم الاقتباس **الطرفي** من الاقتباس، فيُقارَن: «…العمل.» مقابل
            # «…العمل؛» فرقُ ترقيم يُبلَّغ عنه. ولو قُورن الترقيم **بين** الكلمات
            # وحده لضاع هذا الفرق: موضعه بعد آخر كلمة لا بينها — وهو عطب وقع.
            quote_from, quote_to = first_word, last_word
            while quote_from > 0 and not tokens_q[quote_from - 1].word:
                quote_from -= 1
            while quote_to + 1 < len(tokens_q) and not tokens_q[quote_to + 1].word:
                quote_to += 1

            # ⚠️ **وترقيم المصدر الطرفي لا يُقارَن إلا بمقدار ما في الاقتباس.**
            # والسبب أن الاقتباس **مقتطع**: اقتباسٌ ينتهي عند كلمة، وفاصلةُ
            # المصدر بعده ليست من المقتبس بل من بقيّة الجملة. فلو قُورنت لخرج
            # `PUNCTUATION_CHANGED` على كل اقتطاع سليم — أي **إنذار دائم**.
            source_left = 0
            while (
                source_left < first_word - quote_from
                and source_from > 0
                and not tokens_s[source_from - 1].word
            ):
                source_from -= 1
                source_left += 1
            source_right = 0
            while (
                source_right < quote_to - last_word
                and source_to + 1 < len(tokens_s)
                and not tokens_s[source_to + 1].word
            ):
                source_to += 1
                source_right += 1

            changed = _diff_entries(
                [token.text for token in tokens_q[quote_from : quote_to + 1]],
                [token.text for token in tokens_s[source_from : source_to + 1]],
            )
            if not changed:
                # ⚠️ لا يُبلغ عن «ترقيم تغيّر» ولا يُسمّى المتغيّر — وهذا لا
                # يقع في المبدأ (تطابق الوحدات يقتضي تطابق النصّ المطويّ)،
                # لكن تشخيصاً لا يسمّي شيئاً أسوأ من عدم التشخيص.
                changed = ("اختلاف في الترقيم أو في الفصل بين الكلمات دون تغيّر الكلمات",)
            return StrictMatch(
                MatchKind.PUNCTUATION_CHANGED,
                quote,
                _span(source_folded, tokens_s[source_from].start, tokens_s[source_to].end),
                changed,
            )

    # (ب) كلمات كثيرة موجودة → الاقتباس صيغةٌ أخرى لنصّ المصدر، وتُسمّى المخالفة.
    needed = max(_MIN_ANCHOR_WORDS, math.ceil(_ANCHOR_FRACTION * len(texts_q)))
    if matched < needed:
        return StrictMatch(MatchKind.MISSING, quote)

    anchor = matcher.find_longest_match(0, len(texts_q), 0, len(texts_s))
    window_start = max(anchor.b - anchor.a, 0)
    window_end = min(window_start + len(texts_q), len(texts_s))
    if window_start >= window_end:
        return StrictMatch(MatchKind.MISSING, quote)

    changed = _diff_entries(texts_q, texts_s[window_start:window_end])
    return StrictMatch(
        MatchKind.WORD_CHANGED,
        quote,
        _span(
            source_folded,
            tokens_s[word_token_positions[window_start]].start,
            tokens_s[word_token_positions[window_end - 1]].end,
        ),
        changed,
    )


def strict_match(quote: str, source: str) -> StrictMatch:
    """
    يطابق اقتباساً بمصدره بأضيق تسامح: النقل الحرفي وحده.

    الخطوات، ولماذا هذا الترتيب:

    1. **بلا إسقاط التشكيل ولا طيّ الأرقام** — فإن وجد الاقتباس فالنقل تامّ
       (`EXACT`): لم يختلف حرف.
    2. **ثم بالمُسقط كله** (تشكيل · كشيدة · أرقام) — فإن وُجد فالفرق **رسمٌ
       محض** (`FORMATTING_ONLY`) ولا كلمة تبدّلت.
    3. **ثم بالكلمات والترقيم** — فإن تطابقت الكلمات كلها فالفرق ترقيم
       (`PUNCTUATION_CHANGED`)، وإن تطابق بعضها فالفرق كلمات (`WORD_CHANGED`)،
       وإن لم تُعرف مقابلة فـ`MISSING`.

    ⚠️ والخطوة الثالثة **تشخيصٌ لا تسامح**: `PUNCTUATION_CHANGED` و
    `WORD_CHANGED` كلتاهما **غير مقبولتين**، والفرق بينهما في **ما يُقال
    للكاتب** لا في الحكم.

    >>> strict_match("المادة ٢٤٦ من قانون المعاملات",
    ...              "المادة 246 من قانون المعاملات").kind.value
    'formatting_only'
    >>> strict_match("لا يفسخ العقد للمالك فوراً",
    ...              "…لا، يفسخ العقد للمالك فوراً").kind.value
    'punctuation_changed'
    >>> strict_match("لا يفسخ العقد للمالك فوراً",
    ...              "…لا، يفسخ العقد للمالك فوراً").accepted()
    False
    """
    text = quote or ""
    haystack = source or ""

    exact = _fold(text, drop_marks=False)
    source_exact = _fold(haystack, drop_marks=False)
    if exact.text:
        found = source_exact.text.find(exact.text)
        if found != -1:
            return StrictMatch(
                MatchKind.EXACT,
                text,
                _span(source_exact, found, found + len(exact.text)),
            )

    folded = _fold(text, drop_marks=True)
    source_folded = _fold(haystack, drop_marks=True)
    if folded.text:
        found = source_folded.text.find(folded.text)
        if found != -1:
            return StrictMatch(
                MatchKind.FORMATTING_ONLY,
                text,
                _span(source_folded, found, found + len(folded.text)),
            )

    if not folded.text:
        return StrictMatch(MatchKind.MISSING, text)
    return _match_by_words(text, folded, source_folded)


# ==============================================================================
# ٤. العرض — أنصاف الاقتباس والنسبة
# ==============================================================================


class Presentation(str, Enum):
    """كيف قُدّم النصّ في المسودّة: منقولاً، أم منسوباً، أم نثراً عادياً."""

    #: بين علامتي اقتباس — يُدّعى أنه نصّ غيره.
    QUOTED = "quoted"
    #: منسوب إلى نصّ بلا علامات اقتباس — **صياغة الكاتب**.
    ATTRIBUTED = "attributed"
    #: لا نسبة ولا اقتباس — نثر المسودّة.
    NEUTRAL = "neutral"


#: علامات الاقتباس العربية والمتداولة، وكل زوج مفتوح-مغلق. والزوج ذو المحرف
#: الواحد (ASCII) يُقرن بالتناوب: الأول بالثاني، والثالث بالرابع.
_QUOTE_MARKS: dict[str, str] = {
    "«": "»",
    "\u201c": "\u201d",
    "\u2018": "\u2019",
    "\ufd3e": "\ufd3f",  # ﴿ … ﴾
    '"': '"',
    "'": "'",
}

#: صور الأرقام في إشارة المادة: المشرقية والمغربية واللاتينية.
_DIGIT_RANGE = "٠-٩۰-۹0-9"

#: الإشارة إلى مادة **بموضعها في المسودّة**.
#:
#: ⚠️ **ولماذا لا يُستورد نمط `attribution.py`؟** لأن هذا الملف يحتاج ما لا
#: يعطيه ذلك النمط: **الإزاحات** — بها يُقرن الاقتباس بالمرجع **الأقرب** في
#: الجملة نفسها، وبها يُقتطع كلام الكاتب بعد المرجع. و`find_article_refs` في
#: `citations.py` يعمل على النصّ المطبَّع ولا يعيد موضعاً ولا الرسم الخام.
#: والتكرار هنا **ضيّق ومعلن**: كشفُ الإشارة لا الحكم فيها. **والحكم في «لمن
#: هذا النصّ» يبقى في `attribution.py` وحده** ولا يُعاد هنا.
_REFERENCE = re.compile(
    rf"(?<![\w])(?:و|ف)?(?:ال)?"
    rf"(?:ماد[ةه]|مادت(?:ان|ين|ي)|مواد|م)"
    rf"\s*[\(\[]?\s*(?P<num>[{_DIGIT_RANGE}]{{1,4}})"
    rf"(?:\s*/\s*[{_DIGIT_RANGE}]{{1,4}})?"
    rf"\s*[\)\]]?"
)

#: مقاطع المسودّة — تُفصل عند نهاية الجملة.
#:
#: ⚠️ **ولا يُفصل عند النقطتين (:)** — كـ`attribution.py`، وللسبب نفسه:
#: «المادة ٤٣: نصّها» لو فُصلت عنده لخرج المرجع في مقطع والنصّ في آخر، فصار
#: الاقتباس بلا مرجع ولا يُفحص — **إسقاط الفحص بدل الإنذار**، وهو أسوأ عيب.
_SEGMENT = re.compile(r"[^\n\r.؟!?؛;]+")


@dataclass(frozen=True)
class Passage:
    """
    مقطع من المسودّة، وكيف قُدّم فيها.

    Attributes:
        text:         نصّ المقطع. وفي `QUOTED` هو **ما بين العلامتين** (فالعلامتان
                      ليستا من المنقول)، وفي `ATTRIBUTED` كلام الكاتب بعد المرجع،
                      وفي `NEUTRAL` نصّ الجملة.
        presentation: `QUOTED` أو `ATTRIBUTED` أو `NEUTRAL`.
        reference:    المرجع **كما كُتب في المسودّة** («المادة ٤٣/٢»)، فيبحث به
                      المحامي في مسودّته؛ و``""`` إن لم يُذكر مرجع.
    """

    text: str
    presentation: Presentation
    reference: str = ""


@dataclass(frozen=True)
class _Quote:
    """اقتباس صريح في المسودّة: ما بين العلامتين، وموضعه."""

    inner: str
    start: int
    end: int


@dataclass(frozen=True)
class _Reference:
    """إشارة إلى مادة: رسمها وموضعها."""

    surface: str
    start: int
    end: int


def _collapse(text: str) -> str:
    """يطوي المسافات ويحذف الأطراف — للعرض وحده، لا للمقارنة."""
    return _WHITESPACE.sub(" ", text or "").strip()


def _quote_spans(text: str) -> list[_Quote]:
    """
    يستخرج كل اقتباس صريح بين علامتين.

    ⚠️ **والاقتباس غير المغلَق يُهمَل** (حدّ رابع في صدر الملف): القوس المفتوح
    بلا مغلق لو قُرئ اقتباساً لصار **كل ما بعده منقولاً** إلى آخر المستند —
    فيُنذر عن مسودّة سليمة. والثمن تغطية ناقصة معلنة، لا إنذار كاذب.
    """
    spans: list[_Quote] = []
    position = 0
    while position < len(text):
        closer = _QUOTE_MARKS.get(text[position])
        if closer is None:
            position += 1
            continue
        end = text.find(closer, position + 1)
        if end == -1:
            position += 1
            continue
        inner = text[position + 1 : end].strip()
        if inner:
            spans.append(_Quote(inner=inner, start=position, end=end + 1))
        position = end + 1
    return spans


def _gap(quote: _Quote, reference: _Reference) -> int:
    """المسافة بين اقتباس ومرجع — صفر إن تداخلا. وبها يُختار الأقرب."""
    return max(reference.start - quote.end, quote.start - reference.end, 0)


def classify(text: str) -> tuple[Passage, ...]:
    """
    يقسّم المسودّة إلى مقاطع ويسمّي **كيف قُدّم** كلٌّ منها.

    الخطوات: تُستخرج إشارات المواد وعلامات الاقتباس من مواضعها، ثم يُقرن كل
    اقتباس بأقرب مرجع إليه — **ويُقدَّم من كان في الجملة نفسها**، لأن الجملة
    هي وحدة النسبة في النثر القانوني: ما بعد نهاية الجملة كلامٌ آخر.

    ثم:

    * مرجعٌ **مع** اقتباس ← `QUOTED` (يُدّعى أنه نصّ غيره، فيُفحص).
    * مرجعٌ **بلا** اقتباس، وبعده كلام ← `ATTRIBUTED` (صياغة الكاتب).
    * مرجع بلا كلام بعده «المادة ٤٣» ← **ذكرٌ لا نسبة**، فلا يُصنع منه مقطع
      منسوب، وإلا نُسب إلى المادة كلامٌ لم يقل الكاتب إنه منها.
    * ما بقي من الجمل ← `NEUTRAL`.

    ⚠️ **و`NEUTRAL` مقصود لا حشو:** به يظهر الفرق الذي جاء الملف له — أيّ
    العبارات عبارةُ القانون، وأيّها عبارةُ الكاتب، وأيّها نثرٌ لا نسبة فيه.

    >>> [p.presentation.value for p in classify("وتنص المادة ٤٣ على: «لا يجوز إنهاء عقد العمل إلا بإخطار كتابي»")]
    ['quoted']
    >>> [(p.presentation.value, p.reference) for p in classify("وتنص المادة ٤٣ على أنه لا يجوز إنهاء عقد العمل.")]
    [('attributed', 'المادة ٤٣')]
    >>> [p.presentation.value for p in classify("يلتزم الطرف الثاني بسداد الأجرة في مواعيدها.")]
    ['neutral']
    """
    body = text or ""
    if not body.strip():
        return ()

    segments = [
        (match.start(), match.end(), match.group(0)) for match in _SEGMENT.finditer(body)
    ]
    references = [
        _Reference(surface=_collapse(match.group(0)), start=match.start(), end=match.end())
        for match in _REFERENCE.finditer(body)
    ]
    quotes = _quote_spans(body)

    # القرن على **مرّتين**، والترتيب هو الفرق بين إسناد صحيح وإسناد كاذب:
    #
    #  ١. **المرجع في الجملة نفسها** — وهي وحدة النسبة في النثر القانوني.
    #  ٢. ثم **الأقرب على أيّ حال** — لمن لم يجد مرجعاً في جملته.
    #
    # ⚠️ ولو جُعلت المرّتان واحدة (اقتباسٌ بلا مرجع في جملته يأخذ أيّ مرجع
    # متبقٍّ) لَسَرق الاقتباسُ الأول مرجعَ الاقتباس الثاني: مسودّة فيها
    # ««نصّ» يرد في المذكرة. وتنص المادة ٤٣ على: «نصّها»» كان الاقتباس الأول
    # فيها يأخذ «المادة ٤٣» — **فيُفحص نصٌّ على مادة ليست له، ويبقى نصّ المادة
    # بلا مرجع**. وهذا أسوأ من عدم الفحص: يُنتج حكماً في غير موضعه.
    #
    # ⚠️ **والثمن المعلن:** اقتباسٌ لم يبقَ له مرجع يخرج `QUOTED` بلا مرجع،
    # فيُعرَض **ملاحظة** ولا يُطابَق بشيء (حدّ خامس في صدر الملف) — **والاتّجاه
    # هو الصحيح**: لا يُقال عن نصّ إنه خالف مادةً لم يُقرن بها.
    pair_of_quote: dict[int, int] = {}
    used: set[int] = set()

    def _sentences_of(quote: _Quote) -> list[int]:
        return [
            index
            for index, (start, end, _text) in enumerate(segments)
            if start < quote.end and quote.start < end
        ]

    for quote_index, quote in enumerate(quotes):
        overlapping = _sentences_of(quote)
        pool = [
            i
            for i in range(len(references))
            if i not in used
            and any(
                segments[index][0] <= references[i].start < segments[index][1]
                for index in overlapping
            )
        ]
        if not pool:
            continue
        best = min(pool, key=lambda i: (_gap(quote, references[i]), references[i].start))
        used.add(best)
        pair_of_quote[quote_index] = best

    for quote_index, quote in enumerate(quotes):
        if quote_index in pair_of_quote:
            continue
        pool = [i for i in range(len(references)) if i not in used]
        if not pool:
            break
        best = min(pool, key=lambda i: (_gap(quote, references[i]), references[i].start))
        used.add(best)
        pair_of_quote[quote_index] = best

    emitted: list[tuple[int, Passage]] = []
    for seg_start, seg_end, seg_text in segments:
        quotes_here = [i for i, quote in enumerate(quotes) if seg_start <= quote.start < seg_end]
        refs_here = [i for i, ref in enumerate(references) if seg_start <= ref.start < seg_end]
        produced = 0

        for quote_index in quotes_here:
            quote = quotes[quote_index]
            reference_index = pair_of_quote.get(quote_index)
            surface = references[reference_index].surface if reference_index is not None else ""
            emitted.append(
                (quote.start, Passage(text=quote.inner, presentation=Presentation.QUOTED, reference=surface))
            )
            produced += 1

        for reference_index in refs_here:
            if reference_index in used:
                continue
            reference = references[reference_index]
            following = [
                references[other].start
                for other in refs_here
                if other != reference_index and references[other].start > reference.start
            ]
            stop = min(following) if following else seg_end
            claim = _collapse(body[reference.end : stop]).strip(":،؛").strip()
            if not claim:
                # مرجع بلا كلام بعده: «راجع المادة ٤٣» ذكرٌ لا نسبة.
                continue
            emitted.append(
                (
                    reference.start,
                    Passage(text=claim, presentation=Presentation.ATTRIBUTED, reference=reference.surface),
                )
            )
            produced += 1

        if not produced:
            neutral = _collapse(seg_text)
            if neutral:
                emitted.append((seg_start, Passage(text=neutral, presentation=Presentation.NEUTRAL)))

    # ترتيب الورود: المحامي يقرأ المسودّة من أوّلها، فيقرأ الملاحظات في مواضعها.
    emitted.sort(key=lambda item: item[0])
    return tuple(passage for _position, passage in emitted)


# ==============================================================================
# ٥. الفحص
# ==============================================================================

SEVERITY_ERROR = "error"
SEVERITY_NOTICE = "notice"

#: أنواع الحكم. والأسماء ثوابت كما في `review.py`: تُقارَن في `summarize` وفي
#: أي واجهة، والنصّ الحرّ لا يُطابق.
KIND_UNFAITHFUL_QUOTE = "unfaithful_quote"
KIND_UNREFERENCED_QUOTE = "unreferenced_quote"
KIND_UNKNOWN_SOURCE = "unknown_source"
KIND_UNQUOTED_ATTRIBUTION = "unquoted_attribution"

FINDING_KINDS: tuple[str, ...] = (
    KIND_UNFAITHFUL_QUOTE,
    KIND_UNREFERENCED_QUOTE,
    KIND_UNKNOWN_SOURCE,
    KIND_UNQUOTED_ATTRIBUTION,
)

#: ⚠️ **الخطأ نوع واحد، والملاحظات ثلاثة — وهذا هو الفرق الذي يحكم الأداة.**
#:
#: * **الاقتباس غير الأمين خطأ** (`unfaithful_quote`): كلمةٌ أو فاصلة تغيّرت
#:   بين علامتي اقتباس. وهو **تقديم كلام الكاتب على أنه كلام القانون**، وهو
#:   بعينه ما نُهينا عنه. ولا يُصلَح إلا بتصحيح النقل أو برفع العلامتين.
#: * **والنسبة بلا علامات اقتباس ملاحظة** (`unquoted_attribution`) **لا خطأ**:
#:   التلخيص مشروع، والنهي عن **تقديم** كلام الكاتب على أنه النصّ، لا عن
#:   تلخيصه. فجعلها خطأً يمنع التسليم بسبب صياغة سليمة — وهو الطريق إلى أداة
#:   تُنذر دائماً فلا تُقرأ.
#: * **وغياب المصدر في الأرشيف ملاحظة** (`unknown_source`): عيب تغطية لا عيب
#:   مسودّة، على قاعدة `attribution.py` نفسها («`absent` ملاحظة لا خطأ»).
#: * **والاقتباس بلا مرجع ملاحظة** (`unreferenced_quote`): نصٌّ بين علامتي
#:   اقتباس لا يُعرف إلى مادة يُنسب، فلا يُطابَق بشيء. ووجوده **أخطر من
#:   الاقتباس المخالف** لأنه لا يُفحص أصلاً — ولهذا يُعرَض ولا يُسكَت عنه،
#:   ويبقى ملاحظة لأن المسودّة قد تنقل نصّاً مشهوراً بلا حاجة إلى مرجع.
ERROR_KINDS: tuple[str, ...] = (KIND_UNFAITHFUL_QUOTE,)


@dataclass(frozen=True)
class PresentationFinding:
    """
    ملاحظة واحدة على عرض النصّ في المسودّة.

    Attributes:
        kind:         أحد `FINDING_KINDS`.
        severity:     `error` يمنع التسليم، أو `notice` يُعرَض ولا يمنع.
        presentation: كيف قُدّم المقطع — `QUOTED` أو `ATTRIBUTED`.
        reference:    المرجع كما كُتب في المسودّة، أو ``""``.
        text:         نصّ المقطع كما في المسودّة.
        message:      الحكم بالعربية في جملة، وفيها **ما تغيّر بعينه** إن تغيّر.
        match:        حصيلة المطابقة الصارمة، أو ``None`` إن لم تُجرَ مطابقة.
        changed:      ما تغيّر بعينه — يُنسخ من `StrictMatch` للعرض وحده.
    """

    kind: str
    severity: str
    presentation: Presentation
    reference: str
    text: str
    message: str
    match: Optional[MatchKind] = None
    changed: tuple[str, ...] = ()


def _unfaithful_message(reference: str, result: StrictMatch) -> str:
    """يبني الحكم من **نتيجة المطابقة**، فلا يفترق الحكم عن دليله."""
    detail = "؛ ".join(result.changed)
    if result.kind is MatchKind.MISSING:
        return (
            f"الاقتباس المنسوب إلى «{reference}» غير موجود في نصّ المصدر: "
            "نصٌّ بين علامتي اقتباس لا يقابله نصّ في المادة، فلا يُنقل على أنه منها."
        )
    if result.kind is MatchKind.PUNCTUATION_CHANGED:
        return (
            f"الاقتباس المنسوب إلى «{reference}» يخالف نصّ المصدر في ترقيمه، "
            f"والترقيم قد يحمل المعنى فلا يُمحى: {detail}"
        )
    return f"الاقتباس المنسوب إلى «{reference}» يخالف نصّ المصدر في كلماته: {detail}"


def _check_quote(passage: Passage, source_of: Callable[[str], str]) -> tuple[PresentationFinding, ...]:
    """
    يفحص اقتباساً صريحاً: أيطابق نصَّ المصدر؟

    ⚠️ **والاقتباس بلا مرجع لا يُطابَق بشيء ولا يُسكَت عنه** (حدّ مُعلن في صدر
    الملف): لا يُعرف أيّ نصّ يُقارَن به، فيُعرَض **ملاحظة** — والمرجع يُطلب في
    الموجّه. أما الاقتباس الذي له مرجع ولم يُنتج الأرشيف نصّه فملاحظة أخرى.
    """
    if not passage.reference:
        return (
            PresentationFinding(
                kind=KIND_UNREFERENCED_QUOTE,
                severity=SEVERITY_NOTICE,
                presentation=passage.presentation,
                reference="",
                text=passage.text,
                message=(
                    "اقتباس بعلامات تنصيص بلا مرجع إلى مادة: لا يُعرف أيّ نصّ "
                    "يُطابَق به، فهو النقل الوحيد الذي لا يُفحص."
                ),
            ),
        )

    source = source_of(passage.reference) or ""
    if not source.strip():
        return (
            PresentationFinding(
                kind=KIND_UNKNOWN_SOURCE,
                severity=SEVERITY_NOTICE,
                presentation=passage.presentation,
                reference=passage.reference,
                text=passage.text,
                message=(
                    f"لم يُنتج الأرشيف نصّاً للمرجع «{passage.reference}»: تعذّرت "
                    "مطابقة الاقتباس، وهذا نقص تغطية يُعرَض ولا يمنع التسليم."
                ),
            ),
        )

    result = strict_match(passage.text, source)
    if result.accepted():
        return ()

    return (
        PresentationFinding(
            kind=KIND_UNFAITHFUL_QUOTE,
            severity=SEVERITY_ERROR,
            presentation=passage.presentation,
            reference=passage.reference,
            text=passage.text,
            message=_unfaithful_message(passage.reference, result),
            match=result.kind,
            changed=result.changed,
        ),
    )


def _attribution_notice(passage: Passage) -> PresentationFinding:
    """
    ملاحظة النسبة بلا علامات اقتباس.

    ⚠️ **والنهي عن التقديم لا عن التلخيص:** أن يقول الكاتب بلفظه ما تفيده مادة
    هو عمل المحامي. والعيب أن **يُقدَّم لفظ الكاتب على أنه لفظ المادة** — وهو
    ما لا يقع هنا لأن العلامتين غائبتان. فالغرض **بيانيّ**: يرى المحامي بأيّ
    العبارات عبارةُ القانون وأيّها عبارةُ الكاتب، فيعرف ما يُنقل إلى مذكرة أو
    يُسند إلى نصّ حرفيّ.
    """
    return PresentationFinding(
        kind=KIND_UNQUOTED_ATTRIBUTION,
        severity=SEVERITY_NOTICE,
        presentation=passage.presentation,
        reference=passage.reference,
        text=passage.text,
        message=(
            f"نصّ منسوب إلى «{passage.reference}» بلا علامات اقتباس: صياغة الكاتب "
            "لا نصّ المادة — وهي مشروعة، وتُعرَض ليُرى أيّ العبارتين عبارةُ القانون."
        ),
    )


def check_presentation(
    text: str,
    source_of: Callable[[str], str],
) -> tuple[PresentationFinding, ...]:
    """
    يفحص عرض النصّ في المسودّة: هل نُقل نصّ القانون حرفياً كما بين علامتيه؟

    و`source_of` **يحقن** نصّ المادة من أيّ مصدر: أرشيف، أو قاموس، أو دالّة
    تُرجع ما رآه النموذج. فلا يعرف هذا الملف — ولا يجوز أن يعرف — من أين يأتي
    النصّ، فيعمل بلا أرشيف ولا شبكة ولا نموذج، **وتبقى أحكامه قابلة للاختبار
    بمدخلاتها وحدها**.

    >>> source = "لا يجوز إنهاء عقد العمل إلا بإخطار كتابي"
    >>> check_presentation("وتنص المادة ٤٣ على: «لا يجوز إنهاء عقد العمل إلا بإخطار كتابي»", lambda ref: source)
    ()
    >>> bad = check_presentation("وتنص المادة ٤٣ على: «لا يجوز إنهاء عقد العمل بإخطار شفهي»", lambda ref: source)
    >>> bad[0].kind, bad[0].severity, bad[0].match.value
    ('unfaithful_quote', 'error', 'word_changed')
    """
    findings: list[PresentationFinding] = []
    for passage in classify(text):
        if passage.presentation is Presentation.QUOTED:
            findings.extend(_check_quote(passage, source_of))
        elif passage.presentation is Presentation.ATTRIBUTED:
            findings.append(_attribution_notice(passage))
    return tuple(findings)


# ==============================================================================
# ٦. العرض والتلخيص
# ==============================================================================


def _summary_line(findings: Sequence[PresentationFinding]) -> str:
    """
    سطر عربي واحد يصلح للعرض. ويذكر الملاحظات مع الأخطاء لأن **سكوت السطر عن
    الملاحظة يجعل المسودّة تبدو كأن لا شيء فيها**.
    """
    errors = [item for item in findings if item.severity == SEVERITY_ERROR]
    notices = [item for item in findings if item.severity == SEVERITY_NOTICE]

    if not findings:
        return "لا اقتباس مخالف ولا نسبة بلا علامات اقتباس — المسودّة سليمة في عرضها."
    if not errors:
        return f"لا مانع من التسليم · {len(notices)} ملاحظة في العرض تُعرَض للمحامي."
    line = f"{len(errors)} اقتباس غير أمين يمنع التسليم"
    if notices:
        line += f" · {len(notices)} ملاحظة في العرض"
    return line + "."


def summarize(findings: Sequence[PresentationFinding]) -> dict:
    """
    يحوّل الحصيلة إلى قاموس صالح للبثّ كـ JSON إلى الواجهة.

    ⚠️ **و`clean` تُحسب من الأخطاء وحدها:** التلخيص بلا علامات اقتباس، والاقتباس
    الذي لم يُنتج الأرشيف نصّه، والاقتباس بلا مرجع — ثلاثتها **ملاحظات** لا
    تمنع التسليم؛ ومنعُ التسليم بها يعاقب المسودّة على صياغة مشروعة أو على نقص
    في التغطية. أما تغيير كلمة أو فاصلة بين علامتي اقتباس فـ**خطأ** يمنعه،
    لأنه نسبةٌ إلى القانون بغير لفظه.

    والعدّادات تُبنى لكل الأنواع والوجوه — ولو صفراً — ليكون **شكل الجواب
    ثابتاً**، فلا يتبدّل مفتاحٌ في الواجهة بتبدّل ما وُجد في المسودّة.

    >>> payload = summarize(())
    >>> payload["clean"], payload["total"], payload["counts_by_kind"]["unfaithful_quote"]
    (True, 0, 0)
    """
    items = list(findings)

    counts_by_kind: dict[str, int] = {kind: 0 for kind in FINDING_KINDS}
    counts_by_presentation: dict[str, int] = {face.value: 0 for face in Presentation}
    for item in items:
        counts_by_kind[item.kind] = counts_by_kind.get(item.kind, 0) + 1
        counts_by_presentation[item.presentation.value] = (
            counts_by_presentation.get(item.presentation.value, 0) + 1
        )

    errors = [item for item in items if item.severity == SEVERITY_ERROR]
    notices = [item for item in items if item.severity == SEVERITY_NOTICE]

    return {
        "summary": _summary_line(items),
        "clean": not errors,
        "error_count": len(errors),
        "notice_count": len(notices),
        "total": len(items),
        "counts_by_kind": counts_by_kind,
        "counts_by_presentation": counts_by_presentation,
        "findings": [
            {
                "kind": item.kind,
                "severity": item.severity,
                "presentation": item.presentation.value,
                "reference": item.reference,
                "text": item.text,
                "message": item.message,
                "match": item.match.value if item.match is not None else "",
                "changed": list(item.changed),
            }
            for item in items
        ],
    }
