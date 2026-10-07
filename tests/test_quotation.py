"""
اختبارات فصل النقل الحرفي عن الصياغة — أهذا نصّ القانون أم صياغة الكاتب؟
=============================================================================

تشغيل:
    python -m unittest tests.test_quotation

حتمية بالكامل: بلا شبكة، وبلا نموذج، وبلا قاعدة بيانات، وبلا قرص. ولا تحتاج
`fake_deps` لأن `quotation` وحدة نقية كـ`citations.py`: كل حكمها من مدخلاتها،
والنصّ الذي يُطابَق به الاقتباس **يُحقن** في `source_of` فلا تحتاج أرشيفاً.

وأهمّ اختبار في الملف هو ``test_a_comma_that_inverts_the_meaning_is_not_accepted``
— وهو العيب الذي جاء الملف له، مُشاهَداً بالتشغيل:

    quote_in_text("لا يفسخ العقد للمالك فوراً", "…لا، يفسخ العقد للمالك فوراً")
    == True   ← والفاصلة تقلب المعنى

ويليه في الأهمّية ``test_strict_match_and_quote_in_text_disagree_on_the_comma_case``:
اختبار يقيس **الاختلاف بين الوحدتين بالاسم**، حتى لا يجمعهما أحد بعد اليوم
فيَذوب العيب صامتاً.

والثالث ``test_an_attributed_summary_is_a_notice_not_an_error``: يثبّت أن
الملخّص بلا علامات اقتباس **ملاحظة لا خطأ** — فالمنهيّ عنه تقديم كلام الكاتب
على أنه كلام القانون، لا تلخيصه.
"""

from __future__ import annotations

import json
import pathlib
import re as _re
import unittest

import quotation
from citations import quote_in_text
from quotation import (
    ERROR_KINDS,
    FINDING_KINDS,
    KIND_UNFAITHFUL_QUOTE,
    KIND_UNKNOWN_SOURCE,
    KIND_UNQUOTED_ATTRIBUTION,
    KIND_UNREFERENCED_QUOTE,
    SEVERITY_ERROR,
    SEVERITY_NOTICE,
    MatchKind,
    Passage,
    Presentation,
    PresentationFinding,
    StrictMatch,
    check_presentation,
    classify,
    strict_match,
    summarize,
)

# ==============================================================================
# بيانات الاختبار — النصوص الحقيقية من العيب، لا نصوص متخيَّلة
# ==============================================================================

#: العبارة التي تقلب فيها الفاصلة المعنى: «لا، يفسخ» ليست «لا يفسخ».
COMMA_QUOTE = "لا يفسخ العقد للمالك فوراً"
#: المصدر كما ورد في العيب: الفاصلة موجودة، والاقتباس أسقطها.
COMMA_SOURCE = "…لا، يفسخ العقد للمالك فوراً"

#: نصّ مادة العمل المستعمل في أكثر اختبارات العرض.
NOTICE_CLAUSE = "لا يجوز إنهاء عقد العمل إلا بإخطار كتابي"
#: نصّ فيه كلمة تختلف بكلمة، لقياس `WORD_CHANGED` وتسميته.
WAGE_CLAUSE = "يلتزم المستأجر بسداد الأجرة الشهرية في المواعيد المتفق عليها"
WAGE_CLAUSE_CHANGED = "يلتزم المستأجر بسداد الأجرة اليومية في المواعيد المتفق عليها"


def source_of_nothing(reference: str) -> str:
    """أرشيف لم يُنتج شيئاً — الحالة التي تُعرَض ملاحظةً لا خطأً."""
    return ""


# ==============================================================================
# ١. المطابقة الصارمة
# ==============================================================================


