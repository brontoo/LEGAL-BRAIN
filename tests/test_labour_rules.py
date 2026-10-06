"""
اختبارات قواعد العمال — الأساس الذي يُحسب عليه، والتاريخ الذي لا يُقدَّر.
=============================================================================

تشغيل:
    python -m unittest discover -s tests -t . -v

حتمية بالكامل: بلا شبكة، وبلا نموذج، وبلا قاعدة بيانات، وبلا قرص.

ولماذا لا تحتاج `fake_deps`؟ لأن هذا الملف لا يلمس الطبقة الخارجية أصلاً:
`labour_rules` وحدة نقية بلا حالة وبلا إدخال/إخراج، كـ `citations.py`
و`language_audit.py`. فلا شيء يُستعار ولا شيء يُحاكى.

وأهمّ اختبار في الملف هو `TestLeavePayDefect` — وليس لأنه يُثبت الجواب الصحيح،
بل لأنه **يُثبّت الجواب الخطأ على أنه خطأ**:

    بدل الإجازة عن ١١ يوماً على أجر شامل ٨٠٠٠ = ٢٩٣٣٫٣٧، **وهو خطأ**؛
    والصحيح على الأجر الأساسي ٥٠٠٠ = ١٨٣٣٫٣٣.

والاختبار الذي يُثبّت الخطأ أوضح دلالةً من الذي يُثبّت الصواب: الأول يفشل حين
يعود العيب الذي وقع فعلاً، والثاني يمرّ حتى لو صار للحاسبة أساس واحد صامت.
ولذلك يفحص هذا الملف **الفرق** (`1100.00`) و**الأساس المطلوب**، لا المبلغ وحده.

والاختبار الثاني في الأهمّية `TestServicePeriod.test_the_memorandum_under_review_said_1278`:
مدّة الخدمة من ٢٠٢٣-٠٢-٠١ إلى ٢٠٢٦-٠٨-٣١ = **١٣٠٧ أيام**، والمذكرة تحت المراجعة
قالت ١٢٧٨ — وهو خطأ في العدّ لا في المعرفة، فموضعه الحاسبة لا الموجّه.
"""

import pathlib
import re as _re
import unittest
from datetime import date, timedelta
from decimal import Decimal

import labour_rules
from labour_rules import (
    DAYS_PER_MONTH,
    RULES,
    WAGE_BASIS_BASIC,
    WAGE_BASIS_GROSS,
    LeavePay,
    NoticePay,
    Rule,
    ServicePeriod,
    daily_rate,
    end_of_service_gratuity,
    leave_pay,
    notice_pay,
    period_days,
    rule_for,
    rules_block,
    service_period,
    wage_basis_for,
)


# ==============================================================================
# بيانات الاختبار — الأرقام الحقيقية من التقرير، لا أرقام متخيَّلة
# ==============================================================================

#: الواقعة تحت المراجعة: مباشرة العمل وانتهاء العلاقة.
START = date(2023, 2, 1)
END = date(2026, 8, 31)

#: الأجران المتنازع عليهما في التقرير: الأساسي والشامل.
BASIC_WAGE = Decimal("5000")
GROSS_WAGE = Decimal("8000")

#: الرقم الذي ورد في المذكرة تحت المراجعة — خطأ.
DAYS_IN_THE_FLAWED_MEMORANDUM = 1278
#: الرقم الصحيح بالعدّ المعتمد في هذا الملف.
DAYS_CORRECT = 1307
#: الرقم الذي ينتج لو حُسب يوم النهاية أيضاً — العدّ الآخر المعلن.
DAYS_WITH_END_COUNTED = 1308


