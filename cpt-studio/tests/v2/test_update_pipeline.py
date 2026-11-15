"""FINAL-V2 amendment 1 (docs/gemini-migration/AMENDMENT-1.md, adopted as DECISIONS D208): the codes are updated
automatically after a save - the pipeline's half (step 5b: studio/jobs.py, studio/provider_holds.py,
studio/providers/corti.py), driven by jobs.claim_next and jobs.run_job explicitly so every interleaving is deterministic.
TEXT-ONLY and SYNTHETIC: tests/v2/test_jobs.py's documents and scripted interpreter (design v2's own InterpreterV2 with
its one exchange answered here), the in-process FakeProvider for Corti, and a LEGACY fixture made by the installed
release's own chain (tests/legacy_chain.py: a legacy context and assessment, no EventInventory). Nothing is sent
anywhere.

11.1's tests whose subject is in step 5b's files, by id (the rest are named in the step's NOTES): U3 case A; U4 case B on
a legacy fixture; U5 rapid successive edits on a v2 and a legacy fixture at every stage boundary, and (a)-(e); U6 the
late finisher; U7 analyze's compare-and-set; U8 the restores (A17, A19); U9 Stop, Resume, worker death and the hold;
U12 the failures; U18 member acts and saves (A18); U20 the provider hold (A16, A20); U22 a chain re-run after
completion and A21.
"""
from __future__ import annotations

import hashlib
import json
from datetime import date, timedelta
from unittest import mock

from django.utils import timezone

from studio import interpretation, jobs, models, progress, provider_holds, review
from studio.interpretation import holds
from studio.providers.base import ProviderUnavailable
from studio.types import RawExchange
from tests.legacy_chain import legacy_chain
from tests.support import operator as ops
from tests.support import factories as f
from tests.v2.test_jobs import (APPRAISAL, BARE_429, EXAM, EXTRACTION, HTTP_402, HTTP_500, NOTE, POLYP, UNKNOWN,
                                PipelineCase, answered, body, note_answer)
from tests.v2.test_settle import colonoscopy

Run, Job = models.ProviderRun, models.Job
D1, D2, D3 = '2031-03-14', '2031-03-15', '2031-03-16'  # NOTE's own date, and two others a member may save
OFFICE, HOSPITAL = 'office', 'hospital_outpatient'

# A synthetic document that states no date of service (so a member's date is the effective date and no conflict): NOTE
# with its date line replaced by a plain sentence, the units in the same places.
UNDATED = ('SYNTHETIC COLONOSCOPY REPORT\n'                                              # S1
           'Synthetic record written for software tests only.\n'                          # S2
           'Endoscopist: Corvin Ashdale, MD (fictional)\n'                                # S3
           '\n'
           'Findings: The colonoscope was advanced to the cecum.\n')                      # S4
NOT_STATED = {'state': 'not_stated', 'value': '', 'sources': [], 'options': []}


def undated_answer():
    """UNDATED's pass-1 answer: NOTE's, its date of service not stated."""
    answer = colonoscopy(UNDATED)
    answer['encounter']['date_of_service'] = dict(NOT_STATED)
    return answer


MORE_ANSWERS = {UNDATED: undated_answer}


class CortiScript:
    """The in-process Corti whose outcomes are scripted per send (a RawExchange, or 'ok' for a 200 answer selecting
    45378 at EXAM), recording every request it was asked to send (``sent``: request sha256s)."""
    name, mode = 'corti', 'live'

    def __init__(self, *outcomes):
        from tests.test_pipeline_api import FakeProvider

        self.fake = FakeProvider([('45378', EXAM)])
        self.adapter_version = self.fake.adapter_version
        self.outcomes = list(outcomes)
        self.sent = []

    def build_request(self, text, service_date):
        return self.fake.build_request(text, service_date)

    def send(self, request, *, deadline_s):
        self.sent.append(request.canonical_sha256)
        outcome = self.outcomes.pop(0) if self.outcomes else 'ok'
        if outcome == 'ok':
            return self.fake.send(request, deadline_s=deadline_s)
        return outcome


def corti_refusal(status):
    """Corti's coding service answering ``status`` (sent, failed)."""
    data = json.dumps({'error': f'synthetic {status}'}).encode()
    return RawExchange(outcome='failed', sent=True, http_status=status, response_bytes=data,
                       response_sha256=hashlib.sha256(data).hexdigest(), latency_ms=5.0,
                       error=f'Corti answered HTTP {status}; the response body is retained.')


def token_refusal(status):
    """Corti's token endpoint answering ``status``: not sent, its status recorded (FINAL-V2 amendment 1, 7.3)."""
    return RawExchange(outcome='not_sent', sent=False, http_status=status,
                       error=f'Corti authentication was refused (HTTP {status}); no coding request was sent.')


LOCAL_NOT_SENT = RawExchange(outcome='not_sent', sent=False,
                             error='The Corti coding service could not be reached (ConnectError); nothing was sent.')


class UpdateCase(PipelineCase):
    """A v2 and a legacy fixture, and the saves and runs the amendment's tests read."""

    def scripted(self, **kwargs):
        interpreter = super().scripted(**kwargs)
        interpreter.answers.update(MORE_ANSWERS)
        return interpreter

    def new_workspace(self):
        """A workspace of its own for the next fixture (a stored answer is reused within a workspace only)."""
        self.ws = f.workspace(f'Synthetic practice {models.Workspace.objects.count() + 1}')
        f.member(self.ws, self.user, role=models.Membership.REVIEWER)
        return self.ws

    def setUp(self):
        super().setUp()
        self.corti = CortiScript()
        self.enterContext(mock.patch.object(jobs, 'get_provider', side_effect=lambda: self.provider_of()))
        self.disabled = False

    def provider_of(self):
        return None if self.disabled else self.corti

    def v2_fixture(self, text=NOTE, **upload):
        """An encounter whose first processing finished on design v2: fresh, its final assessment current."""
        encounter, _ = self.upload(text, **upload)
        self.drain()
        encounter.refresh_from_db()
        self.assertTrue(review.fresh(encounter))
        self.assertEqual(encounter.current_assessment.engine_version, interpretation.ENGINE_VERSION_V2)
        return encounter

    def legacy_fixture(self, text=NOTE):
        """An encounter the installed release's chain read and assessed (tests/legacy_chain.py): a legacy context and a
        legacy final assessment, no EventInventory; fresh."""
        with legacy_chain():
            encounter, _ = self.upload(text)
            self.drain()
        encounter.refresh_from_db()
        self.assertFalse(interpretation.is_new_context(encounter.current_context))
        self.assertFalse(interpretation.is_new_assessment(encounter.current_assessment))
        self.assertFalse(models.EventInventory.objects.filter(encounter=encounter).exists())
        self.assertTrue(review.fresh(encounter))
        self.interpreter.sent.clear()
        self.corti.sent.clear()
        return encounter

    def save(self, encounter, **values):
        encounter.refresh_from_db()
        return jobs.change_context(encounter, self.user, values)

    def fresh_row(self, encounter):
        return models.Encounter.objects.select_related('current_assessment', 'current_context').get(pk=encounter.pk)

    def gemini_sends(self):
        return list(self.interpreter.sent)

    def assertNoRequestSentTwice(self, encounter):  # noqa: N802 - unittest's naming
        sent = Run.objects.filter(encounter=encounter, sent=True).values_list('provider', 'purpose', 'request_sha256')
        self.assertEqual(len(list(sent)), len(set(sent)), list(sent))
        self.assertEqual(len(self.interpreter.sent), len(set(self.interpreter.sent)))
        self.assertEqual(len(self.corti.sent), len(set(self.corti.sent)))

    def assertSupersededSentNothing(self, encounter):  # noqa: N802 - unittest's naming
        """Every superseded stage of ``encounter`` recorded no run after its supersession (none created while it ran,
        since a superseded stage ends before any door that can send or write)."""
        for job in Job.objects.filter(encounter=encounter, result__contains={'superseded': True}):
            self.assertEqual(job.state, Job.SUCCEEDED)
            made = Run.objects.filter(encounter=encounter, created_at__gte=job.started_at or job.created_at,
                                      created_at__lte=job.finished_at or timezone.now(), sent=True)
            self.assertFalse(made.exists(), (job.kind, job.idempotency_key))

    def values_of(self, encounter):
        row = self.fresh_row(encounter)
        return review.values(row.current_assessment.context)

    def release_corti(self):
        """The operator's recorded release of Corti's hold (7.3)."""
        operator = f.user()
        ops.grant(operator)
        return provider_holds.release(provider_holds.CORTI, user=operator, note='Synthetic release: the cap was raised.')


