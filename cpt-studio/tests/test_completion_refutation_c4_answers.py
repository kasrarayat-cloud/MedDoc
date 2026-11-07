"""Refutation of the integrated completion diff, cycle 4 - member answers (2026-11-06; HARNESS.md "Refutation of the
integrated diff, cycle 4", answers 1-3). The engine reads only an answer that carries its question's fingerprint, to a
question no review decision can open or close; every other answer is the review overlay's, read at read time over the
current decisions as the installed release read every answer; and another code's checks read again without an answered
code keep that code's fingerprint. So no answer - an unrelated one, a withdrawal, a corrected value, an answer recorded
before the binding - invalidates a decision nothing shown had moved, and a rejection that closes a base code's
base_included question releases the base code as the installed overlay did. The scenarios are the answers lens's, each
measured on the installed base, the cycle-2 and the cycle-3 heads. Synthetic documents only; nothing is sent."""
from __future__ import annotations

import json
from unittest import mock

from studio import jobs, models, review
from tests.test_cux_r2_details import PipelineCase
from tests.test_pipeline_api import drain
from tests.test_reference import ArchiveMixin

SYN = 'SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\n'
COLON = 'gi.colonoscopy'
HEDGED_BX = 'Gastric biopsies were possibly obtained with cold forceps.'
ADVANCED = 'The colonoscope was advanced to the cecum'
SNARE = 'A 9 mm pedunculated polyp in the sigmoid colon was removed with a hot snare.'
HEDGED_SNARE = 'A 9 mm polyp in the sigmoid colon was possibly removed with a hot snare.'
HEAD = SYN + 'Colonoscopy report (fictional)\nDate of service: 2026-10-14\nPlace of service: Ambulatory surgery center\n'
BOTH = (SYN + 'Upper endoscopy and colonoscopy report (fictional)\nDate of service: 2026-10-14\nPlace of service: '
        'Ambulatory surgery center\nProcedure: Upper endoscopy and colonoscopy\nThe gastroscope was advanced to the '
        'second part of the duodenum. ' + HEDGED_BX + '\nThe colonoscope was advanced to the cecum and the examination '
        'was completed.\n' + SNARE + '\n')
REPORT = (HEAD + 'Procedure: Colonoscopy\nThe colonoscope was advanced to the cecum and the examination was completed.\n'
          + SNARE + '\n')
HEDGED = (HEAD + 'Procedure: Colonoscopy\nThe colonoscope was advanced to the cecum and the examination was completed.\n'
          + HEDGED_SNARE + '\n')


def earlier_form(encounter, code, fact, user, value='not_documented'):
    """An answer as the installed release recorded it: no question fingerprint."""
    return models.MemberAnswer.objects.create(encounter=encounter, revision=encounter.current_revision,
                                              assessment=encounter.current_assessment, fact=fact, family=COLON,
                                              code=code, value=value, answered_by=user)


class _Case(ArchiveMixin, PipelineCase):
    selections = [('45378', ADVANCED), ('45385', SNARE)]

    def setUp(self):
        super().setUp()
        self.load_pfs()
        self.load_mue()
        self.provider.selections = list(self.selections)

    def decide(self, encounter_id, code, action):
        a = self.encounter(encounter_id).current_assessment
        body = {'proposal_id': str(a.proposals.get(code=code).pk), 'action': action, 'note': 'Synthetic reviewer note.'}
        if action == 'approve':
            body['acknowledgement'] = review.ACKNOWLEDGEMENTS[self.reviewer.actor_kind]
        response = self.client.post(f'/api/encounters/{encounter_id}/decisions', content_type='application/json',
                                    data=json.dumps(body))
        drain()
        self.assertEqual(response.status_code, 201, response.content[:300])
        return response

    def reassess(self, encounter_id):
        jobs.reassess_retained(self.encounter(encounter_id), 'c4-synthetic', user=self.reviewer)
        drain()

    def answer(self, encounter_id, fact, code, value):
        (row,) = [r for r in self.doc(encounter_id)['details_needed'] if r['fact'] == fact and code in r['affects']]
        response = self.save(encounter_id, row, value)
        drain()
        self.assertEqual(response.status_code, 201, response.content[:300])

    def invalidations(self, encounter_id):
        return [(i.decision.proposal.code, i.reason)
                for i in models.DecisionInvalidation.objects.filter(decision__encounter_id=encounter_id)]

    def codes(self, encounter_id):
        return {row['code']: (row['status'], row.get('allowed_actions')) for row in self.doc(encounter_id)['codes']}


class NoAnswerMovesAnotherCodesDecisionTests(_Case):
    """answers 1: the approval or rejection of another code survives every answer that changes nothing it shows."""
    selections = [('43239', HEDGED_BX), ('45378', ADVANCED), ('45385', SNARE)]

    def test_an_unrelated_answer_after_an_earlier_form_one_keeps_the_approval(self):
        encounter_id = self.upload(BOTH)
        earlier_form(self.encounter(encounter_id), '45378', 'base_included', self.reviewer, value='cannot_confirm')
        self.decide(encounter_id, '45385', 'approve')
        self.reassess(encounter_id)  # the install's reassess phase reads the earlier-form answer as the overlay did
        self.assertEqual(self.invalidations(encounter_id), [])
        self.answer(encounter_id, 'performed_status', '43239', 'not_documented')
        self.assertEqual(self.invalidations(encounter_id), [])
        self.assertEqual(self.doc(encounter_id)['state'], 'reviewed')

    def test_withdrawing_the_unrelated_answer_keeps_the_approval(self):
        encounter_id = self.upload(BOTH)
        earlier_form(self.encounter(encounter_id), '45378', 'base_included', self.reviewer, value='cannot_confirm')
        self.reassess(encounter_id)
        self.answer(encounter_id, 'performed_status', '43239', 'not_documented')
        self.decide(encounter_id, '45385', 'approve')
        answer = models.MemberAnswer.objects.get(encounter_id=encounter_id, code='43239')
        response = self.client.post(f'/api/encounters/{encounter_id}/details/{answer.pk}/revoke')
        drain()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(self.invalidations(encounter_id), [])


