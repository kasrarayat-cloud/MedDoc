"""DECISIONS D145 (the Gemini migration's round 5d: the round-5c review of the eus3 repair D135-D138,
round5c/review_eus3.json problems 0, 1, 4 and 5), SYNTHETIC, each built from its source's own input. Nothing is sent.
- (1) problem 0 (critical): an EUS-guided act of a kind the EUS's catalogue entry does not list (D137's class), stated
  positive or uncertain, of no other time or performer, and IN DOUBT - its procedure not usable while it is possibly
  current, its status uncertain, its time only possibly current, or a blocking relation on it - is listed among the EUS
  session's 'doubted' entries (coverage.eus_unprofiled_doubt), so an examination-only EUS code beside it is held
  (combination.base_included's doubt arm), as the installed release (c2e53f8e) holds it.
- (2) problem 4: D137's 'reportable' entries take only an act whose status is a usable 'performed'; an act begun and not
  completed is recorded among the 'doubted' entries instead, so the operator report's service rows
  (readers.EventReader.services_section) never print an attempted and failed stent as a placement.
- (3) problem 1 (high): D136's hold on 43240 asks the TARGET question (fact 'target'), quoting the drainage's own
  sentence, with a reason that says what 43240 describes and where the document places the drainage - built after R3 in
  events.evaluate (events._target_hold, as D29's _site_hold) and asked whether or not the EUS examination's own target is
  verified.
- (4) problem 5: a fiducial placement read as 'tattoo' (an injection for coding, mapping.ONE_ACT, so 43253 is supported
  by it) is recorded by its own kind words, never as 'submucosal tattoo'.
Each test asserts in independent subtests - the outcome, the read-time overlay, the record - so a regression shows every
one it breaks."""
from __future__ import annotations

from types import SimpleNamespace

from django.test import SimpleTestCase

from studio.interpretation import ENGINE_VERSION, combination, coverage, events, mapping, readers, wording
from tests.test_interpretation_events import asked, check, exam, inventory, proposal, reached, run
from tests.test_interpretation_identity import a, act, les, tg
from tests.test_interpretation_r3_eus import DUODENUM
from tests.test_interpretation_r3_integration_d88_d93 import reviewed
from tests.test_interpretation_r4_eus_lower import ready_unheld
from tests.test_interpretation_r5_eus import DRAINAGE_LINES, drainage_case
from tests.test_interpretation_r5c_eus import GB, GE, MASS, base_question, gallbladder, with_examination

BASE_INCLUDED = 'services.base_included'
EUS_LABEL = 'endoscopic ultrasound'


def base_held(test, result, code: str, labels: tuple) -> None:
    """``code`` (an examination-only EUS code) is held base_included beside the acts ``labels`` name - base_hold's own
    check and clarification - at assess time, and the read-time overlay keeps it held with the same question."""
    p = proposal(result, code)
    held, spec = combination.base_hold(code, 'gi.eus', p.key, labels, EUS_LABEL)
    test.assertEqual((p.status, asked(p)), ('needs_clarification', ['base_included']))
    test.assertEqual((check(p, BASE_INCLUDED), list(p.clarifications)), (held, [spec]))
    view = reviewed(result, code)
    test.assertEqual((view.status, view.released, [q['question'] for q in view.questions]),
                     ('needs_clarification', (), [spec.question]))


def entries(result, part: str) -> list:
    """(event, kind, label) of the EUS session's ``part`` ('reportable' or 'doubted') event-coding entries."""
    session = result.completeness['event_coding']['sessions']['gi.eus']
    return [(entry['event'], entry['kind'], entry['label']) for entry in session[part]]


# --- (1) problem 0: an act of D137's class in doubt ----------------------------------------------------------------

# Problem 0's input (the reviewer's r_unsettled_stent): an EGD and an EUS examination in one report; the stent's line
# names neither, and Gemini files it under 'eus' with no procedure words (two current families: procedure_unsettled)
EGD_EUS = {'P1': 'UPPER ENDOSCOPY AND ENDOSCOPIC ULTRASOUND',
           'P2': 'The gastroscope was advanced to the second portion of the duodenum; the esophagus, stomach and duodenum '
                 'were normal.',
           'P3': 'The linear echoendoscope was then advanced to the second portion of the duodenum and the pancreatic '
                 'head mass causing the duodenal obstruction was examined.',
           'P4': 'A 20 mm lumen-apposing metal stent was deployed from the gastric body into a distended jejunal loop.'}