class CaseATests(UpdateCase):
    """U3: a v2 revision with an inventory read at the current versions - nothing is sent to Gemini (D8)."""

    def test_u3_a_setting_change_sends_nothing_and_a_date_change_at_most_one_corti_request(self):
        encounter = self.v2_fixture(UNDATED)
        gemini_before = Run.objects.filter(purpose__in=jobs.READING_PURPOSES).count()
        saved = self.save(encounter, setting=OFFICE)
        self.assertTrue(saved.updating)
        made = Job.objects.filter(encounter=encounter, created_at__gte=saved.context.created_at)
        self.assertFalse(made.filter(kind__in=(jobs.INTERPRET, jobs.APPRAISE, Job.ANALYZE, Job.PREDICT)).exists())
        self.drain()
        self.assertFalse(Run.objects.filter(encounter=encounter, sent=True,
                                            created_at__gte=saved.context.created_at).exists())
        self.assertTrue(review.fresh(self.fresh_row(encounter)))
        self.assertEqual(self.values_of(encounter), {'setting': OFFICE})
        corti_before = len(self.corti.sent)
        self.save(encounter, service_date=D2)
        self.drain()
        self.assertEqual(len(self.corti.sent), corti_before + 1)  # a new effective date: one Corti request
        self.assertEqual(Run.objects.filter(purpose__in=jobs.READING_PURPOSES).count(), gemini_before)  # Gemini: 0
        self.assertTrue(review.fresh(self.fresh_row(encounter)))
        self.save(encounter, service_date=D3)
        self.drain()
        self.assertEqual(len(self.corti.sent), corti_before + 2)
        self.save(encounter, service_date=D2)  # back to a date whose request has a stored answer: reused, nothing sent
        self.drain()
        self.assertEqual(len(self.corti.sent), corti_before + 2)
        self.assertEqual(Run.objects.filter(purpose__in=jobs.READING_PURPOSES).count(), gemini_before)
        row = self.fresh_row(encounter)
        self.assertTrue(review.fresh(row))
        self.assertEqual(review.values(row.current_assessment.context), {'setting': OFFICE, 'service_date': D2})
        self.assertNoRequestSentTwice(encounter)

    def test_u3_a_date_the_document_contradicts_is_held_and_sends_nothing(self):
        """On a document that states its date, a member's other date is the member date conflict (held: no request it
        could carry), so the date change sends no Corti request; the document's own date has the stored answer."""
        encounter = self.v2_fixture()
        corti_before = len(self.corti.sent)
        self.save(encounter, service_date=D2)
        self.drain()
        self.assertEqual(len(self.corti.sent), corti_before)
        self.assertTrue(progress.date_held(self.fresh_row(encounter)))
        self.save(encounter, service_date=D1)
        self.drain()
        self.assertEqual(len(self.corti.sent), corti_before)
        self.assertTrue(review.fresh(self.fresh_row(encounter)))
        self.assertFalse(Run.objects.filter(encounter=encounter, purpose__in=jobs.READING_PURPOSES,
                                            created_at__gt=encounter.current_assessment.created_at).exists())


class CaseBTests(UpdateCase):
    """U4: a legacy encounter's first edit reads it once with both passes; the saves coalesce."""

    def test_u4_two_saves_before_the_reading_coalesce_into_one_reading(self):
        encounter = self.legacy_fixture()
        legacy = encounter.current_assessment
        first = self.save(encounter, setting=OFFICE)
        self.assertEqual((first.updating, first.context.pk), (True, legacy.context_id))  # the context is kept
        [reading] = Job.objects.filter(encounter=encounter, state=Job.QUEUED)
        self.assertEqual(reading.kind, jobs.INTERPRET)
        self.save(encounter, service_date=D2)
        self.assertEqual(list(Job.objects.filter(encounter=encounter, state=Job.QUEUED)), [reading])  # coalesced
        self.drain()
        row = self.fresh_row(encounter)
        self.assertTrue(review.fresh(row))
        self.assertEqual(Job.objects.filter(encounter=encounter, kind=jobs.INTERPRET).count(), 1)
        self.assertEqual(Job.objects.filter(encounter=encounter, kind=jobs.APPRAISE).count(), 1)
        self.assertEqual([purpose for purpose, _ in self.gemini_sends()], [EXTRACTION, APPRAISAL])
        context = row.current_assessment.context
        self.assertEqual(review.values(context), {'setting': OFFICE, 'service_date': D2})
        self.assertEqual(context.earlier_assessment_id, legacy.pk)
        self.assertEqual(row.current_assessment.engine_version, interpretation.ENGINE_VERSION_V2)
        self.save(encounter, setting=HOSPITAL)  # a third save: case A, no Gemini job
        self.assertFalse(Job.objects.filter(encounter=encounter, state=Job.QUEUED,
                                            kind__in=(jobs.INTERPRET, jobs.APPRAISE)).exists())
        self.drain()
        self.assertEqual(len(self.gemini_sends()), 2)
        self.assertNoRequestSentTwice(encounter)


class RapidEditTests(UpdateCase):
    """U5: rapid successive edits end with exactly the last saved values assessed and no duplicate job or send."""

    SAVES = ({'setting': OFFICE}, {'service_date': D2}, {'setting': HOSPITAL})

    def assertLastSaveAssessed(self, encounter, expected):  # noqa: N802 - unittest's naming
        row = self.fresh_row(encounter)
        self.assertTrue(review.fresh(row), progress.encounter_progress(row))
        self.assertEqual(review.values(row.current_assessment.context), expected)
        self.assertEqual(review.values(row), expected)
        self.assertNoRequestSentTwice(encounter)
        self.assertSupersededSentNothing(encounter)
        keys = list(Job.objects.filter(encounter=encounter).values_list('idempotency_key', flat=True))
        self.assertEqual(len(keys), len(set(keys)))

    def expected(self, count):
        out = {}
        for values in self.SAVES[:count]:
            out.update(values)
        return out

    def test_u5_two_and_three_saves_before_the_worker_runs_on_a_v2_fixture(self):
        for count in (2, 3):
            with self.subTest(saves=count):
                encounter = self.v2_fixture()
                for values in self.SAVES[:count]:
                    self.save(encounter, **values)
                self.drain()
                self.assertLastSaveAssessed(encounter, self.expected(count))

    def test_u5_two_and_three_saves_before_the_worker_runs_on_a_legacy_fixture(self):
        for count in (2, 3):
            with self.subTest(saves=count):
                self.new_workspace()  # its own workspace: nothing of the other fixture's reading is reused
                encounter = self.legacy_fixture()
                for values in self.SAVES[:count]:
                    self.save(encounter, **values)
                self.drain()
                self.assertLastSaveAssessed(encounter, self.expected(count))
                self.assertEqual([purpose for purpose, _ in self.gemini_sends()], [EXTRACTION, APPRAISAL])

    def boundaries(self, fixture):
        """A save after each stage the update runs - at every stage boundary - then the rest of the update."""
        for boundary in range(0, 8):
            with self.subTest(fixture=fixture.__name__, boundary=boundary):
                encounter = fixture()
                self.save(encounter, **self.SAVES[0])
                for _ in range(boundary):
                    job = jobs.claim_next()
                    if job is None:
                        break
                    jobs.run_job(job)
                self.save(encounter, **self.SAVES[1])
                self.drain()
                self.assertLastSaveAssessed(encounter, self.expected(2))

    def test_u5_a_save_at_every_stage_boundary_of_a_v2_update(self):
        self.boundaries(self.v2_fixture)

    def test_u5_a_save_at_every_stage_boundary_of_a_legacy_update(self):
        self.boundaries(self.legacy_fixture)

    def test_u5_a_save_while_appraise_runs_after_a_stop_recorded_on_it(self):
        """(a) [R:races-R6]: the running appraise ends cancelled at its send; the save queued its own ':after-save:'
        stage beside it, which carries the update on with no Resume."""
        encounter = self.legacy_fixture()
        self.save(encounter, **self.SAVES[0])
        self.run_next(jobs.INTERPRET)
        appraise = jobs.claim_next()
        self.assertEqual(appraise.kind, jobs.APPRAISE)
        jobs.stop_encounter(encounter, self.user)  # recorded on the RUNNING appraise
        self.save(encounter, **self.SAVES[1])  # lifts the Stop; never coalesces with a running stage
        twin = Job.objects.get(encounter=encounter, state=Job.QUEUED)
        self.assertIn(':after-save:', twin.idempotency_key)
        self.assertEqual(jobs.run_job(appraise).state, Job.CANCELLED)  # its Stop survives clear_stop
        self.drain()
        self.assertLastSaveAssessed(encounter, self.expected(2))

    def test_u5_a_restore_then_a_change_landing_after_a_reading_stage_decided(self):
        """(b): the stage's start check is driven to decide, the save committed, then run_job finishes it."""
        encounter = self.legacy_fixture()
        self.save(encounter, **self.SAVES[0])
        self.save(encounter, setting='')  # the restore: the legacy codes current again, the reading superseded
        self.assertTrue(review.fresh(self.fresh_row(encounter)))
        job = jobs.claim_next()
        self.assertEqual(job.kind, jobs.INTERPRET)
        real, decided = jobs._start_check, []

        def decided_then_saved(stage):
            try:
                real(stage)  # decides: superseded (the details were restored) ...
            except jobs.StageSuperseded as exc:
                decided.append(exc.reason)
                self.save(encounter, **self.SAVES[1])  # ... and the change commits before its result is recorded
                raise
        with mock.patch.object(jobs, '_start_check', side_effect=decided_then_saved):
            finished = jobs.run_job(job)
        self.assertEqual(decided, [review.SUPERSEDED_RESTORED])
        self.assertEqual((finished.state, finished.result.get('superseded')), (Job.SUCCEEDED, True))
        [twin] = Job.objects.filter(encounter=encounter, state=Job.QUEUED)
        self.assertIn(':after-save:', twin.idempotency_key)  # the change's own stage: no Resume needed
        self.drain()
        self.assertLastSaveAssessed(encounter, {'service_date': D2})

    def test_u5_a_save_while_a_reading_stage_runs_on_a_worker_that_dies(self):
        """(c): the save queues its ':after-save:' twin; mark_stale settles the dead stage, a new worker goes on."""
        encounter = self.legacy_fixture()
        self.save(encounter, **self.SAVES[0])
        job = jobs.claim_next()  # the interpret, claimed by a worker that dies before it ends
        self.save(encounter, **self.SAVES[1])
        Job.objects.filter(pk=job.pk).update(started_at=timezone.now() - timedelta(seconds=700))
        jobs.mark_stale()
        job.refresh_from_db()
        self.assertEqual(job.state, Job.CANCELLED)
        self.drain()
        self.assertLastSaveAssessed(encounter, self.expected(2))

    def test_u5_a_save_coalescing_with_a_stage_queued_29_minutes_before_renews_its_deadline(self):
        """(d) [R2:binding-R2B-7]: the coalescing save renews the queued stage's deadline, so it still runs."""
        encounter = self.legacy_fixture()
        self.save(encounter, **self.SAVES[0])
        reading = Job.objects.get(encounter=encounter, state=Job.QUEUED)
        old = timezone.now() - timedelta(minutes=29)
        Job.objects.filter(pk=reading.pk).update(created_at=old, deadline_at=old + jobs.QUEUE_DEADLINE)
        self.save(encounter, **self.SAVES[1])
        reading.refresh_from_db()
        self.assertGreater(reading.deadline_at, timezone.now() + timedelta(minutes=29))
        with mock.patch.object(timezone, 'now', return_value=timezone.now() + timedelta(minutes=2)):
            claimed = jobs.claim_next()
        self.assertEqual((claimed.pk, claimed.state), (reading.pk, Job.RUNNING))
        jobs.run_job(claimed)
        self.drain()
        self.assertLastSaveAssessed(encounter, self.expected(2))

    def test_u5_a_save_never_coalesces_with_the_stale_sweeps_settled_path(self):
        """(e) [R2:binding-R2B-7]: the first save's interpret dies after its run recorded an answer the settled path
        cannot settle (synthetic: an answer to another request); the stale sweep queues the settled path, which sends
        nothing whatever it finds; a save while it is QUEUED queues its own ':after-save:' stage, and the update goes
        on with no Resume."""
        encounter = self.legacy_fixture()
        revision = encounter.current_revision
        self.save(encounter, **self.SAVES[0])
        dying = jobs.claim_next()
        self.assertEqual((dying.kind, dying.idempotency_key), (jobs.INTERPRET, jobs._interpret_key(revision)))
        data = body(note_answer())
        unsettled = Run.objects.create(encounter=encounter, revision=revision, provider='gemini',
                                       adapter_version=interpretation.ADAPTER_VERSION_V2, request_sha256='c' * 64,
                                       request_body={}, contexts=[], state=Run.SUCCEEDED, sent=True, http_status=200,
                                       response_bytes=data, response_sha256=hashlib.sha256(data).hexdigest(),
                                       purpose=interpretation.PURPOSE, scope={'mode': 'replay'},
                                       started_at=timezone.now(), finished_at=timezone.now())
        Job.objects.filter(pk=dying.pk).update(started_at=timezone.now() - timedelta(seconds=700))
        jobs.mark_stale()
        [settled] = Job.objects.filter(encounter=encounter, state=Job.QUEUED)
        self.assertEqual(settled.idempotency_key, jobs._interpret_key(revision, f'settled:{unsettled.pk}'))
        deadline = settled.deadline_at
        self.save(encounter, **self.SAVES[1])
        queued = list(Job.objects.filter(encounter=encounter, state=Job.QUEUED).exclude(pk=settled.pk))
        self.assertEqual(len(queued), 1)
        self.assertTrue(queued[0].idempotency_key.startswith(f'{jobs._interpret_key(revision)}:{jobs.AFTER_SAVE}:'))
        settled.refresh_from_db()
        self.assertEqual((settled.state, settled.deadline_at), (Job.QUEUED, deadline))  # never coalesced with
        self.drain()
        settled.refresh_from_db()
        self.assertEqual((settled.state, settled.error), (Job.CANCELLED, jobs.INTERPRET_SETTLED_MESSAGE))
        self.assertLastSaveAssessed(encounter, self.expected(2))
        self.assertEqual([purpose for purpose, _ in self.gemini_sends()], [EXTRACTION, APPRAISAL])  # no Resume


