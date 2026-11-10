"""Refutation round 5, R5-ACCOUNT (the session's decisions D10, D12 and D13; HARNESS.md 5, 7, 11.1, 12.4, 12.6, 12.10,
12.12; I4, I9): one account of what a model participant did, on every surface - the page, the API, the owner's trace
and both reports - and no surface that turns CPT Studio's own reading of a participant's words into its answer.

- d8-2 (D10): the reports printed a peer answer as CPT Studio's reading of the participant's free text
  (candidates.canonical_value), so 'Cannulation of the bile duct was not successful.' was printed "successful", beside
  the participant's own passage 'Biliary cannulation was unsuccessful.'. They now print each answer only by whether it
  is read as settling the question, with the passages it located, and no value; no release-default path reads a
  participant's value with a candidate reader (pinned here by making every one of them raise).
- truth-1, truth-2, truth-3 (D12): "proposed" is said only of an entry with a located quote. A participant-origin
  alternative names as its proposers only the participants whose entries located the code (support['proposed_by'],
  support['phases']); one that gave the code with no quote found verbatim is recorded apart as having listed it
  (support['listed_by']) and every surface says so. A peer review's additional code that no entry of either phase
  located is "listed in peer review", never "repeated" or "proposed after peer review".
- shapes-1, truth-7: a peer review's position on an HCPCS code, and an HCPCS code it adds, are codes CPT Studio reads
  (participants.peer.code_shaped, the engine's rule), in the API, the trace and both reports.
- truth-6, shapes-2 (D13): a participant row counts the codes that cannot be listed as the engine does - every entry of
  the frozen reading, re-read when serving - and states no count where that reading cannot be read again.
- d8-3: participants.summary counts the open questions a peer review answered, and its answers apart when it answered
  one more than once.
- falsegreen-1, -2, -4, -5: what the round-4 tests let through - the HCPCS half of a code's shape, Corti's own unlisted
  rule beside D9's, the unread-position sentences written out, and the engine's position of a first reading's unlocated
  code that its peer review then proposed.

Each pipeline class runs the real pipeline (tests.test_harness2_pipeline: the real jobs, loop, tool executor, readers
and engine, the vendors' HTTP replaced by scripted bytes in their own envelopes), then the real API, the owner's trace,
the reports through the reports endpoint and the real app.js under node. Synthetic data only; nothing is sent.
"""
import csv
import io
import json
import re
from unittest import mock

from django.db import connection
from django.test import Client, SimpleTestCase, override_settings

from studio import candidates, jobs, models, reports, review, serializers
from studio.participants import peer
from studio.types import QuestionAnswer
from studio.validation import engine
from tests import test_harness2_pipeline as hp
from tests import test_harness_engine as he
from tests.legacy_chain import applied
from tests.support import factories as f
from tests.test_harness2_pipeline import BIOPSY, LAND, SNARE, TWO_EXTENTS
from tests.test_harness2_r2_wording import R2WordingCase, browser
from tests.test_harness2_r4_truth import LATER, LISTED, UNLOCATED, _block, _corti_item, _section
from tests.test_participants_support import code, empty_reading, service
from tests.test_pipeline_api import drain

UNLOCATED_DIAG = 'the colonoscope was advanced to the cecum without any difficulty'  # in no document: never located
LISTED_WORDS = 'with no quote found verbatim in the document, so not proposed'
UNLOCATED_WHY = ('none of its quotes was found verbatim in the document text, and a quote that is not found is never '
                 'evidence')
HCPCS_WHY = 'HCPCS Level II code — CPT-only results'
LES = 'W/LES(S)'  # 8 characters in no code's shape: Corti's own rule lists it (I1), a participant's is counted (D9)


def csv_rows(text):
    return list(csv.DictReader(io.StringIO(text)))


def length(text):
    return f'a value of {len(text):,} character{"" if len(text) == 1 else "s"} (not shown)'


def unlisted_counts(text):
    """Every count a sentence states of codes that cannot be listed ('It returned 2 codes that cannot be listed')."""
    return [int(n) for n in re.findall(r'returned (\d+) codes? that cannot be listed', text)]


class Surfaces:
    """What one encounter shows, collected the same way for every class: the API detail (a reviewer), the owner's
    trace, both reports through the reports endpoint, and the page and the trace as app.js draws them."""

    def owner(self):
        if not hasattr(self, '_owner_client'):
            self._owner_client = Client()
            self._owner_client.force_login(f.member(self.ws, f.user('owner-r5account'),
                                                    role=models.Membership.OWNER))
        return self._owner_client

    def trace(self, encounter_id):
        response = self.owner().get(f'/ops/api/encounters/{encounter_id}/trace')
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()

    def download(self, encounter_id, kind='draft', fmt='txt'):
        made = self.post(f'/ops/api/encounters/{encounter_id}/reports', {'kind': kind, 'fmt': fmt})
        self.assertEqual(made.status_code, 201, made.content)
        got = self.client.get(made.json()['download_url'])
        self.assertEqual(got.status_code, 200)
        return b''.join(got.streaming_content if got.streaming else [got.content]).decode('utf-8')

    def rows(self, detail):
        return {row['name']: row for row in detail['harness']['participants']}

    def summary(self, detail):
        (check,) = [c for c in detail['assessment']['encounter_checks'] if c['id'] == 'participants.summary']
        return check['detail']

    @staticmethod
    def page_lines(detail, tab='codes'):
        return browser(f'visible(page({json.dumps(tab)})).split("\\n")', detail)

    @staticmethod
    def trace_lines(trace):
        return browser('visible(app.traceView(data)).split("\\n")', trace)

    @staticmethod
    def peer_row(detail, name):
        return browser(f'rowOf(page(), "data-peer", {json.dumps(name)})', detail)


# --- d8-2 (D10): a peer answer is printed as the participant's claim, never as CPT Studio's reading of its value -----

STENT = 'A plastic stent was placed.'
DONE_C = 'Deep biliary cannulation was achieved.'
FAILED_C = 'Biliary cannulation was unsuccessful.'
ERCP_DOC = (hp.HEAD + 'Procedure note (fictional)\nDate of service: 2026-10-14\nPlace of service: Hospital outpatient\n'
            'Procedure: ERCP\nThe duodenoscope was advanced to the major papilla.\n' + DONE_C + '\n' + FAILED_C + '\n'
            + STENT + '\n')
FAILED_ANSWER = 'Cannulation of the bile duct was not successful.'
QUESTION = 'ERCP: confirm whether, and which, duct was cannulated.'
SUCCESS = re.compile(r'(?<![A-Za-z])successful')  # the outcome word, never inside 'unsuccessful'
ANSWER_LINE = f'    Answer to "{QUESTION}" (cannulation outcome): '
# Every reader studio.candidates has of a participant's value or passage, and the candidates it builds from them: none is
# called at the release default (refutation round 5, D10; D8 removed them from the page, D7 from every confirmation).
CANDIDATE_READERS = ('canonical_value', 'candidates', '_reading_sources', '_answer_sources', '_date_value',
                     '_status_value', '_landmark_value', '_target_value', '_cannulation_value', '_basis_value',
                     '_basis_stated', 'landmarks_named', 'targets_named', '_why', '_inconsistent', '_qualified',
                     '_candidate')


