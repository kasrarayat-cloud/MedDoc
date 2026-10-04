"""Bounded context contract proofs; all classifications are simulated, not model quality."""
import copy
import hashlib
import json
import os
from pathlib import Path
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase, override_settings

from core import generation as g, v3_history_context as h
from core.jobs import enqueue, run_one
from core.models import Encounter, Job
from core.security import private_path
from documents import word_v3 as w
from .test_v3_ordinary_notes import LIVE, field, run, unit_response
from .test_v3_ordinary_input import ordinary_input_form
from .test_word_v3_workflow import V3Fixture, part_text
from .consent_coverage_fixture import assert_unreviewed_consent_refused, review_protected_consent


def cases():
    path = Path(__file__).resolve().parents[3] / 'docs/rebuild/v1/ordinary-contract-next-20260928/three-history-cases.json'
    return json.loads(path.read_text())['cases']


def body(notes, fields, picks, overrides=None):
    asked, context, _ = g.v3_generation_fields(fields)
    units = g.source_units(notes, asked, context_labels=context)[0]
    by_quote = {u['quote']: u['id'] for u in units}
    fields_out = [{'key': f['key'], 'unit_ids': [by_quote[q] for q in picks.get(f['label'], [])],
                   'conflict': False} for f in asked]
    partitions = []
    for key, f in h.targets(asked, units).items():
        selected = next(a['unit_ids'] for a in fields_out if a['key'] == key)
        partitions.append({'key': key, 'units': [{'unit_id': u['id'],
            'relation': (overrides or {}).get(u['quote'], 'answer' if u['id'] in selected else 'context_only')}
            for u in units]})
    return {'fields': fields_out, 'history_context': partitions}


def offered(notes, fields, picks, overrides=None):
    asked, context, v3_fields = g.v3_generation_fields(fields)
    selections = h.HistorySelections.model_validate(body(notes, fields, picks, overrides))
    g.unit_selections(notes, asked, selections, context_labels=context)
    units = g.source_units(notes, asked, context_labels=context)[0]
    records = h.records(notes, asked, context, units, selections)
    answers = g.validate_selections(notes, asked, selections, context_labels=context,
        evidence_contract=g.TAB_CONTRACT, history_records=records)
    answers = g.v3_adopted(v3_fields, answers, notes, asked, context)
    return {f['label']: answers[f['key']] for f in fields}


