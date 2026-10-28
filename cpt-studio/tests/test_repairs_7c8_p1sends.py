"""Repair round 7c8, cluster P1SENDS (refutation phase 1 over b611b557a, lens sends): an identical request that already
FAILED is never sent again. Synthetic data only; no network: the provider is an in-process stand-in with the live
adapter's name and version (so the real normaliser reads its runs), and where a request's size decides whether it can
be built at all, it builds every request with the live adapter's own builder (corti.build_coding_request).

Every document opens with the synthetic banner.
"""
import hashlib
from datetime import date

from django.conf import settings
from django.test import override_settings
from django.utils import timezone

from studio import jobs, models, review
from studio.ingest import extract_paste
from studio.providers import corti
from studio.providers.base import canonical_body
from studio.types import RawExchange
from tests.test_pipeline_api import drain
from tests.test_repairs_ec5_sends import BANNER, Base
from tests.test_services_second_review import LIVE, REPORT, TwoPassProvider, response

UNDATED = REPORT.replace('Date of service: 2026-10-16\n', '')
DATE = '2026-10-16'
OTHER_DATE = '2026-10-17'
# REPORT followed by a later section the reader keeps outside the service's scope, so the text that documents the
# unresolved biopsy - a second review's excerpt - ends before anything an addendum appends.
TRAILED = REPORT + ('\nDischarge instructions (fictional)\n'
                    'Resume a regular diet today. Call the fictional clinic with any questions.\n')
ADDENDUM = {'text': 'Signed by the fictional endoscopist.', 'synthetic_attestation': 'yes'}
RECONCILE = {'note': 'Checked the synthetic provider console: no result exists.'}


class Provider(TwoPassProvider):
    """A whole document (it carries the banner) is answered with ``first``, an excerpt (a second review) with
    ``later``, each limited to the quotes the request's own text contains. Each send takes the next scripted outcome:
    'succeeded', 'failed' (an HTTP 500 the provider returned: sent, as the live adapter records any complete non-200
    answer) or 'unknown'. With ``max_request_bytes`` set, each request is built by the live adapter's own builder under
    that limit: over it, the request is refused (ProviderUnavailable), never truncated or sent."""

    max_request_bytes = None

    def build_request(self, text, service_date):
        if self.max_request_bytes is None:
            return super().build_request(text, service_date)
        return corti.build_coding_request(self.name, self.adapter_version, text, service_date, self.max_request_bytes)

    def send(self, request, *, deadline_s):
        self.requests.append(request)
        outcome = self.outcomes.pop(0) if self.outcomes else 'succeeded'
        if outcome == 'failed':
            return RawExchange(outcome='failed', sent=True, http_status=500,
                               error='HTTP 500 from the provider (synthetic).')
        if outcome == 'unknown':
            return RawExchange(outcome='unknown', sent=True, error='Read timed out after the request was sent.')
        if outcome == 'not_sent':
            # the token endpoint refused: the live adapter records not_sent (sent=False) before the coding request
            return RawExchange(outcome='not_sent', sent=False,
                               error='Corti authentication was refused (HTTP 503); no coding request was sent.')
        text = request.contexts[0]
        data = response(text, [q for q in (self.first if BANNER in text else self.later) if q[1] in text])
        return RawExchange(outcome='succeeded', sent=True, http_status=200, response_bytes=data,
                           response_sha256=hashlib.sha256(data).hexdigest(), latency_ms=10.0,
                           usage={'creditsConsumed': 0.02}, usage_basis='provider_reported_credits_not_usd')


def canonical(text):
    result = extract_paste(text, limits=jobs._limits())
    assert result.status == 'ok', (result.status, result.messages)
    return result.text


def body_bytes(text, day=None):
    """The canonical body size of the request the live adapter builds for ``text`` (as stored) and ``day``."""
    request = corti.build_coding_request('corti', corti.ADAPTER_VERSION, text, day, 10 ** 9)
    return len(canonical_body(request.body))


def sized_text(limit):
    """An undated synthetic report whose dateless request is at most ``limit`` bytes and whose request carrying
    'Date of service: 2026-10-16' is over it: a legal paste of ruled handout lines."""
    rule = '─' * 40  # a box-drawing rule: 40 characters, 120 bytes in UTF-8
    head = UNDATED + 'Fictional patient handout follows: a printed ruled page for notes.\n'

    def build(lines, pad):
        return head + (rule + '\n') * lines + 'End of handout ' + 'a' * pad + '.\n'
    target = limit - 10
    lines = (target - body_bytes(canonical(build(0, 0)))) // (len((rule + '\n').encode()) + 2)
    lines = max(lines, 0)
    pad = target - body_bytes(canonical(build(lines, 0)))
    text = build(lines, max(pad, 0))
    stored = canonical(text)
    assert body_bytes(stored) <= limit < body_bytes(stored, date.fromisoformat(DATE)), (body_bytes(stored), limit)
    assert len(text) <= settings.MAX_PASTE_CHARS
    return text


