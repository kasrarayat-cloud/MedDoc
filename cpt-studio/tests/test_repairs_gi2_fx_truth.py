"""Fix round gi2, agent 'truth' (refutation lens 'truth', finding truth-1; must-fix class 3, a screen that misstates
persisted state). Synthetic data only; the provider is an in-process stand-in (no network); node runs the shipped
app.js, so the queue is checked as it renders.

The review queue's 'second_review' reason - "Second review available" on a queued row - said a second review could be
asked for on an encounter whose ask the server refuses: the reviewer's ask was queued, and its review2 stage then failed
before it recorded a run (the asking reviewer lost access first), or was stopped, expired or left by a dead worker
before it ran. request_second_review queues ONE stage per key (review2:<revision>:<assessment>, plus the count of
second reviews that conclusively never reached the provider), so once that key is used every ask is refused with
"A second review was already requested for this assessment." - but jobs._second_review_blocker said '' there, so
second_review_status served available=true and the queue claimed it (the review page itself never offered it again:
askedSecondReview). The installed tree made no queue claim at all.

The fix: _second_review_blocker is the one predicate the API accepts an ask by - the bounds, then the ask's own key -
so the encounter view's available flag, the queue reason and POST second-review can never disagree. Where only Resume
runs the stopped stage, the queue says nothing about a second review (the page says "Resume processing runs it once").
"""
import re
from datetime import timedelta
from unittest import mock

from django.conf import settings
from django.test import Client, override_settings
from django.utils import timezone

from studio import jobs, models
from tests.test_pipeline_api import drain
from tests.test_repairs_7c8_p1sends import Steps
from tests.test_repairs_ec5_reportfacts import browser
from tests.test_services_second_review import LIVE, REPORT

QUEUE = '{queue: app.listBody("queue", data.rows), described: app.listDescription("queue", data.rows)}'
OFFERED = 'Second review available'
ASKED = 'A second review was already requested for this assessment.'


def row_meta(html):
    return re.findall(r'<small>([^<]*)</small>', html)


