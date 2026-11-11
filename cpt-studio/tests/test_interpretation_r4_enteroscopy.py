"""DECISIONS D108 (the Gemini migration's round-4 refutation, finding 24), SYNTHETIC, built from the finding's own
documents and variants: a small-bowel enteroscopy code is READY only when its CLASS fits its session examination's
verified reach and, for the stoma and pouch codes, the encounter's verified route (studio/interpretation/classes.py):
- 44360-44373 (beyond the second portion of the duodenum, not including the ileum): a verified jejunal reach;
- 44376-44379 (including the ileum): a verified ileal reach, and never an examination stated incomplete;
- 44380-44384 (ileoscopy through a stoma): the encounter's verified stoma and an ileal reach;
- 44385-44386 (a small-intestinal pouch): the encounter's verified pouch and a reach in the pouch or the ileum.
A reach at the bulb or the second portion of the duodenum fits no enteroscopy code. A code whose class does not fit is
held with the extent question - D43's class question where the reach fits a class - never READY and never excluded; an
unverified reach is R6's own extent question. At 437b708bb each held input below was READY with no question; the
installed release c2e53f8e holds each of finding 24's inputs (performed_status and extent: it reads no enteroscopy
reach on them). Nothing is sent."""
from __future__ import annotations

from django.test import SimpleTestCase

from studio import customer_api
from studio.gi import catalogue
from studio.gi.profiles import PROFILES, family_for_code
from studio.interpretation import classes, coverage, events, normalize, wording
from studio.validation import checks
from tests.test_interpretation_events import ROWS, asked, check, proposal, run
from tests.test_interpretation_identity import a, accepted, act, sc, tg

EXAMINATION_CLASS = 'facts.examination_class'
INCOMPLETE = 'service.incomplete'
HEADER = 'SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE'
DATED = 'Date of service: November 5, 2026'
SIGNED = 'Endoscopist: Tomas Reyes, MD (fictional)'
LOOPING = 'The examination was incomplete because of looping.'
LOOPED = a('incomplete', 'incomplete', ['P9'])  # the reach's completion, verified in LOOPING
# R6's extent question for the enteroscopy profile, in the installed release's words ("Small-bowel enteroscopy: confirm
# the furthest extent reached.", as c2e53f8e asks it on every input of finding 24)
EXTENT = checks.FACT_QUESTIONS['extent'].format(label=PROFILES['gi.enteroscopy'].label)
JEJUNUM, ILEUM, D2, BULB = 'mid jejunum', 'proximal ileum', 'second portion of the duodenum', 'duodenal bulb'


def report(lines: dict, *, found, lesions=(), reach=(), anatomy=(), open_questions=()):
    """(the normalized inventory, the document's text) of a synthetic answer over ``lines`` ({passage id: line}, in
    order), dated in P2 and signed in P3 as finding 24's documents are, read by read.read and normalized with the real
    linked steps."""
    if any(entry['completion']['passages'] == ['P9'] for entry in reach) or open_questions:
        lines = {**lines, 'P9': LOOPING}
    text = '\n'.join(lines.values()) + '\n'
    value = {'passages': [{'id': pid, 'text': line} for pid, line in lines.items()],
             'encounter': {'date_of_service': {'value': '2026-11-05', 'state': 'stated', 'words': 'November 5, 2026',
                                               'passages': ['P2'], 'other_dates': []},
                           'documenting_endoscopist': {'words': 'Tomas Reyes, MD (fictional)', 'passages': ['P3']},
                           'team': [], 'anatomy': list(anatomy), 'reach': list(reach), 'visit_facts': []},
             'lesions': list(lesions), 'events': list(found), 'open_questions': list(open_questions)}
    return normalize.normalize(accepted(value), text), text


def reaching(landmark: str, words: str, completion=None) -> dict:
    return {'event': 'E1', 'landmark': landmark, 'words': words, 'passages': ['P5'],
            'completion': completion or a('not_stated')}


