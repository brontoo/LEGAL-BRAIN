"""
اختبارات ملف القضية — الأسئلة التي لا تُصاغ مذكرة قبل أن تُسأل.
=============================================================================

تشغيل::

    cd legal-brain
    python -m unittest discover -s tests -t . -v

حتمية بالكامل: بلا شبكة، وبلا نموذج، وبلا قاعدة بيانات، وبلا قرص.

ولماذا لا تحتاج `fake_deps`؟ لأن هذا الملف لا يلمس الطبقة الخارجية أصلاً:
`case_file` وحدة نقية بلا حالة وبلا إدخال/إخراج، كـ `citations.py`
و`labour_rules.py`. فلا شيء يُستعار ولا شيء يُحاكى.

⚠️ **وأهمّ اختبار في هذا الملف ليس في الحقول، بل في الجدول:**
`test_regime_notes_match_the_real_case` و`test_regime_notes_are_not_empty_for_every_case`.

والسبب أن عيباً حقيقياً وقع في هذا الملف: المطابقة قارنت **مفاتيح لاتينية**
(``difc``، ``dubai``، ``abu_dhabi``) بـ**نصّ عربي حرّ** (``"أبوظبي"``)، فكان
التقاطع فراغاً **دائماً** — صفرُ ملاحظات في كل قضية، ومنها قضية عمالية في
أبوظبي. ⚠️ **والفراغ كان صامتاً:** يُقرأ على أنه «لا موضع افتراق في قضيتك»،
فيتوقّف المحامي عن السؤال — **وهو نقيض ما وُجد الجدول له**.

فالاختبارات هنا تحرس ثلاثة أشياء لا الحقول وحدها:

١. أن المطابقة تقع على **المفاتيح** لا على النصّ (`EmirateKey`, `ForumKey`).
٢. أن **كل ملاحظة في الجدول يمكن بلوغها** بقضية قابلة للبناء — فلا تبقى
   ملاحظة مكتوبة لا تظهر أبداً، وهو عيب صامت آخر من الجنس نفسه.
٣. أن **كل نصّ لا يُعرف مفتاحه يرفع استثناءً** ولا يمرّ صامتاً.
"""

import json
import pathlib
import re as _re
import unittest
from dataclasses import fields, replace

import case_file
from case_file import (
    BLOCKING_FIELDS,
    EMIRATE_ALIASES,
    EMIRATES,
    ESTABLISHED_FIELDS,
    QUESTIONS,
    REGIME_NOTES,
    CaseFile,
    CaseStage,
    DisputeType,
    ForumKey,
    Party,
    Question,
    RegimeArea,
    RegimeNote,
    derive_emirate_key,
    derive_forum_key,
    notes_summary,
    questions_for,
    regime_notes,
)
from labour_rules import period_days

from datetime import date


# ==============================================================================
# بيانات الاختبار — قضايا **مبنية في الاختبار** لا مستعارة من الملف
# ==============================================================================
# ⚠️ تُبنى هنا لا تُنادَى من `case_file._complete_case()` عن قصد: لو نادى
# الاختبار بيانات الملف، ثم عُدّلت بيانات الملف، **لتغيّر الاختبار معها**
# فلم يعد يحرس شيئاً. والبناء في الاختبار يجعل التغيّر يُكشَف، وهو المطلوب.
#
# ⚠️ وواحدة فقط تُنادَى من الملف: `_difc_case` في اختبار الوثائق، حيث يكون
# المطلوب **فحص المثال المنشور** لا فحص قيمة بعينها.


def _replace_regime(case: CaseFile, **changes) -> CaseFile:
    """
    نسخة من ملف القضية بتغيير حقول العقد وحدها — **بلا تعديل الأصل**.

    ⚠️ و``dataclasses.replace`` تُعيد بناء النسخة فتمرّ بـ``__post_init__``
    (فحُقوق الحارس باقية)، ولا تُعدّل الكائن الأصلي (فهو مجمَّد). وهذا مقصود:
    الحالات تُبنى من بعضها بلا أن يُفسد إحداها الأخرى.
    """
    return replace(case, **changes)


def _abudhabi_labour(*, forum: str = "محكمة أبوظبي الابتدائية") -> CaseFile:
    """
    🔑 **القضية التي كشفت عيب المطابقة:** دعوى عمالية في أبوظبي على البرّ.

    ⚠️ وهي كانت تُعيد **صفر ملاحظات**، ومنها ملاحظة مسار وزارة الموارد
    البشرية — وهي أمثل ما ينطبق عليها. فالمتوقّع لها الآن ملاحظتان:
    ``employment`` و``emirate``.
    """
    return CaseFile(
        country="الإمارات العربية المتحدة",
        emirate="أبوظبي",
        forum=forum,
        dispute_type=DisputeType.LABOUR,
        stage=CaseStage.FIRST_INSTANCE,
        our_party=Party.CLAIMANT,
        claims=("مكافأة نهاية الخدمة",),
        key_dates=(("تاريخ انتهاء العلاقة", "2026-08-31"),),
        likely_law=("المرسوم بقانون اتحادي ٣٣ لسنة ٢٠٢١",),
        has_arbitration_clause=False,
        has_choice_of_law=False,
    )


def _onshore_dubai(*, dispute_type: DisputeType = DisputeType.COMMERCIAL) -> CaseFile:
    """قضية في دبي على البرّ — أمام محكمة، لا أمام مركز مالي."""
    return CaseFile(
        country="الإمارات العربية المتحدة",
        emirate="دبي",
        forum="محكمة دبي الابتدائية",
        dispute_type=dispute_type,
        stage=CaseStage.FIRST_INSTANCE,
        our_party=Party.DEFENDANT,
        claims=("رفض المطالبة",),
        key_dates=(("تاريخ الواقعة", "2025-04-01"),),
        likely_law=("قانون المعاملات المدنية",),
        has_arbitration_clause=False,
        has_choice_of_law=False,
    )


def _difc() -> CaseFile:
    """قضية أمام محاكم مركز دبي المالي العالمي — مفتاحها ``difc`` لا ``dubai``."""
    return CaseFile(
        country="الإمارات العربية المتحدة",
        emirate="دبي",
        forum="محاكم مركز دبي المالي العالمي (DIFC Courts)",
        dispute_type=DisputeType.COMMERCIAL,
        stage=CaseStage.FIRST_INSTANCE,
        our_party=Party.DEFENDANT,
        claims=("رفض المطالبة",),
        key_dates=(("تاريخ الواقعة", "2025-04-01"),),
        likely_law=("قوانين مركز دبي المالي العالمي",),
        has_arbitration_clause=False,
        has_choice_of_law=False,
    )


