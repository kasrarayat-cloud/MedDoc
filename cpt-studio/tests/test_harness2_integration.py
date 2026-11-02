"""harness@2 part B integrated (HARNESS.md 12): the pipeline package's records read by the review package's API,
candidates, confirmation and reports, each fact computed ONCE and read the same way on both sides, and a reviewer's
confirmation carried end to end through the real pipeline with nothing mocked between the endpoint and the engine.

Synthetic data only; nothing is sent. The fixtures are the pipeline suite's (tests.test_harness2_pipeline): Corti's
in-process fake, Astra and Fable as the real replay adapters on the real tool loop, and CPT Studio's real CMS tool
executor over a synthetic reference store and the bundled passages.
"""
import hashlib
import json
from datetime import timedelta
from unittest import mock

from django.test import override_settings
from django.utils import timezone

from studio import jobs, models, reports, review, serializers
from studio.reference import tools
from studio.types import EvidenceSpan, to_jsonable
from tests.test_harness2_pipeline import (LAND, PFS_KEY, TWO_EXTENTS, ColonCase, Harness2Case, answered, asks, failed,
                                          open_questions, passages_call, reading)
from tests.test_harness_pipeline import TIME_QUOTE
from tests.test_harness_pipeline import _WorkerDied
from tests.test_pipeline_api import drain
from tests.test_repairs_pipeline import RECONCILE_NOTE


def confirm(case, encounter_id, question, candidate):
    """POST the confirmation endpoint (HARNESS.md 12.5) with the candidate's id and the attestation served with it."""
    return case.post(f'/api/encounters/{encounter_id}/clarifications/{question.pk}/confirm',
                     {'candidate_id': candidate['id'], 'attestation': candidate['attestation']})


def served_candidates(case, encounter_id, question):
    detail = case.client.get(f'/api/encounters/{encounter_id}').json()
    return next(c for c in detail['clarifications'] if c['id'] == str(question.pk))['candidates']


# --- a confirmation, end to end (HARNESS.md 11.3, 12.1, 12.5) ---------------------------------------------------------