def answers_cannulation(name, *answers, number=2):
    """``name``'s peer review answering the one open cannulation question with each of ``answers`` (settled, value,
    quote)."""
    def answer(body):
        (question,) = [q for q in hp.open_questions(name, body) if q['fact'] == 'cannulation']
        return hp.answered(name, hp.peer_answer(answers=[(question['question_id'], settled, value, quote)
                                                         for settled, value, quote in answers]), number)
    return answer


class ErcpCase(Surfaces, hp.Harness2Case):
    """The d8 lens's ERCP note: both cannulation outcomes are documented, so CPT Studio's readers ask the cannulation
    question on 43274 (Corti's code on the stent line). Both first readings propose 43274; Fable's peer review is
    empty and Astra's answers the question as a test scripts it."""
    corti_codes = (('43274', STENT),)

    def setUp(self):
        super().setUp()
        both = hp.reading(codes=[('43274', STENT)], services=[('e1', 'ercp', 'performed', STENT)])
        for name in ('astra', 'fable'):
            self.adapters[name].first = [hp.answered(name, both)]
        self.adapters['fable'].peer = [hp.answered('fable', hp.EMPTY_PEER, number=2)]

    def chain(self, *answers):
        self.adapters['astra'].peer = [answers_cannulation('astra', *answers)]
        encounter_id = self.create(ERCP_DOC)
        drain()
        final = self.encounter(encounter_id).current_assessment
        self.assertEqual((review.assessment_phase(final), review.is_final(final)), (2, True))
        return encounter_id

    def all_reports(self, encounter_id):
        """{(kind, fmt): text}: the draft, then - 43274 rejected, which lifts its question's hold - the reviewed report,
        each downloaded through the reports endpoint."""
        files = {('draft', fmt): self.download(encounter_id, 'draft', fmt) for fmt in ('txt', 'csv')}
        (stent,) = self.encounter(encounter_id).current_assessment.proposals.filter(bucket='selected')
        decided = self.post(f'/api/encounters/{encounter_id}/decisions',
                            {'proposal_id': str(stent.pk), 'action': 'reject', 'note': 'Synthetic rejection.'})
        self.assertEqual(decided.status_code, 201, decided.content)
        files.update({('reviewed', fmt): self.download(encounter_id, 'reviewed', fmt) for fmt in ('txt', 'csv')})
        return files

    @staticmethod
    def peer_answer_rows(text):
        return [row for row in csv_rows(text) if row['item_list'] == 'peer_answer']


@applied
class PeerAnswerReportTests(ErcpCase):
    """d8-2: Astra answers the open cannulation question 'Cannulation of the bile duct was not successful.', quoting
    'Biliary cannulation was unsuccessful.'. Both reports printed 'Answer to "...": successful' and a CSV peer_answer
    row with 'successful', CPT Studio's own reading of that answer, inverted (refutation round 5, d8-2, major)."""

    def test_a_negated_answer_is_never_printed_as_its_opposite_in_either_report(self):
        self.assertIs(review.confirmations_offered(), False)  # the release default
        encounter_id = self.chain((True, FAILED_ANSWER, FAILED_C))
        # the record keeps Astra's own words, and CPT Studio's dormant reader inverts them (recorded, not repaired: D10)
        (peer_run,) = self.runs_of(encounter_id, 'astra', 'peer_review')
        (answer,) = jobs.peer_reading(peer_run)[0].answers
        self.assertEqual((answer.settled, answer.value), (True, FAILED_ANSWER))
        self.assertEqual(candidates.canonical_value('cannulation', 'gi.ercp', FAILED_ANSWER)[0], 'successful')
        files = self.all_reports(encounter_id)
        for (kind, fmt), text in files.items():
            with self.subTest(kind=kind, fmt=fmt):
                self.assertNotIn(FAILED_ANSWER, text)  # no value at all: not the participant's words either
                if fmt == 'txt':
                    lines = _block(_section(text, reports.PEER_TITLE), '  - Astra · ')
                    self.assertIn(ANSWER_LINE + 'Astra says the document settles it', lines)
                    self.assertTrue(any(line.startswith(f'      "{FAILED_C}" [chars ') for line in lines), lines)
                    self.assertEqual([line for line in _section(text, reports.PEER_TITLE) if SUCCESS.search(line)],
                                     [])
                else:
                    rows = self.peer_answer_rows(text)
                    self.assertEqual([(row['proposed_by'], row['status'], row['exclusion_reason']) for row in rows],
                                     [('astra', 'settled', '')])
                    self.assertTrue(rows[0]['evidence'].startswith(f'"{FAILED_C}" ['), rows[0]['evidence'])
                    self.assertTrue(rows[0]['checks'].endswith(';fact=cannulation'), rows[0]['checks'])
        # the participant's own words stay where the release shows them: the owner's trace
        answers = [run['review']['answers'] for item in self.trace(encounter_id)['participants']
                   for run in item['runs'] if run.get('review') and item['name'] == 'astra']
        self.assertEqual([[(a['settled'], a['value']) for a in each] for each in answers], [[(True, FAILED_ANSWER)]])

    def test_an_answer_read_as_not_settling_the_question_says_so_and_no_more(self):
        encounter_id = self.chain((False, '', FAILED_C))
        text = self.download(encounter_id, 'draft', 'txt')
        lines = _block(_section(text, reports.PEER_TITLE), '  - Astra · ')
        self.assertIn(ANSWER_LINE + "Astra's answer is read as not settling it", lines)
        self.assertNotIn('not settled by the document', text)  # CPT Studio says nothing of the document itself
        (row,) = self.peer_answer_rows(self.download(encounter_id, 'draft', 'csv'))
        self.assertEqual((row['status'], row['exclusion_reason']), ('not_settled', ''))

    def test_no_release_default_path_reads_a_participant_s_value_with_a_candidate_reader(self):
        # every candidate reader raises: the pipeline, the API (a reviewer and the owner), the page and both reports
        # in both kinds run at the release default without calling one
        readers = {name: mock.Mock(side_effect=AssertionError(f'candidates.{name} was called')) for name in
                   CANDIDATE_READERS}
        with mock.patch.multiple(candidates, **readers):
            encounter_id = self.chain((True, FAILED_ANSWER, FAILED_C))
            self.assertEqual({job.state for job in self.jobs_of(encounter_id)}, {models.Job.SUCCEEDED})
            detail = self.client.get(f'/ops/api/encounters/{encounter_id}')
            self.assertEqual(detail.status_code, 200, detail.content)
            questions = detail.json()['clarifications']
            self.assertTrue(questions)
            self.assertEqual([c['candidates'] for c in questions], [[]] * len(questions))
            self.page_lines(detail.json())
            self.trace(encounter_id)
            self.assertEqual(len(self.all_reports(encounter_id)), 4)
            self.assertEqual({name: reader.call_count for name, reader in readers.items()},
                             dict.fromkeys(CANDIDATE_READERS, 0))
            # the positive control: the dormant path does call them, so a patched reader would have been seen
            with override_settings(STUDIO_OFFER_CONFIRMATIONS=True):
                with self.assertRaises(AssertionError):
                    review.assessment_candidates(self.encounter(encounter_id).current_assessment)
            self.assertEqual(readers['candidates'].call_count, 1)


