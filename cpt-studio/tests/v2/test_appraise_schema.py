"""contract/appraise_schema.py: the shape pass 2 answers in (docs/gemini-migration/FINAL-V2.md 2.4 and 1.8; step 2c of
8.1). TEXT-ONLY: no network, no provider.

Proved: LOCAL_SCHEMA is 2.4's APPRAISAL field for field, in v1's LOCAL form (every field required, no other allowed);
RESPONSE_SCHEMA derives mechanically and shares no node with it; CPT Studio's own validator accepts a valid answer and
refuses the shapes 2.4 forbids; BOUNDS are 1.8's numbers; the two shas handed to the integration owner; 5.7 measure 4.
"""
from __future__ import annotations

import ast
import copy
from pathlib import Path

from django.test import SimpleTestCase

from studio.interpretation.contract import appraise_schema, jsonschema
from studio.interpretation.contract.types import Attached, Kind, Qualifier2, UnlistedWhat, VerdictValue
from studio.participants import reading
from tests.v2.test_types import measure_4  # step 0b's statement of 5.7 measure 4

APP = Path(__file__).resolve().parents[2]
MODULE = APP / 'studio' / 'interpretation' / 'contract' / 'appraise_schema.py'
# The shas this step hands the integration owner (APPRAISAL_LOCAL_SCHEMA_SHA256, APPRAISAL_RESPONSE_SCHEMA_SHA256).
LOCAL_SHA256 = '526dd4e4116c07ed3e1431759a47ac79d4a4d3e7aba81c3133933abe5da46cbf'
RESPONSE_SHA256 = 'fc83346270c6bc165baba78ed8a731132c7e90f172ad22853b100d085ffbd275'


def valid():
    return {'verdicts': [{'claim': 'K1', 'verdict': 'supports', 'attached': 'yes', 'qualifiers': [],
                          'evidence': ['S1']}],
            'unlisted': [{'units': ['S2'], 'what': 'denial', 'kind': '', 'session': ''}]}


class SchemaTests(SimpleTestCase):
    def test_local_schema_is_2_4s_appraisal(self):
        schema = appraise_schema.LOCAL_SCHEMA
        self.assertEqual(list(schema['properties']), ['verdicts', 'unlisted'])
        verdict = schema['properties']['verdicts']['items']
        self.assertEqual(list(verdict['properties']), ['claim', 'verdict', 'attached', 'qualifiers', 'evidence'])
        self.assertEqual(verdict['properties']['verdict']['enum'], [value.value for value in VerdictValue])
        self.assertEqual(verdict['properties']['verdict']['enum'], ['supports', 'contradicts', 'qualified', 'unclear'])
        self.assertEqual(verdict['properties']['attached']['enum'], ['yes', 'no', 'unclear'])
        self.assertEqual(verdict['properties']['attached']['enum'], [value.value for value in Attached])
        self.assertEqual(verdict['properties']['qualifiers']['items']['enum'], [value.value for value in Qualifier2])
        self.assertEqual(verdict['properties']['evidence'], {'type': 'array', 'items': {'type': 'string'}})
        unlisted = schema['properties']['unlisted']['items']
        self.assertEqual(list(unlisted['properties']), ['units', 'what', 'kind', 'session'])
        self.assertEqual(unlisted['properties']['what']['enum'], ['act', 'denial', 'doubt'])
        self.assertEqual(unlisted['properties']['what']['enum'], [value.value for value in UnlistedWhat])
        self.assertEqual(unlisted['properties']['kind']['enum'], [value.value for value in Kind] + [''])
        self.assertEqual(unlisted['properties']['session'], {'type': 'string'})

    def test_every_object_requires_its_fields_and_forbids_others(self):
        pending = [appraise_schema.LOCAL_SCHEMA]
        objects = 0
        while pending:
            node = pending.pop()
            if node['type'] == 'object':
                objects += 1
                self.assertIs(node['additionalProperties'], False)
                self.assertEqual(node['required'], list(node['properties']))
                pending.extend(node['properties'].values())
            elif node['type'] == 'array':
                pending.append(node['items'])
            else:
                self.assertIn(node['type'], ('string',))
        self.assertEqual(objects, 3)

    def test_the_response_schema_derives_mechanically(self):
        self.assertEqual(appraise_schema.RESPONSE_SCHEMA, jsonschema.gemini_schema(appraise_schema.LOCAL_SCHEMA))
        self.assertEqual(appraise_schema.RESPONSE_SCHEMA['propertyOrdering'], ['verdicts', 'unlisted'])
        derived = jsonschema.gemini_schema(appraise_schema.LOCAL_SCHEMA)
        derived['properties']['verdicts']['items']['properties']['verdict']['enum'].append('agrees')
        self.assertNotIn('agrees', appraise_schema.LOCAL_SCHEMA['properties']['verdicts']['items']['properties'][
            'verdict']['enum'])

    def test_the_validator_accepts_a_valid_answer_and_refuses_the_rest(self):
        self.assertEqual(reading.schema_error(valid(), appraise_schema.LOCAL_SCHEMA, 'the appraisal'), '')
        refused = {
            'an extra field': lambda data: data['verdicts'][0].update(confidence='high'),
            'a missing field': lambda data: data['verdicts'][0].pop('attached'),
            'a verdict off the list': lambda data: data['verdicts'][0].update(verdict='agrees'),
            'a qualifier off the list': lambda data: data['verdicts'][0].update(qualifiers=['certain']),
            'words in evidence': lambda data: data['verdicts'][0].update(evidence=[{'unit': 'S1', 'words': 'x'}]),
            'a kind off the list': lambda data: data['unlisted'][0].update(kind='polypectomy'),
            'free text': lambda data: data.update(notes='I think'),
        }
        for name, change in refused.items():
            with self.subTest(case=name):
                data = valid()
                change(data)
                self.assertNotEqual(reading.schema_error(data, appraise_schema.LOCAL_SCHEMA, 'the appraisal'), '')

    def test_the_bounds_are_1_8s(self):
        self.assertEqual(dict(appraise_schema.BOUNDS), {appraise_schema.Bound.EVIDENCE: 8,
                                                        appraise_schema.Bound.UNLISTED: 32})
        self.assertEqual({bound.value for bound in appraise_schema.Bound}, {'verdicts', 'evidence', 'unlisted'})
        with self.assertRaises(TypeError):
            appraise_schema.BOUNDS[appraise_schema.Bound.EVIDENCE] = 9  # type: ignore[index]

    def test_the_shas_handed_to_the_integration_owner(self):
        self.assertEqual(jsonschema.sha256_of(appraise_schema.LOCAL_SCHEMA), LOCAL_SHA256)
        self.assertEqual(jsonschema.sha256_of(appraise_schema.RESPONSE_SCHEMA), RESPONSE_SHA256)
        changed = copy.deepcopy(appraise_schema.LOCAL_SCHEMA)
        changed['properties']['unlisted']['items']['properties']['what']['enum'].append('plan')
        self.assertNotEqual(jsonschema.sha256_of(changed), LOCAL_SHA256)

    def test_measure_4_holds(self):
        source = MODULE.read_text(encoding='utf-8')
        self.assertEqual(measure_4(source, engine=False), [])
        imported = set()
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.ImportFrom):
                imported.add(node.module)
            elif isinstance(node, ast.Import):
                imported |= {alias.name for alias in node.names}
        self.assertEqual(imported, {'__future__', 'collections.abc', 'enum', 'types', 'typing',
                                    'studio.interpretation.contract', 'studio.interpretation.contract.types'})