def _adgm() -> CaseFile:
    """قضية أمام محاكم سوق أبوظبي العالمي — مركز مالي بإمارة أبوظبي."""
    return CaseFile(
        country="الإمارات العربية المتحدة",
        emirate="أبوظبي",
        forum="محاكم سوق أبوظبي العالمي (ADGM Courts)",
        dispute_type=DisputeType.COMMERCIAL,
        stage=CaseStage.FIRST_INSTANCE,
        our_party=Party.CLAIMANT,
        claims=("تنفيذ التزام تعاقدي",),
        key_dates=(("تاريخ الواقعة", "2025-05-01"),),
        likely_law=("قوانين سوق أبوظبي العالمي",),
        has_arbitration_clause=False,
        has_choice_of_law=False,
    )


def _incomplete() -> CaseFile:
    """
    ملف ناقص: لا إمارة ولا جهة ولا طلبات — **النقص مكتوب لا محذوف**.

    ⚠️ والنقص يُكتب لأن حقول ``CaseFile`` بلا افتراضي: لا وجود لحالة «ملف
    افتراضي» يملؤها الكود، وهي القيمة المفترضة التي جاء الملف لمنعها.
    """
    return CaseFile(
        country="الإمارات العربية المتحدة",
        emirate="",
        forum="",
        dispute_type=DisputeType.LABOUR,
        stage=CaseStage.FIRST_INSTANCE,
        our_party=Party.CLAIMANT,
        claims=(),
        key_dates=(),
        likely_law=(),
    )


# ==============================================================================
# ١. التصنيفات المغلقة — الجولة الكاملة على القيمة الآلية
# ==============================================================================


def _round_trip(enum_class):
    """يعيد كل قيمة تصنيف بعد جولة على قيمتها الآلية."""
    return [enum_class(member.value) for member in enum_class]


class TestEnumsRoundTrip(unittest.TestCase):
    """
    كل تصنيف يعود من قيمته الآلية **القيمة نفسها** — لا صورةً تشبهها.

    ⚠️ **ولماذا هذا اختبار لا عبث؟** لأن التصنيفات تُبَثّ إلى الواجهة
    بقيمها الآلية (``"first_instance"``) وتُقرأ منها في نداء لاحق. فلو لم
    تُعِد الجولة القيمة نفسها لَما كان للبثّ معنى، ولَما أمكن أن يُفحَص ملف
    قضية أعادته الواجهة. وهذا موضع يمرّ فيه الخطأ صامتاً: ``"first instance"``
    بفراغ لا يُرفض إلا إن كانت الجولة مفحوصة.
    """

    def test_case_stage_round_trips(self):
        """المرحلة: كل قيمة من ``CaseStage`` تعود من نصّها الآلي."""
        for stage in CaseStage:
            with self.subTest(stage=stage.value):
                self.assertIs(CaseStage(stage.value), stage)
        self.assertEqual(
            [member.value for member in CaseStage],
            [
                "first_instance",
                "appeal",
                "cassation",
                "reconsideration",
                "execution",
                "arbitration",
            ],
        )

    def test_dispute_type_round_trips(self):
        """
        نوع النزاع: الجولة كاملة، **و``LEASE`` مستقلة عن ``REAL_ESTATE``**.

        ⚠️ والاستقلال مقصود ومفحوص: لو أُعيدت المطابقة بينهما «تبسيطاً»
        لسقط أثر مسار فضّ المنازعات الإيجارية من أوّل حقل — وهو مسار له
        لائحة وإجراء يختلفان عن نزاع الملكية العقارية.
        """
        for dispute in DisputeType:
            with self.subTest(dispute=dispute.value):
                self.assertIs(DisputeType(dispute.value), dispute)
        self.assertNotEqual(DisputeType.LEASE, DisputeType.REAL_ESTATE)
        self.assertNotEqual(DisputeType.LEASE.value, DisputeType.REAL_ESTATE.value)

    def test_party_round_trips(self):
        """الصفة: جولة كاملة، **ولا قيمة محايدة** («الطرفان») في التصنيف."""
        for party in Party:
            with self.subTest(party=party.value):
                self.assertIs(Party(party.value), party)
        self.assertEqual([member.value for member in Party], ["claimant", "defendant"])

    def test_forum_key_round_trips(self):
        """مفتاح الجهة: التصنيف الذي تُبنى عليه مطابقة المركزين الماليين."""
        for forum in ForumKey:
            with self.subTest(forum=forum.value):
                self.assertIs(ForumKey(forum.value), forum)
        self.assertIn(ForumKey.DIFC.value, {member.value for member in ForumKey})

    def test_regime_area_round_trips(self):
        """باب الافتراق: الجولة كاملة — وهو مفتاح التصفية على الجدول."""
        for area in RegimeArea:
            with self.subTest(area=area.value):
                self.assertIs(RegimeArea(area.value), area)
        self.assertEqual(
            {member.value for member in RegimeArea},
            {"free_zone", "emirate", "employment", "choice_of_law", "arbitration"},
        )

    def test_a_str_enum_keeps_its_machine_value_as_the_string(self):
        """
        التصنيف نصّ أيضاً — فتُقارَن قيمته بالنصّ بلا ``.value``.

        وهذا ما يجعل ``json.dumps`` والفرز والمقارنة تعمل بلا تحويل، وهو
        قرار مقصود في ``str, Enum`` كما في ``DisputeType`` في هذا المشروع.
        """
        self.assertEqual(CaseStage.APPEAL, "appeal")
        self.assertEqual(DisputeType.LABOUR, "labour")
        self.assertIn("lease", {member.value for member in DisputeType})


# ==============================================================================
# ٢. الحقول المانعة والأسئلة — العيب الذي يوقف الصياغة
# ==============================================================================