class ConfirmationEndToEndTests(ColonCase):
    def extent_question(self, assessment):
        question = assessment.clarifications.get(proposal__key='sel:0', state=models.Clarification.OPEN)
        self.assertEqual((question.fact, question.proposal.code), ('extent', '45385'))
        return question

    def test_a_confirmation_is_read_by_the_reassessment_it_queues_inside_its_transaction_and_nothing_is_sent(self):
        encounter_id = self.create(TWO_EXTENTS)
        drain()
        final = self.encounter(encounter_id).current_assessment
        self.assertEqual((jobs.assessment_phase(final), review.is_final(final)), (2, True))
        question = self.extent_question(final)
        # Astra's peer review answered assess #1's question about 45385's extent with the landmark passage: one verified
        # candidate, in CPT Studio's words, located by Astra after peer review
        candidate = next(c for c in served_candidates(self, encounter_id, question) if c['verified'])
        self.assertEqual((candidate['value'], candidate['located_by'], candidate['phase'],
                          candidate['spans'][0]['text']), ('cecum', ['astra'], 'peer_review', LAND))
        made = models.Job.objects.get(encounter_id=encounter_id, kind='assess', result__assessment=str(final.pk))
        before = (models.ProviderRun.objects.count(), models.ProviderExchange.objects.count(),
                  [len(adapter.loops) for adapter in self.adapters.values()], len(self.corti.requests))
        response = confirm(self, encounter_id, question, candidate)
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.json()['effect'], 'reassessment')
        confirmation = models.FindingConfirmation.objects.get()
        # jobs.reassess_after_confirmation ran inside confirm_finding's transaction, under the encounter row lock: the
        # one re-assessment is queued under the final assessment's key with the confirmations' digest
        queued = self.jobs_of(encounter_id)[-1]
        digest = hashlib.sha256(str(confirmation.pk).encode()).hexdigest()[:12]
        self.assertEqual((queued.kind, queued.state, queued.idempotency_key, queued.context_id, queued.provider_run_id,
                          queued.requested_by_id),
                         ('assess', 'queued', f'{made.idempotency_key}:c:{digest}', final.context_id,
                          final.provider_run_id, self.reviewer.pk))
        self.assertEqual(self.encounter(encounter_id).state, 'processing')
        drain()
        again = self.encounter(encounter_id).current_assessment
        self.assertNotEqual(again, final)
        # nothing was sent, nothing more was queued, and no peer review was asked for
        after = (models.ProviderRun.objects.count(), models.ProviderExchange.objects.count(),
                 [len(adapter.loops) for adapter in self.adapters.values()], len(self.corti.requests))
        self.assertEqual(after, before)
        self.assertEqual(self.jobs_of(encounter_id)[-1].pk, queued.pk)
        self.assertEqual(models.Job.objects.get(pk=queued.pk).state, 'succeeded')
        # the engine read the confirmation, and says it is a confirmation, never the reader's own reading
        item = again.proposals.get(key='sel:0')
        self.assertEqual((item.code, item.status, item.support['confirmed']),
                         ('45385', 'ready', [str(confirmation.pk)]))
        words = f"confirmed from Astra's located passage by {self.reviewer.label()}"
        recorded = json.dumps([item.rationale, item.checks, item.support])
        self.assertIn(words, recorded)
        self.assertIn('confirmations.applied', [c['id'] for c in again.encounter_checks])
        self.assertNotIn('confirmations.ignored', [c['id'] for c in again.encounter_checks])
        self.assertEqual(again.proposals.get(key='sel:1').status, 'needs_clarification')  # another question
        # what it read is the stored passage, each span exactly as the review package records it
        (finding,) = jobs.confirmed_findings(again.revision)
        self.assertEqual(finding.evidence, tuple(EvidenceSpan(0, span['start'], span['end'], span['text'], True,
                                                              span['page']) for span in confirmation.spans))
        self.assertEqual((finding.located_by, finding.confirmed_by, finding.confirmation_id),
                         (('astra',), self.reviewer.label(), str(confirmation.pk)))
        # it reads exactly what the final assessment read
        before_records, after_records = self.records(final), self.records(again)
        for name in ('astra', 'fable'):
            for key in ('state', 'run', 'reading_sha256', 'peer_state', 'peer_run', 'peer_sha256'):
                self.assertEqual(after_records[name][key], before_records[name][key], (name, key))
        # nothing is approved: the code is ready for a member's decision, which stays the member's (I3, I4)
        self.assertFalse(models.Decision.objects.exists())
        proposal = next(p for p in self.client.get(f'/api/encounters/{encounter_id}').json()['assessment']['proposals']
                        if p['key'] == 'sel:0')
        self.assertEqual((proposal['decision_state'], proposal['confirmed']), ('undecided', [str(confirmation.pk)]))
        # the confirmed question is answered and raised no more, and the confirmation is still listed
        self.assertFalse(again.clarifications.filter(proposal__key='sel:0', state=models.Clarification.OPEN).exists())
        detail = self.client.get(f'/api/encounters/{encounter_id}').json()
        self.assertEqual([c['id'] for c in detail['confirmations']], [str(confirmation.pk)])

    def test_a_refused_reassessment_leaves_nothing_recorded(self):
        encounter_id = self.create(TWO_EXTENTS)
        drain()
        final = self.encounter(encounter_id).current_assessment
        question = self.extent_question(final)
        candidate = next(c for c in served_candidates(self, encounter_id, question) if c['verified'])
        # a member's save queued a new assess, which a Stop cancelled: the final assessment is still the one shown,
        # but it is no longer the current context's, so there is nothing to re-assess
        self.assertEqual(self.post(f'/api/encounters/{encounter_id}/context', {'setting': 'office'}).status_code, 201)
        self.assertEqual(self.client.post(f'/api/encounters/{encounter_id}/stop').status_code, 200)
        self.assertEqual(self.encounter(encounter_id).current_assessment, final)
        response = confirm(self, encounter_id, question, candidate)
        self.assertEqual(response.status_code, 409, response.content)
        self.assertEqual(response.json()['error'], jobs.REASSESS_NONE)
        self.assertFalse(models.FindingConfirmation.objects.exists())
        self.assertFalse(models.AuditEvent.objects.filter(event='finding.confirmed').exists())


