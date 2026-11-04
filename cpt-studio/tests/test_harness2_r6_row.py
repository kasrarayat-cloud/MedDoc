"""Refutation round 6, R6-ROW: the Clarification row while the current revision has no assessment (row-1), and the title
mark of an alternative a peer review proposed with a located quote (falsegreen-2). falsegreen-4 (the page's listedText)
is pinned in the `// refutation round 6, R6-ROW` block of tests/frontend/app.test.cjs, with the row's branches.

row-1. An addendum makes its revision current, and the encounter's current assessment stays the earlier revision's until
the new revision is first assessed - through every stage before that assessment, and for good after a member's Stop
before it. The API serves that assessment as `assessment`, with its clarifications and open_clarifications, while
harness.clarification.open counted the open questions of review.live_assessment - the current assessment only when it
was made on the current revision - and so served 0. The row's guards read doc.assessment, so the row drew "None open" /
"No question is open for this revision." in its succeeded look beside the earlier revision's open questions the same
response serves; with Corti alone too. Now harness_json serves the count as null while the current revision has no
assessment, and the row reads null as it reads no assessment: "Waiting" / "Known once the proposals are checked." while
a stage runs, otherwise "Not asked" / "No question was asked: the proposals were not checked for this revision." - never
a count. The earlier revision's questions are drawn as before: recorded, not repaired here, and not pinned here.

falsegreen-2. HARNESS.md 11.1: a code first proposed in phase 2 is marked proposed after peer review. Round 5 moved the
only pin of the " · proposed after peer review" mark on an alternative's title to an alternative D12 made listed-only,
so a page that drops the mark passed every test. Pinned here on the real pipeline: Fable's peer review adds the HCPCS
code G0121 quoting the landmarks line, which the engine keeps as an alternative proposed by Fable in peer review with a
located quote.

Each pin runs the real pipeline and renders the served detail with the shipped app.js (node). On the base de6418fc6 the
row-1 pins of the window failed for the finding's reason ({'open': 0} and "None open"), and the one before any
assessment failed on the count alone, which was 0. Synthetic data only; nothing is sent: Corti is the suite's
in-process fake read by the real normaliser, and Astra and Fable are the real replay adapters on the real tool loop
(tests.test_harness2_pipeline) or disabled.
"""
import json
import re
from html import unescape
from unittest import mock

from django.conf import settings
from django.test import Client, TestCase, override_settings

from studio import jobs, models, review
from tests import test_harness2_pipeline as hp
from tests.support.operator import OperatorReads
from tests.support import factories as f
from tests.test_harness2_pipeline import LAND, SNARE, TWO_EXTENTS, ColonCase
from tests.test_harness2_r2_evidence import page
from tests.test_harness2_r2_wording import R2WordingCase
from tests.test_harness2_r4_conf import NOTE
from tests.test_harness2_r5_row import CECUM, COLON, RowMixin
from tests.test_pipeline_api import FakeProvider, drain

ADDENDUM = 'The colonoscope was advanced to the cecum.'
# The row while the current revision has no assessment, exactly as it reads where there is no assessment at all: no
# count, no note, and not the succeeded look (gray, never green).
WAITING = {'state': 'waiting', 'badge': 'Waiting', 'tone': 'gray', 'lines': ['Known once the proposals are checked.'],
           'notes': []}
NOT_ASKED = {'state': 'not_run', 'badge': 'Not asked', 'tone': 'gray',
             'lines': ['No question was asked: the proposals were not checked for this revision.'], 'notes': []}


def clarification_row(html):
    """The Clarification row of the Review participants card as a reader sees it: its data-state, its badge and the
    badge's tone, its lines and its notes (tests.test_harness2_r4_conf.clarification_row gives the lines and notes)."""
    at = html.index('data-participant="clarification"')
    start = html.rindex('<div class="check-item', 0, at)
    end = html.find('<div class="check-item', at)
    row = html[start:end if end > 0 else len(html)]
    badge = re.search(r'<span class="status ([^"]*)">([^<]*)</span>', row)
    return {'state': re.search(r'data-state="([^"]*)"', row).group(1), 'badge': unescape(badge.group(2)),
            'tone': badge.group(1), 'lines': [unescape(line) for line in re.findall(r'<p>(.*?)</p>', row)],
            'notes': [unescape(note) for note in re.findall(r'<small class="check-source">(.*?)</small>', row)]}


