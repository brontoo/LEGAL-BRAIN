"""
اختبارات سجلّ القواعد — **الفصل بين ما يُفحص وما يتغيّر بالتشريع، مُثبَتاً.**
================================================================================

تشغيل:
    python -m unittest tests.test_rules
    python -m unittest discover -s tests -t . -v

حتمية بالكامل: بلا شبكة، وبلا نموذج، وبلا قاعدة بيانات، وبلا قرص (إلا قراءة
نصّ `rules.py` نفسه في فحصين بنيويين، على نمط `test_deadlines.py`).

**وأهمّ اختبارين في الملف هما الزوجان اللذان أنتجا الخطأ:**
`test_a_verification_rule_with_a_date_raises` و
`test_a_substantive_rule_without_a_date_raises` — فالخطأ الذي بلغ ثمانية
وعشرين في المئة في احتساب المكافأة أصلُه **حكم موضوعي قُرئ فحصاً دائماً**.
وهذا الملف يثبّت أن ذلك **مستحيل في البناء**، لا موكول إلى انتباه الكاتب.

ولماذا لا تحتاج هذه الاختبارات `fake_deps`؟ لأن `rules` وحدة نقية بلا حالة
وبلا إدخال/إخراج، كـ `citations.py` و`deadlines.py`. فلا شيء يُستعار ولا شيء
يُحاكى.
"""

from __future__ import annotations

import ast
import json
import pathlib
import unittest
from datetime import date

import case_file
import citations
import rules
from case_file import CaseStage, DisputeType
from rules import (
    SHIPPED,
    VERIFICATION_RULES,
    DistinctionFinding,
    DistinctionKind,
    Rule,
    RuleFamily,
    RuleSet,
    applicable,
    check_distinctions,
    clean_message,
    conflicts,
    for_key,
    must_review,
    summarize,
)


# ==============================================================================
# ١. أدوات الفحص — ونصّ الوحدة يُقرأ للفحص البنيوي وحده
# ==============================================================================


def _module_source() -> str:
    """نصّ الوحدة — يُقرأ للفحص البنيوي وحده، ولا يُقرأ منه رقم."""
    return pathlib.Path(rules.__file__).read_text(encoding="utf-8")


def _module_tree() -> ast.Module:
    """شجرة الوحدة النحوية — تُفحص بها الحدود التي لا يراها النداء."""
    return ast.parse(_module_source())


def _bare_number_literals() -> list[int]:
    """
    الأرقام الحرفية **غير المسمّاة** في كود الوحدة.

    ⚠️ **والمسمّى لا يُعدّ مكشوفاً:** ``_PROXIMITY_CHARS = 120`` رقمٌ له اسم
    معلن وتفسير مكتوب، فيُعَدّ في موضعه. وأما ``120`` عائمةً في سطر شرط
    فسقفٌ لا يُعرَف سببه ولا يُراجَع. فالفحص يطالب بأن **يكون لكل رقم اسم**
    — وهذا أوسع من منع رقم بعينه وأصدق.

    ⚠️ و`ast` مقصود بدل البحث النصّي: أمثلة التوثيق نصوصٌ لا تُنفَّذ، فلو
    بحثنا نصّاً لظهرت أرقام الأمثلة أرقاماً مُدرَجة — وهي شرحٌ لا قاعدة.
    والفحص على **ما يُنفَّذ** وحده.

    ⚠️ **والسالب يُقرأ عدداً**: ``-1`` في الشجرة ``UnaryOp`` على ثابت، فلو
    تُرك لمرّ «‐١» مجهولاً. والصواب أن يُقرأ قيمةً واحدة، لأن السالب قد يكون
    مدّةً سالبة كما قد يكون اصطلاح مكتبة.
    """
    tree = _module_tree()
    named: set[int] = set()

    def _number(node: ast.AST) -> ast.Constant | None:
        """الثابت الرقمي من عقدة، ولو كان سالباً أو موجباً بإشارة."""
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            if not isinstance(node.value, bool):
                return node
        if isinstance(node, ast.UnaryOp) and isinstance(node.operand, ast.Constant):
            if isinstance(node.operand.value, (int, float)) and not isinstance(
                node.operand.value, bool
            ):
                return node.operand
        return None

    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            targets, value = list(node.targets), node.value
        elif isinstance(node, ast.AnnAssign):
            targets, value = [node.target], node.value
        else:
            continue
        number = _number(value)
        if number is not None and any(
            isinstance(target, ast.Name) for target in targets
        ):
            named.add(id(number))

    bare = []
    for node in ast.walk(tree):
        number = _number(node) if isinstance(node, (ast.Constant, ast.UnaryOp)) else None
        if number is not None and id(number) not in named:
            bare.append(abs(number.value))
    return sorted(set(bare))


def _prose() -> str:
    """
    نثر الوحدة: توثيقها وتوثيق أصنافها — **بلا أسطر الأمثلة**.

    ⚠️ **والاستثناء محدود ومُعلَّل:** أمثلة التوثيق في `_adjacent` تُنشئ
    الصيغة التي يفحصها الملف **ليري كيف يمسكها**؛ فلو فُحصت لصار في الملف
    «إنذار كاذب» على شرحه. والنثر نفسه — وهو ما يُقرأ على المحامي — يبقى
    مفحوصاً كلّه.
    """
    parts = [rules.__doc__ or ""]
    for node in ast.walk(_module_tree()):
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            docstring = ast.get_docstring(node)
            if docstring:
                parts.append(docstring)
    prose = []
    for block in parts:
        prose.append(
            "\n".join(
                line
                for line in block.splitlines()
                if not line.strip().startswith((">>>", "..."))
            )
        )
    return "\n\n".join(prose)


#: قاعدة فحص صالحة — تُبنى في الاختبار ولا تُضاف إلى الجدول المشحون.
def _verification(
    key: str = "check.example",
    statement: str = "نصّ فحص.",
    subject: str = "check",
) -> Rule:
    """قاعدة فحص بسيطة — للاختبار، ولا تُشحن."""
    return Rule(
        key=key,
        family=RuleFamily.VERIFICATION,
        subject=subject,
        statement=statement,
    )


#: حكم موضوعي صالح — بمصدره وتاريخه.
def _substantive(
    key: str = "leave.basis",
    statement: str = "الأساس هو الأجر الأساسي.",
    source: str = "مصدر يتحقّق منه المحامي",
    in_force_from: str = "2021-01-01",
    supersedes: tuple[str, ...] = (),
    subject: str = "leave",
) -> Rule:
    """حكم موضوعي بسيط — للاختبار، ولا يُشحن."""
    return Rule(
        key=key,
        family=RuleFamily.SUBSTANTIVE,
        subject=subject,
        statement=statement,
        source=source,
        in_force_from=in_force_from,
        supersedes=supersedes,
    )


