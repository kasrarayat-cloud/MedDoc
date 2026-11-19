"""DECISIONS D98, D99 and D100 (the round-4 refutation of 437b708bb, findings 7, 8 and 1): what the pairing table and
the rules that hold OTHER codes read as this encounter's.

D98 (finding 7). coverage.possibly_current and relations._possibly_current read only a current_encounter time as
possibly current, so a time Gemini gave as 'unknown' was an ABSENCE for the rules that hold other codes by an event:
on the attested FRESH-2 answer W1-u30a-rel-f4-unread-before-017 r1 (the snare's time 'unknown', worded 'Once'), with
one on-contract biopsy of the polyp it removed added, 45380 was READY while 45385 was asked its time; the installed
release c2e53f8e holds 45380 as part of the removal. Now an explicit unknown is possibly current (FINAL C6: absent,
never a match and never a non-match): only an earlier_encounter or future time, verified or not, is not current. The
same reader held the lift injection beside an EMR worded 'Once' (45381), the EGD beside an upper EUS examination
(43235, D70), the stone extraction beside a lithotripsy (43264, D74) and - relations' half - a bleeding control beside
a removal (45382, D41).

D99 (finding 8). On a document whose date no check establishes, D67(a) leaves a current time worded with a day
('On 11/09/2026') date_unchecked, and relations.time_row read it as UNKNOWN: a same-day denial ('Impression: No
polypectomy was performed.') was UNRESOLVED(time), so 45385 asked only its time, the conflicts check said there was no
conflict and '1 conflict in the record' left completeness, where the installed release asks conflict:snare. Now a
current_encounter time whose ONLY failure is date_unchecked pairs as current: a pending date check is not a doubt about
the encounter. The act's own code is still held by its unverified time until a date decides it.

D100 (finding 1). relations.Context's examination Counter (the pairing table's unresolved sessions) counted a digital
rectal examination Gemini lists as the colonoscopy's examination (device manual, verified; the attested C2MEM-029 r1 E9
form), so 'No biopsies were taken.' beside the biopsy asked 'In which procedure ...?' (session_unresolved) and never the
contradiction, while coverage read the colonoscopy as the one session. Now it counts only ENDOSCOPIC examinations
(events.endoscopic_examination, FINAL 5.6 E13).

RECORDED: the committed FRESH-2 run 1 of W1-u30a-rel-f4-unread-before-017 (tests/fixtures/interpretation), its request
and body checked against the manifest, read verbatim. SYNTHETIC: the shared S08 builders, and the chain built like
tests.test_pipeline_assess_events (the replay interpreter, the in-process Corti fake, the legacy entry points failing if
called). Nothing is sent."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from django.test import SimpleTestCase

from studio import jobs, models
from studio.ingest.extract import extract_paste
from studio.interpretation import adapter, coverage, events, facts, normalize, relations, verify
from studio.interpretation import assess as events_engine
from studio.interpretation import read as interpretation_read
from studio.reference.store import InMemoryReferenceLookup
from studio.types import EvidenceSpan, NormalizedResponse, PageSpan, ProviderCode
from tests.support import factories as f
from tests.test_interpretation_coverage import hemoclips
from tests.test_interpretation_events import (COLONOSCOPE, L1, POLYP, asked, check, colonoscopy, exam, inventory,
                                              proposal, reached, removed, run)
from tests.test_interpretation_identity import a, accepted, act, les, sc, snare, tg
from tests.test_interpretation_r3_claims import held_both, stone_clearance
from tests.test_interpretation_r3_currency import (DATE_LINE, NOT_STATED, OPENED, SEVERAL_ONE_LINE, SEVERAL_TWO_LINES,
                                                   STATED)
from tests.test_interpretation_replay import FIXTURES, MANIFEST, text_and_pages
from tests.test_pipeline_assess_events import HEAD, EventsCase, envelope

ENTRIES = {entry['id']: entry for entry in MANIFEST['documents']}


def conflicts_check(result):
    return next(item for item in result.encounter_checks if item.id == 'services.conflicts')


# --- D98 (finding 7): the attested 'unknown' time on a removal --------------------------------------------------------

ATTESTED = 'W1-u30a-rel-f4-unread-before-017'
SNARE_LINE = 'It was removed piecemeal with a cold snare in four pieces.'
BIOPSY_LINE = 'During this procedure, cold forceps biopsies of the polyp were taken.'


def pasted(raw: str) -> tuple:
    """The revision text and pages of a PASTE of ``raw`` (tests.test_interpretation_replay.text_and_pages' tiling)."""
    result = extract_paste(raw)
    spans = sorted(result.pages, key=lambda span: span.start)
    tiled = []
    for index, span in enumerate(spans):
        end = spans[index + 1].start if index + 1 < len(spans) else len(result.text)
        tiled.append(PageSpan(page=span.page, start=tiled[-1].end if tiled else 0, end=end))
    return result.text, tuple(tiled)


def attested_answer() -> tuple:
    """(Gemini's recorded answer, the recorded document) of FRESH-2 run 1 of ATTESTED, verbatim: the request the
    document frames and the body's sha256 checked against the manifest, the answer read as adapter.answer_text gives
    it."""
    entry = ENTRIES[ATTESTED]
    text, pages = text_and_pages(entry)
    request = adapter.Interpreter().build_request(text, pages, 'paste')
    assert request.canonical_sha256 == entry['request_sha256'], ATTESTED
    run_1 = entry['runs']['r1']
    body = (FIXTURES / run_1['body']).read_bytes()
    assert hashlib.sha256(body).hexdigest() == run_1['body_sha256'], ATTESTED
    return json.loads(adapter.answer_text(request, body)), (FIXTURES / entry['document']).read_bytes().decode('utf-8')


def biopsy_event() -> dict:
    """The one on-contract event the finding adds for BIOPSY_LINE (P7): a cold forceps biopsy of Gemini's own lesion L1,
    its words verbatim, its time the whole present-encounter frame 'During this procedure', the documenting team."""
    return {'id': 'E3', 'procedure': a('colonoscopy', 'Colonoscopy', ['P3']),
            'kind': a('biopsy', 'cold forceps biopsies', ['P7']),
            'technique': a('cold_forceps', 'cold forceps', ['P7']),
            'target': tg('L1', 'ascending_colon', 'the polyp', ['P7']),
            'time': a('current_encounter', 'During this procedure', ['P7']), 'performer': a('documenting_team'),
            'status': a('performed', 'were taken', ['P7']), 'scope': sc(), 'purpose': a('not_stated'), 'part_of': '',
            'sequence': 0, 'contradicts': []}


def attested(snare_time=None, *, open_questions: bool = True) -> tuple:
    """(the normalized inventory, the assessment) of the finding's input: the recorded document and answer verbatim,
    plus BIOPSY_LINE and its event; ``snare_time`` replaces the snare's (E2) time when given. Read and assessed as
    score_fresh.py does: the gemini-context facts with no member values, one replayed proposer response citing 45380
    on the biopsy line and 45385 on the snare line, an empty reference lookup."""
    answer, raw = attested_answer()
    assert raw.endswith(SNARE_LINE + '\n'), raw[-80:]
    answer['passages'].append({'id': 'P7', 'text': BIOPSY_LINE})
    answer['events'].append(biopsy_event())
    if snare_time is not None:
        next(item for item in answer['events'] if item['id'] == 'E2')['time'] = snare_time
    if not open_questions:
        answer['open_questions'] = []
    text, pages = pasted(raw + BIOPSY_LINE + '\n')
    parsed = interpretation_read.read(json.dumps(answer))
    assert not isinstance(parsed, interpretation_read.Refusal), parsed
    inv = normalize.normalize(parsed, text)
    derived = facts.derive(inv, {})
    codes = []
    for code, quote in (('45380', BIOPSY_LINE), ('45385', SNARE_LINE)):
        start = text.index(quote)
        codes.append(ProviderCode('selected', 'cpt', code, 'UNVERIFIED PROVIDER WORDING',
                                  (EvidenceSpan(0, start, start + len(quote), quote, True),)))
    result = events_engine.assess(
        inventory=inv, context=dict(derived.facts), normalized=NormalizedResponse('replay', 'test@1', tuple(codes)),
        provider_status='succeeded', reference=InMemoryReferenceLookup((), {}), text=text, pages=pages,
        extraction_status='ok', extraction_messages=())
    return inv, result


class D98AttestedUnknownTime(SimpleTestCase):
    """Finding 7's input: the snare of the 22 mm polyp, its time 'unknown' worded 'Once' as Gemini recorded it, holds
    the biopsy of that polyp (biopsy_of_removed_lesion): 45380 is held as part of the removal, never READY, as the
    installed release holds it; 45385 keeps its own time question."""

    def test_d98_the_attested_unknown_time_snare_keeps_the_biopsy_of_its_polyp_held(self):
        variants = {'as recorded': {}, 'unknown with no words': {'snare_time': a('unknown')},
                    "Gemini's open questions removed": {'open_questions': False}}
        for name, options in variants.items():
            inv, result = attested(**options)
            reading = events.Reading.of(inv)
            snared, biopsy = reading.events['E2'], reading.events['E3']
            with self.subTest(name):
                self.assertEqual((snared['time']['value'], snared['time']['state']), ('unknown', 'absent'))
                self.assertEqual(snared['current'], 'unresolved')
                self.assertTrue(coverage.possibly_current(snared))
                self.assertTrue(coverage.current_performed(snared))
                self.assertTrue(relations._possibly_current(snared))
                self.assertEqual(coverage.bundled_reason(reading, biopsy), coverage.COMMON['biopsy_of_removed_lesion'])
                p = proposal(result, '45380')
                self.assertEqual((p.bucket, p.status, asked(p), p.support['reason']),
                                 ('selected', 'needs_clarification', ['performed_status'], events.BUNDLED))
                self.assertIn(coverage.COMMON['biopsy_of_removed_lesion'], check(p, 'service.status').detail)
                own = proposal(result, '45385')
                self.assertEqual((own.status, asked(own)), ('needs_clarification', ['event_time']))

    def test_d98_control_a_current_time_holds_it_and_an_earlier_one_releases_it(self):
        """The reference: the same snare with a current_encounter time (worded 'Once', unanchored) holds 45380 exactly
        as the unknown time now does; an earlier_encounter time is not current, verified or not (D62), so the biopsy
        taken 'During this procedure' of a polyp removed on another occasion is not bundled into that removal."""
        inv, result = attested(a('current_encounter', 'Once', ['P5', 'P6']))
        p = proposal(result, '45380')
        self.assertEqual((p.status, p.support['reason']), ('needs_clarification', events.BUNDLED))
        inv, result = attested(a('earlier_encounter', 'Once', ['P5', 'P6']))
        reading = events.Reading.of(inv)
        self.assertFalse(coverage.possibly_current(reading.events['E2']))
        self.assertFalse(relations._possibly_current(reading.events['E2']))
        self.assertEqual(coverage.bundled_reason(reading, reading.events['E3']), '')


class D98PossiblyCurrent(SimpleTestCase):
    def test_d98_an_unknown_time_is_possibly_current_and_only_an_earlier_or_future_one_is_not(self):
        """Both readers, over the states normalize gives a time of each value (an 'unknown' time is bound absent): an
        unknown time, opened by Gemini's question or not, is possibly current; a current_encounter time is, whatever its
        reasons (D62, D68); an earlier_encounter or future time never is, verified or not."""
        dated = [('verified', []), ('unverified', ['date_mismatch']), ('unverified', ['date_unchecked']),
                 ('unverified', ['time_marker_missing']), ('discarded', ['passage_unlocated'])]
        states = {'current_encounter': dated + [('unverified', ['other_occasion']),
                                                ('unverified', ['current_unanchored'])],
                  'unknown': [('absent', [])], 'earlier_encounter': dated, 'future': dated}
        for value, found in states.items():
            for state, reasons in found:
                for opened in (False, True):
                    time = {'value': value, 'state': state, 'open': opened, 'reasons': reasons}
                    record = {'time': time, 'current': verify.currency(time)}
                    with self.subTest(value=value, state=state, reasons=reasons, opened=opened):
                        expected = value in ('current_encounter', 'unknown')
                        self.assertEqual(coverage.possibly_current(record), expected)
                        self.assertEqual(relations._possibly_current(record), expected)
        self.assertFalse(coverage.possibly_current({}))  # no time at all is no time Gemini gave


class D98Siblings(SimpleTestCase):
    """The finding's three siblings, each whole's time 'unknown' (worded 'Once', and with no words), and relations'
    half: the part's code is held exactly as beside a current whole, never READY."""

    UNKNOWN = {"'Once'": lambda passage: a('unknown', 'Once', [passage]), 'no words': lambda passage: a('unknown')}

    def test_d98_the_lift_injection_stays_bundled_into_an_unknown_time_emr(self):
        polyp = 'In the ascending colon there was a 25 mm flat polyp.'
        lift = 'A submucosal injection of saline with methylene blue was given to lift the lesion.'
        line = 'Once, the lesion was removed by endoscopic mucosal resection in three pieces.'
        lesion = les('L1', '25 mm flat polyp', 'P2', landmark='ascending_colon', site_words='ascending colon',
                     size_words='25 mm')
        for name, time in self.UNKNOWN.items():
            injection = act('E2', 'P3', 'injection', 'submucosal injection', status_words='was given',
                            target=tg('L1', 'ascending_colon', 'the lesion', ['P3']),
                            purpose=a('lift_for_resection', 'to lift the lesion', ['P3']))
            resection = act('E3', 'P4', 'emr', 'endoscopic mucosal resection',
                            status_words='was removed by endoscopic mucosal resection',
                            target=tg('L1', 'ascending_colon', 'the lesion', ['P4']), time=time('P4'))
            inv, text = inventory({'P1': COLONOSCOPE, 'P2': polyp, 'P3': lift, 'P4': line},
                                  events=[exam(), injection, resection], lesions=[lesion], reach=[reached()])
            result = run(inv, text, [('45381', lift), ('45390', line)])
            with self.subTest(name):
                self.assertEqual(events.Reading.of(inv).events['E3']['time']['state'], 'absent')
                p = proposal(result, '45381')
                self.assertEqual((p.status, p.support['reason']), ('needs_clarification', events.BUNDLED))
                self.assertEqual(asked(proposal(result, '45390')), ['event_time'])

    def test_d98_the_egd_stays_held_beside_an_unknown_time_upper_eus(self):
        egd_line = 'EGD: the gastroscope was advanced to the second portion of the duodenum.'
        eus_line = 'Once, the linear echoendoscope was introduced and advanced to the second portion of the duodenum.'
        fna_line = 'A 2.5 cm hypoechoic mass in the pancreatic head was sampled with a 22-gauge needle, three passes.'
        for name, time in self.UNKNOWN.items():
            egd = exam('E1', 'P1', words='gastroscope', procedure=a('egd', 'gastroscope', ['P1']))
            eus = exam('E2', 'P2', words='linear echoendoscope', status_words='was introduced and advanced',
                       procedure=a('eus', 'linear echoendoscope', ['P2']), time=time('P2'))
            fna = act('E3', 'P3', 'fna', 'sampled', status_words='was sampled with a 22-gauge needle',
                      procedure=a('eus', 'needle', ['P3']), technique=a('needle', '22-gauge needle', ['P3']),
                      target=tg('', 'pancreas', 'pancreatic head', ['P3']))
            inv, text = inventory({'P1': egd_line, 'P2': eus_line, 'P3': fna_line}, events=[egd, eus, fna],
                                  reach=[reached('E1', 'second_portion_duodenum', 'second portion of the duodenum',
                                                 'P1'),
                                         reached('E2', 'second_portion_duodenum', 'second portion of the duodenum',
                                                 'P2')])
            sessions_ = coverage.sessions(events.Reading.of(inv))
            result = run(inv, text, [('43235', egd_line), ('43242', fna_line)])
            with self.subTest(name):
                # D70: an upper EUS examination that may be this encounter's is a doubt: the EGD may be its portion
                self.assertEqual((sessions_['gi.eus'].examinations, sessions_['gi.eus'].possible,
                                  sessions_['gi.egd'].part_of, sessions_['gi.egd'].possibly_part_of),
                                 ((), ('E2',), '', 'gi.eus'))
                p = proposal(result, '43235')
                self.assertEqual(p.status, 'needs_clarification')
                self.assertIn('base_included', asked(p))

    def test_d98_a_lithotripsy_left_unknown_still_claims_the_stone_clearance(self):
        line = 'Once, a 15 mm stone in the common bile duct was fragmented with mechanical lithotripsy.'
        for name, time in self.UNKNOWN.items():
            inv, text, lines = stone_clearance(line, time=time('P3'))
            with self.subTest(name):
                self.assertEqual(events.Reading.of(inv).events['E3']['time']['state'], 'absent')
                held_both(self, run(inv, text, [('43264', lines['P4']), ('43265', lines['P3'])]), 'event_time')

    def test_d98_a_bleeding_control_beside_an_unknown_time_polypectomy_is_asked(self):
        """relations._possibly_current: D41's procedural_adjunct bundling identity is recorded beside a removal whose
        time Gemini left 'unknown', so the bleeding control that names nothing is asked, never READY alone."""
        line = 'Once, a 6 mm sessile polyp in the sigmoid colon was removed with a cold snare.'
        clips = 'Immediate oozing from the polypectomy site was controlled with two hemoclips for hemostasis.'
        for name, time in self.UNKNOWN.items():
            removal = snare('E2', 'P2', target=tg('L1', 'sigmoid_colon', '6 mm sessile polyp in the sigmoid colon',
                                                  ['P2']), time=time('P2'))
            inv, text = colonoscopy(hemoclips(), polyp=removal, lines={'P2': line, 'P3': clips})
            with self.subTest(name):
                self.assertIn(('bundling_identity', 'E2', 'procedural_adjunct'),
                              [(item['type'], item['statement'], item['reason']) for item in inv.events['relations']
                               if item['event'] == 'E3'])
                p = proposal(run(inv, text, [('45385', line), ('45382', clips)]), '45382')
                self.assertEqual((p.status, asked(p), p.support['reason']),
                                 ('needs_clarification', ['act_target'], events.BUNDLING_IDENTITY))


# --- D99 (finding 8): a same-day denial beside a current time no date has checked yet --------------------------------

DATED_POLYP = 'On 11/09/2026, a 6 mm sessile polyp in the sigmoid colon was removed with a cold snare.'
DENIAL = 'Impression: No polypectomy was performed.'


def denial_answer(polyp_line: str = DATED_POLYP, time_words: str = 'On 11/09/2026', *, date_lines=None,
                  date_of_service=NOT_STATED, open_questions=(), denied: bool = True) -> tuple:
    """(Gemini's synthetic answer, the document's lines) of finding 8: a colonoscopy to the cecum (E1), the cold snare
    removal of a 6 mm sigmoid polyp (E2, L1) whose time Gemini gives as current_encounter worded ``time_words`` (no
    words when empty), and - when ``denied`` - 'Impression: No polypectomy was performed.' (E3: removal, not_performed,
    all_of_kind); no date line unless ``date_lines`` gives one."""
    lines = {**(date_lines or {}), 'P1': COLONOSCOPE, 'P2': polyp_line}
    removal = snare('E2', 'P2', target=tg('L1', 'sigmoid_colon', '6 mm sessile polyp in the sigmoid colon', ['P2']),
                    time=a('current_encounter', time_words, ['P2']) if time_words else a('current_encounter'))
    found = [exam(), removal]
    if denied:
        lines['P3'] = DENIAL
        found.append(act('E3', 'P3', 'removal', 'polypectomy', status='not_performed',
                         status_words='No polypectomy was performed', scope=sc('all_of_kind', 'No polypectomy',
                                                                               ['P3'])))
    lesion = les('L1', '6 mm sessile polyp', 'P2', landmark='sigmoid_colon', site_words='sigmoid colon',
                 size_words='6 mm')
    value = {'passages': [{'id': pid, 'text': text} for pid, text in lines.items()],
             'encounter': {'date_of_service': date_of_service, 'documenting_endoscopist': {'words': '', 'passages': []},
                           'team': [], 'anatomy': [], 'reach': [reached()], 'visit_facts': []},
             'lesions': [lesion], 'events': found, 'open_questions': list(open_questions)}
    return value, lines


def denial_document(polyp_line: str = DATED_POLYP, time_words: str = 'On 11/09/2026', **options) -> tuple:
    """(the normalized inventory, the document's text, the snare line) of denial_answer."""
    value, lines = denial_answer(polyp_line, time_words, **options)
    text = '\n'.join(lines.values()) + '\n'
    return normalize.normalize(accepted(value), text), text, polyp_line


def stored_relations(inv) -> list:
    return [(item['type'], item['statement'], item['event'], item['attribute'], item['reason'])
            for item in inv.events['relations']]


CONTRADICTED = [('contradiction', 'E3', 'E2', 'status', 'same_act')]
UNRESOLVED_TIME = [('unresolved', 'E3', 'E2', 'time', 'time_unresolved')]  # DECISIONS D128
# the finding's variants of the undated document: (document options, the snare line, its time words)
UNDATED = {
    'no date line': ({}, DATED_POLYP, 'On 11/09/2026'),
    "'several' dates on one line": (dict(date_lines=SEVERAL_ONE_LINE[0], date_of_service=SEVERAL_ONE_LINE[1]),
                                    DATED_POLYP, 'On 11/09/2026'),
    "'several' dates on two lines": (dict(date_lines=SEVERAL_TWO_LINES[0], date_of_service=SEVERAL_TWO_LINES[1]),
                                     DATED_POLYP, 'On 11/09/2026'),
    "the date line opened by Gemini's own question": (dict(date_lines={'P0': DATE_LINE}, date_of_service=STATED,
                                                           open_questions=OPENED), DATED_POLYP, 'On 11/09/2026'),
    "'On November 9, 2026'": ({}, DATED_POLYP.replace('On 11/09/2026', 'On November 9, 2026'),
                              'On November 9, 2026'),
}


class D99TimeRow(SimpleTestCase):
    """relations.time_row, on the attribute records normalize stores."""

    @staticmethod
    def side(value: str = 'current_encounter', state: str = 'verified', reasons=(), opened: bool = False,
             basis: str = 'stated', found=None) -> dict:
        return {'time': {'value': value, 'state': state, 'reasons': list(reasons), 'open': opened, 'basis': basis,
                         'literals': found or {}}}

    def test_d99_a_current_time_whose_only_failure_is_date_unchecked_pairs_as_current(self):
        unchecked = self.side(state='unverified', reasons=['date_unchecked'],
                              found={'dates': [{'value': '2026-11-09', 'precision': 'day'}]})
        default = self.side(basis='default')
        self.assertEqual(relations.time_row(default, unchecked), relations.Row('time', relations.SAME))
        self.assertEqual(relations.time_row(unchecked, default), relations.Row('time', relations.SAME))
        self.assertEqual(relations.time_row(unchecked, unchecked), relations.Row('time', relations.SAME))
        # DECISIONS D128 (1) moved this expectation: against another time a pending check is no difference - a date no
        # date has checked is no literal, and no fact (it was DIFFERENT, another_time, never hard). Beside a denial,
        # D128 (0) narrows the rest: tests.test_interpretation_r5_currency.D128TimeRow
        earlier = self.side('earlier_encounter', found={'markers': ['previously']})
        self.assertEqual(relations.time_row(earlier, unchecked),
                         relations.Row('time', relations.UNKNOWN, 'time_unresolved'))
        self.assertEqual(verify.exclusion_basis('time', unchecked['time']), '')
        self.assertFalse(verify.usable(unchecked['time']))  # the act's own code still reads it as unverified

    def test_d99_every_other_unverified_time_stays_unknown(self):
        """The control: only date_unchecked ALONE, on an unopened current_encounter time, is a pending date check."""
        others = {
            'date_unchecked with current_unanchored': self.side(state='unverified',
                                                                reasons=['date_unchecked', 'current_unanchored']),
            'date_unchecked with other_occasion': self.side(state='unverified',
                                                            reasons=['date_unchecked', 'other_occasion']),
            'date_unchecked, opened by an open question': self.side(state='unverified', reasons=['date_unchecked'],
                                                                    opened=True),
            'date_mismatch': self.side(state='unverified', reasons=['date_mismatch']),
            'current_unanchored': self.side(state='unverified', reasons=['current_unanchored']),
            'an earlier time date_unchecked': self.side('earlier_encounter', 'unverified', ['date_unchecked']),
            'a future time date_unchecked': self.side('future', 'unverified', ['date_unchecked']),
            'unknown': self.side('unknown', 'absent', basis='absent'),
            'discarded': self.side(state='discarded', reasons=['date_unchecked']),
        }
        default = self.side(basis='default')
        for name, other in others.items():
            with self.subTest(name):
                self.assertEqual(relations.time_row(default, other),
                                 relations.Row('time', relations.UNKNOWN, 'time_unresolved'))
                self.assertEqual(relations.time_row(other, default),
                                 relations.Row('time', relations.UNKNOWN, 'time_unresolved'))


class D99UndatedDenial(SimpleTestCase):
    """Finding 8's input and its variants: the undated note's dated snare beside the impression's denial is a
    CONTRADICTION, so 45385 asks conflict:snare once the member's date settles the day, as the installed release does,
    and the conflicts check and completeness state the conflict."""

    def assert_contradiction_asked(self, result):
        p = proposal(result, '45385')
        self.assertEqual((p.bucket, p.status, asked(p)), ('selected', 'needs_clarification', ['conflict:snare']))
        self.assertEqual(p.support['reason'], events.CONFLICT)
        self.assertEqual(conflicts_check(result).status, 'warn')
        self.assertIn('1 conflict in the record', result.completeness['reasons'])

    def test_d99_the_same_day_denial_is_a_contradiction_on_the_undated_note(self):
        """DECISIONS D128 (0) moved this pin's expectation: the act's own check is still pending at normalize, so the
        pair is UNRESOLVED(time) - stored before any date can say whether the snare is that day's."""
        for name, (options, line, words) in UNDATED.items():
            inv, _, _ = denial_document(line, words, **options)
            snared = next(item for item in inv.events['events'] if item['id'] == 'E2')
            with self.subTest(name):
                self.assertIsNone(inv.encounter_facts['date_of_service']['value'])
                self.assertEqual((snared['time']['state'], snared['time']['reasons']), ('unverified',
                                                                                        ['date_unchecked']))
                self.assertEqual(stored_relations(inv), UNRESOLVED_TIME)

    def test_d99_the_members_date_asks_the_contradiction(self):
        """DECISIONS D128 (0) moved this pin's expectation: with the member's equal date the re-judged time is usable,
        and the denial's UNRESOLVED(time) relation asks the contradiction as the statement's scope (D102); the conflicts
        check is pass (assess reuses the stored relation; recorded)."""
        for name, (options, line, words) in UNDATED.items():
            inv, text, line = denial_document(line, words, **options)
            with self.subTest(name):
                result = run(inv, text, [('45385', line)], user_values={'service_date': '2026-11-09'})
                p = proposal(result, '45385')
                self.assertEqual((p.bucket, p.status, asked(p)), ('selected', 'needs_clarification',
                                                                  ['statement_scope']))
                self.assertEqual(conflicts_check(result).status, 'pass')

    def test_d99_control_the_documents_own_date_asks_the_contradiction(self):
        inv, text, line = denial_document(date_lines={'P0': DATE_LINE}, date_of_service=STATED)
        self.assertEqual(stored_relations(inv), CONTRADICTED)
        self.assert_contradiction_asked(run(inv, text, [('45385', line)]))

    def test_d99_with_no_date_or_another_date_the_snare_stays_held(self):
        """No date decides the day, or the member's date differs from it: the code is held, never READY and never
        excluded."""
        inv, text, line = denial_document()
        for member in (None, '2026-11-10'):
            result = run(inv, text, [('45385', line)], user_values={'service_date': member} if member else {})
            with self.subTest(member=member):
                p = proposal(result, '45385')
                self.assertEqual((p.bucket, p.status), ('selected', 'needs_clarification'))

    def test_d99_an_earlier_denial_sets_the_act_apart_only_on_the_dated_document(self):
        """Beside a denial Gemini places at an earlier encounter ('Previously, no polyp was removed.', verified by its
        marker), only the document's OWN date sets the snare apart: the dated document's snare day is a usable current
        time, the pair is another time (INDEPENDENT, another_time), and 45385 is READY. On the undated note the snare's
        day is a pending check, and a pending check never sets a pair apart (DECISIONS D128 (1)): the relation is
        UNRESOLVED(time), and 45385 is held, never READY - asking the denial as its scope (statement_scope) with the
        member's date equal to the day, and its own time (event_time) with no date or another date.

        History: D99 read the pending check as current on both sides, so on the undated note the member's equal date
        made 45385 READY as the document's own date does (this test's earlier name, "...sets the act apart as the dated
        document does", said that); 437b708bb had held it (event_time) on the stale UNRESOLVED(time) relation. D128 (1)
        moved the undated note's expectations, and DECISIONS D143 (5) renamed the test to say what it asserts."""
        earlier = 'Previously, no polyp was removed.'
        for name, options, member, status in (
                ("the document's own date", dict(date_lines={'P0': DATE_LINE}, date_of_service=STATED), None, 'ready'),
                ("the undated note, the member's equal date", {}, '2026-11-09', 'needs_clarification'),
                ('the undated note, no date', {}, None, 'needs_clarification'),
                ("the undated note, the member's other date", {}, '2026-11-10', 'needs_clarification')):
            value, lines = denial_answer(denied=False, **options)
            lines['P3'] = earlier
            value['passages'].append({'id': 'P3', 'text': earlier})
            value['events'].append(act('E3', 'P3', 'removal', 'removed', status='not_performed',
                                       status_words='no polyp was removed', scope=sc('all_of_kind', 'no polyp', ['P3']),
                                       time=a('earlier_encounter', 'Previously', ['P3'])))
            text = '\n'.join(lines.values()) + '\n'
            inv = normalize.normalize(accepted(value), text)
            with self.subTest(name):
                self.assertEqual(stored_relations(inv), [('independent', 'E3', 'E2', 'time', 'another_time')]
                                 if options else UNRESOLVED_TIME)  # D128 (1): the undated note's pending check
                p = proposal(run(inv, text, [('45385', DATED_POLYP)],
                                 user_values={'service_date': member} if member else {}), '45385')
                self.assertEqual(p.status, status)
                if status != 'ready':
                    self.assertEqual(asked(p), ['statement_scope'] if member == '2026-11-09' else ['event_time'])

    def test_d99_control_a_date_unchecked_examination_never_unresolves_the_pairing(self):
        """D99 is the time ROW's. The pairing table's unresolved sessions still count VERIFIED current examinations
        (D87): an aside examination Gemini calls current, dated in its own words ('On 03/14/2024, a colonoscopy ...'),
        on the undated note is a doubt, never a second examination of the pairing's session. Counted as current there,
        it would make the denial's pair session_unresolved and take the contradiction's question, where the document's
        own date (which makes it date_mismatch) asks the contradiction: a doubt never takes another doubt's
        question."""
        aside = 'On 03/14/2024, a colonoscopy to the cecum was performed.'
        for name, options, member in (("the undated note, the member's date", {}, '2026-11-09'),
                                      ('the undated note, no date', {}, None),
                                      ("the document's own date", dict(date_lines={'P0': DATE_LINE},
                                                                       date_of_service=STATED), None)):
            value, lines = denial_answer(POLYP, '', **options)
            lines['P4'] = aside
            value['passages'].append({'id': 'P4', 'text': aside})
            value['events'].append(exam('E4', 'P4', words='colonoscopy', status_words='was performed',
                                        time=a('current_encounter', 'On 03/14/2024', ['P4'])))
            text = '\n'.join(lines.values()) + '\n'
            inv = normalize.normalize(accepted(value), text)
            reading = events.Reading.of(inv)
            with self.subTest(name):
                self.assertNotEqual(reading.events['E4']['time']['state'], 'verified')
                self.assertEqual(reading.context.unresolved_sessions, frozenset())
                self.assertEqual(stored_relations(inv), CONTRADICTED)
                p = proposal(run(inv, text, [('45385', POLYP)],
                                 user_values={'service_date': member} if member else {}), '45385')
                self.assertEqual(p.status, 'needs_clarification')
                self.assertIn('conflict:snare', asked(p))

    def test_d99_control_the_acts_own_code_is_still_held_by_its_unchecked_time(self):
        """With no denial there is no pair: the undated note's dated snare is held on its own time until a date decides
        it, and READY once the member's date equals its day (D67's control, unchanged)."""
        inv, text, line = denial_document(denied=False)
        self.assertEqual(stored_relations(inv), [])
        held = proposal(run(inv, text, [('45385', line)]), '45385')
        self.assertEqual((held.status, asked(held)), ('needs_clarification', ['event_time']))
        self.assertEqual(proposal(run(inv, text, [('45385', line)], user_values={'service_date': '2026-11-09'}),
                                  '45385').status, 'ready')


class D99Chain(EventsCase):
    """D99 through the production chain (extract, interpret by replay, analyze, predict with the Corti fake, assess),
    the legacy reader's entry points failing if called: the member's date at upload, and saved afterwards
    (jobs.change_context, on the frozen inventory), each asks the contradiction."""
    corti_groups = ((('45385', DATED_POLYP),),)

    def upload_with(self, user_values):
        value, lines = denial_answer()
        text = HEAD + '\n'.join(lines.values()) + '\n'
        encounter = models.Encounter.objects.create(workspace=self.ws, title='Synthetic note', created_by=self.user,
                                                    user_values=user_values)
        revision = f.pasted_revision(encounter, self.user, text, extract=False)
        jobs.start_pipeline(revision, self.user)
        self.run_next(models.Job.EXTRACT)
        revision.refresh_from_db()
        kind = jobs._participant_document(revision)[0]
        request = adapter.build_request(revision.text, jobs._participant_pages(revision), kind)
        folder = Path(self.replay) / adapter.NAME
        folder.mkdir(exist_ok=True)
        (folder / f'{request.canonical_sha256}.json').write_bytes(envelope(value))
        return encounter

    def drained(self, encounter):
        with self.legacy_reader_fails():
            ran = self.drain()
        self.assertTrue(ran and all(job.state == models.Job.SUCCEEDED for job in ran),
                        [(job.kind, job.state, job.error) for job in ran])
        encounter.refresh_from_db()
        assessment = models.Assessment.objects.get(pk=encounter.current_assessment_id)
        self.assertEqual(assessment.engine_version, 'cpt-studio-events@1')
        stored = models.EventInventory.objects.get(pk=assessment.event_inventory_id)
        return assessment, stored

    def assert_contradiction_asked(self, assessment, stored):
        """DECISIONS D128 (0) moved this pin's expectations: the frozen inventory's pair is UNRESOLVED(time), and with
        the member's equal date 45385 asks the denial as its scope (D102) with the conflicts check pass."""
        self.assertEqual(assessment.context.facts['service_date']['state'], 'supplies')
        self.assertEqual(stored_relations(stored), UNRESOLVED_TIME)
        held = self.proposal(assessment, '45385')
        self.assertEqual((held.status, [spec.fact for spec in held.clarifications.all()]),
                         ('needs_clarification', ['statement_scope']))
        found = next(item for item in assessment.encounter_checks if item['id'] == 'services.conflicts')
        self.assertEqual(found['status'], 'pass')
        self.assertNotIn('1 conflict in the record', assessment.completeness['reasons'])

    def test_d99_the_members_date_at_upload_and_saved_afterwards_asks_the_contradiction(self):
        self.assert_contradiction_asked(*self.drained(self.upload_with({'service_date': '2026-11-09'})))
        encounter = self.upload_with({})
        first, _ = self.drained(encounter)
        self.assertEqual(self.proposal(first, '45385').status, 'needs_clarification')
        with self.legacy_reader_fails():
            jobs.change_context(encounter, self.user, {'service_date': '2026-11-09'})
        saved, stored = self.drained(encounter)
        self.assertNotEqual(saved.pk, first.pk)
        self.assert_contradiction_asked(saved, stored)


# --- D100 (finding 1): a digital rectal examination is no session for the pairing table ------------------------------

BIOPSY = 'Cold forceps biopsies were taken from the transverse colon.'
NO_BIOPSY = 'No biopsies were taken.'
NO_POLYP = 'No polyp was removed.'
DRE = 'Digital rectal examination showed normal sphincter tone, no palpable mass, and no gross blood.'


def dre(eid: str, passage: str, technique=None) -> dict:
    """The attested C2MEM-029 r1 E9 form: a colonoscopy examination, its device manual ('Digital'), target the rectum
    ('rectal'), status performed ('Digital rectal examination showed'), time and performer the frame defaults."""
    return act(eid, passage, 'examination', 'Digital rectal examination',
               status_words='Digital rectal examination showed',
               technique=technique or a('manual', 'Digital', [passage]), target=tg('', 'rectum', 'rectal', [passage]))


def biopsy_document(fourth=None, *, dre_first: bool = False, fourth_line: str = DRE):
    """Finding 1's document: the colonoscopy to the cecum, the transverse colon biopsy (E2), 'No biopsies were taken.'
    (E3, all_of_kind) and ``fourth`` - an examination event built (eid, passage) for ``fourth_line``, the DRE line by
    default, or None for none."""
    order = ('dre', 'col', 'bx', 'no') if dre_first else ('col', 'bx', 'no', 'dre')
    ids = {name: f'P{index}' for index, name in enumerate(order, 1)}
    lines = {ids['col']: COLONOSCOPE, ids['bx']: BIOPSY, ids['no']: NO_BIOPSY}
    found = [exam('E1', ids['col']),
             act('E2', ids['bx'], 'biopsy', 'biopsies', status_words='were taken',
                 technique=a('cold_forceps', 'Cold forceps', [ids['bx']]),
                 target=tg('', 'transverse_colon', 'transverse colon', [ids['bx']])),
             act('E3', ids['no'], 'biopsy', 'biopsies', status='not_performed', status_words='No biopsies were taken',
                 scope=sc('all_of_kind', 'No', [ids['no']]))]
    if fourth is not None:
        lines[ids['dre']] = fourth_line
        found.append(fourth('E4', ids['dre']))
    lines = {pid: lines[pid] for pid in sorted(lines)}
    return inventory(lines, events=found, reach=[reached('E1', 'cecum', 'cecum', ids['col'])])


def snare_document(fourth=None):
    """The snare analogue: the colonoscopy, the sigmoid snare (E2, POLYP), 'No polyp was removed.' (E3, all_of_kind)
    and ``fourth`` on the DRE line."""
    lines = {'P1': COLONOSCOPE, 'P2': POLYP, 'P3': NO_POLYP}
    found = [exam(), removed(), act('E3', 'P3', 'snare', 'removed', status='not_performed',
                                    status_words='No polyp was removed', scope=sc('all_of_kind', 'No', ['P3']))]
    if fourth is not None:
        lines['P4'] = DRE
        found.append(fourth('E4', 'P4'))
    return inventory(lines, events=found, lesions=[L1], reach=[reached()])


class D100DigitalRectalExamination(SimpleTestCase):
    """Finding 1's input: the DRE beside the colonoscopy never makes the pairing's session unresolved, so the denial
    beside the act of its kind is the contradiction, asked as such - as without the DRE line, and as the installed
    release asks it (conflict:biopsy)."""

    def assert_asked(self, inv, text, code: str, line: str, kind: str):
        reading = events.Reading.of(inv)
        self.assertEqual(stored_relations(inv), CONTRADICTED)
        self.assertEqual(reading.context.unresolved_sessions, frozenset())
        session = coverage.sessions(reading)['gi.colonoscopy']
        self.assertEqual((session.event, session.unresolved, session.examinations), ('E1', False, ('E1',)))
        result = run(inv, text, [(code, line)])
        p = proposal(result, code)
        self.assertEqual((p.status, asked(p)), ('needs_clarification', [f'conflict:{kind}']))
        self.assertEqual(conflicts_check(result).status, 'warn')
        self.assertIn('1 conflict in the record', result.completeness['reasons'])

    def test_d100_a_digital_rectal_examination_never_unresolves_the_pairing(self):
        for name, dre_first in (('the DRE line last', False), ('the DRE line first', True)):
            inv, text = biopsy_document(dre, dre_first=dre_first)
            with self.subTest(name):
                found = events.Reading.of(inv).events['E4']
                self.assertEqual((found['technique']['value'], found['technique']['state'], found['current']),
                                 ('manual', 'verified', 'yes'))
                self.assertFalse(events.endoscopic_examination(found))
                self.assert_asked(inv, text, '45380', BIOPSY, 'biopsy')

    def test_d100_the_snare_analogue_asks_the_contradiction(self):
        inv, text = snare_document(dre)
        self.assert_asked(inv, text, '45385', POLYP, 'snare')

    def test_d100_control_without_the_dre_line(self):
        for inv, text, code, line, kind in ((*biopsy_document(), '45380', BIOPSY, 'biopsy'),
                                            (*snare_document(), '45385', POLYP, 'snare')):
            with self.subTest(code):
                self.assert_asked(inv, text, code, line, kind)

    def test_d100_control_a_second_endoscopic_examination_still_unresolves_the_pairing(self):
        """D87's rule, kept: two verified current ENDOSCOPIC examinations leave the pairing's session unresolved. E13
        reads a VERIFIED manual device only (an unstated or unverified device never sets an examination apart), so a
        digital examination whose device Gemini does not state, one whose manual device its words do not verify, and a
        second colonoscope, still count."""
        seconds = {
            'the DRE with no device stated': (lambda eid, passage: dre(eid, passage, technique=a('not_stated')), DRE),
            'the DRE whose manual device is not verified': (
                lambda eid, passage: dre(eid, passage, technique=a('manual', 'finger', [passage])), DRE),
            'a second colonoscope': (lambda eid, passage: exam(eid, passage, status_words='was reinserted'),
                                     'The colonoscope was reinserted to the cecum.'),
        }
        for name, (second, line) in seconds.items():
            inv, text = biopsy_document(second, fourth_line=line)
            found = events.Reading.of(inv).events['E4']
            with self.subTest(name):
                self.assertFalse(verify.usable(found['technique']) and found['technique']['value'] == 'manual')
                self.assertTrue(events.endoscopic_examination(found))
                self.assertEqual(events.Reading.of(inv).context.unresolved_sessions, frozenset({'gi.colonoscopy'}))
                self.assertEqual(stored_relations(inv), [('unresolved', 'E3', 'E2', 'procedure',
                                                          'session_unresolved')])
                p = proposal(run(inv, text, [('45380', BIOPSY)]), '45380')
                self.assertEqual(p.status, 'needs_clarification')
