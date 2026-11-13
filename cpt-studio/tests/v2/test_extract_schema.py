"""Pass 1's answer shape (contract/extract_schema.py; docs/gemini-migration/FINAL-V2.md 1.3-1.8 and 2.1, step 1b of 8.1),
TEXT-ONLY and SYNTHETIC.

What is proved here, each against the design's text or against v1 computed in the test:
- LOCAL_SCHEMA_2 is 1.4's answer, key for key and in order, in v1's LOCAL form, with ``doubts`` [R:CO-1] and
  ``device_reached`` [R:CO-8]; every FACT, SOURCE and DOUBT is 1.3's; what 1.4 says is gone from v1 is gone; no field
  certifies anything (3.6);
- RESPONSE_SCHEMA_2 derives mechanically from it, through the 0b copy of v1's generator, and equals v1's generator's own
  output; it shares nothing with its source;
- ATTRIBUTES agrees with the schema both ways, names every Attribute, and gives each id the family I4 resolves it in;
- BOUNDS_2 is 1.8's, number for number; DOUBT_ATTRIBUTES names, for each DOUBT_ABOUT value, attributes its families
  carry, and ``whole`` all of them (the rows DECISIONS D200 confirms);
- each family's id letter (DECISIONS D185) is engine/types.IdFamily's;
- DEFINITIONS gives each enumeration of the schema one line that names its values, describes meanings and quotes
  nothing; no code reads it but its canonical form; no line needs a named exemption from 2a's scans (triage 2a R5), and
  2a's scans run over it with only 2a's reviewed runs exempt, passed explicitly (integration O7);
- the definitions the integration owner ruled, in the lines and in both passes' instructions: pressure_measurement and
  manometry narrowed both ways (DECISIONS D209, pass 1's half), motility and anorectal made disjoint (D214);
- the schema shas the integration owner pins, measured (DEFINITIONS has no pin of its own: D202), and the sizes (about
  7.9x v1's, measured at D1 before any compaction: D203);
- 5.7 measure 4 already holds here (step 0b's rules), DEFINITIONS being the pinned OUTPUT table the rule names.
"""
from __future__ import annotations

import ast
import copy
import enum
import hashlib
import re
from pathlib import Path

from django.test import SimpleTestCase

from studio import interpretation
from studio.interpretation import schema  # v1, read only: the generator parity proof, computed here
from studio.interpretation.contract import extract_schema as xs
from studio.interpretation.contract import jsonschema
from studio.interpretation.contract import types as ct
from studio.interpretation.engine.types import IdFamily
from studio.participants import reading
from tests.v2.test_types import measure_4  # step 0b's statement of 5.7 measure 4: one implementation, many readers

APP = Path(__file__).resolve().parents[2]
CONTRACT = APP / 'studio' / 'interpretation' / 'contract'
A, F = ct.Attribute, xs.Family

# The shas this step hands the integration owner (2.5: LOCAL_SCHEMA_SHA256_V2, RESPONSE_SCHEMA_SHA256_V2), measured on
# this tree. A changed byte of either changes them: until the first recording under gemini-events@2 (D1) it needs only
# the recomputed pin, after it a new INTERPRETATION_VERSION (DECISIONS D202). Step 1b3's rulings (D209's pass-1 half,
# D214) change definitions only, which are no schema bytes, so both are as INT-5 wrote them (measured again by 1b3).
LOCAL_SHA256 = '7cd387041de317825f371415070bcee1703be0d9022c92bf77580f59dda3d04c'
RESPONSE_SHA256 = 'bcb7fce8f1fa0b28c5fb8ea7514ba22f14ce06f18d1f557b16b92798f1109cab'
# DEFINITIONS has no pin of its own (DECISIONS D202): 2a renders every line verbatim into INSTRUCTIONS_2, whose pin
# covers them. This sha is this step's own change detector, so a changed definition is seen here before 2a's pin moves.
# Step 1b3's value, after D209's act kinds and D214's session kinds (ac34cda7... is superseded).
DEFINITIONS_SHA256 = '1b7563e52a8203dfc4bcd614c766b9d84bfed4692e82a65c60bac3b72fc30a9c'
SIZES = {'local': 89_759, 'response': 95_046, 'fact_nodes': 53, 'source_nodes': 112, 'enum_sites': 299, 'depth': 12}


def nodes(node: dict, path: str = ''):
    """(path, node) for every node of a schema, the root ('') included; a list's items are path + '[]'."""
    yield path, node
    for key, child in node.get('properties', {}).items():
        yield from nodes(child, f'{path}.{key}' if path else key)
    if 'items' in node:
        yield from nodes(node['items'], path + '[]')


def depth(node: dict) -> int:
    children = list(node.get('properties', {}).values()) + ([node['items']] if 'items' in node else [])
    return 1 + max((depth(child) for child in children), default=0)


def keys(path: str) -> list:
    node = dict(nodes(xs.LOCAL_SCHEMA_2))[path]
    return list(node['properties'])


FACT_KEYS = ['state', 'value', 'qualifiers', 'sources', 'options']
SOURCE_KEYS = ['units', 'words', 'link']


def is_fact(node: dict) -> bool:
    return node.get('type') == 'object' and list(node.get('properties', {})) == FACT_KEYS


def values(enumeration) -> list:
    return [member.value for member in enumeration]


# --- the answer -------------------------------------------------------------------------------------------------------