# --- one implementation per fact (HARNESS.md 12.3, 12.6) -------------------------------------------------------------

class OneReadingTests(Harness2Case):
    """Each fact both packages read - an assessment's phase, a run's reading and peer review, the frozen sha256s, a
    run's retrieved and used references - has one implementation, the pipeline's, and every page reads it there."""

    def setUp(self):
        super().setUp()
        self.adapters['astra'].peer = [
            asks('astra', passages_call('call_peer_1', 'ncci_endoscopy_rules'), number=3),
            answered('astra', {'question_answers': [], 'code_positions': [], 'additional_codes': [],
                               'references_used': [{'ref': 'rule-01', 'use': 'Retrieved in this peer review.'},
                                                   {'ref': f'fact:{PFS_KEY}:99213:status',
                                                    'use': 'Retrieved by the first reading only.'}]}, number=4)]

    def runs(self, encounter_id):
        return [run for run in self.runs_of(encounter_id) if run.provider in ('astra', 'fable')]

    def test_the_phase_is_the_pipelines_on_every_page(self):
        encounter_id = self.create()
        drain()
        first, final = self.assessments(encounter_id)
        for assessment in (first, final, None):
            self.assertEqual(review.assessment_phase(assessment), jobs.assessment_phase(assessment))
        detail = self.client.get(f'/api/encounters/{encounter_id}').json()
        self.assertEqual(detail['harness']['phase'], jobs.assessment_phase(final))
        owner = models.Membership.objects.get(user=self.reviewer, workspace=self.ws)
        owner.role = models.Membership.OWNER
        owner.save(update_fields=['role'])
        trace = self.client.get(f'/api/encounters/{encounter_id}/trace').json()
        self.assertEqual([a['phase'] for a in trace['assessments']], [jobs.assessment_phase(first),
                                                                      jobs.assessment_phase(final)])
        snapshot = reports.snapshot(self.encounter(encounter_id), 'draft')
        self.assertEqual(snapshot['phase'], jobs.assessment_phase(final))

    def test_a_reading_and_a_peer_review_are_read_by_the_pipelines_readers_on_every_page(self):
        encounter_id = self.create()
        drain()
        owner = models.Membership.objects.get(user=self.reviewer, workspace=self.ws)
        owner.role = models.Membership.OWNER
        owner.save(update_fields=['role'])
        trace = self.client.get(f'/api/encounters/{encounter_id}/trace').json()
        traced = {run['id']: run for participant in trace['participants'] for run in participant['runs']}
        for run in self.runs(encounter_id):
            with self.subTest(provider=run.provider, purpose=run.purpose):
                if run.purpose == models.ProviderRun.PEER_REVIEW:
                    expected = jobs.peer_reading(run)
                    self.assertEqual(review.stored_peer_review(run), expected)
                    self.assertEqual(traced[str(run.pk)]['review'], json.loads(json.dumps(to_jsonable(expected[0]))))
                else:
                    expected = jobs.participant_reading(run)
                    self.assertEqual(review.stored_reading(run), expected)
                    self.assertEqual(traced[str(run.pk)]['reading']['references_used'],
                                     to_jsonable(expected[0])['references_used'])
                self.assertIsNotNone(expected[0])

    def test_the_frozen_sha256s_are_one_function(self):
        encounter_id = self.create()
        drain()
        first, final = self.assessments(encounter_id)
        readings, reviews = review.frozen_inputs(final)
        self.assertEqual(([r.name for r in readings], [name for name, _, _ in reviews]), (['astra', 'fable'],
                                                                                         ['astra', 'fable']))
        records = self.records(final)
        for item in readings:
            self.assertEqual(records[item.name]['reading_sha256'], jobs.answer_sha256(item.reading))
            self.assertEqual(self.records(first)[item.name]['reading_sha256'], jobs.answer_sha256(item.reading))
        for name, run_id, peer in reviews:
            self.assertEqual((records[name]['peer_run'], records[name]['peer_sha256']),
                             (run_id, jobs.answer_sha256(peer)))
        # the frozen list the assessments recorded names exactly those sha256s
        self.assertEqual(records['astra']['frozen'][1:3], [['astra', records['astra']['reading_sha256']],
                                                           ['fable', records['fable']['reading_sha256']]])

    def test_retrieved_references_are_the_executors_own_and_used_is_the_readers_check(self):
        encounter_id = self.create()
        drain()
        source = models.ReferenceSource.objects.get(key=PFS_KEY)
        detail = self.client.get(f'/api/encounters/{encounter_id}').json()
        rows = {row['name']: row for row in detail['harness']['participants']}
        for name, field, purpose in (('astra', 'references', 'independent'), ('fable', 'references', 'independent'),
                                     ('astra', 'peer_references', 'peer_review')):
            with self.subTest(name=name, purpose=purpose):
                run = self.runs_of(encounter_id, name, purpose)[0]
                shown = rows[name][field]
                calls = list(models.ToolCall.objects.filter(exchange__run=run).order_by('exchange__turn', 'id'))
                self.assertTrue(calls)
                # every ref the run's own tool calls returned, once, each dated as the executor's result states it
                self.assertEqual({item['ref'] for item in shown['retrieved']}, set(jobs.run_refs(run)))
                stated = {item['ref']: item for call in calls for item in tools.retrieved_references(call.result)}
                for item in shown['retrieved']:
                    for key in ('source_key', 'release', 'effective_start', 'effective_end'):
                        self.assertEqual(item[key], str(stated[item['ref']][key]), (item['ref'], key))
                    self.assertEqual(item['kind'], 'fact' if item['ref'].startswith('fact:') else 'passage')
                # 'used' is the reader's own check, which agrees with the retrieved list
                reading = (jobs.peer_reading(run) if purpose == 'peer_review' else jobs.participant_reading(run))[0]
                self.assertEqual(shown['used'], [{'ref': ref.ref, 'use': ref.use, 'retrieved': ref.retrieved}
                                                 for ref in reading.references_used])
                retrieved = {item['ref'] for item in shown['retrieved']}
                self.assertTrue(all(item['retrieved'] == (item['ref'] in retrieved) for item in shown['used']))
        # a fact the executor returned carries the installed source's own release and window
        fact = next(item for item in rows['astra']['references']['retrieved'] if item['ref'].startswith('fact:'))
        self.assertEqual((fact['source_key'], fact['release'], fact['effective_start'], fact['effective_end']),
                         (PFS_KEY, source.release, '2026-10-01', '2026-12-31'))
        # the peer review's retrieval never counts for the first reading's, nor the reverse (11.2)
        peer_used = {item['ref']: item['retrieved'] for item in rows['astra']['peer_references']['used']}
        self.assertEqual(peer_used, {'rule-01': True, f'fact:{PFS_KEY}:99213:status': False})

    def test_a_reused_run_is_read_with_the_refs_of_the_loop_that_answered_it_on_every_page(self):
        first_id = self.create()
        drain()
        second_id = self.create()  # the identical requests in the same workspace: every participant run is a reuse
        drain()
        for name in ('astra', 'fable'):
            with self.subTest(name):
                original = self.runs_of(first_id, name, 'independent')[0]
                reused = self.runs_of(second_id, name, 'independent')[0]
                self.assertEqual((reused.reused_from_id, reused.exchanges.count()), (original.pk, 0))
                self.assertEqual(review.run_refs(reused), jobs.run_refs(original))
                self.assertEqual(review.stored_reading(reused), jobs.participant_reading(original))
                self.assertEqual(review.participant_references(reused), review.participant_references(original))
                self.assertTrue(review.participant_references(reused)['retrieved'])
        # the second encounter's final assessment reads both frozen readings back as recorded: none is dropped
        readings, reviews = review.frozen_inputs(self.encounter(second_id).current_assessment)
        self.assertEqual(([r.name for r in readings], [name for name, _, _ in reviews]), (['astra', 'fable'],
                                                                                         ['astra', 'fable']))


