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
import pathlib
import re
import unittest

from tests import fake_deps

# ⚠️ قبل استيراد main: يحجب fastapi وpydantic والتبعيات الثقيلة.
fake_deps.install()

import main  # noqa: E402
from citations import CITATIONS_BEGIN, CITATIONS_END  # noqa: E402
from revisions import STYLE_TARGET  # noqa: E402

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
        """
        قائمة المسارات كاملة — لا عددها.

        العدد الثابت كان هشّاً: كل مسار جديد يكسره بلا أن يقول شيئاً. أما
        تأكيد **المجموعة** فيجعل أي إضافة قراراً واعياً يُحدَّث هنا عن قصد،
        ويمنع حذف مسار أو تغيير طريقة بالخطأ.
        """
        routes = {(method, path) for method, path, _fn, _kw in main.app.routes}
        self.assertEqual(
            routes,
            {
                ("GET", "/"),
                ("GET", "/health"),
                ("POST", "/generate"),
                ("POST", "/chat"),
                ("POST", "/revisions"),
                ("GET", "/revisions/stats"),
                ("GET", "/archive/overview"),
                ("GET", "/archive/documents"),
            },
            "تغيّرت قائمة المسارات — أضِف الجديد هنا عن قصد",
        )

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
        """المراحل تُبثّ كما كانت: تحليل ← أداة ← أدلّة ← صياغة ← تحقّق."""
        fake_deps.AGENT_SCRIPT = scripted_turn(GENUINE_QUOTE)
        stages = [payload for kind, payload in self.run_stream() if kind == "stage"]
        messages = [stage.message for stage in stages]

        self.assertEqual(messages[0], main.STAGE_ANALYSING)
        self.assertIn(main.TOOL_STAGE_LABELS["search_contract_clauses"], messages)
        self.assertIn(main.STAGE_EVIDENCE_FOUND, messages)
        self.assertIn(main.STAGE_DRAFTING, messages)
        self.assertIn(main.STAGE_VERIFYING, messages)

    def test_each_stage_carries_a_stable_key(self):
        """
        🔑 المفتاح الآلي — وعليه يُبنى مشهد «فريق المكتب».

        الواجهة تقرّر بالمفتاح لا بالنصّ العربي. ولو رُبطت بالنصّ لانكسر
        المشهد **بصمت** عند أول تعديل صياغة — وهو العطب نفسه الذي أصلحناه في
        الأدوات الخمس (انحراف نسخة عن أخرى بلا خطأ ظاهر).
        """
        fake_deps.AGENT_SCRIPT = scripted_turn(GENUINE_QUOTE)
        keys = [payload.key for kind, payload in self.run_stream() if kind == "stage"]

        self.assertEqual(keys[0], main.KEY_INTAKE)
        self.assertIn(main.TOOL_STAGE_KEYS["search_contract_clauses"], keys)
        self.assertIn(main.KEY_EVIDENCE, keys)
        self.assertIn(main.KEY_DRAFTING, keys)
        self.assertIn(main.KEY_VERIFYING, keys)

    def test_verifying_stage_precedes_the_report(self):
        """المدقّق يظهر **قبل** وصول نتيجته — لا بعده."""
        fake_deps.AGENT_SCRIPT = scripted_turn(GENUINE_QUOTE)
        kinds = [kind for kind, _payload in self.run_stream()]
        verifying_at = kinds.index("stage")  # أول مرحلة = الاستقبال
        self.assertLess(kinds.index("citations"), kinds.index("final"))
        self.assertIsNotNone(verifying_at)

    def test_tool_key_map_covers_every_stage_label(self):
        """كل أداة لها وسم مرحلة **ومفتاح** — ولا واحدة بلا الآخر."""
        self.assertEqual(set(main.TOOL_STAGE_KEYS), set(main.TOOL_STAGE_LABELS))

    def test_tool_keys_are_unique(self):
        """لكل أداة مفتاحها الخاص — وإلا تحرّكت شخصيتان بلا سبب."""
        keys = list(main.TOOL_STAGE_KEYS.values())
        self.assertEqual(len(keys), len(set(keys)))

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

    def test_stage_frames_carry_the_machine_key(self):
        """
        إطار المرحلة يحمل **المفتاح الآلي** مع النصّ.

        الواجهة تحتاجه لتعرف أي شخصية تعمل الآن في مشهد المكتب. والنصّ وحده
        لا يكفي: يتغيّر بتغيّر الصياغة، والمفتاح ثابت.
        """
        fake_deps.AGENT_SCRIPT = scripted_turn(GENUINE_QUOTE)
        events = parse_frames(drain_sse(main._build_messages("صغ عقداً")))
        stage_events = [event for event in events if event["type"] == "stage"]

        self.assertTrue(stage_events)
        for event in stage_events:
            self.assertIn("stage", event)
            self.assertTrue(event["stage"], "مفتاح فارغ")
            self.assertIn("message", event)

        keys = [event["stage"] for event in stage_events]
        self.assertIn(main.KEY_INTAKE, keys)
        self.assertIn(main.KEY_VERIFYING, keys)
        self.assertIn(main.TOOL_STAGE_KEYS["search_contract_clauses"], keys)

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
# ٧. جمع تصحيحات المحامي
# ==============================================================================

