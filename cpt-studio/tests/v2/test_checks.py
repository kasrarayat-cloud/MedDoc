"""contract/checks.py: the check orchestration (docs/gemini-migration/FINAL-V2.md 3.1; DECISIONS D206; step 3a of 8.1).
TEXT-ONLY and SYNTHETIC: the notes are test_settle's (written for these tests, fictional clinicians, checked against
DEV-EXCLUSION there); every pass-1 answer is constructed by hand; nothing is sent anywhere.

What is proved:
- check(text, pages, read) returns one Checked carrying every field D206 names, each from its producer: the units and
  closures (segment), every source's location (I1-I3), every anchor, the section places (G2, closers included), the G4
  edges, the restatements G6 counts (CheckedTests);
- each finding on the fact 3.1 names: I1-I3, G1 per link type (positive and negative), G2 on a section's owner, occasion
  and performer, G3, G4 on an act's inherited keys (a statement's date relation only), G5 through geometry.Event and
  extent_units - an act's anchor infers a reach, a denial's does not (the integration's O2; DECISIONS D198), G6, K1-K8,
  L1 (its literals and D193's per-event key), Q1, the anchor rule (anchor_invalid on every fact of the event), and
  D200's object-less doubts (FindingTests);
- the Vocabulary is the ruled tables: family_admits reads FAMILY_KINDS.get(family, frozenset()) (O9, O14), FAMILY_REACH
  is K3's reach (D192) (VocabularyTests);
- the claim set and the settled inventory rest on one implementation: Checked's closures, G4 edges and anchor words are
  what appraise_prompt.basis computes for claims (OneImplementationTests);
- check is pure and refuses an answer read against another segmentation; the module keeps NoWordLists and imports no
  regular-expression or v1 module (ModuleTests).
"""
from __future__ import annotations

import ast
import copy
import dataclasses
import json
from pathlib import Path
from unittest import mock

from django.test import SimpleTestCase

from studio.interpretation.contract import appraise_prompt, checks, extract_read, geometry, segment
from studio.interpretation.contract import extract_schema as xs
from studio.interpretation.contract.extract_read import FactKey
from studio.interpretation.contract.types import (AnchorCitation, Attribute, Checked, Citation, Kind, Landmark,
                                                  Precision, Reason, SectionPlace, SessionKind, Source, Span)
from studio.interpretation.engine import requirements_table
from tests.v2.test_settle import (NOTE, PROBE_B, colonoscopy, doubt, event, event_of, fact, frame, labelled,
                                  note_answer, opening, section, section_of, session, src)
from tests.v2.test_types import measure_4

APP = Path(__file__).resolve().parents[2]
MODULE = APP / 'studio' / 'interpretation' / 'contract' / 'checks.py'
A, F, R = Attribute, xs.Family, Reason


def read(text, data):
    found = extract_read.read(json.dumps(data), len(segment.units(text)))
    assert not isinstance(found, extract_read.Refusal), found
    return found


def checked(data, text=NOTE):
    return checks.check(text, (), read(text, data))


def key(family, name, attribute, index=0):
    return FactKey(family, name, attribute, index)


def findings(found, family, name, attribute, index=0):
    return found.findings.get(key(family, name, attribute, index), ())