UPPER_Q = 'The gastroscope was advanced to the second portion of the duodenum'
EUS_Q = 'The linear echoendoscope was then advanced to the second portion of the duodenum'
STENT_PLACEMENT = 'stent placement'
IN_DOUBT = 'stent placement (stated in doubt)'


def unsettled_stent():
    """Problem 0's input: the EGD to D2 (E1), the EUS examination of the pancreatic head mass (E2, done) and the stent
    (E3, kind stent, procedure 'eus' with no words)."""
    found = [exam('E1', 'P2', words='gastroscope', procedure=a('egd', 'UPPER ENDOSCOPY', ['P1'])),
             act('E2', 'P3', 'examination', 'linear echoendoscope', status_words='was then advanced',
                 procedure=a('eus', 'ENDOSCOPIC ULTRASOUND', ['P1']),
                 technique=a('endoscope', 'linear echoendoscope', ['P3']),
                 target=tg('L1', 'pancreas', 'the pancreatic head mass', ['P3'])),
             act('E3', 'P4', 'stent', 'lumen-apposing metal stent', status_words='was deployed', procedure=a('eus'),
                 technique=a('stent', 'lumen-apposing metal stent', ['P4']),
                 target=tg('', 'jejunum', 'a distended jejunal loop', ['P4']))]
    lesions = [les('L1', 'pancreatic head mass', 'P3', landmark='pancreas', site_words='pancreatic head')]
    return inventory(EGD_EUS, events=found, lesions=lesions,
                     reach=[reached('E1', 'second_portion_duodenum', DUODENUM, 'P2'),
                            reached('E2', 'second_portion_duodenum', DUODENUM, 'P3')])


def stent(passage: str = 'P4', kind_words: str = 'lumen-apposing metal stent', **changes) -> dict:
    """The gastroenterostomy's lumen-apposing stent (E2) beside problem 2's EUS examination (r5c's with_examination)."""
    options = {'status_words': 'was deployed', 'procedure': a('eus', 'EUS-guided', ['P1']),
               'technique': a('stent', 'lumen-apposing metal stent', [passage]),
               'target': tg('', 'jejunum', 'a distended jejunal loop', [passage])}
    options.update(changes)
    return act('E2', passage, 'stent', kind_words, **options)


# the source's sibling (the reviewer's r_ge_later): the stent told 'Later, ...' - its time unanchored, possibly current
LATER = dict(GE, P4='Later, a 20 mm lumen-apposing metal stent was deployed from the gastric body into a distended '
                    'jejunal loop.')
# arm (b), constructed: the stent's status uncertain, its time given as another occasion's with no words (not verified:
# so neither possibly current nor verified another time)
UNCLEAR = dict(GE, P4='It is unclear whether a 20 mm lumen-apposing metal stent was deployed from the gastric body into '
                      'a distended jejunal loop.')
# arm (d), constructed: the stent named 'LAMS' by Gemini (kind words that do not locate: the kind not usable, so no D137
# act) beside a stent denial - an UNRESOLVED relation on it (scope_unresolved)
DENIED = dict(GE, P5='No stent was placed across the pylorus.')
# controls: the stent verified at another time, and the stent denied
EARLIER = dict(GE, P4='At her index EUS on 01/14/2024, a 20 mm lumen-apposing metal stent was deployed from the gastric '
                      'body into a distended jejunal loop.')
NO_STENT = dict(GE, P4='No lumen-apposing metal stent was placed.')


def denial() -> dict:
    return act('E3', 'P5', 'stent', 'stent', status='not_performed', status_words='No stent was placed',
               procedure=a('eus', 'EUS-guided', ['P1']), target=tg('', 'pylorus', 'the pylorus', ['P5']))


def later_case():
    return with_examination(LATER, stent(time=a('current_encounter', 'Later', ['P4'])))


def unclear_case():
    return with_examination(UNCLEAR, stent(status='uncertain', status_words='It is unclear whether',
                                           time=a('earlier_encounter')))


def related_case():
    return with_examination(DENIED, stent(kind_words='LAMS'), denial())


