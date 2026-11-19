"""DECISIONS D169 (round 5g, narrowing only; refute6 families finding[0], judges findings[6] and [0]), SYNTHETIC: one
currency rule for the exclusion, the E/M and the bundling.

- (1) families finding[0] (critical): an act Gemini places at an earlier encounter in words that put it on the date of
  service ("Earlier today, I performed a flexible sigmoidoscopy ...", earlier_encounter worded "Earlier today", verified
  by its marker) was EXCLUDED "at an earlier encounter, not on the date of service" while the E/M check of the same
  assessment read it on that date (facts.day_of ON). events.deciding now reads an exclusion's time basis with day_of
  (events._off_the_date): an act it does not place OFF is never excluded for its time. The code is held (7.6), never
  excluded; c2e53f8e is READY ("Earlier today") or holds it ("Earlier in the day", "Earlier this morning").
- (2) and (3) NOT INTEGRATED (round 5g integration; review:currency7 problems 0-4 and 6): the clock-time and
  this-date reading (2) put another day's act on the date of service and released the E/M; reading only a verified other
  time as not current (3) dropped questions and listings that 05a881a75, e5628be56 and c2e53f8e all keep, and moved a
  READY code's acts. judges findings[6] and [0] stay open for the next round.
- Recorded (D169Recorded): what (1) cannot reach in its ownership (the act's listing; its event_time question).

Each fixture is a synthetic Gemini answer over a synthetic document (fictional patients), read by read.read, normalized
with the real linked steps and assessed through assess.assess with a synthetic Corti response citing the document's own
words (the S08 builders), member values office/established. Texts are byte-identical to the findings' inputs where a
sha256 prefix is asserted (refute6/currency-em/cases/f1-cases.json, refute6/verify-gate-em-0/out/cases.json). The
outcomes of c2e53f8e (engine.assess with gi_context.extract_context, merge_user_values office/established and
detect.route on the date the merged context gives, the same synthetic reference rows), e5628be56, f9013e12e and
05a881a75 quoted in the docstrings were measured on byte-identical texts (round5g/currency7/out/r0/census.md). The
attested answer is the committed FRESH-2 recording of W1-u30a-rel-f4-unread-before-017 with its snare's time and open
question replaced by FRESH-1 r1's own, verbatim. Nothing is sent."""
from __future__ import annotations

import copy
import hashlib
import json

from django.test import SimpleTestCase

from studio.interpretation import coverage, events, facts, normalize, relations, verify
from studio.interpretation import read as interpretation_read
from studio.reference.store import InMemoryReferenceLookup
from studio.types import EvidenceSpan, NormalizedResponse, ProviderCode
from tests.test_interpretation_events import (COLONOSCOPE, MUE_KEY, MUE_ROW, PFS_KEY, ROWS, _info, _pfs, asked, check,
                                              exam, inventory, proposal, reached, response, run)
from tests.test_interpretation_identity import a, act, les, tg
from tests.test_interpretation_r3_families import MEMBER, PLAN, TIME, VISIT, visit, visit_facts
from tests.test_interpretation_r4_currency_pairing import BIOPSY_LINE, SNARE_LINE, attested_answer, biopsy_event, pasted
from tests.test_interpretation_r4_em_same_day import OTHER_GI_LABEL, held_for_separate_em
from tests.test_interpretation_r5_em import NON_GI_LABEL
from tests.test_interpretation_r5c_currency import EGD_LABEL, FLEX_SIG_LABEL, SEPARATE, SEPARATE_LINE
from tests.test_interpretation_r5e_currency import APART, LISTED, SECOND_HELD, SECOND_INFORMATIONAL
from tests.test_interpretation_replay import FIXTURES, MANIFEST, text_and_pages

