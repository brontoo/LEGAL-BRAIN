"""
اختبارات حلقة المراجعة والإعادة — الخطأ يُصلَح، وما لا يُصلَح يُعرَض.
================================================================================

تشغيل::

    cd legal-brain
    python -m unittest tests.test_revision_loop -v
    python -m unittest discover -s tests -t . -v

**حتمية بالكامل: بلا شبكة، وبلا نموذج، وبلا قاعدة بيانات، وبلا قرص.** وهذا شرط
لا تحسين: `redraft` و`collect` محقونان في هذه الاختبارات بدوالّ تُعيد نصّاً ثابتاً،
**فالحلقة تُقاس بلا نداء واحد.** ولو احتاجت الحلقة نموذجاً لَما شُغّلت في كل مرّة،
ولا يمكن أن تُقال فيها جملة «هذا سلوكها» بلا تحفّظ.

ولماذا هذه الاختبارات بعينها
----------------------------
* ``test_a_fixed_error_disappears_and_the_loop_stops_early`` — الحلقة تُنقص خطأً
  ثم **تتوقّف**: ولا تُنفق محاولة على مسودّة نظيفة.
* ``test_a_non_converging_redraft_stops_before_the_ceiling`` و
  ``test_the_loop_respects_max_attempts`` — **حدّان مختلفان**: الأوّل عن إعادة
  صياغة لا تُنقص شيئاً (فتُوقف المحاولات قبل السقف)، والثاني عن إعادة صياغة
  تُنقص خطأً كل مرّة ولا تنقّي المسودّة أبداً (فالسقف هو ما يوقفها). ولو لم
  يوجد الأوّل لأنفقت الحلقة كل محاولاتها على مسودّة لا تتقارب.
* ``test_a_missing_article_is_reported_not_redrafted`` — **العيب الذي وُلد
  `attribution.py` له**: نصّ صحيح منسوب إلى مادة ليست له. وإعادة الصياغة لا
  تُنشئ نصّاً غير موجود في الأرشيف، فالمحاولة عليه إنفاق بلا مقابل.
* ``test_an_arithmetic_finding_is_not_fixed_by_rewriting`` — الرقم يُحتسب بأداة
  أو يُمرَّر من البيانات، **ولا يُعاد كتابته**: كتابته تخميناً تُنتج رقماً آخر لا
  سند له — وهو أساس الأجر الخاطئ المسجَّل في `briefing.py`.
* ``test_remaining_errors_are_returned_never_hidden`` — الشرط الصريح: **لا
  يُخفى خطأ مادّي** لأن المحاولات نفدت.
* ``test_an_unrun_check_is_not_a_clean_check`` — **القاعدة المركزية في
  `briefing.py`**: الفحص الذي لم يجرِ ليس فحصاً نجح. وقائمة أخطاء فارغة تعني
  الشيئين معاً، فلا يجوز أن يُقرأ فراغها شهادة.
* ``test_describe_never_says_ready_to_file`` — لا عبارة في هذا الملف تعني أن
  المستند صالح للإيداع، **ولا في أفضل حصيلة يمكن بناؤها**.
* ``test_the_same_inputs_give_the_same_outcome`` — الحلقة دالّة صافية: لا حالة
  على مستوى الوحدة، ولا اعتماد على ترتيب النداءات.
"""

import io
import json
import pathlib
import re
import unittest
from contextlib import redirect_stdout

import revision_loop
from attribution import STATUS_MATCHED, verify_attributions
from citations import Evidence, format_evidence_block, quote_in_text
from facts import Fact, FactLedger, FactShift, Standing, check_fidelity
from language_audit import audit_language
from review import KINDS as REVIEW_KINDS
from review import SEVERITIES, parse_review
from revision_loop import (
    ARITHMETIC_MUST_BE_COMPUTED,
    ARCHIVE_DOES_NOT_HOLD,
    DEFAULT_MAX_ATTEMPTS,
    NEVER_SAY,
    SEVERITY_ERROR,
    SEVERITY_NOTICE,
    SOURCE_ATTRIBUTION,
    SOURCE_FIDELITY,
    SOURCE_LANGUAGE,
    SOURCE_REVIEW,
    SOURCES,
    STOP_CEILING,
    STOP_CLEAN,
    STOP_MESSAGES,
    STOP_NO_PROGRESS,
    STOP_NOTHING_FIXABLE,
    STOP_REDRAFT_FAILED,
    Attempt,
    LoopAction,
    LoopError,
    LoopResult,
    collect_errors,
    describe,
    is_fixable,
    run_loop,
    sources_checked,
)


# ==============================================================================
# ١. بيانات الاختبار — مأخوذة من وحدات المشروع نفسها
# ==============================================================================
# ⚠️ **ولا يُخترع اعتراض ولا واقعة.** الاعتراضات تُقرأ بـ`parse_review` (فتُمرّ
# على فحص النصّ الحقيقي في `review.py`)، والافتراقات تُنتج بـ`check_fidelity`
# على سجلّ وقائع حقيقي، والإسنادات تُفحص بـ`verify_attributions`، وملاحظات
# الصياغة تُنتج بـ`audit_language`. **فما يُختبر هو المسار الحقيقي، لا شكل
# متخيَّل** — وهو الدرس المسجَّل في `briefing.py`: اختبارٌ يبني مدخلاته بيده
# يختبر نفسه، ويبقى الشكل الحقيقي غير مختبر.

DRAFT = (
    "إنذار قانوني\n"
    "تأخّر المستأجر عن سداد الأجرة عن أربعة أشهر كاملة، ولم يسدّد شيئاً حتى تاريخه.\n"
    "ونطالب بسداد المبلغ خلال سبعة أيام من تاريخ الاستلام.\n"
    "ونحتسب المبلغ المستحقّ ١٢٥٠٠ درهم على أساس الأجرة الشهرية.\n"
    "وقد أُرفق محضر الجلسة المؤرّخ ٢٠٢٤-٠٦-١١ مع الإشعار."
)

BRIEF = (
    "الوقائع: تأخّر المستأجر عن سداد الأجرة المتأخرة عن ثلاثة أشهر، وقد سدّد "
    "شهراً واحداً بإيصال.\n"
    "المطلوب: إنذار بالمبلغ المتبقّي ومهلة سبعة أيام للسداد."
)

ARTICLE_TEXT = (
    "المادة ٧٥: للمالك أن يطالب بالأجرة المتأخرة، ولا يفسخ العقد إلا بعد "
    "إنذار مدّته ثلاثون يوماً على الأقل."
)
EVIDENCE = format_evidence_block(
    [
        Evidence(
            ref="L1",
            chunk_id="11",
            document_name="قانون المعاملات المدنية",
            text=ARTICLE_TEXT,
            similarity=0.91,
            tool="legislation",
        )
    ]
)

#: اقتباسات **حرفية** من المسودّة — كلٌّ منها جملة كاملة لا كلمة.
Q_FACT = "تأخّر المستأجر عن سداد الأجرة عن أربعة أشهر كاملة"
Q_OMISSION = "ولم يسدّد شيئاً حتى تاريخه"
Q_TERM = "ونطالب بسداد المبلغ خلال سبعة أيام من تاريخ الاستلام"
Q_ARITH = "ونحتسب المبلغ المستحقّ ١٢٥٠٠ درهم على أساس الأجرة الشهرية"
Q_EXTRA = "وقد أُرفق محضر الجلسة المؤرّخ ٢٠٢٤-٠٦-١١ مع الإشعار"

#: سند حرفي من الموجز أو المقتطفات.
B_MONTHS = "الأجرة المتأخرة عن ثلاثة أشهر"

