"""Refutation round 4, R4-CONF: with confirmations off no candidate is served, and nothing CPT Studio says names a way
a question is settled or a confirmation it does not offer (HARNESS.md 12.10 as amended, the session's D8).

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
- d7-3: the refusal says only what happened (review.CONFIRMATIONS_NOT_OFFERED, the dev preview server's), and the
  Clarification row says what the readiness rules make true - checked against review.readiness and review._review_state
  on the pipeline's own cases: a question about the encounter holds the reviewed report; a question about a code holds
  that code, which can still be rejected; a question about a documented service no code carries holds neither.
  (Superseded, round 5: the row only counts - how many questions are open and what each is about, the session's D11,
  tests/test_harness2_r5_row.py - so the row pins below are moved to that; what each question holds is pinned on
  review.readiness and review._review_state, as before.)
- d7-4: the reports print CONFIRMED FINDINGS only while confirmations are offered.
- d7-5: the engine's participants.summary says of a participant's peer answers what is true in both modes.
- falsegreen-7 and falsegreen-4: tests/test_harness2_api.py's Harness2Case - whose rows the API tests pin and the
  website fixtures serialize - records the participants entries and the reconciliation retrieval the assess stage
  records, and the committed fixtures serve no reconciliation fact or passage beside a Reference validation row that
  says none was checked.

Each test failed on the base 3daafa91b. Synthetic data only; nothing is sent: Corti is the harness@1 suite's in-process
fake, Astra and Fable the real replay adapters on the real tool loop (tests.test_harness2_pipeline) or the recorded rows
of tests.test_harness2_api.
"""
import re
from contextlib import ExitStack
from html import unescape
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.test import SimpleTestCase, override_settings

from studio import jobs, models, reports, review
from studio.types import sha256_json
from tests import test_harness2_api as h2
from tests.test_frontend import HARNESS2_SCENARIOS, _fixture
from tests.test_harness2_pipeline import EMPTY_PEER, HEAD, TWO_EXTENTS, ColonCase, answered, reading
from tests.test_harness2_pipeline import Harness2Case as PipelineCase
from tests.test_harness2_r2_evidence import NO_BASIS, PRIOR, VISIT, page
from tests.test_participants_support import code as code_item, empty_reading, service as service_item
from tests.test_pipeline_api import drain

ROOT = Path(settings.BASE_DIR)
DORMANT = dict(STUDIO_OFFER_CONFIRMATIONS=True)  # the dormant confirmation path, as its own tests run it
# The refusal, written out here: what happened, and no way a question is settled (d7-3).
NOT_OFFERED = 'This release offers no reviewer confirmation, so nothing was recorded.'
# What the page drew for a located passage in round 3 (D7), none of which a page may now say.
LOCATED_WORDS = ('candidate-answers', 'Their answer', 'located passages', 'located for this question', 'Located by',
                 'An answer CPT Studio cannot restate', 'confirm-finding', '<span class="status green">Verified</span>')
# Every reader a served candidate came from, none of which runs for the response while confirmations are not offered.
READERS = ('studio.review.frozen_inputs', 'studio.review.peer_answers', 'studio.review.recorded_inventory',
           'studio.candidates.candidates', 'studio.candidates._reading_sources', 'studio.candidates._answer_sources',
           'studio.candidates._basis_stated', 'studio.validation.reconcile.status_stated')
NOTE = "A participant's own questions never hold the reviewed report."


def clarification_row(html):
    """The Clarification row of the Review participants card as a reader sees it: (its lines, its notes)."""
    at = html.index('data-participant="clarification"')
    start = html.rindex('<div class="check-item', 0, at)
    end = html.find('<div class="check-item', at)
    row = html[start:end if end > 0 else len(html)]
    return ([unescape(line) for line in re.findall(r'<p>(.*?)</p>', row)],
            [unescape(note) for note in re.findall(r'<small class="check-source">(.*?)</small>', row)])


def membership_of(user, workspace):
    return models.Membership.objects.get(user=user, workspace=workspace)


