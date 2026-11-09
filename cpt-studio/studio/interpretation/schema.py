"""The shape Gemini answers in (design/contract.md 3, as design/ADJUDICATION.md C-7 and C-15 amend it): the enumerations,
LOCAL_SCHEMA, RESPONSE_SCHEMA and BOUNDS of gemini-events@1.

LOCAL_SCHEMA is the source. It is written in the lowercase form CPT Studio validates itself
(participants.reading.schema_error): the types object, array, string and integer; every object forbids additional
properties and requires every property it declares; there is no nullable union, so an absent value is "", [] or the
enumeration's not-stated value. RESPONSE_SCHEMA - what generationConfig.responseSchema carries - is derived from it by
gemini_schema, mechanically: each type upper-cased, additionalProperties dropped, properties, required, items and enum
kept, and propertyOrdering set to each object's declaration order. One generator, so the two cannot drift. Gemini's form
is a hint to the model and is never trusted: read.py validates every answer against LOCAL_SCHEMA (D13).

There is no free-text field. Every string an answer gives is an enumeration value, an id, an ISO date, a copy of the
document's text, or words copied from inside one (contract 3.2, P9).

The enumerations are the contract's lists, verbatim and in their order (contract 3.1), with the adjudication's additions:
- SCOPES gains ``exceptive`` before ``unknown`` (C-7): a statement such as "no further / no other / no additional
  intervention", which covers only acts beyond those the document reports, never pairs with a positive act of its kind
  and never excludes one. Gemini assigns it, and its scope words are verified as words, never through a lexicon.
- LANDMARKS gains ``right_colon``, ``left_colon``, ``proximal_colon`` and ``distal_colon`` right after ``colon``, the
  regions before the segments they contain (C-15). Which segments each contains is a containment rule of lexicon.py
  (contract 1 and appendix B), versioned by INVENTORY_VERSION, not by this module.

Everything here is part of gemini-events@1: a changed byte of LOCAL_SCHEMA or RESPONSE_SCHEMA changes the request's
sha256 and needs a new INTERPRETATION_VERSION and new pins (studio/interpretation/__init__.py); a changed bound changes
what is read and needs one too.
"""
from __future__ import annotations

import hashlib
import json
from types import MappingProxyType

# --- the enumerations (contract 3.1; ADJUDICATION C-7, C-15) ------------------------------------------------------------

# gi.profiles' family slugs without the "gi." prefix; other_gi is gi.other and not_gi is gi.unsupported.
PROCEDURES = ('office_em', 'egd', 'enteroscopy', 'colonoscopy', 'flex_sig', 'eus', 'ercp', 'capsule', 'motility',
              'reflux', 'anorectal', 'feeding_tube', 'sedation', 'em_other', 'other_gi', 'not_gi', 'unknown')
# The catalogue's act kinds less the legacy ``specimen``, plus ``examination``, the umbrellas ``removal`` and
# ``intervention``, and ``other``.
KINDS = ('examination', 'em_visit', 'em_prolonged', 'biopsy', 'hot_biopsy', 'snare', 'emr', 'esd', 'removal', 'ablation',
         'bleeding_control', 'clip', 'tattoo', 'injection', 'band_ligation', 'dilation', 'stent', 'stent_removal',
         'stent_exchange', 'foreign_body', 'decompression', 'tube_placement', 'tube_replacement', 'peg', 'myotomy',
         'fundoplication', 'fna', 'drainage', 'cannulation', 'sphincterotomy', 'stone_extraction', 'lithotripsy',
         'cholangioscopy', 'pressure_measurement', 'capsule_study', 'manometry', 'ph_monitoring', 'rectal_sensation',
         'balloon_expulsion', 'moderate_sedation', 'intervention', 'other')
DEVICES = ('not_stated', 'endoscope', 'cold_snare', 'hot_snare', 'snare', 'cold_forceps', 'hot_forceps', 'forceps',
           'needle', 'injection', 'balloon', 'wire_bougie', 'bougie', 'clip', 'band', 'argon_plasma', 'radiofrequency',
           'cryotherapy', 'thermal_probe', 'electrocautery', 'stent', 'basket', 'extraction_balloon', 'sphincterotome',
           'lithotripter', 'cholangioscope', 'capsule', 'catheter', 'manual', 'other')
TIMES = ('current_encounter', 'earlier_encounter', 'future', 'unknown')
PERFORMERS = ('documenting_team', 'other_clinician', 'other_facility', 'unknown')
STATUSES = ('performed', 'attempted_not_completed', 'planned', 'not_performed', 'uncertain')
SCOPES = ('not_applicable', 'single_target', 'all_of_kind', 'listed_targets', 'exceptive', 'unknown')
PURPOSES = ('not_stated', 'diagnostic', 'removal', 'lift_for_resection', 'marking', 'hemostasis', 'prophylaxis',
            'treatment', 'access', 'other')