def dbe(place: str = JEJUNUM, landmark: str = 'jejunum', *, completion=None, status=None, open_questions=(),
        biopsy=None, reach_words: str = ''):
    """Finding 24's document (cases/dbe_jejunum_44377.json), as Gemini reads it on the prompt contract: an oral
    double-balloon enteroscopy (E1) to ``place`` - its reach entry at ``landmark`` (P5) - and the cold-forceps biopsy of
    an ulcer there (E2, P6). ``completion``: the reach's completion (LOOPED: LOOPING in P9); ``status``: the
    examination's status attribute; ``biopsy``: E2 replaced; ``reach_words``: the reach's words, when not ``place``."""
    lines = {'P0': HEADER, 'P1': 'DOUBLE-BALLOON ENTEROSCOPY REPORT', 'P2': DATED, 'P3': SIGNED,
             'P4': 'Indication: Suspected small-bowel bleeding on capsule endoscopy.',
             'P5': f'The double-balloon enteroscope was advanced orally to the {place}.',
             'P6': f'Biopsies of an ulcer in the {place} were taken with cold forceps.'}
    procedure = a('enteroscopy', 'DOUBLE-BALLOON ENTEROSCOPY', ['P1'])
    examination = act('E1', 'P5', 'examination', 'double-balloon enteroscope', status_words='was advanced',
                      procedure=procedure, technique=a('endoscope', 'double-balloon enteroscope', ['P5']))
    if status is not None:
        examination['status'] = status
        lines['P9'] = LOOPING
    sampled = biopsy or act('E2', 'P6', 'biopsy', 'Biopsies', status_words='were taken', procedure=procedure,
                            technique=a('cold_forceps', 'cold forceps', ['P6']),
                            target=tg('L1', landmark, f'an ulcer in the {place}', ['P6']))
    if biopsy is not None:
        lines[biopsy['status']['passages'][0]] = BIOPSY_DENIED
    ulcer = {'id': 'L1', 'words': 'an ulcer', 'landmark': landmark, 'site_words': place, 'size_words': '',
             'multiplicity': 'single', 'passages': ['P6']}
    return report(lines, found=[examination, sampled], lesions=[ulcer],
                  reach=[reaching(landmark, reach_words or place, completion)], open_questions=open_questions)


BIOPSY_DENIED = 'No biopsies were taken.'


def push(place: str = D2, landmark: str = 'second_portion_duodenum', *, completion=None):
    """Finding 24's push enteroscopy (cases/ent_reach_d2.json, ent_reach_bulb.json, ent_short_*.json): the enteroscope
    (E1) advanced to ``place`` - its reach at ``landmark`` (P5) - argon plasma coagulation of two angioectasias there
    (E2, P6) and a cold-forceps biopsy of its mucosa (E3, P7); ``completion``: the reach's completion."""
    lines = {'P0': HEADER, 'P1': 'PUSH ENTEROSCOPY REPORT', 'P2': DATED, 'P3': SIGNED,
             'P4': 'Indication: Iron-deficiency anemia with suspected small-bowel bleeding.',
             'P5': f'The enteroscope was advanced to the {place}.',
             'P6': f'Two angioectasias in the {place} were treated with argon plasma coagulation.',
             'P7': f'A biopsy of the {place} mucosa was taken with cold forceps.'}
    procedure = a('enteroscopy', 'PUSH ENTEROSCOPY', ['P1'])
    found = [act('E1', 'P5', 'examination', 'enteroscope', status_words='was advanced', procedure=procedure,
                 technique=a('endoscope', 'enteroscope', ['P5'])),
             act('E2', 'P6', 'ablation', 'argon plasma coagulation', status_words='were treated', procedure=procedure,
                 technique=a('argon_plasma', 'argon plasma coagulation', ['P6']),
                 target=tg('L1', landmark, f'Two angioectasias in the {place}', ['P6'])),
             act('E3', 'P7', 'biopsy', 'biopsy', status_words='was taken', procedure=procedure,
                 technique=a('cold_forceps', 'cold forceps', ['P7']),
                 target=tg('', landmark, f'the {place} mucosa', ['P7']))]
    group = {'id': 'L1', 'words': 'Two angioectasias', 'landmark': landmark, 'site_words': place, 'size_words': '',
             'multiplicity': 'group', 'passages': ['P6']}
    return report(lines, found=found, lesions=[group], reach=[reaching(landmark, place, completion)])


ILEOSTOMY = 'The patient has an end ileostomy after a total proctocolectomy for Crohn disease.'
J_POUCH = 'The patient has an ileal J-pouch after a restorative proctocolectomy for ulcerative colitis.'


