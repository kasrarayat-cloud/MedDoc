"""DECISIONS D141 (the round-5 review of D114: gemini-migration/round5b/review_enteroscopy-route.json, problems 0, 1,
4 and 5), SYNTHETIC, built from the review's own documents (its tools/cases.py: the Roux-en-Y enteroscopy to the
proximal ileum, the oral double-balloon enteroscopy whose procedure words name an end ileostomy, the EGD and push
enteroscopy with an angioectasia in the third portion of the duodenum told in the push enteroscopy's sentence and on a
line of its own, and the parity note's gastric APC) - studio/interpretation/classes.py and coverage.coding_family:
- (problem 0) a gastric pouch is never the small-intestinal pouch: a pouch entry is the small-intestinal pouch only when
  its own words name one, and a pouch of no stated type is a doubt (it verifies no pouch class and keeps the
  examination's own route deciding the ileal class);
- (problems 0 and 4) in the words of the examination's own statement a stoma or a pouch states the route only inside a
  route phrase, never as an anatomy mention;
- (problem 1) an act beyond the done EGD's verified reach keeps Gemini's family, and so does an act at the generic
  duodenum told in its own examination's sentence; on a line of its own such an act moves, as the installed release
  reads it;
- (problem 5) the diagnostic code's act question is added beside the base rule's question, never in its place.
At 46e461e7f every held input below except the costs named was READY; the installed release c2e53f8e's outputs are
named in each test (engine.assess as tests/test_harness_engine.py drives it, and jobs._assess_child: they agree on every
probe row). DECISIONS D148 (the round-5c review of D141) changes the expectations of the pins whose docstrings name it;
its own pins are tests/test_interpretation_r5d_enteroscopy.py's. Nothing is sent."""
from __future__ import annotations

from django.test import SimpleTestCase

from studio.interpretation import classes, combination, coverage, events, normalize
from tests.test_interpretation_events import asked, check, proposal, run
from tests.test_interpretation_identity import a, accepted, act, tg
from tests.test_interpretation_r5_enteroscopy_route import (DATED, HEADER, ILEOSTOMY, J_POUCH, POUCH_ENTRY, SIGNED,
                                                            STOMA, STOMA_ENTRY, code_of, held, ileoscopy, line,
                                                            oral_dbe, ready)

ELSEWHERE = 'service.act_elsewhere'
BASE = 'services.base_included'
POUCH = frozenset({'pouch'})


def document(lines: dict, *, found, lesions=(), reach=(), anatomy=()):
    """(the normalized inventory, the text) of a synthetic answer over ``lines`` ({passage id: line}, in order), dated
    in P2 and signed in P3, read by read.read and normalized with the real linked steps."""
    text = '\n'.join(lines.values()) + '\n'
    value = {'passages': [{'id': pid, 'text': text_line} for pid, text_line in lines.items()],
             'encounter': {'date_of_service': {'value': '2026-11-05', 'state': 'stated', 'words': 'November 5, 2026',
                                               'passages': ['P2'], 'other_dates': []},
                           'documenting_endoscopist': {'words': 'Tomas Reyes, MD (fictional)', 'passages': ['P3']},
                           'team': [], 'anatomy': list(anatomy), 'reach': list(reach), 'visit_facts': []},
             'lesions': list(lesions), 'events': list(found), 'open_questions': []}
    return normalize.normalize(accepted(value), text), text


def reaching(eid: str, landmark: str, words: str, pid: str) -> dict:
    return {'event': eid, 'landmark': landmark, 'words': words, 'passages': [pid], 'completion': a('not_stated')}


def small_bowel(title: str, procedure_line: str, procedure_words: str, anatomy_line: str, exam_line: str,
                landmark: str, reach_words: str, biopsy_line: str, target_words: str, *, anatomy, kind_words: str = '',
                scope_words: str = 'enteroscope', status_words: str = 'was advanced'):
    """The review's small_bowel_case: E1 the examination (P6; procedure words in P4), E2 a cold-forceps biopsy (P7) at
    ``landmark``, E1's reach there (P6), the anatomy entries ``anatomy`` in ``anatomy_line`` (P5)."""
    lines = {'P0': HEADER, 'P1': title, 'P2': DATED, 'P3': SIGNED, 'P4': procedure_line, 'P5': anatomy_line,
             'P6': exam_line, 'P7': biopsy_line}
    procedure = a('enteroscopy', procedure_words, ['P4'])
    e1 = act('E1', 'P6', 'examination', kind_words or scope_words, status_words=status_words, procedure=procedure,
             technique=a('endoscope', scope_words, ['P6']))
    e2 = act('E2', 'P7', 'biopsy', 'Biopsies', status_words='were taken', procedure=procedure,
             technique=a('cold_forceps', 'cold forceps', ['P7']), target=tg('', landmark, target_words, ['P7']))
    return document(lines, found=[e1, e2], reach=[reaching('E1', landmark, reach_words, 'P6')], anatomy=anatomy)


# --- problem 0: the Roux-en-Y enteroscopy (B/fb07's attested shapes: the gastric pouch filed as anatomy 'pouch', and
# the examination's kind words the whole examination sentence)
RYGB = 'The patient has a Roux-en-Y gastric bypass with a small gastric pouch.'
RYGB_ANATOMY = ({'state': 'altered', 'landmark': 'stomach', 'words': 'Roux-en-Y gastric bypass', 'passages': ['P5']},
                {'state': 'altered', 'landmark': 'pouch', 'words': 'small gastric pouch', 'passages': ['P5']})


