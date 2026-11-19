"""What the engine exposes for the blind acceptance set (docs/gemini-migration/FINAL-V2.md 9.1; step 5a of its 8.1;
cpt-studio-measure@1), TEXT-ONLY and SYNTHETIC: engine/measure.py's export of one run of one document.

What is proved here:
- the export matches 9.1's shape exactly: 9.1's own JSON block is parsed out of FINAL-V2.md at test time, and every key
  of every record, every list's element shape and every value's type are compared with an export of a dummy assessment
  whose every part 9.1 shows is populated (an excluded code with its exclusion, a held code with its item, held facts,
  trace witnesses and considerations, kept and dropped unlisted statements, doubts, facts with verdicts, relations,
  health) - so a key added, dropped or renamed on either side turns it red;
- it runs on a dummy assessment (a hand-built FactSet and row view) and on a stored v2 row (written by store.row_v2 and
  read back: tests/v2/test_facts.py's synthetic colonoscopy) through the default facts.effective;
- it is JSON data, deterministic, holds no ``text`` or ``words`` key and no slice of the revision;
- health is settle's 3.2.6 measures as shares, None where nothing was measured; unlisted and doubts are offsets, a unit
  id the row does not have left out (a storable row always exports: the refutation's P5).

Schema @2 (AMENDMENT-2 section 6 part 1, its step F9; D292's FX-SCORE), on rows store.row_v2 writes and load_v2 reads:
- @2 is @1 and ``events``: every @1 key equal to what @1 writes for the same input (so every @1 reader is unaffected,
  and the tests above are unchanged), ``events`` keyed as AMENDMENT-2's own text writes it (parsed from AMENDMENT-2.md);
- a READY anchored on its act's own statement, whose expected act span lies on an impression line that retells that act
  and that no event anchors, counts as that act through @2's events - the scorer's rule (AMENDMENT-2 section 6 part 2,
  widened by D292) restated here as an oracle - and not through @1, which has no events;
- only a line that retells the act is listed: role restates or summarizes, G6 counted (the role's source geometry),
  its role claim's geometry check passed, none of its units any event's anchor unit, every unit in the row; a line
  another event retells too, or one only another event retells, refuses the READY; a title never counts; and, as D292
  rules the class, only an event listing a restatement @2 lists is a lister (step f9's QUESTION Q1);
- a restatement record no row holds is refused, never dropped (a dropped lister would loosen the every-lister rule).
Every document and fact here is written for this test: no real patient, no development or acceptance document.
"""
from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import replace
from pathlib import Path

from django.test import SimpleTestCase

from studio import interpretation
from studio.interpretation.contract import types as ct
from studio.interpretation.engine import assess as AS
from studio.interpretation.engine import facts as F
from studio.interpretation.engine import measure as M
from studio.interpretation.engine.types import Span
from tests.v2 import evaluate_fixtures as EF
from tests.v2 import test_assess as TA

APP = Path(__file__).resolve().parents[2]
DESIGN = APP / 'docs' / 'gemini-migration' / 'FINAL-V2.md'
A, Kind = ct.Attribute, ct.Kind
sup, neg, X, E = EF.sup, EF.neg, EF.X, EF.E
DAY = TA.DAY


def design_shape() -> dict:
    """9.1's JSON block, as FINAL-V2.md writes it (the first ```json fence after its 9.1 heading)."""
    lines = DESIGN.read_text(encoding='utf-8').splitlines()
    start = next(index for index, line in enumerate(lines) if line.startswith('### 9.1 '))
    opening = next(index for index in range(start, len(lines)) if lines[index].startswith('```json'))
    closing = next(index for index in range(opening + 1, len(lines)) if lines[index].startswith('```'))
    return json.loads('\n'.join(lines[opening + 1:closing]))


# The fields 9.1 shows with a record or a value that an export may leave empty: a code with no item (READY) or no
# exclusion, a READY row's witness, a fact with no verdict or control, an encounter-scope subject, an unappraised value.
NULLABLE = {'item', 'exclusion', 'witness', 'verdict', 'control', 'subject', 'inherited_from', 'reason', 'result',
            'value', 'rank', 'session', 'kind', 'row', 'appraisal', 'controls_coherent', 'absorbed_by', 'attribute',
            'state'}


def mismatches(example, found, path='$') -> list:
    """Where ``found`` differs from 9.1's ``example`` in shape: keys, list element shapes and value types."""
    if isinstance(example, dict):
        if not isinstance(found, dict):
            return [f'{path}: a record expected, {type(found).__name__} found']
        if set(example) == {'...'}:  # 9.1 writes pass2 as {"...": "the same"}: pass1's shape
            return []
        out = []
        if set(example) != set(found):
            out.append(f'{path}: keys {sorted(set(found) ^ set(example))} differ')
        for key in sorted(set(example) & set(found)):
            if found[key] is None and key in NULLABLE:
                continue
            out += mismatches(example[key], found[key], f'{path}.{key}')
        return out
    if isinstance(example, list):
        if not isinstance(found, list):
            return [f'{path}: a list expected, {type(found).__name__} found']
        if not example:
            return []
        return [problem for index, item in enumerate(found)
                for problem in mismatches(example[0], item, f'{path}[{index}]')]
    if isinstance(example, bool):
        return [] if isinstance(found, bool) else [f'{path}: a boolean expected']
    if isinstance(example, int):
        return [] if type(found) is int else [f'{path}: an integer expected, {found!r} found']
    if isinstance(example, float):
        return [] if isinstance(found, float) else [f'{path}: a number expected, {found!r} found']
    if isinstance(example, str):
        return [] if isinstance(found, str) else [f'{path}: a string expected, {found!r} found']
    return [f'{path}: unexpected {example!r}']


def populated(example, found, path='$') -> list:
    """Every key 9.1 shows is non-empty somewhere in ``found``: at each path of the example, at least one of the values
    the export holds there (across every element of every list) is neither None nor empty - so the shape test compares
    real elements, never only empty lists or nulls."""
    out = []

    def values_at(nodes, key):
        return [node.get(key) for node in nodes if isinstance(node, dict)]

    def walk(example, nodes, where):
        if isinstance(example, dict):
            if set(example) == {'...'}:
                return
            for key, value in example.items():
                if value == []:
                    continue  # 9.1 shows no element of it (service_questions): nothing to compare
                present = [node for node in values_at(nodes, key) if node not in (None, [], {})]
                if not present:
                    out.append(f'{where}.{key} is empty')
                    continue
                walk(value, present, f'{where}.{key}')
        elif isinstance(example, list) and example:
            elements = [item for node in nodes if isinstance(node, list) for item in node]
            if not elements:
                out.append(f'{where} is empty')
                return
            walk(example[0], elements, f'{where}[*]')

    walk(example, [found], path)
    return out


