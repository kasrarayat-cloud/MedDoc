"""Round 5 regressions in review, reports and the review page (repair round 4c, lead).

bypass:0 — confirming a gated E/M's exclusion releases the same-day rule exactly as a rejection does.
bypass:3 — the reviewed TXT says what the review recorded, counted from its own lists.
bypass:4 — an approval records the current whole-document attestation, word for word, or is refused.
Synthetic data only.
"""
import re
from pathlib import Path

from django.core.exceptions import ValidationError
from django.test import TestCase

from studio import models, reports, review, serializers
from tests.support import pipeline_factories as pf

EM_GATE, MARKER = 'em.same_day_if_reinstated', 'review.same_day_em'
SAME_DAY = '99213 needs a separately identifiable E/M: 46221 was reinstated as a same-day procedure'
APP_JS = Path(__file__).resolve().parents[1] / 'studio' / 'static' / 'studio' / 'app.js'


def excluded_em_result():
    """The banding visit of bypass:0: the E/M and the banding are both reinstatable exclusions."""
    em_gate = pf.check(EM_GATE, 'warn')
    marker = pf.check(MARKER, 'warn')
    reinstatement = pf.check('review.reinstatement', 'pass')
    return pf.result(
        pf.proposal('exc:0', '99213', [pf.DATE_PASSAGE], bucket='excluded', reinstatable=True,
                    checks=pf.standard_checks() + (reinstatement, em_gate)),
        pf.proposal('exc:1', '46221', [pf.PLAN_PASSAGE], bucket='excluded', reinstatable=True,
                    checks=pf.standard_checks() + (reinstatement, marker)))


def selected_em_result():
    em_gate = pf.check(EM_GATE, 'warn')
    marker = pf.check(MARKER, 'warn')
    reinstatement = pf.check('review.reinstatement', 'pass')
    return pf.result(
        pf.proposal('sel:0', '99213', [pf.DATE_PASSAGE], checks=pf.standard_checks() + (em_gate,)),
        pf.proposal('exc:1', '46221', [pf.PLAN_PASSAGE], bucket='excluded', reinstatable=True,
                    checks=pf.standard_checks() + (reinstatement, marker)))


class ConfirmedEmReleasesTheSameDayRuleTests(TestCase):
    """bypass:0. Before the repair a confirmed E/M exclusion kept the blocker, so a review that decided every code
    correctly could never produce a reviewed report."""

    def setUp(self):
        self.s = pf.scenario()

    def ready(self):
        return review.readiness(self.s.encounter)

    def test_confirming_the_em_then_reinstating_and_approving_the_banding_is_reviewed(self):
        pf.assess(self.s.encounter, excluded_em_result(), ctx=pf.context(self.s.encounter, self.s.revision))
        self.s.decide('exc:0', 'confirm', note='No separate E/M at this visit.')
        self.s.decide('exc:1', 'reinstate', note='Banded today.')
        self.s.decide('exc:1', 'approve')
        self.assertEqual(self.ready(), {'draft': True, 'reviewed': True, 'blockers': []})
        snap = reports.snapshot(self.s.encounter, reports.REVIEWED)
        lists = {item['code']: item['list'] for item in snap['proposals']}
        self.assertEqual(lists, {'99213': 'excluded', '46221': 'approved'})

    def test_the_other_order_is_reviewed_too(self):
        pf.assess(self.s.encounter, excluded_em_result(), ctx=pf.context(self.s.encounter, self.s.revision))
        self.s.decide('exc:1', 'reinstate')
        self.s.decide('exc:1', 'approve')
        self.s.decide('exc:0', 'confirm')
        self.assertEqual(self.ready()['blockers'], [])

    def test_an_undecided_excluded_em_shows_only_its_own_blocker(self):
        pf.assess(self.s.encounter, excluded_em_result(), ctx=pf.context(self.s.encounter, self.s.revision))
        self.s.decide('exc:1', 'reinstate')
        self.s.decide('exc:1', 'approve')
        self.assertEqual(self.ready()['blockers'],
                         ['99213 was excluded by a documentation check: confirm the exclusion or reinstate it'])

    def test_a_reinstated_or_approved_em_is_still_held(self):
        pf.assess(self.s.encounter, excluded_em_result(), ctx=pf.context(self.s.encounter, self.s.revision))
        self.s.decide('exc:1', 'reinstate')
        self.s.decide('exc:0', 'reinstate')
        self.assertIn(SAME_DAY, self.ready()['blockers'])
        self.s.decide('exc:1', 'revoke')
        self.s.decide('exc:0', 'approve')  # approved while the banding is not reinstated
        self.s.decide('exc:1', 'reinstate')
        self.assertIn(SAME_DAY, self.ready()['blockers'])
        self.assertFalse(self.ready()['reviewed'])

    def test_a_selected_em_keeps_its_explanation_until_it_is_rejected(self):
        pf.assess(self.s.encounter, selected_em_result(), ctx=pf.context(self.s.encounter, self.s.revision))
        self.s.decide('exc:1', 'reinstate')
        self.assertIn(SAME_DAY, self.ready()['blockers'])
        self.s.decide('sel:0', 'reject')
        self.assertNotIn(SAME_DAY, self.ready()['blockers'])


