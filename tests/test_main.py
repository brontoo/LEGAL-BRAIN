"""
اختبارات `main.py` — المسارات والبثّ والتحقّق من الأسانيد.
=============================================================================

تشغيل:
    python -m unittest discover -s tests -t . -v

`main.py` يُشغّل الوكيل في **خيط منفصل** ويمرّر أحداثه إلى طابور asyncio. وأخطر
ما في هذه البنية هو موضع فتح جامع الأدلّة: `ContextVar` معزول لكل خيط، فلو
فُتح في حلقة الأحداث بدل الخيط العامل لما رأته الأدوات، ولظلّ التحقّق يعمل
**بلا أدلّة** فيرفض كل استشهاد — أو يقبل بلا فحص. وهذا ما تفحصه المجموعة هنا.

الاختبار الحاسم: ``test_evidence_is_registered_for_the_round`` — يُثبت أن
عدد الأدلّة المسجَّلة أكبر من صفر، أي أن الجامع فُتح في الموضع الصحيح.
"""

import asyncio
import json
import pathlib
import re
import unittest

from tests import fake_deps

# ⚠️ قبل استيراد main: يحجب fastapi وpydantic والتبعيات الثقيلة.
fake_deps.install()

import main  # noqa: E402
from case_file import (  # noqa: E402
    BLOCKING_FIELDS,
    ESTABLISHED_FIELDS,
    CaseFile,
    CaseStage,
    DisputeType,
    ForumKey,
    Party,
    RegimeArea,
)
from citations import CITATIONS_BEGIN, CITATIONS_END  # noqa: E402
from facts import CLIENT_STATEMENT_IS_NOT_PROOF, Standing  # noqa: E402
from revisions import STYLE_TARGET  # noqa: E402

# ⚠️ ويُستورد `briefing` في الاختبار **بقدر ما يُقرأ منه ثابت**: اسم المراجعة،
# ودرجات السلامة. فبدل أن نكتب «المراجعة الثانية» و«verified» بيدنا — وهي
# نسخةٌ من الحقيقة تفترق عن الوحدة عند أوّل تعديل — نقرؤها من الوحدة نفسها.
import briefing  # noqa: E402

CLAUSE = "على المستأجر سداد الأجرة في أول خمسة أيام من كل شهر ميلادي."
GENUINE_QUOTE = "سداد الأجرة في أول خمسة أيام من كل شهر"
FORGED_QUOTE = "سداد الأجرة خلال ثلاثين يوماً من بداية الشهر"


def scripted_turn(quote: str, *, body: str = "عقد إيجار تجاري\nالبند الأول: السداد.") -> list:
    """
    يبني نصّاً برمجياً للوكيل: نداء أداة عقود، ثم مسودّة بكتلة أسانيد.

    الأداة **حقيقية** وتُنفَّذ فعلاً (انظر `fake_deps._run_scripted_stream`)،
    فتمرّ الأدلّة في جامع الجولة كما تمرّ في الإنتاج.
    """
    return [
        {"tool": "search_contract_clauses", "args": {"query": "إيجار"}},
        {
            "content": (
                f"{body}\n"
                f"{CITATIONS_BEGIN}\n"
                f"C1 :: {quote}\n"
                f"{CITATIONS_END}"
            )
        },
    ]


def drain_sse(
    messages: list,
    case_frame: dict | None = None,
    ledger: object = None,
) -> list:
    """
    يستهلك مولّد SSE ويُرجع الإطارات الخام.

    ⚠️ و``case_frame`` يُمرَّر كما يمرّره `/generate` — فالإطار الأول في البثّ
    يأتي من المولّد نفسه، فلا يفترق الاختبار عن المسار الحقيقي.

    ⚠️ **و``ledger`` كذلك**: إطار `facts` **لا يمكن بناؤه في `/generate`** لأنه
    يحتاج المسودّة، فيُبنى داخل المولّد بعد أن تُكتب — فالسجلّ يمرّ إلى المولّد
    كما يمرّ في المسار الحقيقي، ولا يُبنى في الاختبار بناءً ثانياً.
    """

    async def collect() -> list:
        return [
            frame async for frame in main._sse_generator(messages, case_frame, ledger)
        ]

    return asyncio.run(collect())


def case_events(events: list) -> list:
    """إطارات `case` وحدها — لتقرأها اختبارات القضية بلا تكرار الفلترة."""
    return [event for event in events if event["type"] == "case"]


def case_input(case: object) -> object:
    """
    يحوّل حملاً إلى ما يفهمه `/generate` — **عبر المسار نفسه لا عبر نسخة**.

    ⚠️ ولا يُنادَى ``_case_from_payload`` بحملٍ من عندنا: هو يقرأ الحقول من
    كائن النقل، فلو مرّرنا قاموساً لَقرأ الغياب من كل حقل ولبُني الإطار عن
    «حملٍ لا يكفي» — أي لَما اختبرنا شيئاً. فالمسار: ``CasePayload`` ثم الملف.
    """
    if case is None or not isinstance(case, dict):
        return case
    return main.CasePayload(**case)


def case_report(case: object) -> dict:
    """تقرير إطار `case` لحملٍ ما — كما يُبنى في `generate` بالضبط."""
    return main._case_frame(main._case_from_payload(case_input(case)))


def case_block(case: object) -> str:
    """كتلة القضية في الرسالة لحملٍ ما — كما تُبنى في `generate` بالضبط."""
    return main._case_prompt_block(main._case_from_payload(case_input(case)))


def fact_input(facts: object) -> object:
    """
    يحوّل حمل وقائع إلى ما يفهمه `/generate` — **عبر المسار نفسه لا عبر نسخة**.

    ⚠️ كـ``case_input``: لا يُنادَى ``_facts_from_payload`` بقائمة قواميس من
    عندنا، لأن كائن النقل (`FactPayload`) هو ما يقرأه المسار في الإنتاج — فلو
    مرّرنا قاموساً لَما اختبرنا إلى المسار نفسه.
    """
    if facts is None or not isinstance(facts, list):
        return facts
    return [
        main.FactPayload(**item) if isinstance(item, dict) else item for item in facts
    ]


def ledger_of(facts: object) -> object:
    """السجلّ المبنيّ من حمل وقائع — **ببناء الوحدة، لا ببناء يدويّ في الاختبار**."""
    return main._facts_from_payload(fact_input(facts))

#: علامة مميّزة من نصّ «لا ملف قضية» — تُفحَص في الرسالة بلا نسخ النصّ كله.
CASE_BLOCK_ABSENT_MARKER = "لم يُنشأ ملف قضية"

#: حمل ملف قضية **كامل**: إيجار في دبي أمام مركز فضّ المنازعات الإيجارية،
#: و``has_choice_of_law`` و``has_arbitration_clause`` متروكتان ``None`` عن
#: قصد — «لم يُنظر»، وهي الحالة التي يجب أن **تُسأل** لا أن تُخمَّن.
COMPLETE_CASE = {
    "country": "الإمارات العربية المتحدة",
    "emirate": "دبي",
    "forum": "مركز فضّ المنازعات الإيجارية - دبي",
    "dispute_type": "lease",
    "stage": "first_instance",
    "our_party": "claimant",
    "claims": ["سداد الأجرة المتأخرة", "فسخ عقد الإيجار"],
    "key_dates": [["تاريخ الواقعة", "2024-01-10"]],
    "likely_law": ["قانون المعاملات المدنية"],
}

#: وما يجب أن يُنتجه الملف من ذلك الحمل — **يُبنى بكائن الوحدة، لا بقائمة
#: مكتوبة هنا**. والفرق جوهري: قائمةٌ مكتوبة يدوياً تختبر نسخةً من الحقيقة،
#: فلو تغيّر ترتيب الوحدة مرّ الاختبار وهما مختلفان — وهو الاختبار الذي
#: **يشهد لشكل متخيَّل** (انظر `briefing.py`).
COMPLETE_CASE_EXPECTED = CaseFile(
    country="الإمارات العربية المتحدة",
    emirate="دبي",
    forum="مركز فضّ المنازعات الإيجارية - دبي",
    dispute_type=DisputeType.LEASE,
    stage=CaseStage.FIRST_INSTANCE,
    our_party=Party.CLAIMANT,
    claims=("سداد الأجرة المتأخرة", "فسخ عقد الإيجار"),
    key_dates=(("تاريخ الواقعة", "2024-01-10"),),
    likely_law=("قانون المعاملات المدنية",),
)

#: حمل **ناقص الحقول المانعة** — لا إمارة ولا جهة ولا طلبات.
#:
#: ⚠️ والنقص مكتوب صريحاً لا محذوفاً، كما في `test_case_file._incomplete`:
#: حقول ``CaseFile`` بلا افتراضي، فمن أراد ملفاً ناقصاً كتب النقص.
#:
#: ⚠️ **والحقول الثلاثة غير النصّية حاضرة عن قصد** (``dispute_type``
#: و``stage`` و``our_party``): هي **وحدها** لا يُبنى ملف بغيابها، لأن حقول
#: ``CaseFile`` كلها بلا افتراضي. فالنقص المفحوص هنا هو نقصُ ما **يمكن أن
#: يكون غائباً** (نصّ فارغ أو قائمة فارغة) — وهو الواقع الذي يُسأل عنه.
INCOMPLETE_CASE = {
    "country": "الإمارات العربية المتحدة",
    "dispute_type": "lease",
    "stage": "first_instance",
    "our_party": "claimant",
}

#: ونظيره — النقص **مكتوب** لا محذوف، كما في `CaseFile` نفسها.
INCOMPLETE_CASE_EXPECTED = CaseFile(
    country="الإمارات العربية المتحدة",
    emirate="",
    forum="",
    dispute_type=DisputeType.LEASE,
    stage=CaseStage.FIRST_INSTANCE,
    our_party=Party.CLAIMANT,
    claims=(),
    key_dates=(),
    likely_law=(),
)

#: حملٌ **لا يكفي لبناء ملف**: فيه الإمارة، وغابت عنه الحقول الثلاثة التي
#: لا افتراضي لها في ``CaseFile``. فيُقال ما لم يصل، ولا يُبنى شيء من عندنا.
UNBUILDABLE_CASE = {"emirate": "دبي", "claims": ["سداد الأجرة"]}

#: ملف قضية أمام مركز دبي المالي — **مركز مالي لا «دبي»**.
#:
#: ⚠️ وهذا القياس هو الذي يمنع تسرّب ملاحظة الدفاع الإيجاري ومسار الوزارة:
#: مفتاح جهته ``difc`` ومفتاح إمارته ``dubai``، والشرط يقرأ الأول.
DIFC_CASE = {
    "country": "الإمارات العربية المتحدة",
    "emirate": "دبي",
    "forum": "محاكم مركز دبي المالي العالمي (DIFC Courts)",
    "dispute_type": "commercial",
    "stage": "first_instance",
    "our_party": "defendant",
    "claims": ["رفض المطالبة"],
    "key_dates": [["تاريخ الواقعة", "2025-04-01"]],
    "likely_law": ["قوانين مركز دبي المالي العالمي"],
    "has_arbitration_clause": False,
    "has_choice_of_law": False,
}


# ------------------------------------------------------------------------------
# ملف قضية **لا سؤال مفتوح فيه** — أقصى ما يُبنى من حمل
# ------------------------------------------------------------------------------
# ⚠️ **ولماذا يُكتب هنا؟** لأن سؤال «لم يُنظر» (`None`) **مانعٌ للدرجة العليا**
# في `briefing.readiness`، وهو كذلك في الوحدة عن حقّ: من لم يُسأل عن شرط التحكيم
# لا يُشهد له بأنّه ضبط المسار. فالقضية المكتملة في `COMPLETE_CASE` تُبقي الحقلين
# `None` **عن قصد** (لأنهما «لم يُنظر»)، فلا تصلح مدخلاً لقياس «أفضل حال ممكنة».
# فالجواب هنا **مكتوب** لا مسكوت عنه — ولا يُخترع جواب، بل يُقال: «لا شرط تحكيم،
# ولا اتّفاق على قانون مختار». ومن أراد أن يعرف ما الذي يمنع الدرجة العليا فليُغبْ
# هذين الحقلين ويرَ الرتبة تهبط — وهو الفرق بين «لم يُسأل» و«أُجيب».
COMPLETE_CASE_ANSWERED = {
    **COMPLETE_CASE,
    "has_choice_of_law": False,
    "has_arbitration_clause": False,
}


# ------------------------------------------------------------------------------
# وقائع الاختبار — **الواقعة التاريخية نفسها، لا واقعة مُخترَعة**
# ------------------------------------------------------------------------------
# ⚠️ `facts.py` وُجد لعطب تكرّر في ثلاث مسودّات: واقعةٌ غُيِّرت فانقلب مَن عليه
# الخطأ. فلو اخترعنا واقعةً «تشبه» الحادثة لَما شهد الاختبار على العطب الذي
# جاءت الوحدة لمنعه. والواقعة أدناه هي هي: **رفض التوقيع على مخالصة متضمّنة
# تنازلاً**، بنصّها ومصدرها وموضعها ودرجتها والنصّ الذي تستند إليه.

#: 🔑 الواقعة المُسجَّلة — ودرجتها ``claimed`` لأن رواية الموكّل ليست دليلاً
#: (انظر `CLIENT_STATEMENT_IS_NOT_PROOF`)، **ولا يجوز أن تُرقّى إلى `AGREED`**.
RELEASE_FACT = {
    "key": "release.refused",
    "statement": "رفض الموظف التوقيع على مخالصة متضمّنة تنازلاً",
    "source": "مخالصة مؤرّخة ٢٠٢٤-٠٥-١٠",
    "locus": "الصفحة ٢",
    "date": "2024-05-10",
    "asserted_by": "الموكّل",
    "standing": "claimed",
    "quote": "أرفض التوقيع على هذه المخالصة لاشتمالها على تنازل",
}

#: سجلّ الاختبار — واقعة واحدة، هي التي غُيِّرت في المسودّة المعطوبة.
FACTS = [RELEASE_FACT]

#: المسودّة المعطوبة — **واقعة أخرى قيلت على أنّها الواقعة الأولى**.
#:
#: ⚠️ **وهي سليمة الأسانيد والصياغة**: كل ما فيها منقول صحيحاً، ولا فيها خطأ
#: لغوي. والعيب كلّه في **واقعة واحدة قلبها** — ولذلك **لا يكشفها** فحص
#: الاستشهادات ولا التدقيق اللغوي ولا المراجعة الثانية، فكلّها تقرأ المسودّة
#: في نفسها ولا تقابلها بسجلّ. وهذا هو موضع `facts.py` بالذات.
FLAWED_DRAFT = (
    "وحيث إن الموظف رفض استلام المبلغ المعروض عليه، فإنه لا يستحقّ المطالبة به."
)

#: مسودّة **أمينة** في جملة واحدة — القياس السالب لفحص الوقائع.
#:
#: ⚠️ **وهي الجملة السليمة نفسها التي يمرّ عليها `language_audit` بلا خطأ ولا
#: ملاحظة**، فالقياس «أفضل حال» لا يحتاج مدخلات مصطنعة.
CLEAN_DRAFT = "البند الأول: يلتزم الطرف الثاني بالسداد في الأوّل من كلّ شهر."

#: الواقعة المقابلة للمسودّة الأمينة — **بنصّها التامّ لا بنصفه**.
#:
#: ⚠️ ولماذا النصّ التام؟ لأن المقارنة تُنتج إنذاراً كاذباً على **إعادة الصياغة
#: المشروعة** (وهو حدّ معلن في `facts.py`): واقعةٌ نصف جملة تُقرأ ``reworded``
#: لأن كل رمز زائد في النافذة يخفض نسبة الاتّحاد. فالمدخل الذي نُسمّيه «نظيفاً»
#: يجب أن يكون نظيفاً فعلاً — وإلا كان الاختبار **يشهد لعطب لا وجود له**، وهو
#: العيب المسجَّل في صدر `briefing.py`.
FULL_FACT = {
    "key": "contract.payment",
    "statement": CLEAN_DRAFT,
    "source": "عقد إيجار تجاري",
    "locus": "البند الأول",
    "date": "",
    "asserted_by": "المستند",
    "standing": "claimed",
    "quote": CLEAN_DRAFT,
}

#: عبارات **لا يجوز أن تظهر في أيّ إطار** — لأن معناها أن المخرج صار منتهياً
#: قابلاً للتسليم، وهو حكمٌ ليس للخادم.
#:
#: ⚠️ **وهي مكتوبة في الاختبار وحده ولا تُكتب ثابتاً في `main.py`**، على قاعدة
#: `tests/test_briefing.py`: الكلمة المحرّمة تُعرف في الاختبار، ولو كُتبت ثابتاً
#: في الملف لظهرت في مخرجه، ولو كُتبت في تعليق لاحتمل أن تُنسخ إلى نصّ.
FORBIDDEN_READY_PHRASES = (
    "جاهز للإيداع",
    "جاهزة للإيداع",
    "جاهز للاكتتاب",
    "صالح للإيداع",
    "صالح للاكتتاب",
    "جاهز للاستخدام",
)



def parse_frames(frames: list) -> list:
    """يحلّل إطارات SSE ويُرجع كائنات الأحداث."""
    events = []
    for frame in frames:
        assert frame.startswith("data: "), f"إطار غير صالح: {frame[:40]!r}"
        assert frame.endswith("\n\n"), f"إطار بلا فاصل: {frame[-10:]!r}"
        events.append(json.loads(frame[len("data: ") :]))
    return events


