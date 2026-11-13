"""Design v2's shared labels and types (docs/gemini-migration/FINAL-V2.md, step 0b of 8.1), TEXT-ONLY and SYNTHETIC.

What is proved here, each against the design or against v1 computed in the test:
- the labels: v1's names and values byte-identical (the 17 retired modules read them for good, 5.0); v2's labels of 1.1
  under new names; every pin of 2.5 named, each naming the step that fills it, and written as a sha256 but the health
  thresholds' (DECISIONS D202); the family dispatch of is_new_assessment and is_new_context for @1 and @2 alike;
- the settings: D49's deadlines for the second call (7.4 [R:MO-3]), as literal assignments beside the interpreter's;
- the enumerations: each a plain, unique, closed Enum whose values are the design's strings in its order, the ones the
  design derives from v1 equal to v1's tuples by value;
- the records: frozen dataclasses with slots holding exactly the fields the design names, each of the type it names
  (typing.get_type_hints); the engine's text-free boundary, typed (no field holds a str but HeldFact's two code fields);
- the check records of DECISIONS D206 (the waves 1-2 triage's INT-4): Citation, AnchorCitation and SectionPlace are
  contract/geometry.py's records field for field, closers included (the integration's O3), and convert from geometry's
  output with nothing lost; Checked freezes what it is given, is generic in the answer's fact key (mypy --strict refuses
  another key), holds only this module's and the standard library's types, and carries every finding the checks give
  (the reader's, geometry's, consistency's) and every input claims.py's Basis reads besides pass 1's answer;
- the docstrings the integration's O4 and t0's note 7 named: engine/facts.iso_value names store's _v2_date_precision,
  engine/types.py says facts.py builds from store.textfree_v2's view (D188), and no docstring line of either types
  module stops short inside its paragraph;
- the done-when of 8.1 step 0b: the types import with no v1 module (a fresh interpreter), and mypy --strict passes on
  both types.py (run here, with a positive control: a string operation on a fact value is refused);
- the new modules already keep 5.7 measure 4 (the guard proper is step 6a's), each rule with a planted control;
- contract/jsonschema.py equals v1's schema.py on v1's own schemas: outputs, refusals, bytes, hashes and code.
"""
from __future__ import annotations

import ast
import copy
import dataclasses
import datetime
import enum
import hashlib
import inspect
import os
import re
import subprocess
import sys
import types
import typing
from collections.abc import Hashable, Mapping
from pathlib import Path

import hypothesis
from django.conf import settings
from django.test import SimpleTestCase
from hypothesis import strategies as st

from studio import interpretation
from studio.interpretation import prompt, schema  # v1, read only for the parity proofs (computed here)
from studio.interpretation import store
from studio.interpretation.contract import claims, consistency, extract_read, extract_schema, geometry, jsonschema
from studio.interpretation.contract import types as ct
from studio.interpretation.engine import facts
from studio.interpretation.engine import types as et
from studio.models import Assessment, EncounterContext, EventInventory, Job, ProviderRun, RoutingRun

APP = Path(__file__).resolve().parents[2]
PACKAGE = APP / 'studio' / 'interpretation'
DEV_EXCLUSION = APP / 'docs' / 'gemini-migration' / 'acceptance-a1' / 'DEV-EXCLUSION.sha256'  # hashes only
NEW_MODULES = {
    'contract/__init__': PACKAGE / 'contract' / '__init__.py',
    'contract/types': PACKAGE / 'contract' / 'types.py',
    'contract/jsonschema': PACKAGE / 'contract' / 'jsonschema.py',
    'engine/__init__': PACKAGE / 'engine' / '__init__.py',
    'engine/types': PACKAGE / 'engine' / 'types.py',
}

# --- the labels -------------------------------------------------------------------------------------------------------

# v1's label lines, verbatim: each must stand in __init__.py exactly once, byte for byte (FINAL-V2 5.0).
V1_LINES = (
    "INTERPRETATION_VERSION = 'gemini-events@1'",
    "INSTRUCTIONS_SHA256 = '00da58c5a8f0f5deca4ee0dd8259bb7065ee6dd551e408e3257bd33b4eee14b1'",
    "LOCAL_SCHEMA_SHA256 = '93574cacb4dc3d9fb0c3ed7789a8c2f7c708bf94176b53f1dd850fcd0214ccc3'",
    "RESPONSE_SCHEMA_SHA256 = '7bb3057d724012910b4210272c31480eacb6fc6fe6dbacbce4415c61592d2537'",
    "INVENTORY_VERSION = 'gemini-inventory@1'",
    "LABEL = f\"{INTERPRETATION_VERSION}+{INVENTORY_VERSION.removeprefix('gemini-')}\"  # gemini-events@1+inventory@1",
    "ADAPTER_VERSION = 'gemini-generate@cptstudio-1'  # ProviderRun.adapter_version (at most 40 characters)",
    "MODEL = 'gemini-4-argon'  # D13: named by the URL; a response's modelVersion must equal it exactly",
    "PROVIDER = 'gemini'  # ProviderRun.provider; an operator field, never shown to a customer (D22)",
    "PURPOSE = 'interpretation'  # ProviderRun.purpose (at most 16 characters)",
    "JOB_KIND = 'interpret'  # Job.kind (at most 10 characters)",
    "ENGINE_VERSION = 'cpt-studio-events@1'  # Assessment.engine_version of a new-path assessment",
    "CONTEXT_VERSION = 'gemini-context@1'  # EncounterContext.version derived from an inventory (D6)",
    "ROUTING_VERSION = 'gemini-routing@1'  # RoutingRun.version of the derived stand-in (D6)",
)
V1_VALUES = {
    'INTERPRETATION_VERSION': 'gemini-events@1',
    'INSTRUCTIONS_SHA256': '00da58c5a8f0f5deca4ee0dd8259bb7065ee6dd551e408e3257bd33b4eee14b1',
    'LOCAL_SCHEMA_SHA256': '93574cacb4dc3d9fb0c3ed7789a8c2f7c708bf94176b53f1dd850fcd0214ccc3',
    'RESPONSE_SCHEMA_SHA256': '7bb3057d724012910b4210272c31480eacb6fc6fe6dbacbce4415c61592d2537',
    'INVENTORY_VERSION': 'gemini-inventory@1', 'LABEL': 'gemini-events@1+inventory@1',
    'ADAPTER_VERSION': 'gemini-generate@cptstudio-1', 'MODEL': 'gemini-4-argon', 'PROVIDER': 'gemini',
    'PURPOSE': 'interpretation', 'JOB_KIND': 'interpret', 'ENGINE_VERSION': 'cpt-studio-events@1',
    'CONTEXT_VERSION': 'gemini-context@1', 'ROUTING_VERSION': 'gemini-routing@1',
}
# FINAL-V2 1.1, and 8.1 step 0b's names for them
V2_VALUES = {
    'INTERPRETATION_VERSION_V2': 'gemini-events@2', 'APPRAISAL_VERSION': 'gemini-appraisal@1',
    'INVENTORY_VERSION_V2': 'gemini-inventory@2', 'REQUIREMENTS_VERSION': 'cpt-requirements@1',
    'ENGINE_VERSION_V2': 'cpt-studio-events@2', 'CONTEXT_VERSION_V2': 'gemini-context@2',
    'ROUTING_VERSION_V2': 'gemini-routing@2', 'ADAPTER_VERSION_V2': 'gemini-generate@cptstudio-2',
    'INTERPRETATION_PAIR': 'gemini-events@2/appraisal@1', 'APPRAISAL_PURPOSE': 'appraisal',
    'APPRAISE_JOB_KIND': 'appraise',
}
# FINAL-V2 2.5, item by item, and the name that holds each pin
PINS_2_5 = {
    'pass 1 instruction': 'INSTRUCTIONS_SHA256_V2',
    'pass 2 instruction': 'APPRAISAL_INSTRUCTIONS_SHA256',
    'pass 1 LOCAL schema': 'LOCAL_SCHEMA_SHA256_V2',
    'pass 2 LOCAL schema': 'APPRAISAL_LOCAL_SCHEMA_SHA256',
    'pass 1 RESPONSE schema': 'RESPONSE_SCHEMA_SHA256_V2',
    'pass 2 RESPONSE schema': 'APPRAISAL_RESPONSE_SCHEMA_SHA256',
    "the segmentation rule's constants": 'SEGMENTATION_SHA256',
    'claims.TEMPLATES': 'TEMPLATES_SHA256',
    'claims.STATEMENT_TEMPLATES': 'STATEMENT_TEMPLATES_SHA256',
    'the claims.CONTROLS generator with its tables': 'CONTROLS_SHA256',
    'the CLAIMED table': 'CLAIMED_SHA256',
    'the health thresholds': 'HEALTH_THRESHOLDS_SHA256',
    'the per-request claim bound': 'CLAIM_BOUND_SHA256',
}
# DECISIONS D202 (arbiter triage INT-5): the integration owner wrote every pin but this one in one commit after build
# waves 1 and 2, each value computed by its step's own function and checked by that step's pin test (test_segment,
# test_extract_prompt, test_extract_read, test_requirements, test_claims, test_appraise_prompt, test_appraise_read);
# step 8 sets the health thresholds from D3
UNWRITTEN_PINS = frozenset({'HEALTH_THRESHOLDS_SHA256'})


def _init_source() -> str:
    return (PACKAGE / '__init__.py').read_text(encoding='utf-8')


def _pin_comment(source: str, name: str) -> str:
    """The comment that goes with a pin: its own trailing comment, else the comment lines right above it."""
    lines = source.split('\n')
    at = next(i for i, line in enumerate(lines) if line.startswith(f'{name} = '))
    _, _, trailing = lines[at].partition('#')
    if trailing.strip():
        return trailing
    above = []
    for line in reversed(lines[:at]):
        if not line.startswith('#'):
            break
        above.append(line)
    return ' '.join(reversed(above))


