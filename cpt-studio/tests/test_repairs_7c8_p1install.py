"""Refutation phase 1 over b611b557a, cluster P1INSTALL: rollback safety (must-fix class 5, and class 1 through a
rollback). Synthetic data only; no network: the provider is an in-process stand-in with the live adapter's name and
version, and the installer's in-image scripts run here, on this test database, exactly as `manage shell -c` runs them.

Every document opens with the synthetic banner.

- security-0: rollback-app closed only the stages created since the CURRENT pair was created, so a second review a
  member stopped under an earlier pair of a revision that runs it outlived the window; the installed revision 057a7d39
  then offered its Resume and its worker ended on the unknown stage kind (KeyError, a crash loop).
- migrate-0: the failure path (and rollback-app before the '*-previous' recovery) put 057a7d39 back over a context this
  revision had remade into a member date conflict while a provider outcome was unknown; 057a7d39's reconcile then
  requested that context, which it reads as having no date, and sent a request without one.
- migrate-1: after any rollback, a hold this revision recorded (nothing sent: a member date conflict) became 057a7d39's
  run in use, so a member's metadata save there re-sent the byte-identical request that had FAILED.
- migrate-2: the upgrade never recomputed the stored list state, so an encounter whose provider outcome 057a7d39 left
  unknown (and unreconciled) stayed 'Reviewed' and off the review queue under this revision's rule.

The round-7c8 skeptic of that repair (cross-revision probes with 057a7d398's real code):
- sk:0: the two revisions read a report's service date differently (its title's date here, a labelled outside
  procedure's date there); 057a7d39's request for its own reading had FAILED, this revision's succeeded and became
  057a7d39's run in use, and nothing was named - so its next metadata save re-sent the byte-identical FAILED request.
- sk:1: a hold over a SUCCEEDED request, while the member's date (which 057a7d39 requests as the date) is an older
  request that FAILED: not named either (only the newest primary was compared), and the setting save re-sent it.
- sk:2: the migrate-2 refusal also refused a same-revision `app` re-run (a provider-mode switch in an incident) and the
  reinstall the failure path's receipt asks for, until a member reconciled on the running web - a released, paid send.
- sk:3: a code only the bounded second review selected left the decision set at 057a7d39's next re-assessment,
  without a reviewer's decision, and nothing refused the rollback.
"""
import datetime as dt
import hashlib
from types import SimpleNamespace
from unittest import mock

from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from studio import jobs, models, review
from studio.types import RawExchange
from tests.support import factories as f
from tests.test_pipeline_api import OFFICE_NOTE, drain
from tests.test_repairs_r1_m import NEW_REVISION, OLD_REVISION, DockerWorld, install, run_app_script
from tests.test_services_second_review import LIVE, REPORT, TwoPassProvider, response

VISIT = ('99213', 'Total time on the date of the encounter was 24 minutes.')
SNARE = ('45385', 'was removed with a cold snare')
BIOPSY = ('45380', 'was sampled with cold biopsy forceps')
UNDATED_NOTE = OFFICE_NOTE.replace('Date of service: 2026-10-20\n\n', '')
MEMBER_CONFLICT = '2026-09-01'  # differs from OFFICE_NOTE's documented 2026-10-20
# sk:0: the installed revision 057a7d39 can read a document's service date otherwise than this revision (the skeptic's
# probe a_dates proved it with its real code: a report's title gave this revision 2026-10-14, a labelled outside
# procedure date gave 057a7d39 2026-09-03). The tests below build 057a7d39's rows with such a reading of OFFICE_NOTE
# (whose documented 2026-10-20 this revision reads), so they do not depend on this revision's reading of a contested
# document - which the CONTEXT cluster changes.
INSTALLED_READING = '2026-09-03'
NOTE = 'Closed by the installer: undone (revision aaaaaaaaaaaa), so this stage will not run.'
OLD_IMAGE, NEW_IMAGE = 'sha256:' + 'b' * 64, 'sha256:' + 'a' * 64


class Provider(TwoPassProvider):
    """The live adapter's name and version, each outcome scripted ('failed': the provider answered HTTP 500); a
    response names only the quotes the request's own text contains."""

    def send(self, request, *, deadline_s):
        if self.outcomes and self.outcomes[0] == 'failed':
            self.outcomes.pop(0)
            self.requests.append(request)
            data = b'{"error":"synthetic internal server error"}'
            return RawExchange(outcome='failed', sent=True, http_status=500, response_bytes=data,
                               response_sha256=hashlib.sha256(data).hexdigest(),
                               error='HTTP 500 from the provider (synthetic).')
        first, later = self.first, self.later
        self.first = [q for q in first if q[1] in request.contexts[0]]
        self.later = [q for q in later if q[1] in request.contexts[0]]
        try:
            return super().send(request, deadline_s=deadline_s)
        finally:
            self.first, self.later = first, later


