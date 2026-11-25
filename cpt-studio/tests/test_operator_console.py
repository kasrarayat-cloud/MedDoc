"""The operator console (BUILD-SPEC 9; studio.operator): the gate (every /ops/ URL answers what an unknown URL answers
to anyone who is not an operator, before anything else), the pages (the list by reference, an encounter's metadata, and
its rounds' whole answers, codes, decisions, answers, audit events' data and original once its content is opened with a
reason - release 1, C2), the record of every read (C1: ops.list, ops.detail, ops.content_open, ops.original), and the
three recorded acts with their CSRF check: reconcile an unknown run, retry a failed round, release the holds, each
refusal a 303 back to its page with its code. Synthetic data only."""
from datetime import timedelta
from unittest import mock

from django.conf import settings
from django.test import Client, TestCase
from django.utils import timezone

from studio import jobs, models, operator
from tests.support import operator as ops
from tests.support import rounds as r
from tests.test_admin_console import use_throttle

Run, Round = models.ProviderRun, models.CodingRound


class ConsoleCase(r.CustomerCase, TestCase):
    def setUp(self):
        super().setUp()
        self.enc = self.done(title='Synthetic EGD for the console')
        self.round = Round.objects.get(encounter=self.enc)
        self.operator_user = r.f.user('platform-operator')
        self.ops = ops.admin_client(self.operator_user)
        use_throttle(self)  # the Sign-ins page reads Lane 2's studio.throttle (a stub while this tree has none)

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
        for name, caller in callers.items():
            # what an unknown URL answers this same caller: release 1's session policy (studio.sessions) reads a
            # signed-in caller's session before every view, so its unknown-URL answer carries Vary: Cookie too
            unknown = caller.get('/opsx/nothing-here')
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
        # the revocation ended the session (release 1, C3): signed out, the admin host sends it to the sign-in
        self.assertEqual(self.ops.get('/ops/')['Location'], '/login/?next=%2Fops%2F')
        # and a new session of the account, second factor and all (no new grant), is a stranger's
        again = Client(HTTP_HOST='admin.quillmd.com')
        again.force_login(self.operator_user)
        self.assertEqual(ops.mark_signed_in(again, door='admin').get('/ops/').status_code, 404)