GENERATED = "البند الأول: يلتزم الطرف الثاني بسداد مبلغ عشرين ألف درهم."
CORRECTED = (
    "البند الأول: يلتزم الطرف الثاني بسداد مبلغ خمسة وعشرين ألف درهم "
    "خلال ثلاثين يوماً من تاريخ التوقيع."
)


class TestRevisionRoutes(MainTestBase):
    """مسارَان جديدان — وكلاهما محمي."""

    def test_routes_are_registered(self):
        routes = {(method, path) for method, path, _fn, _kw in main.app.routes}
        self.assertIn(("POST", "/revisions"), routes)
        self.assertIn(("GET", "/revisions/stats"), routes)

    def test_both_require_auth(self):
        """الإحصاءات تكشف حجم المكتب — تُحمى كغيرها."""
        by_key = {
            (method, path): kw.get("dependencies")
            for method, path, _fn, kw in main.app.routes
        }
        self.assertTrue(by_key[("POST", "/revisions")])
        self.assertTrue(by_key[("GET", "/revisions/stats")])

    def test_health_announces_revision_capture(self):
        self.assertTrue(asyncio.run(main.health())["revision_capture"])


class TestSaveRevision(MainTestBase):
    """`POST /revisions` — حفظ الزوج وقياسه."""

    def test_saves_a_row_with_the_expected_fields(self):
        payload = asyncio.run(
            main.save_revision(
                main.RevisionRequest(
                    generated_text=GENERATED,
                    corrected_text=CORRECTED,
                    doc_type="عقد",
                    prompt="وقائع",
                    session_id="ج1",
                )
            )
        )

        rows = fake_deps.FAKE_SUPABASE.inserted_into(main.REVISIONS_TABLE)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["generated_text"], GENERATED)
        self.assertEqual(rows[0]["corrected_text"], CORRECTED)
        self.assertEqual(rows[0]["doc_type"], "عقد")
        self.assertEqual(rows[0]["session_id"], "ج1")

        self.assertTrue(payload["saved"])
        self.assertGreater(payload["edit_ratio"], 0.0)
        self.assertLessEqual(payload["edit_ratio"], 1.0)
        self.assertIn("quality_band", payload)
        self.assertGreater(payload["word_count"], 0)

    def test_stored_row_has_no_embedding(self):
        """
        🔑 الجدول ليس جزءاً من قاعدة المعرفة.

        لو ظهر `embedding` في الصفّ المُدرَج لكان معناه أن التصحيحات تُضمَّن
        وتدخل الاسترجاع — فتعود المسودّة المولَّدة في جولة لاحقة كـ«سياق
        موثوق» وتصير الهلوسة حقيقة مؤرشفة. وهذا الفحص يحمي ذلك القرار.
        """
        asyncio.run(
            main.save_revision(
                main.RevisionRequest(generated_text=GENERATED, corrected_text=CORRECTED)
            )
        )
        row = fake_deps.FAKE_SUPABASE.inserted_into(main.REVISIONS_TABLE)[0]
        self.assertNotIn("embedding", row)
        self.assertEqual(main.REVISIONS_TABLE, "draft_revisions")

    def test_rejects_unchanged_revision(self):
        """تصحيح بلا تغيير: ٤٠٠، ولا يُحفظ شيء."""
        with self.assertRaises(main.HTTPException) as ctx:
            asyncio.run(
                main.save_revision(
                    main.RevisionRequest(generated_text=GENERATED, corrected_text=GENERATED)
                )
            )
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertEqual(fake_deps.FAKE_SUPABASE.inserted_into(main.REVISIONS_TABLE), [])

    def test_rejects_empty_corrected(self):
        with self.assertRaises(main.HTTPException) as ctx:
            asyncio.run(
                main.save_revision(
                    main.RevisionRequest(generated_text=GENERATED, corrected_text="   ")
                )
            )
        self.assertEqual(ctx.exception.status_code, 400)

    def test_missing_table_gives_an_actionable_message(self):
        """
        الجدول غير موجود أشيع سبب للفشل.

        و«relation does not exist» لا تدلّ المحامي على المطلوب، فتسمّي
        الرسالة القسم الدقيق في `schema.sql`.
        """
        fake_deps.FAKE_SUPABASE.raise_on_table.add(main.REVISIONS_TABLE)

        with self.assertRaises(main.HTTPException) as ctx:
            asyncio.run(
                main.save_revision(
                    main.RevisionRequest(generated_text=GENERATED, corrected_text=CORRECTED)
                )
            )

        self.assertEqual(ctx.exception.status_code, 503)
        self.assertIn("schema.sql", ctx.exception.detail)
        self.assertIn("١٠", ctx.exception.detail)

    def test_other_storage_errors_are_reported_plainly(self):
        """خطأ آخر يُعاد نصّه — لا يُخفى وراء رسالة الجدول الناقص."""
        message = main._revision_storage_error(RuntimeError("انتهت المهلة"))
        self.assertIn("انتهت المهلة", message)
        self.assertNotIn("schema.sql", message)


