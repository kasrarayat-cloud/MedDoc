"""DECISIONS D109 (the round-4 refutation of 437b708bb, findings 13, 23, 14, 15 and 16), SYNTHETIC: the same-day E/M
rule reads an act by its kind, places an act "earlier in the day" on the date of service, and counts a non-GI or
unidentified act only as an act of this encounter.

- Findings 13 and 23: an in-office band ligation (and an anoscopy) that Gemini files under the visit (procedure
  office_em: the note's only heading is the visit's) had family gi.office_em, outside SAME_DAY_FAMILIES, so it made no
  procedure day and 99213 was READY - c2e53f8e holds it with separate_em ("Other GI service is documented as performed
  on the same date"). An act of a procedural KIND (combination.SAME_DAY_KINDS) now counts as another GI service
  whatever family Gemini gave it, when its time is current_encounter (any state) or its own words place it on the
  date.
- Finding 14: facts.day_of read "earlier in the day", "Earlier that day" and "Earlier in the morning" (a verified
  earlier_encounter time: an endoscopy at its own encounter earlier on the same date) as OFF the date, so 99213 was
  READY beside it; c2e53f8e holds it with separate_em. lexicon.SAME_DAY_FRAMES, read whole as D54 reads a current
  time's words, place such an act ON the date - DECISIONS D112: only frames anchored to today, so the anaphoric
  "Earlier that day" (G2) is OFF again (tests/test_interpretation_r5_em.py pins it).
- Findings 15 and 16 (D94 narrowed): an act of gi.unsupported or of no family counts only when its time is
  current_encounter (any state) and its performer is not verified to another clinician or facility. A CT "interpreted
  separately by the radiology service" (fb13's attested shape) asked separate_em, and an abdominal ultrasound named in
  the indication with an undatable earlier time (fb14's) asked event_time, where c2e53f8e is READY. D94's own pins (the
  office excision and the unidentified act, tests/test_interpretation_r3_integration_d90_d92_d94.py) still ask.

Each fixture is a synthetic Gemini answer over a synthetic document (fictional patients), read by read.read, normalized
with the real linked steps and assessed through assess.assess with a synthetic Corti response citing the document's own
words (the S08 builders). Each pin carries controls - what D109 must NOT move. Nothing is sent."""
from __future__ import annotations

from django.test import SimpleTestCase

from studio.gi import catalogue, profiles
from studio.interpretation import combination, events, facts, lexicon, mapping, schema
from studio.validation import checks
from tests.test_interpretation_events import asked, check, inventory, proposal, run
from tests.test_interpretation_identity import a, act, tg
from tests.test_interpretation_r3_families import (BANDING, MEMBER, OFFICE, PLAN, TIME, VISIT, banding, visit,
                                                   visit_facts)

DAY = '2026-11-09'
OTHER_GI_LABEL = profiles.PROFILES['gi.other'].label  # 'Other GI service'
SEPARATE = 'a significant, separately identifiable E/M service is not established'


def held_for_separate_em(test, p, label: str):
    """99213 held on a procedure day: separate_em asked, em.same_day_procedure naming ``label``, the modifier 25
    consideration shown and no 'no same-day procedure' check."""
    test.assertEqual((p.bucket, p.status, asked(p)), ('selected', 'needs_clarification', ['separate_em']))
    same_day = check(p, 'em.same_day_procedure')
    test.assertEqual(same_day.status, 'warn')
    test.assertIn(f'{label} is ', same_day.detail)
    test.assertIn(SEPARATE, p.clarifications[0].reason)
    test.assertIsNone(check(p, 'em.same_day_coverage'))
    test.assertIn(checks.SEPARATE_EM_CONSIDERATION, p.modifier_considerations)


def ready_with_no_procedure_day(test, p):
    """99213 READY with its member values: no question, no procedure day ('No same-day procedure is documented')."""
    test.assertEqual((p.bucket, p.status, asked(p)), ('selected', 'ready', []))
    test.assertEqual(check(p, 'em.same_day_coverage').status, 'not_verified')
    test.assertIsNone(check(p, 'em.same_day_procedure'))
    test.assertNotIn(checks.SEPARATE_EM_CONSIDERATION, p.modifier_considerations)


def em(inv, text, visit_line=VISIT, user_values=MEMBER):
    return proposal(run(inv, text, [('99213', visit_line)], user_values=user_values), '99213')


def day_of(inv, eid='E1'):
    return facts.day_of(events.Reading.of(inv).events[eid], DAY)


def procedure_day(inv):
    return combination.procedure_day(events.Reading.of(inv), DAY)


