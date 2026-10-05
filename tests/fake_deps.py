"""
وحدات وهمية للتبعيات الثقيلة — لتشغيل الكود الحقيقي بلا تثبيت شيء.
=============================================================================

الفكرة
------
`legal_agent.py` يستورد `supabase` و`sentence_transformers` و`langchain_google_genai`
و`langgraph`. وتثبيت هذه الحزم ثقيل جداً (torch وحده ~800 MB، والنموذج 2.2 GB)،
فلو توقّف الاختبار عليها لما شُغِّل أبداً.

فهذه الوحدة **تحجب التبعيات لا الكود**: تُسجّل وحدات وهمية في `sys.modules`
قبل استيراد `legal_agent`، فيُحمَّل هو **حقيقياً** — بأدواته وموجّهه ومنطقه —
بينما تُستبدل الطبقة الخارجية وحدها.

الفرق عن الاختبارات السابقة
---------------------------
كانت الاختبارات القديمة تستبدل `legal_agent` **بأكمله** بوهمي، فتختبر `main.py`
فقط. وهذه تفعل العكس: تُبقي `legal_agent` حقيقياً وتُوهم ما تحته. والسبب أن
الخطوة الحالية تُعدّل **أدوات الاسترجاع نفسها**، فيجب أن يكون تحت الاختبار هو
الكود الحقيقي لا نسخة منه.

⚠️ **الوحدات تُسجَّل في `sys.modules` ولا تُكتب على القرص** — فلا ملفات مؤقتة
تُترك خلفنا ولا تعارض مع استيرادات أخرى.

الاستخدام
---------
    from tests import fake_deps
    fake_deps.install()          # قبل استيراد legal_agent
    import legal_agent

و`install()` آمنة عند تكرارها.
"""

from __future__ import annotations

import os
import sys
import types
from typing import Any

#: أبعاد متجه التضمين — مطابقة لـ `intfloat/multilingual-e5-large` ولعمود
#: `vector(1024)` في `schema.sql`. لو اختلفا لفشل الاسترجاع في الإنتاج فقط.
EMBEDDING_DIM = 1024


# ==============================================================================
# ١. أدوات مساعدة
# ==============================================================================


def _register(name: str, parent: str | None = None, **attrs: Any) -> types.ModuleType:
    """يُسجّل وحدة وهمية في `sys.modules`، ويربطها بأبيها إن وُجد."""
    module = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(module, key, value)
    sys.modules[name] = module
    if parent is not None:
        setattr(sys.modules[parent], name.rsplit(".", 1)[-1], module)
    return module


# ==============================================================================
# ٢. متجهات ونموذج تضمين وهميان
# ==============================================================================


class FakeVector(list):
    """
    يُقلّد مصفوفة NumPy التي يُعيدها `SentenceTransformer.encode`.

    يحمل `tolist()` لأن `encode_query` يستدعيها — ولو أعادت الوهمية قائمة
    عادية لانكسر الكود الحقيقي عند أول استدعاء.
    """

    def tolist(self) -> list[float]:
        return list(self)


class FakeEmbedder:
    """
    يقلّد `SentenceTransformer` ويسجّل كل نصّ ضُمِّن.

    التسجيل ضروري: البادئة `"query: "` شرط لعمل نموذج e5، وإغفالها يُفسد
    جودة الاسترجاع **بصمت** بلا أي خطأ. فالاختبار يفحصها في النصّ المُضمَّن
    نفسه، لا في الكود.
    """

    instances: list["FakeEmbedder"] = []

    def __init__(self, model_name: str = "") -> None:
        self.model_name = model_name
        self.encoded: list[str] = []
        FakeEmbedder.instances.append(self)

    def encode(self, text: str) -> FakeVector:
        self.encoded.append(text)
        return FakeVector([0.01] * EMBEDDING_DIM)

    @classmethod
    def last(cls) -> "FakeEmbedder":
        """آخر نموذج أُنشئ — للوصول إليه من الاختبار."""
        return cls.instances[-1]

    @classmethod
    def reset(cls) -> None:
        cls.instances.clear()


