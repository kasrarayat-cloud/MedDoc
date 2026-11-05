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

Refutation round 5b's three fixes (the lead's verify-r4/apply_z21.py, declared before code in amendment_20261104_hold_only_r5b,
which governs wherever the hold-only amendment disagrees), each through the path its finding used:
- (a) X-R5B-1: a code the bounded second review selects for a service left without a proposal, whose match is
  named_only, is added as a second-review proposal and held - never an informational alternative - and the approved
  export waits for its decision (engine.assess with a second-review response; the customer API to the approved export);
- (b) Y-F1, Y-F2: a merged act keeps the cue only when every statement of it carries it, so an impression restating the
  act with its site, or an addendum posted from the detail row naming its site and service, lifts the hold;
- (c) X-R5B-2: the named_only hold carries its acts, so the partner code offers its separate-lesion modifier review and
  an approval with XS succeeds.

Every document is synthetic and nothing is sent. The second review, addendum and modifier-review classes run through the
real endpoints and pipeline on the test database, with in-process fakes for every provider and participant.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path
from unittest import mock

from django.test import SimpleTestCase, override_settings

from ops.gi4 import battery
from studio import review
from studio.gi import catalogue, services
from studio.types import NormalizedResponse, PageSpan
from tests import test_customer_surface as tcs
from tests import test_repairs_gi2_present as gi2
from tests import test_services_reconcile as rec
from tests.test_customer_fixtures import CitingCorti
from tests.test_cux_bind import MARA, acts, bundled, conflicts, inventory, outcomes, run, service
from tests.test_cux_hold import state
from tests.test_harness2_pipeline import install_reference_store
from tests.test_harness_pipeline import FakeParticipant
from tests.test_pipeline_api import drain
from tests.test_services_second_review import TwoPassProvider

DECLARATION = json.loads((Path(__file__).resolve().parent / 'fixtures' / 'gi4' / 'declarations'
                          / 'cux-r5-binding.json').read_text(encoding='utf-8'))
# the hold-only form's amendment, declared before its code: it governs wherever the refuted form's keys above disagree
HOLD_ONLY = DECLARATION['amendment_20261104_hold_only']
# round 5b's three fixes, declared before their code: the hold-only rule's latest record, which governs wherever the
# hold-only amendment disagrees (its rows, readings, movements, inventory acts, cost cells and offers)
R5B = DECLARATION['amendment_20261104_hold_only_r5b']
DECLARED = {(name, code): (before, after) for name, code, before, after in R5B['battery']}
READINGS = {tuple(key.split(' | ')): reading for key, reading in R5B['readings'].items()}
# The harness repair's amendment (2026-11-05), measured after its code (refutation multi-3: a prophylactic hemostatic
# clip is never control of bleeding done): it governs wherever round 5b disagrees, on the R2 rows alone.
H2R = DECLARATION['amendment_20261105_harness_repair']
READINGS.update({tuple(key.split(' | ')): reading for key, reading in H2R['readings'].items()})
PREFIX = 'R8 R5 '
HELD = 'selected/needs_clarification'
READY = 'selected/ready'
CUE = services.NAME_ONLY_CUE
R1_SHAPES = ('R8 R5 R1 dash', 'R8 R5 R1b dash upper endoscopy named', 'R8 R5 R3 dash')
A3_CONTROL = 'R8 R3 A3 control, the colonoscope told again before the labelled act'
G1_GASTROSCOPE = 'R8 R5 residual G1 impression act by label, the gastroscope named (R1a-r3 path)'
# round 5b's rows (R5_Z_SOURCES) and the round-5b findings' own inputs
Z1 = 'R8 R5 Z1 an impression restating the label-only snare with its size and site'
Z2 = 'R8 R5 Z2 an addendum restating the label-only snare with its site and service'
Z3 = 'R8 R5 Z3 a label-only snare beside a forceps removal on its own line'
Y1 = 'R8 R5 Y1 COLONOSCOPY heading, Findings: sub-heading'
Y3 = 'R8 R5 Y3 PROCEDURE 2: COLONOSCOPY heading'
H1146 = 'R8 R5 hold 1146 a procedures-performed line, the label acted on by name'
BY_NAME = 'Polyp A was removed with a cold snare.'
# Y-F2's addendum, as the physician posts it from the detail row (refute-r5b-results.json r5brefute:Y)
ADDENDUM = 'Polyp A was removed with a cold snare during the colonoscopy, in the sigmoid colon, on the date of service.'
# the X-R5B-1 verifier's second-review shapes (refute-r5b/verify-X/X-R5B-1): the extra passages its codes cite
CECUM_Q = 'The colonoscope was advanced to the cecum.'
GASTRO_Q = 'The gastroscope was then passed to the second part of the duodenum.'