# --- findings 13 and 23: an act of a procedural kind, whatever its family ---------------------------------------------

HEADING = 'GASTROENTEROLOGY OFFICE VISIT'
ESTABLISHED = 'Established patient seen today for rectal bleeding.'
ANOSCOPY = 'Anoscopy showed grade 2 internal hemorrhoids.'
HEADED = {'H1': HEADING, 'V1': ESTABLISHED, 'V2': TIME, 'P1': ANOSCOPY, 'P2': BANDING, 'P3': PLAN}  # finding 13's text


def headed_visit() -> dict:
    """Finding 13's E0: the visit, its procedure office_em named by the heading's 'OFFICE VISIT'."""
    return act('E0', 'V1', 'em_visit', 'Established patient', status_words='seen today',
               procedure=a('office_em', 'OFFICE VISIT', ['H1']))


def under_the_visit(words: str = HEADING, passages=('H1',), procedure: str = 'office_em') -> dict:
    """A procedure attribute that files an act under the visit: office_em (or ``procedure``) with the heading's words,
    or with ``words`` in ``passages``; no words at all with words ''."""
    return a(procedure, words, list(passages) if words else [])


def headed_anoscopy(procedure=None) -> dict:
    """Finding 13's E1: the anoscopy, an examination filed under the visit."""
    return act('E1', 'P1', 'examination', 'Anoscopy', status_words='showed',
               procedure=procedure if procedure is not None else under_the_visit())


def headed_banding(procedure=None, **changes) -> dict:
    """Finding 13's E2: the band ligation filed under the visit, performed, current 'today', at the anal canal."""
    changes.setdefault('time', a('current_encounter', 'today', ['P2']))
    changes.setdefault('target', tg('', 'anal_canal', 'one internal hemorrhoid', ['P2']))
    return act('E2', 'P2', 'band_ligation', 'Rubber band ligation', status_words='was performed',
               procedure=procedure if procedure is not None else under_the_visit(), **changes)


def headed_note(*acts, lines=None, drop=()):
    """(inventory, text) of finding 13's note: the visit E0 beside ``acts``, the lines ``drop`` names removed."""
    kept = {pid: line for pid, line in {**HEADED, **(lines or {})}.items() if pid not in drop}
    return inventory(kept, events=[headed_visit(), *acts], visits=[visit_facts()])


def office_note(*acts, lines=None):
    """D81's office note (tests/test_interpretation_r3_families OFFICE): the visit E0 beside ``acts``."""
    return inventory({**OFFICE, **(lines or {})}, events=[visit(), *acts], visits=[visit_facts()])


