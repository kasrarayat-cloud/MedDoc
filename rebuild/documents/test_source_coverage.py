"""Physical source ambiguities stay explicit before paid generation.

These controls do not promote instruction lists or printed alternatives into
clinical answers. Long answer reflow is limited to the actual written row.
"""
import io
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from lxml import etree

from . import word_v3
from .service import inspect_template


def data(doc):
    out=io.BytesIO();doc.save(out);return out.getvalue()


def numbered(doc,text,number_id,format):
    numbering=doc.part.numbering_part.element
    if numbering.find(qn('w:num')+f"[@{qn('w:numId')}='{number_id}']") is None:
        abstract=OxmlElement('w:abstractNum');abstract.set(qn('w:abstractNumId'),str(number_id))
        level=OxmlElement('w:lvl');level.set(qn('w:ilvl'),'0')
        for tag,value in (('w:start','1'),('w:numFmt',format),('w:lvlText','%1)')):
            node=OxmlElement(tag);node.set(qn('w:val'),value);level.append(node)
        abstract.append(level);numbering.append(abstract)
        num=OxmlElement('w:num');num.set(qn('w:numId'),str(number_id))
        node=OxmlElement('w:abstractNumId');node.set(qn('w:val'),str(number_id));num.append(node);numbering.append(num)
    p=doc.add_paragraph(text);num=OxmlElement('w:numPr')
    for tag,value in (('w:ilvl','0'),('w:numId',str(number_id))):
        node=OxmlElement(tag);node.set(qn('w:val'),value);num.append(node)
    p._p.get_or_add_pPr().append(num)
    return p