def text_of(name):
    return battery.CASES[name][0]


def quotes(name):
    return {code: quote for code, quote, _ in battery.CASES[name][1]}


def second_reviewed(name, primary, second):
    """(the primary-only result, the result with the bounded second review) of row ``name`` as engine.assess reads it
    (tests.test_services_reconcile.run): the primary's codes ``primary`` [(code, quote)], then the second review's
    ``second`` over the scope items the primary-only assessment flags for it, as jobs.stage_review2 builds them."""
    text = text_of(name)
    first = [rec.sel(code, rec.span(text, quote)) for code, quote in primary]
    alone = rec.run(text, first)
    items = [u['label'] for u in alone.completeness['unresolved_items'] if u['second_review']][:8]
    response = NormalizedResponse('replay', 'test@1', tuple(rec.sel(code, rec.span(text, quote))
                                                            for code, quote in second))
    return alone, rec.run(text, first, second=response, second_scope={'items': items})


def second_review_case(name):
    """The primary's and the second review's codes of a declared second-review case (R5B['second_review']), as the
    X-R5B-1 verifier's cases cite them: 'SR' the primary's biopsy (an EGD base for the 1406 row) then 45385; 'SR3' the
    biopsy, then 45378 and 45385; 'SR4' the biopsy and 45378, then 45385; 'SR0' nothing, then 45385."""
    kind, row = name.split(' | ', 1)
    q = quotes(row)
    biopsy = [('43239', q['43239'])] if '43239' in q else [('43235', GASTRO_Q)]
    return row, {'SR': (biopsy, [('45385', q['45385'])]),
                 'SR3 base+snare': (biopsy, [('45378', CECUM_Q), ('45385', q['45385'])]),
                 'SR4 act item': (biopsy + [('45378', CECUM_Q)], [('45385', q['45385'])]),
                 'SR0 nothing primary': ([], [('45385', q['45385'])])}[kind]


def merged_cells(result):
    """The second review's merge as the declaration records it: each proposal's cell (an alternative by its key), each
    unresolved item, the provider.second_review check's status."""
    cells = []
    for p in result.proposals:
        if p.bucket == 'alternative':
            cells.append(f'{p.code} alternative ({p.key})')
        else:
            support = p.support or {}
            cells.append(f"{p.code} {p.bucket}/{p.status} [{', '.join(c.fact for c in p.clarifications)}] "
                         f"{support.get('reason')}" + (' (second review)' if support.get('origin') == 'second_review'
                                                       else ''))
    check = next((c for c in result.encounter_checks if c.id == 'provider.second_review'), None)
    return {'cells': cells, 'unresolved': [f"{u['family']} {u['act'] or '(service)'} {u['reason']}"
                                           for u in result.completeness['unresolved_items']],
            'check': check.status if check is not None else None}


