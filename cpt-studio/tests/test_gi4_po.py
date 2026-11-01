"""GI round 4, package PO: the second-review offer (validation/engine.py: _routing_agrees and its _po_ helpers).

An unresolved item the installed rule does not offer is offered - the flag only: a member still asks, once per revision
and date, and no stage sends anything (tests/test_gi4_po_state.py) - when routing does not contradict the
documented-service reading and the document's own head makes it today's procedure report: PO-1, routing reads the item's
family only silently (h4-02); PO-2, routing's not-today reading of the item's own passage comes only from a section that
reaches it across a heading-like line the layout does not read (h4-05). Every expectation here was declared before the
code (tests/fixtures/gi4/declarations/po.json): the regression replay's offers per member state, the H4 rows read with
their own and with an empty provider answer, and the guard rows, whose texts the declaration pins by sha256.

The declaration's dated amendment (amendment_20261101), also committed before its code, adds five holds the package's
own refutation earned - A1 a head field labelled sedation or anaesthesia, A2 the family named on a title line of the
head, A3 (PO-2) a passage of the item on such a title line, A4 (PO-2) no unread heading naming another occurrence
anywhere within the reach, A5 no statement that a procedure was called off or not performed which names none - and
the AMENDED_ROWS that pin each hold (their texts pinned by sha256 there too).

Each tests/test_gi4_po_mutants.py PO_MUTANTS entry removes one guard and is killed by a test HERE (H6, run against
sealed copies through the harness's mutant machinery). The registry and its anchor check live in that other module on
purpose: a check that every anchor occurs in this tree fails on every mutated copy, so inside the detector it would
"kill" every mutant by construction. Offline: nothing is sent and no database is read. Every document is synthetic.
"""
import dataclasses
import datetime as dt
import json
from pathlib import Path
from types import SimpleNamespace

from django.test import SimpleTestCase

from ops.gi4 import battery, boot, regression, replay
from studio.gi import detect, sections
from studio.gi import services as gi_services
from studio.types import Span
from studio.validation import engine, reconcile

FIXTURES = Path(__file__).resolve().parent / 'fixtures' / 'gi4'
DECLARED = json.loads((FIXTURES / 'declarations' / 'po.json').read_text(encoding='utf-8'))
PD_DECLARED = json.loads((FIXTURES / 'declarations' / 'pd.json').read_text(encoding='utf-8'))
PIN = json.loads((FIXTURES / 'pins' / 'replay.json').read_text(encoding='utf-8'))
DOCS = regression.load_fixtures()
# The Wave 1 integration (all six packages in one tree). The H4 rows package PA added after PO branched, which PO's
# declaration predates: their offers are not moved by any Wave 1 package (measured on installed 80df1831d168, on each
# package's own tree and on the integrated tree, with the row's own answer and with an empty one).
PA_ROWS_OFFERS = {
    'PA1 disagreeing second reader: a plan line it reads nothing in (EUS)': {
        'own': [], 'empty': [['gi.eus', '', 'no_proposal', True]]},
    'PA2 disagreeing second reader: "No further" read as uncertain (EUS)': {
        'own': [], 'empty': [['gi.eus', '', 'no_proposal', True]]},
    'PA3 agreeing second reader: a headed prior-procedures line (ERCP)': {
        'own': [['gi.ercp', '', 'no_proposal', True]], 'empty': [['gi.ercp', '', 'no_proposal', True]]},
}
# UNDECLARED: two offer-battery cells the integrated tree moves where NO declaration names the movement (po.json pins
# them otherwise; pa.json and pv1.json never ran this battery). Recorded by the Wave 1 integration, not declared away:
# po.json is unchanged and stays the expectation for every other cell, and these two are pinned at the measured value,
# with PO's declared value checked to differ, until a declaration or a ruling settles them.
#   S3h, own answer: PA's declared hold of 43259 (pa.json: excluded -> selected/needs_clarification) gives the EUS family
#     a held proposal, so the 'no_proposal' item PO declared its offer on no longer exists (PA alone measures the same).
#   telephone-only time, empty answer: PV1's C4 hold (pv1.json: telephone wording holds every E/M reading) no longer
#     reads the visit as performed, so installed's offered 'no_proposal' office-visit item is gone (PV1 alone the same).
UNDECLARED_OFFERS = {
    ('S3h h4-05 counterfactual, EUS code citing the narrative', 'own'): [],
    ('telephone-only time', 'empty'): [],
}
H402, H405 = DOCS['h4-02']['text'], DOCS['h4-05']['text']
B = 'SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\n'
FILL = ''.join(f'Line {i} of the outside summary lists medications and allergies in detail.\n' for i in range(8))
COPIED = ('Colonoscopy at Mercy GI.\nCecum: normal.\nTerminal ileum: normal.\nThe entire colon was examined. A 10 mm polyp '
          'was removed with a hot snare.\n\nAssessment\nAdenoma history.\n')