def reject_selected(encounter, assessment, user, workspace):
    for proposal in assessment.proposals.filter(bucket='selected'):
        review.record_decision(encounter=encounter, proposal=proposal, action='reject', user=user,
                               membership=membership_of(user, workspace), note='Synthetic rejection.')


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
                data = self.client_for(user).get(f'/ops/api/encounters/{self.encounter.pk}').json()
                self.assertIs(data['permissions']['can_confirm'], False)
                self.assertEqual(sum(c['state'] == 'open' for c in data['clarifications']), 4)
                self.assertEqual([(c['candidates'], c['confirmation']) for c in data['clarifications']],
                                 [([], None)] * len(data['clarifications']))
        # the control: on the dormant path a member who may confirm is served the candidates; a member who may not is
        # served none (candidates go only to a member who may confirm one)
        with override_settings(**DORMANT):
            served = {user: self.client_for(user).get(f'/ops/api/encounters/{self.encounter.pk}').json()
                      for user in (self.reviewer, self.viewer)}
        reviewer, viewer = served[self.reviewer], served[self.viewer]
        self.assertIs(reviewer['permissions']['can_confirm'], True)
        self.assertTrue(all(c['candidates'] for c in reviewer['clarifications'] if c['state'] == 'open'))
        self.assertIs(viewer['permissions']['can_confirm'], False)
        self.assertEqual([c['candidates'] for c in viewer['clarifications']], [[]] * len(viewer['clarifications']))

    def test_the_page_draws_no_candidate_and_no_answer_it_attributes_to_a_participant(self):
        detail = self.client_for(self.owner).get(f'/ops/api/encounters/{self.encounter.pk}').json()
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
        detail = self.client.get(f'/ops/api/encounters/{encounter_id}').json()
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


# --- d7-3: no sentence names a way a question is settled --------------------------------------------------------------

class RefusalTests(SimpleTestCase):
    def test_the_refusal_says_only_what_happened(self):
        self.assertEqual(review.CONFIRMATIONS_NOT_OFFERED, NOT_OFFERED)
        # the dev preview server refuses a confirmation with the same sentence
        source = (ROOT / 'ops' / 'dev_preview_server.cjs').read_text(encoding='utf-8')
        self.assertIn(f"const CONFIRMATIONS_NOT_OFFERED = '{NOT_OFFERED}';", source)


@override_settings(**h2.BOTH)
class EncounterQuestionTests(h2.Harness2Case):
    """The case's final assessment: the date of service (a question about the encounter) and three questions about
    its two codes."""

    def test_the_clarification_row_counts_and_the_readiness_rules_say_what_each_question_holds(self):
        detail = self.client_for(self.reviewer).get(f'/ops/api/encounters/{self.encounter.pk}').json()
        # moved by refutation round 5 (R5-ROW, the session's D11; renamed from "..._row_says_what_the_readiness_rules_
        # make_true"): the row says only how many questions are open and what each is about; what each holds is the
        # readiness rules' to say, pinned below as before
        self.assertEqual(clarification_row(page(detail)), (
            ['One open question is about the encounter.', '3 open questions are each about a code.'], [NOTE]))
        membership = membership_of(self.reviewer, self.ws)
        held = {q.proposal for q in self.final.clarifications.filter(state='open', proposal__isnull=False)}
        self.assertEqual(sorted(p.code for p in held), ['45380', '45385'])
        blockers = review.readiness(self.encounter)['blockers']
        for proposal in held:  # each code with an open question: held, and it can still be rejected
            self.assertEqual((proposal.status, review.allowed_actions(proposal, self.final, membership)),
                             ('needs_clarification', ['reject']))
            self.assertIn(f'{proposal.code} has an open clarification', blockers)
        # once every code is rejected, the question about the encounter still holds the reviewed report
        reject_selected(self.encounter, self.final, self.reviewer, self.ws)
        ready = review.readiness(self.encounter)
        self.assertEqual((ready['reviewed'], ready['blockers']), (False, ['Open clarification: service date']))
        self.assertEqual(review._review_state(self.encounter, self.final), 'needs_clarification')