class LateFinisherTests(UpdateCase):
    """U6: an assess for C1 whose save made C2 current before its persist writes nothing; C2's assessment follows."""

    def test_u6_the_late_finisher_is_superseded_and_writes_nothing(self):
        encounter = self.v2_fixture()
        before = encounter.current_assessment
        self.save(encounter, setting=OFFICE)
        [assess] = Job.objects.filter(encounter=encounter, state=Job.QUEUED, kind=Job.ASSESS)
        counts = (models.Assessment.objects.count(), models.Proposal.objects.count(),
                  models.Clarification.objects.count())
        states = dict(models.Clarification.objects.values_list('pk', 'state'))
        real = review.persist_assessment

        def save_first(**kwargs):
            self.save(encounter, setting=HOSPITAL)  # C2 current while the bounded child computed C1's codes
            return real(**kwargs)
        with mock.patch.object(review, 'persist_assessment', side_effect=save_first):
            finished = self.run_next(Job.ASSESS)
        self.assertEqual((finished.state, finished.result.get('superseded')), (Job.SUCCEEDED, True))
        self.assertEqual(finished.result['skipped'], review.SUPERSEDED_CONTEXT)
        self.assertEqual((models.Assessment.objects.count(), models.Proposal.objects.count(),
                          models.Clarification.objects.count()), counts)
        self.assertEqual(dict(models.Clarification.objects.values_list('pk', 'state')), states)
        self.assertEqual(self.fresh_row(encounter).current_assessment_id, before.pk)
        self.drain()
        row = self.fresh_row(encounter)
        self.assertTrue(review.fresh(row))
        self.assertEqual(review.values(row.current_assessment.context), {'setting': HOSPITAL})
        self.assertEqual(assess.kind, Job.ASSESS)


class AnalyzeTests(UpdateCase):
    """U7: analyze's compare-and-set (4.2)."""

    def test_u7_a_save_after_the_inventory_and_before_analyze_supersedes_the_analyze(self):
        encounter = self.legacy_fixture()
        self.save(encounter, setting=OFFICE)
        self.run_next(jobs.INTERPRET)
        self.run_next(jobs.APPRAISE)
        saved = self.save(encounter, service_date=D2)  # case A now: the save derives the context itself
        self.assertTrue(interpretation.is_new_context(saved.context))
        analyze = self.run_next(Job.ANALYZE)
        self.assertEqual((analyze.result.get('superseded'), analyze.result.get('skipped')),
                         (True, review.SUPERSEDED_DERIVED))
        self.drain()
        row = self.fresh_row(encounter)
        self.assertTrue(review.fresh(row))
        self.assertEqual(review.values(row.current_assessment.context), {'setting': OFFICE, 'service_date': D2})
        inventory = models.EventInventory.objects.get(encounter=encounter)
        final = [context for context in models.EncounterContext.objects.filter(event_inventory=inventory)
                 if review.values(context) == {'setting': OFFICE, 'service_date': D2}]
        self.assertEqual(len(final), 1)

    def test_u7_a_save_landing_while_analyze_waits_for_the_lock_is_in_its_context(self):
        encounter = self.legacy_fixture()
        self.save(encounter, setting=OFFICE)
        self.run_next(jobs.INTERPRET)
        self.run_next(jobs.APPRAISE)
        real = jobs._stored_inventory

        def save_meanwhile(inventory, revision):
            stored = real(inventory, revision)
            # a case-B save that read the revision before its inventory existed commits now (its values stored,
            # nothing derived): analyze, taking the lock after it, derives with them
            with mock.patch.object(jobs, '_saved_inventory', return_value=None):
                self.save(encounter, service_date=D2)
            return stored
        with mock.patch.object(jobs, '_stored_inventory', side_effect=save_meanwhile):
            analyze = self.run_next(Job.ANALYZE)
        self.assertNotIn('superseded', analyze.result)
        context = models.EncounterContext.objects.get(pk=analyze.result['context'])
        self.assertEqual(review.values(context), {'setting': OFFICE, 'service_date': D2})
        self.drain()
        row = self.fresh_row(encounter)
        self.assertTrue(review.fresh(row))
        inventory = models.EventInventory.objects.get(encounter=encounter)
        final = [item for item in models.EncounterContext.objects.filter(event_inventory=inventory)
                 if review.values(item) == {'setting': OFFICE, 'service_date': D2}]
        self.assertEqual(len(final), 1)


