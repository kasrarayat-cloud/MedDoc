"""Refutation of the integrated completion diff, cycle 3: member answers (2026-11-06; HARNESS.md "Refutation of the
integrated diff, cycle 3", answers C3-1 to C3-4). Each test is the answers lens's own scenario, measured on the installed
base, the cycle-1 head and the cycle-2 head before the repair. Synthetic documents only; nothing is sent."""
from __future__ import annotations

import datetime
import json

from django.utils import timezone

from studio import jobs, models, review
from studio.validation import questions
from tests.test_cux_r2_details import PipelineCase
from tests.test_pipeline_api import drain
from tests.test_reference import ArchiveMixin

SYN = 'SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\n'
COLON = 'gi.colonoscopy'
SNARE = 'A 9 mm pedunculated polyp in the sigmoid colon was removed with a hot snare.'
ADVANCED = 'The colonoscope was advanced to the cecum'
REPORT = (SYN + 'Colonoscopy report (fictional)\nDate of service: 2026-10-14\nPlace of service: Ambulatory surgery '
          'center\nProcedure: Colonoscopy\nThe colonoscope was advanced to the cecum and the examination was '
          'completed.\n' + SNARE + '\n')
OFFICE_SNARE = 'A 9 mm polyp in the sigmoid colon was removed with a hot snare.'
OFFICE_COLON = (SYN + 'Office visit and colonoscopy (fictional)\nDate of service: 2026-10-14\nPlace of service: Office\n'
                'Established patient seen for reflux.\nProcedure: Colonoscopy\nThe colonoscope was advanced to the cecum '
                'and the examination was completed.\n' + OFFICE_SNARE + '\n')
FORCEPS = 'A 4 mm polyp in the rectum was removed with cold forceps.'
HEDGED_SNARE = 'A 9 mm polyp in the sigmoid colon was possibly removed with a hot snare.'
HEDGED = (SYN + 'Colonoscopy report (fictional)\nDate of service: 2026-10-14\nPlace of service: Ambulatory surgery '
          'center\nProcedure: Colonoscopy\nThe colonoscope was advanced to the cecum and the examination was '
          'completed.\n' + FORCEPS + '\n' + HEDGED_SNARE + '\n')


def earlier_form(encounter, assessment, code, family, fact, user, value='not_documented'):
    """An answer as the installed release recorded it: no question fingerprint."""
    return models.MemberAnswer.objects.create(encounter=encounter, revision=encounter.current_revision,
                                              assessment=assessment, fact=fact, family=family, code=code, value=value,
                                              answered_by=user)


def asked(doc, fact):
    return [row for row in doc['details_needed'] if row['fact'] == fact]


def undo_reading(since):
    from tests.test_repairs_r1_m import install, run_app_script
    body = install.UNDO_HAZARDS + (
        "import datetime\n"
        "hazards = undo_hazards()\n"
        "written = written_since(datetime.datetime.fromisoformat(P['since']), sorted(hazards))\n"
        "print(ANSWER + json.dumps({'hazards': hazards, 'written': written}))\n")
    answer = run_app_script(body, {'since': since.isoformat()})
    closed = {'hazards': answer['hazards'], 'written_since': answer['written']}
    shown = {pk: [reason for reason in reasons if reason in install.SHOWN_HAZARDS]
             for pk, reasons in answer['hazards'].items()}
    hold, _notes = install.undo_hold([{'problems': [], 'closed': closed, 'acting': {}, 'shown': shown,
                                       'since': since}], same=False)
    return answer['hazards'], hold


class _Case(ArchiveMixin, PipelineCase):
    def setUp(self):
        super().setUp()
        self.load_pfs()
        self.load_mue()

    def decide(self, encounter_id, code, action):
        a = self.encounter(encounter_id).current_assessment
        body = {'proposal_id': str(a.proposals.get(code=code).pk), 'action': action, 'note': 'Synthetic reviewer note.'}
        if action == 'approve':
            body['acknowledgement'] = review.ACKNOWLEDGEMENTS[self.reviewer.actor_kind]
        response = self.client.post(f'/api/encounters/{encounter_id}/decisions', content_type='application/json',
                                    data=json.dumps(body))
        drain()
        return response

    def invalidated(self, encounter_id):
        return [(d.proposal.code, d.action) for d in models.Decision.objects.filter(encounter_id=encounter_id)
                if models.DecisionInvalidation.objects.filter(decision=d).exists()]


class EarlierFormAnswerApprovalTests(_Case):
    """Answers C3-1: an answer recorded before the binding never reopens an approval through a re-assessment."""

    def setUp(self):
        super().setUp()
        self.provider.selections = [('45378', ADVANCED), ('45385', SNARE)]

    def test_the_reassess_phase_keeps_the_approval(self):
        encounter_id = self.upload(REPORT)
        encounter = self.encounter(encounter_id)
        earlier_form(encounter, encounter.current_assessment, '45378', COLON, 'base_included', self.reviewer,
                     value='cannot_confirm')
        self.assertEqual(self.decide(encounter_id, '45385', 'approve').status_code, 201)
        jobs.reassess_retained(self.encounter(encounter_id), 'c3-synthetic', user=self.reviewer)
        drain()
        doc = self.doc(encounter_id)
        self.assertEqual(self.invalidated(encounter_id), [])
        self.assertEqual(doc['state'], 'reviewed')
        self.assertTrue(doc['readiness'].get('approved'))
        codes = {row['code']: row['status'] for row in doc['codes']}
        self.assertEqual(codes['45385'], 'approved')
        self.assertEqual(codes['45378'], 'excluded')

    def test_this_releases_own_answer_keeps_the_other_codes_decision(self):
        # refutation cycle 4 (answers 1-3): an answer to the base code's base_included question - a question a review
        # decision opens and closes - is the review overlay's, and a check another code's answer moves keeps that code's
        # fingerprint, so the approval of 45385 carries, as the installed release carried every decision across an answer
        encounter_id = self.upload(REPORT)
        self.assertEqual(self.decide(encounter_id, '45385', 'approve').status_code, 201)
        (row,) = asked(self.doc(encounter_id), 'base_included')
        self.assertEqual(self.save(encounter_id, row, 'cannot_confirm').status_code, 201)
        self.assertEqual(self.invalidated(encounter_id), [])


