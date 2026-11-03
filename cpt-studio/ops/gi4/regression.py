"""The regression encounters (h4-01..h4-06, h2-08, h2-10): what the service read, what it retained, what the authors
expect, and the member states each one is replayed in.

Two sources give the same records:
- the raw regression inputs (``--inputs DIR``: live-text/, live-state/*.json and the two manifests, local files CI cannot
  read; h2-10's retained runs and text are given on their own with ``--h210-runs`` and ``--h210-text``), and
- the committed derived fixtures in tests/fixtures/gi4/regression/ (``<doc>.txt`` is the text the service read, and
  ``<doc>.json`` holds the walk's answer, the retained runs with their provider answers, the reference sources, the stored
  outcomes and the manifest expectations). ``python -m ops.gi4.regression derive --inputs DIR ...`` writes them, and
  refuses unless every text equals the request body the service sent and every request rebuilds to its stored sha256.
Every document is synthetic. No reviewer, encounter or run identifier is kept beyond an 8-character run label.
"""
from __future__ import annotations

import argparse
import base64
import datetime as dt
import json
import re
import sys
from pathlib import Path

from ops.gi4 import boot

FIXTURES = boot.HARNESS_TREE / 'tests' / 'fixtures' / 'gi4' / 'regression'
# document id -> the file stem the regression inputs use
DOCS = {'h4-01': 'Pasted_note_2026-10-31_1258', 'h4-02': 'h4-02', 'h4-03': 'h4-03', 'h4-04': 'h4-04', 'h4-05': 'h4-05',
        'h4-06': 'h4-06.scanned', 'h2-08': 'h2-08-hepatology-note'}
ALL_DOCS = tuple(DOCS) + ('h2-10',)
MANIFEST_KEYS = ('class', 'expected_context', 'expected_routing', 'expected_clarifications', 'must_not_code',
                 'incomplete_services', 'review_plan')
SOURCE_FIELDS = ('key', 'kind', 'publisher', 'title', 'release', 'url', 'sha256', 'effective_start', 'effective_end',
                 'license_note', 'scope_note')
FAR_DATE = '1998-01-01'  # a member answer no document states


class Missing(Exception):
    """The regression inputs are not where the caller said (CI has no access to them)."""


# --- dates the harness reads itself (never through the tree under test, so both trees get the same member states) ---

_MONTHS = ('jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec')
_DATE = re.compile(r'(?<![\w/-])(?:(?P<iy>(?:19|20)\d\d)-(?P<im>\d\d)-(?P<id>\d\d)'
                   r'|(?P<um>\d{1,2})/(?P<ud>\d{1,2})/(?P<uy>(?:19|20)\d\d)'
                   r'|(?P<mn>jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?[ \t]+(?P<md>\d{1,2}),?[ \t]+'
                   r'(?P<my>(?:19|20)\d\d))(?![\w/-])', re.I)


def documented_dates(text: str) -> list[str]:
    """Every calendar date the text writes in a full form (ISO, m/d/yyyy, 'Month d, yyyy'), in order, once each."""
    seen = []
    for m in _DATE.finditer(text):
        try:
            if m.group('iy'):
                day = dt.date(int(m.group('iy')), int(m.group('im')), int(m.group('id')))
            elif m.group('uy'):
                day = dt.date(int(m.group('uy')), int(m.group('um')), int(m.group('ud')))
            else:
                day = dt.date(int(m.group('my')), _MONTHS.index(m.group('mn').lower()[:3]) + 1, int(m.group('md')))
        except ValueError:
            continue
        if day.isoformat() not in seen:
            seen.append(day.isoformat())
    return seen