class TestTheTwoFamilies(unittest.TestCase):
    """
    🔑 **الزوج الذي أنتج الخطأ: فحصٌ بتاريخ، وحكمٌ بلا تاريخ.**

    ⚠️ والخطأ الذي بلغ ثمانية وعشرين في المئة لم يكن في معرفة القاعدة، بل في
    **موضعها**: حكم موضوعي وُضع في طبقة تُقرأ فحصاً لا يُراجَع، فبقي قانوناً
    ملغى يبدو سارياً. فالاختبارات هنا تُثبّت أن هذا الخلط **يرفع استثناءً
    عند البناء**، فلا يدخل السجلّ أصلاً.
    """

    def test_a_verification_rule_with_a_date_raises(self):
        """
        🔑 **قاعدة فحص تحمل تاريخ نفاذ — تُرفض.**

        والسبب أن التاريخ على الفحص **يدعو قارئه إلى الظنّ بأنه سيُراجَع**:
        من رأى تاريخاً على قاعدة ظنّ أنها مؤقّتة، فإمّا أهملها لأنها «قد
        تكون تبدّلت»، وإمّا اعتمدها لأنها «تبدو مُراجَعة». وهي لا تتبدّل
        أصلاً، فلا معنى للتاريخ ولا لانتظار المراجعة.
        """
        with self.assertRaises(ValueError) as caught:
            Rule(
                key="check.dated",
                family=RuleFamily.VERIFICATION,
                statement="قاعدة فحص بتاريخ — وهذا هو الخلط.",
                source="موضع الفحص",
                in_force_from="2024-01-01",
            )
        self.assertIn("قاعدة فحص بتاريخ نفاذ", str(caught.exception))

    def test_a_substantive_rule_without_a_date_raises(self):
        """
        🔑 **حكم موضوعي بلا تاريخ نفاذ — يُرفض، وهو أصل الخطأ.**

        الحكم الذي لا تاريخ له **يصير قانوناً ملغى يبدو سارياً**: يُقرأ
        سليماً ويُحسب به، ولا شيء في المنظومة يقول إن نصّاً آخر حلّ محلّه.
        وهذا بعينه ما أنتج نقصاً نحو ثمانية وعشرين في المئة في المكافأة.
        """
        with self.assertRaises(ValueError) as caught:
            Rule(
                key="leave.basis",
                family=RuleFamily.SUBSTANTIVE,
                statement="الأساس هو الأجر الأساسي.",
                source="مصدر يتحقّق منه المحامي",
            )
        self.assertIn("حكم موضوعي بلا تاريخ نفاذ", str(caught.exception))

    def test_a_substantive_rule_with_a_date_and_a_source_is_accepted(self):
        """
        الصورة الصحيحة: حكم موضوعي بمصدره وتاريخه — وهذا ما يُقبل.

        ولا يُشترط أن يكون الحكم صحيحاً — فذلك للمحامي — وإنما أن يكون
        **قابلاً للمراجعة**: مصدرٌ يُتحقَّق منه، وتاريخٌ يعرف القارئ منه
        من أيّ لحظة يسري.
        """
        rule = _substantive()
        self.assertEqual(rule.family, RuleFamily.SUBSTANTIVE)
        self.assertEqual(rule.in_force_from, "2021-01-01")
        self.assertTrue(rule.source.strip())
        self.assertFalse(rule.is_verification)

    def test_a_non_iso_date_raises(self):
        """
        التاريخ بصيغة ISO وحدها — وإلا رُفض.

        ⚠️ والسبب أن هذا الحقل **يُقارَن بالوقائع** في `applicable`؛ فتاريخ
        حرّ («مارس ٢٠٢٤») لا يُقارَن، فتمرّ قاعدةٌ لأن تاريخها لم يُفهَم —
        وهو العيب نفسه بثوب آخر.
        """
        with self.assertRaises(ValueError) as caught:
            _substantive(in_force_from="مارس ٢٠٢٤")
        self.assertIn("تاريخ نفاذ غير صالح", str(caught.exception))

    def test_an_empty_key_or_statement_is_refused(self):
        """مفتاح فارغ أو نصّ فارغ: لا قاعدة — ولا تصل إلى جدول."""
        with self.assertRaises(ValueError):
            _verification(key="   ")
        with self.assertRaises(ValueError):
            Rule(key="check.empty", family=RuleFamily.VERIFICATION, statement="  ")

    def test_the_family_has_exactly_two_values(self):
        """
        والعائلتان مغلقتان على قيمتين — فلا ثالثة تُخترع بينهما.

        لو أُضيفت قيمة ثالثة («فحص مؤقّت» مثلاً) لسقط الفصل الذي وُجد الملف
        له: يصير الحكم المتغيّر مقبولاً في طبقة تُقرأ فحصاً، وهو الخلط بعينه.
        """
        self.assertEqual(
            {member.value for member in RuleFamily},
            {"verification", "substantive"},
        )
        self.assertIsInstance(RuleFamily.VERIFICATION, str)

    def test_a_rule_is_frozen(self):
        """القاعدة لا تُعدَّل بعد إنشائها — فلا تتبدّل قاعدة أثناء تشغيل."""
        rule = _verification()
        with self.assertRaises(Exception):
            rule.statement = "آخر"  # type: ignore[misc]