# ==============================================================================
# ٣. عميل Supabase وهمي
# ==============================================================================


class FakeSupabase:
    """
    يقلّد `supabase.Client`، ويسجّل نداءات RPC ويعيد صفوفاً مُعدّة مسبقاً.

    التسجيل هو ما يجعل **اختبار الانحدار** ممكناً: نُثبت أن كل أداة تنادي
    دالة RPC الصحيحة، بنفس العتبة ونفس الحدّ — فإعادة هيكلة الأدوات الخمس
    في دالة واحدة هي بالضبط نوع التغيير الذي يُسقِط أداة بصمت.
    """

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []
        self.rows: dict[str, list[dict]] = {}
        # -- الجداول (للتصحيحات ونحوها) -------------------------------------
        self.table_calls: list[tuple[str, str, Any]] = []
        self.inserted: dict[str, list[dict]] = {}
        self.table_rows: dict[str, list[dict]] = {}
        #: أسماء جداول ترفع عندها العمليات استثناءً — لاختبار مسار الجدول الناقص.
        self.raise_on_table: set[str] = set()

    # -- RPC ----------------------------------------------------------------

    def set_rows(self, rpc_name: str, rows: list[dict]) -> None:
        """يُحدّد الصفوف التي تُعيدها دالة RPC معيّنة."""
        self.rows[rpc_name] = rows

    def set_rows_for_all(self, rows: list[dict]) -> None:
        """يُحدّد نفس الصفوف لكل دوال RPC — لتسهيل اختبارات العزل."""
        for name in (
            "match_legal_documents",
            "match_legal_drafts",
            "match_legal_contracts",
            "match_legal_notices",
            "match_legal_poa",
        ):
            self.rows[name] = rows

    def rpc(self, name: str, params: dict) -> "_FakeRPCBuilder":
        return _FakeRPCBuilder(self, name, params)

    # -- الجداول ------------------------------------------------------------

    def table(self, name: str) -> "_FakeTableBuilder":
        return _FakeTableBuilder(self, name)

    def set_table_rows(self, table_name: str, rows: list[dict]) -> None:
        """يُحدّد الصفوف التي يُعيدها `select` على جدول معيّن."""
        self.table_rows[table_name] = rows

    def inserted_into(self, table_name: str) -> list[dict]:
        """الصفوف المُدرَجة في جدول — لفحص ما حُفظ فعلاً."""
        return self.inserted.get(table_name, [])

    def reset(self) -> None:
        self.calls.clear()
        self.rows.clear()
        self.table_calls.clear()
        self.inserted.clear()
        self.table_rows.clear()
        self.raise_on_table.clear()

    # -- مساعدات للاختبار ----------------------------------------------------

    def last_call(self) -> tuple[str, dict]:
        """آخر نداء RPC: (اسم الدالة، معاملاتها)."""
        return self.calls[-1]

    def rpc_names(self) -> list[str]:
        """أسماء دوال RPC بالترتيب — لفحص التوجيه."""
        return [name for name, _ in self.calls]


class _FakeRPCBuilder:
    """يبني نداء RPC ولا ينفّذه إلا عند `execute()` — كما في العميل الحقيقي."""

    def __init__(self, owner: FakeSupabase, name: str, params: dict) -> None:
        self._owner = owner
        self._name = name
        self._params = params

    def execute(self) -> types.SimpleNamespace:
        self._owner.calls.append((self._name, self._params))
        return types.SimpleNamespace(data=self._owner.rows.get(self._name, []))


