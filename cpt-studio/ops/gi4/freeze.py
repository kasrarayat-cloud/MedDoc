"""H2: the request-side freeze and differential between two trees. A request is the document's text plus, when one is
known, one "Date of service" line, so the date the request carries is the only interpretation it sends; this tool shows
that a change moves nothing on that side (or only what its package declared).

(a) the sha256 of every cue pattern context.py or sections.py reads (their module-level patterns and constants, and every
    cues.* and symbols.* name they reference), and sections.layout identity (sections, sentences, clauses) per text;
(b) the date channel per text and member state, classified NEW-SEND (a date the base did not send), NEW-TAKE (a member
    answer the base did not take), NEW-HELD (an answer the base did not hold) and SEND->ASK (the base sent the document's
    date, the head asks); the gate is NEW-SEND = NEW-TAKE = 0, always;
(c) the request sha256 for the primary (no member answer) and every dated request;
(d) the analyze stage's mention counts (detect.service_mention_count, services.mention_count).
Every other movement must be declared (``--declare FILE``: {"cues_added": [...], "movements": {"CLASS": max}}); with no
declaration the expected delta is NONE, and any movement fails.

  python -m ops.gi4.freeze --base REF|DIR --head REF|DIR [--corpus FILE.jsonl ...] [--quick] [--declare FILE]
  python -m ops.gi4.freeze --tree DIR --cues --json-out FILE        (one tree's cue inventory; used by the above)
Each ref is exported with git archive into the scratch directory and read in a process of its own.
"""
from __future__ import annotations

import argparse
import ast
import collections
import hashlib
import inspect
import json
import re
import sys
import types
from pathlib import Path

from ops.gi4 import boot, corpus as corpus_mod

DATE_CLASSES = ('NEW-SEND', 'NEW-TAKE', 'NEW-HELD', 'SEND->ASK')
OTHER_CLASSES = ('LAYOUT-CHANGED', 'FACT-CHANGED', 'REQUEST-CHANGED', 'MENTIONS-CHANGED', 'STATE-CHANGED',
                 'TEXT-MISSING', 'READER-ERROR')
GATE = ('NEW-SEND', 'NEW-TAKE')


# --- (a) the cue inventory -------------------------------------------------------------------------------------------

def _canon(value, depth=0):
    """A JSON form of a constant (patterns with their flags), or None for what is no constant (functions, classes,
    modules, objects)."""
    if depth > 6:
        return ['deep']
    if isinstance(value, re.Pattern):
        return ['re', value.pattern if isinstance(value.pattern, str) else value.pattern.decode('latin-1'), value.flags]
    if isinstance(value, (bool, int, float, str)) or value is None:
        return ['v', value]
    if isinstance(value, bytes):
        return ['b', value.hex()]
    if isinstance(value, (tuple, list)):
        items = [_canon(v, depth + 1) for v in value]
        return None if any(i is None for i in items) else ['t', items]
    if isinstance(value, (set, frozenset)):
        items = [_canon(v, depth + 1) for v in value]
        return None if any(i is None for i in items) else ['s', sorted(json.dumps(i) for i in items)]
    if isinstance(value, dict):
        items = [[_canon(k, depth + 1), _canon(v, depth + 1)] for k, v in value.items()]
        return None if any(k is None or v is None for k, v in items) else ['d', sorted(json.dumps(i) for i in items)]
    if callable(value) and depth > 0:
        return ['fn', getattr(value, '__module__', ''), getattr(value, '__qualname__', repr(value))]
    return None


