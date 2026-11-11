"""Round 3 of the Gemini migration's refutation, the claims and the base code (DECISIONS D74 and D75), SYNTHETIC and
REPLAYED: nothing is sent.

- D74 (round-3 finding 5): a code D27 narrows (CodeLink.defining) claims the current performed acts of the kinds its
  covers name beside its defining kinds whenever its family has an event of a defining kind stated positive and
  possibly current, in ANY verification state - not only when the code is matched. A lithotripsy whose time is only
  unanchored, or whose status words do not bind, is a doubt about 43265, never an absence of it: 43264 and 43265
  proposed for one stone clearance both stay held with competing_codes, as the installed release holds them. A narrowed
  code with no positive defining event (not documented) still claims nothing.
- D75 (round-3 finding 17): an act stated positive and possibly current whose PROCEDURE is not usable (unverified or
  opened) counts as doubted in its family's session when that family has a current session (a done examination), so
  combination.base_included holds the diagnostic base code beside it: 43235 is never READY beside the four EGD biopsies
  whose procedure Gemini cited as the 3-character heading 'EGD' (finding 17's committed recordings).
"""
from __future__ import annotations

import copy
from types import SimpleNamespace

from django.test import SimpleTestCase

from studio.interpretation import adapter, assess, coverage, events, facts, normalize
from studio.interpretation import read as interpretation_read
from studio.types import EvidenceSpan, ParticipantInput, ParticipantReading
from tests.test_interpretation_events import (LOOKUP, asked, check, exam, inventory, proposal, reached, response,
                                              run)
from tests.test_interpretation_identity import a, act, tg
from tests.test_interpretation_replay import FIXTURES, MANIFEST, text_and_pages

# --- D74: one stone clearance (finding 5's own document) -----------------------------------------------------------------

STONE = {'P1': 'Procedure: The duodenoscope was advanced to the major papilla.',
         'P2': 'Deep biliary cannulation was achieved with a sphincterotome and a guidewire.',
         'P3': 'A 15 mm stone in the common bile duct was fragmented with mechanical lithotripsy.',
         'P4': 'The stone fragments were extracted from the bile duct with an extraction balloon.'}
READ_NOTHING = tuple(ParticipantInput(name, 'read', ParticipantReading(
    provider=name, adapter_version=f'{name}@test', reading_version='harness-reading@2', requested_model='model',
    returned_model='model', codes=(), not_coded=())) for name in ('astra', 'fable'))


def stone_clearance(p3: str = STONE['P3'], *, status: str = 'performed', status_words: str = 'was fragmented',
                    procedure=None, **changes):
    """Finding 5's ERCP: the duodenoscope (E1), the biliary cannulation (E2), the mechanical lithotripsy of the 15 mm
    stone (E3, ``changes`` applied) and the balloon extraction of its fragments (E4); (inventory, text, lines)."""
    lines = dict(STONE, P3=p3)
    lithotripsy = act('E3', 'P3', 'lithotripsy', 'lithotripsy', status=status, status_words=status_words,
                      procedure=procedure or a('ercp'), target=tg('', 'common_bile_duct', 'common bile duct', ['P3']),
                      technique=a('lithotripter', 'lithotripsy', ['P3']), **changes)
    inv, text = inventory(lines, events=[
        exam('E1', 'P1', words='duodenoscope', procedure=a('ercp')),
        act('E2', 'P2', 'cannulation', 'cannulation', status_words='was achieved', procedure=a('ercp'),
            target=tg('', 'bile_duct', 'biliary', ['P2']), technique=a('sphincterotome', 'sphincterotome', ['P2'])),
        lithotripsy,
        act('E4', 'P4', 'stone_extraction', 'extracted', status_words='were extracted', procedure=a('ercp'),
            target=tg('', 'bile_duct', 'bile duct', ['P4']),
            technique=a('extraction_balloon', 'extraction balloon', ['P4']))])
    return inv, text, lines


