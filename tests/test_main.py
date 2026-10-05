"""
اختبارات `main.py` — المسارات والبثّ والتحقّق من الأسانيد.
=============================================================================

تشغيل:
    python -m unittest discover -s tests -t . -v

`main.py` يُشغّل الوكيل في **خيط منفصل** ويمرّر أحداثه إلى طابور asyncio. وأخطر
ما في هذه البنية هو موضع فتح جامع الأدلّة: `ContextVar` معزول لكل خيط، فلو
فُتح في حلقة الأحداث بدل الخيط العامل لما رأته الأدوات، ولظلّ التحقّق يعمل
**بلا أدلّة** فيرفض كل استشهاد — أو يقبل بلا فحص. وهذا ما تفحصه المجموعة هنا.

الاختبار الحاسم: ``test_evidence_is_registered_for_the_round`` — يُثبت أن
عدد الأدلّة المسجَّلة أكبر من صفر، أي أن الجامع فُتح في الموضع الصحيح.
"""

import asyncio
import json
import unittest

from tests import fake_deps

# ⚠️ قبل استيراد main: يحجب fastapi وpydantic والتبعيات الثقيلة.
fake_deps.install()

import main  # noqa: E402
from citations import CITATIONS_BEGIN, CITATIONS_END  # noqa: E402

CLAUSE = "على المستأجر سداد الأجرة في أول خمسة أيام من كل شهر ميلادي."
GENUINE_QUOTE = "سداد الأجرة في أول خمسة أيام من كل شهر"
FORGED_QUOTE = "سداد الأجرة خلال ثلاثين يوماً من بداية الشهر"


def scripted_turn(quote: str, *, body: str = "عقد إيجار تجاري\nالبند الأول: السداد.") -> list:
    """
    يبني نصّاً برمجياً للوكيل: نداء أداة عقود، ثم مسودّة بكتلة أسانيد.

    الأداة **حقيقية** وتُنفَّذ فعلاً (انظر `fake_deps._run_scripted_stream`)،
    فتمرّ الأدلّة في جامع الجولة كما تمرّ في الإنتاج.
    """
    return [
        {"tool": "search_contract_clauses", "args": {"query": "إيجار"}},
        {
            "content": (
                f"{body}\n"
                f"{CITATIONS_BEGIN}\n"
                f"C1 :: {quote}\n"
                f"{CITATIONS_END}"
            )
        },
    ]


def drain_sse(messages: list) -> list:
    """يستهلك مولّد SSE ويُرجع الإطارات الخام."""

    async def collect() -> list:
        return [frame async for frame in main._sse_generator(messages)]

    return asyncio.run(collect())


def parse_frames(frames: list) -> list:
    """يحلّل إطارات SSE ويُرجع كائنات الأحداث."""
    events = []
    for frame in frames:
        assert frame.startswith("data: "), f"إطار غير صالح: {frame[:40]!r}"
        assert frame.endswith("\n\n"), f"إطار بلا فاصل: {frame[-10:]!r}"
        events.append(json.loads(frame[len("data: ") :]))
    return events


class MainTestBase(unittest.TestCase):
    """قاعدة مشتركة: تُفرّغ التسجيلات والنصّ البرمجي قبل كل اختبار."""

    def setUp(self) -> None:
        fake_deps.reset()
        fake_deps.FAKE_SUPABASE.set_rows(
            "match_legal_contracts",
            [fake_deps.make_row(chunk_id=777, document_name="عقد إيجار سكني", chunk_content=CLAUSE)],
        )

    def run_stream(self) -> list:
        """يشغّل `_stream_agent` ويُرجع كل أحداثه (kind, payload)."""
        return list(main._stream_agent(main._build_messages("صغ عقداً")))


# ==============================================================================
# ١. المسارات والمصادقة — انحدار
# ==============================================================================


