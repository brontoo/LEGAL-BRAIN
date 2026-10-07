"""
اختبارات سجلّ الأسانيد — أيحكم هذا السند هذه الواقعة، **ثم**؟
=============================================================================

تشغيل:
    python -m unittest tests.test_authority -v
    python -m unittest discover -s tests -t . -v

حتمية بالكامل: بلا شبكة، وبلا نموذج، وبلا قاعدة بيانات، وبلا قرص. ولا تحتاج
`fake_deps` لأن `authority` وحدة نقية كـ`citations.py` و`attribution.py`: كل
حكمها من مدخلاتها.

⚠️⚠️ **وأهمّ اختبارين في الملف هما الواقعتان اللتان جاء الملف لهما:**

١. ``test_the_amended_provision_does_not_govern_the_earlier_facts`` — **العيب
   الذي وقع فعلاً**: الواقعة **قبل نفاذ النصّ المعتمد في المذكرة**، فالاستشهاد
   به عليها استشهادٌ بنصّ لا يحكمها. والنصّ موجود، ومنسوب إلى مادّته، ومصدره
   رسمي — **و`citations.py` و`attribution.py` يمرّانه كاملاً**. والعيب في
   **الزمن وحده**، وهو أقرب إلى الكشف: لا يظهر في أي موضع من المستند.

٢. ``test_a_secondary_summary_is_not_the_provision`` — **العيب الثالث**:
   ملخّص نتائج بحث قام مقام النصّ الذي يُقتبس. والتعليق ليس النصّ، ولا يُنقل
   عنه نصٌّ يُنسب إلى مادة.

⚠️ **ونصوص هذا الملف بياناتُ اختبارٍ لا قانون.** أسماء التشريعات وأرقام
المواد وتواريخها **ملفٌّ يملؤه المحامي** — وهذا الملف يملؤه ليقيس به سلوك
الوحدة، لا ليُثبت حكماً في أي واقعة. والوحدة نفسها **لا تحمل نصّاً ولا رقماً
ولا تاريخاً**، ويُثبَّت ذلك بالتحليل النحوي في ``TestModuleGuarantees``.

⚠️ **وأسماء الصيغ في هذا الملف مشروحةٌ بمواضعها**، لأن القارئ يحتاج أن يعرف
من الاختبار نفسه: أيّ سلوك مُثبَّت، وأيّه **حدّ معلَن** لا مرغوب.
"""

import ast
import json
import pathlib
import re
import unittest

import authority
from authority import (
    CLEAN_EMPTY_NOTE,
    ERROR_FINDING_KINDS,
    LABELS,
    NOTICE_FINDING_KINDS,
    STATUSES,
    STATUS_APPLIES,
    STATUS_CONDITIONS_UNMET,
    STATUS_CONDITIONS_UNVERIFIED,
    STATUS_NOT_IN_FORCE,
    ApplicationCheck,
    Assertion,
    Authority,
    AuthorityRegister,
    Finding,
    SourceKind,
    asserted_without_source,
    check_application,
    in_force_on,
    parse_date,
    secondary_as_primary,
    summarize,
    transitional_note,
    unsourced,
)

# ==============================================================================
# بيانات الاختبار — الخطّ الزمني الذي وقعت فيه العيوب
# ==============================================================================
#
# ⚠️ **والخطّ الزمني مقصود بهذا الترتيب، لأن العيوب الثلاثة كلّها عيوبُ زمن:**

#: تاريخ نفاذ السند المفحوص.
IN_FORCE_FROM = "2022-02-02"
#: تاريخ انتهاء سريانه — والسند مغلق به.
IN_FORCE_TO = "2023-12-31"
#: تعديل لاحق لنفاذه — عليه يُبنى فحص التقاطع الانتقالي.
AMENDED_AT = "2023-06-01"
#: **الواقعة قبل النفاذ** — والسند المعتمد في المذكرة لا يحكمها. **(العيب الأول)**
BEFORE_IN_FORCE = "2022-01-20"
#: الواقعة داخل السريان **وقبل التعديل** — محكومة بالنصّ كما كان.
FACTS_DATE = "2023-01-15"
#: الواقعة داخل السريان **وبعد التعديل** — هنا فقط يُسأل عن القاعدة الانتقالية.
AFTER_AMENDMENT = "2023-07-01"
#: واقعة بعد انتهاء السريان — العلاج مختلف: يُبحث عن النصّ الحالي.
AFTER_EXPIRY = "2024-06-01"

#: شرط الانطباق المُدرَج في السند — وهو الذي يُطابَق بالوقائع.
NOTICE_CONDITION = "قيام الطرف بإخطار كتابي"
#: شرط ثانٍ، ليُقاس الفرق بين «تناقضه الوقائع» و«لا تتكلّم عنه».
NO_MINISTRY_CONDITION = "صدور قرار من الوزارة"

#: الواقعة التي تحمل **نفي الشرط** — وهي صيغة الوقائع التي جاءت في المذكرة.
FACTS_NEGATING_NOTICE = "لم يقم الطرف الثاني بإخطار كتابي قبل إنهاء العقد"
#: الواقعة التي **تثبت الشرط** — بلفظ مختلف عن لفظ الشرط عمداً.
FACTS_STATING_NOTICE = "قام الطرف الثاني بإخطار كتابي قبل إنهاء العقد"
#: وقائع **لا تتكلّم** عن شرط الإخطار أصلاً.
FACTS_SILENT = "بقي العامل في الخدمة حتى تاريخ انتهاء العلاقة"
#: واقعة صالحة للتكرار في فحص الحتمية على مستوى الوحدة.
FACTS_STILL_VALID_SENTINEL = "قام الطرف الثاني بإخطار كتابي قبل إنهاء العقد"

#: مسودّة تستشهد بمصدر ثانوي بتمهيد استشهاد — **العيب الثالث في سطر واحد**.
DRAFT_CITING_A_SECONDARY = (
    "وفقا لتعليق على قانون المعاملات المدنية المدنية فإن الإخطار واجب قبل الإنهاء."
)


def the_amended_authority() -> Authority:
    """
    السند المفحوص: **سارية بشروط، وعليها تعديل مُعلَن، ومصدرها الرسمي مُدرَج.**

    ⚠️ **ومصدره الرسمي مملوء** ليكون الاختبار على الزمن وحده: لو كان
    ``official_source`` فارغاً لخرج معه إعلان `unsourced` فاختلط الفحصان على
    القارئ. وسندٌ بلا مصدر له اختباره المستقلّ.
    """
    return Authority(
        key="labour-43",
        instrument="المرسوم بقانون اتحادي رقم 33 لسنة 2021",
        article="43",
        kind=SourceKind.FEDERAL_DECREE_LAW,
        official_source="الجريدة الرسمية — الجهة المختصة",
        in_force_from=IN_FORCE_FROM,
        in_force_to=IN_FORCE_TO,
        amended_by=(AMENDED_AT,),
        retrieved_from="L3",
        conditions=(NOTICE_CONDITION,),
    )


def the_open_ended_authority() -> Authority:
    """
    سند **مفتوح النهاية**: تاريخ نفاذ معلوم، و``in_force_to`` فارغ.

    ⚠️ **و``in_force_to`` الفارغ معناه «سارية»**، بخلاف ``in_force_from``
    الفارغ الذي معناه «غير معلوم». **والفرق بين الفراغين هو أوّل ما يُخطئ فيه
    القارئ**، فله اختبار مستقلّ.
    """
    return Authority(
        key="civil-1",
        instrument="مثال تشريع مدني",
        article="1",
        kind=SourceKind.FEDERAL_LAW,
        official_source="جهة رسمية",
        in_force_from="2020-01-01",
    )


def the_secondary_source() -> Authority:
    """
    **تعليق أو ملخّص** — لا يُستشهد به كنصّ، وبلا مصدر رسمي.

    ⚠️ **وله وجهان في هذا الملف:** تصنيفه ``SECONDARY`` يفتح
    `secondary_as_primary`، وفراغ مصدره يفتح `unsourced` — **والاثنان مقصودان
    أن يقعا معاً على سند واحد** ليقيسهما الاختبار كلٌّ على حِدة.
    """
    return Authority(
        key="commentary-1",
        instrument="تعليق على قانون المعاملات المدنية المدنية",
        article="1",
        kind=SourceKind.SECONDARY,
        official_source="",
        in_force_from="2015-01-01",
    )


# ==============================================================================
# ١. الفحص الزمني — الحدود الأربعة
# ==============================================================================