class _FakeTableBuilder:
    """
    يقلّد `client.table(name).insert(...).execute()` و`select(...).execute()`.

    يبني العملية ثم ينفّذها عند `execute()`، كما يفعل العميل الحقيقي — فلو
    نسي أحدهم `execute()` في الكود لم يُسجَّل شيء، وهو خطأ صامت في Supabase
    الحقيقي أيضاً. فالوهمي يحاكيه في هذه النقطة لا يتساهل فيها.
    """

    def __init__(self, owner: FakeSupabase, name: str) -> None:
        self._owner = owner
        self._name = name
        self._op: str | None = None
        self._payload: Any = None

    def insert(self, row: Any) -> "_FakeTableBuilder":
        self._op = "insert"
        self._payload = row
        return self

    def select(self, columns: str = "*") -> "_FakeTableBuilder":
        self._op = "select"
        self._payload = columns
        return self

    def execute(self) -> types.SimpleNamespace:
        self._owner.table_calls.append((self._name, self._op or "", self._payload))

        if self._name in self._owner.raise_on_table:
            raise RuntimeError(
                f'relation "public.{self._name}" does not exist (42P01)'
            )

        if self._op == "insert":
            self._owner.inserted.setdefault(self._name, []).append(self._payload)
            return types.SimpleNamespace(data=[self._payload])

        return types.SimpleNamespace(data=self._owner.table_rows.get(self._name, []))


#: العميل الوحيد الذي يُعيده `create_client` — يُعدّه الاختبار ويقرأ منه.
FAKE_SUPABASE = FakeSupabase()


# ==============================================================================
# ٤. وحدات langchain / langgraph الوهمية
# ==============================================================================


class _FakeMessage:
    """يقلّد رسائل langchain بالحدّ الأدنى الذي يستعمله المشروع."""

    type = "generic"

    def __init__(self, content: Any = "", **kwargs: Any) -> None:
        self.content = content
        self.tool_calls = kwargs.get("tool_calls") or []
        for key, value in kwargs.items():
            setattr(self, key, value)


class _FakeTool:
    """
    يقلّد الأداة الناتجة عن `@tool`.

    مهم: يبقى **قابلاً للنداء كدالة عادية**، لأن الاختبارات تستدعي جسم الأداة
    مباشرة. وفي الوقت نفسه يحمل `name` و`description` و`invoke` كما تحملها
    الأداة الحقيقية، فيعمل الكود الذي يعتمد عليها.
    """

    def __init__(self, func: Any) -> None:
        self._func = func
        self.name = func.__name__
        self.description = (func.__doc__ or "").strip()
        self.func = func
        self.__doc__ = func.__doc__
        self.__name__ = func.__name__

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return self._func(*args, **kwargs)

    def invoke(self, payload: Any, config: Any = None) -> Any:
        if isinstance(payload, dict):
            return self._func(**payload)
        return self._func(payload)


def _tool_decorator(func: Any = None, **kwargs: Any) -> Any:
    """يقلّد `@tool` بصيغتَيه: `@tool` و`@tool(...)`."""
    if func is None:
        return lambda inner: _FakeTool(inner)
    return _FakeTool(func)


class _FakeStateGraph:
    """يقلّد `StateGraph` بلا تنفيذ فعلي — يكفي أن يُبنى ويُصرَّف."""

    def __init__(self, state: Any = None) -> None:
        self.state = state
        self.nodes: dict[str, Any] = {}
        self.edges: list[tuple[Any, Any]] = []

    def add_node(self, name: str, fn: Any = None) -> None:
        self.nodes[name] = fn

    def add_edge(self, start: Any, end: Any) -> None:
        self.edges.append((start, end))

    def add_conditional_edges(self, start: Any, condition: Any, *a: Any) -> None:
        self.edges.append((start, condition))

    def compile(self) -> "_FakeCompiledGraph":
        return _FakeCompiledGraph(self)