class TestBlockingFields(unittest.TestCase):
    """
    ⚠️ **المانع يوقف، ولا يُكمَل من عند الكود.**

    وهذا هو موضع العيب الذي جاء الملف لمنعه: قيمة افتراضية لحقل مانع
    **تُنتج نصّاً صحيحاً في نظام وخاطئاً في الذي ينطبق**، ولا يمكن كشفها بعد
    الكتابة لأنها لا تُكتب في مكان. فالاختبار هنا يثبّت **الغياب** لا الوجود.
    """

    def test_blocking_fields_are_a_subset_of_the_established_fields(self):
        """المانع جزءٌ من المسجَّل، وترتيبه أوّل ``ESTABLISHED_FIELDS``."""
        self.assertTrue(set(BLOCKING_FIELDS) <= set(ESTABLISHED_FIELDS))
        self.assertEqual(
            ESTABLISHED_FIELDS[: len(BLOCKING_FIELDS)],
            BLOCKING_FIELDS,
            "المانعة أولاً — فتُسأل أولاً وتُعرض أولاً",
        )

    def test_every_blocking_field_is_a_real_case_file_field(self):
        """
        ⚠️ اسم حقل مانع لا يقابل حقلاً في ``CaseFile`` عيبٌ صامت.

        ولو كُتب في القائمة اسم غير موجود لَما ظهر في ``missing()`` أبداً،
        فبدا الملف مكتملاً وهو ناقص — وهو نفس نمط العيب الذي وقع في المطابقة
        (وسمٌ لا يُطابق شيئاً فيمرّ صامتاً).
        """
        names = {field.name for field in fields(CaseFile)}
        for name in BLOCKING_FIELDS:
            with self.subTest(field=name):
                self.assertIn(name, names)
        for name in ESTABLISHED_FIELDS:
            with self.subTest(field=name):
                self.assertIn(name, names)

    def test_a_missing_blocking_field_is_never_silently_defaulted(self):
        """
        🔑 **الحقل المانع لا قيمة له في البناء: يُكتب أو يُقرأ في ``missing()``.**

        والنقص هنا **مُعلَن** لا مُكمَل: ``missing()`` تُسمّيه، ``is_complete``
        تُنكر الاكتمال، و``questions_for`` تسأل عنه. ولو أُكمل من عند الكود
        لَما ظهر في واحدة منها.
        """
        case = _incomplete()
        self.assertEqual(
            case.missing(blocking_only=True), ("emirate", "forum", "claims")
        )
        self.assertFalse(case.is_complete())
        # ولا قيمة يُملأ بها الفراغ: الحقل كما كُتب بالضبط.
        self.assertEqual(case.emirate, "")
        self.assertEqual(case.forum, "")
        self.assertEqual(case.claims, ())
        # والمفتاح المشتقّ من نصّ فارغ يبقى فارغاً — ولا يُخمَّن إمارة.
        self.assertEqual(case.emirate_key, "")
        self.assertEqual(case.forum_key, "")

    def test_a_complete_case_has_no_missing_blocking_field(self):
        """والملف المكتمل لا مانع فيه — فلا يُوقف مسار الصياغة بلا سبب."""
        case = _onshore_dubai()
        self.assertEqual(case.missing(blocking_only=True), ())
        self.assertTrue(case.is_complete())

    def test_confirmed_and_missing_partition_the_fields(self):
        """
        ⚠️ ``confirmed`` و``missing`` **قسمة** لا وصفان مستقلّان.

        ولو افترقا لأمكن أن يكون حقلٌ ثابتاً ومفقوداً معاً — وهو التناقض
        الداخلي نفسه الذي رُصد في ``labour_rules.py`` حين صار لشيء واحد
        معياران. فالاختبار يفحص **أنهما لا يتقاطعان وأنهما يستغرقان**.
        """
        for case in (_incomplete(), _onshore_dubai(), _difc(), _abudhabi_labour()):
            with self.subTest(emirate=case.emirate, forum=case.forum):
                confirmed = set(case.confirmed())
                missing = set(case.missing())
                self.assertEqual(confirmed & missing, set())
                self.assertEqual(confirmed | missing, set(ESTABLISHED_FIELDS))


