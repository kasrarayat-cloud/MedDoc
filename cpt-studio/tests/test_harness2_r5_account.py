"""Refutation round 5, R5-ACCOUNT (the session's decisions D10, D12 and D13; HARNESS.md 5, 7, 11.1, 12.4, 12.6, 12.10,
12.12; I4, I9): one account of what a model participant did, on every surface - the page, the API, the owner's trace
and both reports - and no surface that turns CPT Studio's own reading of a participant's words into its answer.

- d8-2 (D10): the reports printed a peer answer as CPT Studio's reading of the participant's free text
  (candidates.canonical_value), so 'Cannulation of the bile duct was not successful.' was printed "successful", beside
  the participant's own passage 'Biliary cannulation was unsuccessful.'. They now print only the participant's claim -
  that the document settles the question, or that its answer is read as not settling it - with the passages it
  located, and no value; no release-default path reads a participant's value with a candidate reader (pinned here by
  making every one of them raise).
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
        response = self.owner().get(f'/api/encounters/{encounter_id}/trace')
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()

    def download(self, encounter_id, kind='draft', fmt='txt'):
        made = self.post(f'/api/encounters/{encounter_id}/reports', {'kind': kind, 'fmt': fmt})
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
            detail = self.client.get(f'/api/encounters/{encounter_id}')
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


class AnsweredQuestionCountTests(ErcpCase):
    """d8-3: one open question, answered twice in one peer review (the reader keeps both and notes the repeat): the
    summary said "It answered 2 open questions"."""

    def test_two_answers_to_one_question_are_two_answers_to_one_question(self):
        encounter_id = self.chain((True, 'Biliary cannulation failed.', FAILED_C), (True, 'successful', DONE_C))
        first = self.assessments(encounter_id)[0]
        self.assertEqual(first.clarifications.filter(state=models.Clarification.OPEN, fact='cannulation').count(), 1)
        summary = self.summary(self.client.get(f'/api/encounters/{encounter_id}').json())
        self.assertIn(ANSWERED_TWICE, summary)
        self.assertNotIn('2 open questions', summary)
        # and the reports print each answer as the participant's claim, neither value (D10)
        text = self.download(encounter_id, 'draft', 'txt')
        lines = _block(_section(text, reports.PEER_TITLE), '  - Astra · ')
        self.assertEqual(lines.count(ANSWER_LINE + 'Astra says the document settles it'), 2)
        self.assertEqual([line for line in lines if SUCCESS.search(line) or 'failed' in line], [])

    def test_one_answer_to_one_question_reads_as_before(self):
        encounter_id = self.chain((True, FAILED_ANSWER, FAILED_C))
        self.assertIn(ANSWERED_ONCE, self.summary(self.client.get(f'/api/encounters/{encounter_id}').json()))


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


# --- shapes-1, truth-7: a peer review's HCPCS codes are codes CPT Studio reads ------------------------------------------

DATE = {'value': '2026-10-14', 'evidence': ['Date of service: 2026-10-14']}
TWO_SERVICES = [service(1, id='S1', family='colonoscopy', status='performed', evidence=[SNARE]),
                service(2, id='S2', family='colonoscopy', status='performed', evidence=[BIOPSY])]


def position(value, stance, quote):
    return {'code': value, 'position': stance, 'reason': 'Synthetic.', 'evidence': [quote]}


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
        self.assertFalse([line for line in txt if reports.UNREAD_CODE in line])
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
        self.assertIn(f'    Position on {reports.UNREAD_CODE}: disputes', txt)
        self.assertIn(f'    Additional code {reports.UNREAD_CODE} · units 1 — listed in peer review', txt)
        self.assertEqual(rows, [('peer_position', '', 'disputes'), ('peer_additional_code', '', 'listed_in_peer_review')])
        self.assertEqual([(c['code'], c['phase']) for c in review_['additional_codes']], [(length('G0121;LES'), '')])
        self.assertEqual(self.rows(detail)['fable']['peer']['codes_added'], [])

