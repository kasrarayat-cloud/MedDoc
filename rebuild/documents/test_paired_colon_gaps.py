"""Physical mixed-line destinations and ordinary clinician recording controls."""
import io
from copy import deepcopy
from zipfile import ZipFile
import unittest
from docx import Document
from . import word_v3 as w


def saved(doc):
    out=io.BytesIO();doc.save(out);return out.getvalue()


class OperatorRecording(unittest.TestCase):
    def form(self, caption):
        doc=Document();table=doc.add_table(rows=2,cols=2)
        table.cell(0,0).text=caption;table.cell(1,0).text='Clinical reason'
        table.cell(1,1).text='Original neighbor entry'
        doc.sections[0].header.paragraphs[0].text='Original header'
        doc.sections[0].footer.paragraphs[0].text='Original footer'
        return saved(doc)

    def test_complete_current_operator_recording_ordinary_argument_preserves_original(self):
        for argument in ('initial symptoms','initial physical observations','signed document receipt',
                         'signed referral received and recorded'):
            with self.subTest(argument=argument):
                caption='This section is for the clinician to record '+argument
                raw=self.form(caption);info=w.inspect(raw);field=next(f for f in info['fields']if f['locator']['slot']=='b/tbl[0]/tr[0]/tc[1]')
                self.assertFalse(field.get('write_protected'))
                self.assertEqual(w.destination_roles(raw,[field])['violations'],{})
                out=w.fill(raw,info['fields'],{field['key']:'Synthetic recorded observation'})
                doc=Document(io.BytesIO(out));self.assertEqual(doc.tables[0].cell(0,0).text,caption)
                self.assertEqual(doc.tables[0].cell(0,1).text,'Synthetic recorded observation')
                self.assertEqual(doc.tables[0].cell(1,1).text,'Original neighbor entry')
                with ZipFile(io.BytesIO(raw))as before,ZipFile(io.BytesIO(out))as after:
                    self.assertEqual(before.comment,after.comment)
                    for name in before.namelist():
                        if name!='word/document.xml':self.assertEqual(before.read(name),after.read(name),name)

    def test_named_author_and_complete_operator_actions_never_gain_permission(self):
        for caption in ('This section is for Alex Reed to record initial symptoms',
                        'This section is for Dr. Synthetic to record symptoms',
                        'This section is for the clinician to write his comments',
                        'This section is for the clinician to record initial symptoms and I approve this document',
                        'This section is for the clinician to record initial patient signature',
                        'This section is reserved for the line manager to supply comments',
                        'Date and time Alex Reed is to write his comments:'):
            with self.subTest(caption=caption):
                raw=self.form(caption);info=w.inspect(raw);field=next(f for f in info['fields']if f['locator']['slot']=='b/tbl[0]/tr[0]/tc[1]')
                self.assertTrue(field.get('write_protected'))
                with self.assertRaises(w.V3Failure):w.fill(raw,info['fields'],{field['key']:'Dr Synthetic Finalizer'})
                forged=deepcopy(field);forged.update(label='Clinical value',kind='text')
                for key in ('write_protected','destination_roles','answer_policy'):forged.pop(key,None)
                with self.assertRaises(w.V3Failure):w.fill(raw,[forged],{forged['key']:'Dr Synthetic Finalizer'})
                self.assertEqual(w.fill(raw,info['fields'],{}),raw)
