"""
اختبارات سِجلّ الوقائع — الواقعة التي غُيِّرت مرّات، وقد صارت مُختبرة.
=============================================================================

تشغيل::

    cd legal-brain
    python -m unittest discover -s tests -t . -v

حتمية بالكامل: بلا شبكة، وبلا نموذج، وبلا قاعدة بيانات، وبلا قرص. وهذا شرط
لا تحسين: `check_fidelity` يجب أن يُشغَّل في كل مرّة، ولو احتاج نداءً لَما
شُغِّل.

وأهمّ اختبار في الملف `test_refusing_a_release_is_not_refusing_payment` —
وهو **العيب التاريخي** الذي جاء هذا الملف لمنعه:

    الموظف **رفض التوقيع على مخالصة متضمّنة تنازلاً**،
    فصارت في المذكرة: **رفض استلام المبلغ**.

⚠️ **وتكرّر العيب في ثلاث مسودّات متعاقبة**، وأصلُه البنيوي أن الوقائع كانت
تمرّ **نثراً غير متمايز**: لا مصدر، ولا درجة إثبات، ولا نصّ تستند إليه. فلا
شيء كان يستطيع أن يكتشف التغيير.

⚠️ **واختبار ثانٍ لا يقلّ عنه:** `test_a_faithful_restatement_is_not_a_contradiction`.
لأن أداة تُنذر دائماً **لا تُنذر أبداً**: لو وُسمت المسودّة الأمينة بأنها
**نقضت** الواقعة، لتعلّم المحامي ألّا يقرأ التقرير — ثم يضيع العيب الحقيقي
حين يظهر. فالأمين يجب ألّا يُقرأ نقضاً، ولو وُسم ``reworded`` (وهو الإنذار
الكاذب المعلن في هذا الفحص).
"""

import ast
import json
import pathlib
import unittest

import facts
from citations import normalize
from facts import (
    CLIENT_STATEMENT_IS_NOT_PROOF,
    FIDELITY_ACCEPT_COVERAGE,
    FIDELITY_REWORD_MAX_RATIO,
    OPPONENT_PLEADING_IS_NOT_EVIDENCE,
    STANDING_LABELS,
    Fact,
    FactLedger,
    FactShift,
    FactVersion,
    Standing,
    SystemOverclaimError,
    VersionConflict,
    assert_system_does_not_agree,
    check_fidelity,
    shifts_summary,
    stale_settlement_figure,
    summarize,
)


# ==============================================================================
# بيانات الاختبار — الواقعة التاريخية **حرفياً**، لا واقعة متخيَّلة
# ==============================================================================

#: الواقعة كما وقعت: رفض التوقيع على مخالصة متضمّنة تنازلاً.
THE_RELEASE_STATEMENT = "رفض الموظف التوقيع على مخالصة متضمّنة تنازلاً"

#: نصّ المخالصة الذي تستند إليه — اقتباس حرفي.
THE_RELEASE_QUOTE = "أرفض التوقيع على هذه المخالصة لاشتمالها على تنازل"

#: ⚠️ **المسودّة المعطوبة:** تنقل واقعة أخرى (استلام المبلغ) على أنها
#: الواقعة الأولى. والفرق ليس لغوياً: الأول يمتنع عن **تنازل**، والثاني يمتنع
#: عن **قبض حقّه** — فأيّهما كانت الواقعة يتغيّر مَن عليه الخطأ.
THE_FLAWED_DRAFT = (
    "وحيث إن الموظف رفض استلام المبلغ المعروض عليه، فإنه لا يستحقّ "
    "المطالبة به.\n"
    "وقد أُرفق محضر الجلسة المؤرّخ ٢٠٢٤-٠٦-١١."
)

#: **والمسودّة الأمينة:** تحمل نصّ الواقعة، ومعها زيادة مشروعة حولها.
THE_FAITHFUL_DRAFT = (
    "وحيث إن الموظف رفض التوقيع على مخالصة متضمّنة تنازلاً، فلا يصحّ "
    "الاحتجاج عليه بأنه قَبِلَ ما عُرض عليه.\n"
    "وقد أُرفق نصّ المخالصة."
)


def _the_release_fact(**changes) -> Fact:
    """الواقعة التاريخية بمفتاحها وموضوعها — والتغيير للتجارب يُمرَّر."""
    base = dict(
        key="release.refused",
        statement=THE_RELEASE_STATEMENT,
        source="مخالصة مؤرّخة ٢٠٢٤-٠٥-١٠",
        locus="الصفحة ٢",
        date="2024-05-10",
        asserted_by="الموكّل",
        standing=Standing.CLAIMED,
        quote=THE_RELEASE_QUOTE,
        subject="release",
    )
    base.update(changes)
    return Fact(**base)


def _the_payment_fact(**changes) -> Fact:
    """
    واقعة **مختلفة الموضوع**: استلام المبلغ.

    ⚠️ وهي واقعة مشروعة في السجلّ، ولا عيب فيها. والعيب أن تُنقل **مكان**
    واقعة الرفض — فالواقعتان موضوعهما مختلف (``payment`` ≠ ``release``).
    """
    base = dict(
        key="payment.refused",
        statement="رفض الموظف استلام المبلغ المعروض عليه",
        source="محضر جلسة ٢٠٢٤-٠٦-١١",
        locus="البند ٣",
        date="2024-06-11",
        asserted_by="الموكّل",
        standing=Standing.CLAIMED,
        quote="",
        subject="payment",
    )
    base.update(changes)
    return Fact(**base)


def _the_ledger() -> FactLedger:
    """🔑 السجلّ الذي يقابل المسودّة المعطوبة: واقعة الرفض وحدها."""
    return FactLedger((_the_release_fact(),))


def _negated(statement: str) -> str:
    """
    يُدخل أداة نفي على نصّ الواقعة — مادة اختبار ``contradicted``.

    ⚠️ **والاشتقاق مقصود لا النصّ المحفوظ:** لو كُتبت المسودّة المنقوضة نصّاً
    ثابتاً، ثم عُدّل نصّ الواقعة، **لبقي الاختبار ناجحاً وهو لا يفحص شيئاً**.
    أما اشتقاقها فيجعل الاختبار يفحص **علاقة النقض** لا نصّاً حرفياً.
    """
    return "لم " + statement if not facts._has_negation(statement) else statement


# ==============================================================================
# ١. الدرجات — كل درجة تُمارَس، ولا درجتان تُطابقان
# ==============================================================================


