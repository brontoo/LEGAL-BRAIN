"""
اختبارات سند المادة — هل النصّ المنسوب نصُّ المادة التي نُسب إليها؟
=============================================================================

تشغيل:
    python -m unittest discover -s tests -t . -v

حتمية بالكامل: بلا شبكة، وبلا نموذج، وبلا قاعدة بيانات، وبلا قرص. ولا تحتاج
`fake_deps` لأن `attribution` وحدة نقية كـ `citations.py`: كل حكمها من مدخلاتها.

وأهمّ اختبار في الملف هو ``test_the_real_case_is_mismatched_not_matched`` — وهو
الواقعة التي جاء الملف لها: مسودّة كتبت «المادة ٤٣/٢ تنص على: …» ونقلت نصاً عن
العقد محدد المدة **هو في الأرشيف فعلاً لكن تحت المادة ٤٢**. فالنصّ حقيقي، والفحص
القائم (`citations.py`) يمرّره، والمذكرة تُسلَّم بنصّ صحيح منسوب إلى مادة بريئة.
والاختبار يثبّت **الحالتين معاً**: أن الحكم ``mismatched``، وأنه **ليس**
``matched`` — وإلا لمرّ العيب لو عاد.

والاختبار الثاني في الأهمّية ``test_the_extractor_prefers_the_quoted_span``:
الاقتباس بين علامتي تنصيص نصُّ المادة، وما قبله كلام الكاتب عنها — فلو دخل
التمهيد في الاقتباس لصار كل إسناد صحيح ``mismatched``، أي **أداة تُنذر دائماً
فلا تُقرأ**.
"""

import json
import pathlib
import re as _re
import unittest

import attribution
from attribution import (
    ERROR_STATUSES,
    STATUS_ABSENT,
    STATUS_MATCHED,
    STATUS_MISMATCHED,
    Attribution,
    AttributionOutcome,
    extract_attributions,
    summarize,
    verify_attribution,
    verify_attributions,
)
from citations import MIN_QUOTE_CHARS, Evidence, normalize

# ==============================================================================
# بيانات الاختبار — النصوص الحقيقية من العيب، لا نصوص متخيَّلة
# ==============================================================================

#: النصّ الذي نُسب إلى المادة ٤٣/٢ في المسودّة الحقيقية، **وهو في الأرشيف تحت
#: المادة ٤٢** — وهذا هو العيب كله في سطرين.
FIXED_TERM = (
    "ينتهي عقد العمل غير محدد المدة إذا أبرم الطرفان عقداً جديداً محدد المدة"
)
#: نصّ المادة ٤٣ الفعلي في الأرشيف — لا يحوي ما سبق.
NOTICE_CLAUSE = "لا يجوز إنهاء عقد العمل إلا بإخطار كتابي"
#: ذيل نصّ المادة ٤٣، ليكون المقطع أطول من الاقتباس المأخوذ منه.
NOTICE_CLAUSE_TAIL = "، ويجب تسليم العامل مستحقاته عند انتهاء العلاقة"

#: الاقتباس المطابق للمادة ٤٣ — يُبنى منه الرسم الخام.
ARTICLE_43_QUOTE = f"{NOTICE_CLAUSE}{NOTICE_CLAUSE_TAIL}"


def make_evidence() -> list:
    """المقاطع كما تُرجعها أدوات الاسترجاع: كل مقطع بحامله من رقم المادة."""
    return [
        Evidence(
            ref="L1",
            chunk_id="42",
            document_name="قانون تنظيم علاقات العمل",
            text=f"المادة 42: {FIXED_TERM}",
            similarity=0.9,
            tool="legislation",
        ),
        Evidence(
            ref="L2",
            chunk_id="43",
            document_name="قانون تنظيم علاقات العمل",
            text=f"المادة 43: {ARTICLE_43_QUOTE}",
            similarity=0.87,
            tool="legislation",
        ),
        Evidence(
            ref="L3",
            chunk_id="29",
            document_name="قانون تنظيم علاقات العمل",
            text=(
                "المادة 29/9: يُحسب بدل الإجازة السنوية على الأجر الأساسي، "
                "ولا يُزاد عليه إلا إذا منح اتفاقٌ العامل ميزةً أفضل"
            ),
            similarity=0.8,
            tool="legislation",
        ),
    ]


def text_of(item: Evidence) -> str:
    """النصّ الذي يُفحص — وهو ما رآه النموذج، لا النصّ الكامل للمقطع."""
    return item.text


