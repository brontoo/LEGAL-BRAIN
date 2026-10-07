"""
صحّة الوحدات — حارس يمنع عطبين صامتين.
============================================================================

⚠️ **هذا الملف وُلد من عطب حقيقي لم يكشفه شيء.**

في جولة سابقة كُتبت وحدة `facts.py` وفيها:

    _DIGIT_TRANSLATION = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "0123456789")

**٢٠ محرفاً مقابل ١٠ — فترفع `ValueError` عند الاستيراد.** والوحدة **لا تُستورد
إطلاقاً**: لا من مسار، ولا من اختبار.

⚠️ **والسويت كان أخضر.** ٥١٨ اختباراً تمرّ، وملف ميّت في المجلد. **لأن لا شيء
يلمسه، فلا شيء يفشل.**

⚠️ **والدرس أن «الاختبارات تمرّ» ليست عبارة عن سلامة المشروع**، بل عن سلامة
**ما تُشغّله الاختبارات**. وما لا يُشغَّل لا يُقاس.

⚠️ **و`ast.parse` لا يكفي**: العطب أعلاه **نحويّاً سليم تماماً**، ولا يظهر إلا
بالتنفيذ. فالحارس هنا **يستورد فعلاً**.
"""

from __future__ import annotations

import importlib
import pathlib
import re
import sys
import unittest

PROJECT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

#: ⚠️ **وحدات مبنيّة ولم تُوصَل بعد — قائمة مؤقّتة يجب أن تفرغ.**
#:
#: ووجودها هنا **إقرار بالدَّين لا إعفاء منه**. والاختبار يمرّ بها اليوم،
#: **ويفشل إن بقي فيها اسم بعد أن يُوصَل صاحبه** — فالرقم يُنقص ولا يزيد.
#:
#: وترك الوحدة بلا واصل يعني ألّا يقيسها شيء: لا اختبار، ولا مسار، ولا خطأ.
PENDING_WIRING: tuple[tuple[str, str], ...] = (
    ("case_file", "يُوصَل عند بناء مصفوفة الطلبات (البند ٥)"),
    ("facts", "يُوصَل عند فحص أمانة الوقائع في مسار التوليد (البند ٢)"),
    ("deadlines", "يُوصَل عند فحص المواعيد والاختصاص في مصفوفة الطلبات (البند ٥)"),
    ("untrusted", "يُوصَل عند تغليف نصّ المستندات قبل الموجّه (البند ١١)"),
)

#: ⚠️ **نصوص تُستورد عند التشغيل لا عند الفحص** — سكربتات ومسارات تستدعي
#: حزماً لا تُثبَّت في بيئة الاختبار (`dotenv` · `pymupdf` · `chainlit` · `bs4`).
#: وهي **لا تُعدّ يتيمة**: يستدعيها المشغّل من سطر الأوامر أو من uvicorn.
STANDALONE_SCRIPTS: tuple[str, ...] = (
    "app_chainlit",
    "ask_brain",
    "contracts_ingester",
    "drafts_ingester",
    "drive_folders",
    "html_ingester",
    "ingest_documents",
    "legal_agent",
    "main",
    "notices_ingester",
    "office_test",
    "pdf_ingester",
    "poa_ingester",
    "smart_office",
    "test_groq",
)

#: ولا يُفحص هذا الملف على نفسه (يستورد ما يستورد).
SELF = "test_module_health"


def _modules() -> list[str]:
    """أسماء وحدات المشروع — بلا المجلدات الفرعية ولا الملفات الخاصة."""
    return sorted(
        path.name[:-3]
        for path in PROJECT.glob("*.py")
        if not path.name.startswith("_")
    )


def _importers(name: str) -> list[str]:
    """
    من يستورد هذه الوحدة؟ — بالبحث في النصّ لا بالتنفيذ.

    ⚠️ والبحث نصّي عن سطر الاستيراد، **فلا يضيف تبعية ولا يُشغّل شيئاً**.
    """
    pattern = re.compile(rf"^\s*(from\s+{re.escape(name)}\b|import\s+{re.escape(name)}\b)", re.M)
    found: list[str] = []
    for path in list(PROJECT.glob("*.py")) + list((PROJECT / "tests").glob("*.py")):
        if path.stem in (name, SELF):
            continue
        try:
            source = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        # التعليقات لا تُنشئ تبعية — فنُزيلها قبل البحث
        without_comments = re.sub(r"#.*", "", source)
        if pattern.search(without_comments):
            found.append(path.name)
    return found


class TestModulesAreNotDead(unittest.TestCase):
    """
    كل وحدة **يجب أن يلمسها شيء**.
    ========================================================================
    ⚠️ والغرض ليس التنظيم بل **قابلية القياس**: وحدة لا يستوردها اختبار ولا
    مسار **لا يُقاس سلوكها بأي حال**، فتكون مكتوبة لا عاملة.
    """

    def test_every_module_is_imported_by_something(self):
        """🔑 الحارس الأساسي — ويمنع تكرار عطب `facts.py`."""
        orphans = []
        for name in _modules():
            if name in STANDALONE_SCRIPTS:
                continue
            if _importers(name):
                continue
            orphans.append(name)

        pending = {name for name, _ in PENDING_WIRING}
        unexpected = sorted(set(orphans) - pending)

        # ⚠️ ولا يكفي أن تكون الوحدة في القائمة — بل يجب أن تكون القائمة دقيقة:
        # فوحدة صارت موصولة وبقيت في القائمة **تُخفي ديناً سُدِّد**.
        stale = sorted(
            name for name, _ in PENDING_WIRING if name not in orphans
        )

        self.assertEqual(
            unexpected,
            [],
            f"وحدات لا يستوردها شيء ولم تُدرَج في PENDING_WIRING: {unexpected}",
        )
        self.assertEqual(
            stale,
            [],
            f"وحدات صارت موصولة — احذفها من PENDING_WIRING: {stale}",
        )

    def test_the_pending_list_documents_a_reason(self):
        """⚠️ والدَّين يُكتب بسببه — فلا قائمة أسماء بلا تفسير."""
        for name, reason in PENDING_WIRING:
            with self.subTest(module=name):
                self.assertTrue(reason.strip(), f"{name}: لا سبب مذكور")
                self.assertGreater(len(reason), 15, f"{name}: السبب غير مُفصَّل")