# --- d8-3: the open questions answered are counted as questions --------------------------------------------------------

ANSWERED_TWICE = 'It gave 2 answers to 1 open question; an answer is recorded and decides nothing by itself.'
ANSWERED_ONCE = 'It answered 1 open question; an answer is recorded and decides nothing by itself.'


@applied
class AnsweredQuestionCountTests(ErcpCase):
    """d8-3: one open question, answered twice in one peer review (the reader keeps both and notes the repeat): the
    summary said "It answered 2 open questions"."""

    def test_two_answers_to_one_question_are_two_answers_to_one_question(self):
        encounter_id = self.chain((True, 'Biliary cannulation failed.', FAILED_C), (True, 'successful', DONE_C))
        first = self.assessments(encounter_id)[0]
        self.assertEqual(first.clarifications.filter(state=models.Clarification.OPEN, fact='cannulation').count(), 1)
        summary = self.summary(self.client.get(f'/ops/api/encounters/{encounter_id}').json())
        self.assertIn(ANSWERED_TWICE, summary)
        self.assertNotIn('2 open questions', summary)
        # and the reports print each answer as the participant's claim, neither value (D10)
        text = self.download(encounter_id, 'draft', 'txt')
        lines = _block(_section(text, reports.PEER_TITLE), '  - Astra · ')
        self.assertEqual(lines.count(ANSWER_LINE + 'Astra says the document settles it'), 2)
        self.assertEqual([line for line in lines if SUCCESS.search(line) or 'failed' in line], [])

    def test_one_answer_to_one_question_reads_as_before(self):
        encounter_id = self.chain((True, FAILED_ANSWER, FAILED_C))
        self.assertIn(ANSWERED_ONCE, self.summary(self.client.get(f'/ops/api/encounters/{encounter_id}').json()))


class AnsweredQuestionEngineTests(SimpleTestCase):
    """d8-3 in the engine: answers counted by the distinct question ids they answer."""

    def summary_of(self, *question_ids):
        colon = he.COLON
        answers = [QuestionAnswer(question_id, True, 'cecum', (he.located(colon, he.CECUM),))
                   for question_id in question_ids]
        given = he.reviewed('astra', [he.code(colon, '45385', he.SNARE)], he.peer('astra', answers=answers))
        result = he.run(colon, he.corti(('45385', he.span(colon, he.SNARE))), [given])
        return he.encounter_check(result, 'participants.summary').detail

    def test_answers_are_counted_by_the_questions_they_answer(self):
        self.assertIn(ANSWERED_TWICE, self.summary_of('q-1', 'q-1'))
        self.assertIn('It answered 2 open questions; ', self.summary_of('q-1', 'q-2'))
        self.assertIn('It gave 3 answers to 2 open questions; ', self.summary_of('q-1', 'q-2', 'q-1'))
        self.assertIn(ANSWERED_ONCE, self.summary_of('q-1'))


# --- D12 (truth-1, truth-2, truth-3): "proposed" only of an entry with a located quote ---------------------------------