@override_settings(V3_HISTORY_CONTEXT=True)
class HistoryContextContract(SimpleTestCase):
    def test_original_five_history_targets_gain_without_changing_original_picks(self):
        for case in cases():
            out = offered(case['notes'], case['fields'], case['original_all_picks'])
            for target in case['targets']:
                label = target['field']
                with self.subTest(case=case['name'], label=label):
                    answer = out[label]
                    if case['name'] == 'r1-note2' and label == 'History of present illness':
                        self.assertEqual(answer['status'], 'conflict')
                        continue
                    value = '\n'.join(target['original_selection'])
                    self.assertEqual((answer['status'], answer['text']), ('supported', value))
                    self.assertEqual(answer['evidence'], target['evidence'])
                    f = next(f for f in case['fields'] if f['label'] == label)
                    self.assertEqual(g.governed_decisions(case['notes'], case['fields'], {f['key']: answer}), [])
            if case['name'] == 'r1-note4':
                for label in ('Allergies', 'Medications', 'Smoker'):
                    self.assertEqual(out[label]['status'], 'conflict')

    def test_partition_is_complete_closed_and_bound_to_exact_output(self):
        case = cases()[0]
        asked, context, _ = g.v3_generation_fields(case['fields'])
        units = g.source_units(case['notes'], asked, context_labels=context)[0]
        original = body(case['notes'], case['fields'], case['original_all_picks'])
        mutations = []
        for mutate in (
            lambda d: d['history_context'].pop(),
            lambda d: d['history_context'].append(copy.deepcopy(d['history_context'][0])),
            lambda d: d['history_context'][0]['units'].pop(),
            lambda d: d['history_context'][0]['units'].append(copy.deepcopy(d['history_context'][0]['units'][0])),
            lambda d: d['history_context'][0]['units'][0].update(unit_id=999),
            lambda d: d['history_context'][0]['units'][0].update(relation='context_only'),
        ):
            data = copy.deepcopy(original); mutate(data); mutations.append(data)
        for data in mutations:
            with self.subTest(data=data):
                with self.assertRaises(ValidationError):
                    h.records(case['notes'], asked, context, units, h.HistorySelections.model_validate(data))
        for value in (True, '1', -1):
            data = copy.deepcopy(original); data['history_context'][0]['units'][0]['unit_id'] = value
            with self.assertRaises((ValueError, ValidationError)):
                h.records(case['notes'], asked, context, units, h.HistorySelections.model_validate(data))

    def test_existing_hardguards_veto_forged_context_only_and_actor_shortcuts(self):
        fs = [field('chief', 'Chief complaint'), field('hpi', 'History of present illness', 'long_text')]
        first = 'Patient presents with a cough.'
        probes = [
            ('The following symptoms are denied:\n' + first, first),
            (first + ' Correction: this history belongs to another patient.', first),
            ('Family history:\n' + first, first),
            ('The patient advocate presents with a cough. Plan: rest.', 'The patient advocate presents with a cough.'),
        ]
        for relation in ('his father', 'a caregiver', 'a patient advocate', 'a doctor'):
            probes.append(('Patient presents with ' + relation + '. He reports low-grade fevers.', 'He reports low-grade fevers.'))
        for notes, quote in probes:
            with self.subTest(notes=notes):
                out = offered(notes, fs, {'Chief complaint': [quote]})['Chief complaint']
                self.assertEqual((out['status'], out['text']), ('conflict', ''))
                forged = {**out, 'status': 'supported', 'text': quote, 'reviewed': True}
                self.assertEqual(g.governed_decisions(notes, fs, {'chief': forged}), ['Chief complaint'])

    def test_required_qualifier_contrary_and_unknown_context_cannot_be_omitted(self):
        fs = [field('chief', 'Chief complaint')]
        first, tail = 'Patient presents with a cough.', 'The cough resolved yesterday.'
        notes = first + ' ' + tail
        for relation in ('required_qualifier', 'contrary', 'unresolved'):
            answer = offered(notes, fs, {'Chief complaint': [first]}, {tail: relation})['Chief complaint']
            self.assertEqual(answer['status'], 'conflict')
            forged = {**answer, 'status': 'supported', 'text': first, 'reviewed': True}
            self.assertEqual(g.governed_decisions(notes, fs, {'chief': forged}), ['Chief complaint'])

    def test_clinically_related_assessment_does_not_release_allergy_medication_or_smoker(self):
        case = cases()[2]
        for assessment in ('penicillin anaphylaxis.', 'penicillin hypersensitivity.',
                           'daily cigarette smoking.', 'ibuprofen cessation.'):
            notes = case['notes'].replace('tension-type headache.', assessment)
            picks = copy.deepcopy(case['original_all_picks'])
            picks['Assessment'] = ['Assessment is ' + assessment]
            out = offered(notes, case['fields'], picks)
            for label in ('Allergies', 'Medications', 'Smoker'):
                self.assertEqual((out[label]['status'], out[label]['text']), ('conflict', ''), (assessment, label))

    def test_identical_occurrences_keep_order_and_separate_evidence(self):
        fs = [field('hpi', 'History of present illness')]
        quote = 'Patient presents with a cough.'
        notes = quote + ' ' + quote
        units = g.source_units(notes, fs)[0]
        selected = h.HistorySelections(fields=[g.UnitSelection(key='hpi', unit_ids=[2, 1], conflict=False)],
            history_context=[h.HistoryRelation(key='hpi', units=[h.UnitRelation(unit_id=i, relation='answer') for i in (1, 2)])])
        records = h.records(notes, fs, [], units, selected)
        answer = g.validate_selections(notes, fs, selected, evidence_contract=g.TAB_CONTRACT, history_records=records)['hpi']
        self.assertEqual((answer['status'], answer['text']), ('supported', quote + '\n' + quote))
        self.assertEqual([e['start'] for e in answer['evidence']], [0, len(quote) + 1])
        self.assertEqual(g.governed_decisions(notes, fs, {'hpi': answer}), [])

    def test_stored_relation_is_invalid_after_notes_mapping_text_evidence_or_flag_change(self):
        case = cases()[0]; label = 'Chief complaint'
        answer = offered(case['notes'], case['fields'], case['original_all_picks'])[label]
        f = next(f for f in case['fields'] if f['label'] == label)
        variants = []
        changed = copy.deepcopy(answer); changed['text'] += ' altered'; variants.append((case['notes'], case['fields'], changed))
        changed = copy.deepcopy(answer); changed['evidence'][0]['end'] -= 1; variants.append((case['notes'], case['fields'], changed))
        changed = copy.deepcopy(answer); changed['history_context'] += 'tampered'; variants.append((case['notes'], case['fields'], changed))
        changed_fields = copy.deepcopy(case['fields']); changed_fields[0]['context'] = 'Donor only'; variants.append((case['notes'], changed_fields, answer))
        variants.append((case['notes'] + ' New source statement.', case['fields'], answer))
        for notes, fields, value in variants:
            with self.subTest(notes=notes, fields=fields):
                self.assertIn(label, g.governed_decisions(notes, fields, {f['key']: value}))
        with override_settings(V3_HISTORY_CONTEXT=False):
            self.assertIn(label, g.governed_decisions(case['notes'], case['fields'], {f['key']: answer}))
        legacy = {key: value for key, value in answer.items() if key != 'history_context'}
        self.assertIn(label, g.governed_decisions(case['notes'], case['fields'], {f['key']: legacy}))

    def test_same_role_aliases_scoped_fields_and_source_capacity_get_no_new_contract(self):
        unit = [{'id': 1, 'quote': 'Patient presents with a cough.', 'start': 0, 'end': 29}]
        self.assertEqual(h.targets([field('a', 'HPI'), field('b', 'History of present illness')], unit), {})
        scoped = field('a', 'Chief complaint'); scoped['context'] = 'Left knee'
        self.assertEqual(h.targets([scoped], unit), {})
        self.assertEqual(h.targets([field('a', 'Chief complaint')], unit * 65), {})
        ordinary = field('a', 'Chief complaint'); ordinary['context'] = 'Chief complaint'
        self.assertEqual(set(h.targets([ordinary], unit)), {'a'})

    @override_settings(**LIVE)
    def test_request_and_reservation_are_versioned_bounded_and_disable_before_sending(self):
        case = cases()[0]
        flagged = g.configuration()
        with override_settings(V3_HISTORY_CONTEXT=False):
            old = g.configuration()
        self.assertNotIn('history_context_contract', old)
        self.assertEqual(flagged['history_context_contract'], h.CONTRACT)
        self.assertEqual({k: v for k, v in flagged.items() if k != 'history_context_contract'}, old)
        captured = {}
        def response(**kw):
            captured.update(kw)
            payload = json.loads(kw['messages'][0]['content'])
            reply = unit_response(payload, case['original_all_picks'])
            reply.content[0].text = json.dumps(body(case['notes'], case['fields'], case['original_all_picks']))
            return reply
        with patch('anthropic.Anthropic') as provider:
            provider.return_value.messages.create.side_effect = response
            result = g.generate(case['notes'], case['fields'], flagged)
        self.assertEqual(captured['model'], 'claude-sonnet-5')
        self.assertEqual(captured['max_tokens'], flagged['request_profile']['max_output_tokens'])
        self.assertEqual(result[0]['history_context_contract'], h.CONTRACT)
        bound = g.maximum_cost(case['notes'], case['fields'], flagged)
        self.assertGreater(bound, g.maximum_cost(case['notes'], case['fields'], old))
        unrelated = [field('a', 'Activities')]
        self.assertEqual(g.maximum_cost(case['notes'], unrelated, flagged), g.maximum_cost(case['notes'], unrelated, old))
        # The separate schema and instructions are actually included in the bound;
        # no additional provider request or larger output reservation is hidden.
        sent = len(json.dumps(captured).encode())
        from decimal import Decimal
        priced = Decimal(sent) * Decimal(flagged['input_rate']) / 1000000
        priced += Decimal(captured['max_tokens']) * Decimal(flagged['output_rate']) / 1000000
        self.assertGreaterEqual(bound, priced)
        with override_settings(V3_HISTORY_CONTEXT=False), patch('anthropic.Anthropic') as provider:
            from core.jobs import NoProviderRequest
            with self.assertRaises(NoProviderRequest): g.generate(case['notes'], case['fields'], flagged)
            provider.assert_not_called()
        with override_settings(AI_MODEL='claude-sonnet-4-6'), patch('anthropic.Anthropic') as provider:
            legacy = g.configuration()
            with self.assertRaisesMessage(ValidationError, 'exact native claude-sonnet-5'):
                g.maximum_cost(case['notes'], case['fields'], legacy)
            with self.assertRaisesMessage(NoProviderRequest, 'exact native claude-sonnet-5'):
                g.generate(case['notes'], case['fields'], legacy)
            provider.assert_not_called()


