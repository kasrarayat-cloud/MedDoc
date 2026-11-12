"""Variant repair, round 2 (2026-11-04): refutation round 2's L1/R05, L1/R06 and L1/R12 - a form a reader already
declares, written in a variant spelling or layout - read as the declared form is, failing closed (declared before code in
tests/fixtures/gi4/declarations/cux-r2-variants.json).

- V05 (R8 D8): the heading line of an indication section is never today's statement, with or without its final full
  stop; after it the section reads as before (today's report inside a titled report, the indication outside one). A
  history section's heading line already never is.
- V06 (P1 rule 2, the lead's L3, R2a): an act compound's hyphen in its Unicode spellings (U+2010 to U+2014) is read
  wherever the ASCII hyphen is: the inventory, its doubtful compounds and field labels, a participle's predicate reading
  and the own-passage release.
- V12 (R8 D12): "not seen in person" hyphenated or contracted is cues.NOT_IN_PERSON's phrase, read on its plain form's
  path, and the phrase's own words never clear its own hold (two spaces, a line break, a curly apostrophe).
The space form "biopsy proven", the noun compound "polypectomy scar" and "not evaluated in person" are new wording and
read as installed (ops.gi4.battery.R2V_RESIDUALS). Every document is synthetic. No database, nothing sent.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from django.test import SimpleTestCase

from ops.gi4 import battery
from studio.gi import cues, detect, services
from tests.test_cux_hold import (CC, CECUM, EMDAY, TITLED, TODAY_BX, TWIN, acts, em_chassis, proposal, row, run, sel,
                                 span, state)

DECLARATION = json.loads((Path(__file__).resolve().parent / 'fixtures' / 'gi4' / 'declarations' / 'cux-r2-variants.json')
                         .read_text(encoding='utf-8'))
DECLARED = {(name, code): after for name, code, _, after in DECLARATION['battery']}
UNMOVED = {tuple(key.split(' | ')): value for key, value in DECLARATION['unmoved'].items()}
PREFIX = 'R8 R2 V '
DASHES = ('\u2010', '\u2011', '\u2012', '\u2013', '\u2014')  # hyphen, non-breaking hyphen, figure dash, en dash, em dash
HELD, READY = 'selected/needs_clarification', 'selected/ready'
B = 'SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\n'
DAY = date(2026, 10, 14)
EM_DAY = date(2026, 10, 26)


def outcome(result, code):
    item = proposal(result, code)
    return f'{item.bucket}/{item.status}'


class VariantRowsTests(SimpleTestCase):
    """Every 'R8 R2 V ' battery row ends where the declaration says, with no violation; its other codes keep their base
    state (measured on e25286af0 with the rows added); the residual rows read as installed."""

    def test_the_rows(self):
        names = DECLARATION['battery_rows_added']
        self.assertEqual(sorted(names), sorted(n for n in battery.CASES if n.startswith(PREFIX)))
        self.assertEqual(len(names), 24)
        for name in names:
            result = row(name)
            for code in result['proposals']:
                with self.subTest(name, code=code):
                    self.assertEqual(state(result, code), DECLARED.get((name, code)) or UNMOVED[(name, code)])
                    self.assertEqual(result['proposals'][code]['violations'], [])

    def test_the_residuals_read_as_installed(self):
        recorded = DECLARATION['residuals_measured']['rows']
        self.assertEqual(sorted(recorded), sorted(battery.R2V_RESIDUALS))
        m = battery.modules()
        for name, (text, codes) in battery.R2V_RESIDUALS.items():
            with self.subTest(name):
                self.assertNotIn(name, battery.CASES)
                self.assertNotIn(name, battery.R8_USER)
                result = battery.run_row(m, name, text, codes, battery.R2V_RESIDUAL_USER.get(name))
                self.assertEqual({code: state(result, code) for code in result['proposals']}, recorded[name])
                # a recorded residual: READY where the honest truth says it is not done today
                self.assertEqual([p['violations'] for p in result['proposals'].values()],
                                 [['READY where the truth says not done today']])


# --- V05: an indication's heading line ------------------------------------------------------------------------------

SNARE_LINE = 'Indication: Surveillance after a sigmoid polyp was removed with a hot snare'


class IndicationHeadingLineTests(SimpleTestCase):
    """V05 (refutation L1/R05): inside a titled report the heading line of an indication section is the indication's
    whatever it ends with; only that line - today's report after it reads as before, and outside a titled report the
    whole paragraph stays the indication's, as before."""

    def snare_reading(self, line):
        """(the snare acts' statuses, 45385's outcome citing the line and the reach sentence, 45380's on today's biopsy)"""
        text = TITLED.format(indication=line, body=TODAY_BX)
        result = run(text, [sel('45380', span(text, TODAY_BX)), sel('45385', span(text, line), span(text, CECUM))])
        return (sorted(status for _, kind, status in acts(text) if kind == 'snare'), outcome(result, '45385'),
                outcome(result, '45380'))

    def test_the_heading_line_is_the_indications_whatever_it_ends_with(self):
        for heading in ('Indication:', 'Indications:', 'Reason for procedure:', 'Indication for procedure:'):
            for end in ('', ';', ',', ' -', '.', '!'):
                line = SNARE_LINE.replace('Indication:', heading, 1) + end
                with self.subTest(line):
                    self.assertEqual(self.snare_reading(line), (['uncertain'], HELD, READY))
        dash = 'Indication: surveillance - sigmoid polyp removed with hot snare'
        text = TITLED.format(indication=dash, body=TODAY_BX)
        result = run(text, [sel('45380', span(text, TODAY_BX)), sel('45385', span(text, dash))])
        self.assertEqual((outcome(result, '45385'), outcome(result, '45380')), (HELD, READY))

    def test_the_part_is_the_heading_line_only(self):
        text = TITLED.format(indication=SNARE_LINE, body=TODAY_BX)
        start = text.index(SNARE_LINE)
        found = [(p.start, p.end) for p in services.parts(text) if p.kind == 'indication']
        self.assertEqual(found, [(start, start + len(SNARE_LINE) + 1)])  # the line and its newline, nothing after it
        after = [p.kind for p in services.parts(text) if p.start >= start + len(SNARE_LINE) + 1]
        self.assertTrue(after and set(after) == {'report'}, after)

    def test_statement_line_end_keeps_its_full_stop_test(self):
        from studio.gi import sections
        for line, complete, partial in ((SNARE_LINE, False, True), (SNARE_LINE + '.', True, True),
                                        ('Indication:', False, False)):
            text = TITLED.format(indication=line, body=TODAY_BX)
            section = next(s for s in sections.layout(text).sections if s.kind == 'indication')
            with self.subTest(line):
                self.assertEqual(services._statement_line_end(text, section) is not None, complete)
                self.assertEqual(services._statement_line_end(text, section, complete=False) is not None, partial)

    def test_controls_todays_acts_after_the_line_stay_ready(self):
        # D8's trap: today's biopsy right under an unterminated indication line, with no heading between
        for line in ('Indication: surveillance', SNARE_LINE, SNARE_LINE + ';'):
            text = TITLED.replace('{indication}\nProcedure: Colonoscopy\n' + CECUM + '\n{body}\n',
                                  line + '\n' + TODAY_BX + '\nProcedure: Colonoscopy\n' + CECUM + '\n')
            with self.subTest(line):
                self.assertIn(('gi.colonoscopy', 'biopsy', 'performed'), acts(text))
                self.assertEqual(outcome(run(text, [sel('45380', span(text, TODAY_BX))]), '45380'), READY)
        snare = 'A 9 mm polyp in the sigmoid colon was removed with a hot snare.'
        text = TITLED.format(indication=SNARE_LINE, body=snare)
        self.assertIn(('gi.colonoscopy', 'snare', 'performed'), acts(text))
        self.assertEqual(outcome(run(text, [sel('45385', span(text, snare))]), '45385'), READY)

    def test_outside_a_titled_report_the_paragraph_stays_the_indications(self):
        # the period rule's protection of a multi-line indication: its next line never becomes today's report
        second = 'A sigmoid polyp was removed with a hot snare.'
        for line in ('Indication: Surveillance after polypectomy', 'Indication: surveillance;'):
            text = (B + 'Date of service: 2026-10-14\nPlace of service: Ambulatory surgery center\n' + line + '\n' + second
                    + '\n\nProcedure: Colonoscopy\n' + CECUM + '\n' + TODAY_BX + '\n')
            with self.subTest(line):
                self.assertNotIn(('gi.colonoscopy', 'snare', 'performed'), acts(text))
                result = run(text, [sel('45380', span(text, TODAY_BX)), sel('45385', span(text, second))])
                self.assertEqual((outcome(result, '45385'), outcome(result, '45380')), (HELD, READY))

    def test_a_history_heading_line_is_never_todays_either(self):
        for line in ('History: a sigmoid polyp was removed with a hot snare',
                     'History: a sigmoid polyp was removed with a hot snare.',
                     'Prior procedures: a sigmoid polyp was removed with a hot snare'):
            with self.subTest(line):
                self.assertEqual(self.snare_reading(line)[1:], (HELD, READY))
                self.assertNotIn('performed', [s for _, kind, s in acts(TITLED.format(indication=line, body=TODAY_BX))
                                               if kind == 'snare'])