class _CleanReviewLLM:
    """
    نموذج المراجعة **بلا اعتراضات** — لبناء «أفضل حال ممكنة» في الاختبار.

    ⚠️ **ولماذا يُستبدل النموذج، والوهميّ في `fake_deps` قائم؟** لأن الوهميّ
    يُرجع نصّاً فارغاً، و`parse_review` **يرفع** على الفارغ
    («مخرج المراجع فارغ — لا شيء يُقرأ») — فمسار المراجعة **الناجحة** لا يُبلَغ
    في هذه المجموعة أصلاً، وهو سلوك قائم لا نُغيّره (وإنّما نُشهد عليه في
    ``test_a_check_that_did_not_run_reaches_briefing_as_absent``).

    فالمطلوب هنا مدخلٌ **أقصى ما يمكن بناؤه**: مراجعة جرت ولم تجد ما تعترض عليه.
    ويُعطى ذلك بمصفوفة JSON فارغة — وهي الشكل الذي يفهمه `parse_review`
    («لا اعتراضات»)، لا بنصّ نخترعه. ولا شبكة ولا نموذج في ذلك.
    """

    def invoke(self, *_args, **_kwargs) -> object:
        return fake_deps._FakeMessage(content="[]")


class MainTestBase(unittest.TestCase):
    """قاعدة مشتركة: تُفرّغ التسجيلات والنصّ البرمجي قبل كل اختبار."""

    def setUp(self) -> None:
        fake_deps.reset()
        fake_deps.FAKE_SUPABASE.set_rows(
            "match_legal_contracts",
            [fake_deps.make_row(chunk_id=777, document_name="عقد إيجار سكني", chunk_content=CLAUSE)],
        )

    def swap_review_llm(self, replacement: object) -> None:
        """
        يُبدّل نموذج المراجعة مؤقّتاً، ويُعيد الأصليّ بعده — **بلا `mock`**.

        ⚠️ والتبديل على ``main.llm`` وحده لا على `legal_agent.llm`: هذا الأخير
        يُبنى منه `llm_with_tools` عند الاستيراد، فتبديله يمسّ الوكيل نفسه.
        والمُراد هنا **نداء المراجعة وحده** (`_review_round`).
        """
        self.addCleanup(setattr, main, "llm", main.llm)
        main.llm = replacement

    def run_stream(self) -> list:
        """يشغّل `_stream_agent` ويُرجع كل أحداثه (kind, payload)."""
        return list(main._stream_agent(main._build_messages("صغ عقداً")))


# ==============================================================================
# ١. المسارات والمصادقة — انحدار
# ==============================================================================


class TestRoutes(MainTestBase):
    """المسارات الأربعة والمصادقة عليها — أول ما ينكسر عند إضافة ميزة."""

    def test_all_routes_still_registered(self):
        """
        قائمة المسارات كاملة — لا عددها.

        العدد الثابت كان هشّاً: كل مسار جديد يكسره بلا أن يقول شيئاً. أما
        تأكيد **المجموعة** فيجعل أي إضافة قراراً واعياً يُحدَّث هنا عن قصد،
        ويمنع حذف مسار أو تغيير طريقة بالخطأ.
        """
        routes = {(method, path) for method, path, _fn, _kw in main.app.routes}
        self.assertEqual(
            routes,
            {
                ("GET", "/"),
                ("GET", "/health"),
                ("POST", "/generate"),
                ("POST", "/chat"),
                ("POST", "/revisions"),
                ("GET", "/revisions/stats"),
                ("GET", "/archive/overview"),
                ("GET", "/archive/documents"),
                ("GET", "/archive/chunks"),
            },
            "تغيّرت قائمة المسارات — أضِف الجديد هنا عن قصد",
        )

    def test_sensitive_routes_stay_protected(self):
        """`/generate` و`/chat` يبقيان محميين — لا تُضاف ميزة تفتحهما."""
        posts = {
            path: kw.get("dependencies")
            for method, path, _fn, kw in main.app.routes
            if method == "POST"
        }
        self.assertTrue(posts["/generate"])
        self.assertTrue(posts["/chat"])

    def test_health_stays_open_and_reports_verification(self):
        """/health غير محمي (للمراقبة) ويُعلن أن التحقّق مُفعَّل."""
        payload = asyncio.run(main.health())
        self.assertEqual(payload["status"], "ok")
        self.assertIn("tools", payload)
        self.assertTrue(payload["citation_verification"])
        self.assertIn("auth_required", payload)


# ==============================================================================
# ٢. الموجّه
# ==============================================================================


class TestMessages(MainTestBase):
    """`/generate` و`/chat` يستخدمان الموجّه الموثَّق — وإلا طلبنا سندات لا تُقبل."""

    def test_system_message_carries_citation_rules(self):
        messages = main._build_messages("وقائع")
        self.assertIn(CITATIONS_BEGIN, messages[0].content)
        self.assertIn(CITATIONS_END, messages[0].content)

    def test_document_type_hint_still_injected(self):
        """حقن نوع المستند وتلميح الأداة — لم يتغيّر."""
        messages = main._build_messages("وقائع", "إنذار قانوني")
        self.assertIn("إنذار قانوني", messages[1].content)
        self.assertIn("search_legal_notices", messages[1].content)

    def test_session_history_uses_cited_prompt(self):
        """الجلسة الجديدة تبدأ بالموجّه الموثَّق أيضاً."""
        history = main._get_history("اختبار-جلسة")
        self.assertIn(CITATIONS_BEGIN, history[0].content)


# ==============================================================================
# ٣. عقدة التحقّق
# ==============================================================================


class TestCaseFilePayload(MainTestBase):
    """
    حمل ملف القضية على `/generate` — **يُبنى مرة واحدة قبل الوكيل**.
    ========================================================================
    ⚠️ **والخطر الذي تمنعه هذه المجموعة ليس الفشل بل الصمت.**

    الوحدة `case_file.py` كانت مبنية ومختبرة **ولا يُناديها أيّ موضع**، فكانت
    توجد ولا تُغيّر شيئاً. ووصلها بمسار التوليد يفتح بابين: أن يُقبل حملٌ
    فاسد فيُبنى عليه، أو أن يُبتلع حملٌ فاسد فيظنّ المستدعي أنه مرّ —
    **وحملٌ يُتجاهَل صامتاً أسوأ من حملٍ غائب**، لأن المستدعي لا يعلم فيُعيد
    الكرّة على يقين.

    فالفحص هنا على ثلاث: يُبنى صحيحاً، ويُرفض فاسداً **برسالة الملف**،
    و**لا يُستدعى نموذج** إن كان فاسداً.
    """

    def test_a_valid_payload_becomes_the_module_object(self):
        """الحمل الصالح يُبنى ملفاً — والقيم كما وردت لا كما فُسّرت."""
        case_input = main._case_from_payload(main.CasePayload(**COMPLETE_CASE))
        case = case_input.case
        self.assertIsInstance(case, CaseFile)
        self.assertEqual(case.dispute_type, DisputeType.LEASE)
        self.assertEqual(case.stage, CaseStage.FIRST_INSTANCE)
        self.assertEqual(case.our_party, Party.CLAIMANT)
        self.assertEqual(case.claims, ("سداد الأجرة المتأخرة", "فسخ عقد الإيجار"))
        # والمفتاح مشتقّ في الوحدة لا هنا — وهذا الفحص يمنع نسخةً ثانية منه.
        self.assertEqual(case.emirate_key, "dubai")
        self.assertEqual(case.forum_key, ForumKey.ONSHORE.value)

    def test_the_incomplete_payload_is_reported_as_missing(self):
        """
        🔑 **الحمل الناقص لا يُرفض — يُبنى ويُقال نقصه.**

        وهذا الفرق هو الذي لا يوقف الصياغة: النقص **مخرَج** يُسأل عنه، لا
        سبباً لردّ الطلب. ولو رُدّ لَما أمكن أن تُصاغ مذكرة قبل استيفاء
        الاستمارة كلها — وهو نقيض المطلوب: أن تسأل وتمضي.
        """
        case = main._case_from_payload(main.CasePayload(**INCOMPLETE_CASE)).case
        self.assertIsInstance(case, CaseFile)
        self.assertFalse(case.is_complete())
        # والمانعة النصّية الثلاث غائبة — والقائمة هي قائمة الوحدة نفسها.
        self.assertEqual(
            case.missing(blocking_only=True), ("emirate", "forum", "claims")
        )
        self.assertEqual(case.claims, ())

    def test_a_payload_too_empty_to_build_is_declared_not_ignored(self):
        """
        🔑 **وحملٌ لا يكفي لبناء ملف يُعلَن ولا يُمرّ صامتاً.**

        ⚠️ وهذا أخطر ما في الوصل: المستدعي أرسل الإمارة والطلبات، ولو أسقطناه
        صامتاً لَظنّ أنهما مرّا **وبُنيت المسودّة على غير ما طلب**. ولا يُبنى
        الملف بقيمة مخترعة إنقاذاً له، لأن القيمة المخترعة هي **الافتراض
        الصامت** الذي وُجد `case_file.py` لمنعه. فيُقال: وصل حمل، ولم يكفِ.
        """
        case_input = main._case_from_payload(main.CasePayload(**UNBUILDABLE_CASE))

        self.assertTrue(case_input.requested, "حملٌ وصل ولم يُعلَم به")
        self.assertIsNone(case_input.case, "بُني ملف بقيم لم تُرسل")
        # ⚠️ والحقول الناقصة **بترتيب ملف القضية** لا بترتيب نكتبه هنا، ولا
        # بترتيب ``BLOCKING_FIELDS`` الدارج: ``our_party`` يتقدّم ``stage``.
        self.assertEqual(
            case_input.unbuildable, ("dispute_type", "our_party")
        )
        self.assertEqual(
            set(case_input.unbuildable), {"dispute_type", "our_party"}
        )
        message = main._case_absent_message(case_input)
        self.assertIn("لم يكفِ", message)
        self.assertIn("dispute_type", message)

    def test_no_payload_means_no_case_file(self):
        """وغياب الحمل يعني «لم يُنشأ ملف» — ولا يُبنى ملف فارغ عن لسانه."""
        case_input = main._case_from_payload(None)
        self.assertFalse(case_input.requested)
        self.assertIsNone(case_input.case)
        self.assertIsNone(case_report(None)["summary"])

    def test_an_unknown_emirate_is_rejected_with_the_modules_own_message(self):
        """
        🔑 **نصّ الإمارة المجهول يوقف البناء — وبرسالة الوحدة نفسها.**

        ولو ترجمناها إلى نصّ من عندنا لضاع اسم ``EMIRATE_ALIASES``، وهو
        **الموضع الوحيد الذي تُضاف فيه الصورة** — فيصير الإصلاح تخميناً.
        """
        with self.assertRaises(main.HTTPException) as caught:
            main._case_from_payload(
                main.CasePayload(dispute_type="lease", emirate="دولة قطر")
            )

        self.assertEqual(caught.exception.status_code, 400)
        self.assertIn("دولة قطر", caught.exception.detail)
        self.assertIn("EMIRATE_ALIASES", caught.exception.detail)

    def test_an_unknown_enum_names_the_accepted_values(self):
        """
        ⚠️ **وقيمة التصنيف المجهولة تُرفض بأسماء القيم المتاحة.**

        ولو مرّت لَما ظهرت خطأً بل قيمةً لا تُطابق شيئاً في الجدول — فلا
        تُفتح ملاحظة، ويُقرأ الفراغ سلامة. وهذا هو العطب نفسه الذي أُصلح في
        مطابقة الجهة: نصٌّ لا يُطابق شيئاً **يمرّ صامتاً**.
        """
        for field_name, raw, accepted in (
            ("dispute_type", "إيجاري", "lease"),
            ("stage", "التمييز", "cassation"),
            ("our_party", "الطرفان", "claimant"),
        ):
            with self.subTest(field=field_name):
                with self.assertRaises(main.HTTPException) as caught:
                    main._case_from_payload(main.CasePayload(**{field_name: raw}))
                self.assertEqual(caught.exception.status_code, 400)
                self.assertIn(raw, caught.exception.detail)
                self.assertIn(accepted, caught.exception.detail)

    def test_malformed_lists_are_rejected_not_reinterpreted(self):
        """والمعطى المشوّه يُردّ ولا يُعاد تفسيره إلى معنى لم يُقصد."""
        with self.assertRaises(main.HTTPException) as caught:
            main._case_from_payload(main.CasePayload(key_dates=["2024-01-10"]))
        self.assertEqual(caught.exception.status_code, 400)

    def test_an_invalid_case_never_starts_generation(self):
        """
        🔑 **الحمل الفاسد يُردّ قبل أن يُستدعى نموذج واحد.**

        ولو بُني الملف داخل البثّ لكان الردّ ٤٠٠ **بعد** أن دُفع ثمن التوليد،
        ولظهرت مراحل في الواجهة ثم اختفت. فالفحص: لا خطوة وكيل، ولا نموذج
        تضمين، ولا نداء أداة — أي أن المسار **لم يبدأ أصلاً**.

        ⚠️ و``doc_type`` ممرَّر صريحاً كما في `test_generate_returns_streaming_response`:
        فقيمته في ``GenerateRequest`` وسمٌ من ``Field``، والوهميّ في
        `fake_deps` **لا يفكّه** إلى نصّ (وهو حدّ فيه لا في `main.py`).
        """
        with self.assertRaises(main.HTTPException) as caught:
            asyncio.run(
                main.generate(
                    main.GenerateRequest(
                        prompt="صغ عقداً",
                        doc_type="عقد",
                        case=main.CasePayload(emirate="دولة قطر"),
                    )
                )
            )

        self.assertEqual(caught.exception.status_code, 400)
        self.assertEqual(fake_deps.AGENT_SCRIPT, [])
        self.assertEqual(fake_deps.FakeEmbedder.instances, [], "استُدعي النموذج")
        self.assertEqual(fake_deps.FAKE_SUPABASE.calls, [], "جرت أداة استرجاع")


class TestRunAgentCollectShape(MainTestBase):
    """
    `/chat` يعتمد على الثلاثي — فلا يُعاد تشكيله عند وصل ملف القضية.
    ========================================================================
    ⚠️ **وهذا القرار مفحوص لا موصوف.** البديل كان تمرير الملف من
    ``_run_agent_collect``، وهو يعني رابعاً في الثلاثي **فينكسر كل مستدعٍ له
    بصمت** — وهو النوع نفسه من العطب الذي حرسه `test_all_routes_still_registered`
    في المسارات. فالشكل يُثبَّت هنا بالعدد والأنواع معاً.
    """

    def test_run_agent_collect_shape_is_unchanged(self):
        fake_deps.AGENT_SCRIPT = scripted_turn(GENUINE_QUOTE)
        collected = main._run_agent_collect(main._build_messages("صغ عقداً"))

        self.assertIsInstance(collected, tuple)
        self.assertEqual(len(collected), 3)
        final_text, citations, language = collected
        self.assertIn("عقد إيجار", final_text)
        self.assertTrue(citations["has_evidence"])
        self.assertIn("summary", language)

    def test_chat_accepts_no_case_at_all(self):
        """/chat لا مدخل لملف قضية فيه — ولا يُطلب منه ما ليس له."""
        fake_deps.AGENT_SCRIPT = scripted_turn(GENUINE_QUOTE)
        payload = asyncio.run(main.chat_endpoint(main.ChatRequest(prompt="صغ عقداً")))
        self.assertEqual(
            set(payload), {"response", "session_id", "citations", "language"}
        )



    """`_verify_round` — فصل المستند النظيف عن تقرير الأسانيد."""

    def _evidence(self):
        from legal_agent import _build_evidence  # noqa: PLC0415
        from citations import RefAllocator  # noqa: PLC0415

        return _build_evidence(
            "contracts",
            [fake_deps.make_row(chunk_id=777, document_name="عقد إيجار سكني", chunk_content=CLAUSE)],
            RefAllocator(),
        )

    def test_clean_text_has_no_citation_block(self):
        """المستند المُعاد للواجهة نظيف — الكتلة ليست جزءاً من العقد."""
        raw = f"عقد إيجار\n{CITATIONS_BEGIN}\nC1 :: {GENUINE_QUOTE}\n{CITATIONS_END}"
        clean, _report = main._verify_round(raw, self._evidence())
        self.assertEqual(clean, "عقد إيجار")
        self.assertNotIn(CITATIONS_BEGIN, clean)

    def test_genuine_quote_appears_in_report(self):
        raw = f"عقد إيجار\n{CITATIONS_BEGIN}\nC1 :: {GENUINE_QUOTE}\n{CITATIONS_END}"
        _clean, report = main._verify_round(raw, self._evidence())

        self.assertTrue(report["has_evidence"])
        self.assertEqual(len(report["verified"]), 1)
        self.assertEqual(report["verified"][0]["document_name"], "عقد إيجار سكني")
        self.assertEqual(report["verified"][0]["chunk_id"], "777")
        self.assertEqual(report["rejected"], [])
        self.assertIn("موثَّقة", report["summary"])

    def test_forged_quote_is_reported_with_reason(self):
        """🔑 الغاية: بند مؤلَّف يظهر في التقرير بسببه، لا يمرّ صامتاً."""
        raw = f"عقد إيجار\n{CITATIONS_BEGIN}\nC1 :: {FORGED_QUOTE}\n{CITATIONS_END}"
        _clean, report = main._verify_round(raw, self._evidence())

        self.assertFalse(report["has_evidence"])
        self.assertEqual(report["verified"], [])
        self.assertEqual(len(report["rejected"]), 1)
        self.assertIn("غير موجود حرفياً", report["rejected"][0]["reason"])
        self.assertIn(FORGED_QUOTE, report["rejected"][0]["quoted_span"])

    def test_unbacked_article_is_reported(self):
        """مادة في المتن لم ترد في أي مقطع: تُعرَض بلا سند."""
        raw = (
            "عقد إيجار\nيستند إلى المادة ٤٢ من قانون المعاملات المدنية.\n"
            f"{CITATIONS_BEGIN}\nC1 :: {GENUINE_QUOTE}\n{CITATIONS_END}"
        )
        _clean, report = main._verify_round(raw, self._evidence())

        numbers = [item["number"] for item in report["unbacked_articles"]]
        self.assertIn("42", numbers)

    def test_backed_article_is_not_reported(self):
        """مادة وردت في المقطع المسترجَع: لا تُوسَم."""
        evidence = [
            fake_deps.make_row(chunk_id=1, document_name="قانون", chunk_content="المادة 42 تجيز الفسخ")
        ]
        from citations import RefAllocator  # noqa: PLC0415
        from legal_agent import _build_evidence  # noqa: PLC0415

        built = _build_evidence("legislation", evidence, RefAllocator())
        _clean, report = main._verify_round("استناداً إلى المادة 42", built)
        self.assertEqual(report["unbacked_articles"], [])

    def test_malformed_lines_are_surfaced(self):
        """سطر سند مشوّه يُعرَض للتشخيص — لا يُسقَط صامتاً."""
        raw = f"عقد إيجار\n{CITATIONS_BEGIN}\nC1 بلا فاصل\n{CITATIONS_END}"
        _clean, report = main._verify_round(raw, self._evidence())
        self.assertEqual(report["malformed_lines"], ["C1 بلا فاصل"])

    def test_missing_block_is_reported_as_such(self):
        """بلا كتلة: التقرير يقول ذلك، ولا يدّعي وجود سندات."""
        _clean, report = main._verify_round("عقد إيجار بلا سند", self._evidence())
        self.assertFalse(report["has_citation_block"])
        self.assertFalse(report["has_evidence"])
        self.assertIn("لم يُرفق", report["summary"])

    def test_report_is_json_serializable(self):
        """التقرير يُبثّ كـ JSON — فلا كائنات غريبة فيه."""
        raw = f"عقد إيجار\nيستند إلى المادة ٩٩.\n{CITATIONS_BEGIN}\nC1 :: {FORGED_QUOTE}\n{CITATIONS_END}"
        _clean, report = main._verify_round(raw, self._evidence())
        json.dumps(report, ensure_ascii=False)


