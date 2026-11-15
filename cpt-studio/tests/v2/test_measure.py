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
Every document and fact here is written for this test: no real patient, no development or acceptance document.
"""
from __future__ import annotations

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
        self.assertEqual(data['versions'], {'interpretation': 'gemini-events@2/appraisal@1',
                                            'inventory': 'gemini-inventory@2', 'requirements': 'cpt-requirements@1',
                                            'engine': 'cpt-studio-events@2'})
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