class TestInForceOn(unittest.TestCase):
    """«أكانت المادة سارية يوم الواقعة؟» — حكم ثنائي، وحدوده أربعة."""

    def test_the_boundaries_are_the_days_that_are_always_wrong(self):
        """
        🔑 **الحدود: يوم قبل النفاذ، ويوم النفاذ، ويوم قبل الانتهاء، ويوم
        الانتهاء.**

        ⚠️ **ويوم الانتهاء نفسه سارٍ** — لأن ``in_force_to`` تاريخ **آخر يوم
        نفاذ** لا أوّل يوم بعد النفاذ. ولو أُقصي يومه لنُسب نقصُ يوم إلى نصّ
        سارٍ في يومه، وهو خطأ في الزمن لا في النقل — **وهو العيب الذي جاء هذا
        الملف لمنعه في ثوب صغير**.
        """
        authority = the_amended_authority()

        self.assertFalse(in_force_on(authority, "2022-02-01"), "قبل النفاذ بيوم")
        self.assertTrue(in_force_on(authority, IN_FORCE_FROM), "يوم النفاذ")
        self.assertTrue(in_force_on(authority, "2023-12-30"), "قبل الانتهاء بيوم")
        self.assertTrue(in_force_on(authority, IN_FORCE_TO), "يوم الانتهاء")
        self.assertFalse(in_force_on(authority, AFTER_EXPIRY), "بعد الانتهاء بيوم")

    def test_an_open_ended_authority_stays_in_force(self):
        """سند مفتوح النهاية: سارٍ بعد نفاذه، وغير سارٍ قبله — ولا انتهاء له."""
        authority = the_open_ended_authority()
        self.assertTrue(authority.is_open_ended)
        self.assertFalse(in_force_on(authority, "2019-12-31"))
        self.assertTrue(in_force_on(authority, "2020-01-01"))
        self.assertTrue(in_force_on(authority, "2099-01-01"))

    def test_an_unknown_effective_date_is_not_in_force(self):
        """
        ⚠️ **الجهل بتاريخ النفاذ لا يُقرأ سرياناً.**

        وهو موضع خطأ يقع كثيراً: يُترك الحقل فارغاً فيُظنّ معناه «سارية
        دائماً». والصحيح أنه **لم يُثبَت أنها كانت نافذة** — وهو ما لا يقوم
        عليه استشهاد.
        """
        unknown = Authority(
            key="u",
            instrument="سند مجهول النفاذ",
            article="1",
            kind=SourceKind.UNKNOWN,
            official_source="",
            in_force_from="",
        )
        self.assertFalse(in_force_on(unknown, "2020-01-01"))
        # ⚠️ و`in_force_to` الفارغ في السند المفتوح **لا يمنع السريان** — فالفراغان
        # ليسا شيئاً واحداً، وهذا هو الفرق الذي يُثبَّت هنا.
        self.assertTrue(in_force_on(the_open_ended_authority(), "2020-01-01"))

    def test_an_unreadable_date_is_not_in_force_and_does_not_raise(self):
        """
        ⚠️ **التاريخ المشوّه يُرجع ``False`` ولا يرفع**، لأن الدالّة تُستدعى في
        مسار عرض الحصيلة، واستثناءٌ فيه يهدم الحصيلة كلها بسبب خانة تاريخ.

        ⚠️ **ولا يُخمَّن ناقص**: «2022-02» ليست أوّل الشهر ولا آخره — والأول
        يُقدّم النفاذ يوماً والثاني يؤخّره، **وكلاهما اختراع لتاريخ لم يُدخله
        المحامي**.
        """
        authority = the_amended_authority()
        self.assertFalse(in_force_on(authority, "لا-تاريخ"))
        self.assertFalse(in_force_on(authority, ""))
        self.assertFalse(in_force_on(authority, "2022-13-45"))
        self.assertIsNone(parse_date("2022-02"))
        self.assertIsNone(parse_date("2022/02/02"))
        self.assertEqual(parse_date("٢٠٢٢-٠٢-٠٢"), parse_date("2022-02-02"))

    def test_the_check_raises_on_a_malformed_facts_date(self):
        """
        ⚠️ **أما تاريخ الواقعة فيُرفض بالاستثناء لا بالسكوت.**

        والفرق جوهري: `check_application` بلا تاريخ ليس «مادة غير سارية»، بل
        **سؤال لم يُطرح**. فلو رجع ``not_in_force`` لكان حكماً مخترعاً في ثوب
        نتيجة، والسكوت عن سؤال أسوأ من التوقّف عليه.
        """
        with self.assertRaises(ValueError):
            check_application(the_amended_authority(), [], "قبل-التعديل")


# ==============================================================================
# ٢. العيب الأول والثاني — النصّ المعتمد لا يحكم الواقعة
# ==============================================================================


class TestTheAmendedProvision(unittest.TestCase):
    """ نصٌّ صحيح في موضع لا يحكم — والعيب كلّه في الزمن. """

    def test_the_amended_provision_does_not_govern_the_earlier_facts(self):
        """
        🔑🔑 **هذا هو العيب الذي وقع فعلاً، وهو سبب وجود الملف.**

        الواقعة سبقت نفاذ النصّ المعتمد في المذكرة: الكاتب فتح النصّ الساري
        **اليوم**، فقرأ حكماً لم يكن قائماً وقت الواقعة، وكتبه في مذكرة عنها.
        والنصّ صحيح، ومنسوب إلى مادّته، ومصدره رسمي، **و`citations.py`
        و`attribution.py` يمرّانه كاملاً** — لأنه موجود فعلاً في الأرشيف
        الحديث. والعيب في **الزمن وحده**.

        ⚠️ **والاختبار يثبّت الحالتين معاً**: أن الحكم ``not_in_force``، وأنه
        **ليس** ``conditions_unmet`` — لأن الادّعاء لو خرج «شرطٌ لم يتحقّق»
        لَما بان أن المادة لا تحكم أصلاً، **والفرق بين «لا تحكم» و«شرطها لم
        يتحقّق» هو الفرق بين نصّ في غير موضعه ونصّ في موضعه**.
        """
        check = check_application(
            the_amended_authority(), [FACTS_STATING_NOTICE], BEFORE_IN_FORCE
        )

        self.assertEqual(check.status, STATUS_NOT_IN_FORCE)
        self.assertNotEqual(check.status, STATUS_CONDITIONS_UNMET)
        self.assertNotEqual(check.status, STATUS_APPLIES)
        self.assertTrue(check.is_error)
        # والسبب مسمّى: الواقعة **قبل النفاذ** — لا «غير سارية» مُجمَلة.
        self.assertIn("قبل نفاذ", check.reason)

    def test_the_same_authority_applies_inside_its_force_period(self):
        """
        ⚠️ **والعيب ليس في السند بل في استعماله**: السند نفسه **يحكم** واقعةً
        داخل مدّة سريانه. ولو منع الفحص سنداً سارياً لصار أداة تُنذر دائماً
        فلا تُقرأ.
        """
        check = check_application(
            the_amended_authority(), [FACTS_STATING_NOTICE], "2023-03-01"
        )
        self.assertEqual(check.status, STATUS_APPLIES)
        self.assertFalse(check.is_error)

    def test_an_expired_provision_names_its_end_date(self):
        """انتهاء السريان يُقال بتاريخه — لأن العلاج يختلف: يُبحث عن النصّ الحالي."""
        check = check_application(
            the_amended_authority(), [FACTS_STATING_NOTICE], AFTER_EXPIRY
        )
        self.assertEqual(check.status, STATUS_NOT_IN_FORCE)
        self.assertIn(IN_FORCE_TO, check.reason)

    def test_an_unknown_effective_date_says_so_and_asks_for_it(self):
        """
        ⚠️ **وسندٌ تاريخ نفاذه غير مُدخَل يُعلَن كذلك** — ولا يُقرأ سرياناً.

        والفرق في التصرّف واضح: هذا **يسأل عن تاريخ**، ومنتهي السريان **يسأل
        عن بديل**، ومن لم ينفذ بعد **ينتظر نصّه الساري**.
        """
        nameless = Authority(
            key="nameless",
            instrument="سند بلا تاريخ نفاذ",
            article="2",
            kind=SourceKind.MINISTERIAL_DECISION,
            official_source="جهة رسمية",
            in_force_from="",
        )
        check = check_application(nameless, [], "2023-01-01")
        self.assertEqual(check.status, STATUS_NOT_IN_FORCE)
        self.assertIn("تاريخ النفاذ غير معلوم", check.reason)

    def test_the_temporal_check_precedes_the_conditions(self):
        """
        ⚠️ **الترتيب هو المنطق:** لا يُقال «انطبق شرطها» ولا «لم تتكلّم الوقائع
        عن شرطها» عن نصّ لا يحكم الواقعة أصلاً — فالسؤال سقط قبل أن يُطرح.

        وهذا **بالضبط العيب الأول**: مادة صحيحة في موضع لا تنطبق فيه، لأن
        أحداً لم يسأل أوّلاً: هل تحكم هذه المادة هذه الواقعة؟
        """
        check = check_application(the_amended_authority(), [], BEFORE_IN_FORCE)
        # بلا وقائع أصلاً كان الشرط «غير متحقَّق منه» — لكن الزمن سبقه.
        self.assertEqual(check.status, STATUS_NOT_IN_FORCE)
        self.assertEqual(check.unverified, ())
        self.assertEqual(check.unmet, ())


# ==============================================================================
# ٣. القاعدة الانتقالية — إعلانٌ لا حكم
# ==============================================================================


