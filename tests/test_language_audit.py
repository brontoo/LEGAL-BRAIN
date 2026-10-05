"""
اختبارات التدقيق اللغوي — عمل «سيبويه المُكشّر».
=============================================================================

تشغيل:
    python -m unittest discover -s tests -t . -v

حتمية بالكامل: بلا شبكة وبلا نموذج وبلا قاعدة بيانات.

وأهمّ اختبار فيها `test_catches_the_markdown_bug_that_actually_happened`:
المشروع **وقع فيه هذا العيب فعلاً** — ظهرت في مستند مولَّد علامات ``**`` و``###``
حرفياً، والموجّه يمنعها، والمستند يُنسخ إلى Word. فالفحص يحمي عيباً واقعاً لا
متخيَّلاً.
"""

import json
import unittest

from language_audit import LanguageReport, audit_language, summarize


CLEAN_DOCUMENT = (
    "لائحة دعوى تجارية\n"
    "\n"
    "المدعي: شركة الأفق للتجارة\n"
    "المدعى عليها: مؤسسة النخيل\n"
    "\n"
    "الوقائع:\n"
    "تتعامل المدعية مع المدعى عليها بموجب فواتير معتمدة لم تُسدد.\n"
    "\n"
    "الطلبات:\n"
    "1. إلزام المدعى عليها بسداد المبلغ.\n"
    "2. إلزامها بالرسوم والمصاريف.\n"
)


class TestCleanDocument(unittest.TestCase):
    """المستند السليم لا يُوسَم — وإلا صار الفحص ضجيجاً يُتجاهَل."""

    def test_clean_document_has_no_findings(self):
        report = audit_language(CLEAN_DOCUMENT)
        self.assertTrue(report.clean)
        self.assertEqual(report.findings, [])
        self.assertIn("سليمة", report.summary())

    def test_empty_and_none(self):
        for value in (None, "", "   "):
            with self.subTest(value=value):
                report = audit_language(value)
                self.assertEqual(report.findings, [])


class TestMarkdown(unittest.TestCase):
    """مخلفات Markdown — وهي عيب وقع في هذا المشروع فعلاً."""

    def test_catches_the_markdown_bug_that_actually_happened(self):
        """
        🔑 النصّ الذي ظهر حقيقةً في مستند مولَّد.

        الموجّه يمنع ``**`` و``###`` صراحةً، لكن النموذج خالفه. وهذا الفحص
        يلتقط المخالفة بدل أن تصل إلى Word.
        """
        document = "** لائحة دعوى تجارية **\n\n### موضوع الدعوى:\nمطالبة مالية."
        report = audit_language(document)

        self.assertFalse(report.clean)
        kinds = {item.kind for item in report.errors}
        self.assertEqual(kinds, {"markdown"})
        labels = " ".join(item.message for item in report.errors)
        self.assertIn("تسميك", labels)
        self.assertIn("وسم عنوان", labels)

    def test_catches_each_markdown_marker(self):
        cases = {
            "**نصّ**": "تسميك",
            "__نصّ__": "تسميك",
            "# عنوان": "وسم عنوان",
            "## عنوان فرعي": "وسم عنوان",
            "> اقتباس": "علامة اقتباس",
            "---": "خط أفقي",
            "- بند": "تعداد",
            "* بند": "تعداد",
            "| عمود | عمود |": "صفّ جدول",
        }
        for line, expected in cases.items():
            with self.subTest(line=line):
                report = audit_language(f"الوقائع:\n{line}\nالطلبات:")
                self.assertTrue(report.errors, f"لم يُكتشف: {line}")
                self.assertIn(expected, report.errors[0].message)

    def test_reports_the_line_number(self):
        document = "سطر أول\nسطر ثانٍ\n**سطر ثالث**"
        finding = audit_language(document).errors[0]
        self.assertEqual(finding.line, 3)

    def test_does_not_repeat_the_same_marker(self):
        """العلامة الواحدة تُبلَّغ مرة واحدة — لا عشرين سطراً من الضجيج."""
        report = audit_language("**أ**\n\n**ب**\n\n**ج**")
        self.assertEqual(len(report.errors), 1)


