"""Refutation round 4, R4-SHAPES (the session's decision D9): one strict-shape rule for every value a model participant
wrote that CPT Studio lists or displays (HARNESS.md 12.4 as amended for refutation round 4; I9: no CPT descriptor text
is displayed). A code is listed or shown only in a CPT or HCPCS code's shape, a modifier only as two capital letters or
digits, an id only as letters and digits of at most 8 characters (any other under one name of CPT Studio's own), and a
reference the participant's own tool results never returned only as such a short id; anything else only by its length.

- shapes-1: a participant's code outside a code's shape ('W/LES(S)', 8 characters) was listed by the engine (any code of
  1 to 10 characters), so it reached the reconciliation, the retrieval, the alternatives, the participants.summary
  check, both reports and the trace's reconciliation and retrieval rows - while the same trace named it by its length in
  the reading. It is now counted, as Corti's unlisted codes are, and never listed. Corti's own listing does not change
  (I1).
- shapes-2, truth-3: the trace named a peer review's service ids with a ShownIds of its own, so the biopsy code a peer
  review added on 'colon-b' was shown on 'id 1', the name the same trace gave the snare service. One ShownIds now serves
  all of a participant's runs in one trace.
- shapes-3: a reference the participant cited and its tool calls never returned ('colonoscopy-flexible-with-biopsy-
  single-or-multiple', CPT 45380's descriptor with hyphens) was served by the API and the trace, drawn on every code
  card and printed in both reports as written.
- shapes-4: a tool call's arguments were served as the participant wrote them ('Colonoscopy, flexible, diagnostic').
- falsegreen-2: the trace's peer-review positions and additional codes are pinned in the strict shapes.
- falsegreen-3: the reader's problems name descriptor-like text that opens with a date or a code by its length.

Each pipeline test first shows that the record itself keeps what is withheld, so none passes on an input that never had
it, and that values in their shapes are still shown. Synthetic data only; nothing is sent. Corti is the harness@1
suite's in-process fake; Astra and Fable are the real replay adapters on the real tool loop with scripted answers
(tests.test_harness2_pipeline), their tool calls answered by CPT Studio's real CMS tool executor.
"""
import csv
import io
import json

from django.test import Client

from studio import jobs, models
from studio.participants import peer, prompt
from studio.participants.openai_astra import AstraParticipant
from studio.types import ReferenceUse
from studio.validation import engine
from tests import test_harness_engine as he
from tests.support import factories as f
from tests.test_harness2_pipeline import BIOPSY, EMPTY_PEER, PFS_KEY, SNARE, TWO_EXTENTS, answered, asks, reading
from tests.test_harness2_r2_peer import PeerMaterialCase
from tests.test_participants_reading import NOTE, PAGES
from tests.test_participants_support import OfflineTestCase, astra_with, code, empty_reading, service
from tests.test_pipeline_api import drain

LES = 'W/LES(S)'  # 8 characters: the engine listed it (1 to 10), the trace's reading named it by its length
REF = 'colonoscopy-flexible-with-biopsy-single-or-multiple'  # 51: CPT 45380's descriptor, its punctuation as hyphens
# the opening of 45378's descriptor, its semicolon written as a comma
ARG_CODES = ['Colonoscopy, flexible, diagnostic', 'SNARE-POLYPECTOMY']
TOOL_WORDS = 'Colonoscopy, flexible; diagnostic'  # a tool CPT Studio does not have, 34 characters (it keeps up to 40)
TOPIC_WORDS = 'colonoscopy; with biopsy, single or multiple'  # a topic outside the enumeration
RAW_ARGUMENTS = 'Colonoscopy, flexible; with biopsy'  # arguments that are not JSON: the loop records the text as given
FACT = f'fact:{PFS_KEY}:45385:mult_proc'  # what Astra's own cms_code_facts call returns: CPT Studio's own identifier
UNRETRIEVED_FACT = f'fact:{PFS_KEY}:45380:status'  # a fact ref in CPT Studio's form that no tool call returned to it
PASSAGE = 'ncci-2026-ch6-c-1'  # a passage key no tool call of the peer review returned
# falsegreen-2's tokens (the falsegreen lens's probe): each 20 characters or fewer with no whitespace
POSITION_TOKEN = 'SYNTH;WITH-POLYP(S)'
ADDED_TOKEN = 'SYNTH;WITH-LESION(S)'
MODIFIER_TOKEN = 'W/SYNTH-SNARE(S)'
SID_TOKEN = 'SNARE;WITH-SYNTH(S)'
# every value of this case a surface withholds (PASSAGE aside: CPT Studio's own key of a passage its retrieval holds)
WITHHELD = [LES, REF, *ARG_CODES, TOOL_WORDS, TOPIC_WORDS, RAW_ARGUMENTS, UNRETRIEVED_FACT, POSITION_TOKEN, ADDED_TOKEN,
            MODIFIER_TOKEN, SID_TOKEN, 'colon-a', 'colon-b']


