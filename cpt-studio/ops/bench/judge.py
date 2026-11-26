"""The bench's judge (RELEASE-2-SPEC R2-2 and section 8): PASS, FAIL or INVALID for B against A, from the rounds in an
output folder and the table in acceptance.json. No Django, no database, no browser: ops/test_bench.py drives it.

    python3 judge.py verdict --out <folder> --a A --b B [--acceptance acceptance.json] [--control]
    python3 judge.py spread  --out <folder> --a A:1 --a A:2      # the A/A spread of every metric, from a valid pair
    python3 judge.py floors  --out <folder> --a A:1 --a A:2 --source TEXT [--acceptance acceptance.json] [--check]
        # acceptance.json with every A-derived value (the recorded A, its spread, the floors, the gain spreads) from
        # a valid A/A pair, printed whole (or, with --check, compared byte for byte with the committed table)

The rounds of a folder: for each tag, base round (round mod 100) and part group, the first attempt that is valid on
its own (attempt_reasons), else the newest; a later attempt never replaces a valid one. A round's files are merged:
metrics pooled, each check and control ANDed across the files that recorded it.

INVALID means "run again", never a pass or a fail. It is answered when (section 8):
- the two trees' app.js hashes are equal (unless --control: A against A on purpose), a tag's files come from more than
  one tree, or A's files are not the release-1 revision the table names;
- any answer had an unexpected status, or any page logged a console error, or a request left loopback;
- the load average was above 8 before, during or after a round;
- release 1's own value differs from its reference - lane M's recorded A (else section 8's figure), on every row whose
  A is read - by more than the larger of 20%, twice the row's own A/A spread and one step of its instrument;
- a row has too few samples (A's too, wherever A is read); a round's control is missing or failed; a part of a round
  failed with an error, or an operation never finished;
- a row needs a derived value the table does not carry (a floor, a gain spread: the table is not derived yet).
Otherwise each gated row is judged on the pooled median of its samples (or its stated statistic):
- an absolute limit is the number;
- a limit relative to A uses A measured in the same session, and a "no worse than A" limit (factor >= 1) is never
  tighter than A x (1 + 2 x that metric's recorded A/A spread): the floor_factor acceptance.json carries, derived
  before any B was measured (judge.py floors), never at run time (C5); and on a row with an instrument step (a_step),
  never below A + one step (judge[5]);
- a gain - wherever a limit lies below A (above it for a rate) - counts only when it exceeds twice the A/A spread, on
  every row that reads A (a needs_a-false row is judged on its absolute limit alone: judge[2]).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROUND_RE = re.compile(r'^(?P<tag>[A-Za-z][A-Za-z0-9_]{0,15})-r(?P<round>\d+)-'
                      r'(?P<parts>[a-z+-]+(?:@[A-Z0-9+]+)?)\.json$')
MAX_LOAD = 8.0
A_TOLERANCE = 0.20
ROUND_PROFILES = ('P0', 'P1', 'P2', 'P3')  # a round file without its own profiles ran them all (bench_run.PROFILES)
PROFILE_PARTS = ('open', 'lists')  # bench_run's only parts that read the round's profiles


# --- reading rounds ---------------------------------------------------------------------------------------------------

def file_profiles(name: str) -> tuple:
    """The profiles a round file's part group ran: its own (open@P0, lists@P1+P2), else every one."""
    m = ROUND_RE.match(name)
    parts = m.group('parts') if m else ''
    return tuple(parts.split('@', 1)[1].split('+')) if '@' in parts else ROUND_PROFILES


def coverage(name: str, data: dict) -> set:
    """What one round file measured, whatever its group is called: (part, profile) for open and lists, (part, '*')
    for every other part, which runs alike whatever profiles it is given (office and office@P0 are one measurement)."""
    profiles = file_profiles(name)
    return {(part, p) for part in data.get('parts', []) for p in (profiles if part in PROFILE_PARTS else ('*',))}


def attempt_reasons(name: str, data: dict, controls=(), revision=None) -> list:
    """Why one round file is INVALID on its own: invalid_reasons' round rules applied to this file alone (a load sample
    above 8, a failed part, an unexpected status, a console error, a request off loopback, an operation that never
    finished), and the controls where this file's open part ran at P0, the only profile that plants them. The driver
    keeps or runs again by this rule, and the judge chooses attempts by it, so the two never disagree."""
    why = []
    peaks = [load[0] for load in (data.get('load_before'), data.get('load_after')) if load]
    peaks.append(data.get('load_max') or 0)  # as load_rounds reads it; the bench always writes it
    if max(peaks) > MAX_LOAD:
        why.append(f'load average {max(peaks):.1f} > {MAX_LOAD}')
    for key, words in (('errors', 'a part failed'), ('unexpected_statuses', 'unexpected statuses'),
                       ('console_errors', 'console error(s)'), ('blocked_requests', 'requests left loopback'),
                       ('unfinished', 'operation(s) never finished')):
        if data.get(key):
            why.append(f'{words}: {str(data[key])[:200]}')
    if 'open' in data.get('parts', []) and 'P0' in file_profiles(name):
        for control in controls:
            found = (data.get('controls') or {}).get(control)
            if found is None:
                why.append(f'control {control} missing')
            elif not found.get('ok'):
                why.append(f'control {control} failed')
    if revision and data.get('revision') != revision:  # judge[9]: a file of another tree is no attempt of this tag's
        why.append(f'measured on revision {str(data.get("revision"))[:12]}, not {str(revision)[:12]}')
    return why


