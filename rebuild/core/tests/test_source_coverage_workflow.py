"""Explicit source review cannot be replaced by a generic confirmation or copied writer."""
import copy
import io
import json
import os
import tempfile
from pathlib import Path
from zipfile import ZipFile
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TestCase,override_settings
from docx import Document

from core import import_binding
from core.jobs import enqueue,run_one
from core.models import Encounter,Job,Reservation,TemplateVersion
from core.security import private_path
from documents.test_source_coverage import numbered
from .test_word_v3_workflow import V3Fixture
from .test_workflow import TEST_SETTINGS
from .test_v3_supersession_floor import SONNET_55_DEFAULT


@override_settings(**dict(TEST_SETTINGS,QUILLMD_WORD_ENGINE='v3',QUILLMD_ROLE_SUGGESTIONS=False))
class SourceReviewWorkflow(V3Fixture,TestCase):
    def source(self,shape):
        doc=Document()
        if shape=='list':
            numbered(doc,'Gender',90,'decimal')
            for item in ('Male','Female','Other'):numbered(doc,item,91,'lowerLetter')
        elif shape=='unbalanced':doc.add_paragraph('Site: [left/right')
        elif shape=='internal_tabs':
            from documents.test_source_coverage import SourceCoverage
            doc=SourceCoverage().inner_tabs()
            doc.paragraphs[-1].text='Reason for visit: ______'
            out=io.BytesIO();doc.save(out);return doc,out.getvalue()
        else:doc.add_paragraph('The care received was right for [me/us].')
        doc.add_paragraph('Reason for visit: ______')
        out=io.BytesIO();doc.save(out);return doc,out.getvalue()

    def test_exact_review_preserves_printed_sources_and_ordinary_field_workflow(self):
        for shape in ('list','alternatives','unbalanced','internal_tabs'):
            with self.subTest(shape=shape):
                original,raw=self.source(shape)
                template,version=self.uploaded(data=raw,name='Synthetic exact source review '+shape)
                issues=version.import_manifest['coverage']['selected_engine_issues']
                self.assertTrue(issues)
                with self.assertRaises(ValidationError):import_binding.verify(version)
                response=self.client.post(f'/templates/{template.pk}/',dict(action='v3_confirm',mapping_version=version.pk,
                                                                          checked_every_field='on'))
                self.assertEqual(response.status_code,400)
                self.assertEqual(self.new_encounter(version).status_code,200)
                self.assertFalse(Encounter.objects.filter(template_version=version).exists())
                self.assertEqual(Job.objects.filter(encounter__template_version=version).count(),0)
                response=self.client.post(f'/templates/{template.pk}/',dict(action='v3_coverage',mapping_version=version.pk,
                                            **{'exclude_'+issue['id']:'on' for issue in issues}))
                self.assertEqual(response.status_code,302,response.content.decode())
                reviewed=self.latest(template);self.assertNotEqual(version.pk,reviewed.pk)
                self.assertEqual(version.import_manifest,reviewed.import_manifest)
                self.assertFalse(reviewed.import_manifest['coverage']['automatic_complete'])
                import_binding.verify(reviewed);self.confirm(template,reviewed)
                self.assertEqual(self.new_encounter(reviewed,'Reason for visit: Synthetic review').status_code,302)
                encounter=Encounter.objects.get(template_version=reviewed);job=enqueue(encounter,self.user)
                self.assertTrue(run_one());job.refresh_from_db();self.assertEqual(job.state,'succeeded',job.error)
                encounter.refresh_from_db();key=reviewed.fields[0]['key']
                response=self.client.post(f'/encounters/{encounter.pk}/save/',{'revision':encounter.revision,
                                    'answer_'+key:'Synthetic review','reviewed_'+key:'on'})
                self.assertEqual(response.status_code,302);encounter.refresh_from_db()
                response=self.client.post(f'/encounters/{encounter.pk}/finalize/',{'revision':encounter.revision,'reviewed':'on'})
                self.assertEqual(response.status_code,302);encounter.refresh_from_db();self.assertEqual(encounter.status,'finalized')
                export=Document(private_path(encounter.export_path))
                self.assertEqual([p.text for p in export.paragraphs[:-1]],[p.text for p in original.paragraphs[:-1]])
                self.assertEqual(export.paragraphs[-1].text,'Reason for visit: Synthetic review')

    def test_precise_exclusion_cannot_be_copied_into_by_a_forged_manual_field(self):
        _,raw=self.source('alternatives');template,version=self.uploaded(data=raw)
        issue=version.import_manifest['coverage']['selected_engine_issues'][0]
        version.corrections={'coverage_review':[{'id':issue['id'],'disposition':'leave_unchanged',
                                 'source_sha256':template.sha256,'reviewed_by':str(self.user.pk)}]}
        self.assertTrue(import_binding.coverage_reviewed(version))
        fields=copy.deepcopy(version.fields)
        fields.append(dict(key='manual_alternative',label='Forged free text',kind='text',locator={
            'part':issue['part'],'slot':issue['slot'],'target':dict(type='span',start=issue['start'],end=issue['end'])}))
        version.fields=fields;version.import_manifest=import_binding.for_mapping(version.import_manifest,fields)
        self.assertFalse(import_binding.coverage_reviewed(version))
        with self.assertRaises(ValidationError):import_binding.verify(version)

    def test_unqualified_fixed_header_refuses_generic_review_before_job_or_reservation(self):
        from documents.test_source_coverage import SourceCoverage
        doc=Document();SourceCoverage().fixed_header(doc);doc.add_paragraph('Reason: ______')
        out=io.BytesIO();doc.save(out);template,version=self.uploaded(data=out.getvalue())
        self.assertTrue(version.import_manifest['coverage']['block_generation'])
        with self.assertRaises(ValidationError):import_binding.verify(version)
        response=self.client.post(f'/templates/{template.pk}/',{'action':'v3_confirm',
                                 'mapping_version':version.pk,'checked_every_field':'on'})
        self.assertEqual(response.status_code,400)
        self.assertEqual(self.new_encounter(version).status_code,200)
        self.assertEqual(Job.objects.count(),0);self.assertEqual(Reservation.objects.count(),0)

    def test_measured_document_quarantine_refuses_even_precise_exclusion_before_money(self):
        _,raw=self.source('alternatives');template,version=self.uploaded(data=raw)
        manifest=copy.deepcopy(version.import_manifest)
        quarantined=TemplateVersion.objects.create(template=template,number=2,fields=version.fields,
                    contract=version.contract,created_by=self.user,import_manifest=manifest,
                    corrections={'coverage_review':[{'id':issue['id'],'disposition':'leave_unchanged',
                                  'source_sha256':template.sha256,'reviewed_by':str(self.user.pk)}
                                 for issue in manifest['coverage']['selected_engine_issues']]})
        self.assertEqual(quarantined.import_manifest,version.import_manifest)
        from documents.word_v3 import KNOWN_LAYOUT_FAILURES
        declaration={'failed_anchors':[version.fields[0]['locator']],
                     'evidence':['synthetic measured-failure control']}
        with patch.dict(KNOWN_LAYOUT_FAILURES,{template.sha256:declaration}):
            self.assertFalse(import_binding.coverage_reviewed(quarantined))
            with self.assertRaisesMessage(ValidationError,'retained rendered answer failures'):
                import_binding.verify(quarantined)
            response=self.client.post(f'/templates/{template.pk}/',{'action':'v3_confirm',
                                     'mapping_version':quarantined.pk,'checked_every_field':'on'})
            self.assertEqual(response.status_code,400)
            self.assertEqual(self.new_encounter(quarantined).status_code,200)
            self.assertEqual(Job.objects.count(),0);self.assertEqual(Reservation.objects.count(),0)

    def test_spaced_date_source_has_valid_binding_and_genuine_export(self):
        from documents.service import fill_template
        doc=Document();doc.add_paragraph('Date: [DD / MM / YYYY]')
        out=io.BytesIO();doc.save(out);template,version=self.uploaded(data=out.getvalue())
        self.assertFalse(version.import_manifest['coverage'].get('block_generation'))
        self.confirm(template,version);import_binding.verify(version)
        field=version.fields[0];self.assertEqual(field['kind'],'date')
        target=Path(self.directory.name)/'spaced-date-export.docx'
        fill_template(private_path(template.original_path),version.fields,{field['key']:'03/14/2026'},target)
        self.assertEqual(Document(target).paragraphs[0].text,'Date: 03/14/2026')

    @override_settings(**dict(SONNET_55_DEFAULT, AI_MODE='fixture'))
    def test_adjacent_answers_real_upload_worker_review_finalization_and_export(self):
        from documents import word_v3
        from documents.test_source_coverage import AdjacentCheckboxAnswers
        helper = AdjacentCheckboxAnswers()
        shapes = (
            ('conditional', helper.form('Any symptoms? ☐ No ☐ Yes → if yes, describe: ______'),
             {'Any symptoms?': 'Yes', 'if yes, describe:': 'Synthetic headache', 'Unrelated note': 'Synthetic review'}),
            ('native_other', helper.form(' Other, specify___________', native=True),
             {'Other, specify': 'checked', 'Unrelated note': 'Synthetic review'}),
            ('independent_age', helper.form('Gender\t\t ☐ Male\t\t☐ Female\t\tAge   ................  years'),
             {'Gender': 'Female', 'Age': '42', 'Unrelated note': 'Synthetic review'}),
        )
        for shape, raw, expected in shapes:
            with self.subTest(shape=shape):
                from docx.oxml import OxmlElement
                from docx.oxml.ns import qn
                from docx.opc.constants import RELATIONSHIP_TYPE
                original_doc = Document(io.BytesIO(raw))
                original_doc.add_paragraph('Clinician signature: ______')
                original_doc.add_paragraph('Tick control retained: ☒ Printed')
                fixed = original_doc.add_paragraph('Fixed guidance: ')
                relationship = original_doc.part.relate_to('https://example.invalid/synthetic-guidance',
                    RELATIONSHIP_TYPE.HYPERLINK,is_external=True)
                link=OxmlElement('w:hyperlink');link.set(qn('r:id'),relationship)
                run=OxmlElement('w:r');text=OxmlElement('w:t');text.text='Read the synthetic guidance'
                run.append(text);link.append(run);fixed._p.append(link)
                buffer=io.BytesIO();original_doc.save(buffer);raw=buffer.getvalue()
                evidence = None
                scratch = Path(os.environ.get('QUILLMD_STATE_DIR', '/nonexistent'))
                approved = Path('/opt/meddoc-pro/rebuild/.runtime/v1-sol-continuation-20261002/word/adjacent-writein')
                if scratch.is_relative_to(approved) and scratch.is_dir() and not scratch.is_symlink():
                    evidence = Path(tempfile.mkdtemp(prefix='workflow-'+shape+'-', dir=scratch))
                    (evidence/'original.docx').write_bytes(raw)
                template, version = self.uploaded(data=raw, name='Synthetic adjacent '+shape)
                self.assertFalse(version.import_manifest['coverage'].get('block_generation'))
                import_binding.verify(version); self.confirm(template, version)
                blank = next(f for f in version.fields if f.get('source_questions')
                             and f['source_questions'][0]['relation'] == 'adjacent_checkbox_answer')
                # The same-label Other control and write-in require their full
                # distinct contexts; this fixture does not guess between them.
                values = {f['key']: ('Synthetic location' if f['key'] == blank['key'] and shape == 'native_other'
                                    else expected.get(f['label'],'')) for f in version.fields}
                notes = '\n\n'.join(f"{f['context']} > {f['label']}: {values[f['key']]}" if shape == 'native_other'
                                   else f"{f['label']}: {values[f['key']]}" for f in version.fields if values[f['key']])
                if evidence:
                    (evidence/'mapping.json').write_text(json.dumps({'fields':version.fields,
                        'import_manifest':version.import_manifest,'input_notes':notes,'expected':values},indent=2))
                self.assertEqual(self.new_encounter(version, notes).status_code, 302)
                encounter = Encounter.objects.get(template_version=version)
                page = self.client.get(f'/encounters/{encounter.pk}/')
                self.assertIsNotNone(page.context['generation_max_charge'], page.context['generation_quote_error'])
                response = self.client.post(f'/encounters/{encounter.pk}/generate/',
                    {'revision':encounter.revision,'usage_quote':page.context['usage_quote']})
                self.assertEqual(response.status_code,302)
                self.assertTrue(run_one()); encounter.refresh_from_db()
                job = Job.objects.get(encounter=encounter)
                self.assertEqual(job.state,'succeeded',job.error)
                first = copy.deepcopy(encounter.answers)
                if evidence: (evidence/'first-pass.json').write_text(json.dumps(first,indent=2))
                print('ADJACENT_FIRST_PASS',shape,json.dumps({k:{'status':v.get('status'),'text':v.get('text')}
                                                           for k,v in first.items()},sort_keys=True))
                # Field review may correct a fixture hold; preserve the first
                # response separately and never credit corrections as automatic.
                payload = {'revision':encounter.revision}
                for field in version.fields:
                    payload['answer_'+field['key']] = values[field['key']]
                    payload['reviewed_'+field['key']] = 'on'
                if shape == 'conditional':
                    choice = next(f for f in version.fields if f['kind']=='choice')
                    invalid = {**payload,'answer_'+choice['key']:'No'}
                    self.assertEqual(self.client.post(f'/encounters/{encounter.pk}/save/',invalid).status_code,302)
                    encounter.refresh_from_db()
                    refused = self.client.post(f'/encounters/{encounter.pk}/finalize/',
                        {'revision':encounter.revision,'reviewed':'on'})
                    self.assertEqual(refused.status_code,200); encounter.refresh_from_db()
                    self.assertEqual(encounter.status,'draft'); self.assertFalse(encounter.export_path)
                    if evidence: (evidence/'unselected-finalization.json').write_text(json.dumps(
                        {'status_code':refused.status_code,'encounter_status':encounter.status,'export_path':''}))
                payload['revision'] = encounter.revision
                self.assertEqual(self.client.post(f'/encounters/{encounter.pk}/save/',payload).status_code,302)
                encounter.refresh_from_db()
                self.assertEqual(self.client.post(f'/encounters/{encounter.pk}/finalize/',
                    {'revision':encounter.revision,'reviewed':'on'}).status_code,302)
                encounter.refresh_from_db(); self.assertEqual(encounter.status,'finalized')
                response = self.client.get(f'/encounters/{encounter.pk}/export/')
                self.assertEqual(response.status_code,200)
                exported = b''.join(response.streaming_content)
                if evidence:
                    (evidence/'final.docx').write_bytes(exported)
                    (evidence/'review-actions.json').write_text(json.dumps({'answers':values,
                        'automatic_correct':sum(first.get(k,{}).get('status')=='supported' and first[k].get('text')==v
                                                for k,v in values.items() if v),'expected_count':sum(bool(v) for v in values.values()),
                        'corrections_count':sum(first.get(k,{}).get('status')!='supported' or first[k].get('text')!=v
                                               for k,v in values.items() if v),'fixture_only':True},indent=2))
                final = Document(io.BytesIO(exported))
                self.assertEqual(final.paragraphs[-4].text,'Unrelated note: Synthetic review')
                self.assertEqual(final.paragraphs[-3].text,'Clinician signature: ______')
                self.assertEqual(final.paragraphs[-2].text,'Tick control retained: ☒ Printed')
                self.assertEqual(final.paragraphs[-1]._p.xml,original_doc.paragraphs[-1]._p.xml)
                with ZipFile(io.BytesIO(raw)) as source, ZipFile(io.BytesIO(exported)) as written:
                    for name in source.namelist():
                        if name != 'word/document.xml': self.assertEqual(source.read(name),written.read(name),name)
                if shape == 'conditional':
                    self.assertEqual(final.paragraphs[0].text,
                        'Any symptoms? ☐ No ☒ Yes → if yes, describe: Synthetic headache')
                elif shape == 'native_other':
                    index = word_v3.SlotIndex(word_v3.open_package(exported))
                    choice = next(f for f in version.fields if f['kind']=='checkbox')
                    self.assertEqual(word_v3.constrained_option_states(index,choice),[True])
                    self.assertIn('Other, specifySynthetic location',final.paragraphs[1].text)
                else:
                    self.assertEqual(final.paragraphs[0].text,
                        'Gender\t\t ☐ Male\t\t☒ Female\t\tAge   42  years')
                self.assertEqual(private_path(template.original_path).read_bytes(),raw)