@applied
class AlternativeAccountTests(Surfaces, R2WordingCase):
    """A participant-origin alternative named every participant that gave the code as its proposer - "Proposed by Astra
    (independent participant), but not added as a proposal: none of its quotes was found verbatim ..." - beside the
    same assessment's "It listed 1 code (45378) with no quote found verbatim in the document, so it did not propose it"
    (refutation round 5, truth-1, truth-3; round 4's truth-2 applied EV-2 = IND-3 to the cards, the row, the engine's
    position and the summary only)."""

    def test_an_alternative_no_participant_located_names_no_proposer_on_any_surface(self):
        # truth-1: Astra's first reading lists 45378 with a quote no document holds; nobody else lists it
        self.adapters['astra'].first = [hp.answered('astra', hp.reading(
            codes=[('45385', SNARE), ('45380', BIOPSY), ('45378', UNLOCATED_DIAG)],
            services=[('c1', 'colonoscopy', 'performed', SNARE)]))]
        self.adapters['fable'].peer = [hp.answered('fable', hp.peer_answer(), number=2)]
        encounter_id = self.create(TWO_EXTENTS)
        drain()
        self.assertIn({'code': '45378', 'quote': ''},
                      self.records(self.encounter(encounter_id).current_assessment)['astra']['codes'])
        detail = self.detail(encounter_id)
        [alternative] = self.proposals(detail, '45378')
        reason = (f'Listed by Astra {LISTED_WORDS}, and not added as a proposal: {UNLOCATED_WHY}. Alternatives cannot be '
                  'approved.')
        self.assertEqual((alternative['bucket'], alternative['proposed_by'], alternative['phases'],
                          alternative['listed_by'], alternative['support']['listed_by']),
                         ('alternative', [], {}, ['astra'], ['astra']))
        self.assertNotIn('phases', alternative['support'])
        self.assertEqual((alternative['exclusion_reason'], alternative['rationale']),
                         (reason, f'Listed by Astra {LISTED_WORDS}; not added as a proposal: {UNLOCATED_WHY}. '
                                  'Informational only.'))
        self.assertEqual(alternative['support']['participants']['astra']['position'], 'not_proposed')
        self.assertIn('It listed 1 code (45378) with no quote found verbatim in the document, so it did not propose '
                      'it.', self.summary(detail))
        # the page's Alternatives
        page = self.page_lines(detail)
        self.assertEqual(page[page.index('45378 · Colonoscopy') + 1], reason)
        self.assertFalse([line for line in page if 'Proposed by Astra' in line])
        # both reports
        txt = self.download(encounter_id)
        self.assertEqual(_block(_section(txt, reports.ALTERNATIVES_TITLE), '  - 45378 · '),
                         [f'  - 45378 · Colonoscopy — listed by Astra {LISTED_WORDS}, never selectable: {reason}',
                          f'     Proposed by: no participant; listed by Astra {LISTED_WORDS}'])
        rows = [row for row in csv_rows(self.download(encounter_id, fmt='csv')) if row['code'] == '45378']
        self.assertEqual([(row['item_list'], row['proposal_origin'], row['proposed_by'], row['exclusion_reason'])
                          for row in rows], [('alternative', 'participant', '', reason)])
        # the owner's trace
        trace = self.trace(encounter_id)
        (row,) = [item for item in trace['reconciliation'] if item['code'] == '45378']
        self.assertEqual((row['proposed_by'], row['listed_by']), ([], ['astra']))
        trace_page = self.trace_lines(trace)
        self.assertIn(f'Proposed by: no participant; listed by Astra {LISTED_WORDS}', trace_page)
        for where, text in (('page', '\n'.join(page)), ('txt', txt), ('trace', '\n'.join(trace_page))):
            self.assertNotIn('Proposed by: not recorded', text, where)

    def test_an_alternative_one_participant_located_and_another_listed_names_each_for_what_it_did(self):
        # Astra locates G0121 (an HCPCS code: out of scope, so an alternative); Fable lists it with an unfound quote
        self.adapters['astra'].first = [hp.answered('astra', hp.reading(
            codes=[('45385', SNARE), ('45380', BIOPSY), ('G0121', LAND)],
            services=[('c1', 'colonoscopy', 'performed', SNARE)]))]
        self.adapters['fable'].first = [hp.answered('fable', hp.reading(
            codes=[('45385', SNARE), ('G0121', UNLOCATED_DIAG)], services=[('c1', 'colonoscopy', 'performed', SNARE)]))]
        encounter_id = self.create(TWO_EXTENTS)
        drain()
        detail = self.detail(encounter_id)
        [alternative] = self.proposals(detail, 'G0121')
        apart = f'Listed by Fable {LISTED_WORDS} by Fable.'
        reason = (f'Proposed by Astra (independent participant), but not added as a proposal: {HCPCS_WHY}. {apart} '
                  'Alternatives cannot be approved.')
        self.assertEqual((alternative['proposed_by'], alternative['phases'], alternative['listed_by'],
                          alternative['exclusion_reason']), (['astra'], {'astra': 'independent'}, ['fable'], reason))
        # moved by refutation round 7 (display-5): a participant's verbatim quote is never called an evidence passage
        # (it was 'Informational only. 1 exact evidence passage.')
        self.assertEqual(alternative['rationale'],
                         f'Proposed by Astra (independent participant); not added as a proposal: {HCPCS_WHY}. {apart} '
                         'Informational only. 1 passage of the document quoted verbatim.')
        txt = self.download(encounter_id)
        self.assertEqual(_block(_section(txt, reports.ALTERNATIVES_TITLE), '  - G0121 · '), [
            f'  - G0121 · Service outside the GI profiles — proposed by Astra, not added as a proposal; listed by Fable '
            f'{LISTED_WORDS} by Fable, never selectable: {reason}',
            f'     Proposed by: Astra; listed by Fable {LISTED_WORDS} by Fable'])
        (row,) = [item for item in self.trace(encounter_id)['reconciliation'] if item['code'] == 'G0121']
        self.assertEqual((row['proposed_by'], row['listed_by']), (['astra'], ['fable']))
        self.assertIn(f'Proposed by: Astra; listed by Fable {LISTED_WORDS} by Fable',
                      self.trace_lines(self.trace(encounter_id)))
        # control: the located alternative of one participant reads as before (Fable's 45378 after peer review is a
        # proposal of its own; Astra's G0121 is worded as round 4 worded a located alternative)
        self.assertEqual(self.proposals(detail, '45378')[0]['proposed_by'], ['fable'])

    def test_a_participant_s_listing_beside_corti_s_own_row_of_the_code_says_no_participant_proposed_it(self):
        # Corti selects G0105 (excluded for scope); Astra lists G0105 with a quote no document holds: its alternative
        # has no proposer, and the same report names Corti as the proposer of Corti's own row - so the participant's
        # row says "no participant", never "none"
        self.corti.selections = [('45385', SNARE), ('45380', BIOPSY), ('G0105', SNARE)]
        self.adapters['astra'].first = [hp.answered('astra', hp.reading(
            codes=[('45385', SNARE), ('45380', BIOPSY), ('G0105', UNLOCATED_DIAG)],
            services=[('c1', 'colonoscopy', 'performed', SNARE)]))]
        encounter_id = self.create(TWO_EXTENTS)
        drain()
        detail = self.detail(encounter_id)
        rows = sorted((p['bucket'], p['proposed_by'], p['listed_by']) for p in self.proposals(detail, 'G0105'))
        self.assertEqual(rows, [('alternative', [], ['astra']), ('excluded', ['corti'], [])])
        txt = self.download(encounter_id)
        reason = (f'Listed by Astra {LISTED_WORDS}, and not added as a proposal: {HCPCS_WHY}. Alternatives cannot be '
                  'approved.')
        self.assertEqual(_block(_section(txt, reports.ALTERNATIVES_TITLE), '  - G0105 · '), [
            f'  - G0105 · Service outside the GI profiles — listed by Astra {LISTED_WORDS}, never selectable: {reason}',
            f'     Proposed by: no participant; listed by Astra {LISTED_WORDS}'])
        excluded = _block(_section(txt, 'EXCLUDED CANDIDATES'), '  - G0105 · ')
        self.assertIn('     Proposed by: Corti', excluded)
        self.assertNotIn('Proposed by: none', txt)

    def test_a_peer_review_s_unlocated_additional_code_is_listed_never_proposed_after_peer_review(self):
        # truth-3: Fable's peer review adds 45378 with a quote no document holds
        self.adapters['fable'].peer = [hp.answered('fable', hp.peer_answer(codes=[('45378', UNLOCATED_DIAG)]),
                                                   number=2)]
        encounter_id = self.create(TWO_EXTENTS)
        drain()
        detail = self.detail(encounter_id)
        [alternative] = self.proposals(detail, '45378')
        reason = (f'Listed by Fable {LISTED_WORDS}, and not added as a proposal: {UNLOCATED_WHY}. Alternatives cannot be '
                  'approved.')
        self.assertEqual((alternative['proposed_by'], alternative['phases'], alternative['listed_by'],
                          alternative['exclusion_reason']), ([], {}, ['fable'], reason))
        # the card's positions (and the trace's) no longer add "It proposed it after peer review."
        self.assertEqual(alternative['participant_positions']['fable'],
                         {'position': 'not_proposed', 'detail': 'Fable did not propose this code.', 'quote': ''})
        fable = self.rows(detail)['fable']
        self.assertEqual(fable['peer']['codes_added'], [])
        self.assertNotIn('45378', fable['peer']['detail'])
        peer_row = self.peer_row(detail, 'fable')
        self.assertIn('It first proposed no code in peer review that can be listed.', peer_row)
        self.assertNotIn('45378', peer_row)
        page = self.page_lines(detail)
        self.assertIn('45378 · Colonoscopy', page)  # the Alternatives title carries no "proposed after peer review"
        self.assertEqual(page[page.index('45378 · Colonoscopy') + 1], reason)
        txt = self.download(encounter_id)
        self.assertIn('    Additional code 45378 · units 1 — listed in peer review', _section(txt, reports.PEER_TITLE))
        added = [row for row in csv_rows(self.download(encounter_id, fmt='csv'))
                 if row['item_list'] == 'peer_additional_code']
        self.assertEqual([(row['proposed_by'], row['code'], row['status']) for row in added],
                         [('fable', '45378', 'listed_in_peer_review')])
        trace = self.trace(encounter_id)
        fable_runs = next(item for item in trace['participants'] if item['name'] == 'fable')['runs']
        self.assertEqual([[(c['code'], c['phase']) for c in run['review']['additional_codes']]
                          for run in fable_runs if run.get('review')], [[('45378', '')]])
        trace_page = self.trace_lines(trace)
        self.assertTrue([line for line in trace_page if line.startswith('45378 · units 1 · confidence high · listed '
                                                                        'in peer review')], trace_page)
        self.assertIn(f'Proposed by: no participant; listed by Fable {LISTED_WORDS}', trace_page)
        self.assertFalse([line for line in trace_page if 'proposed it after peer review' in line.lower()
                          or 'never independent' in line])

    def test_a_code_listed_with_no_located_quote_in_both_phases_is_never_said_to_be_repeated(self):
        # truth-2: Astra's first reading lists 45385 with a quote no document holds, and its peer review lists it
        # again with the same quote; 45385 is Corti's
        self.adapters['astra'].first = [hp.answered('astra', hp.reading(
            codes=[('45385', UNLOCATED), ('45380', BIOPSY)], services=[('c1', 'colonoscopy', 'performed', SNARE)]))]
        self.adapters['astra'].peer = [hp.answered('astra', hp.peer_answer(codes=[('45385', UNLOCATED)]), number=2)]
        encounter_id = self.create(TWO_EXTENTS)
        drain()
        detail = self.detail(encounter_id)
        [snare] = self.proposals(detail, '45385', bucket='selected')
        self.assertEqual((snare['proposed_by'], snare['phases']), (['corti', 'fable'], {'fable': 'independent'}))
        self.assertEqual(snare['participant_positions']['astra'],
                         {'position': 'not_proposed', 'quote': '', 'detail': LISTED})
        astra = self.rows(detail)['astra']
        self.assertEqual(astra['peer']['codes_added'], [])
        self.assertNotIn('first proposed', astra['peer']['detail'])
        self.assertNotIn('45385', astra['peer']['detail'])
        txt = self.download(encounter_id)
        self.assertIn('    Additional code 45385 · units 1 — listed in peer review', _section(txt, reports.PEER_TITLE))
        self.assertNotIn('repeated in peer review', txt)
        added = [row for row in csv_rows(self.download(encounter_id, fmt='csv'))
                 if row['item_list'] == 'peer_additional_code' and row['proposed_by'] == 'astra']
        self.assertEqual([(row['proposed_by'], row['code'], row['status']) for row in added],
                         [('astra', '45385', 'listed_in_peer_review')])
        trace = self.trace(encounter_id)
        astra_runs = next(item for item in trace['participants'] if item['name'] == 'astra')['runs']
        self.assertEqual([[(c['code'], c['phase']) for c in run['review']['additional_codes']]
                          for run in astra_runs if run.get('review')], [[('45385', '')]])
        self.assertFalse([line for line in self.trace_lines(trace) if 'first proposed in its independent reading'
                          in line])

    def test_located_entries_keep_their_phases(self):
        # control: a code its first reading located and its peer review lists again (located or not) is repeated; a code
        # only its peer review located is proposed after peer review (ColonCase: Fable's 45378 on the landmarks)
        self.adapters['astra'].peer = [hp.answered('astra', hp.peer_answer(codes=[('45385', SNARE),
                                                                                  ('45380', UNLOCATED_DIAG)]),
                                                   number=2)]
        encounter_id = self.create(TWO_EXTENTS)
        drain()
        detail = self.detail(encounter_id)
        astra, fable = self.rows(detail)['astra'], self.rows(detail)['fable']
        self.assertEqual((astra['peer']['codes_added'], fable['peer']['codes_added']), ([], ['45378']))
        self.assertIn('It listed 45385 and 45380 again in peer review; it first proposed them in its independent '
                      'reading.', astra['peer']['detail'])
        txt = _section(self.download(encounter_id), reports.PEER_TITLE)
        self.assertIn('    Additional code 45385 · units 1 — repeated in peer review; first proposed in its independent '
                      'reading', txt)
        self.assertIn('    Additional code 45378 · units 1 — proposed after peer review, never independent', txt)