class LabelTests(SimpleTestCase):
    def test_v1_labels_are_byte_identical(self):
        source_lines = _init_source().split('\n')
        for line in V1_LINES:
            with self.subTest(line=line[:40]):
                self.assertEqual(source_lines.count(line), 1)
        self.assertEqual({name: getattr(interpretation, name) for name in V1_VALUES}, V1_VALUES)

    def test_v2_labels_are_the_designs(self):
        self.assertEqual({name: getattr(interpretation, name) for name in V2_VALUES}, V2_VALUES)
        # the pair is built from its two parts, as v1's LABEL is
        self.assertEqual(interpretation.INTERPRETATION_PAIR,
                         f"{interpretation.INTERPRETATION_VERSION_V2}/"
                         f"{interpretation.APPRAISAL_VERSION.removeprefix('gemini-')}")
        # v2 adds labels and changes none: pass 1 keeps v1's purpose, job kind, model and provider (1.1, 7.4)
        self.assertEqual((interpretation.PURPOSE, interpretation.JOB_KIND, interpretation.MODEL),
                         ('interpretation', 'interpret', 'gemini-4-argon'))

    def test_each_v2_label_fits_its_column(self):
        columns = (
            (interpretation.INTERPRETATION_PAIR, EventInventory, 'interpretation_version'),
            (interpretation.INVENTORY_VERSION_V2, EventInventory, 'inventory_version'),
            (interpretation.ENGINE_VERSION_V2, Assessment, 'engine_version'),
            (interpretation.CONTEXT_VERSION_V2, EncounterContext, 'version'),
            (interpretation.ROUTING_VERSION_V2, RoutingRun, 'version'),
            (interpretation.ADAPTER_VERSION_V2, ProviderRun, 'adapter_version'),
            (interpretation.APPRAISAL_PURPOSE, ProviderRun, 'purpose'),
            (interpretation.APPRAISE_JOB_KIND, Job, 'kind'),
        )
        for value, model, name in columns:
            with self.subTest(column=f'{model.__name__}.{name}'):
                self.assertLessEqual(len(value), model._meta.get_field(name).max_length)
        # the counts the design states (1.1: 27 of 40; 6.3: 9 of 16 and 8 of 10)
        self.assertEqual((len(interpretation.INTERPRETATION_PAIR), len(interpretation.ADAPTER_VERSION_V2),
                          len(interpretation.APPRAISAL_PURPOSE), len(interpretation.APPRAISE_JOB_KIND)),
                         (27, 27, 9, 8))

    def test_every_pin_of_2_5_is_written_or_waits_for_step_8_and_names_its_step(self):
        source = _init_source()
        pins = {name for name in vars(interpretation) if 'SHA256' in name}
        self.assertEqual(pins, set(PINS_2_5.values()) | {'INSTRUCTIONS_SHA256', 'LOCAL_SCHEMA_SHA256',
                                                         'RESPONSE_SCHEMA_SHA256'})
        self.assertEqual(len(PINS_2_5), 13)
        self.assertLess(UNWRITTEN_PINS, set(PINS_2_5.values()))
        for item, name in PINS_2_5.items():
            with self.subTest(pin=item):
                if name in UNWRITTEN_PINS:
                    self.assertEqual(getattr(interpretation, name), '')
                else:  # a sha256 in lowercase hexadecimal; its value is its step's pin test's to check
                    self.assertRegex(getattr(interpretation, name), r'\A[0-9a-f]{64}\Z')
                self.assertRegex(_pin_comment(source, name), r'\bstep (?:[0-9][a-z]|8)\b')

    def test_the_family_dispatch_keeps_working_for_both_versions(self):
        for version, new in ((interpretation.ENGINE_VERSION, True), (interpretation.ENGINE_VERSION_V2, True),
                             ('cpt-studio-validation@10', False), ('cpt-studio-events', False), (None, False)):
            with self.subTest(engine_version=version):
                self.assertIs(interpretation.is_new_assessment(types.SimpleNamespace(engine_version=version)), new)
        for version, new in ((interpretation.CONTEXT_VERSION, True), (interpretation.CONTEXT_VERSION_V2, True),
                             ('gi-context@5', False), ('gemini-context', False), (None, False)):
            with self.subTest(context_version=version):
                self.assertIs(interpretation.is_new_context(types.SimpleNamespace(version=version)), new)
        family = interpretation._family
        self.assertEqual(family(interpretation.ENGINE_VERSION), family(interpretation.ENGINE_VERSION_V2))
        self.assertEqual(family(interpretation.CONTEXT_VERSION), family(interpretation.CONTEXT_VERSION_V2))

    def test_the_package_still_imports_nothing(self):
        tree = ast.parse(_init_source())
        imports = [node for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom))]
        self.assertEqual([(node.module, [alias.name for alias in node.names]) for node in imports],
                         [('__future__', ['annotations'])])


# --- the settings -----------------------------------------------------------------------------------------------------


def _settings_literals() -> dict:
    """cptstudio/settings.py's literal assignments, read as the installer's tests read them
    (ops/test_install_harness)."""
    literals = {}
    for node in ast.parse((APP / 'cptstudio' / 'settings.py').read_text(encoding='utf-8')).body:
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
            try:
                literals[node.targets[0].id] = ast.literal_eval(node.value)
            except (ValueError, TypeError, SyntaxError):
                pass
    return literals


class SettingsTests(SimpleTestCase):
    def test_the_second_call_takes_d49s_deadlines(self):
        from studio import jobs

        self.assertEqual((settings.APPRAISER_READ_TIMEOUT_SECONDS, settings.APPRAISER_SEND_DEADLINE_SECONDS,
                          settings.JOB_DEADLINE_SECONDS['appraise']), (480, 510, 560))
        # D49's values: the interpreter's, unchanged beside them
        self.assertEqual((settings.INTERPRETER_READ_TIMEOUT_SECONDS, settings.INTERPRETER_SEND_DEADLINE_SECONDS,
                          settings.JOB_DEADLINE_SECONDS['interpret']), (480, 510, 560))
        # the read bounds the generation inside the send; the send and its recording fit the stage, and the stage ends
        # before the stale-stage sweep (7.4)
        self.assertLess(settings.APPRAISER_READ_TIMEOUT_SECONDS, settings.APPRAISER_SEND_DEADLINE_SECONDS)
        self.assertLess(settings.APPRAISER_SEND_DEADLINE_SECONDS + jobs.LOOP_RECORDING_SECONDS,
                        settings.JOB_DEADLINE_SECONDS['appraise'])
        self.assertLess(settings.JOB_DEADLINE_SECONDS['appraise'], settings.STALE_RUNNING_SECONDS)
        # a cut-off answer of 32,768 tokens at the slowest measured rate (82.4 tokens per second) fits the read
        self.assertLess(32_768 / 82.4, settings.APPRAISER_READ_TIMEOUT_SECONDS)

    def test_they_are_literal_assignments_as_the_interpreters_are(self):
        literals = _settings_literals()
        self.assertEqual((literals['APPRAISER_READ_TIMEOUT_SECONDS'], literals['APPRAISER_SEND_DEADLINE_SECONDS'],
                          literals['JOB_DEADLINE_SECONDS']['appraise']), (480, 510, 560))
        # every other stage's deadline is as before
        self.assertEqual({kind: seconds for kind, seconds in literals['JOB_DEADLINE_SECONDS'].items()
                          if kind != 'appraise'},
                         {'extract': 300, 'analyze': 60, 'predict': 180, 'assess': 120, 'review2': 180, 'astra': 580,
                          'fable': 580, 'astra_peer': 580, 'fable_peer': 580, 'interpret': 560})


# --- the enumerations -------------------------------------------------------------------------------------------------

# The design's own lists (FINAL-V2 1.3, 1.4, 1.7, 2.4, 3.2), written out here.
DESIGN_LISTS = {
    ct.FactState: ('supported', 'negated', 'contradicted'),
    ct.Link: ('statement', 'section', 'frame', 'placing', 'document_frame', 'antecedent', 'other_statement'),
    ct.Qualifier: ('hedged', 'conditional', 'reported', 'partial', 'named_only', 'restatement_only', 'reference_only',
                   'approximate'),
    ct.DoubtBasis: ('stated', 'conflict', 'unclear'),
    ct.DoubtAbout: ('status', 'kind', 'session', 'date_relation', 'performer', 'entry', 'target', 'technique',
                    'purpose', 'cause', 'part_of', 'yield', 'access_outcome', 'extent', 'stations', 'completion',
                    'approach', 'anatomy', 'identity', 'date_of_service', 'visit', 'whole'),
    ct.Status: ('performed', 'attempted_not_completed', 'planned'),
    ct.DateRelation: ('on_date_of_service', 'earlier_date', 'later_date'),
    ct.EncounterRelation: ('this_encounter', 'separate_encounter'),
    ct.Performer: ('documenting_team', 'other_clinician', 'other_facility'),
    ct.Owner: ('documenting_clinician', 'nursing', 'anesthesia', 'pathology', 'radiology', 'other_clinician',
               'outside_record', 'patient_reported', 'administrative'),
    ct.SectionRole: ('header', 'indication', 'history', 'medications', 'sedation', 'procedure', 'findings',
                     'impression', 'complications', 'specimens', 'plan', 'pathology_result', 'nursing_note',
                     'anesthesia_record', 'addendum', 'signature', 'other'),
    ct.PersonRole: ('documenting_clinician', 'trainee', 'assistant', 'nurse', 'anesthesia', 'pathologist',
                    'radiologist', 'referring', 'other'),
    ct.OtherClass: ('procedure', 'test', 'order', 'imaging', 'laboratory', 'counseling', 'evaluation', 'medication',
                    'other'),
    ct.Tract: ('upper', 'lower', 'pancreatobiliary'),
    ct.Approach: ('oral', 'transnasal', 'transanal', 'through_stoma', 'through_pouch', 'through_gastrostomy',
                  'percutaneous'),
    ct.Completion: ('complete', 'incomplete', 'terminated'),
    ct.Station: ('esophagus', 'stomach', 'duodenum', 'jejunum', 'ileum', 'colon', 'rectum'),
    ct.Structure: ('lesion', 'stricture', 'ulcer', 'bleeding_site', 'vessel', 'varix', 'stone', 'stent', 'duct',
                   'pancreatic_fluid_collection', 'gallbladder', 'liver', 'lymph_node', 'mass', 'wall', 'lumen',
                   'foreign_body', 'mucosa', 'anastomosis', 'other'),
    ct.Duct: ('biliary', 'pancreatic', 'cystic'),
    ct.Route: ('submucosal', 'eus_transmural', 'eus_fine_needle', 'intraluminal', 'intraductal', 'percutaneous',
               'topical'),
    ct.Purpose: ('diagnostic', 'removal', 'lift_for_resection', 'marking', 'hemostasis', 'prophylaxis', 'treatment',
                 'access', 'sampling', 'drainage', 'decompression', 'other'),
    ct.Cause: ('act_of_this_session', 'pre_existing_lesion', 'spontaneous', 'earlier_procedure', 'other'),
    ct.PartRelation: ('step_of', 'lift_for', 'access_for', 'adjunct_of', 'component_of'),
    ct.Material: ('stones', 'stone_fragments', 'sludge', 'debris', 'stent', 'foreign_body', 'tissue', 'anything'),
    ct.AccessOutcome: ('achieved', 'failed', 'achieved_after_failed_attempts'),
    ct.Breadth: ('single_target', 'listed_targets', 'all_of_kind', 'exceptive', 'segment'),
    ct.AnatomyType: ('surgically_absent', 'anastomosis', 'stoma', 'ileal_pouch', 'gastric_pouch', 'roux_limb',
                     'bypass', 'other_alteration'),
    ct.AnastomosisSubtype: ('ileocolic', 'colocolic', 'colorectal', 'coloanal', 'ileorectal', 'ileoanal',
                            'gastrojejunal', 'gastroduodenal', 'esophagojejunal', 'esophagogastric', 'hepaticojejunal',
                            'choledochoduodenal', 'pancreaticojejunal', 'other'),
    ct.RestatementRole: ('restates', 'summarizes', 'title', 'names_only', 'refers_back'),
    ct.EmBasis: ('total_time', 'medical_decision_making'),
    ct.Separate: ('stated',),
    ct.Result: ('supported', 'negated', 'contradicted', 'unknown', 'unresolved'),
    ct.Precision: ('day', 'month', 'year'),
    ct.VerdictValue: ('supports', 'contradicts', 'qualified', 'unclear'),
    ct.Attached: ('yes', 'no', 'unclear'),
    ct.UnlistedWhat: ('act', 'denial', 'doubt'),
    ct.CardType: ('act', 'session', 'section', 'lesion', 'anatomy'),
    et.ItemKind: ('question', 'explanation'),
    et.Outcome: ('ready', 'needs_clarification', 'excluded'),
    et.Cover: ('citation',),
    et.IdFamily: ('E', 'X', 'N', 'L', 'Y', 'P', 'S'),
}
QUALIFIERS_2_ADDED = ('negated_context', 'other_occasion', 'other_performer', 'other_entry', 'other_target',
                      'other_act', 'scope_limited', 'planned_only', 'history_only')
