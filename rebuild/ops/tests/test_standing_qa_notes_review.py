"""Prospective mapping metadata only; original source, field positions and scoring remain frozen."""
from copy import deepcopy
import json
import unittest
from types import SimpleNamespace

from ops import provider_campaign as pc, standing_qa_notes_review as nr


class ProspectiveNotesMappingReview(unittest.TestCase):
    def setUp(self):
        self.row = json.loads(nr.MANIFEST.read_text())
        self.inputs = {'cases':json.loads((nr.MANIFEST.parents[3] / 'docs/rebuild/v1/sonnet5-campaign/diagnostics/notes/cases.json').read_text())}

    def test_only_explicit_protection_changes_and_frozen_expectations_stay_unchanged(self):
        before = deepcopy(self.inputs)
        current = nr.inputs_with_review(self.inputs, self.row)
        self.assertEqual(self.inputs, before)
        self.assertEqual(current['cases']['cases'], before['cases']['cases'])
        old = before['cases']['forms']['r1-11']['fields']
        new = current['cases']['forms']['r1-11']['fields']
        self.assertEqual(current['original_frozen_notes_fields']['r1-11'], old)
        self.assertEqual(len(old), len(new))
        for a,b in zip(old,new):
            if a['key'] != 'v3_10':self.assertEqual(a,b)
            else:self.assertEqual(b,{**a,'write_protected':True,'review_reason':self.row['review_reason']})

    def test_changed_source_or_old_field_is_refused(self):
        for change in ('source','label','already_protected'):
            data = deepcopy(self.inputs)
            form = data['cases']['forms']['r1-11']
            if change == 'source':form['sha256'] = '0'*64
            else:
                field = next(f for f in form['fields'] if f['key']=='v3_10')
                if change == 'label':field['label']='Other consent'
                else:field['write_protected']=True
            with self.subTest(change=change),self.assertRaises(pc.Refused):
                nr.inputs_with_review(data,self.row)

    def test_additional_or_changed_issue_or_mapping_cannot_be_approved(self):
        fields = nr.inputs_with_review(self.inputs,self.row)['cases']['forms']['r1-11']['fields']
        template = SimpleNamespace(sha256=self.row['source_sha256'])
        coverage = {'automatic_complete':False,'block_generation':True,'selected_engine_issues':[{
            'id':self.row['issue_id'],'part':self.row['part'],'slot':self.row['slot'],'code':'human_signing_action'}]}
        version = SimpleNamespace(fields=fields,import_manifest={'coverage':coverage})
        nr.assert_reviewable(template,version,self.row,fields)
        for change in ('id','slot','code','extra','complete','quarantine','mapping'):
            v = deepcopy(version)
            c = v.import_manifest['coverage']
            if change in ('id','slot','code'):c['selected_engine_issues'][0][change]='changed'
            elif change=='extra':c['selected_engine_issues'].append(deepcopy(c['selected_engine_issues'][0]))
            elif change=='complete':c['automatic_complete']=True
            elif change=='quarantine':c['layout_quarantine']=True
            else:v.fields[0]['label']='changed'
            with self.subTest(change=change),self.assertRaises(pc.Refused):
                nr.assert_reviewable(template,v,self.row,fields)