@override_settings(**LIVE)
class Base(TestCase):
    def setUp(self):
        self.ws = f.workspace()
        self.reviewer = f.member(self.ws, f.user('reviewer'))
        self.client = Client(enforce_csrf_checks=False)
        self.client.force_login(self.reviewer)
        self.provider = Provider(first=[VISIT, SNARE], later=[VISIT, SNARE, BIOPSY])
        patcher = mock.patch('studio.jobs.get_provider', return_value=self.provider)
        patcher.start()
        self.addCleanup(patcher.stop)

    def create(self, text, **extra):
        with self.captureOnCommitCallbacks(execute=True):
            reply = self.client.post('/api/encounters', {'text': text, 'synthetic_attestation': 'yes', **extra})
        self.assertEqual(reply.status_code, 201, reply.content)
        return reply.json()['id']

    def post(self, path, data=None):
        import json
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(path, data=json.dumps(data or {}), content_type='application/json')

    def set_context(self, encounter_id, **values):
        reply = self.post(f'/api/encounters/{encounter_id}/context', values)
        self.assertEqual(reply.status_code, 201, reply.content)
        drain()

    def sent(self):
        return len(self.provider.requests)

    def encounter(self, encounter_id):
        return models.Encounter.objects.get(pk=encounter_id)

    def hazards(self):
        return run_app_script(install.UNDO_HAZARDS_READ, {})['hazards']

    def close(self, since, kinds=None):
        """CLOSE_STAGES for a pair undone since ``since``, the next worker running ``kinds`` (default: the kinds every
        revision's worker runs, 057a7d39's STAGES)."""
        kinds = list(install.COMMON_STAGE_KINDS if kinds is None else kinds)
        return run_app_script(install.CLOSE_STAGES, {'since': since.isoformat(), 'note': NOTE, 'kinds': kinds})

    def runs(self, encounter_id):
        return list(models.ProviderRun.objects.filter(encounter_id=encounter_id).order_by('created_at'))

    def second_review_codes(self, encounter_id):
        """(code, bucket) of every proposal of the current assessment that only the bounded second review selected."""
        assessment = self.encounter(encounter_id).current_assessment
        return sorted((p.code, p.bucket) for p in assessment.proposals.all()
                      if (p.support or {}).get('origin') == 'second_review' and p.bucket != models.Proposal.ALTERNATIVE)

    def addendum(self, encounter_id):
        """An addendum on this revision's web: a newer revision, processed (its own request, or its hold)."""
        reply = self.post(f'/api/encounters/{encounter_id}/addenda',
                          {'text': 'Addendum (synthetic): no change to the plan.', 'synthetic_attestation': 'yes'})
        self.assertEqual(reply.status_code, 201, reply.content)
        drain()

    def installed_request(self, day, *, member, text=OFFICE_NOTE, state=models.ProviderRun.FAILED, encounter=None):
        """The rows the installed revision 057a7d39 leaves when it requests ``day`` for ``text``: its gi-context@1 row
        (``day`` as the member's value, kept as plain metadata when ``member``, else as its own reading of the
        document's date), the routing it made, and its request carrying that date, which the provider answered with
        HTTP 500 (FAILED) or answered (SUCCEEDED). With ``encounter``, a further request of that encounter's current
        revision (the member changed the date there). Returns (encounter id, run)."""
        from datetime import date

        from studio.gi import context as gi_context
        from studio.types import to_jsonable
        if encounter is None:
            encounter = f.encounter(self.ws, self.reviewer)
            revision = f.pasted_revision(encounter, self.reviewer, text)
        else:
            encounter = self.encounter(encounter)
            revision = encounter.current_revision
        when = date.fromisoformat(day)
        facts = {name: to_jsonable(fact) for name, fact in gi_context.extract_context(revision.text).items()}
        facts['service_date'] = {'name': 'service_date', 'value': day, 'origin': 'user' if member else 'document',
                                 'evidence': [], 'note': gi_context.USER_NOTE if member else ''}
        values = {'service_date': day} if member else {}
        context = models.EncounterContext.objects.create(
            encounter=encounter, revision=revision, facts=facts, user_values=values, version='gi-context@1',
            sha256=hashlib.sha256(f'{encounter.pk}:{day}:{member}'.encode()).hexdigest())
        jobs._record_routing(revision, jobs._route_child(revision.text, when), when)
        models.Encounter.objects.filter(pk=encounter.pk).update(current_context=context, user_values=values)
        request = self.provider.build_request(revision.text, when)
        self.provider.requests.append(request)  # it was sent: counted as the installed revision's send
        answered = state == models.ProviderRun.SUCCEEDED
        data = response(revision.text, []) if answered else b'{"error":"synthetic internal server error"}'
        run = models.ProviderRun.objects.create(
            encounter=encounter, revision=revision, provider=self.provider.name,
            adapter_version=self.provider.adapter_version, request_sha256=request.canonical_sha256,
            request_body=request.body, contexts=list(request.contexts), state=state, sent=True,
            http_status=200 if answered else 500, response_bytes=data, response_sha256=hashlib.sha256(data).hexdigest(),
            requested_by=self.reviewer, service_date=when, started_at=timezone.now(), finished_at=timezone.now(),
            error='' if answered else 'HTTP 500 from the provider (synthetic).')
        return str(encounter.pk), run


# --- security-0: a stage of a kind the next worker cannot run is closed whichever pair created it --------------------