class AnUnlistedEusActInDoubtIsADoubt(SimpleTestCase):
    """D145 (1), problem 0 (critical): e5628be56 READYs 43259 on each of these inputs (alone and beside 43235); c2e53f8e
    holds it [performed_status, target]."""

    def test_d145_43259_beside_a_stent_whose_procedure_is_unsettled_is_held(self):
        inv, text = unsettled_stent()
        reading = events.Reading.of(inv)
        with self.subTest(part='fixture'):  # the review's: done, its procedure not usable (two current families)
            event = reading.events['E3']
            self.assertEqual((event['procedure']['state'], event['procedure']['reasons'], events.done(event),
                              coverage.eus_guided_act(event), coverage.eus_unprofiled_doubt(reading, event)),
                             ('unverified', ['procedure_unsettled'], True, False, True))
        for picks in ([('43259', EUS_Q)], [('43235', UPPER_Q), ('43259', EUS_Q)]):
            result = run(inv, text, picks)
            with self.subTest(codes=len(picks), part='assess'):  # e5628be56: READY
                base_held(self, result, '43259', (IN_DOUBT,))
            with self.subTest(codes=len(picks), part='record'):
                self.assertEqual((entries(result, 'reportable'), entries(result, 'doubted')),
                                 ([], [('E3', 'stent', STENT_PLACEMENT)]))
            with self.subTest(codes=len(picks), part='completeness'):
                self.assertEqual(result.completeness['state'], 'incomplete')

    def test_d145_the_same_stent_told_later_is_held(self):
        """The source's sibling: 'Later, ...' leaves the stent's time unverified - possibly current, not done."""
        inv, text = later_case()
        reading = events.Reading.of(inv)
        with self.subTest(part='fixture'):
            event = reading.events['E2']
            self.assertEqual((event['time']['state'], events.done(event), coverage.possibly_current(event),
                              events.usable(event, 'procedure')), ('unverified', False, True, True))
        result = run(inv, text, [('43259', GE['P2'])])
        with self.subTest(part='assess'):  # e5628be56: READY, complete_pending_review
            base_held(self, result, '43259', (IN_DOUBT,))
            self.assertEqual(result.completeness['state'], 'incomplete')
        with self.subTest(part='record'):
            self.assertEqual(entries(result, 'doubted'), [('E2', 'stent', STENT_PLACEMENT)])

    def test_d145_a_stent_whose_status_is_uncertain_is_held(self):
        """Arm (b), constructed: its status uncertain, its time neither possibly current nor verified another time."""
        inv, text = unclear_case()
        reading = events.Reading.of(inv)
        with self.subTest(part='fixture'):
            event = reading.events['E2']
            self.assertEqual((events.value(event, 'status'), coverage.possibly_current(event),
                              events.verified_other_time(event)), ('uncertain', False, False))
        result = run(inv, text, [('43259', GE['P2'])])
        with self.subTest(part='assess'):  # e5628be56: READY
            base_held(self, result, '43259', (IN_DOUBT,))

    def test_d145_a_stent_with_a_relation_on_it_is_held(self):
        """Arm (d), constructed: a done stent whose kind is not usable (no D137 act) with an UNRESOLVED relation on it."""
        inv, text = related_case()
        reading = events.Reading.of(inv)
        with self.subTest(part='fixture'):
            event = reading.events['E2']
            self.assertEqual((event['kind']['state'], events.done(event), coverage.eus_guided_act(event),
                              [(item['type'], item['statement']) for item in reading.relations_of('E2')]),
                             ('unverified', True, False, [('unresolved', 'E3')]))
        result = run(inv, text, [('43259', GE['P2'])])
        with self.subTest(part='assess'):  # e5628be56: READY
            base_held(self, result, '43259', (IN_DOUBT,))
        with self.subTest(part='record'):  # the denial is no doubt: not stated positive or uncertain
            self.assertEqual(entries(result, 'doubted'), [('E2', 'stent', STENT_PLACEMENT)])

    def test_d145_controls_another_occasion_a_denial_and_a_plain_fna(self):
        """Unchanged from e5628be56: a stent verified at another occasion and a denied stent are no doubt (43259 READY),
        and the plain FNA beside its examination leaves 43242 READY and 43259 held as before."""
        for name, lines, found in (
                ('another_occasion', EARLIER, stent(time=a('earlier_encounter', 'At her index EUS on 01/14/2024',
                                                           ['P4']))),
                ('denied', NO_STENT, stent(status='not_performed', status_words='No lumen-apposing metal stent was placed',
                                           target=tg()))):
            inv, text = with_examination(lines, found)
            reading = events.Reading.of(inv)
            with self.subTest(control=name, part='fixture'):
                self.assertFalse(coverage.eus_unprofiled_doubt(reading, reading.events['E2']))
            result = run(inv, text, [('43259', GE['P2'])])
            with self.subTest(control=name, part='assess'):
                ready_unheld(self, result, '43259')
                self.assertEqual((entries(result, 'reportable'), entries(result, 'doubted')), ([], []))
        lines = dict(GE, P1='Procedure: EUS with fine-needle aspiration.',
                     P4='EUS-guided fine-needle aspiration of the pancreatic head mass was performed with a 22-gauge '
                        'needle.')
        fna = act('E2', 'P4', 'fna', 'fine-needle aspiration', status_words='was performed',
                  procedure=a('eus', 'EUS-guided', ['P4']), technique=a('needle', '22-gauge needle', ['P4']),
                  target=tg('L1', 'pancreas', 'the pancreatic head mass', ['P4']))
        inv, text = with_examination(lines, fna)
        with self.subTest(control='fna'):
            ready_unheld(self, run(inv, text, [('43242', lines['P4'])]), '43242')
            result = run(inv, text, [('43242', lines['P4']), ('43259', lines['P2'])])
            self.assertEqual((proposal(result, '43259').status, asked(proposal(result, '43259'))),
                             ('needs_clarification', ['base_included']))
            self.assertEqual(entries(result, 'doubted'), [])