def chosen_attempts(out: Path, controls=(), revisions=None) -> tuple[list, list]:
    """(kept, not used): for each tag, base round (round mod 100) and part group, the FIRST attempt that is valid on its
    own (attempt_reasons), else the newest, so a round with no valid attempt stays INVALID. A valid round is final: the
    driver runs a round again as round + 100 only after an INVALID attempt, and an attempt found after a valid one is
    set aside, never judged. Every file stays on disk, never overwritten."""
    attempts = {}
    for path in sorted(Path(out).glob('*.json')):
        m = ROUND_RE.match(path.name)
        if m:
            number = int(m.group('round'))
            attempts.setdefault((m.group('tag'), number % 100, m.group('parts')), []).append((number, path))
    kept, unused = [], []
    for key, found in attempts.items():
        found.sort()
        named = (revisions or {}).get(key[0])  # judge[9]: the tag's named tree, when the caller names one
        valid = [path for _, path in found
                 if not attempt_reasons(path.name, json.loads(path.read_text()), controls, named)]
        choice = valid[0] if valid else found[-1][1]
        kept.append(choice)
        unused += [path.name for _, path in found if path != choice]
    return sorted(kept, key=lambda p: p.name), sorted(unused)


def _and_merge(into: dict, more: dict):
    """A check or control several files of one round record (correct.barcode_every_open from every open@Px,
    left.no_store from the open and left-behind parts) holds only when every file says ok; each file's own result
    is kept."""
    for name, value in more.items():
        prior = into.get(name)
        into[name] = value if prior is None else {'ok': bool(prior.get('ok')) and bool(value.get('ok')),
                                                  'by_file': prior.get('by_file', [prior]) + [value]}


def load_rounds(out: Path, controls=(), revisions=None) -> dict:
    """{tag: {base round: merged}}: the chosen attempt of each round file of the folder (chosen_attempts), the files of
    one tag and base round merged: metrics pooled, checks and controls ANDed, every file's tree kept."""
    rounds = {}
    kept, superseded = chosen_attempts(Path(out), controls, revisions)
    for path in kept:
        m = ROUND_RE.match(path.name)
        data = json.loads(path.read_text())
        merged = rounds.setdefault(m.group('tag'), {}).setdefault(int(m.group('round')) % 100, {
            'metrics': {}, 'checks': {}, 'controls': {}, 'errors': [], 'unexpected_statuses': {}, 'console_errors': [],
            'blocked_requests': [], 'unfinished': [], 'loads': [], 'files': {}, 'revision': None, 'parts': [],
            'requests': None, 'requests_effort': None, 'trees': set(), 'static': {}, 'office': {}, 'front_door': None,
            'superseded': superseded})
        merged['parts'] += data.get('parts', [])
        covered = merged.setdefault('covered', {})  # D-R2-44: a valid round is final under any group name
        for pair in sorted(coverage(path.name, data)):
            if pair in covered:
                merged.setdefault('remeasured', []).append(f'{"@".join(pair)}: {covered[pair]} and {path.name}')
            else:
                covered[pair] = path.name
        for name, values in data.get('metrics', {}).items():
            merged['metrics'].setdefault(name, []).extend(values)
        _and_merge(merged['checks'], data.get('checks', {}))
        _and_merge(merged['controls'], data.get('controls', {}))
        merged['errors'] += data.get('errors', [])
        for key, n in data.get('unexpected_statuses', {}).items():
            merged['unexpected_statuses'][key] = merged['unexpected_statuses'].get(key, 0) + n
        merged['console_errors'] += data.get('console_errors', [])
        merged['blocked_requests'] += data.get('blocked_requests', [])
        merged['unfinished'] += data.get('unfinished', [])  # an operation bench.cjs gave up waiting for
        merged['loads'] += [data.get('load_before'), data.get('load_after')]
        merged.setdefault('load_max', []).append(data.get('load_max', 0) or 0)
        merged['files'].update(data.get('files', {}))
        merged['revision'] = data.get('revision') or merged['revision']
        merged['trees'].add((data.get('revision'), json.dumps(data.get('files') or {}, sort_keys=True)))
        twice = merged.setdefault('remeasured', [])  # judge[0]: requests, an office size and the front door come
        if data.get('requests') is not None:          # from one file of a round, never the last of two
            if merged['requests'] is not None:
                twice.append(f'requests: {path.name} and an earlier file')
            merged['requests'] = data['requests']
            merged['requests_effort'] = data.get('requests_effort')
        merged['static'].update(data.get('static', {}))
        for size, value in (data.get('office') or {}).items():
            if str(size) in merged['office']:
                twice.append(f'office {size}: {path.name} and an earlier file')
            merged['office'][str(size)] = value
        if data.get('front_door'):
            if merged['front_door']:
                twice.append(f'front_door: {path.name} and an earlier file')
            merged['front_door'] = data['front_door']
    return rounds


def pooled(rounds_of_tag: dict, metric: str) -> list:
    return [v for r in sorted(rounds_of_tag) for v in rounds_of_tag[r]['metrics'].get(metric, [])]


def stat(values, how='median'):
    values = [v for v in values if isinstance(v, (int, float)) and not isinstance(v, bool)]
    if not values:
        return None
    if how == 'median':
        return statistics.median(values)
    if how == 'max':
        return max(values)
    if how == 'min':
        return min(values)
    if how == 'mean':
        return statistics.fmean(values)
    if how == 'p95':
        ordered = sorted(values)
        return ordered[min(len(ordered) - 1, int(round(0.95 * (len(ordered) - 1))))]
    if how == 'sum':
        return sum(values)
    raise ValueError(how)


