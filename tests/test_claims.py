"""
اختبارات مصفوفة الطلبات والدفوع — أربعة أسئلة كانت تُخلط، وطلبٌ كان يُغفل.
=============================================================================

تشغيل::

    cd legal-brain
    python -m unittest tests.test_claims

وأو كامل السويت::

    cd legal-brain
    python -m unittest discover -s tests -t . -v

حتمية بالكامل: بلا شبكة، وبلا نموذج، وبلا قرص، وبلا طباعة. وهذا شرط لا تحسين،
لأن هذه المصفوفة يجب أن تُبنى في كل مرّة تُفتح فيها مسودّة، ولو احتاجت نداءً
لَما بُنيت.

⚠️ **ولماذا لا تحتاج `fake_deps`؟** لأن `claims` وحدة نقية بلا حالة وبلا
إدخال/إخراج، كـ `citations.py` و`case_file.py`: تُبنى مدخلاتها في الاختبار
ويُقرأ مخرَجها. فلا شيء يُستعار ولا شيء يُحاكى.

وأهمّ اختبارَين في هذا الملف
----------------------------
١. ``test_our_own_set_off_needs_documents`` — وهو **العيب التاريخي** الذي جاءت
   هذه الوحدة لمنعه: **الشركة** تمسّكت بخصم نصيب وسيط، **وطالبت الموظف بأن
   يُثبته**. وهذا قلبٌ لعبء الإثبات: من يتمسّك بواقعة هو المطالب بإثباتها.

٢. ``test_denying_the_entitlement_and_disputing_the_amount_are_different`` —
   وهو العيب الثاني: «نسلّم بأصل الاستحقاق وننازع في المقدار» و«ننكر
   الاستحقاق» دفعتان مختلفتان، ولا يجوز أن تُقرأ إحداهما مكان الأخرى.

⚠️ **والاختبارات تُبنى في هذا الملف لا تُنادَى من `claims`:** لو نادت بياناتِ
الوحدة ثم عُدّلت الوحدة، **لتغيّر الاختبار معها** فلم يعد يحرس شيئاً.
"""

import ast
import inspect
import json
import sys
import unittest

import claims
from case_file import CaseFile, CaseStage, DisputeType, Party
from facts import Fact, FactLedger, Standing

from claims import (
    AXIS_LABELS,
    AXIS_QUESTIONS,
    BURDEN_GROUND_MARKERS,
    BURDEN_LABELS,
    BURDEN_CARRYING_GROUNDS,
    CODE_FACT_ASSERTED_ONLY,
    CODE_MISSING_OUTCOME,
    CODE_NO_FACTS,
    CODE_OUR_GROUND_NEEDS_DOCUMENTS,
    CODE_STAGE_GROUND,
    CODE_SUGGESTED_NOT_ADOPTED,
    CODE_UNANSWERED,
    CODE_UNKNOWN_BURDEN,
    GATE_JURISDICTION,
    GATE_MARKERS,
    MERITS,
    PROCEDURAL_GATES,
    SEVERITY_ERROR,
    SEVERITY_NOTICE,
    STAGE_ACCEPTS,
    STAGE_PROHIBITS,
    SUGGESTION_NOTE,
    Burden,
    Claim,
    ClaimMatrix,
    Defence,
    DisputeAxis,
    Stage,
    burden_finding,
    burden_for,
    claimable_total,
    cross_check_facts,
    fact_checks,
    grounds_in_item,
    order_for_review,
    review_order_labels,
    stage_constraints,
    stage_of_case,
    stock_defences,
    suggested_only,
    summarize,
    unanswered,
    validate_for_stage,
)


# ==============================================================================
# بيانات الاختبار — قضية عمالية إماراتية، **مبنية هنا** لا مستعارة
# ==============================================================================
# ⚠️ والوقائع تُكتب بنصوصها كما تُكتب في ملف قضية حقيقي، لأن المطابقة في
# `claims` تجري على **النصّ المطبَّع**، ولو كتب الاختبار مفاتيح لاتينية لما
# فحص شيئاً من المطابقة العربية — وهي أكثر ما يُخطئ.

#: نصّ الطلب — وهو الطلب الذي أُغفل في المراجعات، فصار مادّة اختبار.
THE_CLAIM_LABEL = "مكافأة نهاية الخدمة عن مدّة الخدمة كاملة"

#: نصّ الدفع بالتقادم — فيه لفظ البوابة، فتُختبر المطابقة عليه.
THE_LIMITATION_LABEL = "الدفع بالتقادم: انقضاء ميعاد الدعوى العمالية"

#: نصّ دفع المقاصة — **والعيب التاريخي بنصّه**.
THE_SETOFF_LABEL = "الدفع بالخصم من المطالبة: يُخصم نصيب الوسيط من مبلغ المطالبة"

#: ما يقوله دفع المقاصة من تعليل — وفيه الموضع الثاني (الوسيط).
THE_SETOFF_RESPONSE = (
    "المطالبة لا تُقبل بمقدارها، إذ يُخصم منها نصيب الوسيط المتفق عليه."
)


def _claim(**changes) -> Claim:
    """
    طلبٌ كامل الحقول — والتغيير للتجارب يُمرَّر.

    ⚠️ والحقول الكاملة **مقصودة**: البناء الناقص يجعل كل اختبار يشتكي من نقص
    لا من العيب المقصود فحصه، فيضيع سبب الفشل.

    ⚠️ **والتغيير يُدمج في آخر القاموس**: لو مُرّر الحقل نفسه في ``changes``
    وفي القاعدة لَرفع بايثون ``TypeError`` عند التكرار — وهو خطأ في بناء
    الاختبار لا في الوحدة، فيُضيع على القارئ سببَ الفشل.
    """
    base = {
        "key": "end_of_service",
        "label": THE_CLAIM_LABEL,
        "claimed_by": Party.CLAIMANT,
        "elements": ("علاقة عمل", "انتهاء العلاقة", "مدّة خدمة معلومة"),
        "supporting_facts": ("service.ended",),
        "opposing_facts": (),
        "evidence": ("عقد العمل", "إخطار إنهاء العلاقة"),
        "axes_in_dispute": (DisputeAxis.QUANTUM,),
        "burden": Burden.ON_US,
        "response": "المكافأة مستحقّة، والنزاع في مقدارها لا في أصلها.",
        "outcome_sought": "إلزام المدّعى عليه بالمبلغ الصحيح بعد التصحيح.",
        "documents_required": ("عقد العمل", "كشف مدّة الخدمة"),
    }
    return Claim(**{**base, **changes})


def _defence(**changes) -> Defence:
    """دفعٌ كامل الحقول — بالبنية نفسها، وفرقٌ واحد: ``is_procedural``."""
    base = {
        "key": "limitation",
        "label": THE_LIMITATION_LABEL,
        "claimed_by": Party.DEFENDANT,
        "elements": ("ميعاد سارٍ", "انقضاؤه", "انتفاء سبب قاطع"),
        "supporting_facts": ("service.ended",),
        "opposing_facts": ("claim.filed",),
        "evidence": ("إخطار إنهاء العلاقة", "صحيفة الدعوى"),
        "axes_in_dispute": (DisputeAxis.EXISTENCE,),
        "burden": Burden.ON_US,
        "response": "انقضى ميعاد الدعوى، فتُرفض المطالبة شكلاً قبل الموضوع.",
        "outcome_sought": "عدم قبول الدعوى لانقضاء الميعاد.",
        "documents_required": ("إخطار إنهاء العلاقة المؤرّخ", "صحيفة الدعوى بتاريخها"),
        "is_procedural": True,
    }
    return Defence(**{**base, **changes})


def _setoff_defence(**changes) -> Defence:
    """
    🔑 **دفع المقاصة — وهو العيب التاريخي.**

    الشركة (موكّلنا) تمسّكت بخصم نصيب الوسيط، وفي المسودّة الأصلية طُلب من
    **الموظف** أن يُثبته. فالاختبار يبني هذا الدفع ويفحص أن الوحدة تُعلن أن
    **العبء علينا** وأن المستندات لازمة.

    ⚠️ **والتغيير يُمرَّر** لتفحص الصورة المُصلَحة أيضاً (بمستندات وبعبءٍ صحيح)
    — لأن الفحص الذي لا يُختبر على الصورة السليمة يصير إنذاراً دائماً.
    """
    base = {
        "key": "setoff",
        "label": THE_SETOFF_LABEL,
        "elements": ("دين متقابل", "اتّحاد الجنس", "مقدار الخصم"),
        "axes_in_dispute": (DisputeAxis.QUANTUM,),
        "burden": Burden.ON_OPPONENT,  # ⚠️ **وهو الخطأ**: كُتب على الخصم وهو علينا.
        "response": THE_SETOFF_RESPONSE,
        "outcome_sought": "خصم نصيب الوسيط من المبلغ المحكوم به.",
        "documents_required": (),  # 🔑 **فراغ مقصود**: وهو موضع الخطأ.
        "is_procedural": False,
    }
    return _defence(**{**base, **changes})