class TestTheShippedTable(unittest.TestCase):
    """
    الجدول المشحون: **فحوصٌ وحدها**، ولا حكم موضوعي ولا رقم مادة واحد.

    وهذه الاختبارات تحرس **حدود الجدول** لا صحّته القانونية: أن يكون فارغاً
    من الأحكام الموضوعية، وأن يحمل كل سطر مصدره، وأن يُصرّح بأنّه **ليس
    بياناً بالقانون** — والتصريح في الكود لا في وثيقة خارجية، لأن من قرأ
    الجدول قرأ الكود.
    """

    def test_the_shipped_table_contains_no_substantive_rule(self):
        """
        🔑 **لا حكم موضوعي واحد في الجدول — يُفحص مباشرةً.**

        وهذا أهمّ ما في هذا الصنف: لو أضاف أحدهم سطراً موضوعياً «لأنه يبدو
        مفيداً» لصار في المنظومة **قانونٌ بلا تاريخ**، وهو العيب الذي جاء
        الملف لمنعه. فالاختبار يفحص الأمر **على الجدول نفسه**، لا على نيّة
        من كتبه.
        """
        self.assertEqual(SHIPPED.by_family(RuleFamily.SUBSTANTIVE), ())
        self.assertEqual(
            {rule.family for rule in SHIPPED.rules},
            {RuleFamily.VERIFICATION},
        )
        self.assertEqual(
            {rule.family for rule in VERIFICATION_RULES},
            {RuleFamily.VERIFICATION},
        )

    def test_every_shipped_rule_has_no_date_and_names_its_source(self):
        """
        وكل سطر فحص: **بلا تاريخ، وبمصدره** — والشرطان معاً.

        المصدر هو الذي يُعرَف به **الفحص الذي ينفّذ القاعدة**، فتصير القاعدة
        قابلة للتحقّق من الكود لا من نيّة كاتبها. والفحص بلا مصدر **رأيٌ
        يتنكّر في هيئة قاعدة**.
        """
        for rule in VERIFICATION_RULES:
            with self.subTest(key=rule.key):
                self.assertTrue(rule.is_verification)
                self.assertEqual(rule.in_force_from, "")
                self.assertTrue(rule.source.strip())
                self.assertTrue(rule.statement.strip())
                self.assertTrue(rule.note.strip())

    def test_the_five_named_rules_are_present_in_the_objectives_order(self):
        """
        القواعد الخمسة التي حدّدها الوصف — بنصوصها وترتيبها.

        والترتيب مقصود: البحث في الاقتباس، ثم صيغته، ثم الواقعة، ثم الحساب،
        ثم نفاذ النصّ، ثم الطلب غير المجاب — وهذا هو ترتيب ما يُراجَع في
        المسودّة: من السند إلى الحكم إلى الاستحقاق.
        """
        keys = SHIPPED.keys
        self.assertEqual(
            keys,
            (
                "cite.traceable",
                "cite.quote_is_wording",
                "fact.source_and_standing",
                "calc.basis_and_inputs",
                "provision.in_force_on_facts",
                "claim.unanswered_visible",
            ),
        )
        self.assertIn("مقطع مسترجع", for_key(SHIPPED, "cite.traceable").statement)
        self.assertIn("نصّ المادة", for_key(SHIPPED, "cite.quote_is_wording").statement)
        self.assertIn("درجتها", for_key(SHIPPED, "fact.source_and_standing").statement)
        self.assertIn("أساسه ومدخلاته", for_key(SHIPPED, "calc.basis_and_inputs").statement)
        self.assertIn("سارياً", for_key(SHIPPED, "provision.in_force_on_facts").statement)
        self.assertIn("لم يُجَب", for_key(SHIPPED, "claim.unanswered_visible").statement)

    def test_the_table_states_it_is_not_a_statement_of_the_law(self):
        """
        ⚠️ الحدّ مكتوب **في الكود** — «ليس بياناً بالقانون» و«للمحامي».

        والتحذير الذي يعيش في وثيقة خارجية لا يُقرأ مع ما يحذّر منه. فالفحص
        هنا على نصّ الوحدة، على ما فُعل في `test_labour_rules.py`.
        """
        source = _module_source()
        self.assertIn("ليس بياناً بالقانون", source)
        self.assertIn("للمحامي", source)

    def test_no_article_number_is_embedded(self):
        """
        🔑 **ولا رقم مادة واحد في نصّ الوحدة — بفحص `citations` نفسه.**

        ⚠️ والمصدر واحد عن قصد: صيغة الإشارة إلى المادة في `citations.py` هي
        صيغة المشروع، فلو فحصناها هنا بفحصٍ آخر لأمكن أن يمرّ الرقم هناك
        ويسقط هنا — وهو **حكمان لنصّ واحد**. والفحص على النصّ كلّه (توثيقاً
        وتعليقاً وكوداً)، فلا يمرّ رقمٌ من أيّ باب.

        ولماذا الرفض بهذه الشدّة؟ لأن رقم المادة المكتوب في الكود **يُوهم
        بعين المرجع**: من قرأه ظنّ أنّ الرقم محقَّق في المشروع، وليس كذلك —
        والرقم المخمَّن **يمضي إلى المذكرة**، بخلاف الغياب الذي يوقف الكاتب.
        """
        refs = citations.find_article_refs(_module_source())
        self.assertEqual(
            [ref.surface for ref in refs],
            [],
            "رقم مادة مُدرَج في الوحدة — وهذا ما لا يُكتب هنا.",
        )
        # وحراسة الفحص نفسه: لو تغيّرت صيغة `citations` لصار الفحص أعمى.
        self.assertEqual(citations.find_article_refs("وفقاً للمادة ٢٤٦")[0].number, "246")

    def test_no_legal_period_and_no_bare_number_is_embedded(self):
        """
        🔑 **ولا مدّة قانونية ولا رقم غير مسمّى في كود الوحدة** — على نمط فحص
        العطلات في `test_deadlines.py`.

        ⚠️ والفحص على **شجرة النحو** لا على النصّ: أمثلة التوثيق نصوصٌ لا
        تُنفَّذ، فلو بحثنا نصّاً لظهرت أرقام الأمثلة أرقاماً مُدرَجة. والذي
        يُفحص هنا هو **ما يُنفَّذ** — وكل رقم فيه له **اسم معلن**: لا مدّة
        إشعار ولا مدّة تقادم ولا عدد أيام مجرّداً. فالرقم المحفوظ في الكود
        **يصير خطأً في اللحظة التي يتغيّر فيها النصّ، ولا شيء في المنظومة
        يُبلّغ بذلك** — وهذا بعينه ما أنتج الثمانية والعشرين في المئة.
        """
        self.assertEqual(
            _bare_number_literals(),
            [],
            "أرقام غير مسمّاة في كود الوحدة — وكلّها مشتبهة كمدّة أو سقف.",
        )
        # وحراسة الفحص نفسه: الرقم المسمّى الوحيد في الملف معروف، فلا يصير
        # الفحص أعمى لو حُذف الاسم يوماً.
        self.assertEqual(rules._PROXIMITY_CHARS, 120)
        self.assertFalse(hasattr(rules, "LEGAL_PERIODS"))

    def test_the_module_prose_does_not_trip_its_own_check(self):
        """
        ⚠️ **نثر الوحدة لا يُنتج ملاحظة على نفسه.**

        والسند عمليّ: هذا الملف يُنتج تقريراً بالعربية، وتقريره سيُقرأ إلى
        جانبه. فلو أطلق الملف ملاحظة على شرحه، صار **إنذاراً كاذباً في أوّل
        ما يُقرأ** — وصدّق القارئ الإنذار كذّب التقرير كله. وهذا الدرس نفسه
        مكتوب في `language_audit.py` حين وُسمت أحد عشر سلوكاً صحيحاً أخطاءً
        فضاع التقرير.
        """
        self.assertEqual(check_distinctions(_prose()), ())