class TestTransitionalNote(unittest.TestCase):
    """التعديل المُعلَن: يُقال إن هنا موضع نظر، ولا يُقال ماذا تنصّ القاعدة."""

    def test_the_note_fires_only_when_the_date_straddles_an_amendment(self):
        """
        🔑 **الشرط: تعديل مُعلَن وقع قبل الواقعة، وداخل مدّة السريان.**

        * قبل النفاذ: لا سريان يُعدَّل → لا إعلان.
        * بين النفاذ والتعديل: الواقعة محكومة بالنصّ الأصلي → لا تقاطع.
        * بعد التعديل وداخل السريان: **هنا التقاطع وحده** → إعلان.
        * وبعد انتهاء السريان: التعديل لا يمسّ واقعةً لا تحكمها المادة.
        """
        authority = the_amended_authority()

        self.assertEqual(transitional_note(authority, "2021-01-01"), "")
        self.assertEqual(transitional_note(authority, "2023-05-31"), "")
        self.assertNotEqual(transitional_note(authority, AFTER_AMENDMENT), "")
        self.assertEqual(transitional_note(authority, AFTER_EXPIRY), "")

    def test_the_note_never_states_what_the_transitional_rule_provides(self):
        """
        🔑🔑 **وهذا هو حدّ الملف، وهو أهمّ من الإعلان نفسه.**

        الدالّة **لا تعرف** القاعدة الانتقالية، ولا يجوز أن تعرفها: لو كُتبت
        في الكود «يُطبَّق النصّ الجديد على الوقائع اللاحقة» لصار رأياً في
        القانون **يتقادم بصمت** في اللحظة التي يُعدَّل فيها المُعدِّل. فالإعلان
        يسمّي المُعدِّل وتاريخه، **ويسلّم القراءة للمحامي صراحةً**.

        ⚠️ **والاختبار يمنع أن يُكتَب حكمٌ محلّ الإعلان**، ويمنع أيضاً أن
        **تُعدَّد الاحتمالات** «قد يُطبَّق الجديد وقد يبقى الأصل» — فتعدادُها
        يُقرأ ترجيحاً بلا سند. المطلوب: «القاعدة لم تُفحَص، واقرأها أنت».
        """
        note = transitional_note(the_amended_authority(), AFTER_AMENDMENT)

        self.assertIn(AMENDED_AT, note, "التعديل مُسمّى بتاريخه")
        self.assertIn(AFTER_AMENDMENT, note, "والواقعة مُسمّاة بتاريخها")
        self.assertIn("لم تُفحَص", note)
        self.assertIn("المحامي", note)
        self.assertIn("لا يقول ماذا تنصّ", note)
        for forbidden in (
            "يُطبَّق النصّ الجديد",
            "تنصّ القاعدة",
            "يسري النصّ الجديد",
            "قد يُطبَّق",
            "قد يبقى",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, note)

    def test_an_authority_without_amendments_never_fires(self):
        """بلا تعديل مُعلَن: لا إعلان — ولا فراغ يُقرأ «لا قاعدة انتقالية»."""
        self.assertEqual(
            transitional_note(the_open_ended_authority(), "2026-01-01"), ""
        )

    def test_an_amendment_with_an_unreadable_date_is_not_guessed(self):
        """
        ⚠️ **وتعديلٌ بتاريخ مشوّه لا يُخمَّن تاريخه.** يُسقَط من حساب التقاطع
        (فلا يخرج إعلان كاذب بلا تاريخه)، ولا يُبنى عليه تقاطع مُقدَّر.

        وحدّه المعلن: **إسقاطٌ في اتجاه نقص التغطية لا في اتجاه الاتهام** —
        وهو الاتجاه المقبول في `attribution.py` نفسه.
        """
        authority = Authority(
            key="bad-amendment",
            instrument="سند بتعديل مشوّه",
            article="1",
            kind=SourceKind.LOCAL_LAW,
            official_source="جهة رسمية",
            in_force_from="2020-01-01",
            amended_by=("في يونيو",),
        )
        self.assertEqual(transitional_note(authority, "2023-01-01"), "")

    def test_an_amendment_on_the_facts_date_does_not_fire(self):
        """
        ⚠️ **وتعديلٌ في يوم الواقعة نفسه لا يُعدّ سابقاً لها.** فالتقاطع يُبنى
        على «قبل» لا على «عند»: الواقعة تُقرأ بالنصّ الذي كان ساريًا في يومها،
        وادّعاء العكس افتراضٌ في محلّ القراءة.
        """
        authority = Authority(
            key="same-day",
            instrument="سند بتعديل في يوم الواقعة",
            article="1",
            kind=SourceKind.LOCAL_LAW,
            official_source="جهة رسمية",
            in_force_from="2020-01-01",
            amended_by=("2024-03-10",),
        )
        self.assertEqual(transitional_note(authority, "2024-03-10"), "")
        self.assertNotEqual(transitional_note(authority, "2024-03-11"), "")

    def test_the_note_also_appears_in_the_check_reason(self):
        """
        ⚠️ **والإعلان يُحمَل في الحصيلة أيضاً**، فلا يحتاج القارئ أن ينادي
        الدالّة بنفسه على كل سند ليعرف أن هنا موضع نظر.
        """
        check = check_application(
            the_amended_authority(), [FACTS_STATING_NOTICE], AFTER_AMENDMENT
        )
        self.assertEqual(check.status, STATUS_APPLIES)
        self.assertIn(AMENDED_AT, check.reason)


# ==============================================================================
# ٤. الشروط — «تناقضه الوقائع» مقابل «لا تتكلّم عنه»
# ==============================================================================


class TestConditions(unittest.TestCase):
    """⚠️ الفرق بين «الوقائع تنفي هذا» و«الوقائع تسكت عن هذا» — وهو فرقُ تصرّف."""

    def test_contradicted_versus_unaddressed(self):
        """
        🔑🔑 **الاختبار الذي يفصل الحالتين، وهما ليستا واحدة:**

        * ``conditions_unmet`` — الوقائع **تناقض** الشرط: «لم يقم الطرف
          بإخطار كتابي» على شرط «قيام الطرف بإخطار كتابي». وهذا **اعتراض**
          يُصلَح في المسودّة أو في الواقعة، ويُعرَض على المحامي.
        * ``conditions_unverified`` — الوقائع **لا تتكلّم** عن الشرط. وهذا
          **سؤال** على المحامي، **وليس تحقّقاً ولا انتفاءً**.

        ⚠️ **ولا يوجد استنتاج ثالث اسمه «متحقّق».** لو قلنا «متحقّق» لأن
        الوقائع سكتت لصار السكوتُ إثباتاً — وهو أخطر من العيب الذي جاء الملف
        لمنعه، لأن المذكرة تُبنى على شرط لم يُثبته أحد.
        """
        authority = the_amended_authority()

        unmet = check_application(authority, [FACTS_NEGATING_NOTICE], "2023-03-01")
        self.assertEqual(unmet.status, STATUS_CONDITIONS_UNMET)
        self.assertEqual(unmet.unmet, (NOTICE_CONDITION,))
        self.assertEqual(unmet.unverified, ())
        self.assertFalse(unmet.is_error, "الشرط المتناقض لا يمنع التسليم")

        silent = check_application(authority, [FACTS_SILENT], "2023-03-01")
        self.assertEqual(silent.status, STATUS_CONDITIONS_UNVERIFIED)
        self.assertEqual(silent.unverified, (NOTICE_CONDITION,))
        self.assertEqual(silent.unmet, ())
        self.assertFalse(silent.is_error, "والسكوت لا يمنع التسليم أيضاً")

    def test_a_condition_the_facts_speak_to_is_not_reported(self):
        """
        ⚠️ **والمذكرة السليمة لا تُنذر.** الشرط الذي تتكلّم عنه الوقائع **لا
        يُدرَج** في `unverified`: الإدراج على الاحتياط يجعل كل سند مشروط
        مُعلَناً، فتصير الأداة إنذاراً دائماً لا يُقرأ.
        """
        check = check_application(
            the_amended_authority(), [FACTS_STATING_NOTICE], "2023-03-01"
        )
        self.assertEqual(check.status, STATUS_APPLIES)
        self.assertEqual(check.unverified, ())
        self.assertEqual(check.unmet, ())

    def test_an_authority_without_conditions_applies_when_in_force(self):
        """
        ⚠️ **وسند بلا شروط معلَنة: ``applies`` إن كان سارياً.**

        ⚠️ **و``applies`` هنا معناها «لم يُعترض عليها من داخل الجدول»، لا «ثبت
        انطباقها».** ولا يجوز أن يكون للملف رأي في نطاق مادة بلا شرط مُدرَج:
        ذلك نصّ قانون محفوظ، وهو ما ترفضه ترويسة الملف. ومن أراد الحكم الثاني
        فليُدرج شرطه.
        """
        check = check_application(the_open_ended_authority(), [], "2023-01-01")
        self.assertEqual(check.status, STATUS_APPLIES)

    def test_unmet_is_reported_before_unverified(self):
        """
        ⚠️ **الأشدّ يُذكر أوّلاً.** تقريرٌ يقول «ثمّة شرط لم تتكلّم عنه الوقائع»
        بينما شرطٌ آخر **تناقضه الوقائع صراحةً** يُخفي الأخطر بالأخفّ.
        """
        authority = Authority(
            key="two-conditions",
            instrument="سند بشرطين",
            article="3",
            kind=SourceKind.CABINET_DECISION,
            official_source="جهة رسمية",
            in_force_from="2020-01-01",
            conditions=(NO_MINISTRY_CONDITION, "تقديم طلب خلال الميعاد"),
        )
        check = check_application(
            authority, ["لم يصدر قرار من الوزارة"], "2023-01-01"
        )
        self.assertEqual(check.status, STATUS_CONDITIONS_UNMET)
        self.assertEqual(check.unmet, (NO_MINISTRY_CONDITION,))
        self.assertEqual(check.unverified, (), "والأخفّ لا يُذكر مع الأشدّ")

    def test_a_negation_that_does_not_touch_the_condition_is_not_a_contradiction(self):
        """
        ⚠️ **حدّ الفحص اللفظي، مُثبَّت في اختبار لا موصوف في تعليق.**

        ذكرُ النفي في واقعة **لا تتكلّم عن الشرط** ليس تناقضاً بل سكوت. ولو
        أُعلن تناقضاً لصار كل سطر فيه «لم» اتهاماً — وهو ما يجعل الأداة تُنذر
        دائماً. **وهذا هو الفرق بين ``conditions_unmet`` و``conditions_unverified``
        في موضعه الحسّاس.**
        """
        check = check_application(
            the_amended_authority(),
            ["لم يحضر جلسة التحكيم ولم يقدّم أي مستند"],
            "2023-03-01",
        )
        self.assertEqual(check.status, STATUS_CONDITIONS_UNVERIFIED)
        self.assertEqual(check.unmet, ())

    def test_every_condition_is_evaluated_separately(self):
        """
        ⚠️ **والشروط تُفحص فرادى لا جملةً**: الشرط الذي لا تتكلّم عنه الوقائع
        لا يُطوى لمجرد أن غيره متناقض — فيُقرأ كل شرط على حِدته.
        """
        authority = Authority(
            key="three-conditions",
            instrument="سند بثلاثة شروط",
            article="4",
            kind=SourceKind.LOCAL_LAW,
            official_source="جهة رسمية",
            in_force_from="2020-01-01",
            conditions=(
                NOTICE_CONDITION,
                "تقديم طلب خلال الميعاد",
                "سداد الرسم المقرر",
            ),
        )
        check = check_application(authority, [FACTS_NEGATING_NOTICE], "2023-01-01")
        self.assertEqual(check.status, STATUS_CONDITIONS_UNMET)
        self.assertEqual(check.unmet, (NOTICE_CONDITION,))

    def test_exceptions_are_carried_and_not_silently_dropped(self):
        """
        ⚠️ **والاستثناءات تُحمل ولا تُفحص — وهذا حدّ مقصود لا سهو.**

        إثبات استثناء **واقعةٌ لا تُخترع من عدم**، فلا يستنتجها الملف. ووجودها
        في الحصيلة يمنع أن يمرّ سندٌ إلى المذكرة باستثناءٍ نُسي.
        """
        authority = Authority(
            key="with-exceptions",
            instrument="سند باستثناءات",
            article="5",
            kind=SourceKind.FEDERAL_LAW,
            official_source="جهة رسمية",
            in_force_from="2020-01-01",
            conditions=(NOTICE_CONDITION,),
            exceptions=("ما لم يتّفق الطرفان على غير ذلك",),
        )
        check = check_application(authority, [FACTS_STATING_NOTICE], "2023-01-01")
        self.assertEqual(check.status, STATUS_APPLIES)
        self.assertEqual(check.exceptions, ("ما لم يتّفق الطرفان على غير ذلك",))
        self.assertIn("استثناءات", check.reason)

    def test_the_check_carries_its_authority_identity(self):
        """
        ⚠️ **الحكم بلا سنده لا يُقابَل بشيء** — فيُحمل معه المفتاح والمادة
        والاسم، **والشروط نفسها**: لو عُرضت الحالة وحدها لاحتج القارئ أن يفتح
        السجلّ ليعرف أيّ شرط رسب.
        """
        check = check_application(
            the_amended_authority(), [FACTS_SILENT], "2023-03-01"
        )
        self.assertEqual(check.key, "labour-43")
        self.assertEqual(check.article, "43")
        self.assertEqual(check.instrument, "المرسوم بقانون اتحادي رقم 33 لسنة 2021")
        self.assertEqual(check.conditions, (NOTICE_CONDITION,))

    def test_the_check_is_frozen(self):
        """الحكم لا يُعدَّل بعد إنشائه — فلا تتبدّل نتيجة أثناء تشغيل."""
        check = check_application(
            the_amended_authority(), [FACTS_SILENT], "2023-03-01"
        )
        self.assertIsInstance(check, ApplicationCheck)
        with self.assertRaises(Exception):
            check.status = STATUS_APPLIES  # type: ignore[misc]


