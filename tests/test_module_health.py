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

import doctest
import importlib
import pathlib
import re
import subprocess
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
#: **وقد فُرِّغت: `case_file` و`facts` التُزِما، وصار لكلٍّ اختبار مُلتزَم يستورده.**
PENDING_WIRING: tuple[tuple[str, str], ...] = ()

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


#: ⚠️ **تخزين مؤقّت لعملية `git` — لأن نداءها لكل ملف كلّف ٢٥ ثانية.**
#:
#: و`_importers` تُنادى لكل وحدة، **وكانت تسأل git عن المُعدَّل في كل مرّة**،
#: فصار التشغيل ٢٥ ثانية بدل ثانية. **والنتيجة لا تتغيّر داخل التشغيل الواحد**
#: — فتكرار السؤال إسراف محض، وهو نفسه الصنف الذي نُحاسب الكود عليه.
_GIT_CACHE: dict[str, object] = {}


def _cached(key: str, fn):
    """يُنادي `fn` **مرّة واحدة في عمر العملية**."""
    if key not in _GIT_CACHE:
        _GIT_CACHE[key] = fn()
    return _GIT_CACHE[key]


def _tracked_uncached() -> set[str] | None:
    """
    الملفات المُلتزَم بها في git — أو ``None`` إن تعذّر السؤال.

    ⚠️ **وهذا الإصلاح جاء من عطب في الحارس نفسه، لا في الكود المفحوص.**

    كان الحارس يقرأ **نظام الملفات**، فيرى ملفات تُكتَب الآن ولم تُلتزَم بعد.
    **فيفشل في شجرة العمل مع أن الشجرة المُلتزَم بها سليمة** — لأن الملفات
    الناقصة ليست فيها.

    ⚠️ **والنتيجة أن حارساً لا يستطيع أن يشهد على التزام يُربك قارئ فشله:**
    أهو عطب في المشروع أم عمل جارٍ؟ **وهما سؤالان مختلفان تماماً.**

    ⚠️ **والفرق جوهري في هذا المشروع بعينه:** الوكلاء يكتبون ملفات كبيرة على
    مدى جولات، **فشجرة العمل حمراء بحقّ معظم الوقت** — والحارس الذي لا يفرّق
    بين «عمل لم يكتمل» و«عمل أُلتزم وهو معطوب» **حارسٌ يُهمَل**.

    و`git ls-files` هو الفاصل: **ما لم يُلتزَم لم يصل إلى أحد بعد.**
    """
    try:
        result = subprocess.run(
            ["git", "ls-files"],
            cwd=PROJECT,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return {line.strip() for line in result.stdout.splitlines() if line.strip()}


def _dirty_uncached() -> set[str]:
    """
    الملفات المُلتزَم بها **والمُعدَّلة الآن** في شجرة العمل — أو مجموعة فارغة.

    ⚠️ **وهذا إصلاح النصف الثاني من عطب، لا النصف الأول.**

    صار الحارس يسأل git **أيّ ملفات تُفحَص** ✅ — لكنه كان يقرأ **محتواها**
    من شجرة العمل. **فملفٌ مُلتزَم يُعدَّل الآن ويصير معطوباً لحظياً يُفشل
    الحارس** — مع أن المُلتزَم به سليم.

    ⚠️ **والنتيجة أن «فشل الحارس» صار له معنيان**، ولا يستطيع قارئه أن يفرّق:
    أهو عطب في الالتزام، أم وكيل يكتب الآن؟ **وهما سؤالان متعاكسان.**

    ⚠️ **والحلّ الكامل أن يُقرأ المحتوى من `git show HEAD:path`** — لكن
    `TestModulesImportCleanly` **يستورد الوحدة فعلاً**، والاستيراد يحتاج ملفاً
    على القرص. فالكامل يحتاج `git worktree` مؤقّتاً — **وهو أثقل من أن يحتمله
    كل تشغيل.**

    **فالحدّ يُعلَن بدل أن يُخفى:** الملف المُعدَّل **يُستثنى ويُعدّ**،
    **ومرور الحارس معناه أن المُلتزَم به سليم.**
    """
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=PROJECT,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return set()
    if result.returncode != 0:
        return set()
    changed: set[str] = set()
    for line in result.stdout.splitlines():
        if len(line) < 4:
            continue
        path = line[3:].strip()
        # «R  old -> new» — نأخذ الاسم الجديد
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        changed.add(path.strip().strip('"'))
    return changed


def _modules() -> list[str]:
    """
    أسماء وحدات المشروع — **المُلتزَم بها وحدها** إن أمكن السؤال.

    ⚠️ وملف نصف مكتوب لا يُفحَص: **لا يُقال عنه إنه معطوب، ولا إنه سليم.**
    """
    tracked = _tracked()
    dirty = _dirty()
    return sorted(
        path.name[:-3]
        for path in PROJECT.glob("*.py")
        if not path.name.startswith("_")
        and (tracked is None or path.name in tracked)
        # ⚠️ والمُعدَّل يُستثنى: محتواه لم يُلتزَم بعد، فلا يُشهَد عليه.
        and path.name not in dirty
    )


def _importers(name: str) -> list[str]:
    """
    من يستورد هذه الوحدة؟ — بالبحث في النصّ لا بالتنفيذ.

    ⚠️ والبحث نصّي عن سطر الاستيراد، **فلا يضيف تبعية ولا يُشغّل شيئاً**.
    """
    tracked = _tracked()
    pattern = re.compile(rf"^\s*(from\s+{re.escape(name)}\b|import\s+{re.escape(name)}\b)", re.M)
    found: list[str] = []
    for path in list(PROJECT.glob("*.py")) + list((PROJECT / "tests").glob("*.py")):
        if path.stem in (name, SELF):
            continue
        # ⚠️ **والمُلتزَم به وحده**: فاختبار يُكتَب الآن **لا يُصلح وحدةً يتيمة**،
        # لأن ما لم يُلتزَم لم يصل إلى أحد.
        rel = path.relative_to(PROJECT).as_posix()
        # ⚠️ **ولا يُستثنى المُعدَّل هنا — وهذا إصلاح عطب تكرّر أربع مرات.**
        #
        # كان هنا سطر يُسقط الملف المُعدَّل. وهو صواب لفحص **المحتوى**،
        # **وخاطئ لفحص الوجود**: فوجودُ واصل **لا يعتمد على محتواه**. فإذا
        # كان الوحيد الذي يستورد وحدةً مُعدَّلاً لحظياً، حسبها الحارس
        # **يتيمة** وأفشل — بلا عطب. وقد وقع ذلك مع `quotation` ثم
        # مع `authority`.
        if tracked is not None and rel not in tracked:
            continue
        # ⚠️ ومُعدَّل الآن؟ **فاستيراده لم يُلتزَم بعد** — ولا يُشهَد به.
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
        # فوحدة صارت موصولة وبقيت في القائمة **تُخفي دَيناً سُدِّد**.
        #
        # ⚠️ **وشرط `name in seen` ليس زيادة — بل هو إصلاح عطب وقع.**
        #
        # كان الشرط `name not in orphans` وحده. و`orphans` تُبنى من `_modules()`
        # **وهي المُلتزَم به وحده**. فوحدة **لم تُلتزَم بعد** تخرج من `orphans`
        # — **لا لأنها موصولة، بل لأنها ليست في الالتزام أصلاً** — **فيُوصف
        # دَينها بأنه سُدِّد وهو قائم.** وهذا خلطٌ بين «غير موجود» و«موجود
        # وموصول»، **وهما نقيضان.**
        seen = set(_modules())
        stale = sorted(
            name
            for name, _ in PENDING_WIRING
            if name in seen and name not in orphans
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

    def test_every_module_imports_or_lacks_a_dependency(self):
        """
        كل وحدة تُستورد فعلاً — أو تفشل بسبب حزمة غائبة وحدها.

        ⚠️ **وكان هذا الاختبار مُعلَّماً «فشل متوقَّع» لأن `facts.py` رفع
        `ValueError`** — جدول أرقام بطولين مختلفين: عشرين محرفاً مقابل عشرة.
        **وقد أُصلح، فحُذف السطر.**

        🔑 **وكيف عُرف أن وقت الحذف جاء؟** لم يُعرف بالقراءة ولا بالتذكّر —
        **بل أبلغت `unittest` عن «نجاح غير متوقَّع» وعدّته فشلاً.** فالدَّين
        المُعلَن بـ`expectedFailure` **يُطالب بسداده من نفسه**، ولا يبقى بعد
        زوال سببه. **وهذا الفرق بين تسجيل عطبٍ وإخفائه.**
        """
        dirty = _dirty()
        skipped = []
        for name in _modules():
            with self.subTest(module=name):
                if f"{name}.py" in dirty:
                    skipped.append(name)
                    continue
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


class TestDoctestsPass(unittest.TestCase):
    """
    **أمثلة التوثيق تُشغَّل — لأنها توثيق يكذب إن لم تُشغَّل.**
    ========================================================================
    ⚠️ **ولد هذا الصنف من عطب حقيقي لم يكشفه شيء.**

    وحدة `claims.py` كُتبت وفيها **٢٢ مثالاً يستدعي دوالّ مساعدة غير موجودة**
    (``_the_matrix`` · ``_the_setoff_defence`` …). و`test_claims` **كان يمرّ:
    ٤٦ اختباراً `OK`** — **والسويت لا يرى العطب**، لأن `unittest` لا يُشغّل
    الأمثلة، **ولا أحد يُشغّل `doctest` تلقائياً.**

    ⚠️ **وهو نفس صنف عطب `maketrans` في `facts.py`:** شيء معطوب لا يُشغّله
    شيء، **فالسويت الأخضر لا يقول عنه شيئاً.**

    ⚠️ **وتوثيق يفشل أمثاله أسوأ من غياب التوثيق**: القارئ يثق به فلا يجرّب.

    ⚠️ **والفحص على المُلتزَم به وحده** — فوحدة نصف مكتوبة لا تُحاسَب على
    أمثلتها بعد.
    """

    #: ⚠️ **وحدات لا تُستورد في بيئة الاختبار** — تستدعي حزماً غير مثبّتة،
    #: أو تقرأ اعتمادات عند الاستيراد. **تُترك لأمر التشغيل.**
    NOT_IMPORTABLE: tuple[str, ...] = (
        "app_chainlit", "ask_brain", "contracts_ingester", "drafts_ingester",
        "drive_folders", "html_ingester", "ingest_documents", "legal_agent",
        "main", "notices_ingester", "office_test", "pdf_ingester",
        "poa_ingester", "smart_office", "test_groq",
    )

    def test_every_module_s_own_examples_run(self):
        """🔑 كل مثال في التوثيق يُنفَّذ فعلاً — لا يُقرأ."""
        failures: list[str] = []
        attempted_total = 0

        for name in _modules():
            if name in self.NOT_IMPORTABLE:
                continue
            try:
                module = importlib.import_module(name)
            except ModuleNotFoundError:
                continue
            except Exception:  # noqa: BLE001
                # عطب الاستيراد يُمسكه الصنف الآخر، فلا يُكرَّر هنا.
                continue

            # ⚠️ `testmod` يستعمل **فضاء أسماء الوحدة** — وتمرير `globs={}`
            # يُجرّد الأمثلة من أسمائها **فيُفشلها كلها زوراً.** وقد وقع ذلك
            # في تشخيص هذا العطب: **أنذرتُ عن أربع عشرة وحدة سليمة.**
            result = doctest.testmod(module, verbose=False, report=False)
            attempted_total += result.attempted
            if result.failed:
                failures.append(f"{name}: {result.failed} من {result.attempted}")

        self.assertGreater(
            attempted_total, 0, "لا أمثلة شُغّلت — الفحص لم يجرِ فعلاً"
        )
        self.assertEqual(
            failures,
            [],
            f"أمثلة توثيق تفشل (مُلتزَم بها): {failures}",
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
        "deadlines",
        "attribution",
        "review",
        "labour_rules",
        "citations",
        "language_audit",
        # ⚠️ **ووحدات الهدف الثلاث الباقية — تُدرَج الآن لتُشهَد متى التُزمت.**
        # والحارس يتجاوز غير المُلتزَم به، فإدراجها لا يُفشله اليوم؛
        # **ومتى التُزمت، صار اختبارها وأمثلتها شرطاً.**
        "authority",
        "claims",
        "rules",
        "revision_loop",
        "quotation",
        "revisions",
    )

    #: ⚠️ **وحدات الهدف بلا اختبار بعد — دَين مُعلَن، لا إعفاء.**
    #:
    #: والحارس يفشل إن بقي في هذه القائمة اسم **صارت له اختبارات**، فيُنقص
    #: الرقم ولا يزيد. **والغرض ألّا يُقال «بُني» عن وحدة لا يقيسها شيء.**
    PENDING_TESTS: tuple[str, ...] = ()

    #: ⚠️ **وحدات يسمّيها الهدف ولم تُلتزَم بها بعد — الدَّين الأكبر، مُعلَناً.**
    #:
    #: ⚠️ **والحارس يشهد على الالتزام لا على شجرة العمل، وهذا اختيار مقصود:**
    #: الوكلاء يكتبون ملفات كبيرة على مدى جولات، **فشجرة العمل حمراء بحقّ
    #: معظم الوقت.** وحارسٌ يخلط «عمل لم يكتمل» بـ«عمل أُلتزم وهو معطوب»
    #: **يُهمَل بعد أسبوع** — فيزول غرضه كله.
    #:
    #: ⚠️ **ولكن إغفالها صامتاً أسوأ**: فالهدف طلب هذه الوحدات بالاسم.
    #: فهي **مُعلَنة هنا حتى تُلتزَم، والقائمة تُفرَّغ ولا تزيد.**
    PENDING_COMMIT: tuple[str, ...] = (
    )

    def test_the_named_modules_not_yet_committed_are_declared(self):
        """
        🔑 **والدَّين الأكبر لا يُغفَل لأن الحارس لا يراه.**

        ⚠️ الهدف سمّى وحدات بعينها، **ومنها ما لم يُلتزَم به بعد** — فيمرّ
        من كل فحوص هذا الملف صامتاً، **لأن الحارس يقرأ الالتزام لا القرص.**
        وهذا الصنف يجعل ذلك مرئياً: **قائمة بأسمائها تُفرَّغ، لا تُنسى.**
        """
        tracked = _tracked()
        if tracked is None:
            self.skipTest("git غير متاح — تعذّر تحديد المُلتزَم به")

        present = sorted(
            name for name in self.PENDING_COMMIT if (PROJECT / f"{name}.py").exists()
        )
        self.assertEqual(
            present,
            sorted(self.PENDING_COMMIT),
            "وحدات في PENDING_COMMIT لا وجود لها على القرص — راجع القائمة",
        )

        # ⚠️ **وإن صارت الوحدة مُلتزَم بها، وجب حذفها** — فلا تبقى القائمة
        # تصف عملاً أُنجز، فتتحوّل إلى ضجيج لا يُقرأ.
        committed = sorted(
            name for name in self.PENDING_COMMIT if f"{name}.py" in tracked
        )
        self.assertEqual(
            committed,
            [],
            f"وحدات صارت مُلتزَم بها — احذفها من PENDING_COMMIT: {committed}",
        )

    def test_each_named_module_exists_and_has_a_test_file(self):
        tracked = _tracked()
        for name in self.NAMED:
            with self.subTest(module=name):
                if tracked is not None and f"{name}.py" not in tracked:
                    # ⚠️ **ووحدة لم تُلتزَم ليست محلّ شهادة**: لا يُقال عنها
                    # إنها معطوبة ولا إنها سليمة. **ودَينها في PENDING_COMMIT.**
                    continue
                self.assertTrue(
                    (PROJECT / f"{name}.py").exists(), f"الوحدة مفقودة: {name}.py"
                )
                if name in self.PENDING_TESTS:
                    continue
                test_file = PROJECT / "tests" / f"test_{name}.py"
                tracked = _tracked()
                # ⚠️ **واختبارٌ لم يُلتزَم به لا يُصلح وحدة**: فهو لا يصل إلى
                # أحد غير كاتبه. **والحارس يشهد على الالتزام لا على شجرة العمل**
                # — لأن شجرة العمل تحمل عملاً جارياً بحقّ.
                present = test_file.exists() and (
                    tracked is None or test_file.relative_to(PROJECT).as_posix() in tracked
                )
                self.assertTrue(
                    present,
                    f"{name}.py بلا اختبار مُلتزَم به — ولا يُقاس سلوكها",
                )

    def test_the_pending_tests_list_has_not_gone_stale(self):
        """
        ⚠️ **ولا يبقى الدَّين بعد سداده.**

        فوحدة صارت لها اختبارات وبقيت في `PENDING_TESTS` **تُخفي عملاً أُنجز**
        — وهو أسوأ من العكس، لأنه يجعل القائمة تفقد معناها فلا يقرؤها أحد.
        """
        tracked = _tracked()
        stale = sorted(
            name
            for name in self.PENDING_TESTS
            if (PROJECT / "tests" / f"test_{name}.py").exists()
            and (
                tracked is None
                or (PROJECT / "tests" / f"test_{name}.py").relative_to(PROJECT).as_posix()
                in tracked
            )
        )
        self.assertEqual(
            stale, [], f"وحدات صار لها اختبارات — احذفها من PENDING_TESTS: {stale}"
        )


if __name__ == "__main__":
    unittest.main()

def _tracked() -> set[str] | None:
    """المُلتزَم به — **مرّة واحدة لكل تشغيل**."""
    return _cached("tracked", _tracked_uncached)  # type: ignore[return-value]


def _dirty() -> set[str]:
    """المُعدَّل الآن — **مرّة واحدة لكل تشغيل**."""
    return _cached("dirty", _dirty_uncached)  # type: ignore[return-value]