class TestQuestions(unittest.TestCase):
    """
    الأسئلة: **بترتيب الأولوية، المانع أولاً** — وبلا سؤال مخترع.

    والترتيب ليس تفصيلاً: المحامي يُسأل عن الحقل الذي يُغيّر الاختصاص قبل
    الحقل الذي يُكمل البيان، وإلا استُنزف في التفاصيل وتوقّف عن السؤال
    الذي يُغيّر النتيجة.
    """

    def test_blocking_questions_come_first(self):
        """
        🔑 الحقول المانعة أولاً في ``QUESTIONS``، ثم غيرها.

        والفحص على **موضع كل حقل** لا على مجموعة: القائمة المكتوبة بترتيبها
        هي المصدر الوحيد للترتيب، فيجب أن يكون الترتيب فيها ظاهراً.
        """
        fields = [question.field for question in QUESTIONS]
        blocking_positions = [fields.index(name) for name in BLOCKING_FIELDS]
        other_positions = [
            fields.index(name)
            for name in ("country", "likely_law", "key_dates")
            if name in fields
        ]
        self.assertEqual(blocking_positions, sorted(blocking_positions))
        if other_positions:
            self.assertLess(
                max(blocking_positions),
                min(other_positions),
                "سؤال مانع بعد سؤال غير مانع — الترتيب انقلب",
            )

    def test_questions_for_returns_only_the_missing_in_priority_order(self):
        """
        ``questions_for`` تُرجع أسئلة الناقص وحده، **بترتيب ``QUESTIONS``**.

        ⚠️ ولا يُفرز الناتج فرزه ثانية: الفرز على ``BLOCKING_FIELDS`` يجعل
        للترتيب مصدرين يفترقان عند أول تعديل.
        """
        result = questions_for({"claims", "emirate", "key_dates"})
        self.assertEqual([question.field for question in result], ["emirate", "claims", "key_dates"])
        self.assertNotIn("dispute_type", [question.field for question in result])

    def test_questions_for_ignores_an_unknown_field(self):
        """
        ⚠️ **الحقل المجهول يُهمَل ولا يُخترع له سؤال.**

        وسؤالٌ مخترع يُجاب، والجواب يُكتب في القالب فيصير **افتراضاً صامتاً**
        — وهو العيب نفسه الذي جاء الملف لمنعه.
        """
        result = questions_for({"لا_يوجد_مثل_هذا_الحقل", "claims"})
        self.assertEqual([question.field for question in result], ["claims"])

    def test_every_question_has_its_why(self):
        """
        سؤال بلا سبب **يُقرأ استيفاءً لشكليات**، فلا يُجاب جواباً واعياً.

        وكل سؤال في الملف يجب أن يحمل سببه، وأن تكون صيغته صيغة سؤال.
        """
        for question in QUESTIONS:
            with self.subTest(field=question.field):
                self.assertIsInstance(question, Question)
                self.assertTrue(question.question.strip())
                self.assertTrue(question.why.strip())
                self.assertIn("؟", question.question)

    def test_the_question_for_a_missing_field_is_never_defaulted(self):
        """
        🔑 **الملف الناقص يُنتج أسئلة، ولا يُنتج قيماً مفترضة.**

        وهذا الفرق بين استمارة تُسأل وأخرى تُخمَّن: ``questions_for_missing``
        تُرجع الأسئلة، والحقول تبقى فارغة كما كُتبت — فلا يُبنى عليها شيء
        في المسار.
        """
        case = _incomplete()
        asked = [question.field for question in case.questions_for_missing()]
        # ⚠️ والمانعة أولاً، ثم ما يكمل البيان — والترتيب هو ترتيب `QUESTIONS`.
        self.assertEqual(
            asked, ["emirate", "forum", "claims", "likely_law", "key_dates"]
        )
        # والحقل الثابت لا يُسأل عنه أصلاً.
        self.assertNotIn("dispute_type", asked)
        # ⚠️ والمانع الناقص يُسأل عنه **قبل** ما يكمل البيان.
        self.assertLess(asked.index("emirate"), asked.index("likely_law"))
        self.assertLess(asked.index("forum"), asked.index("key_dates"))
        # والحقول نفسها لم تُملأ: السؤال مخرَج، لا تعيين.
        self.assertEqual(case.claims, ())
        self.assertEqual(case.emirate, "")

    def test_the_open_regime_questions_distinguish_none_from_false(self):
        """
        ⚠️ **``None`` («لم يُنظر») تُسأل، و``False`` («لا يوجد») لا تُسأل.**

        والخلط بينهما يجعل السؤال يُطرح على من أجاب، فيُقرأ استيفاءً
        ويُهمَل — ثم يُهمَل معه السؤال الحقيقي حين يظهر. وهو الفرق نفسه
        بين «لا» و«لا أعرف» في ``FactVersion.signed`` في `facts.py`.

        ⚠️ والفحص **حقلٌ حقلٌ** لا على القائمة كلها: الجواب عن أحد السؤالين
        لا يُسقط الآخر، ولو فُحصا معاً لَما ظهر الفرق بين الحالتين.
        """
        unanswered = CaseFile(
            country="الإمارات العربية المتحدة",
            emirate="دبي",
            forum="محكمة دبي الابتدائية",
            dispute_type=DisputeType.COMMERCIAL,
            stage=CaseStage.FIRST_INSTANCE,
            our_party=Party.CLAIMANT,
            claims=("مطالبة",),
            key_dates=(),
            likely_law=(),
        )
        self.assertEqual(
            [question.field for question in unanswered.open_regime_questions()],
            ["has_choice_of_law", "has_arbitration_clause"],
        )

        chosen_only = _replace_regime(unanswered, has_choice_of_law=True)
        self.assertEqual(
            [question.field for question in chosen_only.open_regime_questions()],
            ["has_arbitration_clause"],
            "الجواب عن القانون المختار لا يُسقط سؤال شرط التحكيم",
        )

        clause_only = _replace_regime(unanswered, has_arbitration_clause=False)
        self.assertEqual(
            [question.field for question in clause_only.open_regime_questions()],
            ["has_choice_of_law"],
            "وقول «لا شرط تحكيم» جوابٌ يسقط سؤاله هو وحده",
        )

        both_answered = _replace_regime(
            unanswered, has_choice_of_law=False, has_arbitration_clause=False
        )
        self.assertEqual(both_answered.open_regime_questions(), ())

    def test_the_free_zone_does_not_ask_about_a_chosen_law(self):
        """
        ⚠️ **والمركز المالي مستثنى من سؤال القانون المختار عن قصد.**

        لأن نظام المركز يُسأل عنه في ملاحظته أصلاً، وسؤال «هل اختير قانون
        آخر؟» فيه تكرار يُنقص قيمة السؤال الأول. فالناتج سؤال شرط التحكيم
        وحده — وحدّ هذا الاستثناء **ظاهر في الاختبار** لا مسكوت عنه.
        """
        free_zone = _replace_regime(_difc(), has_choice_of_law=None, has_arbitration_clause=None)
        self.assertEqual(
            [question.field for question in free_zone.open_regime_questions()],
            ["has_arbitration_clause"],
        )
        # والملف على البرّ يُسأل عن الاثنين.
        onshore = _replace_regime(
            _onshore_dubai(), has_choice_of_law=None, has_arbitration_clause=None
        )
        self.assertEqual(
            [question.field for question in onshore.open_regime_questions()],
            ["has_choice_of_law", "has_arbitration_clause"],
        )


# ==============================================================================
# ٣. الجدول — المطابقة على المفاتيح، لا على النصّ العربي
# ==============================================================================