def installed_run_in_use(revision):
    """057a7d39's jobs._run_in_use, restated: the run whose outcome the installed revision reads as standing once a
    rollback (or the failure path) restores it - the revision's newest finished run, whatever it was made for (that
    revision has no purpose column), a reservation the stale sweep settled unsent excluded, and none when that run is
    a reconciled unknown outcome. Its _run_answers is this revision's, unchanged: a run that carries no request
    answers none."""
    from django.db.models import Q
    Run = models.ProviderRun
    swept = Q(state=Run.NOT_SENT) & Q(started_at__isnull=True) & ~Q(request_sha256='')
    run = (revision.provider_runs.filter(state__in=(Run.SUCCEEDED, Run.FAILED, Run.NOT_SENT, Run.UNKNOWN))
           .exclude(swept).order_by('-created_at').first())
    if run is None or (run.state == Run.UNKNOWN and run.reconciled_at is not None):
        return None
    return run


class Steps(Base):
    provider_class = Provider

    def context(self, encounter_id, **values):
        self.set_context(encounter_id, **values)
        drain()

    def reconcile(self, encounter_id):
        unknown = models.ProviderRun.objects.get(encounter_id=encounter_id, state=models.ProviderRun.UNKNOWN,
                                                 reconciled_at__isnull=True)
        reply = self.post(f'/api/encounters/{encounter_id}/reconcile',
                          {'provider_run_id': str(unknown.pk), **RECONCILE})
        self.assertEqual(reply.status_code, 201, reply.content)
        drain()

    def shas(self):
        return [request.canonical_sha256 for request in self.provider.requests]

    def runs(self, encounter_id, **filters):
        return list(models.ProviderRun.objects.filter(encounter_id=encounter_id, **filters).order_by('created_at'))

    def assert_failed_run_stands(self, encounter_id, failed):
        """The send door met the request that failed and sent nothing: the predict recorded a run of its own - not
        sent, carrying that request, saying so with the failure's error - and the encounter is re-assessed with it
        (provider_failed; the screen names it). That run is the revision's newest finished run as this revision and the
        installed one (057a7d39, after a rollback) read it, and it answers the current context's request on both, so no
        later save on either sends the request again (round 7c8 skeptic, sk:2: re-assessing with the older failed run
        itself left a newer run standing)."""
        encounter = self.encounter(encounter_id)
        revision, assessment = encounter.current_revision, encounter.current_assessment
        run = assessment.provider_run
        self.assertEqual(encounter.state, 'provider_failed')
        self.assertEqual((run.state, run.sent, run.request_sha256, run.revision_id, run.purpose),
                         (models.ProviderRun.NOT_SENT, False, failed.request_sha256, revision.pk,
                          models.ProviderRun.PRIMARY))
        self.assertTrue(run.error.startswith(jobs.FAILED_BEFORE_MESSAGE), run.error)
        self.assertIn(failed.error, run.error)
        self.assertEqual(assessment.context_id, encounter.current_context_id)
        self.assertEqual(jobs._run_in_use(revision), run)
        self.assertEqual(installed_run_in_use(revision), run)
        self.assertTrue(jobs._run_answers(run, revision, encounter.current_context))
        self.assertEqual(self.detail(encounter_id)['state_run'], str(run.pk))
        self.assertEqual(review.latest_job(encounter).kind, models.Job.ASSESS)
        return run


# --- sends-0: a run that carries no request is no request's outcome --------------------------------------------------