#: الواقعة التاريخية من `facts.py` — رفض التوقيع على مخالصة متضمّنة تنازلاً.
THE_FACT = Fact(
    key="release.refused",
    statement="رفض الموظف التوقيع على مخالصة متضمّنة تنازلاً",
    source="مخالصة مؤرّخة ٢٠٢٤-٠٥-١٠",
    locus="الصفحة ٢",
    date="2024-05-10",
    asserted_by="الموكّل",
    standing=Standing.CLAIMED,
    quote="أرفض التوقيع على هذه المخالصة لاشتمالها على تنازل",
    subject="release",
)
THE_LEDGER = FactLedger((THE_FACT,))

#: مسودّة **تنقل واقعة أخرى** على أنها الواقعة الأولى — العيب التاريخي نفسه.
FLAWED_FIDELITY_DRAFT = (
    "وحيث إن الموظف رفض استلام المبلغ المعروض عليه، فإنه لا يستحقّ المطالبة به."
)
#: ومسودّة **لم تُذكر فيها الواقعة أصلاً** — الافتراق من نوع `missing`.
MISSING_FIDELITY_DRAFT = "نصّ لا علاقة له بالواقعة المذكورة ابداً."

#: مقطعان من الأرشيف، والنصّ المنسوب إلى المادة ٧٥ نصُّ المادة ٤٣.
ARTICLE_43 = (
    "المادة ٤٣: ينتهي العقد المحدد المدة بمضي مدته، ولا يجوز تجديده إلا "
    "باتفاق مكتوب."
)
ATTRIBUTION_EVIDENCE = [
    Evidence(ref="L1", chunk_id="11", document_name="قانون المعاملات المدنية", text=ARTICLE_TEXT),
    Evidence(ref="L2", chunk_id="12", document_name="قانون المعاملات المدنية", text=ARTICLE_43),
]
MISMATCHED_DRAFT = (
    "وتنص المادة ٧٥ على: «ينتهي العقد المحدد المدة بمضي مدته، ولا يجوز "
    "تجديده إلا باتفاق مكتوب»."
)
ABSENT_REFERENCE = "المادة ٩٩"
ABSENT_DRAFT = (
    "وتنص المادة ٩٩ على: «ما لا نجده في المقاطع المسترجعة أصلاً هنا»."
)

#: لغويّات: عيب Markdown (خطأ)، وافتتاح حواري (خطأ)، وفراغ ولاتينية (ملاحظتان).
MARKDOWN_DOCUMENT = "** لائحة دعوى تجارية **\nالبند الأول: يلتزم الطرف الثاني."
PREAMBLE_DOCUMENT = "بالتأكيد، إليك المستند المطلوب."
NOTICE_DOCUMENT = (
    "البند الأول: يلتزم [اسم المدعي] بالسداد.\nوشركة Alpha Trading LLC ملتزمة."
)
CLEAN_DOCUMENT = "البند الأول: يلتزم الطرف الثاني بالسداد خلال سبعة أيام."

#: مسودّتان يستعملهما `collect` المحقون: معطوبة، ثم مُصلَحة.
BROKEN_DRAFT = "مسودّة فيها مخالفة الموجز"
FIXED_DRAFT = "مسودّة مصحّحة على الموجز"


def element(kind: str, severity: str, quote: str, basis: str = "") -> dict:
    """اعتراض كما يخرج من المراجع الثاني — يُقرأ بـ`parse_review` لا يُلفّق."""
    return {
        "kind": kind,
        "severity": severity,
        "message": f"اعتراض من نوع {kind}.",
        "quote": quote,
        "basis": basis,
    }


def review_outcome(*elements: dict, draft: str = DRAFT):
    """حصيلة مراجعة حقيقية على المسودّة نفسها."""
    return parse_review(
        json.dumps(list(elements), ensure_ascii=False), draft, BRIEF, EVIDENCE
    )


def review_errors(*elements: dict, draft: str = DRAFT) -> tuple[LoopError, ...]:
    """الأخطاء المجموعة من اعتراضات حقيقية."""
    return collect_errors(draft, review_outcome=review_outcome(*elements, draft=draft))


def fidelity_errors(count: int, offset: int = 0) -> tuple[LoopError, ...]:
    """
    افتراقات وقائع بعدد معلوم — **لكلٍّ نصّه الخاصّ** في المسودّة.

    ⚠️ والنصّ الخاصّ مهمّ: هويّة الخطأ تُبنى على نصّه، فافتراقات بلا نصّ تتشابه
    في الهويّة فلا يُقاس «كم أُصلح» قياساً صحيحاً.
    """
    shifts = tuple(
        FactShift(
            fact_key=f"fact.{index}",
            kind="reworded",
            draft_text=f"نصّ الواقعة رقم {index} في المسودّة",
            fact_statement=f"واقعة رقم {index}",
            note=f"الواقعة أُعيدت صياغتها (قياس {index}).",
        )
        for index in range(offset, offset + count)
    )
    return collect_errors(DRAFT, fidelity_shifts=shifts)


def scripted_collect(table: dict) -> callable:
    """
    `collect` محقون: مسودّة ← أخطاؤها.

    ⚠️ والربط **بالمسودّة لا بالمحاولة**: هذا هو الشكل الحقيقي — الأخطاء نتيجةُ
    نصّ، لا نتيجةُ عدّاد. ولو رُبطت بالمحاولة لَما اختُبر أن الحلقة تقرأ الخطأ
    من المسودّة الجديدة.
    """

    def collect(draft: str, attempt: int) -> tuple[LoopError, ...]:
        return table.get(draft, ())

    return collect


def forbidden_redraft(draft: str, errors: tuple, attempt: int) -> str:
    """إعادة صياغة **لا يجوز أن تُنادى** — لإثبات أن مساراً ما لا يُنفق محاولة."""
    raise AssertionError("لا يجوز أن تُنادى إعادة الصياغة في هذا الاختبار")


# ==============================================================================
# ٢. سلامة بيانات الاختبار
# ==============================================================================


class TestFixturesAreReal(unittest.TestCase):
    """
    ضمان على البيانات نفسها.

    لو انحرف اقتباس بحرف لصار اختبار «الاعتراض يُقرأ» يختبر الإسقاط لا القراءة
    — ويمرّ أخضر وهو يقيس العكس. وهذا هو العطب الذي وُلد
    `TestFixturesAreReal` في `test_review.py` لمنعه، فيُثبَّت هنا بالشكل نفسه.
    """

    def test_every_quote_is_verbatim_in_the_draft(self):
        for quote in (Q_FACT, Q_OMISSION, Q_TERM, Q_ARITH, Q_EXTRA):
            with self.subTest(quote=quote):
                self.assertTrue(quote_in_text(quote, DRAFT), quote)

    def test_the_basis_is_verbatim_in_the_brief_or_the_evidence(self):
        self.assertTrue(quote_in_text(B_MONTHS, BRIEF))

    def test_the_flawed_fidelity_draft_really_diverges(self):
        self.assertEqual(
            [shift.kind for shift in check_fidelity(FLAWED_FIDELITY_DRAFT, THE_LEDGER)],
            ["reworded"],
        )
        self.assertEqual(
            [shift.kind for shift in check_fidelity(MISSING_FIDELITY_DRAFT, THE_LEDGER)],
            ["missing"],
        )

    def test_the_attribution_drafts_really_diverge(self):
        mismatched = verify_attributions(
            MISMATCHED_DRAFT, ATTRIBUTION_EVIDENCE, lambda row: row.text
        )
        self.assertEqual([check.status for check in mismatched.checks], ["mismatched"])
        absent = verify_attributions(
            ABSENT_DRAFT, ATTRIBUTION_EVIDENCE, lambda row: row.text
        )
        self.assertEqual([check.status for check in absent.checks], ["absent"])

    def test_the_language_documents_really_produce_what_is_claimed(self):
        self.assertIn(
            ("markdown", SEVERITY_ERROR),
            [(item.kind, item.severity) for item in audit_language(MARKDOWN_DOCUMENT).findings],
        )
        self.assertIn(
            ("preamble", SEVERITY_ERROR),
            [(item.kind, item.severity) for item in audit_language(PREAMBLE_DOCUMENT).findings],
        )
        self.assertEqual(
            [(item.kind, item.severity) for item in audit_language(NOTICE_DOCUMENT).findings],
            [("placeholder", SEVERITY_NOTICE), ("latin", SEVERITY_NOTICE)],
        )
        self.assertEqual(audit_language(CLEAN_DOCUMENT).findings, [])