class TestStanding(unittest.TestCase):
    """
    🔑 **درجة الواقعة — وهي الحقل الذي بحضوره يصير تغيير الوزن قابلاً للكشف.**

    وهذا هو أصل العيب: «متفق عليها» و«ادعاء لم يثبت» كانا يُكتبان في المذكرة
    بالصيغة نفسها، فلا يفرّق القارئ بين ما أثبته الخصم وما يدّعيه موكّلنا.
    """

    def test_every_standing_round_trips_through_its_machine_value(self):
        """
        الجولة الكاملة على القيمة الآلية — والدرجة تُبَثّ وتُعاد.

        فلو لم تُعِد الجولة القيمة نفسها لَما أمكن أن يصل تقرير الدرجة إلى
        الواجهة ويعود، وهو ما يمنع عرض «أيّ وقائع ادعاء» على المحامي.
        """
        for standing in Standing:
            with self.subTest(standing=standing.value):
                self.assertIs(Standing(standing.value), standing)
        self.assertEqual(
            [member.value for member in Standing],
            ["agreed", "claimed", "disputed", "inferred", "uncertain"],
        )

    def test_each_standing_is_distinguishable(self):
        """
        ⚠️ الدرجات **مختلفة بعضها عن بعض** — لا قيمتان بمعنى واحد.

        ولو تساوت درجتان لَما كان للتصنيف معنى، وصار الوسم زينةً في العرض.
        """
        values = {member.value for member in Standing}
        self.assertEqual(len(values), len(list(Standing)))
        self.assertEqual(len({member.name for member in Standing}), len(list(Standing)))

    def test_each_standing_is_exercised_by_a_fact(self):
        """
        🔑 **وكل درجة تُمارَس بواقعة حقيقية** لا تُعرَّف فقط.

        لأن الدرجة التي لا تُستعمل في هذا الملف **لم تُختبر مسارها**: هل
        تُعرض؟ هل تُترجم؟ هل تُصفّى بها ``by_standing``؟ فالمطلوب أن تُبنى
        لكل درجة واقعة، وتُنادى بها الدوالّ.
        """
        all_standings = list(Standing)
        ledger = FactLedger(
            tuple(
                Fact(
                    key=f"fact.{standing.value}",
                    statement=f"واقعة بدرجة {standing.value}",
                    source="مستند",
                    locus="الصفحة ١",
                    date="",
                    asserted_by="الموكّل",
                    standing=standing,
                    quote="نصّ",
                    subject=standing.value,
                )
                for standing in all_standings
            )
        )
        for standing in all_standings:
            with self.subTest(standing=standing.value):
                found = ledger.by_standing(standing)
                self.assertEqual(len(found), 1)
                self.assertEqual(found[0].standing, standing)
                self.assertEqual(found[0].standing_label, STANDING_LABELS[standing.value])
                self.assertTrue(found[0].standing_label.strip())

    def test_each_standing_has_an_arabic_label(self):
        """
        ⚠️ ولكل درجة **اسم عربي** يُعرض على المحامي.

        ودرجة بلا اسم عربي تُعرَض بمفتاحها اللاتيني (``uncertain``)، وهو ما
        لا يُقرأ في تقرير عربي — فيصير الوسم صامتاً عملياً.
        """
        self.assertEqual(set(STANDING_LABELS), {m.value for m in Standing})
        for standing, label in STANDING_LABELS.items():
            with self.subTest(standing=standing):
                self.assertTrue(label.strip())
                self.assertNotEqual(label, standing)

    def test_the_labels_do_not_call_a_claim_established(self):
        """
        ⚠️ **وسم ``CLAIMED`` لا يقول «ثابت» ولا «متفق عليه».**

        وهذا ليس تحسين صياغة: الوسم هو ما يقرأه المحامي في التقرير، فلو قال
        «ثابت» لَعاد العيب من باب الوزن لا من باب النصّ.
        """
        label = STANDING_LABELS[Standing.CLAIMED.value]
        self.assertIn("ادعاء", label)
        self.assertIn("لم يثبت", label)
        self.assertNotIn("ثابت", label.replace("لم يثبت", ""))


# ==============================================================================
# ٢. السجلّ — القراءة والصفّ
# ==============================================================================


class TestLedgerReading(unittest.TestCase):
    """
    السجلّ يُقرأ بالمفتاح والدرجة، **والمجهول يُعاد ``None`` لا يُخترع**.

    على قاعدة ``rule_for`` في `labour_rules.py`: ``None`` جوابٌ مقصود
    («لا واقعة بهذا المفتاح»)، ولو أُعيدت واقعة فارغة لأمكن أن يُبنى عليها
    كما يُبنى على المسجَّلة.
    """

    def test_of_key_returns_the_fact_or_none(self):
        """الواقعة بمفتاحها، والمفتاح المجهول ``None`` — لا واقعة مخترعة."""
        ledger = _the_ledger()
        found = ledger.of_key("release.refused")
        self.assertIsNotNone(found)
        self.assertEqual(found.statement, THE_RELEASE_STATEMENT)
        self.assertEqual(found.quote, THE_RELEASE_QUOTE)
        self.assertEqual(found.source, "مخالصة مؤرّخة ٢٠٢٤-٠٥-١٠")
        self.assertIsNone(ledger.of_key("لا.يوجد"))
        self.assertIsNone(ledger.of_key(""))

    def test_by_standing_filters_and_accepts_a_machine_string(self):
        """
        الصفّ بالدرجة، ويُقبل النصّ الآلي — لأن الواجهة تُرسل ``"claimed"``.

        والقيمة الغريبة لا تُطابق شيئاً فتُعيد فراغاً، **ولا تُخمَّن لها درجة**
        — وهو الفرق بين تصفية وتخمين.
        """
        ledger = FactLedger((_the_release_fact(), _the_payment_fact()))
        self.assertEqual(len(ledger.by_standing(Standing.CLAIMED)), 2)
        self.assertEqual(len(ledger.by_standing("claimed")), 2)
        self.assertEqual(ledger.by_standing("agreed"), ())
        self.assertEqual(ledger.by_standing("لا_توجد_درجة"), ())

    def test_unquoted_returns_the_facts_without_a_quote(self):
        """
        ⚠️ **واقعة بلا نصّ لا تصلح أساساً لاقتباس.**

        وفحص `citations.py` يقوم على اقتباس حرفي، فالمطالبة باقتباس واقعة لا
        نصّ لها تُنتج اقتباساً **مؤلَّفاً** — وهو أخطر من غياب الواقعة. فيُقال
        للمحامي ذلك قبل أن يُطلب منه ما لا يوجد.
        """
        ledger = FactLedger((_the_release_fact(), _the_payment_fact()))
        self.assertEqual([fact.key for fact in ledger.unquoted()], ["payment.refused"])
        self.assertTrue(_the_release_fact().is_quoted)
        self.assertFalse(_the_payment_fact().is_quoted)

    def test_the_ledger_rejects_a_duplicate_key(self):
        """
        ⚠️ **المفتاح المكرّر يُرفض.** ولو قُبل لَما عُرف أيّ الواقعتين تُنادَى
        بـ``of_key`` — فيصير السجلّ يفترق عن نفسه، وهو أسوأ من التوقّف.
        """
        duplicate = _the_release_fact(
            source="مستند آخر", statement="واقعة أخرى بنفس المفتاح"
        )
        with self.assertRaises(ValueError):
            FactLedger((_the_release_fact(), duplicate))

    def test_the_ledger_rejects_a_fact_without_a_key_or_a_statement(self):
        """وواقعة بلا مفتاح أو بلا نصّ **لا تُعرَف ولا تُطالَب** — فتُرفض."""
        with self.assertRaises(ValueError):
            FactLedger((_the_release_fact(key="  "),))
        with self.assertRaises(ValueError):
            FactLedger((_the_release_fact(statement="   "),))

    def test_the_ledger_keeps_the_input_order(self):
        """
        ⚠️ والسجلّ **لا يُرتّب وقائعه**: موضع الواقعة يتبع ترتيب قراءة
        المستندات، والدوالّ التي تُرتّب تُرتّب نتيجتها وحدها.
        """
        ledger = FactLedger((_the_payment_fact(), _the_release_fact()))
        self.assertEqual(ledger.keys(), ("payment.refused", "release.refused"))
        self.assertEqual(
            [fact.key for fact in ledger.facts], ["payment.refused", "release.refused"]
        )

    def test_the_fact_is_frozen(self):
        """الواقعة لا تُعدَّل بعد تسجيلها — فلا يتبدّل دليل أثناء تشغيل."""
        fact = _the_release_fact()
        with self.assertRaises(Exception):
            fact.statement = "نصّ آخر"  # type: ignore[misc]
        self.assertIsInstance(fact, Fact)


