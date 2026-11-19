"""studio/review.py's binding of a member's answer on design v2 (docs/gemini-migration/DECISIONS.md D259; step q02's
request R1; built by step 5b of repair round w8r). TEXT-ONLY and SYNTHETIC: tests/v2_documents.py's TWO_PROCEDURES v2
(fictional clinician, no real patient) through tests/v2/test_jobs.PipelineCase - design v2's pipeline in replay, its
pass-1 answer written by hand and pass 2 the faithful oracle; nothing is sent anywhere.

D259: for a proposal of an events@2 assessment whose support carries the item's question, every reading of "the question
a member is asked" - review.asked_fingerprints (what answers.save_details records) and the binding answer_states and
_closed_pairs make at read time - uses that stored fingerprint (engine/assess.question_fingerprint,
cpt-studio-question@2) for the proposal's member key; engine/assess binds the same; v1's binding is unchanged. What is
proved here:
- a "Not documented" saved through the product's own door (answers.save_details) is recorded with the item's stored
  fingerprint, read time binds it by that fingerprint (answer_states: bound, the overlay excludes the code), and the
  recompute the save queues binds it by the same one - the code excluded by that answer, nothing recorded as asked
  differently, the recompute's own item fingerprint equal to it (DoorBindingTests);
- an answer carrying the rendered question's fingerprint (cpt-studio-question@1, what the door recorded before D259)
  is asked differently at read time and at the recompute alike: one fingerprint, never two readings (DoorBindingTests);
- the closed-question reading (_closed_pairs) binds a stored item by its stored fingerprint too (ClosedReadingTests);
- the readings over plain records: only an events@2 assessment's stored item is read, by its code, family and fact
  key, the first in stored order for a key two proposals carry, and only for a key a question asks; a v1 or legacy
  assessment's binding is questions.group's, unchanged (StoredQuestionsTests).

DECISIONS D270 (repair round w9r, step 5b; refute-5b-r1 P1 and P3; TRIAGE G1-01 and G2-11):
- an answer a design v2 proposal records in support['answered'] is applied: after the AGAIN recompute that excluded
  45385 by the door-saved answer, review.answer_states counts it applied, the details panel keeps the answered row with
  the answer in effect, and the customer's account (customer_api.encounter_json) lists no earlier answer and never says
  "This question is no longer asked, so this answer is not applied."; withdrawing it re-queues an AGAIN that holds 45385
  again; a changed answer on the closed row binds to that row's question until its own recompute applies it
  (AppliedAnswerTests; review.answered_items over plain records, AnsweredItemsTests);
- D259 extended to service questions: the renderer records each service question's engine fingerprint
  (completeness['service_questions']), the details door records a service answer with it and read time binds by it,
  as engine/assess does - on refute-5b-r1 P3's input (an EGD whose reach is not stated beside a colonoscopy to the
  cecum, 45378 selected) the stored record and read time agree that the question is answered and closed, and an answer
  carrying the rendered question's fingerprint is asked differently at both (ServiceQuestionTests; the readings over
  plain records, StoredServiceQuestionsTests).
"""
from __future__ import annotations

import json
from types import SimpleNamespace

from django.test import SimpleTestCase

from studio import answers, interpretation, jobs, models, review
from studio.interpretation import overlay
from studio.interpretation.engine import assess as AS
from studio.validation import questions
from tests import v2_documents
from tests.test_pipeline_api import FakeProvider
from tests.v2 import test_assess as TA
from tests.v2.test_jobs import PipelineCase
from tests.v2.test_settle import answer as pass_one, event, fact, frame, session, src

Job = models.Job
KEY = ('45385', 'gi.colonoscopy', 'extent')  # TWO_PROCEDURES v2: 45385 is held on its colonoscopy's extent


class DoorBindingCase(PipelineCase):
    """TWO_PROCEDURES v2 through design v2's pipeline: 43239 READY, 45385 held on the extent (one question)."""

    def setUp(self):
        super().setUp()
        self.interpreter.answers[v2_documents.TWO_PROCEDURES] = v2_documents.two_procedures_answer
        self.provider = FakeProvider(list(v2_documents.TWO_CODES))

    def finished(self):
        """(encounter, final assessment, its proposals in stored order), the pipeline drained."""
        encounter, _ = self.upload(v2_documents.TWO_PROCEDURES)
        done = self.drain()
        self.assertTrue(all(job.state == Job.SUCCEEDED for job in done), [(job.kind, job.error) for job in done])
        encounter.refresh_from_db()
        final = encounter.current_assessment
        self.assertEqual(final.engine_version, interpretation.ENGINE_VERSION_V3)
        return encounter, final, list(final.proposals.order_by('position'))

    def held(self, proposals):
        [held] = [p for p in proposals if p.code == '45385']
        self.assertEqual((held.bucket, held.status, held.family, held.support['item']['fact']),
                         ('selected', 'needs_clarification', 'gi.colonoscopy', 'extent'))
        return held

    def rendered_fingerprint(self, assessment, proposals):
        """The fingerprint of 45385's question as the rendered question gives it (questions.instance over the rendered
        question and its passages: cpt-studio-question@1) - what the details door recorded before D259."""
        current = review.current_decisions(assessment)
        _, stored, decided, kwargs = review._overlay_inputs(assessment, current)
        from studio.interpretation import readers

        views = readers.for_assessment(assessment).views(assessment, stored, decided, kwargs, answers=())
        return questions.group(review.question_pairs(assessment, proposals, views))[KEY]

    def recompute(self, encounter):
        """The AGAIN recompute the answers queued, run: (its job, the assessment it made)."""
        [job] = self.drain()
        self.assertEqual((job.kind, job.state, job.result['mode']), ('assess', Job.SUCCEEDED, 'again'))
        encounter.refresh_from_db()
        return job, encounter.current_assessment


class DoorBindingTests(DoorBindingCase):
    def test_d259_a_door_saved_answer_binds_at_read_time_and_at_the_recompute_by_the_one_stored_fingerprint(self):
        encounter, final, proposals = self.finished()
        held = self.held(proposals)
        stored = held.support['question']  # engine/assess.question_fingerprint of 45385's one item
        self.assertEqual(len(stored), 64)
        self.assertNotEqual(stored, self.rendered_fingerprint(final, proposals))  # @2 over facts, never @1's text
        self.assertEqual(review.stored_questions(final, proposals), {KEY: stored})
        self.assertEqual(review.asked_fingerprints(final), {KEY: stored})  # what the door records now
        # the product's own door: the details panel's row for 45385's question, saved "Not documented"
        [row] = [item for item in answers.details_needed(encounter, final) if '45385' in item['affects']]
        saved = answers.save_details(encounter, self.user, [{'id': row['id'], 'fact': row['fact'],
                                                             'value': models.MemberAnswer.NOT_DOCUMENTED}])
        [answer_id] = saved['answer_ids']
        answer = models.MemberAnswer.objects.get(pk=answer_id)
        self.assertEqual((answer.code, answer.family, answer.fact, answer.question), (*KEY, stored))
        # read time binds it by that fingerprint, and the overlay applies it until the recompute has run
        applied, bound, earlier = review.answer_states(final)
        self.assertEqual(([a.pk for a in applied], [a.pk for a in bound], earlier), ([], [answer.pk], []))
        [view] = [view for view in review.effective_view(final).values() if view.code == '45385']
        self.assertEqual((view.status, view.reason, view.answered), ('excluded', review.DETAIL_UNAVAILABLE, 'extent'))
        # the recompute the save queued binds it by the same fingerprint: 45385 excluded by that answer, nothing asked
        # differently, and the recompute's own item fingerprint is the one recorded
        _, again = self.recompute(encounter)
        [excluded] = [p for p in again.proposals.all() if p.code == '45385']
        self.assertEqual((excluded.bucket, excluded.support['answered']['answers']), ('excluded', [str(answer.pk)]))
        self.assertEqual(excluded.support['question'], stored)
        record = again.completeness['member_answers']
        self.assertEqual(([(entry['answer'], entry['code'], entry['fact']) for entry in record['applied']],
                          record['earlier']), ([(str(answer.pk), '45385', 'extent')], []))
        [view] = [view for view in review.effective_view(again).values() if view.code == '45385']
        self.assertEqual(view.status, 'excluded')  # read time reads the recompute's exclusion

    def test_d259_an_answer_carrying_the_rendered_questions_fingerprint_is_asked_differently_at_both(self):
        encounter, final, proposals = self.finished()
        rendered = self.rendered_fingerprint(final, proposals)
        answer = models.MemberAnswer.objects.create(encounter=encounter, revision=final.revision, assessment=final,
                                                    code=KEY[0], family=KEY[1], fact=KEY[2],
                                                    value=models.MemberAnswer.NOT_DOCUMENTED, answered_by=self.user,
                                                    question=rendered)
        applied, bound, earlier = review.answer_states(final)
        self.assertEqual((applied, bound, [(a.pk, why) for a, why in earlier]),
                         ([], [], [(answer.pk, questions.ASKED_DIFFERENTLY)]))
        [view] = [view for view in review.effective_view(final).values() if view.code == '45385']
        self.assertEqual(view.status, 'needs_clarification')  # read time does not apply it ...
        encounter.refresh_from_db()
        jobs.recompute_after_answers(encounter, self.user)
        _, again = self.recompute(encounter)
        [still] = [p for p in again.proposals.all() if p.code == '45385']
        self.assertEqual((still.bucket, still.status), ('selected', 'needs_clarification'))  # ... nor does assess
        self.assertEqual([(entry['answer'], entry['why']) for entry in again.completeness['member_answers']['earlier']],
                         [(str(answer.pk), 'asked_differently')])