@override_settings(**LIVE)
class RunWithoutARequestIsNoOutcomeTests(Steps):
    """sends-0: a request failed; a date whose request could not be built recorded a not-sent run with no request (and
    sent nothing); clearing the date then SENT the byte-identical failed request again, because the run without a
    request stood as the run in use and answers no request (the sibling of the held run, ec5 integration)."""

    def sized_text(self, limit):
        return sized_text(limit)

    def test_a_date_whose_request_cannot_be_built_then_cleared_never_resends_the_failed_request(self):
        # the finding's smallest input: the live adapter's own limit, 512,000 bytes
        self.provider.max_request_bytes = settings.PROVIDER_MAX_REQUEST_BYTES
        self.provider.outcomes = ['failed']
        encounter_id = self.create(self.sized_text(settings.PROVIDER_MAX_REQUEST_BYTES))
        drain()
        [failed] = self.runs(encounter_id)
        self.assertEqual((failed.state, failed.sent, failed.service_date), (models.ProviderRun.FAILED, True, None))
        self.context(encounter_id, service_date=DATE)  # the dated request cannot be built: nothing is sent
        self.assertEqual(self.sent(), 1)
        unbuilt = self.runs(encounter_id)[-1]
        self.assertEqual((unbuilt.state, unbuilt.request_sha256), (models.ProviderRun.NOT_SENT, ''))
        self.assertIn('over the 512,000-byte limit', unbuilt.error)
        self.context(encounter_id, service_date='')  # cleared: the request is the failed one, byte for byte
        self.assertEqual(self.sent(), 1)
        self.assertEqual(self.shas(), [failed.request_sha256])
        run = self.assert_failed_run_stands(encounter_id, failed)
        self.assertEqual(self.runs(encounter_id), [failed, unbuilt, run])

    def test_the_context_dialogs_whole_body(self):
        # the same steps posted as the context dialog posts them: every field, every time; a smaller limit on the
        # same builder keeps the document short
        text = self.sized_text(4_000)
        self.provider.max_request_bytes = 4_000
        self.provider.outcomes = ['failed']
        encounter_id = self.create(text)
        drain()
        self.context(encounter_id, service_date=DATE, setting='', billing_context='')
        self.context(encounter_id, service_date='', setting='', billing_context='')
        self.assertEqual(self.sent(), 1)
        self.assert_failed_run_stands(encounter_id, self.runs(encounter_id)[0])

    def test_control_a_request_never_sent_is_sent_once_its_date_is_cleared(self):
        # a run without a request before any request was sent: clearing the date makes the one attempt, once
        text = self.sized_text(4_000)
        self.provider.max_request_bytes = 4_000
        encounter_id = self.create(text, service_date=DATE)  # a member's date at upload: nothing can be built
        drain()
        self.assertEqual(self.sent(), 0)
        self.assertEqual([r.request_sha256 for r in self.runs(encounter_id)], [''])
        self.context(encounter_id, service_date='')
        self.assertEqual(self.sent(), 1)
        self.assertEqual(self.dates_sent(), [])
        self.assertNotEqual(self.encounter(encounter_id).state, 'provider_failed')

    def test_control_an_answered_request_is_reused_after_the_same_steps(self):
        text = self.sized_text(4_000)
        self.provider.max_request_bytes = 4_000
        encounter_id = self.create(text)
        drain()
        self.context(encounter_id, service_date=DATE)
        self.context(encounter_id, service_date='')
        self.assertEqual(self.sent(), 1)
        self.assertEqual(self.encounter(encounter_id).current_assessment.provider_run.state,
                         models.ProviderRun.SUCCEEDED)


# --- sends-1: a FAILED second review is never sent again, on any revision --------------------------------------------

