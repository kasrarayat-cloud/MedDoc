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
from studio.validation import questions
from tests import v2_documents
from tests.test_pipeline_api import FakeProvider
from tests.v2.test_jobs import PipelineCase

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
        self.assertEqual(final.engine_version, interpretation.ENGINE_VERSION_V2)
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
        self.assertEqual(final.engine_version, interpretation.ENGINE_VERSION_V2)
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