class SecondReviewStoppedUnderAnEarlierPairTests(Base):
    """Refutation p1, security-0. The finding's smallest input: a reviewer asks for the second review, a member stops
    it before it runs (cancelled, resumable), a later pair of the same revision is created (an `app` re-run), and its
    rollback-app closes only what was created since then."""

    def stopped_second_review(self):
        encounter_id = self.create(REPORT)
        drain()
        self.assertEqual(self.post(f'/api/encounters/{encounter_id}/second-review').status_code, 201)
        self.assertEqual(self.post(f'/api/encounters/{encounter_id}/stop').status_code, 200)
        job = models.Job.objects.get(encounter_id=encounter_id, kind=models.Job.REVIEW2)
        self.assertEqual(job.state, models.Job.CANCELLED)
        self.assertTrue(review.can_resume(self.encounter(encounter_id)))
        return encounter_id, job

    def test_a_second_review_stopped_under_an_earlier_pair_is_closed_for_a_worker_that_has_no_such_stage(self):
        encounter_id, job = self.stopped_second_review()
        # a stopped stage of a kind every worker runs, also left by an earlier pair: it stays resumable
        other_id = self.create(OFFICE_NOTE)
        self.assertEqual(self.post(f'/api/encounters/{other_id}/stop').status_code, 200)
        extract = models.Job.objects.get(encounter_id=other_id, kind=models.Job.EXTRACT)
        self.assertEqual(extract.state, models.Job.CANCELLED)
        since = timezone.now() + dt.timedelta(seconds=1)  # the later pair was created after both Stops

        answer = self.close(since)  # the next worker runs extract, analyze, predict and assess (057a7d39's STAGES)

        self.assertEqual((answer['closed'], answer['kinds']), (1, ['review2']))
        job.refresh_from_db()
        self.assertEqual((job.state, job.error), (models.Job.FAILED, NOTE))
        self.assertFalse(review.can_resume(self.encounter(encounter_id)))
        extract.refresh_from_db()
        self.assertEqual(extract.state, models.Job.CANCELLED)
        self.assertTrue(review.can_resume(self.encounter(other_id)))
        with mock.patch.object(jobs, 'STAGES', {k: v for k, v in jobs.STAGES.items() if k != models.Job.REVIEW2}):
            self.assertEqual(run_app_script(install.UNRUNNABLE_STAGES, {})['stuck'], 0)  # as 057a7d39 reads it
        self.assertEqual(self.sent(), 1)

    def test_controls_a_next_worker_that_runs_it_keeps_it_and_a_stage_no_resume_reaches_is_left(self):
        encounter_id, job = self.stopped_second_review()
        since = timezone.now() + dt.timedelta(seconds=1)
        self.assertEqual(self.close(since, kinds=sorted(jobs.STAGES))['closed'], 0)  # it runs review2: kept
        job.refresh_from_db()
        self.assertEqual(job.state, models.Job.CANCELLED)
        self.assertTrue(review.can_resume(self.encounter(encounter_id)))
        # a later member action makes another stage the latest: no Resume reaches the stopped review any more
        self.set_context(encounter_id, setting='asc')
        self.assertFalse(review.can_resume(self.encounter(encounter_id)))
        self.assertEqual(self.close(timezone.now() + dt.timedelta(seconds=1))['closed'], 0)
        job.refresh_from_db()
        self.assertEqual(job.state, models.Job.CANCELLED)


# --- migrate-0 / migrate-1: what an older revision would act on wrongly is named, never left for it ------------------

