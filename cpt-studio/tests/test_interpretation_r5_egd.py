"""DECISIONS D115-D119 (the Gemini migration's round-4 family parity audit of the EGD codes, gaps D, A, B, C and H),
SYNTHETIC, each built from its gap's own input (repair4/audit-egd: the document, a Gemini answer written to prompt.py's
contract, the proposer's citations replayed) and its controls:
- D115 (gap D, critical): "Two hemostatic clips were placed across the ulcer." beside "A 12 mm clean-based ulcer ..." - a
  clip or an injection read as a bleeding control from its verified hemostasis purpose alone, whose own words state no
  bleeding, is a bleeding control in DOUBT (mapping.POSSIBLE_BLEEDING_CONTROL): 43255 (43227, 44366, 45334, 45382) is
  held with performed_status, never READY; no injection code takes it; the base code beside it stays held and the act
  is listed in doubt.
- D116 (gap A): an EGD stent removal or exchange (Gemini's stent_removal and stent_exchange) is a reportable kind of its
  session: 43235 beside it is held base_included.
- D117 (gap B): a positive removal whose method is not stated ("A polypectomy of the gastric body polyp was performed.",
  Gemini's 'removal' umbrella) is a doubted act of its session: the base code is held base_included, and the act is
  listed in doubt with the method question - never invisible.
- D118 (gap C): two dilation codes of different techniques for ONE stricture (a through-the-scope balloon, then a Savary
  dilator) compete, as the installed release's _same_claim holds them: both are held with competing_codes.
- D119 (gap H): a PEG Gemini files under the feeding-tube procedure, beside a done EGD, holds 43235 base_included, as the
  installed release reads the PEG as the EGD's own act.
CASES holds every input, so the installed release (c2e53f8e) can be run on the very same texts and citations. Each test
asserts in independent subtests - the outcome, the read-time overlay, the structure - so a regression shows every one it
breaks. Nothing is sent."""
from __future__ import annotations

import copy

from django.test import SimpleTestCase

from studio.interpretation import combination, coverage, events, mapping, normalize, overlay
from studio.types import to_jsonable
from tests.test_interpretation_events import asked, check, proposal, run
from tests.test_interpretation_identity import accepted

HEAD = 'SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE'
DAY = '2026-11-05'
ADV = 'The gastroscope was advanced to the second portion of the duodenum.'
BASE_INCLUDED, COMPETING = 'services.base_included', 'proposals.competing'


# --- the audit's builders (repair4/audit-egd/scripts/build_cases.py) ------------------------------------------------------

def at(value: str, words: str = '', passages=()) -> dict:
    return {'value': value, 'words': words, 'passages': list(passages)}


def tgt(lesion: str = '', landmark: str = 'not_stated', words: str = '', passages=()) -> dict:
    return {'lesion': lesion, 'landmark': landmark, 'words': words, 'passages': list(passages)}


def event(eid: str, procedure: dict, kind: dict, *, status: dict, technique=None, target=None, time=None,
          performer=None, purpose=None) -> dict:
    return {'id': eid, 'procedure': procedure, 'kind': kind, 'technique': technique or at('not_stated'),
            'target': target or tgt(), 'time': time or at('current_encounter'),
            'performer': performer or at('documenting_team'), 'status': status,
            'scope': {'value': 'not_applicable', 'targets': [], 'words': '', 'passages': []},
            'purpose': purpose or at('not_stated'), 'part_of': '', 'sequence': 0, 'contradicts': []}


def lesion(lid: str, words: str, landmark: str, site_words: str, size_words: str, passages) -> dict:
    return {'id': lid, 'words': words, 'landmark': landmark, 'site_words': site_words, 'size_words': size_words,
            'multiplicity': 'single', 'passages': list(passages)}


def report(title: str = 'UPPER ENDOSCOPY REPORT', **lines) -> dict:
    """The audit's report: the synthetic banner (P1), the title (P2), the date line (P3), the endoscopist (P4), then
    ``lines`` (P5 ... in order)."""
    return {'P1': HEAD, 'P2': title, 'P3': 'Date of service: November 5, 2026',
            'P4': 'Endoscopist: Tomas Reyes, MD (fictional)', **lines}


def examination(procedure: str = 'egd', words: str = 'UPPER ENDOSCOPY', scope: str = 'The gastroscope was advanced',
                device: str = 'gastroscope') -> dict:
    """The session's examination (E1): ``device`` advanced (P5), performed, its procedure named by the title (P2)."""
    return event('E1', at(procedure, words, ['P2']), at('examination', scope, ['P5']),
                 technique=at('endoscope', device, ['P5']), status=at('performed', 'was advanced', ['P5']))


CASES: dict = {}
EGD_REACH = ('E1', 'second_portion_duodenum', 'second portion of the duodenum', 'P5')


def case(name: str, lines: dict, events_: list, codes, *, lesions=(), reach=EGD_REACH, anatomy=()) -> str:
    """Record ``name``: the text of ``lines``, the answer (every line but the banner cited; the date of P3, the
    endoscopist of P4, the examination's reach), the proposer's citations ``codes`` ((code, (quotes ...)) each)."""
    text = '\n'.join(lines.values()) + '\n'
    value = {'passages': [{'id': pid, 'text': line} for pid, line in lines.items() if pid != 'P1'],
             'encounter': {'date_of_service': {'value': DAY, 'state': 'stated', 'words': 'November 5, 2026',
                                               'passages': ['P3'], 'other_dates': []},
                           'documenting_endoscopist': {'words': 'Tomas Reyes, MD (fictional)', 'passages': ['P4']},
                           'team': [], 'anatomy': list(anatomy),
                           'reach': ([{'event': reach[0], 'landmark': reach[1], 'words': reach[2], 'passages': [reach[3]],
                                       'completion': at('not_stated')}] if reach else []),
                           'visit_facts': []},
             'lesions': list(lesions), 'events': list(events_), 'open_questions': []}
    for _, quotes in codes:
        for quote in quotes:
            assert quote in text, (name, quote)
    CASES[name] = {'text': text, 'answer': value, 'codes': [[code, list(quotes)] for code, quotes in codes], 'day': DAY}
    return name


def built(name: str):
    """(the normalized inventory, the text) of case ``name``."""
    item = CASES[name]
    return normalize.normalize(accepted(copy.deepcopy(item['answer'])), item['text']), item['text']


def assessed(name: str):
    inv, text = built(name)
    return run(inv, text, [(code, tuple(quotes)) for code, quotes in CASES[name]['codes']])


def reviewed(result, code: str):
    """The read-time overlay's view of ``code`` over the stored rows and event coding."""
    stored = [overlay.stored_from(p) for p in result.proposals]
    return overlay.review_view(stored, {}, completeness=to_jsonable(result.completeness))[proposal(result, code).key]


def items(result) -> list:
    return [(item['act'], item['reason']) for item in result.completeness['unresolved_items']]


def service_facts(result) -> list:
    return [spec.fact for spec in result.clarifications]


def session_labels(result, family: str = 'gi.egd') -> tuple:
    coding = result.completeness['event_coding']['sessions'][family]
    return [item['label'] for item in coding['reportable']], [item['label'] for item in coding['doubted']]


