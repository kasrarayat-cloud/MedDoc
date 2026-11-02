"""Refutation round 4, R4-CONF: with confirmations off no candidate is served (HARNESS.md 12.10 as amended, the
session's D8).

Round 3's D7 still served, for every open question, each participant's "located passage" with "Their answer: <value>".
Those values were CPT Studio's own inferences from a participant's reading, never its answer to the question: an E/M
basis read by the dormant check's own reader in the passage, which also chose the passages shown ("Their answer: time"
beside "Total time of 45 minutes is not used to select the level", d7-1; an earlier visit's time in a history section,
truth-1), and a service's status or extent paired with every quote of that service ("performed" beside a
photographed-landmarks sentence for a forceps biopsy question Fable never addressed, d7-2). Pinned here at the release
default, settings.STUDIO_OFFER_CONFIRMATIONS (a code-level False):

- D8 (d7-1, d7-2, truth-1): review.assessment_candidates is {} before it reads a participant's reading; the API serves
  every clarification's candidates as [] to every member, and can_confirm false; the page draws no candidate block, no
  "Their answer" and no located passage; review.located_passages and review.UNCHECKED_WHY are removed (falsegreen-5, an
  unpinned copy of the candidates' merge in located_passages, is moot with it). The dormant path is the control: it
  still offers the same rows' candidates to a member who may confirm one.

Each test failed on the base 3daafa91b. Synthetic data only; nothing is sent: Corti is the harness@1 suite's in-process
fake, Astra and Fable the real replay adapters on the real tool loop (tests.test_harness2_pipeline) or the recorded rows
of tests.test_harness2_api.
"""
from contextlib import ExitStack
from unittest import mock

from django.test import override_settings

from studio import jobs, models, review
from tests import test_harness2_api as h2
from tests.test_harness2_pipeline import EMPTY_PEER, HEAD, answered, reading
from tests.test_harness2_pipeline import Harness2Case as PipelineCase
from tests.test_harness2_r2_evidence import NO_BASIS, PRIOR, VISIT, page
from tests.test_participants_support import code as code_item, empty_reading, service as service_item
from tests.test_pipeline_api import drain

DORMANT = dict(STUDIO_OFFER_CONFIRMATIONS=True)  # the dormant confirmation path, as its own tests run it
# What the page drew for a located passage in round 3 (D7), none of which a page may now say.
LOCATED_WORDS = ('candidate-answers', 'Their answer', 'located passages', 'located for this question', 'Located by',
                 'An answer CPT Studio cannot restate', 'confirm-finding', '<span class="status green">Verified</span>')
# Every reader a served candidate came from, none of which runs for the response while confirmations are not offered.
READERS = ('studio.review.frozen_inputs', 'studio.review.peer_answers', 'studio.review.recorded_inventory',
           'studio.candidates.candidates', 'studio.candidates._reading_sources', 'studio.candidates._answer_sources',
           'studio.candidates._basis_stated', 'studio.validation.reconcile.status_stated')


# --- D8: no candidate is served while confirmations are not offered (d7-1, d7-2, truth-1) -----------------------------

