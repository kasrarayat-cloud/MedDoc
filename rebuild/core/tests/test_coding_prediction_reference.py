"""Bounded direct-prediction reference closure; no provider calls.

Pure retained-fixture controls run without a database. PostgreSQL controls
exercise the actual JSON projection separately against synthetic references.
"""
from copy import deepcopy
from datetime import date
import hashlib
import json
from types import SimpleNamespace as N
from unittest import skipUnless
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import connection
from django.test import SimpleTestCase, TestCase
from django.test.utils import CaptureQueriesContext

from core import coding_engine as engine, coding_reference_store as store, corti_coding
from core.corti_response import CatalogRelease, DatedTerminology
from core.coding_terminology import reference_digest, validate_code
from core.models import CodeSet, CodingRelease
from core.tests.test_coding_reference_store import fixture
from core.tests import test_coordinated_coding as elias, test_coding_exception_scope as iris


class MemoryProjection:
    """Instrumented authority fixture, not a replacement for SQL controls."""
    def __init__(self, metadata):
        self.full = metadata.full
        self.total_bytes = 0
        self.calls = []

    def bounded(self, value):
        size = len(json.dumps(value).encode())
        self.total_bytes += size
        if size > store.MAX_QUERY_BYTES or self.total_bytes > store.MAX_TOTAL_BYTES:
            raise ValidationError('Projection byte bound reached.')
        return deepcopy(value)

    def read(self, expression, params=()):
        self.calls.append((expression, params))
        tabular = self.full['tabular']
        if "'format', tabular->'format'" in expression:
            return self.bounded({k:v for k,v in tabular.items() if k not in ('codes', 'nodes')})
        if "entry->>'code' = ANY" in expression:
            codes = set(params[0])
            return self.bounded([e for e in self.full['index'] if e['code'] in codes])
        if 'WITH ORDINALITY' in expression:
            return self.bounded([{'id':e['id'], 'term':e['term'], 'code':e['code'],
                'description':tabular['codes'].get(e['code'], '')}
                for e in self.full['index'] if e['parent_id'] is None])
        if 'jsonb_each' in expression:
            wanted, bases = params
            return self.bounded({k:v for k,v in tabular['codes'].items() if k in wanted
                or any(k == base or len(k.replace('.', '')) == 7 and k.startswith(base) for base in bases)})
        if "tabular->'codes'->wanted" in expression:
            return self.bounded({k:v for k,v in tabular['codes'].items() if k in params[0]})
        raise AssertionError('Unexpected projection expression: '+expression)

    def index(self, identities):
        rows = [e for e in self.full['index'] if e['id'] in identities]
        if len(rows) > store.MAX_IDENTITIES or {e['id'] for e in rows} != identities:
            raise ValidationError('Invalid Index projection.')
        return {e['id']:e for e in self.bounded(rows)}

    def nodes(self, identities):
        return self.bounded({k:v for k,v in self.full['tabular']['nodes'].items() if k in identities})

    def children(self, parents):
        rows = [e for e in self.full['index'] if e['parent_id'] in parents]
        if len(rows) > store.MAX_IDENTITIES:
            raise ValidationError('Oversized child projection.')
        return {e['id']:e for e in self.bounded(rows)}


def projected(full, codes, contract=engine.CURRENT_SOURCE_CONTRACT):
    metadata = N(pk='reference', release_id='release', digest='digest',
        release=N(version='FY2027'), full=full)
    with patch.object(store, '_Projection', MemoryProjection):
        return store.prediction_reference(metadata, codes, source_contract=contract)


