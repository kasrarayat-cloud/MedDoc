"""Current versions for new documents; historical records and sealed definitions stay intact."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone
from docx import Document

from core.forms import EncounterForm
from core.models import (AIStageReceipt, Department, Encounter, Job, Membership,
                         Organization, Patient, Template, TemplateVersion, User)
from core import semantic_preparation as definitions
from documents import inspect_template


@override_settings(
    AI_MODE='fixture', ADMIN_SITE=False, WORD_PREPARATION_ENABLED=True,
    TESTING_AUTHORITY_MODE='', TESTING_AUTHORITY_ID='', TESTING_AUTHORITY_SHA256='',
    STORAGES={'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
              'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}},
)
class CurrentTemplateSelectionTests(TestCase):
    def setUp(self):
        directory=tempfile.TemporaryDirectory(); self.addCleanup(directory.cleanup)
        self.root=Path(directory.name)
        storage=override_settings(MEDIA_ROOT=self.root); storage.enable(); self.addCleanup(storage.disable)
        self.user=User.objects.create_user(username='current-version-doctor',
            email='current-version@synthetic.invalid',verified_at=timezone.now())
        organization=Organization.objects.create(name='Synthetic current-version practice')
        self.department=Department.objects.create(organization=organization,name='Synthetic current X-ray')
        Membership.objects.create(user=self.user,department=self.department,role='clinician')
        self.patient=Patient.objects.create(department=self.department,display_name='Synthetic wrist patient',
            reference='synthetic-current-wrist',created_by=self.user)
        document=Document(); table=document.add_table(rows=0,cols=2)
        for label in ('Patient name','Assessment'):
            cells=table.add_row().cells; cells[0].text=label; cells[1].text=''
        document.save(self.root/'blank.docx')
        self.original=(self.root/'blank.docx').read_bytes()
        self.template=Template.objects.create(department=self.department,name='Synthetic wrist form',
            format='docx',original_name='blank.docx',original_path='blank.docx',
            sha256=hashlib.sha256(self.original).hexdigest(),created_by=self.user)
        self.source=TemplateVersion.objects.create(template=self.template,number=1,
            fields=inspect_template(self.root/'blank.docx')['fields'],created_by=self.user)
        self.client.force_login(self.user)

    def legacy(self,template=None,fields=None):
        template=template or self.template
        return TemplateVersion.objects.create(template=template,
            number=template.versions.latest('number').number+1,
            fields=deepcopy(fields or self.source.fields),created_by=self.user)

    def semantic(self,source=None):
        source=source or self.source
        preparation=definitions.create_preparation(source,self.user)
        self.assertTrue(definitions.run_one()); preparation.refresh_from_db()
        self.assertEqual(preparation.state,'review',preparation.error_code)
        return definitions.approve(preparation.pk,self.user,preparation.revision,
            preparation.inventory['inventory_sha256'],[field['key'] for field in source.fields],True)

    def post(self,version,notes='Synthetic Alex Morgan reports left wrist pain.'):
        return {'patient':str(self.patient.pk),'template_version':str(version.pk),'notes':notes,
                'service_date':timezone.localdate().isoformat(),'synthetic_only':'on'}

    def choices(self):
        return list(EncounterForm(user=self.user).fields['template_version'].queryset)

    def test_library_offers_one_current_version_per_template_and_newest_legacy_without_definitions(self):
        second=self.legacy(); third=self.legacy()
        another=Template.objects.create(department=self.department,name='Another synthetic form',
            format='docx',original_name='blank.docx',original_path='blank.docx',sha256=self.template.sha256,
            created_by=self.user)
        other_version=TemplateVersion.objects.create(template=another,number=1,
            fields=self.source.fields,created_by=self.user)
        self.assertEqual({version.pk for version in self.choices()},{third.pk,other_version.pk})
        page=self.client.get('/encounters/new/')
        self.assertContains(page,f'value="{third.pk}"')
        self.assertNotContains(page,f'value="{self.source.pk}"')
        self.assertNotContains(page,f'value="{second.pk}"')

    def test_latest_semantic_is_used_even_if_a_later_legacy_version_exists(self):
        approved=self.semantic(); later=self.legacy()
        self.assertEqual([version.pk for version in self.choices()],[approved.pk])
        response=self.client.get('/encounters/new/',{'template':str(self.template.pk)})
        self.assertEqual(response.context['form'].initial['template_version'],approved.pk)
        self.assertNotContains(response,f'value="{later.pk}"')
        self.assertNotContains(response,f'value="{self.source.pk}"')

    def test_newer_separately_approved_semantic_version_supersedes_prior_approval(self):
        first=self.semantic(); latest=self.semantic(first)
        self.assertEqual([version.pk for version in self.choices()],[latest.pk])
        self.assertNotEqual(first.semantic_preparation_id,latest.semantic_preparation_id)
        self.assertEqual(definitions.validated_semantic_definitions(first),first.semantic_definitions)

    def test_legacy_post_after_semantic_approval_refuses_without_losing_notes_or_enqueuing(self):
        approved=self.semantic(); notes='Synthetic retained wrist notes: pain after a fall.'
        before=AIStageReceipt.objects.count()
        with patch('core.views.enqueue') as enqueue:
            response=self.client.post('/encounters/new/',self.post(self.source,notes))
        self.assertContains(response,'Choose its current version below',status_code=409)
        self.assertContains(response,notes,status_code=409)
        self.assertContains(response,f'value="{approved.pk}"',status_code=409)
        self.assertFalse(Encounter.objects.exists()); self.assertFalse(Job.objects.exists())
        self.assertEqual(AIStageReceipt.objects.count(),before); enqueue.assert_not_called()

    def test_later_legacy_post_cannot_downgrade_an_approved_semantic_form(self):
        self.semantic(); later=self.legacy()
        response=self.client.post('/encounters/new/',self.post(later))
        self.assertEqual(response.status_code,409)
        self.assertFalse(Encounter.objects.exists()); self.assertFalse(Job.objects.exists())

    def test_current_semantic_post_creates_only_a_draft_with_that_exact_mapping(self):
        approved=self.semantic(); before=AIStageReceipt.objects.count()
        response=self.client.post('/encounters/new/',self.post(approved))
        self.assertEqual(response.status_code,302)
        encounter=Encounter.objects.get()
        self.assertEqual(encounter.template_version_id,approved.pk)
        self.assertEqual(encounter.notes,self.post(approved)['notes'])
        self.assertEqual(encounter.status,'draft'); self.assertEqual(encounter.answers,{})
        self.assertEqual(AIStageReceipt.objects.count(),before); self.assertFalse(Job.objects.exists())

    def test_mapping_change_between_form_validation_and_creation_is_refused(self):
        notes='Synthetic wrist notes retained through the concurrent mapping change.'
        validate=EncounterForm.is_valid
        def publish_after_validation(form):
            valid=validate(form)
            if valid:self.legacy()
            return valid
        with patch.object(EncounterForm,'is_valid',publish_after_validation):
            response=self.client.post('/encounters/new/',self.post(self.source,notes))
        self.assertContains(response,'Choose its current version below',status_code=409)
        self.assertContains(response,notes,status_code=409)
        self.assertFalse(Encounter.objects.exists()); self.assertFalse(Job.objects.exists())

    def test_semantic_approval_between_validation_and_creation_is_refused_without_hidden_upgrade(self):
        validate=EncounterForm.is_valid
        def approve_after_validation(form):
            valid=validate(form)
            if valid:self.semantic()
            return valid
        with patch.object(EncounterForm,'is_valid',approve_after_validation):
            response=self.client.post('/encounters/new/',self.post(self.source))
        self.assertEqual(response.status_code,409)
        self.assertFalse(Encounter.objects.exists()); self.assertFalse(Job.objects.exists())

    def test_foreign_template_is_neither_listed_preselected_nor_accepted(self):
        other=Department.objects.create(organization=Organization.objects.create(name='Synthetic foreign'),name='Other')
        foreign=Template.objects.create(department=other,name='Foreign synthetic form',format='docx',
            original_name='blank.docx',original_path='blank.docx',sha256=self.template.sha256,created_by=self.user)
        version=TemplateVersion.objects.create(template=foreign,number=1,fields=self.source.fields,created_by=self.user)
        response=self.client.get('/encounters/new/',{'template':str(foreign.pk)})
        self.assertNotIn('template_version',response.context['form'].initial)
        self.assertNotContains(response,'Foreign synthetic form')
        response=self.client.post('/encounters/new/',self.post(version))
        self.assertEqual(response.status_code,409); self.assertFalse(Encounter.objects.exists())

    def test_existing_legacy_document_and_download_stay_bound_to_the_original_version(self):
        export=b'SYNTHETIC preserved historical download'
        (self.root/'historical.docx').write_bytes(export)
        encounter=Encounter.objects.create(department=self.department,patient=self.patient,
            template_version=self.source,created_by=self.user,service_date=timezone.localdate(),
            notes='Synthetic historical notes.',status='finalized',export_path='historical.docx',
            export_sha256=hashlib.sha256(export).hexdigest())
        before=Encounter.objects.filter(pk=encounter.pk).values().get()
        approved=self.semantic()
        response=self.client.post('/encounters/new/',self.post(approved))
        self.assertEqual(response.status_code,302)
        self.assertEqual(Encounter.objects.filter(pk=encounter.pk).values().get(),before)
        download=self.client.get(f'/encounters/{encounter.pk}/export/')
        self.assertEqual(download.status_code,200); self.assertEqual(b''.join(download.streaming_content),export)
        self.assertEqual((self.root/'blank.docx').read_bytes(),self.original)

    def test_unchanged_semantic_mapping_save_is_a_noop_and_preserves_approval(self):
        approved=self.semantic(); before=list(self.template.versions.order_by('number').values())
        prep_before=approved.semantic_preparation.__class__.objects.filter(pk=approved.semantic_preparation_id).values().get()
        response=self.client.post(f'/templates/{self.template.pk}/',{'mapping_version':str(approved.pk),
            'labels':json.dumps({f['key']:f['label'] for f in approved.fields})})
        self.assertEqual(response.status_code,302)
        self.assertEqual(list(self.template.versions.order_by('number').values()),before)
        approved.refresh_from_db()
        self.assertEqual(approved.semantic_preparation.__class__.objects.filter(pk=approved.semantic_preparation_id).values().get(),prep_before)
        self.assertEqual(definitions.validated_semantic_definitions(approved),approved.semantic_definitions)

    def test_semantic_label_change_is_held_for_definition_review_and_retained(self):
        approved=self.semantic(); labels={f['key']:f['label'] for f in approved.fields}
        labels[approved.fields[0]['key']]='Unsaved precise patient name'
        before=list(self.template.versions.order_by('number').values())
        response=self.client.post(f'/templates/{self.template.pk}/',{'mapping_version':str(approved.pk),'labels':json.dumps(labels)})
        self.assertContains(response,'Use the reusable answer definitions review',status_code=200)
        self.assertContains(response,'Unsaved precise patient name')
        self.assertEqual(list(self.template.versions.order_by('number').values()),before)

    def test_mapping_edit_after_semantic_approval_cannot_create_another_legacy_contract(self):
        approved=self.semantic(); later=self.legacy(); before=self.template.versions.count()
        labels={f['key']:f['label'] for f in later.fields}; labels[later.fields[0]['key']]='Later unapproved meaning'
        response=self.client.post(f'/templates/{self.template.pk}/',{'mapping_version':str(later.pk),'labels':json.dumps(labels)})
        self.assertContains(response,'separately approved answer definitions')
        self.assertEqual(self.template.versions.count(),before)
        self.assertEqual([version.pk for version in self.choices()],[approved.pk])

    def test_stale_mapping_save_keeps_its_conflict_response_and_existing_versions(self):
        approved=self.semantic(); before=self.template.versions.count()
        response=self.client.post(f'/templates/{self.template.pk}/',{'mapping_version':str(self.source.pk),
            'labels':json.dumps({f['key']:f['label'] for f in approved.fields})})
        self.assertContains(response,'Your unsaved labels are retained',status_code=409)
        self.assertEqual(self.template.versions.count(),before)

    def test_legacy_label_edit_remains_supported_without_semantic_definitions(self):
        labels={f['key']:f['label'] for f in self.source.fields}; labels[self.source.fields[0]['key']]='Documented patient name'
        response=self.client.post(f'/templates/{self.template.pk}/',{'mapping_version':str(self.source.pk),'labels':json.dumps(labels)})
        self.assertEqual(response.status_code,302)
        latest=self.template.versions.latest('number')
        self.assertEqual(latest.number,2); self.assertEqual(latest.fields[0]['label'],'Documented patient name')
        self.assertEqual(latest.semantic_definitions,{}); self.assertIsNone(latest.semantic_preparation_id)