@override_settings(**h2.BOTH)
class NoCandidateTests(h2.Harness2Case):
    """The harness@2 case's final assessment: four open questions - 45385's extent, 45380's status and extent, the date
    of service - for which round 3 served eight located passages, three of them "Their answer: performed" for a forceps
    biopsy question on passages that do not name it (d7-2, truth-1 (b))."""

    def open_questions(self):
        return list(self.final.clarifications.filter(state=models.Clarification.OPEN))

    def test_no_candidate_is_served_and_no_reading_is_read_for_one(self):
        self.assertEqual(sorted(q.fact for q in self.open_questions()),
                         ['extent', 'extent', 'performed_status', 'service_date'])
        with ExitStack() as stack:
            for target in READERS:
                stack.enter_context(mock.patch(target, side_effect=AssertionError(f'{target} was read')))
            self.assertEqual(review.assessment_candidates(self.final), {})
        # the control: the dormant path offers every open question candidates from the same rows
        with override_settings(**DORMANT):
            dormant = review.assessment_candidates(self.final)
        self.assertEqual(set(dormant), {str(q.pk) for q in self.open_questions()})
        self.assertTrue(all(dormant.values()), dormant)

    def test_the_api_serves_no_member_a_candidate_and_no_member_may_confirm(self):
        for user in (self.owner, self.reviewer, self.viewer):
            with self.subTest(user=user.username):
                data = self.client_for(user).get(f'/api/encounters/{self.encounter.pk}').json()
                self.assertIs(data['permissions']['can_confirm'], False)
                self.assertEqual(sum(c['state'] == 'open' for c in data['clarifications']), 4)
                self.assertEqual([(c['candidates'], c['confirmation']) for c in data['clarifications']],
                                 [([], None)] * len(data['clarifications']))
        # the control: on the dormant path a member who may confirm is served the candidates; a member who may not is
        # served none (candidates go only to a member who may confirm one)
        with override_settings(**DORMANT):
            served = {user: self.client_for(user).get(f'/api/encounters/{self.encounter.pk}').json()
                      for user in (self.reviewer, self.viewer)}
        reviewer, viewer = served[self.reviewer], served[self.viewer]
        self.assertIs(reviewer['permissions']['can_confirm'], True)
        self.assertTrue(all(c['candidates'] for c in reviewer['clarifications'] if c['state'] == 'open'))
        self.assertIs(viewer['permissions']['can_confirm'], False)
        self.assertEqual([c['candidates'] for c in viewer['clarifications']], [[]] * len(viewer['clarifications']))

    def test_the_page_draws_no_candidate_and_no_answer_it_attributes_to_a_participant(self):
        detail = self.client_for(self.owner).get(f'/api/encounters/{self.encounter.pk}').json()
        html = page(detail)
        for words in LOCATED_WORDS:
            self.assertNotIn(words, html)
        self.assertNotIn('data-question=', html)
        # each question is still asked where it was: on its code's card, the date with the encounter
        for question in self.open_questions():
            self.assertIn(f'data-clarification="{question.pk}"', html)

    def test_the_located_passage_reader_and_its_fixed_why_are_removed(self):
        self.assertFalse(hasattr(review, 'located_passages'))
        self.assertFalse(hasattr(review, 'UNCHECKED_WHY'))


OFFICE_TOP = (HEAD + 'Office visit note (fictional)\nDate of service: 2026-10-20\nPlace of service: Office\n'
              + VISIT + '\n')
EM_NOT_USED = 'Total time of 45 minutes is not used to select the level; the level rests on MDM.'
OFFICE_TAIL = 'Assessment: reflux, stable on current therapy.\nPlan: continue omeprazole.\n'


class BasisTests(PipelineCase):
    """d7-1 and truth-1 (a), through the real pipeline at the release default: Corti selects 99214 on the visit line,
    and Astra's first reading has one office visit service quoting a single sentence (the reading schema has no basis
    field). Round 3 served it "Their answer: time" - the dormant check's own E/M reader's value of the sentence."""
    corti_codes = (('99214', VISIT),)

    def setUp(self):
        super().setUp()
        self.assertIs(review.confirmations_offered(), False)

    def served(self, text, passage):
        office = empty_reading(codes=[code_item('99214', service_ids=[], evidence=[VISIT])],
                               services=[service_item(1, id='v1', family='office_em', evidence=[passage])])
        self.adapters['astra'].first = [answered('astra', office)]
        self.adapters['fable'].first = [answered('fable', reading())]
        for name in ('astra', 'fable'):
            self.adapters[name].peer = [answered(name, EMPTY_PEER, number=2)]
        encounter_id = self.create(text)
        drain()
        final = self.encounter(encounter_id).current_assessment
        self.assertEqual((jobs.assessment_phase(final), review.is_final(final)), (2, True))
        question = final.clarifications.get(fact='em_basis', state=models.Clarification.OPEN)
        detail = self.client.get(f'/api/encounters/{encounter_id}').json()
        served = next(c for c in detail['clarifications'] if c['id'] == str(question.pk))['candidates']
        self.assertEqual(served, [])
        html = page(detail)
        for words in LOCATED_WORDS:
            self.assertNotIn(words, html)
        # the control: the input reaches the candidates' readers, which the dormant path still runs
        with override_settings(**DORMANT):
            self.assertTrue(review.assessment_candidates(final)[str(question.pk)])

    def test_a_basis_read_in_a_passage_that_denies_it_is_never_served(self):
        self.served(OFFICE_TOP + EM_NOT_USED + '\n' + OFFICE_TAIL, EM_NOT_USED)

    def test_an_earlier_visit_s_time_is_never_served_as_this_visit_s_basis(self):
        self.served(NO_BASIS, PRIOR)