# --- the A/A spread, the floors and the derived values (C5, D-R2-44) --------------------------------------------------

def up_spread(a: float, b: float) -> float:
    """|a - b| / mean(a, b), rounded UP at 4 decimals (protocol[5]): 1 + 2 x the spread is then never below C5's exact
    minimum. The inner round keeps float noise from lifting a value that is already exact at 4 decimals."""
    mean = (a + b) / 2
    return 0.0 if mean == 0 else math.ceil(round(abs(a - b) / abs(mean) * 10000, 6)) / 10000


def spread(first: dict, second: dict, how='median') -> dict:
    """{metric: up_spread of the two rounds' values} over the metrics both rounds measured (0 when both are 0)."""
    out = {}
    for name in sorted(set(first['metrics']) & set(second['metrics'])):
        a, b = stat(first['metrics'][name], how), stat(second['metrics'][name], how)
        if a is None or b is None:
            continue
        out[name] = up_spread(a, b)
    return out


def floor_factor(spread_value: float) -> float:
    """C5: a "no worse than A" limit is at least A x (1 + 2 x the metric's A/A spread)."""
    return round(1 + 2 * float(spread_value), 4)


def needs_floor(gate: dict) -> bool:
    return (('rel_max' in gate and gate['rel_max'] >= 1) or 'rel_plus' in gate or gate.get('no_worse')) and \
        'abs_max' not in gate


DERIVED_ROW_KEYS = ('a_recorded', 'a_spread', 'spread')
DERIVED_GATE_KEYS = ('spread', 'floor_factor')
DERIVED_RULE = ('derive(): for every row that reads A, a_recorded = both A/A rounds pooled in the row\'s own statistic '
                '(2 decimals), a_spread = up_spread of the two rounds\' values in that statistic (|a - b| / mean, '
                'rounded up at 4 decimals), the same spread as the row\'s gain spread and on each no-worse-than-A gate '
                'with floor_factor = 1 + 2 x it (C5); rows: {row id: [round 1, round 2, pooled]}; sha256 of the rows')


def reads_a(row: dict) -> bool:
    """A metric row whose A is read - its A-column check, a limit relative to A, a floor or a gain - unless the row says
    needs_a false (a metric release 1 does not have)."""
    return row.get('kind', 'metric') == 'metric' and bool(row.get('metric')) and row.get('needs_a', True) is not False


def base_table(table: dict) -> dict:
    """The table with every A-derived value taken out: derive's input, and the committed form until an A/A is
    derived."""
    out = json.loads(json.dumps(table))
    out['derived'] = None
    for row in out['rows']:
        for key in DERIVED_ROW_KEYS:
            row.pop(key, None)
        for gate in row.get('gate', []):
            for key in DERIVED_GATE_KEYS:
                gate.pop(key, None)
    return out


def derived_digest(values: dict) -> str:
    return hashlib.sha256(json.dumps(values, sort_keys=True).encode()).hexdigest()


def derive_row(row: dict, first_value, second_value, both_value) -> dict:
    """One row's A-derived values (derive's rule), written into ``row``."""
    spread_value = up_spread(first_value, second_value)
    row['a_recorded'] = round(both_value, 2)
    row['a_spread'] = spread_value
    row['spread'] = spread_value
    for gate in row.get('gate', []):
        if needs_floor(gate):
            gate['spread'] = spread_value
            gate['floor_factor'] = floor_factor(spread_value)
    return row


def derive(table: dict, first: dict, second: dict, source: str) -> dict:
    """acceptance.json's A-derived values from one valid A/A pair (C5, D-R2-44), in one pass and never None: for every
    row that reads A, its recorded A, its A/A spread in its own statistic, its gain spread and its floors (derive_row).
    The table is first stripped of earlier values (base_table), so a derivation is reproducible: the same table and
    rounds give the same bytes. ValueError when the pair lacks a value a row reads (a part group never measured)."""
    out = base_table(table)
    values, missing, short = {}, [], []
    for row in out['rows']:
        if not reads_a(row):
            continue
        how = row.get('stat', 'median')
        one, two = first['metrics'].get(row['metric'], []), second['metrics'].get(row['metric'], [])
        found = [stat(one, how), stat(two, how), stat(one + two, how)]
        if None in found:
            missing.append(row['id'])
            continue
        # section 8's validity rule: too few samples is INVALID, A's too; min_samples counts a session's three rounds
        need = math.ceil(row.get('min_samples', 1) / 3)
        counts = [sum(1 for v in r if isinstance(v, (int, float)) and not isinstance(v, bool)) for r in (one, two)]
        if min(counts) < need:
            short.append(f'{row["id"]} {counts} (need {need} a round)')
            continue
        values[row['id']] = found
    if missing:
        raise ValueError(f'the A/A pair has no value for {len(missing)} row(s) that read A: {missing[:10]}')
    if short:
        raise ValueError(f'too few samples in an A/A round for {len(short)} row(s) that read A: {short[:10]}')
    for row in out['rows']:
        if row['id'] in values:
            derive_row(row, *values[row['id']])
    out['derived'] = {'source': source, 'rule': DERIVED_RULE, 'rows': values, 'sha256': derived_digest(values)}
    return out


# --- one row ----------------------------------------------------------------------------------------------------------

