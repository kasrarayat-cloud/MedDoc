"""Separate preparation versions, source seals and scope; synthetic fixtures only."""
from copy import deepcopy
import hashlib
from pathlib import Path
import tempfile
from types import SimpleNamespace
from unittest.mock import patch
from docx import Document
from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import QueryDict
from django.template.loader import render_to_string
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from documents import inspect_template
from documents.semantic_preparation_roles import (build_inventory, default_definitions, digest,
    fixture_role, validate_definitions)
from core import semantic_preparation as workflow
from core.models import AIStageReceipt, Department, Membership, Organization, Template, TemplateVersion, User
from core.semantic_preparation_views import posted_definitions


class DefinitionPreparationPureTests(SimpleTestCase):
    def test_advanced_word_adapter_cannot_enter_unqualified_semantic_preparation(self):
        prep=self.prep()
        prep.source_version.document_backend={'backend':'wm-iov-foss-v2'}
        with patch('core.template_source.source_for_version') as source_reader:
            with self.assertRaisesMessage(ValidationError,'qualified Word adapter requires the existing labelled-evidence review'):
                workflow._validate_source(prep)
        source_reader.assert_not_called()

    def fields(self, count=8):
        labels = ['Patient name', 'Reason for visit', 'History', 'Findings', 'Pain score0 to 10',
                  'Assessment', 'Plan', 'Follow-up']
        return [{'key': 'field_'+str(index), 'label': labels[index % 8], 'kind': 'text',
                 'locator': {'cell': index}} for index in range(count)]

    def prep(self, count=8):
        fields = self.fields(count)
        template = SimpleNamespace(pk='template', sha256='a'*64, format='docx')
        source = SimpleNamespace(pk='source', number=1, template=template, template_id='template',
            fields=fields, review_requirements=[], document_backend={}, prepared_path='',
            prepared_sha256='', preparation_id=None)
        inventory = build_inventory(fields, source_version_id='source', source_sha256='a'*64,
            original={'stories': [{'texts': ['Complete synthetic blank original']}], 'questions': []})
        return SimpleNamespace(pk='prep', source_version=source, inventory=inventory,
            proposal=fixture_role(fields, inventory, 'proposer'), checker=fixture_role(fields, inventory, 'checker'),
            config={'mode': 'fixture'}, corrections={}, correction_history=[], revision=0,
            approved_definitions=default_definitions(fields), approved_by_id='doctor', approved_at=timezone.now())

    def test_definition_seal_binds_entire_source_and_both_original_roles(self):
        original = self.prep(); seal = workflow.approval_binding(original)
        mutations = [lambda p: p.source_version.fields[0].update(label='Changed meaning'),
            lambda p: p.source_version.fields[0]['locator'].update(cell=9),
            lambda p: p.source_version.document_backend.update(backend='other'),
            lambda p: p.source_version.review_requirements.append({'changed': True}),
            lambda p: p.proposal['fields'][0]['definition'].update(meaning='Changed proposal'),
            lambda p: p.checker['fields'][0].update(state='unresolved'),
            lambda p: p.corrections.update(field_0=default_definitions(p.source_version.fields)['field_0']),
            lambda p: p.approved_definitions['field_0'].update(meaning='Different approval'),
            lambda p: p.correction_history.append({'reason': 'different history'}),
            lambda p: setattr(p, 'revision', 1), lambda p: setattr(p, 'approved_by_id', 'other doctor'),
            lambda p: p.config.update(model='changed')]
        for mutate in mutations:
            changed = deepcopy(original); mutate(changed)
            with self.subTest(mutation=mutate): self.assertNotEqual(workflow.approval_binding(changed), seal)

    def test_posted_destination_is_code_controlled_and_all_definition_fields_round_trip(self):
        prep = self.prep(); values = default_definitions(prep.source_version.fields)
        values['field_0']['meaning'] = 'Only the patient name, without the presenting complaint.'
        post = self.post(values)
        post['field_field_0_locator_sha256'] = 'b'*64
        post['field_field_0_field_key'] = 'field_7'
        self.assertEqual(posted_definitions(prep, post), values)

    @staticmethod
    def post(values):
        post = QueryDict(mutable=True)
        for key, definition in values.items():
            prefix = 'field_'+key+'_'
            for name in ('meaning', 'value_type', 'unit'):
                post[prefix+name] = definition[name] or ''
            post[prefix+'choices'] = '\n'.join(definition['choices'])
            for name, value in {**definition['scope'], **definition['constraints']}.items():
                post[prefix+name] = '' if value is None else value
            post.appendlist('reviewed_field', key)
        return post

    def test_supported_100_field_form_round_trips_below_bounded_request_field_limit(self):
        prep = self.prep(100); values = default_definitions(prep.source_version.fields)
        post = self.post(values)
        post['revision'] = '0'; post['correction_reason'] = 'Compared all original questions and constraints.'
        encoded = post.urlencode()
        self.assertGreater(len(encoded.split('&')), 1000)
        self.assertLess(len(encoded.split('&')), settings.DATA_UPLOAD_MAX_NUMBER_FIELDS)
        reparsed = QueryDict(encoded)
        self.assertEqual(posted_definitions(prep, reparsed), values)
        self.assertEqual(len(reparsed.getlist('reviewed_field')), 100)
        with self.assertRaises(ValueError): default_definitions(self.fields(101))

    def test_every_field_must_be_explicitly_reviewed_once(self):
        prep = self.prep(); keys = [field['key'] for field in prep.source_version.fields]
        workflow._reviewed(prep, keys)
        for invalid in [keys[:-1], keys+keys[:1], keys[:-1]+['unknown']]:
            with self.assertRaises(ValidationError): workflow._reviewed(prep, invalid)

    def test_approval_cannot_validate_with_same_version_as_its_source(self):
        prep = self.prep(); prep.state = 'approved'; prep.approval_sha256 = workflow.approval_binding(prep)
        version = deepcopy(prep.source_version)
        version.semantic_definitions = prep.approved_definitions
        version.semantic_preparation_id = prep.pk; version.semantic_preparation = prep
        with patch.object(workflow, '_validate_source') as read, self.assertRaises(ValidationError):
            workflow.validated_semantic_definitions(version)
        read.assert_not_called()