def ileoscopy(*, stoma: str = 'end ileostomy'):
    """The stoma class's control: an ileoscopy (E1) through an end ileostomy into the neo-terminal ileum (its reach, P5)
    with a cold-forceps biopsy there (E2, P6); ``stoma``: the words of the encounter's altered-anatomy stoma entry in
    ILEOSTOMY (P4) - '' for none."""
    lines = {'P0': HEADER, 'P1': 'ILEOSCOPY THROUGH STOMA REPORT', 'P2': DATED, 'P3': SIGNED, 'P4': ILEOSTOMY,
             'P5': 'The enteroscope was advanced through the ileostomy into the neo-terminal ileum for 25 cm.',
             'P6': 'Biopsies of the neo-terminal ileum were taken with cold forceps.'}
    procedure = a('enteroscopy', 'ILEOSCOPY', ['P1'])
    found = [act('E1', 'P5', 'examination', 'enteroscope', status_words='was advanced', procedure=procedure,
                 technique=a('endoscope', 'enteroscope', ['P5'])),
             act('E2', 'P6', 'biopsy', 'Biopsies', status_words='were taken', procedure=procedure,
                 technique=a('cold_forceps', 'cold forceps', ['P6']),
                 target=tg('', 'neo_terminal_ileum', 'neo-terminal ileum', ['P6']))]
    anatomy = [{'state': 'altered', 'landmark': 'stoma', 'words': stoma, 'passages': ['P4']}] if stoma else []
    return report(lines, found=found, anatomy=anatomy,
                  reach=[reaching('neo_terminal_ileum', 'neo-terminal ileum')])


def pouchoscopy(*, pouch: str = 'ileal J-pouch'):
    """The pouch class's control: the endoscope (E1) advanced into the J-pouch (its reach, P5) with a cold-forceps biopsy
    of the pouch body (E2, P6); ``pouch``: the words of the encounter's altered-anatomy pouch entry in J_POUCH (P4) - ''
    for none."""
    lines = {'P0': HEADER, 'P1': 'POUCHOSCOPY REPORT', 'P2': DATED, 'P3': SIGNED, 'P4': J_POUCH,
             'P5': 'The endoscope was advanced through the anus into the J-pouch.',
             'P6': 'Biopsies of the pouch body were taken with cold forceps.'}
    procedure = a('enteroscopy', 'POUCHOSCOPY', ['P1'])
    found = [act('E1', 'P5', 'examination', 'endoscope', status_words='was advanced', procedure=procedure,
                 technique=a('endoscope', 'endoscope', ['P5'])),
             act('E2', 'P6', 'biopsy', 'Biopsies', status_words='were taken', procedure=procedure,
                 technique=a('cold_forceps', 'cold forceps', ['P6']), target=tg('', 'pouch', 'pouch body', ['P6']))]
    anatomy = [{'state': 'altered', 'landmark': 'pouch', 'words': pouch, 'passages': ['P4']}] if pouch else []
    return report(lines, found=found, anatomy=anatomy, reach=[reaching('pouch', 'J-pouch')])


def line(text: str, pid: str) -> str:
    """The document's line ``pid`` (passages are one line each)."""
    return text.splitlines()[int(pid[1:])]


def held(test, p, exam_class: str, reached: str, words: str, form: str) -> None:
    """``p`` is selected and held on its class alone - the class check's warn and one extent question, in ``form``
    (classes.class_hold's) - never excluded and never READY; its act is supported (the class is the only reason)."""
    reason, question = classes.class_hold(p.code, exam_class, reached, words, form)
    test.assertEqual((p.bucket, p.status, asked(p), p.support['reason']),
                     ('selected', 'needs_clarification', ['extent'], events.SUPPORTED))
    test.assertEqual((check(p, EXAMINATION_CLASS).status, check(p, EXAMINATION_CLASS).label,
                      check(p, EXAMINATION_CLASS).detail, p.clarifications[0].question, p.clarifications[0].reason),
                     ('warn', classes.CHECK[1], reason, question, reason))
    test.assertEqual(check(p, 'facts.required').status, 'pass')  # the reach is verified: R6 asks nothing itself


def ready(test, p) -> None:
    test.assertEqual((p.bucket, p.status, asked(p), check(p, EXAMINATION_CLASS)), ('selected', 'ready', [], None))


# --- finding 24's inputs: each was READY at 437b708bb -----------------------------------------------------------------