#: الواقعة الحقيقية: نصّ المادة ٤٢ منسوباً إلى المادة ٤٣/٢، بعلامتي تنصيص.
THE_REAL_CASE = f"وتنص المادة ٤٣/٢ على: «{FIXED_TERM}»"

#: إسناد صحيح: نصّ المادة ٤٣ إلى المادة ٤٣، بعلامتي تنصيص.
A_CORRECT_ATTRIBUTION = f"وتنص المادة 43 على: «{ARTICLE_43_QUOTE}»"


# ==============================================================================
# ١. الاستخراج — المراجع وصيغها
# ==============================================================================


class TestExtractAttributions(unittest.TestCase):
    """استخراج أزواج (المرجع، النصّ المنسوب) من المتن الخام."""

    def test_each_reference_form_is_extracted(self):
        """
        🔑 **صيغ الإشارة الأربع، وكلّها تُستخرج كما كُتبت في المسودّة.**

        و«كما كُتبت» مقصود: حقول المرجع تُعرَض على المحامي ليبحث بها في
        مسودّته، فلو خرجت مطبَّعة («الماده 43 2») لصار البحث عنها عملاً عليه.
        """
        forms = [
            f"وتنص المادة 43 على: «{NOTICE_CLAUSE}»",
            f"وتنص المادة 43/2 على: «{NOTICE_CLAUSE}»",
            f"وتنص المادة (43) على: «{NOTICE_CLAUSE}»",
            f"وتنص م 43 على: «{NOTICE_CLAUSE}»",
        ]
        expected = ["المادة 43", "المادة 43/2", "المادة (43)", "م 43"]
        for draft, reference in zip(forms, expected):
            with self.subTest(reference=reference):
                pairs = extract_attributions(draft)
                self.assertEqual(len(pairs), 1)
                self.assertEqual(pairs[0][0], reference)

    def test_arabic_indic_digits_are_read_like_latin_ones(self):
        """
        الأرقام الهندية واللاتينية مادةٌ واحدة.

        والرقم في حقل المرجع يبقى على رسمه، لكن **الفحص** يجري على المطبَّع —
        فيجب أن يتّفق «٤٣» و«43» على المادة نفسها، وإلا لصار كل إسناد بأرقام
        هندية بلا فحص.
        """
        pairs = extract_attributions(f"وتنص المادة ٤٣ على: «{NOTICE_CLAUSE}»")
        self.assertEqual(pairs[0][0], "المادة ٤٣")
        check = verify_attribution(
            pairs[0][0], pairs[0][1], make_evidence(), text_of
        )
        self.assertEqual(check.status, STATUS_MATCHED)
        self.assertEqual(check.evidence_ref, "L2")

    def test_a_reference_with_no_text_after_it_is_not_an_attribution(self):
        """«المادة ٤٣.» ذكرٌ للمادة لا إسنادٌ لنصّ — فلا يُخرج زوجاً كاذباً."""
        self.assertEqual(extract_attributions("راجع المادة 43."), [])

    def test_two_references_in_one_sentence_are_paired_with_their_own_texts(self):
        """
        🔑 **لكل مرجع نصّه، لا نصّ جاره.**

        والمرجعان في جملة واحدة يفصل بينهما نصّان؛ فلو أُخذ لكلٍّ منهما بقيّة
        الجملة لصار نصّ المادة ٤٢ منسوباً إلى ٤٣ أيضاً — **وهو العيب نفسه
        مصنوعاً في الاستخراج**.
        """
        draft = f"وتنص المادة 43 على: «{NOTICE_CLAUSE}» وتنص المادة 42 على: «{FIXED_TERM}»"
        pairs = extract_attributions(draft)
        self.assertEqual([reference for reference, _quote in pairs], ["المادة 43", "المادة 42"])
        self.assertIn(normalize(NOTICE_CLAUSE), pairs[0][1])
        self.assertNotIn(normalize(FIXED_TERM), pairs[0][1])
        self.assertIn(normalize(FIXED_TERM), pairs[1][1])

    def test_the_extractor_prefers_the_quoted_span(self):
        """
        🔑 **الاقتباس بين علامتيه هو المنسوب، والتمهيد ليس منه.**

        «وتنص المادة ٤٣ على أنه …» تمهيدُ الكاتب عن المادة؛ ولو بقي في الاقتباس
        لصار نصّ المادة نفسه غير موجود في المقطع — لأن **كلام الكاتب ليس في
        المادة**. فهذا هو الموضع الذي كان يُنتج ``mismatched`` كاذباً عن كل
        إسناد صحيح.
        """
        draft = f"وتنص المادة 43 على أنه {NOTICE_CLAUSE}."
        pairs = extract_attributions(draft)
        self.assertEqual(len(pairs), 1)
        self.assertNotIn("تنص", pairs[0][1])
        self.assertNotIn("علي انه", pairs[0][1])
        check = verify_attribution(pairs[0][0], pairs[0][1], make_evidence(), text_of)
        self.assertEqual(check.status, STATUS_MATCHED)

    def test_a_quote_below_the_evidence_threshold_is_not_judged(self):
        """
        ⚠️ **ما دون ``MIN_QUOTE_CHARS`` ليس اقتباساً، فلا يُصدَّق عليه حكم.**

        إصدار «منسوب إلى غير مادّته» على كلمتين اتهامٌ لا دليل عليه. والثمن
        **تغطية ناقصة معلنة** لا اتهام كاذب — والمرجع نفسه يبقى مفحوصاً في
        `citations.py` بـ``unbacked_article_refs``.
        """
        outcome = verify_attributions("وتنص المادة 43 على: «كتابي»", make_evidence(), text_of)
        self.assertEqual(outcome.checks, [])
        self.assertTrue(outcome.clean)
        self.assertLess(len(normalize("كتابي")), MIN_QUOTE_CHARS)

    def test_a_repeated_attribution_is_reported_once(self):
        """التكرار المطويّ لا يُضخّم العدّاد المعروض على المحامي — كـ`review.py`."""
        draft = f"وتنص المادة 43 على: «{NOTICE_CLAUSE}» وتنص المادة 43 على: «{NOTICE_CLAUSE}»"
        self.assertEqual(len(extract_attributions(draft)), 1)

    def test_empty_draft(self):
        """مسودّة فارغة: لا زوج ولا انهيار."""
        self.assertEqual(extract_attributions(""), [])
        self.assertEqual(extract_attributions(None), [])