def _justice_claim(**changes) -> Claim:
    """طلبٌ على محور ``EXISTENCE`` وحده — أي **إنكارٌ للاستحقاق**، لا نزاعٌ في مقدار."""
    base = {
        "key": "no_entitlement",
        "label": "إنكار استحقاق المكافأة أصلاً لانقطاع علاقة العمل قبل استحقاقها",
        "axes_in_dispute": (DisputeAxis.EXISTENCE,),
        "burden": Burden.ON_OPPONENT,
        "response": "لا وجود للاستحقاق: العلاقة لم تبلغ المدّة التي ينشأ بها.",
        "outcome_sought": "رفض الدعوى لانعدام الاستحقاق.",
        "documents_required": ("كشف تواريخ علاقة العمل",),
    }
    return _claim(**{**base, **changes})


def _ledger() -> FactLedger:
    """
    سجلّ وقائع صغير — فيه واقعة **مسندة** وأخرى **مُدَّعاة**.

    ⚠️ والدرجتان مختلفتان عن قصد: `facts.py` يقوم على أن ``CLAIMED`` لا تُسند
    شيئاً. فلو كان السجلّ كله ``AGREED`` لَما فحص اختبار الإسناد شيئاً.
    """
    return FactLedger(
        (
            Fact(
                key="service.ended",
                statement="انتهت علاقة العمل بتاريخ ٢٠٢٦-٠٨-٣١",
                source="إخطار إنهاء العلاقة",
                locus="الصفحة ١",
                date="2026-08-31",
                asserted_by="الطرفان",
                standing=Standing.AGREED,
                quote="تنتهي علاقتك بالشركة اعتباراً من ٣١ أغسطس ٢٠٢٦",
                subject="service",
            ),
            # ⚠️ واقعة **ادّعاها الموكّل** — لا تُسند طلباً، وهي مادّة الاختبار.
            Fact(
                key="release.refused",
                statement="رفض الموظف التوقيع على مخالصة متضمّنة تنازلاً",
                source="مخالصة مؤرّخة ٢٠٢٤-٠٥-١٠",
                locus="الصفحة ٢",
                date="2024-05-10",
                asserted_by="الموكّل",
                standing=Standing.CLAIMED,
                quote="أرفض التوقيع على هذه المخالصة لاشتمالها على تنازل",
                subject="release",
            ),
        )
    )


def _matrix(**changes) -> ClaimMatrix:
    """
    المصفوفة الأساس: طلبٌ موضوعيّ، ودفع تقادم إجرائيّ، ودفع مقاصة.

    ⚠️ والترتيب في ``claims`` **مقلوب عن قصد** (الموضوع قبل الإجرائي)، ليكون
    اختبار الترتيب فاحصاً للفرز لا صادفاً ترتيباً صحيحاً في الإدخال.
    """
    base = {
        "claims": (_claim(),),
        "defences": (_setoff_defence(), _defence()),
        "stage": Stage.FIRST_INSTANCE,
        "our_party": Party.DEFENDANT,
    }
    return ClaimMatrix(**{**base, **changes})


def _cassation_evidence_ground(**changes) -> Defence:
    """
    وجهٌ **يطعن في تقدير الدليل** — وهو ما لا تقبله مرحلة التمييز.

    ⚠️ والوجه مكتوب بصياغته الواقعية («لم تعطِ المحكمة وزنًا للدليل») لا
    بلفظ مجرّد، لأن المطابقة على الألفاظ كما تُكتب في الأوراق.
    """
    base = {
        "key": "cassation_evidence",
        "label": "الطعن بأن المحكمة لم تزن الدليل ولم تعطه وزنه",
        "axes_in_dispute": (DisputeAxis.PROOF,),
        "response": (
            "أخطأت المحكمة في تقدير الدليل، ولم تزن البينة وزناً صحيحاً، فجاء "
            "حكمها على خلاف ما استخلصته."
        ),
        "outcome_sought": "نقض الحكم والإحالة.",
        "documents_required": ("الحكم المطعون فيه",),
        "is_procedural": False,
    }
    return _defence(**{**base, **changes})


def _axes_of(matrix: ClaimMatrix, key: str) -> tuple[str, ...]:
    """محاور عنصرٍ بعينه — مساعدة قراءة، لا منطق إضافي."""
    item = matrix.of_key(key)
    assert item is not None, f"لا عنصر بالمفتاح {key!r}"
    return tuple(axis.value for axis in item.axes_in_dispute)


def _any_axis_item(matrix: ClaimMatrix, axis: DisputeAxis) -> list[str]:
    """مفاتيح العناصر التي تُنازَع على محورٍ بعينه."""
    return [item.key for item in matrix.items if axis in item.axes_in_dispute]


def _codes(findings) -> list[str]:
    """رموز الأحكام — تُقارَن الرموز لا النصوص، فالنصّ يتغيّر والرمز يثبت."""
    return [
        finding["code"] if isinstance(finding, dict) else finding.code
        for finding in findings
    ]


def _finding_for(findings, key: str):
    """
    أوّل حكمٍ على عنصرٍ بعينه، أو ``None``.

    ⚠️ **وتقبل الأحكام بالصورتين** — كائنَ ``Finding`` وقاموسَ المخرَج
    المبثوث. والسبب أن بعض الفحوص تُختبر على **نتيجة الدالّة** (وهي كائنات)
    وبعضها على **ما يُبثّ** (وهو قواميس)، وسؤالٌ واحد بصيغتين أهون من سؤالين
    يفترقان.
    """
    for finding in findings:
        if isinstance(finding, dict):
            if finding.get("item_key") == key:
                return finding
        elif finding.item_key == key:
            return finding
    return None


def _case(**changes) -> CaseFile:
    """ملف قضية عمالية في أبوظبي — مبنيّ هنا لا مستعار من `case_file`."""
    base = dict(
        country="الإمارات العربية المتحدة",
        emirate="أبوظبي",
        forum="محكمة أبوظبي الابتدائية",
        dispute_type=DisputeType.LABOUR,
        stage=CaseStage.FIRST_INSTANCE,
        our_party=Party.DEFENDANT,
        claims=(THE_CLAIM_LABEL,),
        key_dates=(("تاريخ انتهاء العلاقة", "2026-08-31"),),
        likely_law=("المرسوم بقانون اتحادي ٣٣ لسنة ٢٠٢١",),
        has_arbitration_clause=False,
        has_choice_of_law=False,
    )
    base.update(changes)
    return CaseFile(**base)


# ==============================================================================
# ١. المحاور الأربعة — وهي التي كانت تُخلط
# ==============================================================================


class TestTheFourAxesAreKeptApart(unittest.TestCase):
    """
    🔑 **«أصل الاستحقاق» و«المقدار» و«الحلول» و«الإثبات» — أربعة أسئلة لا سؤال.**

    وهذا أصل العيب الثاني: الصياغة كانت تجيب عن أحدها وتُقرأ كأنها أجابت عن
    الأربعة. والفصل هنا **بتصنيف مغلق** لا بنصيحة في تعليق، لأن ما لا يُصنَّف
    لا يُفحَص.
    """

    def test_denying_the_entitlement_and_disputing_the_amount_are_different(self):
        """
        🔑 **إنكارُ الاستحقاق ونزاعُ المقدار دفعتان مختلفتان — ولا تُقرأ إحداهما مكان الأخرى.**

        ⚠️ وهذا العيب بعينه: مسودّة تقول «لا يستحقّ» وكاتبها أراد «يستحقّ
        أقلّ». الأولى تُسقط المطالبة كلها، والثانية تُسقط منها بمقدار — ولكلٍّ
        عبءٌ ونتيجة. فالمطلوب أن يُسجَّل النزاع على محوره، وأن يظهر الافتراق
        **في المصفوفة** لا في نيّة الكاتب.
        """
        denying = ClaimMatrix(
            claims=(_justice_claim(),), stage=Stage.FIRST_INSTANCE,
            our_party=Party.DEFENDANT,
        )
        disputing = ClaimMatrix(
            claims=(_claim(),), stage=Stage.FIRST_INSTANCE,
            our_party=Party.DEFENDANT,
        )

        self.assertEqual(_axes_of(denying, "no_entitlement"), ("existence",))
        self.assertEqual(_axes_of(disputing, "end_of_service"), ("quantum",))

        # ⚠️ **ولا يُبلَّغ أحدهما عن الآخر:** عنصرٌ على محور لا يُحتسب على غيره.
        self.assertIn("no_entitlement", _any_axis_item(denying, DisputeAxis.EXISTENCE))
        self.assertNotIn("no_entitlement", _any_axis_item(denying, DisputeAxis.QUANTUM))
        self.assertIn("end_of_service", _any_axis_item(disputing, DisputeAxis.QUANTUM))
        self.assertNotIn(
            "end_of_service", _any_axis_item(disputing, DisputeAxis.EXISTENCE)
        )

    def test_one_claim_can_record_several_axes_at_once(self):
        """
        المطالبة الواحدة تُنازَع على **أكثر من محور** — وهذا هو الأصل لا الاستثناء.

        «نسلّم بأصل الاستحقاق وننازع في المقدار والاستحقاق لم يحلّ» كلامٌ صحيح
        ومتكرّر، فلو كان الحقل قيمةً واحدة لسقط أحد المحورين **صامتاً** — وهذا
        هو العيب نفسه بصورة أخرى.
        """
        both = ClaimMatrix(
            claims=(
                _claim(
                    axes_in_dispute=(DisputeAxis.QUANTUM, DisputeAxis.DUE),
                    response="المكافأة مستحقّة، والنزاع في مقدارها وفي حلول أجلها.",
                ),
            ),
            our_party=Party.DEFENDANT,
        )

        self.assertEqual(_axes_of(both, "end_of_service"), ("quantum", "due"))
        payload = summarize(both)
        self.assertEqual(payload["by_axis"]["quantum"], 1)
        self.assertEqual(payload["by_axis"]["due"], 1)
        self.assertEqual(payload["by_axis"]["existence"], 0)

    def test_every_axis_has_a_label_and_the_question_it_answers(self):
        """
        ⚠️ **والمحور بلا سؤاله يُخلط بغيره في الصياغة.**

        فالفرق بين المحاور يُنسى عملياً، ولا يثبت إلا بأن يُعرض مع كل محور
        **السؤال الذي يجيب عنه**: «الاستحقاق قائم، فما مقداره؟» تُفرّق بين
        نزاع المقدار ونزاع الأصل حيث لا تُفرّق التسمية وحدها.
        """
        for axis in DisputeAxis:
            with self.subTest(axis=axis.value):
                self.assertTrue(AXIS_LABELS.get(axis.value, "").strip())
                self.assertTrue(AXIS_QUESTIONS.get(axis.value, "").strip())
        self.assertEqual(len(AXIS_LABELS), len(list(DisputeAxis)))
        self.assertEqual(len(AXIS_QUESTIONS), len(list(DisputeAxis)))