class TestRoutes(MainTestBase):
    """المسارات الأربعة والمصادقة عليها — أول ما ينكسر عند إضافة ميزة."""

    def test_all_routes_still_registered(self):
        routes = {(method, path) for method, path, _fn, _kw in main.app.routes}
        for expected in (
            ("GET", "/"),
            ("GET", "/health"),
            ("POST", "/generate"),
            ("POST", "/chat"),
        ):
            with self.subTest(route=expected):
                self.assertIn(expected, routes)
        self.assertEqual(len(main.app.routes), 4)

    def test_sensitive_routes_stay_protected(self):
        """`/generate` و`/chat` يبقيان محميين — لا تُضاف ميزة تفتحهما."""
        posts = {
            path: kw.get("dependencies")
            for method, path, _fn, kw in main.app.routes
            if method == "POST"
        }
        self.assertTrue(posts["/generate"])
        self.assertTrue(posts["/chat"])

    def test_health_stays_open_and_reports_verification(self):
        """/health غير محمي (للمراقبة) ويُعلن أن التحقّق مُفعَّل."""
        payload = asyncio.run(main.health())
        self.assertEqual(payload["status"], "ok")
        self.assertIn("tools", payload)
        self.assertTrue(payload["citation_verification"])
        self.assertIn("auth_required", payload)


# ==============================================================================
# ٢. الموجّه
# ==============================================================================


class TestMessages(MainTestBase):
    """`/generate` و`/chat` يستخدمان الموجّه الموثَّق — وإلا طلبنا سندات لا تُقبل."""

    def test_system_message_carries_citation_rules(self):
        messages = main._build_messages("وقائع")
        self.assertIn(CITATIONS_BEGIN, messages[0].content)
        self.assertIn(CITATIONS_END, messages[0].content)

    def test_document_type_hint_still_injected(self):
        """حقن نوع المستند وتلميح الأداة — لم يتغيّر."""
        messages = main._build_messages("وقائع", "إنذار قانوني")
        self.assertIn("إنذار قانوني", messages[1].content)
        self.assertIn("search_legal_notices", messages[1].content)

    def test_session_history_uses_cited_prompt(self):
        """الجلسة الجديدة تبدأ بالموجّه الموثَّق أيضاً."""
        history = main._get_history("اختبار-جلسة")
        self.assertIn(CITATIONS_BEGIN, history[0].content)


# ==============================================================================
# ٣. عقدة التحقّق
# ==============================================================================


