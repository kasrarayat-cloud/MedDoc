"""Fixed synthetic Word stage: pure source/XML/temporary ledger, zero resources."""
from copy import deepcopy
import ast
import dataclasses
import hashlib
import io
from pathlib import Path
import re
import unittest

from ops import provider_campaign as pc, standing_qa as st, standing_qa_word_structure as wq
from . import network_guard
from .test_standing_qa import Base, RUNNER_COMMIT, repository

CANONICAL = Path(__file__).parents[3] / 'docs/foundation/mutations/20261004-quillmd-v1-standing-api-testing-5.md'


def declaration_text():
    """Use the existing declaration grammar and authority; admit only three new sends."""
    text = CANONICAL.read_text()
    text = re.sub(r'^stage:.*\n', '', text, flags=re.M)
    text = re.sub(r'^(?:notes_mapping_review|elicited_fixture_manifest|transcription_\w+):.*\n', '', text, flags=re.M)
    text = re.sub(r'^pricing_version transcription:.*\n', '', text, flags=re.M)
    text = text.replace('request_deadline_seconds: 180', 'request_deadline_seconds: 480')
    text = text.replace('max_sends_per_run: 6', 'max_sends_per_run: 1')
    return text + ('\nword_structure_fixture_manifest: ' + wq.MANIFEST_SHA256 + '\n'
                   'stage: word_structure_qualification sends 3 requires none\n')


def setUpModule():
    network_guard.start()


def tearDownModule():
    network_guard.stop()