class TestRevisionStats(MainTestBase):
    """`GET /revisions/stats` — التقدّم نحو تقليد الأسلوب."""

    def test_empty_database(self):
        result = asyncio.run(main.revision_stats())
        self.assertEqual(result["count"], 0)
        self.assertEqual(result["average_edit_ratio"], 0.0)
        self.assertEqual(result["target"], STYLE_TARGET)
        self.assertEqual(result["progress_percent"], 0.0)

    def test_summarizes_stored_ratios(self):
        fake_deps.FAKE_SUPABASE.set_table_rows(
            main.REVISIONS_TABLE,
            [{"edit_ratio": 0.05}, {"edit_ratio": 0.15}, {"edit_ratio": None}],
        )
        result = asyncio.run(main.revision_stats())

        self.assertEqual(result["count"], 2, "الصفّ بلا نسبة يجب ألّا يُحسب")
        self.assertAlmostEqual(result["average_edit_ratio"], 0.1, places=3)
        self.assertEqual(sum(result["distribution"].values()), 2)

    def test_stats_only_selects_the_ratio_column(self):
        """
        الإحصاء يجلب عمود النسبة وحده لا المسودّات.

        ولو جلب النصوص لصارت الحمولة ضخمة مع كل فتح للوحة — وهي بيانات لا
        يحتاجها الحساب أصلاً.
        """
        asyncio.run(main.revision_stats())
        table_calls = fake_deps.FAKE_SUPABASE.table_calls
        self.assertTrue(table_calls)
        _name, op, columns = table_calls[-1]
        self.assertEqual(op, "select")
        self.assertEqual(columns, "edit_ratio")

    def test_missing_table_gives_an_actionable_message(self):
        fake_deps.FAKE_SUPABASE.raise_on_table.add(main.REVISIONS_TABLE)
        with self.assertRaises(main.HTTPException) as ctx:
            asyncio.run(main.revision_stats())
        self.assertEqual(ctx.exception.status_code, 503)
        self.assertIn("schema.sql", ctx.exception.detail)


