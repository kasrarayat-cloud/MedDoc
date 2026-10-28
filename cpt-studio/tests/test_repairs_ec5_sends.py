"""Repair round ec5, cluster SENDS: provider sends, the upgrade and the undo (refutation r1 lenses sends, migrate and
context, re-checked at the reviewer-requested second review, 8985dde42). Synthetic data only; no network: the
provider is an in-process stand-in with the live adapter's name and version, so the real normaliser reads its runs.

Every document opens with the synthetic banner. A context "the installed revision recorded" is the exact row 057a7d39's
merge wrote (gi-context@1: a member's value kept as plain metadata, origin 'user'); a run it sent is built by the same
request builder the stand-in uses for every other run.
"""
import hashlib
import json
from datetime import date, timedelta
from unittest import mock
from uuid import uuid4

from django.conf import settings
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from studio import jobs, models, review
from studio.gi import context as gi_context
from studio.providers import corti
from studio.providers.base import ProviderUnavailable
from tests.support import factories as f
from tests.test_pipeline_api import OFFICE_NOTE, drain
from tests.test_services_second_review import LIVE, REPORT, TwoPassProvider, response

BANNER = 'SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE'
SNARE = ('45385', 'was removed with a cold snare')
BIOPSY = ('45380', 'was sampled with cold biopsy forceps')
VISIT = ('99213', 'Total time on the date of the encounter was 24 minutes.')
DOCUMENTED = date(2026, 10, 16)  # REPORT's own date
MEMBER = '1998-01-01'
EARLIER_VERSION = 'gi-context@1'
# REPORT with its date written as a table row: the installed revision read no date in it, the current rules read
# 2026-10-16 (gi/context.py; the corpus's svc-18 and svc-36 rows are written the same way).
REPORT_TABLE_DATE = REPORT.replace('Date of service: 2026-10-16', 'Date of service | 2026-10-16')


class Provider(TwoPassProvider):
    """TwoPassProvider answering only the quotes the request's own text contains (an excerpt may omit one)."""

    def send(self, request, *, deadline_s):
        first, later = self.first, self.later
        self.first = [q for q in first if q[1] in request.contexts[0]]
        self.later = [q for q in later if q[1] in request.contexts[0]]
        try:
            return super().send(request, deadline_s=deadline_s)
        finally:
            self.first, self.later = first, later


class Base(TestCase):
    provider_class = Provider

    def setUp(self):
        self.ws = f.workspace()
        self.reviewer = f.member(self.ws, f.user('reviewer'))
        self.client = Client(enforce_csrf_checks=False)
        self.client.force_login(self.reviewer)
        self.provider = self.provider_class(first=[SNARE], later=[BIOPSY, SNARE])
        patcher = mock.patch('studio.jobs.get_provider', return_value=self.provider)
        patcher.start()
        self.addCleanup(patcher.stop)

    # --- actions ----------------------------------------------------------------------------------------------------

    def create(self, text=REPORT, **extra):
        with self.captureOnCommitCallbacks(execute=True):
            reply = self.client.post('/api/encounters', {'text': text, 'synthetic_attestation': 'yes', **extra})
        self.assertEqual(reply.status_code, 201, reply.content)
        return reply.json()['id']

    def post(self, path, data=None):
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(path, data=json.dumps(data or {}), content_type='application/json')

    def set_context(self, encounter_id, **values):
        reply = self.post(f'/api/encounters/{encounter_id}/context', values)
        self.assertEqual(reply.status_code, 201, reply.content)

    def ask(self, encounter_id):
        return self.post(f'/api/encounters/{encounter_id}/second-review')

    def detail(self, encounter_id):
        return self.client.get(f'/api/encounters/{encounter_id}').json()

    # --- what was sent and what stands ------------------------------------------------------------------------------

    def sent(self):
        return len(self.provider.requests)

    def dates_sent(self):
        return [c for request in self.provider.requests for c in request.contexts[1:]]

    def encounter(self, encounter_id):
        return models.Encounter.objects.get(pk=encounter_id)

    def selected(self, encounter_id):
        assessment = self.encounter(encounter_id).current_assessment
        return {p.code: p.support.get('origin') for p in assessment.proposals.filter(bucket='selected')}

    def unresolved(self, encounter_id):
        return self.encounter(encounter_id).current_assessment.completeness.get('unresolved_items', [])

    def date_question(self, encounter_id):
        return [q for q in self.detail(encounter_id)['clarifications'] if q['fact'] == 'service_date']

    # --- the installed revision's rows (057a7d39) -------------------------------------------------------------------

    def installed_context(self, encounter_id, values, *, facts=None):
        """The context row 057a7d39 recorded for the current revision with the member's ``values`` (gi-context@1):
        every non-empty member value kept as plain metadata, whatever the document says; the encounter's current one."""
        encounter = self.encounter(encounter_id)
        facts = dict(facts if facts is not None else encounter.current_context.facts)
        for name, value in values.items():
            facts[name] = {'name': name, 'value': value, 'origin': 'user', 'evidence': [], 'note': gi_context.USER_NOTE}
        context = models.EncounterContext.objects.create(
            encounter=encounter, revision=encounter.current_revision, facts=facts, user_values=dict(values),
            version=EARLIER_VERSION, sha256='0' * 64)
        encounter.user_values = dict(values)
        encounter.current_context = context
        encounter.save(update_fields=['user_values', 'current_context', 'updated_at'])
        return context

    def installed_run(self, encounter_id, service_date, *, state=models.ProviderRun.SUCCEEDED, created=None):
        """A primary request the installed revision sent for ``service_date`` (a str or None), and its outcome."""
        encounter = self.encounter(encounter_id)
        revision = encounter.current_revision
        request = self.provider.build_request(revision.text, date.fromisoformat(service_date) if service_date else None)
        self.provider.requests.append(request)  # it was sent: counted as the installed revision's send
        data = response(request.contexts[0], [q for q in self.provider.first if q[1] in request.contexts[0]])
        succeeded = state == models.ProviderRun.SUCCEEDED
        run = models.ProviderRun.objects.create(
            encounter=encounter, revision=revision, provider=self.provider.name,
            adapter_version=self.provider.adapter_version, request_sha256=request.canonical_sha256,
            request_body=request.body, contexts=list(request.contexts), state=state, sent=True,
            http_status=200 if succeeded else None, response_bytes=data if succeeded else b'',
            response_sha256=hashlib.sha256(data).hexdigest() if succeeded else '',
            usage={'creditsConsumed': 0.02} if succeeded else {}, requested_by=self.reviewer,
            service_date=date.fromisoformat(service_date) if service_date else None,
            started_at=timezone.now(), finished_at=timezone.now())
        if created is not None:
            models.ProviderRun.objects.filter(pk=run.pk).update(created_at=created)
            run.refresh_from_db()
        return run

    def installed_job(self, encounter_id, kind, context, *, run=None, state=models.Job.QUEUED, started=None, tag=''):
        encounter = self.encounter(encounter_id)
        job = jobs.enqueue(kind, encounter=encounter, revision=encounter.current_revision, context=context,
                           provider_run=run, key=f'{kind}:{context.pk}:installed{tag}', requested_by=self.reviewer)
        if state != models.Job.QUEUED or started is not None:
            models.Job.objects.filter(pk=job.pk).update(state=state, started_at=started)
            job.refresh_from_db()
        return job

    def before_the_stage(self, encounter_id, started):
        """The rows made before the installed revision's stage started are older than it (the stale-stage sweep
        settles a predict by the run created after its start)."""
        earlier = started - timedelta(hours=1)
        models.ProviderRun.objects.filter(encounter_id=encounter_id).update(created_at=earlier)
        models.Job.objects.filter(encounter_id=encounter_id).exclude(started_at=started).update(created_at=earlier)