def a_tolerance(row: dict) -> float:
    """How far release 1's own value may be from the A column: 20%, or twice the metric's own recorded A/A spread where
    that is larger - C5's rule (no limit tighter than release 1's own spread) applied to the check that A is A, so a
    one-sample metric such as the longest GC pause does not make every round INVALID. It is never less than one step of
    the row's instrument (a_step: Event Timing reports durations in 8 ms steps), so one key 8 ms slower than a recorded
    32 ms is still A (judge[9])."""
    tolerance = max(A_TOLERANCE, 2 * (row.get('a_spread') or 0))
    step, reference = row.get('a_step'), row.get('a_recorded')
    if step and isinstance(reference, (int, float)) and not isinstance(reference, bool) and reference > 0:
        tolerance = max(tolerance, step / reference)
    return tolerance


def a_reference(row: dict):
    """(value, whose) the A-column check compares with: lane M's recorded A (this bench, this host, the A/A protocol)
    where acceptance.json holds one, else section 8's figure."""
    if row.get('a_recorded') is not None:
        return row['a_recorded'], "lane M's recorded A"
    return row.get('a_section8'), "section 8's A"


def a_column_close(a_now, a_ref, tolerance=A_TOLERANCE) -> bool:
    """Release 1's own value is within the tolerance of the A column (a number, or a [low, high] range)."""
    if a_ref is None or a_now is None:
        return True
    low, high = (a_ref, a_ref) if not isinstance(a_ref, list) else a_ref
    if low <= a_now <= high:
        return True
    near = low if a_now < low else high
    return near == 0 and a_now == 0 or (near != 0 and abs(a_now - near) / abs(near) <= tolerance)


def judge_requests(row: dict, a_rounds: dict, b_rounds: dict, out: dict) -> dict:
    """The coder row (R2-3, bench[3], D-R2-44): every round's requests (min_rows of them) equal release 1's byte
    for byte - the parameters' sha256 with output_config.effort taken out, the case, role and attempts - and the
    effort each tree sent is the row's own: release 1's 'max' on A, R2-33's 'high' on B, matching the tree's
    settings. Two empty lists are equal and prove nothing, so a round with too few rows, or rows without the sent
    effort, is INVALID."""
    runs = {'a': [r for r in a_rounds.values() if r.get('requests') is not None],
            'b': [r for r in b_rounds.values() if r.get('requests') is not None]}
    if not runs['a'] or not runs['b']:
        return {**out, 'verdict': 'INVALID', 'why': ['the requests part is missing']}
    every = runs['a'] + runs['b']
    need = row.get('min_rows', 1)  # section 8: 8 request hashes
    if any(len(r['requests']) < need for r in every):
        return {**out, 'verdict': 'INVALID',
                'why': [f'too few coder requests recorded: {min(len(r["requests"]) for r in every)} in a round, '
                        f'need {need}']}
    if any(not isinstance(x, dict) or 'effort' not in x for r in every for x in r['requests']):
        return {**out, 'verdict': 'INVALID',
                'why': ['a requests part recorded no sent effort (a bench before D-R2-44)']}
    strip = lambda rows: [{k: v for k, v in x.items() if k != 'effort'} for x in rows]  # noqa: E731
    if any(strip(r['requests']) != strip(runs['a'][0]['requests']) for r in every):
        return {**out, 'verdict': 'FAIL', 'why': ['what the coder is sent differs between the trees or rounds, effort '
                                                  'aside']}
    for side, rounds_of in runs.items():
        want = (row.get('effort') or {}).get(side)
        sent = sorted({x['effort'] for r in rounds_of for x in r['requests']})
        named = sorted({str(r.get('requests_effort')) for r in rounds_of})
        if want is None or sent != [want] or named != [want]:
            out['verdict'] = 'FAIL'
            out['why'].append(f'{side.upper()} sent effort {sent} with settings {named}; the row names {want}')
    return out