# ==============================================================================
# ٥. العيب الثالث — مصدر ثانوي مقام النصّ
# ==============================================================================


class TestSecondaryAsPrimary(unittest.TestCase):
    """التعليق ليس النصّ، ولا يُنقل عنه نصٌّ يُنسب إلى مادة."""

    def test_a_secondary_summary_is_not_the_provision(self):
        """
        🔑🔑 **العيب الثالث الذي جاء الملف له.**

        ملخّص نتائج بحث قام مقام قراءة النصّ الذي سيُقتبس. والتعليق يقول
        «يُفهم من المادة كذا»، والنصّ يقول «يُحكم بكذا» — **وهويّة ما يُقتبس
        مختلفة، لا درجة الثقة**. ومن كتب «تنص المادة…» ونصُّ ما بين يديه ملخّص
        معلّق **لم يقتبس بتخمين، بل نسب إلى المادة ما لم تُرد به**.

        ⚠️ **وهو خطأ يمنع التسليم** كالاستشهاد بنصّ غير نافذ: كلاهما إخبار
        كاذب عن القانون، لا ثغرة في المُدخَل.
        """
        findings = secondary_as_primary(
            (the_secondary_source(),), DRAFT_CITING_A_SECONDARY
        )

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].kind, "secondary_as_primary")
        self.assertEqual(findings[0].key, "commentary-1")
        self.assertEqual(findings[0].source, "draft")
        self.assertIn(findings[0].kind, ERROR_FINDING_KINDS)
        self.assertTrue(findings[0].is_error)
        self.assertTrue(findings[0].detail, "الإعلان بلا شاهد لا يُصلَح")

    def test_a_quoted_secondary_source_is_caught(self):
        """وأخطرها: التعليق **صدر جملةً تُنقل حرفياً** بين علامتَي تنصيص."""
        # ⚠️ والاسم مكتوبٌ في المتن **بنصّه الخام** لا برسم مطبّع: الشاهد يُبنى على
        # النصّ الذي يفتحه المحامي، فلا تُطبّع الأسماء في متن الاختبار.
        draft = "ويقول تعليق على قانون المعاملات المدنية المدنية: «الإخطار واجب»."
        findings = secondary_as_primary((the_secondary_source(),), draft)
        self.assertEqual(len(findings), 1)

    def test_a_compound_citation_lead_is_caught(self):
        """
        ⚠️ **والصيغ المركّبة أكثر ما يُكتب في المذكرات الإماراتية**:
        «وفقاً لما ورد في التعليق…». ولو لم تُدرَج في القائمة لَمرّ التعليق
        مستشهداً به كأنه نصّ — **وهو العيب الثالث نفسه في ثوبه الأشيع**.
        """
        draft = "وفقا لما ورد في تعليق على قانون المعاملات المدنية المدنية فإن الإخطار واجب."
        self.assertEqual(
            len(secondary_as_primary((the_secondary_source(),), draft)), 1
        )

    def test_a_secondary_source_used_as_a_document_reference_is_caught(self):
        """وإذا صار التعليق موضع الإحالة على القانون، فهو سندٌ في غير موضعه."""
        draft = "المرجع: تعليق على قانون المعاملات المدنية المدنية رقم 5 لسنة 1985."
        self.assertEqual(
            len(secondary_as_primary((the_secondary_source(),), draft)), 1
        )

    def test_a_secondary_source_declared_as_secondary_is_not_flagged(self):
        """
        ⚠️ **والمذكرة السليمة لا تُعلَن.**

        ذكرُ التعليق على أنه تعليق — «لم نقف على نصّ يحكم الواقعة»، أو «وقد
        ناقش تعليق فلان هذه المسألة» — **تحريرٌ سليم** لا يجوز أن يُعلَن. ولو
        أُعلن لصار كل ذكرٍ لفقه خطأً، وهو الطريق إلى أداة تُنذر دائماً.
        **والفارق أن الاسم يُذكر بلا تمهيد استشهاد ولا تنصيص.**
        """
        silent = "ولم نقف في هذا الموضع على نصّ يحكم الواقعة."
        self.assertEqual(secondary_as_primary((the_secondary_source(),), silent), ())

        named = "وقد ناقش تعليق على قانون المعاملات المدنية المدنية هذه المسألة."
        self.assertEqual(secondary_as_primary((the_secondary_source(),), named), ())

    def test_a_primary_source_is_never_flagged_however_it_is_used(self):
        """
        ⚠️ **الفحص على التصنيف لا على الصيغة**: نصٌّ قانوني يُستشهد به بالصيغة
        نفسها **لا يُعلَن** — وإلا صار الفحص منعاً للاستشهاد بالنصّ.
        """
        draft = "وفقا لقانون المعاملات المدنية فإن الإخطار واجب قبل الإنهاء."
        self.assertEqual(secondary_as_primary((the_amended_authority(),), draft), ())

    def test_an_unmentioned_secondary_source_is_not_flagged(self):
        """
        ⚠️ **والإعلان بلا موضع لا يُصلَح**: المحامي لا يجد ما يُغيّر. فمصدرٌ
        ثانوي في السجلّ ولم يُذكر في المتن **لا يُعلَن** — ودَينُه في السجلّ
        يُرى بأداة أخرى (`unsourced`)، لا بإعلانٍ لا موضع له.
        """
        draft = "يلتزم الطرف الثاني بسداد الأجرة في مواعيدها المتفق عليها."
        self.assertEqual(secondary_as_primary((the_secondary_source(),), draft), ())

    def test_the_source_name_is_matched_across_spelling_variants(self):
        """
        ⚠️ **والاسم يُطابَق برسمه لا بتطابقه الحرفي**: أرقام هندية وتشكيل
        وترقيم زائد — وكلها الاختلافات التي تجعل الاسم نفسه يُكتب برسمين.
        ولو طُوبق حرفياً لسقط الإعلان عند أول اختلاف رسم.
        """
        draft = (
            "وفقا لتعليق على قانون المعاملات المدنية المدنية (طبعة ثانية) "
            "فإن الإخطار واجب."
        )
        self.assertEqual(
            len(secondary_as_primary((the_secondary_source(),), draft)), 1
        )

    def test_the_same_inputs_always_give_the_same_findings(self):
        """حتمية: المدخل نفسه يُعطي الإعلان نفسه بترتيبه نفسه."""
        first = secondary_as_primary(
            (the_secondary_source(), the_amended_authority()),
            DRAFT_CITING_A_SECONDARY,
        )
        second = secondary_as_primary(
            (the_secondary_source(), the_amended_authority()),
            DRAFT_CITING_A_SECONDARY,
        )
        self.assertEqual(first, second)

    def test_empty_draft(self):
        """بلا متن: لا إعلان ولا انهيار."""
        self.assertEqual(secondary_as_primary((the_secondary_source(),), ""), ())
        self.assertEqual(secondary_as_primary((the_secondary_source(),), None), ())


