"""Real isolated import + physical export controls, using synthetic editable originals."""
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile
from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from lxml import etree
from django.test import override_settings
from .service import DocumentError, engine_fingerprint, fill_template, inspect_template


class ImportSelection(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def save(self, document):
        path = self.root/'original.docx'
        document.save(path)
        return path

    def simple(self):
        doc=Document();table=doc.add_table(rows=2,cols=2)
        table.cell(0,0).text='Reason for visit';table.cell(1,0).text='Plan'
        return doc

    def test_complete_simple_table_keeps_legacy_identical_fields(self):
        path=self.save(self.simple());old=inspect_template(path,engine='legacy');new=inspect_template(path,engine='auto')
        self.assertEqual(new['fields'],old['fields'])
        self.assertEqual(new['import_manifest']['engine'],'legacy')
        self.assertEqual(new['import_manifest']['source_sha256'],hashlib.sha256(path.read_bytes()).hexdigest())
        self.assertFalse(new['import_manifest']['coverage']['automatic_complete'])

    @override_settings(QUILLMD_WORD_AUTO_PREFER_V3=True)
    def test_new_ordinary_preference_requires_exact_parity_and_keeps_existing_legacy_fill(self):
        path=self.save(self.simple());old=inspect_template(path,engine='legacy');new=inspect_template(path,engine='auto')
        self.assertEqual(new['import_manifest']['engine'],'v3')
        self.assertTrue(new['import_manifest']['coverage']['new_import_v3_preference']['exact_ordinary_parity'])
        self.assertEqual([f['label'] for f in new['fields']],[f['label'] for f in old['fields']])
        output=self.root/'old-mapping.docx';fill_template(path,old['fields'],{'cell_0':'SYNTHETIC existing encounter'},output)
        self.assertEqual(Document(output).tables[0].cell(0,1).text,'SYNTHETIC existing encounter')
        self.assertNotIn('contract',inspect_template(path,engine='legacy'))

    @override_settings(QUILLMD_WORD_AUTO_PREFER_V3=True)
    def test_preference_does_not_drop_governing_context_roles_or_owner_contract(self):
        owner=Path(__file__).with_name('__fixtures__')/'Colonoscopy_Operative_Template.docx'
        self.assertEqual(inspect_template(owner,engine='auto')['import_manifest']['engine'],'legacy')
        for case in ('context','signing'):
            with self.subTest(case=case):
                doc=self.simple()
                if case=='context':
                    heading=doc.add_paragraph('Family history',style='Heading 1')
                    doc._body._body.insert(0,heading._p)
                else:doc.tables[0].cell(0,0).text='Parent attestation:'
                result=inspect_template(self.save(doc),engine='auto')
                self.assertEqual(result['import_manifest']['engine'],'legacy')
                self.assertFalse(result['import_manifest']['coverage']['new_import_v3_preference']['exact_ordinary_parity'])

    def test_parity_rejects_wrong_label_kind_context_and_overlapping_or_broader_places(self):
        import copy
        from . import import_selection as selection
        old={'fields':[{'key':'old1','label':'Finding','kind':'text'}, {'key':'old2','label':'Plan','kind':'text'}]}
        places=[('p#cell1',None,None),('p#cell2',None,None)]
        new={'fields':[{'key':'v3_1','label':'Finding','kind':'text','context':'Finding'},
                       {'key':'v3_2','label':'Plan','kind':'long_text','context':'Plan'}]}
        class Reader:
            def of(self,field):return [places[int(field['key'][-1])-1]]
        self.assertTrue(selection.ordinary_parity(old,new,places,Reader()))
        for key,value in (('label','Unrelated finding'),('kind','date'),('context','Father > Finding'),
                          ('answer_policy',{'source_author':'patient'}),('copies',[{'part':'word/header1.xml'}])):
            altered=copy.deepcopy(new);altered['fields'][0][key]=value
            self.assertFalse(selection.ordinary_parity(old,altered,places,Reader()))
        altered=copy.deepcopy(new);altered['fields'][1]['key']='v3_1'
        self.assertFalse(selection.ordinary_parity(old,altered,places,Reader()))
        self.assertFalse(selection.ordinary_parity(old,new,[('p#cell1/p[0]',0,8),places[1]],Reader()))

    def test_explicit_engine_imports_are_bound_and_legacy_omissions_stop_generation(self):
        doc=self.simple();doc.add_paragraph('Current medications: ____________')
        path=self.save(doc)
        for engine in ('legacy','v3'):
            imported=inspect_template(path,engine=engine);bound=imported['import_manifest']
            self.assertEqual(bound['engine'],engine)
            self.assertEqual(bound['engine_code_sha256'],engine_fingerprint(engine))
            self.assertEqual(bound['source_sha256'],hashlib.sha256(path.read_bytes()).hexdigest())
            self.assertEqual(bound['coverage']['block_generation'],engine=='legacy')

    def test_accepting_a_table_does_not_silently_omit_a_paragraph_blank(self):
        doc=self.simple();doc.add_paragraph('Current medications: ____________')
        path=self.save(doc);legacy=inspect_template(path,engine='legacy');selected=inspect_template(path,engine='auto')
        self.assertEqual(len(legacy['fields']),2)
        self.assertEqual(selected['import_manifest']['engine'],'v3',selected['import_manifest'])
        self.assertEqual(len(selected['import_manifest']['coverage']['legacy_omissions']),1)
        self.assertEqual({f['label'] for f in selected['fields']},{'Reason for visit','Plan','Current medications'})
        before=path.read_bytes();out=self.root/'export.docx'
        answers={f['key']:f['label']+' synthetic answer' for f in selected['fields']}
        fill_template(path,selected['fields'],answers,out)
        parsed=Document(out)
        self.assertEqual(parsed.tables[0].cell(0,1).text,'Reason for visit synthetic answer')
        self.assertEqual(parsed.tables[0].cell(1,1).text,'Plan synthetic answer')
        self.assertIn('Current medications synthetic answer',parsed.paragraphs[-1].text)
        self.assertEqual(path.read_bytes(),before)

    def test_owner_colonoscopy_keeps_all_seventeen_legacy_destinations(self):
        path=Path(__file__).with_name('__fixtures__')/'Colonoscopy_Operative_Template.docx'
        old=inspect_template(path,engine='legacy');new=inspect_template(path,engine='auto')
        # The clinical fixture's qualified route answers17 and leaves7 clinical/
        # identity areas held; physical mapping contains all24 original places.
        self.assertEqual(len(old['fields']),24)
        self.assertEqual(new['import_manifest']['engine'],'legacy',new['import_manifest'])
        self.assertEqual(new['fields'],old['fields'])

    def test_headers_footers_and_adjacent_paragraph_fields_are_not_lost(self):
        doc=self.simple();doc.sections[0].header.paragraphs[0].text='Patient name: ______'
        doc.sections[0].footer.paragraphs[0].text='Page note: ______'
        doc.add_paragraph('Right knee: ______   Left knee: ______')
        selected=inspect_template(self.save(doc),engine='auto')
        self.assertEqual(selected['import_manifest']['engine'],'v3')
        labels={f['label'] for f in selected['fields']}
        self.assertTrue({'Patient name','Page note','Right knee','Left knee'}<=labels)

    def test_shared_vertical_answer_is_reported_and_never_chosen_silently(self):
        doc=self.simple();table=doc.add_table(rows=2,cols=2)
        table.cell(0,0).text='Medications';table.cell(1,0).text='Allergies';table.cell(0,1).merge(table.cell(1,1))
        result=inspect_template(self.save(doc),engine='auto')
        self.assertTrue(any('NOT mapped' in warning for warning in result['warnings']))
        self.assertTrue(result['import_manifest']['coverage']['block_generation'])
        self.assertEqual(result['import_manifest']['coverage']['selected_engine_issues'][0]['code'],'shared_merged_answer')
        self.assertFalse(result['import_manifest']['coverage']['automatic_complete'])

    def test_legacy_rejection_routes_a_mixed_checkbox_form_to_v3(self):
        doc=self.simple();doc.add_paragraph('Smoker? ☐ Yes ☐ No')
        path=self.save(doc);result=inspect_template(path,engine='auto')
        self.assertEqual(result['import_manifest']['engine'],'v3')
        choice=next(f for f in result['fields'] if f['label']=='Smoker?')
        self.assertEqual(choice['kind'],'choice')
        output=self.root/'checked.docx';fill_template(path,result['fields'],{choice['key']:'Yes'},output)
        self.assertIn('☒ Yes',Document(output).paragraphs[-1].text)
        self.assertIn('☐ No',Document(output).paragraphs[-1].text)

    def test_protected_and_digitally_signed_originals_are_explicitly_unsupported(self):
        for engine in ('legacy','v3','auto'):
            for shape in ('protected','signed'):
                with self.subTest(engine=engine,shape=shape):
                    doc=self.simple()
                    if shape=='protected':
                        node=OxmlElement('w:documentProtection');node.set(qn('w:enforcement'),'1');node.set(qn('w:edit'),'forms')
                        doc.settings.element.append(node)
                    path=self.save(doc)
                    if shape=='signed':
                        with ZipFile(path,'a') as archive:archive.writestr('_xmlsignatures/sig1.xml','<Signature/>')
                    with self.assertRaises(DocumentError) as caught:inspect_template(path,engine=engine)
                    self.assertEqual(caught.exception.code,shape+'_document')

    def test_scanned_or_empty_document_cannot_earn_automatic_support(self):
        path=self.save(Document())
        with self.assertRaises(DocumentError) as caught:inspect_template(path,engine='auto')
        self.assertEqual(caught.exception.code,'no_fields')

    def test_words_before_boxes_are_known_source_bound_exclusions_before_generation(self):
        doc=Document();doc.add_paragraph('Gender: Male☐Female☐');doc.add_paragraph('Reason for visit: ____________')
        result=inspect_template(self.save(doc),engine='auto')
        self.assertEqual([f['label'] for f in result['fields']],['Reason for visit'])
        coverage=result['import_manifest']['coverage']
        self.assertTrue(coverage['block_generation'])
        self.assertEqual(len(coverage['selected_engine_issues']),1)
        self.assertEqual(coverage['selected_engine_issues'][0]['slot'],'b/p[0]')
        self.assertIn('printed before each box',coverage['selected_engine_issues'][0]['detail'])

    def test_separate_checkbox_write_ins_are_never_silently_counted_covered(self):
        doc=Document();doc.add_paragraph('Symptoms (tick all that apply): ☐ Pain ☐ Other: ______ and ______')
        result=inspect_template(self.save(doc),engine='auto')
        coverage=result['import_manifest']['coverage']
        self.assertTrue(coverage['block_generation'])
        issues=[i for i in coverage['selected_engine_issues'] if i['code']=='unmapped_checkbox_write_in']
        self.assertEqual(len(issues),2)
        self.assertTrue(all(i['start']<i['end'] for i in issues))
        self.assertFalse(coverage['automatic_complete'])

    def test_unresolved_structural_answers_remain_reviewable_and_held_even_with_zero_fields(self):
        from .test_question_boxes import TabColumnOwnership
        from . import word_v3
        for many in (False,True):
            path=self.save(TabColumnOwnership().form(many=many))
            with patch('documents.layout_transport.verify_document',
                       side_effect=DocumentError('Synthetic renderer unavailable.','layout_unavailable')):
                imported=inspect_template(path,engine='v3')
            self.assertEqual(imported['contract'],word_v3.CONTRACT)
            self.assertEqual(imported['fields'],[])
            self.assertFalse(imported['import_manifest']['coverage']['automatic_complete'])
            if many:
                self.assertTrue(imported['import_manifest']['coverage']['block_generation'])
                self.assertTrue(imported['import_manifest']['coverage']['selected_engine_issues'])
            else:
                self.assertGreater(imported['layout_pending'],0)
            automatic=inspect_template(path,engine='auto')
            self.assertEqual(automatic['import_manifest']['engine'],'legacy')
            self.assertTrue(automatic['import_manifest']['coverage']['block_generation'])