def held_base(test, result, code: str, included: str) -> None:
    """``code`` is held with the base rule's own question beside ``included`` at assess time, and the overlay keeps it."""
    p = proposal(result, code)
    with test.subTest(part=f'{code} held base_included'):
        test.assertEqual((p.status, asked(p), [spec.question for spec in p.clarifications]),
                         ('needs_clarification', ['base_included'],
                          [f'Is {code} reported separately from {included} for this examination?']))
        test.assertIsNotNone(check(p, BASE_INCLUDED))
    with test.subTest(part=f'{code} held at read time'):
        view = reviewed(result, code)
        test.assertEqual((view.status, view.released, [q['fact'] for q in view.questions]),
                         ('needs_clarification', (), ['base_included']))


def ready(test, result, code: str) -> None:
    p = proposal(result, code)
    with test.subTest(part=f'{code} READY'):
        test.assertEqual((p.status, asked(p), check(p, BASE_INCLUDED), check(p, COMPETING)), ('ready', [], None, None))
        test.assertEqual(reviewed(result, code).status, 'ready')


def held(test, result, code: str, facts: list) -> None:
    p = proposal(result, code)
    with test.subTest(part=f'{code} held {facts}'):
        test.assertEqual((p.status, asked(p)), ('needs_clarification', facts))
        test.assertEqual(reviewed(result, code).status, 'needs_clarification')


EGD = at('egd', 'UPPER ENDOSCOPY', ['P2'])

# --- D115 (gap D): a hemostatic clip or injection whose own words state no bleeding is a bleeding control in doubt ------

CLEAN_ULCER = 'A 12 mm clean-based ulcer was seen in the gastric antrum.'
CLIPS = 'Two hemostatic clips were placed across the ulcer.'
NORMAL = 'The esophagus and duodenum were normal.'
ULCER = lesion('L1', '12 mm clean-based ulcer', 'gastric_antrum', 'gastric antrum', '12 mm', ['P6', 'P7'])


def clip(line: str = CLIPS, *, kind_words: str = 'clips were placed', status_words: str = 'were placed',
         technique_words: str = 'hemostatic clips', target_words: str = 'the ulcer', purpose_words: str = 'hemostatic',
         kind: str = 'clip', technique: str = 'clip', procedure=EGD, landmark: str = 'gastric_antrum') -> dict:
    """Gap D's E2: a clip (P7), performed, of lesion L1 ('the ulcer'), its purpose hemostasis worded 'hemostatic' (the
    attested note8 and C2MEM purpose shape: "hemostatic clipping" with purpose hemostasis, words "hemostatic")."""
    assert all(words in line for words in (kind_words, status_words, technique_words, target_words, purpose_words))
    return event('E2', procedure, at(kind, kind_words, ['P7']), status=at('performed', status_words, ['P7']),
                 technique=at(technique, technique_words, ['P7']), target=tgt('L1', landmark, target_words, ['P7']),
                 purpose=at('hemostasis', purpose_words, ['P7']))


def ulcer_case(name: str, codes, *, ulcer: str = CLEAN_ULCER, line: str = CLIPS, act=None, ulcer_lesion=ULCER) -> str:
    """Gap D's document D1: the clean-based ulcer (P6), clipped (P7)."""
    lines = report(P5=ADV, P6=ulcer, P7=line, P8=NORMAL)
    return case(name, lines, [examination(), act if act is not None else clip(line)], codes, lesions=[ulcer_lesion])


D1 = ulcer_case('d115_d1', [('43255', (CLIPS,))])
D1_BASE = ulcer_case('d115_d1_base', [('43235', (ADV,))])
INJECTION_LINE = 'A hemostatic injection of dilute epinephrine was given into the ulcer base.'
INJECTION = clip(INJECTION_LINE, kind='injection', kind_words='injection', status_words='was given',
                 technique='injection', technique_words='injection', target_words='the ulcer base')
D1_INJECTION = ulcer_case('d115_injection', [('43255', (INJECTION_LINE,)), ('43236', (INJECTION_LINE,)),
                                             ('43243', (INJECTION_LINE,)), ('43235', (ADV,))],
                          line=INJECTION_LINE, act=INJECTION)
# bleeding stated, or the hemostasis named, in the act's own words: a bleeding control, as before (controls)
OOZING_LINE = 'Two hemostatic clips were placed across the oozing vessel at the ulcer base.'
D1_OOZING = ulcer_case('d115_own_words_oozing', [('43255', (OOZING_LINE,))], line=OOZING_LINE,
                       act=clip(OOZING_LINE, target_words='the oozing vessel at the ulcer base'))
NOUN_LINE = 'Two clips were placed across the ulcer for hemostasis.'
D1_NOUN = ulcer_case('d115_own_words_hemostasis', [('43255', (NOUN_LINE,))], line=NOUN_LINE,
                     act=clip(NOUN_LINE, technique_words='clips', purpose_words='for hemostasis'))
CONTROL_LINE = 'Two hemostatic clips were placed to control the bleeding from the ulcer.'
D1_CONTROL = ulcer_case('d115_own_words_control', [('43255', (CONTROL_LINE,))], line=CONTROL_LINE,
                        act=clip(CONTROL_LINE, purpose_words='to control the bleeding', target_words='the ulcer'))
# a bleeding word that is negated, prevented or hedged states none: in doubt (held)
PREVENT_LINE = 'Two hemostatic clips were placed across the ulcer to prevent delayed bleeding.'
D1_PREVENT = ulcer_case('d115_prevention', [('43255', (PREVENT_LINE,))], line=PREVENT_LINE,
                        act=clip(PREVENT_LINE, purpose_words='to prevent delayed bleeding'))
NON_BLEEDING_LINE = 'Two hemostatic clips were placed across the non-bleeding ulcer.'
D1_NON_BLEEDING = ulcer_case('d115_non_bleeding', [('43255', (NON_BLEEDING_LINE,))], line=NON_BLEEDING_LINE,
                             act=clip(NON_BLEEDING_LINE, target_words='the non-bleeding ulcer'))
STIGMATA_LINE = 'Two hemostatic clips were placed across the ulcer without stigmata of recent bleeding.'
D1_STIGMATA = ulcer_case('d115_without_stigmata', [('43255', (STIGMATA_LINE,))], line=STIGMATA_LINE,
                         act=clip(STIGMATA_LINE, target_words='the ulcer without stigmata of recent bleeding'))
# its time not anchored to this encounter (D35: "At that time" names another occasion): the time question survives
AT_THAT_TIME = 'At that time, two hemostatic clips were placed across the ulcer.'
TIMED_CLIP = clip(AT_THAT_TIME)
TIMED_CLIP['time'] = at('current_encounter', 'At that time', ['P7'])
D1_TIME = ulcer_case('d115_time_unanchored', [('43255', (AT_THAT_TIME,))], line=AT_THAT_TIME, act=TIMED_CLIP)
# gap D's D3: bleeding stated only for the lesion, in another sentence - not read (the recorded cost)
OOZING_ULCER = 'A 12 mm ulcer with an oozing visible vessel was seen in the gastric antrum.'
D3 = ulcer_case('d115_d3_lesion_only', [('43255', (CLIPS,))], ulcer=OOZING_ULCER,
                ulcer_lesion=lesion('L1', '12 mm ulcer with an oozing visible vessel', 'gastric_antrum',
                                    'gastric antrum', '12 mm', ['P6', 'P7']))