# FINAL-V2 1.4, object by object, field by field, in its order.
DESIGN_KEYS = {
    '': ['encounter', 'people', 'sections', 'sessions', 'anatomy', 'lesions', 'events', 'doubts'],
    'encounter': ['date_of_service', 'other_dates', 'documenting_clinician'],
    'encounter.date_of_service': ['state', 'value', 'sources', 'options'],
    'encounter.date_of_service.options[]': ['value', 'sources'],
    'encounter.other_dates[]': ['value', 'role'],
    'people[]': ['id', 'name', 'role'],
    'sections[]': ['id', 'start', 'end', 'owner', 'role', 'occasion', 'performer', 'performer_person'],
    'sessions[]': ['id', 'examination', 'kind', 'encounter', 'tract', 'approach', 'through', 'reached', 'device_reached',
                   'reached_anatomy', 'completion', 'stations', 'part_of_session'],
    'anatomy[]': ['id', 'type', 'organ', 'subtype', 'joins'],
    'lesions[]': ['id', 'description', 'multiplicity', 'places', 'distinct_from', 'same_as'],
    'events[]': ['id', 'anchor', 'restatements', 'kind', 'other_class', 'status', 'session', 'date_relation', 'date',
                 'performer', 'performer_person', 'target', 'technique', 'purpose', 'cause', 'cause_event', 'part_of',
                 'part_relation', 'yield', 'access_outcome', 'scope', 'visit'],
    'events[].anchor': ['units', 'kind_words', 'status_words'],
    'events[].restatements[]': ['units', 'role'],
    'events[].target': ['lesion', 'structure', 'places', 'anatomy', 'duct'],
    'events[].technique': ['device', 'route'],
    'events[].scope': ['breadth', 'targets', 'segment', 'covers', 'excepts'],
    'events[].visit': ['basis', 'separately_identifiable'],
    'doubts[]': ['about', 'objects', 'units', 'basis', 'readings'],
}
# 1.4 "Gone from v1's answer", and v1 fields with no v2 counterpart; plus 3.6: no field that certifies.
GONE = ('passages', 'open_questions', 'sequence', 'contradicts', 'reach', 'visit_facts', 'documenting_endoscopist',
        'team', 'procedure', 'time', 'landmark', 'site_words', 'size_words', 'instrument', 'reached_instrument')
CERTIFYING = re.compile(r'verif|confiden|certain|probab|score', re.IGNORECASE)


class AnswerShapeTests(SimpleTestCase):
    def test_the_answer_is_1_4s_key_for_key_in_order(self):
        for path, expected in DESIGN_KEYS.items():
            with self.subTest(object=path or 'root'):
                self.assertEqual(keys(path), expected)
        objects = [path for path, node in nodes(xs.LOCAL_SCHEMA_2) if node['type'] == 'object' and not is_fact(node)
                   and list(node['properties']) != SOURCE_KEYS
                   and (not path.endswith('.options[]') or path == 'encounter.date_of_service.options[]')]
        self.assertEqual(sorted(objects), sorted(DESIGN_KEYS))  # every object of the answer is one of 1.4's

    def test_doubts_and_device_reached_are_in_both_schemas(self):
        for name, root in (('LOCAL', xs.LOCAL_SCHEMA_2), ('RESPONSE', xs.RESPONSE_SCHEMA_2)):
            with self.subTest(schema=name):
                every = dict(nodes(root))
                doubt = every['doubts[]']
                self.assertEqual(list(doubt['properties']), DESIGN_KEYS['doubts[]'])
                self.assertEqual(doubt['properties']['about']['enum'], values(ct.DoubtAbout))
                self.assertEqual(doubt['properties']['basis']['enum'], values(ct.DoubtBasis))
                session = list(every['sessions[]']['properties'])
                self.assertEqual(session.index('device_reached'), session.index('reached') + 1)
                reached = every['sessions[].device_reached[]']
                self.assertEqual(reached['properties']['value']['enum'], values(ct.Extent) + [''])

    def test_what_1_4_retired_is_gone_and_nothing_certifies(self):
        names = {name for _, node in nodes(xs.LOCAL_SCHEMA_2) for name in node.get('properties', {})}
        self.assertFalse(names & set(GONE), names & set(GONE))
        self.assertEqual([name for name in names if CERTIFYING.search(name)], [])
        self.assertTrue(CERTIFYING.search('verified') and CERTIFYING.search('confidence'))  # the control

    def test_the_local_form(self):
        self.assertEqual(reading.schema_error({}, xs.LOCAL_SCHEMA_2, 'the interpretation'),
                         "the interpretation lacks the required field 'encounter'")
        for path, node in nodes(xs.LOCAL_SCHEMA_2):
            with self.subTest(path=path or 'root'):
                self.assertIn(node['type'], ('object', 'array', 'string'))  # the answer has no integer
                if node['type'] == 'object':
                    self.assertIs(node['additionalProperties'], False)
                    self.assertEqual(node['required'], list(node['properties']))
                    self.assertEqual(set(node), {'type', 'additionalProperties', 'required', 'properties'})

    def test_every_fact_is_1_3s_fact(self):
        facts = [(path, node) for path, node in nodes(xs.LOCAL_SCHEMA_2) if is_fact(node)]
        self.assertEqual(len(facts), SIZES['fact_nodes'])
        for path, node in facts:
            with self.subTest(fact=path):
                properties = node['properties']
                self.assertEqual(properties['state']['enum'], values(ct.FactState))
                self.assertEqual(properties['qualifiers'], {'type': 'array', 'items': {'type': 'string',
                                                                                      'enum': values(ct.Qualifier)}})
                for sources in (properties['sources'], properties['options']['items']['properties']['sources']):
                    self.assertEqual(sources['type'], 'array')
                    self.assertEqual(list(sources['items']['properties']), SOURCE_KEYS)
                option = properties['options']['items']
                self.assertEqual(list(option['properties']), ['value', 'sources'])
                value, side = properties['value'], option['properties']['value']
                if 'enum' in value:  # an enumeration: '' is the contradicted value only, never an option's
                    self.assertEqual(value['enum'][-1], '')
                    self.assertEqual(side['enum'], value['enum'][:-1])
                    self.assertNotIn('', side['enum'])
                else:  # an id or a date
                    self.assertEqual((value, side), ({'type': 'string'}, {'type': 'string'}))

    def test_every_source_is_1_3s_source(self):
        sources = [node for _, node in nodes(xs.LOCAL_SCHEMA_2) if node['type'] == 'object'
                   and list(node['properties']) == SOURCE_KEYS]
        self.assertEqual(len(sources), SIZES['source_nodes'])
        for node in sources:
            self.assertEqual(node['properties'], {'units': {'type': 'array', 'items': {'type': 'string'}},
                                                  'words': {'type': 'string'},
                                                  'link': {'type': 'string', 'enum': values(ct.Link)}})

    def test_the_date_of_service_keeps_v1s_states(self):
        when = dict(nodes(xs.LOCAL_SCHEMA_2))['encounter.date_of_service']['properties']
        self.assertEqual(when['state']['enum'], list(schema.DATE_STATES))  # v1's, by value
        self.assertEqual((when['value'], when['options']['items']['properties']['value']),
                         ({'type': 'string'}, {'type': 'string'}))


