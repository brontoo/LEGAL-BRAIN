"""
اختبارات المراجع الثاني — التحقّق من اعتراضات الخصم.
=============================================================================

تشغيل:
    python -m unittest discover -s tests -t . -v

حتمية بالكامل: بلا شبكة، وبلا نموذج، وبلا قاعدة بيانات، وبلا قرص.

ولماذا لا تحتاج `fake_deps`؟ لأن هذا الملف لا يلمس الطبقة الخارجية أصلاً:
لا `supabase` ولا نموذج تضمين ولا مفتاح API. مخرج المراجع يصل **نصّاً**،
والمقتطفات تصل **نصّاً** منسّقاً (يُبنى في الإنتاج بـ
`citations.format_evidence_block` — وقد استُعمل هنا في بناء البيانات نفسها،
فاختُبرت الوصلة الحقيقية بلا قاعدة بيانات). فلا شيء يُستعار ولا شيء يُحاكى.

وأهمّ اختبار في الملف: `test_a_forged_basis_is_dropped_and_counted` مع
`test_a_forged_quote_is_dropped_and_counted` — لأن الفكرة كلها أن **المراجع
لا يُصدَّق**. ومراجع يختلق سنده أو نصّه أسوأ من عدم وجود مراجع: يُطمئن
المحامي زوراً.
"""

import json
import pathlib
import re as _re
import unittest

import citations
import review
from citations import Evidence, format_evidence_block, normalize, quote_in_text
from review import (
    DEFAULT_KIND,
    DEFAULT_SEVERITY,
    KINDS,
    MIN_QUOTE_CHARS,
    REVIEW_BEGIN,
    REVIEW_END,
    ReviewFinding,
    ReviewOutcome,
    ReviewParseError,
    build_review_prompt,
    parse_review,
    summarize,
)


# ==============================================================================
# بيانات الاختبار
# ==============================================================================
# الموجز والمسودّة **يختلفان في واقعة واحدة مقصودة**: الموجز يقول إن المتأخر
# ثلاثة أشهر وقد سُدّد شهر، والمسودّة تقول أربعة أشهر ولم يُسدَّد شيء. فهذه
# مخالفة يلتقطها المراجع، وهي مادة اختبار `fact` الحقيقية لا المتخيَّلة.

BRIEF = (
    "الموجز: إنذار المستأجر قبل الفسخ.\n"
    "الوقائع: تأخّر المستأجر عن سداد الأجرة المتأخرة عن ثلاثة أشهر، وقد سدّد "
    "شهراً واحداً بإيصال مؤرّخ في ١٠ مارس ٢٠٢٤.\n"
    "المطلوب: إنذار بالمبلغ المتبقّي ومهلة سبعة أيام للسداد."
)

DRAFT = (
    "إنذار قانوني\n"
    "\n"
    "إلى: شركة الأفق للتجارة\n"
    "\n"
    "بموجب عقد الإيجار المؤرّخ في ١ يناير ٢٠٢٣، تأخّر المستأجر عن سداد الأجرة "
    "عن أربعة أشهر كاملة، ولم يسدّد شيئاً حتى تاريخه.\n"
    "\n"
    "ونطالب بسداد المبلغ خلال سبعة أيام من تاريخ الاستلام، استناداً إلى "
    "المادة ٧٥ من قانون المعاملات المدنية."
)

#: مقطع مسترجَع كما يُعطى للمراجع — منسّق بدالّة `citations` نفسها.
ARTICLE_TEXT = (
    "المادة ٧٥: للمالك أن يطالب بالأجرة المتأخرة، ولا يفسخ العقد إلا بعد "
    "إنذار مدّته ثلاثون يوماً على الأقل."
)

EVIDENCE = format_evidence_block(
    [
        Evidence(
            ref="L1",
            chunk_id="11",
            document_name="قانون المعاملات المدنية",
            text=ARTICLE_TEXT,
            similarity=0.91,
            tool="legislation",
        )
    ]
)

#: اقتباسات حرفية من المسودّة.
Q_MONTHS = "تأخّر المستأجر عن سداد الأجرة عن أربعة أشهر كاملة"
Q_PAID = "ولم يسدّد شيئاً حتى تاريخه"
Q_TERM = "سبعة أيام من تاريخ الاستلام"
Q_ARTICLE = "المادة ٧٥ من قانون المعاملات المدنية"
#: اقتباس **مؤلَّف**: صياغته معقولة ورقمه القانوني واقعي، ولا وجود له في المسودّة.
Q_FORGED = "ولم يسدّد سوى شهرين اثنين حتى تاريخه"

#: سند حرفي من الموجز أو المقتطفات.
B_MONTHS = "الأجرة المتأخرة عن ثلاثة أشهر"
B_PAID = "سدّد شهراً واحداً بإيصال"
B_TERM = "ومهلة سبعة أيام للسداد"
B_NOTICE = "إنذار مدّته ثلاثون يوماً على الأقل"
#: سند **مؤلَّف**: يبدو مادة قانونية، ولا وجود له في الموجز ولا في المقتطفات.
B_FORGED = "المادة ٧٦ تمنح المالك حقّ الفسخ الفوري"

VALID_QUOTES = (Q_MONTHS, Q_PAID, Q_TERM, Q_ARTICLE)
VALID_BASES = (B_MONTHS, B_PAID, B_TERM, B_NOTICE)


def finding(**overrides) -> dict:
    """اعتراض صالح تماماً — يُعدَّل في كل اختبار بما يخصّه وحده."""
    element = {
        "kind": "fact",
        "severity": "error",
        "message": "المسودّة تقول أربعة أشهر والموجز يقول ثلاثة.",
        "quote": Q_MONTHS,
        "basis": B_MONTHS,
    }
    element.update(overrides)
    return element