class RestoreTests(UpdateCase):
    """U8: a save back to the earlier codes' own values (2.5) - fresh at once, the update's stages superseded, nothing
    sent after it, the earlier codes' decisions and open questions kept (A17) - and A19's refusal in case B."""

    def membership(self):
        return models.Membership.objects.get(workspace=self.ws, user=self.user)

    def a_decision(self, assessment):
        """A reviewer's rejection of one of ``assessment``'s codes (a decision a restore must keep, uncarried)."""
        membership = self.membership()
        for proposal in assessment.proposals.order_by('code', 'pk'):
            if review.REJECT in review.allowed_actions(proposal, assessment, membership):
                return review.record_decision(encounter=self.fresh_row(assessment.encounter), proposal=proposal,
                                              action=review.REJECT, user=self.user, membership=membership,
                                              note='Synthetic rejection kept across the restore.')
        self.fail('no code of the earlier codes can be decided on')

    def counts(self, encounter):
        return (models.EncounterContext.objects.filter(encounter=encounter).count(),
                Job.objects.filter(encounter=encounter).count(),
                models.AuditEvent.objects.filter(encounter=encounter).count(),
                Run.objects.filter(encounter=encounter).count(), dict(self.fresh_row(encounter).user_values or {}))

    def assertKept(self, encounter, earlier, decision, opened):  # noqa: N802 - unittest's naming
        row = self.fresh_row(encounter)
        self.assertEqual((row.current_assessment_id, review.fresh(row)), (earlier.pk, True))
        self.assertEqual(set(models.Clarification.objects.filter(
            assessment=earlier, state=models.Clarification.OPEN).values_list('pk', flat=True)), opened)
        self.assertFalse(models.DecisionInvalidation.objects.filter(decision__encounter=encounter).exists())
        if decision is None:
            return
        self.assertEqual(models.Decision.objects.filter(encounter=encounter).count(), 1)  # nothing carried
        self.assertIn(review.REVOKE, review.allowed_actions(decision.proposal, earlier, self.membership()))

    def test_u8_a_legacy_save_then_its_restore_while_the_interpret_is_queued(self):
        encounter = self.legacy_fixture()
        earlier = encounter.current_assessment
        decision = self.a_decision(earlier)
        opened = set(models.Clarification.objects.filter(
            assessment=earlier, state=models.Clarification.OPEN).values_list('pk', flat=True))
        self.assertTrue(self.save(encounter, setting=OFFICE).updating)
        [reading] = Job.objects.filter(encounter=encounter, state=Job.QUEUED)
        self.assertEqual(reading.kind, jobs.INTERPRET)
        restored = self.save(encounter, setting='')
        self.assertEqual((restored.restored, restored.updating, restored.pk), (True, False, earlier.context_id))
        self.assertTrue(review.fresh(self.fresh_row(encounter)))  # at once, before the worker runs
        after = timezone.now()
        self.drain()
        reading.refresh_from_db()
        self.assertEqual((reading.state, reading.result), (Job.SUCCEEDED, {'skipped': review.SUPERSEDED_RESTORED,
                                                                           'superseded': True}))
        self.assertFalse(Run.objects.filter(encounter=encounter, created_at__gte=after).exists())
        self.assertEqual(self.gemini_sends(), [])
        self.assertKept(encounter, earlier, decision, opened)

    def test_u8_a_v2_save_then_its_restore_before_the_update_assessed(self):
        # (a decision on a v2 assessment needs the overlay to read event_coding@2 - step 5c's: until it lands such an
        # assessment fails closed (D50) and offers no action, so the decision half is the legacy test's above)
        encounter = self.v2_fixture()
        earlier = encounter.current_assessment
        decision = None
        opened = set(models.Clarification.objects.filter(
            assessment=earlier, state=models.Clarification.OPEN).values_list('pk', flat=True))
        self.save(encounter, setting=OFFICE)
        queued = list(Job.objects.filter(encounter=encounter, state=Job.QUEUED))
        self.assertTrue(queued)
        self.assertTrue(self.save(encounter, setting='').restored)
        made = models.Assessment.objects.filter(encounter=encounter).count()
        after = timezone.now()
        self.drain()
        for job in queued:
            job.refresh_from_db()
            self.assertEqual((job.state, job.result.get('superseded')), (Job.SUCCEEDED, True), job.kind)
        self.assertEqual(models.Assessment.objects.filter(encounter=encounter).count(), made)
        self.assertFalse(Run.objects.filter(encounter=encounter, sent=True, created_at__gte=after).exists())
        self.assertKept(encounter, earlier, decision, opened)

    def test_u8_t8_a_save_back_to_a_first_processings_unfinished_codes_is_an_ordinary_update_never_a_restore(self):
        """[R:truth-T8] (U8's fifth case): a first processing's assess #1 is shown (current, not final: it owes a peer
        stage - made so here, as A17's test does); a save makes it the earlier codes (an update now); a save back to its
        values is no restore (2.5: only final earlier codes) but an ordinary update, whose final replaces it."""
        first = {}
        real = jobs.owed_peer_stages

        def owes(assessment):
            return ('astra_peer',) if assessment.pk == first.get('pk') else real(assessment)
        with mock.patch.object(jobs, 'owed_peer_stages', side_effect=owes), \
                mock.patch.object(jobs, '_queue_peers', return_value=None):
            encounter, _ = self.upload(UNDATED)
            self.drain()
            unfinished = self.fresh_row(encounter).current_assessment
            first['pk'] = unfinished.pk
            row = self.fresh_row(encounter)
            self.assertFalse(review.is_final(row.current_assessment))
            self.assertEqual((review.fresh(row), review.update_pending(row)), (False, False))  # processing, no update
            self.assertTrue(self.save(encounter, setting=OFFICE).updating)
            row = self.fresh_row(encounter)
            self.assertEqual(review.earlier(row).pk, unfinished.pk)  # T8: the codes the member was shown
            back = self.save(encounter, setting='')
            self.assertEqual((back.restored, back.updating), (False, True))  # never a restore of unfinished codes
            self.assertNotEqual(back.context.pk, unfinished.context_id)
            self.drain()
        row = self.fresh_row(encounter)
        self.assertTrue(review.fresh(row), progress.encounter_progress(row))
        self.assertNotEqual(row.current_assessment_id, unfinished.pk)
        self.assertEqual(review.values(row.current_assessment.context), {})

    def test_u8_a19_a_case_b_save_back_to_codes_that_cannot_stand_is_refused_and_the_update_goes_on(self):
        """The earlier codes E's own document review is an unknown outcome the operator's reconciliation released (A21:
        E can no longer stand as it is, A19): a case-B save back to E's values is RESTORE_REFUSED and writes nothing;
        the update goes on and its final replaces E. (Synthetic: E's Corti run is recorded unknown, as the installed
        release recorded such a run.)"""
        from studio import customer_api

        encounter = self.legacy_fixture()
        earlier = encounter.current_assessment
        Run.objects.filter(pk=earlier.provider_run_id).update(state=Run.UNKNOWN,
                                                              error='Read timed out after the request was sent.')
        self.assertTrue(jobs.reconcile(encounter, Run.objects.get(pk=earlier.provider_run_id), self.user,
                                       'Synthetic: the vendor log shows no answer.'))
        row = self.fresh_row(encounter)
        self.assertEqual((review.fresh(row), review.update_kind(row), review.restorable(row)),
                         (False, review.UPDATE_CHECK, False))
        self.save(encounter, setting=OFFICE)
        counts = self.counts(encounter)
        with self.assertRaises(jobs.Refused) as refused:
            self.save(encounter, setting='')
        self.assertEqual(str(refused.exception), customer_api.RESTORE_REFUSED)
        self.assertEqual(self.counts(encounter), counts)  # nothing written
        self.drain()
        row = self.fresh_row(encounter)
        self.assertTrue(review.fresh(row))
        self.assertNotEqual(row.current_assessment_id, earlier.pk)
        self.assertEqual(review.values(row.current_assessment.context), {'setting': OFFICE})
        self.assertEqual(len(self.corti.sent), 1)  # the released attempt, once


class StopResumeTests(UpdateCase):
    """U9: Stop, Resume, a dead worker, the interpreter's hold - during an update."""

    def test_u9_a_stop_after_a_legacy_updates_reading_reads_stopped_and_resume_queues_its_analyze(self):
        from studio import customer_api

        encounter = self.legacy_fixture()
        self.save(encounter, setting=OFFICE)
        self.run_next(jobs.INTERPRET)
        self.run_next(jobs.APPRAISE)
        jobs.stop_encounter(encounter, self.user)
        row = self.fresh_row(encounter)
        panel = progress.encounter_progress(row)
        self.assertEqual((panel['phase'], panel['error']),
                         ('stopped', {'text': customer_api.update_text('stopped_by_member', review.UPDATE_DETAILS, True),
                                      'action': 'resume'}))
        job = jobs.resume(encounter, self.user)
        inventory = models.EventInventory.objects.get(encounter=encounter)
        self.assertEqual(job.kind, Job.ANALYZE)
        self.assertTrue(job.idempotency_key.startswith(f'analyze:{row.current_revision_id}:{inventory.pk}:resume:'))
        self.drain()
        row = self.fresh_row(encounter)
        self.assertTrue(review.fresh(row))
        self.assertEqual(review.values(row.current_assessment.context), {'setting': OFFICE})
        self.assertEqual([purpose for purpose, _ in self.gemini_sends()], [EXTRACTION, APPRAISAL])  # nothing re-sent

    def test_u9_the_stale_sweep_queues_no_successor_for_a_superseded_stage(self):
        encounter = self.legacy_fixture()
        self.save(encounter, setting=OFFICE)
        job = jobs.claim_next()
        self.assertEqual(job.kind, jobs.INTERPRET)

        def dies(*args, **kwargs):
            raise KeyboardInterrupt  # the worker dies after the run's outcome was recorded
        with mock.patch.object(jobs, '_settle_interpretation', side_effect=dies):
            with self.assertRaises(KeyboardInterrupt), jobs._stage_scope(job):
                jobs.STAGES[jobs.INTERPRET](job)
        self.assertTrue(self.save(encounter, setting='').restored)  # the dead stage no longer serves the saved state
        Job.objects.filter(pk=job.pk).update(started_at=timezone.now() - timedelta(seconds=700))
        jobs.mark_stale()
        job.refresh_from_db()
        self.assertEqual(job.state, Job.SUCCEEDED)
        self.assertFalse(Job.objects.filter(encounter=encounter, state__in=(Job.QUEUED, Job.RUNNING)).exists())
        self.assertTrue(review.fresh(self.fresh_row(encounter)))

    def test_u9_a_bare_429_during_an_update_holds_every_save_unsent_until_the_release_then_one_resume(self):
        encounter = self.legacy_fixture()
        earlier = encounter.current_assessment
        self.interpreter.script = {EXTRACTION: [answered(BARE_429, status=429)]}
        self.save(encounter, setting=OFFICE)
        self.drain()
        self.assertTrue(holds.is_held())
        held_at = timezone.now()
        row = self.fresh_row(encounter)
        self.assertEqual((progress.encounter_progress(row)['phase'], row.current_assessment_id), ('paused', earlier.pk))
        sent = list(self.interpreter.sent)
        self.save(encounter, service_date=D1)  # every save while held records only not-sent runs
        self.drain()
        jobs.resume(encounter, self.user)
        self.drain()
        self.assertEqual(self.interpreter.sent, sent)
        self.assertFalse(Run.objects.filter(encounter=encounter, sent=True, created_at__gte=held_at).exists())
        self.assertTrue(Run.objects.filter(encounter=encounter, scope__held=holds.HELD_HOLD).exists())
        with self.assertRaises(jobs.Refused):
            jobs.retry_reading(encounter, self.user)  # RETRY_PAUSED: never retried while the hold stands
        operator = f.user()
        ops.grant(operator)
        holds.release(user=operator, note='Synthetic release: the spending cap was raised.')
        self.assertIsNotNone(jobs.resume(encounter, self.user))
        self.drain()
        self.assertEqual([purpose for purpose, _ in self.interpreter.sent], [EXTRACTION, EXTRACTION, APPRAISAL])
        row = self.fresh_row(encounter)
        self.assertTrue(review.fresh(row))
        self.assertEqual(review.values(row.current_assessment.context), {'setting': OFFICE, 'service_date': D1})

    def test_u9_a_worker_dead_mid_predict_during_an_update_is_confirmed_then_reconciled_and_sent_once(self):
        encounter = self.v2_fixture(UNDATED)
        earlier = encounter.current_assessment
        self.save(encounter, service_date=D2)
        job = jobs.claim_next()
        self.assertEqual(job.kind, Job.PREDICT)

        def dies(request, *, deadline_s):
            raise KeyboardInterrupt  # the worker dies while the request is in flight
        with mock.patch.object(self.corti, 'send', side_effect=dies):
            with self.assertRaises(KeyboardInterrupt), jobs._stage_scope(job):
                jobs.STAGES[Job.PREDICT](job)
        Job.objects.filter(pk=job.pk).update(started_at=timezone.now() - timedelta(seconds=700))
        jobs.mark_stale()
        [run] = Run.objects.filter(encounter=encounter, state=Run.UNKNOWN)
        row = self.fresh_row(encounter)
        self.assertEqual(row.current_assessment_id, earlier.pk)  # the earlier codes stand
        self.assertEqual(progress.encounter_progress(row)['phase'], 'being_confirmed')
        with self.assertRaises(jobs.Refused):
            jobs.retry_update(encounter, self.user)  # an unknown outcome is reconciled, never retried
        self.assertTrue(jobs.reconcile(encounter, run, self.user, 'Synthetic: the vendor log shows no answer.'))
        sends = len(self.corti.sent)
        self.drain()
        self.assertEqual(len(self.corti.sent), sends + 1)  # the released attempt, once
        row = self.fresh_row(encounter)
        self.assertTrue(review.fresh(row))
        self.assertEqual(review.values(row.current_assessment.context), {'service_date': D2})

    def kill_after_the_outcome(self, encounter):
        """Run the queued predict until its run's outcome is recorded, then kill the worker (R2B-6)."""
        job = jobs.claim_next()
        self.assertEqual(job.kind, Job.PREDICT)
        real = jobs._send

        def send_then_die(*args, **kwargs):
            real(*args, **kwargs)
            raise KeyboardInterrupt
        with mock.patch.object(jobs, '_send', side_effect=send_then_die):
            with self.assertRaises(KeyboardInterrupt), jobs._stage_scope(job):
                jobs.STAGES[Job.PREDICT](job)
        Job.objects.filter(pk=job.pk).update(started_at=timezone.now() - timedelta(seconds=700))
        jobs.mark_stale()
        job.refresh_from_db()
        return job

    def test_u9_r2b6_a_worker_killed_after_corti_answered_settles_by_the_update_rules(self):
        for status, state in ((500, Job.FAILED), (402, Job.CANCELLED)):
            with self.subTest(status=status):
                self.new_workspace()
                encounter = self.v2_fixture(UNDATED)
                earlier = encounter.current_assessment
                self.corti.outcomes = [corti_refusal(status)]
                self.save(encounter, service_date=D2)
                job = self.kill_after_the_outcome(encounter)
                self.assertEqual(job.state, state, job.error)
                self.assertFalse(Job.objects.filter(encounter=encounter, state=Job.QUEUED).exists())  # nothing queued
                row = self.fresh_row(encounter)
                self.assertEqual(row.current_assessment_id, earlier.pk)  # the earlier codes untouched
                self.assertEqual(progress.encounter_progress(row)['phase'], 'paused' if status == 402 else 'failed')
                self.release_corti()