# --- V06: an act compound's hyphen in its Unicode spellings ----------------------------------------------------------

def compound(dash):
    return f'Surveillance of biopsy{dash}proven Barrett esophagus was performed.'


EGD = (B + 'Upper endoscopy report (fictional)\nDate of service: 2026-10-14\nPlace of service: Ambulatory surgery center\n'
       'Procedure: EGD\nThe gastroscope was advanced to the second portion of the duodenum.\n')
COLON = (B + 'Colonoscopy report (fictional)\nDate of service: 2026-10-14\nPlace of service: Ambulatory surgery center\n'
         'Procedure: Colonoscopy\n' + CECUM + '\n')
TODAY_SNARE = 'A 7 mm polyp in the sigmoid colon was removed with a cold snare.'
# sentences an act compound decides, beside today's own snare (a colonoscopy) or alone (an upper endoscopy)
COMPOUND_SENTENCES = (
    (EGD, 'Surveillance of biopsy{d}proven Barrett esophagus was performed.'),
    (EGD, 'Follow-up of a biopsy{d}confirmed gastric adenoma was performed.'),
    (COLON + TODAY_SNARE + '\n', 'The snare{d}resected sigmoid polyp was not retrieved.'),
    (COLON + TODAY_SNARE + '\n', 'The sigmoid polyp was neither snare{d}resected nor retrieved.'),
    (COLON + TODAY_SNARE + '\n', 'Polyp 1 - sigmoid colon, 7 mm\nSnare{d}resected: No\nForceps{d}removed: Yes'),
    (COLON + TODAY_SNARE + '\n', 'Hot snare{d}resected: Not done'),
    (COLON + TODAY_SNARE + '\n', 'Cold snare{d}resected: No'),
    (COLON, 'A 7 mm polyp in the sigmoid colon was snare{d}resected.'),
    (COLON, 'A clip on the snare{d}resected site.'),
    (COLON, 'Tattoo beside the snare{d}resected polyp.'),
    (COLON, 'Forceps biopsies near the snare{d}treated lesion.'),
    (COLON, 'Biopsy, snare{d}removed polyp.'),
    (COLON, 'Cold forceps of the snare{d}treated area.'),
)


