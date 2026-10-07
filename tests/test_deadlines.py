"""
اختبارات مواعيد الإجراءات — العدّ الذي لا يُخترع، والحدّ الذي لا يتجاوزه الكود.
================================================================================

تشغيل:
    python -m unittest discover -s tests -t .

حتمية بالكامل: بلا شبكة، وبلا نموذج، وبلا قاعدة بيانات. والقرص الوحيد الذي
يُلمس هو **نصّ هذه الوحدة نفسها** (`deadlines.py`) في اختبارين بنيويين — على
نمط `test_labour_rules.py` — لأن بعض الحدود لا تُفحص بالنداء بل بالنصّ: أن لا
يُدرَج تاريخ عطلة، ولا تُحفظ مدّة قانونية.

وأهمّ اختبار في الملف `test_the_service_period_is_1307_days_not_1278` — وهو
ليس اختباراً على دالّة، بل **تثبيت لعيب وقع فعلاً**: مدّة خدمة من
٢٠٢٣-٠٢-٠١ إلى ٢٠٢٦-٠٨-٣١ كُتبت في مذكرة «١٢٧٨ يوماً»، والصحيح ١٣٠٧ — أو
١٣٠٨ لو حُسب يوم النهاية. والأخيران **ليسا خلافاً**: هما اتفاقيتان تفترقان
بيوم واحد، والقاعدة هي التي تختار.

والاختبار الثاني في الأهمّية `TestNoHolidayCalendarIsEmbedded`: العطلات
الرسمية تُعلَن كلّ سنة وتُعدَّل، فالتقويم المحفوظ في الكود يصير خطأً في السنة
التالية بلا أن يُبلّغ أحد — والموعد المتأخّر يُسقط استحقاقاً. فالاختبار يفحص
نصّ الوحدة بالتحليل النحوي (``ast``) فلا يمرّ فيه تاريخ حرفيّ واحد.
"""

import ast
import pathlib
import re
import unittest
from datetime import date, timedelta

import deadlines
import labour_rules
from deadlines import (
    CALENDAR_EXCLUSIVE,
    CALENDAR_INCLUSIVE_END,
    CONVENTIONS,
    DEFAULT_WEEKEND,
    MONTHS_WHOLE,
    UNIT_LABELS,
    WORKING_DAYS,
    Convention,
    DayCount,
    DeadlineRule,
    HolidaySet,
    Period,
    Unit,
    add_period,
    convention_for,
    counted_days,
    describe_rule,
    is_expired,
    period_between,
    rule_for,
    service_period,
)

# ==============================================================================
# بيانات الاختبار — الوقائع الحقيقية من التقرير، لا أرقام متخيَّلة
# ==============================================================================

#: الواقعة تحت المراجعة: مباشرة العمل وانتهاء العلاقة.
START = date(2023, 2, 1)
END = date(2026, 8, 31)

#: الرقم الذي ورد في المذكرة تحت المراجعة — خطأ في العدّ لا في المعرفة.
DAYS_IN_THE_FLAWED_MEMORANDUM = 1278
#: الرقم الصحيح بالعدّ المعتمد (يوم النهاية حدٌّ لا يُحسب).
DAYS_CORRECT = 1307
#: الرقم نفسه إذا حُسب يوم النهاية — العدّ الآخر المعلن.
DAYS_WITH_END_COUNTED = 1308

#: ⚠️ **تقويم اختبار — تواريخ مُختلَقة للاختبار، وليست عطلات الإمارات.**
#:
#: ولا تُنقل هذه التواريخ إلى شيء: العطلات الرسمية تُعلَن كلّ سنة وتُعدَّل،
#: ولذلك **لا تُدرج في الوحدة** بل تُمرَّر إليها. وهذه هنا تواريخ اختبار
#: اصطناعية، وضعت لأن التقويم مُدخل لا بدّ منه لفحص العدّ بأيام العمل.
TEST_WEEKEND_ONLY = HolidaySet(frozenset(), label="بلا عطلات مورَّدة")
TEST_FRIDAY_ONLY = HolidaySet(
    frozenset(), weekend=frozenset({4}), label="الجمعة وحدها عطلة"
)
TEST_ONE_HOLIDAY = HolidaySet(
    frozenset({date(2026, 6, 3)}), label="عطلة اختبار واحدة"
)
#: عطلة تقع على يوم هو عطلة نهاية أسبوع أصلاً — تُستعمل لفحص عدم العدّ مرتين.
TEST_HOLIDAY_ON_A_SATURDAY = HolidaySet(
    frozenset({date(2026, 6, 6)}), label="عطلة اختبار تقع على سبت"
)

#: أسبوع كامل للفحص: الاثنين ٢٠٢٦-٠٦-٠١ إلى الأحد ٢٠٢٦-٠٦-٠٧.
#: (الجمعة ٥ والسبت ٦ فيه عطلة نهاية الأسبوع الافتراضية.)
WEEK_START = date(2026, 6, 1)
WEEK_END = date(2026, 6, 7)


def _module_source() -> str:
    """نصّ الوحدة — يُقرأ للفحص البنيوي وحده، ولا يُقرأ منه رقم."""
    return pathlib.Path(deadlines.__file__).read_text(encoding="utf-8")


def _module_tree() -> ast.Module:
    """شجرة الوحدة النحوية — تُفحص بها الحدود التي لا يراها النداء."""
    return ast.parse(_module_source())


def _calls_named(tree: ast.AST, name: str) -> list[ast.Call]:
    """
    كلّ نداء لدالّة أو صنف باسم ``name`` **في الكود** (لا في النصوص).

    و``ast`` مقصود بدل البحث النصّي: أمثلة التوثيق (``>>>``) نصوصٌ في شجرة
    النحو لا تُنفَّذ، فلو بحثنا نصّاً لظهرت أمثلةُ التوثيق تواريخَ مُدرَجة —
    وهي شرحٌ لا تقويم. والفحص هنا يقع على **ما يُنفَّذ**.
    """
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == name
    ]


