"""The operator console (BUILD-SPEC 9; studio.operator): the gate (every /ops/ URL answers what an unknown URL answers
to anyone who is not an operator, before anything else), the pages (the list, an encounter's rounds, runs, whole
answers, codes, decisions, answers, audit events and original), the audit of views, and the three recorded acts with
their CSRF check: reconcile an unknown run, retry a failed round, release the holds. Synthetic data only."""
from django.test import Client, TestCase

from studio import jobs, models
from tests.support import operator as ops
from tests.support import rounds as r

Run, Round = models.ProviderRun, models.CodingRound


class ConsoleCase(r.CustomerCase, TestCase):
    def setUp(self):
        super().setUp()
        self.enc = self.done(title='Synthetic EGD for the console')
        self.round = Round.objects.get(encounter=self.enc)
        self.operator_user = r.f.user('platform-operator')
        self.ops = ops.client(self.operator_user)

    def urls(self):
        run = Run.objects.filter(encounter=self.enc).first()
        return {'GET': ['/ops/', f'/ops/encounters/{self.enc.pk}', f'/ops/encounters/{self.enc.pk}/original'],
                'POST': [f'/ops/encounters/{self.enc.pk}/reconcile', f'/ops/encounters/{self.enc.pk}/retry',
                         '/ops/holds/release'],
                'run': run}

    def unknown(self, run=None):
        run = run or Run.objects.filter(encounter=self.enc, purpose=jobs.CHECKER).get()
        Run.objects.filter(pk=run.pk).update(state=Run.UNKNOWN)
        return run


class GateTests(ConsoleCase):
    def test_every_ops_url_answers_a_customer_exactly_as_an_unknown_url(self):
        owner = r.f.member(self.ws, role=models.Membership.OWNER)
        callers = {'anonymous': Client(), 'reviewer': self.client_for(self.reviewer),
                   'owner': self.client_for(owner), 'viewer': self.client_for(self.viewer)}
        urls = self.urls()
        unknown = Client().get('/opsx/nothing-here')
        for name, caller in callers.items():
            for method in ('GET', 'POST'):
                for url in urls[method] + urls['GET' if method == 'POST' else 'POST']:
                    with self.subTest(caller=name, method=method, url=url):
                        response = caller.get(url) if method == 'GET' else caller.post(url, {'note': 'x' * 20})
                        self.assertEqual(response.status_code, 404)
                        self.assertEqual(response.get('Vary'), unknown.get('Vary'))
        self.assertEqual(self.client_for(self.reviewer).get('/ops').status_code, 404)  # no slash appended
        self.assertFalse(models.ProviderRun.objects.filter(reconciled_at__isnull=False).exists())
        self.assertEqual(Round.objects.filter(encounter=self.enc).count(), 1)

    def test_a_revoked_operator_is_a_stranger_again(self):
        self.assertEqual(self.ops.get('/ops/').status_code, 200)
        from studio import operator
        operator.revoke(self.operator_user, 'Synthetic test revocation of the console grant.', 'tests')
        self.assertEqual(self.ops.get('/ops/').status_code, 404)


class PageTests(ConsoleCase):
    def test_the_list_shows_every_workspaces_encounters_with_their_latest_cost(self):
        other = r.f.encounter(self.other_ws, self.outsider, title='Another practice note')
        r.f.paste(other, self.outsider)
        response = self.ops.get('/ops/')
        self.assertEqual(response.status_code, 200)
        page = response.content.decode('utf-8')
        for text in ('Synthetic EGD for the console', 'Another practice note', 'Gastroenterology', 'Another practice',
                     'Questions for you', 'none (earlier review)', 'No hold stands'):
            with self.subTest(text=text):
                self.assertIn(text, page)
        cost = sum(jobs.run_cost(run) for run in Run.objects.filter(encounter=self.enc))
        self.assertIn(f'{cost.quantize(cost.__class__("0.000001"))}', page)

    def test_an_encounter_page_shows_the_record_and_is_audited_once(self):
        self.unknown()
        response = self.ops.get(f'/ops/encounters/{self.enc.pk}')
        self.assertEqual(response.status_code, 200)
        page = response.content.decode('utf-8')
        source = self.enc.files.get()
        reader = Run.objects.get(encounter=self.enc, purpose=jobs.READER)
        for text in (f'sha256 {source.sha256}', 'claude-fable-5-2', 'reader', 'checker', 'req_synthetic',
                     reader.response_id, 'input 12000', 'output 3000', 'I read the whole note.',
                     'The polyp was removed by snare.', 'A diagnostic colonoscopy is documented.',
                     'Was a biopsy taken from a separate site?', 'The note is not signed.', 'Record the reconciliation',
                     'coding.round_done', 'provider.sending', 'Citations by code'):
            with self.subTest(text=text):
                self.assertIn(text, page)
        self.ops.get(f'/ops/encounters/{self.enc.pk}')
        events = models.AuditEvent.objects.filter(encounter=self.enc, event='operator.viewed')
        self.assertEqual([(event.actor_id, event.data['view']) for event in events],
                         [(self.operator_user.pk, 'detail')])

    def test_the_original_is_served_with_its_sha256_and_audited(self):
        response = self.ops.get(f'/ops/encounters/{self.enc.pk}/original')
        self.assertEqual(response.status_code, 200)
        source = self.enc.files.get()
        self.assertEqual(response['X-Content-SHA256'], source.sha256)
        self.assertEqual(response.content, r.f.PDF_BYTES)
        self.assertTrue(models.AuditEvent.objects.filter(event='operator.viewed', data__view='original').exists())

    def test_the_pages_render_for_a_paste_and_every_round_state(self):
        enc = self.encounter(title='Synthetic pasted note', pdf=False)
        r.write_round(enc, state_=Round.FAILED, failure_kind='busy', error=jobs.FAILURE_TEXT['busy'],
                      codes=[{'code': '45385', 'status': 'ready', 'modifiers': None, 'second_check': None}])
        page = self.ops.get(f'/ops/encounters/{enc.pk}')
        self.assertEqual(page.status_code, 200)
        text = page.content.decode('utf-8')
        self.assertIn('Pasted text, ', text)
        self.assertIn('Retry the failed round', text)
        self.assertIn('No run was recorded for this round.', text)
        r.write_round(enc, state_=Round.CANCELLED)
        r.write_round(enc, state_=Round.QUEUED)
        self.assertEqual(self.ops.get(f'/ops/encounters/{enc.pk}').status_code, 200)
        earlier = self.encounter(title='Synthetic earlier review')
        self.assertIn('No coding round: an earlier review.',
                      self.ops.get(f'/ops/encounters/{earlier.pk}').content.decode('utf-8'))
        self.assertEqual(self.ops.get('/ops/').status_code, 200)
        self.assertEqual(self.ops.get('/ops/encounters/f1000000-0000-4000-8000-000000000009').status_code, 404)

    def test_a_fallback_served_run_is_flagged(self):
        reader = Run.objects.get(encounter=self.enc, purpose=jobs.READER)
        Run.objects.filter(pk=reader.pk).update(scope={**reader.scope, 'fallback': True})
        self.assertIn('served by a fallback', self.ops.get(f'/ops/encounters/{self.enc.pk}').content.decode())