def judge_row(row: dict, a_rounds: dict, b_rounds: dict, *, control: bool = False) -> dict:
    """{verdict, a, b, limit, why} for one acceptance row."""
    how = row.get('stat', 'median')
    kind = row.get('kind', 'metric')
    out = {'id': row['id'], 'metric': row.get('metric'), 'verdict': 'PASS', 'why': []}
    if kind == 'report':
        out['a'], out['b'] = stat(pooled(a_rounds, row['metric']), how), stat(pooled(b_rounds, row['metric']), how)
        out['verdict'] = 'REPORT'
        return out
    if kind == 'external':
        return {**out, 'verdict': 'EXTERNAL', 'why': [row.get('where', 'judged outside the bench')]}
    if kind == 'office':
        return judge_office(row, b_rounds, table_office=row.get('model'))
    if kind == 'max_ratio':
        values = [stat(pooled(b_rounds, m), how) for m in row['metrics']]
        if any(v is None or v <= 0 for v in values):
            return {**out, 'verdict': 'INVALID', 'why': ['a size is missing']}
        out['b'] = round(max(values) / min(values), 3)
        if out['b'] > row['max']:
            out['verdict'], out['why'] = 'FAIL', [f'largest / smallest {out["b"]} > {row["max"]}']
        return out
    if kind == 'equal':
        values = [stat(pooled(b_rounds, m), 'max') for m in row['metrics']]
        lows = [stat(pooled(b_rounds, m), 'min') for m in row['metrics']]
        if any(v is None for v in values):
            return {**out, 'verdict': 'INVALID', 'why': ['a side is missing']}
        out['b'] = values
        if len(set(values) | set(lows)) != 1:
            out['verdict'], out['why'] = 'FAIL', [f'not equal: {values} (lowest {lows})']
        return out
    if kind == 'check':
        results = [r['checks'].get(row['check']) for r in b_rounds.values()]
        if not results or any(r is None for r in results):
            return {**out, 'verdict': 'INVALID', 'why': [f'check {row["check"]} missing in a round']}
        if row.get('control_a'):  # R2-32 M5 and M9: checked on A as the control (the walk on A first)
            on_a = [r['checks'].get(row['check']) for r in a_rounds.values()]
            if not on_a or any(c is None or not c.get('ok') for c in on_a):
                return {**out, 'verdict': 'INVALID', 'detail_a': on_a,
                        'why': [f'A, the control, did not pass {row["check"]} in every round']}
        if not all(r['ok'] for r in results):
            return {**out, 'verdict': 'FAIL', 'why': [f'check {row["check"]} failed'], 'detail': results}
        return out
    if kind == 'same_as_a':
        return judge_requests(row, a_rounds, b_rounds, out)
    a_values, b_values = pooled(a_rounds, row['metric']), pooled(b_rounds, row['metric'])
    need = row.get('min_samples', 1)
    a, b = stat(a_values, how), stat(b_values, how)
    out.update({'a': a, 'b': b, 'n_a': len(a_values), 'n_b': len(b_values)})
    if kind == 'ratio':
        b2 = stat(pooled(b_rounds, row['over']), how)
        if b is None or not b2:
            return {**out, 'verdict': 'INVALID', 'why': ['a ratio has a missing side']}
        out['b'] = round(b / b2, 3)
        if out['b'] > row['max']:
            out['verdict'], out['why'] = 'FAIL', [f'ratio {out["b"]} > {row["max"]}']
        return out
    if kind == 'round_trips':
        p2, p0 = stat(pooled(b_rounds, row['metric']), how), stat(pooled(b_rounds, row['over']), how)
        if p2 is None or p0 is None:
            return {**out, 'verdict': 'INVALID', 'why': ['a profile is missing']}
        out['b'] = round((p2 - p0) / row['per_ms'], 3)
        if out['b'] > row['max']:
            out['verdict'], out['why'] = 'FAIL', [f'{out["b"]} round trips > {row["max"]}']
        return out
    if len(b_values) < need or (row.get('needs_a', True) and len(a_values) < need):  # A is read unless it says not
        return {**out, 'verdict': 'INVALID',
                'why': [f'too few samples (A {len(a_values)}, B {len(b_values)}, need {need})']}
    reference, whose = a_reference(row)
    if not control and reference is not None and row.get('needs_a', True) and a is not None and \
            not a_column_close(a, reference, a_tolerance(row)):
        return {**out, 'verdict': 'INVALID',
                'why': [f'A {a} is more than {a_tolerance(row):.0%} from {whose} {reference}']}
    if b is None:
        return {**out, 'verdict': 'INVALID', 'why': ['no B value']}
    limits = []
    for gate in row.get('gate', []):
        if 'abs_max' in gate:
            limits.append(('max', gate['abs_max'], 'absolute'))
        if 'abs_min' in gate:
            limits.append(('min', gate['abs_min'], 'absolute'))
        if 'eq' in gate:
            limits.append(('eq', gate['eq'], 'exact'))
        if 'rel_max' in gate or 'rel_plus' in gate or 'rel_min' in gate:
            if a is None:
                return {**out, 'verdict': 'INVALID', 'why': ['no A value for a relative limit']}
            if 'rel_min' in gate:
                limits.append(('min', gate['rel_min'] * a, f'{gate["rel_min"]} A'))
                continue
            factor, plus = gate.get('rel_max', 1.0), gate.get('rel_plus', 0.0)
            limit = factor * a + plus + gate.get('page_load_ms', 0) * 0
            if gate.get('plus_metric'):
                extra = stat(pooled(b_rounds, gate['plus_metric']), how)
                if extra is None:
                    return {**out, 'verdict': 'INVALID', 'why': [f'{gate["plus_metric"]} was not measured']}
                limit += extra
            if needs_floor(gate):
                ff = gate.get('floor_factor')
                if ff is None:
                    return {**out, 'verdict': 'INVALID', 'why': ['no recorded A/A spread for a no-worse-than-A limit']}
                # never tighter than one step of the row's instrument (a_step), as the A-column check (D-R2-47)
                floor = max(ff * a, a + (row.get('a_step') or 0)) + \
                    (stat(pooled(b_rounds, gate['plus_metric']), how) if gate.get('plus_metric') else 0)
                limit = max(limit, floor)
            limits.append(('max', limit, f'{factor} A + {plus}'))
    for direction, limit, label in limits:
        if (direction == 'max' and b > limit) or (direction == 'min' and b < limit) or \
                (direction == 'eq' and b != limit):
            out['verdict'] = 'FAIL'
            out['why'].append(f'{b} vs {label} limit {round(limit, 2)}')
    out['limits'] = [[d, round(v, 2), lab] for d, v, lab in limits]
    # section 8: a gain counts only when it exceeds twice the A/A spread of its metric - wherever a limit, absolute or
    # relative, lies below A (above it for a rate), not only on a row flagged gain (judge[10]: scan20's 400 ms). An
    # absolute limit is held against the A measured in the session and the A the table records (its recorded A, else
    # section 8's), so a session whose A came in low inside its tolerance still asks the gain (the round-2 replay of
    # refute-m1 judge[10]: A 380, B 398 against 400 passed); a relative limit is built from the session's A alone
    ref = row.get('a_recorded', row.get('a_section8'))
    def under(v, lab):
        return (a is not None and v < a) or (lab == 'absolute' and ref is not None and v < ref)

    def over(v, lab):
        return (a is not None and v > a) or (lab == 'absolute' and ref is not None and v > ref)
    below = [v for d, v, lab in limits if d == 'max' and under(v, lab)]
    above = [v for d, v, lab in limits if d == 'min' and over(v, lab)]
    if out['verdict'] == 'PASS' and reads_a(row) and (row.get('gain') or below or above):  # needs_a false: B alone
        s = row.get('spread')
        if s is None:
            return {**out, 'verdict': 'INVALID', 'why': ['no recorded A/A spread for a gain']}
        up = row.get('gain_direction') == 'up' or bool(above)
        gain = None if not a else ((b / a - 1) if up else (1 - b / a))
        if gain is None or gain <= 2 * s:
            out['verdict'] = 'FAIL'
            shown = None if gain is None else round(gain, 3)
            out['why'].append(f'the gain {shown} does not exceed twice the A/A spread {s}')
    return out


