"""
عقد الاستشهاد — تحقّق حتمي من أن كل سند في المسودّة مأخوذ من أرشيفك.
=============================================================================

المشكلة التي يحلّها
------------------
الوكيل يسترجع مقاطع من أرشيفك ثم يكتب مسودّة. لكن **لا شيء يتحقّق** أن ما
كتبه موجود فعلاً في ما استرجعه. فإن كتب «المادة ٤٢ من قانون المعاملات
المدنية» ولم تكن في أي مقطع مسترجع، لا أحد يلاحظ — والمستند يُسلَّم.

الحلّ
-----
النموذج **يروي**، والخادم **يُقرّر**. هذا الملف هو الخادم:

1. يُرقّم المقاطع المسترجعة بمراجع قصيرة (`L1`، `D1` ...) فيسهل على النموذج
   الاقتباس منها بلا أخطاء نسخ.
2. يطلب من النموذج أن يُرفق **اقتباساً حرفياً** لكل سند، لا رقم مادة.
3. **يتحقّق حتمياً** أن كل اقتباس موجود حرفياً في نصّ المقطع الذي رآه النموذج.
4. ويفحص **أرقام المواد المذكورة في المتن**: كل رقم مادة لم يظهر في أي مقطع
   مسترجع = بلا سند، ويُعرَض على المحامي.

فائدة جوهرية: **مادة مؤلَّفة لا تستطيع إنتاج اقتباس حرفي موجود في أرشيفك.**

المبدأ التصميمي
---------------
- **بلا أي تبعية خارجية** — مكتبة بايثون القياسية وحدها. فيعمل الاختبار بلا
  شبكة ولا مفتاح API ولا نموذج تضمين.
- **بلا حالة وبلا إدخال/إخراج** — دوال نقية، فتُختبر مباشرة وتُستعمل من أي
  مسار: الـ API، أو Chainlit، أو Swarmmy، أو سكربت.
- **التحقّق مقابل ما رآه النموذج بالضبط.** حقل `Evidence.text` هو النصّ
  المعروض على النموذج — لا النصّ الكامل للمقطع. السبب: السؤال الصحيح ليس
  «هل هذا النصّ موجود في القاعدة؟» بل «هل اقتبس النموذج مما أُعطيه؟». ولو
  تحقّقنا من النصّ الكامل لقبلنا اقتباساً من جزء لم يره النموذج قطّ.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Iterable, Optional, Sequence

# ==============================================================================
# ١. الثوابت والعقد النصّي
# ==============================================================================

#: أقلّ طول مقبول للاقتباس **بعد التطبيع**.
#:
#: الغرض: منع اقتباس قصير عابر من المطابقة بالمصادفة. عبارة من خمسة محارف
#: مثل «الماده» توجد في كل مقطع قانوني تقريباً، فتكون «موثَّقة» زوراً.
#:
#: ١٢ محرفاً عربياً ≈ كلمتان إلى ثلاث. رفع الرقم يزيد الصرامة ويقلّل
#: المقبول؛ خفضه يفعل العكس. وهو قابل للضبط لكل نداء.
MIN_QUOTE_CHARS = 12

#: علامتا كتلة الأسانيد التي يُرفقها النموذج في آخر المستند.
#:
#: القوسان المزدوجان مقصودان: لا يظهران في النثر القانوني العربي، فيسهل
#: العثور على الكتلة وحذفها قبل النسخ إلى Word.
CITATIONS_BEGIN = "[[الأسانيد]]"
CITATIONS_END = "[[/الأسانيد]]"

#: الفاصل بين المرجع والاقتباس داخل سطر السند.
REF_SEPARATOR = "::"

#: بادئات المراجع لكل أداة استرجاع — تجعل المرجع مفهوم السياق.
TOOL_REF_PREFIXES = {
    "legislation": "L",  # search_uae_legislation
    "drafts": "D",       # search_drafting_style
    "contracts": "C",    # search_contract_clauses
    "notices": "N",      # search_legal_notices
    "poa": "P",          # search_poa_clauses
}


# ==============================================================================
# ٢. التطبيع العربي
# ==============================================================================
# الغرض: مقارنة نصّين عربيين مكتوبين باختلافات إملائية لا تغيّر المعنى.
#
# النموذج لن يعيد التشكيل ولا الكشيدة، وقد يكتب «إ» مكان «ا»، و«٢٤٦» بأرقام
# هندية. وكل ذلك فروق شكلية لا تمسّ الكلمة. فلو قارنّا حرفياً لبطل التحقّق
# مع كل مسودّة سليمة — وهو أسوأ من عدم التحقّق، لأنه يُفقد الثقة فيه.
#
# ⚠️ ملاحظة على الطرد: القواعد أدناه **متحفّظة عن قصد**. كل قاعدة فيها طيّ
#    صورتين إملائيتين **للكلمة نفسها** (أ/ا، ة/ه، ى/ي، ٢/2) — لا طيّ كلمتين
#    مختلفتين. ولا حذف لحرف من هيكل الكلمة إلا التشكيل والكشيدة، وهما زخرفة
#    لا حروف. فلا يتحوّل «غير مؤيَّد» إلى «غير مويد» بسبب أخطاء، بل بسبب
#    اختلاف رسم لا يغيّر الكلمة.

#: التشكيل وعلامات الضبط — زخرفة لا حروف، وتُحذف بالكامل.
#: النطاقات: التشكيل الأساسي 064B–065F · الإضافي 0610–061A ·
#:           الألف الخنجرية 0670 · علامات الوقف 06D6–06ED.
_DIACRITICS = re.compile(r"[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED]")

#: الكشيدة (التطويل) — حشو بصري لا قيمة له في المطابقة.
_TATWEEL = "\u0640"

#: الأرقام العربية-الهندية (المشرقية والمغربية) إلى اللاتينية.
_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")

#: صور الألف — كلها الحرف نفسه برسم مختلف.
_ALEF = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا"})

#: الياء والألف المقصورة والهمزتان على الكرسيين.
_YA = str.maketrans({"ى": "ي", "ئ": "ي", "ؤ": "و"})

#: التاء المربوطة والهاء — تُكتبان بالتبادل في كثير من النصوص العربية.
_TA_MARBUTA = str.maketrans({"ة": "ه"})

#: كل ما ليس حرفاً عربياً ولا رقماً ولا فراغاً يُستبدل بفراغ.
#: يشمل علامات الترقيم والتنصيص والأقواس والشرطات بجميع صورها.
_NOT_WORD = re.compile(r"[^\w\s]", re.UNICODE)

#: الفراغات المتعدّدة — تُطوى إلى فراغ واحد.
_WHITESPACE = re.compile(r"\s+")

#: محارف التحكّم غير المرئية (تأتي من الاستخراج من PDF).
_CONTROL = re.compile(r"[\u200b-\u200f\u202a-\u202e\u2066-\u2069\ufeff]")


def normalize(text: Optional[str]) -> str:
    """
    يُطبّع نصاً عربياً لأغراض المطابقة الحرفية.

    الخطوات بالترتيب:

    1. **NFKC** — يطوي صور العرض العربية (ﻻ، ﺁ …) التي ينتجها استخراج PDF
       إلى حروفها الأساسية.
    2. حذف محارف التحكّم غير المرئية (علامات الاتجاه والفراغ الصفري).
    3. حذف التشكيل والكشيدة.
    4. توحيد الأرقام إلى اللاتينية.
    5. طيّ صور الألف والياء والتاء المربوطة.
    6. استبدال كل ترقيم بفراغ.
    7. طيّ الفراغات وحذف الأطراف.

    >>> normalize("المــادة (٢٤٦) من قانون المُعاملات")
    'الماده 246 من قانون المعاملات'
    """
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", text)
    text = _CONTROL.sub("", text)
    text = _DIACRITICS.sub("", text)
    text = text.replace(_TATWEEL, "")
    text = text.translate(_DIGITS)
    text = text.translate(_ALEF).translate(_YA).translate(_TA_MARBUTA)
    text = _NOT_WORD.sub(" ", text)
    text = _WHITESPACE.sub(" ", text)
    return text.strip()


def quote_in_text(
    quote: str,
    text: str,
    *,
    min_quote_chars: int = MIN_QUOTE_CHARS,
) -> bool:
    """
    هل الاقتباس موجود **حرفياً** داخل النصّ بعد تطبيع الاثنين؟

    هذا هو الفحص الحاسم في الملف كله. مادة مؤلَّفة لا تجتازه.

    لاحظ أن المثال الثاني يفشل **لسببين معاً**: الاقتباس غير حرفي (ستون ≠
    ثلاثون)، وطوله أقل من الحد الأدنى. وكلاهما سبب كافٍ للرفض.

    >>> quote_in_text("ثلاثون يوماً من تاريخ الإخطار",
    ...               "يُرسل الإخطار قبل ثلاثون يوماً من تاريخ الإخطار كتابةً")
    True
    >>> quote_in_text("ستون يوماً من تاريخ الإخطار",
    ...               "يُرسل الإخطار قبل ثلاثون يوماً من تاريخ الإخطار كتابةً")
    False
    """
    normalized_quote = normalize(quote)
    if len(normalized_quote) < min_quote_chars:
        return False
    normalized_text = normalize(text)
    if not normalized_text:
        return False
    return normalized_quote in normalized_text


# ==============================================================================
# ٣. النماذج
# ==============================================================================


@dataclass(frozen=True)
class Evidence:
    """
    مقطع استرجعته إحدى الأدوات، كما **رآه النموذج**.

    Attributes:
        ref:        المرجع القصير الذي يخاطبه النموذج، مثل ``L1``.
        chunk_id:   مفتاح المقطع في ``legal_documents`` (العمود ``id``).
        document_name: اسم المستند المصدر.
        text:       النصّ **المعروض على النموذج** — لا النصّ الكامل للمقطع.
                    التحقّق يجري عليه وحده، لأن السؤال هو «هل اقتبس النموذج
                    ممّا أُعطيه؟» لا «هل هذا موجود في القاعدة؟».
        similarity: درجة التشابه التي أعادتها دالة RPC، إن وُجدت.
        tool:       مفتاح الأداة المصدر (legislation, contracts, …).
    """

    ref: str
    chunk_id: str
    document_name: str
    text: str
    similarity: Optional[float] = None
    tool: str = ""


@dataclass(frozen=True)
class Citation:
    """اقتباس ادّعاه النموذج قبل التحقّق."""

    ref: str
    quoted_span: str


@dataclass(frozen=True)
class VerifiedCitation:
    """اقتباس ثبت أنه موجود حرفياً في المقطع المشار إليه."""

    ref: str
    chunk_id: str
    document_name: str
    quoted_span: str
    similarity: Optional[float] = None


@dataclass(frozen=True)
class RejectedCitation:
    """اقتباس رُفض، مع سبب مقروء بالعربية."""

    ref: str
    quoted_span: str
    reason: str


@dataclass
class VerificationOutcome:
    """حصيلة التحقّق من مسودّة واحدة."""

    verified: list[VerifiedCitation] = field(default_factory=list)
    rejected: list[RejectedCitation] = field(default_factory=list)
    #: مقاطع استُرجعت ولم يقتبس منها النموذج — للعلم لا للرفض.
    unused_refs: list[str] = field(default_factory=list)

    @property
    def has_evidence(self) -> bool:
        """هل نجا استشهاد واحد على الأقل؟"""
        return bool(self.verified)

    @property
    def total_claimed(self) -> int:
        """عدد الاقتباسات التي ادّعاها النموذج."""
        return len(self.verified) + len(self.rejected)

    def summary(self) -> str:
        """سطر عربي موجز يصلح للعرض في الواجهة أو السجل."""
        if self.total_claimed == 0:
            return "لم يُرفق أي سند."
        if not self.rejected:
            return f"كل الأسانيد موثَّقة ({len(self.verified)})."
        return (
            f"موثَّق: {len(self.verified)} · "
            f"مرفوض: {len(self.rejected)} من {self.total_claimed}."
        )


@dataclass
class ParsedCitations:
    """نتيجة قراءة كتلة الأسانيد من مخرج النموذج."""

    citations: list[Citation] = field(default_factory=list)
    #: أسطر داخل الكتلة لم تُقرأ — تُعرَض للتشخيص ولا تمرّ صامتة.
    malformed: list[str] = field(default_factory=list)
    #: هل أرفق النموذج الكتلة أصلاً؟ الفرق مهم: غيابها ليس خطأ صياغة بل
    #: إفصاح عن عدم وجود سند.
    has_block: bool = False


@dataclass(frozen=True)
class ArticleRef:
    """إشارة إلى مادة قانونية في متن المسودّة."""

    surface: str   # كما وردت في المتن، مثل «المادة ٢٤٦»
    number: str    # الرقم بعد التطبيع، مثل «246»


# ==============================================================================
# ٤. توزيع المراجع
# ==============================================================================


class RefAllocator:
    """
    يوزّع مراجع قصيرة ومتتابعة على المقاطع المسترجعة.

    المرجع القصير مقصود: مطالبة النموذج بنسخ معرّف طويل مثل ``48213`` تُنتج
    أخطاء نسخ، وأخطاء النسخ تُرفض فتُضيع أسانيد صحيحة. أما ``L1`` فلا يُخطئ
    فيه.

    البادئة لكل أداة تجعل المرجع مفهوم السياق: يرى المحامي ``C3`` فيعرف أنه
    البند الثالث من العقود.

    ⚠️ العدّاد **تصاعدي لكل بادئة على حدة** ولا يُعاد ضبطه تلقائياً. والسبب
    مهمّ: لو أعاد كل نداء أداة العدّ من البداية، لأعاد نداءان لنفس الأداة في
    الجولة الواحدة المراجع نفسها — فيرى النموذج مقطعين مختلفين بالمرجع ``L1``،
    ويصير اقتباسه غامضاً والتحقّق معه بلا معنى.

    >>> alloc = RefAllocator()
    >>> alloc.next_ref("contracts")
    'C1'
    >>> alloc.next_ref("contracts")
    'C2'
    >>> alloc.next_ref("legislation")
    'L1'
    """

    def __init__(self) -> None:
        self._counters: dict[str, int] = {}

    def next_ref(self, tool: str) -> str:
        """يعيد المرجع التالي للأداة المعطاة."""
        prefix = TOOL_REF_PREFIXES.get(tool, "X")
        self._counters[prefix] = self._counters.get(prefix, 0) + 1
        return f"{prefix}{self._counters[prefix]}"

    def reset(self) -> None:
        """يصفّر العدّادات — يُستدعى في بداية كل جولة."""
        self._counters.clear()


# ==============================================================================
# ٥. بناء نصّ السياق المعروض على النموذج
# ==============================================================================


def format_evidence_block(evidence: Sequence[Evidence]) -> str:
    """
    يُنسّق المقاطع المسترجعة نصّاً مرقّماً يُعرض على النموذج.

    كل مقطع يحمل مرجعه واسم مستنده، ثم نصّه. والمرجع هو ما يُطلب من النموذج
    الاقتباس باسمه.

    >>> format_evidence_block([Evidence("C1", "12", "عقد إيجار", "المدة سنتان")])
    '[C1] المستند: عقد إيجار\\nالمدة سنتان'
    """
    if not evidence:
        return ""
    blocks = []
    for item in evidence:
        head = f"[{item.ref}] المستند: {item.document_name}"
        if item.similarity is not None:
            head += f" (تشابه {item.similarity:.2f})"
        blocks.append(f"{head}\n{item.text.strip()}")
    return "\n\n".join(blocks)


# ==============================================================================
# ٦. قراءة كتلة الأسانيد من مخرج النموذج
# ==============================================================================


def split_document_and_citations(text: str) -> tuple[str, str]:
    """
    يفصل المتن عن كتلة الأسانيد.

    Returns:
        (المتن بلا الكتلة, محتوى الكتلة). ومحتوى الكتلة فارغ إن لم توجد.
    """
    if not text or CITATIONS_BEGIN not in text:
        return (text or "").strip(), ""

    start = text.index(CITATIONS_BEGIN) + len(CITATIONS_BEGIN)
    end = text.find(CITATIONS_END, start)
    if end == -1:
        # الكتلة مفتوحة بلا إغلاق — يُحتفظ بما بعدها ويُهمَل الوسم.
        return text[: text.index(CITATIONS_BEGIN)].strip(), text[start:].strip()
    body = text[: text.index(CITATIONS_BEGIN)].strip()
    block = text[start:end].strip()
    return body, block


def strip_citations_block(text: str) -> str:
    """
    يحذف كتلة الأسانيد فيبقى المستند نظيفاً للنسخ إلى Word.

    ضروري لأن كتلة الأسانيد ليست جزءاً من المستند القانوني.

    >>> strip_citations_block('البند الأول\\n[[الأسانيد]]\\nL1 :: نص\\n[[/الأسانيد]]')
    'البند الأول'
    """
    return split_document_and_citations(text)[0]


def parse_citations(text: str, *, ref_separator: str = REF_SEPARATOR) -> ParsedCitations:
    """
    يقرأ كتلة الأسانيد ويستخرج الاقتباسات.

    الصيغة المتوقّعة داخل الكتلة — سطر لكل سند::

        [[الأسانيد]]
        L1 :: الغرامة سبعون درهماً عن كل يوم تأخير
        C2 :: مدة الإخطار ثلاثون يوماً
        [[/الأسانيد]]

    الأسطر التي لا تُقرأ تُجمَع في ``malformed`` ولا تُسقَط صامتة: سطر مشوّه
    يعني سنداً ضائعاً، وإسقاطه صامتاً يخفي عيباً في الموجّه.

    >>> result = parse_citations('متن\\n[[الأسانيد]]\\nL1 :: نص حرفي\\n[[/الأسانيد]]')
    >>> result.has_block, result.citations[0].ref
    (True, 'L1')
    """
    result = ParsedCitations()
    _, block = split_document_and_citations(text)
    if not block:
        return result

    result.has_block = True
    for raw_line in block.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        # نُزيل التعداد النقطي الذي قد يضيفه النموذج رغم منعه.
        line = re.sub(r"^[-*•\d\.\)\s]+", "", line).strip()
        if not line:
            continue
        if ref_separator not in line:
            result.malformed.append(raw_line.strip())
            continue
        ref, _, quote = line.partition(ref_separator)
        ref = ref.strip().strip("[]").strip()
        quote = quote.strip().strip('"').strip("«»").strip()
        if not ref or not quote:
            result.malformed.append(raw_line.strip())
            continue
        result.citations.append(Citation(ref=ref, quoted_span=quote))
    return result


# ==============================================================================
# ٧. التحقّق
# ==============================================================================


def verify_citations(
    citations: Sequence[Citation],
    evidence: Sequence[Evidence],
    *,
    min_quote_chars: int = MIN_QUOTE_CHARS,
) -> VerificationOutcome:
    """
    يتحقّق أن كل اقتباس موجود حرفياً في المقطع الذي يشير إليه مرجعه.

    حالات الرفض الثلاث، ولكلٍّ سبب مكتوب بالعربية:

    1. **المرجع غير موجود** — النموذج أشار إلى ``L7`` ولم تُسترجَع سبعة مقاطع
       من التشريعات. هذا أخطرها: استشهاد بمصدر لم يُعطَ له.
    2. **الاقتباس قصير جداً** — لا يصلح دليلاً.
    3. **الاقتباس غير موجود حرفياً** — الصيغة الأشيع للتأليف.

    ``unused_refs`` تُملأ بالمقاطع التي استُرجعت ولم يُقتبس منها: ليست خطأً،
    لكنها مفيدة للمحامي («استرجعنا ثلاثة بنود ولم تستند المسودّة إلا إلى
    واحد»).

    >>> ev = [Evidence("L1", "7", "قانون", "الغرامة سبعون درهماً عن كل يوم تأخير")]
    >>> out = verify_citations([Citation("L1", "سبعون درهماً عن كل يوم")], ev)
    >>> out.has_evidence
    True
    """
    by_ref: dict[str, Evidence] = {item.ref: item for item in evidence}
    outcome = VerificationOutcome()
    cited_refs: set[str] = set()

    for citation in citations:
        cited_refs.add(citation.ref)
        item = by_ref.get(citation.ref)

        if item is None:
            outcome.rejected.append(
                RejectedCitation(
                    ref=citation.ref,
                    quoted_span=citation.quoted_span,
                    reason="المرجع غير موجود في المقاطع المسترجعة",
                )
            )
            continue

        normalized_quote = normalize(citation.quoted_span)
        if len(normalized_quote) < min_quote_chars:
            outcome.rejected.append(
                RejectedCitation(
                    ref=citation.ref,
                    quoted_span=citation.quoted_span,
                    reason=(
                        f"الاقتباس أقصر من الحد الأدنى "
                        f"({len(normalized_quote)} من {min_quote_chars} محرفاً)"
                    ),
                )
            )
            continue

        if not quote_in_text(
            citation.quoted_span, item.text, min_quote_chars=min_quote_chars
        ):
            outcome.rejected.append(
                RejectedCitation(
                    ref=citation.ref,
                    quoted_span=citation.quoted_span,
                    reason="الاقتباس غير موجود حرفياً في نصّ المقطع",
                )
            )
            continue

        outcome.verified.append(
            VerifiedCitation(
                ref=item.ref,
                chunk_id=item.chunk_id,
                document_name=item.document_name,
                quoted_span=citation.quoted_span,
                similarity=item.similarity,
            )
        )

    outcome.unused_refs = [item.ref for item in evidence if item.ref not in cited_refs]
    return outcome


# ==============================================================================
# ٨. فحص أرقام المواد في المتن
# ==============================================================================
# التحقّق أعلاه يحمي **الاقتباسات**. لكن النموذج قد يكتب في المتن «المادة ٤٢»
# بلا اقتباس إطلاقاً — وهو ما يحدث فعلاً. فالمسودّة تبدو موثَّقة وفيها مادة
# لا سند لها.
#
# الفحص هنا مكمّل وليس بديلاً: يجمع كل رقم مادة في المتن، ويبحث عنه في
# المقاطع المسترجعة. كل رقم لم يظهر في أي مقطع = بلا سند.

#: صيغ الإشارة إلى المادة. تعمل على النصّ **المطبَّع**: فيه «الماده» لا
#: «المادة» (طيّ التاء المربوطة)، والأرقام لاتينية.
_ARTICLE_PATTERN = re.compile(
    r"(?:ال)?(?:ماده|مادتان|مادتي|مواد|بند|بنود|فقره|فقرات)"
    r"\s*(?:رقم\s*)?(?P<num>\d{1,4})"
)

#: صيغة البحث عن رقم في المقاطع — مع حدود تمنع مطابقة جزئية:
#: «24» لا يجب أن يطابق «246».
def _number_pattern(number: str) -> re.Pattern[str]:
    return re.compile(rf"(?<!\d){re.escape(number)}(?!\d)")


def find_article_refs(text: str) -> list[ArticleRef]:
    """
    يستخرج كل إشارة إلى مادة قانونية من متن المسودّة.

    >>> [r.number for r in find_article_refs("وفقاً للمادة ٢٤٦ والمادة 15")]
    ['246', '15']
    """
    normalized = normalize(text)
    if not normalized:
        return []
    found: list[ArticleRef] = []
    seen: set[tuple[str, str]] = set()
    for match in _ARTICLE_PATTERN.finditer(normalized):
        number = match.group("num")
        key = (match.group(0), number)
        if key in seen:
            continue
        seen.add(key)
        found.append(ArticleRef(surface=match.group(0).strip(), number=number))
    return found


def unbacked_article_refs(
    document_text: str,
    evidence: Sequence[Evidence],
) -> list[ArticleRef]:
    """
    أرقام المواد المذكورة في المتن **ولم تظهر في أي مقطع مسترجع**.

    هذه هي المواد التي لا سند لها في أرشيفك: إمّا أخذها النموذج من معرفته
    العامة، وإمّا اختلقها. في الحالتين يجب أن يراها المحامي قبل أن يعتمد
    المستند.

    ⚠️ حدود الفحص: يتحقّق من **ظهور الرقم** في المقاطع، لا من انطباق المادة
    على الواقعة. فمادة موجودة في الأرشيف قد تكون غير منطبقة — وهذا حكم
    قانوني لا يحسمه كود. الفحص يمنع التأليف، لا سوء التطبيق.

    >>> ev = [Evidence("L1", "7", "قانون", "المادة 246: لكل دعوى...")]
    >>> unbacked_article_refs("استناداً إلى المادة ٢٤٦ والمادة ٩٩٩", ev)[0].number
    '999'
    """
    refs = find_article_refs(document_text)
    if not refs:
        return []
    if not evidence:
        return refs

    haystack = " ".join(normalize(item.text) for item in evidence)
    unbacked = []
    for ref in refs:
        if not _number_pattern(ref.number).search(haystack):
            unbacked.append(ref)
    return unbacked