class TestStrictMatch(unittest.TestCase):
    """ما يقبله الملف من فرق، وما يرفضه — والفرق هو كل الفائدة."""

    def test_a_comma_that_inverts_the_meaning_is_not_accepted(self):
        """
        🔑 **العيب الذي جاء الملف له — مثبَّتاً باسمه هنا.**

        «لا يفسخ العقد» ليست «لا، يفسخ العقد للمالك»: الفاصلة تنقل النفي من
        الفعل إلى ما قبله، فينقلب المعنى. و`quote_in_text` يقبل هذا الاقتباس
        لأن التطبيع يمحو الفاصلة (انظر الصنف التالي). وهذا الملف **لا يقبله**،
        ويسمّي الفاصلة بعينها — فإن عاد التسامح يوماً، سقط هذا الاختبار.
        """
        result = strict_match(COMMA_QUOTE, COMMA_SOURCE)

        self.assertEqual(result.kind, MatchKind.PUNCTUATION_CHANGED)
        self.assertNotEqual(result.kind, MatchKind.EXACT)
        self.assertNotEqual(result.kind, MatchKind.FORMATTING_ONLY)
        self.assertFalse(result.accepted())
        # ويُسمّى المتغيّر بعينه: الفاصلة نفسها، لا «اختلاف في الترقيم» مبهماً.
        self.assertTrue(result.changed, "لم يُسمَّ الترقيم المخالف")
        self.assertIn("،", " ".join(result.changed))

    def test_a_punctuation_difference_is_named_and_is_not_a_word_change(self):
        """
        الفرق في **الترقيم وحده** لا يُقرأ «كلمة تغيّرت».

        والفرق بين الحالتين هو الفرق بين ما يُقال للكاتب: «أسقطتَ فاصلة»
        و«غيّرتَ كلمة». ومن خلطهما اتّهم الكاتب بتبديل نصّ لم يبدّله.
        """
        result = strict_match("يجوز إنهاء عقد العمل.", "يجوز إنهاء عقد العمل؛")
        self.assertEqual(result.kind, MatchKind.PUNCTUATION_CHANGED)
        self.assertIn("؛", " ".join(result.changed))

    def test_whitespace_only_difference_is_exact(self):
        """المسافات فواصل أسطر في الاستخراج لا كلمات — فتُطوى وحدها."""
        result = strict_match("لا  يفسخ\nالعقد   للمالك", "لا يفسخ العقد للمالك")
        self.assertEqual(result.kind, MatchKind.EXACT)
        self.assertTrue(result.accepted())
        self.assertEqual(result.changed, ())

    def test_spacing_around_punctuation_is_a_formatting_difference(self):
        """
        ⚠️ فراغٌ ملاصق لعلامة ترقيم **ليس تغييراً في الترقيم**.

        «لا، يفسخ» و«لا،يفسخ» ترقيمهما واحد؛ ولو عُدّ الفراغ فرقاً لخرج
        `PUNCTUATION_CHANGED` على مسافة — **إنذار كاذب عن اقتباس أمين**.
        """
        result = strict_match("لا، يفسخ العقد", "لا،يفسخ العقد")
        self.assertEqual(result.kind, MatchKind.EXACT)
        self.assertTrue(result.accepted())

    def test_diacritics_and_tatweel_are_formatting_only(self):
        """التشكيل والكشيدة زخرفة: النموذج لا يعيدهما، ورفضهما إبطال لكل مسودّة."""
        without = strict_match("المستأجر عن سداد", "المُستَأجِر عن سداد")
        with_tatweel = strict_match("المادة 43 من القانون", "المــادة 43 من القانون")

        for result in (without, with_tatweel):
            with self.subTest(quote=result.quote):
                self.assertEqual(result.kind, MatchKind.FORMATTING_ONLY)
                self.assertTrue(result.accepted())

    def test_arabic_indic_digits_are_formatting_only(self):
        """«٤٣» و«43» الرقم نفسه — فرق رسم لا فرق كلمة."""
        result = strict_match("المادة 43", "المادة ٤٣")
        self.assertEqual(result.kind, MatchKind.FORMATTING_ONLY)
        self.assertTrue(result.accepted())

    def test_the_two_digit_scripts_fold_on_both_sides(self):
        """الطيّ على **الجانبين**: اقتباس بأرقام هندية ومصدر لاتيني يُقبل أيضاً."""
        self.assertTrue(strict_match("المادة ٤٣", "المادة 43").accepted())

    def test_a_changed_word_is_word_changed_and_names_the_words(self):
        """كلمة تبدّلت = `WORD_CHANGED`، وتُسمّى الكلمتان: ما في الاقتباس وما في المصدر."""
        result = strict_match(WAGE_CLAUSE_CHANGED, WAGE_CLAUSE)

        self.assertEqual(result.kind, MatchKind.WORD_CHANGED)
        self.assertFalse(result.accepted())
        named = " ".join(result.changed)
        self.assertIn("اليومية", named)
        self.assertIn("الشهرية", named)

    def test_a_quotation_not_present_at_all_is_missing(self):
        """نصّ لا مقابلة له في المصدر: `MISSING` — ولا يُسمّى فيه تغيير لأنه لا مقابل له."""
        result = strict_match(
            "يلتزم الطرف الثاني بتسليم المستندات",
            "لا يجوز إنهاء عقد العمل إلا بإخطار كتابي",
        )
        self.assertEqual(result.kind, MatchKind.MISSING)
        self.assertFalse(result.accepted())
        self.assertEqual(result.source_span, "")
        self.assertEqual(result.changed, ())

    def test_the_source_span_shows_the_raw_source_wording(self):
        """
        `source_span` بعرض **رسم المصدر** لا المطويّ: به يرى المحامي بمَ قُوبل
        الاقتباس. ولو عُرض المطويّ لبحث في مسودّته عن نصّ ليس فيها.
        """
        digits = strict_match("المادة 246", "المادة ٢٤٦ من قانون المعاملات")
        comma = strict_match(COMMA_QUOTE, COMMA_SOURCE)

        self.assertEqual(digits.source_span, "المادة ٢٤٦")
        self.assertEqual(comma.source_span, "لا، يفسخ العقد للمالك فوراً")

    def test_accepted_is_only_exact_and_formatting_only(self):
        """
        ⚠️ **جدول القبول: حالتان تُقبلان وثلاث لا تُقبل.** وهي الضمانة التي
        تجعل «تغيير الفاصلة» و«تغيير الكلمة» و«الغياب» كلها مرفوضة معاً.
        """
        accepted = {MatchKind.EXACT, MatchKind.FORMATTING_ONLY}
        for kind in MatchKind:
            with self.subTest(kind=kind.value):
                result = StrictMatch(kind=kind, quote="نصّ")
                self.assertEqual(result.accepted(), kind in accepted)

    def test_punctuation_at_the_edge_of_the_quotation_is_compared(self):
        """
        ⚠️ **عطب وقع أثناء بناء هذا الملف، ويُثبَّت هنا فلا يعود.**

        أول بناء قارن الترقيم **بين الكلمات** وحده، فسقط فرقٌ حقيقي: الاقتباس
        «…العمل.» والمصدر «…العمل؛» — الكلمات هي هي، والترقيم المخالف **بعد**
        آخر كلمة لا بينها، فخرج `PUNCTUATION_CHANGED` بلا تسمية. والفرق بين
        النقطة والفاصلة المنقوطة فرقٌ يُرى، فلا يُبلَّغ عنه بلا اسم.
        """
        result = strict_match("يجوز إنهاء عقد العمل.", "يجوز إنهاء عقد العمل؛")
        self.assertEqual(result.kind, MatchKind.PUNCTUATION_CHANGED)
        self.assertIn("؛", " ".join(result.changed))

    def test_punctuation_of_the_source_after_the_excerpt_is_not_a_difference(self):
        """
        ⚠️ **والحدّ المقابل، وهو الأهمّ: اقتطاعٌ سليم لا يُنذر.**

        الاقتباس ينتهي عند كلمة، وفاصلةُ المصدر **بعده** ليست من المقتبس بل من
        بقيّة الجملة. فلو قُورنت لخرج `PUNCTUATION_CHANGED` على كل اقتطاع سليم
        — **إنذار دائم**، وهو أسوأ ما في أداة كهذه.
        """
        result = strict_match(
            "لا يجوز إنهاء عقد العمل",
            "لا يجوز إنهاء عقد العمل، ويجب تسليم العامل مستحقاته عند انتهاء العلاقة",
        )
        self.assertEqual(result.kind, MatchKind.EXACT)
        self.assertTrue(result.accepted())

    def test_leading_punctuation_claimed_by_the_quote_is_reported(self):
        """وعلامة ترقيم في الاقتباس لا مقابل لها في المصدر تُسمّى ولا تُمحى."""
        result = strict_match("، نصّ المادة", "نصّ المادة")
        self.assertEqual(result.kind, MatchKind.PUNCTUATION_CHANGED)
        self.assertIn("،", " ".join(result.changed))

    def test_a_short_quotation_is_still_judged(self):
        """
        ⚠️ عتبة `MIN_QUOTE_CHARS` **عتبة دليل** في `citations.py` (أقلّ طول
        يُعدّ سنداً)، لا شرطاً في «أهذا نقل حرفي؟». فلا تُستورد هنا: العبارة
        القصيرة بين علامتي اقتباس تبقى نقلَ نصّ يُفحص، ولها مصدر أو ليس لها.
        """
        self.assertTrue(strict_match("بإخطار كتابي", NOTICE_CLAUSE).accepted())
        self.assertEqual(
            strict_match("بإخطار شفهي", NOTICE_CLAUSE).kind, MatchKind.WORD_CHANGED
        )

    def test_empty_inputs_are_missing(self):
        """لا انهيار على الفراغ: لا مصدر ولا اقتباس = `MISSING`."""
        for quote, source in (("", NOTICE_CLAUSE), (NOTICE_CLAUSE, ""), ("", ""), ("   ", " ")):
            with self.subTest(quote=quote, source=source):
                self.assertEqual(strict_match(quote, source).kind, MatchKind.MISSING)

    def test_the_same_inputs_always_give_the_same_outcome(self):
        """حتمية: لا حالة على مستوى الوحدة، فالمدخل نفسه يُعطي النتيجة نفسها."""
        first = strict_match(COMMA_QUOTE, COMMA_SOURCE)
        _unused = strict_match(WAGE_CLAUSE_CHANGED, WAGE_CLAUSE)
        third = strict_match(COMMA_QUOTE, COMMA_SOURCE)
        self.assertEqual(first, third)


