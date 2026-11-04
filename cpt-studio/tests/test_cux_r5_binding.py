"""Reader repair, round 5 (2026-11-04): R1a-r5, the lead's structural binding rule, landed verbatim (declared before
code in tests/fixtures/gi4/declarations/cux-r5-binding.json).

Where more than one procedure family is read performed (the office visit not counted), a non-denied act whose own
clause names no site, whose part names no service and whose kind is not catalogue.NOT_REPORTED (clip, cannulation) is
never given its service by a lesion's name: it is unbound as R1a-r3 unbinds, and takes no site from another clause of
its sentence. No telling is detected and no word is listed.

- the four shapes main 20a64b860 reads worse than installed are held (R1, R1b and R3 dash: 45380; R2 dash combined:
  45382);
- the base probes: no diagnostic base code (45378, 43235) is released;
- the controls: R1a-r3's gastroscope path, a single-service note's label-only act, a labelled clip, a labelled denial,
  one procedure performed beside one planned, and the G1 shape (the unbound act takes no other clause's site);
- the declared costs, pinned as costs: the R8 R3 A3 control and the hold class;
- Mara unchanged; the residuals read as recorded.

Every document is synthetic. No database, nothing sent.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from django.test import SimpleTestCase

from ops.gi4 import battery
from studio.gi import catalogue
from studio.types import PageSpan
from tests.test_cux_bind import MARA, acts, bundled, conflicts, inventory, outcomes, run, service
from tests.test_cux_hold import row, state

DECLARATION = json.loads((Path(__file__).resolve().parent / 'fixtures' / 'gi4' / 'declarations'
                          / 'cux-r5-binding.json').read_text(encoding='utf-8'))
# the after-code amendment (dated, measured after code; it changes no key above it)
AFTER_CODE = DECLARATION.get('after_code_20261104', {})
DECLARED = {(name, code): (before, after)
            for name, code, before, after in DECLARATION['battery'] + AFTER_CODE.get('battery', [])}
UNMOVED = {tuple(key.split(' | ')): cell
           for key, cell in list(DECLARATION['unmoved'].items()) + list(AFTER_CODE.get('unmoved', {}).items())}
PREFIX = 'R8 R5 '
HELD = 'selected/needs_clarification'
READY = 'selected/ready'
R1_SHAPES = ('R8 R5 R1 dash', 'R8 R5 R1b dash upper endoscopy named', 'R8 R5 R3 dash')
G1_ROWS = ('R8 R5 G1 impression act by label, a bare endoscope',
           'R8 R5 G1 impression act by label, the upper endoscopy named',
           'R8 R5 G1 impression act by label, the gastroscope named (R1a-r3 path)')
A3_CONTROL = 'R8 R3 A3 control, the colonoscope told again before the labelled act'


def text_of(name):
    return battery.CASES[name][0]


def lesion_id(inv, family, size):
    return next(les.id for les in service(inv, family).lesions if les.size == size)


def proposal(result, code):
    return next(p for p in result.proposals if p.code == code and p.bucket == 'selected')


class R5RowsTests(SimpleTestCase):
    """Every round-5 battery row ends where the declaration says, with no violation; the rows are the declared texts
    (the lead's cases, base probes and refuter cases verbatim); the residuals read as recorded."""

    def test_the_rows(self):
        names = DECLARATION['battery_rows_added']
        self.assertEqual(sorted(names), sorted(n for n in battery.CASES if n.startswith(PREFIX)))
        for name in names:
            result = row(name)
            for code in result['proposals']:
                with self.subTest(name, code=code):
                    expected = DECLARED[(name, code)][1] if (name, code) in DECLARED else UNMOVED[(name, code)]
                    self.assertEqual(state(result, code), expected)
                    self.assertEqual(result['proposals'][code]['violations'], [])

    def test_every_row_is_its_declared_text(self):
        texts = {name: text for name, (text, _) in battery.CASES.items() if name.startswith(PREFIX)}
        texts.update({name: text for name, (text, _) in battery.R5_RESIDUALS.items()})
        self.assertEqual({name: hashlib.sha256(text.encode('utf-8')).hexdigest() for name, text in texts.items()},
                         DECLARATION['texts_sha256'])
        self.assertEqual(sorted(battery.R5_SOURCES), sorted(n for n in DECLARATION['battery_rows_added']
                                                            if DECLARATION['battery_rows_sources'][n].startswith(
                                                                'verify-r4/refuter-cases.json')))

    def test_the_residuals_read_as_recorded(self):
        recorded = DECLARATION['residuals_measured']['rows']
        self.assertEqual(sorted(recorded), sorted(battery.R5_RESIDUALS))
        m = battery.modules()
        for name, (text, codes) in battery.R5_RESIDUALS.items():
            result = battery.run_row(m, name, text, codes)
            for code, cell in recorded[name].items():
                with self.subTest(name, code=code):
                    self.assertEqual(state(result, code), cell)
            # an honest truth that reads a violation on main, installed and here: recorded, never a register row
            self.assertTrue(any(p['violations'] for p in result['proposals'].values()), name)
            self.assertNotIn(name, battery.CASES)


class FourShapesTests(SimpleTestCase):
    """The four shapes main reads worse than installed: a lesion's label no longer gives the upper endoscopy's biopsy
    to the colon polyp, nor the prophylactic clip's hemostatic act to Polyp B."""

    def test_the_upper_endoscopy_s_biopsy_is_never_the_colon_polyp_s(self):
        for name in R1_SHAPES:
            with self.subTest(name):
                self.assertEqual(acts(inventory(text_of(name)), 'gi.colonoscopy', 'biopsy'), [])
                result = row(name)
                self.assertEqual(state(result, '45380'), HELD)
                self.assertEqual(result['proposals']['45380']['clarifications'], ['performed_status'])

    def test_the_prophylactic_clip_is_no_bleeding_control_at_the_polyp(self):
        name = 'R8 R5 R2 dash combined'
        inv = inventory(text_of(name))
        self.assertEqual(acts(inv, kind='bleeding_control'), [])
        # the clip itself keeps its label (catalogue.NOT_REPORTED): bundled at Polyp B, as before
        self.assertEqual([a.lesion for a in acts(inv, 'gi.colonoscopy', 'clip')],
                         [lesion_id(inv, 'gi.colonoscopy', '12 mm')])
        result = row(name)
        self.assertEqual({code: state(result, code) for code in result['proposals']},
                         {'43239': READY, '45385': READY, '45382': HELD})

    def test_the_paren_and_unlabelled_forms_read_as_on_main(self):
        # no label is read in them (the first fresh walk document's gap b): the rule never engages
        for name in ('R8 R5 R1 paren', 'R8 R5 R1b paren upper endoscopy named', 'R8 R5 R3 paren',
                     'R8 R5 R1 control unlabelled', 'R8 R5 R2 paren combined'):
            result = row(name)
            for code in result['proposals']:
                with self.subTest(name, code=code):
                    self.assertNotIn((name, code), DECLARED)
                    self.assertEqual(state(result, code), UNMOVED[(name, code)])


class BaseProbeTests(SimpleTestCase):
    """The lead's base-code probes: an act unbound by the rule never releases the diagnostic base code."""

    def test_no_diagnostic_base_code_is_released(self):
        names = [n for n in battery.CASES if n.startswith(PREFIX + 'B')]
        self.assertEqual(len(names), 6)
        for name in names:
            result = row(name)
            base = '43235' if '43235' in result['proposals'] else '45378'
            with self.subTest(name):
                self.assertEqual(state(result, base), HELD)
                self.assertEqual(result['proposals'][base]['clarifications'], ['base_included'])


class ControlTests(SimpleTestCase):
    """What the rule keeps: R1a-r3's own reading where the gastroscope is named, a single-service note's label-only
    act, a labelled clip and a labelled denial after the upper endoscopy, and each label's lesion where one procedure
    is performed beside one planned."""

    def test_the_gastroscope_named_reads_as_on_main(self):
        name = 'R8 R5 control, the gastroscope named (R1a-r3 path)'
        self.assertEqual(acts(inventory(text_of(name)), 'gi.colonoscopy', 'biopsy'), [])
        result = row(name)
        for code in result['proposals']:
            with self.subTest(code):
                self.assertNotIn((name, code), DECLARED)
                self.assertEqual(state(result, code), UNMOVED[(name, code)])

    def test_a_single_service_note_s_label_only_act_stays_bound(self):
        name = 'R8 R5 control, a colonoscopy-only note with a label-only act'
        inv = inventory(text_of(name))
        self.assertEqual([a.lesion for a in acts(inv, 'gi.colonoscopy', 'snare')],
                         [lesion_id(inv, 'gi.colonoscopy', '8 mm')])
        self.assertEqual(state(row(name), '45385'), READY)

    def test_a_labelled_clip_keeps_its_label(self):
        name = 'R8 R5 control, a labelled clip after the upper endoscopy'
        inv = inventory(text_of(name))
        self.assertIn('clip', catalogue.NOT_REPORTED)
        self.assertEqual([a.lesion for a in acts(inv, 'gi.colonoscopy', 'clip')],
                         [lesion_id(inv, 'gi.colonoscopy', '8 mm')])
        self.assertEqual(acts(inv, 'gi.egd', 'clip'), [])
        result = row(name)
        self.assertEqual({code: state(result, code) for code in result['proposals']}, {'45385': READY, '43239': READY})

    def test_a_labelled_denial_keeps_its_label(self):
        name = 'R8 R5 control, a labelled denial after the upper endoscopy'
        inv = inventory(text_of(name))
        self.assertEqual([a.lesion for a in acts(inv, kind='biopsy', status='negated')],
                         [lesion_id(inv, 'gi.colonoscopy', '8 mm')])
        self.assertEqual(conflicts(inv), [])
        result = row(name)
        self.assertEqual({code: state(result, code) for code in result['proposals']}, {'45385': READY, '43239': READY})

    def test_one_procedure_performed_beside_one_planned_keeps_each_label(self):
        # one procedure is read performed, so the rule does not engage although the part names no service (the
        # planned EGD is a second documented service): each act stays its own lesion's, and the distinct-lesion
        # consideration stands
        name = 'R8 R5 control, one procedure performed and one planned, acts by label'
        text, codes = battery.CASES[name]
        inv = inventory(text)
        self.assertEqual({(a.kind, a.lesion) for a in acts(inv, 'gi.colonoscopy', status='performed')},
                         {('biopsy', lesion_id(inv, 'gi.colonoscopy', '4 mm')),
                          ('snare', lesion_id(inv, 'gi.colonoscopy', '8 mm'))})
        result = run(text, [(code, quote) for code, quote, _ in codes])
        for code in ('45380', '45385'):
            with self.subTest(code):
                p = proposal(result, code)
                self.assertEqual(p.status, 'ready')
                self.assertTrue(any('59 or XS' in m for m in p.modifier_considerations), p.modifier_considerations)


class UnboundActTakesNoOtherSiteTests(SimpleTestCase):
    """Refutation 4b's G1 shape: 'Impression: Polyp A was biopsied with cold forceps; the antrum was normal.' after
    the upper examination is told. The act the rule unbinds takes no site from the antrum's clause, so the impression's
    restatement of the colon biopsy is never an upper endoscopy's biopsy - told by a bare endoscope, by the upper
    endoscopy's name, or by the gastroscope (R1a-r3's path, where main took the other clause's site: READY)."""

    def test_the_impression_s_restatement_is_never_an_upper_biopsy(self):
        for name in G1_ROWS:
            with self.subTest(name):
                self.assertEqual(acts(inventory(text_of(name)), 'gi.egd'), [])
                result = row(name)
                self.assertEqual(state(result, '43239'), HELD)
                self.assertEqual(result['proposals']['43239']['clarifications'], ['performed_status'])
                self.assertEqual(state(result, '45380'), READY)
        self.assertEqual(DECLARED[(G1_ROWS[2], '43239')], (READY, HELD))  # a fix: main READY, truth not done


class DeclaredCostTests(SimpleTestCase):
    """The declared costs, pinned as costs: each is a code whose truth is done, READY on main, that the rule holds
    because only a lesion's name would place its act - the R8 R3 A3 control and the hold class (a combined note with
    no section heading naming a service, a lesion defined in one sentence and acted on by its name alone in another).
    A held done code is no battery violation, so these pins are what keeps the cost visible."""

    def test_the_costs_are_exactly_the_declared_holds(self):
        costs = [tuple(cell) for cell in DECLARATION['declared_costs']['hold_class']['cost_cells']]
        fixes = [tuple(cell) for cell in DECLARATION['fixes_against_base']]
        self.assertEqual(sorted(costs + fixes), sorted(tuple(m) for m in DECLARATION['battery']))
        self.assertIn(A3_CONTROL, [name for name, _, _, _ in costs])
        for name, code, before, after in costs:
            with self.subTest(name, code=code):
                self.assertEqual({c: t for c, _, t in battery.CASES[name][1]}[code], 'done')
                self.assertEqual((before, after), (READY, HELD))
                result = row(name)
                self.assertEqual(state(result, code), HELD)
                self.assertEqual(result['proposals'][code]['clarifications'], ['performed_status'])
                self.assertEqual(result['proposals'][code]['violations'], [])
        for name, code, before, after in fixes:
            with self.subTest(name, code=code):
                self.assertEqual({c: t for c, _, t in battery.CASES[name][1]}[code], 'not_done')

    def test_the_a3_control_s_snare_is_no_longer_bound(self):
        # the colonoscope told again restores nothing: the rule detects no telling
        inv = inventory(text_of(A3_CONTROL))
        self.assertEqual(acts(inv, 'gi.colonoscopy', 'snare'), [])
        self.assertEqual(state(row(A3_CONTROL), '45385'), HELD)

    def test_a_label_only_act_in_the_class_is_no_service_s_act(self):
        for name in ('R8 R5 hold 1146 a procedures-performed line, the label acted on by name',
                     'R8 R5 hold 1277 findings first, the label acted on after the colonoscope',
                     'R8 R5 hold 1406 the colonoscope reinserted to the identified polyp',
                     'R8 R5 hold, a combined title whose second service the note denies'):
            with self.subTest(name):
                self.assertEqual(acts(inventory(text_of(name)), kind='snare'), [])
        self.assertEqual(acts(inventory(text_of('R8 R5 hold 1383 an upper lesion acted on by its label')), kind='snare'),
                         [])

    def test_a_combined_title_counts_a_service_the_note_denies(self):
        # pass 1 reads the title's EGD performed although the note denies it, so the rule engages: recorded, not changed
        name = 'R8 R5 hold, a combined title whose second service the note denies'
        inv = inventory(text_of(name))
        self.assertEqual(service(inv, 'gi.colonoscopy').status, 'performed')
        self.assertNotEqual(service(inv, 'gi.egd').status, 'performed')
        self.assertEqual(state(row(name), '45385'), HELD)


class MaraUnchangedTests(SimpleTestCase):
    """Mara's retained revision (tests/fixtures/cux/mara, tests/test_cux_bind.MaraEndToEndTests): its labelled clip,
    'One prophylactic clip was placed at the COL-2 resection site.', keeps its label because a clip is
    catalogue.NOT_REPORTED, and the acceptance stands."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.text = (MARA / 'rev1.txt').read_text(encoding='utf-8')
        cls.readme = json.loads((MARA / 'README.json').read_text(encoding='utf-8'))
        starts = [i for i in range(len(cls.text)) if cls.text.startswith('SYNTHETIC TEST CASE - ALL PEOPLE', i)]
        cls.pages = tuple(PageSpan(n + 1, s, (starts[n + 1] - 2) if n + 1 < len(starts) else len(cls.text))
                          for n, s in enumerate(starts))

    def test_the_labelled_clip_keeps_its_lesion(self):
        inv = inventory(self.text, self.pages)
        colon = service(inv, 'gi.colonoscopy')
        self.assertEqual([a.lesion for a in colon.acts if a.kind == 'clip'], [lesion_id(inv, 'gi.colonoscopy', '8 mm')])
        self.assertEqual(conflicts(inv), [])

    def test_the_acceptance_stands(self):
        from tests.test_cux_bind import MaraEndToEndTests  # its retained response, checked against the README's sha256
        result = run(self.text, normalized=MaraEndToEndTests.response(self), pages=self.pages)
        self.assertEqual({code: o[:2] for code, o in outcomes(result).items()},
                         {'43239': ('selected', 'ready'), '45380': ('selected', 'ready'), '45385': ('selected', 'ready')})
        self.assertEqual(bundled(result), [('gi.colonoscopy', 'clip')])
