"""Offline native-adapter fault controls; no installed files, DB or provider calls."""
import copy
from contextlib import contextmanager,redirect_stdout
import hashlib
from io import StringIO
import json
from pathlib import Path,PurePosixPath
import tempfile
import unittest
from unittest.mock import patch

from ops import word_milestone_delivery as delivery

CANDIDATE='a'*40


def plan():
    return {'format':1,'qualified':True,'source_before':delivery.BASE,'word_base':delivery.WORD_BASE,
        'candidate':CANDIDATE,'source_sha256':{'rebuild/example.py':'b'*64},
        'migration_nodes':list(delivery.MIGRATIONS),'minimum_available_bytes':delivery.MINIMUM_SPACE,
        'static_source_sha256':{name:'c'*64 for name in delivery.STATIC_INPUTS},
        'campaign':delivery.CAMPAIGN,'campaign_scope_sha256':delivery.CAMPAIGN_SCOPE,
        'provider_calls':0,'authentication_submissions':0,'historical_deployment_approval_verified':False,
        'original_baselines_replaced':False}


def populations():
    schema={'functions':{},'triggers':{},'constraints':{},'indexes':{},'policies':[],'sequence_metadata':[],
        'default_acl':[],'sequences':{'core_template_id_seq':[[4,True]],
            'django_migrations_id_seq':[[100,True]],'django_content_type_id_seq':[[100,True]],
            'auth_permission_id_seq':[[100,True]]}}
    tables={name:{'columns':['id','content'],'old_columns':[['id','uuid','NO',None,None],
        ['content','text','NO',None,None]],'old_rows':'d'*64,'rows':2,'sha256':'e'*64,
        'definitions':[['id','uuid',True,None,'','',True],['content','text',True,None,'','',True]],
        'owner_acl':[['quillmd_owner',None,False,False,'r']]}
        for name in ('core_templateversion','auth_permission','django_content_type','django_migrations')}
    before={'tables':tables,'invariants':{'broken':0},'referenced_files':{'templates/original.docx':'f'*64},
        'schema':schema,'applied_core_migrations':['0018_servicehealth'],'expected_new_table_privileges':[]}
    after=copy.deepcopy(before)
    contract=delivery.migration_model_metadata()['columns']
    after['tables']['core_templateversion']['columns']+=sorted(delivery.ADDED_COLUMNS)
    after['tables']['core_templateversion']['definitions']+=copy.deepcopy(contract['core_templateversion'])
    for name in delivery.NEW_TABLES:
        after['tables'][name]={'rows':0,'columns':[value[0] for value in contract[name]],'definitions':copy.deepcopy(contract[name]),
            'old_columns':[],'owner_acl':[['quillmd_owner',None,False,False,'r']],'privileges':[],'old_rows':'0'*64}
    after['added_migrations']=[('core',name) for name in delivery.MIGRATIONS]
    after['added_content_types']=[('core',model) for model in ('templatepreparation','preparationreceipt')]
    after['added_permissions']=[(model,verb+'_'+model) for model in ('templatepreparation','preparationreceipt')
        for verb in ('add','change','delete','view')]
    functions,triggers=delivery.migration_sql_metadata()
    after['expected_functions']=functions;after['expected_triggers']=triggers
    after['schema']['functions']=copy.deepcopy(functions)
    after['schema']['triggers']={name:{**value,'definition':'source-derived trigger'} for name,value in triggers.items()}
    for kind in ('constraints','indexes'):after['schema'][kind]=copy.deepcopy(delivery.SCHEMA_CONTRACT[kind])
    for name,count in (('django_migrations_id_seq',5),('django_content_type_id_seq',2),('auth_permission_id_seq',8)):
        after['schema']['sequences'][name][0][0]+=count
    after['applied_core_migrations']+=list(delivery.MIGRATIONS)
    return before,after


