"""The customer queue and the re-check of what is still open (session decisions (n) and (o), 2026-11-04).

(n) The installed page offered the bounded second review ("Ask the provider once more"); the new customer page keeps
    it, worded by function: ``recheck`` {available, can_request} beside ``unresolved``, ``available`` by the predicate
    POST second-review accepts an ask by, ``can_request`` only for owners and reviewers. Asking queues the one stage
    and the offer is gone; nothing is sent by the offer itself.
(o) The queue lists what its badge counts: each list row carries ``in_queue`` (customer_api.in_queue) and the session
    counts exactly those rows - the three customer states that wait on the member and what the review queue's rule
    (serializers.queue_reasons, refutations gi2 RC6 and ec5) holds waiting.

Synthetic data only; the provider is an in-process fake (no network).
"""
from django.test import Client

from studio import customer_api, models
from tests.support import factories as f
from tests.test_pipeline_api import FakeProvider, drain
from tests.test_repairs_7c8_p1reports import COLONOSCOPY
from tests.test_repairs_gi2_present import BIOPSY, LETTER, SNARE, UNDATED, VISIT_TIME, Harness
from tests.test_services_second_review import TwoPassProvider


class RecheckTests(Harness):
    def customer(self, encounter_id, client=None):
        reply = (client or self.client).get(f'/api/encounters/{encounter_id}')
        self.assertEqual(reply.status_code, 200, reply.content)
        return reply.json()

    def test_a_re_check_is_offered_where_one_can_be_asked_and_only_to_a_member_who_may_ask(self):
        provider = self.use(TwoPassProvider(first=[SNARE], later=[BIOPSY]))
        encounter_id = self.create()
        drain()
        self.approve(encounter_id, '45385')
        self.assertEqual(self.row(encounter_id)['queue_reasons'], ['incomplete', 'second_review'])
        doc = self.customer(encounter_id)
        self.assertEqual(doc['recheck'], {'available': True, 'can_request': True})
        self.assertTrue(doc['unresolved'])
        viewer = f.member(self.ws, f.user('viewer'), role=models.Membership.VIEWER)
        client = Client(enforce_csrf_checks=False)
        client.force_login(viewer)
        self.assertEqual(self.customer(encounter_id, client)['recheck'], {'available': True, 'can_request': False})
        self.assertEqual(client.post(f'/api/encounters/{encounter_id}/second-review', data='{}',
                                     content_type='application/json').status_code, 403)
        sent = len(provider.requests)
        reply = self.post(f'/api/encounters/{encounter_id}/second-review')
        self.assertEqual((reply.status_code, reply.json()), (201, {'second_review': 'queued'}))
        self.assertEqual(len(provider.requests), sent)  # the ask queues the stage; the worker sends
        self.assertEqual(self.customer(encounter_id)['recheck'], {'available': False, 'can_request': False})
        self.assertEqual(self.post(f'/api/encounters/{encounter_id}/second-review').status_code, 409)
        drain()
        self.assertEqual(len(provider.requests), sent + 1)  # one bounded request, once
        doc = self.customer(encounter_id)
        self.assertEqual(doc['recheck'], {'available': False, 'can_request': False})
        self.assertEqual(self.post(f'/api/encounters/{encounter_id}/second-review').status_code, 409)
        self.assertEqual(len(provider.requests), sent + 1)

    def test_no_re_check_is_offered_where_nothing_is_open_or_while_processing(self):
        self.use(TwoPassProvider(first=[SNARE, BIOPSY], later=[]))
        complete = self.create()
        self.assertEqual(self.customer(complete)['recheck'], {'available': False, 'can_request': False})  # processing
        drain()
        self.approve(complete, '45385')
        self.approve(complete, '45380')
        self.assertEqual(self.customer(complete)['recheck'], {'available': False, 'can_request': False})


class QueueTests(Harness):
    def customer_rows(self):
        reply = self.client.get('/api/encounters')
        self.assertEqual(reply.status_code, 200, reply.content)
        return reply.json()['encounters']

    def test_the_badge_counts_exactly_the_rows_the_queue_lists(self):
        self.use(TwoPassProvider(first=[SNARE], later=[BIOPSY]))
        reviewed = self.create()  # reviewed, its biopsy left open with a re-check available
        drain()
        self.approve(reviewed, '45385')
        self.use(TwoPassProvider(first=[SNARE, BIOPSY], later=[]))
        complete = self.create(COLONOSCOPY.replace('Colonoscopy report', 'Colonoscopy report (second copy)'))
        drain()
        self.approve(complete, '45385')
        self.approve(complete, '45380')
        self.use(FakeProvider(selections=[('99213', VISIT_TIME)]))
        letter = self.create(LETTER)
        drain()
        processing = self.create(UNDATED)  # still processing
        rows = {row['id']: row for row in self.customer_rows()}
        self.assertEqual({key: row['in_queue'] for key, row in rows.items()},
                         {reviewed: True, complete: False, letter: True, processing: False})
        self.assertEqual(rows[reviewed]['state'], 'reviewed')  # beyond the three states: what the rule holds waiting
        self.assertEqual(self.queue_count(), 2)
        self.assertEqual(self.queue_count(), sum(row['in_queue'] for row in rows.values()))
        operator_rows = {row['id']: row for row in self.rows()}
        for key, row in rows.items():
            self.assertEqual(row['in_queue'], row['state'] in customer_api.QUEUE_STATES
                             or bool(operator_rows[key]['queue_reasons']), key)