class ClosedReadingTests(DoorBindingCase):
    """answer_states' second reading (_closed_pairs: a question the assessment closed with a member's answer that no
    longer stands) binds a stored item by its stored fingerprint (bound_fingerprints, D259). The closed question is
    planted as an ANSWERED Clarification of the final assessment - the record v1's renderer left for an answer the
    engine read, which review._close_answered writes - so the reading itself is exercised."""

    def test_d259_a_superseding_answer_binds_to_the_closed_item_by_its_stored_fingerprint(self):
        encounter, final, proposals = self.finished()
        held = self.held(proposals)
        stored = held.support['question']
        rendered = self.rendered_fingerprint(final, proposals)
        first = models.MemberAnswer.objects.create(encounter=encounter, revision=final.revision, assessment=final,
                                                   code=KEY[0], family=KEY[1], fact=KEY[2],
                                                   value=models.MemberAnswer.NOT_DOCUMENTED, answered_by=self.user,
                                                   question=stored)
        [row] = held.clarifications.filter(state=models.Clarification.OPEN)
        row.state, row.answer = models.Clarification.ANSWERED, first
        row.save(update_fields=['state', 'answer'])
        models.MemberAnswerRevocation.objects.create(answer=first, revoked_by=self.user,
                                                     reason=models.MemberAnswerRevocation.SUPERSEDED)
        # the stored fingerprint supersedes the closed question; the rendered question's does not, and stays the
        # earlier answer the first reading made it (no open question asks its key)
        for question, expected in ((stored, 'bound'), (rendered, questions.NO_LONGER_ASKED)):
            with self.subTest(question=question[:12]):
                later = models.MemberAnswer.objects.create(
                    encounter=encounter, revision=final.revision, assessment=final, code=KEY[0], family=KEY[1],
                    fact=KEY[2], value=models.MemberAnswer.CANNOT_CONFIRM, answered_by=self.user, question=question)
                applied, bound, earlier = review.answer_states(final)
                self.assertEqual(applied, [])
                if expected == 'bound':
                    self.assertEqual(([a.pk for a in bound], earlier), ([later.pk], []))
                else:
                    self.assertEqual((bound, [(a.pk, why) for a, why in earlier]), ([], [(later.pk, expected)]))
                models.MemberAnswerRevocation.objects.create(answer=later, revoked_by=self.user,
                                                             reason=models.MemberAnswerRevocation.SUPERSEDED)


def proposal(code, *, position, question='q' * 64, fact='extent', family='gi.colonoscopy', bucket='selected',
             item=True):
    support = {'question': question, 'item': {'message': fact, 'fact': fact, 'kind': 'question'} if item else None}
    return SimpleNamespace(code=code, family=family, position=position, bucket=bucket, support=support)


def pair(code, fact, family='gi.colonoscopy', question='Q?'):
    return (questions.member_key(code, family, fact), questions.instance('proposal', family, fact, code, question, 'R.'))


class StoredQuestionsTests(SimpleTestCase):
    V2 = SimpleNamespace(engine_version=interpretation.ENGINE_VERSION_V2)

    def test_d259_an_events_2_proposals_stored_item_is_read_by_its_code_family_and_fact(self):
        rows = [proposal('45385', position=1, question='a' * 64), proposal('45378', position=0, question='b' * 64,
                                                                           fact='base_included')]
        self.assertEqual(review.stored_questions(self.V2, rows),
                         {('45385', 'gi.colonoscopy', 'extent'): 'a' * 64,
                          ('45378', 'gi.colonoscopy', 'base_included'): 'b' * 64})

    def test_d259_the_first_in_stored_order_binds_a_key_two_proposals_carry(self):
        rows = [proposal('45385', position=3, question='c' * 64), proposal('45385', position=1, question='d' * 64)]
        self.assertEqual(review.stored_questions(self.V2, rows), {KEY: 'd' * 64})  # engine/assess: the first's question

    def test_d259_a_proposal_with_no_stored_item_names_nothing(self):
        rows = [proposal('45385', position=0, question=''), proposal('45386', position=1, item=False),
                proposal('45387', position=2, bucket='alternative'),
                proposal('45388', position=3, question=None),
                SimpleNamespace(code='45389', family='gi.colonoscopy', position=4, bucket='selected', support=None),
                proposal('45390', position=5, fact='')]
        self.assertEqual(review.stored_questions(self.V2, rows), {})

    def test_d259_only_a_key_a_question_asks_is_bound_and_by_its_stored_fingerprint(self):
        rows = [proposal('45385', position=0, question='e' * 64), proposal('45378', position=1, question='f' * 64,
                                                                           fact='base_included')]
        pairs = [pair('45385', 'extent'), pair('45385', 'performed_status'), pair('', 'extent', 'gi.egd')]
        grouped = questions.group(pairs)
        self.assertEqual(review.bound_fingerprints(self.V2, rows, pairs),
                         {KEY: 'e' * 64, ('45385', 'gi.colonoscopy', 'performed_status'):
                          grouped[('45385', 'gi.colonoscopy', 'performed_status')],
                          ('', 'gi.egd', 'extent'): grouped[('', 'gi.egd', 'extent')]})
        self.assertNotIn(('45378', 'gi.colonoscopy', 'base_included'), review.bound_fingerprints(self.V2, rows, pairs))

    def test_d259_v1s_binding_and_the_legacy_engines_are_unchanged(self):
        rows = [proposal('45385', position=0, question='g' * 64)]
        pairs = [pair('45385', 'extent'), pair('', 'extent', 'gi.egd')]
        for version in (interpretation.ENGINE_VERSION, 'cpt-studio-validation@10', None):
            with self.subTest(version=version):
                assessment = SimpleNamespace(engine_version=version)
                self.assertEqual(review.stored_questions(assessment, rows), {})
                self.assertEqual(review.bound_fingerprints(assessment, rows, pairs), questions.group(pairs))


# --- DECISIONS D270 (repair round w9r, step 5b): assess, read time and the customer's account agree on answers ---------

NO_LONGER_ASKED_TEXT = answers.EARLIER_WHY[questions.NO_LONGER_ASKED]