@applied
@override_settings(ASTRA_MODE='disabled', FABLE_MODE='disabled')
class CortiOnlyListedByTests(Surfaces, R2WordingCase):
    """Corti only (I1): no participant's alternative exists, so listed_by is [] on every proposal and every trace
    reconciliation row, no participant row counts a code, and a report's snapshot carries no listed_by at all - a
    Corti-only report is harness@1's exactly (API.md)."""

    def test_corti_only_serves_no_lister_and_its_reports_carry_none(self):
        encounter_id = self.create(TWO_EXTENTS)
        drain()
        self.assertEqual(self.kinds(encounter_id), ['extract', 'analyze', 'predict', 'assess'])
        detail = self.detail(encounter_id)
        self.assertEqual(detail['harness']['phase'], 0)
        self.assertTrue(detail['assessment']['proposals'])
        self.assertEqual({json.dumps(p['listed_by']) for p in detail['assessment']['proposals']}, {'[]'})
        self.assertEqual([row['unlisted_codes'] for row in detail['harness']['participants']], [0, 0, 0])
        self.assertEqual({json.dumps(row['listed_by']) for row in self.trace(encounter_id)['reconciliation']}, {'[]'})
        snap = reports.snapshot(self.encounter(encounter_id), 'draft')
        self.assertTrue(snap['proposals'])
        self.assertFalse([item for item in snap['proposals'] if 'listed_by' in item])


class AlternativeEngineTests(SimpleTestCase):
    """D12 in the engine itself (tests.test_harness_engine's document and helpers)."""

    def test_a_participant_whose_entries_located_nothing_is_never_a_proposer_and_has_no_phase(self):
        colon = he.COLON
        astra = he.read('astra', [he.code(colon, '45385', he.SNARE), he.code(colon, '45378', 'not in the text at all')])
        fable = he.reviewed('fable', [he.code(colon, '45385', he.SNARE)],
                            he.peer('fable', additional=[he.code(colon, '45378', 'nor is this one in the text')]))
        result = he.run(colon, he.corti(('45385', he.span(colon, he.SNARE))), [astra, fable])
        alternative = he.proposal(result, '45378')
        self.assertEqual((alternative.bucket, alternative.support.get('proposed_by'), alternative.support.get('phases'),
                          alternative.support.get('listed_by')), ('alternative', [], None, ['astra', 'fable']))
        self.assertEqual(alternative.exclusion_reason, f'Listed by Astra and Fable {LISTED_WORDS}, and not added as a '
                                                       f'proposal: {UNLOCATED_WHY}. Alternatives cannot be approved.')
        harness = engine._Harness([astra, fable], colon, ())
        self.assertEqual((harness.phase('45378', 'astra'), harness.phase('45378', 'fable')), ('', ''))
        self.assertEqual(harness.phase('45385', 'astra'), 'independent')
        # a located one is still its proposer, with its phase
        located = he.reviewed('fable', [he.code(colon, '45385', he.SNARE)],
                              he.peer('fable', additional=[he.code(colon, 'G0121', he.CECUM)]))
        alternative = he.proposal(he.run(colon, he.corti(('45385', he.span(colon, he.SNARE))), [astra, located]),
                                  'G0121')
        self.assertEqual((alternative.support['proposed_by'], alternative.support['phases'],
                          alternative.support.get('listed_by')), (['fable'], {'fable': 'peer_review'}, None))
        self.assertTrue(alternative.exclusion_reason.startswith('Proposed by Fable after peer review, but not added as '
                                                                f'a proposal: {HCPCS_WHY}.'))


# --- shapes-1, truth-7: a peer review's HCPCS codes are codes CPT Studio reads ------------------------------------------

DATE = {'value': '2026-10-14', 'evidence': ['Date of service: 2026-10-14']}
TWO_SERVICES = [service(1, id='S1', family='colonoscopy', status='performed', evidence=[SNARE]),
                service(2, id='S2', family='colonoscopy', status='performed', evidence=[BIOPSY])]


