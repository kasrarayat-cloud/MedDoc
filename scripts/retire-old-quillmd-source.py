#!/usr/bin/env python3
"""Retire pinned old worktree source and one old nightly cron; dry-run by default."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import subprocess
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
SHARED = Path('/opt/meddoc-pro')
MANIFEST = ROOT / 'docs/rebuild/obsolete-source-manifest.json'
RESULT = ROOT / 'docs/rebuild/obsolete-source-cleanup-result.json'
DECLARATION = '20260917-quillmd-obsolete-source.md'
ALLOWED = {
    'services/form-detect/app.py',
    'services/form-detect/requirements.txt',
    'services/form-detect/Dockerfile',
    'docker/gotenberg-fonts.Dockerfile',
    'scripts/backfill-auto-certify.ts',
    'scripts/execute-gate0-deactivation.sql',
    'scripts/execute-r226-archive.sql',
    'scripts/execute-r230-practice-archived-backfill.sql',
    'scripts/migrate-specialty-vocab.sql',
    'scripts/prisma-generate.sh',
    'scripts/assert-migrations-applied.sh',
    'scripts/data/build-icd10cm.mjs',
    'scripts/qa/b6-writer-refuses-on-qa.ts',
    'scripts/qa/b8-failure-cost-log-assert.py',
    'scripts/qa/b8-failure-cost-log-assert.sh',
    'scripts/qa/f2-signed-vs-presign-bytes.ts',
    'scripts/qa/rc1-assembly-on-qa.ts',
    'scripts/qa/rc2-twin-door-on-qa.ts',
    'scripts/qa/settle-word-numbering.ts',
}


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def run(args, data=None):
    result = subprocess.run(args, input=data, capture_output=True)
    # Do not expose raw crontab content or command stderr in audit output.
    require(result.returncode == 0, f'Command failed: {args[:2]} (exit {result.returncode})')
    return result.stdout


def file_check(row):
    rel = row['path']
    require(rel in ALLOWED, 'File is outside the literal retirement allowlist.')
    path = ROOT / rel
    require(path.is_file() and not path.is_symlink() and path.resolve() == path,
            f'Missing file, symlink, or resolved-path drift: {rel}')
    require(digest(path.read_bytes()) == row['sha256'], f'Content changed: {rel}')
    run(['git', '-C', str(ROOT), 'ls-files', '--error-unmatch', rel])
    run(['git', '-C', str(ROOT), 'diff', '--exit-code', 'HEAD', '--', rel])
    return path


def cron_replacement(original, spec):
    require(digest(original) == spec['original_crontab_sha256'], 'Crontab changed since review.')
    lines = original.splitlines(keepends=True)
    matches = [i for i, line in enumerate(lines)
               if digest(line.rstrip(b'\r\n')) == spec['line_sha256']]
    require(len(matches) == 1, 'Expected exactly one pinned nightly cron entry.')
    target = lines[matches[0]]
    require(target.split()[:5] == [b'0', b'2', b'*', b'*', b'*']
            and b'/opt/meddoc-pro/tests/automated/run-all.sh --smoke --e2e' in target,
            'Pinned cron no longer describes the reviewed old nightly test.')
    replacement = b''.join(line for i, line in enumerate(lines) if i != matches[0])
    require(digest(replacement) == spec['expected_crontab_sha256'], 'Unexpected cron delta.')
    return replacement


def container_state():
    ids = run(['docker', 'ps', '-aq']).decode().split()
    rows = json.loads(run(['docker', 'inspect', *ids])) if ids else []
    return {row['Id']: (row['Image'], row['State']['Running']) for row in rows}


def marketing_check():
    with urlopen('http://127.0.0.1:3010/', timeout=10) as response:
        require(response.status == 200, 'Marketing health check failed.')


def precheck():
    require(ROOT == SHARED / '.worktrees/quillmd-fresh' and ROOT.resolve() == ROOT,
            'Run only in the verified fresh worktree.')
    manifest = json.loads(MANIFEST.read_text())
    rows = manifest['files']
    require(len(rows) == 19 and {row['path'] for row in rows} == ALLOWED,
            'Manifest differs from the reviewed 19-file scope.')
    require(pwd.getpwuid(os.getuid()).pw_name == manifest['cron']['owner'] == 'claude',
            'Only the reviewed claude crontab may change.')
    for row in rows:
        file_check(row)
    original = run(['crontab', '-l'])
    replacement = cron_replacement(original, manifest['cron'])
    shared_files = {row['path']: digest((SHARED / row['path']).read_bytes()) for row in rows}
    marketing_check()
    print('CHECKED: 19 pinned old worktree files and one claude 02:00 nightly cron; '
          'marketing HTTP 200. Root crontab and monitoring jobs are excluded.', flush=True)
    return rows, original, replacement, shared_files


def execute():
    declaration = os.environ.get('RULED_MUTATION_DECLARATION', '')
    commit = os.environ.get('RULED_MUTATION_DECL_COMMIT', '')
    require(Path(declaration).name == DECLARATION and re.fullmatch('[a-f0-9]{40}', commit),
            'Execute only through the committed ruled-mutation gate.')
    for path in (MANIFEST, Path(__file__).resolve()):
        rel = str(path.relative_to(ROOT))
        run(['git', '-C', str(ROOT), 'ls-files', '--error-unmatch', rel])
        run(['git', '-C', str(ROOT), 'diff', '--exit-code', 'HEAD', '--', rel])
    rows, original, replacement, shared_files = precheck()
    before_containers = container_state()
    result = {'started_at_utc': datetime.now(timezone.utc).isoformat(),
              'declaration_commit': commit, 'removed_worktree_files': [],
              'removed_nightly_cron': False, 'complete': False}
    try:
        # crontab offers no compare-and-swap API; compare again immediately
        # before replacement and verify the exact result without exposing it.
        require(run(['crontab', '-l']) == original, 'Crontab changed before installation.')
        run(['crontab', '-'], replacement)
        result['removed_nightly_cron'] = True
        require(run(['crontab', '-l']) == replacement, 'Installed cron differs from expected bytes.')
        for row in rows:
            file_check(row).unlink()
            result['removed_worktree_files'].append(row['path'])
        require(all(not (ROOT / row['path']).exists() for row in rows), 'A target remains.')
        require(all(digest((SHARED / path).read_bytes()) == sha
                    for path, sha in shared_files.items()), 'Shared-tree source changed.')
        require(container_state() == before_containers, 'Container identity/image/state changed.')
        marketing_check()
        result.update(complete=True, marketing_http=200,
                      expected_crontab_sha256=digest(replacement),
                      protected_containers_preserved=len(before_containers),
                      shared_tree_target_files_preserved=len(shared_files))
    finally:
        result['finished_at_utc'] = datetime.now(timezone.utc).isoformat()
        RESULT.write_text(json.dumps(result, indent=2) + '\n')
    print('VERIFIED: one obsolete nightly cron removed; 19 old worktree files removed; '
          'shared source, containers, and marketing preserved.', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    execute() if args.execute else precheck()