# --- sends-0 / migrate-1: an identical request is never sent again, in either direction -------------------------------

@override_settings(**LIVE)
class IdenticalRequestTests(Base):
    """A report documented from its first character makes the second review's excerpt the whole text: the request
    would repeat the primary's byte for byte. It is refused when asked for and skipped however its stage is reached;
    and a later primary identical to an answered second review reuses that answer."""

    TITLE_FIRST = (
        # the banner line is the report's own title, so the report part starts at character 0 (the finding's own
        # input, the report pasted from its title line, is test_services_second_review's title-first case)
        f'{BANNER} - Colonoscopy - procedure note\n' + REPORT[REPORT.index('Date of service'):],
    )

    def whole_text_offered(self, encounter_id):
        offered = self.detail(encounter_id)['second_review']
        assessment = self.encounter(encounter_id).current_assessment
        items, span = jobs._second_review_items(assessment)
        return offered, items, span

    def test_a_report_documented_from_its_first_character_never_resends_the_primary_request(self):
        for text in self.TITLE_FIRST:
            with self.subTest(first_line=text.splitlines()[0][-30:]):
                before = self.sent()
                # the 7c8 fix round (P2DATES, sk:5/sk:7): a first line naming a document in words this service cannot
                # place is no title of the note, so its labelled date is asked; the member answers it (the over-hold's
                # remedy), and the request carries the same date as before
                encounter_id = self.create(text, service_date='2026-10-16')
                drain()
                self.assertEqual(self.sent() - before, 1)
                offered, items, span = self.whole_text_offered(encounter_id)
                self.assertTrue(items)  # the biopsy is unresolved
                revision = self.encounter(encounter_id).current_revision
                self.assertEqual(span, (0, len(revision.text)))  # the finding's precondition: the excerpt is the text
                self.assertFalse(offered['available'])
                self.assertIn('already answered', offered['reason'])
                self.assertEqual(self.ask(encounter_id).status_code, 409)
                drain()
                self.assertEqual(self.sent() - before, 1)

    def test_a_second_review_stage_reached_without_the_request_check_never_resends_it(self):
        # a review2 queued another way (a Resume of one cancelled before it ran, or one an earlier state of this code
        # queued): the stage re-checks the identity itself
        encounter_id = self.create(self.TITLE_FIRST[0])
        drain()
        encounter = self.encounter(encounter_id)
        assessment = encounter.current_assessment
        job = jobs.enqueue(models.Job.REVIEW2, encounter=encounter, revision=encounter.current_revision,
                           context=encounter.current_context, provider_run=assessment.provider_run,
                           key='review2:queued-another-way', requested_by=self.reviewer)
        drain()
        job.refresh_from_db()
        self.assertIn('repeat a primary request already answered', job.result.get('skipped', ''))
        self.assertEqual(self.sent(), 1)
        self.assertFalse(models.ProviderRun.objects.filter(encounter_id=encounter_id, purpose='second_review').exists())

    def test_reverse_a_primary_identical_to_an_answered_second_review_reuses_it(self):
        source = f'{BANNER}\n{self.TITLE_FIRST[0]}'  # its report part, the excerpt, opens with the banner too
        first = self.create(source, service_date='2026-10-16')  # its date asked and answered, as above
        drain()
        self.assertEqual(self.ask(first).status_code, 201)
        drain()
        self.assertEqual(self.sent(), 2)
        excerpt = models.ProviderRun.objects.get(encounter_id=first, purpose='second_review').contexts[0]
        self.assertTrue(excerpt.startswith(BANNER))
        twin = self.create(source, service_date='2026-10-16')  # the same report again: its primary and, asked for,
        # its second review are reused
        drain()
        self.assertEqual(self.ask(twin).status_code, 201)
        drain()
        self.assertEqual(self.sent(), 2)
        second = models.ProviderRun.objects.get(encounter_id=twin, purpose='second_review')
        self.assertEqual((second.sent, second.state), (False, models.ProviderRun.SUCCEEDED))
        pasted = self.create(excerpt, service_date='2026-10-16')  # the excerpt as a note of its own: the answered
        # second review is reused
        drain()
        self.assertEqual(self.sent(), 2)
        run = models.ProviderRun.objects.get(encounter_id=pasted, purpose='primary')
        self.assertEqual((run.sent, run.reused_from.purpose), (False, 'second_review'))
        self.assertIsNone(run.reused_from.reused_from_id)

    def test_control_a_report_under_a_heading_line_sends_its_one_second_review(self):
        encounter_id = self.create()
        drain()
        offered, items, span = self.whole_text_offered(encounter_id)
        self.assertTrue(offered['available'], offered)
        self.assertGreater(span[0], 0)
        self.assertEqual(self.ask(encounter_id).status_code, 201)
        drain()
        self.assertEqual(self.sent(), 2)
        self.assertEqual(self.selected(encounter_id), {'45385': 'primary', '45380': 'second_review'})