class D109ProceduralKindWhateverItsFamily(SimpleTestCase):
    """D109 (findings 13 and 23): an act of a procedural kind makes a procedure day whatever procedure Gemini filed it
    under - office_em, em_other or sedation included."""

    def test_d109_the_procedural_kinds_are_every_act_a_procedural_family_lists(self):
        """SAME_DAY_KINDS: every kind a procedural family's catalogue entry lists (acts, bundled and unsupported acts),
        the examination kinds and the umbrellas - every schema kind but the visit's, prolonged visit time, moderate
        sedation and 'other'. The families an act counts by its kind are exactly those outside SAME_DAY_FAMILIES, and
        D81's families are unchanged."""
        self.assertEqual(set(schema.KINDS) - combination.SAME_DAY_KINDS,
                         {'em_visit', 'em_prolonged', 'moderate_sedation', 'other'})
        self.assertEqual(combination.SAME_DAY_KINDS - set(schema.KINDS), {mapping.EUS_EXAMINATION})
        for family in lexicon.PROCEDURAL_FAMILIES:
            entry = catalogue.CATALOGUE[family]
            listed = set(entry.acts) | {kind for kind, _ in entry.bundled + entry.unsupported_acts}
            with self.subTest(family=family):
                self.assertLessEqual(listed & set(mapping.CATALOGUE_KINDS), combination.SAME_DAY_KINDS)
        for kind in ('band_ligation', 'biopsy', 'removal', 'injection', 'examination', 'intervention', 'clip',
                     'cannulation', 'balloon_expulsion', 'esd'):
            self.assertIn(kind, combination.SAME_DAY_KINDS)
        self.assertEqual(combination.CURRENT_ONLY_FAMILIES, {'gi.unsupported', ''})
        outside = {slug for slug in profiles.PROFILES if slug not in combination.SAME_DAY_FAMILIES}
        self.assertEqual(outside, {'gi.office_em', 'gi.em_other', 'gi.sedation'})

    def test_d109_finding_13_the_headed_office_note_asks_separate_em(self):
        """Finding 13's exact input: the anoscopy (E1) and the banding (E2) both filed under the visit's heading
        ('GASTROENTEROLOGY OFFICE VISIT'), Corti proposing 99213 alone. 437b708bb: READY, 'No same-day procedure is
        documented'; c2e53f8e: held, separate_em, 'Other GI service is documented as performed on the same date'. With
        no member values it asks setting, patient_status and separate_em (437b708bb: the first two only)."""
        inv, text = headed_note(headed_anoscopy(), headed_banding())
        self.assertEqual({eid: events.Reading.of(inv).events[eid]['family'] for eid in ('E1', 'E2')},
                         {'E1': 'gi.office_em', 'E2': 'gi.office_em'})
        self.assertEqual(procedure_day(inv).labels, (OTHER_GI_LABEL,))
        held_for_separate_em(self, em(inv, text, ESTABLISHED), OTHER_GI_LABEL)
        p = em(inv, text, ESTABLISHED, user_values=None)
        self.assertEqual((p.status, sorted(asked(p))), ('needs_clarification', ['patient_status', 'separate_em',
                                                                               'setting']))

    def test_d109_finding_13_its_variants(self):
        """Finding 13's other variants, each READY at 437b708bb and held at c2e53f8e: the banding alone (the anoscopy
        line removed); the banding with NO procedure words (its procedure unverified, procedure_unsettled - a possible
        same-day procedure, never an absence: D62, D75); filed em_other or sedation; and the anoscopy alone - an
        endoscopic examination."""
        no_anoscopy = ('P1',)
        variants = (
            ('the banding alone, the anoscopy line removed', [headed_banding()], no_anoscopy, 'labels'),
            ('the banding with no procedure words', [headed_banding(under_the_visit(''))], no_anoscopy, 'possible'),
            ('em_other, no words', [headed_banding(under_the_visit('', procedure='em_other'))], no_anoscopy,
             'possible'),
            ('sedation, no words', [headed_banding(under_the_visit('', procedure='sedation'))], no_anoscopy,
             'possible'),
            ('the anoscopy alone', [headed_anoscopy()], ('P2',), 'labels'),
        )
        for label, acts, drop, listed in variants:
            with self.subTest(label):
                inv, text = headed_note(*acts, drop=drop)
                self.assertEqual(getattr(procedure_day(inv), listed), (OTHER_GI_LABEL,))
                held_for_separate_em(self, em(inv, text, ESTABLISHED), OTHER_GI_LABEL)

    def test_d109_finding_23_d81s_office_banding_filed_under_the_visit(self):
        """Finding 23: D81's own office note with the banding's procedure office_em - its own words 'office' (which
        verify), the visit's 'Office visit', or a heading's 'GASTROENTEROLOGY OFFICE VISIT' - and em_other. 437b708bb:
        READY, no modifier 25 consideration; c2e53f8e: held, separate_em. D81's pinned other_gi banding still asks."""
        variants = (
            ("its own words 'office'", banding(procedure=a('office_em', 'office', ['P2'])), {}),
            ("the visit's words 'Office visit'", banding(procedure=a('office_em', 'Office visit', ['V1'])), {}),
            ("a heading's words", banding(procedure=a('office_em', HEADING, ['H1'])), {'H1': HEADING}),
            ('em_other with no words', banding(procedure=a('em_other')), {}),
            ("D81's pinned other_gi banding", banding(), {}),
        )
        for label, procedure, lines in variants:
            with self.subTest(label):
                inv, text = office_note(procedure, lines=lines)
                held_for_separate_em(self, em(inv, text), OTHER_GI_LABEL)
                p = em(inv, text, user_values=None)
                self.assertEqual(sorted(asked(p)), ['patient_status', 'separate_em', 'setting'])

    def test_d109_an_act_read_by_its_kind_is_done_only_with_its_kind_usable(self):
        """The banding filed office_em with its own words is DONE (status, performer, procedure, time and kind usable);
        with its kind's words unlocated it is only POSSIBLE - its kind is what makes it a procedure - and 99213 still
        asks separate_em."""
        inv, _ = office_note(banding(procedure=a('office_em', 'office', ['P2'])))
        self.assertEqual((procedure_day(inv).labels, procedure_day(inv).possible), ((OTHER_GI_LABEL,), ()))
        unlocated = act('E1', 'P2', 'band_ligation', 'banded with a ring', status_words='was performed',
                        procedure=a('office_em', 'office', ['P2']))
        inv, text = office_note(unlocated)
        self.assertFalse(events.usable(events.Reading.of(inv).events['E1'], 'kind'))
        self.assertEqual((procedure_day(inv).labels, procedure_day(inv).possible), ((), (OTHER_GI_LABEL,)))
        held_for_separate_em(self, em(inv, text), OTHER_GI_LABEL)

    def test_d109_an_act_filed_under_the_visit_earlier_in_the_day_counts(self):
        """C-3's second arm through the kind: the banding filed office_em at its own encounter 'Earlier in the day'
        (a verified earlier_encounter time, ON the date by the D109 frames) makes a procedure day."""
        line = 'Earlier in the day, rubber band ligation of one internal hemorrhoid was performed in the office.'
        earlier = banding(procedure=a('office_em', 'office', ['P2']),
                          time=a('earlier_encounter', 'Earlier in the day', ['P2']))
        inv, text = office_note(earlier, lines={'P2': line})
        self.assertEqual(day_of(inv), facts.ON)
        held_for_separate_em(self, em(inv, text), OTHER_GI_LABEL)

    def test_d109_controls_what_the_kind_never_reads(self):
        """What the kind arm must NOT move: an act of no procedural kind filed under the visit (a digital rectal
        examination - an examination whose device is verified manual, E13; moderate sedation; 'other'); and a banding
        filed office_em that C-3 does not count - verified at an earlier encounter ('in 2024'), or with an earlier time
        no word places (an indication's banding, 'Indication:', time_marker_missing): READY, no event_time, as at
        437b708bb."""
        dre_line = 'Digital rectal examination showed normal tone.'
        dre = act('E1', 'P1', 'examination', 'Digital rectal examination', status_words='showed',
                  procedure=a('office_em', 'Office visit', ['V1']), technique=a('manual', 'Digital', ['P1']))
        sedation = act('E1', 'P1', 'moderate_sedation', 'moderate sedation', status_words='was given',
                       procedure=a('office_em', 'Office visit', ['V1']))
        other = act('E1', 'P1', 'other', 'counseling', status_words='was provided',
                    procedure=a('office_em', 'Office visit', ['V1']))
        in_2024 = banding(procedure=a('office_em', 'office', ['P2']), time=a('earlier_encounter', 'in 2024', ['P2']))
        indication = 'Indication: rectal bleeding after rubber band ligation of an internal hemorrhoid in the office.'
        undatable = act('E1', 'P2', 'band_ligation', 'rubber band ligation', status_words='rubber band ligation',
                        procedure=a('office_em', 'office', ['P2']), time=a('earlier_encounter', 'Indication:', ['P2']))
        controls = (
            ('a digital rectal examination', dre, {'P1': dre_line}),
            ('moderate sedation filed under the visit', sedation, {'P1': 'Moderate sedation was given.'}),
            ("an act of kind 'other' filed under the visit", other, {'P1': 'Counseling was provided.'}),
            ('a banding verified in 2024', in_2024,
             {'P2': 'Rubber band ligation of one internal hemorrhoid was performed in the office in 2024.'}),
            ("an indication's banding, its earlier time undatable", undatable, {'P2': indication}),
        )
        for label, procedure, lines in controls:
            with self.subTest(label):
                inv, text = office_note(procedure, lines={'P1': 'Exam unremarkable.', **lines})
                found = procedure_day(inv)
                self.assertEqual((found.labels, found.possible, found.undatable), ((), (), ()))
                ready_with_no_procedure_day(self, em(inv, text))