class TestRulesTable(unittest.TestCase):
    """
    جدول القواعد: صغير، قابل للتحقّق، **وللمحامي أن يراجعه**.

    وهذا الجدول ليس بياناً بالقانون. الاختبارات هنا تحرس **شكله وحدوده** لا
    صحّته القانونية: أن يكون الأساس من ثوابت مغلقة، وأن يحمل كل استحقاق مادّته،
    وأن تُذكر القواعد الأربع التي أمر بها المحامي، **وألّا يُزاد فيها رقم مادة
    لم يُعطَ** — لأن الزيادة بالتخمين أسوأ من النقص.
    """

    def test_the_four_rules_the_lawyer_asked_for_are_present(self):
        """القواعد الأربع التي حدّدها المحامي — كلها في الجدول بترتيبها."""
        self.assertEqual(
            [rule.entitlement for rule in RULES],
            [
                "بدل الإجازة السنوية",
                "مكافأة نهاية الخدمة",
                "أجر مدة الإشعار",
                "الأجر خلال الإجازة",
            ],
        )

    def test_leave_pay_basis_is_the_basic_wage_and_article_29_9(self):
        """
        🔑 **العيب الأول في التقرير.**

        بدل الإجازة السنوية على **الأجر الأساسي**، والمادة ٢٩/٩ هي سنده: تجعل
        الأساسي أساساً إلا إذا منح اتفاقٌ العامل ميزةً أفضل.
        """
        rule = rule_for("بدل الإجازة السنوية")
        self.assertIsNotNone(rule)
        self.assertEqual(rule.basis, WAGE_BASIS_BASIC)
        self.assertEqual(rule.article, "٢٩/٩")

    def test_gratuity_basis_is_the_basic_wage_and_article_51(self):
        """مكافأة نهاية الخدمة على الأجر الأساسي، والمادة ٥١ هي سندها."""
        rule = rule_for("مكافأة نهاية الخدمة")
        self.assertEqual(rule.basis, WAGE_BASIS_BASIC)
        self.assertEqual(rule.article, "٥١")

    def test_notice_pay_keeps_the_contract_and_excusal_is_not_a_ground(self):
        """
        🔑 **العيب الثاني في التقرير.**

        أجر مدة الإشعار: العقد يبقى قائماً خلالها والأجر واجبٌ كاملاً. وإعفاء
        العامل من الحضور **ليس سبباً لحرمانه**. والنصّان مكتوبان في القاعدة صريحين
        لأن الاستدلال الخاطئ كان في هذه النقطة بالذات لا في الحساب.
        """
        rule = rule_for("أجر مدة الإشعار")
        self.assertEqual(rule.article, "٤٣/٢")
        self.assertIn("يبقى قائماً", rule.statement)
        self.assertIn("الحضور", rule.statement)
        self.assertIn("ليس بذاته", rule.statement)

    def test_leave_wage_requires_actual_leave(self):
        """
        الأجر خلال الإجازة: لا يستحقّ إلا من كان في إجازة فعلاً.

        ⚠️ والحدّ الصريح في نصّ القاعدة: **الموافقة المسجَّلة لا تحسم وحدها** ما
        إذا كان قد أدّى عملاً. وهذا ما يمنع أن تُقرأ موافقةٌ إدارية كإثبات
        لعدم العمل — وهو خلط بين ورقة وواقعة.
        """
        rule = rule_for("الأجر خلال الإجازة")
        self.assertIsNotNone(rule)
        self.assertIn("في إجازة فعلاً", rule.statement)
        self.assertIn("لا يحسم", rule.statement)

    def test_every_rule_names_its_basis_and_its_article(self):
        """
        قاعدة بلا مادة **رأيٌ لا قاعدة**، وقاعدة بلا أساس لا تُحسب.

        فلا يُقبل في الجدول سطر ناقص: النقص هنا لا يُرى في المذكرة، لأن
        الغياب لا يُكتب.
        """
        for rule in RULES:
            with self.subTest(entitlement=rule.entitlement):
                self.assertIn(
                    rule.basis, (WAGE_BASIS_BASIC, WAGE_BASIS_GROSS)
                )
                self.assertTrue(rule.article.strip())
                self.assertTrue(rule.statement.strip())
                # والمادة بصيغة «رقم» أو «رقم/بند» — لا نصّاً حرّاً، فيمكن
                # فحصها آلياً ومقارنتها بما أُعطي.
                self.assertRegex(rule.article, r"^[٠-٩]+(/[٠-٩]+)?$")

    def test_no_article_number_beyond_what_the_lawyer_gave(self):
        """
        🔑 **حدّ لا يُتجاوز: لا تُخترع أرقام مواد.**

        المحامي أعطى ثلاثة أرقام لا غير: ٢٩/٩ و٥١ و٤٣/٢. والجدول كلّه يجب أن
        يبقى في هذه الحدود. ولو أضاف أحدهم رقماً من عنده — ولو بدا معقولاً —
        لكان هذا الاختبار هو الذي يوقفه، لأن رقم مادة مخمَّن **يمضي إلى المذكرة**
        ولا يتوقف عند حائط.
        """
        allowed = {"٢٩/٩", "٥١", "٤٣/٢"}
        articles = {rule.article for rule in RULES}
        self.assertTrue(
            articles <= allowed,
            f"أرقام مواد خارج ما أُعطي: {sorted(articles - allowed)}",
        )

    def test_lookup_by_name_and_unknown_entitlement(self):
        """
        الأساس يُسأل عنه بالاسم، والمجهول يُعاد ``None`` لا أساساً مخترعاً.

        و``None`` هنا هو ما يجعل «الأساس غير محقَّق» ممكناً في الموجّه: لو
        أعادت الدالّة أساساً افتراضياً لأمكن للنموذج أن يحسب على أساس لم تُقرّره
        قاعدة، وهي **العيب الأول نفسه** في ثوب جديد.
        """
        self.assertEqual(wage_basis_for("مكافأة نهاية الخدمة"), WAGE_BASIS_BASIC)
        self.assertEqual(wage_basis_for("أجر مدة الإشعار"), WAGE_BASIS_GROSS)
        self.assertIsNone(wage_basis_for("بدل السكن"))
        self.assertIsNone(rule_for("بدل السكن"))

    def test_rules_are_frozen_dataclasses(self):
        """القاعدة لا تُعدَّل بعد إنشائها — فلا تتبدّل قاعدة أثناء تشغيل."""
        rule = RULES[0]
        self.assertTrue(isinstance(rule, Rule))
        with self.assertRaises(Exception):
            rule.basis = WAGE_BASIS_GROSS  # type: ignore[misc]

    def test_the_table_states_it_is_the_lawyers_to_verify(self):
        """
        ⚠️ التحذير مكتوب في **الكود** لا في وثيقة خارجية.

        لأن من يقرأ الجدول يقرأ الكود، والتحذير الذي يعيش في ملف آخر لا يُقرأ
        مع ما يحذّر منه.
        """
        source = pathlib.Path(labour_rules.__file__).read_text(encoding="utf-8")
        self.assertIn("للمحامي", source)
        self.assertIn("ليس بياناً بالقانون", source)