CONCL = '\nEndosonographic Conclusion\n'
FILLER = ''.join(f'Filler sentence {i} repeats that the gland was seen well.\n' for i in range(210))
# (text, codes): the guard rows the declaration pins (codes: (code, quote); none = an empty provider answer)
ROWS = {
    'G-head clinic note, copied colonoscopy': (B + 'Hepatology Clinic Note\nDate of service: 10/20/2026\n\nSummary of '
                                               'outside records\nThe patient brought copies from Mercy GI.\n' + FILL
                                               + COPIED, ()),
    'G-around booking with head fields': (B + 'Endoscopy Booking\nDate of service: 10/20/2026\nEndoscopist: Synthetic '
                                          'Endoscopist, MD (fictional)\nSedation: propofol by CRNA, planned\n\nSummary of '
                                          'outside records\nThe patient brought copies from Mercy GI.\n' + FILL + COPIED,
                                          ()),
    'G-reach h4-05, 210 filler lines': (H405.replace(CONCL, '\n' + FILLER + CONCL), ()),
    'G-occurrence h4-05, previous summary line': (H405.replace(CONCL, '\nPrevious Endosonography Summary' + CONCL), ()),
    'G-contradiction h4-05, repeat EUS not done': (H405.replace('Repeat MRI with MRCP in 12 months.',
                                                                'Repeat MRI with MRCP in 12 months. A repeat EUS was not '
                                                                'performed.'), ()),
    'G-unread h4-05, directly headed HPI line': (H405.replace('\nPrior Studies\n', '\nHPI\nEndosonography of the '
                                                              'pancreas.\n\nPrior Studies\n', 1), ()),
    'G-evidence h4-02, repeat biopsies planned': (H402.replace(
        '2. Rectosigmoid inflammation of the same pattern; biopsied.',
        '2. Rectosigmoid inflammation of the same pattern; biopsied, and repeat biopsies are planned in six weeks.'),
        (('45330', 'Flexible sigmoidoscope'),)),
    'G-atleast P00160 runaway history, title only': (
        B + 'Surveillance Colonoscopy\nHensley Narrows Surgery Center (fictional)\nFacility category: ambulatory '
        'surgical center, POS 24\nProcedure date: October 13, 2026\nPatient: Petronella Szymanski-Abara (fictional), 64 '
        'years\nGastroenterologist: Lazare Sobczak-Muir, DO (fictional)\nSedation: propofol by Wynona Tarkington-Ezeh, '
        'CRNA (fictional)\nPrior Studies\nEarlier colonoscopy (this service): October 13, 2024 - two small polyps, '
        'removed by cold snare.\nWhy It Was Done\nSix kilograms of unintended weight loss over five months.\nObservations '
        'by Segment\nThe colonoscope was advanced to the cecum. Cold forceps biopsies were taken from the ascending '
        'colon.\nAt a Glance\n1. Biopsies taken; results to follow.\nPlan\nRepeat colonoscopy booked for November 4, '
        '2026.\nReport authenticated: Lazare Sobczak-Muir, DO (fictional), October 13, 2026 11:52\n', ()),
    'P-h4-02': (H402, ()),
    'P-h4-05': (H405, ()),
}
# The amendment's rows (declaration amendment_20261101): each hold's killing row, the classes it closes, and two
# positive rows A5 must not hold.
OUTSIDE = '\n\nSummary of outside records\nThe patient brought copies from Mercy GI.\n' + FILL + COPIED
COLON_HEAD = ('Surveillance Colonoscopy\nHensley Narrows Surgery Center (fictional)\nProcedure date: October 13, 2026\n'
              'Gastroenterologist: Lazare Sobczak-Muir, DO (fictional)\nSedation: propofol by Wynona Tarkington-Ezeh, CRNA '
              '(fictional)\n')
PRIOR_EUS = ('Prior Studies\nEndoscopic ultrasound at Tamsworth (fictional) on 2025-04-09.\nScope Passage and Views\nA linear '
             'echoendoscope was introduced by mouth. Views were obtained from the duodenal bulb and the stomach.\n'
             'Endosonographic Conclusion\nBranch-duct cyst of the pancreatic body, 19 mm.\n')
COLON_BODY = ('Observations by Segment\nThe colonoscope was advanced to the cecum. Cold forceps biopsies were taken from the '
              'ascending colon.\nAt a Glance\n1. Biopsies taken; results to follow.\nReport authenticated: Lazare '
              'Sobczak-Muir, DO (fictional), October 13, 2026 11:52\n')


def once(text, old, new):
    """``text`` with the one occurrence of ``old`` replaced (a row that no longer applies fails loudly)."""
    assert text.count(old) == 1, old
    return text.replace(old, new)


