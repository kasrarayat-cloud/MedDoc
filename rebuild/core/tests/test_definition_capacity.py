"""Definition-only prospective limits; all SDK requests are offline fixtures."""
from copy import deepcopy
from decimal import Decimal
from importlib import import_module
import json
from unittest.mock import patch
from django.db import DatabaseError,connection,transaction
from django.test import SimpleTestCase,TestCase,override_settings
from core import ai_stages
from core.models import AIStageReceipt,TemplateDefinitionPreparation
from core.security import private_path
from core.tests.test_semantic_preparation import DefinitionPreparationDatabaseTests

CONFIG={'mode':'live','provider':'anthropic','model':'claude-sonnet-5-5','input_rate':'2',
        'cached_rate':'0.2','output_rate':'10','semantic_definition_version':4,
        'semantic_component_contract':'field-components-v2'}

def historical(config):
    return {**config,'definition_stage_protocol':ai_stages.PROTOCOL,'definition_max_calls':2,
            'definition_request_byte_limit':512000,'definition_output_token_limit':16000,
            'definition_maximum_cost':str(ai_stages.quote(config,output_tokens=16000)*2)}


class DefinitionCapacityPureTests(SimpleTestCase):
    def test_prospective_and_frozen_v4_have_distinct_limits_and_exact_old_quote(self):
        old=historical(CONFIG);retained=ai_stages.encode(old);current=ai_stages.definition_pipeline_config(CONFIG)
        self.assertEqual(ai_stages.definition_limits(old),(16000,120))
        self.assertEqual(ai_stages.definition_limits(current),(32000,240))
        self.assertEqual(old['definition_maximum_cost'],'2.94000000000')
        self.assertEqual(Decimal(current['definition_maximum_cost']),Decimal('3.26'))
        with patch.object(ai_stages,'definition_pipeline_config',side_effect=AssertionError('No prospective reinterpretation')):
            ai_stages.validate_definition_config(old);ai_stages.validate_definition_config(current)
        self.assertEqual(ai_stages.encode(old),retained)

    def test_only_supported_prospective_definition_contract(self):
        for key,value in [('provider','openai'),('model','other'),('semantic_definition_version',3),
                          ('semantic_definition_version',4.0),('semantic_component_contract','field-components-v1')]:
            with self.subTest(key=key,value=value):
                config={**CONFIG,key:value};self.assertEqual(ai_stages.definition_pipeline_config(config),historical(config))

    def test_explicit_invalid_profile_never_falls_back(self):
        current=ai_stages.definition_pipeline_config(CONFIG)
        for key,values in [('definition_capacity_profile',[None,False,'unknown']),
            ('definition_output_token_limit',[True,'32000',32000.0,16000,32001]),
            ('definition_timeout_seconds',[True,'240',240.0,120,241]),
            ('semantic_definition_version',[True,'4',4.0,3]),
            ('semantic_component_contract',[None,'field-components-v1']),('model',['other']),('provider',['openai'])]:
            for value in values:
                with self.subTest(key=key,value=value),self.assertRaises(ai_stages.StageNotSent):
                    ai_stages.definition_limits({**current,key:value})
        with self.assertRaises(ai_stages.StageNotSent):ai_stages.definition_limits({**historical(CONFIG),'definition_timeout_seconds':240})
        for key,value in [('definition_max_calls',True),('definition_request_byte_limit',512001),('definition_maximum_cost','100')]:
            with self.assertRaises(ai_stages.StageNotSent):ai_stages.validate_definition_config({**current,key:value})

    def test_sdk_limits_zero_retries_and_truncation_remains_incomplete(self):
        import httpx
        from anthropic import Anthropic
        for current in [historical(CONFIG),ai_stages.definition_pipeline_config(CONFIG)]:
            maximum,timeout=ai_stages.definition_limits(current);sent=[];retained=[]
            def handle(request):
                sent.append(json.loads(request.content));self.assertEqual(request.extensions['timeout']['read'],timeout)
                return httpx.Response(200,json={'id':'msg_fixture','type':'message','role':'assistant','model':CONFIG['model'],
                    'content':[{'type':'text','text':'{"unfinished":'}],'stop_reason':'max_tokens','stop_sequence':None,
                    'usage':{'input_tokens':10,'output_tokens':maximum}})
            with httpx.Client(transport=httpx.MockTransport(handle))as http:
                def client(**kw):
                    self.assertEqual(kw,{'timeout':timeout,'max_retries':0})
                    return Anthropic(api_key='offline-fixture',base_url='https://fixture.invalid',http_client=http,**kw)
                with patch('anthropic.Anthropic',side_effect=client):
                    result=ai_stages._response({}, {'type':'object','properties':{}},'Original instructions',current,maximum,timeout,retained.append)
            self.assertEqual(len(sent),1);self.assertEqual(sent[0]['max_tokens'],maximum)
            self.assertEqual(len(retained),1);self.assertFalse(result[-1])

    def test_migration_changes_only_one_condition_and_reverse_is_exact(self):
        migration=import_module('core.migrations.0035_definition_capacity_profile')
        old=import_module('core.migrations.0033_retained_semantic_revalidation_v3').REVALIDATION_SQL
        self.assertEqual(migration.CAPACITY_SQL.replace(migration.NEW_CONDITION,migration.OLD_CONDITION),old)
        self.assertEqual(migration.Migration.operations[0].reverse_sql,old)