# ==============================================================================
# ٢. العبء — والعيب التاريخي
# ==============================================================================


class TestBurden(unittest.TestCase):
    """
    **من يتمسّك بواقعة هو المطالب بإثباتها** — لا من بدأ الخصومة.

    ⚠️ وهذا هو الأصل الذي خالفه العيب التاريخي: الشركة تمسّكت بخصمٍ، وطُلب
    من الموظف أن يُثبته. فالمصفوفة تُعلن العبء **حيث يجب أن يكون**، لا حيث
    كُتب.
    """

    def test_a_claim_advanced_by_a_party_carries_that_partys_burden(self):
        """
        القاعدة الأولى: من ادّعى حمل عبء ما ادّعاه.

        والفحص يقع **بالتبادل**: الطلب نفسه عبؤه علينا إن كنّا المدّعين،
        وعلى الخصم إن كنّا المدّعى عليهم — فالقاعدة على **من تمسّك** لا على
        صفة الطلب في ذاته.
        """
        claim = _claim()
        self.assertIs(burden_for(claim, Party.CLAIMANT), Burden.ON_US)
        self.assertIs(burden_for(claim, Party.DEFENDANT), Burden.ON_OPPONENT)

    def test_our_own_set_off_needs_documents(self):
        """
        🔑 **العيب التاريخي: تمسّكنا بالخصم وطلبنا من الخصم أن يُثبته.**

        كانت الشركة تخصم نصيب وسيط، **وطالبت الموظف بإثبات نصيب الوسيط**.
        وهذا قلبٌ لعبء الإثبات: من يتمسّك بخصمٍ أو سدادٍ أو تنازلٍ **هو**
        المطالب بدليله. فالفحص هنا: العبء **علينا**، و``documents_required``
        فارغ ⇒ **خطأ** لا ملاحظة، لأن الأثر ليس نقصاً في البيان بل حجّة لا
        وجود لها نُقلت تبعتها إلى الخصم.
        """
        defence = _setoff_defence()
        matrix = ClaimMatrix(
            claims=(_claim(),),
            defences=(defence,),
            our_party=Party.DEFENDANT,
        )

        # المفتاح: قرأنا اللفظ فقلبنا العبء.
        self.assertEqual(grounds_in_item(defence), ("setoff", "intermediary"))
        self.assertIs(burden_for(defence, Party.DEFENDANT), Burden.ON_US)

        finding = burden_finding(defence, Party.DEFENDANT)
        self.assertIsNotNone(finding, "التمسّك بالخصم بلا مستند يجب أن يُنذر")
        assert finding is not None
        self.assertEqual(finding.code, CODE_OUR_GROUND_NEEDS_DOCUMENTS)
        self.assertEqual(finding.severity, SEVERITY_ERROR)

        # ⚠️ **وإعلان الافتراق بين ما كُتب وما يجب:** «العبء على الخصم» في
        # المصفوفة هو الخطأ نفسه، فلا يمرّ بلا إعلان.
        payload = summarize(matrix)
        self.assertIn(
            CODE_OUR_GROUND_NEEDS_DOCUMENTS,
            [entry["code"] for entry in payload["findings"]],
        )
        self.assertFalse(payload["clean"])
    def test_the_same_set_off_with_documents_is_no_longer_an_error(self):
        """
        ⚠️ **وإصلاح العيب يُسقط الإنذار — وإلا صار إنذاراً دائماً لا يُقرأ.**

        وهذا هو الوجه الآخر للفحص: العيب **مقدارُه المستند**، لا التمسّك
        بذاته. فمن عبّأ ``documents_required`` لم يبقَ عليه عيب — وهذا شرط
        ألّا يتحوّل التقرير إلى ضجيج يُتجاهَل.
        """
        fixed = _setoff_defence(
            documents_required=(
                "كشف حساب يُثبت تحويل نصيب الوسيط",
                "اتّفاق الوساطة الموقّع",
            ),
            burden=Burden.ON_US,
        )
        matrix = ClaimMatrix(
            claims=(_claim(),), defences=(fixed,), our_party=Party.DEFENDANT
        )

        self.assertIsNone(burden_finding(fixed, Party.DEFENDANT))
        payload = summarize(matrix)
        self.assertNotIn(
            CODE_OUR_GROUND_NEEDS_DOCUMENTS,
            [entry["code"] for entry in payload["findings"]],
        )

    def test_a_gap_of_burden_is_a_notice_and_is_not_read_as_no_burden(self):
        """
        ⚠️ **``UNKNOWN`` ليست ``ON_NEITHER``**، و«لا أعرف» ليست «لا عبء».

        والخلط بينهما هو العيب المكتوب في `case_file.py` عند الفرق بين
        ``False`` و``None``: من لم يُحدَّد عبؤه يُسأل، ومن قيل إن العبء لا يقع
        على أحد فقد أُجيب عنه بغير سؤال.
        """
        unknown = _claim(burden=Burden.UNKNOWN)
        matrix = ClaimMatrix(claims=(unknown,), our_party=Party.DEFENDANT)

        payload = summarize(matrix)
        entry = _finding_for(payload["findings"], "end_of_service")
        self.assertIsNotNone(entry)
        assert entry is not None
        self.assertEqual(entry["code"], CODE_UNKNOWN_BURDEN)
        # ⚠️ **ملاحظة لا خطأ:** «لم يُحدَّد» نقصٌ يُسأل عنه، وليس عيباً يمنع
        # تسليم مصفوفة سليمة في كل ما عدا هذا الحقل.
        self.assertEqual(entry["severity"], SEVERITY_NOTICE)
        self.assertEqual(payload["by_severity"][SEVERITY_NOTICE], 1)

    def test_a_claim_we_raise_ourselves_needs_documents_even_without_a_carrying_ground(self):
        """
        ⚠️ **والفراغ عيبٌ في كل موضع يكون العبء فيه علينا** — لا في المواضع
        المنقولة وحدها.

        الشرط ``documents_required`` غير فارغ حين يكون العبء علينا هو شرط
        عامّ؛ والمواضع المنقولة (خصم، سداد، وسيط، تنازل) تُشدّد الحكم لأن
        العيب فيها **تاريخي وواقع**، لا لأنها الوحيدة المعنية.
        """
        # ⚠️ ولا لفظ لموضعٍ منقول هنا، فالعبء على من ادّعى.
        bare = _claim(documents_required=())
        self.assertIsNone(
            burden_finding(bare, Party.CLAIMANT),
            "لا موضع منقول هنا — فالإنذار من `burden_finding` ليس موضعه",
        )
        self.assertIs(burden_for(bare, Party.CLAIMANT), Burden.ON_US)
        self.assertFalse(bare.documents_required)


# ==============================================================================
# ٣. الترتيب — الإجراء قبل الموضوع
# ==============================================================================