# ==============================================================================
# ٣. التناقض — يُكتشف ولا يُختلق
# ==============================================================================


class TestConflicts(unittest.TestCase):
    """
    🔑 **التناقض يُكتشف من موضوعه، ولا يُختلق من تشابه لفظي.**

    والفرق هو الفرق بين تقرير يُقرأ وتقرير يُتجاهل: لو نُسب تناقض إلى
    وقائعتين لا علاقة بينهما («تأخّر عن السداد» و«تأخّر عن التوقيع»)، لَغرق
    التناقض الحقيقي في جدار من الأزواج التي لا معنى لها — وهو ما وقع فعلاً
    في `language_audit.py`.
    """

    def test_finds_a_genuine_contradiction(self):
        """
        🔑 **تناقض حقيقي، موضوعه واحد والنصّان متقاربان.**

        «وقّع الموظف على المخالصة» و«لم يوقّع الموظف على المخالصة» — نقيضان
        على الأمر نفسه، والفرق بينهما **أداة نفي واحدة**. وهذا هو التناقض
        الذي يهمّ المحامي: أُثبت الفعل أم نُفي؟
        """
        ledger = FactLedger(
            (
                _the_release_fact(
                    key="release.signed",
                    statement="وقّع الموظف على المخالصة متضمّنة تنازلاً",
                    quote="وقّع المستلم على هذه المخالصة",
                    asserted_by="الخصم",
                ),
                _the_release_fact(
                    statement="لم يوقّع الموظف على المخالصة متضمّنة تنازلاً",
                    quote="امتنع عن التوقيع",
                ),
            )
        )
        pairs = ledger.conflicts()
        self.assertEqual(len(pairs), 1)
        first, second = pairs[0]
        self.assertEqual({first.key, second.key}, {"release.signed", "release.refused"})
        self.assertEqual(first.effective_subject, second.effective_subject)

    def test_does_not_invent_a_conflict_from_unrelated_facts(self):
        """
        🔑 **القياس السالب:** واقعتان متقاربتان لفظاً ولا تناقض بينهما.

        «تأخّر المستأجر عن سداد الأجرة» و«تأخّر الموظف عن التوقيع على الإخطار»
        تشتركان في «تأخّر» و«عن»، ولا تتناقضان بحال. ولو قرن السجلّ بالتشابه
        النصّي لظهرتا زوجاً متناقضاً — وهو تناقض مخترع.
        """
        ledger = FactLedger(
            (
                Fact(
                    key="payment.delayed",
                    statement="تأخّر المستأجر عن سداد الأجرة ثلاثة أشهر",
                    source="كشف الحساب",
                    locus="الصفحة ١",
                    date="2024-03-01",
                    asserted_by="الموكّل",
                    standing=Standing.CLAIMED,
                    quote="متأخّرات ثلاثة أشهر",
                    subject="payment",
                ),
                Fact(
                    key="notice.delayed",
                    statement="تأخّر الموظف عن التوقيع على الإخطار",
                    source="الإخطار",
                    locus="الصفحة ١",
                    date="2024-05-01",
                    asserted_by="الخصم",
                    standing=Standing.CLAIMED,
                    quote="تأخّر في التوقيع",
                    subject="notice",
                ),
            )
        )
        self.assertEqual(ledger.conflicts(), ())

    def test_does_not_pair_facts_of_different_standing(self):
        """
        ⚠️ **واختلاف الدرجة ليس تناقضاً بل اختلاف مصدر.**

        «ادعاء لم يثبت» في مقابل «استنتاج المنظومة» بابان مختلفان، وجمعهما
        في زوج متناقض يُقحم على المحامي سؤالاً لا معنى له. والتناقض يقتضي أن
        يكون الطرفان على **الأمر نفسه** بمصدرين مختلفين.
        """
        ledger = FactLedger(
            (
                _the_release_fact(standing=Standing.INFERRED, quote=""),
                _the_release_fact(
                    key="release.signed",
                    statement="لم يوقّع الموظف على المخالصة متضمّنة تنازلاً",
                ),
            )
        )
        self.assertEqual(ledger.conflicts(), ())

    def test_a_bare_substitution_is_read_as_a_conflict(self):
        """
        ⚠️ **والاستبدال المادّي بلا نفي تناقضٌ أيضاً.**

        «لم يستلم الموظف سوى نصف مستحقاته» في مقابل «لم يستلم الموظف
        مستحقاته»: لا نفيَ مقابل إثبات، بل **حدٌّ مختلف في الموضع نفسه** —
        ونصف المستحقات ليس كلّها. فالتغطية المتبادلة عالية والنسبة منخفضة.
        """
        ledger = FactLedger(
            (
                Fact(
                    key="dues.all",
                    statement="لم يستلم الموظف مستحقاته كاملة",
                    source="إفادة الخصم",
                    locus="الصفحة ١",
                    date="",
                    asserted_by="الخصم",
                    standing=Standing.DISPUTED,
                    quote="لم يستلم مستحقاته",
                    subject="dues",
                ),
                Fact(
                    key="dues.half",
                    statement="لم يستلم الموظف سوى نصف مستحقاته كاملة",
                    source="إفادة الموكّل",
                    locus="الصفحة ٢",
                    date="",
                    asserted_by="الموكّل",
                    standing=Standing.DISPUTED,
                    quote="استلم نصفها",
                    subject="dues",
                ),
            )
        )
        pairs = ledger.conflicts()
        self.assertEqual(len(pairs), 1)
        self.assertEqual({pairs[0][0].key, pairs[0][1].key}, {"dues.all", "dues.half"})

    def test_the_same_subject_without_contradiction_is_not_a_conflict(self):
        """
        ⚠️ **الموضوع الواحد لا يكفي:** وقائعتان about المخالصة لا تتناقضان إن
        لم تتناولا التفصيل نفسه.

        «وُقّعت المخالصة في ١٠ مايو» و«للمخالصة ثلاث نسخ» — موضوعهما واحد
        ولا تناقض. ولو اكتُفي بالموضوع لَظهر زوج لا معنى له، وهو إقحام.
        """
        ledger = FactLedger(
            (
                Fact(
                    key="release.dated",
                    statement="حملت المخالصة تاريخ ١٠ مايو",
                    source="المخالصة",
                    locus="الصفحة ١",
                    date="2024-05-10",
                    asserted_by="الموكّل",
                    standing=Standing.CLAIMED,
                    quote="التاريخ ١٠ مايو",
                    subject="release",
                ),
                Fact(
                    key="release.copies",
                    statement="للمخالصة ثلاث نسخ محفوظة",
                    source="سجلّ الشركة",
                    locus="الصفحة ٤",
                    date="",
                    asserted_by="الخصم",
                    standing=Standing.CLAIMED,
                    quote="ثلاث نسخ",
                    subject="release",
                ),
            )
        )
        self.assertEqual(ledger.conflicts(), ())


# ==============================================================================
# ٤. النسخ المتعدّدة — أيّها المعمول به؟
# ==============================================================================