# --- sends-1 / migrate-0: a member date the installed revision kept is never sent -------------------------------------

@override_settings(**LIVE)
class PreUpgradeMemberDateTests(Base):
    """The installed revision kept a member's date that differs from the document's as plain metadata
    (gi-context@1, origin 'user'); the current rules keep it as a conflict and send nothing. Whatever door reaches
    such a context after the upgrade - a queued predict, a Resume of a stopped predict or assess, a reconciliation, the
    stale-stage sweep, a context change or a reviewer's second review - nothing is sent with the member's date."""

    def documented(self):
        encounter_id = self.create()
        drain()
        self.assertEqual(self.sent(), 1)
        return encounter_id

    def assert_nothing_sent_with_the_member_date(self, encounter_id, sends):
        """``sends`` counts the requests made before the upgrade (the installed revision's included): none since."""
        self.assertEqual(self.sent(), sends, [r.contexts[1:] for r in self.provider.requests])
        encounter = self.encounter(encounter_id)
        self.assertNotEqual(encounter.current_context.version, EARLIER_VERSION)
        self.assertTrue(gi_context.is_member_conflict(encounter.current_context.facts['service_date']))
        self.assertFalse(models.Job.objects.filter(encounter_id=encounter_id, kind=models.Job.REVIEW2).exists())
        self.assertFalse(models.ProviderRun.objects.filter(encounter_id=encounter_id, service_date=date(1998, 1, 1))
                         .exclude(pk__in=self.installed).exists())

    def setUp(self):
        super().setUp()
        self.installed = []  # the runs the installed revision made with the member's date

    def held_with_the_date_question(self, encounter_id):
        encounter = self.encounter(encounter_id)
        run = encounter.current_assessment.provider_run
        self.assertEqual((run.state, run.scope.get('held')),
                         (models.ProviderRun.NOT_SENT, models.ProviderRun.HELD_MEMBER_DATE_CONFLICT))
        self.assertTrue(self.date_question(encounter_id))

    def test_a_predict_queued_at_the_swap(self):
        encounter_id = self.documented()
        context = self.installed_context(encounter_id, {'service_date': MEMBER})
        self.installed_job(encounter_id, models.Job.PREDICT, context)
        drain()
        self.assert_nothing_sent_with_the_member_date(encounter_id, 1)
        self.held_with_the_date_question(encounter_id)

    def test_resume_of_a_stopped_predict(self):
        encounter_id = self.documented()
        context = self.installed_context(encounter_id, {'service_date': MEMBER})
        self.installed_job(encounter_id, models.Job.PREDICT, context, state=models.Job.CANCELLED)
        self.assertTrue(review.can_resume(self.encounter(encounter_id)))
        self.assertEqual(self.post(f'/api/encounters/{encounter_id}/resume').status_code, 201)
        drain()
        self.assert_nothing_sent_with_the_member_date(encounter_id, 1)
        self.held_with_the_date_question(encounter_id)

    def test_resume_of_a_stopped_assess_of_the_member_dates_answer(self):
        # the installed revision sent the member's date (its documented behaviour) and was stopped before assessing
        encounter_id = self.documented()
        context = self.installed_context(encounter_id, {'service_date': MEMBER})
        run = self.installed_run(encounter_id, MEMBER)
        self.installed.append(run.pk)
        self.installed_job(encounter_id, models.Job.ASSESS, context, run=run, state=models.Job.CANCELLED)
        self.assertEqual(self.post(f'/api/encounters/{encounter_id}/resume').status_code, 201)
        drain()
        self.assert_nothing_sent_with_the_member_date(encounter_id, 2)
        self.held_with_the_date_question(encounter_id)
        self.assertEqual(self.ask(encounter_id).status_code, 409)
        drain()
        self.assertEqual(self.sent(), 2)

    def test_reconciling_the_member_dates_unknown_outcome(self):
        encounter_id = self.documented()
        self.installed_context(encounter_id, {'service_date': MEMBER})
        run = self.installed_run(encounter_id, MEMBER, state=models.ProviderRun.UNKNOWN)
        self.installed.append(run.pk)
        reply = self.post(f'/api/encounters/{encounter_id}/reconcile',
                          {'provider_run_id': str(run.pk), 'note': 'Checked the provider console: nothing billed.'})
        self.assertEqual(reply.status_code, 201, reply.content)
        drain()
        self.assert_nothing_sent_with_the_member_date(encounter_id, 2)
        self.held_with_the_date_question(encounter_id)

    def test_the_stale_sweep_of_a_predict_whose_answer_was_recorded(self):
        # the installed worker sent the member's date, recorded the answer and died before queueing the assess
        encounter_id = self.documented()
        context = self.installed_context(encounter_id, {'service_date': MEMBER})
        started = timezone.now() - timedelta(hours=2)
        self.installed_job(encounter_id, models.Job.PREDICT, context, state=models.Job.RUNNING, started=started)
        self.before_the_stage(encounter_id, started)
        run = self.installed_run(encounter_id, MEMBER, created=started + timedelta(seconds=5))
        self.installed.append(run.pk)
        jobs.mark_stale()
        drain()
        self.assert_nothing_sent_with_the_member_date(encounter_id, 2)
        self.held_with_the_date_question(encounter_id)

    def test_the_stale_sweep_of_a_predict_cut_before_it_sent_then_resume(self):
        encounter_id = self.documented()
        context = self.installed_context(encounter_id, {'service_date': MEMBER})
        started = timezone.now() - timedelta(hours=2)
        self.installed_job(encounter_id, models.Job.PREDICT, context, state=models.Job.RUNNING, started=started)
        self.before_the_stage(encounter_id, started)
        jobs.mark_stale()
        self.assertTrue(review.can_resume(self.encounter(encounter_id)))
        self.assertEqual(self.post(f'/api/encounters/{encounter_id}/resume').status_code, 201)
        drain()
        self.assert_nothing_sent_with_the_member_date(encounter_id, 1)
        self.held_with_the_date_question(encounter_id)

    def test_a_context_change_after_the_upgrade(self):
        encounter_id = self.documented()
        self.installed_context(encounter_id, {'service_date': MEMBER})
        self.set_context(encounter_id, setting='asc')
        drain()
        self.assert_nothing_sent_with_the_member_date(encounter_id, 1)
        self.held_with_the_date_question(encounter_id)

    def test_a_reviewers_second_review_on_the_earlier_context(self):
        encounter_id = self.documented()
        context = self.installed_context(encounter_id, {'service_date': MEMBER})
        self.assertEqual(self.ask(encounter_id).status_code, 409)
        encounter = self.encounter(encounter_id)
        job = jobs.enqueue(models.Job.REVIEW2, encounter=encounter, revision=encounter.current_revision,
                           context=context, provider_run=encounter.current_assessment.provider_run,
                           key='review2:earlier-context', requested_by=self.reviewer)
        drain()
        job.refresh_from_db()
        self.assertIn('nothing was sent', job.result.get('skipped', ''))
        self.assertEqual(self.sent(), 1)

    def test_control_a_member_date_for_an_undated_document_is_sent_once(self):
        undated = REPORT.replace('Date of service: 2026-10-16\n', '')
        encounter_id = self.create(undated)
        drain()
        context = self.installed_context(encounter_id, {'service_date': '2026-10-16'})
        self.installed_job(encounter_id, models.Job.PREDICT, context)
        drain()
        self.assertEqual(self.sent(), 2)
        self.assertEqual(self.dates_sent(), ['Date of service: 2026-10-16'])
        encounter = self.encounter(encounter_id)
        self.assertEqual(encounter.current_context.facts['service_date']['origin'], 'user')
        self.assertEqual(encounter.current_assessment.provider_run.service_date, DOCUMENTED)


