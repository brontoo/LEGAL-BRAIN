"""Adapter over the existing lazy e5 encoder, Supabase client and vector(1024)."""
from dataclasses import asdict, replace
import time
import math
from .diagnostics import call
from .schemas import RetrievalError, BranchResult
from .config import THRESHOLDS


def filters(request, config):
    return {'jurisdiction':asdict(request.context.jurisdiction),
            'as_of':request.context.as_of.isoformat() if request.context.as_of else None,
            'unknown_policy':config.unknown_policy}


def retrieve(client, encode, session, request, config):
    started=time.perf_counter()
    try:
        vector=session.embedding(request.query,encode)
        if len(vector)!=1024 or any(type(x) not in (float,int) or not math.isfinite(x) for x in vector):
            raise RetrievalError('Invalid embedding vector')
        if not any(vector): raise RetrievalError('Zero embedding vector')
    except Exception:
        return BranchResult('semantic',status='embedding_unavailable',elapsed_ms=(time.perf_counter()-started)*1000)
    def run():
        return client.rpc('hybrid_semantic_v1',{'p_family':request.family,'p_embedding':vector,
             'p_threshold':THRESHOLDS[request.family],'p_limit':config.candidate_pool,
             'p_filters':filters(request,config)}).execute().data
    result=call('semantic',run)
    return replace(result,elapsed_ms=(time.perf_counter()-started)*1000)