class TestEmirateAndForumKeys(unittest.TestCase):
    """
    المفاتيح: **الموضع الوحيد الذي يُشتقّ فيه مفتاح من نصّ** — وهو يُفحَص.

    ⚠️ وهذا هو العيب الذي وُجدت هذه الاختبارات له: مطابقةٌ على النصّ الحرّ
    لا تُطابق شيئاً، والفراغ يُقرأ سلامةً. فالنصّ الذي لا يُعرف مفتاحه يجب
    أن **يرفع استثناءً** لا أن يمرّ.
    """

    def test_every_emirate_has_an_alias_and_every_alias_maps_to_a_real_emirate(self):
        """
        ⚠️ **لا مفتاح بلا صورة، ولا صورة إلى مفتاح غير موجود.**

        والفحص في الاتجاهين: مفتاحٌ بلا صورة لا يمكن بلوغه أبداً (فتصمت
        ملاحظته)، وصورةٌ إلى مفتاح مخترع **تنسب قضية إلى إمارة غير موجودة**.
        """
        aliases = set(EMIRATE_ALIASES.values())
        self.assertEqual(aliases, set(EMIRATES))
        for alias, key in EMIRATE_ALIASES.items():
            with self.subTest(alias=alias):
                self.assertIn(key, EMIRATES)

    def test_the_emirate_key_is_derived_from_arabic_and_latin_forms(self):
        """
        المفتاح يُشتقّ من الصورتين: العربية بأدوات التعريف وبلاها، واللاتينية.

        ⚠️ و«إمارة دبي» و«دبي» و«DUBAI» و«dubai» قضية واحدة — والاشتقاق
        **مرة واحدة هنا** أهون من تكراره في كل موضع مطابقة.
        """
        self.assertEqual(derive_emirate_key("دبي"), "dubai")
        self.assertEqual(derive_emirate_key("إمارة دبي"), "dubai")
        self.assertEqual(derive_emirate_key("DUBAI"), "dubai")
        self.assertEqual(derive_emirate_key("أبوظبي"), "abu_dhabi")
        self.assertEqual(derive_emirate_key("أبو ظبي"), "abu_dhabi")
        self.assertEqual(derive_emirate_key("الشارقة"), "sharjah")
        self.assertEqual(derive_emirate_key("ras_al_khaimah"), "ras_al_khaimah")
        self.assertEqual(derive_emirate_key("غير_معروفة"), None)

    def test_an_unknown_emirate_text_fails_loudly(self):
        """
        🔑 **النصّ المجهول يرفع استثناءً — ولا يُسقِط المطابقة صامتاً.**

        وهذا هو الدرس بعينه: أول نسخة أسقطت كل ملاحظة **بصمت**، فقُرئ
        الفراغ «لا موضع افتراق». فالآن النصّ غير المذكور في
        ``EMIRATE_ALIASES`` **يوقف البناء** حتى تُضاف صورته في موضع واحد.
        والمقايضة معلنة: توقّفٌ ظاهر أهون من تقرير فارغ كاذب.
        """
        with self.assertRaises(ValueError) as caught:
            CaseFile(
                country="الإمارات العربية المتحدة",
                emirate="دولة قطر",
                forum="محكمة",
                dispute_type=DisputeType.CIVIL,
                stage=CaseStage.FIRST_INSTANCE,
                our_party=Party.CLAIMANT,
                claims=("مطالبة",),
                key_dates=(),
                likely_law=(),
            )
        message = str(caught.exception)
        self.assertIn("EMIRATE_ALIASES", message)
        self.assertIn("دولة قطر", message)

    def test_an_empty_emirate_text_is_missing_not_an_error(self):
        """
        ⚠️ **والفراغ ليس نصّاً مجهولاً:** هو «لم يُسجَّل»، ويُسأل عنه.

        ولو رفع الفراغ استثناءً لَما أمكن بناء ملف ناقص أصلاً — ولَما ظهر
        السؤال، وهو أول ما يجب أن يظهر.
        """
        case = _incomplete()
        self.assertEqual(case.emirate, "")
        self.assertEqual(case.emirate_key, "")
        self.assertIn("emirate", case.missing())

    def test_the_forum_key_separates_the_free_zones_from_onshore(self):
        """
        🔑 **``difc`` و``adgm`` وصفٌ للجهة لا للإمارة.**

        فمفتاح جهة قضية في دبي على البرّ ``onshore`` وإن كانت إمارتها
        ``dubai`` — وهذا هو الفصل الذي يمنع تسرّب ملاحظة المركز المالي إلى
        قضية إيجار في دبي، وهو نصّ صحيح في موضع خاطئ.
        """
        self.assertEqual(derive_forum_key("محاكم مركز دبي المالي العالمي (DIFC Courts)"), "difc")
        self.assertEqual(derive_forum_key("محاكم سوق أبوظبي العالمي (ADGM Courts)"), "adgm")
        self.assertEqual(derive_forum_key("محكمة دبي الابتدائية"), "onshore")
        self.assertEqual(derive_forum_key("مركز فضّ المنازعات الإيجارية - دبي"), "onshore")
        # والتحكيم يُقدَّم: «مركز دبي للتحكيم» تحكيمٌ لا مركزٌ مالي.
        self.assertEqual(derive_forum_key("مركز دبي للتحكيم"), "arbitration")
        self.assertEqual(_difc().forum_key, "difc")
        self.assertEqual(_onshore_dubai().forum_key, "onshore")
        self.assertTrue(_difc().is_free_zone)
        self.assertFalse(_onshore_dubai().is_free_zone)

    def test_every_forum_alias_points_to_a_forum_key(self):
        """
        ⚠️ كل صورة في جدول الجهات تُشير إلى مفتاح من ``ForumKey``.

        والفحص يمنع مفتاحاً حرّاً مكتوباً في الجدول: مفتاحٌ غير معرّف لا
        يُقارَن بشيء في الشرط، فتُكتب الصورة ولا تعمل — وهو عيب صامت.
        """
        allowed = {member.value for member in ForumKey}
        for needle, key in case_file._FORUM_ALIASES:
            with self.subTest(needle=needle):
                self.assertIn(key, allowed)