ATTRIBUTES = (
    'date_of_service', 'other_dates.role', 'documenting_clinician', 'role', 'owner', 'occasion', 'performer',
    'performer_person', 'examination', 'kind', 'encounter', 'tract', 'approach', 'through', 'reached', 'device_reached',
    'reached_anatomy', 'completion', 'stations', 'part_of_session', 'type', 'organ', 'subtype', 'joins', 'multiplicity',
    'places', 'distinct_from', 'same_as', 'restatements.role', 'other_class', 'status', 'session', 'date_relation',
    'date', 'target.lesion', 'target.structure', 'target.places', 'target.anatomy', 'target.duct', 'technique.device',
    'technique.route', 'purpose', 'cause', 'cause_event', 'part_of', 'part_relation', 'yield', 'access_outcome',
    'scope.breadth', 'scope.targets', 'scope.segment', 'scope.covers', 'scope.excepts', 'visit.basis',
    'visit.separately_identifiable', 'entry')


def _derived_lists() -> dict:
    """The lists FINAL-V2 1.4 derives from v1's, computed here from v1's schema."""
    landmarks = [value for value in schema.LANDMARKS if value != 'not_stated']
    at = landmarks.index('second_portion_duodenum') + 1
    landmarks[at:at] = ['third_portion_duodenum', 'fourth_portion_duodenum']
    return {
        ct.Kind: tuple(schema.KINDS),
        ct.DateRole: tuple(schema.DATE_ROLES),
        ct.DateState: tuple(schema.DATE_STATES),
        ct.Multiplicity: tuple(value for value in schema.MULTIPLICITY if value != 'unknown'),
        ct.Device: tuple(value for value in schema.DEVICES if value != 'not_stated'),
        ct.Landmark: tuple(landmarks),
        ct.Extent: tuple(landmarks) + ('stated_depth',),
        ct.SessionKind: tuple(value for value in schema.PROCEDURES if value != 'unknown'),
    }


# 3.1 K1's rules in its order, each giving the reason structure_<rule> (DECISIONS D186)
K1_RULES = ('scope', 'yield', 'access_outcome', 'cause', 'part_of', 'endoscopic', 'visit', 'other_class', 'status_time',
            'exceptive', 'listed_targets', 'single_target', 'segment', 'umbrella')


def _reasons() -> tuple:
    """FINAL-V2 3.3's reasons in its row order, 3.1's check reasons in row 4 (K1's after G5's), 3.2.3's in row 9 (a
    qualified verdict that names no qualifier after those that name one): DECISIONS D186."""
    qualifiers = DESIGN_LISTS[ct.Qualifier]
    return (('contradicted_by_pass1', 'doubt_stated', 'doubt_unclear', 'silent',
             'shape_inconsistent', 'unit_unknown', 'words_not_in_units', 'words_not_bounded', 'units_not_consecutive',
             'source_too_long', 'anchor_words', 'reference_invalid')
            + tuple(f'geometry_{link}' for link in DESIGN_LISTS[ct.Link])
            + ('section_order', 'section_start_unlocated', 'target_detached', 'inherit_unattached', 'extent_inferred')
            + tuple(f'structure_{rule}' for rule in K1_RULES)
            + ('session_inconsistent', 'session_conflict', 'session_unreachable', 'anatomy_conflict',
               'person_conflict', 'instrument_conflict', 'frame_role', 'literal_mismatch', 'literal_unchecked',
               'anchor_invalid')
            + tuple(f'qualified:{q}' for q in qualifiers if q != 'approximate')
            + ('unappraised', 'cards_indistinct', 'control_incoherent', 'appraisal_contradicts')
            + tuple(f'appraisal_qualified:{q}' for q in qualifiers + QUALIFIERS_2_ADDED)
            + ('appraisal_qualified', 'appraisal_unclear', 'appraisal_detached', 'appraisal_missing'))


def _all_enums() -> dict:
    expected = {**DESIGN_LISTS, **_derived_lists(), ct.Attribute: ATTRIBUTES, ct.Reason: _reasons(),
                ct.Qualifier2: DESIGN_LISTS[ct.Qualifier] + QUALIFIERS_2_ADDED, ct.CheckStatus: ('ok', 'failed')}
    return expected


class EnumTests(SimpleTestCase):
    def test_every_enumeration_is_the_designs_in_its_order(self):
        for cls, values in _all_enums().items():
            with self.subTest(enum=cls.__name__):
                self.assertEqual(tuple(member.value for member in cls), values)

    def test_every_enumeration_of_both_modules_is_checked(self):
        defined = {value for module in (ct, et) for value in vars(module).values()
                   if isinstance(value, type) and issubclass(value, enum.Enum) and value.__module__ == module.__name__}
        self.assertEqual(defined, set(_all_enums()))

    def test_the_sizes_the_design_states(self):
        self.assertEqual((len(ct.Kind), len(ct.Device), len(ct.SessionKind), len(ct.Landmark), len(ct.Extent)),
                         (42, 29, 16, len(schema.LANDMARKS) + 1, len(schema.LANDMARKS) + 2))
        self.assertEqual({member.value for member in ct.Extent} - {member.value for member in ct.Landmark},
                         {'stated_depth'})

    def test_each_is_a_plain_unique_closed_enum(self):
        for cls in _all_enums():
            with self.subTest(enum=cls.__name__):
                self.assertFalse(issubclass(cls, str))  # never a StrEnum: a member is not a str (5.7 measure 5)
                self.assertEqual(len(cls.__members__), len(list(cls)))  # no alias
                self.assertTrue(all(type(member.value) is str for member in cls))
                with self.assertRaises(ValueError):
                    cls('a value the design does not name')
                first = next(iter(cls))
                self.assertNotEqual(first, first.value)  # a member never equals a raw string

    def test_member_names_follow_their_values(self):
        for cls in _all_enums():
            if cls is et.IdFamily:
                continue
            for member in cls:
                with self.subTest(member=f'{cls.__name__}.{member.name}'):
                    self.assertEqual(member.name, re.sub(r'[^a-z0-9]+', '_', member.value).upper())

    def test_each_card_type_gives_its_id_letter(self):
        # FINAL-V2 2.4: cards are renumbered A1.. acts and statements about acts, X1.. sessions, N0.. sections, L1..
        # lesions, Y1.. anatomy entries; the letter is CardType's own, so a renumbering reads it instead of a copy
        self.assertEqual([card_type.letter for card_type in ct.CardType], ['A', 'X', 'N', 'L', 'Y'])


# --- the records ------------------------------------------------------------------------------------------------------

# Every record and exactly the fields the design names (FINAL-V2 1.2, 1.3, 1.7, 2.4, 3.2.4, 4.1, 4.4, 9.1).
FIELDS = {
    ct.Span: ('start', 'end'),
    ct.Unit: ('id', 'start', 'end', 'line', 'paragraph', 'page', 'forced'),
    ct.Source: ('units', 'words', 'link'),
    ct.Option: ('value', 'sources'),
    ct.Fact: ('state', 'value', 'qualifiers', 'sources', 'options'),
    ct.Doubt: ('about', 'objects', 'units', 'basis', 'readings'),
    ct.Claim: ('id', 'template', 'subject', 'value', 'units', 'content'),
    ct.Card: ('id', 'type', 'units', 'kind_words', 'status_words'),
    ct.Verdict: ('claim', 'verdict', 'attached', 'qualifiers', 'evidence'),
    ct.Unlisted: ('units', 'what', 'kind', 'session'),
    ct.LocatedWords: ('start', 'end', 'text'),
    ct.SettledSource: ('units', 'link', 'words', 'geometry'),
    ct.SettledOption: ('value', 'sources'),
    ct.SettledClaim: ('state', 'value', 'qualifiers', 'options', 'inherited_from'),
    ct.StoredLiteral: ('value', 'precision'),
    ct.Checks: ('integrity', 'geometry', 'literal', 'literals', 'consistency', 'qualified'),
    ct.ControlVerdict: ('claim', 'verdict'),
    ct.Appraisal: ('claim', 'content', 'verdict', 'attached', 'qualifiers', 'evidence', 'control'),
    ct.SettledFact: ('claim', 'sources', 'checks', 'appraisal', 'result', 'reasons'),
    # DECISIONS D206: what contract/checks.check returns, and contract/geometry.py's records inside it, field for field
    ct.Citation: ('units', 'span', 'words', 'place', 'reasons'),
    ct.AnchorCitation: ('units', 'span', 'kind_words', 'status_words', 'place', 'reasons'),
    ct.SectionPlace: ('id', 'index', 'start', 'opening', 'start_units', 'end_units', 'closers', 'closed', 'closing',
                      'span', 'reasons'),
    ct.Checked: ('units', 'closures', 'citations', 'anchors', 'sections', 'containing', 'restatements', 'findings',
                 'failed_links', 'literals', 'joined', 'document_date', 'objectless_doubts'),
    et.Id: ('family', 'number'),
    et.IsoDate: ('value', 'precision'),
    et.Cited: ('link', 'units', 'at'),  # DECISIONS D188
    et.Fact: ('result', 'value', 'state', 'options', 'reasons', 'spans', 'cited', 'inherited_from', 'counter'),  # D188
    et.Anchor: ('units', 'kind_words', 'status_words'),
    et.UnlistedStatement: ('units', 'what', 'kind', 'session'),
    et.FactSet: ('encounter', 'people', 'sections', 'sessions', 'anatomy', 'lesions', 'events', 'anchors', 'unlisted',
                 'pair_controls', 'completeness'),
    et.HeldFact: ('fact', 'attribute', 'subject', 'result', 'kind', 'cause', 'reason', 'spans', 'rank'),  # D189
    et.Exclusion: ('event', 'fact', 'cover', 'anchor'),
    et.Evaluation: ('supporting', 'held_facts', 'bindings', 'exclusion'),
}