class QuestionIdentityTests(ColonCase):
    def test_a_peer_answer_is_matched_by_the_identity_its_request_described(self):
        encounter_id = self.create(TWO_EXTENTS)
        drain()
        first, final = self.assessments(encounter_id)
        for name in ('astra', 'fable'):
            run = self.runs_of(encounter_id, name, 'peer_review')[0]
            shown = self.adapters[name].loops_of('peer')[0]['bodies'][0]
            self.assertEqual(shown, run.request_body)
            asked = open_questions(name, run.request_body)
            self.assertTrue(asked)
            for question in asked:
                clarification = models.Clarification.objects.select_related('proposal').get(pk=question['question_id'])
                self.assertEqual(clarification.assessment_id, first.pk)
                self.assertEqual((question['scope'], question['family'], question['fact'], question['proposal_key']),
                                 review.question_identity(clarification)[:4])
        # Astra answered assess #1's question about 45385's extent; the candidates match it to the final assessment's
        # question with the same identity, the code included
        readings, reviews = review.frozen_inputs(final)
        questions = list(final.clarifications.filter(state=models.Clarification.OPEN).select_related('proposal'))
        matched = review.peer_answers(final, questions, reviews)
        answered_questions = [q for q in questions if matched[q.pk]]
        self.assertEqual([(q.proposal.key, q.proposal.code, q.fact) for q in answered_questions],
                         [('sel:0', '45385', 'extent')])
        (answer,) = matched[answered_questions[0].pk]
        asked = models.Clarification.objects.select_related('proposal').get(pk=answer.answer.question_id)
        self.assertEqual(asked.assessment_id, first.pk)
        self.assertEqual(review.question_identity(asked), review.question_identity(answered_questions[0]))


