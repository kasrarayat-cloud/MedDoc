"""Real PostgreSQL JSON projections over small synthetic reference releases.

These tests perform no provider/network operations and import no real catalogue.
The full official release and web-process RSS are separate operational checks.
"""
from copy import deepcopy
from datetime import date
from types import SimpleNamespace
from unittest import skipUnless
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import connection
from django.test import SimpleTestCase, TestCase
from django.test.utils import CaptureQueriesContext

from core import coding_reference_store as store
from core.coding_terminology import parse_reference, reference_digest, validate_code
from core.models import CodeSet, CodingRelease


def fixture():
    index = '''<ICD10CM.index><version>2027</version><letter>
      <mainTerm><title>Synthetic alpha</title><code>A00.0</code>
        <term><title>specified</title><code>A00.1</code></term></mainTerm>
      <mainTerm><title>Synthetic alias</title><see>Synthetic alpha, specified</see></mainTerm>
      <mainTerm><title>Synthetic injury</title><code>S00.0</code></mainTerm>
      <mainTerm><title>Unselected condition</title><code>A01.0</code></mainTerm>
      </letter></ICD10CM.index>'''
    tabular = '''<ICD10CM.tabular><version>2027</version>
      <chapter><name>1</name><notes><note>Synthetic chapter instruction.</note></notes>
        <section id="A00-A09"><includes><note>Synthetic section inclusion.</note></includes>
          <diag><name>A00</name><desc>Synthetic category</desc>
            <codeFirst><note>Synthetic sequencing instruction.</note></codeFirst>
            <diag><name>A00.0</name><desc>Synthetic alpha</desc>
              <excludes1><note>Synthetic alternative (A00.1)</note></excludes1></diag>
            <diag><name>A00.1</name><desc>Synthetic specified alpha</desc></diag></diag>
          <diag><name>A01.0</name><desc>Unselected condition</desc></diag>
        </section></chapter>
      <chapter><name>19</name><section id="S00-S09"><diag><name>S00</name><desc>Synthetic injury</desc>
        <sevenChrNote><note>Synthetic seventh character requirement.</note></sevenChrNote>
        <sevenChrDef><extension char="A">Synthetic initial</extension><extension char="D">Synthetic subsequent</extension></sevenChrDef>
        <diag><name>S00.0</name><desc>Synthetic injury base without expansion leaf</desc></diag>
      </diag></section></chapter></ICD10CM.tabular>'''
    return parse_reference(index, tabular, {'A00.0':'Synthetic alpha', 'A00.1':'Synthetic specified alpha',
        'A01.0':'Unselected condition', 'S00.0XXA':'Synthetic initial injury', 'S00.0XXD':'Synthetic subsequent injury'})


def saved_selection(reference, choices):
    rows, candidates = [], {}
    for number, (code, entry_code) in enumerate(choices):
        key = f'finding{number}'
        entry = next(e for e in reference['index'] if e['code'] == entry_code)
        rows.append({'id':key, 'system':'ICD-10-CM', 'code':code})
        candidates[key] = [{'entry_id':entry['id'], 'system':'ICD-10-CM', 'code':code,
                            'path':['UNTRUSTED MODEL PATH'], 'description':'UNTRUSTED DESCRIPTION',
                            'instructions':['UNTRUSTED INSTRUCTION'], 'source_aliases':[]}]
    return SimpleNamespace(result={'suggestions':rows, 'candidates':candidates}), {
        'selected_ids':[row['id'] for row in rows], 'overrides':{}}


class SparseReferenceInputTests(SimpleTestCase):
    def test_assertion_scope_ids_are_bound_and_validated_before_reference_reads(self):
        reference=fixture()
        run,selected=saved_selection(reference,[('A00.0','A00.0')])
        child=next(e for e in reference['index'] if e['code']=='A00.1')
        run.result['source_checks']={'finding0':{'index_scope_entry_ids':[child['id']]}}
        self.assertIn(child['id'],store._requested(run,selected)[1])
        for value in ['not-a-list', ["idx:' OR true --"], [None], ['idx:'+'a'*64]*2049]:
            run.result['source_checks']['finding0']['index_scope_entry_ids']=value
            with self.subTest(value=str(value)[:80]),patch.object(store,'_Projection') as projection:
                with self.assertRaises(ValidationError):store.selection_reference(None,run,selected)
                projection.assert_not_called()

    def test_invalid_selection_refuses_before_any_reference_read(self):
        reference = fixture()
        run, selected = saved_selection(reference, [('A00.0','A00.0')])
        invalid = [None, {}, {'selected_ids':'finding0','overrides':{}},
                   {'selected_ids':['finding0','finding0'],'overrides':{}},
                   {'selected_ids':['missing'],'overrides':{}},
                   {'selected_ids':['finding0'],'overrides':{'other':{'code':'A00.1','reason':'x'}}}]
        for value in invalid:
            with self.subTest(value=value), patch.object(store, '_Projection') as projection:
                with self.assertRaises(ValidationError): store.selection_reference(None, run, value)
                projection.assert_not_called()
        for bad in ["idx:' OR true --", 'idx:'+'a'*63, None, True]:
            changed=deepcopy(run);changed.result['candidates']['finding0'][0]['entry_id']=bad
            with self.subTest(entry=bad), patch.object(store, '_Projection') as projection:
                with self.assertRaises(ValidationError): store.selection_reference(None, changed, selected)
                projection.assert_not_called()

    def test_ancestry_cycle_and_missing_parent_refuse(self):
        for initial in [{'a':{'parent':'a'}}, {'a':{'parent':'missing'}}]:
            with self.subTest(initial=initial), self.assertRaises(ValidationError):
                store._ancestors({'a'},initial,lambda _: {},'parent')