# Every record field's type as typing.get_type_hints reads it, written out from the design (FINAL-V2 1.2, 1.3, 1.7, 2.4,
# 4.1, 4.4; DECISIONS D188, D189): names and order alone let a retyped field through (Source.link as a str, say). A
# fact value is spelled out, not read from et.Value, so the alias cannot widen unseen.
_VALUE = enum.Enum | et.Id | et.IsoDate
_FACTS = Mapping[ct.Attribute, tuple[et.Fact, ...]]
_OBJECTS = Mapping[et.Id, _FACTS]
TYPES = {
    ct.Span: {'start': int, 'end': int},
    ct.Unit: {'id': str, 'start': int, 'end': int, 'line': int, 'paragraph': int, 'page': int, 'forced': bool},
    ct.Source: {'units': tuple[str, ...], 'words': str, 'link': ct.Link},
    ct.Option: {'value': str, 'sources': tuple[ct.Source, ...]},
    ct.Fact: {'state': ct.FactState, 'value': str, 'qualifiers': tuple[ct.Qualifier, ...],
              'sources': tuple[ct.Source, ...], 'options': tuple[ct.Option, ...]},
    ct.Doubt: {'about': ct.DoubtAbout, 'objects': tuple[str, ...], 'units': tuple[str, ...], 'basis': ct.DoubtBasis,
               'readings': tuple[str, ...]},
    ct.Claim: {'id': str, 'template': str, 'subject': str, 'value': str, 'units': tuple[str, ...], 'content': str},
    ct.Card: {'id': str, 'type': ct.CardType, 'units': tuple[str, ...], 'kind_words': ct.Span | None,
              'status_words': ct.Span | None},
    ct.Verdict: {'claim': str, 'verdict': ct.VerdictValue, 'attached': ct.Attached,
                 'qualifiers': tuple[ct.Qualifier2, ...], 'evidence': tuple[str, ...]},
    ct.Unlisted: {'units': tuple[str, ...], 'what': ct.UnlistedWhat, 'kind': ct.Kind | None, 'session': str | None},
    ct.LocatedWords: {'start': int, 'end': int, 'text': str},
    ct.SettledSource: {'units': tuple[str, ...], 'link': ct.Link, 'words': ct.LocatedWords | None,
                       'geometry': ct.CheckStatus},
    ct.SettledOption: {'value': str, 'sources': tuple[ct.SettledSource, ...]},
    ct.SettledClaim: {'state': ct.FactState | None, 'value': str, 'qualifiers': tuple[ct.Qualifier, ...],
                      'options': tuple[ct.SettledOption, ...], 'inherited_from': str | None},
    ct.StoredLiteral: {'value': str, 'precision': ct.Precision},
    ct.Checks: {'integrity': ct.CheckStatus, 'geometry': ct.CheckStatus, 'literal': ct.CheckStatus,
                'literals': tuple[ct.StoredLiteral, ...], 'consistency': ct.CheckStatus, 'qualified': bool},
    ct.ControlVerdict: {'claim': str, 'verdict': ct.VerdictValue | None},
    ct.Appraisal: {'claim': str, 'content': str, 'verdict': ct.VerdictValue | None, 'attached': ct.Attached | None,
                   'qualifiers': tuple[ct.Qualifier2, ...], 'evidence': tuple[str, ...],
                   'control': ct.ControlVerdict | None},
    ct.SettledFact: {'claim': ct.SettledClaim, 'sources': tuple[ct.SettledSource, ...], 'checks': ct.Checks,
                     'appraisal': ct.Appraisal | None, 'result': ct.Result, 'reasons': tuple[ct.Reason, ...]},
    ct.Citation: {'units': tuple[str, ...], 'span': ct.Span | None, 'words': ct.LocatedWords | None,
                  'place': ct.Span | None, 'reasons': tuple[ct.Reason, ...]},
    ct.AnchorCitation: {'units': tuple[str, ...], 'span': ct.Span | None, 'kind_words': ct.LocatedWords | None,
                        'status_words': ct.LocatedWords | None, 'place': ct.Span | None,
                        'reasons': tuple[ct.Reason, ...]},
    ct.SectionPlace: {'id': str, 'index': int, 'start': int | None, 'opening': ct.Span | None,
                      'start_units': tuple[str, ...], 'end_units': tuple[tuple[str, ...], ...],
                      'closers': tuple[ct.Span | None, ...], 'closed': bool, 'closing': int | None,
                      'span': ct.Span | None, 'reasons': tuple[ct.Reason, ...]},
    # generic in the answer's fact key, ct.Key (checks.check fills Checked[extract_read.FactKey])
    ct.Checked: {'units': tuple[ct.Unit, ...], 'closures': Mapping[tuple[str, ...], tuple[str, ...]],
                 'citations': Mapping[ct.Source, ct.Citation], 'anchors': Mapping[str, ct.AnchorCitation],
                 'sections': tuple[ct.SectionPlace, ...], 'containing': Mapping[str, str],
                 'restatements': Mapping[tuple[str, int], str | None],
                 'findings': Mapping[ct.Key, tuple[ct.Reason, ...]],
                 'failed_links': Mapping[ct.Key, tuple[ct.Source, ...]],
                 'literals': Mapping[ct.Key, tuple[ct.StoredLiteral, ...]],
                 'joined': tuple[tuple[tuple[ct.Key, ...], tuple[ct.Key, ...]], ...],
                 'document_date': datetime.date | None, 'objectless_doubts': Mapping[int, tuple[str, ...]]},
    et.Id: {'family': et.IdFamily, 'number': int},
    et.IsoDate: {'value': datetime.date, 'precision': ct.Precision},
    et.Cited: {'link': ct.Link, 'units': ct.Span, 'at': ct.Span | None},
    et.Fact: {'result': ct.Result, 'value': _VALUE | None, 'state': ct.FactState | None, 'options': tuple[_VALUE, ...],
              'reasons': tuple[ct.Reason, ...], 'spans': tuple[ct.Span, ...], 'cited': tuple[et.Cited, ...],
              'inherited_from': et.Id | None, 'counter': tuple[ct.Span, ...]},
    et.Anchor: {'units': tuple[ct.Span, ...], 'kind_words': ct.Span | None, 'status_words': ct.Span | None},
    et.UnlistedStatement: {'units': tuple[ct.Span, ...], 'what': ct.UnlistedWhat, 'kind': ct.Kind | None,
                           'session': et.Id | None},
    et.FactSet: {'encounter': _FACTS, 'people': _OBJECTS, 'sections': _OBJECTS, 'sessions': _OBJECTS,
                 'anatomy': _OBJECTS, 'lesions': _OBJECTS, 'events': _OBJECTS, 'anchors': Mapping[et.Id, et.Anchor],
                 'unlisted': tuple[et.UnlistedStatement, ...],
                 'pair_controls': Mapping[tuple[et.Id, ct.Attribute, _VALUE], bool],
                 'completeness': Mapping[et.Id, ct.Result]},
    et.HeldFact: {'fact': str, 'attribute': ct.Attribute | None, 'subject': et.Id | None, 'result': ct.Result | None,
                  'kind': et.ItemKind, 'cause': str, 'reason': ct.Reason | None, 'spans': tuple[ct.Span, ...],
                  'rank': int | None},
    et.Exclusion: {'event': et.Id, 'fact': ct.Attribute, 'cover': et.Cover, 'anchor': tuple[ct.Span, ...]},
    et.Evaluation: {'supporting': tuple[et.Id, ...], 'held_facts': tuple[et.HeldFact, ...],
                    'bindings': Mapping[tuple[ct.Kind, ...], et.Id], 'exclusion': et.Exclusion | None},
}

E1, E2, X1, N2, L1 = (et.Id(et.IdFamily.EVENT, 1), et.Id(et.IdFamily.EVENT, 2), et.Id(et.IdFamily.SESSION, 1),
                      et.Id(et.IdFamily.SECTION, 2), et.Id(et.IdFamily.LESION, 1))


def _samples() -> dict:
    """One synthetic instance of every record: ids, enumeration members and offsets only (the text is 'abcd')."""
    source = ct.Source(('S1', 'S2'), '', ct.Link.STATEMENT)
    words = ct.LocatedWords(0, 4, 'abcd')
    settled_source = ct.SettledSource(('S1',), ct.Link.SECTION, words, ct.CheckStatus.OK)
    control = ct.ControlVerdict('K2', ct.VerdictValue.CONTRADICTS)
    checks = ct.Checks(ct.CheckStatus.OK, ct.CheckStatus.OK, ct.CheckStatus.OK,
                       (ct.StoredLiteral('2026-11-09', ct.Precision.DAY),), ct.CheckStatus.OK, False)
    appraisal = ct.Appraisal('K1', 'f' * 64, ct.VerdictValue.SUPPORTS, ct.Attached.YES, (), ('S1',), control)
    claim = ct.SettledClaim(ct.FactState.SUPPORTED, 'on_date_of_service', (), (), 'N2')
    span = ct.Span(0, 4)
    cited = et.Cited(ct.Link.SECTION, span, ct.Span(1, 3))
    fact = et.Fact(ct.Result.SUPPORTED, ct.DateRelation.ON_DATE_OF_SERVICE, ct.FactState.SUPPORTED, (), (), (span,),
                   (cited,), N2, ())
    held = et.HeldFact('event_time', ct.Attribute.DATE_RELATION, E1, ct.Result.UNKNOWN, et.ItemKind.QUESTION,
                       'reading_unknown', ct.Reason.DOUBT_UNCLEAR, (span,), 6)
    exclusion = et.Exclusion(E2, ct.Attribute.STATUS, et.Cover.CITATION, (span,))
    citation = ct.Citation(('S1', 'S2'), span, words, span, ())
    anchor = ct.AnchorCitation(('S1',), span, words, None, span, ())
    place = ct.SectionPlace('N1', 1, 0, ct.Span(0, 2), ('S1',), (('S2',),), (ct.Span(2, 4),), True, 4, span, ())
    status, kind = _fact_key('E1', ct.Attribute.STATUS), _fact_key('E1', ct.Attribute.KIND)
    checked = ct.Checked((ct.Unit('S1', 0, 4, 1, 1, 1, False),), {('S1',): ('S1',)}, {source: citation}, {'E1': anchor},
                         (place,), {'E1': 'N1'}, {('E1', 0): 'N1'}, {status: (ct.Reason.GEOMETRY_STATEMENT,)},
                         {status: (source,)}, {kind: (ct.StoredLiteral('2026-11-09', ct.Precision.DAY),)},
                         (((status,), (kind,)),), datetime.date(2026, 11, 9), {0: ('E1',)})
    return {
        ct.Span: span,
        ct.Unit: ct.Unit('S1', 0, 4, 1, 1, 1, False),
        ct.Source: source,
        ct.Option: ct.Option('earlier_date', (source,)),
        ct.Fact: ct.Fact(ct.FactState.NEGATED, 'performed', (ct.Qualifier.APPROXIMATE,), (source,), ()),
        ct.Doubt: ct.Doubt(ct.DoubtAbout.DATE_RELATION, ('E1',), ('S1',), ct.DoubtBasis.UNCLEAR,
                           ('on_date_of_service', 'earlier_date')),
        ct.Claim: ct.Claim('K1', 'act.date_relation', 'E1', 'on_date_of_service', ('S1',), 'f' * 64),
        ct.Card: ct.Card('A1', ct.CardType.ACT, ('S1', 'S2'), span, None),
        ct.Verdict: ct.Verdict('K1', ct.VerdictValue.QUALIFIED, ct.Attached.UNCLEAR, (ct.Qualifier2.HISTORY_ONLY,),
                               ('S1',)),
        ct.Unlisted: ct.Unlisted(('S3',), ct.UnlistedWhat.DENIAL, ct.Kind.BIOPSY, None),
        ct.LocatedWords: words,
        ct.SettledSource: settled_source,
        ct.SettledOption: ct.SettledOption('earlier_date', (settled_source,)),
        ct.SettledClaim: claim,
        ct.StoredLiteral: ct.StoredLiteral('2026-11', ct.Precision.MONTH),
        ct.Checks: checks,
        ct.ControlVerdict: control,
        ct.Appraisal: appraisal,
        ct.SettledFact: ct.SettledFact(claim, (settled_source,), checks, appraisal, ct.Result.SUPPORTED, ()),
        ct.Citation: citation,
        ct.AnchorCitation: anchor,
        ct.SectionPlace: place,
        ct.Checked: checked,
        et.Id: E1,
        et.IsoDate: et.IsoDate(datetime.date(2026, 11, 9), ct.Precision.DAY),
        et.Cited: cited,
        et.Fact: fact,
        et.Anchor: et.Anchor((span,), span, None),
        et.UnlistedStatement: et.UnlistedStatement((span,), ct.UnlistedWhat.ACT, None, X1),
        et.FactSet: et.FactSet({ct.Attribute.DATE_OF_SERVICE: (fact,)}, {}, {}, {X1: {}}, {}, {L1: {}},
                               {E1: {ct.Attribute.DATE_RELATION: (fact,)}}, {E1: et.Anchor((span,), None, None)}, (),
                               {(E2, ct.Attribute.TARGET_PLACES, ct.Landmark.RECTUM): True}, {X1: ct.Result.SUPPORTED}),
        et.HeldFact: held,
        et.Exclusion: exclusion,
        et.Evaluation: et.Evaluation((E1,), (held,), {(ct.Kind.SNARE,): E1}, exclusion),
    }


