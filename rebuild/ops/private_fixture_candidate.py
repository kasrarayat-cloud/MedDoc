"""Prepare a new isolated fixture archive; never launch, stop, migrate or install it.

The pure bundle functions validate supplied bytes. The CLI independently checks
the exact local Git tree and live CI citation before creating task-owned assets.
Source refutation still requires the integration owner's exact-target evidence.
No credential file is opened here; the retained QA launcher keeps its existing
protected credential procedure for later authorized execution.
"""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import tarfile

from ops import v1_private_install_preparation as preparation

RUNTIME = Path('/opt/meddoc-pro/rebuild/.runtime/v1-sol-continuation-20261002')
OLD_RELEASE = '789c0372127d89b1750a2f790c561e68c19f1654'
OLD_ROOT = RUNTIME / 'demo-789c0372'
HELPERS = {
    'qa_launch.py': '578cb1b3ff99b1dad051dee66690806f14d59fb4f6b1198ec5ecfda8267629dd',
    'start.sh': '66356ec19f5f6c3680ff25a307e3ee28b2c423e13aa92825a707739742914413',
    'stop.sh': '54b743da424d21d8fd66e40b850003a8f54badcaa5394e20360a9ceff5d68130',
    'run_harness.sh': '51e31f2ba8d371d11d0a9e52fa5de8f7a4f9ee10a814568bf3298e4785e5b2cb',
    'netwatch.py': '45749a850892b98e2bae15cb1c02c1cec914e64c01998bcef5677fda555878f7',
    'create_qa_database.py': 'fe655ed822151089af5b46ed92af747c23f850dc783a3ac46d4bf7a5774e4425',
}
SCHEMA_PATH = 'docs/rebuild/v1/private-synthetic-install-preparation-20261004/schema-contract.json'
WORD_RUNTIME = '/opt/meddoc-pro/rebuild/.runtime/v1-product-20260930/int/browser/word-build/runtime'
WORD_MANIFEST = '/opt/meddoc-pro/rebuild/.runtime/v1-product-20260930/int/browser/word-build/runtime-manifest.json'
WORD_SHA256 = '2a1e4477144207bed04d3f3d38cb3b276cdaf7e450ef7d622f1ee63cd4e0d756'


def archive_sources(raw, target, tree, *, object_format='sha1'):
    """Match every regular archived file to the supplied full tracked rebuild tree.

    The CLI gets ``tree`` independently from git ls-tree. This pure function
    cannot authenticate caller-supplied Git metadata or source-safety receipts.
    """
    preparation.require(object_format in ('sha1', 'sha256'), 'Unknown Git object format.')
    preparation.require(isinstance(raw, bytes) and 0 < len(raw) <= 128 * 1024 * 1024,
                        'Bounded source archive required.')
    sources = {}
    with tarfile.open(fileobj=io.BytesIO(raw), mode='r:') as archive:
        preparation.require(archive.pax_headers.get('comment') == target, 'Archive revision differs.')
        for member in archive.getmembers():
            path = PurePosixPath(member.name)
            preparation.require(not path.is_absolute() and str(path) == member.name.rstrip('/')
                                and '..' not in path.parts and path.parts[0] == 'rebuild'
                                and (not path.name.startswith('.env') or path.name == '.env.example')
                                and (member.isdir() or member.isfile()), 'Non-source archive entry refused.')
            if not member.isfile():
                continue
            preparation.require(member.name not in sources and member.name in tree,
                                'Duplicate or untracked archive entry refused.')
            mode, kind, blob = tree[member.name]
            preparation.require(mode in ('100644', '100755') and kind == 'blob', 'Linked runtime source refused.')
            content = archive.extractfile(member).read()
            identity = hashlib.new(object_format, b'blob ' + str(len(content)).encode() + b'\0' + content).hexdigest()
            preparation.require(identity == blob, 'Archived bytes differ from the tracked Git blob.')
            sources[member.name] = content
    preparation.require(set(sources) == set(tree), 'Tracked runtime files omitted from source archive.')
    return sources