# ==============================================================================
# ٢. الفحص — الحالات الثلاث
# ==============================================================================


class TestVerifyAttribution(unittest.TestCase):
    """الحكم: أين يقع النصّ بالنسبة إلى المادة التي نُسب إليها؟"""

    def test_a_correct_attribution_is_matched(self):
        """الإسناد الصحيح يخرج ``matched`` — حتى لا يمنع الفحص تسليم مسودّة سليمة."""
        check = verify_attribution("المادة 43", ARTICLE_43_QUOTE, make_evidence(), text_of)
        self.assertEqual(check.status, STATUS_MATCHED)
        self.assertEqual(check.evidence_ref, "L2")
        self.assertEqual(check.found_in, "L2")

    def test_the_real_case_is_mismatched_not_matched(self):
        """
        🔑 **الواقعة التي جاء الملف لها.**

        نصّ العقد محدد المدة **موجود في الأرشيف** (تحت المادة ٤٢)، فكل فحص قائم
        يمرّره. والمادة ٤٣ لا تحويه. فالحكم ``mismatched``، ويُسجَّل أن النصّ
        وُجد في ``L1`` — لأن **الفرق بين «نصّ مؤلَّف» و«نصّ في مادة أخرى» فرقٌ
        في التصرّف**: الأول يُحذف، والثاني يُنقل إلى مادّته.
        """
        check = verify_attribution("المادة ٤٣/٢", FIXED_TERM, make_evidence(), text_of)
        self.assertEqual(check.status, STATUS_MISMATCHED)
        self.assertNotEqual(check.status, STATUS_MATCHED)
        self.assertEqual(check.evidence_ref, "L2")
        self.assertEqual(check.found_in, "L1")
        # والنصّ حقيقي فعلاً — وهذا ما يجعل العيب خطيراً: لا شيء فيه مؤلَّف.
        self.assertTrue(normalize(FIXED_TERM) in normalize(make_evidence()[0].text))

    def test_an_article_no_evidence_mentions_is_absent(self):
        """
        🔑 **مادة لم يُنتجها الاسترجاع: ``absent`` لا ``mismatched``.**

        الفرق هو الفرق بين عيب في المسودّة وعيب في التغطية. ولو صارت ``absent``
        خطأً لمنعنا تسليم مسودّة سليمة بسبب أرشيف ناقص.
        """
        check = verify_attribution("المادة 88", "لا يجوز تشغيل العامل أكثر من ثماني ساعات", make_evidence(), text_of)
        self.assertEqual(check.status, STATUS_ABSENT)
        self.assertEqual(check.evidence_ref, "")
        self.assertEqual(check.found_in, "")

    def test_a_real_quote_under_an_unretrieved_article_is_still_absent(self):
        """
        ⚠️ **النصّ الحقيقي لا ينقذ مادةً غير مسترجَعة.**

        نصّ المادة ٤٢ موجود، والمسودّة نسبته إلى المادة ٩٩ التي لا يذكرها أي
        مقطع. والحكم ``absent`` لا ``matched``: لا يُقال «ثبت النصّ» ولم تُفحص
        مادّته أصلاً، ولا يُقال ``mismatched`` ولم يُعرف نصُّ المادة ٩٩.
        """
        check = verify_attribution("المادة ٩٩", FIXED_TERM, make_evidence(), text_of)
        self.assertEqual(check.status, STATUS_ABSENT)

    def test_number_boundaries_prevent_a_partial_match(self):
        """
        «المادة ٤٣» لا تُقرأ «المادة ٤٣٠».

        وهذا حدّ ``citations.py`` نفسه في البحث عن الرقم: بلا حدود يصير كل رقم
        جزءاً من رقم آخر، فتُنسب النصوص إلى موادّ لم تُذكر.
        """
        evidence = [
            Evidence("L1", "1", "قانون", "المادة 430: نصّ آخر تماماً لا علاقة له"),
        ]
        check = verify_attribution("المادة 43", NOTICE_CLAUSE, evidence, text_of)
        self.assertEqual(check.status, STATUS_ABSENT)

    def test_an_unreadable_reference_is_a_notice_not_an_accusation(self):
        """مرجع لا يُقرأ رقمه: ``absent`` — «المرجع الذي لا يُقرأ لا يُتَّهم نصُّه»."""
        check = verify_attribution("المادة", NOTICE_CLAUSE, make_evidence(), text_of)
        self.assertEqual(check.status, STATUS_ABSENT)
        self.assertEqual(check.evidence_ref, "")

    def test_without_evidence_nothing_is_mismatched(self):
        """بلا استرجاع لا يُتّهم كاتب: كل إسناد ``absent`` — وهو الحكم الصحيح."""
        check = verify_attribution("المادة 43", ARTICLE_43_QUOTE, [], text_of)
        self.assertEqual(check.status, STATUS_ABSENT)

    def test_an_owner_that_merely_mentions_the_article_still_counts_as_its_holder(self):
        """
        ⚠️ **حدّ معلن:** المقطع الذي **يذكر** المادة يُعدّ حاملاً لها.

        فإذا كان نصّ المادة نفسها لم يُسترجَع، ووُجد ذكره العابر فقط، خرج اقتباسٌ
        صحيح ``mismatched`` وكان الأحقّ به ``absent``. والحدّ مكتوب في صدر الملف
        لأن الأداة تُتَّهم به أحياناً، ومن عرف حدّه عرف كيف يقرأ نتيجته.
        """
        evidence = [
            Evidence("L1", "1", "حكم قضائي", "وكما ورد في المادة 43 من قانون العمل، فقد قضت المحكمة"),
        ]
        check = verify_attribution("المادة 43", NOTICE_CLAUSE, evidence, text_of)
        self.assertEqual(check.status, STATUS_MISMATCHED)
        self.assertEqual(check.found_in, "")

    def test_text_of_is_used_and_not_evidence_text(self):
        """
        الفحص على **ما أُعطي** لا على النصّ الكامل للمقطع.

        وهو مبدأ `citations.py` نفسه: السؤال «هل اقتبس النموذج ممّا أُعطي؟» لا
        «هل هذا موجود في القاعدة؟». فلو قرأ هذا الملف ``item.text`` بنفسه لفحص
        نصاً لم يره الكاتب.
        """
        evidence = [Evidence("L1", "1", "قانون", "المادة 43: نصّ كامل لا يراه النموذج")]
        outcome = verify_attributions(
            f"وتنص المادة 43 على: «{NOTICE_CLAUSE}»",
            evidence,
            lambda _item: "المادة 43: نصّ آخر مقتطع",
        )
        self.assertEqual(outcome.checks[0].status, STATUS_MISMATCHED)

    def test_attribution_is_frozen(self):
        """الفحص الواحد لا يُعدَّل بعد إنشائه — فلا تتبدّل نتيجة أثناء تشغيل."""
        check = verify_attribution("المادة 43", ARTICLE_43_QUOTE, make_evidence(), text_of)
        self.assertTrue(isinstance(check, Attribution))
        with self.assertRaises(Exception):
            check.status = STATUS_MISMATCHED  # type: ignore[misc]

    def test_a_direct_call_with_a_short_quote_is_a_known_limit(self):
        """
        ⚠️ **حدّ معلن ومُثبَّت في اختبار، لا سلوك مرغوب:** النداء المباشر بنصّ
        دون ``MIN_QUOTE_CHARS`` يخرج ``mismatched``، لأن ``quote_in_text`` لا
        تثبت ما دون العتبة.

        وهذا **لا يقع في المسار المعتاد**، لأن ``extract_attributions`` لا تُخرج
        زوجاً دون العتبة. والاختبار يثبّت الحدّ ليراه من غيّر العتبة أو تجاوز
        المستخرج — فالحدّ الذي يُثبَّت في اختبار لا يتبدّل صامتاً.
        """
        check = verify_attribution("المادة 43", "كتابي", make_evidence(), text_of)
        self.assertEqual(check.status, STATUS_MISMATCHED)
        self.assertEqual(verify_attributions("وتنص المادة 43 على: «كتابي»", make_evidence(), text_of).checks, [])