class RecordTests(SimpleTestCase):
    def test_each_record_holds_exactly_the_fields_the_design_names(self):
        for cls, names in FIELDS.items():
            with self.subTest(record=cls.__name__):
                self.assertEqual(tuple(field.name for field in dataclasses.fields(cls)), names)

    def test_each_record_field_has_the_type_the_design_names(self):
        self.assertEqual(set(TYPES), set(FIELDS))
        for cls, hints in TYPES.items():
            with self.subTest(record=cls.__name__):
                self.assertEqual(tuple(hints), FIELDS[cls])
                self.assertEqual(typing.get_type_hints(cls), hints)

    def test_every_record_of_both_modules_is_checked(self):
        for module in (ct, et):
            with self.subTest(module=module.__name__):
                defined = {value for value in vars(module).values() if isinstance(value, type)
                           and dataclasses.is_dataclass(value) and value.__module__ == module.__name__}
                self.assertEqual(defined, {cls for cls in FIELDS if cls.__module__ == module.__name__})

    def test_an_engine_fact_keeps_its_six_field_constructor(self):
        # DECISIONS D188 adds cited, inherited_from and counter, each empty by default: 4.1's six-field Fact builds as
        # before, and the three fields carry what they are given
        span, cited = ct.Span(0, 4), et.Cited(ct.Link.STATEMENT, ct.Span(0, 9), None)
        six = et.Fact(ct.Result.SUPPORTED, ct.Performer.DOCUMENTING_TEAM, ct.FactState.SUPPORTED, (), (), (span,))
        self.assertEqual((six.cited, six.inherited_from, six.counter), ((), None, ()))
        nine = et.Fact(ct.Result.SUPPORTED, ct.Performer.DOCUMENTING_TEAM, ct.FactState.SUPPORTED, (), (), (span,),
                       (cited,), N2, (ct.Span(5, 9),))
        self.assertEqual((nine.cited, nine.inherited_from, nine.counter), ((cited,), N2, (ct.Span(5, 9),)))
        self.assertNotEqual(nine, six)
        self.assertEqual(dataclasses.replace(nine, cited=(), inherited_from=None, counter=()), six)

    def test_records_construct_and_are_frozen_with_slots(self):
        samples = _samples()
        self.assertEqual(set(samples), set(FIELDS))
        for cls, sample in samples.items():
            with self.subTest(record=cls.__name__):
                self.assertIsInstance(sample, cls)
                self.assertTrue(cls.__dataclass_params__.frozen)
                self.assertEqual(cls.__slots__, FIELDS[cls])
                self.assertFalse(hasattr(sample, '__dict__'))
                with self.assertRaises(dataclasses.FrozenInstanceError):
                    setattr(sample, FIELDS[cls][0], getattr(sample, FIELDS[cls][0]))
                with self.assertRaises((dataclasses.FrozenInstanceError, AttributeError, TypeError)):
                    setattr(sample, 'not_a_field', 1)
                self.assertEqual(sample, copy.copy(sample))

    def test_the_engine_boundary_holds_no_str(self):
        # FINAL-V2 4.1, 5.7 measure 5: a fact value is an Enum member, an Id or an IsoDate; no field is a str, but
        # HeldFact's fact and cause, CPT Studio's own codes in 4.4's parameterized forms
        allowed = {(et.HeldFact, 'fact'), (et.HeldFact, 'cause')}
        for cls in (cls for cls in FIELDS if cls.__module__ == et.__name__):
            hints = typing.get_type_hints(cls, vars(et))
            for name, hint in hints.items():
                with self.subTest(field=f'{cls.__name__}.{name}'):
                    self.assertEqual(str in _leaves(hint), (cls, name) in allowed)
        self.assertEqual(set(typing.get_args(et.Value)), {enum.Enum, et.Id, et.IsoDate})

    def test_span(self):
        self.assertEqual(sorted([ct.Span(5, 9), ct.Span(0, 4), ct.Span(0, 2)]),
                         [ct.Span(0, 2), ct.Span(0, 4), ct.Span(5, 9)])
        self.assertIs(et.Span, ct.Span)
        for start, end in ((-1, 2), (3, 2), (True, 2), (0, 2.0), ('0', 2)):
            with self.subTest(span=(start, end)), self.assertRaises(ValueError):
                ct.Span(start, end)

    @hypothesis.settings(database=None, deadline=None)
    @hypothesis.given(st.integers(-5, 50), st.integers(-5, 50))
    def test_a_span_exists_exactly_when_it_runs_forward_from_zero(self, start, end):
        if 0 <= start <= end:
            self.assertEqual((ct.Span(start, end).start, ct.Span(start, end).end), (start, end))
        else:
            with self.assertRaises(ValueError):
                ct.Span(start, end)

    def test_ids(self):
        for label in ('E1', 'N0', 'X12', 'L3', 'Y1', 'P2', 'S181'):
            with self.subTest(label=label):
                self.assertEqual(str(et.Id.parse(label)), label)
        self.assertEqual(et.Id.parse('N0'), et.Id(et.IdFamily.SECTION, 0))
        for label in ('', 'E', 'E03', 'E+3', 'E 3', 'e3', 'E-1', 'E3 ', ' E3', 'K1', 'A1', 'E٣', 'E3.0', 'EE3'):
            with self.subTest(label=label), self.assertRaises(ValueError):
                et.Id.parse(label)
        for family, number in ((et.IdFamily.EVENT, -1), (et.IdFamily.EVENT, True), ('E', 1)):
            with self.subTest(id=(family, number)), self.assertRaises(ValueError):
                et.Id(family, number)
        self.assertEqual(len({E1, et.Id.parse('E1'), E2}), 2)  # hashable, by value

    @hypothesis.settings(database=None, deadline=None)
    @hypothesis.given(st.sampled_from(list(et.IdFamily)), st.integers(0, 10 ** 9))
    def test_an_id_round_trips_through_its_label(self, family, number):
        self.assertEqual(et.Id.parse(str(et.Id(family, number))), et.Id(family, number))

    @hypothesis.settings(database=None, deadline=None)
    @hypothesis.given(st.text(max_size=8))
    def test_parse_accepts_only_the_canonical_label(self, label):
        try:
            parsed = et.Id.parse(label)
        except ValueError:
            return
        self.assertEqual(str(parsed), label)

    def test_iso_dates(self):
        cases = ((datetime.date(2026, 11, 9), ct.Precision.DAY, '2026-11-09'),
                 (datetime.date(2026, 11, 1), ct.Precision.MONTH, '2026-11'),
                 (datetime.date(2023, 1, 1), ct.Precision.YEAR, '2023'))
        for value, precision, iso in cases:
            with self.subTest(iso=iso):
                self.assertEqual(et.IsoDate(value, precision).iso, iso)
        for value, precision in ((datetime.date(2026, 11, 9), ct.Precision.MONTH),
                                 (datetime.date(2023, 2, 1), ct.Precision.YEAR),
                                 (datetime.date(2026, 11, 9), 'day'),
                                 # a date value is a datetime.date: never text, never a datetime, checked first
                                 ('2026-11-09', ct.Precision.DAY), (datetime.datetime(2026, 11, 9), ct.Precision.DAY),
                                 (datetime.datetime(2026, 11, 1), ct.Precision.MONTH), (20261109, ct.Precision.DAY),
                                 (None, ct.Precision.YEAR), ('2026-11-09', 'day')):
            with self.subTest(date=(value, precision)), self.assertRaises(ValueError):
                et.IsoDate(value, precision)

    def test_a_factset_and_an_evaluation_freeze_what_they_are_given(self):
        span = ct.Span(0, 4)
        fact = et.Fact(ct.Result.UNKNOWN, None, None, (), (ct.Reason.SILENT,), ())
        events = {E1: {ct.Attribute.STATUS: (fact,)}}
        unlisted = [et.UnlistedStatement((span,), ct.UnlistedWhat.DOUBT, None, None)]
        facts = et.FactSet({}, {}, {}, {}, {}, {}, events, {}, unlisted, {}, {})
        events[E2] = {}  # the caller's mapping changes; the FactSet does not
        events[E1][ct.Attribute.KIND] = (fact,)
        self.assertEqual(list(facts.events), [E1])
        self.assertEqual(list(facts.events[E1]), [ct.Attribute.STATUS])
        self.assertIsInstance(facts.unlisted, tuple)
        for mapping in (facts.events, facts.events[E1], facts.encounter, facts.anchors, facts.pair_controls,
                        facts.completeness):
            with self.subTest(mapping=type(mapping).__name__), self.assertRaises(TypeError):
                mapping[E2] = ()
        self.assertEqual(facts, et.FactSet({}, {}, {}, {}, {}, {}, {E1: {ct.Attribute.STATUS: (fact,)}}, {},
                                           tuple(unlisted), {}, {}))
        bindings = {(ct.Kind.DILATION,): E1}
        evaluation = et.Evaluation([E1], [], bindings)
        bindings[(ct.Kind.STENT,)] = E2
        self.assertEqual((evaluation.supporting, evaluation.held_facts, dict(evaluation.bindings),
                          evaluation.exclusion), ((E1,), (), {(ct.Kind.DILATION,): E1}, None))
        with self.assertRaises(TypeError):
            evaluation.bindings[(ct.Kind.STENT,)] = E2