class FindingInputs(SimpleTestCase):
    def test_d108_44377_on_the_double_balloon_enteroscopy_to_the_mid_jejunum_is_held_with_the_class_question(self):
        """The finding's exact input: 44377 ('including ileum') citing the biopsy sentence of an enteroscopy that
        stopped in the mid jejunum. The jejunum fits 44360-44373, so the question is the class question."""
        inv, text = dbe()
        reading = events.Reading.of(inv)
        session = coverage.sessions(reading)['gi.enteroscopy']
        self.assertEqual((session.event, reading.events['E1']['extent']['value'],
                          reading.events['E1']['extent']['state']), ('E1', 'jejunum', 'verified'))
        p = proposal(run(inv, text, [('44377', line(text, 'P6'))]), '44377')
        held(self, p, classes.ILEAL, 'jejunum', JEJUNUM, classes.CLASS_FORM)
        self.assertEqual(p.clarifications[0].question,
                         'The documented enteroscopy (“mid jejunum”) reached the jejunum. Was a small-bowel enteroscopy '
                         'past the second portion of the duodenum that reaches the ileum performed on the date of '
                         'service?')
        self.assertEqual(p.clarifications[0].reason,
                         'The enteroscopy is documented as reaching the jejunum (“mid jejunum”); 44377 accounts for a '
                         'small-bowel enteroscopy past the second portion of the duodenum that reaches the ileum, which '
                         'CPT Studio could not find in the document.')

    def test_d108_44377_and_44361_proposed_together_for_the_one_biopsy_compete_and_the_misfit_asks_its_class(self):
        """D40 as D28's EUS siblings show it: CPT Studio never chooses between two codes for one act."""
        inv, text = dbe()
        result = run(inv, text, [('44361', line(text, 'P6')), ('44377', line(text, 'P6'))])
        self.assertEqual({code: (proposal(result, code).status, asked(proposal(result, code)))
                          for code in ('44361', '44377')},
                         {'44361': ('needs_clarification', ['competing_codes']),
                          '44377': ('needs_clarification', ['competing_codes', 'extent'])})

    def test_d108_44361_on_a_reach_into_the_proximal_ileum_is_held_with_the_class_question(self):
        """The finding's variant: 44361 ('not including ileum') on an enteroscopy that reached the proximal ileum."""
        inv, text = dbe(ILEUM, 'ileum')
        p = proposal(run(inv, text, [('44361', line(text, 'P6'))]), '44361')
        held(self, p, classes.JEJUNAL, 'ileum', ILEUM, classes.CLASS_FORM)

    def test_d108_the_stoma_and_pouch_codes_on_an_oral_enteroscopy_are_held(self):
        """The finding's variant: 44382 (ileoscopy through a stoma) and 44386 (a pouch's biopsy) on the oral
        double-balloon enteroscopy to the mid jejunum - no stoma, no pouch, and a jejunal reach."""
        inv, text = dbe()
        for code, exam_class in (('44382', classes.STOMA), ('44386', classes.POUCH)):
            p = proposal(run(inv, text, [(code, line(text, 'P6'))]), code)
            with self.subTest(code=code):
                held(self, p, exam_class, 'jejunum', JEJUNUM, classes.CLASS_FORM)

    def test_d108_a_push_enteroscopy_stopped_at_the_second_portion_or_the_bulb_fits_no_enteroscopy_code(self):
        """The finding's variants: 44369 and 44361, alone and together, on a push enteroscopy stopped at the second
        portion of the duodenum or at the bulb - an upper endoscopy's reach, which no enteroscopy class fits: R6's own
        extent question, the reason naming the reach."""
        for place, landmark, reached in ((D2, 'second_portion_duodenum', 'second portion duodenum'),
                                         (BULB, 'duodenal_bulb', 'duodenal bulb')):
            inv, text = push(place, landmark)
            for picks in ((('44369', 'P6'),), (('44361', 'P7'),), (('44369', 'P6'), ('44361', 'P7'))):
                result = run(inv, text, [(code, line(text, pid)) for code, pid in picks])
                for code, _ in picks:
                    p = proposal(result, code)
                    with self.subTest(reach=landmark, picks=[c for c, _ in picks], code=code):
                        held(self, p, classes.JEJUNAL, reached, place, classes.EXTENT_FORM)
                        self.assertEqual(p.clarifications[0].question, EXTENT)

    def test_d108_a_reach_named_only_as_the_small_bowel_fits_no_class(self):
        """As D28 reads its classes: the small bowel named as such may be the jejunum or the ileum."""
        inv, text = dbe('small bowel', 'small_bowel')
        for code in ('44361', '44377'):
            p = proposal(run(inv, text, [(code, line(text, 'P6'))]), code)
            with self.subTest(code=code):
                held(self, p, classes.code_class(code), 'small bowel', 'small bowel', classes.EXTENT_FORM)

    def test_d108_the_push_enteroscopy_stated_incomplete_at_the_second_portion_is_held_and_keeps_d61s_signals(self):
        """The finding's incomplete variant: the D2 report with a verified 'incomplete' completion was READY with only
        service.incomplete and the 52/53 consideration. Both stay (D61), and the codes are held."""
        inv, text = push(completion=LOOPED)
        self.assertEqual(inv.events['events'][0]['completion']['state'], 'verified')
        for code, pid in (('44369', 'P6'), ('44361', 'P7')):
            p = proposal(run(inv, text, [(code, line(text, pid))]), code)
            with self.subTest(code=code):
                held(self, p, classes.JEJUNAL, 'second portion duodenum', D2, classes.EXTENT_FORM)
                self.assertEqual((p.modifier_considerations, [item.detail for item in p.checks if item.id == INCOMPLETE]),
                                 ((checks.incomplete_consideration(code, ROWS.get(code), 'RVU26D'),),
                                  [wording.incomplete_check('incomplete').detail]))


