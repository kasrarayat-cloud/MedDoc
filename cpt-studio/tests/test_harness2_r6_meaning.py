"""Refutation round 6, R6-MEANING: the owner's D10/D12 meaning check of 2026-11-03 - "verify that the displayed
conclusion preserves the quotation's meaning, negation, procedure ownership and time context. A quotation existing
verbatim must not itself establish clinical support." - and the findings it reproduced (meaning-r6/findings.json, each
verified in meaning-r6/results.json), on the findings' own inputs:

- negation-4, ownership-7: a first reading's 'proposed' position says the participant proposed the code "quoting the
  document verbatim", the engine's own words, never "with evidence";
- the session's D14 (negation-1, -2, -3, ownership-1, -4, time-1, time-2): a participant's code that no decidable Corti
  proposal carries is never added as a proposal. It is listed as informational - an alternative - with CPT Studio's own
  reason, so no participant's code is ever selected or ready, counts as covering a documented act, makes another code
  included or clears an unresolved item; Corti's proposals are assessed exactly as with no participant configured;
- negation-5: a service only a participant reads as performed is worded with the documented-service reading's own
  not-done reading of that family where CPT Studio reads it inside the quoted passage (refutation round 7, display-1:
  never a reading of another passage), in the completeness reason and in the check;
- ownership-5: the page labels the source passages as showing the coded act only where they are the act's own.

The engine classes run the real routing, inventory and engine (tests.test_harness_engine's helpers); the pipeline
classes run the real jobs, tool loop, readers, engine, API, reports and app.js under node (tests.test_harness2_pipeline:
Corti's in-process fake and the replay participants answering scripted bytes). The paths with no participant
configured are not changed (I1): tests/test_harness_engine_parity.py and CortiOnlyParityTests pin them. Synthetic data
only; nothing is sent.
"""
import json
from html import unescape

from django.test import SimpleTestCase, override_settings

from studio import models, review
from studio.validation import engine
from tests import test_harness2_pipeline as hp
from tests.test_harness2_r2_wording import browser
from tests.test_harness2_r5_account import Surfaces, csv_rows
from tests.test_harness_engine import code, corti, peer, read, reviewed, run, service, span, without_record
from tests.test_pipeline_api import drain

# CPT Studio's own reason for a participant's code that no decidable proposal carries (the session's D14), written out
# so that a change of its wording is a change of this pin
D14_REASON = ("a quote found verbatim in the document does not by itself show that the coded act was done at this "
              "encounter, and in this release a participant's code is never added as a proposal of its own")
ACK = review.ACKNOWLEDGEMENTS['human']

# --- the findings' documents (synthetic) ------------------------------------------------------------------------------

HEAD = hp.HEAD
COLON = (HEAD + 'Colonoscopy report (fictional)\nDate of service: 2026-10-14\n'
         'Place of service: Ambulatory surgery center\nProcedure: Colonoscopy\n'
         'The colonoscope was advanced to the cecum and the examination was completed.\n')
CECUM = 'The colonoscope was advanced to the cecum and the examination was completed.'
SEEN = 'A 9 mm pedunculated polyp in the sigmoid colon was seen.'
FAILED = 'Hot snare polypectomy failed.'
ATTEMPTED = 'Hot snare polypectomy was attempted but the polyp could not be removed.'
NO_TISSUE = 'Cold forceps biopsy was attempted but no tissue was obtained.'
ERCP = (HEAD + 'Procedure note (fictional)\nDate of service: 2026-10-14\nPlace of service: Hospital outpatient\n'
        'Procedure: ERCP\nThe duodenoscope was advanced to the major papilla.\n')
CANNULATED = 'Deep biliary cannulation was achieved.'
STENT_FAILED = 'Biliary stent placement failed.'
EGD = (HEAD + 'Procedure note (fictional)\nDate of service: 2026-10-14\nPlace of service: Hospital outpatient\n'
       'Procedure: EGD\nThe endoscope was advanced to the second part of the duodenum.\n')
D2 = 'The endoscope was advanced to the second part of the duodenum.'
NODULE = 'A small nodule was seen in the gastric antrum.'
EGD_BIOPSY_FAILED = 'Cold forceps biopsy of the antrum failed.'
HEADER_COLON = COLON.replace('Procedure: Colonoscopy', 'Procedure: Colonoscopy with hot snare polypectomy')
NO_POLYPS_REMOVED = 'No polyps were removed.'
NOT_REMOVED = 'The polyp was not removed.'
CONSIDERED = 'Snare removal was considered but not performed.'
TOP = HEAD + 'Procedure report (fictional)\nDate of service: 2026-10-14\nPlace of service: Ambulatory surgery center\n'
EGD7 = ('EGD: The gastroscope was advanced to the second portion of the duodenum. Erythema was seen in the gastric '
        'antrum.')
EGD7_BX = 'Biopsies were taken with cold forceps.'
COLON7N = ('Colonoscopy: The colonoscope was advanced to the cecum and the examination was completed. The colon was '
           'normal. No biopsies were taken.')
F7N = TOP + 'Procedures: EGD and colonoscopy\n' + EGD7 + '\n' + EGD7_BX + '\n' + COLON7N + '\n'
EGD_LINE = ('EGD: The gastroscope was advanced to the second portion of the duodenum. A 6 mm sessile polyp was seen in '
            'the gastric body.')
EGD_SNARE = 'The polyp was removed with a hot snare.'
COLON_LINE = ('Colonoscopy: The colonoscope was advanced to the cecum and the examination was completed. The colon was '
              'normal. No polyps were seen.')
F1 = TOP + 'Procedures: EGD and colonoscopy\n' + EGD_LINE + '\n' + EGD_SNARE + '\n' + COLON_LINE + '\n'
CO_SNARE = 'A 7 mm polyp in the ascending colon was removed with a cold snare.'
FS_BIOPSY = 'Biopsies of the rectal mucosa were taken with cold forceps.'
COLON_FS = (HEAD + 'Colonoscopy report (fictional)\nDate of service: 2026-10-14\nPlace of service: Ambulatory surgery '
            'center\nProcedure: Colonoscopy\n' + CECUM + '\n' + CO_SNARE + '\n\n{heading}\nThe flexible sigmoidoscope '
            'was advanced to 60 cm in the descending colon.\n' + FS_BIOPSY + '\n')
H1 = COLON_FS.format(heading='Separate note: Flexible sigmoidoscopy (fictional), 2026-10-14')
DIAG_HEAD = (HEAD + 'Colonoscopy report (fictional)\nDate of service: 2026-10-14\n'
             'Place of service: Ambulatory surgery center\n')
CECUM_LANDMARKS = ('The colonoscope was advanced to the cecum, identified by the appendiceal orifice and ileocecal '
                   'valve.')
NOT_REMOVED_TODAY = 'A 15 mm sessile polyp was seen in the transverse colon and was not removed today.'
LAST_LABEL = 'Last colonoscopy: 9 mm polyp removed with hot snare.'


def doc(head, *lines):
    return head + ''.join(line + '\n' for line in lines)