def length(text):
    return f'a value of {len(text):,} character{"" if len(text) == 1 else "s"} (not shown)'


def compact(value):
    """A JSON value as participants.peer names it by its length: compact, an object's keys sorted."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def named(number, text):
    """The name CPT Studio gives the ``number``-th id it withholds (participants.peer.ShownIds)."""
    return f'id {number}: {length(text)}'


def astra_first_reading():
    """Astra's first reading: two colonoscopy services whose ids are withheld ('colon-a' quotes the snare, 'colon-b' the
    biopsy), 45385 on the first, LES on the second, and four references used - one its own tool calls returned."""
    return empty_reading(
        date_of_service={'value': '2026-10-14', 'evidence': ['Date of service: 2026-10-14']},
        services=[service(1, id='colon-a', family='colonoscopy', status='performed', evidence=[SNARE]),
                  service(2, id='colon-b', family='colonoscopy', status='performed', evidence=[BIOPSY])],
        codes=[code('45385', service_ids=['colon-a'], evidence=[SNARE]),
               code(LES, service_ids=['colon-b'], evidence=[BIOPSY])],
        references_used=[{'ref': REF, 'use': 'Synthetic use.'}, {'ref': 'rule01', 'use': 'Synthetic use.'},
                         {'ref': FACT, 'use': 'Synthetic use.'}, {'ref': UNRETRIEVED_FACT, 'use': 'Synthetic use.'}])


def astra_peer_review():
    """Astra's peer review: 45380 added on 'colon-b' (the biopsy service), a position on a descriptor-like code and an
    additional code whose code, modifier and first service id are descriptor-like, and a passage key it never
    retrieved."""
    return {'question_answers': [],
            'code_positions': [{'code': '45380', 'position': 'supports', 'reason': 'Synthetic.', 'evidence': [BIOPSY]},
                               {'code': POSITION_TOKEN, 'position': 'disputes', 'reason': 'Synthetic.',
                                'evidence': [SNARE]}],
            'additional_codes': [code('45380', service_ids=['colon-b'], evidence=[BIOPSY]),
                                 code(ADDED_TOKEN, modifiers=[MODIFIER_TOKEN, 'XS'], service_ids=[SID_TOKEN, 'colon-a'],
                                      evidence=[SNARE])],
            'references_used': [{'ref': PASSAGE, 'use': 'Synthetic use.'}]}


class ShapesCase(PeerMaterialCase):
    """The round-4 shapes lens's encounter (refute-harness-r4/shapes, probe 1) and more: Corti selects 45385; Astra's
    first loop makes five tool calls in one exchange - descriptor-like codes, a tool CPT Studio does not have, a topic
    outside the enumeration, arguments that are not JSON, and one call CPT Studio answers - then reads; its peer review
    adds 45380 on 'colon-b'; Fable reads 45385."""
    corti_codes = (('45385', SNARE),)

    def setUp(self):
        super().setUp()
        self.adapters['astra'].first = [
            asks('astra', ('call_astra_1', 'cms_code_facts', {'codes': ARG_CODES, 'date_of_service': '2026-10-20'}),
                 ('call_astra_2', TOOL_WORDS, {'codes': ['45385']}),
                 ('call_astra_3', 'cms_policy_passages', {'topic': TOPIC_WORDS, 'codes': ['45380']}),
                 ('call_astra_4', 'cms_code_facts', RAW_ARGUMENTS),
                 ('call_astra_5', 'cms_code_facts', {'codes': ['45385'], 'date_of_service': '2026-10-14'})),
            answered('astra', astra_first_reading())]
        self.adapters['fable'].first = [answered('fable', reading(codes=[('45385', SNARE)]))]
        self.adapters['astra'].peer = [answered('astra', astra_peer_review(), number=2)]
        self.adapters['fable'].peer = [answered('fable', EMPTY_PEER, number=2)]
        self.owner = f.member(self.ws, f.user('owner-r4shapes'), role=models.Membership.OWNER)

    def run_chain(self):
        """(encounter id, the owner's trace, the encounter detail, the TXT, the CSV rows) of the encounter, after the
        record itself is shown to keep every value the surfaces withhold."""
        encounter_id = self.create(TWO_EXTENTS)
        drain()
        astra = jobs.participant_reading(self.runs_of(encounter_id, 'astra', 'independent')[0])[0]
        self.assertEqual([item.code for item in astra.codes], ['45385', LES])
        self.assertEqual([item.id for item in astra.services], ['colon-a', 'colon-b'])
        self.assertEqual([(item.ref, item.retrieved) for item in astra.references_used],
                         [(REF, False), ('rule01', False), (FACT, True), (UNRETRIEVED_FACT, False)])
        review = jobs.peer_reading(self.runs_of(encounter_id, 'astra', 'peer_review')[0])[0]
        self.assertEqual([(item.code, item.modifiers, item.service_ids) for item in review.additional_codes],
                         [('45380', (), ('colon-b',)), (ADDED_TOKEN, (MODIFIER_TOKEN, 'XS'), (SID_TOKEN, 'colon-a'))])
        self.assertEqual([item.code for item in review.positions], ['45380', POSITION_TOKEN])
        self.assertEqual([(item.ref, item.retrieved) for item in review.references_used], [(PASSAGE, False)])
        calls = models.ToolCall.objects.filter(exchange__run__encounter_id=encounter_id,
                                               exchange__run__provider='astra').order_by('id')
        self.assertEqual([(call.tool, call.arguments) for call in calls][:4], [
            ('cms_code_facts', {'codes': ARG_CODES, 'date_of_service': '2026-10-20'}),
            (TOOL_WORDS, {'codes': ['45385']}),
            ('cms_policy_passages', {'topic': TOPIC_WORDS, 'codes': ['45380']}),
            ('cms_code_facts', RAW_ARGUMENTS)])
        client = Client()
        client.force_login(self.owner)
        trace = client.get(f'/ops/api/encounters/{encounter_id}/trace')
        self.assertEqual(trace.status_code, 200)
        detail = self.client.get(f'/ops/api/encounters/{encounter_id}')
        self.assertEqual(detail.status_code, 200)
        files = {}
        for fmt in ('txt', 'csv'):
            made = self.post(f'/ops/api/encounters/{encounter_id}/reports', {'kind': 'draft', 'fmt': fmt})
            self.assertEqual(made.status_code, 201, made.content)
            got = self.client.get(made.json()['download_url'])
            self.assertEqual(got.status_code, 200)
            files[fmt] = b''.join(got.streaming_content if got.streaming else [got.content]).decode('utf-8')
        return encounter_id, trace.json(), detail.json(), files['txt'], list(csv.reader(io.StringIO(files['csv'])))

    @staticmethod
    def astra_runs(trace):
        runs = next(item for item in trace['participants'] if item['name'] == 'astra')['runs']
        return (next(run for run in runs if run['purpose'] == 'independent'),
                next(run for run in runs if run['purpose'] == 'peer_review'))

    @staticmethod
    def rows(detail):
        return {row['name']: row for row in detail['harness']['participants']}


class ParticipantCodeShapeTests(ShapesCase):
    """shapes-1: a participant's code outside a code's shape is counted, never listed (the engine's _Harness)."""

    def test_a_participant_code_outside_a_code_s_shape_reaches_no_list_and_is_counted(self):
        _, trace, detail, txt, rows = self.run_chain()
        proposals = [(p['code'], p['bucket'], (p['support'] or {}).get('origin')) for p in
                     detail['assessment']['proposals']]
        # moved by refutation round 6 (R6-MEANING, the session's D14): the peer review's 45380, in a code's shape, is
        # read - and listed as its alternative, never a proposal (it was a selected proposal of its own)
        self.assertEqual(proposals, [('45385', 'selected', 'primary'), ('45380', 'alternative', 'participant')])
        self.assertEqual([(row['code'], row['bucket']) for row in trace['reconciliation']],
                         [('45385', 'selected'), ('45380', 'alternative')])
        # moved by refutation round 7 (d14-1): only the proposal provider's codes are traced; the participant's 45380,
        # never a proposal (D14), is never looked up for one (it was ['45380', '45385'])
        self.assertEqual(sorted(entry.get('code') for entry in trace['retrieval']), ['45385'])
        summary = next(check['detail'] for check in detail['assessment']['encounter_checks']
                       if check['id'] == 'participants.summary')
        self.assertIn('Astra (OpenAI, gpt-6-astra) read the document. It proposed 1 code (45385), 1 quoting the '
                      'document verbatim. ' + engine.participant_unlisted_codes(1, 'It'), summary)
        self.assertIn('It listed 1 additional code (45380), 1 quoting the document verbatim; a code first proposed in '
                      'peer review is never counted as independent. '
                      + engine.participant_unlisted_codes(1, 'In peer review it'), summary)
        self.assertIn('It returned 1 code that cannot be listed: not in the shape of a CPT code (four digits, then a '
                      'digit or a capital letter) or of an HCPCS Level II code (a capital letter, then four digits). '
                      'It is not shown and never truncated.', summary)
        # the participant row lists the codes it can and counts the other (review.listed_codes)
        astra = self.rows(detail)['astra']
        self.assertEqual((astra['codes'], astra['unlisted_codes']), (['45385'], 1))
        self.assertTrue(astra['detail'].endswith(engine.participant_unlisted_codes(1)), astra['detail'])
        # nowhere on the reconciliation's side, the reports, the trace or the API
        served = detail
        for value in (LES, ADDED_TOKEN, POSITION_TOKEN):
            for where, text in (('trace', json.dumps(trace, ensure_ascii=False)), ('txt', txt),
                                ('csv', json.dumps(rows, ensure_ascii=False)),
                                ('detail', json.dumps(served, ensure_ascii=False))):
                self.assertNotIn(value, text, f'{value} in {where}')

    def test_corti_s_own_listing_does_not_change_and_a_participant_s_same_value_is_not_read(self):
        # Corti's code of up to 10 characters is listed, excluded for scope, as before (I1 pins that path); the same
        # value in Astra's reading is not read for it - neither a proposal of its own nor a position on Corti's
        self.corti.selections = [('45385', SNARE), (LES, BIOPSY)]
        _, trace, detail, txt, _ = self.run_chain()
        listed = sorted((p['code'], p['bucket'], p['key']) for p in detail['assessment']['proposals'])
        # moved by refutation round 6 (R6-MEANING, the session's D14): the peer review's 45380 is its alternative (it
        # was sel:1)
        self.assertEqual(listed, [('45380', 'alternative', 'altp:0'), ('45385', 'selected', 'sel:0'),
                                  (LES, 'excluded', 'exc:0')])
        excluded = next(p for p in detail['assessment']['proposals'] if p['code'] == LES)
        self.assertEqual(excluded['proposed_by'], ['corti'])
        astra = excluded['support']['participants']['astra']
        self.assertEqual((astra['position'], astra['quote']), ('not_proposed', ''))
        self.assertEqual(astra['detail'], engine.UNREAD_CODE_POSITION.format(label='Astra'))
        self.assertEqual(excluded['support']['participants']['fable']['detail'], f'Fable did not propose {LES}.')
        self.assertIn(f'  - {LES} · ', txt)  # Corti's excluded proposal, as harness@1 prints it


class TraceIdsTests(ShapesCase):
    """shapes-2, truth-3: one name per withheld id for a participant across its reading and its peer review."""

    def test_a_peer_review_s_service_id_has_the_name_its_first_reading_gave_it(self):
        _, trace, _, _, _ = self.run_chain()
        first, peer_run = self.astra_runs(trace)
        snare, biopsy = named(1, 'colon-a'), named(2, 'colon-b')
        self.assertEqual([item['id'] for item in first['reading']['services']], [snare, biopsy])
        self.assertEqual([(item['code'], item['service_ids']) for item in first['reading']['codes']],
                         [('45385', [snare]), (length(LES), [biopsy])])
        # the biopsy code the peer review added is on the biopsy service, under the biopsy service's own name; an id the
        # reading never named gets a name no service carries
        self.assertEqual([(item['code'], item['service_ids'], item['phase'])
                          for item in peer_run['review']['additional_codes']],
                         [('45380', [biopsy], 'peer_review'),
                          (length(ADDED_TOKEN), [named(3, SID_TOKEN), snare], '')])
        names = [*[item['id'] for item in first['reading']['services']],
                 *[sid for item in peer_run['review']['additional_codes'] for sid in item['service_ids']]]
        self.assertEqual(len({name: None for name in names}), 3)  # three ids, three names, never one for two


class ReferenceShapeTests(ShapesCase):
    """shapes-3: a reference the participant's own tool results never returned is shown only as a short id of letters
    and digits, otherwise by its length - in the API, the trace and both reports; a retrieved one as given."""

    def test_a_reference_never_retrieved_is_shown_only_as_a_short_id_or_by_its_length(self):
        _, trace, detail, txt, rows = self.run_chain()
        shown = [(length(REF), False), ('rule01', False), (FACT, True), (length(UNRETRIEVED_FACT), False)]
        astra = self.rows(detail)['astra']
        self.assertEqual([(item['ref'], item['retrieved']) for item in astra['references']['used']], shown)
        self.assertEqual([item['use'] for item in astra['references']['used']], ['Synthetic use.'] * 4)
        self.assertIn(FACT, [item['ref'] for item in astra['references']['retrieved']])
        self.assertEqual([(item['ref'], item['retrieved']) for item in astra['peer_references']['used']],
                         [(length(PASSAGE), False)])
        first, peer_run = self.astra_runs(trace)
        self.assertEqual([(item['ref'], item['retrieved']) for item in first['reading']['references_used']], shown)
        self.assertEqual([(item['ref'], item['retrieved']) for item in peer_run['review']['references_used']],
                         [(length(PASSAGE), False)])
        for line in (f'    Used: {length(REF)} — cited, not retrieved by this run, so never shown as retrieved',
                     '    Used: rule01 — cited, not retrieved by this run, so never shown as retrieved',
                     f'    Used: {FACT} — retrieved by this run',
                     f'    Used: {length(UNRETRIEVED_FACT)} — cited, not retrieved by this run, so never shown as '
                     'retrieved',
                     f'    Used: {length(PASSAGE)} — cited, not retrieved by this run, so never shown as retrieved'):
            self.assertIn(line, txt.splitlines())
        header = rows[0]
        column = {name: header.index(name) for name in header}
        used = [(row[column['proposal_origin']], row[column['status']], row[column['exclusion_reason']])
                for row in rows[1:] if row[column['item_list']] == 'participant_reference'
                and row[column['status']] != 'retrieved' and row[column['proposed_by']] == 'astra']
        self.assertEqual(used, [('independent', 'cited_not_retrieved', length(REF)),
                                ('independent', 'cited_not_retrieved', 'rule01'), ('independent', 'used', FACT),
                                ('independent', 'cited_not_retrieved', length(UNRETRIEVED_FACT)),
                                ('peer_review', 'cited_not_retrieved', length(PASSAGE))])
        # (PASSAGE is CPT Studio's own key of a passage the reconciliation's retrieval holds, so it is not looked for)
        for value in (REF, UNRETRIEVED_FACT):
            for where, text in (('trace', json.dumps(trace, ensure_ascii=False)), ('txt', txt),
                                ('csv', json.dumps(rows, ensure_ascii=False)),
                                ('detail', json.dumps(detail, ensure_ascii=False))):
                self.assertNotIn(value, text, f'{value} in {where}')


class ToolArgumentShapeTests(ShapesCase):
    """shapes-4: a tool call's arguments in the trace - codes in a code's shape, a date in its digits, a topic of the
    enumeration, a tool CPT Studio has - and anything else the participant wrote only by its length."""

    def test_the_trace_shows_a_tool_call_s_arguments_and_tool_only_in_their_shapes(self):
        _, trace, _, _, _ = self.run_chain()
        first, _ = self.astra_runs(trace)
        calls = [(call['tool'], call['arguments'])
                 for exchange in first['exchanges'] for call in exchange['tool_calls']]
        self.assertEqual(calls, [
            ('cms_code_facts',
             {'codes': [length(ARG_CODES[0]), length(ARG_CODES[1])], 'date_of_service': '2026-10-20'}),
            (length(TOOL_WORDS), {'codes': ['45385']}),
            ('cms_policy_passages', {'topic': length(TOPIC_WORDS), 'codes': ['45380']}),
            ('cms_code_facts', length(RAW_ARGUMENTS)),
            ('cms_code_facts', {'codes': ['45385'], 'date_of_service': '2026-10-14'})])
        self.assertIn(FACT, [ref for exchange in first['exchanges'] for call in exchange['tool_calls']
                             for ref in call['refs']])  # CPT Studio's own refs, as returned
        text = json.dumps(trace, ensure_ascii=False)
        for value in (*ARG_CODES, TOOL_WORDS, TOPIC_WORDS, RAW_ARGUMENTS):
            self.assertNotIn(value, text, value)


class TraceReviewShapeTests(ShapesCase):
    """falsegreen-2: the trace's peer review - its positions and its additional codes' codes and modifiers - in the
    strict shapes (serializers._code_entry), pinned on tokens of 20 characters or fewer with no whitespace, which round
    2's token rule served as written."""

    def test_the_trace_s_peer_review_shows_codes_and_modifiers_only_in_their_shapes(self):
        _, trace, _, _, _ = self.run_chain()
        _, peer_run = self.astra_runs(trace)
        review = peer_run['review']
        self.assertEqual([(item['code'], item['position']) for item in review['positions']],
                         [('45380', 'supports'), (length(POSITION_TOKEN), 'disputes')])
        self.assertEqual([(item['code'], item['modifiers']) for item in review['additional_codes']],
                         [('45380', []), (length(ADDED_TOKEN), [length(MODIFIER_TOKEN), 'XS'])])
        text = json.dumps(trace, ensure_ascii=False)
        self.assertEqual([value for value in WITHHELD if value in text], [])


class ReaderQuotingTests(OfflineTestCase):
    """falsegreen-3: a problem quotes a model-written value only in a shape that cannot carry descriptor text
    (participants.reading._token); descriptor-like text that opens with a date or a code is named by its length - its
    date shape is digits and date punctuation only, never 'a digit and then anything'."""

    def setUp(self):
        super().setUp()
        self.adapter = AstraParticipant(self.tmp / 'never-read.env')
        self.request = self.adapter.build_request(NOTE, PAGES, 'paste', None)

    def test_a_first_reading_names_date_and_code_led_descriptor_text_by_its_length(self):
        result = self.adapter.read(self.request, astra_with(empty_reading(
            date_of_service={'value': '2026-10-21;W/LES(S)', 'evidence': []}, services=[service()],
            codes=[code('45385;WITH-POLYP(S)'), code('45380(S)'), code('45385')],
            not_coded=[{'service_ids': ['s1'], 'code': '2026-10-21(S)', 'reason': 'other', 'evidence': []}])))
        self.assertFalse(result.refused, result.problems)
        self.assertEqual(result.problems, (
            'date_of_service a value of 19 characters is not a YYYY-MM-DD date; it was not used.',
            'codes[0] (a value of 19 characters) is not a five-character CPT code; it is kept as given.',
            'codes[1] (a value of 8 characters) is not a five-character CPT code; it is kept as given.',
            'not_coded[0] (a value of 13 characters) is not a five-character CPT code; it is kept as given.'))

    def test_a_peer_review_names_them_by_their_length_too(self):
        review = peer.read(json.dumps({
            'question_answers': [], 'references_used': [],
            'code_positions': [{'code': '45385;WITH-POLYP(S)', 'position': 'supports', 'reason': '', 'evidence': []}],
            'additional_codes': [code('45380(S)', service_ids=[]), code('2026-10-21;W/LES(S)', units=0)]}),
            NOTE, provider='astra', adapter_version='synthetic@1', requested_model='gpt-6-astra',
            returned_model='gpt-6-astra', question_ids=(), frozen_inputs=())
        self.assertEqual(review.problems, (
            'code_positions[0] (a value of 19 characters) is not a five-character CPT code; it is kept as given.',
            'additional_codes[0] (a value of 8 characters) is not a five-character CPT code; it is kept as given.',
            'additional_codes[1] (a value of 19 characters) gives 0 units, outside 1 to 99; it was dropped.'))
        # the shapes that are quoted still are: a code, a date, a short id
        review = peer.read(json.dumps({
            'question_answers': [], 'references_used': [],
            'code_positions': [{'code': value, 'position': 'supports', 'reason': '', 'evidence': []}
                               for value in ('2026-10-21', '4538', 'G0121x')],
            'additional_codes': []}), NOTE, provider='astra', adapter_version='synthetic@1',
            requested_model='gpt-6-astra', returned_model='gpt-6-astra', question_ids=(), frozen_inputs=())
        self.assertEqual(review.problems, tuple(
            f'code_positions[{index}] ({name}) is not a five-character CPT code; it is kept as given.'
            for index, name in enumerate(["'2026-10-21'", "'4538'", "'G0121x'"])))


# --- the engine, pure (tests.test_harness_engine's document and helpers) ----------------------------------------------

class EngineListingTests(OfflineTestCase):
    """shapes-1 in the engine itself: _Harness reads a participant's code only in a CPT or HCPCS code's shape
    (engine.participant_listable, the one rule participants.peer.code_shaped states), in its first reading and its peer
    review alike, and counts every other code it gave; participant_codes() (what the assess stage looks up) agrees."""

    def test_codes_outside_a_code_s_shape_are_counted_and_codes_in_one_are_listed(self):
        colon = he.COLON
        astra = he.read('astra', [he.code(colon, '45385', he.SNARE), he.code(colon, LES, he.BIOPSY),
                                  he.code(colon, '4538', he.BIOPSY), he.code(colon, 'g0121', he.BIOPSY),
                                  he.code(colon, '45380', he.BIOPSY), he.code(colon, 'G0121', he.CECUM)])
        result = he.run(colon, he.corti(('45385', he.span(colon, he.SNARE))), [astra])
        # HARNESS.md P-ADMIT (2026-11-05): 45380, in a code's shape and on the biopsy passage, is read and admitted (as
        # before D14, which listed it); G0121 is out of scope and listed
        self.assertEqual([(p.code, p.bucket) for p in result.proposals],
                         [('45385', 'selected'), ('45380', 'selected'), ('G0121', 'alternative')])
        summary = he.encounter_check(result, 'participants.summary').detail
        self.assertIn('It proposed 3 codes (45385, 45380, G0121), 3 quoting the document verbatim. '
                      + engine.participant_unlisted_codes(3, 'It'), summary)
        self.assertIn('It returned 3 codes that cannot be listed: not in the shape of a CPT code', summary)
        self.assertIn('They are not shown and never truncated.', summary)
        self.assertEqual(engine.participant_codes([astra]), ('45380', '45385', 'G0121'))

    def test_a_peer_review_s_codes_and_positions_outside_a_code_s_shape_are_never_read(self):
        colon = he.COLON
        added = he.peer('astra', additional=[he.code(colon, LES, he.BIOPSY), he.code(colon, '45380', he.BIOPSY)],
                        positions=[he.stance(colon, LES, 'disputes', he.SNARE), he.stance(colon, '45385', 'supports',
                                                                                         he.SNARE)])
        given = he.reviewed('astra', [he.code(colon, '45385', he.SNARE)], added)
        result = he.run(colon, he.corti(('45385', he.span(colon, he.SNARE))), [given])
        # moved by refutation round 6 (R6-MEANING, the session's D14): the peer review's 45380 is read and listed, never
        # a proposal (it was selected)
        self.assertEqual([(p.code, p.bucket) for p in result.proposals],
                         [('45385', 'selected'), ('45380', 'alternative')])
        summary = he.encounter_check(result, 'participants.summary').detail
        self.assertIn('it took 2 positions on codes (1 supports, 1 disputes, 0 cannot tell)', summary)
        self.assertIn('It listed 1 additional code (45380), 1 quoting the document verbatim; a code first proposed in '
                      'peer review is never counted as independent. '
                      + engine.participant_unlisted_codes(1, 'In peer review it'), summary)
        self.assertEqual(engine.participant_codes([given]), ('45380', '45385'))
        self.assertEqual(he.proposal(result, '45385').support['participants']['astra']['peer']['position'], 'supports')

    def test_corti_s_listing_is_unchanged_and_no_participant_position_is_read_on_a_code_outside_a_code_s_shape(self):
        colon = he.COLON
        corti = he.corti(('45385', he.span(colon, he.SNARE)), (LES, he.span(colon, he.BIOPSY)))
        alone = he.run(colon, corti)
        astra = he.read('astra', [he.code(colon, '45385', he.SNARE), he.code(colon, LES, he.BIOPSY)],
                        advised=[he.not_coded(colon, LES, he.BIOPSY)])
        fable = he.read('fable', [he.code(colon, '45385', he.SNARE)])
        result = he.run(colon, corti, [astra, fable])
        # Corti's code of up to 10 characters is listed as before, excluded for scope (I1's own path)
        self.assertEqual([(p.code, p.bucket) for p in alone.proposals], [('45385', 'selected'), (LES, 'excluded')])
        self.assertEqual([(p.code, p.bucket) for p in result.proposals], [('45385', 'selected'), (LES, 'excluded')])
        self.assertEqual(he.decision(he.proposal(result, LES)), he.decision(he.proposal(alone, LES)))
        positions = he.proposal(result, LES).support['participants']
        self.assertEqual(positions['astra'], {'position': 'not_proposed', 'quote': '',
                                              'detail': engine.UNREAD_CODE_POSITION.format(label='Astra')})
        self.assertEqual(positions['fable'], {'position': 'not_proposed', 'quote': '',
                                              'detail': f'Fable did not propose {LES}.'})
        self.assertEqual(he.proposal(result, LES).support['proposed_by'], ['corti'])
        # and in peer review: a position on it is not read either
        stance = he.peer('astra', positions=[he.stance(colon, LES, 'disputes', he.BIOPSY)])
        reviewed = he.run(colon, corti, [he.reviewed('astra', [he.code(colon, '45385', he.SNARE)], stance), fable])
        self.assertEqual(he.proposal(reviewed, LES).support['participants']['astra']['peer'],
                         {'position': 'no_position', 'quote': '',
                          'detail': engine.UNREAD_PEER_POSITION.format(label='Astra')})


class SharedRuleTests(OfflineTestCase):
    """The one rule (participants.peer): what each helper shows as given and what it names by its length."""

    def test_a_code_s_shape_is_one_rule_for_the_peer_request_and_the_engine(self):
        for value in ('45385', '0537T', '3008F', '0001U', 'G0121', '99213', '1234Z'):
            self.assertTrue(peer.code_shaped(value), value)
            self.assertTrue(engine.participant_listable(value), value)
            self.assertEqual(peer.shown_code(value), value)
        for value in (LES, '4538', '453855', 'g0121', '45385 ', ' 45385', '45385-59', '４５３８５', '', None, 45385,
                      'G012', '45385;', ADDED_TOKEN):
            self.assertFalse(peer.code_shaped(value), value)
            self.assertFalse(engine.participant_listable(value), value)
        # Corti's own listing is another rule, pinned by I1: 1 to 10 characters
        self.assertTrue(engine._listable(LES))
        self.assertEqual(engine.MAX_LISTED_CODE, 10)

    def test_a_reference_is_shown_as_given_only_when_retrieved_or_a_short_id(self):
        cases = [((FACT, True), FACT), ((PASSAGE, True), PASSAGE), (('rule01', False), 'rule01'),
                 ((PASSAGE, False), length(PASSAGE)), ((REF, False), length(REF)),
                 ((UNRETRIEVED_FACT, False), length(UNRETRIEVED_FACT)), (('', False), ''),
                 ((REF, 'yes'), length(REF)), ((REF, 1), length(REF))]  # only True is retrieved
        for (ref, retrieved), expected in cases:
            self.assertEqual(peer.shown_reference(ref, retrieved), expected, (ref, retrieved))
        for (ref, retrieved), expected in cases[:-2]:
            self.assertEqual(peer.shown_ref(ReferenceUse(ref=ref, use='', retrieved=retrieved)), expected)

    def test_a_tool_call_is_shown_only_in_the_tools_own_shapes(self):
        self.assertEqual(peer.shown_tool('cms_code_facts'), 'cms_code_facts')
        self.assertEqual(peer.shown_tool('cms_policy_passages'), 'cms_policy_passages')
        self.assertEqual(peer.shown_tool(TOOL_WORDS), length(TOOL_WORDS))
        self.assertEqual(peer.shown_tool(''), '')
        cases = [
            ({'codes': ['45385', 'G0121', *ARG_CODES], 'date_of_service': '2026-10-20'},
             {'codes': ['45385', 'G0121', *[length(value) for value in ARG_CODES]], 'date_of_service': '2026-10-20'}),
            ({'codes': [], 'date_of_service': ''}, {'codes': [], 'date_of_service': ''}),
            ({'topic': 'ncci_endoscopy_rules', 'codes': ['45380']},
             {'topic': 'ncci_endoscopy_rules', 'codes': ['45380']}),
            ({'topic': TOPIC_WORDS, 'codes': ['45380']}, {'topic': length(TOPIC_WORDS), 'codes': ['45380']}),
            ({'codes': ['45385'], 'date_of_service': '2026-10-21;W/LES(S)'},
             {'codes': ['45385'], 'date_of_service': length('2026-10-21;W/LES(S)')}),
            ({'codes': [45385, None, ['45385']], 'date_of_service': 20261021},
             {'codes': [length('45385'), length('null'), length('["45385"]')], 'date_of_service': length('20261021')}),
            ({'codes': TOOL_WORDS}, {'codes': length(TOOL_WORDS)}),
            ({TOOL_WORDS: ['45385']}, length(compact({TOOL_WORDS: ['45385']}))),
            ({'codes': ['45385'], 'note': 'x'}, length(compact({'codes': ['45385'], 'note': 'x'}))),
            (RAW_ARGUMENTS, length(RAW_ARGUMENTS)), ([*ARG_CODES], length(compact(ARG_CODES))),
            (None, None), ('', ''), ({}, {})]
        for given, expected in cases:
            self.assertEqual(peer.shown_arguments(given), expected, given)
        self.assertEqual(sorted({name for tool in prompt.TOOLS for name in tool['parameters']['properties']}),
                         ['codes', 'date_of_service', 'topic'])  # the fields the rule knows are the tools' own