class TestVerifyRound(MainTestBase):
    """`_verify_round` — فصل المستند النظيف عن تقرير الأسانيد."""

    def _evidence(self):
        from legal_agent import _build_evidence  # noqa: PLC0415
        from citations import RefAllocator  # noqa: PLC0415

        return _build_evidence(
            "contracts",
            [fake_deps.make_row(chunk_id=777, document_name="عقد إيجار سكني", chunk_content=CLAUSE)],
            RefAllocator(),
        )

    def test_clean_text_has_no_citation_block(self):
        """المستند المُعاد للواجهة نظيف — الكتلة ليست جزءاً من العقد."""
        raw = f"عقد إيجار\n{CITATIONS_BEGIN}\nC1 :: {GENUINE_QUOTE}\n{CITATIONS_END}"
        clean, _report = main._verify_round(raw, self._evidence())
        self.assertEqual(clean, "عقد إيجار")
        self.assertNotIn(CITATIONS_BEGIN, clean)

    def test_genuine_quote_appears_in_report(self):
        raw = f"عقد إيجار\n{CITATIONS_BEGIN}\nC1 :: {GENUINE_QUOTE}\n{CITATIONS_END}"
        _clean, report = main._verify_round(raw, self._evidence())

        self.assertTrue(report["has_evidence"])
        self.assertEqual(len(report["verified"]), 1)
        self.assertEqual(report["verified"][0]["document_name"], "عقد إيجار سكني")
        self.assertEqual(report["verified"][0]["chunk_id"], "777")
        self.assertEqual(report["rejected"], [])
        self.assertIn("موثَّقة", report["summary"])

    def test_forged_quote_is_reported_with_reason(self):
        """🔑 الغاية: بند مؤلَّف يظهر في التقرير بسببه، لا يمرّ صامتاً."""
        raw = f"عقد إيجار\n{CITATIONS_BEGIN}\nC1 :: {FORGED_QUOTE}\n{CITATIONS_END}"
        _clean, report = main._verify_round(raw, self._evidence())

        self.assertFalse(report["has_evidence"])
        self.assertEqual(report["verified"], [])
        self.assertEqual(len(report["rejected"]), 1)
        self.assertIn("غير موجود حرفياً", report["rejected"][0]["reason"])
        self.assertIn(FORGED_QUOTE, report["rejected"][0]["quoted_span"])

    def test_unbacked_article_is_reported(self):
        """مادة في المتن لم ترد في أي مقطع: تُعرَض بلا سند."""
        raw = (
            "عقد إيجار\nيستند إلى المادة ٤٢ من قانون المعاملات المدنية.\n"
            f"{CITATIONS_BEGIN}\nC1 :: {GENUINE_QUOTE}\n{CITATIONS_END}"
        )
        _clean, report = main._verify_round(raw, self._evidence())

        numbers = [item["number"] for item in report["unbacked_articles"]]
        self.assertIn("42", numbers)

    def test_backed_article_is_not_reported(self):
        """مادة وردت في المقطع المسترجَع: لا تُوسَم."""
        evidence = [
            fake_deps.make_row(chunk_id=1, document_name="قانون", chunk_content="المادة 42 تجيز الفسخ")
        ]
        from citations import RefAllocator  # noqa: PLC0415
        from legal_agent import _build_evidence  # noqa: PLC0415

        built = _build_evidence("legislation", evidence, RefAllocator())
        _clean, report = main._verify_round("استناداً إلى المادة 42", built)
        self.assertEqual(report["unbacked_articles"], [])

    def test_malformed_lines_are_surfaced(self):
        """سطر سند مشوّه يُعرَض للتشخيص — لا يُسقَط صامتاً."""
        raw = f"عقد إيجار\n{CITATIONS_BEGIN}\nC1 بلا فاصل\n{CITATIONS_END}"
        _clean, report = main._verify_round(raw, self._evidence())
        self.assertEqual(report["malformed_lines"], ["C1 بلا فاصل"])

    def test_missing_block_is_reported_as_such(self):
        """بلا كتلة: التقرير يقول ذلك، ولا يدّعي وجود سندات."""
        _clean, report = main._verify_round("عقد إيجار بلا سند", self._evidence())
        self.assertFalse(report["has_citation_block"])
        self.assertFalse(report["has_evidence"])
        self.assertIn("لم يُرفق", report["summary"])

    def test_report_is_json_serializable(self):
        """التقرير يُبثّ كـ JSON — فلا كائنات غريبة فيه."""
        raw = f"عقد إيجار\nيستند إلى المادة ٩٩.\n{CITATIONS_BEGIN}\nC1 :: {FORGED_QUOTE}\n{CITATIONS_END}"
        _clean, report = main._verify_round(raw, self._evidence())
        json.dumps(report, ensure_ascii=False)


# ==============================================================================
# ٤. المسار الكامل عبر الوكيل
# ==============================================================================


