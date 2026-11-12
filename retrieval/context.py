"""Request-scoped context, embedding reuse and safe diagnostics; never global evidence."""
import contextlib
import contextvars
from dataclasses import asdict, dataclass, field
from datetime import date
import re
import threading
from case_file import derive_forum_key
from skills.schemas import JurisdictionContext, SkillError
from .schemas import RetrievalContext, RetrievalError


@dataclass
class RetrievalSession:
    context: RetrievalContext = field(default_factory=RetrievalContext)
    embeddings: dict = field(default_factory=dict)
    diagnostics: list = field(default_factory=list)
    lock: object = field(default_factory=threading.RLock)

    def embedding(self, query, encode):
        with self.lock:
            if query not in self.embeddings:
                if len(self.embeddings)>=32: self.embeddings.clear()
                self.embeddings[query]=tuple(encode(query))
            return list(self.embeddings[query])

    def record(self, summary):
        with self.lock:
            if len(self.diagnostics)<100: self.diagnostics.append(summary)


_current = contextvars.ContextVar('legal_hybrid_session',default=None)


def current_session(): return _current.get()


@contextlib.contextmanager
def retrieval_session(context=None):
    token=_current.set(RetrievalSession(context or RetrievalContext()))
    try: yield _current.get()
    finally: _current.reset(token)


def from_payload(payload=None, *, jurisdiction=None, case=None):
    if payload is None: payload={}
    if not isinstance(payload,dict) or set(payload)-{'jurisdiction','as_of'}:
        raise RetrievalError('Invalid retrieval context fields')
    try:
        context=JurisdictionContext.from_mapping(payload.get('jurisdiction',jurisdiction))
        raw=payload.get('as_of')
        if raw is not None and (not isinstance(raw,str) or not re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}',raw)):
            raise RetrievalError('Invalid as_of date')
        when=date.fromisoformat(raw) if raw else None
    except (ValueError,TypeError,SkillError) as exc:
        raise RetrievalError('Invalid retrieval jurisdiction or as_of date') from exc
    unsupported=False
    if case is not None:
        forum=derive_forum_key(getattr(case,'forum',None) or '')
        if forum in ('adgm','difc'):
            if context.court_jurisdiction not in ('unknown',forum):
                raise RetrievalError('Retrieval context conflicts with case forum')
            context=JurisdictionContext(**{**asdict(context),'court_jurisdiction':forum})
        country=(getattr(case,'country',None) or '').strip().lower()
        unsupported=bool(country and country not in ('uae','u.a.e.','united arab emirates','الإمارات','الامارات','الإمارات العربية المتحدة','الامارات العربية المتحدة'))
    return RetrievalContext(context,when,unsupported)
