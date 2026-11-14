"""Explicit external destinations, exclusive writes and owner-only permissions."""
import hashlib
import json
import os
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def outside_repository(path):
    path = Path(path).expanduser()
    if any(part.is_symlink() for part in (path, *path.parents)):
        raise ValueError('Symlink destinations are not allowed')
    resolved = path.resolve()
    # Reject this checkout, ancestor destinations and any other Git working tree.
    if resolved.is_relative_to(REPO) or REPO.is_relative_to(resolved):
        raise ValueError('Private artifacts must be outside the repository')
    for parent in (resolved, *resolved.parents):
        if (parent/'.git').exists():
            raise ValueError('Private destination is a Git working tree')
    return resolved


def directory(path):
    path = outside_repository(path)
    path.mkdir(mode=0o700, parents=True, exist_ok=False)
    path.chmod(0o700)
    return path


def write(path, value):
    path = outside_repository(path)
    raw = (json.dumps(value, ensure_ascii=False, indent=2)+'\n').encode()
    descriptor = os.open(path, os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os, 'O_NOFOLLOW', 0), 0o600)
    with os.fdopen(descriptor, 'wb') as stream:
        stream.write(raw)
    return hashlib.sha256(raw).hexdigest()


def read(path):
    path = Path(path)
    if path.is_symlink():raise ValueError('Symlink input is not accepted')
    if path.stat().st_size > 32*1024*1024:
        raise ValueError('Evaluation artifact exceeds size limit')
    try:
        return json.loads(path.read_bytes())
    except (ValueError, RecursionError, UnicodeError):
        raise ValueError('Invalid bounded evaluation JSON') from None


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
