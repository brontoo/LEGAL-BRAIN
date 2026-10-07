"""
اختبارات التقرير الداخلي — المخرج الثاني، المفصول عن المذكرة.
=============================================================================

تشغيل:
    python -m unittest discover -s tests -t . -v

حتمية بالكامل: بلا شبكة وبلا نموذج وبلا قاعدة بيانات وبلا قرص.

ولماذا هذا الملف موجود
----------------------
ثلاث مراجعات مستقلّة وجدت أن مذكرات هذا المشروع وُصفت بالاكتمال وفيها أساس
أجرٍ خاطئ وتاريخ خاطئ ومادة منسوبة إلى غير مادّتها وواقعة مُغيَّرة ثلاث مرّات.
فالعيب لم يكن في الصياغة وحدها، بل في **عرض عمل لم يُتحقَّق منه على أنه منتهٍ**.

ولذلك أهمّ اختبارين هنا:

* `test_a_missing_check_is_not_a_passing_check` — الفحص الذي لم يجرِ يُعرَض
  غائباً ويُعدّ ثغرةً بمستوى خطأ، ولا يُقرأ سلامةً. وهذا سبب وجود الملف.
* `test_nothing_is_ever_reported_ready_to_file` — ولا مدخل واحد يُنتج عبارةً
  معناها أن المستند جاهز للإيداع، **ولا حتى المدخل النظيف تماماً**.

⚠️ الأشكال المتوقَّعة في هذا الملف **تُبنى من الوحدات نفسها لا بيد**:

* `citations.py` — **لا يوجد فيها `summarize`**. شكل ملخّصها يُبنى في
  `main.py::_verify_round`، فيبنيه هنا **مساعد واحد** (``citation_report``)
  بالمفاتيح نفسها التي يكتبها `main.py`، **ومنه ``attribution`` المتداخل** —
  ويستدعيه كل اختبار، فلا يفترق شكل عن شكل.
* `review.py` · `attribution.py` · `language_audit.py` — ملخّصاتها تُبنى
  بدالّات ``summarize`` الحقيقية.
* `case_file.py` · `facts.py` — **مدخلان لا فحصان**: لا ``summarize`` في
  `case_file.py`، و`facts.py::summarize` لا يُنتج ``error_count``. فلا يُبنى
  لهما شكل نظيف من وحدات المشروع، ولذلك لا يحكمان الدرجة (``INPUT_KINDS``) —
  ويُختبر ذلك صراحةً في `test_the_inputs_are_reported_but_do_not_gate`.

⛔ **والعطب الذي جعل هذا التغيير لازماً مسجَّل هنا**: الاختبار كان يبني مدخلاته
قاموساً بيده بمفاتيح لا يُنتجها مستدعٍ، فكان **يمرّ على شكل لم تره الخدمة قطّ**:
ملف الدعوى والوقائع يُمرَّران فيه، و`main.py` لا يمرّرهما. فصار كل نداء حقيقي
«ناقص الفحص»، وتساوى الغائبُ النظيفَ في الرتبة — وهو العيب الذي وُلد الملف
لمنعه — وصارت ``verified`` غير قابلة للبلوغ. فالاختبار كان **يشهد لعطبٍ لا وجود
له**، وهذا أسوأ من غياب الاختبار.
"""

import json
import re
import unittest

from attribution import AttributionOutcome, summarize as summarize_attribution
from attribution import verify_attributions
from briefing import (
    CHECK_KINDS,
    DASH,
    EXPECTED_KINDS,
    INPUT_KINDS,
    SAFETY_PARTLY,
    SAFETY_UNVERIFIED,
    SAFETY_VERIFIED,
    InternalReport,
    Source,
    build,
    gather,
    readiness,
    safety_rank,
    to_json,
)
from citations import (
    Evidence,
    normalize,
    parse_citations,
    strip_citations_block,
    unbacked_article_refs,
    verify_citations,
)
from language_audit import audit_language, summarize as summarize_language_audit
from review import parse_review, summarize as summarize_review

# ------------------------------------------------------------------------------
# المنع المطلق: العبارات التي لا يجوز أن تُكتب في أي مخرج
# ------------------------------------------------------------------------------
# ⚠️ **وهي مكتوبة عربيةً هنا لا في `briefing.py`**، وهذا مقصود: لو كُتبت هناك
# ثابتاً لظهرت في الملف المُنتَج، ولو ظهرت في تعليق لاحتمل أن تُنسخ إلى نصّ.
# فالكلمة المحرّمة تُعرف في الاختبار وحده، والاختبار يفحص كل مخرج ممكن.
FORBIDDEN_READY_PHRASES = (
    "جاهز للإيداع",
    "جاهزة للإيداع",
    "جاهز للاكتتاب",
    "صالح للإيداع",
)

#: وثلاث صيغ أخرى تُمنع في نصّ **الملف** نفسه، لأن التعليق يُنسخ: سطرٌ يشرح
#: المنع يحمل العبارة، ونسخةٌ منه في نصّ كافٍ لأن تظهر للمحامي. فالمصدر كلّه
#: مفحوص — والاختبار أعلاه يفحص المخرج حيث لا تظهر هذه الصيغ أصلاً.
FORBIDDEN_SOURCE_PHRASES = FORBIDDEN_READY_PHRASES + (
    "ready to file",
    "صالح للاكتتاب",
    "جاهز للاستخدام",
)


def _all_output_text(report: InternalReport) -> str:
    """
    كل نصّ يستطيع المحامي أن يراه عن هذا التقرير، مجموعاً.

    ⚠️ ويشمل ``safety`` و``headline`` صراحةً لا ``to_markdown`` وحده: العبارة
    التي تُمنع في المستند قد تُكتب في سطر الحالة، وهو أوّل ما يُقرأ.
    """
    return "\n".join(
        (
            report.safety,
            report.headline,
            report.to_markdown(),
            to_json(report),
        )
    )


def _missing_text(report: InternalReport) -> str:
    """
    نصّ «ما ينقص» و«المخاطر» و«ما يحتاج مراجعة بشرية»، مجموعاً.

    ⚠️ **ولا يُختبر الغياب على ``to_markdown`` وحده**: الغياب يُسجَّل في ثلاث
    مجموعات، ومن اختبر واحدة ظنّ أنّ الأخرى لا تُبلِّغ.
    """
    return "\n".join(
        (*report.gaps, *report.risks, *report.needs_review)
    )


def _labels() -> dict:
    """اسم كل نوع بالعربية — من الوحدة لا من نصّ مكتوب في الاختبار."""
    return {source.kind: source.label for source in gather(None)}


def _citation_row(report: InternalReport) -> str:
    """صفّ الأسانيد في جدول المصادر — للشهادة على عرض الأعداد."""
    label = _labels()["citation"]
    return next(
        line for line in report.to_markdown().splitlines() if f"| {label} |" in line
    )


# ------------------------------------------------------------------------------
# بناء ملخّص الأسانيد الحقيقي — بالمفاتيح التي يكتبها `main.py::_verify_round`
# ------------------------------------------------------------------------------

EVIDENCE = (
    Evidence(
        ref="L1",
        chunk_id="7",
        document_name="قانون المعاملات المدنية",
        text="المادة 246: لكلّ دعوى أن تُقام أمام المحكمة المختصّة.",
        similarity=0.91,
        tool="legislation",
    ),
    Evidence(
        ref="C1",
        chunk_id="12",
        document_name="عقد إيجار سكني",
        text="يلتزم المستأجر بسداد الأجرة الشهرية في الأوّل من كلّ شهر.",
        similarity=0.88,
        tool="contracts",
    ),
)