def as_json(*elements: object) -> str:
    """يبني مخرج مراجع كما يخرج من النموذج فعلاً: عربي غير مُهرَّب."""
    return json.dumps(list(elements), ensure_ascii=False)


def parse(*elements: object) -> ReviewOutcome:
    """يقرأ اعتراضات على بيانات الاختبار المشتركة."""
    return parse_review(as_json(*elements), DRAFT, BRIEF, EVIDENCE)


# ==============================================================================
# ٠. سلامة بيانات الاختبار
# ==============================================================================


class TestFixturesAreReal(unittest.TestCase):
    """
    ضمان على البيانات نفسها.

    لو انحرف اقتباس في هذا الملف بحرف، لصار اختبار «الاقتباس الصحيح يُقبَل»
    يختبر الإسقاط لا القبول — ويمرّ أخضر وهو يقيس العكس. فيُثبَّت هنا أن كل
    اقتباس **موجود فعلاً** في مصدره، وأن المؤلَّف **غائب فعلاً** عن مصدره.
    """

    def test_each_quote_is_verbatim_in_the_draft(self):
        for quote in VALID_QUOTES:
            with self.subTest(quote=quote):
                self.assertTrue(quote_in_text(quote, DRAFT), quote)

    def test_each_basis_is_verbatim_in_the_brief_or_the_evidence(self):
        for basis in VALID_BASES:
            with self.subTest(basis=basis):
                self.assertTrue(
                    quote_in_text(basis, BRIEF) or quote_in_text(basis, EVIDENCE),
                    basis,
                )

    def test_the_forged_quote_is_not_in_the_draft(self):
        self.assertFalse(quote_in_text(Q_FORGED, DRAFT))

    def test_the_forged_basis_is_in_neither_source(self):
        self.assertFalse(quote_in_text(B_FORGED, BRIEF))
        self.assertFalse(quote_in_text(B_FORGED, EVIDENCE))

    def test_the_draft_really_contradicts_the_brief(self):
        """وإلا لكان اختبار `fact` يختبر مخالفة غير موجودة."""
        self.assertIn("أربعة أشهر", DRAFT)
        self.assertIn("ثلاثة أشهر", BRIEF)


# ==============================================================================
# ١. قراءة المصفوفة السليمة
# ==============================================================================


class TestParseWellFormed(unittest.TestCase):
    """المصفوفة السليمة — كل حقل يصل إلى المحامي كما كتبه المراجع."""

    def test_fields_survive_intact(self):
        outcome = parse(finding())
        self.assertIsInstance(outcome, ReviewOutcome)
        self.assertEqual(outcome.dropped, 0)
        self.assertEqual(len(outcome.findings), 1)

        item = outcome.findings[0]
        self.assertEqual(item.kind, "fact")
        self.assertEqual(item.severity, "error")
        self.assertEqual(item.message, "المسودّة تقول أربعة أشهر والموجز يقول ثلاثة.")
        self.assertEqual(item.quote, Q_MONTHS)
        self.assertEqual(item.basis, B_MONTHS)

    def test_several_elements_are_all_read(self):
        outcome = parse(
            finding(kind="fact", quote=Q_MONTHS, basis=B_MONTHS),
            finding(kind="omission", severity="notice", quote=Q_PAID, basis=B_PAID),
            finding(kind="unsupported", severity="notice", quote=Q_ARTICLE, basis=""),
        )
        self.assertEqual(len(outcome.findings), 3)
        self.assertEqual(outcome.dropped, 0)

    def test_extra_keys_are_ignored(self):
        element = finding()
        element["confidence"] = 0.4
        element["explanation"] = "شرح زائد"
        self.assertEqual(len(parse(element).findings), 1)

    def test_escaped_arabic_parses_the_same(self):
        """المراجع قد يُعيد النصّ مُهرَّباً (\\uXXXX) — وهو النصّ نفسه."""
        escaped = json.dumps([finding()], ensure_ascii=True)
        plain = json.dumps([finding()], ensure_ascii=False)
        self.assertEqual(
            parse_review(escaped, DRAFT, BRIEF, EVIDENCE).findings,
            parse_review(plain, DRAFT, BRIEF, EVIDENCE).findings,
        )


class TestTolerantReading(unittest.TestCase):
    """النموذج يحيط جوابه بالنثر والسياج رغم المنع — فيُقرأ لا يُرفض."""

    def test_json_wrapped_in_prose(self):
        text = "إليك اعتراضاتي:\n" + as_json(finding()) + "\nوشكراً على الثقة."
        outcome = parse_review(text, DRAFT, BRIEF, EVIDENCE)
        self.assertEqual(len(outcome.findings), 1)

    def test_json_in_a_markdown_fence(self):
        text = "```json\n" + as_json(finding()) + "\n```"
        self.assertEqual(len(parse_review(text, DRAFT, BRIEF, EVIDENCE).findings), 1)

    def test_json_inside_the_review_markers(self):
        text = f"{REVIEW_BEGIN}\n{as_json(finding())}\n{REVIEW_END}"
        self.assertEqual(len(parse_review(text, DRAFT, BRIEF, EVIDENCE).findings), 1)

    def test_a_stray_bracket_before_the_array_is_skipped(self):
        """شرح فيه قوس غير مغلق لا يجوز أن يُسقِط الجواب كلّه."""
        text = "ملاحظة [غير مكتملة على المادة ٧٥\n" + as_json(finding())
        self.assertEqual(len(parse_review(text, DRAFT, BRIEF, EVIDENCE).findings), 1)

    def test_the_first_array_wins(self):
        """القاعدة المعلنة: **أول** مصفوفة، وما بعدها يُهمَل — ولو كانت فارغة."""
        text = "لا اعتراض [] ثم " + as_json(finding())
        outcome = parse_review(text, DRAFT, BRIEF, EVIDENCE)
        self.assertEqual(outcome.findings, [])
        self.assertEqual(outcome.dropped, 0)


