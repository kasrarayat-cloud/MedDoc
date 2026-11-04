"""Reader repair, round 5 (2026-11-04): R1a-r5 in its hold-only form, the lead's rule landed verbatim (declared before
code in tests/fixtures/gi4/declarations/cux-r5-binding.json, amendment_20261104_hold_only; the unbinding form declared
above it was refuted by refutation round 5 and reverted).

Every act keeps main's binding and placement. Where more than one procedure family is read performed (the office visit
not counted), a performed act that a lesion label or specimen number binds, whose own clause names no site, whose part
names no service and whose kind is not catalogue.NOT_REPORTED (a clip, a cannulation) carries services.NAME_ONLY_CUE;
reconcile.match holds a code whose supporting performed acts all carry it (reason 'named_only', clarification
performed_status), after the conflict check, and no release or exclusion path reads that reason.

- every 'R8 R5 ' row reads as declared (cell, clarifications, reason) with no violation, every act stays where main
  puts it with its declared cue, the rows are their declared texts, and the residuals read as recorded;
- the four false READYs main reads are held, their acts still documented (R1, R1b and R3 dash 45380; R2 dash combined
  45382);
- the diagnostic base codes stay held [base_included] (the B probes, refutation round 5's X2 and X3);
- X1: 43251 held and its snare at the colon lesion; X4: the conflict kept;
- R1a-r3's path unchanged; the controls carry no cue;
- the hold class pinned: every declared cost is a done code held [performed_status] for reason named_only;
- Mara unchanged and carrying no cue.

Every document is synthetic. No database, nothing sent.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from django.test import SimpleTestCase

from ops.gi4 import battery
from studio.gi import catalogue, services
from studio.types import PageSpan
from tests.test_cux_bind import MARA, acts, bundled, conflicts, inventory, outcomes, run, service
from tests.test_cux_hold import state

DECLARATION = json.loads((Path(__file__).resolve().parent / 'fixtures' / 'gi4' / 'declarations'
                          / 'cux-r5-binding.json').read_text(encoding='utf-8'))
# the hold-only form's amendment, declared before its code: it governs wherever the refuted form's keys above disagree
HOLD_ONLY = DECLARATION['amendment_20261104_hold_only']
DECLARED = {(name, code): (before, after) for name, code, before, after in HOLD_ONLY['battery']}
READINGS = {tuple(key.split(' | ')): reading for key, reading in HOLD_ONLY['readings'].items()}
PREFIX = 'R8 R5 '
HELD = 'selected/needs_clarification'
READY = 'selected/ready'
CUE = services.NAME_ONLY_CUE
R1_SHAPES = ('R8 R5 R1 dash', 'R8 R5 R1b dash upper endoscopy named', 'R8 R5 R3 dash')
A3_CONTROL = 'R8 R3 A3 control, the colonoscope told again before the labelled act'
G1_GASTROSCOPE = 'R8 R5 residual G1 impression act by label, the gastroscope named (R1a-r3 path)'


def text_of(name):
    return battery.CASES[name][0]


def read(name, text=None, codes=None):
    """{code: (bucket/status, clarification facts, support reason, violations)} as the stages read the row (the battery's
    run_row view, with each proposal's support reason)."""
    text, codes = (text, codes) if text is not None else battery.CASES[name]
    truths = {code: truth for code, _, truth in codes}
    out = {}
    for p in run(text, [(code, quote) for code, quote, _ in codes]).proposals:
        if p.bucket == 'alternative' or p.code not in truths:
            continue
        view = {'bucket': p.bucket, 'status': p.status, 'modifiers': list(p.modifier_considerations),
                'checks': sorted(c.id for c in p.checks if c.status in ('warn', 'fail'))}
        out[p.code] = (f'{p.bucket}/{p.status}', sorted(c.fact for c in p.clarifications),
                       (p.support or {}).get('reason', ''), battery.violations(truths[p.code], view))
    return out


def act_rows(inv):
    """[family, kind, status, lesion, carries the cue] per act, as the declaration records them."""
    return [[s.family, a.kind, a.status, a.lesion, CUE in a.cues] for s in inv.services for a in s.acts]


def lesion_id(inv, family, size):
    return next(les.id for les in service(inv, family).lesions if les.size == size)


def mara():
    text = (MARA / 'rev1.txt').read_text(encoding='utf-8')
    starts = [i for i in range(len(text)) if text.startswith('SYNTHETIC TEST CASE - ALL PEOPLE', i)]
    pages = tuple(PageSpan(n + 1, s, (starts[n + 1] - 2) if n + 1 < len(starts) else len(text))
                  for n, s in enumerate(starts))
    return text, pages


class HoldOnlyRowsTests(SimpleTestCase):
    """Every 'R8 R5 ' row ends where the amendment says (bucket/status, clarifications and the support reason), with no
    violation; the rows are the declared texts and sources; the residuals read as recorded."""

    def test_the_rows(self):
        names = HOLD_ONLY['battery_rows']
        self.assertEqual(sorted(names), sorted(n for n in battery.CASES if n.startswith(PREFIX)))
        self.assertEqual(sorted({name for name, _ in READINGS}), sorted(names))
        for name in names:
            result = read(name)
            self.assertEqual(sorted(result), sorted(code for row, code in READINGS if row == name), name)
            for code, (cell, clarifications, reason, violations) in result.items():
                with self.subTest(name, code=code):
                    expected = READINGS[(name, code)]
                    self.assertEqual((cell, clarifications, reason),
                                     (expected['cell'], expected['clarifications'], expected['reason']))
                    self.assertEqual(violations, [])
                    if (name, code) in DECLARED:
                        self.assertEqual(DECLARED[(name, code)][1], cell)

    def test_every_row_is_its_declared_text(self):
        declared = {name: digest for name, digest in DECLARATION['texts_sha256'].items()
                    if name not in HOLD_ONLY['battery_rows_moved_to_residuals']}
        declared.update(HOLD_ONLY['texts_sha256'])
        texts = {name: text for name, (text, _) in battery.CASES.items() if name.startswith(PREFIX)}
        texts.update({name: text for name, (text, _) in battery.R5_RESIDUALS.items()})
        self.assertEqual({name: hashlib.sha256(text.encode('utf-8')).hexdigest() for name, text in texts.items()},
                         declared)
        self.assertEqual(battery.R5_XY_SOURCES, HOLD_ONLY['battery_rows_sources'])
        self.assertEqual(sorted(battery.R5_XY_SOURCES), sorted(HOLD_ONLY['battery_rows_added']))
        self.assertTrue(all(name.startswith(('R8 R5 X', 'R8 R5 Y')) for name in battery.R5_XY_SOURCES))
        self.assertEqual(sorted(battery.R5_SOURCES), sorted(n for n in DECLARATION['battery_rows_added']
                                                            if DECLARATION['battery_rows_sources'][n].startswith(
                                                                'verify-r4/refuter-cases.json')))

    def test_the_residuals_read_as_recorded(self):
        recorded = HOLD_ONLY['residuals_measured']['rows']
        self.assertEqual(sorted(recorded), sorted(battery.R5_RESIDUALS))
        for name, (text, codes) in battery.R5_RESIDUALS.items():
            result = read(name, text, codes)
            for code, cell in recorded[name].items():
                with self.subTest(name, code=code):
                    self.assertEqual(result[code][0], cell)
            # an honest truth that reads a violation on main, installed and here: recorded, never a register row
            self.assertTrue(any(violations for *_, violations in result.values()), name)
            self.assertNotIn(name, battery.CASES)


class PlacementTests(SimpleTestCase):
    """The form moves no act: every act of every round-5 row, of the A3 rows, of the residuals and of Mara is where main
    puts it (family, kind, status, lesion), and carries the cue exactly where the amendment says."""

    def test_every_act_is_where_main_puts_it_with_its_declared_cue(self):
        declared = HOLD_ONLY['inventory_acts']
        texts = {name: text for name, (text, _) in battery.CASES.items() if name in declared}
        texts.update({name: text for name, (text, _) in battery.R5_RESIDUALS.items()})
        self.assertEqual(sorted(texts) + ['mara rev1'], sorted(declared))
        for name, text in texts.items():
            with self.subTest(name):
                self.assertEqual(act_rows(inventory(text)), declared[name])
        self.assertEqual(act_rows(inventory(*mara())), declared['mara rev1'])

    def test_only_a_performed_reported_act_carries_the_cue(self):
        cued = [act for rows in HOLD_ONLY['inventory_acts'].values() for act in rows if act[4]]
        self.assertTrue(cued)
        for family, kind, status, lesion, _ in cued:
            self.assertEqual(status, 'performed')
            self.assertNotIn(kind, catalogue.NOT_REPORTED)
            self.assertTrue(lesion, 'a cued act is a bound act')


class FourShapesTests(SimpleTestCase):
    """The four shapes main 20a64b860 reads worse than installed: held, and their acts stay documented where main puts
    them, carrying the cue."""

    def test_the_biopsy_by_label_stays_the_colon_polyp_s_and_45380_is_held(self):
        for name in R1_SHAPES:
            with self.subTest(name):
                inv = inventory(text_of(name))
                (biopsy,) = acts(inv, 'gi.colonoscopy', 'biopsy')
                self.assertEqual((biopsy.lesion, CUE in biopsy.cues), (lesion_id(inv, 'gi.colonoscopy', '8 mm'), True))
                self.assertEqual(read(name)['45380'][:3], (HELD, ['performed_status'], 'named_only'))
                self.assertEqual(DECLARED[(name, '45380')], (READY, HELD))  # a fix: main READY, truth not done

    def test_the_prophylactic_clip_s_bleeding_control_is_held_and_the_clip_keeps_no_cue(self):
        name = 'R8 R5 R2 dash combined'
        inv = inventory(text_of(name))
        polyp_b = lesion_id(inv, 'gi.colonoscopy', '12 mm')
        self.assertEqual([(a.lesion, CUE in a.cues) for a in acts(inv, kind='bleeding_control')], [(polyp_b, True)])
        self.assertEqual([(a.lesion, CUE in a.cues) for a in acts(inv, 'gi.colonoscopy', 'clip')], [(polyp_b, False)])
        result = read(name)
        self.assertEqual({code: result[code][:3] for code in result},
                         {'43239': (READY, [], 'service'), '45385': (READY, [], 'service'),
                          '45382': (HELD, ['performed_status'], 'named_only')})


class BaseCodeTests(SimpleTestCase):
    """A label-only act stays documented, so a diagnostic base code beside it stays held [base_included]: the six base
    probes and round 5's X2 (the code beside a label-only snare) and X3 (the base code cited alone)."""

    def test_no_diagnostic_base_code_is_released(self):
        names = [n for n in battery.CASES if n.startswith((PREFIX + 'B', PREFIX + 'X2 ', PREFIX + 'X3 '))
                 and n != 'R8 R5 X3 an EGD by another provider, the snare code']
        self.assertEqual(len(names), 13)
        for name in names:
            result = read(name)
            base = '43235' if '43235' in result else '45378'
            with self.subTest(name):
                self.assertEqual(result[base][:2], (HELD, ['base_included']))

    def test_the_label_only_snare_stays_documented_beside_the_base_code(self):
        for name, family, size in (('R8 R5 X2 colon base code beside a label-only snare', 'gi.colonoscopy', '8 mm'),
                                   ('R8 R5 X2 upper base code beside a label-only snare', 'gi.egd', '6 mm'),
                                   ('R8 R5 X3 the 1146 row text, its base code beside 43239', 'gi.colonoscopy', '8 mm')):
            with self.subTest(name):
                inv = inventory(text_of(name))
                self.assertEqual([(a.status, a.lesion, CUE in a.cues) for a in acts(inv, family, 'snare')],
                                 [('performed', lesion_id(inv, family, size), True)])


class RefutedShapesTests(SimpleTestCase):
    """Refutation round 5's X1 and X4, as the hold-only form reads them: as main does."""

    def test_x1_43251_is_held_and_the_snare_stays_at_the_colon_lesion(self):
        name = 'R8 R5 X1 snare by label, the EGD titled first'
        inv = inventory(text_of(name))
        self.assertEqual(acts(inv, 'gi.egd'), [])
        (snare,) = acts(inv, 'gi.colonoscopy', 'snare')
        self.assertEqual((snare.lesion, CUE in snare.cues), (lesion_id(inv, 'gi.colonoscopy', '8 mm'), True))
        result = read(name)
        self.assertEqual(result['43251'][:3], (HELD, ['performed_status'], 'act_missing'))
        self.assertEqual(result['45385'][:3], (HELD, ['extent', 'performed_status'], 'named_only'))
        # FA2: the biopsy the same way
        biopsy = read('R8 R5 X1 biopsy by label, the EGD titled first')
        self.assertEqual(biopsy['43239'][:3], (HELD, ['performed_status'], 'act_missing'))
        self.assertEqual(biopsy['45380'][:2], (HELD, ['extent', 'performed_status']))

    def test_x4_the_genuine_conflict_is_kept(self):
        for name in ('R8 R5 X4 a performed snare and a sited denial at one polyp',
                     'R8 R5 X4 a performed snare and a labelled denial at one polyp'):
            with self.subTest(name):
                inv = inventory(text_of(name))
                polyp_a = lesion_id(inv, 'gi.colonoscopy', '8 mm')
                self.assertEqual([c.lesion for c in conflicts(inv, 'gi.colonoscopy', 'snare')], [polyp_a])
                self.assertIn(['gi.colonoscopy', 'snare', 'performed', polyp_a, True], act_rows(inv))
                result = read(name)
                self.assertEqual(result['45385'][:3], (HELD, ['conflict:snare'], 'conflict'))
                self.assertEqual(result['43239'][0], READY)


class ControlTests(SimpleTestCase):
    """What the form leaves as main reads it: R1a-r3's path, a single-service note's label-only act, a labelled clip, a
    labelled denial, one procedure performed beside one planned, and the round-5 controls - none carries the cue."""

    def test_r1a_r3_s_path_is_unchanged(self):
        name = 'R8 R5 control, the gastroscope named (R1a-r3 path)'
        inv = inventory(text_of(name))
        self.assertEqual(acts(inv, 'gi.colonoscopy', 'biopsy'), [])
        self.assertFalse(any(CUE in a.cues for a in acts(inv)))
        self.assertEqual({code: cell[:2] for code, cell in read(name).items()},
                         {'43239': (HELD, ['performed_status']), '45380': (HELD, ['performed_status'])})
        name = 'R8 R5 X2 colon base code, the R1a-r3 path'
        self.assertFalse(any(CUE in a.cues for a in acts(inventory(text_of(name)))))
        self.assertEqual(read(name)['45378'][:2], (HELD, ['base_included']))
        # the G1 shape told by the gastroscope reads as main reads it: recorded as a residual (43239 READY, not done)
        text, codes = battery.R5_RESIDUALS[G1_GASTROSCOPE]
        self.assertEqual(read(G1_GASTROSCOPE, text, codes)['43239'][:2], (READY, []))
        self.assertNotIn(G1_GASTROSCOPE.replace('residual ', ''), battery.CASES)

    def test_the_controls_carry_no_cue_and_read_ready(self):
        for name in ('R8 R5 control, a colonoscopy-only note with a label-only act',
                     'R8 R5 control, a labelled clip after the upper endoscopy',
                     'R8 R5 control, a labelled denial after the upper endoscopy',
                     'R8 R5 Y1 control, no sub-heading', 'R8 R5 Y2 control, EGD alone',
                     'R8 R5 Y4 control, no second family'):
            with self.subTest(name):
                self.assertFalse(any(CUE in a.cues for a in acts(inventory(text_of(name)))))
                self.assertEqual({cell[0] for cell in read(name).values()}, {READY})

    def test_a_labelled_clip_and_a_labelled_denial_keep_their_lesions(self):
        inv = inventory(text_of('R8 R5 control, a labelled clip after the upper endoscopy'))
        self.assertIn('clip', catalogue.NOT_REPORTED)
        self.assertEqual([(a.lesion, CUE in a.cues) for a in acts(inv, 'gi.colonoscopy', 'clip')],
                         [(lesion_id(inv, 'gi.colonoscopy', '8 mm'), False)])
        inv = inventory(text_of('R8 R5 control, a labelled denial after the upper endoscopy'))
        self.assertEqual([(a.lesion, CUE in a.cues) for a in acts(inv, kind='biopsy', status='negated')],
                         [(lesion_id(inv, 'gi.colonoscopy', '8 mm'), False)])
        self.assertEqual(conflicts(inv), [])

    def test_one_procedure_performed_beside_one_planned_carries_no_cue(self):
        # one procedure is read performed, so no act is name_only although the part names no service (the planned EGD is
        # a second documented service): both codes READY with the distinct-lesion consideration
        name = 'R8 R5 control, one procedure performed and one planned, acts by label'
        text, codes = battery.CASES[name]
        inv = inventory(text)
        self.assertEqual({(a.kind, a.lesion, CUE in a.cues) for a in acts(inv, 'gi.colonoscopy', status='performed')},
                         {('biopsy', lesion_id(inv, 'gi.colonoscopy', '4 mm'), False),
                          ('snare', lesion_id(inv, 'gi.colonoscopy', '8 mm'), False)})
        result = run(text, [(code, quote) for code, quote, _ in codes])
        for code in ('45380', '45385'):
            with self.subTest(code):
                p = next(p for p in result.proposals if p.code == code and p.bucket == 'selected')
                self.assertEqual(p.status, 'ready')
                self.assertTrue(any('59 or XS' in m for m in p.modifier_considerations), p.modifier_considerations)


class DeclaredCostTests(SimpleTestCase):
    """The hold class, pinned as a cost: each declared cost is a code whose truth is done, READY on main, held
    [performed_status] for reason named_only - a held done code is no battery violation, so these pins keep the cost
    visible. The fixes are the false READYs held. Together they are every declared movement."""

    def test_the_costs_and_fixes_are_exactly_the_declared_movements(self):
        costs = [tuple(cell) for cell in HOLD_ONLY['declared_costs']['hold_class']['cost_cells']]
        fixes = [tuple(cell) for cell in HOLD_ONLY['fixes_against_base']]
        self.assertEqual(sorted(costs + fixes), sorted(tuple(m) for m in HOLD_ONLY['battery']))
        self.assertEqual((len(costs), len(fixes)), (21, 4))
        self.assertIn(A3_CONTROL, [name for name, _, _, _ in costs])
        # the realistic shapes the class names each have a row among its costs
        for shape in HOLD_ONLY['declared_costs']['hold_class']['realistic_shapes']:
            self.assertTrue(any(name.startswith(f'{PREFIX}{shape} ') for name, _, _, _ in costs), shape)
        for name, code, before, after in costs:
            with self.subTest(name, code=code):
                self.assertEqual({c: t for c, _, t in battery.CASES[name][1]}[code], 'done')
                self.assertEqual((before, after), (READY, HELD))
                self.assertEqual(read(name)[code], (HELD, ['performed_status'], 'named_only', []))
        for name, code, before, after in fixes:
            with self.subTest(name, code=code):
                self.assertEqual({c: t for c, _, t in battery.CASES[name][1]}[code], 'not_done')
        # a named_only hold is exactly a declared movement, or X1's two cells main already holds [extent]
        moved = {(name, code) for name, code, _, _ in HOLD_ONLY['battery'] if name.startswith(PREFIX)}
        self.assertEqual({tuple(key.split(' | ')) for key in HOLD_ONLY['named_only_cells']} - moved,
                         {('R8 R5 X1 snare by label, the EGD titled first', '45385'),
                          ('R8 R5 X1 biopsy by label, the EGD titled first', '45380')})

    def test_the_a3_control_s_snare_stays_bound_and_carries_the_cue(self):
        inv = inventory(text_of(A3_CONTROL))
        (snare,) = acts(inv, 'gi.colonoscopy', 'snare')
        self.assertEqual((snare.lesion, CUE in snare.cues), (lesion_id(inv, 'gi.colonoscopy', '8 mm'), True))
        self.assertEqual(read(A3_CONTROL)['45385'][:3], (HELD, ['performed_status'], 'named_only'))

    def test_a_combined_title_counts_a_service_the_note_denies(self):
        # pass 1 reads the title's EGD performed although the note denies it, so the act carries the cue: recorded, not
        # changed (the class includes such a note)
        name = 'R8 R5 hold, a combined title whose second service the note denies'
        inv = inventory(text_of(name))
        self.assertEqual(service(inv, 'gi.colonoscopy').status, 'performed')
        self.assertNotEqual(service(inv, 'gi.egd').status, 'performed')
        self.assertEqual([CUE in a.cues for a in acts(inv, 'gi.colonoscopy', 'snare')], [True])
        self.assertEqual(read(name)['45385'][:3], (HELD, ['performed_status'], 'named_only'))


class MaraUnchangedTests(SimpleTestCase):
    """Mara's retained revision (tests/fixtures/cux/mara, tests/test_cux_bind.MaraEndToEndTests): no act carries the
    cue - its labelled clip, 'One prophylactic clip was placed at the COL-2 resection site.', is catalogue.NOT_REPORTED -
    and the acceptance stands."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.text, cls.pages = mara()  # MaraEndToEndTests.response reads text and readme
        cls.readme = json.loads((MARA / 'README.json').read_text(encoding='utf-8'))

    def test_no_act_carries_the_cue_and_the_clip_keeps_its_lesion(self):
        inv = inventory(self.text, self.pages)
        self.assertEqual([a for a in acts(inv) if CUE in a.cues], [])
        colon = service(inv, 'gi.colonoscopy')
        self.assertEqual([a.lesion for a in colon.acts if a.kind == 'clip'], [lesion_id(inv, 'gi.colonoscopy', '8 mm')])
        self.assertEqual(conflicts(inv), [])

    def test_the_acceptance_stands(self):
        from tests.test_cux_bind import MaraEndToEndTests  # its retained response, checked against the README's sha256
        result = run(self.text, normalized=MaraEndToEndTests.response(self), pages=self.pages)
        self.assertEqual({code: o[:2] for code, o in outcomes(result).items()},
                         {'43239': ('selected', 'ready'), '45380': ('selected', 'ready'), '45385': ('selected', 'ready')})
        self.assertEqual(bundled(result), [('gi.colonoscopy', 'clip')])