@override_settings(WORD_PREPARATION_ENABLED=True,AI_MODE='fixture',TESTING_AUTHORITY_MODE='',TESTING_AUTHORITY_ID='',TESTING_AUTHORITY_SHA256='')
class DefinitionCapacityDatabaseTests(TestCase):
    setUp=DefinitionPreparationDatabaseTests.setUp

    def parent(self,config):
        prep=TemplateDefinitionPreparation.objects.create(source_version=self.source,requested_by=self.user,config=config)
        prep.state='proposer';prep.save(update_fields=['state']);return prep

    def reserve(self,config):
        prep=self.parent(config)
        return AIStageReceipt.objects.create(definition_preparation=prep,stage='definition_proposer',attempt=1,
            config=config,provider=config['provider'],requested_model=config['model'],simulated=True,
            request_path='receipts/'+'a'*48+'.json',request_sha256='b'*64,quote_maximum=0)

    def test_actual_guard_old_new_and_forged_config(self):
        ai_stages.assert_installed_guards()
        with transaction.atomic():
            self.reserve(historical({**CONFIG,'mode':'fixture'}))
            transaction.set_rollback(True)
        current=ai_stages.definition_pipeline_config({**CONFIG,'mode':'fixture'})
        for key,value in [('definition_capacity_profile',None),('definition_capacity_profile','other'),
            ('definition_timeout_seconds',None),('definition_timeout_seconds','240'),('definition_timeout_seconds',240.0),
            ('definition_output_token_limit',True),('semantic_definition_version','4'),('model','other'),
            ('semantic_component_contract','field-components-v1'),('definition_max_calls',3)]:
            with self.subTest(key=key,value=value),self.assertRaises(DatabaseError),transaction.atomic():self.reserve({**current,key:value})
        orphan=historical({**CONFIG,'mode':'fixture'});orphan['definition_timeout_seconds']=240
        with self.assertRaises(DatabaseError),transaction.atomic():self.reserve(orphan)
        receipt=self.reserve(current)
        with self.assertRaises(DatabaseError),transaction.atomic():AIStageReceipt.objects.filter(pk=receipt.pk).update(config={})

    def test_actual_stage_retains_old_envelope_and_new_timeout_without_extra_calls(self):
        for config in [historical({**CONFIG,'mode':'fixture'}),ai_stages.definition_pipeline_config({**CONFIG,'mode':'fixture'})]:
            with transaction.atomic():
                prep=self.parent(config)
                args=dict(definition_preparation=prep,stage='definition_proposer',payload={'x':'exact'},schema={'type':'object'},instructions='Exact retained instruction.',config=config,fixture_output={})
                self.assertEqual(ai_stages.execute_stage(**args),{})
                receipt=prep.ai_stage_receipts.get();envelope=json.loads(private_path(receipt.request_path).read_bytes())
                expected={'protocol':ai_stages.PROTOCOL,'stage':'definition_proposer','attempt':1,'payload':{'x':'exact'},'schema':{'type':'object'},'instructions':'Exact retained instruction.','max_output_tokens':config['definition_output_token_limit']}
                if 'definition_capacity_profile'in config:expected['timeout_seconds']=240
                self.assertEqual(private_path(receipt.request_path).read_bytes(),ai_stages.encode(expected))
                with self.assertRaises(ai_stages.StageNotSent):ai_stages.execute_stage(**args)
                self.assertEqual(prep.ai_stage_receipts.count(),1)
                transaction.set_rollback(True)

    def test_actual_migration_reverse_restores_exact_then_forward_reapplies(self):
        migration=import_module('core.migrations.0035_definition_capacity_profile')
        current=import_module('core.migrations.0036_component_choice_capacity')
        with transaction.atomic():
            with connection.cursor()as cursor:cursor.execute(migration.PREVIOUS_SQL)
            with self.assertRaises(ai_stages.StageNotSent):ai_stages.assert_installed_guards()
            with connection.cursor()as cursor:cursor.execute(migration.CAPACITY_SQL)
            with self.assertRaises(ai_stages.StageNotSent):ai_stages.assert_installed_guards()
            with connection.cursor()as cursor:cursor.execute(current.CAPACITY_SQL)
            ai_stages.assert_installed_guards()