def family_case(name: str, title: str, procedure: str, scope_words: str, device: str, landmark: str, reach: tuple,
                code: str, base: str) -> str:
    """The D1 shape in another family: its examination (P5), a clean-based ulcer at ``landmark`` (P6), two hemostatic
    clips across it (P7); ``code`` (its bleeding-control code) and ``base`` (its base code) proposed."""
    where = landmark.replace('_', ' ')
    advanced = f'The {device} was advanced to the {reach[2]}.'
    ulcer = f'A 6 mm clean-based ulcer was seen in the {where}.'
    lines = report(title, P5=advanced, P6=ulcer, P7=CLIPS, P8='No other lesion was seen.')
    proc = at(procedure, title.split(' REPORT')[0], ['P2'])
    exam = event('E1', proc, at('examination', scope_words, ['P5']), technique=at('endoscope', device, ['P5']),
                 status=at('performed', 'was advanced', ['P5']))
    return case(name, lines, [exam, clip(procedure=proc, landmark=landmark)], [(code, (CLIPS,)), (base, (advanced,))],
                lesions=[lesion('L1', '6 mm clean-based ulcer', landmark, where, '6 mm', ['P6', 'P7'])],
                reach=('E1', reach[0], reach[2], 'P5'))


FAMILIES = {
    '45382': family_case('d115_colonoscopy', 'COLONOSCOPY REPORT', 'colonoscopy', 'The colonoscope was advanced',
                         'colonoscope', 'ascending_colon', ('cecum', '', 'cecum'), '45382', '45378'),
    '45334': family_case('d115_sigmoidoscopy', 'FLEXIBLE SIGMOIDOSCOPY REPORT', 'flex_sig',
                         'The sigmoidoscope was advanced', 'sigmoidoscope', 'sigmoid_colon',
                         ('descending_colon', '', 'descending colon'), '45334', '45330'),
    # the esophagoscopy's bleeding-control code, of the upper GI family: on gap D's own EGD document
    '43227': ulcer_case('d115_esophagoscopy_code', [('43227', (CLIPS,)), ('43235', (ADV,))]),
    '44366': family_case('d115_enteroscopy', 'PUSH ENTEROSCOPY REPORT', 'enteroscopy', 'The enteroscope was advanced',
                         'enteroscope', 'jejunum', ('jejunum', '', 'proximal jejunum'), '44366', '44360'),
}

# a hemostatic clip on the lesion a snare removes: read as the bleeding control it is that removal's procedural adjunct
# (D30), never separately reported - so it is no doubted act of its own (not listed), and 43255 is held
POLYP = 'A 7 mm sessile polyp in the gastric body was removed with a cold snare.'
SITE_CLIPS = 'Two hemostatic clips were placed on the polypectomy site of the polyp.'
ADJUNCT = case('d115_adjunct', report(P5=ADV, P6=POLYP, P7=SITE_CLIPS, P8=NORMAL),
               [examination(),
                event('E3', EGD, at('snare', 'removed with a cold snare', ['P6']),
                      status=at('performed', 'was removed', ['P6']), technique=at('cold_snare', 'cold snare', ['P6']),
                      target=tgt('L1', 'gastric_body', 'A 7 mm sessile polyp in the gastric body', ['P6']),
                      purpose=at('removal', 'removed', ['P6'])),
                clip(SITE_CLIPS, target_words='the polypectomy site of the polyp', landmark='gastric_body')],
               [('43251', (POLYP,)), ('43255', (SITE_CLIPS,))],
               lesions=[lesion('L1', '7 mm sessile polyp', 'gastric_body', 'gastric body', '7 mm', ['P6', 'P7'])])


def raw(kind: str, status: str = 'performed', *, status_state: str = 'verified', purpose_words: str = 'hemostatic',
        status_words: str = 'were placed') -> dict:
    """An event in its stored shape, as far as catalogue_kind reads it: a verified hemostasis purpose worded
    ``purpose_words`` and ``status`` (worded ``status_words``) in ``status_state``."""
    def record(value, text='', state='verified'):
        return {'value': value, 'state': state, 'open': False, 'basis': 'stated',
                'words': {'text': text, 'start': 0, 'end': len(text)} if text else None}
    return {'id': 'E2', 'family': 'gi.egd', 'kind': record(kind), 'status': record(status, status_words, status_state),
            'purpose': record('hemostasis', purpose_words), 'target': record('not_stated'),
            'technique': record('not_stated')}