# --- a dummy assessment whose every part 9.1 shows is populated -------------------------------------------------------


def excluded_and_held() -> EF.Doc:
    """A colonoscopy X1, its examination begun and not completed (52/53), whose reach to the splenic flexure pass 2 left
    unclear (COLFULL asks the extent) with the cold snare removal E2 (45385 held: extent); E3 "No biopsies were taken."
    - a broad denial of biopsies, its kind and status words the whole of its unit, which 45380 cites (EXCLUDED by
    citation, 4.6); and E4, "At the 2023 colonoscopy no polyp was removed.", a denial of removals at another date, which
    pairs with the snare INDEPENDENT by its timing."""
    doc = EF.Doc()
    doc.session(1, ct.SessionKind.COLONOSCOPY, encounter=sup(ct.EncounterRelation.THIS_ENCOUNTER),
                reached=[EF.unres(ct.Extent.SPLENIC_FLEXURE)])
    doc.exam(1, status=sup(ct.Status.ATTEMPTED_NOT_COMPLETED))
    doc.lesion(1, lesion_places=[sup(ct.Landmark.SIGMOID_COLON)])
    doc.act(2, Kind.SNARE, places=[sup(ct.Landmark.SIGMOID_COLON)], lesion=sup(EF.L(1)),
            device=sup(ct.Device.COLD_SNARE))
    doc.act(3, Kind.BIOPSY, status=neg(ct.Status.PERFORMED), breadth=sup(ct.Breadth.ALL_OF_KIND),
            kind_words=Span(300, 330), status_words=Span(330, 360))
    doc.act(4, Kind.REMOVAL, status=neg(ct.Status.PERFORMED), date=sup(ct.DateRelation.EARLIER_DATE),
            breadth=sup(ct.Breadth.ALL_OF_KIND))
    return doc


def view() -> dict:
    """A row view in store.textfree_v2's shape for the dummy assessment: units, one stored fact with its verdicts, a
    kept unlisted doubt and a doubt pass 1 reported."""
    units = [{'id': f'S{n}', 'start': 100 * n, 'end': 100 * n + 60, 'line': n, 'paragraph': n, 'page': 1,
              'forced': False} for n in range(1, 6)]
    appraised = {'claim': 'K1', 'content': '0' * 64, 'verdict': 'supports', 'attached': 'yes', 'qualifiers': [],
                 'evidence': ['S2'], 'control': {'claim': 'K2', 'verdict': 'contradicts'}}
    kind = {'claim': {'state': 'supported', 'value': 'snare', 'qualifiers': [], 'options': [], 'inherited_from': None},
            'sources': [{'units': ['S2'], 'link': 'statement', 'at': {'start': 200, 'end': 210}, 'geometry': 'ok'}],
            'checks': {}, 'appraisal': appraised, 'result': 'supported', 'reasons': []}
    relation = {'claim': {'state': 'supported', 'value': 'on_date_of_service', 'qualifiers': [], 'options': [],
                          'inherited_from': 'N2'},
                'sources': [], 'checks': {}, 'appraisal': None, 'result': 'unresolved',
                'reasons': ['appraisal_unclear']}
    silent = {'claim': {'state': None, 'value': '', 'qualifiers': [], 'options': [], 'inherited_from': None},
              'sources': [], 'checks': {}, 'appraisal': None, 'result': 'unknown', 'reasons': ['silent']}
    return {'units': units,
            'encounter': {'date_of_service': silent, 'other_dates': [], 'documenting_clinician': silent},
            'people': [], 'sections': [], 'anatomy': [], 'lesions': [],
            'sessions': [{'id': 'X1', 'kind': silent, 'reached': [silent], 'completeness': None}],
            'events': [{'id': 'E2', 'anchor': {'units': ['S2'], 'kind_words': None, 'status_words': None},
                        'restatements': [], 'kind': kind, 'date_relation': relation,
                        'target': {'places': [kind, silent]}}],
            'doubts': [{'about': 'date_relation', 'objects': ['E2'], 'units': ['S2'], 'basis': 'unclear',
                        'readings': ['earlier_date']}],
            'claims': [], 'unlisted': [{'units': ['S4', 'S5'], 'what': 'doubt', 'kind': 'snare', 'session': 'X1'}]}


def report() -> dict:
    return {'unlisted': {'kept': 1, 'dropped': [{'units': ['S5'], 'what': 'act', 'kind': 'snare', 'session': 'X1',
                                                 'event': 'E2'}]},
            'health': {'pairs': 20, 'not_rejected': 1, 'claims': 40, 'established': 38, 'verdicts': 60, 'missing': 0,
                       'refused': []}}


def runs() -> dict:
    run = M.Run('6f1c3f0e-2a8b-4c55-9a51-0d6c1b7e2003', '2' * 64, '3' * 64, interpretation.MODEL, M.Usage(100, 20, 5),
                0.01, 1.5)
    return {'pass1': run, 'pass2': replace(run, run='6f1c3f0e-2a8b-4c55-9a51-0d6c1b7e2004', request_sha256='4' * 64,
                                           response_sha256='5' * 64)}


def dummy() -> tuple:
    """(the export, the assessment, the FactSet) of the dummy: 45385 held and 45380 excluded, an office-free
    colonoscopy on the date of service."""
    R = TA.dated(excluded_and_held().build())
    assessment = TA.run(R, ('45385', 2), ('45380', AS_SPAN))
    data = M.export(assessment, view=view(), report=report(), case=M.Case('a' * 64, 'b' * 64, 1),
                    label=M.Label.SYNTHETIC, guard=M.Guard(0, 0), R=R, **runs())
    return data, assessment, R


AS_SPAN = TA.EvidenceSpan(0, 300, 360, TA.TEXT[300:360], True)