# --- the derivation ----------------------------------------------------------------------------------------------------


class DerivationTests(SimpleTestCase):
    def test_the_response_schema_is_derived_mechanically(self):
        self.assertEqual(xs.RESPONSE_SCHEMA_2, jsonschema.gemini_schema(xs.LOCAL_SCHEMA_2))
        self.assertEqual(xs.RESPONSE_SCHEMA_2, schema.gemini_schema(xs.LOCAL_SCHEMA_2))  # v1's generator agrees
        local, gemini = dict(nodes(xs.LOCAL_SCHEMA_2)), dict(nodes(xs.RESPONSE_SCHEMA_2))
        self.assertEqual(list(local), list(gemini))
        for path, node in local.items():
            with self.subTest(path=path or 'root'):
                derived = gemini[path]
                self.assertEqual(derived['type'], node['type'].upper())
                self.assertNotIn('additionalProperties', derived)
                self.assertEqual(derived.get('enum'), node.get('enum'))
                if node['type'] == 'object':
                    self.assertEqual(set(derived), {'type', 'properties', 'required', 'propertyOrdering'})
                    self.assertEqual(derived['propertyOrdering'], list(node['properties']))
                    self.assertEqual(derived['required'], derived['propertyOrdering'])
                else:
                    self.assertEqual(set(derived) - {'items', 'enum'}, {'type'})

    def test_the_derived_schema_shares_nothing_with_its_source(self):
        before = jsonschema.canonical(xs.LOCAL_SCHEMA_2)
        derived = jsonschema.gemini_schema(xs.LOCAL_SCHEMA_2)
        derived['properties']['events']['items']['properties']['kind']['properties']['value']['enum'].append('x')
        derived['required'].append('x')
        self.assertEqual(jsonschema.canonical(xs.LOCAL_SCHEMA_2), before)
        self.assertEqual(jsonschema.sha256_of(xs.RESPONSE_SCHEMA_2), RESPONSE_SHA256)

    def test_no_node_of_the_source_is_shared(self):
        seen = [id(node) for _, node in nodes(xs.LOCAL_SCHEMA_2)]
        self.assertEqual(len(seen), len(set(seen)))
        copied = copy.deepcopy(xs.LOCAL_SCHEMA_2)
        copied['properties']['doubts']['items']['properties']['about']['enum'].append('x')
        self.assertEqual(jsonschema.sha256_of(xs.LOCAL_SCHEMA_2), LOCAL_SHA256)


# --- the attribute table -----------------------------------------------------------------------------------------------

# 3.1 I4 and 1.4's comments: the family each id an attribute holds is resolved in.
REFERENCES = {
    (F.ENCOUNTER, A.DOCUMENTING_CLINICIAN): F.PERSON, (F.SECTION, A.PERFORMER_PERSON): F.PERSON,
    (F.SESSION, A.EXAMINATION): F.EVENT, (F.SESSION, A.THROUGH): F.ANATOMY, (F.SESSION, A.REACHED_ANATOMY): F.ANATOMY,
    (F.SESSION, A.PART_OF_SESSION): F.SESSION, (F.LESION, A.DISTINCT_FROM): F.LESION, (F.LESION, A.SAME_AS): F.LESION,
    (F.EVENT, A.SESSION): F.SESSION, (F.EVENT, A.PERFORMER_PERSON): F.PERSON, (F.EVENT, A.TARGET_LESION): F.LESION,
    (F.EVENT, A.TARGET_ANATOMY): F.ANATOMY, (F.EVENT, A.CAUSE_EVENT): F.EVENT, (F.EVENT, A.PART_OF): F.EVENT,
    (F.EVENT, A.SCOPE_TARGETS): F.LESION, (F.EVENT, A.SCOPE_COVERS): F.EVENT, (F.EVENT, A.SCOPE_EXCEPTS): F.EVENT,
}
DATES = {(F.ENCOUNTER, A.DATE_OF_SERVICE), (F.EVENT, A.DATE)}
FAMILY_PATHS = {F.ENCOUNTER: 'encounter', F.PERSON: 'people[]', F.SECTION: 'sections[]', F.SESSION: 'sessions[]',
                F.ANATOMY: 'anatomy[]', F.LESION: 'lesions[]', F.EVENT: 'events[]'}