class TestDistinctions(unittest.TestCase):
    """
    🔑 **الفروق الأربعة: تُمسَك حين تُخلط، ولا تُمسَك حين تُفصل.**

    ⚠️ وهذا الصنف هو **الرصيد الأهمّ في الملف**: فحصٌ يُنذر على الصياغة
    الصحيحة أسوأ من فحصٍ لا يُنذر أصلاً — لأن الأول يُفقد الثقة فيُهمَل
    التقرير كله. ولذلك لكل فرق **صيغ محرَّرة** يُثبت الاختبار أنها تعبر
    بلا ملاحظة.
    """

    #: ⚠️ **صيغ محرَّرة — كلّها تذكر طرفَي الفرق وتفصل بينهما.**
    #:
    #: وهي جواب العيب لا العيب: من كتب «آخر يوم عمل ليس تاريخ انتهاء العقد»
    #: فقد فعل ما وُجد هذا الملف لأجله. فمرورها بلا ملاحظة **شرط قبول** لا
    #: ترف.
    CAREFUL_SENTENCES: tuple[str, ...] = (
        "آخر يوم حضور للمدعي هو ٢٠٢٥-٠٣-٠١، وأما تاريخ انتهاء العقد فهو ٢٠٢٥-٠٣-٣١.",
        "آخر يوم عمل ليس تاريخ انتهاء العقد، فالأول واقعة حضور والثاني واقعة إنهاء.",
        "أجر الإجازة عن مدة خدمة يُحسب على الأجر الأساسي، بينما الرصيد المتراكم "
        "عند الانتهاء يُصرف على أساس آخر.",
        "بدل الإجازة الذي يُصرف عند انتهاء الخدمة بدلٌ عن رصيد متراكم، لا أجر عن "
        "مدة عمل.",
        "الأجر الشامل ٨٠٠٠ درهم، ورصيد الإجازة ١١ يوماً، ويُحسب البدل على الأجر "
        "الأساسي.",
        "لا يستحق المدعي أي مبلغ، ولا ننازع في طريقة الاحتساب.",
        "لا ينازع المدعى عليه في استحقاق العمولة، وإنما ينازع في مقدارها.",
        "الفحص يجب أن يكون ثابتاً، بينما النصّ القانوني الساري يتغير بتغير "
        "التشريع.",
        "معيار الاحتساب الذي يسري على واقعة ٢٠٢٤-٠٥-١٠ يجب أن يُثبت أنه كان "
        "نافذاً في ذلك التاريخ.",
    )

    def test_attendance_is_not_confused_with_the_end_of_the_contract(self):
        """
        🔑 **الفرق الأول: «آخر يوم عمل» مقروناً بـ«انتهاء العقد» بلا فاصل.**

        وهما يفترقان حين يُعفى العامل من الحضور خلال مدّة الإشعار: العقد يبقى
        قائماً مدّةً لا يعمل فيها العامل، والفرق **يغيّر ما هو واجب**.
        """
        findings = check_distinctions(
            "آخر يوم عمل للمدعي هو ٢٠٢٥-٠٣-٣١، وينتهي العقد في التاريخ نفسه."
        )
        self.assertEqual([item.kind for item in findings], [DistinctionKind.ATTENDANCE_VS_END])
        self.assertTrue(findings[0].quote)
        self.assertIn("انتهاء العقد", findings[0].why)

    def test_leave_wage_is_not_confused_with_the_accrued_balance(self):
        """
        🔑 **الفرق الثاني: أجر الإجازة عن مدّة وصرف الرصيد المتراكم.**

        الأول **أجر عن مدّة**، والثاني **صرف رصيد** — والأساس مختلف والحساب
        مختلف، وجمعهما في حساب واحد أنتج رقماً خاطئاً في هذا المشروع.
        """
        findings = check_distinctions(
            "أجر الإجازة عن المدة، ورصيد الإجازة المتراكم، كلاهما يُحسب على "
            "الأجر الأساسي."
        )
        self.assertEqual(
            [item.kind for item in findings],
            [DistinctionKind.LEAVE_DURING_VS_BALANCE],
        )

    def test_denying_entitlement_while_disputing_the_amount_is_caught(self):
        """
        🔑 **الفرق الثالث: نفيُ الاستحقاق والنزاعُ في المقدار معاً.**

        وقد عبّرت إحدى المراجعات عن العيب بدقّة: صياغة هذا المشروع **دمجت
        الاستحقاق بالمقدار**. ومن دمجها قرأ الإقرار نزاعاً والنزاع إنكاراً.
        """
        findings = check_distinctions(
            "لا يستحق المدعي أي مبلغ، والمبلغ المطالب به مبالغ فيه."
        )
        self.assertEqual(
            [item.kind for item in findings],
            [DistinctionKind.ENTITLEMENT_VS_QUANTUM],
        )

    def test_a_law_presented_as_a_fixed_check_is_caught(self):
        """
        🔑 **الفرق الرابع: نصّ تشريعي يُوصف بأنه لا يتبدّل.**

        وهذا هو العيب الذي أنتج الثمانية والعشرين في المئة بعينه: حكمٌ
        موضوعي قُرئ فحصاً دائماً، فلا سؤال عن نفاذه ولا عن ملغاةٍ حلّت محله.
        """
        findings = check_distinctions("المادة ٥ من القانون هي قاعدة ثابتة لا تتغير.")
        self.assertEqual(
            [item.kind for item in findings],
            [DistinctionKind.VERIFICATION_VS_SUBSTANTIVE],
        )

    def test_careful_prose_produces_nothing(self):
        """
        🔑 **والأهمّ: الصياغة التي تفصل لا تُنتج ملاحظة — تسع صيغ.**

        ⚠️ والعدد مقصود: صيغة واحدة قد تعبر مصادفةً بعبارة فصل، وتسع صيغ
        تُثبت أن الفحص **لا يعاقب من أحسن**. وكل صيغة هنا تذكر طرفَي فرق
        وتفصل بينهما بعبارة صريحة أو بحرف فصل.
        """
        self.assertGreaterEqual(len(self.CAREFUL_SENTENCES), 4)
        for sentence in self.CAREFUL_SENTENCES:
            with self.subTest(sentence=sentence[:40]):
                self.assertEqual(
                    check_distinctions(sentence),
                    (),
                    "ملاحظة على صياغة تفصل بين المفهومين — وهذا إنذار كاذب.",
                )

    def test_the_four_distinctions_are_named(self):
        """والفروق أربعة **معلنة بأسمائها** — فلا فرق بلا اسم يُسأل عنه."""
        self.assertEqual(
            {member.value for member in DistinctionKind},
            {
                "attendance_vs_end",
                "leave_during_vs_balance",
                "entitlement_vs_quantum",
                "verification_vs_substantive",
            },
        )
        for member in DistinctionKind:
            with self.subTest(kind=member.value):
                self.assertTrue(rules.DISTINCTION_LABELS[member].strip())

    def test_a_finding_carries_the_offending_text(self):
        """
        والملاحظة **تحمل العبارة كما كُتبت** — وإلا لم يستطع المحامي أن يردّ.

        ⚠️ والاقتباس بعد طيّ رسم الحروف (الألف والتاء المربوطة والتشكيل)،
        لأن المطابقة تجري على المطويّ، ولو أُعيد النصّ الأصلي لصار الدليل
        **لا يُقابَل بما طُوبق**. والطيّ لا يُخفي لفظاً: هو رسم الحرف نفسه.
        """
        findings = check_distinctions("المادة ٩ من القانون هي قاعدة ثابتة لا تتغير.")
        self.assertEqual(len(findings), 1)
        self.assertIn("قاعده ثابته", findings[0].quote)
        self.assertIsInstance(findings[0], DistinctionFinding)
        self.assertEqual(findings[0].label, "فحصٌ عامّ ≠ حكم موضوعي")

    def test_a_finding_is_not_repeated_for_the_same_sentence(self):
        """
        والعبارة الواحدة **لا تُنتج الملاحظة مرّتين** — والتكرار يُشوّش.

        وهذا الدرس مكتوب في `language_audit.py`: التقرير الذي يملأه التكرار
        لا يُقرأ، وإذا لم يُقرأ لم يُنذر.
        """
        text = (
            "المادة ٥ من القانون قاعدة ثابتة لا تتغير. "
            "المادة ٥ من القانون قاعدة ثابتة لا تتغير."
        )
        findings = check_distinctions(text)
        quotes = [item.quote for item in findings]
        self.assertEqual(len(quotes), len(set(quotes)))

    def test_empty_and_none_inputs_are_safe(self):
        """نصّ فارغ أو ``None``: لا ملاحظة ولا استثناء — والفحص لا يفترض نصّاً."""
        self.assertEqual(check_distinctions(""), ())
        self.assertEqual(check_distinctions("   \n  "), ())
        self.assertEqual(check_distinctions(None), ())

    def test_the_detector_is_stated_to_be_a_checklist_not_an_opinion(self):
        """
        ⚠️ **الحدّ مكتوب في الكود: قائمة تحقّق لا رأي قانوني.**

        ولماذا يُفحص هذا نصّاً؟ لأن أخطر ما يمكن أن يفعله هذا الملف أن يُقرأ
        تقريره **حكماً قانونياً**. فالتصريح بحدّه جزء من عمله، لا تعليق عليه.
        """
        source = _module_source()
        self.assertIn("قائمة تحقّق", source)
        self.assertIn("لا رأي قانوني", source)
        self.assertIn("ليس شهادة سلامة", source)