class ShapeTests(SimpleTestCase):
    def test_the_export_matches_9_1s_shape_key_for_key(self):
        example = design_shape()
        data, assessment, _ = dummy()
        self.assertEqual({p.code: p.status for p in assessment.codes},
                         {'45385': AS.Outcome.NEEDS_CLARIFICATION, '45380': AS.Outcome.EXCLUDED})
        self.assertEqual(mismatches(example, data), [])
        self.assertEqual(populated(example, data), [])
        self.assertEqual(data['schema'], 'cpt-studio-measure@1')
        self.assertEqual(set(data['runs']['pass2']), set(example['runs']['pass1']))

    def test_the_shape_test_refuses_a_key_added_dropped_or_retyped(self):
        example = design_shape()
        data, _, _ = dummy()
        added = json.loads(json.dumps(data))
        added['codes'][0]['key'] = 'sel:0'
        dropped = json.loads(json.dumps(data))
        del dropped['encounter']['doubts']
        retyped = json.loads(json.dumps(data))
        retyped['case']['run_index'] = '1'
        for name, broken in (('added', added), ('dropped', dropped), ('retyped', retyped)):
            with self.subTest(case=name):
                self.assertTrue(mismatches(example, broken))
        emptied = json.loads(json.dumps(data))
        emptied['relations'] = []
        self.assertTrue(populated(example, emptied))

    def test_the_codes_carry_their_acts_item_trace_exclusion_and_considerations(self):
        data, _, _ = dummy()
        codes = {code['code']: code for code in data['codes']}
        held, excluded = codes['45385'], codes['45380']
        self.assertEqual((held['origin'], held['proposed_by'], held['status']),
                         ('corti', ['corti'], 'needs_clarification'))
        self.assertEqual(held['acts'], [{'event': 'E2', 'kind': 'snare', 'session': 'X1', 'anchor': [[200, 260]]}])
        self.assertEqual((held['item']['fact'], held['item']['kind'], held['item']['subject'], held['item']['cause']),
                         ('extent', 'question', 'X1', 'appraisal:unclear'))
        self.assertIn({'requirement': 'COLFULL', 'truth': 'U', 'witness': {
            'subject': 'X1', 'attribute': 'reached', 'result': 'unresolved', 'reason': 'appraisal_unclear'}},
            held['trace'])
        self.assertEqual(held['held_facts'], [{'fact': 'extent', 'subject': 'X1', 'result': 'unresolved',
                                               'reason': 'appraisal_unclear', 'cause': 'appraisal:unclear',
                                               'rank': 14}])
        self.assertEqual(excluded['exclusion'], {'event': 'E3', 'fact': 'status', 'cover': 'citation',
                                                 'anchor': [[300, 360]]})
        self.assertEqual((excluded['status'], excluded['item'], excluded['held_facts']), ('excluded', None, []))
        self.assertEqual((held['considerations'], excluded['considerations']), (['52|53'], []))


class ContentTests(SimpleTestCase):
    def test_encounter_health_facts_relations_and_guard(self):
        data, _, _ = dummy()
        encounter = data['encounter']
        self.assertEqual(encounter['date_of_service'], {'value': '2026-11-09', 'result': 'supported'})
        self.assertEqual(encounter['unlisted'], {'kept': [[400, 560]],
                                                 'dropped': [{'units': [[500, 560]], 'absorbed_by': 'E2'}]})
        self.assertEqual(encounter['doubts'], [{'about': 'date_relation', 'objects': ['E2'], 'basis': 'unclear',
                                                'units': [[200, 260]]}])
        self.assertEqual(data['health'], {'appraisal': 38 / 40, 'controls_coherent': 19 / 20})
        self.assertEqual(M.health({}), {'appraisal': None, 'controls_coherent': None})
        facts = data['facts']
        self.assertEqual([(fact['subject'], fact['attribute']) for fact in facts],
                         [(None, 'date_of_service'), (None, 'documenting_clinician'), ('X1', 'kind'),
                          ('X1', 'reached'), ('E2', 'kind'), ('E2', 'date_relation'), ('E2', 'target.places'),
                          ('E2', 'target.places')])
        self.assertEqual(facts[4]['verdict'], 'supports')
        self.assertEqual(facts[4]['control'], 'contradicts')
        self.assertEqual(facts[5]['inherited_from'], 'N2')
        self.assertEqual(data['guard'], {'legacy_calls': 0, 'retired_calls': 0})
        # AMENDMENT-2 8.1: the D22 labels engine/assess.versions() writes (the @3 pair, inventory and engine), and
        # cpt-requirements@2 since DECISIONS D292, @3 since D324 (11)
        self.assertEqual(data['versions'], {'interpretation': 'gemini-events@3/appraisal@2',
                                            'inventory': 'gemini-inventory@3', 'requirements': 'cpt-requirements@3',
                                            'engine': 'cpt-studio-events@3'})
        self.assertEqual(data['relations'], [{'statement': 'E4', 'act': 'E2', 'type': 'INDEPENDENT', 'row': 'timing'}])

    def test_a_unit_the_row_does_not_have_is_left_out_never_a_failed_export(self):
        """3.1 I1's unit_unknown is an item-level finding and the store keeps pass 1's doubts as given, so a storable row
        may hold a doubt (or an unlisted statement) citing a unit id the row does not have: the export leaves that unit
        out, as engine/facts.py reads it, and exports the rest (the refutation's P5: it raised). A cited id that is no
        string is no row's and is refused."""
        data, assessment, R = dummy()
        broken = view()
        broken['doubts'] += [{'about': 'kind', 'objects': ['E2'], 'units': ['S99'], 'basis': 'unclear', 'readings': []},
                             {'about': 'kind', 'objects': ['E2'], 'units': ['S99', 'S3'], 'basis': 'stated',
                              'readings': []}]
        broken['unlisted'] += [{'units': ['S99', 'S1'], 'what': 'act', 'kind': 'biopsy', 'session': 'X1'}]
        found = M.export(assessment, view=broken, report=report(), case=M.Case('a' * 64, 'b' * 64, 1),
                         label=M.Label.SYNTHETIC, guard=M.Guard(0, 0), R=R, **runs())
        self.assertEqual([doubt['units'] for doubt in found['encounter']['doubts']], [[[200, 260]], [], [[300, 360]]])
        self.assertEqual(found['encounter']['unlisted']['kept'], [[400, 560], [100, 160]])
        self.assertEqual(mismatches(design_shape(), found), [])
        self.assertEqual({key: value for key, value in found.items() if key != 'encounter'},
                         {key: value for key, value in data.items() if key != 'encounter'})
        unnamed = view()
        unnamed['doubts'][0]['units'] = [7]
        with self.assertRaises(ValueError):
            M.export(assessment, view=unnamed, report=report(), case=M.Case('a' * 64, 'b' * 64, 1),
                     label=M.Label.SYNTHETIC, guard=M.Guard(0, 0), R=R, **runs())

    def test_a_path_that_is_no_attribute_is_refused(self):
        broken = view()
        broken['events'][0]['nonsense'] = broken['events'][0]['kind']
        with self.assertRaises(ValueError):
            M.stored_facts(broken)

    def test_json_deterministic_and_text_free(self):
        first, _, _ = dummy()
        second, _, _ = dummy()
        self.assertEqual(json.dumps(first, sort_keys=True), json.dumps(second, sort_keys=True))
        keys, strings, stack = set(), set(), [first]
        while stack:
            item = stack.pop()
            if isinstance(item, dict):
                keys |= set(item)
                stack += list(item.values())
            elif isinstance(item, list):
                stack += item
            elif isinstance(item, str):
                strings.add(item)
        self.assertFalse({'text', 'words', 'quote'} & keys)
        self.assertFalse({value for value in strings if len(value) >= 12 and value in TA.TEXT})