#: النصّ البرمجي الذي سيُنفّذه `agent.stream` — يُعدّه الاختبار.
#:
#: كل خطوة إمّا:
#:   ``{"tool": "search_contract_clauses", "args": {...}}``  → نداء أداة حقيقي
#:   ``{"content": "نصّ المسودّة"}``                          → مخرج النموذج
#:
#: مثال:
#:     AGENT_SCRIPT = [
#:         {"tool": "search_contract_clauses", "args": {"query": "إيجار"}},
#:         {"content": "عقد إيجار\n...\n[[الأسانيد]]\nC1 :: نصّ\n[[/الأسانيد]]"},
#:     ]
AGENT_SCRIPT: list[dict] = []

#: إن حُدِّد، يرفع `agent.stream` هذا الاستثناء — لاختبار مسار الفشل.
AGENT_RAISE: BaseException | None = None


def _resolve_real_tool(name: str) -> Any:
    """
    يجلب الأداة **الحقيقية** من `legal_agent` بتحميل كسول.

    الكسل ضروري: `fake_deps` يُستورد قبل `legal_agent`، فلا يمكن الإشارة إلى
    أدواته في زمن الاستيراد.
    """
    module = sys.modules.get("legal_agent")
    return getattr(module, name, None) if module else None


def _run_scripted_stream(steps: list[dict]) -> Any:
    """
    يحوّل النصّ البرمجي إلى أحداث `updates` كما يفعل LangGraph الحقيقي.

    والأهم: عند خطوة أداة **يستدعي الأداة الحقيقية** لا نصّاً مُعدّاً مسبقاً.
    فيمرّ الاختبار بالمسار الفعلي: النداء، والتنسيق، والتسجيل في جامع الأدلّة.
    ولو اكتفينا بإرجاع نصّ جاهز لما اختُبر شيء من ذلك — ولما كان في الاختبار
    قيمة.
    """
    for step in steps:
        if "content" in step:
            yield {"chatbot": {"messages": [_FakeMessage(content=step["content"])]}}
            continue

        if "tool" in step:
            name = step["tool"]
            args = dict(step.get("args") or {})
            # ١) النموذج "يقرّر" نداء الأداة
            yield {
                "chatbot": {
                    "messages": [
                        _FakeMessage(content="", tool_calls=[{"name": name, "args": args}])
                    ]
                }
            }
            # ٢) عقدة الأدوات تنفّذها فعلاً — وهنا تُسجَّل الأدلّة
            tool = _resolve_real_tool(name)
            result = tool(**args) if callable(tool) else ""
            yield {"tools": {"messages": [_FakeMessage(content=result)]}}


class _FakeCompiledGraph:
    """
    يقلّد الرسم المُصرَّف، وينفّذ النصّ البرمجي في `AGENT_SCRIPT`.

    الخصائص التي تستطيع الاختبارات ضبطها:
        ``fake_deps.AGENT_SCRIPT``  قائمة الخطوات
        ``fake_deps.AGENT_RAISE``   استثناء يُرفع فور النداء
    """

    def __init__(self, builder: _FakeStateGraph) -> None:
        self.builder = builder

    def stream(self, *args: Any, **kwargs: Any) -> Any:
        if AGENT_RAISE is not None:
            raise AGENT_RAISE
        return _run_scripted_stream(AGENT_SCRIPT)

    def invoke(self, *args: Any, **kwargs: Any) -> dict:
        return {"messages": []}


class _FakeLLM:
    """يقلّد `ChatGoogleGenerativeAI` — `bind_tools` تُعيد النموذج نفسه."""

    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs
        self.bound_tools: list[Any] = []

    def bind_tools(self, tools: Any) -> "_FakeLLM":
        self.bound_tools = list(tools)
        return self

    def invoke(self, messages: Any) -> _FakeMessage:
        return _FakeMessage(content="")


class _FakeToolNode:
    def __init__(self, tools: Any = None, **kwargs: Any) -> None:
        self.tools = list(tools or [])


# ==============================================================================
# ٥. التركيب
# ==============================================================================