class UndoHazardsTests(Base):
    """Refutation p1, migrate-0 and migrate-1. The installer reads, with this revision's image, every encounter whose
    records the installed revision 057a7d39 would act on under its own rules: an unreconciled unknown outcome (its
    reconcile requests the current context, without a date when that holds a member date conflict), and a request that
    failed or was not sent which its next metadata save or Resume could make again (round-7c8 skeptic, sk:0/sk:1: not
    only where a hold or second review stands over the newest primary request)."""

    def test_migrate0_an_unknown_outcome_under_a_member_date_conflict_is_named_until_it_is_reconciled_here(self):
        self.provider.outcomes = ['unknown']
        encounter_id = self.create(OFFICE_NOTE)
        drain()
        self.set_context(encounter_id, service_date=MEMBER_CONFLICT)  # this revision holds the conflict
        self.assertEqual(self.sent(), 1)
        context = self.encounter(encounter_id).current_context
        self.assertEqual(context.facts['service_date']['origin'], 'conflict')
        self.assertEqual(self.hazards(), {encounter_id: ['unknown']})
        self.assertEqual(self.close(timezone.now())['hazards'], {encounter_id: ['unknown']})
        # cleared the documented way, on this revision's web: its reconcile holds the conflict and sends nothing
        unknown = models.ProviderRun.objects.get(encounter_id=encounter_id, state=models.ProviderRun.UNKNOWN)
        reply = self.post(f'/api/encounters/{encounter_id}/reconcile',
                          {'provider_run_id': str(unknown.pk), 'note': 'Checked the provider console: nothing billed.'})
        self.assertEqual(reply.status_code, 201, reply.content)
        drain()
        self.assertEqual(self.sent(), 1)
        self.assertEqual(self.hazards(), {})

    def test_migrate1_a_hold_over_a_failed_request_is_named_once_a_metadata_save_would_make_it_again(self):
        self.provider.outcomes = ['failed']
        encounter_id = self.create(OFFICE_NOTE)
        drain()
        failed = self.runs(encounter_id)[-1]
        self.assertEqual((failed.state, failed.sent), (models.ProviderRun.FAILED, True))
        self.set_context(encounter_id, service_date=MEMBER_CONFLICT)
        hold = self.runs(encounter_id)[-1]
        self.assertEqual((hold.state, hold.request_sha256, hold.scope), (models.ProviderRun.NOT_SENT, '',
                                                                          {'held': 'member_date_conflict'}))
        # the installed revision's save requests the member's date (its own rule: a first send, documented) - never
        # the documented date's request that failed (proven with its real code, round-7c8 probe d_member: D1)
        self.assertEqual(self.hazards(), {})
        # answered with the documented date: the request is the one that failed, so this revision re-assesses with it
        # and records nothing newer - the hold still stands newest, and the installed revision's save, now requesting
        # its own reading of the document's date, would send that failed request again (probe d_member: D2)
        self.set_context(encounter_id, service_date='')
        self.assertEqual(self.sent(), 1)
        self.assertEqual(self.runs(encounter_id)[-1].pk, hold.pk)
        self.assertEqual(self.hazards(), {encounter_id: ['outcome']})
        self.assertEqual(self.close(timezone.now())['hazards'], {encounter_id: ['outcome']})
        # an addendum makes a newer request, whose outcome then stands for the document
        reply = self.post(f'/api/encounters/{encounter_id}/addenda',
                          {'text': 'Addendum (synthetic): no change to the plan.', 'synthetic_attestation': 'yes'})
        self.assertEqual(reply.status_code, 201, reply.content)
        drain()
        self.assertEqual(self.sent(), 2)
        self.assertEqual(self.hazards(), {})

    def test_migrate1_the_findings_shape_is_named_until_an_addendum_makes_a_newer_request(self):
        # the finding's rows: the installed revision sent the member's date and it FAILED (HTTP 500); a member's
        # setting save here holds the conflict over it
        encounter_id, failed = self.installed_request(MEMBER_CONFLICT, member=True)
        self.set_context(encounter_id, setting='office')
        hold = self.runs(encounter_id)[-1]
        self.assertEqual((hold.state, hold.request_sha256, hold.scope),
                         (models.ProviderRun.NOT_SENT, '', {'held': 'member_date_conflict'}))
        self.assertEqual(self.sent(), 1)  # the installed revision's own request only
        self.assertEqual(self.hazards(), {encounter_id: ['outcome']})
        # clearing the member's date makes the request for the documented date, newer than the hold; the request that
        # failed stays named: with no member date the installed revision's save requests its OWN reading of the
        # document's date, which this image cannot know (sk:0: the two revisions can read it differently)
        self.set_context(encounter_id, service_date='')
        self.assertEqual(self.sent(), 2)
        self.assertEqual(self.provider.requests[-1].contexts[1:], ('Date of service: 2026-10-20',))
        self.assertNotEqual(self.runs(encounter_id)[-1].pk, hold.pk)
        self.assertEqual(self.hazards(), {encounter_id: ['outcome']})
        self.addendum(encounter_id)
        self.assertEqual(self.sent(), 3)
        self.assertEqual(self.hazards(), {})

    def test_controls_a_hold_over_a_succeeded_request_a_second_review_and_a_first_hold_are_not_named(self):
        # a second review newer than its primary, which succeeded (a second review is only ever made for one), that
        # added no code: the installed revision's re-assessment, which does not read it, removes nothing a reviewer
        # decides on (a code it added is named: SecondReviewCodeTests)
        reviewed = self.create(REPORT)
        drain()
        self.provider.later = [VISIT, SNARE]
        self.assertEqual(self.post(f'/api/encounters/{reviewed}/second-review').status_code, 201)
        drain()
        self.assertEqual(self.runs(reviewed)[-1].purpose, models.ProviderRun.SECOND_REVIEW)
        self.assertFalse(self.second_review_codes(reviewed))
        # a hold over a request that succeeded: the installed revision's save requests the member's date (its own
        # rule, a first send - documented), never a request that failed
        succeeded = self.create(OFFICE_NOTE)
        drain()
        self.set_context(succeeded, service_date=MEMBER_CONFLICT)
        self.assertEqual(self.runs(succeeded)[-1].scope, {'held': 'member_date_conflict'})
        # a member date conflict entered at upload: the first run is the hold, no request stands behind it
        first = self.create(OFFICE_NOTE.replace('(fictional)', '(fictional) B'), service_date=MEMBER_CONFLICT)
        drain()
        self.assertEqual([run.state for run in self.runs(first)], [models.ProviderRun.NOT_SENT])
        self.assertEqual(self.hazards(), {})

    def test_migrate0_a_stopped_predict_on_a_member_date_conflict_is_named_and_a_stopped_hold_is_not(self):
        # the installed revision's Resume requests the CURRENT context for a stopped predict (and for a stopped assess
        # of an earlier context); with a member date conflict there it would send without a date
        encounter_id = self.create(OFFICE_NOTE)
        drain()
        reply = self.post(f'/api/encounters/{encounter_id}/context', {'service_date': MEMBER_CONFLICT})
        self.assertEqual(reply.status_code, 201, reply.content)
        self.assertEqual(self.post(f'/api/encounters/{encounter_id}/stop').status_code, 200)  # the hold's assess
        self.assertTrue(review.can_resume(self.encounter(encounter_id)))
        self.assertEqual(self.hazards(), {})  # its Resume re-assesses the same context with the hold: nothing sent
        encounter = self.encounter(encounter_id)
        job = jobs.enqueue(models.Job.PREDICT, encounter=encounter, revision=encounter.current_revision,
                           context=encounter.current_context, key=f'predict:{encounter.current_context_id}:stopped',
                           requested_by=self.reviewer)
        models.Job.objects.filter(pk=job.pk).update(state=models.Job.CANCELLED)
        self.assertEqual(self.hazards(), {encounter_id: ['conflict']})