class TestProceduralGatesComeFirst(unittest.TestCase):
    """
    ⚠️ **الاختصاص، فالقبول، فالتقادم، فالصفة، فالإجراء — ثم الموضوع.**

    ولماذا؟ لأن كل بوابة **يترتّب على فواتها أثر لا يُتدارك بالحكم في
    الموضوع**: الحكم من محكمة غير مختصّة باطل ولو كان صواباً. **فالدفع في
    الموضوع قبل هذه البوابات دفعٌ في الترتيب الخطأ** — يُتعَب فيه ثم يُقال
    إن المحكمة لا تنظر الدعوى.
    """

    def test_procedural_gates_come_before_the_merits(self):
        """
        🔑 **العنصر الإجرائي يُقدَّم على عنصر الموضوع دائماً** — ولو كان
        ترتيب الإدخال معكوساً.

        والمصفوفة في الاختبار تُدخَل **موضوعاً ثم إجرائياً** عن قصد: لو جاء
        الترتيب صحيحاً بمصادفة ترتيب الإدخال لَما فحص الاختبار فرزاً.
        """
        ordered = order_for_review(_matrix())
        self.assertEqual(
            [item.key for item in ordered], ["limitation", "end_of_service", "setoff"]
        )

        # ⚠️ والفحص **على المواضع** لا على القائمة، ليكون صالحاً لأي مصفوفة:
        # كل إجرائي قبل كل موضوعي. والموضوعيان هنا **لا بوابة لهما**، فيحفظان
        # ترتيب الإدخال (والفرز مستقرّ) — وهذا هو الترتيب المقصود.
        positions = {item.key: index for index, item in enumerate(ordered)}
        self.assertLess(positions["limitation"], positions["end_of_service"])
        self.assertLess(positions["limitation"], positions["setoff"])

    def test_jurisdiction_and_limitation_precede_every_merits_item(self):
        """
        🔑 والاختصاص والتقادم **قبل كل** عنصر موضوعي.

        والفرق بينهما: الاختصاص **قبل** التقادم، لأن ما بعده يُبحث بعد أن
        يثبت أن هذه الجهة تنظر أصلاً.
        """
        matrix = ClaimMatrix(
            claims=(_claim(key="merits_two", label="طلب تعويض عن فصل تعسّفي"), _claim()),
            defences=(
                _defence(
                    key="jurisdiction",
                    label="الدفع بعدم اختصاص المحكمة",
                    response="المحكمة غير مختصّة نوعياً بنظر هذا النزاع.",
                    is_procedural=True,
                ),
                _defence(),
            ),
            our_party=Party.DEFENDANT,
        )
        ordered = [item.key for item in order_for_review(matrix)]

        self.assertEqual(ordered[0], "jurisdiction")
        self.assertEqual(ordered[1], "limitation")
        merits_positions = [
            index
            for index, key in enumerate(ordered)
            if key in ("end_of_service", "merits_two")
        ]
        self.assertEqual(len(merits_positions), 2)
        self.assertGreater(min(merits_positions), ordered.index("limitation"))
        self.assertGreater(min(merits_positions), 0)

    def test_a_procedural_defence_not_marked_as_such_is_still_ordered_as_a_gate(self):
        """
        ⚠️ **والاحتياط يعمل:** دفعٌ إجرائيّ لم يُوسَم ``is_procedural`` يُقرأ
        بلفظه فلا يقع في آخر الترتيب مع الموضوع.

        والسبب أن العيب الذي وُجد الترتيب لمنعه هو **أن يُبنى في الموضوع قبل
        فحص البوابة**، ولو وقع ذلك بسبب حقلٍ لم يُمتلأ لَكان العيب قائماً.
        """
        unmarked = _defence(is_procedural=False)  # ⚠️ وسمٌ خاطئ مقصود
        self.assertTrue(any(
            marker in unmarked.label for marker in GATE_MARKERS["limitation"]
        ))
        matrix = ClaimMatrix(
            claims=(_claim(),), defences=(unmarked,), our_party=Party.DEFENDANT
        )
        ordered = [item.key for item in order_for_review(matrix)]
        self.assertEqual(ordered[0], "limitation")

    def test_the_order_keeps_every_item_and_is_stable(self):
        """
        ⚠️ **والترتيب لا يُسقط عنصراً**: العنصر الذي لا يُسند إلى بوابة يبقى
        في المخرَج موضوعاً في آخره.

        ولماذا هذا شرط؟ لأن العنصر المحذوف من الترتيب **عنصر ضائع**، والحذف
        هو العيب الأول الذي جاءت هذه الوحدة لمنعه: طلبات تُغفل ولا يعرف أحد.
        """
        matrix = _matrix()
        ordered = order_for_review(matrix)
        self.assertEqual(len(ordered), len(matrix.items))
        self.assertEqual({item.key for item in ordered}, {item.key for item in matrix.items})

        # إعادة الترتيب على مخرَج مرتّب تُعطي الترتيب نفسه (ثبات).
        self.assertEqual(
            [item.key for item in order_for_review(matrix)],
            [item.key for item in ordered],
        )
        self.assertEqual(review_order_labels(matrix), ("التقادم", "الموضوع"))

    def test_the_gate_table_is_ordered_and_complete(self):
        """
        ⚠️ **والترتيب في ثابت واحد** — ولو كان له مصدران لافترقا.

        والاختصاص أوّلها، والاختصاص مفرد في ثابتٍ باسمه لأن أكثر من موضع
        يقرؤه.
        """
        self.assertEqual(PROCEDURAL_GATES[0], GATE_JURISDICTION)
        self.assertEqual(
            list(PROCEDURAL_GATES),
            ["jurisdiction", "admissibility", "limitation", "standing", "procedure"],
        )
        for gate in PROCEDURAL_GATES:
            with self.subTest(gate=gate):
                self.assertTrue(GATE_MARKERS.get(gate), f"بوابة بلا ألفاظ: {gate}")
        self.assertNotIn(MERITS, PROCEDURAL_GATES)


# ==============================================================================
# ٤. الاقتراح ليس دفعاً — والوحدة لا تُضيف شيئاً
# ==============================================================================


class TestSuggestionsAreNeverPleadings(unittest.TestCase):
    """
    ⚠️ **الدفع بلا واقعة تُسنده يُسقط نفسه، ويُفقد الدفوع السليمة وزنها معه.**

    فالقرار في هذه الوحدة: **لا يُضاف دفعٌ واحد** إلى أيّ مصفوفة. والاقتراح
    مخرَج منفصل، وموسوم في **كل** بند منه لا في ترويسة المخرَج — لأن الترويسة
    تُقرأ مرّة والاقتراح يُنسخ منفرداً.
    """

    def test_no_defence_is_added_by_the_module(self):
        """
        🔑 **بناء المصفوفة لا يُضيف دفعاً لم يُمرَّر** — ولا الاقتراح ولا
        الفحص ولا العرض.
        """
        supplied = _matrix()
        before = tuple(item.key for item in supplied.defences)

        # كل الدوال التي تلمس المصفوفة — ولا واحدة منها تُعدّلها.
        order_for_review(supplied)
        summarize(supplied, ledger=_ledger(), draft="", stage=Stage.CASSATION)
        suggested_only(supplied, Stage.CASSATION)
        stock_defences(Stage.CASSATION)

        self.assertEqual(tuple(item.key for item in supplied.defences), before)
        self.assertEqual(before, ("setoff", "limitation"))

    def test_suggestions_are_separate_and_labelled_in_the_output(self):
        """
        ⚠️ **والوسم بياناتٌ في الخرج لا نصيحةٌ في تعليق:** ``prompt_only`` في
        كل بند، وعبارة التحذير معه.

        ومن قرأ المخرَج في واجهة أو في JSON **يجب أن يرى** أنه ليس pleading،
        والاقتراح الذي يُقرأ دفعاً مرفوعاً هو الطريق إلى دفعٍ بلا واقعة.
        """
        matrix = _matrix()
        suggestions = suggested_only(matrix, Stage.CASSATION)

        self.assertTrue(suggestions, "التمييز له دفوع متاحة بلا شك")
        for suggestion in suggestions:
            with self.subTest(key=suggestion.key):
                self.assertTrue(suggestion.prompt_only)
                self.assertEqual(suggestion.note, SUGGESTION_NOTE)
                self.assertTrue(suggestion.facts_required)
                self.assertTrue(suggestion.documents_required)
        # ⚠️ **وما تبنّيناه لا يُقترح:** عرضُ المرفوع اقتراحاً يُرفع مرّتين.
        self.assertNotIn("limitation", [item.key for item in suggestions])

    def test_the_suggestions_never_enter_the_findings_as_errors(self):
        """
        ⚠️ الاقتراح غير المتبنّى **ملاحظة لا خطأ** — على قاعدة `review.py`.

        ولو وُسم خطأً لمنع تسليم مصفوفة سليمة، فتُهمَل معه الأخطاء الحقيقية
        حين تظهر — وهذا هو الدرس الذي دُفع ثمنه في `language_audit.py`.
        """
        payload = summarize(
            _matrix(),
            suggestions=suggested_only(_matrix(), Stage.CASSATION),
        )
        entries = [
            entry for entry in payload["findings"]
            if entry["code"] == CODE_SUGGESTED_NOT_ADOPTED
        ]
        self.assertTrue(entries)
        for entry in entries:
            self.assertEqual(entry["severity"], SEVERITY_NOTICE)
        # ⚠️ **والاقتراح وحده لا يُنتج خطأً:** مصفوفةٌ كل عناصرها سليمة تبقى
        # نظيفة ومعها اقتراحات — ولو وُسم الاقتراح خطأً لمنع تسليمها.
        payload_clean = summarize(ClaimMatrix(our_party=Party.DEFENDANT))
        self.assertTrue(payload_clean["clean"])
        self.assertNotEqual(
            summarize(
                _matrix(),
                suggestions=suggested_only(_matrix(), Stage.FIRST_INSTANCE),
            )["suggested_defences"],
            [],
        )

    def test_stock_defences_name_the_facts_they_require(self):
        """
        ⚠️ **والبند الذي لا يذكر ما يلزمه ليس اقتراحاً بل تلقيناً.**

        الفرق بين الاثنين هو الحقلان ``facts_required`` و``documents_required``:
        من قرأ أن الدفع يحتاج واقعةً ليست في ملفه **لم يرفعه** — وهذا هو
        الغرض الحقيقي من الجدول.
        """
        for stage in Stage:
            with self.subTest(stage=stage.value):
                for suggestion in stock_defences(stage):
                    self.assertTrue(suggestion.facts_required)
                    self.assertTrue(suggestion.documents_required)
                    self.assertEqual(suggestion.stage, stage.value)

    def test_the_stock_list_is_small_and_closed(self):
        """
        ⚠️ **والقائمة قصيرة عن قصد:** الطويلة تُقرأ قائمة دفوع جاهزة فيُنسخ
        منها، والقصيرة تُقرأ سؤالاً.

        والحدّ المكتوب هنا حارس على **التوسّع**: من أراد أن يزيد بنداً مرّ
        بهذا الحدّ فرأى أنه يُوسّع، ولم يزد بنداً صامتاً.
        """
        self.assertLessEqual(len(claims._STOCK_DEFENCES), 16)
        # ⚠️ **ولكل بند مرحلةٌ واحدة على الأقل يوجد فيها** — فلا بند ميتاً
        # لا يظهر في أيّ مرحلة، وهو عيب صامت من جنس ما كشفه `test_module_health`.
        for entry in claims._STOCK_DEFENCES:
            with self.subTest(key=entry["key"]):
                self.assertTrue(entry["stages"])