class TestVersionConflicts(unittest.TestCase):
    """
    ⚠️ **تعدّد النسخ وحده لا يفيد المحامي بشيء.**

    «للمخالصة ثلاث نسخ» جملة تُقرأ ويُمضى. أما «النسخة الموقّعة المؤرّخة كذا
    هي المعمول بها، ويُحتاج تحديد توقيع الأخرى» فسؤالٌ يُجاب. فالحصيلة يجب
    أن تُسمّي **المقترحة للعمل** أو تقول صريحاً ما ينقص تحديده.
    """

    def _versions(self) -> tuple[FactVersion, ...]:
        return (
            FactVersion(
                document="مخالصة",
                version="1",
                date="2024-05-01",
                signed=False,
                note="أُرسلت ولم تُوقَّع",
            ),
            FactVersion(
                document="مخالصة",
                version="2",
                date="2024-05-10",
                signed=True,
                note="تحمل توقيع الموظف",
            ),
        )

    def test_it_names_the_proposed_operative_version_and_its_date(self):
        """
        🔑 **النسخة المقترحة وتاريخها وتوقيعها** في سطر واحد.

        والترجيح على **ما في السجلّ** (الموقّعة ثم الأحدث) لا على حكم قانوني،
        والحدّ معلن في ``limit`` الموضع: المحامي هو من يعتمد النسخة.
        """
        conflicts = FactLedger(versions=self._versions()).version_conflicts()
        self.assertEqual(len(conflicts), 1)
        conflict = conflicts[0]
        self.assertIsInstance(conflict, VersionConflict)
        self.assertEqual(conflict.document, "مخالصة")
        self.assertEqual(len(conflict.versions), 2)
        self.assertIn("2", conflict.note)          # النسخة المقترحة
        self.assertIn("2024-05-10", conflict.note)  # وتاريخها
        self.assertIn("موقّعة", conflict.note)      # وحال توقيعها

    def test_a_single_version_is_not_reported(self):
        """⚠️ والتعدّد وحده يُذكر — ومستند بنسخة واحدة لا يُدخل التقرير."""
        ledger = FactLedger(
            versions=(FactVersion(document="عقد", version="1", date="2024-01-01"),)
        )
        self.assertEqual(ledger.version_conflicts(), ())

    def test_an_unknown_signature_is_stated_not_assumed(self):
        """
        ⚠️ **«لم يُفحص» ليست «غير موقّعة».**

        والخلط بينهما يجعل تقرير المحامي صحيحاً في الملف خاطئاً في الواقع:
        نسخةٌ لم تُفحص تُعرض غير موقّعة، فيُبنى على ذلك ما لا يُبنى. فالنصّ
        يقول **ما ينقص تحديده** صريحاً.
        """
        ledger = FactLedger(
            versions=(
                FactVersion(document="مخالصة", version="1", date="2024-05-01"),
                FactVersion(document="مخالصة", version="2", date="2024-05-10"),
            )
        )
        conflict = ledger.version_conflicts()[0]
        self.assertIn("لم يُفحص", conflict.note)
        self.assertIn("تحديد", conflict.note)

    def test_an_implied_missing_version_is_flagged(self):
        """
        ⚠️ **وإذا استُنتج وجود نسخة غير مسجَّلة قيل ذلك.**

        فالمسافات بين النسخ قد تدلّ على نسخة مفقودة، والمحامي يحتاج أن يعرف
        أن السجلّ قد يكون ناقصاً قبل أن يبني على «النسخة الأخيرة».
        """
        ledger = FactLedger(
            versions=(
                FactVersion(document="مخالصة", version="1", date="2024-05-01"),
                FactVersion(
                    document="مخالصة", version="3", date="2024-05-20", implied=True
                ),
            )
        )
        conflict = ledger.version_conflicts()[0]
        self.assertIn("غير مسجَّلة", conflict.note)


# ==============================================================================
# ٥. ما يجب أن يُراجَع — والترتيب هو الفائدة
# ==============================================================================


