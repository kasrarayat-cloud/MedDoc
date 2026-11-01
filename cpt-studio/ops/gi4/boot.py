"""Offline bootstrap, sealed tree exports and subprocess plumbing for the gi4 harness.

Nothing here imports Django or the service at import time. ``offline()`` is called by a tool's ``main`` only, before
anything imports ``studio``: it puts the tree to read first on sys.path, makes every socket connection and every database
connection attempt raise, forces the provider off and sets Django up. The committed tests never call it: they run inside
the Django test runner and hand the harness the modules already imported.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
import socket
import stat
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

HARNESS_TREE = Path(__file__).resolve().parents[2]  # the cpt-studio directory this harness lives in
REPO_ROOT = HARNESS_TREE.parent
LIVE_DB_PORT = '55451'  # the live service's database port: never used by anything here
# The throwaway database's settings (never connected to by an offline tool: a connection attempt raises). They are set
# only so that importing the settings module can never name the live database.
OFFLINE_ENV = {
    'CPT_STUDIO_DB_HOST': '127.0.0.1', 'CPT_STUDIO_DB_PORT': '55461', 'CPT_STUDIO_DB_NAME': 'cptstudio_ci',
    'CPT_STUDIO_DB_USER': 'cptstudio_ci', 'CPT_STUDIO_DB_PASSWORD': 'synthetic-cpt-ci-database-only',
    'CPT_STUDIO_TEST_DB_SUFFIX': 'gi4offline', 'CPT_STUDIO_PROVIDER_MODE': 'disabled',
    'CPT_STUDIO_CORTI_CREDENTIALS_FILE': '', 'CPT_STUDIO_REPLAY_DIR': '', 'CPT_STUDIO_AUTHORIZATION_REF': '',
    'CPT_STUDIO_SECRET_KEY': 'synthetic-gi4-harness-offline-key-with-no-external-access',
    'DJANGO_SETTINGS_MODULE': 'cptstudio.settings',
}
EXPORT_MARK = '.gi4-export'


class OfflineViolation(RuntimeError):
    """A network or database connection was attempted by an offline tool."""


def _refuse_network(*args, **kwargs):
    raise OfflineViolation('the gi4 harness runs offline: no network connection is made')


def _refuse_database(*args, **kwargs):
    raise OfflineViolation('the gi4 harness runs offline: no database connection is made')


def offline(tree=None, *, state_dir=None):
    """Read ``tree`` (a cpt-studio directory; default: the harness's own) offline. Returns the resolved tree path."""
    tree = Path(tree or HARNESS_TREE).resolve()
    if not (tree / 'studio' / 'gi' / 'context.py').is_file():
        raise SystemExit(f'{tree} is not a cpt-studio directory')
    loaded = sys.modules.get('studio')
    if loaded is not None:
        if Path(loaded.__file__).resolve().parents[1] != tree:
            raise SystemExit(f'studio is already imported from {loaded.__file__}; one tree per process')
        return tree
    os.environ.update(OFFLINE_ENV)
    os.environ['CPT_STUDIO_STATE_DIR'] = str(Path(state_dir or tempfile.gettempdir()).resolve())
    if os.environ['CPT_STUDIO_DB_PORT'] == LIVE_DB_PORT:  # belt and braces: OFFLINE_ENV never names it
        raise SystemExit('refusing the live database port')
    socket.socket.connect = _refuse_network
    socket.socket.connect_ex = _refuse_network
    socket.create_connection = _refuse_network
    sys.path.insert(0, str(tree))
    import django
    django.setup()
    from django.conf import settings
    from django.db.backends.base import base as db_base
    db_base.BaseDatabaseWrapper.connect = _refuse_database
    db_base.BaseDatabaseWrapper.ensure_connection = _refuse_database
    if settings.PROVIDER_MODE != 'disabled' or settings.CORTI_CREDENTIALS_FILE:
        raise SystemExit('the gi4 harness runs with the provider disabled and no credentials file')
    import studio
    if Path(studio.__file__).resolve().parents[1] != tree:
        raise SystemExit(f'studio resolved to {studio.__file__}, not to {tree}')
    return tree


# --- trees -----------------------------------------------------------------------------------------------------------

def git(*args, cwd=REPO_ROOT) -> str:
    return subprocess.run(['git', *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


def resolve(ref: str) -> str:
    """The full commit sha of ``ref`` (40 characters, read back from git)."""
    sha = git('rev-parse', '--verify', f'{ref}^{{commit}}')
    if len(sha) != 40:
        raise SystemExit(f'{ref!r} did not resolve to a full commit sha')
    return sha


def scratch_dir(arg=None) -> Path:
    """The scratch directory (mode 0700): ``arg``, else CPT_STUDIO_GI4_SCRATCH, else a new temporary directory."""
    path = Path(arg or os.environ.get('CPT_STUDIO_GI4_SCRATCH') or tempfile.mkdtemp(prefix='cpt-gi4-'))
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.chmod(0o700)
    return path.resolve()


def seal(root: Path) -> None:
    """Make an exported tree read-only (a sealed copy: nothing edits it in place)."""
    for path in sorted(root.rglob('*'), reverse=True) + [root]:
        mode = path.lstat().st_mode
        if not stat.S_ISLNK(mode):
            path.chmod(mode & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))


def unseal(root: Path) -> None:
    for path in [root] + sorted(root.rglob('*')):
        mode = path.lstat().st_mode
        if not stat.S_ISLNK(mode):
            path.chmod(mode | stat.S_IWUSR)


def export_ref(ref: str, scratch: Path) -> Path:
    """The cpt-studio directory of ``ref`` exported with ``git archive`` into ``scratch`` (sealed, reused when the
    same commit was exported before). The worktree is never touched."""
    sha = resolve(ref)
    dest = scratch / f'tree-{sha[:12]}'
    mark = dest / EXPORT_MARK
    if mark.is_file() and mark.read_text().strip() == sha:
        return dest / 'cpt-studio'
    if dest.exists():
        unseal(dest)
        shutil.rmtree(dest)
    dest.mkdir(mode=0o700, parents=True)
    data = subprocess.run(['git', 'archive', '--format=tar', sha, 'cpt-studio'], cwd=REPO_ROOT, check=True,
                          capture_output=True).stdout
    with tarfile.open(fileobj=io.BytesIO(data)) as archive:
        archive.extractall(dest, filter='data')
    mark.write_text(sha + '\n')
    seal(dest)
    return dest / 'cpt-studio'


def tree_arg(value: str, scratch: Path) -> Path:
    """A ``--base``/``--head`` value: a cpt-studio directory as it is, or a git ref exported (sealed) into ``scratch``."""
    path = Path(value)
    if path.is_dir() and (path / 'studio' / 'gi' / 'context.py').is_file():
        return path.resolve()
    return export_ref(value, scratch)


def tree_of(args, scratch: Path) -> Path:
    """The tree a single-tree run reads: ``--tree DIR``, an exported ``--ref REF``, or the harness's own tree."""
    if getattr(args, 'ref', None):
        return export_ref(args.ref, scratch)
    return Path(getattr(args, 'tree', None) or HARNESS_TREE).resolve()


def run_tool(module: str, tree: Path, extra: list, *, scratch: Path, label: str) -> dict:
    """Run ``python -m ops.gi4.<module> --tree TREE --json-out FILE ...`` in a process of its own (one tree per
    process) from the harness's tree, and return the JSON it wrote."""
    out = scratch / f'{module}-{label}-{os.getpid()}.json'
    env = {k: v for k, v in os.environ.items() if k not in ('PYTHONPATH', 'PYTHONHOME', 'PYTHONSTARTUP')}
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    env['CPT_STUDIO_GI4_SCRATCH'] = str(scratch)
    cmd = [sys.executable, '-B', '-m', f'ops.gi4.{module}', '--tree', str(tree), '--json-out', str(out), *extra]
    done = subprocess.run(cmd, cwd=HARNESS_TREE, env=env, text=True, capture_output=True)
    if done.returncode != 0:
        sys.stderr.write(done.stdout[-4000:] + done.stderr[-6000:])
        raise SystemExit(f'{module} on {tree} failed (exit {done.returncode})')
    data = json.loads(out.read_text(encoding='utf-8'))
    out.unlink()
    return data


def write_json(path, data) -> None:
    Path(path).write_text(json.dumps(data, indent=1, sort_keys=True, ensure_ascii=False) + '\n', encoding='utf-8')


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8', 'surrogatepass')).hexdigest()


def sha256_file(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def differences(a, b, path='', limit=200, out=None) -> list:
    """Every path at which two JSON values differ (at most ``limit``), as 'path: a != b' strings."""
    out = [] if out is None else out
    if len(out) >= limit:
        return out
    if isinstance(a, dict) and isinstance(b, dict):
        for key in sorted(set(a) | set(b), key=str):
            if key not in a or key not in b:
                out.append(f'{path}/{key}: ' + ('only in head' if key not in a else 'only in base'))
            else:
                differences(a[key], b[key], f'{path}/{key}', limit, out)
    elif isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        for i, (x, y) in enumerate(zip(a, b)):
            differences(x, y, f'{path}[{i}]', limit, out)
    elif a != b:
        show = lambda v: (json.dumps(v, ensure_ascii=False)[:160])  # noqa: E731
        out.append(f'{path}: {show(a)} != {show(b)}')
    return out
