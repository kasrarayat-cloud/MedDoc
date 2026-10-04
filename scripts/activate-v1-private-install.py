#!/usr/bin/env python3
"""Normal preserving private V1 installation door; default verifies source only.

Execute only through run-ruled-mutation.sh with a frozen committed declaration.
Unmet product gates or a missing frozen PostgreSQL contract refuse BEFORE the
runtime backend, protected credentials, installed services or timers are read.
"""
import argparse
import hashlib
import json
import os
import re
from pathlib import Path, PurePosixPath
import subprocess
import sys
import signal

sys.dont_write_bytecode = True
SOURCE = Path(__file__).resolve().parents[1]
ROOT = Path('/opt/meddoc-pro')
SELF = 'scripts/activate-v1-private-install.py'
CATALOG_EVIDENCE = ROOT / 'rebuild/.runtime/v1-private-install-catalog'
sys.path.insert(0, str(SOURCE / 'rebuild'))
from ops import v1_private_install_preparation as p
from ops import v1_private_install_adapter as adapter


def output(command, *, cwd=SOURCE):
    return subprocess.check_output(command, cwd=cwd, timeout=90, stderr=subprocess.PIPE).decode().strip()


def git(*args, cwd=SOURCE):
    return output(['git', *args], cwd=cwd)


def source_file(relative, target):
    path = PurePosixPath(relative)
    p.require(not path.is_absolute() and str(path) == relative and '..' not in path.parts
              and '.runtime' not in path.parts and (not path.name.startswith('.env') or path.name == '.env.example'),
              'Non-source declaration path.')
    actual = SOURCE / relative
    p.require(actual.resolve() == actual and actual.is_file(), 'Canonical tracked source file required.')
    raw = actual.read_bytes()
    p.require(subprocess.check_output(['git', 'show', target + ':' + relative], cwd=SOURCE, timeout=90) == raw,
              'Tracked candidate source bytes changed.')
    return raw


def catalog_file(record):
    # Raw database catalog evidence is retained outside Git. The declaration
    # names only its SHA, not an arbitrary private path or a production secret.
    p.require(isinstance(record, dict) and set(record) == {'sha256'}
              and isinstance(record['sha256'], str) and re.fullmatch('[a-f0-9]{64}', record['sha256']),
              'Frozen synthetic PostgreSQL catalog evidence identity is absent.')
    from ops.backup_restore import read_private
    raw = read_private(CATALOG_EVIDENCE / (record['sha256'] + '.json'), 2 * 1024 * 1024)
    p.require(p.sha(raw) == record['sha256'], 'Frozen PostgreSQL receipt changed.')
    return raw


def validate_source(target, relative):
    p.require(len(target) == 40 and all(c in '0123456789abcdef' for c in target)
              and SOURCE.resolve() == SOURCE and SOURCE.is_relative_to(ROOT / '.worktrees'),
              'Use a full revision and its retained target worktree.')
    p.require(git('rev-parse', 'HEAD') == target and not git('status', '--porcelain', '--untracked-files=no'),
              'Exact clean candidate checkout required.')
    raw = source_file(relative, target)
    frozen = json.loads(raw)
    p.require(frozen.get('format') == 'quillmd-v1-private-install-declaration-v1'
              and frozen.get('status') == 'frozen' and frozen.get('baseline') == p.BASELINE,
              'The new installation declaration is prepared, not frozen; installation remains held.')
    changed = git('diff', '--name-only', p.BASELINE, target).splitlines()
    p.require(frozen.get('changed_paths') == changed and SELF in changed and relative in changed,
              'Exact complete reviewed source delta required; an allowlist subset is insufficient.')
    # The commit, every tracked path/mode/blob, and clean checkout bind the FULL
    # source tree. The smaller preparation dictionary is only its declared-byte
    # predicate and never claims full-tree completeness independently.
    tree = subprocess.check_output(['git', 'ls-tree', '-r', '-z', target], cwd=SOURCE, timeout=90)
    p.require(all(row.split(b' ', 1)[0] in (b'100644', b'100755') for row in tree.split(b'\0') if row),
              'Candidate source has a link/submodule or unsupported tracked mode.')
    sources = {name: source_file(name, target) for name in frozen['preparation_paths']}
    schema = source_file(frozen['schema_path'], target)
    declaration = {'format': 'quillmd-private-v1-preparation-v1', 'baseline': p.BASELINE, 'target': target,
        'schema_sha256': p.sha(schema), 'source_sha256': {name: p.sha(value) for name, value in sources.items()},
        'data_mode': 'synthetic', 'payment_mode': 'test', 'public_maintenance': True, 'cpt_enabled': False}
    p.require(frozen.get('catalog_contract'), 'Frozen synthetic PostgreSQL catalog contract is absent.')
    catalog = catalog_file(frozen['catalog_contract'])
    adapter.validate_catalog_contract(catalog, sources, schema)
    # Prospective technical evidence is created after this commit's CI/provider/
    # Word gates. It cannot be committed into its own target SHA. This fixed
    # owner-only path is evidence, never a secret-file or alternate env reader.
    from ops.backup_restore import read_private
    qualification_path = ROOT / 'rebuild/.runtime/v1-private-install-qualification' / (target + '.json')
    qualification = read_private(qualification_path, 2 * 1024 * 1024)
    evidence = json.loads(qualification)
    p.plan(declaration, schema, sources, evidence, destination='installed_qualified_v1')
    frozen = dict(frozen, qualification_sha256=p.sha(qualification))
    return frozen, declaration, schema, sources, evidence, catalog, hashlib.sha256(tree).hexdigest()


