"""
اختبارات أدوات الاسترجاع الخمس وجامع الأدلة.
=============================================================================

تشغيل:
    python -m unittest discover -s tests -t . -v

هذه الاختبارات تُشغّل `legal_agent.py` **حقيقياً** — بأدواته وموجّهه ومنطقه —
بينما تُستبدل تبعياته الثقيلة بوحدات وهمية (`tests/fake_deps.py`). فلا حاجة
إلى torch ولا نموذج 2.2 GB ولا شبكة ولا مفتاح Supabase.

أهم ثلاث مجموعات هنا:

1. ``TestRetrievalRegression`` — يُثبت أن إعادة هيكلة الأدوات الخمس في مسار
   واحد **لم تغيّر الاسترجاع**: نفس دالة RPC، ونفس العتبة، ونفس الحدّ. وهذا
   هو الخطر الحقيقي في هذا النوع من التغيير: أداة تُسقِط عتبتها بصمت.

2. ``TestLegacyFormat`` — يُثبت أن المسارات التي لا تتحقّق (Chainlit وSwarmmy
   وسطر الأوامر) تُخرج **نفس النصّ السابق حرفياً**، فلا ينكسر شيء لم نمسّه.

3. ``TestThreadIsolation`` — يُثبت أن طلبين متزامنين لا تختلط أدلّتهما.
   لو اختلطت لقُبل استشهاد مسودّة بمقطع من مسودّة أخرى — وهو خطأ يمرّ بصمت
   لأنه يبدو تحقّقاً ناجحاً.
"""

import threading
import unittest

from tests import fake_deps

# ⚠️ يجب أن يسبق استيرادَ legal_agent: يحجب التبعيات الثقيلة قبل تحميلها.
fake_deps.install()

import legal_agent  # noqa: E402
import labour_rules  # noqa: E402
from citations import (  # noqa: E402
    CITATIONS_BEGIN,
    CITATIONS_END,
    Citation,
    normalize,
    parse_citations,
    verify_citations,
)

ALL_TOOLS = ("legislation", "drafts", "contracts", "notices", "poa")


class LegalAgentTestBase(unittest.TestCase):
    """قاعدة مشتركة: تُفرّغ التسجيلات قبل كل اختبار."""

    def setUp(self) -> None:
        fake_deps.reset()
        # النموذج مُخزَّن في الوحدة، فسجلّ النصوص المُضمَّنة يتراكم بين الاختبارات.
        legal_agent.get_model().encoded.clear()

    def set_rows(self, tool_key: str, *rows: dict) -> None:
        """يُهيّئ الصفوف التي ستُعيدها أداة معيّنة."""
        rpc_name = legal_agent._TOOL_CONFIG[tool_key][0]
        fake_deps.FAKE_SUPABASE.set_rows(rpc_name, list(rows))

    def call_tool(self, tool_key: str, query: str = "استعلام"):
        """يستدعي أداة الاسترجاع الحقيقية بالأداة المطلوبة."""
        tools = {
            "legislation": legal_agent.search_uae_legislation,
            "drafts": legal_agent.search_drafting_style,
            "contracts": legal_agent.search_contract_clauses,
            "notices": legal_agent.search_legal_notices,
            "poa": legal_agent.search_poa_clauses,
        }
        return tools[tool_key](query)


# ==============================================================================
# ١. انحدار الاسترجاع — لم يتغيّر شيء
# ==============================================================================