class PageTests(ConsoleCase):
    def test_the_list_names_every_workspaces_encounters_by_reference_with_their_latest_cost(self):
        other = r.f.encounter(self.other_ws, self.outsider, title='Another practice note')
        r.f.paste(other, self.outsider)
        response = self.ops.get('/ops/')
        self.assertEqual(response.status_code, 200)
        page = response.content.decode('utf-8')
        for text in (str(self.enc.pk)[:8], str(other.pk)[:8], 'Gastroenterology', 'Another practice',
                     'Questions for you', 'none (earlier review)', 'No hold stands'):
            with self.subTest(text=text):
                self.assertIn(text, page)
        for title in ('Synthetic EGD for the console', 'Another practice note', 'synthetic-note'):  # release 1, C2
            self.assertNotIn(title, page)
        cost = sum(jobs.run_cost(run) for run in Run.objects.filter(encounter=self.enc))
        self.assertIn(f'{cost.quantize(cost.__class__("0.000001"))}', page)
        listed = models.AccessRecord.objects.get(view='ops.list')
        self.assertEqual((set(listed.encounter_ids), listed.count, listed.actor_role),
                         ({str(self.enc.pk), str(other.pk)}, 2, 'operator'))

    def test_an_encounter_page_opens_on_its_metadata_and_records_every_view(self):
        self.unknown()
        response = self.ops.get(f'/ops/encounters/{self.enc.pk}')
        self.assertEqual(response.status_code, 200)
        page = response.content.decode('utf-8')
        source = self.enc.files.get()
        reader = Run.objects.get(encounter=self.enc, purpose=jobs.READER)
        for text in (f'<title>Encounter {str(self.enc.pk)[:8]} · CPT Studio</title>', f'sha256 {source.sha256}',
                     'claude-fable-5-2', 'reader', 'checker', 'req_synthetic', reader.response_id, 'input 12000',
                     'output 3000', 'Record the reconciliation', 'coding.round_done', 'provider.sending',
                     'Open the content', 'No patient details.'):
            with self.subTest(text=text):
                self.assertIn(text, page)
        for content in ('Synthetic EGD for the console', 'synthetic-note.pdf', 'I read the whole note.',
                        'The polyp was removed by snare.', 'A diagnostic colonoscopy is documented.',
                        'Was a biopsy taken from a separate site?', 'The note is not signed.', 'Citations by line',
                        '2026-11-02', 'medicare', f'/ops/encounters/{self.enc.pk}/original'):
            with self.subTest(closed=content):
                self.assertNotIn(content, page)
        self.ops.get(f'/ops/encounters/{self.enc.pk}')
        rows = models.AccessRecord.objects.filter(view='ops.detail').order_by('created_at')
        self.assertEqual([(row.actor_id, row.encounter_ids, row.filters) for row in rows],
                         [(self.operator_user.pk, [str(self.enc.pk)], {'content': False})] * 2)
        self.assertFalse(models.AuditEvent.objects.filter(event='operator.viewed').exists())  # the read is the record

    def test_the_content_opens_with_a_reason_and_a_reference_for_this_session_only(self):
        open_content(self.ops, self.enc)
        page = self.ops.get(f'/ops/encounters/{self.enc.pk}').content.decode('utf-8')
        for text in ('Synthetic EGD for the console', 'synthetic-note.pdf', 'I read the whole note.',
                     'The polyp was removed by snare.', 'A diagnostic colonoscopy is documented.',
                     'Was a biopsy taken from a separate site?', 'The note is not signed.', 'Citations by line',
                     '2026-11-02', f'/ops/encounters/{self.enc.pk}/original', 'Open in this session until'):
            with self.subTest(text=text):
                self.assertIn(text, page)
        self.assertIn(f'<title>Encounter {str(self.enc.pk)[:8]} · CPT Studio</title>', page)  # the tab never names it
        opened = models.AccessRecord.objects.get(view='ops.content_open')
        self.assertEqual((opened.reason, opened.encounter_ids), ('support_request: SR-2026-0042', [str(self.enc.pk)]))
        self.assertEqual(models.AccessRecord.objects.filter(view='ops.detail').get().filters, {'content': True})
        # another session of the same operator has no grant
        other = ops.admin_client(self.operator_user)
        self.assertNotIn('I read the whole note.', other.get(f'/ops/encounters/{self.enc.pk}').content.decode())
        self.assertEqual(other.get(f'/ops/encounters/{self.enc.pk}/original').status_code, 403)

    def test_the_original_is_served_only_while_open_named_by_reference_with_its_sha256(self):
        url = f'/ops/encounters/{self.enc.pk}/original'
        closed = self.ops.get(url)
        self.assertEqual((closed.status_code, closed.content.decode()), (403, 'Open the content first, with a reason.'))
        self.assertFalse(models.AccessRecord.objects.filter(view='ops.original').exists())
        open_content(self.ops, self.enc)
        response = self.ops.get(url)
        self.assertEqual(response.status_code, 200)
        source = self.enc.files.get()
        self.assertEqual(response['X-Content-SHA256'], source.sha256)
        self.assertEqual(response.content, r.f.PDF_BYTES)
        self.assertEqual(response['Content-Disposition'], f'attachment; filename="encounter-{str(self.enc.pk)[:8]}.pdf"')
        row = models.AccessRecord.objects.get(view='ops.original')
        self.assertEqual((row.encounter_ids, row.filters), ([str(self.enc.pk)], {'format': 'original'}))

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
        open_content(self.ops, enc)
        self.assertIn('45385', self.ops.get(f'/ops/encounters/{enc.pk}').content.decode())
        r.write_round(enc, state_=Round.CANCELLED)
        r.write_round(enc, state_=Round.QUEUED)
        self.assertEqual(self.ops.get(f'/ops/encounters/{enc.pk}').status_code, 200)
        earlier = self.encounter(title='Synthetic earlier review')
        self.assertIn('No coding round: an earlier review.',
                      self.ops.get(f'/ops/encounters/{earlier.pk}').content.decode('utf-8'))
        self.assertEqual(self.ops.get('/ops/').status_code, 200)
        self.assertEqual(self.ops.get('/ops/encounters/f1000000-0000-4000-8000-000000000009').status_code, 404)

    def test_codes_decisions_and_citations_are_shown_by_line(self):
        # FIX-SPEC 1: two lines can hold one code, so the console names the line of every row and every decision, and
        # files the citations by line; units and modifiers the coding review did not give read "not given"
        self.assertEqual(self.decide(self.enc, 'L1', '45385', 'approve').status_code, 201)
        metadata = self.ops.get(f'/ops/encounters/{self.enc.pk}').content.decode('utf-8')
        self.assertIn('Decisions</th><td>1 · approve 1', metadata)
        self.assertNotIn('<th>Line</th><th>Code</th>', metadata)
        open_content(self.ops, self.enc)
        page = self.ops.get(f'/ops/encounters/{self.enc.pk}').content.decode('utf-8')
        for fragment in ('<th>Line</th><th>Code</th>', '<td class="mono">L1</td><td class="mono">45385</td><td class="num">1</td>',
                         '<td class="mono">M1</td><td class="mono">45378</td><td class="num">1</td>',
                         '<td class="mono">L1</td><td class="mono">45385</td><td>approve</td>', 'Citations by line',
                         'lines L2; codes 45380'):
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, page)
        self.assertNotIn('Citations by code', page)
        given = self.encounter(title='Synthetic note with nothing given')
        r.write_round(given, codes=[r.row('64483', 'needs_review', units=None, modifiers=None),
                                    r.row('64483', 'ready', modifiers=[])])
        open_content(self.ops, given)
        page = self.ops.get(f'/ops/encounters/{given.pk}').content.decode('utf-8')
        self.assertIn('<td class="mono">L1</td><td class="mono">64483</td><td class="num">not given</td>'
                      '<td class="mono">not given</td>', page)
        self.assertIn('<td class="mono">L2</td><td class="mono">64483</td><td class="num">1</td><td class="mono">none</td>',
                      page)

    def test_a_fallback_served_run_is_flagged(self):
        reader = Run.objects.get(encounter=self.enc, purpose=jobs.READER)
        Run.objects.filter(pk=reader.pk).update(scope={**reader.scope, 'fallback': True})
        self.assertIn('served by a fallback', self.ops.get(f'/ops/encounters/{self.enc.pk}').content.decode())