class D115BleedingControlInDoubt(SimpleTestCase):
    """D115: c2e53f8e holds 43255 on gap D's D1 ("leaves the bleeding control in doubt"); 1caaf0609 read the clip as a
    bleeding control done and gave it READY."""

    def test_d115_gap_d1_hemostatic_clips_with_no_bleeding_stated_hold_43255(self):
        inv, _ = built(D1)
        clipped = events.Reading.of(inv).events['E2']
        with self.subTest(part='the event: a bleeding control in doubt'):
            self.assertEqual((clipped['catalogue_kind'], clipped['key']['role'], mapping.hemostasis_in_doubt(clipped)),
                             (mapping.POSSIBLE_BLEEDING_CONTROL, 'act', True))
        result = assessed(D1)
        p = proposal(result, '43255')
        with self.subTest(part='43255 held with performed_status, never READY'):
            self.assertEqual((p.status, asked(p)), ('needs_clarification', ['performed_status']))
            self.assertEqual(p.support['state'], 'uncertain')
        with self.subTest(part='the question shows the clip statement the code cites'):
            self.assertIn(CLIPS, [span['text'] for span in p.support['source']])
        with self.subTest(part='the overlay keeps it held'):
            self.assertEqual(reviewed(result, '43255').status, 'needs_clarification')
        with self.subTest(part='the act is listed in doubt, never invisible'):
            self.assertEqual(items(result), [(mapping.POSSIBLE_BLEEDING_CONTROL, 'in_doubt')])

    def test_d115_43235_beside_the_bleeding_control_in_doubt_stays_held(self):
        result = assessed(D1_BASE)
        with self.subTest(part='the event coding lists it in doubt'):
            self.assertEqual(session_labels(result), ([], ['possible bleeding control']))
        held_base(self, result, '43235', 'possible bleeding control (stated in doubt)')

    def test_d115_a_hemostatic_injection_with_no_bleeding_stated_takes_no_code(self):
        result = assessed(D1_INJECTION)
        for code in ('43255', '43236', '43243'):
            held(self, result, code, ['performed_status'])
        held_base(self, result, '43235', '43255, 43236, 43243')

    def test_d115_bleeding_stated_or_hemostasis_named_in_its_own_words_keeps_the_bleeding_control(self):
        for name in (D1_OOZING, D1_NOUN, D1_CONTROL):
            with self.subTest(case=name):
                inv, _ = built(name)
                self.assertEqual(events.Reading.of(inv).events['E2']['catalogue_kind'], mapping.BLEEDING_CONTROL)
                ready(self, assessed(name), '43255')

    def test_d115_a_negated_prevented_or_hedged_bleeding_word_states_none(self):
        for name in (D1_PREVENT, D1_NON_BLEEDING, D1_STIGMATA):
            with self.subTest(case=name):
                inv, _ = built(name)
                self.assertEqual(events.Reading.of(inv).events['E2']['catalogue_kind'],
                                 mapping.POSSIBLE_BLEEDING_CONTROL)
                held(self, assessed(name), '43255', ['performed_status'])

    def test_d115_every_family_holds_its_bleeding_control_code(self):
        for code, name in FAMILIES.items():
            result = assessed(name)
            with self.subTest(code=code):
                held(self, result, code, ['performed_status'])
                base = CASES[name]['codes'][1][0]
                self.assertEqual((proposal(result, base).status, asked(proposal(result, base))),
                                 ('needs_clarification', ['base_included']))

    def test_d115_a_statement_that_is_not_a_usable_performed_keeps_the_bleeding_control(self):
        cases = {
            'performed, verified': (raw('clip'), mapping.POSSIBLE_BLEEDING_CONTROL),
            'injection performed': (raw('injection'), mapping.POSSIBLE_BLEEDING_CONTROL),
            'a denial': (raw('clip', 'not_performed', status_words='No hemostatic clips'), mapping.BLEEDING_CONTROL),
            'planned': (raw('clip', 'planned', status_words='will be placed'), mapping.BLEEDING_CONTROL),
            'uncertain': (raw('clip', 'uncertain', status_words='may have been placed'), mapping.BLEEDING_CONTROL),
            'attempted': (raw('clip', 'attempted_not_completed', status_words='could not be placed'),
                          mapping.BLEEDING_CONTROL),
            'status words unbound': (raw('clip', status_state='unverified'), mapping.BLEEDING_CONTROL),
            'a tattoo is no hemostatic kind': (raw('tattoo'), 'tattoo'),
        }
        for name, (item, expected) in cases.items():
            with self.subTest(case=name):
                self.assertEqual(mapping.catalogue_kind(item), expected)

    def test_d115_the_words_read(self):
        stated = ('for hemostasis', 'to control the bleeding', 'the oozing vessel', 'the spurting vessel',
                  'the visible vessel', 'an adherent clot', 'actively bleeding', 'stigmata of recent bleeding',
                  'the bleeding ulcer', 'hemorrhage from the ulcer')
        none = ('hemostatic', 'hemostatic clips', 'the ulcer', 'to prevent bleeding', 'to prevent delayed bleeding',
                'prophylactic hemostasis', 'to ensure hemostasis', 'no active bleeding', 'without bleeding',
                'no active bleeding, oozing or visible vessel', 'the non-bleeding ulcer', "it wasn't bleeding",
                'without stigmata of recent bleeding', 'a previously bleeding ulcer', 'if bleeding recurs',
                'nonbleeding', '')
        for text in stated:
            with self.subTest(stated=text):
                self.assertTrue(mapping.bleeding_stated(text))
        for text in none:
            with self.subTest(none=text):
                self.assertFalse(mapping.bleeding_stated(text))

    def test_d115_a_removals_adjunct_is_not_listed_and_its_code_is_held(self):
        result = assessed(ADJUNCT)
        reading = events.Reading.of(built(ADJUNCT)[0])
        with self.subTest(part='read as the bleeding control, it is part of the removal: not doubted'):
            self.assertEqual((reading.events['E2']['catalogue_kind'], coverage.doubted(reading, reading.events['E2'])),
                             (mapping.POSSIBLE_BLEEDING_CONTROL, False))
            self.assertNotIn(mapping.POSSIBLE_BLEEDING_CONTROL, [act for act, _ in items(result)])
        ready(self, result, '43251')
        held(self, result, '43255', ['performed_status'])

    def test_d115_an_unanchored_time_is_still_asked_at_service_scope(self):
        """1caaf0609 asked 43255's event_time (h4 over the bleeding control it read). The bleeding control in doubt is
        matched by no code, so 43255 is held not documented, and the act's own time question is asked of the service
        (coverage.in_doubt_questions over the doubted act): the genuine question is never dropped."""
        inv, _ = built(D1_TIME)
        clipped = events.Reading.of(inv).events['E2']
        self.assertEqual((clipped['catalogue_kind'], events.usable(clipped, 'time')),
                         (mapping.POSSIBLE_BLEEDING_CONTROL, False))
        result = assessed(D1_TIME)
        held(self, result, '43255', ['performed_status'])
        self.assertEqual(service_facts(result), ['event_time'])

    def test_d115_recorded_cost_bleeding_stated_only_for_the_lesion_is_not_read(self):
        """Gap D's D3: the lesion's own description states the oozing vessel ("A 12 mm ulcer with an oozing visible
        vessel ..."), the clip's own words do not. catalogue_kind reads the event alone, so the act stays in doubt and
        43255 is held - as c2e53f8e holds it, where 1caaf0609 READYs it (the design's "or for its lesion"; recorded)."""
        inv, _ = built(D3)
        self.assertEqual(events.Reading.of(inv).events['E2']['catalogue_kind'], mapping.POSSIBLE_BLEEDING_CONTROL)
        held(self, assessed(D3), '43255', ['performed_status'])


# --- D116 (gap A): an EGD stent removal or exchange is a reportable act of its session ------------------------------------

REMOVED_STENT = 'The fully covered esophageal stent was removed by its retrieval loop without difficulty.'
EXCHANGED_STENT = 'The esophageal stent was exchanged for a new 18 mm fully covered esophageal stent across the stricture.'
RESOLVED = 'The underlying esophageal stricture had resolved, and the stomach and duodenum were normal.'
STENT_REMOVAL = event('E2', EGD, at('stent_removal', 'was removed', ['P6']), status=at('performed', 'was removed', ['P6']),
                      technique=at('other', 'retrieval loop', ['P6']), target=tgt('', 'esophagus', 'esophageal', ['P6']),
                      purpose=at('removal', 'removed', ['P6']))
A1 = case('d116_a1', report(P5=ADV, P6=REMOVED_STENT, P7=RESOLVED), [examination(), STENT_REMOVAL], [('43235', (ADV,))])
A3 = case('d116_a3', report(P5=ADV, P6=EXCHANGED_STENT, P7=RESOLVED),
          [examination(), event('E2', EGD, at('stent_exchange', 'was exchanged', ['P6']),
                                status=at('performed', 'was exchanged', ['P6']),
                                technique=at('stent', 'fully covered esophageal stent', ['P6']),
                                target=tgt('', 'esophagus', 'esophageal', ['P6']))],
          [('43235', (ADV,))])
POSSIBLY_REMOVED = 'The fully covered esophageal stent was possibly removed by its retrieval loop.'
A1_DOUBT = case('d116_a1_uncertain', report(P5=ADV, P6=POSSIBLY_REMOVED, P7=RESOLVED),
                [examination(), event('E2', EGD, at('stent_removal', 'removed', ['P6']),
                                      status=at('uncertain', 'was possibly removed', ['P6']),
                                      target=tgt('', 'esophagus', 'esophageal', ['P6']))],
                [('43235', (ADV,))])