# --- (2) problem 4: an act begun and not completed is doubted, never reportable --------------------------------------

ATTEMPTED = dict(GE, P4=('Deployment of a 20 mm lumen-apposing metal stent from the gastric body into the jejunal loop '
                         'was attempted but failed.'))


def attempted_case():
    """The r5c D137 pin's input: the gastroenterostomy's stent 'attempted but failed' beside its EUS examination."""
    return with_examination(ATTEMPTED, stent(status='attempted_not_completed', status_words='was attempted but failed',
                                             target=tg('', 'jejunum', 'the jejunal loop', ['P4'])))


def service_rows(result) -> list:
    """(session, its acts) of the operator report's service rows, as readers.EventReader.services_section prints them."""
    assessment = SimpleNamespace(engine_version=ENGINE_VERSION, completeness=result.completeness)
    return [(row['id'], row['acts']) for row in readers.EventReader().services_section(assessment, result.completeness)]


class AnUnlistedEusActBegunIsNoPlacement(SimpleTestCase):
    """D145 (2), problem 4: e5628be56 records the attempted stent as reportable, so the report's EUS service row prints
    'stent placement'; 43259 is held either way (c2e53f8e: held)."""

    def test_d145_an_attempted_stent_is_doubted_never_reportable(self):
        inv, text = attempted_case()
        result = run(inv, text, [('43259', ATTEMPTED['P2'])])
        with self.subTest(part='record'):  # e5628be56: reportable [('E2', 'stent', 'stent placement')], doubted []
            self.assertEqual((entries(result, 'reportable'), entries(result, 'doubted')),
                             ([], [('E2', 'stent', STENT_PLACEMENT)]))
        with self.subTest(part='service_rows'):  # e5628be56: [('gi.eus', ['stent placement'])]
            self.assertEqual(service_rows(result), [('gi.eus', [])])
        with self.subTest(part='assess'):
            base_held(self, result, '43259', (IN_DOUBT,))

    def test_d145_control_a_performed_stent_stays_reportable(self):
        inv, text = with_examination(GE, stent())
        result = run(inv, text, [('43259', GE['P2'])])
        self.assertEqual((entries(result, 'reportable'), entries(result, 'doubted')),
                         ([('E2', 'stent', STENT_PLACEMENT)], []))
        self.assertEqual(service_rows(result), [('gi.eus', [STENT_PLACEMENT])])
        base_held(self, result, '43259', (STENT_PLACEMENT,))


# --- (3) problem 1: D136's hold asks the drainage's target ------------------------------------------------------------

DESCRIBES = '43240 describes the transmural drainage of a pancreatic fluid collection (a pseudocyst or walled-off necrosis)'
GB_QUESTION = ('Which structure was the drainage (“EUS-guided transmural drainage of the gallbladder was performed from '
               'the duodenal bulb with a 15 mm lumen-apposing metal stent.”) done on: a pancreatic fluid collection (a '
               'pseudocyst or walled-off necrosis), or another structure?')