class ActTests(ConsoleCase):
    def refused(self, response, code, page=None):
        """A refusal: 303 back to the page with the refusal's code, which that page then names."""
        page = page or f'/ops/encounters/{self.enc.pk}'
        self.assertEqual((response.status_code, response['Location']), (303, f'{page}?error={code}'))
        self.assertIn(operator.ERRORS[code], self.ops.get(response['Location']).content.decode())

    def test_reconcile_records_an_unknown_run_with_a_note_and_needs_the_token(self):
        run = self.unknown()
        strict = ops.admin_client(self.operator_user, enforce_csrf_checks=True)
        url = f'/ops/encounters/{self.enc.pk}/reconcile'
        self.assertEqual(strict.post(url, {'run': str(run.pk), 'note': 'Checked the console.'}).status_code, 403)
        self.refused(self.ops.post(url, {'run': str(run.pk), 'note': 'too short'}), 'note-short')
        self.assertIn('at least 12 characters', operator.ERRORS['note-short'])
        done = self.ops.post(url, {'run': str(run.pk), 'note': 'The vendor console shows it was billed once.'})
        self.assertEqual((done.status_code, done['Location']), (303, f'/ops/encounters/{self.enc.pk}?done=reconciled'))
        run.refresh_from_db()
        self.assertEqual((run.reconciled_by_id, run.reconciliation_note),
                         (self.operator_user.pk, 'The vendor console shows it was billed once.'))
        self.refused(self.ops.post(url, {'run': str(run.pk), 'note': 'The vendor console shows it was billed once.'}),
                     'reconcile-only')
        self.refused(self.ops.post(url, {'run': 'not-a-run', 'note': 'The vendor console shows nothing.'}), 'run')
        self.assertIn('The reconciliation was recorded.', self.ops.get(done['Location']).content.decode())

    def test_retry_queues_a_new_round_of_a_failed_round_only(self):
        url = f'/ops/encounters/{self.enc.pk}/retry'
        self.refused(self.ops.post(url), 'retry-nothing')
        self.assertEqual(operator.ERRORS['retry-nothing'], jobs.RETRY_NOTHING)
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
        self.refused(self.ops.post('/ops/holds/release', {'note': '  '}), 'release-note', page='/ops/')
        response = self.ops.post('/ops/holds/release', {'note': 'The key was rotated and checked.'})
        self.assertEqual((response.status_code, response['Location']), (303, '/ops/?done=released'))
        release = models.InterpreterHoldRelease.objects.get(hold=hold)
        self.assertEqual((release.released_by_id, release.note), (self.operator_user.pk,
                                                                   'The key was rotated and checked.'))
        self.assertFalse(jobs.standing_holds().exists())
        self.refused(self.ops.post('/ops/holds/release', {'note': 'Nothing stands now.'}), 'no-hold', page='/ops/')

    def test_a_refusal_whose_sentence_has_no_code_names_none_of_its_text(self):
        with mock.patch.object(jobs, 'retry', side_effect=jobs.Refused('A sentence jobs has not said before.')):
            answer = self.ops.post(f'/ops/encounters/{self.enc.pk}/retry')
        self.refused(answer, 'refused')
        self.assertNotIn('sentence', answer['Location'])