class TestRetrievalRegression(LegalAgentTestBase):
    """
    إعادة الهيكلة لم تغيّر الاسترجاع.

    الأدوات الخمس كانت نسخاً متشابهة، وجُمعت في `_search`. وهذا بالضبط نوع
    التغيير الذي يُسقِط عتبة أو يقلب حدّاً بلا أن يلاحظ أحد — لأن الأداة تظلّ
    «تعمل» وتُعيد نتائج، لكن بعتبة مختلفة تجلب مقاطع لا تصلح.
    """

    #: القيم الأصلية كما كانت في الكود قبل الجمع — مرجع لا يُعدَّل.
    EXPECTED = {
        "legislation": ("match_legal_documents", 0.75, 3),
        "drafts": ("match_legal_drafts", 0.70, 2),
        "contracts": ("match_legal_contracts", 0.70, 4),
        "notices": ("match_legal_notices", 0.70, 3),
        "poa": ("match_legal_poa", 0.70, 3),
    }

    def test_config_matches_original_values(self):
        """جدول الإعداد يطابق القيم الأصلية حرفياً."""
        for tool_key, expected in self.EXPECTED.items():
            with self.subTest(tool=tool_key):
                rpc, threshold, count, _label = legal_agent._TOOL_CONFIG[tool_key]
                self.assertEqual((rpc, threshold, count), expected)

    def test_each_tool_calls_its_own_rpc(self):
        """كل أداة تنادي دالة RPC الخاصة بها — لا دالة أختها."""
        for tool_key, (rpc_name, _t, _c) in self.EXPECTED.items():
            with self.subTest(tool=tool_key):
                fake_deps.reset()
                self.set_rows(tool_key, fake_deps.make_row())
                self.call_tool(tool_key)
                self.assertEqual(fake_deps.FAKE_SUPABASE.rpc_names(), [rpc_name])

    def test_each_tool_passes_its_threshold_and_count(self):
        """العتبة والحدّ يُمرَّران صحيحين إلى RPC."""
        for tool_key, (rpc_name, threshold, count) in self.EXPECTED.items():
            with self.subTest(tool=tool_key):
                fake_deps.reset()
                self.set_rows(tool_key, fake_deps.make_row())
                self.call_tool(tool_key)
                _name, params = fake_deps.FAKE_SUPABASE.last_call()
                self.assertEqual(params["match_threshold"], threshold)
                self.assertEqual(params["match_count"], count)

    def test_embedding_has_1024_dimensions(self):
        """
        المتجه 1024 بُعداً — مطابق لعمود `vector(1024)` في `schema.sql`.

        لو اختلفا لفشل الاسترجاع **في الإنتاج وحده**، لأن الاختبار لا يلمس
        قاعدة بيانات.
        """
        self.set_rows("legislation", fake_deps.make_row())
        self.call_tool("legislation")
        _name, params = fake_deps.FAKE_SUPABASE.last_call()
        self.assertEqual(len(params["query_embedding"]), fake_deps.EMBEDDING_DIM)
        self.assertEqual(fake_deps.EMBEDDING_DIM, 1024)

    def test_query_prefix_is_preserved(self):
        """
        البادئة `"query: "` شرط لعمل نموذج e5.

        إغفالها يُفسد جودة الاسترجاع **بلا أي خطأ ظاهر** — فلا شيء يكشفه إلا
        فحص النصّ المُضمَّن نفسه. (المقابل `"passage: "` في سكربتات الاستيعاب.)
        """
        self.set_rows("legislation", fake_deps.make_row())
        self.call_tool("legislation", "فسخ عقد إيجار")
        encoded = legal_agent.get_model().encoded
        self.assertEqual(len(encoded), 1)
        self.assertTrue(encoded[0].startswith("query: "), encoded[0][:40])
        self.assertIn("فسخ عقد إيجار", encoded[0])

    def test_empty_results_message_per_tool(self):
        """لكل أداة رسالتها عند غياب النتائج — ولا انهيار."""
        for tool_key in ALL_TOOLS:
            with self.subTest(tool=tool_key):
                fake_deps.reset()
                # لا صفوف مُعدّة: يُعيد RPC قائمة فارغة
                result = self.call_tool(tool_key)
                self.assertEqual(result, legal_agent._EMPTY_RESULTS[tool_key])

    def test_no_tool_calls_rpc_directly(self):
        """
        لا نداء RPC مباشر في ملف الوحدة خارج `_search`.

        الفحص على المصدر: لو عاد أحدهم فنسخ نداءً في أداة، لظهر هنا فوراً.
        """
        import pathlib
        import re

        source = pathlib.Path(legal_agent.__file__).read_text(encoding="utf-8")
        occurrences = re.findall(r"get_supabase\(\)\.rpc", source)
        self.assertEqual(len(occurrences), 1, "نداء RPC يجب أن يكون في موضع واحد")