class TestPreamble(unittest.TestCase):
    """الافتتاح الحواري — عيب في مستند قانوني لا مسألة ذوق."""

    def test_catches_chatty_openers(self):
        for opener in ("بالتأكيد، إليك المستند:", "إليك لائحة الدعوى", "تفضل المستند المطلوب"):
            with self.subTest(opener=opener):
                report = audit_language(f"{opener}\nالبند الأول: السداد.")
                self.assertFalse(report.clean)
                self.assertEqual(report.errors[0].kind, "preamble")

    def test_does_not_flag_a_legitimate_legal_opening(self):
        """
        ⚠️ الفحص يجب ألّا يوسم صياغة قانونية سليمة.

        «بناءً على طلب الموكل» افتتاح مشروع في مذكرة، بخلاف «بناءً على طلبك»
        الحوارية. والتمييز بينهما مقصود في النمط.
        """
        legitimate = [
            "بناءً على طلب الموكل، نتقدم إلى عدالتكم بالآتي:",
            "الوقائع:",
            "أولاً: الديباجة",
            "بموجب عقد الإيجار المؤرخ في...",
        ]
        for line in legitimate:
            with self.subTest(line=line):
                report = audit_language(f"{line}\nالمادة الأولى: ...")
                self.assertTrue(report.clean, f"وُسم خطأً: {line}")

    def test_only_checks_the_first_real_line(self):
        """فقرة لاحقة تبدأ بـ«إليك» ليست افتتاحاً."""
        document = "الوقائع:\nثم قال المدعي: إليك ما يثبت ذلك."
        self.assertTrue(audit_language(document).clean)

    def test_skips_leading_blank_lines(self):
        report = audit_language("\n\n\nبالتأكيد، إليك المستند\nالبند الأول.")
        self.assertFalse(report.clean)


class TestPlaceholders(unittest.TestCase):
    """
    الفراغ في المستند — **ملاحظة لا خطأً**.

    ⚠️ وهذا التصنيف كان خطأً في أوّل نسخة، **والتشغيل الحقيقي هو الذي كشفه**:
    أنتج إنذاراً قانونياً فيه `الاسم والصفة [..]` و`التوقيع: [..]` (فراغان
    مشروعان ليملأهما المحامي)، فوسمته الأداة **أحد عشر خطأً أحمر**.

    والدرس أن الحدّ بين «خطأ يمنع التسليم» و«ملاحظة للعلم» **لا يُوضع بالحدس**:
    فحدسي الأول — «فراغ مجرّد مشروع، وحقل مسمّى خطأ» — لم يصمد، لأن النموذج
    لا يعرف الاسم في الحالتين.
    """

    def test_catches_placeholder_forms(self):
        for text in ("السيد [اسم المدعي]", "المبلغ {{ amount }}", "الاسم: ___", "رقم XXX"):
            with self.subTest(text=text):
                found = audit_language(f"الوقائع:\n{text}").notices
                self.assertTrue(found, f"لم يُكتشف: {text}")
                self.assertEqual(found[0].kind, "placeholder", f"عند: {text}")

    def test_a_blank_does_not_block_delivery(self):
        """
        🔑 **اختبار الحالة الحقيقية التي كشفت العيب.**

        فراغ التوقيع واسم الشركة في إنذار **سلوك صحيح**: النموذج لا يعرف
        التوقيع. فوسمُه خطأً كان يمنع تسليم مستند سليم.
        """
        notice = (
            "إنذار قانوني\n"
            "\n"
            "عن الشركة المنذرة:\n"
            "الاسم والصفة [..]\n"
            "التوقيع: [..]\n"
        )
        report = audit_language(notice)
        self.assertTrue(report.clean, "فراغ التوقيع لا يجوز أن يمنع التسليم")
        self.assertTrue(report.notices)
        self.assertTrue(all(item.kind == "placeholder" for item in report.notices))

    def test_identical_blanks_are_reported_once(self):
        """
        الفراغ المتكرّر ملاحظة **واحدة** لا إحدى عشرة.

        أداة تُنذر أحد عشر مرّة على الشيء نفسه لا تُقرأ، ومعها يضيع العيب
        الحقيقي حين يظهر.
        """
        document = "\n".join("[..]" for _ in range(11))
        report = audit_language(document)
        self.assertEqual(len(report.notices), 1)
        self.assertIn("تكرّر 11", report.notices[0].message)

    def test_distinct_blanks_are_separate_notices(self):
        report = audit_language("المدعي: [الاسم]\nالتوقيع: [..]")
        self.assertEqual(len(report.notices), 2)

    def test_underscores_are_a_blank_not_markdown(self):
        """
        `___` فراغ لملء لا تسميك Markdown.

        القاعدتان تتصادمان ظاهرياً، والفصل بينهما مهمّ: لو صُنّف «مخلّف
        Markdown» لضاع معناه ولو كان ملاحظة.
        """
        report = audit_language("الاسم: ___")
        self.assertEqual(report.notices[0].kind, "placeholder")
        self.assertEqual(report.errors, [])

    def test_real_markdown_underline_bold_is_still_caught(self):
        """وفي المقابل `__نصّ__` تسميك حقيقي — فيبقى **خطأً**."""
        report = audit_language("__الوقائع__")
        self.assertEqual(report.errors[0].kind, "markdown")

    def test_placeholder_is_not_also_reported_as_latin(self):
        """`XXX` عيب واحد لا اثنان — وإلا تضاعف الضجيج."""
        report = audit_language("رقم XXX")
        self.assertEqual(len(report.findings), 1)
        self.assertEqual(report.findings[0].kind, "placeholder")

    def test_reports_the_line_number(self):
        report = audit_language("الوقائع:\nسطر سليم.\nالمدعي: [الاسم]")
        self.assertEqual(report.notices[0].line, 3)

    def test_catches_placeholder_anywhere_not_just_first_line(self):
        report = audit_language("الوقائع:\nسطر سليم.\nالمدعي: [الاسم]")
        self.assertEqual(report.notices[0].kind, "placeholder")


