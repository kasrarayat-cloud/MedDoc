#!/usr/bin/env python3
"""Offline validation of the campaign runner: every stop condition, the ledger, evidence retention and cleanup,
driven end to end through the real runner (its re-executed, scrubbed process and the candidate's product path) against
the loopback mock provider. No provider request is possible: offline mode refuses anything but the loopback mock and
the fixed offline marker.

    python ops/wm_narrative_campaign_offline.py --out DIR --engine BUILD --pg-admin ADMIN.json

ADMIN.json names a THROWAWAY synthetic Postgres (host, port, user, password) whose superuser may create and drop the
per-scenario `quillmd_wmn_campaign_v*` databases. Each scenario gets a fresh database, campaign directory and mock; the
databases are dropped afterwards and the campaign directories are kept as the validation's evidence.
"""
import argparse
import json
import os
import signal
import socket
import subprocess
import sys
import time
from decimal import Decimal, ROUND_UP
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUNNER = HERE / 'wm_narrative_campaign.py'
MOCK = HERE / 'wm_narrative_mock_provider.py'
sys.path.insert(0, str(HERE))
import wm_narrative_campaign as campaign  # noqa: E402

ALL = list(campaign.STAGE_1)


def replay(*cases):
    return [{'kind': 'replay', 'case': c} for c in cases]


#: (name, mock script, runner extras, expectations)
SCENARIOS = [
    ('pass', replay(*ALL), {}, {'exit': 0, 'verdict': 'PASS', 'classes': ['adopted'] * 5, 'requests': 5}),
    ('wrong-answer-stops', replay(*ALL), {'override': 'C18'},
     {'exit': 3, 'verdict': 'FAIL', 'classes': ['adopted', 'adopted'], 'requests': 2, 'stop': 'WRONG ANSWER'}),
    ('one-transport-retry', replay('C14') + [{'kind': 'status', 'code': 529}] + replay('C18', 'C19', 'H05', 'H12'), {},
     {'exit': 0, 'verdict': 'PASS', 'requests': 6,
      'classes': ['adopted', 'transport_failure', 'adopted', 'adopted', 'adopted', 'adopted'], 'kinds_retry': 1}),
    ('two-consecutive-transport-failures', replay('C14') + [{'kind': 'hang', 'seconds': 20}, {'kind': 'drop'}], {},
     {'exit': 4, 'verdict': 'STOPPED', 'classes': ['adopted', 'transport_failure', 'transport_failure'], 'requests': 3,
      'stop': 'Two consecutive transport failures'}),
    ('retries-exhausted', [{'kind': 'status', 'code': 529}] + replay('C14') + [{'kind': 'status', 'code': 429}]
     + replay('C18') + [{'kind': 'status', 'code': 500}], {},
     {'exit': 4, 'verdict': 'STOPPED', 'requests': 5, 'stop': 'retries used',
      'classes': ['transport_failure', 'adopted', 'transport_failure', 'adopted', 'transport_failure']}),
    ('configuration-failure-stops', [{'kind': 'status', 'code': 401}], {},
     {'exit': 4, 'verdict': 'STOPPED', 'classes': ['configuration_failure'], 'requests': 1, 'stop': 'configuration_failure'}),
    ('unusable-output-is-absorbed', replay('C14') + [{'kind': 'truncated', 'case': 'C18'}] + replay('C19', 'H05', 'H12'), {},
     {'exit': 5, 'verdict': 'INCOMPLETE', 'requests': 5,
      'classes': ['adopted', 'output_unusable', 'adopted', 'adopted', 'adopted'], 'absorbed': 1}),
    ('cost-above-maximum-stops', [{'kind': 'overcost', 'case': 'C14'}], {},
     {'exit': 4, 'verdict': 'STOPPED', 'requests': 1, 'stop': 'above its maximum'}),
    ('model-mismatch-stops', [{'kind': 'model', 'case': 'C14', 'model': 'claude-other-model'}], {},
     {'exit': 4, 'verdict': 'STOPPED', 'requests': 1, 'stop': 'answered as'}),
    ('key-shaped-text-is-caught', [{'kind': 'text', 'case': 'C14', 'append': 'sk-ant-offline-FAKE-not-a-key-000000'}]
     + replay('C18', 'C19', 'H05', 'H12'), {},
     {'exit': 4, 'verdict': 'STOPPED', 'requests': 5, 'stop': 'KEY FOUND IN EVIDENCE'}),
]


def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def admin_sql(admin, statement):
    import psycopg
    with psycopg.connect(host=admin['host'], port=admin['port'], user=admin['user'], password=admin['password'],
                         dbname='postgres', autocommit=True) as connection:
        return connection.execute(statement).fetchall() if statement.lstrip().upper().startswith('SELECT') else \
            connection.execute(statement)


