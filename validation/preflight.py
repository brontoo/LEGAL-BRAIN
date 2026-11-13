"""Presence/package inspection only. Never connect, load a model or print secrets."""
import importlib.util
import os
import re
import base64
import json
import time
from urllib.parse import urlsplit

READY='READY_FOR_TEST'
CONFIG='BLOCKED_MISSING_CONFIGURATION'
DEPENDENCY='BLOCKED_MISSING_DEPENDENCY'
UNVERIFIED='BLOCKED_ENVIRONMENT_UNVERIFIED'


def claimed_backend_role(key,now=None):
    """JWT claim inspection is not signature/authorization verification."""
    try:
        part=key.split('.')[1];value=json.loads(base64.urlsafe_b64decode(part+'='*(-len(part)%4)))
        role=value.get('role')
        if type(value.get('exp')) is int and value['exp']<=(time.time() if now is None else now):return 'expired'
        return role if role in ('service_role','authenticated') else None
    except Exception:return None


def available(name):
    try:return importlib.util.find_spec(name) is not None
    except (ImportError,ValueError):return False


def inspect(*,confirm_nonproduction=False,operator_opt_in=False):
    packages={name:available(name) for name in ('fastapi','pydantic','supabase','sentence_transformers','langchain_google_genai','langchain_core','langgraph')}
    presence={key:bool(os.environ.get(key)) for key in ('GOOGLE_API_KEY','SUPABASE_URL','SUPABASE_KEY','LEGAL_BRAIN_TEST_PROJECT_REF','LEGAL_BRAIN_TEST_DATABASE_DSN')}
    verified=bool(confirm_nonproduction and operator_opt_in and os.environ.get('LEGAL_BRAIN_LIVE_ENV')=='nonproduction')
    def state(keys,deps):
        if not all(presence[k] for k in keys):return CONFIG
        if not all(packages[d] for d in deps):return DEPENDENCY
        return READY if verified else UNVERIFIED
    result={'backend_test':READY if packages['fastapi'] and packages['pydantic'] else DEPENDENCY,
            'local_dependencies':READY if all(packages.values()) else DEPENDENCY,
            'gemini':state(('GOOGLE_API_KEY',),('langchain_google_genai','langchain_core','langgraph','supabase','sentence_transformers')),
            'supabase':state(('SUPABASE_URL','SUPABASE_KEY','LEGAL_BRAIN_TEST_PROJECT_REF'),('supabase',)),
            'e5_model':DEPENDENCY if not packages['sentence_transformers'] else UNVERIFIED,
            'test_database':CONFIG if not presence['LEGAL_BRAIN_TEST_DATABASE_DSN'] else UNVERIFIED,
            'nonproduction_confirmation':READY if verified else UNVERIFIED,
            'presence':presence,'packages':packages,'model_loaded':False,'network_access_performed':False,
            'credential_authorization':'operator_confirmation_only_not_inferred_from_presence'}
    if result['supabase']==READY:
        try:
            url=urlsplit(os.environ['SUPABASE_URL']); ref=os.environ['LEGAL_BRAIN_TEST_PROJECT_REF']
            safe=bool(re.fullmatch(r'[a-z0-9]{10,40}',ref) and url.scheme=='https' and url.hostname==ref+'.supabase.co'
                      and not url.username and not url.password and url.port is None and url.path in ('','/') and not url.query and not url.fragment)
        except (ValueError,TypeError):safe=False
        if not safe:result['supabase']='FAILED_PREFLIGHT'
    return result


if __name__=='__main__':
    import json
    print(json.dumps(inspect(),indent=2))