AMENDED_ROWS = {
    'A-sedation clinic note titled with the family, Attending field': (
        B + 'Colonoscopy Follow-up Visit\nDate of service: 10/20/2026\nAttending: Synthetic Attending, MD (fictional)'
        + OUTSIDE, ()),
    'A-sedation clinic note titled with the family, sedation named in a sentence': (
        B + 'Colonoscopy Follow-up Visit\nShe tolerated sedation poorly in the past.\nDate of service: 10/20/2026'
        + OUTSIDE, ()),
    'A-sedation consult note, endoscopist field': (
        B + 'GI Consultation\nDate of service: 10/20/2026\nEndoscopist: Synthetic Endoscopist, MD (fictional)' + OUTSIDE,
        ()),
    'A-sedation compact clinic note, copied record at the top': (
        B + 'Hepatology Clinic Note\nAttending: Synthetic Attending, MD (fictional)\nColonoscopy at Mercy GI\nCecum: '
        'normal.\nThe entire colon was examined. A 10 mm polyp was removed with a hot snare.\n\nAssessment\nAdenoma '
        'history.\n', ()),
    'A-head h4-05 without the head words the PS guard reads': (
        once(once(H405, 'Performing endoscopist: ', 'Report author: '),
             'Anesthetic care: monitored anesthesia care by the Tamsworth Department of Anesthesiology (fictional)',
             'Anesthetic care: MAC by the Tamsworth department (fictional)'), ()),
    'A-around colonoscopy records review with head fields': (
        B + 'Colonoscopy Records Review\nDate of service: 10/20/2026\nEndoscopist: Synthetic Endoscopist, MD '
        '(fictional)\nSedation: none' + OUTSIDE, ()),
    'A-title colonoscopy report, copied EGD block': (
        B + COLON_HEAD + '\nObservations\nThe colonoscope was advanced to the cecum. The colon was normal.\n\nCopied from '
        'the referral packet\nEGD at Mercy GI.\nThe duodenum was normal. A 6 mm gastric polyp was removed with a hot '
        'snare.\nReport authenticated: Lazare Sobczak-Muir, DO (fictional), October 13, 2026 11:52\n', ()),
    'A-title short head, a copied EGD line after the head fields': (
        B + 'Surveillance Colonoscopy\nGastroenterologist: Lazare Sobczak-Muir, DO (fictional)\nSedation: propofol by a '
        'CRNA (fictional)\nEGD at Mercy GI\nThe duodenum was normal. A 6 mm gastric polyp was removed with a hot snare.\n'
        'Observations\nThe colonoscope was advanced to the cecum. The colon was normal.\n', ()),
    'A-evtitle colonoscopy report, EUS review named in the title, copied EUS block': (
        B + once(COLON_HEAD, 'Surveillance Colonoscopy\n', 'Surveillance Colonoscopy and Endosonography Review\n')
        + PRIOR_EUS + COLON_BODY, ()),
    'A-evtitle colonoscopy report, copied prior EUS block': (B + COLON_HEAD + PRIOR_EUS + COLON_BODY, ()),
    'A-between h4-05, an unread heading naming an earlier EUS far above': (
        once(H405, 'What the Echoendoscope Showed', 'What the Earlier Echoendoscope Showed'), ()),
    'A-between h4-05, an earlier EUS report heading opens the runaway part': (
        once(H405, 'Question to Answer', 'Earlier EUS Report Excerpt'), ()),
    'A-occurrence h4-05, a lowercase outside-records line above the evidence': (
        once(H405, CONCL, '\nOutside records' + CONCL), ()),
    'A-notdone h4-05, the procedure cancelled before sedation': (
        once(H405, 'Is the possible nodule on MRI tissue or mucin?\n', 'Is the possible nodule on MRI tissue or mucin?\n'
             'The procedure was cancelled before sedation because the platelet count was 18,000.\n'), ()),
    'A-notdone h4-05, no endoscopic procedure performed today': (
        once(H405, 'Is the possible nodule on MRI tissue or mucin?\n', 'Is the possible nodule on MRI tissue or mucin?\n'
             'No endoscopic procedure was performed today.\n'), ()),
    'A-notdone h4-05, procedure not performed': (
        once(H405, 'Is the possible nodule on MRI tissue or mucin?\n', 'Is the possible nodule on MRI tissue or mucin?\n'
             'Procedure not performed.\n'), ()),
    'A-notdone h4-02, the lower examination deferred': (
        once(H402, 'Upper Tract Observations\n', 'Lower examination deferred to next week.\nUpper Tract Observations\n'),
        ()),
    'A-notdone h4-02, a cancelled status line': (
        once(H402, 'Upper Tract Observations\n', 'Status: Cancelled - the patient had eaten breakfast.\nUpper Tract '
             'Observations\n'), ()),
    'A-positive h4-05, no other procedures were performed': (
        once(H405, 'no fine-needle aspiration or biopsy was performed.', 'no fine-needle aspiration or biopsy was '
             'performed. No other procedures were performed.'), ()),
    'A-positive h4-02, an earlier procedure cancelled in September': (
        once(H402, 'Upper Tract Observations\n', 'His first procedure in September was cancelled because of a low '
             'platelet count.\nUpper Tract Observations\n'), ()),
}
AMENDED = DECLARED['amendment_20261101']['guard_rows']['rows']