def position(value, stance, quote):
    return {'code': value, 'position': stance, 'reason': 'Synthetic.', 'evidence': [quote]}


@applied
class HcpcsPeerCodeTests(Surfaces, R2WordingCase):
    """shapes-1, truth-7: the peer review's additional codes and positions were read in the CPT shape alone, so an HCPCS
    code the engine reads (participant_listable) was "a code CPT Studio does not read" in both reports, '' in the CSV,
    "listed in peer review" in the trace, and missing from codes_added."""

    def peer_surfaces(self, encounter_id, name):
        detail = self.detail(encounter_id)
        trace = self.trace(encounter_id)
        runs = next(item for item in trace['participants'] if item['name'] == name)['runs']
        (review_,) = [run['review'] for run in runs if run.get('review')]
        rows = csv_rows(self.download(encounter_id, fmt='csv'))
        return (detail, review_, _section(self.download(encounter_id), reports.PEER_TITLE),
                [(row['item_list'], row['code'], row['status']) for row in rows
                 if row['item_list'] in ('peer_position', 'peer_additional_code') and row['proposed_by'] == name])

    def test_an_hcpcs_position_and_an_hcpcs_additional_code(self):
        # the shapes lens's input: Corti selects 45385 and G0121; Astra's peer review disputes G0121 and adds G0105
        self.corti.selections = [('45385', SNARE), ('G0121', BIOPSY)]
        self.adapters['astra'].first = [hp.answered('astra', empty_reading(
            date_of_service=DATE, services=TWO_SERVICES, codes=[code('45385', service_ids=['S1'], evidence=[SNARE])]))]
        self.adapters['fable'].first = [hp.answered('fable', hp.reading(codes=[('45385', SNARE)]))]
        self.adapters['astra'].peer = [hp.answered('astra', {
            'question_answers': [], 'references_used': [], 'code_positions': [position('G0121', 'disputes', BIOPSY)],
            'additional_codes': [code('G0105', service_ids=['S2'], evidence=[BIOPSY])]}, number=2)]
        self.adapters['fable'].peer = [hp.answered('fable', hp.EMPTY_PEER, number=2)]
        encounter_id = self.create(TWO_EXTENTS)
        drain()
        detail, review_, txt, rows = self.peer_surfaces(encounter_id, 'astra')
        self.assertEqual(self.rows(detail)['astra']['peer']['codes_added'], ['G0105'])
        self.assertIn('Codes it proposed after peer review, never independent: G0105.', self.peer_row(detail, 'astra'))
        self.assertEqual([(c['code'], c['phase']) for c in review_['additional_codes']], [('G0105', 'peer_review')])
        self.assertEqual([(c['code'], c['position']) for c in review_['positions']], [('G0121', 'disputes')])
        self.assertIn('    Position on G0121: disputes', txt)
        self.assertIn('    Additional code G0105 · units 1 — proposed after peer review, never independent', txt)
        # written out (refutation round 6, falsegreen-3: read through reports.UNREAD_CODE, the constant under test,
        # this passed whatever that sentence said), and the constant kept beside it, so the pin is no weaker than it was
        self.assertFalse([line for line in txt
                          if 'a code CPT Studio does not read' in line or reports.UNREAD_CODE in line])
        self.assertEqual(rows, [('peer_position', 'G0121', 'disputes'),
                                ('peer_additional_code', 'G0105', 'proposed_after_peer_review')])

    def test_an_hcpcs_code_a_peer_review_adds_quoting_the_document(self):
        # truth-7 (a): ColonCase, except Fable's peer review adds G0121 on the landmarks line
        self.adapters['fable'].peer = [hp.answered('fable', hp.peer_answer(codes=[('G0121', LAND)]), number=2)]
        encounter_id = self.create(TWO_EXTENTS)
        drain()
        detail, review_, txt, rows = self.peer_surfaces(encounter_id, 'fable')
        self.assertEqual(self.rows(detail)['fable']['peer']['codes_added'], ['G0121'])
        self.assertEqual([(c['code'], c['phase']) for c in review_['additional_codes']], [('G0121', 'peer_review')])
        self.assertIn('    Additional code G0121 · units 1 — proposed after peer review, never independent', txt)
        self.assertEqual(rows, [('peer_additional_code', 'G0121', 'proposed_after_peer_review')])
        [alternative] = self.proposals(detail, 'G0121')
        self.assertEqual((alternative['proposed_by'], alternative['phases']), (['fable'], {'fable': 'peer_review'}))

    def test_an_hcpcs_position_on_corti_s_excluded_code(self):
        # truth-7 (b): Corti selects G0105 (excluded for scope); Astra's peer review disputes it quoting the snare line
        self.corti.selections = [('45385', SNARE), ('45380', BIOPSY), ('G0105', SNARE)]
        self.adapters['astra'].peer = [hp.answered('astra', hp.peer_answer(positions=[('G0105', 'disputes', SNARE)]),
                                                   number=2)]
        encounter_id = self.create(TWO_EXTENTS)
        drain()
        detail, review_, txt, rows = self.peer_surfaces(encounter_id, 'astra')
        [excluded] = self.proposals(detail, 'G0105')
        self.assertEqual(excluded['support']['participants']['astra']['peer']['detail'],
                         'In peer review, Astra disputes G0105, quoting the document verbatim.')
        self.assertIn('    Position on G0105: disputes', txt)
        self.assertEqual(rows, [('peer_position', 'G0105', 'disputes')])

    def test_a_value_in_no_code_s_shape_is_still_not_read(self):
        # control: a peer review's code in no code's shape stays "a code CPT Studio does not read" and is never shown
        self.adapters['fable'].peer = [hp.answered('fable', hp.peer_answer(codes=[('G0121;LES', LAND)],
                                                                           positions=[(LES, 'disputes', SNARE)]),
                                                   number=2)]
        encounter_id = self.create(TWO_EXTENTS)
        drain()
        detail, review_, txt, rows = self.peer_surfaces(encounter_id, 'fable')
        # the sentences written out (refutation round 6, falsegreen-3: through reports.UNREAD_CODE, the constant under
        # test, "a code it did not propose" there passed this control)
        self.assertIn('    Position on a code CPT Studio does not read: disputes', txt)
        self.assertIn('    Additional code a code CPT Studio does not read · units 1 — listed in peer review', txt)
        self.assertEqual(rows, [('peer_position', '', 'disputes'), ('peer_additional_code', '', 'listed_in_peer_review')])
        self.assertEqual([(c['code'], c['phase']) for c in review_['additional_codes']], [(length('G0121;LES'), '')])
        self.assertEqual(self.rows(detail)['fable']['peer']['codes_added'], [])


# --- D13 (truth-6, shapes-2): one count of a participant's codes that cannot be listed ---------------------------------