class MinimumNecessaryTests(ConsoleCase):
    """Release 1, C2: the seeded title, file name and note text appear on no console page without a grant - every
    console GET route - and do appear with one; the grant is this session's, ends after CONTENT_GRANT_SECONDS, and needs
    a reason and a reference; the download's name holds none of them."""
    TITLE, FILE, TEXT = 'ZZ-TITLE-MARKER', 'zz-file-marker-note.txt', 'ZZ-TEXT-MARKER'

    def setUp(self):
        super().setUp()
        self.marked = r.f.encounter(self.ws, self.reviewer, title=f'{self.TITLE} synthetic note', service_date='2026-11-03')
        r.f.upload(self.marked, self.reviewer, data=f'SYNTHETIC NOTE {self.TEXT} polyp removed.'.encode(),
                   filename=self.FILE, media_type='text/plain')
        r.write_round(self.marked, codes=[r.row('45385', 'ready', reason=f'{self.TEXT} documents the snare.')],
                      problems=[f'{self.TEXT} is not signed.'])
        models.CodingAnswer.objects.create(encounter=self.marked, round=Round.objects.get(encounter=self.marked),
                                           question='Synthetic question?', answer=f'{self.TEXT} answer',
                                           answered_by=self.reviewer)

    def console_gets(self):
        """Every console route a GET reaches (the full urlconf's ops/ routes, real ids, and each list's filters)."""
        from cptstudio import urls as customer_urls
        ids = {'<uuid:encounter_id>': str(self.marked.pk), '<uuid:user_id>': str(self.reviewer.pk),
               '<uuid:workspace_id>': str(self.ws.pk)}
        paths = []
        for pattern in customer_urls.urlpatterns:
            route = str(pattern.pattern)
            if route.startswith('ops/'):
                for placeholder, value in ids.items():
                    route = route.replace(placeholder, value)
                paths.append('/' + route)
        return paths + [f'/ops/activity?workspace={self.ws.pk}', '/ops/activity?kind=documents',
                        f'/ops/activity/reads?workspace={self.ws.pk}', '/ops/encounters/' + str(self.marked.pk) +
                        '/original?format=original']

    def assert_unmarked(self, client, path):
        answer = client.get(path)
        body = answer.content.decode('utf-8', 'replace')
        for marker in (self.TITLE, self.FILE, self.TEXT, 'synthetic note'):
            self.assertNotIn(marker, body)
            self.assertNotIn(marker, answer.get('Content-Disposition', ''))
        return answer

    def test_no_console_page_shows_the_title_file_name_or_text_without_a_grant(self):
        statuses = {}
        for path in self.console_gets():
            with self.subTest(path=path):
                statuses[path] = self.assert_unmarked(self.ops, path).status_code
        self.assertEqual(statuses[f'/ops/encounters/{self.marked.pk}'], 200)
        self.assertEqual(statuses[f'/ops/encounters/{self.marked.pk}/original'], 403)
        self.assertEqual(statuses['/ops/'], 200)

    def test_with_a_grant_the_document_shows_them_and_the_download_is_named_by_reference(self):
        open_content(self.ops, self.marked)
        page = self.ops.get(f'/ops/encounters/{self.marked.pk}').content.decode()
        for marker in (self.TITLE, self.FILE, self.TEXT, '2026-11-03'):
            with self.subTest(marker=marker):
                self.assertIn(marker, page)
        original = self.ops.get(f'/ops/encounters/{self.marked.pk}/original')
        self.assertIn(self.TEXT.encode(), original.content)
        self.assertEqual(original['Content-Disposition'],
                         f'attachment; filename="encounter-{str(self.marked.pk)[:8]}.txt"')
        for path in ('/ops/', '/ops/spending', '/ops/activity', '/ops/activity/reads'):  # the lists stay unmarked
            with self.subTest(path=path):
                self.assert_unmarked(self.ops, path)

    def test_the_grant_ends_after_its_time(self):
        start = timezone.now()
        with mock.patch.object(timezone, 'now', return_value=start):
            open_content(self.ops, self.marked)
        within = start + timedelta(seconds=settings.CONTENT_GRANT_SECONDS - 1)
        after = start + timedelta(seconds=settings.CONTENT_GRANT_SECONDS + 1)
        # release 1, B5 (Lane 2): an operator idle for SESSION_IDLE_OPERATOR_SECONDS is signed out before the grant ends,
        # so this operator keeps working in between; the grant's own end is what the test measures
        working = start + timedelta(seconds=settings.SESSION_IDLE_OPERATOR_SECONDS - 100)
        with mock.patch.object(timezone, 'now', return_value=working):
            self.assertEqual(self.ops.get('/ops/').status_code, 200)
        with mock.patch.object(timezone, 'now', return_value=within):
            self.assertIn(self.TITLE, self.ops.get(f'/ops/encounters/{self.marked.pk}').content.decode())
            self.assertEqual(self.ops.get(f'/ops/encounters/{self.marked.pk}/original').status_code, 200)
        with mock.patch.object(timezone, 'now', return_value=after):
            self.assert_unmarked(self.ops, f'/ops/encounters/{self.marked.pk}')
            self.assertEqual(self.ops.get(f'/ops/encounters/{self.marked.pk}/original').status_code, 403)

    def test_a_grant_opens_one_document_only(self):
        open_content(self.ops, self.enc)
        self.assert_unmarked(self.ops, f'/ops/encounters/{self.marked.pk}')
        self.assertEqual(self.ops.get(f'/ops/encounters/{self.marked.pk}/original').status_code, 403)

    def test_the_reason_and_the_reference_are_both_required(self):
        url = f'/ops/encounters/{self.marked.pk}/content'
        for label, body, code in (('no reason', {'reference': 'SR-1001'}, 'reason'),
                                  ('an unknown reason', {'reason': 'curiosity', 'reference': 'SR-1001'}, 'reason'),
                                  ('no reference', {'reason': 'support_request'}, 'reference'),
                                  ('a blank reference', {'reason': 'support_request', 'reference': '   '}, 'reference'),
                                  ('a name, no number', {'reason': 'support_request', 'reference': 'Jane Doe'}, 'reference'),
                                  ('too long', {'reason': 'support_request', 'reference': '1' * 61}, 'reference'),
                                  ('a NUL', {'reason': 'support_request', 'reference': 'SR-1\x00'}, 'reference'),
                                  ('a script', {'reason': 'support_request', 'reference': '<b>1</b>'}, 'reference')):
            with self.subTest(label):
                answer = self.ops.post(url, body)
                self.assertEqual((answer.status_code, answer['Location']),
                                 (303, f'/ops/encounters/{self.marked.pk}?error={code}'))
        self.assertFalse(models.AccessRecord.objects.filter(view='ops.content_open').exists())
        self.assert_unmarked(self.ops, f'/ops/encounters/{self.marked.pk}')
        self.assertIn(operator.REFERENCE_RULE, self.ops.get(f'/ops/encounters/{self.marked.pk}?error=reference')
                      .content.decode())
        for reason in operator.CONTENT_REASONS:  # each of the four reasons opens it
            with self.subTest(reason=reason):
                open_content(self.ops, self.marked, reason=reason, reference='TICKET 1001/2')
        open_content(self.ops, self.marked, reference=' SR-77 \n  part 2 ')  # white space read as one space
        self.assertEqual(models.AccessRecord.objects.filter(reason='support_request: SR-77 part 2').count(), 1)
        self.assertEqual(sorted(row.reason.split(':')[0] for row in
                                models.AccessRecord.objects.filter(view='ops.content_open')),
                         sorted([*operator.CONTENT_REASONS, 'support_request']))

    def test_the_content_form_says_no_patient_details_and_is_csrf_checked(self):
        page = self.ops.get(f'/ops/encounters/{self.marked.pk}').content.decode()
        self.assertIn('No patient details.', page)
        strict = ops.admin_client(self.operator_user, enforce_csrf_checks=True)
        answer = strict.post(f'/ops/encounters/{self.marked.pk}/content', {'reason': 'support_request',
                                                                          'reference': 'SR-1001'})
        self.assertEqual(answer.status_code, 403)
        self.assertFalse(models.AccessRecord.objects.filter(view='ops.content_open').exists())