class WorkerKilledHoldTests(UpdateCase):
    """U9's remaining kills [R2:binding-R2B-6]: a worker killed after a run Corti's hold kept unsent was recorded, during an
    update; and in a first processing, after Corti's 402 and after a held run. mark_stale settles each as the stage
    would - CANCELLED, paused, queueing nothing - never a final made with the refused or held run."""

    def kill_after(self, target, job):
        """Run ``job`` (a predict) until jobs.``target`` has recorded its run, then kill the worker; mark_stale."""
        real = getattr(jobs, target)

        def record_then_die(*args, **kwargs):
            real(*args, **kwargs)
            raise KeyboardInterrupt
        with mock.patch.object(jobs, target, side_effect=record_then_die):
            with self.assertRaises(KeyboardInterrupt), jobs._stage_scope(job):
                jobs.STAGES[Job.PREDICT](job)
        Job.objects.filter(pk=job.pk).update(started_at=timezone.now() - timedelta(seconds=700))
        jobs.mark_stale()
        job.refresh_from_db()
        return job

    def hold_set_elsewhere(self):
        holder = self.v2_fixture(UNDATED)
        self.corti.outcomes = [corti_refusal(402)]
        self.save(holder, service_date=D3)
        self.drain()
        self.assertTrue(provider_holds.held(provider_holds.CORTI))

    def assertPausedAndNothingQueued(self, job, encounter):  # noqa: N802 - unittest's naming
        self.assertEqual((job.state, job.error), (Job.CANCELLED, jobs.PROVIDER_PAUSED_MESSAGE))
        self.assertFalse(Job.objects.filter(encounter=encounter, state=Job.QUEUED).exists())

    def test_u9_a_worker_killed_after_a_held_run_was_recorded_during_an_update_ends_paused(self):
        encounter = self.v2_fixture(UNDATED)
        earlier = encounter.current_assessment
        self.hold_set_elsewhere()
        self.save(encounter, service_date=D2)
        job = jobs.claim_next()
        self.assertEqual(job.kind, Job.PREDICT)
        job = self.kill_after('_provider_hold_run', job)
        self.assertPausedAndNothingQueued(job, encounter)
        row = self.fresh_row(encounter)
        self.assertEqual(row.current_assessment_id, earlier.pk)  # the earlier codes untouched
        self.assertEqual(progress.encounter_progress(row)['phase'], 'paused')

    def test_u9_a_first_processing_killed_after_its_402_or_a_held_run_ends_paused_never_in_a_final(self):
        for case in ('402', 'held'):
            with self.subTest(case=case):
                self.new_workspace()
                if case == 'held':
                    self.hold_set_elsewhere()
                else:
                    self.corti.outcomes = [corti_refusal(402)]
                encounter, _ = self.upload(UNDATED, values={'service_date': D2})
                while True:
                    job = jobs.claim_next()
                    if job.kind == Job.PREDICT:
                        break
                    jobs.run_job(job)
                job = self.kill_after('_send' if case == '402' else '_provider_hold_run', job)
                self.assertPausedAndNothingQueued(job, encounter)
                self.drain()
                self.assertFalse(models.Assessment.objects.filter(encounter=encounter).exists())  # never a final
                self.assertIsNone(self.fresh_row(encounter).current_assessment_id)
                self.release_corti()


