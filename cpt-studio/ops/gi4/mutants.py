"""H6: the mutant battery. One killing mutant per guard, applied to a COPY of a sealed export (never to a worktree and
never to a file anyone is editing), with the sha256 printed after the mutation is applied and again after it is
restored, and the restore compared with the original bytes.

A mutant names the guard it removes, one exact anchor (it must occur exactly once, or nothing is applied and the
mutant counts as NOT RUN, never as killed), its replacement, and its detector:
  unit:LABEL    the Django test LABEL (SimpleTestCase only: no database) fails on the mutant
  state:LABEL   the Django test LABEL fails on the mutant, on the throwaway test database (127.0.0.1:55461 only)
  replay        the H1 replay differs from the unmutated tree's
  freeze        the H2 freeze gate fails (base: the unmutated tree, head: the mutant)
  battery       the H4 battery shows a movement no declaration names
Every detector first runs on the unmutated copy and must pass there: a detector that fails without the mutation proves
nothing (a failing baseline turns every mutant into a false kill).

  python -m ops.gi4.mutants --base REF|DIR [--only NAME ...] [--scratch DIR]
"""
from __future__ import annotations

import argparse
import contextlib
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from ops.gi4 import boot


@dataclass(frozen=True)
class Mutant:
    name: str
    guard: str
    path: str  # relative to the cpt-studio directory
    old: str
    new: str
    detector: str


MUTANTS = (
    # --- package PS: the shared helpers (killed by their own unit tests) ---
    Mutant('ps-head-lines-blank', 'head_lines_end skips whitespace-only lines', 'studio/gi/sections.py',
           '        if _NON_BLANK.search(text, start, end):\n            count, found = count + 1, end',
           '        if True:\n            count, found = count + 1, end',
           'unit:tests.test_gi4_sections'),
    Mutant('ps-procedure-head-reach', 'procedure_report_head reads the head only', 'studio/gi/sections.py',
           '    return end > 0 and PROCEDURE_HEAD.search(text, 0, end) is not None',
           '    return PROCEDURE_HEAD.search(text) is not None', 'unit:tests.test_gi4_sections'),
    Mutant('ps-around-title-field', 'around_procedure_title: a field is no title', 'studio/gi/sections.py',
           '                    and not _TITLE_FIELD.search(line) and AROUND_PROCEDURE_WORDS.search(line):',
           '                    and AROUND_PROCEDURE_WORDS.search(line):', 'unit:tests.test_gi4_sections'),
    Mutant('ps-around-title-sentence', 'around_procedure_title: a sentence is no title', 'studio/gi/sections.py',
           "            if line and len(line) <= AROUND_PROCEDURE_TITLE_CHARS and line[-1] not in '.!?;,' \\",
           '            if line and len(line) <= AROUND_PROCEDURE_TITLE_CHARS \\', 'unit:tests.test_gi4_sections'),
    Mutant('ps-under-occurrence-head', 'under_another_occurrence reads the heading-like line above',
           'studio/gi/sections.py',
           '            return bool(ANOTHER_OCCURRENCE_HEAD.search(line))\n        end = start - 1\n    return False\n\n\n'
           'HEADING_REACH_LINES',
           '            return False\n        end = start - 1\n    return False\n\n\nHEADING_REACH_LINES',
           'unit:tests.test_gi4_sections'),
    Mutant('ps-beyond-reach-fail-closed', 'beyond_heading_reach fails closed past its reach', 'studio/gi/sections.py',
           '    if pos - lo > HEADING_REACH_CHARS:\n        return True',
           '    if pos - lo > HEADING_REACH_CHARS:\n        return False', 'unit:tests.test_gi4_sections'),
    Mutant('ps-beyond-reach-heading-like', 'beyond_heading_reach finds an unread heading-like line',
           'studio/gi/sections.py',
           "                and all(w[:1].isupper() for w in _HEADING_WORD.findall(line) if len(w) >= 4):\n"
           "            return True",
           "                and all(w[:1].isupper() for w in _HEADING_WORD.findall(line) if len(w) >= 4):\n"
           "            return False", 'unit:tests.test_gi4_sections'),
    # --- H1's three planted controls (the replay must differ on each) ---
    Mutant('ctl-date-charge-answer', "the charge-block question takes only the installed reading's date",
           'studio/gi/context.py', "if value == own else", "if True else", 'replay'),
    Mutant('ctl-routing-elsewhere-order', "routing's order of another encounter's statuses", 'studio/gi/detect.py',
           "ELSEWHERE_ORDER = ('negated', 'historical', 'planned')",
           "ELSEWHERE_ORDER = ('planned', 'historical', 'negated')", 'replay'),
    Mutant('ctl-request-date-line', "the request's date line", 'studio/providers/corti.py',
           "(text, f'Date of service: {service_date.isoformat()}')",
           "(text, f'Service date: {service_date.isoformat()}')", 'replay'),
    # --- H2's gates ---
    Mutant('freeze-member-differs-is-conflict', 'a member date differing from the documented one is a conflict',
           'studio/gi/context.py', '                and str(documented.value) != value:',
           '                and str(documented.value) != value and False:', 'freeze'),
    Mutant('freeze-cue-pattern', 'a cue pattern sections.py reads (cues.PROCEDURE_TITLE)', 'studio/gi/cues.py',
           r"(?:procedure\s+)?(?:report|note)$')", r"(?:procedure\s+)?(?:report|note|summary)$')", 'freeze'),
    Mutant('freeze-heading-length', "the layout's heading length limit", 'studio/gi/sections.py',
           '    if not raw.strip() or len(raw) > 60:\n        return None\n    label = normalize_label(raw)',
           '    if not raw.strip() or len(raw) > 24:\n        return None\n    label = normalize_label(raw)', 'freeze'),
    Mutant('freeze-mention-count', "the analyze stage's mention count", 'studio/gi/detect.py',
           '    return len(_service_mentions(text))\n', '    return len(_service_mentions(text)) // 2\n', 'freeze'),
    # --- H4's code-level guard ---
    Mutant('battery-exclusion-needs-agreement', 'an exclusion needs the second reader to agree', 'studio/validation/engine.py',
           '    return not _second_reading(outcome, text, day, pages)\n', '    return True\n', 'battery'),
    # --- H5's state guards (the throwaway test database) ---
    Mutant('state-reuse-retained', 'an identical retained request is reused, never sent again', 'studio/jobs.py',
           "    ).order_by('created_at').first()\n    if prior is not None:\n        run = models.ProviderRun.objects.create(",
           "    ).order_by('created_at').first()\n    if False:\n        run = models.ProviderRun.objects.create(",
           'state:tests.test_gi4_state'),
    Mutant('state-upgrade-predict-never-sends', "an upgrade's own predict never sends", 'studio/jobs.py',
           '    if job.idempotency_key == _upgrade_predict_key(context):\n        # Refutation r1',
           '    if False:\n        # Refutation r1', 'state:tests.test_gi4_state'),
)
REPLAY_CONTROLS = ('ctl-date-charge-answer', 'ctl-routing-elsewhere-order', 'ctl-request-date-line')
BY_NAME = {m.name: m for m in MUTANTS}