def support_acts(name):
    """{code: the act ids its support record names} of row ``name``, read as the stages read it."""
    text, codes = battery.CASES[name]
    return {p.code: [a['id'] for a in (p.support or {}).get('acts', [])]
            for p in run(text, [(code, quote) for code, quote, _ in codes]).proposals if p.bucket != 'alternative'}


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
        names = R5B['battery_rows']
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
        declared.update(R5B['texts_sha256'])
        texts = {name: text for name, (text, _) in battery.CASES.items() if name.startswith(PREFIX)}
        texts.update({name: text for name, (text, _) in battery.R5_RESIDUALS.items()})
        self.assertEqual({name: hashlib.sha256(text.encode('utf-8')).hexdigest() for name, text in texts.items()},
                         declared)
        self.assertEqual(battery.R5_XY_SOURCES, HOLD_ONLY['battery_rows_sources'])
        self.assertEqual(sorted(battery.R5_XY_SOURCES), sorted(HOLD_ONLY['battery_rows_added']))
        self.assertTrue(all(name.startswith(('R8 R5 X', 'R8 R5 Y')) for name in battery.R5_XY_SOURCES))
        # round 5b's rows, verbatim from refute-r5b (each source named; each text's sha256 declared above)
        self.assertEqual(battery.R5_Z_SOURCES, R5B['battery_rows_sources'])
        self.assertEqual(sorted(battery.R5_Z_SOURCES), sorted(R5B['battery_rows_added']))
        self.assertTrue(all(name.startswith('R8 R5 Z') and source.startswith('refute-r5b/')
                            for name, source in battery.R5_Z_SOURCES.items()))
        self.assertEqual(sorted(battery.R5_SOURCES), sorted(n for n in DECLARATION['battery_rows_added']
                                                            if DECLARATION['battery_rows_sources'][n].startswith(
                                                                'verify-r4/refuter-cases.json')))

    def test_the_residuals_read_as_recorded(self):
        recorded = R5B['residuals_measured']['rows']
        self.assertEqual(recorded, HOLD_ONLY['residuals_measured']['rows'])
        self.assertEqual(sorted(recorded), sorted(battery.R5_RESIDUALS))
        for name, (text, codes) in battery.R5_RESIDUALS.items():
            result = read(name, text, codes)
            closed = H2R['residuals_closed'].get(name, {})
            for code, cell in recorded[name].items():
                with self.subTest(name, code=code):
                    self.assertEqual(result[code][0], closed.get(code, cell))
            # an honest truth that reads a violation on main, installed and here: recorded, never a register row - but
            # the harness repair closed the prophylactic hemostatic clip's (H2R): those read no violation now
            self.assertEqual(any(violations for *_, violations in result.values()), not closed, name)
            self.assertNotIn(name, battery.CASES)