class CodeQuestionTests(ColonCase):
    """Two colonoscopy codes Corti selects on a note with no extent reached, and 45378 Fable's peer review adds: four
    questions, each about a code; none about the encounter. Moved by refutation round 6 (R6-MEANING, the session's D14):
    the 45378 Fable's peer review adds is its alternative, never a proposal, so two questions, each about one of Corti's
    codes."""

    def test_a_question_about_a_code_holds_that_code_which_can_still_be_rejected(self):
        encounter_id = self.create(TWO_EXTENTS)
        drain()
        encounter = self.encounter(encounter_id)
        final = encounter.current_assessment
        detail = self.client.get(f'/ops/api/encounters/{encounter_id}').json()
        # moved by refutation round 5 (R5-ROW, the session's D11): the row says only how many questions are open and
        # what each is about; that each holds its code, which can still be rejected, is the readiness rules', pinned
        # below as before (and the row after the rejections in tests/test_harness2_r5_row.py)
        self.assertEqual(clarification_row(page(detail)), (['2 open questions are each about a code.'], [NOTE]))
        membership = membership_of(self.reviewer, self.ws)
        held = {q.proposal for q in final.clarifications.filter(state='open')}
        self.assertNotIn(None, held)
        for proposal in held:
            self.assertEqual((proposal.status, review.allowed_actions(proposal, final, membership)),
                             ('needs_clarification', ['reject']))
        self.assertEqual(review._review_state(encounter, final), 'needs_clarification')
        # rejecting each code releases the reviewed report: no question held anything but its code
        reject_selected(encounter, final, self.reviewer, self.ws)
        self.assertTrue(final.clarifications.filter(state='open').exists())
        self.assertEqual(review.readiness(encounter), {'draft': True, 'reviewed': True, 'blockers': []})
        self.assertEqual(review._review_state(self.encounter(encounter_id), final), 'reviewed')


EGD_AND_COLON = (HEAD + 'Procedure report (fictional)\nDate of service: 2026-10-14\n'
                 'Place of service: Ambulatory surgery center\nProcedures: Upper endoscopy and colonoscopy\n'
                 'An upper endoscopy was performed.\n'
                 'The colonoscope was advanced to the cecum and the examination was completed.\n'
                 'A 9 mm pedunculated polyp in the sigmoid colon was removed with a hot snare.\n')


class ServiceQuestionTests(PipelineCase):
    """A documented upper endoscopy with no extent, which no code carries, beside a colonoscopy code: the readers ask
    its extent as a question about the service, which holds neither a code nor the reviewed report."""
    corti_codes = (('45385', 'was removed with a hot snare'),)

    def test_a_question_about_a_service_no_code_carries_holds_neither(self):
        both = reading(codes=[('45385', 'was removed with a hot snare')],
                       services=[('c1', 'colonoscopy', 'performed', 'was removed with a hot snare')])
        for name in ('astra', 'fable'):
            self.adapters[name].first = [answered(name, both)]
            self.adapters[name].peer = [answered(name, EMPTY_PEER, number=2)]
        encounter_id = self.create(EGD_AND_COLON)
        drain()
        encounter = self.encounter(encounter_id)
        final = encounter.current_assessment
        self.assertEqual([(q.scope, q.fact, q.proposal_id) for q in final.clarifications.filter(state='open')],
                         [('service', 'extent', None)])
        detail = self.client.get(f'/ops/api/encounters/{encounter_id}').json()
        # moved by refutation round 5 (R5-ROW, the session's D11): the row says only how many questions are open and
        # what each is about; that this one holds neither a code nor the reviewed report is the readiness rules', pinned
        # below as before (and a service a code carries in tests/test_harness2_r5_row.py)
        self.assertEqual(clarification_row(page(detail)),
                         (['One open question is about a documented service.'], [NOTE]))
        (snare,) = final.proposals.filter(bucket='selected')
        self.assertEqual((snare.code, snare.status), ('45385', 'ready'))
        self.assertIn('approve', review.allowed_actions(snare, final, membership_of(self.reviewer, self.ws)))
        self.assertEqual(review.readiness(encounter)['blockers'], ['45385 has no decision'])
        reject_selected(encounter, final, self.reviewer, self.ws)
        self.assertEqual(review.readiness(encounter), {'draft': True, 'reviewed': True, 'blockers': []})
        self.assertEqual(review._review_state(self.encounter(encounter_id), final), 'reviewed')


# --- d7-4, d7-5: no confirmation wording where none is offered --------------------------------------------------------

@override_settings(**h2.BOTH)
class ConfirmationWordingTests(h2.Harness2Case):
    def txt(self):
        return reports.render_txt(reports.snapshot(self.encounter, 'draft')).decode('utf-8')

    def test_the_reports_print_no_confirmed_findings_section(self):
        snap = reports.snapshot(self.encounter, 'draft')
        self.assertNotIn('confirmed_findings', snap)
        text = reports.render_txt(snap).decode('utf-8')
        self.assertNotIn('\nCONFIRMED FINDINGS\n', text)
        self.assertNotIn('no reviewer has confirmed a finding', text)
        self.assertNotIn('confirmed_finding', reports.render_csv(snap).decode('utf-8'))
        # the control: the dormant path prints it
        with override_settings(**DORMANT):
            self.assertIn('\nCONFIRMED FINDINGS\n  None: no reviewer has confirmed a finding for this revision.\n',
                          self.txt())

    def test_the_summary_says_what_a_peer_answer_is_in_either_mode(self):
        (summary,) = [c['detail'] for c in self.final.encounter_checks if c['id'] == 'participants.summary']
        said = 'an answer is recorded and decides nothing by itself.'
        self.assertIn(f'It answered 3 open questions; {said}', summary)  # Astra
        self.assertIn(f'It answered 1 open question; {said}', summary)  # Fable
        self.assertNotIn('confirm', summary)
        text = self.txt()
        self.assertEqual(text.count(said), 2)
        self.assertNotIn('reviewer confirms', text)
        # the engine reads no setting: the dormant path's assessment of the same rows says the same
        with override_settings(**DORMANT):
            self.assertEqual(sha256_json(self.result(2)), self.final.sha256)