class AppliedAnswerTests(DoorBindingCase):
    """D270, refute-5b-r1 P1 (TRIAGE G1-01, option (b)): TWO_PROCEDURES v2, "Not documented" saved for 45385's extent
    through the details door, then the AGAIN recompute it queued. The recompute excludes 45385 by that answer and records
    it in the proposal's support['answered'] (the design v2 renderer writes no clarification for an excluded code), so
    that record is what says the assessment applied it: review.answer_states counts it applied, the details panel keeps
    the answered row with the answer in effect (withdrawable), and the customer's earlier answers never list it as "no
    longer asked, so this answer is not applied" beside the code it excluded. Withdrawing it still re-queues an AGAIN
    that holds 45385 again; a changed answer on the closed row binds to that row's question (never "no longer asked")
    until its own recompute applies it."""

    def answered(self):
        """(encounter, the AGAIN assessment, the door-saved answer) after "Not documented" on 45385's extent row."""
        encounter, final, _ = self.finished()
        [row] = [item for item in answers.details_needed(encounter, final) if '45385' in item['affects']]
        saved = answers.save_details(encounter, self.user, [{'id': row['id'], 'fact': row['fact'],
                                                             'value': models.MemberAnswer.NOT_DOCUMENTED}])
        [answer_id] = saved['answer_ids']
        _, again = self.recompute(encounter)
        return encounter, again, models.MemberAnswer.objects.get(pk=answer_id)

    def payload(self, encounter):
        from studio import customer_api

        encounter.refresh_from_db()
        return customer_api.encounter_json(encounter, models.Membership.objects.get(workspace=self.ws, user=self.user))

    def test_d270_an_answer_a_design_v2_proposal_records_is_applied_and_shown_in_effect(self):
        encounter, again, answer = self.answered()
        [excluded] = [p for p in again.proposals.all() if p.code == '45385']
        self.assertEqual((excluded.bucket, excluded.support['answered']['answers']), ('excluded', [str(answer.pk)]))
        self.assertFalse(again.clarifications.filter(proposal=excluded).exists())  # no clarification row records it
        self.assertEqual([(p.code, fact, sorted(ids)) for p, fact, ids in review.answered_items(again)],
                         [('45385', 'extent', [str(answer.pk)])])
        # read time: the answer the assessment applied is applied - never an earlier answer
        applied, bound, earlier = review.answer_states(again)
        self.assertEqual(([a.pk for a in applied], bound, earlier), ([answer.pk], [], []))
        self.assertEqual(answers.earlier_answers(encounter, again), [])
        # the details panel keeps the answered row, the answer in effect on it
        [row] = [item for item in answers.details_needed(encounter, again) if '45385' in item['affects']]
        self.assertEqual((row['fact'], row['saved']['answer_id'], row['saved']['value']),
                         ('extent', str(answer.pk), models.MemberAnswer.NOT_DOCUMENTED))
        # the customer's account: 45385 excluded, the answer in effect on its row, and no "no longer asked" anywhere
        payload = self.payload(encounter)
        self.assertEqual(payload['earlier_answers'], [])
        self.assertEqual([(item['fact'], item['affects'], (item['saved'] or {}).get('answer_id'))
                          for item in payload['details_needed']], [('extent', ['45385'], str(answer.pk))])
        self.assertEqual({code['code']: code['status'] for code in payload['codes'] + payload['other_codes']
                          if code.get('code') == '45385'}, {'45385': 'excluded'})
        self.assertNotIn(NO_LONGER_ASKED_TEXT, json.dumps(payload))

    def test_d270_withdrawing_the_applied_answer_requeues_an_again_that_holds_45385_again(self):
        encounter, again, answer = self.answered()
        revocation = answers.revoke_answer(encounter, self.user, answer.pk)
        self.assertEqual(revocation.reason, models.MemberAnswerRevocation.WITHDRAWN)
        # DECISIONS D290, G4-05 (build list B27; refute-5b-r1 R1's mutant V8): between the withdrawal and its recompute
        # the AGAIN is live and the stored exclusion stands, as the overlay reads it - so no 45385 row is asked (V8 gave
        # the withdrawn answer's row back, to be answered by key alone) and no earlier answer is listed
        self.assertTrue(Job.objects.filter(encounter=encounter, kind=Job.ASSESS, state=Job.QUEUED).exists())
        encounter.refresh_from_db()
        self.assertEqual(encounter.current_assessment_id, again.pk)
        self.assertEqual([item for item in answers.details_needed(encounter, again) if '45385' in item['affects']], [])
        self.assertEqual(answers.earlier_answers(encounter, again), [])
        _, after = self.recompute(encounter)
        self.assertNotEqual(after.pk, again.pk)
        [held] = [p for p in after.proposals.all() if p.code == '45385']
        self.assertEqual((held.bucket, held.status), ('selected', 'needs_clarification'))
        self.assertEqual(review.answer_states(after), ([], [], []))
        [row] = [item for item in answers.details_needed(encounter, after) if '45385' in item['affects']]
        self.assertEqual((row['fact'], row['saved']), ('extent', None))  # asked again, nothing saved
        self.assertEqual(answers.earlier_answers(encounter, after), [])
        self.assertEqual(self.payload(encounter)['earlier_answers'], [])

    def test_d270_a_changed_answer_on_the_closed_row_binds_to_its_question_until_its_recompute(self):
        encounter, again, first = self.answered()
        [excluded] = [p for p in again.proposals.all() if p.code == '45385']
        [row] = [item for item in answers.details_needed(encounter, again) if '45385' in item['affects']]
        saved = answers.save_details(encounter, self.user, [{'id': row['id'], 'fact': row['fact'],
                                                             'value': models.MemberAnswer.CANNOT_CONFIRM}])
        [answer_id] = saved['answer_ids']
        later = models.MemberAnswer.objects.get(pk=answer_id)
        self.assertEqual(later.question, excluded.support['question'])  # the closed row's question, D259's fingerprint
        self.assertTrue(models.MemberAnswerRevocation.objects.filter(answer=first).exists())
        # until its recompute has run, read time binds it to the question the assessment closed: in effect on that row,
        # never "no longer asked" (the stored exclusion stands, as the overlay reads it)
        applied, bound, earlier = review.answer_states(again)
        self.assertEqual((applied, [a.pk for a in bound], earlier), ([], [later.pk], []))
        self.assertEqual(answers.earlier_answers(encounter, again), [])
        [row] = [item for item in answers.details_needed(encounter, again) if '45385' in item['affects']]
        self.assertEqual((row['saved']['answer_id'], row['saved']['value']),
                         (str(later.pk), models.MemberAnswer.CANNOT_CONFIRM))
        self.assertNotIn(NO_LONGER_ASKED_TEXT, json.dumps(self.payload(encounter)))
        _, after = self.recompute(encounter)
        [excluded] = [p for p in after.proposals.all() if p.code == '45385']
        self.assertEqual((excluded.bucket, excluded.support['answered']['answers'],
                          excluded.support['answered']['value']),
                         ('excluded', [str(later.pk)], models.MemberAnswer.CANNOT_CONFIRM))
        self.assertEqual([a.pk for a in review.answer_states(after)[0]], [later.pk])


class AnsweredItemsTests(SimpleTestCase):
    """review.answered_items over plain records: only a design v2 assessment's proposals that engine/assess excluded by a
    member's answer (questions.answered_away: a marker naming a fact and an unavailable value), in stored order; [] for
    v1 and the legacy engine, whose record is their clarification rows."""

    def test_d270_only_a_v2_proposal_engine_assess_excluded_by_an_answer_names_its_answers(self):
        def marked(code, position, **marker):
            return SimpleNamespace(code=code, family='gi.colonoscopy', position=position, bucket='excluded',
                                   support={'answered': marker} if marker else {})

        rows = [marked('45385', 2, fact='extent', value='not_documented', answers=['a2', 'a3']),
                marked('45380', 1, fact='target', value='cannot_confirm', answers=['a1']),
                marked('45378', 0),
                marked('45384', 3, fact='', value='not_documented', answers=['a4']),
                marked('45386', 4, fact='extent', value='confirmed', answers=['a5'])]
        v2 = SimpleNamespace(engine_version=interpretation.ENGINE_VERSION_V2)
        self.assertEqual([(p.code, fact, sorted(ids)) for p, fact, ids in review.answered_items(v2, rows)],
                         [('45380', 'target', ['a1']), ('45385', 'extent', ['a2', 'a3'])])
        for version in (interpretation.ENGINE_VERSION, 'cpt-studio-validation@10', None):
            with self.subTest(version=version):
                self.assertEqual(review.answered_items(SimpleNamespace(engine_version=version), rows), [])