@applied
class UnlistedCountTests(Surfaces, R2WordingCase):
    """The engine counts every entry of a reading in no code's shape; the row counted the assessment's record of the
    reading, which keeps one entry per code value, so '45385-59' given twice was 2 in the summary and 1 on the row
    (refutation round 5, truth-6, shapes-2)."""

    def fable_reads(self, *codes):
        self.adapters['fable'].first = [hp.answered('fable', hp.reading(
            codes=list(codes), services=[('c1', 'colonoscopy', 'performed', SNARE)]))]
        encounter_id = self.create(TWO_EXTENTS)
        drain()
        return encounter_id

    def assertRowSays(self, detail, name, count):
        row = self.rows(detail)[name]
        self.assertEqual((row['codes'], row['unlisted_codes']), (['45385'], count))
        self.assertEqual(unlisted_counts(row['detail']), [count])
        self.assertTrue(row['detail'].endswith(engine.participant_unlisted_codes(count)), row['detail'])
        self.assertEqual(unlisted_counts(browser(f'rowOf(page(), "data-participant", {json.dumps(name)})', detail)),
                         [count])
        # the engine's own sentence for this participant's first reading, in participants.summary
        said = self.summary(detail).split(f'{name.capitalize()} (', 1)[1].split('Fable (', 1)[0]
        self.assertEqual(unlisted_counts(said), [count])

    def test_a_value_given_twice_is_counted_twice_as_the_engine_counts_it(self):
        encounter_id = self.fable_reads(('45385', SNARE), ('45385-59', SNARE), ('45385-59', SNARE))
        record = self.records(self.encounter(encounter_id).current_assessment)['fable']
        self.assertEqual([item['code'] for item in record['codes']], ['45385', '45385-59'])  # one entry per value
        self.assertRowSays(self.detail(encounter_id), 'fable', 2)

    def test_one_value_on_two_services_is_two_codes(self):
        # shapes-2: Astra gives 'W/LES(S)' once on each of two services
        self.adapters['astra'].first = [hp.answered('astra', empty_reading(
            date_of_service=DATE, services=TWO_SERVICES, codes=[
                code('45385', service_ids=['S1'], evidence=[SNARE]), code(LES, service_ids=['S1'], evidence=[SNARE]),
                code(LES, service_ids=['S2'], evidence=[BIOPSY])]))]
        encounter_id = self.create(TWO_EXTENTS)
        drain()
        self.assertRowSays(self.detail(encounter_id), 'astra', 2)

    @staticmethod
    def rewrite(assessment, records):
        """The assessment's participant entries as ``records`` (Assessment rows are immutable: only the database
        itself can make such a record, as one stored before a change would read)."""
        with connection.cursor() as cursor:
            cursor.execute(f'UPDATE {models.Assessment._meta.db_table} SET participants = %s::jsonb WHERE id = %s',
                           [json.dumps(records), assessment.pk])

    def test_the_count_is_read_again_from_the_frozen_reading_and_none_is_stated_without_it(self):
        encounter_id = self.fable_reads(('45385', SNARE), ('45385-59', SNARE), ('45385-59', SNARE))
        assessment = self.encounter(encounter_id).current_assessment
        records = [dict(record) for record in assessment.participants]
        fable = next(record for record in records if record['name'] == 'fable')
        # a record that lists none of the codes that cannot be listed: the row still states the reading's own count
        fable['codes'] = [{'code': '45385', 'quote': SNARE}]
        self.rewrite(assessment, records)
        self.assertEqual(self.rows(self.detail(encounter_id))['fable']['unlisted_codes'], 2)
        # a reading that no longer reads back as recorded: no count, rather than another one
        fable['reading_sha256'] = '0' * 64
        self.rewrite(assessment, records)
        row = self.rows(self.detail(encounter_id))['fable']
        self.assertEqual((row['codes'], row['unlisted_codes'], row['detail']),
                         (['45385'], None, 'Answered; the reading was used.'))

    def test_a_reading_whose_every_code_can_be_listed_states_no_count(self):
        encounter_id = self.fable_reads(('45385', SNARE))
        row = self.rows(self.detail(encounter_id))['fable']
        self.assertEqual((row['codes'], row['unlisted_codes'], row['detail']),
                         (['45385'], 0, 'Answered; the reading was used.'))


class UnlistedCountEngineTests(SimpleTestCase):
    """D13: one function counts a reading's, and a peer review's, entries the engine does not read."""

    def test_one_count_for_the_summary_and_the_row(self):
        colon = he.COLON
        entries = [he.code(colon, '45385', he.SNARE), he.code(colon, '45385-59', he.SNARE),
                   he.code(colon, '45385-59', he.SNARE), he.code(colon, LES, he.BIOPSY), he.code(colon, 'G0121', he.CECUM)]
        self.assertEqual(engine.participant_unlisted_count(entries), 3)
        self.assertEqual(engine.participant_unlisted_count([]), 0)
        given = he.reviewed('astra', entries, he.peer('astra', additional=[he.code(colon, LES, he.BIOPSY),
                                                                           he.code(colon, LES, he.SNARE)]))
        result = he.run(colon, he.corti(('45385', he.span(colon, he.SNARE))), [given])
        summary = he.encounter_check(result, 'participants.summary').detail
        self.assertIn(engine.participant_unlisted_codes(3, 'It'), summary)
        self.assertIn(engine.participant_unlisted_codes(2, 'In peer review it'), summary)


# --- falsegreen-1: the HCPCS half of a code's shape, against values that open in it and carry more --------------------

HCPCS_LED = ('G0121;LES', 'G0121;SYNTH-LESION(S) BY SNARE', 'G0121 ', 'G0121-59')


class HcpcsShapeTests(SimpleTestCase):
    """falsegreen-1: code_shaped's CPT half was pinned against '45385-59', '45385;' and '45385 '; its HCPCS half only
    against 'g0121' and 'G012', so HCPCS.match in place of fullmatch passed every test, and 'G0121;LES' became a
    participant's alternative (I9) while a 30-character value failed the assess stage (I10)."""

    def test_a_value_that_opens_in_an_hcpcs_code_s_shape_and_carries_more_is_no_code(self):
        for value in HCPCS_LED:
            with self.subTest(value=value):
                self.assertFalse(peer.code_shaped(value))
                self.assertFalse(engine.participant_listable(value))
                self.assertEqual(peer.shown_code(value), length(value))
        self.assertTrue(peer.code_shaped('G0121'))  # control: the code alone

    def test_the_engine_counts_it_and_lists_nothing_of_it(self):
        colon = he.COLON
        for value in HCPCS_LED:
            with self.subTest(value=value):
                astra = he.read('astra', [he.code(colon, '45385', he.SNARE), he.code(colon, value, he.BIOPSY)])
                result = he.run(colon, he.corti(('45385', he.span(colon, he.SNARE))), [astra])
                self.assertEqual([(p.code, p.bucket) for p in result.proposals], [('45385', 'selected')])
                self.assertEqual(engine.participant_codes([astra]), ('45385',))
                self.assertIn(engine.participant_unlisted_codes(1, 'It'),
                              he.encounter_check(result, 'participants.summary').detail)