# --- the verdict ------------------------------------------------------------------------------------------------------

def invalid_reasons(rounds: dict, tags, *, control: bool, controls: list, a_revision: str | None = None) -> list:
    """Why rounds of ``tags`` (A then B) are INVALID: each round's own rules, every file of a tag measured on one tree
    (judge[3]: a file of another tree never enters a verdict unseen), the two trees' app.js hashes over every file, and,
    where the table names release 1's revision, every A file measured on it."""
    why = []
    hashes = {}
    for tag in tags:
        if tag not in rounds or not rounds[tag]:
            why.append(f'no rounds of {tag}')
            continue
        trees = set()
        for number, r in sorted(rounds[tag].items()):
            where = f'{tag} round {number}'
            if r['unexpected_statuses']:
                why.append(f'{where}: unexpected statuses {r["unexpected_statuses"]}')
            if r['console_errors']:
                first = r['console_errors'][0][:120]
                why.append(f'{where}: {len(r["console_errors"])} console error(s), first: {first}')
            if r['blocked_requests']:
                why.append(f'{where}: requests left loopback: {r["blocked_requests"][:3]}')
            peaks = [load[0] for load in r['loads'] if load] + r.get('load_max', [])
            if peaks and max(peaks) > MAX_LOAD:
                why.append(f'{where}: load average {max(peaks):.1f} > {MAX_LOAD}')
            if r['errors']:
                why.append(f'{where}: a part failed: {str(r["errors"][0])[:200]}')
            if r.get('remeasured'):  # one part at one profile measured twice in one round (D-R2-44)
                why.append(f'{where}: measured twice: {r["remeasured"][:3]}')
            if r.get('unfinished'):  # its samples were never recorded, so no row can see it (judge[1])
                why.append(f'{where}: {len(r["unfinished"])} operation(s) never finished: {r["unfinished"][:3]}')
            if 'open' in r['parts']:
                for name in controls:
                    c = r['controls'].get(name)
                    if c is None:
                        why.append(f'{where}: control {name} missing')
                    elif not c.get('ok'):
                        why.append(f'{where}: control {name} failed: {c}')
            trees |= r.get('trees') or {(r.get('revision'), json.dumps(r.get('files') or {}, sort_keys=True))}
        if len(trees) > 1:  # one tag is one tree
            why.append(f'{tag}: its round files were measured on {len(trees)} trees (revisions '
                       f'{sorted({str(rev)[:12] for rev, _ in trees})})')
        hashes[tag] = {json.loads(files).get('studio/static/studio/app.js') for _, files in trees}
        if a_revision and tag == tags[0]:
            others = sorted({str(rev) for rev, _ in trees if rev != a_revision})
            if others:
                why.append(f'{tag} is not release 1: revision(s) {[o[:12] for o in others[:3]]}, the table names '
                           f'{a_revision[:12]}')
    if len(tags) == 2 and tags[0] != tags[1] and all(rounds.get(t) for t in tags) and \
            set(rounds[tags[0]]) != set(rounds[tags[1]]):  # A B A B A B: no tag gets rounds of its own
        why.append(f'{tags[0]} and {tags[1]} carry different rounds: {sorted(rounds[tags[0]])} and '
                   f'{sorted(rounds[tags[1]])}')
    if not control and len(tags) == 2 and all(t in hashes for t in tags) and hashes[tags[0]] & hashes[tags[1]]:
        why.append('the two trees\' app.js hashes are equal (judge A against A only with --control)')
    return why


def table_a_revision(table: dict):
    """The 40-hex release-1 revision the table's a_tree names, else None."""
    named = re.match(r'[0-9a-f]{40}', str(table.get('a_tree') or ''))
    return named.group(0) if named else None