class PredictionProjectionTests(SimpleTestCase):
    def test_invalid_or_oversized_codes_refuse_before_reading_reference(self):
        for value in (None, (), 'R12', [None], ['r12'], ['R12', 'R12'], ['R12']*65, ["R12' OR true"]):
            with self.subTest(value=value), patch.object(store, '_Projection') as projection:
                with self.assertRaises(ValidationError): store.prediction_reference(None, value)
                projection.assert_not_called()

    def test_empty_selection_reads_no_index_or_code_catalogue(self):
        full = fixture()
        sparse = projected(full, [])
        self.assertEqual(sparse.index, [])
        self.assertEqual(sparse.tabular['codes'], {})
        self.assertEqual(sparse.tabular['nodes'], {})
        self.assertLess(sparse.projection_bytes, 4096)

    def test_complete_subtypes_alias_roots_and_original_index_order_are_preserved(self):
        full = fixture()
        root = next(e for e in full['index'] if e['code']=='A00.0')
        extra = deepcopy(root)
        extra.update(id='idx:'+hashlib.sha256(b'other-lexical-root').hexdigest(), code='A01.0', children=[])
        full['index'].insert(0, extra)
        sparse = projected(full, ['A00.0'])
        self.assertIn(extra['id'], sparse._index_lookup)
        self.assertEqual([e['id'] for e in sparse.index],
            [e['id'] for e in full['index'] if e['id'] in sparse._index_lookup])
        self.assertEqual(engine.index_subtypes(sparse, {'term':'Synthetic alpha', 'index_terms':[]},
            source_contract=engine.CURRENT_SOURCE_CONTRACT), engine.index_subtypes(N(**full),
            {'term':'Synthetic alpha', 'index_terms':[]}, source_contract=engine.CURRENT_SOURCE_CONTRACT))
        self.assertEqual(sparse.tabular['codes']['A00.1'], full['tabular']['codes']['A00.1'])
        self.assertEqual(validate_code(sparse, 'A00.0', ['A00.0','A00.1']),
            validate_code(full, 'A00.0', ['A00.0','A00.1']))

    def test_retained_elias_and_iris_complete_results_equal_full_reference_for_each_contract(self):
        for module in (elias, iris):
            full = deepcopy(module.FIXTURE['reference'])
            full['release'] = N(**full['release'])
            full_reference = N(**full)
            terms = DatedTerminology([CatalogRelease('icd10cm-outpatient', full['release'].version,
                date(2026,10,1), date(2027,9,30), full['release'].source_url, full['release'].sha256,
                full['tabular']['codes'], full['release'].source_url)])
            codes = [row['code'] for row in module.RAW['codes'] if row['system']=='icd10cm-outpatient']
            for contract in (None, engine.SOURCE_CONTRACT, engine.CURRENT_SOURCE_CONTRACT):
                sparse = projected(full, codes, contract)
                sparse.release, sparse.release_id = full_reference.release, full_reference.release_id
                current = elias.run(module.FIXTURE['notes'])
                current.inputs['patient_identity']['display_name'] = ('Synthetic Iris Vale' if module is iris else 'Synthetic Elias Mercer')
                current.config = {'mode':'live', 'provider':'corti', **({'clinical_source_contract':contract} if contract else {})}
                values = []
                for reference in (full_reference, sparse):
                    with patch.object(corti_coding, 'terminology', return_value=(terms, {'available':False})), \
                         patch.object(engine, 'reference_for', return_value=reference) as get_reference:
                        values.append(corti_coding.retained_result(current, module.FIXTURE['request'],
                            module.RAW, module.FIXTURE['provenance']['original_response_sha256']))
                        get_reference.assert_called_once_with(current, prediction_codes=codes)
                with self.subTest(case=module.__name__, contract=contract):
                    self.assertEqual(values[0], values[1])
                    self.assertLess(sparse.projection_bytes, store.MAX_TOTAL_BYTES)

    def test_full_source_and_specificity_refusals_do_not_disappear_in_projection(self):
        full = deepcopy(elias.FIXTURE['reference']);full['release'] = N(**full['release'])
        sparse = projected(full, ['R19.7'])
        sparse.release_id, sparse.release = full['release_id'], full['release']
        for quote in ('Diarrhea was evaluated today.', 'The patient has functional diarrhea.',
                      'The patient denies diarrhea.', 'The patient has infectious diarrhea.',
                      'Diarrhea is a possibility only, not an established symptom.',
                      'The patient was evaluated for diarrhea last year.'):
            notes = 'Patient: Synthetic Elias Mercer\nAssessment:\n'+quote
            run = elias.run(notes);proposal = elias.selected('R19.7', quote, notes)
            with self.subTest(quote=quote):
                self.assertEqual(corti_coding._icd_source(run, N(**full), proposal, ['R19.7']),
                    corti_coding._icd_source(run, sparse, proposal, ['R19.7']))

    def test_missing_duplicate_cycle_foreign_parent_and_depth_refuse(self):
        original = fixture()
        for kind in ('missing','unlisted','duplicate','cycle','parent','depth'):
            full = deepcopy(original)
            root = next(e for e in full['index'] if e['code']=='A00.0')
            child = next(e for e in full['index'] if e['code']=='A00.1')
            if kind=='missing': full['index'].remove(child)
            elif kind=='unlisted': root['children'] = []
            elif kind=='duplicate': root['children'] *= 2
            elif kind=='cycle': child['children'] = [root['id']]
            elif kind=='parent': child['parent_id'] = 'idx'+'0'*64
            with self.subTest(kind=kind), patch.object(store,'MAX_DEPTH',1 if kind=='depth' else store.MAX_DEPTH):
                with self.assertRaises(ValidationError): projected(full,['A00.0'])

    def test_byte_and_identity_bounds_refuse_without_fallback(self):
        for option, value in [('MAX_QUERY_BYTES',128),('MAX_TOTAL_BYTES',128),('MAX_IDENTITIES',1)]:
            with self.subTest(option=option), patch.object(store, option, value), \
                 patch.object(engine, '_loaded_reference', side_effect=AssertionError('No full fallback')):
                with self.assertRaises(ValidationError): projected(fixture(), ['A00.0'])