class TestParseErrors(unittest.TestCase):
    """
    ما لا يُفهم يُرفع استثناءً — ولا يُقرأ صمتاً كأنه «لا اعتراض».

    وهذا الفرق جوهري: لو قُرئ فشل النداء «سلامةً»، لمرّ عطلٌ في المسار كأنه
    شهادة براءة للمسودّة.
    """

    def test_no_array_at_all_raises(self):
        for text in (
            "لا اعتراض.",
            "",
            "   ",
            None,
            "{}",
            '{"message": "خ"}',
            '```json\n{"a": 1}\n```',
            "[كلام ليس JSON]",
            "null",
        ):
            with self.subTest(text=text):
                with self.assertRaises(ReviewParseError):
                    parse_review(text, DRAFT, BRIEF, EVIDENCE)

    def test_an_unterminated_array_raises(self):
        with self.assertRaises(ReviewParseError):
            parse_review('[{"message": "خ"', DRAFT, BRIEF, EVIDENCE)

    def test_the_error_is_a_value_error(self):
        """ليمسكه من يمسك `ValueError` في المسار العام بلا معالجة خاصة."""
        self.assertTrue(issubclass(ReviewParseError, ValueError))


# ==============================================================================
# ٢. التحقّق — قلب الملف
# ==============================================================================


class TestVerification(unittest.TestCase):
    """
    لا يُصدَّق المراجع: كل اعتراض يُختبر بنصّه.

    والاختباران الأهمّ في الملف هنا: اقتباس مؤلَّف، وسند مؤلَّف. كلاهما يُسقَط
    ويُحسب. ولو مرّا لصار التقرير تهديداً لا حماية.
    """

    def test_a_forged_quote_is_dropped_and_counted(self):
        """🔑 صياغة معقولة ورقم واقعي — وليست في المسودّة. لا يجوز أن تمرّ."""
        outcome = parse(finding(quote=Q_FORGED, basis=B_MONTHS))
        self.assertEqual(outcome.findings, [])
        self.assertEqual(outcome.dropped, 1)

    def test_a_forged_basis_is_dropped_and_counted(self):
        """
        🔑 الاقتباس صحيح حرفياً والسند مؤلَّف.

        وهو أخطر من الاقتباس المؤلَّف، لأن الاعتراض يبدو **موثَّقاً**: يقرأ
        المحامي اقتباساً صادقاً من مستنده ويطمئنّ إلى سند لم يُكتب قطّ.
        """
        outcome = parse(finding(basis=B_FORGED))
        self.assertEqual(outcome.findings, [])
        self.assertEqual(outcome.dropped, 1)

    def test_a_basis_from_the_brief_is_kept(self):
        outcome = parse(finding(basis=B_MONTHS))
        self.assertEqual(len(outcome.findings), 1)
        self.assertEqual(outcome.dropped, 0)

    def test_a_basis_from_the_evidence_is_kept(self):
        outcome = parse(
            finding(kind="unsupported", severity="error", quote=Q_TERM, basis=B_NOTICE)
        )
        self.assertEqual(len(outcome.findings), 1)
        self.assertEqual(outcome.findings[0].basis, B_NOTICE)

    def test_an_empty_basis_is_kept(self):
        """اعتراض يقع على المسودّة وحدها لا سند له في الموجز — وهو مشروع."""
        outcome = parse(finding(quote=Q_ARTICLE, basis=""))
        self.assertEqual(len(outcome.findings), 1)
        self.assertEqual(outcome.findings[0].basis, "")

    def test_a_whitespace_basis_is_an_empty_basis(self):
        """الفراغ ليس سنداً — ولا يجوز أن يُسقِط اعتراضاً صحيحاً بسوء تقدير."""
        outcome = parse(finding(basis="   \n  "))
        self.assertEqual(len(outcome.findings), 1)
        self.assertEqual(outcome.findings[0].basis, "")

    def test_a_missing_basis_key_is_kept(self):
        element = finding()
        element.pop("basis")
        outcome = parse(element)
        self.assertEqual(len(outcome.findings), 1)
        self.assertEqual(outcome.findings[0].basis, "")

    def test_a_quote_from_the_brief_is_not_a_quote_from_the_draft(self):
        """
        المراجع نقل من الموجز ونسبه إلى المسودّة — فيُسقَط.

        والفحص يجري على **المسودّة** وحدها، لأن السؤال «ماذا كتبت المسودّة؟»
        لا «هل هذا النصّ موجود في مكان ما؟».
        """
        outcome = parse(finding(quote=B_MONTHS, basis=B_MONTHS))
        self.assertEqual(outcome.findings, [])
        self.assertEqual(outcome.dropped, 1)

    def test_a_short_quote_is_dropped_though_it_is_in_the_draft(self):
        """🔑 الإسقاط هنا **بالطول لا بالغياب** — والفرق يُثبَّت بالفحص المباشر."""
        short = "المادة"
        self.assertIn(short, DRAFT)
        self.assertLess(len(normalize(short)), MIN_QUOTE_CHARS)
        self.assertTrue(quote_in_text(short, DRAFT, min_quote_chars=1))

        outcome = parse(finding(quote=short))
        self.assertEqual(outcome.findings, [])
        self.assertEqual(outcome.dropped, 1)

    def test_a_short_basis_is_dropped_though_it_is_in_the_brief(self):
        """
        ⚠️ قرار مقصود: السند يمرّ بعتبة الاقتباس نفسها.

        «ثلاثة أشهر» موجودة في الموجز فعلاً، لكنها أقصر من اقتباس معتبر. ولو
        قُبل السند بوجوده وحده لأمكن «إسناد» كل اعتراض بكلمتين شائعتين توجدان
        في أي مقتطف — فتصير الحماية باباً بلا قفل.
        """
        short_basis = "ثلاثة أشهر"
        self.assertLess(len(normalize(short_basis)), MIN_QUOTE_CHARS)
        self.assertTrue(quote_in_text(short_basis, BRIEF, min_quote_chars=1))

        outcome = parse(finding(basis=short_basis))
        self.assertEqual(outcome.findings, [])
        self.assertEqual(outcome.dropped, 1)

    def test_a_quote_with_other_spacing_or_diacritics_is_kept(self):
        """
        المراجع لن يعيد التشكيل ولا فواصل الأسطر — وغيابها لا يُبطل اعتراضاً.

        ⚠️ ويُلاحظ أن المحفوظ هو **رسم المراجع** لا رسم المسودّة: نحن نتحقّق
        من النصّ المطبَّع، ولا نعيد كتابة اقتباسه. والقاعدة في `citations.py`
        تقوم على هذا التسامح نفسه، وإلا لبطل التحقّق مع كل مسودّة سليمة.
        """
        as_written = "وَلَمْ   يَسُدِّدْ\nشَيْئاً حتى تاريخه"
        self.assertEqual(normalize(as_written), normalize(Q_PAID))

        outcome = parse(finding(quote=as_written))
        self.assertEqual(len(outcome.findings), 1)
        self.assertEqual(outcome.findings[0].quote, as_written.strip())
        self.assertNotEqual(outcome.findings[0].quote, Q_PAID)

    def test_verification_is_per_element_not_all_or_nothing(self):
        """اعتراض فاسد لا يُسقِط الصحيح معه — الحكم فردي."""
        outcome = parse(
            finding(quote=Q_MONTHS, basis=B_MONTHS),
            finding(quote=Q_FORGED, basis=B_MONTHS),
            finding(kind="unsupported", severity="notice", quote=Q_PAID, basis=B_FORGED),
        )
        self.assertEqual(len(outcome.findings), 1)
        self.assertEqual(outcome.dropped, 2)