# Finding 5's three texts: the lithotripsy's time worded and unanchored (D54: current_unanchored), twice, and its status
# words not binding ('was broken up' is not in its passage); each with the fact the held 43265 asks of its own act.
DOUBTED = {
    'During the procedure': (dict(p3='During the procedure, a 15 mm stone in the common bile duct was fragmented with '
                                     'mechanical lithotripsy.',
                                  time=a('current_encounter', 'During the procedure', ['P3'])), 'event_time'),
    'After biliary sphincterotomy': (dict(p3='After biliary sphincterotomy, a 15 mm stone in the common bile duct was '
                                             'fragmented with mechanical lithotripsy.',
                                          time=a('current_encounter', 'After biliary sphincterotomy', ['P3'])),
                                     'event_time'),
    'status words that do not bind': (dict(status_words='was broken up'), 'performed_status'),
}


def held_both(test, result, own_fact):
    """43264 held asking competing_codes only, 43265 held asking its own act's question and competing_codes."""
    extraction, lithotripsy = proposal(result, '43264'), proposal(result, '43265')
    test.assertEqual((extraction.status, asked(extraction), extraction.support.get('competes')),
                     ('needs_clarification', ['competing_codes'], ['43265']))
    test.assertEqual((lithotripsy.status, asked(lithotripsy), lithotripsy.support.get('competes')),
                     ('needs_clarification', [own_fact, 'competing_codes'], ['43264']))
    test.assertEqual(check(extraction, 'proposals.competing').status, 'warn')
    test.assertEqual([item['id'] for item in extraction.support['acts']], ['E4'])  # E* unchanged: claims are not acts
    test.assertEqual(lithotripsy.support['acts'], [])


def claims(inv, text: str, code: str, line: str) -> tuple:
    """assess._claims of ``code`` evaluated from the exact span of ``line``."""
    reading = events.Reading.of(inv)
    start = text.index(line)
    kept = (EvidenceSpan(0, start, start + len(line), line, True),)
    return assess._claims(SimpleNamespace(evaluation=events.evaluate(code, kept, reading)), reading)