# ==============================================================================
# ٥. المرحلة — ما تقبله وما تمنعه
# ==============================================================================


class TestStageConstraints(unittest.TestCase):
    """
    ⚠️ **والمرحلة لا تُغيّر الوقائع، بل تُغيّر ما يجوز أن يُقال.**

    وهذا ما جُعل **بيانات** لا نثراً: القيد الذي يعيش في تعليق لا يُفحَص،
    والقيد الذي يعيش في جدول يُفحص على كل عنصر.
    """

    def test_cassation_cannot_attack_the_weighing_of_evidence(self):
        """
        🔑 **التمييز محكمة قانون لا محكمة وقائع** — فلا يُطعن فيه بتقدير
        الدليل.

        ⚠️ والوجه نفسه **يُقبل في الاستئناف**، لأن الاستئناف مراجعةٌ للموضوع
        لا نظرٌ في القانون وحده. فالفحص على **المرحلتين معاً**، وإلا لَكان
        الاختبار فاحصاً مفتاحاً في جدول لا قاعدةً مرحلية.
        """
        ground = _cassation_evidence_ground()

        violations = validate_for_stage(ground, Stage.CASSATION)
        self.assertEqual([item.rule for item in violations], ["attacks_evidence_weighing"])
        self.assertEqual(violations[0].stage, Stage.CASSATION.value)
        self.assertEqual(violations[0].kind, "defence")
        # ⚠️ والألفاظ التي أوقعت المطابقة تُعرض ليُرى سبب الإنذار.
        self.assertIn("تقدير الدليل", violations[0].note)

    def test_the_same_attack_on_the_evidence_is_admitted_on_appeal(self):
        """
        🔑 **والوجه نفسه يُقبل في الاستئناف** — وهذا هو الفرق بين المرحلتين.

        لو مُنع الطعن في تقدير الدليل في **كل** مرحلة لَكان الجدول قيداً واحداً
        لا يفرّق بين مستند ومستند؛ ولو قُبل في التمييز لَصار التمييز محكمة
        وقائع. فالمقابلة بين المرحلتين هي الفحص، لا الفحص على التمييز وحده.
        """
        ground = _defence(
            key="appeal_evidence",
            label="الاستئناف على تقدير الدليل: لم تزن المحكمة البينة",
            # ⚠️ ولا لفظ «وقائع جديدة» هنا، لأن ما يُختبر هو **تقدير الدليل**
            # وحده — وإلا لفحص الاختبار وجهاً آخر فمرّ لسبب غير سببه.
            response="لم تزن المحكمة البينة وزناً صحيحاً، فجاء حكمها على غير أساس.",
            axes_in_dispute=(DisputeAxis.PROOF,),
            documents_required=("الحكم المستأنف",),
            is_procedural=False,
        )
        self.assertEqual(validate_for_stage(ground, Stage.CASSATION)[0].rule,
                         "attacks_evidence_weighing")
        self.assertEqual(
            validate_for_stage(ground, Stage.APPEAL),
            (),
            "الاستئناف مراجعةٌ للموضوع، فيقبل الطعن في وزن الدليل",
        )

    def test_a_cassation_ground_on_a_point_of_law_passes(self):
        """
        ⚠️ **والوجه الصحيح يمرّ:** خطأٌ في تطبيق القانون هو ما يُقبل في التمييز.

        ولو لم يمرّ لَكانت الأداة تُنذر دائماً — **وأداة تُنذر دائماً لا
        تُنذر أبداً**.
        """
        law_ground = _defence(
            key="cassation_law",
            label="الطعن بمخالفة القانون: أخطأت المحكمة في تطبيق المادة ٤٢",
            response=(
                "طبّقت المحكمة نصاً لا ينطبق على واقعة الدعوى، فأخطأت في "
                "تطبيق القانون."
            ),
            axes_in_dispute=(DisputeAxis.EXISTENCE,),
            documents_required=("الحكم المطعون فيه",),
            is_procedural=False,
        )
        self.assertEqual(validate_for_stage(law_ground, Stage.CASSATION), ())

    def test_the_prohibited_thing_differs_by_stage(self):
        """
        ⚠️ **وما تمنعه كل مرحلة يختلف:** الوقائع الجديدة في الاستئناف، وتقدير
        الدليل في التمييز، وأصل الحقّ في التنفيذ، ونطاق الشرط في التحكيم.

        والفحص يُثبت **الاختلاف** لا وجود قيد: القيد الواحد لكل المراحل كان
        سيُقرأ جدولاً واحداً فلا يفرّق بين مستند ومستند.
        """
        reargue = _defence(
            key="appeal_reargue",
            label="الاستئناف على وقائع جديدة لم تبحثها المحكمة",
            response="لم تبحث المحكمة الوقائع الجديدة ولم تنظر فيها.",
            is_procedural=False,
        )
        self.assertEqual(
            [item.rule for item in validate_for_stage(reargue, Stage.APPEAL)],
            ["reargues_the_facts"],
        )
        # ⚠️ والابتدائي لا يمنعه: الموضوع مفتوح فيه.
        self.assertEqual(validate_for_stage(reargue, Stage.FIRST_INSTANCE), ())

        execution = _defence(
            key="execution_right",
            label="المنازعة في أصل الحقّ المحكوم به",
            response="الحقّ المحكوم به غير ثابت في أصله.",
            is_procedural=True,
        )
        self.assertEqual(
            [item.rule for item in validate_for_stage(execution, Stage.EXECUTION)],
            ["execution_disputes_the_execution"],
        )
        self.assertEqual(validate_for_stage(execution, Stage.FIRST_INSTANCE), ())

    def test_a_stage_ground_is_an_error_in_the_summary(self):
        """
        ⚠️ **والوجه الذي لا تقبله المرحلة خطأ يمنع التسليم** — لا ملاحظة.

        لأن الأثر ليس «انظر في الأمر» بل **وجهٌ ساقط لا يُعتدّ به**: من أودعه
        مذكرةً فقد كتب ما لا يُقال في هذه المرحلة.
        """
        matrix = ClaimMatrix(
            claims=(_claim(),),
            defences=(_cassation_evidence_ground(),),
            stage=Stage.CASSATION,
            our_party=Party.DEFENDANT,
        )
        payload = summarize(matrix, stage=Stage.CASSATION)
        entry = _finding_for(payload["findings"], "cassation_evidence")
        self.assertIsNotNone(entry)
        assert entry is not None
        self.assertEqual(entry["code"], CODE_STAGE_GROUND)
        self.assertEqual(entry["severity"], SEVERITY_ERROR)
        self.assertFalse(payload["clean"])

    def test_every_stage_declares_what_it_accepts_and_what_it_prohibits(self):
        """
        ⚠️ **ومرحلةٌ لها ما تقبله بلا ما تمنعه تُنتج قيداً نصفُه غائب** — وهو
        أسوأ من غيابه كله لأن نصفه يُقرأ كمالاً.

        ولماذا يُفحص الجدولان؟ لأن ما تقبله المرحلة وما تمنعه **بيانات**،
        والبيانات الناقصة لا تُنذر: تُقرأ سطراً ناقصاً ولا شيء يشكو.
        """
        self.assertEqual(set(STAGE_ACCEPTS), set(STAGE_PROHIBITS))
        self.assertEqual(set(STAGE_ACCEPTS), set(Stage))
        for stage in Stage:
            with self.subTest(stage=stage.value):
                lines = stage_constraints(stage)
                self.assertGreaterEqual(len(lines), 3)
                self.assertTrue(lines[0].startswith("المرحلة:"))
        self.assertEqual(len(stage_constraints(Stage.CASSATION)), 6)
        self.assertTrue(
            any("تقدير الدليل" in line for line in stage_constraints(Stage.CASSATION))
        )

    def test_the_stage_view_round_trips_with_the_case_file_stage(self):
        """
        ⚠️ **ولا يفترق تصنيفان:** ``Stage`` هنا و``CaseStage`` في `case_file.py`.

        والفرق بينهما **حقلٌ في ملف القضية** و**موضعُ عرض**، فلو أُضيفت مرحلة
        في أحدهما ولم تُضَف في الآخر لَما ظهر النقص — وهذا بعينه العيب المكتوب
        في `case_file.py` عند ``EMIRATE_ALIASES``: **مفتاحٌ لا يساوي نصّاً ⇒
        تقاطعٌ فراغٌ دائم، والفراغ يُقرأ سلامةً وهو جهل.**
        """
        self.assertEqual(len(CaseStage), len(Stage))
        for case_stage in CaseStage:
            with self.subTest(stage=case_stage.value):
                derived = stage_of_case(_case(stage=case_stage))
                self.assertIsInstance(derived, Stage)
                self.assertEqual(derived.value, case_stage.value)
        for stage in Stage:
            with self.subTest(stage=stage.value):
                self.assertIsInstance(stage, Stage)
                self.assertEqual(stage.value, CaseStage(stage.value).value)