# --- the classes that fit: READY --------------------------------------------------------------------------------------

class ClassesThatFit(SimpleTestCase):
    def test_d108_a_jejunal_reach_fits_44360_to_44373(self):
        """The finding's control (push enteroscopy to the proximal jejunum: 44361 and 44369 READY, as expected), the
        double-balloon enteroscopy to the mid jejunum's 44361, and the examination-only 44360."""
        inv, text = push('proximal jejunum', 'jejunum')
        result = run(inv, text, [('44369', line(text, 'P6')), ('44361', line(text, 'P7'))])
        for code in ('44369', '44361'):
            with self.subTest(push=code):
                ready(self, proposal(result, code))
        inv, text = dbe()
        ready(self, proposal(run(inv, text, [('44361', line(text, 'P6'))]), '44361'))
        lines_only = dbe()[1]
        examination_only, text = report({pid: line(lines_only, pid) for pid in ('P0', 'P1', 'P2', 'P3', 'P4', 'P5')},
                                        found=[dbe_examination()], reach=[reaching('jejunum', JEJUNUM)])
        ready(self, proposal(run(examination_only, text, [('44360', line(text, 'P5'))]), '44360'))

    def test_d108_an_ileal_reach_fits_44376_to_44379(self):
        for place, landmark in ((ILEUM, 'ileum'), ('terminal ileum', 'terminal_ileum')):
            inv, text = dbe(place, landmark)
            with self.subTest(reach=landmark):
                ready(self, proposal(run(inv, text, [('44377', line(text, 'P6'))]), '44377'))

    def test_d108_an_ileoscopy_through_the_encounters_verified_stoma_fits_44380_to_44384(self):
        """DECISIONS D114 (the round-4 review of D108, problem 0) changes this control's expectation: the encounter's
        verified stoma says a stoma exists, never that the examination went through it, and this answer's examination
        words ('ILEOSCOPY', 'enteroscope', 'was advanced') name no route - so 44382 is held with D114's route question,
        never READY. Its READY control, the route named in the examination's own words, is
        tests/test_interpretation_r5_enteroscopy_route.py's test_d114_44382_on_the_ileoscopy_is_ready_only_through_its_
        verified_stoma_route."""
        inv, text = ileoscopy()
        self.assertEqual(classes.routes(events.Reading.of(inv).encounter), frozenset({'stoma'}))
        p = proposal(run(inv, text, [('44382', line(text, 'P6'))]), '44382')
        reason, question = classes.class_hold('44382', classes.STOMA, 'neo terminal ileum', 'neo-terminal ileum',
                                              classes.ROUTE_FORM, through=frozenset({'stoma'}))
        self.assertEqual((p.bucket, p.status, asked(p), check(p, EXAMINATION_CLASS).status,
                          check(p, EXAMINATION_CLASS).detail, p.clarifications[0].question),
                         ('selected', 'needs_clarification', ['extent'], 'warn', reason, question))

    def test_d108_a_pouch_examination_with_the_encounters_verified_pouch_fits_44385_and_44386(self):
        inv, text = pouchoscopy()
        self.assertEqual(classes.routes(events.Reading.of(inv).encounter), frozenset({'pouch'}))
        ready(self, proposal(run(inv, text, [('44386', line(text, 'P6'))]), '44386'))