class TestNotices(unittest.TestCase):
    """ملاحظات للعلم — لا تمنع التسليم."""

    def test_latin_words_are_a_notice_not_an_error(self):
        """أسماء الشركات والمصطلحات مشروعة — فلا تُصنَّف خطأً."""
        report = audit_language("الوقائع:\nتعاملت المدعية مع شركة Alpha Trading LLC.")
        self.assertTrue(report.clean, "الملاحظة يجب ألّا تمنع التسليم")
        self.assertEqual(len(report.notices), 1)
        self.assertEqual(report.notices[0].kind, "latin")

    def test_a_multi_word_name_is_one_notice(self):
        """
        اسم شركة من ثلاث كلمات = ملاحظة واحدة لا ثلاث.

        ثلاث ملاحظات لاسم واحد ضجيج يُغرق التقرير فيُتجاهَل كله.
        """
        report = audit_language("شركة Alpha Trading LLC")
        self.assertEqual(len(report.notices), 1)
        self.assertIn("Alpha Trading LLC", report.notices[0].sample)

    def test_separate_latin_names_are_separate_notices(self):
        report = audit_language("التعامل مع Alpha وبعدها Beta")
        self.assertEqual(len(report.notices), 2)

    def test_repeated_long_line_is_a_notice(self):
        line = "يلتزم الطرف الثاني بسداد كامل المبلغ المتفق عليه خلال ثلاثين يوماً."
        report = audit_language(f"الوقائع:\n{line}\n{line}")
        self.assertTrue(report.clean)
        self.assertEqual(report.notices[0].kind, "repetition")

    def test_two_address_blocks_are_not_a_paste_artifact(self):
        """
        🔑 **اختبار الحالة الحقيقية الثانية.**

        إنذار قانوني فيه كتلتا عنوان — للمنذَر إليه وللمنذِر — فتتكرّر فيه أسطر
        العنوان والهاتف والبريد. **وهذا هو الصواب**، ولا تُكتب عناوين الطرفين
        بغير التكرار. فوسمُه «أثر لصق مزدوج» كان وسمَ الصيغة القانونية السليمة
        بالعطب.
        """
        notice = (
            "إلى المنذر إليه:\n"
            "العنوان: .....................................................\n"
            "رقم الهاتف: .....................................................\n"
            "البريد الإلكتروني: .....................................................\n"
            "\n"
            "من المنذر:\n"
            "العنوان: .....................................................\n"
            "رقم الهاتف: .....................................................\n"
            "البريد الإلكتروني: .....................................................\n"
        )
        report = audit_language(notice)
        self.assertEqual(report.notices, [], "كتلتا العنوان بنية لا لصق مزدوج")

    def test_a_far_apart_repeat_is_not_flagged(self):
        line = "يلتزم الطرف الثاني بسداد كامل المبلغ المتفق عليه خلال ثلاثين يوماً."
        filler = "\n".join(f"بند رقم {index}: نصّ تعبئة." for index in range(5))
        report = audit_language(f"{line}\n{filler}\n{line}")
        self.assertEqual(report.notices, [])

    def test_adjacent_repeat_is_flagged_even_with_a_blank_between(self):
        """واللصق المزدوج غالباً يفصل بينه سطر فارغ — فيُلتقط."""
        line = "يلتزم الطرف الثاني بسداد كامل المبلغ المتفق عليه خلال ثلاثين يوماً."
        report = audit_language(f"{line}\n\n{line}")
        self.assertEqual(report.notices[0].kind, "repetition")

    def test_short_repeated_lines_are_not_flagged(self):
        """«المادة» و«البند» تتكرّر بحقّ — ووسمها يُغرق التقرير."""
        report = audit_language("المادة\nالمادة\nالمادة")
        self.assertEqual(report.notices, [])