def citation_report(raw_draft: str, evidence=EVIDENCE) -> dict:
    """
    ملخّص الأسانيد كما يُبنى في `main.py::_verify_round` — **بالمفاتيح نفسها**.

    ⛔ **وهذا المساعد هو الوحيد الذي يُبنى فيه شكل الأسانيد في هذا الملف**،
    ويستدعيه كل اختبار. والسبب مسجَّل: أول نسخة بنت المدخلات قواميس بيد داخل كل
    اختبار، فاخترعت مفاتيح لا يُنتجها `_verify_round` — **ومنها غياب
    ``attribution`` المتداخل** — فمرّت الاختبارات على شكل لا تراه الخدمة قطّ.

    ⚠️ **وعليه: كل مفتاح يكتبه `_verify_round` يُكتب هنا، ومنه ``attribution``
    المتداخل (فحص ثالث لا يقيسه `verify_citations`).** ومتى تغيّر
    `_verify_round` وجب تحديث هذا المساعد معه، وإلا عاد العيب نفسه: اختبارٌ
    يشهد لشكلٍ متخيَّل.

    ولا تُستدعى دالّة خاصة من `main.py` (فاستيراد خادم الويب في اختبار وحدة
    عيب)، بل تُعاد صياغة التعبير نفسه من واجهة `citations.py` العامة.
    """
    parsed = parse_citations(raw_draft)
    outcome = verify_citations(parsed.citations, list(evidence))
    clean = strip_citations_block(raw_draft)
    unbacked = unbacked_article_refs(clean, list(evidence))

    return {
        "summary": outcome.summary(),
        "has_evidence": outcome.has_evidence,
        "evidence_count": len(evidence),
        "has_citation_block": parsed.has_block,
        "verified": [
            {
                "ref": item.ref,
                "document_name": item.document_name,
                "chunk_id": item.chunk_id,
                "quoted_span": item.quoted_span,
                "similarity": item.similarity,
            }
            for item in outcome.verified
        ],
        "rejected": [
            {"ref": item.ref, "quoted_span": item.quoted_span, "reason": item.reason}
            for item in outcome.rejected
        ],
        "unbacked_articles": [
            {"surface": ref.surface, "number": ref.number} for ref in unbacked
        ],
        "malformed_lines": parsed.malformed,
        # ⚠️ وهذا المفتاح المتداخل كان **غائباً** من المساعد الأول، وهو الفحص
        # الثالث في `_verify_round`: نسبة النصّ إلى مادّته. فغيابه من الاختبار
        # يعني أن الشكل الذي جرّبه الاختبار ليس الشكل الذي يُرسله `main.py`.
        "attribution": summarize_attribution(
            verify_attributions(clean, list(evidence), lambda row: row.text)
        ),
    }


#: مسودّة كلّ أسانيدها صحيحة، وفيها مادة واحدة بلا سند وموادّ لها سند.
DRAFT_ONE_UNBACKED = (
    "يستند المدّعي إلى المادة 246 من قانون المعاملات المدنية.\n"
    "ويلتزم المستأجر بسداد الأجرة عملاً بالمادة 999.\n"
    "\n"
    "[[الأسانيد]]\n"
    "L1 :: لكلّ دعوى أن تُقام أمام المحكمة المختصّة\n"
    "[[/الأسانيد]]"
)

#: مسودّة فيها سند مرفوض (نصّه ليس في المقطع) وسطر سند مشوّه.
DRAFT_WITH_REJECTED = (
    "يلتزم المستأجر بسداد الأجرة الشهرية.\n"
    "\n"
    "[[الأسانيد]]\n"
    "C1 :: الأجرة تُسدد كلّ ثلاثة أشهر مقدّماً\n"
    "سطر بلا فاصل\n"
    "[[/الأسانيد]]"
)

#: مسودّة نظيفة تماماً: سند واحد موجود حرفياً، ولا مادة بلا سند.
DRAFT_CLEAN = (
    "تنتقل الملكية بالتسليم.\n"
    "\n"
    "[[الأسانيد]]\n"
    "C1 :: يلتزم المستأجر بسداد الأجرة الشهرية\n"
    "[[/الأسانيد]]"
)

#: جملة عربية سليمة تمرّ من `language_audit.py` بلا خطأ ولا ملاحظة.
CLEAN_SENTENCE = "البند الأول: يلتزم الطرف الثاني بالسداد في الأوّل من كلّ شهر."


def failed_review_report() -> dict:
    """
    ما يُرجعه `main.py::_review_round` **حين يفشل النداء** — بنصّه الحرفي.

    ⚠️ **والخطر فيه أنه يصل ``clean: True`` ومعه ``error_count: 0``**: من قرأ
    ``clean`` قدّمه على ``failed`` حسبه فحصاً نجح، وهو لم يحدث قطّ. ولذلك لا
    يُكتب هذا الشكل بيدٍ إلا هنا مرّة واحدة، ليُشهد عليه في اختبارين.
    """
    return {
        "summary": "تعذّرت المراجعة الثانية: TimeoutError",
        "clean": True,
        "error_count": 0,
        "notice_count": 0,
        "dropped": 0,
        "findings": [],
        "failed": True,
    }


def clean_checks() -> dict:
    """
    **الفحوص الأربعة كلّها، حاضرةً ونظيفة** — مدخلاتها من وحداتها الحقيقية.

    ⚠️ **ولا يُضاف هنا مدخل، ولا يُبنى قاموس فحص بيد.** كل ملخّص يأتي من
    ``summarize`` الحقيقية (أو من ``citation_report`` الذي يحاكي
    `_verify_round`). وهذا هو المدخل الذي يجب أن يبلغ الدرجة العليا: مَن أراد أن
    يعرف أيّ فحص يمنع ``verified`` فليُغبْه من هذه القائمة ويرَ الرتبة.

    ⛔ **ولماذا أربعة لا ستّة؟** لأن ``case_file`` و``facts`` **مدخلان لا
    فحوص**، ولا وحدة في المشروع تُنتج لهما «حالاً نظيفة»: لا ``summarize`` في
    `case_file.py`، و`facts.py::summarize` لا يُنتج ``error_count``. فتمريرهما
    هنا كان سيُنتج **شكلاً لا يمرّره أي مستدعٍ** — وهو العطب نفسه في صورة أخرى.
    ويُختبر غيابهما في `test_the_inputs_are_reported_but_do_not_gate`.
    """
    reports: dict = {
        "citation": citation_report(DRAFT_CLEAN),
        "attribution": summarize_attribution(AttributionOutcome()),
        "review": summarize_review([], 0),
        "language": summarize_language_audit(audit_language(CLEAN_SENTENCE)),
    }
    assert tuple(reports) == CHECK_KINDS, (
        f"مدخل نظيف ناقص فحصاً: {tuple(reports)} != {CHECK_KINDS}"
    )
    return reports


def clean_reports() -> dict:
    """
    المدخل الكامل: **الفحوص كلّها نظيفة، والمدخلان حاضرَين أيضاً**.

    ⚠️ و``case_file`` و``facts`` هما **شكل ما يمرّره المستدعي**، لا ما تُنتجه
    وحدة: يُمرَّران هنا لغرضين — أن تُختبر صفوفهما في التقرير، وأن يُشهد أنّ
    **حضورهما لا يغيّر الدرجة** لأن لا عدّ يُقرأ لهما (``errors`` تبقى ``None``
    فتُعرض ``—``، وهذا هو الصواب: لا يُكتب صفر لمصدر لم يُبلَّغ عن عدده).
    """
    reports: dict = dict(clean_checks())
    reports["case_file"] = {"summary": "ملف الدعوى قد أُرسل (حالة اختبار)."}
    reports["facts"] = {"summary": "الوقائع قد أُرسلت (حالة اختبار)."}
    assert tuple(reports) == EXPECTED_KINDS, (
        f"ترتيب الأنواع تغيّر: {tuple(reports)} != {EXPECTED_KINDS}"
    )
    return reports


