"""DECISIONS D148 (the round-5c review of D141: gemini-migration/round5c/review_enteroscopy3.json, problems 0-3),
SYNTHETIC, built from the review's own documents (its tools/refute.py and cases.py: the pouchoscopy into the pre-pouch
ileum beside the attested PEG entry 'A PEG tube is in place in the gastric body', the EGD and push enteroscopy whose
duodenal APC the gastroscope treated before the exchange, the separate-line duodenal APC whose citations reach the push
enteroscopy's line or an Impression, and the parity note's base question) - studio/interpretation/classes.py
(pouch_types, routes, doubted_routes, base_asked) and coverage.coding_family and beyond_reach:
- (problem 0) a pouch entry is typed by its OWN words only: no other anatomy entry types it, so a PEG in the gastric
  body never makes an untyped pouch a gastric one;
- (problems 1 and 2) D141's shared-passage test is gone: an act at the generic duodenum moves to the EGD unless its own
  target words name a portion beyond the second and every done EGD's verified reach stops at or before the second
  portion; an act at the second portion's landmark whose own words name a portion beyond it is read alike;
- (problem 3) the base rule's question is asked once: base_asked reads the base rule's arm (a) too.
The installed release c2e53f8e's outputs are named in each test (engine.assess as tests/test_harness_engine.py drives
it, and jobs._assess_child: they agree on every probe row); e5628be56's where it differs. DECISIONS D153 (the round-5d
review of D148, problems 0-2) withdraws the act-words arm: the pins whose docstrings name D153 pinned a release it
withdraws, and now pin the hold it restores; its own pins are tests/test_interpretation_r5e_enteroscopy.py's. Nothing
is sent."""
from __future__ import annotations

from django.test import SimpleTestCase

from studio.interpretation import classes, coverage, events, normalize
from tests.test_interpretation_events import asked, check, proposal, run
from tests.test_interpretation_identity import a, accepted, act, tg
from tests.test_interpretation_r5_enteroscopy_route import DATED, HEADER, SIGNED, held, ready

ELSEWHERE = 'service.act_elsewhere'
BASE = 'services.base_included'
POUCH = frozenset({'pouch'})


def inventory(lines: dict, *, found, lesions=(), reach=(), anatomy=(), edit=None):
    """(the normalized inventory, the text) of a synthetic answer over ``lines`` ({passage id: line}, P0.. in order),
    dated in P2 and signed in P3, read by read.read and normalized with the real linked steps; ``edit`` changes the
    answer's value first (a citation the review's variants add)."""
    text = '\n'.join(lines.values()) + '\n'
    value = {'passages': [{'id': pid, 'text': text_line} for pid, text_line in lines.items()],
             'encounter': {'date_of_service': {'value': '2026-11-05', 'state': 'stated', 'words': 'November 5, 2026',
                                               'passages': ['P2'], 'other_dates': []},
                           'documenting_endoscopist': {'words': 'Tomas Reyes, MD (fictional)', 'passages': ['P3']},
                           'team': [], 'anatomy': list(anatomy), 'reach': list(reach), 'visit_facts': []},
             'lesions': list(lesions), 'events': list(found), 'open_questions': []}
    if edit is not None:
        edit(value)
    return normalize.normalize(accepted(value), text), text


def reaching(eid: str, landmark: str, words: str, pid: str) -> dict:
    return {'event': eid, 'landmark': landmark, 'words': words, 'passages': [pid], 'completion': a('not_stated')}


def line(text: str, pid: str) -> str:
    return text.splitlines()[int(pid[1:])]


def picked(inv, text, chosen):
    return run(inv, text, [(code, line(text, pid)) for code, pid in chosen])


def code_of(inv, text: str, code: str, pid: str):
    return proposal(picked(inv, text, ((code, pid),)), code)


# --- problem 0: the pouch typed by its own words ------------------------------------------------------------------

PEG_LINE = 'A PEG tube is in place in the gastric body.'  # the PEG entry is attested in C/W1S-156
PEG_ENTRY = {'state': 'altered', 'landmark': 'gastric_body', 'words': 'A PEG tube is in place in the gastric body',
             'passages': ['P8']}
BARE = ('The patient has a pouch after a proctocolectomy for ulcerative colitis.', 'pouch')
FORMED = ('History: ulcerative colitis, total proctocolectomy with pouch formation in 2015.',
          'total proctocolectomy with pouch formation')
