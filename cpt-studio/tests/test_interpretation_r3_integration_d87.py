"""DECISIONS D87 (the integration of round 3, 732d172d2): a possible examination is a doubt, never a fact. Regression
pins built from the reviewers' own inputs, SYNTHETIC: every input is a synthetic Gemini answer over a synthetic
document, read by read.read and normalized with the real linked steps, then assessed through assess.assess with a
synthetic Corti response whose spans are the document's own (the S08 builders of test_interpretation_events). Nothing is
sent.

D87: Session.examinations holds the DONE examinations only; D62's possible ones are Session.possible (``unresolved`` and
``event`` still count both, as D62 decided). relations' unresolved sessions count VERIFIED current examinations again; a
possibly current one leaves the session unresolved in coverage.sessions alone, which holds every code of it. A session
left unresolved only by possible examinations keeps the C3/C-4 structure of its one done examination.

- The review of D68 (currency), problem 1: an EUS whose today's examination names no target, beside an examination
  Gemini calls current_encounter while its own words place it elsewhere ("Previously, the linear echoendoscope showed a
  2.5 cm hypoechoic mass in the pancreatic head."). assess._inventory_fact read Session.examinations and took 'structure
  examined = pancreas' from it: 43253 (fiducials) and 43240 (drainage) were READY. They ask the target.
- The same review, problem 2: an ERCP with 'At the original ERCP, the duodenoscope was advanced to the major papilla.'
  beside 'No stent was placed.' and the stent placement. relations counted the possible examination, so the pairing was
  session_unresolved and 43274 never asked conflict:stent; in the colonoscopy analogue 45385 beside 'No polyp was
  removed.' never asked conflict:snare. Both ask the contradiction.
- The D68 author's disagreement 4: EGD + upper EUS + FNA plus an EGD examination worded 'Previously' or 'On 01/14/2024'.
  The EGD session, unresolved, lost C-4's part_of, and 43235 asked its extent instead of base_included. It asks
  base_included. The same disagreement's 'same mechanism' (events.broad reads relations' unresolved sessions): 45385
  citing a scar beside 'No polyp was removed today.' asked performed_status instead of statement_scope. It asks the
  statement's scope again.

Each pin also asserts its input's shape (the aside examination is unverified, current_encounter, and possible), so it
cannot pass on an input that no longer reaches the path it guards."""
from __future__ import annotations

from django.test import SimpleTestCase

from studio.interpretation import coverage, events, overlay, relations
from tests.test_interpretation_events import (COLONOSCOPE, L1, POLYP, asked, check, exam, inventory, proposal, reached,
                                              removed, run)
from tests.test_interpretation_identity import a, act, sc, tg


def session_shape(reading, family: str) -> tuple:
    """(event, unresolved, examinations, possible, part_of, possibly_part_of) of ``family``'s session."""
    s = coverage.sessions(reading)[family]
    return s.event, s.unresolved, s.examinations, s.possible, s.part_of, s.possibly_part_of


def question_of(p, fact: str) -> str:
    found = [spec.question for spec in p.clarifications if spec.fact == fact]
    return found[0] if len(found) == 1 else f'{len(found)} questions of {fact}'


class Possible(SimpleTestCase):
    def assert_possible(self, reading, eid: str, reasons) -> None:
        """The aside examination ``eid`` is a D62 possible examination: current_encounter and unverified for
        ``reasons``, positive, not done - so its session is unresolved and it is never the session."""
        event = reading.events[eid]
        self.assertEqual((events.value(event, 'time'), event['time']['state'], event['time']['reasons'],
                          event['current'], events.done(event), coverage.possibly_current(event)),
                         ('current_encounter', 'unverified', reasons, 'unresolved', False, True), eid)


# --- the currency review, problem 1: a possible examination is never a FACT source (assess._inventory_fact) ----------

EUS_TODAY = 'A linear echoendoscope was advanced to the duodenum.'
FIDUCIALS = 'Three gold fiducial markers were placed under EUS guidance.'
DRAINAGE = 'A transmural drainage was performed under EUS guidance.'
# the reviewer's words and the time reasons each gives E2 (probe.py p1, probe_p1_variants.py)
ASIDE_WORDS = (('Previously', ['other_occasion']), ('At the original procedure', ['other_occasion']),
               ('On 01/14/2024', ['date_mismatch']), ('In 2024', ['date_mismatch', 'current_unanchored']),
               ('At the index procedure', ['current_unanchored']), ('Next', ['other_occasion']))


