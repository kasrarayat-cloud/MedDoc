"""DECISIONS D152 (the Gemini migration's round 5e, narrowing only: the round-5d review of D146, round5d review:colon3
problems 0-2), SYNTHETIC, each built from its source's own input. Nothing is sent.

D152 (1) (a signature label read from the start of the line on which the act's passage begins, so a sentence
hard-wrapped before the act's own words is held as the one-line sentence is) and D152 (2) (status or kind words that
open at the label) were built and HELD BACK under this round's narrowing rule. Each also holds, another_role, the stone
extraction of finding 5's stone clearance when its line opens with a signature label - hard-wrapped before the act's
words, or with the status words opening at the label. A code another_role_hold holds supports nothing, so it claims
nothing (assess._claims), and the lithotripsy's 43265 loses its competing_codes hold and is READY: a RELEASE against
4f82e5056 and e5628be56, which hold 43264 and 43265 [competing_codes], and against the installed release configured as
in production (Astra and Fable read and proposing nothing: tests.test_interpretation_r3_claims.READ_NOTHING), which
holds both [competing_codes] too. With no participant configured, c2e53f8e is READY on both.

These pins keep that: whatever reads the extraction's label, the lithotripsy's code stays held with competing_codes
and the extraction's stays held, in both configurations. Each asserts in independent subtests."""
from __future__ import annotations

from django.test import SimpleTestCase

from tests.test_interpretation_events import asked, exam, inventory, proposal, run
from tests.test_interpretation_identity import a, act, tg
from tests.test_interpretation_r3_claims import READ_NOTHING, STONE

PARTICIPANTS = ((), READ_NOTHING)  # none configured, and Astra and Fable read and proposing nothing (production's)
LABEL = 'Documented by Jo Rowe, RN: '
# finding 5's extraction line (STONE['P4']) told after a signature label, hard-wrapped before the act's own words
WRAPPED = LABEL + 'The stone fragments from the bile duct\nwere extracted with an extraction balloon.'
ONE_LINE = LABEL + 'The stone fragments were extracted from the bile duct with an extraction balloon.'


def clearance(p4: str, status_words: str = 'were extracted') -> tuple:
    """Finding 5's stone clearance (tests.test_interpretation_r3_claims.stone_clearance's events): the duodenoscope
    (E1), the biliary cannulation (E2), the physician's mechanical lithotripsy of the 15 mm stone (E3, P3) and the
    balloon extraction of its fragments (E4) told on ``p4``; 43264 citing the extraction, 43265 the lithotripsy (one
    stone clearance: D55, D74)."""
    lines = dict(STONE, P4=p4)
    inv, text = inventory(lines, events=[
        exam('E1', 'P1', words='duodenoscope', procedure=a('ercp')),
        act('E2', 'P2', 'cannulation', 'cannulation', status_words='was achieved', procedure=a('ercp'),
            target=tg('', 'bile_duct', 'biliary', ['P2']), technique=a('sphincterotome', 'sphincterotome', ['P2'])),
        act('E3', 'P3', 'lithotripsy', 'lithotripsy', status_words='was fragmented', procedure=a('ercp'),
            target=tg('', 'common_bile_duct', 'common bile duct', ['P3']),
            technique=a('lithotripter', 'lithotripsy', ['P3'])),
        act('E4', 'P4', 'stone_extraction', 'extracted', status_words=status_words, procedure=a('ercp'),
            target=tg('', 'bile_duct', 'bile duct', ['P4']),
            technique=a('extraction_balloon', 'extraction balloon', ['P4']))])
    return inv, text, [('43264', p4), ('43265', STONE['P3'])]


class TheRivalOfASignedExtractionStaysHeld(SimpleTestCase):
    """D152's held-back rules (1) and (2), DECISIONS D152: the inputs on which each would RELEASE 43265."""

    def rival_held(self, inv, text, codes, **where) -> None:
        for participants in PARTICIPANTS:
            result = run(inv, text, codes, participants=participants)
            extraction, lithotripsy = proposal(result, '43264'), proposal(result, '43265')
            with self.subTest(participants=len(participants), **where):
                self.assertEqual(lithotripsy.status, 'needs_clarification')
                self.assertIn('competing_codes', asked(lithotripsy))
                self.assertEqual(extraction.status, 'needs_clarification')

    def test_d152_the_rival_of_a_wrapped_signature_extraction_stays_held(self):
        """D152 (1)'s release: the extraction told after 'Documented by Jo Rowe, RN:', its line hard-wrapped before
        'were extracted'. 4f82e5056, e5628be56 and this build: 43264 and 43265 held [competing_codes], in both
        configurations. c2e53f8e: both held [competing_codes] with Astra and Fable read and proposing nothing; both
        READY with none configured. D152 (1) as built (held back): 43264 held another_role, 43265 READY."""
        self.rival_held(*clearance(WRAPPED), shape='wrapped')

    def test_d152_the_rival_of_an_extraction_whose_status_words_open_at_the_label_stays_held(self):
        """D152 (2)'s release: the one-line extraction after 'Documented by Jo Rowe, RN:', Gemini's status words
        'Documented by Jo Rowe, RN: The stone fragments were extracted' opening at the label. 4f82e5056, e5628be56 and
        this build: both held [competing_codes]; c2e53f8e as above. D152 (2) as built (held back): 43264 held
        another_role, 43265 READY."""
        self.rival_held(*clearance(ONE_LINE, status_words=LABEL + 'The stone fragments were extracted'),
                        shape='status words opening at the label')