# --- finding 14: an act earlier on the same date is ON the date -------------------------------------------------------

OFFICE_14 = {'V1': VISIT, 'V2': TIME}


def earlier_act(line: str, kind: str, kind_words: str, procedure: dict, words: str, value='earlier_encounter',
                **changes):
    """(inventory, text) of finding 14's office note: the visit (E0), its total time and the act line P1 (E1) by 'I',
    performed, its time ``value`` worded ``words``."""
    item = act('E1', 'P1', kind, kind_words, status_words='I performed', procedure=procedure,
               time=a(value, words, ['P1']), performer=a('documenting_team', 'I', ['P1']), **changes)
    return inventory({**OFFICE_14, 'P1': line}, events=[visit(), item], visits=[visit_facts()])


EGD_LINE = 'I performed an upper endoscopy earlier in the day, which showed a clean-based duodenal ulcer.'
BANDING_LINE = 'Earlier in the day, I performed rubber band ligation of one internal hemorrhoid.'
MORNING_LINE = 'Earlier in the morning I performed a flexible sigmoidoscopy, which showed internal hemorrhoids.'
THAT_DAY_LINE = 'Earlier that day, I performed a flexible sigmoidoscopy, which showed internal hemorrhoids.'
FINDING_14 = (
    ('B4: an EGD earlier in the day', EGD_LINE, 'examination', 'upper endoscopy',
     a('egd', 'upper endoscopy', ['P1']), 'earlier in the day', profiles.PROFILES['gi.egd'].label),
    ('B5: a banding earlier in the day', BANDING_LINE, 'band_ligation', 'rubber band ligation', a('other_gi'),
     'Earlier in the day', OTHER_GI_LABEL),
    ('B6: a flexible sigmoidoscopy earlier in the morning', MORNING_LINE, 'examination', 'flexible sigmoidoscopy',
     a('flex_sig', 'flexible sigmoidoscopy', ['P1']), 'Earlier in the morning', profiles.PROFILES['gi.flex_sig'].label),
)  # DECISIONS D112: G2 ("Earlier that day", THAT_DAY_LINE) is anaphoric - tests/test_interpretation_r5_em.py