class FakeHost:
    """Inject one concrete failure at a boundary and retain operation ordering."""
    def __init__(self,failure=None):
        self.before,self.after=populations();self.failure=failure;self.events=[];self.records={}
        self.source=delivery.BASE;self.migrated=False;self.published=False;self.recovered=False
        self.inside=False;self.reconciled=0
        self.rolled_back=False
        self.ingress={'inode':8,'sha256':'1'*64}
        self.configuration={delivery.normal.INGRESS:{'inode':7,'sha256':'0'*64},
            '/etc/systemd/system/voiceassistmain-product.service':{'inode':9,'sha256':'2'*64}}
    def event(self,name):
        self.events.append(name)
        if self.failure==name:raise delivery.Refusal('word_delivery_injected_'+name)
    def check_plan(self,value):self.event('check_plan')
    @contextmanager
    def hold(self,recovering=False):
        assert not self.inside;self.inside=True;self.events.append('recovery_hold' if recovering else 'hold')
        try:yield
        finally:self.inside=False;self.events.append('release')
    def space(self,stage):
        self.event('space_'+stage)
        return {'phase':stage,'available_bytes':delivery.MINIMUM_SPACE,'minimum_available_bytes':delivery.MINIMUM_SPACE}
    def record(self,stage,value):self.records[stage]=copy.deepcopy(value)
    def snapshot(self,before=None):
        assert self.inside
        database=copy.deepcopy(self.after if self.migrated else self.before)
        if self.rolled_back:
            for name,count in (('django_migrations_id_seq',5),('django_content_type_id_seq',2),('auth_permission_id_seq',8)):
                database['schema']['sequences'][name][0][0]+=count
        if before and not self.migrated:
            database.update(added_migrations=[],added_content_types=[],added_permissions=[])
        configuration=copy.deepcopy(self.configuration)
        if self.published:configuration[delivery.normal.INGRESS]=self.ingress
        if self.failure=='foreign_inode' and self.migrated:
            configuration['/etc/systemd/system/voiceassistmain-product.service']['inode']+=1
        if self.failure=='partial_schema' and self.source==CANDIDATE:
            database['tables']['core_templateversion']['columns'].append('prepared_path')
        return {'files':{'templates/original.docx':{'sha256':'f'*64}},'mail':{},
            'configuration':configuration,'foreign_services':{'voiceassistmain-product.service':{'MainPID':'400','InvocationID':'old'}},
            'database':database}
    def native_admission(self,before):self.event('native_admission')
    def service(self,action,unit):assert self.inside;self.events.append(action+':'+unit)
    def no_pending_work(self):self.event('no_pending')
    def require_stopped(self):self.event('require_stopped')
    def capture_backup(self,before):self.event('backup');return {'authenticated_dump_and_objects':True}
    def prepare_static(self):self.event('static_stage');return {'qualified':True}
    def migrate_and_forward(self,candidate):
        self.event('forward');self.source=candidate
        if self.failure in ('ff_then_rollback','partial_schema'):
            self.rolled_back=True
            raise delivery.Refusal('word_delivery_injected_commit_result')
        self.migrated=True
        if self.failure=='unknown_complete_commit':raise delivery.Refusal('word_delivery_injected_commit_result')
    def source_revision(self):return self.source
    def install_static(self,preparation):self.event('static_install')
    def configure(self,recovery=False):self.event('configure')
    def readiness(self,candidate):self.event('readiness');return {'release':candidate}
    def publish_ingress(self):self.event('ingress');self.published=True;return self.ingress
    def normal_structure(self):self.event('normal_structure');return {'authenticated_acceptance_required':True}
    def require_stop_for_recovery(self):self.event('recovery_stop')
    def reconcile_forward(self,before,observed):
        delivery.original_population(before['database'],observed['database'],allow_metadata_consumption=True)
        self.event('reconcile_forward');self.reconciled+=1;self.migrated=True
        return {'complete':True,'migration_replay':False,'attempts':1}
    def recover(self,preparation,actual):
        self.event('recover');self.recovered=True
        return {'complete':True,'served_revision':actual,'feature_campaign_normal_origin_off':actual!=delivery.BASE}


