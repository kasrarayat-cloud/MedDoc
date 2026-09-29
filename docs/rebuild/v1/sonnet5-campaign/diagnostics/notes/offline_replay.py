"""Offline replay of the frozen ordinary-notes diagnostic set against the checked-out candidate.

No model, no network, no database, no environment file:
  * socket connect/create_connection/getaddrinfo raise before Django loads;
  * dotenv.load_dotenv is replaced by a no-op, so settings never opens an env file;
  * the database host is a nonexistent local socket directory and every connection attempt raises.

The provider is SIMULATED: selections are fed through the same validation/adoption functions the application uses
(the core/tests/test_v3_ordinary_notes.run and core/tests/test_v3_field_relations.offered shapes, keyed by field key
so repeated labels stay distinct) and the stored-answer review governance. Nothing here measures Sonnet 5.

Since the 2026-09-29 repair (CHECK.md N5, N6, N7):
  * the forms are the real synthetic .docx files built by build_note_forms.py; cases.json carries each form's sha256
    and the fields the candidate's v3 inspect gives it, and this script re-inspects every form and reports drift;
  * observations are NOT written into cases.json. cases.json holds only expectations and is frozen (its sha256 is in
    mapping/EXPECTED-SHA256SUMS) BEFORE anything is recorded; --record refuses unless it still matches, and writes
    offline-observations.json;
  * every listed selection is recorded REPLAYED ALONE (every other field selecting nothing), so its outcome does not
    depend on what the reference selected elsewhere; when the reference's other selections change it, the entry
    carries observed_with_reference and depends_on_other_fields=true;
  * --replay scores WHOLE responses (a live answer is replayed as it was returned, never looked up entry by entry).

Usage (from the candidate worktree):
  TMPDIR=/tmp rebuild/.venv/bin/python -B <this file> --state-dir <scratch dir> [--out <json>] [--record]
      --record   writes offline-observations.json (once, after the freeze)
      default    compares against offline-observations.json and exits 1 on any drift
  ... --replay <responses.json>   replay whole responses: {"N01": {"default": {"v3_1": {"units": [...] | "unit_ids":
                                  [...], "conflict": false, "options": [...], "relations": {...}}, ...}}}
"""
import argparse
import datetime as dt
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
OBSERVATIONS = os.path.join(HERE, 'offline-observations.json')
MANIFEST = os.path.join(HERE, '..', 'mapping', 'EXPECTED-SHA256SUMS')
REBUILD = os.path.abspath(os.path.join(HERE, '../../../../../../rebuild'))
PATHS = ('default', 'field_relations')


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


def path_settings():
    """The two send paths, as the repository's own live-mode test settings (documented Sonnet 5 $2/$10)."""
    from core.tests.test_v3_ordinary_notes import LIVE
    return {'default': dict(LIVE, V3_HISTORY_CONTEXT=False, V3_FIELD_RELATIONS=False,
                            V3_GENERATION_BATCHES=False, WM_NARRATIVE=False),
            'field_relations': dict(LIVE, V3_HISTORY_CONTEXT=False, V3_FIELD_RELATIONS=True,
                                    V3_GENERATION_BATCHES=False, WM_NARRATIVE=False)}


def sha(path):
    with open(path, 'rb') as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def frozen_cases_sha():
    """The cases.json sha256 frozen in mapping/EXPECTED-SHA256SUMS, or None."""
    if not os.path.exists(MANIFEST):
        return None
    for line in open(MANIFEST):
        parts = line.split()
        if len(parts) == 2 and parts[1] == '../notes/cases.json':
            return parts[0]
    return None