class TestApplicable(unittest.TestCase):
    """
    الترشيح على ثلاثة: نوع النزاع، والمرحلة، والتاريخ — **والفراغ يعني الكل**.

    ⚠️ والفراغ في النوع أو المرحلة **ليس «لا شيء»**: قاعدة لا تسري على شيء
    وجودها عبث. وهذا الفرق يُثبَّت هنا لأنه يُقرأ خطأً في أكثر الأحيان.
    """

    def test_an_empty_applies_to_means_every_dispute_type(self):
        """
        ``applies_to`` فارغة: القاعدة تسري على **كل** أنواع النزاع.

        وهذا هو حال قواعد الفحص المشحونة: هي على الوثيقة لا على نوع النزاع،
        فلو قُلنا إن الفراغ يعني «لا نوع» لسقطت كل قواعد الفحص من كل قضية —
        وهو نقيض المقصود.
        """
        for dispute_type in DisputeType:
            with self.subTest(dispute_type=dispute_type.value):
                self.assertEqual(
                    len(applicable(None, dispute_type, CaseStage.FIRST_INSTANCE)),
                    len(VERIFICATION_RULES),
                )

    def test_an_empty_stages_means_every_stage(self):
        """``stages`` فارغة: القاعدة تسري في **كل** المراحل."""
        for stage in CaseStage:
            with self.subTest(stage=stage.value):
                self.assertEqual(
                    len(applicable(None, DisputeType.LABOUR, stage)),
                    len(VERIFICATION_RULES),
                )

    def test_the_dispute_type_filter_is_honoured(self):
        """نوع مذكور: القاعدة تسري عليه، ولا تسري على غيره."""
        labour_only = Rule(
            key="check.labour",
            family=RuleFamily.VERIFICATION,
            subject="check",
            applies_to=(DisputeType.LABOUR,),
            statement="فحص يخصّ النزاع العمالي.",
        )
        rule_set = RuleSet(rules=(labour_only,))
        self.assertEqual(
            applicable(rule_set, DisputeType.LABOUR, CaseStage.FIRST_INSTANCE),
            (labour_only,),
        )
        self.assertEqual(
            applicable(rule_set, DisputeType.LEASE, CaseStage.FIRST_INSTANCE),
            (),
        )

    def test_the_stage_filter_is_honoured(self):
        """ومرحلة مذكورة: تسري فيها وحدها."""
        appeal_only = Rule(
            key="check.appeal",
            family=RuleFamily.VERIFICATION,
            subject="check",
            stages=(CaseStage.APPEAL,),
            statement="فحص يخصّ مرحلة الاستئناف.",
        )
        rule_set = RuleSet(rules=(appeal_only,))
        self.assertEqual(
            applicable(rule_set, DisputeType.CIVIL, CaseStage.APPEAL),
            (appeal_only,),
        )
        self.assertEqual(
            applicable(rule_set, DisputeType.CIVIL, CaseStage.CASSATION),
            (),
        )

    def test_a_rule_with_no_date_applies_and_a_dated_rule_does_not_before_it(self):
        """
        🔑 **والتاريخ لا يُرشَّح به إلا ما حمل تاريخاً.**

        فقاعدة الفحص تسري دائماً، والحكم الموضوعي يسري من تاريخ نفاذه.
        ⚠️ و``on_date`` الفارغ **لا يُطابق المؤرَّخة**: الجهل بتاريخ الوقائع
        **يُقلّل** ما يسري ولا يزيد، لأن ضدّه إدخال حكم بلا سؤال «هل كان
        نافذاً؟» — وهو أصل الخطأ الذي جاء الملف لمنعه.
        """
        dated = _substantive(key="leave.basis", in_force_from="2024-01-01")
        older = _substantive(
            key="leave.old", in_force_from="2010-01-01", statement="نصّ قديم."
        )
        rule_set = RuleSet(rules=(_verification(), dated, older))

        with self.subTest("قبل النفاذ"):
            self.assertEqual(
                [rule.key for rule in applicable(rule_set, DisputeType.LABOUR, CaseStage.FIRST_INSTANCE, "2023-06-01")],
                ["check.example", "leave.old"],
            )
        with self.subTest("بعد النفاذ"):
            self.assertEqual(
                [rule.key for rule in applicable(rule_set, DisputeType.LABOUR, CaseStage.FIRST_INSTANCE, "2024-06-01")],
                ["check.example", "leave.basis", "leave.old"],
            )
        with self.subTest("بلا تاريخ — لا تُطابق المؤرَّخة"):
            self.assertEqual(
                [rule.key for rule in applicable(rule_set, DisputeType.LABOUR, CaseStage.FIRST_INSTANCE)],
                ["check.example"],
            )
        with self.subTest("يوم النفاذ نفسه يُحسب"):
            self.assertEqual(
                len(applicable(rule_set, DisputeType.LABOUR, CaseStage.FIRST_INSTANCE, "2024-01-01")),
                3,
            )

    def test_the_order_is_the_table_order(self):
        """والترتيب هو ترتيب الجدول — فلا يفترق ترتيب العرض عن ترتيب التحرير."""
        self.assertEqual(
            [rule.key for rule in applicable(None, DisputeType.LABOUR, CaseStage.FIRST_INSTANCE)],
            list(SHIPPED.keys),
        )

    def test_an_invalid_query_date_raises_when_a_dated_rule_is_in_play(self):
        """
        تاريخ استعلام غير صالح يرفع استثناءً — ولا يُقارَن نصّاً بنصّ.

        ⚠️ **ولا يُنادى الفحص إلا على سجلّ فيه قاعدة مؤرَّخة:** قواعد الجدول
        المشحون بلا تاريخ، فلا يُقرأ تاريخ الاستعلام أصلاً — وهذا **قصرُ
        دائرة مقصود** في `Rule.applies_on`، لأن الجهل بالتاريخ يُقلّل ما
        يسري ولا يزيد. فمن نادى بسجلٍّ فحوصٍ كلها وتاريخٍ غير صالح لم يُخطئ:
        لم يكن في السجلّ ما يُقارَن بتاريخ.
        """
        dated = _substantive(key="leave.basis", in_force_from="2021-01-01")
        rule_set = RuleSet(rules=(_verification(), dated))
        with self.assertRaises(ValueError) as caught:
            applicable(rule_set, DisputeType.LABOUR, CaseStage.FIRST_INSTANCE, "يوم الثلاثاء")
        self.assertIn("تاريخ غير صالح", str(caught.exception))
        # وحراسة القصر: سجلّ الفحوص وحده لا يقرأ التاريخ، فلا يرفع.
        self.assertEqual(
            len(applicable(None, DisputeType.LABOUR, CaseStage.FIRST_INSTANCE, "يوم الثلاثاء")),
            len(VERIFICATION_RULES),
        )


