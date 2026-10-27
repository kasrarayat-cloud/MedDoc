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

    def assert_failed_run_stands(self, encounter_id, run):
        """The re-check met the request that failed and re-assessed with it: provider_failed, and the screen names that
        run (nothing new was recorded for it, nothing was sent)."""
        encounter = self.encounter(encounter_id)
        self.assertEqual(encounter.state, 'provider_failed')
        self.assertEqual(encounter.current_assessment.provider_run_id, run.pk)
        self.assertEqual(encounter.current_assessment.context_id, encounter.current_context_id)
        self.assertEqual(self.detail(encounter_id)['state_run'], str(run.pk))
        self.assertEqual(review.latest_job(encounter).kind, models.Job.ASSESS)


# --- sends-0: a run that carries no request is no request's outcome --------------------------------------------------

@override_settings(**LIVE)
class RunWithoutARequestIsNoOutcomeTests(Steps):
    """sends-0: a request failed; a date whose request could not be built recorded a not-sent run with no request (and
    sent nothing); clearing the date then SENT the byte-identical failed request again, because the run without a
    request stood as the run in use and answers no request (the sibling of the held run, ec5 integration)."""

    def sized_text(self, limit):
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
        self.assertLessEqual(body_bytes(stored), limit)
        self.assertGreater(body_bytes(stored, date.fromisoformat(DATE)), limit)
        self.assertLessEqual(len(text), settings.MAX_PASTE_CHARS)
        return text

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
        self.assert_failed_run_stands(encounter_id, failed)
        self.assertEqual(len(self.runs(encounter_id)), 2)

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

    def test_the_run_without_a_request_is_not_the_run_in_use(self):
        text = self.sized_text(4_000)
        self.provider.max_request_bytes = 4_000
        self.provider.outcomes = ['failed']
        encounter_id = self.create(text)
        drain()
        self.context(encounter_id, service_date=DATE)
        failed, unbuilt = self.runs(encounter_id)
        self.assertEqual(unbuilt.request_sha256, '')
        self.assertEqual(jobs._run_in_use(self.encounter(encounter_id).current_revision), failed)

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

    def assert_recorded_not_resent(self, encounter_id, sent):
        self.assertEqual(self.sent(), sent)  # nothing new
        encounter = self.encounter(encounter_id)
        run = encounter.current_assessment.provider_run
        self.assertEqual((run.state, run.request_sha256, run.sent, run.revision_id),
                         (models.ProviderRun.NOT_SENT, '', False, encounter.current_revision_id))
        self.assertEqual(run.error, jobs.FAILED_BEFORE_MESSAGE)
        self.assertEqual(encounter.state, 'provider_failed')
        self.assertEqual(self.detail(encounter_id)['state_run'], str(run.pk))

    def test_a_primary_whose_request_a_failed_second_review_carried(self):
        encounter_id = self.create(UNDATED)
        drain()
        revision = self.encounter(encounter_id).current_revision
        dated = self.provider.build_request(revision.text, date.fromisoformat(DATE))
        self.failed_run(revision, dated, models.ProviderRun.SECOND_REVIEW)
        self.context(encounter_id, service_date=DATE)
        self.assert_recorded_not_resent(encounter_id, sent=1)

    def test_a_primary_whose_request_failed_on_an_earlier_revision(self):
        encounter_id = self.create(UNDATED)
        drain()
        first = self.encounter(encounter_id).current_revision
        reply = self.post(f'/api/encounters/{encounter_id}/addenda', ADDENDUM)
        self.assertEqual(reply.status_code, 201, reply.content)
        drain()
        self.assertEqual(self.sent(), 2)  # the upload's request and the addendum revision's
        revision = self.encounter(encounter_id).current_revision
        self.failed_run(first, self.provider.build_request(revision.text, date.fromisoformat(DATE)),
                        models.ProviderRun.PRIMARY)
        self.context(encounter_id, service_date=DATE)
        self.assert_recorded_not_resent(encounter_id, sent=2)