ANAL = ('The patient has a pouch-anal anastomosis after a proctocolectomy for ulcerative colitis.',
        'pouch-anal anastomosis')
J_POUCH = ('The patient has an ileal J-pouch after a restorative proctocolectomy for ulcerative colitis.',
           'ileal J-pouch')
RYGB_ENTRY = {'state': 'altered', 'landmark': 'stomach', 'words': 'Roux-en-Y gastric bypass', 'passages': ['P5']}
RYGB_EXAM = 'The enteroscope was advanced through the small gastric pouch and the Roux limb into the proximal ileum.'


def pouch_entry(words: str) -> dict:
    return {'state': 'altered', 'landmark': 'pouch', 'words': words, 'passages': ['P5']}


def small_bowel(title: str, procedure_line: str, procedure_words: str, anatomy_line: str, exam_line: str,
                landmark: str, reach_words: str, biopsy_line: str, target_words: str, *, anatomy, scope_words: str,
                status_words: str = 'was advanced', kind_words: str = '', extra=()):
    """The review's small_bowel: E1 the examination (P6; procedure words in P4), E2 a cold-forceps biopsy (P7) at
    ``landmark``, E1's reach there (P6), the anatomy entries ``anatomy`` (P5; ``extra`` lines from P8)."""
    lines = {'P0': HEADER, 'P1': title, 'P2': DATED, 'P3': SIGNED, 'P4': procedure_line, 'P5': anatomy_line,
             'P6': exam_line, 'P7': biopsy_line}
    lines.update({f'P{index}': text for index, text in enumerate(extra, start=8)})
    procedure = a('enteroscopy', procedure_words, ['P4'])
    e1 = act('E1', 'P6', 'examination', kind_words or scope_words, status_words=status_words, procedure=procedure,
             technique=a('endoscope', scope_words, ['P6']))
    e2 = act('E2', 'P7', 'biopsy', 'Biopsies', status_words='were taken', procedure=procedure,
             technique=a('cold_forceps', 'cold forceps', ['P7']), target=tg('', landmark, target_words, ['P7']))
    return inventory(lines, found=[e1, e2], reach=[reaching('E1', landmark, reach_words, 'P6')], anatomy=anatomy)


def pouchoscopy(anatomy_line: str, anatomy, *, pouch_words: str = 'pouch', status_words: str = 'was advanced',
                extra=()):
    """The review's pouchoscopy into the pre-pouch ileum ('Procedure: Pouchoscopy.')."""
    return small_bowel('POUCHOSCOPY REPORT', 'Procedure: Pouchoscopy.', 'Pouchoscopy', anatomy_line,
                       f'The endoscope was advanced through the anus into the {pouch_words} and through the pouch '
                       'inlet into the pre-pouch ileum for 15 cm.', 'ileum', 'pre-pouch ileum',
                       'Biopsies of the pre-pouch ileum were taken with cold forceps.', 'pre-pouch ileum',
                       anatomy=anatomy, scope_words='endoscope', status_words=status_words, extra=extra)


def oral_dbe(anatomy_line: str, anatomy, *, status_words: str = 'was advanced', extra=()):
    """The review's oral double-balloon enteroscopy to the proximal ileum."""
    return small_bowel('DOUBLE-BALLOON ENTEROSCOPY REPORT', 'Procedure: Double-balloon enteroscopy.',
                       'Double-balloon enteroscopy', anatomy_line,
                       'The double-balloon enteroscope was advanced orally to the proximal ileum.', 'ileum',
                       'proximal ileum', 'Biopsies of an ulcer in the proximal ileum were taken with cold forceps.',
                       'an ulcer in the proximal ileum', anatomy=anatomy, scope_words='double-balloon enteroscope',
                       status_words=status_words, extra=extra)


def rygb_exam(anatomy_line: str, anatomy):
    """The review's Roux-en-Y enteroscopy (B/fb07's attested shapes: the kind words the whole sentence)."""
    return small_bowel('SINGLE-BALLOON ENTEROSCOPY REPORT', 'Procedure: Single-balloon enteroscopy.',
                       'Single-balloon enteroscopy', anatomy_line, RYGB_EXAM, 'ileum', 'proximal ileum',
                       'Biopsies of an ulcer in the proximal ileum were taken with cold forceps.',
                       'an ulcer in the proximal ileum', anatomy=anatomy, scope_words='enteroscope',
                       kind_words=RYGB_EXAM)