# ==============================================================================
# ٦. ما أُغفل — الطلب الذي لا يُجاب
# ==============================================================================


class TestUnanswered(unittest.TestCase):
    """
    ⚠️ **الطلب الذي لا يُسجَّل لا يُجاب** — وهذا هو العيب الأول.

    والإغفال **صمتٌ لا خطأ**، فلا يُقرأ عيباً لأنه لا يقول شيئاً. فهذا الموضع
    يحوّل الصمت إلى قول.
    """

    def test_an_unanswered_claim_is_found(self):
        """
        🔑 **الطلب الغائب عن المسودّة يُعلن غائباً** — ولا يُحذف من المصفوفة.

        والمسودّة في الاختبار تخاطب الدفع بالتقادم **وحدها**، فالمتوقّع أن
        يُعلن الطلب ودفع المقاصة، لا أن يُعلن ما خوطب.
        """
        matrix = _matrix()
        draft = "وحيث إن الدفع بالتقادم: انقضاء ميعاد الدعوى العمالية ثابت، فتُرفض الدعوى."

        findings = unanswered(matrix, draft)
        missed = [finding.item_key for finding in findings]
        self.assertEqual(missed, ["end_of_service", "setoff"])
        self.assertNotIn("limitation", missed)
        for finding in findings:
            self.assertEqual(finding.code, CODE_UNANSWERED)
            # ⚠️ **ملاحظة لا خطأ:** «لم تُجَب» دعوى قابلة للردّ على المطابقة
            # اللفظية، لا حكم على المسودّة.
            self.assertEqual(finding.severity, SEVERITY_NOTICE)

    def test_the_claim_remains_visible_while_it_is_reported_as_unanswered(self):
        """
        ⚠️ **والإعلان لا يُسقط:** العنصر يبقى في المصفوفة وفي تفصيل المخرَج.

        ولماذا؟ لأن الحذف يُعيد العيب الأصلي: **يصير النقص صامتاً**. والتقرير
        يجب أن يقول «لم تُجَب» لا أن يُنقص من المصفوفة.
        """
        matrix = _matrix()
        payload = summarize(matrix, draft="كلام لا يخاطب شيئاً من المصفوفة")

        reported = {
            entry["item_key"]
            for entry in payload["findings"]
            if entry["code"] == CODE_UNANSWERED
        }
        self.assertEqual(reported, {"end_of_service", "setoff", "limitation"})
        self.assertIn("end_of_service", [claim["key"] for claim in payload["claims"]])
        self.assertEqual(payload["claim_count"], 1)

    def test_a_draft_that_addresses_everything_reports_nothing(self):
        """
        ⚠️ **والمسودّة الشاملة لا تُنذر بشيء** — وهذا حدّ الإنذار الكاذب.

        ولو أُعلن ما خوطب لَصارت الأداة ضجيجاً دائماً فتُهمَل — وهي النتيجة
        نفسها التي جاء منعها. والمطابقة على **المفتاح أو نصّ الطلب** معاً،
        فتُختبر الصورتان: مسودّة بالمفاتيح ومسودّة بلفظ الطلب.
        """
        matrix = _matrix()
        by_label = (
            "أولاً: الدفع بالتقادم: انقضاء ميعاد الدعوى العمالية لا يقوم. "
            "ثانياً: الدفع بالخصم من المطالبة: يُخصم نصيب الوسيط من مبلغ "
            "المطالبة لا يقوم في المقدار. "
            "ثالثاً: مكافأة نهاية الخدمة عن مدّة الخدمة كاملة تستحقّ."
        )
        self.assertEqual(unanswered(matrix, by_label), ())

        # ⚠️ والصورة الثانية بالمفاتيح: من يكتب مفاتيحه في متن المسودّة لا
        # يُتَّهم بالإغفال — والمطابقة على التسمية وحدها كانت ستُخطئ فيه.
        by_key = "بند limitation لا يقوم، وبند setoff لا يقوم، وبند end_of_service يستحقّ."
        self.assertEqual(unanswered(matrix, by_key), ())

        # ⚠️ **ولا مسودّة ⇒ كل عنصر غير مجيوب**، لا «لا حكم»: المسودّة الغائبة
        # **لم تخاطب شيئاً**، وقراءتها كسلامة تُعيد العيب الأصلي — يُسلَّم
        # مستند لم يُكتب بعد ويُقرأ تقريره تقريرَ مستندٍ سليم.
        self.assertEqual(
            [finding.item_key for finding in unanswered(matrix, "")],
            ["end_of_service", "setoff", "limitation"],
        )


# ==============================================================================
# ٧. الوقائع — الطلب المستند إلى ادعاء
# ==============================================================================