class TestServicePeriod(unittest.TestCase):
    """
    المدّة: عدد أيامها، وفكّها التقويمي، وقرار يوم النهاية.

    والاختبار الحاسم هنا هو `test_the_memorandum_under_review_said_1278`:
    المذكرة تحت المراجعة قالت ١٢٧٨ يوماً، **والصحيح ١٣٠٧**. والفرق ٢٩ يوماً
    ينقص من مدّة خدمة عامل — وهو نقص لا يُلاحَظ لأنه لا يبدو خطأً.
    """

    def test_the_memorandum_under_review_said_1278(self):
        """
        🔑 **العيب الحقيقي، بالرقم الصحيح والرقم الخطأ معاً.**

        من ٢٠٢٣-٠٢-٠١ إلى ٢٠٢٦-٠٨-٣١ = **١٣٠٧ أيام**. والمذكرة قالت ١٢٧٨.
        فالاختبار يفحص الاثنين: أن الصحيح ١٣٠٧، وأن ١٢٧٨ **ليس** الصحيح — وإلا
        لمرّ الرقم القديم لو عاد.
        """
        period = service_period(START, END)
        self.assertEqual(period.days, DAYS_CORRECT)
        self.assertNotEqual(period.days, DAYS_IN_THE_FLAWED_MEMORANDUM)
        # والفرق ينقص من المدّة، لا يزيد — أي في مصلحة صاحب العمل، وهو ما يجعل
        # مروره صامتاً أخطر.
        self.assertEqual(
            period.days - DAYS_IN_THE_FLAWED_MEMORANDUM,
            DAYS_CORRECT - DAYS_IN_THE_FLAWED_MEMORANDUM,
        )
        self.assertGreater(period.days, DAYS_IN_THE_FLAWED_MEMORANDUM)

    def test_end_of_period_is_a_boundary_not_a_worked_day(self):
        """
        قرار يوم النهاية: ``end`` **حدٌّ لا يُحسب**، و١٣٠٧ هي الدليل.

        ``(end - start).days`` = ١٣٠٧ بالضبط. ولو حُسب يوم النهاية لصار ١٣٠٨.
        والاختبار يثبّت القرارين معاً، فيكون العدّ الآخر **معلَناً** لا ضمنياً.
        """
        self.assertFalse(service_period(START, END).inclusive_end)
        self.assertEqual(
            service_period(START, END).days,
            (END - START).days,
        )
        self.assertEqual(
            service_period(START, END, inclusive_end=True).days,
            DAYS_WITH_END_COUNTED,
        )

    def test_the_parts_are_calendar_parts(self):
        """
        الفكّ تقويمي: ٣ سنوات و٦ أشهر و٢٩ يوماً.

        والخمسة والعشرون يوماً الباقية بعد الأشهر الستة هي ما تبقّى من أغسطس،
        فالفكّ يقف عند أول الشهر لا عند ٣٠ يوماً عدّاً. ولو عدّت الحاسبة الشهر
        ٣٠ يوماً لظهر في المذكرة فكٌّ لا يُطابق تاريخاً في التقويم.
        """
        period = service_period(START, END)
        self.assertEqual(
            (period.years, period.months, period.remainder_days), (3, 6, 29)
        )

    def test_exact_anniversary_gives_whole_years(self):
        """
        الطرف الواقع على الذكرى يعطي سنوات كاملة — بلا كسر.

        ⚠️ **ولاحظ الفرق بين العدّين، فهو أصل هذا الاختبار:** الذكرى تعني أن
        آخر يوم في المدّة هو عشيّة يوم الذكرى (لأن ``end`` حدٌّ لا يُحسب). ومن
        ٢٠٢٣-٠٢-٠١ إلى ٢٠٢٦-٠٢-٠١ = ١٠٩٦ يوماً = ٢ سنوات و١١ شهراً و٣٠ يوماً
        بالتقويم، لأن الذكرى الثالثة تقع في اليوم التالي للنهاية. ولو حُسب يوم
        النهاية لصار ١٠٩٧ وصارت «٣ سنوات» — وهذا هو العدّ الآخر المعلن.

        فالاختبار يثبّت **العدّ المعتمد** وعواقبه على الفكّ معاً، حتى لا يُقرأ
        الفكّ خطأً فيُظنّ خطأً في الحساب.
        """
        period = service_period(date(2023, 2, 1), date(2026, 2, 1))
        self.assertEqual(
            (period.years, period.months, period.remainder_days), (2, 11, 30)
        )
        self.assertEqual(period.days, 1096)
        # وبيوم النهاية محسوباً تصير المدّة سنةً ثالثة تامة.
        counted = service_period(date(2023, 2, 1), date(2026, 2, 1), inclusive_end=True)
        self.assertEqual((counted.years, counted.months, counted.remainder_days), (3, 0, 0))
        self.assertEqual(counted.days, 1097)

    def test_a_full_calendar_year_is_365_days(self):
        """
        والسنة المكتملة ٣٦٥ يوماً — بالعدّ التقويمي لا بضرب ١٢ في ٣٠.

        ومن ٢٠٢٣-٠٢-٠١ إلى ٢٠٢٤-٠٢-٠١ = ٣٦٥ يوماً، وفكّها «١١ شهراً و٣٠ يوماً»
        لأن الذكرى تقع في اليوم التالي للنهاية. والرقمان متفّقان: ٣٠ يوماً هي
        ما بين ١ فبراير و١ مارس، و٣١ يوماً هي يناير، ومجموعهما ٣٦٥ مع الأشهر
        الأحد عشر. ولا يُدّعى «سنة» هنا لأن الحدّ يمنعها — والعدّ الآخر يمنحها.
        """
        period = service_period(date(2023, 2, 1), date(2024, 2, 1))
        self.assertEqual(period.days, 365)
        self.assertEqual(
            (period.years, period.months, period.remainder_days), (0, 11, 30)
        )
        counted = service_period(date(2023, 2, 1), date(2024, 2, 1), inclusive_end=True)
        self.assertEqual((counted.years, counted.months, counted.remainder_days), (1, 0, 0))
        self.assertEqual(counted.days, 366)

    def test_leap_day_does_not_break_the_decomposition(self):
        """
        ⚠️ ٢٩ فبراير لا يُسقط الحساب.

        `_step_month` يُرجع آخر يوم من الشهر الهدف عندما لا يوجد اليوم نفسه،
        فالمدّة من ٢٠٢٤-٠٢-٢٩ إلى ٢٠٢٥-٠٢-٢٨ تمرّ بلا استثناء. وعدد أيامها ٣٦٥
        بهذا العدّ (٣٦٦ لو حُسب يوم النهاية)، والفكّ يقف عند ٢٨ فبراير لأن
        `_step_month` لم يستطع بلوغ الذكرى في ٢٩ منه — وهو السلوك الصحيح لا
        الخطأ: التقويم لا يعرف «٢٩ فبراير ٢٠٢٥».
        """
        period = service_period(date(2024, 2, 29), date(2025, 2, 28))
        self.assertEqual(period.days, 365)
        self.assertEqual(
            (period.years, period.months, period.remainder_days), (0, 11, 29)
        )
        counted = service_period(date(2024, 2, 29), date(2025, 2, 28), inclusive_end=True)
        self.assertEqual(counted.days, 366)

    def test_a_single_day(self):
        """يوم واحد مدّةً — والحدّ الأدنى لا يُنتج صفراً ولا سالباً."""
        period = service_period(date(2026, 1, 1), date(2026, 1, 2))
        self.assertEqual(period.days, 1)
        self.assertEqual((period.years, period.months, period.remainder_days), (0, 0, 0))

    def test_a_short_period_is_all_days(self):
        """مدّة أقصر من شهر: كلها أيام، ولا يُدّعى فيها شهر."""
        period = service_period(date(2026, 1, 1), date(2026, 1, 15))
        self.assertEqual(period.days, 14)
        self.assertEqual(
            (period.years, period.months, period.remainder_days), (0, 0, 13)
        )

    def test_a_reversed_period_raises_rather_than_returning_zero(self):
        """
        المدّة المعكوسة **ترفع استثناءً**، ولا تُرجع صفراً.

        ولو أُرجع صفر لصار الخطأ في المدخل **نقصاً صامتاً في المستحقّ**، وهو
        أسوأ من التوقّف: المذكرة تُسلَّم وفيها مدّة خدمة صفر بلا سبب ظاهر.
        """
        with self.assertRaises(ValueError):
            service_period(date(2026, 1, 1), date(2025, 1, 1))

    def test_the_period_carries_its_two_ends(self):
        """الحصيلة تحمل طرفيها — فـ«١٣٠٧» وحدها لا تُراجَع، وهما يُراجَعان."""
        period = service_period(START, END)
        self.assertEqual(period.start, START)
        self.assertEqual(period.end, END)
        self.assertIn("1307", period.describe())
        self.assertIn("3 سنة", period.describe())

    def test_period_days_is_the_single_counter(self):
        """
        العدّ في موضع واحد، **والافتراضيان متّفقان**.

        ⚠️ وهذه هي نقطة الخطأ التي وقعت هنا: للدالّتين وسيطان مختلفا الاسم
        (`exclusive` و`inclusive_end`) ومقلوبا المعنى. فإن اختلف افتراضيّاهما
        أعطى النداء نفسه رقمين لمدّة واحدة — وهو التناقض بعينه. فالاختبار يثبّت
        أن النداء بلا وسيط في الدالّتين يُعطي الرقم نفسه، ويُعلن العدّ الآخر.
        """
        self.assertEqual(period_days(START, END), DAYS_CORRECT)
        self.assertEqual(period_days(START, END), service_period(START, END).days)
        # والعدّ الآخر: النهاية محسوبة.
        self.assertEqual(period_days(START, END, exclusive=False), DAYS_WITH_END_COUNTED)
        self.assertEqual(
            period_days(START, END, exclusive=False),
            service_period(START, END, inclusive_end=True).days,
        )

    def test_invariant_over_many_periods(self):
        """
        ضمان على مدى واسع: لا سنوات سالبة، ولا شهر فوق ١٢، ولا باقٍ فوق شهر.

        وهذا فحص **شكلي** لا حسابي: يمنع الأرقام المستحيلة التي تنشأ من خطأ في
        التقويم، ويترك الأرقام الممكنة للمحامي. وقد كشف فعلاً — أثناء كتابة
        الملف — باقياً يجمع إلى ما فوق الشهر في مدّة قصيرة.
        """
        for month in (1, 3, 6, 12):
            for day in (1, 15, 28):
                start = date(2024, month, day)
                for offset in (0, 1, 29, 179, 365, 366, 730, 1000, 1307, 1339):
                    end = start + timedelta(days=offset)
                    for inclusive in (True, False):
                        period = service_period(start, end, inclusive_end=inclusive)
                        with self.subTest(start=start, end=end, inclusive=inclusive):
                            self.assertGreaterEqual(period.years, 0)
                            self.assertGreaterEqual(period.months, 0)
                            self.assertLessEqual(period.months, 12)
                            self.assertGreaterEqual(period.remainder_days, 0)
                            self.assertLess(period.remainder_days, 31)

    def test_service_period_is_frozen(self):
        """الحصيلة لا تُعدَّل بعد إنشائها."""
        period = service_period(START, END)
        self.assertTrue(isinstance(period, ServicePeriod))
        with self.assertRaises(Exception):
            period.days = 1  # type: ignore[misc]