def rygb(place: str = 'proximal ileum', landmark: str = 'ileum', *, whole_sentence: bool = True):
    exam = f'The enteroscope was advanced through the small gastric pouch and the Roux limb into the {place}.'
    return small_bowel('SINGLE-BALLOON ENTEROSCOPY REPORT', 'Procedure: Single-balloon enteroscopy.',
                       'Single-balloon enteroscopy', RYGB, exam, landmark, place,
                       f'Biopsies of an ulcer in the {place} were taken with cold forceps.', f'an ulcer in the {place}',
                       anatomy=RYGB_ANATOMY, kind_words=exam if whole_sentence else '')


def pouchoscopy(anatomy_line: str, anatomy, *, status_words: str = 'was advanced', pouch_words: str = 'J-pouch'):
    """The review's pouchoscopy into the pre-pouch ileum, its anatomy ``anatomy`` in ``anatomy_line``."""
    return small_bowel('POUCHOSCOPY REPORT', 'Procedure: Pouchoscopy.', 'Pouchoscopy', anatomy_line,
                       f'The endoscope was advanced through the anus into the {pouch_words} and through the pouch '
                       'inlet into the pre-pouch ileum for 15 cm.', 'ileum', 'pre-pouch ileum',
                       'Biopsies of the pre-pouch ileum were taken with cold forceps.', 'pre-pouch ileum',
                       anatomy=anatomy, scope_words='endoscope', status_words=status_words)


BARE_POUCH = 'The patient has a pouch after a proctocolectomy for ulcerative colitis.'
BARE_POUCH_ENTRY = {'state': 'altered', 'landmark': 'pouch', 'words': 'pouch', 'passages': ['P5']}
BOTH = 'The patient has an ileal J-pouch and a Roux-en-Y gastric bypass.'
BOTH_ANATOMY = ({'state': 'altered', 'landmark': 'pouch', 'words': 'ileal J-pouch', 'passages': ['P5']},
                {'state': 'altered', 'landmark': 'stomach', 'words': 'Roux-en-Y gastric bypass', 'passages': ['P5']})


def anatomy_of(sentence: str, words: str):
    """The encounter of an oral double-balloon enteroscopy whose anatomy line is ``sentence`` and whose one pouch
    entry's words are ``words`` (standing in it)."""
    inv, _ = oral_dbe(anatomy_line=sentence,
                      anatomy=({'state': 'altered', 'landmark': 'pouch', 'words': words, 'passages': ['P5']},))
    return events.Reading.of(inv).encounter