def member_states(doc: dict) -> list[tuple[str, str | None]]:
    """(label, member answer) for every state a document is replayed in: none; the walk's answer; each documented date;
    a date no document states; one day either side of the anchor (the walk's answer, else the first documented date);
    a plan date (the first documented date after the anchor, else the anchor plus 28 days). One state per answer."""
    dates = documented_dates(doc['text'])
    anchor = doc.get('walk_answer') or (dates[0] if dates else None)
    states = [('none', None)]
    if doc.get('walk_answer'):
        states.append(('walk', doc['walk_answer']))
    states += [(f'doc:{d}', d) for d in dates]
    states.append(('far', FAR_DATE))
    if anchor:
        a = dt.date.fromisoformat(anchor)
        later = [d for d in dates if d > anchor]
        states += [('minus1', (a - dt.timedelta(days=1)).isoformat()), ('plus1', (a + dt.timedelta(days=1)).isoformat()),
                   ('plan', later[0] if later else (a + dt.timedelta(days=28)).isoformat())]
    out, seen = [], set()
    for label, answer in states:
        if answer not in seen:
            seen.add(answer)
            out.append((label, answer))
    return out


# --- loading ---------------------------------------------------------------------------------------------------------

def load_fixtures(directory: Path = FIXTURES) -> dict[str, dict]:
    docs = {}
    for doc_id in ALL_DOCS:
        record = json.loads((directory / f'{doc_id}.json').read_text(encoding='utf-8'))
        record['text'] = (directory / f'{doc_id}.txt').read_text(encoding='utf-8')
        if boot.sha256_text(record['text']) != record['text_sha256']:
            raise ValueError(f'{doc_id}: the committed text does not match its recorded sha256')
        docs[doc_id] = record
    return docs


def _run_record(run: dict, response_bytes: bytes) -> dict:
    return {'run': str(run.get('id') or run.get('run_id'))[:8], 'service_date': run.get('service_date'),
            'state': run.get('state'), 'sent': run.get('sent'), 'purpose': run.get('purpose'),
            'request_sha256': run.get('request_sha256') or '',
            'response': json.loads(response_bytes) if response_bytes else None}


def _manifest_entry(manifest: dict, doc_id: str) -> dict:
    for entry in manifest.get('documents', []):
        if entry.get('id') == doc_id:
            out = {k: entry.get(k) for k in MANIFEST_KEYS}
            out['author_codes'] = [c['code'] for c in (entry.get('author_expected_cpt') or {}).get('codes', [])]
            out['source_sha256'] = entry.get('source_sha256')
            return out
    return {}


def load_inputs(directory, h210_runs=None, h210_text=None) -> dict[str, dict]:
    """The records from the raw regression inputs. Raises Missing when ``directory`` is absent."""
    root = Path(directory) if directory else None
    if root is None or not (root / 'live-text').is_dir() or not (root / 'live-state').is_dir():
        raise Missing(f'regression inputs not found at {directory!r} (CI has no access to them)')
    manifests = {}
    for name in ('h4-sealed-manifest.json', 'h2-08-walk-manifest.json'):
        if (root / name).is_file():
            manifests[name] = json.loads((root / name).read_text(encoding='utf-8'))
    docs = {}
    for doc_id, stem in DOCS.items():
        text = (root / 'live-text' / f'{stem}.txt').read_bytes().decode('utf-8')
        state = json.loads((root / 'live-state' / f'{stem}.json').read_text(encoding='utf-8'))
        runs = sorted(state['runs'], key=lambda r: r['run']['created_at'])
        current = state['encounter'].get('current_assessment_id')
        stored_props = [p for p in state.get('proposals') or [] if p.get('assessment_id') == current]
        proposals_by_id = {p['id']: p for p in state.get('proposals') or []}
        sources = [{k: s.get(k, '') for k in SOURCE_FIELDS} for s in state['assessments'][0]['reference_sources']
                   if s.get('connected')]
        manifest = _manifest_entry(manifests.get('h2-08-walk-manifest.json' if doc_id == 'h2-08'
                                                 else 'h4-sealed-manifest.json', {}), doc_id)
        docs[doc_id] = {
            'id': doc_id, 'text': text, 'text_sha256': boot.sha256_text(text),
            'walk_answer': (state['encounter'].get('user_values') or {}).get('service_date'),
            'runs': [_run_record(r['run'], base64.b64decode(r['response_b64']) if r.get('response_b64') else b'')
                     for r in runs],
            'request_texts_equal': all(((r['run'].get('request_body') or {}).get('context') or [{'text': text}])[0]
                                       ['text'] == text for r in runs),
            'reference_sources': sources,
            'stored': {
                'contexts': [[c['version'], c['facts']['service_date']['origin'], c['facts']['service_date']['value']]
                             for c in sorted(state.get('contexts') or [], key=lambda c: c['created_at'])],
                'proposals': sorted([p['code'], p['bucket'], p['status'], p['fingerprint'][:8]] for p in stored_props),
                'open_clarifications': sorted([q['scope'], q['family'], q['fact']] for q in state.get('clarifications') or []
                                              if q.get('state') == 'open'),
                'decisions': [[d['action'], (proposals_by_id.get(d['proposal_id']) or {}).get('code', ''),
                               d['proposal_fingerprint'][:8]] for d in state.get('decisions') or []],
                'state': state['encounter'].get('state'),
            },
            'manifest': manifest,
        }
    if h210_runs:
        rows = json.loads(Path(h210_runs).read_text(encoding='utf-8'))
        sent = [r for r in rows if r.get('request_body')]
        text = sent[0]['request_body']['context'][0]['text']
        if h210_text is not None and Path(h210_text).read_text(encoding='utf-8') != text:
            raise ValueError('h2-10: the given text differs from the text its request carried')
        docs['h2-10'] = {
            'id': 'h2-10', 'text': text, 'text_sha256': boot.sha256_text(text), 'walk_answer': None,
            'runs': [_run_record(r, base64.b64decode(r['response_b64']) if r.get('response_b64') else b'')
                     for r in sorted(rows, key=lambda r: r['created_at'])],
            'request_texts_equal': all(r['request_body']['context'][0]['text'] == text for r in sent),
            'reference_sources': docs['h4-04']['reference_sources'],
            'stored': {'contexts': [], 'proposals': [], 'open_clarifications': [], 'decisions': [], 'state': ''},
            'manifest': {},
        }
    return docs