# ==============================================================================
# ٤-ب. وحدات fastapi / pydantic الوهمية
# ==============================================================================
# تُلزم `main.py` بأن يُستورد حقيقياً: مساراته، ومنطق بثّه، ومنطق التحقّق.
# والوهمي هنا هو الإطار وحده.


class HTTPException(Exception):
    """يقلّد `fastapi.HTTPException` بالحقول التي يقرؤها المشروع."""

    def __init__(self, status_code: int = 500, detail: Any = "", headers: Any = None):
        self.status_code = status_code
        self.detail = detail
        self.headers = headers or {}
        super().__init__(detail)


def Depends(dependency: Any = None, **kwargs: Any) -> Any:
    """يُعيد التبعية نفسها — فالاختبار يستطيع نداءها مباشرة."""
    return dependency


def Header(default: Any = None, **kwargs: Any) -> Any:
    return default


class CORSMiddleware:
    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs


class StreamingResponse:
    """يقلّد `StreamingResponse` ويحفظ المحتوى ليُستهلك في الاختبار."""

    def __init__(self, content: Any, media_type: Any = None, headers: Any = None):
        self.content = content
        self.media_type = media_type
        self.headers = headers or {}
        self.status_code = 200


class HTMLResponse(str):
    """يقلّد `HTMLResponse` — نصّ صالح للفحص."""


class BaseModel:
    """يقلّد `pydantic.BaseModel` بالحدّ الأدنى: تخزين الحقول."""

    def __init__(self, **kwargs: Any) -> None:
        for key, value in kwargs.items():
            setattr(self, key, value)


class _FieldMarker:
    def __init__(self, default: Any = None, **kwargs: Any) -> None:
        self.default = default
        self.info = kwargs


def Field(default: Any = None, **kwargs: Any) -> _FieldMarker:  # noqa: N802
    """يقلّد `pydantic.Field` — القيمة الافتراضية هي ما يهمّ الاختبار."""
    return _FieldMarker(default, **kwargs)


class _FakeFastAPI:
    """
    يقلّد `FastAPI` ويسجّل المسارات.

    التسجيل يسمح بفحص أن المسارات ما زالت قائمة وأن المصادقة ما زالت مربوطة —
    وهو أول ما ينكسر عند إضافة ميزة إلى `main.py`.
    """

    def __init__(self, **kwargs: Any) -> None:
        self.routes: list[tuple[str, str, Any, dict]] = []
        self.version = kwargs.get("version", "0")
        self.title = kwargs.get("title", "")
        self.middleware: tuple | None = None

    def _reg(self, method: str, path: str, **kwargs: Any) -> Any:
        def decorator(fn: Any) -> Any:
            self.routes.append((method, path, fn, kwargs))
            return fn

        return decorator

    def get(self, path: str, **kwargs: Any) -> Any:
        return self._reg("GET", path, **kwargs)

    def post(self, path: str, **kwargs: Any) -> Any:
        return self._reg("POST", path, **kwargs)

    def add_middleware(self, *args: Any, **kwargs: Any) -> None:
        self.middleware = (args, kwargs)


# ==============================================================================
# ٥. التركيب
# ==============================================================================

#: الوحدات التي نحجبها. تُحفظ نسخها الأصلية إن وُجدت (!) ليمكن التراجع.
_HIDDEN = (
    "dotenv",
    "supabase",
    "sentence_transformers",
    "langchain_google_genai",
    "langchain_core",
    "langchain_core.tools",
    "langchain_core.messages",
    "langgraph",
    "langgraph.graph",
    "langgraph.graph.message",
    "langgraph.prebuilt",
    "fastapi",
    "fastapi.middleware",
    "fastapi.middleware.cors",
    "fastapi.responses",
    "pydantic",
)

_saved: dict[str, Any] = {}
_installed = False