class ScheduledRetentionTests(unittest.TestCase):
    unit='founder-receptionist-quality-retention.service'
    def endpoint(self,start=1000000,invocation='a'*32):
        timer=self.unit.removesuffix('.service')+'.timer'
        return {'LoadState':'loaded','ActiveState':'inactive','SubState':'dead','MainPID':'0',
            'InvocationID':invocation,'FragmentPath':'/etc/systemd/system/'+self.unit,
            'DropInPaths':'','UnitFileState':'static','WorkingDirectory':'/home/voiceassistmain/VoiceAssistMain',
            'ExecMainStartTimestampMonotonic':str(start),
            'scheduled_retention':{'runtime':{'Type':'oneshot','TriggeredBy':timer,'Result':'success',
                'ExecMainCode':'1','ExecMainStatus':'0','ExecMainExitTimestampMonotonic':str(start+500000),
                'InactiveExitTimestampMonotonic':str(start)},
                'timer_identity':{'Id':timer,'LoadState':'loaded','ActiveState':'active','SubState':'waiting',
                    'FragmentPath':'/etc/systemd/system/'+timer,'DropInPaths':'','UnitFileState':'enabled','Unit':self.unit,
                    'InvocationID':'c'*32,'ActiveEnterTimestampMonotonic':'500000','InactiveExitTimestampMonotonic':'500000'},
                'timer_values':[start-25000,[['OnUnitActiveUSec',60000000,start+60000000],['OnBootUSec',30000000,30000000]],1000000,0,False],
                'boot_id':'12345678-1234-1234-1234-123456789abc','observed_monotonic_us':start+1000000,
                'attribution':'prospectively expected timer-correlated transition; dispatch history unverified'}}
    def pair(self):return {self.unit:self.endpoint()},{self.unit:self.endpoint(61000000,'b'*32)}
    def test_exact_scheduled_transition_and_unchanged_endpoint(self):
        before,after=self.pair()
        self.assertTrue(delivery.foreign_service_preservation(before,after))
        self.assertTrue(delivery.foreign_service_preservation(before,copy.deepcopy(before)))
    def test_unexplained_other_unit_invocation_refused(self):
        before,after=self.pair()
        before['other.service']={'InvocationID':'a'};after['other.service']={'InvocationID':'b'}
        with self.assertRaises(delivery.Refusal):delivery.foreign_service_preservation(before,after)
    def test_stable_service_changes_refused(self):
        for key,value in [('MainPID','123'),('WorkingDirectory','/changed'),('DropInPaths','/changed'),
            ('UnitFileState','disabled'),('FragmentPath','/changed'),('ActiveState','active'),('SubState','running')]:
            with self.subTest(key=key):
                before,after=self.pair();after[self.unit][key]=value
                with self.assertRaises(delivery.Refusal):delivery.foreign_service_preservation(before,after)
    def test_timer_binding_failures_refused(self):
        cases=[('runtime','Type','simple'),('runtime','TriggeredBy','other.timer'),('runtime','Result','exit-code'),
            ('runtime','ExecMainCode','2'),('runtime','ExecMainStatus','1'),('timer_identity','ActiveState','inactive'),
            ('timer_identity','Unit','other.service'),('timer_identity','DropInPaths','/changed')]
        for group,key,value in cases:
            with self.subTest(group=group,key=key):
                before,after=self.pair();after[self.unit]['scheduled_retention'][group][key]=value
                with self.assertRaises(delivery.Refusal):delivery.foreign_service_preservation(before,after)
    def test_wrong_trigger_profile_boot_and_sequence_refused(self):
        for mutate in [lambda c:c['timer_values'].__setitem__(0,1),
            lambda c:c['timer_values'].__setitem__(2,2000000),lambda c:c['timer_values'].__setitem__(3,1),
            lambda c:c['timer_values'].__setitem__(4,True),lambda c:c['timer_values'][1][0].__setitem__(1,120000000),
            lambda c:c.__setitem__('boot_id','87654321-1234-1234-1234-123456789abc'),
            lambda c:c['runtime'].__setitem__('ExecMainExitTimestampMonotonic','1'),
            lambda c:c.__setitem__('observed_monotonic_us',1)]:
            before,after=self.pair();mutate(after[self.unit]['scheduled_retention'])
            with self.assertRaises(delivery.Refusal):delivery.foreign_service_preservation(before,after)
        before,after=self.pair();after[self.unit]['InvocationID']=before[self.unit]['InvocationID']
        with self.assertRaises(delivery.Refusal):delivery.foreign_service_preservation(before,after)
        before,after=self.pair();after[self.unit]['scheduled_retention']['timer_identity']['InvocationID']='d'*32
        with self.assertRaises(delivery.Refusal):delivery.foreign_service_preservation(before,after)
    def test_expected_timer_run_never_waives_configuration_or_inode(self):
        before,after=self.pair()
        baseline={'files':{},'mail':{},'foreign_services':before,'configuration':{'/foreign':{'inode':1}}}
        changed=copy.deepcopy(baseline);changed['foreign_services']=after;changed['configuration']['/foreign']['inode']=2
        with self.assertRaises(delivery.Refusal):delivery.preservation(baseline,changed)
    def test_duplicate_and_extra_bus_metadata_refused_before_comparison(self):
        endpoint=self.endpoint();context=endpoint.pop('scheduled_retention')
        timer=self.unit.removesuffix('.service')+'.timer'
        config={'/etc/systemd/system/'+name:{'sha256':digest} for name,digest in
            zip((self.unit,timer),delivery.SCHEDULED_RETENTION[self.unit])}
        bus_path='/org/freedesktop/systemd1/unit/'+''.join(c if c.isalnum() else '_'+format(ord(c),'02x') for c in timer)
        for fault in (None,'duplicate_path','duplicate_trigger','extra'):
            def command(argv,**kwargs):
                if argv[0]=='systemctl':
                    source=context['runtime'] if argv[2]==self.unit else context['timer_identity']
                    names=argv[3].removeprefix('--property=').split(',')
                    return ('\n'.join(name+'='+source[name] for name in names)+'\n').encode()
                if argv[2]=='call':
                    if fault=='duplicate_path':return ('{"type":"s","type":"o","data":'+json.dumps([bus_path])+'}').encode()
                    return json.dumps({'type':'o','data':[bus_path]}).encode()
                rows=[{'type':kind,'data':value} for kind,value in zip(['t','a(stt)','t','t','b'],context['timer_values'])]
                if fault=='extra':rows[0]['unreviewed']='extra'
                lines=[json.dumps(row) for row in rows]
                if fault=='duplicate_trigger':lines[0]='{"type":"s","type":"t","data":'+str(context['timer_values'][0])+'}'
                return ('\n'.join(lines)+'\n').encode()
            with patch.object(delivery.old,'command',side_effect=command),patch.object(Path,'read_text',return_value=context['boot_id']):
                if fault:
                    with self.assertRaises(delivery.Refusal):delivery.scheduled_retention_observation(self.unit,config,endpoint,lambda _:endpoint)
                else:self.assertEqual(delivery.scheduled_retention_observation(self.unit,config,endpoint,lambda _:endpoint)['timer_values'],context['timer_values'])