@override_settings(**LIVE)
class FailedSecondReviewTests(Steps):
    """sends-1: a reviewer's second review FAILED; an addendum that left the excerpt as it was made a new revision, the
    card offered "Ask the provider once more" again, and the ask SENT the byte-identical request again (the bound is
    per revision, and the retained-result lookup matches only a SUCCEEDED run). With a provider that keeps failing,
    every addendum and ask sent it once more."""

    def failed_then_addendum(self, *, second_outcome='failed'):
        encounter_id = self.create(TRAILED)
        drain()
        self.assertEqual(self.selected(encounter_id), {'45385': 'primary'})
        self.provider.outcomes = [second_outcome]
        self.assertEqual(self.ask(encounter_id).status_code, 201)
        drain()
        [second] = self.runs(encounter_id, purpose=models.ProviderRun.SECOND_REVIEW)
        self.assertEqual(second.state, second_outcome)
        reply = self.post(f'/api/encounters/{encounter_id}/addenda', ADDENDUM)
        self.assertEqual(reply.status_code, 201, reply.content)
        drain()
        encounter = self.encounter(encounter_id)
        self.assertEqual(encounter.current_revision.number, 2)
        self.assertEqual(self.selected(encounter_id), {'45385': 'primary'})  # the biopsy is still unresolved
        revision = encounter.current_revision
        span = jobs._second_review_items(encounter.current_assessment)[1]
        excerpt = self.provider.build_request(revision.text[span[0]:span[1]], date.fromisoformat(DATE))
        self.assertEqual(excerpt.canonical_sha256, second.request_sha256)  # the finding's precondition
        return encounter_id, second

    def test_an_addendum_that_leaves_the_excerpt_as_it_was_never_resends_the_failed_review(self):
        encounter_id, second = self.failed_then_addendum()
        sent = self.sent()
        offered = self.detail(encounter_id)['second_review']
        self.assertFalse(offered['available'], offered)
        self.assertIn('failed', offered['reason'])
        reply = self.ask(encounter_id)
        self.assertEqual(reply.status_code, 409, reply.content)
        drain()
        self.assertEqual(self.sent(), sent)
        self.assertEqual(self.shas().count(second.request_sha256), 1)
        self.assertEqual(self.runs(encounter_id, purpose=models.ProviderRun.SECOND_REVIEW), [second])
        self.assertEqual(self.encounter(encounter_id).state, 'needs_clarification')  # the assessment's own state

    def test_a_second_review_stage_reached_without_the_request_check_never_resends_it(self):
        # a review2 queued another way (one an earlier state of this code queued, or a Resume of one cancelled before
        # it ran): the stage meets the failed request itself
        encounter_id, second = self.failed_then_addendum()
        sent = self.sent()
        encounter = self.encounter(encounter_id)
        job = jobs.enqueue(models.Job.REVIEW2, encounter=encounter, revision=encounter.current_revision,
                           context=encounter.current_context, provider_run=encounter.current_assessment.provider_run,
                           key='review2:queued-another-way', requested_by=self.reviewer)
        drain()
        job.refresh_from_db()
        self.assertEqual(job.state, models.Job.SUCCEEDED)
        self.assertIn('failed', job.result.get('skipped', ''))
        self.assertEqual(self.sent(), sent)
        self.assertEqual(self.runs(encounter_id, purpose=models.ProviderRun.SECOND_REVIEW), [second])

    def test_every_later_addendum_too(self):
        encounter_id, second = self.failed_then_addendum()
        for number in (3, 4):
            reply = self.post(f'/api/encounters/{encounter_id}/addenda',
                              {**ADDENDUM, 'text': f'Countersigned (fictional), copy {number}.'})
            self.assertEqual(reply.status_code, 201, reply.content)
            drain()
            self.assertEqual(self.ask(encounter_id).status_code, 409)
            drain()
        self.assertEqual(self.shas().count(second.request_sha256), 1)

    def test_control_an_answered_second_review_is_reused_on_the_next_revision(self):
        encounter_id, second = self.failed_then_addendum(second_outcome='succeeded')
        sent = self.sent()
        # revision 2 has had no second review: asked for, the retained answer is reused and nothing is sent
        self.assertEqual(self.ask(encounter_id).status_code, 201)
        drain()
        self.assertEqual(self.sent(), sent)
        reused = self.runs(encounter_id, purpose=models.ProviderRun.SECOND_REVIEW)[-1]
        self.assertEqual((reused.sent, reused.reused_from_id), (False, second.pk))
        self.assertEqual(self.selected(encounter_id), {'45385': 'primary', '45380': 'second_review'})

    def test_control_a_changed_excerpt_asks_its_one_second_review(self):
        # without the later section the addendum extends the excerpt: another request, made once when asked for
        encounter_id = self.create(REPORT)
        drain()
        self.provider.outcomes = ['failed']
        self.assertEqual(self.ask(encounter_id).status_code, 201)
        drain()
        [failed] = self.runs(encounter_id, purpose=models.ProviderRun.SECOND_REVIEW)
        reply = self.post(f'/api/encounters/{encounter_id}/addenda',
                          {**ADDENDUM, 'text': 'The fictional biopsy site was marked with a tattoo.'})
        self.assertEqual(reply.status_code, 201, reply.content)
        drain()
        offered = self.detail(encounter_id)['second_review']
        self.assertTrue(offered['available'], offered)
        sent = self.sent()
        self.assertEqual(self.ask(encounter_id).status_code, 201)
        drain()
        self.assertEqual(self.sent(), sent + 1)
        self.assertNotEqual(self.shas()[-1], failed.request_sha256)
        self.assertEqual(self.ask(encounter_id).status_code, 409)  # and once only


# --- sends-2: a FAILED primary request is never sent again, whatever came between -------------------------------------

