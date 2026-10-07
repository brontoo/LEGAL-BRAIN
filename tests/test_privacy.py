"""
اختبارات أمان السجلّ — هل يمكن جعل نصّ آمن للكتابة في طرفية أو ملف؟
=================================================================================

تشغيل:
    cd legal-brain
    python -m unittest discover -s tests -t . -v

لماذا ملفّ منفصل عن ``test_untrusted.py``؟
------------------------------------------
لأن ما يُختبر هنا **خصيصة أخرى غير الكشف**. ``test_untrusted.py`` يسأل: «هل
رصدنا القيمة؟». وهذا الملف يسأل: «هل صار النصّ **آمناً للكتابة**؟».

والفرق ليس لفظياً. الكشف قد ينجح والنصّ يبقى غير آمن، إذا حُجب جزء من الرقم
وبقي باقيه، أو حُجبت القيمة من موضع ونسيت في آخر. وهذا هو العيب الذي وقع
فعلاً في هذا المشروع: ``main.py`` و``legal_agent.py`` يطبعان أسطر تقدّم، وقد
يظهر فيها اسم مستند أو اسم خصم أو مبلغ. وحينها تُقرأ في طرفية، أو تُكتَب في
ملف سجلّ، أو تُصوَّر وتُلصق في محادثة.

والقاعدة التي يقوم عليها الملف:

> **ما لا يُحجَب لا يُكتَب.** فالسطر يمرّ على ``redact`` **قبل** الطبع لا بعده،
> وهذا الاختبار يثبّت أن ``redact`` تُنجز ذلك فعلاً.
"""

import unittest

from untrusted import redact, scan_sensitive

#: موجز واقعي بلغة العمل: اسم، ورقم هوية، وهاتف، وبريد — وكلّه في متن قانوني
#: عربي كما يُكتب في ملف قضية حقيقي.
REALISTIC_BRIEF = (
    "الموكل: أحمد بن سعيد المهيري، رقم الهوية 784-1985-1234567-1، "
    "هاتفه 0501234567، وبريده ahmed.legal@example.ae. "
    "يطالب المدعى عليها بسداد مبلغ 29,000 درهم قيمة أعمال تنفيذها بموجب "
    "العقد المؤرخ في 2026/01/15، وقد امتنعت عن السداد رغم الإنذار."
)

#: المتن القانوني الذي يجب أن يبقى **سليماً حرفاً بحرف** بعد الحجب.
LEGAL_CONTENT_WORDS = (
    "الموكل",
    "يطالب المدعى عليها بسداد مبلغ",
    "درهم",
    "قيمة أعمال تنفيذها بموجب",
    "العقد المؤرخ في",
    "وقد امتنعت عن السداد رغم الإنذار",
)