# ==============================================================================
# ٣. قائمة واحدة، بشكل واحد
# ==============================================================================


class TestCollectErrors(unittest.TestCase):
    """الجمع: كل خطأ بشكله الواحد، ونوعه من وحدته، ولا اختراع فحص لم يُشغَّل."""

    def test_a_review_finding_arrives_whole(self):
        outcome = review_outcome(
            element("fact", SEVERITY_ERROR, Q_FACT, B_MONTHS)
        )
        errors = collect_errors(DRAFT, review_outcome=outcome)

        self.assertEqual(len(errors), 1)
        error = errors[0]
        self.assertEqual(error.source, SOURCE_REVIEW)
        self.assertEqual(error.kind, "fact")
        self.assertEqual(error.severity, SEVERITY_ERROR)
        self.assertEqual(error.quote, Q_FACT)
        self.assertEqual(error.message, outcome.findings[0].message)

    def test_an_arithmetic_finding_says_the_figure_must_be_computed(self):
        """
        🔑 الرقم لا يُصلَح بإعادة الصياغة — والرسالة تقول ذلك صراحةً.

        وإصلاحه خارج نصّ المسودّة: يُحتسب بأداة أو يُمرَّر من البيانات. ولو
        أُعيدت كتابته تخميناً لتغيّر الرقم وبقي بلا سند — وهو أساس الأجر الخاطئ
        الذي سجّله `briefing.py` في ثلاث مذكّرات وُصفت بالاكتمال.
        """
        errors = review_errors(element("arithmetic", SEVERITY_ERROR, Q_ARITH))
        error = errors[0]

        self.assertEqual(error.kind, "arithmetic")
        self.assertEqual(error.action, LoopAction.REPORT_ONLY)
        self.assertFalse(error.fixable_by_redraft)
        self.assertFalse(is_fixable(error))
        self.assertIn(ARITHMETIC_MUST_BE_COMPUTED, error.message)
        self.assertIn("يُحتسب", error.message)

    def test_a_missing_article_is_a_notice_from_attribution(self):
        outcome = verify_attributions(
            ABSENT_DRAFT, ATTRIBUTION_EVIDENCE, lambda row: row.text
        )
        errors = collect_errors(DRAFT, attribution_outcome=outcome)

        self.assertEqual([error.kind for error in errors], ["absent"])
        error = errors[0]
        self.assertEqual(error.source, SOURCE_ATTRIBUTION)
        self.assertEqual(error.severity, SEVERITY_NOTICE)
        self.assertEqual(error.action, LoopAction.REPORT_ONLY)
        self.assertFalse(error.fixable_by_redraft)
        self.assertIn(ABSENT_REFERENCE, error.message)
        self.assertIn(ARCHIVE_DOES_NOT_HOLD, error.message)

    def test_a_mismatched_attribution_is_an_error_and_names_both_sides(self):
        outcome = verify_attributions(
            MISMATCHED_DRAFT, ATTRIBUTION_EVIDENCE, lambda row: row.text
        )
        error = collect_errors(DRAFT, attribution_outcome=outcome)[0]

        self.assertEqual(error.kind, "mismatched")
        self.assertEqual(error.severity, SEVERITY_ERROR)
        self.assertEqual(error.action, LoopAction.REDRAFT)
        self.assertTrue(is_fixable(error))
        # ⚠️ و«النصّ موجود في مادة أخرى» يقتضي **نقلاً**، و«النصّ غير موجود في
        # أيّ مقطع» يقتضي حذفاً. فذكرهما في الرسالة ليس تفصيلاً.
        self.assertIn("L2", error.message)

    def test_a_matched_attribution_produces_no_error(self):
        outcome = verify_attributions(
            f"وتنص المادة ٧٥ على: «للمالك أن يطالب بالأجرة المتأخرة».",
            ATTRIBUTION_EVIDENCE,
            lambda row: row.text,
        )
        self.assertEqual([check.status for check in outcome.checks], [STATUS_MATCHED])
        self.assertEqual(collect_errors(DRAFT, attribution_outcome=outcome), ())

    def test_a_missing_fact_is_surfaced_without_a_redraft_rule(self):
        """
        ⚠️ قرار معلن: الواقعة الغائبة **لا تُصلحها محاولة في هذا الملف**.

        و`check_fidelity` توسم `missing` كل واقعة لم تصل إلى المسودّة، وقد تكون
        الواقعة من ملفٍّ لا يخصّ هذا المستند. فأيُضاف كل ما في السجلّ، أم يُترك
        للمحامي أن يقرّر؟ **والقرار قراره**، فالحلقة لا تُنفق محاولة عليه
        وتُسمّيه `stop` — لأن قاعدة إصلاحه لم تُعلَن، **والجهل يُعرَض ولا يُخمَّن**.
        """
        shifts = check_fidelity(MISSING_FIDELITY_DRAFT, THE_LEDGER)
        error = collect_errors(DRAFT, fidelity_shifts=shifts)[0]

        self.assertEqual(error.kind, "missing")
        self.assertEqual(error.severity, SEVERITY_ERROR)
        self.assertEqual(error.action, LoopAction.STOP)
        self.assertFalse(is_fixable(error))
        # ونصّ الواقعة من السجلّ حاضر في الرسالة: الافتراق لا يُراجَع بطرف واحد.
        self.assertIn(THE_FACT.statement, error.message)

    def test_a_reworded_fact_is_fixable(self):
        shifts = check_fidelity(FLAWED_FIDELITY_DRAFT, THE_LEDGER)
        error = collect_errors(DRAFT, fidelity_shifts=shifts)[0]

        self.assertEqual(error.kind, "reworded")
        self.assertEqual(error.severity, SEVERITY_ERROR)
        self.assertTrue(is_fixable(error))

    def test_language_errors_and_notices_keep_their_severity(self):
        report = audit_language(NOTICE_DOCUMENT)
        errors = collect_errors(DRAFT, language_report=report)

        self.assertEqual(
            [(error.kind, error.severity) for error in errors],
            [("placeholder", SEVERITY_NOTICE), ("latin", SEVERITY_NOTICE)],
        )
        self.assertTrue(all(not is_fixable(error) for error in errors))

    def test_a_markdown_error_is_fixable_and_a_preamble_error_is_not_declared(self):
        """
        ⚠️ `markdown` في جدول الإصلاح، و`preamble` **خارجه**.

        و`preamble` عيبُ صياغة يُزال بنصّ جديد — لكن قاعدة إصلاحه لم تُعلَن في
        جدول هذا الملف، **فلا يُدَّعى لها حكم لم يُكتب**: يُعرَض على المحامي.
        وهذا هو الفرق بين قاعدة معلَنة وقاعدة يُتوقَّع من القارئ أن يستنبطها.
        """
        markdown = collect_errors(
            DRAFT, language_report=audit_language(MARKDOWN_DOCUMENT)
        )[0]
        preamble = collect_errors(
            DRAFT, language_report=audit_language(PREAMBLE_DOCUMENT)
        )[0]

        self.assertEqual(markdown.kind, "markdown")
        self.assertTrue(is_fixable(markdown))
        self.assertEqual(preamble.kind, "preamble")
        self.assertEqual(preamble.severity, SEVERITY_ERROR)
        self.assertFalse(is_fixable(preamble))
        self.assertEqual(preamble.action, LoopAction.STOP)

    def test_nothing_given_means_an_empty_list_not_a_clean_bill(self):
        """⚠️ الفراغ هنا «لم يُفحص شيء» — ولا يُقرأ سلامةً (انظر `TestSourcesChecked`)."""
        self.assertEqual(collect_errors(DRAFT), ())

    def test_the_order_is_fixed_by_source_not_by_the_call(self):
        """
        الترتيب جزء من العقد: المصادر بترتيب `SOURCES`، وما بعده ترتيب الوحدة.

        ولو رُتّبت القائمة على ترتيب الوسائط الممرَّرة لتغيّر التقرير بين نداءين
        بالمدخلات نفسها — وهو ما يمنعه `test_the_same_inputs_give_the_same_outcome`.
        """
        errors = collect_errors(
            DRAFT,
            language_report=audit_language(MARKDOWN_DOCUMENT),
            attribution_outcome=verify_attributions(
                MISMATCHED_DRAFT, ATTRIBUTION_EVIDENCE, lambda row: row.text
            ),
            review_outcome=review_outcome(element("fact", SEVERITY_ERROR, Q_FACT)),
            fidelity_shifts=check_fidelity(FLAWED_FIDELITY_DRAFT, THE_LEDGER),
        )

        self.assertEqual(
            tuple(dict.fromkeys(error.source for error in errors)), SOURCES
        )

    def test_the_derived_fields_are_one_decision(self):
        """
        ⚠️ `action` و`fixable_by_redraft` **حكمان على شيء واحد**، فلا يفترقان.

        وهذا هو العطب الذي يمنعه الملف في مواضع أخرى («رقمان لشيء واحد»): حقلٌ
        يُكتب في موضع وآخر يُحسب في موضع ثانٍ، فيُقرأ الخطأ نفسه مُصلَحاً وغير
        مُصلَح في نداءين. والقاعدة واحدة (`_action_for`)، وهذا الاختبار يمسحها.
        """
        errors = (
            review_errors(
                element("fact", SEVERITY_ERROR, Q_FACT),
                element("strength", SEVERITY_NOTICE, Q_TERM),
            )
            + collect_errors(
                DRAFT,
                fidelity_shifts=check_fidelity(FLAWED_FIDELITY_DRAFT, THE_LEDGER)
                + check_fidelity(MISSING_FIDELITY_DRAFT, THE_LEDGER),
            )
            + collect_errors(
                DRAFT,
                attribution_outcome=verify_attributions(
                    MISMATCHED_DRAFT, ATTRIBUTION_EVIDENCE, lambda row: row.text
                ),
            )
            + collect_errors(
                DRAFT, language_report=audit_language(MARKDOWN_DOCUMENT)
            )
        )
        self.assertGreater(len(errors), 4)

        for error in errors:
            with self.subTest(source=error.source, kind=error.kind):
                self.assertEqual(error.fixable_by_redraft, is_fixable(error))
                self.assertEqual(
                    error.action is LoopAction.REDRAFT, error.fixable_by_redraft
                )

    def test_a_loop_error_cannot_be_edited_in_place(self):
        """الخطأ المعروض على المحامي لا يُعدَّل بعد عرضه (نمط المشروع كله)."""
        error = review_errors(element("fact", SEVERITY_ERROR, Q_FACT))[0]
        with self.assertRaises(Exception):
            error.message = "غير ذلك"  # type: ignore[misc]