class PouchType(SimpleTestCase):
    def test_d141_a_gastric_pouch_is_never_the_small_intestinal_pouch(self):
        """Problem 0 (critical): the review's Roux-en-Y enteroscopy to the proximal ileum. D108 read 'small gastric
        pouch' as the small-intestinal pouch, and D114 read the bare 'pouch' of the kind words as the route: 44386 was
        READY. 44386 is held (its class needs the small-intestinal pouch), never READY; 44377 is READY, as at
        1caaf0609 (c2e53f8e holds both with R6's extent question: it reads no extent on this document)."""
        for whole_sentence in (True, False):
            inv, text = rygb(whole_sentence=whole_sentence)
            encounter = events.Reading.of(inv).encounter
            with self.subTest(whole_sentence=whole_sentence):
                self.assertEqual((classes.routes(encounter), classes.doubted_routes(encounter)),
                                 (frozenset(), frozenset()))
                held(self, code_of(inv, text, '44386'), classes.POUCH, 'ileum', 'proximal ileum', classes.CLASS_FORM)
                ready(self, code_of(inv, text, '44377'))
        inv, text = rygb('mid jejunum', 'jejunum')
        held(self, code_of(inv, text, '44386'), classes.POUCH, 'jejunum', 'mid jejunum', classes.CLASS_FORM)
        ready(self, code_of(inv, text, '44361'))

    def test_d141_the_entrys_own_words_name_the_small_intestinal_pouch(self):
        for sentence, words in (
                (J_POUCH, 'ileal J-pouch'), ('The patient has a Kock pouch.', 'Kock pouch'),
                ('The patient has a pelvic pouch.', 'pelvic pouch'), ('The patient has an S-pouch.', 'S-pouch'),
                ('The patient has a W-pouch.', 'W-pouch'), ('The patient has an IPAA pouch.', 'IPAA pouch'),
                ('The patient has a continent ileostomy pouch.', 'continent ileostomy pouch'),
                ('The patient has an ileoanal pouch.', 'ileoanal pouch'),
                ('The patient has a pouch reservoir.', 'pouch reservoir')):
            with self.subTest(words=words):
                encounter = anatomy_of(sentence, words)
                self.assertEqual((classes.routes(encounter), classes.doubted_routes(encounter)), (POUCH, frozenset()))
        for sentence, words in (('The patient has a small gastric pouch.', 'small gastric pouch'),
                                ('The patient has a gastric pouch after a sleeve.', 'gastric pouch')):
            with self.subTest(words=words):
                encounter = anatomy_of(sentence, words)
                self.assertEqual((classes.routes(encounter), classes.doubted_routes(encounter)),
                                 (frozenset(), frozenset()))

    def test_d141_a_pouch_of_no_stated_type_is_a_doubt(self):
        """'The patient has a pouch after a proctocolectomy.' (words 'pouch'): the pouch is no verified small-intestinal
        pouch, so 44386 is held; it may be one, so the examination's own route still decides the ileal class - read as
        no pouch at all, 44377 would be READY on this pouchoscopy into the pre-pouch ileum (46e461e7f: 44386 READY;
        c2e53f8e holds both, extent and performed_status). With the oral route verified, 44377 is READY."""
        inv, text = pouchoscopy(BARE_POUCH, (BARE_POUCH_ENTRY,), pouch_words='pouch')
        encounter = events.Reading.of(inv).encounter
        self.assertEqual((classes.routes(encounter), classes.doubted_routes(encounter)), (frozenset(), POUCH))
        p = code_of(inv, text, '44377')
        held(self, p, classes.ILEAL, 'ileum', 'pre-pouch ileum', classes.ROUTE_FORM, through=POUCH)
        self.assertIn('through the mouth or through the documented pouch', p.clarifications[0].question)
        held(self, code_of(inv, text, '44386'), classes.POUCH, 'ileum', 'pre-pouch ileum', classes.CLASS_FORM)
        inv, text = pouchoscopy(BARE_POUCH, (BARE_POUCH_ENTRY,), pouch_words='pouch',
                                status_words='was advanced through the anus into the pouch')
        held(self, code_of(inv, text, '44386'), classes.POUCH, 'ileum', 'pre-pouch ileum', classes.CLASS_FORM,
             route=classes.THROUGH_POUCH, route_words='was advanced through the anus into the pouch')
        inv, text = oral_dbe(anatomy_line=BARE_POUCH, anatomy=(BARE_POUCH_ENTRY,), status_words='was advanced orally')
        ready(self, code_of(inv, text, '44377'))

    def test_d141_an_intestinal_pouch_beside_a_gastric_bypass_is_a_doubt(self):
        """DECISIONS D148 (the round-5c review of D141, problem 0) changes this pin's expectation: a pouch entry is
        typed by its OWN words alone, so the 'Roux-en-Y gastric bypass' entry no longer types the 'ileal J-pouch'
        entry - it is the small-intestinal pouch, and with the route stated ('was advanced through the anus into the
        J-pouch') 44386 is READY, the code the document supports (46e461e7f READY; c2e53f8e holds it, performed_status
        and extent: a release the spec states). Name kept."""
        inv, text = pouchoscopy(BOTH, BOTH_ANATOMY, status_words='was advanced through the anus into the J-pouch')
        encounter = events.Reading.of(inv).encounter
        self.assertEqual((classes.routes(encounter), classes.doubted_routes(encounter)), (POUCH, frozenset()))
        ready(self, code_of(inv, text, '44386'))


# --- problems 0 and 4: the route only in a route phrase -------------------------------------------------------------

ANATOMY_MENTION = 'Double-balloon enteroscopy in a patient with an end ileostomy'