class ForeignTemplateTests(unittest.TestCase):
    template='external-task@.service'
    instance='external-task@one.service'
    def observation(self,*,files=None,instances=None,active='active',second=None,extra='',load='loaded'):
        config={'/etc/systemd/system/'+self.template:{'sha256':'a'*64,'inode':100}}
        rows=[{'unit_file':self.template,'state':'static','preset':None}] if files is None else files
        units=[] if instances is None else instances
        calls=[]
        def command(argv,**kwargs):
            calls.append(argv)
            if argv[1]=='list-unit-files':return json.dumps(rows).encode()
            if argv[1]=='list-units':return json.dumps(second if second is not None and
                sum(row[1]=='list-units' for row in calls)>1 else units).encode()
            self.assertNotEqual(argv[2],self.template)
            return ('LoadState='+load+'\nActiveState='+active+'\nSubState=running\nMainPID=123\n'
                'InvocationID='+'a'*32+'\nFragmentPath=/etc/systemd/system/'+self.template+'\n'
                'DropInPaths=\nUnitFileState=static\nWorkingDirectory=/external\n'
                'ExecMainStartTimestampMonotonic=100\n'+extra).encode()
        with patch.object(delivery.old,'command',side_effect=command):
            value=delivery.foreign_service_observation(config)
        return value,calls
    def test_uninstantiated_template_has_file_state_and_no_invented_process(self):
        value,calls=self.observation()
        self.assertEqual(value[self.template],{'template_file':True,'UnitFileState':'static',
            'UnitFilePreset':None,'instances':{}})
        self.assertEqual([row[1] for row in calls],['list-unit-files','list-units','list-units'])
        self.assertIn('external-task@*.service',calls[1])
    def test_loaded_instances_preserve_pid_invocation_and_template_state(self):
        units=[{'unit':self.instance,'load':'loaded','active':'active','sub':'running'}]
        value,_=self.observation(instances=units)
        self.assertEqual(value[self.template]['instances'][self.instance]['MainPID'],'123')
        host=FakeHost()
        with host.hold():before=host.snapshot()
        before['foreign_services']=value
        for target,key,new in ((value[self.template],'UnitFileState','enabled'),
                (value[self.template]['instances'][self.instance],'MainPID','124'),
                (value[self.template]['instances'][self.instance],'InvocationID','changed')):
            after=copy.deepcopy(before)
            if key=='UnitFileState':after['foreign_services'][self.template][key]=new
            else:after['foreign_services'][self.template]['instances'][self.instance][key]=new
            with self.assertRaises(delivery.Refusal):delivery.preservation(before,after)
        after=copy.deepcopy(before);after['foreign_services'][self.template]['instances']={}
        with self.assertRaises(delivery.Refusal):delivery.preservation(before,after)
    def test_missing_duplicate_or_unrelated_file_states_refuse(self):
        row={'unit_file':self.template,'state':'static','preset':None}
        for rows in ([],[row,row],[{**row,'unit_file':'other@.service'}],[{**row,'state':''}]):
            with self.subTest(rows=rows),self.assertRaises(delivery.Refusal):self.observation(files=rows)
    def test_wrong_duplicate_or_racing_instances_refuse(self):
        row={'unit':self.instance,'load':'loaded','active':'active','sub':'running'}
        for rows in ([{**row,'unit':'other@one.service'}],[row,row],[{**row,'active':'inactive'}],
                     [{**row,'unit':self.template}]):
            with self.subTest(rows=rows),self.assertRaises(delivery.Refusal):self.observation(instances=rows)
    def test_concrete_unit_read_failure_is_never_suppressed(self):
        with patch.object(delivery.old,'command',side_effect=delivery.old.Refusal('bounded_command_failed')):
            with self.assertRaises(delivery.old.Refusal):delivery.foreign_service_observation(
                {'/etc/systemd/system/external.service':{'sha256':'a'*64}})
    def test_malformed_properties_enums_and_missing_preset_refuse(self):
        unit={'unit':self.instance,'load':'loaded','active':'active','sub':'running'}
        for kwargs in ({'extra':'MainPID=456\n'}, {'active':'invented'}, {'load':'invented'}):
            with self.subTest(kwargs=kwargs),self.assertRaises(delivery.Refusal):self.observation(instances=[unit],**kwargs)
        for row in ({'unit_file':self.template,'state':'static'},
                {'unit_file':self.template,'state':'invented','preset':None}):
            with self.subTest(row=row),self.assertRaises(delivery.Refusal):self.observation(files=[row])
    def test_instance_arrival_disappearance_and_state_race_refuse(self):
        first={'unit':self.instance,'load':'loaded','active':'active','sub':'running'}
        for second in ([],[first,{**first,'unit':'external-task@two.service'}],
                       [{**first,'active':'inactive','sub':'dead'}]):
            with self.subTest(second=second),self.assertRaises(delivery.Refusal):
                self.observation(instances=[first],second=second)
        with self.assertRaises(delivery.Refusal):self.observation(instances=[],second=[first])


class PortableMetadataTests(unittest.TestCase):
    def test_source_metadata_does_not_require_native_host_interpreter(self):
        delivery.migration_model_metadata.cache_clear()
        try:
            with patch.object(delivery, 'APP', Path('/nonexistent-native-host/rebuild')):
                columns=delivery.migration_model_metadata()['columns']
            self.assertEqual(set(columns), set(delivery.NEW_TABLES)|{'core_templateversion'})
        finally:
            delivery.migration_model_metadata.cache_clear()

    def test_native_admission_requires_exact_qualified_engine(self):
        from types import SimpleNamespace
        host=delivery.NativeHost.__new__(delivery.NativeHost)
        host.source_revision=lambda:delivery.BASE
        host.native=SimpleNamespace(state=lambda unit:{'ActiveState':'inactive','MainPID':'0'})
        host.storage=None;host.no_pending_work=lambda:None
        before={'database':{'tables':dict.fromkeys(delivery.old.TABLES),
            'applied_core_migrations':['0018_servicehealth'],'schema':{'default_acl':[]},
            'postgresql_server_version_num':delivery.SCHEMA_CONTRACT['postgresql_server_version_num']}}
        with patch.object(delivery.old,'service_boundary') as check:
            host.native_admission(before);check.assert_called_once()
        for engine in ('160015','170010','180000'):
            changed=copy.deepcopy(before);changed['database']['postgresql_server_version_num']=engine
            with patch.object(delivery.old,'service_boundary') as check,self.assertRaisesRegex(
                    delivery.Refusal,'native_canonical_schema_engine_version'):
                host.native_admission(changed)
            check.assert_not_called()