class TestLookupRefuses(unittest.TestCase):
    """
    🔑 **`for_key` لا تُرجع افتراضياً أبداً — والمجهول ``None``.**

    وهذا هو الدرس المكتوب في `deadlines.convention_for` و
    `labour_rules.rule_for`: الردّ المخترع على مفتاح مجهول **يُنشئ قاعدة
    تُقرأ حيث لا تنطبق**، ولا يظهر الخطأ لأن الناتج كائن صالح. والفراغ يُرى،
    والردّ المخترع لا يُرى.
    """

    def test_for_key_never_returns_a_default(self):
        """
        🔑 **المفتاح المجهول يعطي ``None`` — لا أقرب مفتاح ولا أول قاعدة.**

        ⚠️ والمفاتيح المُجرَّبة **قريبة من مفاتيح حقيقية** عن قصد:
        ``calc.basis`` قريب من ``calc.basis_and_inputs``، و``cite`` بادئة
        ``cite.traceable``. فلو أُضيفت «مطابقة قريبة» يوماً لمرّ هذا الاختبار
        فاشلاً — وهو المقصود.
        """
        for unknown in (
            "لا-وجود-له",
            "calc.basis",
            "cite",
            "CITE.TRACEABLE",
            "cite.traceable ",
            "",
        ):
            with self.subTest(key=unknown):
                self.assertIsNone(for_key(SHIPPED, unknown))

    def test_for_key_returns_the_rule_when_it_exists(self):
        """والمفتاح الموجود يُرجع قاعدته بعينها — لا نسخةً ولا ملخّصاً."""
        rule = for_key(SHIPPED, "calc.basis_and_inputs")
        self.assertIsNotNone(rule)
        self.assertEqual(rule.key, "calc.basis_and_inputs")
        self.assertIs(rule, applicable(None, DisputeType.CIVIL, CaseStage.APPEAL)[3])

    def test_an_empty_rule_set_answers_nothing(self):
        """وسجلّ فارغ: لا قاعدة بمفتاح، ولا قاعدة سارية — والفراغ ليس خطأً."""
        empty = RuleSet()
        self.assertIsNone(for_key(empty, "cite.traceable"))
        self.assertEqual(applicable(empty, DisputeType.CIVIL, CaseStage.APPEAL), ())
        self.assertEqual(conflicts(empty), ())
        self.assertEqual(must_review(empty), ())


class TestConflicts(unittest.TestCase):
    """
    التعارض: **يُبلَّغ ولا يُحلّ** — والحكم بين قاعدتين للمحامي لا للكود.

    ⚠️ والشروط الثلاثة (العائلة، والموضوع، والنطاق المُصرَّح) هي التي تمنع
    الإنذار الكاذب: «الاقتباس يُتبَّع» و«الواقعة تحمل مصدرها» قاعدتان
    مختلفتان ولا تتعارضان، ولو قيل إنهما تتعارضان لامتلأ التقرير بما ليس فيه.
    """

    def test_conflicts_finds_a_genuine_overlap(self):
        """
        🔑 **تعارض حقيقي: قاعدتان على الموضوع نفسه في النطاق نفسه، ونصّان
        مختلفان.**

        وهذا هو ما يُراد إظهاره للمحرّر: قاعدتان تحكمان الشيء نفسه بحكمين —
        فإحداهما زائدة أو خاطئة، والقرار للمحامي. والنطاق **مُصرَّح به** في
        القاعدتين، لأن التعارض لا يُدّعى على عمومٍ لم يُصرَّح به.
        """
        first = Rule(
            key="leave.basis",
            family=RuleFamily.VERIFICATION,
            subject="leave",
            applies_to=(DisputeType.LABOUR,),
            stages=(CaseStage.FIRST_INSTANCE,),
            statement="الأساس هو الأجر الأساسي.",
        )
        second = Rule(
            key="leave.basis_gross",
            family=RuleFamily.VERIFICATION,
            subject="leave",
            applies_to=(DisputeType.LABOUR,),
            stages=(CaseStage.FIRST_INSTANCE,),
            statement="الأساس هو الأجر الشامل.",
        )
        both = RuleSet(rules=(first, second))
        self.assertEqual(conflicts(both), (("leave.basis", "leave.basis_gross"),))

    def test_a_shared_declared_stage_is_enough_for_an_overlap(self):
        """
        ⚠️ **وتصريحٌ ببُعد واحد يكفي:** قاعدتان تشتركان في المرحلة ولم
        تُصرّحا بنوع نزاع **تتقاطعان** — لأن كلًّا منهما تسري على كل نوع لم
        تصرّح به. وهذا هو معنى الفراغ في `applicable` نفسه.

        ولو اشتُرط التصريح بالنوع والمرحلة معاً لسقط تعارضٌ حقيقي من التقرير،
        وهو **إنذار ناقص** — وأخطر من الإنذار الزائد لأن الزائد يُرى.
        """
        first = Rule(
            key="calc.basis",
            family=RuleFamily.VERIFICATION,
            subject="calculation",
            stages=(CaseStage.FIRST_INSTANCE,),
            statement="الاحتساب على الأجر الأساسي.",
        )
        second = Rule(
            key="leave.basis",
            family=RuleFamily.VERIFICATION,
            subject="calculation",
            stages=(CaseStage.FIRST_INSTANCE,),
            statement="الاحتساب على الأجر الشامل.",
        )
        self.assertEqual(conflicts(RuleSet(rules=(first, second))), (("calc.basis", "leave.basis"),))

    def test_conflicts_does_not_invent_one_from_rules_of_different_families(self):
        """
        🔑 **قاعدة فحص وقاعدة موضوعية لا تتعارضان — ولو اختلف نصّهما.**

        لأن إحداهما **تُفحص** والأخرى **تُطبَّق**، فهما في بابين. ولو قِيس
        التعارض بالنصّ وحده لصار كل سطرين متعارضين، **وأداةٌ تُنذر دائماً لا
        تُنذر أبداً**.
        """
        verification = _verification(
            key="leave.check", statement="يُتحقّق من الأساس.", subject="leave"
        )
        substantive = _substantive(
            key="leave.basis", statement="الأساس هو الأجر الأساسي.", subject="leave"
        )
        both = RuleSet(rules=(verification, substantive))
        self.assertEqual(conflicts(both), ())

    def test_conflicts_does_not_invent_one_from_different_subjects(self):
        """
        ⚠️ **ولا تعارض بين موضوعين مختلفين** — ولو تساوى النطاق.

        فالقاعدتان العامّتان اللتان لم تُصرّحا بنطاق **لا يُبنى تعارضهما على
        عمومهما**: «الاقتباس يُتبَّع» و«الواقعة تحمل مصدرها» جمعهما أنهما في
        الجدول نفسه، لا أنهما تتنازعان. وهذا الشرط هو الذي يجعل الجدول
        المشحون **بلا تعارضات** — وقد فُحص كذلك أدناه.
        """
        first = _verification(key="citation.traceable", statement="يُتبَّع.", subject="citation")
        second = _verification(key="fact.source", statement="يُسجَّل.", subject="fact")
        self.assertEqual(conflicts(RuleSet(rules=(first, second))), ())
        self.assertEqual(conflicts(SHIPPED), ())

    def test_identical_statements_are_not_a_conflict(self):
        """ونصّان متطابقان ليسا تعارضاً — فلا يُنذر على تكرار لا على خلاف."""
        first = _verification(key="leave.a", statement="نصّ واحد.", subject="leave")
        second = _verification(key="leave.b", statement="نصّ واحد.", subject="leave")
        self.assertEqual(conflicts(RuleSet(rules=(first, second))), ())

    def test_disjoint_scopes_are_not_a_conflict(self):
        """ونطاقان منفصلان ليسا تعارضاً — ولو اتّفق الموضوع والنصّ اختلف."""
        first = Rule(
            key="leave.a",
            family=RuleFamily.VERIFICATION,
            subject="leave",
            applies_to=(DisputeType.LABOUR,),
            statement="حكم أول.",
        )
        second = Rule(
            key="leave.b",
            family=RuleFamily.VERIFICATION,
            subject="leave",
            applies_to=(DisputeType.LEASE,),
            statement="حكم آخر.",
        )
        self.assertEqual(conflicts(RuleSet(rules=(first, second))), ())

    def test_the_conflict_output_is_ordered_and_deduplicated(self):
        """
        والناتج **مرتَّب بالمفاتيح وبلا تكرار** — فالفحص يقارن نصّاً لا ترتيباً.

        ⚠️ والترتيب ليس تفصيلاً: لو كان الناتج بحسب ترتيب الجدول لتبدّل
        بمجرد نقل سطر، ولصار كل فحص له لونٌ مختلف. والمرتَّب يُقارَن.
        """
        a = Rule(
            key="leave.a",
            family=RuleFamily.VERIFICATION,
            subject="leave",
            stages=(CaseStage.APPEAL,),
            statement="نصّ أ.",
        )
        b = Rule(
            key="leave.b",
            family=RuleFamily.VERIFICATION,
            subject="leave",
            stages=(CaseStage.APPEAL,),
            statement="نصّ ب.",
        )
        c = Rule(
            key="leave.c",
            family=RuleFamily.VERIFICATION,
            subject="leave",
            stages=(CaseStage.APPEAL,),
            statement="نصّ ج.",
        )
        self.assertEqual(
            conflicts(RuleSet(rules=(c, b, a))),
            (("leave.a", "leave.b"), ("leave.a", "leave.c"), ("leave.b", "leave.c")),
        )