class TestAMissingCheckIsNotAPassingCheck(unittest.TestCase):
    """
    🔑 **الفحص الذي لم يجرِ ليس فحصاً نجح** — وهذه هي علّة وجود الملف.

    والكودبيس تعلّم هذا الدرس مرّة في `frontend/components/review-panel.tsx`:
    كان الشكل يصل `failed: True` ومعه `clean: True` و`error_count: 0` (انظر
    `_review_round` في `main.py`)، فلو قُدِّم `clean` على `failed` لقيل
    «سليمة» عن مراجعة لم تحدث قطّ.
    """

    def test_a_missing_check_is_not_a_passing_check(self):
        reports = {
            "citation": citation_report(DRAFT_CLEAN),
            "language": summarize_language_audit(audit_language("البند الأول: السداد.")),
            # `attribution` · `review` · `case_file` · `facts` لم تُشغَّل.
        }
        report = build(reports)

        by_kind = {source.kind: source for source in report.sources}

        # ١) كل نوع متوقَّع يظهر، والغائب منها يظهر غائباً صريحاً.
        self.assertEqual(tuple(by_kind), EXPECTED_KINDS)
        self.assertFalse(by_kind["attribution"].present)
        self.assertFalse(by_kind["review"].present)
        self.assertFalse(by_kind["case_file"].present)
        self.assertFalse(by_kind["facts"].present)
        self.assertTrue(by_kind["citation"].present)
        self.assertTrue(by_kind["language"].present)

        # ٢) ونصّ الغائب يقول «لم يُشغَّل» ولا يقول سلامة.
        self.assertIn("لم يُشغَّل", by_kind["review"].summary)
        self.assertNotIn("سليم", by_kind["review"].summary)

        # ٣) ويُعدّ ثغرةً بمستوى خطأ — لا ملاحظة.
        gap_text = "\n".join(report.gaps)
        self.assertIn("المراجعة الثانية: لم يُشغَّل الفحص", gap_text)
        self.assertIn("ملف الدعوى: لم يُشغَّل الفحص", gap_text)

        # ٤) ويمنع بلوغ الدرجة العليا — وهذا هو الأثر العملي للقاعدة.
        self.assertEqual(report.safety, SAFETY_PARTLY)
        self.assertNotEqual(report.safety, SAFETY_VERIFIED)

        # ٥) ويُطلب على مراجعة بشرية صراحةً.
        review_text = "\n".join(report.needs_review)
        self.assertIn("المراجعة الثانية لم يُشغَّل", review_text)

    def test_a_failed_check_is_a_missing_check_and_never_clean(self):
        """
        ⚠️ **الحالة الواقعية**: `_review_round` يفشل فيُرجع ``failed: True``
        ومعه ``clean: True`` و``error_count: 0``.

        فلو قرأ هذا الملف `clean` لحسب المراجعة **ناجحة**، وهي لم تحدث. وتقديم
        `failed` على `clean` هو الترتيب نفسه الذي فُرض في `review-panel.tsx`.
        """
        report = build({"review": failed_review_report()})
        source = {item.kind: item for item in report.sources}["review"]

        self.assertFalse(source.present, "المراجعة الفاشلة ليست مراجعة جرت")
        self.assertIn("تعذّر", source.summary)
        self.assertNotEqual(report.safety, SAFETY_VERIFIED)

    def test_nothing_running_at_all_is_unverified(self):
        """لا ملخّص واحد: لا يُبنى على المسودّة حكم، والدرجة الدنيا."""
        report = build({})
        self.assertEqual(report.safety, SAFETY_UNVERIFIED)
        self.assertIn("لم يجرِ فحص واحد", report.headline)
        self.assertEqual(len(report.sources), len(EXPECTED_KINDS))