class UpdateFailureTests(UpdateCase):
    """U12: the failures of an update (7.1, 7.2): the earlier codes are never replaced by an assessment without a
    document review, and each failure's retry is the one 7.2 names."""

    def dated_update(self, *outcomes):
        """An undated v2 fixture and a date change whose Corti request is answered by ``outcomes``, run to its end."""
        encounter = self.v2_fixture(UNDATED)
        earlier = encounter.current_assessment
        self.corti.outcomes = list(outcomes)
        self.save(encounter, service_date=D2)
        self.drain()
        return encounter, earlier

    def assertEarlierStands(self, encounter, earlier):  # noqa: N802 - unittest's naming
        row = self.fresh_row(encounter)
        self.assertEqual((row.current_assessment_id, review.fresh(row)), (earlier.pk, False))
        self.assertTrue(review.update_pending(row))
        return row

    def test_u12_a_corti_500_fails_the_update_and_retry_update_releases_one_attempt(self):
        encounter, earlier = self.dated_update(corti_refusal(500))
        row = self.assertEarlierStands(encounter, earlier)
        self.assertEqual(progress.encounter_progress(row)['error']['action'], 'retry_update')
        [failed] = Run.objects.filter(encounter=encounter, state=Run.FAILED)
        job = jobs.retry_update(encounter, self.user)
        self.assertEqual(job.idempotency_key, f'predict:{row.current_context_id}:retry-release:{failed.pk}')
        with self.assertRaises(jobs.Refused):
            jobs.retry_update(encounter, self.user)  # a second Retry while the first is queued
        self.drain()
        self.assertEqual(len(self.corti.sent), 3)  # the first processing, the 500, the released attempt
        row = self.fresh_row(encounter)
        self.assertTrue(review.fresh(row))
        self.assertEqual(review.values(row.current_assessment.context), {'service_date': D2})

    def test_u12_corti_not_sent_for_a_local_reason_fails_and_retry_update_queues_it_again(self):
        from studio import customer_api

        encounter, earlier = self.dated_update(LOCAL_NOT_SENT)
        row = self.assertEarlierStands(encounter, earlier)
        panel = progress.encounter_progress(row)
        self.assertEqual(panel['error'], {'text': customer_api.update_text('review_not_sent', review.UPDATE_DETAILS,
                                                                           True), 'action': 'retry_update'})
        [unsent] = Run.objects.filter(encounter=encounter, state=Run.NOT_SENT).exclude(request_sha256='')
        job = jobs.retry_update(encounter, self.user)
        self.assertEqual(job.idempotency_key, f'predict:{row.current_context_id}:retry:{unsent.pk}')
        self.drain()
        self.assertTrue(review.fresh(self.fresh_row(encounter)))

    def test_u12_a_corti_429_402_and_a_token_401_pause_the_update_under_the_hold_and_are_never_retried(self):
        from studio import customer_api

        for outcome, reason in ((corti_refusal(429), provider_holds.QUOTA), (corti_refusal(402), provider_holds.QUOTA),
                                (token_refusal(401), provider_holds.AUTH)):
            with self.subTest(status=outcome.http_status, sent=outcome.sent):
                self.new_workspace()
                encounter, earlier = self.dated_update(outcome)
                row = self.assertEarlierStands(encounter, earlier)
                [hold] = provider_holds.active(provider_holds.CORTI)
                self.assertEqual((hold.reason, hold.http_status), (reason, outcome.http_status))
                panel = progress.encounter_progress(row)
                self.assertEqual((panel['phase'], panel['error']['action']), ('paused', 'resume'))
                with self.assertRaises(jobs.Refused) as refused:
                    jobs.retry_update(encounter, self.user)
                self.assertEqual(str(refused.exception), customer_api.RETRY_UPDATE_HELD)
                sends = len(self.corti.sent)
                jobs.resume(encounter, self.user)
                self.drain()
                self.assertEqual(len(self.corti.sent), sends)  # never retried in a loop
                self.assertEarlierStands(encounter, earlier)
                self.release_corti()
                self.assertIsNotNone(jobs.resume(encounter, self.user))
                self.drain()
                self.assertEqual(len(self.corti.sent), sends + 1)  # after the release, one send
                self.assertTrue(review.fresh(self.fresh_row(encounter)))

    def test_u12_a_pass_1_500_during_a_legacy_update_offers_one_retry_of_the_reading(self):
        from studio import customer_api

        encounter = self.legacy_fixture()
        earlier = encounter.current_assessment
        self.interpreter.script = {EXTRACTION: [answered(HTTP_500, status=500)]}
        self.save(encounter, setting=OFFICE)
        self.drain()
        row = self.assertEarlierStands(encounter, earlier)
        panel = progress.encounter_progress(row)
        self.assertEqual(panel['error'], {'text': customer_api.update_text('reading_failed', review.UPDATE_DETAILS,
                                                                           True), 'action': 'retry_reading'})
        with self.assertRaises(jobs.Refused) as refused:
            jobs.retry_update(encounter, self.user)
        self.assertEqual(str(refused.exception), customer_api.RETRY_UPDATE_READING)
        jobs.retry_reading(encounter, self.user)
        self.drain()
        self.assertEqual([purpose for purpose, _ in self.interpreter.sent], [EXTRACTION, EXTRACTION, APPRAISAL])
        self.assertTrue(review.fresh(self.fresh_row(encounter)))

    def test_u12_an_unhealthy_appraisal_and_a_cut_off_reading_during_a_legacy_update(self):
        """Pass 2 unhealthy: 7.1's appraisal row with Try reading again (a retry re-sends pass 2 only); pass 1 cut off
        at its output limit (MAX_TOKENS): the too-long row, no Retry. The earlier codes stand in both."""
        from studio import customer_api
        from tests.test_interpretation_adapter import encoded, with_parts
        from tests.v2.test_settle import faithful, verdict

        def yes_man(claim, role, claim_set):
            return verdict(claim, 'supports')  # every control supported too: control acceptance refuses
        cut = answered(encoded(with_parts({'text': '{"events": ['}, finish='MAX_TOKENS')))
        for name, oracle, script, situation, action in (
                ('unhealthy', yes_man, {}, 'appraisal_failed', 'retry_reading'),
                ('cut off', faithful, {EXTRACTION: [cut]}, 'too_long', 'none')):
            with self.subTest(name):
                self.new_workspace()
                encounter = self.legacy_fixture()
                earlier = encounter.current_assessment
                self.interpreter.oracle, self.interpreter.script = oracle, {k: list(v) for k, v in script.items()}
                self.save(encounter, setting=OFFICE)
                self.drain()
                row = self.assertEarlierStands(encounter, earlier)
                self.assertEqual(progress.encounter_progress(row)['error'], {
                    'text': customer_api.update_text(situation, review.UPDATE_DETAILS, True), 'action': action})
                if action == 'none':
                    with self.assertRaises(jobs.Refused) as refused:
                        jobs.retry_reading(encounter, self.user)
                    self.assertEqual(str(refused.exception), jobs.RETRY_TOO_LONG)
                    continue
                self.interpreter.oracle = faithful
                self.assertEqual(jobs.retry_reading(encounter, self.user).kind, jobs.APPRAISE)
                self.drain()
                self.assertEqual([purpose for purpose, _ in self.gemini_sends()], [EXTRACTION, APPRAISAL, APPRAISAL])
                self.assertTrue(review.fresh(self.fresh_row(encounter)))

    def test_u12_a_stage_that_sends_nothing_fails_during_an_update_and_retry_update_runs_it_again(self):
        """7.1's processing-failed row (an overrun of assess's bounded child; a derivation analyze refused): the earlier
        codes stand; retry_update re-queues the same stage under its own key plus ':resume:<uuid>' (7.2), sending
        nothing, and the update completes."""
        from studio import bounded, customer_api

        for stage in (Job.ASSESS, Job.ANALYZE):
            with self.subTest(stage=stage):
                self.new_workspace()
                encounter = self.legacy_fixture()
                earlier = encounter.current_assessment
                if stage == Job.ASSESS:
                    real, calls = jobs.sentinel.run_counted, []

                    def overrun_once(fn, *args, **kwargs):
                        if fn is jobs._assess_child_v2 and not calls:
                            calls.append(fn)
                            raise bounded.Overrun('time')
                        return real(fn, *args, **kwargs)
                    patch = mock.patch.object(jobs.sentinel, 'run_counted', side_effect=overrun_once)
                else:
                    real_derive, calls = jobs.derived_facts, []

                    def refused_once(*args, **kwargs):
                        if not calls:
                            calls.append(args)
                            raise jobs.StageFailure('The encounter context could not be derived (synthetic).')
                        return real_derive(*args, **kwargs)
                    patch = mock.patch.object(jobs, 'derived_facts', side_effect=refused_once)
                self.save(encounter, setting=OFFICE)
                with patch:
                    self.drain()
                    row = self.assertEarlierStands(encounter, earlier)
                    failed = review.latest_job(row)
                    self.assertEqual((failed.kind, failed.state), (stage, Job.FAILED))
                    self.assertEqual(progress.encounter_progress(row)['error'], {
                        'text': customer_api.update_text('processing_failed', review.UPDATE_DETAILS, True),
                        'action': 'retry_update'})
                    sends = (list(self.interpreter.sent), list(self.corti.sent))
                    job = jobs.retry_update(encounter, self.user)
                    self.assertEqual(job.kind, stage)
                    self.assertTrue(job.idempotency_key.startswith(failed.idempotency_key.split(':resume:')[0]
                                                                   + ':resume:'))
                    self.drain()
                self.assertEqual((list(self.interpreter.sent), list(self.corti.sent)), sends)  # nothing sent by it
                row = self.fresh_row(encounter)
                self.assertTrue(review.fresh(row), progress.encounter_progress(row))
                self.assertEqual(review.values(row.current_assessment.context), {'setting': OFFICE})

    def test_u12_l4_an_earlier_e_whose_own_corti_request_could_not_be_built_completes_with_its_own_outcome(self):
        """[R:legacy-L4]: neither E's request nor the update's could be built from the same revision text, so the update
        goes on with E's own outcome - no Corti request sent, on the legacy E after both Gemini passes only."""
        def unbuildable(text, service_date):
            raise ProviderUnavailable('The request would be over the byte limit (synthetic); nothing was sent.')
        for fixture in (self.v2_fixture, self.legacy_fixture):
            with self.subTest(fixture=fixture.__name__):
                self.new_workspace()
                with mock.patch.object(self.corti, 'build_request', side_effect=unbuildable):
                    encounter = fixture()
                    earlier = encounter.current_assessment
                    self.assertEqual((earlier.provider_run.state, earlier.provider_run.request_sha256),
                                     (Run.NOT_SENT, ''))
                    self.save(encounter, setting=OFFICE)
                    self.drain()
                row = self.fresh_row(encounter)
                self.assertTrue(review.fresh(row), progress.encounter_progress(row))
                self.assertNotEqual(row.current_assessment_id, earlier.pk)
                self.assertEqual(row.current_assessment.provider_run.request_sha256, '')
                self.assertEqual(self.corti.sent, [])
                if fixture == self.legacy_fixture:
                    self.assertEqual([purpose for purpose, _ in self.gemini_sends()], [EXTRACTION, APPRAISAL])

    def test_u12_l4_an_earlier_e_whose_own_corti_run_failed_completes_with_its_own_outcome(self):
        """[R:legacy-L4]: E's own document review failed (a 500); a setting change keeps Corti's request, so the update
        completes with E's own outcome - no Corti request sent, on the legacy E after both Gemini passes only."""
        for fixture in (self.v2_fixture, self.legacy_fixture):
            with self.subTest(fixture=fixture.__name__):
                self.new_workspace()
                self.corti.outcomes = [corti_refusal(500)]
                encounter = fixture()
                earlier = encounter.current_assessment
                self.assertEqual(earlier.provider_run.state, Run.FAILED)
                sends = len(self.corti.sent)
                self.save(encounter, setting=OFFICE)
                self.drain()
                row = self.fresh_row(encounter)
                self.assertTrue(review.fresh(row), progress.encounter_progress(row))
                self.assertNotEqual(row.current_assessment_id, earlier.pk)
                self.assertEqual(len(self.corti.sent), sends)
                if fixture == self.legacy_fixture:
                    self.assertEqual([purpose for purpose, _ in self.gemini_sends()], [EXTRACTION, APPRAISAL])