class TestMustReview(unittest.TestCase):
    """
    المراجعة: **موضوعي بلا مصدر، أو قاعدة حلّ محلّها غيرُها.**

    ⚠️ وموضع الدلالة على «انتهت النافذة» هو ``supersedes`` لا تاريخ انتهاء
    مكتوب: التاريخ الذي نثق به هو **تاريخ نفاذ اللاحق**، لا تاريخ موت
    السابق الذي لا نعرفه.
    """

    def test_must_review_lists_a_substantive_rule_with_no_source(self):
        """
        🔑 **حكم موضوعي بلا مصدر: يُدرَج في المراجعة — ولا يمرّ صامتاً.**

        لأنه لا يستطيع المحامي أن يتحقّق منه، فيصير **رأياً يتنكّر في هيئة
        مرجع**. والعائلة الموضوعية هي التي توجب المصدر.
        """
        unsourced = Rule(
            key="leave.basis",
            family=RuleFamily.SUBSTANTIVE,
            subject="leave",
            statement="الأساس هو الأجر الأساسي.",
            in_force_from="2021-01-01",
        )
        review = must_review(RuleSet(rules=(unsourced,)))
        self.assertEqual([rule.key for rule in review], ["leave.basis"])
        payload = summarize(RuleSet(rules=(unsourced,)))
        self.assertEqual(payload["review_count"], 1)
        self.assertEqual(payload["review"][0]["reason"], "بلا مصدر")

    def test_must_review_lists_a_superseded_rule(self):
        """
        🔑 **والقاعدة التي حلّ محلها غيرُها تُدرَج — وهذا أصل عيب الثمانية
        والعشرين في المئة:** قاعدة ملغاة تُقرأ سارية لأن لا شيء وسمها.
        """
        old = _substantive(
            key="leave.old",
            statement="الأساس خمسة عشر يوماً.",
            in_force_from="2010-01-01",
            supersedes=("leave.basis",),
        )
        new = _substantive(
            key="leave.basis",
            statement="الأساس واحد وعشرون يوماً.",
            in_force_from="2021-01-01",
        )
        rule_set = RuleSet(rules=(old, new))
        self.assertEqual([rule.key for rule in must_review(rule_set, "2026-01-01")], ["leave.old"])
        # وقبل نفاذ اللاحق لم تنته نافذة السابق: لا مراجعة.
        self.assertEqual(must_review(rule_set, "2015-01-01"), ())

    def test_a_sound_rule_is_not_listed(self):
        """وما كان بمصدره وغيرَ منسوخ **لا يُدرَج** — فالقائمة ليست كل الجدول."""
        sound = _substantive(key="leave.basis", supersedes=())
        self.assertEqual(must_review(RuleSet(rules=(sound,)), "2026-01-01"), ())

    def test_the_shipped_table_needs_no_review(self):
        """والجدول المشحون كله فحوص — فلا يحتاج مراجعة قبل الاعتماد."""
        self.assertEqual(must_review(SHIPPED), ())
        self.assertEqual(summarize()["review_count"], 0)