# ==============================================================================
# ٣. التصنيف المجهول لا يُسقِط المسار
# ==============================================================================


class TestUnknownLabelsDoNotCrash(unittest.TestCase):
    """
    التسمية الغريبة تُصحَّح ولا تقتل النداء.

    النموذج قد يخترع تصنيفاً («opinion»، «critical») في أي وقت. ولو رفع
    استثناءً لضاع التقرير كلّه — بما فيه الاعتراضات الصحيحة — بسبب كلمة واحدة.
    """

    def test_unknown_kind_and_severity_are_coerced_not_fatal(self):
        outcome = parse(finding(kind="opinion", severity="fatal"))
        self.assertEqual(len(outcome.findings), 1)
        self.assertEqual(outcome.dropped, 0)
        self.assertEqual(outcome.findings[0].kind, DEFAULT_KIND)
        self.assertEqual(outcome.findings[0].severity, DEFAULT_SEVERITY)
        self.assertEqual((DEFAULT_KIND, DEFAULT_SEVERITY), ("unsupported", "notice"))

    def test_missing_kind_and_severity_take_the_defaults(self):
        element = finding()
        element.pop("kind")
        element.pop("severity")
        item = parse(element).findings[0]
        self.assertEqual(item.kind, DEFAULT_KIND)
        self.assertEqual(item.severity, DEFAULT_SEVERITY)

    def test_a_coerced_label_does_not_block_delivery(self):
        """
        والافتراضي **ألين** لا أصلح: وسم تصنيف مجهول بأنه خطأ يمنع تسليم
        مسودّة قد تكون سليمة — أي معاقبة المحامي على عيب في تسمية النموذج.
        """
        outcome = parse(finding(severity="catastrophic"))
        self.assertTrue(outcome.clean)
        self.assertIn("لا مانع من التسليم", outcome.summary())

    def test_case_and_spacing_are_read(self):
        """« Fact » و« ERROR » هما `fact` و`error` — الرسم لا يغيّر التصنيف."""
        item = parse(finding(kind=" Fact ", severity=" ERROR ")).findings[0]
        self.assertEqual((item.kind, item.severity), ("fact", "error"))

    def test_non_objects_are_dropped_and_counted(self):
        """عنصر ليس كائناً يعني أن الشكل لم يُفهم — ويجب أن يُرى لا أن يمرّ."""
        text = json.dumps([1, "نصّ", None, ["مصفوفة"], finding()], ensure_ascii=False)
        outcome = parse_review(text, DRAFT, BRIEF, EVIDENCE)
        self.assertEqual(len(outcome.findings), 1)
        self.assertEqual(outcome.dropped, 4)

    def test_an_element_without_a_message_is_dropped(self):
        for value in (None, "", "   ", 5):
            with self.subTest(message=value):
                element = finding()
                element["message"] = value
                outcome = parse(element)
                self.assertEqual(outcome.findings, [])
                self.assertEqual(outcome.dropped, 1)

    def test_a_non_string_quote_is_dropped(self):
        """`quote` رقم مجرّد ليس اقتباساً — ولا يُحوَّل إلى نصّ ليمرّ."""
        element = finding()
        element["quote"] = 12345
        outcome = parse(element)
        self.assertEqual(outcome.findings, [])
        self.assertEqual(outcome.dropped, 1)


# ==============================================================================
# ٤. التكرار والترتيب
# ==============================================================================