# ==============================================================================
# ٨. نقل تغطية كانت في فحص خارجي
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


class TestArchiveEndpoints(MainTestBase):
    """
    نقطتا الأرشيف — وهما ما يُغني لوحة القيادة والمكتبة عن الأرقام المكتوبة.
    ========================================================================
    كانت الصفحتان تعرضان «١٢٤٨ مستنداً» و«٨٥٣٠ سنداً» **مكتوبة بخط اليد**،
    و«من أرشيف Qdrant» وهو **خطأ واقعي**: الأرشيف في Supabase/pgvector.

    وهذا الفحص يثبّت أن ما يُعرض يأتي من قاعدة البيانات فعلاً.
    """

    def setUp(self) -> None:
        super().setUp()
        self.supabase = fake_deps.FAKE_SUPABASE

    # -- GET /archive/overview ------------------------------------------------

    def test_overview_returns_all_five_families_even_when_empty(self):
        """العائلات الخمس تُعاد كلها — و«٠» أصدق من الإخفاء."""
        payload = asyncio.run(main.archive_overview())
        self.assertEqual(
            [item["key"] for item in payload["families"]],
            [key for key, _ in main.ARCHIVE_FAMILIES],
        )
        self.assertTrue(all(item["documents"] == 0 for item in payload["families"]))
        self.assertEqual(payload["documents"], 0)
        self.assertEqual(payload["chunks"], 0)

    def test_overview_sums_the_families(self):
        self.supabase.set_rows(
            "archive_overview",
            [
                {"family_key": "legislation", "documents": 12, "chunks": 900},
                {"family_key": "contracts", "documents": 3, "chunks": 40},
            ],
        )
        payload = asyncio.run(main.archive_overview())
        self.assertEqual(payload["documents"], 15)
        self.assertEqual(payload["chunks"], 940)

    def test_overview_fills_absent_families_with_zero(self):
        """عائلة غابت من ردّ الخادم تُعرض بصفر — لا تُحذف من اللوحة."""
        self.supabase.set_rows(
            "archive_overview",
            [{"family_key": "poa", "documents": 2, "chunks": 7}],
        )
        by_key = {
            item["key"]: item
            for item in asyncio.run(main.archive_overview())["families"]
        }
        self.assertEqual(len(by_key), 5)
        self.assertEqual(by_key["poa"]["documents"], 2)
        self.assertEqual(by_key["notices"]["documents"], 0)

    def test_overview_pairs_a_machine_key_with_an_arabic_label(self):
        """
        مفتاح آلي **و** وسم عربي — كما في مفاتيح المراحل.

        ولو رُبطت الواجهة بالوسم العربي لانكسرت التصفية بصمت عند أول تعديل.
        """
        for item in asyncio.run(main.archive_overview())["families"]:
            with self.subTest(key=item["key"]):
                self.assertRegex(item["key"], r"^[a-z_]+$")
                self.assertTrue(item["label"])
                self.assertNotRegex(item["label"], r"^[a-z_]+$")

    def test_overview_missing_function_names_the_section_to_run(self):
        """رسالة تسمّي القسم المطلوب — كما فعلت رسالة جدول التصحيحات."""
        self.supabase.raise_on_rpc.add("archive_overview")
        with self.assertRaises(main.HTTPException) as caught:
            asyncio.run(main.archive_overview())
        self.assertEqual(caught.exception.status_code, 503)
        self.assertIn("القسم ١١", caught.exception.detail)

    def test_overview_calls_exactly_one_rpc(self):
        asyncio.run(main.archive_overview())
        self.assertEqual(self.supabase.rpc_names(), ["archive_overview"])

    # -- GET /archive/documents -----------------------------------------------

    def seed_documents(self) -> None:
        self.supabase.set_rows(
            "archive_documents",
            [
                {
                    "document_name": "قانون المعاملات المدنية",
                    "document_type": "تشريع",
                    "family_key": "legislation",
                    "chunks": 420,
                    "added_at": "2026-09-01T10:00:00Z",
                },
                {
                    "document_name": "عقد إيجار سكني",
                    "document_type": "عقود عقارية",
                    "family_key": "contracts",
                    "chunks": 18,
                    "added_at": "2026-09-02T10:00:00Z",
                },
            ],
        )

    def test_documents_group_by_name_with_their_chunk_count(self):
        self.seed_documents()
        payload = asyncio.run(main.archive_documents())
        self.assertEqual(payload["count"], 2)
        names = [item["document_name"] for item in payload["documents"]]
        self.assertIn("قانون المعاملات المدنية", names)
        self.assertEqual(payload["documents"][0]["chunks"], 420)

    def test_documents_resolve_the_arabic_family_label(self):
        """الواجهة لا تُترجم المفاتيح — الخادم يُرسل الوسم معها."""
        self.seed_documents()
        payload = asyncio.run(main.archive_documents())
        labels = {item["family"]: item["family_label"] for item in payload["documents"]}
        self.assertEqual(labels["legislation"], "التشريعات والأحكام")
        self.assertEqual(labels["contracts"], "العقود والاتفاقيات")

    def test_documents_pass_empty_filters_as_null(self):
        """
        الفراغ يُحوَّل إلى `null` لا إلى `''`.

        ودالّة SQL تعامل الاثنين سواءً (`coalesce`)، لكن `null` هو ما تعنيه
        «لا تصفية» — ويمنع `ilike '%%'` من مطابقة كل شيء بالخطأ.
        """
        asyncio.run(main.archive_documents())
        _name, params = self.supabase.last_call()
        self.assertIsNone(params["search_term"])
        self.assertIsNone(params["family_filter"])

    def test_documents_trim_the_search_term(self):
        asyncio.run(main.archive_documents(search="  إيجار  "))
        _name, params = self.supabase.last_call()
        self.assertEqual(params["search_term"], "إيجار")

    def test_documents_pass_a_known_family_through(self):
        asyncio.run(main.archive_documents(family="notices"))
        _name, params = self.supabase.last_call()
        self.assertEqual(params["family_filter"], "notices")

    def test_documents_reject_an_unknown_family_loudly(self):
        """
        عائلة مجهولة تُرفض ولا تُتجاهَل.

        ولو تُوجّهت التصفية الخاطئة إلى «لا تصفية» لعاد الأرشيف كاملاً **وبدا
        صحيحاً** — وهي أسوأ من خطأ صريح.
        """
        with self.assertRaises(main.HTTPException) as caught:
            asyncio.run(main.archive_documents(family="legislationn"))
        self.assertEqual(caught.exception.status_code, 400)
        self.assertIn("legislationn", caught.exception.detail)
        self.assertEqual(self.supabase.calls, [], "لم يكن ينبغي نداء قاعدة البيانات")

    def test_documents_clamp_the_row_limit(self):
        for requested, expected in ((0, 1), (-5, 1), (50, 50), (9999, main.ARCHIVE_MAX_ROWS)):
            with self.subTest(requested=requested):
                self.supabase.reset()
                asyncio.run(main.archive_documents(limit=requested))
                _name, params = self.supabase.last_call()
                self.assertEqual(params["max_rows"], expected)

    def test_documents_report_truncation(self):
        """
        والقَصّ يُعلَن ولا يُسكت عنه.

        ولو سكت، لأوهمت الصفحة أن ما تراه هو الأرشيف كله — وهو عين ما كانت
        تفعله الأرقام المكتوبة بخط اليد.
        """
        self.supabase.set_rows(
            "archive_documents",
            [
                {"document_name": f"مستند {i}", "family_key": "drafts", "chunks": 1}
                for i in range(5)
            ],
        )
        payload = asyncio.run(main.archive_documents(limit=5))
        self.assertTrue(payload["truncated"])
        self.assertEqual(payload["limit"], 5)

    def test_documents_not_truncated_when_fewer_than_the_limit(self):
        self.seed_documents()
        payload = asyncio.run(main.archive_documents(limit=50))
        self.assertFalse(payload["truncated"])

    def test_documents_tolerate_null_columns_from_the_database(self):
        """قيم `null` في القاعدة لا تُسقط الصفحة — تُعرض فراغاً."""
        self.supabase.set_rows(
            "archive_documents",
            [{"document_name": None, "document_type": None, "family_key": None, "chunks": None}],
        )
        item = asyncio.run(main.archive_documents())["documents"][0]
        self.assertEqual(item["document_name"], "")
        self.assertEqual(item["document_type"], "")
        self.assertEqual(item["family_label"], "")
        self.assertEqual(item["chunks"], 0)

    def test_documents_missing_function_names_the_section_to_run(self):
        self.supabase.raise_on_rpc.add("archive_documents")
        with self.assertRaises(main.HTTPException) as caught:
            asyncio.run(main.archive_documents())
        self.assertEqual(caught.exception.status_code, 503)
        self.assertIn("القسم ١١", caught.exception.detail)