def offers_of(text, codes=(), user_values=None):
    """[family, act, reason, offered] per unresolved item, as the stages read the text (analyze child, the member's
    answer merged, assess child) with a synthetic provider answer: ``codes`` = ((code, exact quote), ...)."""
    m = battery.modules()
    user_values = user_values or {}
    document_facts, day, _ = m.jobs._analyze_child(text, user_values, 1000)
    facts = m.jobs._merged_facts(document_facts, user_values)
    context = m.jobs.context_facts(SimpleNamespace(facts=facts))
    response = battery.response(m, text, [(code, quote, '') for code, quote in codes])
    _, result = m.jobs._assess_child(text, day, (m.PageSpan(1, 0, len(text)),), context, response, m.Lookup([], {}),
                                     'succeeded', 'ok', ())
    m.jobs.release_routing_caches()
    return [[u['family'], u['act'] or '', u['reason'], bool(u['second_review'])]
            for u in result.completeness['unresolved_items']]


def declared(offers):
    return [[family, act, reason, po] for family, act, reason, _, po in offers]


def amended(offers):
    """An amendment row's offers as the amended rule makes them: [family, act, reason, installed offer, committed offer
    (0f2512471), amended offer] -> [family, act, reason, amended offer]."""
    return [[family, act, reason, po] for family, act, reason, _, _, po in offers]


class RegressionOfferTests(SimpleTestCase):
    """H1's offers: h4-02 (PO-1) and h4-05 (PO-2) move as declared in every member state; no other document's do."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.result = replay.replay(DOCS)

    def offers(self, doc_id, label):
        return sorted([o['family'], o['reason'], bool(o['second_review'])]
                      for o in self.result['documents'][doc_id]['states'][label]['offers'])

    def test_the_declared_documents_offer_in_every_member_state(self):
        for doc_id in ('h4-02', 'h4-05'):
            want = DECLARED['replay'][doc_id]
            # The Wave 1 integration: a state package PD declares newly held (pd.json) is assessed as a member-date hold
            # (no provider answer), so each item's reason there is 'no_proposal'; the offer flag stays PO's
            pd = PD_DECLARED['replay'].get(doc_id)
            held = set(pd['newly_held']) if isinstance(pd, dict) else set()
            self.assertEqual(sorted(self.result['documents'][doc_id]['states']), sorted(want['states']), doc_id)
            for label in want['states']:
                self.assertEqual(self.offers(doc_id, label),
                                 sorted([f, 'no_proposal' if label in held else r, po] for f, r, _, po in want['offers']),
                                 (doc_id, label))

    def test_no_other_document_moves(self):
        for doc_id in DECLARED['replay']['unchanged']:
            for label, state in PIN['documents'][doc_id]['states'].items():
                self.assertEqual(self.offers(doc_id, label), state['offers'], (doc_id, label))

    def test_the_offer_is_only_a_flag(self):
        """Nothing but the flag moves on the declared documents: the same items, questions and completeness."""
        for doc_id in ('h4-02', 'h4-05'):
            for label, state in PIN['documents'][doc_id]['states'].items():
                now = self.result['documents'][doc_id]['states'][label]
                self.assertEqual(sorted([o['family'], o['reason']] for o in now['offers']),
                                 sorted(o[:2] for o in state['offers']), (doc_id, label))
                self.assertEqual([now['completeness']['state'], now['completeness']['unresolved']],
                                 state['completeness'], (doc_id, label))
                self.assertEqual(sorted([q[0], q[1], q[2]] for q in now['clarifications']), state['questions'])


class OfferBatteryTests(SimpleTestCase):
    """The H4 rows read with their own and with an empty provider answer: only S3h's EUS moves (PO-2)."""

    def test_every_row_offers_as_declared(self):
        rows = DECLARED['offer_battery']['rows']
        self.assertEqual(sorted(set(battery.CASES) - set(rows)), sorted(PA_ROWS_OFFERS))  # PA's rows only
        self.assertEqual(sorted(set(rows) - set(battery.CASES)), [])
        for name, (text, codes) in battery.CASES.items():
            got = {'own': offers_of(text, [(code, quote) for code, quote, _ in codes]), 'empty': offers_of(text)}
            for answer in ('own', 'empty'):
                with self.subTest(name, answer=answer):
                    if name in PA_ROWS_OFFERS:
                        self.assertEqual(got[answer], PA_ROWS_OFFERS[name][answer])
                    elif (name, answer) in UNDECLARED_OFFERS:
                        self.assertEqual(got[answer], UNDECLARED_OFFERS[(name, answer)])
                        self.assertNotEqual(got[answer], declared(rows[name][answer]))  # still unlike PO's declaration
                    else:
                        self.assertEqual(got[answer], declared(rows[name][answer]))