class Scenario:
    def __init__(self, out, admin, engine, name, number):
        self.name, self.admin, self.engine = name, admin, engine
        self.dir = Path(out) / f'{number:02d}-{name}'
        self.dir.mkdir(mode=0o700, parents=True)
        self.campaign = self.dir / 'campaign'
        self.db_name = f'quillmd_wmn_campaign_v{number:02d}'
        self.mock = None

    def start(self, script):
        admin_sql(self.admin, f'DROP DATABASE IF EXISTS {self.db_name}')
        admin_sql(self.admin, f'CREATE DATABASE {self.db_name}')
        (self.dir / 'db.json').write_text(json.dumps({'name': self.db_name, 'user': self.admin['user'],
                                                      'password': self.admin['password'], 'host': self.admin['host'],
                                                      'port': self.admin['port']}))
        (self.dir / 'db.json').chmod(0o600)
        self.restart_mock(script)

    def restart_mock(self, script):
        self.stop_mock()
        self.port = free_port()
        (self.dir / 'script.json').write_text(json.dumps(script))
        self.mock = subprocess.Popen([sys.executable, '-B', str(MOCK), '--port', str(self.port), '--script',
                                      str(self.dir / 'script.json'), '--log', str(self.dir / 'mock-requests.jsonl')],
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        CHILDREN.append(self.mock)
        for _ in range(100):
            try:
                socket.create_connection(('127.0.0.1', self.port), timeout=0.2).close()
                break
            except OSError:
                time.sleep(0.1)
        (self.dir / 'provider.json').write_text(json.dumps({
            'ANTHROPIC_API_KEY': campaign.OFFLINE_KEY, 'ANTHROPIC_BASE_URL': f'http://127.0.0.1:{self.port}',
            'QUILLMD_AI_PROVIDER': 'anthropic', 'QUILLMD_AI_MODEL': campaign.EXPECTED_MODEL,
            'QUILLMD_AI_INPUT_RATE': '3', 'QUILLMD_AI_OUTPUT_RATE': '15', 'QUILLMD_AI_CACHED_RATE': '0.30',
            'QUILLMD_PROVIDER_DISCOUNT_RATE': '0', 'QUILLMD_DEEPGRAM_RATE_PER_MINUTE': '0.0043',
            'QUILLMD_DEEPGRAM_RATE_PER_SECOND': ''}))

    def command(self, stage=1, mode='offline', extra=()):
        return [sys.executable, '-B', str(RUNNER), 'run', '--mode', mode, '--stage', str(stage),
                '--campaign-dir', str(self.campaign), '--db', str(self.dir / 'db.json'), '--engine', str(self.engine),
                *(['--provider', str(self.dir / 'provider.json')] if mode == 'offline' else []),
                '--offline-timeout', '3', '--offline-retry-wait', '0.5', *extra]

    def run(self, stage=1, mode='offline', extra=(), timeout=1200):
        started = time.time()
        runner = subprocess.Popen(self.command(stage, mode, extra), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                  start_new_session=True, env={'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8'})
        CHILDREN.append(runner)
        try:
            out, err = runner.communicate(timeout=timeout)
        finally:
            if runner.poll() is None:
                os.killpg(runner.pid, signal.SIGKILL)
                runner.wait(timeout=30)
        (self.dir / f'runner-stage{stage}-{mode}.log').write_text(out + '\n--- stderr ---\n' + err)
        return runner.returncode, round(time.time() - started, 1)

    def stop_mock(self):
        if self.mock and self.mock.poll() is None:
            os.killpg(self.mock.pid, signal.SIGTERM)
            self.mock.wait(timeout=10)
        self.mock = None

    def finish(self):
        for child in CHILDREN:
            if child.poll() is None:
                try:
                    os.killpg(child.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                child.wait(timeout=30)
        self.stop_mock()
        admin_sql(self.admin, f"SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '{self.db_name}'")
        admin_sql(self.admin, f'DROP DATABASE IF EXISTS {self.db_name}')

    def requests(self):
        path = self.dir / 'mock-requests.jsonl'
        return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


def check(scenario, expected, code):
    """Every assertion the scenario makes, as (name, passed, detail)."""
    out = []
    c = scenario.campaign
    verdict = json.loads((c / 'stage-1-verdict.json').read_text()) if (c / 'stage-1-verdict.json').exists() else {}
    report = json.loads((c / 'report-stage-1.json').read_text()) if (c / 'report-stage-1.json').exists() else {}
    rows = campaign.load_ledger(c / 'ledger') if (c / 'ledger').exists() else []
    classes = [o['class'] if o else None for _, o in rows]
    out.append(('exit status', code == expected['exit'], f'{code} (expected {expected["exit"]})'))
    out.append(('verdict', verdict.get('verdict') == expected['verdict'], verdict.get('verdict')))
    if 'classes' in expected:
        out.append(('ledger outcome classes', classes == expected['classes'], classes))
    out.append(('every attempt has an outcome', all(o is not None for _, o in rows), len(rows)))
    received = scenario.requests()
    out.append(('provider requests received == expected', len(received) == expected['requests'],
                f'{len(received)} (expected {expected["requests"]})'))
    ran = sum(1 for _, o in rows if o and o.get('worker_ran'))
    out.append(('every received request is a ledger attempt', len(received) == ran, f'{len(received)} vs {ran}'))
    out.append(('no request carried anything but the offline marker',
                all(r['credential_is_offline_marker'] for r in received), len(received)))
    out.append(('every request used the declared model and max_tokens',
                all(r['model'] == campaign.EXPECTED_MODEL and r['max_tokens'] == 12000 and r['has_output_config']
                    for r in received), len(received)))
    if 'stop' in expected:
        out.append(('stop reason', any(expected['stop'] in s for s in verdict.get('stops', [])), verdict.get('stops')))
    if 'kinds_retry' in expected:
        retries = sum(1 for a, _ in rows if a['kind'] == 'retry')
        out.append(('retries recorded', retries == expected['kinds_retry'], retries))
    # Provider exposure: the runner's own total equals the ledger recomputed independently, and an attempt that did
    # not settle is counted at its maximum x 1.1.
    recomputed = sum((campaign.exposure(a, o) for a, o in rows), Decimal('0'))
    stated = Decimal(report.get('totals_stage', {}).get('provider_exposure', '-1'))
    out.append(('provider exposure recomputes', stated == recomputed.quantize(campaign.CENT), f'{stated} vs {recomputed}'))
    for a, o in rows:
        if o and o['class'] in ('transport_failure', 'configuration_failure', 'unknown', 'interrupted_unknown'):
            out.append((f'attempt {a["number"]} unsettled counted at its maximum',
                        campaign.exposure(a, o) == campaign.attempt_bound(a['maximum_cost']), campaign.exposure(a, o)))
    records = sorted(c.glob('db-records-stage-1*.json'))
    out.append(('database records exported', bool(records), [p.name for p in records]))
    if records:
        db = json.loads(records[0].read_text())
        debits = -sum((Decimal(str(e['amount'])) for e in db['ledger'] if e['kind'] != 'campaign_grant'), Decimal('0'))
        charged = Decimal(report.get('totals_stage', {}).get('wallet_charged', '-1'))
        out.append(('wallet charged == ledger debits net of reversals', charged == debits.quantize(campaign.CENT, rounding=ROUND_UP),
                    f'{charged} vs {debits}'))
        grants = [e for e in db['ledger'] if e['kind'] == 'campaign_grant']
        out.append(('wallet funded once, to the stage limit', len(grants) == 1
                    and Decimal(str(grants[0]['amount'])) == campaign.STAGES[1]['wallet_limit'], grants))
        if 'absorbed' in expected:
            absorbed = [p for p in db['platform_costs'] if p['kind'] == 'absorbed_failure']
            out.append(('unusable output absorbed (provider paid, customer not)', len(absorbed) == expected['absorbed'],
                        absorbed))
    adopted = sum(1 for _, o in rows if o and o['class'] == 'adopted')
    out.append(('a replay file per adopted answer', len(list((c / 'replay').glob('*.json'))) >= adopted - 0,
                len(list((c / 'replay').glob('*.json')))))
    out.append(('a score per adopted answer', len(list((c / 'scores').glob('*.json'))) == adopted,
                len(list((c / 'scores').glob('*.json')))))
    out.append(('private evidence (0700 dirs, 0600 files)',
                all((p.stat().st_mode & 0o077) == 0 for p in [c, *c.rglob('*')] if not p.is_symlink()), str(c)))
    return out


def evidence_checks(scenario, label=''):
    """The owner's retention condition, re-checkable from the files alone: every request the provider received was
    captured before it was sent (canonically identical), and every attempt has a manifest entry whose request, response
    and replay files exist and match their recorded sha256."""
    c = scenario.campaign
    out = []
    rows = campaign.load_ledger(c / 'ledger') if (c / 'ledger').exists() else []
    captured = [json.loads(p.read_text()) for p in sorted((c / 'requests').glob('[0-9]*-request.json'))]
    received = scenario.requests()
    out.append((f'{label}a captured request per request received, identical',
                sorted(r['arguments_sha256'] for r in captured) == sorted(r.get('request_canonical_sha256') for r in received)
                and all(r['arguments'].get('model') and r['arguments'].get('messages') for r in captured),
                (len(captured), len(received))))
    entries = {p.name: json.loads(p.read_text()) for p in sorted((c / 'manifest').glob('[0-9]*.json'))}
    missing = [a['number'] for a, _ in rows if f'{a["number"]:03d}-{a["case"]}.json' not in entries]
    out.append((f'{label}a manifest entry per attempt', not missing and len(entries) == len(rows), (len(entries), missing)))
    bad = []
    for name, entry in entries.items():
        for part in ('request', 'response', 'replay'):
            ref = entry.get(part)
            if ref and (not (c / ref['file']).exists() or campaign.file_sha256(c / ref['file']) != ref['sha256']):
                bad.append((name, part))
        if entry['class'] == 'adopted' and not (entry.get('response_model') and entry.get('usage') and entry.get('request')):
            bad.append((name, 'adopted without model, usage or request'))
        if entry.get('request') and entry.get('request_arguments_sha256') not in {r['arguments_sha256'] for r in captured}:
            bad.append((name, 'request hash'))
        if entry.get('replay_written_by_this_attempt') and not entry.get('replay_matches_response'):
            bad.append((name, 'a replay this attempt wrote differs from its answer'))
    out.append((f'{label}every manifest file present and hash-matched', not bad, bad[:5]))
    outcomes = {a['number']: o for a, o in rows}
    disagree = [n for n, e in ((e['attempt'], e) for e in entries.values())
                if outcomes.get(n) and (e['class'] != outcomes[n]['class']
                                        or e.get('provider_actual_cost') != outcomes[n].get('provider_actual_cost'))]
    out.append((f'{label}the manifest agrees with the ledger', not disagree, disagree))
    return out


CHILDREN = []


def _terminate(signum, frame):
    raise SystemExit(f'signal {signum}')


def main():
    signal.signal(signal.SIGTERM, _terminate)      # (a killed driver still stops its mock, its runner and drops its
    signal.signal(signal.SIGINT, _terminate)       #  database — the runner's review: all three outlived a SIGTERM)
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', required=True)
    parser.add_argument('--engine', required=True)
    parser.add_argument('--pg-admin', required=True)
    parser.add_argument('--only', nargs='*')
    args = parser.parse_args()
    admin = json.loads(Path(args.pg_admin).read_text())
    Path(args.out).mkdir(mode=0o700, parents=True, exist_ok=False)
    results, number = [], 0
    for name, script, extras, expected in SCENARIOS:
        number += 1
        if args.only and name not in args.only:
            continue
        s = Scenario(args.out, admin, args.engine, name, number)
        try:
            s.start(script)
            extra = []
            if extras.get('override'):
                # A key the case really expects supported, re-declared missing: the correct pre-fill now scores as a
                # wrong one. This exercises the runner's stop wiring only; the product is not being judged here.
                cases = json.loads((HERE.parent / 'core/tests/benchmarks/wm_narrative/cases.json').read_text())['cases']
                case = next(c for c in cases if c['id'] == extras['override'])
                key = next(k for k, v in case['expected_fields'].items() if v['outcome'] == 'supported')
                extra = ['--expectation-override', json.dumps(
                    {'case': extras['override'], 'key': key, 'expected': {'outcome': 'missing'}})]
            code, seconds = s.run(extra=extra)
            checks = check(s, expected, code) + evidence_checks(s)
        except Exception as error:
            checks, seconds = [('scenario ran', False, f'{type(error).__name__}: {error}')], None
        finally:
            s.finish()
        if seconds is not None:      # (and it all survives the synthetic database's removal and the mock's end)
            dropped = not admin_sql(admin, f"SELECT 1 FROM pg_database WHERE datname = '{s.db_name}'")
            checks += [('the synthetic database is gone', dropped, s.db_name)] + evidence_checks(s, 'after cleanup: ')
            checks.append(('after cleanup: the database records export survives',
                           bool(sorted(s.campaign.glob('db-records-stage-1*.json'))), s.campaign.name))
        results.append({'scenario': name, 'seconds': seconds, 'passed': all(ok for _, ok, _ in checks),
                        'checks': [{'check': n, 'passed': ok, 'detail': str(d)[:300]} for n, ok, d in checks]})
        print(f'{"PASS" if results[-1]["passed"] else "FAIL"}  {name}  ({seconds}s)', flush=True)
    results.extend(special_cases(args, admin, number))
    leftover = admin_sql(admin, "SELECT datname FROM pg_database WHERE datname LIKE 'quillmd_wmn_campaign%'")
    results.append({'scenario': 'cleanup', 'passed': not leftover,
                    'checks': [{'check': 'no scenario database left', 'passed': not leftover, 'detail': str(leftover)}]})
    print(f'{"PASS" if not leftover else "FAIL"}  cleanup (databases left: {leftover})')
    (Path(args.out) / 'validation.json').write_text(json.dumps(results, indent=1))
    failed = [r['scenario'] for r in results if not r['passed']]
    print(json.dumps({'scenarios': len(results), 'failed': failed}))
    return 1 if failed else 0


def special_cases(args, admin, number):
    """The interrupted run, the gates that must refuse before anything is read or sent, and a stage never re-run."""
    results = []
    # An interrupted run: killed while its request hangs, then resumed. The attempt with no outcome is recorded as an
    # unknown provider outcome, counted at its maximum, and its case is retried (a retry, from the stage's budget).
    s = Scenario(args.out, admin, args.engine, 'interrupted-run-resumes', number + 1)
    checks = []
    try:
        s.start([{'kind': 'hang', 'seconds': 60}])
        runner = subprocess.Popen(s.command(), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                  start_new_session=True, env={'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8'})
        for _ in range(600):
            if s.requests():
                break
            time.sleep(0.2)
        attempt_written = any((s.campaign / 'ledger').glob('*-attempt.json'))
        os.killpg(runner.pid, signal.SIGKILL)
        runner.wait(timeout=30)
        checks.append(('the attempt was written before the request', attempt_written, attempt_written))
        s.restart_mock(replay(*ALL))
        code, _ = s.run()
        rows = campaign.load_ledger(s.campaign / 'ledger')
        first = rows[0][1] or {}
        checks += [
            ('killed attempt recorded as an unknown outcome', first.get('class') == 'interrupted_unknown', first.get('class')),
            ('it carries its job', bool(first.get('job')), first.get('job')),
            ('unknown counted at its maximum', campaign.exposure(*rows[0]) == campaign.attempt_bound(rows[0][0]['maximum_cost']),
             str(campaign.exposure(*rows[0]))),
            ('its case retried as a retry', rows[1][0]['case'] == rows[0][0]['case'] and rows[1][0]['kind'] == 'retry',
             [r[0]['kind'] for r in rows]),
            ('the resumed stage completed', code == 0, code),
        ] + evidence_checks(s)       # (the killed attempt's request was captured before it was sent; recovery wrote its entry)
    except Exception as error:
        checks.append(('scenario ran', False, f'{type(error).__name__}: {error}'))
    finally:
        s.finish()
    results.append({'scenario': 'interrupted-run-resumes', 'passed': all(ok for _, ok, _ in checks),
                    'checks': [{'check': n, 'passed': ok, 'detail': str(d)[:300]} for n, ok, d in checks]})
    print(f'{"PASS" if results[-1]["passed"] else "FAIL"}  interrupted-run-resumes')
    # Killed after the worker ADOPTED a wrong draft and before its outcome was written (the runner's review: recorded as
    # unknown, the case was resent, the wrong answer never scored and the stage PASSED). The restart must record it as
    # adopted, score it, stop FAIL, and resend nothing.
    s = Scenario(args.out, admin, args.engine, 'killed-after-adoption', number + 3)
    checks = []
    try:
        s.start([{'kind': 'replay', 'case': 'C18'}] + replay(*ALL))       # (C14 answered with C18's response: wrong)
        code, _ = s.run(extra=['--offline-crash', 'after_worker'])
        checks.append(('the first run died after the worker', code == 137, code))
        code, _ = s.run()
        rows = campaign.load_ledger(s.campaign / 'ledger')
        first = rows[0][1] or {}
        verdict = json.loads((s.campaign / 'stage-1-verdict.json').read_text())
        checks += [
            ('recovered as adopted, from the job record', first.get('class') == 'adopted' and first.get('recovered'), first.get('class')),
            ('scored and stopped as a wrong answer', code == 3 and any('WRONG' in x for x in verdict['stops']), verdict['stops']),
            ('nothing resent', len(s.requests()) == 1 and len(rows) == 1, (len(s.requests()), len(rows))),
            ('its wallet charge is in the ledger', Decimal(first.get('wallet_charged') or '0') > 0, first.get('wallet_charged')),
        ] + evidence_checks(s)       # (the adopted answer's request, response and replay, retained by recovery)
    except Exception as error:
        checks.append(('scenario ran', False, f'{type(error).__name__}: {error}'))
    finally:
        s.finish()
    results.append({'scenario': 'killed-after-adoption', 'passed': all(ok for _, ok, _ in checks),
                    'checks': [{'check': n, 'passed': ok, 'detail': str(d)[:300]} for n, ok, d in checks]})
    print(f'{"PASS" if results[-1]["passed"] else "FAIL"}  killed-after-adoption')
    # Round 19's focused pass over the runner: each interruption is recorded from the product's own records, exactly as a
    # finished attempt would be, and nothing is resent that the provider already answered.
    def interrupted(name, offset, script, crash, expect):
        s = Scenario(args.out, admin, args.engine, name, number + offset)
        checks = []
        try:
            s.start(script)
            code, _ = s.run(extra=['--offline-crash', crash])
            checks.append((f'the first run ended ({crash})', code == expect['first_exit'], code))
            if expect.get('restart', True):
                code, _ = s.run()
            rows = campaign.load_ledger(s.campaign / 'ledger')
            first = rows[0][1] or {}
            verdict = json.loads((s.campaign / 'stage-1-verdict.json').read_text())
            checks += [(label, test(code, rows, first, verdict, s), detail(code, rows, first, verdict, s))
                       for label, test, detail in expect['checks']]
            checks += evidence_checks(s)
        except Exception as error:
            checks.append(('scenario ran', False, f'{type(error).__name__}: {error}'))
        finally:
            s.finish()
        results.append({'scenario': name, 'passed': all(ok for _, ok, _ in checks),
                        'checks': [{'check': n, 'passed': ok, 'detail': str(d)[:300]} for n, ok, d in checks]})
        print(f'{"PASS" if results[-1]["passed"] else "FAIL"}  {name}')

    interrupted('killed-before-the-worker', 5, replay(*ALL), 'before_worker', {'first_exit': 137, 'checks': [
        ('recorded as never run, from the product', lambda c, r, f, v, s: f.get('class') == 'not_run' and f.get('recovered'),
         lambda c, r, f, v, s: f.get('class')),
        ('its queued job was cancelled, never run by the next attempt', lambda c, r, f, v, s: f.get('state') == 'cancelled',
         lambda c, r, f, v, s: f.get('state')),
        ('counted at zero, provably', lambda c, r, f, v, s: campaign.exposure(*r[0]) == 0, lambda c, r, f, v, s: str(campaign.exposure(*r[0]))),
        ('its case resent as a retry, and the stage passed', lambda c, r, f, v, s: r[1][0]['kind'] == 'retry' and c == 0
         and r[1][1]['class'] == 'adopted', lambda c, r, f, v, s: (c, [x[0]['kind'] for x in r])),
        ('the provider saw only the five answered requests', lambda c, r, f, v, s: len(s.requests()) == 5,
         lambda c, r, f, v, s: len(s.requests())),
    ]})
    interrupted('wrong-model-then-killed', 6, [{'kind': 'model', 'case': 'C14', 'model': 'claude-other-model'}]
                + replay('C18', 'C19', 'H05', 'H12'), 'after_worker', {'first_exit': 137, 'checks': [
        ('recovered with the model the provider answered as', lambda c, r, f, v, s: f.get('response_model') == 'claude-other-model',
         lambda c, r, f, v, s: f.get('response_model')),
        ('the model stop fires', lambda c, r, f, v, s: c == 4 and any('answered as' in x for x in v['stops']),
         lambda c, r, f, v, s: (c, v['stops'])),
        ('nothing resent', lambda c, r, f, v, s: len(s.requests()) == 1, lambda c, r, f, v, s: len(s.requests())),
    ]})
    interrupted('configuration-failure-then-killed', 7, [{'kind': 'status', 'code': 401}] * 3, 'after_worker',
                {'first_exit': 137, 'checks': [
        ('recovered as a configuration failure, from the audit row', lambda c, r, f, v, s: f.get('class') == 'configuration_failure',
         lambda c, r, f, v, s: (f.get('class'), f.get('error_class'))),
        ('stopped without a retry', lambda c, r, f, v, s: c == 4 and len(s.requests()) == 1 and len(r) == 1,
         lambda c, r, f, v, s: (c, len(s.requests()), len(r))),
    ]})
    interrupted('sigterm-as-the-answer-lands', 8, [{'kind': 'replay', 'case': 'C18'}] + replay(*ALL), 'term_after_worker',
                {'first_exit': 3, 'restart': False, 'checks': [
        ('the adopted draft was scored before the verdict', lambda c, r, f, v, s: any('WRONG' in x for x in v['stops']),
         lambda c, r, f, v, s: v['stops']),
        ('its score is kept', lambda c, r, f, v, s: any((s.campaign / 'scores').glob('001-*.json')),
         lambda c, r, f, v, s: sorted(p.name for p in (s.campaign / 'scores').glob('*.json'))),
        ('nothing further sent', lambda c, r, f, v, s: len(s.requests()) == 1, lambda c, r, f, v, s: len(s.requests())),
    ]})
    # Round 20's focused pass over the runner: no verdict while the record is incomplete, and never a resume against
    # another database.
    def record_of(s):
        opened = sorted(s.campaign.glob('report-stage-1-open-*.json'))
        return ((s.campaign / 'stage-1-verdict.json').exists(),
                json.loads(opened[-1].read_text()) if opened else None)

    def scenario(name, offset, body):
        s = Scenario(args.out, admin, args.engine, name, number + offset)
        checks = []
        try:
            checks += body(s)
            checks += evidence_checks(s)
        except Exception as error:
            checks.append(('scenario ran', False, f'{type(error).__name__}: {error}'))
        finally:
            s.finish()
        results.append({'scenario': name, 'passed': all(ok for _, ok, _ in checks),
                        'checks': [{'check': n, 'passed': ok, 'detail': str(d)[:300]} for n, ok, d in checks]})
        print(f'{"PASS" if results[-1]["passed"] else "FAIL"}  {name}')

    def killed_in_flight(s):
        runner = subprocess.Popen(s.command(), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                  start_new_session=True, env={'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8'})
        CHILDREN.append(runner)
        for _ in range(600):
            if s.requests():
                break
            time.sleep(0.2)
        os.killpg(runner.pid, signal.SIGKILL)
        runner.wait(timeout=30)

    def another_database(s):
        s.start([{'kind': 'hang', 'seconds': 60}])
        killed_in_flight(s)
        other = s.db_name + 'b'
        admin_sql(admin, f'DROP DATABASE IF EXISTS {other}')
        admin_sql(admin, f'CREATE DATABASE {other}')
        try:
            original = (s.dir / 'db.json').read_text()
            (s.dir / 'db.json').write_text(json.dumps({**json.loads(original), 'name': other}))
            s.restart_mock(replay(*ALL))
            code, _ = s.run()
            log = (s.dir / 'runner-stage1-offline.log').read_text()
            verdict, opened = record_of(s)
            out = [('a resume against another database is refused', code == 2 and 'never resumed against another database'
                    in log, (code, log[-200:])),
                   ('nothing further was sent', len(s.requests()) == 1, len(s.requests())),
                   ('no verdict was written', not verdict, verdict)]
            (s.dir / 'db.json').write_text(original)
        finally:
            admin_sql(admin, f"SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '{other}'")
            admin_sql(admin, f'DROP DATABASE IF EXISTS {other}')
        code, _ = s.run()
        rows = campaign.load_ledger(s.campaign / 'ledger')
        first = rows[0][1] or {}
        return out + [
            ('resumed against its own database, the killed attempt is an unknown outcome',
             first.get('class') == 'interrupted_unknown' and first.get('job'), first.get('class')),
            ('counted at its maximum', campaign.exposure(*rows[0]) == campaign.attempt_bound(rows[0][0]['maximum_cost']),
             str(campaign.exposure(*rows[0]))),
            ('its case retried, and the stage passed', code == 0 and rows[1][0]['kind'] == 'retry', (code, len(rows)))]

    def between_the_records(s):
        s.start(replay(*ALL))
        code, _ = s.run(extra=['--offline-crash', 'term_before_manifest'])
        verdict = json.loads((s.campaign / 'stage-1-verdict.json').read_text())
        entry = json.loads((s.campaign / 'manifest' / '001-C14.json').read_text())
        return [('the run stopped on the signal', code == 4 and verdict['verdict'] == 'STOPPED', (code, verdict['stops'])),
                ('the attempt still has its manifest entry, completed after the interruption',
                 entry['completed_after_interruption'] and entry['class'] == 'adopted', entry.get('class')),
                ('nothing further was sent', len(s.requests()) == 1, len(s.requests()))]

    def database_lost(s):
        s.start([{'kind': 'hang', 'seconds': 8}] + replay(*ALL))
        runner = subprocess.Popen(s.command(), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                  start_new_session=True, env={'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8'})
        CHILDREN.append(runner)
        for _ in range(600):
            if s.requests():
                break
            time.sleep(0.2)
        admin_sql(admin, f"SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '{s.db_name}'")
        runner.communicate(timeout=600)
        verdict, opened = record_of(s)
        out = [('the run ended OPEN, with no verdict', runner.returncode == 6 and not verdict and opened
                and opened.get('verdict') == 'OPEN', (runner.returncode, verdict, (opened or {}).get('open'))),
               ('the open report names the attempt with no outcome',
                any('no outcome' in gap for gap in (opened or {}).get('open', [])), (opened or {}).get('open'))]
        code, _ = s.run()
        rows = campaign.load_ledger(s.campaign / 'ledger')
        first = rows[0][1] or {}
        return out + [
            ('the next start recorded it from the product, at its maximum',
             first.get('recovered') and campaign.exposure(*rows[0]) == campaign.attempt_bound(rows[0][0]['maximum_cost']),
             (first.get('class'), str(campaign.exposure(*rows[0])))),
            ('and the stage completed', code == 0, code)]

    def before_the_world(s):
        s.start([{'kind': 'replay', 'case': 'C18'}] + replay(*ALL))         # (C14 answered with C18's response: wrong)
        first_code, _ = s.run(extra=['--offline-crash', 'after_worker'])
        code, _ = s.run(extra=['--offline-crash', 'term_at_world'])
        verdict, opened = record_of(s)
        out = [('the first run died after the worker', first_code == 137, first_code),
               ('the restart ended before its world: OPEN, no verdict, the unscored draft named', code == 6 and not verdict
                and any('not scored' in gap for gap in (opened or {}).get('open', [])), (code, (opened or {}).get('open')))]
        code, _ = s.run()
        verdict = json.loads((s.campaign / 'stage-1-verdict.json').read_text())
        rows = campaign.load_ledger(s.campaign / 'ledger')
        return out + [('the next start scored it and stopped FAIL', code == 3 and any('WRONG' in x for x in verdict['stops']),
                       (code, verdict['stops'])),
                      ('nothing resent', len(s.requests()) == 1 and len(rows) == 1, (len(s.requests()), len(rows)))]

    scenario('resumed-against-another-database', 9, another_database)
    scenario('killed-between-outcome-and-manifest', 10, between_the_records)
    scenario('database-lost-in-flight', 11, database_lost)
    scenario('killed-before-the-world-on-restart', 12, before_the_world)
    # Gates that refuse (exit 2) before any database, configuration or request is touched.
    s = Scenario(args.out, admin, args.engine, 'gates-refuse', number + 4)
    checks = []
    try:
        s.start(replay(*ALL))
        code, _ = s.run(mode='live')
        log = (s.dir / 'runner-stage1-live.log').read_text()
        checks.append(('live mode outside its fixed evidence place, or without a committed declaration, is refused',
                       code == 2 and ('declaration' in log or 'nowhere else' in log), log[-200:]))
        checks.append(('no request was made', not s.requests(), len(s.requests())))
        code, _ = s.run(stage=2)
        log = (s.dir / 'runner-stage2-offline.log').read_text()
        checks.append(('stage 2 is gated on a stage 1 PASS', code == 2 and 'gated' in log, log[-200:]))
        code, _ = s.run()
        checks.append(('stage 1 passes', code == 0, code))
        code, _ = s.run()
        log = (s.dir / 'runner-stage1-offline.log').read_text()
        checks.append(('a stage with a verdict is never re-run', code == 2 and 'never re-run' in log, log[-200:]))
        checks.append(('the refused re-run made no request', len(s.requests()) == 5, len(s.requests())))
        bad = json.loads((s.dir / 'provider.json').read_text())
        bad['ANTHROPIC_BASE_URL'] = 'https://api.anthropic.com'
        (s.dir / 'provider-bad.json').write_text(json.dumps(bad))
        cmd = s.command(stage=1)
        cmd[cmd.index('--provider') + 1] = str(s.dir / 'provider-bad.json')
        cmd[cmd.index('--campaign-dir') + 1] = str(s.dir / 'campaign-bad')
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120, env={'PATH': '/usr/bin:/bin'})
        checks.append(('offline mode refuses a non-loopback provider', result.returncode == 2 and 'loopback' in result.stderr,
                       result.stderr[-200:]))
    except Exception as error:
        checks.append(('scenario ran', False, f'{type(error).__name__}: {error}'))
    finally:
        s.finish()
    results.append({'scenario': 'gates-refuse', 'passed': all(ok for _, ok, _ in checks),
                    'checks': [{'check': n, 'passed': ok, 'detail': str(d)[:300]} for n, ok, d in checks]})
    print(f'{"PASS" if results[-1]["passed"] else "FAIL"}  gates-refuse')
    return results


if __name__ == '__main__':
    sys.exit(main())