class TestTheHistoricalDefect(unittest.TestCase):
    """
    🔑 **العيب الحقيقي: ١٢٧٨ في المذكرة، والصحيح ١٣٠٧.**

    مدّة الخدمة من ٢٠٢٣-٠٢-٠١ إلى ٢٠٢٦-٠٨-٣١ تحتوي ٢٩ فبراير ٢٠٢٤ (٢٠٢٤
    كبيسة)، والعدّ اليدوي أنتج ١٢٧٨ — ينقص ٢٩ يوماً من مدّة عامل، وهو نقص لا
    يُلاحَظ لأنه لا يبدو خطأً. والاختبار يثبّت الصواب **والخطأ معاً**: اختبارٌ
    يقول «١٣٠٧ صواب» يمرّ ولو عاد الرقم القديم إلى الرقم نفسه بطريق آخر، أما
    اختبارٌ يقول «١٢٧٨ ليست الصواب» فيفشل حين يعود العيب.
    """

    def test_the_service_period_is_1307_days_not_1278(self):
        """
        🔑 من ٢٠٢٣-٠٢-٠١ إلى ٢٠٢٦-٠٨-٣١ = **١٣٠٧ أيام**، وليست ١٢٧٨.

        والرقمان مقصودان معاً: الأول هو الصحيح، والثاني هو ما كتبته المذكرة —
        فيُثبَّت أنه **ليس** الصحيح، فلا يمرّ لو عاد.
        """
        period = service_period(START, END)
        self.assertEqual(period.days, DAYS_CORRECT)
        self.assertNotEqual(period.days, DAYS_IN_THE_FLAWED_MEMORANDUM)
        self.assertGreater(period.days, DAYS_IN_THE_FLAWED_MEMORANDUM)
        # والفرق ينقص من المدّة لا يزيد — أي في مصلحة صاحب العمل، وهو ما يجعل
        # مروره صامتاً أخطر.
        self.assertEqual(
            period.days - DAYS_IN_THE_FLAWED_MEMORANDUM,
            DAYS_CORRECT - DAYS_IN_THE_FLAWED_MEMORANDUM,
        )

    def test_the_same_period_with_the_end_day_counted_is_1308(self):
        """
        🔑 **الرقم الآخر: ١٣٠٨ إذا كان يوم النهاية محسوباً.**

        وهو ليس خطأً ولا تصحيحاً لـ١٣٠٧، بل **اتفاقية أخرى**: العرف العمالي
        يعدّ آخر يوم عمل من المدّة، فالعامل الذي عمل يوم ٣١ أغسطس عمل يوماً
        يُحسب له. ومن أخذ أحد الرقمين بلا سؤال «أيّ حدٍّ عُدّ؟» أخذ حساباً بلا
        قاعدة.
        """
        period = period_between(START, END, CALENDAR_INCLUSIVE_END)
        self.assertEqual(period.days, DAYS_WITH_END_COUNTED)
        self.assertEqual(period.convention_key, "calendar_inclusive_end")
        self.assertNotEqual(period.days, DAYS_CORRECT)

    def test_the_two_numbers_are_one_choice_apart(self):
        """
        ⚠️ **الفرق بين ١٣٠٧ و١٣٠٨ يومٌ واحد — هو يوم النهاية بعينه.**

        وهذا هو أصل الدرس: اتفاقيتان، رقم واحد يفترقان فيه، والاختيار **خاصية
        في القاعدة** لا عرف عام. فلو كان الفرق أكبر لكان أحد الرقمين خطأً
        حسابياً؛ ولكونه يوماً واحداً فهو **قرار**.
        """
        exclusive = period_between(START, END, CALENDAR_EXCLUSIVE)
        inclusive = period_between(START, END, CALENDAR_INCLUSIVE_END)
        self.assertEqual(inclusive.days - exclusive.days, 1)
        self.assertFalse(exclusive.convention_key == inclusive.convention_key)

    def test_the_1307_contains_the_start_day_and_not_the_end_day(self):
        """
        ⚠️ **حدّ لا بدّ من فحصه: أين يوم البداية من الـ١٣٠٧؟**

        الأيام المحسوبة في ``calendar_exclusive`` هي من ``start`` إلى ما قبل
        ``end``: أوّلها ٢٠٢٣-٠٢-٠١ (يوم البداية **داخلها**)، وآخرها ٢٠٢٦-٠٨-٣٠
        (عشيّة يوم النهاية)، وعددها ١٣٠٧. ومن استبعد يوم البداية أيضاً أنتج
        ١٣٠٦ — وهو رقم لا يوافق العدّ المعتمد ولا طلب المحامي. فالاختبار يثبّت
        الحدّين ويثبّت أن ١٣٠٦ **لم** تُنتَج.
        """
        days = counted_days(START, END, CALENDAR_EXCLUSIVE)
        self.assertEqual(len(days), DAYS_CORRECT)
        self.assertEqual(days[0], START)
        self.assertEqual(days[-1], END - timedelta(days=1))
        self.assertNotIn(END, days)
        self.assertNotEqual(len(days), DAYS_CORRECT - 1)

    def test_the_period_carries_its_ends_and_its_convention(self):
        """
        الحصيلة تحمل طرفيها **والاتفاقية التي عُدّت بها**.

        فـ«١٣٠٧» وحدها لا تُراجَع، و«من ٢٠٢٣-٠٢-٠١ إلى ٢٠٢٦-٠٨-٣١ = ١٣٠٧
        باتفاقية كذا» تُراجَع. وإظهار الاتفاقية في الحصيلة هو ما يمنع أن يُنسب
        إلى القاعدة عدٌّ لم تقرّه.
        """
        period = service_period(START, END)
        self.assertEqual(period.start, START)
        self.assertEqual(period.end, END)
        self.assertEqual(period.convention_key, CALENDAR_EXCLUSIVE.key)
        self.assertEqual(period.describe(), "٣ سنة و٦ شهر و٢٩ يوماً (1307 يوماً)")
        self.assertEqual(str(period), period.describe())

    def test_the_flawed_number_would_have_been_caught_by_the_calendar(self):
        """
        ⚠️ **وموضع العيب: العدّ اليدوي لا العدّ التقويمي.**

        ``(end - start).days`` = ١٣٠٧ بالضبط، وهو عدّ واحد لا يُخطئ. فالاختبار
        يقابل رقم الوحدة برقم التقويم مباشرةً — فلا يكون الاتفاق مصادفةً في
        واقعة واحدة.
        """
        self.assertEqual((END - START).days, DAYS_CORRECT)
        self.assertEqual(period_between(START, END, CALENDAR_EXCLUSIVE).days, (END - START).days)


class TestTheLeapYear(unittest.TestCase):
    """
    ٢٠٢٤ كبيسة — واليوم الزائد يظهر في **ثلاثة اتجاهات**، وكلّها تُفحص:

    ١. **في العدّ عبره**: سنة ٢٠٢٤ = ٣٦٦ يوماً لا ٣٦٥.
    ٢. **في الإضافة فوقه**: ٢٨ فبراير ٢٠٢٤ + يوم = ٢٩ فبراير، + يومين =
       ١ مارس؛ ومن ٢٨ فبراير ٢٠٢٣ + ٣٦٥ يوماً = ٢٧ فبراير ٢٠٢٥ (لا ٢٨).
    ٣. **في طول السنة المستعمل للسنوات الكاملة**: والفكّ التقويمي **لا يفترض
       ٣٦٥ يوماً**، فلا يُقسم العدد على ٣٦٥ ولا تُضرب سنة في ٣٦٥ — لأن ذلك هو
       الذي أنتج «١٢٧٨».
    """

    def test_the_leap_day_is_counted_between_28_february_and_1_march(self):
        """
        🔑 **٢٨ فبراير ٢٠٢٤ إلى ١ مارس ٢٠٢٤ = يومان** (والثالث لو حُسبت النهاية).

        والمدّة **تحتوي** ٢٩ فبراير ٢٠٢٤ — والاختبار يفحص الأيام المحسوبة
        أنفسها لا العدد وحده: فمَن عدّ ١ لغير الكبيسة لم يظهر خطؤه في العدد بل
        في اليوم الغائب. والمقارنة بسنة غير كبيسة (٢٠٢٣) تُظهر الفرق يوماً.
        """
        leap = period_between(date(2024, 2, 28), date(2024, 3, 1), CALENDAR_EXCLUSIVE)
        self.assertEqual(leap.days, 2)
        self.assertIn(date(2024, 2, 29), counted_days(date(2024, 2, 28), date(2024, 3, 1), CALENDAR_EXCLUSIVE))
        # وبعدّ يوم النهاية: ثلاثة أيام.
        self.assertEqual(
            period_between(date(2024, 2, 28), date(2024, 3, 1), CALENDAR_INCLUSIVE_END).days,
            3,
        )
        # وفي سنة غير كبيسة: يوم واحد بعدّ الحدّ.
        self.assertEqual(
            period_between(date(2023, 2, 28), date(2023, 3, 1), CALENDAR_EXCLUSIVE).days,
            1,
        )

    def test_counting_across_the_leap_day_costs_exactly_one_more_day(self):
        """
        السنة التي تحتوي ٢٩ فبراير **٣٦٦ يوماً**، والتي لا تحتويه ٣٦٥.

        والاختبار يقابل السنتين بالفكّ نفسه: العدد يفترق بيوم، والفكّ التقويمي
        يقول «١١ شهراً و٣٠ يوماً» في الحالتين — لأن الذكرى تقع في اليوم التالي
        للنهاية. فالرقمان **لا يتناقضان**: الأول عدّ أيام، والثاني رحلة تقويمية.
        """
        days_2024 = period_between(date(2024, 1, 1), date(2025, 1, 1), CALENDAR_EXCLUSIVE)
        days_2023 = period_between(date(2023, 1, 1), date(2024, 1, 1), CALENDAR_EXCLUSIVE)
        self.assertEqual(days_2024.days, 366)
        self.assertEqual(days_2023.days, 365)
        self.assertEqual(days_2024.days - days_2023.days, 1)
        self.assertEqual(
            (days_2024.whole_years, days_2024.whole_months, days_2024.remainder_days),
            (0, 11, 30),
        )

    def test_adding_a_period_over_the_leap_day(self):
        """
        **الاتجاه الثاني: الإضافة فوق ٢٩ فبراير.**

        * ٢٨ فبراير ٢٠٢٤ + يوم = ٢٩ فبراير (اليوم الكبيس موجود).
        * ٢٩ فبراير ٢٠٢٤ + يوم = ١ مارس.
        * ٢٨ فبراير ٢٠٢٤ + ٣٦٥ يوماً = ٢٧ فبراير ٢٠٢٥، لأن اليوم الكبيس
          **استُهلك في الطريق**؛ ولو كان التقويم يظنّ كلّ سنة ٣٦٥ يوماً لأعطى
          ٢٨ فبراير — وهو اليوم الذي يخطئ به العدّ بضربٍ ثابت.
        """
        self.assertEqual(
            add_period(date(2024, 2, 28), 1, Unit.DAYS, CALENDAR_EXCLUSIVE),
            date(2024, 2, 29),
        )
        self.assertEqual(
            add_period(date(2024, 2, 29), 1, Unit.DAYS, CALENDAR_EXCLUSIVE),
            date(2024, 3, 1),
        )
        self.assertEqual(date(2024, 2, 29) + timedelta(days=1), date(2024, 3, 1))
        self.assertEqual(
            add_period(date(2024, 2, 28), 365, Unit.DAYS, CALENDAR_EXCLUSIVE),
            date(2025, 2, 27),
        )

    def test_the_year_length_for_whole_years_is_calendrical_not_365(self):
        """
        🔑 **الاتجاه الثالث: طول السنة المستعمل للسنوات الكاملة.**

        الفكّ **رحلة تقويمية** لا قسمة: من ٢٠٢٤-٠١-٠١ إلى ٢٠٢٥-٠١-٠١ (٣٦٦
        يوماً) يعطي **صفر سنوات تقويمية**، لأن الذكرى (٢٠٢٥-٠١-٠١) ليست داخل
        المدّة — ويوم النهاية وحده هو الذي يجعلها سنة كاملة. ولو قُسمت الأيام
        على ٣٦٥ لظهرت «سنة» كاملة، وهو خطأٌ من جنس «١٢٧٨»: المعيار المفترض.

        ⚠️ **ويُفحص معه أن الرقم ٣٦٥ لا يظهر في نصّ الوحدة أصلاً** — فالحساب
        لا يفترض طول سنة، والفحص البنيوي يمنع أن يُدخل أحدهم ``/ 365`` لاحقاً
        فيعود العيب من الباب نفسه.
        """
        period = period_between(date(2024, 1, 1), date(2025, 1, 1), CALENDAR_EXCLUSIVE)
        self.assertEqual(period.days, 366)
        self.assertEqual(period.whole_years, 0)
        # وإذا صار يوم النهاية محسوباً صارت سنةً تقويمية كاملة — نعم بالاتفاقية
        # لا بالحساب.
        counted = period_between(date(2024, 1, 1), date(2025, 1, 1), CALENDAR_INCLUSIVE_END)
        self.assertEqual((counted.whole_years, counted.whole_months, counted.remainder_days), (1, 0, 0))
        # ولا طول سنة مفترض في نصّ الوحدة.
        self.assertNotIn("365", _module_source())
        self.assertNotIn("366", _module_source())


