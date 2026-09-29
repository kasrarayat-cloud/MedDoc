"""The ONE check of the diagnostic freeze, and the provenance every graded output records (RECHECK.md R2).

`verify()` refuses (FreezeMismatch) unless every file mapping/EXPECTED-SHA256SUMS lists exists and matches its frozen
sha256, and every expected map in mapping/ is listed. `provenance()` returns what a grader writes beside its result:
the manifest's sha256, the grader's own sha256, the sha256 of each input it graded, and the candidate (the commit the
diagnostics are pinned to, whether this checkout's rebuild/ still equals it outside rebuild/ops/, and the sha256 of the
engine files the graders exercise).

Used by mapping/grade_app_path.py (--grade, --self-test), notes/offline_replay.py (--replay) and the campaign's stage
runner (rebuild/ops/sonnet5_stages.py) BEFORE anything is graded or sent. It opens no socket, imports no Django and
reads no environment file.
"""
import hashlib
import subprocess
from pathlib import Path

DIAGNOSTICS = Path(__file__).resolve().parent
MANIFEST = DIAGNOSTICS / 'mapping' / 'EXPECTED-SHA256SUMS'
WORKTREE = DIAGNOSTICS.parents[3]
#: The candidate every frozen expectation and recorded observation is pinned to (FREEZE.json `candidate.sha`).
CANDIDATE = '8e3dcfd07a5946430e7291b520faf35c8055127b'
ENGINE_FILES = ('rebuild/core/mapping_assistance.py', 'rebuild/core/mapping_wire.py', 'rebuild/core/mapping_jobs.py',
                'rebuild/core/v3_mapping.py', 'rebuild/core/generation.py', 'rebuild/core/v3_field_relations.py',
                'rebuild/documents/word_v3.py', 'rebuild/documents/service.py')


class FreezeMismatch(Exception):
    """A frozen diagnostic file differs from EXPECTED-SHA256SUMS (or an expected map is unlisted): nothing is graded."""


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def listed(manifest=MANIFEST):
    """{name relative to the manifest's directory: frozen sha256}."""
    frozen = {}
    for line in Path(manifest).read_text().splitlines():
        if not line.strip() or line.startswith('#'):
            continue
        digest, name = line.split(None, 1)
        frozen[name.strip()] = digest
    return frozen


def verify(manifest=MANIFEST):
    """Every listed file matches and every expected map is listed; otherwise FreezeMismatch naming each difference."""
    manifest = Path(manifest)
    if not manifest.is_file():
        raise FreezeMismatch(f'{manifest} is missing: the diagnostics are not frozen')
    frozen = listed(manifest)
    base = manifest.parent
    problems = [] if frozen else ['the manifest lists no file']
    for name, digest in sorted(frozen.items()):
        path = base / name
        now = sha256(path) if path.is_file() else None
        if now != digest:
            problems.append(f'{name}: frozen {digest}, now {now}')
    for path in sorted(base.glob('*.expected.json')):
        if path.name not in frozen:
            problems.append(f'{path.name}: an expected map the manifest does not list')
    if problems:
        raise FreezeMismatch('the diagnostics differ from their freeze (mapping/EXPECTED-SHA256SUMS): '
                             + '; '.join(problems))
    return {'manifest': 'mapping/EXPECTED-SHA256SUMS', 'manifest_sha256': sha256(manifest), 'frozen_files_match': True,
            'frozen_files': frozen}


def candidate():
    """The candidate the frozen sets are pinned to, and whether this checkout still runs it (rebuild/ outside ops/)."""
    def git(*args):
        try:
            return subprocess.run(['git', '-C', str(WORKTREE), *args], capture_output=True, text=True, timeout=60)
        except (OSError, subprocess.SubprocessError):
            return None
    head = git('rev-parse', 'HEAD')
    same = git('diff', '--quiet', CANDIDATE, '--', 'rebuild', ':(exclude)rebuild/ops')
    return {'commit': CANDIDATE,
            'head': head.stdout.strip() if head is not None and head.returncode == 0 else None,
            'rebuild_equals_candidate': (None if same is None or same.returncode not in (0, 1) else same.returncode == 0),
            'engine_sha256': {name: (sha256(WORKTREE / name) if (WORKTREE / name).is_file() else None)
                              for name in ENGINE_FILES}}


def provenance(grader, inputs):
    """What a graded output records. Refuses (FreezeMismatch) first, before anything is graded."""
    frozen = verify()
    return {'manifest': frozen['manifest'], 'manifest_sha256': frozen['manifest_sha256'], 'frozen_files_match': True,
            'grader': Path(grader).name, 'grader_sha256': sha256(grader),
            'inputs': {name: (sha256(path) if path is not None and Path(path).is_file() else None)
                       for name, path in inputs.items()},
            'candidate': candidate()}