class TestStreamAgent(MainTestBase):
    """`_stream_agent` — الجامع، والمراحل، والتقرير، والمستند النظيف."""

    def test_evidence_is_registered_for_the_round(self):
        """
        🔑 الاختبار الحاسم في هذا الملف.

        يُثبت أن جامع الأدلّة فُتح في **الخيط العامل** حيث تجري الأدوات. ولو
        فُتح في حلقة الأحداث لكانت الأدلّة صفراً، ولظلّ التحقّق «يعمل» وهو
        يرفض كل شيء لأنه لا يرى شيئاً.
        """
        fake_deps.AGENT_SCRIPT = scripted_turn(GENUINE_QUOTE)
        events = self.run_stream()
        report = next(payload for kind, payload in events if kind == "citations")

        self.assertEqual(report["evidence_count"], 1, "لم تُسجَّل أي أدلّة")
        self.assertTrue(report["has_evidence"])
        self.assertEqual(len(report["verified"]), 1)

    def test_stages_are_emitted_in_order(self):
        """المراحل تُبثّ كما كانت: تحليل ← أداة ← أدلّة ← صياغة."""
        fake_deps.AGENT_SCRIPT = scripted_turn(GENUINE_QUOTE)
        stages = [payload for kind, payload in self.run_stream() if kind == "stage"]

        self.assertEqual(stages[0], main.STAGE_ANALYSING)
        self.assertIn(main.TOOL_STAGE_LABELS["search_contract_clauses"], stages)
        self.assertIn(main.STAGE_EVIDENCE_FOUND, stages)
        self.assertIn(main.STAGE_DRAFTING, stages)

    def test_citations_event_precedes_final(self):
        """التقرير يُبثّ قبل المستند — حتى تجهز الواجهة لعرضه."""
        fake_deps.AGENT_SCRIPT = scripted_turn(GENUINE_QUOTE)
        kinds = [kind for kind, _payload in self.run_stream()]
        self.assertLess(kinds.index("citations"), kinds.index("final"))

    def test_final_text_is_clean(self):
        """ما يصل الواجهة لا يحمل كتلة الأسانيد."""
        fake_deps.AGENT_SCRIPT = scripted_turn(GENUINE_QUOTE)
        final = next(payload for kind, payload in self.run_stream() if kind == "final")
        self.assertIn("عقد إيجار", final)
        self.assertNotIn(CITATIONS_BEGIN, final)
        self.assertNotIn(CITATIONS_END, final)

    def test_forged_draft_is_flagged_end_to_end(self):
        """مسودّة بمادة مؤلَّفة: التقرير يقول ذلك والمستند يبقى نظيفاً."""
        fake_deps.AGENT_SCRIPT = scripted_turn(FORGED_QUOTE)
        events = self.run_stream()
        report = next(payload for kind, payload in events if kind == "citations")
        final = next(payload for kind, payload in events if kind == "final")

        self.assertFalse(report["has_evidence"])
        self.assertEqual(len(report["rejected"]), 1)
        self.assertNotIn(CITATIONS_BEGIN, final)

    def test_no_tool_call_yields_empty_final_without_report(self):
        """
        بلا نصّ: مستند فارغ **ولا تقرير أسانيد**.

        وهذا هو العقد: لا يوجد ما يُتحقَّق منه، فلا نُصدر تقريراً فارغاً يوهم
        بأن فحصاً جرى. وطبقة SSE تُبلّغ العميل بخطأ صريح بدل ذلك.
        """
        fake_deps.AGENT_SCRIPT = [{"content": ""}]
        events = self.run_stream()
        final = next(payload for kind, payload in events if kind == "final")
        reports = [payload for kind, payload in events if kind == "citations"]

        self.assertEqual(final, "")
        self.assertEqual(reports, [], "لا تقرير حين لا يوجد ما يُتحقَّق منه")

    def test_collector_is_closed_after_the_round(self):
        """بعد الجولة لا يبقى جامع نشط في هذا الخيط."""
        fake_deps.AGENT_SCRIPT = scripted_turn(GENUINE_QUOTE)
        self.run_stream()
        from legal_agent import current_collector  # noqa: PLC0415

        self.assertIsNone(current_collector())

    def test_agent_failure_propagates(self):
        """فشل الوكيل يرتفع — ويُلتقط في `_sse_generator` ليُبلَّغ العميل."""
        fake_deps.AGENT_RAISE = RuntimeError("انقطاع الشبكة")
        with self.assertRaises(RuntimeError):
            self.run_stream()


# ==============================================================================
# ٥. بثّ SSE
# ==============================================================================