class GuardRowTests(SimpleTestCase):
    """Each guard's killing row offers nothing; the positive controls offer (the texts are pinned by the declaration)."""

    def check(self, name):
        text, codes = ROWS[name]
        row = DECLARED['guard_rows']['rows'][name]
        self.assertEqual(boot.sha256_text(text), row['text_sha256'], name)
        self.assertEqual([list(c) for c in codes], row['codes'], name)
        self.assertEqual(offers_of(text, codes), declared(row['offers']), name)

    def test_the_rows_are_the_declared_ones(self):
        self.assertEqual(sorted(ROWS), sorted(DECLARED['guard_rows']['rows']))

    def test_a_copied_procedure_in_a_note_without_a_procedure_head(self):  # also held by A1 and A2 (amendment)
        self.check('G-head clinic note, copied colonoscopy')

    def test_a_booking_note_whose_head_names_the_endoscopist(self):  # also held by A2 (amendment)
        self.check('G-around booking with head fields')

    def test_a_heading_beyond_the_reach_is_never_a_found_line(self):  # kills po-runaway-within-reach
        self.check('G-reach h4-05, 210 filler lines')

    def test_an_unread_line_naming_another_occurrence(self):  # also held by A4 (amendment)
        self.check('G-occurrence h4-05, previous summary line')

    def test_a_denied_mention_of_the_family(self):  # kills po2-family-contradicts
        self.check('G-contradiction h4-05, repeat EUS not done')

    def test_a_directly_headed_not_today_mention(self):  # kills po-runaway-unread-heading
        self.check('G-unread h4-05, directly headed HPI line')

    def test_an_item_passage_read_as_planned(self):  # kills po1-evidence-says-nothing
        self.check('G-evidence h4-02, repeat biopsies planned')

    def test_evidence_only_silent_beside_another_occasions_mentions(self):  # kills po2-at-least-one, po1-family-silent
        self.check('G-atleast P00160 runaway history, title only')

    def test_the_positive_controls(self):
        self.check('P-h4-02')
        self.check('P-h4-05')


class AmendedGuardRowTests(SimpleTestCase):
    """The amendment's rows (declaration amendment_20261101): each hold's killing row offers nothing, nor do the classes
    it closes; A5 does not hold the two positive rows (the texts are pinned by the declaration)."""

    def check(self, name):
        text, codes = AMENDED_ROWS[name]
        row = AMENDED[name]
        self.assertEqual(boot.sha256_text(text), row['text_sha256'], name)
        self.assertEqual([list(c) for c in codes], row['codes'], name)
        self.assertEqual(offers_of(text, codes), amended(row['offers']), name)

    def test_the_rows_are_the_declared_ones(self):
        self.assertEqual(sorted(AMENDED_ROWS), sorted(AMENDED))
        self.assertFalse(set(AMENDED_ROWS) & set(ROWS))

    def test_a_follow_up_visit_with_an_attending_field(self):  # kills po-document-sedation
        self.check('A-sedation clinic note titled with the family, Attending field')

    def test_sedation_named_in_a_sentence_is_no_sedation_field(self):  # kills po-sedation-label
        self.check('A-sedation clinic note titled with the family, sedation named in a sentence')

    def test_consult_and_clinic_notes_with_copied_records(self):  # held by A1 and A2
        self.check('A-sedation consult note, endoscopist field')
        self.check('A-sedation compact clinic note, copied record at the top')

    def test_a_head_without_the_words_the_ps_guard_reads(self):  # kills po-document-head
        self.check('A-head h4-05 without the head words the PS guard reads')

    def test_a_records_review_titled_with_the_family(self):  # kills po-document-around
        self.check('A-around colonoscopy records review with head fields')

    def test_a_family_named_only_in_a_copied_block(self):  # kills po-family-on-title
        self.check('A-title colonoscopy report, copied EGD block')

    def test_a_copied_line_after_the_head_fields_is_no_title(self):  # kills po-title-before-fields
        self.check('A-title short head, a copied EGD line after the head fields')

    def test_a_family_the_title_names_but_the_inventory_takes_from_a_copied_block(self):  # kills po2-evidence-on-title
        self.check('A-evtitle colonoscopy report, EUS review named in the title, copied EUS block')

    def test_a_prior_study_copied_under_unread_headings(self):  # held by A2 and A3
        self.check('A-evtitle colonoscopy report, copied prior EUS block')

    def test_an_unread_heading_naming_another_occurrence_far_above(self):  # kills po-runaway-occurrence-between
        self.check('A-between h4-05, an unread heading naming an earlier EUS far above')
        self.check('A-between h4-05, an earlier EUS report heading opens the runaway part')

    def test_a_lowercase_occurrence_line_right_above(self):  # kills po-runaway-occurrence
        self.check('A-occurrence h4-05, a lowercase outside-records line above the evidence')

    def test_a_procedure_called_off_or_not_performed_naming_none(self):  # kills po-document-not-done
        self.check('A-notdone h4-05, the procedure cancelled before sedation')
        self.check('A-notdone h4-05, no endoscopic procedure performed today')
        self.check('A-notdone h4-05, procedure not performed')
        self.check('A-notdone h4-02, the lower examination deferred')
        self.check('A-notdone h4-02, a cancelled status line')

    def test_no_other_procedures_is_no_statement_that_none_was_done(self):  # kills po-not-done-other
        self.check('A-positive h4-05, no other procedures were performed')

    def test_an_earlier_encounter_cancelled_with_its_own_time_is_not_held(self):
        self.check('A-positive h4-02, an earlier procedure cancelled in September')