COLON_STENT = 'The colonic stent in the sigmoid colon was removed with a snare.'
A_COLON = case('d116_colonoscopy', report('COLONOSCOPY REPORT', P5='The colonoscope was advanced to the cecum.',
                                          P6=COLON_STENT),
               [event('E1', at('colonoscopy', 'COLONOSCOPY', ['P2']), at('examination', 'The colonoscope was advanced',
                                                                         ['P5']),
                      technique=at('endoscope', 'colonoscope', ['P5']), status=at('performed', 'was advanced', ['P5'])),
                event('E2', at('colonoscopy', 'COLONOSCOPY', ['P2']), at('stent_removal', 'was removed', ['P6']),
                      status=at('performed', 'was removed', ['P6']),
                      target=tgt('', 'sigmoid_colon', 'in the sigmoid colon', ['P6']))],
               [('45378', ('The colonoscope was advanced to the cecum.',))], reach=('E1', 'cecum', 'cecum', 'P5'))


class D116StentRemovalAndExchange(SimpleTestCase):
    """D116: c2e53f8e holds 43235 base_included beside an EGD stent act; 1caaf0609 read stent_removal and stent_exchange
    as no act of the EGD and gave 43235 READY."""

    def test_d116_gap_a1_a_stent_removal_holds_43235(self):
        result = assessed(A1)
        with self.subTest(part='a reportable act of the EGD'):
            self.assertEqual(session_labels(result), (['stent removal'], []))
        held_base(self, result, '43235', 'stent removal')

    def test_d116_gap_a3_a_stent_exchange_holds_43235(self):
        result = assessed(A3)
        self.assertEqual(session_labels(result), (['stent exchange'], []))
        held_base(self, result, '43235', 'stent exchange')

    def test_d116_a_stent_removal_in_doubt_holds_43235(self):
        result = assessed(A1_DOUBT)
        self.assertEqual(session_labels(result), ([], ['stent removal']))
        held_base(self, result, '43235', 'stent removal (stated in doubt)')

    def test_d116_in_every_family_that_places_a_stent(self):
        result = assessed(A_COLON)
        self.assertEqual(session_labels(result, 'gi.colonoscopy'), (['stent removal'], []))
        held_base(self, result, '45378', 'stent removal')
        with self.subTest(part='the families'):
            reading = events.Reading.of(built(A1)[0])
            removal = reading.events['E2']
            self.assertEqual({family: coverage.reportable_kind({**removal, 'family': family}) for family in
                              ('gi.egd', 'gi.enteroscopy', 'gi.colonoscopy', 'gi.flex_sig', 'gi.ercp', 'gi.eus')},
                             {'gi.egd': True, 'gi.enteroscopy': True, 'gi.colonoscopy': True, 'gi.flex_sig': True,
                              'gi.ercp': True, 'gi.eus': False})


# --- D117 (gap B): a positive removal of unstated method is a doubted act of its session ----------------------------------

GASTRIC_POLYP = 'A 7 mm sessile polyp was seen in the gastric body.'
POLYPECTOMY = 'A polypectomy of the gastric body polyp was performed.'
BIOPSIES = 'Biopsies of the gastric antrum were taken with cold forceps.'
GASTRIC_LESION = lesion('L1', '7 mm sessile polyp', 'gastric_body', 'gastric body', '7 mm', ['P6', 'P7'])
UMBRELLA = event('E2', EGD, at('removal', 'polypectomy', ['P7']), status=at('performed', 'was performed', ['P7']),
                 target=tgt('L1', 'gastric_body', 'the gastric body polyp', ['P7']),
                 purpose=at('removal', 'polypectomy', ['P7']))
B1 = case('d117_b1', report(P5=ADV, P6=GASTRIC_POLYP, P7=POLYPECTOMY, P8=NORMAL), [examination(), UMBRELLA],
          [('43235', (ADV,))], lesions=[GASTRIC_LESION])
B2 = case('d117_b2', report(P5=ADV, P6=GASTRIC_POLYP, P7=POLYPECTOMY, P8=NORMAL), [examination(), UMBRELLA],
          [('43235', (ADV,)), ('43251', (POLYPECTOMY,))], lesions=[GASTRIC_LESION])
REMOVED = 'The gastric body polyp was removed.'
B3 = case('d117_b3', report(P5=ADV, P6=GASTRIC_POLYP, P7=REMOVED, P8=NORMAL),
          [examination(), event('E2', EGD, at('removal', 'was removed', ['P7']), status=at('performed', 'was removed',
                                                                                         ['P7']),
                                target=tgt('L1', 'gastric_body', 'The gastric body polyp', ['P7']),
                                purpose=at('removal', 'removed', ['P7']))],
          [('43235', (ADV,))], lesions=[GASTRIC_LESION])
B4 = case('d117_b4', report(P5=ADV, P6=GASTRIC_POLYP, P7=POLYPECTOMY, P8=BIOPSIES),
          [examination(), UMBRELLA,
           event('E3', EGD, at('biopsy', 'Biopsies', ['P8']), status=at('performed', 'were taken', ['P8']),
                 technique=at('cold_forceps', 'cold forceps', ['P8']),
                 target=tgt('', 'gastric_antrum', 'the gastric antrum', ['P8']))],
          [('43239', (BIOPSIES,))], lesions=[GASTRIC_LESION])
COLON = at('colonoscopy', 'COLONOSCOPY', ['P2'])
CECUM = 'The colonoscope was advanced to the cecum.'
COLON_EXAM = event('E1', COLON, at('examination', 'The colonoscope was advanced', ['P5']),
                   technique=at('endoscope', 'colonoscope', ['P5']), status=at('performed', 'was advanced', ['P5']))
SIGMOID_POLYPECTOMY = 'A polypectomy of the 5 mm sigmoid polyp was performed.'
B_COLON = case('d117_colonoscopy', report('COLONOSCOPY REPORT', P5=CECUM, P6=SIGMOID_POLYPECTOMY),
               [COLON_EXAM, event('E2', COLON, at('removal', 'polypectomy', ['P6']),
                                  status=at('performed', 'was performed', ['P6']),
                                  target=tgt('L1', 'sigmoid_colon', 'the 5 mm sigmoid polyp', ['P6']),
                                  purpose=at('removal', 'polypectomy', ['P6']))],
               [('45378', (CECUM,))], lesions=[lesion('L1', '5 mm sigmoid polyp', 'sigmoid_colon', 'sigmoid', '5 mm',
                                                       ['P6'])],
               reach=('E1', 'cecum', 'cecum', 'P5'))
HISTORY_REMOVAL = 'A 4 mm rectal polyp was removed at her colonoscopy in January 2024.'
B_HISTORY = case('d117_history', report('COLONOSCOPY REPORT', P5=CECUM, P6=HISTORY_REMOVAL),
                 [COLON_EXAM, event('E2', COLON, at('removal', 'was removed', ['P6']),
                                    status=at('performed', 'was removed', ['P6']),
                                    time=at('earlier_encounter', 'in January 2024', ['P6']),
                                    target=tgt('', 'rectum', 'A 4 mm rectal polyp', ['P6']),
                                    purpose=at('removal', 'removed', ['P6']))],
                 [('45378', (CECUM,))], reach=('E1', 'cecum', 'cecum', 'P5'))