# ==============================================================================
# ٤. أيّ فحص جرى؟ — الفراغ ليس شهادة
# ==============================================================================


class TestSourcesChecked(unittest.TestCase):
    """
    `sources_checked` هي الفاصل بين «فُحص فلم يُوجد» و«لم يُفحص».

    ⚠️ وكلتاهما قائمة أخطاء فارغة، **وهما حقيقتان مختلفتان** — والخلط بينهما هو
    العيب الذي وُلد `briefing.py` لمنعه، وظلّ يعمل في `review-panel.tsx` حيث كان
    الشكل يصل `clean: True` ومعه أن المراجعة **لم تحدث**.
    """

    def test_all_four_are_reported_in_a_fixed_order(self):
        checked = sources_checked(
            review_outcome=review_outcome(),
            fidelity_shifts=(),
            attribution_outcome=verify_attributions(
                MISMATCHED_DRAFT, ATTRIBUTION_EVIDENCE, lambda row: row.text
            ),
            language_report=audit_language(CLEAN_DOCUMENT),
        )
        self.assertEqual(checked, SOURCES)

    def test_a_component_passed_as_none_is_absent(self):
        checked = sources_checked(
            review_outcome=review_outcome(),
            fidelity_shifts=None,
            attribution_outcome=None,
            language_report=None,
        )
        self.assertEqual(checked, (SOURCE_REVIEW,))
        self.assertNotIn(SOURCE_FIDELITY, checked)
        self.assertNotIn(SOURCE_ATTRIBUTION, checked)
        self.assertNotIn(SOURCE_LANGUAGE, checked)

    def test_a_none_component_contributes_nothing(self):
        """لا خطأ منه ولا ملاحظة — ولا هو مذكور نظيفاً."""
        errors = collect_errors(
            DRAFT,
            review_outcome=None,
            fidelity_shifts=None,
            attribution_outcome=None,
            language_report=None,
        )
        self.assertEqual(errors, ())

    def test_the_severity_vocabulary_is_the_project_vocabulary(self):
        self.assertEqual({SEVERITY_ERROR, SEVERITY_NOTICE}, set(SEVERITIES))


# ==============================================================================
# ٥. هل يُبرَّر نداء آخر؟ — الحكم على الخطأ وحده
# ==============================================================================


class TestIsFixable(unittest.TestCase):
    """
    الحكم **دالّة صافية من الخطأ**، لا من عدّ ولا من نسبة ثقة.

    ⚠️ وهذا هو جواب الملف على الشرط الذي بُني عليه الطلب: «لا يُعتمد على تقدير
    النموذج لنفسه ولا على رقم ثقة». فالسؤال «هل نحاول مرّة أخرى؟» يُجاب عنه بنوع
    الخطأ ومصدره ودرجته — ولو أُجيب عنه برقم لَقُرئ «٠٫٩» فسُلِّم مستند لم يُفحص.
    """

    def test_the_answer_depends_only_on_source_kind_and_severity(self):
        base = review_errors(element("arithmetic", SEVERITY_ERROR, Q_ARITH))[0]
        decorated = LoopError(
            source=base.source,
            kind=base.kind,
            severity=base.severity,
            message="رسالة أخرى تماماً",
            quote="اقتباس آخر",
            action=base.action,
            fixable_by_redraft=base.fixable_by_redraft,
        )
        self.assertEqual(is_fixable(base), is_fixable(decorated))

    def test_the_flag_does_not_override_the_rule(self):
        """
        ⚠️ الحكم يُعاد حسابه من القاعدة، **ولا يُقرأ من الحقل المشتقّ**.

        فحقلٌ يُكتب بيدٍ في اختبار أو في مسار آخر قد يخالف القاعدة؛ فلو قرأته
        الحلقة لَدَخل خطأ `arithmetic` في قائمة إعادة الصياغة لأن أحداً وسمه
        «قابل للإصلاح».
        """
        lying = LoopError(
            source=SOURCE_REVIEW,
            kind="arithmetic",
            severity=SEVERITY_ERROR,
            message="خ",
            quote=Q_ARITH,
            action=LoopAction.REDRAFT,
            fixable_by_redraft=True,
        )
        self.assertFalse(is_fixable(lying))

    def test_a_notice_is_never_fixable(self):
        notices = (
            review_errors(element("fact", SEVERITY_NOTICE, Q_FACT))
            + collect_errors(DRAFT, language_report=audit_language(NOTICE_DOCUMENT))
            + collect_errors(
                DRAFT,
                attribution_outcome=verify_attributions(
                    ABSENT_DRAFT, ATTRIBUTION_EVIDENCE, lambda row: row.text
                ),
            )
        )
        self.assertGreaterEqual(len(notices), 4)
        for error in notices:
            with self.subTest(source=error.source, kind=error.kind):
                self.assertEqual(error.severity, SEVERITY_NOTICE)
                self.assertFalse(is_fixable(error))

    def test_there_are_only_three_actions(self):
        self.assertEqual(
            [action.value for action in LoopAction],
            ["redraft", "report_only", "stop"],
        )