# ==============================================================================
# ٢. الفرق بين المطابقة الصارمة والمطابقة المتسامحة — مثبَّتاً بالاسم
# ==============================================================================


class TestTheTwoMatchersMustNotConverge(unittest.TestCase):
    """
    `strict_match` و`quote_in_text` **يختلفان عن قصد**، والاختلاف مُثبَّت هنا.

    ⚠️ ولو جُمعا يوماً (باستدعاء `normalize` داخل `strict_match` مثلاً) لسقط
    هذان الاختباران — **وهذا هو الغرض**: لا يذوب العيب صامتاً.
    """

    def test_strict_match_and_quote_in_text_disagree_on_the_comma_case(self):
        """
        🔑 **نفس المدخل: المتسامح يقبل، والصارم يرفض.**

        ولا يقال إن أحدهما «خطأ»: لكلٍّ سؤاله. `quote_in_text` يسأل «أهذا
        موجود؟» فيمنع التأليف، و`strict_match` يسأل «أهذا منقول كما هو؟»
        فيمنع تغيير المعنى. والمسودّة تحتاج الجوابين معاً.
        """
        loose = quote_in_text(COMMA_QUOTE, COMMA_SOURCE)
        strict = strict_match(COMMA_QUOTE, COMMA_SOURCE).accepted()

        self.assertTrue(loose, "المطابقة المتسامحة تغيّرت — راجع citations.py")
        self.assertFalse(strict, "المطابقة الصارمة تسامحت في فاصلة تقلب المعنى")
        self.assertNotEqual(
            loose,
            strict,
            "المطابقتان اتّفقتا على حالة الفاصلة — وهذا ذوبان العيب الذي جاء الملف له",
        )

    def test_the_loose_matcher_erases_the_comma_and_the_strict_one_names_it(self):
        """
        الفرق مُفسَّر لا مُدَّعى: `normalize` يمحو الترقيم كله، فالاقتباس بلا
        فاصلة يوجد في النصّ الذي فيه فاصلة. أما `strict_match` فيسمّي الفاصلة.
        """
        from citations import normalize

        self.assertNotIn("،", normalize(COMMA_SOURCE))
        self.assertIn("،", " ".join(strict_match(COMMA_QUOTE, COMMA_SOURCE).changed))

    def test_the_module_does_not_import_or_call_the_loose_normalizer(self):
        """
        ⚠️ **فحص بالمصدر لا بالسلوك**: استيراد `normalize` هنا يُذيب الحدّ بين
        الوحدتين. والفحص نصّي لأنه لا يمكن إثبات «لا يستدعي» بالتشغيل.
        """
        source = pathlib.Path(quotation.__file__).read_text(encoding="utf-8")

        self.assertNotIn("from citations", source)
        self.assertNotIn("import citations", source)
        self.assertNotIn("citations.normalize(", source)