# ==============================================================================
# ٢. التنسيق القديم — لم ينكسر مسار لم نمسّه
# ==============================================================================


class TestLegacyFormat(LegalAgentTestBase):
    """
    بلا جامع أدلة، الإخراج يطابق السابق حرفياً.

    هذا ما يحمي Chainlit وSwarmmy وسطر الأوامر: لم تُعدَّل، فيجب ألّا يتغيّر
    ما تتلقّاه.
    """

    def test_legislation_format_is_byte_identical(self):
        """أداة التشريعات بلا وسم عرض — كما كانت."""
        self.set_rows("legislation", fake_deps.make_row(document_name="قانون", chunk_content="نصّ"))
        self.assertEqual(self.call_tool("legislation"), "\n- قانون: نصّ\n")

    def test_each_tool_keeps_its_own_label(self):
        """وسوم العرض لكل أداة: هيكلة/بند/قسم/صلاحية."""
        expected = {
            "drafts": "\n- هيكلة من: مستند: نصّ\n",
            "contracts": "\n- بند من: مستند: نصّ\n",
            "notices": "\n- قسم من: مستند: نصّ\n",
            "poa": "\n- صلاحية من: مستند: نصّ\n",
        }
        for tool_key, wanted in expected.items():
            with self.subTest(tool=tool_key):
                fake_deps.reset()
                self.set_rows(tool_key, fake_deps.make_row(document_name="مستند", chunk_content="نصّ"))
                self.assertEqual(self.call_tool(tool_key), wanted)

    def test_multiple_rows_are_joined(self):
        """عدّة مقاطع تُدمج في نصّ واحد كما كانت."""
        self.set_rows(
            "legislation",
            fake_deps.make_row(chunk_id=1, document_name="أ", chunk_content="نص أ"),
            fake_deps.make_row(chunk_id=2, document_name="ب", chunk_content="نص ب"),
        )
        self.assertEqual(self.call_tool("legislation"), "\n- أ: نص أ\n\n- ب: نص ب\n")

    def test_truncation_notice_is_kept(self):
        """الاقتطاع عند 1800 محرفاً مع إشعاره — كما كان بالضبط."""
        self.set_rows("legislation", fake_deps.make_row(chunk_content="ط" * 2000))
        result = self.call_tool("legislation")
        self.assertTrue(result.endswith("\n... (تم الاقتطاع)"))
        self.assertEqual(len(result), 1800 + len("\n... (تم الاقتطاع)"))

    def test_no_truncation_when_short(self):
        self.set_rows("legislation", fake_deps.make_row(chunk_content="نصّ قصير"))
        self.assertNotIn("تم الاقتطاع", self.call_tool("legislation"))

    def test_no_collector_is_registered_implicitly(self):
        """غياب السياق يعني غياب الجامع — لا إنشاء ضمني بحالة عالقة."""
        self.assertIsNone(legal_agent.current_collector())
        self.set_rows("legislation", fake_deps.make_row())
        self.call_tool("legislation")
        self.assertIsNone(legal_agent.current_collector(), "لم يُفترض إنشاء جامع")


# ==============================================================================
# ٣. التنسيق الجديد — مع جامع أدلة
# ==============================================================================