# ==============================================================================
# ٦. الحلقة — الحدّ، والتقارب، والإيقاف
# ==============================================================================


class TestTheLoop(unittest.TestCase):
    """سلوك الحلقة: متى تعيد الصياغة، ومتى تتوقّف، وبأيّ عدد من المحاولات."""

    def test_a_fixed_error_disappears_and_the_loop_stops_early(self):
        """
        🔑 خطأ واحد قابل للإصلاح، وإعادة صياغة تُنجزه — **فلا محاولة ثالثة**.

        ولو واصلت الحلقة إلى السقف لنفَقت محاولاتٍ على مسودّة نظيفة، وهو إنفاق
        من وقت المحامي ومال الموكّل بلا مقابل. والفحص الثاني يُثبت أن الخطأ زال:
        **التوقّف عن خلوص لا عن ثقة.**
        """
        calls: list = []

        def redraft(draft, errors, attempt):
            calls.append((draft, tuple(error.kind for error in errors), attempt))
            return FIXED_DRAFT

        result = run_loop(
            BROKEN_DRAFT,
            redraft,
            scripted_collect(
                {BROKEN_DRAFT: review_errors(element("fact", SEVERITY_ERROR, Q_FACT))}
            ),
            max_attempts=5,
        )

        self.assertEqual(result.attempts_used, 2)
        self.assertEqual(result.stop_code, STOP_CLEAN)
        self.assertEqual(result.stopped_reason, STOP_MESSAGES[STOP_CLEAN])
        self.assertEqual(result.final_draft, FIXED_DRAFT)
        self.assertEqual(result.material_remaining, ())
        self.assertEqual(result.remaining, ())
        self.assertEqual(result.fixed_total, 1)
        self.assertEqual(result.attempts[1].fixed, 1)
        self.assertEqual(calls, [(BROKEN_DRAFT, ("fact",), 1)])
        self.assertFalse(result.can_be_called_verified)  # لم يُعلَن فحص

    def test_the_loop_respects_max_attempts(self):
        """
        إعادة صياغة تُنقص خطأً في كل مرّة ولا تنقّي المسودّة أبداً: **السقف وحده**.

        ⚠️ ولا يتناقض هذا مع `test_a_non_converging_redraft_stops_before_the_ceiling`:
        هنا **العدد ينقص** في كل جولة (فلا ينطبق شرط عدم التقارب)، وهناك لا ينقص
        (فيتوقّف قبل السقف). ولو لم يوجد هذا الاختبار لَما عُرف أن الحلقة تتوقّف
        عند السقف أصلاً، ولو لم يوجد ذاك لَنفَقت كل محاولاتها على مسودّة لا تتقارب.
        """
        calls: list = []

        def redraft(draft, errors, attempt):
            calls.append(attempt)
            return f"{BROKEN_DRAFT} #{attempt}"

        table = {
            BROKEN_DRAFT: fidelity_errors(4),
            f"{BROKEN_DRAFT} #1": fidelity_errors(3),
            f"{BROKEN_DRAFT} #2": fidelity_errors(2),
            f"{BROKEN_DRAFT} #3": fidelity_errors(1),
        }

        result = run_loop(BROKEN_DRAFT, redraft, scripted_collect(table), max_attempts=3)

        self.assertEqual(result.attempts_used, 3)
        self.assertEqual(result.stop_code, STOP_CEILING)
        self.assertEqual(result.stopped_reason, STOP_MESSAGES[STOP_CEILING] + " (السقف المعلن: 3 محاولة · المستنفد: 3.)")
        self.assertEqual(calls, [1, 2])
        self.assertEqual([attempt.remaining for attempt in result.attempts], [4, 3, 2])
        self.assertEqual([attempt.fixed for attempt in result.attempts], [0, 1, 1])
        self.assertEqual(len(result.material_remaining), 2)

    def test_a_non_converging_redraft_stops_before_the_ceiling(self):
        """
        🔑 عدد الأخطاء لم ينقص ⇒ **إيقاف، لا استمرار**.

        والمحاولة التي لا تُنقص خطأً إنفاقٌ بلا مقابل، ولو أُتيح لها السقف كله
        لأنفقت خمس محاولات على المسودّة نفسها. والسبب يُقال بالعربية لا يُسكت عنه.
        """
        calls: list = []
        same = fidelity_errors(2)

        def redraft(draft, errors, attempt):
            calls.append(attempt)
            return f"{BROKEN_DRAFT} #{attempt}"

        result = run_loop(
            BROKEN_DRAFT,
            redraft,
            scripted_collect(
                {
                    BROKEN_DRAFT: same,
                    f"{BROKEN_DRAFT} #1": same,
                    f"{BROKEN_DRAFT} #2": same,
                }
            ),
            max_attempts=5,
        )

        self.assertEqual(result.attempts_used, 2)
        self.assertEqual(result.stop_code, STOP_NO_PROGRESS)
        self.assertEqual(result.stopped_reason, STOP_MESSAGES[STOP_NO_PROGRESS])
        self.assertEqual(calls, [1])
        self.assertLess(result.attempts_used, 5)

    def test_remaining_errors_are_returned_never_hidden(self):
        """
        🔑 ما بقي بعد آخر محاولة **يُعاد ويُعرَض** — نفاد المحاولات ليس سبب إخفاء.

        وهذا هو نصّ الطلب: «إن بقي خطأ مادّي فأظهره للمستخدم ولا تُخفِه». فالحقل
        `material_remaining` يُعاد، و`describe` يذكره بجملته، **ويُذكر معه أن
        الإيقاف كان بنفاد المحاولات لا بخلوص الفحص**.
        """
        same = fidelity_errors(2, offset=10)
        result = run_loop(
            BROKEN_DRAFT,
            lambda draft, errors, attempt: f"{BROKEN_DRAFT} #{attempt}",
            scripted_collect(
                {BROKEN_DRAFT: same, f"{BROKEN_DRAFT} #1": same}
            ),
            max_attempts=4,
        )

        self.assertEqual(result.material_remaining, result.attempts[-1].errors)
        self.assertEqual(len(result.material_remaining), 2)
        self.assertFalse(result.can_be_called_verified)

        text = describe(result)
        for error in result.material_remaining:
            with self.subTest(kind=error.kind):
                self.assertIn(error.message, text)
        self.assertIn("لا يُخفى", text)
        self.assertIn(STOP_MESSAGES[STOP_NO_PROGRESS], text)

    def test_a_missing_article_is_reported_not_redrafted(self):
        """
        🔑 مادة ليست في الأرشيف: **إعادة الصياغة لا تُنشئ نصّاً**.

        وهي الحالة التي وُلد `attribution.py` لها: نصّ صحيح منسوب إلى مادة ليست
        له. والإصلاح استرجاعٌ أو نقلٌ، لا محاولة صياغة. فالحلقة تنتهي في محاولة
        واحدة وتُعرض المادة باسمها.
        """
        errors = collect_errors(
            DRAFT,
            attribution_outcome=verify_attributions(
                ABSENT_DRAFT, ATTRIBUTION_EVIDENCE, lambda row: row.text
            ),
        )
        result = run_loop(
            BROKEN_DRAFT,
            forbidden_redraft,
            scripted_collect({BROKEN_DRAFT: errors}),
        )

        self.assertEqual(result.attempts_used, 1)
        self.assertEqual(result.stop_code, STOP_NOTHING_FIXABLE)
        self.assertEqual(result.remaining, errors)
        self.assertEqual(result.material_remaining, ())  # ملاحظة لا خطأ
        self.assertEqual(len(result.notices_remaining), 1)
        self.assertEqual(result.remaining[0].action, LoopAction.REPORT_ONLY)
        self.assertIn(ABSENT_REFERENCE, describe(result))

    def test_an_arithmetic_finding_is_not_fixed_by_rewriting(self):
        """
        🔑 الرقم لا يُصحَّح بنصّ جديد — والرسالة تقول: يُحتسب ويُمرَّر.

        والخطأ **مادّي** (أساس الأجر الخاطئ في `briefing.py`)، فهو يمنع التسليم
        ويبقى في `material_remaining`، **ولا تُنفق عليه محاولة**.
        """
        errors = review_errors(element("arithmetic", SEVERITY_ERROR, Q_ARITH))
        result = run_loop(
            BROKEN_DRAFT,
            forbidden_redraft,
            scripted_collect({BROKEN_DRAFT: errors}),
        )

        self.assertEqual(result.attempts_used, 1)
        self.assertEqual(result.material_remaining, errors)
        self.assertEqual(result.material_remaining[0].action, LoopAction.REPORT_ONLY)
        self.assertIn(ARITHMETIC_MUST_BE_COMPUTED, describe(result))

    def test_a_notice_never_triggers_a_redraft(self):
        """
        ⚠️ الملاحظة تُعرَض ولا تُنفق عليها محاولة.

        وهذا هو الدرس المدفوع الثمن في `language_audit.py`: أحد عشر سلوكاً
        صحيحاً وُسمت أخطاءً، فصار التقرير جداراً أحمر لا يُقرأ — **وصار معه
        العيب الحقيقي غير مقروء حين ظهر.** فالحلقة التي تُعيد الصياغة لأجل ملاحظة
        تُنتج الأداة نفسها.
        """
        errors = collect_errors(
            DRAFT, language_report=audit_language(NOTICE_DOCUMENT)
        )
        self.assertEqual(len(errors), 2)

        result = run_loop(
            BROKEN_DRAFT,
            forbidden_redraft,
            scripted_collect({BROKEN_DRAFT: errors}),
        )

        self.assertEqual(result.attempts_used, 1)
        self.assertEqual(result.stop_code, STOP_NOTHING_FIXABLE)
        self.assertEqual(result.material_remaining, ())
        self.assertEqual(len(result.notices_remaining), 2)

    def test_a_failed_redraft_keeps_the_last_checked_draft(self):
        """
        إعادة صياغة لا تُنتج نصّاً ⇒ **تبقى آخر مسودّة مفحوصة**.

        ولو استُبدلت بفراغ لسُلّم مستند فارغ، وهو أسوأ من مسودّة فيها خطأ معروف
        **معروض على المحامي**. والسبب يُقال بالعربية.
        """
        result = run_loop(
            BROKEN_DRAFT,
            lambda draft, errors, attempt: "   ",
            scripted_collect(
                {BROKEN_DRAFT: review_errors(element("fact", SEVERITY_ERROR, Q_FACT))}
            ),
        )

        self.assertEqual(result.stop_code, STOP_REDRAFT_FAILED)
        self.assertEqual(result.final_draft, BROKEN_DRAFT)
        self.assertEqual(result.attempts_used, 1)
        self.assertEqual(len(result.material_remaining), 1)

    def test_the_loop_stops_at_the_ceiling_without_a_wasted_call(self):
        """النداء الأخير لا يقع: الفحص عند السقف يخرج **قبل** إعادة الصياغة."""
        calls: list = []

        def redraft(draft, errors, attempt):
            calls.append(attempt)
            return f"{BROKEN_DRAFT} #{attempt}"

        result = run_loop(
            BROKEN_DRAFT,
            redraft,
            scripted_collect(
                {BROKEN_DRAFT: fidelity_errors(2), f"{BROKEN_DRAFT} #1": fidelity_errors(1)}
            ),
            max_attempts=2,
        )
        self.assertEqual(result.attempts_used, 2)
        self.assertEqual(calls, [1])

    def test_max_attempts_below_one_raises(self):
        """⚠️ الحلقة بلا سقف إنفاق غير محدود — والسقف مفروض لا موعود."""
        for value in (0, -1, -100):
            with self.subTest(max_attempts=value):
                with self.assertRaises(ValueError):
                    run_loop(BROKEN_DRAFT, forbidden_redraft, scripted_collect({}), max_attempts=value)

    def test_a_non_integer_max_attempts_raises(self):
        for value in ("3", None, 2.5, True):
            with self.subTest(max_attempts=value):
                with self.assertRaises(ValueError):
                    run_loop(BROKEN_DRAFT, forbidden_redraft, scripted_collect({}), max_attempts=value)

    def test_a_non_text_draft_raises(self):
        with self.assertRaises(ValueError):
            run_loop(None, forbidden_redraft, scripted_collect({}))

    def test_the_default_ceiling_is_three(self):
        """الحدّ الافتراضي معلن — لا يُترك للصدفة ولا يُغيَّر بلا تغيير الاختبار."""
        self.assertEqual(DEFAULT_MAX_ATTEMPTS, 3)
        result = run_loop(
            BROKEN_DRAFT,
            lambda draft, errors, attempt: f"{BROKEN_DRAFT} #{attempt}",
            scripted_collect(
                {
                    BROKEN_DRAFT: fidelity_errors(3),
                    f"{BROKEN_DRAFT} #1": fidelity_errors(3),
                }
            ),
        )
        self.assertEqual(result.stop_code, STOP_NO_PROGRESS)

    def test_progress_is_reported_through_the_callback(self):
        """
        ⚠️ الحلقة **لا تطبع ولا تُخرج شيئاً**: من أراد بثّ إطار في الواجهة يمرّر
        `on_progress`. والاختباران هنا يُثبتان الأمرين معاً: الإطارات تصل،
        والمخرج القياسي يبقى فارغاً.
        """
        frames: list = []
        captured = io.StringIO()

        with redirect_stdout(captured):
            result = run_loop(
                BROKEN_DRAFT,
                lambda draft, errors, attempt: f"{BROKEN_DRAFT} #{attempt}",
                scripted_collect(
                    {
                        BROKEN_DRAFT: fidelity_errors(2),
                        f"{BROKEN_DRAFT} #1": fidelity_errors(1),
                    }
                ),
                max_attempts=3,
                on_progress=frames.append,
            )

        self.assertEqual([frame.number for frame in frames], [1, 2, 3])
        self.assertEqual([frame.remaining for frame in frames], [2, 1, 0])
        self.assertTrue(all(isinstance(frame, Attempt) for frame in frames))
        self.assertEqual(captured.getvalue(), "")
        self.assertEqual(result.attempts_used, 3)

    def test_the_same_inputs_give_the_same_outcome(self):
        """
        🔑 دالّة صافية: لا حالة على مستوى الوحدة، ولا اعتماد على ترتيب النداءات.

        وهذا هو الفرق نفسه الذي رُجّح به `ReviewOutcome` على `last_dropped()` في
        `review.py`: لو خُزّن شيء في حالة الوحدة لكان الجواب هنا مرتهناً بترتيب
        النداءات لا بمدخلاتها. ونداء ثالث بين الاثنين يُثبت أن شيئاً لم يُحفظ.
        """
        table = {
            BROKEN_DRAFT: fidelity_errors(3),
            f"{BROKEN_DRAFT} #1": fidelity_errors(2),
            f"{BROKEN_DRAFT} #2": fidelity_errors(1),
        }

        def run():
            return run_loop(
                BROKEN_DRAFT,
                lambda draft, errors, attempt: f"{BROKEN_DRAFT} #{attempt}",
                scripted_collect(table),
                max_attempts=3,
            )

        first = run()
        run_loop(BROKEN_DRAFT, lambda draft, errors, attempt: "", scripted_collect({}))
        collect_errors(DRAFT, language_report=audit_language(NOTICE_DOCUMENT))
        third = run()

        self.assertEqual(first, third)
        self.assertEqual(
            [(attempt.number, attempt.remaining, attempt.fixed) for attempt in first.attempts],
            [(attempt.number, attempt.remaining, attempt.fixed) for attempt in third.attempts],
        )
        self.assertEqual(describe(first), describe(third))
        self.assertEqual(
            collect_errors(DRAFT, language_report=audit_language(NOTICE_DOCUMENT)),
            collect_errors(DRAFT, language_report=audit_language(NOTICE_DOCUMENT)),
        )