# ==============================================================================
# ٣. حدود معلنة — تُثبَّت في اختبار فلا تتبدّل صامتة
# ==============================================================================


class TestDeclaredLimits(unittest.TestCase):
    """
    الحدود المعلنة في صدر `quotation.py` — كلٌّ منها في اختبار.

    ⚠️ والقاعدة: الحدّ الذي لا يُثبَّت في اختبار **يتبدّل صامتاً**، فيقرأ
    القارئ في التوثيق حدّاً وينفّذ الكود غيره. والحدّ المعلن يُقرأ مع النتيجة.
    """

    def test_a_quotation_may_start_inside_a_source_word(self):
        """
        ⚠️ **حدّ الكلمة لا يُفحص** (الحدّ الأول): الشائع في الصياغة القانونية أن
        يُقتطع الاقتباس بعد واو العطف المتّصلة («ويجب…» ← «يجب…»)، ورفضه إنذارٌ
        عن اقتباس أمين — **وأداة تُنذر دائماً لا تُقرأ**.
        """
        result = strict_match(
            "يجب تسليم العامل مستحقاته",
            "ويجب تسليم العامل مستحقاته عند انتهاء العلاقة",
        )
        self.assertEqual(result.kind, MatchKind.EXACT)
        self.assertTrue(result.accepted())

    def test_a_heavy_paraphrase_is_missing_not_word_changed(self):
        """
        ⚠️ **حدّ النصف** (الحدّ الثالث): ما دون نصف الكلمات المتطابقة لا تُعرف
        له مقابلة، فيُقال `MISSING` لا `WORD_CHANGED`.

        والفرق **في التفسير لا في النتيجة**: الحالتان مرفوضتان معاً — ولا
        يُنسب إلى الاقتباس مقابلٌ لم يثبت، فتُسمّى «كلمات مخالفة» بلا مرساة.
        """
        result = strict_match(
            "عقد العمل المبرم بين الطرفين على أن يُنفَّذ بحسن نية",
            "لا يجوز إنهاء عقد العمل إلا بإخطار كتابي",
        )
        self.assertEqual(result.kind, MatchKind.MISSING)
        self.assertFalse(result.accepted())

    def test_an_unclosed_quotation_is_not_a_quotation(self):
        """
        ⚠️ **الاقتباس غير المغلَق يُهمَل** (الحدّ الرابع): لو قُرئ اقتباساً لصار
        كل ما بعده منقولاً إلى آخر المستند — فيُنذر عن مسودّة سليمة.
        """
        passages = classify("وتنص المادة ٤٣ على: «نصّ المادة كما هو")
        self.assertEqual([p for p in passages if p.presentation is Presentation.QUOTED], [])
        self.assertEqual([p.presentation for p in passages], [Presentation.ATTRIBUTED])


# ==============================================================================
# ٤. العرض — الاقتباس والنسبة والنثر
# ==============================================================================


class TestClassify(unittest.TestCase):
    """أيُقدَّم النصّ منقولاً أم منسوباً أم نثراً؟"""

    def test_every_quotation_marker_is_found(self):
        """
        🔑 **علامات الاقتباس الأربع** («…» · "…" · '…' · ﴿…﴾) — والنموذج
        يبدّل بينها بلا قاعدة، فما لا يُقرأ اقتباساً يمرّ بلا فحص.
        """
        markers = (
            ("«", "»"),
            ("\u201c", "\u201d"),  # "…"
            ("\u2018", "\u2019"),  # '…'
            ("\ufd3e", "\ufd3f"),  # ﴿…﴾
            ('"', '"'),            # علامة ASCII كما تخرج من بعض النماذج
        )
        for opener, closer in markers:
            with self.subTest(marker=opener):
                draft = f"وتنص المادة ٤٣ على {opener}{NOTICE_CLAUSE}{closer}."
                passages = classify(draft)
                self.assertEqual(len(passages), 1)
                self.assertIs(passages[0].presentation, Presentation.QUOTED)
                self.assertEqual(passages[0].text, NOTICE_CLAUSE)
                self.assertEqual(passages[0].reference, "المادة ٤٣")

    def test_an_unquoted_article_statement_is_attributed(self):
        """
        🔑 **بلا علامات اقتباس = صياغة الكاتب**، وهي الحالة التي كان القارئ
        يعجز عن تمييزها من نصّ المادة.
        """
        passages = classify(f"وتنص المادة ٤٣ على أنه {NOTICE_CLAUSE}.")

        self.assertEqual(len(passages), 1)
        self.assertIs(passages[0].presentation, Presentation.ATTRIBUTED)
        self.assertEqual(passages[0].reference, "المادة ٤٣")
        self.assertIn(NOTICE_CLAUSE, passages[0].text)

    def test_each_quotation_is_paired_with_its_own_reference(self):
        """اقتباسان ومرجعان في جملة واحدة: لكل اقتباس مرجعه، لا مرجع جاره."""
        draft = (
            "وتنص المادة ٤٣ على: «لا يجوز إنهاء عقد العمل إلا بإخطار كتابي» "
            "وتنص المادة ٤٢ على: «ينتهي العقد بمضي مدته»."
        )
        quoted = [p for p in classify(draft) if p.presentation is Presentation.QUOTED]

        self.assertEqual([p.reference for p in quoted], ["المادة ٤٣", "المادة ٤٢"])
        self.assertEqual(quoted[1].text, "ينتهي العقد بمضي مدته")

    def test_a_quotation_does_not_steal_a_reference_from_the_next_sentence(self):
        """
        🔑 **المرجع يُقرن بجملته، لا بجواره.**

        الاقتباس الأول في جملة لا مرجع فيها، والثاني في جملة فيها المرجع. ولو
        أخذ الأولُ مرجعَ الثاني (لأنه أقرب عدداً) لَفُحص نصٌّ على مادة ليست له،
        وبقي نصّ المادة بلا مرجع — **حكمٌ في غير موضعه**.
        """
        draft = (
            "«نصّ الاقتباس الأول كاملاً هنا» يرد في المذكرة. "
            "وتنص المادة ٤٣ على: «نصّ المادة الثالثة والأربعين كما هو مكتوب»."
        )
        quoted = [p for p in classify(draft) if p.presentation is Presentation.QUOTED]

        self.assertEqual(len(quoted), 2)
        self.assertEqual(quoted[0].reference, "")
        self.assertEqual(quoted[1].reference, "المادة ٤٣")
        self.assertEqual(quoted[1].text, "نصّ المادة الثالثة والأربعين كما هو مكتوب")

    def test_a_naked_reference_is_not_an_attribution(self):
        """«راجع المادة ٤٣.» ذكرٌ للمادة لا نسبةَ نصّ إليها — فلا يُصنع منها مقطع منسوب."""
        passages = classify("راجع المادة ٤٣.")
        self.assertEqual([p.presentation for p in passages], [Presentation.NEUTRAL])

    def test_plain_prose_is_neutral(self):
        """
        ⚠️ و`NEUTRAL` مقصود: به يظهر أيّ العبارات نثرٌ لا نسبة فيه — وهو نصف
        الغرض («يرى المحامي بأيّ العبارات عبارةُ القانون وأيّها عبارةُ الكاتب»).
        """
        passages = classify("يلتزم الطرف الثاني بسداد الأجرة في مواعيدها المتفق عليها.")
        self.assertEqual(len(passages), 1)
        self.assertIs(passages[0].presentation, Presentation.NEUTRAL)
        self.assertEqual(passages[0].reference, "")

    def test_passages_keep_the_order_of_the_draft(self):
        """ترتيب الورود: المحامي يقرأ المسودّة من أوّلها، فيقرأ الملاحظات في مواضعها."""
        draft = (
            "وتنص المادة ٤٣ على: «لا يجوز إنهاء عقد العمل إلا بإخطار كتابي». "
            "وتنص المادة ٤٤ على أنه يجب تسليم العامل مستحقاته."
        )
        self.assertEqual(
            [p.presentation.value for p in classify(draft)],
            ["quoted", "attributed"],
        )

    def test_empty_draft_has_no_passages(self):
        """مسودّة فارغة: لا مقطع ولا انهيار."""
        self.assertEqual(classify(""), ())
        self.assertEqual(classify("   \n  "), ())