def eus_beside_an_aside(words: str, kind: str = 'injection') -> tuple:
    """(inventory, text, the act's line) of problem 1: today's EUS examination naming no target (E1, P1), the aside
    examination naming the pancreatic head whose time Gemini gives as current_encounter with ``words`` (E2, P2), and the
    fiducial placement (``kind`` 'injection') or the transmural drainage ('drainage'), naming no place (E3, P3)."""
    line = FIDUCIALS if kind == 'injection' else DRAINAGE
    lines = {'P1': EUS_TODAY,
             'P2': f'{words}, the linear echoendoscope showed a 2.5 cm hypoechoic mass in the pancreatic head.',
             'P3': line}
    today = exam('E1', 'P1', words='echoendoscope', procedure=a('eus'))
    aside = exam('E2', 'P2', words='linear echoendoscope', status_words='showed', procedure=a('eus'),
                 target=tg('', 'pancreas', 'pancreatic head', ['P2']), time=a('current_encounter', words, ['P2']))
    if kind == 'injection':
        procedure_act = act('E3', 'P3', 'injection', 'fiducial markers', status_words='were placed', procedure=a('eus'))
    else:
        procedure_act = act('E3', 'P3', 'drainage', 'transmural drainage', status_words='was performed',
                            procedure=a('eus'))
    inv, text = inventory(lines, events=[today, aside, procedure_act])
    return inv, text, line


class D87PossibleExaminationIsNoFactSource(Possible):
    """Problem 1 of the review of D68 (HIGH, a new wrong READY at 62d5bf0dd): the target fact reads the session's DONE
    examinations and the code's supporting events, never an examination that may be another occasion's."""

    def held_on_its_target(self, code: str, kind: str) -> None:
        for words, reasons in ASIDE_WORDS:
            inv, text, line = eus_beside_an_aside(words, kind)
            reading = events.Reading.of(inv)
            with self.subTest(code=code, words=words):
                self.assert_possible(reading, 'E2', reasons)  # the input reaches the path
                result = run(inv, text, [(code, line)])
                p = proposal(result, code)  # the outcome first, then the structure that gives it
                self.assertEqual((p.status, asked(p), p.support['reason']),
                                 ('needs_clarification', ['target'], events.SUPPORTED))
                self.assertEqual(question_of(p, 'target'), 'Endoscopic ultrasound: confirm the structure examined.')
                self.assertEqual(check(p, 'facts.required').detail, 'Not documented: structure examined.')
                self.assertEqual(result.completeness['state'], 'incomplete')
                self.assertEqual(session_shape(reading, 'gi.eus'), ('', True, ('E1',), ('E2',), '', ''))
                # the stored record lists the possible examination apart from the done one (event_coding, D87)
                stored = overlay.read_coding(result.completeness)['sessions']['gi.eus']
                self.assertEqual((stored['examinations'], stored['possible'], stored['unresolved']),
                                 (['E1'], ['E2'], True))

    def test_d87_43253_beside_a_possible_examination_naming_the_pancreas_asks_the_structure_examined(self):
        self.held_on_its_target('43253', 'injection')

    def test_d87_43240_beside_a_possible_examination_naming_the_pancreas_asks_the_structure_examined(self):
        self.held_on_its_target('43240', 'drainage')


# --- the currency review, problem 2: the pairing reads VERIFIED current examinations (relations.Context) --------------

ERCP_TODAY = 'The duodenoscope was advanced to the major papilla.'
CANNULATION = 'Deep biliary cannulation was achieved with a sphincterotome and a guidewire.'
STENT = 'A 10 Fr by 7 cm plastic biliary stent was placed in the common bile duct.'
NO_STENT = 'No stent was placed.'
ERCP_ASIDES = (('At the original ERCP', ['other_occasion']), ('Previously', ['other_occasion']),
               ('On 01/14/2024', ['date_mismatch']))


def ercp_beside_an_aside(words: str) -> tuple:
    """(inventory, text) of problem 2 (probe.py p4): today's ERCP examination (E1), the biliary cannulation (E2), the
    plastic biliary stent placement (E3), an examination Gemini calls current_encounter with ``words`` (E4) and the
    broad current denial 'No stent was placed.' (E5, all_of_kind)."""
    lines = {'P1': ERCP_TODAY, 'P2': CANNULATION, 'P3': STENT,
             'P4': f'{words}, the duodenoscope was advanced to the major papilla.', 'P5': NO_STENT}
    ercp = exam('E1', 'P1', words='duodenoscope', procedure=a('ercp'))
    cannulation = act('E2', 'P2', 'cannulation', 'cannulation', status_words='was achieved', procedure=a('ercp'),
                      target=tg('', 'bile_duct', 'biliary', ['P2']))
    stent = act('E3', 'P3', 'stent', 'stent', status_words='was placed', procedure=a('ercp'),
                technique=a('stent', 'plastic biliary stent', ['P3']),
                target=tg('', 'common_bile_duct', 'common bile duct', ['P3']))
    aside = exam('E4', 'P4', words='duodenoscope', procedure=a('ercp'), time=a('current_encounter', words, ['P4']))
    denial = act('E5', 'P5', 'stent', 'stent', status='not_performed', status_words='No stent was placed',
                 procedure=a('ercp'), scope=sc('all_of_kind', 'No', ['P5']))
    return inventory(lines, events=[ercp, cannulation, stent, aside, denial])