# ==============================================================================
# ٦. المصادر — ما بلا مصدر رسمي يُعلَن ولا يُعرض محقَّقاً
# ==============================================================================


class TestUnsourced(unittest.TestCase):
    """``official_source`` الفارغ معناه «لم يُتحقَّق»، لا «لا مصدر له»."""

    def test_unsourced_lists_the_authorities_with_no_official_source(self):
        """
        🔑 **الاختبار الأساسي، وفيه قراران:**

        1. السند الفارغ المصدر **يُدرَج** — ولا يُمرَّر كأنه محقَّق.
        2. **ولا يُرفض من السجلّ**: مصدرٌ لم يُتحقَّق بعد **يبقى مفيداً في
           الفحص الزمني وفحص الشروط**، وهما لا يحتاجان رابطاً. ولو اشترطنا
           مصدراً كاملاً للإدراج لتُرك السجلّ فارغاً — **فلا يُفحص شيء**.
        """
        found = unsourced((the_amended_authority(), the_secondary_source()))
        self.assertEqual([entry.key for entry in found], ["commentary-1"])
        self.assertEqual(found[0].official_source, "")

    def test_a_whitespace_only_source_is_not_a_source(self):
        """⚠️ ``"   "`` ليست مصدراً — وإلا صار السجلّ «موثَّقاً» بخانة فيها فراغ."""
        blank = Authority(
            key="blank",
            instrument="سند بخانة مصدر فارغة",
            article="1",
            kind=SourceKind.UNKNOWN,
            official_source="   ",
            in_force_from="2020-01-01",
        )
        self.assertEqual([entry.key for entry in unsourced((blank,))], ["blank"])

    def test_a_fully_sourced_register_reports_nothing(self):
        """وسجلّ كلّه بمصادر رسمية: لا إعلان — فلا تُنذر الأداة بلا سبب."""
        self.assertEqual(unsourced((the_amended_authority(),)), ())

    def test_unsourced_is_a_notice_not_an_error(self):
        """
        ⚠️ **و``unsourced`` ملاحظة لا خطأ.** المصدر الفارغ قد يكون سهو إدراج،
        والوقائع قد تكون صحيحة. ومن جعلها خطأً منع تسليم مذكرة سليمة بسبب
        **خانة تُملأ** — وهو الطريق إلى أداة تُنذر دائماً فلا تُقرأ.
        """
        payload = summarize(
            (), unsourced_authorities=unsourced((the_secondary_source(),))
        )
        self.assertTrue(payload["clean"])
        self.assertEqual(payload["error_count"], 0)
        self.assertEqual(payload["notice_count"], 1)
        self.assertIn("unsourced", NOTICE_FINDING_KINDS)
        self.assertNotIn("unsourced", ERROR_FINDING_KINDS)


# ==============================================================================
# ٧. العبارات التي تُقرّر القانون بلا سند
# ==============================================================================
#
# ⚠️⚠️ **ولماذا هذا الفحص في هذا الملف؟** لأن هذه العبارات **تعمل عمل السند
# وهي ليست سنداً**: القارئ يقرأ «استقر القضاء على كذا» فيفهم أن وراءها حكماً
# مستقرّاً فيسكت. ولو نُزعت العبارة لسأل: وما سندك؟ فالعبارة **تُغلق السؤال**
# بلا أن تُجيب عليه — وهي من جنس العيب الأول في هذا الملف.


class TestAssertedWithoutSource(unittest.TestCase):
    """مطابقة حتمية بلا نموذج — **ولا تفهم المعنى، فحدّها معلَن في الترويسة**."""

    def test_each_phrase_is_found(self):
        """
        🔑 **كل صيغة تُعلَن بموضعها وسياقها** — والموضع يُحفظ لأن الإعلان بلا
        موضع يُعيد القارئ إلى قراءة المستند كله ليجدها.
        """
        samples = {
            "استقر القضاء على أن الإخطار واجب.": "استقر القضاء",
            "وفاستقرت المحكمة على ذلك.": "استقرت المحكمة",
            "ومن المقرر قانوناً أن الإخطار واجب.": "من المقرر قانونا",
            "وهي بصفتها قاعدة مستقرة لا تحتاج بياناً.": "قاعد",
            "ومن الثابت قانوناً أن العقد ينتهي بمضي مدته.": "الثابت قانونا",
            "لا خلاف على أن الإخطار شرط للإنهاء.": "لا خلاف",
            "It is settled law that notice is required.": "settled law",
            "This is a well-established principle.": "well established principle",
        }
        for draft, expected in samples.items():
            with self.subTest(draft=draft):
                found = asserted_without_source(draft)
                self.assertTrue(found, f"لم يُعلَن شيء في: {draft}")
                joined = " · ".join(item.phrase for item in found)
                self.assertIn(expected, joined)

    def test_ordinary_legal_prose_produces_nothing(self):
        """
        🔑🔑 **ولا تُعلَن الجمل القانونية العادية.**

        وهذا هو الفرق بين أداة تُقرأ وأداةٍ تُنذر دائماً. والأنماط مبنيّة على
        **تركيب** لا على كلمة مفردة: «استقر» **مع** «القضاء»، و«المقرر» **مع**
        «قانوناً/في قضاء»، و«قاعدة» **مع** «مستقرة». فتُمرّ الجمل الثلاث
        الآتية بلا إعلان:

        1. «الاستقرار» في غير القضاء (استقرار العامل في مقرّ عمله).
        2. «المقرر» بمعنى المُعتمَد إدارياً.
        3. «قاعدة» بمعنى أساس أو ضابط حسابي.
        """
        prose = (
            "يستقر العامل في مقر العمل المتفق عليه في العقد.",
            "المقرر أن يُقدّم الطلب إلى الجهة المختصة مصحوباً بالمستندات.",
            "ويُحتسب البدل على القاعدة المتفق عليها في العقد المبرم بين الطرفين.",
        )
        for sentence in prose:
            with self.subTest(sentence=sentence):
                self.assertEqual(asserted_without_source(sentence), ())

    def test_a_quoted_phrase_attributed_to_a_source_is_not_an_assertion(self):
        """
        🔑🔑 **والمُقتبَس لا يُحاكَم هنا — وهذا موضع الفصل بين هذا الملف
        و`attribution.py`.**

        ما نقله الكاتب عن غيره موضعه `attribution.py` (أهو نصُّ مادّته؟). أما
        هذا الملف فيحاكم **القرار الذي قرّره الكاتب بلفظه**. فالعبارة بين
        علامتَي تنصيص **تُفرَّغ قبل الفحص**، ولو أُعلنت لكان كل نقلٍ عن حكم
        اتهاماً للكاتب بما لم يقله.

        ⚠️ **ويفحص الاختبار الحالتين**: الصيغة نفسها **تُعلَن** بلا تنصيص،
        و**لا تُعلَن** داخل التنصيص — فليس الإعلان عن العبارة وحدها.
        """
        inside = "ويقول المدعي «استقر القضاء على وجوب الإخطار» في مذكورته."
        self.assertEqual(asserted_without_source(inside), ())

        outside = "ويقول المدعي إن استقر القضاء على وجوب الإخطار."
        self.assertNotEqual(asserted_without_source(outside), ())

    def test_a_phrase_in_a_rejection_context_is_not_an_assertion(self):
        """
        ⚠️ **ومن كتب العبارة لينفيها لم يُقرّرها.**

        «ولا يصحّ القول بأن من المقرر قانوناً…» **تنفي** القاعدة، وإعلانُها
        تناقضٌ صريح مع معناها. والفحص لفظي ومحدود بنافذة قريبة، **وهو أشهر
        موضع لخطأ إعلانٍ كاذب في هذا الملف** (الحدّ الرابع في ترويسة الوحدة).
        """
        rejecting = "ولا يصحّ القول بأن من المقرر قانوناً أن الإخطار غير واجب."
        self.assertEqual(asserted_without_source(rejecting), ())

    def test_the_positions_point_at_the_phrase_in_the_supplied_text(self):
        """
        ⚠️ **والموضع يُقاس على النصّ المُعطى نفسه.** فلو حُذف المُقتبَس بدل
        تفريغه لتغيّرت المواضع، **فصار الموضع المُعلَن لا يوافق موضعاً في
        المستند الذي فتحه المحامي** — وإعلانٌ بموضع خاطئ أسوأ من غياب الموضع،
        لأن القارئ يبحث فلا يجد فيُكذّب الأداة كلها.
        """
        draft = "أولاً. ومن المقرر قانوناً أن الإخطار واجب. أخيراً."
        found = asserted_without_source(draft)
        self.assertEqual(len(found), 1)
        item = found[0]
        self.assertIsInstance(item, Assertion)
        self.assertEqual(draft[item.start : item.start + len(item.phrase)], item.phrase)
        self.assertTrue(item.context)

    def test_a_reported_prefix_defect_stays_fixed(self):
        """
        🔑🔑 **عيبٌ رُصد بمراجعة مستقلّة، ويُثبّت هنا فلا يعود.**

        كان النمط `(?:\u0648|\u0641)?` **يُجيز حرف عطف واحدًا**، والتعليق يَعِد بأن
        «و»/«ف» البادئة مرنة. فصيغة «وفاستقرت» — **وهي أوّل ما يُكتب** — **لا تُطابق**،
        لأن العربية تقدّم الحرفين معاً. **وهو أسوأ من غياب الصيغة**: صيغةٌ
        مكتوبة في القائمة ولا تعمل = **فشلٌ صامت**.

        ⚠️ **والأمثلة الثلاثة مُثبّتة معاً**، لأن إصلاح الحرفين كان يمكن أن يُسقِط
        الحرف الواحد.
        """
        samples = {
            "وفاستقرت المحكمة على ذلك.": "وفاستقرت المحكمة",
            "واستقرت المحكمة على ذلك.": "واستقرت المحكمة",
            "فاستقرت المحكمة على ذلك.": "فاستقرت المحكمة",
        }
        for draft, expected in samples.items():
            with self.subTest(draft=draft):
                found = asserted_without_source(draft)
                self.assertTrue(found, f"لم يُعلن شيء في: {draft}")
                self.assertEqual(found[0].phrase, expected)

    def test_a_reported_match_defect_stays_fixed(self):
        """
        🔑🔑 **عيبٌ ثانٍ من المراجعة نفسها: صيغةٌ في التعليق ولا تُطابق.**

        كان النمط `علي[هه]` — أي «عليه/عليها» — **فلا يُطابق «على»
        المجرّدة**، وهي الصيغة المكتوبة في تعليق القائمة نفسه: «لا خلاف على أن».
        وكانت «لا خلاف في أن» **تُعلَن** و«لا خلاف على أن» **لا تُعلَن**
        — والفرق بينهما حرفٌ لا معنى، **وهو علامةُ أن النمط لا يفعل ما وُعد به**.
        """
        samples = {
            "لا خلاف على أن الإخطار شرط للإنهاء.": "لا خلاف على أن",
            "لا خلاف في أن الإخطار شرط للإنهاء.": "لا خلاف في أن",
            "ولا خلاف على أن الإخطار شرط للإنهاء.": "ولا خلاف على أن",
            "لا جدال على أن الإخطار شرط للإنهاء.": "لا جدال على أن",
            "لا نزاع في أن الإخطار شرط للإنهاء.": "لا نزاع في أن",
        }
        for draft, expected in samples.items():
            with self.subTest(draft=draft):
                found = asserted_without_source(draft)
                self.assertTrue(found, f"لم يُعلن شيء في: {draft}")
                self.assertEqual(found[0].phrase, expected)

    def test_a_reported_quotation_defect_stays_fixed(self):
        """
        🔑🔑 **عيبٌ ثالث: صيغة النقطتين في علامة النقل عن مصدر ثانوي.**

        كان `_introduces_a_quotation` يطلب النقطتين **قبل** اسم المصدر ولا يقبلهما
        بعده — **وفي الصيغة الوثائقية نفسها («يقول تعليق فلان: «…»») النقطتان
        بعد الاسم**، فكان الشرط يرفض الصيغة التي جاء لأجلها.

        ⚠️ **والاختبار يثبّت الوجهين المنقولين**، لأن النصّ المنقول حرفياً عن تعليق
        **لا يمرّ من أي فحص آخر**: `attribution.py` يفحص نسبة النصّ إلى مادّته،
        ولا يعرف أن المصدر تعليق.
        """
        samples = (
            "ويقول تعليق على قانون المعاملات المدنية: «الإخطار واجب».",
            "ويقول تعليق على قانون المعاملات المدنية «الإخطار واجب».",
        )
        for draft in samples:
            with self.subTest(draft=draft):
                findings = secondary_as_primary((the_secondary_source(),), draft)
                self.assertEqual(len(findings), 1, draft)

    def test_the_quotation_helper_accepts_the_colon_on_either_side(self):
        """
        ⚠️ **وحدّ الدالّة نفسها:** النقطتان تُقبلان قبل الاسم أو بعده، لأن
        العربية تكتب الوجهين، **والعلامة واحدة في المعنى**.
        """
        self.assertTrue(authority._introduces_a_quotation("", ': «نصّ'))
        self.assertTrue(
            authority._introduces_a_quotation("وفقا ل", " : «نصّ")
        )
        self.assertFalse(
            authority._introduces_a_quotation("وفقا ل", " نصّ")
        )
        self.assertFalse(
            authority._introduces_a_quotation("راجع", " «نصّ")
        )

    def test_empty_input(self):
        """بلا نصّ: لا إعلان ولا انهيار."""
        self.assertEqual(asserted_without_source(""), ())
        self.assertEqual(asserted_without_source(None), ())

    def test_each_phrase_is_reported_once(self):
        """العبارة الواحدة لا تُعلَن مرّتين ولو طابقها نمطان (يُطوى التداخل)."""
        draft = "من المقرر قانوناً أن الإخطار واجب."
        self.assertEqual(len(asserted_without_source(draft)), 1)

    def test_the_detection_is_deterministic(self):
        """حتمية: النصّ نفسه يُعطي الإعلان نفسه بترتيبه نفسه (بترتيب النصّ)."""
        draft = (
            "ومن المقرر قانوناً أن الإخطار واجب. "
            "وقد استقر القضاء على أن الإنهاء يحتاج إخباراً."
        )
        first = asserted_without_source(draft)
        second = asserted_without_source(draft)
        self.assertEqual(first, second)
        self.assertEqual(
            [item.start for item in first], sorted(item.start for item in first)
        )


