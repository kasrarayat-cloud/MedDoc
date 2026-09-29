"""Offline replay of the frozen ordinary-notes diagnostic set against the checked-out candidate.

No model, no network, no database, no environment file:
  * socket connect/create_connection/getaddrinfo raise before Django loads;
  * dotenv.load_dotenv is replaced by a no-op, so settings never opens an env file;
  * the database host is a nonexistent local socket directory and every connection attempt raises.

The provider is SIMULATED: each field's first `acceptable` selection is fed through the same
validation/adoption functions the application uses (core/tests/test_v3_ordinary_notes.run and
core/tests/test_v3_field_relations.offered, re-keyed by field key so repeated labels stay distinct).
Nothing here measures Sonnet 5.

Usage (from the candidate worktree):
  TMPDIR=/tmp rebuild/.venv/bin/python -B <this file> --state-dir <scratch dir> [--out <json>] [--record]
  --record  writes observed_offline / cost bounds into cases.json (done once, at freeze)
  default   compares against the recorded values and exits 1 on any drift
"""
import argparse
import hashlib
import json
import os
import socket
import sys


def _deny(*_a, **_k):
    raise AssertionError('Network denied (offline diagnostic replay)')


socket.socket.connect = _deny
socket.socket.connect_ex = _deny
socket.create_connection = _deny
socket.getaddrinfo = _deny

HERE = os.path.dirname(os.path.abspath(__file__))
CASES = os.path.join(HERE, 'cases.json')
REBUILD = os.path.abspath(os.path.join(HERE, '../../../../../../rebuild'))


def boot(state_dir):
    import dotenv
    dotenv.load_dotenv = lambda *a, **k: False
    for k in ('QUILLMD_V3_FIELD_RELATIONS', 'QUILLMD_V3_HISTORY_CONTEXT', 'QUILLMD_V3_GENERATION_BATCHES',
              'QUILLMD_WM_NARRATIVE', 'QUILLMD_ENV_MANAGED'):
        os.environ.pop(k, None)
    os.environ.update(QUILLMD_SECRET_KEY='offline-diagnostic-only-no-external-access',
                      QUILLMD_DB_PASSWORD='unused-offline', QUILLMD_DB_NAME='none', QUILLMD_DB_USER='none',
                      QUILLMD_DB_HOST='/nonexistent-offline-socket-dir', QUILLMD_DB_PORT='1',
                      QUILLMD_AI_MODE='fixture', QUILLMD_ADMIN_SITE='0', QUILLMD_HTTPS='0',
                      QUILLMD_STATE_DIR=os.path.abspath(state_dir), DJANGO_SETTINGS_MODULE='quillmd.settings')
    sys.path.insert(0, REBUILD)
    import django
    django.setup()
    from django.db.backends.base import base as dbbase

    def nodb(self, *a, **k):
        raise AssertionError('Database denied (offline diagnostic replay)')
    dbbase.BaseDatabaseWrapper.ensure_connection = nodb