def earlier(line):
    """time-1's document: an earlier colonoscopy's polypectomy on its own line, then today's diagnostic examination."""
    return DIAG_HEAD + line + '\nProcedure: Colonoscopy\n' + CECUM_LANDMARKS + '\n' + NOT_REMOVED_TODAY + '\n'


# --- the pipeline -----------------------------------------------------------------------------------------------------

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


def corti_rows(detail):
    """Each of Corti's proposals as a reviewer is served it: its key, code, bucket, status, the actions it allows, its
    checks and its questions."""
    questions = {}
    for item in detail.get('clarifications') or []:
        questions.setdefault(item.get('proposal_id'), []).append((item['fact'], item['question']))
    return [(p['key'], p['code'], p['bucket'], p['status'], p['allowed_actions'],
             [(c['id'], c['status'], c['detail']) for c in p['checks']], sorted(questions.get(p['id'], [])))
            for p in proposals(detail) if (p.get('support') or {}).get('origin') != 'participant']


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

    def corti_alone(self, text, corti=()):
        """The same document with no model participant configured (I1's path), as a reviewer is served it."""
        with override_settings(ASTRA_MODE='disabled', FABLE_MODE='disabled'):
            self.corti.selections = list(corti)
            encounter_id = self.create(text)
            drain()
            detail = self.detail(encounter_id)
        self.assertEqual(detail['harness']['phase'], 0)
        return detail


# --- negation-4, ownership-7: a first reading's 'proposed' position names no evidence ---------------------------------

PROPOSED_DETAIL = '{label} proposed this code, quoting the document verbatim.'


class PositionWordingTests(MeaningCase):
    """review.participant_positions' 'proposed' detail is the engine's own words ("quoting the document verbatim"):
    "with evidence located in the document" called a denial, or another procedure's sentence, evidence for the code."""

    def positions_of(self, detail, value):
        return {p['bucket']: p['participant_positions'] for p in proposals(detail) if p['code'] == value}

    def assert_worded(self, encounter_id, detail):
        trace = self.trace(encounter_id)
        surfaces = '\n'.join([json.dumps(detail), *self.page_lines(detail), *self.trace_lines(trace),
                              json.dumps(trace)])
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

    def test_t1b_a_history_sentence_beside_corti_s_code(self):
        """time-3, t1b: Corti's 45385 rests on today's hot-snare sentence; Astra's first reading quotes only the
        history line about 2019. Its position names no evidence (the same repair as negation-4; pinned on time-3's own
        input at the integration of R6-MEANING), and Corti's code is as with Corti alone."""
        history = 'Prior colonoscopy in 2019 with polypectomy.'
        snare = 'A 9 mm pedunculated polyp in the sigmoid colon was removed with a hot snare.'
        text = (HEAD + 'Colonoscopy report (fictional)\nDate of service: 2026-10-14\n'
                'Place of service: Ambulatory surgery center\nHistory\n' + history + '\nProcedure: Colonoscopy\n'
                + CECUM_LANDMARKS + '\n' + snare + '\nPlan\nRepeat colonoscopy in 3 years.\n')
        encounter_id = self.scenario(text, [('45385', snare)],
                                     astra=hp.reading(codes=[('45385', history)], services=[colon_service(snare)]))
        detail = self.detail(encounter_id)
        astra = self.positions_of(detail, '45385')['selected']['astra']
        self.assertEqual(astra, {'position': 'proposed', 'detail': PROPOSED_DETAIL.format(label='Astra'),
                                 'quote': history})
        self.assertIn(f'Astra proposed it: Astra proposed this code, quoting the document verbatim. — “{history}”',
                      self.page_lines(detail))
        self.assert_worded(encounter_id, detail)
        self.assertEqual(corti_rows(detail), corti_rows(self.corti_alone(text, [('45385', snare)])))


# --- D14 on the engine: a participant's code no decidable proposal carries is an alternative, never a proposal --------

def participant_only(result, value):
    return [p for p in result.proposals if p.code == value and (p.support or {}).get('origin') == 'participant']


def corti_part(result):
    """Corti's proposals (and alternatives), with what the participants add to a support taken out (their record and the
    identity a confirmation is bound to): what the engine makes of them with no participant configured."""
    return [without_record(p) for p in result.proposals if (p.support or {}).get('origin') != 'participant']


RECONCILED = ('unresolved_items', 'covered', 'included_by', 'bundled', 'not_listed')