class CheckedTests(SimpleTestCase):
    def setUp(self):
        self.data = note_answer()
        self.found = checked(self.data)

    def test_the_units_and_closures_are_the_segmentations(self):
        units = segment.units(NOTE)
        self.assertEqual(self.found.units, units)
        self.assertEqual(len(units), 13)
        layout = geometry.Layout(NOTE, units)
        self.assertEqual(self.found.closures[('S7',)], layout.closure(('S7',)))
        self.assertEqual(self.found.closures[('S9',)], ('S9',))
        self.assertNotIn(('S99',), self.found.closures)
        for run in (('S6',), ('S12',), ('S13',), ('S3',)):
            self.assertIn(run, self.found.closures)

    def test_every_source_of_the_answer_is_located(self):
        layout = geometry.Layout(NOTE, segment.units(NOTE))
        sources = []
        for item in read(NOTE, self.data).facts:
            sources += [*item.fact.sources, *(source for option in item.fact.options for source in option.sources)]
        sources += [Source(('S3',), 'Corvin Ashdale', geometry.Link.STATEMENT),
                    Source(('S5',), 'History:', geometry.Link.SECTION),
                    Source(('S7',), 'A 6 mm sessile polyp', geometry.Link.STATEMENT)]
        for source in sources:
            with self.subTest(source=source):
                located = geometry.locate(layout, source)
                self.assertEqual(self.found.citations[source],
                                 Citation(located.units, located.span, located.words, located.place, located.reasons))
        polyp = self.found.citations[Source(('S7',), 'sigmoid colon', geometry.Link.STATEMENT)]
        self.assertEqual(NOTE[polyp.words.start:polyp.words.end], 'sigmoid colon')
        self.assertEqual(polyp.words.text, 'sigmoid colon')  # the revision's own slice (P9)

    def test_every_anchor_is_located(self):
        self.assertEqual(set(self.found.anchors), {'E1', 'E2', 'E3', 'E4', 'E5', 'E6', 'E7'})
        e2 = self.found.anchors['E2']
        self.assertIsInstance(e2, AnchorCitation)
        self.assertEqual((e2.kind_words.text, e2.status_words.text, e2.reasons), ('cold snare', 'was removed', ()))

    def test_the_section_places_are_geometrys_field_for_field(self):
        layout = geometry.Layout(NOTE, segment.units(NOTE))
        raw = self.data['sections']
        given = geometry.Sections(layout, [geometry.Section(item['id'], checks._source(item['start']),
                                                            tuple(checks._source(end) for end in item['end']))
                                           for item in raw])
        self.assertEqual([dataclasses.astuple(place) for place in self.found.sections],
                         [dataclasses.astuple(place) for place in given.places])
        self.assertTrue(all(isinstance(place, SectionPlace) for place in self.found.sections))
        self.assertEqual(self.found.sections[0].opening, Span(0, 0))  # D199: an empty N0

    def test_the_g4_edges_and_the_restatements_g6_counts(self):
        self.assertEqual(dict(self.found.containing), {'E1': 'N2', 'E2': 'N2', 'E3': 'N2', 'E4': 'N2', 'E5': 'N2',
                                                       'E6': 'N3', 'E7': 'N3'})
        self.assertEqual(dict(self.found.restatements), {('E2', 0): 'N4'})
        self.assertEqual(self.found.document_date.isoformat(), '2031-03-14')

    def test_a_clean_answer_has_no_finding_but_on_facts_settle_and_claims_leave_alone(self):
        """NOTE's answer is filed cleanly: no S2, I or G finding, no K or L finding, no qualifier."""
        self.assertEqual(dict(self.found.findings), {})
        self.assertEqual(dict(self.found.failed_links), {})
        self.assertEqual(self.found.joined, ())
        self.assertEqual(dict(self.found.objectless_doubts), {})

    def test_the_record_is_frozen_and_pure(self):
        again = checked(note_answer())
        for field in dataclasses.fields(Checked):
            with self.subTest(field=field.name):
                first, second = getattr(self.found, field.name), getattr(again, field.name)
                self.assertEqual(dict(first) if hasattr(first, 'items') else first,
                                 dict(second) if hasattr(second, 'items') else second)
        with self.assertRaises(TypeError):
            self.found.findings[key(F.EVENT, 'E2', A.KIND)] = (R.SILENT,)