class TestRegimeNotes(unittest.TestCase):
    """
    🔑 **جدول أماكن الافتراق — وهو موضع العيب الحقيقي في هذا الملف.**

    وكان يعود **صفر ملاحظات في كل قضية**، ومنها قضية عمالية في أبوظبي. وهذا
    هو أسوأ ما يمكن أن تفعله أداة تحقّق: أن تصمت فيُقرأ صمتها سلامة.
    """

    def test_regime_notes_match_the_real_case(self):
        """
        🔑 **قضية عمالية في أبوظبي يجب أن تُرجع ملاحظة مسار الوزارة.**

        وهي الاختبار الذي **كان يفشل** قبل إصلاح المطابقة، وهذا مقصوده:
        اختبارٌ يمرّ مع الكود الخاطئ لا يحرس شيئاً. فالمفحوص هنا اسم الباب
        (``employment``) لا عدد الملاحظات.
        """
        notes = regime_notes(_abudhabi_labour())
        areas = [note.area for note in notes]
        self.assertIn(
            RegimeArea.EMPLOYMENT,
            areas,
            "قضية عمالية على البرّ ولا ملاحظة عن مسار الوزارة — المطابقة صامتة",
        )
        self.assertIn(RegimeArea.EMIRATE, areas)
        self.assertTrue(areas, "صفر ملاحظات لقضية عمالية في أبوظبي")
        # والسند والحدّ مكتوبان، فلا تصير الملاحظة رأياً بلا مرجع.
        employment = next(note for note in notes if note.area is RegimeArea.EMPLOYMENT)
        self.assertTrue(employment.source.strip())
        self.assertTrue(employment.limit.strip())

    def test_difc_notes_do_not_leak_into_onshore_dubai(self):
        """
        🔑 **الفصل الذي يقوم عليه ``forum_key``: مركز مالي ≠ دبي على البرّ.**

        فقضية أمام محاكم مركز دبي المالي تُرجع ملاحظة المنطقة الحرّة، وقضية
        في دبي على البرّ **لا** تُرجعها — وإن اتّفقت الإمارة. ولو لم يُفصل
        لَظهرت ملاحظة «لا يُقاس على قانون العمل الاتحادي» في ملفٍّ لا شأن
        له بمركز مالي، وهي **نصّ صحيح في موضع خاطئ**.
        """
        difc_areas = {note.area for note in regime_notes(_difc())}
        onshore_areas = {note.area for note in regime_notes(_onshore_dubai())}
        self.assertIn(RegimeArea.FREE_ZONE, difc_areas)
        self.assertNotIn(
            RegimeArea.FREE_ZONE,
            onshore_areas,
            "ملاحظة مركز مالي ظهرت في قضية على البرّ — تسرّبت",
        )

    def test_onshore_dubai_notes_do_not_leak_into_difc(self):
        """
        🔑 **والفصل في الاتجاه الآخر — وهو الذي يُسقط النصّ الصحيح.**

        قضية أمام مركز مالي إمارتها ``dubai``، فلو قرأت المطابقة الإمارة
        لَظهرت لها ملاحظة النظام القضائي المحلي ومركز فضّ المنازعات الإيجارية
        — وهي **صحيحة في دبي وخاطئة في هذه القضية**.
        """
        difc_areas = {note.area for note in regime_notes(_difc())}
        self.assertNotIn(RegimeArea.EMIRATE, difc_areas)
        self.assertNotIn(RegimeArea.EMPLOYMENT, difc_areas)
        self.assertEqual(difc_areas, {RegimeArea.FREE_ZONE})

    def test_regime_notes_are_not_empty_for_every_case(self):
        """
        🔑 **لا ملاحظة مكتوبة لا تُبلَغ أبداً.**

        وهذا عيب صامت من جنس العيب الأول: الشرط إمّا لا يُطابق شيئاً أبداً،
        وإمّا يُطابق لكن لا قضية قابلة للبناء تُظهره. وفي الحالتين **يُقرأ
        الجدول أكبر مما هو عليه**. فالفحص: لكل ``trigger`` في الجدول قضيةٌ
        تُرجع ملاحظته.
        """
        built = {
            "free_zone": _difc(),
            "onshore_emirate": _onshore_dubai(),
            "other_emirates": CaseFile(
                country="الإمارات العربية المتحدة",
                emirate="الشارقة",
                forum="محكمة الشارقة الابتدائية",
                dispute_type=DisputeType.CIVIL,
                stage=CaseStage.FIRST_INSTANCE,
                our_party=Party.DEFENDANT,
                claims=("رفض المطالبة",),
                key_dates=(),
                likely_law=(),
                has_arbitration_clause=False,
                has_choice_of_law=False,
            ),
            "onshore_labour": _abudhabi_labour(),
            "choice_of_law": CaseFile(
                country="الإمارات العربية المتحدة",
                emirate="دبي",
                forum="محكمة دبي الابتدائية",
                dispute_type=DisputeType.COMMERCIAL,
                stage=CaseStage.FIRST_INSTANCE,
                our_party=Party.CLAIMANT,
                claims=("مطالبة",),
                key_dates=(),
                likely_law=("القانون الإنجليزي",),
                has_arbitration_clause=False,
                has_choice_of_law=True,
            ),
            "arbitration_clause": CaseFile(
                country="الإمارات العربية المتحدة",
                emirate="دبي",
                forum="هيئة التحكيم",
                dispute_type=DisputeType.COMMERCIAL,
                stage=CaseStage.ARBITRATION,
                our_party=Party.DEFENDANT,
                claims=("رفض المطالبة",),
                key_dates=(),
                likely_law=(),
                has_arbitration_clause=True,
                has_choice_of_law=False,
            ),
        }
        triggers = {note.trigger for note in REGIME_NOTES}
        self.assertEqual(
            triggers,
            set(built),
            "شرط في الجدول بلا قضية تُظهره، أو قضية اختبار لشرط غير موجود",
        )
        for trigger, case in built.items():
            with self.subTest(trigger=trigger):
                returned = {note.trigger for note in regime_notes(case)}
                self.assertIn(
                    trigger,
                    returned,
                    f"الشرط {trigger} لا يُبلَغ بأي قضية — ملاحظة ميتة",
                )

    def test_every_note_carries_its_source_and_its_limit(self):
        """
        ⚠️ **ملاحظة بلا مصدر رأيٌ يتنكّر في هيئة مرجع، وبلا حدٍّ تُقرأ أوسع
        مما هي عليه.**

        وكلتا الحالتين تُنتج العيب الذي جاء الجدول لمنعه: نصّ صحيح في موضع
        خاطئ، يُقرأ نتيجةً لا سؤالاً.
        """
        for note in REGIME_NOTES:
            with self.subTest(area=note.area.value, trigger=note.trigger):
                self.assertTrue(note.source.strip())
                self.assertTrue(note.limit.strip())
                self.assertTrue(note.note.strip())
                self.assertIn("تحقّق", note.note)

    def test_every_note_names_the_fields_its_trigger_reads(self):
        """
        ⚠️ ``applies_to`` **توثيقٌ يُفحَص آلياً** لا زينة.

        فلو قال شرطٌ إنه يقرأ ``forum_key`` وهو يقرأ ``emirate_key``، لتوثّق
        للقارئ خلاف ما يجري — وهو أسوأ من غياب التوثيق.
        """
        allowed = {
            "emirate_key",
            "forum_key",
            "dispute_type",
            "has_choice_of_law",
            "has_arbitration_clause",
        }
        for note in REGIME_NOTES:
            with self.subTest(trigger=note.trigger):
                self.assertTrue(note.applies_to)
                self.assertTrue(set(note.applies_to) <= allowed)

    def test_every_note_trigger_is_registered(self):
        """
        ⚠️ شرطٌ غير مسجَّل في ``_TRIGGERS`` **يجعل الملاحظة لا تُفتح أبداً**.

        وهذا حلقة من العيب الأول: الجدول يبدو أكبر مما يعمل. فيُفحَص
        التطابق بين الأسماء في الجدول وأسماء الشروط المسجّلة.
        """
        for note in REGIME_NOTES:
            with self.subTest(trigger=note.trigger):
                self.assertIn(note.trigger, case_file._TRIGGERS)

    def test_every_trigger_is_used_by_some_note(self):
        """
        ⚠️ وشرطٌ مسجَّل لا تُفتح به ملاحظة **كودٌ ميت يبدو فعّالاً**.

        والفحص في الاتجاهين، فلا يبقى شرطٌ بلا ملاحظة ولا ملاحظة بلا شرط.
        """
        used = {note.trigger for note in REGIME_NOTES}
        self.assertEqual(set(case_file._TRIGGERS), used)

    def test_the_two_emirate_sets_partition_the_emirates(self):
        """
        ⚠️ **مجموعتا الإمارات تقسمان ``EMIRATES`` بلا تداخل ولا نقص.**

        وقد وقع التداخل فعلاً: انطبقت ملاحظة النظام المحرَّر **وملاحظة
        الإمارات غير المحرَّرة** على قضية في الشارقة، فقرأ المحامي في تقرير
        واحد ملاحظتين متناقضتين — والتكرار هنا يُفقد التقرير كلّه الثمن.
        """
        noted = set(case_file._EMIRATES_WITH_FORUM_NOTES)
        unannotated = set(case_file._EMIRATES_WITHOUT_NOTES)
        self.assertEqual(noted & unannotated, set())
        self.assertEqual(noted | unannotated, set(EMIRATES))

    def test_a_sharjah_case_gets_one_emirate_note_not_two(self):
        """
        🔑 **والعيب بعد إصلاحه:** قضية الشارقة تُرجع **ملاحظة نطاق واحدة**.

        والفحص على **عدد ملاحظات باب الإمارة** لا على وجودها: التكرار هو
        العيب، والوجود هو الصواب.
        """
        case = CaseFile(
            country="الإمارات العربية المتحدة",
            emirate="الشارقة",
            forum="محكمة الشارقة الابتدائية",
            dispute_type=DisputeType.LEASE,
            stage=CaseStage.FIRST_INSTANCE,
            our_party=Party.DEFENDANT,
            claims=("رفض طلب الإخلاء",),
            key_dates=(),
            likely_law=(),
            has_arbitration_clause=False,
            has_choice_of_law=False,
        )
        emirate_notes = [
            note for note in regime_notes(case) if note.area is RegimeArea.EMIRATE
        ]
        self.assertEqual(len(emirate_notes), 1)
        self.assertEqual(emirate_notes[0].trigger, "other_emirates")

    def test_an_unrelated_case_does_not_get_dubai_or_free_zone_notes(self):
        """
        🔑 **القياس السالب:** القضية التي لا تخصّها ملاحظة لا تُرجعها.

        والفحص على **غياب** ملاحظات دبي وأبوظبي والمناطق الحرّة ومسار
        الوزارة من قضية إيجار في الشارقة — فظهور واحدة منها يعني جدولاً
        يوسم كل نزاع بملاحظات لا تخصّه.
        """
        case = CaseFile(
            country="الإمارات العربية المتحدة",
            emirate="الفجيرة",
            forum="محكمة الفجيرة الابتدائية",
            dispute_type=DisputeType.CIVIL,
            stage=CaseStage.FIRST_INSTANCE,
            our_party=Party.CLAIMANT,
            claims=("مطالبة مالية",),
            key_dates=(),
            likely_law=(),
            has_arbitration_clause=False,
            has_choice_of_law=False,
        )
        areas = {note.area for note in regime_notes(case)}
        self.assertEqual(areas, {RegimeArea.EMIRATE})
        self.assertNotIn(RegimeArea.FREE_ZONE, areas)
        self.assertNotIn(RegimeArea.EMPLOYMENT, areas)

    def test_the_arbitration_note_is_opened_by_the_clause_field(self):
        """
        ⚠️ **شرط التحكيم واقعة عن العقد لا عن الجهة**، فيُسأل عنه صريحاً.

        ولو استُنتج من نصّ الجهة وحدها لَما ظهرت الملاحظة في قضية أمام محكمة
        وفي عقدها شرط تحكيم — وهي الحالة التي يُدفع فيها بالشرط فيُغيَّر
        الاختصاص، وهي أكثر موضع وقع فيه «النصّ الصحيح في الموضع الخاطئ».
        """
        case = CaseFile(
            country="الإمارات العربية المتحدة",
            emirate="دبي",
            forum="محكمة دبي الابتدائية",
            dispute_type=DisputeType.COMMERCIAL,
            stage=CaseStage.FIRST_INSTANCE,
            our_party=Party.DEFENDANT,
            claims=("رفض المطالبة",),
            key_dates=(),
            likely_law=(),
            has_arbitration_clause=True,
            has_choice_of_law=False,
        )
        areas = {note.area for note in regime_notes(case)}
        self.assertIn(RegimeArea.ARBITRATION, areas)
        # والملاحظة معلَّقة على الحقل الصريح لا على نصّ الجهة.
        note = next(n for n in REGIME_NOTES if n.area is RegimeArea.ARBITRATION)
        self.assertIn("has_arbitration_clause", note.applies_to)

    def test_the_choice_of_law_note_is_opened_by_its_field_only(self):
        """
        ⚠️ **``has_choice_of_law`` لا يُقرأ من ``likely_law``.**

        فذاك **ترجيح المحامي** لا اتّفاق الطرفين. ولو فُتحت الملاحظة به
        لَظهرت في ملفٍّ لم يُختَر فيه قانون أصلاً، وصار التقرير يقول للمحامي
        «تحقّق من نطاق القانون المختار» ولا اختيار في العقد.
        """
        case = CaseFile(
            country="الإمارات العربية المتحدة",
            emirate="دبي",
            forum="محكمة دبي الابتدائية",
            dispute_type=DisputeType.COMMERCIAL,
            stage=CaseStage.FIRST_INSTANCE,
            our_party=Party.CLAIMANT,
            claims=("مطالبة",),
            key_dates=(),
            likely_law=("القانون الإنجليزي",),  # ترجيح بلا اتّفاق معلن
            has_arbitration_clause=False,
            has_choice_of_law=None,
        )
        areas = {note.area for note in regime_notes(case)}
        self.assertNotIn(RegimeArea.CHOICE_OF_LAW, areas)

    def test_the_table_states_it_is_a_checklist_not_a_legal_opinion(self):
        """
        ⚠️ التحذير مكتوب في **الكود** لا في وثيقة خارجية.

        لأن من يقرأ الجدول يقرأ الكود، والتحذير الذي يعيش في ملف آخر لا
        يُقرأ مع ما يحذّر منه — وهو الدرس نفسه في `labour_rules.py`.
        """
        source = pathlib.Path(case_file.__file__).read_text(encoding="utf-8")
        self.assertIn("للمحامي", source)
        self.assertIn("قائمة تحقّق", source)
        self.assertIn("ليس بياناً بالقانون", source)

    def test_the_notes_are_returned_in_table_order(self):
        """
        الترتيب ترتيب الجدول — وهو ترتيب الأولوية المعروض على المحامي.

        والفرز على موضع الملاحظة في ``REGIME_NOTES`` يُثبّته، فلا يتغيّر
        بتغيّر بنية الجدول الداخلية ولا بعدد الشروط.
        """
        positions = {id(note): index for index, note in enumerate(REGIME_NOTES)}
        for case in (_difc(), _abudhabi_labour(), _onshore_dubai()):
            with self.subTest(emirate=case.emirate, forum=case.forum):
                indexes = [positions[id(note)] for note in regime_notes(case)]
                self.assertEqual(indexes, sorted(indexes))

    def test_the_notes_summary_is_json_safe(self):
        """العرض صالح للبثّ — يُسلسَل بلا محوّل مخصّص."""
        payload = notes_summary(regime_notes(_abudhabi_labour()))
        text = json.dumps(payload, ensure_ascii=False)
        self.assertIn("employment", text)
        self.assertIsInstance(payload, list)
        for item in payload:
            self.assertEqual(
                set(item), {"area", "trigger", "note", "source", "limit"}
            )