class D14EngineTests(SimpleTestCase):
    """Each meaning finding's input, and every phrasing its verifier measured: the participant's code is an alternative
    with CPT Studio's own reason, and everything about Corti's proposals and the reconciliation is what the engine makes
    with no participant at all - so no participant's code is ever selected or ready, holds or recasts Corti's base
    code (services.base_included), covers a documented act or clears an unresolved item."""

    def assert_d14(self, text, corti_codes, participants, only, provider_status='succeeded'):
        codes = corti(*((value, span(text, quote)) for value, quote in corti_codes))
        result = run(text, codes, participants, provider_status=provider_status)
        alone = run(text, codes, provider_status=provider_status)
        for value in only:
            items = participant_only(result, value)
            self.assertEqual([(p.bucket, p.status, p.reinstatable) for p in items],
                             [('alternative', 'informational', False)], (value, text[-120:]))
            self.assertTrue(items[0].key.startswith('altp:'), items[0].key)
            self.assertIn(f'but not added as a proposal: {D14_REASON}. ', items[0].exclusion_reason)
            self.assertFalse(any(p.code == value and p.bucket != 'alternative' for p in result.proposals), value)
        self.assertEqual(corti_part(result), list(alone.proposals), text[-160:])
        self.assertEqual(result.clarifications, alone.clarifications)
        for key in RECONCILED:
            self.assertEqual(result.completeness[key], alone.completeness[key], key)
        # nothing a participant gave is selected: every selected proposal is Corti's
        self.assertEqual([p.code for p in result.proposals if p.bucket != 'alternative'],
                         [p.code for p in alone.proposals if p.bucket != 'alternative'])
        return result, alone

    def test_negation_1_a_failed_or_attempted_act(self):
        """negation-1: N1-N4 and the verifier's 19 phrasings of a failed, abandoned or attempted act, each a
        participant-only code (Ready on 80df1831d168's engine and on the harness's)."""
        n1 = doc(COLON, SEEN, FAILED)
        self.assert_d14(n1, [('45378', CECUM)],
                        [read('astra', [code(n1, '45385', FAILED), code(n1, '45378', CECUM)]),
                         reviewed('fable', [code(n1, '45378', CECUM)])], ['45385'])
        n2 = doc(COLON, SEEN, ATTEMPTED)  # Fable's peer review adds 45385 on the attempt
        self.assert_d14(n2, [('45378', CECUM)],
                        [reviewed('astra', [code(n2, '45378', CECUM)]),
                         reviewed('fable', [code(n2, '45378', CECUM)],
                                  review=peer('fable', additional=(code(n2, '45385', ATTEMPTED),)))], ['45385'])
        n3 = doc(COLON, SEEN, NO_TISSUE)
        self.assert_d14(n3, [('45378', CECUM)], [read('astra', [code(n3, '45380', NO_TISSUE)])], ['45380'])
        n4 = doc(ERCP, CANNULATED, STENT_FAILED)
        self.assert_d14(n4, [('43260', CANNULATED)], [read('astra', [code(n4, '43274', STENT_FAILED)])], ['43274'])
        for value, head, base, line in (
                ('45385', COLON, ('45378', CECUM), 'Hot snare polypectomy was unsuccessful.'),
                ('45385', COLON, ('45378', CECUM), 'The snare polypectomy was abandoned.'),
                ('45385', COLON, ('45378', CECUM), 'Hot snare polypectomy was attempted without success.'),
                ('45385', COLON, ('45378', CECUM), 'An attempt at hot snare polypectomy failed.'),
                ('45385', COLON, ('45378', CECUM), 'Hot snare polypectomy: unsuccessful.'),
                ('45380', COLON, ('45378', CECUM), 'Cold forceps biopsy failed.'),
                ('45380', COLON, ('45378', CECUM), 'Cold forceps biopsy was unsuccessful.'),
                ('45380', COLON, ('45378', CECUM), 'An attempted cold forceps biopsy yielded no tissue.'),
                ('45380', COLON, ('45378', CECUM), 'Biopsy was attempted without success.'),
                ('43239', EGD, ('43235', D2), 'Gastric biopsy was attempted but no tissue was obtained.'),
                ('43244', EGD, ('43235', D2), 'Variceal band ligation failed.'),
                ('43262', ERCP, ('43260', CANNULATED), 'Biliary sphincterotomy failed.'),
                ('43274', ERCP, ('43260', CANNULATED), 'Stent placement was unsuccessful.'),
                ('43264', ERCP, ('43260', CANNULATED), 'Stone extraction was unsuccessful.'),
                ('43264', ERCP, ('43260', CANNULATED), 'Balloon sweep failed to clear the stone.')):
            with self.subTest(line):
                text = doc(head, SEEN if head is COLON else NODULE if head is EGD else CANNULATED, line)
                self.assert_d14(text, [base], [read('astra', [code(text, value, line)])], [value])

    def test_negation_2_an_act_sentence_whose_own_predicate_reports_a_failure(self):
        """negation-2: the inventory reads these acts as done, so the readers would have made the participant's code
        ready ('Every provider passage shows forceps biopsy.') and held Corti's 43235 as included in it."""
        for value, base, line in (('43239', ('43235', D2), EGD_BIOPSY_FAILED),
                                  ('43249', ('43235', D2), 'Balloon dilation of the stricture failed.'),
                                  ('43244', ('43235', D2), 'Band ligation of the varices was unsuccessful.')):
            with self.subTest(line):
                text = doc(EGD, NODULE, line)
                self.assert_d14(text, [base], [read('astra', [code(text, value, line)]),
                                               read('fable', [code(text, '43235', D2)])], [value])
        text = doc(COLON, SEEN, 'Hot snare removal of the polyp was unsuccessful.')
        self.assert_d14(text, [('45378', CECUM)],
                        [read('astra', [code(text, '45385', 'Hot snare removal of the polyp was unsuccessful.')])],
                        ['45385'])

    def test_negation_3_a_denial_under_a_procedure_line_that_names_the_act(self):
        """negation-3: N15, N17, N16, N9 and the verifier's further denials - the participant's denial was the only
        thing that brought 45385 forward ('it is not about the documented colonoscopy, so it does not decide')."""
        for line in (NO_POLYPS_REMOVED, NOT_REMOVED, 'We did not remove the polyp.', CONSIDERED,
                     'The polyp could not be removed.', 'The polyp was left in place.'):
            with self.subTest(line):
                text = doc(HEADER_COLON, SEEN, line)
                self.assert_d14(text, [('45378', CECUM)],
                                [read('astra', [code(text, '45385', line)]),
                                 reviewed('fable', [code(text, '45378', CECUM)],
                                          review=peer('fable', positions=()))], ['45385'])

    def test_ownership_1_another_procedures_sentence(self):
        """ownership-1: a combined report's EGD sentence quoted for a colonoscopy code (F7N, F1, F1b) and an EGD and
        ERCP report's biopsy line quoted for an ERCP code (F2): never the colonoscopy's (or the ERCP's) act."""
        self.assert_d14(F7N, [('43239', EGD7_BX), ('45378', COLON7N)], [read('astra', [code(F7N, '45380', EGD7_BX)])],
                        ['45380'])
        self.assert_d14(F1, [('43251', EGD_SNARE), ('45378', COLON_LINE)],
                        [read('astra', [code(F1, '45385', EGD_SNARE)]), read('fable', [code(F1, '43251', EGD_SNARE)])],
                        ['45385'])
        self.assert_d14(F1, [('45378', COLON_LINE)], [read('astra', [code(F1, '45385', EGD_SNARE)])], ['45385'])
        f2 = (HEAD + 'Procedure report (fictional)\nDate of service: 2026-10-14\n'
              'Place of service: Hospital outpatient\nProcedures: EGD and ERCP\n' + EGD7 + '\n' + EGD7_BX
              + '\nERCP: The duodenoscope was advanced to the major papilla. Deep biliary cannulation was achieved. A '
              'biliary sphincterotomy was performed.\n')
        sphincterotomy = 'A biliary sphincterotomy was performed.'
        self.assert_d14(f2, [('43239', EGD7_BX), ('43262', sphincterotomy)],
                        [read('astra', [code(f2, '43261', EGD7_BX)])], ['43261'])

    def test_ownership_4_a_separate_same_day_note(self):
        """ownership-4: a separate flexible sigmoidoscopy note after the colonoscopy (H1, H3, H6, H7): its biopsy is
        never the colonoscopy's 45380, and the colonoscopy's snare never the sigmoidoscopy's 45338."""
        for heading in ('Separate note: Flexible sigmoidoscopy (fictional), 2026-10-14',
                        'Separate note: Flexible sigmoidoscopy, 2026-10-14', 'Second procedure: Flexible sigmoidoscopy',
                        'Addendum - flexible sigmoidoscopy performed the same day by Dr. Vale'):
            with self.subTest(heading):
                text = COLON_FS.format(heading=heading)
                self.assert_d14(text, [('45385', CO_SNARE), ('45331', FS_BIOPSY)],
                                [read('astra', [code(text, '45380', FS_BIOPSY), code(text, '45338', CO_SNARE)]),
                                 read('fable', [code(text, '45331', FS_BIOPSY)])], ['45380', '45338'])

    def test_time_1_an_earlier_colonoscopy_s_polypectomy(self):
        """time-1: Corti selects nothing; the participant's quote of an earlier colonoscopy is no proposal, so the
        encounter stays as with no participant - no code, the gap flagged - and nothing is approvable."""
        for line in (LAST_LABEL, 'At the index colonoscopy, a 9 mm polyp was removed with a hot snare.',
                     'Most recent colonoscopy: 9 mm polyp removed with hot snare.',
                     'Index colonoscopy: 9 mm polyp removed with hot snare.',
                     'At the last colonoscopy a 9 mm polyp was removed with a hot snare.'):
            with self.subTest(line):
                text = earlier(line)
                result, alone = self.assert_d14(
                    text, [], [read('astra', [code(text, '45385', line)],
                                    services=[service(text, 'colonoscopy', line)])], ['45385'])
                self.assertEqual([p.bucket for p in result.proposals], ['alternative'])
                self.assertEqual(alone.proposals, ())
                self.assertEqual(result.completeness['state'], alone.completeness['state'])
                # a first proposed after peer review, by Fable alone (t25): the same
                peered = run(text, (), [reviewed('fable', [], review=peer('fable',
                                                                          additional=(code(text, '45385', line),)))])
                self.assertEqual([(p.bucket, p.status) for p in peered.proposals], [('alternative', 'informational')])
                self.assertIn(D14_REASON, peered.proposals[0].exclusion_reason)

    def test_time_2_beside_corti_s_correct_base_code(self):
        """time-2: Corti's 45378 on today's cecal intubation keeps its own question (never "Is 45378 reported
        separately from 45385"), and CPT Studio's own unresolved-act warning stays."""
        text = earlier(LAST_LABEL)
        for participants in ([read('astra', [code(text, '45385', LAST_LABEL)],
                                   services=[service(text, 'colonoscopy', LAST_LABEL)])],
                             [reviewed('astra', []), reviewed('fable', [], review=peer(
                                 'fable', additional=(code(text, '45385', LAST_LABEL),)))]):
            with self.subTest(len(participants)):
                result, alone = self.assert_d14(text, [('45378', CECUM_LANDMARKS)], participants, ['45385'])
                base = next(p for p in result.proposals if p.code == '45378')
                corti_base = next(p for p in alone.proposals if p.code == '45378')
                self.assertEqual([q.question for q in base.clarifications],
                                 [q.question for q in corti_base.clarifications])
                self.assertFalse(any('45385' in q.question for q in base.clarifications), base.clarifications)
                self.assertTrue(result.completeness['unresolved_items'])
                self.assertEqual(result.completeness['included_by'], alone.completeness['included_by'])

    def test_a_documented_act_a_participant_codes_stays_unresolved(self):
        """The rule's plain case (tests.test_harness_engine's MergeTests moved with it): the biopsy Corti did not code
        is documented as done, and a participant's 45380 on it is listed, never a proposal - so the biopsy stays
        unresolved and completeness is what Corti's code alone leaves."""
        text = (HEAD + 'Colonoscopy report (fictional)\nDate of service: 2026-10-14\n'
                'Place of service: Ambulatory surgery center\nProcedure: Colonoscopy\n' + CECUM + '\nA 9 mm '
                'pedunculated polyp in the sigmoid colon was removed with a hot snare.\nA separate 12 mm flat lesion '
                'in the ascending colon was biopsied with cold forceps.\n')
        result, alone = self.assert_d14(text, [('45385', 'was removed with a hot snare')],
                                        [read('astra', [code(text, '45380', 'was biopsied with cold forceps')])],
                                        ['45380'])
        self.assertEqual([(i['family'], i['act']) for i in result.completeness['unresolved_items']],
                         [('gi.colonoscopy', 'biopsy')])
        self.assertEqual(result.completeness['state'], alone.completeness['state'])

    def test_with_no_usable_corti_answer_nothing_is_a_proposal(self):
        """Corti failed (I10: it blocks only itself): the participants still read and are recorded, and none of their
        codes is a proposal."""
        text = doc(COLON, SEEN, FAILED)
        result = run(text, (), [read('astra', [code(text, '45385', FAILED)]),
                                read('fable', [code(text, '45378', CECUM)])], provider_status='failed')
        self.assertEqual([(p.code, p.bucket, p.status) for p in result.proposals],
                         [('45385', 'alternative', 'informational'), ('45378', 'alternative', 'informational')])
        self.assertTrue(all(D14_REASON in p.exclusion_reason for p in result.proposals))
        provider = next(c for c in result.encounter_checks if c.id == 'provider.status')
        self.assertIn('so there are no CPT proposals', provider.detail)  # true: none is a proposal

    def test_the_scope_and_unlocated_reasons_still_come_first(self):
        """The existing reasons apply first: a code out of the CPT scope says so, and a code none of whose quotes was
        found verbatim says that; D14's reason is given only where neither applies."""
        text = doc(COLON, SEEN, FAILED)
        result = run(text, corti(('45378', span(text, CECUM))),
                     [read('astra', [code(text, 'G0105', CECUM), code(text, '45380', 'not in the document'),
                                     code(text, '45385', FAILED)])])
        reasons = {p.code: p.exclusion_reason for p in result.proposals if p.bucket == 'alternative'}
        self.assertEqual(sorted(reasons), ['45380', '45385', 'G0105'])
        self.assertIn('HCPCS Level II code', reasons['G0105'])
        self.assertNotIn(D14_REASON, reasons['G0105'])
        self.assertIn(engine.UNLOCATED, reasons['45380'])
        self.assertNotIn(D14_REASON, reasons['45380'])
        self.assertIn(D14_REASON, reasons['45385'])


