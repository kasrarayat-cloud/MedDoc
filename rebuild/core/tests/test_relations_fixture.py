"""Deterministic labelled fixture correctness, never Sonnet qualification."""
import json
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase, override_settings

from core import generation as g, generation_batch as b, batch_jobs, relations_fixture as fixture
from core.jobs import run_one
from core.models import Encounter, GenerationBatch, Job, ProviderReceipt, Usage
from .test_v3_supersession_floor import SONNET_55_DEFAULT, form
from .test_generation_batch import manifest, sample
from .test_word_v3_workflow import V3, V3Fixture, build_questionnaire, part_text

SETTINGS = {**V3, **SONNET_55_DEFAULT, 'AI_MODE': 'fixture', 'V3_GENERATION_BATCHES': True}


@override_settings(**SETTINGS)
class LabelledRelationsFixture(SimpleTestCase):
    def test_single_fixture_accepts_exact_labels_and_has_explicit_simulated_identity(self):
        fields = form('Symptoms', 'Allergies')
        notes = 'Symptoms: cough.\n\nAllergies: penicillin.'
        with patch('socket.socket.connect', side_effect=AssertionError('Network denied')):
            answers, cost, units, rates, provider, request, simulated = g.generate(notes, fields)
        self.assertEqual([answers[f['key']]['text'] for f in fields], ['cough.', 'penicillin.'])
        self.assertEqual([answers[f['key']]['status'] for f in fields], ['supported', 'supported'])
        self.assertEqual((str(cost), units, rates, provider, request, simulated),
            ('0', {}, {}, 'synthetic-labelled-relations-fixture', '', True))
        self.assertEqual(g.governed_decisions(notes, fields, answers), [])

    def test_unlabelled_or_ambiguous_context_is_not_invented_as_independent(self):
        fields = form('Symptoms', 'Allergies')
        notes = 'Symptoms: cough.\n\nIt was not the patient.'
        wire = fixture.body(notes, fields, fields, [])
        self.assertTrue(all(row['context']['unresolved'] for row in wire['fields']))
        answers = g.generate(notes, fields)[0]
        self.assertEqual((answers['f1']['status'], answers['f1']['text']), ('conflict', ''))
        repeated = form('Symptoms', 'Symptoms')
        answers = g.generate('Symptoms: cough.', repeated)[0]
        self.assertTrue(all(a['status'] != 'supported' for a in answers.values()))

    def test_partition_and_option_ids_use_the_requested_part_schema(self):
        fields = form('Symptoms', 'Smoker')
        fields[1].update(kind='choice', options=['Yes', 'No'])
        notes = 'Symptoms: cough.\n\nSmoker: No.'
        first = fixture.body(notes, fields, fields, [], requested_ids=['f1'])
        self.assertNotIn('option_ids', first['fields'][0])
        whole = fixture.body(notes, fields, fields, [])
        self.assertEqual(whole['fields'][0]['option_ids'], [])
        self.assertEqual(whole['fields'][1]['option_ids'], ['f2:1'])
        answers = g.generate(notes, fields)[0]
        self.assertEqual((answers['f2']['status'], answers['f2']['text']), ('supported', 'No'))

    def test_over_100_labelled_fields_use_valid_v4_parts_and_complete_source(self):
        encounter = sample(101)
        plan = b.plan_for(encounter, g.configuration(encounter.template_version.fields))
        responses = [batch_jobs.fixture_response(plan, SimpleNamespace(pk=i, field_ids=p['field_ids']))
                     for i, p in enumerate(plan['parts'], 1)]
        self.assertGreater(len(responses), 1)
        answers, _ = b.assemble(plan, responses)
        self.assertEqual(len(answers), 101)
        self.assertTrue(all(a['status'] == 'supported' for a in answers.values()))
        for response in responses:
            self.assertEqual(response['synthetic_source'], 'deterministic-batch-fixture')
            self.assertTrue(all('context' in row for row in json.loads(response['content'][0]['text'])['fields']))


@override_settings(**SETTINGS)
class LargeFixtureWorkflow(V3Fixture, TestCase):
    def test_browser_worker_to_genuine_export_keeps_101_fixture_answers_and_zero_cost(self):
        deny = patch('socket.socket.connect', side_effect=AssertionError('Network denied'))
        deny.start(); self.addCleanup(deny.stop)
        template, first = self.uploaded(data=build_questionnaire(101), name='Synthetic v4 fixture 101')
        # Independently authored questionnaire has no cross-question rules;
        # this is a simulated fixture declaration, never a live qualification.
        from core.models import TemplateVersion
        version = TemplateVersion.objects.create(template=template, number=2, contract='v3', fields=first.fields,
            document_backend=first.document_backend,
            generation_constraints=manifest(first.fields, template.sha256, synthetic=True), created_by=self.user)
        self.confirm(template, version)
        notes = '\n\n'.join(f"{f['label']}: documented {i:03d}." for i, f in enumerate(version.fields))
        self.new_encounter(version, notes)
        encounter = Encounter.objects.latest('created_at')
        page = self.client.get(f'/encounters/{encounter.pk}/')
        self.assertIsNotNone(page.context['generation_max_charge'], page.context['generation_quote_error'])
        response = self.client.post(f'/encounters/{encounter.pk}/generate/',
            {'revision': encounter.revision, 'usage_quote': page.context['usage_quote']})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(GenerationBatch.objects.filter(encounter=encounter).exists(),
            [str(m) for m in self.client.get(f'/encounters/{encounter.pk}/').context['messages']])
        batch = GenerationBatch.objects.get(encounter=encounter)
        for _ in range(10):
            if not run_one(): break
        batch.refresh_from_db(); encounter.refresh_from_db()
        self.assertEqual(batch.state, 'succeeded', batch.error)
        self.assertEqual(len(encounter.answers), 101)
        self.assertTrue(all(a['status'] == 'supported' for a in encounter.answers.values()))
        usage = Usage.objects.filter(job__generation_part__batch=batch)
        self.assertEqual(usage.count(), batch.parts.count())
        self.assertTrue(all(u.simulated and u.actual_cost == 0 for u in usage))
        self.assertEqual(ProviderReceipt.objects.filter(job__generation_part__batch=batch).count(), batch.parts.count())
        payload = {'revision': encounter.revision}
        for field in version.fields:
            payload['answer_'+field['key']] = encounter.answers[field['key']]['text']
            payload['reviewed_'+field['key']] = 'on'
        self.assertEqual(self.client.post(f'/encounters/{encounter.pk}/save/', payload).status_code, 302)
        encounter.refresh_from_db()
        response = self.client.post(f'/encounters/{encounter.pk}/finalize/', {'revision': encounter.revision, 'reviewed': 'on'})
        self.assertEqual(response.status_code, 302)
        encounter.refresh_from_db(); self.assertEqual(encounter.status, 'finalized')
        response = self.client.get(f'/encounters/{encounter.pk}/export/')
        self.assertEqual(response.status_code, 200)
        text = part_text(b''.join(response.streaming_content))
        for i in range(101): self.assertIn(f'documented {i:03d}.', text)
        self.assertEqual(Job.objects.filter(encounter=encounter, state='failed').count(), 0)