class RoutePhrase(SimpleTestCase):
    def test_d141_an_anatomy_mention_never_verifies_the_route(self):
        """Problem 4 (critical): the review's oral double-balloon enteroscopy whose procedure words are 'Double-balloon
        enteroscopy in a patient with an end ileostomy' (status words 'was advanced'; the document says 'advanced
        orally'). D114 read the ileostomy as the route: 44382 READY. 44382 is held (extent), as c2e53f8e holds it;
        44377 too. 'history of', 's/p' and 'status post' mentions name no route either."""
        for words in (ANATOMY_MENTION, 'Double-balloon enteroscopy, history of ileostomy',
                      'Double-balloon enteroscopy s/p ileostomy', 'Double-balloon enteroscopy status post ileostomy'):
            inv, text = oral_dbe(procedure_line=f'Procedure: {words}.', procedure_words=words)
            with self.subTest(words=words):
                self.assertEqual(classes.examination_route(events.Reading.of(inv).events['E1']), ('', ''))
                for code, exam_class in (('44382', classes.STOMA), ('44377', classes.ILEAL)):
                    held(self, code_of(inv, text, code), exam_class, 'ileum', 'proximal ileum', classes.ROUTE_FORM,
                         through=STOMA)

    def test_d141_an_anatomy_mention_beside_the_oral_route_is_a_doubt(self):
        """The mention still names the stoma among the examination's own words, so beside 'was advanced orally' the
        route is not verified (D87): 44377 is held (a cost; c2e53f8e holds it, extent), never READY on the wrong
        class."""
        inv, text = oral_dbe(procedure_line=f'Procedure: {ANATOMY_MENTION}.', procedure_words=ANATOMY_MENTION,
                             status_words='was advanced orally')
        self.assertEqual(classes.examination_route(events.Reading.of(inv).events['E1']), ('', ''))
        held(self, code_of(inv, text, '44377'), classes.ILEAL, 'ileum', 'proximal ileum', classes.ROUTE_FORM,
             through=STOMA)

    def test_d141_a_route_phrase_states_the_stoma_route(self):
        """through, via, per, into, by way of the stoma; 'transstomal'; 'stomal intubation': 44382 READY (as at
        46e461e7f where its words named the ileostomy; c2e53f8e holds every one, extent and performed_status)."""
        built = {'procedure': ileoscopy(procedure_words='Ileoscopy through the ileostomy')}
        for name, route, rest in (('through', 'through the ileostomy', 'into the neo-terminal ileum'),
                                  ('per stoma', 'per stoma', 'into the neo-terminal ileum'),
                                  ('via', "via the patient's end ileostomy", 'into the neo-terminal ileum'),
                                  ('by way of', 'by way of the stoma', 'into the neo-terminal ileum'),
                                  ('into', 'into the stoma', 'and on to the neo-terminal ileum')):
            built[name] = self.with_exam_line(f'was advanced {route}',
                                              f'The enteroscope was advanced {route} {rest} for 25 cm.')
        for name, (inv, text) in built.items():
            with self.subTest(route=name):
                self.assertEqual(classes.examination_route(events.Reading.of(inv).events['E1'])[0],
                                 classes.THROUGH_STOMA)
                ready(self, code_of(inv, text, '44382'))
        for words in ('Transstomal ileoscopy', 'Ileoscopy by stomal intubation'):
            inv, text = self.with_procedure(words)
            with self.subTest(route=words):
                self.assertEqual(classes.examination_route(events.Reading.of(inv).events['E1'])[0],
                                 classes.THROUGH_STOMA)
                ready(self, code_of(inv, text, '44382'))

    def with_exam_line(self, status_words: str, exam_line: str):
        lines = {'P0': HEADER, 'P1': 'ILEOSCOPY THROUGH STOMA REPORT', 'P2': DATED, 'P3': SIGNED,
                 'P4': 'Procedure: Ileoscopy through the ileostomy.', 'P5': ILEOSTOMY, 'P6': exam_line,
                 'P7': 'Biopsies of the neo-terminal ileum were taken with cold forceps.'}
        procedure = a('enteroscopy', 'Ileoscopy', ['P4'])
        e1 = act('E1', 'P6', 'examination', 'enteroscope', status_words=status_words, procedure=procedure,
                 technique=a('endoscope', 'enteroscope', ['P6']))
        e2 = act('E2', 'P7', 'biopsy', 'Biopsies', status_words='were taken', procedure=procedure,
                 technique=a('cold_forceps', 'cold forceps', ['P7']),
                 target=tg('', 'neo_terminal_ileum', 'neo-terminal ileum', ['P7']))
        return document(lines, found=[e1, e2], anatomy=[STOMA_ENTRY],
                        reach=[reaching('E1', 'neo_terminal_ileum', 'neo-terminal ileum', 'P6')])

    def with_procedure(self, words: str):
        lines = {'P0': HEADER, 'P1': 'ILEOSCOPY REPORT', 'P2': DATED, 'P3': SIGNED, 'P4': f'Procedure: {words}.',
                 'P5': ILEOSTOMY, 'P6': 'The enteroscope was advanced into the neo-terminal ileum for 25 cm.',
                 'P7': 'Biopsies of the neo-terminal ileum were taken with cold forceps.'}
        procedure = a('enteroscopy', words, ['P4'])
        e1 = act('E1', 'P6', 'examination', 'enteroscope', status_words='was advanced', procedure=procedure,
                 technique=a('endoscope', 'enteroscope', ['P6']))
        e2 = act('E2', 'P7', 'biopsy', 'Biopsies', status_words='were taken', procedure=procedure,
                 technique=a('cold_forceps', 'cold forceps', ['P7']),
                 target=tg('', 'neo_terminal_ileum', 'neo-terminal ileum', ['P7']))
        return document(lines, found=[e1, e2], anatomy=[STOMA_ENTRY],
                        reach=[reaching('E1', 'neo_terminal_ileum', 'neo-terminal ileum', 'P6')])

    def test_d141_a_place_named_in_the_statement_is_no_route(self):
        """D114's disclosed gap 5(b): status words 'was advanced to the distal ileum, 20 cm proximal to the ileostomy'
        verified the stoma route (44382 READY at 46e461e7f; c2e53f8e holds it, extent). 'to the ileostomy' is a place:
        held. So is the pre-pouch ileum in 'was advanced into the pre-pouch ileum' (44386 READY at 46e461e7f; c2e53f8e
        holds it)."""
        place_words = 'was advanced to the distal ileum, 20 cm proximal to the ileostomy'
        inv, text = oral_dbe(place='distal ileum', status_words=place_words,
                             exam_line=f'The double-balloon enteroscope {place_words}.')
        self.assertEqual(classes.examination_route(events.Reading.of(inv).events['E1']), ('', ''))
        held(self, code_of(inv, text, '44382'), classes.STOMA, 'ileum', 'distal ileum', classes.ROUTE_FORM,
             through=STOMA)
        inv, text = oral_dbe(anatomy_line=J_POUCH, anatomy=(POUCH_ENTRY,), place='pre-pouch ileum',
                             exam_line='The double-balloon enteroscope was advanced into the pre-pouch ileum.',
                             status_words='was advanced into the pre-pouch ileum')
        self.assertEqual(classes.examination_route(events.Reading.of(inv).events['E1']), ('', ''))
        held(self, code_of(inv, text, '44386'), classes.POUCH, 'ileum', 'pre-pouch ileum', classes.ROUTE_FORM,
             through=POUCH)

    def test_d141_a_pouchoscopy_is_ready_through_its_route_phrase(self):
        """The READY control of the changed D114 pin: 'Pouchoscopy' states no route phrase (held), 'was advanced through
        the anus into the J-pouch' does - 44386 READY, 44377 the class question with the route named."""
        inv, text = pouchoscopy(J_POUCH, (POUCH_ENTRY,), status_words='was advanced through the anus into the J-pouch')
        self.assertEqual(classes.examination_route(events.Reading.of(inv).events['E1']),
                         (classes.THROUGH_POUCH, 'was advanced through the anus into the J-pouch'))
        ready(self, code_of(inv, text, '44386'))
        held(self, code_of(inv, text, '44377'), classes.ILEAL, 'ileum', 'pre-pouch ileum', classes.CLASS_FORM,
             route=classes.THROUGH_POUCH, route_words='was advanced through the anus into the J-pouch')

    def test_d141_a_route_phrase_never_runs_across_a_mark_a_break_or_its_reach(self):
        for text, route, expected in (
                ('through the pouch inlet', classes.THROUGH_POUCH, True),
                ("through the patient's end ileostomy", classes.THROUGH_STOMA, True),
                ('into the ileal J-pouch', classes.THROUGH_POUCH, True),
                ('per stoma', classes.THROUGH_STOMA, True),
                ('trans-stomal', classes.THROUGH_STOMA, True),
                ('in a patient with an end ileostomy', classes.THROUGH_STOMA, False),
                ('through the mouth, ileostomy in place', classes.THROUGH_STOMA, False),
                ('was advanced per os with an ileostomy', classes.THROUGH_STOMA, False),
                ('was advanced into small bowel to stoma', classes.THROUGH_STOMA, False),
                ('into the pre-pouch ileum', classes.THROUGH_POUCH, False),
                ('through the long tortuous distal small bowel stoma', classes.THROUGH_STOMA, False),
                ('pouchoscopy', classes.THROUGH_POUCH, False)):
            with self.subTest(text=text):
                self.assertIs(classes.route_phrase(text, route), expected)