def helpers(target, blobs):
    preparation.require(isinstance(target, str) and re.fullmatch('[a-f0-9]{40}', target)
                        and target != OLD_RELEASE, 'New exact demonstration revision required.')
    preparation.require(set(blobs) == set(HELPERS), 'Retained helper set differs.')
    destination = RUNTIME / ('demo-' + target[:8])
    database = 'quillmd_qa_int_sol_' + target[:8]
    result = {}
    for name, expected in HELPERS.items():
        preparation.require(isinstance(blobs[name], bytes) and preparation.sha(blobs[name]) == expected,
                            'Retained fixture helper changed.')
        text = blobs[name].decode()
        text = text.replace(str(OLD_ROOT), str(destination)).replace(OLD_RELEASE, target)
        text = text.replace('789c0372', target[:8])
        if name == 'qa_launch.py':
            old = "'QUILLMD_REGISTRATION': 'open'"
            preparation.require(text.count(old) == 1, 'Registration source boundary changed.')
            text = text.replace(old, "'QUILLMD_REGISTRATION': 'invite'")
            # Make the fixture profile explicit in both retained launcher modes.
            old = "'QUILLMD_AI_MODE': 'fixture'}"
            preparation.require(text.count(old) == 1, 'Fixture provider boundary changed.')
            text = text.replace(old, "'QUILLMD_AI_MODE': 'fixture',\n"
                "           'QUILLMD_AI_PROVIDER': 'anthropic', 'QUILLMD_AI_MODEL': 'claude-sonnet-5-5',\n"
                "           'QUILLMD_AI_THINKING': 'between_tools', 'QUILLMD_AI_EFFORT': 'medium',\n"
                "           'QUILLMD_AI_INFERENCE_GEO': '', 'QUILLMD_AI_INPUT_RATE': '2',\n"
                "           'QUILLMD_AI_OUTPUT_RATE': '10', 'QUILLMD_AI_CACHED_RATE': '0.20',\n"
                "           'QUILLMD_WORD_ENGINE': 'auto', 'QUILLMD_V3_FIELD_RELATIONS': '1'}")
        preparation.require(str(OLD_ROOT) not in text and OLD_RELEASE not in text and '789c0372' not in text,
                            'Old demonstration identity remains.')
        if name.endswith('.py'):
            compile(text, name, 'exec')
        result[name] = text.encode()
    return destination, database, result


def bundle(declaration, evidence, schema, archive, tree, helper_bytes, word, *, object_format='sha1'):
    sources = archive_sources(archive, declaration['target'], tree, object_format=object_format)
    plan = preparation.plan(declaration, schema, sources, evidence, destination='isolated_fixture_demo')
    destination, database, rendered = helpers(declaration['target'], helper_bytes)
    preparation.require(isinstance(word, dict) and word.get('runtime') == WORD_RUNTIME
                        and word.get('manifest') == WORD_MANIFEST and word.get('manifest_sha256') == WORD_SHA256
                        and word.get('qualification') is True, 'Exact retained Word runtime required.')
    return rendered, sources, {'commit': declaration['target'], 'root': str(destination),
        'database': database, 'ports': [9160, 9161], 'ai_mode': 'fixture', 'registration': 'invite',
        'model_configuration': preparation.MODEL, 'ordinary_field_contract': preparation.CONTRACT,
        'field_relations': True, 'word_engine': 'auto', 'new_import_v3_preference': True,
        'role_suggestions': False, 'source_tar_sha256': preparation.sha(archive),
        'runtime_source_sha256': {name: preparation.sha(raw) for name, raw in sources.items()},
        'retained_helper_sha256': HELPERS,
        'prepared_helper_sha256': {name: preparation.sha(raw) for name, raw in rendered.items()},
        'installed_units': [], 'installed_mutation_performed': False, 'old_demo_modified': False,
        'prepared_only': True, 'launched': False, 'plan': plan,
        'live_evidence': 'Separately declared standing campaigns; fixture results are never live qualification.'}


def regular_bytes(path, *, private=False):
    path = Path(path)
    for part in (path, *path.parents):
        preparation.require(not part.is_symlink(), 'Linked metadata refused.')
    info = path.lstat()
    preparation.require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_size <= 5 * 1024 * 1024,
                        'Bounded regular metadata file required.')
    if private:
        preparation.require(info.st_uid == os.getuid() and stat.S_IMODE(info.st_mode) in (0o600, 0o700),
                            'Metadata must be owner-only.')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, 'rb') as stream:
        now = os.fstat(stream.fileno())
        preparation.require((now.st_dev, now.st_ino, now.st_mode, now.st_nlink, now.st_size)
                            == (info.st_dev, info.st_ino, info.st_mode, info.st_nlink, info.st_size),
                            'Metadata changed during open.')
        return stream.read()