class TestSSE(MainTestBase):
    """إطارات SSE: الشكل، والترتيب، ومسار الفشل."""

    def test_frames_are_well_formed(self):
        """كل إطار `data: {...}\\n\\n` — العقد الذي تعتمد عليه الواجهة."""
        fake_deps.AGENT_SCRIPT = scripted_turn(GENUINE_QUOTE)
        frames = drain_sse(main._build_messages("صغ عقداً"))
        self.assertTrue(frames)
        events = parse_frames(frames)
        self.assertTrue(events)
        for event in events:
            self.assertIn("type", event)

    def test_citations_frame_is_emitted(self):
        fake_deps.AGENT_SCRIPT = scripted_turn(GENUINE_QUOTE)
        events = parse_frames(drain_sse(main._build_messages("صغ عقداً")))

        citation_events = [e for e in events if e["type"] == "citations"]
        self.assertEqual(len(citation_events), 1)
        report = citation_events[0]["report"]
        self.assertTrue(report["has_evidence"])
        self.assertEqual(report["evidence_count"], 1)

    def test_done_frame_carries_the_clean_document(self):
        fake_deps.AGENT_SCRIPT = scripted_turn(GENUINE_QUOTE)
        events = parse_frames(drain_sse(main._build_messages("صغ عقداً")))

        done = [e for e in events if e["type"] == "done"]
        self.assertEqual(len(done), 1)
        self.assertIn("عقد إيجار", done[0]["document"])
        self.assertNotIn(CITATIONS_BEGIN, done[0]["document"])

    def test_arabic_is_not_escaped(self):
        """`ensure_ascii=False` — وإلا وصل العربي مُرمَّزاً وغير مقروء."""
        fake_deps.AGENT_SCRIPT = scripted_turn(GENUINE_QUOTE)
        frames = drain_sse(main._build_messages("صغ عقداً"))
        joined = "".join(frames)
        self.assertIn("عقد إيجار", joined)
        self.assertNotIn("\\u0639", joined)

    def test_error_frame_on_agent_failure(self):
        """فشل الوكيل يُبلَّغ كإطار خطأ — لا يُترك الاتصال معلّقاً."""
        fake_deps.AGENT_RAISE = RuntimeError("انقطاع الشبكة")
        events = parse_frames(drain_sse(main._build_messages("صغ عقداً")))

        errors = [e for e in events if e["type"] == "error"]
        self.assertEqual(len(errors), 1)
        self.assertIn("انقطاع الشبكة", errors[0]["message"])

    def test_empty_final_yields_error_not_empty_done(self):
        """بلا نصّ: خطأ صريح بدل مستند فارغ يُعرض كأنه نجاح."""
        fake_deps.AGENT_SCRIPT = [{"content": ""}]
        events = parse_frames(drain_sse(main._build_messages("صغ عقداً")))
        self.assertNotIn("done", [e["type"] for e in events])
        self.assertIn("error", [e["type"] for e in events])


# ==============================================================================
# ٦. نقاط النهاية
# ==============================================================================


class TestEndpoints(MainTestBase):
    """`/generate` و`/chat` — الشكل الذي تتلقّاه الواجهة."""

    def test_generate_returns_streaming_response(self):
        fake_deps.AGENT_SCRIPT = scripted_turn(GENUINE_QUOTE)
        response = asyncio.run(
            main.generate(main.GenerateRequest(prompt="صغ عقداً", doc_type="عقد"))
        )
        self.assertEqual(response.media_type, "text/event-stream")
        self.assertEqual(response.headers["Cache-Control"], "no-cache, no-transform")
        self.assertEqual(response.headers["X-Accel-Buffering"], "no")

    def test_chat_returns_citations_alongside_the_answer(self):
        """/chat صار يُرجع التقرير أيضاً — إضافة لا كسر."""
        fake_deps.AGENT_SCRIPT = scripted_turn(GENUINE_QUOTE)
        payload = asyncio.run(main.chat_endpoint(main.ChatRequest(prompt="صغ عقداً")))

        self.assertIn("response", payload)
        self.assertIn("session_id", payload)
        self.assertIn("citations", payload)
        self.assertTrue(payload["citations"]["has_evidence"])
        self.assertNotIn(CITATIONS_BEGIN, payload["response"])

    def test_chat_flags_forged_quote(self):
        fake_deps.AGENT_SCRIPT = scripted_turn(FORGED_QUOTE)
        payload = asyncio.run(main.chat_endpoint(main.ChatRequest(prompt="صغ عقداً")))
        self.assertFalse(payload["citations"]["has_evidence"])

    def test_chat_keeps_session_memory(self):
        """الذاكرة بين الأدوار لم تتغيّر."""
        fake_deps.AGENT_SCRIPT = scripted_turn(GENUINE_QUOTE)
        asyncio.run(main.chat_endpoint(main.ChatRequest(prompt="أول", session_id="ج1")))
        asyncio.run(main.chat_endpoint(main.ChatRequest(prompt="ثانٍ", session_id="ج1")))

        history = main._get_history("ج1")
        # رسالة النظام + دور المستخدم + ردّ الوكيل + دور ثانٍ + ردّ ثانٍ
        self.assertGreaterEqual(len(history), 4)