class TestEvidenceCollector(LegalAgentTestBase):
    """مع جامع نشط: مقاطع مرقّمة تُسجَّل وتُعرض للنموذج ليقتبس منها."""

    def test_refs_are_sequential_with_tool_prefix(self):
        """مراجع L1..L3 للتشريعات، وC1..C2 للعقود."""
        self.set_rows(
            "legislation",
            *[fake_deps.make_row(chunk_id=i) for i in range(3)],
        )
        with legal_agent.collect_evidence() as collected:
            block = self.call_tool("legislation")

        self.assertIn("[L1]", block)
        self.assertIn("[L2]", block)
        self.assertIn("[L3]", block)
        self.assertEqual([e.ref for e in collected.evidence], ["L1", "L2", "L3"])

    def test_evidence_carries_source_fields(self):
        """كل دليل يحمل معرّف المقطع واسم المستند ودرجة التشابه."""
        self.set_rows(
            "notices",
            fake_deps.make_row(
                chunk_id=48213,
                document_name="إنذار سابق",
                chunk_content="يُرسل الإنذار كتابةً",
                similarity=0.83,
            ),
        )
        with legal_agent.collect_evidence() as collected:
            block = self.call_tool("notices")

        self.assertEqual(len(collected.evidence), 1)
        item = collected.evidence[0]
        self.assertEqual(item.chunk_id, "48213")
        self.assertEqual(item.document_name, "إنذار سابق")
        self.assertEqual(item.similarity, 0.83)
        self.assertEqual(item.tool, "notices")
        self.assertEqual(item.ref, "N1")
        self.assertIn("إنذار سابق", block)

    def test_refs_stay_unique_across_repeated_calls(self):
        """
        نداءان لنفس الأداة في الجولة نفسها لا يتصادمان في المراجع.

        لو تصادما لرأى النموذج مقطعين مختلفين بالمرجع نفسه، فصار اقتباسه
        غامضاً والتحقّق معه.
        """
        self.set_rows("legislation", fake_deps.make_row(chunk_id=1), fake_deps.make_row(chunk_id=2))
        with legal_agent.collect_evidence() as collected:
            self.call_tool("legislation")
            self.call_tool("legislation")

        refs = [e.ref for e in collected.evidence]
        self.assertEqual(refs, ["L1", "L2", "L3", "L4"])
        self.assertEqual(len(set(refs)), len(refs), "مراجع مكرّرة")

    def test_different_tools_use_different_prefixes(self):
        """كل أداة ببادئتها — فيعرف المحامي مصدر كل سند."""
        for tool_key in ALL_TOOLS:
            self.set_rows(tool_key, fake_deps.make_row())

        with legal_agent.collect_evidence() as collected:
            for tool_key in ALL_TOOLS:
                self.call_tool(tool_key)

        refs = [e.ref for e in collected.evidence]
        self.assertEqual(refs, ["L1", "D1", "C1", "N1", "P1"])

    def test_long_chunk_does_not_drop_the_next_one(self):
        """
        🔑 إصلاح عيب حقيقي في السلوك القديم.

        الاقتطاع القديم كان على **مجموع** المقاطع، فمقطع طويل يستهلك الميزانية
        كلها وتُسقَط المقاطع التالية بالكامل — فيضيع سند موجود بلا أن يعلم أحد.
        الآن السقف لكل مقطع، فيصل الجميع.
        """
        self.set_rows(
            "legislation",
            fake_deps.make_row(chunk_id=1, document_name="طويل", chunk_content="ط" * 3000),
            fake_deps.make_row(chunk_id=2, document_name="قصير", chunk_content="نصّ مهمّ"),
        )
        with legal_agent.collect_evidence() as collected:
            block = self.call_tool("legislation")

        self.assertEqual(len(collected.evidence), 2)
        self.assertIn("قصير", block, "المقطع الثاني ضاع")
        self.assertIn("نصّ مهمّ", block)

    def test_per_chunk_truncation_is_applied(self):
        """المقطع الأطول من السقف يُقتطع، ويبقى دليلاً صالحاً للاقتباس."""
        self.set_rows("legislation", fake_deps.make_row(chunk_content="ط" * 3000))
        with legal_agent.collect_evidence() as collected:
            self.call_tool("legislation")

        text = collected.evidence[0].text
        self.assertEqual(len(text), legal_agent.MAX_CHARS_PER_CHUNK + len("\n... (تم الاقتطاع)"))
        self.assertTrue(text.endswith("\n... (تم الاقتطاع)"))

    def test_collector_len_and_evidence_copy(self):
        """`evidence` تُعيد نسخة — فلا يُعدّل مستدعٍ السجلّ بالخطأ."""
        self.set_rows("legislation", fake_deps.make_row())
        with legal_agent.collect_evidence() as collected:
            self.call_tool("legislation")
            self.assertEqual(len(collected), 1)
            leaked = collected.evidence
            leaked.clear()
            self.assertEqual(len(collected), 1, "النسخة أثّرت على الأصل")