class TestNeedsVerification(unittest.TestCase):
    """
    🔑 **الأسماء والأرقام والتواريخ والتوقيعات أولاً.**

    ⚠️ **ولماذا هذا الترتيب بالتحديد؟** لأن القراءة الآلية (OCR) تُخطئ فيها
    **خطأً قريباً من الصواب**: «٤٩» و«٤٩٠»، و«٢٠٢٤» و«٢٠٢١»، والتوقيع لا
    يُقرأ أصلاً بل يُخمَّن وجوده. وهذا هو الفرق بين خطأ يُكشف وخطأ يمرّ:
    الخطأ في **معنى الجملة** يُقرأ فيُستغرب، والخطأ في **رقم** يُقرأ فيُقبل —
    لأن الرقم لا يبدو خطأً في ذاته.
    """

    def _uncertain(self) -> tuple[Fact, ...]:
        """
        وقائع غير محقَّقة **بترتيب إدخال مضادّ لترتيب العرض**.

        ⚠️ وهذا مقصود: التوقيع آخراً في الإدخال وأولاً في العرض، فلو مرّ
        الترتيب كما هو لنجح اختبار الترتيب **بالمصادفة** — والاختبار الذي
        ينجح لاتّفاق المصادفة لا يحرس شيئاً.
        """
        return (
            Fact(
                key="note.text",
                statement="أُرسلت المخالصة بخطاب إلى الموظف",
                source="خطاب الإرسال",
                locus="الصفحة ١",
                date="",
                asserted_by="الموكّل",
                standing=Standing.UNCERTAIN,
                quote="نصّ الخطاب",
                subject="note",
            ),
            Fact(
                key="salary.amount",
                statement="بلغ الأجر الشهري ٨٠٠٠ درهم",
                source="كشف الراتب",
                locus="الصفحة ١",
                date="",
                asserted_by="الموكّل",
                standing=Standing.UNCERTAIN,
                quote="الأجر الشامل",
                subject="salary",
            ),
            Fact(
                key="signature.status",
                statement="المخالصة موقّعة من الموظف",
                source="صورة ممسوحة",
                locus="الصفحة ٢",
                date="",
                asserted_by="النظام",
                standing=Standing.UNCERTAIN,
                quote="",
                subject="signature",
            ),
            Fact(
                key="plain.reading",
                statement="يُرجّح أن الورقة تحمل إقراراً",
                source="الصورة",
                locus="الصفحة ٣",
                date="",
                asserted_by="النظام",
                standing=Standing.UNCERTAIN,
                quote="",
                subject="plain",
            ),
        )

    def test_needs_verification_orders_names_numbers_dates_signatures_first(self):
        """
        🔑 **الترتيب هو الغرض من الدالّة لا زينة فيها.**

        ⚠️ **والمفحوص علاقاتُ ترتيب لا مواضع مطلقة**، لأن المواضع المطلقة
        تتبدّل بتبدّل بيانات السجلّ، فتُصبح الاختبار هشّاً لا كاشفاً. والذي
        يعنيه المحامي: **أيّ وقائع يقرأ أولاً**.

        والترتيب في هذه البيانات — مقيساً على القاعدة:
          * ``signature.status`` — توقيع، وهو الرتبة الأولى (وكلمتها فيها
            «م» بادئةُ اسم أيضاً، فلا يهمّ: التوقيع أسبق).
          * ``note.text`` — تاريخ في حقله (تاريخ أول مايو).
          * ``salary.amount`` — رقم في متنه (٨٠٠٠).
          * ``plain.reading`` — لا إشارة فيه أصلاً، فيقع آخراً.
        فالمفحوص أن **التوقيع قبل غيره**، وأن **الرقم قبل ما لا إشارة فيه**.
        """
        ordered = [fact.key for fact in FactLedger(self._uncertain()).needs_verification()]
        self.assertEqual(ordered[0], "signature.status")
        self.assertLess(
            ordered.index("note.text"),
            ordered.index("plain.reading"),
            "تاريخٌ غير محقَّق يجب أن يُراجَع قبل قراءة لا إشارة فيها",
        )
        self.assertLess(
            ordered.index("salary.amount"),
            ordered.index("plain.reading"),
            "رقمٌ غير محقَّق يجب أن يُراجَع قبل قراءة لا إشارة فيها",
        )
        self.assertEqual(ordered[-1], "plain.reading")

    def test_only_uncertain_and_disputed_facts_are_listed(self):
        """
        ⚠️ **والوقائع الثابتة لا تُطالب بتحقّق.**

        ولو أُدرجت لصار التقرير جداراً من الطلبات، فيُتجاهَل — ومع تجاهله
        يضيع الرقم غير المحقَّق الذي كان يجب أن يُراجَع.
        """
        ledger = FactLedger(
            (
                _the_release_fact(standing=Standing.AGREED),
                _the_release_fact(
                    key="release.disputed",
                    standing=Standing.DISPUTED,
                    statement="وقّع الموظف على المخالصة متضمّنة تنازلاً",
                ),
                _the_payment_fact(standing=Standing.INFERRED),
            )
        )
        keys = [fact.key for fact in ledger.needs_verification()]
        self.assertIn("release.disputed", keys)
        self.assertNotIn("release.refused", keys)
        self.assertNotIn("payment.refused", keys)

    def test_a_number_is_ranked_before_a_plain_reading_without_any_signal(self):
        """
        ⚠️ **والرقم المجرّد أخطر ما تُخطئ فيه القراءة الآلية ويبدو سليماً.**

        ⚠️ **وزرعٌ مقصود في التصميم:** بيانات هاتين الواقعتين **بلا رقم في
        الموضع أو المصدر** — فلا «الصفحة ٣» ولا تاريخ ولا مفتاح فيه رقم.
        والسبب أن أي رقم في أي حقل يجعل الواقعتين في الرتبة نفسها، فيقيس
        الاختبار **ترتيب الإدخال** لا أثر الرقم. وهذا عيب وقع فعلاً أثناء
        كتابة هذا الملف: كان الموضع «الصفحة ٣» فتقدّمت الواقعة التي لا رقم
        لها، والاختبار كان ينجح لسبب لا علاقة له بالرقم.
        """
        plain = Fact(
            key="plain.reading",
            statement="يُرجّح أن الورقة تحمل إقراراً",
            source="الصورة الممسوحة",
            locus="الموضع الأول",
            date="",
            asserted_by="النظام",
            standing=Standing.UNCERTAIN,
            quote="",
            subject="plain",
        )
        amount = Fact(
            key="amount.reading",
            statement="بلغ المبلغ المقروء ١٢٥٠٠ درهم",
            source="الصورة الممسوحة",
            locus="الموضع الثاني",
            date="",
            asserted_by="النظام",
            standing=Standing.UNCERTAIN,
            quote="",
            subject="amount",
        )
        # ⚠️ وفحص الزرع أولاً: لو صار في أحد الحقلين رقم لعاد العيب صامتاً.
        self.assertFalse(facts._has_number(f"{plain.source} {plain.locus} {plain.date}"))
        self.assertTrue(facts._has_number(amount.statement))

        ordered = [fact.key for fact in FactLedger((plain, amount)).needs_verification()]
        self.assertEqual(ordered, ["amount.reading", "plain.reading"])

    def test_the_order_is_deterministic(self):
        """
        ⚠️ **والترتيب ثابت بين نداءين** — فالفرز مستقرّ والرتبة معلنة.

        وترتيبٌ يتغيّر بين تشغيلين يجعل المحامي يشكّ في التقرير كلّه، لا في
        الترتيب وحده.
        """
        ledger = FactLedger(self._uncertain())
        first = [fact.key for fact in ledger.needs_verification()]
        for _ in range(5):
            self.assertEqual([fact.key for fact in ledger.needs_verification()], first)


# ==============================================================================
# ٦. القاعدتان — رواية الموكّل وادعاء الخصم
# ==============================================================================


class TestClientAndOpponentRules(unittest.TestCase):
    """
    🔑 **القاعدتان اللتان تمنعان العيب من أصله.**

    رواية الموكّل **صحيحة في نظره**، وادعاء الخصم **صحيح في نظره**، ولا
    واحدٌ منهما دليل. ولو مرّت إحداهما `AGREED` لصارت في المذكرة حقيقةً
    مسلَّمة — وهي صورة أخرى من العيب: أن يُغيَّر **وزن** الواقعة لا نصّها.
    """

    def test_a_client_statement_never_becomes_agreed(self):
        """
        🔑 **رواية الموكّل تُسجَّل ``CLAIMED`` ولا تصير ``AGREED`` أبداً.**

        وهذا يقع عملياً: الموكّل يقول «اتفقنا على كذا»، فيُكتب «اتفق الطرفان
        على كذا» — والاتّفاق لم يثبت. والمحامي يقرأها في ملفّه فيصدّقها،
        والخصم ينكرها، فيسقط الطلب.
        """
        client_statement = _the_release_fact(
            key="client.claim",
            statement="اتفق الطرفان على مبلغ التسوية",
            source="رواية الموكّل",
            asserted_by="الموكّل",
            standing=Standing.CLAIMED,
            quote="",
            subject="settlement",
        )
        ledger = FactLedger((client_statement,))
        # الدرجة كما سُجّلت — ولا ترقية صامتة في السجلّ.
        self.assertEqual(ledger.of_key("client.claim").standing, Standing.CLAIMED)
        self.assertEqual(ledger.by_standing(Standing.AGREED), ())
        # ⚠️ **والحارس لا يرفع على رواية الموكّل** — لأنها سُجّلت `CLAIMED`
        # لا `AGREED`. وهذه هي القاعدة عاملة: الرواية تمرّ موسومة، فلا تُبنى
        # عليها مطالبة كأنها ثابتة. ولو رفع الحارس عليها لصار عائقاً في
        # المسار، ومع تعطيله تعود الترقية الصامتة.
        assert_system_does_not_agree((client_statement,))
        # ⚠️ ويرفع على **الحالة المستحيلة وحدها**: واقعة بدرجة `AGREED`
        # أنشأها مسار آلي. وهذا هو الموضع الذي يجب أن يوقف الصياغة.
        with self.assertRaises(SystemOverclaimError):
            assert_system_does_not_agree(
                (_the_release_fact(standing=Standing.AGREED),)
            )
        # والقاعدة نصّها في الوحدة، لا في وثيقة خارجية.
        self.assertIn("ليست دليلاً", CLIENT_STATEMENT_IS_NOT_PROOF)
        self.assertIn("CLAIMED", CLIENT_STATEMENT_IS_NOT_PROOF)

    def test_the_guard_accepts_every_standing_the_system_may_record(self):
        """
        ⚠️ **والحارس لا يرفع على ما يجوز للمنظومة أن تُنشئه.**

        ولو رفع على ``INFERRED`` — وهي استنتاج المنظومة نفسه — لصار الحارس
        عائقاً يُعطَّل، ومع تعطيله يعود الترقية الصامتة.
        """
        for standing in facts.SYSTEM_RECORDED_STANDINGS:
            with self.subTest(standing=standing.value):
                assert_system_does_not_agree((_the_release_fact(standing=standing),))
        self.assertNotIn(Standing.AGREED, facts.SYSTEM_RECORDED_STANDINGS)

    def test_an_opponent_pleading_is_never_evidence(self):
        """
        🔑 **وادعاء الخصم في صحيفة دعواه ليس دليلاً على ما يدّعيه.**

        وهذا مقلوب القاعدة الأولى: فيها ما يقوله الخصم لا ما ثبت. ولو أُعيد
        في مسودّتنا بلا وسم، صار **ادعاء الخصم حجّة على موكّلنا** — وهو
        أسوأ من غياب الواقعة، لأن الغائبة تُطلب وهذه تُقرأ ثابتة.
        """
        pleading = _the_release_fact(
            key="opponent.pleading",
            statement="يقرّ الموظف بأنه استلم كامل مستحقاته",
            source="صحيفة دعوى الخصم",
            asserted_by="الخصم",
            standing=Standing.CLAIMED,
            quote="استلمت كامل مستحقاتي",
            subject="dues",
        )
        ledger = FactLedger((pleading,))
        self.assertEqual(ledger.of_key("opponent.pleading").standing, Standing.CLAIMED)
        self.assertNotEqual(ledger.of_key("opponent.pleading").standing, Standing.AGREED)
        self.assertEqual(ledger.by_standing(Standing.AGREED), ())
        self.assertIn("ليس دليلاً", OPPONENT_PLEADING_IS_NOT_EVIDENCE)
        self.assertIn("CLAIMED", OPPONENT_PLEADING_IS_NOT_EVIDENCE)

    def test_both_rules_are_printed_in_the_summary(self):
        """
        ⚠️ **والقاعدة تُعرَض مع التقرير، لا في تعليق في الكود.**

        لأن القاعدة التي تعيش في تعليق **لا تُقرأ مع التقرير**، والذي يقرأ
        التقرير هو من يحتاجها.
        """
        payload = summarize(_the_ledger())
        self.assertEqual(
            payload["rules"],
            {
                "client_statement_is_not_proof": CLIENT_STATEMENT_IS_NOT_PROOF,
                "opponent_pleading_is_not_evidence": OPPONENT_PLEADING_IS_NOT_EVIDENCE,
            },
        )

    def test_the_rules_are_written_in_the_module_not_in_a_side_document(self):
        """
        ⚠️ نصّ القاعدتين **في الوحدة** — كما في ``RULES`` في `labour_rules.py`.

        والتصحيح الذي يعيش في محادثة أو في وثيقة خارجية **لا يصل إلى
        المسار**، وهو الدرس الذي كُتب في صدر `labour_rules.py`: العيب أُبلغ
        به النموذج في محادثة، فعاد في التشغيل التالي.
        """
        source = pathlib.Path(facts.__file__).read_text(encoding="utf-8")
        self.assertIn("CLIENT_STATEMENT_IS_NOT_PROOF", source)
        self.assertIn("OPPONENT_PLEADING_IS_NOT_EVIDENCE", source)
        self.assertIn("ليست دليلاً", source)