def routes_of(inv) -> tuple:
    encounter = events.Reading.of(inv).encounter
    return classes.routes(encounter), classes.doubted_routes(encounter)


class PouchTypedByItsOwnWords(SimpleTestCase):
    def test_d148_an_untyped_pouch_beside_a_peg_in_the_gastric_body_is_a_doubt(self):
        """Problem 0 (critical, introduced by D141): D141 typed a pouch by the gastric words of every verified altered
        entry, so the untyped pouch beside 'A PEG tube is in place in the gastric body' read as a gastric pouch - no
        route, no doubt - and 44377 was READY on the pouchoscopy into the pre-pouch ileum (its only check
        pfs.presence). 46e461e7f and c2e53f8e hold it (c2e53f8e: performed_status and extent). The pouch is a doubt
        again: 44377 asks the route question naming the documented pouch, as without the PEG; the same with the pouch
        words 'total proctocolectomy with pouch formation' and 'pouch-anal anastomosis', and with the status words
        'was advanced through the anus into the pouch' (the class question, the route named)."""
        for anatomy_line, words in (BARE, FORMED, ANAL):
            inv, text = pouchoscopy(anatomy_line, (pouch_entry(words), PEG_ENTRY), extra=(PEG_LINE,))
            with self.subTest(words=words):
                self.assertEqual(routes_of(inv), (frozenset(), POUCH))
                p = code_of(inv, text, '44377', 'P7')
                held(self, p, classes.ILEAL, 'ileum', 'pre-pouch ileum', classes.ROUTE_FORM, through=POUCH)
                self.assertIn('through the mouth or through the documented pouch', p.clarifications[0].question)
                held(self, code_of(inv, text, '44386', 'P7'), classes.POUCH, 'ileum', 'pre-pouch ileum',
                     classes.CLASS_FORM)
        routed = 'was advanced through the anus into the pouch'
        inv, text = pouchoscopy(BARE[0], (pouch_entry('pouch'), PEG_ENTRY), extra=(PEG_LINE,), status_words=routed)
        held(self, code_of(inv, text, '44377', 'P7'), classes.ILEAL, 'ileum', 'pre-pouch ileum', classes.CLASS_FORM,
             route=classes.THROUGH_POUCH, route_words=routed)

    def test_d148_the_oral_enteroscopy_beside_the_untyped_pouch_and_the_peg_reads_its_route(self):
        """The review's twin: an oral double-balloon enteroscopy in the same patient. The pouch in doubt keeps the
        examination's own route deciding: with 'was advanced' only, 44377 asks the route question (e5628be56 READY,
        through the PEG's gastric word; c2e53f8e holds it, extent); with 'was advanced orally', READY."""
        anatomy = (pouch_entry('pouch'), PEG_ENTRY)
        inv, text = oral_dbe(BARE[0], anatomy, extra=(PEG_LINE,))
        held(self, code_of(inv, text, '44377', 'P7'), classes.ILEAL, 'ileum', 'proximal ileum', classes.ROUTE_FORM,
             through=POUCH)
        inv, text = oral_dbe(BARE[0], anatomy, extra=(PEG_LINE,), status_words='was advanced orally')
        ready(self, code_of(inv, text, '44377', 'P7'))

    def test_d148_a_pouch_entry_is_typed_by_its_own_words_alone(self):
        """pouch_types reads each pouch entry's own words and no other entry: (intestinal, gastric) per entry; the
        intestinal pouch alone is the small-intestinal pouch, neither or both a doubt, a gastric pouch alone nothing."""
        for name, anatomy_line, anatomy, types, expected in (
                ('untyped beside the PEG', BARE[0], (pouch_entry('pouch'), PEG_ENTRY), ((False, False),),
                 (frozenset(), POUCH)),
                ('J-pouch beside the PEG', J_POUCH[0], (pouch_entry('ileal J-pouch'), PEG_ENTRY), ((True, False),),
                 (POUCH, frozenset())),
                ('J-pouch beside the bypass', 'The patient has an ileal J-pouch and a Roux-en-Y gastric bypass.',
                 (pouch_entry('ileal J-pouch'), RYGB_ENTRY), ((True, False),), (POUCH, frozenset())),
                ('untyped beside the bypass', 'The patient has a Roux-en-Y gastric bypass with a small gastric pouch.',
                 (RYGB_ENTRY, pouch_entry('pouch')), ((False, False),), (frozenset(), POUCH)),
                ('gastric alone', 'The patient has a Roux-en-Y gastric bypass with a small gastric pouch.',
                 (RYGB_ENTRY, pouch_entry('small gastric pouch')), ((False, True),), (frozenset(), frozenset())),
                ('both in its own words', 'The patient has an ileal pouch after a gastric bypass.',
                 (pouch_entry('ileal pouch after a gastric bypass'),), ((True, True),), (frozenset(), POUCH))):
            inv, _ = oral_dbe(anatomy_line, anatomy, extra=(PEG_LINE,))
            with self.subTest(case=name):
                self.assertEqual(classes.pouch_types(events.Reading.of(inv).encounter), types)
                self.assertEqual(routes_of(inv), expected)

    def test_d148_an_untyped_pouch_beside_a_separate_gastric_bypass_is_a_doubt(self):
        """The spec's report: the Roux-en-Y enteroscopy with the pouch entry's words 'pouch' (untyped) beside a
        separate 'Roux-en-Y gastric bypass' entry. Typed by the bypass's words at e5628be56, the pouch was gastric and
        44377 READY; typed by its own words it is a doubt, so the examination's route decides - 'through the small
        gastric pouch' reads as the pouch route - and 44377 is held with the class question (a cost; c2e53f8e holds it
        too, with R6's extent question). 44386 stays held."""
        inv, text = rygb_exam('The patient has a Roux-en-Y gastric bypass with a small gastric pouch.',
                              (RYGB_ENTRY, pouch_entry('pouch')))
        self.assertEqual(routes_of(inv), (frozenset(), POUCH))
        for code, exam_class in (('44377', classes.ILEAL), ('44386', classes.POUCH)):
            with self.subTest(code=code):
                held(self, code_of(inv, text, code, 'P7'), exam_class, 'ileum', 'proximal ileum', classes.CLASS_FORM,
                     route=classes.THROUGH_POUCH, route_words=RYGB_EXAM)

    def test_d148_an_ileal_j_pouch_beside_a_peg_is_the_small_intestinal_pouch(self):
        """A release the spec states, recorded: the typed J-pouch beside the PEG entry, the pouchoscopy's route stated
        ('was advanced through the anus into the J-pouch'). D141 read the PEG's gastric word against the J-pouch
        (a doubt: 44386 held); typed by its own words it is the small-intestinal pouch, and 44386 is READY - the code
        the document supports (a pouchoscopy through the J-pouch with biopsies). c2e53f8e holds it (performed_status
        and extent)."""
        routed = 'was advanced through the anus into the J-pouch'
        inv, text = pouchoscopy(J_POUCH[0], (pouch_entry('ileal J-pouch'), PEG_ENTRY), extra=(PEG_LINE,),
                                pouch_words='J-pouch', status_words=routed)
        self.assertEqual(routes_of(inv), (POUCH, frozenset()))
        ready(self, code_of(inv, text, '44386', 'P7'))
        held(self, code_of(inv, text, '44377', 'P7'), classes.ILEAL, 'ileum', 'pre-pouch ileum', classes.CLASS_FORM,
             route=classes.THROUGH_POUCH, route_words=routed)