def sha(path):
    with open(path, 'rb') as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--state-dir', required=True)
    ap.add_argument('--out')
    ap.add_argument('--record', action='store_true')
    ap.add_argument('--cases', default=CASES, help='alternative cases.json (for testing the drift check)')
    args = ap.parse_args()
    cases_path = os.path.abspath(args.cases)
    os.makedirs(args.state_dir, exist_ok=True)
    boot(args.state_dir)

    from decimal import Decimal
    from django.test import override_settings
    from core import generation as g, v3_field_relations as rel, billing
    from core.tests.test_v3_ordinary_notes import LIVE

    doc = json.load(open(cases_path))
    settings_for = {'default': dict(LIVE, V3_HISTORY_CONTEXT=False, V3_FIELD_RELATIONS=False,
                                    V3_GENERATION_BATCHES=False, WM_NARRATIVE=False),
                    'field_relations': dict(LIVE, V3_HISTORY_CONTEXT=False, V3_FIELD_RELATIONS=True,
                                            V3_GENERATION_BATCHES=False, WM_NARRATIVE=False)}

    def form_of(case):
        return doc['forms'][case['form']] if isinstance(case['form'], str) else case['form']

    def units_of(notes, fields):
        asked, context, _ = g.v3_generation_fields(fields)
        return g.source_units(notes, asked, context_labels=context)[0]

    def option_ids(f, texts):
        by_text = {o['text']: o['id'] for o in rel.options(f)}
        return [by_text[t] for t in texts]

    def adopt(path, notes, fields, selection):
        """selection: {key: sel}; unlisted fields select nothing."""
        asked, context, v3_fields = g.v3_generation_fields(fields)
        units = g.source_units(notes, asked, context_labels=context)[0]
        by_quote = {u['quote']: u['id'] for u in units}
        if path == 'default':
            chosen = g.UnitSelections(fields=[g.UnitSelection(
                key=f['key'], unit_ids=[by_quote[q] for q in selection.get(f['key'], {}).get('units', [])],
                conflict=bool(selection.get(f['key'], {}).get('conflict'))) for f in asked])
            chosen = g.unit_selections(notes, asked, chosen, context_labels=context)
            answers = g.validate_selections(notes, asked, chosen, context_labels=context,
                                            evidence_contract=g.TAB_CONTRACT)
            return g.v3_adopted(v3_fields, answers, notes, asked, context)
        body = []
        for f in asked:
            s = selection.get(f['key'], {})
            ids = [by_quote[q] for q in s.get('units', [])]
            relations = s.get('relations', {})
            body.append({'key': f['key'], 'unit_ids': ids, 'conflict': bool(s.get('conflict')),
                         'option_ids': option_ids(f, s.get('options', [])),
                         'context': ['answer' if u['id'] in ids else relations.get(u['quote'], 'independent')
                                     for u in units]})
        chosen = rel.FieldSelections.model_validate({'fields': body})
        records = rel.records(notes, fields, context, units, chosen, g.SONNET_5)
        answers = g.validate_selections(notes, asked, chosen, context_labels=context, evidence_contract=g.TAB_CONTRACT,
                                        ordinary_records=records, catalogue=fields)
        return g.v3_adopted(fields, answers, notes, asked, context)

    def state(value):
        s = value.get('status')
        return {'conflict': 'held', 'missing': 'missing', 'supported': 'supported'}.get(s, s)

    def review(notes, fields, key, value):
        """What the stored-answer review path does to a supported generation answer."""
        if value.get('status') != 'supported':
            return None
        f = next(x for x in fields if x['key'] == key)
        governance = g.governance_for(notes, fields)
        row = g.as_currently_governed(governance, notes, {**f, **value})
        decisions = g.governed_decisions(notes, fields, {key: value})
        return {'status': state(row), 'text': row.get('text', ''), 'governed_decision': f['label'] in decisions}

    def observe(path, notes, fields, selection, keys):
        adopted = adopt(path, notes, fields, selection)
        out = {}
        for k in keys:
            v = adopted[k]
            o = {'status': state(v), 'text': v.get('text', '')}
            if v.get('held_candidate'):
                o['held_candidate'] = v['held_candidate'].get('text', '')
            rv = review(notes, fields, k, v)
            if rv is not None:
                o['review'] = rv
            out[k] = o
        return out

    def check(expect, got):
        if expect == 'held':
            return got['status'] == 'held'
        if expect == 'not_supported':
            return got['status'] != 'supported'
        if expect == 'not_yes':
            return got['text'] not in ('Yes', 'Yes.')
        if expect == 'supported':
            return got['status'] == 'supported'
        if expect in ('model_dependent', 'recorded'):
            return True
        raise ValueError(expect)

    def applies(selection, path):
        return path in selection.get('paths', ('default', 'field_relations'))

    def verdict(desired, desired_text, got):
        if desired == 'not_asserted':
            return 'recorded'
        if desired == 'supported':
            if got['status'] != 'supported':
                return 'over_hold'
            return 'as_desired' if desired_text in (None, got['text']) else 'text_mismatch'
        if got['status'] == 'supported':
            return 'leak'
        return 'as_desired' if got['status'] == desired else 'not_supported_other_state'

    def caught(app_should, got):
        if got['status'] != 'supported':
            return 'caught'
        return 'adopted_model_dependent' if app_should == 'model_dependent' else 'leak'

    def slim(o):
        out = {'status': o['status'], 'text': o['text']}
        if 'review' in o:
            out['review_status'] = o['review']['status']
        return out

    results = {'candidate_files': {p: sha(os.path.join(REBUILD, p)) for p in (
                   'core/generation.py', 'core/v3_field_relations.py', 'core/v3_literal_facts.py',
                   'core/v3_destination.py')},
               'cases_sha256_before': sha(cases_path), 'cases': {}}
    total_cost = {'default': Decimal(0), 'field_relations': Decimal(0)}
    drift = []
    for case in doc['cases']:
        fields = form_of(case)
        notes = case['notes']
        keys = [f['key'] for f in fields]
        rec = {'units': {}, 'reference': {}, 'selections': [], 'adversarial': [], 'cost_bound_usd': {}}
        paths = list(case['send_paths'])
        info_paths = [p for p in ('default', 'field_relations') if p not in paths]
        recorded = {}   # (field, kind, index) -> {path: observed}
        for path in paths + info_paths:
            sent = path in paths
            with override_settings(**settings_for[path]):
                units = [u['quote'] for u in units_of(notes, fields)]
                rec['units'][path] = units
                for k, e in case['fields'].items():
                    for s in e['raw_model_expectation']['acceptable'] + e['raw_model_expectation'].get('forbidden', []):
                        for q in list(s['units']) + list(s.get('relations', {})):
                            assert q in units, (case['id'], k, q, units)
                reference = {k: next(s for s in e['raw_model_expectation']['acceptable'] if applies(s, path))
                             for k, e in case['fields'].items()}
                ref = observe(path, notes, fields, reference, keys)
                rec['reference'][path] = {'sent': sent, 'fields': ref}
                for k, e in case['fields'].items():
                    ae = e['app_adoption_expectation']
                    for kind in ('acceptable', 'forbidden'):
                        for i, s in enumerate(e['raw_model_expectation'].get(kind, [])):
                            if not applies(s, path):
                                continue
                            o = ref[k] if s is reference[k] else observe(path, notes, fields, {**reference, k: s}, [k])[k]
                            if kind == 'acceptable':
                                if 'desired' in s:
                                    v = verdict(s['desired'], s.get('desired_text'), o)
                                else:
                                    v = verdict(ae['desired'], ae.get('desired_text'), o)
                            else:
                                v = caught(s.get('app_should', 'not_supported'), o)
                            row = {**slim(o), 'verdict': v}
                            rec['selections'].append({'path': path, 'sent': sent, 'field': k, 'kind': kind,
                                                      'index': i, 'observed': o, 'verdict': v})
                            if sent:
                                recorded.setdefault((k, kind, i), {})[path] = row
                for sim in case.get('adversarial_simulations', []):
                    want = {'both': ['default', 'field_relations']}.get(sim['path'], [sim['path']])
                    if path not in want:
                        continue
                    o = observe(path, notes, fields, sim['selection'], list(sim['expected']))
                    ok = {k: check(v, o[k]) for k, v in sim['expected'].items()}
                    rec['adversarial'].append({'name': sim['name'], 'path': path, 'observed': o, 'meets_expected': ok})
                for ctl in case.get('offline_controls', []):
                    want = {'both': ['default', 'field_relations']}.get(ctl['path'], [ctl['path']])
                    if path not in want:
                        continue
                    ctl_units = [u['quote'] for u in units_of(ctl['notes'], fields)]
                    for s in ctl['selection'].values():
                        for q in s['units']:
                            assert q in ctl_units, (case['id'], ctl['name'], q, ctl_units)
                    o = observe(path, ctl['notes'], fields, ctl['selection'], list(ctl['expected']))
                    ok = {k: check(v, o[k]) for k, v in ctl['expected'].items()}
                    rec.setdefault('controls', []).append({'name': ctl['name'], 'path': path, 'observed': o,
                                                           'meets_expected': ok})
                cost = g.maximum_cost(notes, fields, g.configuration(fields))
                rec['cost_bound_usd'][path] = {'provider_cost_max': str(cost),
                                               'customer_hold_max': str(cost * billing.MULTIPLIER), 'sent': sent}
                if sent:
                    total_cost[path] += cost
        results['cases'][case['id']] = rec

        # Record into (--record) or compare against cases.json.
        for k, e in case['fields'].items():
            for kind in ('acceptable', 'forbidden'):
                for i, s in enumerate(e['raw_model_expectation'].get(kind, [])):
                    got = recorded.get((k, kind, i))
                    if got is None:
                        continue
                    if args.record:
                        s['observed_offline'] = got
                    elif s.get('observed_offline') != got:
                        drift.append({'case': case['id'], 'field': k, 'kind': kind, 'index': i,
                                      'recorded': s.get('observed_offline'), 'now': got})
            ae = e['app_adoption_expectation']
            first = next(i for i, s in enumerate(e['raw_model_expectation']['acceptable'])
                         if all(applies(s, p) for p in paths))
            got = recorded[(k, 'acceptable', first)]
            if args.record:
                ae['observed_offline'] = got
            elif ae.get('observed_offline') != got:
                drift.append({'case': case['id'], 'field': k, 'kind': 'reference',
                              'recorded': ae.get('observed_offline'), 'now': got})
        for sim_rec, sim in ((r, next(x for x in case['adversarial_simulations'] if x['name'] == r['name']))
                             for r in rec['adversarial']):
            if args.record:
                sim.setdefault('observed_offline', {})[sim_rec['path']] = {
                    k: {**slim(v), 'meets_expected': sim_rec['meets_expected'][k]} for k, v in sim_rec['observed'].items()}
            for k, ok in sim_rec['meets_expected'].items():
                if not ok:
                    results.setdefault('adversarial_not_met', []).append(
                        {'case': case['id'], 'simulation': sim_rec['name'], 'purpose': sim.get('purpose'),
                         'path': sim_rec['path'], 'field': k, 'observed': slim(sim_rec['observed'][k])})
        for ctl_rec in rec.get('controls', []):
            ctl = next(x for x in case['offline_controls'] if x['name'] == ctl_rec['name'])
            row = {k: {**slim(v), 'meets_expected': ctl_rec['meets_expected'][k]} for k, v in ctl_rec['observed'].items()}
            if args.record:
                ctl.setdefault('observed_offline', {})[ctl_rec['path']] = row
            elif ctl.get('observed_offline', {}).get(ctl_rec['path']) != row:
                drift.append({'case': case['id'], 'control': ctl['name'], 'path': ctl_rec['path'],
                              'recorded': ctl.get('observed_offline', {}).get(ctl_rec['path']), 'now': row})
            for k, ok in ctl_rec['meets_expected'].items():
                if not ok:
                    results.setdefault('controls_not_met', []).append(
                        {'case': case['id'], 'control': ctl['name'], 'path': ctl_rec['path'], 'field': k,
                         'observed': slim(ctl_rec['observed'][k])})
        if not args.record:
            for sim_rec in rec['adversarial']:
                sim = next(x for x in case['adversarial_simulations'] if x['name'] == sim_rec['name'])
                row = {k: {**slim(v), 'meets_expected': sim_rec['meets_expected'][k]}
                       for k, v in sim_rec['observed'].items()}
                if sim.get('observed_offline', {}).get(sim_rec['path']) != row:
                    drift.append({'case': case['id'], 'simulation': sim['name'], 'path': sim_rec['path'],
                                  'recorded': sim.get('observed_offline', {}).get(sim_rec['path']), 'now': row})
        if args.record:
            case['cost_bound_usd'] = {p: {x: y for x, y in rec['cost_bound_usd'][p].items() if x != 'sent'}
                                      for p in paths}

    results['planned_sends'] = {p: sum(1 for c in doc['cases'] if p in c['send_paths'])
                                for p in ('default', 'field_relations')}
    results['provider_cost_max_total_usd'] = {p: str(v) for p, v in total_cost.items()}
    results['provider_cost_max_total_usd']['all'] = str(sum(total_cost.values()))
    results['rates_used'] = {'input_per_million': str(settings_for['default']['AI_INPUT_RATE']),
                             'output_per_million': str(settings_for['default']['AI_OUTPUT_RATE']),
                             'source': 'core/tests/test_v3_ordinary_notes.LIVE (documented Sonnet 5 $2/$10)'}
    if not args.record and doc.get('offline_replay', {}).get('candidate_files_sha256') != results['candidate_files']:
        drift.append({'kind': 'candidate_files', 'recorded': doc.get('offline_replay', {}).get('candidate_files_sha256'),
                      'now': results['candidate_files']})
    results['drift'] = drift
    if args.record:
        doc['offline_replay'] = {
            'script': 'offline_replay.py',
            'candidate_files_sha256': results['candidate_files'],
            'planned_sends': results['planned_sends'],
            'provider_cost_max_total_usd': results['provider_cost_max_total_usd'],
            'customer_hold_max_total_usd': str(sum(total_cost.values()) * billing.MULTIPLIER),
            'rates_used': results['rates_used'],
            'adversarial_not_met': results.get('adversarial_not_met', []),
            'controls_not_met': results.get('controls_not_met', []),
        }
        with open(cases_path, 'w') as fh:
            json.dump(doc, fh, indent=1, ensure_ascii=False)
            fh.write('\n')
    results['cases_sha256_after'] = sha(cases_path)
    if args.out:
        with open(args.out, 'w') as fh:
            json.dump(results, fh, indent=1, ensure_ascii=False)
            fh.write('\n')
    print(json.dumps({'planned_sends': results['planned_sends'],
                      'provider_cost_max_total_usd': results['provider_cost_max_total_usd'],
                      'adversarial_not_met': len(results.get('adversarial_not_met', [])),
                      'drift': len(drift), 'recorded': args.record}, indent=1))
    return 1 if drift else 0


if __name__ == '__main__':
    sys.exit(main())