def inventory_acts(text):
    inventory = services.build(text, service_date=DAY, routing=detect.route(text, DAY))
    return sorted((s.family, a.kind, a.status) for s in inventory.services for a in s.acts)


class CompoundHyphenSpellingTests(SimpleTestCase):
    """V06 (refutation L1/R06): an attributive act compound written with U+2010 to U+2014 reads exactly as the ASCII one
    does - as no act, as a doubtful compound read only as a denial, or as a predicate where an auxiliary makes it one."""

    def test_the_compound_is_read_with_each_hyphen_spelling(self):
        for dash in ('-',) + DASHES:
            text = compound(dash)
            with self.subTest(hex(ord(dash))):
                self.assertTrue(services._attributive_compound(text, text.index('biopsy'), text.index('biopsy') + 6))
                self.assertEqual(services._acts_in(text, 0, len(text)), [])
                self.assertTrue(services._compound_participle(text, text.index('proven')))
        for joiner in (' ', '\u2015', '\u2212', ' \u2013 ', ' - '):
            text = compound(joiner)
            with self.subTest(repr(joiner)):
                self.assertFalse(services._attributive_compound(text, text.index('biopsy'), text.index('biopsy') + 6))
                self.assertEqual([kind for kind, _, _ in services._acts_in(text, 0, len(text))], ['biopsy'])

    def test_each_spelling_reads_as_the_ascii_compound(self):
        for head, sentence in COMPOUND_SENTENCES:
            ascii_text = head + sentence.format(d='-') + '\n'
            want = inventory_acts(ascii_text)
            for dash in DASHES:
                with self.subTest(sentence, dash=hex(ord(dash))):
                    self.assertEqual(inventory_acts(head + sentence.format(d=dash) + '\n'), want)

    def test_a_doubtful_compound_label_is_the_item_a_denial_denies(self):
        for dash in ('-',) + DASHES:
            for label in (f'Snare{dash}resected', f'Hot snare{dash}resected', f'Cold snare{dash}resected'):
                with self.subTest(label):
                    self.assertTrue(services._own_question(label, 0, len(label), denial=True))
                    self.assertFalse(services._own_question(label, 0, len(label)))

    def test_the_own_passage_release_never_stands_on_it(self):
        for dash in DASHES:
            text = EGD + compound(dash) + '\n'
            with self.subTest(hex(ord(dash))):
                item = proposal(run(text, [sel('43239', span(text, compound(dash)))]), '43239')
                self.assertEqual((item.bucket, item.status), ('selected', 'needs_clarification'))
                self.assertNotEqual((item.support or {}).get('reason'), 'own_passage')

    def test_controls_a_biopsy_today_and_the_attributive_release(self):
        biopsy = 'Cold forceps biopsies were taken from the distal esophagus.'
        for dash in ('-',) + DASHES:
            with self.subTest(hex(ord(dash))):
                text = EGD + compound(dash) + '\n' + biopsy + '\n'
                self.assertEqual(outcome(run(text, [sel('43239', span(text, biopsy))]), '43239'), READY)
                # the declared form's own release: no denied snare on the attributive compound beside today's snare
                text = COLON + TODAY_SNARE + f'\nThe snare{dash}resected sigmoid polyp was not retrieved.\n'
                self.assertEqual(outcome(run(text, [sel('45385', span(text, TODAY_SNARE))]), '45385'), READY)

    def test_the_space_form_reads_as_installed(self):
        # new wording, a recorded residual: an act word, a space and a participle is also how a report states its act
        text = EGD + compound(' ') + '\n'
        self.assertIn(('gi.egd', 'biopsy', 'performed'), inventory_acts(text))


