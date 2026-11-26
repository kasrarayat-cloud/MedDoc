"""The bench's judge (RELEASE-2-SPEC R2-2 and section 8): PASS, FAIL or INVALID for B against A, from the rounds in an
output folder and the table in acceptance.json. No Django, no database, no browser: ops/test_bench.py drives it.

    python3 judge.py verdict --out <folder> --a A --b B [--acceptance acceptance.json] [--control]
    python3 judge.py spread  --out <folder> --a A:1 --a A:2      # the A/A spread of every metric, from two A rounds
    python3 judge.py floors  --spread <spread.json> [--acceptance acceptance.json]   # the C5 floors, printed

INVALID means "run again", never a pass or a fail. It is answered when (section 8):
- the two trees' app.js hashes are equal (unless --control: A against A on purpose);
- any answer had an unexpected status, or any page logged a console error, or a request left loopback;
- the load average was above 8 before or after a round;
- release 1's own median differs by more than 20% from section 8's A column (rows that carry one);
- a row has too few samples; a round's control is missing or failed; a part of a round failed with an error.
Otherwise each gated row is judged on the pooled median of its samples (or its stated statistic):
- an absolute limit is the number;
- a limit relative to A uses A measured in the same session, and a "no worse than A" limit (factor >= 1) is never
  tighter than A x (1 + 2 x that metric's recorded A/A spread): the floor_factor acceptance.json carries, computed by
  lane M before any B was measured, never at run time (C5);
- a gain (a limit below A) counts only when it exceeds twice the metric's A/A spread.
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROUND_RE = re.compile(r'^(?P<tag>[A-Za-z][A-Za-z0-9_]{0,15})-r(?P<round>\d+)-'
                      r'(?P<parts>[a-z+-]+(?:@[A-Z0-9+]+)?)\.json$')
MAX_LOAD = 8.0
A_TOLERANCE = 0.20


# --- reading rounds ---------------------------------------------------------------------------------------------------

def newest_attempts(out: Path) -> tuple[list, list]:
    """(kept, superseded): the round files of the folder, one per tag, base round and parts - the newest attempt. The
    protocol driver runs a round again as round + 100 only when the attempt before it was INVALID (its load passed 8 or
    it failed), so a later attempt supersedes an earlier one; the earlier files stay on disk, never overwritten."""
    best, superseded = {}, []
    for path in sorted(Path(out).glob('*.json')):
        m = ROUND_RE.match(path.name)
        if not m:
            continue
        number = int(m.group('round'))
        key = (m.group('tag'), number % 100, m.group('parts'))
        if key in best and best[key][0] > number:
            superseded.append(path.name)
            continue
        if key in best:
            superseded.append(best[key][1].name)
        best[key] = (number, path)
    return [path for _, path in sorted(best.values(), key=lambda v: v[1].name)], sorted(superseded)


def load_rounds(out: Path) -> dict:
    """{tag: {base round: merged}}: the newest attempt of each round file of the folder (newest_attempts), the files of
    one tag and base round merged."""
    rounds = {}
    kept, superseded = newest_attempts(Path(out))
    for path in kept:
        m = ROUND_RE.match(path.name)
        data = json.loads(path.read_text())
        merged = rounds.setdefault(m.group('tag'), {}).setdefault(int(m.group('round')) % 100, {
            'metrics': {}, 'checks': {}, 'controls': {}, 'errors': [], 'unexpected_statuses': {}, 'console_errors': [],
            'blocked_requests': [], 'loads': [], 'files': {}, 'revision': None, 'parts': [], 'requests': None,
            'static': {}, 'office': {}, 'front_door': None, 'superseded': superseded})
        merged['parts'] += data.get('parts', [])
        for name, values in data.get('metrics', {}).items():
            merged['metrics'].setdefault(name, []).extend(values)
        merged['checks'].update(data.get('checks', {}))
        merged['controls'].update(data.get('controls', {}))
        merged['errors'] += data.get('errors', [])
        for key, n in data.get('unexpected_statuses', {}).items():
            merged['unexpected_statuses'][key] = merged['unexpected_statuses'].get(key, 0) + n
        merged['console_errors'] += data.get('console_errors', [])
        merged['blocked_requests'] += data.get('blocked_requests', [])
        merged['loads'] += [data.get('load_before'), data.get('load_after')]
        merged.setdefault('load_max', []).append(data.get('load_max', 0) or 0)
        merged['files'].update(data.get('files', {}))
        merged['revision'] = data.get('revision') or merged['revision']
        if data.get('requests') is not None:
            merged['requests'] = data['requests']
        merged['static'].update(data.get('static', {}))
        for size, value in (data.get('office') or {}).items():
            merged['office'][str(size)] = value
        if data.get('front_door'):
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


# --- the A/A spread and the floors (C5) -------------------------------------------------------------------------------

def spread(first: dict, second: dict, how='median') -> dict:
    """{metric: |m1 - m2| / mean(m1, m2)} over the metrics both runs measured (0 when both medians are 0)."""
    out = {}
    for name in sorted(set(first['metrics']) & set(second['metrics'])):
        a, b = stat(first['metrics'][name], how), stat(second['metrics'][name], how)
        if a is None or b is None:
            continue
        mean = (a + b) / 2
        out[name] = 0.0 if mean == 0 else round(abs(a - b) / abs(mean), 4)
    return out


def floor_factor(spread_value: float) -> float:
    """C5: a "no worse than A" limit is at least A x (1 + 2 x the metric's A/A spread)."""
    return round(1 + 2 * float(spread_value), 4)


def apply_floors(table: dict, spreads: dict) -> dict:
    """Each no-worse-than-A gate (a factor >= 1, a plus term, or `no_worse`) gets its metric's floor_factor; a row whose
    metric has no recorded spread is left without one and the judge answers INVALID for it."""
    for row in table['rows']:
        for gate in row.get('gate', []):
            if needs_floor(gate):
                s = spreads.get(row['metric'])
                gate['spread'] = s
                gate['floor_factor'] = floor_factor(s) if s is not None else None
        if row.get('gain'):
            row['spread'] = spreads.get(row['metric'])
        if row.get('metric') and (row.get('a_section8') is not None or row.get('a_recorded') is not None):
            row['a_spread'] = spreads.get(row['metric'])  # widens the A-column check for a noisy metric (a_tolerance)
    return table


def needs_floor(gate: dict) -> bool:
    return (('rel_max' in gate and gate['rel_max'] >= 1) or 'rel_plus' in gate or gate.get('no_worse')) and \
        'abs_max' not in gate


# --- one row ----------------------------------------------------------------------------------------------------------

def a_tolerance(row: dict) -> float:
    """How far release 1's own value may be from the A column: 20%, or twice the metric's own recorded A/A spread where
    that is larger - C5's rule (no limit tighter than release 1's own spread) applied to the check that A is A, so a
    one-sample metric such as the longest GC pause does not make every round INVALID."""
    return max(A_TOLERANCE, 2 * (row.get('a_spread') or 0))


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
        if not all(r['ok'] for r in results):
            return {**out, 'verdict': 'FAIL', 'why': [f'check {row["check"]} failed'], 'detail': results}
        return out
    if kind == 'same_as_a':
        a_list = [r['requests'] for r in a_rounds.values() if r.get('requests') is not None]
        b_list = [r['requests'] for r in b_rounds.values() if r.get('requests') is not None]
        if not a_list or not b_list:
            return {**out, 'verdict': 'INVALID', 'why': ['the requests part is missing']}
        if any(x != a_list[0] for x in a_list + b_list):
            return {**out, 'verdict': 'FAIL', 'why': ['what the coder is sent differs between the trees or rounds']}
        return out
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
    if len(b_values) < need or (row.get('needs_a') and len(a_values) < need):
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
                floor = ff * a + (stat(pooled(b_rounds, gate['plus_metric']), how) if gate.get('plus_metric') else 0)
                limit = max(limit, floor)
            limits.append(('max', limit, f'{factor} A + {plus}'))
    for direction, limit, label in limits:
        if (direction == 'max' and b > limit) or (direction == 'min' and b < limit) or \
                (direction == 'eq' and b != limit):
            out['verdict'] = 'FAIL'
            out['why'].append(f'{b} vs {label} limit {round(limit, 2)}')
    out['limits'] = [[d, round(v, 2), lab] for d, v, lab in limits]
    if row.get('gain') and out['verdict'] == 'PASS':
        s = row.get('spread')
        if s is None:
            return {**out, 'verdict': 'INVALID', 'why': ['no recorded A/A spread for a gain']}
        gain = None if not a else ((b / a - 1) if row.get('gain_direction') == 'up' else (1 - b / a))
        if gain is None or gain <= 2 * s:
            out['verdict'] = 'FAIL'
            shown = None if gain is None else round(gain, 3)
            out['why'].append(f'the gain {shown} does not exceed twice the A/A spread {s}')
    return out


# --- the verdict ------------------------------------------------------------------------------------------------------

def invalid_reasons(rounds: dict, tags, *, control: bool, controls: list) -> list:
    why = []
    hashes = {}
    for tag in tags:
        if tag not in rounds or not rounds[tag]:
            why.append(f'no rounds of {tag}')
            continue
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
            if 'open' in r['parts']:
                for name in controls:
                    c = r['controls'].get(name)
                    if c is None:
                        why.append(f'{where}: control {name} missing')
                    elif not c.get('ok'):
                        why.append(f'{where}: control {name} failed: {c}')
            hashes.setdefault(tag, set()).add(r['files'].get('studio/static/studio/app.js'))
    if not control and len(tags) == 2 and all(t in hashes for t in tags) and hashes[tags[0]] & hashes[tags[1]]:
        why.append('the two trees\' app.js hashes are equal (judge A against A only with --control)')
    return why


def verdict(rounds: dict, table: dict, a: str, b: str, *, control: bool = False) -> dict:
    why = invalid_reasons(rounds, [a, b], control=control, controls=table.get('controls', []))
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
    return {'verdict': answer, 'invalid': why, 'superseded': superseded, 'rows': rows}


# --- the office model: arithmetic against the vhost's zones (section 8) -----------------------------------------------

def rate_per_ms(rate: str) -> float:
    m = re.fullmatch(r'(\d+)r/([sm])', rate)
    if not m:
        raise ValueError(rate)
    return int(m.group(1)) / (1000.0 if m.group(2) == 's' else 60000.0)


def zone_of(zone_maps: dict, method: str, path: str) -> list:
    """The limit_req zones a request counts in, by the vhost's own key maps (the exempt flag 0: an office address)."""
    keys = []
    path = path.split('?', 1)[0].replace('<id>', '00000000-0000-4000-8000-000000000000')
    line = f'0:{method} {path}'
    for key, body in zone_maps.items():
        for m in re.finditer(r'"(~?)\^?([^"]*)"\s+\$cpt_client;', body):
            regex, pattern = m.group(1) == '~', m.group(2)
            if (regex and re.match('^' + pattern, line)) or (not regex and line == pattern):
                keys.append(key)
                break
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
    s = sub.add_parser('spread')
    s.add_argument('--out', required=True)
    s.add_argument('--a', action='append', required=True, help='TAG:ROUND, twice')
    f = sub.add_parser('floors')
    f.add_argument('--spread', required=True)
    f.add_argument('--acceptance', default=str(HERE / 'acceptance.json'))
    args = parser.parse_args(argv)
    if args.command == 'verdict':
        table = json.loads(Path(args.acceptance).read_text())
        answer = verdict(load_rounds(Path(args.out)), table, args.a, args.b, control=args.control)
        print(json.dumps(answer, indent=1, default=str))
        return {'PASS': 0, 'FAIL': 1, 'INVALID': 3}[answer['verdict']]
    if args.command == 'spread':
        rounds = load_rounds(Path(args.out))
        (t1, r1), (t2, r2) = [(x.split(':')[0], int(x.split(':')[1])) for x in args.a]
        print(json.dumps(spread(rounds[t1][r1], rounds[t2][r2]), indent=1, sort_keys=True))
        return 0
    table = json.loads(Path(args.acceptance).read_text())
    print(json.dumps(apply_floors(table, json.loads(Path(args.spread).read_text())), indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main())