class TestMonthClamping(unittest.TestCase):
    """
    🔑 **تقييد اليوم: ٣١ يناير + شهر = ٢٨ فبراير، لا ٣ مارس.**

    والشهر وحدة تقويمية لا ثلاثون يوماً، فمن فاض يومُه على الشهر الهدف **يقف
    عند آخر يوم منه**. ولو قفز إلى الشهر التالي لكان الموعد بعد الحدّ بيومين أو
    ثلاثة، ولا يظهر السبب في الورقة: يُقرأ «شهر» ويُظنّ أنه صحيح.
    """

    def test_31_january_plus_one_month_is_28_february(self):
        """٣١ يناير ٢٠٢٦ + شهر = ٢٨ فبراير ٢٠٢٦ — لا ٣ مارس."""
        result = add_period(date(2026, 1, 31), 1, Unit.MONTHS, MONTHS_WHOLE)
        self.assertEqual(result, date(2026, 2, 28))
        self.assertNotEqual(result, date(2026, 3, 3))
        self.assertNotEqual(result, date(2026, 3, 1))

    def test_31_january_in_a_leap_year_plus_one_month_is_29_february(self):
        """وفي سنة كبيسة: ٣١ يناير ٢٠٢٤ + شهر = ٢٩ فبراير ٢٠٢٤."""
        self.assertEqual(
            add_period(date(2024, 1, 31), 1, Unit.MONTHS, MONTHS_WHOLE),
            date(2024, 2, 29),
        )

    def test_31_january_plus_thirteen_months(self):
        """
        ٣١ يناير ٢٠٢٦ + ١٣ شهراً = ٢٨ فبراير ٢٠٢٧.

        ⚠️ والفحص مقصود على **أكثر من سنة**: فالتقييد يقع بعد السنة أيضاً، ولو
        كان الحساب يتقدّم سنةً ثم شهراً لظهر الفرق في السنة الثانية.
        """
        self.assertEqual(
            add_period(date(2026, 1, 31), 13, Unit.MONTHS, MONTHS_WHOLE),
            date(2027, 2, 28),
        )

    def test_29_february_plus_twelve_months_is_28_february(self):
        """
        🔑 ٢٩ فبراير ٢٠٢٤ + ١٢ شهراً = ٢٨ فبراير ٢٠٢٥.

        فالسنة التالية ليست كبيسة، و«٢٩ فبراير ٢٠٢٥» **غير موجود** في التقويم؛
        فالقاعدة أن نقف عند آخر يوم من الشهر لا أن نتجاوزه. ولو تُجوهل ذلك
        لسقط الحساب باستثناء — وهو أسوأ من التقييد لأنه يوقف المسار كله.
        """
        self.assertEqual(
            add_period(date(2024, 2, 29), 12, Unit.MONTHS, MONTHS_WHOLE),
            date(2025, 2, 28),
        )
        self.assertEqual(
            add_period(date(2024, 2, 29), 1, Unit.YEARS, MONTHS_WHOLE),
            date(2025, 2, 28),
        )

    def test_a_shorter_month_also_clamps(self):
        """والتقييد ليس للفبراير وحده: ٣١ مارس + شهر = ٣٠ أبريل."""
        self.assertEqual(
            add_period(date(2026, 3, 31), 1, Unit.MONTHS, MONTHS_WHOLE),
            date(2026, 4, 30),
        )

    def test_a_whole_month_is_its_calendar_length(self):
        """
        ⚠️ **والشهر ليس ثلاثين يوماً:** يناير كاملاً = **٣١ يوماً**، وفبراير
        ٢٠٢٦ = ٢٨ يوماً. فمن ضرب الأشهر في ثلاثين أنتج موعداً يخالف التقويم
        الذي كتبته القاعدة.
        """
        self.assertEqual(
            period_between(date(2026, 1, 1), date(2026, 1, 31), MONTHS_WHOLE).days,
            31,
        )
        self.assertEqual(
            period_between(date(2026, 2, 1), date(2026, 2, 28), MONTHS_WHOLE).days,
            28,
        )
        self.assertNotEqual(
            period_between(date(2026, 1, 1), date(2026, 1, 31), MONTHS_WHOLE).days,
            30,
        )

    def test_adding_months_does_not_depend_on_the_day_count_basis(self):
        """
        ⚠️ **تحويل الأشهر تقويميّ دائماً، لا يتغيّر بأساس العدّ.**

        والسبب أن الشهر تقويمي بحكم تعريفه؛ وأما «أين ينتهي الشهر» — في يومه
        الأخير أو في أوّل الشهر التالي — فمسألة القاعدة لا التقويم. وتركُ
        التحويل صريحاً يمنع أن يُنتج عدّان موعدين لتاريخ واحد.
        """
        cases = (1, 13, 25)
        for months in cases:
            with self.subTest(months=months):
                self.assertEqual(
                    add_period(date(2026, 1, 31), months, Unit.MONTHS, MONTHS_WHOLE),
                    add_period(date(2026, 1, 31), months, Unit.MONTHS, CALENDAR_EXCLUSIVE),
                )

    def test_a_week_is_seven_calendar_days_under_every_convention(self):
        """
        ⚠️ **والأسبوع سبعة أيام تقويمية دائماً — ولا يُحوّل إلى أيام عمل.**

        فـ«أسبوع عمل» ليس سبعة أيام عمل، ولا يجوز أن نفترض له عدداً لم تنصّ
        عليه القاعدة. ومن عنده أسبوع بأيام العمل فليحوّله إلى أيام عمل صريحة،
        أو فليكتب اتفاقيته هو. والاختبار يثبّت أن الاتفاقيتين تُعطيان التاريخ
        نفسه — فلا يُدخل الملف عرفاً من عنده.
        """
        self.assertEqual(
            add_period(date(2026, 1, 1), 2, Unit.WEEKS, CALENDAR_EXCLUSIVE),
            date(2026, 1, 15),
        )
        self.assertEqual(
            add_period(date(2026, 1, 1), 2, Unit.WEEKS, WORKING_DAYS, TEST_WEEKEND_ONLY),
            date(2026, 1, 15),
        )