@override_settings(WORD_PREPARATION_ENABLED=True, AI_MODE='fixture', TESTING_AUTHORITY_MODE='',
                   TESTING_AUTHORITY_ID='', TESTING_AUTHORITY_SHA256='',
                   STORAGES={'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
                             'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}})
class DefinitionPreparationDatabaseTests(TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(); self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        settings_override = override_settings(MEDIA_ROOT=self.root)
        settings_override.enable(); self.addCleanup(settings_override.disable)
        self.user = User.objects.create_user(username='definition-doctor', email='definition-doctor@synthetic.invalid',
            verified_at=timezone.now())
        self.org = Organization.objects.create(name='Synthetic definition preparation')
        self.department = Department.objects.create(name='Synthetic ankle clinic', organization=self.org)
        Membership.objects.create(user=self.user, department=self.department, role='clinician')
        document = Document(); table = document.add_table(rows=0, cols=2)
        for label in DefinitionPreparationPureTests().fields():
            cells = table.add_row().cells; cells[0].text = label['label']; cells[1].text = ''
        document.save(self.root/'blank.docx')
        info = inspect_template(self.root/'blank.docx')
        self.template = Template.objects.create(department=self.department, name='Synthetic ankle form', format='docx',
            original_name='blank.docx', original_path='blank.docx', sha256=hashlib.sha256((self.root/'blank.docx').read_bytes()).hexdigest(),
            created_by=self.user)
        self.source = TemplateVersion.objects.create(template=self.template, number=1, fields=info['fields'], created_by=self.user)

    def test_advanced_word_semantic_start_is_refused_before_receipts_or_provider_calls(self):
        source=TemplateVersion.objects.create(template=self.template,number=2,fields=self.source.fields,
            document_backend={'backend':'wm-iov-foss-v2'},created_by=self.user)
        self.client.force_login(self.user)
        with patch.object(workflow.ai_stages,'execute_stage') as send:
            response=self.client.post(reverse('template_definitions_start',args=[self.template.pk]),{'source_version':str(source.pk)})
        self.assertContains(response,'qualified Word adapter requires the existing labelled-evidence review',status_code=409)
        self.assertFalse(source.definition_preparations.exists())
        self.assertFalse(AIStageReceipt.objects.exists())
        send.assert_not_called()
        response=self.client.get(reverse('template_detail',args=[self.template.pk]))
        self.assertContains(response,'Continue using that approved mapping')
        self.assertNotContains(response,'Prepare reusable answer definitions</button>')

    def prepared(self):
        prep = workflow.create_preparation(self.source, self.user)
        self.assertTrue(workflow.run_one()); prep.refresh_from_db()
        self.assertEqual(prep.state, 'review', prep.error_code)
        return prep

    def approve(self, prep):
        return workflow.approve(prep.pk, self.user, prep.revision, prep.inventory['inventory_sha256'],
            [field['key'] for field in self.source.fields], True)

    def test_supported_workflow_creates_separate_semantic_version_and_preserves_original(self):
        old_source = deepcopy(self.source.fields); original = (self.root/'blank.docx').read_bytes()
        prep = self.prepared()
        receipts = list(prep.ai_stage_receipts.order_by('created_at'))
        self.assertEqual([row.stage for row in receipts], ['definition_proposer', 'definition_checker'])
        self.assertTrue(all(row.simulated and row.actual_cost == 0 and row.state == 'succeeded' for row in receipts))
        version = self.approve(prep); prep.refresh_from_db(); self.source.refresh_from_db()
        self.assertEqual(version.number, 2); self.assertEqual(version.semantic_preparation_id, prep.pk)
        self.assertEqual(version.fields, old_source); self.assertEqual(self.source.fields, old_source)
        self.assertEqual(self.source.semantic_definitions, {}); self.assertIsNone(self.source.semantic_preparation_id)
        self.assertEqual((self.root/'blank.docx').read_bytes(), original)
        self.assertEqual(workflow.validated_semantic_definitions(version), prep.approved_definitions)
        from core.template_source import source_for_version
        self.assertEqual(source_for_version(version), self.root/'blank.docx')
        self.assertFalse(workflow.run_one()); self.assertEqual(AIStageReceipt.objects.count(), 2)

    def test_repeated_start_reuses_request_and_cannot_create_provider_replay(self):
        prep = self.prepared()
        self.assertEqual(workflow.create_preparation(self.source, self.user).pk, prep.pk)
        self.assertEqual(workflow.create_preparation(self.source, self.user).pk, prep.pk)
        self.assertFalse(workflow.run_one()); self.assertEqual(prep.ai_stage_receipts.count(), 2)

    def test_uncertain_definition_requires_explicit_review_and_separate_correction_history(self):
        prep = self.prepared()
        # A separate valid retained checker result disagrees; public approval cannot skip it.
        with patch.object(workflow, 'roles_agree', return_value=False):
            with self.assertRaises(ValidationError): self.approve(prep)
        before_proposal = deepcopy(prep.proposal); before_checker = deepcopy(prep.checker)
        values = workflow.corrected_definitions(prep)
        first = self.source.fields[0]['key']; values[first]['meaning'] = 'Only the documented patient name.'
        corrected = workflow.correct(prep.pk, self.user, 0, values, list(values), 'Compared each original field and clarified patient name.')
        self.assertEqual(corrected.revision, 1); self.assertEqual(corrected.proposal, before_proposal)
        self.assertEqual(corrected.checker, before_checker); self.assertEqual(len(corrected.correction_history), 1)
        version = self.approve(corrected)
        self.assertEqual(version.semantic_definitions[first]['meaning'], 'Only the documented patient name.')
        self.assertEqual(prep.ai_stage_receipts.count(), 2)

    def test_tenant_roles_stale_revision_and_stale_mapping_cannot_approve(self):
        prep = self.prepared(); values = workflow.corrected_definitions(prep)
        other = User.objects.create_user(username='definition-other', verified_at=timezone.now())
        with self.assertRaises(PermissionDenied):
            workflow.correct(prep.pk, other, 0, values, list(values), 'Unauthorized correction attempt.')
        with self.assertRaises(ValidationError):
            workflow.correct(prep.pk, self.user, 9, values, list(values), 'Stale correction attempt.')
        TemplateVersion.objects.create(template=self.template, number=2, fields=self.source.fields, created_by=self.user)
        with self.assertRaises(ValidationError): self.approve(prep)
        self.assertEqual(self.template.versions.count(), 2)

    def test_raw_response_tampering_blocks_approval_without_repeating_stages(self):
        prep = self.prepared(); receipt = prep.ai_stage_receipts.first()
        (self.root/receipt.result_path).write_text('{"tampered":true}')
        with self.assertRaises(ValidationError): self.approve(prep)
        self.assertEqual(self.template.versions.count(), 1); self.assertFalse(workflow.run_one())

    def test_http_correction_preserves_entered_values_on_validation_error_and_tenant_status_is_scoped(self):
        prep = self.prepared(); values = workflow.corrected_definitions(prep)
        first = self.source.fields[0]['key']; values[first]['meaning'] = 'My unsaved precise patient name definition.'
        post = DefinitionPreparationPureTests.post(values)
        post['revision'] = '0'; post['correction_reason'] = 'short'
        self.client.force_login(self.user)
        response = self.client.post(reverse('template_definitions_correct', args=[prep.pk]), post)
        self.assertEqual(response.status_code, 409)
        self.assertContains(response, values[first]['meaning'], status_code=409)
        self.assertContains(response, 'Save reviewed definitions', status_code=409)
        self.assertEqual(prep.ai_stage_receipts.count(), 2)
        stranger = User.objects.create_user(username='definition-stranger', verified_at=timezone.now())
        self.client.force_login(stranger)
        self.assertEqual(self.client.get(reverse('template_definitions_status', args=[prep.pk])).status_code, 404)

    def test_new_definition_review_after_approval_gets_its_own_source_without_changing_prior_approval(self):
        first_prep = self.prepared(); version = self.approve(first_prep)
        first_prep.refresh_from_db(); seal = first_prep.approval_sha256
        next_prep = workflow.create_preparation(version, self.user)
        self.assertNotEqual(next_prep.pk, first_prep.pk); self.assertTrue(workflow.run_one())
        next_prep.refresh_from_db(); self.assertEqual(next_prep.state, 'review', next_prep.error_code)
        next_version = self.approve(next_prep)
        first_prep.refresh_from_db(); self.assertEqual(first_prep.approval_sha256, seal)
        self.assertEqual(next_version.number, 3)
        self.assertEqual(workflow.validated_semantic_definitions(next_version), next_prep.approved_definitions or next_version.semantic_definitions)

    def test_explicit_blocked_retry_retains_attempt_and_replayed_retry_reuses_new_request(self):
        prep=workflow.create_preparation(self.source,self.user)
        with patch.object(workflow,'_inventory',side_effect=ValidationError('Controlled source refusal')):
            self.assertTrue(workflow.run_one())
        prep.refresh_from_db();self.assertEqual(prep.state,'blocked')
        before={key:deepcopy(value) for key,value in prep.__dict__.items() if key!='_state'}
        self.assertEqual(workflow.create_preparation(self.source,self.user).pk,prep.pk)
        new=workflow.create_preparation(self.source,self.user,retry_of=prep.pk)
        self.assertNotEqual(new.pk,prep.pk);self.assertEqual(new.config['definition_retry_of'],str(prep.pk))
        self.assertEqual(workflow.create_preparation(self.source,self.user,retry_of=prep.pk).pk,new.pk)
        prep.refresh_from_db()
        self.assertEqual({key:value for key,value in prep.__dict__.items() if key!='_state'},before)
        self.assertTrue(workflow.run_one());new.refresh_from_db();self.assertEqual(new.state,'review')
        self.assertEqual(AIStageReceipt.objects.count(),2)

    def test_uncertain_blocked_preparation_cannot_buy_another_provider_request(self):
        prep=workflow.create_preparation(self.source,self.user)
        from core.ai_stages import StageUnknown
        with patch.object(workflow,'_call_role',side_effect=StageUnknown('Controlled uncertain provider response')):
            self.assertTrue(workflow.run_one())
        prep.refresh_from_db();self.assertEqual(prep.state,'blocked');self.assertEqual(prep.error_code,'provider_unknown')
        with self.assertRaises(ValidationError):workflow.create_preparation(self.source,self.user,retry_of=prep.pk)
        self.assertEqual(workflow.create_preparation(self.source,self.user).pk,prep.pk)
        self.assertEqual(prep.__class__.objects.count(),1)