class TestVerifyAttributions(unittest.TestCase):
    """الحصيلة كاملة: كل إسنادات المسودّة، بترتيب ورودها."""

    def test_the_real_case_end_to_end(self):
        """
        🔑 **من المتن الخام إلى الحكم: النصّ الصحيح في المادة الخطأ.**

        والمسودّة تُقرأ بطلاقة، والاقتباس حقيقي، ومقطع المادة ٤٣ موجود — ومع
        ذلك الحكم ``mismatched``. ولو كان الفحص على وجود النصّ في الأرشيف وحده
        لمرّ هذا الإسناد كما مرّ من كل فحص قائم.
        """
        outcome = verify_attributions(THE_REAL_CASE, make_evidence(), text_of)
        self.assertEqual(len(outcome.checks), 1)
        self.assertEqual(len(outcome.mismatched), 1)
        self.assertEqual(len(outcome.matched), 0)
        self.assertFalse(outcome.clean)
        self.assertEqual(outcome.checks[0].found_in, "L1")

    def test_a_correct_attribution_end_to_end(self):
        outcome = verify_attributions(A_CORRECT_ATTRIBUTION, make_evidence(), text_of)
        self.assertEqual(len(outcome.matched), 1)
        self.assertEqual(outcome.mismatched, [])
        self.assertTrue(outcome.clean)

    def test_a_draft_without_article_references_has_no_checks_and_is_clean(self):
        """🔑 مسودّة بلا إسناد: لا فحوص، و``clean`` صحيحة — ولا انهيار."""
        outcome = verify_attributions(
            "يلتزم الطرف الثاني بسداد الأجرة في مواعيدها المتفق عليها.",
            make_evidence(),
            text_of,
        )
        self.assertEqual(outcome.checks, [])
        self.assertTrue(outcome.clean)
        self.assertEqual(outcome.mismatched, [])
        self.assertIn("لا إسناد", outcome.summary())

    def test_absent_alone_does_not_block_delivery(self):
        """
        ⚠️ **الملاحظة لا تمنع التسليم، والخطأ يمنعه — وهذا الفرق مقصود.**

        من جعل ``absent`` خطأً منع تسليم مسودّة سليمة بسبب أرشيف ناقص، ومن جعل
        ``mismatched`` ملاحظةً سلّم قولاً كاذباً عن القانون. وكلاهما أسوأ من
        عدم الفحص.
        """
        outcome = verify_attributions(
            "وتنص المادة 88 على: «لا يجوز تشغيل العامل أكثر من ثماني ساعات يومياً»",
            make_evidence(),
            text_of,
        )
        self.assertEqual(len(outcome.absent), 1)
        self.assertTrue(outcome.clean)
        self.assertIn(STATUS_MISMATCHED, ERROR_STATUSES)
        self.assertNotIn(STATUS_ABSENT, ERROR_STATUSES)

    def test_the_same_inputs_always_give_the_same_outcome(self):
        """
        🔑 **حتمية:** المدخل نفسه يُعطي الحصيلة نفسها، دائماً.

        وهي الضمان الذي يجعل الحصيلة تُبنى من المدخلات لا من ترتيب النداءات —
        على النمط الذي شرحه `review.py` في رفض حالةٍ على مستوى الوحدة.
        """
        first = verify_attributions(THE_REAL_CASE, make_evidence(), text_of)
        second = verify_attributions(THE_REAL_CASE, make_evidence(), text_of)
        self.assertEqual(first.checks, second.checks)
        once = extract_attributions(THE_REAL_CASE)
        twice = extract_attributions(THE_REAL_CASE)
        self.assertEqual(once, twice)

    def test_checks_keep_the_order_of_the_draft(self):
        """الفحوص بترتيب ورودها في المسودّة — فالمحامي يقرأها في مواضعها."""
        draft = (
            f"وتنص المادة 43 على: «{NOTICE_CLAUSE}» "
            f"وتنص المادة 42 على: «{FIXED_TERM}»"
        )
        outcome = verify_attributions(draft, make_evidence(), text_of)
        self.assertEqual(
            [check.reference for check in outcome.checks],
            ["المادة 43", "المادة 42"],
        )
        self.assertEqual(len(outcome.matched), 2)