class ActTests(ConsoleCase):
    def test_reconcile_records_an_unknown_run_with_a_note_and_needs_the_token(self):
        run = self.unknown()
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(self.operator_user)
        url = f'/ops/encounters/{self.enc.pk}/reconcile'
        self.assertEqual(strict.post(url, {'run': str(run.pk), 'note': 'Checked the console.'}).status_code, 403)
        short = self.ops.post(url, {'run': str(run.pk), 'note': 'too short'})
        self.assertEqual(short.status_code, 400)
        self.assertIn('at least 12 characters', short.content.decode())
        done = self.ops.post(url, {'run': str(run.pk), 'note': 'The vendor console shows it was billed once.'})
        self.assertEqual((done.status_code, done['Location']), (303, f'/ops/encounters/{self.enc.pk}?done=reconciled'))
        run.refresh_from_db()
        self.assertEqual((run.reconciled_by_id, run.reconciliation_note),
                         (self.operator_user.pk, 'The vendor console shows it was billed once.'))
        again = self.ops.post(url, {'run': str(run.pk), 'note': 'The vendor console shows it was billed once.'})
        self.assertEqual(again.status_code, 409)
        other = self.ops.post(url, {'run': 'not-a-run', 'note': 'The vendor console shows nothing.'})
        self.assertEqual(other.status_code, 404)
        self.assertIn('The reconciliation was recorded.', self.ops.get(done['Location']).content.decode())

    def test_retry_queues_a_new_round_of_a_failed_round_only(self):
        url = f'/ops/encounters/{self.enc.pk}/retry'
        refused = self.ops.post(url)
        self.assertEqual(refused.status_code, 409)
        self.assertIn(jobs.RETRY_NOTHING, refused.content.decode())
        Round.objects.filter(pk=self.round.pk).update(state=Round.FAILED, failure_kind='busy')
        response = self.ops.post(url)
        self.assertEqual(response.status_code, 303)
        latest = Round.objects.filter(encounter=self.enc).order_by('-number').first()
        self.assertEqual((latest.number, latest.trigger, latest.state), (2, Round.RETRY, Round.QUEUED))
        self.assertEqual(models.Job.objects.filter(encounter=self.enc, state=models.Job.QUEUED).count(), 1)

    def test_release_ends_every_standing_hold_with_the_operators_note(self):
        run = Run.objects.filter(encounter=self.enc).first()
        hold = models.InterpreterHold.objects.create(reason='auth', http_status=401, vendor_status='authentication_error',
                                                     violations=[], run=run)
        page = self.ops.get('/ops/').content.decode()
        self.assertIn('Release every standing hold', page)
        self.assertIn('authentication_error', page)
        empty = self.ops.post('/ops/holds/release', {'note': '  '})
        self.assertEqual(empty.status_code, 400)
        response = self.ops.post('/ops/holds/release', {'note': 'The key was rotated and checked.'})
        self.assertEqual((response.status_code, response['Location']), (303, '/ops/?done=released'))
        release = models.InterpreterHoldRelease.objects.get(hold=hold)
        self.assertEqual((release.released_by_id, release.note), (self.operator_user.pk,
                                                                   'The key was rotated and checked.'))
        self.assertFalse(jobs.standing_holds().exists())
        self.assertEqual(self.ops.post('/ops/holds/release', {'note': 'Nothing stands now.'}).status_code, 409)