def schema_path(family, field) -> str:
    if (family, field.attribute) == (F.ENCOUNTER, A.OTHER_DATES_ROLE):
        return 'encounter.other_dates[].role'
    return '.'.join((FAMILY_PATHS[family],) + field.path)


class AttributeTableTests(SimpleTestCase):
    def test_the_table_and_the_schema_agree_both_ways(self):
        every = dict(nodes(xs.LOCAL_SCHEMA_2))
        listed = set()
        for family, fields in xs.ATTRIBUTES.items():
            for field in fields:
                if field.arity is xs.Arity.OTHER:
                    continue
                path = schema_path(family, field)
                with self.subTest(attribute=path):
                    node = every[path]
                    if field.arity is xs.Arity.FACT:
                        self.assertTrue(is_fact(node))
                        fact = node
                    elif field.arity in (xs.Arity.SLOT, xs.Arity.FACTS):
                        self.assertEqual(node['type'], 'array')
                        self.assertTrue(is_fact(node['items']))
                        fact = node['items']
                    else:  # LIST: a plain list of ids or of enumeration values
                        self.assertEqual(node['type'], 'array')
                        expected = {'type': 'string'} if field.values is None else {'type': 'string',
                                                                                      'enum': values(field.values)}
                        self.assertEqual(node['items'], expected)
                        listed.add(path)
                        continue
                    value = fact['properties']['value']
                    self.assertEqual(value.get('enum'), values(field.values) + [''] if field.values else None)
                    listed.add(path if field.arity is xs.Arity.FACT else path + '[]')
        in_schema = {path for path, node in every.items() if is_fact(node)}
        in_schema |= {path for path, node in every.items() if path.startswith('events[].scope.')
                      and path.count('.') == 2 and node['type'] == 'array' and not is_fact(node['items'])}
        self.assertEqual(listed, in_schema)

    def test_the_attributes_the_answer_does_not_give_as_facts(self):
        other = {(family, field.attribute) for family, fields in xs.ATTRIBUTES.items() for field in fields
                 if field.arity is xs.Arity.OTHER}
        self.assertEqual(other, {(F.ENCOUNTER, A.DATE_OF_SERVICE), (F.EVENT, A.RESTATEMENTS_ROLE), (F.EVENT, A.ENTRY)})
        self.assertEqual(dict(nodes(xs.LOCAL_SCHEMA_2))['events[].restatements[].role']['enum'],
                         values(ct.RestatementRole))
        self.assertEqual(xs.field(F.EVENT, A.ENTRY).values, ct.Owner)  # an act's entry is its section's owner (1.5)

    def test_every_attribute_is_some_familys(self):
        named = {field.attribute for fields in xs.ATTRIBUTES.values() for field in fields}
        self.assertEqual(named, set(ct.Attribute))
        for family in xs.Family:
            with self.subTest(family=family):
                attributes = xs.attributes(family)
                self.assertEqual(len(attributes), len(set(attributes)))

    def test_ids_and_dates(self):
        refers = {(family, field.attribute): field.refers_to for family, fields in xs.ATTRIBUTES.items()
                  for field in fields if field.refers_to is not None}
        self.assertEqual(refers, REFERENCES)
        dates = {(family, field.attribute) for family, fields in xs.ATTRIBUTES.items() for field in fields
                 if field.is_date}
        self.assertEqual(dates, DATES)
        for family, fields in xs.ATTRIBUTES.items():
            for field in fields:
                self.assertFalse(field.values is not None and field.refers_to is not None, field)

    def test_each_list_takes_its_1_8_bound(self):
        bounds = {(family, field.attribute): field.bound for family, fields in xs.ATTRIBUTES.items()
                  for field in fields if field.arity in (xs.Arity.FACTS, xs.Arity.LIST)}
        self.assertEqual(bounds, {
            (F.SESSION, A.REACHED): xs.Bound.PLACES, (F.SESSION, A.DEVICE_REACHED): xs.Bound.PLACES,
            (F.SESSION, A.STATIONS): xs.Bound.STATIONS, (F.ANATOMY, A.JOINS): xs.Bound.PLACES,
            (F.LESION, A.PLACES): xs.Bound.PLACES, (F.LESION, A.DISTINCT_FROM): xs.Bound.LESION_LINKS,
            (F.LESION, A.SAME_AS): xs.Bound.LESION_LINKS, (F.EVENT, A.TARGET_PLACES): xs.Bound.PLACES,
            (F.EVENT, A.SCOPE_TARGETS): xs.Bound.SCOPE_LIST, (F.EVENT, A.SCOPE_SEGMENT): xs.Bound.SCOPE_LIST,
            (F.EVENT, A.SCOPE_COVERS): xs.Bound.SCOPE_LIST, (F.EVENT, A.SCOPE_EXCEPTS): xs.Bound.SCOPE_LIST})
        for family, fields in xs.ATTRIBUTES.items():
            for field in fields:
                if field.arity is xs.Arity.SLOT:
                    self.assertIs(field.bound, xs.Bound.SLOT)
                elif field.arity in (xs.Arity.FACT, xs.Arity.OTHER):
                    self.assertIsNone(field.bound)

    def test_field_lookup(self):
        self.assertEqual(xs.field(F.EVENT, A.TARGET_PLACES).path, ('target', 'places'))
        with self.assertRaises(KeyError):
            xs.field(F.LESION, A.STATUS)


