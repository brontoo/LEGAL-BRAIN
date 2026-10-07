"""
الأخطاء الستة السابقة — اختبارات دائمة تمنع عودتها.
============================================================================

⚠️ **هذا الملف ليس اختباراً لوحدة، بل أرشيف لعيوب وقعت فعلاً.**

كل صنف فيه يقابل خطأً ظهر في مذكرة حقيقية، رصده محامٍ راجع ثلاث نسخ متتالية.
وقد كان بعضها يتكرّر بعد أن نُبِّه النموذج إليه صراحةً — **فالتنبيه في محادثة
لا يدخل المسار، وهذا الملف يدخله.**

⚠️ **ولماذا اختبار لا تعليق؟** لأن التعليق يوصي، والاختبار يُلزِم. ومن راجع هذا
المشروع لاحقاً قد لا يعرف أن «رفض المخالصة» كان يوماً «رفض الاستلام» — **إلا
إن فشل هذا الملف.** وحينها يعرف.

⚠️ **والحالات مكتوبة كما وقعت** — بالأسماء والأرقام نفسها — **لأن اختباراً
مجرَّداً لا يُذكِّر بأحد.**
"""

from __future__ import annotations

import pathlib
import sys
import unittest
from datetime import date
from decimal import Decimal

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from attribution import summarize as summarize_attribution
from attribution import verify_attributions
from citations import Evidence
from labour_rules import (
    end_of_service_gratuity,
    leave_pay,
    rules_block,
    service_period,
)
from review import parse_review


# ── الوقائع كما وردت في الموجز الحقيقي ─────────────────────────────────────
BASIC_WAGE = Decimal("5000")     # الراتب الأساسي
GROSS_WAGE = Decimal("8000")     # الراتب الإجمالي
START = date(2023, 2, 1)         # تاريخ الالتحاق
END = date(2026, 8, 31)          # آخر يوم عمل فعلي


def _evidence(text: str, ref: str = "L1") -> Evidence:
    """مقطع مسترجَع — بنصّه فقط، فالمُراجع لا يُعطى إلا النصّ."""
    return Evidence(
        ref=ref,
        chunk_id="1",
        document_name="المرسوم بقانون اتحاديّ رقم 33 لسنة 2021",
        text=text,
        similarity=0.9,
        tool="legislation",
    )


class TestDefect2LeavePayBasis(unittest.TestCase):
    """
    العطب ② — بدل الإجازة محسوباً على الأجر **الإجمالي** لا الأساسي.
    ========================================================================
    ⚠️ **وهذا أخطر ما في القائمة مالياً**، لأنه يُنقص حقّ العامل لا حقّ الشركة.
    والمستشار يكتب للشركة، **فيُخشى أن يُغفل حقّ الخصم** — وهو ما يُضعف موقف
    موكّله لا يُقوّيه.

    والقاعدة: المادة ٢٩/٩ تجعل الأساس هو الأجر الأساسي، ما لم يثبت اتفاق يمنح
    العامل ميزة أفضل.
    """

    def test_eleven_days_on_the_basic_wage_not_the_gross(self):
        """١١ يوماً على أساسي ٥٠٠٠ = ١,٨٣٣٫٣٣ — لا ٢,٩٣٣٫٣٣."""
        pay = leave_pay(11, BASIC_WAGE, GROSS_WAGE)
        self.assertEqual(str(pay.on_basic), "1833.33")
        self.assertEqual(str(pay.on_gross), "2933.33")
        self.assertNotEqual(str(pay.on_basic), str(pay.on_gross))

    def test_the_calculator_names_the_basis_the_rules_require(self):
        """
        ⚠️ **والقيمة الحقيقية هنا ليست الرقم بل الإفصاح.**

        الحاسبة تُظهر **الأساسين** وتقول أيّهما تجبّه القاعدة. فالخطأ يصير
        مرئياً في المذكرة بدل أن يكون صامتاً — ولو أظهرت رقماً واحداً لما
        استطاع أحد كشفه.
        """
        pay = leave_pay(11, BASIC_WAGE, GROSS_WAGE)
        self.assertTrue(hasattr(pay, "required_amount"))
        self.assertEqual(str(pay.required_amount), "1833.33")

    def test_twenty_four_days_on_the_basic_wage(self):
        """٢٤ يوماً على الأساسي = ٤,٠٠٠ — وهو مطلب المدعي الآخر."""
        self.assertEqual(str(leave_pay(24, BASIC_WAGE).on_basic), "4000.00")

    def test_a_gross_wage_figure_is_never_the_required_one_here(self):
        """⚠️ ولا يجوز أن يكون الإجمالي هو «المستحق» في بدل الإجازة."""
        pay = leave_pay(11, BASIC_WAGE, GROSS_WAGE)
        self.assertNotEqual(str(pay.required_amount), str(pay.on_gross))