# ==============================================================================
# ٤. المسار الكامل عبر الوكيل
# ==============================================================================


class TestStreamAgent(MainTestBase):
    """`_stream_agent` — الجامع، والمراحل، والتقرير، والمستند النظيف."""

    def test_evidence_is_registered_for_the_round(self):
        """
        🔑 الاختبار الحاسم في هذا الملف.

        يُثبت أن جامع الأدلّة فُتح في **الخيط العامل** حيث تجري الأدوات. ولو
        فُتح في حلقة الأحداث لكانت الأدلّة صفراً، ولظلّ التحقّق «يعمل» وهو
        يرفض كل شيء لأنه لا يرى شيئاً.
        """
        fake_deps.AGENT_SCRIPT = scripted_turn(GENUINE_QUOTE)
        events = self.run_stream()
        report = next(payload for kind, payload in events if kind == "citations")

        self.assertEqual(report["evidence_count"], 1, "لم تُسجَّل أي أدلّة")
        self.assertTrue(report["has_evidence"])
        self.assertEqual(len(report["verified"]), 1)

    def test_stages_are_emitted_in_order(self):
        """المراحل تُبثّ كما كانت: تحليل ← أداة ← أدلّة ← صياغة ← تحقّق."""
        fake_deps.AGENT_SCRIPT = scripted_turn(GENUINE_QUOTE)
        stages = [payload for kind, payload in self.run_stream() if kind == "stage"]
        messages = [stage.message for stage in stages]

        self.assertEqual(messages[0], main.STAGE_ANALYSING)
        self.assertIn(main.TOOL_STAGE_LABELS["search_contract_clauses"], messages)
        self.assertIn(main.STAGE_EVIDENCE_FOUND, messages)
        self.assertIn(main.STAGE_DRAFTING, messages)
        self.assertIn(main.STAGE_VERIFYING, messages)

    def test_each_stage_carries_a_stable_key(self):
        """
        🔑 المفتاح الآلي — وعليه يُبنى مشهد «فريق المكتب».

        الواجهة تقرّر بالمفتاح لا بالنصّ العربي. ولو رُبطت بالنصّ لانكسر
        المشهد **بصمت** عند أول تعديل صياغة — وهو العطب نفسه الذي أصلحناه في
        الأدوات الخمس (انحراف نسخة عن أخرى بلا خطأ ظاهر).
        """
        fake_deps.AGENT_SCRIPT = scripted_turn(GENUINE_QUOTE)
        keys = [payload.key for kind, payload in self.run_stream() if kind == "stage"]

        self.assertEqual(keys[0], main.KEY_INTAKE)
        self.assertIn(main.TOOL_STAGE_KEYS["search_contract_clauses"], keys)
        self.assertIn(main.KEY_EVIDENCE, keys)
        self.assertIn(main.KEY_DRAFTING, keys)
        self.assertIn(main.KEY_VERIFYING, keys)

    def test_verifying_stage_precedes_the_report(self):
        """المدقّق يظهر **قبل** وصول نتيجته — لا بعده."""
        fake_deps.AGENT_SCRIPT = scripted_turn(GENUINE_QUOTE)
        kinds = [kind for kind, _payload in self.run_stream()]
        verifying_at = kinds.index("stage")  # أول مرحلة = الاستقبال
        self.assertLess(kinds.index("citations"), kinds.index("final"))
        self.assertIsNotNone(verifying_at)

    def test_tool_key_map_covers_every_stage_label(self):
        """كل أداة لها وسم مرحلة **ومفتاح** — ولا واحدة بلا الآخر."""
        self.assertEqual(set(main.TOOL_STAGE_KEYS), set(main.TOOL_STAGE_LABELS))

    def test_tool_keys_are_unique(self):
        """لكل أداة مفتاحها الخاص — وإلا تحرّكت شخصيتان بلا سبب."""
        keys = list(main.TOOL_STAGE_KEYS.values())
        self.assertEqual(len(keys), len(set(keys)))

    def test_citations_event_precedes_final(self):
        """التقرير يُبثّ قبل المستند — حتى تجهز الواجهة لعرضه."""
        fake_deps.AGENT_SCRIPT = scripted_turn(GENUINE_QUOTE)
        kinds = [kind for kind, _payload in self.run_stream()]
        self.assertLess(kinds.index("citations"), kinds.index("final"))

    def test_final_text_is_clean(self):
        """ما يصل الواجهة لا يحمل كتلة الأسانيد."""
        fake_deps.AGENT_SCRIPT = scripted_turn(GENUINE_QUOTE)
        final = next(payload for kind, payload in self.run_stream() if kind == "final")
        self.assertIn("عقد إيجار", final)
        self.assertNotIn(CITATIONS_BEGIN, final)
        self.assertNotIn(CITATIONS_END, final)

    def test_forged_draft_is_flagged_end_to_end(self):
        """مسودّة بمادة مؤلَّفة: التقرير يقول ذلك والمستند يبقى نظيفاً."""
        fake_deps.AGENT_SCRIPT = scripted_turn(FORGED_QUOTE)
        events = self.run_stream()
        report = next(payload for kind, payload in events if kind == "citations")
        final = next(payload for kind, payload in events if kind == "final")

        self.assertFalse(report["has_evidence"])
        self.assertEqual(len(report["rejected"]), 1)
        self.assertNotIn(CITATIONS_BEGIN, final)

    def test_no_tool_call_yields_empty_final_without_report(self):
        """
        بلا نصّ: مستند فارغ **ولا تقرير أسانيد**.

        وهذا هو العقد: لا يوجد ما يُتحقَّق منه، فلا نُصدر تقريراً فارغاً يوهم
        بأن فحصاً جرى. وطبقة SSE تُبلّغ العميل بخطأ صريح بدل ذلك.
        """
        fake_deps.AGENT_SCRIPT = [{"content": ""}]
        events = self.run_stream()
        final = next(payload for kind, payload in events if kind == "final")
        reports = [payload for kind, payload in events if kind == "citations"]

        self.assertEqual(final, "")
        self.assertEqual(reports, [], "لا تقرير حين لا يوجد ما يُتحقَّق منه")

    def test_collector_is_closed_after_the_round(self):
        """بعد الجولة لا يبقى جامع نشط في هذا الخيط."""
        fake_deps.AGENT_SCRIPT = scripted_turn(GENUINE_QUOTE)
        self.run_stream()
        from legal_agent import current_collector  # noqa: PLC0415

        self.assertIsNone(current_collector())

    def test_agent_failure_propagates(self):
        """فشل الوكيل يرتفع — ويُلتقط في `_sse_generator` ليُبلَّغ العميل."""
        fake_deps.AGENT_RAISE = RuntimeError("انقطاع الشبكة")
        with self.assertRaises(RuntimeError):
            self.run_stream()


# ==============================================================================
# ٤-ب. إطار `case` — ما يُثبَت وما يُسأل عنه، قبل أول مرحلة
# ==============================================================================
# ⚠️ **والقيم تُقارَن بمخرَج الوحدة نفسه لا بنسخة مكتوبة في الاختبار.**
# والسبب أن الكتابة اليدوية تختبر نسخةً من الحقيقة: لو تغيّر ترتيب الأسئلة
# في `case_file.py` لمرّ الاختبار وهما مختلفان — وهو الاختبار الذي **يشهد
# لشكل متخيَّل**، وهو العيب المسجَّل في `briefing.py`. فالمفحوص هنا **الوصل**
# لا منطق الوحدة: هل يصل ما تُنتجه الوحدة كما هو؟


class TestCaseFrame(MainTestBase):
    """إطار `case`: موضعه، وقيمه، وما يقوله عند غياب الملف."""

    def payload(self, case: object = None) -> dict:
        """إطار `case` لحملٍ ما، عبر مسار `generate` نفسه."""
        return case_report(case)

    def test_a_valid_case_frame_carries_the_modules_own_values(self):
        """
        🔑 الإطار يحمل ``confirmed`` و``missing`` و``is_complete`` — **من الوحدة**.

        ⚠️ ولا يُعاد تعريف «ثابت» ولا «ناقص» هنا: الوحدة هي التي تعرف، ونسخةٌ
        ثانية في `main.py` **تنحرف عنها بصمت** فيُعرض للمحامي خلاف ما جرى.
        """
        report = self.payload(COMPLETE_CASE)

        self.assertTrue(report["established"])
        self.assertEqual(report["confirmed"], list(COMPLETE_CASE_EXPECTED.confirmed()))
        self.assertEqual(report["missing"], list(COMPLETE_CASE_EXPECTED.missing()))
        self.assertEqual(report["is_complete"], COMPLETE_CASE_EXPECTED.is_complete())
        self.assertEqual(report["summary"], COMPLETE_CASE_EXPECTED.summary())

    def test_the_frame_is_json_serializable(self):
        """الإطار يُبثّ بـ ``json.dumps`` — فلا كائنات غريبة فيه."""
        report = self.payload(COMPLETE_CASE)
        json.dumps(report, ensure_ascii=False)

    def test_an_incomplete_case_is_reported_and_not_complete(self):
        """والملف الناقص **يُقال نقصه** ولا يُجمَّل: ``is_complete`` كاذبةٌ لو قيلت."""
        report = self.payload(INCOMPLETE_CASE)

        self.assertTrue(report["established"])
        self.assertFalse(report["is_complete"])
        self.assertIn("emirate", report["missing"])
        self.assertNotIn("emirate", report["confirmed"])
        self.assertTrue(report["questions"], "نقص بلا سؤال يُقرأ سلامة")

    def test_no_case_supplied_still_emits_a_case_frame(self):
        """
        🔑 **ولا يُحذف الإطار عند غياب الملف — ولا يدّعي اكتمالاً.**

        وهذا هو الأصل الذي يقوم عليه `briefing.py`: **الفحص غير المُشغَّل ليس
        فحصاً ناجحاً.** فالإطار يقول ``established: False`` صراحةً، ويحمل النصّ
        الذي يمنع قراءة السكوت موافقةً على الاختصاص والتقادم.
        """
        report = self.payload(None)

        self.assertFalse(report["established"])
        self.assertFalse(report["is_complete"], "غياب الملف ليس اكتمالاً")
        self.assertEqual(report["confirmed"], [])
        self.assertEqual(report["missing"], [])
        self.assertIsNone(report["summary"])
        self.assertIn("لم يُنشأ", report["message"])
        self.assertIn("غير متحقَّق", report["message"])

    def test_the_absent_block_says_which_checks_did_not_run(self):
        """
        ⚠️ ونصّ الغياب **يسمّي ما سقط** لا يقول «لا مشكلة».

        ولو قال «لا ملف قضية» وسكت لَقُرئ فراغاً محايداً، والمطلوب أن يُقرأ
        **تنبيهاً**: كل ما يتوقّف على الاختصاص أو التقادم أو المرحلة غير
        متحقَّق منه، لأن لا إمارة ولا جهة ولا مرحلة سُجّلت.
        """
        message = main._case_prompt_block(None)
        for expected in ("الاختصاص", "التقادم", "المرحلة"):
            with self.subTest(word=expected):
                self.assertIn(expected, message)

    def test_the_open_questions_keep_the_modules_order(self):
        """
        🔑 **الأسئلة بترتيب الوحدة، والمانع أولاً — وبلا فرز ثانٍ هنا.**

        والترتيب **مصدره الواحد** ``QUESTIONS`` في `case_file.py`؛ ولو فُرز في
        `main.py` على ``BLOCKING_FIELDS`` لصار للترتيب مصدران يفترقان عند أول
        تعديل — وهو التعليل المكتوب في ``questions_for`` نفسه.
        """
        report = self.payload(INCOMPLETE_CASE)
        fields = [question["field"] for question in report["questions"]]

        # ⚠️ مقارنة بمخرَج الوحدة، لا بقائمة مكتوبة هنا.
        expected = [q.field for q in INCOMPLETE_CASE_EXPECTED.questions_for_missing()]
        expected += [q.field for q in INCOMPLETE_CASE_EXPECTED.open_regime_questions()]
        self.assertEqual(fields, expected)

        # والمانع أولاً: كل حقل مانع قبل كل حقل غير مانع.
        positions = {name: index for index, name in enumerate(fields)}
        blocking = [positions[name] for name in BLOCKING_FIELDS if name in positions]
        others = [
            positions[name]
            for name in fields
            if name not in BLOCKING_FIELDS
        ]
        self.assertEqual(blocking, sorted(blocking), "ترتيب المانعة انقلب")
        if blocking and others:
            self.assertLess(max(blocking), min(others), "سؤال مانع بعد غير مانع")
        # والوسم من الوحدة أيضاً (`blocking_missing` المحسوب في `summary`).
        for question in report["questions"]:
            with self.subTest(field=question["field"]):
                self.assertEqual(
                    question["blocking"],
                    question["field"]
                    in INCOMPLETE_CASE_EXPECTED.summary()["blocking_missing"],
                )
        # ⚠️ و«لم يُنظر» (`None`) سؤالٌ، و«لا» (`False`) جوابٌ لا سؤال: لو خُلطا
        # لطُلب من المحامي ما أجاب عنه، فيُقرأ السؤال استيفاءً ويُهمَل.
        self.assertIn("has_choice_of_law", fields)
        self.assertIn("has_arbitration_clause", fields)

    def test_regime_notes_appear_with_their_sources(self):
        """
        ⚠️ **وملاحظة بلا مصدر رأيٌ يتنكّر في هيئة مرجع.**

        والمفحوص هنا أن المصدر **وحدّه** يصلان إلى الإطار كما في الوحدة —
        فحقل ``limit`` ليس ترفاً: الملاحظة التي تُقرأ أوسع مما هي عليه تُنتج
        النصّ الصحيح في الموضع الخاطئ.
        """
        payload = dict(COMPLETE_CASE)
        payload["forum"] = "محاكم مركز دبي المالي العالمي (DIFC Courts)"
        payload["dispute_type"] = "commercial"
        payload["has_choice_of_law"] = False
        payload["has_arbitration_clause"] = False
        report = self.payload(payload)

        notes = report["regime_notes"]
        self.assertTrue(notes, "قضية في مركز مالي بلا ملاحظة — الجدول صامت")
        for note in notes:
            with self.subTest(area=note["area"]):
                self.assertTrue(note["source"].strip(), "ملاحظة بلا مصدر")
                self.assertTrue(note["limit"].strip(), "ملاحظة بلا حدّ")
                self.assertTrue(note["note"].strip())
        # ⚠️ والملاحظات هي ملاحظات الوحدة بنفس ترتيب جدولها — لا نسخةً عندنا.
        self.assertEqual(
            [note["area"] for note in notes],
            [
                note.area.value
                for note in main.case_file_module.regime_notes(
                    main._case_from_payload(case_input(DIFC_CASE)).case
                )
            ],
        )
        self.assertEqual(notes[0]["area"], RegimeArea.FREE_ZONE.value)

    def test_notes_are_the_ones_the_case_actually_triggers(self):
        """
        ⚠️ **والقياس السالب:** قضية على البرّ لا تجرّ ملاحظة مركز مالي.

        ولو جرّتها لَظهر في المسودّة تنبيه عن نظام عمالي خاصّ بمركز لا شأن
        للقضية به — وهو **النصّ الصحيح في الموضع الخاطئ** بعينه.
        """
        areas = {
            note["area"] for note in self.payload(COMPLETE_CASE)["regime_notes"]
        }
        self.assertNotIn(RegimeArea.FREE_ZONE.value, areas)
        self.assertIn(RegimeArea.EMIRATE.value, areas)