class ServiceAnswerUndoTests(_Case):
    """Answers C3-2: an assessment whose documented service's question an answer closed is this revision's write."""

    def setUp(self):
        super().setUp()
        self.provider.selections = [('45385', OFFICE_SNARE)]

    def test_an_earlier_form_service_answer_reassessed_in_the_window_is_held(self):
        encounter_id = self.upload(OFFICE_COLON)
        encounter = self.encounter(encounter_id)
        em = encounter.current_assessment.clarifications.get(fact='em_basis')
        earlier_form(encounter, encounter.current_assessment, '', em.family, 'em_basis', self.reviewer)
        since = timezone.now()
        jobs.reassess_retained(self.encounter(encounter_id), 'c3-synthetic', user=self.reviewer)
        drain()
        current = self.encounter(encounter_id).current_assessment
        self.assertEqual([c.state for c in current.clarifications.filter(fact='em_basis')],
                         [models.Clarification.ANSWERED])
        hazards, hold = undo_reading(since)
        self.assertEqual(hazards, {encounter_id: ['member_answer']})
        self.assertTrue(hold)

    def test_a_withdrawn_service_answer_whose_recompute_stopped_is_held(self):
        since = timezone.now() - datetime.timedelta(seconds=1)
        encounter_id = self.upload(OFFICE_COLON)
        (row,) = asked(self.doc(encounter_id), 'em_basis')
        self.assertEqual(self.save(encounter_id, row, 'not_documented').status_code, 201)
        (answer,) = models.MemberAnswer.objects.filter(encounter_id=encounter_id)
        self.assertEqual(self.client.post(f'/api/encounters/{encounter_id}/details/{answer.pk}/revoke').status_code,
                         201)
        self.client.post(f'/api/encounters/{encounter_id}/stop')
        hazards, hold = undo_reading(since)
        self.assertEqual(hazards, {encounter_id: ['member_answer']})
        self.assertTrue(hold)


class SupersedingServiceAnswerTests(_Case):
    """Answers C3-3: a superseding answer to a closed documented service's question is shown on its row."""

    def setUp(self):
        super().setUp()
        self.provider.selections = [('45385', OFFICE_SNARE)]

    def test_the_new_answer_keeps_its_row_while_its_recompute_is_stopped(self):
        encounter_id = self.upload(OFFICE_COLON)
        (row,) = asked(self.doc(encounter_id), 'em_basis')
        self.assertEqual(self.save(encounter_id, row, 'not_documented').status_code, 201)
        (row,) = asked(self.doc(encounter_id), 'em_basis')
        response = self.client.post(f'/api/encounters/{encounter_id}/details', content_type='application/json',
                                    data=json.dumps({'answers': [{'id': row['id'], 'fact': row['fact'],
                                                                  'value': 'cannot_confirm'}]}))
        self.assertEqual(response.status_code, 201)
        self.client.post(f'/api/encounters/{encounter_id}/stop')
        new = models.MemberAnswer.objects.get(pk=response.json()['answer_ids'][0])
        rows = [(r['fact'], (r['saved'] or {}).get('value'), (r['saved'] or {}).get('answer_id'))
                for r in self.doc(encounter_id)['details_needed']]
        self.assertIn(('em_basis', 'cannot_confirm', str(new.pk)), rows)


class ClosedRowFingerprintTests(_Case):
    """Answers C3-4: a new answer to a row an earlier-form answer closed is bound to that question's fingerprint."""

    def setUp(self):
        super().setUp()
        self.provider.selections = [('45380', FORCEPS), ('45385', HEDGED_SNARE)]

    def test_the_new_answer_carries_the_closed_questions_fingerprint(self):
        encounter_id = self.upload(HEDGED)
        encounter = self.encounter(encounter_id)
        earlier_form(encounter, encounter.current_assessment, '45385', COLON, 'performed_status', self.reviewer)
        jobs.reassess_retained(self.encounter(encounter_id), 'c3-synthetic', user=self.reviewer)
        drain()
        (row,) = asked(self.doc(encounter_id), 'performed_status')
        response = self.client.post(f'/api/encounters/{encounter_id}/details', content_type='application/json',
                                    data=json.dumps({'answers': [{'id': row['id'], 'fact': row['fact'],
                                                                  'value': 'cannot_confirm'}]}))
        self.assertEqual(response.status_code, 201)
        drain()
        new = models.MemberAnswer.objects.get(pk=response.json()['answer_ids'][0])
        self.assertEqual(len(new.question), 64)
        key = questions.member_key('45385', COLON, 'performed_status')
        bound, earlier = questions.bind([{'code': new.code, 'family': new.family, 'fact': new.fact,
                                          'value': new.value, 'question': new.question}], {key: 'e' * 64})
        self.assertEqual((len(bound), [why for _, why in earlier]), (0, [questions.ASKED_DIFFERENTLY]))