def colonoscopy_beside_an_aside(words: str) -> tuple:
    """(inventory, text) of problem 2's colonoscopy analogue (probe_p4b.py): today's colonoscopy to the cecum (E1), the
    cold snare removal of L1 (E2), an examination Gemini calls current_encounter with ``words`` (E3) and 'No polyp was
    removed.' (E4, not_performed, all_of_kind)."""
    lines = {'P1': COLONOSCOPE, 'P2': POLYP, 'P3': f'{words}, the colonoscope was advanced to the cecum.',
             'P4': 'No polyp was removed.'}
    aside = exam('E3', 'P3', time=a('current_encounter', words, ['P3']))
    denial = act('E4', 'P4', 'snare', 'removed', status='not_performed', status_words='No polyp was removed',
                 scope=sc('all_of_kind', 'No', ['P4']))
    return inventory(lines, events=[exam(), removed(), aside, denial], lesions=[L1], reach=[reached()])


def pairings(inv) -> list:
    return [(item['type'], item['statement'], item['event'], item['attribute'], item['reason'])
            for item in inv.events['relations']]


class D87PairingCountsVerifiedExaminations(Possible):
    """Problem 2 of the review of D68 (MEDIUM, a dropped contradiction question at 62d5bf0dd): a possible examination
    leaves the session unresolved in coverage (every code of it held), never in the pairing table - a doubt never takes
    another doubt's question, so the denial beside the act is a CONTRADICTION, asked as one."""

    def test_d87_no_stent_was_placed_beside_the_stent_placement_asks_conflict_stent(self):
        for words, reasons in ERCP_ASIDES:
            inv, text = ercp_beside_an_aside(words)
            reading = events.Reading.of(inv)
            with self.subTest(words=words):
                self.assert_possible(reading, 'E4', reasons)  # the input reaches the path
                p = proposal(run(inv, text, [('43274', STENT)]), '43274')  # the outcome first
                self.assertEqual((p.status, asked(p), p.support['reason']),
                                 ('needs_clarification', ['conflict:stent'], events.CONFLICT))
                self.assertEqual(question_of(p, 'conflict:stent'),
                                 'The record states the stent placement both as performed and as not performed. '
                                 'Which is correct for this encounter?')
                self.assertEqual(pairings(inv), [(relations.CONTRADICTION, 'E5', 'E3', 'status', 'same_act')])
                self.assertEqual(reading.context.unresolved_sessions, frozenset())
                # coverage still holds every code of the session: unresolved, the possible examination apart
                self.assertEqual(session_shape(reading, 'gi.ercp'), ('', True, ('E1',), ('E4',), '', ''))

    def test_d87_no_polyp_was_removed_beside_the_snare_removal_asks_conflict_snare(self):
        for words, reasons in ERCP_ASIDES[1:]:
            inv, text = colonoscopy_beside_an_aside(words)
            reading = events.Reading.of(inv)
            with self.subTest(words=words):
                self.assert_possible(reading, 'E3', reasons)  # the input reaches the path
                p = proposal(run(inv, text, [('45385', POLYP)]), '45385')  # the outcome first
                # the extent: the session stays unresolved in coverage (D62), so no one examination's reach is read
                self.assertEqual((p.status, asked(p), p.support['reason']),
                                 ('needs_clarification', ['conflict:snare', 'extent'], events.CONFLICT))
                self.assertEqual(question_of(p, 'conflict:snare'),
                                 'The record states the snare removal both as performed and as not performed. '
                                 'Which is correct for this encounter?')
                self.assertEqual(pairings(inv), [(relations.CONTRADICTION, 'E4', 'E2', 'status', 'same_act')])
                self.assertEqual(reading.context.unresolved_sessions, frozenset())
                self.assertEqual(session_shape(reading, 'gi.colonoscopy'), ('', True, ('E1',), ('E3',), '', ''))

    def test_d87_control_two_verified_examinations_still_leave_the_pairing_unresolved(self):
        # the decision's boundary, on the same two documents: a second examination whose current time IS verified
        # ("During this procedure") is a done examination, and a session holding two leaves the pairing unresolved
        # (FINAL 7.8; relations' all_of_kind row) - only the POSSIBLE one stopped counting. The question the unresolved
        # pairing asks is D91's, not pinned here; the code is held either way.
        for build, family, code, cited, pairing in (
                (ercp_beside_an_aside, 'gi.ercp', '43274', STENT, ('E5', 'E3')),
                (colonoscopy_beside_an_aside, 'gi.colonoscopy', '45385', POLYP, ('E4', 'E2'))):
            inv, text = build('During this procedure')
            reading = events.Reading.of(inv)
            aside = 'E4' if family == 'gi.ercp' else 'E3'
            with self.subTest(family=family):
                self.assertEqual((reading.events[aside]['time']['state'], reading.events[aside]['current'],
                                  events.done(reading.events[aside])), ('verified', 'yes', True))
                p = proposal(run(inv, text, [(code, cited)]), code)
                self.assertEqual((p.status, p.support['reason']), ('needs_clarification', events.UNRESOLVED))
                self.assertEqual(pairings(inv), [(relations.UNRESOLVED, *pairing, 'procedure', 'session_unresolved')])
                self.assertEqual(reading.context.unresolved_sessions, frozenset({family}))
                self.assertEqual(session_shape(reading, family), ('', True, ('E1', aside), (), '', ''))


