"""The shape pass 2 answers in (gemini-appraisal@1; docs/gemini-migration/FINAL-V2.md 2.4 and 1.8 [R:MO-3]; step 2c of
8.1): LOCAL_SCHEMA, RESPONSE_SCHEMA derived from it mechanically, and BOUNDS.

**LOCAL_SCHEMA is the source**, written in v1's LOCAL form (1.4): every object requires every property it declares, in
the design's order, and forbids any other; no nullable union; the types are object, array and string. It is 2.4's
APPRAISAL, field for field:
- ``verdicts``: one per claim - ``claim`` (the claim's id, K1..), ``verdict`` (VERDICTS: supports, contradicts,
  qualified, unclear), ``attached`` (ATTACHED: yes, no, unclear), ``qualifiers`` (QUALIFIERS_2) and ``evidence`` (the
  unit ids relied on, no words);
- ``unlisted``: every statement of an act, a denial of one or a doubt about one that no card's claims describe -
  ``units``, ``what`` (act, denial or doubt), ``kind`` (a KINDS value, or '' when the document names none) and
  ``session`` (a session card's id, or '' when the document does not say).
RESPONSE_SCHEMA, what generationConfig.responseSchema carries, is ``jsonschema.gemini_schema(LOCAL_SCHEMA)``: the one
generator step 0b copied from v1 (contract/jsonschema.py), so the two cannot drift. Gemini's form is a hint to the model
and never trusted: contract/appraise_read.py validates every answer against LOCAL_SCHEMA.

**BOUNDS** (1.8, read and never sent; a whole answer outside them is refused, named by count, never truncated):
evidence 8 unit ids per verdict; unlisted 32 entries; and the verdicts at most one per claim of the request - a count
that is the request's own (at most claims.CLAIM_BOUND, 640), so appraise_read takes it from the claim set. Within that
count a missing, repeated or unknown claim id is an item-level finding (3.2.4), never a refusal.

Everything here belongs to APPRAISAL_VERSION (gemini-appraisal@1): a changed byte of LOCAL_SCHEMA or RESPONSE_SCHEMA
changes what is asked or read. The integration owner writes the two shas (APPRAISAL_LOCAL_SCHEMA_SHA256,
APPRAISAL_RESPONSE_SCHEMA_SHA256) in studio/interpretation/__init__.py after the wave's last repair; until the first
recording under the label a changed schema needs only its pins recomputed, after it gemini-appraisal@2 and new pins
(2.5; DECISIONS D202).

Pure: imports only the standard library and the contract's types and jsonschema; touches no document text; holds no
word list (every module-level collection holds enumeration members or numbers; the schema is built in a function).
"""
from __future__ import annotations

from collections.abc import Mapping
from enum import Enum, unique
from types import MappingProxyType
from typing import Any

from studio.interpretation.contract import jsonschema
from studio.interpretation.contract.types import Attached, Kind, Qualifier2, UnlistedWhat, VerdictValue


@unique
class Bound(Enum):
    """What one number of BOUNDS bounds (1.8). VERDICTS is the request's own claim count (not in BOUNDS)."""
    VERDICTS = 'verdicts'  # at most one verdict per claim of the request
    EVIDENCE = 'evidence'  # unit ids in one verdict's evidence
    UNLISTED = 'unlisted'  # entries in unlisted


# 1.8, number for number (VERDICTS is the request's claim count, read from the claim set).
BOUNDS: Mapping[Bound, int] = MappingProxyType({Bound.EVIDENCE: 8, Bound.UNLISTED: 32})


def _local_schema() -> dict[str, Any]:
    """LOCAL_SCHEMA, built fresh: no node is shared, so the derived schema and every copy are independent."""

    def string() -> dict[str, Any]:
        return {'type': 'string'}

    def strings() -> dict[str, Any]:
        return {'type': 'array', 'items': string()}

    def enum(values: type[Enum], *, empty: bool = False) -> dict[str, Any]:
        """An enumeration's values in its order; with ``empty``, '' after them (unlisted.kind when none is named)."""
        return {'type': 'string', 'enum': [member.value for member in values] + ([''] if empty else [])}

    def obj(properties: dict[str, Any]) -> dict[str, Any]:
        """Every field required and nothing else allowed, in the order given."""
        return {'type': 'object', 'additionalProperties': False, 'required': list(properties),
                'properties': properties}

    verdict = obj({'claim': string(), 'verdict': enum(VerdictValue), 'attached': enum(Attached),
                   'qualifiers': {'type': 'array', 'items': enum(Qualifier2)}, 'evidence': strings()})
    unlisted = obj({'units': strings(), 'what': enum(UnlistedWhat), 'kind': enum(Kind, empty=True),
                    'session': string()})
    return obj({'verdicts': {'type': 'array', 'items': verdict}, 'unlisted': {'type': 'array', 'items': unlisted}})


LOCAL_SCHEMA: dict[str, Any] = _local_schema()


def _local_schema_q() -> dict[str, Any]:
    """Round r3's LOCAL_SCHEMA_Q (DECISIONS D306-D308; build-v2/a2b/r3 DESIGN-v2 c.2): a question request's
    structured-output schema - LOCAL_SCHEMA with each verdict carrying ``quotes`` (the proof: passages of the document's
    own words), required like every field. LOCAL_SCHEMA itself is untouched (I-FACT). How many quotes count, and how
    long each may be, is the reader's item-level bound (appraise_read: QUOTE_MAX_CHARS, and contract/proof's QUOTES_MAX
    - DECISIONS D318 (1)), never a schema keyword: the schema stays the one the probe sent."""
    schema = _local_schema()
    verdict = schema['properties']['verdicts']['items']
    verdict['properties']['quotes'] = {'type': 'array', 'items': {'type': 'string'}}
    verdict['required'].append('quotes')
    return schema


LOCAL_SCHEMA_Q: dict[str, Any] = _local_schema_q()
# DECISIONS D318 (1): QUOTES_MAX, THE flood cap of a question verdict's quotes - ONE constant, held here beside the schema
# whose ``quotes`` it bounds, read by contract/appraise_read (quotes_bound) and contract/proof (locate), and rendered into
# the question instruction (contract/question_claims.PROOF); never a schema keyword (the schema stays the one the probe
# sent). Every quote must already lie inside the claim's own passages, so a flood of the document's other words voids a
# proof whatever its size; the cap only bounds a degenerate answer and the locator's search. 8 = twice the most quotes
# Fable gave one verdict at effort max in step 1 long (r3-probe-2: 4), and room for every passage a form may draw on -
# its two required objects plus a frame value passage or a section head, or a reach's two alternatives: at most 4 - to be
# quoted per unit across a sentence a line break splits in two (4 x 2).
QUOTES_MAX = 8

# What generationConfig.responseSchema carries: derived, never written by hand.
RESPONSE_SCHEMA: dict[str, Any] = jsonschema.gemini_schema(LOCAL_SCHEMA)
