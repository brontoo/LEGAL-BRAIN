"""Parameterized PostgreSQL simple-configuration FTS; deliberately not BM25."""
from .diagnostics import call
from .normalization import normalize
from .query_analysis import references
from .semantic import filters


def retrieve(client, request, config):
    return call('lexical',lambda: client.rpc('hybrid_lexical_v1',{
        'p_family':request.family,'p_query':normalize(request.query),
        'p_references':[{'kind':ref.kind,'value':ref.value} for ref in references(request.query)],
        'p_limit':config.candidate_pool,'p_filters':filters(request,config)}).execute().data)