@skipUnless(connection.vendor=='postgresql', 'Actual PostgreSQL JSON operators are required.')
class PredictionProjectionPostgresTests(TestCase):
    def setUp(self):
        self.full = fixture()
        self.release = CodeSet.objects.create(system='ICD-10-CM', version='SYNTHETIC-PREDICTION',
            effective_from=date(2026,10,1), effective_until=date(2027,9,30),
            source_url='https://example.invalid/synthetic-reference', sha256='b'*64)
        row = CodingRelease.objects.create(release=self.release, **self.full,
            provenance={'fixture':True}, digest=reference_digest(self.full))
        self.metadata = CodingRelease.objects.only('release_id','digest').select_related('release').get(pk=row.pk)

    def test_actual_sql_matches_complete_in_memory_projection(self):
        for codes in ([], ['A00.0'], ['A00.0','A00.1'], ['S00.0XXA'], ['R12']):
            with self.subTest(codes=codes), CaptureQueriesContext(connection) as captured:
                actual = store.prediction_reference(self.metadata, codes, source_contract=engine.CURRENT_SOURCE_CONTRACT)
                expected = projected(self.full, codes)
                self.assertEqual(actual.index, expected.index)
                self.assertEqual(actual.tabular, expected.tabular)
                self.assertTrue(all('octet_length(payload::text)' in q['sql'] for q in captured))
                self.assertTrue({'index','tabular','provenance'} <= self.metadata.get_deferred_fields())

    def test_engine_direct_projection_never_enters_full_release_cache(self):
        run=N(releases=[{'system':'ICD-10-CM','id':str(self.release.pk),'coding_digest':self.metadata.digest,
            'sha256':self.release.sha256}],inputs={'service_date':'2026-10-17'},
            config={'clinical_source_contract':engine.CURRENT_SOURCE_CONTRACT})
        with patch.object(engine,'_loaded_reference',side_effect=AssertionError('Full reference cache accessed')):
            actual=engine.reference_for(run,prediction_codes=['A00.0'])
        self.assertIn('A00.0',actual.tabular['codes'])

    def test_changed_binding_and_server_or_cumulative_overflow_refuse(self):
        changed=deepcopy(self.metadata);changed.digest='0'*64
        with self.assertRaises(ValidationError):store.prediction_reference(changed,['A00.0'])
        for option in ('MAX_QUERY_BYTES','MAX_TOTAL_BYTES'):
            with self.subTest(option=option),patch.object(store,option,128),self.assertRaises(ValidationError):
                store.prediction_reference(self.metadata,['A00.0'])

    def test_large_unrelated_entries_do_not_transfer_but_complete_target_scope_does(self):
        full=deepcopy(self.full)
        next(row for row in full['index'] if row['code']=='A01.0')['unrelated_padding']='x'*(1024*1024)
        full['tabular']['nodes']['A01.0']['unrelated_padding']='y'*(1024*1024)
        release=CodeSet.objects.create(system='ICD-10-CM',version='SYNTHETIC-PREDICTION-LARGE',
            effective_from=date(2026,10,1),effective_until=date(2027,9,30),
            source_url='https://example.invalid/synthetic-reference',sha256='c'*64)
        row=CodingRelease.objects.create(release=release,**full,digest=reference_digest(full))
        metadata=CodingRelease.objects.only('release_id','digest').select_related('release').get(pk=row.pk)
        sparse=store.prediction_reference(metadata,['A00.0'])
        self.assertLess(sparse.projection_bytes,48*1024)
        self.assertNotIn('A01.0',sparse.tabular['codes'])
        self.assertIn('A00.1',sparse.tabular['codes'])
        self.assertEqual(validate_code(sparse,'A00.0',['A00.0','A00.1']),
            validate_code(full,'A00.0',['A00.0','A00.1']))