class SourceCoverage(unittest.TestCase):
    def inspect(self,doc):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'original.docx';path.write_bytes(data(doc))
            return inspect_template(path,engine='v3')

    def test_unpunctuated_numbered_lists_require_exact_review_without_invented_choices(self):
        for title,items in (('Gender',('Male','Female','Other')),
                            ('Discharge instructions',('Call clinic','Keep wound dry'))):
            with self.subTest(title=title):
                doc=Document();numbered(doc,title,90,'decimal')
                for item in items:numbered(doc,item,91,'lowerLetter')
                doc.add_paragraph('Reason for visit: ______')
                result=self.inspect(doc)
                self.assertEqual([f['label'] for f in result['fields']],['Reason for visit'])
                issues=result['import_manifest']['coverage']['selected_engine_issues']
                self.assertEqual(len(issues),1+len(items))
                self.assertEqual({i['code'] for i in issues},{'unclassified_response_list'})
                self.assertEqual({i['slot'] for i in issues},{f'b/p[{i}]' for i in range(1+len(items))})
                self.assertTrue(result['import_manifest']['coverage']['block_generation'])

    def test_explicit_question_keeps_qualified_lettered_choices(self):
        doc=Document();doc.add_paragraph('Which knee was examined?')
        for item in ('Left knee','Right knee'):numbered(doc,item,91,'lowerLetter')
        result=self.inspect(doc)
        choice=next(f for f in result['fields'] if f['label']=='Which knee was examined?')
        self.assertEqual((choice['kind'],choice['options']),('choice',['Left knee','Right knee']))
        self.assertFalse(result['import_manifest']['coverage'].get('selected_engine_issues'))

    def test_bare_factor_list_is_held_without_creating_blanks(self):
        doc=Document();doc.add_paragraph('History of associated factors:')
        doc.add_paragraph('a) Hypertension');doc.add_paragraph('b) Peripheral arterial disease')
        doc.add_paragraph('Reason for visit: ______')
        result=self.inspect(doc)
        self.assertEqual([f['label'] for f in result['fields']],['Reason for visit'])
        issues=result['import_manifest']['coverage']['selected_engine_issues']
        self.assertEqual([i['slot'] for i in issues],['b/p[0]','b/p[1]','b/p[2]'])

    def test_literal_lists_do_not_depend_on_parent_punctuation_or_casing(self):
        for title in ('Gender','Gender.','Gender:','Instructions'):
            for prefix in ('a)','A)'):
                with self.subTest(title=title,prefix=prefix):
                    doc=Document();doc.add_paragraph(title)
                    doc.add_paragraph(prefix+' Male');doc.add_paragraph(('b)' if prefix=='a)' else 'B)')+' Female')
                    doc.add_paragraph('Reason: ______');result=self.inspect(doc)
                    self.assertEqual([f['label'] for f in result['fields']],['Reason'])
                    self.assertEqual(len(result['import_manifest']['coverage']['selected_engine_issues']),3)
                    self.assertTrue(result['import_manifest']['coverage']['block_generation'])

    def test_list_does_not_bridge_a_table_or_unrelated_numbering(self):
        doc=Document();numbered(doc,'Instructions',90,'decimal');numbered(doc,'One item',91,'lowerLetter')
        doc.add_table(rows=1,cols=1).cell(0,0).text='Fixed boundary'
        numbered(doc,'Separate item',91,'lowerLetter');doc.add_paragraph('Reason: ______')
        result=self.inspect(doc)
        self.assertFalse([i for i in result['import_manifest']['coverage'].get('selected_engine_issues',[])
                          if i['code']=='unclassified_response_list'])

    def test_printed_pronoun_alternatives_are_exact_unwritable_source_ranges(self):
        doc=Document();doc.add_paragraph('The care received was right for [me/us].')
        doc.add_paragraph('Reason: ______')
        result=self.inspect(doc);self.assertEqual([f['label'] for f in result['fields']],['Reason'])
        issue=result['import_manifest']['coverage']['selected_engine_issues'][0]
        self.assertEqual(issue['code'],'printed_bracket_alternatives')
        text=doc.paragraphs[0].text;self.assertEqual(text[issue['start']:issue['end']],'[me/us]')
        self.assertEqual(issue['slot'],'b/p[0]')
        output=word_v3.fill(data(doc),result['fields'],{result['fields'][0]['key']:'Synthetic review'})
        self.assertEqual(Document(io.BytesIO(output)).paragraphs[0].text,text)

    def test_alternative_parts_cannot_escape_through_punctuation_unicode_or_digits(self):
        for alternatives in ('left/right-hand','me/us/other-person',"patient's/carer's",
                             'patient/carer (specify)','mild/moderate/grade 3','α/β','左/右',
                             'patient’s/carer’s','1/2/3'):
            with self.subTest(alternatives=alternatives):
                doc=Document();doc.add_paragraph('Selection: ['+alternatives+']');doc.add_paragraph('Reason: ______')
                result=self.inspect(doc)
                self.assertEqual([f['label'] for f in result['fields']],['Reason'])
                issue=result['import_manifest']['coverage']['selected_engine_issues'][0]
                self.assertEqual(issue['code'],'printed_bracket_alternatives')
                self.assertEqual(doc.paragraphs[0].text[issue['start']:issue['end']],'['+alternatives+']')
                self.assertTrue(result['import_manifest']['coverage']['block_generation'])

    def test_ordinary_placeholders_and_dates_remain_usable(self):
        doc=Document();doc.add_paragraph('Name: [patient name]')
        doc.add_paragraph('Date: [dd/mm/yyyy]');doc.add_paragraph('Plan: [enter left/right]')
        doc.add_paragraph('Printed abbreviation [SDU] and [This page is intentionally left blank]')
        result=self.inspect(doc)
        self.assertFalse(result['import_manifest']['coverage'].get('selected_engine_issues'))
        self.assertEqual({f['label'] for f in result['fields']},{'Name patient name','Date dd/mm/yyyy','Plan enter left/right'})

    def test_long_bracketed_source_is_not_silently_discarded_at_grammar_limit(self):
        for length in (121,2100):
            with self.subTest(length=length):
                doc=Document();doc.add_paragraph('['+'complete this authoring instruction '+'x'*length+']')
                doc.add_paragraph('Reason: ______');result=self.inspect(doc)
                self.assertEqual([f['label'] for f in result['fields']],['Reason'])
                issue=result['import_manifest']['coverage']['selected_engine_issues'][0]
                self.assertEqual(issue['code'],'unmapped_bracketed_source')
                self.assertEqual((issue['start'],issue['end']),(0,len(doc.paragraphs[0].text)))

    def test_inline_writer_expands_only_written_exact_row_and_preserves_neighbor_nodes(self):
        doc=Document();table=doc.add_table(rows=2,cols=1)
        table.cell(0,0).text='Finding: ______';table.cell(1,0).text='Fixed neighboring content'
        for row in table.rows:
            height=OxmlElement('w:trHeight');height.set(qn('w:hRule'),'exact');height.set(qn('w:val'),'180')
            row._tr.get_or_add_trPr().append(height)
        raw=data(doc);result=self.inspect(doc)
        field=next(f for f in result['fields'] if f['label']=='Finding')
        self.assertEqual(field['locator']['target']['type'],'span')
        answer='SYNTHETIC '+'long review '*5
        with self.assertRaises(word_v3.V3Failure):
            word_v3.fill(raw,result['fields'],{field['key']:'SYNTHETIC '+'long review '*60})
        out=word_v3.fill(raw,result['fields'],{field['key']:answer})
        original=Document(io.BytesIO(raw));export=Document(io.BytesIO(out))
        self.assertEqual(export.tables[0].rows[0]._tr.find('.//'+qn('w:trHeight')).get(qn('w:hRule')),'atLeast')
        self.assertEqual(etree.tostring(export.tables[0].rows[1]._tr),etree.tostring(original.tables[0].rows[1]._tr))
        self.assertEqual(export.tables[0].cell(0,0).text,'Finding: '+answer)
        with ZipFile(io.BytesIO(raw)) as before,ZipFile(io.BytesIO(out)) as after:
            self.assertEqual(before.namelist(),after.namelist())
            for name in before.namelist():
                if name!='word/document.xml':self.assertEqual(before.read(name),after.read(name),name)