# ==============================================================================
# ٤. الحصيلة — العرض والبثّ
# ==============================================================================


class TestSummaryAndShape(unittest.TestCase):
    """
    الحصيلة صالحة للبثّ، **والتصنيفات بقيمها الآلية** لا بأسمائها العربية.

    والفرق ليس شكلياً: الواجهة تُعيد ما بُثّ إلى نداء لاحق، فلو بُثّ
    ``"first_instance"`` كـ ``"المرحلة الابتدائية"`` لَما أمكن إعادة بنائه.
    """

    def test_the_summary_is_json_safe_and_uses_machine_values(self):
        """``summary`` تُسلسَل بـ ``json.dumps`` بلا محوّل، وبالقيم الآلية."""
        payload = _abudhabi_labour().summary()
        text = json.dumps(payload, ensure_ascii=False)
        self.assertIn("labour", text)
        self.assertIn("first_instance", text)
        self.assertEqual(payload["dispute_type"], "labour")
        self.assertEqual(payload["stage"], "first_instance")
        self.assertEqual(payload["our_party"], "claimant")

    def test_the_summary_carries_the_keys_and_the_missing_fields(self):
        """
        ⚠️ والمفاتيح في القصاصة **محسوبة لا محفوظة**.

        فلو حُفظت لَما تبعت تعديل الملف، و«هل تُصاغ المسودّة الآن» قرارٌ
        يُبنى عليها.
        """
        payload = _incomplete().summary()
        self.assertEqual(payload["emirate_key"], "")
        self.assertEqual(payload["forum_key"], "")
        self.assertFalse(payload["complete"])
        self.assertEqual(payload["blocking_missing"], ["emirate", "forum", "claims"])
        self.assertEqual(
            payload["confirmed"], ["dispute_type", "our_party", "country"]
        )

    def test_the_summary_lists_the_dates_as_pairs(self):
        """التواريخ (الوصف، التاريخ) — والوصف يبقى كما كُتب ليُقرأ."""
        payload = _abudhabi_labour().summary()
        self.assertEqual(
            payload["key_dates"], [["تاريخ انتهاء العلاقة", "2026-08-31"]]
        )

    def test_case_file_and_its_notes_are_frozen(self):
        """الملف والملاحظة لا يُعدَّلان بعد إنشائهما — فلا يتبدّل شيء أثناء تشغيل."""
        case = _onshore_dubai()
        with self.assertRaises(Exception):
            case.emirate = "الشارقة"  # type: ignore[misc]
        note = REGIME_NOTES[0]
        self.assertIsInstance(note, RegimeNote)
        with self.assertRaises(Exception):
            note.source = ""  # type: ignore[misc]


