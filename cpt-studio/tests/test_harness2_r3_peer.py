"""Refutation round 3, R3-PEER: what a peer request shows of the other model's and Corti's values (HARNESS.md 12.4 as
amended for refutation round 3's peer-1; I9: no CPT descriptor text sent).

- peer-1: a code, modifier or id another model or Corti wrote reached the other vendors whenever it was a "short token"
  (participants.reading._token: at most 20 characters, no whitespace). So 'SYNTH;WITH-LESION(S)' - a Corti code the
  engine refuses to list and tells the member is not shown - and round 2's IR2-3 placeholder re-split into pieces of 20
  characters or fewer reached OpenAI and Anthropic verbatim, as codes, modifiers and service ids; and a Corti code the
  engine does list (up to 10 characters, excluded for scope) reached them as the code of CPT Studio's excluded proposal.
  A value is now shown only in a strict shape: a code in a CPT or HCPCS code's shape, a modifier of exactly two capital
  letters or digits, an id - and a reference never retrieved - of letters and digits only, at most 8 characters.
  Everything else is named by its length, and an id so withheld under a name of CPT Studio's own, the same for every
  mention of it in the request, so references between items still match. Each pipeline test first shows that the record
  itself still carries what the peer request leaves out, so none passes on an input that never had it; and each shows
  that short real codes, modifiers and ids still reach the request.
- peer-2 (a confirmed conclusion in another code's check shown as CPT Studio's own reading) is unreachable while this
  release offers no reviewer confirmation (D7): recorded in HARNESS.md 12.4 as a dormant-path finding, tested by
  R3-CONF.

Synthetic data only; nothing is sent. Corti is the harness@1 suite's in-process fake; Astra and Fable are the real
replay adapters on the real tool loop with scripted answers (tests.test_harness2_pipeline).
"""
import json
import re

from django.test import SimpleTestCase

from studio import jobs
from studio.participants import peer, prompt
from studio.participants.reading import CODE
from studio.types import (EvidenceSpan, LocatedQuote, ParticipantCode, ParticipantNotCoded, ParticipantQuestion,
                          ParticipantReading, ParticipantService, ReferenceUse)
from studio.validation import checks, engine
from tests.test_harness2_pipeline import (BIOPSY, CPT_STUDIO, EMPTY_PEER, SNARE, TWO_EXTENTS, answered,
                                          document_sections, peer_document, reading)
from tests.test_harness2_r2_peer import (CITED_REF, CORTI_LONG, LONG_BASIS, LONG_CODE, NOT_CODED_LONG,
                                         PeerMaterialCase, posted_bodies, stored_bodies)
from tests.test_participants_support import code, empty_reading, service
from tests.test_pipeline_api import drain

# app.js DESCRIPTOR_LIKE at 624754eb1 (studio/static/studio/app.js:141), JS /i as re.I: the page's own descriptor rule
PAGE_RULE = re.compile(
    r'\((?:s|es|ies)\)|;\s*(?:with|without|diagnostic|including|each|single|multiple|first|initial)\b'
    r'|\bsingle or multiple\b|\bwhen performed\b|\(separate procedure\)|\blist separately\b'
    r'|\bvisit for the\b[^.;]{0,80}?\bof an? (?:new|established) patient\b|\bmedically appropriate history\b'
    r'|\bminutes must be met or exceeded\b|\bsingle\/multiple\b|\bw\/(?:o\b|[a-z])', re.I)