class FamilyLetterTests(SimpleTestCase):
    def test_each_family_opens_its_ids_with_its_own_letter(self):
        # DECISIONS D185 and 1.4's convention (P1, N0, X1, Y1, L1, E1); the encounter has no id
        self.assertEqual({family: family.letter for family in xs.Family},
                         {F.ENCOUNTER: '', F.PERSON: 'P', F.SECTION: 'N', F.SESSION: 'X', F.ANATOMY: 'Y', F.LESION: 'L',
                          F.EVENT: 'E'})
        # the engine's IdFamily holds exactly these letters and the units' S, so an id the reader admits is one the
        # engine reads (engine/types.Id.parse)
        letters = [family.letter for family in xs.Family if family is not F.ENCOUNTER]
        self.assertEqual(len(letters), len(set(letters)))
        self.assertEqual(set(letters) | {'S'}, {member.value for member in IdFamily})


# --- the bounds --------------------------------------------------------------------------------------------------------


class BoundsTests(SimpleTestCase):
    def test_the_bounds_are_1_8s(self):
        self.assertEqual({bound.value: number for bound, number in xs.BOUNDS_2.items()}, {
            'events': 200, 'sections': 48, 'sessions': 16, 'people': 16, 'anatomy': 16, 'lesions': 64,
            'other_dates': 16, 'restatements': 16, 'doubts': 64, 'doubt_objects': 16, 'doubt_readings': 4, 'slot': 1,
            'places': 8, 'stations': 7, 'lesion_links': 16, 'sources': 8, 'options': 4, 'scope_list': 32,
            'words_chars': 600, 'cited_units': 4000, 'source_units': 12})
        self.assertEqual(set(xs.BOUNDS_2), set(xs.Bound))
        with self.assertRaises(TypeError):
            xs.BOUNDS_2[xs.Bound.EVENTS] = 1  # read-only
        self.assertEqual(xs.BOUNDS_2[xs.Bound.STATIONS], len(ct.Station))  # 1.8: stations 7, one per station


# --- the doubts' table ------------------------------------------------------------------------------------------------

# The table as built, read back (each row from 1.4's DOUBT_ABOUT and 1.6's rows; DECISIONS D200 confirms every row).
DOUBT_ROWS = {
    'status': {F.EVENT: (A.STATUS,)},
    'kind': {F.EVENT: (A.KIND, A.OTHER_CLASS), F.SESSION: (A.KIND,)},
    'session': {F.EVENT: (A.SESSION,)},
    'date_relation': {F.EVENT: (A.DATE_RELATION, A.DATE), F.SECTION: (A.OCCASION,), F.SESSION: (A.ENCOUNTER,)},
    'performer': {F.EVENT: (A.PERFORMER, A.PERFORMER_PERSON), F.SECTION: (A.PERFORMER, A.PERFORMER_PERSON)},
    'entry': {F.EVENT: (A.ENTRY,), F.SECTION: (A.OWNER,)},
    'target': {F.EVENT: (A.TARGET_LESION, A.TARGET_STRUCTURE, A.TARGET_PLACES, A.TARGET_ANATOMY, A.TARGET_DUCT),
               F.LESION: (A.PLACES,)},
    'technique': {F.EVENT: (A.TECHNIQUE_DEVICE, A.TECHNIQUE_ROUTE), F.SESSION: (A.APPROACH, A.THROUGH)},
    'purpose': {F.EVENT: (A.PURPOSE,)},
    'cause': {F.EVENT: (A.CAUSE, A.CAUSE_EVENT)},
    'part_of': {F.EVENT: (A.PART_OF, A.PART_RELATION), F.SESSION: (A.PART_OF_SESSION,)},
    'yield': {F.EVENT: (A.YIELD,)},
    'access_outcome': {F.EVENT: (A.ACCESS_OUTCOME,)},
    'extent': {F.SESSION: (A.REACHED, A.DEVICE_REACHED, A.REACHED_ANATOMY, A.COMPLETION)},
    'stations': {F.SESSION: (A.STATIONS,)},
    'completion': {F.SESSION: (A.COMPLETION,)},
    'approach': {F.SESSION: (A.APPROACH, A.THROUGH)},
    'anatomy': {F.ANATOMY: (A.TYPE, A.ORGAN, A.SUBTYPE, A.JOINS)},
    'identity': {F.LESION: (A.MULTIPLICITY, A.SAME_AS, A.DISTINCT_FROM)},
    'date_of_service': {F.ENCOUNTER: (A.DATE_OF_SERVICE,)},
    'visit': {F.EVENT: (A.VISIT_BASIS, A.VISIT_SEPARATELY_IDENTIFIABLE)},
}


class DoubtTableTests(SimpleTestCase):
    def test_every_about_value_has_its_row(self):
        self.assertEqual(set(xs.DOUBT_ATTRIBUTES), set(ct.DoubtAbout))
        for about, row in DOUBT_ROWS.items():
            with self.subTest(about=about):
                self.assertEqual(dict(xs.DOUBT_ATTRIBUTES[ct.DoubtAbout(about)]), row)
        self.assertEqual({family: attributes for family, attributes in
                          xs.DOUBT_ATTRIBUTES[ct.DoubtAbout.WHOLE].items()},
                         {family: xs.attributes(family) for family in xs.Family})

    def test_each_row_names_attributes_its_families_carry(self):
        for about, row in xs.DOUBT_ATTRIBUTES.items():
            for family, attributes in row.items():
                with self.subTest(about=about, family=family):
                    self.assertTrue(attributes)
                    self.assertTrue(set(attributes) <= set(xs.attributes(family)))
        encounter = [about for about, row in xs.DOUBT_ATTRIBUTES.items() if F.ENCOUNTER in row]
        self.assertEqual(encounter, [ct.DoubtAbout.DATE_OF_SERVICE, ct.DoubtAbout.WHOLE])  # the encounter has no id
        with self.assertRaises(TypeError):
            xs.DOUBT_ATTRIBUTES[ct.DoubtAbout.STATUS][F.LESION] = (A.PLACES,)  # read-only