def _sha(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def cue_inventory(modules=None) -> dict:
    """{name: sha256} of every constant context.py and sections.py read: their own module-level constants
    ('context.X', 'sections.X') and every cues.* / symbols.* attribute their source references ('cues.X', 'symbols.X')."""
    if modules is None:
        from studio.gi import context, cues, sections
        from studio.ingest import symbols
        modules = {'context': context, 'sections': sections, 'cues': cues, 'symbols': symbols}
    out = {}
    for prefix in ('context', 'sections'):
        mod = modules[prefix]
        for name, value in vars(mod).items():
            if name.startswith('__') or isinstance(value, (types.ModuleType, type)) or inspect.isroutine(value):
                continue
            c = _canon(value)
            if c is not None:
                out[f'{prefix}.{name}'] = _sha(c)
        aliases = {'cues': 'cues', '_BOX_SYMBOLS': 'symbols', 'symbols': 'symbols'}
        for node in ast.walk(ast.parse(inspect.getsource(mod))):
            if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id in aliases:
                target = aliases[node.value.id]
                value = getattr(modules[target], node.attr, None)
                c = None if value is None else _canon(value)
                if c is None and value is not None and not inspect.isroutine(value):
                    c = ['repr', repr(value)]
                if c is not None:
                    out[f'{target}.{node.attr}'] = _sha(c)
    return dict(sorted(out.items()))


def compare_cues(base: dict, head: dict) -> dict:
    return {'changed': sorted(k for k in base if k in head and base[k] != head[k]),
            'removed': sorted(k for k in base if k not in head),
            'added': sorted(k for k in head if k not in base), 'count': [len(base), len(head)]}


# --- (b)-(d) the differential ----------------------------------------------------------------------------------------

def classify(base: dict, head: dict) -> tuple[collections.Counter, dict]:
    """Movement counts and up to five examples per class, base -> head, over the texts both observed."""
    counts, examples = collections.Counter(), collections.defaultdict(list)

    def note(cls, doc_id, detail):
        counts[cls] += 1
        if len(examples[cls]) < 5:
            examples[cls].append(f'{doc_id}: {detail}')

    for doc_id, b in base.items():
        h = head.get(doc_id)
        if h is None:
            note('TEXT-MISSING', doc_id, 'not observed on the head')
            continue
        if 'error' in b or 'error' in h:
            if b.get('error') != h.get('error'):
                note('READER-ERROR', doc_id, f"{b.get('error')} -> {h.get('error')}")
            continue
        if b['layout'] != h['layout']:
            note('LAYOUT-CHANGED', doc_id, 'sections.layout differs')
        if b['fact'] != h['fact']:
            note('FACT-CHANGED', doc_id, f"{b['fact'][:2]} -> {h['fact'][:2]}")
        if b['mentions'] != h['mentions']:
            note('MENTIONS-CHANGED', doc_id, f"{b['mentions']} -> {h['mentions']}")
        for label, bs in b['states'].items():
            hs = h['states'].get(label)
            if hs is None:
                note('STATE-CHANGED', doc_id, f'{label} not observed on the head')
                continue
            moved = False
            if hs['sends'] not in ('DATELESS', 'HELD') and hs['sends'] != bs['sends']:
                note('NEW-SEND', doc_id, f"{label}: {bs['sends']} -> {hs['sends']}")
                moved = True
            if hs['taken'] and not bs['taken']:
                note('NEW-TAKE', doc_id, f"{label}: {bs['answer']} taken")
                moved = True
            if hs['held'] and not bs['held']:
                note('NEW-HELD', doc_id, f"{label}: {bs['answer']} held ({bs['sends']} -> HELD)")
                moved = True
            if label == 'none' and bs['sends'] not in ('DATELESS', 'HELD') and hs['sends'] in ('DATELESS', 'HELD'):
                note('SEND->ASK', doc_id, f"{bs['sends']} -> {hs['sends']}")
                moved = True
            if hs['sends'] == bs['sends'] and hs['request'] != bs['request']:
                note('REQUEST-CHANGED', doc_id, f"{label}: {str(bs['request'])[:8]} -> {str(hs['request'])[:8]}")
                moved = True
            if not moved and (hs['sends'], hs['taken'], hs['held']) != (bs['sends'], bs['taken'], bs['held']):
                note('STATE-CHANGED', doc_id, f"{label}: {bs['sends']} -> {hs['sends']}")
    return counts, dict(examples)


def gate(cues: dict, counts: collections.Counter, declaration: dict) -> list:
    """The reasons the freeze fails (empty when it holds)."""
    reasons = []
    for cls in GATE:
        if counts.get(cls):
            reasons.append(f'{cls} = {counts[cls]} (the gate is {cls} = 0)')
    if cues['changed'] or cues['removed']:
        reasons.append(f"cue patterns changed {cues['changed']} / removed {cues['removed']}")
    undeclared = sorted(set(cues['added']) - set(declaration.get('cues_added', ())))
    if undeclared:
        reasons.append(f'cue patterns added and not declared: {undeclared}')
    allowed = declaration.get('movements', {})
    for cls, n in sorted(counts.items()):
        if cls not in GATE and n > allowed.get(cls, 0):
            reasons.append(f'{cls} = {n}, declared {allowed.get(cls, 0)}')
    return reasons


def main(argv=None):
    parser = argparse.ArgumentParser(prog='python -m ops.gi4.freeze')
    parser.add_argument('--base')
    parser.add_argument('--head')
    parser.add_argument('--tree')
    parser.add_argument('--cues', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--corpus', nargs='*', default=(), help='extra JSONL corpora ({"text": ...} per line)')
    parser.add_argument('--quick', action='store_true', help='a twentieth of the generated corpus')
    parser.add_argument('--declare', help='the package declaration (JSON); default: the expected delta is NONE')
    parser.add_argument('--workers', type=int, default=10)
    parser.add_argument('--scratch')
    parser.add_argument('--out', help='write the report (JSON) here')
    parser.add_argument('--json-out', help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.cues:
        boot.offline(args.tree)
        boot.write_json(args.json_out, cue_inventory())
        return 0
    if not (args.base and args.head):
        parser.error('--base and --head are required')
    scratch = boot.scratch_dir(args.scratch)
    trees = {'base': boot.tree_arg(args.base, scratch), 'head': boot.tree_arg(args.head, scratch)}
    declaration = json.loads(Path(args.declare).read_text(encoding='utf-8')) if args.declare else {}
    cues = compare_cues(*(boot.run_tool('freeze', trees[k], ['--cues'], scratch=scratch, label=f'cues-{k}')
                          for k in ('base', 'head')))
    docs = corpus_mod.full_corpus(quick=args.quick, extra=args.corpus)
    corpus_path = scratch / f'h2-corpus{"-quick" if args.quick else ""}.jsonl'
    corpus_mod.write(docs, corpus_path)
    obs = {k: corpus_mod.observe_tree(t, corpus_path, scratch, f'h2-{k}', readers=False, workers=args.workers)
           for k, t in trees.items()}
    counts, examples = classify(obs['base'], obs['head'])
    states = sum(len(o.get('states', {})) for o in obs['base'].values())
    requests = sum(1 for o in obs['base'].values() for s in o.get('states', {}).values() if s['request'])
    reasons = gate(cues, counts, declaration)
    print(f"== H2 freeze: base {trees['base']}\n               head {trees['head']}")
    print(f"(a) cue patterns read by context.py and sections.py: base {cues['count'][0]}, head {cues['count'][1]}; "
          f"changed {len(cues['changed'])}, removed {len(cues['removed'])}, added {len(cues['added'])}"
          + (f" {cues['added']}" if cues['added'] else ''))
    layout_n = counts.get('LAYOUT-CHANGED', 0)
    print(f'    sections.layout over {len(docs)} texts: {"identical" if not layout_n else f"{layout_n} differ"}')
    print(f'(b) date channel over {states} text x member states:', ', '.join(f'{c} {counts.get(c, 0)}'
                                                                              for c in DATE_CLASSES))
    print(f"(c) requests over {requests} primary and dated requests: changed {counts.get('REQUEST-CHANGED', 0)}")
    print(f"(d) mention counts over {len(docs)} texts: changed {counts.get('MENTIONS-CHANGED', 0)}")
    others = {c: counts.get(c, 0) for c in OTHER_CLASSES if counts.get(c)}
    if others:
        print('    other movements:', others)
    for cls, rows in examples.items():
        for row in rows:
            print(f'      {cls}: {row}')
    print('== GATE', 'HOLDS' if not reasons else 'FAILS: ' + '; '.join(reasons))
    if args.out:
        boot.write_json(args.out, {'cues': cues, 'texts': len(docs), 'states': states, 'requests': requests,
                                   'counts': dict(counts), 'examples': examples, 'gate': reasons,
                                   'trees': {k: str(v) for k, v in trees.items()}})
    return 1 if reasons else 0


if __name__ == '__main__':
    sys.exit(main())