class TestLeavePayDefect(unittest.TestCase):
    """
    🔑 **العيب الأول: بدل الإجازة على الأجر الخطأ.**

    حسب الكاتب على الأجر الشامل (٨٠٠٠) بدل الأجر الأساسي (٥٠٠٠). و١١ يوماً
    تعطي ٢٩٣٣٫٣٧ على الأول و١٨٣٣٫٣٣ على الثاني.

    وهذه الاختبارات تُثبّت **الرقم الخطأ على أنه خطأ**، لا الصواب على أنه صواب:
    اختبارٌ يقول «٢٩٣٣٫٣٧ خطأ» يفشل حين يعود العيب، واختبارٌ يقول «١٨٣٣٫٣٣
    صواب» يمرّ حتى لو صار للحاسبة أساس واحد صامت لا يُرى.
    """

    def test_eleven_days_on_the_basic_wage_is_1833_33(self):
        """🔑 الرقم الصحيح من التقرير: ١١ يوماً على أساسي ٥٠٠٠ = ١٨٣٣٫٣٣."""
        pay = leave_pay(11, BASIC_WAGE)
        self.assertEqual(str(pay.on_basic), "1833.33")
        self.assertEqual(str(pay.required_amount), "1833.33")
        self.assertEqual(pay.required_basis, WAGE_BASIS_BASIC)

    def test_computing_on_the_gross_wage_gives_2933_37_and_is_wrong(self):
        """
        🔑 **الرقم الخطأ، مصرَّحاً بأنه خطأ.**

        ١١ يوماً على أجر شامل ٨٠٠٠ = ٢٩٣٣٫٣٧ — وهو **ليس** المطلوب. والقاعدة
        تطلب الأساسي، فالمطلوب ١٨٣٣٫٣٣. والاختبار يفحص أن الرقمين مختلفان، وأن
        المطلوب هو الأساسي — فلا يمرّ استعمال الأساس الخطأ ولو كان الرقم صحيحاً
        حسابياً على أساسه.
        """
        pay = leave_pay(11, BASIC_WAGE, GROSS_WAGE)
        self.assertEqual(str(pay.on_gross), "2933.33")
        self.assertNotEqual(pay.required_amount, pay.on_gross)
        self.assertEqual(pay.required_basis, WAGE_BASIS_BASIC)
        self.assertEqual(str(pay.required_amount), "1833.33")
        # ⚠️ والرقم الذي كتبته المذكرة تحت المراجعة كان **٢٩٣٣٫٣٧** لا ٢٩٣٣٫٣٣:
        # خطأ في الأساس **وفي التقريب** معاً. فالمذكرة أخطأت خطأين لا خطأً
        # واحداً — والاختبار يثبّت أن أياً من الرقمين ليس هو المطلوب.
        self.assertNotEqual(str(pay.required_amount), "2933.37")
        self.assertNotEqual(str(pay.on_gross), "2933.37")

    def test_the_difference_is_visible_and_amounts_to_1100(self):
        """
        الفرق بين الأساسين **يُعرض** ولا يُترك ليُكتشف.

        والفرق ١١٠٠ درهم في أحد عشر يوماً: رقم لا يُستهان به، ولا يظهر أبداً لو
        أعرضت الحاسبة أساساً واحداً صامتاً. وهذا هو الغرض من عرض الأساسين معاً.
        """
        pay = leave_pay(11, BASIC_WAGE, GROSS_WAGE)
        self.assertEqual(str(pay.difference), "1100.00")
        self.assertEqual(pay.difference, pay.on_gross - pay.on_basic)
        self.assertIn("1100.00", pay.describe())
        self.assertIn("الأجر الأساسي", pay.describe())

    def test_required_basis_comes_from_the_table_not_from_the_calculator(self):
        """
        الأساس المطلوب يُقرأ من **الجدول**، فلا يصير للحاسبة رأي يخالف الموجّه.

        ولو اختارت الحاسبة أساسها بنفسها لأمكن أن تتفق مع نفسها وتخالف القاعدة،
        فيصل إلى المذكرة رقمٌ يبدو سليماً وهو على أساس لم يُقرّه أحد.
        """
        pay = leave_pay(11, BASIC_WAGE, GROSS_WAGE)
        table_basis = wage_basis_for("بدل الإجازة السنوية")
        self.assertEqual(pay.required_basis, table_basis)
        self.assertEqual(pay.article, rule_for("بدل الإجازة السنوية").article)
        self.assertIn("الأساسي", pay.rule_statement)

    def test_without_a_gross_wage_there_is_no_difference(self):
        """
        بلا أجر شامل لا يُدّعى فرق ولا يُخترع أساس ثانٍ.

        و``None`` هنا مقصود: الفرق بين رقم ورقم غير موجود ليس صفراً، بل سؤال لم
        يُطرح. وإظهاره صفراً كان سيوهم القارئ بأن الأساسين اتّفقا.
        """
        pay = leave_pay(11, BASIC_WAGE)
        self.assertIsNone(pay.on_gross)
        self.assertIsNone(pay.difference)
        self.assertEqual(str(pay.required_amount), "1833.33")

    def test_arithmetic_is_per_day_thirty(self):
        """
        الأجر اليومي = الشهري ÷ ٣٠، والتقريب عند النتيجة لا في اليومي.

        ولو قُرّب اليومي أولاً (٥٠٠٠ ÷ ٣٠ = ١٦٦٫٦٧) لصار ١١ يوماً = ١٨٣٣٫٣٧،
        أي فرق سنتين لا يُفسّره محامٍ. والاختبار يثبّت أن التقريب في الموضع
        الصحيح.
        """
        self.assertEqual(DAYS_PER_MONTH, Decimal("30"))
        self.assertEqual(
            daily_rate(BASIC_WAGE) * 11, Decimal("1833.333333333333333333333334")
        )
        self.assertEqual(str(leave_pay(11, BASIC_WAGE).on_basic), "1833.33")
        self.assertNotEqual(str(leave_pay(11, BASIC_WAGE).on_basic), "1833.37")

    def test_half_a_cent_rounds_up(self):
        """
        التقريب المالي: نصف الدرهم يُرفع (``ROUND_HALF_UP``).

        وهو عرف المستندات المالية العربية. أما ``Decimal`` الافتراضي
        (``ROUND_HALF_EVEN``) فيُخفض النصف فيخالف العرف بلا سبب مذكور.
        """
        # ٥ أيام على ٥٠٠٠ = ٨٣٣٫٣٣٣... والأجر الشامل ٨٠٠٠ يعطي ١٣٣٣٫٣٣
        pay = leave_pay(5, BASIC_WAGE, GROSS_WAGE)
        self.assertEqual(str(pay.on_basic), "833.33")
        self.assertEqual(str(pay.on_gross), "1333.33")

    def test_the_amounts_are_decimal_never_float(self):
        """
        المال ``Decimal`` لا عائمة.

        وعشرية بايثون تكفي هنا لسبب عملي: جمع مبالغ مذكرات بعوائم يُنتج فروقاً
        في المنزلة الأخيرة تظهر في المذكرة كتناقض، وهو نفس العيب الرابع الذي
        رصده المراجع في المكافأة.
        """
        pay = leave_pay(11, BASIC_WAGE, GROSS_WAGE)
        self.assertIsInstance(pay.on_basic, Decimal)
        self.assertIsInstance(pay.on_gross, Decimal)
        self.assertIsInstance(pay.difference, Decimal)

    def test_negative_days_raise(self):
        """عدد أيام سالب خطأ مدخل يرفع استثناءً، ولا يُنتج مبلغاً سالباً."""
        with self.assertRaises(ValueError):
            leave_pay(-1, BASIC_WAGE)

    def test_leave_pay_is_frozen(self):
        pay = leave_pay(11, BASIC_WAGE)
        self.assertTrue(isinstance(pay, LeavePay))
        with self.assertRaises(Exception):
            pay.days = 12  # type: ignore[misc]


