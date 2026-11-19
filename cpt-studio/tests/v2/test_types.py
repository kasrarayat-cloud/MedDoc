"""Design v2's shared labels and types (docs/gemini-migration/FINAL-V2.md, step 0b of 8.1), TEXT-ONLY and SYNTHETIC.

What is proved here, each against the design or against v1 computed in the test:
- the labels: v1's names and values byte-identical (the 17 retired modules read them for good, 5.0) but MODEL's value,
  which DECISIONS D230 sets to gemini-4-carbon for every request built (D272, step cb); v2's labels of 1.1
  under new names; every pin of 2.5 named, each naming the step that fills it, and written as a sha256 but the health
  thresholds' (DECISIONS D202); the family dispatch of is_new_assessment and is_new_context for @1 and @2 alike;
- AMENDMENT-2's labels (8.1, adopted by DECISIONS D279; the interpreter is Claude Fable 5.2, D275): the _V3 names beside
  v2's, each fitting its column, the anthropic-version value beside ADAPTER_VERSION_V3, READ_PROVIDERS, the model and
  provider; its pins (8.2, with the three pass-2 objects D292's U1 and U3 change) placeholders that name their steps,
  and every pin of a recorded label kept byte for byte;
- the settings: AMENDMENT-2 1.12's deadlines for both passes as literal assignments, and D289's guard (G2-01): each
  send deadline at least fable_adapter.MAX_TOKENS at 100 tokens per second plus 40 s, each read timeout at most its
  deadline, each stage at least its send, recording and 45 s, each stale threshold above its stage; 1.11's credential
  settings (the existing Anthropic credential, the historical mode and replay settings);
- the enumerations: each a plain, unique, closed Enum whose values are the design's strings in its order, the ones the
  design derives from v1 equal to v1's tuples by value;
- the records: frozen dataclasses with slots holding exactly the fields the design names, each of the type it names
  (typing.get_type_hints); the engine's text-free boundary, typed (no field holds a str but HeldFact's two code fields);
  AMENDMENT-2 4.3's two additions, Reason.SLOT_OVERFULL in row 4 right after reference_invalid and the engine Fact's
  defaulted negated_values;
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

# v1's label lines, verbatim: each must stand in __init__.py exactly once, byte for byte (FINAL-V2 5.0); MODEL's value is
# DECISIONS D230's (the owner's directive of 2026-11-13: gemini-4-carbon), its comment unchanged.
V1_LINES = (
    "INTERPRETATION_VERSION = 'gemini-events@1'",
    "INSTRUCTIONS_SHA256 = '00da58c5a8f0f5deca4ee0dd8259bb7065ee6dd551e408e3257bd33b4eee14b1'",
    "LOCAL_SCHEMA_SHA256 = '93574cacb4dc3d9fb0c3ed7789a8c2f7c708bf94176b53f1dd850fcd0214ccc3'",
    "RESPONSE_SCHEMA_SHA256 = '7bb3057d724012910b4210272c31480eacb6fc6fe6dbacbce4415c61592d2537'",
    "INVENTORY_VERSION = 'gemini-inventory@1'",
    "LABEL = f\"{INTERPRETATION_VERSION}+{INVENTORY_VERSION.removeprefix('gemini-')}\"  # gemini-events@1+inventory@1",
    "ADAPTER_VERSION = 'gemini-generate@cptstudio-1'  # ProviderRun.adapter_version (at most 40 characters)",
    "MODEL = 'gemini-4-carbon'  # D13: named by the URL; a response's modelVersion must equal it exactly",
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
    'ADAPTER_VERSION': 'gemini-generate@cptstudio-1', 'MODEL': 'gemini-4-carbon', 'PROVIDER': 'gemini',
    'PURPOSE': 'interpretation', 'JOB_KIND': 'interpret', 'ENGINE_VERSION': 'cpt-studio-events@1',
    'CONTEXT_VERSION': 'gemini-context@1', 'ROUTING_VERSION': 'gemini-routing@1',
}
# FINAL-V2 1.1, and 8.1 step 0b's names for them
V2_VALUES = {
    'INTERPRETATION_VERSION_V2': 'gemini-events@2', 'APPRAISAL_VERSION': 'gemini-appraisal@1',
    'INVENTORY_VERSION_V2': 'gemini-inventory@2', 'REQUIREMENTS_VERSION': 'cpt-requirements@3',  # D292; D324 (11)
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
# Every pin of a label already recorded (gemini-events@2: D1; gemini-appraisal@1: D1v, D1w), byte for byte: AMENDMENT-2
# moves none of them (8.2 [R:replay-R1]; DECISIONS D202), and the dormant Gemini adapter and its recordings read them.
RECORDED_PINS = {
    'INSTRUCTIONS_SHA256_V2': '543adde5d07822bc45c3eaffb52c19175ad5a8d30b842c1e2ebc8008707b9089',
    'LOCAL_SCHEMA_SHA256_V2': '7cd387041de317825f371415070bcee1703be0d9022c92bf77580f59dda3d04c',
    'RESPONSE_SCHEMA_SHA256_V2': 'bcb7fce8f1fa0b28c5fb8ea7514ba22f14ce06f18d1f557b16b92798f1109cab',
    'SEGMENTATION_SHA256': '41d2245ada69f2a573d0354486323d9f30e00fef7091f531e2e0541a11af8e78',
    'APPRAISAL_INSTRUCTIONS_SHA256': '892d696beaa9261875d7e4dfba5836b5445ce5f045c297ad668e3303f480292d',
    'APPRAISAL_LOCAL_SCHEMA_SHA256': '526dd4e4116c07ed3e1431759a47ac79d4a4d3e7aba81c3133933abe5da46cbf',
    'APPRAISAL_RESPONSE_SCHEMA_SHA256': 'fc83346270c6bc165baba78ed8a731132c7e90f172ad22853b100d085ffbd275',
    'TEMPLATES_SHA256': '8362112662c3172e6d375e713bb2ba5da7057e6f3c30085b68bc8359a50ef823',
    'STATEMENT_TEMPLATES_SHA256': '3880e4af3eefbdbccf0c5bb8e4a099df1d50268b485e991f46db7b8f3a19e162',
    'CONTROLS_SHA256': 'e4a8a79250ed14135b3d9f613fc4c4f57094bbe588b5484a1be98cc591a31c32',
    'CLAIMED_SHA256': '8c95246d6ff8a260b344bb5a52e25f51ac744343ed8ebe5887764ad7e5cd7b81',
    'HEALTH_THRESHOLDS_SHA256': '',
    'CLAIM_BOUND_SHA256': '58f544bee79e592b0a40c01e24884995f2e9dd4dd9ff4c16aeec104dcf691f02',
}

# AMENDMENT-2 8.1 (DECISIONS D279; the interpreter is Claude Fable 5.2, D275): the new names beside v2's, never in their
# place [R:replay-R4], the anthropic-version value beside the adapter version [R:replay-R8], and 1.1's model, provider
# and READ_PROVIDERS
V3_VALUES = {
    'INTERPRETATION_VERSION_V3': 'gemini-events@3', 'APPRAISAL_VERSION_V3': 'gemini-appraisal@2',
    'INVENTORY_VERSION_V3': 'gemini-inventory@3', 'ENGINE_VERSION_V3': 'cpt-studio-events@3',
    'INTERPRETATION_PAIR_V3': 'gemini-events@3/appraisal@2',
    'ADAPTER_VERSION_V3': 'anthropic-messages@cptstudio-interp-1', 'API_VERSION_V3': '2026-10-21',
    'MODEL_V3': 'claude-fable-5-2', 'PROVIDER_V3': 'anthropic', 'READ_PROVIDERS': ('anthropic', 'gemini'),
}
# each new label beside the v2 label it succeeds: the version moves, the family stays (8.1)
V3_SUCCEEDS = {'INTERPRETATION_VERSION_V3': 'INTERPRETATION_VERSION_V2', 'APPRAISAL_VERSION_V3': 'APPRAISAL_VERSION',
               'INVENTORY_VERSION_V3': 'INVENTORY_VERSION_V2', 'ENGINE_VERSION_V3': 'ENGINE_VERSION_V2'}
# AMENDMENT-2 8.2, item by item, and the name holding each new pin: the instruction of pass 1, 8.2's two pass-2 pins of
# their own, and the three pass-2 objects DECISIONS D292 changes after 8.2 was written (U1's statement templates, U3's
# reached_anatomy claim and its shared control) - each a placeholder until the integration owner writes it after the
# build's last repair, computed by its step's own function on the merged tree (D202: nothing is recorded under the new
# labels yet). Every other pin of 8.2 is a v2 pin above, kept (RECORDED_PINS).
PINS_8_2 = {
    'pass 1 instruction (INSTRUCTIONS_3, with ANSWER_SHAPE_2)': 'INSTRUCTIONS_SHA256_V3',
    'claims.TEMPLATES (D292 U3)': 'TEMPLATES_SHA256_V3',
    'claims.STATEMENT_TEMPLATES (D292 U1)': 'STATEMENT_TEMPLATES_SHA256_V3',
    'the claims.CONTROLS generator (D292 U3)': 'CONTROLS_SHA256_V3',
    'the per-request claim bound claims.CLAIM_BOUND_V3': 'CLAIM_BOUND_SHA256_V3',
    'the health thresholds of gemini-appraisal@2': 'HEALTH_THRESHOLDS_SHA256_V3',
}


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
        # v2 adds labels and changes none: pass 1 keeps v1's purpose, job kind, model and provider (1.1, 7.4); the one
        # model, of both passes and of every request built, is the one DECISIONS D230 sets
        self.assertEqual((interpretation.PURPOSE, interpretation.JOB_KIND, interpretation.MODEL),
                         ('interpretation', 'interpret', 'gemini-4-carbon'))

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
        self.assertEqual(pins, set(PINS_2_5.values()) | set(PINS_8_2.values()) | {
            'INSTRUCTIONS_SHA256', 'LOCAL_SCHEMA_SHA256', 'RESPONSE_SCHEMA_SHA256'})
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

    def test_amendment_2s_labels_are_8_1s_beside_v2s(self):
        self.assertEqual({name: getattr(interpretation, name) for name in V3_VALUES}, V3_VALUES)
        # the pair is built from its two parts, as v2's is; READ_PROVIDERS names Fable's provider and the stored runs'
        self.assertEqual(interpretation.INTERPRETATION_PAIR_V3,
                         f"{interpretation.INTERPRETATION_VERSION_V3}/"
                         f"{interpretation.APPRAISAL_VERSION_V3.removeprefix('gemini-')}")
        self.assertEqual(interpretation.READ_PROVIDERS, (interpretation.PROVIDER_V3, interpretation.PROVIDER))
        # new names, never v2's moved: each succeeds its v2 label in the same family, so the family dispatch reads an
        # @3 row as a new-path row, and the v2 names keep their values (V2_VALUES, above)
        family = interpretation._family
        for new, old in V3_SUCCEEDS.items():
            with self.subTest(label=new):
                self.assertEqual(family(getattr(interpretation, new)), family(getattr(interpretation, old)))
                self.assertNotEqual(getattr(interpretation, new), getattr(interpretation, old))
        self.assertEqual({name: getattr(interpretation, name) for name in V2_VALUES}, V2_VALUES)
        self.assertIs(interpretation.is_new_assessment(
            types.SimpleNamespace(engine_version=interpretation.ENGINE_VERSION_V3)), True)
        # the labels 8.1 leaves alone, and the Gemini model and provider the dormant adapter and its tests read (1.1)
        self.assertEqual((interpretation.CONTEXT_VERSION_V2, interpretation.ROUTING_VERSION_V2, interpretation.MODEL,
                          interpretation.PROVIDER, interpretation.ADAPTER_VERSION_V2),
                         ('gemini-context@2', 'gemini-routing@2', 'gemini-4-carbon', 'gemini',
                          'gemini-generate@cptstudio-2'))

    def test_each_v3_label_fits_its_column(self):
        columns = (
            (interpretation.INTERPRETATION_PAIR_V3, EventInventory, 'interpretation_version'),
            (interpretation.INVENTORY_VERSION_V3, EventInventory, 'inventory_version'),
            (interpretation.ENGINE_VERSION_V3, Assessment, 'engine_version'),
            (interpretation.ADAPTER_VERSION_V3, ProviderRun, 'adapter_version'),
            (interpretation.PROVIDER_V3, ProviderRun, 'provider'),
            (interpretation.MODEL_V3, ProviderRun, 'requested_model'),
            (interpretation.MODEL_V3, ProviderRun, 'returned_model'),
            *((provider, ProviderRun, 'provider') for provider in interpretation.READ_PROVIDERS),
        )
        for value, model, name in columns:
            with self.subTest(column=f'{model.__name__}.{name}', value=value):
                self.assertLessEqual(len(value), model._meta.get_field(name).max_length)
        # the counts 8.1 and 1.1 state: the pair 27 of 40, the adapter version 37 of 40, the provider 9 of 20
        self.assertEqual((len(interpretation.INTERPRETATION_PAIR_V3), len(interpretation.ADAPTER_VERSION_V3),
                          len(interpretation.PROVIDER_V3)), (27, 37, 9))

    def test_every_pin_of_8_2_is_its_owning_functions_measure_and_no_recorded_pin_moves(self):
        """AMENDMENT-2 8.2: the integration owner writes each pin after the build's last repair, by its owning step's
        function on the merged tree (D202: no recording exists under the new labels) - step f2's
        extract_prompt.pins_fable for pass 1 and appraise_prompt.pins_fable for pass 2 (f3s's documents under
        gemini-appraisal@2); HEALTH_THRESHOLDS_SHA256_V3 is settle.health_document()'s measure, 3.2.6's values
        unchanged (8.2 sets it from D3, which D277 does not run: DECISIONS D293)."""
        from studio.interpretation.contract import appraise_prompt, extract_prompt, settle
        measured = {**extract_prompt.pins_fable(), **appraise_prompt.pins_fable()}
        source = _init_source()
        for item, name in PINS_8_2.items():
            with self.subTest(pin=item):
                comment = _pin_comment(source, name)
                if name == 'HEALTH_THRESHOLDS_SHA256_V3':  # 8.2 sets it from D3, which D277 does not run: D293
                    self.assertEqual(getattr(interpretation, name), jsonschema.sha256_of(settle.health_document()))
                    self.assertRegex(comment, r'\bD277\b.*\bD293\b')
                else:  # written: its owning function's measure on this tree, the step named
                    self.assertEqual(getattr(interpretation, name), measured[name])
                    self.assertRegex(comment, r'\bstep f[0-9][a-z]*\b')
        self.assertEqual({name: getattr(interpretation, name) for name in RECORDED_PINS}, RECORDED_PINS)
        self.assertEqual(len(PINS_8_2), 6)
        # 8.2's pin of a 1,000-claim bound is the one its comment states (claims.claim_bound_document's form)
        thousand = jsonschema.sha256_of({'claims_per_request': 1000})
        self.assertEqual(thousand, '3fe08a5c8ec23575e2df78032d5b4b18dcff0927ce1c628743c47946b9415628')
        self.assertIn(thousand, _pin_comment(source, 'CLAIM_BOUND_SHA256_V3'))

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


def _settings_assigned() -> set:
    """Every name cptstudio/settings.py assigns at module level, literal or not."""
    tree = ast.parse((APP / 'cptstudio' / 'settings.py').read_text(encoding='utf-8'))
    return {target.id for node in tree.body if isinstance(node, ast.Assign) for target in node.targets
            if isinstance(target, ast.Name)}


# AMENDMENT-2 1.12's rows for the interpreter's two passes (DECISIONS D279, D289's G2-01), each pass with its send
# deadline, read timeout and stage (its job kind); every other stage keeps its deadline.
PASSES_1_12 = {'interpretation': ('INTERPRETER_SEND_DEADLINE_SECONDS', 'INTERPRETER_READ_TIMEOUT_SECONDS', 'interpret'),
               'appraisal': ('APPRAISER_SEND_DEADLINE_SECONDS', 'APPRAISER_READ_TIMEOUT_SECONDS', 'appraise')}
SEND_1_12, READ_1_12, STAGE_1_12, STALE_1_12 = 1320, 1320, 1380, 1440
# round r3 (DESIGN-v2 e.7, DECISIONS D322): the appraise stage plans round 1 of the questions after its settle, in a
# child of settings.QUESTION_CHILD_SECONDS (120 s), so its stale threshold moved by that: 1,440 -> 1,560 s
STALE_R3 = {'appraise': 1560}
OTHER_STAGES = {'extract': 300, 'analyze': 60, 'predict': 180, 'assess': 120, 'review2': 180, 'astra': 580,
                'fable': 580, 'astra_peer': 580, 'fable_peer': 580}
# 1.12's derivation: a send at the output maximum at 100 tokens per second (13.5% below the slowest measured rate),
# plus 40 s for the connection, the prefill and the stream's tail; a stage of its send, the recording and 45 s of work
RATE_1_12, TAIL_1_12, STAGE_WORK_1_12 = 100, 40, 45


class SettingsTests(SimpleTestCase):
    def test_each_reading_pass_fits_the_bounds_its_output_maximum_sets(self):
        """D289's guard (G2-01; W9R-BUILD-LIST B21), read from the module that sends: for each pass, the send deadline
        holds fable_adapter.MAX_TOKENS at 100 tokens per second plus 40 s, the read timeout never cuts before the
        deadline, the stage covers the send, its recording and 45 s of work, and the stage's stale threshold lies above
        the stage. A changed cap or deadline that breaks any of them fails here."""
        from studio import jobs
        from studio.interpretation import fable_adapter

        cap = fable_adapter.MAX_TOKENS / RATE_1_12 + TAIL_1_12
        for purpose, (send, read, kind) in PASSES_1_12.items():
            with self.subTest(purpose=purpose):
                deadline = getattr(settings, send)
                self.assertLessEqual(cap, deadline)
                self.assertLessEqual(getattr(settings, read), deadline)
                self.assertLessEqual(deadline + jobs.LOOP_RECORDING_SECONDS + STAGE_WORK_1_12,
                                     settings.JOB_DEADLINE_SECONDS[kind])
                self.assertLess(settings.JOB_DEADLINE_SECONDS[kind], settings.STALE_RUNNING_SECONDS_BY_KIND[kind])

    def test_the_settings_are_1_12s_literal_assignments(self):
        literals = _settings_literals()
        for purpose, (send, read, kind) in PASSES_1_12.items():
            with self.subTest(purpose=purpose):
                self.assertEqual((literals[send], literals[read], literals['JOB_DEADLINE_SECONDS'][kind],
                                  literals['STALE_RUNNING_SECONDS_BY_KIND'][kind]),
                                 (SEND_1_12, READ_1_12, STAGE_1_12, STALE_R3.get(kind, STALE_1_12)))
                self.assertEqual((getattr(settings, send), getattr(settings, read)), (SEND_1_12, READ_1_12))
        # the per-kind threshold names the reading stages only - the two passes and, since round r3, the question stage
        # (D322 (4): its own rows, tests/v2/test_question_stage.py) - every other stage keeps its deadline and the
        # stale-stage sweep's 600 s
        self.assertEqual(set(literals['STALE_RUNNING_SECONDS_BY_KIND']), {'interpret', 'appraise', 'question'})
        self.assertEqual({kind: seconds for kind, seconds in literals['JOB_DEADLINE_SECONDS'].items()
                          if kind not in ('interpret', 'appraise', 'question')}, OTHER_STAGES)
        self.assertEqual((literals['JOB_DEADLINE_SECONDS']['question'],
                          literals['STALE_RUNNING_SECONDS_BY_KIND']['question']), (1588, 1768))
        self.assertEqual(literals['STALE_RUNNING_SECONDS'], 600)
        # the interpreter's response cap (1.12's last row)
        self.assertEqual(settings.INTERPRETER_MAX_RESPONSE_BYTES, 16 * 1024 * 1024)
        # the derivation the guard reads: 128,000 tokens at 100 per second plus 40 s is the deadline exactly, and the
        # stage is the send, the recording and 45 s
        from studio import jobs

        self.assertEqual(128_000 / RATE_1_12 + TAIL_1_12, SEND_1_12)
        self.assertEqual(SEND_1_12 + jobs.LOOP_RECORDING_SECONDS + STAGE_WORK_1_12, STAGE_1_12)

    def test_the_interpreter_reads_the_existing_anthropic_credential_and_keeps_its_mode_and_replay_settings(self):
        # AMENDMENT-2 1.11 (D275): no interpreter key of its own - the setting is the Fable participant's,
        # ANTHROPIC_CREDENTIALS_FILE - and the mode and replay directory keep their historical settings and variables
        source = (APP / 'cptstudio' / 'settings.py').read_text(encoding='utf-8')
        for line in ("ANTHROPIC_CREDENTIALS_FILE = _env('ANTHROPIC_CREDENTIALS_FILE', '')",
                     "GEMINI_MODE = _env('GEMINI_MODE', 'disabled')",
                     "GEMINI_REPLAY_DIR = _env('GEMINI_REPLAY_DIR', '')",
                     "GEMINI_CREDENTIALS_FILE = _env('GEMINI_CREDENTIALS_FILE', '')"):
            with self.subTest(line=line):
                self.assertEqual(source.count(line), 1)
        credentials = {name for name in _settings_assigned() if 'CREDENTIALS' in name}
        self.assertEqual(credentials, {'CORTI_CREDENTIALS_FILE', 'OPENAI_CREDENTIALS_FILE',
                                       'ANTHROPIC_CREDENTIALS_FILE', 'GEMINI_CREDENTIALS_FILE'})
        # read from the environment when the settings load (a fresh process, synthetic paths only, no file opened)
        script = ('import cptstudio.settings as s\n'
                  'print(repr((s.ANTHROPIC_CREDENTIALS_FILE, s.GEMINI_MODE, s.GEMINI_REPLAY_DIR)))\n')
        base = {'PATH': os.environ.get('PATH', ''), 'PYTHONDONTWRITEBYTECODE': '1',
                'CPT_STUDIO_SECRET_KEY': 'synthetic-settings-check-only'}
        given = {'CPT_STUDIO_ANTHROPIC_CREDENTIALS_FILE': '/run/cpt-studio/anthropic-credentials.env',
                 'CPT_STUDIO_GEMINI_MODE': 'replay',
                 'CPT_STUDIO_GEMINI_REPLAY_DIR': '/app/tests/fixtures/interpretation'}
        for environment, expected in (({}, ('', 'disabled', '')),
                                      (given, ('/run/cpt-studio/anthropic-credentials.env', 'replay',
                                               '/app/tests/fixtures/interpretation'))):
            with self.subTest(environment=sorted(environment)):
                completed = subprocess.run([sys.executable, '-c', script], cwd=APP, env={**base, **environment},
                                           capture_output=True, text=True, timeout=60)
                self.assertEqual(completed.returncode, 0, completed.stderr)
                self.assertEqual(completed.stdout.strip(), repr(expected))


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
    # settle's closed lists, moved here with its records (DECISIONS D229; FINAL-V2 1.7, 3.2.3's coherence table, 3.2.6)
    ct.ClaimRole: ('claim', 'control', 'pair_control', 'completeness', 'completeness_control'),
    ct.PairOutcome: ('established', 'incoherent', 'uninformative', 'contradicted', 'qualified', 'unclear', 'detached',
                     'missing', 'control_missing'),
    ct.HealthRefusal: ('control_acceptance', 'establishment', 'completeness'),
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
    qualified verdict that names no qualifier after those that name one): DECISIONS D186. AMENDMENT-2 4.3.2 adds
    slot_overfull to row 4, right after reference_invalid."""
    qualifiers = DESIGN_LISTS[ct.Qualifier]
    return (('contradicted_by_pass1', 'doubt_stated', 'doubt_unclear', 'silent',
             'shape_inconsistent', 'unit_unknown', 'words_not_in_units', 'words_not_bounded', 'units_not_consecutive',
             'source_too_long', 'anchor_words', 'reference_invalid', 'slot_overfull')
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

    def test_slot_overfull_is_row_4s_reason_right_after_reference_invalid_and_integritys(self):
        # AMENDMENT-2 4.3.2: the reader's item-level finding on every fact of a single-valued slot holding more than
        # one joins the closed list in row 4, after REFERENCE_INVALID (I4's) and before G1's geometry reasons
        from studio.interpretation.contract import settle

        members = list(ct.Reason)
        at = members.index(ct.Reason.SLOT_OVERFULL)
        self.assertEqual(ct.Reason.SLOT_OVERFULL.value, 'slot_overfull')
        self.assertEqual(members[at - 1:at + 2],
                         [ct.Reason.REFERENCE_INVALID, ct.Reason.SLOT_OVERFULL, ct.Reason.GEOMETRY_STATEMENT])
        self.assertEqual(ct.Reason('slot_overfull'), ct.Reason.SLOT_OVERFULL)
        # 4.3.5: in none of settle's geometry, literal and consistency tables, so row 4 reads it as integrity's ("an
        # unforeseen reason fails integrity"), and settle's order puts it where the closed list does
        self.assertNotIn(ct.Reason.SLOT_OVERFULL,
                         settle.GEOMETRY_REASONS | settle.LITERAL_REASONS | settle.CONSISTENCY_REASONS)
        self.assertEqual(settle.ordered({ct.Reason.GEOMETRY_STATEMENT, ct.Reason.SLOT_OVERFULL,
                                         ct.Reason.REFERENCE_INVALID}),
                         (ct.Reason.REFERENCE_INVALID, ct.Reason.SLOT_OVERFULL, ct.Reason.GEOMETRY_STATEMENT))


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
    # DECISIONS D229 (w34 O4 and O5): settle's stored claim and verification report records, as settle defined them
    ct.Usage: ('prompt', 'candidates', 'thoughts', 'total', 'cached', 'tool_use_prompt'),
    ct.Usages: ('interpretation', 'appraisal'),
    ct.Health: ('pairs', 'not_rejected', 'claims', 'established', 'verdicts', 'missing', 'refused'),
    ct.Coherence: ('established', 'incoherent', 'uninformative', 'contradicted', 'qualified', 'unclear', 'detached',
                   'missing', 'control_missing'),
    ct.DoubtApplied: ('index', 'about', 'basis', 'objects', 'malformed', 'applied', 'unlisted'),
    ct.Dropped: ('units', 'what', 'kind', 'session', 'event'),
    ct.UnlistedReport: ('kept', 'dropped'),
    ct.Report: ('counts', 'reasons', 'doubts', 'health', 'coherence', 'unlisted', 'usage'),
    ct.StoredVerdict: ('verdict', 'attached', 'qualifiers', 'evidence'),
    ct.StoredClaim: ('id', 'role', 'template', 'subject', 'attribute', 'value', 'units', 'content', 'verdict'),
    ct.StoredCompleteness: ('appraisal', 'result', 'reasons'),
    et.Id: ('family', 'number'),
    et.IsoDate: ('value', 'precision'),
    et.Cited: ('link', 'units', 'at'),  # DECISIONS D188
    # D188's three fields, then AMENDMENT-2 4.3.3's negated_values
    et.Fact: ('result', 'value', 'state', 'options', 'reasons', 'spans', 'cited', 'inherited_from', 'counter',
              'negated_values'),
    et.Anchor: ('units', 'kind_words', 'status_words'),
    et.UnlistedStatement: ('units', 'what', 'kind', 'session'),
    # FINAL-V2 4.1 R's eleven, then round r3's (DESIGN-v2 f.1, DECISIONS D306-D308; restated at round r3's integration):
    # the established question answers folded in on R_q, the fact pass's controlled facts and R_q's base, R_base
    et.FactSet: ('encounter', 'people', 'sections', 'sessions', 'anatomy', 'lesions', 'events', 'anchors', 'unlisted',
                 'pair_controls', 'completeness', 'independent', 'unlisted_independent', 'off_lesion', 'distinct',
                 'absorbed', 'controlled', 'base'),
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
    ct.Usage: {'prompt': int, 'candidates': int, 'thoughts': int, 'total': int, 'cached': int, 'tool_use_prompt': int},
    ct.Usages: {'interpretation': ct.Usage, 'appraisal': ct.Usage},
    ct.Health: {'pairs': int, 'not_rejected': int, 'claims': int, 'established': int, 'verdicts': int, 'missing': int,
                'refused': tuple[ct.HealthRefusal, ...]},
    ct.Coherence: {name: int for name in ('established', 'incoherent', 'uninformative', 'contradicted', 'qualified',
                                          'unclear', 'detached', 'missing', 'control_missing')},
    ct.DoubtApplied: {'index': int, 'about': ct.DoubtAbout, 'basis': ct.DoubtBasis, 'objects': tuple[str, ...],
                      'malformed': bool, 'applied': int, 'unlisted': bool},
    ct.Dropped: {'units': tuple[str, ...], 'what': ct.UnlistedWhat, 'kind': ct.Kind | None, 'session': str | None,
                 'event': str},
    ct.UnlistedReport: {'kept': int, 'dropped': tuple[ct.Dropped, ...]},
    ct.Report: {'counts': Mapping[ct.Attribute, Mapping[ct.Result, int]], 'reasons': Mapping[ct.Reason, int],
                'doubts': tuple[ct.DoubtApplied, ...], 'health': ct.Health, 'coherence': ct.Coherence,
                'unlisted': ct.UnlistedReport, 'usage': ct.Usages},
    ct.StoredVerdict: {'verdict': ct.VerdictValue, 'attached': ct.Attached, 'qualifiers': tuple[ct.Qualifier2, ...],
                       'evidence': tuple[str, ...]},
    ct.StoredClaim: {'id': str, 'role': ct.ClaimRole, 'template': str, 'subject': str, 'attribute': ct.Attribute,
                     'value': str, 'units': tuple[str, ...], 'content': str, 'verdict': ct.StoredVerdict | None},
    ct.StoredCompleteness: {'appraisal': ct.Appraisal, 'result': ct.Result, 'reasons': tuple[ct.Reason, ...]},
    et.Id: {'family': et.IdFamily, 'number': int},
    et.IsoDate: {'value': datetime.date, 'precision': ct.Precision},
    et.Cited: {'link': ct.Link, 'units': ct.Span, 'at': ct.Span | None},
    et.Fact: {'result': ct.Result, 'value': _VALUE | None, 'state': ct.FactState | None, 'options': tuple[_VALUE, ...],
              'reasons': tuple[ct.Reason, ...], 'spans': tuple[ct.Span, ...], 'cited': tuple[et.Cited, ...],
              'inherited_from': et.Id | None, 'counter': tuple[ct.Span, ...], 'negated_values': tuple[_VALUE, ...]},
    et.Anchor: {'units': tuple[ct.Span, ...], 'kind_words': ct.Span | None, 'status_words': ct.Span | None},
    et.UnlistedStatement: {'units': tuple[ct.Span, ...], 'what': ct.UnlistedWhat, 'kind': ct.Kind | None,
                           'session': et.Id | None},
    et.FactSet: {'encounter': _FACTS, 'people': _OBJECTS, 'sections': _OBJECTS, 'sessions': _OBJECTS,
                 'anatomy': _OBJECTS, 'lesions': _OBJECTS, 'events': _OBJECTS, 'anchors': Mapping[et.Id, et.Anchor],
                 'unlisted': tuple[et.UnlistedStatement, ...],
                 'pair_controls': Mapping[tuple[et.Id, ct.Attribute, _VALUE], bool],
                 'completeness': Mapping[et.Id, ct.Result],
                 # round r3 (DESIGN-v2 f.1): Q-REL's pairs set apart, its unlisted ones by entry index, Q-ONLESION's (act,
                 # lesion), Q-LESION's lesion pairs, Q-ABSORB's entry indices, the controlled (subject, attribute) facts
                 # the calibration pool reads (DESIGN-v2 b.9), and R_base
                 'independent': frozenset[tuple[et.Id, et.Id]], 'unlisted_independent': frozenset[tuple[int, et.Id]],
                 'off_lesion': frozenset[tuple[et.Id, et.Id]], 'distinct': frozenset[tuple[et.Id, et.Id]],
                 'absorbed': frozenset[int], 'controlled': frozenset[tuple[et.Id | None, ct.Attribute]],
                 'base': et.FactSet | None},
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
    usage = ct.Usage(10, 2, 3, 15, 0, 0)
    usages = ct.Usages(usage, ct.Usage(20, 4, 6, 30, 0, 0))
    health = ct.Health(4, 1, 6, 5, 10, 0, (ct.HealthRefusal.COMPLETENESS,))
    coherence = ct.Coherence(5, 1, 0, 0, 0, 0, 0, 0, 0)
    doubt_applied = ct.DoubtApplied(0, ct.DoubtAbout.PERFORMER, ct.DoubtBasis.UNCLEAR, ('E1',), False, 1, False)
    dropped = ct.Dropped(('S2',), ct.UnlistedWhat.ACT, ct.Kind.SNARE, 'X1', 'E1')
    unlisted_report = ct.UnlistedReport(1, (dropped,))
    stored_verdict = ct.StoredVerdict(ct.VerdictValue.SUPPORTS, ct.Attached.YES, (), ('S1',))
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
        ct.Usage: usage,
        ct.Usages: usages,
        ct.Health: health,
        ct.Coherence: coherence,
        ct.DoubtApplied: doubt_applied,
        ct.Dropped: dropped,
        ct.UnlistedReport: unlisted_report,
        ct.Report: ct.Report({ct.Attribute.KIND: {ct.Result.SUPPORTED: 1}}, {ct.Reason.SILENT: 2}, (doubt_applied,),
                             health, coherence, unlisted_report, usages),
        ct.StoredVerdict: stored_verdict,
        ct.StoredClaim: ct.StoredClaim('K1', ct.ClaimRole.CLAIM, 'act.kind', 'E1', ct.Attribute.KIND, 'snare', ('S1',),
                                       'f' * 64, stored_verdict),
        ct.StoredCompleteness: ct.StoredCompleteness(appraisal, ct.Result.SUPPORTED, ()),
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
        # DECISIONS D188 adds cited, inherited_from and counter, and AMENDMENT-2 4.3.3 negated_values, each empty by
        # default: 4.1's six-field Fact builds as before, and the four fields carry what they are given
        span, cited = ct.Span(0, 4), et.Cited(ct.Link.STATEMENT, ct.Span(0, 9), None)
        six = et.Fact(ct.Result.SUPPORTED, ct.Performer.DOCUMENTING_TEAM, ct.FactState.SUPPORTED, (), (), (span,))
        self.assertEqual((six.cited, six.inherited_from, six.counter, six.negated_values), ((), None, (), ()))
        nine = et.Fact(ct.Result.SUPPORTED, ct.Performer.DOCUMENTING_TEAM, ct.FactState.SUPPORTED, (), (), (span,),
                       (cited,), N2, (ct.Span(5, 9),))
        self.assertEqual((nine.cited, nine.inherited_from, nine.counter), ((cited,), N2, (ct.Span(5, 9),)))
        self.assertEqual(nine.negated_values, ())
        self.assertNotEqual(nine, six)
        self.assertEqual(dataclasses.replace(nine, cited=(), inherited_from=None, counter=()), six)
        ten = dataclasses.replace(nine, negated_values=(ct.Performer.OTHER_CLINICIAN,))
        self.assertEqual(ten.negated_values, (ct.Performer.OTHER_CLINICIAN,))
        self.assertNotEqual(ten, nine)
        self.assertEqual(dataclasses.replace(ten, negated_values=()), nine)

    def test_an_overfilled_slot_is_one_fact_holding_its_written_values_and_its_negated_ones(self):
        # AMENDMENT-2 4.3.3: the one fact an overfilled single-valued slot is read as - unresolved, contradicted, value
        # None, reason slot_overfull, options every value the slot's facts wrote once each in written order, spans every
        # written fact's - carries in negated_values the written values whose fact was negated (A-v2's shape: one
        # supported device, two negated); a reader of what pass 1 stated reads the options less them (4.3.3 b)
        written = (ct.Device.COLD_SNARE, ct.Device.HOT_SNARE, ct.Device.FORCEPS)
        spans = (ct.Span(0, 9), ct.Span(10, 19), ct.Span(20, 29))
        merged = et.Fact(ct.Result.UNRESOLVED, None, ct.FactState.CONTRADICTED, written, (ct.Reason.SLOT_OVERFULL,),
                         spans, negated_values=written[1:])
        self.assertEqual((merged.options, merged.negated_values), (written, written[1:]))
        self.assertEqual(tuple(value for value in merged.options if value not in merged.negated_values),
                         (ct.Device.COLD_SNARE,))
        self.assertEqual(merged.reasons, (ct.Reason.SLOT_OVERFULL,))
        # every written value is supported (A-v6's shape): nothing is negated; a date slot holds its written dates (T9)
        supported = dataclasses.replace(merged, options=(ct.Landmark.CECUM, ct.Landmark.ILEUM), negated_values=())
        self.assertEqual(supported.negated_values, ())
        dates = (et.IsoDate(datetime.date(2026, 11, 2), ct.Precision.DAY),
                 et.IsoDate(datetime.date(2026, 11, 9), ct.Precision.DAY))
        dated = dataclasses.replace(merged, options=dates, negated_values=dates[:1])
        self.assertEqual(dated.negated_values, dates[:1])
        # frozen as every record field is
        with self.assertRaises(dataclasses.FrozenInstanceError):
            setattr(merged, 'negated_values', ())

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