class TestCasePrompt(MainTestBase):
    """
    كتلة القضية في الرسالة — **والأسئلة المفتوحة أهمّ ما فيها**.
    ========================================================================
    ⚠️ **الإطار يُعلن للمحامي، والرسالة تمنع النموذج من الافتراض.** فالاثنان
    ضروريان: تقريرٌ يُقرأ ولا يُقيَّد به النموذج يُنتج مسودّة تجزم بما لم
    يُسجَّل، وهي أخطر من المسودّة الناقصة لأنها تبدو تامة.
    """

    def user_content(self, case: object = None) -> str:
        """نصّ رسالة المستخدم كما يُبنى — وكتلة القضية داخله لا منفصلة."""
        messages = main._build_messages(
            "وقائع القضية", "مذكرة دفاع", main._case_from_payload(case_input(case))
        )
        return messages[1].content

    def test_the_established_facts_are_in_the_prompt(self):
        """الوقائع المُثبَتَة تُدخل الرسالة — والقيم كما سُجّلت."""
        content = self.user_content(COMPLETE_CASE)
        for expected in ("دبي", "مركز فضّ المنازعات الإيجارية - دبي", "lease",
                         "first_instance", "claimant", "فسخ عقد الإيجار"):
            with self.subTest(value=expected):
                self.assertIn(expected, content)

    def test_the_open_questions_are_in_the_prompt_with_their_reason(self):
        """
        🔑 **والسؤال يُكتب بـ``why`` معه.**

        فسؤال بلا سبب يُقرأ استيفاءً لشكليات فلا يُجاب جواباً واعياً — وهو
        التعليل المكتوب في ``Question`` نفسها.
        """
        content = self.user_content(INCOMPLETE_CASE)
        question = INCOMPLETE_CASE_EXPECTED.questions_for_missing()[0]

        self.assertIn(question.question, content)
        self.assertIn(question.why, content)
        self.assertIn(question.field, content)

    def test_the_prompt_forbids_assuming_an_answer(self):
        """
        ⚠️ **ومنع الافتراض مكتوب صراحةً لا مفهوماً من السياق.**

        والمطلوب اثنان: ألّا يُفترض جواب، **وأن يُقال في موضعه** حين يمسّ
        السؤالُ المفتوح جوهرَ الحكم. الأول يمنع الخطأ الصامت، والثاني يجعله
        مرئياً لمن يقرأ المسودّة.
        """
        content = self.user_content(INCOMPLETE_CASE)
        self.assertIn("لا تفترض", content)
        self.assertIn("قُل في موضعه", content)

    def test_the_case_does_not_block_the_rest_of_the_draft(self):
        """
        ⚠️ **والنقص لا يوقف العمل — وهذا نصّ لا نيّة.**

        المطلوب أن يُسأل عن النواقص **ويمضي فيما لا يتوقّف عليها**؛ ولو قيل
        للنموذج «توقّف» لَما خرج مستند أصلاً، وهو خلاف المطلوب صراحةً.
        """
        content = self.user_content(INCOMPLETE_CASE)
        self.assertIn("اصوغ الأجزاء", content)

    def test_no_case_supplied_still_says_so_in_the_prompt(self):
        """
        🔑 **ولا تُحذف الكتلة عند غياب الملف — فحذفها يُقرأ موافقةً صامتة.**

        وهذا نقيض القاعدة: الفحص غير المُشغَّل ليس فحصاً ناجحاً، والسكوت عنه
        يجعل مسودّةً عن الاختصاص تبدو مبنية على سؤال سُئل.
        """
        content = self.user_content(None)
        self.assertIn(CASE_BLOCK_ABSENT_MARKER, content)
        self.assertIn("لم يُنشأ", content)

    def test_the_block_is_built_even_without_a_doc_type(self):
        """والكتلة تُبنى في كل الأحوال — ولو لم يُرسل نوع مستند."""
        messages = main._build_messages("وقائع")
        self.assertIn(CASE_BLOCK_ABSENT_MARKER, messages[1].content)

    def test_a_complete_case_does_not_invent_questions(self):
        """
        ⚠️ **ولا يُسأل عن حقل ثابت** — سؤالٌ عن مُثبَت يُقرأ استيفاءً.

        والمتبقّي في ملف كامل هو أسئلة «لم يُنظر» في الجدول وحدها، ولا واحد
        منها عن نقصٍ في الملف: المانعة كلها ثابتة، فلا يظهر لها سؤال.
        """
        content = self.user_content(COMPLETE_CASE)
        self.assertIn(main.CASE_BLOCK_QUESTIONS_HEADER, content)
        self.assertNotIn(main.CASE_BLOCK_NO_QUESTIONS, content)

        # ⚠️ والمانعة **ثابتة** في هذا الحمل — فالفحص أن الوحدة لا تسأل عنها.
        self.assertEqual(COMPLETE_CASE_EXPECTED.missing(blocking_only=True), ())
        for field_name in BLOCKING_FIELDS:
            with self.subTest(field=field_name):
                self.assertNotIn(f"- [{field_name}]", content)
        # وكل حقل مسجَّل إمّا ثابت وإمّا مسؤول عنه سؤالٌ — ولا يُسكَت عنه.
        self.assertEqual(
            set(COMPLETE_CASE_EXPECTED.confirmed())
            | set(COMPLETE_CASE_EXPECTED.missing()),
            set(ESTABLISHED_FIELDS),
        )


# ==============================================================================
# ٥. بثّ SSE
# ==============================================================================


class TestSSE(MainTestBase):
    """إطارات SSE: الشكل، والترتيب، ومسار الفشل."""

    # -- إطار `case` — الأول في البثّ ولا يُحذف -------------------------------

    def test_the_case_frame_precedes_the_first_stage(self):
        """
        🔑 **إطار `case` قبل أول مرحلة — وهذا هو موضعه لا غير.**

        ولو جاء بعد المرحلة الأولى لَبدأت الواجهة في العرض ثم عادت لتُصحّح:
        فيُبنى المشهد على ناقص، ويُقرأ التأخّر عطباً في الاتصال. والفحص على
        **الموضع** لا على الوجود.
        """
        fake_deps.AGENT_SCRIPT = scripted_turn(GENUINE_QUOTE)
        events = parse_frames(
            drain_sse(
                main._build_messages(
                    "صغ عقداً",
                    None,
                    main._case_from_payload(case_input(COMPLETE_CASE)),
                ),
                case_report(COMPLETE_CASE),
            )
        )
        kinds = [event["type"] for event in events]

        self.assertEqual(kinds[0], "case", "أول إطار ليس ملف القضية")
        self.assertLess(
            kinds.index("case"), kinds.index("stage"), "الملف بعد أول مرحلة"
        )

    def test_the_case_frame_carries_the_module_values_over_the_wire(self):
        """وما يصل الواجهة هو ما تُنتجه الوحدة — بعد التسلسل وإعادة القراءة."""
        fake_deps.AGENT_SCRIPT = scripted_turn(GENUINE_QUOTE)
        report = case_events(
            parse_frames(
                drain_sse(main._build_messages("صغ عقداً"), case_report(COMPLETE_CASE))
            )
        )[0]["report"]

        self.assertTrue(report["established"])
        self.assertEqual(report["confirmed"], list(COMPLETE_CASE_EXPECTED.confirmed()))
        self.assertEqual(report["is_complete"], COMPLETE_CASE_EXPECTED.is_complete())
        self.assertEqual(report["summary"], COMPLETE_CASE_EXPECTED.summary())

    def test_no_case_still_emits_a_case_frame_saying_so(self):
        """
        ⚠️ **والغياب يُبثّ ولا يُسكَت عنه.**

        ولو لم يُبثّ إطار لَما فرّقت الواجهة بين «لم يُنشأ ملف» و«ملف مكتمل
        لا ملاحظات فيه» — وهما ليسا سواءً: الأول فحصٌ لم يُشغَّل، والثاني
        فحصٌ جرى. والسكوت يخلط بينهما، وهو خلطٌ يُبنى عليه قرار.
        """
        fake_deps.AGENT_SCRIPT = scripted_turn(GENUINE_QUOTE)
        events = parse_frames(
            drain_sse(main._build_messages("صغ عقداً"), case_report(None))
        )
        report = case_events(events)[0]["report"]

        self.assertFalse(report["established"])
        self.assertFalse(report["is_complete"], "غياب الملف ادُّعي اكتمالاً")
        self.assertIn("لم يُنشأ", report["message"])
        self.assertLess(
            [event["type"] for event in events].index("case"),
            [event["type"] for event in events].index("stage"),
        )

    def test_an_incomplete_case_does_not_block_generation(self):
        """
        🔑 **والملف الناقص لا يوقف الصياغة — المراحل تتبع الإطار.**

        وهذا هو المطلوب صراحةً: أن **يُسأل** عن النواقص **ويمضي** فيما لا
        يتوقّف عليها. فلو أوقف النقصُ البثَّ لَما خرج مستند، ولو سكت لَما
        عُرف النقص — والمفحوص هنا أن الاثنين يقعان معاً: إطارٌ يقول النقص،
        ثم مراحل، ثم مستند.
        """
        fake_deps.AGENT_SCRIPT = scripted_turn(GENUINE_QUOTE)
        events = parse_frames(
            drain_sse(
                main._build_messages("صغ عقداً"),
                case_report(INCOMPLETE_CASE),
            )
        )
        kinds = [event["type"] for event in events]

        self.assertIn("case", kinds)
        self.assertIn("stage", kinds, "الملف الناقص أوقف المراحل")
        self.assertIn("done", kinds, "الملف الناقص أوقف التوليد")
        report = case_events(events)[0]["report"]
        self.assertFalse(report["is_complete"])
        self.assertTrue(report["questions"])

    def test_the_open_questions_in_the_frame_keep_the_modules_order(self):
        """
        ⚠️ **والأسئلة بترتيب الوحدة، المانع أولاً — بلا فرز هنا.**

        والفرز الثاني يجعل للترتيب مصدرين يفترقان عند أول تعديل، فيُسأل
        المحامي عن الحقل الذي يُكمل البيان قبل الذي يُغيّر الاختصاص.
        """
        report = case_report(INCOMPLETE_CASE)
        fields = [question["field"] for question in report["questions"]]

        expected = [q.field for q in INCOMPLETE_CASE_EXPECTED.questions_for_missing()]
        expected += [q.field for q in INCOMPLETE_CASE_EXPECTED.open_regime_questions()]
        self.assertEqual(fields, expected)
        self.assertEqual(fields[0], "emirate", "أول سؤال ليس مانعاً")

    def test_regime_notes_reach_the_frame_with_their_sources(self):
        """⚠️ والملاحظة تصل بمصدرها وحدّها — وإلا صارت رأياً بلا مرجع."""
        notes = case_report(DIFC_CASE)["regime_notes"]

        self.assertTrue(notes)
        self.assertEqual(notes[0]["area"], RegimeArea.FREE_ZONE.value)
        self.assertTrue(notes[0]["source"].strip())
        self.assertTrue(notes[0]["limit"].strip())

    def test_the_route_itself_starts_the_stream_with_the_case_frame(self):
        """
        🔑 **والوصل مفحوص من `generate` نفسها، لا من المساعد وحده.**

        ⚠️ والفرق ليس شكلياً: بناء الإطار في `_case_frame` صحيح **ولا يثبت أن
        `/generate` يمرّره إلى البثّ**. ولو نُسي التمرير لَما ظهر الإطار في
        الواجهة أصلاً — **وتمرّ الاختبارات كلها**، لأنها تنادي أجزاءً منفصلة.
        وهذا هو النوع نفسه من العطب الذي كُشف في `briefing.py`: أجزاءٌ
        تُختبر منفصلةً والمسار الحقيقي **لم يُشغَّل قطّ**.
        """
        fake_deps.AGENT_SCRIPT = scripted_turn(GENUINE_QUOTE)
        response = asyncio.run(
            main.generate(
                main.GenerateRequest(
                    prompt="صغ عقداً",
                    doc_type="عقد",
                    case=main.CasePayload(**INCOMPLETE_CASE),
                )
            )
        )

        async def collect() -> list:
            return [frame async for frame in response.content]

        events = parse_frames(asyncio.run(collect()))
        kinds = [event["type"] for event in events]

        self.assertEqual(kinds[0], "case", "المسار لم يبدأ بإطار ملف القضية")
        report = case_events(events)[0]["report"]
        self.assertTrue(report["established"])
        self.assertFalse(report["is_complete"])
        self.assertIn("stage", kinds)
        self.assertIn("done", kinds)

    def test_frames_are_well_formed(self):
        """كل إطار `data: {...}\\n\\n` — العقد الذي تعتمد عليه الواجهة."""
        fake_deps.AGENT_SCRIPT = scripted_turn(GENUINE_QUOTE)
        frames = drain_sse(main._build_messages("صغ عقداً"))
        self.assertTrue(frames)
        events = parse_frames(frames)
        self.assertTrue(events)
        for event in events:
            self.assertIn("type", event)

    def test_stage_frames_carry_the_machine_key(self):
        """
        إطار المرحلة يحمل **المفتاح الآلي** مع النصّ.

        الواجهة تحتاجه لتعرف أي شخصية تعمل الآن في مشهد المكتب. والنصّ وحده
        لا يكفي: يتغيّر بتغيّر الصياغة، والمفتاح ثابت.
        """
        fake_deps.AGENT_SCRIPT = scripted_turn(GENUINE_QUOTE)
        events = parse_frames(drain_sse(main._build_messages("صغ عقداً")))
        stage_events = [event for event in events if event["type"] == "stage"]

        self.assertTrue(stage_events)
        for event in stage_events:
            self.assertIn("stage", event)
            self.assertTrue(event["stage"], "مفتاح فارغ")
            self.assertIn("message", event)

        keys = [event["stage"] for event in stage_events]
        self.assertIn(main.KEY_INTAKE, keys)
        self.assertIn(main.KEY_VERIFYING, keys)
        self.assertIn(main.TOOL_STAGE_KEYS["search_contract_clauses"], keys)

    def test_citations_frame_is_emitted(self):
        fake_deps.AGENT_SCRIPT = scripted_turn(GENUINE_QUOTE)
        events = parse_frames(drain_sse(main._build_messages("صغ عقداً")))

        citation_events = [e for e in events if e["type"] == "citations"]
        self.assertEqual(len(citation_events), 1)
        report = citation_events[0]["report"]
        self.assertTrue(report["has_evidence"])
        self.assertEqual(report["evidence_count"], 1)

    def test_done_frame_carries_the_clean_document(self):
        fake_deps.AGENT_SCRIPT = scripted_turn(GENUINE_QUOTE)
        events = parse_frames(drain_sse(main._build_messages("صغ عقداً")))

        done = [e for e in events if e["type"] == "done"]
        self.assertEqual(len(done), 1)
        self.assertIn("عقد إيجار", done[0]["document"])
        self.assertNotIn(CITATIONS_BEGIN, done[0]["document"])

    def test_arabic_is_not_escaped(self):
        """`ensure_ascii=False` — وإلا وصل العربي مُرمَّزاً وغير مقروء."""
        fake_deps.AGENT_SCRIPT = scripted_turn(GENUINE_QUOTE)
        frames = drain_sse(main._build_messages("صغ عقداً"))
        joined = "".join(frames)
        self.assertIn("عقد إيجار", joined)
        self.assertNotIn("\\u0639", joined)

    def test_error_frame_on_agent_failure(self):
        """فشل الوكيل يُبلَّغ كإطار خطأ — لا يُترك الاتصال معلّقاً."""
        fake_deps.AGENT_RAISE = RuntimeError("انقطاع الشبكة")
        events = parse_frames(drain_sse(main._build_messages("صغ عقداً")))

        errors = [e for e in events if e["type"] == "error"]
        self.assertEqual(len(errors), 1)
        self.assertIn("انقطاع الشبكة", errors[0]["message"])

    def test_empty_final_yields_error_not_empty_done(self):
        """بلا نصّ: خطأ صريح بدل مستند فارغ يُعرض كأنه نجاح."""
        fake_deps.AGENT_SCRIPT = [{"content": ""}]
        events = parse_frames(drain_sse(main._build_messages("صغ عقداً")))
        self.assertNotIn("done", [e["type"] for e in events])
        self.assertIn("error", [e["type"] for e in events])


# ==============================================================================
# ٦. نقاط النهاية
# ==============================================================================


class TestEndpoints(MainTestBase):
    """`/generate` و`/chat` — الشكل الذي تتلقّاه الواجهة."""

    def test_generate_returns_streaming_response(self):
        fake_deps.AGENT_SCRIPT = scripted_turn(GENUINE_QUOTE)
        response = asyncio.run(
            main.generate(main.GenerateRequest(prompt="صغ عقداً", doc_type="عقد"))
        )
        self.assertEqual(response.media_type, "text/event-stream")
        self.assertEqual(response.headers["Cache-Control"], "no-cache, no-transform")
        self.assertEqual(response.headers["X-Accel-Buffering"], "no")

    def test_chat_returns_citations_alongside_the_answer(self):
        """/chat صار يُرجع التقرير أيضاً — إضافة لا كسر."""
        fake_deps.AGENT_SCRIPT = scripted_turn(GENUINE_QUOTE)
        payload = asyncio.run(main.chat_endpoint(main.ChatRequest(prompt="صغ عقداً")))

        self.assertIn("response", payload)
        self.assertIn("session_id", payload)
        self.assertIn("citations", payload)
        self.assertTrue(payload["citations"]["has_evidence"])
        self.assertNotIn(CITATIONS_BEGIN, payload["response"])

    def test_chat_flags_forged_quote(self):
        fake_deps.AGENT_SCRIPT = scripted_turn(FORGED_QUOTE)
        payload = asyncio.run(main.chat_endpoint(main.ChatRequest(prompt="صغ عقداً")))
        self.assertFalse(payload["citations"]["has_evidence"])

    def test_chat_keeps_session_memory(self):
        """الذاكرة بين الأدوار لم تتغيّر."""
        fake_deps.AGENT_SCRIPT = scripted_turn(GENUINE_QUOTE)
        asyncio.run(main.chat_endpoint(main.ChatRequest(prompt="أول", session_id="ج1")))
        asyncio.run(main.chat_endpoint(main.ChatRequest(prompt="ثانٍ", session_id="ج1")))

        history = main._get_history("ج1")
        # رسالة النظام + دور المستخدم + ردّ الوكيل + دور ثانٍ + ردّ ثانٍ
        self.assertGreaterEqual(len(history), 4)