# --- the definitions --------------------------------------------------------------------------------------------------

# Values a line names by its list rather than one by one: the places (LANDMARKS2) and EXTENTS, which is the places and
# stated_depth. Every other line names every value of its enumeration.
NAMED_BY_LIST = {ct.Landmark: ('anastomosis', 'stoma', 'pouch', 'other'), ct.Extent: ('stated_depth',)}
VENDORS = re.compile(r'gemini|google|corti\b|astra|fable|claude|anthropic|openai|gpt', re.IGNORECASE)


def enumerations_used(root: dict) -> list:
    """Every enumeration class whose values (or values and '') make an enum of ``root``, in first-use order."""
    by_values = {tuple(values(enumeration)): enumeration for enumeration in xs.ENUMERATIONS}
    used = []
    for _, node in nodes(root):
        if 'enum' in node:
            listed = tuple(node['enum'][:-1] if node['enum'][-1] == '' else node['enum'])
            enumeration = by_values[listed]  # KeyError: an enum site no listed enumeration explains
            if enumeration not in used:
                used.append(enumeration)
    return used


class DefinitionTests(SimpleTestCase):
    def test_every_enumeration_the_schema_uses_has_one_line(self):
        self.assertEqual(enumerations_used(xs.LOCAL_SCHEMA_2), list(xs.ENUMERATIONS))
        self.assertEqual(list(xs.DEFINITIONS), list(xs.ENUMERATIONS))
        self.assertEqual(len(xs.ENUMERATIONS), 39)
        for enumeration, line in xs.DEFINITIONS.items():
            with self.subTest(enumeration=enumeration.__name__):
                self.assertTrue(issubclass(enumeration, enum.Enum))
                self.assertIsInstance(line, str)
                self.assertNotIn('\n', line)
                self.assertEqual(line, line.strip())
                self.assertTrue(line[0].isupper() and line.endswith('.'), line)

    def test_each_line_names_its_values(self):
        for enumeration, line in xs.DEFINITIONS.items():
            named = NAMED_BY_LIST.get(enumeration, values(enumeration))
            with self.subTest(enumeration=enumeration.__name__):
                for value in named:
                    self.assertRegex(line, rf'(?<![a-z_]){re.escape(value)}(?![a-z_])')
        self.assertNotRegex('stone_extraction', r'(?<![a-z_])stone(?![a-z_])')  # the boundary control

    def test_a_definition_describes_and_never_quotes(self):
        for enumeration, line in xs.DEFINITIONS.items():
            with self.subTest(enumeration=enumeration.__name__):
                self.assertFalse(set(line) & set('"“”‘’`«»'), line)  # no quoted surface form (2.3)
                self.assertIsNone(VENDORS.search(line))  # no provider or product name (2.3)
                self.assertIsNone(re.search(r'\d', line))  # no code, count, date or measure
                self.assertNotIn('e.g.', line)
                self.assertNotIn('for example', line.lower())
        self.assertIsNotNone(VENDORS.search('a Gemini answer'))  # the control

    def test_the_canonical_document(self):
        document = xs.definitions_document()
        self.assertEqual(list(document), [enumeration.__name__ for enumeration in xs.ENUMERATIONS])
        self.assertEqual(jsonschema.sha256_of(document), DEFINITIONS_SHA256)  # the change detector, no pin (D202)
        with self.assertRaises(TypeError):
            xs.DEFINITIONS[ct.Kind] = 'x'  # read-only

    def test_no_definition_needs_a_named_scan_exemption(self):
        # triage 2a R5: 2a's scans exempted two phrases for 1b's lines alone - 'not stated' (survey 4's label for an
        # empty value) in the device line, and 'setting' (D3's member-entered setting) in the session-kind line. The
        # lines now say the same meanings without them, so no exemption is needed.
        for enumeration, line in xs.DEFINITIONS.items():
            with self.subTest(enumeration=enumeration.__name__):
                self.assertNotIn('not stated', ' '.join(line.lower().split()))
                self.assertIsNone(re.search(r'(?i)\bsetting', line))
        device, kinds = xs.DEFINITIONS[ct.Device], xs.DEFINITIONS[ct.SessionKind]
        self.assertIn('snare (a snare the document does not call cold or hot)', device)
        self.assertIn('forceps (forceps the document does not call cold or hot)', device)
        self.assertIn('em_other (an evaluation and management service other than an office or outpatient visit)',
                      kinds)
        self.assertIn('office_em (an office or outpatient evaluation and management visit)', kinds)
        self.assertIsNotNone(re.search(r'(?i)\bsetting', 'in another setting'))  # the control

    def test_2as_scans_exempt_no_quoted_phrase_and_only_2as_reviewed_runs(self):
        # 2a's own scans (one implementation, imported here because 2a's test module imports this one), run over the
        # instruction 2a renders the definitions into. No quoted phrase is exempt, by name or whole (triage 2a R5: the
        # 'not stated' and 'setting' exemptions are gone); the only runs exempt are 2a's reviewed runs of three or four
        # words (SHARED_RUNS, each with its reason, none a whole phrase), passed explicitly here (integration O7 = 2a-2
        # R3), and every run the definitions share with survey 4 is one of them.
        from studio.interpretation.contract import extract_prompt as xp
        from tests.v2 import test_extract_prompt as scans
        self.assertIsNone(re.search(r'(?i)\bsetting', xp.INSTRUCTIONS_2))  # D3: no setting, none allowed
        for line in xs.DEFINITIONS.values():
            self.assertIn(line, xp.INSTRUCTIONS_2)  # rendered verbatim (D202)
        if not scans.SURVEY_4.is_file():
            self.skipTest('survey 4 (design-v2/survey/failures.md) is not in this environment')
        data = scans.SURVEY_4.read_bytes()
        self.assertEqual(hashlib.sha256(data).hexdigest(), scans.SURVEY_4_SHA256)  # the survey 2a's scan is written for
        phrases = scans.survey_4_phrases(data.decode('utf-8'))
        self.assertIn(('not', 'stated'), phrases)  # the phrase once exempted is still a survey phrase, scanned for
        definitions = scans.words('\n'.join(xs.DEFINITIONS.values()))
        self.assertEqual(scans.phrase_hits(scans.words(xp.INSTRUCTIONS_2), phrases, exempt=scans.SHARED_RUNS), [])
        self.assertEqual(scans.phrase_hits(definitions, phrases, exempt=scans.SHARED_RUNS), [])
        # with nothing exempt, what the definitions share is a subset of the reviewed runs, none of them a whole phrase
        shared = scans.phrase_hits(definitions, phrases, exempt=())
        self.assertLessEqual(set(shared), set(scans.SHARED_RUNS))
        self.assertFalse({tuple(run.split()) for run in scans.SHARED_RUNS} & phrases)
        # the controls: the phrase once exempted is found; and three words from the middle of a long survey phrase that
        # are no reviewed run, added to the definitions' words, break the subset
        self.assertTrue(scans.phrase_hits(scans.words('a snare not stated as cold or hot'), phrases,
                                          exempt=scans.SHARED_RUNS))
        long = max(sorted(phrases), key=len)
        middle = next(list(long[at:at + scans.SUB_PHRASE]) for at in range(2, len(long) - scans.SUB_PHRASE + 1)
                      if ' '.join(long[at:at + scans.SUB_PHRASE]) not in scans.SHARED_RUNS)
        self.assertFalse(set(scans.phrase_hits(definitions + middle, phrases, exempt=())) <= set(scans.SHARED_RUNS))

    def test_no_code_reads_the_definitions_but_their_canonical_form(self):
        for name in ('extract_schema.py', 'extract_read.py'):
            tree = ast.parse((CONTRACT / name).read_text(encoding='utf-8'))
            readers = {function.name for function in ast.walk(tree) if isinstance(function, ast.FunctionDef)
                       for node in ast.walk(function) if isinstance(node, ast.Name) and node.id == 'DEFINITIONS'}
            readers |= {function.name for function in ast.walk(tree) if isinstance(function, ast.FunctionDef)
                        for node in ast.walk(function) if isinstance(node, ast.Attribute) and node.attr == 'DEFINITIONS'}
            with self.subTest(module=name):
                self.assertEqual(readers, {'definitions_document'} if name == 'extract_schema.py' else set())