# ==============================================================================
# ٧. الأنواع من الوحدات الأمّ — لا مفردات ثانية
# ==============================================================================


class TestKindsAreTheOriginModulesOwnValues(unittest.TestCase):
    """
    🔑 `kind` يمرّ كما هو من الوحدة التي رصدت الخطأ.

    ولو ترجمه هذا الملف إلى مفردات خاصة به لانحرف القاموسان عند أول نوع جديد
    يُضاف في الوحدة الأمّ — **وهذا المشروع دفع ثمن «شيئين لشيء واحد» مرّتين**:
    جدول أرقام ثانٍ في `facts.py` رفع `ValueError` عند الاستيراد ولا شيء كان
    يستورد الوحدة (فالسويت الأخضر لم يقل شيئاً)، وعتبة ثانية كان يمكن أن تُقبل
    عبارةٌ في ملف وتُرفض في آخر بلا أن يظهر فرق.
    """

    def test_review_kinds_pass_through_unchanged(self):
        elements = [
            element("fact", SEVERITY_ERROR, Q_FACT),
            element("omission", SEVERITY_NOTICE, Q_OMISSION),
            element("unsupported", SEVERITY_NOTICE, Q_TERM),
            element("arithmetic", SEVERITY_ERROR, Q_ARITH),
            element("strength", SEVERITY_NOTICE, Q_EXTRA),
        ]
        outcome = review_outcome(*elements)
        errors = collect_errors(DRAFT, review_outcome=outcome)

        self.assertEqual(
            [error.kind for error in errors],
            [finding.kind for finding in outcome.findings],
        )
        self.assertEqual(sorted(error.kind for error in errors), sorted(REVIEW_KINDS))
        for error in errors:
            with self.subTest(kind=error.kind):
                self.assertIn(error.kind, REVIEW_KINDS)

    def test_fidelity_kinds_pass_through_unchanged(self):
        shifts = check_fidelity(FLAWED_FIDELITY_DRAFT, THE_LEDGER) + check_fidelity(
            MISSING_FIDELITY_DRAFT, THE_LEDGER
        )
        errors = collect_errors(DRAFT, fidelity_shifts=shifts)
        self.assertEqual([error.kind for error in errors], [shift.kind for shift in shifts])
        self.assertEqual(
            sorted(error.kind for error in errors), ["missing", "reworded"]
        )

    def test_attribution_statuses_pass_through_unchanged(self):
        outcome = verify_attributions(
            MISMATCHED_DRAFT + "\n" + ABSENT_DRAFT,
            ATTRIBUTION_EVIDENCE,
            lambda row: row.text,
        )
        errors = collect_errors(DRAFT, attribution_outcome=outcome)
        self.assertEqual(
            [error.kind for error in errors],
            [
                check.status
                for check in outcome.checks
                if check.status != STATUS_MATCHED
            ],
        )

    def test_language_kinds_pass_through_unchanged(self):
        report = audit_language(MARKDOWN_DOCUMENT + "\n" + NOTICE_DOCUMENT)
        errors = collect_errors(DRAFT, language_report=report)
        self.assertEqual(
            [error.kind for error in errors], [item.kind for item in report.findings]
        )