# --- problems 1 and 2: the duodenal portion beyond the second ------------------------------------------------------

EGD_D2 = 'EGD: The gastroscope was advanced to the second portion of the duodenum.'
PUSH = 'Push enteroscopy: The enteroscope was then advanced to the proximal jejunum.'
DUO = 'A duodenal angioectasia was treated with argon plasma coagulation.'
D3_LINE = 'An angioectasia in the third portion of the duodenum was treated with argon plasma coagulation.'
D3_WORDS = 'An angioectasia in the third portion of the duodenum'
GASTRIC = 'Two gastric antral angioectasias'


def egd_push(act_line: str = '', act_pid: str = 'P7', *, landmark: str = 'duodenum', words: str = 'A duodenal '
             'angioectasia', status_words: str = 'was treated', push_line: str = PUSH, egd_line: str = EGD_D2,
             egd_reach=('second_portion_duodenum', 'second portion of the duodenum'), extra=(), edit=None):
    """The review's egd_push: an EGD (E1, P5; its reach ``egd_reach``, None for none), a push enteroscopy to the
    proximal jejunum (E2, P6) and argon plasma coagulation of ``words`` at ``landmark`` filed under the enteroscopy (E3,
    in ``act_pid``: P7 a line of its own, ``act_line``; or P6, told in ``push_line``)."""
    lines = {'P0': HEADER, 'P1': 'EGD AND PUSH ENTEROSCOPY REPORT', 'P2': DATED, 'P3': SIGNED,
             'P4': 'Procedure: EGD and push enteroscopy.', 'P5': egd_line, 'P6': push_line}
    if act_pid == 'P7':
        lines['P7'] = act_line
    lines.update({f'P{index}': text for index, text in enumerate(extra, start=8)})
    upper, push = a('egd', 'EGD', ['P5']), a('enteroscopy', 'Push enteroscopy', ['P6'])
    found = [act('E1', 'P5', 'examination', 'gastroscope', status_words='was advanced', procedure=upper,
                 technique=a('endoscope', 'gastroscope', ['P5'])),
             act('E2', 'P6', 'examination', 'enteroscope', status_words='was then advanced', procedure=push,
                 technique=a('endoscope', 'enteroscope', ['P6'])),
             act('E3', act_pid, 'ablation', 'argon plasma coagulation', status_words=status_words, procedure=push,
                 technique=a('argon_plasma', 'argon plasma coagulation', [act_pid]),
                 target=tg('L1', landmark, words, [act_pid]))]
    lesion = {'id': 'L1', 'words': words, 'landmark': landmark, 'site_words': '', 'size_words': '',
              'multiplicity': 'group', 'passages': [act_pid]}
    reach = [reaching('E2', 'jejunum', 'proximal jejunum', 'P6')]
    if egd_reach:
        reach.insert(0, reaching('E1', egd_reach[0], egd_reach[1], 'P5'))
    return inventory(lines, found=found, lesions=[lesion], reach=reach, edit=edit)