class PlacementTests(SimpleTestCase):
    """The form moves no act: every act of every round-5 row, of the A3 rows, of the residuals and of Mara is where main
    puts it (family, kind, status, lesion), and carries the cue exactly where the amendment says."""

    def test_every_act_is_where_main_puts_it_with_its_declared_cue(self):
        declared = {**R5B['inventory_acts'], **H2R['inventory_acts']}  # H2R: the R2 rows' bleeding control in doubt
        texts = {name: text for name, (text, _) in battery.CASES.items() if name in declared}
        texts.update({name: text for name, (text, _) in battery.R5_RESIDUALS.items()})
        self.assertEqual(sorted(texts) + ['mara rev1'], sorted(declared))
        for name, text in texts.items():
            with self.subTest(name):
                self.assertEqual(act_rows(inventory(text)), declared[name])
        self.assertEqual(act_rows(inventory(*mara())), declared['mara rev1'])

    def test_only_a_performed_reported_act_carries_the_cue(self):
        cued = [act for rows in R5B['inventory_acts'].values() for act in rows if act[4]]
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
        # the harness repair (H2R, refutation multi-3): "hemostatic" alone leaves the bleeding control in doubt, so the
        # act is no longer a performed one tied by a name, and 45382 is held as an act in doubt (round 5b: named_only)
        self.assertEqual([(a.lesion, a.status, CUE in a.cues, services.HEMOSTATIC_CUE in a.cues)
                          for a in acts(inv, kind='bleeding_control')], [(polyp_b, 'uncertain', False, True)])
        self.assertEqual([(a.lesion, CUE in a.cues) for a in acts(inv, 'gi.colonoscopy', 'clip')], [(polyp_b, False)])
        result = read(name)
        self.assertEqual({code: result[code][:3] for code in result},
                         {'43239': (READY, [], 'service'), '45385': (READY, [], 'service'),
                          '45382': (HELD, ['performed_status'], 'act_missing')})


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
        costs = [tuple(cell) for cell in R5B['declared_costs']['hold_class']['cost_cells']]
        fixes = [tuple(cell) for cell in R5B['fixes_against_base']]
        self.assertEqual(sorted(costs + fixes), sorted(tuple(m) for m in R5B['battery']))
        self.assertEqual((len(costs), len(fixes)), (22, 4))
        # round 5b adds one cost (the Z3 row's 45385, a Y3 shape) and moves none of the hold-only form's movements
        self.assertEqual(sorted(set(costs) - {tuple(c) for c in HOLD_ONLY['declared_costs']['hold_class']['cost_cells']}),
                         [(Z3, '45385', READY, HELD)])
        self.assertEqual(fixes, [tuple(cell) for cell in HOLD_ONLY['fixes_against_base']])
        self.assertIn(A3_CONTROL, [name for name, _, _, _ in costs])
        # the realistic shapes the class names each have a row among its costs
        for shape in R5B['declared_costs']['hold_class']['realistic_shapes']:
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
        moved = {(name, code) for name, code, _, _ in R5B['battery'] if name.startswith(PREFIX)}
        self.assertEqual({tuple(key.split(' | ')) for key in R5B['named_only_cells']} - moved,
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


# --- refutation round 5b's three fixes (amendment_20261104_hold_only_r5b), each through the path its finding used ------

class SecondReviewAddsTheHeldCodeTests(SimpleTestCase):
    """Fix (a), X-R5B-1 through engine.assess with the bounded second review's response: a code the re-check selects for
    the unproposed service of a hold-class document is added as a proposal from the second review and held
    [performed_status] (named_only) - never an informational alternative that leaves the service silently uncoded."""

    def test_the_named_only_code_is_added_held_and_the_service_is_accounted_for(self):
        for name in (Y3, H1146, Y1):
            with self.subTest(name):
                q = quotes(name)
                alone, result = second_reviewed(name, [('43239', q['43239'])], [('45385', q['45385'])])
                self.assertIn('colonoscopy (documented as performed) has no supported proposal',
                              [u['label'] for u in alone.completeness['unresolved_items'] if u['second_review']])
                (p,) = [p for p in result.proposals if p.code == '45385']
                self.assertEqual((p.bucket, p.status, [c.fact for c in p.clarifications], p.support['origin'],
                                  p.support['reason'], p.support['state']),
                                 ('selected', 'needs_clarification', ['performed_status'], 'second_review',
                                  'named_only', 'uncertain'))
                self.assertEqual([u for u in result.completeness['unresolved_items'] if u['family'] == 'gi.colonoscopy'],
                                 [])
                check = next(c for c in result.encounter_checks if c.id == 'provider.second_review')
                self.assertEqual(check.status, 'info')
                self.assertIn('selected 45385, added as a proposal for review', check.detail)

    def test_every_declared_second_review_case_merges_as_declared(self):
        declared = R5B['second_review']['cases']
        self.assertEqual(len(declared), 21)
        for name, expected in declared.items():
            with self.subTest(name):
                row, (primary, second) = second_review_case(name)
                _, result = second_reviewed(row, primary, second)
                self.assertEqual(merged_cells(result), expected)
                self.assertFalse(any(cell.startswith('45385 alternative') for cell in expected['cells']))

    def test_control_a_colonoscopy_only_note_adds_it_ready(self):
        name = 'R8 R5 control, a colonoscopy-only note with a label-only act'
        _, result = second_reviewed(name, [], [('45385', quotes(name)['45385'])])
        (p,) = [p for p in result.proposals if p.code == '45385']
        self.assertEqual((p.bucket, p.status, p.support['origin'], p.support['reason']),
                         ('selected', 'ready', 'second_review', 'service'))


class MergedCueTests(SimpleTestCase):
    """Fix (b), Y-F1 and Y-F2 through the inventory and the stages: a merged act keeps services.NAME_ONLY_CUE only when
    every statement of it carries it, so an impression restating the label-only snare with its size and site (Z1), or an
    addendum naming its site and service (Z2), lifts the hold in whichever order the statements come."""

    def test_a_sited_restatement_or_addendum_lifts_the_hold(self):
        for name, restatement in ((Z1, '2. 8 mm sigmoid colon polyp removed with a cold snare.'), (Z2, ADDENDUM)):
            with self.subTest(name):
                inv = inventory(text_of(name))
                (snare,) = acts(inv, 'gi.colonoscopy', 'snare')
                self.assertEqual([ev.text for ev in snare.evidence][1:], [restatement])
                self.assertEqual((snare.status, snare.lesion, CUE in snare.cues),
                                 ('performed', lesion_id(inv, 'gi.colonoscopy', '8 mm'), False))
                self.assertEqual(read(name)['45385'], (READY, [], 'service', []))
                self.assertEqual(DECLARED.get((name, '45385')), None)  # main reads it READY too: no movement

    def test_the_cue_survives_a_merge_unless_a_statement_names_its_own_site(self):
        # amendment_20261104_site_only_lift: only a statement naming a site of its own lifts the mark; one that names no
        # site (its service read from its sentence's instrument or its part: X-R5C-1) leaves it
        inv = inventory(text_of(Y1))
        (named,) = acts(inv, 'gi.colonoscopy', 'snare')  # the label-only statement: the cue
        self.assertIn(CUE, named.cues)
        self.assertEqual(named.anatomy, ())
        bare = tuple(c for c in named.cues if c != CUE)
        sited = replace(named, cues=bare, anatomy=('sigmoid colon',), evidence=named.evidence + named.evidence)
        unsited = replace(named, cues=bare, evidence=named.evidence + named.evidence)
        (merged,) = services._merge_acts([named, sited])
        self.assertNotIn(CUE, merged.cues)  # a statement of the act naming its site lifts the mark
        self.assertEqual(list(merged.cues), list(bare))
        (merged,) = services._merge_acts([named, unsited])
        self.assertIn(CUE, merged.cues)  # a statement naming no site of its own never does
        for first in (sited, unsited):
            with self.subTest(first_names_a_site=first is sited):
                (merged,) = services._merge_acts([first, named])
                self.assertNotIn(CUE, merged.cues)  # an uncued first statement keeps its own cues, as before
        (merged,) = services._merge_acts([named, replace(named, evidence=named.evidence)])
        self.assertIn(CUE, merged.cues)  # every statement label-only: the mark stays

    def test_a_label_only_act_with_no_restatement_stays_held(self):
        # the declared class: no statement of the act names its site, so the code stays held
        for name in (Y1, Y3, H1146):
            with self.subTest(name):
                self.assertEqual(read(name)['45385'], (HELD, ['performed_status'], 'named_only', []))


class SiteOnlyLiftTests(SimpleTestCase):
    """Refutation round 5c, X-R5C-1 and X-R5C-2 (amendment_20261104_site_only_lift): a restatement that names the
    colonoscope or the colonoscopy only to say the act came after it, or that names no site, leaves the name-only hold -
    the wrong colonoscopy code and the prophylactic clip's bleeding control stay held; a restatement naming the act's site
    still lifts it (Z1, Z2: MergedCueTests)."""

    WITHDRAWN = ('Impression: After withdrawal of the colonoscope, biopsies were taken with the same cold forceps used to '
                 'retrieve Polyp A.')
    CLIP = 'Impression: The hemostatic clip was placed prophylactically at the Polyp B stalk site during the colonoscopy.'

    def test_a_restatement_naming_no_site_of_its_own_keeps_the_hold(self):
        # the harness repair (H2R): the R2 row's 45382 is held as an act in doubt ("hemostatic" alone), not named_only
        for name, line, code, reason in (('R8 R5 R1 dash', self.WITHDRAWN, '45380', 'named_only'),
                                         ('R8 R5 R2 dash combined', self.CLIP, '45382', 'act_missing')):
            with self.subTest(name):
                text, codes = battery.CASES[name]
                self.assertEqual(read(name)[code][:3], (HELD, ['performed_status'], reason))  # the row alone
                restated = text.rstrip('\n') + '\n' + line + '\n'
                self.assertEqual(read(name, text=restated, codes=codes)[code],
                                 (HELD, ['performed_status'], reason, []))


class HeldCodeCarriesItsActsTests(SimpleTestCase):
    """Fix (c), X-R5B-2 through the stages and the review overlay: the named_only hold carries its acts, so the support
    record names them and the separate-lesion modifier review and considerations read them as main does; the code stays
    held."""

    def test_every_named_only_cell_names_its_acts(self):
        closed = H2R['named_only_cells_closed']  # the harness repair: the R2 combined row's 45382 is held as in doubt
        declared = {key: ids for key, ids in R5B['named_only_support_acts'].items() if key not in closed}
        self.assertEqual(sorted(declared), sorted(cell for cell in R5B['named_only_cells'] if cell not in closed))
        by_row = {}
        for key, ids in declared.items():
            name, code = key.split(' | ')
            by_row.setdefault(name, {})[code] = ids
        for name, codes in by_row.items():
            with self.subTest(name):
                found = support_acts(name)
                for code, ids in codes.items():
                    self.assertTrue(ids, key)
                    self.assertEqual(found[code], ids)

    def test_the_held_snare_keeps_its_modifier_review_and_considerations(self):
        from studio.validation import review_view
        text, codes = battery.CASES[Z3]
        result = run(text, [(code, quote) for code, quote, _ in codes])
        by_code = {p.code: p for p in result.proposals if p.bucket != 'alternative'}
        snare, biopsy = by_code['45385'], by_code['45380']
        self.assertEqual((snare.status, snare.support['reason'], [c.fact for c in snare.clarifications]),
                         ('needs_clarification', 'named_only', ['performed_status']))
        self.assertTrue(any('59 or XS' in m for m in snare.modifier_considerations), snare.modifier_considerations)
        self.assertTrue(any('59 or XS' in m for m in biopsy.modifier_considerations), biopsy.modifier_considerations)
        stored = [review_view.stored_from(p) for p in result.proposals]
        views = review_view.review_view(stored, {}, services=result.services,
                                        reference_sources=result.reference_sources)
        reviews = {v.code: (v.modifier_review or {}) for v in views.values() if v.bucket != 'alternative'}
        self.assertEqual((reviews['45385'].get('codes'), reviews['45385'].get('options')), (['45385', '45380'], ['59', 'XS']))
        self.assertEqual((reviews['45380'].get('codes'), reviews['45380'].get('options')), (['45380', '45385'], ['59', 'XS']))
        self.assertEqual(reviews['43239'], {})


@override_settings(**gi2.LIVE)
class SecondReviewApprovedExportTests(gi2.Harness):
    """Fix (a), X-R5B-1 through the customer API: after the bounded second review the snare code is a code that needs a
    detail - nothing is listed as an alternative only - and the approved export waits until it is decided."""

    def customer(self, encounter_id):
        reply = self.client.get(f'/api/encounters/{encounter_id}')
        self.assertEqual(reply.status_code, 200, reply.content)
        return reply.json()

    def approved_export(self, encounter_id):
        return self.post(f'/api/encounters/{encounter_id}/reports', {'kind': 'approved', 'fmt': 'txt'})

    def walk(self, name):
        q = quotes(name)
        self.use(TwoPassProvider(first=[('43239', q['43239'])], later=[('45385', q['45385'])]))
        encounter_id = self.create(text_of(name))
        drain()
        self.assertEqual([c['code'] for c in self.customer(encounter_id)['codes']], ['43239'])
        asked = self.post(f'/api/encounters/{encounter_id}/second-review')
        self.assertEqual(asked.status_code, 201, asked.content)
        drain()
        doc = self.customer(encounter_id)
        (held,) = [c for c in doc['codes'] if c['code'] == '45385']
        self.assertEqual((held['status'], held['allowed_actions']), ('needs_detail', ['reject']))
        self.assertEqual(doc['other_codes'], [])
        self.assertEqual(doc['unresolved'], [])
        self.approve(encounter_id, '43239')
        refused = self.approved_export(encounter_id)
        self.assertEqual(refused.status_code, 409, refused.content)
        self.assertEqual(refused.json()['details']['blockers'], ['45385 needs a detail.'])
        reply = self.post(f'/api/encounters/{encounter_id}/decisions', {'proposal_id': held['id'], 'action': 'reject'})
        self.assertEqual(reply.status_code, 201, reply.content)
        done = self.approved_export(encounter_id)
        self.assertEqual(done.status_code, 201, done.content)
        report = self.client.get(done.json()['download_url']).content.decode('utf-8')
        self.assertIn('1. 43239', report)
        self.assertNotIn('45385', report)

    def test_y3_the_approved_export_waits_for_the_added_code(self):
        self.walk(Y3)

    def test_1146_the_approved_export_waits_for_the_added_code(self):
        self.walk(H1146)


class AddendumLiftsTheHoldTests(tcs.SurfaceCase):
    """Fix (b), Y-F2 through the customer API: the physician's addendum, posted from the held code's detail row and
    naming the act's site and service, is assessed as revision 2 and lifts the hold; the code can then be approved.
    Corti is tests.test_customer_fixtures.CitingCorti and both participants agree; nothing is sent."""

    SELECTIONS = [('45385', (BY_NAME,)), ('43239', ('Cold forceps biopsies were taken from the gastric antrum.',))]

    def setUp(self):
        super().setUp()
        install_reference_store()
        self.text = text_of(Y1)
        self.inputs += [self.text, ADDENDUM, 'Synthetic round 5b addendum']

    def agreeing(self):
        for name in ('astra', 'fable'):
            self.adapters[name] = FakeParticipant(name, codes=[(code, cited[0]) for code, cited in self.SELECTIONS])

    def sent(self):
        self.agreeing()
        with mock.patch('studio.jobs.get_provider', return_value=CitingCorti(self.SELECTIONS)):
            encounter_id = self.create(text=self.text, title='Synthetic round 5b addendum')
            drain()
        return encounter_id

    def code(self, encounter_id, code):
        doc = self.detail(encounter_id)
        tcs.assert_contract(self, doc)
        (row,) = [c for c in doc['codes'] if c['code'] == code]
        return doc, row

    def approve(self, encounter_id, row):
        return self.signed_in(self.reviewer).post(
            f'/api/encounters/{encounter_id}/decisions', content_type='application/json',
            data=json.dumps({'proposal_id': row['id'], 'action': 'approve',
                             'acknowledgement': review.ACKNOWLEDGEMENTS[self.reviewer.actor_kind]}))

    def test_an_addendum_naming_the_site_and_service_lifts_the_hold(self):
        encounter_id = self.sent()
        doc, held = self.code(encounter_id, '45385')
        self.assertEqual((held['status'], held['allowed_actions']), ('needs_detail', ['reject']))
        (row,) = [r for r in doc['details_needed'] if r['fact'] == 'performed_status']
        self.assertTrue(row['addendum_allowed'])
        self.agreeing()
        with mock.patch('studio.jobs.get_provider', return_value=CitingCorti(self.SELECTIONS)):
            reply = self.signed_in(self.reviewer).post(
                f'/api/encounters/{encounter_id}/addenda', content_type='application/json',
                data=json.dumps({'text': ADDENDUM, 'clarification_id': row['id'], 'synthetic_attestation': 'yes'}))
            self.assertEqual(reply.status_code, 201, reply.content)
            drain()
        encounter = self.encounter(encounter_id)
        self.assertEqual((encounter.current_revision.number, encounter.current_revision.kind), (2, 'addendum'))
        doc, ready = self.code(encounter_id, '45385')
        self.assertEqual((ready['status'], ready['allowed_actions']), ('ready', ['approve', 'reject']))
        self.assertEqual([r for r in doc['details_needed'] if r['fact'] == 'performed_status'], [])
        snares = [a for s in encounter.current_assessment.services['services'] for a in s['acts'] if a['kind'] == 'snare']
        self.assertEqual([([e['text'] for e in a['evidence']], CUE in a['cues']) for a in snares],
                         [([BY_NAME, ADDENDUM], False)])
        reply = self.approve(encounter_id, ready)
        self.assertEqual(reply.status_code, 201, reply.content)

    def test_control_with_no_addendum_the_code_stays_held(self):
        encounter_id = self.sent()
        _, held = self.code(encounter_id, '45385')
        self.assertEqual(held['status'], 'needs_detail')
        reply = self.approve(encounter_id, held)
        self.assertEqual(reply.status_code, 409, reply.content)


@override_settings(**gi2.LIVE)
class ModifierReviewTests(gi2.Harness):
    """Fix (c), X-R5B-2 through the customer API: beside the held label-only snare (45385), the ready forceps removal
    of a second polyp (45380) keeps the separate-lesion modifier review, and approving it with XS succeeds."""

    def test_the_partner_code_offers_its_modifier_review_and_an_xs_approval_succeeds(self):
        q = quotes(Z3)
        self.use(TwoPassProvider(first=[(code, q[code]) for code in ('43239', '45385', '45380')], later=[]))
        encounter_id = self.create(text_of(Z3))
        drain()
        doc = self.client.get(f'/api/encounters/{encounter_id}').json()
        rows = {c['code']: c for c in doc['codes']}
        self.assertEqual((rows['45385']['status'], rows['45380']['status']), ('needs_detail', 'ready'))
        for code in ('45385', '45380'):
            with self.subTest(code):
                self.assertEqual(rows[code]['modifier_review']['options'], ['59', 'XS'])
        acknowledgement = self.client.get('/api/session').json()['acknowledgement']
        reply = self.post(f'/api/encounters/{encounter_id}/decisions',
                          {'proposal_id': rows['45380']['id'], 'action': 'approve',
                           'acknowledgement': acknowledgement, 'modifiers': ['XS']})
        self.assertEqual(reply.status_code, 201, reply.content)
        self.assertEqual(reply.json()['decision']['modifiers'], ['XS'])