class EnvironmentTests(unittest.TestCase):
    original=(b'# retain bytes\nQUILLMD_DATA_MODE=synthetic\nQUILLMD_PREVIEW_AUTH_ENABLED=1\n'
        b'QUILLMD_APP_BASE_URL=https://app.quillmd.com:9443\nQUILLMD_AI_MODE=live\nQUILLMD_AI_PROVIDER=anthropic\n'
        b'QUILLMD_RELEASE_SHA='+delivery.BASE.encode()+b'\nAPI_TOKEN="literal-private-example"\n')
    def test_environment_changes_only_declared_keys_and_recovery_disables(self):
        prepared=delivery.render_environment(self.original,CANDIDATE)
        self.assertIn(b'API_TOKEN="literal-private-example"\n',prepared)
        self.assertIn(b'QUILLMD_WORD_PREPARATION_ENABLED="1"',prepared)
        recovered=delivery.render_environment(self.original,CANDIDATE,recovery=True)
        self.assertIn(b'QUILLMD_WORD_PREPARATION_ENABLED="0"',recovered)
        self.assertIn(b'QUILLMD_WORD_PREPARATION_CAMPAIGN=""',recovered)
        self.assertIn(b'QUILLMD_OWNER_NORMAL_ORIGIN_ENABLED="0"',recovered)
        self.assertIn(b'QUILLMD_RELEASE_SHA="'+CANDIDATE.encode()+b'"',recovered)
    def test_rejects_patient_unrestricted_or_duplicate_release(self):
        for raw in (self.original.replace(b'=synthetic\n',b'=real\n'),
            self.original.replace(b'PREVIEW_AUTH_ENABLED=1',b'PREVIEW_AUTH_ENABLED=0'),
            self.original.replace(b'app.quillmd.com:9443',b'app.quillmd.com'),
            self.original+b'QUILLMD_RELEASE_SHA="'+CANDIDATE.encode()+b'"\n'):
            with self.subTest(raw=delivery.sha(raw)),self.assertRaises(delivery.Refusal):
                delivery.render_environment(raw,CANDIDATE)
    def test_default_cli_accesses_no_installed_state_and_selected_is_unqualified(self):
        with patch.object(delivery,'QUALIFIED',False),patch.object(delivery,'NativeHost',side_effect=AssertionError('installed access')),redirect_stdout(StringIO()) as output:
            self.assertEqual(delivery.main([]),0)
            self.assertFalse(json.loads(output.getvalue())['installed_state_accessed'])
            with self.assertRaisesRegex(delivery.Refusal,'finished_diff_qualification_required'):
                delivery.main(['--execute','--directory','/irrelevant'])
        with patch.object(delivery,'QUALIFIED',True),patch.object(delivery,'NativeHost',side_effect=AssertionError('installed access')),redirect_stdout(StringIO()) as output:
            self.assertEqual(delivery.main([]),0)
            self.assertFalse(json.loads(output.getvalue())['installed_state_accessed'])
    def test_space_requirement_is_actual_28gib_not_capacity(self):
        from types import SimpleNamespace
        for available,admitted in ((delivery.MINIMUM_SPACE-1,False),(delivery.MINIMUM_SPACE,True)):
            value=SimpleNamespace(f_bavail=available,f_frsize=1,f_favail=400)
            with tempfile.TemporaryDirectory() as directory,patch.object(delivery,'ROOT',Path(directory)),\
                    patch.object(delivery.os,'statvfs',return_value=value) as measure:
                if admitted:
                    observation=delivery.admission_space('control')
                    self.assertEqual(observation['available_bytes'],available)
                    self.assertEqual(observation['filesystem_device'],Path(directory).stat().st_dev)
                else:
                    with self.assertRaisesRegex(delivery.Refusal,'storage_28gib'):delivery.admission_space('control')
                measure.assert_called_once_with(Path(directory))