class TestWorkingDays(unittest.TestCase):
    """
    🔑 **المدّة بأيام العمل ليست المدّة بالتقويم.**

    وهي العيب الثاني في أصل الملف: من طبّق عدّاً واحداً على كلّ مدّة أنتج
    موعداً صحيحاً في موضع وخاطئاً في آخر بلا أن يظهر له فرق. والفحص هنا على
    أسبوع كامل محدّد الوقائع: من الاثنين ٢٠٢٦-٠٦-٠١ إلى الأحد ٢٠٢٦-٠٦-٠٧،
    وفيه الجمعة ٥ والسبت ٦.
    """

    def test_a_week_of_working_days_with_the_default_weekend(self):
        """
        أسبوع واحد بتقويم بلا عطلات مورَّدة = **٥ أيام عمل** (والسبعة تقويمية).

        فالجمعة والسبت عطلة نهاية الأسبوع الافتراضية، والأيام الخمسة الباقية
        أيام عمل. والاختبار يفحص الرقمين معاً لأن الفرق بينهما هو الدرس.
        """
        period = period_between(WEEK_START, WEEK_END, WORKING_DAYS, TEST_WEEKEND_ONLY)
        self.assertEqual(period.days, 5)
        self.assertEqual(period.working_days, 5)
        self.assertEqual(
            period_between(WEEK_START, WEEK_END, CALENDAR_INCLUSIVE_END).days, 7
        )
        self.assertNotEqual(period.days, 7)

    def test_the_supplied_holiday_set_reduces_the_count(self):
        """
        عطلة مورَّدة واحدة (الأربعاء ٢٠٢٦-٠٦-٠٣) تُنقص يوماً: ٥ ← **٤**.

        ⚠️ وهذا موضع **التقويم المورَّد** بعينه: بلا التقويم تُعدّ العطلة يوم
        عمل فيطول الموعد بلا أن يظهر. فالاختبار يثبّت الأثر — لا وجود الحقل.
        """
        period = period_between(WEEK_START, WEEK_END, WORKING_DAYS, TEST_ONE_HOLIDAY)
        self.assertEqual(period.days, 4)
        self.assertEqual(
            period.days,
            period_between(WEEK_START, WEEK_END, WORKING_DAYS, TEST_WEEKEND_ONLY).days - 1,
        )

    def test_a_holiday_that_falls_on_the_weekend_is_not_counted_twice(self):
        """
        عطلة تقع على السبت لا تُنقص شيئاً — **ولا تُعدّ مرتين**.

        فمن طرح «أيام العطلات» من «أيام الأسبوع» بلا فحص التداخل أنقص يوماً
        زائداً في كل عطلة توافق عطلة نهاية الأسبوع — وهو نقص صامت في المدّة.
        """
        period = period_between(
            WEEK_START, WEEK_END, WORKING_DAYS, TEST_HOLIDAY_ON_A_SATURDAY
        )
        self.assertEqual(period.days, 5)
        self.assertEqual(period.days, period_between(WEEK_START, WEEK_END, WORKING_DAYS, TEST_WEEKEND_ONLY).days)

    def test_a_friday_only_weekend_differs_from_a_friday_and_saturday_one(self):
        """
        🔑 **ونهاية الأسبوع نفسها اتفاقية: الجمعة وحدها ≠ الجمعة والسبت.**

        فبتقويم الجمعة وحدها يصير السبت يوم عمل: ٥ ← **٦**. ولو كان الافتراض
        مطبوعاً في الحساب لما أمكن لأيّ قاعدة تخالفه — والقاعدة هي التي تقول
        أيّهما نهاية الأسبوع في الجهة المعنيّة.
        """
        friday_only = period_between(WEEK_START, WEEK_END, WORKING_DAYS, TEST_FRIDAY_ONLY)
        friday_and_saturday = period_between(WEEK_START, WEEK_END, WORKING_DAYS, TEST_WEEKEND_ONLY)
        self.assertEqual(friday_only.days, 6)
        self.assertEqual(friday_and_saturday.days, 5)
        self.assertNotEqual(friday_only.days, friday_and_saturday.days)
        self.assertEqual(DEFAULT_WEEKEND, frozenset({4, 5}))
        self.assertNotEqual(TEST_FRIDAY_ONLY.weekend, DEFAULT_WEEKEND)

    def test_a_working_day_count_without_a_calendar_is_refused(self):
        """
        ⚠️ **الامتناع موضع: لا عدّ بأيام العمل بلا تقويم مورَّد.**

        التقويم الفارغ يعدّ كلّ عطلة رسمية يوم عمل، فيُنتج موعداً متأخّراً —
        **والمدّ الزائد لا يظهر في الورقة**. فترفض الحاسبة ولا تخمّن، وكذلك
        تفعل `is_expired`: الامتناع يُرى، والموعد المُخترَع لا يُرى.
        """
        with self.assertRaises(ValueError):
            period_between(WEEK_START, WEEK_END, WORKING_DAYS)
        with self.assertRaises(ValueError):
            add_period(WEEK_START, 1, Unit.DAYS, WORKING_DAYS)
        with self.assertRaises(ValueError):
            is_expired(WEEK_END, WEEK_END, WORKING_DAYS)

    def test_working_days_are_filled_only_when_a_calendar_is_supplied(self):
        """
        وعدد أيام العمل ``None`` إذا لم يُورَّد تقويم — **و``None`` ليست صفراً**.

        الفرق بين «لا أعرف» و«لا يوجد» فرقٌ لا يُطوى: صفرٌ كان سيوهم بأن المدّة
        لا أيام عمل فيها، وهو نقيض الواقع في مدّة تقويمية.
        """
        with_calendar = period_between(WEEK_START, WEEK_END, CALENDAR_INCLUSIVE_END, TEST_WEEKEND_ONLY)
        without_calendar = period_between(WEEK_START, WEEK_END, CALENDAR_INCLUSIVE_END)
        self.assertEqual(with_calendar.working_days, 5)
        self.assertIsNone(without_calendar.working_days)
        self.assertIsNotNone(with_calendar.describe_working_days())
        self.assertIsNone(without_calendar.describe_working_days())
        self.assertNotEqual(without_calendar.working_days, 0)

    def test_adding_working_days_skips_the_weekend(self):
        """
        إضافة يوم عمل من الخميس ٢٠٢٦-٠٦-٠٤: يوم العمل الأول هو الخميس نفسه
        (لأن يوم النهاية محسوب في هذه الاتفاقية)، والثاني يقفز الجمعة والسبت
        إلى **الأحد ٢٠٢٦-٠٦-٠٧**.

        ولو كان العدّ تقويمياً لكان ٢٦-٠٦-٠٥ و٢٦-٠٦-٠٦ — وهما عطلة. فالاختبار
        يثبّت القفز لا العدد.
        """
        self.assertEqual(
            add_period(date(2026, 6, 4), 1, Unit.DAYS, WORKING_DAYS, TEST_WEEKEND_ONLY),
            date(2026, 6, 4),
        )
        self.assertEqual(
            add_period(date(2026, 6, 4), 2, Unit.DAYS, WORKING_DAYS, TEST_WEEKEND_ONLY),
            date(2026, 6, 7),
        )
        self.assertNotEqual(
            add_period(date(2026, 6, 4), 2, Unit.DAYS, CALENDAR_EXCLUSIVE),
            date(2026, 6, 7),
        )


class TestIsExpiredAtTheBoundary(unittest.TestCase):
    """
    ⚠️ **الموعد في يومه: فائت أم لا؟ — الجواب من الاتفاقية لا من عرف.**

    وليس هذا تفصيلاً: هو الفرق بين موعد يُرفع في يومه وموعد يُرفع في الغد،
    وهو نفسه الفرق بين ١٣٠٧ و١٣٠٨.
    """

    def test_on_the_deadline_under_the_boundary_convention(self):
        """
        في اتفاقية «النهاية حدٌّ»: المدّة انتهت **قبل** يوم الموعد، فالموعد
        **فائت في يومه**.
        """
        deadline = date(2026, 6, 10)
        self.assertTrue(is_expired(deadline, deadline, CALENDAR_EXCLUSIVE))
        self.assertFalse(is_expired(deadline, deadline - timedelta(days=1), CALENDAR_EXCLUSIVE))
        self.assertTrue(is_expired(deadline, deadline + timedelta(days=1), CALENDAR_EXCLUSIVE))

    def test_on_the_deadline_under_the_inclusive_end_convention(self):
        """
        وفي اتفاقية «يوم النهاية محسوب»: يوم الموعد **آخر أيام المدّة**، فلا
        يكون فائتاً فيه — ويفوت في اليوم التالي.
        """
        deadline = date(2026, 6, 10)
        self.assertFalse(is_expired(deadline, deadline, CALENDAR_INCLUSIVE_END))
        self.assertFalse(is_expired(deadline, deadline - timedelta(days=1), CALENDAR_INCLUSIVE_END))
        self.assertTrue(is_expired(deadline, deadline + timedelta(days=1), CALENDAR_INCLUSIVE_END))

    def test_the_one_day_difference_is_the_whole_answer(self):
        """⚠️ والاتفاقيتان تفترقان في **يوم واحد** — يوم الموعد نفسه."""
        deadline = date(2026, 6, 10)
        self.assertNotEqual(
            is_expired(deadline, deadline, CALENDAR_EXCLUSIVE),
            is_expired(deadline, deadline, CALENDAR_INCLUSIVE_END),
        )

    def test_a_working_day_deadline_on_a_weekend_is_refused(self):
        """
        🔑 **ولا يمتدّ الموعد إلى يوم العمل التالي — والامتناع هنا هو الفرق
        بين حاسبة ومستشار.**

        المدّة المعدودة بأيام العمل لا تنتهي في يوم عطلة؛ فإن وقع الموعد على
        يوم غير يوم عمل فالسؤال صار **حكماً في القاعدة** (أيمتدّ؟) لا حساباً.
        ومن أراد المدّ فليأتِ بحكمه، وليكن صريحاً — لا أن يُخترع في صمت فيُكتب
        في المذكرة موعد لم يُقرّه أحد.
        """
        friday = date(2026, 6, 5)  # الجمعة، عطلة نهاية الأسبوع الافتراضية.
        self.assertEqual(friday.weekday(), 4)
        with self.assertRaises(ValueError):
            is_expired(friday, friday, WORKING_DAYS, TEST_WEEKEND_ONLY)
        # وإذا كان الموعد يوم عمل فالجواب ممكن.
        sunday = date(2026, 6, 7)
        self.assertFalse(is_expired(sunday, sunday, WORKING_DAYS, TEST_WEEKEND_ONLY))
        self.assertTrue(is_expired(sunday, sunday + timedelta(days=1), WORKING_DAYS, TEST_WEEKEND_ONLY))


