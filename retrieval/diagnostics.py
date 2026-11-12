"""Bounded operational categories; exception bodies and queries never leave adapters."""
import time
from .schemas import BranchResult


def call(name, function):
    started=time.perf_counter()
    try:
        rows=function()
        if not isinstance(rows,list):
            return BranchResult(name,status='invalid_response',elapsed_ms=(time.perf_counter()-started)*1000)
        return BranchResult(name,tuple(rows),'ok',(time.perf_counter()-started)*1000)
    except Exception as exc:
        code=str(getattr(exc,'code',''))
        status=('migration_absent' if code in ('PGRST202','42883','42P01') else
                'timeout' if isinstance(exc,TimeoutError) or code=='57014' or any(c.__name__ in {'ReadTimeout','ConnectTimeout','PoolTimeout','WriteTimeout','TimeoutException','APITimeoutError'} for c in type(exc).__mro__) else
                'permission_denied' if code=='42501' else 'rpc_unavailable')
        return BranchResult(name,status=status,elapsed_ms=(time.perf_counter()-started)*1000)