class OutcomeIsARequestTheOlderRevisionWouldMakeAgainTests(Base):
    """Round-7c8 skeptic of the first repair, sk:0 and sk:1 (migrate-1's class: after a rollback a request that FAILED
    is re-sent byte-identical behind a metadata save, and neither revision alone would send it). 'outcome' names every
    request of the current revision that failed or was not sent through the send, with no retained answer the installed
    revision would reuse, that its next metadata save could make while its run in use - the newest finished run,
    whatever it was made for - carries another request: the member's date when one is set (it requests that date), else
    any (it requests its own reading of the document's date, which this image cannot know); and every such request its
    Resume of a stopped predict makes for the current context's stored date, which it does not compare."""

    def test_sk0_the_installed_revisions_reading_failed_and_this_revisions_request_stands_newest(self):
        # 057a7d39's request for its own reading of the document's date FAILED (probe a_dates); this revision reads the
        # documented date, and a member's setting save here sends that request, which succeeds and is newest
        encounter_id, failed = self.installed_request(INSTALLED_READING, member=False)
        self.set_context(encounter_id, setting='asc')
        self.assertEqual(self.sent(), 2)
        self.assertEqual(self.provider.requests[-1].contexts[1:], ('Date of service: 2026-10-20',))
        newest = self.runs(encounter_id)[-1]
        self.assertEqual((newest.state, newest.purpose), (models.ProviderRun.SUCCEEDED, models.ProviderRun.PRIMARY))
        self.assertEqual(self.hazards(), {encounter_id: ['outcome']})
        self.assertEqual(self.close(timezone.now())['hazards'], {encounter_id: ['outcome']})
        self.addendum(encounter_id)  # a newer revision, whose own request then stands
        self.assertEqual(self.sent(), 3)
        self.assertEqual(self.hazards(), {})

    def test_sk0_control_the_installed_revisions_failed_request_standing_alone_is_not_named(self):
        # the skeptic's control A1c: the same rows, untouched here - the failed request is its run in use, which its
        # save compares with the request it makes (nothing sent)
        self.installed_request(INSTALLED_READING, member=False)
        self.assertEqual(self.hazards(), {})

    def test_sk1_a_hold_over_a_succeeded_request_while_the_members_date_is_a_request_that_failed(self):
        # the skeptic's rows (b_hold): the installed revision sent the member's date and it FAILED; with the date
        # cleared the documented date's request succeeded; here the member enters the same date again, which this
        # revision holds - the hold is the installed revision's run in use, and its setting save would request the
        # member's date: the request that failed
        encounter_id, failed = self.installed_request(MEMBER_CONFLICT, member=True)
        self.set_context(encounter_id, service_date='')
        self.assertEqual(self.runs(encounter_id)[-1].state, models.ProviderRun.SUCCEEDED)
        self.set_context(encounter_id, service_date=MEMBER_CONFLICT)
        self.assertEqual(self.runs(encounter_id)[-1].scope, {'held': 'member_date_conflict'})
        self.assertEqual(self.sent(), 2)
        self.assertEqual(self.hazards(), {encounter_id: ['outcome']})
        self.assertEqual(self.close(timezone.now())['hazards'], {encounter_id: ['outcome']})
        self.addendum(encounter_id)  # a newer revision: the member's date is held there, and nothing failed
        self.assertEqual(self.sent(), 2)
        self.assertEqual(self.hazards(), {})

    def test_controls_the_members_own_date_answered_by_its_run_in_use_and_a_retained_answer(self):
        # the installed revision's own date change: the member's first date FAILED, the second succeeded and stands -
        # its save requests the member's (second) date, which that run answers; the first is made again only by a
        # member's date change, as on the installed revision alone
        changed, _ = self.installed_request(MEMBER_CONFLICT, member=True)
        self.installed_request('2026-09-02', member=True, state=models.ProviderRun.SUCCEEDED, encounter=changed)
        # a failed request whose identical request another encounter has since had answered: it reuses that answer
        retained, _ = self.installed_request(INSTALLED_READING, member=False)
        self.set_context(retained, setting='asc')  # this revision's request stands newer than the failed one
        self.assertEqual(self.hazards(), {retained: ['outcome']})
        self.installed_request(INSTALLED_READING, member=False, state=models.ProviderRun.SUCCEEDED)
        self.assertEqual(self.hazards(), {})

    def test_a_stopped_predict_whose_resume_makes_a_request_that_failed_is_named(self):
        # the installed revision's Resume of a stopped predict sends the current context's request without asking its
        # run in use: here that is the request that failed, although the failed run itself is the newest
        encounter_id, failed = self.installed_request('2026-10-20', member=False)
        self.assertEqual(self.hazards(), {})  # its save compares, and the failed run answers: nothing sent
        self.stopped(encounter_id, models.Job.PREDICT)
        self.assertEqual(self.hazards(), {encounter_id: ['outcome']})
        # control: a stopped assess of the current context is re-assessed with its own run (nothing sent)
        other_id, other = self.installed_request('2026-10-20', member=False,
                                                 text=OFFICE_NOTE.replace('(fictional)', '(fictional) C'))
        self.stopped(other_id, models.Job.ASSESS, provider_run=other)
        self.assertEqual(self.hazards(), {encounter_id: ['outcome']})
        # a stopped analyze: its Resume reads the document afresh and requests that reading, also without comparing
        read_id, _ = self.installed_request('2026-10-20', member=False,
                                            text=OFFICE_NOTE.replace('(fictional)', '(fictional) D'))
        self.stopped(read_id, models.Job.ANALYZE)
        self.assertEqual(self.hazards(), {encounter_id: ['outcome'], read_id: ['outcome']})

    def stopped(self, encounter_id, kind, provider_run=None):
        """A stage of ``kind`` for the current context, stopped as the latest (what a Resume runs again)."""
        encounter = self.encounter(encounter_id)
        job = jobs.enqueue(kind, encounter=encounter, revision=encounter.current_revision,
                           context=encounter.current_context, provider_run=provider_run,
                           key=f'{kind}:{encounter.current_context_id}:stopped', requested_by=self.reviewer)
        models.Job.objects.filter(pk=job.pk).update(state=models.Job.CANCELLED)
        self.assertTrue(review.can_resume(self.encounter(encounter_id)))


class SecondReviewCodeTests(Base):
    """Round-7c8 skeptic of the first repair, sk:3 (must-fix class 4). The installed revision's re-assessment reads the
    primary answer alone (057a7d398 jobs.stage_assess: job.provider_run, no second review), so after a rollback a code
    only the bounded second review selected left the decision set at the encounter's next re-assessment there - a
    member's setting save - without a reviewer's decision, and nothing was named. 'second_review' names an encounter
    whose current assessment holds such a code in its decision set (selected or excluded), until an addendum makes a
    newer revision, whose assessment reads no second review until one is asked for."""

    def test_sk3_a_code_only_the_second_review_selected_is_named_until_an_addendum(self):
        # the skeptic's rows (c_review2): the primary proposes 45385, a reviewer asks for the second review, which
        # proposes 45380 for the biopsy left unresolved; the assessment then selects 45380 and 45385
        encounter_id = self.create(REPORT)
        drain()
        self.assertEqual(self.post(f'/api/encounters/{encounter_id}/second-review').status_code, 201)
        drain()
        self.assertEqual(self.second_review_codes(encounter_id), [('45380', models.Proposal.SELECTED)])
        self.assertEqual(self.hazards(), {encounter_id: ['second_review']})
        self.assertEqual(self.close(timezone.now())['hazards'], {encounter_id: ['second_review']})
        self.addendum(encounter_id)
        self.assertFalse(self.second_review_codes(encounter_id))
        self.assertEqual(self.hazards(), {})

    def test_control_a_second_review_that_only_listed_an_alternative_is_not_named(self):
        # a code it selected that accounts for nothing it was asked about is shown as an alternative only (no review
        # action): the installed revision's re-assessment drops that line, and no code a reviewer decides on
        encounter_id = self.create(REPORT)
        drain()
        self.provider.later = [('99213', 'was sampled with cold biopsy forceps')]
        self.assertEqual(self.post(f'/api/encounters/{encounter_id}/second-review').status_code, 201)
        drain()
        listed = [(p.code, p.bucket) for p in self.encounter(encounter_id).current_assessment.proposals.all()
                  if (p.support or {}).get('origin') == 'second_review']
        self.assertEqual(listed, [('99213', models.Proposal.ALTERNATIVE)])
        self.assertEqual(self.hazards(), {})