# --- D270, refute-5b-r1 P3 (TRIAGE G2-11, option (a)): D259 extended to service questions -----------------------------

EGD = 'EGD: the gastroscope was inserted.'
COLON = 'Colonoscopy: the colonoscope was advanced to the cecum.'
SERVICE_DOC = (v2_documents.HEAD                                           # S1
               + 'Date of service: 11/09/2026.\n'                          # S2
               + v2_documents.ENDOSCOPIST + '\n'                           # S3
               + EGD + '\n'                                                # S4
               + COLON + '\n')                                             # S5
SERVICE_KEY = ('', 'gi.egd', 'extent')


def service_doc_answer():
    """SERVICE_DOC's pass-1 answer: an EGD X1 whose reach is not stated (its examination E1) and a colonoscopy X2 to the
    cecum (E2). Read by the engine with 45378 selected: 45378 READY, and one service question - the EGD's extent, which
    no code asks (D125) - '1 open question' (refute-5b-r1 P3's input, the w8r builder's probe note)."""
    from tests.v2.test_settle import answer, event, fact, frame, session, src

    D = v2_documents
    return answer(
        sections=[D._opening('S3', 'S2', 'S1'), D._labelled('N1', 'S4', 'EGD:', 'procedure', 'S3', 'S2'),
                  D._labelled('N2', 'S5', 'Colonoscopy:', 'procedure', 'S3', 'S2')],
        people=D._people('S3', 'Endoscopist'), clinician=[fact('P1', frame(['S3'], D.NAME))],
        sessions=[session('X1', fact('egd', src(['S4'], 'gastroscope')), examination=[fact('E1', src(['S4']))]),
                  session('X2', fact('colonoscopy', src(['S5'], 'colonoscope')), examination=[fact('E2', src(['S5']))],
                          reached=[fact('cecum', src(['S5'], 'advanced to the cecum'))])],
        events=[event('E1', ['S4'], 'gastroscope', 'was inserted', 'examination', session=[fact('X1', src(['S4']))]),
                event('E2', ['S5'], 'colonoscope', 'was advanced', 'examination', session=[fact('X2', src(['S5']))])],
        when=D._when('S2', '11/09/2026', '2026-11-09'))


def open_question_reasons(completeness):
    return [reason for reason in (completeness or {}).get('reasons') or () if 'open question' in reason]


class ServiceQuestionCase(PipelineCase):
    def setUp(self):
        super().setUp()
        self.interpreter.answers[SERVICE_DOC] = service_doc_answer
        self.provider = FakeProvider([('45378', COLON)])

    def finished(self):
        encounter, _ = self.upload(SERVICE_DOC)
        done = self.drain()
        self.assertTrue(all(job.state == Job.SUCCEEDED for job in done), [(job.kind, job.error) for job in done])
        encounter.refresh_from_db()
        final = encounter.current_assessment
        self.assertEqual(final.engine_version, interpretation.ENGINE_VERSION_V3)
        self.assertEqual([(p.code, p.bucket, p.status) for p in final.proposals.all()], [('45378', 'selected', 'ready')])
        return encounter, final

    def rendered_fingerprint(self, assessment):
        """The service question's fingerprint as questions.group gives it over the rendered row (cpt-studio-question@1) -
        what the details door recorded before D270."""
        return questions.group(review.question_pairs(assessment, list(assessment.proposals.all()), {}))[SERVICE_KEY]

    def recompute(self, encounter):
        [job] = self.drain()
        self.assertEqual((job.kind, job.state, job.result['mode']), ('assess', Job.SUCCEEDED, 'again'))
        encounter.refresh_from_db()
        return encounter.current_assessment

    def service_row(self, encounter, assessment):
        [row] = [item for item in answers.details_needed(encounter, assessment)
                 if not item['affects'] and item['fact'] == 'extent']
        return row


class ServiceQuestionTests(ServiceQuestionCase):
    """D270, refute-5b-r1 P3: the renderer records each service question's engine fingerprint (engine/assess
    .service_fingerprint) in completeness['service_questions'], where read time reads it; the details door
    (answers.save_details through review's question pairs) records a member's answer with it and read time binds by it,
    as engine/assess._close_services does - one fingerprint. P3's input (an EGD whose reach is not stated beside a
    colonoscopy to the cecum, 45378 selected, "Not documented" on the service row, the AGAIN): the stored record and
    read time agree that the question is answered and closed."""

    def test_d270_the_renderer_records_each_service_questions_engine_fingerprint(self):
        encounter, final = self.finished()
        [recorded] = final.completeness[review.SERVICE_QUESTIONS]
        self.assertEqual((recorded['family'], recorded['fact'], len(recorded['question']), recorded['closed']),
                         ('gi.egd', 'extent', 64, []))
        self.assertNotEqual(recorded['question'], self.rendered_fingerprint(final))  # @2 over facts, never @1's text
        self.assertEqual(review.stored_service_questions(final), {SERVICE_KEY: recorded['question']})
        self.assertEqual(review.asked_fingerprints(final), {SERVICE_KEY: recorded['question']})  # what the door records
        [row] = final.clarifications.filter(proposal__isnull=True, scope='service')
        self.assertEqual((row.family, row.fact, row.state), ('gi.egd', 'extent', models.Clarification.OPEN))
        self.assertEqual(open_question_reasons(final.completeness), ['1 open question'])

    def test_d270_a_service_answer_saved_through_the_door_is_closed_by_one_fingerprint_at_read_time_and_assess(self):
        encounter, final = self.finished()
        stored = final.completeness[review.SERVICE_QUESTIONS][0]['question']
        row = self.service_row(encounter, final)
        saved = answers.save_details(encounter, self.user, [{'id': row['id'], 'fact': row['fact'],
                                                             'value': models.MemberAnswer.NOT_DOCUMENTED}])
        [answer_id] = saved['answer_ids']
        answer = models.MemberAnswer.objects.get(pk=answer_id)
        self.assertEqual((answer.code, answer.family, answer.fact, answer.question), (*SERVICE_KEY, stored))
        # read time, until the recompute runs: bound by that fingerprint, the service question closed
        applied, bound, earlier = review.answer_states(final)
        self.assertEqual((applied, [a.pk for a in bound], earlier), ([], [answer.pk], []))
        self.assertEqual([q for q in review.open_questions_of(final) if q['scope'] == 'service'], [])
        # the recompute binds it by the same fingerprint: the service question closed, nothing asked differently
        again = self.recompute(encounter)
        record = again.completeness['member_answers']
        self.assertEqual(([(entry['answer'], entry['scope'], entry['family'], entry['fact']) for entry in record['applied']],
                          record['earlier']), ([(str(answer.pk), 'service', 'gi.egd', 'extent')], []))
        self.assertEqual(again.completeness[review.SERVICE_QUESTIONS],
                         [{'family': 'gi.egd', 'fact': 'extent', 'question': stored, 'closed': [str(answer.pk)]}])
        self.assertEqual(open_question_reasons(again.completeness), [])  # the stored record: answered and closed
        [closed] = again.clarifications.filter(proposal__isnull=True, scope='service')
        self.assertEqual((closed.state, closed.answer_id), (models.Clarification.ANSWERED, answer.pk))
        # read time over the recompute agrees: applied, no open question, the row's answer in effect
        self.assertEqual(review.answer_states(again), ([answer], [], []))
        self.assertEqual(review.open_questions_of(again), [])
        self.assertEqual(open_question_reasons(review.coding_completeness(encounter)), [])
        self.assertEqual((self.service_row(encounter, again)['saved'] or {}).get('answer_id'), str(answer.pk))
        from studio import customer_api

        encounter.refresh_from_db()
        payload = customer_api.encounter_json(encounter,
                                              models.Membership.objects.get(workspace=self.ws, user=self.user))
        self.assertEqual(payload['earlier_answers'], [])
        self.assertEqual([(item['fact'], item['affects'], (item['saved'] or {}).get('answer_id'))
                          for item in payload['details_needed']], [('extent', [], str(answer.pk))])
        self.assertNotIn(NO_LONGER_ASKED_TEXT, json.dumps(payload))

    def test_d270_an_answer_carrying_the_rendered_service_questions_fingerprint_is_asked_differently_at_both(self):
        encounter, final = self.finished()
        rendered = self.rendered_fingerprint(final)
        answer = models.MemberAnswer.objects.create(encounter=encounter, revision=final.revision, assessment=final,
                                                    code='', family='gi.egd', fact='extent',
                                                    value=models.MemberAnswer.NOT_DOCUMENTED, answered_by=self.user,
                                                    question=rendered)
        applied, bound, earlier = review.answer_states(final)
        self.assertEqual((applied, bound, [(a.pk, why) for a, why in earlier]),
                         ([], [], [(answer.pk, questions.ASKED_DIFFERENTLY)]))
        self.assertEqual([q['fact'] for q in review.open_questions_of(final) if q['scope'] == 'service'], ['extent'])
        encounter.refresh_from_db()
        jobs.recompute_after_answers(encounter, self.user)
        again = self.recompute(encounter)
        self.assertEqual([(entry['answer'], entry['why']) for entry in again.completeness['member_answers']['earlier']],
                         [(str(answer.pk), 'asked_differently')])
        self.assertEqual(open_question_reasons(again.completeness), ['1 open question'])
        self.assertEqual([q['fact'] for q in review.open_questions_of(again) if q['scope'] == 'service'], ['extent'])