def form_fields(doc, case):
    form = case['form']
    if isinstance(form, str):
        entry = doc['forms'][form]
        return entry['fields'] if isinstance(entry, dict) else entry
    return form


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--state-dir', required=True)
    ap.add_argument('--out')
    ap.add_argument('--record', action='store_true')
    ap.add_argument('--cases', default=CASES, help='alternative cases.json (for testing the drift check)')
    ap.add_argument('--observations', default=OBSERVATIONS)
    ap.add_argument('--replay', help='whole responses to replay (see the module docstring)')
    ap.add_argument('--skip-form-check', action='store_true', help='do not re-inspect the .docx forms')
    args = ap.parse_args()
    cases_path = os.path.abspath(args.cases)
    os.makedirs(args.state_dir, exist_ok=True)
    if args.record and frozen_cases_sha() != sha(cases_path):
        print('cases.json does not match the frozen manifest (mapping/EXPECTED-SHA256SUMS); freeze the expectations '
              'before recording observations', file=sys.stderr)
        return 1
    boot(args.state_dir)

    from decimal import Decimal
    from django.test import override_settings
    from core import generation as g, v3_field_relations as rel, billing

    doc = json.load(open(cases_path))
    settings_for = path_settings()
    drift = []

    # ─── the forms are real: re-inspect each and compare with the fields the cases carry ─────────────────────
    forms_checked = {}
    if not args.skip_form_check:
        from documents import service
        for name, entry in doc['forms'].items():
            if not isinstance(entry, dict) or 'docx' not in entry:
                continue
            path = os.path.join(entry['runtime_dir'], entry['docx'])
            ok_sha = os.path.exists(path) and sha(path) == entry['sha256']
            ok_fields = ok_sha and service.inspect_template(path, engine='v3')['fields'] == entry['fields']
            forms_checked[name] = {'sha256_matches': ok_sha, 'v3_inspect_equals_case_fields': bool(ok_fields)}
            if not (ok_sha and ok_fields):
                drift.append({'form': name, **forms_checked[name]})

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
        by_id = {u['id'] for u in units}

        def ids(s):
            if 'unit_ids' in s:
                assert all(i in by_id for i in s['unit_ids']), s
                return list(s['unit_ids'])
            return [by_quote[q] for q in s.get('units', [])]
        if path == 'default':
            chosen = g.UnitSelections(fields=[g.UnitSelection(
                key=f['key'], unit_ids=ids(selection.get(f['key'], {})),
                conflict=bool(selection.get(f['key'], {}).get('conflict'))) for f in asked])
            chosen = g.unit_selections(notes, asked, chosen, context_labels=context)
            answers = g.validate_selections(notes, asked, chosen, context_labels=context,
                                            evidence_contract=g.TAB_CONTRACT)
            return g.v3_adopted(v3_fields, answers, notes, asked, context)
        body = []
        for f in asked:
            s = selection.get(f['key'], {})
            chosen_ids = ids(s)
            relations = s.get('relations', {})
            body.append({'key': f['key'], 'unit_ids': chosen_ids, 'conflict': bool(s.get('conflict')),
                         'option_ids': option_ids(f, s.get('options', [])),
                         'context': ['answer' if u['id'] in chosen_ids else relations.get(u['quote'], 'independent')
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
        return path in selection.get('paths', PATHS)

    def texts_of(entry):
        if 'desired_texts' in entry:
            return entry['desired_texts']
        return [entry['desired_text']] if entry.get('desired_text') is not None else None

    def verdict(desired, desired_texts, got):
        if desired == 'not_asserted':
            return 'recorded'
        if desired == 'usefulness_loss':          # CHECK.md N2: a silent blank is a loss, never "correct"
            return 'leak' if got['status'] == 'supported' else 'usefulness_loss'
        if desired == 'supported':
            if got['status'] != 'supported':
                return 'over_hold'
            return 'as_desired' if desired_texts is None or got['text'] in desired_texts else 'text_mismatch'
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

    def same_set(a, b):
        return sorted(a) == sorted(b)

    def match_entry(field_exp, path, sel, units):
        """The listed entry a whole-response selection matches (unit set, conflict, and options on relations)."""
        quotes = sel.get('units')
        if quotes is None:
            by_id = {u['id']: u['quote'] for u in units}
            quotes = [by_id[i] for i in sel.get('unit_ids', [])]
        for kind in ('acceptable', 'forbidden'):
            for i, s in enumerate(field_exp['raw_model_expectation'].get(kind, [])):
                if not applies(s, path):
                    continue
                if same_set(s['units'], quotes) and bool(s.get('conflict')) == bool(sel.get('conflict')) and (
                        path == 'default' or same_set(s.get('options', []), sel.get('options', []))) and (
                        path == 'default' or 'relations' not in s or s['relations'] == sel.get('relations', {})):
                    return kind, i
        return 'unlisted', None

    # ─── --replay: score whole responses ──────────────────────────────────────────────────────────────────────
    if args.replay:
        responses = json.load(open(args.replay))
        by_case = {c['id']: c for c in doc['cases']}
        out = {}
        for cid, per_path in responses.items():
            case = by_case[cid]
            fields = form_fields(doc, case)
            for path, selection in per_path.items():
                with override_settings(**settings_for[path]):
                    units = units_of(case['notes'], fields)
                    got = observe(path, case['notes'], fields, selection, [f['key'] for f in fields])
                rows = {}
                for k, e in case['fields'].items():
                    kind, index = match_entry(e, path, selection.get(k, {}), units)
                    ae = e['app_adoption_expectation']
                    entry = e['raw_model_expectation'][kind][index] if kind != 'unlisted' else {}
                    rows[k] = {**slim(got[k]), 'matched': kind, 'index': index,
                               'verdict': (verdict(entry.get('desired', ae['desired']),
                                                   texts_of(entry) if 'desired' in entry else texts_of(ae), got[k])
                                           if kind == 'acceptable' else
                                           caught(entry.get('app_should', 'not_supported'), got[k])
                                           if kind == 'forbidden' else 'adjudicate_by_hand')}
                out.setdefault(cid, {})[path] = rows
        print(json.dumps(out, indent=1, ensure_ascii=False))
        return 0

    # ─── replay every listed selection, alone and beside the reference ────────────────────────────────────────
    results = {'candidate_files': {p: sha(os.path.join(REBUILD, p)) for p in (
                   'core/generation.py', 'core/v3_field_relations.py', 'core/v3_literal_facts.py',
                   'core/v3_destination.py')},
               'cases_sha256': sha(cases_path), 'forms_checked': forms_checked, 'cases': {}}
    total_cost = {p: Decimal(0) for p in PATHS}
    tallies = {}
    for case in doc['cases']:
        fields = form_fields(doc, case)
        notes = case['notes']
        keys = [f['key'] for f in fields]
        rec = {'units': {}, 'reference': {}, 'fields': {}, 'entries': [], 'adversarial': [], 'controls': [],
               'cost_bound_usd': {}}
        paths = list(case['send_paths'])
        info_paths = [p for p in PATHS if p not in paths]
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
                rec['reference'][path] = {'sent': sent, 'fields': {k: slim(v) for k, v in ref.items()}}
                for k, e in case['fields'].items():
                    ae = e['app_adoption_expectation']
                    first = next(i for i, s in enumerate(e['raw_model_expectation']['acceptable'])
                                 if all(applies(s, p) for p in paths))
                    ref_entry = e['raw_model_expectation']['acceptable'][first]
                    if applies(ref_entry, path):
                        o = ref[k] if reference[k] is ref_entry else observe(path, notes, fields, {**reference, k: ref_entry}, [k])[k]
                        v = verdict(ae['desired'], texts_of(ae), o)
                        rec['fields'].setdefault(k, {})[path] = {**slim(o), 'verdict': v, 'sent': sent}
                        if sent:
                            tallies.setdefault(path, {}).setdefault(v, 0)
                            tallies[path][v] += 1
                    for kind in ('acceptable', 'forbidden'):
                        for i, s in enumerate(e['raw_model_expectation'].get(kind, [])):
                            if not applies(s, path):
                                continue
                            alone = observe(path, notes, fields, {k: s}, [k])[k]
                            beside = ref[k] if s is reference[k] else observe(path, notes, fields, {**reference, k: s}, [k])[k]
                            if kind == 'acceptable':
                                v = verdict(s['desired'], texts_of(s), alone) if 'desired' in s else \
                                    verdict(ae['desired'], texts_of(ae), alone)
                            else:
                                v = caught(s.get('app_should', 'not_supported'), alone)
                            row = {'field': k, 'kind': kind, 'index': i, 'path': path, 'sent': sent,
                                   'observed_alone': slim(alone), 'verdict': v,
                                   'depends_on_other_fields': slim(alone) != slim(beside)}
                            if alone.get('held_candidate'):
                                row['held_candidate'] = alone['held_candidate']
                            if row['depends_on_other_fields']:
                                row['observed_with_reference'] = slim(beside)
                            rec['entries'].append(row)
                for sim in case.get('adversarial_simulations', []):
                    want = {'both': list(PATHS)}.get(sim['path'], [sim['path']])
                    if path not in want:
                        continue
                    o = observe(path, notes, fields, sim['selection'], list(sim['expected']))
                    ok = {k: check(v, o[k]) for k, v in sim['expected'].items()}
                    rec['adversarial'].append({'name': sim['name'], 'path': path, 'purpose': sim.get('purpose'),
                                               'observed': {k: slim(v) for k, v in o.items()}, 'meets_expected': ok})
                for ctl in case.get('offline_controls', []):
                    want = {'both': list(PATHS)}.get(ctl['path'], [ctl['path']])
                    if path not in want:
                        continue
                    ctl_units = [u['quote'] for u in units_of(ctl['notes'], fields)]
                    for s in ctl['selection'].values():
                        for q in s['units']:
                            assert q in ctl_units, (case['id'], ctl['name'], q, ctl_units)
                    o = observe(path, ctl['notes'], fields, ctl['selection'], list(ctl['expected']))
                    ok = {k: check(v, o[k]) for k, v in ctl['expected'].items()}
                    rec['controls'].append({'name': ctl['name'], 'path': path,
                                            'observed': {k: slim(v) for k, v in o.items()}, 'meets_expected': ok})
                if sent:
                    cost = g.maximum_cost(notes, fields, g.configuration(fields))
                    rec['cost_bound_usd'][path] = {'provider_cost_max': str(cost),
                                                   'customer_hold_max': str(cost * billing.MULTIPLIER)}
                    total_cost[path] += cost
                    frozen = (case.get('cost_bound_usd') or {}).get(path, {}).get('provider_cost_max')
                    if frozen is not None and frozen != str(cost):
                        drift.append({'case': case['id'], 'path': path, 'cost_bound_frozen': frozen, 'now': str(cost)})
        results['cases'][case['id']] = rec

    results['planned_sends'] = {p: sum(1 for c in doc['cases'] if p in c['send_paths']) for p in PATHS}
    results['provider_cost_max_total_usd'] = {p: str(v) for p, v in total_cost.items()}
    results['provider_cost_max_total_usd']['all'] = str(sum(total_cost.values()))
    results['reference_verdicts_on_sent_paths'] = tallies
    results['adversarial_not_met'] = [{'case': cid, 'simulation': a['name'], 'path': a['path'], 'field': k,
                                       'observed': a['observed'][k]}
                                      for cid, r in results['cases'].items() for a in r['adversarial']
                                      for k, ok in a['meets_expected'].items() if not ok]
    results['controls_not_met'] = [{'case': cid, 'control': a['name'], 'path': a['path'], 'field': k,
                                    'observed': a['observed'][k]}
                                   for cid, r in results['cases'].items() for a in r['controls']
                                   for k, ok in a['meets_expected'].items() if not ok]
    results['entries_depending_on_other_fields'] = [
        {'case': cid, **{k: e[k] for k in ('field', 'kind', 'index', 'path', 'observed_alone', 'observed_with_reference')}}
        for cid, r in results['cases'].items() for e in r['entries'] if e['depends_on_other_fields']]
    results['rates_used'] = {'input_per_million': str(settings_for['default']['AI_INPUT_RATE']),
                             'output_per_million': str(settings_for['default']['AI_OUTPUT_RATE']),
                             'source': 'core/tests/test_v3_ordinary_notes.LIVE (documented Sonnet 5 $2/$10)'}
    comparable = {k: results[k] for k in ('candidate_files', 'cases_sha256', 'forms_checked', 'cases', 'planned_sends',
                                         'provider_cost_max_total_usd', 'reference_verdicts_on_sent_paths')}
    if args.record:
        record = {'schema': 'quillmd.sonnet5-diagnostics.ordinary-notes.observations.v2',
                  'recorded_at': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
                  'script_sha256': sha(os.path.abspath(__file__)),
                  'what': ('What candidate 8e3dcfd0 did, offline with a SIMULATED provider, with every listed selection '
                           '(replayed alone), with each case\'s reference response, and with the adversarial '
                           'simulations and controls. Recorded AFTER cases.json was frozen.'),
                  **{k: results[k] for k in results}}
        with open(args.observations, 'w') as fh:
            json.dump(record, fh, indent=1, ensure_ascii=False)
            fh.write('\n')
    else:
        recorded = json.load(open(args.observations)) if os.path.exists(args.observations) else {}
        if not recorded:
            drift.append({'kind': 'observations', 'missing': args.observations})
        for k, v in comparable.items():
            if recorded.get(k) != v:
                drift.append({'kind': k, 'differs': True})
    results['drift'] = drift
    if args.out:
        with open(args.out, 'w') as fh:
            json.dump(results, fh, indent=1, ensure_ascii=False)
            fh.write('\n')
    print(json.dumps({'planned_sends': results['planned_sends'],
                      'provider_cost_max_total_usd': results['provider_cost_max_total_usd'],
                      'reference_verdicts_on_sent_paths': tallies,
                      'adversarial_not_met': len(results['adversarial_not_met']),
                      'controls_not_met': len(results['controls_not_met']),
                      'entries_depending_on_other_fields': len(results['entries_depending_on_other_fields']),
                      'forms_checked': forms_checked, 'drift': drift, 'recorded': args.record}, indent=1))
    return 1 if drift else 0


if __name__ == '__main__':
    sys.exit(main())