class StoredRowTests(SimpleTestCase):
    def test_the_export_runs_on_a_stored_row_through_effective(self):
        from tests.v2 import test_facts as TF

        content = TF.colonoscopy()
        stored = TF.stored(content)
        row = TF.view(content)
        at = TF.unit_span(6)
        proposals = TA.NormalizedResponse('corti', 'synthetic@1', codes=(TA.ProviderCode(
            'selected', 'CPT', '45385', '', (TA.EvidenceSpan(0, at.start, at.end, TF.TEXT[at.start:at.end], True),)),))
        assessment = AS.assess(inventory=row, date_of_service=DAY, text=TF.TEXT, pages=(), integrity=TA.Integrity(),
                               provider_status='succeeded', proposals=proposals, reference=TA.Lookup(),
                               member=TA.ENTERED, label=str)
        data = M.export(assessment, view=row, report=stored.verification, case=M.Case('a' * 64, TF.TEXT_SHA256, 2),
                        label=M.Label.REPLAY, guard=M.Guard(0, 0), **runs())
        self.assertEqual(data, M.export(assessment, view=row, report=stored.verification,
                                        case=M.Case('a' * 64, TF.TEXT_SHA256, 2), label=M.Label.REPLAY,
                                        guard=M.Guard(0, 0), R=F.effective(row, DAY), **runs()))
        self.assertEqual(mismatches(design_shape(), data), [])
        self.assertEqual(len(data['facts']), sum(1 for _ in M._facts_in(row['encounter'], ''))
                         + sum(1 for family in ('people', 'sections', 'sessions', 'anatomy', 'lesions', 'events')
                               for item in row[family] for _ in M._facts_in(item, '')))
        self.assertEqual(data['encounter']['doubts'][0]['objects'], ['E3'])
        self.assertEqual(json.loads(json.dumps(data)), data)

    def test_a_stored_row_whose_doubt_cites_a_unit_it_does_not_have_exports(self):
        """The refutation's P5 on a row the store itself writes and reads back: the synthetic colonoscopy with one more
        doubt citing S99, as settle stores pass 1's doubts; store, assess and the export all accept it, the doubt with no
        span."""
        from studio.interpretation import store
        from tests.v2 import test_facts as TF

        content = TF.colonoscopy()
        self.assertNotIn('S99', {unit['id'] for unit in content['units']})
        content['doubts'] = list(content['doubts']) + [{'about': 'kind', 'objects': ['E2'], 'units': ['S99'],
                                                         'basis': 'unclear', 'readings': []}]
        stored = TF.stored(content)
        row = store.textfree_v2(stored)
        at = TF.unit_span(6)
        proposals = TA.NormalizedResponse('corti', 'synthetic@1', codes=(TA.ProviderCode(
            'selected', 'CPT', '45385', '', (TA.EvidenceSpan(0, at.start, at.end, TF.TEXT[at.start:at.end], True),)),))
        assessment = AS.assess(inventory=row, date_of_service=DAY, text=TF.TEXT, pages=(), integrity=TA.Integrity(),
                               provider_status='succeeded', proposals=proposals, reference=TA.Lookup(),
                               member=TA.ENTERED, label=str)
        data = M.export(assessment, view=row, report=stored.verification, case=M.Case('a' * 64, TF.TEXT_SHA256, 1),
                        label=M.Label.REPLAY, guard=M.Guard(0, 0), **runs())
        self.assertEqual(data['encounter']['doubts'][-1], {'about': 'kind', 'objects': ['E2'], 'basis': 'unclear',
                                                           'units': []})
        self.assertEqual(mismatches(design_shape(), data), [])


# --- schema @2 (AMENDMENT-2 section 6 part 1, its step F9; D292's FX-SCORE) ------------------------------------------

AMENDMENT_2 = APP / 'docs' / 'gemini-migration' / 'AMENDMENT-2.md'


def events_shape() -> dict:
    """AMENDMENT-2 section 6 part 1's event entry, as its own text writes it ("`events: [{event, anchor: SPANS,
    restatements: SPANS}]`"): {key: its kind, '' for a bare name}."""
    text = AMENDMENT_2.read_text(encoding='utf-8')
    opening = '`events: [{'
    start = text.index(opening) + len(opening)
    body = text[start:text.index('}]`', start)]
    return {name.strip(): kind.strip() for name, _, kind in (item.partition(':') for item in body.split(','))}


def design_shape_2() -> dict:
    """@2's example: 9.1's JSON block and AMENDMENT-2's event entry (an id; SPANS as 9.1 writes offsets)."""
    example = design_shape()
    example['events'] = [{name: [[0, 0]] if kind == 'SPANS' else 'E3' for name, kind in events_shape().items()}]
    return example


def without(data: dict, *keys) -> dict:
    return {key: value for key, value in data.items() if key not in keys}


def role(value: str, units, geometry: str = 'ok', checked: str = 'ok', *, located: str = 'words') -> dict:
    """A restatement's role as contract/settle.py:role stores it: pass 1's value, supported and unappraised; its one
    source the restatement's own units (link other_statement), G6's verdict as its geometry; ``checked``, its checks'
    geometry. ``located``: 'words' as store.row_v2 is given a source, 'at' as store.textfree_v2's view holds it."""
    return {'claim': {'state': 'supported', 'value': value, 'qualifiers': [], 'options': [], 'inherited_from': None},
            'sources': [{'units': list(units), 'link': 'other_statement', located: None, 'geometry': geometry}],
            'checks': {'integrity': 'ok', 'geometry': checked, 'literal': 'ok', 'literals': [], 'consistency': 'ok',
                       'qualified': False},
            'appraisal': None, 'result': 'unresolved', 'reasons': ['unappraised']}


def retold_view() -> dict:
    """The dummy's row view with E2 retold by S3 (a summarizes line G6 counted) and named by S1 (a title)."""
    found = view()
    found['events'][0]['restatements'] = [{'units': ['S3'], 'role': role('summarizes', ['S3'], located='at')},
                                          {'units': ['S1'], 'role': role('title', ['S1'], located='at')}]
    return found


# A synthetic colonoscopy note written for this test (no real patient), one unit per line: its snares told in findings,
# then retold by impression lines.
RETOLD_LINES = (
    'SYNTHETIC COLONOSCOPY NOTE - FICTIONAL PATIENT - NOT FOR CLINICAL USE',  # S1: the title
    'Date of service: 11/09/2026',  # S2
    'Endoscopist: Synthetic Endoscopist, MD (fictional)',  # S3
    'Findings: The colonoscope was advanced to the cecum.',  # S4: E1, the examination
    'A 5 mm sessile polyp in the descending colon was removed with a cold snare.',  # S5: E2, a snare
    'A 4 mm sessile polyp in the transverse colon was removed with a cold snare.',  # S6: E3, a second snare
    'Impression: Cold snare polypectomy in the descending colon.',  # S7: retells E2
    'Impression: Colonoscopy to the cecum with two cold snare polypectomies.',  # S8: retells both snares
)
RETOLD_TEXT = '\n'.join(RETOLD_LINES) + '\n'
RETOLD_SHA256 = hashlib.sha256(RETOLD_TEXT.encode('utf-8')).hexdigest()


