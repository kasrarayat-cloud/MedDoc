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


def _family(version: str) -> str:
    return version.partition('@')[0] + '@'


def is_new_assessment(assessment) -> bool:
    """True for an assessment the events engine made, of any cpt-studio-events@ version, as readers.for_assessment
    dispatches (FINAL 8.2); False for every legacy assessment, and for anything with no string engine_version. A later
    events version is still a new-path row: it reaches the event reader, which refuses a version it does not know,
    never the legacy reader."""
    version = getattr(assessment, 'engine_version', None)
    return isinstance(version, str) and version.startswith(_family(ENGINE_VERSION))


def is_new_context(context) -> bool:
    """True for a context derived from an event inventory, of any gemini-context@ version (stage_assess's dispatch,
    FINAL 6.7); False for every legacy context, and for anything with no string version."""
    version = getattr(context, 'version', None)
    return isinstance(version, str) and version.startswith(_family(CONTEXT_VERSION))