class TestDeduplication(unittest.TestCase):
    """
    المراجع الذي يكرّر نفسه لا يُنتج جداراً من الضجيج.

    على نمط تجميع الفراغات في `language_audit.py`: أوّل تشغيل حقيقي أنتج أحد
    عشر خطأً متطابقاً، فصار التقرير جداراً أحمر لا يُقرأ — **ومعه يضيع العيب
    الحقيقي حين يظهر**. والمراجع الثاني أشدّ ميلاً إلى التكرار لأن الاعتراض
    الواحد يُصاغ من زوايا.
    """

    def test_identical_pairs_collapse_to_one(self):
        outcome = parse(finding(), finding())
        self.assertEqual(len(outcome.findings), 1)

    def test_a_duplicate_is_not_counted_as_dropped(self):
        """
        🔑 التكرار ليس إسقاطاً.

        `dropped` يُعرَض على المحامي بمعنى «لم يثبت نصّه». ولو دخل فيه التكرار
        لصار الرقم **كاذباً**: يقول إن المراجع اختلق نصّاً وهو لم يفعل، بل كرّر
        ما ثبت.
        """
        outcome = parse(finding(), finding(), finding())
        self.assertEqual(len(outcome.findings), 1)
        self.assertEqual(outcome.dropped, 0)

    def test_the_same_quote_with_a_different_kind_is_kept_twice(self):
        """مخالفة الموجز وضعف الحجّة قد يقعان على الجملة نفسها — وهما اعتراضان."""
        outcome = parse(
            finding(kind="fact", quote=Q_MONTHS, basis=B_MONTHS),
            finding(kind="strength", severity="notice", quote=Q_MONTHS, basis=B_MONTHS),
        )
        self.assertEqual(len(outcome.findings), 2)

    def test_the_same_kind_with_different_quotes_is_kept_twice(self):
        outcome = parse(finding(quote=Q_MONTHS), finding(quote=Q_PAID, basis=B_PAID))
        self.assertEqual(len(outcome.findings), 2)

    def test_diacritic_variants_of_the_same_quote_collapse(self):
        """
        والطي على النصّ **المطبَّع** لا على الرسم.

        فتكرار الاعتراض باختلاف تشكيل هو الاعتراض نفسه، وإسقاطه على الرسم
        وحده يُنتج جداراً متشابهاً — وهو الضجيج نفسه بصورة أخرى.
        """
        variant = "وَلَمْ يَسُدِّدْ شَيْئًا حَتَّى تَارِيخِهِ"
        self.assertEqual(normalize(variant), normalize(Q_PAID))

        outcome = parse(finding(quote=Q_PAID), finding(quote=variant))
        self.assertEqual(len(outcome.findings), 1)
        self.assertEqual(outcome.dropped, 0)


class TestOrdering(unittest.TestCase):
    """الترتيب المعروض: الأخطاء أولاً (تمنع التسليم)، ثم الأنواع بترتيبها."""

    def test_errors_come_before_notices(self):
        outcome = parse(
            finding(kind="strength", severity="notice", quote=Q_ARTICLE, basis=""),
            finding(kind="arithmetic", severity="error", quote=Q_MONTHS, basis=B_MONTHS),
            finding(kind="omission", severity="notice", quote=Q_TERM, basis=B_TERM),
            finding(kind="fact", severity="error", quote=Q_PAID, basis=B_PAID),
        )
        self.assertEqual(
            [item.severity for item in outcome.findings],
            ["error", "error", "notice", "notice"],
        )

    def test_kinds_follow_the_declared_order(self):
        """
        والترتيب **ليس أبجدياً** بل ترتيب `KINDS` المعلن: المخالفة الصريحة
        أولاً، وتقدير قوّة الحجّة آخراً — وهو ترتيب الثقل لا ترتيب الحروف.
        """
        outcome = parse(
            finding(kind="strength", severity="notice", quote=Q_ARTICLE, basis=""),
            finding(kind="arithmetic", severity="error", quote=Q_MONTHS, basis=B_MONTHS),
            finding(kind="fact", severity="error", quote=Q_PAID, basis=B_PAID),
            finding(kind="omission", severity="notice", quote=Q_TERM, basis=B_TERM),
        )
        self.assertEqual(
            [item.kind for item in outcome.findings],
            ["fact", "arithmetic", "omission", "strength"],
        )
        self.assertEqual(KINDS, ("fact", "omission", "unsupported", "arithmetic", "strength"))

    def test_equal_rank_keeps_the_reviewers_order(self):
        """ما تساوت رتبته يبقى بترتيب وروده — فالفرز مستقرّ لا عابث."""
        outcome = parse(
            finding(kind="unsupported", severity="notice", quote=Q_TERM, basis=""),
            finding(kind="unsupported", severity="notice", quote=Q_PAID, basis=""),
        )
        self.assertEqual([item.quote for item in outcome.findings], [Q_TERM, Q_PAID])


# ==============================================================================
# ٥. الجواب الفارغ — جوابٌ من الدرجة الأولى
# ==============================================================================