class StoredServiceQuestionsTests(SimpleTestCase):
    """review.stored_service_questions and bound_fingerprints over plain records."""

    V2 = interpretation.ENGINE_VERSION_V2

    def assessment(self, recorded, version=V2):
        return SimpleNamespace(engine_version=version, completeness={review.SERVICE_QUESTIONS: recorded})

    def test_d270_each_recorded_service_question_is_read_by_its_family_and_fact_the_first_in_stored_order(self):
        recorded = [{'family': 'gi.egd', 'fact': 'extent', 'question': 'a' * 64, 'closed': []},
                    {'family': 'gi.colonoscopy', 'fact': 'performed_status', 'question': 'b' * 64, 'closed': ['x']},
                    {'family': 'gi.egd', 'fact': 'extent', 'question': 'c' * 64, 'closed': []},
                    {'family': '', 'fact': 'procedure', 'question': 'd' * 64, 'closed': []}]
        self.assertEqual(review.stored_service_questions(self.assessment(recorded)),
                         {('', 'gi.egd', 'extent'): 'a' * 64, ('', 'gi.colonoscopy', 'performed_status'): 'b' * 64,
                          ('', '', 'procedure'): 'd' * 64})

    def test_d270_an_entry_that_names_no_family_fact_and_fingerprint_names_nothing(self):
        recorded = [{'family': 'gi.egd', 'fact': '', 'question': 'a' * 64}, {'family': 'gi.egd', 'fact': 'extent'},
                    {'family': None, 'fact': 'extent', 'question': 'b' * 64}, ['gi.egd', 'extent', 'c' * 64],
                    {'family': 'gi.egd', 'fact': 'extent', 'question': ''}, 'extent']
        self.assertEqual(review.stored_service_questions(self.assessment(recorded)), {})
        for completeness in (None, {}, {review.SERVICE_QUESTIONS: None}, {review.SERVICE_QUESTIONS: {'a': 1}}):
            with self.subTest(completeness=completeness):
                assessment = SimpleNamespace(engine_version=self.V2, completeness=completeness)
                self.assertEqual(review.stored_service_questions(assessment), {})

    def test_d270_v1s_and_the_legacy_engines_service_binding_is_unchanged(self):
        recorded = [{'family': 'gi.egd', 'fact': 'extent', 'question': 'e' * 64, 'closed': []}]
        pairs = [pair('', 'extent', 'gi.egd'), pair('45385', 'extent')]
        for version in (interpretation.ENGINE_VERSION, 'cpt-studio-validation@10', None):
            with self.subTest(version=version):
                assessment = self.assessment(recorded, version)
                self.assertEqual(review.stored_service_questions(assessment), {})
                self.assertEqual(review.bound_fingerprints(assessment, [], pairs), questions.group(pairs))

    def test_d270_a_service_key_binds_by_its_recorded_fingerprint_and_a_proposal_key_by_its_stored_item(self):
        recorded = [{'family': 'gi.egd', 'fact': 'extent', 'question': 'f' * 64, 'closed': []}]
        rows = [proposal('45385', position=0, question='g' * 64)]
        pairs = [pair('', 'extent', 'gi.egd'), pair('45385', 'extent'), pair('', 'extent', 'gi.colonoscopy')]
        grouped = questions.group(pairs)
        self.assertEqual(review.bound_fingerprints(self.assessment(recorded), rows, pairs),
                         {('', 'gi.egd', 'extent'): 'f' * 64, KEY: 'g' * 64,
                          ('', 'gi.colonoscopy', 'extent'): grouped[('', 'gi.colonoscopy', 'extent')]})
        # a recorded question no pair asks binds nothing
        self.assertNotIn(('', 'gi.egd', 'extent'), review.bound_fingerprints(self.assessment(recorded), rows, pairs[1:]))


# --- DECISIONS D283 (build list B15, B17, B19): the review half of one implementation of member answers --------------

BALLOON = 'The distal esophagus was dilated with a balloon.'  # test_assess.one_dilation: one balloon dilation
DILATED = 'The distal esophagus was dilated.'  # test_assess.egd_dilation: a dilation whose device is not stated


def dilation_document(sentence: str) -> str:
    """An EGD note (fictional endoscopist, no real patient): the gastroscope advanced to the second portion of the
    duodenum, then one dilation of the distal esophagus told by ``sentence``."""
    return (v2_documents.HEAD                                  # S1
            + 'Date of service: 11/09/2026.\n'                 # S2
            + v2_documents.ENDOSCOPIST + '\n'                  # S3
            + v2_documents.G1 + '\n'                           # S4
            + sentence + '\n')                                 # S5


def dilation_answer(device: bool):
    """Pass 1's answer to dilation_document: the EGD X1 (its examination E1) and the dilation E2 of the distal esophagus,
    its device the balloon S5 states (``device``) or none (test_assess.one_dilation and egd_dilation, read through the
    pipeline)."""
    D = v2_documents
    technique = {'technique__device': [fact('balloon', src(['S5'], 'balloon'))]} if device else {}

    def build() -> dict:
        return pass_one(
            sections=[D._opening('S3', 'S2', 'S1'), D._labelled('N1', 'S4', 'EGD:', 'procedure', 'S3', 'S2')],
            people=D._people('S3', 'Endoscopist'),
            clinician=[fact('P1', frame(['S3'], D.NAME))],
            sessions=[session('X1', fact('egd', src(['S4'], 'gastroscope')), examination=[fact('E1', src(['S4']))],
                              reached=[fact('second_portion_duodenum',
                                            src(['S4'], 'advanced to the second portion of the duodenum'))])],
            events=[event('E1', ['S4'], 'gastroscope', 'was advanced', 'examination',
                          session=[fact('X1', src(['S4']))]),
                    event('E2', ['S5'], 'dilated', 'was dilated', 'dilation', session=[fact('X1', src(['S5']))],
                          target__places=[fact('distal_esophagus', src(['S5'], 'distal esophagus'))], **technique)],
            when=D._when('S2', '11/09/2026', '2026-11-09'))
    return build