def frame_parts_as_d54(text: str) -> list:
    """The split lexicon.current_frame and dated_frame apply (D54), as their own patterns apply it."""
    return [part.strip() for part in lexicon._FRAME_JOINS.split(lexicon._FRAME_EDGES.sub('', lexicon.fold(text)))]


class D109SameDateFrames(SimpleTestCase):
    """D109 (finding 14): a time whose own words are made of whole same-date frames is ON the date of service, whatever
    time Gemini gives - earlier_encounter included."""

    def test_d109_finding_14_an_act_earlier_in_the_day_is_on_the_date(self):
        """Finding 14's inputs B4-B6 (verified earlier_encounter times, the act by 'I'; G2 is D112's, the r5 module):
        437b708bb read each OFF the date and made 99213 READY ('Stated but not as done today'); c2e53f8e holds 99213
        with separate_em naming the family. Each is now ON, 99213 asks separate_em, and the routing stand-in reads the
        family performed, as the installed routing does."""
        for label, line, kind, kind_words, procedure, words, family_label in FINDING_14:
            with self.subTest(label):
                inv, text = earlier_act(line, kind, kind_words, procedure, words)
                stored = events.Reading.of(inv).events['E1']
                self.assertTrue(events.usable(stored, 'time'))  # verified: its 'earlier' marker
                self.assertEqual(day_of(inv), facts.ON)
                held_for_separate_em(self, em(inv, text), family_label)
                family = stored['family']
                self.assertIn({'family': family, 'status': 'performed', 'mentions': [], 'facts': [], 'missing': []},
                              facts.routing_stand_in(inv, DAY)['findings'])

    def test_d109_the_egd_earlier_in_the_day_is_documented_as_performed(self):
        """B4 in full: the EGD is DONE (every attribute usable), so the check says it is documented as performed - the
        installed release's own sentence."""
        inv, text = earlier_act(*FINDING_14[0][1:6])
        self.assertEqual(procedure_day(inv).labels, (profiles.PROFILES['gi.egd'].label,))
        self.assertIn('Upper GI endoscopy (EGD, esophagoscopy, POEM) is documented as performed on the same date',
                      check(em(inv, text), 'em.same_day_procedure').detail)

    def test_d109_a_current_time_worded_earlier_in_the_day_is_on_the_date(self):
        """Finding 14's control: the same EGD given current_encounter worded 'earlier in the day' is unverified (D35's
        'earlier') - 437b708bb read it UNDATABLE and asked the E/M's event_time; its own words now place it on the date,
        so it is a POSSIBLE same-day procedure and 99213 asks separate_em instead."""
        inv, text = earlier_act(EGD_LINE, 'examination', 'upper endoscopy', a('egd', 'upper endoscopy', ['P1']),
                                'earlier in the day', value='current_encounter')
        self.assertFalse(events.usable(events.Reading.of(inv).events['E1'], 'time'))
        self.assertEqual(day_of(inv), facts.ON)
        self.assertEqual(procedure_day(inv).possible, (profiles.PROFILES['gi.egd'].label,))
        held_for_separate_em(self, em(inv, text), profiles.PROFILES['gi.egd'].label)

    def test_d109_the_frames_are_read_whole_as_d54_reads_them(self):
        """facts.day_of over an earlier_encounter EGD: words made only of whole same-date frames are ON (verified by
        their 'earlier', or not: 'later in the day'); words with anything else, or another day's period, are OFF as
        before; a bare 'that day' or 'in the morning' is no frame and, with no earlier marker, UNDATABLE as before;
        'earlier today' (SAME_DAY_WORDS, read anywhere in the words) is ON as before."""
        cases = (
            ('earlier in the day', facts.ON), ('Earlier in the day,', facts.ON),
            ('Earlier that day', facts.OFF),  # DECISIONS D112: anaphoric, no frame - read by its 'earlier' marker
            ('Earlier in the morning', facts.ON), ('later in the day', facts.ON), ('earlier this afternoon', facts.ON),
            ('earlier in the day; earlier today', facts.ON), ('earlier today', facts.ON),
            ('I performed it earlier today', facts.ON), ('Earlier on the same day', facts.ON),
            ('earlier in the day, before her visit', facts.OFF), ('earlier in the day in 2024', facts.OFF),
            ('earlier in the morning of her admission', facts.OFF), ('earlier this year', facts.OFF),
            ('earlier in the week', facts.OFF), ('previously', facts.OFF),
            ('that day', facts.UNDATABLE), ('in the morning', facts.UNDATABLE),  # no marker: unverified, as before
        )
        line = 'An upper endoscopy was performed earlier.'
        for words, expected in cases:
            with self.subTest(words=words):
                stated = f'{line} {words}.'
                inv, _ = inventory({'P1': stated}, events=[
                    act('E1', 'P1', 'examination', 'upper endoscopy', status_words='was performed', procedure=a('egd'),
                        time=a('earlier_encounter', words, ['P1']))])
                self.assertEqual(day_of(inv), expected)

    def test_d109_the_frame_split_is_d54s(self):
        """facts' split (written without a pattern) equals lexicon's D54 split over every shape it meets: edges,
        commas, semicolons, a standalone 'and', 'and' inside a word, punctuation inside, empty and blank words."""
        for text in ('Earlier in the day,', ' , earlier in the day ; today. ', 'earlier in the day and today',
                     'sandy and band', 'today., on withdrawal', '', '   ', ',;', '(earlier that day)', 'and',
                     ' and today', 'earlier that day,, and later', 'Earlier—that day', '_today_', 'today and and x'):
            with self.subTest(text=text):
                self.assertEqual(facts._frame_parts(text), frame_parts_as_d54(text))
        self.assertEqual(facts._SAME_DAY_FRAMES, frozenset(lexicon.fold(f) for f in lexicon.SAME_DAY_FRAMES))
        for word in facts.SAME_DAY_WORDS:  # every same-day word is a whole frame too
            self.assertIn(word, facts._SAME_DAY_FRAMES)
        for bare in ('that day', 'that morning', 'in the morning', 'the day', 'earlier', 'later'):
            self.assertNotIn(bare, facts._SAME_DAY_FRAMES)

    def test_d109_controls_another_date_stays_off(self):
        """What the frames must NOT move: an act verified 'in 2024' (finding 14's control) and one whose words carry
        more than frames are OFF, and 99213 is READY as before."""
        controls = (
            ('in 2024', 'I performed an upper endoscopy in 2024, which showed a clean-based duodenal ulcer.',
             'in 2024'),
            ('words beyond the frames', 'I performed an upper endoscopy earlier in the day, before her visit.',
             'earlier in the day, before her visit'),
        )
        for label, line, words in controls:
            with self.subTest(label):
                inv, text = earlier_act(line, 'examination', 'upper endoscopy', a('egd', 'upper endoscopy', ['P1']),
                                        words)
                self.assertEqual(day_of(inv), facts.OFF)
                ready_with_no_procedure_day(self, em(inv, text))