# --- sends-2 / context-2: the paid second review stays with the request it answered -----------------------------------

@override_settings(**LIVE)
class SecondReviewAcrossReuseTests(Base):
    """A date round trip (a member conflict cleared, or a member date changed and changed back) reuses the retained
    primary result; the second review made for that request on this revision and date is read again, whichever run
    carries the primary answer - never dropped from the decision set, never asked for twice."""

    def round_trip(self, encounter_id, values=(MEMBER, '')):
        for value in values:
            self.set_context(encounter_id, service_date=value)
            drain()

    def assert_kept(self, encounter_id, sends):
        self.assertEqual(self.sent(), sends)
        self.assertEqual(self.selected(encounter_id), {'45385': 'primary', '45380': 'second_review'})
        self.assertEqual(self.unresolved(encounter_id), [])
        self.assertIsNotNone(self.encounter(encounter_id).current_assessment.second_run_id)
        self.assertEqual(self.ask(encounter_id).status_code, 409)
        drain()
        self.assertEqual(self.sent(), sends)

    def test_clearing_a_member_date_conflict(self):
        encounter_id = self.create()
        drain()
        self.assertEqual(self.ask(encounter_id).status_code, 201)
        drain()
        self.round_trip(encounter_id)
        self.assert_kept(encounter_id, 2)

    def test_an_undated_report_whose_member_date_goes_and_comes_back(self):
        undated = REPORT.replace('Date of service: 2026-10-16\n', '')
        encounter_id = self.create(undated, service_date='2026-10-16')
        drain()
        self.assertEqual(self.ask(encounter_id).status_code, 201)
        drain()
        self.round_trip(encounter_id, ('2026-10-17', '2026-10-16'))
        self.assert_kept(encounter_id, 3)  # the primary for 2026-10-17 is a new request; nothing else is

    def test_a_second_review_made_for_a_reused_primary(self):
        # the same report twice in one workspace: the second's primary reuses the first's; its reviewer asks
        self.create()
        drain()
        twin = self.create()
        drain()
        self.assertEqual(self.sent(), 1)
        self.assertEqual(self.ask(twin).status_code, 201)
        drain()
        self.assertEqual(self.sent(), 2)
        self.round_trip(twin)
        self.assert_kept(twin, 2)

    def test_a_reused_second_review_made_for_a_reused_primary(self):
        first = self.create()
        drain()
        self.assertEqual(self.ask(first).status_code, 201)
        drain()
        twin = self.create()
        drain()
        self.assertEqual(self.ask(twin).status_code, 201)
        drain()
        self.assertEqual(self.sent(), 2)
        self.round_trip(twin)
        self.assert_kept(twin, 2)
        self.round_trip(twin, ('2026-10-22', '2026-10-16'))  # a member date that agrees with the document's
        self.assert_kept(twin, 2)

    def test_controls_another_answer_to_the_same_request_or_an_unreadable_scope_never_reads_it(self):
        encounter_id = self.create()
        drain()
        self.assertEqual(self.ask(encounter_id).status_code, 201)
        drain()
        encounter = self.encounter(encounter_id)
        revision, primary = encounter.current_revision, encounter.current_assessment.provider_run
        second = models.ProviderRun.objects.get(encounter_id=encounter_id, purpose='second_review')
        self.assertEqual(jobs._second_run_for(revision, primary).pk, second.pk)
        other = models.ProviderRun.objects.get(pk=primary.pk)  # the same request answered otherwise
        other.pk, other.run_identity, other.response_sha256 = None, uuid4(), '0' * 64
        other.save()
        self.assertIsNone(jobs._second_run_for(revision, other))
        models.ProviderRun.objects.filter(pk=second.pk).update(scope={**second.scope, 'primary_run': 'not-a-run'})
        self.assertIsNone(jobs._second_run_for(revision, primary))

    def test_control_a_second_review_for_another_date_is_never_read(self):
        undated = REPORT.replace('Date of service: 2026-10-16\n', '')
        encounter_id = self.create(undated, service_date='2026-10-16')
        drain()
        self.assertEqual(self.ask(encounter_id).status_code, 201)
        drain()
        self.round_trip(encounter_id, ('2026-10-17',))
        self.assertEqual(self.sent(), 3)
        assessment = self.encounter(encounter_id).current_assessment
        self.assertIsNone(assessment.second_run_id)
        self.assertNotIn('second_review', self.selected(encounter_id).values())


# --- migrate-2: a member setting the installed revision kept is never read as the setting -----------------------------