class StaleMixin(RowMixin):
    def addendum(self, encounter_id, clarification_id=None):
        data = {'text': ADDENDUM, 'synthetic_attestation': 'yes'}
        if clarification_id:
            data['clarification_id'] = clarification_id
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(f'/api/encounters/{encounter_id}/addenda', data=json.dumps(data),
                                        content_type='application/json')
        self.assertEqual(response.status_code, 201, response.content)

    def stop(self, encounter_id):
        self.assertEqual(self.client.post(f'/api/encounters/{encounter_id}/stop').status_code, 200)
        drain()

    def resume(self, encounter_id):
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(self.client.post(f'/api/encounters/{encounter_id}/resume').status_code, 201)
        drain()

    def assert_unassessed(self, detail, row, earlier):
        """The current revision has no assessment, and the current assessment served beside it is an earlier
        revision's, whose open questions ``earlier`` ((scope, fact, code) of each) the same response serves: the API
        serves no count, and the row is ``row`` - never a count of those questions."""
        encounter = models.Encounter.objects.get(pk=detail['id'])
        self.assertIsNone(review.live_assessment(encounter))
        self.assertNotEqual(encounter.current_assessment.revision_id, encounter.current_revision_id)
        self.assertEqual(self.open_questions(detail), earlier)
        self.assertEqual(detail['open_clarifications'], len(earlier))
        # each half on its own, so a regression of either says which
        with self.subTest('the API', state=detail['state']):
            # the finding: {'open': 0}, beside open_clarifications and the open questions served
            self.assertEqual(detail['harness']['clarification'], {'open': None})
        with self.subTest('the page', state=detail['state']):
            # the finding: {'state': 'none', 'badge': 'None open', 'tone': 'green', 'lines': ['No question is open for
            # this revision.'], 'notes': [NOTE]}
            self.assertEqual(clarification_row(page(detail)), row)

    def assert_counted(self, detail):
        """The current revision is assessed: the API counts its assessment's open questions again - those the same
        response serves. Their number."""
        self.assertIsNotNone(review.live_assessment(models.Encounter.objects.get(pk=detail['id'])))
        served = len(self.open_questions(detail))
        self.assertEqual((detail['harness']['clarification'], detail['open_clarifications']),
                         ({'open': served}, served))
        return served


class StaleRowTests(StaleMixin, ColonCase):
    """(A) Participants on, at the release default (no confirmation offered): R4-CONF's CodeQuestionTests input -
    TWO_EXTENTS drained to its final assessment, Corti's 45385 and 45380, two questions each about a code (their
    extents) - then an addendum answering 45385's extent question, as the page's own "Answer with an addendum" sends it.

    Moved at the integration of R6-MEANING (D14): the 45378 Fable's peer review adds is a participant's code no Corti
    proposal carries, so it is listed as an alternative and never a proposal, and no question is asked about it. The
    constants were four open questions before the addendum (45378's base_included and extent among them), three of the
    earlier revision's in the window, and one open once revision 2 was assessed; measured on the merged tree, they are
    two, one (45380's extent) and none. The window's pins - no count, never the earlier revision's - are unchanged."""

    ASKED = [('proposal', 'extent', '45380')]

    def answer_45385(self, encounter_id):
        drain()
        before = self.detail(encounter_id)
        self.assertEqual(before['harness']['clarification'], {'open': 2})
        self.assertEqual(clarification_row(page(before)),
                         {'state': 'open', 'badge': '2 open', 'tone': 'amber',
                          'lines': ['2 open questions are each about a code.'], 'notes': [NOTE]})
        codes = {p['id']: p['code'] for p in before['assessment']['proposals']}
        (question,) = [item for item in before['clarifications'] if item['state'] == 'open'
                       and item['fact'] == 'extent' and codes.get(item['proposal_id']) == '45385']
        self.addendum(encounter_id, question['id'])

    def test_busy_then_stopped_the_row_counts_none_of_the_earlier_revision_s_questions(self):
        self.assertIs(review.confirmations_offered(), False)
        encounter_id = self.create(TWO_EXTENTS)
        self.answer_45385(encounter_id)
        busy = self.detail(encounter_id)
        self.assertEqual((busy['state'], busy['revision']['number'], busy['pipeline']['busy']), ('processing', 2, True))
        self.assert_unassessed(busy, WAITING, self.ASKED)
        self.stop(encounter_id)
        stopped = self.detail(encounter_id)
        self.assertEqual((stopped['state'], stopped['revision']['number'], stopped['pipeline']['busy']),
                         ('stopped', 2, False))
        self.assert_unassessed(stopped, NOT_ASKED, self.ASKED)
        # Resume: once revision 2 is assessed, the API counts its open questions again - none: the addendum's cecum
        # line settles 45380's extent too - and the row reads the count, now of this revision (CortiOnlyStaleRowTests
        # pins a count of one after its resume)
        self.resume(encounter_id)
        resumed = self.detail(encounter_id)
        self.assertEqual(self.assert_counted(resumed), 0)
        self.assertEqual(clarification_row(page(resumed)),
                         {'state': 'none', 'badge': 'None open', 'tone': 'green',
                          'lines': ['No question is open for this revision.'], 'notes': [NOTE]})

    def test_the_count_is_null_through_every_stage_before_the_revision_s_first_assessment(self):
        encounter_id = self.create(TWO_EXTENTS)
        self.answer_45385(encounter_id)
        unassessed, counted = [], []
        while (job := jobs.claim_next()) is not None:
            jobs.run_job(job)
            detail = self.detail(encounter_id)
            if review.live_assessment(self.encounter(encounter_id)) is None:
                self.assert_unassessed(detail, WAITING, self.ASKED)
                unassessed.append(job.kind)
            else:
                self.assert_counted(detail)
                counted.append(job.kind)
        self.assertEqual(unassessed, ['extract', 'analyze', 'predict', 'astra', 'fable'])
        self.assertEqual(counted, ['assess', 'astra_peer', 'fable_peer', 'assess'])