def dbe_examination() -> dict:
    return act('E1', 'P5', 'examination', 'double-balloon enteroscope', status_words='was advanced',
               procedure=a('enteroscopy', 'DOUBLE-BALLOON ENTEROSCOPY', ['P1']),
               technique=a('endoscope', 'double-balloon enteroscope', ['P5']))


# --- the route and the completion -------------------------------------------------------------------------------------

class RouteAndCompletion(SimpleTestCase):
    def test_d108_a_stoma_or_pouch_code_needs_the_encounters_verified_route(self):
        """Its own reach without its route is D43's stoma arm: the class question. A stoma or pouch entry whose words do
        not stand in its passage is no verified route."""
        for name, built, code, exam_class, reached, words in (
                ('no stoma', ileoscopy(stoma=''), '44382', classes.STOMA, 'neo terminal ileum', 'neo-terminal ileum'),
                ('stoma unverified', ileoscopy(stoma='loop ileostomy'), '44382', classes.STOMA, 'neo terminal ileum',
                 'neo-terminal ileum'),
                ('no pouch', pouchoscopy(pouch=''), '44386', classes.POUCH, 'pouch', 'J-pouch'),
                ('pouch unverified', pouchoscopy(pouch='Kock pouch'), '44386', classes.POUCH, 'pouch', 'J-pouch')):
            inv, text = built
            self.assertEqual(classes.routes(events.Reading.of(inv).encounter), frozenset())
            p = proposal(run(inv, text, [(code, line(text, 'P6'))]), code)
            with self.subTest(case=name):
                held(self, p, exam_class, reached, words, classes.CLASS_FORM)

    def test_d108_an_examination_stated_incomplete_never_fits_the_ileal_class(self):
        """D43, D56 and D72 as the full EUS class reads them: an 'incomplete' completion in ANY state - verified, its
        words not standing in their passage, opened by Gemini's own question - or the examination's status
        attempted_not_completed holds 44377 on its ileal reach, in the class question's incomplete form."""
        cases = {
            'verified': dict(completion=LOOPED),
            'words not in their passage': dict(completion=a('incomplete', 'could not be completed', ['P9'])),
            'opened': dict(completion=LOOPED, open_questions=[{'about': 'completion', 'events': ['E1'], 'lesions': [],
                                                               'passages': ['P9']}]),
            'attempted_not_completed': dict(status=a('attempted_not_completed', 'was incomplete', ['P9']))}
        control, control_text = dbe(ILEUM, 'ileum')
        ready(self, proposal(run(control, control_text, [('44377', line(control_text, 'P6'))]), '44377'))
        for name, options in cases.items():
            inv, text = dbe(ILEUM, 'ileum', **options)
            examination = events.Reading.of(inv).events['E1']
            self.assertTrue(classes.incomplete(examination), name)
            self.assertEqual(coverage.sessions(events.Reading.of(inv))['gi.enteroscopy'].event, 'E1', name)
            p = proposal(run(inv, text, [('44377', line(text, 'P6'))]), '44377')
            with self.subTest(case=name):
                held(self, p, classes.ILEAL, 'ileum', ILEUM, classes.INCOMPLETE_FORM)
                self.assertIn('is stated to be incomplete', p.clarifications[0].question)

    def test_d108_the_jejunal_class_reads_its_reach_only(self):
        """Like D43's limited class: an examination stated incomplete at a verified jejunal reach still fits 44360-44373
        (READY, with D61's warn and 52/53 consideration); the deeper class is the one an incompleteness withholds."""
        inv, text = dbe(completion=LOOPED)
        p = proposal(run(inv, text, [('44361', line(text, 'P6'))]), '44361')
        ready(self, p)
        self.assertEqual((p.modifier_considerations, [item.detail for item in p.checks if item.id == INCOMPLETE]),
                         ((checks.incomplete_consideration('44361', ROWS.get('44361'), 'RVU26D'),),
                          [wording.incomplete_check('incomplete').detail]))