def line(n: int) -> list:
    """S<n>'s [start, end] in RETOLD_TEXT."""
    start = sum(len(item) + 1 for item in RETOLD_LINES[:n - 1])
    return [start, start + len(RETOLD_LINES[n - 1])]


def retold_at(words: str, after: str = '') -> dict:
    """Words located in RETOLD_TEXT where they first occur at or after ``after``: the revision's own slice."""
    start = RETOLD_TEXT.index(words, RETOLD_TEXT.index(after) if after else 0)
    return {'start': start, 'end': start + len(words), 'text': words}


def retold(*, second: bool = False, restated: dict | None = None) -> tuple:
    """(the stored row, store.textfree_v2's view) of RETOLD_TEXT, written by store.row_v2 and read back by load_v2: a
    colonoscopy X1 to the cecum (its examination E1, S4) with the cold snare E2 (S5) and, with ``second``, the cold
    snare E3 (S6), each act's facts established as settle establishes them (tests/v2/test_facts.py's shapes);
    ``restated``: {event id: [(role, units[, geometry[, checked]])]}, each event's restatements, none by default."""
    from studio.interpretation import store
    from tests.v2 import test_facts as TF

    k, src, est = TF.Ledger(), TF.src, TF.est
    dos = lambda: src(['S2'], 'document_frame', retold_at('11/09/2026'))  # noqa: E731
    clinician = lambda: src(['S3'], 'document_frame')  # noqa: E731
    findings = lambda: src(['S4'], 'section', retold_at('Findings:'))  # noqa: E731
    inherited = dict(inherited_from='N1')
    sections = [
        TF.section('N0', src([], 'section'), owner=TF.fact('documenting_clinician', [clinician()]),
                   role=TF.fact('header', [src(['S1'], 'section')]), occasion=TF.fact('on_date_of_service', [dos()]),
                   performer=TF.fact('documenting_team', [clinician()])),
        TF.section('N1', findings(), owner=TF.fact('documenting_clinician', [clinician()]),
                   role=TF.fact('findings', [src(['S4'], 'section')]),
                   occasion=est(k, 'N1', 'occasion', 'on_date_of_service', [dos()], control='earlier_date',
                                literals=TF.DAY),
                   performer=TF.fact('documenting_team', [clinician()])),
    ]
    sessions = [TF.session('X1', examination=TF.fact('E1', [src(['S4'])]),
                           kind=est(k, 'X1', 'kind', 'colonoscopy', [src(['S1'], 'document_frame')], control='flex_sig'),
                           encounter=est(k, 'X1', 'encounter', 'this_encounter', [src(['S4'])]),
                           reached=[est(k, 'X1', 'reached', 'cecum',
                                        [src(['S4'], words=retold_at('advanced to the cecum'))], control='cecum')])]

    def done(name: str, unit: str) -> dict:
        """An act's status, session, timing, performer and entry, established."""
        return dict(status=est(k, name, 'status', 'performed', [src([unit])], control='performed'),
                    session=est(k, name, 'session', 'X1', [src([unit])], control='X2'),
                    date_relation=est(k, name, 'date_relation', 'on_date_of_service', [dos()],
                                      control='earlier_date', literals=TF.DAY, **inherited),
                    performer=est(k, name, 'performer', 'documenting_team', [clinician()],
                                  control='other_clinician', **inherited),
                    entry=est(k, name, 'entry', 'documenting_clinician', [findings()], control='nursing',
                              **inherited))

    def snare(name: str, unit: str, lesion: str, place: str, after: str) -> dict:
        words = retold_at('cold snare', after)
        return TF.event(name, [unit], words, retold_at('was removed', after),
                        kind=est(k, name, 'kind', 'snare', [src([unit], words=words)], control='emr'),
                        target={'lesion': est(k, name, 'target.lesion', lesion, [src([unit])]),
                                'places': [est(k, name, 'target.places', place,
                                               [src([unit], words=retold_at(place.replace('_', ' '), after))],
                                               control='rectum')]},
                        technique={'device': est(k, name, 'technique.device', 'cold_snare',
                                                 [src([unit], words=words)])},
                        **done(name, unit))

    lesions = [TF.lesion('L1', src(['S5'], words=retold_at('5 mm sessile polyp')),
                         places=[est(k, 'L1', 'places', 'descending_colon',
                                     [src(['S5'], words=retold_at('descending colon'))])])]
    events = [TF.event('E1', ['S4'], retold_at('colonoscope'), retold_at('was advanced'),
                       kind=est(k, 'E1', 'kind', 'examination', [src(['S4'], words=retold_at('colonoscope'))]),
                       **done('E1', 'S4')),
              snare('E2', 'S5', 'L1', 'descending_colon', 'A 5 mm')]
    k.pair('E2', 'target.places', 'rectum', ['S5'], 'contradicts')
    if second:
        lesions.append(TF.lesion('L2', src(['S6'], words=retold_at('4 mm sessile polyp')),
                                 places=[est(k, 'L2', 'places', 'transverse_colon',
                                             [src(['S6'], words=retold_at('transverse colon'))])]))
        events.append(snare('E3', 'S6', 'L2', 'transverse_colon', 'A 4 mm'))
        k.pair('E3', 'target.places', 'rectum', ['S6'], 'contradicts')
    for event in events:
        for value, units, *checks in (restated or {}).get(event['id'], ()):
            event['restatements'].append({'units': list(units), 'role': role(value, units, *checks)})
    people = [{'id': 'P1', 'name': src(['S3'], words=retold_at('Synthetic Endoscopist')),
               'role': TF.fact('documenting_clinician', [src(['S3'])])}]
    content = {'units': [{'id': f'S{n}', 'start': line(n)[0], 'end': line(n)[1], 'line': n, 'paragraph': n, 'page': 1,
                          'forced': False} for n in range(1, len(RETOLD_LINES) + 1)],
               'encounter': TF.encounter(est(k, '', 'date_of_service', '2026-11-09', [dos()], literals=TF.DAY), [],
                                         TF.fact('P1', [clinician()])),
               'people': people, 'sections': sections, 'sessions': sessions, 'anatomy': [], 'lesions': lesions,
               'events': events, 'doubts': [], 'claims': k.claims, 'unlisted': []}
    fields = store.row_v2(encounter_id=TF.ENCOUNTER, revision_id=TF.REVISION, provider_run_id=TF.RUN,
                          appraisal_run_id=TF.APPRAISAL_RUN, revision_text=RETOLD_TEXT, text_sha256=RETOLD_SHA256,
                          request_sha256='2' * 64, response_sha256='3' * 64, appraisal_request_sha256='4' * 64,
                          appraisal_response_sha256='5' * 64, events=content, verification=TF.report(0))
    stored = store.load_v2(json.loads(json.dumps(fields)), text_sha256=RETOLD_SHA256, response_sha256='3' * 64,
                           appraisal_response_sha256='5' * 64)
    return stored, store.textfree_v2(stored)