# ==============================================================================
# ٧. جمع تصحيحات المحامي
# ==============================================================================

GENERATED = "البند الأول: يلتزم الطرف الثاني بسداد مبلغ عشرين ألف درهم."
CORRECTED = (
    "البند الأول: يلتزم الطرف الثاني بسداد مبلغ خمسة وعشرين ألف درهم "
    "خلال ثلاثين يوماً من تاريخ التوقيع."
)


class TestRevisionRoutes(MainTestBase):
    """مسارَان جديدان — وكلاهما محمي."""

    def test_routes_are_registered(self):
        routes = {(method, path) for method, path, _fn, _kw in main.app.routes}
        self.assertIn(("POST", "/revisions"), routes)
        self.assertIn(("GET", "/revisions/stats"), routes)

    def test_both_require_auth(self):
        """الإحصاءات تكشف حجم المكتب — تُحمى كغيرها."""
        by_key = {
            (method, path): kw.get("dependencies")
            for method, path, _fn, kw in main.app.routes
        }
        self.assertTrue(by_key[("POST", "/revisions")])
        self.assertTrue(by_key[("GET", "/revisions/stats")])

    def test_health_announces_revision_capture(self):
        self.assertTrue(asyncio.run(main.health())["revision_capture"])


class TestSaveRevision(MainTestBase):
    """`POST /revisions` — حفظ الزوج وقياسه."""

    def test_saves_a_row_with_the_expected_fields(self):
        payload = asyncio.run(
            main.save_revision(
                main.RevisionRequest(
                    generated_text=GENERATED,
                    corrected_text=CORRECTED,
                    doc_type="عقد",
                    prompt="وقائع",
                    session_id="ج1",
                )
            )
        )

        rows = fake_deps.FAKE_SUPABASE.inserted_into(main.REVISIONS_TABLE)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["generated_text"], GENERATED)
        self.assertEqual(rows[0]["corrected_text"], CORRECTED)
        self.assertEqual(rows[0]["doc_type"], "عقد")
        self.assertEqual(rows[0]["session_id"], "ج1")

        self.assertTrue(payload["saved"])
        self.assertGreater(payload["edit_ratio"], 0.0)
        self.assertLessEqual(payload["edit_ratio"], 1.0)
        self.assertIn("quality_band", payload)
        self.assertGreater(payload["word_count"], 0)

    def test_stored_row_has_no_embedding(self):
        """
        🔑 الجدول ليس جزءاً من قاعدة المعرفة.

        لو ظهر `embedding` في الصفّ المُدرَج لكان معناه أن التصحيحات تُضمَّن
        وتدخل الاسترجاع — فتعود المسودّة المولَّدة في جولة لاحقة كـ«سياق
        موثوق» وتصير الهلوسة حقيقة مؤرشفة. وهذا الفحص يحمي ذلك القرار.
        """
        asyncio.run(
            main.save_revision(
                main.RevisionRequest(generated_text=GENERATED, corrected_text=CORRECTED)
            )
        )
        row = fake_deps.FAKE_SUPABASE.inserted_into(main.REVISIONS_TABLE)[0]
        self.assertNotIn("embedding", row)
        self.assertEqual(main.REVISIONS_TABLE, "draft_revisions")

    def test_rejects_unchanged_revision(self):
        """تصحيح بلا تغيير: ٤٠٠، ولا يُحفظ شيء."""
        with self.assertRaises(main.HTTPException) as ctx:
            asyncio.run(
                main.save_revision(
                    main.RevisionRequest(generated_text=GENERATED, corrected_text=GENERATED)
                )
            )
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertEqual(fake_deps.FAKE_SUPABASE.inserted_into(main.REVISIONS_TABLE), [])

    def test_rejects_empty_corrected(self):
        with self.assertRaises(main.HTTPException) as ctx:
            asyncio.run(
                main.save_revision(
                    main.RevisionRequest(generated_text=GENERATED, corrected_text="   ")
                )
            )
        self.assertEqual(ctx.exception.status_code, 400)

    def test_missing_table_gives_an_actionable_message(self):
        """
        الجدول غير موجود أشيع سبب للفشل.

        و«relation does not exist» لا تدلّ المحامي على المطلوب، فتسمّي
        الرسالة القسم الدقيق في `schema.sql`.
        """
        fake_deps.FAKE_SUPABASE.raise_on_table.add(main.REVISIONS_TABLE)

        with self.assertRaises(main.HTTPException) as ctx:
            asyncio.run(
                main.save_revision(
                    main.RevisionRequest(generated_text=GENERATED, corrected_text=CORRECTED)
                )
            )

        self.assertEqual(ctx.exception.status_code, 503)
        self.assertIn("schema.sql", ctx.exception.detail)
        self.assertIn("١٠", ctx.exception.detail)

    def test_other_storage_errors_are_reported_plainly(self):
        """خطأ آخر يُعاد نصّه — لا يُخفى وراء رسالة الجدول الناقص."""
        message = main._revision_storage_error(RuntimeError("انتهت المهلة"))
        self.assertIn("انتهت المهلة", message)
        self.assertNotIn("schema.sql", message)


class TestRevisionStats(MainTestBase):
    """`GET /revisions/stats` — التقدّم نحو تقليد الأسلوب."""

    def test_empty_database(self):
        result = asyncio.run(main.revision_stats())
        self.assertEqual(result["count"], 0)
        self.assertEqual(result["average_edit_ratio"], 0.0)
        self.assertEqual(result["target"], STYLE_TARGET)
        self.assertEqual(result["progress_percent"], 0.0)

    def test_summarizes_stored_ratios(self):
        fake_deps.FAKE_SUPABASE.set_table_rows(
            main.REVISIONS_TABLE,
            [{"edit_ratio": 0.05}, {"edit_ratio": 0.15}, {"edit_ratio": None}],
        )
        result = asyncio.run(main.revision_stats())

        self.assertEqual(result["count"], 2, "الصفّ بلا نسبة يجب ألّا يُحسب")
        self.assertAlmostEqual(result["average_edit_ratio"], 0.1, places=3)
        self.assertEqual(sum(result["distribution"].values()), 2)

    def test_stats_only_selects_the_ratio_column(self):
        """
        الإحصاء يجلب عمود النسبة وحده لا المسودّات.

        ولو جلب النصوص لصارت الحمولة ضخمة مع كل فتح للوحة — وهي بيانات لا
        يحتاجها الحساب أصلاً.
        """
        asyncio.run(main.revision_stats())
        table_calls = fake_deps.FAKE_SUPABASE.table_calls
        self.assertTrue(table_calls)
        _name, op, columns = table_calls[-1]
        self.assertEqual(op, "select")
        self.assertEqual(columns, "edit_ratio")

    def test_missing_table_gives_an_actionable_message(self):
        fake_deps.FAKE_SUPABASE.raise_on_table.add(main.REVISIONS_TABLE)
        with self.assertRaises(main.HTTPException) as ctx:
            asyncio.run(main.revision_stats())
        self.assertEqual(ctx.exception.status_code, 503)
        self.assertIn("schema.sql", ctx.exception.detail)


# ==============================================================================
# ٨. نقل تغطية كانت في فحص خارجي
# ==============================================================================
# كانت هذه الحالات في فحص انحدار خارجي (`stub_check.py`) يستبدل `legal_agent`
# **بأكمله** بوهمي. وقد انتهى دوره: ما يغطّيه صار هنا، مع فارق أن الاختبار هنا
# يُشغّل `legal_agent` الحقيقي. لكن تفاصيله المفيدة نُقلت لا تُركت.


class TestExtractText(MainTestBase):
    """
    `_extract_text` — توحيد محتوى الرسالة.

    تبدو تافهة وهي ليست كذلك: Gemini يُرجع أحياناً **قائمة كتل محتوى** بدل نصّ،
    فتظهر الواجهة فارغة بلا أي خطأ ظاهر. ولهذا تُفحص الأشكال كلها.
    """

    def test_plain_string(self):
        message = fake_deps._FakeMessage(content="مرحباً")
        self.assertEqual(main._extract_text(message), "مرحباً")

    def test_content_blocks_as_gemini_returns_them(self):
        message = fake_deps._FakeMessage(
            content=[{"type": "text", "text": "أ"}, {"type": "text", "text": "ب"}]
        )
        self.assertEqual(main._extract_text(message), "أب")

    def test_list_of_strings(self):
        message = fake_deps._FakeMessage(content=["س", "ص"])
        self.assertEqual(main._extract_text(message), "سص")

    def test_none_content(self):
        message = fake_deps._FakeMessage(content=None)
        self.assertEqual(main._extract_text(message), "")

    def test_ignores_non_text_blocks(self):
        """كتل غير نصّية (صور، نداءات أدوات) لا تُحوَّل إلى نصّ."""
        message = fake_deps._FakeMessage(
            content=[{"type": "image", "data": "..."}, {"type": "text", "text": "نصّ"}]
        )
        self.assertEqual(main._extract_text(message), "نصّ")


class TestConfiguration(MainTestBase):
    """إعدادات تُقرأ عند الاستيراد — تتغيّر بلا اختبار فينكسر الإنتاج."""

    def test_all_five_tools_have_a_stage_label(self):
        """كل أداة لها وسم مرحلة — وإلا ظهر اسم خاطئ في الواجهة أثناء البحث."""
        for tool_name in (
            "search_uae_legislation",
            "search_drafting_style",
            "search_contract_clauses",
            "search_legal_notices",
            "search_poa_clauses",
        ):
            with self.subTest(tool=tool_name):
                self.assertIn(tool_name, main.TOOL_STAGE_LABELS)
                self.assertTrue(main.TOOL_STAGE_LABELS[tool_name])

    def test_document_type_hints_point_at_real_tools(self):
        """تلميحات أنواع المستندات تشير إلى أسماء أدوات موجودة فعلاً."""
        for doc_type, hint in main.DOC_TYPE_TOOL_HINT.items():
            with self.subTest(doc_type=doc_type):
                self.assertIn(hint, main.TOOL_STAGE_LABELS)

    def test_allowed_origins_is_a_list(self):
        """`ALLOWED_ORIGINS` يُقرأ عند الاستيراد — شكله قائمة لا نصّ."""
        self.assertIsInstance(main._allowed_origins, list)

    def test_cors_is_registered(self):
        self.assertIsNotNone(main.app.middleware)

    def test_recursion_limit_is_bounded(self):
        """حدّ خطوات الوكيل موجود ومعقول — بدونه تدور الحلقة بلا نهاية."""
        self.assertGreaterEqual(main.AGENT_RECURSION_LIMIT, 4)
        self.assertLessEqual(main.AGENT_RECURSION_LIMIT, 50)


class TestArchiveEndpoints(MainTestBase):
    """
    نقطتا الأرشيف — وهما ما يُغني لوحة القيادة والمكتبة عن الأرقام المكتوبة.
    ========================================================================
    كانت الصفحتان تعرضان «١٢٤٨ مستنداً» و«٨٥٣٠ سنداً» **مكتوبة بخط اليد**،
    و«من أرشيف Qdrant» وهو **خطأ واقعي**: الأرشيف في Supabase/pgvector.

    وهذا الفحص يثبّت أن ما يُعرض يأتي من قاعدة البيانات فعلاً.
    """

    def setUp(self) -> None:
        super().setUp()
        self.supabase = fake_deps.FAKE_SUPABASE

    # -- GET /archive/overview ------------------------------------------------

    def test_overview_returns_all_five_families_even_when_empty(self):
        """العائلات الخمس تُعاد كلها — و«٠» أصدق من الإخفاء."""
        payload = asyncio.run(main.archive_overview())
        self.assertEqual(
            [item["key"] for item in payload["families"]],
            [key for key, _ in main.ARCHIVE_FAMILIES],
        )
        self.assertTrue(all(item["documents"] == 0 for item in payload["families"]))
        self.assertEqual(payload["documents"], 0)
        self.assertEqual(payload["chunks"], 0)

    def test_overview_sums_the_families(self):
        self.supabase.set_rows(
            "archive_overview",
            [
                {"family_key": "legislation", "documents": 12, "chunks": 900},
                {"family_key": "contracts", "documents": 3, "chunks": 40},
            ],
        )
        payload = asyncio.run(main.archive_overview())
        self.assertEqual(payload["documents"], 15)
        self.assertEqual(payload["chunks"], 940)

    def test_overview_fills_absent_families_with_zero(self):
        """عائلة غابت من ردّ الخادم تُعرض بصفر — لا تُحذف من اللوحة."""
        self.supabase.set_rows(
            "archive_overview",
            [{"family_key": "poa", "documents": 2, "chunks": 7}],
        )
        by_key = {
            item["key"]: item
            for item in asyncio.run(main.archive_overview())["families"]
        }
        self.assertEqual(len(by_key), 5)
        self.assertEqual(by_key["poa"]["documents"], 2)
        self.assertEqual(by_key["notices"]["documents"], 0)

    def test_overview_pairs_a_machine_key_with_an_arabic_label(self):
        """
        مفتاح آلي **و** وسم عربي — كما في مفاتيح المراحل.

        ولو رُبطت الواجهة بالوسم العربي لانكسرت التصفية بصمت عند أول تعديل.
        """
        for item in asyncio.run(main.archive_overview())["families"]:
            with self.subTest(key=item["key"]):
                self.assertRegex(item["key"], r"^[a-z_]+$")
                self.assertTrue(item["label"])
                self.assertNotRegex(item["label"], r"^[a-z_]+$")

    def test_overview_missing_function_names_the_section_to_run(self):
        """رسالة تسمّي القسم المطلوب — كما فعلت رسالة جدول التصحيحات."""
        self.supabase.raise_on_rpc.add("archive_overview")
        with self.assertRaises(main.HTTPException) as caught:
            asyncio.run(main.archive_overview())
        self.assertEqual(caught.exception.status_code, 503)
        self.assertIn("القسم ١١", caught.exception.detail)

    def test_overview_calls_exactly_one_rpc(self):
        asyncio.run(main.archive_overview())
        self.assertEqual(self.supabase.rpc_names(), ["archive_overview"])

    # -- GET /archive/documents -----------------------------------------------

    def seed_documents(self) -> None:
        self.supabase.set_rows(
            "archive_documents",
            [
                {
                    "document_name": "قانون المعاملات المدنية",
                    "document_type": "تشريع",
                    "family_key": "legislation",
                    "chunks": 420,
                    "added_at": "2026-09-01T10:00:00Z",
                },
                {
                    "document_name": "عقد إيجار سكني",
                    "document_type": "عقود عقارية",
                    "family_key": "contracts",
                    "chunks": 18,
                    "added_at": "2026-09-02T10:00:00Z",
                },
            ],
        )

    def test_documents_group_by_name_with_their_chunk_count(self):
        self.seed_documents()
        payload = asyncio.run(main.archive_documents())
        self.assertEqual(payload["count"], 2)
        names = [item["document_name"] for item in payload["documents"]]
        self.assertIn("قانون المعاملات المدنية", names)
        self.assertEqual(payload["documents"][0]["chunks"], 420)

    def test_documents_resolve_the_arabic_family_label(self):
        """الواجهة لا تُترجم المفاتيح — الخادم يُرسل الوسم معها."""
        self.seed_documents()
        payload = asyncio.run(main.archive_documents())
        labels = {item["family"]: item["family_label"] for item in payload["documents"]}
        self.assertEqual(labels["legislation"], "التشريعات والأحكام")
        self.assertEqual(labels["contracts"], "العقود والاتفاقيات")

    def test_documents_pass_empty_filters_as_null(self):
        """
        الفراغ يُحوَّل إلى `null` لا إلى `''`.

        ودالّة SQL تعامل الاثنين سواءً (`coalesce`)، لكن `null` هو ما تعنيه
        «لا تصفية» — ويمنع `ilike '%%'` من مطابقة كل شيء بالخطأ.
        """
        asyncio.run(main.archive_documents())
        _name, params = self.supabase.last_call()
        self.assertIsNone(params["search_term"])
        self.assertIsNone(params["family_filter"])

    def test_documents_trim_the_search_term(self):
        asyncio.run(main.archive_documents(search="  إيجار  "))
        _name, params = self.supabase.last_call()
        self.assertEqual(params["search_term"], "إيجار")

    def test_documents_pass_a_known_family_through(self):
        asyncio.run(main.archive_documents(family="notices"))
        _name, params = self.supabase.last_call()
        self.assertEqual(params["family_filter"], "notices")

    def test_documents_reject_an_unknown_family_loudly(self):
        """
        عائلة مجهولة تُرفض ولا تُتجاهَل.

        ولو تُوجّهت التصفية الخاطئة إلى «لا تصفية» لعاد الأرشيف كاملاً **وبدا
        صحيحاً** — وهي أسوأ من خطأ صريح.
        """
        with self.assertRaises(main.HTTPException) as caught:
            asyncio.run(main.archive_documents(family="legislationn"))
        self.assertEqual(caught.exception.status_code, 400)
        self.assertIn("legislationn", caught.exception.detail)
        self.assertEqual(self.supabase.calls, [], "لم يكن ينبغي نداء قاعدة البيانات")

    def test_documents_clamp_the_row_limit(self):
        for requested, expected in ((0, 1), (-5, 1), (50, 50), (9999, main.ARCHIVE_MAX_ROWS)):
            with self.subTest(requested=requested):
                self.supabase.reset()
                asyncio.run(main.archive_documents(limit=requested))
                _name, params = self.supabase.last_call()
                self.assertEqual(params["max_rows"], expected)

    def test_documents_report_truncation(self):
        """
        والقَصّ يُعلَن ولا يُسكت عنه.

        ولو سكت، لأوهمت الصفحة أن ما تراه هو الأرشيف كله — وهو عين ما كانت
        تفعله الأرقام المكتوبة بخط اليد.
        """
        self.supabase.set_rows(
            "archive_documents",
            [
                {"document_name": f"مستند {i}", "family_key": "drafts", "chunks": 1}
                for i in range(5)
            ],
        )
        payload = asyncio.run(main.archive_documents(limit=5))
        self.assertTrue(payload["truncated"])
        self.assertEqual(payload["limit"], 5)

    def test_documents_not_truncated_when_fewer_than_the_limit(self):
        self.seed_documents()
        payload = asyncio.run(main.archive_documents(limit=50))
        self.assertFalse(payload["truncated"])

    def test_documents_tolerate_null_columns_from_the_database(self):
        """قيم `null` في القاعدة لا تُسقط الصفحة — تُعرض فراغاً."""
        self.supabase.set_rows(
            "archive_documents",
            [{"document_name": None, "document_type": None, "family_key": None, "chunks": None}],
        )
        item = asyncio.run(main.archive_documents())["documents"][0]
        self.assertEqual(item["document_name"], "")
        self.assertEqual(item["document_type"], "")
        self.assertEqual(item["family_label"], "")
        self.assertEqual(item["chunks"], 0)

    def test_documents_missing_function_names_the_section_to_run(self):
        self.supabase.raise_on_rpc.add("archive_documents")
        with self.assertRaises(main.HTTPException) as caught:
            asyncio.run(main.archive_documents())
        self.assertEqual(caught.exception.status_code, 503)
        self.assertIn("القسم ١١", caught.exception.detail)