class FindingTests(SimpleTestCase):
    def changed(self, edit, text=NOTE, base=note_answer):
        data = base() if callable(base) else copy.deepcopy(base)
        edit(data)
        return checked(data, text)

    def test_i1_i3_unknown_and_non_consecutive_units_and_long_sources(self):
        found = self.changed(lambda data: event_of(data, 'E2')['kind']['sources'][0]['units'].append('S99'))
        self.assertEqual(findings(found, F.EVENT, 'E2', A.KIND), (R.UNIT_UNKNOWN, R.GEOMETRY_STATEMENT))
        found = self.changed(lambda data: event_of(data, 'E2')['technique']['device'][0]['sources'][0].update(
            units=['S7', 'S9']))
        self.assertIn(R.UNITS_NOT_CONSECUTIVE, findings(found, F.EVENT, 'E2', A.TECHNIQUE_DEVICE))

    def test_i2_words_not_in_units_and_words_not_bounded(self):
        found = self.changed(lambda data: event_of(data, 'E2')['technique']['device'][0]['sources'][0].update(
            words='hot snare'))
        self.assertEqual(findings(found, F.EVENT, 'E2', A.TECHNIQUE_DEVICE), (R.WORDS_NOT_IN_UNITS,))
        found = self.changed(lambda data: event_of(data, 'E2')['technique']['device'][0]['sources'][0].update(
            words='old snar'))
        self.assertEqual(findings(found, F.EVENT, 'E2', A.TECHNIQUE_DEVICE), (R.WORDS_NOT_BOUNDED,))

    def test_g1_every_link_type_holds_and_fails(self):
        cases = {
            # statement: inside the act's anchor closure / in another act's unit
            'statement': (lambda data: None, lambda data: event_of(data, 'E2')['kind']['sources'][0].update(
                units=['S8'], words='clip'), (F.EVENT, 'E2', A.KIND), R.GEOMETRY_STATEMENT),
            # section: the containing section's start / a unit of the section that is not its start
            'section': (lambda data: section_of(data, 'N1')['role'][0]['sources'][0].update(words='History:'),
                        lambda data: section_of(data, 'N1')['role'][0]['sources'][0].update(
                            words='Prior colonoscopy'), (F.SECTION, 'N1', A.ROLE), R.GEOMETRY_SECTION),
            # frame: inside the containing section's span / in another part
            'frame': (lambda data: None, lambda data: section_of(data, 'N1')['occasion'][0]['sources'][0].update(
                units=['S6'], words='Findings'), (F.SECTION, 'N1', A.OCCASION), R.GEOMETRY_FRAME),
            # placing: a sentence that is not the act's own anchor / the anchor itself
            'placing': (lambda data: event_of(data, 'E7').update(date_relation=[fact(
                'on_date_of_service', src(['S2'], '03/14/2031', 'placing'))]),
                        lambda data: event_of(data, 'E7').update(date_relation=[fact(
                            'on_date_of_service', src(['S12'], 'were taken', 'placing'))]),
                        (F.EVENT, 'E7', A.DATE_RELATION), R.GEOMETRY_PLACING),
            # document_frame: a frame unit inside N0 / a unit outside N0
            'document_frame': (lambda data: None, lambda data: section_of(data, 'N2')['occasion'][0].update(
                sources=[frame(['S6'], 'Findings')]), (F.SECTION, 'N2', A.OCCASION), R.GEOMETRY_DOCUMENT_FRAME),
            # antecedent: a unit before the anchor / one after it
            'antecedent': (lambda data: event_of(data, 'E3')['target'].update(lesion=[fact(
                'L1', src(['S7'], 'A 6 mm sessile polyp', 'antecedent'))]),
                           lambda data: event_of(data, 'E3')['target'].update(lesion=[fact(
                               'L1', src(['S9'], 'biopsy', 'antecedent'))]),
                           (F.EVENT, 'E3', A.TARGET_LESION), R.GEOMETRY_ANTECEDENT),
            # other_statement: units that exist / a unit the text does not have (I1, and the link fails)
            'other_statement': (lambda data: event_of(data, 'E2')['target'].update(places=[fact(
                'sigmoid_colon', src(['S13'], 'Polyp removed', 'other_statement'))]),
                                lambda data: event_of(data, 'E2')['target'].update(places=[fact(
                                    'sigmoid_colon', src(['S98'], '', 'other_statement'))]),
                                (F.EVENT, 'E2', A.TARGET_PLACES), R.GEOMETRY_OTHER_STATEMENT),
        }
        for name, (holds, fails, where, reason) in cases.items():
            with self.subTest(link=name):
                found = self.changed(holds)
                self.assertNotIn(reason, findings(found, *where))
                found = self.changed(fails)
                self.assertIn(reason, findings(found, *where))
                self.assertTrue(found.failed_links[key(*where)])

    def test_g2_on_a_sections_owner_occasion_and_performer(self):
        found = self.changed(lambda data: section_of(data, 'N3')['start'].update(words='Lower endoscopy:'))
        for attribute in (A.OWNER, A.OCCASION, A.PERFORMER):
            with self.subTest(attribute=attribute):
                self.assertIn(R.SECTION_START_UNLOCATED, findings(found, F.SECTION, 'N3', attribute))
        self.assertNotIn(R.SECTION_START_UNLOCATED, findings(found, F.SECTION, 'N3', A.ROLE))  # D186: three facts
        self.assertIsNone(found.sections[3].span)

    def test_g3_a_target_away_from_its_anchor_is_detached(self):
        found = self.changed(lambda data: event_of(data, 'E7')['target']['places'][0]['sources'][0].update(
            units=['S11'], words='duodenum'))
        self.assertIn(R.TARGET_DETACHED, findings(found, F.EVENT, 'E7', A.TARGET_PLACES))
        def later(data):  # E2's lesion described in E7's sentence: neither its anchor, a restatement nor before it
            data['lesions'].append({'id': 'L2', 'description': src(['S12'], 'gastric antrum'), 'multiplicity': [],
                                    'places': [], 'distinct_from': [], 'same_as': []})
            event_of(data, 'E2')['target']['lesion'] = [fact('L2', src(['S7'], 'A 6 mm sessile polyp'))]
        self.assertIn(R.TARGET_DETACHED, findings(self.changed(later), F.EVENT, 'E2', A.TARGET_LESION))
        found = self.changed(lambda data: event_of(data, 'E3')['target'].update(lesion=[fact('L1', src(['S8']))]))
        self.assertEqual(findings(found, F.EVENT, 'E3', A.TARGET_LESION), ())  # L1 told before it: an antecedent

    def test_g4_on_the_inherited_keys_of_an_act_and_a_statement(self):
        found = self.changed(lambda data: section_of(data, 'N2')['start'].update(words='Results:'))
        for attribute in (A.DATE_RELATION, A.PERFORMER, A.PERFORMER_PERSON, A.ENTRY):
            with self.subTest(act='E2', attribute=attribute):
                self.assertEqual(findings(found, F.EVENT, 'E2', attribute), (R.INHERIT_UNATTACHED,))
        for attribute, expected in ((A.DATE_RELATION, (R.INHERIT_UNATTACHED,)), (A.ENTRY, (R.INHERIT_UNATTACHED,)),
                                    (A.PERFORMER, ())):
            with self.subTest(statement='E4', attribute=attribute):
                self.assertEqual(findings(found, F.EVENT, 'E4', attribute), expected)
        self.assertEqual(findings(found, F.EVENT, 'E7', A.DATE_RELATION), ())  # N3 still holds E7

    def test_g5_an_acts_anchor_infers_a_reach_a_denials_and_the_examinations_do_not(self):
        """The integration's O2: geometry.Event and extent_units, with D198's 3a half."""
        def reach(units, words, link='other_statement'):
            return lambda data: data['sessions'][0].update(reached=[fact('cecum', src(units, words, link))])
        self.assertEqual(findings(self.changed(reach(['S6'], 'advanced to the cecum', 'statement')), F.SESSION, 'X1',
                                  A.REACHED), ())
        self.assertEqual(findings(self.changed(reach(['S7'], 'sigmoid colon')), F.SESSION, 'X1', A.REACHED),
                         (R.EXTENT_INFERRED,))
        self.assertEqual(findings(self.changed(reach(['S9'], 'Neither biopsy')), F.SESSION, 'X1', A.REACHED), ())
        self.assertEqual(findings(self.changed(reach(['S10'], 'anastomosis')), F.SESSION, 'X1', A.REACHED), ())

    def test_g6_a_restatement_on_an_anchor_unit_is_ignored(self):
        found = self.changed(lambda data: event_of(data, 'E2').update(restatements=[{'units': ['S8'],
                                                                                     'role': 'restates'}]))
        self.assertEqual(dict(found.restatements), {})
        found = self.changed(lambda data: event_of(data, 'E2').update(restatements=[{'units': ['S10'],
                                                                                     'role': 'restates'}]))
        self.assertEqual(dict(found.restatements), {('E2', 0): 'N2'})

    def test_k1_to_k8_l1_and_q1_through_consistency_with_the_real_vocabulary(self):
        cases = {
            'K1': (lambda data: event_of(data, 'E4')['scope']['breadth'][0].update(value='exceptive'),
                   (F.EVENT, 'E4', A.SCOPE_BREADTH), R.STRUCTURE_EXCEPTIVE),
            'K2': (lambda data: event_of(data, 'E7')['kind'].update(value='lithotripsy'),
                   (F.EVENT, 'E7', A.SESSION), R.SESSION_INCONSISTENT),
            'K3': (lambda data: event_of(data, 'E7')['target']['places'][0].update(value='sigmoid_colon'),
                   (F.EVENT, 'E7', A.SESSION), R.SESSION_UNREACHABLE),
            'K4': (lambda data: data['anatomy'][0].update(type=fact('surgically_absent', src(['S10'], 'ileocolic')),
                                                          organ=[fact('cecum', src(['S10'], 'ileocolic'))],
                                                          subtype=[]),
                   (F.SESSION, 'X1', A.REACHED), R.ANATOMY_CONFLICT),
            'K5': (lambda data: event_of(data, 'E2').update(performer=[fact('other_clinician', src(['S7']))],
                                                            performer_person=[fact('P1', src(['S7']))]),
                   (F.EVENT, 'E2', A.PERFORMER), R.PERSON_CONFLICT),
            'K6': (lambda data: data['sessions'][0].update(device_reached=[fact('cecum', src(['S6'], 'cecum'))]),
                   (F.SESSION, 'X1', A.REACHED), R.INSTRUMENT_CONFLICT),
            'K7': (lambda data: section_of(data, 'N1')['occasion'][0].update(
                value='on_date_of_service', sources=[frame(['S2'])]), (F.SECTION, 'N1', A.OCCASION), R.FRAME_ROLE),
            'L1': (lambda data: section_of(data, 'N1')['occasion'][0].update(value='later_date'),
                   (F.SECTION, 'N1', A.OCCASION), R.LITERAL_MISMATCH),
            'Q1': (lambda data: event_of(data, 'E2')['technique']['device'][0]['qualifiers'].append('hedged'),
                   (F.EVENT, 'E2', A.TECHNIQUE_DEVICE), R.QUALIFIED_HEDGED),
        }
        for name, (edit, where, reason) in cases.items():
            with self.subTest(rule=name):
                self.assertIn(reason, findings(self.changed(edit), *where))
        found = self.changed(lambda data: event_of(data, 'E7')['technique']['device'][0]['qualifiers'].append(
            'approximate'))
        self.assertEqual(findings(found, F.EVENT, 'E7', A.TECHNIQUE_DEVICE), ())  # approximate never lowers

    def test_k8_joins_and_l1_stores_its_literals_with_d193s_per_event_key(self):
        found = self.changed(lambda data: data['sessions'][0]['reached'].append(fact(
            'colon', src(['S6'], 'cecum'), state='negated')))
        self.assertEqual(found.joined, (((key(F.SESSION, 'X1', A.REACHED, 0),), (key(F.SESSION, 'X1', A.REACHED, 1),)),))
        self.assertNotIn(key(F.SESSION, 'X1', A.REACHED, 0), found.findings)  # K8 is no finding
        found = self.changed(lambda data: event_of(data, 'E2').update(date=[fact('2027', src(['S5'], '2027'))]))
        self.assertEqual([(item.value, item.precision) for item in found.literals[key(F.EVENT, 'E2',
                                                                                        A.DATE_RELATION)]],
                         [('2031-03-14', Precision.DAY), ('2027', Precision.YEAR)])
        self.assertEqual(findings(found, F.EVENT, 'E2', A.DATE_RELATION), (R.LITERAL_MISMATCH,))
        self.assertEqual([(item.value, item.precision) for item in found.literals[key(F.SECTION, 'N1', A.OCCASION)]],
                         [('2027', Precision.YEAR)])

    def test_the_anchor_rule_marks_every_fact_of_an_event_whose_anchor_fails(self):
        found = self.changed(lambda data: event_of(data, 'E2')['anchor'].update(status_words='was taken'))
        self.assertEqual(found.anchors['E2'].reasons, (R.ANCHOR_WORDS,))
        for attribute, index in ((A.KIND, 0), (A.STATUS, 0), (A.SESSION, 0), (A.TARGET_PLACES, 0),
                                 (A.TECHNIQUE_DEVICE, 0), (A.RESTATEMENTS_ROLE, 0), (A.DATE_RELATION, 0),
                                 (A.PERFORMER, 0), (A.ENTRY, 0)):
            with self.subTest(attribute=attribute):
                self.assertIn(R.ANCHOR_INVALID, findings(found, F.EVENT, 'E2', attribute, index))
        self.assertNotIn(R.ANCHOR_INVALID, findings(found, F.EVENT, 'E3', A.KIND))
        self.assertNotIn(key(F.EVENT, 'E2', A.TARGET_DUCT), found.findings)  # a silent slot is no fact

    def test_d200_an_objectless_doubt_reaches_the_events_anchored_at_its_units(self):
        found = self.changed(lambda data: data['doubts'].extend([doubt('status', ['E99'], ['S9', 'S10']),
                                                                  doubt('status', [], ['S1']),
                                                                  doubt('status', ['E2'], ['S7'])]))
        self.assertEqual(dict(found.objectless_doubts), {0: ('E4', 'E5'), 1: ()})

    def test_the_document_date_is_none_when_its_literal_fails(self):
        found = self.changed(lambda data: data['encounter']['date_of_service'].update(value='2031-03-15'))
        self.assertIsNone(found.document_date)
        self.assertIn(R.LITERAL_MISMATCH, findings(found, F.ENCOUNTER, '', A.DATE_OF_SERVICE))