class WordStructureFixedStage(Base):
    def declaration(self, text=None):
        root, path = repository(self, declaration_text() if text is None else text, name=CANONICAL.name)
        return st.declared_standing(path, repository=root, uses=('live',), out=io.StringIO())

    def test_complete_plan_has_exact_three_once_only_send_identities(self):
        inputs = wq.frozen_inputs(); sends = st.standing_plan(wq.STAGE, inputs)
        self.assertEqual(tuple(s.case for s in sends), wq.CASE_IDS)
        self.assertEqual([s.index for s in sends], [1, 2, 3])
        self.assertEqual([s.id for s in sends], ['word-structure:' + n for n in wq.CASE_IDS])
        self.assertEqual({s.path for s in sends}, {'field_relations'})
        self.assertEqual({s.pricing_key for s in sends}, {wq.PRICING})
        self.assertEqual(st.stage_inputs(wq.STAGE, self.declaration()), inputs)

    def test_actual_normal_notes_field_persists_exact_v2_and_proves_old_terminal_LF_failure(self):
        # Compile this exact declaration expression, without importing models,
        # setting up Django, creating an account or opening a database.
        from django import forms
        source = Path(__file__).parents[2] / 'core/forms.py'
        tree = ast.parse(source.read_bytes())
        class_ = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'EncounterForm')
        declaration = next(n for n in class_.body if isinstance(n, ast.Assign)
                           and any(isinstance(t, ast.Name) and t.id == 'notes' for t in n.targets))
        field = eval(compile(ast.Expression(declaration.value), str(source), 'eval'), {'forms': forms})
        self.assertTrue(field.strip)
        old = wq.MANIFEST.with_name('word-structure-qualification-v1.json')
        import json
        original = json.loads(old.read_bytes()); current = wq.frozen_inputs()['word_structure']
        self.assertEqual(hashlib.sha256(old.read_bytes()).hexdigest(), current['previous_manifest_sha256'])
        for before, after in zip(original['cases'], current['cases']):
            self.assertEqual(after['notes'], before['notes'][:-1])
            self.assertTrue(before['notes'].endswith('\n'))
            self.assertNotEqual(field.clean(before['notes']), before['notes'])
            self.assertEqual(field.clean(before['notes']), after['notes'])
            self.assertEqual(field.clean(after['notes']), after['notes'])
            for key in ('id','form','desired_supported','required_holds','physical_expected','accepted_date_values'):
                self.assertEqual(after.get(key), before.get(key))
            self.assertNotEqual(field.clean(after['notes'].replace('not documented', 'documented')), after['notes'])
        self.assertEqual(original['forms'], current['forms'])

    def test_changed_missing_reordered_sources_and_arbitrary_sends_refuse(self):
        exact = wq.frozen_inputs()
        for mutate in (lambda x: x['word_structure']['cases'].pop(),
                       lambda x: x['word_structure']['cases'].reverse(),
                       lambda x: x['word_structure']['cases'][0].update(notes='Changed.'),
                       lambda x: x['word_structure']['forms'][wq.FORM_IDS[0]].update(sha256='0' * 64)):
            changed = deepcopy(exact); mutate(changed)
            with self.assertRaises(pc.Refused):wq.plan_sends(changed)
        send = wq.plan_sends(exact)[0]
        for key, value in [('id', 'word-structure:WQ99'), ('case', 'WQ02'), ('path', 'default'),
                           ('form', 'restricted-original'), ('pricing_key', 'ordinary_notes')]:
            with self.subTest(key=key), self.assertRaises(pc.Refused):
                st.send_inputs(dataclasses.replace(send, **{key: value}), exact)

    def test_deterministic_real_catalogues_and_generation_role_admission(self):
        from documents import word_v3 as word
        from core import generation as generation
        inputs = wq.frozen_inputs()['word_structure']; totals = [0, 0, 0]
        for case in inputs['cases']:
            spec = inputs['forms'][case['form']]; raw = wq.build(case['form'])
            self.assertEqual(raw, wq.build(case['form']))
            self.assertEqual(hashlib.sha256(raw).hexdigest(), spec['sha256'])
            detected = word.inspect(raw)
            self.assertEqual(detected['fields'], spec['fields'])
            self.assertEqual([wq.issue_identity(r) for r in detected.get('coverage_issues', [])], spec['source_issues'])
            asked, held, _ = generation.v3_generation_fields(spec['fields'])
            asked_labels = {field['label'] for field in asked}
            self.assertTrue(set(case['desired_supported']) <= asked_labels)
            human = set(case['required_holds']) - {'Allergies'}
            self.assertTrue(human <= set(held)); self.assertFalse(human & asked_labels)
            self.assertIn('Allergies', asked_labels)
            totals = [totals[0] + len(case['desired_supported']), totals[1] + len(human), totals[2] + 1]
            values = {f['key']: case['desired_supported'][f['label']] for f in spec['fields']
                      if f['label'] in case['desired_supported']}
            self.assertTrue(word.fill(raw, spec['fields'], values))
            self.assertEqual(word.fill(raw, spec['fields'], {}), raw)
        self.assertEqual(totals, [7, 5, 3])
        with self.assertRaises(pc.Refused):wq.build('original-corpus')

    def test_mapping_admission_retains_exact_fields_and_only_named_source_exclusions(self):
        from documents.import_selection import digest
        inputs = wq.frozen_inputs()['word_structure']
        for spec in inputs['forms'].values():
            fields = spec['fields']
            manifest = {'engine': 'v3', 'source_sha256': spec['sha256'],
                'mapping_sha256': digest(fields), 'initial_mapping_sha256': digest(fields),
                'coverage': {'block_generation': bool(spec['source_issues']),
                    'selected_engine_issues': deepcopy(spec['source_issues'])}}
            self.assertEqual(wq.mapping_admission(spec['sha256'], fields, manifest, spec), manifest['coverage'])
            for mutate in (lambda x: x.update(source_sha256='0' * 64),
                           lambda x: x.update(mapping_sha256='0' * 64),
                           lambda x: x['coverage'].update(comparison_unresolved=True),
                           lambda x: x['coverage'].update(layout_quarantine='foreign'),
                           lambda x: x['coverage'].update(block_generation=not bool(spec['source_issues'])),
                           lambda x: x['coverage'].update(selected_engine_issues=[{'code': 'unmapped_answer'}])):
                changed = deepcopy(manifest); mutate(changed)
                with self.assertRaises(pc.Refused):wq.mapping_admission(spec['sha256'], fields, changed, spec)
            with self.assertRaises(pc.Refused):wq.mapping_admission(spec['sha256'], fields[:-1], manifest, spec)

    def test_actual_normalization_scores_seven_answers_and_eight_holds_separately(self):
        counts = {}; inputs = wq.frozen_inputs()['word_structure']
        for case in inputs['cases']:
            fields = inputs['forms'][case['form']]['fields']
            raw = {f['key']: {'status': 'supported', 'text': case['desired_supported'][f['label']]}
                   if f['label'] in case['desired_supported'] else {'status': 'conflict', 'text': ''} for f in fields}
            outcomes = wq.elicited.usefulness(case, fields, wq.stages.steps.field_outcomes(raw))
            for value in outcomes.values():counts[value] = counts.get(value, 0) + 1
            for field in fields:
                if field['label'] in case['required_holds']:
                    for status in ('supported', 'held', 'missing', 'conflict', 'unknown'):
                        bad = deepcopy(raw); bad[field['key']] = {'status': status, 'text': 'Dr Invented'}
                        result = wq.elicited.usefulness(case, fields, wq.stages.steps.field_outcomes(bad))
                        self.assertEqual(result[field['key']], 'unsupported_accepted')
                else:
                    bad = deepcopy(raw); bad[field['key']] = {'status': 'conflict', 'text': ''}
                    result = wq.elicited.usefulness(case, fields, wq.stages.steps.field_outcomes(bad))
                    self.assertEqual(result[field['key']], 'over_held')
        self.assertEqual(counts, {'supported_correct': 7, 'held_correct': 8})

    def test_predeclared_date_alternatives_use_independent_calendar_not_writer(self):
        inputs = wq.frozen_inputs()['word_structure']
        for case in (inputs['cases'][0], inputs['cases'][2]):
            fields = inputs['forms'][case['form']]['fields']
            raw = {f['key']: {'status': 'supported', 'text': case['desired_supported'][f['label']]}
                   if f['label'] in case['desired_supported'] else {'status': 'conflict', 'text': ''} for f in fields}
            field = next(f for f in fields if f['label'] == 'Visit date')
            for value in case['accepted_date_values']['Visit date']:
                changed = deepcopy(raw); changed[field['key']]['text'] = value
                outcomes = wq.usefulness(case, fields, wq.stages.steps.field_outcomes(changed))
                self.assertEqual(outcomes[field['key']], 'supported_correct')
            for value in ('2026-03-15', '05/10/2026', '02/29/2026', '03/14/2026 extra', '03-14-2026'):
                changed = deepcopy(raw); changed[field['key']]['text'] = value
                self.assertEqual(wq.usefulness(case, fields, wq.stages.steps.field_outcomes(changed))[field['key']],
                                 'unsupported_accepted')
        self.assertEqual(wq.calendar_identity('02/29/2024'), '2024-02-29')
        self.assertEqual(wq.calendar_identity('29/Feb/2024'), '2024-02-29')
        self.assertEqual(wq.calendar_identity('12/12/2026'), '2026-12-12')
        self.assertIsNone(wq.calendar_identity('05/10/2026'))
        self.assertIsNone(wq.calendar_identity('2026-02-29'))

    def test_three_send_declaration_needs_exact_hash_count_and_stage(self):
        d = self.declaration()
        self.assertEqual([(s.id, s.sends, s.requires) for s in d.stages], [(wq.STAGE, 3, None)])
        self.assertEqual((d.max_sends_per_run, d.max_output_tokens_per_request, d.request_deadline_seconds), (1, 20000, 480))
        for changed in (declaration_text().replace('sends 3', 'sends 2'),
                        declaration_text().replace(wq.MANIFEST_SHA256, '0' * 64),
                        declaration_text().replace('stage: word_structure_qualification sends 3 requires none',
                                                   'stage: model_check sends 1 requires none'),
                        declaration_text().replace('word_structure_fixture_manifest: ' + wq.MANIFEST_SHA256 + '\n', '')):
            with self.assertRaises(pc.Refused):self.declaration(changed)
        root, path = repository(self, CANONICAL.read_text(), name=CANONICAL.name)
        old = st.declared_standing(path, repository=root, uses=('live',), out=io.StringIO())
        self.assertEqual(sum(s.sends for s in old.stages), 24)
        self.assertFalse(any(s.id == wq.STAGE for s in old.stages))

    def test_unsafe_result_stops_without_relabelling_old_worker_record(self):
        record = {'verdict': pc.classify_case({'f': 'unsupported_accepted'}, []),
                  'stops_stage': False, 'recorded_as': 'held_ambiguity'}
        original = deepcopy(record)
        qualified, stops = st.qualification_result(wq.STAGE, record, False)
        self.assertTrue(stops); self.assertTrue(qualified['stops_stage']); self.assertEqual(record, original)
        self.assertEqual(st.qualification_result('notes_comparison', record, False), (record, False))
        with self.assertRaises(pc.Refused):st.qualification_result(wq.STAGE, {'verdict': {}}, False)

    def test_unknown_attempt_is_terminal_and_attempted_case_never_becomes_eligible_again(self):
        d = dataclasses.replace(self.declaration(), qa_signing_key_file=None)
        campaign = self.campaign(d); inputs = st.stage_inputs(wq.STAGE, campaign.declaration)
        sends = wq.plan_sends(inputs); send = sends[0]
        st.begin_run(campaign, wq.STAGE, [send], inputs, 1, {'runner_commit': RUNNER_COMMIT})
        campaign.admit(wq.STAGE, '0.1', runner_commit=RUNNER_COMMIT)
        attempt = self.notes_attempt(campaign, send, inputs, changes={'stage': wq.STAGE})
        campaign.ledger.write_attempt(attempt)
        self.assertNotIn(send, st.remaining_sends(campaign, wq.STAGE, sends))
        st.settle(campaign)
        self.assertEqual(campaign.ledger.stage_state(wq.STAGE)['state'], 'failed')
        with self.assertRaises(pc.Refused):campaign.stage_open(wq.STAGE)