# --- D14 through the pipeline: every surface, and Corti's proposals as with no participant configured -----------------

class D14PipelineTests(MeaningCase):
    def assert_d14(self, text, only, corti=(), **participants):
        """The findings' input through the pipeline: each participant-only code is served as an alternative a member
        can do nothing with, and every Corti proposal's bucket, status, allowed actions, checks and questions are the
        participants-disabled run's on the same document."""
        encounter_id = self.scenario(text, corti, **participants)
        detail = self.detail(encounter_id)
        self.assertEqual(detail['harness']['phase'], 2)
        for value in only:
            rows = [p for p in proposals(detail) if p['code'] == value]
            self.assertEqual([(p['bucket'], p['status'], p['allowed_actions'], p['reinstatable']) for p in rows],
                             [('alternative', 'informational', [], False)], value)
            self.assertIn(D14_REASON, rows[0]['exclusion_reason'])
            made = self.post(f'/api/encounters/{encounter_id}/decisions',
                             {'proposal_id': rows[0]['id'], 'action': 'approve', 'acknowledgement': ACK,
                              'note': 'Synthetic attempt.'})
            self.assertNotEqual(made.status_code, 201, value)
            self.assertFalse(any(value in blocker for blocker in detail['readiness']['blockers']),
                             detail['readiness'])
        self.assertFalse(models.Decision.objects.filter(encounter_id=encounter_id).exists())
        self.assertEqual(corti_rows(detail), corti_rows(self.corti_alone(text, corti)))
        return encounter_id, detail

    def test_n1_every_surface_lists_the_failed_polypectomy_as_an_alternative(self):
        """negation-1, N1: Astra's 45385 on "Hot snare polypectomy failed." (Fable's peer review supporting it) was
        Ready, approvable and approved into the reviewed report, and held Corti's 45378 as included in it."""
        text = doc(COLON, SEEN, FAILED)
        encounter_id, detail = self.assert_d14(
            text, ['45385'], [('45378', CECUM)],
            astra=hp.reading(codes=[('45385', FAILED), ('45378', CECUM)], services=[colon_service(FAILED)]),
            fable=hp.reading(codes=[('45378', CECUM)], services=[colon_service(CECUM)]),
            fable_peer=hp.peer_answer(positions=[('45385', 'supports', FAILED)]))
        (item,) = [p for p in proposals(detail) if p['code'] == '45385']
        self.assertEqual((item['proposed_by'], item['support']['origin']), (['astra'], 'participant'))
        # the page: no code card for it, and its Alternatives row gives CPT Studio's reason, with no action
        page = browser('page()', detail)
        self.assertNotIn(f'id="card-{item["id"]}"', page)
        reason = json.dumps(D14_REASON)
        row = browser(f'visible(page()).split("\\n").filter(line => line.includes({reason})).join("\\n")', detail)
        self.assertIn(D14_REASON, row)
        # card-scoped (refutation round 7, falsegreen-3): the page draws a card's badge and its code on separate lines,
        # so the per-line check this replaces could never fail
        self.assertEqual(browser('cards(page()).map(visible).filter(card => card.split("\\n").includes("45385") '
                                 '&& card.includes("Ready for review")).length', detail), 0)
        # the reports: listed under ALTERNATIVES, never selectable, and never among the selections
        draft = self.download(encounter_id, 'draft', 'txt')
        listed = [line for line in draft.splitlines() if '45385' in line and 'never selectable' in line]
        self.assertEqual(len(listed), 1, draft)
        self.assertIn(D14_REASON, listed[0])
        rows = [r for r in csv_rows(self.download(encounter_id, 'draft', 'csv'))
                if r['code'] == '45385' and r['item_list'] in ('approved', 'rejected', 'undecided', 'excluded',
                                                                'alternative')]
        self.assertEqual([r['item_list'] for r in rows], ['alternative'])
        # the owner's trace: its reconciliation row is the alternative's
        trace = self.trace(encounter_id)
        lines = [line for line in self.trace_lines(trace) if line.startswith('45385 ·')]
        self.assertTrue(lines, self.trace_lines(trace))
        self.assertFalse(any('ready' in line for line in lines), lines)

    def test_negation_1_n2_to_n4(self):
        self.assert_d14(doc(COLON, SEEN, ATTEMPTED), ['45385'], [('45378', CECUM)],
                        astra=hp.reading(codes=[('45378', CECUM)], services=[colon_service(CECUM)]),
                        fable=hp.reading(codes=[('45378', CECUM)], services=[colon_service(CECUM)]),
                        fable_peer=hp.peer_answer(codes=[('45385', ATTEMPTED)]))
        self.assert_d14(doc(COLON, SEEN, NO_TISSUE), ['45380'], [('45378', CECUM)],
                        astra=hp.reading(codes=[('45380', NO_TISSUE)], services=[colon_service(CECUM)]),
                        fable=hp.reading(codes=[('45378', CECUM)], services=[colon_service(CECUM)]))
        self.assert_d14(doc(ERCP, CANNULATED, STENT_FAILED), ['43274'], [('43260', CANNULATED)],
                        astra=hp.reading(codes=[('43274', STENT_FAILED)],
                                         services=[('e1', 'ercp', 'performed', CANNULATED)]),
                        fable=hp.reading(codes=[('43260', CANNULATED)],
                                         services=[('e1', 'ercp', 'performed', CANNULATED)]))

    def test_negation_2_n10(self):
        self.assert_d14(doc(EGD, NODULE, EGD_BIOPSY_FAILED), ['43239'], [('43235', D2)],
                        astra=hp.reading(codes=[('43239', EGD_BIOPSY_FAILED)],
                                         services=[('u1', 'egd', 'performed', D2)]),
                        fable=hp.reading(codes=[('43235', D2)], services=[('u1', 'egd', 'performed', D2)]))

    def test_negation_3_n15_n17_n9(self):
        for line in (NO_POLYPS_REMOVED, NOT_REMOVED, CONSIDERED):
            with self.subTest(line):
                self.assert_d14(doc(HEADER_COLON, SEEN, line), ['45385'], [('45378', CECUM)],
                                astra=hp.reading(codes=[('45385', line)], services=[colon_service(CECUM)]),
                                fable=hp.reading(codes=[('45378', CECUM)], services=[colon_service(CECUM)]),
                                fable_peer=hp.peer_answer(positions=[('45385', 'supports', line)]))

    def test_ownership_1_f7n_and_f1b(self):
        self.assert_d14(F7N, ['45380'], [('43239', EGD7_BX), ('45378', COLON7N)],
                        astra=hp.reading(codes=[('45380', EGD7_BX)]))
        self.assert_d14(F1, ['45385'], [('45378', COLON_LINE)], astra=hp.reading(codes=[('45385', EGD_SNARE)]))

    def test_ownership_4_h1(self):
        self.assert_d14(H1, ['45380', '45338'], [('45385', CO_SNARE), ('45331', FS_BIOPSY)],
                        astra=hp.reading(codes=[('45380', FS_BIOPSY), ('45338', CO_SNARE)]),
                        fable=hp.reading(codes=[('45331', FS_BIOPSY)]))

    def test_time_1_p1_and_its_peer_review_variant(self):
        """time-1: the participant's quote of the last colonoscopy turned "No CPT code was proposed" into a Ready,
        approvable 45385 and a reviewed report; it is now listed, and the encounter reads as with Corti alone."""
        text = earlier(LAST_LABEL)
        astra = hp.reading(codes=[('45385', LAST_LABEL)], services=[colon_service(LAST_LABEL)])
        encounter_id, detail = self.assert_d14(text, ['45385'], astra=astra)
        alone = self.corti_alone(text)
        self.assertEqual(detail['assessment']['completeness']['unresolved_items'],
                         alone['assessment']['completeness']['unresolved_items'])
        self.assertFalse(detail['readiness']['reviewed'])
        # the panel says whose the listed code is, never that the provider proposed it (Corti selected nothing)
        lines = self.page_lines(detail)
        # moved by refutation round 7 (display-2): who gave it, never "independent" (it was "Each code listed below is
        # an independent participant's, offered only as an alternative."); and by round 8 (wording-3, page-3): never
        # "not the provider", which a refused or unread provider response can carry the same code against
        self.assertIn('No code is selected for approval. Each code listed below was given by Astra or Fable and is '
                      'offered only as an alternative.', lines)
        self.assertFalse(any('The provider proposed' in line for line in lines), lines)
        self.assert_d14(text, ['45385'], fable_peer=hp.peer_answer(codes=[('45385', LAST_LABEL)]))

    def test_time_2_p4_and_p6(self):
        """time-2: Corti's correct 45378 keeps its own question and CPT Studio's own unresolved-act warning stays."""
        text = earlier(LAST_LABEL)
        for participants in ({'astra': hp.reading(codes=[('45385', LAST_LABEL)], services=[colon_service(LAST_LABEL)])},
                             {'fable_peer': hp.peer_answer(codes=[('45385', LAST_LABEL)])}):
            with self.subTest(sorted(participants)):
                encounter_id, detail = self.assert_d14(text, ['45385'], [('45378', CECUM_LANDMARKS)], **participants)
                draft = self.download(encounter_id, 'draft', 'txt')
                self.assertIn('snare removal (hot snare) in the colonoscopy [not_covered]', draft)
                self.assertNotIn('Is 45378 reported separately from 45385', json.dumps(detail))