class DilationCase(PipelineCase):
    """A dilation document through design v2's pipeline (pass 1 written by hand, pass 2 the faithful oracle), the
    proposal provider selecting ``CODES`` on the dilation's sentence."""
    SENTENCE, DEVICE, CODES = BALLOON, True, ('43249', '43233')

    def setUp(self):
        super().setUp()
        self.document = dilation_document(self.SENTENCE)
        self.interpreter.answers[self.document] = dilation_answer(self.DEVICE)
        self.provider = FakeProvider([(code, self.SENTENCE) for code in self.CODES])

    def finished(self):
        """(encounter, final assessment, {code: proposal}), the pipeline drained."""
        encounter, _ = self.upload(self.document)
        done = self.drain()
        self.assertTrue(all(job.state == Job.SUCCEEDED for job in done), [(job.kind, job.error) for job in done])
        encounter.refresh_from_db()
        final = encounter.current_assessment
        self.assertEqual(final.engine_version, interpretation.ENGINE_VERSION_V3)
        return encounter, final, {p.code: p for p in final.proposals.all()}

    def membership(self):
        return models.Membership.objects.get(workspace=self.ws, user=self.user)

    def decide(self, encounter, proposal, action):
        return review.record_decision(encounter=models.Encounter.objects.get(pk=encounter.pk), proposal=proposal,
                                      action=action, user=self.user, membership=self.membership(),
                                      note='Synthetic decision.',
                                      acknowledgement=review.ACKNOWLEDGEMENTS.get(self.user.actor_kind, ''))

    def view_of(self, assessment, code):
        [view] = [view for view in review.effective_view(assessment).values() if view.code == code]
        return view

    def recompute(self, encounter):
        [job] = self.drain()
        self.assertEqual((job.kind, job.state, job.result['mode']), ('assess', Job.SUCCEEDED, 'again'))
        encounter.refresh_from_db()
        return encounter.current_assessment


class CompetingAnswerTests(DilationCase):
    """DECISIONS D283, G1-01 option (c) (the integration's S1; build list B15): one balloon dilation proposed as 43249 and
    43233, each held by the competition alone. An answer to 43233's competing question - recorded before the question
    stopped taking answers (studio/answers.py refuses one since L4-6), so written here as such a record - binds nothing
    at read time, as engine/assess binds nothing to it: review.answer_states binds none and lists it not_applied, the
    review overlay reads every code as stored (both held, no detail unavailable), and the reviewer's rejection of 43233
    - what the competing hold's own sentence asks for (D270 DQ-3) - releases 43249. As asked (the item's stored
    fingerprint) and with no fingerprint (the earlier form, bound by key); "Not documented" and "Cannot confirm"."""

    def test_b15_an_answer_to_the_competing_question_binds_nothing_and_the_rejection_releases_the_rival(self):
        for value in (models.MemberAnswer.NOT_DOCUMENTED, models.MemberAnswer.CANNOT_CONFIRM):
            for asked in (True, False):
                with self.subTest(value=value, fingerprint='as asked' if asked else 'none'):
                    encounter, final, by = self.finished()
                    for code, rival in (('43249', '43233'), ('43233', '43249')):
                        self.assertEqual((by[code].status, by[code].support['item']['fact'],
                                          by[code].support['competes']), ('needs_clarification', 'competing_codes',
                                                                          [rival]))
                    rival = by['43233']
                    given = models.MemberAnswer.objects.create(
                        encounter=encounter, revision=final.revision, assessment=final, code=rival.code,
                        family=rival.family, fact=overlay.COMPETING_FACT, value=value,
                        question=rival.support['question'] if asked else '', answered_by=self.user)
                    applied, bound, earlier = review.answer_states(final)
                    self.assertEqual((applied, bound, [(item.pk, why) for item, why in earlier]),
                                     ([], [], [(given.pk, AS.Unbound.NOT_APPLIED.value)]))
                    for proposal in by.values():
                        view = self.view_of(final, proposal.code)
                        self.assertEqual((view.status, view.reason, view.answered, view.released, view.recomputed,
                                          view.stale), (proposal.status, '', '', (), (), ()), proposal.code)
                    self.decide(encounter, rival, review.REJECT)
                    view = self.view_of(final, '43249')
                    self.assertEqual((view.status, view.released), ('ready', (overlay.COMPETING_FACT,)))


class NamedRivalTests(DilationCase):
    """DECISIONS D283, G1-04 option (a) (the integration's S4 = O3; build list B17): an EGD dilation whose device is not
    stated, 43249 and 43213 proposed for it (test_assess.egd_dilation). "Cannot confirm" to 43249's technique, saved
    through the details door and read at assess by the recompute it queues, excludes 43249 but leaves it in the
    competition, so 43213's competing question names it. The rejection that question asks for is offered: 43249 allows
    [reject] (detail unavailable, no decision), the rejection is recorded, 43213 then reads ready (its competing hold
    released) and 43249 allows [revoke]. Controls: "Not documented" (43249 out of the competition, no question names
    it) and a code a member's answer leaves detail unavailable that no competing question names allow nothing."""
    SENTENCE, DEVICE, CODES = DILATED, False, ('43249', '43213')

    def answered(self, value, codes=None):
        """(encounter, the AGAIN assessment, {code: proposal}) after ``value`` saved to 43249's technique row."""
        encounter, final, by = self.finished()
        self.assertEqual(by['43249'].support['item']['fact'], 'technique')
        [row] = [item for item in answers.details_needed(encounter, final) if item['affects'] == ['43249']]
        answers.save_details(encounter, self.user, [{'id': row['id'], 'fact': row['fact'], 'value': value}])
        again = self.recompute(encounter)
        return encounter, again, {p.code: p for p in again.proposals.all()}

    def test_b17_the_rival_an_open_competing_question_names_offers_the_rejection_it_asks_for(self):
        encounter, again, by = self.answered(models.MemberAnswer.CANNOT_CONFIRM)
        self.assertEqual((by['43249'].bucket, by['43249'].support['answered']['value']),
                         ('excluded', models.MemberAnswer.CANNOT_CONFIRM))
        self.assertEqual((by['43213'].status, by['43213'].support['item']['fact'], by['43213'].support['competes']),
                         ('needs_clarification', overlay.COMPETING_FACT, ['43249']))
        self.assertEqual(self.view_of(again, '43249').reason, review.DETAIL_UNAVAILABLE)
        self.assertEqual(review.allowed_actions(by['43249'], again, self.membership()), [review.REJECT])
        self.decide(encounter, by['43249'], review.REJECT)
        view = self.view_of(again, '43213')
        self.assertEqual((view.status, view.released), ('ready', (overlay.COMPETING_FACT,)))
        self.assertEqual(review.allowed_actions(by['43249'], again, self.membership()), [review.REVOKE])

    def test_b17_controls_a_code_no_competing_question_names_offers_nothing(self):
        encounter, again, by = self.answered(models.MemberAnswer.NOT_DOCUMENTED)
        self.assertEqual(by['43249'].bucket, 'excluded')
        self.assertEqual((by['43213'].status, by['43213'].support.get('competes') or []), ('ready', []))
        self.assertEqual(review.allowed_actions(by['43249'], again, self.membership()), [])