class D74DoubtedDefiningAct(SimpleTestCase):
    def test_d74_finding_5_a_doubted_lithotripsy_still_competes_for_the_stone_clearance(self):
        """Finding 5's three texts, with no participant and with Astra and Fable read and proposing nothing (the
        production configuration): the installed release holds both codes with competing_codes; so does this engine,
        and 43265 keeps the question its own doubted act asks."""
        for name, (options, own_fact) in DOUBTED.items():
            inv, text, lines = stone_clearance(**options)
            lithotripsy = events.Reading.of(inv).events['E3']
            self.assertNotEqual(lithotripsy['time' if own_fact == 'event_time' else 'status']['state'], 'verified')
            for participants in ((), READ_NOTHING):
                with self.subTest(text=name, participants=len(participants)):
                    result = run(inv, text, [('43264', lines['P4']), ('43265', lines['P3'])],
                                 participants=participants)
                    held_both(self, result, own_fact)

    def test_d74_claims_read_a_positive_possibly_current_defining_act_in_any_verification_state(self):
        """The held 43265's claims: the extraction (E4) whenever its family's lithotripsy is stated positive and
        possibly current - its time unanchored, its status words unbound, its status attempted - and nothing when the
        lithotripsy is denied, planned, verified at an earlier encounter or stated in another family. A time worded with
        another occasion's marker follows coverage.possibly_current, whatever D62's carve-out decides (today: evidence,
        not a doubt, so nothing is claimed). DECISIONS D163 (round 5f): the held 43265 also claims its own doubted
        lithotripsy (E3), as a held code keeps the acts its evaluation read; no rival claims E3, so no outcome moves."""
        claimed = {
            'time unanchored': stone_clearance(**DOUBTED['During the procedure'][0]),
            'status words unbound': stone_clearance(**DOUBTED['status words that do not bind'][0]),
            'attempted, not completed': stone_clearance(
                'Mechanical lithotripsy of a 15 mm stone in the common bile duct was attempted and abandoned.',
                status='attempted_not_completed', status_words='was attempted and abandoned'),
        }
        for name, (inv, text, lines) in claimed.items():
            with self.subTest(claimed=name):
                self.assertEqual(events.evaluate('43265', (), events.Reading.of(inv)).supporting, ())
                self.assertEqual(claims(inv, text, '43265', lines['P3']), ('E4', 'E3'))  # D163: E3 too
        unclaimed = {
            'denied': stone_clearance('No lithotripsy was performed for the 15 mm stone in the common bile duct.',
                                      status='not_performed', status_words='No lithotripsy was performed'),
            'planned': stone_clearance('Mechanical lithotripsy of the 15 mm stone in the common bile duct is planned.',
                                       status='planned', status_words='is planned'),
            'an earlier encounter': stone_clearance(
                'In 2024 a 15 mm stone in the common bile duct was fragmented with mechanical lithotripsy.',
                time=a('earlier_encounter', 'In 2024', ['P3'])),
            'another family': stone_clearance(procedure=a('egd')),
        }
        for name, (inv, text, lines) in unclaimed.items():
            with self.subTest(unclaimed=name):
                self.assertEqual(claims(inv, text, '43265', lines['P3']), ())
        inv, text, lines = unclaimed['another family']
        self.assertEqual(events.Reading.of(inv).events['E3']['family'], 'gi.egd')
        inv, text, lines = stone_clearance(
            'At the original procedure, a 15 mm stone in the common bile duct was fragmented with mechanical '
            'lithotripsy.', time=a('current_encounter', 'At the original procedure', ['P3']))
        lithotripsy = events.Reading.of(inv).events['E3']
        self.assertEqual((lithotripsy['family'], lithotripsy['time']['state']), ('gi.ercp', 'unverified'))
        self.assertEqual(claims(inv, text, '43265', lines['P3']),
                         ('E4', 'E3') if coverage.possibly_current(lithotripsy) else ())  # D163: E3 too

    def test_d74_the_hot_forceps_and_gastrostomy_codes_compete_when_their_defining_act_is_doubted(self):
        """The two other codes D74 widens: 44365 (its hot forceps removal's time unanchored) beside 44369 for the
        ablation, and 49440 (its gastrostomy's status words unbound) beside 49441 for the jejunostomy tube placement.
        Each pair is held with competing_codes; each held narrowed code keeps its own question."""
        lines = {'P1': 'The enteroscope was advanced to the jejunum.',
                 'P2': 'Two gastric antral angioectasias were treated with argon plasma coagulation.',
                 'P3': 'During the procedure, a 5 mm jejunal polyp was removed with hot biopsy forceps.'}
        inv, text = inventory(lines, reach=[reached(landmark='jejunum', words='jejunum')], events=[
            exam(words='enteroscope', procedure=a('enteroscopy')),
            act('E2', 'P2', 'ablation', 'argon plasma coagulation', status_words='were treated',
                procedure=a('enteroscopy'), technique=a('argon_plasma', 'argon plasma coagulation', ['P2']),
                target=tg('', 'gastric_antrum', 'gastric antral', ['P2'])),
            act('E3', 'P3', 'hot_biopsy', 'hot biopsy forceps', status_words='was removed', procedure=a('enteroscopy'),
                technique=a('hot_forceps', 'hot biopsy forceps', ['P3']), target=tg('', 'jejunum', 'jejunal', ['P3']),
                time=a('current_encounter', 'During the procedure', ['P3']))])
        self.assertEqual(events.Reading.of(inv).events['E3']['time']['reasons'], ['current_unanchored'])
        result = run(inv, text, [('44365', lines['P3']), ('44369', lines['P2'])])
        self.assertEqual({code: (proposal(result, code).status, asked(proposal(result, code)),
                                 proposal(result, code).support.get('competes')) for code in ('44365', '44369')},
                         {'44365': ('needs_clarification', ['event_time', 'competing_codes'], ['44369']),
                          '44369': ('needs_clarification', ['competing_codes'], ['44365'])})
        lines = {'P1': 'A 14 Fr jejunostomy tube was placed percutaneously under fluoroscopic guidance.',
                 'P2': 'A 20 Fr gastrostomy tube was placed percutaneously under fluoroscopic guidance.'}
        inv, text = inventory(lines, events=[
            act('E1', 'P1', 'tube_placement', 'jejunostomy tube', status_words='was placed',
                procedure=a('feeding_tube')),
            act('E2', 'P2', 'peg', 'gastrostomy tube', status_words='was inserted', procedure=a('feeding_tube'))])
        self.assertEqual(events.Reading.of(inv).events['E2']['status']['state'], 'unverified')
        result = run(inv, text, [('49440', lines['P2']), ('49441', lines['P1'])])
        self.assertEqual({code: (proposal(result, code).status, asked(proposal(result, code)),
                                 proposal(result, code).support.get('competes')) for code in ('49440', '49441')},
                         {'49440': ('needs_clarification', ['performed_status', 'competing_codes'], ['49441']),
                          '49441': ('needs_clarification', ['competing_codes'], ['49440'])})

    def test_d74_controls_a_verified_lithotripsy_competes_and_none_documented_claims_nothing(self):
        """Controls D74 keeps (D55 and D27): the verified lithotripsy and the frame 'During this procedure' compete as
        before; with no lithotripsy stated at all, 43265 is held not documented, claims nothing, and 43264 is READY."""
        frame = dict(p3='During this procedure, a 15 mm stone in the common bile duct was fragmented with mechanical '
                        'lithotripsy.', time=a('current_encounter', 'During this procedure', ['P3']))
        for name, options in (('verified', {}), ('a whole present-encounter frame', frame)):
            inv, text, lines = stone_clearance(**options)
            with self.subTest(control=name):
                self.assertEqual(events.Reading.of(inv).events['E3']['time']['state'], 'verified')
                result = run(inv, text, [('43264', lines['P4']), ('43265', lines['P3'])], participants=READ_NOTHING)
                self.assertEqual({code: (asked(proposal(result, code)), proposal(result, code).support.get('competes'))
                                  for code in ('43264', '43265')},
                                 {'43264': (['competing_codes'], ['43265']), '43265': (['competing_codes'], ['43264'])})
        lines = {pid: STONE[pid] for pid in ('P1', 'P2', 'P4')}
        inv, text = inventory(lines, events=[
            exam('E1', 'P1', words='duodenoscope', procedure=a('ercp')),
            act('E2', 'P2', 'cannulation', 'cannulation', status_words='was achieved', procedure=a('ercp'),
                target=tg('', 'bile_duct', 'biliary', ['P2']), technique=a('sphincterotome', 'sphincterotome', ['P2'])),
            act('E4', 'P4', 'stone_extraction', 'extracted', status_words='were extracted', procedure=a('ercp'),
                target=tg('', 'bile_duct', 'bile duct', ['P4']),
                technique=a('extraction_balloon', 'extraction balloon', ['P4']))])
        self.assertEqual(claims(inv, text, '43265', lines['P4']), ())
        result = run(inv, text, [('43264', lines['P4']), ('43265', lines['P4'])], participants=READ_NOTHING)
        self.assertEqual((proposal(result, '43264').status, proposal(result, '43265').support['reason']),
                         ('ready', events.NOT_DOCUMENTED))