# ==============================================================================
# ٧. نقل تغطية كانت في فحص خارجي
# ==============================================================================
# كانت هذه الحالات في فحص انحدار خارجي (`stub_check.py`) يستبدل `legal_agent`
# **بأكمله** بوهمي. وقد انتهى دوره: ما يغطّيه صار هنا، مع فارق أن الاختبار هنا
# يُشغّل `legal_agent` الحقيقي. لكن تفاصيله المفيدة نُقلت لا تُركت.


class TestExtractText(MainTestBase):
    """
    `_extract_text` — توحيد محتوى الرسالة.

    تبدو تافهة وهي ليست كذلك: Gemini يُرجع أحياناً **قائمة كتل محتوى** بدل نصّ،
    فتظهر الواجهة فارغة بلا أي خطأ ظاهر. ولهذا تُفحص الأشكال كلها.
    """

    def test_plain_string(self):
        message = fake_deps._FakeMessage(content="مرحباً")
        self.assertEqual(main._extract_text(message), "مرحباً")

    def test_content_blocks_as_gemini_returns_them(self):
        message = fake_deps._FakeMessage(
            content=[{"type": "text", "text": "أ"}, {"type": "text", "text": "ب"}]
        )
        self.assertEqual(main._extract_text(message), "أب")

    def test_list_of_strings(self):
        message = fake_deps._FakeMessage(content=["س", "ص"])
        self.assertEqual(main._extract_text(message), "سص")

    def test_none_content(self):
        message = fake_deps._FakeMessage(content=None)
        self.assertEqual(main._extract_text(message), "")

    def test_ignores_non_text_blocks(self):
        """كتل غير نصّية (صور، نداءات أدوات) لا تُحوَّل إلى نصّ."""
        message = fake_deps._FakeMessage(
            content=[{"type": "image", "data": "..."}, {"type": "text", "text": "نصّ"}]
        )
        self.assertEqual(main._extract_text(message), "نصّ")


class TestConfiguration(MainTestBase):
    """إعدادات تُقرأ عند الاستيراد — تتغيّر بلا اختبار فينكسر الإنتاج."""

    def test_all_five_tools_have_a_stage_label(self):
        """كل أداة لها وسم مرحلة — وإلا ظهر اسم خاطئ في الواجهة أثناء البحث."""
        for tool_name in (
            "search_uae_legislation",
            "search_drafting_style",
            "search_contract_clauses",
            "search_legal_notices",
            "search_poa_clauses",
        ):
            with self.subTest(tool=tool_name):
                self.assertIn(tool_name, main.TOOL_STAGE_LABELS)
                self.assertTrue(main.TOOL_STAGE_LABELS[tool_name])

    def test_document_type_hints_point_at_real_tools(self):
        """تلميحات أنواع المستندات تشير إلى أسماء أدوات موجودة فعلاً."""
        for doc_type, hint in main.DOC_TYPE_TOOL_HINT.items():
            with self.subTest(doc_type=doc_type):
                self.assertIn(hint, main.TOOL_STAGE_LABELS)

    def test_allowed_origins_is_a_list(self):
        """`ALLOWED_ORIGINS` يُقرأ عند الاستيراد — شكله قائمة لا نصّ."""
        self.assertIsInstance(main._allowed_origins, list)

    def test_cors_is_registered(self):
        self.assertIsNotNone(main.app.middleware)

    def test_recursion_limit_is_bounded(self):
        """حدّ خطوات الوكيل موجود ومعقول — بدونه تدور الحلقة بلا نهاية."""
        self.assertGreaterEqual(main.AGENT_RECURSION_LIMIT, 4)
        self.assertLessEqual(main.AGENT_RECURSION_LIMIT, 50)


if __name__ == "__main__":
    unittest.main(verbosity=2)