class TestTheEmptyAnswer(unittest.TestCase):
    """
    «لا اعتراض» هو الجواب **الأكثر وقوعاً** في مسودّة سليمة.

    ولهذا يُختبر اختباراً كامل الأهلية لا هامشياً: لو عاملناه عطلاً أو نقصاً،
    لدفعنا المراجع إلى اختلاق اعتراضات ليُرضي الأداة — وهو الخطر الذي يقوم
    عليه هذا الملف كله. والموجّه ينصّ على ذلك صراحةً، وهذه الاختبارات تُثبّت
    الطرفين: الموجّه والقارئ.
    """

    def test_empty_array_is_a_valid_answer(self):
        outcome = parse_review("[]", DRAFT, BRIEF, EVIDENCE)
        self.assertEqual(outcome.findings, [])
        self.assertEqual(outcome.dropped, 0)
        self.assertTrue(outcome.clean)
        self.assertIn("لا اعتراض", outcome.summary())

    def test_empty_array_in_prose_fences_or_markers(self):
        for text in ("[ ]", "لا اعتراض.\n[]\n", "```json\n[]\n```", f"{REVIEW_BEGIN}[] {REVIEW_END}"):
            with self.subTest(text=text):
                outcome = parse_review(text, DRAFT, BRIEF, EVIDENCE)
                self.assertEqual(outcome.findings, [])
                self.assertTrue(outcome.clean)

    def test_summarize_of_an_empty_answer_is_clean_and_arabic(self):
        payload = summarize([], 0)
        self.assertTrue(payload["clean"])
        self.assertEqual(payload["error_count"], 0)
        self.assertEqual(payload["notice_count"], 0)
        self.assertEqual(payload["findings"], [])
        self.assertIn("لا اعتراض", payload["summary"])
        json.dumps(payload, ensure_ascii=False)

    def test_the_prompt_declares_the_empty_answer(self):
        """الموجّه هو النصف الآخر للضمان: بلا هذا النصّ يختلق النموذج اعتراضاً."""
        prompt = build_review_prompt(BRIEF, DRAFT, EVIDENCE)
        self.assertIn("إن لم تجد اعتراضاً فلا تخترع واحداً", prompt)
        self.assertIn("[]", prompt)

    def test_all_objections_unverifiable_is_not_the_same_as_no_objections(self):
        """
        🔑 الفرق الذي يجب أن يراه المحامي.

        المراجع اتّهم ولم يُثبت: `clean` تبقى صحيحة (لا عيب ثابت)، لكن
        `dropped` تفضح أنه حاول. وسكوت المراجع رضاً ليس كسكوته عجزاً.
        """
        outcome = parse(
            finding(quote=Q_FORGED, basis=""),
            finding(basis=B_FORGED),
        )
        self.assertEqual(outcome.findings, [])
        self.assertTrue(outcome.clean)
        self.assertEqual(outcome.dropped, 2)
        self.assertIn("أُسقط", outcome.summary())


# ==============================================================================
# ٦. العرض للمحامي
# ==============================================================================


class TestSummarize(unittest.TestCase):
    """شكل ما يُبَثّ إلى الواجهة — JSON صالح، والحدّ فيه هو حدّ التسليم."""

    def test_shape_is_json_safe(self):
        outcome = parse(
            finding(),
            finding(kind="strength", severity="notice", quote=Q_ARTICLE, basis=""),
        )
        payload = summarize(outcome.findings, outcome.dropped)

        self.assertIsInstance(json.dumps(payload, ensure_ascii=False), str)
        self.assertEqual(
            set(payload["findings"][0]),
            {"kind", "severity", "message", "quote", "basis"},
        )
        self.assertEqual(payload["error_count"], 1)
        self.assertEqual(payload["notice_count"], 1)
        self.assertFalse(payload["clean"])
        self.assertEqual(payload["dropped"], 0)

    def test_clean_is_true_exactly_when_there_is_no_error(self):
        with_error = summarize(parse(finding()).findings)
        self.assertFalse(with_error["clean"])
        self.assertEqual(with_error["error_count"], 1)

        notice_only = summarize(parse(finding(severity="notice")).findings)
        self.assertTrue(notice_only["clean"])
        self.assertEqual(notice_only["notice_count"], 1)
        self.assertEqual(notice_only["error_count"], 0)

        nothing = summarize([])
        self.assertTrue(nothing["clean"])

    def test_dropped_is_passed_through_and_mentioned_in_the_summary(self):
        payload = summarize([], dropped=3)
        self.assertEqual(payload["dropped"], 3)
        self.assertIn("3", payload["summary"])
        self.assertIn("أُسقط", payload["summary"])

    def test_the_outcome_summary_matches_summarize(self):
        """دالّة عرض واحدة، فلا يفترق نصّان للمحامي عن الحصيلة نفسها."""
        outcome = parse(finding(), finding(quote=Q_FORGED))
        self.assertEqual(
            outcome.summary(),
            summarize(outcome.findings, outcome.dropped)["summary"],
        )

    def test_default_dropped_is_zero(self):
        self.assertEqual(summarize([])["dropped"], 0)


# ==============================================================================
# ٧. الموجّه
# ==============================================================================


class TestBuildReviewPrompt(unittest.TestCase):
    """الموجّه هو النصف الأول من العقد: ما يُطلب هو ما يُفحص لاحقاً."""

    def setUp(self):
        self.prompt = build_review_prompt(BRIEF, DRAFT, EVIDENCE)

    def test_carries_all_three_inputs(self):
        self.assertIn(BRIEF, self.prompt)
        self.assertIn(DRAFT, self.prompt)
        self.assertIn(ARTICLE_TEXT, self.prompt)

    def test_demands_the_opposing_role(self):
        """بلا طلب العداء صراحةً يكتب النموذج تقريراً لطيفاً بلا اعتراض واحد."""
        self.assertIn("الخصم", self.prompt)
        self.assertIn("لا أن تمدح", self.prompt)

    def test_demands_bare_json_only(self):
        self.assertIn("مصفوفة JSON وحدها", self.prompt)
        self.assertIn("لا نثر قبلها ولا بعدها", self.prompt)

    def test_names_every_kind_and_severity(self):
        for kind in KINDS:
            with self.subTest(kind=kind):
                self.assertIn(f"`{kind}`", self.prompt)
        for severity in ("error", "notice"):
            with self.subTest(severity=severity):
                self.assertIn(f"`{severity}`", self.prompt)

    def test_demands_verbatim_quotes_and_bases(self):
        self.assertIn("حرفاً بحرف", self.prompt)
        self.assertIn("quote", self.prompt)
        self.assertIn("basis", self.prompt)

    def test_forbids_inventing_a_basis(self):
        self.assertIn("ولا تختلق سنداً", self.prompt)

    def test_forbids_arithmetic(self):
        """المراجع لا يحسب: يشير إلى الرقم المشكوك فيه لا إلى نتيجته."""
        self.assertIn("لا تحسب", self.prompt)

    def test_separates_blocking_from_informational(self):
        self.assertIn("يمنع التسليم", self.prompt)
        self.assertIn("لا يمنع", self.prompt)

    def test_mentions_the_markers_without_requiring_them(self):
        self.assertIn(REVIEW_BEGIN, self.prompt)
        self.assertIn(REVIEW_END, self.prompt)

    def test_empty_inputs_do_not_crash(self):
        prompt = build_review_prompt("", "", "")
        self.assertIn("لا موجز.", prompt)
        self.assertIn("لا مسودّة.", prompt)
        self.assertIn("لا مقتطفات.", prompt)

    def test_is_deterministic(self):
        self.assertEqual(self.prompt, build_review_prompt(BRIEF, DRAFT, EVIDENCE))