class TestAMissingCheckIsStrictlyWorseThanACleanOne(unittest.TestCase):
    """
    🔑 **الفحص الغائب يخفض الدرجة، ولا يكتفي بأن يغيّر النصّ.**

    وهذا هو العيب الحقيقي الذي كشفته مراجعة هذا الملف بعد كتابته: كانت
    ``_count`` ترفض **القوائم**، و`citations.py` لا تُبلغ بعدّاد أصلاً بل
    بقوائم (``rejected`` · ``unbacked_articles`` · ``malformed_lines``). فحُسب
    كلُّ ملخّص أسانيد ``None`` — «لم يُبلَّغ عن عدد» — **حتى وهو يقول ``[]``**.

    وكانت النتيجة أن المدخل النظيف والمدخل الناقص **يبلغان الدرجة نفسها**،
    فيقرأ المحامي توصيةً واحدة عن مسودّة فُحصت كلها وعن مسودّة لم تُفحص
    أسانيدها. وهو بعينه العيب الذي وُلد هذا الملف لمنعه: **عرضُ ما لم يُتحقَّق
    منه على أنه منتهٍ**.
    """

    def test_a_missing_check_is_strictly_worse_than_a_clean_one(self):
        """
        🔑 **والفحص الغائب أدنى رتبةً من الفحص النظيف — لكل فحص، واحداً واحداً.**

        ⛔ **وهذا الاختبار كان يمرّ على عطبٍ حقيقي.** كان يدور على
        ``EXPECTED_KINDS`` ستّاً، والمدخل النظيف عنده **قاموس مكتوب بيد** فيه
        ``case_file`` و``facts`` بمفتاح ``error_count: 0`` — **وهو شكل لا
        يُنتجه مستدعٍ ولا وحدة**. فكان يمرّ، والواقع أنّ كل نداء حقيقي يمرّر
        الأربعة وحدها فيهبط إلى ``partly_verified`` أبداً، **فتساوي الغائبُ
        النظيفَ في الرتبة**. فالاختبار كان يشهد لسلوك لا وجود له.

        والآن يدور على :data:`CHECK_KINDS` — الفحوص التي تُنتج ملخّصاتها وحدات
        المشروع فعلاً — ومدخلاته من ``summarize`` الحقيقية.
        """
        clean = build(clean_reports())
        # ١) **ولا يُقاس غيابٌ على درجة لم تُبلَغ**: النظيف يبلغ العليا أولاً.
        self.assertEqual(
            clean.safety, SAFETY_VERIFIED, "المدخل النظيف لم يبلغ الدرجة العليا"
        )

        # ٢) وكل فحص يُغاب وحده، فتُقاس رتبته على رتبة النظيف — **أدنى لا مختلفة**.
        for kind in CHECK_KINDS:
            with self.subTest(removed=kind):
                partial = clean_reports()
                partial[kind] = None
                report = build(partial)
                self.assertGreater(
                    safety_rank(report.safety),
                    safety_rank(clean.safety),
                    f"غياب «{kind}» لم يخفض الدرجة عن {clean.safety}",
                )
                self.assertNotEqual(report.safety, SAFETY_VERIFIED)
                # ويُسجَّل الغياب نصّاً أيضاً، فلا يُخفى وإن خفض الدرجة.
                self.assertIn(_labels()[kind], _missing_text(report))

    def test_a_failed_review_is_strictly_worse(self):
        """
        ⛔ **مراجعةٌ لم تحدث لا تُقرأ مراجعةً نظيفة — ولو قالت ``clean: True``.**

        وهذا بعينه ما تعلّمه `review-panel.tsx`: الشكل الفاشل يصل ومعه
        ``clean: True`` و``error_count: 0``، فمن قدّم ``clean`` على ``failed``
        أنتج لوحةً تقول «سليمة» عن مراجعة **لم تحدث قطّ**.
        """
        clean = build(clean_reports())
        self.assertEqual(clean.safety, SAFETY_VERIFIED)

        failed = clean_reports()
        failed["review"] = failed_review_report()
        failed_report = build(failed)

        source = {item.kind: item for item in failed_report.sources}["review"]
        self.assertFalse(source.present, "المراجعة الفاشلة عُدّت مراجعةً جرت")
        self.assertIsNotNone(failed_report.safety)
        self.assertGreater(
            safety_rank(failed_report.safety),
            safety_rank(clean.safety),
            "المراجعة الفاشلة لم تُخفض الدرجة عن المراجعة النظيفة",
        )
        # ⛔ ولا تكفي مخالفة النصّ: الرتبة نفسها يجب أن تضعف.
        self.assertNotEqual(failed_report.safety, clean.safety)

    def test_an_error_count_is_strictly_worse_than_clean(self):
        """
        و**الفحص الذي جرى وأبلغ عن خطأ** أدنى رتبةً من الفحص الذي جرى ونظف —
        وإلا لكان وجود العيب وعدمه سواءً في التوصية.
        """
        clean = build(clean_reports())
        dirty = clean_reports()
        dirty["citation"] = citation_report(DRAFT_WITH_REJECTED)
        dirty_report = build(dirty)

        source = {item.kind: item for item in dirty_report.sources}["citation"]
        self.assertTrue(source.present, "الفحص الذي أبلغ عن خطأ فحصٌ جرى")
        self.assertTrue(source.errors, "الاختبار يحتاج خطأً مُبلَّغاً عنه فعلاً")
        self.assertGreater(
            safety_rank(dirty_report.safety),
            safety_rank(clean.safety),
            "الفحص الذي أبلغ عن خطأ لم يخفض الدرجة",
        )

    def test_the_inputs_are_reported_but_do_not_gate(self):
        """
        🔑 **والفرق بين فحصٍ ومدخل — وهو ما كان مخفياً فصار معلَناً.**

        ملف الدعوى والوقائع **يُبلَّغ عن غيابهما** (في «ما ينقص» وعلى قائمة
        المراجعة البشرية، فلا يُخفى)، **ولا يُقاس عليهما حكم**، لأن لا وحدة في
        المشروع تُنتج لهما ملخّصاً بعدّ: لا ``summarize`` في `case_file.py`،
        و`facts.py::summarize` لا يُنتج ``error_count``.

        ⛔ **وإدخالهما في حكم الدرجة كان العطب**: لا مستدعٍ يمرّرهما، فصار كل
        نداء حقيقي «ناقص الفحص» أبداً، وتساوى الغائبُ النظيفَ في الرتبة، وصارت
        ``verified`` وعداً لا يُوفى.
        """
        self.assertEqual(INPUT_KINDS, ("case_file", "facts"))
        self.assertEqual(set(CHECK_KINDS) | set(INPUT_KINDS), set(EXPECTED_KINDS))
        self.assertEqual(set(CHECK_KINDS) & set(INPUT_KINDS), set())

        # حاضرَين: لا يرفعان الدرجة ولا يخفضانها، ولا يُعرض لهما صفر مخترع،
        # ولا يُشكى من عدّ غائب لا وجود له في المشروع أصلاً.
        with_inputs = build(clean_reports())
        self.assertEqual(with_inputs.safety, SAFETY_VERIFIED)
        by_kind = {item.kind: item for item in with_inputs.sources}
        for kind in INPUT_KINDS:
            self.assertTrue(by_kind[kind].present)
            # ⚠️ ``—`` لا ``0``: لم يُبلَّغ عن عدّ لهذين، ولا يُخترع.
            self.assertIsNone(by_kind[kind].errors)
            self.assertIsNone(by_kind[kind].notices)
        self.assertEqual(
            with_inputs.risks,
            (),
            "المدخل الحاضر أنتج سطر خطر — والقسم يُقرأ ضجيجاً حينها",
        )
        self.assertNotIn(
            "لم يُبلَّغ عن عدد",
            "\n".join(with_inputs.gaps),
            "المدخل لا عدّ له، فطلبُ عدّه سطرٌ في كل تقرير عن لا شيء",
        )

        # وغائبان: يُسجَّل غيابهما ولا يخفضان الدرجة على الأربعة النظيفة.
        without_inputs = build(clean_checks())
        self.assertEqual(
            without_inputs.safety,
            SAFETY_VERIFIED,
            "غياب المدخلين خفض الدرجة — وهو العطب الذي منع بلوغ verified",
        )
        for kind in INPUT_KINDS:
            with self.subTest(missing=kind):
                report = build({**clean_checks(), kind: None})
                self.assertEqual(report.safety, SAFETY_VERIFIED)
                source = {item.kind: item for item in report.sources}[kind]
                self.assertFalse(source.present)
                self.assertIn("لم يُشغَّل", source.summary)
                self.assertIn("لم يُشغَّل الفحص", _missing_text(report))
                self.assertIn("لم يُشغَّل", "\n".join(report.needs_review))

    def test_an_empty_list_is_a_reported_zero_and_a_missing_key_is_a_gap(self):
        """
        ⚠️ **قاعدة مستقرّة في هذا الكودبيس: ``[]`` إبلاغٌ عن صفر، والغياب عن
        «لا أعرف» — و``0`` حيث لا يُعرف كذبٌ صغير يُبنى عليه قرار.**

        ولا تُخلط الصورتان في مخرج واحد: ``rejected: []`` تُعرض ``0``، وحذف
        المفتاح يُعرض ``—``.
        """
        # صورة الإبلاغ بالقائمة الفارغة: صفرٌ مُبلَّغ به، ويُعرض صفراً.
        reported = citation_report(DRAFT_CLEAN)
        self.assertEqual(reported["rejected"], [])
        report = build({**clean_checks(), "citation": reported})
        source = {item.kind: item for item in report.sources}["citation"]
        self.assertEqual(source.errors, 0)
        self.assertEqual(source.notices, len(reported["malformed_lines"]))
        self.assertNotIn(f"| {DASH} |", _citation_row(report))
        self.assertEqual(report.safety, SAFETY_VERIFIED)

        # وصورة الغياب: ``—`` لا صفر، ونصّ صريح بأن العدد لم يُبلَّغ به.
        absent = citation_report(DRAFT_CLEAN)
        del absent["rejected"]
        absent_report = build({**clean_checks(), "citation": absent})
        absent_source = {item.kind: item for item in absent_report.sources}["citation"]
        self.assertIsNone(absent_source.errors)
        self.assertIn(f"| {DASH} |", _citation_row(absent_report))
        self.assertIn("لم يُبلَّغ عن عدد الأخطاء", _missing_text(absent_report))
        self.assertGreater(
            safety_rank(absent_report.safety), safety_rank(report.safety)
        )

    def test_a_clean_check_is_strictly_better_than_a_failed_one(self):
        """و`failed: True` كالغياب: المراجعة التي لم تحدث لا ترفع الدرجة."""
        failed = clean_reports()
        failed["review"] = failed_review_report()
        self.assertGreater(
            safety_rank(build(failed).safety), safety_rank(build(clean_reports()).safety)
        )

    def test_a_number_carried_in_a_list_is_a_number_not_a_gap(self):
        """
        ⚠️ **اختبار انحدار على العيب نفسه.**

        ``rejected: []`` إبلاغٌ عن **صفر** لا عن «عدد غير معروف». ومن نادى
        ``_count([])`` وحصل على ``None`` جعل كل مسودّة بلا سند مرفوض تُقرأ
        «لم يُبلَّغ عن عدد الأخطاء»، ثم منع الدرجة العليا عنها دائماً.
        """
        clean = build(clean_reports())
        citation = {item.kind: item for item in clean.sources}["citation"]
        self.assertEqual(citation.errors, 0)
        self.assertNotIn("لم يُبلَّغ عن عدد الأخطاء", "\n".join(clean.gaps))

        # وبالمقابل: قائمة غير فارغة عددٌ موجب.
        rejected = {item.kind: item for item in build(
            {"citation": citation_report(DRAFT_WITH_REJECTED)}
        ).sources}["citation"]
        # ⚠️ ولا تُعدّ الأسطر المشوّهة هنا: موضعها «ما ينقص» (سند ضائع) لا
        # «الأخطاء»، لأن الخطأ قولٌ في المسودّة والسطر المشوّه نقصٌ في قراءتها.
        self.assertEqual(rejected.errors, 1)
        self.assertGreater(rejected.errors, 0)

    def test_verified_is_reachable_or_absent(self):
        """
        ⚠️ **والدرجة العليا إمّا تُبلَغ وإمّا لا وجود لها.**

        حالةٌ في التوقيع لا يمكن بلوغها كذبةٌ في العقد: تقول لمن يقرأ النوع إن
        ثمّة نجاحاً ممكناً، ثم لا تبلغه مسودّة قطّ. وأفضل مدخل ممكن هو كل فحص
        متوقَّع حاضر، وكل عدد مُرسل صفراً، ولا دعوى غير موثَّقة، ولا سؤال مفتوح.

        ⛔ **وقد كانت غير قابلة للبلوغ فعلاً** حين حكم في الدرجة نوعان لا
        يُنتجهما مستدعٍ. فصار الحارس هنا يدور على الفحوص وحدها، ويشهد أنّ
        **نقصاً واحداً فيها** كافٍ لمنعها.
        """
        self.assertEqual(build(clean_checks()).safety, SAFETY_VERIFIED)
        # ولا يبلغها نقصٌ واحد — لا فحصاً ولا عدداً ولا سؤالاً.
        for kind in CHECK_KINDS:
            partial = clean_checks()
            partial[kind] = None
            self.assertNotEqual(build(partial).safety, SAFETY_VERIFIED)
        with_question = build(clean_checks(), open_questions=("هل صُدّق الإخطار؟",))
        self.assertNotEqual(with_question.safety, SAFETY_VERIFIED)

    def test_the_clean_case_still_never_says_ready(self):
        """والضمان الأصلي يبقى على **أفضل** مدخل ممكن، لا على الأنظف وحده."""
        best = build(clean_reports())
        self.assertEqual(best.safety, SAFETY_VERIFIED)
        text = _all_output_text(best)
        for phrase in FORBIDDEN_READY_PHRASES:
            self.assertNotIn(phrase, text)