# ==============================================================================
# ٧. 🔑 فحص الأمانة — العيب التاريخي
# ==============================================================================


class TestTheHistoricalDefect(unittest.TestCase):
    """
    🔑 **العيب الذي جاء هذا الملف لمنعه، مُختبراً إلى الأبد.**

    الموظف **رفض التوقيع على مخالصة متضمّنة تنازلاً**، فصارت في المذكرة
    **رفض استلام المبلغ**. والفرق ليس لغوياً: الأول يمتنع عن **تنازل**،
    والثاني يمتنع عن **قبض حقّه** — فأيّهما كانت الواقعة يتغيّر **مَن عليه
    الخطأ**. وقد تكرّر في ثلاث مسودّات متعاقبة.
    """

    def test_refusing_a_release_is_not_refusing_payment(self):
        """
        🔑 **الاختبار التاريخي: المسودّة المعطوبة تُكشَف.**

        المفحوص:
          * أن **افتراقاً واحداً** على الأقل يُوسم لواقعة الرفض؛
          * وأن وسمه **ليس ``contradicted``** — فالمسودّة لم تنقض الواقعة
            بأداة نفي، بل **استبدلت فعلها ومفعوله** (التوقيع ← الاستلام،
            المخالصة ← المبلغ)؛
          * وأن نصّ المسودّة المنحرف **يُعرَض** مع نصّ الواقعة، فالمحامي
            يرى الطرفين لا الشكوى وحدها.

        ⚠️ **ولماذا يفحص الوسم لا مجرّد الوجود؟** لأن الوسم هو ما يقرأه
        المحامي: ``contradicted`` تقول «نُقضت» و``reworded`` تقول «حضرت
        محرّفة» — وهما سؤالان مختلفان يُطرحان على من يقرأ.
        """
        shifts = check_fidelity(THE_FLAWED_DRAFT, _the_ledger())

        self.assertTrue(shifts, "المسودّة بدّلت الواقعة ولم يُوسم افتراق")
        release_shifts = [shift for shift in shifts if shift.fact_key == "release.refused"]
        self.assertEqual(
            len(release_shifts),
            1,
            "افتراق الواقعة يجب أن يُوسم مرة واحدة لا مرة لكل جملة",
        )

        shift = release_shifts[0]
        self.assertIsInstance(shift, FactShift)
        self.assertEqual(shift.kind, "reworded")
        self.assertNotEqual(shift.kind, "contradicted")

        # ونصّ الطرفين معروض: الواقعة من السجلّ، والنصّ المقابل من المسودّة.
        self.assertEqual(shift.fact_statement, THE_RELEASE_STATEMENT)
        self.assertIn("استلام", shift.draft_text)
        self.assertNotIn("تنازلا", normalize(shift.draft_text))
        self.assertTrue(shift.note.strip())

        # ⚠️ ولفظ الواقعة **غائب** من المسودّة، ولفظ الواقعة الأخرى حاضر.
        normalized_draft = normalize(THE_FLAWED_DRAFT)
        self.assertNotIn("تنازلا", normalized_draft)
        self.assertIn("استلام", normalized_draft)

    def test_the_defect_is_caught_even_without_the_note_wording(self):
        """
        ⚠️ **الكشف لا يعتمد على حفظ الصياغة.**

        فلو أُعيدت صياغة الواقعة في السجلّ («امتنع الموظف عن التوقيع على
        إقرار فيه تنازل»)، **لبقي الافتراق موسوماً** — لأن الفحص يقارن
        الرموز لا نصّاً محفوظاً. وهذا هو الفرق بين فحص وبين مطابقة نصّية
        تصلح ليوم واحد.
        """
        ledger = FactLedger(
            (
                _the_release_fact(
                    statement="امتنع الموظف عن التوقيع على إقرار فيه تنازل",
                    quote="امتنعت عن التوقيع",
                ),
            )
        )
        shifts = check_fidelity(THE_FLAWED_DRAFT, ledger)
        self.assertTrue(shifts, "تغيير الصياغة أسقط الكشف")
        self.assertEqual(shifts[0].fact_key, "release.refused")

    def test_a_contradicted_restatement_is_marked_contradicted(self):
        """
        🔑 **والحالة الأصرح: المسودّة تنفي ما أثبتته الواقعة.**

        «رضي الموظف بالمخالصة» تصير «**لم** يرضَ الموظف بالمخالصة» — أو
        «وقّع» تصير «**لم** يوقّع». والوسم هنا ``contradicted`` لا
        ``reworded``، لأن الفرق **أداة نفي** لا صياغة.
        """
        ledger = FactLedger(
            (_the_release_fact(statement="رضي الموظف بالمخالصة متضمّنة تنازلاً"),)
        )
        draft = "وحيث إن " + _negated("رضي الموظف بالمخالصة متضمّنة تنازلاً") + "، فلا يصحّ.\n"
        shifts = check_fidelity(draft, ledger)
        self.assertEqual(len(shifts), 1)
        self.assertEqual(shifts[0].kind, "contradicted")
        self.assertIn("النفي", shifts[0].note)

    def test_a_faithful_restatement_is_not_a_contradiction(self):
        """
        🔑 **والمسودّة الأمينة لا تُقرأ نقضاً — وهذا شرط بقاء الأداة مفيدة.**

        ⚠️ **والحدّ معلن:** قد يُوسم الأمين ``reworded`` إن زاد كلامُه حول
        الواقعة (فالزيادة تُبعد نسبة التشابه). وهذا **الإنذار الكاذب المقصود**
        في هذا الفحص، ومكتوب في ``FIDELITY_REWORD_MAX_RATIO``. أما ما لا
        يجوز — وما يُفقد الأداة قيمتها — فهو أن يُوسم **``contradicted``**:
        أداة تقول «نُقضت» على نصّ أمين تُعلّم المحامي ألّا يقرأها، ثم يضيع
        النقض الحقيقي حين يقع.
        """
        shifts = check_fidelity(THE_FAITHFUL_DRAFT, _the_ledger())
        kinds = {shift.kind for shift in shifts}
        self.assertNotIn(
            "contradicted",
            kinds,
            "مسودّة تحمل نصّ الواقعة حرفياً وُسمت نقضاً — الأداة تُنذر على السليم",
        )
        self.assertNotIn("missing", kinds, "نصّ الواقعة حاضر ولم يُقرأ")

    def test_a_missing_fact_is_flagged_when_the_draft_omits_it(self):
        """
        ⚠️ **والواقعة الغائبة تُكشف بالوسم ``missing``.**

        وهي أخطر الحالات: الغياب **لا يُقرأ**، فلا يرى المحامي في المسودّة
        ما يشير إلى أن شيئاً سقط منها. فالمفحوص أن الوسم ينقلب إلى
        ``missing`` حين لا يُذكر من الواقعة شيء — لا أن يبقى ``reworded``.
        """
        draft = "وحيث إن المستأجر تأخّر عن سداد الأجرة أربعة أشهر، فيُفسخ العقد.\n"
        shifts = check_fidelity(draft, _the_ledger())
        self.assertEqual(len(shifts), 1)
        self.assertEqual(shifts[0].kind, "missing")
        self.assertEqual(shifts[0].draft_text, "")
        self.assertEqual(shifts[0].fact_statement, THE_RELEASE_STATEMENT)

    def test_each_shift_carries_the_text_it_rests_on(self):
        """
        ⚠️ **الافتراق بلا طرفيه لا يُراجَع.**

        «لم تُذكر الواقعة» وحدها لا تُراجَع، و«هذه الواقعة: … وهذا نصّ
        المسودّة: …» تُراجَع. فالحقول الثلاثة (المفتاح، نصّ المسودّة، نصّ
        الواقعة) شرطٌ في المخرَج لا زينة فيه.
        """
        for draft in (THE_FLAWED_DRAFT, THE_FAITHFUL_DRAFT, "ملف آخر لا علاقة له\n"):
            for shift in check_fidelity(draft, _the_ledger()):
                with self.subTest(kind=shift.kind):
                    self.assertTrue(shift.fact_key)
                    self.assertTrue(shift.fact_statement)
                    self.assertTrue(shift.note)
                    self.assertIn(shift.kind, {"missing", "reworded", "contradicted"})