# --- findings 15 and 16: a non-GI or unidentified act counts only as an act of this encounter -------------------------

RUQ_VISIT = 'Office visit: established patient seen today for right upper quadrant pain.'
THIRTY = 'Total time on the date of the encounter: 30 minutes.'
CT_LINE = 'CT images obtained today were interpreted separately by the radiology service.'
FLUOROSCOPY = 'Fluoroscopy images were interpreted separately by the radiology service.'  # fb13's own line
MRCP_PLAN = 'Plan: MRCP; recheck in 4 weeks.'
CBD_VISIT = 'Office visit: established patient seen today for a dilated common bile duct.'
INDICATION = 'Indication: Dilated common bile duct on abdominal ultrasound; evaluate for choledocholithiasis.'
REASON = 'Reason for visit: Dilated common bile duct on abdominal ultrasound.'
PAST = ('Past history: ERCP with stone extraction at another hospital in 2023, followed by laparoscopic '
        'cholecystectomy.')
SURVEILLANCE = 'Indication: surveillance after polypectomy of a tubular adenoma.'
EUS_PLAN = 'Plan: EUS; recheck in 4 weeks.'


def the_visit(line: str, minutes: str, passage: str = 'V1') -> tuple:
    """(E0, its visit facts): an office E/M visit (office_em) and its total time ``minutes`` (V2)."""
    return (act('E0', passage, 'em_visit', 'Office visit', status_words='seen today',
                procedure=a('office_em', 'Office visit', [passage])),
            {'event': 'E0', 'basis': a('total_time', minutes, ['V2']), 'separately_identifiable': a('not_stated')})


