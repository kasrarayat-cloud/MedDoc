"""Refutation round 6, R6-MEANING: the owner's D10/D12 meaning check of 2026-11-03 - "verify that the displayed
conclusion preserves the quotation's meaning, negation, procedure ownership and time context. A quotation existing
verbatim must not itself establish clinical support." - and the findings it reproduced (meaning-r6/findings.json, each
verified in meaning-r6/results.json), on the findings' own inputs:

- negation-4, ownership-7: a first reading's 'proposed' position says the participant proposed the code "quoting the
  document verbatim", the engine's own words, never "with evidence".

The pipeline classes run the real jobs, tool loop, readers, engine, API, reports and app.js under node
(tests.test_harness2_pipeline: Corti's in-process fake and the replay participants answering scripted bytes). The paths
with no participant configured are not changed (I1): tests/test_harness_engine_parity.py and CortiOnlyParityTests pin
them. Synthetic data only; nothing is sent.
"""
import json

from studio import models
from tests import test_harness2_pipeline as hp
from tests.test_harness2_r5_account import Surfaces
from tests.test_pipeline_api import drain

# --- the findings' documents (synthetic) --------------------------------------------------------------------------------

HEAD = hp.HEAD
COLON = (HEAD + 'Colonoscopy report (fictional)\nDate of service: 2026-10-14\n'
         'Place of service: Ambulatory surgery center\nProcedure: Colonoscopy\n'
         'The colonoscope was advanced to the cecum and the examination was completed.\n')
CECUM = 'The colonoscope was advanced to the cecum and the examination was completed.'
SEEN = 'A 9 mm pedunculated polyp in the sigmoid colon was seen.'
NOT_REMOVED = 'The polyp was not removed.'
TOP = HEAD + 'Procedure report (fictional)\nDate of service: 2026-10-14\nPlace of service: Ambulatory surgery center\n'


def doc(head, *lines):
    return head + ''.join(line + '\n' for line in lines)


# --- the pipeline --------------------------------------------------------------------------------------------------------

ENDO = {'status': 'A', 'global_days': '000', 'mult_proc': '3', 'pctc': '0'}
BASE = {'status': 'A', 'global_days': '000', 'mult_proc': '2', 'endo_base': None, 'pctc': '0'}
EXTRA_PFS = {'43235': BASE, '43239': {**ENDO, 'endo_base': '43235'}, '43251': {**ENDO, 'endo_base': '43235'},
             '43260': BASE, '43261': {**ENDO, 'endo_base': '43260'}, '43262': {**ENDO, 'endo_base': '43260'},
             '43274': {**ENDO, 'endo_base': '43260'}, '45330': BASE, '45331': {**ENDO, 'endo_base': '45330'},
             '45338': {**ENDO, 'endo_base': '45330'}}


def colon_service(quote, status='performed'):
    return ('c1', 'colonoscopy', status, quote)


def proposals(detail):
    return (detail.get('assessment') or {}).get('proposals') or []


class MeaningCase(Surfaces, hp.Harness2Case):
    """The real pipeline offline, with CMS rows for every code the findings' inputs use."""
    corti_codes = ()

    def setUp(self):
        super().setUp()
        pfs = models.ReferenceSource.objects.get(key=hp.PFS_KEY)
        mue = models.ReferenceSource.objects.get(key=hp.MUE_KEY)
        for value, facts in EXTRA_PFS.items():
            models.ReferenceCodeFact.objects.create(source=pfs, code=value, facts=facts)
            models.ReferenceCodeFact.objects.create(source=mue, code=value, facts=hp.MUE_ROW)

    def detail(self, encounter_id):
        response = self.client.get(f'/api/encounters/{encounter_id}')
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()

    def scenario(self, text, corti=(), astra=None, fable=None, astra_peer=None, fable_peer=None):
        self.corti.selections = list(corti)
        self.adapters['astra'].first = [hp.answered('astra', astra or hp.reading())]
        self.adapters['fable'].first = [hp.answered('fable', fable or hp.reading())]
        self.adapters['astra'].peer = [hp.answered('astra', astra_peer or hp.peer_answer(), number=2)]
        self.adapters['fable'].peer = [hp.answered('fable', fable_peer or hp.peer_answer(), number=2)]
        encounter_id = self.create(text)
        drain()
        return encounter_id