class TestDefect3NoticePayAndExcusal(unittest.TestCase):
    """
    العطب ③ — إنكار أجر مدة الإشعار بحجّة **الإعفاء من الحضور**.
    ========================================================================
    ⚠️ والمادة ٤٣/٢ تُبقي العقد قائماً خلال مهلة الإنذار، والأجر مستحقّ
    كاملاً. **والإعفاء صدر من الشركة نفسها** — فلا يصير سبباً لإنقاص حقّ
    العامل. وعدم أداء المهام بسبب إعفاء صاحب العمل **ليس وحده** سبباً لرفض
    الأجر.

    ⚠️ **وهذا العطب عاد بعد تصحيح**: النموذج أقرّ بالقاعدة ثم **امتنع عن
    الحساب** وقال إن المبلغ «غير محقَّق بالملف». حذف حساب مختلف عليه **ليس
    تصحيحاً له**.
    """

    def test_the_block_orders_the_computation_rather_than_forbidding_it(self):
        """
        🔑 **وهذا اختبار انحدار على صياغة، لا على حساب.**

        كان في الموجّه «**لا تحسب أنت** أيّ تاريخ ولا مدّة ولا مبلغاً» —
        فأخذها النموذج حرفياً وامتنع عن الحساب كله. **فالمنع والإذن كلاهما
        يُنتج مذكرة بلا أرقام** — والفرق بينهما هو الفرق بين مذكرة صامتة
        ومذكرة محسوبة.
        """
        block = rules_block()
        self.assertIn("احسب", block)
        self.assertNotIn("لا تحسب", block)

    def test_the_nine_days_are_computable_from_the_facts_given(self):
        """
        والحساب المعلوم المدخلات **يُجرى** — ٨٠٠٠ ÷ ٣٠ × ٩ = ٢,٤٠٠.
        """
        daily = GROSS_WAGE / Decimal("30")
        self.assertEqual(str((daily * 9).quantize(Decimal("0.01"))), "2400.00")


class TestDefect1ServicePeriod(unittest.TestCase):
    """
    العطب ① — مدة الخدمة **١٢٧٨ يوماً** والصواب ١٣٠٧.
    ========================================================================
    ⚠️ والفرق ٢٩ يوماً — **شهر كامل تقريباً** — جاء من العدّ اليدوي.

    ⚠️ **والمدة تحتوي ٢٩ فبراير ٢٠٢٤** (سنة كبيسة)، فمن عدّ بضرب السنوات في
    ٣٦٥ يُخطئ. **ولذلك تُحسب بالتاريخ لا بالتقدير.**
    """

    def test_the_period_is_1307_days_not_1278(self):
        """🔑 العطب التاريخي — مثبَّتاً بالرقم الذي وقع."""
        period = service_period(START, END)
        self.assertEqual(period.days, 1307)
        self.assertNotEqual(period.days, 1278)

    def test_the_period_crosses_a_leap_day(self):
        """ولولا ٢٩ فبراير ٢٠٢٤ لكان الرقم غيره — فالعدّ بالتاريخ لازم."""
        feb_28 = service_period(date(2024, 2, 28), date(2024, 2, 29))
        self.assertGreaterEqual(feb_28.days, 1)


class TestDefect6GratuityQuantum(unittest.TestCase):
    """
    العطب ⑥ — **صيغة قانون ملغى** في مبلغ المكافأة.
    ========================================================================
    ⚠️ كان في الكود «**نصف شهر**» (١٥ يوماً) لكل سنة من الخمس الأولى — **وهي
    صيغة القانون الاتحادي ٨ لسنة ١٩٨٠ الملغى.**

    ⚠️ **والمادة ٥١ من المرسوم بقانون ٣٣ لسنة ٢٠٢١ تجعلها ٢١ يوماً**، ثم
    ٣٠ يوماً. والفرق نحو ٢٨٪ — **وهو في حقّ العامل.**

    ⚠️ **والخطأ جاء من موجزٍ كتبتُه أنا للمنصة**، لا من النموذج. **والدرس أن
    القاعدة المكتوبة بلا مادةٍ تُراجَع تصير قانوناً ملغى يبدو سليماً.**
    """

    def test_1307_days_gives_the_twenty_one_day_figure(self):
        """١٢,٥٣٢٫٨٨ — ويوافق تقدير المُقيِّم المستقل (١٢,٥٤١٫٦٧) في حدود التقريب."""
        amount = end_of_service_gratuity(BASIC_WAGE, service_period(START, END))
        self.assertEqual(str(amount), "12532.88")

    def test_the_repealed_fifteen_day_figure_is_not_produced(self):
        """🔑 ورقم القانون الملغى (٨,٩٥٢٫٠٥) لا يجوز أن يظهر بعد اليوم."""
        amount = end_of_service_gratuity(BASIC_WAGE, service_period(START, END))
        self.assertNotEqual(str(amount), "8952.05")

    def test_one_year_is_twenty_one_days_of_the_basic_wage(self):
        """والتحقق المباشر: سنة واحدة = ٥٠٠٠ × ٢١ ÷ ٣٠ = ٣,٥٠٠ (لا ٢,٥٠٠)."""
        one_year = service_period(date(2023, 2, 1), date(2024, 2, 1))
        self.assertEqual(str(end_of_service_gratuity(BASIC_WAGE, one_year)), "3500.00")