# ==============================================================================
# ٤. عزل الجلسات
# ==============================================================================


class TestCollectorIsolation(LegalAgentTestBase):
    """
    الأدلّة معزولة بين الطلبات.

    هذا أخطر ما في التصميم: `main.py` يُشغّل الوكيل في خيط منفصل لكل طلب. ولو
    كان الجامع متغيّراً عاماً لرأى الطلب أدلّة غيره، فيُقبل اقتباس مسودّة
    بمقطع من مسودّة أخرى — وهذا يبدو تحقّقاً ناجحاً، فيمرّ بصمت.
    """

    def test_two_threads_do_not_share_evidence(self):
        """طلبان متزامنان: كلٌّ يرى أدلّته وحدها."""
        self.set_rows("legislation", fake_deps.make_row(chunk_id=1, document_name="تشريع"))
        self.set_rows("contracts", fake_deps.make_row(chunk_id=2, document_name="عقد"))

        results: dict[str, list] = {}
        barrier = threading.Barrier(2)

        def worker(key: str, tool_key: str) -> None:
            with legal_agent.collect_evidence() as collected:
                barrier.wait(timeout=5)  # يضمن التزامن الفعلي
                self.call_tool(tool_key)
                results[key] = collected.evidence

        threads = [
            threading.Thread(target=worker, args=("a", "legislation")),
            threading.Thread(target=worker, args=("b", "contracts")),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)

        self.assertEqual(len(results["a"]), 1, "تسرّبت أدلّة من الطلب الآخر")
        self.assertEqual(len(results["b"]), 1, "تسرّبت أدلّة من الطلب الآخر")
        self.assertEqual(results["a"][0].tool, "legislation")
        self.assertEqual(results["b"][0].tool, "contracts")
        self.assertEqual(results["a"][0].chunk_id, "1")
        self.assertEqual(results["b"][0].chunk_id, "2")

    def test_collector_is_released_after_context(self):
        """بعد الخروج من السياق لا يبقى جامع نشط."""
        self.set_rows("legislation", fake_deps.make_row())
        with legal_agent.collect_evidence():
            self.assertIsNotNone(legal_agent.current_collector())
        self.assertIsNone(legal_agent.current_collector())

    def test_collector_is_released_after_exception(self):
        """وحتى لو انهار الوكيل، لا يبقى جامع عالقاً للأبد."""
        self.set_rows("legislation", fake_deps.make_row())
        with self.assertRaises(RuntimeError):
            with legal_agent.collect_evidence():
                raise RuntimeError("فشل الوكيل")
        self.assertIsNone(legal_agent.current_collector())

    def test_successive_contexts_do_not_accumulate(self):
        """جولتان متتاليتان: الثانية لا ترى أدلّة الأولى."""
        self.set_rows("legislation", fake_deps.make_row())
        with legal_agent.collect_evidence() as first:
            self.call_tool("legislation")
        with legal_agent.collect_evidence() as second:
            self.call_tool("legislation")

        self.assertEqual(len(first), 1)
        self.assertEqual(len(second), 1)
        self.assertEqual(second.evidence[0].ref, "L1", "المراجع استمرّت من الجولة السابقة")


# ==============================================================================
# ٥. الموجّه
# ==============================================================================