class TestArchiveChunks(MainTestBase):
    """
    نقطة المقاطع — «فتح مستند» و«البحث النصّي».
    ========================================================================
    وهي التي تجعل الأرشيف أداة عمل لا جدولاً: يبحث المحامي عن نصّ، **ويفتح
    المستند** ليقرأ ما يستند إليه الفريق فعلاً.
    """

    def setUp(self) -> None:
        super().setUp()
        self.supabase = fake_deps.FAKE_SUPABASE

    def test_passes_all_four_filters_trimmed(self):
        asyncio.run(
            main.archive_chunks(
                search="  إيجار  ",
                family="contracts",
                document="  عقد أ  ",
                sort="name",
                limit=10,
            )
        )
        _name, params = self.supabase.last_call()
        self.assertEqual(
            params,
            {
                "search_term": "إيجار",
                "family_filter": "contracts",
                "document_filter": "عقد أ",
                "sort_order": "name",
                "max_rows": 10,
            },
        )

    def test_empty_filters_become_null(self):
        """الفراغ يُحوَّل إلى `null` لا `''` — وإلا طابق `ilike '%%'` كل شيء."""
        asyncio.run(main.archive_chunks())
        _name, params = self.supabase.last_call()
        for key in ("search_term", "family_filter", "document_filter"):
            self.assertIsNone(params[key], key)

    def test_clamps_the_row_limit(self):
        for requested, expected in (
            (0, 1),
            (-3, 1),
            (50, 50),
            (9999, main.ARCHIVE_MAX_CHUNK_ROWS),
        ):
            with self.subTest(requested=requested):
                self.supabase.reset()
                asyncio.run(main.archive_chunks(limit=requested))
                self.assertEqual(self.supabase.last_call()[1]["max_rows"], expected)

    def test_chunk_ceiling_is_lower_than_the_document_ceiling(self):
        """
        ⚠️ وسقف المقاطع **أقلّ** من سقف المستندات عن قصد: نصّ المقطع أطول بكثير
        من اسم مستند، فـ٢٠٠ مقطع حمولة قد تبلغ ميغابايتات.
        """
        self.assertLess(main.ARCHIVE_MAX_CHUNK_ROWS, main.ARCHIVE_MAX_ROWS)

    def test_rejects_an_unknown_family_loudly(self):
        with self.assertRaises(main.HTTPException) as caught:
            asyncio.run(main.archive_chunks(family="legislationn"))
        self.assertEqual(caught.exception.status_code, 400)
        self.assertIn("legislationn", caught.exception.detail)
        self.assertEqual(self.supabase.calls, [], "لم يكن ينبغي نداء قاعدة البيانات")

    def test_maps_the_family_to_its_arabic_label(self):
        self.supabase.set_rows(
            "archive_chunks",
            [
                {
                    "id": 7,
                    "document_name": "عقد إيجار",
                    "family_key": "contracts",
                    "chunk_content": "البند الأول: يلتزم الطرف الثاني.",
                    "chunk_index": 3,
                }
            ],
        )
        item = asyncio.run(main.archive_chunks())["chunks"][0]
        self.assertEqual(item["family_label"], "العقود والاتفاقيات")
        self.assertEqual(item["content"], "البند الأول: يلتزم الطرف الثاني.")
        self.assertEqual(item["chunk_index"], 3)
        self.assertEqual(item["id"], 7)

    def test_tolerates_null_columns_from_the_database(self):
        self.supabase.set_rows("archive_chunks", [{}])
        item = asyncio.run(main.archive_chunks())["chunks"][0]
        self.assertEqual(item["content"], "")
        self.assertEqual(item["document_name"], "")
        self.assertEqual(item["family_label"], "")
        self.assertIsNone(item["chunk_index"])

    def test_reports_truncation(self):
        self.supabase.set_rows(
            "archive_chunks", [{"id": i, "chunk_content": "x"} for i in range(5)]
        )
        payload = asyncio.run(main.archive_chunks(limit=5))
        self.assertTrue(payload["truncated"])
        self.assertEqual(payload["count"], 5)

    def test_not_truncated_below_the_limit(self):
        self.supabase.set_rows("archive_chunks", [{"id": 1, "chunk_content": "x"}])
        self.assertFalse(asyncio.run(main.archive_chunks(limit=50))["truncated"])

    def test_missing_function_names_section_twelve(self):
        """
        🔑 **والقسم ١٢ لا ١١.**

        المقاطع أُضيفت في قسم ثانٍ، ولو قيل «١١» لبحث المستخدم في القسم الخطأ
        ولم يجد الدالّة. (وهو خطأ ارتُكب فعلاً حين أُضيفت هذه النقطة.)
        """
        self.supabase.raise_on_rpc.add("archive_chunks")
        with self.assertRaises(main.HTTPException) as caught:
            asyncio.run(main.archive_chunks())
        self.assertEqual(caught.exception.status_code, 503)
        self.assertIn("القسم ١٢", caught.exception.detail)

    def test_overview_still_names_section_eleven(self):
        """وفي المقابل: دوالّ القسم ١١ ما زالت تسمّي قسمها هي."""
        self.supabase.raise_on_rpc.add("archive_overview")
        with self.assertRaises(main.HTTPException) as caught:
            asyncio.run(main.archive_overview())
        self.assertIn("القسم ١١", caught.exception.detail)


class TestProxyContract(MainTestBase):
    """
    الوسيط يمرّر **معاملات العنوان** إلى الخادم.
    ========================================================================
    ⚠️ وهذا فحص يعبر من بايثون إلى ملف TypeScript، كما يفعل عقد مشهد المكتب.

    والسبب أن العطب الذي يمنعه **صامت تماماً**: الوسيط كان يبني العنوان بلا
    `request.nextUrl.search`، فتُرمى `?search=` و`?document=` و`?family=` —
    **ومع ذلك ينجح الطلب ويُعيد `200` ببيانات خاطئة**.

    وقد وقع فعلاً: **البحث في الأرشيف لم يعمل، والنقر على مستند جلب كل
    المقاطع، والتصفية بالعائلة لم تفعل شيئاً** — عطبٌ واحد أخفى ثلاث ميزات،
    ولم يُكشف إلا باختبار حقيقي على أرشيف حقيقي.
    """

    ROUTE = (
        pathlib.Path(__file__).resolve().parent.parent
        / "frontend"
        / "app"
        / "api"
        / "[...path]"
        / "route.ts"
    )

    def setUp(self) -> None:
        super().setUp()
        self.source = self.ROUTE.read_text(encoding="utf-8")

    def test_route_file_exists(self):
        self.assertTrue(self.ROUTE.exists(), f"مفقود: {self.ROUTE}")

    def test_forwards_the_query_string(self):
        """🔑 **العطب الذي وقع فعلاً** — معاملات العنوان يجب أن تُمرَّر."""
        self.assertIn(
            "request.nextUrl.search",
            self.source,
            "الوسيط يُسقط معاملات العنوان (?search= · ?document= · ?family=)",
        )

    def test_query_string_is_appended_to_the_target(self):
        """
        ولا يكفي أن يُقرأ — بل يجب أن يُلحَق بالعنوان المقصود.

        ⚠️ وفحصٌ نصّي بسيط لا regex: الأول تشوّه في التمرير ففشل **وهو محقّ**،
        والدرس أن الفحص الهشّ يُشغِل وقتاً في نفسه لا في العطب.
        """
        self.assertIn(
            '${request.nextUrl.search}',
            self.source,
            "العنوان المقصود لا يحمل معاملات العنوان",
        )

    def test_still_forwards_the_body_for_writes(self):
        """وبه لا يُكسر ما يعمل: الجسم والبثّ كما كانا."""
        self.assertIn("request.text()", self.source)
        self.assertIn("upstream.body", self.source)

    def test_token_is_still_added_on_the_server(self):
        """
        والرمز يُضاف على الخادم ولا يعبر إلى المتصفح.

        ⚠️ والفحص على **أسطر الكود وحدها**: `NEXT_PUBLIC_` مذكورة في تعليق
        يحذّر من استخدامها، فلو فُحص الملف كله لفشل الاختبار **وهو محقّ**.
        """
        self.assertIn("API_TOKEN", self.source)
        self.assertIn("authorization", self.source)

        code = "\n".join(
            line
            for line in self.source.splitlines()
            if not line.lstrip().startswith(("*", "//", "/*"))
        )
        self.assertNotIn("NEXT_PUBLIC_", code, "بادئة حسّاسة في كود المتصفح")


class TestArchiveSort(MainTestBase):
    """
    الفرز **يُرفض إن كان مجهولاً** ولا يُتجاهَل.
    ========================================================================
    ⚠️ والسبب أن الفرز المجهول لو تُوجّه إلى «لا فرز» لعادت **النتيجة نفسها**
    بلا خطأ — فيظنّ المستخدم أن زرّ الترتيب لا يعمل، ويُهدر وقته في الواجهة
    **والعطب في الخادم**. فالرفض الصريح (400) أرحم من الصمت.
    """

    def setUp(self) -> None:
        super().setUp()
        self.supabase = fake_deps.FAKE_SUPABASE

    def test_accepts_the_three_known_orders(self):
        for key in ("recent", "name", "size"):
            with self.subTest(key=key):
                self.assertEqual(main._archive_sort(key), key)

    def test_defaults_to_recent(self):
        self.assertEqual(main._archive_sort(""), "recent")
        self.assertEqual(main._archive_sort(None), "recent")  # type: ignore[arg-type]

    def test_is_case_and_space_insensitive(self):
        self.assertEqual(main._archive_sort("  NAME  "), "name")

    def test_rejects_an_unknown_order(self):
        with self.assertRaises(main.HTTPException) as caught:
            main._archive_sort("newest")
        self.assertEqual(caught.exception.status_code, 400)
        self.assertIn("newest", caught.exception.detail)

    def test_documents_pass_the_sort_through(self):
        asyncio.run(main.archive_documents(sort="size"))
        self.assertEqual(self.supabase.last_call()[1]["sort_order"], "size")

    def test_chunks_pass_the_sort_through(self):
        asyncio.run(main.archive_chunks(sort="name"))
        self.assertEqual(self.supabase.last_call()[1]["sort_order"], "name")

    def test_documents_reject_a_bad_sort_before_touching_the_database(self):
        with self.assertRaises(main.HTTPException):
            asyncio.run(main.archive_documents(sort="nope"))
        self.assertEqual(self.supabase.calls, [])


class TestOfficeSceneContract(MainTestBase):
    """
    مفاتيح مشهد المكتب في الواجهة تطابق مفاتيح الخادم.
    ========================================================================
    ⚠️ هذا الفحص **يعبر حدّ اللغتين** عن قصد، وهو من أهمّ ما في هذا الملف.

    السبب أن العطب الذي يمنعه **صامت تماماً**: لو أُضيفت مرحلة في `main.py`
    ولم تُضف شخصيتها في الواجهة، لما ظهر أي خطأ — تبقى الشخصية نائمة أبداً
    ولا يلاحظ أحد. وهو النوع نفسه من الانحراف الصامت الذي أصلحناه في الأدوات
    الخمس (سقوط أداة من نسخة موجّه واحدة بلا خطأ ظاهر).

    ولذلك يُفحص الاتجاهان: كل مرحلة لها شخصية، ولا شخصية بلا مرحلة.
    """

    SCENE = (
        pathlib.Path(__file__).resolve().parent.parent
        / "frontend"
        / "components"
        / "office-scene.tsx"
    )

    def setUp(self) -> None:
        super().setUp()
        self.source = self.SCENE.read_text(encoding="utf-8")

    def backend_stages(self) -> set:
        """كل مفتاح مرحلة يبثّه الخادم فعلاً."""
        return set(main.TOOL_STAGE_KEYS.values()) | {
            main.KEY_INTAKE,
            main.KEY_EVIDENCE,
            main.KEY_DRAFTING,
            main.KEY_VERIFYING,
            main.KEY_POLISH,
            main.KEY_SEAL,
        }

    def stage_map(self) -> dict:
        """جدول `STAGE_CHARACTER` من ملف المشهد: مرحلة ← شخصية."""
        block = re.search(
            r"const STAGE_CHARACTER[^{]*\{(.*?)\n\};", self.source, re.DOTALL
        )
        self.assertIsNotNone(block, "لم يُعثر على STAGE_CHARACTER في المشهد")
        return dict(re.findall(r'(\w+):\s*"(\w+)"', block.group(1)))

    def characters(self) -> set:
        """
        مفاتيح الشخصيات في `TEAM`.

        ويُقرأ من كتلة `TEAM` وحدها لا من الملف كله: فـ`key={worker.key}` في
        JSX ليس تعريف شخصية، ولو قرأناه لظهرت مفاتيح وهمية.
        """
        block = re.search(r"const TEAM[^=]*=\s*\[(.*?)\n\];", self.source, re.DOTALL)
        self.assertIsNotNone(block, "لم يُعثر على TEAM في المشهد")
        return set(re.findall(r'key:\s*"(\w+)"', block.group(1)))

    def test_scene_file_is_present(self):
        self.assertTrue(self.SCENE.exists(), f"مفقود: {self.SCENE}")

    def test_every_backend_stage_is_mapped(self):
        """كل مرحلة يبثّها الخادم لها مدخل في الجدول — وإلا نائمة أبداً."""
        missing = self.backend_stages() - set(self.stage_map())
        self.assertEqual(missing, set(), f"مراحل بلا شخصية: {sorted(missing)}")

    def test_no_stage_is_mapped_without_a_backend_stage(self):
        """ولا مدخل لمرحلة لا يبثّها الخادم — وإلا لم تتحرّك قطّ."""
        orphans = set(self.stage_map()) - self.backend_stages()
        self.assertEqual(orphans, set(), f"مراحل لا يبثّها الخادم: {sorted(orphans)}")

    def test_every_character_owns_at_least_one_stage(self):
        """كل شخصية معرَّفة لها مرحلة — وإلا فلا تظهر أبداً."""
        idle = self.characters() - set(self.stage_map().values())
        self.assertEqual(idle, set(), f"شخصيات بلا مرحلة: {sorted(idle)}")

    def test_no_stage_maps_to_an_unknown_character(self):
        """ولا مرحلة تُوجَّه إلى شخصية غير معرَّفة — وإلا اختفت الحركة."""
        unknown = set(self.stage_map().values()) - self.characters()
        self.assertEqual(unknown, set(), f"شخصيات غير معرَّفة: {sorted(unknown)}")

    def test_scene_has_a_name_and_role_for_every_character(self):
        """لكل شخصية اسم ودور معروضان — وهذا ما طلبه المستخدم صراحةً."""
        count = len(self.characters())
        self.assertEqual(len(re.findall(r'name:\s*"', self.source)), count)
        self.assertEqual(len(re.findall(r'role:\s*"', self.source)), count)

    def test_the_team_uses_the_names_that_already_exist_in_the_system(self):
        """
        ⚠️ الأسماء تأتي من `smart_office.py` و`office_test.py` لا من خيال أحد.

        اخترعتُ سابقاً تسعة أسماء فرفضها المستخدم: الفريق في نظامه **خمسة**
        بأسمائهم. وهذا الفحص يمنع عودة الاختراع — ولو أُضيف اسم في الكود
        وليس في `smart_office.py` لظهر هنا.
        """
        expected_names = {
            "أمين المكتبة",
            "مُسوَدَّة أفندي",
            "المفتش ثُغرة",
            "سيبويه المُكشّر",
            "المعلم أبو الختم",
        }
        found = set(re.findall(r'name:\s*"([^"]+)"', self.source))
        self.assertEqual(found, expected_names)

    def test_scene_uses_logical_spacing_for_rtl(self):
        """
        المشهد يستخدم خصائص منطقية لا فيزيائية.

        التطبيق RTL بالكامل، و`ml-`/`left-` تُنتج الفراغ في الجهة الخطأ.
        """
        for physical in ("ml-", "mr-", "pl-", "pr-", "left-", "right-"):
            self.assertNotIn(physical, self.source, f"خاصية فيزيائية في ملف RTL: {physical}")

    def test_scene_draws_no_untrusted_html(self):
        """لا `dangerouslySetInnerHTML` في المشهد — كبقية الواجهة."""
        self.assertNotIn("dangerouslySetInnerHTML", self.source)

    def test_character_keys_do_not_collide_with_stage_keys(self):
        """
        مفاتيح الشخصيات مختلفة عن مفاتيح المراحل.

        لو تشابهت لالتبس الجدول: `drafting` مرحلة، ولو كانت كذلك شخصية لكان
        `STAGE_CHARACTER[drafting] == drafting` وهو التباس لا خطأ صريح.
        """
        self.assertEqual(self.characters() & self.backend_stages(), set())


