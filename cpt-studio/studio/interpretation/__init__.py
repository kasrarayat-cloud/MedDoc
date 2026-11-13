"""Gemini as CPT Studio's interpreter of documented clinical events (owner directive 2026-11-09; design/FINAL.md as
design/ADJUDICATION.md amends it): one persisted event inventory per revision, read by every new-path consumer.

This module holds the labels only, so importing the package loads nothing else. The contract's parts are its modules:
prompt (what Gemini is asked), schema (the shape it answers in), read (the strict reader of one answer), store (the
persisted inventory's versioned reader). Nothing in this package imports studio.gi except the reference tables
gi.profiles and gi.catalogue (D17); these four import none of it.

The versions (contract 1, with FINAL C4's two columns):
- INTERPRETATION_VERSION names what is asked and how an answer is structurally read: prompt.INSTRUCTIONS,
  schema.LOCAL_SCHEMA, schema.RESPONSE_SCHEMA, schema.BOUNDS and read.py's rules. A changed byte of the first three
  changes the request's sha256 and needs a new version; BOUNDS and read.py's rules are read, never sent, and change what
  is read (a new version once the product has recorded answers under this one; DECISIONS D32 raised two bounds before
  that, schema.py). The three pins beside it are checked whenever a request is built (prompt.check_pins) or an answer
  is read (read.check_pin), so whatever carries this label asks and reads exactly this.
- INVENTORY_VERSION names normalization, verification, the lexicons and the identity and pairing rules. A new one
  re-reads a stored answer into a new EventInventory row with no new request.
- LABEL names the pair in the verification report. EventInventory stores the two versions in two columns (FINAL 4.1).

Design v2 (docs/gemini-migration/FINAL-V2.md 1.1 and 2.5, adopted as DECISIONS D178; step 0b of its 8.1) adds its labels
beside these under new names: the suffix _V2 where a v1 name exists, a plain name where none does. v1's names and values
stay byte-identical, because the 17 retired v1 modules and their tests read them for good (FINAL-V2 5.0) and jobs.py
calls v1 until step 5b switches it. v2's code lives in the two subpackages, contract and engine; this module imports
neither, and still loads nothing else. is_new_assessment and is_new_context dispatch by version family, so @1 and @2
rows alike are new-path rows.
"""
from __future__ import annotations

INTERPRETATION_VERSION = 'gemini-events@1'
# sha256 of prompt.INSTRUCTIONS (UTF-8) and of the canonical bytes of schema.LOCAL_SCHEMA and schema.RESPONSE_SCHEMA
# (schema.sha256_of). A changed byte of any of them needs a new INTERPRETATION_VERSION and new pins.
INSTRUCTIONS_SHA256 = '00da58c5a8f0f5deca4ee0dd8259bb7065ee6dd551e408e3257bd33b4eee14b1'
LOCAL_SCHEMA_SHA256 = '93574cacb4dc3d9fb0c3ed7789a8c2f7c708bf94176b53f1dd850fcd0214ccc3'
RESPONSE_SCHEMA_SHA256 = '7bb3057d724012910b4210272c31480eacb6fc6fe6dbacbce4415c61592d2537'

INVENTORY_VERSION = 'gemini-inventory@1'
LABEL = f"{INTERPRETATION_VERSION}+{INVENTORY_VERSION.removeprefix('gemini-')}"  # gemini-events@1+inventory@1

ADAPTER_VERSION = 'gemini-generate@cptstudio-1'  # ProviderRun.adapter_version (at most 40 characters)
MODEL = 'gemini-4-argon'  # D13: named by the URL; a response's modelVersion must equal it exactly
PROVIDER = 'gemini'  # ProviderRun.provider; an operator field, never shown to a customer (D22)
PURPOSE = 'interpretation'  # ProviderRun.purpose (at most 16 characters)
JOB_KIND = 'interpret'  # Job.kind (at most 10 characters)
ENGINE_VERSION = 'cpt-studio-events@1'  # Assessment.engine_version of a new-path assessment
CONTEXT_VERSION = 'gemini-context@1'  # EncounterContext.version derived from an inventory (D6)
ROUTING_VERSION = 'gemini-routing@1'  # RoutingRun.version of the derived stand-in (D6)

# --- design v2 (FINAL-V2 1.1): what each label names, and what a change of it needs, is 1.1's table -------------------
INTERPRETATION_VERSION_V2 = 'gemini-events@2'  # pass 1: instruction, schemas, bounds, read rules, the segmentation rule
# pass 2: instruction, schemas, bounds (the per-request claim bound), read rules, claim templates, CLAIMED (by sha), the
# CONTROLS generator and its tables, the seed rule, the health thresholds
APPRAISAL_VERSION = 'gemini-appraisal@1'
INVENTORY_VERSION_V2 = 'gemini-inventory@2'  # the checks, inheritance, the settle table, the doubt mapping, the reasons
REQUIREMENTS_VERSION = 'cpt-requirements@1'  # the requirement table, its read-sets, the CLAIMED table, RANK
ENGINE_VERSION_V2 = 'cpt-studio-events@2'  # Assessment.engine_version: the engine and event_coding@2
CONTEXT_VERSION_V2 = 'gemini-context@2'  # EncounterContext.version derived by engine/derive.py
ROUTING_VERSION_V2 = 'gemini-routing@2'  # RoutingRun.version of engine/derive.py's stand-in
ADAPTER_VERSION_V2 = 'gemini-generate@cptstudio-2'  # ProviderRun.adapter_version: two request kinds (27 of 40)
# EventInventory.interpretation_version of a v2 row: the pair asked and read, so the existing unique key holds per
# appraisal version - gemini-events@2/appraisal@1, 27 of 40 characters
INTERPRETATION_PAIR = f"{INTERPRETATION_VERSION_V2}/{APPRAISAL_VERSION.removeprefix('gemini-')}"
APPRAISAL_PURPOSE = 'appraisal'  # ProviderRun.purpose of pass 2 (9 of 16 characters; pass 1 keeps PURPOSE)
APPRAISE_JOB_KIND = 'appraise'  # Job.kind of pass 2's stage (8 of 10 characters; pass 1 keeps JOB_KIND)