GB_REASON = f'{DESCRIBES}; the document places this drainage at the gallbladder. Held for the reviewer, not excluded.'
R6_TARGET = 'Endoscopic ultrasound: confirm the structure examined.'
# the reviewer's r_gb_exam_mass: a malignant obstruction - the EUS examination of the pancreatic head mass (its target
# verified, L1) and an EUS-guided gallbladder drainage
GB_MASS = {'P1': 'Procedure: EUS with EUS-guided gallbladder drainage.',
           'P2': 'The linear echoendoscope was advanced to the second portion of the duodenum.',
           'P3': 'The pancreatic head mass causing the biliary obstruction was examined.',
           'P4': GB['P4']}


def gallbladder_beside_the_mass():
    found = [act('E1', 'P2', 'examination', 'linear echoendoscope', status_words='was advanced',
                 procedure=a('eus', 'EUS', ['P1']), technique=a('endoscope', 'linear echoendoscope', ['P2']),
                 target=tg('L1', 'pancreas', 'The pancreatic head mass', ['P3'])),
             act('E2', 'P4', 'drainage', 'transmural drainage', status_words='was performed',
                 procedure=a('eus', 'EUS-guided', ['P4']), technique=a('stent', 'lumen-apposing metal stent', ['P4']),
                 target=tg('', 'gallbladder', 'the gallbladder', ['P4']))]
    return inventory(GB_MASS, events=found, lesions=[MASS],
                     reach=[reached('E1', 'second_portion_duodenum', DUODENUM, 'P2')])


def target_held(test, result, facts: list, question: str, reason: str, why: str) -> None:
    """43240 is held with the target question first (fact 'target', ``question``, ``reason``), the drainage (E2) its one
    question event and supporting nothing, its support reason ``why``; the read-time overlay keeps it held."""
    p = proposal(result, '43240')
    first = p.clarifications[0]
    test.assertEqual((p.status, asked(p), p.support['reason']), ('needs_clarification', facts, why))
    test.assertEqual((first.fact, first.question, first.reason), ('target', question, reason))
    test.assertEqual((p.support['acts'], p.support['question_events']), ([], ['E2']))
    # never that CPT Studio could not confirm it was done (wording.status_reason's sentence): R3 verified it performed
    test.assertFalse([spec.reason for spec in p.clarifications
                      if spec.reason.startswith('CPT Studio could not confirm from the document that the ')])
    view = reviewed(result, '43240')
    test.assertEqual((view.status, view.released, [q['question'] for q in view.questions][:1]),
                     ('needs_clarification', (), [question]))