# --- D75: an act whose procedure is not usable, beside the diagnostic base code -----------------------------------------

EGD_LINE = ('Gastroscope passed under direct vision through the esophagus and\nstomach to the second part of the '
            'duodenum.')
# Finding 17's committed recordings: in each, Gemini cites the heading 'EGD' (3 characters, too short to locate) as the
# four cold-forceps biopsies' procedure words; with two current families the default does not settle.
FINDING_17 = {('W1-u31a-reg-p1-history-families-004', 'r1'): ['E2', 'E3', 'E4', 'E5'],
              ('W1-u31a-reg-p1-history-families-004', 'r2'): ['E2', 'E3', 'E4', 'E5'],
              ('W1-u31a-reg-p1-history-families-004', 'r3'): ['E4', 'E5', 'E6', 'E7'],
              ('W1S-438', 'r1'): ['E6', 'E7', 'E8', 'E9'],
              ('W1S-068', 'r1'): ['E6', 'E7', 'E8', 'E9']}


def replayed(document: str, run_name: str):
    """(inventory, text, pages) of a committed FRESH recording, read and normalized as the pipeline does (nothing is
    sent: tests/test_interpretation_replay.py)."""
    entry = next(item for item in MANIFEST['documents'] if item['id'] == document)
    text, pages = text_and_pages(entry)
    request = adapter.Interpreter().build_request(text, pages, 'paste')
    body = (FIXTURES / entry['runs'][run_name]['body']).read_bytes()
    parsed = interpretation_read.read(adapter.answer_text(request, body))
    return normalize.normalize(parsed, text), text, pages


def assessed(inv, text: str, pages, codes):
    return assess.assess(inventory=inv, context=facts.derive(inv, {}).facts, normalized=response(text, codes),
                         provider_status='succeeded', reference=LOOKUP, text=text, pages=pages, extraction_status='ok')


def egd_session(result) -> tuple:
    session = result.completeness['event_coding']['sessions']['gi.egd']
    return [item['event'] for item in session['reportable']], [item['event'] for item in session['doubted']]