class VocabularyTests(SimpleTestCase):
    def test_family_admits_reads_the_family_kinds_table_and_a_missing_family_admits_nothing(self):
        """DECISIONS D191; the integration's O9 and O14."""
        self.assertTrue(checks.family_admits(SessionKind.ERCP, Kind.CANNULATION))
        self.assertTrue(checks.family_admits(SessionKind.COLONOSCOPY, Kind.CLIP))
        self.assertFalse(checks.family_admits(SessionKind.COLONOSCOPY, Kind.PEG))
        self.assertFalse(checks.family_admits(SessionKind.NOT_GI, Kind.BIOPSY))  # no row: the empty set
        for family in SessionKind:
            for kind in Kind:
                self.assertEqual(checks.family_admits(family, kind),
                                 kind in requirements_table.FAMILY_KINDS.get(family, frozenset()))
        reduced = {family: kinds for family, kinds in requirements_table.FAMILY_KINDS.items()
                   if family is not SessionKind.EGD}
        with mock.patch.object(requirements_table, 'FAMILY_KINDS', reduced):
            self.assertFalse(checks.family_admits(SessionKind.EGD, Kind.BIOPSY))

    def test_k3_reads_the_real_reach(self):
        from studio.interpretation.engine import anatomy, catalogue
        self.assertIs(checks.VOCABULARY.region, anatomy.region)
        self.assertIs(checks.VOCABULARY.contains, anatomy.contains)
        self.assertIs(checks.VOCABULARY.reach, catalogue.FAMILY_REACH)
        self.assertNotIn(anatomy.region(Landmark.SIGMOID_COLON), checks.VOCABULARY.reach[SessionKind.EGD])