# --- migrate-2 / sk:2: the stored list states are recomputed once the new pair replaced the old one -------------------

class RecomputedStatesTests(Base):
    """Refutation p1, migrate-2, and the round-7c8 skeptic of its first repair (sk:2). The first repair refused the app
    phase while any outcome was unknown, so a same-revision re-run (`app --provider-mode disabled`, as during a provider
    incident) and the reinstall the failure path's receipt asks for were refused until a member reconciled on the
    running web - releasing a paid send, and on a restored older web acting under its rules. Nothing is refused now:
    once the new pair has replaced the old one, every stored list state is recomputed with this revision's derivation."""

    def run_app(self):
        details, replace = app_phase(lambda image_id, env, body, params, **kwargs: run_app_script(body, params))
        self.assertIsInstance(details, dict, details)
        replace.assert_called_once()
        return details

    def test_sk2_a_same_revision_rerun_over_an_unknown_outcome_installs_and_sends_nothing(self):
        # the skeptic's probe (a): an outcome THIS revision left unknown, its stored state its own derivation; then
        # `app --provider-mode disabled` for the same revision
        self.provider.outcomes = ['unknown']
        encounter_id = self.create(OFFICE_NOTE)
        drain()
        self.assertEqual(self.sent(), 1)
        stored = self.encounter(encounter_id).state
        self.assertEqual(stored, review._derive_state(self.encounter(encounter_id)))
        details = self.run_app()
        self.assertEqual(details['states_recomputed']['changed'], {})
        self.assertEqual((self.encounter(encounter_id).state, self.sent()), (stored, 1))

    def test_sk2_the_reinstall_the_failure_paths_receipt_asks_for_installs_without_a_reconcile(self):
        # the skeptic's probe (b): the new pair's send was in flight when it was stopped, the failure path's close names
        # the unknown outcome (the restored worker is left stopped) and its receipt asks for this revision again
        self.provider.outcomes = ['unknown']
        swap = timezone.now() - dt.timedelta(seconds=1)
        encounter_id = self.create(OFFICE_NOTE)
        drain()
        self.assertEqual(self.close(swap)['hazards'], {encounter_id: ['unknown']})
        self.run_app()
        self.assertEqual(self.sent(), 1)
        self.assertEqual(models.ProviderRun.objects.get(encounter_id=encounter_id).reconciled_at, None)

    def test_migrate2_the_upgrade_recomputes_a_stored_state_the_replaced_revision_derived_otherwise(self):
        # the finding's shape: a first request succeeded, a date change came back unknown, and clearing it reused the
        # first answer - the stored state read 'reviewed' under the installed revision's rule
        encounter_id = self.create(UNDATED_NOTE, service_date='2026-10-20')
        drain()
        self.provider.outcomes = ['unknown']
        self.set_context(encounter_id, service_date='2026-10-21')
        self.set_context(encounter_id, service_date='2026-10-20')
        self.assertEqual(self.sent(), 2)
        models.Encounter.objects.filter(pk=encounter_id).update(state='reviewed')  # as 057a7d39 derived it
        self.assertEqual(review._derive_state(self.encounter(encounter_id)), 'provider_unknown')
        other = self.create(OFFICE_NOTE)  # control: a stored state that is this revision's derivation is not written
        drain()
        untouched = self.encounter(other).updated_at
        details = self.run_app()
        self.assertEqual(details['states_recomputed']['changed'], {encounter_id: ['reviewed', 'provider_unknown']})
        self.assertEqual(self.encounter(encounter_id).state, 'provider_unknown')
        self.assertEqual(self.encounter(other).updated_at, untouched)
        self.assertEqual(self.sent(), 3)

    def test_a_copy_of_the_live_installation_is_not_refused_and_has_nothing_to_undo(self):
        # 2026-10-27 16:23Z: 11 encounters, 11 provider runs, all succeeded and sent, no stage active, none unknown
        for number in range(11):
            self.create(OFFICE_NOTE.replace('(fictional)', f'(fictional) {number}'))
            drain()
        runs = models.ProviderRun.objects.all()
        self.assertEqual((runs.count(), runs.filter(state=models.ProviderRun.SUCCEEDED, sent=True).count()), (11, 11))
        self.assertFalse(models.Job.objects.filter(state__in=(models.Job.QUEUED, models.Job.RUNNING)).exists())
        details = self.run_app()
        self.assertEqual(details['states_recomputed'], {'encounters': 11, 'changed': {}})
        self.assertEqual(details['unrunnable_stages']['stuck'], 0)
        self.assertEqual(self.hazards(), {})


def app_phase(app_script, replace=None):
    """install.phase_app with ``app_script`` answering its in-image reads (and ``replace`` as replace_services, when
    given); no container, no Docker."""
    ctx = SimpleNamespace(revision=NEW_REVISION, log=lambda label, data: 'log',
                          args=SimpleNamespace(provider_mode='disabled', authorization_ref=''))
    with mock.patch.object(install, 'installed_image', return_value=NEW_IMAGE), \
            mock.patch.object(install, 'require_db'), \
            mock.patch.object(install, 'read_protected_env', return_value=b''), \
            mock.patch.object(install, 'oneshot', return_value=SimpleNamespace(returncode=0, stdout=b'', stderr=b'')), \
            mock.patch.object(install, 'app_script', app_script), \
            mock.patch.object(install, 'replace_services', side_effect=replace,
                              return_value={'started': {}}) as replaced:
        try:
            return install.phase_app(ctx), replaced
        except install.InstallError as error:
            return error, replaced