# --- the peer runs' records (HARNESS.md 12.1, 12.6) -------------------------------------------------------------------

class PeerRunRecordTests(Harness2Case):
    def assertEveryPeerRunNamesItsModeAndAssessment(self, expected_states):
        runs = list(models.ProviderRun.objects.filter(purpose=models.ProviderRun.PEER_REVIEW).order_by('created_at'))
        self.assertEqual(sorted(run.state for run in runs), sorted(expected_states))
        for run in runs:
            with self.subTest(run=str(run.pk), state=run.state):
                self.assertEqual(set(run.scope) - {'held'}, {'mode', 'assessment'})
                assessment = models.Assessment.objects.get(pk=run.scope['assessment'])
                self.assertEqual(assessment.revision_id, run.revision_id)
                self.assertEqual(review.run_mode(run), run.scope['mode'])

    def test_every_peer_run_records_its_mode_and_the_assessment_it_was_made_for(self):
        self.adapters['astra'].peer_loops = [[failed()]]
        first = self.create()
        drain()  # Astra's peer review fails; Fable's is sent
        self.assertEqual(self.post(f'/api/encounters/{first}/context', {'setting': 'office'}).status_code, 201)
        drain()  # a new assess #1: Astra's failed request is never sent again; Fable's answer is reused
        with mock.patch.object(self.adapters['fable'], 'build_peer_request', side_effect=ValueError('synthetic')), \
                self.assertLogs('studio.jobs', level='ERROR'):
            self.create('SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT\n' + self.encounter(first).current_revision.text)
            drain()  # another document: Astra's peer review is sent; Fable's request cannot be built
        self.assertEveryPeerRunNamesItsModeAndAssessment(
            ['failed', 'succeeded', 'not_sent', 'succeeded', 'succeeded', 'not_sent'])
        reused = models.ProviderRun.objects.filter(purpose=models.ProviderRun.PEER_REVIEW, reused_from__isnull=False)
        self.assertEqual([run.provider for run in reused], ['fable'])

    def test_a_replayed_peer_review_reads_replay_and_a_live_one_live(self):
        encounter_id = self.create()
        job = self.run_until('astra_peer')
        self.adapters['astra'].mode = 'live'
        with override_settings(AUTHORIZATION_REF=''):
            jobs.run_job(job)  # refused by the live gate: recorded not sent, in live mode
        self.adapters['astra'].mode = 'replay'
        drain()
        detail = self.client.get(f'/api/encounters/{encounter_id}').json()
        modes = {(run['provider'], run['purpose']): run['mode'] for run in detail['provider_runs']}
        self.assertEqual((modes[('astra', 'peer_review')], modes[('fable', 'peer_review')]), ('live', 'replay'))
        self.assertEqual({(run['provider'], run['purpose']): run['mode'] for run in detail['provider_runs']
                          if run['purpose'] == 'independent'}, {('astra', 'independent'): 'replay',
                                                                ('fable', 'independent'): 'replay'})