def exported(*, schema=M.Schema.V2, codes=(('45385', 5),), **row) -> dict:
    """The export of the retold note (``retold(**row)``), assessed with the proposal provider selecting each (code, unit)
    on that unit's own words; ``schema`` None calls export with no schema, as an @1 caller does."""
    stored, found = retold(**row)
    proposals = TA.NormalizedResponse('corti', 'synthetic@1', codes=tuple(
        TA.ProviderCode('selected', 'CPT', code, '', (TA.EvidenceSpan(0, *line(n), RETOLD_TEXT[slice(*line(n))], True),))
        for code, n in codes))
    assessment = AS.assess(inventory=found, date_of_service=DAY, text=RETOLD_TEXT, pages=(), integrity=TA.Integrity(),
                           provider_status='succeeded', proposals=proposals, reference=TA.Lookup(), member=TA.ENTERED,
                           label=str)
    return M.export(assessment, view=found, report=stored.verification, case=M.Case('a' * 64, RETOLD_SHA256, 1),
                    label=M.Label.SYNTHETIC, guard=M.Guard(0, 0), **({} if schema is None else {'schema': schema}),
                    **runs())


def overlaps(first: list, second: list) -> bool:
    return first[0] < second[1] and second[0] < first[1]


def counted_as(export: dict, code: str, expected: list) -> str:
    """How the scorer counts a READY row's act against its expected act spans - the oracle the export must serve
    (tools/v2/score_v2.py's any-overlap; AMENDMENT-2 section 6 part 2 as D292 widens it, the class the hold-cause
    judge built as score_v2_s6.by_restatement, restated): 'anchor' when the code's acts' anchors overlap an expected
    span; 'restatement' when an expected span X overlaps no event's anchor, at least one event lists a restatement
    overlapping X, and EVERY event that lists one is one of the code's acts; 'wrong_ready' otherwise. An @1 export has no
    events, so the second rule never applies to it."""
    found = next(item for item in export['codes'] if item['code'] == code)
    if found['status'] != 'ready':
        raise AssertionError(f'{code} is {found["status"]}, not ready')
    if any(overlaps(span, x) for act in found['acts'] for span in act['anchor'] for x in expected):
        return 'anchor'
    table, acts = export.get('events', []), {act['event'] for act in found['acts']}
    for x in expected:
        if any(overlaps(span, x) for event in table for span in event['anchor']):
            continue
        listing = {event['event'] for event in table if any(overlaps(span, x) for span in event['restatements'])}
        if listing and listing <= acts:
            return 'restatement'
    return 'wrong_ready'


def told_by(export: dict) -> dict:
    """{event: its listed restatement spans}."""
    return {event['event']: event['restatements'] for event in export['events']}


class SchemaTwoTests(SimpleTestCase):
    def test_v2_is_v1_and_events_whatever_the_input(self):
        """On the dummy, the stored colonoscopy and the retold note: every @1 key of the @2 export is what @1 writes for
        the same input, ``events`` comes last, and the default is @1 exactly - so no @1 reader sees a difference."""
        from tests.v2 import test_facts as TF

        _, assessment, R = dummy()
        content = TF.colonoscopy()
        stored = TF.stored(content)
        row = TF.view(content)
        at = TF.unit_span(6)
        proposals = TA.NormalizedResponse('corti', 'synthetic@1', codes=(TA.ProviderCode(
            'selected', 'CPT', '45385', '', (TA.EvidenceSpan(0, at.start, at.end, TF.TEXT[at.start:at.end], True),)),))
        colonoscopy = AS.assess(inventory=row, date_of_service=DAY, text=TF.TEXT, pages=(), integrity=TA.Integrity(),
                                provider_status='succeeded', proposals=proposals, reference=TA.Lookup(),
                                member=TA.ENTERED, label=str)
        inputs = {
            'dummy': (lambda **kw: M.export(assessment, view=retold_view(), report=report(),
                                            case=M.Case('a' * 64, 'b' * 64, 1), label=M.Label.SYNTHETIC,
                                            guard=M.Guard(0, 0), R=R, **runs(), **kw)),
            'stored colonoscopy': (lambda **kw: M.export(colonoscopy, view=row, report=stored.verification,
                                                         case=M.Case('a' * 64, TF.TEXT_SHA256, 2),
                                                         label=M.Label.REPLAY, guard=M.Guard(0, 0), **runs(), **kw)),
            'retold note': (lambda **kw: exported(second=True, restated={'E2': [('summarizes', ['S7'])]},
                                                  schema=kw.get('schema'))),
        }
        for name, build in inputs.items():
            with self.subTest(input=name):
                one, two, default = build(schema=M.Schema.V1), build(schema=M.Schema.V2), build()
                self.assertEqual(default, one)
                self.assertNotIn('events', one)
                self.assertEqual((one['schema'], two['schema']), ('cpt-studio-measure@1', 'cpt-studio-measure@2'))
                self.assertEqual(without(two, 'schema', 'events'), without(one, 'schema'))
                self.assertEqual(list(two), [*one, 'events'])
                self.assertEqual(mismatches(design_shape(), one), [])
                self.assertEqual(mismatches(design_shape_2(), two), [])
                self.assertTrue(two['events'])

    def test_the_v2_export_matches_9_1_and_amendment_2s_events_key_for_key(self):
        """@2's shape is 9.1's block with AMENDMENT-2's own event entry (parsed from AMENDMENT-2.md): every key, every
        list's element shape and every value's type, populated - and a key added to, dropped from or retyped in an event
        turns it red."""
        self.assertEqual(events_shape(), {'event': '', 'anchor': 'SPANS', 'restatements': 'SPANS'})
        example = design_shape_2()
        _, assessment, R = dummy()
        data = M.export(assessment, view=retold_view(), report=report(), case=M.Case('a' * 64, 'b' * 64, 1),
                        label=M.Label.SYNTHETIC, guard=M.Guard(0, 0), R=R, schema=M.Schema.V2, **runs())
        self.assertEqual(data['events'], [{'event': 'E2', 'anchor': [[200, 260]], 'restatements': [[300, 360]]}])
        self.assertEqual(mismatches(example, data), [])
        self.assertEqual(populated(example, data), [])
        added, dropped, retyped = (json.loads(json.dumps(data)) for _ in range(3))
        added['events'][0]['role'] = 'summarizes'
        del dropped['events'][0]['restatements']
        retyped['events'][0]['anchor'] = [['200', '260']]
        for name, broken in (('added', added), ('dropped', dropped), ('retyped', retyped)):
            with self.subTest(case=name):
                self.assertTrue(mismatches(example, broken))
        self.assertTrue(mismatches(design_shape(), data))  # @2 is not @1: its events key is reported

    def test_the_schema_is_closed(self):
        _, assessment, R = dummy()
        self.assertEqual([member.value for member in M.Schema], ['cpt-studio-measure@1', 'cpt-studio-measure@2'])
        self.assertEqual(M.SCHEMA, 'cpt-studio-measure@1')
        self.assertEqual(M.TELLING_ROLES, {ct.RestatementRole.RESTATES, ct.RestatementRole.SUMMARIZES})
        with self.assertRaises(TypeError):
            M.export(assessment, view=view(), report=report(), case=M.Case('a' * 64, 'b' * 64, 1),
                     label=M.Label.SYNTHETIC, guard=M.Guard(0, 0), R=R, schema='cpt-studio-measure@2', **runs())