# ==============================================================================
# ٥. الفحص — خطأ أم ملاحظة؟
# ==============================================================================


class TestCheckPresentation(unittest.TestCase):
    """الحكم: أيُقبل النقل، أم يُنذر، أم يُعرَض للعلم؟"""

    def test_a_faithful_quotation_produces_no_finding(self):
        """الاقتباس الأمين لا يُنتج شيئاً — وإلا صارت الأداة ضجيجاً يُهمَل."""
        draft = f"وتنص المادة ٤٣ على: «{NOTICE_CLAUSE}»."
        self.assertEqual(check_presentation(draft, lambda reference: NOTICE_CLAUSE), ())

    def test_a_quotation_that_differs_only_in_formatting_produces_no_finding(self):
        """والتشكيل والأرقام والصيغة الشكلية لا تُنذر: مسودّة سليمة تُسلَّم."""
        draft = "وتنص المادة ٤٣ على: «لا يجوز إنهاء عقد العمل إلا بإخطار كتابي»."
        source = "لا يجوز إنهاء عقد العمل إلا بإخطار كتابيّ"
        self.assertEqual(check_presentation(draft, lambda reference: source), ())

    def test_a_quoted_passage_with_a_changed_word_is_an_error_naming_the_word(self):
        """
        🔑 **تغيير كلمة بين علامتي اقتباس = خطأ يمنع التسليم، والكلمة تُسمّى.**

        وهذا هو موضع «لا يجوز تقديم كلام الكاتب على أنه كلام القانون»: العلامتان
        تدّعيان النقل، واللفظ ليس لفظ المادة.
        """
        draft = f"وتنص المادة ٤٣ على: «{WAGE_CLAUSE_CHANGED}»."
        findings = check_presentation(draft, lambda reference: WAGE_CLAUSE)

        self.assertEqual(len(findings), 1)
        finding = findings[0]
        self.assertEqual(finding.kind, KIND_UNFAITHFUL_QUOTE)
        self.assertEqual(finding.severity, SEVERITY_ERROR)
        self.assertIs(finding.match, MatchKind.WORD_CHANGED)
        self.assertIn("اليومية", finding.message)
        self.assertIn("الشهرية", finding.message)
        self.assertIn(KIND_UNFAITHFUL_QUOTE, ERROR_KINDS)

    def test_a_changed_comma_in_a_quotation_is_an_error(self):
        """
        🔑 **العيب الأول من طرفه الآخر:** الفاصلة المُسقطة في اقتباس حقيقي =
        خطأ، لا ملاحظة. وهو الفرق بين هذا الملف و`quote_in_text`.
        """
        draft = f"وتنص المادة ٤٣ على: «{COMMA_QUOTE}»."
        findings = check_presentation(draft, lambda reference: COMMA_SOURCE)

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].kind, KIND_UNFAITHFUL_QUOTE)
        self.assertEqual(findings[0].severity, SEVERITY_ERROR)
        self.assertIs(findings[0].match, MatchKind.PUNCTUATION_CHANGED)
        self.assertIn("،", " ".join(findings[0].changed))

    def test_a_quotation_not_in_the_source_is_an_error(self):
        """اقتباس لا يقابله نصّ في المادة: خطأ — وهو أقرب الحالات إلى التأليف."""
        draft = "وتنص المادة ٤٣ على: «يلتزم الطرف الثاني بتسليم المستندات»."
        findings = check_presentation(draft, lambda reference: NOTICE_CLAUSE)

        self.assertEqual(findings[0].kind, KIND_UNFAITHFUL_QUOTE)
        self.assertIs(findings[0].match, MatchKind.MISSING)
        self.assertIn("غير موجود", findings[0].message)

    def test_a_quotation_for_a_reference_with_no_source_is_a_notice(self):
        """
        🔑 **الأرشيف لم يُنتج المادة: ملاحظة لا خطأ** — على قاعدة
        `attribution.py` («`absent` ملاحظة لا خطأ»). فمنع التسليم بسبب نقص
        تغطية يعاقب المسودّة على عيب في الأرشيف.
        """
        draft = f"وتنص المادة ٩٩ على: «{NOTICE_CLAUSE}»."
        findings = check_presentation(draft, source_of_nothing)

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].kind, KIND_UNKNOWN_SOURCE)
        self.assertEqual(findings[0].severity, SEVERITY_NOTICE)
        self.assertIsNone(findings[0].match)
        self.assertTrue(summarize(findings)["clean"])

    def test_an_unreferenced_quotation_is_a_notice(self):
        """
        ⚠️ **اقتباس بلا مرجع: يُعرَض ولا يُسكَت عنه** — لا يُعرف أيّ نصّ
        يُطابَق به، فهو النقل الذي لا يُفحص. وملاحظةٌ لا خطأ، لأن نقل نصّ
        معروف بلا مرجع ليس مخالفة، وغيابُه عن التقرير هو الخطر.
        """
        draft = f"وقد قيل «{NOTICE_CLAUSE}» في المذكرة."
        findings = check_presentation(draft, lambda reference: NOTICE_CLAUSE)

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].kind, KIND_UNREFERENCED_QUOTE)
        self.assertEqual(findings[0].severity, SEVERITY_NOTICE)
        self.assertEqual(findings[0].reference, "")

    def test_an_attributed_summary_is_a_notice_not_an_error(self):
        """
        🔑 **الملخّص بلا علامات اقتباس: ملاحظة لا خطأ.**

        أن يصوغ المحامي بلفظه ما تفيده مادة هو عمله، لا عيبه. والمنهيّ عنه —
        بنصّ التوجيه — **تقديم** كلام الكاتب على أنه كلام القانون، وقد غابت
        العلامتان فانتفى التقديم. والملاحظة غرضها **بيانيّ**: يرى المحامي أيّ
        العبارات عبارةُ القانون وأيّها عبارةُ الكاتب.

        ولو صارت خطأً لمنعت تسليم مسودّة سليمة — **وأداة تُنذر دائماً لا تُقرأ**.
        """
        draft = f"وتنص المادة ٤٣ على أنه {NOTICE_CLAUSE}."
        findings = check_presentation(draft, lambda reference: NOTICE_CLAUSE)

        self.assertEqual(len(findings), 1)
        finding = findings[0]
        self.assertEqual(finding.kind, KIND_UNQUOTED_ATTRIBUTION)
        self.assertEqual(finding.severity, SEVERITY_NOTICE)
        self.assertIs(finding.presentation, Presentation.ATTRIBUTED)
        self.assertNotIn(KIND_UNQUOTED_ATTRIBUTION, ERROR_KINDS)

        payload = summarize(findings)
        self.assertTrue(payload["clean"])
        self.assertEqual(payload["error_count"], 0)
        self.assertEqual(payload["notice_count"], 1)

    def test_the_verdict_follows_the_injected_source(self):
        """
        🔑 **الحكم تابعٌ لما حُقن، لا لمعرفة محفوظة.**

        الاقتباس نفسه: إن حمل المصدرُ الحقنة نصَّه فلا حكم، وإن حمل غيره فالخطأ
        قائم. ولو كان في الملف نصُّ مادة محفوظ لَما تغيّر الحكم — ولَما فحص شيئاً.
        """
        draft = f"وتنص المادة ٤٣ على: «{NOTICE_CLAUSE}»."
        self.assertEqual(check_presentation(draft, lambda reference: NOTICE_CLAUSE), ())
        self.assertFalse(check_presentation(draft, lambda reference: WAGE_CLAUSE) == ())

    def test_the_injected_source_is_asked_by_the_reference_as_written(self):
        """
        العقد بين الوحدة والمستدعي: `source_of` يُنادى **بالمرجع كما كُتب في
        المسودّة** («المادة ٤٣»)، فيستطيع المستدعي أن يبحث به في أرشيفه.
        """
        asked: list[str] = []

        def recall(reference: str) -> str:
            asked.append(reference)
            return NOTICE_CLAUSE

        check_presentation(f"وتنص المادة ٤٣ على: «{NOTICE_CLAUSE}».", recall)
        self.assertEqual(asked, ["المادة ٤٣"])

    def test_an_empty_or_quotation_free_draft_is_clean_and_says_so_in_arabic(self):
        """
        🔑 **مسودّة بلا اقتباس: لا فحص، و`clean` صحيحة** — والسطر بالعربية،
        لأن ما يُعرض على المحامي عربي.
        """
        for draft in ("", "   ", "يلتزم الطرف الثاني بسداد الأجرة في مواعيدها المتفق عليها."):
            with self.subTest(draft=draft):
                findings = check_presentation(draft, source_of_nothing)
                self.assertEqual(findings, ())
                payload = summarize(findings)
                self.assertTrue(payload["clean"])
                self.assertEqual(payload["total"], 0)
                self.assertTrue(payload["summary"].strip())
                self.assertTrue(
                    any("\u0600" <= char <= "\u06ff" for char in payload["summary"]),
                    "سطر الملخّص ليس عربياً",
                )
                self.assertIn("سليمة", payload["summary"])

    def test_a_neutral_passage_never_produces_a_finding(self):
        """النثر الذي لا نسبة فيه لا يُحاكم — وإلا صار كل سطر في المسودّة اعتراضاً."""
        self.assertEqual(check_presentation("راجع المادة ٤٣.", source_of_nothing), ())

    def test_the_same_inputs_always_give_the_same_findings(self):
        """حتمية الحصيلة: الفحوص تُبنى من المدخلات لا من ترتيب النداءات."""
        draft = (
            f"وتنص المادة ٤٣ على: «{WAGE_CLAUSE_CHANGED}». "
            f"وتنص المادة ٤٤ على أنه {NOTICE_CLAUSE}."
        )
        first = check_presentation(draft, lambda reference: WAGE_CLAUSE)
        second = check_presentation(draft, lambda reference: WAGE_CLAUSE)
        self.assertEqual(first, second)
        self.assertEqual(classify(draft), classify(draft))

    def test_findings_are_frozen(self):
        """الحكم لا يُعدَّل بعد إنشائه — فلا تتبدّل نتيجة أثناء تشغيل."""
        finding = check_presentation(
            f"وتنص المادة ٤٣ على: «{WAGE_CLAUSE_CHANGED}».", lambda reference: WAGE_CLAUSE
        )[0]
        with self.assertRaises(Exception):
            finding.severity = SEVERITY_NOTICE  # type: ignore[misc]