# --- the derived state of a peer stage that did not finish (HARNESS.md 12.1) ------------------------------------------

class PeerStageStateTests(Harness2Case):
    def test_a_peer_stage_left_mid_send_is_the_encounter_wide_unknown_outcome_never_a_processing_failure(self):
        encounter_id = self.create()
        job = self.run_until('astra_peer')
        with mock.patch.object(self.adapters['astra'], 'send_loop', side_effect=_WorkerDied()):
            with self.assertRaises(_WorkerDied):
                jobs.run_job(job)
        models.Job.objects.filter(pk=job.pk).update(started_at=timezone.now() - timedelta(minutes=11))
        jobs.mark_stale()
        job.refresh_from_db()
        self.assertEqual(job.state, 'unknown')
        self.assertEqual(self.encounter(encounter_id).state, 'provider_unknown')
        peer = self.runs_of(encounter_id, 'astra', 'peer_review')[0]
        self.assertEqual(self.post(f'/api/encounters/{encounter_id}/reconcile',
                                   {'provider_run_id': str(peer.pk), 'note': RECONCILE_NOTE}).status_code, 201)
        drain()
        self.assertEqual(self.encounter(encounter_id).state, 'ready_for_review')

    def test_a_peer_stage_that_failed_is_a_processing_failure_never_provider_failed(self):
        encounter_id = self.create()
        job = self.run_until('astra_peer')
        with mock.patch('studio.jobs._peer_material', side_effect=RuntimeError('synthetic')), \
                self.assertLogs('studio.jobs', level='ERROR'):
            jobs.run_job(job)
        job.refresh_from_db()
        self.assertEqual(job.state, 'failed')
        self.assertEqual(self.encounter(encounter_id).state, 'processing_failed')
        self.assertIsNone(review.state_run(self.encounter(encounter_id)))


# --- the stage order the API reads (HARNESS.md 12.1) ------------------------------------------------------------------

class StageOrderTests(Harness2Case):
    def test_the_stage_order_is_the_order_the_pipeline_runs_and_assess_two_follows_the_peer_stages(self):
        encounter_id = self.create()
        drain()
        chain = self.jobs_of(encounter_id)
        self.assertEqual([job.kind for job in chain], list(serializers.STAGE_ORDER))
        self.assertEqual([serializers._stage_index(job) for job in chain], list(range(len(chain))))
        self.assertEqual(serializers.PEER_STAGES, tuple(jobs.PEER_KIND[name] for name in ('astra', 'fable')))
        self.assertEqual({name: stages for name, stages in serializers.HARNESS_STAGES.items() if name != 'corti'},
                         {name: (name, jobs.PEER_KIND[name]) for name in ('astra', 'fable')})
        # assess #2 is no stage before the peer stages: the chain has reached them
        latest, ahead = serializers._stage_progress(chain, models.Job.ASTRA_PEER)
        self.assertEqual((latest.pk, ahead), (chain[6].pk, False))
        # a new assess #1 is: the chain it starts has yet to reach them
        self.assertEqual(self.post(f'/api/encounters/{encounter_id}/context', {'setting': 'office'}).status_code, 201)
        chain = self.jobs_of(encounter_id)
        self.assertEqual(serializers._stage_progress(chain, models.Job.ASTRA_PEER)[1], True)
        drain()
        # a re-assessment after a confirmation follows the peer stages, as assess #2 does
        chain = self.jobs_of(encounter_id)
        again = models.Job(kind=models.Job.ASSESS, idempotency_key=f'{chain[-1].idempotency_key}:c:{"0" * 12}',
                           created_at=timezone.now(), state=models.Job.QUEUED)
        self.assertEqual(serializers._stage_index(again), len(serializers.STAGE_ORDER) - 1)
        self.assertEqual(serializers._stage_progress(chain + [again], models.Job.FABLE_PEER)[1], False)
        # the participant rows read their first-reading stage, as before
        self.assertEqual(serializers._stage_progress(chain + [again], models.Job.ASTRA)[1], False)