class TheDrainagesTargetIsAsked(SimpleTestCase):
    """D145 (3), problem 1 (high): e5628be56 holds 43240 [performed_status, target] (7.4's last resort - 'could not
    confirm ... that the drainage ... was done' - then R6's generic target), and [performed_status] alone beside an EUS
    examination whose own target is verified; c2e53f8e asks [performed_status, target] on every one."""

    def test_d145_43240_on_a_gallbladder_drainage_asks_its_target(self):
        """g1_gallbladder_43240: the examination names no target, so R6's structure examined is still asked after it."""
        inv, text = gallbladder()
        reading = events.Reading.of(inv)
        link = mapping.code_link('43240')
        with self.subTest(part='fixture'):  # the drainage passes R3; its defining target is read after it
            drainage = reading.events['E2']
            self.assertEqual((events.supports(reading, link, ('drainage',), drainage),
                              events.defining_fit(reading, link, drainage)), (True, False))
        result = run(inv, text, [('43240', GB['P4'])])
        with self.subTest(part='assess'):
            target_held(self, result, ['target', 'target'], GB_QUESTION, GB_REASON, events.ANOTHER_SITE)
            self.assertEqual(proposal(result, '43240').clarifications[1].question, R6_TARGET)
        with self.subTest(part='completeness'):
            self.assertEqual(result.completeness['state'], 'incomplete')

    def test_d145_asked_beside_an_examination_whose_own_target_is_verified(self):
        """The reviewer's r_gb_exam_mass, and the r5c pin's examination of the gallbladder itself: the structure examined
        is documented, and 43240 still asks the drainage's target (e5628be56: [performed_status] alone)."""
        for name, (inv, text) in (('the pancreatic head mass', gallbladder_beside_the_mass()),
                                  ('the gallbladder', gallbladder(tg('', 'gallbladder', 'the gallbladder', ['P3'])))):
            with self.subTest(examined=name):
                target_held(self, run(inv, text, [('43240', GB['P4'])]), ['target'], GB_QUESTION, GB_REASON,
                            events.ANOTHER_SITE)

    def test_d145_the_reason_says_where_the_document_places_the_drainage(self):
        for name, place in (('bile_duct', 'common bile duct'), ('hepatic_duct', 'bile duct'),
                            ('liver_abscess', 'liver')):
            inv, text = drainage_case(name)
            line = DRAINAGE_LINES[name]
            reason, question = wording.defining_target_hold('43240', 'drainage', place, line)
            with self.subTest(target=name):
                self.assertEqual(reason, f'{DESCRIBES}; the document places this drainage at the {place}. Held for the '
                                         'reviewer, not excluded.')
                target_held(self, run(inv, text, [('43240', line)]), ['target', 'target'], question, reason,
                            events.ANOTHER_SITE)

    def test_d145_a_drainage_whose_target_is_not_verified_asks_its_target(self):
        """'the walled-off necrosis' with no lesion, and D87's drainage naming no place (r3 integration): SITE, and the
        reason says CPT Studio could not confirm which structure it was done on."""
        inv, text = drainage_case('necrosis', with_lesion=False)
        line = DRAINAGE_LINES['necrosis']
        reason = (f'{DESCRIBES}; CPT Studio could not confirm from the document which structure this drainage was done '
                  'on. Held for the reviewer, not excluded.')
        question = ('Which structure was the drainage (“EUS-guided transmural drainage of the walled-off necrosis was '
                    'performed with a 20 mm lumen-apposing metal stent.”) done on: a pancreatic fluid collection (a '
                    'pseudocyst or walled-off necrosis), or another structure?')
        result = run(inv, text, [('43240', line)])
        target_held(self, result, ['target', 'target'], question, reason, events.SITE)
        self.assertEqual(check(proposal(result, '43240'), 'events.attributes').status, 'warn')

    def test_d145_controls_a_pancreatic_fluid_collection_still_supports_43240(self):
        """D27's recorded difference kept: the verified pseudocyst, walled-off necrosis and by-lesion drainages are READY,
        as at e5628be56 (c2e53f8e holds every 43240); beside a gallbladder drainage, the pseudocyst's alone supports it."""
        for name in ('pseudocyst', 'necrosis', 'by_lesion'):
            inv, text = drainage_case(name)
            with self.subTest(target=name):
                ready_unheld(self, run(inv, text, [('43240', DRAINAGE_LINES[name])]), '43240')
        lines = {'P1': 'The linear echoendoscope was advanced to the stomach.',
                 'P2': 'A 9 cm pancreatic pseudocyst was seen abutting the posterior gastric wall.',
                 'P3': DRAINAGE_LINES['pseudocyst'], 'P4': DRAINAGE_LINES['gallbladder']}
        found = [exam('E1', 'P1', words='linear echoendoscope', procedure=a('eus', 'echoendoscope', ['P1'])),
                 act('E2', 'P3', 'drainage', 'transmural drainage', status_words='was performed',
                     procedure=a('eus', 'EUS-guided', ['P3']), technique=a('stent', 'stent', ['P3']),
                     target=tg('L1', 'pancreas', 'the pseudocyst', ['P3'])),
                 act('E3', 'P4', 'drainage', 'transmural drainage', status_words='was performed',
                     procedure=a('eus', 'EUS-guided', ['P4']), technique=a('stent', 'stent', ['P4']),
                     target=tg('', 'gallbladder', 'the gallbladder', ['P4']))]
        pseudocyst = les('L1', 'A 9 cm pancreatic pseudocyst', 'P2', landmark='pancreas', site_words='pancreatic',
                         size_words='9 cm')
        inv, text = inventory(lines, events=found, lesions=[pseudocyst],
                              reach=[reached('E1', 'stomach', 'stomach', 'P1')])
        with self.subTest(target='the pseudocyst beside the gallbladder'):
            p = proposal(run(inv, text, [('43240', DRAINAGE_LINES['pseudocyst'])]), '43240')
            self.assertEqual((p.status, asked(p), [item['id'] for item in p.support['acts']]), ('ready', [], ['E2']))

    def test_d145_every_other_code_meets_its_target(self):
        """defining_fit is True for every code but 43240, so the hold reads no other code."""
        inv, _ = gallbladder()
        reading = events.Reading.of(inv)
        for code in ('43242', '43253', '43259', '43235', '43237', '43238'):
            with self.subTest(code=code):
                self.assertTrue(events.defining_fit(reading, mapping.code_link(code), reading.events['E2']))