class RetoldTests(SimpleTestCase):
    def test_a_ready_anchored_on_a_retelling_line_counts_as_that_act(self):
        """The snare E2 is told at S5 and retold by the impression S7 (summarizes; G6 counted it). 45385 is READY on E2,
        anchored on S5. An expected act span on the impression's words overlaps no event's anchor, and only E2, the
        code's act, retells it: through @2 the READY counts as that act; through @1, which has no events, the same row
        is a wrong READY of the act kind, as before."""
        restated = {'E2': [('summarizes', ['S7'])]}
        two, one = exported(restated=restated), exported(restated=restated, schema=M.Schema.V1)
        code = next(item for item in two['codes'] if item['code'] == '45385')
        self.assertEqual((code['status'], code['acts']),
                         ('ready', [{'event': 'E2', 'kind': 'snare', 'session': 'X1', 'anchor': [line(5)]}]))
        self.assertEqual(two['events'], [{'event': 'E1', 'anchor': [line(4)], 'restatements': []},
                                         {'event': 'E2', 'anchor': [line(5)], 'restatements': [line(7)]}])
        impression = [line(7)[0] + len('Impression: '), line(7)[1]]  # the expectation quotes the impression's words
        self.assertEqual(counted_as(two, '45385', [impression]), 'restatement')
        self.assertEqual(counted_as(one, '45385', [impression]), 'wrong_ready')
        self.assertEqual(counted_as(two, '45385', [line(5)]), 'anchor')  # on its own statement, as before
        self.assertEqual(without(two, 'schema', 'events'), without(one, 'schema'))
        # the restates role retells too (M6), and the act stays READY
        self.assertEqual(counted_as(exported(restated={'E2': [('restates', ['S7'])]}), '45385', [impression]),
                         'restatement')

    def test_a_line_every_act_of_the_code_retells_counts_and_any_other_lister_refuses(self):
        """45385 READY on two snares E2 and E3 (both its acts). S8 retold by both counts (a faithful summary of every act,
        the judge's widening); retold also by the examination E1, which is no act of 45385, it refuses (a line two events
        claim never forgives); S7 retold only by E1 refuses (a line only another event retells)."""
        snares = {'E2': [('summarizes', ['S7']), ('summarizes', ['S8'])], 'E3': [('summarizes', ['S8'])]}
        data = exported(second=True, restated=snares)
        code = next(item for item in data['codes'] if item['code'] == '45385')
        self.assertEqual((code['status'], [act['event'] for act in code['acts']]), ('ready', ['E2', 'E3']))
        self.assertEqual(told_by(data), {'E1': [], 'E2': [line(7), line(8)], 'E3': [line(8)]})
        self.assertEqual(counted_as(data, '45385', [line(8)]), 'restatement')
        self.assertEqual(counted_as(data, '45385', [line(7)]), 'restatement')
        session = exported(second=True, restated={**snares, 'E1': [('summarizes', ['S8'])]})
        self.assertEqual(told_by(session)['E1'], [line(8)])
        self.assertEqual(counted_as(session, '45385', [line(8)]), 'wrong_ready')
        self.assertEqual(counted_as(session, '45385', [line(7)]), 'restatement')
        other = exported(second=True, restated={'E1': [('summarizes', ['S7'])]})
        self.assertEqual(counted_as(other, '45385', [line(7)]), 'wrong_ready')

    def test_as_ruled_only_a_listed_restatement_makes_its_event_a_lister(self):
        """As D292 rules the class (its judge's table; step f9's NOTES, QUESTION Q1): the every-lister condition counts
        the events that list a restatement @2 lists, so a line the examination E1 only names (names_only), or retells
        with its role claim's geometry check failed, does not refuse the READY whose act E2 retells it; the same line
        retold by E1 as @2 lists it does refuse."""
        for given in ([('names_only', ['S7'])], [('restates', ['S7'], 'ok', 'failed')]):
            with self.subTest(e1=given):
                data = exported(restated={'E1': given, 'E2': [('summarizes', ['S7'])]})
                self.assertEqual(told_by(data), {'E1': [], 'E2': [line(7)]})
                self.assertEqual(counted_as(data, '45385', [line(7)]), 'restatement')
        data = exported(restated={'E1': [('summarizes', ['S7'])], 'E2': [('summarizes', ['S7'])]})
        self.assertEqual(told_by(data), {'E1': [line(7)], 'E2': [line(7)]})
        self.assertEqual(counted_as(data, '45385', [line(7)]), 'wrong_ready')

    def test_only_a_line_that_retells_the_act_is_listed(self):
        """restates and summarizes retell the act and are listed; a title, a names_only and a refers_back line do not
        (FINAL-V2 4.7: a title is never a statement), so a READY whose expected span lies only on one is a wrong READY."""
        for value, listed in (('restates', True), ('summarizes', True), ('title', False), ('names_only', False),
                              ('refers_back', False)):
            with self.subTest(role=value):
                data = exported(restated={'E2': [(value, ['S7'])]})
                self.assertEqual(told_by(data)['E2'], [line(7)] if listed else [])
                self.assertEqual(counted_as(data, '45385', [line(7)]), 'restatement' if listed else 'wrong_ready')
        title = exported(restated={'E2': [('title', ['S1'])]})  # the document's title line, which G6 counts
        self.assertEqual(told_by(title)['E2'], [])
        self.assertEqual(counted_as(title, '45385', [line(1)]), 'wrong_ready')

    def test_g6_and_the_role_geometry_decide_what_is_listed(self):
        """A telling restatement is listed only when G6 counted it (its role's source geometry), its role claim passed
        its geometry check, none of its units is any event's anchor unit and the row has every unit it cites - the last
        two re-read from the row, whatever the row says of its geometry."""
        cases = (
            ('G6 ignored it: its role source geometry failed', [('summarizes', ['S7'], 'failed', 'failed')], []),
            ('its role claim failed its geometry check', [('summarizes', ['S7'], 'ok', 'failed')], []),
            ("another event's anchor unit, the row's geometry ok", [('summarizes', ['S4'])], []),
            ('one of its units is its own anchor unit', [('summarizes', ['S5', 'S6'])], []),
            ('a unit the row does not have, the row\'s geometry ok', [('summarizes', ['S7', 'S99'])], []),
            ('no unit at all', [('summarizes', [])], []),
            ('a counted one beside an ignored one', [('summarizes', ['S8'], 'failed', 'failed'),
                                                     ('summarizes', ['S7'])], [line(7)]),
            ('one line retold twice: listed once', [('summarizes', ['S7']), ('restates', ['S7'])], [line(7)]),
            ('two lines: each in its first place', [('summarizes', ['S8']), ('summarizes', ['S7'])],
             [line(8), line(7)]),
        )
        for name, given, listed in cases:
            with self.subTest(case=name):
                stored, found = retold(restated={'E2': given})
                self.assertEqual({event['event']: event['restatements'] for event in M.events(found)},
                                 {'E1': [], 'E2': listed})
        anchored = exported(restated={'E2': [('summarizes', ['S4'])]})
        self.assertEqual(counted_as(anchored, '45385', [line(4)]), 'wrong_ready')  # S4 is E1's anchor
        failed = exported(restated={'E2': [('summarizes', ['S7'], 'ok', 'failed')]})
        self.assertEqual(counted_as(failed, '45385', [line(7)]), 'wrong_ready')

    def test_anchors_cover_every_event_act_or_statement_valid_or_not(self):
        """Every event of the row is listed with its anchor, a denial and a doubted act among them, equal to the anchor
        the engine reads (so the codes' acts anchors are these); an anchor that is not a valid run is still listed (it
        names where pass 1 placed an event), each unit the row has once, in order."""
        from tests.v2 import test_facts as TF

        content = TF.colonoscopy()
        row = TF.view(content)
        table = M.events(row)
        R = F.effective(row, DAY)
        self.assertEqual([event['event'] for event in table], ['E1', 'E2', 'E3', 'E4', 'E5'])
        self.assertEqual({event['event']: event['anchor'] for event in table},
                         {str(event): [[span.start, span.end] for span in anchor.units]
                          for event, anchor in R.anchors.items()})
        self.assertEqual([event['restatements'] for event in table], [[], [], [], [], []])
        found = view()
        found['events'].append({**copy.deepcopy(found['events'][0]), 'id': 'E3',
                                'anchor': {'units': ['S3', 'S99', 'S3', 'S4'], 'kind_words': None,
                                           'status_words': None}})
        self.assertEqual(M.events(found), [{'event': 'E2', 'anchor': [[200, 260]], 'restatements': []},
                                           {'event': 'E3', 'anchor': [[300, 360], [400, 460]], 'restatements': []}])
        # an event's anchor units are G6's, valid or not: E2's restatement on S4 is never listed
        found['events'][0]['restatements'] = [{'units': ['S4'], 'role': role('summarizes', ['S4'], located='at')}]
        self.assertEqual(M.events(found)[0]['restatements'], [])

    def test_a_record_no_row_holds_is_refused_never_dropped(self):
        """A restatement or event record the view cannot hold is refused (ValueError) by @2, never left out: a dropped
        lister would loosen the scorer's every-lister condition. @1 reads none of it and still exports."""
        _, assessment, R = dummy()

        def changed(change) -> dict:
            found = retold_view()
            change(found['events'][0])
            return found

        cases = {
            'no role': lambda event: event['restatements'][0].pop('role'),
            'a role that is no RestatementRole': lambda event: event['restatements'][0]['role']['claim'].update(
                value='impression'),
            'a role with no value': lambda event: event['restatements'][0]['role']['claim'].update(value=None),
            'a source geometry that is no CheckStatus': lambda event: event['restatements'][0]['role']['sources'][
                0].update(geometry='maybe'),
            'checks with no geometry': lambda event: event['restatements'][0]['role']['checks'].pop('geometry'),
            'sources that are no list': lambda event: event['restatements'][0]['role'].update(sources='S3'),
            'a unit cited by no id': lambda event: event['restatements'][0].update(units=[3]),
            'an anchor unit cited by no id': lambda event: event['anchor'].update(units=[2]),
            'an event with no id': lambda event: event.pop('id'),
            'restatements that are no list': lambda event: event.update(restatements=None),
        }
        for name, change in cases.items():
            with self.subTest(case=name):
                found = changed(change)
                with self.assertRaises(ValueError):
                    M.events(found)
                with self.assertRaises(ValueError):
                    M.export(assessment, view=found, report=report(), case=M.Case('a' * 64, 'b' * 64, 1),
                             label=M.Label.SYNTHETIC, guard=M.Guard(0, 0), R=R, schema=M.Schema.V2, **runs())
        for name in ('a role that is no RestatementRole', 'a source geometry that is no CheckStatus'):
            with self.subTest(at_1=name):
                one = M.export(assessment, view=changed(cases[name]), report=report(),
                               case=M.Case('a' * 64, 'b' * 64, 1), label=M.Label.SYNTHETIC, guard=M.Guard(0, 0), R=R,
                               **runs())
                self.assertEqual(mismatches(design_shape(), one), [])

    def test_the_v2_export_is_json_deterministic_and_text_free(self):
        restated = {'E1': [('summarizes', ['S8'])], 'E2': [('summarizes', ['S7']), ('summarizes', ['S8'])],
                    'E3': [('restates', ['S8']), ('title', ['S1'])]}
        first, second = (exported(second=True, restated=restated) for _ in range(2))
        self.assertEqual(json.dumps(first, sort_keys=True), json.dumps(second, sort_keys=True))
        self.assertEqual(json.loads(json.dumps(first)), first)
        keys, strings, stack = set(), set(), [first]
        while stack:
            item = stack.pop()
            if isinstance(item, dict):
                keys |= set(item)
                stack += list(item.values())
            elif isinstance(item, list):
                stack += item
            elif isinstance(item, str):
                strings.add(item)
        self.assertFalse({'text', 'words', 'quote', 'role'} & keys)
        self.assertFalse({value for value in strings if len(value) >= 12 and value in RETOLD_TEXT})
