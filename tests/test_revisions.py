"""
اختبارات جمع تصحيحات المحامي.
=============================================================================

تشغيل:
    python -m unittest discover -s tests -t . -v

`revisions.py` بلا أي تبعية خارجية وبلا إدخال/إخراج، فاختباره مباشر وسريع.

وأهمّ ما يُفحص هنا ليس الحساب بل **القرارات**:
  - لماذا لا نطبّع العربية في هذه المقارنة (بخلاف `citations.py`).
  - لماذا `autojunk=False` في difflib — وهي نقطة تُنتج نسبة تعديل مضخّمة
    بصمت في النصّ القانوني العربي تحديداً، لأنه مليء بكلمات متكرّرة.
  - لماذا نرفض حفظ تصحيح بلا تغيير.
"""

import time
import unittest

from revisions import (
    STYLE_TARGET,
    RevisionRejected,
    build_revision,
    edit_ratio,
    normalize_for_diff,
    quality_band,
    summarize,
)


# ==============================================================================
# ١. التجهيز للمقارنة
# ==============================================================================


class TestNormalizeForDiff(unittest.TestCase):
    """تطبيع الفراغات وحده — لا التطبيع العربي."""

    def test_collapses_whitespace(self):
        self.assertEqual(normalize_for_diff("أ   ب\tج"), "أ ب ج")

    def test_collapses_line_breaks(self):
        """
        فواصل الأسطر تتغيّر عند النسخ من Word وإليه بلا أن تتغيّر كلمة.

        ولو لم نطبّعها لظهرت نسبة تعديل ضخمة وهمية لمجرّد اختلاف التنسيق.
        """
        original = "البند الأول\nيلتزم الطرف الثاني\nبالسداد"
        pasted = "البند الأول يلتزم الطرف الثاني بالسداد"
        self.assertEqual(normalize_for_diff(original), normalize_for_diff(pasted))
        self.assertEqual(edit_ratio(original, pasted), 0.0)

    def test_empty_and_none(self):
        self.assertEqual(normalize_for_diff(""), "")
        self.assertEqual(normalize_for_diff(None), "")
        self.assertEqual(normalize_for_diff("   "), "")

    def test_does_not_fold_arabic_orthography(self):
        """
        ⚠️ قرار مقصود: لا نطبّع الألف ولا التاء المربوطة ولا التشكيل.

        السبب أن هذه مقارنة **أسلوب** لا مطابقة. فلو طبّعنا، لما احتُسبت
        إضافة المحامي للتشكيل تعديلاً — وهي تعديل أسلوبي حقيقي يجب أن يُقاس.
        (وهذا هو عكس ما يفعله `citations.py` عن قصد: هناك نتحقّق من نقل حرفي.)
        """
        self.assertNotEqual(normalize_for_diff("على المستأجر"), normalize_for_diff("علي المستاجر"))
        self.assertNotEqual(normalize_for_diff("مدة"), normalize_for_diff("مده"))


# ==============================================================================
# ٢. نسبة التعديل
# ==============================================================================