class TestNothingIsEverReportedReadyToFile(unittest.TestCase):
    """
    🔑 **ولا مدخل واحد يُنتج عبارةً معناها الجاهزية للإيداع.**

    وهذه هي الجملة التي بُنيت عليها الحاجة: «لا تصف النتيجة بأنها جاهزة
    للإيداع تلقائياً؛ بيّن حالة التحقّق وما بقي مطلوباً، واترك القرار للمستخدم».
    """

    def test_nothing_is_ever_reported_ready_to_file(self):
        clean = build(clean_reports())
        # المدخل النظيف تماماً يبلغ أعلى درجة — وهي تقرير عن الفحوص لا شهادة.
        self.assertEqual(clean.safety, SAFETY_VERIFIED)

        for report, label in (
            (clean, "نظيف"),
            (build({}), "لا شيء"),
            (build({"citation": citation_report(DRAFT_WITH_REJECTED)}), "سند مرفوض"),
            (build(clean_reports(), open_questions=("هل صُدّق الإخطار؟",)), "سؤال مفتوح"),
            (build(clean_reports(), notes={"conflicts": ("تاريخان متعارضان.",)}), "تعارض"),
        ):
            with self.subTest(case=label):
                text = _all_output_text(report)
                for phrase in FORBIDDEN_READY_PHRASES:
                    self.assertNotIn(phrase, text, f"ظهرت في الحالة: {label}")

    def test_the_clean_headline_says_what_was_checked_not_that_it_is_approved(self):
        """
        أنظف حالة تقول **ما الذي تُحقّق منه** — لا أن المستند صار صالحاً.

        والفرق ليس لفظياً: الفحوص تغطّي ما تُغطّيه وحدها، وحكم القيمة القانونية
        للمحامي لا لهذا الملف.
        """
        clean = build(clean_reports())
        self.assertIn("كل فحص متوقَّع جرى", clean.headline)
        self.assertIn("القرار قرار المحامي", clean.headline)
        self.assertIn("لا شهادة", clean.headline)

    def test_the_output_never_uses_the_word_clean_for_the_document(self):
        """
        ولا تُنقل كلمة الوحدات ``clean`` إلى نصّ التقرير، لأن معناها هناك «لا
        خطأ مُبلَّغ عنه» — وهي تُقرأ في العربية «سليم»، وهي أوسع ممّا شُهد به.
        """
        for report in (build(clean_reports()), build({})):
            text = report.to_markdown()
            self.assertNotIn("clean", text)
            self.assertNotIn("المستند سليم", text)


class TestAnUnavailableNumberPrintsAsADashNotZero(unittest.TestCase):
    """
    **الرقم الذي لا يُحسب لا يُعرض.** والقاعدة المستقرّة في هذا الكودبيس: عرض
    ``0`` مكان ``—`` كذبٌ صغير يُبنى عليه قرار — «لم يُبلَّغ عن عدد» ليست «صفر».
    """

    def test_an_unavailable_number_prints_as_a_dash_not_zero(self):
        # ملخّص أسانيد فيه سند مرفوض، ثم **تُحذف** قائمة ``rejected`` من الإرسال
        # كلّه — فلم يبقَ في الإرسال عددٌ يُشتقّ منه `error_count`.
        summary = citation_report(DRAFT_WITH_REJECTED)
        self.assertTrue(summary["rejected"], "الاختبار يحتاج سناً مرفوضاً فعلاً")
        del summary["rejected"]

        report = build({"citation": summary, "language": clean_reports()["language"]})
        source = {item.kind: item for item in report.sources}["citation"]

        self.assertIsNone(source.errors, "غياب العدد يجب أن يبقى None لا صفراً")
        self.assertIn(f"| {DASH} |", report.to_markdown())
        self.assertIn("لم يُبلَّغ عن عدد الأخطاء", "\n".join(report.gaps))
        self.assertNotEqual(report.safety, SAFETY_VERIFIED)

    def test_a_number_that_was_supplied_as_zero_is_printed_as_zero(self):
        """
        وفي المقابل: صفرٌ **أُرسل** يُعرض ``0``.

        لو عرضنا ``—`` لكل صفر لكان التقرير يقول «لا أعرف» عن فحص جرى فعلاً
        ولم يجد شيئاً — وهو تعمية لا تحفّظ.
        """
        report = build(clean_reports())
        row = next(line for line in report.to_markdown().splitlines() if "الأسانيد |" in line)
        columns = [cell.strip() for cell in row.strip("|").split("|")]
        self.assertEqual(columns[2], "0", f"عمود الأخطاء: {row}")

    def test_zero_is_not_printed_for_a_source_that_did_not_run(self):
        """والمصدر الغائب لا يُعرض له صفر — بل شرطة."""
        report = build({"language": clean_reports()["language"]})
        row = next(line for line in report.to_markdown().splitlines() if "ملف الدعوى |" in line)
        columns = [cell.strip() for cell in row.strip("|").split("|")]
        self.assertEqual(columns[1], "لم يُجرِ الفحص")
        self.assertEqual(columns[2], DASH)
        self.assertNotEqual(columns[2], "0")

    def test_a_partial_sum_of_counts_is_not_reported(self):
        """
        المجموع المشتقّ لا يُعرض إن كان أحد أجزائه غائباً.

        ⚠️ لأن مجموعاً ناقصاً يُعرض كرقم كامل أسوأ من عدم عرض رقم: القارئ لا
        يستطيع أن يعرف أنه ناقص.
        """
        summary = citation_report(DRAFT_ONE_UNBACKED)
        del summary["unbacked_articles"]  # بقي `rejected` وحده
        report = build({"citation": summary})
        source = {item.kind: item for item in report.sources}["citation"]
        self.assertIsNone(source.errors)