class D117RemovalOfUnstatedMethod(SimpleTestCase):
    """D117: c2e53f8e reads a snare in "A polypectomy ... was performed." and holds 43235 base_included; 1caaf0609 read
    the umbrella as no act at all: 43235 READY with coding complete, and beside 43239 the polypectomy was invisible."""

    def test_d117_gap_b1_a_polypectomy_of_unstated_method_holds_43235_and_is_listed_in_doubt(self):
        result = assessed(B1)
        with self.subTest(part='a doubted act of the EGD'):
            self.assertEqual(session_labels(result), ([], ['removal']))
        held_base(self, result, '43235', 'removal (stated in doubt)')
        with self.subTest(part='listed in doubt, with the method question'):
            self.assertEqual(items(result), [('removal', 'in_doubt')])
            self.assertEqual(service_facts(result), ['act_method'])

    def test_d117_gap_b4_beside_43239_the_polypectomy_is_never_invisible(self):
        result = assessed(B4)
        ready(self, result, '43239')
        with self.subTest(part='coding is not complete: the removal is listed in doubt and its method asked'):
            self.assertEqual(items(result), [('removal', 'in_doubt')])
            self.assertEqual(service_facts(result), ['act_method'])
            self.assertEqual(result.completeness['state'], 'incomplete')

    def test_d117_gap_b3_was_removed_holds_43235(self):
        held_base(self, assessed(B3), '43235', 'removal (stated in doubt)')

    def test_d117_control_b2_a_method_code_beside_it_asks_the_method(self):
        result = assessed(B2)
        held(self, result, '43251', ['act_method'])
        held_base(self, result, '43235', '43251')
        with self.subTest(part='the code reads the removal: no second item or question'):
            self.assertEqual((items(result), service_facts(result)), ([], []))

    def test_d117_the_colonoscopy_base_code_too(self):
        result = assessed(B_COLON)
        self.assertEqual(session_labels(result, 'gi.colonoscopy'), ([], ['removal']))
        held_base(self, result, '45378', 'removal (stated in doubt)')

    def test_d117_d115_the_families_and_the_frame_of_a_doubted_act(self):
        """D117's umbrella and D115's bleeding control in doubt are doubted acts only in a family whose catalogue acts
        hold such an act (a removal method; the bleeding control) - never in the ERCP's or the EUS's - and only when stated
        positive or uncertain and not verified at another time or by another performer."""
        umbrella = events.Reading.of(built(B1)[0])
        doubted_clip = events.Reading.of(built(D1)[0])
        other = {'value': 'other_clinician', 'state': 'verified', 'open': False, 'basis': 'stated'}
        earlier = {'value': 'earlier_encounter', 'state': 'verified', 'open': False, 'basis': 'stated'}
        denied = {'value': 'not_performed', 'state': 'verified', 'open': False, 'basis': 'stated'}
        uncertain = {'value': 'uncertain', 'state': 'verified', 'open': False, 'basis': 'stated'}
        for name, reading in (('removal', umbrella), ('possible bleeding control', doubted_clip)):
            item = reading.events['E2']
            found = {variant: coverage.doubted(reading, changed) for variant, changed in (
                ('as stated', item), ('ERCP', {**item, 'family': 'gi.ercp'}), ('EUS', {**item, 'family': 'gi.eus'}),
                ('colonoscopy', {**item, 'family': 'gi.colonoscopy'}), ('another performer', {**item, 'performer': other}),
                ('another time', {**item, 'time': earlier}), ('denied', {**item, 'status': denied}),
                ('uncertain', {**item, 'status': uncertain}))}
            with self.subTest(act=name):
                self.assertEqual(found, {'as stated': True, 'ERCP': False, 'EUS': False, 'colonoscopy': True,
                                         'another performer': False, 'another time': False, 'denied': False,
                                         'uncertain': True})

    def test_d117_control_a_removal_at_another_encounter_is_no_doubt(self):
        result = assessed(B_HISTORY)
        self.assertEqual(session_labels(result, 'gi.colonoscopy'), ([], []))
        ready(self, result, '45378')


# --- D118 (gap C): two dilation codes of different techniques for one stricture compete ------------------------------------

STRICTURE = 'A benign-appearing peptic stricture was seen in the distal esophagus at 37 cm.'
BALLOON = 'The stricture was dilated with a through-the-scope balloon to 15 mm.'
SAVARY = 'The stricture was then dilated with a Savary dilator passed over a guidewire to 17 mm.'
GASTRIC_NORMAL = 'The stomach and duodenum were normal.'
STRICTURE_LESION = lesion('L1', 'benign-appearing peptic stricture', 'distal_esophagus', 'distal esophagus', '', ['P6'])


def dilation(eid: str, passage: str, device: str, device_words: str, *, status_words: str, target=None, time=None,
             kind_words: str = 'dilated') -> dict:
    return event(eid, EGD, at('dilation', kind_words, [passage]), status=at('performed', status_words, [passage]),
                 technique=at(device, device_words, [passage]),
                 target=target if target is not None else tgt('L1', 'distal_esophagus', 'The stricture', [passage]),
                 time=time)


C1 = case('d118_c1', report(P5=ADV, P6=STRICTURE, P7=BALLOON, P8=SAVARY, P9=GASTRIC_NORMAL),
          [examination(), dilation('E2', 'P7', 'balloon', 'through-the-scope balloon', status_words='was dilated'),
           dilation('E3', 'P8', 'wire_bougie', 'Savary dilator passed over a guidewire', status_words='was then dilated')],
          [('43249', (BALLOON,)), ('43248', (SAVARY,))], lesions=[STRICTURE_LESION])
DISTAL_BALLOON = 'The distal esophagus was dilated with a through-the-scope balloon to 15 mm.'
MID_SAVARY = 'The mid esophagus was dilated with a Savary dilator passed over a guidewire to 17 mm.'
C_TWO_SITES = case('d118_two_sites', report(P5=ADV, P6=DISTAL_BALLOON, P7=MID_SAVARY, P8=GASTRIC_NORMAL),
                   [examination(),
                    dilation('E2', 'P6', 'balloon', 'through-the-scope balloon', status_words='was dilated',
                             target=tgt('', 'distal_esophagus', 'The distal esophagus', ['P6'])),
                    dilation('E3', 'P7', 'wire_bougie', 'Savary dilator passed over a guidewire',
                             status_words='was dilated', target=tgt('', 'mid_esophagus', 'The mid esophagus', ['P7']))],
                   [('43249', (DISTAL_BALLOON,)), ('43248', (MID_SAVARY,))])
SAVARY_UNPLACED = 'A Savary dilator was then passed over a guidewire to 17 mm.'
C_UNREAD = case('d118_savary_site_unread', report(P5=ADV, P6=STRICTURE, P7=BALLOON, P8=SAVARY_UNPLACED,
                                                  P9=GASTRIC_NORMAL),
                [examination(), dilation('E2', 'P7', 'balloon', 'through-the-scope balloon', status_words='was dilated'),
                 dilation('E3', 'P8', 'wire_bougie', 'Savary dilator', status_words='was then passed',
                          kind_words='Savary dilator', target=tgt())],
                [('43249', (BALLOON,)), ('43248', (SAVARY_UNPLACED,))], lesions=[STRICTURE_LESION])
PYLORUS = 'A pyloric channel stricture was seen.'
PYLORIC_BALLOON = 'The pyloric stricture was dilated with a through-the-scope balloon to 15 mm.'
C_PYLORUS = case('d118_one_dilation_any_technique_code', report(P5=ADV, P6=PYLORUS, P7=PYLORIC_BALLOON, P8=NORMAL),
                 [examination(), dilation('E2', 'P7', 'balloon', 'through-the-scope balloon', status_words='was dilated',
                                          target=tgt('L1', 'pylorus', 'The pyloric stricture', ['P7']))],
                 [('43245', (PYLORIC_BALLOON,)), ('43249', (PYLORIC_BALLOON,))],
                 lesions=[lesion('L1', 'pyloric channel stricture', 'pylorus', 'pyloric channel', '', ['P6', 'P7'])])
