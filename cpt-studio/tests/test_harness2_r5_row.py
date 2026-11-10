"""Refutation round 5, R5-ROW: the Clarification row only counts (HARNESS.md 12.10 as amended, the session's D11;
d8-1, truth-4, parity-1, truth-5).

Round 4 (d7-3) had the row say what each open question holds by the readiness rules: "4 questions about codes are
open; each holds its code, which can still be rejected." and "One question about a documented service no code carries
is open; it holds neither a code nor the reviewed report." The row read neither a code's decision, nor whether the
assessment is final, nor which service a code carries, so each sentence was false in a state the page reaches:

- d8-1 (a), truth-4: every selected code rejected (only revoke offered) and the encounter reviewed, its questions still
  open - no question holds a code, and none "can still be rejected";
- d8-1 (b): a run stopped after assess #1 - not final, so no action is offered and a decision is refused (409);
- parity-1: a Corti-only page at the release default (Astra and Fable disabled), a code rejected while its question is
  still open (tests.test_review.ReadinessTests.test_a_clarification_needing_proposal_blocks_until_rejected's shape,
  here through the real pipeline);
- truth-5: a conflict on the documented service 45385 carries, called a service "no code carries".

D11: the row says how many questions are open and what each is about - the encounter (scope encounter, no proposal), a
code (a proposal) or a documented service (scope service, no proposal) - and nothing else; where the questions served
do not account for the API's count it says only the count, as before. What holds the reviewed report is readiness's to
say - review.readiness's blockers, which the page draws as "Still needed: ..." (exportStatusText), pinned here beside
each row - and the row restates none of it. The note "A participant's own questions never hold the reviewed report."
stays (HARNESS.md 5).

Each pin runs the real pipeline and renders the served detail with the shipped app.js (node), as R4-CONF's
CodeQuestionTests do; each failed on the base 0ca5e6623 for its finding's reason. Synthetic data only; nothing is sent:
Corti is the suite's in-process fake read by the real normaliser, and Astra and Fable are the real replay adapters on
the real tool loop (tests.test_harness2_pipeline) or disabled.
"""
import json
from unittest import mock

from django.conf import settings
from django.test import Client, TestCase, override_settings

from studio import customer_api, jobs, review
from tests.legacy_chain import applied
from tests.support import factories as f
from tests.support.operator import OperatorReads
from tests.test_harness2_pipeline import EMPTY_PEER, HEAD, SNARE, TWO_EXTENTS, ColonCase, answered, reading
from tests.test_harness2_pipeline import Harness2Case as PipelineCase
from tests.test_harness2_r2_evidence import page
from tests.test_harness2_r2_wording import browser
from tests.test_harness2_r4_conf import NOTE, clarification_row, reject_selected
from tests.test_pipeline_api import FakeProvider, drain

# What the row no longer says of an open question (D11): what it holds, whether its code can still be rejected, how it
# is settled, or that no code carries its service.
UNSAID = ('hold', 'reject', 'settle', 'addendum', 'no code carries')
REVIEWED = 'Reviewed — every selected code has a current decision.'


class RowMixin:
    def detail(self, encounter_id):
        response = self.client.get(f'/ops/api/encounters/{encounter_id}')
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()

    def open_questions(self, detail):
        """(scope, fact, code) of each open question served, sorted; a question about no code has code ''."""
        codes = {proposal['id']: proposal['code'] for proposal in detail['assessment']['proposals']}
        return sorted((item['scope'], item['fact'], codes.get(item['proposal_id']) or '')
                      for item in detail['clarifications'] if item['state'] == 'open')

    def still_needed(self, detail):
        """What readiness says on the page (exportStatusText, from review.readiness's blockers): what holds the reviewed
        report, which the row restates none of."""
        return browser('app.exportStatusText(data)', detail)

    def assert_counts(self, detail, lines):
        """The row as the page draws it: exactly ``lines``, then the note, and no line saying what a question holds,
        whether its code can still be rejected, how it is settled, or that no code carries a service."""
        drawn, notes = clarification_row(page(detail))
        for line in drawn:
            for word in UNSAID:
                self.assertNotIn(word, line.lower(), line)
        self.assertEqual((drawn, notes), (lines, [NOTE]))