class TestPrompts(unittest.TestCase):
    """قواعد التوثيق تُضاف فقط حيث يمكن التحقّق فعلاً."""

    def test_base_prompt_is_unchanged(self):
        """`SYSTEM_PROMPT` لم تُعدَّل — فبقيت مساراتها على سلوكها السابق."""
        self.assertNotIn(CITATIONS_BEGIN, legal_agent.SYSTEM_PROMPT)
        self.assertNotIn("توثيق الأسانيد", legal_agent.SYSTEM_PROMPT)

    def test_base_prompt_still_has_everything_it_had(self):
        """قواعد التوجيه والتنسيق وأسماء الأدوات الخمس — كلها باقية."""
        prompt = legal_agent.SYSTEM_PROMPT
        for tool_name in (
            "search_uae_legislation",
            "search_drafting_style",
            "search_contract_clauses",
            "search_legal_notices",
            "search_poa_clauses",
        ):
            with self.subTest(tool=tool_name):
                self.assertIn(tool_name, prompt)
        self.assertIn("تنسيق المخرج", prompt)
        self.assertIn("قواعد التوجيه", prompt)
        self.assertIn(legal_agent.ROUTING_RULES, prompt)
        self.assertIn(legal_agent.FORMATTING_RULES, prompt)

    def test_cited_prompt_is_base_plus_rules(self):
        """
        الموجّه الموثَّق = الأساسي + قواعد التوثيق + قواعد الاحتساب، لا نسخة موازية.

        ⚠️ **وهذا السطر عُدِّل بقدر ما لزم وحده.** كان يفحص أن المجموع طرفان
        (الأساسي + التوثيق)، فأُضيف الطرف الثالث — وهو `rules_block()` من
        `labour_rules` — لأن قواعد احتساب المستحقات العمالية تُلحَق بالموجّه
        الموثَّق. والفحص باقٍ على معناه: الموجّه **مُركَّب** من أجزائه المعروفة،
        لا نصّاً ثالثاً يُنسخ ويُنسى.
        """
        self.assertEqual(
            legal_agent.SYSTEM_PROMPT_CITED,
            legal_agent.SYSTEM_PROMPT
            + legal_agent.CITATION_RULES
            + labour_rules.rules_block(),
        )

    def test_citation_rules_state_the_contract(self):
        """القواعد تذكر الوسمين والفاصل وشرط الحرفية والقيود المهمّة."""
        rules = legal_agent.CITATION_RULES
        self.assertIn(CITATIONS_BEGIN, rules)
        self.assertIn(CITATIONS_END, rules)
        self.assertIn("::", rules)
        self.assertIn("حرفي", rules)
        self.assertIn("[L1]", rules)
        self.assertIn("لا تذكر رقم مادة", rules)

    def test_the_labour_rules_reach_the_model_through_the_prompt(self):
        """
        🔑 **اختبار الوصلة التي كانت مفقودة.**

        العيب الذي جاء `labour_rules` لمنعه وقع **لأن القاعدة لم تكن في المنظومة
        بل في محادثة**: المراجع أبلغ النموذج بالعيب، وعاد في التشغيل التالي. فما
        يُفحص هنا ليس وجود الملف ولا جودة نصّه، بل **أن الأساس الذي تطلبه القاعدة
        يصل إلى النموذج فعلاً**. ولو نُسي الإلحاق لمرّ كل شيء وبقي العيب.
        """
        prompt = legal_agent.SYSTEM_PROMPT_CITED
        self.assertIn(labour_rules.rules_block(), prompt)
        self.assertIn("٢٩/٩", prompt)
        self.assertIn("٤٣/٢", prompt)
        self.assertIn("غير محقَّق", prompt)
        self.assertNotIn("قواعد احتساب المستحقات العمالية", legal_agent.SYSTEM_PROMPT)

    def test_rules_match_what_the_parser_expects(self):
        """
        عقد الموجّه يطابق ما يقرؤه `parse_citations`.

        لو غيّر أحدهم الصيغة في الموجّه ولم يغيّرها في القارئ، لما وُجد سند
        واحد ولبدت كل مسودّة «بلا أسانيد» بلا سبب ظاهر.
        """
        sample = (
            "البند الأول: يلتزم الطرف الثاني.\n"
            f"{CITATIONS_BEGIN}\n"
            "L1 :: عبارة حرفية من المقطع المسترجع\n"
            f"{CITATIONS_END}"
        )
        parsed = parse_citations(sample)
        self.assertTrue(parsed.has_block)
        self.assertEqual(parsed.malformed, [])
        self.assertEqual(parsed.citations[0].ref, "L1")


# ==============================================================================
# ٦. الإدماج الكامل
# ==============================================================================