class TestEveryExpectedKindAppears(unittest.TestCase):
    """كل نوع متوقَّع يظهر في المخرج، أُرسل أم لم يُرسَل."""

    def test_every_expected_kind_appears_whether_supplied_or_not(self):
        for reports in ({}, {"review": clean_reports()["review"]}, clean_reports()):
            with self.subTest(supplied=tuple(reports)):
                gathered = gather(reports)
                self.assertEqual(tuple(item.kind for item in gathered), EXPECTED_KINDS)
                report = build(reports)
                self.assertEqual(tuple(item.kind for item in report.sources), EXPECTED_KINDS)
                table = report.to_markdown()
                for source in report.sources:
                    self.assertIn(source.label, table)

    def test_gather_tolerates_a_none_mapping(self):
        self.assertEqual(len(gather(None)), len(EXPECTED_KINDS))
        self.assertTrue(all(not item.present for item in gather(None)))

    def test_an_unknown_kind_in_the_input_is_ignored(self):
        """
        نوع غير متوقَّع لا يُدخل صفّاً في التقرير.

        فالأنواع المتوقَّعة **شبكة ثابتة** لا تُشتقّ من الإدخال: لو اشتُقّت
        لتغيّر شكل التقرير بتغيّر الإدخال، ولظهرت أنواع لم يعلم بها أحد.
        """
        report = build({"something_else": {"summary": "x", "error_count": 3}})
        self.assertEqual(tuple(item.kind for item in report.sources), EXPECTED_KINDS)
        self.assertNotIn("something_else", report.to_markdown())


class TestRisks(unittest.TestCase):
    """المخاطر: سطر لكل نوع خطأ **باسمه**، لا بعدد مجرَّد."""

    def test_errors_produce_risks_that_name_the_kind(self):
        findings, dropped = _review_with_error()
        self.assertEqual(dropped, 0)
        # و``dropped`` يُمرَّر عدداً صريحاً — وهو المفتاح الذي يقرؤه `_RISK_LABELS`.
        review = summarize_review(findings, dropped=2)
        self.assertIn("أُسقط", review["summary"])

        reports = {
            "citation": citation_report(DRAFT_WITH_REJECTED),
            "language": summarize_language_audit(audit_language("**تسميك**")),
            "review": review,
        }
        report = build(reports)
        risks = "\n".join(report.risks)

        self.assertIn("اقتباسات مرفوضة", risks)
        self.assertIn("أسطر أسانيد لم تُقرأ", risks)
        self.assertIn("الأسانيد", risks)
        self.assertIn("التدقيق اللغوي", risks)
        self.assertIn("المراجعة الثانية", risks)
        self.assertIn("اعتراضات أُسقطت", risks)

    def test_a_risk_is_not_written_for_zero_errors(self):
        """الخطر الذي لم يقع لا يُكتب — وإلا صار القسم ضجيجاً يُغرِق الخطر."""
        report = build(clean_reports())
        self.assertEqual(report.risks, ())
        self.assertNotIn("0.", "\n".join(report.risks))

    def test_the_report_count_is_not_repeated_with_its_detail(self):
        """
        الرقم نفسه لا يُعرض مرّتين (مرّة «أخطاء مُبلَّغ عنها» ومرّة بالتفصيل).

        ⚠️ لأن العرض المزدوج يجعل خطأً واحداً يُقرأ خطأين، وهو عين ما يجعل
        المحامي يُهمل التقرير.
        """
        reports = {"citation": citation_report(DRAFT_WITH_REJECTED)}
        report = build(reports)
        joined = "\n".join(report.risks)
        self.assertIn("اقتباسات مرفوضة", joined)
        self.assertNotIn("أخطاء مُبلَّغ عنها", joined)


class TestNotes(unittest.TestCase):
    """التعارضات والبدائل: تُمرَّر كما هي، أو تبقى فارغة بلا اختلاق."""

    def test_notes_pass_through_unchanged(self):
        conflicts = ("تاريخ الإخطار في الموجز يخالف تاريخه في العقد.",)
        alternatives = ("يمكن الاعتماد على الإخطار الشفهي بدلاً من الكتابي.",)
        report = build(clean_reports(), notes={"conflicts": conflicts, "alternatives": alternatives})

        self.assertEqual(report.conflicts, conflicts)
        self.assertEqual(report.alternatives, alternatives)
        markdown = report.to_markdown()
        self.assertIn(conflicts[0], markdown)
        self.assertIn(alternatives[0], markdown)
        payload = report.to_dict()
        self.assertEqual(payload["conflicts"], list(conflicts))
        self.assertEqual(payload["alternatives"], list(alternatives))

    def test_absent_notes_yield_empty_groups_not_invented_content(self):
        """
        ⚠️ **ولا وحدة في المشروع تُنتج تعارضات أو بدائل اليوم.**

        فتقريرٌ فيه تعارضات مؤلَّفة أسوأ من تقرير يقول لا شيء، لأن الأول
        يُفقد الثقة في التقرير كلّه حين يُكتشف أنه اخترع.
        """
        report = build(clean_reports())
        self.assertEqual(report.conflicts, ())
        self.assertEqual(report.alternatives, ())
        markdown = report.to_markdown()
        self.assertNotIn("## التعارضات", markdown)
        self.assertNotIn("## البدائل", markdown)


class TestNeedsReview(unittest.TestCase):
    """ما يحتاج مراجعة بشرية — يُجمع من ما أبلغت به الوحدات لا مما يُخترع."""

    def test_every_mismatched_attribution_is_listed_with_its_reference(self):
        """
        ⚠️ و`mismatched` **خطأ** لا ملاحظة في `attribution.py`، لأنه قولٌ كاذب
        عن القانون بنصّه: الاقتباس موجود في الأرشيف، لكنه ليس نصّ المادة التي
        نُسب إليها. فالنسبة الكاذبة تحمل شكل التوثيق فتمرّ من كل فحص آخر.
        """
        draft = "وتنص المادة 43 على: «العقد المحدد المدة ينتهي بمضي مدته»"
        evidence = (
            Evidence(
                ref="L2",
                chunk_id="9",
                document_name="قانون المعاملات",
                text="المادة 43: ينتهي عقد العمل بإخطار كتابي.",
                tool="legislation",
            ),
        )
        # الإسناد يُبنى بأدوات `attribution.py` نفسها، والملخّص بـ`summarize`
        # الحقيقية — فلا يُخترع شكل ولا مفتاح.
        real = verify_attributions(draft, evidence, lambda item: item.text)
        payload = summarize_attribution(real)
        self.assertFalse(real.clean)
        self.assertEqual(payload["error_count"], 1)

        report = build({"attribution": payload})
        joined = "\n".join(report.needs_review)
        self.assertIn("منسوب إلى غير مادّته", joined)
        self.assertIn("43", joined)

    def test_unverified_citations_are_counted_and_listed(self):
        report = build({"citation": citation_report(DRAFT_ONE_UNBACKED)})

        # دعوى غير موثَّقة: مادة ذُكرت في المتن ولا سند لها في المسترجَع.
        self.assertEqual(report.unverified_claims, 1)
        joined = "\n".join(report.needs_review)
        self.assertIn("مادة ذُكرت في المتن ولا سند لها", joined)
        self.assertIn("999", joined)

    def test_a_dropped_review_objection_is_listed(self):
        """
        الاعتراض المُسقَط يُعرض على المحامي.

        ⚠️ وليس تفصيلاً: مسودّة أُسقطت فيها كل الاعتراضات تخرج `clean` — وهذا
        صحيح إذ لم يثبت عيب. لكنها ليست كمسودّة لم يُعترض عليها أصلاً، والمحامي
        يستحقّ أن يعرف الفرق: هل سكت المراجع لأنه رضي، أم لأنه اتّهم ولم يُثبت؟
        """
        findings, dropped = _review_with_dropped()
        self.assertTrue(dropped, "الاختبار يحتاج اعتراضاً مُسقَطاً فعلاً")
        report = build({"review": summarize_review(findings, dropped)})
        self.assertIn("اعتراضات أُسقطت", "\n".join(report.needs_review))

    def test_open_questions_are_collected(self):
        questions = ("هل صُدّق الإخطار؟", "من يوقّع عن الشركة؟")
        report = build(clean_reports(), open_questions=questions)
        self.assertEqual(report.open_questions, questions)
        joined = "\n".join(report.needs_review)
        for question in questions:
            self.assertIn(question, joined)
            self.assertIn(question, report.to_markdown())
        self.assertNotEqual(report.safety, SAFETY_VERIFIED)