class PreservationTests(unittest.TestCase):
    def test_fresh_baseline_accepts_exact_state_but_rejects_inode_content_and_invocation(self):
        host=FakeHost()
        with host.hold():before=host.snapshot()
        self.assertTrue(delivery.preservation(before,copy.deepcopy(before)))
        mutations=(('configuration','/etc/systemd/system/voiceassistmain-product.service','inode',10),
            ('configuration','/etc/systemd/system/voiceassistmain-product.service','sha256','8'*64),
            ('foreign_services','voiceassistmain-product.service','MainPID','401'),
            ('foreign_services','voiceassistmain-product.service','InvocationID','new'))
        for group,path,key,value in mutations:
            after=copy.deepcopy(before);after[group][path][key]=value
            with self.subTest(key=key),self.assertRaises(delivery.Refusal):delivery.preservation(before,after)
    def test_only_exact_declared_ingress_change_is_accepted(self):
        host=FakeHost()
        with host.hold():before=host.snapshot()
        after=copy.deepcopy(before);after['configuration'][delivery.normal.INGRESS]=host.ingress
        self.assertTrue(delivery.preservation(before,after,ingress=host.ingress))
        after['configuration']['/etc/systemd/system/voiceassistmain-product.service']['inode']+=1
        with self.assertRaises(delivery.Refusal):delivery.preservation(before,after,ingress=host.ingress)
    def test_source_metadata_covers_actual_finite_forward_literals(self):
        functions,triggers=delivery.migration_sql_metadata()
        self.assertEqual((len(functions),len(triggers)),(13,11))
        self.assertEqual(functions['quillmd_delivery_actor']['arguments'],'actor uuid, department uuid')
        self.assertEqual(functions['quillmd_delivery_exposure']['language'],'sql')
        self.assertEqual(triggers['core_templateversion:prepared_version_guard']['type'],7)
        self.assertFalse(any('@CAMPAIGN@' in value['body'] for value in functions.values()))
        self.assertIn(delivery.CAMPAIGN,functions['quillmd_delivery_config']['body'])
    def test_old_rows_permissions_and_unrelated_schema_are_preserved(self):
        before,after=populations();self.assertTrue(delivery.projected_population(before,after))
        for mutation in ('rows','metadata','owner','function','table','reference'):
            changed=copy.deepcopy(after)
            if mutation=='rows':changed['tables']['core_templateversion']['old_rows']='9'*64
            elif mutation=='metadata':changed['added_permissions'].append(('templateversion','delete_templateversion'))
            elif mutation=='owner':changed['tables']['core_templateversion']['owner_acl']=[['other',None,False,False]]
            elif mutation=='function':changed['schema']['functions']['unexpected']={}
            elif mutation=='table':changed['tables']['unexpected']={'rows':0}
            else:changed['referenced_files']={}
            with self.subTest(mutation=mutation),self.assertRaises(delivery.Refusal):delivery.projected_population(before,changed)
    def test_counterexamples_disabled_wrong_event_and_function_search_path_refuse(self):
        before,after=populations()
        for key,value in (('enabled','D'),('type',9),('function','unexpected'),('when','false')):
            changed=copy.deepcopy(after)
            changed['schema']['triggers']['core_templateversion:prepared_version_guard'][key]=value
            with self.subTest(key=key),self.assertRaisesRegex(delivery.Refusal,'new_trigger_source_or_enabled_state'):
                delivery.projected_population(before,changed)
    def test_new_schema_column_shape_owner_privileges_and_rls_refuse(self):
        before,after=populations()
        for mutation in ('missing_column','wrong_type','owner','public_dml','rls','old_added_type'):
            changed=copy.deepcopy(after);table=changed['tables']['core_templatepreparation']
            if mutation=='missing_column':table['definitions']=table['definitions'][:1]
            elif mutation=='wrong_type':table['definitions'][2][1]='text'
            elif mutation=='owner':table['owner_acl'][0][0]='unrelated_owner'
            elif mutation=='public_dml':table['privileges']=[['quillmd_owner','PUBLIC','INSERT',False]]
            elif mutation=='rls':table['owner_acl'][0][2]=True
            else:changed['tables']['core_templateversion']['definitions'][-1][1]='text'
            with self.subTest(mutation=mutation),self.assertRaises(delivery.Refusal):delivery.projected_population(before,changed)
    def test_only_recorded_bounded_metadata_sequence_consumption_can_survive_rollback(self):
        before,_=populations()
        before['schema']['sequences'].update({name:[[100,True]] for name in
            ('django_migrations_id_seq','django_content_type_id_seq','auth_permission_id_seq')})
        after=copy.deepcopy(before)
        limits={'django_migrations_id_seq':5,'django_content_type_id_seq':2,'auth_permission_id_seq':8}
        for name,maximum in limits.items():after['schema']['sequences'][name][0][0]+=maximum
        with self.assertRaises(delivery.Refusal):delivery.original_population(before,after)
        proof=delivery.original_population(before,after,allow_metadata_consumption=True)
        self.assertEqual({name:row['consumed'] for name,row in proof['retained_metadata_sequence_consumption'].items()},limits)
        for name in (*limits,'core_template_id_seq'):
            changed=copy.deepcopy(after);changed['schema']['sequences'][name][0][0]+=1
            with self.subTest(name=name),self.assertRaises(delivery.Refusal):delivery.original_population(before,changed,allow_metadata_consumption=True)
        before,after=populations()
        for key,value in (('configuration','{search_path=attacker,public}'),('acl','{public=X/quillmd_owner}'),
            ('language','sql'),('arguments','other text'),('returns','text'),('security_definer',True)):
            changed=copy.deepcopy(after);changed['schema']['functions']['quillmd_prepared_version_guard'][key]=value
            with self.subTest(key=key),self.assertRaisesRegex(delivery.Refusal,'new_function_source_or_security'):
                delivery.projected_population(before,changed)
    def test_required_new_constraints_and_index_contract_reject_missing_or_changed_metadata(self):
        before,after=populations()
        for kind in ('constraints','indexes'):
            for mutation in ('missing','definition','state','extra'):
                changed=copy.deepcopy(after);items=changed['schema'][kind];name=next(iter(items))
                if mutation=='missing':del items[name]
                elif mutation=='definition':items[name]['definition']='CHECK (true)' if kind=='constraints' else 'CREATE INDEX unrelated'
                elif mutation=='state':items[name]['validated' if kind=='constraints' else 'valid']=False
                else:items['core_templatepreparation:unexpected']={}
                with self.subTest(kind=kind,mutation=mutation),self.assertRaises(delivery.Refusal):delivery.projected_population(before,changed)
    def test_success_requires_exact_metadata_sequence_consumption(self):
        before,after=populations();self.assertTrue(delivery.projected_population(before,after))
        for name in ('django_migrations_id_seq','django_content_type_id_seq','auth_permission_id_seq'):
            for value in (1,100,1000000100):
                changed=copy.deepcopy(after);changed['schema']['sequences'][name][0][0]=value
                with self.subTest(name=name,value=value),self.assertRaises(delivery.Refusal):delivery.projected_population(before,changed)
        empty_before=copy.deepcopy(before);empty_after=copy.deepcopy(after)
        for name,count in (('django_migrations_id_seq',5),('django_content_type_id_seq',2),('auth_permission_id_seq',8)):
            empty_before['schema']['sequences'][name]=[[1,False]]
            empty_after['schema']['sequences'][name]=[[count,True]]
        self.assertTrue(delivery.projected_population(empty_before,empty_after))
        for name in ('django_migrations_id_seq','django_content_type_id_seq','auth_permission_id_seq'):
            changed=copy.deepcopy(empty_after);changed['schema']['sequences'][name][0][1]=False
            with self.subTest(name=name),self.assertRaises(delivery.Refusal):delivery.projected_population(empty_before,changed)
        rollback=copy.deepcopy(empty_before);rollback['schema']['sequences']['django_migrations_id_seq']=[[2,False]]
        with self.assertRaises(delivery.Refusal):delivery.original_population(empty_before,rollback,allow_metadata_consumption=True)
    def test_native_pending_jobs_reservations_preparation_and_unknown_receipts_refuse(self):
        host=delivery.NativeHost.__new__(delivery.NativeHost)
        for target in ('core_job','core_reservation','core_templatepreparation','core_preparationreceipt'):
            def query(statement):
                if statement.startswith('SELECT tablename'):return [('core_templatepreparation',),('core_preparationreceipt',)]
                return [(1 if ('FROM '+target+' ') in statement else 0,)]
            with self.subTest(target=target),self.assertRaises(delivery.Refusal):host._pending(query)