# The refutation lens's tokens (refute-harness-r3/peer, probe 1), each 20 characters or fewer with no whitespace
CORTI_TOKEN = 'SYNTH;WITH-LESION(S)'  # 20: the engine never lists it ("It is not shown and never truncated")
ASTRA_CODE = 'SYNTH;WITH-POLYP(S)'  # 19
ASTRA_MOD = 'W/SYNTH-SNARE(S)'  # 16
ASTRA_SID = 'SNARE;WITH-SYNTH(S)'  # 19
# A Corti code of 10 characters or fewer: the engine lists it, as an excluded proposal (not a CPT code format), so CPT
# Studio's own reading names it too (the lens's note: "shown as given in cpt_studio.excluded[].code")
CORTI_LISTED = 'W/LES(S)'
LESION_SID = 'LESION(S)'  # a lesion-shaped service id (9)
NOT_CODED_TOKEN = 'NOT;W(S)'  # 8
# Round 2's IR2-3 placeholder re-split into short tokens: the lens's pieces of 20 characters or fewer, and the
# verifier's split on whitespace (each piece then a token of its own)
SPLIT = ['SYNTHETIC-PLACEHOLDER'[:20], ';with-removal-of', 'lesion(s)-by', 'PLACEHOLDER-technique'[:20]]
WORDS = 'SYNTH-PLACEHOLDER; with removal of lesion(s) by PLACEHOLDER technique'.split()
WITHHELD = [CORTI_TOKEN, CORTI_LISTED, ASTRA_CODE, ASTRA_MOD, ASTRA_SID, LESION_SID, NOT_CODED_TOKEN, *SPLIT,
            'SYNTH-PLACEHOLDER;', 'lesion(s)']


def length(text):
    return f'a value of {len(text)} character{"" if len(text) == 1 else "s"} (not shown)'


def named(number, text):
    """The name a peer request gives the ``number``-th id it withholds (peer.ShownIds)."""
    return f'id {number}: {length(text)}'


def hits(text):
    return sorted({match.group(0) for match in PAGE_RULE.finditer(text)})


def located(text):
    return LocatedQuote(quote=text, spans=(EvidenceSpan(context_index=0, start=0, end=len(text), text=text,
                                                        exact=True),))


def other_reading(services=(), codes=(), not_coded=(), questions=(), references=()):
    """Another model's frozen first reading, as the reader records it."""
    return ParticipantReading(provider='astra', adapter_version='synthetic@1', reading_version=prompt.READING_VERSION,
                              requested_model='gpt-6-astra', returned_model='gpt-6-astra', services=tuple(services),
                              codes=tuple(codes), not_coded=tuple(not_coded), questions=tuple(questions),
                              references_used=tuple(references))


def colon(sid):
    return ParticipantService(id=sid, family='colonoscopy', status='performed', description='', anatomy='',
                              extent='', technique='', evidence=(located(SNARE),))


# --- the shapes, pure ------------------------------------------------------------------------------------------------

CODES_SHOWN = ['45385', '0537T', '3008F', '0001U', 'G0121', '99213']
CODES_WITHHELD = [CORTI_TOKEN, CORTI_LISTED, ASTRA_CODE, NOT_CODED_TOKEN, *SPLIT, *WORDS, '45385-59', '4538', '453855',
                  'g0121', '45385 ', ' 45385', '45385\n', '４５３８５', 'G012', '45385;']
MODIFIERS_SHOWN = ['XS', '59', '25', 'PT', 'GA', '76']
MODIFIERS_WITHHELD = [ASTRA_MOD, *SPLIT, *WORDS, 'xs', 'X', 'XSS', 'W/', 'of', 'by', '(S)', 'X ', '５９']
IDS_SHOWN = ['c1', 's1', 'L1', 'svc2', 'lesion1', 'abc12345']
IDS_WITHHELD = [ASTRA_SID, LESION_SID, *SPLIT, 'svc-1', 'service_1', 'abcdefghi', 'c 1', 'c1\n', 'ｃ１',
                'SYNTH-PLACEHOLDER;', 'lesion(s)']