# --- the definitions the integration owner ruled (D209's pass-1 half, D214) --------------------------------------------

# Each is a sentence of its value line (a meaning, never a word list or a keyword rule: 5.7), rendered verbatim into
# pass 1's instruction; the act kinds' line also into pass 2's (appraise_prompt renders it, step 2c), so both passes say
# the same (D209). DECISIONS D209: pressure_measurement names the sphincter of Oddi (it serves only 43263); manometry
# names every manometry study other than the sphincter of Oddi's. D214: motility never takes anorectal testing, and
# anorectal testing, anorectal manometry included, is always anorectal.
PRESSURE_MEASUREMENT = 'pressure_measurement (a pressure measurement of the sphincter of Oddi)'
MANOMETRY = ('manometry (any manometry study other than one of the sphincter of Oddi, that is esophageal, gastric, '
             'duodenal or small-bowel, colonic or anorectal manometry, and an esophageal balloon distension study)')
MOTILITY = ('motility (a motility or manometry study of the esophagus, the stomach, the small bowel or the colon, never '
            'anorectal testing)')
ANORECTAL = 'anorectal (anorectal testing, anorectal manometry included)'
# the lines as step 1b wrote them, before the rulings: names only for the two kinds, overlapping session kinds
BEFORE_RULINGS = ('pressure_measurement, capsule_study, manometry, ph_monitoring',
                  'motility (a motility or manometry study)', 'anorectal (anorectal testing)')


def meaning(line: str, value: str) -> str:
    """What ``line`` says ``value`` means: the words inside the parentheses that follow the value's name. ValueError
    unless the line defines the value exactly once."""
    head = f'{value} ('
    if line.count(head) != 1:
        raise ValueError(f'{value} is defined {line.count(head)} times in the line.')
    start = line.index(head) + len(head)
    return line[start:line.index(')', start)]