class OperationTests(unittest.TestCase):
    def test_success_orders_backup_schema_static_readiness_before_ingress(self):
        host=FakeHost();result=delivery.execute(plan(),host)
        self.assertTrue(result['complete']);self.assertFalse(result['authenticated_https_workflows_verified'])
        self.assertEqual(result['provider_calls'],0)
        for first,second in (('backup','forward'),('static_stage','forward'),('forward','static_install'),('static_install','readiness'),('readiness','ingress')):
            self.assertLess(host.events.index(first),host.events.index(second))
        self.assertFalse(any('voiceassist' in event and event.startswith(('start:','stop:')) for event in host.events))
        self.assertFalse(result['original_baselines_replaced'])
    def test_before_drain_refusal_has_no_service_actions(self):
        for phase in ('check_plan','native_admission','space_admitted'):
            host=FakeHost(phase)
            with self.subTest(phase=phase),self.assertRaises(delivery.Refusal):delivery.execute(plan(),host)
            self.assertFalse(any(event.startswith(('stop:','start:')) for event in host.events))
    def test_failed_preparation_recovers_original_without_migration(self):
        host=FakeHost('static_stage')
        with self.assertRaises(delivery.Refusal):delivery.execute(plan(),host)
        self.assertTrue(host.recovered);self.assertEqual(host.source,delivery.BASE)
        self.assertNotIn('forward',host.events);self.assertIn('first-failure',host.records)
    def test_ff_then_observed_full_rollback_completes_only_unapplied_schema(self):
        host=FakeHost('ff_then_rollback')
        with self.assertRaises(delivery.Refusal):delivery.execute(plan(),host)
        self.assertEqual(host.reconciled,1);self.assertTrue(host.recovered)
        self.assertEqual(host.records['first-failure']['reason'],'word_delivery_injected_commit_result')
        self.assertNotIn('forward_reconciliation',host.records['first-failure'])
        self.assertTrue(host.records['failed']['forward_reconciliation']['complete'])
        self.assertTrue(host.records['failed']['recovery']['feature_campaign_normal_origin_off'])
    def test_unknown_but_complete_commit_is_observed_without_resending(self):
        host=FakeHost('unknown_complete_commit')
        with self.assertRaises(delivery.Refusal):delivery.execute(plan(),host)
        self.assertEqual(host.reconciled,0);self.assertTrue(host.recovered)
        self.assertEqual(host.events.count('forward'),1)
    def test_partial_schema_never_starts_or_replays(self):
        host=FakeHost('partial_schema')
        with self.assertRaises(delivery.Refusal):delivery.execute(plan(),host)
        self.assertFalse(host.recovered);self.assertEqual(host.reconciled,0)
        self.assertFalse(any(event.startswith('start:') for event in host.events))
        self.assertFalse(host.records['failed']['recovery']['complete'])
    def test_foreign_change_prevents_publication_and_is_not_approved(self):
        host=FakeHost('foreign_inode')
        with self.assertRaises(delivery.Refusal):delivery.execute(plan(),host)
        self.assertNotIn('ingress',host.events)
        self.assertFalse(host.records['failed']['historical_deployment_approval_verified'])
    def test_storage_failure_after_schema_recovers_feature_off(self):
        host=FakeHost('space_forward_schema_verified')
        with self.assertRaises(delivery.Refusal):delivery.execute(plan(),host)
        self.assertTrue(host.recovered);self.assertNotIn('ingress',host.events)
        self.assertEqual(host.source,CANDIDATE)