@applied
class HcpcsLedPipelineTests(Surfaces, R2WordingCase):
    """falsegreen-1 through the pipeline: the value is counted, never listed or shown, and the longest - which a
    Proposal cannot hold - never fails the assess stage."""

    def check(self, value):
        self.adapters['astra'].first = [hp.answered('astra', hp.reading(codes=[('45385', SNARE), (value, BIOPSY)]))]
        self.adapters['fable'].first = [hp.answered('fable', hp.reading(codes=[('45385', SNARE)]))]
        for name in ('astra', 'fable'):
            self.adapters[name].peer = [hp.answered(name, hp.EMPTY_PEER, number=2)]
        encounter_id = self.create(TWO_EXTENTS)
        drain()
        self.assertEqual({job.state for job in self.jobs_of(encounter_id)}, {models.Job.SUCCEEDED})
        self.assertIn(value, [item.code for item in jobs.participant_reading(
            self.runs_of(encounter_id, 'astra', 'independent')[0])[0].codes])  # the reading keeps it as given
        detail = self.detail(encounter_id)
        self.assertEqual(sorted((p['code'], p['bucket']) for p in detail['assessment']['proposals']),
                         [('45380', 'selected'), ('45385', 'selected')])
        astra = self.rows(detail)['astra']
        self.assertEqual((astra['codes'], astra['unlisted_codes']), (['45385'], 1))
        for where, text in (('detail', json.dumps(detail)), ('trace', json.dumps(self.trace(encounter_id))),
                            ('txt', self.download(encounter_id))):
            self.assertNotIn(value, text, where)

    def test_a_short_hcpcs_led_value_is_counted_and_never_shown(self):
        self.check('G0121;LES')  # 9 characters: within the proposal provider's 1-10 rule

    def test_a_long_hcpcs_led_value_never_fails_the_assess_stage(self):
        self.check('G0121;SYNTH-LESION(S) BY SNARE')  # 30 characters: no Proposal could hold it


# --- falsegreen-2: Corti's own rule beside D9's -------------------------------------------------------------------------

@applied
class CortiShortUnshapedTests(Surfaces, R2WordingCase):
    """falsegreen-2: Corti's unlisted count is the engine's own rule for the proposal provider (engine._listable: 1 to 10
    characters, I1), never D9's participant rule. Every round-4 pin used values both rules agree on, so a count by
    participant_listable passed them all, and Corti's row said 'W/LES(S)' (8 characters) could not be listed beside its
    own code list naming it."""

    def test_a_corti_code_of_ten_characters_or_fewer_in_no_code_s_shape_is_listed_and_not_counted(self):
        def edit(answer, text):
            answer['codes'].append(_corti_item(LES, text, BIOPSY))
        with self.corti_answer(edit):
            encounter_id = self.create(TWO_EXTENTS)
            drain()
        detail = self.detail(encounter_id)
        corti = self.rows(detail)['corti']
        self.assertEqual((corti['detail'], corti['codes'], corti['unlisted_codes']),
                         ('Answered; its codes were checked.', ['45380', '45385', LES], 0))
        self.assertFalse([c for c in detail['assessment']['encounter_checks'] if c['id'] == 'provider.unlisted'])
        self.assertIn((LES, 'excluded'), [(p['code'], p['bucket']) for p in detail['assessment']['proposals']])
        self.assertEqual(serializers.corti_unlisted_counts(self.encounter(encounter_id).current_assessment), (0, 0))
        lines = _block(_section(self.download(encounter_id), 'REVIEW PARTICIPANTS'), '  - Corti · ')
        self.assertEqual(lines[0], '  - Corti · Corti · answered; its codes were checked')
        self.assertFalse([line for line in lines if line.startswith('    Not listed: ')])


# --- falsegreen-4: the unread-position sentences, written out ---------------------------------------------------------

UNREAD_CODE_ASTRA = ("Astra gave this code in an entry CPT Studio does not read: a participant's code is read only in the "
                     "shape of a CPT or HCPCS code, and this code is not in one.")
UNREAD_PEER_ASTRA = ("In peer review, Astra took a position on this code, which CPT Studio does not read: a participant's "
                     "code is read only in the shape of a CPT or HCPCS code, and this code is not in one.")


class UnreadPositionSentenceTests(SimpleTestCase):
    """falsegreen-4: every pin compared the support with engine.UNREAD_*.format(label='Astra') - the constants under
    test - so restoring "did not propose this code" there passed them all."""

    def test_the_sentences_on_corti_s_code_of_a_value_a_participant_gave_unread(self):
        colon = he.COLON
        corti = he.corti(('45385', he.span(colon, he.SNARE)), (LES, he.span(colon, he.BIOPSY)))
        astra = he.read('astra', [he.code(colon, '45385', he.SNARE), he.code(colon, LES, he.BIOPSY)])
        fable = he.read('fable', [he.code(colon, '45385', he.SNARE)])
        result = he.run(colon, corti, [astra, fable])
        self.assertEqual(he.proposal(result, LES).support['participants']['astra'],
                         {'position': 'not_proposed', 'quote': '', 'detail': UNREAD_CODE_ASTRA})
        stance = he.peer('astra', positions=[he.stance(colon, LES, 'disputes', he.BIOPSY)])
        reviewed = he.run(colon, corti, [he.reviewed('astra', [he.code(colon, '45385', he.SNARE)], stance), fable])
        self.assertEqual(he.proposal(reviewed, LES).support['participants']['astra']['peer'],
                         {'position': 'no_position', 'quote': '', 'detail': UNREAD_PEER_ASTRA})


# --- falsegreen-5: the engine's position of a first reading's unlocated code that peer review proposed ---------------

@applied
class FirstReadingThenPeerReviewTests(Surfaces, R2WordingCase):
    """falsegreen-5: round 4's variant A - Astra's frozen first reading lists 45385 with a quote no document holds, and
    its peer review proposes 45385 on the snare passage. HARNESS.md 12.12 recorded the engine's support position as
    'not_proposed' there; the engine says 'proposed', of both phases, and no test read it. The card's
    participant_positions speaks of the first reading alone."""

    def test_the_engine_s_position_is_of_both_phases_and_the_card_s_of_the_first_reading(self):
        self.adapters['astra'].first = [hp.answered('astra', hp.reading(
            codes=[('45385', UNLOCATED), ('45380', BIOPSY)], services=[('c1', 'colonoscopy', 'performed', SNARE)]))]
        self.adapters['astra'].peer = [hp.answered('astra', hp.peer_answer(codes=[('45385', SNARE)]), number=2)]
        encounter_id = self.create(TWO_EXTENTS)
        drain()
        [snare] = self.proposals(self.detail(encounter_id), '45385', bucket='selected')
        self.assertEqual((snare['proposed_by'], snare['phases']),
                         (['corti', 'astra', 'fable'], {'astra': 'peer_review', 'fable': 'independent'}))
        position_ = snare['support']['participants']['astra']
        # moved by refutation round 6 (R6-TRACE, account-3): the detail counts as proposals only the entries that
        # located a quote, so it no longer says "Astra proposed 45385 2 times" of one located entry and one listing
        self.assertEqual({key: position_[key] for key in ('position', 'detail', 'quote')}, {
            'position': 'proposed', 'quote': SNARE,
            'detail': 'Astra proposed 45385, listed in its independent reading with no quote found verbatim there, and '
                      'proposed after peer review (stated units 1, 1; modifiers none; confidence high), quoting the '
                      'document verbatim in 1 passage.'})
        self.assertEqual(snare['participant_positions']['astra'],
                         {'position': 'not_proposed', 'quote': '', 'detail': LISTED + LATER})