def protected_metadata(path):
    path = Path(path)
    preparation.require(path.is_absolute() and path.is_relative_to(RUNTIME) and path.suffix == '.json',
                        'Task-owned JSON metadata path required.')
    return json.loads(regular_bytes(path, private=True))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--declaration', type=Path)
    parser.add_argument('--evidence', type=Path)
    parser.add_argument('--inventory', action='store_true', help='Read local Git only; emit an exact declaration for review.')
    parser.add_argument('--commit', help='Full commit required with --inventory.')
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    if args.inventory:
        if not args.commit or args.declaration or args.evidence or args.check_only:
            parser.error('--inventory requires --commit and no execution metadata/options')
        target = args.commit
        preparation.require(re.fullmatch('[a-f0-9]{40}', target), 'Exact inventory revision required.')
    else:
        if not args.declaration or not args.evidence or args.commit:
            parser.error('Supply --declaration and --evidence, without --commit')
        declaration, evidence = protected_metadata(args.declaration), protected_metadata(args.evidence)
        target = declaration['target']
        preparation.citation(target, evidence.get('ci'))
    def git(*command):
        return subprocess.check_output(['git', *command], cwd=args.source, timeout=60)
    preparation.require(args.source.is_absolute() and args.source == args.source.resolve()
                        and not args.source.is_symlink()
                        and args.source.is_relative_to(Path('/opt/meddoc-pro/.worktrees')),
                        'Isolated source worktree required.')
    preparation.require(git('rev-parse', 'HEAD').decode().strip() == target
                        and git('status', '--porcelain') == b'', 'Exact clean candidate worktree required.')
    tree = {}
    for line in git('ls-tree', '-rz', '--full-tree', target, '--', 'rebuild').split(b'\0'):
        if line:
            identity, path = line.split(b'\t', 1)
            tree[path.decode()] = identity.decode().split()
    preparation.require(all('.runtime' not in PurePosixPath(name).parts
                            and (not PurePosixPath(name).name.startswith('.env')
                                 or PurePosixPath(name).name == '.env.example') for name in tree),
                        'Tracked runtime state or environment file refused before archive creation.')
    archive = git('archive', target, 'rebuild')
    schema = git('show', target + ':' + SCHEMA_PATH)
    object_format = git('rev-parse', '--show-object-format').decode().strip()
    if args.inventory:
        sources = archive_sources(archive, target, tree, object_format=object_format)
        declaration = {'format': 'quillmd-private-v1-preparation-v1', 'baseline': preparation.BASELINE,
            'target': target, 'schema_sha256': preparation.SCHEMA_SHA256,
            'source_sha256': {name: preparation.sha(raw) for name, raw in sources.items()},
            'data_mode': 'synthetic', 'payment_mode': 'test', 'public_maintenance': True, 'cpt_enabled': False}
        preparation.source_contract(declaration, schema, sources)
        print(json.dumps(declaration, indent=2))
        return
    ids = ','.join(str(row['run_id']) for row in evidence['ci'])
    subprocess.run(['bash', 'scripts/check-citation.sh', target, '--expect', ids],
                   cwd=args.source, check=True, timeout=360)
    helper_bytes = {name: regular_bytes(OLD_ROOT / name, private=True) for name in HELPERS}
    word = json.loads(regular_bytes(OLD_ROOT / 'word-runtime.json', private=True))
    preparation.require(word.get('runtime') == WORD_RUNTIME and word.get('manifest') == WORD_MANIFEST
                        and word.get('manifest_sha256') == WORD_SHA256 and word.get('qualification') is True,
                        'Exact retained Word runtime metadata required before reading its manifest.')
    preparation.require(preparation.sha(regular_bytes(WORD_MANIFEST)) == WORD_SHA256,
                        'Retained Word runtime manifest changed.')
    rendered, sources, record = bundle(declaration, evidence, schema, archive, tree, helper_bytes, word,
                                      object_format=object_format)
    for name, content in rendered.items():
        if name.endswith('.sh'):
            subprocess.run(['bash', '-n'], input=content, check=True, timeout=5)
    if args.check_only:
        print(json.dumps({'check_only': True, 'commit': target, 'source_files': len(sources),
                          'source_tar_sha256': record['source_tar_sha256'], 'root': record['root'],
                          'database': record['database'], 'ports': record['ports'], 'launched': False}))
        return
    os.umask(0o077)
    preparation.require(git('rev-parse', 'HEAD').decode().strip() == target
                        and git('status', '--porcelain') == b'', 'Candidate moved during qualification checks.')
    destination = Path(record['root'])
    preparation.require(not destination.exists() and not destination.is_symlink(), 'Never overwrite a demonstration.')
    destination.mkdir(mode=0o700)
    def write(path, raw, mode=0o600):
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(raw)
    for name in ('src', 'state', 'home', 'evidence', 'state/tmp', 't'):
        (destination / name).mkdir(mode=0o700, parents=True, exist_ok=True)
    write(destination / 'source.tar', archive)
    for name, content in sources.items():
        path = destination / 'src' / name
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        write(path, content, 0o700 if tree[name][0] == '100755' else 0o600)
    for name, content in rendered.items():
        write(destination / name, content, 0o700 if name.endswith('.sh') else 0o600)
    write(destination / 'word-runtime.json', json.dumps(word, indent=2).encode())
    write(destination / 'declaration.json', json.dumps(declaration, indent=2).encode())
    write(destination / 'evidence.json', json.dumps(evidence, indent=2).encode())
    write(destination / 'prepared.json', json.dumps(record, indent=2).encode())
    print(json.dumps({'prepared_only': True, 'commit': target, 'root': record['root'],
                      'database': record['database'], 'ports': record['ports'], 'launched': False}))


if __name__ == '__main__':
    main()