# --- the context's audit row (HARNESS.md 12.5) ------------------------------------------------------------------------

class ContextAuditTests(Harness2Case):
    def test_a_members_own_save_records_no_confirmation(self):
        encounter_id = self.create()
        drain()
        self.assertEqual(self.post(f'/api/encounters/{encounter_id}/context', {'setting': 'office'}).status_code, 201)
        event = models.AuditEvent.objects.get(encounter_id=encounter_id, event='context.changed')
        self.assertEqual(set(event.data), {'fields', 'context'})


# --- which assessment is final: one rule for the pipeline and the API (HARNESS.md 12.1, 12.5) -------------------------

DATE_LINE = 'Date of service: 2026-10-20'


class FinalAssessmentTests(Harness2Case):
    def assertTheApiReadsTheFinalAssessmentAsThePipelineDecided(self, encounter_id):
        """Every assess #1 the pipeline made queued a peer stage exactly when the API reads it as not final."""
        for job in models.Job.objects.filter(encounter_id=encounter_id, kind='assess', state='succeeded'):
            if jobs._assess_mode(job) != jobs.FIRST or 'assessment' not in (job.result or {}):
                continue
            assessment = models.Assessment.objects.get(pk=job.result['assessment'])
            queued = 'peer_review' in job.result
            self.assertEqual(bool(jobs.owed_peer_stages(assessment)), queued, job.idempotency_key)
            self.assertEqual(review.is_final(assessment), not queued, job.idempotency_key)

    def test_the_api_and_the_pipeline_agree_on_the_final_assessment_in_each_chain(self):
        self.adapters['astra'].first = self.adapters['fable'].first = [failed()]
        failing = self.create()  # no first reading read: assess #1 is final
        drain()
        self.adapters['astra'].first = [asks('astra', ('call_astra_1', 'cms_code_facts',
                                                       {'codes': ['99213'], 'date_of_service': '2026-10-20'})),
                                        answered('astra', reading(codes=[('99213', TIME_QUOTE)]), number=2)]
        self.adapters['fable'].first = [answered('fable', reading(codes=[('99213', TIME_QUOTE)]))]
        normal = self.create('SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT\n' + self.encounter(failing)
                             .current_revision.text)
        drain()
        for encounter_id in (failing, normal):
            self.assertTheApiReadsTheFinalAssessmentAsThePipelineDecided(encounter_id)
        self.assertEqual([jobs.assessment_phase(a) for a in self.assessments(failing)], [1])
        self.assertEqual([jobs.assessment_phase(a) for a in self.assessments(normal)], [1, 2])

    def test_a_held_first_assessment_is_final_and_its_date_question_is_confirmed_through_the_context(self):
        for name in ('astra', 'fable'):
            self.adapters[name].first = [answered(name, reading(codes=[('99213', TIME_QUOTE)], date_value='2026-10-20',
                                                                date_evidence=[DATE_LINE]))]
        encounter_id = self.create()
        drain()
        # a member enters another date: the hold. The assess reads the frozen readings and queues no peer review, so
        # it is the final assessment - the API says so, and offers the readings' located date for the date question
        response = self.post(f'/api/encounters/{encounter_id}/context', {'service_date': '2026-10-22'})
        self.assertEqual(response.status_code, 201, response.content)
        drain()
        held = self.encounter(encounter_id).current_assessment
        self.assertEqual((jobs.assessment_phase(held), jobs.owed_peer_stages(held), review.is_final(held)),
                         (1, [], True))
        self.assertTheApiReadsTheFinalAssessmentAsThePipelineDecided(encounter_id)
        # and the report says why no peer review follows it, never that one does
        snapshot = reports.snapshot(self.encounter(encounter_id), 'draft')
        self.assertEqual((snapshot['peer_review']['owed'], snapshot['peer_review']['held']), (False, True))
        text = reports.render_txt(snapshot).decode('utf-8').splitlines()
        self.assertEqual(text[text.index('PEER REVIEW') + 1],
                         '  - none: the service date entered as encounter metadata conflicts with the document, and no '
                         'peer review is sent while that question is open')
        question = held.clarifications.get(state=models.Clarification.OPEN, scope='encounter', fact='service_date')
        candidate = next(c for c in served_candidates(self, encounter_id, question) if c['verified'])
        self.assertEqual((candidate['value'], candidate['located_by'], candidate['spans'][0]['text']),
                         ('2026-10-20', ['astra', 'fable'], DATE_LINE))
        response = confirm(self, encounter_id, question, candidate)
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.json()['effect'], 'context')
        confirmation = models.FindingConfirmation.objects.get()
        # the date entered as the member's, through the context path, whose own audit row names the confirmation
        event = (models.AuditEvent.objects.filter(encounter_id=encounter_id, event='context.changed')
                 .latest('created_at'))
        self.assertEqual((event.data['fields'], event.data['confirmation']), (['service_date'], str(confirmation.pk)))
        self.assertEqual(self.encounter(encounter_id).user_values, {'service_date': '2026-10-20'})
        drain()
        # the hold is settled: a new assess #1 queues the peer reviews and assess #2 is the final assessment; the
        # engine never read the date's confirmation (it is the context's)
        final = self.encounter(encounter_id).current_assessment
        self.assertEqual((jobs.assessment_phase(final), review.is_final(final)), (2, True))
        self.assertEqual(jobs.confirmed_findings(final.revision), ())
        self.assertNotIn('confirmations.ignored', [c['id'] for c in final.encounter_checks])
        self.assertFalse(final.clarifications.filter(state=models.Clarification.OPEN, fact='service_date').exists())
        self.assertTheApiReadsTheFinalAssessmentAsThePipelineDecided(encounter_id)
        self.assertEqual(self.encounter(encounter_id).state, 'ready_for_review')

    def test_no_candidate_is_offered_while_no_model_participant_is_configured(self):
        for name in ('astra', 'fable'):
            self.adapters[name].first = [answered(name, reading(codes=[('99213', TIME_QUOTE)], date_value='2026-10-20',
                                                                date_evidence=[DATE_LINE]))]
        encounter_id = self.create()
        drain()
        self.assertEqual(self.post(f'/api/encounters/{encounter_id}/context',
                                   {'service_date': '2026-10-22'}).status_code, 201)
        drain()
        held = self.encounter(encounter_id).current_assessment
        self.assertTrue(review.assessment_candidates(held))
        # with both participants disabled since, no assessment would read a confirmation (I1): none is offered
        with override_settings(ASTRA_MODE='disabled', FABLE_MODE='disabled'):
            self.assertEqual(review.assessment_candidates(held), {})
            question = held.clarifications.get(state=models.Clarification.OPEN, fact='service_date')
            self.assertEqual(served_candidates(self, encounter_id, question), [])


# --- an entry read back from JSON ------------------------------------------------------------------------------------

class EntryRunTests(Harness2Case):
    def test_an_entry_that_names_no_run_id_reads_no_run_and_never_fails(self):
        encounter_id = self.create()
        drain()
        final = self.encounter(encounter_id).current_assessment
        record = dict(self.records(final)['astra'])
        self.assertEqual(review.record_run(final, record).pk, self.runs_of(encounter_id, 'astra', 'independent')[0].pk)
        for value in ('not-a-run-id', '', None, 12, ['x']):
            with self.subTest(value=value):
                broken = dict(record, run=value, peer_run=value)
                self.assertIsNone(review.record_run(final, broken))
                self.assertIsNone(review.record_run(final, broken, 'peer_run'))
                self.assertEqual(jobs.recorded_reading(final.revision, broken), (None, None))
                self.assertEqual(jobs.recorded_peer_review(final.revision, broken), (None, None))
        # a run of another participant, or of the other phase, is never the entry's
        fable = self.runs_of(encounter_id, 'fable', 'independent')[0]
        self.assertIsNone(review.record_run(final, dict(record, run=str(fable.pk))))
        self.assertIsNone(review.record_run(final, dict(record, peer_run=record['run']), 'peer_run'))