# ==============================================================================
# ٨. حتمية الفحص — الضمانة الأخيرة
# ==============================================================================


class TestFidelityDeterminism(unittest.TestCase):
    """
    🔑 **المدخل نفسه يُعطي المخرَج نفسه، دائماً — وبلا نموذج ولا شبكة.**

    وهذا هو الشرط الذي يقوم عليه الملف كلّه: فحصٌ يحتاج نداءً **لا يُشغَّل**
    في كل تشغيل، وما لا يُشغَّل لا يُعوَّل عليه. وقد كشف هذا المشروع ثمن
    «ضمانة» لا تُختبر: العيب نفسه تكرّر في ثلاث مسودّات.
    """

    def test_the_same_inputs_give_the_same_outcome(self):
        """
        🔑 **خمس تشغيلات، مخرَج واحد** — نصّاً ونوعاً وملاحظةً.

        والفحص على **الكائن كاملاً** لا على النوع وحده: النوع ثابت والملاحظة
        تحمل الأرقام (التغطية والنسبة)، وهي التي تُقرأ في التقرير.
        """
        ledger = _the_ledger()
        outcomes = set()
        for _ in range(5):
            shifts = check_fidelity(THE_FLAWED_DRAFT, ledger)
            outcomes.add(
                tuple(
                    (shift.fact_key, shift.kind, shift.draft_text, shift.note)
                    for shift in shifts
                )
            )
        self.assertEqual(len(outcomes), 1, "الفحص غير حتمي — المخرَج تغيّر بين تشغيلين")

    def test_the_check_uses_no_model_and_no_network(self):
        """
        ⚠️ **الوحدة لا تستورد شبكة ولا عميل نموذج.**

        والفحص على **المصدر** لا على الوعد: استيرادُ وحدةِ شبكةٍ في هذا
        الملف يُلغي حتميته ولو لم يُندَ منها شيء، لأن أول من يناديها يُدخل
        الاعتماد. وهذا فحصٌ يُشبه ما في `test_labour_rules.py` حين قرأ مصدر
        الوحدة ليتحقّق من تحذير مكتوب فيها.
        """
        source = pathlib.Path(facts.__file__).read_text(encoding="utf-8")
        for forbidden in (
            "import requests",
            "import httpx",
            "import openai",
            "import socket",
            "urllib.request",
            "import asyncio",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)

    def test_the_check_does_not_write_or_print(self):
        """
        ⚠️ ولا طباعة ولا كتابة ملفّات: الوحدة **بلا إدخال/إخراج**، فتُختبر
        مباشرة وتُستدعى من أي مسار (الـ API، أو سطر أوامر، أو سكربت).

        ⚠️ **والبحث في الكود لا في نصّ الوثائق.** فالصيغة ``>>> print(...)``
        قد تظهر في مثال وثيقة (كما في ``assert_system_does_not_agree``)، وهي
        **ليست طباعة في الوحدة** بل سطر يُنفَّذ عند تشغيل `doctest`. ولو
        بحثنا في النصّ الخام لوقعنا بين أمرين: إمّا حذف المثال النافع، وإمّا
        إضعاف الفحص. فالفحص يجري على **الشجرة النحوية بعد إسقاط الوثائق** —
        وهذا أدقّ ما يمكن بلا تشغيل.
        """
        source = pathlib.Path(facts.__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)
        # إسقاط سلاسل الوثائق: أول تعبير في الوحدة، ثم أول تعبير في كل صنف
        # ودالّة — وهي المواضع التي تُكتب فيها الأمثلة.
        for node in ast.walk(tree):
            if not isinstance(
                node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
            ):
                continue
            body = getattr(node, "body", None)
            if not body:
                continue
            first = body[0]
            if (
                isinstance(first, ast.Expr)
                and isinstance(first.value, ast.Constant)
                and isinstance(first.value.value, str)
            ):
                first.value.value = ""
        code_without_docstrings = ast.unparse(tree)

        self.assertNotIn("print(", code_without_docstrings)
        self.assertNotIn("open(", code_without_docstrings)
        self.assertNotIn("sys.stdout", code_without_docstrings)
        # وتأكيد أن الإسقاط لم يُفرغ الملف: لو أفرغه لنجح الفحص على لا شيء.
        self.assertIn("def check_fidelity", code_without_docstrings)

    def test_the_same_inputs_give_the_same_summary(self):
        """
        ⚠️ **والبثّ حتميّ أيضاً** — و``summarize`` قابلة للتسلسل بلا محوّل.

        وترتيب الوقائع في القصاصة، وترتيب الافتراقات، كلاهما ثابت — فلو
        تغيّر لَتغيّر ما تراه الواجهة بين نداءين على المدخل نفسه.
        """
        ledger = FactLedger(
            (_the_release_fact(), _the_payment_fact()),
            versions=(
                FactVersion(document="مخالصة", version="1", date="2024-05-01"),
                FactVersion(document="مخالصة", version="2", date="2024-05-10", signed=True),
            ),
        )
        shifts = check_fidelity(THE_FLAWED_DRAFT, ledger)
        payloads = {json.dumps(summarize(ledger, shifts), ensure_ascii=False, sort_keys=True) for _ in range(3)}
        self.assertEqual(len(payloads), 1)

    def test_the_shifts_summary_is_json_safe(self):
        """وقصاصة الافتراقات وحدها صالحة للبثّ — للواجهة التي تعرض الفحص."""
        shifts = check_fidelity(THE_FLAWED_DRAFT, _the_ledger())
        payload = shifts_summary(shifts)
        self.assertIsInstance(payload, list)
        self.assertEqual(
            set(payload[0]),
            {"fact_key", "kind", "draft_text", "fact_statement", "note"},
        )
        json.dumps(payload, ensure_ascii=False)