def derive(docs: dict, out: Path) -> None:
    """Write the committed fixtures from raw records, after checking each text against its request bodies."""
    from studio.providers.corti import ADAPTER_VERSION, build_coding_request
    out.mkdir(parents=True, exist_ok=True)
    for doc_id, record in docs.items():
        if not record.pop('request_texts_equal', True):
            raise SystemExit(f'{doc_id}: a stored request body carries another text')
        for run in record['runs']:
            if not run['request_sha256']:
                continue
            day = dt.date.fromisoformat(run['service_date']) if run['service_date'] else None
            sha = build_coding_request('corti', ADAPTER_VERSION, record['text'], day, 10 ** 8).canonical_sha256
            if sha != run['request_sha256']:
                raise SystemExit(f'{doc_id}: run {run["run"]} does not rebuild to its stored request sha256')
        text = record.pop('text')
        (out / f'{doc_id}.txt').write_text(text, encoding='utf-8')
        boot.write_json(out / f'{doc_id}.json', record)
        record['text'] = text
    print(f'wrote {len(docs)} documents to {out}')


def main(argv=None):
    parser = argparse.ArgumentParser(prog='python -m ops.gi4.regression')
    parser.add_argument('action', choices=('derive', 'check'))
    parser.add_argument('--inputs', help='the regression inputs directory (local only)')
    parser.add_argument('--h210-runs', help="h2-10's retained runs (JSON)")
    parser.add_argument('--h210-text', help="h2-10's source text, checked against its request body")
    parser.add_argument('--out', default=str(FIXTURES))
    parser.add_argument('--tree')
    parser.add_argument('--json-out')
    args = parser.parse_args(argv)
    try:
        docs = load_inputs(args.inputs, args.h210_runs, args.h210_text)
    except Missing as exc:
        print(f'SKIPPED: {exc}')
        return 0
    boot.offline(args.tree)
    if args.action == 'derive':
        derive(docs, Path(args.out))
        return 0
    committed = load_fixtures(Path(args.out))
    bad = []
    for doc_id, record in docs.items():
        record.pop('request_texts_equal', None)
        diffs = boot.differences(committed.get(doc_id), record, doc_id)
        bad += diffs
    print('\n'.join(bad) or f'the committed fixtures equal the regression inputs ({len(docs)} documents)')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