COMPLETIONS = ('complete', 'incomplete', 'not_stated')
EM_BASES = ('total_time', 'medical_decision_making', 'not_stated')
SEPARATE = ('stated', 'denied', 'not_stated')
DATE_STATES = ('stated', 'several', 'not_stated')
DATE_ROLES = ('this_encounter', 'birth', 'other_occurrence', 'other_document', 'report_time', 'unclear')
ANATOMY_STATES = ('absent', 'altered')
MULTIPLICITY = ('single', 'group', 'unknown')
# services.ANATOMY's canonical names in snake case, plus neo_terminal_ileum, anastomosis, stoma and pouch (contract 3.1),
# plus the four colon regions (C-15).
LANDMARKS = ('not_stated', 'esophagus', 'proximal_esophagus', 'mid_esophagus', 'distal_esophagus',
             'gastroesophageal_junction', 'stomach', 'gastric_cardia', 'gastric_fundus', 'gastric_body', 'gastric_antrum',
             'pylorus', 'duodenum', 'duodenal_bulb', 'second_portion_duodenum', 'ampulla', 'jejunum', 'ileum',
             'terminal_ileum', 'neo_terminal_ileum', 'small_bowel', 'colon', 'right_colon', 'left_colon',
             'proximal_colon', 'distal_colon', 'cecum', 'appendiceal_orifice', 'ileocecal_valve', 'ascending_colon',
             'hepatic_flexure', 'transverse_colon', 'splenic_flexure', 'descending_colon', 'sigmoid_colon',
             'rectosigmoid', 'rectum', 'anal_canal', 'anastomosis', 'stoma', 'pouch', 'common_bile_duct', 'bile_duct',
             'pancreatic_duct', 'pancreas', 'gallbladder', 'liver', 'lymph_node', 'other')
QUESTION_ABOUT = ('date_of_service', 'procedure', 'kind', 'technique', 'target', 'time', 'performer', 'status', 'scope',
                  'extent', 'completion', 'visit_basis', 'identity', 'contradiction', 'other')

ENUMERATIONS = MappingProxyType({
    'PROCEDURES': PROCEDURES, 'KINDS': KINDS, 'DEVICES': DEVICES, 'TIMES': TIMES, 'PERFORMERS': PERFORMERS,
    'STATUSES': STATUSES, 'SCOPES': SCOPES, 'PURPOSES': PURPOSES, 'COMPLETIONS': COMPLETIONS, 'EM_BASES': EM_BASES,
    'SEPARATE': SEPARATE, 'DATE_STATES': DATE_STATES, 'DATE_ROLES': DATE_ROLES, 'ANATOMY_STATES': ANATOMY_STATES,
    'MULTIPLICITY': MULTIPLICITY, 'LANDMARKS': LANDMARKS, 'QUESTION_ABOUT': QUESTION_ABOUT,
})


# --- LOCAL_SCHEMA (contract 3.2): the source ---------------------------------------------------------------------------

def _string() -> dict:
    return {'type': 'string'}


def _ids() -> dict:
    return {'type': 'array', 'items': {'type': 'string'}}


def _enum(values: tuple) -> dict:
    return {'type': 'string', 'enum': list(values)}


def _list(items: dict) -> dict:
    return {'type': 'array', 'items': items}


def _object(properties: dict) -> dict:
    """Every field required and nothing else allowed (the participants' rule, participants/prompt.py _object)."""
    return {'type': 'object', 'additionalProperties': False, 'required': list(properties), 'properties': properties}


def _attribute(values: tuple) -> dict:
    """An attribute: its enumeration value, the words inside its own passages that state it, and those passages."""
    return _object({'value': _enum(values), 'words': _string(), 'passages': _ids()})


LOCAL_SCHEMA = _object({
    'passages': _list(_object({'id': _string(), 'text': _string()})),
    'encounter': _object({
        'date_of_service': _object({
            'value': _string(),
            'state': _enum(DATE_STATES),
            'words': _string(),
            'passages': _ids(),
            'other_dates': _list(_object({'value': _string(), 'role': _enum(DATE_ROLES), 'words': _string(),
                                          'passages': _ids()})),
        }),
        'documenting_endoscopist': _object({'words': _string(), 'passages': _ids()}),
        'team': _list(_object({'words': _string(), 'passages': _ids()})),
        'anatomy': _list(_object({'state': _enum(ANATOMY_STATES), 'landmark': _enum(LANDMARKS), 'words': _string(),
                                  'passages': _ids()})),
        'reach': _list(_object({'event': _string(), 'landmark': _enum(LANDMARKS), 'words': _string(),
                                'passages': _ids(), 'completion': _attribute(COMPLETIONS)})),
        'visit_facts': _list(_object({'event': _string(), 'basis': _attribute(EM_BASES),
                                      'separately_identifiable': _attribute(SEPARATE)})),
    }),
    'lesions': _list(_object({
        'id': _string(),
        'words': _string(),
        'landmark': _enum(LANDMARKS),
        'site_words': _string(),
        'size_words': _string(),
        'multiplicity': _enum(MULTIPLICITY),
        'passages': _ids(),
    })),
    'events': _list(_object({
        'id': _string(),
        'procedure': _attribute(PROCEDURES),
        'kind': _attribute(KINDS),
        'technique': _attribute(DEVICES),
        'target': _object({'lesion': _string(), 'landmark': _enum(LANDMARKS), 'words': _string(), 'passages': _ids()}),
        'time': _attribute(TIMES),
        'performer': _attribute(PERFORMERS),
        'status': _attribute(STATUSES),
        'scope': _object({'value': _enum(SCOPES), 'targets': _ids(), 'words': _string(), 'passages': _ids()}),
        'purpose': _attribute(PURPOSES),
        'part_of': _string(),
        'sequence': {'type': 'integer'},
        'contradicts': _list(_object({'event': _string(), 'passages': _ids()})),
    })),
    'open_questions': _list(_object({'about': _enum(QUESTION_ABOUT), 'events': _ids(), 'lesions': _ids(),
                                     'passages': _ids()})),
})