# ==============================================================================
# ٦. العرض على الواجهة
# ==============================================================================


class TestSummarize(unittest.TestCase):
    """العرض: JSON صالح، وعدّادات لا تفترق عن الحصيلة."""

    def _mixed_draft(self) -> str:
        """مسودّة فيها خطأ وملاحظة — لقياس العدّادات والفصل بينهما."""
        return (
            f"وتنص المادة ٤٣ على: «{WAGE_CLAUSE_CHANGED}». "
            f"وتنص المادة ٤٤ على أنه {NOTICE_CLAUSE}."
        )

    def test_the_payload_is_json_safe_and_carries_the_detail(self):
        """🔑 الحصيلة تُبثّ إلى الواجهة: لا كائن غير قابل للترميز، والنوع يُقرأ بنصّه."""
        findings = check_presentation(self._mixed_draft(), lambda reference: WAGE_CLAUSE)
        payload = summarize(findings)
        encoded = json.dumps(payload, ensure_ascii=False)

        self.assertFalse(payload["clean"])
        self.assertEqual(payload["error_count"], 1)
        self.assertEqual(payload["notice_count"], 1)
        self.assertEqual(payload["total"], 2)
        self.assertEqual(payload["findings"][0]["match"], "word_changed")
        self.assertEqual(payload["findings"][0]["severity"], SEVERITY_ERROR)
        self.assertEqual(payload["findings"][0]["presentation"], "quoted")
        self.assertIsInstance(payload["findings"][0]["changed"], list)
        self.assertIn("اليومية", encoded)

    def test_counts_by_kind_and_by_presentation(self):
        """العدّادات لكل نوع وكل وجه — والوجه `attributed` يُعدّ وإن كان ملاحظة."""
        payload = summarize(
            check_presentation(self._mixed_draft(), lambda reference: WAGE_CLAUSE)
        )

        self.assertEqual(payload["counts_by_kind"][KIND_UNFAITHFUL_QUOTE], 1)
        self.assertEqual(payload["counts_by_kind"][KIND_UNQUOTED_ATTRIBUTION], 1)
        self.assertEqual(payload["counts_by_kind"][KIND_UNKNOWN_SOURCE], 0)
        self.assertEqual(payload["counts_by_presentation"]["quoted"], 1)
        self.assertEqual(payload["counts_by_presentation"]["attributed"], 1)
        self.assertEqual(payload["counts_by_presentation"]["neutral"], 0)

    def test_every_kind_key_is_present_even_at_zero(self):
        """شكل الجواب ثابت: لو تبدّلت المفاتيح بتبدّل المسودّة لانكسرت الواجهة."""
        payload = summarize(())
        self.assertEqual(sorted(payload["counts_by_kind"]), sorted(FINDING_KINDS))
        self.assertEqual(
            sorted(payload["counts_by_presentation"]), ["attributed", "neutral", "quoted"]
        )

    def test_notices_alone_leave_the_payload_clean(self):
        """
        ⚠️ **الملاحظة لا تمنع التسليم والخطأ يمنعه** — وهذا الفرق هو الفرق بين
        تقرير يُقرأ وتقرير يُتجاهَل.
        """
        draft = (
            f"وتنص المادة ٤٤ على أنه {NOTICE_CLAUSE}. "
            f"وتنص المادة ٩٩ على: «{NOTICE_CLAUSE}»."
        )
        findings = check_presentation(draft, source_of_nothing)
        payload = summarize(findings)

        self.assertEqual(len(findings), 2)
        self.assertTrue(payload["clean"])
        self.assertEqual(payload["error_count"], 0)
        self.assertEqual(payload["notice_count"], 2)
        self.assertEqual(payload["counts_by_kind"][KIND_UNKNOWN_SOURCE], 1)
        self.assertEqual(payload["counts_by_kind"][KIND_UNQUOTED_ATTRIBUTION], 1)

    def test_an_error_alone_blocks_delivery(self):
        """والخطأ وحده يمنع: `clean` تُحسب من الأخطاء لا من مجموع الحصيلة."""
        payload = summarize(
            check_presentation(
                f"وتنص المادة ٤٣ على: «{WAGE_CLAUSE_CHANGED}».", lambda reference: WAGE_CLAUSE
            )
        )
        self.assertFalse(payload["clean"])
        self.assertEqual(payload["notice_count"], 0)
        self.assertIn("يمنع التسليم", payload["summary"])

    def test_the_summary_line_separates_error_from_notice(self):
        """السطر يميّز الخطأ من الملاحظة — وهما تصرّفان مختلفان عند المحامي."""
        error = summarize(
            check_presentation(
                f"وتنص المادة ٤٣ على: «{WAGE_CLAUSE_CHANGED}».", lambda reference: WAGE_CLAUSE
            )
        )
        notice = summarize(
            check_presentation(
                f"وتنص المادة ٤٤ على أنه {NOTICE_CLAUSE}.", source_of_nothing
            )
        )
        self.assertIn("يمنع التسليم", error["summary"])
        self.assertNotIn("يمنع التسليم", notice["summary"])
        self.assertIn("ملاحظة", notice["summary"])

    def test_a_bare_finding_list_is_accepted(self):
        """تُقبل `tuple` كما تُقبل `list`، ولا يُعاد ترتيب شيء."""
        findings = list(
            check_presentation(self._mixed_draft(), lambda reference: WAGE_CLAUSE)
        )
        self.assertEqual(summarize(findings), summarize(tuple(findings)))

    def test_an_unknown_finding_kind_is_still_counted(self):
        """
        ⚠️ نوع أجنبي لا يُسقَط من العدّاد: مستدعٍ بنى ملاحظته بنفسه يستحقّ أن
        تُعرض، وإسقاط ما لا يُعرف يُخفي عيباً في تسمية النوع.
        """
        stranger = PresentationFinding(
            kind="something_else",
            severity=SEVERITY_NOTICE,
            presentation=Presentation.NEUTRAL,
            reference="",
            text="نصّ",
            message="ملاحظة من خارج الملف.",
        )
        payload = summarize([stranger])
        self.assertEqual(payload["total"], 1)
        self.assertEqual(payload["counts_by_kind"]["something_else"], 1)
        self.assertTrue(payload["clean"])