def _leaves(hint) -> set:
    """Every type a hint is built from (unions, generics and aliases unfolded)."""
    args = typing.get_args(hint)
    if not args:
        return {hint}
    return set().union(*(_leaves(arg) for arg in args)) | ({typing.get_origin(hint)} if typing.get_origin(hint)
                                                             is not types.UnionType else set())


# --- the check records (DECISIONS D206; the waves 1-2 triage's INT-4) -------------------------------------------------

# A synthetic note, written for these tests (the clinician is fictional; no development or acceptance document), whose
# sections give geometry one closing source that locates (N1's) and one that does not (N2's).
NOTE = ('SYNTHETIC COLONOSCOPY NOTE\n'
        'Findings: The colonoscope was advanced to the cecum. A polyp was removed with a cold snare.\n'
        'Signed by Q. R. Vance, MD (fictional).\n'
        'Plan: Repeat colonoscopy in 3 years.\n')
# contract/geometry.py's records: those Checked carries (defined in contract/types.py, D206), its inputs, and those used
# only inside checks.check (G5's unit sets and the subject G1 measures against).
GEOMETRY_CARRIED = {'Citation': ct.Citation, 'AnchorCitation': ct.AnchorCitation, 'SectionPlace': ct.SectionPlace}
GEOMETRY_INPUTS = frozenset({'Anchor', 'Restatement', 'Section', 'Event'})
GEOMETRY_INTERNAL = frozenset({'Extent', 'Subject'})
# Each field of contract/consistency.Findings (step 2b), and the Checked field that carries it.
FINDINGS_HOME = {'structure': 'findings', 'consistency': 'findings', 'literal': 'findings', 'qualified': 'findings',
                 'literals': 'literals', 'joined': 'joined', 'document_date': 'document_date'}
# Each field contract/claims.Basis (step 2c) reads besides pass 1's answer, and the Checked field it comes from.
BASIS_HOME = {'units': 'units', 'findings': 'findings', 'closures': 'closures', 'sections': 'containing',
              'restatement_sections': 'restatements', 'anchor_words': 'anchors'}
KEYED = frozenset({'findings', 'failed_links', 'literals', 'joined'})  # the Checked fields typed by the fact key
STANDARD_TYPES = frozenset({str, int, bool, type(None), datetime.date, tuple, Mapping})
# mypy --strict reads a Checked by its fact key: a key of that type passes, its iteration yields it, another is refused
# (line 11 alone, its errors naming the key).
GENERIC_PROBE = ('from dataclasses import dataclass\n'
                 'from studio.interpretation.contract.types import Checked, Reason\n'
                 '@dataclass(frozen=True)\n'
                 'class FactKey:\n'
                 '    number: int\n'
                 'def reasons(checked: Checked[FactKey]) -> tuple[Reason, ...]:\n'
                 '    return checked.findings.get(FactKey(1), ())\n'
                 'def first(checked: Checked[FactKey]) -> int:\n'
                 '    return next(iter(checked.findings)).number + checked.joined[0][1][0].number\n'
                 'def wrong(checked: Checked[FactKey]) -> tuple[Reason, ...]:\n'
                 '    return checked.findings.get("E1", ())\n')


def _fact_key(event: str, attribute: ct.Attribute, index: int = 0) -> extract_read.FactKey:
    """An event's fact key, as contract/extract_read keys it (the key checks.check fills Checked with)."""
    return extract_read.FactKey(extract_schema.Family.EVENT, event, attribute, index)


def _inside(record: type) -> set:
    """Every type the fields of ``record`` are built from, and those of every record among them, recursively."""
    found: set = set()
    pending = [record]
    while pending:
        for hint in typing.get_type_hints(pending.pop()).values():
            for leaf in _leaves(hint):
                if leaf not in found:
                    found.add(leaf)
                    if dataclasses.is_dataclass(leaf):
                        pending.append(leaf)
    return found


def _note_geometry() -> tuple:
    """NOTE's layout and sections, as contract/geometry.py computes them."""
    layout = geometry.Layout.of(NOTE)
    sections = geometry.Sections(layout, [
        geometry.Section('N0', ct.Source((), '', ct.Link.SECTION), ()),
        geometry.Section('N1', ct.Source(('S2',), 'Findings:', ct.Link.SECTION),
                         (ct.Source(('S4',), 'Signed by Q. R. Vance', ct.Link.SECTION),)),
        geometry.Section('N2', ct.Source(('S5',), 'Plan:', ct.Link.SECTION),
                         (ct.Source(('S9',), 'nothing', ct.Link.SECTION),))])
    return layout, sections


def _moved(cls: type, record: object) -> object:
    """``record`` copied field for field into ``cls``: how checks.check can put geometry's records into a Checked until
    geometry returns contract/types.py's own (the request to step 1c)."""
    return cls(**{field.name: getattr(record, field.name) for field in dataclasses.fields(record)})


def _short_lines(source: str) -> list:
    """Each docstring line (number, text) that stops short inside its paragraph: 79 characters or fewer, followed by
    another line of the same paragraph (the modules wrap at 120). A list item or a table row (a line opening with -,
    *, | or a number and a full stop) starts a line of its own, so a short line before one ends nothing early."""
    lines, found = source.split('\n'), []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) \
                    and isinstance(first.value.value, str):
                for number in range(first.lineno, first.end_lineno):
                    line, following = lines[number - 1], lines[number].strip()
                    opener = following.split(' ', 1)[0]
                    item = following.startswith(('-', '*', '|')) or (opener.endswith('.') and opener[:-1].isdigit())
                    if line.strip() and following and following != '"""' and not item and len(line) < 80:
                        found.append((number, line))
    return found