def interpreted(line: str = CT_LINE, words: str = 'CT images', kind_words: str = 'interpreted',
                status_words: str = 'were interpreted', **changes) -> tuple:
    """(inventory, text) of finding 15's office note: the visit and fb13's shape for ``line`` (E1, P2) - procedure
    not_gi, kind other 'interpreted', performed 'were interpreted', current_encounter with no words, other_clinician
    'radiology service' - unless the arguments or ``changes`` say otherwise."""
    changes.setdefault('procedure', a('not_gi', words, ['P2']))
    changes.setdefault('performer', a('other_clinician', 'radiology service', ['P2']))
    item = act('E1', 'P2', 'other', kind_words, status_words=status_words, **changes)
    e0, facts_ = the_visit(RUQ_VISIT, '30 minutes')
    return inventory({'V1': RUQ_VISIT, 'V2': THIRTY, 'P2': line, 'P3': MRCP_PLAN}, events=[e0, item],
                     visits=[facts_])


def history_study(line: str, *more, kind='other', kind_words='abdominal ultrasound', time_words='Indication:',
                  procedure=None, status_words='on abdominal ultrasound') -> tuple:
    """(inventory, text) of finding 16's office note: the visit and fb14's shape for ``line`` (E1, P1) - procedure
    not_gi, kind ``kind``, performed, earlier_encounter worded ``time_words`` (no earlier marker: time_marker_missing),
    performer unknown - with ``more`` events."""
    item = act('E1', 'P1', kind, kind_words, status_words=status_words,
               procedure=procedure if procedure is not None else a('not_gi', 'abdominal ultrasound', ['P1']),
               time=a('earlier_encounter', time_words, ['P1']), performer=a('unknown'))
    e0, facts_ = the_visit(CBD_VISIT, '25 minutes')
    return inventory({'V1': CBD_VISIT, 'V2': TIME, 'P1': line, 'P3': EUS_PLAN}, events=[e0, item, *more],
                     visits=[facts_])