# ==============================================================================
# ٨. الأمانة — ما لم يُفحص، وما بقي، وما لا يُقال
# ==============================================================================


class TestHonesty(unittest.TestCase):
    """ما يستطيع الملف أن يشهد به وما لا يستطيع — وهو الحدّ الأهمّ فيه."""

    @staticmethod
    def _clean_result(**overrides) -> LoopResult:
        """أفضل حصيلة يمكن بناؤها: لا خطأ، وكل الفحوص معلَنٌ أنها جرت."""
        return run_loop(
            DRAFT,
            forbidden_redraft,
            lambda draft, attempt: (),
            checked_sources=overrides.get("checked_sources", SOURCES),
            max_attempts=overrides.get("max_attempts", DEFAULT_MAX_ATTEMPTS),
        )

    def test_an_unrun_check_is_not_a_clean_check(self):
        """
        🔑 القاعدة المركزية: **الفحص الذي لم يجرِ ليس فحصاً نجح.**

        والحصيلة هنا هي الحصيلة نفسها في الحالتين — لا خطأ في أيّ فحص جرى — ومع
        ذلك **لا يجوز** أن تُقرأ نظافةً كاملة إن كان فحص الوقائع لم يُشغَّل. فقائمة
        الأخطاء الفارغة تعني الشيئين معاً، ولا يفصل بينهما إلا `sources_checked`.
        """
        checked_without_fidelity = sources_checked(
            review_outcome=review_outcome(),
            fidelity_shifts=None,
            attribution_outcome=verify_attributions(
                f"وتنص المادة ٧٥ على: «للمالك أن يطالب بالأجرة المتأخرة».",
                ATTRIBUTION_EVIDENCE,
                lambda row: row.text,
            ),
            language_report=audit_language(CLEAN_DOCUMENT),
        )
        self.assertNotIn(SOURCE_FIDELITY, checked_without_fidelity)
        self.assertEqual(len(checked_without_fidelity), 3)

        blocked = run_loop(
            DRAFT,
            forbidden_redraft,
            lambda draft, attempt: (),
            checked_sources=checked_without_fidelity,
        )
        self.assertEqual(blocked.stopped_reason, STOP_MESSAGES[STOP_CLEAN])
        self.assertEqual(blocked.remaining, ())
        self.assertEqual(blocked.unrun_sources, (SOURCE_FIDELITY,))
        self.assertFalse(blocked.can_be_called_verified)

        # والفرق ليس في الأخطاء — بل في إعلان الفحص وحده.
        declared = self._clean_result(checked_sources=SOURCES)
        self.assertEqual(declared.remaining, blocked.remaining)
        self.assertTrue(declared.can_be_called_verified)

    def test_the_best_result_is_still_not_a_certificate(self):
        """
        أعلى ما يبلغه الملف: الفحوص الأربعة جرت، ولا خطأ، والإيقاف لخلوص الفحص.

        **وهو ليس شهادة على المستند**: هو تقرير عن الفحوص التي جرت، والحدّ مكتوب
        في `describe` نفسه لا في هذا الاختبار وحده.
        """
        result = self._clean_result()

        self.assertEqual(result.stop_code, STOP_CLEAN)
        self.assertEqual(result.attempts_used, 1)
        self.assertEqual(result.unrun_sources, ())
        self.assertTrue(result.can_be_called_verified)

        text = describe(result)
        self.assertIn("تقرير عن الفحوص لا شهادة بصحّة المستند", text)
        self.assertIn("والقرار للمحامي", text)

    def test_a_late_stop_is_not_a_clean_stop(self):
        """التوقّف لسبب آخر **ليس نجاحاً**، ولو خلا آخر فحص من خطأ مادّي."""
        result = run_loop(
            BROKEN_DRAFT,
            lambda draft, errors, attempt: "   ",
            scripted_collect({BROKEN_DRAFT: review_errors()}),
            checked_sources=SOURCES,
        )
        self.assertEqual(result.stop_code, STOP_CLEAN)
        self.assertTrue(result.can_be_called_verified)

        failed = run_loop(
            BROKEN_DRAFT,
            lambda draft, errors, attempt: "   ",
            scripted_collect(
                {BROKEN_DRAFT: review_errors(element("fact", SEVERITY_ERROR, Q_FACT))}
            ),
            checked_sources=SOURCES,
        )
        self.assertEqual(failed.stop_code, STOP_REDRAFT_FAILED)
        self.assertFalse(failed.can_be_called_verified)

    def test_describe_never_says_ready_to_file(self):
        """
        🔑 لا عبارة في `describe` تعني أن المستند صالح للإيداع — **ولا في أحسن
        حصيلة**. و`NEVER_SAY` هي القائمة المعلَنة، والاختبار يمرّ على كل شكل
        مُنتَج: الأفضل، والسقف، وعدم التقارب، وما لا يُصلح، وما فشلت صياغته.
        """
        results = [
            self._clean_result(),
            run_loop(
                BROKEN_DRAFT,
                lambda draft, errors, attempt: f"{BROKEN_DRAFT} #{attempt}",
                scripted_collect(
                    {BROKEN_DRAFT: fidelity_errors(3), f"{BROKEN_DRAFT} #1": fidelity_errors(3)}
                ),
                max_attempts=4,
                checked_sources=SOURCES,
            ),
            run_loop(
                BROKEN_DRAFT,
                forbidden_redraft,
                scripted_collect(
                    {
                        BROKEN_DRAFT: collect_errors(
                            DRAFT,
                            attribution_outcome=verify_attributions(
                                ABSENT_DRAFT, ATTRIBUTION_EVIDENCE, lambda row: row.text
                            ),
                        )
                    }
                ),
                checked_sources=SOURCES,
            ),
            run_loop(
                BROKEN_DRAFT,
                forbidden_redraft,
                scripted_collect(
                    {
                        BROKEN_DRAFT: review_errors(
                            element("arithmetic", SEVERITY_ERROR, Q_ARITH)
                        )
                    }
                ),
                checked_sources=SOURCES,
            ),
            run_loop(
                BROKEN_DRAFT,
                lambda draft, errors, attempt: "",
                scripted_collect(
                    {BROKEN_DRAFT: review_errors(element("fact", SEVERITY_ERROR, Q_FACT))}
                ),
            ),
            self._clean_result(checked_sources=()),
            LoopResult(
                attempts=(),
                final_draft="",
                stopped_reason="لا محاولة",
                material_remaining=(),
                attempts_used=0,
            ),
        ]

        self.assertTrue(NEVER_SAY, "قائمة العبارات الممنوعة فارغة — لا تحرس شيئاً")
        self.assertTrue(results[0].can_be_called_verified, "أفضل حصيلة لم تُبنَ")

        for index, result in enumerate(results):
            text = describe(result)
            for phrase in NEVER_SAY:
                with self.subTest(result=index, phrase=phrase):
                    self.assertNotIn(phrase, text, f"العبارة «{phrase}» ظهرت في الوصف")

    def test_describe_states_what_ran_and_what_did_not(self):
        result = run_loop(
            DRAFT,
            forbidden_redraft,
            lambda draft, attempt: (),
            checked_sources=(SOURCE_REVIEW,),
        )
        text = describe(result)

        self.assertIn("الفحوص التي جرت", text)
        self.assertIn("المراجعة الثانية", text)
        self.assertIn("الفحوص التي لم تُشغَّل", text)
        self.assertIn("وغياب الفحص ليس سلامة", text)
        for source in (SOURCE_FIDELITY, SOURCE_ATTRIBUTION, SOURCE_LANGUAGE):
            with self.subTest(source=source):
                self.assertIn(revision_loop.SOURCE_LABELS[source], text)

    def test_describe_states_the_attempts_and_the_stop_reason(self):
        result = run_loop(
            BROKEN_DRAFT,
            lambda draft, errors, attempt: f"{BROKEN_DRAFT} #{attempt}",
            scripted_collect(
                {BROKEN_DRAFT: fidelity_errors(3), f"{BROKEN_DRAFT} #1": fidelity_errors(2)}
            ),
            max_attempts=2,
        )
        text = describe(result)

        self.assertIn("المحاولات: 2", text)
        self.assertIn("أُصلح خلال الحلقة: 1", text)
        self.assertIn("سبب الإيقاف:", text)
        self.assertIn(STOP_MESSAGES[STOP_CEILING], text)
        self.assertIn("لا يُوصف هذا المستند", text)

    def test_there_is_no_confidence_number_anywhere(self):
        """
        ⚠️ لا رقم ثقة ولا نسبة ولا متوسّط في هذا الملف — **لا في الحصيلة ولا في
        الوصف**. والأرقام الظاهرة كلها **أعداد وقائع**: كم محاولة، وكم خطأ. ولو
        ظهر «ثقة ٠٫٨» لَقُرئ دليلاً على صواب لم يُفحص.
        """
        result = self._clean_result()
        text = describe(result)

        for forbidden in (
            "ثقة",
            "٪",
            "%",
            "confidence",
            "score",
            "متوسّط",
            "average",
            "0.",
            "0٫",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, text)

    def test_the_result_cannot_be_edited_in_place(self):
        result = self._clean_result()
        with self.assertRaises(Exception):
            result.final_draft = "غير ذلك"  # type: ignore[misc]