@override_settings(**LIVE)
class FailedPrimaryRequestTests(Steps):
    """sends-2: an undated report's request failed; a member's date was sent; going back (clearing the date, or the date
    of a request that failed) SENT the failed request again, byte-identical, because whether the request changed was
    decided against the newest run only and the retained-result lookup matches only a SUCCEEDED run. A reconciliation's
    one released attempt spent itself the same way."""

    def test_a_cleared_member_date_after_a_failed_dateless_request(self):
        self.provider.outcomes = ['failed']
        encounter_id = self.create(UNDATED)
        drain()
        [failed] = self.runs(encounter_id)
        self.context(encounter_id, service_date=DATE)  # another request: sent once, answered
        self.assertEqual(self.sent(), 2)
        self.context(encounter_id, service_date='')
        self.assertEqual(self.sent(), 2)
        self.assertEqual(self.shas().count(failed.request_sha256), 1)
        self.assert_failed_run_stands(encounter_id, failed)
        self.context(encounter_id, service_date=DATE)  # the answered date again: its answer, nothing sent
        self.assertEqual(self.sent(), 2)
        self.assertEqual(self.encounter(encounter_id).current_assessment.provider_run.state,
                         models.ProviderRun.SUCCEEDED)

    def test_a_date_round_trip_back_to_a_failed_date(self):
        encounter_id = self.create(UNDATED)
        drain()
        self.provider.outcomes = ['failed']
        self.context(encounter_id, service_date=DATE)
        failed = self.runs(encounter_id)[-1]
        self.assertEqual((failed.state, failed.service_date), (models.ProviderRun.FAILED, date.fromisoformat(DATE)))
        self.context(encounter_id, service_date=OTHER_DATE)
        self.assertEqual(self.sent(), 3)
        self.context(encounter_id, service_date=DATE)
        self.assertEqual(self.sent(), 3)
        self.assertEqual(self.shas().count(failed.request_sha256), 1)
        self.assert_failed_run_stands(encounter_id, failed)

    def test_a_reconciliations_released_attempt_never_resends_a_failed_request(self):
        encounter_id = self.create(UNDATED)
        drain()
        self.provider.outcomes = ['failed']
        self.context(encounter_id, service_date=DATE)
        failed = self.runs(encounter_id)[-1]
        self.provider.outcomes = ['unknown']
        self.context(encounter_id, service_date=OTHER_DATE)
        self.context(encounter_id, service_date=DATE)  # blocked while the unknown outcome stands: nothing sent
        self.assertEqual(self.sent(), 3)
        self.assertEqual(self.encounter(encounter_id).state, 'provider_unknown')
        self.reconcile(encounter_id)
        self.assertEqual(self.sent(), 3)
        self.assertEqual(self.shas().count(failed.request_sha256), 1)
        self.assert_failed_run_stands(encounter_id, failed)

    def test_toggling_dates_over_failing_requests_sends_each_request_once(self):
        self.provider.outcomes = ['failed'] * 10
        encounter_id = self.create(UNDATED)
        drain()
        for value in (DATE, '', DATE, '', DATE):
            self.context(encounter_id, service_date=value)
        self.assertEqual(self.sent(), 2)
        self.assertEqual(len(set(self.shas())), 2)
        self.assertEqual(self.encounter(encounter_id).state, 'provider_failed')

    def test_control_another_date_is_sent_once(self):
        self.provider.outcomes = ['failed', 'failed']
        encounter_id = self.create(UNDATED)
        drain()
        self.context(encounter_id, service_date=DATE)
        self.context(encounter_id, service_date=OTHER_DATE)
        self.assertEqual(self.sent(), 3)
        self.assertEqual(len(set(self.shas())), 3)
        self.assertEqual(self.dates_sent(), [f'Date of service: {DATE}', f'Date of service: {OTHER_DATE}'])

    def test_control_an_answered_round_trip_is_reused(self):
        encounter_id = self.create(UNDATED)
        drain()
        self.context(encounter_id, service_date=DATE)
        self.context(encounter_id, service_date='')
        self.assertEqual(self.sent(), 2)
        self.assertEqual(self.encounter(encounter_id).current_assessment.provider_run.state,
                         models.ProviderRun.SUCCEEDED)

    def test_a_released_attempt_that_failed_is_never_sent_a_third_time(self):
        self.provider.outcomes = ['unknown', 'failed']
        encounter_id = self.create(UNDATED)
        drain()
        self.reconcile(encounter_id)  # the one released attempt: the same request, sent once more, and it failed
        failed = self.runs(encounter_id)[-1]
        self.assertEqual((failed.state, failed.request_sha256), (models.ProviderRun.FAILED, self.shas()[0]))
        self.context(encounter_id, setting='office')
        self.context(encounter_id, service_date=DATE)
        self.context(encounter_id, service_date='')
        self.assertEqual(self.sent(), 3)
        self.assertEqual(self.shas().count(failed.request_sha256), 2)
        self.assert_failed_run_stands(encounter_id, failed)

    def test_control_a_reconciled_unknown_request_is_made_once_more(self):
        # the request whose outcome is unknown is the one a reconciliation releases: sent once more, once
        self.provider.outcomes = ['unknown']
        encounter_id = self.create(UNDATED)
        drain()
        self.reconcile(encounter_id)
        self.assertEqual(self.sent(), 2)
        self.assertEqual(self.shas()[0], self.shas()[1])
        self.assertEqual(self.encounter(encounter_id).current_assessment.provider_run.state,
                         models.ProviderRun.SUCCEEDED)

    def test_control_another_encounter_sends_its_own_request(self):
        # the rule reads one document's runs: the same report uploaded again is a member's new request
        self.provider.outcomes = ['failed']
        first = self.create(UNDATED)
        drain()
        second = self.create(UNDATED)
        drain()
        self.assertEqual(self.sent(), 2)
        self.assertEqual(self.shas()[0], self.shas()[1])
        self.assertEqual(self.encounter(first).state, 'provider_failed')
        self.assertNotEqual(self.encounter(second).state, 'provider_failed')