def install() -> None:
    """
    يثبّت الوحدات الوهمية في `sys.modules`.

    يجب أن تُستدعى **قبل** استيراد `legal_agent`. وتكرار الاستدعاء آمن.
    """
    global _installed
    if _installed:
        return

    # متغيّرات بيئة صورية: `get_supabase()` يرفع استثناءً إن نقصت، ولا نريد
    # أن يعتمد اختبار الأدوات على وجود `.env` حقيقي على الجهاز.
    os.environ.setdefault("SUPABASE_URL", "https://fake.supabase.test")
    os.environ.setdefault("SUPABASE_KEY", "fake-key-for-tests")
    os.environ.setdefault("GOOGLE_API_KEY", "fake-google-key-for-tests")

    # حفظ ما هو موجود فعلاً، حتى يمكن إعادة الحالة كما كانت (underrun).
    for name in _HIDDEN:
        if name in sys.modules:
            _saved[name] = sys.modules[name]

    _register("dotenv", load_dotenv=lambda *a, **k: False)

    _register("supabase", create_client=lambda url, key: FAKE_SUPABASE, Client=object)

    _register("sentence_transformers", SentenceTransformer=FakeEmbedder)

    _register("langchain_google_genai", ChatGoogleGenerativeAI=_FakeLLM)

    core = _register("langchain_core")
    _register("langchain_core.tools", parent="langchain_core", tool=_tool_decorator)
    _register(
        "langchain_core.messages",
        parent="langchain_core",
        HumanMessage=_FakeMessage,
        AIMessage=_FakeMessage,
        SystemMessage=_FakeMessage,
        ToolMessage=_FakeMessage,
    )

    _register("langgraph")
    _register(
        "langgraph.graph",
        parent="langgraph",
        StateGraph=_FakeStateGraph,
        START="__start__",
        END="__end__",
    )
    _register("langgraph.graph.message", parent="langgraph.graph", add_messages=list)
    _register(
        "langgraph.prebuilt",
        parent="langgraph",
        ToolNode=_FakeToolNode,
        tools_condition=lambda state: "__end__",
    )

    core.tools = sys.modules["langchain_core.tools"]
    core.messages = sys.modules["langchain_core.messages"]

    _register(
        "fastapi",
        FastAPI=_FakeFastAPI,
        Depends=Depends,
        Header=Header,
        HTTPException=HTTPException,
    )
    _register("fastapi.middleware")
    _register(
        "fastapi.middleware.cors",
        parent="fastapi.middleware",
        CORSMiddleware=CORSMiddleware,
    )
    _register(
        "fastapi.responses",
        parent="fastapi",
        StreamingResponse=StreamingResponse,
        HTMLResponse=HTMLResponse,
    )
    _register("pydantic", BaseModel=BaseModel, Field=Field)

    _installed = True


def uninstall() -> None:
    """يُزيل الوحدات الوهمية ويعيد الأصلية إن كانت محفوظة."""
    global _installed
    if not _installed:
        return
    for name in _HIDDEN:
        sys.modules.pop(name, None)
    sys.modules.update(_saved)
    _saved.clear()
    FAKE_SUPABASE.reset()
    FakeEmbedder.reset()
    _installed = False


def reset() -> None:
    """يُفرّغ التسجيلات بين الاختبارات — بلا إزالة الوحدات."""
    global AGENT_RAISE
    FAKE_SUPABASE.reset()
    FakeEmbedder.reset()
    AGENT_SCRIPT.clear()
    AGENT_RAISE = None


def make_row(
    chunk_id: Any = 1,
    document_name: str = "مستند اختبار",
    chunk_content: str = "نصّ المقطع",
    similarity: float = 0.9,
) -> dict:
    """يبني صفّاً بشكل ما تُرجعه دوال RPC فعلاً (انظر `schema.sql`)."""
    return {
        "id": chunk_id,
        "document_name": document_name,
        "chunk_content": chunk_content,
        "similarity": similarity,
    }