@applied
class AfterRejectionTests(RowMixin, ColonCase):
    """d8-1 (a), truth-4: R4-CONF's CodeQuestionTests input - TWO_EXTENTS, Corti's 45385 and 45380 and the 45378 Fable's
    peer review adds, four questions each about a code - and then reject_selected. Moved by refutation round 6
    (R6-MEANING, the session's D14): the 45378 Fable's peer review adds is its alternative, never a proposal, so its two
    questions are not asked: two questions, each about one of Corti's codes."""

    def test_every_code_rejected_and_the_encounter_reviewed_the_row_says_only_what_is_open(self):
        self.assertIs(review.confirmations_offered(), False)
        encounter_id = self.create(TWO_EXTENTS)
        drain()
        encounter = self.encounter(encounter_id)
        final = encounter.current_assessment
        self.assertEqual((jobs.assessment_phase(final), review.is_final(final)), (2, True))
        asked = [('proposal', 'extent', '45380'), ('proposal', 'extent', '45385')]
        before = self.detail(encounter_id)
        self.assertEqual(self.open_questions(before), asked)
        # readiness says what holds the reviewed report: each code its open question holds
        self.assertEqual(self.still_needed(before),
                         'Draft — not reviewed. Still needed: 45385 has an open clarification; '
                         '45380 has an open clarification.')
        reject_selected(encounter, final, self.reviewer, self.ws)
        after = self.detail(encounter_id)
        # the state round 4's row was false in: every code rejected, only revoke offered, the encounter reviewed, and
        # every question still open
        self.assertEqual(self.open_questions(after), asked)
        self.assertEqual(sorted((p['code'], p['decision_state'], p['allowed_actions'])
                                for p in after['assessment']['proposals'] if p['bucket'] == 'selected'),
                         [(code, 'rejected', ['revoke']) for code in ('45380', '45385')])
        self.assertEqual(after['readiness'], {'draft': True, 'reviewed': True, 'blockers': []})
        self.assertEqual(after['harness']['final']['state'], 'reviewed')
        self.assertEqual(self.still_needed(after), REVIEWED)
        # the finding: the row still said "4 questions about codes are open; each holds its code, which can still be
        # rejected."
        self.assert_counts(after, ['2 open questions are each about a code.'])
        # and it says the same before any decision: it reads no decision, so it says nothing a decision changes
        self.assert_counts(before, ['2 open questions are each about a code.'])


@applied
class StoppedTests(RowMixin, ColonCase):
    """d8-1 (b): the same case stopped after assess #1. That assessment owes its peer reviews, so it is not final: no
    action is offered and a decision is refused."""

    def test_a_run_stopped_before_its_peer_reviews_the_row_says_only_what_is_open(self):
        self.assertIs(review.confirmations_offered(), False)
        encounter_id = self.create(TWO_EXTENTS)
        jobs.run_job(self.run_until('assess'))  # assess #1, which queues the first peer stage
        self.assertEqual(self.client.post(f'/api/encounters/{encounter_id}/stop').status_code, 200)
        drain()
        encounter = self.encounter(encounter_id)
        current = encounter.current_assessment
        self.assertEqual((encounter.state, jobs.assessment_phase(current), review.is_final(current)),
                         ('stopped', 1, False))
        detail = self.detail(encounter_id)
        self.assertEqual(self.open_questions(detail),
                         [('proposal', 'extent', '45380'), ('proposal', 'extent', '45385')])
        selected = [p for p in detail['assessment']['proposals'] if p['bucket'] == 'selected']
        self.assertEqual([p['allowed_actions'] for p in selected], [[], []])
        refused = self.post(f'/api/encounters/{encounter_id}/decisions',
                            {'proposal_id': selected[0]['id'], 'action': 'reject', 'note': 'Synthetic rejection.'})
        # moved by the customer interface change (CORE-UX-DESIGN.md 5): a refusal reaches a member in the customer
        # vocabulary
        self.assertEqual((refused.status_code, refused.json()),
                         (409, {'error': customer_api.customer_error(review.NOT_FINAL_DECISION)}))
        self.assertIn(f'Still needed: {review.NOT_FINAL_BLOCKER}', self.still_needed(detail))
        # the finding: the row said "2 questions about codes are open; each holds its code, which can still be
        # rejected."
        self.assert_counts(detail, ['2 open questions are each about a code.'])


CECUM = 'The colonoscope was advanced to the cecum and the examination was completed.'
COLON = (HEAD + 'Colonoscopy report (fictional)\nDate of service: 2026-10-21\n'
         'Place of service: Ambulatory surgery center\nProcedure: Colonoscopy\n' + CECUM + '\n'
         'A 9 mm pedunculated polyp in the sigmoid colon was removed with a hot snare.\n')