class ClosedAndDestroyedTests(ConsoleCase):
    """Release 1, D1 (Lane 4's disposal): a destroyed document's tombstone is in no console list and its routes answer
    404; a closed practice drops out of the console's routine lists - its documents leave the front page - while its
    records stay."""

    def test_the_front_page_leaves_out_tombstones_and_closed_practices(self):
        gone = self.encounter(title='Synthetic destroyed note')
        models.Encounter.objects.filter(pk=gone.pk).update(destroyed_at=timezone.now(), state='destroyed', title='')
        closed_note = r.f.encounter(self.other_ws, self.outsider, title='Synthetic note of a closed practice')
        r.f.paste(closed_note, self.outsider)
        models.Workspace.objects.filter(pk=self.other_ws.pk).update(closed_at=timezone.now())
        page = self.ops.get('/ops/').content.decode()
        self.assertIn(str(self.enc.pk)[:8], page)
        self.assertNotIn(str(gone.pk)[:8], page)
        self.assertNotIn(str(closed_note.pk)[:8], page)
        self.assertIn('The documents of 1 closed workspace are left out.', page)
        self.assertEqual(models.AccessRecord.objects.get(view='ops.list').encounter_ids, [str(self.enc.pk)])
        # a closed practice's document keeps its page (reading stays on until the practice confirms receipt)
        self.assertEqual(self.ops.get(f'/ops/encounters/{closed_note.pk}').status_code, 200)

    def test_every_console_route_of_a_tombstone_answers_404(self):
        gone = self.encounter(title='Synthetic destroyed note')
        models.Encounter.objects.filter(pk=gone.pk).update(destroyed_at=timezone.now(), state='destroyed', title='')
        for method, path, body in (('get', f'/ops/encounters/{gone.pk}', None),
                                   ('get', f'/ops/encounters/{gone.pk}/original', None),
                                   ('post', f'/ops/encounters/{gone.pk}/content',
                                    {'reason': 'support_request', 'reference': 'SR-1'}),
                                   ('post', f'/ops/encounters/{gone.pk}/retry', {}),
                                   ('post', f'/ops/encounters/{gone.pk}/reconcile', {'run': '', 'note': 'x' * 20})):
            with self.subTest(path=path, method=method):
                answer = getattr(self.ops, method)(path, body) if body is not None else getattr(self.ops, method)(path)
                self.assertEqual(answer.status_code, 404)
        self.assertFalse(models.AccessRecord.objects.filter(encounter_ids__contains=[str(gone.pk)]).exists())

    def test_the_activity_keeps_a_tombstones_events_with_no_link_to_it(self):
        gone = self.encounter(title='Synthetic destroyed note')
        models.Encounter.objects.filter(pk=gone.pk).update(destroyed_at=timezone.now(), state='destroyed', title='')
        page = self.ops.get('/ops/activity').content.decode()
        self.assertIn(f'<span class="mono">{str(gone.pk)[:8]}</span> <span class="flag">destroyed</span>', page)
        self.assertNotIn(f'href="/ops/encounters/{gone.pk}"', page)
        self.assertIn(f'href="/ops/encounters/{self.enc.pk}"', page)

def open_content(client, encounter, reason='support_request', reference='SR-2026-0042'):
    """Open ``encounter``'s content in ``client``'s session (release 1, C2), as the page's form does."""
    answer = client.post(f'/ops/encounters/{encounter.pk}/content', {'reason': reason, 'reference': reference})
    assert (answer.status_code, answer['Location']) == (303, f'/ops/encounters/{encounter.pk}?done=opened'), answer
    return answer
