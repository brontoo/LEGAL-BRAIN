"""Backend deployment guard. No secret values are included in diagnostics."""
import os
from collections.abc import Mapping


def authentication_required(environ: Mapping[str, str] | None = None) -> bool:
    env = os.environ if environ is None else environ
    # Any production marker wins; a conflicting development marker cannot disable it.
    return (any(env.get(name, '').strip().lower() in {'production', 'prod'}
                for name in ('APP_ENV', 'ENVIRONMENT', 'NODE_ENV'))
            or env.get('REQUIRE_API_TOKEN', '').strip().lower() == 'true')


def validate_backend_auth(token: str, environ: Mapping[str, str] | None = None) -> None:
    if authentication_required(environ) and not token.strip():
        raise RuntimeError('Backend authentication required: configure API_TOKEN for production')