# --- falsegreen-7, falsegreen-4: the case's and the fixtures' rows are the assess stage's -----------------------------

@override_settings(**h2.BOTH)
class CaseRowsTests(h2.Harness2Case):
    def test_the_participants_entries_and_the_retrieval_are_the_stage_s(self):
        # assess #1, made by the real assess stage from the case's own stored rows
        job = jobs.enqueue(models.Job.ASSESS, encounter=self.encounter, revision=self.revision, context=self.context,
                           provider_run=self.corti, requested_by=self.reviewer,
                           key=jobs._assess_key(f'assess:{self.context.pk}:{self.corti.pk}', self.revision))
        self.assertEqual(jobs.claim_next(), job)
        job.refresh_from_db()
        jobs.run_job(job)
        job.refresh_from_db()
        self.assertEqual(job.state, models.Job.SUCCEEDED, job.error)
        made = models.Assessment.objects.get(pk=job.result['assessment'])
        self.assertEqual(made.sha256, self.first.sha256)
        self.assertEqual(made.participants, self.first.participants)
        self.assertEqual(made.retrieval, self.first.retrieval)
        # assess #2's entries, as the stage records them: each first reading's record with its peer review's, and the
        # frozen list
        records = []
        for name in h2.ADAPTERS:
            item, record = jobs._first_input(self.encounter, name, self.runs[name])
            records.append(jobs._with_peer(self.encounter, item, record, self.peer_runs[name])[1])
        frozen = jobs._frozen(self.revision, self.corti, {record['name']: record for record in records})
        self.assertEqual(self.final.participants, [{**record, 'frozen': frozen} for record in records])
        # so each participant's position on 45385 is its own located quote, never "none of its quotes was found"
        detail = self.client_for(self.reviewer).get(f'/ops/api/encounters/{self.encounter.pk}').json()
        snare = next(p for p in detail['assessment']['proposals'] if p['code'] == '45385' and p['bucket'] == 'selected')
        positions = snare['participant_positions']
        self.assertEqual({name: (item['position'], item['quote']) for name, item in positions.items()},
                         {name: ('proposed', 'was removed with a cold snare') for name in h2.ADAPTERS})


class FixtureRetrievalTests(SimpleTestCase):
    def test_no_fixture_serves_a_reconciliation_fact_beside_a_row_that_says_none_was_checked(self):
        checked = 0
        for name in HARNESS2_SCENARIOS:
            doc = _fixture(name)
            reference = doc['harness']['reference_validation']
            if reference['state'] == 'waiting':  # processing: no retrieval is stated yet
                continue
            with self.subTest(name):
                self.assertEqual(reference['state'], 'not_verified')
                self.assertEqual((reference['codes_checked'], reference['passages'], reference['sources']), (0, 0, []))
                self.assertEqual([item for p in doc['assessment']['proposals'] for item in p['retrieval']], [])
                checked += 1
        self.assertEqual(checked, 3)
        # the trace's reconciliation retrieval is the stage's for a document with no service date: each code looked up
        # on an unknown date, nothing applied. Moved by refutation round 8 (retrieval-1, retrieval-2): an alternative's
        # code is never traced, and 45381 is a participant's alternative in this fixture (it was ('45380', '45381',
        # '45385'): the builder passes jobs._retrieval the prefetched codes, the participants' among them)
        trace = _fixture('trace-harness2-final.json')
        self.assertEqual([(e['code'], e['service_date'], e['facts'], e['passages']) for e in trace['retrieval']],
                         [(code, None, [], []) for code in ('45380', '45385')])
        self.assertTrue(all('Service date unknown; dated references cannot be applied.' in e['notes']
                            for e in trace['retrieval']))