# --- V12: "not seen in person" hyphenated, contracted, or written with other white space ---------------------------

VARIANTS = ('Patient not seen in-person today.', "Patient wasn't seen in person today.",
            'Patient wasn\u2019t seen in person today.', "Patient isn't seen in person today.",
            "Patient wasn't seen in-person today.", 'Patient not seen in\u2011person today.',
            'Patient not seen in\u2013person today.', 'Patient not  seen in person today.',
            'Patient not seen\nin person today.', "The patient wasn't seen.", 'The patient wasn\u2019t seen.',
            "She isn't seen in clinic today.", 'Patient not seen in-office today.', 'No in\u2011person visit today.',
            "Ms. Lane wasn't seen in person today.")
# (plain, variant) pairs whose clause names another time or another service: the variant clears as the plain form does
PAIRS = (('The patient was not seen in the office for two years.', "The patient wasn't seen in the office for two years."),
         ('Patient not seen in office for two years.', 'Patient not seen in-office for two years.'),
         ('The patient was not seen for her CT results.', "The patient wasn't seen for her CT results."),
         ('The patient was not seen for her CT results.', 'The patient wasn\u2019t seen for her CT results.'),
         ('Patient not seen in person today.', "Patient wasn't seen in person today."),
         ('Patient not seen in person today.', 'Patient not  seen in person today.'),
         ('No in-person visit today.', 'No in\u2011person visit today.'),
         ('Ms. Lane was not seen in person today.', "Ms. Lane wasn't seen in person today."),
         ('No in-person visit was needed for the CT results.', 'No in\u2011person visit was needed for the CT results.'))