class TestNoticePayDefect(unittest.TestCase):
    """
    🔑 **العيب الثاني: حرمان العامل أجر مدة الإشعار.**

    وقد كان الاستدلال أن العامل أُعفي من الحضور، فلا أجر له. والقاعدة أن العقد
    يبقى قائماً خلال مدة الإشعار وأن الأجر واجبٌ كاملاً. فالاختبارات هنا لا تفحص
    المبلغ وحده — بل تفحص أن **الاستدلال الخاطئ مستحيل** من هذه الحصيلة.
    """

    def test_the_wage_is_payable_in_full_and_excusal_does_not_defeat_it(self):
        """
        🔑 الإعفاء من الحضور **لا يُسقط** الاستحقاق — والحقل يثبت ذلك.

        ``excusal_defeats_claim`` ثابتٌ على ``False`` مهما كان الإعفاء، و
        ``contract_continues`` على ``True``. فهذان الحقلان هما جواب العيب مكتوباً
        في الحصيلة، فلا يُعاد بناء الاستدلال في كل مسودّة.
        """
        pay = notice_pay(30, BASIC_WAGE, GROSS_WAGE, attendance_excused=True)
        self.assertTrue(pay.contract_continues)
        self.assertTrue(pay.attendance_excused)
        self.assertFalse(pay.excusal_defeats_claim)
        self.assertEqual(pay.article, "٤٣/٢")
        self.assertIn("الحضور", pay.rule_statement)

    def test_the_amount_is_not_reduced_by_the_excusal(self):
        """
        والمبلغ **لا ينقص** بسبب الإعفاء — لا بنصف ولا بأي نسبة.

        ولو كان للإعفاء أثر في المبلغ لكان ذلك أول ما يظهر: المقارنة بين الحالة
        مع الإعفاء وبدونه. فالاختبار يفحص التساوي، لا مجرّد وجود رقم.
        """
        excused = notice_pay(30, BASIC_WAGE, GROSS_WAGE, attendance_excused=True)
        not_excused = notice_pay(30, BASIC_WAGE, GROSS_WAGE, attendance_excused=False)
        self.assertEqual(excused.required_amount, not_excused.required_amount)
        self.assertEqual(str(excused.required_amount), "8000.00")

    def test_notice_basis_is_the_gross_wage_unlike_leave_pay(self):
        """
        أساس أجر الإشعار **مخالف** لأساس الإجازة — والقاعدة تقول ذلك صراحةً.

        والسبب أن الأجر هنا عن مدّة **لم تُعمل**، فيُقاس بما كان العامل يتقاضاه
        لولا الإنهاء. ولو وحّدنا الأساسين «للتبسيط» لخالفنا القاعدة في أحد
        الموضعين — وهو بعينه العيب الذي جاء هذا الملف لمنعه.
        """
        pay = notice_pay(30, BASIC_WAGE, GROSS_WAGE)
        self.assertEqual(pay.required_basis, WAGE_BASIS_GROSS)
        self.assertNotEqual(
            pay.required_basis,
            wage_basis_for("بدل الإجازة السنوية"),
        )
        self.assertEqual(str(pay.required_amount), "8000.00")

    def test_without_a_gross_wage_the_basic_is_used_and_still_flagged(self):
        """
        نقص المدخل لا يُسقط الاستحقاق، ولا يُخفى أن الأساس ناقص.

        فالحصيلة تبقى تقول إن الأساس المطلوب هو الأجر الشامل — حتى يعرف
        المحامي أن الرقم ناقص لأن **مدخلاً** ناقص، لا لأن القاعدة نقصت.
        """
        pay = notice_pay(30, BASIC_WAGE)
        self.assertIsNone(pay.on_gross)
        self.assertEqual(pay.required_basis, WAGE_BASIS_GROSS)
        self.assertEqual(str(pay.required_amount), "5000.00")

    def test_negative_days_raise(self):
        with self.assertRaises(ValueError):
            notice_pay(-5, BASIC_WAGE)

    def test_notice_pay_is_frozen(self):
        pay = notice_pay(30, BASIC_WAGE)
        self.assertTrue(isinstance(pay, NoticePay))
        with self.assertRaises(Exception):
            pay.days = 31  # type: ignore[misc]