# ==============================================================================
# ٨. ما يفعله `quote_in_text` فعلاً
# ==============================================================================


class TestQuoteInTextBehaviour(unittest.TestCase):
    """
    حدود الحكم الذي يقرّر مصير كل اعتراض — **مفحوصة بالتشغيل لا بالافتراض**.

    وحدود الحكم تصير حدود الأداة، فتُثبَّت هنا صريحةً: ما تتسامح فيه
    `quote_in_text` وما لا تتسامح فيه، حتى لا يظنّ قارئ التقرير أن اجتياز
    الفحص أكثر ممّا هو.
    """

    def test_diacritics_and_spacing_are_folded(self):
        """التسامح مقصود: النموذج لا يعيد التشكيل ولا فواصل الأسطر."""
        self.assertTrue(quote_in_text("المُستَأجِر  عن\nسداد الاجرة", DRAFT))
        self.assertTrue(quote_in_text("تاخر المستاجر عن سداد الاجره", DRAFT))

    def test_punctuation_is_erased_so_a_comma_cannot_be_verified(self):
        """
        ⚠️ حدّ حقيقي: الترقيم يُمحى قبل المطابقة.

        فالفاصلة لا تُثبَّت ولا تُنفى: اقتباس بلا فاصلة يجتاز الفحص على نصّ
        فيه فاصلة. وهي في الأغلب فرق رسم لا يغيّر المعنى — وهذا سبب التسامح
        أصلاً — لكنها قد تفرق: «لا، يفسخ» ليست «لا يفسخ». فالفحص يمنع
        **التأليف**، ولا يمنع **القراءة الخاطئة**، ولذلك يُلزَم المراجع
        بالقراءة ولا يُكتفى باجتيازه.
        """
        draft = "قال المستأجر: لا، يفسخ العقد للمالك فوراً"
        self.assertNotIn("لا يفسخ العقد للمالك فوراً", draft)
        self.assertTrue(quote_in_text("لا يفسخ العقد للمالك فوراً", draft))

    def test_word_order_still_matters(self):
        """التسامح في الرسم لا في الترتيب — وإلا صار الفحص بلا معنى."""
        self.assertFalse(quote_in_text("عن سداد الأجرة تأخّر المستأجر", DRAFT))

    def test_a_date_alone_is_too_short_to_be_a_quote(self):
        """
        ⚠️ ومفاجأة عملية تخصّ نوع `arithmetic` بالذات.

        «٢٠٢٣/٠١/٠١» تُطبَّع إلى «2023 01 01» — عشرة محارف — فتُرفض
        **بالعتبة** لا بالغياب. فاعتراض على تاريخ لا يجوز أن يُسند إلى الرقم
        وحده، بل يقتبس كلمات حوله. ولهذا يطلب الموجّه من المراجع أن يقول أيّ
        رقم يشكّ فيه ولماذا، لا أن يقتبس الرقم.
        """
        draft_with_date = "بموجب العقد المؤرّخ في ٢٠٢٣/٠١/٠١ بين الطرفين."
        self.assertEqual(normalize("٢٠٢٣/٠١/٠١"), "2023 01 01")
        self.assertLess(len(normalize("٢٠٢٣/٠١/٠١")), MIN_QUOTE_CHARS)
        self.assertFalse(quote_in_text("٢٠٢٣/٠١/٠١", draft_with_date))
        self.assertTrue(quote_in_text("٢٠٢٣/٠١/٠١", draft_with_date, min_quote_chars=1))
        self.assertTrue(quote_in_text("العقد المؤرّخ في ٢٠٢٣/٠١/٠١", draft_with_date))

    def test_arabic_digits_fold_to_latin(self):
        """«٧٥» و«75» الرقم نفسه — فلا يُرفض اقتباس سليم لاختلاف رسم الرقم."""
        self.assertTrue(quote_in_text("المادة 75 من قانون المعاملات المدنية", DRAFT))

    def test_empty_inputs_never_match(self):
        self.assertFalse(quote_in_text("", DRAFT))
        self.assertFalse(quote_in_text("نصّ طويل بما يكفي للمطابقة", ""))


# ==============================================================================
# ٩. المسار كاملاً
# ==============================================================================