# --- the one rule: whatever the failed request was made for, on whichever revision -----------------------------------

@override_settings(**LIVE)
class WhateverItWasMadeForTests(Steps):
    """The send door reads every run of the encounter that sent the request, whatever it was made for and on whichever
    revision. No upload or member action reaches these shapes today (an addendum's text extends its parent's, and a
    second review never repeats its own primary request), so each test records the failed run itself."""

    def failed_run(self, revision, request, purpose):
        return models.ProviderRun.objects.create(
            encounter=revision.encounter, revision=revision, provider=self.provider.name,
            adapter_version=self.provider.adapter_version, request_sha256=request.canonical_sha256,
            request_body=request.body, contexts=list(request.contexts), state=models.ProviderRun.FAILED, sent=True,
            http_status=500, error='HTTP 500 from the provider (synthetic).', requested_by=self.reviewer,
            service_date=date.fromisoformat(DATE), purpose=purpose, started_at=timezone.now(),
            finished_at=timezone.now())

    def test_a_second_review_whose_request_a_failed_primary_run_carried(self):
        encounter_id = self.create(REPORT)
        drain()
        encounter = self.encounter(encounter_id)
        revision = encounter.current_revision
        span = jobs._second_review_items(encounter.current_assessment)[1]
        excerpt = self.provider.build_request(revision.text[span[0]:span[1]], date.fromisoformat(DATE))
        self.failed_run(revision, excerpt, models.ProviderRun.PRIMARY)
        offered = self.detail(encounter_id)['second_review']
        self.assertFalse(offered['available'], offered)
        self.assertIn('failed', offered['reason'])
        self.assertEqual(self.ask(encounter_id).status_code, 409)
        jobs.enqueue(models.Job.REVIEW2, encounter=encounter, revision=revision, context=encounter.current_context,
                     provider_run=encounter.current_assessment.provider_run, key='review2:queued-another-way',
                     requested_by=self.reviewer)
        drain()
        self.assertEqual(self.sent(), 1)
        self.assertFalse(models.ProviderRun.objects.filter(encounter_id=encounter_id, purpose='second_review').exists())

    def assert_recorded_not_resent(self, encounter_id, sent, failed):
        self.assertEqual(self.sent(), sent)  # nothing new
        # the predict's own not-sent run, on this revision, as for a failed primary request of this revision
        self.assert_failed_run_stands(encounter_id, failed)

    def test_a_primary_whose_request_a_failed_second_review_carried(self):
        encounter_id = self.create(UNDATED)
        drain()
        revision = self.encounter(encounter_id).current_revision
        dated = self.provider.build_request(revision.text, date.fromisoformat(DATE))
        failed = self.failed_run(revision, dated, models.ProviderRun.SECOND_REVIEW)
        self.context(encounter_id, service_date=DATE)
        self.assert_recorded_not_resent(encounter_id, sent=1, failed=failed)

    def test_a_primary_whose_request_failed_on_an_earlier_revision(self):
        encounter_id = self.create(UNDATED)
        drain()
        first = self.encounter(encounter_id).current_revision
        reply = self.post(f'/api/encounters/{encounter_id}/addenda', ADDENDUM)
        self.assertEqual(reply.status_code, 201, reply.content)
        drain()
        self.assertEqual(self.sent(), 2)  # the upload's request and the addendum revision's
        revision = self.encounter(encounter_id).current_revision
        failed = self.failed_run(first, self.provider.build_request(revision.text, date.fromisoformat(DATE)),
                                 models.ProviderRun.PRIMARY)
        self.context(encounter_id, service_date=DATE)
        self.assert_recorded_not_resent(encounter_id, sent=2, failed=failed)


# --- round 7c8, the P1SENDS skeptic: a reuse is not a send, and the run in use is the outcome that stands ------------