# ==============================================================================
# ٩. العرض — القصاصة والسطر
# ==============================================================================


class TestSummary(unittest.TestCase):
    """
    القصاصة تُعطي الأعداد **والأسماء** — والاسم هو ما يُراجَع عليه.

    «ثمّ ثلاث وقائع تحتاج تحقّقاً» لا تُراجَع، و«``signature.status``
    و``salary.amount``» تُراجَع. وهذا فرقٌ في صلاحية التقرير لا في شكله.
    """

    def test_the_summary_counts_by_standing_and_names_the_rest(self):
        """القصاصة تُعدّ بالدرجة، وتُسمّي غير المحقَّقة وغير المُسنَدة بنصّ."""
        ledger = FactLedger((_the_release_fact(), _the_payment_fact()))
        payload = summarize(ledger)

        self.assertEqual(payload["fact_count"], 2)
        self.assertEqual(payload["by_standing"]["claimed"], 2)
        self.assertEqual(payload["by_standing"]["agreed"], 0)
        self.assertEqual(payload["unquoted"], ["payment.refused"])
        self.assertEqual(
            [fact["key"] for fact in payload["needs_verification"]], []
        )

    def test_the_summary_lists_the_conflicts_with_their_subject(self):
        """⚠️ والتناقض يُعرَض بموضوعه وطرفيه — لا بعدد."""
        ledger = FactLedger(
            (
                _the_release_fact(
                    key="release.signed",
                    statement="وقّع الموظف على المخالصة متضمّنة تنازلاً",
                ),
                _the_release_fact(
                    statement="لم يوقّع الموظف على المخالصة متضمّنة تنازلاً"
                ),
            )
        )
        payload = summarize(ledger)
        self.assertEqual(payload["conflict_count"], 1)
        conflict = payload["conflicts"][0]
        self.assertEqual(conflict["subject"], "release")
        self.assertEqual(
            {conflict["first"]["key"], conflict["second"]["key"]},
            {"release.signed", "release.refused"},
        )

    def test_the_summary_line_mentions_the_unquoted_facts(self):
        """
        ⚠️ **وذكر «بلا نصّ» في السطر مقصود.**

        لأن وقائع بلا نصّ تعني أن `citations.py` **لا يستطيع أن يقتبس لها**،
        فالمذكرة ستُبنى على معنى منقول. والمحامي يستحقّ أن يعرف ذلك من السطر
        الأول، لا أن يكتشفه حين يُرفض اقتباسه.
        """
        payload = summarize(FactLedger((_the_release_fact(), _the_payment_fact())))
        self.assertIn("بلا نصّ", payload["summary"])
        self.assertIn("وقائع: 2", payload["summary"])

    def test_the_summary_carries_the_shifts_it_was_given(self):
        """⚠️ والافتراقات جزءٌ من القصاصة إن أُعطيت — فلا يفترق الفحص عن التقرير."""
        shifts = check_fidelity(THE_FLAWED_DRAFT, _the_ledger())
        payload = summarize(_the_ledger(), shifts)
        self.assertEqual(len(payload["shifts"]), len(shifts))
        self.assertEqual(payload["shifts"][0]["fact_key"], "release.refused")

    def test_a_stale_settlement_figure_is_flagged(self):
        """
        🔑 **العيب الرابع: مبلغ من تسوية سابقة يُقرأ احتساباً.**

        وقرّرت مسودّة مبلغاً (١٢٥٠٠) جاء من تسوية سابقة لا من احتساب. والوسم
        على **الواقعة** لا على المسودّة: نقلُ المبلغ مشروع، والذي يجب أن
        يُمنع أن يُقرأ **محتسباً** — فيُنقل موسوماً بذلك.
        """
        settlement = _the_release_fact(
            key="settlement.amount",
            statement="بلغ التسوية السابقة ١٢٥٠٠ درهم",
            source="تسوية سابقة",
            quote="مبلغ التسوية ١٢٥٠٠ درهماً",
            subject="settlement",
        )
        self.assertTrue(stale_settlement_figure(settlement))
        self.assertFalse(stale_settlement_figure(_the_release_fact()))

    def test_the_thresholds_are_stated_and_ordered(self):
        """
        ⚠️ **والعتبتان معلنتان ومرتّبتان** — فلا تُقرأ عتبةٌ مكان أخرى.

        ولو تساوتا لَسقط التمييز بين «لم تُذكر» و«ذُكرت محرّفة»، وهو الفرق
        الذي يقرأه المحامي.
        """
        self.assertLess(FIDELITY_ACCEPT_COVERAGE, FIDELITY_REWORD_MAX_RATIO)
        self.assertLessEqual(FIDELITY_ACCEPT_COVERAGE, 1.0)
        self.assertLessEqual(FIDELITY_REWORD_MAX_RATIO, 1.0)

    def test_the_thresholds_are_documented_as_the_least_bad_available(self):
        """
        ⚠️ **وحدّ الفحص مكتوب في الكود لا مخفيّ.**

        المقارنة بالرموز **تُنذر على إعادة الصياغة**، والعلاج الحقيقي (نموذج
        يقيس المعنى) مرفوض عن قصد لأن الفحص يجب أن يبقى حتمياً. والحدّ الذي
        لا يُكتب في الكود **يُنسى**، ثم يُقرأ الإنذار الكاذب عيباً في الفحص.
        """
        source = pathlib.Path(facts.__file__).read_text(encoding="utf-8")
        self.assertIn("إنذار", source)
        self.assertIn("FIDELITY_REWORD_MAX_RATIO", source)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