class CheckRecordTests(SimpleTestCase):
    def test_the_note_is_synthetic_and_no_acceptance_document(self):
        with open(DEV_EXCLUSION, encoding='ascii') as handle:
            excluded = {line.strip() for line in handle if line.strip()}
        self.assertEqual(len(excluded), 288)
        for data in (NOTE.encode('utf-8'), NOTE.strip().encode('utf-8')):
            self.assertNotIn(hashlib.sha256(data).hexdigest(), excluded)

    def test_geometrys_records_are_defined_here_field_for_field(self):
        # D206: the records inside Checked live in this module. Each equals geometry's own in its fields, their order,
        # their types and its dataclass form, so geometry can import it from here with no other change.
        for name, record in GEOMETRY_CARRIED.items():
            theirs = getattr(geometry, name)
            with self.subTest(record=name):
                self.assertEqual([field.name for field in dataclasses.fields(record)],
                                 [field.name for field in dataclasses.fields(theirs)])
                self.assertEqual(typing.get_type_hints(record), typing.get_type_hints(theirs))
                self.assertEqual(record.__slots__, theirs.__slots__)
                self.assertEqual(repr(record.__dataclass_params__), repr(theirs.__dataclass_params__))
        # the integration's O3: SectionPlace carries closers, each closing source's place, right after end_units
        names = [field.name for field in dataclasses.fields(ct.SectionPlace)]
        self.assertEqual(names.index('closers'), names.index('end_units') + 1)
        self.assertEqual(typing.get_type_hints(ct.SectionPlace)['closers'], tuple[ct.Span | None, ...])

    def test_geometrys_output_moves_into_them_with_nothing_lost(self):
        layout, sections = _note_geometry()
        located, unlocated = sections.place('N1'), sections.place('N2')
        # both kinds of closer: one that locates (its place) and one that does not (None; G2 then fails)
        self.assertEqual((located.closers, located.closing, located.span),
                         ((ct.Span(119, 140),), 140, ct.Span(27, 140)))
        self.assertEqual((unlocated.closers, unlocated.closing, unlocated.span, unlocated.reasons),
                         ((None,), None, None, (ct.Reason.SECTION_START_UNLOCATED,)))
        anchor = geometry.locate_anchor(layout, geometry.Anchor(('S3',), 'cold snare', 'was removed'))
        citation = geometry.locate(layout, ct.Source(('S2', 'S3'), 'cecum. A polyp', ct.Link.STATEMENT))
        self.assertEqual((anchor.reasons, citation.reasons), ((), ()))
        produced = ((located, ct.SectionPlace), (unlocated, ct.SectionPlace), (sections.opening, ct.SectionPlace),
                    (anchor, ct.AnchorCitation), (citation, ct.Citation))
        for record, mine in produced:
            with self.subTest(record=type(record).__name__):
                moved = _moved(mine, record)
                self.assertIs(type(moved), mine)
                self.assertEqual(dataclasses.astuple(moved), dataclasses.astuple(record))
        # what geometry returns is what Checked's records hold, by the type geometry declares
        self.assertIs(typing.get_type_hints(geometry.locate)['return'], geometry.Citation)
        self.assertIs(typing.get_type_hints(geometry.bind_words)['return'], geometry.Citation)
        self.assertIs(typing.get_type_hints(geometry.locate_anchor)['return'], geometry.AnchorCitation)
        self.assertEqual(typing.get_type_hints(geometry.Sections.place)['return'], geometry.SectionPlace | None)

    def test_checked_freezes_what_it_is_given(self):
        key, other = _fact_key('E1', ct.Attribute.STATUS), _fact_key('E2', ct.Attribute.STATUS)
        clean = _fact_key('E3', ct.Attribute.STATUS)  # given with empty entries: absent means none
        source = ct.Source(('S1',), '', ct.Link.STATEMENT)
        unit = ct.Unit('S1', 0, 4, 1, 1, 1, False)
        citation = ct.Citation(('S1',), ct.Span(0, 4), None, ct.Span(0, 4), ())
        anchor = ct.AnchorCitation(('S1',), ct.Span(0, 4), None, None, ct.Span(0, 4), ())
        place = ct.SectionPlace('N0', 0, 0, ct.Span(0, 0), (), (), (), False, None, ct.Span(0, 4), ())
        literal = ct.StoredLiteral('2026-11', ct.Precision.MONTH)
        given = {'units': [unit], 'closures': {('S1',): ['S1']}, 'citations': {source: citation},
                 'anchors': {'E1': anchor}, 'sections': [place], 'containing': {'E1': 'N0'},
                 'restatements': {('E1', 0): None}, 'findings': {key: [ct.Reason.UNIT_UNKNOWN]},
                 'failed_links': {key: [source]}, 'literals': {key: [literal]}, 'joined': [([key], [other])],
                 'document_date': datetime.date(2026, 11, 9), 'objectless_doubts': {0: ['E1']}}
        for name in ('findings', 'failed_links', 'literals'):
            given[name][clean] = []
        given['objectless_doubts'][2] = []  # kept: no event qualifies (D200)
        checked = ct.Checked(**given)
        frozen = {'units': (unit,), 'closures': {('S1',): ('S1',)}, 'citations': {source: citation},
                  'anchors': {'E1': anchor}, 'sections': (place,), 'containing': {'E1': 'N0'},
                  'restatements': {('E1', 0): None}, 'findings': {key: (ct.Reason.UNIT_UNKNOWN,)},
                  'failed_links': {key: (source,)}, 'literals': {key: (literal,)}, 'joined': (((key,), (other,)),),
                  'document_date': datetime.date(2026, 11, 9), 'objectless_doubts': {0: ('E1',), 2: ()}}
        # the caller's containers change, inside and out; the Checked does not
        given['units'].append(ct.Unit('S2', 5, 9, 1, 1, 1, False))
        given['closures'][('S1',)].append('S2')
        given['closures'][('S2',)] = ['S2']
        given['citations'].clear()
        given['anchors']['E2'] = anchor
        given['sections'].clear()
        given['containing']['E2'] = 'N0'
        given['restatements'][('E1', 1)] = 'N0'
        given['findings'][key].append(ct.Reason.SOURCE_TOO_LONG)
        given['findings'][other] = [ct.Reason.SILENT]
        given['failed_links'][key].clear()
        given['literals'][key].append(literal)
        given['joined'][0][0].append(other)
        given['joined'].append(([], []))
        given['objectless_doubts'][0].append('E2')
        given['objectless_doubts'][1] = []
        for name, value in frozen.items():
            with self.subTest(field=name):
                held = getattr(checked, name)
                self.assertEqual(dict(held) if isinstance(held, Mapping) else held, value)
                if isinstance(held, Mapping):  # read-only, and every sequence value a tuple
                    with self.assertRaises(TypeError):
                        held['a key'] = ()
                    self.assertTrue(all(type(item) is not list for item in held.values()))
                elif name != 'document_date':
                    self.assertIs(type(held), tuple)
        self.assertTrue(all(type(side) is tuple for pair in checked.joined for side in pair))
        self.assertTrue(all(clean not in getattr(checked, name) for name in ('findings', 'failed_links', 'literals')))
        with self.assertRaises(TypeError):  # it holds read-only mappings, so it is not hashable
            hash(checked)
        self.assertEqual(checked, ct.Checked(**frozen))

    def test_checked_is_generic_in_the_answers_fact_key(self):
        # extract_read defines FactKey and imports this module, so the key is a type parameter, bound to Hashable
        self.assertIs(ct.Key.__bound__, Hashable)
        self.assertTrue(issubclass(extract_read.FactKey, Hashable))
        hints = typing.get_type_hints(ct.Checked)
        self.assertEqual({name for name, hint in hints.items() if ct.Key in _leaves(hint)}, KEYED)
        self.assertIs(typing.get_origin(ct.Checked[extract_read.FactKey]), ct.Checked)
        self.assertEqual(typing.get_args(ct.Checked[extract_read.FactKey]), (extract_read.FactKey,))
        self.assertIn(typing.Generic, ct.Checked.__mro__)

    def test_mypy_reads_a_checked_by_its_fact_key_and_refuses_another(self):
        probe = subprocess.run([sys.executable, '-m', 'mypy', '--strict', '--cache-dir', os.devnull, '-c',
                                GENERIC_PROBE], capture_output=True, text=True, timeout=300, cwd=APP)
        errors = [line for line in probe.stdout.splitlines() if ': error:' in line]
        self.assertEqual(probe.returncode, 1, probe.stdout + probe.stderr)
        self.assertEqual({error.split(':')[1] for error in errors}, {'11'}, probe.stdout)
        self.assertTrue(any('No overload variant of "get" of "Mapping" matches argument types "str"' in error
                            for error in errors), probe.stdout)
        self.assertIn('def get(self, FactKey, /) -> tuple[Reason, ...] | None', probe.stdout)

    def test_every_type_inside_checked_is_this_modules_or_the_standard_librarys(self):
        # so settle.py and claims.py read a Checked importing contract/types.py alone (D206)
        found = _inside(ct.Checked)
        own = {leaf for leaf in found if isinstance(leaf, type) and leaf.__module__ == ct.__name__}
        self.assertEqual(found - own - STANDARD_TYPES - {...}, {ct.Key})  # ...: tuple[X, ...]'s ellipsis
        self.assertLessEqual({ct.Citation, ct.AnchorCitation, ct.SectionPlace, ct.Unit, ct.Source, ct.LocatedWords,
                              ct.Span, ct.StoredLiteral, ct.Reason, ct.Link, ct.Precision}, own)

    def test_checked_carries_every_finding_its_producers_give(self):
        checked = typing.get_type_hints(ct.Checked)
        reasons = typing.get_args(checked['findings'])[1]
        self.assertEqual(reasons, tuple[ct.Reason, ...])
        # consistency.Findings (2b): K1-K7, L1 and Q1 by fact key into findings; L1's literals, K8's groups and the
        # claim-time reference date each into their own field
        produced = typing.get_type_hints(consistency.Findings)
        self.assertEqual(set(produced), set(FINDINGS_HOME))
        self.assertLessEqual(set(FINDINGS_HOME.values()), set(checked))
        for name in ('structure', 'consistency', 'literal', 'qualified'):
            with self.subTest(findings=name):
                self.assertEqual(produced[name], Mapping[extract_read.FactKey, reasons])
        self.assertEqual(typing.get_args(produced['literals']),
                         (extract_read.FactKey, typing.get_args(checked['literals'])[1]))
        self.assertEqual(produced['document_date'], checked['document_date'])
        # K8: a Joined's family, object and attribute are each of its keys' own, so the pair (supported, negated)
        # carries it whole
        joined, key = typing.get_type_hints(consistency.Joined), typing.get_type_hints(extract_read.FactKey)
        self.assertEqual(produced['joined'], tuple[consistency.Joined, ...])
        self.assertEqual([field.name for field in dataclasses.fields(consistency.Joined)],
                         ['family', 'object', 'attribute', 'supported', 'negated'])
        self.assertEqual({name: joined[name] for name in ('family', 'object', 'attribute')},
                         {name: key[name] for name in ('family', 'object', 'attribute')})
        self.assertEqual((joined['supported'], joined['negated']), (tuple[extract_read.FactKey, ...],) * 2)
        self.assertEqual(checked['joined'], tuple[tuple[tuple[ct.Key, ...], tuple[ct.Key, ...]], ...])
        # the reader's (1b) item-level findings: closed-list reasons by fact key, as findings keeps them; a doubt by
        # its position, as objectless_doubts keys it
        for record in (extract_read.ReadFact, extract_read.ReadMember):
            with self.subTest(read=record.__name__):
                hints = typing.get_type_hints(record)
                self.assertEqual((hints['key'], hints['reasons']), (extract_read.FactKey, reasons))
        self.assertIs(typing.get_type_hints(extract_read.ReadDoubt)['index'],
                      typing.get_args(checked['objectless_doubts'])[0])
        # geometry (1c): every record it defines is an input, a record Checked carries, or used inside checks.check
        records = {name for name, value in vars(geometry).items() if isinstance(value, type)
                   and dataclasses.is_dataclass(value) and (value.__module__ == geometry.__name__
                                                            or name in GEOMETRY_CARRIED)}
        self.assertEqual(records, set(GEOMETRY_CARRIED) | GEOMETRY_INPUTS | GEOMETRY_INTERNAL)
        self.assertLessEqual(set(GEOMETRY_CARRIED.values()), _inside(ct.Checked))

    def test_checked_carries_every_input_claims_reads(self):
        # claims.Basis (2c) reads pass 1's answer and what geometry computed: each of the latter from one Checked field
        basis, checked = typing.get_type_hints(claims.Basis), typing.get_type_hints(ct.Checked)
        self.assertEqual(set(basis) - {'answer'}, set(BASIS_HOME))
        self.assertLessEqual(set(BASIS_HOME.values()), set(checked))
        for name in ('units', 'closures', 'sections'):
            with self.subTest(basis=name):
                self.assertEqual(basis[name], checked[BASIS_HOME[name]])
        self.assertEqual(typing.get_args(basis['findings']),
                         (extract_read.FactKey, typing.get_args(checked['findings'])[1]))
        # a restatement's section: Checked's None marks a restatement G6 counts that lies attached in no section
        theirs, mine = typing.get_args(basis['restatement_sections']), typing.get_args(checked['restatements'])
        self.assertEqual((mine[0], mine[1]), (theirs[0], theirs[1] | None))
        # an event's located kind and status words: Basis takes their spans, which each AnchorCitation's hold
        self.assertEqual(basis['anchor_words'], Mapping[str, tuple[ct.Span | None, ct.Span | None]])
        self.assertEqual(checked['anchors'], Mapping[str, ct.AnchorCitation])
        anchor, words = typing.get_type_hints(ct.AnchorCitation), typing.get_type_hints(ct.LocatedWords)
        self.assertEqual((anchor['kind_words'], anchor['status_words']), (ct.LocatedWords | None,) * 2)
        self.assertEqual((words['start'], words['end']), (int, int))

    def test_the_engine_docstrings_say_what_is_built(self):
        # the integration's O4: iso_value reads a date as store's _v2_date_precision does (1d#6 dropped _v2_precision)
        self.assertIn("(store's _v2_date_precision)", facts.iso_value.__doc__)
        self.assertTrue(callable(store._v2_date_precision))
        self.assertFalse(hasattr(store, '_v2_precision'))
        # t0's note 7: facts.py builds the FactSet from store.textfree_v2's view of the row (DECISIONS D188)
        module = ' '.join(et.__doc__.split())
        self.assertIn("engine/facts.py (step 2d) builds the FactSet only from store.textfree_v2's view of the stored "
                      "row, in which every source's words are offsets and no text remains (DECISIONS D188)", module)
        self.assertNotIn('strips every text', module)
        self.assertTrue(callable(store.textfree_v2))
        # and no docstring line of either types module stops short inside its paragraph (HeldFact's "(4.4:" line did)
        for name in ('contract/types', 'engine/types'):
            with self.subTest(module=name):
                self.assertEqual(_short_lines(NEW_MODULES[name].read_text(encoding='utf-8')), [])
        held = ' '.join(et.HeldFact.__doc__.split())
        self.assertIn('who owns the hold in measurement (4.4: reading_unknown, reading_contradicted,', held)
        # the rule's planted controls: a paragraph broken early is found, one wrapped at the width is not
        broken = 'def f():\n    """A paragraph that\n    goes on after an early break."""\n'
        self.assertEqual(_short_lines(broken), [(2, '    """A paragraph that')])
        self.assertEqual(_short_lines('def f():\n    """' + 'word ' * 22 + '\n    goes on."""\n'), [])
        listed = 'def f():\n    """The steps:\n    - one;\n    - two.\n    1. three.\n    | a | b |\n    """\n'
        self.assertEqual(_short_lines(listed), [])


# --- the boundary: done-when of 8.1 step 0b, and 5.7 measure 4 kept ahead of step 6a's guard --------------------------

RETIRED = ('prompt', 'schema', 'read', 'normalize', 'verify', 'literals', 'identity', 'lexicon', 'relations', 'mapping',
           'classes', 'ercp', 'facts', 'events', 'coverage', 'combination', 'assess')  # FINAL-V2 5.0
TEXT_MODULES = ('segment', 'geometry', 'fold', 'date_literals')  # contract's, FINAL-V2 5.7 measure 4
FORBIDDEN_IMPORTS = ('re', 'regex', 'unicodedata', 'difflib', 'fnmatch', 'lexicon', 'literals')
STR_METHODS = ('find', 'index', 'rfind', 'startswith', 'endswith', 'split', 'rsplit', 'partition', 'lower', 'upper',
               'casefold', 'strip', 'replace', 'count', 'istitle', 'isupper')