# --- negation-5: a participant's performed service where the documented-service reading reads it as not done ----------

NO_EGD = 'An upper endoscopy was not performed.'
NEGATED_REASON = ('Astra reads a performed upper endoscopy where the documented-service reading reads the upper '
                  'endoscopy as negated (“An upper endoscopy was not performed.”)')


class MissingServiceWordingTests(SimpleTestCase):
    """_Harness.missing: the reason, and the participants.services check that follows it, name the inventory's own
    negated, planned, historical or cancelled reading of the service's family where routing reads it inside the quoted
    passage, and never a reading of another passage (refutation round 7, display-1); coding completeness stays
    incomplete beside it (the safety net)."""

    def test_n11_a_service_the_inventory_reads_as_negated(self):
        text = doc(COLON, NO_EGD)
        result = run(text, corti(('45378', span(text, CECUM))),
                     [read('astra', [code(text, '45378', CECUM)],
                           services=[service(text, 'colonoscopy', CECUM), service(text, 'egd', NO_EGD)]),
                      read('fable', [code(text, '45378', CECUM)], services=[service(text, 'colonoscopy', CECUM)])])
        self.assertEqual([(s['family'], s['status']) for s in result.services['services']],
                         [('gi.colonoscopy', 'performed'), ('gi.egd', 'negated')])
        complete = result.completeness
        self.assertEqual(complete['state'], 'incomplete')
        self.assertIn(NEGATED_REASON, complete['reasons'])
        self.assertEqual([m['reason'] for m in complete['participant_services']], [NEGATED_REASON])
        check = next(c for c in result.encounter_checks if c.id == 'participants.services')
        self.assertEqual(check.status, 'warn')
        # the check follows the reason; and it says completeness is incomplete, never "until a reviewer checks the
        # document": the reviewed report keeps it incomplete (engine.reviewed_completeness)
        self.assertEqual(check.detail, 'Astra reads a performed upper endoscopy (“An upper endoscopy was not '
                                       'performed.”), where the documented-service reading reads the upper endoscopy '
                                       'as negated. The documented-service reading reads no performed service of that '
                                       'kind, so coding completeness is incomplete.')
        # moved by refutation round 10 (wording-2): the fallback's wording (it was "that the documented-service reading
        # does not read as performed")
        self.assertNotIn(NO_PERFORMED_SERVICE, json.dumps(complete))

    def test_with_no_reading_of_that_family_the_wording_is_as_before(self):
        """A family the inventory reads nothing of keeps the sentence it had: there is no reading to name."""
        text = doc(COLON, 'Esophagogastroduodenoscopy findings were reviewed with the patient.')
        quote = 'Esophagogastroduodenoscopy findings were reviewed with the patient.'
        result = run(text, corti(('45378', span(text, CECUM))),
                     [read('astra', [code(text, '45378', CECUM)], services=[service(text, 'eus', quote)])])
        (entry,) = result.completeness['participant_services']
        # moved by refutation round 10 (wording-2): only what makes the service missing (it was "... that the
        # documented-service reading does not read as performed ...")
        self.assertEqual(entry['reason'], f'Astra reads a performed endoscopic ultrasound {NO_PERFORMED_SERVICE} '
                                          f'(“{quote}”)')
        check = next(c for c in result.encounter_checks if c.id == 'participants.services')
        self.assertTrue(check.detail.startswith(f'Astra reads a performed endoscopic ultrasound (“{quote}”). The '
                                                'documented-service reading reads no performed service'), check.detail)

    def test_a_performed_reading_of_that_family_is_no_missing_service(self):
        """The control (N11C): the inventory reads the upper endoscopy as performed, so nothing is missing."""
        done = 'An upper endoscopy was performed to the second portion of the duodenum.'
        text = doc(COLON, done)
        result = run(text, corti(('45378', span(text, CECUM))),
                     [read('astra', [code(text, '45378', CECUM)], services=[service(text, 'egd', done)])])
        self.assertNotIn('participant_services', result.completeness)
        self.assertIsNone(next((c for c in result.encounter_checks if c.id == 'participants.services'), None))