DAY = '2026-11-09'
NO_PROPOSAL = 'office / outpatient visit (documented as performed) has no supported proposal'
# The synthetic reference rows widened to the codes these pins propose (round5g/currency7/tools/rows.py's values)
MY_ROWS = dict(ROWS)
MY_ROWS.update({'45330': _pfs('2', None), '45331': _pfs('3', '45330'), '43264': _pfs('3', '43260'),
                '43265': _pfs('3', '43260')})
MY_LOOKUP = InMemoryReferenceLookup([_info(PFS_KEY, 'cms-pfs', 'RVU26D'), _info(MUE_KEY, 'cms-mue-practitioner', '2026-Q4')],
                                    {PFS_KEY: {(code, ''): row for code, row in MY_ROWS.items()},
                                     MUE_KEY: {(code, ''): MUE_ROW for code in MY_ROWS}})


def sha(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()[:16]


def office(line: str, *items, stated: bool = False, visit_line: str = VISIT, extra=None) -> tuple:
    """(inventory, text) of D81's office note: the visit (E0, V1) and its total time (V2), the separately identifiable
    statement P5 when ``stated``, ``extra`` lines, the act line P2, the plan P3."""
    separate = {'separately_identifiable': a('stated', SEPARATE, ['P5'])} if stated else {}
    lines = {'V1': visit_line, 'V2': TIME, **({'P5': SEPARATE_LINE} if stated else {}), **(extra or {}), 'P2': line,
             'P3': PLAN}
    return inventory(lines, events=[visit(), *items], visits=[{**visit_facts(), **separate}])


def by_i(pid: str = 'P2') -> dict:
    return a('documenting_team', 'I', [pid])


def flex(time: dict, performer=None, status_words: str = 'I performed', technique: bool = True) -> dict:
    """The flexible sigmoidoscopy by 'I' (E1, P2): with its endoscope (the families lens's builder) or without (the
    judges verifier's)."""
    extra = {'technique': a('endoscope', 'flexible sigmoidoscopy', ['P2'])} if technique else {}
    return act('E1', 'P2', 'examination', 'flexible sigmoidoscopy', status_words=status_words,
               procedure=a('flex_sig', 'flexible sigmoidoscopy', ['P2']), time=time,
               performer=performer if performer is not None else by_i(), **extra)


def egd(time: dict, performer=None, status_words: str = 'I performed', technique: bool = False) -> dict:
    extra = {'technique': a('endoscope', 'upper endoscopy', ['P2'])} if technique else {}
    return act('E1', 'P2', 'examination', 'upper endoscopy', status_words=status_words,
               procedure=a('egd', 'upper endoscopy', ['P2']), time=time,
               performer=performer if performer is not None else by_i(), **extra)


def assessed(inv, text, codes):
    return run(inv, text, list(codes), user_values=MEMBER, reference=MY_LOOKUP)


def day_of(inv, eid: str = 'E1') -> str:
    return facts.day_of(events.Reading.of(inv).events[eid], DAY)


def em(inv, text, *codes):
    return proposal(assessed(inv, text, [('99213', VISIT), *codes]), '99213')


def listing(inv, text):
    completeness = assessed(inv, text, []).completeness
    return ([str(item.get('label')) for item in completeness['unresolved_items']],
            [str(item.get('label')) for item in completeness['not_listed']])


def second_99213(inv, text):
    result = run(inv, text, [], user_values=MEMBER, reference=MY_LOOKUP,
                 second=response(text, [('99213', VISIT)], provider='fable'), second_scope={'items': [NO_PROPOSAL]})
    return [(p.bucket, p.status, asked(p)) for p in result.proposals if p.code == '99213']


def held_not_excluded(test, p, *facts_asked):
    """A code held, never excluded: selected, needs_clarification, no exclusion reason, asking ``facts_asked``."""
    test.assertEqual((p.bucket, p.status), ('selected', 'needs_clarification'))
    test.assertFalse(p.exclusion_reason)
    test.assertEqual(asked(p), list(facts_asked))


def ready_with_the_consideration(test, p):
    test.assertEqual((p.bucket, p.status, asked(p)), ('selected', 'ready', []))
    test.assertTrue(any('Modifier 25' in m for m in p.modifier_considerations))


def asks_event_time(test, p):
    test.assertEqual((p.bucket, p.status, asked(p)), ('selected', 'needs_clarification', ['event_time']))


# --- (1) families finding[0]: the exclusion's time basis reads day_of --------------------------------------------------

FLEX_TODAY = 'Earlier today, I performed a flexible sigmoidoscopy to 40 cm, which showed internal hemorrhoids.'
EGD_TODAY = ('Earlier today, I performed an upper endoscopy to the second portion of the duodenum and took biopsies of '
             'the gastric antrum.')
EGD_SHE = 'She underwent an upper endoscopy earlier today, which showed a clean-based duodenal ulcer.'
FLEX = ('45330', 'flexible sigmoidoscopy')


class D169AnActOnTheDateIsNeverExcludedForItsTime(SimpleTestCase):
    """D169 (1): events.deciding reads an exclusion's time basis with facts.day_of; an act it places ON is held."""

    def test_d169_finding_0_the_flexible_sigmoidoscopy_earlier_today_is_held_never_excluded(self):
        """The finding's input, byte-identical (the lens's f1.flex.earlier-today.lead): D81's office lines with "Earlier
        today, I performed a flexible sigmoidoscopy to 40 cm, which showed internal hemorrhoids." (examination flex_sig
        by 'I', earlier_encounter worded "Earlier today", verified by its marker). 05a881a75, f9013e12e and e5628be56:
        day_of ON and 99213 held with separate_em, yet 45330 EXCLUDED 'at an earlier encounter, not on the date of
        service'. c2e53f8e: 45330 READY. Now 45330 is held (not documented as done at this encounter: performed_status,
        and the extent), alone and beside 99213, never excluded; the time decides nothing (events.deciding)."""
        inv, text = office(FLEX_TODAY, flex(a('earlier_encounter', 'Earlier today', ['P2'])))
        self.assertEqual(sha(text), '370423261866b676')
        e1 = events.Reading.of(inv).events['E1']
        self.assertEqual((e1['time']['value'], e1['time']['state']), ('earlier_encounter', 'verified'))
        self.assertEqual(verify.exclusion_basis('time', e1['time']), 'marker')
        self.assertEqual(day_of(inv), facts.ON)
        self.assertEqual(events.deciding(e1), ('', '', ''))
        p = proposal(assessed(inv, text, [FLEX]), '45330')
        held_not_excluded(self, p, 'performed_status', 'extent')
        self.assertEqual(p.support['reason'], events.NOT_DOCUMENTED)
        result = assessed(inv, text, [('99213', VISIT), FLEX])
        held_not_excluded(self, proposal(result, '45330'), 'performed_status', 'extent')
        held_for_separate_em(self, proposal(result, '99213'), FLEX_SIG_LABEL)

    def test_d169_finding_0_its_members_earlier_in_the_day_this_morning_and_whole_line_words(self):
        """The finding's members, each EXCLUDED on every new-path head: "Earlier in the day" and "Earlier this
        morning" (c2e53f8e holds 45330 asking performed_status), and the whole line as the time words (FRESH-2 attests
        whole-line time words). Now held, never excluded."""
        for line, words in ((FLEX_TODAY, FLEX_TODAY),
                            (FLEX_TODAY.replace('Earlier today', 'Earlier in the day'), 'Earlier in the day'),
                            (FLEX_TODAY.replace('Earlier today', 'Earlier this morning'), 'Earlier this morning')):
            with self.subTest(words=words):
                inv, text = office(line, flex(a('earlier_encounter', words, ['P2'])))
                self.assertEqual(day_of(inv), facts.ON)
                held_not_excluded(self, proposal(assessed(inv, text, [FLEX]), '45330'), 'performed_status', 'extent')

    def test_d169_finding_0_the_upper_endoscopy_members(self):
        """The EGD with biopsies, whole-line words (byte-identical to the lens's): 43239 AND 43235 were both EXCLUDED
        (c2e53f8e holds 43239 [extent], 43235 [base_included, extent]); with the words "Earlier today" only, 43235 was
        excluded and 43239 held asking statement_scope. "She underwent an upper endoscopy earlier today, ..." with the
        performer unknown: 43235 was EXCLUDED (c2e53f8e: held [extent]). Now every one is held, never excluded."""
        for words in (EGD_TODAY, 'Earlier today'):
            exam_ = egd(a('earlier_encounter', words, ['P2']), technique=True)
            biopsy = act('E2', 'P2', 'biopsy', 'took biopsies', status_words='took biopsies',
                         procedure=a('egd', 'upper endoscopy', ['P2']), time=a('earlier_encounter', words, ['P2']),
                         performer=by_i(), target=tg('', 'gastric_antrum', 'gastric antrum', ['P2']))
            inv, text = office(EGD_TODAY, exam_, biopsy)
            if words == EGD_TODAY:
                self.assertEqual(sha(text), '5704becbd9ce82aa')
            result = assessed(inv, text, [('43239', 'took biopsies of the gastric antrum'), ('43235', 'upper endoscopy')])
            with self.subTest(words=words):
                held_not_excluded(self, proposal(result, '43239'), 'performed_status', 'extent')
                held_not_excluded(self, proposal(result, '43235'), 'performed_status', 'extent')
        inv, text = office(EGD_SHE, egd(a('earlier_encounter', 'earlier today', ['P2']), a('unknown'),
                                        status_words='underwent', technique=True))
        self.assertEqual(sha(text), '340b9f02cd5de416')
        held_not_excluded(self, proposal(assessed(inv, text, [('43235', 'upper endoscopy')]), '43235'),
                          'performed_status', 'extent')

    def test_d169_d162s_pinned_exclusion_is_held(self):
        """D162's recorded exclusion (tests/test_interpretation_r5f_currency.py, the EGD by 'I' "earlier in the day,
        before her visit" with 43235: ON by D162's frame, excluded on every new-path head, held on c2e53f8e asking extent
        and performed_status): held now, the same class as (1). So is D162's recorded problem 1 ("three months prior to
        today's visit", ON by 'today's')."""
        for line, words in (('I performed an upper endoscopy earlier in the day, before her visit.',
                             'earlier in the day, before her visit'),
                            ("I performed her last upper endoscopy three months prior to today's visit, which showed "
                             "gastritis.", "three months prior to today's visit")):
            with self.subTest(words=words):
                inv, text = office(line, egd(a('earlier_encounter', words, ['P2'])))
                self.assertEqual(day_of(inv), facts.ON)
                held_not_excluded(self, proposal(assessed(inv, text, [('43235', 'upper endoscopy')]), '43235'),
                                  'performed_status', 'extent')

    def test_d169_the_time_basis_reads_day_of_and_nothing_else_moves(self):
        """events.deciding over one statement each: a usable earlier time day_of places ON gives no time basis; OFF ones
        keep theirs (a marker, a compared literal); the status and performer bases are read as before - another
        facility's act "Earlier in the day" (ON by its frame) is still decided by its performer."""
        cases = (
            ('Earlier today', None, ('', '', '')),
            ('Two weeks ago', None, ('time', 'earlier_encounter', 'marker')),
            ('On 10/30/2026', None, ('time', 'earlier_encounter', 'literal')),
            ('Earlier in the day', a('other_facility', 'at an outside hospital', ['P2']),
             ('performer', 'other_facility', 'marker')),
        )
        for words, performer, expected in cases:
            line = f'{words}, she had undergone an upper endoscopy at an outside hospital, which showed gastritis.'
            inv, _ = office(line, egd(a('earlier_encounter', words, ['P2']), performer or a('unknown'),
                                      status_words='had undergone'))
            with self.subTest(words=words):
                self.assertEqual(events.deciding(events.Reading.of(inv).events['E1']), expected)
        denial = act('E1', 'P2', 'examination', 'flexible sigmoidoscopy', status='not_performed',
                     status_words='No flexible sigmoidoscopy was performed',
                     procedure=a('flex_sig', 'flexible sigmoidoscopy', ['P2']))
        inv, _ = office('No flexible sigmoidoscopy was performed today.', denial)
        self.assertEqual(events.deciding(events.Reading.of(inv).events['E1']), ('status', 'not_performed', 'literal'))

    def test_d169_controls_an_act_off_the_date_is_excluded_as_before(self):
        """Unchanged on every tree: an act its own words place on another date - "Two weeks ago", "Previously", "On
        10/30/2026, earlier in the day" (a literal decides) - and the verified outside EGD "Earlier in the day, before
        her visit, ... at an outside hospital" (D132's condition: OFF) are excluded with 43235."""
        cases = (
            ('Two weeks ago, I performed an upper endoscopy, which showed gastritis.', 'Two weeks ago', None),
            ('Previously, I performed an upper endoscopy, which showed gastritis.', 'Previously', None),
            ('On 10/30/2026, earlier in the day, I performed an upper endoscopy, which showed gastritis.',
             'On 10/30/2026, earlier in the day', None),
            ('Earlier in the day, before her visit, she had undergone an upper endoscopy at an outside hospital.',
             'Earlier in the day, before her visit', a('other_facility', 'at an outside hospital', ['P2'])),
        )
        for line, words, performer in cases:
            inv, text = office(line, egd(a('earlier_encounter', words, ['P2']), performer,
                                         status_words='had undergone' if performer else 'I performed'))
            with self.subTest(words=words):
                self.assertEqual(day_of(inv), facts.OFF)
                p = proposal(assessed(inv, text, [('43235', 'upper endoscopy')]), '43235')
                self.assertEqual((p.bucket, p.status), ('excluded', 'excluded'))


# --- (2) judges finding[6]: a clock time and this date's own words place an OFF act ON -------------------------------

FLEX_TAIL = 'I performed a flexible sigmoidoscopy, which showed internal hemorrhoids.'
EGD_TAIL = 'I performed an upper endoscopy, which showed gastritis.'
FINDING_6 = ('Earlier this AM', 'Earlier this a.m.', 'Earlier this PM', 'Immediately prior to this visit',
             'Just prior to this visit', 'Earlier on this date', 'At 7:45, prior to this office visit',
             'This AM, prior to clinic', 'Earlier, at 8:30', 'Earlier, at 0830')


class D169Recorded(SimpleTestCase):
    """D169's recorded outcomes: what (1) cannot reach inside its ownership, the forbidden-class rows the spec's outcome
    for (2) brings (each equal to c2e53f8e and supported by the document), and other-day words beside a clock time."""

    def test_d169_recorded_stop_the_act_is_not_listed_and_its_question_is_7_6s(self):
        """STOPPED (1): with no code proposed the flexible sigmoidoscopy "Earlier today" is listed nowhere (c2e53f8e
        lists 'flexible sigmoidoscopy (documented as performed) has no supported proposal'): coverage lists 'has no
        supported proposal' only for a session with a DONE event (events.done reads a usable current_encounter time),
        outside this repair's ownership. And 45330 asks 7.6's performed_status, not event_time: 7.4 reads an act Gemini
        places at another time as no positive candidate (_without_support) and h4 asks only an unusable time - both
        outside this repair's ownership."""
        inv, text = office(FLEX_TODAY, flex(a('earlier_encounter', 'Earlier today', ['P2'])))
        unresolved, not_listed = listing(inv, text)
        self.assertFalse([label for label in unresolved if 'sigmoidoscopy' in label])
        self.assertEqual(asked(proposal(assessed(inv, text, [FLEX]), '45330')), ['performed_status', 'extent'])