TEXT_NAMES = ('text', 'words', 'quote', 'unit_text')


def _imported(tree: ast.AST) -> list:
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found += [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            found += [node.module or ''] + [f'{node.module}.{alias.name}' for alias in node.names]
    return found


def _strings(node: ast.AST) -> int:
    """How many string constants a literal collection holds (a dict's keys and values both)."""
    items = [*node.keys, *node.values] if isinstance(node, ast.Dict) else getattr(node, 'elts', [])
    return sum(1 for item in items if isinstance(item, ast.Constant) and isinstance(item.value, str))


def measure_4(source: str, engine: bool) -> list:
    """5.7 measure 4's rules as they bind a new module of this step: the imports (WordsNeverDecide's), NoWordLists (no
    module-level collection of two or more strings) and, in engine/, WordsNeverDecide's text rules."""
    tree, out = ast.parse(source), []
    for name in _imported(tree):
        parts = name.split('.')
        if parts[0] in FORBIDDEN_IMPORTS or (len(parts) > 2 and parts[:2] == ['studio', 'interpretation']
                                             and parts[2] in RETIRED + FORBIDDEN_IMPORTS):
            out.append(f'imports {name}')
        if engine and parts[:3] == ['studio', 'interpretation', 'contract'] and len(parts) > 3 and \
                parts[3] in TEXT_MODULES:
            out.append(f'imports a text module {name}')
    for statement in tree.body:
        if isinstance(statement, (ast.Assign, ast.AnnAssign)) and statement.value is not None:
            for node in ast.walk(statement.value):
                if isinstance(node, (ast.Tuple, ast.List, ast.Set, ast.Dict)) and _strings(node) >= 2:
                    out.append(f'a module-level word list at line {node.lineno}')
    if engine:
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr in TEXT_NAMES:
                out.append(f'reads .{node.attr}')
            elif isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Constant) and \
                    node.slice.value in TEXT_NAMES:
                out.append(f"reads [{node.slice.value!r}]")
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and \
                    node.func.attr in STR_METHODS and not isinstance(node.func.value, ast.Constant):
                out.append(f'calls .{node.func.attr}()')
            elif isinstance(node, ast.Compare) and any(isinstance(op, (ast.In, ast.NotIn)) for op in node.ops):
                operands = [node.left, *node.comparators]
                if any((isinstance(item, ast.Constant) and isinstance(item.value, str)) or _strings(item)
                       for item in operands):
                    out.append(f'tests membership against a string at line {node.lineno}')
    return out


class BoundaryTests(SimpleTestCase):
    def test_the_types_import_with_no_v1_module(self):
        code = ('import sys\n'
                'import studio.interpretation.contract.types, studio.interpretation.engine.types\n'
                'import studio.interpretation.contract.jsonschema\n'
                'print(",".join(sorted(m for m in sys.modules if m.startswith("studio"))))\n')
        result = subprocess.run([sys.executable, '-I', '-B', '-c', f'import sys; sys.path.insert(0, {str(APP)!r})\n'
                                 + code], capture_output=True, text=True, timeout=60, cwd=APP)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip().split(','),
                         ['studio', 'studio.interpretation', 'studio.interpretation.contract',
                          'studio.interpretation.contract.jsonschema', 'studio.interpretation.contract.types',
                          'studio.interpretation.engine', 'studio.interpretation.engine.types'])

    def test_mypy_strict_passes_on_both_types_files_and_refuses_a_string_operation_on_a_value(self):
        def mypy(*arguments):
            return subprocess.run([sys.executable, '-m', 'mypy', '--strict', '--cache-dir', os.devnull, *arguments],
                                  capture_output=True, text=True, timeout=300, cwd=APP)

        result = mypy('studio/interpretation/contract/types.py', 'studio/interpretation/engine/types.py')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('Success: no issues found in 2 source files', result.stdout)
        # the positive control: the fence mypy is here for (5.7 measure 5) - a string operation on a fact value fails
        probe = mypy('-c', 'from studio.interpretation.engine.types import Fact\n'
                           'def probe(fact: Fact) -> bool:\n'
                           '    return fact.value.startswith("x") if fact.value is not None else False\n')
        self.assertEqual(probe.returncode, 1, probe.stdout + probe.stderr)
        self.assertIn('has no attribute "startswith"', probe.stdout)

    def test_the_new_modules_keep_measure_4(self):
        for name, path in NEW_MODULES.items():
            with self.subTest(module=name):
                self.assertEqual(measure_4(path.read_text(encoding='utf-8'), engine=name.startswith('engine/')), [])
        # engine/types.py names contract's types only, never a text module, and nothing of v1
        engine = [n for n in _imported(ast.parse(NEW_MODULES['engine/types'].read_text(encoding='utf-8')))
                  if n.startswith('studio')]
        self.assertTrue(engine)
        self.assertTrue(all(n.startswith('studio.interpretation.contract.types') for n in engine), engine)

    def test_each_rule_refuses_a_planted_control(self):
        plants = {
            'import re\n': 'imports re',
            'import unicodedata\n': 'imports unicodedata',
            'from studio.interpretation import lexicon\n': 'imports studio.interpretation.lexicon',
            'from studio.interpretation.schema import canonical\n': 'imports studio.interpretation.schema',
            'from studio.interpretation.contract import fold\n': 'imports a text module',
            "MARKERS = ('no', 'not')\n": 'a module-level word list',
            "TABLE = frozenset({'denied', 'without'})\n": 'a module-level word list',
            'def f(fact):\n    return fact.text\n': 'reads .text',
            "def f(row):\n    return row['words']\n": "reads ['words']",
            'def f(value):\n    return value.startswith("no")\n': 'calls .startswith()',
            'def f(value):\n    return "no" in value\n': 'tests membership against a string',
        }
        for plant, expected in plants.items():
            with self.subTest(plant=plant.strip()):
                found = measure_4(plant, engine=True)
                self.assertTrue(any(expected in finding for finding in found), found)
        self.assertEqual(measure_4('def f(value):\n    return value is None\n', engine=True), [])  # a control


# --- contract/jsonschema.py against v1's schema.py --------------------------------------------------------------------


def _nodes(node):
    """Every schema node of a LOCAL schema, the root included."""
    yield node
    for child in node.get('properties', {}).values():
        yield from _nodes(child)
    if 'items' in node:
        yield from _nodes(node['items'])


def _normalized(function) -> str:
    """A function's code with its docstring and annotations dropped (an annotated assignment read as a plain one)."""
    tree = ast.parse(inspect.getsource(function))
    definition = tree.body[0]
    definition.returns = None
    for argument in definition.args.args + definition.args.kwonlyargs:
        argument.annotation = None
    if isinstance(definition.body[0], ast.Expr) and isinstance(definition.body[0].value, ast.Constant):
        definition.body = definition.body[1:]
    for parent in ast.walk(definition):
        for field, value in ast.iter_fields(parent):
            if isinstance(value, list):
                setattr(parent, field, [ast.Assign(targets=[item.target], value=item.value, type_comment=None)
                                        if isinstance(item, ast.AnnAssign) else item for item in value])
    return ast.dump(definition)


MALFORMED = (
    [], 'string', {'type': 'object'},
    {'type': 'string', 'format': 'date'},
    {'type': 'number'},
    {'type': 'object', 'properties': {'a': {'type': 'string'}}, 'required': ['a']},
    {'type': 'object', 'properties': {'a': {'type': 'string'}}, 'required': [], 'additionalProperties': False},
    {'type': 'object', 'properties': {'a': {'type': 'string'}, 'b': {'type': 'string'}}, 'required': ['b', 'a'],
     'additionalProperties': False},
    {'type': 'string', 'enum': []},
    {'type': 'string', 'enum': ['a', 'a']},
    {'type': 'string', 'enum': ['a', 1]},
    {'type': 'integer', 'enum': ['1']},
    {'type': 'array', 'items': {'type': 'string', 'nullable': True}},
    {'type': 'array'},
)


class JsonSchemaParityTests(SimpleTestCase):
    def test_gemini_schema_equals_v1s_on_v1s_own_schemas(self):
        self.assertEqual(jsonschema.gemini_schema(schema.LOCAL_SCHEMA), schema.gemini_schema(schema.LOCAL_SCHEMA))
        self.assertEqual(jsonschema.gemini_schema(schema.LOCAL_SCHEMA), schema.RESPONSE_SCHEMA)
        count = 0
        for node in _nodes(schema.LOCAL_SCHEMA):
            count += 1
            self.assertEqual(jsonschema.gemini_schema(node), schema.gemini_schema(node))
        self.assertGreater(count, 100)  # it walked the whole schema

    def test_every_refusal_is_v1s(self):
        for node in MALFORMED:
            with self.subTest(node=node):
                with self.assertRaises(ValueError) as v1:
                    schema.gemini_schema(node)
                with self.assertRaises(ValueError) as v2:
                    jsonschema.gemini_schema(node)
                self.assertEqual(str(v2.exception), str(v1.exception))

    def test_the_canonical_bytes_and_hashes_are_v1s(self):
        values = (schema.LOCAL_SCHEMA, schema.RESPONSE_SCHEMA, dict(schema.BOUNDS), prompt.INSTRUCTIONS,
                  {'b': ['é', 1, None, True], 'a': {'z': 'ü', 'y': 2.5}}, [], '', 'Å')
        for value in values:
            with self.subTest(value=str(value)[:40]):
                self.assertEqual(jsonschema.canonical(value), schema.canonical(value))
                self.assertEqual(jsonschema.sha256_of(value), schema.sha256_of(value))
        # v1's own pins, reproduced through the copy
        self.assertEqual((jsonschema.sha256_of(prompt.INSTRUCTIONS), jsonschema.sha256_of(schema.LOCAL_SCHEMA),
                          jsonschema.sha256_of(schema.RESPONSE_SCHEMA)),
                         (interpretation.INSTRUCTIONS_SHA256, interpretation.LOCAL_SCHEMA_SHA256,
                          interpretation.RESPONSE_SCHEMA_SHA256))
        for bad in (float('nan'), {'a': float('inf')}):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError) as v1:
                    schema.canonical(bad)
                with self.assertRaises(ValueError) as v2:
                    jsonschema.canonical(bad)
                self.assertEqual(str(v2.exception), str(v1.exception))

    def test_the_derived_schema_shares_nothing_with_its_source(self):
        before = jsonschema.canonical(schema.LOCAL_SCHEMA)
        derived = jsonschema.gemini_schema(schema.LOCAL_SCHEMA)
        derived['properties']['events']['items']['properties']['kind']['properties']['value']['enum'].append('x')
        derived['required'].append('x')
        self.assertEqual(jsonschema.canonical(schema.LOCAL_SCHEMA), before)

    def test_the_code_is_v1s(self):
        self.assertEqual(jsonschema._KEYWORDS, schema._KEYWORDS)
        for name in ('gemini_schema', 'canonical', 'sha256_of'):
            with self.subTest(function=name):
                self.assertEqual(_normalized(getattr(jsonschema, name)), _normalized(getattr(schema, name)))