class NamedRivalAloneTests(NamedRivalTests):
    """B17's second control: 43249 proposed alone for the dilation whose device is not stated - "Cannot confirm" to its
    technique leaves it detail unavailable with no rival, so no competing question names it: it allows nothing."""
    CODES = ('43249',)

    def test_b17_the_rival_an_open_competing_question_names_offers_the_rejection_it_asks_for(self):
        encounter, again, by = self.answered(models.MemberAnswer.CANNOT_CONFIRM)
        self.assertEqual(by['43249'].bucket, 'excluded')
        self.assertEqual(self.view_of(again, '43249').reason, review.DETAIL_UNAVAILABLE)
        self.assertEqual(review.allowed_actions(by['43249'], again, self.membership()), [])

    def test_b17_controls_a_code_no_competing_question_names_offers_nothing(self):
        pass  # the parent's control needs 43213


class NamedRivalThreeWayTests(NamedRivalTests):
    """refute-f6-r1 F6R1-3 (D276: B17 as its class, whatever the size of the competition): the dilation whose device is
    not stated proposed as 43249, 43213 and 43248, all three competing. "Not documented" to 43249's technique takes
    43249 out of the competition (D249): the two left still compete and their open competing question names them
    alone, so 43249 allows nothing - at read time (the recompute it queues not run) and after it. "Cannot confirm"
    leaves 43249 in the competition, named by the open competing question: [reject] at read time and after the
    recompute, the rejection recorded, then [revoke]."""
    CODES = ('43249', '43213', '43248')

    def saved(self, value):
        """(encounter, the assessment read time reads - its recompute queued, not run -, {code: proposal}) after
        ``value`` saved to 43249's technique row through the details door."""
        encounter, final, by = self.finished()
        self.assertEqual({code: sorted(by[code].support.get('competes') or []) for code in self.CODES},
                         {'43249': ['43213', '43248'], '43213': ['43248', '43249'], '43248': ['43213', '43249']})
        [row] = [item for item in answers.details_needed(encounter, final) if item['affects'] == ['43249']]
        answers.save_details(encounter, self.user, [{'id': row['id'], 'fact': row['fact'], 'value': value}])
        return encounter, final, by

    def test_b17_the_rival_an_open_competing_question_names_offers_the_rejection_it_asks_for(self):
        encounter, final, by = self.saved(models.MemberAnswer.CANNOT_CONFIRM)
        view = self.view_of(final, '43249')
        self.assertEqual((view.reason, view.answer), (review.DETAIL_UNAVAILABLE, models.MemberAnswer.CANNOT_CONFIRM))
        self.assertEqual(review.allowed_actions(by['43249'], final, self.membership()), [review.REJECT])
        again = self.recompute(encounter)
        mine = {p.code: p for p in again.proposals.all()}
        self.assertEqual(review.allowed_actions(mine['43249'], again, self.membership()), [review.REJECT])
        self.decide(encounter, mine['43249'], review.REJECT)
        self.assertEqual(review.allowed_actions(mine['43249'], again, self.membership()), [review.REVOKE])

    def test_b17_controls_a_code_no_competing_question_names_offers_nothing(self):
        encounter, final, by = self.saved(models.MemberAnswer.NOT_DOCUMENTED)
        view = self.view_of(final, '43249')
        self.assertEqual((view.reason, view.answer), (review.DETAIL_UNAVAILABLE, models.MemberAnswer.NOT_DOCUMENTED))
        self.assertTrue(any(q.get('fact') == overlay.COMPETING_FACT for q in self.view_of(final, '43213').questions))
        self.assertEqual(review.allowed_actions(by['43249'], final, self.membership()), [])
        again = self.recompute(encounter)
        mine = {p.code: p for p in again.proposals.all()}
        self.assertEqual(review.allowed_actions(mine['43249'], again, self.membership()), [])


class AssessedAnswersTests(SimpleTestCase):
    """DECISIONS D283, G3-17 with RS-4's and C5's correction (build list B19), over records (test_overlay.Case: the
    engine's assessment persisted as the renderer persists it): overlay.assessed_answers names every answer assess read
    that the overlay binds - the competition's overlay-bound "Not documented" (D270 DQ-2) and an overlay-bound answer of
    either value on a primary (G1-03) - and nothing else: not one asked differently, one no longer asked, one to the
    competing question, or a "Cannot confirm" that binds no primary. review._reads_a_withdrawn_answer holds readiness
    (STALE_ANSWER_BLOCKER) while one it names no longer stands, and never for an answer it does not name."""

    @staticmethod
    def case(doc, codes, given):
        from tests.v2 import test_overlay as TO  # imported here: test_overlay imports test_assess

        return TO.Case(doc.build(), *codes, answers=given)

    @staticmethod
    def withdrawn(case, standing):
        """review._reads_a_withdrawn_answer over ``case``'s record, with ``standing`` (answer ids) its standing answers."""
        from unittest import mock

        none = SimpleNamespace(filter=lambda **kw: SimpleNamespace(
            exclude=lambda **kw: SimpleNamespace(exists=lambda: False)))
        assessment = SimpleNamespace(engine_version=interpretation.ENGINE_VERSION_V3, completeness=case.completeness,
                                     clarifications=none, proposals=SimpleNamespace(all=lambda: list(case.rows)))
        with mock.patch.object(review, '_standing', return_value=[SimpleNamespace(pk=pk) for pk in standing]):
            return review._reads_a_withdrawn_answer(assessment)

    def test_b19_the_answers_assess_read_and_the_ones_it_did_not(self):
        doc = TA.office_and_sigmoidoscopy
        prolonged = TA.office_prolonged
        prolonged_codes = (('99215', 1), ('99214', 1), ('99417', 2))
        plain = TA.by_code(TA.run(prolonged().build(), *prolonged_codes, member=TA.ENTERED))
        day = TA.by_code(TA.run(doc().build(), *TA.OFFICE_DAY, member=TA.ENTERED))
        c7 = doc()
        c7.act(3, TA.Kind.EM_PROLONGED, session=TA.X(1))
        c7_codes = (('99215', 1), ('99417', 3), ('45330', 2))
        c7_plain = TA.by_code(TA.run(c7.build(), *c7_codes, member=TA.ENTERED))
        dilation_codes = (('43249', 2), ('43213', 2))
        dilation = TA.by_code(TA.run(TA.egd_dilation().build(), *dilation_codes))
        read, unasked, other = AS.Unbound.OVERLAY_READ, AS.Unbound.NO_LONGER_ASKED, AS.Unbound.ASKED_DIFFERENTLY
        rows = []
        for value in ('not_documented', 'cannot_confirm'):
            rows.append(('G1-03: an answer on the only primary', prolonged(), prolonged_codes,
                         (TA.answer(plain['99215'], value=value, answer_id='a1'),), {'a1'}, {'a1': read}))
        rows += [
            ('D270 DQ-2: the competition\'s "Not documented"', doc(), TA.OFFICE_DAY,
             (TA.answer(day['99214'], answer_id='a1'),), {'a1'}, {'a1': read}),
            ('an unbound "Cannot confirm": no primary, the competition as it stands', doc(), TA.OFFICE_DAY,
             (TA.answer(day['99214'], value='cannot_confirm', answer_id='a1'),), set(), {'a1': read}),
            ('asked differently (an item the engine binds by its fingerprint)', TA.egd_dilation(), dilation_codes,
             (TA.answer(dilation['43249'], question='0' * 64, answer_id='a1'),), set(), {'a1': other}),
            ('no longer asked (C7: 99417\'s item moved to its ADDON row)', c7, c7_codes,
             (TA.answer(c7_plain['99215'], answer_id='a1'), TA.answer(c7_plain['99417'], answer_id='a2')), {'a1'},
             {'a1': read, 'a2': unasked}),
        ]
        for name, built, codes, given, named, whys in rows:
            with self.subTest(name, values=[item.value for item in given]):
                case = self.case(built, codes, given)
                self.assertEqual({entry.answer: entry.why for entry in case.assessment.earlier_answers}, whys)
                self.assertEqual(overlay.assessed_answers(case.completeness, case.rows), frozenset(named))
                every = {item.answer_id for item in given}
                self.assertFalse(self.withdrawn(case, every))  # every answer standing
                for gone in every:
                    self.assertEqual(self.withdrawn(case, every - {gone}), gone in named, gone)

    def test_b19_an_answer_to_the_competing_question_is_never_read(self):
        found = TA.by_code(TA.run(TA.one_dilation().build(), ('43249', 2), ('43233', 2)))
        given = (TA.answer(found['43233'], answer_id='a1', fact=overlay.COMPETING_FACT),)
        case = self.case(TA.one_dilation(), (('43249', 2), ('43233', 2)), given)
        self.assertEqual(overlay.assessed_answers(case.completeness, case.rows), frozenset())
        self.assertFalse(self.withdrawn(case, set()))