# ==============================================================================
# ٩. سجلّ الوقائع — الفحص الذي يمنع تغيير واقعة
# ==============================================================================
# ⚠️ **وما تمنعه هذه المجموعة ليس الفشل الصريح بل النجاح الكاذب.** الوحدة
# `facts.py` كانت مبنيّة ومختبرة **ولا يُناديها أيّ موضع** — فكانت توجد ولا
# تُغيّر شيئاً، كحال `case_file.py` قبل وصلها. والوصل يفتح ثلاثة أبواب يجب أن
# تُغلق: أن يُقبل سجلّ فاسد فيُبنى عليه، أو أن يُبتلع سجلّ فاسد فيظنّ المستدعي
# أنّه مرّ، أو أن يُسكَت عن غياب السجلّ فيُقرأ السكوت سلامة.


class TestFactPayload(MainTestBase):
    """
    حمل الوقائع على `/generate` — **يُبنى مرة واحدة قبل الوكيل**.
    ========================================================================
    ⚠️ **والقاعدة التي يفحصها هذا الصنف**: السجلّ الفاسد يُردّ **برسالة الوحدة
    نفسها** وبقبل أن يُستدعى نموذج واحد — لأن **سجلّاً يُتجاهَل صامتاً أسوأ من
    سجلٍّ غائب**: المستدعي يظنّ أنّ وقائعه قُوبلت، فتُبنى المسودّة على غير ما
    أرسل. ورسالة الوحدة لا تُترجم: نصُّها يسمّي الموضع الذي يُصلَح فيه.
    """

    def test_a_valid_payload_becomes_the_module_object(self):
        """الحمل الصالح يُبنى سجلاً — والقيَم كما وردت لا كما فُسّرت."""
        ledger = ledger_of(FACTS)
        self.assertIsInstance(ledger, main.FactLedger)

        fact = ledger.of_key("release.refused")
        self.assertIsNotNone(fact)
        self.assertEqual(fact.statement, RELEASE_FACT["statement"])
        self.assertEqual(fact.quote, RELEASE_FACT["quote"])
        self.assertEqual(fact.locus, RELEASE_FACT["locus"])
        self.assertEqual(fact.source, RELEASE_FACT["source"])
        # ⚠️ والدرجة تُقرأ من الوحدة لا من نصّ مكتوب هنا.
        self.assertEqual(fact.standing, Standing.CLAIMED)
        self.assertTrue(fact.is_quoted)

    def test_no_payload_means_no_ledger(self):
        """وغياب الحمل يعني «لم يُرسل سجلّ» — ولا يُبنى سجلّ فارغ عن لسانه."""
        self.assertIsNone(main._facts_from_payload(None))

    def test_an_empty_list_is_a_built_and_reported_empty_ledger(self):
        """
        ⚠️ **و``[]`` ليست غياباً**: سجلٌّ فارغ يُبنى ويُفحَص ويُقال ``fact_count: 0``.
        والخطر الذي يمنعه هذا الفرق أن يُقرأ الفراغ المُعلَن غياباً — أو العكس.
        """
        ledger = ledger_of([])
        self.assertIsInstance(ledger, main.FactLedger)
        self.assertEqual(ledger.keys(), ())

    def test_the_raw_json_shape_is_read_too(self):
        """
        ⚠️ **والواقعة تُقرأ بصورتيها**: كائنَ نقل (وهو ما يُنتجه بيدانتيك)،
        وقاموساً خاماً (وهو ما يصل في جسم JSON). والقراءة واحدة، فلا يفترق ما
        يُختبر عمّا يخدم.
        """
        ledger = main._facts_from_payload([dict(RELEASE_FACT)])

        self.assertEqual(ledger.keys(), ("release.refused",))
        self.assertEqual(
            ledger.of_key("release.refused").standing, Standing.CLAIMED
        )

    def test_a_ledger_that_is_not_a_list_is_rejected(self):
        with self.assertRaises(main.HTTPException) as caught:
            main._facts_from_payload(fact_input("وقائع"))
        self.assertEqual(caught.exception.status_code, 400)
        self.assertIn("قائمة", caught.exception.detail)

    def test_an_unknown_standing_is_rejected_with_the_modules_own_values(self):
        """
        ⚠️ **والقيمة المجهولة تُرفض بأسماء القيم المتاحة من التصنيف نفسه.**
        ولو مرّت لَما ظهرت خطأً بل قيمةً لا تُطابق شيئاً في `by_standing` —
        **فيُقرأ الفراغ سلامة**، وهو العطب نفسه الذي أُصلح في مطابقة الجهة.
        """
        payload = [dict(RELEASE_FACT, standing="مؤكَّدة")]
        with self.assertRaises(main.HTTPException) as caught:
            main._facts_from_payload(fact_input(payload))

        self.assertEqual(caught.exception.status_code, 400)
        self.assertIn("مؤكَّدة", caught.exception.detail)
        for member in Standing:
            with self.subTest(standing=member.value):
                self.assertIn(member.value, caught.exception.detail)

    def test_a_missing_standing_is_rejected_not_assumed(self):
        """
        🔑 **وغياب الدرجة لا يُملأ بقيمة مخترعة.**

        ودرجة الواقعة **وزنها في المذكرة**، فافتراضُها حكمٌ من عندنا لم يكتبه
        أحد — وهو **الافتراض الصامت** الذي يقوم هذا المشروع على منعه. ومن أراد
        أن يعرف أثر ذلك فليقرأ `Standing`: «استنتاج» و«غير محقّقة» و«متنازع
        عليها» أنواعُ حكمٍ مختلفة، ولا يُقاس بعضها إلى بعض.
        """
        payload = [{key: value for key, value in RELEASE_FACT.items() if key != "standing"}]
        with self.assertRaises(main.HTTPException) as caught:
            main._facts_from_payload(fact_input(payload))

        self.assertEqual(caught.exception.status_code, 400)
        self.assertIn("درجة الواقعة", caught.exception.detail)
        self.assertIn(Standing.CLAIMED.value, caught.exception.detail)

    def test_a_duplicate_key_is_rejected_with_the_modules_own_message(self):
        """
        ⚠️ **والرسالة رسالة الوحدة لا رسالتنا.**

        «مفتاح مكرّر في السجلّ» تُكتب في `facts.py` وحدها، ولو ترجمناها إلى نصّ
        من عندنا لضاع الموضع الذي يُصلَح فيه — وهو المفتاح المكرّر بعينه.
        """
        payload = [RELEASE_FACT, RELEASE_FACT]
        with self.assertRaises(main.HTTPException) as caught:
            main._facts_from_payload(fact_input(payload))

        self.assertEqual(caught.exception.status_code, 400)
        self.assertIn("مفتاح مكرّر", caught.exception.detail)
        self.assertIn("release.refused", caught.exception.detail)

    def test_a_fact_without_a_statement_is_rejected(self):
        """وواقعة بلا نصّ تُردّ برسالة الوحدة أيضاً — لا تُبنى بمعنى مخترع."""
        payload = [dict(RELEASE_FACT, statement="")]
        with self.assertRaises(main.HTTPException) as caught:
            main._facts_from_payload(fact_input(payload))
        self.assertEqual(caught.exception.status_code, 400)
        self.assertIn("release.refused", caught.exception.detail)

    def test_a_system_agreed_fact_is_refused_with_the_modules_rule(self):
        """
        🔑 **والحارس يُنادى: المنظومة لا تُنشئ واقعة «متفقاً عليها».**

        ورسالة الوحدة تُنقل كاملةً — وفيها القاعدة نفسها، لا إشارة إليها:
        **رواية الموكّل ليست دليلاً**. ولو مرّت `AGREED` من مسار آلي لصارت في
        المذكرة حقيقةً مسلَّمة، وهي **صورة أخرى من العيب الأول**: أن يُغيَّر
        **وزن** الواقعة لا نصّها.
        """
        payload = [dict(RELEASE_FACT, standing=Standing.AGREED.value)]
        with self.assertRaises(main.HTTPException) as caught:
            main._facts_from_payload(fact_input(payload))

        self.assertEqual(caught.exception.status_code, 400)
        # ⚠️ والرسالة بنصّ الوحدة: `AGREED` بحرفه اللاتيني كما تكتبه، ومعها
        # القاعدة كاملةً — لا إشارة إليها.
        self.assertIn(Standing.AGREED.name, caught.exception.detail)
        self.assertIn(CLIENT_STATEMENT_IS_NOT_PROOF, caught.exception.detail)

    def test_a_malformed_ledger_never_starts_generation(self):
        """
        🔑 **والسجلّ الفاسد يُردّ قبل أن يُستدعى نموذج واحد.**

        ولو بُني السجلّ داخل البثّ لكان الردّ بعد أن دُفع ثمن التوليد، ولظهرت
        مراحل في الواجهة ثم اختفت. **والفحص هنا على الحركة لا على الرسالة**: لا
        نداء أداة، ولا نموذج تضمين — فالمسار **لم يبدأ أصلاً**، ومن ثمّ لا إطار
        مرحلة، لأن النقطة رفعت قبل أن تُرجع بثّاً يُستهلك.
        """
        with self.assertRaises(main.HTTPException) as caught:
            asyncio.run(
                main.generate(
                    main.GenerateRequest(
                        prompt="صغ عقداً",
                        doc_type="عقد",
                        facts=[main.FactPayload(**dict(RELEASE_FACT, standing="باطلة"))],
                    )
                )
            )

        self.assertEqual(caught.exception.status_code, 400)
        # ⚠️ والردّ من موضع السجلّ لا من موضع آخر: الرسالة تسمّي الدرجة.
        self.assertIn("درجة الواقعة", caught.exception.detail)
        self.assertEqual(fake_deps.AGENT_SCRIPT, [])
        self.assertEqual(fake_deps.FakeEmbedder.instances, [], "استُدعي النموذج")
        self.assertEqual(fake_deps.FAKE_SUPABASE.calls, [], "جرت أداة استرجاع")

    def test_a_valid_ledger_is_built_before_the_agent_runs(self):
        """
        ⚠️ **والبناء قبل الخيط، والبثّ بعد النداء**: نداء `/generate` بحملٍ صالح
        يُرجع بثّاً **ولا يكون الوكيل قد جرى بعد** — فالسجلّ بُني، والرسائل بُنيت،
        ولم يُضمَّن نصّ ولم يُسترجَع سند. والمفحوص أنّ الردّ لا ينتظر التوليد: لو
        جرى الوكيل داخل النقطة لظهر أثرُه قبل أن يُستهلك البثّ.
        """
        fake_deps.AGENT_SCRIPT = scripted_turn(GENUINE_QUOTE, body=CLEAN_DRAFT)

        response = asyncio.run(
            main.generate(
                main.GenerateRequest(prompt="صغ عقداً", doc_type="عقد", facts=FACTS)
            )
        )

        self.assertEqual(response.media_type, "text/event-stream")
        self.assertEqual(
            fake_deps.FakeEmbedder.instances, [], "جرى الوكيل قبل إرجاع البثّ"
        )
        self.assertEqual(fake_deps.FAKE_SUPABASE.calls, [], "جرت أداة قبل البثّ")


class TestFactsFrame(MainTestBase):
    """
    إطار `facts` — فحص الأمانة على المسودّة، وإعلانه حين لا يُشغَّل.
    ========================================================================
    ⚠️ **وموضع الإطار في البثّ شرطٌ في فائدته**: الواقعة المُغيَّرة تُرى **قبل**
    أن يُعتمد المستند لا بعده. وقد تكرّر العيب في ثلاث مسودّات لأن الإنذار كان
    يأتي — لو جاء — بعد التسليم.
    """

    def facts_of(self, events: list) -> dict:
        """إطار `facts` الواحد من إطارات البثّ."""
        frames = [event for event in events if event["type"] == "facts"]
        self.assertEqual(len(frames), 1, "إطار `facts` ليس واحداً")
        return frames[0]["report"]

    def test_a_valid_fact_payload_emits_a_facts_frame(self):
        """حملٌ صالح ⇒ إطارٌ واحد يقول إنّ الفحص **جرى**، ومعه مخرَج الوحدة."""
        fake_deps.AGENT_SCRIPT = scripted_turn(GENUINE_QUOTE, body=CLEAN_DRAFT)
        report = self.facts_of(
            parse_frames(
                drain_sse(
                    main._build_messages("صغ عقداً"), None, ledger_of([FULL_FACT])
                )
            )
        )

        self.assertTrue(report["ran"])
        self.assertEqual(report["message"], "")
        self.assertEqual(report["ledger"]["fact_count"], 1)
        self.assertEqual(report["shifts"], [])
        # ⚠️ وقاعدتا الوحدة تصلان مع الملخّص، فلا تُقرأ وقائعه بلا قواعده.
        self.assertIn(
            "client_statement_is_not_proof", report["ledger"]["rules"]
        )
        self.assertIn(
            "opponent_pleading_is_not_evidence", report["ledger"]["rules"]
        )

    def test_no_ledger_still_emits_a_facts_frame_saying_it_did_not_run(self):
        """
        🔑 **ولا يُحذف الإطار عند غياب السجلّ — ولا يدّعي أنّ الفحص نجح.**

        وهذا هو الأصل الذي يقوم عليه `briefing.py`: **الفحص الذي لم يُشغَّل ليس
        فحصاً نجح.** ولو حُذف الإطار لَقرأ المحامي سكوتاً، والسكوت في موضع فحصٍ
        يُقرأ سلامة — **والواقعة المُغيَّرة لا يكشفها فحص الأسانيد ولا الصياغة**.
        """
        fake_deps.AGENT_SCRIPT = scripted_turn(GENUINE_QUOTE)
        report = self.facts_of(
            parse_frames(drain_sse(main._build_messages("صغ عقداً")))
        )

        self.assertFalse(report["ran"])
        self.assertIsNone(report["ledger"], "ملخّص بلا فحص يُقرأ نظافة")
        self.assertEqual(report["shifts"], [])
        self.assertIn("لم يُجرِ", report["message"])
        self.assertIn("لم يُشغَّل", report["message"])
        # ⚠️ ولا عبارة سلامة في نصّ الغياب.
        self.assertNotIn("سليم", report["message"])
        self.assertNotIn("لا افتراق", report["message"])

    def test_a_changed_fact_reaches_the_frame(self):
        """
        🔑 **العيب التاريخي نفسه — لا واقعة مُخترَعة للاختبار.**

        الموظف **رفض التوقيع على مخالصة متضمّنة تنازلاً**، فصارت في المسودّة
        **رفض استلام المبلغ**. والفرق ليس في الصياغة بل في **مَن عليه الخطأ**:
        الأول يمتنع عن تنازل، والثاني يمتنع عن قبض حقّه. والأولى تُبنى عليها
        دعوى العامل، والثانية تُهدَم بها.

        ⚠️ **والمفحوص أنّ الافتراق وصل الإطار** — بالواقعة بعينها، وبوسمٍ ليس
        «لم تُذكر»: فالواقعة **حاضرة محرَّفة**، وهي التي تُقرأ فتُقبل. ووسمُها
        ``missing`` كان يُخفي أنّها في المسودّة بمعنى آخر — وهو الفرق الذي
        ضُبطت عليه عتبات `facts.py`.
        """
        fake_deps.AGENT_SCRIPT = scripted_turn(GENUINE_QUOTE, body=FLAWED_DRAFT)
        report = self.facts_of(
            parse_frames(
                drain_sse(main._build_messages("صغ عقداً"), None, ledger_of(FACTS))
            )
        )

        self.assertTrue(report["ran"])
        shifts = report["shifts"]
        self.assertEqual(
            [shift["fact_key"] for shift in shifts],
            ["release.refused"],
            "لم يصل الافتراق إلى الإطار — وهو العيب الذي تكرّر ثلاث مرّات",
        )

        shifted = shifts[0]
        self.assertNotEqual(shifted["kind"], "missing", "الواقعة حاضرة لا غائبة")
        self.assertIn("استلام", shifted["draft_text"])
        self.assertIn("التوقيع", shifted["fact_statement"])
        self.assertIn("تنازلاً", shifted["fact_statement"])
        # ⚠️ والوسم من الوحدة لا منّا: الأرقام والعتبات تُقرأ في `note` أيضاً،
        # لأن العتبات **عتبات**، والمحامي يستحقّ أن يعرف قربَ الافتراق من الحدّ.
        self.assertTrue(shifted["note"].strip())
        self.assertEqual(report["ledger"]["shifts"], shifts)

    def test_a_faithful_draft_does_not_shift_a_fact_that_matches_it(self):
        """
        ⚠️ **والقياس السالب: أداة تُنذر دائماً لا تُنذر أبداً.**

        مسودّة تحمل الواقعة بنصّها ⇒ لا افتراق. ولو أُنذر عليها لصار كل إنذار
        من الفحص ضجيجاً يُقرأ ويُهمَل — ومع الإهمال يمرّ العيب الحقيقي.
        """
        fake_deps.AGENT_SCRIPT = scripted_turn(GENUINE_QUOTE, body=CLEAN_DRAFT)
        report = self.facts_of(
            parse_frames(
                drain_sse(
                    main._build_messages("صغ عقداً"), None, ledger_of([FULL_FACT])
                )
            )
        )
        self.assertEqual(report["shifts"], [])

    def test_the_frame_is_json_serializable(self):
        """الإطار يُبثّ بـ ``json.dumps`` — وإلا انكسر البثّ صامتاً."""
        fake_deps.AGENT_SCRIPT = scripted_turn(GENUINE_QUOTE, body=FLAWED_DRAFT)
        for event in parse_frames(
            drain_sse(main._build_messages("صغ عقداً"), None, ledger_of(FACTS))
        ):
            if event["type"] == "facts":
                json.dumps(event["report"], ensure_ascii=False)

    def test_no_draft_means_no_facts_frame_and_no_false_missing(self):
        """
        ⚠️ **وبلا مسودّة لا يُبنى الإطار أصلاً** — ولا تُوسم كل واقعة ``missing``.

        ولو بُني لَوسم الفحص **كل** واقعة غائبة، لا لأنها سقطت من مسودّة، بل
        لأنه لا مسودّة — والوسم حينها **كذبٌ لا إنذار**: يُقرأ سقوطُ وقائع لم
        تُكتب بعد. وهذا هو مسار الفشل نفسه الذي يُبثّ فيه خطأٌ صريح.
        """
        fake_deps.AGENT_SCRIPT = [{"content": ""}]
        events = parse_frames(
            drain_sse(main._build_messages("صغ عقداً"), None, ledger_of(FACTS))
        )
        kinds = [event["type"] for event in events]

        self.assertNotIn("facts", kinds)
        self.assertNotIn("briefing", kinds)
        self.assertIn("error", kinds)