class TestDefect4MisattributedArticle(unittest.TestCase):
    """
    العطب ④ — **نصّ منسوب إلى المادة ٤٣ وهو ليس نصّها**.
    ========================================================================
    ⚠️ وهذا العطب **لم يكشفه شيء عندنا قبل هذه الجولة**، لأنه كان يمرّ من
    `verify_citations` سالماً: **النصّ كان موجوداً في المقاطع فعلاً** — لكنه من
    عقد محدد المدة، والمادة ٤٣ الحالية لا تحمله.

    وقد قالها المُقيِّم بجملة تُثبَّت: **«إسناد صياغة غير صحيحة إلى مادة قانونية
    أخطر من عدم ذكر المادة أصلاً».**
    """

    #: نصّ المادة بنفسها
    ARTICLE_43 = (
        "المادة 43 : يجب أن يلتزم الطرفان بمدة الإنذار المتفق عليها، "
        "على ألا تقل عن ثلاثين يوماً."
    )
    #: النصّ الذي نقله النموذج ونسبه إليها — وهو من موضع آخر
    WRONG_TEXT = "عقد العمل غير المحدد المدة ينتهي بإرادة أي من الطرفين"

    def test_a_quotation_from_elsewhere_is_flagged_as_mismatched(self):
        """🔑 والعطب الحقيقي — يجب أن يُكشف ولا يمرّ."""
        draft = f"وتنص المادة 43 على أن «{self.WRONG_TEXT}»."
        outcome = verify_attributions(
            draft, [_evidence(self.ARTICLE_43)], lambda row: row.text
        )
        self.assertEqual(len(outcome.checks), 1)
        self.assertEqual(outcome.checks[0].status, "mismatched")
        self.assertGreaterEqual(summarize_attribution(outcome)["error_count"], 1)

    def test_the_articles_own_wording_is_matched(self):
        """وفي المقابل: النقل الأمين يمرّ — فالفحص لا يعترض على الصواب."""
        draft = (
            "وتنص المادة 43 على أن «يجب أن يلتزم الطرفان بمدة الإنذار "
            "المتفق عليها»."
        )
        outcome = verify_attributions(
            draft, [_evidence(self.ARTICLE_43)], lambda row: row.text
        )
        self.assertEqual(outcome.checks[0].status, "matched")
        self.assertTrue(summarize_attribution(outcome)["clean"])

    def test_an_article_no_passage_mentions_is_a_notice_not_an_error(self):
        """
        ⚠️ **والفرق مقصود:** مادة لم يُنتجها الاسترجاع **ثغرةٌ في الأرشيف**،
        لا **قولٌ خاطئ عن القانون**. ولا يُعاقَب المحامي على ما لم يصل إليه
        البحث.
        """
        draft = "وتنص المادة 99 على أنه «لا يجوز الفصل تعسفاً»."
        outcome = verify_attributions(
            draft, [_evidence(self.ARTICLE_43)], lambda row: row.text
        )
        self.assertEqual(outcome.checks[0].status, "absent")
        report = summarize_attribution(outcome)
        self.assertEqual(report["error_count"], 0)
        self.assertTrue(report["clean"])