OFFICE_VISIT = 'Office visit: established patient seen in the office.'
TOTAL_TIME = 'Total time on the date of the encounter was 74 minutes.'
PROLONGED = 'Prolonged service time beyond the visit was 15 minutes.'
SIGMOIDOSCOPY = 'Flexible sigmoidoscopy: the sigmoidoscope was advanced to the sigmoid colon.'


def office_document(prolonged: bool) -> str:
    """An office note (fictional clinician, no real patient): the visit and its total time, its prolonged time
    (``prolonged``), and a flexible sigmoidoscopy to the sigmoid colon on the same day."""
    return (v2_documents.HEAD                                  # S1
            + 'Date of service: 11/09/2026.\n'                 # S2
            + v2_documents.CLINICIAN + '\n'                    # S3
            + OFFICE_VISIT + '\n'                              # S4
            + TOTAL_TIME + '\n'                                # S5
            + (PROLONGED + '\n' if prolonged else '')          # S6
            + SIGMOIDOSCOPY + '\n')                            # S6 or S7


def office_answer(prolonged: bool):
    """Pass 1's answer to office_document: the office visit X1 (this encounter; the visit E1, its basis the stated total
    time, and its prolonged time E3 when stated) and the flexible sigmoidoscopy X2 to the sigmoid colon (E2) - test_assess's
    office_and_sigmoidoscopy, and with the prolonged time refute-consistency C7's scene, read through the pipeline."""
    D = v2_documents
    sig = 'S7' if prolonged else 'S6'

    def build() -> dict:
        events = [event('E1', ['S4'], 'Office visit', 'seen', 'em_visit', session=[fact('X1', src(['S4']))],
                        visit__basis=[fact('total_time', src(['S5'], '74 minutes', 'placing'))]),
                  event('E2', [sig], 'sigmoidoscope', 'was advanced', 'examination', session=[fact('X2', src([sig]))])]
        if prolonged:
            events.append(event('E3', ['S6'], 'Prolonged service time', 'was 15 minutes', 'em_prolonged',
                                session=[fact('X1', src(['S6']))]))
        return pass_one(
            sections=[D._opening('S3', 'S2', 'S1')],
            people=D._people('S3', 'Clinician'),
            clinician=[fact('P1', frame(['S3'], D.NAME))],
            sessions=[session('X1', fact('office_em', src(['S4'], 'Office')), examination=[fact('E1', src(['S4']))],
                              encounter=[fact('this_encounter', frame(['S2']))]),
                      session('X2', fact('flex_sig', src([sig], 'Flexible sigmoidoscopy')),
                              examination=[fact('E2', src([sig]))],
                              reached=[fact('sigmoid_colon', src([sig], 'advanced to the sigmoid colon'))])],
            events=events,
            when=D._when('S2', '11/09/2026', '2026-11-09'))
    return build


class WithdrawnReadAnswerTests(PipelineCase):
    """DECISIONS D283, G3-17 with RS-4's and C5's correction (build list B19), through the product's doors: an
    assessment that READ a member's overlay-bound answer holds readiness at STALE_ANSWER_BLOCKER once that answer no
    longer stands, until the recompute. (a) A key-bound "Not documented" assess read for the competition (D270 DQ-2:
    99214 beside 99213 on one office visit, a same-day flexible sigmoidoscopy asking each the separately identifiable
    visit); (b) an answer of either value assess read for the ADDON row (G1-03: 99215's separately identifiable visit
    answered, 99417's only primary). Each withdrawn through the door with the recompute it queues stopped: the blocker
    stands; resumed and recomputed: it is gone."""

    VALUES = {'setting': 'office', 'patient_status': 'established'}

    def finished(self, prolonged, codes):
        document = office_document(prolonged)
        self.interpreter.answers[document] = office_answer(prolonged)
        self.provider = FakeProvider(list(codes))
        encounter, _ = self.upload(document, values=self.VALUES)
        done = self.drain()
        self.assertTrue(all(job.state == Job.SUCCEEDED for job in done), [(job.kind, job.error) for job in done])
        encounter.refresh_from_db()
        final = encounter.current_assessment
        self.assertEqual(final.engine_version, interpretation.ENGINE_VERSION_V3)
        return encounter, final

    def fresh(self, encounter):
        return models.Encounter.objects.get(pk=encounter.pk)

    def stale(self, encounter):
        return review.STALE_ANSWER_BLOCKER in review.readiness(self.fresh(encounter))['blockers']

    def read_then_withdrawn(self, encounter, final, code, value):
        """``value`` saved to ``code``'s row through the door, its AGAIN run (assess reads it: overlay.assessed_answers
        names it), then withdrawn with the AGAIN that queues stopped; the blocker checked before and after the
        recompute."""
        [row] = [item for item in answers.details_needed(encounter, final) if code in item['affects']]
        saved = answers.save_details(encounter, self.user, [{'id': row['id'], 'fact': row['fact'], 'value': value}])
        [answer_id] = saved['answer_ids']
        [job] = self.drain()
        self.assertEqual((job.kind, job.state, job.result['mode']), ('assess', Job.SUCCEEDED, 'again'))
        again = self.fresh(encounter).current_assessment
        rows = [overlay.stored_from(p, ()) for p in again.proposals.all()]
        self.assertEqual(overlay.assessed_answers(again.completeness, rows), frozenset({str(answer_id)}))
        self.assertFalse(self.stale(encounter))
        answers.revoke_answer(encounter, self.user, answer_id)
        jobs.stop_encounter(self.fresh(encounter), self.user)
        self.assertEqual(self.fresh(encounter).current_assessment_id, again.pk)  # the recompute has not run
        self.assertTrue(self.stale(encounter))
        jobs.resume(self.fresh(encounter), self.user)
        self.drain()
        self.assertNotEqual(self.fresh(encounter).current_assessment_id, again.pk)
        self.assertFalse(self.stale(encounter))

    def test_b19_a_key_bound_not_documented_assess_read_for_the_competition(self):
        encounter, final = self.finished(False, (('99213', TOTAL_TIME), ('99214', TOTAL_TIME),
                                                 ('45330', SIGMOIDOSCOPY)))
        by = {p.code: p for p in final.proposals.all()}
        self.assertEqual({code: (p.status, (p.support.get('item') or {}).get('fact')) for code, p in by.items()},
                         {'99213': ('needs_clarification', 'separate_em'),
                          '99214': ('needs_clarification', 'separate_em'), '45330': ('ready', None)})
        self.read_then_withdrawn(encounter, final, '99214', models.MemberAnswer.NOT_DOCUMENTED)

    def test_b19_an_answer_of_either_value_assess_read_for_the_addon_row(self):
        for value in (models.MemberAnswer.NOT_DOCUMENTED, models.MemberAnswer.CANNOT_CONFIRM):
            with self.subTest(value=value):
                encounter, final = self.finished(True, (('99215', TOTAL_TIME), ('99417', PROLONGED),
                                                        ('45330', SIGMOIDOSCOPY)))
                by = {p.code: p for p in final.proposals.all()}
                self.assertEqual({code: (p.status, (p.support.get('item') or {}).get('fact'))
                                  for code, p in by.items()},
                                 {'99215': ('needs_clarification', 'separate_em'),
                                  '99417': ('needs_clarification', 'separate_em'), '45330': ('ready', None)})
                self.read_then_withdrawn(encounter, final, '99215', value)