class AppPhaseRecomputesOnlyOverItsOwnPairTests(SimpleTestCase):
    """The recompute runs after replace_services succeeded - never before, so a failure path restores the old pair over
    the states it derived - and a recompute that fails says the pair runs and to rerun the phase."""

    def answers(self, calls, recompute=None):
        def app_script(image_id, env, body, params, **kwargs):
            if body == install.UNRUNNABLE_STAGES:
                calls.append('unrunnable')
                return {'known': ['analyze', 'assess', 'extract', 'predict', 'review2'], 'stuck': 0, 'kinds': []}
            if body == install.RECOMPUTE_STATES:
                calls.append('recompute')
                if isinstance(recompute, Exception):
                    raise recompute
                return {'encounters': 2, 'changed': {'e1': ['reviewed', 'provider_unknown']}}
            raise AssertionError('an unexpected in-image script')
        return app_script

    def test_the_states_are_recomputed_after_the_new_pair_replaced_the_old_one(self):
        calls = []
        details, replaced = app_phase(self.answers(calls), replace=lambda *a, **k: calls.append('replace') or {})
        self.assertIsInstance(details, dict, details)
        self.assertEqual(calls, ['unrunnable', 'replace', 'recompute'])
        self.assertEqual(details['states_recomputed']['changed'], {'e1': ['reviewed', 'provider_unknown']})

    def test_a_failed_replacement_recomputes_nothing(self):
        calls = []

        def fail(*args, **kwargs):
            calls.append('replace')
            raise install.InstallError('worker did not become ready; the previous pair was restored')
        error, replaced = app_phase(self.answers(calls), replace=fail)
        self.assertIsInstance(error, install.InstallError)
        self.assertEqual(calls, ['unrunnable', 'replace'])

    def test_a_failed_recompute_says_the_pair_runs_and_to_rerun_the_phase(self):
        calls = []
        error, replaced = app_phase(self.answers(calls, recompute=install.InstallError('exit 1')),
                                    replace=lambda *a, **k: calls.append('replace') or {'started': {}})
        self.assertIsInstance(error, install.InstallError)
        self.assertEqual(calls, ['unrunnable', 'replace', 'recompute'])
        self.assertIn('web and worker running', str(error))
        self.assertIn('rerun --phase app', str(error))


# --- the phases: rollback-app refuses, the failure path leaves the restored worker stopped ---------------------------

class World(DockerWorld):
    """DockerWorld with the undo's reads: the kinds the next worker runs, and what the close's answer names."""

    def __init__(self, *, hazards_after=None, **kwargs):
        super().__init__(**kwargs)
        self.hazards_after, self.kinds_read = hazards_after or {}, []

    def close(self, image_id, env_bytes, since, revision, reason, kinds=None):
        answer = super().close(image_id, env_bytes, since, revision, reason)
        self.closed['kinds'] = kinds
        return {**answer, 'hazards': self.hazards_after}

    def stage_kinds_of(self, image_id, env_bytes):
        self.record('kinds', image_id)
        self.kinds_read.append(image_id)
        return ['analyze', 'assess', 'extract', 'predict', 'reviewN'] if image_id == OLD_IMAGE else ['x']


class FailurePathLeavesTheRestoredWorkerStoppedTests(SimpleTestCase):
    """Refutation p1, migrate-0/-1 (the automatic failure path cannot refuse): when the close's answer names encounters
    the restored revision would act on wrongly, its web is restored and its worker is left stopped - nothing can be
    sent - and the receipt says so; security-0: the close is told the kinds the restored worker runs."""

    def replace(self, world, failing_role='worker'):
        def wait(role, revision, image_id):
            if role == failing_role:
                raise install.InstallError(f'{role} did not become ready')
            return {'id': f'new-{role}'}
        ctx = SimpleNamespace(revision=NEW_REVISION, log=lambda label, data: None)
        for container in world.live.values():
            container['Image'] = OLD_IMAGE
        with mock.patch.object(install, 'inspect', world.inspect), mock.patch.object(install, 'docker', world.docker), \
                mock.patch.object(install, 'wait_service', wait), \
                mock.patch.object(install, 'close_undone_stages', world.close), \
                mock.patch.object(install, 'stage_kinds_of', world.stage_kinds_of), \
                mock.patch.object(install, 'oneshot', side_effect=AssertionError('no real container in a test')):
            return install.replace_services(ctx, NEW_IMAGE, b'ENV=1\n', 'live', 'ruling.md')

    def test_named_encounters_leave_the_restored_worker_stopped_and_the_receipt_says_why(self):
        world = World(hazards_after={'e1': ['unknown'], 'e2': ['outcome']})
        with self.assertRaises(install.InstallError) as caught:
            self.replace(world)
        message = str(caught.exception)
        self.assertIn('worker did not become ready', message)
        self.assertIn('left stopped', message)
        self.assertIn('2 encounter(s)', message)
        self.assertEqual(caught.exception.details['hazards'], {'e1': ['unknown'], 'e2': ['outcome']})
        self.assertEqual(world.ids(), {install.SERVICES['web']: 'old-web', install.SERVICES['worker']: 'old-worker'})
        started = [call[1] for call in world.calls if call[0] == 'start']
        self.assertEqual(started, [install.SERVICES['web']])
        close = world.index('close')
        self.assertLess(close, world.index('rename', install.SERVICES['worker'] + '-previous'))
        self.assertLess(close, world.index('start', install.SERVICES['web']))

    def test_the_close_is_told_the_kinds_the_restored_worker_runs_and_nothing_named_restores_both(self):
        world = World()
        with self.assertRaises(install.InstallError) as caught:
            self.replace(world)
        self.assertNotIn('left stopped', str(caught.exception))
        self.assertEqual(world.kinds_read, [OLD_IMAGE])
        self.assertLess(world.index('kinds', OLD_IMAGE), world.index('close'))
        self.assertEqual(world.closed['kinds'], ['analyze', 'assess', 'extract', 'predict', 'reviewN'])
        self.assertEqual(sorted(call[1] for call in world.calls if call[0] == 'start'),
                         sorted(install.SERVICES.values()))