@override_settings(PROVIDER_MODE='live', AUTHORIZATION_REF='docs/foundation/rulings/2026-10-23-cpt-studio-gi.md')
class CortiOnlyStaleRowTests(OperatorReads, StaleMixin, TestCase):
    """(B) Corti alone at the release default (Astra and Fable disabled, no confirmation offered): R5-ROW's
    CortiOnlyTests input - Corti selects 45385 on the snare and 45378 on the cecum, and the engine asks whether 45378 is
    reported separately from 45385 - then an addendum that answers no question (POST /addenda needs none)."""

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

    def create(self):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post('/api/encounters', {'text': COLON, 'synthetic_attestation': 'yes'})
        self.assertEqual(response.status_code, 201, response.content)
        return response.json()['id']

    def test_busy_then_stopped_the_row_counts_none_of_the_earlier_revision_s_question(self):
        self.assertEqual((settings.ASTRA_MODE, settings.FABLE_MODE), ('disabled', 'disabled'))
        self.assertIs(review.confirmations_offered(), False)
        encounter_id = self.create()
        drain()
        before = self.detail(encounter_id)
        self.assertEqual((before['harness']['phase'], before['harness']['clarification']), (0, {'open': 1}))
        asked = [('proposal', 'base_included', '45378')]
        self.assertEqual(self.open_questions(before), asked)
        self.addendum(encounter_id)
        busy = self.detail(encounter_id)
        self.assertEqual((busy['state'], busy['revision']['number'], busy['harness']['phase']), ('processing', 2, 0))
        self.assert_unassessed(busy, WAITING, asked)
        self.stop(encounter_id)
        stopped = self.detail(encounter_id)
        self.assertEqual((stopped['state'], stopped['revision']['number'], stopped['harness']['phase']),
                         ('stopped', 2, 0))
        self.assert_unassessed(stopped, NOT_ASKED, asked)
        self.resume(encounter_id)
        self.assertEqual(self.assert_counted(self.detail(encounter_id)), 1)

    def test_before_any_assessment_the_count_is_null_and_the_row_reads_as_before(self):
        # no assessment at all (the first revision's pipeline queued, then stopped): no count either, and the row as it
        # read before, from doc.assessment (the count was 0 here)
        encounter_id = self.create()
        busy = self.detail(encounter_id)
        self.assertEqual((busy['state'], busy['assessment'], busy['open_clarifications']), ('processing', None, 0))
        self.assertEqual(busy['harness']['clarification'], {'open': None})
        self.assertEqual(clarification_row(page(busy)), WAITING)
        self.stop(encounter_id)
        stopped = self.detail(encounter_id)
        self.assertEqual((stopped['state'], stopped['assessment'], stopped['open_clarifications']),
                         ('stopped', None, 0))
        self.assertEqual(stopped['harness']['clarification'], {'open': None})
        self.assertEqual(clarification_row(page(stopped)), NOT_ASKED)


class PeerProposedAlternativeTitleTests(R2WordingCase):
    """falsegreen-2: ColonCase, except Fable's peer review adds G0121 quoting the landmarks line. G0121 is an HCPCS code
    outside the GI profiles, so the engine keeps it as an alternative, proposed by Fable in peer review with a located
    quote; its title on the page carries the mark (HARNESS.md 11.1)."""

    def test_an_alternative_a_peer_review_proposed_is_titled_proposed_after_peer_review(self):
        self.adapters['fable'].peer = [hp.answered('fable', hp.peer_answer(codes=[('G0121', LAND)]), number=2)]
        encounter_id = self.create(TWO_EXTENTS)
        drain()
        detail = self.detail(encounter_id)
        (alternative,) = self.proposals(detail, 'G0121')
        self.assertEqual((alternative['bucket'], alternative['proposed_by'], alternative['listed_by'],
                          alternative['phases'], alternative['family_label']),
                         ('alternative', ['fable'], [], {'fable': 'peer_review'}, 'Service outside the GI profiles'))
        # the mutant m_js_titlesuffix (no mark on an alternative's title) drew '<strong>G0121 · Service outside the GI
        # profiles</strong>' and passed every test
        self.assertEqual(re.findall(r'<strong>(G0121 · [^<]*)</strong>', page(detail)),
                         ['G0121 · Service outside the GI profiles · proposed after peer review'])