@override_settings(**LIVE)
class TheQueueOffersOnlyAnAskTheServerAcceptsTests(Steps):
    """Each test ends by making the ask itself: the queue's claim is judged against what POST second-review answers."""

    def rows(self):
        return self.client.get('/api/encounters').json()['encounters']

    def row(self, encounter_id):
        (row,) = [r for r in self.rows() if r['id'] == encounter_id]
        return row

    def queue(self):
        return browser(QUEUE, {'rows': self.rows()})

    def review_page(self, encounter_id):
        return browser('app.documentedServices(data.doc)', {'doc': self.detail(encounter_id)})

    def review2(self, encounter_id):
        return models.Job.objects.filter(encounter_id=encounter_id, kind=models.Job.REVIEW2).order_by('created_at')

    def second_runs(self, encounter_id):
        return list(models.ProviderRun.objects.filter(encounter_id=encounter_id,
                                                      purpose=models.ProviderRun.SECOND_REVIEW).order_by('created_at'))

    def assessed(self):
        encounter_id = self.create(REPORT)
        drain()
        self.assertTrue(self.detail(encounter_id)['second_review']['available'])
        self.assertIn('second_review', self.row(encounter_id)['queue_reasons'])
        return encounter_id

    def asked(self, encounter_id):
        self.assertEqual(self.ask(encounter_id).status_code, 201)
        return self.review2(encounter_id).get()

    def assert_not_offered(self, encounter_id):
        """No list, view or screen offers the ask the server refuses; the encounter stays queued for its coding."""
        row = self.row(encounter_id)
        self.assertNotIn('second_review', row['queue_reasons'])
        self.assertIn('incomplete', row['queue_reasons'])  # still waits on a member (RC6), only the claim is gone
        detail = self.detail(encounter_id)
        self.assertEqual(detail['queue_reasons'], row['queue_reasons'])
        self.assertEqual((detail['second_review']['available'], detail['second_review']['reason']), (False, ASKED))
        shown = self.queue()
        self.assertIn(f'#doc/{encounter_id}', shown['queue'])
        self.assertNotIn(OFFERED, shown['queue'])
        self.assertIn('Coding incomplete', ' '.join(row_meta(shown['queue'])), shown['queue'])
        self.assertNotIn('data-action="second-review"', self.review_page(encounter_id))
        sent = len(self.provider.requests)
        reply = self.ask(encounter_id)
        self.assertEqual((reply.status_code, reply.json().get('error')), (409, ASKED))
        drain()
        self.assertEqual(len(self.provider.requests), sent)  # the refused ask sent nothing
        return detail

    # --- the normal case: the claim is an ask the server accepts ----------------------------------------------------

    def test_normal_the_queue_offers_the_ask_and_the_server_accepts_it(self):
        encounter_id = self.assessed()
        shown = self.queue()
        self.assertIn(OFFERED, ' '.join(row_meta(shown['queue'])))
        self.assertIn('data-action="second-review"', self.review_page(encounter_id))
        sent = len(self.provider.requests)
        job = self.asked(encounter_id)
        self.assertEqual(job.state, models.Job.QUEUED)
        self.assertNotIn('second_review', self.row(encounter_id)['queue_reasons'])  # processing: waits on its stages
        drain()
        self.assertEqual(len(self.provider.requests), sent + 1)
        self.assertEqual([r.state for r in self.second_runs(encounter_id)], [models.ProviderRun.SUCCEEDED])
        self.assertNotIn('second_review', self.row(encounter_id)['queue_reasons'])  # made once per document and date

    def test_control_after_a_second_review_that_was_never_sent_the_offer_returns_and_is_accepted(self):
        # A second review that conclusively never reached the provider releases another ask under a new key
        # (refutation gi2, eus2 L1): the used key of the first ask must not hide it.
        self.provider.outcomes = ['succeeded', 'not_sent']
        encounter_id = self.assessed()
        self.asked(encounter_id)
        drain()
        self.assertEqual([r.state for r in self.second_runs(encounter_id)], [models.ProviderRun.NOT_SENT])
        detail = self.detail(encounter_id)
        self.assertEqual((detail['second_review']['available'], detail['second_review']['reason']), (True, ''))
        self.assertIn('second_review', self.row(encounter_id)['queue_reasons'])
        self.assertIn(OFFERED, self.queue()['queue'])
        self.assertEqual(self.ask(encounter_id).status_code, 201)
        drain()
        self.assertEqual([r.state for r in self.second_runs(encounter_id)],
                         [models.ProviderRun.NOT_SENT, models.ProviderRun.SUCCEEDED])

    # --- failed: no action can obtain it, and nothing claims it can -------------------------------------------------

    def test_failed_the_asking_reviewer_lost_access_before_the_stage_ran(self):
        encounter_id = self.assessed()
        asker = models.User.objects.create_user('asker', password='x')
        membership = models.Membership.objects.create(user=asker, workspace=self.ws, role=models.Membership.REVIEWER)
        other = Client(enforce_csrf_checks=False)
        other.force_login(asker)
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(other.post(f'/api/encounters/{encounter_id}/second-review').status_code, 201)
        membership.active = False
        membership.save(update_fields=['active'])
        drain()
        job = self.review2(encounter_id).get()
        self.assertEqual(job.state, models.Job.FAILED)
        self.assertEqual(self.second_runs(encounter_id), [])
        detail = self.assert_not_offered(encounter_id)
        self.assertFalse(detail['pipeline']['can_resume'])
        self.assertIn('Second provider review did not complete', self.review_page(encounter_id))
        reply = self.post(f'/api/encounters/{encounter_id}/resume')
        self.assertEqual(reply.status_code, 409)

    def test_failed_the_reviewer_was_demoted_before_the_stage_ran(self):
        encounter_id = self.assessed()
        self.asked(encounter_id)
        models.Membership.objects.filter(user=self.reviewer).update(role=models.Membership.VIEWER)
        drain()
        models.Membership.objects.filter(user=self.reviewer).update(role=models.Membership.REVIEWER)
        self.assertEqual(self.review2(encounter_id).get().state, models.Job.FAILED)
        self.assert_not_offered(encounter_id)

    # --- stopped, expired, swept: only Resume runs it, and the queue says nothing about a second review -------------

    def assert_resume_runs_it_once(self, encounter_id):
        page = self.review_page(encounter_id)
        self.assertIn('Second provider review stopped', page)
        self.assertIn('Resume processing runs it once.', page)
        sent = len(self.provider.requests)
        self.assertEqual(self.post(f'/api/encounters/{encounter_id}/resume').status_code, 201)
        drain()
        self.assertEqual(len(self.provider.requests), sent + 1)
        self.assertEqual([r.state for r in self.second_runs(encounter_id)], [models.ProviderRun.SUCCEEDED])
        self.assertNotIn('second_review', self.row(encounter_id)['queue_reasons'])

    def test_stopped_before_the_stage_ran(self):
        encounter_id = self.assessed()
        self.asked(encounter_id)
        self.assertEqual(self.post(f'/api/encounters/{encounter_id}/stop').status_code, 200)
        drain()
        job = self.review2(encounter_id).get()
        self.assertEqual((job.state, job.error), (models.Job.CANCELLED, 'Stopped by a workspace member.'))
        detail = self.assert_not_offered(encounter_id)
        self.assertEqual(detail['state'], 'stopped')
        self.assertTrue(detail['pipeline']['can_resume'])
        self.assertEqual(self.client.get('/api/session').json()['counts']['queue'], 1)  # RC6: incomplete, a decision
        self.assert_resume_runs_it_once(encounter_id)

    def test_expired_before_the_stage_could_start(self):
        encounter_id = self.assessed()
        self.asked(encounter_id)
        self.review2(encounter_id).update(deadline_at=timezone.now() - timedelta(seconds=1))
        drain()
        job = self.review2(encounter_id).get()
        self.assertEqual(job.state, models.Job.CANCELLED)
        self.assertIn('expired', job.error)
        self.assert_not_offered(encounter_id)
        self.assert_resume_runs_it_once(encounter_id)

    def test_swept_while_running_by_the_stale_stage_sweep(self):
        encounter_id = self.assessed()
        self.asked(encounter_id)
        job = jobs.claim_next()
        self.assertEqual((job.kind, job.state), (models.Job.REVIEW2, models.Job.RUNNING))
        models.Job.objects.filter(pk=job.pk).update(
            started_at=timezone.now() - timedelta(seconds=settings.STALE_RUNNING_SECONDS + 60))
        jobs.mark_stale()
        job.refresh_from_db()
        self.assertEqual(job.state, models.Job.CANCELLED)
        self.assertEqual(self.second_runs(encounter_id), [])
        self.assert_not_offered(encounter_id)
        self.assert_resume_runs_it_once(encounter_id)