class RollbackAppRefusesTests(SimpleTestCase):
    """Refutation p1, migrate-0/-1 and security-0 at rollback-app: it refuses, before stopping anything, while this
    revision's records would be acted on wrongly by an older revision; a second read after the close (a request in
    flight when the worker stopped becomes an unknown outcome) leaves the pair stopped, not removed; and the close is
    told the kinds the parked worker runs, or only the common four when no pair is parked."""

    def rollback(self, world, hazards_before=None, parked=True):
        reads = []

        def undo_hazards(image_id, env_bytes, revision):
            world.record('hazards', image_id)
            reads.append(image_id)
            return hazards_before or {}
        world.live[install.SERVICES['web']] = world.container('new-web', 'web', NEW_IMAGE, NEW_REVISION,
                                                              '2026-10-27T12:30:00.700000001Z')
        world.live[install.SERVICES['worker']] = world.container('new-worker', 'worker', NEW_IMAGE, NEW_REVISION,
                                                                 '2026-10-27T12:30:41.25Z')
        if parked:
            world.live[install.SERVICES['worker'] + '-previous'] = world.container(
                'old-worker', 'worker', OLD_IMAGE, OLD_REVISION, '2026-10-01T00:00:00Z')
        ctx = SimpleNamespace(revision=NEW_REVISION)
        with mock.patch.object(install, 'inspect', world.inspect), mock.patch.object(install, 'docker', world.docker), \
                mock.patch.object(install, 'close_undone_stages', world.close), \
                mock.patch.object(install, 'stage_kinds_of', world.stage_kinds_of), \
                mock.patch.object(install, 'undo_hazards', undo_hazards), \
                mock.patch.object(install, 'require_db', lambda: world.record('require_db')), \
                mock.patch.object(install, 'read_protected_env', return_value=b'ENV=2\n'), \
                mock.patch.object(install, 'oneshot', side_effect=AssertionError('no real container in a test')):
            return install.phase_rollback_app(ctx), reads

    def test_named_encounters_refuse_before_anything_is_stopped(self):
        world = World(previous=False)
        with self.assertRaises(install.InstallError) as caught:
            self.rollback(world, hazards_before={'e1': ['unknown']})
        self.assertIn('1 encounter(s)', str(caught.exception))
        self.assertIn('nothing was stopped or removed', str(caught.exception))
        self.assertEqual(caught.exception.details['hazards'], {'e1': ['unknown']})
        self.assertFalse([call for call in world.calls if call[0] in ('stop', 'rm', 'close')])
        self.assertEqual(world.calls[world.index('hazards')][1], NEW_IMAGE)

    def test_named_after_the_close_the_pair_is_left_stopped_not_removed(self):
        world = World(previous=False, hazards_after={'e2': ['unknown']})
        with self.assertRaises(install.InstallError) as caught:
            self.rollback(world)
        self.assertIn('stopped, not removed', str(caught.exception))
        self.assertEqual(caught.exception.details['hazards'], {'e2': ['unknown']})
        self.assertFalse([call for call in world.calls if call[0] == 'rm'])
        self.assertTrue([call for call in world.calls if call[0] == 'stop'])

    def test_controls_nothing_named_closes_with_the_parked_workers_kinds_and_removes_the_pair(self):
        world = World(previous=False)
        result, reads = self.rollback(world)
        self.assertEqual(reads, [NEW_IMAGE])
        self.assertLess(world.index('hazards'), world.index('stop', '--time', str(install.STOP_SECONDS['worker']),
                                                            install.SERVICES['worker']))
        self.assertEqual(world.kinds_read, [OLD_IMAGE])
        self.assertEqual(world.closed['kinds'], ['analyze', 'assess', 'extract', 'predict', 'reviewN'])
        self.assertEqual(result['stages_closed']['hazards'], {})
        self.assertEqual(world.ids(), {install.SERVICES['worker'] + '-previous': 'old-worker'})
        # with no parked pair to ask, only the kinds every revision's worker runs are kept
        world = World(previous=False)
        self.rollback(world, parked=False)
        self.assertEqual(world.kinds_read, [])
        self.assertEqual(world.closed['kinds'], list(install.COMMON_STAGE_KINDS))


class StageKindsTests(SimpleTestCase):
    def test_the_next_workers_kinds_are_its_own_image_answer_else_the_common_four(self):
        with mock.patch.object(install, 'app_script', return_value={'known': ['predict', 'extract', 'review2'],
                                                                     'stuck': 0, 'kinds': []}) as app_script:
            self.assertEqual(install.stage_kinds_of(OLD_IMAGE, b''), ['extract', 'predict', 'review2'])
        self.assertEqual(app_script.call_args[0][2], install.UNRUNNABLE_STAGES)
        with mock.patch.object(install, 'app_script', side_effect=install.InstallError('no answer')):
            self.assertEqual(install.stage_kinds_of(OLD_IMAGE, b''), list(install.COMMON_STAGE_KINDS))
        with mock.patch.object(install, 'app_script', side_effect=AssertionError('never run')):
            for image in (None, '', 'old', 'sha256:short'):  # not an image id: nothing is run for it
                self.assertEqual(install.stage_kinds_of(image, b''), list(install.COMMON_STAGE_KINDS))