class ShapeTests(SimpleTestCase):
    """peer.shown_reading, pure: the other model's codes, modifiers, ids and unretrieved refs, each shown as given only
    in its strict shape (HARNESS.md 12.4 as amended for peer-1)."""

    def test_a_code_is_shown_only_in_a_cpt_or_hcpcs_code_s_shape(self):
        shown = peer.shown_reading(other_reading(
            codes=[ParticipantCode(code=value) for value in CODES_SHOWN + CODES_WITHHELD],
            not_coded=[ParticipantNotCoded(code=value) for value in CODES_SHOWN + CODES_WITHHELD + ['']]))
        expected = CODES_SHOWN + [length(value) for value in CODES_WITHHELD]
        self.assertEqual([item['code'] for item in shown['codes']], expected)
        self.assertEqual([item['code'] for item in shown['not_coded']], expected + [''])  # no code named stays ''
        self.assertEqual(hits(json.dumps(shown, ensure_ascii=False)), [])

    def test_the_shapes_are_the_engine_s_own(self):
        # every code the engine reads in one of its scope formats is shown, and the only codes withheld are those it
        # calls invalid - excluded for scope with the fixed sentence, which never names them (jobs._peer_codes)
        corpus = CODES_SHOWN + CODES_WITHHELD + MODIFIERS_WITHHELD + IDS_WITHHELD + ['1234Z', 'Z9999', '0001A']
        for value in corpus:
            with self.subTest(value=value):
                kind = checks.code_scope(value)[0]
                self.assertEqual(peer.shown_code(value) == value, kind != 'invalid' or bool(CODE.fullmatch(value)))
                if peer.shown_code(value) != value:
                    self.assertEqual(kind, 'invalid')
                # a modifier is shown exactly when the engine states it (engine.MODIFIER_SHAPE)
                self.assertEqual(peer.shown_modifier(value) == value, bool(engine.MODIFIER_SHAPE.fullmatch(value)))
        for value in MODIFIERS_SHOWN:
            self.assertTrue(engine.MODIFIER_SHAPE.fullmatch(value))
            self.assertEqual(peer.shown_modifier(value), value)

    def test_a_modifier_is_shown_only_as_two_capital_letters_or_digits(self):
        shown = peer.shown_reading(other_reading(
            codes=[ParticipantCode(code='45385', modifiers=tuple(MODIFIERS_SHOWN + MODIFIERS_WITHHELD))]))
        self.assertEqual(shown['codes'][0]['modifiers'],
                         MODIFIERS_SHOWN + [length(value) for value in MODIFIERS_WITHHELD])

    def test_an_id_is_shown_only_as_letters_and_digits_and_any_other_is_named_alike_wherever_it_is_mentioned(self):
        ids = IDS_SHOWN + IDS_WITHHELD
        shown = peer.shown_reading(other_reading(
            services=[colon(value) for value in ids],
            codes=[ParticipantCode(code='45385', service_ids=tuple(reversed(ids)))],
            not_coded=[ParticipantNotCoded(service_ids=(ASTRA_SID, 'c1', LESION_SID))],
            questions=[ParticipantQuestion(question='Q?', why='W.', service_ids=(LESION_SID, ASTRA_SID, 's1'))]))
        names = {value: named(index, value) for index, value in enumerate(IDS_WITHHELD, start=1)}
        expected = {**{value: value for value in IDS_SHOWN}, **names}
        self.assertEqual([item['id'] for item in shown['services']], [expected[value] for value in ids])
        # every mention of an id is the same in the request, so what refers to a service still finds it ...
        self.assertEqual(shown['codes'][0]['service_ids'], [expected[value] for value in reversed(ids)])
        self.assertEqual(shown['not_coded'][0]['service_ids'], [expected[ASTRA_SID], 'c1', expected[LESION_SID]])
        self.assertEqual(shown['clarifications'][0]['service_ids'], [expected[LESION_SID], expected[ASTRA_SID], 's1'])
        # ... and no two services are made one: withheld ids of one length get different names, never a shown id's
        lengths = [len(value) for value in IDS_WITHHELD]
        self.assertLess(len(set(lengths)), len(lengths))  # 'LESION(S)', 'abcdefghi' and 'lesion(s)' are all 9
        self.assertEqual(len(set(names.values())), len(names))
        self.assertFalse(set(names.values()) & set(IDS_SHOWN))

    def test_an_id_name_holds_within_one_request_and_starts_again_in_the_next(self):
        first = peer.shown_reading(other_reading(services=[colon(LESION_SID), colon(ASTRA_SID)]))
        second = peer.shown_reading(other_reading(services=[colon(ASTRA_SID), colon(LESION_SID)]))
        self.assertEqual([item['id'] for item in first['services']], [named(1, LESION_SID), named(2, ASTRA_SID)])
        self.assertEqual([item['id'] for item in second['services']], [named(1, ASTRA_SID), named(2, LESION_SID)])
        self.assertEqual(peer.shown_reading(other_reading(services=[colon(LESION_SID), colon(ASTRA_SID)])), first)

    def test_a_reference_never_retrieved_is_shown_only_as_a_short_id_and_a_retrieved_one_as_given(self):
        refs = [ReferenceUse(ref='fact:cms-pfs-rvu26d:45385:status', use='', retrieved=True),
                ReferenceUse(ref='mult-proc-3-part-1', use='', retrieved=True),
                ReferenceUse(ref='rule01', use='', retrieved=False),
                ReferenceUse(ref='rule-01', use='', retrieved=False),
                ReferenceUse(ref=ASTRA_SID, use='', retrieved=False),
                ReferenceUse(ref=CITED_REF, use='', retrieved=False),
                ReferenceUse(ref='fact:cms-pfs-rvu26d:45385:status', use='', retrieved=False)]
        shown = peer.shown_reading(other_reading(references=refs))
        self.assertEqual([item['ref'] for item in shown['references_used']],
                         ['fact:cms-pfs-rvu26d:45385:status', 'mult-proc-3-part-1', 'rule01', length('rule-01'),
                          length(ASTRA_SID), length(CITED_REF), length('fact:cms-pfs-rvu26d:45385:status')])

    def test_round_two_s_ir2_3_text_and_its_pieces_reach_no_shown_field(self):
        pieces = [*LONG_CODE.split(), *LONG_BASIS.split(), *CORTI_LONG.split(), *NOT_CODED_LONG.split()]
        pieces = [piece for piece in pieces if not re.fullmatch(r'[A-Za-z0-9]{1,8}', piece)]  # words an id may be
        shown = peer.shown_reading(other_reading(
            services=[colon(value) for value in pieces],
            codes=[ParticipantCode(code=value, modifiers=tuple(pieces[:16]), service_ids=tuple(pieces[:64]))
                   for value in [LONG_CODE, *pieces]],
            not_coded=[ParticipantNotCoded(code=NOT_CODED_LONG, service_ids=tuple(pieces))],
            references=[ReferenceUse(ref=value, use='') for value in pieces]))
        text = json.dumps(shown, ensure_ascii=False)
        for value in [LONG_CODE, LONG_BASIS, CORTI_LONG, NOT_CODED_LONG, *pieces]:
            self.assertFalse([field for field in self.fields(shown) if field == value], value)
        self.assertEqual(hits(text), [])

    @staticmethod
    def fields(shown):
        """Every code, modifier, id and ref a shown reading holds."""
        for item in shown['services']:
            yield item['id']
        for key in ('codes', 'not_coded'):
            for item in shown[key]:
                yield item['code']
                yield from item.get('modifiers', [])
                yield from item['service_ids']
        for item in shown['clarifications']:
            yield from item['service_ids']
        for item in shown['references_used']:
            yield item['ref']