# --- problem 1: the act's region within the EGD's verified reach ---------------------------------------------------

D3_PART = ('Push enteroscopy: The enteroscope was then advanced to the proximal jejunum, and an angioectasia in the '
           'third portion of the duodenum was treated with argon plasma coagulation.')
D3_LINE = 'An angioectasia in the third portion of the duodenum was treated with argon plasma coagulation.'
PUSH = 'Push enteroscopy: The enteroscope was then advanced to the proximal jejunum.'
EGD_LINE = 'EGD: The gastroscope was advanced to the second portion of the duodenum.'
GASTRIC = 'Two gastric antral angioectasias'


def egd_push(act_line: str = '', act_pid: str = 'P7', *, landmark: str = 'duodenum', words: str = '',
             status_words: str = 'was treated', push_line: str = PUSH, egd_line: str = EGD_LINE,
             egd_reach=('second_portion_duodenum', 'second portion of the duodenum')):
    """The review's egd_push_case: an EGD (E1, P5; its reach ``egd_reach``), a push enteroscopy to the proximal jejunum
    (E2, P6) and argon plasma coagulation of ``words`` at ``landmark`` filed under the enteroscopy (E3, in ``act_pid``:
    P7 a line of its own, ``act_line``; or P6, told in ``push_line``)."""
    lines = {'P0': HEADER, 'P1': 'EGD AND PUSH ENTEROSCOPY REPORT', 'P2': DATED, 'P3': SIGNED,
             'P4': 'Procedure: EGD and push enteroscopy.', 'P5': egd_line, 'P6': push_line}
    if act_pid == 'P7':
        lines['P7'] = act_line
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
    return document(lines, found=found, lesions=[lesion],
                    reach=[reaching('E1', egd_reach[0], egd_reach[1], 'P5'),
                           reaching('E2', 'jejunum', 'proximal jejunum', 'P6')])


def picks(inv, text, chosen):
    return run(inv, text, [(code, line(text, pid)) for code, pid in chosen])


def family_of_e3(inv) -> str:
    reading = events.Reading.of(inv)
    return coverage.coding_family(reading, reading.events['E3'])