# ==============================================================================
# ٣. العرض
# ==============================================================================


class TestSummarize(unittest.TestCase):
    """العرض على المحامي والواجهة — JSON صالح، وعدّادات لا تفترق عن الحصيلة."""

    def test_the_payload_is_json_safe_and_carries_the_detail(self):
        """🔑 الحصيلة تُبثّ إلى الواجهة: لا ``Decimal`` ولا ``set`` ولا كائن غير قابل للترميز."""
        outcome = verify_attributions(THE_REAL_CASE, make_evidence(), text_of)
        payload = summarize(outcome)
        encoded = json.dumps(payload, ensure_ascii=False)

        self.assertFalse(payload["clean"])
        self.assertEqual(payload["error_count"], 1)
        self.assertEqual(payload["notice_count"], 0)
        self.assertEqual(payload["total"], 1)
        self.assertEqual(payload["checks"][0]["status"], STATUS_MISMATCHED)
        self.assertEqual(payload["checks"][0]["reference"], "المادة ٤٣/٢")
        self.assertEqual(payload["checks"][0]["found_in"], "L1")
        self.assertIn("المادة ٤٣/٢", encoded)

    def test_absent_is_counted_as_a_notice_and_leaves_the_payload_clean(self):
        outcome = verify_attributions(
            "وتنص المادة 88 على: «لا يجوز تشغيل العامل أكثر من ثماني ساعات يومياً»",
            make_evidence(),
            text_of,
        )
        payload = summarize(outcome)
        self.assertTrue(payload["clean"])
        self.assertEqual(payload["error_count"], 0)
        self.assertEqual(payload["notice_count"], 1)

    def test_the_payload_accepts_a_bare_check_list(self):
        """تُقبل الحصيلة أو قائمة الفحوص — ولا يُعاد ترتيب شيء."""
        checks = verify_attributions(THE_REAL_CASE, make_evidence(), text_of).checks
        self.assertEqual(summarize(checks), summarize(AttributionOutcome(checks=checks)))

    def test_the_summary_line_separates_mismatch_from_absence(self):
        """السطر يميّز «منسوب إلى غير مادّته» من «مادة لم تُسترجَع» — وهما تصرّفان."""
        mismatched = AttributionOutcome(
            checks=[Attribution("المادة ٤٣/٢", "نصّ", STATUS_MISMATCHED, "L2", "L1")]
        )
        absent = AttributionOutcome(
            checks=[Attribution("المادة ٨٨", "نصّ", STATUS_ABSENT, "")]
        )
        self.assertIn("غير مادّته", mismatched.summary())
        self.assertIn("لم تُسترجَع", absent.summary())
        self.assertNotIn("غير مادّته", absent.summary())

    def test_empty_payload(self):
        """بلا فحوص: ``clean`` صحيحة وعدّادات صفر — لا سطر خطأ ولا استثناء."""
        payload = summarize(AttributionOutcome())
        self.assertEqual((payload["clean"], payload["total"], payload["checks"]), (True, 0, []))

    def test_outcome_defaults_are_independent(self):
        """لكل حصيلة قائمتها الخاصة — لا قائمة مشتركة تتلوّث بين المستدعين."""
        first, second = AttributionOutcome(), AttributionOutcome()
        first.checks.append(Attribution("المادة ٤٣", "نصّ", STATUS_MATCHED, "L2"))
        self.assertEqual(second.checks, [])