class TestReportShape(unittest.TestCase):
    """شكل التقرير — يُبثّ كـ JSON إلى الواجهة."""

    def test_errors_come_before_notices(self):
        document = "الوقائع:\nشركة Alpha\n**تسميك**"
        findings = audit_language(document).findings
        severities = [item.severity for item in findings]
        self.assertEqual(severities, sorted(severities, key=lambda s: 0 if s == "error" else 1))

    def test_summary_counts(self):
        report = audit_language("**أ**\nشركة Alpha")
        self.assertFalse(report.clean)
        self.assertEqual(len(report.errors), 1)
        self.assertEqual(len(report.notices), 1)
        self.assertIn("عيب", report.summary())

    def test_summarize_is_json_serializable(self):
        payload = summarize(audit_language("**أ**\n[فراغ]"))
        json.dumps(payload, ensure_ascii=False)
        # `**` خطأ، و`[فراغ]` ملاحظة — والفرق هو ما يمنع التسليم وما لا يمنعه
        self.assertEqual(payload["error_count"], 1)
        self.assertEqual(payload["notice_count"], 1)
        self.assertIn("findings", payload)

    def test_samples_are_truncated(self):
        """المقتطف قصير: لا تُبَثّ المسودّة كاملة في كل ملاحظة."""
        report = audit_language("**" + "ط" * 500 + "**")
        self.assertLessEqual(len(report.findings[0].sample), 80)

    def test_findings_are_immutable(self):
        """الملاحظة لا تُعدَّل بعد إنشائها."""
        finding = audit_language("**أ**").findings[0]
        with self.assertRaises(Exception):
            finding.message = "غير ذلك"  # type: ignore[misc]


class TestModuleGuarantees(unittest.TestCase):
    """ضمانات معمارية — كـ `citations.py`: بلا تبعيات وبلا شبكة."""

    def test_imports_are_stdlib_only(self):
        import pathlib
        import re as _re

        import language_audit

        source = pathlib.Path(language_audit.__file__).read_text(encoding="utf-8")
        imported = set(
            _re.findall(r"^(?:from|import)\s+([A-Za-z_][\w\.]*)", source, _re.MULTILINE)
        )
        allowed = {"__future__", "re", "dataclasses", "typing"}
        self.assertTrue(imported <= allowed, f"استيرادات: {sorted(imported - allowed)}")

    def test_no_environment_or_network_access(self):
        import pathlib

        import language_audit

        source = pathlib.Path(language_audit.__file__).read_text(encoding="utf-8")
        for forbidden in ("os.environ", "requests.", "socket", "http"):
            self.assertNotIn(forbidden, source)

    def test_default_report_is_independent(self):
        first, second = LanguageReport(), LanguageReport()
        first.findings.append("x")  # type: ignore[arg-type]
        self.assertEqual(second.findings, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