class TestEndToEnd(unittest.TestCase):
    """من مخرج المراجع الخام إلى ما يُبَثّ للمحامي."""

    def test_good_bad_and_repeated_objections_together(self):
        outcome = parse(
            finding(),  # صالح
            finding(kind="unsupported", severity="notice", quote=Q_TERM, basis=B_NOTICE),
            finding(),  # تكرار للأول — يُطوى
            finding(quote=Q_FORGED, basis=B_MONTHS),  # اقتباس مؤلَّف
            finding(quote=Q_PAID, basis=B_FORGED),  # سند مؤلَّف
        )
        self.assertEqual(len(outcome.findings), 2)
        self.assertEqual(outcome.dropped, 2)

        payload = summarize(outcome.findings, outcome.dropped)
        self.assertFalse(payload["clean"])
        self.assertEqual(len(payload["findings"]), 2)
        self.assertIn("يمنع التسليم", payload["summary"])
        self.assertIn("أُسقط", payload["summary"])
        json.dumps(payload, ensure_ascii=False)

    def test_a_clean_reviewer_leaves_the_draft_deliverable(self):
        outcome = parse_review(as_json(), DRAFT, BRIEF, EVIDENCE)
        payload = summarize(outcome.findings, outcome.dropped)
        self.assertTrue(payload["clean"])
        self.assertEqual(payload["findings"], [])
        self.assertEqual(payload["dropped"], 0)
        self.assertIn("لا اعتراض", payload["summary"])

    def test_notices_alone_do_not_block_delivery(self):
        """
        وهذا هو الدرس المدفوع الثمن في `language_audit.py`: الملاحظة تُعرَض
        ولا تمنع. ولو منع كل اعتراض التسليم لصار التقرير جداراً يُتجاهَل.
        """
        outcome = parse(
            finding(kind="strength", severity="notice", quote=Q_ARTICLE, basis=""),
            finding(kind="omission", severity="notice", quote=Q_TERM, basis=B_TERM),
        )
        payload = summarize(outcome.findings, outcome.dropped)
        self.assertTrue(payload["clean"])
        self.assertEqual(payload["notice_count"], 2)
        self.assertIn("لا مانع من التسليم", payload["summary"])


# ==============================================================================
# ١٠. ضمانات على الوحدة نفسها
# ==============================================================================


class TestModuleGuarantees(unittest.TestCase):
    """ضمانات معمارية — كـ`citations.py`: بلا تبعيات ثقيلة وبلا شبكة وبلا حالة."""

    def _source(self) -> str:
        return pathlib.Path(review.__file__).read_text(encoding="utf-8")

    def test_imports_are_stdlib_only_plus_citations(self):
        """
        الضمان الذي يجعل هذا الملف يعمل بلا شبكة ولا مفتاح API.

        والفحص على **المصدر** لا على أثر التشغيل: أدقّ وأبعد عن الهشاشة.
        """
        imported = set(
            _re.findall(
                r"^(?:from|import)\s+([A-Za-z_][\w\.]*)", self._source(), _re.MULTILINE
            )
        )
        allowed = {"__future__", "json", "dataclasses", "typing", "citations"}
        self.assertTrue(imported <= allowed, f"استيرادات: {sorted(imported - allowed)}")

    def test_no_environment_network_or_output(self):
        """الوحدة دالّة صافية: لا تُقرأ بيئة، ولا تُفتح شبكة، ولا تُطبَع نجاحات."""
        source = self._source()
        for forbidden in ("os.environ", "getenv", "requests.", "urllib", "socket", "http", "print("):
            self.assertNotIn(forbidden, source, f"الوحدة تحتوي «{forbidden}»")

    def test_the_threshold_is_the_citations_threshold(self):
        """عتبة واحدة للمشروع: لو اختلفت لقُبل اقتباس في ملف ورُفض في آخر."""
        self.assertEqual(MIN_QUOTE_CHARS, citations.MIN_QUOTE_CHARS)
        self.assertEqual(review.MIN_QUOTE_CHARS, citations.MIN_QUOTE_CHARS)

    def test_markers_are_unusual_in_legal_prose(self):
        self.assertIn("[[", REVIEW_BEGIN)
        self.assertIn("[[", REVIEW_END)
        self.assertNotIn(REVIEW_BEGIN, DRAFT)
        self.assertNotIn(REVIEW_END, BRIEF)

    def test_finding_is_immutable(self):
        item = parse(finding()).findings[0]
        with self.assertRaises(Exception):
            item.message = "غير ذلك"  # type: ignore[misc]

    def test_the_dataclass_defaults_basis_to_empty(self):
        item = ReviewFinding(kind="fact", severity="error", message="خ", quote=Q_MONTHS)
        self.assertEqual(item.basis, "")

    def test_outcome_defaults_are_independent(self):
        first, second = ReviewOutcome(), ReviewOutcome()
        first.findings.append("x")  # type: ignore[arg-type]
        self.assertEqual(second.findings, [])
        self.assertEqual(second.dropped, 0)

    def test_repeated_calls_do_not_share_state(self):
        """
        🔑 وهذا هو الاختبار الذي رجّح `ReviewOutcome` على `last_dropped()`.

        نداءان بنفس المدخلات يعطيان نفس الحصيلة، وبينهما نداء آخر — فلا عدّاد
        في حالة الوحدة يُقرأ من النداء الخطأ. ولو كان العدّاد عامّاً لكان
        الجواب هنا مرتهناً **بترتيب النداءات** لا بمدخلاتها.
        """
        text = as_json(finding(), finding(quote=Q_FORGED))
        first = parse_review(text, DRAFT, BRIEF, EVIDENCE)
        empty = parse_review("[]", DRAFT, BRIEF, EVIDENCE)
        third = parse_review(text, DRAFT, BRIEF, EVIDENCE)

        self.assertEqual(empty.dropped, 0)
        self.assertEqual(first.dropped, 1)
        self.assertEqual(third.dropped, first.dropped)
        self.assertEqual(
            [item.quote for item in first.findings],
            [item.quote for item in third.findings],
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