class TestConventionsAreData(unittest.TestCase):
    """
    الاتفاقية **بيانات لا عرف مكتوب في الشروط** — وهذا ما يجعل العدّ قابلاً
    للفحص: من نادى العدّ نادى اتفاقيةً باسمها، وظهر اسمها في الحصيلة. ولو
    كانت الاتفاقية سلوكاً ضمنياً في الشروط لما أمكن فحص «بأيّ حدٍّ عُدّ؟»
    أصلاً — وهو السؤال الذي جاء هذا الملف له.
    """

    def test_the_four_conventions_the_lawyer_asked_for_are_declared(self):
        """الاتفاقيات الأربع المطلوبة — بأسمائها وبترتيبها المقصود."""
        self.assertEqual(
            [convention.key for convention in CONVENTIONS],
            [
                "calendar_exclusive",
                "calendar_inclusive_end",
                "working_days",
                "months_whole",
            ],
        )

    def test_every_convention_has_a_note_saying_when_it_is_the_right_one(self):
        """
        لكل اتفاقية **سطر يبيّن متى تصلح**، لا حكماً على واقعة.

        والسطر العربي مقصود: من قرأ «حين تكون النهاية حدّاً» عرف أن الاختيار
        سؤالٌ يُسأل، لا نتيجة تُؤخذ.
        """
        for convention in CONVENTIONS:
            with self.subTest(key=convention.key):
                self.assertTrue(convention.label.strip())
                self.assertTrue(convention.note.strip())
                self.assertGreater(len(convention.note), 20)
                self.assertIn(convention.unit_basis, (DayCount.CALENDAR, DayCount.WORKING))
                self.assertIsInstance(convention.include_start, bool)
                self.assertIsInstance(convention.include_end, bool)

    def test_the_inclusive_end_field_is_the_one_that_moves_1307_to_1308(self):
        """
        🔑 **حقل واحد هو الفرق بين الرقمين** — فيُفحص بعينه.

        ``calendar_exclusive`` و``calendar_inclusive_end`` يتّفقان في كلّ شيء
        إلا ``include_end``. ولو أُضيف حقلٌ آخر يفترقان فيه لصار الفرق بين
        الرقمين مجهول المصدر.
        """
        self.assertEqual(CALENDAR_EXCLUSIVE.include_start, CALENDAR_INCLUSIVE_END.include_start)
        self.assertEqual(CALENDAR_EXCLUSIVE.unit_basis, CALENDAR_INCLUSIVE_END.unit_basis)
        self.assertFalse(CALENDAR_EXCLUSIVE.include_end)
        self.assertTrue(CALENDAR_INCLUSIVE_END.include_end)

    def test_the_named_constants_are_the_table_itself(self):
        """
        الثوابت المختصرة **مشتقّة من الجدول** لا مكرَّرة عنه.

        ولو كُتبت تعريفاً ثانياً لأمكن تعديل اتفاقية في الجدول وبقاء الثابت
        على القديم — فيُطبَّق على مدّة عدٌّ غير الذي في الجدول، وهو العيب نفسه
        (معياران لشيء واحد).
        """
        self.assertIs(CALENDAR_EXCLUSIVE, CONVENTIONS[0])
        self.assertIs(CALENDAR_INCLUSIVE_END, CONVENTIONS[1])
        self.assertIs(WORKING_DAYS, CONVENTIONS[2])
        self.assertIs(MONTHS_WHOLE, CONVENTIONS[3])
        self.assertEqual(convention_for("months_whole"), MONTHS_WHOLE)

    def test_an_unknown_convention_is_none_not_a_default(self):
        """
        ⚠️ الاتفاقية المجهولة ``None`` — **ولا يُطبَّق عدٌّ افتراضي**.

        ولو أعادت الدالّة اتفاقيةً افتراضية لصارت كلّ مدّة مجهولة الأسانيد
        معدودةً بعدٍّ لم يُطلب، وسكت الجميع عنه.
        """
        self.assertIsNone(convention_for("لا-وجود"))
        self.assertIsNone(convention_for(""))
        self.assertIsNone(convention_for("CALENDAR_EXCLUSIVE"))  # المفتاح آليّ دقيق

    def test_a_convention_without_a_key_is_refused(self):
        """والاتفاقية بلا مفتاح لا تُطلب بالاسم — فترفض عند الإنشاء."""
        with self.assertRaises(ValueError):
            Convention(
                key="  ",
                label="بلا مفتاح",
                include_start=False,
                include_end=False,
                unit_basis=DayCount.CALENDAR,
                note="لا",
            )

    def test_a_convention_with_an_unknown_basis_is_refused(self):
        """وأساس عدّ غير معروف يُرفض — فلا يُدخل نصٌّ حرّ في العدّ."""
        with self.assertRaises(ValueError):
            Convention(
                key="x",
                label="أساس مجهول",
                include_start=False,
                include_end=False,
                unit_basis="تقويمي",  # type: ignore[arg-type]
                note="لا",
            )

    def test_the_module_says_the_choice_belongs_to_the_rule(self):
        """
        ⚠️ **والحدّ مكتوب في الكود لا في وثيقة خارجية.**

        لأن من يقرأ العدّ يقرأ الكود، والتحذير الذي يعيش في ملف آخر لا يُقرأ
        مع ما يحذّر منه. والاختبار يثبّت وجود العبارتين اللتين تمنعان أن يُنسب
        إلى الملف حكمٌ قانوني: أنّ اختيار الاتفاقية **قانون لا حساب**، وأنه
        **لا يُكتب في الملف ربطٌ بين مدّة واتفاقية**.
        """
        source = _module_source()
        self.assertIn("اختيار الاتفاقية قانون", source)
        self.assertIn("لا يُكتب هنا أيّ ربط", source)
        self.assertIn("للمحامي", source)
        self.assertIn("المحامي", source)

    def test_conventions_are_frozen(self):
        """الاتفاقية لا تُعدَّل بعد إنشائها — فلا تتبدّل قاعدة أثناء تشغيل."""
        with self.assertRaises(Exception):
            CALENDAR_EXCLUSIVE.include_end = True  # type: ignore[misc]


