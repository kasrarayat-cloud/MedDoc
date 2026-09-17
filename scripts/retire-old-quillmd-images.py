#!/usr/bin/env python3
"""Remove only reviewed obsolete QuillMD image tags; defaults to read-only checks."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / 'docs/rebuild/obsolete-image-manifest.json'
RESULT = ROOT / 'docs/rebuild/obsolete-image-cleanup-result.json'
ALLOWED = {'meddoc-pro-transcribe-md', 'meddoc-pro-transcribe-md-worker',
           'meddoc-pro-meddoc-pro', 'meddoc-pro-form-detect', 'meddoc-pro-gotenberg'}
DECLARATION = '20260917-quillmd-obsolete-images.md'


def require(condition, reason):
    if not condition:
        raise RuntimeError(reason)


def run(args):
    result = subprocess.run(args, text=True, capture_output=True)
    require(result.returncode == 0, f'Failed command {args[:3]}: {result.stderr.strip()}')
    return result.stdout.strip()


def images():
    ids = sorted(set(run(['docker', 'image', 'ls', '-aq', '--no-trunc']).split()))
    return {item['Id']: item for item in json.loads(run(['docker', 'image', 'inspect', *ids]))}


def containers():
    ids = run(['docker', 'ps', '-aq']).split()
    return json.loads(run(['docker', 'inspect', *ids])) if ids else []


def verify_candidate(row, current, consumers):
    image_id = row['image_id']
    require(re.fullmatch(r'sha256:[a-f0-9]{64}', image_id), 'Invalid manifest image ID.')
    require(image_id in current, f'Pinned image is absent: {image_id}')
    require(row['tags'] and len(row['tags']) == len(set(row['tags'])), 'Invalid tag manifest.')
    require(all(tag.rsplit(':', 1)[0] in ALLOWED for tag in row['tags']), 'Unapproved image repository.')
    require(set(current[image_id].get('RepoTags') or []) == set(row['tags']),
            f'Image tags changed or shared tag exists: {image_id}')
    require(not any(c['Image'] == image_id for c in consumers),
            f'A running or stopped container now references {image_id}')


def precheck():
    require(ROOT != Path('/opt/meddoc-pro') and ROOT.is_relative_to('/opt/meddoc-pro'),
            'Run the reviewed worktree script; do not change the shared deployment tree.')
    manifest = json.loads(MANIFEST.read_text())
    require(set(manifest['allowed_repositories']) == ALLOWED, 'Manifest repository scope changed.')
    rows = manifest['candidates']
    require(len(rows) == 85 and sum(len(r['tags']) for r in rows) == 104,
            'Reviewed 85-image/104-tag scope differs from manifest.')
    require(len({r['image_id'] for r in rows}) == len(rows), 'Duplicate manifest image ID.')
    current, consumers = images(), containers()
    for row in rows:
        verify_candidate(row, current, consumers)
    with urlopen('http://127.0.0.1:3010/', timeout=10) as response:
        require(response.status == 200, 'Marketing baseline is not healthy.')
    print('CHECKED: 85 pinned obsolete images / 104 tags; no container references; '
          'no shared tags; marketing HTTP 200.', flush=True)
    print('Docker-reported unique image bytes: 24,305,405,245. Actual freed disk '
          'may differ because layers and build cache are shared.', flush=True)
    return rows, current, consumers


def execute():
    declaration = os.environ.get('RULED_MUTATION_DECLARATION', '')
    commit = os.environ.get('RULED_MUTATION_DECL_COMMIT', '')
    require(Path(declaration).name == DECLARATION and re.fullmatch('[a-f0-9]{40}', commit),
            'Execute only through the committed ruled-mutation gate.')
    for path in [MANIFEST, Path(__file__).resolve()]:
        rel = str(path.relative_to(ROOT))
        run(['git', '-C', str(ROOT), 'ls-files', '--error-unmatch', rel])
        run(['git', '-C', str(ROOT), 'diff', '--exit-code', 'HEAD', '--', rel])
    rows, before_images, before_containers = precheck()
    planned = {r['image_id'] for r in rows}
    protected_images = set(before_images) - planned
    result = {'started_at_utc': datetime.now(timezone.utc).isoformat(),
              'declaration_commit': commit, 'removed_tags': [], 'complete': False,
              'free_bytes_before': shutil.disk_usage(ROOT).free}
    try:
        for index, row in enumerate(rows, 1):
            # Recheck both stopped and running consumers immediately before each act.
            current = {item['Id']: item for item in json.loads(
                run(['docker', 'image', 'inspect', row['image_id']]))}
            verify_candidate(row, current, containers())
            # No --force, no prune, no ID-wide deletion: only pinned owned tags.
            run(['docker', 'image', 'rm', '--no-prune', *row['tags']])
            result['removed_tags'].extend(row['tags'])
            print(f'Removed reviewed image {index}/{len(rows)} ({len(row["tags"])} tags).', flush=True)
        after_images = images()
        require(protected_images <= set(after_images), 'A protected image disappeared.')
        remaining_tags = {tag for item in after_images.values() for tag in item.get('RepoTags') or []}
        require(not remaining_tags.intersection(result['removed_tags']), 'A planned tag remains.')
        after_containers = {c['Id']: c for c in containers()}
        for old in before_containers:
            new = after_containers.get(old['Id'])
            require(new and new['Image'] == old['Image']
                    and new['State']['Running'] == old['State']['Running'],
                    f'Protected container changed: {old["Name"]}')
        with urlopen('http://127.0.0.1:3010/', timeout=10) as response:
            require(response.status == 200, 'Marketing post-check failed.')
        result.update(complete=True, marketing_http=200,
                      protected_images_preserved=len(protected_images),
                      protected_containers_preserved=len(before_containers))
    finally:
        result['finished_at_utc'] = datetime.now(timezone.utc).isoformat()
        result['free_bytes_after'] = shutil.disk_usage(ROOT).free
        result['observed_free_byte_delta'] = result['free_bytes_after'] - result['free_bytes_before']
        RESULT.write_text(json.dumps(result, indent=2) + '\n')
    print('VERIFIED: obsolete image tags removed; protected images, containers and '
          'marketing preserved. See docs/rebuild/obsolete-image-cleanup-result.json.', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    execute() if args.execute else precheck()