class TestEditRatio(unittest.TestCase):
    """مقياس واحد بسيط: كم تغيّرت الكلمات."""

    def test_identical_texts(self):
        text = "على المستأجر سداد الأجرة في أول خمسة أيام من كل شهر"
        self.assertEqual(edit_ratio(text, text), 0.0)

    def test_empty_inputs(self):
        self.assertEqual(edit_ratio("", ""), 0.0)
        self.assertEqual(edit_ratio(None, None), 0.0)

    def test_one_side_empty_is_total_change(self):
        """أحدهما فارغ والآخر لا: تغيير كامل — لا «صفر»."""
        self.assertEqual(edit_ratio("", "نصّ جديد"), 1.0)
        self.assertEqual(edit_ratio("نصّ قديم", ""), 1.0)

    def test_exact_value_on_known_case(self):
        """أربع كلمات، تغيّرت واحدة ← ربع."""
        self.assertEqual(edit_ratio("أ ب ج د", "أ ب ج ه"), 0.25)

    def test_word_level_value_is_interpretable(self):
        """
        المقارنة على الكلمات لا المحارف.

        الغرض **وضوح الرقم** لا دقّة أعلى: «كلمة من تسع تغيّرت» مفهومة
        للمحامي مباشرة، بخلاف نسبة محارف لا يعرف كيف يترجمها إلى حجم العمل.

        ومثالنا: تسع كلمات تغيّرت واحدة منها ← ١١٪ ≈ 1/9.
        """
        generated = "المادة الأولى من القانون المدني الإماراتي تنص على التعويض"
        corrected = "المادة الأولى من القانون المدني الإماراتي تنص على الفسخ"
        self.assertAlmostEqual(edit_ratio(generated, corrected), 1 / 9, places=3)

    def test_repetitive_legal_text_does_not_inflate_the_ratio(self):
        """
        🔑 الفحص الذي يبرّر `autojunk=False`.

        النصّ القانوني العربي مليء بكلمات متكرّرة («المادة»، «على»، «من»،
        «التي»). والافتراضي في difflib يعتبر العناصر الشائعة في المتتاليات
        الطويلة **نفايات** ويستبعدها من المقارنة — فتنتفخ نسبة التعديل ويظهر
        «تعديل ٤٠٪» على مسودّة لم تتغيّر فيها إلا كلمة واحدة.

        هنا: ٣٠٠ كلمة فيها ٥٠ تكراراً لكلمة واحدة، وتغيير **كلمة واحدة** فقط.
        """
        base = ["المادة"] * 50 + [f"كلمة{i}" for i in range(250)]
        generated = " ".join(base)
        corrected = " ".join(base[:-1] + ["معدّلة"])

        ratio = edit_ratio(generated, corrected)
        self.assertLess(
            ratio,
            0.05,
            f"نسبة مضخّمة: {ratio} — يبدو أن autojunk لم يُعطَّل",
        )
        self.assertAlmostEqual(ratio, 1 / 300, places=3)

    def test_ratio_is_bounded(self):
        """النسبة دائماً بين صفر وواحد — عقد يُعرض في الواجهة."""
        cases = [
            ("نصّ", "نصّ"),
            ("أ", "ب"),
            ("كلمة " * 100, "أخرى " * 100),
            ("نصّ عربي طويل جداً " * 50, "نصّ عربي قصير " * 10),
        ]
        for generated, corrected in cases:
            with self.subTest(generated=generated[:20]):
                ratio = edit_ratio(generated, corrected)
                self.assertGreaterEqual(ratio, 0.0)
                self.assertLessEqual(ratio, 1.0)

    def test_full_rewrite_is_high(self):
        ratio = edit_ratio("البند الأول يلتزم بالسداد", "المادة الخامسة تقضي بالفسخ")
        self.assertGreater(ratio, 0.5)

    def test_performance_on_a_realistic_document(self):
        """
        مستند واقعي (~٢٠٠٠ كلمة) يُقاس في زمن معقول.

        الفحص موجود لأن `autojunk=False` يزيد الزمن في الأسوأ، فلا بدّ من
        التأكّد أن الثمن مقبول لطول المستندات الفعلية.
        """
        paragraph = "المادة رقم ٢٤٦ من قانون المعاملات المدنية الإماراتي تنص على أن التعويض يشمل الضرر الأدبي. "
        generated = paragraph * 80
        corrected = generated.replace("يشمل", "يقتصر على", 1)

        started = time.perf_counter()
        ratio = edit_ratio(generated, corrected)
        elapsed = time.perf_counter() - started

        self.assertGreater(ratio, 0.0)
        self.assertLess(elapsed, 3.0, f"بطيء جداً: {elapsed:.2f} ثانية")


# ==============================================================================
# ٣. التصنيف المقروء
# ==============================================================================


class TestQualityBand(unittest.TestCase):
    """رقم مجرّد لا يعني شيئاً للمحامي — نُترجمه."""

    def test_bands(self):
        self.assertEqual(quality_band(0.0), "مطابق تقريباً")
        self.assertEqual(quality_band(0.04), "مطابق تقريباً")
        self.assertEqual(quality_band(0.10), "تعديل طفيف")
        self.assertEqual(quality_band(0.35), "تعديل جوهري")
        self.assertEqual(quality_band(0.80), "إعادة كتابة")
        self.assertEqual(quality_band(1.0), "إعادة كتابة")

    def test_boundaries_are_not_ambiguous(self):
        """كل نسبة تُصنَّف مرة واحدة — لا فراغ بين الحدود."""
        for value in (0.0, 0.05, 0.1999, 0.2, 0.4999, 0.5, 1.0):
            with self.subTest(value=value):
                self.assertTrue(quality_band(value))


# ==============================================================================
# ٤. بناء السجلّ
# ==============================================================================