# ==============================================================================
# ٩. ضمانات على الوحدة نفسها
# ==============================================================================


class TestModuleGuarantees(unittest.TestCase):
    """ضمانات معمارية — كـ`citations.py`: بلا تبعيات ثقيلة، وبلا شبكة، وبلا حالة."""

    def _source(self) -> str:
        return pathlib.Path(revision_loop.__file__).read_text(encoding="utf-8")

    def test_imports_are_stdlib_only_plus_the_named_modules(self):
        """
        الضمان الذي يجعل هذه الحلقة تعمل في الاختبار بلا نموذج وبلا مفتاح ولا
        شبكة. والفحص على **المصدر** لا على أثر التشغيل.
        """
        imported = set(
            re.findall(
                r"^(?:from|import)\s+([A-Za-z_][\w\.]*)",
                self._source(),
                re.MULTILINE,
            )
        )
        allowed = {
            "__future__",
            "dataclasses",
            "enum",
            "typing",
            "attribution",
            "citations",
            "facts",
            "language_audit",
            "review",
        }
        self.assertTrue(imported <= allowed, f"استيرادات: {sorted(imported - allowed)}")

    def test_no_environment_network_or_output(self):
        """لا تُقرأ بيئة، ولا تُفتح شبكة، ولا يُطبع شيء — الحلقة صامتة."""
        source = self._source()
        for forbidden in (
            "os.environ",
            "getenv",
            "requests.",
            "urllib",
            "socket",
            "http",
            "print(",
            "open(",
        ):
            self.assertNotIn(forbidden, source, f"الوحدة تحتوي «{forbidden}»")

    def test_it_does_not_re_define_the_project_thresholds(self):
        """
        لا عتبة ثانية في هذا الملف: هو يجمع ولا يفحص نصّاً، ومع ذلك لا يُعرَّف
        فيه تطبيع ولا عتبة اقتباس — يُستوردان من `citations.py`.
        """
        source = self._source()
        self.assertNotIn("MIN_QUOTE_CHARS =", source)
        self.assertNotIn("def normalize", source)
        self.assertNotIn("maketrans", source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