# the reason for a service only a participant reads where no reading of its quote is named (refutation round 10,
# wording-2): only what makes the service missing
NO_PERFORMED_SERVICE = 'where the documented-service reading reads no performed service of that kind'


class MissingServicePipelineTests(MeaningCase):
    def test_n11_the_statement_the_reports_and_the_check(self):
        text = doc(COLON, NO_EGD)
        services = [colon_service(CECUM), ('u1', 'egd', 'performed', NO_EGD)]
        encounter_id = self.scenario(text, [('45378', CECUM)],
                                     astra=hp.reading(codes=[('45378', CECUM)], services=services),
                                     fable=hp.reading(codes=[('45378', CECUM)], services=[colon_service(CECUM)]))
        detail = self.detail(encounter_id)
        self.assertEqual(detail['coding']['state'], 'incomplete')
        self.assertIn(NEGATED_REASON, detail['coding']['statement'])
        draft = self.download(encounter_id, 'draft', 'txt')
        self.assertIn(NEGATED_REASON, draft)
        self.assertNotIn(NO_PERFORMED_SERVICE, draft)  # moved by refutation round 10 (wording-2)
        check = next(c for c in detail['assessment']['encounter_checks'] if c['id'] == 'participants.services')
        self.assertIn('where the documented-service reading reads the upper endoscopy as negated', check['detail'])


# --- ownership-5: which source passages the page says show the coded act ----------------------------------------------

C6 = (TOP + 'Procedures: Colonoscopy and upper endoscopy\nColonoscopy: The colonoscope was advanced to the cecum and '
      'the examination was completed.\nRandom biopsies were taken with cold forceps.\nEGD: The gastroscope was '
      'advanced to the second portion of the duodenum.\nA sessile polyp was removed with a hot snare.\n')
COL_BX = 'Random biopsies were taken with cold forceps.'
TODAY_BX = 'A 4 mm polyp in the transverse colon was biopsied with cold forceps.'
MATCHED = (HEAD + 'Colonoscopy report (fictional)\nDate of service: 2026-10-14\nPlace of service: Ambulatory surgery '
           'center\nProcedure: Colonoscopy\n' + CECUM + '\n' + TODAY_BX + '\n')