class TestEndToEndIntegration(LegalAgentTestBase):
    """
    المسار كاملاً: استرجاع حقيقي ← نصّ مرقَّم ← اقتباس النموذج ← الحكم.

    هذا هو الاختبار الذي يُثبت أن الخطوتين (المحرّك والربط) تعملان معاً،
    وأن اقتباساً مؤلَّفاً يُرفض فعلاً في المسار المُركَّب لا في العزلة.
    """

    CLAUSE = "على المستأجر سداد الأجرة في أول خمسة أيام من كل شهر ميلادي."

    def _run(self, model_output: str):
        self.set_rows(
            "contracts",
            fake_deps.make_row(
                chunk_id=777,
                document_name="عقد إيجار سكني",
                chunk_content=self.CLAUSE,
                similarity=0.91,
            ),
        )
        with legal_agent.collect_evidence() as collected:
            self.call_tool("contracts")
            parsed = parse_citations(model_output)
            return verify_citations(parsed.citations, collected.evidence)

    def test_genuine_quote_is_verified(self):
        """اقتباس حرفي من المقطع: يُقبل ويُنسَب لمستنده الصحيح."""
        outcome = self._run(
            f"عقد إيجار\n{self.CLAUSE}\n"
            f"{CITATIONS_BEGIN}\n"
            "C1 :: سداد الأجرة في أول خمسة أيام من كل شهر\n"
            f"{CITATIONS_END}"
        )
        self.assertTrue(outcome.has_evidence)
        self.assertEqual(outcome.verified[0].document_name, "عقد إيجار سكني")
        self.assertEqual(outcome.verified[0].chunk_id, "777")
        self.assertEqual(outcome.rejected, [])

    def test_forged_quote_is_rejected_in_the_real_path(self):
        """
        🔑 الغاية كلها: مسودّة تبدو مقنعة وفيها بند مؤلَّف.

        المقطع يقول «خمسة أيام»، والمسودّة تدّعي «ثلاثين يوماً» وتنسبها إلى
        العقد. النظام يجب أن يرفضها — لا أن يسلّمها.
        """
        outcome = self._run(
            "عقد إيجار\nعلى المستأجر السداد خلال ثلاثين يوماً.\n"
            f"{CITATIONS_BEGIN}\n"
            "C1 :: سداد الأجرة خلال ثلاثين يوماً من بداية الشهر\n"
            f"{CITATIONS_END}"
        )
        self.assertFalse(outcome.has_evidence)
        self.assertEqual(len(outcome.rejected), 1)
        self.assertIn("غير موجود حرفياً", outcome.rejected[0].reason)

    def test_quote_passes_despite_diacritic_differences(self):
        """النموذج لن يعيد التشكيل — وغيابه لا يجوز أن يُبطل اقتباساً صحيحاً."""
        outcome = self._run(
            f"عقد إيجار\n{self.CLAUSE}\n"
            f"{CITATIONS_BEGIN}\n"
            "C1 :: علي المستاجر سداد الاجره في اول خمسه ايام من كل شهر\n"
            f"{CITATIONS_END}"
        )
        self.assertTrue(outcome.has_evidence, outcome.rejected)

    def test_unknown_ref_is_rejected(self):
        """مرجع لم يُسترجَع إطلاقاً — أخطر صور التأليف."""
        outcome = self._run(
            f"عقد إيجار\n{self.CLAUSE}\n"
            f"{CITATIONS_BEGIN}\n"
            "C9 :: عبارة طويلة بما يكفي للاجتياز لكن مرجعها وهمي\n"
            f"{CITATIONS_END}"
        )
        self.assertFalse(outcome.has_evidence)
        self.assertIn("غير موجود", outcome.rejected[0].reason)

    def test_numbered_block_is_what_the_model_sees(self):
        """
        النصّ الذي يصل النموذج يحمل المراجع فعلاً.

        لو نسي التنسيق المراجع لطلبنا منه الاقتباس بمرجع لا يراه — وهو نقض
        للعقد من أساسه.
        """
        self.set_rows("contracts", fake_deps.make_row(chunk_content=self.CLAUSE))
        with legal_agent.collect_evidence():
            block = self.call_tool("contracts")
        self.assertIn("[C1]", block)
        self.assertIn("المستند:", block)
        self.assertIn(normalize("سداد الأجرة")[:10], normalize(block))


if __name__ == "__main__":
    unittest.main(verbosity=2)