class D75UnusableProcedure(SimpleTestCase):
    def test_d75_finding_17_43235_is_held_beside_the_egd_biopsies_whose_procedure_is_unverified(self):
        """Finding 17's five recordings, 43235 proposed alone (the installed release asks base_included there): the
        four biopsies (done, their procedure unverified: passage_unlocated, procedure_unsettled) are the EGD session's
        doubted acts, so 43235 is held with base_included, never READY."""
        for (document, run_name), biopsies in FINDING_17.items():
            inv, text, pages = replayed(document, run_name)
            reading = events.Reading.of(inv)
            with self.subTest(document=document, run=run_name):
                for eid in biopsies:
                    event = reading.events[eid]
                    self.assertEqual((event['family'], event['catalogue_kind'], events.done(event),
                                      event['procedure']['state'], event['procedure']['reasons']),
                                     ('gi.egd', 'biopsy', True, 'unverified',
                                      ['passage_unlocated', 'procedure_unsettled']))
                result = assessed(inv, text, pages, [('43235', EGD_LINE)])
                p = proposal(result, '43235')
                self.assertEqual((p.status, asked(p)), ('needs_clarification', ['base_included']))
                self.assertEqual(egd_session(result), ([], biopsies))
                self.assertIn('includes forceps biopsy (stated in doubt), which this diagnostic code does not account '
                              'for', check(p, 'services.base_included').detail)

    def test_d75_control_the_biopsies_procedure_verified_holds_43235_through_reportable(self):
        """The control: the same five readings with only the biopsies' procedure verified. They are reportable, not
        doubted, and 43235 is held with base_included as before D75."""
        for (document, run_name), biopsies in FINDING_17.items():
            inv, text, pages = replayed(document, run_name)
            content = {'events': copy.deepcopy(inv.events), 'encounter_facts': copy.deepcopy(inv.encounter_facts),
                       'open_questions': copy.deepcopy(inv.open_questions)}
            for event in content['events']['events']:
                if event['id'] in biopsies:
                    event['procedure'] = dict(event['procedure'], state='verified', reasons=[])
            with self.subTest(document=document, run=run_name):
                result = assessed(content, text, pages, [('43235', EGD_LINE)])
                p = proposal(result, '43235')
                self.assertEqual((p.status, asked(p)), ('needs_clarification', ['base_included']))
                self.assertEqual(egd_session(result), (biopsies, []))
                self.assertIn('includes forceps biopsy, which this diagnostic code does not account for',
                              check(p, 'services.base_included').detail)


UPPER_AND_LOWER = {'G1': 'EGD: the gastroscope was advanced to the second portion of the duodenum.',
                   'G2': 'Cold forceps biopsies were taken from the gastric antrum.',
                   'P1': 'Colonoscopy: The colonoscope was advanced to the cecum.'}
GASTROSCOPE = UPPER_AND_LOWER['G1']


def upper_and_lower(*, biopsy=None, egd=None, lines=None, open_questions=(), named=False):
    """An EGD (E1) and a colonoscopy (E3) at one session, and an antral cold forceps biopsy (E2) whose procedure is
    'egd' with no words: with two families the default does not settle, so it is unverified (``biopsy`` changes it;
    ``lines`` replaces document lines)."""
    biopsy = dict({'status_words': 'were taken', 'procedure': a('egd'),
                   'technique': a('cold_forceps', 'cold forceps', ['G2']),
                   'target': tg('', 'gastric_antrum', 'gastric antrum', ['G2'])}, **(biopsy or {}))
    events_ = [exam('E1', 'G1', words='gastroscope', **dict({'procedure': a('egd', 'EGD', ['G1'])}, **(egd or {}))),
               act('E2', 'G2', 'biopsy', 'biopsies', **biopsy),
               exam('E3', 'P1', words='colonoscope', procedure=a('colonoscopy', 'Colonoscopy', ['P1']))]
    return inventory(dict(UPPER_AND_LOWER, **(lines or {})), events=events_, open_questions=open_questions, named=named,
                     reach=[reached('E1', 'second_portion_duodenum', 'second portion of the duodenum', 'G1'),
                            reached('E3', 'cecum', 'cecum', 'P1')])