def family_of_e3(inv) -> str:
    reading = events.Reading.of(inv)
    return coverage.coding_family(reading, reading.events['E3'])


def cite(*changes):
    """An ``edit`` adding passages to E2's or E3's cited attributes: (event index, attribute, passages)."""
    def edit(value):
        for index, name, passages in changes:
            value['events'][index][name]['passages'] = list(passages)
    return edit


class PortionBeyondTheSecond(SimpleTestCase):
    def moved(self, inv, text, act_pid: str = 'P7', egd_facts=('base_included',)):
        """The act is the EGD session's: 44369 held (act_elsewhere, performed_status) and 43235 held base_included
        (``egd_facts``: with R6's extent too where the EGD's reach is not verified), alone and beside 44369, as
        c2e53f8e holds both."""
        self.assertEqual(family_of_e3(inv), 'gi.egd')
        p = code_of(inv, text, '44369', act_pid)
        self.assertEqual((p.status, asked(p), check(p, ELSEWHERE).status),
                         ('needs_clarification', ['performed_status'], 'warn'))
        for chosen in ((('43235', 'P5'),), (('44369', act_pid), ('43235', 'P5'))):
            p = proposal(picked(inv, text, chosen), '43235')
            with self.subTest(picks=[code for code, _ in chosen]):
                self.assertEqual((p.status, asked(p), check(p, BASE).status),
                                 ('needs_clarification', list(egd_facts), 'warn'))

    def stayed(self, inv, text, act_pid: str = 'P7'):
        """The act stays the enteroscopy's: 44369 READY, and 43235 READY beside it (no act in the EGD's session)."""
        self.assertEqual(family_of_e3(inv), 'gi.enteroscopy')
        ready(self, code_of(inv, text, '44369', act_pid))
        result = picked(inv, text, (('44369', act_pid), ('43235', 'P5')))
        ready(self, proposal(result, '44369'))
        self.assertEqual((proposal(result, '43235').status, asked(proposal(result, '43235'))), ('ready', []))

    def test_d148_the_act_the_gastroscope_treated_before_the_exchange_moves(self):
        """Problem 1 (introduced by D141): 'A duodenal angioectasia was treated with argon plasma coagulation, and the
        gastroscope was then exchanged for the enteroscope, which was advanced to the proximal jejunum.' - the APC
        and the push examination in one passage. D141's shared-passage test kept the act with the enteroscopy: 44369
        and 43235 READY. Its own words name no portion beyond the second, so it moves: 44369 held, 43235
        base_included, as c2e53f8e (which READYs 43270)."""
        exchange = ('A duodenal angioectasia was treated with argon plasma coagulation, and the gastroscope was then '
                    'exchanged for the enteroscope, which was advanced to the proximal jejunum.')

        def as_the_review(value):
            value['events'][1]['status'] = a('performed', 'was advanced', ['P6'])
            value['events'][1]['procedure'] = a('enteroscopy', 'enteroscope', ['P6'])
            value['events'][2]['procedure'] = a('enteroscopy', 'enteroscope', ['P6'])

        inv, text = egd_push(act_pid='P6', push_line=exchange, edit=as_the_review)
        self.moved(inv, text, 'P6')

    def test_d148_a_duodenal_act_on_its_own_line_moves_whatever_its_citations(self):
        """Problem 2 (introduced by D141): the passage test read every passage an attribute cites, not the one its
        words stand in. 'A duodenal angioectasia was treated with argon plasma coagulation.' on its own line (P7)
        with its status citing P6 and P7, with the push examination's kind citing P6 and P7, or restated in an
        Impression with the push enteroscopy - 44369 and 43235 READY at e5628be56. Each moves: 44369 held, 43235
        base_included, as c2e53f8e holds both."""
        impression = ('Impression: Push enteroscopy to the proximal jejunum; a duodenal angioectasia was treated with '
                      'argon plasma coagulation.')
        both = ('Impression: EGD and push enteroscopy; the enteroscope was advanced to the proximal jejunum, and a '
                'duodenal angioectasia was treated with argon plasma coagulation.')
        for name, options in (
                ('own line', {}),
                ('status cites P6 and P7', dict(edit=cite((2, 'status', ('P6', 'P7'))))),
                ('the push kind cites P6 and P7', dict(edit=cite((1, 'kind', ('P6', 'P7'))))),
                ('restated in an Impression', dict(extra=(impression,), edit=cite(
                    (1, 'kind', ('P6', 'P8')), (2, 'kind', ('P7', 'P8')), (2, 'status', ('P7', 'P8'))))),
                ('both restated', dict(extra=(both,), edit=cite(
                    (1, 'kind', ('P6', 'P8')), (1, 'status', ('P6', 'P8')), (2, 'kind', ('P7', 'P8')),
                    (2, 'status', ('P7', 'P8')))))):
            inv, text = egd_push(DUO, **options)
            with self.subTest(case=name):
                self.moved(inv, text)

    def test_d148_the_third_portion_on_a_line_of_its_own_moves(self):
        """The spec's D3_LINE: 'An angioectasia in the third portion of the duodenum was treated with argon plasma
        coagulation.' on its own line beside an EGD verified to the second portion. DECISIONS D153 (the round-5d review
        of D148, problems 0-2) withdraws the release D148 pinned here (44369 and 43235 READY): an act's own words never
        place it beyond the EGD's verified reach, so it moves - 44369 held, 43235 base_included, as e5628be56 and
        c2e53f8e hold both (c2e53f8e: 44369 performed_status, 43235 base_included). 44360 alone asks the base rule's
        question and the act's in one clarification (fact procedure), as at e5628be56 (c2e53f8e READY: a cost). Renamed
        from test_d148_the_third_portion_on_a_line_of_its_own_stays_the_enteroscopys."""
        inv, text = egd_push(D3_LINE, words=D3_WORDS)
        self.moved(inv, text)
        p = code_of(inv, text, '44360', 'P6')
        self.assertEqual((p.status, asked(p), check(p, ELSEWHERE).status, [spec.question for spec in p.clarifications]),
                         ('needs_clarification', ['procedure'], 'warn',
                          ['Is 44360 reported separately from ablation for this examination? In which procedure was '
                           f'the ablation (“{D3_WORDS}”) done?']))

    def test_d148_no_form_of_a_portion_beyond_the_second_keeps_the_act(self):
        """BEYOND_SECOND_WORDS is unchanged (D153 reads it in an EGD reach's own words only). DECISIONS D153 withdraws
        the release D148 pinned for each form in an act's own words: every form now leaves the act at its landmark,
        so it moves (44369 held, 43235 base_included, as e5628be56 and c2e53f8e hold every one) - 'distal duodenum'
        (the post-bulbar duodenum a standard EGD samples) among them; so do '3rd portion' and the plural, as before.
        Renamed from test_d148_each_form_of_a_portion_beyond_the_second_keeps_the_act."""
        self.assertEqual(coverage.BEYOND_SECOND_WORDS, ('third portion', 'fourth portion', 'third part',
                                                         'fourth part', 'd3', 'd4', 'distal duodenum'))
        for words in ('An angioectasia in the fourth portion of the duodenum', 'An angioectasia in the third part of '
                      'the duodenum', 'An angioectasia in the fourth part of the duodenum', 'A D3 angioectasia of the '
                      'duodenum', 'A D4 angioectasia of the duodenum', 'An angioectasia in the distal duodenum'):
            inv, text = egd_push(f'{words} was treated with argon plasma coagulation.', words=words)
            with self.subTest(words=words):
                self.moved(inv, text)
        for words, status in (('An angioectasia in the 3rd portion of the duodenum', 'was treated'),
                              ('Angioectasias in the second and third portions of the duodenum', 'were treated')):
            inv, text = egd_push(f'{words} {status} with argon plasma coagulation.', words=words, status_words=status)
            with self.subTest(words=words):
                self.moved(inv, text)

    def test_d148_the_second_portions_landmark_with_third_portion_words_moves(self):
        """The second portion's landmark also takes third-portion words. DECISIONS D153 withdraws the releases D148
        pinned here: the act at that landmark whose own words name the third portion moves - on its own line (44369
        held, as e5628be56 and c2e53f8e hold it) and in the push enteroscopy's sentence, where D141's recorded cost
        returns (e5628be56 held 44369; c2e53f8e READYs 44369 and 43235 there). Renamed from
        test_d148_the_second_portions_landmark_with_third_portion_words_stays."""
        inv, text = egd_push(D3_LINE, landmark='second_portion_duodenum', words=D3_WORDS)
        self.moved(inv, text)
        part = ('Push enteroscopy: The enteroscope was then advanced to the proximal jejunum, and an angioectasia in '
                'the third portion of the duodenum was treated with argon plasma coagulation.')
        inv, text = egd_push(act_pid='P6', push_line=part, landmark='second_portion_duodenum',
                             words='an angioectasia in the third portion of the duodenum')
        self.moved(inv, text, 'P6')

    def test_d148_a_reach_that_may_cover_the_portion_moves_the_act(self):
        """Fail-closed: an EGD reach not verified (its words 'descending duodenum' do not stand in P5), no reach at all,
        a reach at the generic duodenum, and a reach at the second portion's landmark whose own words name the third
        portion may each cover the act - it moves (44369 held, 43235 base_included, as c2e53f8e)."""
        unsettled = ('base_included', 'extent')  # 43235 asks R6's extent too where the EGD's reach is not verified
        for name, facts, options in (
                ('reach not verified', unsettled, dict(egd_reach=('second_portion_duodenum', 'descending duodenum'))),
                ('no reach', unsettled, dict(egd_reach=None)),
                ('generic duodenum', ('base_included',), dict(
                    egd_line='EGD: The gastroscope was advanced to the duodenum.', egd_reach=('duodenum', 'duodenum'))),
                ('third-portion reach words', ('base_included',), dict(
                    egd_line='EGD: The gastroscope was advanced to the third portion of the duodenum.',
                    egd_reach=('second_portion_duodenum', 'third portion of the duodenum')))):
            inv, text = egd_push(D3_LINE, words=D3_WORDS, **options)
            with self.subTest(case=name):
                self.moved(inv, text, egd_facts=facts)

    def test_d148_a_reach_at_the_bulb_is_not_short_of_the_generic_duodenum(self):
        """DECISIONS D153 withdraws the release D148 pinned here (the act's words placed it beyond the bulb: 44369
        READY): an act at the generic duodenum's landmark names no portion, so an EGD verified to the duodenal bulb may
        cover it - it moves (44369 held, 43235 base_included), as e5628be56 and c2e53f8e hold it. Renamed from
        test_d148_a_reach_at_the_bulb_is_short_of_the_third_portion."""
        inv, text = egd_push(D3_LINE, words=D3_WORDS,
                             egd_line='EGD: The gastroscope was advanced to the duodenal bulb.',
                             egd_reach=('duodenal_bulb', 'duodenal bulb'))
        self.moved(inv, text)

    def test_d148_the_reach_order_beyond_the_second_portion(self):
        """DECISIONS D153 changes this pin's expectations back: beyond_reach takes no act words (the words column is
        the act's, kept to show they are not read), so the first three rows are False, as D141 read them; the reach's
        own words are still read (rows 7 and 8: never short)."""
        def reach(value: str, words: str) -> dict:
            return {'extent': {'value': value, 'state': 'verified', 'open': False, 'words': {'text': words}}}

        for examination, landmark, words, expected in (
                (reach('second_portion_duodenum', 'second portion of the duodenum'), 'duodenum', D3_WORDS, False),
                (reach('second_portion_duodenum', 'second portion of the duodenum'), 'second_portion_duodenum',
                 D3_WORDS, False),
                (reach('duodenal_bulb', 'duodenal bulb'), 'duodenum', D3_WORDS, False),
                (reach('gastric_antrum', 'gastric antrum'), 'duodenum', D3_WORDS, True),
                (reach('second_portion_duodenum', 'second portion of the duodenum'), 'duodenum',
                 'A duodenal angioectasia', False),
                (reach('second_portion_duodenum', 'second portion of the duodenum'), 'duodenal_bulb', D3_WORDS, False),
                (reach('second_portion_duodenum', 'third portion of the duodenum'), 'duodenum', D3_WORDS, False),
                (reach('duodenum', 'third portion of the duodenum'), 'duodenum', D3_WORDS, False),
                (reach('duodenum', 'duodenum'), 'second_portion_duodenum', D3_WORDS, False),
                (reach('jejunum', 'proximal jejunum'), 'duodenum', D3_WORDS, False)):
            with self.subTest(reach=examination['extent'], landmark=landmark, words=words):
                self.assertIs(coverage.beyond_reach(examination, landmark), expected)
        unverified = {'extent': {'value': 'duodenal_bulb', 'state': 'unverified', 'open': False, 'words': None}}
        self.assertFalse(coverage.beyond_reach(unverified, 'duodenum'))