@override_settings(**LIVE)
class PreUpgradeSettingTests(Base):
    def test_a_reassess_queued_at_the_swap_holds_the_visit_and_asks(self):
        self.provider.first = [VISIT]
        encounter_id = self.create(OFFICE_NOTE)
        drain()
        self.assertEqual(self.sent(), 1)
        values = {'setting': 'hospital_outpatient', 'billing_context': 'facility'}
        context = self.installed_context(encounter_id, values)
        run = self.encounter(encounter_id).current_assessment.provider_run
        self.installed_job(encounter_id, models.Job.ASSESS, context, run=run)
        drain()
        self.assertEqual(self.sent(), 1)
        encounter = self.encounter(encounter_id)
        self.assertNotEqual(encounter.current_context.version, EARLIER_VERSION)
        self.assertEqual(encounter.current_context.facts['setting']['origin'], 'conflict')
        proposal = encounter.current_assessment.proposals.get(code='99213')
        self.assertEqual(proposal.status, 'needs_clarification')
        self.assertTrue([q for q in self.detail(encounter_id)['clarifications'] if 'place of service' in q['question']])


# --- migrate-5: nothing is sent at the swap that no member asked for --------------------------------------------------

@override_settings(**LIVE)
class NothingSentAtTheSwapTests(Base):
    """Work the installed revision left queued, or stranded, at the swap is finished under the current rules without
    a request no member asked for: the assessment queues no second review (8985dde42), and a context the installed
    revision recorded is remade (WIP 8i) - but when the request the remade context makes differs from the one the
    installed revision sent (the current rules read a date it could not), a stage that never sends (an assess, or the
    stale-stage sweep's settlement of a predict) leaves that request for a member: the encounter offers Resume."""

    def installed_upload(self, text, *, read_date=True):
        """An upload the installed revision extracted and analysed (its gi-context@1 row, without member values; with
        ``read_date`` False it read no service date), nothing assessed yet."""
        from studio.types import to_jsonable
        encounter = f.encounter(self.ws, self.reviewer)
        revision = f.pasted_revision(encounter, self.reviewer, text)
        facts = {name: to_jsonable(fact) for name, fact in gi_context.extract_context(revision.text).items()}
        if not read_date:
            facts['service_date'] = {'name': 'service_date', 'value': None, 'origin': 'missing', 'evidence': [],
                                     'note': gi_context.MISSING_NOTES['service_date']}
        context = models.EncounterContext.objects.create(encounter=encounter, revision=revision, facts=facts,
                                                         user_values={}, version=EARLIER_VERSION, sha256='0' * 64)
        encounter.current_context = context
        encounter.save(update_fields=['current_context', 'updated_at'])
        return str(encounter.pk), context

    def assert_left_for_a_member(self, encounter_id, sends):
        self.assertEqual(self.sent(), sends, [r.contexts[1:] for r in self.provider.requests])
        encounter = self.encounter(encounter_id)
        self.assertNotEqual(encounter.current_context.version, EARLIER_VERSION)
        self.assertEqual(encounter.state, 'stopped')
        self.assertTrue(review.can_resume(encounter))
        latest = review.latest_job(encounter)
        self.assertEqual((latest.kind, latest.state, latest.context_id),
                         (models.Job.PREDICT, models.Job.CANCELLED, encounter.current_context_id))
        self.assertEqual(latest.error, jobs.REMADE_REQUEST_MESSAGE)
        self.assertFalse(self.detail(encounter_id)['pipeline']['stopped_by_member'])  # the system's stop, said so
        reply = self.post(f'/api/encounters/{encounter_id}/resume')  # a member asks: the one request is sent
        self.assertEqual(reply.status_code, 201, reply.content)
        drain()
        self.assertEqual(self.sent(), sends + 1)
        self.assertEqual(self.provider.requests[-1].contexts[1:], ('Date of service: 2026-10-16',))
        encounter = self.encounter(encounter_id)
        self.assertEqual(encounter.current_assessment.provider_run.service_date, DOCUMENTED)
        self.assertNotEqual(encounter.state, 'stopped')

    def test_an_assess_queued_at_the_swap_for_a_date_the_installed_revision_could_not_read(self):
        encounter_id, context = self.installed_upload(REPORT_TABLE_DATE, read_date=False)
        run = self.installed_run(encounter_id, None)  # the installed revision's request, sent without a date
        self.installed_job(encounter_id, models.Job.ASSESS, context, run=run)
        drain()
        self.assert_left_for_a_member(encounter_id, 1)

    def test_the_stale_sweep_of_a_predict_the_installed_worker_finished(self):
        encounter_id, context = self.installed_upload(REPORT_TABLE_DATE, read_date=False)
        started = timezone.now() - timedelta(hours=2)
        self.installed_job(encounter_id, models.Job.PREDICT, context, state=models.Job.RUNNING, started=started)
        self.installed_run(encounter_id, None, created=started + timedelta(seconds=5))
        jobs.mark_stale()
        drain()
        self.assert_left_for_a_member(encounter_id, 1)

    def test_a_resumed_assess_of_the_installed_revisions_answer(self):
        encounter_id, context = self.installed_upload(REPORT_TABLE_DATE, read_date=False)
        run = self.installed_run(encounter_id, None)
        self.installed_job(encounter_id, models.Job.ASSESS, context, run=run, state=models.Job.CANCELLED)
        self.assertEqual(self.post(f'/api/encounters/{encounter_id}/resume').status_code, 201)
        drain()
        self.assert_left_for_a_member(encounter_id, 1)

    def test_controls_a_predict_queued_at_the_swap_sends_its_one_request_for_the_remade_context(self):
        encounter_id, context = self.installed_upload(REPORT_TABLE_DATE, read_date=False)
        self.installed_job(encounter_id, models.Job.PREDICT, context)  # the upload asked for this request
        drain()
        self.assertEqual(self.sent(), 1)
        self.assertEqual(self.dates_sent(), ['Date of service: 2026-10-16'])
        self.assertNotEqual(self.encounter(encounter_id).state, 'stopped')

    def test_controls_an_assess_whose_request_is_unchanged_reassesses_and_asks_no_second_review(self):
        encounter_id, context = self.installed_upload(REPORT)
        run = self.installed_run(encounter_id, '2026-10-16')
        self.installed_job(encounter_id, models.Job.ASSESS, context, run=run)
        drain()
        self.assertEqual(self.sent(), 1)
        encounter = self.encounter(encounter_id)
        self.assertEqual(encounter.current_assessment.provider_run_id, run.pk)
        self.assertNotEqual(encounter.state, 'stopped')
        self.assertTrue(self.unresolved(encounter_id))  # the biopsy: offered to a reviewer, never sent by itself
        self.assertTrue(self.detail(encounter_id)['second_review']['available'])
        self.assertFalse(models.Job.objects.filter(encounter_id=encounter_id, kind=models.Job.REVIEW2).exists())

    def test_controls_the_stale_sweep_of_a_finished_predict_asks_no_second_review(self):
        encounter_id, context = self.installed_upload(REPORT)
        started = timezone.now() - timedelta(hours=2)
        self.installed_job(encounter_id, models.Job.PREDICT, context, state=models.Job.RUNNING, started=started)
        run = self.installed_run(encounter_id, '2026-10-16', created=started + timedelta(seconds=5))
        jobs.mark_stale()
        drain()
        self.assertEqual(self.sent(), 1)
        self.assertEqual(self.encounter(encounter_id).current_assessment.provider_run_id, run.pk)
        self.assertFalse(models.Job.objects.filter(encounter_id=encounter_id, kind=models.Job.REVIEW2).exists())