# ==============================================================================
# ٧. ضمانات على الوحدة نفسها
# ==============================================================================


class TestModuleGuarantees(unittest.TestCase):
    """
    ضمانات معمارية: لو انكسرت، انكسرت الفائدة كلها — كـ`test_attribution.py`.

    ⚠️ والدَّرس الذي وُلد منه `test_module_health.py`: «الاختبارات تمرّ» ليست
    عبارة عن سلامة المشروع، بل عن سلامة **ما تُشغّله الاختبارات**.
    """

    def test_imports_are_stdlib_only(self):
        """
        ⚠️ **لا تبعية خارجية:** الوحدة تُستدعى في مسار الصياغة، وتبعية خارجية
        هنا تعني أن اختبارها يحتاج شبكةً أو مفتاحاً — فلا تُشغَّل فلا تحمي شيئاً.
        """
        source = pathlib.Path(quotation.__file__).read_text(encoding="utf-8")
        imported = set(
            _re.findall(r"^(?:from|import)\s+([A-Za-z_][\w\.]*)", source, _re.MULTILINE)
        )
        allowed = {
            "__future__",
            "dataclasses",
            "difflib",
            "enum",
            "math",
            "re",
            "typing",
            "unicodedata",
        }
        self.assertTrue(imported <= allowed, f"استيرادات: {sorted(imported - allowed)}")

    def test_no_environment_network_or_printing(self):
        """لا بيئة، ولا شبكة، ولا طبع: وحدة تُطبع أثناء الاستيراد تُلوّث أي مسار."""
        source = pathlib.Path(quotation.__file__).read_text(encoding="utf-8")
        for forbidden in (
            "os.environ",
            "getenv",
            "requests.",
            "urllib",
            "socket",
            "http",
            "print(",
            "open(",
        ):
            self.assertNotIn(forbidden, source)

    def test_the_public_nouns_are_frozen_dataclasses(self):
        """الأنصاف لا تُعدَّل بعد إنشائها — فلا تتبدّل نتيجة أثناء تشغيل."""
        for instance in (
            StrictMatch(MatchKind.EXACT, "نصّ"),
            Passage("نصّ", Presentation.NEUTRAL),
            PresentationFinding(
                kind=KIND_UNFAITHFUL_QUOTE,
                severity=SEVERITY_ERROR,
                presentation=Presentation.QUOTED,
                reference="المادة ٤٣",
                text="نصّ",
                message="حكم",
            ),
        ):
            with self.subTest(noun=type(instance).__name__):
                with self.assertRaises(Exception):
                    instance.text = "آخر"  # type: ignore[misc]

    def test_no_module_level_state(self):
        """
        لا حالة على مستوى الوحدة: كل نداء يُعطي نتيجته من مدخلاته وحدها.

        وهو ما يجعل الحصيلة تُعاد كاملةً في `tuple` بدل عدّاد يُقرأ من آخر
        نداء — على النمط الذي شرحه `review.py` في رفض `last_dropped()`.
        """
        first = strict_match(COMMA_QUOTE, COMMA_SOURCE)
        strict_match(WAGE_CLAUSE_CHANGED, WAGE_CLAUSE)
        third = strict_match(COMMA_QUOTE, COMMA_SOURCE)
        self.assertEqual(first, third)

        draft = f"وتنص المادة ٤٣ على: «{COMMA_QUOTE}»."
        once = check_presentation(draft, lambda reference: COMMA_SOURCE)
        check_presentation("نصّ آخر لا اقتباس فيه.", source_of_nothing)
        twice = check_presentation(draft, lambda reference: COMMA_SOURCE)
        self.assertEqual(once, twice)


if __name__ == "__main__":
    unittest.main(verbosity=2)