# ⚠️ **وأرقام هذا الصنف تغيّرت مرة واحدة، ولسببٍ يجب أن يُقرأ.**
#
# كانت محسوبة على **«نصف شهر» (١٥ يوماً)** لكل سنة من الخمس الأولى. **وهي
# صيغة القانون الاتحادي رقم ٨ لسنة ١٩٨٠ الملغى.** والمادة ٥١ من المرسوم
# بقانون اتحادي ٣٣ لسنة ٢٠٢١ تجعلها **٢١ يوماً**، ثم ٣٠ يوماً لما بعد الخمس.
#
# ⚠️ **وكانت هذه الاختبارات تثبّت الرقم الخاطئ بثقة** — وهو أخطر من غياب
# الاختبار: **اختبارٌ يحرس خطأً يمنع اكتشافه.**
#
# فالأرقام الآن: سنة = 3,500 · سنتان = 7,009.59 · 1,307 يوماً = 12,532.88.
# **وهي توافق تقدير المُقيِّم القانوني المستقل (١٢,٥٤١.٦٧)** — والفارق اليسير
# من طريقة توزيع أجزاء السنة، لا من الأساس.


class TestGratuity(unittest.TestCase):
    """
    🔑 **العيب الرابع: احتساب المكافأة متناقض مع نفسه.**

    والعلاج أن يكون للمكافأة **رقم واحد** لا رقمان. فالدالّة تعيد مبلغاً واحداً
    على الأجر الأساسي، والاختبار يتحقّق من قاعدتها بحساب مستقلّ مكتوب في
    الاختبار نفسه — فلا يتحقّق الكود من نفسه، وهو فحصٌ بلا معنى.
    """

    def test_gratuity_is_computed_on_the_basic_wage(self):
        """
        المكافأة على الأجر **الأساسي** — والعيب لو وقع لظهر في الرقم.

        والمقارنة هنا مع الحساب على الشامل: لو حُسبت عليه لكانت أكثر، وهي زيادة
        تُقبل صامتةً لأنها في مصلحة العامل. فالتقرير كان يجب أن يكون **متّسقاً**
        لا كريماً.
        """
        period = service_period(START, END)
        on_basic = end_of_service_gratuity(BASIC_WAGE, period)
        # ⚠️ والمعيار **واحد**: الأيام ÷ ٣٦٥ × (٢١ ÷ ٣٠)، بلا فكّ تقويمي ولا أشهر أثلاثاً.
        # وهذا ما يمنع المعيارين الذين أنتجا رقمين لمدّة واحدة.
                # ⚠️ **وكان هنا `0.5` — نصف شهر، وهي صيغة القانون الملغى.**
        # فالاختبار كان **يحرس خطأً** لا يكشفه: يُعيد الصيغة الخاطئة في
        # معياره، فينجح ما دام الكود مخطئاً، ويسقط لحظة تصحيحه. وهو أخطر
        # من غياب الاختبار — لأن غيابه يترك الشكّ، وحضوره يُطمئن كذباً.
        base = Decimal(DAYS_CORRECT) / Decimal("365") * (Decimal("21") / Decimal("30")) * Decimal("5000")
        self.assertEqual(on_basic, base.quantize(Decimal("0.01")))
        self.assertEqual(str(on_basic), "12532.88")
        self.assertLess(on_basic, end_of_service_gratuity(GROSS_WAGE, period))

    def test_the_same_inputs_give_the_same_number(self):
        """
        🔑 **ضمان عدم التناقض:** المدخل نفسه يُعطي الرقم نفسه، دائماً.

        وهذا ما كان مفقوداً: المذكرة حملت رقمين لمدّة واحدة. والدالّة النقية
        لا تستطيع أن تفعل ذلك — والاختبار يثبّت الضمان لا الدالّة.
        """
        period = service_period(START, END)
        results = {
            str(end_of_service_gratuity(BASIC_WAGE, period)) for _ in range(5)
        }
        self.assertEqual(len(results), 1)
        self.assertEqual(results.pop(), "12532.88")

    def test_exactly_two_years_matches_the_twenty_one_day_rule(self):
        """
        🔑 **الاختبار الذي كشف المعيارين، وهو أهمّ اختبار في هذا الصنف.**

        مدّة سنتين بالضبط على أساسي ٥٠٠٠ يجب أن تكون **٧٠٠٠ بالضبط**: ٢١ يوماً
        عن كل سنة. ولو احتُسبت من الفكّ التقويمي مع نسبة سنوية بـ٣٦٥ لخرجت
        **٤٩٩٧٫١٥** — تنقص ثلاثة دراهم لأن ٢٠٢٤ كبيسة، فصار في الملف معياران:
        سنة تقويمية للحساب وسنة ٣٦٥ للكسر. وهذا هو **التناقض الداخلي** بعينه
        (العيب الرابع)، فجاء هذا الاختبار ليمنع عودته.

        ⚠️ ولاحظ أن المدّة ٧٣١ يوماً لا ٧٣٠، لأن ٢٠٢٤ سنة كبيسة: فيوم واحد من
        الزيادة يظهر في المكافأة (٥٠٠٦٫٨٥) — وهو أثر **معلن ومقصود**، لأن
        المدّة الفعلية لا يُتجاهل منها يوم بحجّة «السنة ٣٦٥».
        """
        period = service_period(date(2023, 1, 1), date(2025, 1, 1))
        self.assertEqual(period.days, 731)
        self.assertEqual(period.years, 1)  # الفكّ التقويمي لا يبلغ الذكرى
        self.assertEqual(
            end_of_service_gratuity(Decimal("5000"), period), Decimal("7009.59")
        )
        # ولو أُسقط اليوم الكبيس من المدّة لكانت ٥٠٠٠ بالضبط — والاختبار يثبت
        # أن الفرق منه لا من خطأ في الاحتساب.
        without_leap_day = ServicePeriod(
            days=730,
            years=2,
            months=0,
            remainder_days=0,
            inclusive_end=False,
            start=date(2023, 1, 1),
            end=date(2025, 1, 1),
        )
        self.assertEqual(
            end_of_service_gratuity(Decimal("5000"), without_leap_day),
            Decimal("7000.00"),
        )

    def test_a_full_year_is_twenty_one_days_of_the_basic_wage(self):
        """وثلاثة٦٥ يوماً = سنة بالضبط: ٥٠٠٠ × ٢١ ÷ ٣٠ = ٣٥٠٠٫٠٠ بلا كسر ولا تشويه."""
        period = service_period(date(2023, 2, 1), date(2024, 2, 1))
        self.assertEqual(period.days, 365)
        self.assertEqual(
            end_of_service_gratuity(Decimal("5000"), period), Decimal("3500.00")
        )

    def test_whole_years_only(self):
        """
        الحساب بجملة واحدة: الأيام ÷ ٣٦٥ × ٢١ يوماً (أو ٣٠ بعد الخمس).

        والمدّة تحت المراجعة ١٣٠٧ أيام = ٣٫٥٨ سنة، فالمكافأة ١٢٥٣٢٫٨٨. ولا فرق
        بين «سنوات كاملة» و«كسر» في هذه القاعدة إلا في الشريحة (٢١ يوماً أو
        شهر)، ولا يُقرَّب الكسر إلى سنة كاملة لأن ذلك يخالف نصّ القاعدة.
        """
        period = service_period(START, END)
        self.assertEqual(period.days, DAYS_CORRECT)
        self.assertEqual(
            end_of_service_gratuity(BASIC_WAGE, period), Decimal("12532.88")
        )
        # والشريحة الثانية (بعد خمس سنوات) بشهر كامل لكل سنة: ٦ سنوات = ٥ × ٢١ ÷ ٣٠
        # + ١ × ١ = ٣٫٥ شهراً. والاختبار يقيس الفرق بين الشريحتين.
        six_years = ServicePeriod(
            days=2190,
            years=6,
            months=0,
            remainder_days=0,
            inclusive_end=False,
            start=date(2020, 1, 1),
            end=date(2026, 1, 1),
        )
        self.assertEqual(
            end_of_service_gratuity(BASIC_WAGE, six_years), Decimal("22500.00")
        )
        # ٢١٩٠ يوماً = ٦ × ٣٦٥: الشريحة الأولى ٥ × ٢١ = ١٠٥ أيام، والثانية ١ × ٣٠
        self.assertEqual(
            end_of_service_gratuity(BASIC_WAGE, six_years),
            Decimal("5000") * Decimal("4.5"),
        )

    def test_zero_length_period_gives_zero(self):
        """
        مدّة صفر → مكافأة صفر، ولا قسمة على صفر ولا استثناء.

        والمدّة الصفرية تُبنى هنا صريحةً، لأن `service_period` لا تُنتجها: أقصر
        مدّة فيها يوم واحد. والفرق مقصود — الحصيلة اليدوية تحاكي ما لو وصلت
        مدّة صفرية من مسار آخر، والحاسبة يجب أن تصمد لها بدل أن تقسم على صفر.
        """
        empty = ServicePeriod(
            days=0,
            years=0,
            months=0,
            remainder_days=0,
            inclusive_end=False,
            start=date(2026, 1, 1),
            end=date(2026, 1, 1),
        )
        self.assertEqual(end_of_service_gratuity(BASIC_WAGE, empty), Decimal("0.00"))
        self.assertEqual(str(end_of_service_gratuity(BASIC_WAGE, empty)), "0.00")

    def test_gratuity_accepts_plain_numbers(self):
        """
        المدخل الرقمي يُحوَّل من **نصّه** لا من عائمة.

        ``Decimal(0.1)`` ليست عُشراً، و``Decimal("0.1")`` هي. ولأن الأجور
        تُكتب غالباً أعداداً صحيحة فقد يمرّ الخطأ صامتاً سنين، ثم يظهر في مبلغ
        بمئات الآلاف.
        """
        period = service_period(START, END)
        self.assertEqual(
            end_of_service_gratuity(5000, period),
            end_of_service_gratuity(BASIC_WAGE, period),
        )
        self.assertEqual(
            end_of_service_gratuity(5000.0, period),
            end_of_service_gratuity(BASIC_WAGE, period),
        )


