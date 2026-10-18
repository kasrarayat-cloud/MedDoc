"""Source-owned discovery exercises real bounded PostgreSQL projections."""
from copy import deepcopy
from unittest import skipUnless
from django.core.exceptions import ValidationError
from django.db import connection
from django.test import TestCase
from core import coding_reference_store as store
from core.tests import test_coding_reference_store as reference_tests


@skipUnless(connection.vendor == 'postgresql', 'Requires PostgreSQL JSON projection.')
class SourceReferenceTests(TestCase):
    setUp = reference_tests.SparseReferencePostgresTests.setUp
    persist = reference_tests.SparseReferencePostgresTests.persist

    def scope(self, terms):
        return {'reference_terms': terms, 'source_sha256': 'a'*64, 'inventory_sha256': 'b'*64}

    def test_empty_provider_set_still_discovers_complete_source_family(self):
        scope = self.scope(['Synthetic alpha'])
        ref = store.prediction_reference(self.reference, [], source_inventory=scope,
            source_contract='source-bound-clinical-coding-v4')
        self.assertEqual({e['code'] for e in ref.index}, {'A00.0', 'A00.1'})
        self.assertEqual(ref.completeness_scope, {
            'contract':'source-reference-closure-v1','source_sha256':'a'*64,
            'inventory_sha256':'b'*64,'terms':['Synthetic alpha'],'complete':True})
        self.assertTrue(any(n['instructions'] for n in ref.tabular['nodes'].values()))

    def test_approved_codes_and_new_source_roots_share_full_instruction_scope(self):
        ref = store.prediction_reference(self.reference, ['A00.0'],
            source_inventory=self.scope(['Unselected condition']), source_contract='source-bound-clinical-coding-v4')
        self.assertEqual({e['code'] for e in ref.index}, {'A00.0', 'A00.1', 'A01.0'})
        self.assertIn('A01.0', ref.tabular['codes'])

    def test_unknown_or_partial_root_never_becomes_an_authoritative_family(self):
        for terms in [['alpha'], ['no matching condition'], ["Synthetic alpha' OR true --"]]:
            ref = store.prediction_reference(self.reference, [], source_inventory=self.scope(terms),
                source_contract='source-bound-clinical-coding-v4')
            self.assertEqual(ref.index, [])
            self.assertEqual(ref.tabular['codes'], {})

    def test_malformed_or_oversized_scope_refuses(self):
        valid = self.scope(['Synthetic alpha'])
        invalid = [None, '', [None], [1]]
        for value in invalid:
            changed = deepcopy(valid); changed['reference_terms'] = value
            with self.assertRaises(ValidationError):
                store.prediction_reference(self.reference, [], source_inventory=changed)
        for terms in [['x']*65, ['x'*181]]:
            with self.assertRaises(ValidationError):
                store.prediction_reference(self.reference, [], source_inventory=self.scope(terms))
