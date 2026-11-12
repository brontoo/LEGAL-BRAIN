"""Offline, source-preserving contractual analysis; never legal approval."""
from .engine import analyze
from .schemas import AnalysisRequest, ClauseError, Document, EvidenceSpan, SupportStatus

__all__ = ['analyze', 'AnalysisRequest', 'ClauseError', 'Document', 'EvidenceSpan', 'SupportStatus']