def live_source(target):
    p.require(git('rev-parse', 'HEAD', cwd=ROOT) == p.BASELINE
              and git('branch', '--show-current', cwd=ROOT) == 'main'
              and git('rev-parse', 'origin/main', cwd=ROOT) == target
              and not git('status', '--porcelain', '--untracked-files=no', cwd=ROOT),
              'Shared main must be clean at the exact measured installed baseline.')
    subprocess.run(['git', 'merge-base', '--is-ancestor', p.BASELINE, target], cwd=ROOT,
                   check=True, timeout=90, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    pulls = json.loads(output(['gh', 'api', 'repos/kasrarayat-cloud/MedDoc/commits/' + target + '/pulls']))
    p.require(any(row.get('merged_at') and row.get('merge_commit_sha') == target
                  and row.get('base', {}).get('ref') == 'main' for row in pulls), 'Exact merged main PR required.')
    subprocess.run(['bash', str(SOURCE / 'scripts/check-citation.sh'), target], cwd=SOURCE,
                   check=True, timeout=180, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


def normal_declaration(target, relative):
    committed = os.environ.get('RULED_MUTATION_DECL_COMMIT', '')
    p.require(os.environ.get('RULED_MUTATION_DECLARATION') == str(SOURCE / relative)
              and re.fullmatch('[a-f0-9]{40}', committed),
              'Execute only through the exact committed normal ruled-mutation declaration.')
    # A normally merged PR's merge SHA differs from the commit which last wrote
    # the declaration. Preserve the established ancestor + exact-blob rule.
    subprocess.run(['git', 'merge-base', '--is-ancestor', committed, target], cwd=SOURCE,
                   check=True, timeout=90, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    prior = subprocess.check_output(['git', 'show', committed + ':' + relative], cwd=SOURCE, timeout=90)
    p.require(prior == source_file(relative, target), 'Normal declaration changed since its recorded commit.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target', required=True)
    parser.add_argument('--declaration', required=True, help='Tracked relative frozen declaration JSON')
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    frozen, declaration, schema, sources, evidence, catalog, tree_sha = validate_source(args.target, args.declaration)
    if not args.execute:
        print(json.dumps({'source_preparation_valid': True, 'target': args.target, 'full_git_tree_sha256': tree_sha,
                          'live_source_ci_state_unverified': True, 'installed_mutation_performed': False}))
        return
    # Require the normal committed declaration BEFORE querying installed state
    # or importing a backend which can access credentials and services.
    normal_declaration(args.target, args.declaration)
    live_source(args.target)
    from ops.v1_private_install_runtime import Backend
    backend = Backend(SOURCE, frozen, args.declaration, declaration, live_source)
    def deadline(signum, frame):
        raise TimeoutError('Private installation exceeded its absolute 1,500-second deadline.')
    signal.signal(signal.SIGALRM, deadline)
    signal.alarm(1500)
    try:
        result = adapter.activate(backend, declaration, schema, sources, evidence, catalog)
    finally:
        signal.alarm(0)
    print(json.dumps({'complete': result['complete'], 'target': args.target, 'evidence': str(backend.state),
                      'provider_calls': 0, 'public_cutover_performed': False}))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, RuntimeError, KeyError, subprocess.SubprocessError):
        raise SystemExit('Private V1 installer refused or stopped; inspect the retained phase evidence. No automatic rollback.') from None