HISTORY_SAVARY = 'In 2024 the stricture had been dilated with a Savary dilator to 15 mm.'
C_HISTORY = case('d118_historical_savary', report(P5=ADV, P6=STRICTURE, P7=HISTORY_SAVARY, P8=BALLOON,
                                                  P9=GASTRIC_NORMAL),
                 [examination(),
                  dilation('E2', 'P8', 'balloon', 'through-the-scope balloon', status_words='was dilated'),
                  dilation('E3', 'P7', 'wire_bougie', 'Savary dilator', status_words='had been dilated',
                           time=at('earlier_encounter', 'In 2024', ['P7']))],
                 [('43249', (BALLOON,)), ('43248', (HISTORY_SAVARY,))], lesions=[STRICTURE_LESION])
UPPER_STRICTURE = 'A short stricture was seen in the distal esophagus at 32 cm.'
LOWER_STRICTURE = 'A second stricture was seen in the distal esophagus at 37 cm.'
UPPER_BALLOON = 'The stricture at 32 cm was dilated with a through-the-scope balloon to 15 mm.'
LOWER_SAVARY = 'The stricture at 37 cm was dilated with a Savary dilator passed over a guidewire to 17 mm.'
C_DISTINCT = case('d118_two_distinct_strictures',
                  report(P5=ADV, P6=UPPER_STRICTURE, P7=LOWER_STRICTURE, P8=UPPER_BALLOON, P9=LOWER_SAVARY),
                  [examination(),
                   dilation('E2', 'P8', 'balloon', 'through-the-scope balloon', status_words='was dilated',
                            target=tgt('L1', 'distal_esophagus', 'The stricture at 32 cm', ['P8'])),
                   dilation('E3', 'P9', 'wire_bougie', 'Savary dilator passed over a guidewire', status_words='was dilated',
                            target=tgt('L2', 'distal_esophagus', 'The stricture at 37 cm', ['P9']))],
                  [('43249', (UPPER_BALLOON,)), ('43248', (LOWER_SAVARY,))],
                  lesions=[lesion('L1', 'short stricture', 'distal_esophagus', 'distal esophagus at 32 cm', '', ['P6']),
                           lesion('L2', 'second stricture', 'distal_esophagus', 'distal esophagus at 37 cm', '',
                                  ['P7'])])


PYLORIC_BOUGIE = 'The pyloric stricture was then dilated with a Savary dilator passed over a guidewire to 15 mm.'
C_PYLORUS_TWO = case('d118_two_pyloric_dilations', report(P5=ADV, P6=PYLORUS, P7=PYLORIC_BALLOON, P8=PYLORIC_BOUGIE),
                     [examination(),
                      dilation('E2', 'P7', 'balloon', 'through-the-scope balloon', status_words='was dilated',
                               target=tgt('L1', 'pylorus', 'The pyloric stricture', ['P7'])),
                      dilation('E3', 'P8', 'wire_bougie', 'Savary dilator passed over a guidewire',
                               status_words='was then dilated',
                               target=tgt('L1', 'pylorus', 'The pyloric stricture', ['P8']))],
                     [('43245', (PYLORIC_BALLOON, PYLORIC_BOUGIE)), ('43249', (PYLORIC_BALLOON,))],
                     lesions=[lesion('L1', 'pyloric channel stricture', 'pylorus', 'pyloric channel', '',
                                     ['P6', 'P7', 'P8'])])
BALLOON_AGAIN = 'The stricture was then dilated again with the through-the-scope balloon to 18 mm.'
C_TWO_BALLOONS = case('d118_two_balloon_dilations', report(P5=ADV, P6=STRICTURE, P7=BALLOON, P8=BALLOON_AGAIN,
                                                           P9=GASTRIC_NORMAL),
                      [examination(), dilation('E2', 'P7', 'balloon', 'through-the-scope balloon', status_words='was dilated'),
                       dilation('E3', 'P8', 'balloon', 'through-the-scope balloon', status_words='was then dilated again')],
                      [('43249', (BALLOON, BALLOON_AGAIN)), ('43248', (BALLOON_AGAIN,))], lesions=[STRICTURE_LESION])
# FRESH-2 fb07's shape: a balloon dilation of a gastrojejunal anastomotic stricture, placed at the stomach by the
# anatomy entry's own type word (D34): 43245 (any technique) fits and is READY; 43249 is held for its site (D29)
GJ_HISTORY = 'She has a Roux-en-Y gastric bypass with a gastrojejunal anastomosis.'
GJ_STRICTURE = 'A benign-appearing stricture was seen at the gastrojejunal anastomosis.'
GJ_BALLOON = 'The anastomotic stricture was dilated with a through-the-scope balloon to 15 mm.'
C_ANASTOMOSIS = case('d118_fb07_shape', report(P5=ADV, P6=GJ_HISTORY, P7=GJ_STRICTURE, P8=GJ_BALLOON),
                     [examination(),
                      dilation('E2', 'P8', 'balloon', 'through-the-scope balloon', status_words='was dilated',
                               target=tgt('L1', 'anastomosis', 'The anastomotic stricture', ['P8']))],
                     [('43245', (GJ_BALLOON,)), ('43249', (GJ_BALLOON,))],
                     lesions=[lesion('L1', 'benign-appearing stricture', 'anastomosis', 'gastrojejunal anastomosis', '',
                                     ['P7'])],
                     anatomy=[{'state': 'altered', 'landmark': 'anastomosis', 'words': 'gastrojejunal anastomosis',
                               'passages': ['P6']}])