@override_settings(**dict(LIVE, V3_HISTORY_CONTEXT=True))
class HistoryContextWorkflow(V3Fixture, TestCase):
    def setUp(self):
        super().setUp()
        deny = patch('socket.socket.connect', side_effect=AssertionError('Network denied'))
        deny.start(); self.addCleanup(deny.stop)

    def test_original_consent_destination_still_requires_explicit_partial_coverage_review(self):
        case = cases()[0]
        path = Path(self.directory.name) / (case['name'] + '.docx')
        template, version = self.uploaded(data=ordinary_input_form(path, [f['label'] for f in case['fields']]),
                                          name=case['name'])
        assert_unreviewed_consent_refused(self, template, version, 'b/tbl[0]/tr[8]/tc[1]')

    def test_three_original_notes_worker_review_no_history_edit_finalize_download(self):
        for case in cases():
            with self.subTest(case=case['name']):
                path = Path(self.directory.name) / (case['name'] + '.docx')
                source = ordinary_input_form(path, [f['label'] for f in case['fields']])
                template, version = self.uploaded(data=source, name=case['name'])
                version = review_protected_consent(self, template, version, 'b/tbl[0]/tr[8]/tc[1]')
                self.confirm(template, version)
                self.new_encounter(version, notes=case['notes'])
                encounter = Encounter.objects.latest('created_at')
                def response(**kw):
                    payload = json.loads(kw['messages'][0]['content'])
                    if (capture := os.environ.get('QUILLMD_HISTORY_ARTIFACTS')):
                        folder = Path(capture); folder.mkdir(parents=True, exist_ok=True)
                        (folder / (case['name'] + '-request.json')).write_text(json.dumps(payload, indent=2))
                    self.assertEqual(len(payload['history_context_targets']), 2)
                    reply = unit_response(payload, case['original_all_picks'], request_id='history-' + case['name'])
                    reply.model = 'claude-sonnet-5'
                    reply.content[0].text = json.dumps(body(case['notes'], version.fields, case['original_all_picks']))
                    return reply
                with patch('anthropic.Anthropic') as provider:
                    provider.return_value.messages.create.side_effect = response
                    job = enqueue(encounter, self.user); self.assertTrue(run_one())
                    self.assertEqual(provider.return_value.messages.create.call_count, 1)
                job.refresh_from_db(); self.assertEqual(job.state, 'succeeded', job.error)
                self.assertEqual(job.config['history_context_contract'], h.CONTRACT)
                encounter.refresh_from_db(); original = copy.deepcopy(encounter.answers)
                consent = next(f for f in version.fields if f['label'] == 'Consent obtained')
                self.assertFalse(original[consent['key']]['text'])
                page = self.client.get(f'/encounters/{encounter.pk}/')
                rows = {row['label']: row for row in page.context['answer_rows']}
                payload = {'revision': encounter.revision}
                assisted = []
                for f in version.fields:
                    answer = encounter.answers[f['key']]
                    value = answer['text']
                    if answer['status'] == 'conflict':
                        assisted.append(f['label'])
                        value = '\n'.join(case['original_all_picks'][f['label']])
                        if f['label'] == 'Smoker': value = 'No'
                        # These are explicit clinician corrections. The mixed
                        # source clause remains an unresolved automatic oracle;
                        # do not copy the entire mixed sentence into both fields.
                        if case['name'] == 'r1-note1':
                            value = {'Past medical history': 'Hypertension.',
                                     'Medications': 'Lisinopril 10 mg daily.'}.get(f['label'], value)
                        payload['held_shown_' + f['key']] = '1'
                    payload['answer_' + f['key']] = value
                    payload['reviewed_' + f['key']] = 'on'
                for label in ('Chief complaint', 'History of present illness'):
                    expected = 'conflict' if case['name'] == 'r1-note2' and label == 'History of present illness' else 'supported'
                    self.assertEqual(rows[label]['status'], expected)
                self.assertEqual(self.client.post(f'/encounters/{encounter.pk}/save/', payload).status_code, 302)
                encounter.refresh_from_db()
                for f in version.fields:
                    if g.question_key(f['label']) in h.ROLES and f['label'] not in assisted:
                        self.assertEqual(encounter.answers[f['key']]['text'], original[f['key']]['text'])
                        self.assertEqual(encounter.answers[f['key']]['status'], 'supported')
                self.client.post(f'/encounters/{encounter.pk}/finalize/', {'revision': encounter.revision, 'reviewed': 'on'})
                encounter.refresh_from_db(); self.assertEqual(encounter.status, 'finalized')
                download = self.client.get(f'/encounters/{encounter.pk}/export/')
                self.assertEqual(download.status_code, 200)
                exported = b''.join(download.streaming_content)
                self.assertEqual(hashlib.sha256(exported).hexdigest(), encounter.export_sha256)
                self.assertEqual(private_path(template.original_path).read_bytes(), source)
                slots = w.SlotIndex(w.open_package(exported))
                consent_slot = consent['locator']['part'] + '#' + consent['locator']['slot']
                source_slots = w.SlotIndex(w.open_package(source))
                from lxml import etree
                self.assertEqual(etree.tostring(slots.by_id[consent_slot].el),
                                 etree.tostring(source_slots.by_id[consent_slot].el))
                for target in case['targets']:
                    for quote in target['original_selection']: self.assertIn(quote, part_text(exported))
                    f = next(f for f in version.fields if f['label'] == target['field'])
                    slot = slots.by_id[f['locator']['part'] + '#' + f['locator']['slot']]
                    self.assertEqual(w.text_of(slot.el).strip(), '\n'.join(target['original_selection']))
                if (capture := os.environ.get('QUILLMD_HISTORY_ARTIFACTS')):
                    folder = Path(capture) / case['name']; folder.mkdir(parents=True, exist_ok=False)
                    (folder / 'original.docx').write_bytes(source)
                    (folder / 'exported.docx').write_bytes(exported)
                    (folder / 'draft.html').write_bytes(page.content)
                    (folder / 'result.json').write_text(json.dumps({'notes': case['notes'], 'simulated_provider': True,
                        'automatic': original, 'assisted_labels': assisted, 'final': encounter.answers,
                        'coverage_review': version.corrections['coverage_review'],
                        'automatic_complete': version.import_manifest['coverage']['automatic_complete'],
                        'export_sha256': encounter.export_sha256}, indent=2))

    def test_forced_supported_context_cases_stay_held_on_page_unchanged_save_and_finalize(self):
        path = Path(self.directory.name) / 'stored-history.docx'
        template, version = self.uploaded(data=ordinary_input_form(path, ['Chief complaint']), name='stored-history')
        self.confirm(template, version)
        f = version.fields[0]
        quote, tail = 'Patient presents with a cough.', 'The cough resolved yesterday.'
        probes = [
            ('The following symptoms are denied:\n' + quote, quote, {}),
            (quote + ' Correction: this belongs to another patient.', quote, {}),
            ('Patient presents with his father. He reports low-grade fevers.', 'He reports low-grade fevers.', {}),
            (quote + ' ' + tail, quote, {tail: 'required_qualifier'}),
            (quote + ' ' + tail, quote, {tail: 'contrary'}),
            (quote + ' ' + tail, quote, {tail: 'unresolved'}),
        ]
        for notes, picked, overrides in probes:
            with self.subTest(notes=notes, overrides=overrides):
                answer = offered(notes, version.fields, {'Chief complaint': [picked]}, overrides)['Chief complaint']
                self.assertEqual(answer['status'], 'conflict')
                self.new_encounter(version, notes=notes)
                e = Encounter.objects.latest('created_at')
                e.answers = {f['key']: {**answer, 'status': 'supported', 'text': picked, 'reviewed': True,
                                        'reviewed_by': str(self.user.pk)}}
                e.save()
                page = self.client.get(f'/encounters/{e.pk}/')
                self.assertContains(page, 'data-held-candidate')
                self.client.post(f'/encounters/{e.pk}/finalize/', {'revision': e.revision, 'reviewed': 'on'})
                e.refresh_from_db(); self.assertNotEqual(e.status, 'finalized')
                # A stale prefilled page and a review tick are not a new decision.
                self.client.post(f'/encounters/{e.pk}/save/', {'revision': e.revision,
                    'answer_' + f['key']: picked, 'reviewed_' + f['key']: 'on'})
                e.refresh_from_db()
                self.client.post(f'/encounters/{e.pk}/finalize/', {'revision': e.revision, 'reviewed': 'on'})
                e.refresh_from_db(); self.assertNotEqual(e.status, 'finalized')
                self.assertFalse(e.export_path)