class TestDefect5ChangedFact(unittest.TestCase):
    """
    العطب ⑤ — **تغيير الواقعة**: «رفض توقيع مخالصة» صارت «رفض استلام».
    ========================================================================
    ⚠️ **وهذا العطب تكرّر في ثلاث نسخ متتالية** — فهو منهجي لا عارض. **وأخطر
    ما فيه أنه يقلب المسؤولية**: فالأولى تُظهر شركة عرضت مستحقاتها، والثانية
    تُظهر شركة **علّقت الدفع على تنازل** — وهو ما تُحاسَب عليه.

    ⚠️ **والواقعة تُحفظ في `facts.py` بحالتها الإثباتية ومصدرها**، فيصير
    تغييرها قابلاً للكشف. **وهذا الصنف يثبّت الواقعة الأصلية نصّاً** حتى لا
    يضيع معنى «المخالصة» من هذا الملف.
    """

    #: الواقعة كما وردت — ولا يجوز أن تُقرأ بغير هذا المعنى
    FACT = (
        "رفض المدعي توقيع مخالصة تتضمن إقراراً باستلام جميع مستحقاته "
        "والتنازل عن أي مطالبات أخرى، وعلّقت الشركة الصرف على توقيعها."
    )
    DISTORTION = "امتنع المدعي عن استلام مستحقاته"

    def test_the_original_fact_names_the_release_and_the_condition(self):
        """🔑 عنصران لا يجوز أن يسقطا: «مخالصة» و«تعليق الصرف»."""
        self.assertIn("مخالصة", self.FACT)
        self.assertIn("علّقت", self.FACT)

    def test_the_distortion_loses_the_release_and_the_waiver(self):
        """
        ⚠️ **ومقارنة اللفظين تُظهر ما ضاع:** «المخالصة» و«التنازل» سقطا،
        فصار الامتناع بلا سبب.
        """
        self.assertNotIn("مخالصة", self.DISTORTION)
        self.assertNotIn("تنازل", self.DISTORTION)


class TestDefect7HedgingContradiction(unittest.TestCase):
    """
    العطب ⑦ — **إقرار متردّد مع حساب نهائي**: «مبدئياً ١٤٬٠٠٠» ثم طلب خصمها.
    ========================================================================
    ⚠️ والمذكرة قالت إن احتساب التحويل البنكي «مبدئي وقد يتغيّر»، ثم طلبت
    خصم ١٤٬٠٠٠ نهائياً. **فالتردّد في الإقرار والجزم في الطلب لا يجتمعان في
    مذكرة واحدة.**

    ⚠️ **وهذا الصنف يثبّت الحساب** — ٢٤٬٠٠٠ − ٦٬٠٠٠ − ٤٬٠٠٠ = ١٤٬٠٠٠ — **ليصير
    الرقمان معروضين معاً**، فيُختار أحدهما ويُدافَع عنه، بدل أن يُعرضا كليهما
    بصيغة ملتبسة.
    """

    LOAN = Decimal("24000")
    PAID_INSTALMENTS = Decimal("6000")
    BANK_TRANSFER = Decimal("4000")

    def test_the_two_balances_are_both_computable(self):
        """الرصيد الدفتري ١٨٬٠٠٠ — وبعد احتساب التحويل ١٤٬٠٠٠."""
        ledger = self.LOAN - self.PAID_INSTALMENTS
        with_transfer = ledger - self.BANK_TRANSFER
        self.assertEqual(ledger, Decimal("18000"))
        self.assertEqual(with_transfer, Decimal("14000"))

    def test_the_difference_is_exactly_the_undocumented_transfer(self):
        """⚠️ والفرق بين الرقمين هو **التحويل الذي لم يُقيَّد** — وهو موضع النزاع."""
        ledger = self.LOAN - self.PAID_INSTALMENTS
        with_transfer = ledger - self.BANK_TRANSFER
        self.assertEqual(ledger - with_transfer, self.BANK_TRANSFER)


class TestDefect6bReviewerCatchesDroppedEvidence(unittest.TestCase):
    """
    وأمانة المُراجع — الاعتراض الذي لا يُثبت نصّه **يُطرح**.
    ========================================================================
    ⚠️ وهذا يمنع مُراجعاً يخترع اعتراضات ليبدو مفيداً. **ومراجعة تُنذر دائماً
    لا تُنذر أبداً** — وهو نفس عطب «سيبويه» حين وسم ١١ سلوكاً صحيحاً كأخطاء.
    """

    DRAFT = "وتنص المادة 43 على أن «يجب أن يلتزم الطرفان بمدة الإنذار»."

    def test_an_objection_quoting_nothing_real_is_dropped(self):
        raw = (
            '[{"kind":"fact","severity":"error",'
            '"message":"النصّ محرَّف",'
            '"quote":"هذا النصّ لا وجود له في المسودّة إطلاقاً",'
            '"basis":""}]'
        )
        outcome = parse_review(raw, self.DRAFT, "موجز", "")
        self.assertEqual(outcome.findings, [])
        self.assertEqual(outcome.dropped, 1)
        self.assertTrue(outcome.clean)

    def test_an_empty_answer_is_clean_and_expected(self):
        """
        🔑 **وهذا الجواب الذي يُقدّمه مُراجع جيّد في معظم الأحيان** — ولذلك
        يُصرّ الموجّه على أن `[]` جواب صحيح. **ولولا ذلك لاخترع اعتراضات.**
        """
        outcome = parse_review("[]", self.DRAFT, "موجز", "")
        self.assertEqual(outcome.findings, [])
        self.assertTrue(outcome.clean)


if __name__ == "__main__":
    unittest.main()
