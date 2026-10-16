#!/usr/bin/env python3
"""Replay retained Corti bytes privately. No provider calls or database imports."""
import argparse
from datetime import date
import hashlib
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.corti_response import DatedTerminology, adapt_response, load_icd_catalog
from corti_replay_preview import render_preview


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON field refused.')
        result[key] = value
    return result


def read_json(path):
    return json.loads(path.read_text(), object_pairs_hook=_object)


def hashes(directory):
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in directory.iterdir() if p.is_file()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence-dir', required=True, type=Path)
    parser.add_argument('--output-dir', required=True, type=Path)
    parser.add_argument('--service-date', required=True, type=date.fromisoformat)
    parser.add_argument('--icd-metadata', type=Path)
    parser.add_argument('--icd-file', type=Path)
    args = parser.parse_args()
    source, output = args.evidence_dir.resolve(), args.output_dir.absolute()
    if output.resolve() != output or output == source or output.is_relative_to(source) or source.is_relative_to(output):
        raise ValueError('Output must be a separate private directory, not an evidence directory or symlink.')
    os.umask(0o077)
    before = hashes(source)
    manifest = read_json(source / 'sha256-manifest.json')
    if any(before.get(name) != digest for name, digest in manifest.items()):
        raise ValueError('Original evidence manifest no longer matches; replay refused.')
    transport, request = read_json(source / 'transport.json'), read_json(source / 'request.json')
    if (before['response.raw.json'] != transport['response_sha256']
            or before['request.json'] != transport['request_sha256']):
        raise ValueError('Original request/response integrity failure.')
    original = read_json(source / 'evaluation.json')
    if original['overall'] != 'FAIL_RESPONSE_QUALITY_WITH_SELECTED_CODES_PASS':
        raise ValueError('Unexpected original verdict; this replay cannot replace it.')
    response = read_json(source / 'response.raw.json')
    releases = []
    if bool(args.icd_metadata) != bool(args.icd_file):
        raise ValueError('Supply both local ICD metadata and full catalogue, or neither.')
    if args.icd_metadata:
        releases.append(load_icd_catalog(args.icd_file, read_json(args.icd_metadata)))
    terminology = DatedTerminology(releases, unavailable_reasons={
        'cpt': 'No owner-authorized CPT catalogue and criteria covering this date are available to this replay. Original provider description retained, unverified.'})
    result = adapt_response(response, request, service_date=args.service_date, terminology=terminology,
                            original_verdict=original['overall'], source_response_sha256=before['response.raw.json'])
    expected = read_json(source / 'expected.local.json')['selected_codes']
    from core.corti_response import normalize_code
    required = {(system, normalize_code(system, code)) for system, codes in expected.items() for code in codes}
    actual = {(p['system'], p['code']) for p in result['proposed_selections']}
    replay_checks = {
        'selected_codes_match_original_expectations': actual == required and len(actual) == len(result['proposed_selections']),
        'all_selected_source_spans_intact': all(p['evidence_status'] == 'valid' for p in result['proposed_selections']),
        'candidates_retained_only_in_diagnostics': result['diagnostics']['candidates'] == response.get('candidates', []),
        'complete_provider_response_retained_in_diagnostics': result['diagnostics']['provider_response'] == response,
        'no_approval_or_activation': result['dashboard_activation_allowed'] is False and all(
            p['approved'] is False and p['selectable'] is False for p in result['proposed_selections']),
        'original_verdict': original['overall'], 'original_hashes_before': before,
    }
    output.mkdir(mode=0o700, parents=True, exist_ok=True)
    output.chmod(0o700)
    for filename, text in [('adapted-response.json', json.dumps(result, indent=2) + '\n'),
                           ('preview.html', render_preview(result, request))]:
        with (output / filename).open('x') as stream:
            stream.write(text)
    after = hashes(source)
    replay_checks['original_evidence_unchanged'] = before == after
    replay_checks['passed'] = all(value is True for key, value in replay_checks.items()
                                  if key not in {'original_verdict', 'original_hashes_before'})
    with (output / 'replay-verification.json').open('x') as stream:
        json.dump(replay_checks, stream, indent=2)
    if not replay_checks['passed']:
        raise SystemExit('Replay checks failed; original evidence preserved. Inspect replay-verification.json.')
    print(json.dumps({'replay_checks': 'PASS', 'provider_calls': 0,
                      'selected_codes': [p['code'] for p in result['proposed_selections']],
                      'original_verdict': original['overall'], 'preview': str(output / 'preview.html')}))


if __name__ == '__main__':
    main()