# P2 READ-HOLD (2026-11-03, R8 D4; tests/fixtures/gi4/declarations/cux-hold.json): an own-passage release now stands only
# where the act's placement rule gives it to the matched family alone, so C6's "Random biopsies were taken with cold
# forceps." and F7N's "Biopsies were taken with cold forceps." (no anatomy, two services) are held - the declared
# fail-closed cost. The label tests below read an own-passage release in the same combined reports through a passage
# whose anatomy places its act ("Cecal biopsies x2.", "Antral biopsies x2."), which still stands.
PLACED_COL_BX, PLACED_EGD_BX = 'Cecal biopsies x2.', 'Antral biopsies x2.'
C6_PLACED = C6.replace(COL_BX, PLACED_COL_BX, 1)
F7N_PLACED = F7N.replace(EGD7_BX, PLACED_EGD_BX, 1)
ACT_LABEL = 'Source passages that show the coded act'
SERVICE_LABEL = 'Source passages of the documented service'
NOT_THE_ACT = '— cited by the provider; does not show the coded act'


class EvidenceChipLabelTests(MeaningCase):
    """The page as it is drawn with no participant configured (the release default): a code whose act the engine read
    from its own cited passage ('own_passage': support.acts []) has the documented service's passages as its source
    passages, which do not show the act, and its cited passage is the one the status was read from."""

    def card(self, detail, value):
        (item,) = [p for p in proposals(detail) if p['code'] == value and p['bucket'] == 'selected']
        return item, browser(f'visible(cardOf(page(), {json.dumps(item["id"])}))', detail)

    def test_e1_corti_s_own_passage_release(self):
        detail = self.corti_alone(C6_PLACED, [('45380', PLACED_COL_BX),
                                              ('43251', 'A sessile polyp was removed with a hot snare.')])
        item, card = self.card(detail, '45380')
        self.assertEqual((item['support']['reason'], item['support']['acts'], item['support']['status']),
                         ('own_passage', [], 'warn'))
        self.assertNotIn(ACT_LABEL, card)
        self.assertIn(SERVICE_LABEL, card)
        self.assertNotIn(NOT_THE_ACT, card)
        self.assertIn(f'“{PLACED_COL_BX}” — cited by the provider', card)

    def test_f7n_the_egd_code_read_from_its_own_passage(self):
        detail = self.corti_alone(F7N_PLACED, [('43239', PLACED_EGD_BX), ('45378', COLON7N)])
        item, card = self.card(detail, '43239')
        self.assertEqual((item['support']['reason'], item['support']['acts']), ('own_passage', []))
        self.assertNotIn(ACT_LABEL, card)
        self.assertIn(SERVICE_LABEL, card)
        self.assertNotIn(NOT_THE_ACT, card)

    def test_the_matched_act_keeps_its_label(self):
        """The control: the inventory reads the biopsy act, and Corti cites only the procedure line - the source passage
        is the act's own, and the cited line does not show it."""
        detail = self.corti_alone(MATCHED, [('45380', 'Procedure: Colonoscopy')])
        item, card = self.card(detail, '45380')
        self.assertTrue(item['support']['acts'])
        self.assertIn(ACT_LABEL, card)
        self.assertNotIn(SERVICE_LABEL, card)
        self.assertIn(f'“Procedure: Colonoscopy” {NOT_THE_ACT}', card)
        self.assertIn(f'“{TODAY_BX}” — selected from the source by CPT Studio', card)


# --- the integration of R6-MEANING (its NEEDS 1): the readiness blocker where every code listed is a participant's -----

# moved by refutation round 7 (display-2): a code first given in peer review is never independent, so the blocker says
# who gave the codes (it was "each code listed is an independent participant's, offered only as an alternative"); moved
# by round 8 (wording-3): it no longer says "not the provider", which a second review not yet read can make false (it
# was "each code listed was given by Astra or Fable, not the provider, and is offered only as an alternative")
PARTICIPANTS_ONLY = ('No code is selected for approval: each code listed was given by Astra or Fable and is offered only '
                     'as an alternative')


class D14BlockerTests(MeaningCase):
    """D14 makes reachable an assessment whose every code is a participant's alternative: time-1 p1, where Corti selects
    nothing. review.readiness still said "No code is selected for approval: the provider proposed only codes that were
    excluded or offered as alternatives" there - false, Corti proposed none of them - and the page's Still needed, the
    draft TXT's Review status and the reviewed report's refusal print that blocker. It is now said as the panel says it
    (app.js emptySelectionCopy); a provider code beside the participants' keeps the provider's sentence."""

    def assert_blocker(self, encounter_id, said, unsaid):
        detail = self.detail(encounter_id)
        self.assertIn(said, detail['readiness']['blockers'])
        self.assertFalse(any(unsaid in blocker for blocker in detail['readiness']['blockers']), detail['readiness'])
        status = browser('app.exportStatusText(data)', detail)
        self.assertIn(f'Still needed: {said}', status)
        self.assertNotIn(unsaid, status)
        txt = self.download(encounter_id).splitlines()
        # the draft TXT's Review status block: its heading line, then one line per blocker, up to the blank line
        start = txt.index('Review status: not complete')
        status_block = txt[start:txt.index('', start)]
        self.assertIn(f'  - {said}', status_block)
        self.assertFalse(any(unsaid in line for line in status_block), status_block)
        refused = self.post(f'/api/encounters/{encounter_id}/reports', {'kind': 'reviewed', 'fmt': 'txt'})
        self.assertEqual(refused.status_code, 409, refused.content)
        self.assertIn(said, refused.json()['details']['blockers'])
        return detail

    def test_time_1_p1_says_whose_the_listed_code_is(self):
        text = earlier(LAST_LABEL)
        astra = hp.reading(codes=[('45385', LAST_LABEL)], services=[colon_service(LAST_LABEL)])
        encounter_id = self.scenario(text, astra=astra)
        detail = self.assert_blocker(encounter_id, PARTICIPANTS_ONLY, 'provider proposed')
        # and nowhere in the draft TXT does CPT Studio say the provider proposed a code
        self.assertNotIn('provider proposed', self.download(encounter_id))
        self.assertEqual([(p['code'], p['bucket'], (p.get('support') or {}).get('origin')) for p in proposals(detail)],
                         [('45385', 'alternative', 'participant')])

    def test_a_provider_code_beside_them_keeps_the_provider_s_sentence(self):
        # control: Corti's own code is listed too (G0121, outside the GI profiles, is excluded and cannot be reinstated:
        # nothing is reviewable), so the provider did propose a code that was excluded - its sentence stands, and the
        # participants' does not
        text = earlier(LAST_LABEL)
        astra = hp.reading(codes=[('45385', LAST_LABEL)], services=[colon_service(LAST_LABEL)])
        encounter_id = self.scenario(text, corti=[('G0121', CECUM_LANDMARKS)], astra=astra)
        detail = self.detail(encounter_id)
        self.assertEqual(sorted((p['code'], p['bucket'], (p.get('support') or {}).get('origin') or 'primary')
                                for p in proposals(detail)),
                         [('45385', 'alternative', 'participant'), ('G0121', 'excluded', 'primary')])
        self.assert_blocker(encounter_id, 'No code is selected for approval: the provider proposed only codes that were '
                            'excluded or offered as alternatives', 'given by Astra or Fable')