class TestFactsCrossCheck(unittest.TestCase):
    """
    ⚠️ **«الطلب المستند إلى واقعة مُدَّعاة طلبٌ لا يستند إلى شيء.»**

    وهذا أخطر من غياب الواقعة: الغائبة تُطلب، والمُدَّعاة تُقرأ ثابتة فيُبنى
    عليها ردٌّ ثم يُنكر الخصم ما كُتب على أنه ثابت — وهو العيب التاريخي في
    `facts.py`: «الموكّل يقول: اتفقنا» ⇒ «اتفق الطرفان».
    """

    def test_a_claim_resting_only_on_an_asserted_fact_is_reported(self):
        """
        🔑 **واقعةٌ بدرجة ``CLAIMED`` في الجانب المؤسِّس ⇒ حكم**، والعنصر يبقى
        ظاهراً.

        ⚠️ **ولا يُحذف العنصر ولا تُعدّل الواقعة:** الحكم عرضٌ يُقرأ، والحذف
        يُعيد العيب صامتاً — والواقعةُ المُدَّعاة قد تُسند بمستند غداً، فيجب
        أن تبقى في موضعها.
        """
        ledger = _ledger()
        matrix = ClaimMatrix(
            claims=(
                _claim(
                    key="release_invalid",
                    label="طلب إبطال المخالصة الموقّعة",
                    supporting_facts=("release.refused",),
                    documents_required=("نصّ المخالصة",),
                ),
            ),
            our_party=Party.DEFENDANT,
        )

        findings = cross_check_facts(matrix, ledger)
        self.assertEqual([finding.code for finding in findings], [CODE_FACT_ASSERTED_ONLY])
        self.assertEqual(findings[0].severity, SEVERITY_ERROR)
        self.assertIn("ادعاء لم يثبت", findings[0].message)

        # ⚠️ **والعنصر باقٍ:** لم يُحذف ولم تُعدّل واقعة السجلّ.
        self.assertIsNotNone(matrix.of_key("release_invalid"))
        self.assertIsNotNone(ledger.of_key("release.refused"))
        self.assertIs(
            ledger.of_key("release.refused").standing, Standing.CLAIMED
        )
        self.assertEqual(
            [claim["key"] for claim in summarize(matrix, ledger=ledger)["claims"]],
            ["release_invalid"],
        )

    def test_a_fact_key_that_is_not_in_the_ledger_is_an_error(self):
        """
        ⚠️ **الإحالة إلى واقعة لا وجود لها** أسوأ من الإحالة إلى واقعة ضعيفة:
        الضعيفة تُقوّى، والمعدومة **لا تُتحقّق ولا تُقارَن**.

        والحكم يسمّي المفاتيح المتاحة، لأن المحامي يحتاج أن يعرف بماذا يُصلح
        الخطأ لا أنه أخطأ فقط.
        """
        matrix = ClaimMatrix(
            claims=(_claim(supporting_facts=("nope.does_not_exist",)),),
            our_party=Party.DEFENDANT,
        )
        findings = cross_check_facts(matrix, _ledger())
        self.assertEqual(
            [finding.code for finding in findings], ["fact_key_not_in_ledger"]
        )
        self.assertIn("service.ended", findings[0].note)

    def test_an_asserted_fact_on_the_opposing_side_is_not_an_error(self):
        """
        ⚠️ **والجانب يُقرأ في الحكم:** واقعة ``CLAIMED`` **معارِضةً** ليست
        عيباً بل هي الأصل في ادعاء الخصم.

        ولو وُسمت عيباً لَصار كل ادعاءٍ للخصم إنذاراً في مصفوفتنا — وهو
        الإنذار الكاذب من الجنس الذي يُفقد التقرير كلّه.
        """
        matrix = ClaimMatrix(
            claims=(_claim(opposing_facts=("release.refused",), supporting_facts=()),),
            our_party=Party.DEFENDANT,
        )
        self.assertEqual(cross_check_facts(matrix, _ledger()), ())
        checks = fact_checks(matrix, _ledger())
        self.assertEqual([(check.side, check.standing) for check in checks],
                         [("opposing", "claimed")])

    def test_the_claimable_total_is_not_the_number_of_keys_written(self):
        """
        ⚠️ **«كم كتبنا» ليست «كم لنا»:** العدد الكامل يكذب.

        مصفوفةٌ بمفتاحين، أحدهما ادعاء، تُعلن واحداً قابلاً للإسناد لا اثنين —
        وهذا هو الفرق الذي يقوم عليه الملف.
        """
        matrix = ClaimMatrix(
            claims=(
                _claim(
                    supporting_facts=("service.ended", "release.refused"),
                ),
            ),
            our_party=Party.DEFENDANT,
        )
        self.assertEqual(claimable_total(matrix, _ledger()), 1)
        self.assertEqual(len(matrix.claims[0].supporting_facts), 2)
        checks = fact_checks(matrix, _ledger())
        self.assertTrue(
            any("ولا تُسند طلباً" in check.note for check in checks),
            "الحكم يشرح **لماذا** لا تُسند",
        )


# ==============================================================================
# ٨. الأحكام والعرض — وما يمنع التسليم وما لا يمنعه
# ==============================================================================


class TestFindingsAndSummary(unittest.TestCase):
    """
    ⚠️ **والفرق بين الخطأ والملاحظة هو الفرق بين تقرير يُقرأ وتقرير يُتجاهَل.**

    والحدّ معلن: أداةٌ تُنذر دائماً **لا تُنذر أبداً**. فالاقتراح غير المتبنّى
    و``UNKNOWN`` **ملاحظتان**، والفراغ في ``outcome_sought`` و``documents_required``
    وبلا وقائع **أخطاء**.
    """

    def test_a_missing_outcome_sought_is_an_error(self):
        """
        ⚠️ **الردّ بلا نتيجة مطلوبة يُقرأ تسليماً أو إغفالاً** — وكلاهما ليس
        ما أراده الكاتب.

        ولذلك هو **خطأ** لا ملاحظة: المستند الذي لا يطلب نتيجةً لا يُنفَّذ فيه
        شيء، فيُسلَّم بلا أثر.
        """
        matrix = ClaimMatrix(
            claims=(_claim(outcome_sought=""),), our_party=Party.DEFENDANT
        )
        payload = summarize(matrix)
        entry = _finding_for(payload["findings"], "end_of_service")
        self.assertIsNotNone(entry)
        assert entry is not None
        self.assertEqual(entry["code"], CODE_MISSING_OUTCOME)
        self.assertEqual(entry["severity"], SEVERITY_ERROR)
        self.assertFalse(payload["clean"])

    def test_a_claim_with_no_facts_on_either_side_is_an_error(self):
        """
        ⚠️ **العنصر الذي لا واقعة له ولا واقعة على خصمه غير قابل للتحقيق**:
        لا يُنفَّذ ولا يُدفع.

        والفرق بينه وبين الواقعة المُدَّعاة أنه **لا يقول شيئاً**: الأول يُقرأ
        ويُمضى لأنه لا يشكو، والثاني يُبنى عليه بغير سند.
        """
        matrix = ClaimMatrix(
            claims=(
                _claim(
                    supporting_facts=(),
                    opposing_facts=(),
                    documents_required=(),
                    burden=Burden.ON_NEITHER,
                ),
            ),
            our_party=Party.DEFENDANT,
        )
        payload = summarize(matrix)
        entry = _finding_for(payload["findings"], "end_of_service")
        self.assertIsNotNone(entry)
        assert entry is not None
        self.assertEqual(entry["code"], CODE_NO_FACTS)
        self.assertEqual(entry["severity"], SEVERITY_ERROR)

    def test_the_burden_error_is_raised_from_the_item_itself(self):
        """
        🔑 **والخطأ التاريخي يُلتقط من العنصر نفسه** — لا من نصّ يُمرَّر.

        وهذا شرط فاعلية الفحص: لو كان يحتاج أن يُمرَّر له العيب لما التقطه في
        مسودّة حقيقية، لأن العيب **لا يُكتب في مكان**، بل يظهر في كون الحقل
        فارغاً.
        """
        matrix = ClaimMatrix(
            claims=(_claim(),), defences=(_setoff_defence(),), our_party=Party.DEFENDANT
        )
        codes = [entry["code"] for entry in summarize(matrix)["findings"]]
        self.assertIn(CODE_OUR_GROUND_NEEDS_DOCUMENTS, codes)

    def test_an_empty_matrix_is_clean_and_says_so_in_arabic(self):
        """
        🔑 **والمصفوفة الفارغة جوابٌ صحيح** — لا نقصٌ يُعتذر عنه.

        ولماذا يُقال صراحةً؟ لأن التقرير الفارغ **يُقرأ نقصاً في التشغيل**
        فيُملأ بما ليس منه — على قاعدة `review.py` في الموجّه: «المصفوفة
        الفارغة ``[]`` جواب صحيح ومتوقَّع».
        """
        payload = summarize(ClaimMatrix())
        self.assertTrue(payload["clean"])
        self.assertEqual(payload["error_count"], 0)
        self.assertEqual(payload["claim_count"], 0)
        self.assertEqual(payload["defence_count"], 0)
        self.assertIn("لا طلبات ولا دفوع في المصفوفة", payload["summary"])
        self.assertIn("جوابٌ صحيح", payload["summary"])
        # ⚠️ والأسماء العربية تُبثّ مع القيم الآلية: الواجهة تُصفّي والمحامي يقرأ.
        self.assertEqual(set(payload["by_axis"]), {axis.value for axis in DisputeAxis})
        self.assertEqual(set(payload["by_burden"]), {burden.value for burden in Burden})

    def test_the_summary_is_json_safe_and_carries_the_rules_with_it(self):
        """
        ⚠️ **والقاعدة تُبثّ مع التقرير لا تُترك تعليقاً:** الذي يقرأ التقرير هو
        من يحتاجها — على قاعدة `summarize` في `facts.py`.

        والفحص على ``json.dumps`` **لا على الشكل**: ما لا يُبثّ لا يصل إلى
        الواجهة، فيُقرأ التقرير في الطرفية وحدها.
        """
        payload = summarize(
            _matrix(),
            findings=(),
            ledger=_ledger(),
            draft="لا يخاطب شيئاً",
            stage=Stage.FIRST_INSTANCE,
            suggestions=suggested_only(_matrix(), Stage.FIRST_INSTANCE),
        )
        text = json.dumps(payload, ensure_ascii=False)
        self.assertIn("الاختصاص", text)
        self.assertIn("suggestion_is_not_a_pleading", payload["rules"])
        self.assertIn("procedural_gates_come_first", payload["rules"])
        self.assertEqual(payload["order"], ["limitation", "end_of_service", "setoff"])
        # ⚠️ والتفصيل يذكر المحور **وسؤاله**، فلا يُخلط محورٌ بغيره في العرض.
        axes = payload["claims"][0]["axes_in_dispute"]
        self.assertEqual(axes[0]["axis"], "quantum")
        self.assertTrue(axes[0]["question"].strip())
        self.assertEqual(payload["claims"][0]["kind"], "claim")
        self.assertEqual(payload["defences"][1]["kind"], "defence")
        self.assertIn("is_procedural", payload["defences"][1])

    def test_the_summary_line_names_the_order_and_the_gate_labels(self):
        """
        ⚠️ **والترتيب يُعرض ليُفهم**، لا ليُستنتج: مصفوفة يقول تقريرها
        «الاختصاص ثم الموضوع» أرصن من مصفوفة تُعرض عناصرها بلا أبواب.
        """
        payload = summarize(_matrix())
        self.assertIn("التقادم", payload["summary"])
        self.assertIn("الموضوع", payload["summary"])
        self.assertEqual(payload["gates"], ["التقادم", "الموضوع"])
        self.assertEqual(set(BURDEN_LABELS), {burden.value for burden in Burden})