# --- negation-4, ownership-7: a first reading's 'proposed' position names no evidence ---------------------------------

PROPOSED_DETAIL = '{label} proposed this code, quoting the document verbatim.'


class PositionWordingTests(MeaningCase):
    """review.participant_positions' 'proposed' detail is the engine's own words ("quoting the document verbatim"):
    "with evidence located in the document" called a denial, or another procedure's sentence, evidence for the code."""

    def positions_of(self, detail, value):
        return {p['bucket']: p['participant_positions'] for p in proposals(detail) if p['code'] == value}

    def assert_worded(self, encounter_id, detail):
        trace = self.trace(encounter_id)
        surfaces = '\n'.join([json.dumps(detail), *self.page_lines(detail), *self.trace_lines(trace), json.dumps(trace)])
        self.assertNotIn('with evidence located in the document', surfaces)

    def test_n13_a_denial_quoted_beside_corti_s_ready_code(self):
        """negation-4, N13: Corti's 45385 rests on the snare sentence; Astra's first reading quotes only another
        polyp's denial."""
        snare = 'A 9 mm pedunculated polyp in the sigmoid colon was removed with a hot snare.'
        text = doc(COLON, snare, 'A 4 mm rectal polyp was also seen.', NOT_REMOVED)
        encounter_id = self.scenario(text, [('45385', snare)],
                                     astra=hp.reading(codes=[('45385', NOT_REMOVED)], services=[colon_service(snare)]),
                                     fable=hp.reading(codes=[('45385', snare)], services=[colon_service(snare)]),
                                     fable_peer=hp.peer_answer(positions=[('45385', 'supports', NOT_REMOVED)]))
        detail = self.detail(encounter_id)
        astra = self.positions_of(detail, '45385')['selected']['astra']
        self.assertEqual(astra, {'position': 'proposed', 'detail': PROPOSED_DETAIL.format(label='Astra'),
                                 'quote': NOT_REMOVED})
        self.assertIn(f'Astra proposed it: Astra proposed this code, quoting the document verbatim. — “{NOT_REMOVED}”',
                      self.page_lines(detail))
        self.assert_worded(encounter_id, detail)

    def test_n6_corti_and_a_participant_on_the_same_denial(self):
        text = doc(COLON, SEEN, 'No polypectomy was performed.')
        encounter_id = self.scenario(text, [('45385', 'No polypectomy was performed.'), ('45378', CECUM)],
                                     astra=hp.reading(codes=[('45385', 'No polypectomy was performed.')],
                                                      services=[colon_service(CECUM)]),
                                     fable=hp.reading(codes=[('45378', CECUM)], services=[colon_service(CECUM)]))
        detail = self.detail(encounter_id)
        (positions,) = [p['participant_positions'] for p in proposals(detail) if p['code'] == '45385']
        self.assertEqual(positions['astra']['detail'], PROPOSED_DETAIL.format(label='Astra'))
        self.assert_worded(encounter_id, detail)

    def test_s1_another_procedures_sentence(self):
        """ownership-7, S1: Astra's 45380 quotes the EGD's biopsy sentence of a combined report."""
        egd_biopsy = 'Patchy erythema in the gastric antrum was biopsied with cold forceps.'
        snare = 'A 9 mm pedunculated polyp in the sigmoid colon was removed with a hot snare.'
        text = (TOP + 'Procedures: Upper endoscopy and colonoscopy\nEGD: The gastroscope was advanced to the second '
                'portion of the duodenum.\n' + egd_biopsy + '\nColonoscopy: The colonoscope was advanced to the cecum '
                'and the examination was completed.\n' + snare + '\n')
        encounter_id = self.scenario(text, [('43239', egd_biopsy), ('45385', snare)],
                                     astra=hp.reading(codes=[('45380', egd_biopsy), ('43251', snare)],
                                                      services=[colon_service(snare)]),
                                     fable=hp.reading(codes=[('43239', egd_biopsy), ('45385', snare)]))
        detail = self.detail(encounter_id)
        for value, name in (('45380', 'astra'), ('43239', 'fable'), ('45385', 'fable')):
            (positions,) = [p['participant_positions'] for p in proposals(detail) if p['code'] == value]
            self.assertEqual(positions[name]['detail'], PROPOSED_DETAIL.format(label=name.title()), value)
        self.assert_worded(encounter_id, detail)