# --- skeptic:1 on migrate-5's repair: the upgrade stops only where it would send, and says what is recorded ----------

# The table-dated report with a long fictional handout written with a three-byte UTF-8 character: a legal paste (under
# MAX_PASTE_CHARS characters) whose request is over PROVIDER_MAX_REQUEST_BYTES (the body is encoded with
# ensure_ascii=False, as corti.build_coding_request encodes it).
OVERSIZE = REPORT_TABLE_DATE + '\nPatient handout (fictional):\n' + '\n'.join(['…' * 100] * 1800) + '\n'


class SizedProvider(Provider):
    """The stand-in building each request exactly as the live adapter does (corti.build_coding_request): a request over
    PROVIDER_MAX_REQUEST_BYTES is refused (ProviderUnavailable), never truncated or sent."""

    def build_request(self, text, service_date):
        return corti.build_coding_request(self.name, self.adapter_version, text, service_date,
                                          settings.PROVIDER_MAX_REQUEST_BYTES)


@override_settings(**LIVE)
class UpgradeStopsOnlyWhereItWouldSendTests(Base):
    """skeptic:1 (on bc7c128b1): after an upgrade's remake at a stage that never sends, the predict was recorded as
    stopped - "the request they make for it differs from the one sent before. Resume to send it." - whatever was
    recorded: for a request the installed revision could not build (nothing sent; Resume then sent nothing either), for
    no run at all (the installed pair ran with the provider disabled), and while an unknown outcome blocked every send
    (the encounter read 'stopped', not 'provider_unknown'). Nothing may be sent by the upgrade itself, and the screen
    must say what is recorded: the predict runs as before and stops only where it would send, worded from the run in
    use."""

    provider_class = SizedProvider
    installed_upload = NothingSentAtTheSwapTests.installed_upload

    def installed_not_sent(self, encounter_id):
        """The run 057a7d39's stage_predict records when the request cannot be built: no request, nothing sent."""
        encounter = self.encounter(encounter_id)
        revision = encounter.current_revision
        with self.assertRaises(ProviderUnavailable) as refused:
            self.provider.build_request(revision.text, None)
        return models.ProviderRun.objects.create(
            encounter=encounter, revision=revision, provider=self.provider.name,
            adapter_version=self.provider.adapter_version, request_sha256='', request_body={}, contexts=[],
            state=models.ProviderRun.NOT_SENT, error=str(refused.exception),
            authorization_ref=LIVE['AUTHORIZATION_REF'], requested_by=self.reviewer, service_date=None,
            finished_at=timezone.now())

    def upgrade_stages(self, encounter_id):
        return [s for s in self.detail(encounter_id)['pipeline']['stages'] if 'after an upgrade' in s['error']]

    def assert_recorded_as_not_sent(self, encounter_id):
        """As without the upgrade: the predict records why nothing could be built, and the screen says that."""
        self.assertEqual(self.sent(), 0)
        encounter = self.encounter(encounter_id)
        self.assertNotEqual(encounter.current_context.version, EARLIER_VERSION)
        self.assertEqual(self.upgrade_stages(encounter_id), [])
        self.assertEqual(encounter.state, 'provider_failed')
        self.assertFalse(review.can_resume(encounter))
        runs = models.ProviderRun.objects.filter(encounter_id=encounter_id)
        self.assertFalse(runs.filter(sent=True).exists())
        latest = runs.order_by('-created_at').first()
        self.assertEqual((latest.state, latest.service_date), (models.ProviderRun.NOT_SENT, DOCUMENTED))
        self.assertIn('nothing was truncated or sent', latest.error)
        self.assertEqual(encounter.current_assessment.provider_run_id, latest.pk)

    def test_a_request_the_current_rules_cannot_build_either_is_recorded_never_stopped(self):
        self.assertLessEqual(len(OVERSIZE), settings.MAX_PASTE_CHARS)
        encounter_id, context = self.installed_upload(OVERSIZE, read_date=False)
        run = self.installed_not_sent(encounter_id)
        self.installed_job(encounter_id, models.Job.ASSESS, context, run=run)  # its assess, queued at the swap
        drain()
        self.assert_recorded_as_not_sent(encounter_id)

    def test_a_resumed_assess_of_a_request_that_could_not_be_built(self):
        encounter_id, context = self.installed_upload(OVERSIZE, read_date=False)
        run = self.installed_not_sent(encounter_id)
        # cancelled before the install (a Stop, a queue expiry or the restart sweep); a reviewer resumes it after
        self.installed_job(encounter_id, models.Job.ASSESS, context, run=run, state=models.Job.CANCELLED)
        self.assertEqual(self.post(f'/api/encounters/{encounter_id}/resume').status_code, 201)
        drain()
        self.assert_recorded_as_not_sent(encounter_id)

    def test_with_no_request_before_the_stop_never_says_one_was_sent(self):
        # the installed pair ran with the provider disabled: its assess carries no run at all
        encounter_id, context = self.installed_upload(REPORT_TABLE_DATE, read_date=False)
        self.installed_job(encounter_id, models.Job.ASSESS, context, run=None)
        drain()
        self.assertEqual(self.sent(), 0)
        encounter = self.encounter(encounter_id)
        self.assertEqual(encounter.state, 'stopped')
        self.assertTrue(review.can_resume(encounter))
        latest = review.latest_job(encounter)
        self.assertEqual((latest.kind, latest.state), (models.Job.PREDICT, models.Job.CANCELLED))
        self.assertNotIn('sent before', latest.error)
        self.assertEqual(latest.error, jobs.REMADE_UNANSWERED_MESSAGE)
        self.assertFalse(self.detail(encounter_id)['pipeline']['stopped_by_member'])
        self.assertEqual(self.post(f'/api/encounters/{encounter_id}/resume').status_code, 201)
        drain()
        self.assertEqual(self.dates_sent(), ['Date of service: 2026-10-16'])  # a member's Resume sends it, once
        self.assertEqual(self.encounter(encounter_id).current_assessment.provider_run.service_date, DOCUMENTED)

    def test_a_request_built_but_never_sent_before_is_never_said_to_be_sent(self):
        # the installed revision built its request and the exchange refused it before sending (outcome not_sent)
        encounter_id, context = self.installed_upload(REPORT_TABLE_DATE, read_date=False)
        run = self.installed_run(encounter_id, None, state=models.ProviderRun.NOT_SENT)
        self.provider.requests.pop()  # nothing reached the provider
        models.ProviderRun.objects.filter(pk=run.pk).update(
            sent=False, error='The send deadline must be a positive number of seconds; nothing was sent.')
        self.installed_job(encounter_id, models.Job.ASSESS, context, run=run)
        drain()
        self.assertEqual(self.sent(), 0)
        latest = review.latest_job(self.encounter(encounter_id))
        self.assertEqual((latest.kind, latest.state, latest.error),
                         (models.Job.PREDICT, models.Job.CANCELLED, jobs.REMADE_UNANSWERED_MESSAGE))

    def test_a_request_sent_by_another_adapter_version_is_said_to_differ(self):
        # the run in use carries the same body sent by an earlier adapter version: another request, as _run_answers
        # and the retained-answer lookup read it, so the stop says the request differs from the one sent before
        encounter_id, context = self.installed_upload(REPORT)
        run = self.installed_run(encounter_id, '2026-10-16')
        models.ProviderRun.objects.filter(pk=run.pk).update(adapter_version='corti-coding-v1@cptstudio-0')
        self.installed_job(encounter_id, models.Job.ASSESS, context, run=run)
        drain()
        self.assertEqual(self.sent(), 1)  # the installed revision's own request only
        latest = review.latest_job(self.encounter(encounter_id))
        self.assertEqual((latest.kind, latest.state, latest.error),
                         (models.Job.PREDICT, models.Job.CANCELLED, jobs.REMADE_REQUEST_MESSAGE))

    def test_with_the_provider_disabled_now_nothing_is_stopped(self):
        encounter_id, context = self.installed_upload(REPORT_TABLE_DATE, read_date=False)
        self.installed_job(encounter_id, models.Job.ASSESS, context, run=None)
        with mock.patch('studio.jobs.get_provider', return_value=None):
            drain()
        self.assertEqual(self.sent(), 0)
        encounter = self.encounter(encounter_id)
        self.assertEqual(self.upgrade_stages(encounter_id), [])
        self.assertEqual(encounter.state, 'provider_not_run')
        self.assertFalse(review.can_resume(encounter))

    def test_an_unknown_outcome_reads_as_unknown_and_no_resume_is_offered(self):
        encounter_id, context = self.installed_upload(REPORT_TABLE_DATE, read_date=False)
        run = self.installed_run(encounter_id, None, state=models.ProviderRun.UNKNOWN)
        self.installed_job(encounter_id, models.Job.ASSESS, context, run=run)
        drain()
        self.assertEqual(self.sent(), 1)  # the installed revision's own request only
        encounter = self.encounter(encounter_id)
        self.assertEqual(self.upgrade_stages(encounter_id), [])
        self.assertEqual(encounter.state, 'provider_unknown')
        self.assertFalse(review.can_resume(encounter))
        reply = self.post(f'/api/encounters/{encounter_id}/reconcile',
                          {'provider_run_id': str(run.pk), 'note': 'Checked the provider console: nothing billed.'})
        self.assertEqual(reply.status_code, 201, reply.content)
        drain()
        self.assertEqual(self.dates_sent(), ['Date of service: 2026-10-16'])  # the reconciliation's one attempt
        self.assertEqual(self.sent(), 2)

    def test_a_retained_answer_to_the_remade_request_is_reused_never_stopped(self):
        answered = self.create(REPORT_TABLE_DATE)  # under the current rules the dated request is sent and answered
        drain()
        self.assertEqual(self.dates_sent(), ['Date of service: 2026-10-16'])
        encounter_id, context = self.installed_upload(REPORT_TABLE_DATE, read_date=False)
        run = self.installed_run(encounter_id, None)
        self.installed_job(encounter_id, models.Job.ASSESS, context, run=run)
        drain()
        self.assertEqual(self.sent(), 2)  # nothing new
        encounter = self.encounter(encounter_id)
        self.assertEqual(self.upgrade_stages(encounter_id), [])
        self.assertNotEqual(encounter.state, 'stopped')
        used = encounter.current_assessment.provider_run
        self.assertEqual((used.sent, used.service_date, str(used.reused_from.encounter_id)),
                         (False, DOCUMENTED, answered))

    def test_control_an_undo_closes_the_upgrades_queued_predict_before_the_installed_pair_returns(self):
        # rollback safety: the installed revision's worker would run this predict as any other (it does not know the
        # upgrade's stop), so the installer's CLOSE_STAGES must close it, as it closes every stage the new pair opened
        from tests.test_repairs_r1_m import install, run_app_script
        encounter_id, context = self.installed_upload(REPORT_TABLE_DATE, read_date=False)
        self.installed_job(encounter_id, models.Job.ASSESS, context, run=self.installed_run(encounter_id, None))
        swap = timezone.now()
        jobs.run_job(jobs.claim_next())  # the new worker runs the installed revision's assess, and no more
        queued = models.Job.objects.get(encounter_id=encounter_id, kind=models.Job.PREDICT)
        self.assertEqual(queued.state, models.Job.QUEUED)
        note = 'Closed by the installer: undone (revision aaaaaaaaaaaa), so this stage will not run.'
        answer = run_app_script(install.CLOSE_STAGES, {'since': swap.isoformat(), 'note': note})
        self.assertEqual((answer['closed'], answer['kinds']), (1, ['predict']))
        queued.refresh_from_db()
        self.assertEqual((queued.state, queued.error), (models.Job.FAILED, note))
        self.assertFalse(review.can_resume(self.encounter(encounter_id)))
        drain()
        self.assertEqual(self.sent(), 1)  # the installed revision's own request only