class D75Doubted(SimpleTestCase):
    def test_d75_an_unverified_or_opened_procedure_is_doubted_and_holds_the_base_code(self):
        """Synthetic: the biopsy's procedure unverified (the default unsettled; words that do not bind) or opened by
        Gemini's own open question - the act is doubted in its family's current session, and 43235 is held with
        base_included."""
        shapes = {
            'unsettled default': ({}, ['procedure_unsettled']),
            'words that do not bind': (dict(biopsy={'procedure': a('egd', 'upper endoscopy', ['G2'])}),
                                       ['words_unlocated', 'procedure_unsettled']),
            'opened by an open question': (dict(biopsy={'procedure': a('egd', 'EGD', ['G1'])}, open_questions=[
                {'about': 'procedure', 'events': ['E2'], 'lesions': [], 'passages': ['G2']}]), []),
        }
        for name, (options, reasons) in shapes.items():
            inv, text = upper_and_lower(**options)
            reading = events.Reading.of(inv)
            biopsy = reading.events['E2']
            with self.subTest(shape=name):
                self.assertEqual((biopsy['procedure']['reasons'], biopsy['procedure']['open']),
                                 (reasons, name.startswith('opened')))
                self.assertFalse(events.usable(biopsy, 'procedure'))
                self.assertTrue(events.done(biopsy))
                self.assertEqual((coverage.reportable(reading, biopsy), coverage.doubted(reading, biopsy)),
                                 (False, True))
                result = run(inv, text, [('43235', GASTROSCOPE)])
                p = proposal(result, '43235')
                self.assertEqual((p.status, asked(p)), ('needs_clarification', ['base_included']))
                self.assertEqual(egd_session(result), ([], ['E2']))

    def test_d75_the_doubt_keeps_its_bounds(self):
        """What D75 does not doubt: a biopsy whose procedure is verified (reportable instead), one verified at an
        earlier encounter or by another clinician, one denied or planned, and - D75's gate - one whose family has no
        current session (its examination verified at an earlier encounter: no done examination)."""
        inv, text = upper_and_lower(biopsy={'procedure': a('egd', 'EGD', ['G2'])},
                                    lines={'G2': 'EGD: cold forceps biopsies were taken from the gastric antrum.'})
        reading = events.Reading.of(inv)
        self.assertEqual(reading.events['E2']['procedure']['state'], 'verified')
        self.assertEqual((coverage.reportable(reading, reading.events['E2']),
                          coverage.doubted(reading, reading.events['E2'])), (True, False))
        neither = {  # name: (the biopsy's changes, its line, the attribute verified to set it apart)
            'an earlier encounter': (dict(time=a('earlier_encounter', 'In 2024', ['G2'])),
                                     'In 2024 cold forceps biopsies were taken from the gastric antrum.', 'time'),
            'another clinician': (dict(performer=a('other_clinician', 'Dr. Kestrel Vane', ['G2'])),
                                  'Dr. Kestrel Vane took cold forceps biopsies from the gastric antrum.', 'performer'),
            'denied': (dict(status='not_performed', status_words='No biopsies were taken'),
                       'No biopsies were taken from the gastric antrum.', 'status'),
            'planned': (dict(status='planned', status_words='are planned'),
                        'Cold forceps biopsies of the gastric antrum are planned.', 'status'),
        }
        for name, (biopsy, line, attribute) in neither.items():
            inv, text = upper_and_lower(biopsy=biopsy, lines={'G2': line}, named=True)
            reading = events.Reading.of(inv)
            with self.subTest(neither=name):
                self.assertFalse(events.usable(reading.events['E2'], 'procedure'))
                self.assertEqual(reading.events['E2'][attribute]['state'], 'verified')
                self.assertFalse(coverage.doubted(reading, reading.events['E2']))
        inv, text = upper_and_lower(egd={'time': a('earlier_encounter', 'In 2024', ['G1'])}, lines={
            'G1': 'In 2024 the gastroscope was advanced to the second portion of the duodenum.'})
        reading = events.Reading.of(inv)
        self.assertEqual((events.done(reading.events['E1']), events.done(reading.events['E2'])), (False, True))
        self.assertFalse(events.usable(reading.events['E2'], 'procedure'))
        self.assertFalse(coverage.doubted(reading, reading.events['E2']))
        self.assertEqual(run(inv, text, [('45378', UPPER_AND_LOWER['P1'])]).completeness['event_coding'][
            'sessions']['gi.egd']['doubted'], [])