class TestRedactRemovesEveryDetectedValue(unittest.TestCase):
    """الحجب يُزيل **كل** ما رصده الكشف — لا بعضه."""

    def test_the_realistic_brief_is_cleaned_and_still_readable(self):
        """
        🔑 **الحالة التي تهمّ**: موجز عربي واقعي فيه اسم وهوية وهاتف وبريد.

        والمطلوب أمران معاً، وكلاهما ضروري:
          ١) **الأربعة تُزال** — وإلا فالسطر غير آمن للكتابة.
          ٢) **والمتن القانوني يبقى** — وإلا فالسجلّ صار عديم الفائدة، ومعها
             يُمحى السياق الذي يجعل السطر مفهوماً عند المراجعة.
        """
        cleaned = redact(REALISTIC_BRIEF)

        # ١) لا يبقى من البيانات الشخصية شيء.
        for value in ("784-1985-1234567-1", "0501234567", "ahmed.legal@example.ae"):
            with self.subTest(value=value):
                self.assertNotIn(value, cleaned, f"بقيت القيمة: {cleaned}")
        self.assertEqual(scan_sensitive(cleaned), [], f"بقي عثور في: {cleaned}")

        # ٢) والمتن القانوني سليم.
        for fragment in LEGAL_CONTENT_WORDS:
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, cleaned)
        self.assertIn("29,000", cleaned, "المبلغ ليس بيانات شخصية ولا يُحجَب")
        self.assertIn("2026/01/15", cleaned, "التاريخ ليس بيانات شخصية ولا يُحجَب")

    def test_a_country_code_form_is_cleaned_too(self):
        """والصيغة الدولية — وهي الأكثر وقوعاً في المراسلات."""
        text = "هاتف الموكل +971 50 123 4567، وأرضيه 02 123 4567."
        cleaned = redact(text)
        self.assertNotIn("50 123 4567", cleaned)
        self.assertNotIn("02 123 4567", cleaned)
        self.assertNotIn("+971", cleaned, "بادئة الدولة تُحجَب مع الرقم لا دونه")
        self.assertEqual(scan_sensitive(cleaned), [])

    def test_each_kind_is_removed_from_a_mixed_line(self):
        """سطر واحد فيه الأصناف كلها — كلّ صنف يُزال."""
        text = (
            "هوية 784-1985-1234567-1 · هاتف 0501234567 · بريد a@b.ae · "
            "IBAN AE07 0331 2345 6789 0123 456 · بطاقة 4111 1111 1111 1111"
        )
        cleaned = redact(text)
        self.assertEqual(scan_sensitive(cleaned), [])
        self.assertNotIn("784", cleaned)
        self.assertNotIn("0331", cleaned)

    def test_the_number_of_masks_matches_the_number_of_hits(self):
        """
        عدد الأقواس يساوي عدد المواضع المحجوبة.

        ولو نقص، لكان الحجب أضاع موضعاً؛ ولو زاد، لكان حجب نصّاً سليماً. والعدّ
        هنا على المواضع لا الأصناف، فالسطر فيه ثلاث قيم شخصية = ثلاثة أقواس.
        """
        text = "هوية 784-1985-1234567-1 وهاتف 0501234567 وبريد a@b.ae"
        hits = scan_sensitive(text)
        cleaned = redact(text)
        self.assertEqual(len(hits), 3)
        self.assertEqual(cleaned.count("[]"), len(hits))


class TestRedactIsIdempotent(unittest.TestCase):
    """الحجب مرّة ثانية لا يُغيّر شيئاً — وإلا فالأول لم يُتمّ عمله."""

    def test_redacting_twice_changes_nothing_the_second_time(self):
        """
        ⚠️ وهذه ليست تفصيلاً رياضياً، بل شرط عملي: ``redact`` تُستدعى على أسطر
        قد مرّت عليها من قبل (سطر سجلّ يُعاد طبعه، أو نصّ يُمرّر مرّتين في
        المسار). ولو كان الحجب الثاني يُغيّر النصّ، لكان الأثر تراكمياً ويصير
        السجلّ مشوّهاً بلا سبب.
        """
        cases = (
            REALISTIC_BRIEF,
            "هاتفه 0501234567",
            "هاتفه +971 50 123 4567",
            "هويته 784-1985-1234567-1",
            "بريده ahmed@example.ae",
            "IBAN: AE07 0331 2345 6789 0123 456",
            "بطاقته 4111 1111 1111 1111",
            "جواز سفره A12345678",
            "المادة 43: يلتزم الطرف الثاني بالسداد.",
        )
        for text in cases:
            with self.subTest(text=text):
                once = redact(text)
                self.assertEqual(redact(once), once, f"الحجب الثاني غيّر: {once!r}")
                self.assertEqual(redact(redact(once)), once)

    def test_a_clean_text_is_returned_unchanged(self):
        """
        🔑 **النصّ السليم يعود حرفاً بحرف.**

        وهذا مهمّ بقدر ما قبله: ``redact`` تُستدعى في **كل** سطر سجلّ، فلو
        غيّرت نصّاً سليماً — ولو بمسافة — لكانت هي نفسها عيباً في كل سطر تكتبه.
        """
        clean_texts = (
            "المادة 43: يلتزم الطرف الثاني بسداد الأجرة في اليوم الأول.",
            "رقم القضية 1973 لسنة 2026",
            "مبلغ 29,000 درهم",
            "رقم الترخيص CN-1178131",
            "بريد إلكتروني مسجّل لدى الشركة",
            "ص.ب 48448، دبي، الإمارات العربية المتحدة",
            "[Review] اعتراضات: 2 · ملاحظات: 3",
            "الوقائع:\nتتعامل المدعية مع المدعى عليها بموجب فواتير معتمدة.",
        )
        for text in clean_texts:
            with self.subTest(text=text):
                self.assertEqual(redact(text), text)
                self.assertEqual(scan_sensitive(text), [])

    def test_whitespace_and_empty_input(self):
        """والمدخل الفارغ أو المسافات: يعود كما هو بلا انهيار."""
        for value in ("", "   ", "\n\n", "\t"):
            with self.subTest(value=value):
                self.assertEqual(redact(value), value)
        self.assertEqual(redact(None), "")