class ReviewedStatusLineTests(TestCase):
    """bypass:3. The line was fixed text: 'every proposed code has an approve or reject decision', also for a review
    that recorded only confirmations."""

    def setUp(self):
        self.s = pf.scenario()

    def status_line(self):
        text = bytes(reports.generate(self.s.encounter, models.ReportArtifact.REVIEWED, 'txt',
                                      self.s.reviewer).content).decode('utf-8')
        (line,) = [ln for ln in text.splitlines() if ln.startswith('Review status:')]
        return line

    def test_a_review_of_confirmations_only_says_so(self):
        pf.assess(self.s.encounter, excluded_em_result(), ctx=pf.context(self.s.encounter, self.s.revision))
        self.s.decide('exc:0', 'confirm')
        self.s.decide('exc:1', 'confirm')
        line = self.status_line()
        self.assertTrue(line.startswith('Review status: complete — 0 approved, 0 rejected, 2 documentation-check '
                                        'exclusions confirmed;'), line)
        self.assertNotIn('every proposed code has an approve or reject decision', line)

    def test_the_counts_follow_the_lists(self):
        pf.assess(self.s.encounter, pf.standard_result())
        self.s.decide('sel:0', 'approve')
        self.s.decide('sel:1', 'reject')
        self.s.decide('exc:0', 'confirm')
        line = self.status_line()
        self.assertTrue(line.startswith('Review status: complete — 1 approved, 1 rejected, 1 documentation-check '
                                        'exclusion confirmed;'), line)
        self.assertIsNone(re.search(r'NOT\s+REVIEWED|UNREVIEWED', line, re.I))


class AcknowledgementIsTheAttestationTests(TestCase):
    """bypass:4. Approve accepted any non-empty acknowledgement, so a reviewed report could carry 'I did not read the
    document.' as an approval's attestation."""

    def setUp(self):
        self.s = pf.scenario()
        pf.assess(self.s.encounter, pf.standard_result())

    def test_any_other_text_is_refused_and_nothing_is_recorded(self):
        for text in ('I did not read the document.',
                     'I reviewed the source evidence for this code. This synthetic review is not clinical approval '
                     'or billing advice.',
                     review.ACKNOWLEDGEMENTS['agent'],  # the other actor kind's attestation
                     review.ACKNOWLEDGEMENTS['human'][:-1]):
            with self.subTest(text=text[:40]), self.assertRaisesRegex(ValidationError, 'current review attestation'):
                self.s.decide('sel:0', 'approve', acknowledgement=text)
        self.assertFalse(models.Decision.objects.filter(action='approve').exists())

    def test_each_actor_kind_records_its_own_attestation(self):
        with self.assertRaisesRegex(ValidationError, 'current review attestation'):
            self.s.decide('sel:1', 'approve', user=self.s.agent, acknowledgement=review.ACKNOWLEDGEMENTS['human'])
        human = self.s.decide('sel:0', 'approve')
        agent = self.s.decide('sel:1', 'approve', user=self.s.agent)
        self.assertEqual(human.acknowledgement, review.ACKNOWLEDGEMENTS['human'])
        self.assertEqual(agent.acknowledgement, review.ACKNOWLEDGEMENTS['agent'])

    def test_surrounding_whitespace_is_not_a_different_attestation(self):
        decision = self.s.decide('sel:0', 'approve', acknowledgement=f"  {review.ACKNOWLEDGEMENTS['human']}\n")
        self.assertEqual(decision.acknowledgement, review.ACKNOWLEDGEMENTS['human'])

    def test_the_session_serves_the_attestation_the_server_accepts(self):
        for user in (self.s.reviewer, self.s.agent):
            payload = serializers.session_json(user, self.s.membership(user))
            self.assertEqual(payload['acknowledgement'], review.ACKNOWLEDGEMENTS[user.actor_kind])

    def test_the_page_keeps_the_same_two_strings(self):
        source = APP_JS.read_text(encoding='utf-8')
        block = source[source.index('const ACKNOWLEDGEMENTS = {'):]
        block = block[:block.index('};')]
        for kind in ('human', 'agent'):
            (text,) = re.findall(rf"\n  {kind}: '([^']*)',", block)
            self.assertEqual(text, review.ACKNOWLEDGEMENTS[kind], kind)
