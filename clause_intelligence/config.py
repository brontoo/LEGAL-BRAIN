"""Independent opt-ins and fixed resource ceilings."""
import os

MAX_DOCUMENT_CHARS = 100_000
MAX_LINES = 4_000
MAX_CLAUSES = 600
MAX_RECORDS = 2_000
MAX_CLAUSE_CHARS = 20_000
MAX_MODEL_CHARS = 24_000
MAX_MODEL_OUTPUT = 12_000


def enabled():
    return os.environ.get('ENABLE_CLAUSE_INTELLIGENCE', 'false').strip().lower() == 'true'


def model_enabled():
    return os.environ.get('ENABLE_CLAUSE_MODEL_ASSISTANCE', 'false').strip().lower() == 'true'


def role_v2_enabled():
    return os.environ.get('ENABLE_CLAUSE_ROLE_V2', 'false').strip().lower() == 'true'