# ==============================================================================
# ٥. الوصلة بالحاسبة — العيب الرقمي (١٢٧٨ مقابل ١٣٠٧)
# ==============================================================================


class TestTheArithmeticDefectIsGroundedInTheCaseFile(unittest.TestCase):
    """
    🔑 **العيب الثالث في المراجعات: ١٢٧٨ يوماً والصحيح ١٣٠٧.**

    والرقم لا يأتي من معرفة ناقصة بل من **عدّ خاطئ**: يوم النهاية، أو فكّ
    تقويمي مكان عدّ الأيام. وتاريخا الطرفين **حقلان في ملف القضية**
    (``key_dates``) لا في المذكرة. فالاختبار هنا يثبّت أن العدّ في
    `labour_rules` — الموضع الواحد — يُعطي ١٣٠٧ لتاريخَي الواقعة.
    """

    def test_the_period_under_review_is_1307_not_1278(self):
        """
        🔑 من ٢٠٢٣-٠٢-٠١ إلى ٢٠٢٦-٠٨-٣١ = **١٣٠٧ أيام**، لا ١٢٧٨ ولا ١٣٠٨.

        ⚠️ والاختبار يفحص الرقم الخطأ **مصرَّحاً بأنه خطأ**، لا الصواب وحده:
        اختبارٌ يقول «١٣٠٧ صواب» يمرّ ولو عاد الرقم القديم في موضع آخر من
        المسار — أما فحص `assertNotEqual` فيسقط لحظة عودته.
        """
        start, end = date(2023, 2, 1), date(2026, 8, 31)
        self.assertEqual(period_days(start, end), 1307)
        self.assertNotEqual(period_days(start, end), 1278)
        self.assertNotEqual(period_days(start, end), 1308)

    def test_the_case_file_is_where_the_two_dates_are_recorded(self):
        """
        ⚠️ وتاريخا الطرفين **حقلان في الملف**، والعدّ يجري من الملف لا من
        نصّ المذكرة.

        وهذا هو أصل العلاج: العيب الذي وقع كان رقماً في المذكرة، ولو كان
        التاريخ الذي يُقاس عليه مُثبَتاً في الملف لَما اختلف العدّان.
        """
        case = _abudhabi_labour()
        labels = [label for label, _ in case.key_dates]
        self.assertIn("تاريخ انتهاء العلاقة", labels)
        self.assertIn("تاريخ انتهاء العلاقة", case_file.KEY_DATE_FIELDS)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