# --- problem 3: the base question once ------------------------------------------------------------------------------

class BaseQuestionOnce(SimpleTestCase):
    def test_d148_the_base_question_is_asked_once_beside_a_counted_act_code(self):
        """Problem 3: with 44360 and 44369 picked the base rule asks 'Is 44360 reported separately from 44369 for this
        examination?' (its arm (a)), and D141's act question began with the base question again. base_asked reads arm
        (a) - the base rule's own holding of the code - so the act's question is its own: on the parity input (the
        gastric APC) and on the duodenal APC of no portion on its own line. c2e53f8e asks base_included alone there.
        DECISIONS D153 changes the third-portion act's expectation back: it moves again (D148 kept it, and the base
        rule's question was the one question), so it is asked as the other moved acts are - the base question once,
        then the act's own."""
        for name, (inv, text), words in (
                ('parity', egd_push(f'{GASTRIC} were treated with argon plasma coagulation.', landmark='gastric_antrum',
                                    words=GASTRIC, status_words='were treated'), GASTRIC),
                ('duodenal APC on its own line', egd_push(DUO), 'A duodenal angioectasia'),
                ('third portion on its own line', egd_push(D3_LINE, words=D3_WORDS), D3_WORDS)):
            p = proposal(picked(inv, text, (('44360', 'P6'), ('44369', 'P7'))), '44360')
            with self.subTest(case=name):
                self.assertEqual((p.status, asked(p), check(p, BASE).status, check(p, ELSEWHERE).status,
                                  [spec.question for spec in p.clarifications]),
                                 ('needs_clarification', ['base_included', 'procedure'], 'warn', 'warn',
                                  ['Is 44360 reported separately from 44369 for this examination?',
                                   f'In which procedure was the ablation (“{words}”) done?']))
                reading = events.Reading.of(inv)
                found = coverage.sessions(reading)
                self.assertEqual((classes.base_asked(reading, found), classes.base_asked(reading, found, ('44369',))),
                                 (False, True))

    def test_d148_without_a_counted_act_code_the_base_question_stays_in_the_acts(self):
        """The control: with 44360 alone, or beside the EGD's 43235 (no counted code of the enteroscopy accounts for
        an act), the base rule asks nothing from the session, so the act's question still begins with the base rule's
        (D141), as at 1caaf0609."""
        inv, text = egd_push(DUO)
        for chosen in ((('44360', 'P6'),), (('44360', 'P6'), ('43235', 'P5'))):
            p = proposal(picked(inv, text, chosen), '44360')
            with self.subTest(picks=[code for code, _ in chosen]):
                self.assertEqual((p.status, asked(p), [spec.question for spec in p.clarifications]),
                                 ('needs_clarification', ['procedure'],
                                  ['Is 44360 reported separately from ablation for this examination? In which '
                                   'procedure was the ablation (“A duodenal angioectasia”) done?']))