class OneImplementationTests(SimpleTestCase):
    def test_checked_gives_claims_what_appraise_prompt_basis_computes(self):
        """D206: the claim set and the settled inventory rest on one implementation - Checked's closures, G4 edges
        and anchor words are what claims.py is built from (appraise_prompt.basis today)."""
        data = note_answer()
        found_read = read(NOTE, data)
        found = checks.check(NOTE, (), found_read)
        basis = appraise_prompt.basis(NOTE, (), found_read, findings=found.findings)
        self.assertEqual(dict(basis.closures), dict(found.closures))
        self.assertEqual(dict(basis.sections), dict(found.containing))
        self.assertEqual(basis.units, found.units)
        self.assertEqual({name: (None if anchor.kind_words is None else Span(anchor.kind_words.start,
                                                                              anchor.kind_words.end),
                                 None if anchor.status_words is None else Span(anchor.status_words.start,
                                                                                anchor.status_words.end))
                          for name, anchor in found.anchors.items()}, dict(basis.anchor_words))
        self.assertEqual({item: section_ for item, section_ in found.restatements.items() if section_ is not None},
                         dict(basis.restatement_sections))
        self.assertEqual(dict(basis.findings), dict(found.findings))


class ModuleTests(SimpleTestCase):
    source = MODULE.read_text(encoding='utf-8')

    def test_an_answer_read_against_another_segmentation_is_refused(self):
        found = extract_read.read(json.dumps(colonoscopy(PROBE_B, findings_unit='S5')), 9)
        self.assertNotIsInstance(found, extract_read.Refusal)
        with self.assertRaises(ValueError):
            checks.check(PROBE_B, (), found)

    def test_no_word_lists_and_no_regular_expression_or_v1_module(self):
        self.assertEqual(measure_4(self.source, engine=False), [])
        self.assertTrue(measure_4(self.source + "\nNEGATORS = ('no', 'neither')\n", engine=False))  # the control
        imported = set()
        for node in ast.walk(ast.parse(self.source)):
            if isinstance(node, ast.Import):
                imported |= {alias.name for alias in node.names}
            elif isinstance(node, ast.ImportFrom):
                imported |= {f'{node.module}.{alias.name}' for alias in node.names} | {node.module or ''}
        for name in imported:
            parts = name.split('.')
            self.assertNotIn(parts[0], ('re', 'regex', 'unicodedata', 'difflib', 'fnmatch'))
            if parts[:2] == ['studio', 'interpretation'] and len(parts) > 2:
                self.assertIn(parts[2], ('contract', 'engine'), name)
