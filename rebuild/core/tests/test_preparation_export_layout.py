"""Provider-free new-policy approval controls; legacy records keep their policy.

These source/approval fixtures do not qualify SDK export geometry. That is
independently exercised against the actual unchanged WM original and SDK.
"""
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock,patch

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from core import preparation as prep
from core.template_source import approval_binding,source_for_version,export_layout_for_version
from core.tests import test_preparation as fixtures


class PreparedWMExportLayoutTests(SimpleTestCase):
    def setUp(self):
        fixtures.PreparationPureTests.setUp(self)
        self.ordinary_original=(self.root/'original.docx').read_bytes()
    config=fixtures.PreparationPureTests.config
    packet=fixtures.PreparationPureTests.packet
    wm_packet=fixtures.WMContinuationTests.wm_packet

    def prepared(self):
        packet,info,_=self.wm_packet();packet.template.format='docx'
        packet.candidate_info=prep.candidate_inspection(packet,info,{'reviewed_multi_column_rows':[]},{},
            preserve_original_export_layout=True)
        return packet,info

    def sealed_version(self,packet):
        packet.state='approved';packet.approved_by_id='doctor1';packet.approved_at='now'
        packet.approval_sha256=approval_binding(packet)
        return SimpleNamespace(template=packet.template,template_id=packet.template_id,preparation=packet,
            preparation_id=packet.pk,prepared_path=packet.candidate_path,prepared_sha256=packet.candidate_sha256,
            fields=deepcopy(packet.candidate_info['fields']),document_backend=deepcopy(packet.candidate_info['document_backend']),
            review_requirements=deepcopy(packet.candidate_info['review_requirements']))

    def test_only_explicit_new_qualified_wm_candidate_gets_source_bound_policy(self):
        packet,info=self.prepared()
        self.assertEqual(packet.candidate_info['export_layout'],
            {'protocol':'quillmd-preserve-original-layout-v1','source_sha256':prep.WM_IOV_SHA256})
        self.assertEqual(packet.candidate_info['document_backend'],packet.inventory['document_backend'])
        self.assertEqual(packet.candidate_info['warnings'],list(prep.WM_LAYOUT_ADVISORIES))
        self.assertEqual(prep.validate_export_layout_policy(packet),packet.candidate_info['export_layout'])
        historical=prep.candidate_inspection(packet,info,{'reviewed_multi_column_rows':[]},{})
        self.assertNotIn('export_layout',historical)
        ordinary=self.packet()
        with patch.object(prep,'wm_inspection_admission',side_effect=AssertionError('wrong source policy')):
            self.assertIsNone(prep.validate_export_layout_policy(ordinary))

    def test_new_candidate_writer_explicitly_requests_policy_without_changing_old_record(self):
        packet,info,_=self.wm_packet()
        original_info=deepcopy(packet.candidate_info)
        result={'prepared_sha256':prep.WM_IOV_SHA256,'changes':[],'reviewed_multi_column_rows':[]}
        inspect=Mock(return_value={'safe':'candidate'})
        with patch.object(prep,'prepare_candidate',return_value=result),patch.object(prep,'inspect_template',return_value=info),\
                patch.object(prep,'candidate_inspection',inspect):
            prep.build_candidate(packet,{})
        self.assertTrue(inspect.call_args.kwargs['preserve_original_export_layout'])
        self.assertEqual(original_info,{})

    def test_protocol_source_null_extra_keys_and_unqualified_shape_refuse(self):
        packet,_=self.prepared()
        for mutation in ('protocol','source','null','extra','candidate','backend','inventory','baseline'):
            changed=deepcopy(packet)
            if mutation=='protocol':changed.candidate_info['export_layout']['protocol']='any-layout'
            elif mutation=='source':changed.candidate_info['export_layout']['source_sha256']='0'*64
            elif mutation=='null':changed.candidate_info['export_layout']=None
            elif mutation=='extra':changed.candidate_info['export_layout']['allow_everything']=True
            elif mutation=='candidate':changed.candidate_sha256='0'*64
            elif mutation=='backend':changed.candidate_info['document_backend']['mapping_digest']='0'*64
            elif mutation=='inventory':changed.inventory['fields'].pop()
            else:changed.candidate_info['qualified_warning_baseline']['source_sha256']='0'*64
            with self.subTest(mutation=mutation),self.assertRaises((ValidationError,ValueError)):
                prep.validate_export_layout_policy(changed)

    def test_policy_tamper_changes_existing_approval_seal_and_cannot_be_reused(self):
        packet,_=self.prepared();version=self.sealed_version(packet)
        original_bytes=(self.root/'original.docx').read_bytes();prepared_bytes=(self.root/'candidate.docx').read_bytes()
        self.assertEqual(source_for_version(version),self.root/'candidate.docx')
        packet.candidate_info['export_layout']['protocol']='changed-after-approval'
        self.assertNotEqual(approval_binding(packet),packet.approval_sha256)
        with self.assertRaises(ValidationError):source_for_version(version)
        self.assertEqual((self.root/'original.docx').read_bytes(),original_bytes)
        self.assertEqual((self.root/'candidate.docx').read_bytes(),prepared_bytes)

    def test_layout_reuse_returns_only_exact_policy_and_older_absence_stays_none(self):
        packet,_=self.prepared();version=self.sealed_version(packet)
        self.assertEqual(export_layout_for_version(version),prep.WM_EXPORT_LAYOUT_POLICY)
        returned=export_layout_for_version(version);returned['protocol']='local-mutated-copy'
        self.assertEqual(export_layout_for_version(version),prep.WM_EXPORT_LAYOUT_POLICY)
        packet.candidate_info.pop('export_layout');packet.approval_sha256=approval_binding(packet)
        self.assertIsNone(export_layout_for_version(version))
        self.assertNotIn('export_layout',packet.candidate_info)

    def test_alter_add_or_strip_after_approval_and_sealed_null_refuse(self):
        for mutation in ('alter','strip','add','null'):
            packet,_=self.prepared()
            if mutation=='add':packet.candidate_info.pop('export_layout')
            if mutation=='null':packet.candidate_info['export_layout']=None
            version=self.sealed_version(packet)
            if mutation=='alter':packet.candidate_info['export_layout']['protocol']='changed'
            elif mutation=='strip':packet.candidate_info.pop('export_layout')
            elif mutation=='add':packet.candidate_info['export_layout']=dict(prep.WM_EXPORT_LAYOUT_POLICY)
            with self.subTest(mutation=mutation),self.assertRaises((ValidationError,ValueError)):
                export_layout_for_version(version)

    def test_sealed_policy_with_wrong_backend_or_ordinary_source_refuses(self):
        for mutation in ('backend','source'):
            if mutation=='backend':
                packet,_=self.prepared();packet.candidate_info['document_backend']['mapping_digest']='0'*64
                version=self.sealed_version(packet)
            else:
                (self.root/'original.docx').write_bytes(self.ordinary_original)
                version=fixtures.PreparationPureTests.version(self)
                version.preparation.candidate_info['export_layout']=dict(prep.WM_EXPORT_LAYOUT_POLICY)
                version.preparation.approval_sha256=approval_binding(version.preparation)
            with self.subTest(mutation=mutation),self.assertRaises((ValidationError,ValueError)):
                export_layout_for_version(version)

    def test_historical_continuation_does_not_retroactively_add_layout_policy(self):
        packet,info,_=self.wm_packet();packet.template.format='docx'
        manager=Mock();manager.select_for_update.return_value.select_related.return_value.get.return_value=packet
        with patch.object(prep.TemplatePreparation,'objects',manager),patch.object(prep,'membership'),\
                patch.object(prep,'audit'),patch.object(prep,'inspect_template',return_value=info),\
                patch.object(prep,'inspect_preparation',return_value=packet.inventory):
            prep.continue_wm_review.__wrapped__(packet.pk,SimpleNamespace(pk='doctor1'),packet.revision,packet.candidate_sha256)
        self.assertNotIn('export_layout',packet.candidate_info)

    def test_new_approval_creates_new_version_and_reuse_keeps_exact_sealed_policy(self):
        packet,_=self.prepared();packet.state='review'
        packet.corrections={'labels':{f['key']:f['label'] for f in packet.candidate_info['fields']}}
        class TemplateRecord(SimpleNamespace):objects=Mock()
        packet.template=TemplateRecord(**vars(packet.template));packet.template.versions=Mock()
        packet.template.versions.order_by.return_value.first.return_value=SimpleNamespace(number=3)
        manager=Mock();manager.select_for_update.return_value.select_related.return_value.get.return_value=packet
        versions=Mock();actor=SimpleNamespace(pk='synthetic-doctor')
        def create(**values):
            return SimpleNamespace(**values,pk='new-approved-version',template_id=packet.template_id,preparation_id=packet.pk)
        versions.create.side_effect=create
        old_record={'number':3,'export_layout':None};old_snapshot=deepcopy(old_record)
        with patch.object(prep.TemplatePreparation,'objects',manager),patch.object(prep.TemplateVersion,'objects',versions),\
                patch.object(prep,'membership'),patch.object(prep,'audit'):
            version=prep.approve.__wrapped__(packet.pk,actor,packet.revision,packet.candidate_sha256,[],True,True)
        self.assertEqual(version.number,4);self.assertEqual(old_record,old_snapshot)
        self.assertEqual(packet.approval_sha256,approval_binding(packet))
        packet.approved_by_id=actor.pk
        with patch.object(prep,'call_role',side_effect=AssertionError('unnecessary preparation')):
            self.assertEqual(source_for_version(version),self.root/'candidate.docx')
            self.assertEqual(source_for_version(version),self.root/'candidate.docx')
        self.assertEqual(prep.validate_export_layout_policy(version.preparation),prep.WM_EXPORT_LAYOUT_POLICY)

    def test_bad_policy_refuses_before_approval_or_new_version_write(self):
        packet,_=self.prepared();packet.state='review';packet.candidate_info['export_layout']['protocol']='unsupported'
        manager=Mock();manager.select_for_update.return_value.select_related.return_value.get.return_value=packet
        versions=Mock()
        with patch.object(prep.TemplatePreparation,'objects',manager),patch.object(prep.TemplateVersion,'objects',versions),\
                patch.object(prep,'membership'),patch.object(prep,'audit'):
            with self.assertRaises(ValidationError):
                prep.approve.__wrapped__(packet.pk,SimpleNamespace(pk='doctor'),packet.revision,packet.candidate_sha256,[],True,True)
        versions.create.assert_not_called();packet.save.assert_not_called()