class CorrectedValueTests(_Case):

    def test_correcting_an_earlier_form_answers_value_keeps_the_approval(self):
        encounter_id = self.upload(REPORT)
        earlier_form(self.encounter(encounter_id), '45378', 'base_included', self.reviewer, value='cannot_confirm')
        self.reassess(encounter_id)
        self.decide(encounter_id, '45385', 'approve')
        self.answer(encounter_id, 'base_included', '45378', 'not_documented')
        self.assertEqual(self.invalidations(encounter_id), [])
        self.assertEqual(self.doc(encounter_id)['state'], 'reviewed')


class CorrectedValueRejectionTests(_Case):
    selections = [('45378', ADVANCED), ('45385', HEDGED_SNARE)]

    def test_correcting_the_value_keeps_the_rejection_of_the_base(self):
        encounter_id = self.upload(HEDGED)
        earlier_form(self.encounter(encounter_id), '45385', 'performed_status', self.reviewer)
        self.reassess(encounter_id)
        self.decide(encounter_id, '45378', 'reject')
        self.answer(encounter_id, 'performed_status', '45385', 'cannot_confirm')
        self.assertEqual(self.invalidations(encounter_id), [])
        self.assertEqual(self.doc(encounter_id)['state'], 'reviewed')


class RejectionClosesTheBaseQuestionTests(_Case):
    """answers 2: a rejection that closes the base code's base_included question releases it - the answer to that
    question no longer applies, as the installed overlay read it."""
    selections = [('45378', ADVANCED), ('45385', HEDGED_SNARE)]

    def test_a_fingerprinted_answer_then_the_rejection(self):
        encounter_id = self.upload(HEDGED)
        self.answer(encounter_id, 'base_included', '45378', 'cannot_confirm')
        self.assertEqual(self.codes(encounter_id)['45378'][0], 'excluded')
        self.decide(encounter_id, '45385', 'reject')
        self.assertEqual(self.codes(encounter_id)['45378'], ('ready', ['approve', 'reject']))

    def test_an_earlier_form_answer_reassessed_then_the_rejection(self):
        encounter_id = self.upload(HEDGED)
        earlier_form(self.encounter(encounter_id), '45378', 'base_included', self.reviewer, value='cannot_confirm')
        self.reassess(encounter_id)
        self.assertEqual(self.codes(encounter_id)['45378'][0], 'excluded')
        self.decide(encounter_id, '45385', 'reject')
        self.assertEqual(self.codes(encounter_id)['45378'], ('ready', ['approve', 'reject']))


class StaleCheckTests(_Case):
    """answers 3: where the overlay cannot recompute another code's endoscopic check, it is marked stale."""

    def test_the_base_code_shown_also_selected_is_marked_stale(self):
        patcher = mock.patch('studio.jobs.reference_passages.load_passages', side_effect=RuntimeError('synthetic'))
        patcher.start()
        self.addCleanup(patcher.stop)
        encounter_id = self.upload(REPORT)
        earlier_form(self.encounter(encounter_id), '45378', 'base_included', self.reviewer, value='cannot_confirm')
        self.reassess(encounter_id)
        a = self.encounter(encounter_id).current_assessment
        views = review.effective_view(a)
        snare = a.proposals.get(code='45385')
        self.assertEqual(views[snare.key].status, 'ready')
        self.assertEqual(list(views[snare.key].stale), ['pfs.endoscopic_base'])


class KeyBoundBaseAnswerTests(_Case):
    """The differential round over cycle 4 (answers 1): a base_included or separate_em answer binds by its key, as the
    installed release bound every answer. A review decision that rewords the base code's hidden reason (rejecting the
    biopsy code leaves only the snare holding 45378) never withdraws the answer as "asked differently" beside the same
    visible row, and a re-answer supersedes the earlier one (one standing answer)."""
    selections = [('45378', ADVANCED), ('45380', 'Cold forceps biopsies were obtained from the ascending colon.'),
                  ('45385', SNARE)]
    THREE = (HEAD + 'Procedure: Colonoscopy\nThe colonoscope was advanced to the cecum and the examination was completed.\n'
             'Cold forceps biopsies were obtained from the ascending colon.\n' + SNARE + '\n')

    def test_a_rejection_that_rewords_the_hidden_reason_keeps_the_answer(self):
        encounter_id = self.upload(self.THREE)
        self.answer(encounter_id, 'base_included', '45378', 'not_documented')
        self.assertEqual(self.codes(encounter_id)['45378'][0], 'excluded')
        self.decide(encounter_id, '45380', 'reject')
        doc = self.doc(encounter_id)
        self.assertEqual(self.codes(encounter_id)['45378'][0], 'excluded')
        self.assertEqual(doc['earlier_answers'], [])
        self.assertEqual(doc['state'], 'ready')
        self.answer(encounter_id, 'base_included', '45378', 'cannot_confirm')  # a re-answer supersedes the first
        standing = models.MemberAnswer.objects.filter(encounter_id=encounter_id, code='45378', revocation__isnull=True)
        self.assertEqual([a.value for a in standing], ['cannot_confirm'])
