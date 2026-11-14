"""Optional disposable-test adapter. Production code uses the existing Supabase client."""
from types import SimpleNamespace

TABLES={'legislation':'legal_documents','drafts':'legal_drafts','contracts':'legal_contracts','notices':'legal_notices','poa':'legal_poa'}


class DisposableClient:
    def __init__(self,dsn, *, acknowledge_disposable=False):
        if not acknowledge_disposable: raise ValueError('Explicit disposable-database acknowledgement required')
        import psycopg
        from psycopg.conninfo import conninfo_to_dict
        from psycopg.rows import dict_row
        options=conninfo_to_dict(dsn)
        if options.get('host') not in ('127.0.0.1','localhost') or options.get('dbname')!='legal_brain_test':
            raise ValueError('Only the loopback legal_brain_test disposable database is accepted')
        self.connection=psycopg.connect(dsn,autocommit=True,row_factory=dict_row)
        self.connection.execute('set search_path=public,extensions,pg_temp')

    def rpc(self,name,params):
        # Function names come solely from this static allowlist; all values use bind parameters.
        from psycopg.types.json import Jsonb
        names={'hybrid_semantic_v1','hybrid_lexical_v1','hybrid_metadata_audit_v1'}|{'match_'+table for table in TABLES.values()}
        if name not in names: raise ValueError('Unapproved test RPC')
        if name=='hybrid_semantic_v1':
            sql='select * from public.hybrid_semantic_v1(%s,%s::vector,%s,%s,%s::jsonb)'
            values=(params['p_family'],str(params['p_embedding']),params['p_threshold'],params['p_limit'],Jsonb(params['p_filters']))
        elif name=='hybrid_lexical_v1':
            sql='select * from public.hybrid_lexical_v1(%s,%s,%s::jsonb,%s,%s::jsonb)'
            values=(params['p_family'],params['p_query'],Jsonb(params['p_references']),params['p_limit'],Jsonb(params['p_filters']))
        elif name=='hybrid_metadata_audit_v1':
            sql='select public.hybrid_metadata_audit_v1(%s) as audit'
            values=(params['p_family'],)
        else:
            # name is already in the fixed map, never derived from a query/table argument.
            sql='select * from public.'+name+'(%s::vector,%s,%s)'
            values=(str(params['query_embedding']),params['match_threshold'],params['match_count'])
        return SimpleNamespace(execute=lambda:SimpleNamespace(data=list(self.connection.execute(sql,values).fetchall())))

    def close(self): self.connection.close()