@applied
@override_settings(PROVIDER_MODE='live', AUTHORIZATION_REF='docs/foundation/rulings/2026-10-23-cpt-studio-gi.md')
class CortiOnlyTests(OperatorReads, RowMixin, TestCase):
    """parity-1: Corti alone at the release default (Astra and Fable disabled, no confirmation offered). Corti selects
    45385 on the snare and 45378 on the cecum, and the engine asks whether 45378 is reported separately from 45385 - a
    question about 45378. A reviewer approves 45385 and rejects 45378: the encounter is reviewed and the question is
    still open."""

    def setUp(self):
        super().setUp()
        self.ws = f.workspace()
        self.reviewer = f.member(self.ws, f.user('reviewer'))
        self.client = Client(enforce_csrf_checks=False)
        self.client.force_login(self.reviewer)
        corti = FakeProvider(selections=[('45385', SNARE), ('45378', CECUM)])
        patcher = mock.patch('studio.jobs.get_provider', return_value=corti)
        patcher.start()
        self.addCleanup(patcher.stop)

    def post(self, path, data):
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(path, data=json.dumps(data), content_type='application/json')

    def decide(self, detail, code, action, **extra):
        (proposal,) = [p for p in detail['assessment']['proposals'] if p['code'] == code and p['bucket'] == 'selected']
        response = self.post(f'/api/encounters/{detail["id"]}/decisions',
                             {'proposal_id': proposal['id'], 'action': action, **extra})
        self.assertEqual(response.status_code, 201, response.content)

    def test_a_rejected_code_whose_question_is_still_open_the_row_says_only_what_is_open(self):
        self.assertEqual((settings.ASTRA_MODE, settings.FABLE_MODE), ('disabled', 'disabled'))
        self.assertIs(review.confirmations_offered(), False)
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post('/api/encounters', {'text': COLON, 'synthetic_attestation': 'yes'})
        self.assertEqual(response.status_code, 201, response.content)
        encounter_id = response.json()['id']
        drain()
        before = self.detail(encounter_id)
        self.assertEqual(before['harness']['phase'], 0)
        self.assertEqual([(p['name'], p['state']) for p in before['harness']['participants']][1:],
                         [('astra', 'not_configured'), ('fable', 'not_configured')])
        self.assertEqual(self.open_questions(before), [('proposal', 'base_included', '45378')])
        self.assertEqual(self.still_needed(before), 'Draft — not reviewed. Still needed: 45385 has no decision; '
                                                    '45378 has an open clarification.')
        self.decide(before, '45385', 'approve', acknowledgement=review.ACKNOWLEDGEMENTS['human'])
        self.decide(before, '45378', 'reject', note='Synthetic rejection.')
        after = self.detail(encounter_id)
        self.assertEqual(self.open_questions(after), [('proposal', 'base_included', '45378')])
        (rejected,) = [p for p in after['assessment']['proposals'] if p['code'] == '45378']
        self.assertEqual((rejected['decision_state'], rejected['allowed_actions']), ('rejected', ['revoke']))
        self.assertEqual(after['readiness'], {'draft': True, 'reviewed': True, 'blockers': []})
        self.assertEqual(self.still_needed(after), REVIEWED)
        # the finding: the row said "One question about a code is open; it holds that code, which can still be
        # rejected." beside "Final status | Reviewed"
        self.assert_counts(after, ['One open question is about a code.'])
        self.assert_counts(before, ['One open question is about a code.'])


CONFLICT = (HEAD + 'Colonoscopy report (fictional)\nDate of service: 2026-10-14\nProcedure: Colonoscopy\n'
            + CECUM + '\nA 9 mm pedunculated polyp in the sigmoid colon was removed with a hot snare.\n'
            'Cold forceps biopsies were taken from the sigmoid colon.\nNo biopsies were taken.\n')


@applied
class CarriedServiceTests(RowMixin, PipelineCase):
    """truth-5: a documented colonoscopy that both states and denies a forceps biopsy. 45385, which Corti and both
    participants propose on the snare line, carries that colonoscopy; the readers ask the conflict as a question about
    the documented service."""
    corti_codes = (('45385', SNARE),)

    def test_a_conflict_on_a_service_a_code_carries_the_row_says_only_what_is_open(self):
        both = reading(codes=[('45385', SNARE)], services=[('c1', 'colonoscopy', 'performed', SNARE)])
        for name in ('astra', 'fable'):
            self.adapters[name].first = [answered(name, both)]
            self.adapters[name].peer = [answered(name, EMPTY_PEER, number=2)]
        encounter_id = self.create(CONFLICT)
        drain()
        final = self.encounter(encounter_id).current_assessment
        self.assertEqual((jobs.assessment_phase(final), review.is_final(final)), (2, True))
        detail = self.detail(encounter_id)
        (question,) = [item for item in detail['clarifications'] if item['state'] == 'open']
        self.assertEqual((question['scope'], question['fact'], question['proposal_id']),
                         ('service', 'conflict:biopsy', None))
        # the documented service it asks about is the one 45385 carries
        (conflict,) = final.services['conflicts']
        (snare,) = [p for p in detail['assessment']['proposals'] if p['bucket'] == 'selected']
        self.assertEqual((snare['code'], snare['support']['service']), ('45385', conflict['service']))
        # readiness: the question holds neither the code nor the reviewed report
        self.assertEqual(self.still_needed(detail), 'Draft — not reviewed. Still needed: 45385 has no decision.')
        # the finding: the row said "One question about a documented service no code carries is open; it holds neither
        # a code nor the reviewed report."
        self.assert_counts(detail, ['One open question is about a documented service.'])
