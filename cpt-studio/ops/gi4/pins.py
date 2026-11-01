"""The committed pins the gi4 tests compare the current tree with (tests/fixtures/gi4/pins/), written from a SEALED
export of the installed tree, never from a working tree:

  python -m ops.gi4.pins --tree <export of 80df1831d168>/cpt-studio

replay.json   H1's compact reading of every regression encounter in every member state
cues.json     H2(a)'s sha256 of every cue pattern context.py and sections.py read
freeze.json   H2's per-text digest (layout, date channel, requests, mention counts) over the CI corpus
battery.json  H4's outcome of every permanent row
tables.json   H3's corpus size and truth-table cell counts
A package that moves any of them re-pins in the same commit as its declaration, and says which movement each re-pin is.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys

from ops.gi4 import boot

PINS = boot.HARNESS_TREE / 'tests' / 'fixtures' / 'gi4' / 'pins'


def compact_replay(result: dict) -> dict:
    """What H1 pins per document and state: the date channel, the request, routing, the inventory's statuses, every
    proposal's bucket and status, the questions, the offers and completeness."""
    out = {}
    for doc_id, rec in result['documents'].items():
        states = {}
        for label, st in rec['states'].items():
            states[label] = {
                'answer': st['answer'], 'sends': st['sends'], 'taken': st['taken'], 'held': st['held'],
                'request': (st['request_sha256'] or '')[:16], 'response': st['response'].split(':')[0],
                'routing': {f: [r['status'], sorted(x[0] + '=' + str(x[1]) for x in r['facts'])]
                            for f, r in st['routing'].items()},
                'inventory': [[s['family'], s['status'], s['completion'], s['extent']] for s in st['inventory']],
                'proposals': sorted([p['code'], p['bucket'], p['status'], p['fingerprint'][:12]]
                                    for p in st['proposals'] if p['bucket'] != 'alternative'),
                'questions': sorted([q[0], q[1], q[2]] for q in st['clarifications']),
                'offers': sorted([o['family'], o['reason'], bool(o['second_review'])] for o in st['offers']),
                'completeness': [st['completeness']['state'], st['completeness']['unresolved']]}
        out[doc_id] = {'fact': [rec['fact']['origin'], rec['fact']['value']], 'states': states,
                       'failed_hard': sorted(e['id'] for e in rec['expectations'] if e['level'] == 'HARD'
                                             and not e['ok'])}
    return out


def ci_corpus() -> list:
    """The small corpus the committed freeze test reads: the regression texts, every 40th generated document, every
    20th seeded variant and the repository's own test texts."""
    from ops.gi4 import corpus
    docs, seen = [], set()
    for doc in (corpus.regression_texts() + corpus.generated()[::40] + corpus.seeded()[::20] + corpus.repo_texts()):
        digest = boot.sha256_text(doc['text'])
        if digest not in seen:
            seen.add(digest)
            docs.append(doc)
    return docs


def freeze_digests(docs, m) -> dict:
    from ops.gi4 import observe
    out = {}
    for doc in docs:
        rec = observe.text_record(m, doc['text'], doc.get('truth'))
        out[doc['id']] = hashlib.sha256(json.dumps(rec, sort_keys=True).encode()).hexdigest()
        m['jobs'].release_routing_caches()
    return out


def compact_battery(result: dict) -> dict:
    return {name: {code: [p['bucket'], p['status'], p['violations']] for code, p in row['proposals'].items()}
            for name, row in result.items()}


def main(argv=None):
    parser = argparse.ArgumentParser(prog='python -m ops.gi4.pins')
    parser.add_argument('--tree', required=True, help='a sealed export of the installed cpt-studio tree')
    args = parser.parse_args(argv)
    tree = boot.offline(args.tree)
    from ops.gi4 import battery, corpus, freeze, observe, regression, replay, truth
    PINS.mkdir(parents=True, exist_ok=True)
    mark = tree.parent / boot.EXPORT_MARK
    if not mark.is_file():
        raise SystemExit('pins are written from a sealed export (python -m ops.gi4.pins --tree <export>/cpt-studio)')
    meta = {'commit': mark.read_text().strip()}
    boot.write_json(PINS / 'replay.json', {'meta': meta, 'documents': compact_replay(
        replay.replay(regression.load_fixtures()))})
    boot.write_json(PINS / 'cues.json', {'meta': meta, 'cues': freeze.cue_inventory()})
    docs = ci_corpus()
    boot.write_json(PINS / 'freeze.json', {'meta': meta, 'texts': len(docs),
                                           'digests': freeze_digests(docs, observe._modules())})
    boot.write_json(PINS / 'battery.json', {'meta': meta, 'rows': compact_battery(battery.run())})
    boot.write_json(PINS / 'tables.json', {'meta': meta, 'tables': truth.table_counts(corpus.generated()
                                                                                      + corpus.seeded())})
    print(f'pins written to {PINS} from {tree}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