# --- the pipeline: what both vendors are sent ------------------------------------------------------------------------

def lens_reading():
    """Astra's first reading with the lens's tokens in every token field, beside short real values."""
    return empty_reading(
        date_of_service={'value': '2026-10-14', 'evidence': ['Date of service: 2026-10-14']},
        services=[service(1, id=ASTRA_SID, family='colonoscopy', status='performed', evidence=[SNARE]),
                  service(2, id='c1', family='colonoscopy', status='performed', evidence=[BIOPSY]),
                  service(3, id=LESION_SID, family='colonoscopy', status='performed', evidence=[BIOPSY])],
        codes=[code('45385', service_ids=[ASTRA_SID], evidence=[SNARE], modifiers=[ASTRA_MOD, 'XS', *SPLIT]),
               code(ASTRA_CODE, service_ids=[ASTRA_SID], evidence=[SNARE]),
               code('45380', service_ids=['c1', LESION_SID], evidence=[BIOPSY], modifiers=WORDS)],
        not_coded=[{'service_ids': [LESION_SID], 'code': NOT_CODED_TOKEN, 'reason': 'other', 'evidence': [BIOPSY]}],
        clarifications=[{'question': 'Synthetic question?', 'why': 'Synthetic why.',
                         'service_ids': [ASTRA_SID, 'c1', LESION_SID], 'evidence': []}])