# ==============================================================================
# ٨. السجلّ — البحث والتكرار
# ==============================================================================


class TestAuthorityRegister(unittest.TestCase):
    """السجلّ: يُبنى مرة، ويُسأل بمفتاحه وباسم تشريعه — بلا حالة متغيّرة."""

    def test_lookup_by_key_and_by_instrument_article(self):
        """المفتاح الآلي واسم التشريع+المادة يُوصلان إلى السند نفسه."""
        register = AuthorityRegister(
            (the_amended_authority(), the_open_ended_authority())
        )
        self.assertEqual(register.by_key("labour-43").article, "43")
        self.assertEqual(
            register.by_instrument_article(
                "المرسوم بقانون اتحادي رقم 33 لسنة 2021", "43"
            ).key,
            "labour-43",
        )
        self.assertIsNone(register.by_key("لا-وجود"))
        self.assertIsNone(register.by_instrument_article("لا-وجود", "1"))
        self.assertEqual(len(register), 2)

    def test_the_instrument_article_match_folds_digits_and_spacing(self):
        """
        ⚠️ **«رقم ٣٣» و«رقم 33» سندٌ واحد.** ولولا طيّ رسم الأرقام لصار
        لسندٍ واحد مفتاحان يفترقان، **فيُسأل بأحدهما فلا يُوجد** — وهو الفرق
        الصامت الذي يُسقِط فحصاً كاملاً.
        """
        register = AuthorityRegister((the_amended_authority(),))
        self.assertIsNotNone(
            register.by_instrument_article(
                "المرسوم بقانون اتحادي رقم ٣٣ لسنة ٢٠٢١", "٤٣"
            )
        )
        self.assertIsNotNone(
            register.by_instrument_article(
                "  المرسوم  بقانون اتحادي رقم 33 لسنة 2021 ", "43"
            )
        )

    def test_a_duplicate_key_is_declared_and_the_first_wins(self):
        """
        ⚠️ **المفتاح المكرّر عيب إدراج يُعلَن ولا يُرفض به السجلّ.**

        رفضُ السجلّ كلّه لأجل مفتاح مكرّر **يحرم المحامي من فحص بقيّة
        الأسانيد** — وهو أسوأ من العيب. والبحث يُعيد **الأول** فلا يفترق
        الفهرس عن ترتيب الإدراج، والإعلان يمنع أن يُقرأ القرار صامتاً.
        """
        second = Authority(
            key="labour-43",
            instrument="سند آخر يشترك في المفتاح",
            article="99",
            kind=SourceKind.FEDERAL_LAW,
            official_source="جهة رسمية",
            in_force_from="2020-01-01",
        )
        register = AuthorityRegister((the_amended_authority(), second))

        self.assertEqual(register.duplicate_keys, ("labour-43",))
        self.assertEqual(register.by_key("labour-43").article, "43")
        self.assertEqual(len(register), 2, "والسند الثاني يبقى في السجلّ ويُفحص")

    def test_an_empty_register_is_valid(self):
        """سجلّ فارغ: صالح، وبحثه ``None``، ولا انهيار."""
        register = AuthorityRegister()
        self.assertEqual(len(register), 0)
        self.assertEqual(register.authorities, ())
        self.assertEqual(register.duplicate_keys, ())
        self.assertIsNone(register.by_key("أي-مفتاح"))

    def test_the_register_accepts_any_sequence_and_freezes_it(self):
        """
        ⚠️ **والسجلّ يُثبّت مُدخَله ولا يتبعه.** فلو بقي مربوطاً بقائمة
        المستدعي لَأمكن تعديل السجلّ من الخارج بعد بنائه — **فيُسأل عن سند لم
        يُدرج فيه**، ويتبدّل الحكم بلا أن يُنادى أحد.
        """
        supplied = [the_amended_authority()]
        register = AuthorityRegister(supplied)
        supplied.append(the_open_ended_authority())
        self.assertEqual(len(register), 1)

    def test_the_register_is_iterable_in_insertion_order(self):
        """⚠️ وترتيب الإدراج محفوظ — فالعرض على المحامي يتبع ترتيب إدخاله."""
        first, second = the_amended_authority(), the_open_ended_authority()
        register = AuthorityRegister((first, second))
        self.assertEqual([entry.key for entry in register], ["labour-43", "civil-1"])

    def test_a_key_is_required_and_a_free_text_kind_is_refused(self):
        """
        ⚠️ **والحرس على المفتاح والتصنيف لا على اسم التشريع.** سندٌ بلا مفتاح
        لا يُسأل به فتُخلط نتيجته بنتيجة غيره، وتصنيفٌ نصّيّ حرّ يُبنى عليه
        حكم `secondary_as_primary` — **فلا يُترك للقراءة الحرّة**. وأما اسم
        التشريع ورقم المادة فيُتركان ولو فراغاً: **بطاقة ناقصة تُعرَض ناقصةً
        خيرٌ من سند يُرفض إدراجه فلا يُفحص أصلاً.**
        """
        with self.assertRaises(ValueError):
            Authority(
                key="  ",
                instrument="سند بلا مفتاح",
                article="1",
                kind=SourceKind.FEDERAL_LAW,
                official_source="",
                in_force_from="2020-01-01",
            )
        with self.assertRaises(ValueError):
            Authority(
                key="x",
                instrument="سند بتصنيف نصّي",
                article="1",
                kind="تعليق",  # type: ignore[arg-type]
                official_source="",
                in_force_from="2020-01-01",
            )