# --- the D68 author's disagreement 4: the structure of the session's one done examination (C3, C-4) ------------------

EGD = 'EGD: the gastroscope was advanced to the second portion of the duodenum.'
EUS = 'The linear echoendoscope was introduced and advanced to the second portion of the duodenum.'
FNA = 'A 2.5 cm hypoechoic mass in the pancreatic head was sampled with a 22-gauge needle, three passes.'
BASE_INCLUDED = 'Is 43235 reported separately from 43242 for this examination?'


def egd_within_an_upper_eus(words: str = '') -> tuple:
    """(inventory, text) of the D68 author's disagreement 4 (probes/eus_mislabelled.py): today's EGD (E1) and upper EUS
    (E2), both reaching the second portion of the duodenum, the FNA of the pancreatic head (E3), and - with ``words`` -
    an EGD examination Gemini calls current_encounter with them (E4: '<words>, an EGD with the gastroscope was performed
    elsewhere and was normal.')."""
    lines = {'P1': EGD, 'P2': EUS, 'P3': FNA}
    egd = exam('E1', 'P1', words='gastroscope', procedure=a('egd', 'gastroscope', ['P1']))
    eus = exam('E2', 'P2', words='linear echoendoscope', status_words='was introduced and advanced',
               procedure=a('eus', 'linear echoendoscope', ['P2']))
    fna = act('E3', 'P3', 'fna', 'sampled', status_words='was sampled with a 22-gauge needle',
              procedure=a('eus', 'needle', ['P3']), technique=a('needle', '22-gauge needle', ['P3']),
              target=tg('', 'pancreas', 'pancreatic head', ['P3']))
    more = []
    if words:
        lines['P4'] = f'{words}, an EGD with the gastroscope was performed elsewhere and was normal.'
        more = [exam('E4', 'P4', words='gastroscope', status_words='was performed elsewhere',
                     procedure=a('egd', 'EGD', ['P4']), time=a('current_encounter', words, ['P4']))]
    return inventory(lines, events=[egd, eus, fna, *more],
                     reach=[reached('E1', 'second_portion_duodenum', 'second portion of the duodenum', 'P1'),
                            reached('E2', 'second_portion_duodenum', 'second portion of the duodenum', 'P2')])