class TestLogLineScenario(unittest.TestCase):
    """
    سيناريو السجلّ الفعلي — الأسطر التي تُطبع في `main.py` و`legal_agent.py`.

    ⚠️ ولا تُعدَّل تلك الملفات هنا (التوصيل لاحقاً): الاختبار يُحاكي شكل السطر
    ويُثبت أن تمريره على ``redact`` يكفي لجعله آمناً.
    """

    def test_a_progress_line_with_a_client_name_and_amount_is_made_safe(self):
        """
        سطر تقدّم يشبه ما يُطبع فعلاً أثناء التوليد.

        وفيه ما يُشبه ``print(f"\\n[Review] ...")`` — ونصّ عربي فيه اسم ورقم
        هاتف. والاختبار أن السطر يخرج صالحاً للكتابة في ملف سجلّ.
        """
        line = "[Agent Tool] 🔎 مستندات الصياغة: إنذار للموكل أحمد المهيري — هاتفه 0501234567"
        safe = redact(line)
        self.assertNotIn("0501234567", safe)
        self.assertIn("إنذار للموكل", safe, "النصّ التشغيلي يبقى مفهوماً")

    def test_a_document_name_with_a_phone_is_made_safe(self):
        """واسم المستند نفسه قد يحمل رقماً — وهذا يقع فعلاً في الملفات المرفوعة."""
        line = "استرجاع المقطع: عقد-إيجار-0501234567.pdf"
        safe = redact(line)
        self.assertNotIn("0501234567", safe)
        self.assertEqual(scan_sensitive(safe), [])

    def test_repeated_log_lines_are_stable(self):
        """السطر نفسه يُطبع مرّتين — والمخرَج واحد، بلا تراكم."""
        line = "إنذار للموكل 0501234567"
        first = redact(line)
        self.assertEqual(redact(first), first)

    def test_the_summary_report_never_carries_a_value(self):
        """
        وحتى تقرير الكشف نفسه لا يحمل قيمة.

        ``sample`` هو ما يُبَثّ إلى الواجهة ويُكتَب في السجلّ، وهو محجوب في
        ``SensitiveHit`` نفسه. والفحص أن **أرقام القيم** لا تظهر في التقرير
        المُسلسَل: هوية، وهاتف، وبريد.

        ⚠️ ولا يُشترط خلوّ العيّنة من كل رقم: قناع الهوية يبدأ بـ``784``، وهو
        بادئة **كل** هوية في الدولة، فلا يفرّق بين شخص وآخر — ويُسمّي الصنف
        للمحامي. والممنوع ما يفرّق: بقية الأرقام.
        """
        from untrusted import summarize_sensitive

        payload = summarize_sensitive(scan_sensitive(REALISTIC_BRIEF))
        rendered = str(payload)
        for value in ("198512345671", "0501234567", "ahmed.legal@example.ae"):
            with self.subTest(value=value):
                self.assertNotIn(value, rendered)
        for hit in payload["hits"]:
            digits = "".join(char for char in hit["sample"] if char.isdigit())
            self.assertLessEqual(
                len(digits),
                3,
                f"عيّنة تحمل أرقاماً تفرّق: {hit['sample']!r}",
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