class TestTheRulesTableShapeIsEmptyOfLaw(unittest.TestCase):
    """
    🔑 **جدول المدد: الشكل موجود، والمحامي يملؤه — ولا مدّة واحدة في الملف.**

    والسبب مكتوب في الوحدة ومُعادٌ هنا لأنه أهمّ ما في هذا الصنف: المدّة
    المحفوظة في الكود **تصير خطأً صامتاً في اللحظة التي يتغيّر فيها النصّ** —
    تُعدَّل المادة من ثلاثين يوماً إلى ستين، ويبقى الجدول على القديم، فيُحسب
    الموعد على قاعدة ملغاة **بثقة**، وهو أسوأ من الجهل: الجهل يوقف الكاتب،
    والثقة تمضي به إلى المذكرة.
    """

    def test_rule_for_returns_none_for_an_unknown_key(self):
        """
        🔑 **المفتاح المجهول ``None`` لا قاعدة افتراضية.**

        و``None`` هنا **جواب مقصود لا فشل**: معناه أن المدّة غير محقَّقة، وهو
        ما يجب أن يُقال صراحةً بدل أن يُخمَّن مقدارٌ من عند الحاسبة — لأن
        المدّة المخترعة تمضي إلى المذكرة.
        """
        rule = self._example_rule()
        self.assertIs(rule_for("example", (rule,)), rule)
        self.assertIsNone(rule_for("لا-وجود", (rule,)))
        self.assertIsNone(rule_for("example", ()))
        self.assertIsNone(rule_for("", (rule,)))

    def test_there_is_no_rules_table_in_the_module(self):
        """
        ⚠️ **ولا جدول مدد محفوظ في الوحدة.**

        فالدالّة **تستقبل** الجدول، فلا يمكن أن يُحسب موعد من قاعدة لم يأتِ بها
        المحامي في هذا التشغيل — وهذا أقوى من تعليق يقول «لا تُضِف مدّة».
        """
        self.assertFalse(hasattr(deadlines, "RULES"))
        self.assertFalse(hasattr(deadlines, "DEADLINE_RULES"))
        with self.assertRaises(TypeError):
            rule_for("example")  # type: ignore[call-arg]

    def test_no_deadline_rule_is_constructed_in_the_module_code(self):
        """
        ⚠️ **ويفحص نصّ الوحدة بالتحليل النحوي فلا يمرّ فيها سطر قاعدة واحد.**

        وأمثلة التوثيق (``>>>``) تُنشئ قواعد للشرح — وهي **نصوص** لا تُنفَّذ،
        فلا تُحسب. والفحص على ما يُنفَّذ وحده.
        """
        self.assertEqual(_calls_named(_module_tree(), "DeadlineRule"), [])

    def test_the_module_states_why_it_holds_no_period(self):
        """
        والسبب مكتوب في الكود: المدّة المحفوظة **تصير خطأً حين يتغيّر النصّ**،
        ولا شيء في المنظومة يُبلّغ بذلك.
        """
        source = _module_source()
        self.assertIn("لا تُحفظ مدّة واحدة في الجدول", source)
        self.assertIn("تصير خطأً", source)
        self.assertIn("source", source)

    def test_describe_rule_says_a_missing_source_is_missing(self):
        """
        ⚠️ **والمصدر الفارغ يُقال، ولا يُطبع السطر كأن له سنداً.**

        المدّة بلا مصدر **رأيٌ لا قاعدة**، وعلى قاعدة `labour_rules.py`: يُقال
        ذلك ولا يُخفى.
        """
        text = describe_rule(self._example_rule())
        self.assertIn("بلا مصدر مُدرَج", text)
        self.assertIn("مهلة اختبار", text)
        self.assertIn("٣٠ يوماً", text)
        self.assertIn(CALENDAR_INCLUSIVE_END.label, text)

    def test_describe_rule_names_an_unknown_convention_instead_of_guessing(self):
        """
        ⚠️ **والاتفاقية غير المعرَّفة تُقال** — ولا يُطبَّق لها عدٌّ افتراضي.

        فسكوتُ الحاسبة عن اتفاقية مجهولة يجعلها تعدّ بعدٍّ لم تقرّه قاعدة،
        ولا يظهر ذلك في المذكرة.
        """
        rule = DeadlineRule(
            key="x",
            label="مهلة بمصدر",
            amount=7,
            unit=Unit.DAYS,
            convention_key="لا-وجود",
            source="المادة ١",
            note="",
        )
        text = describe_rule(rule)
        self.assertIn("اتفاقية غير معرَّفة", text)
        self.assertIn("لا-وجود", text)
        self.assertIn("المادة ١", text)

    def test_describe_rule_renders_every_unit(self):
        """وكلّ وحدة تُعرض باسمها العربي — فلا يُطبع مفتاح آلي على محامٍ."""
        for unit, label in UNIT_LABELS.items():
            with self.subTest(unit=unit):
                rule = DeadlineRule(
                    key="x",
                    label="مهلة",
                    amount=3,
                    unit=unit,
                    convention_key="calendar_exclusive",
                    source="",
                    note="ملاحظة",
                )
                self.assertIn(label, describe_rule(rule))
                self.assertIn("ملاحظة", describe_rule(rule))

    def test_a_deadline_rule_is_frozen(self):
        """القاعدة لا تُعدَّل بعد إنشائها — فلا يتبدّل مقدار أثناء تشغيل."""
        rule = self._example_rule()
        with self.assertRaises(Exception):
            rule.amount = 60  # type: ignore[misc]

    @staticmethod
    def _example_rule() -> DeadlineRule:
        """قاعدة اختبار يملؤها الاختبار — ولا وجود لها في الوحدة."""
        return DeadlineRule(
            key="example",
            label="مهلة اختبار",
            amount=30,
            unit=Unit.DAYS,
            convention_key="calendar_inclusive_end",
            source="",
            note="",
        )


class TestNoHolidayCalendarIsEmbedded(unittest.TestCase):
    """
    🔑 **لا يُدرَج تاريخ عطلة واحد في الوحدة — والفحص على النصّ لا على النوايا.**

    والسند عملي: العطلات الرسمية تُعلَن كلّ سنة وتُعدَّل، فالتقويم المحفوظ في
    الكود يصير خطأً في السنة التالية بلا أن يُبلّغ أحد — فيُنتج **موعداً
    متأخّراً** عن الموعد الحقيقي، والمدّ الزائد لا يظهر في الورقة. ولا يكفي أن
    يُكتب في تعليق «لا تُضِف عطلة»: التعليق لا يوقف أحداً. فالفحص يقرأ شجرة
    النحو ويُسقط كلّ تاريخ حرفيّ وكلّ تقويم مُنشأ في الوحدة.

    ⚠️ **والأمثلة في التوثيق مستثناة بحكم البنية لا بحكم الاستثناء:** هي نصوص
    في الشجرة، فلا تُنفَّذ ولا تُحسب — والفحص على ما يُنفَّذ.
    """

    def test_no_holiday_calendar_is_embedded(self):
        """
        🔑 **الوحدة لا تحتوي تاريخاً حرفياً واحداً في كودها.**

        فكلّ تقويم عطلات — أيّ تقويم — لا بدّ أن يُكتب بتواريخ حرفية، فالفحص
        عليها يمنع **إدخال تقويم** لا عطلةً بعينها. وهو أوسع من المطلوب وأقوى:
        لا «٢٠٢٦-٠١-٠١» ولا غيره.
        """
        literal_dates = []
        for node in _calls_named(_module_tree(), "date"):
            if node.args and all(
                isinstance(argument, ast.Constant) and isinstance(argument.value, int)
                for argument in node.args
            ):
                literal_dates.append(ast.unparse(node))
        self.assertEqual(
            literal_dates,
            [],
            f"تواريخ حرفية في كود الوحدة — وهذا تقويم مُدرَج: {literal_dates}",
        )

    def test_the_module_never_constructs_a_holiday_set(self):
        """
        🔑 **ولا يُنشئ الملف تقويم عطلات أصلاً** — لا فارغاً ولا ممتلئاً.

        فالتقويم **يُمرَّر** إلى الدالّة، ولا يُقرأ من الملف. وإنشاء تقويم داخل
        الوحدة — ولو فارغاً — يجعل العطلات قراراً في الكود لا مدخلاً من المحامي.
        """
        self.assertEqual(_calls_named(_module_tree(), "HolidaySet"), [])

    def test_the_default_weekend_is_declared_a_convention(self):
        """
        ⚠️ **ونهاية الأسبوع نفسها اتفاقية لا حقيقة كونية.**

        الجمعة والسبت هما الافتراض، ويُبدَّل بتقويم مورَّد (والاختبار يفحص
        التبديل في `TestWorkingDays`). والنصّ يقول إنها عرف لا حقيقة — فلا
        تُقرأ كأنها معلومة عن العالم.
        """
        self.assertEqual(DEFAULT_WEEKEND, frozenset({4, 5}))
        self.assertEqual(len(DEFAULT_WEEKEND), 2)
        source = _module_source()
        self.assertIn("عرفٌ لا حقيقة", source)
        self.assertIn("تُمرَّر", source)

    def test_the_holiday_type_is_a_dataclass_of_supplied_data(self):
        """والتقويم حصيلة بيانات: مجموعة أيام ومجموعة أيام أسبوع، وبلا سلوك مخفيّ."""
        fields = set(HolidaySet.__dataclass_fields__)
        self.assertEqual(fields, {"days", "weekend", "label"})
        self.assertEqual(TEST_WEEKEND_ONLY.days, frozenset())
        with self.assertRaises(Exception):
            TEST_WEEKEND_ONLY.label = "آخر"  # type: ignore[misc]

    def test_an_impossible_weekend_is_refused(self):
        """
        ⚠️ وتقويم كلّه عطل يُرفض — لا لأنه عطلة، بل لأنه **لا يوم عمل فيه**،
        فلو قُبل لانتظر `add_period` أبداً. وقيمة يوم خارج ٠–٦ تُرفض كذلك.
        """
        with self.assertRaises(ValueError):
            HolidaySet(frozenset(), weekend=frozenset({0, 1, 2, 3, 4, 5, 6}))
        with self.assertRaises(ValueError):
            HolidaySet(frozenset(), weekend=frozenset({7}))
        with self.assertRaises(ValueError):
            HolidaySet(frozenset(), weekend=frozenset({-1}))

    def test_a_working_day_holiday_set_answers_the_same_question_consistently(self):
        """و`is_working_day` هي السؤال الواحد: هل هذا اليوم يوم عمل؟ — وتُجاب مرة في موضع."""
        holidays = HolidaySet(frozenset({date(2026, 6, 3)}), label="اختبار")
        self.assertFalse(holidays.is_working_day(date(2026, 6, 3)))  # عطلة مورَّدة
        self.assertFalse(holidays.is_working_day(date(2026, 6, 5)))  # جمعة
        self.assertFalse(holidays.is_working_day(date(2026, 6, 6)))  # سبت
        self.assertTrue(holidays.is_working_day(date(2026, 6, 4)))   # خميس