class PeerRequestTests(PeerMaterialCase):
    """The lens's input (refutation round 3, peer-1) through the real pipeline: what Astra's and Fable's peer requests
    carry, as stored and as handed to the adapters' send."""
    corti_codes = (('45385', SNARE), ('45380', BIOPSY), (CORTI_TOKEN, BIOPSY), (CORTI_LISTED, BIOPSY))

    def setUp(self):
        super().setUp()
        self.adapters['astra'].first = [answered('astra', lens_reading())]
        self.adapters['fable'].first = [answered('fable', reading(codes=[('45385', SNARE)]))]
        for name in ('astra', 'fable'):
            self.adapters[name].peer = [answered(name, EMPTY_PEER, number=2)]

    def run_chain(self):
        encounter_id = self.create(TWO_EXTENTS)
        drain()
        # the record itself keeps what the peer requests leave out ...
        astra = jobs.participant_reading(self.runs_of(encounter_id, 'astra', 'independent')[0])[0]
        self.assertEqual([item.id for item in astra.services], [ASTRA_SID, 'c1', LESION_SID])
        self.assertEqual([item.code for item in astra.codes], ['45385', ASTRA_CODE, '45380'])
        self.assertEqual(astra.codes[0].modifiers, (ASTRA_MOD, 'XS', *SPLIT))
        normalized = jobs._provider_inputs(self.runs_of(encounter_id, 'corti')[0])[1]
        self.assertEqual([item.code for item in normalized.codes if item.role == 'selected'],
                         ['45385', '45380', CORTI_TOKEN, CORTI_LISTED])
        first = [a for a in self.assessments(encounter_id) if jobs.assessment_phase(a) == 1][0]
        excluded = first.proposals.get(code=CORTI_LISTED)
        self.assertEqual(excluded.status, 'excluded')  # the engine lists it: up to 10 characters
        unlisted = [check['detail'] for check in first.encounter_checks if check['id'] == 'provider.unlisted']
        self.assertIn('It is not shown and never truncated.', unlisted[0])  # and refuses to list the 20-character one
        runs = {name: self.runs_of(encounter_id, name, 'peer_review') for name in ('astra', 'fable')}
        self.assertEqual({name: [(run.state, run.sent) for run in found] for name, found in runs.items()},
                         {'astra': [('succeeded', True)], 'fable': [('succeeded', True)]})
        return encounter_id, first, excluded, {name: found[0] for name, found in runs.items()}

    def test_no_peer_request_carries_a_value_that_is_not_in_its_strict_shape(self):
        encounter_id, _, _, runs = self.run_chain()
        corti_tokens = [CORTI_TOKEN, CORTI_LISTED]
        # ... and no peer request sends Corti's to either vendor, nor Astra's to Fable (Astra's own reading is shown to
        # Astra as it wrote it, by design)
        self.assertCarriesNone(stored_bodies(self, encounter_id, [runs['astra']]) + posted_bodies(self, 'astra'),
                               corti_tokens)
        self.assertCarriesNone(stored_bodies(self, encounter_id, [runs['fable']]) + posted_bodies(self, 'fable'),
                               WITHHELD)
        for body in stored_bodies(self, encounter_id, [runs['fable']]) + posted_bodies(self, 'fable'):
            shown = json.loads(body)
            self.assertEqual(hits(json.dumps(shown.get('messages') or shown.get('input'), ensure_ascii=False)), [])
        for name in ('astra', 'fable'):
            sections = document_sections(peer_document(name, runs[name].request_body))
            corti = sections['corti (another coding system):']
            self.assertEqual([item['code'] for item in corti['codes']],
                             ['45385', '45380', length(CORTI_TOKEN), length(CORTI_LISTED)])
            self.assertEqual(hits(json.dumps([corti, sections[CPT_STUDIO]], ensure_ascii=False)), [])

    def test_the_owner_s_trace_shows_another_model_s_values_in_the_same_strict_shapes(self):
        # The owner's trace shows each participant's codes, modifiers and ids in the strict shapes a peer request shows
        # them in (I9: no CPT descriptor text is displayed either; refutation round 3, R3-PEER's display note, applied
        # at integration in serializers._code_entry): the 20-character token rule the trace used before served
        # ASTRA_CODE, ASTRA_MOD and ASTRA_SID as written.
        from django.test import Client

        from studio import models
        from tests.support import factories as f

        owner = f.member(self.ws, f.user('owner'), role=models.Membership.OWNER)
        encounter_id, _, _, _ = self.run_chain()
        client = Client()
        client.force_login(owner)
        trace = client.get(f'/ops/api/encounters/{encounter_id}/trace').json()
        astra = next(item for item in trace['participants'] if item['name'] == 'astra')
        reading = next(run['reading'] for run in astra['runs'] if run['reading'])
        shown = json.dumps(reading, ensure_ascii=False)
        # nowhere in the reading as served - neither as a field's value nor inside a problem the reader wrote about it
        # (the reader quotes a value in a problem only in a strict shape too, participants.reading._token)
        for token in [ASTRA_CODE, ASTRA_MOD, ASTRA_SID, LESION_SID, NOT_CODED_TOKEN, *SPLIT]:
            self.assertNotIn(token, shown, token)
        self.assertIn(f'codes[1] (a value of {len(ASTRA_CODE)} characters) is not a five-character CPT code; it is kept '
                      'as given.', reading['problems'])
        self.assertEqual([item['id'] for item in reading['services']],
                         [named(1, ASTRA_SID), 'c1', named(2, LESION_SID)])
        self.assertEqual([(item['code'], item['service_ids']) for item in reading['codes']],
                         [('45385', [named(1, ASTRA_SID)]), (length(ASTRA_CODE), [named(1, ASTRA_SID)]),
                          ('45380', ['c1', named(2, LESION_SID)])])
        self.assertEqual(reading['codes'][0]['modifiers'], [length(ASTRA_MOD), 'XS', *[length(item) for item in SPLIT]])

    def test_cpt_studio_s_excluded_code_is_named_by_its_length_with_its_reason(self):
        _, _, excluded, runs = self.run_chain()
        reasons = [check['detail'] for check in excluded.checks if check['status'] != 'pass']
        self.assertEqual(reasons, ["Not a CPT Category I or III code format — outside this release's CPT coding "
                                   'scope.'])  # CPT Studio's own sentence: it never names the code
        for name in ('astra', 'fable'):
            shown = document_sections(peer_document(name, runs[name].request_body))[CPT_STUDIO]
            self.assertEqual(shown['excluded'], [{'key': excluded.key, 'code': length(CORTI_LISTED),
                                                  'status': 'excluded', 'reasons': reasons}])
            self.assertEqual([item['code'] for item in shown['held']], ['45385', '45380'])

    def test_short_real_codes_modifiers_and_ids_still_reach_the_other_vendor_and_references_still_match(self):
        encounter_id, _, _, runs = self.run_chain()
        shown = document_sections(peer_document('fable', runs['fable'].request_body))['astra (another model):']
        astra = jobs.participant_reading(self.runs_of(encounter_id, 'astra', 'independent')[0])[0]
        self.assertEqual(shown, peer.shown_reading(astra))
        sid, lesion = named(1, ASTRA_SID), named(2, LESION_SID)
        self.assertEqual([item['id'] for item in shown['services']], [sid, 'c1', lesion])
        self.assertEqual([(item['code'], item['service_ids']) for item in shown['codes']],
                         [('45385', [sid]), (length(ASTRA_CODE), [sid]), ('45380', ['c1', lesion])])
        self.assertEqual(shown['codes'][0]['modifiers'], [length(ASTRA_MOD), 'XS', *[length(v) for v in SPLIT]])
        self.assertEqual(shown['codes'][2]['modifiers'], [length(v) for v in WORDS])
        self.assertEqual([(item['code'], item['service_ids']) for item in shown['not_coded']],
                         [(length(NOT_CODED_TOKEN), [lesion])])
        self.assertEqual(shown['clarifications'][0]['service_ids'], [sid, 'c1', lesion])
        for body in stored_bodies(self, encounter_id, [runs['fable']]) + posted_bodies(self, 'fable'):
            for value in ('"45385"', '"45380"', '"XS"', '"c1"'):
                self.assertIn(value, body.replace('\\"', '"'))
        # the frozen list still names Astra's recorded reading, from which what is shown is made
        record = self.records(self.assessments(encounter_id)[0])['astra']
        listed = dict(prompt.peer_document_inputs(peer_document('fable', runs['fable'].request_body))[1])
        self.assertEqual(listed['astra'], record['reading_sha256'])
