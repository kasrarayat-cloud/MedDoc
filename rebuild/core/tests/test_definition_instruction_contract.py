"""Prospective composite meaning instructions; historical provider bytes stay sealed."""
from copy import deepcopy
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase, override_settings

from core import preparation, semantic_preparation as workflow
from core.models import TemplateDefinitionPreparation
from core.tests import test_semantic_preparation as existing, test_word_answer_contract as word_existing
from documents import semantic_preparation_roles as roles


class DefinitionInstructionContractTests(SimpleTestCase):
    def test_historical_v3_envelope_matches_pre_rowan_revision(self):
        # Computed from unmodified commit 52b097065, independently of the new
        # implementation. Existing v1/v2 hash assertions remain unchanged.
        fields = [{'key':'cell_0','label':'Subjective','kind':'text','locator':{'cell':0}}]
        inventory = roles.build_inventory(fields,source_version_id='synthetic-source',source_sha256='a'*64,
            original={'stories':[{'texts':['Subjective']}],'questions':[]})
        envelope = {role:{'schema':roles.role_schema(role,3), 'instructions':roles.role_instructions(role,3),
            'timed_instructions':roles.role_instructions(role,3,timing_reference=roles.TEMPORAL_REFERENCE_CONTRACT),
            'fixture':roles.fixture_role(fields,inventory,role,definition_version=3)} for role in ('proposer','checker')}
        self.assertEqual(roles.digest(envelope),'b3efb0f96a62b628f969ff878b144f8b9eb6e7a96ec64eba96baec682fabdf73')

    def test_composite_instructions_require_explicit_contract_and_preserve_remainder(self):
        for version in (2,3):
            for role in ('proposer','checker'):
                for timing in (None,roles.TEMPORAL_REFERENCE_CONTRACT):
                    old=roles.role_instructions(role,version,timing_reference=timing)
                    new=roles.role_instructions(role,version,timing_reference=timing,
                        meaning_contract=roles.COMPOSITE_MEANING_CONTRACT)
                    self.assertNotIn(roles.COMPOSITE_MEANING_INSTRUCTIONS,old)
                    self.assertEqual(new.count(roles.COMPOSITE_MEANING_INSTRUCTIONS),1)
                    self.assertEqual(new.replace(roles.COMPOSITE_MEANING_INSTRUCTIONS,''),old)
        with self.assertRaises(roles.DefinitionError):
            roles.role_instructions('proposer',1,meaning_contract=roles.COMPOSITE_MEANING_CONTRACT)

    def test_reusable_role_dispatch_uses_retained_configuration_not_current_defaults(self):
        helper=existing.DefinitionPreparationPureTests()
        for version in (1,2,3):
            for role in ('proposer','checker'):
                prep=helper.prep();prep.config={'mode':'live','semantic_definition_version':version}
                expected=roles.fixture_role(prep.source_version.fields,prep.inventory,role,definition_version=version)
                with patch.object(workflow.ai_stages,'execute_stage',return_value=expected) as send:
                    workflow._call_role(prep,role)
                self.assertEqual(send.call_args.kwargs['instructions'],roles.role_instructions(role,version))
                if version==3:
                    prep.config[roles.MEANING_CONTRACT_KEY]=roles.COMPOSITE_MEANING_CONTRACT
                    with patch.object(workflow.ai_stages,'execute_stage',return_value=expected) as send:
                        workflow._call_role(prep,role)
                    self.assertIn(roles.COMPOSITE_MEANING_INSTRUCTIONS,send.call_args.kwargs['instructions'])

    def test_unknown_explicit_contract_refuses_before_any_provider_stage(self):
        for value in (None,'','future-contract',False,[],{}):
            with self.subTest(value=value):
                prep=existing.DefinitionPreparationPureTests().prep()
                prep.config.update(semantic_definition_version=3,**{roles.MEANING_CONTRACT_KEY:value})
                with patch.object(workflow.ai_stages,'execute_stage') as send, self.assertRaises(ValidationError):
                    workflow._call_role(prep,'proposer')
                send.assert_not_called()
                with self.assertRaises(roles.DefinitionError):
                    preparation.provider_request({},'proposer',{roles.MEANING_CONTRACT_KEY:value})

    def test_inline_upload_request_changes_only_prospective_system_wording(self):
        helper=word_existing.FreshWordContractTests();helper.setUp();self.addCleanup(helper.doCleanups)
        for role in ('proposer','checker'):
            proposal=helper.version().preparation.proposal if role=='checker' else None
            old=preparation.provider_request(helper.inv,role,helper.config,proposal)
            config={**helper.config,roles.MEANING_CONTRACT_KEY:roles.COMPOSITE_MEANING_CONTRACT}
            new=preparation.provider_request(helper.inv,role,config,proposal)
            self.assertNotIn(roles.COMPOSITE_MEANING_INSTRUCTIONS,old['system'])
            self.assertEqual(new['system'].replace(roles.COMPOSITE_MEANING_INSTRUCTIONS,''),old['system'])
            self.assertEqual({k:v for k,v in old.items() if k!='system'},
                             {k:v for k,v in new.items() if k!='system'})


@override_settings(WORD_PREPARATION_ENABLED=True,AI_MODE='fixture',TESTING_AUTHORITY_MODE='',
    TESTING_AUTHORITY_ID='',TESTING_AUTHORITY_SHA256='',
    STORAGES={'default':{'BACKEND':'django.core.files.storage.FileSystemStorage'},
              'staticfiles':{'BACKEND':'django.contrib.staticfiles.storage.StaticFilesStorage'}})
class DefinitionInstructionPersistenceTests(TestCase):
    def setUp(self):
        existing.DefinitionPreparationDatabaseTests.setUp(self)

    def test_both_new_creation_paths_freeze_contract_without_changing_original_mapping(self):
        before=deepcopy(self.source.fields)
        reusable=workflow.create_preparation(self.source,self.user)
        upload=preparation.create_preparation(self.template,self.user)
        reusable.refresh_from_db();upload.refresh_from_db();self.source.refresh_from_db()
        for prep in (reusable,upload):
            self.assertEqual(prep.config[roles.MEANING_CONTRACT_KEY],roles.COMPOUND_ANSWER_CONTRACT)
        self.assertEqual(self.source.fields,before)
        self.assertEqual(self.source.semantic_definitions,{})
        self.assertEqual(reusable.ai_stage_receipts.count(),0)
        self.assertEqual(upload.receipts.count(),0)

    def test_repeated_historical_start_reuses_record_without_adding_new_contract(self):
        old=TemplateDefinitionPreparation.objects.create(source_version=self.source,requested_by=self.user,
            config={'mode':'fixture','semantic_definition_version':2})
        before=deepcopy(old.config)
        self.assertEqual(workflow.create_preparation(self.source,self.user).pk,old.pk)
        old.refresh_from_db();self.assertEqual(old.config,before)
        self.assertNotIn(roles.MEANING_CONTRACT_KEY,old.config)
        self.assertEqual(old.ai_stage_receipts.count(),0)