class D118DilationsOfOneStricture(SimpleTestCase):
    """D118: c2e53f8e (its participant harness configured, as production runs it) holds 43249 and 43248 with
    competing_codes for gap C's balloon-then-Savary dilation of one stricture; 1caaf0609 gave both READY."""

    def test_d118_gap_c1_a_balloon_then_a_savary_dilation_of_one_stricture_compete(self):
        result = assessed(C1)
        for code, rival in (('43249', '43248'), ('43248', '43249')):
            p = proposal(result, code)
            with self.subTest(code=code):
                self.assertEqual((p.status, asked(p), p.support.get('competes')),
                                 ('needs_clarification', ['competing_codes'], [rival]))
                self.assertIsNotNone(check(p, COMPETING))
                self.assertEqual(reviewed(result, code).status, 'needs_clarification')
        with self.subTest(part='each code still accounts for its own dilation only'):
            self.assertEqual(([act['id'] for act in proposal(result, '43249').support['acts']],
                              [act['id'] for act in proposal(result, '43248').support['acts']]), (['E2'], ['E3']))

    def test_d118_the_competing_hold_is_released_once_the_other_code_is_rejected(self):
        result = assessed(C1)
        stored = [overlay.stored_from(p) for p in result.proposals]
        rejected = {proposal(result, '43248').key: overlay.Decided('reject')}
        view = overlay.review_view(stored, rejected, completeness=to_jsonable(result.completeness))
        self.assertEqual((view[proposal(result, '43249').key].status,
                          view[proposal(result, '43249').key].released), ('ready', (combination.COMPETING_FACT,)))

    def test_d118_a_savary_dilation_whose_site_is_unread_competes(self):
        result = assessed(C_UNREAD)
        held(self, result, '43249', ['competing_codes'])
        p = proposal(result, '43248')
        self.assertEqual((p.status, asked(p)), ('needs_clarification', ['act_target', 'competing_codes']))

    def test_d118_control_dilations_at_two_places_verifiably_apart_do_not_compete(self):
        result = assessed(C_TWO_SITES)
        ready(self, result, '43249')
        ready(self, result, '43248')

    def test_d118_control_two_strictures_verified_distinct_do_not_compete(self):
        inv, _ = built(C_DISTINCT)
        with self.subTest(part='the two lesions are distinct (their distances)'):
            self.assertIn('L2', events.Reading.of(inv).lesions['L1']['distinct_from'])
        result = assessed(C_DISTINCT)
        ready(self, result, '43249')
        ready(self, result, '43248')

    def test_d118_control_a_code_of_any_technique_beside_a_code_held_for_its_site(self):
        result = assessed(C_PYLORUS)
        ready(self, result, '43245')
        held(self, result, '43249', ['act_target'])

    def test_d118_control_a_code_held_for_its_site_claims_nothing_of_another_codes_stricture(self):
        result = assessed(C_PYLORUS_TWO)
        ready(self, result, '43245')
        held(self, result, '43249', ['act_target'])

    def test_d118_control_a_code_of_another_technique_than_every_dilation_claims_nothing(self):
        result = assessed(C_TWO_BALLOONS)
        ready(self, result, '43249')
        held(self, result, '43248', ['technique'])

    def test_d118_control_fb07_shape_an_act_is_never_paired_with_itself(self):
        result = assessed(C_ANASTOMOSIS)
        with self.subTest(part='the anastomosis takes the stomach (D34): the any-technique code fits'):
            self.assertEqual(proposal(result, '43249').support['reason'], 'site')
        ready(self, result, '43245')
        held(self, result, '43249', ['act_target'])

    def test_d118_control_a_dilation_at_another_encounter_claims_nothing(self):
        result = assessed(C_HISTORY)
        ready(self, result, '43249')
        p = proposal(result, '43248')
        self.assertNotIn('competing_codes', asked(p))
        self.assertEqual(p.status, 'needs_clarification')


# --- D119 (gap H): a PEG filed under the feeding tube is an act of the EGD done with it too ------------------------------

PEG_TITLE = 'UPPER ENDOSCOPY WITH PEG PLACEMENT'
TRANSILLUMINATED = 'The anterior gastric wall was transilluminated and the site was confirmed by finger indentation.'
PEG_PLACED = 'A 20 Fr pull-type PEG tube was placed under endoscopic guidance without difficulty.'
OTHERWISE = 'The esophagus, stomach and duodenum were otherwise normal.'


def peg_case(name: str, codes, *, procedure=None, status=None, time=None, line: str = PEG_PLACED) -> str:
    """Gap H's document: an EGD (E1) and a PEG (E2) placed during it, Gemini filing the PEG under ``procedure`` (the
    feeding-tube procedure, worded 'PEG' from the heading, by default)."""
    lines = report(PEG_TITLE, P5=ADV, P6=TRANSILLUMINATED, P7=line, P8=OTHERWISE)
    exam = event('E1', at('egd', 'UPPER ENDOSCOPY', ['P2']), at('examination', 'The gastroscope was advanced', ['P5']),
                 technique=at('endoscope', 'gastroscope', ['P5']), status=at('performed', 'was advanced', ['P5']))
    peg = event('E2', procedure or at('feeding_tube', 'PEG', ['P2']), at('peg', 'PEG tube was placed', ['P7']),
                status=status or at('performed', 'was placed', ['P7']), technique=at('other', 'pull-type', ['P7']),
                target=tgt('', 'stomach', 'anterior gastric wall', ['P6']), time=time)
    return case(name, lines, [exam, peg], codes)


H2 = peg_case('d119_h2', [('43235', (ADV,))])
H1 = peg_case('d119_h1', [('43235', (ADV,)), ('43246', (PEG_PLACED,))])
H3 = peg_case('d119_h3', [('43235', (ADV,))], procedure=at('egd', 'UPPER ENDOSCOPY', ['P2']))
PEG_DOUBT_LINE = 'A 20 Fr pull-type PEG tube was possibly placed under endoscopic guidance.'
H_DOUBT = peg_case('d119_doubted', [('43235', (ADV,))], status=at('uncertain', 'was possibly placed', ['P7']),
                   line=PEG_DOUBT_LINE)
PEG_HISTORY_LINE = 'A 20 Fr pull-type PEG tube was placed under endoscopic guidance in 2023.'
H_HISTORY = peg_case('d119_history', [('43235', (ADV,))], line=PEG_HISTORY_LINE,
                     time=at('earlier_encounter', 'in 2023', ['P7']))


class D119PegUnderTheFeedingTube(SimpleTestCase):
    """D119: c2e53f8e reads a PEG placed during an upper endoscopy as that endoscopy's act and holds 43235
    base_included; 1caaf0609 read Gemini's feeding-tube PEG in its own session and gave 43235 READY."""

    def test_d119_gap_h2_a_feeding_tube_peg_beside_the_egd_holds_43235(self):
        result = assessed(H2)
        with self.subTest(part='the PEG stays the feeding-tube session\'s act'):
            self.assertEqual(session_labels(result, 'gi.feeding_tube'), (['gastrostomy (PEG) placement'], []))
            self.assertEqual(session_labels(result), ([], []))
        held_base(self, result, '43235', 'gastrostomy (PEG) placement')

    def test_d119_gap_h1_43235_beside_43246_stays_held(self):
        result = assessed(H1)
        p = proposal(result, '43235')
        self.assertEqual((p.status, asked(p)), ('needs_clarification', ['base_included']))

    def test_d119_a_doubted_feeding_tube_peg_holds_43235(self):
        held_base(self, assessed(H_DOUBT), '43235', 'gastrostomy (PEG) placement (stated in doubt)')

    def test_d119_control_a_peg_under_the_egd_holds_as_before(self):
        held_base(self, assessed(H3), '43235', 'gastrostomy (PEG) placement')

    def test_d119_control_a_peg_at_another_encounter_holds_nothing(self):
        ready(self, assessed(H_HISTORY), '43235')

    def test_d119_the_cross_family_reading_is_the_egd_base_codes_and_the_peg_kind_only(self):
        coding = {'sessions': {'gi.egd': {'reportable': [], 'doubted': []},
                               'gi.feeding_tube': {'reportable': [{'kind': 'peg', 'label': 'gastrostomy (PEG) placement'},
                                                                  {'kind': 'tube_replacement',
                                                                   'label': 'feeding-tube replacement'}],
                                                   'doubted': []},
                               'gi.colonoscopy': {'reportable': [], 'doubted': []}}}
        self.assertEqual(combination.base_included([('43235', 'gi.egd', 'gi.egd'), ('45378', 'gi.colonoscopy',
                                                                                    'gi.colonoscopy')], coding),
                         (('43235', ('gastrostomy (PEG) placement',)),))