# --- the reviewer-requested second review (8985dde42): never sent twice, never sent when it should not be -------------

@override_settings(**LIVE)
class ReviewerSecondReviewTests(Base):
    def processed(self, text=REPORT, **extra):
        encounter_id = self.create(text, **extra)
        drain()
        self.assertEqual(self.sent(), 1)
        return encounter_id

    def test_two_requests_before_it_runs_queue_one_review(self):
        encounter_id = self.processed()
        other = Client(enforce_csrf_checks=False)
        other.force_login(f.member(self.ws, f.user('reviewer2')))
        self.assertEqual(self.ask(encounter_id).status_code, 201)
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(other.post(f'/api/encounters/{encounter_id}/second-review').status_code, 409)
        self.assertEqual(models.Job.objects.filter(encounter_id=encounter_id, kind=models.Job.REVIEW2).count(), 1)
        drain()
        self.assertEqual(self.sent(), 2)

    def test_a_request_then_a_context_change_waits_for_it(self):
        encounter_id = self.processed()
        self.assertEqual(self.ask(encounter_id).status_code, 201)
        reply = self.post(f'/api/encounters/{encounter_id}/context', {'setting': 'asc'})
        self.assertEqual(reply.status_code, 409, reply.content)
        drain()
        self.assertEqual(self.sent(), 2)

    def test_a_stopped_request_is_never_sent_after_the_context_changed(self):
        encounter_id = self.processed()
        self.assertEqual(self.ask(encounter_id).status_code, 201)
        self.assertEqual(self.post(f'/api/encounters/{encounter_id}/stop').status_code, 200)
        self.set_context(encounter_id, setting='asc')
        drain()
        self.assertEqual(self.sent(), 1)
        self.assertEqual(self.post(f'/api/encounters/{encounter_id}/resume').status_code, 409)
        self.assertEqual(self.ask(encounter_id).status_code, 201)  # the new assessment: a reviewer asks again
        drain()
        self.assertEqual(self.sent(), 2)
        self.assertEqual(self.ask(encounter_id).status_code, 409)
        drain()
        self.assertEqual(self.sent(), 2)

    def test_a_stopped_request_resumed_after_a_member_date_conflict_is_never_sent(self):
        encounter_id = self.processed()
        self.assertEqual(self.ask(encounter_id).status_code, 201)
        self.assertEqual(self.post(f'/api/encounters/{encounter_id}/stop').status_code, 200)
        self.set_context(encounter_id, service_date=MEMBER)
        drain()
        self.assertEqual(self.post(f'/api/encounters/{encounter_id}/resume').status_code, 409)
        self.assertEqual(self.ask(encounter_id).status_code, 409)  # no agreed date
        drain()
        self.assertEqual(self.sent(), 1)
        self.assertFalse(models.ProviderRun.objects.filter(encounter_id=encounter_id, purpose='second_review').exists())

    def test_a_request_is_refused_while_an_unknown_outcome_stands(self):
        undated = REPORT.replace('Date of service: 2026-10-16\n', '')
        encounter_id = self.processed(undated, service_date='2026-10-16')
        self.provider.outcomes = ['unknown']
        self.set_context(encounter_id, service_date='2026-10-17')
        drain()
        self.assertEqual(self.sent(), 2)
        self.set_context(encounter_id, service_date='2026-10-16')  # the retained 2026-10-16 answer is reused
        drain()
        self.assertEqual(self.sent(), 2)
        reply = self.ask(encounter_id)
        self.assertEqual(reply.status_code, 409, reply.content)
        self.assertIn('unknown outcome', reply.json()['error'])
        drain()
        self.assertEqual(self.sent(), 2)

    def test_a_request_on_a_member_date_conflict_is_refused_and_nothing_is_queued(self):
        # migrate-4 beside the reviewer's request: a conflicted context never gets a stage that can send
        encounter_id = self.processed()
        self.set_context(encounter_id, service_date=MEMBER)
        drain()
        reply = self.ask(encounter_id)
        self.assertEqual(reply.status_code, 409, reply.content)
        self.assertFalse(models.Job.objects.filter(encounter_id=encounter_id, kind__in=(models.Job.REVIEW2,
                                                                                         models.Job.PREDICT),
                                                   context=self.encounter(encounter_id).current_context).exists())
        self.assertEqual(self.sent(), 1)