class TestBuildRevision(unittest.TestCase):
    """يبني السجلّ ويرفض ما لا فائدة منه."""

    GENERATED = "البند الأول: يلتزم الطرف الثاني بسداد مبلغ عشرين ألف درهم."
    CORRECTED = "البند الأول: يلتزم الطرف الثاني بسداد مبلغ خمسة وعشرين ألف درهم خلال ثلاثين يوماً."

    def test_builds_a_valid_record(self):
        record = build_revision(self.GENERATED, self.CORRECTED, doc_type="عقد", prompt="وقائع")
        self.assertGreater(record.edit_ratio, 0.0)
        self.assertLessEqual(record.edit_ratio, 1.0)
        self.assertEqual(record.doc_type, "عقد")
        self.assertEqual(record.prompt, "وقائع")
        self.assertGreater(record.word_count, 0)
        self.assertEqual(record.quality_band, quality_band(record.edit_ratio))

    def test_rejects_empty_generated(self):
        with self.assertRaises(RevisionRejected) as ctx:
            build_revision("", self.CORRECTED)
        self.assertIn("المسودّة فارغة", str(ctx.exception))

    def test_rejects_empty_corrected(self):
        with self.assertRaises(RevisionRejected) as ctx:
            build_revision(self.GENERATED, "   ")
        self.assertIn("فارغة", str(ctx.exception))

    def test_rejects_unchanged_text(self):
        """
        🔑 تصحيح بلا تغيير لا يُحفظ.

        ولو حُفظ لضخّم العدّاد بلا فائدة، فأوهم المكتب أنه جمع ٢٠٠ زوج
        لتقليد أسلوبه وهو لم يجمع شيئاً.
        """
        with self.assertRaises(RevisionRejected) as ctx:
            build_revision(self.GENERATED, self.GENERATED)
        self.assertIn("لا فرق", str(ctx.exception))

    def test_rejects_unchanged_modulo_whitespace(self):
        """التصحيح الذي يختلف بالتنسيق وحده = بلا تغيير أيضاً."""
        reformatted = self.GENERATED.replace(" ", "\n", 3)
        with self.assertRaises(RevisionRejected):
            build_revision(self.GENERATED, reformatted)

    def test_optional_fields_default_to_none(self):
        record = build_revision(self.GENERATED, self.CORRECTED)
        self.assertIsNone(record.doc_type)
        self.assertIsNone(record.prompt)
        self.assertIsNone(record.session_id)

    def test_to_row_matches_the_table_columns(self):
        """
        الصفّ المُدرَج يطابق أعمدة `draft_revisions` في `schema.sql`.

        التعاقد مهمّ: عمود ناقص يعني إدراجاً يفشل، وعمود زائد يعني خطأ من
        القاعدة. و`quality_band` مشتقّة من `edit_ratio` فلا تُخزَّن — تجنّباً
        لتناقض محتمل بينهما لاحقاً.
        """
        row = build_revision(self.GENERATED, self.CORRECTED).to_row()
        self.assertEqual(
            set(row),
            {
                "generated_text",
                "corrected_text",
                "edit_ratio",
                "word_count",
                "doc_type",
                "prompt",
                "session_id",
            },
        )
        self.assertNotIn("quality_band", row)

    def test_row_is_json_serializable(self):
        import json

        json.dumps(build_revision(self.GENERATED, self.CORRECTED).to_row(), ensure_ascii=False)


# ==============================================================================
# ٥. الإحصاء
# ==============================================================================


class TestSummarize(unittest.TestCase):
    """التقدّم نحو تقليد الأسلوب — رقم يُتابع لا أمنية."""

    def test_empty(self):
        result = summarize([])
        self.assertEqual(result["count"], 0)
        self.assertEqual(result["average_edit_ratio"], 0.0)
        self.assertEqual(result["progress_percent"], 0.0)
        self.assertEqual(result["target"], STYLE_TARGET)
        self.assertEqual(sum(result["distribution"].values()), 0)

    def test_counts_and_average(self):
        result = summarize([0.1, 0.2, 0.3, 0.4])
        self.assertEqual(result["count"], 4)
        self.assertEqual(result["average_edit_ratio"], 0.25)

    def test_median_resists_an_outlier(self):
        """
        🔑 لماذا الوسيط مع المتوسّط؟

        مسودّة واحدة أُعيدت كتابتها بالكامل ترفع المتوسّط فتُخفي أن البقية
        شبه مطابقة. الوسيط يكشف ذلك.
        """
        ratios = [0.02, 0.02, 0.02, 0.02, 1.0]
        result = summarize(ratios)

        self.assertEqual(result["median_edit_ratio"], 0.02)
        self.assertGreater(result["average_edit_ratio"], 0.2)
        self.assertGreater(
            result["average_edit_ratio"],
            result["median_edit_ratio"] * 10,
            "المتوسّط يجب أن ينخدع بالشاذّة والوسيط لا",
        )

    def test_distribution_sums_to_count(self):
        result = summarize([0.01, 0.1, 0.3, 0.9])
        self.assertEqual(sum(result["distribution"].values()), 4)
        self.assertEqual(result["distribution"]["مطابق تقريباً"], 1)
        self.assertEqual(result["distribution"]["إعادة كتابة"], 1)

    def test_ignores_none_values(self):
        """صفّ بلا `edit_ratio` (قيمة فارغة في القاعدة) لا يُسقط الإحصاء."""
        result = summarize([0.1, None, 0.2])
        self.assertEqual(result["count"], 2)

    def test_progress_toward_style_target(self):
        result = summarize([0.1] * 50)
        self.assertEqual(result["target"], STYLE_TARGET)
        self.assertEqual(result["progress_percent"], 25.0)

    def test_progress_is_capped_at_one_hundred(self):
        """تجاوز الهدف لا يُنتج «٢٣٠٪» في الواجهة."""
        result = summarize([0.1] * (STYLE_TARGET + 100))
        self.assertEqual(result["progress_percent"], 100.0)

    def test_median_of_even_count(self):
        self.assertEqual(summarize([0.1, 0.3])["median_edit_ratio"], 0.2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