class RegionWithinTheReach(SimpleTestCase):
    def test_d141_the_in_sentence_d3_angioectasia_stays_the_enteroscopys(self):
        """Problem 1: the angioectasia in the third portion of the duodenum told in the push enteroscopy's own sentence,
        at the generic duodenum's landmark. D114 moved it to the EGD (44369 held, 43235 held base_included, 44360 the
        procedure question). 44369 READY, 43235 READY beside it and 44360 base_included, as c2e53f8e. DECISIONS D148
        (the round-5c review of D141, problems 1 and 2): the act stays by its own words naming the third portion, no
        longer by a shared passage (told_with_its_examination is gone); the outcome is unchanged."""
        inv, text = egd_push(act_pid='P6', push_line=D3_PART,
                             words='an angioectasia in the third portion of the duodenum')
        self.assertEqual(family_of_e3(inv), 'gi.enteroscopy')
        self.assertTrue(coverage.beyond_reach(events.Reading.of(inv).events['E1'], 'duodenum',
                                              'an angioectasia in the third portion of the duodenum'))
        ready(self, code_of(inv, text, '44369', 'P6'))
        result = picks(inv, text, (('44369', 'P6'), ('43235', 'P5')))
        ready(self, proposal(result, '44369'))
        ready(self, proposal(result, '43235'))
        p = code_of(inv, text, '44360', 'P6')
        self.assertEqual((p.status, asked(p), check(p, BASE).status, check(p, ELSEWHERE)),
                         ('needs_clarification', ['base_included'], 'warn', None))

    def test_d141_on_a_line_of_its_own_the_act_moves_as_the_installed_release_reads_it(self):
        """The separate-line twin, and a duodenal angioectasia of no stated portion on its own line: the generic
        duodenum may be either scope's (the EGD reached the duodenum), so the act moves - 44369 held
        (service.act_elsewhere, performed_status) and 43235 held base_included, as c2e53f8e holds both. Kept with the
        enteroscopy as the spec's first clause reads, the second would be READY on an act that may be the EGD's.
        DECISIONS D148 (the round-5c review of D141, problems 1 and 2) changes this pin's expectation: the separate-line
        twin's own words name the third portion, beyond the EGD's verified reach, so it stays the enteroscopy's (44369
        READY: tests/test_interpretation_r5d_enteroscopy.py pins it); the act of no stated portion still moves."""
        for name, act_line, words in (
                ('no portion', 'A duodenal angioectasia was treated with argon plasma coagulation.',
                 'A duodenal angioectasia'),):
            inv, text = egd_push(act_line, words=words)
            with self.subTest(case=name):
                self.assertEqual(family_of_e3(inv), 'gi.egd')
                p = code_of(inv, text, '44369')
                self.assertEqual((p.status, asked(p), check(p, ELSEWHERE).status),
                                 ('needs_clarification', ['performed_status'], 'warn'))
                p = proposal(picks(inv, text, (('44369', 'P7'), ('43235', 'P5'))), '43235')
                self.assertEqual((p.status, asked(p)), ('needs_clarification', ['base_included']))

    def test_d141_an_act_told_in_a_sentence_of_both_examinations_moves(self):
        """Told in a passage the EGD's own statement shares, the act's sentence is not its examination's alone: it moves
        (44369 held, as c2e53f8e reads a duodenal act by its region). DECISIONS D148: the shared-passage test is gone
        (the outcome is unchanged): the act's own words name no portion beyond the second, so it moves."""
        both = ('EGD and push enteroscopy: The gastroscope was advanced to the second portion of the duodenum and the '
                'enteroscope was then advanced to the proximal jejunum, and a duodenal angioectasia was treated with '
                'argon plasma coagulation.')
        lines = {'P0': HEADER, 'P1': 'EGD AND PUSH ENTEROSCOPY REPORT', 'P2': DATED, 'P3': SIGNED,
                 'P4': 'Procedure: EGD and push enteroscopy.', 'P5': both}
        upper, push = a('egd', 'EGD', ['P5']), a('enteroscopy', 'push enteroscopy', ['P5'])
        found = [act('E1', 'P5', 'examination', 'gastroscope', status_words='was advanced', procedure=upper,
                     technique=a('endoscope', 'gastroscope', ['P5'])),
                 act('E2', 'P5', 'examination', 'enteroscope', status_words='was then advanced', procedure=push,
                     technique=a('endoscope', 'enteroscope', ['P5'])),
                 act('E3', 'P5', 'ablation', 'argon plasma coagulation', status_words='was treated', procedure=push,
                     technique=a('argon_plasma', 'argon plasma coagulation', ['P5']),
                     target=tg('L1', 'duodenum', 'a duodenal angioectasia', ['P5']))]
        lesion = {'id': 'L1', 'words': 'a duodenal angioectasia', 'landmark': 'duodenum', 'site_words': '',
                  'size_words': '', 'multiplicity': 'group', 'passages': ['P5']}
        inv, text = document(lines, found=found, lesions=[lesion],
                             reach=[reaching('E1', 'second_portion_duodenum', 'second portion of the duodenum', 'P5'),
                                    reaching('E2', 'jejunum', 'proximal jejunum', 'P5')])
        reading = events.Reading.of(inv)
        self.assertEqual(sorted(event['catalogue_kind'] for event in coverage.done_examinations(reading, 'gi.egd')
                                + coverage.done_examinations(reading, 'gi.enteroscopy')),
                         ['examination', 'examination'])
        self.assertFalse(coverage.beyond_reach(reading.events['E1'], 'duodenum', 'a duodenal angioectasia'))
        self.assertEqual(family_of_e3(inv), 'gi.egd')
        p = code_of(inv, text, '44369', 'P5')
        self.assertEqual((p.status, check(p, ELSEWHERE).status), ('needs_clarification', 'warn'))

    def test_d141_an_act_beyond_the_egds_verified_reach_stays(self):
        """The spec's 'a duodenal portion the done EGD's verified reach does not cover': an EGD verified to the bulb
        beside an APC at the second portion, and an EGD verified to the gastric antrum beside an APC at the bulb - each
        on a line of its own - keep Gemini's family: 44369 READY (46e461e7f held; c2e53f8e holds it, performed_status:
        it reads the region alone)."""
        for name, egd_line, reach, landmark, act_line in (
                ('bulb reach', 'EGD: The gastroscope was advanced to the duodenal bulb.', ('duodenal_bulb',
                                                                                          'duodenal bulb'),
                 'second_portion_duodenum',
                 'An angioectasia in the second portion of the duodenum was treated with argon plasma coagulation.'),
                ('antrum reach', 'EGD: The gastroscope was advanced to the gastric antrum.', ('gastric_antrum',
                                                                                             'gastric antrum'),
                 'duodenal_bulb', 'An angioectasia in the duodenal bulb was treated with argon plasma coagulation.')):
            inv, text = egd_push(act_line, landmark=landmark, words=act_line.split(' was ')[0], egd_line=egd_line,
                                 egd_reach=reach)
            with self.subTest(case=name):
                reading = events.Reading.of(inv)
                self.assertTrue(coverage.beyond_reach(reading.events['E1'], landmark))
                self.assertEqual(family_of_e3(inv), 'gi.enteroscopy')
                ready(self, code_of(inv, text, '44369'))

    def test_d141_an_act_the_egds_reach_may_cover_moves(self):
        """Fail-closed where the reach does not settle it: the EGD's reach not verified (its words not standing in the
        passage) and a reach at the generic duodenum beside an act at the second portion move: 44369 held. DECISIONS
        D148 (the round-5c review of D141, problems 1 and 2) changes this pin's expectation: the act at the second
        portion's landmark told in the push enteroscopy's sentence, whose own words name the third portion (D141's
        recorded cost), now stays - 44369 READY, as c2e53f8e (tests/test_interpretation_r5d_enteroscopy.py pins it)."""
        d2 = 'An angioectasia in the second portion of the duodenum was treated with argon plasma coagulation.'
        for name, options in (
                ('reach not verified', dict(act_line=f'{GASTRIC} were treated with argon plasma coagulation.',
                                            landmark='gastric_antrum', words=GASTRIC, status_words='were treated',
                                            egd_reach=('second_portion_duodenum', 'descending duodenum'))),
                ('reach at the duodenum', dict(act_line=d2, landmark='second_portion_duodenum',
                                               words='An angioectasia in the second portion of the duodenum',
                                               egd_line='EGD: The gastroscope was advanced to the duodenum.',
                                               egd_reach=('duodenum', 'duodenum')))):
            inv, text = egd_push(**options)
            with self.subTest(case=name):
                self.assertEqual(family_of_e3(inv), 'gi.egd')
                p = code_of(inv, text, '44369', options.get('act_pid', 'P7'))
                self.assertEqual((p.status, check(p, ELSEWHERE).status), ('needs_clarification', 'warn'))

    def test_d141_the_reach_order(self):
        cases = (('second_portion_duodenum', 'duodenal_bulb', False),
                 ('duodenal_bulb', 'second_portion_duodenum', True),
                 ('second_portion_duodenum', 'second_portion_duodenum', False), ('duodenum', 'duodenal_bulb', False),
                 ('duodenum', 'second_portion_duodenum', False), ('duodenal_bulb', 'duodenum', False),
                 ('gastric_antrum', 'duodenum', True), ('distal_esophagus', 'gastric_body', True),
                 ('second_portion_duodenum', 'gastric_antrum', False), ('jejunum', 'second_portion_duodenum', False),
                 ('pouch', 'duodenal_bulb', False))
        for reach, landmark, expected in cases:
            examination = {'extent': {'value': reach, 'state': 'verified', 'open': False, 'words': {'text': reach}}}
            with self.subTest(reach=reach, landmark=landmark):
                self.assertIs(coverage.beyond_reach(examination, landmark), expected)
        unverified = {'extent': {'value': 'duodenal_bulb', 'state': 'unverified', 'open': False, 'words': None}}
        self.assertFalse(coverage.beyond_reach(unverified, 'second_portion_duodenum'))