class TestOfficeSceneContract(MainTestBase):
    """
    مفاتيح مشهد المكتب في الواجهة تطابق مفاتيح الخادم.
    ========================================================================
    ⚠️ هذا الفحص **يعبر حدّ اللغتين** عن قصد، وهو من أهمّ ما في هذا الملف.

    السبب أن العطب الذي يمنعه **صامت تماماً**: لو أُضيفت مرحلة في `main.py`
    ولم تُضف شخصيتها في الواجهة، لما ظهر أي خطأ — تبقى الشخصية نائمة أبداً
    ولا يلاحظ أحد. وهو النوع نفسه من الانحراف الصامت الذي أصلحناه في الأدوات
    الخمس (سقوط أداة من نسخة موجّه واحدة بلا خطأ ظاهر).

    ولذلك يُفحص الاتجاهان: كل مرحلة لها شخصية، ولا شخصية بلا مرحلة.
    """

    SCENE = (
        pathlib.Path(__file__).resolve().parent.parent
        / "frontend"
        / "components"
        / "office-scene.tsx"
    )

    def setUp(self) -> None:
        super().setUp()
        self.source = self.SCENE.read_text(encoding="utf-8")

    def backend_stages(self) -> set:
        """كل مفتاح مرحلة يبثّه الخادم فعلاً."""
        return set(main.TOOL_STAGE_KEYS.values()) | {
            main.KEY_INTAKE,
            main.KEY_EVIDENCE,
            main.KEY_DRAFTING,
            main.KEY_VERIFYING,
            main.KEY_POLISH,
            main.KEY_SEAL,
        }

    def stage_map(self) -> dict:
        """جدول `STAGE_CHARACTER` من ملف المشهد: مرحلة ← شخصية."""
        block = re.search(
            r"const STAGE_CHARACTER[^{]*\{(.*?)\n\};", self.source, re.DOTALL
        )
        self.assertIsNotNone(block, "لم يُعثر على STAGE_CHARACTER في المشهد")
        return dict(re.findall(r'(\w+):\s*"(\w+)"', block.group(1)))

    def characters(self) -> set:
        """
        مفاتيح الشخصيات في `TEAM`.

        ويُقرأ من كتلة `TEAM` وحدها لا من الملف كله: فـ`key={worker.key}` في
        JSX ليس تعريف شخصية، ولو قرأناه لظهرت مفاتيح وهمية.
        """
        block = re.search(r"const TEAM[^=]*=\s*\[(.*?)\n\];", self.source, re.DOTALL)
        self.assertIsNotNone(block, "لم يُعثر على TEAM في المشهد")
        return set(re.findall(r'key:\s*"(\w+)"', block.group(1)))

    def test_scene_file_is_present(self):
        self.assertTrue(self.SCENE.exists(), f"مفقود: {self.SCENE}")

    def test_every_backend_stage_is_mapped(self):
        """كل مرحلة يبثّها الخادم لها مدخل في الجدول — وإلا نائمة أبداً."""
        missing = self.backend_stages() - set(self.stage_map())
        self.assertEqual(missing, set(), f"مراحل بلا شخصية: {sorted(missing)}")

    def test_no_stage_is_mapped_without_a_backend_stage(self):
        """ولا مدخل لمرحلة لا يبثّها الخادم — وإلا لم تتحرّك قطّ."""
        orphans = set(self.stage_map()) - self.backend_stages()
        self.assertEqual(orphans, set(), f"مراحل لا يبثّها الخادم: {sorted(orphans)}")

    def test_every_character_owns_at_least_one_stage(self):
        """كل شخصية معرَّفة لها مرحلة — وإلا فلا تظهر أبداً."""
        idle = self.characters() - set(self.stage_map().values())
        self.assertEqual(idle, set(), f"شخصيات بلا مرحلة: {sorted(idle)}")

    def test_no_stage_maps_to_an_unknown_character(self):
        """ولا مرحلة تُوجَّه إلى شخصية غير معرَّفة — وإلا اختفت الحركة."""
        unknown = set(self.stage_map().values()) - self.characters()
        self.assertEqual(unknown, set(), f"شخصيات غير معرَّفة: {sorted(unknown)}")

    def test_scene_has_a_name_and_role_for_every_character(self):
        """لكل شخصية اسم ودور معروضان — وهذا ما طلبه المستخدم صراحةً."""
        count = len(self.characters())
        self.assertEqual(len(re.findall(r'name:\s*"', self.source)), count)
        self.assertEqual(len(re.findall(r'role:\s*"', self.source)), count)

    def test_the_team_uses_the_names_that_already_exist_in_the_system(self):
        """
        ⚠️ الأسماء تأتي من `smart_office.py` و`office_test.py` لا من خيال أحد.

        اخترعتُ سابقاً تسعة أسماء فرفضها المستخدم: الفريق في نظامه **خمسة**
        بأسمائهم. وهذا الفحص يمنع عودة الاختراع — ولو أُضيف اسم في الكود
        وليس في `smart_office.py` لظهر هنا.
        """
        expected_names = {
            "أمين المكتبة",
            "مُسوَدَّة أفندي",
            "المفتش ثُغرة",
            "سيبويه المُكشّر",
            "المعلم أبو الختم",
        }
        found = set(re.findall(r'name:\s*"([^"]+)"', self.source))
        self.assertEqual(found, expected_names)

    def test_scene_uses_logical_spacing_for_rtl(self):
        """
        المشهد يستخدم خصائص منطقية لا فيزيائية.

        التطبيق RTL بالكامل، و`ml-`/`left-` تُنتج الفراغ في الجهة الخطأ.
        """
        for physical in ("ml-", "mr-", "pl-", "pr-", "left-", "right-"):
            self.assertNotIn(physical, self.source, f"خاصية فيزيائية في ملف RTL: {physical}")

    def test_scene_draws_no_untrusted_html(self):
        """لا `dangerouslySetInnerHTML` في المشهد — كبقية الواجهة."""
        self.assertNotIn("dangerouslySetInnerHTML", self.source)

    def test_character_keys_do_not_collide_with_stage_keys(self):
        """
        مفاتيح الشخصيات مختلفة عن مفاتيح المراحل.

        لو تشابهت لالتبس الجدول: `drafting` مرحلة، ولو كانت كذلك شخصية لكان
        `STAGE_CHARACTER[drafting] == drafting` وهو التباس لا خطأ صريح.
        """
        self.assertEqual(self.characters() & self.backend_stages(), set())


if __name__ == "__main__":
    unittest.main(verbosity=2)