class RuledDefinitionTests(SimpleTestCase):
    def test_d209_pressure_measurement_is_the_sphincter_of_oddi_and_manometry_every_other_study(self):
        from studio.interpretation.contract import appraise_prompt, extract_prompt as xp
        kinds = xs.DEFINITIONS[ct.Kind]
        for ruled in (PRESSURE_MEASUREMENT, MANOMETRY):
            with self.subTest(ruled=ruled[:30]):
                self.assertEqual(kinds.count(ruled), 1)  # the act kinds' line says it
                self.assertEqual(xp.INSTRUCTIONS_2.count(ruled), 1)  # pass 1's instruction says it
                self.assertEqual(appraise_prompt.INSTRUCTIONS.count(ruled), 1)  # and pass 2's, from the same line
        pressure, manometry = meaning(kinds, 'pressure_measurement'), meaning(kinds, 'manometry')
        # narrowed both ways: the one site pressure_measurement names is the one manometry sets apart, and every
        # manometry study the ruling lists is manometry's
        self.assertEqual(pressure, 'a pressure measurement of the sphincter of Oddi')
        self.assertIn('other than one of the sphincter of Oddi', manometry)
        for study in ('esophageal', 'gastric', 'duodenal or small-bowel', 'colonic', 'anorectal manometry',
                      'esophageal balloon distension study'):
            with self.subTest(study=study):
                self.assertIn(study, manometry)
                self.assertNotIn(study, pressure)
        self.assertNotIn('manometry', pressure)
        self.assertFalse([line for line in BEFORE_RULINGS[:1] if line in kinds])
        # the control: the line as 1b wrote it named both kinds and defined neither
        self.assertRaises(ValueError, meaning, BEFORE_RULINGS[0], 'manometry')
        self.assertRaises(ValueError, meaning, BEFORE_RULINGS[0], 'pressure_measurement')

    def test_d214_the_motility_and_anorectal_session_kinds_are_disjoint(self):
        from studio.interpretation.contract import extract_prompt as xp
        sessions = xs.DEFINITIONS[ct.SessionKind]
        for ruled in (MOTILITY, ANORECTAL):
            with self.subTest(ruled=ruled[:30]):
                self.assertEqual(sessions.count(ruled), 1)
                self.assertEqual(xp.INSTRUCTIONS_2.count(ruled), 1)
        motility, anorectal = meaning(sessions, 'motility'), meaning(sessions, 'anorectal')
        # motility names its four organs and sets anorectal testing apart; anorectal takes anorectal manometry
        for organ in ('the esophagus', 'the stomach', 'the small bowel', 'the colon'):
            with self.subTest(organ=organ):
                self.assertIn(organ, motility)
                self.assertNotIn(organ, anorectal)
        self.assertTrue(motility.endswith('never anorectal testing'))
        self.assertEqual(anorectal, 'anorectal testing, anorectal manometry included')
        self.assertFalse([line for line in BEFORE_RULINGS[1:] if line in sessions])
        # the control: as 1b wrote them, motility's meaning did not set anorectal testing apart
        self.assertFalse(meaning(BEFORE_RULINGS[1], 'motility').endswith('never anorectal testing'))


# --- the pins, the sizes, and 5.7 measure 4 -----------------------------------------------------------------------------


class PinAndSizeTests(SimpleTestCase):
    def test_the_shas_handed_to_the_integration_owner(self):
        # the two schema pins (INT-5), unchanged by this step's repairs, which are read rules and definitions
        self.assertEqual(jsonschema.sha256_of(xs.LOCAL_SCHEMA_2), LOCAL_SHA256)
        self.assertEqual(jsonschema.sha256_of(xs.RESPONSE_SCHEMA_2), RESPONSE_SHA256)
        # and no third: the definitions have no pin of their own, INSTRUCTIONS_SHA256_V2 covers them (DECISIONS D202)
        self.assertFalse([name for name in dir(interpretation) if 'DEFINITION' in name])
        self.assertTrue(hasattr(interpretation, 'INSTRUCTIONS_SHA256_V2'))  # the control: the pin that covers them

    def test_the_sizes_measured(self):
        measured = {'local': len(jsonschema.canonical(xs.LOCAL_SCHEMA_2)),
                    'response': len(jsonschema.canonical(xs.RESPONSE_SCHEMA_2)),
                    'fact_nodes': sum(1 for _, node in nodes(xs.LOCAL_SCHEMA_2) if is_fact(node)),
                    'source_nodes': sum(1 for _, node in nodes(xs.LOCAL_SCHEMA_2) if node['type'] == 'object'
                                        and list(node['properties']) == SOURCE_KEYS),
                    'enum_sites': sum(1 for _, node in nodes(xs.LOCAL_SCHEMA_2) if 'enum' in node),
                    'depth': depth(xs.LOCAL_SCHEMA_2)}
        self.assertEqual(measured, SIZES)
        v1 = len(schema.canonical(schema.RESPONSE_SCHEMA))  # computed from v1, read only
        self.assertEqual(v1, 12_044)
        self.assertEqual(round(measured['response'] / v1, 1), 7.9)  # DECISIONS D203: measured at D1 before compaction


class MeasureFourTests(SimpleTestCase):
    def test_the_module_keeps_measure_4_with_its_one_pinned_output_table(self):
        source = (CONTRACT / 'extract_schema.py').read_text(encoding='utf-8')
        tree = ast.parse(source)
        statement = next(node for node in tree.body if isinstance(node, ast.AnnAssign)
                         and getattr(node.target, 'id', '') == 'DEFINITIONS')
        table = next(node for node in ast.walk(statement) if isinstance(node, ast.Dict))
        findings = measure_4(source, engine=False)
        # exactly one finding, and it is the definitions' table: every other module-level collection holds no string
        # literal (the schema is built in a function, the tables over enumeration members)
        self.assertEqual(findings, [f'a module-level word list at line {table.lineno}'])

    def test_the_rule_still_sees_a_plant(self):
        planted = (CONTRACT / 'extract_schema.py').read_text(encoding='utf-8') + "\nMARKERS = ('no', 'not')\n"
        self.assertEqual(sum('a module-level word list' in finding for finding in measure_4(planted, engine=False)),
                         2)
        self.assertIn('imports re', measure_4('import re\n', engine=False))