# --- what D108 leaves to R6, to R1 and to the other families ----------------------------------------------------------

class LeftToTheOtherRules(SimpleTestCase):
    def test_d108_an_unverified_reach_is_r6s_extent_question_alone(self):
        """Reach words that do not stand in their passage: no verified reach, so the class reads nothing and R6 asks the
        missing extent - one question, never a second."""
        inv, text = dbe(reach_words='distal jejunum')
        self.assertNotEqual(events.Reading.of(inv).events['E1']['extent']['state'], 'verified')
        for code in ('44361', '44377'):
            p = proposal(run(inv, text, [(code, line(text, 'P6'))]), code)
            with self.subTest(code=code):
                self.assertEqual((p.bucket, p.status, asked(p), p.clarifications[0].question, check(p, EXAMINATION_CLASS),
                                  check(p, 'facts.required').status),
                                 ('selected', 'needs_clarification', ['extent'], EXTENT, None, 'warn'))

    def test_d108_an_excluded_code_stays_excluded_and_waits_on_its_class(self):
        """D108 never excludes and never releases an exclusion: a denied biopsy excludes 44377 and 44361 by R1, as
        before; the misfit 44377 waits on its class question when reinstated (D28's reinstatement wait), 44361 on
        nothing of its class."""
        denied = act('E2', 'P6', 'biopsy', 'biopsies', status='not_performed', status_words='No biopsies were taken',
                     procedure=a('enteroscopy', 'DOUBLE-BALLOON ENTEROSCOPY', ['P1']),
                     scope=sc('all_of_kind', 'No', ['P6']))
        inv, text = dbe(biopsy=denied)
        _, question = classes.class_hold('44377', classes.ILEAL, 'jejunum', JEJUNUM, classes.CLASS_FORM)
        for code, waits in (('44377', [{'fact': 'extent', 'question': question}]), ('44361', None)):
            p = proposal(run(inv, text, [(code, 'No biopsies were taken')]), code)
            with self.subTest(code=code):  # a code that waits on nothing records no waits (assess._support)
                self.assertEqual((p.bucket, p.status, p.reinstatable, p.support.get('reinstatement_waits')),
                                 ('excluded', 'excluded', True, waits))

    def test_d108_every_catalogue_enteroscopy_code_has_exactly_one_class_and_no_other_code_has_one(self):
        expected = {**{code: classes.JEJUNAL for code in ('44360', '44361', '44363', '44364', '44365', '44366', '44369',
                                                          '44370', '44372', '44373')},
                    **{code: classes.ILEAL for code in ('44376', '44377', '44378', '44379')},
                    **{code: classes.STOMA for code in ('44380', '44381', '44382', '44384')},
                    **{code: classes.POUCH for code in ('44385', '44386')}}
        family = {code for code, profile in catalogue.CODES.items() if profile.family == classes.FAMILY}
        self.assertEqual(family, set(expected))
        self.assertEqual({code: classes.code_class(code) for code in family}, expected)
        self.assertEqual({family_for_code(code) for code in family}, {classes.FAMILY})
        self.assertEqual([code for code in catalogue.CODES if code not in family and classes.code_class(code)], [])
        inv, text = dbe()
        reading = events.Reading.of(inv)
        sessions = coverage.sessions(reading)
        for code in catalogue.CODES:
            if code not in family:
                with self.subTest(code=code):
                    self.assertIsNone(classes.enteroscopy_hold(code, family_for_code(code), 'sel:0', reading, sessions,
                                                               ('jejunum', reading.events['E1']['extent'])))

    def test_d108_the_extent_question_is_r6s_and_no_sentence_names_a_vendor(self):
        self.assertEqual(classes.EXTENT_QUESTION.format(label=wording.family_label(classes.FAMILY)), EXTENT)
        self.assertEqual(EXTENT, 'Small-bowel enteroscopy: confirm the furthest extent reached.')
        for exam_class in classes.CLASSES:
            for form in (classes.CLASS_FORM, classes.INCOMPLETE_FORM, classes.EXTENT_FORM):
                for sentence in classes.class_hold('44377', exam_class, 'jejunum', JEJUNUM, form) + (classes.CHECK[1],):
                    with self.subTest(exam_class=exam_class, form=form):
                        self.assertIsNone(customer_api.FORBIDDEN.search(sentence), sentence)
                        self.assertNotIn('gemini', sentence.lower())