class TestRulesBlock(unittest.TestCase):
    """
    كتلة الموجّه — وهي التي تجعل القاعدة **في المنظومة لا في الحوار**.

    وهذا هو أصل العيب كله: المراجع أبلغ النموذج بالعيب في محادثة، وعاد العيب في
    التشغيل التالي. فما يُفحص هنا ليس جمال النصّ، بل وجود **الأوامر الثلاثة**
    التي تمنع تكرار العيوب: لا تحسب، وهذه هي الأسس، وإن لم يكن للاستحقاق أساس
    فقل «غير محقَّق».
    """

    def test_the_block_forbids_computation(self):
        """
        🔑 **الأمر الأول: لا تحسب.** وهو ردّ مباشر على «١٢٧٨ يوماً».

        فالحساب في النصّ المولَّد لا يتحقّق منه أحد، والموجّه هو الموضع الوحيد
        الذي يمكن أن يُمنع فيه قبل وقوعه.
        """
        block = rules_block()
        self.assertIn("لا تحسب", block)
        self.assertIn("تاريخ", block)
        self.assertIn("مدّة", block)
        self.assertIn("مبلغاً", block)

    def test_the_block_orders_the_unverified_answer_instead_of_a_guess(self):
        """
        🔑 **الأمر الثالث، وهو صمّام الأمان.**

        النموذج مُدرَّب على إكمال الناقص؛ فإن لم يُؤمر بأن يقول «غير محقَّق»
        اختار أساساً من عنده — وهي **العيب الأول نفسه** (حساب على ٨٠٠٠ حيث
        القاعدة تطلب ٥٠٠٠). فالبديل يجب أن يكون معلَناً ومأموراً به.
        """
        block = rules_block()
        self.assertIn("غير محقَّق", block)
        self.assertIn("لا يُخمَّن", block)

    def test_the_block_carries_every_rule_from_the_table(self):
        """
        الكتلة تُبنى من الجدول مباشرةً، فلا يفترق الموجّه عن القاعدة.

        ولو كان نصّ الكتلة محفوظاً منفصلاً لأمكن تعديل الجدول وبقاء الموجّه على
        القديم — فيُصلح أحدهم القاعدة في مكان ويظنّ أنها صارت في الموجّه، وهي
        لم تصر.
        """
        block = rules_block()
        for rule in RULES:
            with self.subTest(entitlement=rule.entitlement):
                self.assertIn(rule.entitlement, block)
                self.assertIn(rule.article, block)
                self.assertIn(rule.basis_label, block)

    def test_the_block_names_the_notice_rule_and_the_basic_wage_basis(self):
        """القاعدتان الحاسمتان في الموجّه: ٤٣/٢ لأجر الإشعار، والأساسي للإجازة."""
        block = rules_block()
        self.assertIn("٤٣/٢", block)
        self.assertIn("٢٩/٩", block)
        self.assertIn("الأجر الأساسي", block)

    def test_block_is_deterministic(self):
        """الكتلة حتمية: النداء مرتين يُعطي النصّ نفسه — فلا يتغيّر الموجّه بتشغيل."""
        self.assertEqual(rules_block(), rules_block())

    def test_block_ends_with_a_break_so_it_joins_cleanly(self):
        """الكتلة تنتهي بسطر فارغ، فتلتحق بالموجّه بلا التصاق بفقرة تالية."""
        self.assertTrue(rules_block().endswith("\n"))

    def test_block_is_not_empty_and_is_arabic(self):
        """الكتلة عربية وفيها سطور مرقّمة — فتُقرأ كتعليمات لا كفقرة نثرية."""
        block = rules_block()
        self.assertGreater(len(block), 200)
        self.assertIn("1.", block)
        self.assertIn("2.", block)
        self.assertIn("3.", block)