# ==============================================================================
# ٩. الحصيلة — العدّادات، و``clean``، والسجلّ الفارغ
# ==============================================================================


class TestSummarize(unittest.TestCase):
    """العرض على المحامي والواجهة — JSON صالح، وعدّادات لا تفترق عن الفحوص."""

    def test_not_in_force_and_secondary_are_errors(self):
        """
        🔑🔑 **ولماذا هذان خطأان وغيرهما ملاحظة؟ — وهو أهمّ قرار في الملف.**

        * ``not_in_force`` إنما هو **استشهاد بنصّ لا يحكم الواقعة**: إمّا لم
          يكن نافذاً بعد، وإمّا أُلغي وحلّ غيره. **والكذب هنا في الزمن** —
          ولهذا لا يكشفه `citations.py` ولا `attribution.py`: النصّ موجود،
          ومنسوب إلى مادّته، والمصدر رسمي.
        * ``secondary_as_primary`` إنما هو **تقديم ملخّص مقام النصّ**: قولٌ عن
          القانون لا يقول القانون، ويُقرأ في المستند كأنه النصّ.

        فكلاهما **إخبار كاذب عن القانون**، والكاذب يمنع التسليم.
        """
        stale = check_application(
            the_amended_authority(), [FACTS_STATING_NOTICE], BEFORE_IN_FORCE
        )
        findings = secondary_as_primary(
            (the_secondary_source(),), DRAFT_CITING_A_SECONDARY
        )
        payload = summarize([stale], findings=findings)

        self.assertFalse(payload["clean"])
        self.assertEqual(payload["error_count"], 2)
        self.assertEqual(payload["not_in_force"], 1)
        self.assertEqual(payload["secondary_as_primary"], 1)

    def test_conditions_unverified_and_unsourced_are_notices(self):
        """
        ⚠️⚠️ **ولماذا هذان ملاحظتان؟** لأن كلاًّ منهما **ثغرة في المُدخَل لا
        كذباً في القول**: شرطٌ لا تتكلّم عنه الوقائع **سؤال يُطرح على المحامي**،
        وسندٌ بلا مصدر رسمي **خانة تُملأ**.

        ومن جعل هذين خطأً منع تسليم مذكرة سليمة لمجرد سؤال لم يُسأل — وهو
        الطريق إلى أداة تُنذر دائماً فلا تُقرأ، فتضيع فائدتها كلها. **وهما مع
        ذلك لا يُطويان**: يُعرَضان في العدّاد وفي الحصيلة المفصّلة.
        """
        unverified = check_application(
            the_amended_authority(), [FACTS_SILENT], "2023-03-01"
        )
        payload = summarize(
            [unverified],
            unsourced_authorities=unsourced((the_secondary_source(),)),
        )

        self.assertTrue(payload["clean"])
        self.assertEqual(payload["error_count"], 0)
        self.assertEqual(payload["notice_count"], 2)
        self.assertEqual(payload["conditions_unverified"], 1)
        self.assertEqual(payload["unsourced"], 1)

    def test_the_payload_is_json_safe_and_carries_the_detail(self):
        """
        🔑 الحصيلة تُبثّ إلى الواجهة: لا ``tuple`` ولا كائن غير قابل للترميز،
        **والتفصيل كامل** لأن العدّاد بلا تفصيل لا يُصلَح به شيء.
        """
        checks = [
            check_application(
                the_amended_authority(), [FACTS_NEGATING_NOTICE], "2023-03-01"
            ),
            check_application(
                the_amended_authority(), [FACTS_STATING_NOTICE], BEFORE_IN_FORCE
            ),
        ]
        payload = summarize(checks)
        encoded = json.dumps(payload, ensure_ascii=False)

        self.assertEqual(payload["total"], 2)
        self.assertEqual(payload["conditions_unmet"], 1)
        self.assertEqual(payload["not_in_force"], 1)
        self.assertEqual(payload["checks"][0]["status"], STATUS_CONDITIONS_UNMET)
        self.assertEqual(payload["checks"][0]["unmet"], [NOTICE_CONDITION])
        self.assertEqual(payload["checks"][1]["status"], STATUS_NOT_IN_FORCE)
        self.assertIn("labour-43", encoded)

    def test_an_empty_register_is_clean_and_says_so_in_arabic(self):
        """
        🔑🔑 **السجلّ الفارغ سليم — وهذا جواب صحيح لا فشل أداة.**

        مذكرة لا تعتمد على مادة **جوابٌ صحيح**، وقد صار في المشروع عرفٌ أن
        يُقال صراحةً بدل أن يُترك فراغاً يُقرأ عطباً. ولو خرج الفراغ بلا كلمة
        لَأعاد المستدعي التشغيل ظنّاً أن الفحص لم يُشغَّل.
        """
        payload = summarize(())

        self.assertTrue(payload["clean"])
        self.assertEqual(payload["total"], 0)
        self.assertEqual(payload["error_count"], 0)
        self.assertEqual(payload["notice_count"], 0)
        self.assertEqual(payload["checks"], [])
        self.assertEqual(payload["findings"], [])
        self.assertEqual(payload["note"], CLEAN_EMPTY_NOTE)
        self.assertIn("لا أسانيد", payload["summary"])
        self.assertTrue(re.search(r"[\u0600-\u06FF]", payload["note"]))

    def test_the_summary_line_names_every_kind_of_finding(self):
        """
        ⚠️ **وذكر الملاحظات في السطر ليس تفصيلاً:** حصيلةٌ تخرج ``clean`` وفيها
        شرطٌ لم تتكلّم عنه الوقائع **ليست** كحصيلة فُحصت كلها. والفرق بين «لم
        يُعترض على سند» و«تحقّق كل شرط» فرقٌ يُبنى عليه تصرّف.
        """
        checks = [
            check_application(the_amended_authority(), [FACTS_SILENT], "2023-03-01")
        ]
        payload = summarize(
            checks, unsourced_authorities=unsourced((the_secondary_source(),))
        )
        self.assertIn("شرط غير متحقَّق منه", payload["summary"])
        self.assertIn("بلا مصدر رسمي", payload["summary"])
        self.assertIn("من 1 سنداً", payload["summary"])

    def test_the_labels_cover_every_status_and_finding(self):
        """⚠️ وكل حالة وإعلان له وسم عربي — فلا يُعرض للقارئ مفتاحٌ لاتيني وحده."""
        for status in STATUSES:
            with self.subTest(status=status):
                self.assertIn(status, LABELS)
        for kind in ("secondary_as_primary", "unsourced"):
            with self.subTest(kind=kind):
                self.assertIn(kind, LABELS)

    def test_the_same_inputs_always_give_the_same_outcome(self):
        """
        🔑 **حتمية:** المدخل نفسه يُعطي الحصيلة نفسها، دائماً.

        وهي الضمان الذي يجعل الحصيلة تُبنى من المدخلات لا من ترتيب النداءات —
        **ولا حالة على مستوى الوحدة**، فمستدعٍ ثانٍ لا يقرأ نتيجة الأول.
        """

        def run() -> dict:
            return summarize(
                [
                    check_application(
                        the_amended_authority(),
                        [FACTS_NEGATING_NOTICE],
                        "2023-03-01",
                    ),
                    check_application(
                        the_amended_authority(),
                        [FACTS_STATING_NOTICE],
                        BEFORE_IN_FORCE,
                    ),
                ],
                findings=secondary_as_primary(
                    (the_secondary_source(),), DRAFT_CITING_A_SECONDARY
                ),
                unsourced_authorities=unsourced((the_secondary_source(),)),
            )

        self.assertEqual(run(), run())
        summarize(())  # نداءٌ بينهما لا يُغيّر نتيجة الثالث — فلا حالة محفوظة.
        self.assertEqual(run(), run())

    def test_the_counts_agree_with_the_detail(self):
        """⚠️ **ولا يفترق العدّاد عن التفصيل** — وإلا صار الرقم شهادة بلا دليل."""
        checks = [
            check_application(the_open_ended_authority(), [], "2023-01-01"),
            check_application(
                the_amended_authority(), [FACTS_STATING_NOTICE], BEFORE_IN_FORCE
            ),
            check_application(
                the_amended_authority(), [FACTS_NEGATING_NOTICE], "2023-03-01"
            ),
            check_application(
                the_amended_authority(), [FACTS_SILENT], "2023-03-01"
            ),
        ]
        payload = summarize(checks)
        self.assertEqual(
            payload["applies"]
            + payload["not_in_force"]
            + payload["conditions_unmet"]
            + payload["conditions_unverified"],
            payload["total"],
        )
        self.assertEqual(len(payload["checks"]), payload["total"])