class TestOutputShape(unittest.TestCase):
    """شكل المخرج — يُبثّ JSON إلى الواجهة ويُنسخ نصّاً إلى Word."""

    def test_to_dict_is_json_serialisable(self):
        payload = build(
            {
                "citation": citation_report(DRAFT_WITH_REJECTED),
                "language": summarize_language_audit(audit_language("**تسميك**\n[فراغ]")),
            },
            open_questions=("سؤال؟",),
            notes={"conflicts": ("تعارض.",)},
        ).to_dict()

        encoded = json.dumps(payload, ensure_ascii=False)
        json.loads(encoded)
        self.assertEqual(payload["safety"], SAFETY_PARTLY)
        self.assertIsInstance(payload["sources"], list)
        self.assertEqual(len(payload["sources"]), len(EXPECTED_KINDS))

    def test_markdown_contains_no_none_and_no_empty_dict(self):
        for report in (
            build(clean_reports()),
            build({}),
            build({"language": {"summary": "سليم.", "error_count": 0, "notice_count": None}}),
            build({"citation": citation_report(DRAFT_WITH_REJECTED)}, open_questions=("سؤال؟",)),
        ):
            markdown = report.to_markdown()
            self.assertNotIn("None", markdown)
            self.assertNotIn("{}", markdown)
            # ولا صيغة بايثون في نصّ المحامي: القوائم تُعرض سطوراً لا ``['x']``.
            self.assertNotIn("['", markdown)

    def test_to_dict_keeps_none_where_a_number_was_not_supplied(self):
        """
        ولا يُحوَّل ``None`` إلى صفر عند التسلسل.

        ⚠️ الواجهة تعرض ``—`` حيث وصل ``None``؛ ولو بُثّ صفر لقرأه المحامي
        «لا خطأ» عن فحص لم يُبلَّغ عن عدده.
        """
        report = build({"citation": {"summary": "لا شيء يُشتقّ"}})
        payload = report.to_dict()
        citation = next(item for item in payload["sources"] if item["kind"] == "citation")
        self.assertIsNone(citation["errors"])
        self.assertIsNone(citation["notices"])
        # و``null`` في JSON لا ``0``: الواجهة تعرض ``—`` حيث وصل ``None``.
        serialised = json.dumps(citation, ensure_ascii=False)
        self.assertIn('"errors": null', serialised)
        self.assertNotIn('"errors": 0', serialised)

    def test_safety_is_one_of_three_levels(self):
        for reports in ({}, {"language": clean_reports()["language"]}, clean_reports()):
            with self.subTest(supplied=tuple(reports)):
                self.assertIn(build(reports).safety, (SAFETY_VERIFIED, SAFETY_PARTLY, SAFETY_UNVERIFIED))

    def test_the_sources_table_has_a_row_per_expected_kind(self):
        report = build(clean_reports())
        rows = [line for line in report.to_markdown().splitlines() if line.startswith("| ")]
        # صفّان للترويسة + صفّ لكل نوع
        self.assertEqual(len(rows), len(EXPECTED_KINDS) + 2)


class TestOrdering(unittest.TestCase):
    """الترتيب ثابت لا يتغيّر: لا بترتيب الإدخال، ولا بترتيب النداء."""

    def test_groups_render_in_the_fixed_order(self):
        """
        ⚠️ **والترتيب جزء من التقرير لا من المدخل.**

        لو رُتِّبت المجموعات على ترتيب مفاتيح قاموس المدخل لتغيّر شكل التقرير
        بتغيّر ترتيب الإدخال — وهو ما يمنعه ``GROUP_ORDER`` في `briefing.py`.

        ⛔ **والمدخل هنا ناقص فحصاً عن قصد**: «ما ينقص» لا تُرسم إن كانت فارغة
        (سياجٌ فارغ يُقرأ نقصاً لا انتفاءً)، فاختبار ترتيبها على مدخل نظيف
        يختبر ترتيب مجموعة **غير موجودة** — وهو ما كان يمرّ سابقاً لأن المدخل
        المتخيَّل أنتج أسطر نقص وهمية.
        """
        incomplete = clean_checks()
        incomplete["review"] = None  # نقصٌ حقيقي يُرسم له «ما ينقص»
        report = build(
            incomplete,
            open_questions=("سؤال؟",),
            notes={"conflicts": ("تعارض.",), "alternatives": ("بديل.",)},
        )
        markdown = report.to_markdown()
        headings = [
            h
            for h in (
                "ما ينقص",
                "المخاطر",
                "التعارضات",
                "البدائل",
                "ما يحتاج مراجعة بشرية",
            )
            if f"## {h}" in markdown
        ]
        # ولا يختبر الترتيب على قائمة فارغة: لا بدّ أن تُرسم مجموعة واحدة على الأقل.
        self.assertTrue(headings, "لم تُرسم مجموعة واحدة — الاختبار بلا معنى")
        positions = [markdown.index(f"## {h}") for h in headings]
        self.assertEqual(positions, sorted(positions), "ترتيب المجموعات ليس ثابتاً")
        self.assertLess(markdown.index("## ما ينقص"), markdown.index("## المصادر"))
        self.assertLess(markdown.index("## المصادر"), markdown.index("## أسئلة مفتوحة"))

    def test_ordering_is_stable_across_repeated_calls_and_input_order(self):
        first_input = clean_reports()
        second_input = {kind: first_input[kind] for kind in reversed(list(first_input))}

        first = build(first_input)
        second = build(second_input)
        again = build(first_input)

        self.assertEqual(first.to_markdown(), again.to_markdown())
        self.assertEqual(first.to_markdown(), second.to_markdown())
        self.assertEqual(first.to_dict(), second.to_dict())
        self.assertEqual(
            tuple(item.kind for item in first.sources), EXPECTED_KINDS
        )
        self.assertEqual(
            tuple(item.kind for item in second.sources), EXPECTED_KINDS
        )

    def test_sources_keep_the_expected_order_even_when_none_ran(self):
        report = build({})
        self.assertEqual(tuple(item.kind for item in report.sources), EXPECTED_KINDS)


class TestReadinessGuard(unittest.TestCase):
    """درجة السلامة — ولا مدخل يبلغها بالظنّ."""

    def _clean_sources(self) -> tuple[Source, ...]:
        return gather(clean_reports())

    def test_verified_needs_everything(self):
        sources = self._clean_sources()
        self.assertEqual(readiness(sources, 0), SAFETY_VERIFIED)
        # وكل شرط يُنقض وحده يمنع الدرجة العليا
        self.assertNotEqual(readiness(sources, 1), SAFETY_VERIFIED)
        self.assertNotEqual(readiness(sources, 0, ("سؤال؟",)), SAFETY_VERIFIED)
        self.assertNotEqual(readiness(gather({}), 0), SAFETY_VERIFIED)

    def test_a_missing_count_blocks_the_top_level(self):
        """
        ⚠️ عددٌ لم يُرسل يمنع الدرجة العليا.

        فلا يُشهد بسلامة فحصٍ لا يُعرف عدد أخطائه — وإن كان نصّه يقول سليم.
        """
        sources = tuple(
            Source(
                kind=item.kind,
                label=item.label,
                present=item.present,
                summary=item.summary,
                errors=None,
                notices=item.notices,
            )
            for item in self._clean_sources()
        )
        self.assertEqual(readiness(sources, 0), SAFETY_PARTLY)

    def test_blank_open_questions_do_not_block(self):
        """سؤال فارغ ليس سؤالاً — ولا يُسقط الدرجة بفراغ."""
        self.assertEqual(readiness(self._clean_sources(), 0, ("  ", "")), SAFETY_VERIFIED)