def verdict(rounds: dict, table: dict, a: str, b: str, *, control: bool = False, b_revision=None) -> dict:
    why = invalid_reasons(rounds, [a, b], control=control, controls=table.get('controls', []),
                          a_revision=table_a_revision(table))
    if b_revision:  # judge[9]: B judged as the commit named, as A is as release 1
        others = sorted({str(rev) for r in rounds.get(b, {}).values() for rev, _ in r.get('trees', ())
                         if rev != b_revision})
        if others:
            why.append(f'{b} is not {b_revision[:12]}: revision(s) {[o[:12] for o in others[:3]]}')
    rows = [judge_row({**row, 'model': table.get('office_model')} if row.get('kind') == 'office' else row,
                      rounds.get(a, {}), rounds.get(b, {}), control=control) for row in table['rows']]
    if why or any(r['verdict'] == 'INVALID' for r in rows):
        answer = 'INVALID'
    elif any(r['verdict'] == 'FAIL' for r in rows):
        answer = 'FAIL'
    else:
        answer = 'PASS'
    superseded = sorted({name for tag in (a, b) for r in rounds.get(tag, {}).values()
                         for name in r.get('superseded', [])})
    trees = {tag: sorted({str(rev) for r in rounds.get(tag, {}).values() for rev, _ in r.get('trees', ())})
             for tag in (a, b)}
    return {'verdict': answer, 'invalid': why, 'superseded': superseded, 'trees': trees, 'rows': rows}


def aa_pair(out: Path, specs: list, controls: list, a_revision: str | None = None) -> tuple[list, list]:
    """([round 1, round 2], why not): the A/A pair TAG:ROUND twice, each round merged as load_rounds does, and
    every reason it cannot give floors or a recorded A (protocol[0]: C5's floors come from valid rounds only; an
    INVALID round is run again, never used): a round missing or INVALID by the round rules, two tags, rounds that
    ran different parts, or files not of the release-1 revision the table names (judge[1], judge[9])."""
    picked = [(x.split(':')[0], int(x.split(':')[1])) for x in specs]
    if len(picked) != 2 or picked[0][0] != picked[1][0] or picked[0][1] == picked[1][1]:
        return [], ['an A/A pair is two different rounds of one tag (--a A:1 --a A:2)']
    tag = picked[0][0]
    rounds = load_rounds(Path(out), controls, {tag: a_revision} if a_revision else None)  # judge[9]
    pair = [rounds.get(tag, {}).get(number) for _, number in picked]
    why = [f'{tag}:{number}: no such round in {out}' for (_, number), r in zip(picked, pair) if r is None]
    if why:
        return [], why
    why = invalid_reasons({tag: dict(zip([n for _, n in picked], pair))}, [tag], control=True, controls=controls,
                          a_revision=a_revision)  # the A/A is release 1's, as every A the verdict reads
    if sorted(set(pair[0]['parts'])) != sorted(set(pair[1]['parts'])):
        why.append(f'the two rounds ran different parts: {sorted(set(pair[0]["parts"]))} and '
                   f'{sorted(set(pair[1]["parts"]))}')
    return pair, why


# --- the office model: arithmetic against the vhost's zones (section 8) -----------------------------------------------

def rate_per_ms(rate: str) -> float:
    m = re.fullmatch(r'(\d+)r/([sm])', rate)
    if not m:
        raise ValueError(rate)
    return int(m.group(1)) / (1000.0 if m.group(2) == 's' else 60000.0)


def zone_of(zone_maps: dict, method: str, path: str) -> list:
    """The limit_req zones a request counts in, by the vhost's own key maps (the exempt flag 0: an office address), as
    nginx picks a map's value (judge[6]): an exact string first (case aside), then the expressions in order, then the
    default; a request whose key is empty counts in no zone (R2-27's '"0:POST /api/encounters/search" "";')."""
    keys = []
    path = path.split('?', 1)[0].replace('<id>', '00000000-0000-4000-8000-000000000000')
    line = f'0:{method} {path}'
    for key, body in zone_maps.items():
        body = re.sub(r'#[^\n]*', '', body)
        entries = re.findall(r'"(~?)\^?([^"]*)"\s+("[^"]*"|\$\w+)\s*;', body)
        exact = [value for regex, pattern, value in entries if not regex and pattern.lower() == line.lower()]
        matched = [value for regex, pattern, value in entries if regex and re.match('^' + pattern, line)]
        default = re.search(r'\bdefault\s+("[^"]*"|\$\w+)\s*;', body)
        if (exact or matched or [default.group(1) if default else '""'])[0] != '""':
            keys.append(key)
    return keys


def limit_req(times: list, rate_ms: float, burst: int) -> int:
    """nginx's limit_req with nodelay (ngx_http_limit_req_lookup) over request times in ms: the number refused (429). A
    key's first request makes its node with no excess; each later one has excess = max(0, excess - rate x elapsed + 1)
    and is refused when that passes the burst, a refusal changing neither the excess nor the node's time."""
    refused, excess, last = 0, 0.0, None
    for t in sorted(times):
        if last is None:
            excess, last = 0.0, t
            continue
        value = max(0.0, excess - rate_ms * (t - last) + 1)  # nginx adds the request before it clamps at 0
        if value > burst + 1e-9:
            refused += 1
            continue
        excess, last = value, t
    return refused


def office_requests(model: dict, measured: dict) -> list:
    """The office's requests as (ms, method, path): 20 members signing in within 2 s, then at natural pace (an open,
    reading, the list, again) for a minute, 5 of them typing 30 characters at 350 ms; hashed static files cached,
    except the standby's two for 5 members (section 8)."""
    out = []
    members, typists = model['members'], model['typists']
    for i in range(members):
        start = i * (model['signin_window_ms'] / members)
        for k, (method, path) in enumerate(measured['signin']):
            if path.startswith('/static/') and not (path.endswith('.mjs') and i < model['cold_caches']):
                continue
            out.append((start + 20 * k, method, path))
        t = start + 2000 + (i * 997) % model['open_every_ms']
        while t < model['minutes'] * 60000:
            for k, (method, path) in enumerate(measured['open']):
                out.append((t + 10 * k, method, path))
            for k, (method, path) in enumerate(measured['list']):
                out.append((t + model['read_ms'] + 10 * k, method, path))
            t += model['open_every_ms']
        if i < typists:
            for at, method, path in measured['typing']:
                out.append((model['typing_at_ms'] + i * 600 + at, method, path))
    return sorted(out)