@contextlib.contextmanager
def applied(tree, name: str, scratch: Path):
    """A copy of ``tree`` (the cpt-studio directory of a sealed export) with mutant ``name`` applied; yields the copy's
    path. Prints the sha256 after applying and after restoring; the copy is removed afterwards."""
    mutant = BY_NAME[name]
    source = Path(tree)
    copy_root = scratch / f'mutant-{name}-{os.getpid()}'
    if copy_root.exists():
        boot.unseal(copy_root)
        shutil.rmtree(copy_root)
    shutil.copytree(source, copy_root / 'cpt-studio', symlinks=True)
    boot.unseal(copy_root)
    target = copy_root / 'cpt-studio' / mutant.path
    original = target.read_bytes()
    before = boot.sha256_file(target)
    text = original.decode('utf-8')
    count = text.count(mutant.old)
    if count != 1:
        shutil.rmtree(copy_root)
        raise RuntimeError(f'[{name}] anchor found {count} times (expected exactly 1): NOT RUN')
    mutated = text.replace(mutant.old, mutant.new, 1)
    marker = mutant.new
    target.write_text(mutated, encoding='utf-8')
    applied_ok = marker in target.read_text(encoding='utf-8')
    print(f'[{name}] mutation applied: {applied_ok}; sha256 {before[:16]} -> {boot.sha256_file(target)[:16]} '
          f'({mutant.path})', flush=True)
    if not applied_ok:
        shutil.rmtree(copy_root)
        raise RuntimeError(f'[{name}] the mutation did not apply: NOT RUN')
    try:
        yield copy_root / 'cpt-studio'
    finally:
        target.write_bytes(original)
        after = boot.sha256_file(target)
        print(f'[{name}] restored: {after == before} (sha256 {after[:16]})', flush=True)
        shutil.rmtree(copy_root)
        if after != before:
            raise RuntimeError(f'[{name}] the restore does not match the original bytes')