class TestRealisticInputFromTheRealModules(unittest.TestCase):
    """
    المدخل الواقعي — مبنيّ من ``summarize`` **الحقيقية** للوحدات.

    ⚠️ والغرض أن يُختبر هذا الملف على **الأشكال التي تُنتجها الوحدات فعلاً**
    لا على قاموس مكتوب بيد: القاموس المكتوب بيد يُختبر نفسه، ويبقى الشكل
    الحقيقي غير مختبر حتى يُشغّل في الخدمة.
    """

    def test_real_summaries_of_three_modules(self):
        citation = citation_report(DRAFT_WITH_REJECTED)
        language = summarize_language_audit(
            audit_language("** لائحة دعوى تجارية **\nالوقائع:\nشركة Alpha Trading LLC")
        )
        review = summarize_review(*_review_with_error())

        report = build(
            {"citation": citation, "language": language, "review": review},
            open_questions=("هل صُدّق الإخطار كتابةً؟",),
        )

        # ما أبلغت به الوحدات فعلاً وصل إلى التقرير كما هو.
        by_kind = {item.kind: item for item in report.sources}
        self.assertEqual(by_kind["language"].errors, language["error_count"])
        self.assertEqual(by_kind["language"].notices, language["notice_count"])
        self.assertEqual(by_kind["review"].errors, review["error_count"])
        self.assertEqual(by_kind["review"].notices, review["notice_count"])
        self.assertIsNone(by_kind["attribution"].errors)  # لم تُشغَّل
        self.assertIn(language["summary"], report.to_markdown())
        self.assertIn(review["summary"], report.to_markdown())

        self.assertEqual(report.safety, SAFETY_PARTLY)
        self.assertTrue(report.gaps and report.risks and report.needs_review)
        text = _all_output_text(report)
        for phrase in FORBIDDEN_READY_PHRASES:
            self.assertNotIn(phrase, text)

    def test_real_attribution_summary_of_a_mismatched_reference(self):
        """`attribution.py` نفسه يشهد: ``mismatched`` خطأ و``absent`` ملاحظة."""
        draft = (
            "وتنص المادة 43 على: «العقد المحدد المدة ينتهي بمضي مدته»\n"
            "وتنص المادة 77 على: «يُرسل الإخطار قبل ثلاثين يوماً كتابةً»"
        )
        evidence = (
            Evidence(
                ref="L2",
                chunk_id="9",
                document_name="قانون المعاملات",
                text="المادة 43: ينتهي عقد العمل بإخطار كتابي.",
                tool="legislation",
            ),
        )
        outcome = verify_attributions(draft, evidence, lambda item: item.text)
        payload = summarize_attribution(outcome)

        self.assertEqual(payload["error_count"], 1)
        self.assertEqual(payload["notice_count"], 1)
        self.assertFalse(payload["clean"])

        report = build({"attribution": payload})
        joined = "\n".join(report.needs_review)
        self.assertIn("منسوب إلى غير مادّته", joined)
        # «مادة لم تُسترجَع» ملاحظة لا خطأ — فهي في الملاحظات لا في الأخطاء.
        self.assertEqual(
            {item.kind: item for item in report.sources}["attribution"].errors, 1
        )
        self.assertEqual(report.unverified_claims, 0)

    def test_the_language_finding_kinds_reach_the_report(self):
        """ملخّص سيبويه الحقيقي: عيب Markdown + ملاحظة لاتينية."""
        payload = summarize_language_audit(
            audit_language("** لائحة **\nتعاملت مع شركة Alpha Trading LLC")
        )
        report = build({"language": payload})
        by_kind = {item.kind: item for item in report.sources}
        self.assertEqual(by_kind["language"].errors, 1)
        self.assertEqual(by_kind["language"].notices, 1)
        self.assertIn("التدقيق اللغوي", "\n".join(report.risks))


class TestModuleGuarantees(unittest.TestCase):
    """ضمانات الملف: بلا تبعية خارجية، وبلا حالة، وبلا عبارة جاهزية في النصّ."""

    def test_imports_are_stdlib_only(self):
        import pathlib

        import briefing

        source = pathlib.Path(briefing.__file__).read_text(encoding="utf-8")
        imported = set(re.findall(r"^(?:from|import)\s+([A-Za-z_][\w\.]*)", source, re.MULTILINE))
        allowed = {"__future__", "dataclasses", "datetime", "json", "typing"}
        self.assertTrue(imported <= allowed, f"استيرادات: {sorted(imported - allowed)}")

    def test_the_forbidden_phrase_is_absent_from_the_source_file(self):
        """
        ⚠️ **ولا في تعليق واحد.**

        والسبب أن التعليق يُنسخ: سطرٌ يقول «لا تقل جاهز للإيداع» يحمل العبارة
        نفسها، ونسخةٌ منه في نصّ كافٍ لأن تظهر للمحامي. فالمصدر كلّه مفحوص.
        """
        import pathlib

        import briefing

        source = pathlib.Path(briefing.__file__).read_text(encoding="utf-8")
        for phrase in FORBIDDEN_SOURCE_PHRASES:
            self.assertNotIn(phrase, source)

    def test_build_is_pure(self):
        """بناءان من المدخل نفسه يُنتجان التقرير نفسه — بلا ساعة ولا حالة."""
        reports = clean_reports()
        self.assertEqual(build(reports).to_dict(), build(reports).to_dict())

    def test_the_report_is_immutable(self):
        report = build(clean_reports())
        with self.assertRaises(Exception):
            report.safety = SAFETY_UNVERIFIED  # type: ignore[misc]

    def test_source_is_immutable(self):
        source = gather({})[0]
        with self.assertRaises(Exception):
            source.present = True  # type: ignore[misc]

    def test_arabic_labels_are_present_for_every_expected_kind(self):
        for source in gather(None):
            self.assertTrue(source.label.strip())
            self.assertTrue(re.search(r"[\u0600-\u06FF]", source.label))
            self.assertFalse(source.present)


# ------------------------------------------------------------------------------
# مساعدات بناء اعتراضات المراجعة الحقيقية
# ------------------------------------------------------------------------------

OBJECTION_QUOTE = "تأخّر المستأجر عن سداد الأجرة الشهرية أربعة أشهر"
OBJECTION_BASIS = "تأخّر المستأجر عن سداد الأجرة الشهرية أربعة أشهر"


def _review_with_error():
    """اعتراض حقيقي من `parse_review` — نصّه من المسودّة، وسنده من الموجز."""
    raw = json.dumps(
        [
            {
                "kind": "fact",
                "severity": "error",
                "message": "المسودّة تقول ثلاثة أشهر والموجز يقول أربعة.",
                "quote": OBJECTION_QUOTE,
                "basis": OBJECTION_BASIS,
            },
            {
                "kind": "strength",
                "severity": "notice",
                "message": "الدفع ضعيف.",
                "quote": OBJECTION_QUOTE,
                "basis": OBJECTION_BASIS,
            },
        ],
        ensure_ascii=False,
    )
    outcome = parse_review(raw, OBJECTION_QUOTE, OBJECTION_BASIS, "")
    return outcome.findings, outcome.dropped


def _review_with_dropped():
    """اعتراض لم يثبت نصّه: اقتباسه ليس في المسودّة، فيُسقَط ويُعدّ."""
    raw = json.dumps(
        [
            {
                "kind": "fact",
                "severity": "error",
                "message": "اعتراض بلا نصّ ثابت.",
                "quote": "نصّ لا يوجد في المسودّة إطلاقاً ولا يشبهها",
                "basis": "",
            }
        ],
        ensure_ascii=False,
    )
    outcome = parse_review(raw, OBJECTION_QUOTE, OBJECTION_BASIS, "")
    return outcome.findings, outcome.dropped


if __name__ == "__main__":
    unittest.main(verbosity=2)