class TestSummarize(unittest.TestCase):
    """
    الحصيلة: **JSON-safe**، والأخطاء مفصولة عن الملاحظات.

    ⚠️ والفصل حكمٌ على الأثر لا ترتيبٌ في العرض: الحكم بلا مصدر **عيب في
    البيانات** لا يصلحه القارئ، والتعارض **موضع نظر** لا يُبطل السجلّ.
    """

    def test_the_summary_is_json_safe(self):
        """البثّ يجب أن ينجح — فلا ``Enum`` ولا كائن في القاموس."""
        payload = summarize(SHIPPED)
        json.dumps(payload, ensure_ascii=False)
        self.assertEqual(payload["rule_count"], len(VERIFICATION_RULES))
        self.assertEqual(
            payload["family_counts"],
            {"verification": len(VERIFICATION_RULES), "substantive": 0},
        )
        self.assertEqual(payload["conflicts"], [])
        self.assertEqual(payload["errors"], [])
        self.assertTrue(payload["clean"])

    def test_a_dated_verification_rule_is_an_error_in_the_summary(self):
        """
        ⚠️ **وقاعدة الفحص المؤرَّخة خطأ — لا ملاحظة.**

        والحصيلة تُفحص **بعد البناء** أيضاً، لا في البناء وحده: فالسجلّ قد
        يُبنى من قواعد جُمِعت من مسارات مختلفة، وقد تُبنى القاعدة بتجاوز
        الحقل. فالفحص في الموضعين ليس تكراراً: أحدهما يمنع الإنشاء، والآخر
        يمنع الاعتماد.
        """
        smuggled = Rule.__new__(Rule)
        object.__setattr__(smuggled, "key", "check.dated")
        object.__setattr__(smuggled, "family", RuleFamily.VERIFICATION)
        object.__setattr__(smuggled, "subject", "check")
        object.__setattr__(smuggled, "applies_to", ())
        object.__setattr__(smuggled, "stages", ())
        object.__setattr__(smuggled, "statement", "فحص بتاريخ.")
        object.__setattr__(smuggled, "source", "موضع الفحص")
        object.__setattr__(smuggled, "in_force_from", "2024-01-01")
        object.__setattr__(smuggled, "supersedes", ())
        object.__setattr__(smuggled, "note", "")

        payload = summarize(RuleSet(rules=(smuggled,)))
        self.assertFalse(payload["clean"])
        self.assertEqual(payload["errors"][0]["code"], "verification_rule_dated")
        self.assertIn("تاريخ نفاذ", payload["errors"][0]["detail"])

    def test_the_distinction_findings_are_notices_not_errors(self):
        """وملاحظات الصياغة **ملاحظات** — لا تُبطل السجلّ ولا تمنع الاعتماد."""
        findings = check_distinctions("المادة ٥ من القانون قاعدة ثابتة لا تتغير.")
        payload = summarize(SHIPPED, findings)
        self.assertEqual(payload["errors"], [])
        self.assertTrue(payload["clean"])
        self.assertEqual(payload["findings"], [DistinctionKind.VERIFICATION_VS_SUBSTANTIVE.value])
        self.assertEqual(payload["notices"][0]["code"], "distinction")

    def test_an_empty_rule_set_is_clean_and_says_so_in_arabic(self):
        """
        🔑 **سجلّ فارغ: سليم — ويقول ذلك بالعربية.**

        ⚠️ ولماذا يُشترط القول؟ لأن **الفراغ غير المفسَّر يُقرأ عطباً**: تقريرٌ
        بلا نصّ يجعل القارئ يظنّ أنّ الأداة لم تعمل، فيُهمَل التقرير كله —
        وهو الدرس نفسه الذي دُفع ثمنه في المطابقة الصامتة في `case_file.py`.
        """
        payload = summarize(RuleSet())
        self.assertTrue(payload["clean"])
        self.assertEqual(payload["rule_count"], 0)
        self.assertEqual(payload["family_counts"], {"verification": 0, "substantive": 0})
        self.assertEqual(payload["summary"], clean_message())
        self.assertIn("السجلّ سليم", payload["summary"])
        # وحراسة نفسها: الرسالة عربية، لا إنجليزية.
        self.assertRegex(clean_message(), r"[\u0600-\u06FF]")
        self.assertNotIn("clean", payload["summary"])

    def test_the_summary_carries_every_rule_with_its_source_and_date(self):
        """وتفصيل كل قاعدة يظهر: مصدرها وتاريخها ونطاقها — فيُراجَع لا يُسلَّم."""
        payload = summarize(SHIPPED)
        self.assertEqual([item["key"] for item in payload["rules"]], list(SHIPPED.keys))
        for item in payload["rules"]:
            with self.subTest(key=item["key"]):
                self.assertTrue(item["source"])
                self.assertEqual(item["in_force_from"], "")
                self.assertEqual(item["family"], RuleFamily.VERIFICATION.value)
                self.assertTrue(item["statement"])


class TestDeterminism(unittest.TestCase):
    """
    ⚠️ **المدخل نفسه يُعطي المخرج نفسه، دائماً.**

    وهذا هو الضمان الذي كان مفقوداً في احتساب المكافأة: مذكرة واحدة حملت
    رقمين لمدّة واحدة. ودالّة نقية لا تستطيع أن تفعل ذلك — والاختبار يثبّت
    الضمان لا الدالّة.
    """

    def test_the_same_inputs_always_give_the_same_outcome(self):
        """
        🔑 خمس نداءات، وحصيلة واحدة — نصّاً ونصّاً.

        والفحص على **الحصيلة كاملة** لا على عدد: العدد قد يتّفق والترتيب
        يختلف، والترتيب جزء من المخرج.
        """
        text = "المادة ٥ من القانون قاعدة ثابتة لا تتغير، وآخر يوم عمل هو تاريخ انتهاء العقد."
        first = json.dumps(summarize(SHIPPED, check_distinctions(text)), ensure_ascii=False, sort_keys=True)
        for _ in range(5):
            self.assertEqual(
                json.dumps(summarize(SHIPPED, check_distinctions(text)), ensure_ascii=False, sort_keys=True),
                first,
            )
        self.assertEqual(len({tuple(item.kind for item in check_distinctions(text)) for _ in range(5)}), 1)

    def test_the_registry_has_no_hidden_state(self):
        """
        ولا حالة مخفيّة: السجلّ نفسه **لا يتبدّل** بالنداء عليه.

        ⚠️ وهذا هو الفرق بين بيانات ودالّة تحفظ «آخر ما رُئي»: الثانية
        تُخالف نفسها بين تشغيل وتشغيل، وهو أسوأ ما يقع في مستند قانوني.
        """
        before = SHIPPED.keys
        for _ in range(3):
            applicable(None, DisputeType.LABOUR, CaseStage.APPEAL, "2026-01-01")
            conflicts(SHIPPED)
            must_review(SHIPPED)
            summarize(SHIPPED)
        self.assertEqual(SHIPPED.keys, before)
        self.assertEqual(len(SHIPPED.rules), len(VERIFICATION_RULES))

    def test_the_reused_types_are_the_case_file_ones(self):
        """
        🔑 **ولا نسخة ثانية من تصنيفات `case_file`.**

        ونسخة ثانية **تنحرف عن الأصل بصمت** عند أوّل إضافة قيمة: تُضاف
        المرحلة الجديدة إلى `case_file`، وتبقى النسخة لا تعرفها، فيُرشَّح
        النطاق على تصنيف ناقص ولا يظهر النقص في أي تقرير.
        """
        self.assertIs(rules.DisputeType, case_file.DisputeType)
        self.assertIs(rules.CaseStage, case_file.CaseStage)
        self.assertEqual(
            {member.value for member in DisputeType},
            {member.value for member in case_file.DisputeType},
        )
        for member in CaseStage:
            with self.subTest(stage=member.value):
                self.assertIn(member, list(CaseStage))

    def test_the_module_states_why_it_exists(self):
        """
        ⚠️ **وسبب وجود الملف مكتوب فيه** — الثمانية والعشرون في المئة.

        لأن من يقرأ السجلّ يجب أن يعرف ما الذي يمنعه، وإلا حذف الحرس «تبسيطاً»
        وأعاد العيب. والحرس بلا سببه يُحذف عند أوّل ضيق.
        """
        source = _module_source()
        self.assertIn("ثمانية وعشرين", source)
        self.assertIn("حكمٌ متغيّر وُضع في طبقة ثابتة", source)
        self.assertIn("لا يُراجَع", source)


if __name__ == "__main__":
    unittest.main()
