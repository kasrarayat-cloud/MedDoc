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