# --- problem 5: the act's question beside the base rule's ---------------------------------------------------------

class BaseQuestionKept(SimpleTestCase):
    def test_d141_the_base_question_stays_beside_the_acts(self):
        """Problem 5: on the parity note's input the base rule asked 44360 'Is 44360 reported separately from ablation
        for this examination?' at 1caaf0609 (and c2e53f8e asks it on the in-sentence phrasing); D114's move took its
        only act and the act's procedure question took its place. The one question now asks the base rule's first,
        then the act's (fact procedure: the base rule owns base_included, and the review overlay recomputes it from
        the coding record)."""
        inv, text = egd_push(f'{GASTRIC} were treated with argon plasma coagulation.', landmark='gastric_antrum',
                             words=GASTRIC, status_words='were treated')
        p = code_of(inv, text, '44360', 'P6')
        self.assertEqual((p.status, asked(p), check(p, ELSEWHERE).status, p.clarifications[0].question),
                         ('needs_clarification', ['procedure'], 'warn',
                          'Is 44360 reported separately from ablation for this examination? In which procedure was '
                          'the ablation (“Two gastric antral angioectasias”) done?'))
        self.assertEqual(classes.BASE_QUESTION.format(code='44360', included='ablation'),
                         combination.base_hold('44360', 'gi.enteroscopy', 'sel:0', ('ablation',), None)[1].question)
        reading = events.Reading.of(inv)
        self.assertFalse(classes.base_asked(reading, coverage.sessions(reading)))

    def test_d141_a_moved_act_in_doubt_keeps_the_base_rules_in_doubt_label(self):
        """The base rule names an act in doubt '<label> (stated in doubt)' (combination.base_included): the gastric APC
        whose time words do not stand in its passage is doubted, never reportable, and the kept question says so."""
        lines = {'P0': HEADER, 'P1': 'EGD AND PUSH ENTEROSCOPY REPORT', 'P2': DATED, 'P3': SIGNED,
                 'P4': 'Procedure: EGD and push enteroscopy.', 'P5': EGD_LINE, 'P6': PUSH,
                 'P7': f'{GASTRIC} were treated with argon plasma coagulation.'}
        upper, push = a('egd', 'EGD', ['P5']), a('enteroscopy', 'Push enteroscopy', ['P6'])
        found = [act('E1', 'P5', 'examination', 'gastroscope', status_words='was advanced', procedure=upper,
                     technique=a('endoscope', 'gastroscope', ['P5'])),
                 act('E2', 'P6', 'examination', 'enteroscope', status_words='was then advanced', procedure=push,
                     technique=a('endoscope', 'enteroscope', ['P6'])),
                 act('E3', 'P7', 'ablation', 'argon plasma coagulation', status_words='were treated', procedure=push,
                     technique=a('argon_plasma', 'argon plasma coagulation', ['P7']),
                     target=tg('L1', 'gastric_antrum', GASTRIC, ['P7']),
                     time=a('current_encounter', 'during the procedure', ['P7']))]
        lesion = {'id': 'L1', 'words': GASTRIC, 'landmark': 'gastric_antrum', 'site_words': '', 'size_words': '',
                  'multiplicity': 'group', 'passages': ['P7']}
        inv, text = document(lines, found=found, lesions=[lesion],
                             reach=[reaching('E1', 'second_portion_duodenum', 'second portion of the duodenum', 'P5'),
                                    reaching('E2', 'jejunum', 'proximal jejunum', 'P6')])
        reading = events.Reading.of(inv)
        self.assertEqual((coverage.reportable(reading, reading.events['E3']),
                          coverage.doubted(reading, reading.events['E3']), family_of_e3(inv)), (False, True, 'gi.egd'))
        p = code_of(inv, text, '44360', 'P6')
        self.assertEqual((p.status, asked(p), p.clarifications[0].question),
                         ('needs_clarification', ['procedure'],
                          'Is 44360 reported separately from ablation (stated in doubt) for this examination? In which '
                          'procedure was the ablation (“Two gastric antral angioectasias”) done?'))

    def test_d141_where_the_base_rule_still_asks_the_act_adds_its_own_question_alone(self):
        """A jejunal APC beside the gastric one, both filed under the enteroscopy: the jejunal act stays in the
        enteroscopy's session, the base rule asks base_included from it, and the moved act's question is its own."""
        jejunal = 'Two jejunal angioectasias were treated with argon plasma coagulation.'
        lines = {'P0': HEADER, 'P1': 'EGD AND PUSH ENTEROSCOPY REPORT', 'P2': DATED, 'P3': SIGNED,
                 'P4': 'Procedure: EGD and push enteroscopy.', 'P5': EGD_LINE, 'P6': PUSH,
                 'P7': f'{GASTRIC} were treated with argon plasma coagulation.', 'P8': jejunal}
        upper, push = a('egd', 'EGD', ['P5']), a('enteroscopy', 'Push enteroscopy', ['P6'])
        found = [act('E1', 'P5', 'examination', 'gastroscope', status_words='was advanced', procedure=upper,
                     technique=a('endoscope', 'gastroscope', ['P5'])),
                 act('E2', 'P6', 'examination', 'enteroscope', status_words='was then advanced', procedure=push,
                     technique=a('endoscope', 'enteroscope', ['P6'])),
                 act('E3', 'P7', 'ablation', 'argon plasma coagulation', status_words='were treated', procedure=push,
                     technique=a('argon_plasma', 'argon plasma coagulation', ['P7']),
                     target=tg('L1', 'gastric_antrum', GASTRIC, ['P7'])),
                 act('E4', 'P8', 'ablation', 'argon plasma coagulation', status_words='were treated', procedure=push,
                     technique=a('argon_plasma', 'argon plasma coagulation', ['P8']),
                     target=tg('L2', 'jejunum', 'Two jejunal angioectasias', ['P8']))]
        lesions = [{'id': lid, 'words': words, 'landmark': landmark, 'site_words': '', 'size_words': '',
                    'multiplicity': 'group', 'passages': [pid]}
                   for lid, words, landmark, pid in (('L1', GASTRIC, 'gastric_antrum', 'P7'),
                                                     ('L2', 'Two jejunal angioectasias', 'jejunum', 'P8'))]
        inv, text = document(lines, found=found, lesions=lesions,
                             reach=[reaching('E1', 'second_portion_duodenum', 'second portion of the duodenum', 'P5'),
                                    reaching('E2', 'jejunum', 'proximal jejunum', 'P6')])
        reading = events.Reading.of(inv)
        self.assertTrue(classes.base_asked(reading, coverage.sessions(reading)))
        p = code_of(inv, text, '44360', 'P6')
        self.assertEqual((p.status, asked(p), p.clarifications[-1].question),
                         ('needs_clarification', ['base_included', 'procedure'],
                          'In which procedure was the ablation (“Two gastric antral angioectasias”) done?'))
