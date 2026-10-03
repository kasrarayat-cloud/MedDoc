"""Physical source ambiguities stay explicit before paid generation.

These controls do not promote instruction lists or printed alternatives into
clinical answers. Long answer reflow is limited to the actual written row.
"""
import io
import hashlib
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from zipfile import ZipFile
from unittest.mock import patch

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from lxml import etree

from . import word_v3
from .service import inspect_template
from .test_word_v3 import ff_field


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


class AdjacentCheckboxAnswers(unittest.TestCase):
    def form(self, text, *, native=False, checked=False):
        doc = Document()
        if native:
            doc.add_paragraph('Specify the anatomical site:')
            p = doc.add_paragraph(); ff_field(p, 'checkbox', checked=checked)
            p.add_run(text)
        else:
            doc.add_paragraph(text)
        doc.add_paragraph('Unrelated note: ______')
        return data(doc)

    def fields(self, raw):
        result = word_v3.inspect(raw)
        return result, next(f for f in result['fields'] if f.get('source_questions')
                           and f['source_questions'][0]['relation'] == 'adjacent_checkbox_answer')

    def test_explicit_condition_has_separate_exact_writer_and_never_infers_a_tick(self):
        raw = self.form('Any symptoms? ☐ No ☐ Yes → if yes, describe: ______')
        result, blank = self.fields(raw)
        choice = next(f for f in result['fields'] if f['kind'] == 'choice')
        self.assertEqual(choice['options'], ['No', 'Yes'])
        self.assertEqual(blank['label'], 'if yes, describe:')
        self.assertFalse(result['coverage_issues'])
        self.assertEqual(blank['source_questions'][0]['condition'], 'printed_option')
        for controlling in (None, 'No'):
            answers = {blank['key']: 'Synthetic headache'}
            if controlling is not None: answers[choice['key']] = controlling
            with self.subTest(controlling=controlling), self.assertRaises(word_v3.V3Failure) as error:
                word_v3.fill(raw, result['fields'], answers)
            self.assertEqual(error.exception.code, 'conditional_answer_unselected')
        out = word_v3.fill(raw, result['fields'], {choice['key']: 'Yes', blank['key']: 'Synthetic headache'})
        self.assertEqual(Document(io.BytesIO(out)).paragraphs[0].text,
                         'Any symptoms? ☐ No ☒ Yes → if yes, describe: Synthetic headache')
        self.assertEqual(Document(io.BytesIO(out)).paragraphs[1].text, 'Unrelated note: ______')

    def test_native_other_blank_has_its_own_control_and_preserves_existing_state(self):
        for original_checked in (False, True):
            with self.subTest(original_checked=original_checked):
                raw = self.form(' Other, specify___________', native=True, checked=original_checked)
                result, blank = self.fields(raw)
                choice = next(f for f in result['fields'] if f['kind'] == 'checkbox')
                self.assertEqual(blank['label'], 'Other, specify')
                self.assertEqual(blank['source_questions'][0]['printed_option'], 'Other, specify')
                if not original_checked:
                    with self.assertRaises(word_v3.V3Failure):
                        word_v3.fill(raw, result['fields'], {blank['key']: 'Synthetic location'})
                out = word_v3.fill(raw, result['fields'], {choice['key']: 'checked', blank['key']: 'Synthetic location'})
                index = word_v3.SlotIndex(word_v3.open_package(out))
                self.assertEqual(word_v3.constrained_option_states(index, choice), [True])
                self.assertIn('Other, specifySynthetic location', Document(io.BytesIO(out)).paragraphs[1].text)
                self.assertEqual(Document(io.BytesIO(out)).paragraphs[2].text, 'Unrelated note: ______')
                if original_checked:
                    word_v3.fill(raw, result['fields'], {blank['key']: 'Synthetic location'})

    def test_unit_labelled_answer_does_not_depend_on_adjacent_gender_choice(self):
        raw = self.form('Gender\t\t ☐ Male\t\t☐ Female\t\tAge   ................  years')
        result, blank = self.fields(raw)
        self.assertEqual(blank['label'], 'Age')
        self.assertEqual(blank['source_questions'][0]['condition'], 'independent_unit')
        choice = next(f for f in result['fields'] if f['kind'] == 'choice')
        self.assertEqual(choice['options'], ['Male', 'Female'])
        out = word_v3.fill(raw, result['fields'], {blank['key']: '42'})
        self.assertEqual(Document(io.BytesIO(out)).paragraphs[0].text,
                         'Gender\t\t ☐ Male\t\t☐ Female\t\tAge   42  years')
        self.assertFalse(result['coverage_issues'])

    def test_one_dotted_write_in_preserves_its_printed_option_and_independent_destination(self):
        raw = self.form('☐ Acid\t…………………………..')
        result, blank = self.fields(raw)
        choice = next(f for f in result['fields'] if f['kind'] == 'checkbox')
        self.assertEqual((choice['label'],choice['options'],blank['label']), ('Acid',['Acid'],'Acid'))
        out = word_v3.fill(raw,result['fields'],{choice['key']:'checked',blank['key']:'Synthetic agent'})
        self.assertEqual(Document(io.BytesIO(out)).paragraphs[0].text,'☒ Acid\tSynthetic agent')
        self.assertEqual(Document(io.BytesIO(out)).paragraphs[1].text,'Unrelated note: ______')

    def test_stripped_or_copied_conditional_span_and_changed_owner_are_refused(self):
        raw = self.form('Any symptoms? ☐ No ☐ Yes → if yes, describe: ______')
        result, blank = self.fields(raw)
        choice = next(f for f in result['fields'] if f['kind'] == 'choice')
        for mutate in ('stripped', 'renamed', 'copied', 'widened', 'no_control'):
            with self.subTest(mutate=mutate):
                fields = deepcopy(result['fields']); target = next(f for f in fields if f['key'] == blank['key'])
                if mutate == 'stripped': target.pop('source_questions')
                if mutate == 'renamed': target['label'] = 'Another answer'
                if mutate == 'copied': target['locator']['target']['copies'] = [deepcopy(target['locator'])]
                if mutate == 'widened': target['locator']['target']['start'] = 0
                if mutate == 'no_control': fields.remove(next(f for f in fields if f['key'] == choice['key']))
                with self.assertRaises(word_v3.V3Failure) as error:
                    word_v3.fill(raw, fields, {blank['key']: 'Synthetic description', choice['key']: 'Yes'})
                self.assertEqual(error.exception.code, 'mapping_mismatch')

    def test_two_blanks_and_actual_signing_sources_keep_their_coverage_holds(self):
        for text in ('Any symptoms? ☐ No ☐ Yes → if yes, describe: ____ Location: ____',
                     'Patient signature: ☐ Other, specify_________',
                     'Witness attestation: ☐ No ☐ Yes → if yes, describe: ______',
                     '☐ I certify_________', '☐ We hereby attest_________'):
            with self.subTest(text=text):
                raw = self.form(text); result = word_v3.inspect(raw)
                self.assertFalse([f for f in result['fields'] if f.get('source_questions')
                                  and f['source_questions'][0]['relation'] == 'adjacent_checkbox_answer'])
                self.assertTrue(result['coverage_issues'])
                if 'certify' in text or 'attest' in text:
                    first = result['fields'][0]
                    if first['label'] != 'Unrelated note':
                        forged = deepcopy(first); forged.pop('write_protected', None)
                        with self.assertRaises(word_v3.V3Failure):
                            word_v3.fill(raw, [forged], {forged['key']: 'checked'})


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
                             'patient’s/carer’s','1/2/3','type A/type B','state/local','add/remove',
                             'patient/carer/','patient//carer','patient/\ncarer'):
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
        doc.add_paragraph('Date: [dd/mm/yyyy]');doc.add_paragraph('Plan: [enter clinical plan]')
        doc.add_paragraph('Printed abbreviation [SDU] and [This page is intentionally left blank]')
        result=self.inspect(doc)
        self.assertFalse(result['import_manifest']['coverage'].get('selected_engine_issues'))
        self.assertEqual({f['label'] for f in result['fields']},{'Name patient name','Date dd/mm/yyyy','Plan enter clinical plan'})

    def test_spaced_date_formats_fill_while_spaced_literal_alternatives_stay_held(self):
        for hint in ('DD / MM / YYYY','dd\t/\tmm / yy','MM\u00a0/\u00a0DD / YYYY'):
            with self.subTest(hint=hint):
                doc=Document();doc.add_paragraph('Date: ['+hint+']');result=self.inspect(doc)
                self.assertFalse(result['import_manifest']['coverage'].get('selected_engine_issues'))
                field=result['fields'][0];self.assertEqual(field['kind'],'date')
                out=word_v3.fill(data(doc),result['fields'],{field['key']:'03/14/2026'})
                self.assertEqual(Document(io.BytesIO(out)).paragraphs[0].text,'Date: 03/14/2026')
        doc=Document();doc.add_paragraph('Site: [left / right]');doc.add_paragraph('Reason: ______')
        result=self.inspect(doc);self.assertTrue(result['import_manifest']['coverage']['block_generation'])
        self.assertEqual([f['label'] for f in result['fields']],['Reason'])

    def test_unclosed_slash_source_is_reviewable_without_inventing_an_answer(self):
        doc=Document();doc.add_paragraph('Site: [left/right');doc.add_paragraph('Reason: ______')
        result=self.inspect(doc);self.assertEqual([f['label'] for f in result['fields']],['Reason'])
        issue=result['import_manifest']['coverage']['selected_engine_issues'][0]
        self.assertEqual(issue['code'],'unbalanced_bracketed_source')
        self.assertEqual((issue['start'],issue['end']),(6,len(doc.paragraphs[0].text)))
        out=word_v3.fill(data(doc),result['fields'],{result['fields'][0]['key']:'Synthetic review'})
        self.assertEqual(Document(io.BytesIO(out)).paragraphs[0].text,'Site: [left/right')

    def test_unclosed_slash_before_another_placeholder_keeps_exact_source_and_later_writer(self):
        for suffix,answer in (('Comments: [enter notes]','Synthetic notes'),
                              ('Date: [DD/MM/YYYY]','03/14/2026')):
            with self.subTest(suffix=suffix):
                text='Site: [left/right; '+suffix
                doc=Document();doc.add_paragraph(text);doc.add_paragraph('Reason: ______')
                result=self.inspect(doc);issues=result['import_manifest']['coverage']['selected_engine_issues']
                self.assertEqual(len(issues),1);issue=issues[0]
                self.assertEqual(issue['code'],'unbalanced_bracketed_source')
                later=text.index('[',text.index('[')+1)
                self.assertEqual((issue['start'],issue['end']),(6,later))
                self.assertEqual(text[issue['start']:issue['end']],'[left/right; '+suffix.split('[')[0])
                self.assertTrue(result['import_manifest']['coverage']['block_generation'])
                field=next(f for f in result['fields'] if f['locator']['slot']=='b/p[0]')
                target=field['locator']['target'];self.assertGreaterEqual(target['start'],issue['end'])
                out=word_v3.fill(data(doc),result['fields'],{field['key']:answer})
                exported=Document(io.BytesIO(out))
                self.assertEqual(exported.paragraphs[0].text,text[:later]+answer)
                self.assertEqual(exported.paragraphs[1].text,'Reason: ______')

    def test_closed_alternatives_do_not_consume_the_later_placeholder_or_date(self):
        for suffix,answer in (('Comments: [enter notes]','Synthetic notes'),
                              ('Date: [DD/MM/YYYY]','03/14/2026')):
            with self.subTest(suffix=suffix):
                text='Site: [left/right]; '+suffix
                doc=Document();doc.add_paragraph(text);doc.add_paragraph('Reason: ______')
                result=self.inspect(doc);issues=result['import_manifest']['coverage']['selected_engine_issues']
                self.assertEqual(len(issues),1);issue=issues[0]
                self.assertEqual(issue['code'],'printed_bracket_alternatives')
                self.assertEqual(text[issue['start']:issue['end']],'[left/right]')
                field=next(f for f in result['fields'] if f['locator']['slot']=='b/p[0]')
                out=word_v3.fill(data(doc),result['fields'],{field['key']:answer})
                self.assertEqual(Document(io.BytesIO(out)).paragraphs[0].text,'Site: [left/right]; '+suffix.split('[')[0]+answer)

    def inner_tabs(self):
        doc=Document();p=doc.add_paragraph('Instruction: [identify services before')
        run=p.add_run('\t');run.font.underline=True;p.add_run(' his/her')
        run=p.add_run('\t');run.font.underline=True;p.add_run(' last review]')
        doc.add_paragraph('Reason: ______')
        return doc

    def test_all_blank_shapes_inside_unresolved_brackets_stay_unchanged(self):
        doc=self.inner_tabs();result=self.inspect(doc)
        self.assertEqual([f['label'] for f in result['fields']],['Reason'])
        issue=result['import_manifest']['coverage']['selected_engine_issues'][0]
        self.assertEqual(issue['code'],'printed_bracket_alternatives')
        self.assertTrue(result['import_manifest']['coverage']['block_generation'])
        field=result['fields'][0];out=word_v3.fill(data(doc),result['fields'],{field['key']:'Synthetic adjacent answer'})
        export=Document(io.BytesIO(out));self.assertEqual(export.paragraphs[0].text,doc.paragraphs[0].text)
        self.assertEqual(export.paragraphs[1].text,'Reason: Synthetic adjacent answer')
        self.assertEqual(etree.tostring(export.paragraphs[0]._p),etree.tostring(doc.paragraphs[0]._p))

    def test_original_unresolved_range_refuses_forged_span_and_copy_writers(self):
        doc=self.inner_tabs();raw=data(doc);result=self.inspect(doc)
        issue=result['import_manifest']['coverage']['selected_engine_issues'][0]
        package=word_v3.open_package(raw);index=word_v3.SlotIndex(package);slot=index.by_id['word/document.xml#b/p[0]']
        text,_=word_v3.paragraph_text(slot.el);offset=text.index('\t')
        forged={'key':'manual_source','label':'Forged source blank','kind':'text','locator':{
            'contract':'v3','part':slot.part,'slot':slot.path,'fingerprint':word_v3.fingerprint(slot.el),
            'target':{'type':'span','start':offset,'end':offset+1,'shape':'utab'}}}
        from copy import deepcopy
        copy=deepcopy(result['fields'][0]);copy['locator']['target']['copies']=[{
            'part':slot.part,'slot':slot.path,'fingerprint':word_v3.fingerprint(slot.el)}]
        for field in (forged,copy):
            with self.subTest(field=field['key']):
                with self.assertRaises(word_v3.V3Failure) as failure:
                    word_v3.fill(raw,[field],{field['key']:'SYNTHETIC FORGED WRITE'})
                self.assertEqual(failure.exception.code,'unresolved_source_range')

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

    def fixed_header(self,doc):
        p=doc.sections[0].header.paragraphs[0];p.text='Patient name: ______'
        pict=OxmlElement('w:pict');shape=etree.SubElement(pict,'{urn:schemas-microsoft-com:vml}shape')
        shape.set('style','position:absolute;width:72pt;height:12pt')
        box=etree.SubElement(shape,'{urn:schemas-microsoft-com:vml}textbox')
        content=etree.SubElement(box,qn('w:txbxContent'));pp=etree.SubElement(content,qn('w:p'))
        rr=etree.SubElement(pp,qn('w:r'));etree.SubElement(rr,qn('w:t')).text='FIXED ADJACENT LABEL'
        p.add_run()._r.append(pict)

    def test_fixed_header_geometry_is_explicit_before_generation_and_forged_fill_refuses(self):
        doc=Document();self.fixed_header(doc);doc.add_paragraph('Reason: ______');result=self.inspect(doc)
        self.assertTrue(result['import_manifest']['coverage']['block_generation'])
        issues=result['import_manifest']['coverage']['selected_engine_issues']
        self.assertTrue(any(i['code']=='unqualified_fixed_container' and i['part']=='word/header1.xml' for i in issues))
        field=next(f for f in result['fields'] if f['locator']['part']=='word/header1.xml')
        self.assertTrue(field['write_protected'])
        forged=dict(field,write_protected=False)
        with self.assertRaises(word_v3.V3Failure):word_v3.fill(data(doc),[forged],{forged['key']:'SYNTHETIC replacement'})
        ordinary=next(f for f in result['fields'] if f['label']=='Reason')
        self.assertFalse(ordinary.get('write_protected'))
        out=word_v3.fill(data(doc),result['fields'],{ordinary['key']:'Synthetic ordinary review'})
        self.assertEqual(Document(io.BytesIO(out)).sections[0].header.paragraphs[0].text,'Patient name: ______')

    def test_positioned_table_also_holds_neighbor_growth_but_plain_document_stays_answerable(self):
        doc=Document();floating=doc.add_table(rows=1,cols=2);floating.cell(0,0).text='Finding'
        pos=OxmlElement('w:tblpPr');pos.set(qn('w:vertAnchor'),'text');pos.set(qn('w:tblpY'),'300')
        floating._tbl.tblPr.append(pos)
        regular=doc.add_table(rows=1,cols=2);regular.cell(0,0).text='Plan'
        result=self.inspect(doc);by={f['label']:f for f in result['fields']}
        self.assertTrue(by['Finding']['write_protected']);self.assertTrue(by['Plan']['write_protected'])
        self.assertTrue(result['import_manifest']['coverage']['block_generation'])
        forged=dict(by['Finding'],write_protected=False)
        with self.assertRaises(word_v3.V3Failure):word_v3.fill(data(doc),[forged],{forged['key']:'Synthetic replacement'})
        plan=dict(by['Plan'],write_protected=False)
        with self.assertRaises(word_v3.V3Failure):word_v3.fill(data(doc),[plan],{plan['key']:'Synthetic plan'})
        out=word_v3.fill(data(doc),result['fields'],{})
        parsed=Document(io.BytesIO(out));self.assertEqual(parsed.tables[0].cell(0,1).text,'')
        self.assertEqual(parsed.tables[1].cell(0,1).text,'')
        plain=Document();table=plain.add_table(rows=1,cols=2);table.cell(0,0).text='Plan'
        good=self.inspect(plain);field=good['fields'][0]
        self.assertFalse(good['import_manifest']['coverage'].get('selected_engine_issues'))
        result=word_v3.fill(data(plain),good['fields'],{field['key']:'Synthetic plan'})
        self.assertEqual(Document(io.BytesIO(result)).tables[0].cell(0,1).text,'Synthetic plan')

    def test_cell_append_preserves_original_paragraph_without_unqualified_wrap_repair(self):
        doc=Document();cell=doc.add_table(rows=1,cols=1).cell(0,0);cell.text='FIXED SOURCE GUIDANCE'
        old=etree.tostring(cell.paragraphs[0]._p)
        word_v3.write_cell(cell._tc,'SYNTHETIC synthetic',append=True)
        self.assertEqual(etree.tostring(cell.paragraphs[0]._p),old)
        self.assertIsNone(cell.paragraphs[1]._p.find('./'+qn('w:pPr')+'/'+qn('w:wordWrap')))
        self.assertEqual(cell.paragraphs[1].text,'SYNTHETIC synthetic')

    def test_exact_measured_source_quarantine_cannot_be_cleared_by_forged_writer(self):
        doc=Document();doc.add_paragraph('Reason: ______');raw=data(doc)
        baseline=word_v3.inspect(raw);anchor=baseline['fields'][0]['locator']
        declaration={'case':'synthetic negative control','failed_anchors':[anchor],
                     'evidence':['retained synthetic failure control']}
        with patch.dict(word_v3.KNOWN_LAYOUT_FAILURES,{hashlib.sha256(raw).hexdigest():declaration}):
            result=word_v3.inspect(raw)
            self.assertEqual(result['layout_quarantine']['source_sha256'],hashlib.sha256(raw).hexdigest())
            self.assertTrue(result['fields'][0]['write_protected'])
            forged=dict(result['fields'][0],write_protected=False)
            with self.assertRaises(word_v3.V3Failure) as refusal:
                word_v3.fill(raw,[forged],{forged['key']:'Synthetic replacement'})
            self.assertEqual(refusal.exception.code,'unqualified_layout')
            different=Document();different.add_paragraph('Plan: ______')
            self.assertIsNone(word_v3.inspect(data(different))['layout_quarantine'])