def _django_env(state: bool, scratch: Path) -> dict:
    env = {k: v for k, v in os.environ.items() if k not in ('PYTHONPATH', 'PYTHONHOME', 'PYTHONSTARTUP')}
    env.update(boot.OFFLINE_ENV)
    env.update({'PYTHONDONTWRITEBYTECODE': '1', 'CPT_STUDIO_STATE_DIR': str(scratch)})
    if state:  # the throwaway test database: never the live port
        env.update({'CPT_STUDIO_DB_PORT': '55461', 'CPT_STUDIO_TEST_DB_SUFFIX': 'gi4mut'})
    else:  # no database at all: a closed port, so any query fails loudly
        env.update({'CPT_STUDIO_DB_PORT': '9', 'CPT_STUDIO_TEST_DB_SUFFIX': 'gi4none'})
    assert env['CPT_STUDIO_DB_PORT'] != boot.LIVE_DB_PORT
    return env


def detect(mutant: Mutant, tree: Path, base: Path, scratch: Path) -> tuple[bool, str]:
    """(failed, tail of the output) for the mutant's detector on ``tree`` (``base``: the unmutated tree)."""
    kind, _, label = mutant.detector.partition(':')
    if kind in ('unit', 'state'):
        cmd = [sys.executable, '-B', 'manage.py', 'test', label, '--noinput']
        done = subprocess.run(cmd, cwd=tree, env=_django_env(kind == 'state', scratch), capture_output=True,
                              text=True, timeout=3600)
    else:
        args = {'replay': ['--fixtures'], 'freeze': ['--quick'], 'battery': []}[kind]
        cmd = [sys.executable, '-B', '-m', f'ops.gi4.{kind}', '--base', str(base), '--head', str(tree), *args,
               '--scratch', str(scratch)]
        env = {k: v for k, v in os.environ.items() if k not in ('PYTHONPATH', 'PYTHONHOME', 'PYTHONSTARTUP')}
        env['PYTHONDONTWRITEBYTECODE'] = '1'
        done = subprocess.run(cmd, cwd=boot.HARNESS_TREE, env=env, capture_output=True, text=True, timeout=3600)
    tail = (done.stdout + done.stderr).strip().splitlines()[-12:]
    return done.returncode != 0, '\n'.join(tail)


def main(argv=None):
    parser = argparse.ArgumentParser(prog='python -m ops.gi4.mutants')
    parser.add_argument('--base', required=True, help='git ref or cpt-studio directory to mutate copies of')
    parser.add_argument('--only', nargs='*', default=())
    parser.add_argument('--scratch')
    parser.add_argument('--list', action='store_true')
    args = parser.parse_args(argv)
    if args.list:
        for m in MUTANTS:
            print(f'{m.name:36s} {m.detector:34s} {m.guard}')
        return 0
    scratch = boot.scratch_dir(args.scratch)
    base = Path(args.base).resolve() if Path(args.base).is_dir() else boot.export_ref(args.base, scratch)
    chosen = [m for m in MUTANTS if not args.only or m.name in args.only]
    baselines, results = {}, []
    for mutant in chosen:
        t0 = time.time()
        if mutant.detector not in baselines:
            failed, tail = detect(mutant, base, base, scratch)
            baselines[mutant.detector] = not failed
            print(f'baseline {mutant.detector}: {"passes" if not failed else "FAILS (its mutants prove nothing)"}')
            if failed:
                print(tail)
        if not baselines[mutant.detector]:
            results.append((mutant.name, 'NOT RUN (failing baseline)'))
            continue
        try:
            with applied(base, mutant.name, scratch) as tree:
                failed, tail = detect(mutant, tree, base, scratch)
        except RuntimeError as exc:
            results.append((mutant.name, f'NOT RUN: {exc}'))
            continue
        verdict = 'KILLED' if failed else 'SURVIVED'
        results.append((mutant.name, verdict))
        print(f'[{mutant.name}] {verdict} by {mutant.detector} in {time.time() - t0:.0f}s')
        if not failed:
            print(tail)
    print('\n== mutant battery')
    for name, verdict in results:
        print(f'  {name:36s} {verdict}')
    killed = sum(v == 'KILLED' for _, v in results)
    print(f'  {killed} of {len(results)} killed')
    return 0 if killed == len(results) else 1


if __name__ == '__main__':
    sys.exit(main())