# --- the integration of R6-MEANING (its NEEDS 2): the source panel's highlight title is ownership-5's label ------------

def title_codes(title):
    """A highlight's title as {what it says: the codes it says it of}: "Evidence for", "Passage of the documented service
    for", and that clause "not checked against the coded act". The codes of a clause are listed in the order the API
    serves the proposals, which is not fixed, so they are read as a set."""
    said = {}
    for clause in title.split('; '):
        for prefix in ('Evidence for ', 'Passage of the documented service for '):
            if clause.startswith(prefix):
                codes, kind = clause[len(prefix):], prefix.strip()
                if codes.endswith(', not checked against the coded act'):
                    codes, kind = codes[:-len(', not checked against the coded act')], f'{kind} (not checked)'
                said.setdefault(kind, set()).update(codes.split(', '))
    return said


def marks(detail):
    """Each highlighted passage of the source panel as the page draws it: (its keys, its title, its text)."""
    found = browser('[...page().matchAll(/class="evidence-mark" data-evidence="[^"]*" data-keys="([^"]*)" '
                    'title="([^"]*)">([^<]*)<\\/button>/g)].map(m => [m[1], m[2], m[3]])', detail)
    return [(keys.split(' '), unescape(title), unescape(text)) for keys, title, text in found]


class SourceHighlightTitleTests(MeaningCase):
    """ownership-5's chip label has a second reader: the source panel titles every highlighted passage, and gave the
    documented service's passages of an own-passage support "Evidence for <code>" - the claim the chip no longer makes.
    Each such passage is now titled as the chip labels it; the act's own passages, and the provider's cited passages,
    keep "Evidence for"."""

    card = EvidenceChipLabelTests.card

    def titles(self, detail, item):
        """The titles of the highlighted pieces of ``item``'s source passages (keys <id>:s<n>) and of its cited ones."""
        source, cited = set(), set()
        for keys, title, _ in marks(detail):
            for key in keys:
                if key.startswith(f'{item["id"]}:s'):
                    source.add(title)
                elif key.startswith(f'{item["id"]}:'):
                    cited.add(title)
        return source, cited

    def test_e1_and_f7n_the_service_s_passages(self):
        for text, corti, value in ((C6_PLACED, [('45380', PLACED_COL_BX),
                                                ('43251', 'A sessile polyp was removed with a hot snare.')], '45380'),
                                   (F7N_PLACED, [('43239', PLACED_EGD_BX), ('45378', COLON7N)], '43239')):
            with self.subTest(value):
                detail = self.corti_alone(text, corti)
                item, _ = self.card(detail, value)
                source, cited = self.titles(detail, item)
                self.assertTrue(item['support']['source'])
                self.assertTrue(source)
                for title in source:
                    said = title_codes(title)
                    self.assertIn(value, said.get('Passage of the documented service for', set()), title)
                    self.assertNotIn(value, said.get('Evidence for', set()), title)
                self.assertTrue(cited)
                for title in cited:
                    self.assertIn(value, title_codes(title).get('Evidence for', set()), title)

    def test_the_matched_act_s_passage_keeps_evidence_for(self):
        detail = self.corti_alone(MATCHED, [('45380', 'Procedure: Colonoscopy')])
        item, _ = self.card(detail, '45380')
        source, _ = self.titles(detail, item)
        self.assertTrue(source)
        for title in source:
            said = title_codes(title)
            self.assertIn('45380', said.get('Evidence for', set()), title)
            self.assertNotIn('45380', said.get('Passage of the documented service for', set()), title)


# --- the integration of R6-MEANING: participants.summary's closing sentence -------------------------------------------

# moved by refutation round 7 (d14-3, display-3): each clause is the engine's own rule - a provider code excluded for
# scope or evidence carries no participant's code, and a code in no code's shape is counted, never listed; moved by round
# 8 (wording-4): the first clause names merge's two kinds of proposal - a code the provider only listed, or that its
# second review selected and CPT Studio did not add, carries none (it was "a participant's code that the proposal
# provider also proposed, in scope and with an exact passage, is recorded on that proposal"); moved by round 9
# (wording-4): a selection in a response refused whole is no selection merge sees, so the clause names a response CPT
# Studio used (it was "... selected, in scope and with an exact passage, or that its bounded second review added ...")
NEVER_DECIDE = ("A participant never decides a status and agreement never promotes a code: a participant's code that the "
                'proposal provider selected, in scope and with an exact passage, in a response CPT Studio used, or that its '
                "bounded second review added as a proposal, is recorded on that proposal, which CPT Studio's own readers "
                "judge on the provider's passages alone; any other code a participant gives in a CPT or HCPCS code's "
                'shape, including one the provider only listed, one its second review listed without adding and one in a '
                'provider response CPT Studio did not use, is listed as an alternative and never added as a proposal, and '
                "one in neither shape is counted and never listed; and a participant's questions are notes that never "
                'block.')
SAME_RULES = "by the same rules as the proposal provider's"


class SummarySentenceTests(MeaningCase):
    """participants.summary closed with "each code it proposes is judged by CPT Studio's own readers, with exact
    evidence, by the same rules as the proposal provider's" - false since D14 of a code only a participant gave, which
    no reader reads: on time-1 p1 the same report lists Astra's 45385 as never added as a proposal. It now says what the
    engine does (HARNESS.md I3 as amended for D14), on the API, the page's Checks tab and the TXT report (the CSV carries
    no encounter check)."""

    def test_time_1_p1_every_surface(self):
        text = earlier(LAST_LABEL)
        astra = hp.reading(codes=[('45385', LAST_LABEL)], services=[colon_service(LAST_LABEL)])
        encounter_id = self.scenario(text, astra=astra)
        detail = self.detail(encounter_id)
        self.assertTrue(self.summary(detail).endswith(f' {NEVER_DECIDE}'), self.summary(detail))
        self.assertNotIn(SAME_RULES, self.summary(detail))
        checks = self.page_lines(detail, 'checks')
        self.assertTrue(any(NEVER_DECIDE in line for line in checks))
        self.assertFalse(any(SAME_RULES in line for line in checks))
        # the TXT prints the encounter's checks; the CSV carries per-code rows only, so neither sentence is in it
        report = self.download(encounter_id)
        self.assertIn(NEVER_DECIDE, report)
        self.assertNotIn(SAME_RULES, report)

    def test_a_code_corti_also_proposed(self):
        encounter_id = self.scenario(COLON, corti=[('45378', CECUM)], astra=hp.reading(codes=[('45378', CECUM)]))
        detail = self.detail(encounter_id)
        self.assertEqual([(p['code'], p['bucket'], p['proposed_by']) for p in proposals(detail)],
                         [('45378', 'selected', ['corti', 'astra'])])
        self.assertTrue(self.summary(detail).endswith(f' {NEVER_DECIDE}'), self.summary(detail))