class D87SessionKeepsItsDoneExaminationsStructure(Possible):
    """The D68 author's disagreement 4: a session left unresolved only by POSSIBLE examinations keeps the C3/C-4
    structure of its one done examination - an aside EGD beside today's EGD within an upper EUS leaves the EGD the
    EUS's endoscopic portion, and 43235 asks base_included (as a4dcbea72 and the installed release do), never only its
    extent."""

    def test_d87_an_aside_egd_beside_todays_egd_within_an_upper_eus_asks_base_included(self):
        inv, text = egd_within_an_upper_eus()  # the reference: no aside
        reading = events.Reading.of(inv)
        self.assertEqual(session_shape(reading, 'gi.egd'), ('E1', False, ('E1',), (), 'gi.eus', ''))
        p = proposal(run(inv, text, [('43235', EGD), ('43242', FNA)]), '43235')
        self.assertEqual((p.status, asked(p)), ('needs_clarification', ['base_included']))
        for words, reasons in (('Previously', ['other_occasion']), ('On 01/14/2024', ['date_mismatch'])):
            inv, text = egd_within_an_upper_eus(words)
            reading = events.Reading.of(inv)
            with self.subTest(words=words):
                self.assert_possible(reading, 'E4', reasons)  # the input reaches the path
                p = proposal(run(inv, text, [('43235', EGD), ('43242', FNA)]), '43235')  # the outcome first
                # the extent too: the EGD session stays unresolved (D62), so no one examination's reach is read
                self.assertEqual((p.status, asked(p), p.support['reason']),
                                 ('needs_clarification', ['base_included', 'extent'], events.SUPPORTED))
                self.assertEqual(question_of(p, 'base_included'), BASE_INCLUDED)
                self.assertEqual(session_shape(reading, 'gi.egd'), ('', True, ('E1',), ('E4',), 'gi.eus', ''))
                self.assertEqual(session_shape(reading, 'gi.eus'), ('E2', False, ('E2',), (), '', ''))


# --- the same disagreement's 'same mechanism': events.broad reads relations' unresolved sessions ----------------------

SCAR = 'Cold forceps biopsies were taken from the transverse colon polypectomy scar.'
DENIAL_TODAY = 'No polyp was removed today.'


def scar_beside_a_broad_denial(aside: str) -> tuple:
    """(inventory, text) of the D68 author's broad-denial shape (probes/broad_denial.py): today's colonoscopy to the
    cecum (E1), cold forceps biopsies of the polypectomy scar (E2), 'No polyp was removed today.' (E3, all_of_kind,
    current) and the aside examination line ``aside`` Gemini calls current_encounter with its words before the comma
    (E4)."""
    lines = {'P1': COLONOSCOPE, 'P2': SCAR, 'P3': DENIAL_TODAY, 'P4': aside}
    biopsy = act('E2', 'P2', 'biopsy', 'biopsies', status_words='were taken',
                 technique=a('cold_forceps', 'Cold forceps', ['P2']),
                 target=tg('', 'transverse_colon', 'transverse colon polypectomy scar', ['P2']))
    denial = act('E3', 'P3', 'snare', 'polyp was removed', status='not_performed', status_words='No polyp was removed',
                 scope=sc('all_of_kind', 'No', ['P3']), time=a('current_encounter', 'today', ['P3']))
    aside_exam = exam('E4', 'P4', time=a('current_encounter', aside.split(',')[0], ['P4']))
    return inventory(lines, events=[exam(), biopsy, denial, aside_exam], reach=[reached()])


class D87BroadDenialBesideAPossibleExamination(Possible):
    """The broad statement (C-7/C-8, events.broad) skips a session relations reads as unresolved. Counting a possible
    examination there, 45385 citing the scar beside 'No polyp was removed today.' asked performed_status where the
    statement's own scope is the question; it asks statement_scope again, and 45380 stays held (the session is
    unresolved in coverage, D62), never READY."""

    def test_d87_a_broad_denial_beside_a_possible_examination_asks_its_scope(self):
        for aside, reasons in (('Previously, the colonoscope was advanced to the cecum.', ['other_occasion']),
                               ('On 01/14/2024, the colonoscope was advanced to the cecum.', ['date_mismatch'])):
            inv, text = scar_beside_a_broad_denial(aside)
            reading = events.Reading.of(inv)
            with self.subTest(aside=aside):
                self.assert_possible(reading, 'E4', reasons)  # the input reaches the path
                result = run(inv, text, [('45385', SCAR), ('45380', SCAR)])
                p = proposal(result, '45385')  # the outcome first
                self.assertEqual((p.status, asked(p), p.support['reason']),
                                 ('needs_clarification', ['statement_scope', 'extent'], events.STATEMENT_SCOPE))
                self.assertTrue(question_of(p, 'statement_scope').startswith(
                    'Does “No polyp was removed” apply to the snare removal'), question_of(p, 'statement_scope'))
                biopsy = proposal(result, '45380')
                self.assertEqual((biopsy.status, asked(biopsy)), ('needs_clarification', ['extent']))
                self.assertTrue(events.broad(reading, reading.events['E3']))
                self.assertEqual(reading.context.unresolved_sessions, frozenset())
                self.assertEqual(session_shape(reading, 'gi.colonoscopy'), ('', True, ('E1',), ('E4',), '', ''))