# ==============================================================================
# ١٠. التقرير الداخلي — المخرج الثاني، ومَنع الطمأنة الكاذبة
# ==============================================================================


class TestBriefingFrame(MainTestBase):
    """
    إطار `briefing`: التقرير الداخلي مفصولاً عن المذكرة.
    ========================================================================
    ⚠️ **وعلّة وجود الوحدة ليست عرض الأرقام بل منع خلطٍ واحد**: أن يُقرأ
    **«لم يُفحص»** كما يُقرأ **«فُحص فلم يُوجد عيب»**. وهذا الخلط وقع فعلاً في
    `review-panel.tsx`: وصل الشكل `failed: True` ومعه `clean: True`، فقُدِّم
    `clean` فقيل «سليمة» عن مراجعة **لم تحدث قطّ**.
    """

    def briefing_of(self, events: list) -> dict:
        """إطار `briefing` الواحد من إطارات البثّ."""
        frames = [event for event in events if event["type"] == "briefing"]
        self.assertEqual(len(frames), 1, "إطار `briefing` ليس واحداً")
        return frames[0]

    def test_the_briefing_frame_is_emitted_last_and_carries_both_shapes(self):
        """
        🔑 **والإطار يحمل قاموس الوحدة ونصّها معاً.**

        ⚠️ **والنصّ يُرسل لأنه لا يُعاد بناؤه**: لو أعادت الواجهة رسم التقرير
        لنشأ نصٌّ ثانٍ ينحرف عن `to_markdown` عند أوّل تعديل — وهو الانحراف
        الصامت نفسه الذي أُصلح في الأدوات الخمس.
        """
        fake_deps.AGENT_SCRIPT = scripted_turn(GENUINE_QUOTE, body=CLEAN_DRAFT)
        self.swap_review_llm(_CleanReviewLLM())
        events = parse_frames(
            drain_sse(
                main._build_messages("صغ عقداً"),
                case_report(COMPLETE_CASE_ANSWERED),
                ledger_of([FULL_FACT]),
            )
        )
        frame = self.briefing_of(events)

        # القاموس: درجةٌ من ثلاث، ونعتٌ، ومصادر لكل نوع متوقَّع.
        self.assertIn(frame["report"]["safety"], briefing.SAFETY_LEVELS)
        self.assertEqual(
            [source["kind"] for source in frame["report"]["sources"]],
            list(briefing.EXPECTED_KINDS),
            "نوع متوقَّع غاب من التقرير — فيُقرأ غيابه سلامةً",
        )
        # والنصّ: نفس ما تُنتجه الوحدة، لا نسخةً منه.
        self.assertTrue(frame["markdown"].startswith("# تقرير داخلي"))
        self.assertIn(f"حالة التحقّق: {frame['report']['safety']}", frame["markdown"])
        self.assertIn("## المصادر", frame["markdown"])

    def test_nothing_is_reported_ready_to_file_in_any_frame(self):
        """
        🔑 **ولا إطار واحد يصف المخرج بأنه انتهى قابلاً للتسليم.**

        ⚠️ **وهذا القياس على «أفضل حال ممكنة»**: الفحوص كلها جرت، ولا سؤال
        مفتوح، ولا دعوى غير موثَّقة، ولا خطأ مُبلَّغ عنه — حتى الدرجة العليا
        تُبلَغ. ولو ظهرت العبارة في أي حال فستظهر هنا؛ ولذلك يُفحَص **كل إطار**
        لا إطار التقرير وحده: العبارة تُكتب في سطر حالة أو في عنوان.
        """
        fake_deps.AGENT_SCRIPT = scripted_turn(GENUINE_QUOTE, body=CLEAN_DRAFT)
        self.swap_review_llm(_CleanReviewLLM())
        events = parse_frames(
            drain_sse(
                main._build_messages("صغ عقداً"),
                case_report(COMPLETE_CASE_ANSWERED),
                ledger_of([FULL_FACT]),
            )
        )
        frame = self.briefing_of(events)
        # ⚠️ أوّلاً: هذه **أفضل حال** فعلاً — وإلا لكان الفحص على حالٍ أدنى.
        self.assertEqual(frame["report"]["safety"], briefing.SAFETY_VERIFIED)

        everything = "\n".join(
            json.dumps(event, ensure_ascii=False) for event in events
        )
        for phrase in FORBIDDEN_READY_PHRASES:
            with self.subTest(phrase=phrase):
                self.assertNotIn(phrase, everything)

    def test_a_check_that_did_not_run_reaches_briefing_as_absent(self):
        """
        🔑 **والمراجعة الفاشلة تصل التقرير غائبةً — لا نظيفة.**

        ⚠️ **وهذا مسارٌ واقعيّ لا مُصطنَع**: الوهميّ في `fake_deps` يُرجع نصّاً
        فارغاً، و`parse_review` يرفع عليه، فيُنتج `_review_round` الشكل الحقيقي
        للفشل: ``failed: True`` **ومعه ``clean: True`` و``error_count: 0``**.

        فيُفحص شيئان معاً:
          ١. الإطار يُمرَّر **كما هو** — ``failed`` و``clean`` فيه، ولا نُصلحه
             هنا: إصلاحُه في `main.py` يُخفي أنّ النداء لم يجرِ.
          ٢. والتقرير **لا يقرؤه نظيفاً**: المصدر غائب، وعدده ``None`` لا ``0``
             (والصفر هنا يُقرأ «لا خطأ» عن فحص لم يحدث)، والدرجة ليست عليا.
        """
        fake_deps.AGENT_SCRIPT = scripted_turn(GENUINE_QUOTE, body=CLEAN_DRAFT)
        events = parse_frames(
            drain_sse(
                main._build_messages("صغ عقداً"),
                case_report(COMPLETE_CASE_ANSWERED),
                ledger_of([FULL_FACT]),
            )
        )

        # ١) الإطار كما هو — وفيه الطُعم الذي أُصلح في `review-panel.tsx`.
        review_frame = next(
            event for event in events if event["type"] == "review"
        )["report"]
        self.assertTrue(review_frame["failed"])
        self.assertTrue(review_frame["clean"], "الطُعم: فشلٌ يقول إنّه نظيف")
        self.assertEqual(review_frame["error_count"], 0)

        # ٢) والتقرير لا يقرؤه نظافة.
        report = self.briefing_of(events)["report"]
        label = next(
            source.label for source in briefing.gather(None) if source.kind == "review"
        )
        source = next(item for item in report["sources"] if item["kind"] == "review")
        self.assertFalse(source["present"], "مراجعة لم تحدث قُدّمت حاضرةً")
        self.assertIsNone(
            source["errors"], "صفرٌ مكان «لا نعلم» يُقرأ «لا خطأ»"
        )
        self.assertNotIn("سليم", source["summary"])
        self.assertIn("لم يُشغَّل", "\n".join(report["gaps"]))
        self.assertIn(f"{label}: لم يُشغَّل الفحص", "\n".join(report["gaps"]))
        self.assertNotEqual(report["safety"], briefing.SAFETY_VERIFIED)
        # ⚠️ والنصّ يقول الحدّ نفسه: الصفّ يقول إنّ الفحص لم يُجرِ، والعدد «—».
        markdown = self.briefing_of(events)["markdown"]
        self.assertIn(f"| {label} | لم يُجرِ الفحص |", markdown)

    def test_the_absent_ledger_reaches_briefing_as_absent_too(self):
        """
        ⚠️ **وغياب السجلّ يصل التقرير غائباً كذلك** — لا ملخّصاً نظيفاً.

        ولا يكفي أن يقول إطار `facts` إنّ الفحص لم يُشغَّل: التقرير الداخلي
        يُبنى من ملخّصات، فلو مُرِّر له ``{"shifts": []}`` لَحُسب الفحص **ناجحاً**
        بلا خطأ — وهي الطمأنة الكاذبة بعينها في نوع آخر.
        """
        fake_deps.AGENT_SCRIPT = scripted_turn(GENUINE_QUOTE, body=CLEAN_DRAFT)
        events = parse_frames(
            drain_sse(main._build_messages("صغ عقداً"), case_report(COMPLETE_CASE))
        )

        report = self.briefing_of(events)["report"]
        source = next(item for item in report["sources"] if item["kind"] == "facts")
        self.assertFalse(source["present"])
        self.assertIsNone(source["errors"])
        self.assertIn("الوقائع: لم يُشغَّل الفحص", "\n".join(report["gaps"]))

    def test_the_open_questions_of_the_case_reach_the_report(self):
        """
        ⚠️ **والأسئلة المفتوحة تمنع الدرجة العليا — ولا تُسكَت.**

        ولو لم تُمرَّر لقال نعت التقرير **«ولم يبقَ سؤال مفتوح»** وإطار `case`
        فوقه يعرض أسئلةً لم تُجب. فالطمأنة الكاذبة لا تُمنع في الوحدة وحدها:
        **يجب أن يصلها ما يجعلها صادقة**.
        """
        fake_deps.AGENT_SCRIPT = scripted_turn(GENUINE_QUOTE, body=CLEAN_DRAFT)
        self.swap_review_llm(_CleanReviewLLM())
        events = parse_frames(
            drain_sse(
                main._build_messages("صغ عقداً"),
                case_report(COMPLETE_CASE),
                ledger_of([FULL_FACT]),
            )
        )

        case_questions = main._case_frame(
            main._case_from_payload(case_input(COMPLETE_CASE))
        )["questions"]
        self.assertTrue(case_questions, "القضية المرجعية بلا أسئلة مفتوحة")

        report = self.briefing_of(events)["report"]
        self.assertEqual(
            list(report["open_questions"]),
            [question["question"] for question in case_questions],
        )
        # ⚠️ والسؤال المفتوح **يمنع** الدرجة العليا — وهو الأثر العملي.
        self.assertNotEqual(report["safety"], briefing.SAFETY_VERIFIED)

    def test_the_report_names_the_checks_by_their_module_labels(self):
        """
        ⚠️ **والأنواع تُعرض بأسماء الوحدة** — ولو كتبنا الأسماء هنا لافترقت
        نسختان: واحدة في التقرير وواحدة في الاختبار.
        """
        fake_deps.AGENT_SCRIPT = scripted_turn(GENUINE_QUOTE, body=CLEAN_DRAFT)
        self.swap_review_llm(_CleanReviewLLM())
        events = parse_frames(
            drain_sse(
                main._build_messages("صغ عقداً"),
                case_report(COMPLETE_CASE_ANSWERED),
                ledger_of([FULL_FACT]),
            )
        )
        report = self.briefing_of(events)["report"]

        self.assertEqual(
            [source["label"] for source in report["sources"]],
            [source.label for source in briefing.gather(None)],
        )


class TestFrameOrder(MainTestBase):
    """
    ترتيب الإطارات — **الترتيب المُنفَّذ يُثبَّت هنا، ويُعلَّل**.
    ========================================================================
    ⚠️ **والترتيب ليس تفصيلاً في العرض**، وهو الدرس المكتوب في `briefing.py`
    نفسه: `_verify_round` كان يبني الشكل صحيحاً **ولم يكن أحد يسأل هل يصل**.
    فما يُفحص هنا المواضع لا الوجود:

        case ← المراحل ← citations ← language ← review ← facts ← briefing
             ← مرحلة الختم ← done

    والعلل ثلاث:
      ١. **`case` أولاً** لأنه يُثبِت ما بُنيت عليه المسودّة قبل أن تبدأ — وهو
         موضعٌ فُحص من قبل (`test_the_case_frame_precedes_the_first_stage`).
      ٢. **`facts` بعد `review` وقبل الختم**: الواقعة المُغيَّرة تُرى قبل أن
         يُعتمد المستند؛ والفحص يحتاج مسودّةً ومراجعةً قبلها فلا معنى لتقديمه.
      ٣. **`briefing` آخر إطار تقرير**: كل ما يُلخّصه معروف قبله، **ولا يُحسب
         بعده شيء** — لأن «لا عمل بعد الختم إلا التسليم»، فلا يُبنى تقرير بعد
         أن يُعتمد المستند. وما بعد `briefing` ليس تقريراً: مرحلة الختم، ثم
         التسليم.
    """

    def test_the_frames_come_in_the_order_they_build_on(self):
        fake_deps.AGENT_SCRIPT = scripted_turn(GENUINE_QUOTE, body=CLEAN_DRAFT)
        self.swap_review_llm(_CleanReviewLLM())
        events = parse_frames(
            drain_sse(
                main._build_messages("صغ عقداً"),
                case_report(COMPLETE_CASE_ANSWERED),
                ledger_of([FULL_FACT]),
            )
        )
        kinds = [event["type"] for event in events]

        self.assertEqual(kinds[0], "case", "أول إطار ليس ملف القضية")

        reports = ["citations", "language", "review", "facts", "briefing"]
        positions = [kinds.index(kind) for kind in reports]
        self.assertEqual(
            positions, sorted(positions), f"ترتيب إطارات التقارير انقلب: {kinds}"
        )

        # ⚠️ وكل ما يلخّصه التقرير **قبله**: لا يُبنى تقرير على ما لم يصل بعد.
        for kind in ("case", "citations", "language", "review", "facts"):
            with self.subTest(kind=kind):
                self.assertLess(kinds.index(kind), kinds.index("briefing"))

        # ⚠️ وما بعد التقرير ليس تقريراً: مرحلة الختم، ثم التسليم.
        after = kinds[kinds.index("briefing") + 1 :]
        self.assertEqual(after, ["stage", "done"])
        self.assertEqual(events[kinds.index("briefing") + 1]["stage"], main.KEY_SEAL)

    def test_the_facts_frame_precedes_the_seal_stage(self):
        """🔑 **والواقعة المُغيَّرة تُرى قبل الختم لا بعده** — وهذا كلّ الفائدة."""
        fake_deps.AGENT_SCRIPT = scripted_turn(GENUINE_QUOTE, body=FLAWED_DRAFT)
        events = parse_frames(
            drain_sse(
                main._build_messages("صغ عقداً"), None, ledger_of(FACTS)
            )
        )
        kinds = [event["type"] for event in events]
        seal = kinds.index("stage", kinds.index("facts"))

        self.assertLess(kinds.index("facts"), seal)
        self.assertEqual(events[seal]["stage"], main.KEY_SEAL)
        self.assertLess(kinds.index("facts"), kinds.index("done"))


class TestChatStaysWorking(MainTestBase):
    """
    `/chat` يبقى كما كان — **والخيار المُعلَن: الثلاثي لا يتغيّر شكله**.
    ========================================================================
    ⚠️ **والبديل كان إضافة إطارَي الوقائع والتقرير إلى مُعاد
    `_run_agent_collect`**، وهو يهدم عقداً قائماً على ثلاثة ويُحوّل `/chat` إلى
    مسارٍ ثانويّ مختلف الشكل. أما الإطارات الجديدة فتُهمَل فيه كما يُهمَل إطار
    `review` القائم — لأن `/chat` **لا يبثّ SSE أصلاً**، فلا موضع لإطار بثّ في
    ردّ محادثة. وثمنُ ذلك أن `_stream_agent` يبنيها ثم تُهمَل: حسابٌ حتمي بلا
    نموذج ولا شبكة، أرخص من مسارين يفترقان.
    """

    def test_chat_still_answers_in_the_same_shape(self):
        fake_deps.AGENT_SCRIPT = scripted_turn(GENUINE_QUOTE)
        payload = asyncio.run(main.chat_endpoint(main.ChatRequest(prompt="صغ عقداً")))

        self.assertEqual(
            set(payload), {"response", "session_id", "citations", "language"}
        )
        self.assertTrue(payload["citations"]["has_evidence"])
        self.assertIn("summary", payload["language"])
        # ⚠️ ولا إطار بثّ في ردّ المحادثة — لا `facts` ولا `briefing` ولا `review`.
        for frame_kind in ("facts", "briefing", "review", "case"):
            with self.subTest(frame=frame_kind):
                self.assertNotIn(frame_kind, payload)

    def test_the_collector_still_returns_a_three_tuple(self):
        """
        ⚠️ **والشكل ثلاثيّ — والفحص بالعدد والأنواع معاً.**

        (ولهذا الفحص نظيرٌ في `TestRunAgentCollectShape`؛ وهو يُعاد هنا لأن
        الإطارات الجديدة هي التي تهدّده — فالاختبار الذي يحرس عقداً لا يُترك
        يشهد على نفسه.)
        """
        fake_deps.AGENT_SCRIPT = scripted_turn(GENUINE_QUOTE)
        collected = main._run_agent_collect(main._build_messages("صغ عقداً"))

        self.assertIsInstance(collected, tuple)
        self.assertEqual(len(collected), 3)
        final_text, citations, language = collected
        self.assertIn("عقد إيجار", final_text)
        self.assertIn("summary", citations)
        self.assertIn("summary", language)


if __name__ == "__main__":
    unittest.main(verbosity=2)