# --- RESPONSE_SCHEMA (contract 3.2): derived, never written by hand ----------------------------------------------------

_KEYWORDS = frozenset({'type', 'properties', 'required', 'additionalProperties', 'items', 'enum'})


def gemini_schema(local: dict) -> dict:
    """Gemini's responseSchema for ``local`` (a schema in LOCAL_SCHEMA's form): each type upper-cased,
    additionalProperties dropped, properties, required, items and enum kept, and propertyOrdering set to each object's
    declaration order. Pure; a new dict that shares nothing with ``local``. ValueError for a keyword, a type or an object
    this generator does not implement - an object must forbid additional properties and require exactly its properties,
    in their order - so a schema change cannot pass ungenerated."""
    if not isinstance(local, dict):
        raise ValueError('A schema node must be a dict.')
    unknown = set(local) - _KEYWORDS
    if unknown:
        raise ValueError(f'The interpretation schema uses keywords gemini_schema does not implement: {sorted(unknown)}.')
    kind = local.get('type')
    node = {'type': kind.upper() if isinstance(kind, str) else kind}
    if kind == 'object':
        properties = local.get('properties')
        if (not isinstance(properties, dict) or local.get('additionalProperties') is not False
                or list(local.get('required', ())) != list(properties)):
            raise ValueError('Every object in the interpretation schema must forbid additional properties and require '
                             'exactly the properties it declares, in their order.')
        node['properties'] = {key: gemini_schema(child) for key, child in properties.items()}
        node['required'] = list(properties)
        node['propertyOrdering'] = list(properties)
    elif kind == 'array':
        node['items'] = gemini_schema(local.get('items'))
    elif kind not in ('string', 'integer'):
        raise ValueError(f'The interpretation schema uses the type {kind!r}, which gemini_schema does not implement.')
    if 'enum' in local:
        values = local['enum']
        if kind != 'string' or not isinstance(values, list) or not values or not all(
                isinstance(value, str) for value in values) or len(set(values)) != len(values):
            raise ValueError('An enumeration in the interpretation schema must be a list of distinct strings.')
        node['enum'] = list(values)
    return node


RESPONSE_SCHEMA = gemini_schema(LOCAL_SCHEMA)


# --- the bounds (contract 3.3): a whole answer outside them is refused, named by count, never truncated -----------------

BOUNDS = MappingProxyType({
    'passages': 400,               # entries in the passage table
    'passage_chars': (1, 600),     # characters of one passage's text (participants.reading MAX_QUOTE_CHARS is 600 too)
    'lesions': 64,
    'events': 200,
    'open_questions': 32,
    'anatomy': 16,
    'reach': 16,
    'visit_facts': 8,
    'team': 8,
    'other_dates': 16,
    'attribute_passages': 8,       # passage ids in one ``passages`` list, other than an open question's
    'contradicts': 8,              # per event
    'scope_targets': 16,
    'question_ids': 16,            # ids in each of an open question's events, lesions and passages lists
    'words_chars': 300,            # characters of one ``words``, ``site_words`` or ``size_words``
    'sequence': (0, 999),
    'cited_passages': 4000,        # passage ids cited in the whole answer, every ``passages`` list counted
})


# --- the canonical bytes every pin is taken over ------------------------------------------------------------------------

def canonical(value) -> bytes:
    """``value`` as the request body is hashed and sent (providers.base.canonical_body): keys sorted, no spaces, UTF-8."""
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode('utf-8')


def sha256_of(value) -> str:
    """The sha256 of ``value``'s canonical bytes (a schema) or of its UTF-8 bytes (a text)."""
    data = value.encode('utf-8') if isinstance(value, str) else canonical(value)
    return hashlib.sha256(data).hexdigest()