class DisabledCodingServiceTests(UpdateCase):
    """U12's coding-service-disabled rows (7.1, 7.2, A6; refutation 5b-r1, X1): with get_provider() None nothing is sent,
    so an update goes on only with the outcome the run in use already records for the very request the new context makes
    - its answer, or the earlier codes' own - and is paused (PROVIDER_DISABLED, resumable) for every other request. A
    final made with NO document review never replaces the earlier codes."""

    def no_review_finals(self, encounter):
        return models.Assessment.objects.filter(encounter=encounter, provider_run__isnull=True)

    def test_x1_a_legacy_update_with_the_coding_service_disabled_goes_on_with_es_own_review(self):
        """The refuter's input (probe P1): a legacy E made with a SUCCEEDED Corti run for NOTE's own date; the coding
        service disabled; a setting save (case B). The v2-derived date gives the request E's run carried, so the update
        goes on with E's own run (A6: the review's input is unchanged) - never a final with provider_run None that drops
        every code and clears E."""
        encounter = self.legacy_fixture()
        earlier = encounter.current_assessment
        self.assertEqual(earlier.provider_run.state, Run.SUCCEEDED)
        self.disabled = True
        self.save(encounter, setting=OFFICE)
        done = self.drain()
        [predict] = [job for job in done if job.kind == Job.PREDICT]
        self.assertEqual((predict.state, predict.result.get('run'), predict.result.get('provider')),
                         (Job.SUCCEEDED, str(earlier.provider_run_id), Run.SUCCEEDED))  # read as an answer used
        row = self.fresh_row(encounter)
        self.assertTrue(review.fresh(row), progress.encounter_progress(row))
        final = row.current_assessment
        self.assertNotEqual(final.pk, earlier.pk)
        self.assertEqual((final.engine_version, final.provider_run_id),
                         (interpretation.ENGINE_VERSION_V2, earlier.provider_run_id))
        self.assertEqual(sorted(final.proposals.filter(bucket='selected').values_list('code', flat=True)), ['45378'])
        self.assertFalse(self.no_review_finals(encounter).exists())
        self.assertEqual(self.corti.sent, [])

    def test_x1_a_changed_request_with_the_coding_service_disabled_pauses_and_the_earlier_codes_stay(self):
        """A date change makes a request the run in use does not carry: the update pauses (7.1's coding-service-disabled
        row, Resume), nothing is assessed, and once the service is configured again one Resume sends it once."""
        from studio import customer_api

        for fixture in (self.v2_fixture, self.legacy_fixture):
            with self.subTest(fixture=fixture.__name__):
                self.new_workspace()
                self.disabled = False
                encounter = fixture(UNDATED)
                earlier = encounter.current_assessment
                made = models.Assessment.objects.filter(encounter=encounter).count()
                self.disabled = True
                self.save(encounter, service_date=D2)
                self.drain()
                row = self.fresh_row(encounter)
                self.assertEqual((row.current_assessment_id, review.update_pending(row)), (earlier.pk, True))
                self.assertEqual(models.Assessment.objects.filter(encounter=encounter).count(), made)
                panel = progress.encounter_progress(row)
                self.assertEqual((panel['phase'], panel['error']), ('paused', {
                    'text': customer_api.update_text('review_disabled', review.UPDATE_DETAILS, True),
                    'action': 'resume'}))
                self.disabled = False
                sends = len(self.corti.sent)
                self.assertIsNotNone(jobs.resume(encounter, self.user))
                self.drain()
                self.assertEqual(len(self.corti.sent), sends + 1)
                row = self.fresh_row(encounter)
                self.assertTrue(review.fresh(row))
                self.assertEqual(review.values(row.current_assessment.context), {'service_date': D2})

    def test_x1_with_the_coding_service_disabled_a_failed_run_that_is_not_es_own_never_completes_the_update(self):
        """The run in use carries the request (a setting save after a failed date change) but its outcome is a failure
        that is not E's own: no answer to go on with, so the update pauses - never a final made with that failure or
        with none."""
        encounter = self.v2_fixture(UNDATED)
        earlier = encounter.current_assessment
        self.corti.outcomes = [corti_refusal(500)]
        self.save(encounter, service_date=D2)
        self.drain()
        [failed] = Run.objects.filter(encounter=encounter, state=Run.FAILED)
        made = models.Assessment.objects.filter(encounter=encounter).count()
        self.disabled = True
        self.save(encounter, setting=OFFICE)
        self.drain()
        row = self.fresh_row(encounter)
        self.assertEqual(row.current_assessment_id, earlier.pk)
        self.assertEqual(models.Assessment.objects.filter(encounter=encounter).count(), made)
        latest = review.latest_job(row)
        self.assertEqual((latest.kind, latest.state, latest.error), (Job.PREDICT, Job.CANCELLED,
                                                                     jobs.PROVIDER_DISABLED_MESSAGE))
        self.assertEqual(jobs._run_in_use(row.current_revision), failed)
        self.assertFalse(self.no_review_finals(encounter).exists())


class MarkedSentTests(UpdateCase):
    """Repair gi2's R1 rule kept through the amendment: an outcome an adapter recorded NOT SENT while marking it sent
    may have reached the provider, so it is never trusted as one that never left. A save during an update queues the
    predict where it used to re-check with such a run (A6), so the predict's send door holds it as it holds a request
    that failed (jobs._marked_sent_before): nothing is sent behind a save; a member's retry releases it once."""

    def test_a_marked_sent_attempt_is_never_sent_behind_a_save_and_a_retry_releases_it_once(self):
        from studio import customer_api

        encounter = self.v2_fixture(UNDATED)
        earlier = encounter.current_assessment
        self.corti.outcomes = [RawExchange(outcome='not_sent', sent=True,
                                           error='Recorded not sent but marked sent (synthetic).')]
        self.save(encounter, service_date=D2)
        self.drain()
        [marked] = Run.objects.filter(encounter=encounter, state=Run.NOT_SENT, sent=True)
        row = self.fresh_row(encounter)
        self.assertEqual(row.current_assessment_id, earlier.pk)  # a review that is not E's own never replaces E
        self.assertEqual(progress.encounter_progress(row)['error'], {
            'text': customer_api.update_text('review_failed', review.UPDATE_DETAILS, True), 'action': 'retry_update'})
        sends = len(self.corti.sent)
        self.save(encounter, setting=OFFICE)  # keeps D2's request: the update's predict meets it at the send door
        self.drain()
        self.assertEqual(len(self.corti.sent), sends)
        newest = jobs._run_in_use(row.current_revision)
        self.assertEqual((newest.state, newest.sent, newest.request_sha256), (Run.NOT_SENT, False,
                                                                             marked.request_sha256))
        self.assertTrue(newest.error.startswith(jobs.FAILED_BEFORE_MESSAGE))
        self.assertEqual(self.fresh_row(encounter).current_assessment_id, earlier.pk)
        job = jobs.retry_update(encounter, self.user)  # the member's recorded release: once
        self.assertEqual(job.idempotency_key, f'predict:{self.fresh_row(encounter).current_context_id}:'
                                              f'{jobs.RETRY_RELEASE}:{marked.pk}')
        self.drain()
        self.assertEqual(len(self.corti.sent), sends + 1)
        row = self.fresh_row(encounter)
        self.assertTrue(review.fresh(row))
        self.assertEqual(review.values(row.current_assessment.context), {'service_date': D2, 'setting': OFFICE})