class TestAgreementWithLabourRules(unittest.TestCase):
    """
    🔑 **العدّ واحد: `deadlines.service_period` و`labour_rules.service_period`.**

    و`labour_rules.py` ثبّتت العدّ بعد أن أنتجت نسختان رقمين لمدّة واحدة
    (١٣٠٧ و١٣٠٨)، ثم عاد الخطأ في موضع ثالث فكاد يُنتج ١٣٠٨ مكان ١٣٠٧. فنسخة
    ثانية هنا **تخالف بصمت**، وهي أسوأ من غياب الدالّة. ولهذا لا يوجد في
    `deadlines.py` عدُّ مدّة خدمة ثانٍ: الدالّة **تنادي** العدّ القائم،
    والتفكيك التقويمي يأتي من `labour_rules` مباشرةً.

    ⚠️ والاختبار يثبّت الاتفاق **على مدى تواريخ** لا على واقعة واحدة: فالاتفاق
    في واقعة قد يكون مصادفة، والاتفاق في عشرين مدّة مختلفة دليل.
    """

    #: مدد مختلفة الطول والنوع — منها الكبيسة والقصيرة والشهرية والسنوية.
    CASES: tuple[tuple[date, date], ...] = (
        (date(2023, 2, 1), date(2026, 8, 31)),   # الواقعة تحت المراجعة
        (date(2024, 2, 29), date(2025, 2, 28)),  # تبدأ من يوم كبيس
        (date(2024, 2, 28), date(2024, 3, 1)),   # تعبر اليوم الكبيس
        (date(2024, 1, 1), date(2025, 1, 1)),    # سنة كبيسة كاملة
        (date(2023, 1, 1), date(2024, 1, 1)),    # سنة غير كبيسة
        (date(2026, 1, 1), date(2026, 1, 2)),    # يوم واحد
        (date(2026, 6, 1), date(2026, 6, 7)),    # أسبوع
        (date(2026, 1, 1), date(2026, 1, 31)),   # شهر يناير
        (date(2020, 3, 15), date(2026, 8, 31)),  # مدّة طويلة
        (date(2026, 8, 31), date(2026, 8, 31)),  # مدّة صفرية
    )

    def test_the_two_service_periods_agree_exactly(self):
        """
        🔑 **اليوم نفسه، والفكّ نفسه، في كلّ الحالات.**

        ``days`` تُقابل ``days``، و``(whole_years, whole_months,
        remainder_days)`` تُقابل ``(years, months, remainder_days)``. فلا
        يفترق الرقمان في موضع ولا في حالة حدّية.
        """
        for start, end in self.CASES:
            with self.subTest(start=start, end=end):
                mine = deadlines.service_period(start, end)
                theirs = labour_rules.service_period(start, end)
                self.assertEqual(mine.days, theirs.days)
                self.assertEqual(
                    (mine.whole_years, mine.whole_months, mine.remainder_days),
                    (theirs.years, theirs.months, theirs.remainder_days),
                )
                # والعدّ الواحد في موضعه: `period_days`.
                self.assertEqual(mine.days, labour_rules.period_days(start, end))
                self.assertEqual(mine.days, (end - start).days)

    def test_the_inclusive_direction_agrees_too(self):
        """
        والاتجاه الآخر: يوم النهاية محسوباً — ``calendar_inclusive_end``
        تقابل ``labour_rules.period_days(..., exclusive=False)``.
        """
        for start, end in self.CASES:
            with self.subTest(start=start, end=end):
                mine = period_between(start, end, CALENDAR_INCLUSIVE_END)
                theirs = labour_rules.service_period(start, end, inclusive_end=True)
                self.assertEqual(mine.days, theirs.days)
                self.assertEqual(
                    (mine.whole_years, mine.whole_months, mine.remainder_days),
                    (theirs.years, theirs.months, theirs.remainder_days),
                )
                self.assertEqual(mine.days, labour_rules.period_days(start, end, exclusive=False))

    def test_deadlines_has_no_second_count_and_no_second_decomposition(self):
        """
        ⚠️ **ويفحص النصّ: لا عدّ ثانٍ ولا تفكيك ثانٍ في الوحدة.**

        فوجود ``def _decompose`` أو ``def period_days`` هنا يعني نسخةً ثانية
        تنحرف عن الأولى بلا إنذار. والوحدة **تنادي** تفكيك `labour_rules`
        وتسمّيه باسمه، فيُقرأ ذلك في النصّ لا في النوايا.
        """
        source = _module_source()
        self.assertIn("labour_rules.service_period", source)
        self.assertNotIn("def _decompose", source)
        self.assertNotIn("def period_days", source)
        self.assertNotIn("def service_period(start, end, inclusive_end", source)

    def test_the_month_walk_agrees_with_the_labour_rules_step(self):
        """
        ⚠️ **وتقييد الأشهر لا يخالف تقييد `labour_rules`.**

        `deadlines` تحتاج تقدّم الأشهر في `add_period`، و`labour_rules` تحتاجه
        في التفكيك — فلو افترق التقييد لأنتج الموضعان تاريخين لتاريخ واحد.
        والفحص يقابل الدالّتين على الحالات الحدّية (٣١ و٢٩ فبراير).
        """
        step = getattr(labour_rules, "_step_month", None)
        if step is None:
            self.skipTest("لا دالّة تقدّم أشهر ظاهرة في labour_rules بهذا الاسم.")
        anchors = (
            date(2026, 1, 31),
            date(2024, 1, 31),
            date(2024, 2, 29),
            date(2026, 3, 31),
            date(2026, 8, 31),
        )
        for anchor in anchors:
            for months in (1, 2, 6, 12, 13, 25):
                with self.subTest(anchor=anchor, months=months):
                    self.assertEqual(
                        deadlines._shift_months(anchor, months),
                        step(anchor, months),
                    )