@override_settings(**LIVE)
class RetainedSecondReviewIsReusedTests(Steps):
    """Skeptic sk:1 (capability loss; 5.4 Reuse): the second-review blocker refused, as a request this document had
    sent and that failed, an ask whose identical request another encounter of the workspace had since had answered - an
    answer stage_review2 reuses with nothing sent, as b611b557a did. The refusal came before any retained answer was
    considered, so the offer and the ask refused what the stage serves for free, and the biopsy stayed unresolved."""

    def failed_here_answered_elsewhere(self, *, elsewhere='succeeded'):
        first = self.create(TRAILED)
        drain()
        self.provider.outcomes = ['failed']
        self.assertEqual(self.ask(first).status_code, 201)
        drain()
        [failed] = self.runs(first, purpose=models.ProviderRun.SECOND_REVIEW)
        self.assertEqual((failed.state, failed.sent), (models.ProviderRun.FAILED, True))
        other = self.create(TRAILED)  # the same report uploaded again: its primary answer is reused
        drain()
        self.provider.outcomes = [elsewhere]
        self.assertEqual(self.ask(other).status_code, 201)
        drain()
        [answered] = self.runs(other, purpose=models.ProviderRun.SECOND_REVIEW)
        self.assertEqual((answered.state, answered.sent, answered.request_sha256),
                         (elsewhere, True, failed.request_sha256))
        reply = self.post(f'/api/encounters/{first}/addenda', ADDENDUM)  # leaves the excerpt as it was
        self.assertEqual(reply.status_code, 201, reply.content)
        drain()
        self.assertEqual(self.selected(first), {'45385': 'primary'})
        return first, failed, answered

    def test_an_ask_whose_request_was_answered_elsewhere_is_served_by_that_answer(self):
        first, failed, answered = self.failed_here_answered_elsewhere()
        sent = self.sent()
        offered = self.detail(first)['second_review']
        self.assertTrue(offered['available'], offered)
        self.assertEqual(offered['reason'], '')
        self.assertEqual(self.ask(first).status_code, 201)
        drain()
        self.assertEqual(self.sent(), sent)  # a reuse is not a send
        reused = self.runs(first, purpose=models.ProviderRun.SECOND_REVIEW)[-1]
        self.assertEqual((reused.state, reused.sent, reused.reused_from_id, reused.revision.number),
                         (models.ProviderRun.SUCCEEDED, False, answered.pk, 2))
        self.assertEqual(self.selected(first), {'45385': 'primary', '45380': 'second_review'})
        self.assertEqual(self.shas().count(failed.request_sha256), 2)  # this encounter's attempt and the other's

    def test_control_the_stage_serves_the_same_ask(self):
        # held before the repair too: the stage, reached directly, reuses the retained answer and sends nothing
        first, failed, answered = self.failed_here_answered_elsewhere()
        sent = self.sent()
        encounter = self.encounter(first)
        job = jobs.enqueue(models.Job.REVIEW2, encounter=encounter, revision=encounter.current_revision,
                           context=encounter.current_context, provider_run=encounter.current_assessment.provider_run,
                           key='review2:queued-another-way', requested_by=self.reviewer)
        drain()
        job.refresh_from_db()
        self.assertEqual(job.result.get('second_review'), 'reused', job.result)
        self.assertEqual(self.sent(), sent)
        self.assertEqual(self.selected(first), {'45385': 'primary', '45380': 'second_review'})

    def test_control_an_answer_that_failed_elsewhere_releases_nothing(self):
        # only an answer is reused: the other encounter's own attempt failed too, so nothing is retained to serve the
        # ask, and the request that failed here is refused and never sent again
        first, failed, other = self.failed_here_answered_elsewhere(elsewhere='failed')
        sent = self.sent()
        offered = self.detail(first)['second_review']
        self.assertFalse(offered['available'], offered)
        self.assertIn('failed', offered['reason'])
        self.assertEqual(self.ask(first).status_code, 409)
        drain()
        self.assertEqual(self.sent(), sent)
        self.assertEqual(self.runs(first, purpose=models.ProviderRun.SECOND_REVIEW), [failed])


