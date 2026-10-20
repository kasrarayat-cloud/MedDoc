"""Offline schema-language equivalence; no provider, settings, or database."""
from copy import deepcopy
import json
import unittest

from anthropic import transform_schema

from core import source_assertion_graph as graph
from core.provider_schema import share_anthropic_schema


def expand(schema):
    """Independent, bounded resolver for only the references this writer emits."""
    definitions = schema.get('$defs', {})

    def resolve(value, active=()):
        if isinstance(value, list):
            return [resolve(child, active) for child in value]
        if not isinstance(value, dict):
            return value
        if '$ref' in value:
            if set(value) != {'$ref'} or not value['$ref'].startswith('#/$defs/'):
                raise AssertionError('Unexpected reference shape')
            name = value['$ref'][len('#/$defs/'):]
            if name in active or name not in definitions:
                raise AssertionError('Recursive or missing reference')
            return resolve(definitions[name], (*active, name))
        return {key: resolve(child, active) for key, child in value.items() if key != '$defs'}

    return resolve(schema)


def count(value, keyword):
    if isinstance(value, dict):
        return int(keyword in value) + sum(count(child, keyword) for child in value.values())
    if isinstance(value, list):
        return sum(count(child, keyword) for child in value)
    return 0


class ProviderSchemaTests(unittest.TestCase):
    def test_actual_extractor_language_and_annotations_are_exact_after_expansion(self):
        source = graph.extraction_schema()
        before = deepcopy(source)
        converted = transform_schema(source)
        converted_before = deepcopy(converted)
        shared = share_anthropic_schema(converted)
        # Exact tree equality preserves required/closed keys, nullable unions,
        # enums, source references, and every SDK constraint description.
        self.assertEqual(expand(shared), converted)
        self.assertEqual(json.dumps(expand(shared)), json.dumps(converted))
        self.assertEqual(source, before)
        self.assertEqual(converted, converted_before)
        self.assertEqual(count(converted, 'anyOf'), 15)
        self.assertEqual(count(shared, 'anyOf'), 9)
        self.assertEqual(len(shared['$defs']), 4)
        self.assertLess(len(json.dumps(shared)), len(json.dumps(converted)) * .75)

    def test_checker_schema_has_the_same_exact_language(self):
        converted = transform_schema(graph.checker_schema())
        self.assertEqual(expand(share_anthropic_schema(converted)), converted)

    def test_installed_sdk_preserves_shared_local_definitions(self):
        shared = share_anthropic_schema(transform_schema(graph.extraction_schema()))
        self.assertEqual(transform_schema(shared), shared)

    def test_different_descriptions_required_keys_and_order_are_not_merged(self):
        first = {'type': 'object', 'properties': {'a': {'type': 'string'}, 'b': {'type': 'integer'}},
                 'required': ['a'], 'additionalProperties': False, 'description': 'First'}
        variants = [first, {**first, 'description': 'Second'}, {**first, 'required': ['b']},
                    {**first, 'properties': dict(reversed(list(first['properties'].items())))}]
        schema = {'type': 'object', 'properties': {str(i): variant for i, variant in enumerate(variants)}}
        self.assertEqual(share_anthropic_schema(schema), schema)

    def test_existing_reference_scopes_and_allof_are_left_unchanged(self):
        repeated = {'type': 'object', 'properties': {'x': {'type': 'string'}}}
        for keyword, value in (('$ref', '#/definitions/x'), ('$defs', {'x': repeated}),
                               ('definitions', {'x': repeated}), ('$id', 'https://example.invalid/schema'),
                               ('$anchor', 'anchor'), ('$dynamicRef', '#anchor'),
                               ('$dynamicAnchor', 'anchor'), ('$recursiveRef', '#'),
                               ('$recursiveAnchor', True), ('allOf', [repeated])):
            with self.subTest(keyword=keyword):
                schema = {'type': 'object', 'properties': {'a': repeated, 'b': repeated,
                                                          'nested': {keyword: value}}}
                result = share_anthropic_schema(schema)
                self.assertEqual(result, schema)
                self.assertIsNot(result, schema)

    def test_defaults_examples_and_const_remain_data(self):
        data = {'type': 'object', 'properties': {'quoted': {'type': 'string'}}, '$ref': 'literal data'}
        child = {'type': 'object', 'properties': {'a': {'type': 'string'}},
                 'default': data, 'examples': [data], 'const': data}
        schema = {'type': 'object', 'properties': {'first': child, 'second': child}}
        shared = share_anthropic_schema(schema)
        self.assertEqual(len(shared['$defs']), 1)
        self.assertEqual(next(iter(shared['$defs'].values())), child)

    def test_parent_and_nested_reuse_has_only_reachable_acyclic_definitions(self):
        leaf = {'type': 'object', 'properties': {'a': {'type': 'string'}}}
        parent = {'anyOf': [{'type': 'null'}, {'type': 'object', 'properties': {'one': leaf, 'two': leaf}}]}
        schema = {'type': 'object', 'properties': {'first': parent, 'second': parent, 'third': leaf}}
        shared = share_anthropic_schema(schema)
        self.assertEqual(expand(shared), schema)
        self.assertEqual(len(shared['$defs']), 3)
        self.assertEqual(share_anthropic_schema(shared), shared)
        self.assertEqual(share_anthropic_schema(schema), shared)
        shared['$defs']['shared_1']['anyOf'][0]['type'] = 'string'
        self.assertEqual(parent['anyOf'][0]['type'], 'null')

    def test_small_and_boolean_schemas_return_independent_unchanged_values(self):
        for schema in (True, False, {'type': 'string'}, {'type': 'object', 'properties': {}}):
            with self.subTest(schema=schema):
                self.assertEqual(share_anthropic_schema(schema), schema)

    def test_reference_overhead_never_enlarges_a_tiny_repeated_schema(self):
        schema = {'type': 'object', 'properties': {'a': {'type': 'object'}, 'b': {'type': 'object'}}}
        result = share_anthropic_schema(schema)
        self.assertEqual(result, schema)
        self.assertIsNot(result, schema)
