"""Complete ordinary relations share the existing immutable batch ledger."""
import copy
import json
from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase, override_settings

from core import generation as g, generation_batch as b, batch_jobs as jobs
from core.models import Reservation, Usage
from .test_generation_batch import SETTINGS, BatchFixture, manifest, sample
from .test_v3_field_relations import answer_of, relation_wire, set_relation
from .test_v3_field_relations_workflow import sdk_response

ORDINARY = dict(SETTINGS, V3_FIELD_RELATIONS=True)
NOTE = 'The patient reports persistent aching discomfort.'


def reply(plan, ordinal, *, picks=None):
    ids = plan['parts'][ordinal - 1]['field_ids']
    body = relation_wire(plan['notes'], plan['fields'], picks or {plan['asked'][0]['key']: [NOTE]}, keys=set(ids))
    return {'model': g.SONNET_5, 'stop_reason': 'end_turn',
            'content': [{'type': 'text', 'text': json.dumps(body)}]}


@override_settings(**ORDINARY)
class OrdinaryBatchContract(SimpleTestCase):
    def test_bounded_children_keep_whole_source_catalogue_constraints_and_exact_price(self):
        encounter = sample(notes=NOTE); config = g.configuration(); plan = b.plan_for(encounter, config)
        self.assertGreater(len(plan['parts']), 1)
        self.assertLessEqual(max(len(p['field_ids']) for p in plan['parts']), 100)
        selected = []
        for ordinal, part in enumerate(plan['parts'], 1):
            wire = b.request(plan, ordinal); payload = json.loads(wire['messages'][0]['content'])
            self.assertEqual(payload['catalogue'], plan['fields'])
            self.assertEqual(payload['source_units'], plan['units'])
            self.assertEqual(payload['form_constraints'], plan['constraints'])
            self.assertEqual(payload['requested_field_ids'], part['field_ids'])
            self.assertEqual(part['input_token_bound'], len(json.dumps(wire).encode()) + 12000)
            self.assertEqual(part['request_sha256'], b.digest(wire))
            rate = g.rates(config)
            cost = (Decimal(part['input_token_bound']) * rate['input_per_million'] +
                    Decimal(wire['max_tokens']) * rate['output_per_million']) / 1000000
            self.assertGreaterEqual(Decimal(part['maximum_cost']), cost)
            selected.extend(part['field_ids'])
        self.assertEqual(selected, [f['key'] for f in plan['asked']])
        self.assertEqual(Decimal(plan['maximum_charge']), sum(Decimal(p['maximum_charge']) for p in plan['parts']))
        stored = json.loads(json.dumps(plan, sort_keys=True))
        self.assertEqual(b.request(stored, 1), b.request(plan, 1))
        answers, _ = b.assemble(plan, [reply(plan, n) for n in range(1, len(plan['parts']) + 1)])
        self.assertEqual((answers['q000']['status'], answers['q000']['text']), ('supported', NOTE))
        self.assertEqual(g.governed_decisions(NOTE, plan['fields'], answers), [])
        self.assertTrue(all(a['status'] == 'missing' for k, a in answers.items() if k != 'q000'))

    def test_response_capacity_can_require_batch_below_100_and_never_splits_physical_group(self):
        # (60 units: the v4 partition holds about 32 fields per bounded response, so 50 fields need two parts)
        note = ' '.join('The patient reports symptom ' + str(i) + '.' for i in range(60))
        encounter = sample(50, notes=note); config = g.configuration()
        self.assertTrue(b.needed(encounter.template_version.fields, note, config))
        plan = b.plan_for(encounter, config)
        self.assertGreater(len(plan['parts']), 1)
        for f in encounter.template_version.fields: f['locator']['slot'] = 'b/tbl[0]/tr[0]/tc[1]/p[0]'
        encounter.template_version.generation_constraints = manifest(encounter.template_version.fields)
        with self.assertRaisesMessage(ValidationError, 'indivisible'):
            b.plan_for(encounter, config)
        # (a 101-field form over a 300-sentence note needs more than eight bounded v4 responses)
        long_note = ' '.join('The patient reports finding ' + str(i) + '.' for i in range(300))
        with self.assertRaisesMessage(ValidationError, 'eight'):
            b.plan_for(sample(101, notes=long_note), config)

    def test_cross_child_competing_source_and_changed_request_are_held(self):
        encounter = sample(notes=NOTE); fields = encounter.template_version.fields
        fields[0]['label'] = fields[-1]['label'] = 'Other:'
        fields[0]['context'] = 'Headache sensation'; fields[-1]['context'] = 'Headache prodrome'
        encounter.template_version.generation_constraints = manifest(fields)
        plan = b.plan_for(encounter, g.configuration())
        picks = {fields[0]['key']: [NOTE], fields[-1]['key']: [NOTE]}
        answers, _ = b.assemble(plan, [reply(plan, n, picks=picks) for n in range(1, len(plan['parts']) + 1)])
        self.assertEqual(answers[fields[0]['key']]['status'], 'conflict')
        self.assertEqual(answers[fields[-1]['key']]['status'], 'conflict')
        changed = copy.deepcopy(plan); changed['units'][0]['quote'] = 'The patient is well.'
        with self.assertRaisesMessage(ValidationError, 'differs'): b.request(changed, 1)
        raw = reply(plan, 1); body = json.loads(raw['content'][0]['text'])
        context = body['fields'][0]['context']                           # (a context one unit short)
        next(ids for ids in context.values() if ids).pop(0)
        raw['content'][0]['text'] = json.dumps(body)
        with self.assertRaises(ValidationError):
            b.assemble(plan, [raw] + [reply(plan, n) for n in range(2, len(plan['parts']) + 1)])
        # (the v1 list shape, v2's keyed shape, v3's entry list, and an answer for another part's fields, are refused too)
        v1 = reply(plan, 1); wire_body = json.loads(v1['content'][0]['text'])
        relation_of = [{unit: name for name, ids in item['context'].items() for unit in ids} for item in wire_body['fields']]
        units = [u['id'] for u in plan['units']]
        v1['content'][0]['text'] = json.dumps({'fields': [{**item, 'option_ids': [],
            'context': [relation_of[n][u] for u in units]} for n, item in enumerate(wire_body['fields'])]})
        v2 = reply(plan, 1)
        v2['content'][0]['text'] = json.dumps({'fields': {item['key']: {
            **{k: v for k, v in item.items() if k not in ('key', 'context')},
            'context': {str(u): relation_of[n][u] for u in units}} for n, item in enumerate(wire_body['fields'])}})
        v3 = reply(plan, 1)
        v3['content'][0]['text'] = json.dumps({'fields': [{**item, 'context': [
            {'unit': u, 'relation': relation_of[n][u]} for u in units]} for n, item in enumerate(wire_body['fields'])]})
        foreign = reply(plan, 2)
        for raw in (v1, v2, v3, foreign):
            with self.assertRaises(ValidationError):
                b.assemble(plan, [raw] + [reply(plan, n) for n in range(2, len(plan['parts']) + 1)])


    def test_a_part_whose_answer_disagrees_with_its_selection_holds_that_field_only(self):
        # The batch path assembles through the same records()/read() as the single request: a disagreement is that
        # field's conflict (live attempt 020's shape, and an answer relation on a unit the field did not select), the
        # complete form is still assembled once, and every other field reads as it does without the disagreement.
        encounter = sample(notes=NOTE); plan = b.plan_for(encounter, g.configuration())
        self.assertGreater(len(plan['parts']), 1)
        first, later = plan['asked'][0]['key'], plan['parts'][1]['field_ids'][0]
        clean, _ = b.assemble(plan, [reply(plan, n) for n in range(1, len(plan['parts']) + 1)])
        self.assertEqual((clean[first]['status'], clean[first]['text']), ('supported', NOTE))

        def edited(ordinal, key, edit):
            raw = reply(plan, ordinal); body = json.loads(raw['content'][0]['text'])
            edit(answer_of(body, key)); raw['content'][0]['text'] = json.dumps(body)
            return raw
        for name, ordinal, key, edit in (
                ('the selected unit marked contrary, conflict true', 1, first,
                 lambda f: (set_relation(f, 1, 'contrary'), f.update(conflict=True))),
                ('the selected unit marked independent', 1, first, lambda f: set_relation(f, 1, 'independent')),
                ('an answer relation and nothing selected, in another part', 2, later,
                 lambda f: set_relation(f, 1, 'answer'))):
            with self.subTest(name=name):
                responses = [edited(n, key, edit) if n == ordinal else reply(plan, n)
                             for n in range(1, len(plan['parts']) + 1)]
                answers, _ = b.assemble(plan, responses)
                self.assertEqual((answers[key]['status'], answers[key]['text']), ('conflict', ''))
                self.assertEqual({k: (v['status'], v['text']) for k, v in answers.items() if k != key},
                                 {k: (v['status'], v['text']) for k, v in clean.items() if k != key})

    def test_a_competing_question_in_another_part_that_claims_the_statement_holds_the_one_that_selected_it(self):
        # (refutation of dfde4fc8, F1, on the batch path: the later part's repeated 'Other:' calls the one statement its
        # answer and selects nothing; the first part's 'Other:' selected it. Both are held, as when both select it.)
        encounter = sample(notes=NOTE); fields = encounter.template_version.fields
        fields[0]['label'] = fields[-1]['label'] = 'Other:'
        fields[0]['context'] = 'Headache sensation'; fields[-1]['context'] = 'Headache prodrome'
        encounter.template_version.generation_constraints = manifest(fields)
        plan = b.plan_for(encounter, g.configuration())
        first, last = fields[0]['key'], fields[-1]['key']
        part_of = {k: n for n, p in enumerate(plan['parts'], 1) for k in p['field_ids']}
        self.assertNotEqual(part_of[first], part_of[last])

        def responses(edit):
            out = []
            for n in range(1, len(plan['parts']) + 1):
                raw = reply(plan, n)
                if n == part_of[last]:
                    body = json.loads(raw['content'][0]['text']); edit(answer_of(body, last))
                    raw['content'][0]['text'] = json.dumps(body)
                out.append(raw)
            return out
        clean, _ = b.assemble(plan, responses(lambda f: None))
        self.assertEqual((clean[first]['status'], clean[first]['text']), ('supported', NOTE))
        for name, edit in (('an answer relation, nothing selected', lambda f: set_relation(f, 1, 'answer')),
                           ('a qualifier relation, nothing selected', lambda f: set_relation(f, 1, 'qualifier')),
                           ('the consistent selection', lambda f: (set_relation(f, 1, 'answer'),
                                                                   f.update(unit_ids=[1])))):
            with self.subTest(name=name):
                answers, _ = b.assemble(plan, responses(edit))
                self.assertEqual({k: (answers[k]['status'], answers[k]['text']) for k in (first, last)},
                                 {first: ('conflict', ''), last: ('conflict', '')})
                self.assertEqual({k: (v['status'], v['text']) for k, v in answers.items() if k not in (first, last)},
                                 {k: (v['status'], v['text']) for k, v in clean.items() if k not in (first, last)})
        answers, _ = b.assemble(plan, responses(lambda f: set_relation(f, 1, 'contrary')))
        self.assertEqual((answers[first]['status'], answers[first]['text']), ('supported', NOTE))   # (not a claim)