# --- migrate-3: the reviewer's second review never reaches a worker that cannot run it --------------------------------

@override_settings(**LIVE)
class UndoClosesTheReviewersSecondReviewTests(Base):
    def test_a_second_review_asked_on_the_new_pair_is_closed_before_the_installed_pair_returns(self):
        from tests.test_repairs_r1_m import install, run_app_script
        encounter_id = self.create()
        drain()
        swap = timezone.now()
        self.assertEqual(self.ask(encounter_id).status_code, 201)
        queued = models.Job.objects.get(encounter_id=encounter_id, kind=models.Job.REVIEW2)
        note = 'Closed by the installer: undone (revision aaaaaaaaaaaa), so this stage will not run.'
        answer = run_app_script(install.CLOSE_STAGES, {'since': swap.isoformat(), 'note': note})
        self.assertEqual((answer['closed'], answer['kinds']), (1, ['review2']))
        queued.refresh_from_db()
        self.assertEqual((queued.state, queued.error), (models.Job.FAILED, note))
        encounter = self.encounter(encounter_id)
        self.assertFalse(review.can_resume(encounter))
        with mock.patch.object(jobs, 'STAGES', {k: v for k, v in jobs.STAGES.items() if k != models.Job.REVIEW2}):
            self.assertEqual(run_app_script(install.UNRUNNABLE_STAGES, {})['stuck'], 0)  # as 057a7d39 reads it
        drain()
        self.assertEqual(self.sent(), 1)