class RoutingAgreesUnitTests(SimpleTestCase):
    """_routing_agrees on real readings of a real text, with the item or routing's reading varied by hand."""

    def read(self, text, day):
        routing = detect.route(text, day)
        inventory = gi_services.build(text, service_date=day, routing=routing, context_facts={})
        unresolved, _, _ = reconcile.reconcile(inventory, [])
        return routing, inventory, unresolved

    def tearDown(self):
        __import__('studio.jobs', fromlist=['x']).release_routing_caches()

    def item(self, unresolved, family, act=''):
        return next(u for u in unresolved if u.family == family and u.act == act)

    def span(self, text, needle):
        start = text.index(needle)
        return Span(start, start + len(needle), needle)

    def test_a_family_routing_never_names_is_no_silent_reading(self):  # A2: no title mention, no offer
        routing, inventory, unresolved = self.read(H402, None)
        u = self.item(unresolved, 'gi.egd')  # no passage of its own: only the family reading can decide
        self.assertTrue(engine._routing_agrees(u, inventory, routing, H402, None))
        unnamed = dataclasses.replace(routing, findings=tuple(f for f in routing.findings if f.family != 'gi.egd'))
        self.assertFalse(engine._routing_agrees(u, inventory, unnamed, H402, None))

    def test_h405_offers_under_po2(self):
        day = dt.date(2026, 10, 15)
        routing, inventory, unresolved = self.read(H405, day)
        self.assertTrue(engine._routing_agrees(self.item(unresolved, 'gi.eus'), inventory, routing, H405, day))

    def test_an_item_passage_with_its_own_time_word_is_no_runaway_reading(self):  # kills po-runaway-section-only
        day = dt.date(2026, 10, 15)
        routing, inventory, unresolved = self.read(H405, day)
        u = self.item(unresolved, 'gi.eus')
        title, own = self.span(H405, 'Pancreatic Endosonography'), self.span(H405, 'earlier EUS')
        self.assertEqual(detect.status_for_span(H405, own.start, own.end, day), ('historical', ('historical: earlier',)))
        self.assertTrue(sections.beyond_heading_reach(H405, sections.layout(H405), own.start))
        self.assertFalse(engine._routing_agrees(dataclasses.replace(u, evidence=(title, own)), inventory, routing, H405,
                                                day))
        heading = self.span(H405, 'Endosonographic Conclusion')
        self.assertTrue(engine._routing_agrees(dataclasses.replace(u, evidence=(title, heading)), inventory, routing,
                                               H405, day))

    def test_a_passage_outside_the_text_never_reads_as_saying_nothing(self):  # kills po-unreadable-passage
        routing, inventory, unresolved = self.read(H402, None)
        u = self.item(unresolved, 'gi.egd')
        self.assertEqual(u.evidence, ())
        self.assertTrue(engine._routing_agrees(u, inventory, routing, H402, None))  # PO-1: family silent, no passage
        outside = Span(len(H402) + 5, len(H402) + 9, 'gone')
        self.assertFalse(engine._routing_agrees(dataclasses.replace(u, evidence=(outside,)), inventory, routing, H402,
                                                None))

    def test_a_doubted_mention_of_the_family_contradicts(self):
        day = dt.date(2026, 10, 15)
        routing, inventory, unresolved = self.read(H405, day)
        u = self.item(unresolved, 'gi.eus')

        def doubted(f):
            if f.family != 'gi.eus':
                return f
            first = dataclasses.replace(f.mentions[1], status='uncertain', cues=(detect.DOUBT_PREFIX + " 'not' in its "
                                                                                 'clause',))
            return dataclasses.replace(f, mentions=(f.mentions[0], first) + f.mentions[2:])
        changed = dataclasses.replace(routing, findings=tuple(doubted(f) for f in routing.findings))
        self.assertFalse(engine._routing_agrees(u, inventory, changed, H405, day))

    def test_another_occasions_mention_with_a_doubt_riding_along_contradicts(self):  # kills po2-another-occasion-clean
        day = dt.date(2026, 10, 15)
        routing, inventory, unresolved = self.read(H405, day)
        u = self.item(unresolved, 'gi.eus')
        eus = routing.finding('gi.eus')
        self.assertEqual(eus.mentions[3].cues, ('historical: earlier',))

        def with_cues(cues):
            mention = dataclasses.replace(eus.mentions[3], cues=cues)
            finding = dataclasses.replace(eus, mentions=eus.mentions[:3] + (mention,) + eus.mentions[4:])
            return dataclasses.replace(routing, findings=tuple(finding if f.family == 'gi.eus' else f
                                                               for f in routing.findings))
        self.assertTrue(engine._routing_agrees(u, inventory, with_cues(('historical: earlier',)), H405, day))
        self.assertFalse(engine._routing_agrees(u, inventory, with_cues(
            ('historical: earlier', detect.DOUBT_PREFIX + " 'not' in its clause")), H405, day))

    def test_the_installed_reasons_still_bound_the_offer(self):
        routing, inventory, unresolved = self.read(H402, None)
        u = self.item(unresolved, 'gi.egd')
        for reason in ('unsupported', 'coverage_unknown'):
            self.assertFalse(engine._routing_agrees(dataclasses.replace(u, reason=reason), inventory, routing, H402,
                                                    None))
        self.assertFalse(engine._routing_agrees(u, inventory, None, H402, None))