# ==============================================================================
# ١٠. ضمانات على الوحدة نفسها — الحارس على الحدّ الأهمّ في الملف
# ==============================================================================


class TestModuleGuarantees(unittest.TestCase):
    """لو انكسرت هذه، انكسر الحدّ الذي يقوم عليه الملف كله."""

    @staticmethod
    def _source() -> str:
        return pathlib.Path(authority.__file__).read_text(encoding="utf-8")

    def test_imports_are_stdlib_only(self):
        """
        ⚠️ **لا تبعية خارجية** — وهي شرط عملي لا ذوقي: الوحدة تُستدعى في مسار
        الصياغة، وتبعية خارجية هنا تعني أن اختبارها يحتاج شبكةً أو مفتاحاً،
        **فلا يُشغَّل فلا يحمي شيئاً.**
        """
        imported = set(
            re.findall(
                r"^(?:from|import)\s+([A-Za-z_][\w\.]*)",
                self._source(),
                re.MULTILINE,
            )
        )
        allowed = {"__future__", "re", "dataclasses", "datetime", "enum", "typing"}
        self.assertTrue(imported <= allowed, f"استيرادات: {sorted(imported - allowed)}")
        self.assertNotIn(
            "citations", imported, "ولا استيراد من المشروع: الوحدة قائمة بذاتها"
        )

    def test_no_environment_network_or_printing(self):
        """لا بيئة، ولا شبكة، ولا طبع: وحدة تُطبع أثناء الاستيراد تُلوّث أي مسار."""
        source = self._source()
        for forbidden in (
            "os.environ",
            "getenv",
            "requests.",
            "urllib",
            "socket",
            "http",
            "print(",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)

    def test_no_legal_content_is_embedded(self):
        """
        🔑🔑 **ولا نصّ قانون ولا رقم تشريع ولا تاريخ نفاذ ولا قاعدة انتقالية.**

        ⚠️ **والدليل بالتحليل النحوي لا بمسح المصدر**، لأن التعليقات العربية
        تشرح العيوب وتذكر موادّها — **وشرح العيب ليس تشريعاً في الملف**. فما
        يُفحص هنا **القيم الحرفية في الكود** وحدها: لو كُتب تاريخ نفاذ أو رقم
        مادة في ثابت لظهر في ``ast.Constant``.

        ⚠️ **والسبب أن القاعدة المكتوبة في الكود تصير خطأً في اللحظة التي
        يتغيّر فيها النصّ، ولا شيء في المنظومة يُبلّغ بذلك**: تُعدَّل مادة،
        ويبقى الملف يحكم بالقديم **بثقة** — والثقة تمضي بالمذكرة إلى المحكمة.
        """
        tree = ast.parse(self._source())

        # ⚠️ **وتُستثنى ترويسات الدوالّ والمصنّفات** (`ast.get_docstring`)،
        # لأن أمثلة التوثيق تبني بطاقات في نصّ التوثيق نفسه. والمفحوص هو
        # **ما ينفّذه الكود**: لو كُتب تاريخ نفاذ في ثابت لظهر هنا.
        docstrings: set[int] = set()
        for node in ast.walk(tree):
            if isinstance(
                node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
            ):
                body = getattr(node, "body", None)
                if body and isinstance(body[0], ast.Expr) and isinstance(
                    body[0].value, ast.Constant
                ):
                    docstrings.add(id(body[0].value))

        literals = [
            node.value
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and id(node) not in docstrings
        ]
        self.assertTrue(literals, "لم تُقرأ قيم حرفية — فالفحص لم يجرِ أصلاً")

        iso = re.compile(r"\b(?:19|20)\d{2}-\d{2}(?:-\d{2})?\b")
        arabic_indic = re.compile(r"[\u0660-\u0669\u06F0-\u06F9]")
        law_number = re.compile(r"(?:رقم|لسنة)\s*[\d٠-٩]")

        for index, value in enumerate(literals):
            with self.subTest(index=index, value=value[:40]):
                self.assertIsNone(
                    iso.search(value), f"تاريخ محفوظ في الكود: {value[:60]!r}"
                )
                # ⚠️ **وجداول التطبيع مستثناة** (مثل `str.maketrans` ومجموعات الأرقام في الأنماط):
                # هي **أدوات لغوية** لا محتوى تشريعي، وحذفها يُعطّل المطابقة.
                # والممنوع رقمٌ منسوبٌ إلى تشريع — وهو ما يكشفه `law_number`.
                self.assertIsNone(
                    law_number.search(value), f"أرقام هندية في الكود: {value[:60]!r}"
                )
                self.assertIsNone(
                    law_number.search(value), f"رقم تشريع في الكود: {value[:60]!r}"
                )

    def test_the_verdict_follows_the_classification_and_no_rule_is_saved(self):
        """
        🔑 **والدليل سلوكيّ لا بمسح المصدر: الحكم تابعٌ لما مُرِّر، لا لمعرفة
        محفوظة في الوحدة.**

        السند نفسه، والواقعة نفسها، والتاريخ نفسه — **والتصنيف وحده هو ما
        يتغيّر**، فيتغيّر الحكم. ولو كان في الملف حكمٌ محفوظ لما تغيّر شيء.
        """
        as_provision = Authority(
            key="k",
            instrument="نصّ قانوني",
            article="1",
            kind=SourceKind.FEDERAL_LAW,
            official_source="جهة رسمية",
            in_force_from="2020-01-01",
        )
        as_summary = Authority(
            key="k",
            instrument="نصّ قانوني",
            article="1",
            kind=SourceKind.SECONDARY,
            official_source="جهة رسمية",
            in_force_from="2020-01-01",
        )
        draft = "وفقا لنصّ قانوني فإن الإخطار واجب."
        self.assertEqual(secondary_as_primary((as_provision,), draft), ())
        self.assertEqual(len(secondary_as_primary((as_summary,), draft)), 1)

    def test_the_temporal_verdict_follows_the_dates_and_not_a_saved_rule(self):
        """
        ⚠️ **والدليل نفسه على الفحص الزمني:** السند نفسه، والواقعة نفسها —
        **والتاريخ وحده هو ما يتغيّر**، فيتغيّر الحكم. فلو كانت في الملف قاعدة
        عن مادّة بعينها لَما تغيّر شيء بتغيير التاريخ.
        """
        authority = the_amended_authority()
        self.assertEqual(
            check_application(authority, [FACTS_STATING_NOTICE], BEFORE_IN_FORCE).status,
            STATUS_NOT_IN_FORCE,
        )
        self.assertEqual(
            check_application(authority, [FACTS_STATING_NOTICE], FACTS_DATE).status,
            STATUS_APPLIES,
        )

    def test_statuses_and_finding_kinds_are_closed_names(self):
        """الحالات والإعلانات **ثوابت مغلقة** تُقارَن، لا نصوص حرّة تُقرأ."""
        self.assertEqual(
            STATUSES,
            (
                STATUS_APPLIES,
                STATUS_NOT_IN_FORCE,
                STATUS_CONDITIONS_UNMET,
                STATUS_CONDITIONS_UNVERIFIED,
            ),
        )
        self.assertEqual(STATUS_NOT_IN_FORCE, "not_in_force")
        self.assertEqual(STATUS_CONDITIONS_UNVERIFIED, "conditions_unverified")
        self.assertEqual(ERROR_FINDING_KINDS, ("secondary_as_primary",))
        self.assertEqual(NOTICE_FINDING_KINDS, ("unsourced",))

    def test_the_secondary_kind_is_a_closed_value(self):
        """⚠️ وتصنيف التعليق **قيمة في مغلقة**، فلا يُدخل نصٌّ حرّ في تصنيف يُبنى عليه حكم."""
        self.assertIn("secondary", [kind.value for kind in SourceKind])
        self.assertIsInstance(SourceKind.SECONDARY, str)
        self.assertEqual(SourceKind.SECONDARY.value, "secondary")

    def test_no_module_level_state(self):
        """لا حالة على مستوى الوحدة: كل نداء يُعطي نتيجته من مدخلاته."""
        first = check_application(
            the_amended_authority(), [FACTS_STILL_VALID_SENTINEL], "2023-03-01"
        )
        check_application(the_amended_authority(), [], BEFORE_IN_FORCE)
        transitional_note(the_amended_authority(), AFTER_AMENDMENT)
        asserted_without_source("ومن المقرر قانوناً أن الإخطار واجب.")
        third = check_application(
            the_amended_authority(), [FACTS_STILL_VALID_SENTINEL], "2023-03-01"
        )
        self.assertEqual(first, third)

    def test_the_public_surface_is_the_one_the_project_asked_for(self):
        """الواجهة المطلوبة موجودة بأسمائها — فالمستدعي لا يبحث عنها."""
        for name in (
            "Authority",
            "AuthorityRegister",
            "SourceKind",
            "ApplicationCheck",
            "in_force_on",
            "transitional_note",
            "check_application",
            "secondary_as_primary",
            "unsourced",
            "asserted_without_source",
            "summarize",
        ):
            with self.subTest(name=name):
                self.assertTrue(hasattr(authority, name), f"الدالّة مفقودة: {name}")

    def test_finding_is_json_safe(self):
        """الإعلان الواحد يُبثّ إلى الواجهة بلا ترميز خاص."""
        finding = Finding(
            kind="unsourced",
            key="k",
            instrument="سند",
            article="1",
            source="register",
            reason="سبب",
            detail="شاهد",
        )
        self.assertFalse(finding.is_error)
        self.assertTrue(json.dumps({"k": finding.kind, "r": finding.reason}))


if __name__ == "__main__":
    unittest.main(verbosity=2)