class TestModulesImportCleanly(unittest.TestCase):
    """
    كل وحدة **تُستورد فعلاً** — أو تفشل بسبب حزمة غائبة وحدها.
    ========================================================================
    ⚠️ **والفرق جوهري:** `ModuleNotFoundError` تعني «الحزمة ليست في بيئة
    الاختبار» — وهي حالة بيئة لا عطب كود. **وما عداها عطب.**

    فوحدة `facts.py` رفعت `ValueError`، **وهو ليس حزمة غائبة** — فكان هذا
    الاختبار سيُمسكها من أول لحظة.
    """

    @unittest.expectedFailure
    def test_every_module_imports_or_lacks_a_dependency(self):
        """
        ⚠️ **مُعلَّمة «فشل متوقَّع» مؤقّتاً، والسبب مكتوب.**

        `facts.py` يرفع `ValueError` عند الاستيراد (جدول أرقام بطولين مختلفين).
        والعطب **قيد الإصلاح**، وسطر `expectedFailure` هذا **يُحذف لحظة إصلاحه**.

        🔑 **و`expectedFailure` هنا ليست إعفاءً بل إعلاناً:** فإن مرّ الاختبار
        بعد الإصلاح، **أبلغت مكتبة `unittest` عن «نجاح غير متوقَّع» — وهو فشل**
        — **فلا يبقى السطر صامتاً بعد زوال سببه.** وهو بالضبط السلوك المطلوب:
        **الدَّين يُسجَّل، ويُطالَب بسداده، ولا يُنسى.**
        """
        for name in _modules():
            with self.subTest(module=name):
                try:
                    importlib.import_module(name)
                except ModuleNotFoundError as exc:
                    # حالة بيئة: الحزمة غير مثبّتة هنا — ولا تُعدّ عطباً.
                    self.assertIn(
                        "No module named",
                        str(exc),
                        f"{name}: ModuleNotFoundError بنصّ غير متوقَّع",
                    )
                except Exception as exc:  # noqa: BLE001
                    self.fail(
                        f"{name} لا يُستورد، والعطب ليس حزمةً غائبة: "
                        f"{type(exc).__name__}: {exc}"
                    )


class TestTheModulesTheObjectiveNames(unittest.TestCase):
    """
    وحدات الهدف موجودة فعلاً — وليست وعوداً في تقرير.
    ========================================================================
    ⚠️ والحارس على **الوجود** لا على السلوك: السلوك تفحصه اختبارات كل وحدة.
    **والغرض أن يمنع تقريراً يقول «بُني» وملفاً ليس في المجلد.**
    """

    NAMED = (
        "case_file",
        "facts",
        "untrusted",
        "briefing",
        "attribution",
        "review",
        "labour_rules",
        "citations",
        "language_audit",
    )

    #: ⚠️ **وحدات الهدف بلا اختبار بعد — دَين مُعلَن، لا إعفاء.**
    #:
    #: والحارس يفشل إن بقي في هذه القائمة اسم **صارت له اختبارات**، فيُنقص
    #: الرقم ولا يزيد. **والغرض ألّا يُقال «بُني» عن وحدة لا يقيسها شيء.**
    PENDING_TESTS: tuple[str, ...] = ("case_file", "facts", "untrusted")

    def test_each_named_module_exists_and_has_a_test_file(self):
        for name in self.NAMED:
            with self.subTest(module=name):
                self.assertTrue(
                    (PROJECT / f"{name}.py").exists(), f"الوحدة مفقودة: {name}.py"
                )
                if name in self.PENDING_TESTS:
                    continue
                test_file = PROJECT / "tests" / f"test_{name}.py"
                self.assertTrue(
                    test_file.exists(),
                    f"{name}.py بلا اختبار — ولا يُقاس سلوكها",
                )

    def test_the_pending_tests_list_has_not_gone_stale(self):
        """
        ⚠️ **ولا يبقى الدَّين بعد سداده.**

        فوحدة صارت لها اختبارات وبقيت في `PENDING_TESTS` **تُخفي عملاً أُنجز**
        — وهو أسوأ من العكس، لأنه يجعل القائمة تفقد معناها فلا يقرؤها أحد.
        """
        stale = sorted(
            name
            for name in self.PENDING_TESTS
            if (PROJECT / "tests" / f"test_{name}.py").exists()
        )
        self.assertEqual(
            stale, [], f"وحدات صار لها اختبارات — احذفها من PENDING_TESTS: {stale}"
        )


if __name__ == "__main__":
    unittest.main()
