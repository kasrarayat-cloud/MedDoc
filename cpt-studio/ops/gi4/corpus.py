"""H3: the generated corpus with truth tables, its second review, and the judge.

  python -m ops.gi4.corpus write OUT.jsonl [--quick]        the corpus (generated + seeded families), reviewed
  python -m ops.gi4.corpus tables                            documents and truth-table cells per level (MAY counted)
  python -m ops.gi4.corpus judge [--tree DIR | --base REF|DIR --head REF|DIR] [--workers N]
      the tree's readers against every MUST and SHOULD cell; with two trees, the differential (exit 1 when a MUST
      cell that passed on the base fails on the head)

The truth tables are PROVISIONAL author expectations; no qualified GI coder has reviewed them (truth.CODER_NOTE).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ops.gi4 import boot, gen, regression, seeds, truth

REPO_TEXT_DIRS = ('tests/corpus/services/documents', 'tests/fixtures/gi', 'tests/fixtures/gi3/live-text',
                  'tests/fixtures/gi3/upgrade', 'tests/fixtures/gi4/regression')


def generated(quick=False) -> list:
    docs = [truth.review(d) for d in gen.generate()]
    return docs[::20] if quick else docs


def seeded(quick=False) -> list:
    docs = [truth.review(d) for d in seeds.seeded(regression.load_fixtures())]
    return docs[::10] if quick else docs


def repo_texts() -> list:
    out = []
    for rel in REPO_TEXT_DIRS:
        for path in sorted((boot.HARNESS_TREE / rel).glob('*.txt')):
            out.append({'id': f'repo:{rel}/{path.name}', 'kind': 'repo', 'text': path.read_text(encoding='utf-8')})
    return out


def regression_texts() -> list:
    docs = regression.load_fixtures()
    out = []
    for doc_id, doc in docs.items():
        base = seeds.TRUTH.get(doc_id)
        t = {'date': base['date'], 'answers': {'D': base['date'], **base['never']}} if base else None
        out.append({'id': f'reg:{doc_id}', 'kind': 'regression', 'text': doc['text'], 'truth': t})
    return out


def extra_texts(paths) -> list:
    out, seen = [], set()
    for path in paths or ():
        with open(path, encoding='utf-8') as fh:
            for n, line in enumerate(fh):
                try:
                    text = json.loads(line)['text']
                except (ValueError, KeyError, TypeError):
                    continue
                digest = boot.sha256_text(text)
                if isinstance(text, str) and digest not in seen:
                    seen.add(digest)
                    out.append({'id': f'extra:{Path(path).name}:{n}', 'kind': 'extra', 'text': text})
    return out


def full_corpus(quick=False, extra=()) -> list:
    """Every text H2 reads: the regression texts, the generated corpus, the seeded families, the repository's own test
    texts and any extra JSONL corpora (one text per distinct content)."""
    docs, seen = [], set()
    for doc in regression_texts() + generated(quick) + seeded(quick) + repo_texts() + extra_texts(extra):
        digest = boot.sha256_text(doc['text'])
        if digest not in seen:
            seen.add(digest)
            docs.append(doc)
    return docs


def write(docs, path) -> None:
    with open(path, 'w', encoding='utf-8') as fh:
        for doc in docs:
            fh.write(json.dumps(doc, ensure_ascii=False, sort_keys=True) + '\n')


def load_observations(path) -> dict:
    with open(path, encoding='utf-8') as fh:
        return {r['id']: r for r in map(json.loads, fh)}


def observe_tree(tree: Path, corpus_path: Path, scratch: Path, label: str, *, readers: bool, workers: int) -> dict:
    out = scratch / f'observe-{label}.jsonl'
    boot.run_tool('observe', tree, ['--corpus', str(corpus_path), '--out', str(out), '--workers', str(workers)]
                  + (['--readers'] if readers else []), scratch=scratch, label=label)
    return load_observations(out)


def _print_rates(label, r):
    print(f'== {label}')
    for key, (ok, n) in r['by_kind'].items():
        print(f'  {key:34s} {ok:6d}/{n:<6d} {100 * ok / max(n, 1):5.1f}%')
    for key, (ok, n) in r['by_property'].items():
        print(f'    {key:58s} {ok:6d}/{n:<6d} {100 * ok / max(n, 1):5.1f}%')


def main(argv=None):
    parser = argparse.ArgumentParser(prog='python -m ops.gi4.corpus')
    parser.add_argument('action', choices=('write', 'tables', 'judge'))
    parser.add_argument('out', nargs='?')
    parser.add_argument('--quick', action='store_true')
    parser.add_argument('--tree')
    parser.add_argument('--base')
    parser.add_argument('--head')
    parser.add_argument('--workers', type=int, default=10)
    parser.add_argument('--scratch')
    parser.add_argument('--json-out', help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    docs = generated(args.quick) + seeded(args.quick)
    if args.action == 'write':
        write(docs, args.out or 'gi4-corpus.jsonl')
        print(f'{len(docs)} documents written to {args.out}')
        return 0
    if args.action == 'tables':
        print(json.dumps(truth.table_counts(docs), indent=1))
        print(truth.CODER_NOTE)
        return 0
    scratch = boot.scratch_dir(args.scratch)
    corpus_path = scratch / 'h3-corpus.jsonl'
    write(docs, corpus_path)
    by_id = {d['id']: d for d in docs}
    trees = ([('base', boot.tree_arg(args.base, scratch))] if args.base else
             [('tree', boot.tree_of(args, scratch))]) + ([('head', boot.tree_arg(args.head, scratch))] if args.head else [])
    judged = {}
    for label, tree in trees:
        obs = observe_tree(tree, corpus_path, scratch, label, readers=True, workers=args.workers)
        errors = [i for i, o in obs.items() if 'error' in o]
        judged[label] = truth.judge(by_id, obs)
        _print_rates(f'{label} {tree}: {len(obs)} documents, {len(errors)} reader errors', truth.rates(judged[label], by_id))
    print(truth.CODER_NOTE)
    if args.head:
        diff = truth.differential(judged['base'], judged['head'])
        print('== differential base -> head')
        regressed = 0
        for key, counts in diff['counts'].items():
            flag = '  <-- MUST REGRESSION' if key.startswith('MUST') and counts.get('regressed') else ''
            regressed += bool(flag)
            if counts.get('fixed') or counts.get('regressed') or flag:
                print(f'  {key:58s} fixed {counts.get("fixed", 0):5d} regressed {counts.get("regressed", 0):5d}{flag}')
        for key, ids in diff['examples'].items():
            print(f'     {key}: {ids}')
        print(f'  {"no movement" if not any(c.get("fixed") or c.get("regressed") for c in diff["counts"].values()) else ""}')
        return 1 if regressed else 0
    return 0


if __name__ == '__main__':
    sys.exit(main())