@override_settings(**LIVE)
class TheRunInUseIsTheOutcomeThatStandsTests(Steps):
    """Skeptic sk:2 (rollback safety; class 1 through a rollback) and sk:3: where the send door met a request that had
    FAILED, the predict re-assessed with that OLDER run and recorded nothing; and a cleared date whose newest run
    carried no request re-assessed past it. Either way the revision's newest finished run - the run in use this
    revision reads at every later save, and the one the installed revision 057a7d39 reads once a rollback restores
    it - was not the run whose outcome stood. There, a member's setting save SENT the byte-identical request that had
    failed; here, a member date whose request never reached the provider was never attempted again."""

    def assert_a_setting_save_sends_nothing(self, encounter_id, run):
        sent = self.sent()
        self.context(encounter_id, setting='office')
        self.assertEqual(self.sent(), sent)
        self.assertEqual(self.encounter(encounter_id).current_assessment.provider_run_id, run.pk)

    def test_a_cleared_date_after_an_answered_one(self):
        # the skeptic's shape A: the dateless request FAILED, the member's date was sent and answered, then cleared
        self.provider.outcomes = ['failed']
        encounter_id = self.create(UNDATED)
        drain()
        [failed] = self.runs(encounter_id)
        self.context(encounter_id, service_date=DATE)
        self.assertEqual(self.runs(encounter_id)[-1].state, models.ProviderRun.SUCCEEDED)
        self.context(encounter_id, service_date='')
        self.assertEqual(self.sent(), 2)
        run = self.assert_failed_run_stands(encounter_id, failed)
        self.assert_a_setting_save_sends_nothing(encounter_id, run)

    def test_a_cleared_date_whose_request_could_not_be_built(self):
        # the skeptic's shape B (sends-0's rows): the dated request was over the byte limit, so its run carries none
        self.provider.max_request_bytes = 4_000
        self.provider.outcomes = ['failed']
        encounter_id = self.create(sized_text(4_000))
        drain()
        [failed] = self.runs(encounter_id)
        self.context(encounter_id, service_date=DATE)
        unbuilt = self.runs(encounter_id)[-1]
        self.assertEqual((unbuilt.state, unbuilt.request_sha256), (models.ProviderRun.NOT_SENT, ''))
        self.context(encounter_id, service_date='')
        self.assertEqual(self.sent(), 1)
        run = self.assert_failed_run_stands(encounter_id, failed)
        self.assert_a_setting_save_sends_nothing(encounter_id, run)

    def test_a_cleared_date_after_a_second_review(self):
        # a second review newer than every primary run (the installed revision has no purpose column)
        self.provider.outcomes = ['failed']
        encounter_id = self.create(UNDATED)
        drain()
        [failed] = self.runs(encounter_id)
        self.context(encounter_id, service_date=DATE)
        self.assertEqual(self.ask(encounter_id).status_code, 201)
        drain()
        self.assertEqual(self.runs(encounter_id)[-1].purpose, models.ProviderRun.SECOND_REVIEW)
        self.context(encounter_id, service_date='')
        self.assertEqual(self.sent(), 3)
        run = self.assert_failed_run_stands(encounter_id, failed)
        self.assert_a_setting_save_sends_nothing(encounter_id, run)

    def test_a_member_date_never_sent_is_attempted_when_it_is_set_again(self):
        # sk:3: the dated request never reached the provider (the token endpoint refused); after the round trip the
        # outcome that stands is the dateless request's, so the member's date is a request still to be made
        self.provider.outcomes = ['failed']
        encounter_id = self.create(UNDATED)
        drain()
        [failed] = self.runs(encounter_id)
        self.provider.outcomes = ['not_sent']
        self.context(encounter_id, service_date=DATE)
        refused = self.runs(encounter_id)[-1]
        self.assertEqual((refused.state, refused.sent, refused.service_date),
                         (models.ProviderRun.NOT_SENT, False, date.fromisoformat(DATE)))
        self.context(encounter_id, service_date='')
        self.assertEqual(self.sent(), 2)
        self.context(encounter_id, service_date=DATE)  # the provider answers from here on
        dated = [request.canonical_sha256 for request in self.provider.requests if len(request.contexts) == 2]
        self.assertEqual(dated, [refused.request_sha256] * 2)
        run = self.encounter(encounter_id).current_assessment.provider_run
        self.assertEqual((run.state, run.sent, run.service_date),
                         (models.ProviderRun.SUCCEEDED, True, date.fromisoformat(DATE)))
        self.assertEqual(self.shas().count(failed.request_sha256), 1)

    def test_control_the_same_steps_after_an_answered_dateless_request(self):
        # held before the repair too: whether the member's date is attempted never depends on another request's outcome
        encounter_id = self.create(UNDATED)
        drain()
        self.provider.outcomes = ['not_sent']
        self.context(encounter_id, service_date=DATE)
        self.context(encounter_id, service_date='')
        self.context(encounter_id, service_date=DATE)
        self.assertEqual(len([request for request in self.provider.requests if len(request.contexts) == 2]), 2)
        self.assertEqual(self.encounter(encounter_id).current_assessment.provider_run.state,
                         models.ProviderRun.SUCCEEDED)

    def test_a_run_without_a_request_stands_as_the_installed_revision_reads_it(self):
        # the round-4 pin, restored (sk:2's second place): the not-built run is the newest finished run on both
        # revisions; nothing it answers, and the send door - not the run in use - keeps the failed request unsent
        self.provider.max_request_bytes = 4_000
        self.provider.outcomes = ['failed']
        encounter_id = self.create(sized_text(4_000))
        drain()
        self.context(encounter_id, service_date=DATE)
        unbuilt = self.runs(encounter_id)[-1]
        revision = self.encounter(encounter_id).current_revision
        self.assertEqual(jobs._run_in_use(revision), unbuilt)
        self.assertEqual(installed_run_in_use(revision), unbuilt)