# ==============================================================================
# ٤. ضمانات على الوحدة نفسها
# ==============================================================================


class TestModuleGuarantees(unittest.TestCase):
    """ضمانات معمارية: لو انكسرت، انكسرت الفائدة كلها."""

    def test_imports_are_stdlib_plus_citations_only(self):
        """
        ⚠️ **لا تبعية خارجية** — وهي شرط عملي لا ذوقي: الوحدة تُستدعى في مسار
        الصياغة، وتبعية خارجية هنا تعني أن اختبارها يحتاج شبكةً أو مفتاحاً،
        فلا يُشغَّل فلا يحمي شيئاً.
        """
        source = pathlib.Path(attribution.__file__).read_text(encoding="utf-8")
        imported = set(
            _re.findall(r"^(?:from|import)\s+([A-Za-z_][\w\.]*)", source, _re.MULTILINE)
        )
        allowed = {"__future__", "re", "dataclasses", "typing", "citations"}
        self.assertTrue(imported <= allowed, f"استيرادات: {sorted(imported - allowed)}")

    def test_no_environment_network_or_printing(self):
        """لا بيئة، ولا شبكة، ولا طبع: وحدة تُطبع أثناء الاستيراد تُلوّث أي مسار."""
        source = pathlib.Path(attribution.__file__).read_text(encoding="utf-8")
        for forbidden in ("os.environ", "getenv", "requests.", "urllib", "socket", "http", "print("):
            self.assertNotIn(forbidden, source)

    def test_the_verdict_follows_the_evidence_and_no_article_text_is_saved(self):
        """
        🔑 **لا نصّ مادة محفوظ في هذا الملف — والدليل سلوكيّ لا بمسح المصدر.**

        الإسناد نفسه («المادة ٤٣» ونصّ العقد محدد المدة) يخرج ``matched`` إذا
        حمل مقطعُ المادة ٤٣ ذلك النصّ، و``mismatched`` إذا حمل نصّاً آخر. فالحكم
        **تابعٌ لما استُرجِع**، لا لمعرفة عن المادة ٤٣ مكتوبة في الكود.

        ولو كُتب في الكود «المادة ٤٣ تنصّ على العقد محدد المدة» لصار الملف رأياً
        في القانون يتقادم بصمت، **ولما فحص شيئاً**: المقارنة بين ما كتبه النموذج
        وما استُرجِع من الأرشيف.
        """
        carrying = [Evidence("L1", "1", "قانون", f"المادة 43: {FIXED_TERM}")]
        other = [Evidence("L1", "1", "قانون", f"المادة 43: {NOTICE_CLAUSE}")]
        self.assertEqual(
            verify_attribution("المادة 43", FIXED_TERM, carrying, text_of).status,
            STATUS_MATCHED,
        )
        self.assertEqual(
            verify_attribution("المادة 43", FIXED_TERM, other, text_of).status,
            STATUS_MISMATCHED,
        )

    def test_thresholds_and_statuses_come_from_the_project(self):
        """العتبة عتبة `citations.py`، والحالات أسماء ثوابت لا نصوص حرّة."""
        self.assertGreaterEqual(MIN_QUOTE_CHARS, 8)
        self.assertEqual(STATUS_MATCHED, "matched")
        self.assertEqual(STATUS_ABSENT, "absent")
        self.assertEqual(STATUS_MISMATCHED, "mismatched")

    def test_no_module_level_state(self):
        """
        لا حالة على مستوى الوحدة: كل نداء يُعطي نتيجته من مدخلاته.

        وهو ما يجعل الحصيلة تُعاد كاملةً في `AttributionOutcome` بدل عدّاد
        يُقرأ من آخر نداء — على النمط الذي شرحه `review.py`.
        """
        first = verify_attributions(THE_REAL_CASE, make_evidence(), text_of)
        verify_attributions(A_CORRECT_ATTRIBUTION, make_evidence(), text_of)
        third = verify_attributions(THE_REAL_CASE, make_evidence(), text_of)
        self.assertEqual(first.checks, third.checks)


if __name__ == "__main__":
    unittest.main(verbosity=2)