@skipUnless(connection.vendor == 'postgresql', 'Real PostgreSQL JSON operators are required.')
class SparseReferencePostgresTests(TestCase):
    def setUp(self):
        self.full = fixture()
        self.reference = self.persist(self.full)

    def persist(self, value):
        release = CodeSet.objects.create(system='ICD-10-CM', version='SYNTHETIC-'+str(CodeSet.objects.count()),
            effective_from=date(2026,10,1), effective_until=date(2027,9,30),
            source_url='https://example.invalid/synthetic-reference', sha256='b'*64)
        row = CodingRelease.objects.create(release=release, **value, provenance={'fixture':True},
                                           digest=reference_digest(value))
        return CodingRelease.objects.only('release_id','digest').select_related('release').get(pk=row.pk)

    def read(self, choices, reference=None, full=None):
        run, selections = saved_selection(full or self.full, choices)
        return store.selection_reference(reference or self.reference, run, selections)

    def test_selected_index_and_complete_tabular_ancestors_match_full_reference(self):
        with CaptureQueriesContext(connection) as captured:
            sparse = self.read([('A00.1','A00.1')])
        leaf = next(e for e in self.full['index'] if e['code']=='A00.1')
        expected = {leaf['id'],leaf['parent_id']}
        self.assertEqual(set(sparse._index_lookup),expected)
        self.assertEqual(sparse.index,[e for e in sparse.index if e in self.full['index']])
        self.assertEqual(set(sparse.tabular['codes']),{'A00.1'})
        self.assertEqual(set(sparse.tabular['nodes']),{'A00.1','A00','section:A00-A09','chapter:1'})
        self.assertEqual(validate_code(sparse,'A00.1',['A00.1']),validate_code(self.full,'A00.1',['A00.1']))
        self.assertTrue(all('octet_length(payload::text)' in q['sql'] for q in captured))
        self.assertEqual((sparse.pk,sparse.id,sparse.release_id,sparse.digest),
                         (self.reference.pk,self.reference.pk,self.reference.release_id,self.reference.digest))
        self.assertIs(sparse.release,self.reference.release)
        self.assertTrue({'index','tabular','provenance'} <= self.reference.get_deferred_fields())

    def test_all_selected_codes_participate_in_inherited_exclusions(self):
        sparse=self.read([('A00.0','A00.0'),('A00.1','A00.1')]); selected=['A00.0','A00.1']
        self.assertEqual(validate_code(sparse,'A00.0',selected),validate_code(self.full,'A00.0',selected))
        self.assertIn('excludes1_selected_code_conflict',validate_code(sparse,'A00.0',selected)['errors'])

    def test_code_file_seventh_character_leaf_uses_real_governing_node(self):
        sparse=self.read([('S00.0XXA','S00.0')])
        self.assertNotIn('S00.0XXA',sparse.tabular['nodes'])
        actual=validate_code(sparse,'S00.0XXA',['S00.0XXA'])
        self.assertEqual(actual,validate_code(self.full,'S00.0XXA',['S00.0XXA']))
        self.assertTrue(actual['valid']);self.assertEqual(actual['governing_node'],'S00.0')

    def test_override_loads_its_candidate_entry_and_not_the_original_description(self):
        run, selected=saved_selection(self.full,[('A00.0','A00.0')])
        _, replacement=saved_selection(self.full,[('A00.1','A00.1')])
        child=next(e for e in self.full['index'] if e['code']=='A00.1')
        run.result['candidates']['finding0'].append({'entry_id':child['id'],'system':'ICD-10-CM','code':'A00.1'})
        selected['overrides']={'finding0':{'code':'A00.1','reason':'Synthetic replacement rationale.'}}
        sparse=store.selection_reference(self.reference,run,selected)
        self.assertEqual(sparse.tabular['codes'],{'A00.1':'Synthetic specified alpha'})
        self.assertIn(child['id'],sparse._index_lookup)

    def test_source_aliases_are_real_stored_entries_and_ancestors(self):
        run,selected=saved_selection(self.full,[('A00.1','A00.1')])
        alias=next(e for e in self.full['index'] if e['title']=='Synthetic alias')
        run.result['candidates']['finding0'][0]['source_aliases']=[alias['id']]
        sparse=store.selection_reference(self.reference,run,selected)
        self.assertEqual(sparse._index_lookup[alias['id']],alias)

    def test_assertion_subtype_scope_survives_sparse_approval_projection(self):
        from core.coding_engine import index_subtypes
        run,selected=saved_selection(self.full,[('A00.0','A00.0')])
        child=next(e for e in self.full['index'] if e['code']=='A00.1')
        run.result['source_checks']={'finding0':{'index_scope_entry_ids':[child['id']]}}
        sparse=store.selection_reference(self.reference,run,selected)
        self.assertEqual(sparse._index_lookup[child['id']],child)
        self.assertEqual(index_subtypes(sparse,{'term':'Synthetic alpha'}),
                         index_subtypes(SimpleNamespace(index=self.full['index']),{'term':'Synthetic alpha'}))
        self.assertEqual(set(sparse.tabular['codes']),{'A00.0'})

    def test_unknown_reportable_code_and_entry_identity_refuse(self):
        run,selected=saved_selection(self.full,[('A00','A00.0')])
        with self.assertRaises(ValidationError):store.selection_reference(self.reference,run,selected)
        run,selected=saved_selection(self.full,[('A00.0','A00.0')])
        run.result['candidates']['finding0'][0]['entry_id']='idx:'+'0'*64
        with self.assertRaises(ValidationError):store.selection_reference(self.reference,run,selected)

    def test_binding_checks_primary_key_code_set_and_digest_on_every_projection(self):
        run,selected=saved_selection(self.full,[('A00.0','A00.0')])
        for field,value in [('digest','0'*64),('release_id','00000000-0000-4000-8000-000000000001'),
                            ('id','00000000-0000-4000-8000-000000000002')]:
            metadata=deepcopy(self.reference);setattr(metadata,field,value)
            with self.subTest(field=field),self.assertRaises(ValidationError):
                store.selection_reference(metadata,run,selected)
        self.assertEqual(CodingRelease.objects.get(pk=self.reference.pk).digest,self.reference.digest)

    def test_broken_index_and_tabular_parent_chains_cannot_drop_instructions(self):
        for kind in ['index_missing','index_cycle','tabular_missing','tabular_cycle']:
            value=deepcopy(self.full)
            if kind.startswith('index'):
                leaf=next(e for e in value['index'] if e['code']=='A00.1')
                leaf['parent_id']=leaf['id'] if kind.endswith('cycle') else 'idx:'+'0'*64
            else:
                value['tabular']['nodes']['A00.1']['parent']='A00.1' if kind.endswith('cycle') else 'missing'
            metadata=self.persist(value)
            with self.subTest(kind=kind),self.assertRaises(ValidationError):
                self.read([('A00.1','A00.1')],reference=metadata,full=value)

    def test_unselected_large_entries_never_transfer_to_application(self):
        value=deepcopy(self.full)
        # Deliberate storage padding, not clinical data or an official entry.
        unselected=next(e for e in value['index'] if e['code']=='A01.0')
        unselected['synthetic_storage_padding']='x'*(1024*1024)
        value['tabular']['nodes']['A01.0']['synthetic_storage_padding']='y'*(1024*1024)
        sparse=self.read([('A00.1','A00.1')],reference=self.persist(value),full=value)
        self.assertLess(sparse.projection_bytes,32*1024)
        self.assertNotIn(unselected['id'],sparse._index_lookup)
        self.assertNotIn('A01.0',sparse.tabular['nodes'])
        self.assertEqual(validate_code(sparse,'A00.1',[]),validate_code(value,'A00.1',[]))

    def test_server_and_cumulative_result_bounds_fail_closed(self):
        for option in ['MAX_QUERY_BYTES','MAX_TOTAL_BYTES']:
            with self.subTest(option=option),patch.object(store,option,128),self.assertRaises(ValidationError):
                self.read([('A00.1','A00.1')])

    def test_empty_or_cpt_only_selection_does_not_load_an_icd_catalogue(self):
        for rows,ids in [([],[]),([{'id':'office','system':'CPT','code':'00000'}],['office'])]:
            run=SimpleNamespace(result={'suggestions':rows,'candidates':{}})
            sparse=store.selection_reference(self.reference,run,{'selected_ids':ids,'overrides':{}})
            self.assertEqual(sparse.index,[])
            self.assertEqual(sparse.tabular['codes'],{})
            self.assertEqual(sparse.tabular['nodes'],{})
            self.assertLess(sparse.projection_bytes,4096)