class D109CurrentOnlyFamilies(SimpleTestCase):
    """D109 (findings 15 and 16; D94 narrowed): an act of gi.unsupported or of no family makes a procedure day only as
    an act of this encounter that no other clinician or facility is verified to have done."""

    def assert_ready(self, inv, text, visit_line):
        ready_with_no_procedure_day(self, em(inv, text, visit_line))
        p = em(inv, text, visit_line, user_values=None)
        self.assertEqual(sorted(asked(p)), ['patient_status', 'setting'])

    def test_d109_finding_15_a_study_read_by_the_radiology_service_makes_no_procedure_day(self):
        """Finding 15's input and fb13's attested line: 437b708bb held 99213 with separate_em ('Service outside the GI
        profiles is documented as performed on the same date'); c2e53f8e is READY. Its time is current, but its
        performer is verified to another clinician ('radiology service'), so it makes no procedure day. The same with
        Gemini's procedure 'unknown' (437b708bb: 'A procedure CPT Studio could not identify is possibly performed')."""
        variants = (
            ('the CT, current with no words', interpreted()),
            ("the CT, current worded 'today'", interpreted(time=a('current_encounter', 'today', ['P2']))),
            ("fb13's fluoroscopy line with r1's attributes", interpreted(FLUOROSCOPY, 'Fluoroscopy images')),
            ("the CT, procedure 'unknown'", interpreted(procedure=a('unknown'))),
        )
        for label, (inv, text) in variants:
            with self.subTest(label):
                stored = events.Reading.of(inv).events['E1']
                self.assertTrue(events.verified_other_performer(stored))
                self.assertEqual(day_of(inv), facts.ON)  # on the date - and still no procedure day of this physician's
                self.assertEqual(procedure_day(inv), combination.ProcedureDay())
                self.assert_ready(inv, text, RUQ_VISIT)

    def test_d109_finding_16_a_study_named_in_the_indication_asks_nothing(self):
        """Finding 16's inputs, fb14's attested shape: an abdominal ultrasound named in the indication,
        earlier_encounter worded 'Indication:' (r2), its whole clause (r1) or as an examination (r3); 'Reason for
        visit:'; a 'followed by' cholecystectomy beside an ERCP dated 2023 (W1-u31a-reg-p7-codes-025's shape); and a
        polypectomy whose procedure Gemini leaves 'unknown'. Each time is unverified (time_marker_missing):
        437b708bb asked 99213's event_time ('Was the act ... done at this encounter?'), whose only answers EXCLUDE
        99213; c2e53f8e is READY. Not of this encounter, none makes a procedure day or asks anything."""
        ercp = act('E2', 'P1', 'examination', 'ERCP', status_words='ERCP', procedure=a('ercp', 'ERCP', ['P1']),
                   time=a('earlier_encounter', 'in 2023', ['P1']),
                   performer=a('other_facility', 'another hospital', ['P1']))
        extraction = act('E3', 'P1', 'stone_extraction', 'stone extraction', status_words='stone extraction',
                         procedure=a('ercp', 'ERCP', ['P1']), time=a('earlier_encounter', 'in 2023', ['P1']),
                         performer=a('other_facility', 'another hospital', ['P1']))
        variants = (
            ("fb14 r2: worded 'Indication:'", history_study(INDICATION)),
            ('fb14 r1: worded by its clause', history_study(
                INDICATION, time_words='Indication: Dilated common bile duct on abdominal ultrasound')),
            ('fb14 r3: an examination', history_study(INDICATION, kind='examination')),
            ("'Reason for visit:'", history_study(REASON, time_words='Reason for visit:')),
            ("a 'followed by' cholecystectomy", history_study(
                PAST, ercp, extraction, kind_words='laparoscopic cholecystectomy', time_words='followed by',
                procedure=a('not_gi', 'laparoscopic cholecystectomy', ['P1']),
                status_words='laparoscopic cholecystectomy')),
            ("a polypectomy, procedure 'unknown'", history_study(
                SURVEILLANCE, kind='removal', kind_words='polypectomy', procedure=a('unknown'),
                status_words='polypectomy')),
        )
        for label, (inv, text) in variants:
            with self.subTest(label):
                stored = events.Reading.of(inv).events['E1']
                self.assertEqual((stored['time']['state'], day_of(inv)), ('unverified', facts.UNDATABLE))
                self.assertEqual(procedure_day(inv), combination.ProcedureDay())
                self.assert_ready(inv, text, CBD_VISIT)

    def test_d109_an_act_of_this_encounter_still_counts(self):
        """What the narrowing must NOT move: a non-GI act of this encounter whose performer is not verified to another
        clinician - by the documenting team, unknown, or named as another clinician in words that do not verify (a name
        with no documenting endoscopist to set it apart: name_not_other) - still makes a procedure day (D94's class: the
        office excision; finding 15's ECG obtained in clinic today, the recorded cost); and an unidentified act whose
        current time is unverified (any state) is still undatable, so 99213 asks event_time (C-3)."""
        ecg = 'A 12-lead ECG was obtained in clinic today and showed sinus rhythm.'
        named = 'CT images obtained today were interpreted separately by Dr. Lena Park.'
        earlier = 'CT images obtained previously were interpreted in clinic.'
        variants = (
            ('the CT by the documenting team', interpreted(performer=a('documenting_team')), 'separate_em'),
            ("finding 15's ECG, performer unknown", interpreted(
                ecg, '12-lead ECG', kind_words='ECG', status_words='was obtained', performer=a('unknown')),
             'separate_em'),
            ('another clinician named in words that do not verify', interpreted(
                named, performer=a('other_clinician', 'Dr. Lena Park', ['P2'])), 'separate_em'),
            ('an unidentified act, its current time unverified', interpreted(
                earlier, procedure=a('unknown'), performer=a('documenting_team'),
                time=a('current_encounter', 'previously', ['P2'])), 'event_time'),
        )
        for label, (inv, text), fact in variants:
            with self.subTest(label):
                stored = events.Reading.of(inv).events['E1']
                self.assertFalse(events.verified_other_performer(stored))
                p = em(inv, text, RUQ_VISIT)
                self.assertEqual((p.status, asked(p)), ('needs_clarification', [fact]))
                if fact == 'separate_em':
                    self.assertIsNone(check(p, 'em.same_day_coverage'))
                else:
                    self.assertEqual(procedure_day(inv).undatable, ('E1',))