@override_settings(**ORDINARY)
class OrdinaryBatchWorkflow(BatchFixture, TestCase):
    def setUp(self):
        super().setUp()
        self.encounter.notes = NOTE
        self.encounter.save(update_fields=['notes'])

    def fake_ordinary(self, batch, fail_at=None):
        calls = []
        def call(**wire):
            calls.append(wire)
            self.assertEqual(wire, b.request(batch.plan, len(calls)))
            if len(calls) == fail_at: raise TimeoutError('Synthetic unknown ordinary response')
            body = json.loads(reply(batch.plan, len(calls))['content'][0]['text'])
            response = sdk_response(body)
            response.id = 'msg_ordinary_' + str(len(calls))
            response._request_id = 'ordinary_request_' + str(len(calls))
            response.model_dump = lambda **_: {**reply(batch.plan, len(calls)), 'id': 'msg_ordinary_' + str(len(calls)),
                'usage': {'input_tokens': 100, 'output_tokens': 100, 'cache_read_input_tokens': 0, 'cache_creation_input_tokens': 0}}
            return response
        return calls, call

    def test_all_actual_request_holds_precede_send_then_complete_union_adopts_once(self):
        batch = self.admit(); calls, call = self.fake_ordinary(batch)
        holds = Reservation.objects.filter(job__generation_part__batch=batch, state='held')
        self.assertEqual(sum(holds.values_list('amount', flat=True), Decimal(0)), batch.maximum_charge)
        with patch('anthropic.Anthropic') as provider:
            provider.return_value.messages.create.side_effect = call
            for _ in batch.plan['parts']:
                self.assertTrue(jobs.run_one())
                self.encounter.refresh_from_db(); self.assertEqual(self.encounter.answers, {})
            batch.refresh_from_db()
            self.assertTrue(jobs.run_one(), {'state': batch.state, 'error': batch.error,
                'jobs': list(batch.parts.values_list('ordinal', 'job__state', 'job__error'))})
            self.assertFalse(jobs.run_one())
        batch.refresh_from_db(); self.assertEqual(batch.state, 'succeeded', batch.error)
        self.encounter.refresh_from_db()
        first = self.version.fields[0]['key']
        self.assertEqual((self.encounter.answers[first]['status'], self.encounter.answers[first]['text']), ('supported', NOTE))
        self.assertEqual(Usage.objects.filter(job__generation_part__batch=batch).count(), len(calls))
        self.assertFalse(Reservation.objects.filter(job__generation_part__batch=batch, state='held').exists())
        from core.management.commands.audit_billing import audit_report
        report = audit_report(); self.assertTrue(report['all_checks_pass'], report)

    def test_unknown_second_response_remains_held_and_never_retried(self):
        batch = self.admit(); calls, call = self.fake_ordinary(batch, fail_at=2)
        with patch('anthropic.Anthropic') as provider:
            provider.return_value.messages.create.side_effect = call
            self.assertTrue(jobs.run_one()); self.assertTrue(jobs.run_one())
            self.assertFalse(jobs.run_one()); self.assertFalse(jobs.run_one())
        self.assertEqual(len(calls), 2)
        batch.refresh_from_db(); self.assertEqual(batch.state, 'reconciliation')
        self.encounter.refresh_from_db(); self.assertEqual(self.encounter.answers, {})
        self.assertTrue(Reservation.objects.filter(job__generation_part__batch=batch,
            job__generation_part__ordinal=2, state='held').exists())

    def test_flag_withdrawal_and_cancel_never_send_an_extra_request(self):
        batch = self.admit(); calls, call = self.fake_ordinary(batch)
        with patch('anthropic.Anthropic') as provider:
            provider.return_value.messages.create.side_effect = call
            self.assertTrue(jobs.run_one())
            with override_settings(V3_FIELD_RELATIONS=False): self.assertTrue(jobs.run_one())
            self.assertEqual(len(calls), 1)
        batch.refresh_from_db(); self.assertEqual(batch.state, 'failed')
        self.assertFalse(Reservation.objects.filter(job__generation_part__batch=batch, state='held').exists())
        self.encounter.refresh_from_db(); self.assertEqual(self.encounter.answers, {})