@override_settings(**LIVE)
class OnePredicateTests(Steps):
    """The status the encounter view and the queue read is the predicate the ask is refused by: _second_review_blocker
    names a used key with request_second_review's own refusal, and only once every other bound passed, so no reason it
    gave before changes (the key is consulted last); the key is request_second_review's own (_second_review_key)."""

    def test_the_used_key_is_the_last_bound_and_its_reason_is_the_asks_refusal(self):
        encounter_id = self.create(REPORT)
        drain()
        self.assertEqual(self.ask(encounter_id).status_code, 201)
        self.assertEqual(self.post(f'/api/encounters/{encounter_id}/stop').status_code, 200)
        drain()
        encounter = models.Encounter.objects.get(pk=encounter_id)
        revision, assessment = encounter.current_revision, encounter.current_assessment
        args = (encounter, revision, encounter.current_context, assessment)
        (job,) = models.Job.objects.filter(encounter_id=encounter_id, kind=models.Job.REVIEW2)
        self.assertEqual(job.idempotency_key, jobs._second_review_key(revision, assessment))
        self.assertEqual(jobs.SECOND_REVIEW_ASKED, ASKED)
        self.assertEqual(jobs._second_review_bounds(*args), '')
        self.assertEqual(jobs._second_review_blocker(*args), ASKED)
        self.assertEqual((jobs.second_review_status(encounter)['available'],
                          jobs.second_review_status(encounter)['reason']), (False, ASKED))
        with self.assertRaisesMessage(jobs.Refused, ASKED):
            jobs.request_second_review(encounter, self.reviewer)
        # a bound that refuses first keeps its own reason: the used key never hides it
        with mock.patch('studio.jobs.get_provider', return_value=None):
            self.assertEqual(jobs._second_review_blocker(*args), 'The provider is not configured on this installation.')