def office_429s(zones: dict, requests: list) -> dict:
    """{zone: refused}: every limit_req zone of the vhost, applied to the office's single address."""
    out = {}
    for zone, spec in zones['zones'].items():
        if 'burst' not in spec or 'rate' not in spec:
            continue
        key = spec['key']
        if key == 'cpt_all_key':
            times = [t for t, method, path in requests]
        else:
            times = [t for t, method, path in requests if key in zone_of(zones['maps'], method, path)]
        out[zone] = limit_req(times, rate_per_ms(spec['rate']), spec['burst'])
    return out


def judge_office(row: dict, b_rounds: dict, table_office: dict | None) -> dict:
    """0 answers of 429 at the row's practice size, every round: the office's requests, built from what the round
    measured (a later open and a list visit from the open part, the sign-in and the typing at this size from the office
    part), run through every limit_req zone of the tree's own vhost (the office part reads it)."""
    out = {'id': row['id'], 'verdict': 'PASS', 'why': []}
    size = str(row['size'])
    if not b_rounds or not table_office:
        return {**out, 'verdict': 'INVALID', 'why': ['no rounds, or no office model in the table']}
    worst = {}
    for number, r in sorted(b_rounds.items()):
        office, door = r.get('office') or {}, r.get('front_door') or {}
        at = office.get(size)
        zones = office.get('vhost_zones')
        if not at or not zones or not door.get('later') or not door.get('back'):
            return {**out, 'verdict': 'INVALID', 'why': [f'round {number}: the office or open part is missing']}
        measured = {'signin': [tuple(x.split(' ')[:2]) for x in at['signin']],
                    'open': [tuple(x[:2]) for x in door['later']], 'list': [tuple(x[:2]) for x in door['back']],
                    'typing': [(e['at'], e['method'], e['url']) for e in at['typing']]}
        refused = office_429s(zones, office_requests(table_office, measured))
        worst[number] = refused
        if any(refused.values()):
            out['verdict'] = 'FAIL'
            out['why'].append(f'round {number}: 429s {refused}')
    out['b'] = worst
    return out


# --- command line -----------------------------------------------------------------------------------------------------

def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='command', required=True)
    v = sub.add_parser('verdict')
    v.add_argument('--out', required=True)
    v.add_argument('--a', required=True)
    v.add_argument('--b', required=True)
    v.add_argument('--acceptance', default=str(HERE / 'acceptance.json'))
    v.add_argument('--control', action='store_true')
    v.add_argument('--b-revision', help="B's exact commit: a B round file of another is INVALID on its own")
    s = sub.add_parser('spread')
    s.add_argument('--out', required=True)
    s.add_argument('--a', action='append', required=True, help='TAG:ROUND, twice')
    s.add_argument('--acceptance', default=str(HERE / 'acceptance.json'))
    f = sub.add_parser('floors', help='derive acceptance.json from a valid A/A pair (printed, or --check)')
    f.add_argument('--out', required=True, help='the A/A folder')
    f.add_argument('--a', action='append', required=True, help='TAG:ROUND, twice: the A/A pair')
    f.add_argument('--source', required=True, help='what the pair is: its folder, bench commit and date')
    f.add_argument('--acceptance', default=str(HERE / 'acceptance.json'))
    f.add_argument('--check', action='store_true', help='compare with --acceptance byte for byte instead of printing')
    args = parser.parse_args(argv)
    table = json.loads(Path(args.acceptance).read_text())
    controls = table.get('controls', [])
    if args.command == 'verdict':
        revisions = {args.a: table_a_revision(table)} if table_a_revision(table) else {}  # judge[9]
        if args.b_revision:
            revisions[args.b] = args.b_revision
        answer = verdict(load_rounds(Path(args.out), controls, revisions), table, args.a, args.b,
                         control=args.control, b_revision=args.b_revision)
        print(json.dumps(answer, indent=1, default=str))
        return {'PASS': 0, 'FAIL': 1, 'INVALID': 3}[answer['verdict']]
    pair, why = aa_pair(Path(args.out), args.a, controls, table_a_revision(table))
    if why:  # no spread, no floor and no recorded A from an INVALID or partial pair: run it again
        print('refused: ' + '; '.join(why), file=sys.stderr)
        return 3
    if args.command == 'spread':
        print(json.dumps(spread(*pair), indent=1, sort_keys=True))
        return 0
    try:
        text = json.dumps(derive(table, pair[0], pair[1], args.source), indent=1) + '\n'
    except ValueError as exc:
        print(f'refused: {exc}', file=sys.stderr)
        return 3
    if args.check:
        same = text == Path(args.acceptance).read_text()
        print(f'{args.acceptance} {"is" if same else "is NOT"} exactly this A/A pair\'s derivation', file=sys.stderr)
        return 0 if same else 1
    sys.stdout.write(text)
    return 0


if __name__ == '__main__':
    sys.exit(main())