class HelperTests(SimpleTestCase):
    def test_another_occasion(self):
        self.assertTrue(engine._po_another_occasion(('historical: 2025-04-09 is before the service date',
                                                     'historical: Earlier')))
        self.assertTrue(engine._po_another_occasion(('planned: booked', 'section: plan (Plan)')))
        self.assertFalse(engine._po_another_occasion(('section: history (Prior Studies)',)))
        self.assertFalse(engine._po_another_occasion(('historical: earlier', 'negated: was not performed')))
        self.assertFalse(engine._po_another_occasion(()))

    def test_says_nothing(self):  # kills po-says-nothing-worded
        says = engine._po_says_nothing
        self.assertTrue(says('uncertain', (detect.SILENT,)))
        self.assertTrue(says('uncertain', ('performed: was advanced', 'section: indication (Indication)')))
        self.assertTrue(says('uncertain', ('section: procedure (Procedure)', detect.UNESTABLISHED)))
        self.assertFalse(says('uncertain', ("uncertain: unresolved negation 'defer' in its clause",)))
        self.assertFalse(says('uncertain', ('section: findings (Findings)', 'uncertain: the document denies this '
                                                                           'service (negated: No)')))
        self.assertFalse(says('uncertain', ('uncertain: versus',)))
        self.assertFalse(says('uncertain', ()))
        for status in ('historical', 'planned', 'negated', 'cancelled'):
            self.assertFalse(says(status, ('section: history (Prior Studies)',)), status)

    def test_silent_needs_a_cue(self):
        self.assertTrue(engine._po_silent('uncertain', (detect.SILENT,)))
        self.assertFalse(engine._po_silent('uncertain', ()))
        self.assertFalse(engine._po_silent('historical', (detect.SILENT,)))

    def test_section_only_across_an_unread_heading(self):
        runaway = engine._po_section_only_across_unread_heading
        section_only = ('section: history (Prior Studies)',)
        pos = H405.index('Endosonographic Conclusion')
        self.assertTrue(runaway(H405, pos, 'historical', section_only))
        self.assertTrue(runaway(H405, pos, 'historical', ('performed: was introduced',) + section_only))
        self.assertFalse(runaway(H405, pos, 'historical', ('historical: earlier',) + section_only))
        self.assertFalse(runaway(H405, pos, 'historical', ('performed: was introduced',)))
        self.assertFalse(runaway(H405, pos, 'negated', section_only))
        self.assertFalse(runaway(H405, pos, 'uncertain', section_only))
        self.assertFalse(runaway(H405, pos, 'historical', ()))
        direct = H405.index('Earlier EUS (this service)')  # right under "Prior Studies": no unread line between
        self.assertFalse(runaway(H405, direct, 'historical', section_only))
        title = H405.index('Pancreatic Endosonography')  # before the first heading
        self.assertFalse(runaway(H405, title, 'historical', section_only))

    def test_the_document_guard(self):
        self.assertTrue(engine._po_todays_procedure_report(H402))
        self.assertTrue(engine._po_todays_procedure_report(H405))
        self.assertFalse(engine._po_todays_procedure_report(ROWS['G-head clinic note, copied colonoscopy'][0]))
        self.assertFalse(engine._po_todays_procedure_report(ROWS['G-around booking with head fields'][0]))
        for name in ('A-sedation clinic note titled with the family, Attending field',
                     'A-head h4-05 without the head words the PS guard reads',
                     'A-around colonoscopy records review with head fields',
                     'A-notdone h4-05, the procedure cancelled before sedation'):
            self.assertFalse(engine._po_todays_procedure_report(AMENDED_ROWS[name][0]), name)

    def test_sedation_field(self):  # A1: the label names it
        field = engine._po_sedation_field
        for head in ('Sedation: propofol', 'Sedation provider: a CRNA', 'Sedation and airway: propofol',
                     'Anesthetic care: MAC', 'Anaesthesia: general', 'Type of sedation: moderate', 'Sedation: none'):
            self.assertTrue(field(B + 'Colonoscopy\n' + head + '\n'), head)
        for head in ('She tolerated sedation poorly in the past.', 'HPI: She tolerated sedation poorly.',
                     'Reason for visit: anesthesia for a future colonoscopy', 'Attending: Synthetic Attending, MD',
                     'Medications: propofol per the CRNA'):
            self.assertFalse(field(B + 'Colonoscopy\n' + head + '\n'), head)
        late = B + 'Colonoscopy\n' + ''.join(f'Field {i}: value\n' for i in range(11)) + 'Sedation: propofol\n'
        self.assertFalse(field(late))  # beyond the head's twelve non-empty lines

    def test_procedure_not_done(self):  # A5
        says = engine._po_procedure_not_done
        for line in ('The procedure was cancelled before sedation.', 'The examination was postponed.',
                     'No endoscopic procedure was performed today.', 'No procedure was performed.',
                     'Procedure not performed.', 'The exam was not done.', 'The procedure did not take place.',
                     'Lower examination deferred to next week.', 'Status: Cancelled - the patient had eaten breakfast.',
                     'Procedure status: not performed', 'Outcome: no-show', 'The patient declined the procedure.'):
            self.assertTrue(says('Report\n' + line + '\n'), line)
        for line in ('No other procedures were performed.', 'No further procedure was performed.',
                     'Because the focus behaved as mucin, no fine-needle aspiration or biopsy was performed.',
                     'His first procedure in September was cancelled because of a low platelet count.',
                     'The procedure was not cancelled.', 'The procedure was completed without complication.',
                     'The colonoscopy was cancelled.', 'The upper examination was aborted at the upper sphincter.',
                     'Status: completed'):
            self.assertFalse(says('Report\n' + line + '\n'), line)

    def test_title_lines(self):  # A2 and A3: the head's title lines, before its first field line
        def titles(text):
            return [text[a:b] for a, b in engine._po_title_lines(text)]
        self.assertEqual(titles(H402)[1:], ['Gastroscopy and Sigmoidoscopy for Suspected Gut GVHD',
                                            'Ardenvale University Hospital (fictional), Endoscopy, Floor 3'])
        self.assertEqual(titles(H405)[1], 'Pancreatic Endosonography')
        short = AMENDED_ROWS['A-title short head, a copied EGD line after the head fields'][0]
        self.assertNotIn('EGD at Mercy GI', titles(short))
        self.assertIn('Surveillance Colonoscopy', titles(short))
        self.assertEqual(titles(B + '## Colonoscopy Report ##\nSedation: propofol\n')[1], '## Colonoscopy Report ##')
        self.assertEqual(titles(B + 'A sentence ends here.\nColonoscopy\n'), [B.strip(), 'Colonoscopy'])
        self.assertEqual(titles('Indication: ' + 'x' * 400 + '\nColonoscopy\n'), [])  # a long field line ends the title

    def test_unread_line_names_another_occurrence(self):  # A4
        names = engine._po_unread_line_names_another_occurrence
        text = AMENDED_ROWS['A-between h4-05, an unread heading naming an earlier EUS far above'][0]
        lay = sections.layout(text)
        pos = text.index('Endosonographic Conclusion')
        lo = text.find('\n', lay.section_at(pos).heading.end)
        self.assertFalse(sections.under_another_occurrence(text, pos))  # beyond its six lines and 600 characters
        self.assertTrue(names(text, lo, pos))
        self.assertFalse(names(H405, H405.find('\n', sections.layout(H405).section_at(pos).heading.end), pos))
        lower = AMENDED_ROWS['A-occurrence h4-05, a lowercase outside-records line above the evidence'][0]
        at = lower.index('Endosonographic Conclusion')
        self.assertFalse(names(lower, lower.find('\n', sections.layout(lower).section_at(at).heading.end), at))
        self.assertTrue(sections.under_another_occurrence(lower, at))  # the nearest short line, read by PS

    def test_document_facts_are_read_once_per_text(self):
        jobs = __import__('studio.jobs', fromlist=['x'])
        jobs.release_routing_caches()
        self.assertEqual(engine._po_document.cache_info().currsize, 0)
        first = engine._po_document(H405)
        self.assertIs(engine._po_document(H405), first)
        self.assertEqual(engine._po_document.cache_info().hits, 1)
        jobs.release_routing_caches()  # ROUTING_CACHE_MODULES names this module: the cache is cleared with the others
        self.assertEqual(engine._po_document.cache_info().currsize, 0)