# --- design v2's pins (FINAL-V2 2.5) ----------------------------------------------------------------------------------
# The sha256 of each pinned object, checked when a request is built and when an answer is read (v1's prompt.check_pins
# and read.check_pin pattern); an empty pin refuses both. The integration owner writes them in one commit after the
# wave's repairs, each computed by its step's own function on the merged tree and checked by that step's pin test
# (DECISIONS D202, arbiter triage INT-5: written after build waves 1 and 2). The health thresholds' pin stays empty
# until step 8 sets them from D3. Until the first recording under a label a changed object needs only its pin
# recomputed; after it, a changed byte of a pass-1 object needs gemini-events@3, of a pass-2 object gemini-appraisal@2.
# pass 1 (INTERPRETATION_VERSION_V2):
# contract/extract_prompt.INSTRUCTIONS_2 (UTF-8): step 2a
INSTRUCTIONS_SHA256_V2 = '244858ab0e2f57c98d4d2f0e7ad8d5360e88e9d90bff543b4f489831c7c7ae54'
# canonical bytes of contract/extract_schema.LOCAL_SCHEMA_2 (step 1b): step 2a
LOCAL_SCHEMA_SHA256_V2 = '7cd387041de317825f371415070bcee1703be0d9022c92bf77580f59dda3d04c'
# canonical bytes of contract/extract_schema.RESPONSE_SCHEMA_2 (step 1b): step 2a
RESPONSE_SCHEMA_SHA256_V2 = 'bcb7fce8f1fa0b28c5fb8ea7514ba22f14ce06f18d1f557b16b92798f1109cab'
# the segmentation rule's constants, contract/segment.py (step 1a): step 2a
SEGMENTATION_SHA256 = '41d2245ada69f2a573d0354486323d9f30e00fef7091f531e2e0541a11af8e78'
# pass 2 (APPRAISAL_VERSION):
# contract/appraise_prompt's instruction (UTF-8): step 2c
APPRAISAL_INSTRUCTIONS_SHA256 = '2259b699306d13d174a4e815beba40cbcf9bbedd0c14e21699ebdcebfdc081b0'
# canonical bytes of contract/appraise_schema's LOCAL schema: step 2c
APPRAISAL_LOCAL_SCHEMA_SHA256 = '526dd4e4116c07ed3e1431759a47ac79d4a4d3e7aba81c3133933abe5da46cbf'
# canonical bytes of contract/appraise_schema's RESPONSE schema: step 2c
APPRAISAL_RESPONSE_SCHEMA_SHA256 = 'fc83346270c6bc165baba78ed8a731132c7e90f172ad22853b100d085ffbd275'
# claims.TEMPLATES: step 2c
TEMPLATES_SHA256 = '9efd3e1d2d1fd8124f3bb4c54169e5ede90dc5a4d7bdd7a7f0496927264a7ce0'
# claims.STATEMENT_TEMPLATES: step 2c
STATEMENT_TEMPLATES_SHA256 = '3880e4af3eefbdbccf0c5bb8e4a099df1d50268b485e991f46db7b8f3a19e162'
# the claims.CONTROLS generator with its tables (KIND_SIBLINGS, SESSION_SIBLINGS, CONTRAST_PLACES, the pair-control
# and completeness rules, UNCONTROLLED): step 2c
CONTROLS_SHA256 = '19fbf9621e4f3569170e0ed27a460fd4b172b7596b8d689c1a9c0d0c021db144'
# engine/requirements.CLAIMED, its sha computed by step 1f: step 2c hands it with its pins
CLAIMED_SHA256 = '8c95246d6ff8a260b344bb5a52e25f51ac744343ed8ebe5887764ad7e5cd7b81'
HEALTH_THRESHOLDS_SHA256 = ''  # the health thresholds of 3.2.6 (contract/settle.py, step 3a), set from D3: step 8
# the per-request claim bound of 1.8 (step 2c; 640 claims), recomputed from D2: step 8
CLAIM_BOUND_SHA256 = '58f544bee79e592b0a40c01e24884995f2e9dd4dd9ff4c16aeec104dcf691f02'


def _family(version: str) -> str:
    return version.partition('@')[0] + '@'


def is_new_assessment(assessment: object) -> bool:
    """True for an assessment the events engine made, of any cpt-studio-events@ version, as readers.for_assessment
    dispatches (FINAL 8.2); False for every legacy assessment, and for anything with no string engine_version. A later
    events version is still a new-path row: it reaches the event reader, which refuses a version it does not know,
    never the legacy reader."""
    version = getattr(assessment, 'engine_version', None)
    return isinstance(version, str) and version.startswith(_family(ENGINE_VERSION))


def is_new_context(context: object) -> bool:
    """True for a context derived from an event inventory, of any gemini-context@ version (stage_assess's dispatch,
    FINAL 6.7); False for every legacy context, and for anything with no string version."""
    version = getattr(context, 'version', None)
    return isinstance(version, str) and version.startswith(_family(CONTEXT_VERSION))