def exam(line):
    return em_chassis(('Vital Signs and Exam\n', 'Vital Signs and Exam\n' + line + '\n'))


def history(sentence):
    return em_chassis((CC, CC + ' ' + sentence))


def visit(text):
    item = proposal(run(text, [sel('99204', span(text, TWIN))], user_values=EMDAY), '99204')
    return f'{item.bucket}/{item.status}'


def em_routing(text):
    """routing's office E/M reading: (status, [(mention status, held as no in-person visit)])"""
    found = detect.route(text, EM_DAY).finding('gi.office_em')
    return (found.status, [(m.status, any(c.startswith(detect.EM_NOT_IN_PERSON) for c in m.cues))
                           for m in found.mentions])


class NotSeenInPersonVariantTests(SimpleTestCase):
    """V12 (refutation L1/R12): the declared phrase in its hyphenated and contracted forms, or with other white space
    inside it, holds the E/M reading as the plain form does; another verb ('not evaluated in person') is not read."""

    def test_the_cue_reads_the_phrase_in_each_form(self):
        for words in VARIANTS:
            with self.subTest(words):
                self.assertIsNotNone(cues.NOT_IN_PERSON.search(words))
        for words in ('Patient not evaluated in person today.', 'Patient seen in-person today.',
                      'She was seen in person today.', 'Patient seen in\u2011person today.', 'cannot be seen in person'):
            with self.subTest(words):
                self.assertIsNone(cues.NOT_IN_PERSON.search(words))
        for words in ("n't seen in person", 'n\u2019t seen', 'no in\u2013person', 'not seen'):
            with self.subTest(words):
                self.assertIsNotNone(detect._PV1_ATTENDANCE.search(words))

    def test_each_form_holds_the_visit(self):
        for words in VARIANTS:
            for place, chassis in (('exam', exam), ('history', history)):
                if place == 'history' and '\n' in words:
                    continue
                with self.subTest(words, where=place):
                    self.assertEqual(visit(chassis(words)), HELD)

    def test_each_form_reads_as_its_plain_form(self):
        for plain, variant in PAIRS:
            for chassis in (exam, history):
                with self.subTest(variant, where=chassis.__name__):
                    self.assertEqual(em_routing(chassis(variant)), em_routing(chassis(plain)))
                    self.assertEqual(visit(chassis(variant)), visit(chassis(plain)))

    def test_controls_an_in_person_visit_and_another_verb(self):
        self.assertEqual(visit(em_chassis()), READY)
        for words in ('Patient seen in-person today.', 'She was seen in person today.'):
            with self.subTest(words):
                self.assertEqual(visit(exam(words)), READY)
        # new wording, a recorded residual: another verb is not the declared phrase
        self.assertEqual(visit(exam('Patient not evaluated in person today.')), READY)