# ==============================================================================
# ٩. المصفوفة والحتمية — وهي شرط قابلية المقارنة
# ==============================================================================


class TestMatrixIntegrity(unittest.TestCase):
    """
    ⚠️ **والحتمية شرط لا تحسين:** الأداة التي تُعطي مخرَجاً مختلفاً على المدخل
    نفسه **لا يُقارَن تقريرها بتقرير**، فيضيع الفرق بين ما تحسّن وما لم يتحسّن.
    """

    def test_the_same_inputs_always_give_the_same_outcome(self):
        """
        🔑 **والنداء مرّتان يُعطي القاموس نفسه** — بالمحاور والترتيب والأحكام.

        والفحص على ``json.dumps`` **لا على الهويّة**: القاموسان قد يفترقان في
        الهويّة ويتفقان في المعنى، والمعنى هو ما يُبثّ ويُقارَن.
        """
        def once() -> str:
            matrix = _matrix()
            return json.dumps(
                summarize(
                    matrix,
                    ledger=_ledger(),
                    draft="مسودّة لا تخاطب شيئاً",
                    stage=Stage.CASSATION,
                    suggestions=suggested_only(matrix, Stage.CASSATION),
                ),
                ensure_ascii=False,
                sort_keys=True,
            )

        first, second = once(), once()
        self.assertEqual(first, second)
        self.assertEqual(
            [item.key for item in order_for_review(_matrix())],
            [item.key for item in order_for_review(_matrix())],
        )

    def test_a_duplicate_or_empty_key_stops_the_matrix(self):
        """
        ⚠️ **والمفتاح المكرّر يُوقف البناء:** عنصران بهويّة واحدة يجعلان
        «أُجيب» و«أُغفل» يُقرآن عن العنصر الخطأ — ولا جواب.

        ⚠️ والتكرار **بين الطلبات والدفوع معاً** مرفوض كذلك، لأن المفتاح هو
        ما يُعرَف به العنصر في `unanswered` وفي العدّ.
        """
        with self.assertRaises(ValueError):
            ClaimMatrix(claims=(_claim(), _claim()))
        with self.assertRaises(ValueError):
            ClaimMatrix(claims=(_claim(),), defences=(_setoff_defence(key="end_of_service"),))
        with self.assertRaises(ValueError):
            ClaimMatrix(claims=(_claim(key="   "),))
        with self.assertRaises(ValueError):
            ClaimMatrix(defences=(_setoff_defence(key=""),))

    def test_the_matrix_keeps_the_two_kinds_apart_and_finds_items_by_key(self):
        """
        ⚠️ **والطلبات والدفوع مفصولة لا مخلوطة:** ناتج ``items`` يُعيد الطلبات
        أولاً، ولا يُخلط النوعان في حقل واحد.

        والسبب أن الطلب دعوى يُطالب بها والدفع جواب يُجاب به، ولكلٍّ اتجاه —
        ولو خُلطا لجاز أن يُقرأ دفعٌ مكان طلب في الترتيب وفي العدّ.
        """
        matrix = _matrix()
        self.assertEqual([item.key for item in matrix.items],
                         ["end_of_service", "setoff", "limitation"])
        self.assertIsInstance(matrix.of_key("end_of_service"), Claim)
        self.assertIsInstance(matrix.of_key("setoff"), Defence)
        self.assertIsNone(matrix.of_key("nope"))

    def test_the_module_depends_on_nothing_but_the_standard_library_and_the_project(self):
        """
        ⚠️ **ولا تبعية جديدة:** مكتبة بايثون القياسية وحدها، ومن المشروع
        ``case_file`` و``facts`` و``citations``.

        والفحص نصّي على شجرة الاستيراد — فلا يحتاج تشغيلاً ولا شبكة. والسبب
        أن التبعية الجديدة **تُخرج هذه الوحدة من كل تشغيل**، وما لا يُشغَّل لا
        يُختبر.
        """
        allowed_project = {"case_file", "facts", "citations"}
        tree = ast.parse(inspect.getsource(claims))
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])

        third_party = {
            name
            for name in imported
            if name not in allowed_project
            and name not in sys.stdlib_module_names
        }
        self.assertEqual(third_party, set(), f"تبعية خارجية في `claims`: {third_party}")
        self.assertTrue(allowed_project.issubset(imported))

    def test_a_gate_marker_written_without_normalization_would_never_match(self):
        """
        ⚠️ **الدرس الذي دُفع ثمنه في `case_file.py`:** مفتاحٌ لا يساوي النصّ
        ⇒ تقاطعٌ فراغٌ دائم، **والفراغ يُقرأ سلامةً وهو جهل**.

        فالفحص يُطبّع الألفاظ كما تُطبَّع في المطابقة: كل لفظ يجب أن يبقى كما هو
        بعد التطبيع، وإلا كان **لفظاً لا يمكن أن يوجد** قطّ في نصّ مطبَّع.
        وهذه هي الحادثة نفسها التي وقعت في مطابقة الجهة، وهذا هو الحدّ الذي
        يمنع تكرارها في هذا الملف.
        """
        for gate, markers in GATE_MARKERS.items():
            with self.subTest(gate=gate):
                for marker in markers:
                    self.assertEqual(
                        claims.normalize(marker),
                        marker,
                        f"لفظ غير مطبَّع في {gate}: {marker!r} — لن يطابق أبداً",
                    )
        for ground in BURDEN_CARRYING_GROUNDS:
            with self.subTest(ground=ground):
                for marker in BURDEN_GROUND_MARKERS[ground]:
                    self.assertEqual(claims.normalize(marker), marker)
        for markers in (
            claims._MARKERS_EVIDENCE_WEIGHING,
            claims._MARKERS_NEW_CLAIM,
            claims._MARKERS_JURISDICTION,
        ):
            for marker in markers:
                with self.subTest(marker=marker):
                    self.assertTrue(claims.normalize(marker))


# ==============================================================================
# ١٠. المرحلة في ملف القضية — الاشتقاق لا التمرير
# ==============================================================================


class TestStageOfCase(unittest.TestCase):
    """
    ⚠️ **والمرحلة تُشتقّ من ملف القضية ولا تُمرَّر بيد المستدعي.**

    ولماذا؟ لأن تمريرها يفتح باباً لافتراق صامت: ملفٌّ يقول «استئناف»
    ومصفوفة تقول «ابتدائي»، فيُقترح في المستند ما لا تقبله مرحلته، ويُقترح
    عليه من الدفوع ما لا يُقال فيها.
    """

    def test_every_case_stage_maps_to_the_matching_stage(self):
        """
        🔑 **والجولة كاملة على القيمتين** — فلا قيمة بلا مقابل.

        ⚠️ وهذا هو ما يمنع أن يفترق التصنيفان: القيمة الجديدة في `case_file.py`
        تظهر هنا **ناقصةً في الاختبار** لا في عين المراجع.
        """
        self.assertEqual(
            [stage_of_case(_case(stage=case_stage)) for case_stage in CaseStage],
            list(Stage),
        )

    def test_the_stage_decides_which_defences_are_suggested(self):
        """
        ⚠️ **والمرحلة تُغيّر الاقتراح:** ما يُستحضر في الابتدائي غير ما
        يُستحضر في التمييز.

        ولو كان الجدول واحداً لكل المراحل لَكان الاقتراح **تلقيناً** لا
        سؤالاً — وهو العين الذي مُنع.
        """
        first = {item.key for item in stock_defences(Stage.FIRST_INSTANCE)}
        cassation = {item.key for item in stock_defences(Stage.CASSATION)}
        execution = {item.key for item in stock_defences(Stage.EXECUTION)}

        self.assertIn("setoff", first)
        self.assertNotIn("setoff", cassation)
        self.assertIn("cassation_grounds", cassation)
        self.assertIn("execution_objection", execution)
        self.assertNotEqual(first, cassation)

    def test_a_stage_from_the_case_file_is_usable_without_translation(self):
        """
        ⚠️ **وسؤال المرحلة الواحد:** من مشتقّ من الملف يُنادَى به كل ما يحتاج
        مرحلة، بلا جدول وسيط عند المستدعي — ولو احتاج لَظهر جدولٌ آخر يفترق.
        """
        case = _case(stage=CaseStage.CASSATION)
        stage = stage_of_case(case)
        matrix = ClaimMatrix(
            claims=(_claim(),), defences=(_cassation_evidence_ground(),),
            stage=stage, our_party=case.our_party,
        )
        self.assertTrue(validate_for_stage(matrix.defences[0], stage))
        self.assertEqual(matrix.stage, stage)


if __name__ == "__main__":
    unittest.main()