class StaticTests(unittest.TestCase):
    def fixture(self,temporary):
        host=delivery.NativeHost.__new__(delivery.NativeHost)
        source=Path(temporary)/'source';source.mkdir(mode=0o755)
        stage=Path(temporary)/'stage';stage.mkdir(mode=0o755)
        inputs={}
        for name in delivery.STATIC_INPUTS:
            path=source/name;path.parent.mkdir(parents=True,exist_ok=True)
            content=(b'@font-face{src:url(fonts/dm-sans.ttf)}' if name=='app.css' else
                b'//# sourceMappingURL=docx-preview.min.js.map' if name=='vendor/docx-preview/docx-preview.min.js' else name.encode())
            path.write_bytes(content);path.chmod(0o644);inputs[name]=path
        host.static_sources=lambda:inputs
        host.plan={'static_source_sha256':{name:delivery.sha(path.read_bytes()) for name,path in inputs.items()}}
        expected=host.static_expected(inputs);manifest={}
        for name,path in inputs.items():
            original=PurePosixPath(name);compiled=str(original.with_suffix(''))+'.'+hashlib.md5(expected[name]).hexdigest()[:12]+original.suffix
            for filename,content in ((name,path.read_bytes()),(compiled,expected[name])):
                target=stage/filename;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(content);target.chmod(0o644)
            manifest[name]=compiled
        document={'paths':manifest,'version':'1.1','hash':hashlib.md5(json.dumps(sorted(manifest.items())).encode()).hexdigest()[:12]}
        (stage/'staticfiles.json').write_text(json.dumps(document));(stage/'staticfiles.json').chmod(0o644)
        for root in (source,stage):
            for directory in [root,*[path for path in root.rglob('*') if path.is_dir()]]:directory.chmod(0o755)
        return host,stage,document
    def test_finite_static_manifest_and_exact_source_rewrites(self):
        with tempfile.TemporaryDirectory() as directory:
            host,stage,manifest=self.fixture(directory)
            self.assertIn('staticfiles.json',host.validate_static(stage))
            compiled=stage/manifest['paths']['docx-frame.js'];compiled.write_bytes(b'changed');compiled.chmod(0o644)
            with self.assertRaisesRegex(delivery.Refusal,'static_compilation_bytes'):host.validate_static(stage)
    def test_extra_asset_and_missing_manifest_entry_refuse(self):
        with tempfile.TemporaryDirectory() as directory:
            host,stage,manifest=self.fixture(directory)
            (stage/'unexpected.js').write_bytes(b'new');(stage/'unexpected.js').chmod(0o644)
            with self.assertRaisesRegex(delivery.Refusal,'undeclared_static_output'):host.validate_static(stage)
            (stage/'unexpected.js').unlink();del manifest['paths']['docx-frame.css']
            (stage/'staticfiles.json').write_text(json.dumps(manifest))
            with self.assertRaisesRegex(delivery.Refusal,'finite_static_manifest'):host.validate_static(stage)
    def test_candidate_recovery_completes_candidate_manifest_and_base_restores_old(self):
        host=delivery.NativeHost.__new__(delivery.NativeHost);events=[]
        host.original=b'original';host.ingress_before=b'original-ingress';host.plan={'candidate':CANDIDATE}
        host.check_hold=lambda:None;host.configure=lambda recovery:events.append(('configure',recovery))
        host.install_static=lambda preparation,reconciling:events.append(('candidate-static',reconciling))
        host.restore_static=lambda preparation:events.append(('old-static',True))
        host.service=lambda action,unit:events.append((action,unit));host.readiness=lambda actual:{'release':actual}
        with patch.object(delivery.normal.NativeHost,'ingress',return_value=(b'original-ingress',{})),patch.object(delivery,'protected',return_value=b'original'):
            self.assertTrue(host.recover({'stage':'synthetic'},CANDIDATE)['complete'])
            self.assertIn(('candidate-static',True),events);self.assertNotIn(('old-static',True),events)
            events.clear();self.assertTrue(host.recover({'stage':'synthetic'},delivery.BASE)['complete'])
            self.assertIn(('old-static',True),events);self.assertFalse(any(event[0]=='candidate-static' for event in events))


if __name__=='__main__':unittest.main()