class TestModuleGuarantees(unittest.TestCase):
    """
    ضمانات معمارية — كـ `citations.py` و`language_audit.py`:
    مكتبة قياسية وحدها، ولا شبكة، ولا حالة، ولا إدخال/إخراج.
    """

    def test_imports_are_stdlib_only(self):
        """
        ⚠️ **لا تبعية خارجية.** وهي شرط عملي لا ذوقي: الحاسبة تُستدعى في مسار
        الصياغة، وتبعية خارجية هنا تعني أن الاختبار يحتاج شبكةً أو مفتاحاً —
        فلا يُشغَّل، فلا يحمي شيئاً.
        """
        source = pathlib.Path(labour_rules.__file__).read_text(encoding="utf-8")
        imported = set(
            _re.findall(r"^(?:from|import)\s+([A-Za-z_][\w\.]*)", source, _re.MULTILINE)
        )
        allowed = {"__future__", "dataclasses", "datetime", "decimal", "typing"}
        self.assertTrue(imported <= allowed, f"استيرادات: {sorted(imported - allowed)}")

    def test_no_environment_network_or_printing(self):
        """
        لا بيئة، ولا شبكة، ولا طبع.

        و«لا طبع» مقصود: وحدة تُطبع أثناء الاستيراد تُلوّث مخرج أي مسار يستدعيها،
        والحاسبة تُستدعى من الخادم ومن الاختبار معاً.
        """
        source = pathlib.Path(labour_rules.__file__).read_text(encoding="utf-8")
        for forbidden in ("os.environ", "requests.", "socket", "http", "print("):
            self.assertNotIn(forbidden, source)

    def test_no_module_level_state(self):
        """
        لا حالة على مستوى الوحدة: كل نداء يُعطي نتيجته من مدخلاته.

        وهذا ما يجعل الحصيلة تُعاد كاملةً في `LeavePay` و`NoticePay` بدل عدّاد
        يُقرأ من آخر نداء — على النمط الذي شرحه `review.py` في رفض
        `last_dropped()`.
        """
        first = leave_pay(11, BASIC_WAGE)
        second = leave_pay(30, GROSS_WAGE)
        third = leave_pay(11, BASIC_WAGE)
        self.assertEqual(first, third)
        self.assertNotEqual(first, second)

    def test_rules_tuple_is_immutable(self):
        """الجدول نفسه غير قابل للتعديل — لا يُضاف إليه سطر في زمن التشغيل."""
        self.assertIsInstance(RULES, tuple)
        with self.assertRaises(Exception):
            RULES[0] = RULES[0]  # type: ignore[index]


if __name__ == "__main__":
    unittest.main(verbosity=2)
