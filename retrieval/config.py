"""Independent default-off flag and bounded, validated runtime settings."""
import os
from dataclasses import dataclass
from .schemas import RetrievalError

FINAL_COUNTS = {'legislation': 3, 'drafts': 2, 'contracts': 4, 'notices': 3, 'poa': 3}
THRESHOLDS = {'legislation': .75, 'drafts': .70, 'contracts': .70, 'notices': .70, 'poa': .70}


def enabled() -> bool:
    return os.environ.get('ENABLE_HYBRID_LEGAL_RETRIEVAL', 'false').strip().lower() == 'true'


@dataclass(frozen=True)
class RetrievalConfig:
    candidate_pool: int = 30
    rrf_k: int = 60
    max_per_document: int = 2
    unknown_policy: str = 'research_lead'
    exact_priority: bool = True
    prefer_compatible: bool = True

    def __post_init__(self):
        for value,low,high in ((self.candidate_pool,1,100),(self.rrf_k,1,200),(self.max_per_document,1,20)):
            if type(value) is not int or not low <= value <= high:
                raise RetrievalError('Retrieval setting outside allowed bounds')
        if self.unknown_policy not in ('exclude','research_lead') or type(self.exact_priority) is not bool or type(self.prefer_compatible) is not bool:
            raise RetrievalError('Invalid retrieval policy')

    @classmethod
    def from_env(cls):
        try:
            exact=os.environ.get('HYBRID_EXACT_PRIORITY','true').strip().lower()
            prefer=os.environ.get('HYBRID_PREFER_COMPATIBLE','true').strip().lower()
            if prefer not in ('true','false'):raise RetrievalError('Invalid metadata preference flag')
            if exact not in ('true','false'):raise RetrievalError('Invalid exact priority flag')
            return cls(candidate_pool=int(os.environ.get('HYBRID_CANDIDATE_POOL','30')),
                       rrf_k=int(os.environ.get('HYBRID_RRF_K','60')),
                       max_per_document=int(os.environ.get('HYBRID_MAX_PER_DOCUMENT','2')),
                       unknown_policy=os.environ.get('HYBRID_UNKNOWN_POLICY','research_lead'),
                       exact_priority=exact == 'true',prefer_compatible=prefer == 'true')
        except (ValueError, TypeError) as exc:
            raise RetrievalError('Invalid hybrid retrieval configuration') from exc