class TestTheArithmeticIsCoherent(unittest.TestCase):
    """
    ⚠️ **الضمان الداخلي: الإضافة والعدّ متعاكستان بالاتفاقية نفسها.**

    فإذا أُضيفت مدّة إلى تاريخ ثم عُدّت المدّة بينهما بالاتفاقية المعطاة
    رجعت ``amount`` نفسها — لا زادت يوماً ولا نقصت. وهذا الضمان هو الذي يمنع
    يوماً زائداً في الموعد من حيث لا يُرى: الموعد يُكتب في المذكرة، ولا أحد
    يعيد عدّ المدّة بين طرفيه.
    """

    def test_adding_and_counting_are_inverse_under_each_calendar_convention(self):
        """٣٠ يوماً تُضاف ثم تُعدّ: ٣٠ — تحت الاتفاقيتين التقويميتين."""
        for convention in (CALENDAR_EXCLUSIVE, CALENDAR_INCLUSIVE_END, MONTHS_WHOLE):
            for amount in (1, 7, 30, 90, 365):
                with self.subTest(convention=convention.key, amount=amount):
                    start = date(2026, 3, 1)
                    deadline = add_period(start, amount, Unit.DAYS, convention)
                    self.assertEqual(
                        period_between(start, deadline, convention).days,
                        amount,
                    )

    def test_adding_and_counting_are_inverse_in_working_days(self):
        """و‏٣ و٥ و١٠ أيام عمل تُضاف ثم تُعدّ بالعدد نفسه — مع القفز على العطلة."""
        for amount in (1, 3, 5, 10):
            for holidays in (TEST_WEEKEND_ONLY, TEST_ONE_HOLIDAY, TEST_FRIDAY_ONLY):
                with self.subTest(amount=amount, holidays=holidays.label):
                    start = date(2026, 6, 1)
                    deadline = add_period(start, amount, Unit.DAYS, WORKING_DAYS, holidays)
                    self.assertEqual(
                        period_between(start, deadline, WORKING_DAYS, holidays).days,
                        amount,
                    )

    def test_counted_days_and_the_day_count_never_disagree(self):
        """
        ⚠️ **والعدّان — عدد الأيام والأيام المحسوبة — لا يفترقان.**

        فـ``counted_days`` هي **شرح** العدد، ولو اختلف الشرح عن الرقم لكان في
        الملف معياران. والفحص يجري على عدّة اتفاقيات ومدد مختلفة الطول.
        """
        conventions = (CALENDAR_EXCLUSIVE, CALENDAR_INCLUSIVE_END, MONTHS_WHOLE)
        starts = (date(2024, 1, 1), date(2024, 2, 28), date(2026, 6, 1))
        for convention in conventions:
            for start in starts:
                for offset in (0, 1, 2, 30, 365, 366, 1307):
                    end = start + timedelta(days=offset)
                    with self.subTest(convention=convention.key, start=start, offset=offset):
                        self.assertEqual(
                            len(counted_days(start, end, convention)),
                            period_between(start, end, convention).days,
                        )

    def test_the_same_inputs_always_give_the_same_outcome(self):
        """
        🔑 **المدخل نفسه يُعطي النتيجة نفسها، دائماً — بلا حالة محفوظة.**

        وهذا ما كان مفقوداً في العيب الرابع (`labour_rules.py`): مذكرة حملت
        رقمين لمدّة واحدة. والدالّة النقية لا تستطيع أن تفعل ذلك — والاختبار
        يثبّت الضمان لا الدالّة.
        """
        first = period_between(START, END, CALENDAR_EXCLUSIVE, TEST_WEEKEND_ONLY)
        results = {
            period_between(START, END, CALENDAR_EXCLUSIVE, TEST_WEEKEND_ONLY)
            for _ in range(5)
        }
        self.assertEqual(len(results), 1)
        self.assertEqual(first, results.pop())
        self.assertEqual(first.describe(), first.describe())
        self.assertEqual(
            add_period(START, 30, Unit.DAYS, CALENDAR_EXCLUSIVE),
            add_period(START, 30, Unit.DAYS, CALENDAR_EXCLUSIVE),
        )

    def test_a_reversed_period_raises_rather_than_returning_zero(self):
        """
        المدّة المعكوسة **ترفع استثناءً** ولا تُرجع صفراً.

        ولو أُرجع صفر لصار الخطأ في المدخل **نقصاً صامتاً في المستحقّ**:
        المذكرة تُسلَّم وفيها مدّة صفر بلا سبب ظاهر.
        """
        for call in (
            lambda: period_between(END, START, CALENDAR_EXCLUSIVE),
            lambda: service_period(END, START),
            lambda: counted_days(END, START, CALENDAR_EXCLUSIVE),
            lambda: period_between(END, START, CALENDAR_INCLUSIVE_END),
        ):
            with self.subTest(call=call):
                with self.assertRaises(ValueError):
                    call()

    def test_a_negative_amount_raises(self):
        """والمدّة السالبة سؤال آخر: تُرفض ولا يُخترع لها عدٌّ رجوعي."""
        with self.assertRaises(ValueError):
            add_period(START, -1, Unit.DAYS, CALENDAR_EXCLUSIVE)

    def test_a_zero_period_gives_the_same_date(self):
        """
        المدّة الصفرية تُعيد البداية نفسها — ولا تاريخ «قبل البداية بيوم».

        ⚠️ وهذا استثناء معلن: لو طُبّقت صيغة العدّ على صفر لتقدّم الموعد عند
        الاتفاقية التي تحسب يوم النهاية — وهو موعد قبل الطلب، ولا معنى له.
        """
        self.assertEqual(add_period(START, 0, Unit.DAYS, CALENDAR_INCLUSIVE_END), START)
        self.assertEqual(add_period(START, 0, Unit.DAYS, CALENDAR_EXCLUSIVE), START)
        self.assertEqual(add_period(START, 0, Unit.MONTHS, MONTHS_WHOLE), START)

    def test_a_zero_length_period_is_zero_days(self):
        """ومدّة من تاريخ إلى نفسه: صفر أيام بعدّ الحدّ، ويوم واحد بعدّ النهاية."""
        self.assertEqual(period_between(START, START, CALENDAR_EXCLUSIVE).days, 0)
        self.assertEqual(period_between(START, START, CALENDAR_INCLUSIVE_END).days, 1)
        self.assertEqual(counted_days(START, START, CALENDAR_EXCLUSIVE), ())


class TestModuleGuarantees(unittest.TestCase):
    """
    ضمانات معمارية — كـ `citations.py` و`labour_rules.py`:
    مكتبة قياسية وحدها، ولا شبكة، ولا حالة، ولا إدخال/إخراج، ولا طبع.
    """

    def test_imports_are_stdlib_plus_labour_rules_only(self):
        """
        ⚠️ **لا تبعية خارجية** — وهي شرط عملي لا ذوقي: الحاسبة تُستدعى في مسار
        الصياغة، وتبعية خارجية هنا تعني أن الاختبار يحتاج شبكةً أو مفتاحاً،
        فلا يُشغَّل، فلا يحمي شيئاً. و`labour_rules` **ليست تبعية**: هي وحدة
        المشروع نفسه، والموضع الواحد لعدّ المدّة.
        """
        imported = set(
            re.findall(
                r"^(?:from|import)\s+([A-Za-z_][\w\.]*)",
                _module_source(),
                re.MULTILINE,
            )
        )
        allowed = {"__future__", "dataclasses", "datetime", "enum", "typing", "labour_rules"}
        self.assertTrue(imported <= allowed, f"استيرادات: {sorted(imported - allowed)}")

    def test_no_environment_network_or_printing(self):
        """
        لا بيئة، ولا شبكة، ولا طبع.

        و«لا طبع» مقصود: وحدة تُطبع أثناء الاستيراد تُلوّث مخرج أي مسار يستدعيها
        — والحاسبة تُستدعى من الخادم ومن الاختبار معاً.
        """
        source = _module_source()
        for forbidden in ("os.environ", "requests.", "socket", "http", "print("):
            self.assertNotIn(forbidden, source)

    def test_the_result_carries_its_basis_and_no_module_level_state(self):
        """
        لا حالة على مستوى الوحدة: كلّ نداء يُعطي نتيجته من مدخلاته، والحصيلة
        تحمل أساسها ومفتاح اتفاقيتها.

        وفحص الحالة عمليّ: نتائج مختلفة لمداخل مختلفة، ومتساوية للمدخل نفسه —
        ولو كان في الوحدة عدّاد أو مخزون لظهر الفرق في النداء الثالث.
        """
        first = period_between(START, END, CALENDAR_EXCLUSIVE)
        second = period_between(WEEK_START, WEEK_END, CALENDAR_INCLUSIVE_END)
        third = period_between(START, END, CALENDAR_EXCLUSIVE)
        self.assertEqual(first, third)
        self.assertNotEqual(first, second)
        self.assertEqual(first.convention_key, "calendar_exclusive")
        self.assertEqual(second.convention_key, "calendar_inclusive_end")

    def test_the_period_is_frozen(self):
        """الحصيلة لا تُعدَّل بعد إنشائها — فلا يتبدّل رقم أثناء العرض."""
        period = service_period(START, END)
        self.assertIsInstance(period, Period)
        with self.assertRaises(Exception):
            period.days = 1  # type: ignore[misc]

    def test_the_conventions_tuple_is_immutable(self):
        """وجَدول الاتفاقيات غير قابل للتعديل — لا تُضاف اتفاقية في زمن التشغيل."""
        self.assertIsInstance(CONVENTIONS, tuple)
        with self.assertRaises(Exception):
            CONVENTIONS[0] = CONVENTIONS[0]  # type: ignore[index]

    def test_the_module_is_arabic_first_in_its_documentation(self):
        """
        الوحدة عربية في شرحها — ولماذا: من قرأها قرأ **الحدّ** لا الكود وحده،
        والحدّ في هذا الملف (اختيار الاتفاقية قانون، ولا مدّة ولا عطلة تُدرَج)
        أهمّ من الحساب نفسه.
        """
        source = _module_source()
        self.assertIn("يوم البداية", source)
        self.assertIn("السنة الكبيسة", source)
        self.assertIn("يُخمَّن", source)
        self.assertIn("labour_rules", source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