class ProviderHoldTests(UpdateCase):
    """U20: Corti's provider hold (A16, A20) - set and released only from recorded http_status and sent."""

    def release(self):
        self.release_corti()

    def test_u20_a_402_during_an_update_holds_every_corti_request_until_the_release_then_one_send(self):
        from studio import customer_api

        encounter = self.v2_fixture(UNDATED)
        other = self.v2_fixture(UNDATED)  # another encounter of the workspace, fresh
        self.corti.outcomes = [corti_refusal(402)]
        self.save(encounter, service_date=D2)
        self.drain()
        [hold] = provider_holds.active()
        [refused] = Run.objects.filter(encounter=encounter, state=Run.FAILED)
        self.assertEqual((hold.provider, hold.reason, hold.http_status, hold.run_id),
                         (provider_holds.CORTI, provider_holds.QUOTA, 402, refused.pk))
        sends = len(self.corti.sent)
        # while it stands: another encounter's update, an upload, a Resume and a Retry send nothing
        self.save(other, service_date=D3)
        self.drain()
        third, _ = self.upload(UNDATED, values={'service_date': D3})
        self.drain()
        jobs.resume(encounter, self.user)
        self.drain()
        with self.assertRaises(jobs.Refused) as retry:
            jobs.retry_update(encounter, self.user)
        self.assertEqual(str(retry.exception), customer_api.RETRY_UPDATE_HELD)
        self.assertEqual(len(self.corti.sent), sends)
        held = Run.objects.filter(scope__held=provider_holds.HELD, sent=False)
        self.assertEqual({run.encounter_id for run in held}, {encounter.pk, other.pk, third.pk})
        self.assertEqual(progress.encounter_progress(self.fresh_row(third))['error']['text'],
                         customer_api.PROVIDER_PAUSED)  # a first processing paused under the hold [R2:truth-RT6]
        self.assertEqual(provider_holds.active().count(), 1)  # one hold per refusal
        self.release()
        self.assertEqual(progress.encounter_progress(self.fresh_row(third))['phase'], 'stopped')  # [R3:truth-R3T-7]
        self.assertIsNotNone(jobs.resume(encounter, self.user))
        self.drain()
        self.assertEqual(self.corti.sent[sends:], [refused.request_sha256])  # once, the identical request
        row = self.fresh_row(encounter)
        self.assertTrue(review.fresh(row))
        self.assertEqual(review.values(row.current_assessment.context), {'service_date': D2})

    def test_u20_r3b5_a_first_processing_paused_by_its_own_402_then_a_setting_save_before_and_after_the_release(self):
        """[R2:truth-RT6][R3:binding-R3B-5][R3:truth-R3T-7]: the first processing's own 402 pauses it (PROVIDER_PAUSED,
        never a final made with the refused run); a setting save while paused queues the predict - never a re-check
        with the hold-setting run - which pauses again while the hold stands; after the release it reads stopped by the
        system with Resume, and Resume sends once."""
        from studio import customer_api

        self.corti.outcomes = [corti_refusal(402)]
        encounter, _ = self.upload(UNDATED, values={'service_date': D2})
        self.drain()
        row = self.fresh_row(encounter)
        self.assertIsNone(row.current_assessment_id)
        self.assertEqual(progress.encounter_progress(row)['error']['text'], customer_api.PROVIDER_PAUSED)
        sends = len(self.corti.sent)
        self.save(encounter, setting=OFFICE)
        [queued] = Job.objects.filter(encounter=encounter, state=Job.QUEUED)
        self.assertEqual(queued.kind, Job.PREDICT)
        self.drain()
        self.assertEqual(len(self.corti.sent), sends)  # paused again: the hold stands
        self.assertIsNone(self.fresh_row(encounter).current_assessment_id)
        self.release_corti()
        panel = progress.encounter_progress(self.fresh_row(encounter))
        self.assertEqual((panel['phase'], panel['error']['action']), ('stopped', 'resume'))
        self.assertNotEqual(panel['error']['text'], customer_api.PROVIDER_PAUSED)
        self.assertIsNotNone(jobs.resume(encounter, self.user))
        self.drain()
        self.assertEqual(len(self.corti.sent), sends + 1)  # once, after the release
        row = self.fresh_row(encounter)
        self.assertTrue(review.fresh(row))
        self.assertEqual(review.values(row.current_assessment.context), {'service_date': D2, 'setting': OFFICE})

    def test_u20_the_token_endpoints_429_and_400_hold_and_its_500_fails_with_the_retry_door(self):
        from studio import customer_api

        for outcome, reason in ((token_refusal(429), provider_holds.QUOTA), (token_refusal(400), provider_holds.AUTH),
                                (token_refusal(500), None)):
            with self.subTest(status=outcome.http_status):
                self.new_workspace()
                encounter = self.v2_fixture(UNDATED)
                self.corti.outcomes = [outcome]
                self.save(encounter, service_date=D2)
                self.drain()
                [run] = Run.objects.filter(encounter=encounter, http_status=outcome.http_status)
                self.assertEqual((run.state, run.sent), (Run.NOT_SENT, False))
                row = self.fresh_row(encounter)
                panel = progress.encounter_progress(row)
                if reason is None:
                    self.assertFalse(provider_holds.active().exists())
                    self.assertEqual(panel['error'], {'text': customer_api.update_text(
                        'review_not_sent', review.UPDATE_DETAILS, True), 'action': 'retry_update'})
                    continue
                [hold] = provider_holds.active()
                self.assertEqual((hold.reason, hold.http_status, hold.run_id), (reason, outcome.http_status, run.pk))
                self.assertEqual(panel['phase'], 'paused')
                self.release()

    def test_u20_r3b1_a_402_whose_record_fails_is_unknown_with_its_hold(self):
        from studio import customer_api

        encounter = self.v2_fixture(UNDATED)
        other = self.v2_fixture(UNDATED)
        self.corti.outcomes = [corti_refusal(402)]
        self.save(encounter, service_date=D2)
        with mock.patch.object(jobs, '_finish_run', side_effect=RuntimeError('synthetic: the record failed')):
            self.drain()
        [run] = Run.objects.filter(encounter=encounter, http_status=402)
        self.assertEqual((run.state, run.sent), (Run.UNKNOWN, True))
        [hold] = provider_holds.active()
        self.assertEqual(hold.run_id, run.pk)
        row = self.fresh_row(encounter)
        self.assertEqual(progress.encounter_progress(row)['phase'], 'being_confirmed')
        with self.assertRaises(jobs.Refused) as retry:
            jobs.retry_update(encounter, self.user)
        self.assertEqual(str(retry.exception), jobs.RETRY_UNKNOWN)
        sends = len(self.corti.sent)
        self.save(other, service_date=D3)
        self.drain()
        self.assertEqual(len(self.corti.sent), sends)
        self.assertTrue(Run.objects.filter(encounter=other, scope__held=provider_holds.HELD).exists())
        self.assertNotIn(customer_api.PROVIDER_PAUSED, str(progress.encounter_progress(row)))

    def test_u20_rt2_a_legacy_es_pre_install_429_or_token_refusal_edited_with_the_request_unchanged(self):
        """[R2:truth-RT2]: a legacy E whose own Corti run the installed release recorded FAILED with 429 (no ProviderHold
        row names it: recorded before the install) - a setting save keeps the request, so the update goes on with E's
        own outcome, nothing sent and no hold set; and one whose run is that release's token refusal (recorded not sent,
        no status) - sent once after the install, as its first attempt."""
        installed_token_refusal = RawExchange(outcome='not_sent', sent=False, error=(
            'Corti authentication was refused (HTTP 401); no coding request was sent.'))
        for outcome, sends in ((corti_refusal(429), 0), (installed_token_refusal, 1)):
            with self.subTest(status=outcome.http_status, sent=outcome.sent):
                self.new_workspace()
                self.corti.outcomes = [outcome]
                with mock.patch.object(provider_holds, 'record', return_value=None):  # the installed release set none
                    encounter = self.legacy_fixture()
                earlier = encounter.current_assessment
                self.assertEqual((earlier.provider_run.http_status, provider_holds.active().exists()),
                                 (outcome.http_status, False))
                before = len(self.corti.sent)
                self.save(encounter, setting=OFFICE)
                self.drain()
                self.assertEqual(len(self.corti.sent) - before, sends)
                self.assertFalse(provider_holds.active().exists())
                row = self.fresh_row(encounter)
                self.assertTrue(review.fresh(row), progress.encounter_progress(row))
                self.assertNotEqual(row.current_assessment_id, earlier.pk)
                run = row.current_assessment.provider_run
                if sends:
                    self.assertEqual((run.state, run.sent), (Run.SUCCEEDED, True))
                else:  # E's own outcome: the not-resent record of its own request
                    self.assertEqual((run.state, run.request_sha256), (Run.NOT_SENT, earlier.provider_run.request_sha256))
                    self.assertTrue(run.error.startswith(jobs.FAILED_BEFORE_MESSAGE))

    def test_u20_r3b4_a_refusal_recorded_before_the_install_is_held_by_the_failed_before_door(self):
        """A FAILED 429 for D2's request that no ProviderHold row names (synthetic: recorded by the installed release)
        is held against its identical request: the update meeting it sends nothing and ends failed with the
        refused-before row; its Retry is refused; a save back restores the earlier codes."""
        from studio import customer_api

        encounter = self.v2_fixture(UNDATED)
        earlier = encounter.current_assessment
        revision = encounter.current_revision
        request = self.corti.build_request(revision.text, date.fromisoformat(D2))
        data = b'{"error": "synthetic quota"}'
        Run.objects.create(encounter=encounter, revision=revision, provider='corti',
                           adapter_version=self.corti.adapter_version, request_sha256=request.canonical_sha256,
                           request_body=request.body, contexts=list(request.contexts), state=Run.FAILED, sent=True,
                           http_status=429, response_bytes=data, response_sha256=hashlib.sha256(data).hexdigest(),
                           error='Corti answered HTTP 429; the response body is retained.',
                           service_date=date.fromisoformat(D2), started_at=timezone.now(), finished_at=timezone.now())
        sends = len(self.corti.sent)
        self.save(encounter, service_date=D2)
        self.drain()
        self.assertEqual(len(self.corti.sent), sends)
        self.assertFalse(provider_holds.active().exists())
        row = self.fresh_row(encounter)
        self.assertEqual(progress.encounter_progress(row)['error'], {
            'text': customer_api.update_text('review_refused_before', review.UPDATE_DETAILS, True), 'action': 'none'})
        with self.assertRaises(jobs.Refused) as retry:
            jobs.retry_update(encounter, self.user)
        self.assertEqual(str(retry.exception), customer_api.RETRY_UPDATE_REFUSED_BEFORE)
        self.assertTrue(self.save(encounter, service_date='').restored)
        self.assertEqual(self.fresh_row(encounter).current_assessment_id, earlier.pk)


class ChainReRunTests(UpdateCase):
    """U22's pipeline half: A21 - the earlier codes' own unknown document review reconciled with no save."""

    def test_u22_a21_a_legacy_es_own_unknown_review_reconciled_runs_the_reading_never_superseded(self):
        encounter = self.legacy_fixture()
        earlier = encounter.current_assessment
        Run.objects.filter(pk=earlier.provider_run_id).update(state=Run.UNKNOWN,
                                                              error='Read timed out after the request was sent.')
        row = self.fresh_row(encounter)
        self.assertEqual(review._state_and_run(row)[0], 'provider_unknown')  # before: being confirmed
        self.assertTrue(jobs.reconcile(encounter, Run.objects.get(pk=earlier.provider_run_id), self.user,
                                       'Synthetic: the vendor log shows no answer.'))
        row = self.fresh_row(encounter)
        self.assertEqual((review.fresh(row), review.update_kind(row)), (False, review.UPDATE_CHECK))
        self.assertEqual(progress.encounter_progress(row)['phase'], 'updating')
        self.drain()
        self.assertFalse(Job.objects.filter(encounter=encounter, result__contains={'superseded': True}).exists())
        row = self.fresh_row(encounter)
        self.assertTrue(review.fresh(row))
        self.assertNotEqual(row.current_assessment_id, earlier.pk)
        self.assertEqual(len(self.corti.sent), 1)  # the released predict, once
        self.assertEqual([purpose for purpose, _ in self.gemini_sends()], [EXTRACTION, APPRAISAL])