# --- (4) problem 5: a fiducial placement read as a tattoo is named by its own words ----------------------------------

FIDUCIAL = {'P1': 'Procedure: EUS with fiducial placement.',
            'P2': 'The linear echoendoscope was advanced to the second portion of the duodenum.',
            'P3': 'The pancreatic head mass was examined.',
            'P4': 'EUS-guided placement of three gold fiducial markers into the pancreatic head mass was performed.'}
FIDUCIALS = 'placement of three gold fiducial markers'


def fiducial_case():
    """The reviewer's r_fiducial_exam: the EUS examination of the pancreatic head mass (E1) and the fiducial placement read
    as 'tattoo' (prompt.py KINDS: 'tattoo: an injection that marks a site')."""
    found = [act('E1', 'P2', 'examination', 'linear echoendoscope', status_words='was advanced',
                 procedure=a('eus', 'EUS', ['P1']), technique=a('endoscope', 'linear echoendoscope', ['P2']),
                 target=tg('L1', 'pancreas', 'The pancreatic head mass', ['P3'])),
             act('E2', 'P4', 'tattoo', FIDUCIALS, status_words='was performed', procedure=a('eus', 'EUS-guided', ['P4']),
                 target=tg('L1', 'pancreas', 'the pancreatic head mass', ['P4']))]
    return inventory(FIDUCIAL, events=found, lesions=[MASS],
                     reach=[reached('E1', 'second_portion_duodenum', DUODENUM, 'P2')])


class AFiducialPlacementIsNamedByItsOwnWords(SimpleTestCase):
    """D145 (4), problem 5: e5628be56 records the act as 'submucosal tattoo' and asks 'Is 43259 reported separately from
    submucosal tattoo for this examination?'; c2e53f8e holds 43259 and 43253 [performed_status, target]."""

    def test_d145_the_base_question_names_the_fiducial_placement(self):
        inv, text = fiducial_case()
        result = run(inv, text, [('43259', FIDUCIAL['P2'])])
        with self.subTest(part='assess'):
            base_held(self, result, '43259', (FIDUCIALS,))
            self.assertEqual(proposal(result, '43259').clarifications[0].question, base_question('43259', FIDUCIALS))
        with self.subTest(part='record'):
            self.assertEqual(entries(result, 'reportable'), [('E2', 'tattoo', FIDUCIALS)])

    def test_d145_43253_stays_ready_and_43259_held_beside_it(self):
        inv, text = fiducial_case()
        with self.subTest(codes='43253'):
            ready_unheld(self, run(inv, text, [('43253', FIDUCIAL['P4'])]), '43253')
        result = run(inv, text, [('43253', FIDUCIAL['P4']), ('43259', FIDUCIAL['P2'])])
        with self.subTest(codes='43253+43259'):
            ready_unheld(self, result, '43253')
            base_held(self, result, '43259', ('43253',))

    def test_d145_control_any_other_act_keeps_its_label(self):
        """An act of a kind no EUS code accounts for keeps D137's label: its catalogue label, else its own kind words."""
        for found, lines, label in ((stent(), GE, STENT_PLACEMENT),
                                    (act('E2', 'P4', 'other', 'coil embolization', status_words='was performed',
                                         procedure=a('eus', 'EUS-guided', ['P4']),
                                         target=tg('', 'gastric_fundus', 'the gastric fundal varix', ['P4'])),
                                     dict(GE, P4='EUS-guided coil embolization of the gastric fundal varix was '
                                                 'performed.'), 'coil embolization')):
            inv, text = with_examination(lines, found)
            with self.subTest(label=label):
                self.assertEqual([item['label'] for item in coverage.eus_unprofiled_entries(
                    events.Reading.of(inv), list(events.Reading.of(inv).events.values()))], [label])
