"""Deterministic two-lane core test plan and stdlib aggregate verification."""
import argparse
import hashlib
import json
from pathlib import Path
import re


def plan(classes):
    if not isinstance(classes, dict) or len(classes) < 2:
        raise ValueError('core_shards_need_at_least_two_classes')
    seen = set()
    for name, ids in classes.items():
        if not isinstance(name, str) or not name or not isinstance(ids, list) or not ids:
            raise ValueError('core_shard_class_invalid')
        for test_id in ids:
            if (not isinstance(test_id, str) or not test_id.startswith(name + '.')
                    or test_id in seen):
                raise ValueError('core_shard_test_id_invalid_or_duplicate')
            seen.add(test_id)
    # Stable count balance keeps whole TestCase fixtures together. No timing/history inputs.
    lanes = [[], []]
    for name in sorted(classes, key=lambda name: (-len(classes[name]), name)):
        lane = min(range(2), key=lambda i: (len(lanes[i]), i))
        lanes[lane].extend(classes[name])
    lanes = [sorted(ids) for ids in lanes]
    if not all(lanes) or set(lanes[0]) & set(lanes[1]) or set(lanes[0] + lanes[1]) != seen:
        raise ValueError('core_shard_coverage_invalid')
    return lanes


def manifest(classes, shard, selected, source_sha):
    if type(shard) is not int or shard not in (1, 2):
        raise ValueError('core_shard_index_invalid')
    if not isinstance(source_sha, str) or not re.fullmatch('[0-9a-f]{40}', source_sha):
        raise ValueError('core_shard_source_invalid')
    lanes = plan(classes)
    classes = {name: sorted(ids) for name, ids in sorted(classes.items())}
    if sorted(selected) != lanes[shard - 1]:
        raise ValueError('core_shard_selected_tests_differ')
    universe = sorted(lanes[0] + lanes[1])
    return {'format': 1, 'source_sha': source_sha, 'shard': shard, 'classes': classes,
            'selected': sorted(selected), 'universe_sha256': hashlib.sha256(
                json.dumps(universe, separators=(',', ':')).encode()).hexdigest()}


def verify_manifests(paths, source_sha):
    if len(paths) != 2:
        raise ValueError('core_shards_require_two_manifests')
    rows = [json.loads(Path(path).read_bytes()) for path in paths]
    if any(not isinstance(row, dict) or type(row.get('format')) is not int or row['format'] != 1
           for row in rows):
        raise ValueError('core_shard_manifest_format_invalid')
    if {row['shard'] for row in rows} != {1, 2}:
        raise ValueError('core_shard_manifest_index_mismatch')
    for row in rows:
        expected = manifest(row['classes'], row['shard'], row['selected'], source_sha)
        if row != expected:
            raise ValueError('core_shard_manifest_mismatch')
    if rows[0]['classes'] != rows[1]['classes']:
        raise ValueError('core_shard_discovery_universes_differ')
    lanes = plan(rows[0]['classes'])
    return {'tests': sum(map(len, lanes)), 'classes': len(rows[0]['classes']),
            'shard_counts': list(map(len, lanes)), 'universe_sha256': rows[0]['universe_sha256'],
            'source_sha': source_sha}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-sha', required=True)
    parser.add_argument('manifests', nargs=2)
    args = parser.parse_args()
    try:
        result = verify_manifests(args.manifests, args.source_sha)
    except (OSError, ValueError, KeyError, TypeError):
        parser.exit(1, 'core shards: REFUSED: discovery manifests do not prove complete disjoint coverage\n')
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
