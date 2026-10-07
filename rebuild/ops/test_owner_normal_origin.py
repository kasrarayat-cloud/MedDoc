"""Focused fictional controls; no installed state or provider/login action."""
import ast
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import io
import json
import os
import fcntl
from pathlib import Path
from types import SimpleNamespace
import tempfile
import time
import unittest
from unittest.mock import MagicMock, patch
from . import owner_normal_origin as act

PRIOR='a'*40
TARGET='b'*40
ORIGINAL=(b'original server {\n'+act.SHARED_NAMES+b'\n}\n')
TEMPLATE=b'fictional restricted app443 block\n'
ENV=(b'QUILLMD_RELEASE_SHA="'+PRIOR.encode()+b'"\nQUILLMD_APP_BASE_URL="https://app.quillmd.com:9443"\n'
     b'QUILLMD_PREVIEW_AUTH_ENABLED="1"\nPRIVATE_VALUE="fictional-preserved"\n')

def metadata(raw, inode=2):
    return {'uid':0,'gid':0,'mode':0o644,'device':1,'inode':inode,'sha256':act.sha(raw)}

def population():
    return {'database':{'tables':{'table-'+str(i):{'rows':i,'sha256':str(i)} for i in range(36)},
            'pending_jobs':0,'held':0,'catalog':{'ACL':'unchanged'},'invariants':{},'referenced_files':[]},
        'files':{'file-'+str(i):{'sha256':str(i)} for i in range(67)},'mail':{'synthetic':'unchanged'},
        'static':{'app':'unchanged'},'configuration':{act.INGRESS:metadata(ORIGINAL),
        act.PRIVATE_INGRESS:{'sha256':act.PRIVATE_INGRESS_SHA},str(act.ROOT/'Caddyfile'):{'sha256':act.CADDY_SHA},
        '/etc/systemd/system/voiceassistmain-product.service':{'sha256':'unchanged-foreign'}}}

class FictionalHost:
    def __init__(self):
        self.guard=population();self.events=[];self.revision=PRIOR;self.original_environment=ENV
        self.records={};self.raw=ORIGINAL;self.meta=metadata(ORIGINAL);self.rolling_back=False
        self.old=SimpleNamespace(UNITS=('doctor','admin','worker'),protected=lambda *a:self.environment,
            best_effort_private_stop=lambda _: {'only-own-three':True})
        self.native=object();self.environment=ENV
        self.env_writer=SimpleNamespace(replace_environment=self.replace_env)
        self.cipher=SimpleNamespace(encrypt=lambda raw:b'fictional-cipher:'+raw)
        self.preservation=MagicMock(return_value={'full_original_and_new_records_verified':True,'private_acceptance_sha256':'c'*64})
        self.full_preservation=self.preservation
        self.session_admission=MagicMock(side_effect=lambda minimum:{'remaining_seconds':1790,'required_remaining_seconds':minimum,
            'session_renewal_performed':False,'database_writes':0})
        self.routes=MagicMock(return_value={'https://app.quillmd.com':503})
    @contextmanager
    def hold(self):
        self.events.append('five-locks-held');yield;self.events.append('five-locks-released')
    def check(self,*a): pass
    def check_hold(self): pass
    def forward_budget(self):self.events.append('bounded-forward-budget')
    def git(self,tree,*args):
        if args[:2]==('rev-parse','HEAD'):return (self.revision+'\n').encode()
        if args[:2]==('branch','--show-current'):return b'main\n'
        if args[0]=='status':return b''
        raise AssertionError(args)
    def snapshot(self):return deepcopy(self.guard)
    def foreign(self):return {'exact-seven':'unchanged'}
    def ingress(self):return self.raw,dict(self.meta)
    def boundary(self,release):return {'source':release,'invocations':'fictional-measured'}
    def service(self,action,unit):self.events.append(action+':'+unit)
    def forward(self,target):self.events.append('fast-forward');self.revision=target
    def replace_env(self,path,before,after):
        assert self.environment==before;self.environment=after;self.events.append('environment')
    def replace_ingress(self,before,after,meta):
        assert self.raw==before and self.meta==meta
        self.events.append('only-quillmd-ingress');self.raw=after;self.meta=metadata(after,self.meta['inode']+1)
        self.guard['configuration'][act.INGRESS]=dict(self.meta);return dict(self.meta)
    def write(self,name,value):
        assert name not in self.records;self.records[name]=value

class NormalOriginOperatorTests(unittest.TestCase):
    def fixture(self,root):
        output=root/'output';attempt=root/'attempt'
        scope=SimpleNamespace(output=output,attempt=attempt)
        host=FictionalHost();policy={'private_accepted_revision':PRIOR,'original_ingress_metadata':metadata(ORIGINAL),
                                    'private_acceptance':{'sha256':'c'*64}}
        return scope,host,policy
    def run_transition(self,root,host,policy,execute):
        with patch.object(act,'OUTPUT',root/'output'),patch.object(act,'ATTEMPT',root/'attempt'), \
             patch.object(act,'OLD_INGRESS_SHA',act.sha(ORIGINAL)):
            return act.transition(host,policy,TARGET,{act.TEMPLATE:TEMPLATE},execute=execute)
    @patch.multiple(act,ACTIVE_PROTOCOL_QUALIFIED=False,PRIVATE_ACCEPTANCE_PROTOCOL_QUALIFIED=False,
                    INGRESS_PUBLICATION_QUALIFIED=False)
    def test_default_and_unqualified_execute_never_read_or_act(self):
        with patch.object(act.source_files,'protected',side_effect=AssertionError('installed read')), \
             patch.object(act.old,'git',side_effect=AssertionError('Git read')),patch('sys.stdout',new=io.StringIO()):
            self.assertEqual(act.main([]),0)
            for mode in ('--execute','--preflight'):
                with self.assertRaisesRegex(act.Refusal,'source_protocol_unqualified'):
                    act.main([mode,'--operations-revision',TARGET])
        self.assertFalse(act.ACTIVE_PROTOCOL_QUALIFIED);self.assertFalse(act.PRIVATE_ACCEPTANCE_PROTOCOL_QUALIFIED)
        self.assertFalse(act.INGRESS_PUBLICATION_QUALIFIED)
    @patch.multiple(act,ACTIVE_PROTOCOL_QUALIFIED=True,PRIVATE_ACCEPTANCE_PROTOCOL_QUALIFIED=True,
                    INGRESS_PUBLICATION_QUALIFIED=True)
    def test_qualified_default_is_read_only_and_does_not_claim_campaign_completion(self):
        with patch.object(act.source_files,'protected',side_effect=AssertionError('installed read')), \
             patch.object(act.old,'git',side_effect=AssertionError('Git read')), \
             patch.object(act,'NativeHost',side_effect=AssertionError('native adapter')), \
             patch('sys.stdout',new=io.StringIO()) as stream:
            self.assertEqual(act.main([]),0)
        result=json.loads(stream.getvalue())
        self.assertTrue(all(result[name] for name in ('active_protocol_qualified',
            'private_acceptance_protocol_qualified','ingress_publication_qualified')))
        self.assertFalse(result['private_acceptance_completed']);self.assertFalse(result['installed_state_accessed'])
        self.assertFalse(result['execution_performed'])
        self.assertEqual((result['provider_calls'],result['authentication_submissions'],result['database_writes']),(0,0,0))
    def test_each_source_qualification_is_required_independently_of_policy_or_environment(self):
        names=('ACTIVE_PROTOCOL_QUALIFIED','PRIVATE_ACCEPTANCE_PROTOCOL_QUALIFIED','INGRESS_PUBLICATION_QUALIFIED')
        for name in names:
            values=dict.fromkeys(names,True);values[name]=False
            with self.subTest(name=name),patch.multiple(act,**values),patch.dict(os.environ,{name:'1'}), \
                 patch.object(act.source_files,'protected',side_effect=AssertionError('installed read')), \
                 patch.object(act.old,'git',side_effect=AssertionError('Git read')):
                self.assertFalse(act.qualified())
                with self.assertRaisesRegex(act.Refusal,'source_protocol_unqualified'):act.source_gate(TARGET)
                with self.assertRaisesRegex(act.Refusal,'source_protocol_unqualified'):
                    act.NativeHost({'active_protocol_qualified':True,'private_acceptance_protocol_qualified':True,
                                    'ingress_publication_qualified':True},TARGET,{},0)
    def test_main_passes_the_checked_buffers_not_a_template_tuple(self):
        host=object();buffers={act.TEMPLATE:TEMPLATE};policy={}
        with patch.object(act,'source_gate',return_value=(policy,buffers)), \
             patch.object(act,'transition',return_value={'complete':True}) as transition,patch('sys.stdout',new=io.StringIO()):
            act.main(['--preflight','--operations-revision',TARGET],host=host)
        transition.assert_called_once_with(host,policy,TARGET,buffers,execute=False)
    def test_render_changes_only_the_app_server_name_and_appended_block(self):
        with patch.object(act,'OLD_INGRESS_SHA',act.sha(ORIGINAL)):
            rendered=act.render_ingress(ORIGINAL,TEMPLATE)
            self.assertEqual(rendered,ORIGINAL.replace(act.SHARED_NAMES,act.RESTRICTED_NAMES)+b'\n'+TEMPLATE)
            for bad in (ORIGINAL+b'foreign change',b'wrong',ORIGINAL.replace(act.SHARED_NAMES,b'none')):
                with self.assertRaises(act.Refusal):act.render_ingress(bad,TEMPLATE)
            for bad in (b'',b'\0',b'x'*16385):
                with self.assertRaises(act.Refusal):act.render_ingress(ORIGINAL,bad)
    def test_preflight_reverifies_original_and_added_population_without_output_or_act(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);_,host,policy=self.fixture(root)
            result=self.run_transition(root,host,policy,False)
            self.assertTrue(result['complete']);self.assertFalse(result['execution_performed'])
            host.preservation.assert_called_once()
            self.assertEqual(host.events,['five-locks-held','five-locks-released'])
            self.assertFalse((root/'output').exists());self.assertFalse(host.records)
    def test_population_drift_during_full_proof_cannot_be_recaptured_as_guard(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);_,host,policy=self.fixture(root)
            def completed_then_drifted():
                host.guard['database']['tables']['table-0']['sha256']='unexpected old-row drift'
                return {'complete_original_and_new_report':True}
            host.full_preservation=completed_then_drifted
            with self.assertRaisesRegex(act.Refusal,'guard_database'):
                self.run_transition(root,host,policy,True)
            self.assertEqual(host.events,['five-locks-held']);self.assertFalse(host.records)
            self.assertFalse((root/'output').exists())
    def test_live_session_ttl_refusal_never_renews_or_stops_services(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);_,host,policy=self.fixture(root)
            host.session_admission.side_effect=act.Refusal('normal443_existing_session_remaining_ttl')
            with self.assertRaisesRegex(act.Refusal,'remaining_ttl'):self.run_transition(root,host,policy,True)
            host.preservation.assert_called_once();self.assertFalse(host.records);self.assertFalse((root/'output').exists())
            self.assertEqual(host.events,['five-locks-held'])
    def test_ttl_recheck_before_marker_records_precise_failure_without_any_mutation(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);_,host,policy=self.fixture(root)
            host.session_admission.side_effect=[{'remaining_seconds':700},act.Refusal('normal443_existing_session_remaining_ttl')]
            with self.assertRaisesRegex(act.Refusal,'preparation_failed'):self.run_transition(root,host,policy,True)
            self.assertNotIn('attempt',host.records);self.assertEqual(host.revision,PRIOR);self.assertEqual(host.environment,ENV)
            self.assertEqual(host.records['failed.json']['failure_reason'],'normal443_existing_session_remaining_ttl')
            self.assertEqual(host.records['failed.json']['service_actions'],0)
    def test_execute_is_one_forward_transition_of_own_services_then_one_file(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);_,host,policy=self.fixture(root)
            result=self.run_transition(root,host,policy,True)
            self.assertTrue(result['complete']);self.assertEqual(result['served_revision'],TARGET)
            self.assertEqual(host.events[2:5],['stop:worker','stop:admin','stop:doctor'])
            self.assertLess(host.events.index('fast-forward'),host.events.index('start:doctor'))
            self.assertLess(host.events.index('start:worker'),host.events.index('only-quillmd-ingress'))
            self.assertEqual(host.events.count('fast-forward'),1)
            self.assertEqual(set(host.records),{'environment-before.fernet','environment-enabled.fernet','environment-disabled.fernet',
                'original-ingress.conf','prepared.json','live-sessions-before.json','attempt','complete.json'})
            self.assertTrue(host.records['complete.json']['full_original_and_new_acceptance_population_preserved'])
            self.assertFalse(host.records['complete.json']['actual_provider_model_reverified_by_this_transition'])
            with self.assertRaisesRegex(act.Refusal,'single_consumable_attempt'):
                self.run_transition(root,host,policy,True)
    def test_failure_restores_ingress_and_private_access_with_disabled_flag_without_source_reset(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);_,host,policy=self.fixture(root)
            host.routes.side_effect=act.Refusal('fictional-http-failure')
            with self.assertRaisesRegex(act.Refusal,'failed_with_preserved_evidence'):
                self.run_transition(root,host,policy,True)
            failure=host.records['failed.json'];rollback=failure['rollback']
            self.assertTrue(rollback['complete']);self.assertTrue(rollback['private_availability_preserved'])
            self.assertFalse(rollback['source_reset']);self.assertEqual(host.revision,TARGET)
            self.assertEqual(host.raw,ORIGINAL);self.assertIn(b'QUILLMD_OWNER_NORMAL_ORIGIN_ENABLED="0"',host.environment)
            self.assertEqual(host.events.count('fast-forward'),1)
            self.assertNotIn('complete.json',host.records)
    def test_premarker_failure_never_stops_services_or_changes_environment_or_ingress(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);_,host,policy=self.fixture(root)
            original_write=host.write
            def fail_prepared(name,value):
                if name=='prepared.json':raise OSError('fictional evidence volume refusal')
                original_write(name,value)
            host.write=fail_prepared
            with self.assertRaisesRegex(act.Refusal,'preparation_failed_preserving_availability'):
                self.run_transition(root,host,policy,True)
            self.assertEqual(host.revision,PRIOR);self.assertEqual(host.environment,ENV);self.assertEqual(host.raw,ORIGINAL)
            self.assertEqual(host.events,['five-locks-held'])
            self.assertNotIn('attempt',host.records)
            self.assertFalse(host.records['failed.json']['mutation_started'])
            self.assertEqual(host.records['failed.json']['service_actions'],0)
    def test_partial_ingress_helper_failure_is_detected_and_restored_by_current_bytes(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);_,host,policy=self.fixture(root)
            replace=host.replace_ingress
            def interrupted(before,after,meta):
                result=replace(before,after,meta)
                if after != ORIGINAL:raise OSError('fictional nginx test refusal after atomic replace')
                return result
            host.replace_ingress=interrupted
            with self.assertRaisesRegex(act.Refusal,'failed_with_preserved_evidence'):
                self.run_transition(root,host,policy,True)
            self.assertEqual(host.raw,ORIGINAL);self.assertEqual(host.revision,TARGET)
            self.assertTrue(host.records['failed.json']['rollback']['private_availability_preserved'])
            self.assertFalse(host.records['failed.json']['ingress_helper_completed_before_failure'])
            self.assertEqual(host.records['failed.json']['rollback']['ingress_observed_before_rollback']['sha256'],
                             act.sha(ORIGINAL.replace(act.SHARED_NAMES,act.RESTRICTED_NAMES)+b'\n'+TEMPLATE))
            self.assertEqual(host.events.count('only-quillmd-ingress'),2)
    def test_completed_forward_with_failed_return_uses_measured_target_for_private_rollback(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);_,host,policy=self.fixture(root)
            forward=host.forward
            def failed_return(target):
                forward(target)
                raise act.Refusal('fictional post-merge read-through refusal')
            host.forward=failed_return
            def strict_boundary(release):
                self.assertEqual(host.revision,release)
                self.assertIn(('QUILLMD_RELEASE_SHA="'+release+'"').encode(),host.environment)
                return {'source':release,'invocations':'fictional-measured'}
            host.boundary=strict_boundary
            with self.assertRaisesRegex(act.Refusal,'failed_with_preserved_evidence'):
                self.run_transition(root,host,policy,True)
            rollback=host.records['failed.json']['rollback']
            self.assertTrue(rollback['complete']);self.assertTrue(rollback['private_availability_preserved'])
            self.assertEqual(rollback['served_revision'],TARGET);self.assertEqual(host.revision,TARGET)
            self.assertIn(b'QUILLMD_OWNER_NORMAL_ORIGIN_ENABLED="0"',host.environment)
            self.assertEqual(host.events.count('fast-forward'),1)
    def test_every_current_guard_population_is_strict_including_old_and_new_records(self):
        before=population()
        for key in ('database','files','mail','static','configuration'):
            with self.subTest(key=key):
                after=deepcopy(before);after[key]['unexpected']='unapproved'
                with self.assertRaises(act.Refusal):act.compare_guard(before,after)
        after=deepcopy(before);after['database']['pending_jobs']=1
        with self.assertRaises(act.Refusal):act.compare_guard(before,after)
        after=deepcopy(before);after['configuration'][act.INGRESS]=metadata(TEMPLATE,3)
        self.assertTrue(act.compare_guard(before,after,ingress=metadata(TEMPLATE,3)))
        after['configuration']['foreign']='changed'
        with self.assertRaises(act.Refusal):act.compare_guard(before,after,ingress=metadata(TEMPLATE,3))
    def test_environment_changes_only_release_and_explicit_flag_preserving_private_origin(self):
        for enabled in (False,True):
            updated=act.controlled_environment(ENV,PRIOR,TARGET,enabled=enabled)
            self.assertIn(b'PRIVATE_VALUE="fictional-preserved"',updated)
            self.assertIn(b'QUILLMD_APP_BASE_URL="https://app.quillmd.com:9443"',updated)
            self.assertEqual(updated.count(b'QUILLMD_RELEASE_SHA='),1)
            self.assertEqual(updated.count(b'QUILLMD_OWNER_NORMAL_ORIGIN_ENABLED='),1)
            self.assertIn(('QUILLMD_OWNER_NORMAL_ORIGIN_ENABLED="'+('1' if enabled else '0')+'"').encode(),updated)
        for raw in (ENV+b'QUILLMD_RELEASE_SHA="wrong"\n',ENV+b'QUILLMD_OWNER_NORMAL_ORIGIN_ENABLED="0"\nQUILLMD_OWNER_NORMAL_ORIGIN_ENABLED="1"\n'):
            with self.assertRaises(act.Refusal):act.controlled_environment(raw,PRIOR,TARGET,enabled=True)
        with self.assertRaises(act.Refusal):act.controlled_environment(ENV,PRIOR,'bad',enabled=True)
    def test_private_inputs_require_exact_paths_hashes_and_original_acceptance_scope(self):
        with patch.object(act.source_files,'protected',side_effect=AssertionError('private read')):
            for item in (None,{'path':'/tmp/elsewhere','sha256':'f'*64},{'path':str(act.PRIVATE_PATHS['private_acceptance']),'sha256':None}):
                with self.assertRaises(act.Refusal):act.pinned_receipt(item,'pin',act.PRIVATE_PATHS['private_acceptance'])
    @patch.multiple(act,ACTIVE_PROTOCOL_QUALIFIED=False,PRIVATE_ACCEPTANCE_PROTOCOL_QUALIFIED=False,
                    INGRESS_PUBLICATION_QUALIFIED=False)
    def test_native_constructor_cannot_be_opened_by_a_policy_flag(self):
        with patch.object(act,'private_receipts',side_effect=AssertionError('private input')):
            with self.assertRaisesRegex(act.Refusal,'source_protocol_unqualified'):
                act.NativeHost({'active_protocol_qualified':True},TARGET,{},0)
    @patch.object(act,'SOURCE',Path('/opt/meddoc-pro/.worktrees/fictional-normal443'))
    @patch.multiple(act.os,getuid=lambda:1000,geteuid=lambda:1000,getgid=lambda:1000,getegid=lambda:1000)
    def test_source_gate_authenticates_each_dependency_and_exact_intermediate_operations_scope(self):
        policy={'private_accepted_revision':PRIOR,**{key:True for key in (
            'active_protocol_qualified','private_acceptance_protocol_qualified','ingress_publication_qualified')}}
        def run(bad=None):
            def raw(relative):
                if relative=='rebuild/core/preview_access.py':return b'OWNER_NORMAL_ORIGIN_PROTOCOL_QUALIFIED=True\n'
                if relative=='rebuild/quillmd/settings.py':return b"QUILLMD_OWNER_NORMAL_ORIGIN_ENABLED=os.getenv('QUILLMD_OWNER_NORMAL_ORIGIN_ENABLED','0')=='1'\n"
                return relative.encode()
            def git(tree,*args):
                if args[0]=='rev-parse':return (TARGET+'\n').encode()
                if args[0]=='status' or args[0]=='merge-base':return b''
                if args[0]=='diff':
                    paths=set(act.ALLOWED if args[2]==act.BASE else act.PRIVATE_OPS)
                    if bad=='intermediate' and args[2]==PRIOR:paths.add('rebuild/core/views.py')
                    return ('\n'.join(sorted(paths))+'\n').encode()
                if args[0]=='ls-files':return ('100644 '+'a'*40+' 0 '+args[-1]+'\n').encode()
                if args[0]=='log':return (TARGET+'\n').encode()
                if args[0]=='show':
                    revision,relative=args[1].split(':',1)
                    if bad=='dependency' and revision==act.BASE and relative==act.NATIVE[0]:return b'unapproved dependency'
                    return raw(relative)
                raise AssertionError(args)
            with patch.object(act,'qualified',return_value=True),patch.object(act.old,'git',side_effect=git), \
                 patch.object(act.source_files,'open_root') as opened, \
                 patch.object(act.source_files,'operator_bytes',side_effect=lambda relative,*_:raw(relative)), \
                 patch.object(act,'contract',return_value=policy),patch.object(act.source_files,'sealed_citation') as citation, \
                 patch.dict(os.environ,{'RULED_MUTATION_DECLARATION':act.DECL,'RULED_MUTATION_DECL_COMMIT':TARGET,
                                       'RULED_ACT_MAX_SECS':str(act.OUTER_SECONDS)}):
                opened.return_value.__enter__.return_value=42
                result,buffers=act.source_gate(TARGET)
                self.assertIs(result,policy)
                self.assertTrue(set(act.NATIVE).issubset(buffers));self.assertIn(act.ACCEPTANCE,buffers)
                self.assertEqual({call.args[-1] for call in citation.call_args_list},{act.BASE,TARGET,PRIOR})
        run()
        for bad,label in (('dependency','unchanged_operational_dependency'),('intermediate','intermediate_four_operational_paths')):
            with self.subTest(bad=bad),self.assertRaisesRegex(act.Refusal,label):run(bad)
    def test_source_gate_requires_exact_native_identity_before_git_access(self):
        with patch.object(act,'qualified',return_value=True), \
             patch.object(act,'SOURCE',Path('/opt/meddoc-pro/.worktrees/fictional-normal443')), \
             patch.multiple(act.os,getuid=lambda:1000,geteuid=lambda:1000,getgid=lambda:1000,getegid=lambda:1000), \
             patch.object(act.old,'git',side_effect=AssertionError('Git access before identity admission')) as git:
            for name in ('getuid','geteuid','getgid','getegid'):
                with self.subTest(identity=name),patch.object(act.os,name,return_value=1001), \
                     self.assertRaisesRegex(act.Refusal,'operations_identity'):
                    act.source_gate(TARGET)
            with patch.object(act,'SOURCE',Path('/home/runner/work/quillmd/quillmd')), \
                 self.assertRaisesRegex(act.Refusal,'operations_identity'):
                act.source_gate(TARGET)
            git.assert_not_called()
    def test_qualified_source_requires_the_app_gate_and_exact_default_disabled_setting(self):
        preview=b'OWNER_NORMAL_ORIGIN_PROTOCOL_QUALIFIED=True\n'
        setting=b"QUILLMD_OWNER_NORMAL_ORIGIN_ENABLED=os.getenv('QUILLMD_OWNER_NORMAL_ORIGIN_ENABLED','0')=='1'\n"
        self.assertTrue(act.application_gate(preview,setting))
        for bad in (preview.replace(b'True',b'False'),preview+preview,b''):
            with self.assertRaisesRegex(act.Refusal,'checked_application_qualified'):act.application_gate(bad,setting)
        with self.assertRaisesRegex(act.Refusal,'default_disabled_explicit_setting'):
            act.application_gate(preview,setting.replace(b"'0'",b"'1'"))
    def test_full_preservation_binds_current_publisher_to_adapter_and_reports_new_health_admission(self):
        import types
        host=object.__new__(act.NativeHost);host.served=PRIOR;host.check_hold=MagicMock()
        host.check_private_inputs=MagicMock()
        health={'id':b'fictional-uuid','created_at':b'original','key':b'backup'}
        original={str(i):{} for i in range(35)}
        original['core_servicehealth']={'columns':list(health),'rows':[b'fictional COPY row']}
        full={'id':'fictional-uuid','all_eleven_fields':'source-verified-fictional'}
        host.verifier=SimpleNamespace(original_continuation_capture=lambda *_:(None,None,{'tables':{'django_session':{'rows':212}}},original),
            row_mapping=lambda *_:{'fictional-uuid':dict(health)},service_health_original=lambda _:full)
        host.publisher_admission=MagicMock(return_value={'current_full_row':full})
        host.inputs={'private_acceptance':({},b'fictional qualified private completion')}
        host.current_private_completion=MagicMock();host.historical_policy={};host.authority={};host.common=object()
        host.backup=SimpleNamespace(source_options=lambda *_:{})
        host.old=SimpleNamespace(ROLES=())
        module=types.ModuleType('_fictional_checked_preservation')
        module.admitted_original_row=lambda original,*_:original
        def adapter(raw,common,authority,verifier,completion_check=None,*,publisher_admission):
            self.assertIs(publisher_admission,host.publisher_admission)
            self.assertIs(completion_check,host.current_private_completion)
            return module
        host.acceptance=SimpleNamespace(readonly_connection_flags=MagicMock(),protected=lambda _:b'fictional frozen raw',
            FROZEN=Path('/fictional-retained'),verifier_adapter=adapter,CAMPAIGN=Path('/fictional-campaign'))
        report={'complete':True,'provider_calls':0,'database_writes':0,'served_revision':PRIOR,
                'preservation':{'all_36_tables_all_old_rows_columns_compared':True,'new_health_publications_admitted':False}}
        connection=MagicMock();connection.__enter__.return_value=connection
        connection.cursor.return_value.copy.return_value.__enter__.return_value=[b'fictional current COPY row']
        with patch('psycopg.connect',return_value=connection),patch.object(act,'memory_verifier',return_value=(lambda _:deepcopy(report),{})):
            result=host.full_preservation()
        self.assertTrue(result['private_workflow_report']['preservation']['new_health_publications_admitted'])
        self.assertFalse(report['preservation']['new_health_publications_admitted'])
        self.assertFalse(result['original_capture_replaced']);host.publisher_admission.assert_called_once()
        self.assertEqual(host.check_private_inputs.call_count,2)


class ActualRetainedVerifierTests(unittest.TestCase):
    @unittest.skipUnless((act.EVIDENCE/'recovery-20261007/acceptance-v3-preparation-v2-20261007/verify_installed_acceptance_v3.py').exists(),
                         'Retained fixed source fixture is host-local, not a live verification')
    def test_authenticated_memory_sink_preserves_the_real_initial_gate(self):
        import types
        path=act.EVIDENCE/'recovery-20261007/acceptance-v3-preparation-v2-20261007/verify_installed_acceptance_v3.py'
        raw=act.source_files.protected(path)
        module=types.ModuleType('_fictional_normal443_memory_verifier')
        module.__file__=str(path);module.__dict__['__authenticated_source']=raw
        module.CAMPAIGN=str(act.EVIDENCE/'installed-acceptance-v3-20261007')
        def gate():raise act.Refusal('source_protocol_unqualified')
        module.v3_execution_gate=gate
        module.validate_admin_final_storage=lambda *_:(_ for _ in ()).throw(AssertionError('installed read'))
        module.validate_doctor_final_storage=module.validate_admin_final_storage
        module.protected=lambda *args:(_ for _ in ()).throw(AssertionError('installed read'))
        verify,namespace=act.memory_verifier(module)
        self.assertIs(namespace['v3_execution_gate'],gate)
        with self.assertRaisesRegex(act.Refusal,'source_protocol_unqualified'):
            verify(SimpleNamespace(progress='unused',output=None))
        self.assertEqual(act.sha(path.read_bytes()),act.FROZEN_V3)
        module.__dict__['__authenticated_source']=raw+b'\n# counterexample'
        with self.assertRaisesRegex(act.Refusal,'frozen_verifier_hash'):act.memory_verifier(module)
    @unittest.skipUnless((act.EVIDENCE/'recovery-20261007/acceptance-v3-preparation-v2-20261007/verify_installed_acceptance_v3.py').exists(),
                         'Retained fixed source fixture is host-local, not a live verification')
    def test_memory_adapter_preserves_current_final_storage_checks_before_database_access(self):
        import re,types
        path=act.EVIDENCE/'recovery-20261007/acceptance-v3-preparation-v2-20261007/verify_installed_acceptance_v3.py'
        raw=act.source_files.protected(path);module=types.ModuleType('_fictional_final_storage_memory_verifier')
        module.__file__=str(path);module.__dict__['__authenticated_source']=raw
        campaign=Path('/fictional-fixed-campaign');origin='https://app.quillmd.com:9443';calls=[]
        readback={'complete':True,'origin':origin,'normal_MFA_session_reused':True,'fresh_MFA_submissions':0,
            'auth_reset':False,'department_privacy_verified':True,'started_at':'2026-10-07T00:00:00+00:00',
            'finished_at':'2026-10-07T00:00:01+00:00','checks':[{'name':name,'width':width,'status':200,
                'no_page_overflow':True,'accessibility_violations':[]} for name in ('overview','services','organizations')
                for width in (1440,768,390)]}
        progress={'origin':origin,'browser_workflows_complete':True,'independent_readback_pending':True,'complete':False,
            'existing_records_edited':0,'admin_readback':readback,'release':PRIOR,'cases':[{'name':name} for name in
                ('soap-typed','custom-word-typed','soap-voice','allergy-missing','allergy-legitimate')],
            'started':'2026-10-07T00:00:00+00:00','finished':'2026-10-07T00:00:02+00:00',
            'doctor_final_storage_state':{}}
        def admin(p):calls.append('admin');return {'complete':True}
        def doctor(p):calls.append('doctor');raise act.Refusal('normal443_checked_final_doctor_proof_reached')
        module.__dict__.update(CAMPAIGN=str(campaign),ACCEPTANCE_CAMPAIGN=campaign,ORIGIN=origin,Path=Path,re=re,
            json=json,datetime=datetime,require=act.require,v3_execution_gate=lambda:None,
            protected=lambda _:act.encode(progress),validate_admin_final_storage=admin,validate_doctor_final_storage=doctor)
        verify,_=act.memory_verifier(module)
        with patch('psycopg.connect',side_effect=AssertionError('database connection')), \
             self.assertRaisesRegex(act.Refusal,'checked_final_doctor_proof_reached'):
            verify(SimpleNamespace(progress=str(campaign/'progress.json'),output=None))
        self.assertEqual(calls,['admin','doctor'])


class RuntimeReceiptAndSessionAdmissionTests(unittest.TestCase):
    def chain(self):
        policy={key:{'path':str(path),'binding':act.RUNTIME_BINDING} for key,path in act.PRIVATE_PATHS.items()}
        availability={'complete':True,'source':{'operator_commit':PRIOR}}
        avail_raw=act.encode(availability);policy['availability']={'path':str(act.PRIVATE_PATHS['availability']),'sha256':act.sha(avail_raw)}
        binding={'operations_revision':act.BASE,'served_revision':PRIOR,'availability_receipt_sha256':act.sha(avail_raw),
                 'parent_pid':999999,'parent_start_ticks':456,'preparation_directory':str(act.PRIVATE_PHASE.parent)}
        observation={'protocol':act.PRIVATE_PHASE_PROTOCOL,'binding':binding,'configuration':{'retained':'immutable'},
                     'external_boundary':{'metadata_ns':'1791410000000000001'}}
        phase_raw=act.encode(observation)
        phase_proof={'protocol':act.PRIVATE_PHASE_PROTOCOL,'phase_observation_path':str(act.PRIVATE_PHASE),
                     'phase_observation_sha256':act.sha(phase_raw),'phase_observation':observation}
        admissions={phase:{'format':3,'operations_revision':act.BASE,'served_revision':PRIOR,'phase':phase}
                    for phase in ('before-auth','after-auth')}
        for packet in admissions.values():packet['co_tenant_preservation_admission']=deepcopy(phase_proof)
        admission_paths={phase:act.EVIDENCE/'installed-acceptance-v3-preparation-20261007'/('admission-'+phase+'.json')
                         for phase in admissions}
        admission_items={phase:{'path':str(admission_paths[phase]),'sha256':act.sha(act.encode(packet))}
                         for phase,packet in admissions.items()}
        progress={'operations_revision':act.BASE,'served_revision':PRIOR,'activation_sha256':act.sha(avail_raw),
                  'browser_workflows_complete':True,'complete':False,'independent_readback_pending':True,
                  'admin_readback':{'complete':True},'preparation':admissions,
                  'doctor_final_storage_state':{'path':'fictional fixed state','sha256':'a'*64,'captured_at':'fictional capture'}}
        report={'complete':True,'operations_revision':act.BASE,'served_revision':PRIOR,'activation_sha256':act.sha(avail_raw),
                'co_tenant_preservation_admission':deepcopy(phase_proof),
                'provider_calls':0,'database_writes':0,'cases':[{'name':name} for name in (
                    'soap-typed','custom-word-typed','soap-voice','allergy-missing','allergy-legitimate')],
                'preservation':{'all_36_tables_all_old_rows_columns_compared':True,'all_67_old_referenced_files_preserved':True},
                'browser_progress_sha256':act.sha(act.encode(progress)),
                'admin_readback':{**progress['admin_readback'],'final_storage_state_verification':{'complete':True}},
                'doctor_final_storage_state':{**progress['doctor_final_storage_state'],'verification':{'complete':True}}}
        complete={'format':3,'complete':True,'operations_revision':act.BASE,'served_revision':PRIOR,
                  'phase_preservation_sha256':act.sha(phase_raw),'co_tenant_preservation_admission':deepcopy(phase_proof),
                  'independent_report':str(act.PRIVATE_PATHS['private_report']),
                  'independent_report_sha256':act.sha(act.encode(report)),'availability_preserved':True,'provider_retries':0}
        authority={'phase':'verify','operations_revision':act.BASE,'served_revision':PRIOR,
                   'parent_pid':binding['parent_pid'],'parent_start_ticks':binding['parent_start_ticks'],
                   'phase_preservation_sha256':act.sha(phase_raw),
                   'authority':{'operations_revision':act.BASE,'served_revision':PRIOR,
                       'phase_preservation':{'path':str(act.PRIVATE_PHASE),'sha256':act.sha(phase_raw),'binding':binding},
                       'availability_receipt_sha256':act.sha(avail_raw),'admissions':admission_items},
                   'admission_sha256':{phase:item['sha256'] for phase,item in admission_items.items()}}
        records={act.PRIVATE_PATHS['private_acceptance']:act.encode(complete),act.PRIVATE_PATHS['private_report']:act.encode(report),
                 act.PRIVATE_PATHS['private_authority']:act.encode(authority),act.PRIVATE_PATHS['availability']:avail_raw,
                 act.PRIVATE_PATHS['private_acceptance'].parent/'progress.json':act.encode(progress),
                 act.PRIVATE_PHASE:phase_raw,
                 **{admission_paths[phase]:act.encode(packet) for phase,packet in admissions.items()}}
        policy['private_accepted_revision']=PRIOR
        return policy,records
    def test_runtime_completion_is_causally_bound_without_future_hash_constants(self):
        policy,records=self.chain()
        with patch.object(act.source_files,'protected',side_effect=lambda path:records[Path(path)]):
            actual=act.private_receipts(policy)
        self.assertEqual(actual['private_acceptance'][0]['served_revision'],PRIOR)
        self.assertEqual(actual['progress'][0]['preparation']['after-auth']['operations_revision'],act.BASE)
        self.assertNotIn('sha256',policy['private_acceptance'])
        self.assertEqual(actual['phase_preservation'][1],records[act.PRIVATE_PHASE])

    def test_actual_private_phase_record_is_immutable_history_without_parent_liveness_revival(self):
        policy,records=self.chain();host=object.__new__(act.NativeHost);host.policy=policy
        with patch.object(act.source_files,'protected',side_effect=lambda path:records[Path(path)]), \
             patch.object(act.Path,'read_text',side_effect=AssertionError('historical parent must not be revived')):
            host.inputs=act.private_receipts(policy)
            self.assertEqual(host.inputs['phase_preservation'][0]['binding']['parent_pid'],999999)
            records[act.PRIVATE_PHASE]+=b'\n'
            with self.assertRaisesRegex(act.Refusal,'retained_private_phase_file_binding'):host.check_private_inputs()

    def test_private_phase_hash_observation_and_parent_binding_cannot_be_substituted(self):
        for key,mutate,label in (
            ('private_acceptance',lambda row:row.__setitem__('phase_preservation_sha256','f'*64),'phase_file_binding'),
            ('private_authority',lambda row:row.__setitem__('parent_start_ticks',789),'phase_file_binding'),
            ('private_authority',lambda row:row['authority']['phase_preservation'].__setitem__('path','/tmp/other.json'),'phase_file_binding'),
            ('private_report',lambda row:row['co_tenant_preservation_admission']['phase_observation']['external_boundary'].__setitem__('metadata_ns','1791410000000000002'),'phase_proof_binding'),
            ('private_acceptance',lambda row:row.pop('co_tenant_preservation_admission'),'phase_proof_binding')):
            with self.subTest(key=key,label=label):
                policy,records=self.chain();path=act.PRIVATE_PATHS[key];row=json.loads(records[path]);mutate(row);records[path]=act.encode(row)
                if key=='private_report':
                    complete=json.loads(records[act.PRIVATE_PATHS['private_acceptance']]);complete['independent_report_sha256']=act.sha(records[path])
                    records[act.PRIVATE_PATHS['private_acceptance']]=act.encode(complete)
                with patch.object(act.source_files,'protected',side_effect=lambda path:records[Path(path)]), \
                     self.assertRaisesRegex(act.Refusal,label):act.private_receipts(policy)

    def test_admission_proof_cannot_disappear_even_when_its_whole_causal_chain_is_rehashed(self):
        policy,records=self.chain();phase='after-auth'
        authority=json.loads(records[act.PRIVATE_PATHS['private_authority']])
        path=Path(authority['authority']['admissions'][phase]['path']);packet=json.loads(records[path])
        packet.pop('co_tenant_preservation_admission');records[path]=act.encode(packet)
        authority['authority']['admissions'][phase]['sha256']=act.sha(records[path])
        authority['admission_sha256'][phase]=act.sha(records[path])
        records[act.PRIVATE_PATHS['private_authority']]=act.encode(authority)
        progress_path=act.PRIVATE_PATHS['private_acceptance'].parent/'progress.json'
        progress=json.loads(records[progress_path]);progress['preparation'][phase]=packet
        records[progress_path]=act.encode(progress)
        report=json.loads(records[act.PRIVATE_PATHS['private_report']]);report['browser_progress_sha256']=act.sha(records[progress_path])
        records[act.PRIVATE_PATHS['private_report']]=act.encode(report)
        complete=json.loads(records[act.PRIVATE_PATHS['private_acceptance']])
        complete['independent_report_sha256']=act.sha(records[act.PRIVATE_PATHS['private_report']])
        records[act.PRIVATE_PATHS['private_acceptance']]=act.encode(complete)
        with patch.object(act.source_files,'protected',side_effect=lambda path:records[Path(path)]), \
             self.assertRaisesRegex(act.Refusal,'retained_private_phase_admission_binding'):act.private_receipts(policy)
    def test_complete_candidate_with_any_fixed_parent_stop_record_is_never_admitted(self):
        for parent in (act.PRIVATE_PATHS['private_acceptance'].parent,act.PRIVATE_PATHS['private_authority'].parent):
            with self.subTest(parent=parent):
                policy,records=self.chain();stop=parent/'STOP.json'
                with patch.object(act.os.path,'lexists',side_effect=lambda path:Path(path)==stop), \
                     patch.object(act.source_files,'protected',side_effect=AssertionError('stopped candidate read')):
                    with self.assertRaisesRegex(act.Refusal,'private_campaign_stop_record_absent'):act.private_receipts(policy)
    def test_missing_or_inconsistent_runtime_evidence_refuses(self):
        for key,field,value,label in (
            ('private_acceptance','complete',False,'completed_private_acceptance'),
            ('private_acceptance','served_revision',TARGET,'completed_private_acceptance'),
            ('private_acceptance','independent_report_sha256','f'*64,'completed_private_acceptance'),
            ('private_report','browser_progress_sha256','f'*64,'completed_private_acceptance'),
            ('private_authority','admission_sha256',{'before-auth':'f'*64,'after-auth':'f'*64},'private_admission_causal_chain')):
            with self.subTest(field=field):
                policy,records=self.chain();path=act.PRIVATE_PATHS[key];record=json.loads(records[path]);record[field]=value
                records[path]=act.encode(record)
                # Isolate the deeper progress binding by preserving the actual
                # complete-to-report causal hash when report content changes.
                if key=='private_report':
                    complete=json.loads(records[act.PRIVATE_PATHS['private_acceptance']])
                    complete['independent_report_sha256']=act.sha(records[path])
                    records[act.PRIVATE_PATHS['private_acceptance']]=act.encode(complete)
                    label='completed_browser_cross_binding'
                with patch.object(act.source_files,'protected',side_effect=lambda path:records[Path(path)]), \
                     self.assertRaisesRegex(act.Refusal,label):act.private_receipts(policy)
        policy,records=self.chain();policy['private_report']['path']='/tmp/nonexistent-or-unreviewed-output'
        with patch.object(act.source_files,'protected',side_effect=lambda path:records[Path(path)]),self.assertRaises(act.Refusal):
            act.private_receipts(policy)
    def test_admitted_runtime_chain_cannot_drift_after_the_full_proof(self):
        policy,records=self.chain();host=object.__new__(act.NativeHost);host.policy=policy
        with patch.object(act.source_files,'protected',side_effect=lambda path:records[Path(path)]):
            host.inputs=act.private_receipts(policy)
            self.assertEqual(host.check_private_inputs(),host.inputs)
            # Even equivalent JSON cannot silently replace the admitted bytes.
            path=act.PRIVATE_PATHS['private_acceptance'];records[path]+=b'\n'
            with self.assertRaisesRegex(act.Refusal,'private_inputs_unchanged'):host.check_private_inputs()
    def test_slow_guard_consumes_forward_ttl_budget_before_completion(self):
        fixture=self.sessions();at,secret,fp,actors,states,rows,_,_,decoder=fixture
        for state in states.values():
            for cookie in state['cookies']:
                if cookie['name'] != 'quillmd_doctor_csrf':cookie['expires']=at.timestamp()+601
        for row in rows.values():row['expire_date']=at+timedelta(seconds=601)
        clock=[0];count=[0];host=FictionalHost();host.deadline=2400;host.forward_deadline=None
        host.check=lambda reserve=0:act.NativeHost.check(host,reserve)
        host.check_hold=lambda:host.check()
        host.forward_budget=lambda:act.NativeHost.forward_budget(host)
        def sessions(minimum):
            count[0]+=1
            if count[0]==3:clock[0]=535
            return act.live_session_admission(states,rows,actors,secret,fp,decoder,at+timedelta(seconds=clock[0]),
                                             minimum,admin_device='otp_totp.totpdevice/5')
        host.session_admission=sessions
        delayed=[False,False]
        def snapshot():
            host.check()
            if count[0]==2 and not delayed[0]:clock[0]+=70;delayed[0]=True
            if count[0]==3 and not delayed[1]:clock[0]+=70;delayed[1]=True
            host.check();return deepcopy(host.guard)
        host.snapshot=snapshot
        def routes():clock[0]=535;return {'https://app.quillmd.com':503}
        host.routes=routes
        policy={'private_accepted_revision':PRIOR,'original_ingress_metadata':metadata(ORIGINAL)}
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            with patch.object(act,'OUTPUT',root/'output'),patch.object(act,'ATTEMPT',root/'attempt'), \
                 patch.object(act,'OLD_INGRESS_SHA',act.sha(ORIGINAL)),patch.object(act.time,'monotonic',side_effect=lambda:clock[0]):
                result=act.transition(host,policy,TARGET,{act.TEMPLATE:TEMPLATE},execute=True)
        self.assertTrue(result['complete']);self.assertEqual(host.forward_deadline,540)
        self.assertEqual(host.records['complete.json']['live_session_admission_after']['remaining_seconds'],66)
        self.assertEqual(clock[0],535);self.assertFalse(delayed[1])
        # A later slow capture cannot be hidden after the final TTL proof.
        self.assertGreater(act.live_session_admission(states,rows,actors,secret,fp,decoder,
            at+timedelta(seconds=clock[0]),0,admin_device='otp_totp.totpdevice/5')['remaining_seconds'],60)
    def test_slow_completion_fsync_cannot_return_success_after_live_session_expiry(self):
        fixture=self.sessions();at,secret,fp,actors,states,rows,_,_,decoder=fixture
        for state in states.values():
            for cookie in state['cookies']:
                if cookie['name'] != 'quillmd_doctor_csrf':cookie['expires']=at.timestamp()+601
        for row in rows.values():row['expire_date']=at+timedelta(seconds=601)
        clock=[0];count=[0];host=FictionalHost();host.deadline=2400;host.forward_deadline=None
        host.check=lambda reserve=0:act.NativeHost.check(host,reserve)
        host.check_hold=lambda:host.check()
        host.forward_budget=lambda:act.NativeHost.forward_budget(host)
        def sessions(minimum):
            count[0]+=1
            if count[0]==3:clock[0]=500
            return act.live_session_admission(states,rows,actors,secret,fp,decoder,at+timedelta(seconds=clock[0]),
                                             minimum,admin_device='otp_totp.totpdevice/5')
        host.session_admission=sessions;real_write=host.write
        def stalled_write(name,value):
            real_write(name,value)
            if name=='complete.json':clock[0]+=110
        host.write=stalled_write
        policy={'private_accepted_revision':PRIOR,'original_ingress_metadata':metadata(ORIGINAL)}
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            with patch.object(act,'OUTPUT',root/'output'),patch.object(act,'ATTEMPT',root/'attempt'), \
                 patch.object(act,'OLD_INGRESS_SHA',act.sha(ORIGINAL)),patch.object(act.time,'monotonic',side_effect=lambda:clock[0]):
                with self.assertRaisesRegex(act.Refusal,'failed_with_preserved_evidence'):
                    act.transition(host,policy,TARGET,{act.TEMPLATE:TEMPLATE},execute=True)
        self.assertEqual(clock[0],610);self.assertEqual(host.forward_deadline,540)
        self.assertTrue(host.records['complete.json']['completion_valid_only_without_failed_receipt'])
        self.assertEqual(host.records['failed.json']['failure_reason'],'normal443_bounded_forward_interval')
        self.assertTrue(host.records['failed.json']['rollback']['private_availability_preserved'])
        self.assertEqual(host.raw,ORIGINAL)
        self.assertIn(b'QUILLMD_OWNER_NORMAL_ORIGIN_ENABLED="0"',host.environment)
    def sessions(self):
        from django.core import signing
        at=datetime.now(timezone.utc);secret='fictional-session-key-only';fp='e'*40
        actors={'doctor':'fictional-doctor','admin':'fictional-admin'};states={};rows={};payloads={}
        def signed(value):
            return signing.TimestampSigner(key=secret,salt='django.contrib.sessions.SessionStore',fallback_keys=[]).sign_object(value)
        for index,actor in enumerate(('doctor','admin')):
            doctor_key=chr(97+index*2)*32;preview_key=chr(98+index*2)*32
            normal={'_auth_user_id':actors[actor],'_auth_user_backend':'core.auth.VerifiedBackend','session_version':1}
            if actor=='admin':normal['otp_device_id']='otp_totp.totpdevice/5'
            grant={'kind':'quillmd-preview-v1','grant':{'fingerprint':fp,'issued':at.timestamp()-300,'seen':at.timestamp()-10},
                   'flows':{},'_session_expiry':1800}
            payloads[doctor_key]=normal;payloads[preview_key]=grant
            cookies=[]
            for name,key,site in (('quillmd_doctor_session',doctor_key,'Strict'),('__Host-quillmd_preview',preview_key,'Lax'),
                                  ('quillmd_doctor_csrf','fictional-csrf-'+actor,'Strict')):
                cookies.append({'name':name,'value':key,'domain':'app.quillmd.com','path':'/','httpOnly':True,
                                'secure':True,'sameSite':site,'expires':at.timestamp()+1700})
            states[actor]={'cookies':cookies,'origins':[]}
            for key in (doctor_key,preview_key):
                rows[key]={'session_key':key,'session_data':signed(payloads[key]),'expire_date':at+timedelta(seconds=1700)}
        decoder=lambda raw,key:signing.loads(raw.decode(),key=key,salt='django.contrib.sessions.SessionStore',fallback_keys=[],max_age=None)
        return at,secret,fp,actors,states,rows,payloads,signed,decoder
    def admit(self,fixture,minimum=600):
        at,secret,fp,actors,states,rows,_,_,decoder=fixture
        return act.live_session_admission(states,rows,actors,secret,fp,decoder,at,minimum,admin_device='otp_totp.totpdevice/5')
    def test_genuine_signatures_four_rows_and_measured_ttl_without_renewal(self):
        fixture=self.sessions();before=deepcopy(fixture[4:7]);result=self.admit(fixture)
        self.assertEqual(result['remaining_seconds'],1700);self.assertFalse(result['session_renewal_performed'])
        self.assertEqual(result['database_writes'],0);self.assertEqual(fixture[4:7],before)
        self.assertNotIn('session_data',json.dumps(result));self.assertNotIn('a'*32,json.dumps(result))
    def test_every_live_expiry_boundary_requires_strict_forward_reserve(self):
        for actor in ('doctor','admin'):
            for boundary in ('doctor-db','doctor-browser','preview-db','preview-browser','idle','absolute'):
                with self.subTest(actor=actor,boundary=boundary):
                    fixture=self.sessions();at,_,_,_,states,rows,payloads,signed,_=fixture
                    cookies={c['name']:c for c in states[actor]['cookies']}
                    normal=cookies['quillmd_doctor_session'];preview=cookies['__Host-quillmd_preview']
                    if boundary.endswith('-db'):rows[(normal if boundary.startswith('doctor') else preview)['value']]['expire_date']=at+timedelta(seconds=600)
                    elif boundary.endswith('-browser'):(normal if boundary.startswith('doctor') else preview)['expires']=at.timestamp()+600
                    else:
                        payload=payloads[preview['value']]
                        payload['grant']['seen' if boundary=='idle' else 'issued']=at.timestamp()-(1200 if boundary=='idle' else 6600)
                        if boundary=='idle':payload['grant']['issued']=at.timestamp()-1500
                        rows[preview['value']]['session_data']=signed(payload)
                    with self.assertRaisesRegex(act.Refusal,'remaining_ttl'):self.admit(fixture)
    def test_expired_signature_still_authenticates_history_but_cannot_admit_live_access(self):
        fixture=self.sessions();at,secret,_,_,_,rows,_,_,decoder=fixture
        self.assertTrue(decoder(rows['a'*32]['session_data'].encode(),secret))
        expired=(at+timedelta(seconds=1800),*fixture[1:])
        with self.assertRaises(act.Refusal):self.admit(expired)
    def test_wrong_mfa_actor_cookie_scope_grant_signature_or_population_refuses(self):
        for bad in ('mfa','actor','cookie','fingerprint','signature','extra-row','missing-row','duplicate-key'):
            with self.subTest(bad=bad):
                fixture=self.sessions();_,_,_,_,states,rows,payloads,signed,_=fixture
                if bad in ('mfa','actor'):
                    payloads['c'*32]['otp_device_id' if bad=='mfa' else '_auth_user_id']='wrong'
                    rows['c'*32]['session_data']=signed(payloads['c'*32])
                elif bad=='cookie':states['admin']['cookies'][0]['secure']=False
                elif bad=='fingerprint':
                    payloads['b'*32]['grant']['fingerprint']='wrong';rows['b'*32]['session_data']=signed(payloads['b'*32])
                elif bad=='signature':rows['a'*32]['session_data']+='tampered'
                elif bad=='extra-row':rows['z'*32]=dict(rows['a'*32],session_key='z'*32)
                elif bad=='missing-row':del rows['a'*32]
                else:states['admin']['cookies'][0]['value']='a'*32
                with self.assertRaises(Exception):self.admit(fixture)


class GeneratedSingleFileHelperTests(unittest.TestCase):
    """Execute the real generated Python solely in a disposable directory.

    Root ownership/chroot and native nginx actions are fictional. File opens,
    bytes, exclusive creation, atomic replacement and cleanup are real local IO.
    """
    def host(self, root, *, failure=None, short_write=False):
        original_open,original_fstat,original_write=os.open,os.fstat,os.write
        calls=[];host=object.__new__(act.NativeHost);host.check_hold=MagicMock()
        def root_metadata(fd):
            values=list(original_fstat(fd));values[4]=values[5]=0
            return os.stat_result(values)
        def opened(path,*args,**kwargs):
            return original_open(root if path=='/target' else path,*args,**kwargs)
        def native(command,**kwargs):
            calls.append(command)
            if failure=='nginx' and command[:2]==['/usr/sbin/nginx','-t']:
                raise OSError('fictional nginx test failure')
            return SimpleNamespace(returncode=0)
        def helper(argv,*,input,timeout,failure_directory):
            self.assertEqual(timeout,60);self.assertEqual(failure_directory,act.OUTPUT)
            self.assertEqual([argv[i+1] for i,x in enumerate(argv) if x=='--mount'],
                ['type=bind,src=/,dst=/host,readonly','type=bind,src=/etc/nginx/sites-available,dst=/target'])
            output=io.StringIO()
            with patch.object(os,'open',side_effect=opened),patch.object(os,'fstat',side_effect=root_metadata), \
                 patch.object(os,'chroot'),patch.object(os,'chdir'),patch.object(act.subprocess,'run',side_effect=native), \
                 patch('sys.stdout',new=output),patch.object(os,'write',side_effect=(
                     (lambda fd,raw:original_write(fd,raw[:len(raw)//2])) if short_write else original_write)):
                exec(compile(input,'<fictional-real-generated-helper>','exec'),{})
            return SimpleNamespace(stdout=output.getvalue().encode())
        host.managed=SimpleNamespace(IMAGE='fictional-pinned-image',run_helper=helper)
        return host,calls
    def ingress_metadata(self,path,raw):
        info=path.stat()
        return {'uid':0,'gid':0,'mode':0o644,'device':info.st_dev,'inode':info.st_ino,'sha256':act.sha(raw)}
    def test_single_fixed_file_atomic_replacement_and_native_commands(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);path=root/'quillmd';path.write_bytes(ORIGINAL);path.chmod(0o644)
            foreign=root/'other';foreign.write_bytes(b'unchanged co-tenant')
            host,calls=self.host(root)
            result=host.replace_ingress(ORIGINAL,TEMPLATE,self.ingress_metadata(path,ORIGINAL))
            self.assertEqual(path.read_bytes(),TEMPLATE);self.assertEqual(foreign.read_bytes(),b'unchanged co-tenant')
            self.assertEqual(set(p.name for p in root.iterdir()),{'quillmd','other'})
            self.assertEqual(result['sha256'],act.sha(TEMPLATE));self.assertEqual(result['mode'],0o644)
            self.assertEqual(calls,[['/usr/sbin/nginx','-t'],['/usr/bin/systemctl','reload','nginx.service']])
            self.assertEqual(host.check_hold.call_count,2)
    def test_current_byte_drift_and_existing_candidate_refuse_before_mutation(self):
        for bad in ('drift','candidate'):
            with self.subTest(bad=bad),tempfile.TemporaryDirectory() as temp:
                root=Path(temp);path=root/'quillmd';path.write_bytes(ORIGINAL);path.chmod(0o644)
                expected=self.ingress_metadata(path,ORIGINAL)
                if bad=='drift':path.write_bytes(b'unknown current bytes')
                else:(root/'.quillmd-owner-normal443-v1-candidate').write_bytes(b'unowned existing candidate')
                before={p.name:p.read_bytes() for p in root.iterdir()};host,calls=self.host(root)
                with self.assertRaises((AssertionError,FileExistsError)):
                    host.replace_ingress(ORIGINAL,TEMPLATE,expected)
                self.assertEqual({p.name:p.read_bytes() for p in root.iterdir()},before);self.assertFalse(calls)
    def test_short_write_cleans_only_owned_candidate_without_replacing_original(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);path=root/'quillmd';path.write_bytes(ORIGINAL);path.chmod(0o644)
            host,calls=self.host(root,short_write=True)
            with self.assertRaises(AssertionError):host.replace_ingress(ORIGINAL,TEMPLATE,self.ingress_metadata(path,ORIGINAL))
            self.assertEqual(path.read_bytes(),ORIGINAL);self.assertEqual(set(p.name for p in root.iterdir()),{'quillmd'})
            self.assertFalse(calls)
    def test_failed_nginx_test_retains_measurable_new_bytes_and_supports_exact_restore(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);path=root/'quillmd';path.write_bytes(ORIGINAL);path.chmod(0o644)
            host,calls=self.host(root,failure='nginx')
            with self.assertRaises(OSError):host.replace_ingress(ORIGINAL,TEMPLATE,self.ingress_metadata(path,ORIGINAL))
            self.assertEqual(path.read_bytes(),TEMPLATE);self.assertEqual(calls,[['/usr/sbin/nginx','-t']])
            restored,commands=self.host(root)
            restored.replace_ingress(TEMPLATE,ORIGINAL,self.ingress_metadata(path,TEMPLATE))
            self.assertEqual(path.read_bytes(),ORIGINAL);self.assertEqual(len(commands),2)


@patch.multiple(act.os,getuid=lambda:1000,geteuid=lambda:1000)
class NormalControllerHolderTests(unittest.TestCase):
    def process_start(self,raw):return int(raw.rsplit(') ',1)[1].split()[19])
    def lock_population(self,raw,pid):
        found=set()
        for line in raw.splitlines():
            parts=line.split()
            if len(parts)==8 and parts[1:4]==['FLOCK','ADVISORY','WRITE'] and parts[4]==str(pid):
                major,minor,inode=parts[5].split(':');found.add((int(major,16),int(minor,16),int(inode)))
        return found
    def argv(self,mode='--execute'):
        return b'\0'.join(value.encode() for value in (str(act.PYTHON),'-B',str(act.SOURCE/act.ENTRY),mode,
                                                    '--operations-revision',TARGET))+b'\0'
    def test_own_normal_command_is_distinct_from_private_and_rejects_wrong_or_foreign_holder(self):
        pid=os.getpid();start=self.process_start(Path('/proc/self/stat').read_text())
        now=time.monotonic()
        def admit(command=None,**changes):
            values=dict(operations=TARGET,source=act.SOURCE,mode='--execute',pid=pid,started=start,
                        acquired=now-1,deadline=now+10,parse_start=self.process_start,
                        read_bytes=lambda _:self.argv() if command is None else command)
            values.update(changes);return act.normal_controller_command(**values)
        witness=admit();self.assertEqual(witness['controller'],'normal443');self.assertEqual(witness['parent_pid'],pid)
        for name in ('getuid','geteuid'):
            with self.subTest(identity=name),patch.object(act.os,name,return_value=1001), \
                 self.assertRaisesRegex(act.Refusal,'own_controller_interval'):
                admit()
        for changes,label in (({'pid':pid+1},'own_controller_interval'),({'started':start+1},'own_process_reused'),
                              ({'acquired':now+20},'own_controller_interval'),({'deadline':float('nan')},'own_controller_interval')):
            with self.subTest(changes=changes),self.assertRaisesRegex(act.Refusal,label):admit(**changes)
        for command in (self.argv('--preflight'),self.argv().replace(act.ENTRY.encode(),b'scripts/run-owner-acceptance-v3.py')):
            with self.assertRaisesRegex(act.Refusal,'own_fixed_command'):admit(command)
    def test_actual_five_kernel_locks_are_rechecked_and_released_or_replaced_lock_refuses(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);host=object.__new__(act.NativeHost);fds=[]
            names=tuple('fictional-lock-'+str(i) for i in range(5))
            host.acceptance=SimpleNamespace(LOCKS=names[:4],PUBLICATION_LOCK=names[4],
                process_start=self.process_start,lock_population=self.lock_population)
            host.inside=True;host.source=act.SOURCE;host.operations=TARGET;host.mode='--execute';host.parent_pid=os.getpid()
            host.parent_start=self.process_start(Path('/proc/self/stat').read_text());host.lock_rows=[]
            host.deadline=time.monotonic()+10;host.alignment={'hold':{'acquired_monotonic':time.monotonic()-.01}}
            real_read=Path.read_bytes;real_fstat=os.fstat
            try:
                for name in names:
                    fd=os.open(root/name,os.O_RDWR|os.O_CREAT|os.O_EXCL,0o600);fds.append(fd)
                    fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB);info=os.fstat(fd)
                    host.lock_rows.append({'path':str(root/name),'fd':fd,'device':info.st_dev,'inode':info.st_ino})
                def observed(path):
                    return self.argv() if str(path)==f'/proc/{os.getpid()}/cmdline' else real_read(path)
                def lock_metadata(fd,uid=1000,gid=1000):
                    info=real_fstat(fd)
                    if fd not in fds:return info
                    values=list(info);values[4]=uid;values[5]=gid
                    return os.stat_result(values)
                with patch.object(act,'RUNTIME',root),patch.object(Path,'read_bytes',observed), \
                     patch.object(act.os,'fstat',side_effect=lock_metadata):
                    self.assertTrue(host.check_hold()['same_five_kernel_locks_verified'])
                    directory=os.open(root,os.O_RDONLY|os.O_DIRECTORY)
                    try:self.assertEqual(os.fstat(directory),real_fstat(directory))
                    finally:os.close(directory)
                    for owner in ({'uid':1001},{'gid':1001}):
                        with self.subTest(owner=owner), \
                             patch.object(act.os,'fstat',side_effect=lambda fd:lock_metadata(fd,**owner)), \
                             self.assertRaisesRegex(act.Refusal,'kernel_five_locks'):
                            host.check_hold()
                    fcntl.flock(fds[-1],fcntl.LOCK_UN)
                    with self.assertRaisesRegex(act.Refusal,'kernel_five_locks'):host.check_hold()
                    fcntl.flock(fds[-1],fcntl.LOCK_EX|fcntl.LOCK_NB)
                    (root/names[-1]).rename(root/'detached-actual-lock')
                    (root/names[-1]).write_bytes(b'foreign replacement')
                    with self.assertRaisesRegex(act.Refusal,'kernel_five_locks'):host.check_hold()
            finally:
                for fd in fds:os.close(fd)

def copy_field(value):
    if value is None:
        return b'\\N'
    raw = value if isinstance(value, bytes) else str(value).encode()
    return raw.replace(b'\\', b'\\\\').replace(b'\t', b'\\t').replace(b'\n', b'\\n').replace(b'\r', b'\\r')

def copy_row(columns, values):
    return b'\t'.join((copy_field(values[column]) for column in columns)) + b'\n'

class ServedRenewalTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        global ACTUAL_SERVED_RENEWAL_VERIFIER
        import math
        frozen = Path('/opt/meddoc-pro/rebuild/.runtime/owner-demo-20261006/recovery-20261007/acceptance-v3-preparation-v2-20261007/verify_installed_acceptance_v3.py')
        if not frozen.exists():
            raise unittest.SkipTest('Exact retained frozen pure-helper source not present')
        raw = frozen.read_bytes()
        if act.sha(raw) != '34d4d3bf0b9641a2f642717b33833beb7a7f49a0c043bc095e592c41a78b0023':
            raise AssertionError('Frozen pure-helper source differs')
        names = {'parsed_timestamp', 'copy_value', 'normal_session', 'validate_admin_renewal', 'validate_preview_renewal', 'row_mapping'}
        functions = [node for node in ast.parse(raw).body if isinstance(node, ast.FunctionDef) and node.name in names]
        if {node.name for node in functions} != names:
            raise AssertionError('Frozen helper population differs')
        namespace = {'require': act.served_require, 'datetime': datetime, 'timezone': timezone, 'timedelta': timedelta, 'math': math, 'copy': __import__('copy')}
        exec(compile(ast.Module(body=functions, type_ignores=[]), str(frozen), 'exec'), namespace)
        ACTUAL_SERVED_RENEWAL_VERIFIER = SimpleNamespace(**{name: namespace[name] for name in names})

    def fixture(self):
        from django.core import signing
        self.secret = 'synthetic-disposable-HMAC-secret'
        self.fp = 'e' * 40
        self.actors = {'doctor': '11111111-1111-4111-8111-111111111111', 'admin': '22222222-2222-4222-8222-222222222222'}
        self.keys = {'doctor': {'normal': 'a' * 32, 'preview': 'b' * 32}, 'admin': {'normal': 'c' * 32, 'preview': 'd' * 32}}
        self.at = datetime(2026, 10, 7, 12, tzinfo=timezone.utc)
        self.intervals = {actor: (self.at + timedelta(seconds=index * 10), self.at + timedelta(seconds=index * 10 + 4)) for index, actor in enumerate(('doctor', 'admin'))}
        self.before = {table: {'columns': ['id', 'value'], 'primary_keys': ['id'], 'rows': [b'old\tunchanged\n']} for table in act.SERVED_TABLES}
        session_columns = ['session_key', 'session_data', 'expire_date']
        audit_columns = ['id', 'created_at', 'actor_id', 'organization_id', 'department_id', 'action', 'target', 'details']
        self.before['django_session'] = {'columns': session_columns, 'primary_keys': ['session_key'], 'rows': []}
        self.before['core_auditevent'] = {'columns': audit_columns, 'primary_keys': ['id'], 'rows': [copy_row(audit_columns, {'id': '33333333-3333-4333-8333-333333333333', 'created_at': self.at - timedelta(seconds=500), 'actor_id': self.actors['admin'], 'organization_id': None, 'department_id': None, 'action': 'prior.audit', 'target': '', 'details': '{}'})]}
        self.payloads = {}
        self.new_payloads = {}
        self.new_rows = []
        for actor in ('doctor', 'admin'):
            begin, end = self.intervals[actor]
            normal = {'_auth_user_id': self.actors[actor], '_auth_user_backend': 'core.auth.VerifiedBackend', '_auth_user_hash': 'synthetic-existing-full-hash'}
            if actor == 'admin':
                normal['otp_device_id'] = 'otp_totp.totpdevice/5'
            preview = {'kind': 'quillmd-preview-v1', 'grant': {'fingerprint': self.fp, 'issued': (self.at - timedelta(seconds=300)).timestamp(), 'seen': (self.at - timedelta(seconds=10)).timestamp()}, 'flows': {'existing': 'unchanged'}, '_session_expiry': 1800}
            for kind, payload in (('normal', normal), ('preview', preview)):
                key = self.keys[actor][kind]
                self.payloads[key] = deepcopy(payload)
                later = deepcopy(payload)
                if kind == 'preview':
                    later['grant']['seen'] = (begin + timedelta(seconds=1)).timestamp()
                self.new_payloads[key] = later
                self.before['django_session']['rows'].append(copy_row(session_columns, {'session_key': key, 'session_data': self.signed(payload, self.at - timedelta(seconds=10)), 'expire_date': self.at + timedelta(seconds=1700)}))
                self.new_rows.append(copy_row(session_columns, {'session_key': key, 'session_data': self.signed(later, begin + timedelta(seconds=2)), 'expire_date': begin + timedelta(seconds=1803)}))
        self.before['django_session']['rows'].append(copy_row(session_columns, {'session_key': 'z' * 32, 'session_data': self.signed({'unrelated': True}, self.at), 'expire_date': self.at + timedelta(seconds=1800)}))
        self.after = deepcopy(self.before)
        self.after['django_session']['rows'] = self.new_rows + [self.before['django_session']['rows'][-1]]
        self.after['core_auditevent']['rows'].append(copy_row(audit_columns, {'id': '44444444-4444-4444-8444-444444444444', 'created_at': self.intervals['admin'][0] + timedelta(seconds=1), 'actor_id': self.actors['admin'], 'organization_id': None, 'department_id': None, 'action': 'admin.services_read', 'target': '', 'details': '{}'}))
        return (self.before, self.after)

    def signed(self, payload, at):
        from django.core import signing
        with patch('django.core.signing.time.time', return_value=at.timestamp()):
            return signing.TimestampSigner(key=self.secret, salt='django.contrib.sessions.SessionStore', fallback_keys=[]).sign_object(payload)

    def admit(self):
        return act.admit_served_deltas(self.before, self.after, self.keys, self.actors, self.intervals, self.secret, self.fp, ACTUAL_SERVED_RENEWAL_VERIFIER)

    def mutate_session(self, actor, kind, *, payload=None, expired=None, sign_at=None, old=False):
        table = (self.before if old else self.after)['django_session']
        key = self.keys[actor][kind]
        idx = next((index for index, row in enumerate(table['rows']) if row.startswith(key.encode() + b'\t')))
        cells = dict(zip(table['columns'], table['rows'][idx][:-1].split(b'\t')))
        if payload is not None:
            cells['session_data'] = self.signed(payload, sign_at or self.intervals[actor][0] + timedelta(seconds=2)).encode()
        if expired is not None:
            cells['expire_date'] = str(expired).encode()
        table['rows'][idx] = copy_row(table['columns'], cells)

    def mutate_audit(self, **changes):
        table = self.after['core_auditevent']
        values = dict(zip(table['columns'], table['rows'][-1][:-1].split(b'\t')))
        values = {key: None if value == b'\\N' else value for key, value in values.items()}
        values.update(changes)
        table['rows'][-1] = copy_row(table['columns'], values)

    def test_positive_genuine_frozen_HMAC_helpers_and_byte_projection(self):
        self.fixture()
        original = deepcopy((self.before, self.after))
        result = self.admit()
        self.assertEqual(result['projected_tables'], self.after)
        self.assertEqual(result['session_rows_changed'], 4)
        self.assertEqual(len(result['unchanged_tables']), 34)
        self.assertEqual(result['audit_addition']['action'], 'admin.services_read')
        self.assertEqual((self.before, self.after), original)
        serialized = json.dumps({key: value for key, value in result.items() if key != 'projected_tables'})
        self.assertNotIn(self.secret, serialized)
        self.assertNotIn('a' * 32, serialized)
        self.assertNotIn('session_data', serialized.replace('"session_data"', ''))

    def test_normal_full_payload_actor_and_MFA_changes_refused(self):
        self.fixture()
        for actor, field, value in (('doctor', '_auth_user_hash', 'changed'), ('doctor', '_auth_user_id', self.actors['admin']), ('admin', 'otp_device_id', 'otp_totp.totpdevice/6'), ('admin', '_session_expiry', 600)):
            with self.subTest(actor=actor, field=field):
                self.fixture()
                payload = deepcopy(self.new_payloads[self.keys[actor]['normal']])
                payload[field] = value
                self.mutate_session(actor, 'normal', payload=payload)
                with self.assertRaises(act.ServedDeltaRefusal):
                    self.admit()

    def test_original_admin_MFA_required_even_when_unchanged(self):
        self.fixture()
        payload = deepcopy(self.payloads[self.keys['admin']['normal']])
        payload.pop('otp_device_id')
        self.mutate_session('admin', 'normal', payload=payload, old=True)
        self.mutate_session('admin', 'normal', payload=payload)
        with self.assertRaises(act.ServedDeltaRefusal):
            self.admit()

    def test_preview_fingerprint_issued_flows_expiry_and_seen_refused(self):
        for change in ('fingerprint', 'issued', 'flows', 'remaining', 'seen', 'extra'):
            with self.subTest(change=change):
                self.fixture()
                payload = deepcopy(self.new_payloads[self.keys['doctor']['preview']])
                if change == 'fingerprint':
                    payload['grant']['fingerprint'] = 'f' * 40
                if change == 'issued':
                    payload['grant']['issued'] += 1
                if change == 'flows':
                    payload['flows']['other'] = 'introduced'
                if change == 'remaining':
                    payload['_session_expiry'] = 1900
                if change == 'seen':
                    payload['grant']['seen'] = self.at.timestamp() - 1
                if change == 'extra':
                    payload['extra'] = True
                self.mutate_session('doctor', 'preview', payload=payload)
                with self.assertRaises(act.ServedDeltaRefusal):
                    self.admit()

    def test_genuine_original_and_current_HMACs_required(self):
        from django.core.signing import BadSignature
        for old in (False, True):
            for index in range(4):
                with self.subTest(old=old, index=index):
                    self.fixture()
                    table = (self.before if old else self.after)['django_session']
                    table['rows'][index] = table['rows'][index].replace(b':', b':x', 1)
                    with self.assertRaises(BadSignature):
                        self.admit()

    def test_signed_payload_JSON_type_changes_do_not_compare_equal(self):
        for kind in ('normal', 'preview'):
            with self.subTest(kind=kind):
                self.fixture()
                key = self.keys['doctor'][kind]
                prior = deepcopy(self.payloads[key])
                following = deepcopy(self.new_payloads[key])
                if kind == 'normal':
                    prior['existing_flag'] = True
                    following['existing_flag'] = 1
                else:
                    prior['flows']['existing'] = True
                    following['flows']['existing'] = 1
                self.mutate_session('doctor', kind, old=True, payload=prior, sign_at=self.at - timedelta(seconds=10))
                self.mutate_session('doctor', kind, payload=following)
                with self.assertRaises(act.ServedDeltaRefusal):
                    self.admit()

    def test_expiry_signature_and_actual_window_refused(self):
        for kind, fault in ((kind, fault) for kind in ('normal', 'preview') for fault in ('expiry', 'sign', 'prior-expired', 'interval')):
            with self.subTest(kind=kind, fault=fault):
                self.fixture()
                if fault == 'expiry':
                    self.mutate_session('doctor', kind, expired=self.at + timedelta(seconds=1810))
                if fault == 'sign':
                    self.mutate_session('doctor', kind, payload=self.new_payloads[self.keys['doctor'][kind]], sign_at=self.at - timedelta(seconds=1))
                if fault == 'prior-expired':
                    self.mutate_session('doctor', kind, old=True, expired=self.at)
                if fault == 'interval':
                    self.intervals['doctor'] = (self.at + timedelta(seconds=5), self.at + timedelta(seconds=6))
                with self.assertRaises(act.ServedDeltaRefusal):
                    self.admit()

    def test_every_other_table_and_unnamed_session_byte_preserved(self):
        for table in act.SERVED_TABLES - {'django_session', 'core_auditevent'}:
            with self.subTest(table=table):
                self.fixture()
                self.after[table]['rows'][0] = b'old\tchanged\n'
                with self.assertRaises(act.ServedDeltaRefusal):
                    self.admit()
        self.fixture()
        self.after['django_session']['rows'][-1] = self.after['django_session']['rows'][-1].replace(b'z', b'y', 1)
        with self.assertRaises(act.ServedDeltaRefusal):
            self.admit()

    def test_new_removed_duplicate_or_other_changed_session_refused(self):
        for fault in ('new', 'removed', 'duplicate', 'other-change'):
            with self.subTest(fault=fault):
                self.fixture()
                rows = self.after['django_session']['rows']
                if fault == 'new':
                    rows.append(rows[-1].replace(b'z' * 32, b'y' * 32))
                if fault == 'removed':
                    rows.pop()
                if fault == 'duplicate':
                    rows.append(rows[0])
                if fault == 'other-change':
                    rows[-1] = rows[-1].replace(b':', b':x', 1)
                with self.assertRaises(act.ServedDeltaRefusal):
                    self.admit()

    def test_exact_audit_addition_and_source_fields_required(self):
        self.fixture()
        changes = ({'action': 'admin.other'}, {'actor_id': self.actors['doctor']}, {'organization_id': self.actors['admin']}, {'department_id': self.actors['admin']}, {'target': 'unexpected'}, {'details': '{"extra":true}'}, {'details': '[]'}, {'created_at': self.at}, {'id': '4'}, {'id': '44444444-4444-4444-8444-44444444444A'})
        for change in changes:
            with self.subTest(change=change):
                self.fixture()
                self.mutate_audit(**change)
                with self.assertRaises(act.ServedDeltaRefusal):
                    self.admit()
        for fault in ('missing', 'extra', 'old-mutated', 'old-removed', 'duplicate'):
            with self.subTest(fault=fault):
                self.fixture()
                rows = self.after['core_auditevent']['rows']
                if fault == 'missing':
                    rows.pop()
                if fault == 'extra':
                    rows.append(rows[-1].replace(b'44444444-4444-4444-8444-444444444444', b'55555555-5555-4555-8555-555555555555'))
                if fault == 'old-mutated':
                    rows[0] = rows[0].replace(b'prior.audit', b'alter.audit')
                if fault == 'old-removed':
                    rows.pop(0)
                if fault == 'duplicate':
                    rows.append(rows[-1])
                with self.assertRaises(act.ServedDeltaRefusal):
                    self.admit()

    def test_COPY_schema_population_framing_and_inputs_refused(self):
        for fault in ('table', 'columns', 'pk', 'no-lf', 'raw-lf', 'extra-cell', 'shared-key', 'naive-time', 'long-window'):
            with self.subTest(fault=fault):
                self.fixture()
                if fault == 'table':
                    self.after.pop('auth_group')
                if fault == 'columns':
                    self.after['core_auditevent']['columns'][3] = 'org_id'
                if fault == 'pk':
                    self.after['auth_group']['primary_keys'] = ['value']
                if fault == 'no-lf':
                    self.after['auth_group']['rows'][0] = b'old\tunchanged'
                if fault == 'raw-lf':
                    self.after['auth_group']['rows'][0] = b'old\tunchanged\nextra\n'
                if fault == 'extra-cell':
                    self.after['auth_group']['rows'][0] = b'old\tunchanged\textra\n'
                if fault == 'shared-key':
                    self.keys['admin']['normal'] = self.keys['doctor']['normal']
                if fault == 'naive-time':
                    self.intervals['doctor'] = tuple((t.replace(tzinfo=None) for t in self.intervals['doctor']))
                if fault == 'long-window':
                    self.intervals['doctor'] = (self.at, self.at + timedelta(seconds=1201))
                with self.assertRaises(act.ServedDeltaRefusal):
                    self.admit()

class ServedVerificationControllerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): ServedRenewalTests.setUpClass()

    def fixture(self, root):
        source=ServedRenewalTests();source.fixture();clock=[0.0]
        host=SimpleNamespace(events=[],records={},rolling_back=False,phase=0,verifier=ACTUAL_SERVED_RENEWAL_VERIFIER,
            session_secret=source.secret,preview_fingerprint=source.fp,live_actors=source.actors,
            live_admin_device='otp_totp.totpdevice/5',source=act.SOURCE,operations=TARGET)
        def states(after):
            result={}
            for actor in ('doctor','admin'):
                expiry=(source.intervals[actor][0]+timedelta(seconds=1803) if after else source.at+timedelta(seconds=1700)).timestamp()
                cookies=[]
                for kind,name,site in (('normal','quillmd_doctor_session','Strict'),('preview','__Host-quillmd_preview','Lax'),
                                      ('csrf','quillmd_doctor_csrf','Strict')):
                    cookies.append({'name':name,'value':source.keys[actor][kind] if kind!='csrf' else 'existing-CSRF',
                        'domain':'app.quillmd.com','path':'/','expires':expiry,'httpOnly':True,'secure':True,'sameSite':site})
                result[actor]={'cookies':cookies,'origins':[]}
            return result
        host.live_states=states(False); following=states(True)
        original=ENV;enabled=act.controlled_environment(original,PRIOR,TARGET,enabled=True)
        ingress=b'actual-fictional-normal-ingress';units={'units':{'doctor':'same-current-PID'},'completion_unit_provenance':{'same':True}}
        completion={'format':1,'complete':True,'stage':'complete','served_revision':TARGET,
            'previous_served_revision':PRIOR,'completion_valid_only_without_failed_receipt':True,
            'owner_normal_origin_enabled':True,'session_renewal_performed':False,
            'provider_calls':0,'authentication_submissions':0,'database_writes':0,
            'full_original_and_new_acceptance_population_preserved':True,'units_after':units,
            'ingress_after':metadata(ingress),'candidate_sha256':act.sha(ingress)}
        policy={'private_accepted_revision':PRIOR}
        host.cipher=SimpleNamespace(decrypt=lambda value:value,encrypt=lambda value:b'protected-fictional:'+value)
        host.old=SimpleNamespace(protected=lambda *_:enabled)
        @contextmanager
        def held():host.events.append('hold');yield
        host.hold=held
        def checked():
            host.events.append('held')
            if hasattr(host,'forward_deadline') and not host.rolling_back and clock[0]>=host.forward_deadline:
                raise act.Refusal('normal443_bounded_forward_interval')
        host.check_hold=checked
        host.git=lambda _,*args:(TARGET.encode() if args==('rev-parse','HEAD') else b'main' if args==('branch','--show-current') else b'')
        host.boundary=lambda _:deepcopy(units);host.foreign=lambda:{'same-current-external-boundary':True}
        host.ingress=lambda:(ingress,metadata(ingress))
        def snapshot():
            checked();result=population()
            result['database']['tables']=act.population_fingerprints(source.after if host.phase else source.before)
            return result
        host.snapshot=snapshot
        host.copy_population=lambda:deepcopy(source.after if host.phase else source.before)
        def full(**options):
            checked();host.events.append('full-after' if options.get('projection') else 'full-before')
            self.assertEqual(options['completion'],completion)
            if options.get('projection'):
                self.assertEqual(options['projection'],act.served_projection(source.before,source.after,host.verifier))
            return {'complete':True,'private_workflow_revision':PRIOR,'all_original_and_new_rows':True}
        host.full_preservation=full
        def budget():host.forward_deadline=clock[0]+540
        host.forward_budget=budget
        def session_admission(minimum):
            host.events.append('live-'+str(minimum));indexed=act.served_copy_tables(source.before)['django_session']
            rows={key[0].decode():{'session_key':key[0].decode(),'session_data':host.verifier.copy_value(row[1]['session_data']).decode(),
                'expire_date':host.verifier.parsed_timestamp(row[1]['expire_date'])}
                for key,row in indexed.items() if key[0].decode() in {v for item in source.keys.values() for v in item.values()}}
            result=act.live_session_admission(host.live_states,rows,source.actors,source.secret,source.fp,
                host.verifier.normal_session,source.at+timedelta(seconds=clock[0]),minimum,admin_device=host.live_admin_device)
            checked();return result
        host.session_admission=session_admission
        def gets(_):
            checked();host.events.append('two-GETs');host.phase=1;clock[0]=14
            return {'complete':True,'attempts':[{'actor':actor,'path':'/' if actor=='doctor' else '/console/services/',
                'GET_requests':1,'started_at':source.intervals[actor][0].isoformat(),'finished_at':source.intervals[actor][1].isoformat(),
                'before':deepcopy(host.live_states[actor]),'after':following[actor],'status':200,
                'body_sha256':'f'*64,'markers_verified':True} for actor in ('doctor','admin')]}
        host.authenticated_gets=gets
        def write(name,value):
            self.assertNotIn(name,host.records);host.records[name]=deepcopy(value)
        host.verify_write=write
        paths={act.OUTPUT/'environment-before.fernet':original,act.OUTPUT/'environment-enabled.fernet':enabled}
        real_live=act.live_session_admission
        def clock_live(*args,**kwargs):
            args=list(args);args[6]=source.at+timedelta(seconds=clock[0]);return real_live(*args,**kwargs)
        return source,host,policy,completion,clock,paths,clock_live

    def run_verify(self,root,host,policy,completion,paths,clock_live):
        with patch.object(act,'VERIFY_OUTPUT',root/'verification'),patch.object(act,'VERIFY_ATTEMPT',root/'attempt.json'), \
             patch.object(act,'SERVED_VERIFICATION_PROTOCOL_QUALIFIED',True), \
             patch.object(act,'normal_completion',return_value=(completion,act.encode(completion))), \
             patch.object(act.source_files,'protected',side_effect=lambda path:paths[path]), \
             patch.object(act,'live_session_admission',side_effect=clock_live):
            return act.verify_served(host,policy,TARGET)

    def test_genuine_HMAC_two_GETs_full_projection_and_honest_write_report(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source,host,policy,complete,clock,paths,live=self.fixture(root)
            result=self.run_verify(root,host,policy,complete,paths,live)
            self.assertEqual((result['authenticated_GETs'],result['session_rows_updated'],result['audit_rows_added']),(2,4,1))
            self.assertEqual((result['new_session_rows'],result['clinical_writes'],result['authentication_submissions'],result['provider_calls']),(0,0,0,0))
            report=host.records['complete.json'];self.assertEqual(report['current_served_revision'],TARGET)
            self.assertEqual(report['private_workflow_revision'],PRIOR);self.assertEqual(report['SQL_statement_count'],'not_instrumented')
            self.assertNotIn('database_writes',report);self.assertTrue(report['completion_valid_only_without_STOP'])
            self.assertEqual(host.events.count('two-GETs'),1);self.assertLess(host.events.index('full-before'),host.events.index('two-GETs'))
            self.assertLess(host.events.index('two-GETs'),host.events.index('full-after'))
            observed=json.loads(host.records['renewal-observations.fernet'].removeprefix(b'protected-fictional:'))
            self.assertEqual([len(observed[t][k]) for t,k in (('django_session','before_rows'),('django_session','after_rows'),
                            ('core_auditevent','before_rows'),('core_auditevent','after_rows'))],[4,4,0,1])
            self.assertNotIn('STOP.json',host.records)
            with self.assertRaisesRegex(act.Refusal,'single_served_verification_attempt'):
                self.run_verify(root,host,policy,complete,paths,live)

    def test_low_TTL_and_failed_original_proof_preserve_STOP_before_any_GET(self):
        for fault in ('TTL','original-proof'):
            with self.subTest(fault=fault),tempfile.TemporaryDirectory() as directory:
                root=Path(directory);source,host,policy,complete,clock,paths,live=self.fixture(root)
                if fault=='TTL':clock[0]=1200
                else:host.full_preservation=MagicMock(side_effect=act.Refusal('normal443_original_proof_refused'))
                with self.assertRaisesRegex(act.Refusal,'stopped_preserving_records'):
                    self.run_verify(root,host,policy,complete,paths,live)
                self.assertNotIn('two-GETs',host.events);self.assertFalse(host.records['STOP.json']['request_attempt_started'])
                self.assertNotIn('attempt.json',host.records);self.assertTrue(host.records['STOP.json']['normal_availability_left_in_place'])

    def test_unknown_GET_failure_keeps_one_attempt_STOP_and_does_not_replay(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source,host,policy,complete,clock,paths,live=self.fixture(root)
            host.authenticated_gets=MagicMock(side_effect=TimeoutError('unknown actual request outcome'))
            with self.assertRaisesRegex(act.Refusal,'stopped_preserving_records'):
                self.run_verify(root,host,policy,complete,paths,live)
            host.authenticated_gets.assert_called_once();self.assertTrue(host.records['STOP.json']['request_attempt_started'])
            self.assertIn('attempt.json',host.records);self.assertNotIn('complete.json',host.records)
            self.assertIsNone(host.records['STOP.json']['failure_reason'])

    def test_unrelated_row_change_cannot_enter_projection_or_full_postproof(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source,host,policy,complete,clock,paths,live=self.fixture(root)
            source.after['core_patient']['rows'][0]=b'old\tchanged-clinical-row\n'
            with self.assertRaisesRegex(act.Refusal,'stopped_preserving_records'):
                self.run_verify(root,host,policy,complete,paths,live)
            self.assertIn('two-GETs',host.events);self.assertNotIn('full-after',host.events)
            self.assertIn('STOP.json',host.records);self.assertNotIn('complete.json',host.records)

    def test_slow_postproof_and_completion_fsync_cannot_return_success(self):
        for stall in ('proof','fsync'):
            with self.subTest(stall=stall),tempfile.TemporaryDirectory() as directory:
                root=Path(directory);source,host,policy,complete,clock,paths,live=self.fixture(root)
                genuine_full=host.full_preservation;genuine_write=host.verify_write
                def full(**options):
                    value=genuine_full(**options)
                    if stall=='proof' and options.get('projection'):clock[0]=600
                    return value
                def write(name,value):
                    genuine_write(name,value)
                    if stall=='fsync' and name=='complete.json':clock[0]=600
                host.full_preservation=full;host.verify_write=write
                with self.assertRaisesRegex(act.Refusal,'stopped_preserving_records'):
                    self.run_verify(root,host,policy,complete,paths,live)
                self.assertIn('STOP.json',host.records)
                self.assertEqual('complete.json' in host.records,stall=='fsync')
                self.assertTrue(host.records['STOP.json']['session_and_audit_records_preserved'])

    def test_complete_COPY_guard_preserves_every_other_population_and_sequences(self):
        source=ServedRenewalTests();source.fixture();admission=source.admit()
        before=population();after=deepcopy(before)
        before['database']['tables']=act.population_fingerprints(source.before)
        after['database']['tables']=act.population_fingerprints(source.after)
        self.assertTrue(act.guard_with_admitted_served_changes(before,after,source.before,source.after,admission))
        for key in ('catalog','invariants','referenced_files'):
            with self.subTest(key=key):
                bad=deepcopy(after);bad['database'][key]={'changed':True}
                with self.assertRaises(act.Refusal):act.guard_with_admitted_served_changes(before,bad,source.before,source.after,admission)
        bad=deepcopy(after);bad['database']['tables']['core_auditevent']['sha256']='unbound'
        with self.assertRaisesRegex(act.Refusal,'COPY_and_snapshot_same_population'):
            act.guard_with_admitted_served_changes(before,bad,source.before,source.after,admission)

    def test_new_mode_unqualified_refuses_before_installed_read_and_default_is_inert(self):
        with patch.object(act,'SERVED_VERIFICATION_PROTOCOL_QUALIFIED',False), \
             patch.object(act.source_files,'protected',side_effect=AssertionError('installed read')), \
             patch.object(act,'source_gate',side_effect=AssertionError('source action')),patch('sys.stdout',new=io.StringIO()) as stream:
            self.assertEqual(act.main([]),0)
            with self.assertRaisesRegex(act.Refusal,'served_verification_protocol_unqualified'):
                act.main(['--verify-served','--operations-revision',TARGET])
        default=json.loads(stream.getvalue());self.assertFalse(default['served_authenticated_verification_completed'])
        self.assertFalse(default['installed_state_accessed']);self.assertFalse(default['execution_performed'])

    def test_new_mode_qualified_default_still_never_claims_access_or_verification(self):
        with patch.object(act,'SERVED_VERIFICATION_PROTOCOL_QUALIFIED',True), \
             patch.object(act.source_files,'protected',side_effect=AssertionError('installed read')), \
             patch.object(act,'source_gate',side_effect=AssertionError('source action')),patch('sys.stdout',new=io.StringIO()) as stream:
            self.assertEqual(act.main([]),0)
        default=json.loads(stream.getvalue());self.assertTrue(default['served_verification_protocol_qualified'])
        self.assertFalse(default['served_authenticated_verification_completed']);self.assertFalse(default['execution_performed'])
        self.assertFalse(default['installed_state_accessed'])
        self.assertEqual((default['provider_calls'],default['authentication_submissions'],default['database_writes']),(0,0,0))

    @patch.multiple(act.os,getuid=lambda:1000,geteuid=lambda:1000)
    def test_new_mode_uses_own_fixed_argv_witness_and_rejects_execute_substitution(self):
        witness=NormalControllerHolderTests();pid=os.getpid();started=witness.process_start(Path('/proc/self/stat').read_text())
        now=time.monotonic();options={'operations':TARGET,'source':act.SOURCE,'mode':'--verify-served',
            'pid':pid,'started':started,'acquired':now-1,'deadline':now+10,'parse_start':witness.process_start}
        result=act.normal_controller_command(**options,read_bytes=lambda _:witness.argv('--verify-served'))
        self.assertEqual(result['own_mode'],'--verify-served')
        for name in ('getuid','geteuid'):
            with self.subTest(identity=name),patch.object(act.os,name,return_value=1001), \
                 self.assertRaisesRegex(act.Refusal,'own_controller_interval'):
                act.normal_controller_command(**options,read_bytes=lambda _:witness.argv('--verify-served'))
        with self.assertRaisesRegex(act.Refusal,'own_fixed_command'):
            act.normal_controller_command(**options,read_bytes=lambda _:witness.argv('--execute'))

    def test_created_directory_parent_fsync_failure_gets_STOP_and_collision_is_untouched(self):
        for fault in ('fsync','collision'):
            with self.subTest(fault=fault),tempfile.TemporaryDirectory() as directory:
                root=Path(directory);source,host,policy,complete,clock,paths,live=self.fixture(root)
                if fault=='fsync':
                    with patch.object(act.os,'fsync',side_effect=OSError('fictional one-time parent fsync failure')), \
                         self.assertRaisesRegex(act.Refusal,'stopped_preserving_records'):
                        self.run_verify(root,host,policy,complete,paths,live)
                    self.assertTrue((root/'verification').is_dir());self.assertIn('STOP.json',host.records)
                    self.assertFalse(host.records['STOP.json']['request_attempt_started']);self.assertNotIn('hold',host.events)
                else:
                    with patch.object(act.os,'mkdir',side_effect=FileExistsError('foreign collision')), \
                         self.assertRaises(FileExistsError):self.run_verify(root,host,policy,complete,paths,live)
                    self.assertFalse(host.records);self.assertFalse(host.events)

class ServedCollectorAndFrozenProofTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): ServedRenewalTests.setUpClass()

    def collector(self,fault=''):
        import inspect,subprocess
        tree=ast.parse(inspect.getsource(act.NativeHost.authenticated_gets).strip())
        code=next(n.value.value for n in ast.walk(tree) if isinstance(n,ast.Assign)
            and any(isinstance(t,ast.Name) and t.id=='code' for t in n.targets))
        original="const {request}=createRequire('/opt/meddoc-pro/package.json')('@playwright/test');"
        self.assertEqual(code.count(original),1)
        mock=r'''const trace=[];const fault=FAULT;let number=0;
const request={newContext:async options=>{trace.push({kind:'context',options});let saved=structuredClone(options.storageState);return {
 storageState:async()=>structuredClone(saved),dispose:async()=>trace.push({kind:'dispose'}),
 get:async(url,options)=>{const index=number++;trace.push({kind:'GET',url,options});if(fault==='timeout'&&index===0)throw Error('fictional timeout');
 saved.cookies[0].expires+=1;const text=index===0?'Clinical workspace A little less paperwork.':'Administration Workspace health. Release '+input.target;
 return {status:()=>fault==='redirect'&&index===0?302:200,url:()=>url,
 headers:()=>({'content-type':'text/html'}),body:async()=>Buffer.from(fault==='login'&&index===0?'<input name="password">':text)};}};}};
process.on('exit',()=>console.error(JSON.stringify(trace)));
'''.replace('FAULT',json.dumps(fault))
        states={actor:{'cookies':[{'name':'fictional-existing','value':actor,'expires':1800}], 'origins':[]}
                for actor in ('doctor','admin')}
        output=subprocess.run(['/usr/bin/node','--input-type=module','-e',code.replace(original,mock)],
            input=act.encode({'states':states,'target':TARGET}),capture_output=True,timeout=10)
        return output,json.loads(output.stdout),json.loads(output.stderr),states

    def test_actual_JS_collector_exact_two_GETs_and_real_state_intervals(self):
        result,report,trace,states=self.collector();self.assertEqual(result.returncode,0);self.assertTrue(report['complete'])
        gets=[item for item in trace if item['kind']=='GET'];self.assertEqual([item['url'] for item in gets],
            ['https://app.quillmd.com/','https://app.quillmd.com/console/services/'])
        for item in gets:self.assertEqual(item['options'],{'maxRedirects':0,'maxRetries':0,'timeout':15000,'failOnStatusCode':False})
        contexts=[item for item in trace if item['kind']=='context'];self.assertEqual(len(contexts),2)
        for item in contexts:self.assertFalse(item['options']['ignoreHTTPSErrors']);self.assertEqual(item['options']['timeout'],15000)
        self.assertEqual(len([item for item in trace if item['kind']=='dispose']),2)
        for attempt in report['attempts']:
            self.assertEqual(attempt['before'],states[attempt['actor']]);self.assertNotEqual(attempt['after'],attempt['before'])
            self.assertTrue(attempt['markers_verified']);self.assertEqual(attempt['GET_requests'],1)
            self.assertLessEqual(datetime.fromisoformat(attempt['started_at'].replace('Z','+00:00')),
                datetime.fromisoformat(attempt['finished_at'].replace('Z','+00:00')))
        self.assertNotIn('Clinical workspace',json.dumps(report))

    def test_actual_JS_redirect_login_and_unknown_timeout_stop_without_next_GET_or_retry(self):
        for fault in ('redirect','login','timeout'):
            with self.subTest(fault=fault):
                result,report,trace,_=self.collector(fault)
                self.assertEqual(result.returncode,2);self.assertFalse(report['complete'])
                self.assertEqual(len([item for item in trace if item['kind']=='GET']),1)
                self.assertEqual(len(report['attempts']),1);self.assertEqual(report['attempts'][0]['actor'],'doctor')
                self.assertIn('finished_at',report['attempts'][0]);self.assertEqual(report['failure'],'normal443_authenticated_served_GET_failed_or_unknown')

    def test_projection_admits_only_actual_full_post_maps_and_preserves_historical_reads(self):
        fixture=ServedRenewalTests();fixture.fixture();fixture.admit()
        projection=act.served_projection(fixture.before,fixture.after,ACTUAL_SERVED_RENEWAL_VERIFIER)
        module=SimpleNamespace(row_mapping=ACTUAL_SERVED_RENEWAL_VERIFIER.row_mapping)
        mapping=act.admitted_served_projection(module,projection)
        for table in ('django_session','core_auditevent'):
            packet=fixture.after[table]
            self.assertEqual(mapping(table,packet['rows'],packet['columns'],packet['primary_keys']),projection['projected_populations'][table])
            historical=fixture.before[table]
            self.assertEqual(mapping(table,historical['rows'],historical['columns'],historical['primary_keys']),
                ACTUAL_SERVED_RENEWAL_VERIFIER.row_mapping(table,historical['rows'],historical['columns'],historical['primary_keys']))
            drift=packet['rows']+[packet['rows'][-1].replace(b'\n',b'-foreign\n')]
            with self.assertRaises(act.ServedDeltaRefusal):mapping(table,drift,packet['columns'],packet['primary_keys'])
        bad=deepcopy(projection);bad['post_populations']['core_patient']={}
        with self.assertRaisesRegex(act.Refusal,'exact_two_table_projection'):act.admitted_served_projection(module,bad)

    def service_fixture(self):
        import types
        frozen=act.EVIDENCE/'recovery-20261007/acceptance-v3-preparation-v2-20261007/verify_installed_acceptance_v3.py'
        raw=frozen.read_bytes();self.assertEqual(act.sha(raw),act.FROZEN_V3)
        units={};proofs={};calls=[]
        for index,surface in enumerate(('doctor','admin','worker')):
            name='quillmd-fresh-'+surface+'.service';pid=str(100+index)
            units[name]={'ActiveState':'active','MainPID':pid,'ExecMainStartTimestampMonotonic':str(500+index),
                'FragmentPath':'/etc/systemd/system/'+name,'DropInPaths':''}
            proofs[surface+'.json']={'passed':True,'surface':surface,'release':TARGET,'pid':int(pid),
                'identity':{'all_capability_sets_empty':True,'no_new_privileges':True}}
        boundary={'units':units,'completion_unit_provenance':{'actual-new-starts':'verified'}}
        host=SimpleNamespace(served=PRIOR,operations=TARGET,boundary=MagicMock(return_value=deepcopy(boundary)))
        module=types.ModuleType('_fictional-genuine-normal-service-verifier');module.__file__=str(frozen)
        installed_unit=b'WorkingDirectory=/opt/meddoc-pro/rebuild\n'
        def run(argv):
            calls.append(argv)
            if argv[:4]==['git','-C','/opt/meddoc-pro','rev-parse']:return TARGET.encode()
            if argv[0]=='systemctl':return '\n'.join(key+'='+value for key,value in units[argv[2]].items()).encode()
            if argv[:4]==['git','-C','/opt/meddoc-pro','show']:return installed_unit
            raise AssertionError(argv)
        module.__dict__.update(v3_execution_gate=lambda:None,require=act.require,run=run,Path=Path,json=json,
            sha=act.sha,encoded=lambda value:act.encode(value)+b'\n',exact_native_cgroup=MagicMock())
        storage=SimpleNamespace(read_file=lambda _,name:act.encode(proofs[name]))
        def http_get(url,**_):
            if url.startswith('http://127.0.0.1:'):
                surface='doctor' if ':9130/' in url else 'admin'
                return SimpleNamespace(status_code=200,json=lambda:{'status':'ok','data_mode':'synthetic-only','surface':surface,'release':TARGET})
            return SimpleNamespace(status_code=503,headers={'retry-after':'3600','cache-control':'no-store'})
        return raw,module,host,{'units_after':boundary},storage,http_get,installed_unit,calls

    def test_actual_unchanged_frozen_service_algorithm_uses_new_PIDs_and_rejects_header_or_process_drift(self):
        raw,module,host,completion,storage,http_get,unit,calls=self.service_fixture()
        verify=act.normal_service_verifier(module,raw,host,completion)
        with patch('httpx.get',side_effect=http_get),patch.object(Path,'read_bytes',return_value=unit):
            result=verify(PRIOR,{'unused-private-activation':True},storage)
            self.assertEqual(result['current_served_revision'],TARGET);self.assertEqual(result['private_workflow_served_revision'],PRIOR)
            self.assertEqual(result['doctor']['pid'],100);self.assertEqual(host.boundary.call_count,2)
            with self.assertRaisesRegex(act.Refusal,'unchanged_private_workflow_release'):verify(TARGET,{},storage)
            host.boundary.return_value={'foreign-process':True}
            with self.assertRaisesRegex(act.Refusal,'same_actual_normal_services'):verify(PRIOR,{},storage)
        host.boundary.return_value=completion['units_after']
        def duplicate(url,**kwargs):
            value=http_get(url,**kwargs)
            if url.startswith('https://'):value.headers['retry-after']='3600, 3600'
            return value
        with patch('httpx.get',side_effect=duplicate),patch.object(Path,'read_bytes',return_value=unit), \
             self.assertRaisesRegex(act.Refusal,'Public maintenance'):verify(PRIOR,{},storage)
        template=(act.SOURCE/act.TEMPLATE).read_text()
        self.assertEqual(template.count('proxy_hide_header Cache-Control;'),1)
        self.assertEqual(template.count('proxy_hide_header Retry-After;'),1)
        with self.assertRaisesRegex(act.Refusal,'frozen_service_verifier_identity'):
            act.normal_service_verifier(module,raw+b'\n',host,completion)

    def test_inventory_original_pins_and_exact_target_metadata_bytes_remain_required(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);host=object.__new__(act.NativeHost);host.served=PRIOR;host.operations=TARGET
            host.check_hold=MagicMock();name='rebuild/core/preview_access.py';old=b'old-qualified';current=b'new-qualified'
            path=root/name;path.parent.mkdir(parents=True);path.write_bytes(current);path.chmod(0o644)
            host.buffers={name:current};host.git=lambda _,operation,pin:old if pin==PRIOR+':'+name else current
            with patch.object(act,'ROOT',root),patch.object(act,'APP',root/'rebuild'):
                self.assertTrue(host.installed_inventory(name,act.sha(old)))
                with self.assertRaisesRegex(act.Refusal,'immutable_private_inventory_path'):host.installed_inventory(name,act.sha(current))
                path.write_bytes(b'foreign changed bytes')
                with self.assertRaisesRegex(act.Refusal,'actual_cited_normal_application_path'):host.installed_inventory(name,act.sha(old))
                path.write_bytes(current);path.chmod(0o664)
                with self.assertRaisesRegex(act.source_files.Refusal,'operator_file_identity'):host.installed_inventory(name,act.sha(old))
                other=root/'rebuild/core/unchanged.py';other.write_bytes(b'unchanged')
                self.assertTrue(host.installed_inventory('rebuild/core/unchanged.py',act.sha(b'unchanged')))
                self.assertFalse(host.installed_inventory('rebuild/core/unchanged.py',act.sha(b'foreign')))

    def test_committed_policy_has_exact_separate_writes_and_fixed_paths(self):
        raw=(act.SOURCE/act.DECL).read_bytes();policy=act.contract(raw)
        self.assertEqual(policy['served_verification_policy'],act.SERVED_VERIFICATION_POLICY)
        self.assertEqual(policy['database_writes'],0)
        changed=raw.replace(b'"audit_rows_added": 1',b'"audit_rows_added": 0')
        with self.assertRaisesRegex(act.Refusal,'exact_separate_served_verification_policy'):act.contract(changed)

    def test_real_private_writer_and_nonce_refuse_replaced_output_directory_before_GET(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);output=root/'verification';output.mkdir(mode=0o700)
            host=object.__new__(act.NativeHost);info=output.stat()
            host.served_directory_identity=(info.st_dev,info.st_ino,info.st_uid,info.st_gid,info.st_mode&0o7777)
            host.check_hold=MagicMock();host.acceptance=SimpleNamespace(child_process=MagicMock(side_effect=AssertionError('GET launch')))
            host.source=act.SOURCE;host.operations=TARGET;host.forward_deadline=time.monotonic()+30
            with patch.object(act,'VERIFY_OUTPUT',output),patch.object(act,'VERIFY_ATTEMPT',root/'attempt.json'):
                host.verify_write('prepared.json',{'synthetic':True})
                self.assertEqual((output/'prepared.json').stat().st_mode&0o7777,0o600)
                self.assertEqual(json.loads((output/'prepared.json').read_bytes()),{'synthetic':True})
                with self.assertRaises(FileExistsError):host.verify_write('prepared.json',{'foreign':True})
                output.rename(root/'retained-original');output.mkdir(mode=0o700)
                for name in ('attempt.json','STOP.json','doctor-state-after.json'):
                    with self.subTest(name=name),self.assertRaisesRegex(act.Refusal,'same_owned_verification_directory'):
                        host.verify_write(name,{'foreign':True})
                with self.assertRaisesRegex(act.Refusal,'same_owned_verification_directory'):host.authenticated_gets({})
                host.acceptance.child_process.assert_not_called();self.assertFalse((root/'attempt.json').exists())
                self.assertEqual(list(output.iterdir()),[])
                self.assertEqual(json.loads((root/'retained-original/prepared.json').read_bytes()),{'synthetic':True})

    def test_immediate_pre_child_directory_reread_catches_late_replacement(self):
        host=object.__new__(act.NativeHost);host.check_hold=MagicMock()
        host.check_verification_directory=MagicMock(side_effect=[None,act.Refusal('normal443_same_owned_verification_directory')])
        host.acceptance=SimpleNamespace(child_process=MagicMock(side_effect=AssertionError('GET launch')))
        with self.assertRaisesRegex(act.Refusal,'same_owned_verification_directory'):host.authenticated_gets({})
        self.assertEqual(host.check_verification_directory.call_count,2);host.acceptance.child_process.assert_not_called()

    def test_foreign_boundary_delegates_only_to_checked_current_acceptance_without_recapture(self):
        host=object.__new__(act.NativeHost);host.served=PRIOR;declaration=b'unchanged original recovery declaration'
        host.check_hold=MagicMock()
        acknowledgement={'original-owner-decision':'retained-history'}
        host.buffers={act.RECOVERY_DECL:declaration};host.git=MagicMock(return_value=declaration)
        host.recovery=SimpleNamespace(DECL=act.RECOVERY_DECL,contract_from_bytes=MagicMock(return_value={
            'external_configuration_ack':acknowledgement}),
            loaded_external_state=MagicMock(side_effect=AssertionError('obsolete current reader')))
        proof={'configuration_admission':{'original_baseline_replaced':False,'current-exact-four':'future-bound'},
            'native_host_proof':{'actual-current':'measured'}}
        host.acceptance=SimpleNamespace(current_external_boundary=MagicMock(return_value=proof))
        self.assertEqual(host.foreign(),proof)
        host.acceptance.current_external_boundary.assert_called_once_with(host.recovery,acknowledgement)
        host.recovery.contract_from_bytes.assert_called_once_with(declaration)
        host.git.assert_called_once_with(act.ROOT,'show',PRIOR+':'+act.RECOVERY_DECL)
        host.recovery.loaded_external_state.assert_not_called()
        self.assertEqual(host.check_hold.call_count,2)
        host.acceptance.current_external_boundary=MagicMock(side_effect=act.Refusal('v3_current_configuration_owner_reply_required'))
        with self.assertRaisesRegex(act.Refusal,'current_configuration_owner_reply_required'):host.foreign()

    def test_foreign_unchecked_declaration_or_absent_current_function_refuses_without_fallback(self):
        host=object.__new__(act.NativeHost);host.served=PRIOR
        host.check_hold=MagicMock()
        host.buffers={};host.git=MagicMock(side_effect=AssertionError('Git read'))
        with self.assertRaisesRegex(act.Refusal,'checked_recovery_contract'):host.foreign()
        host.buffers={act.RECOVERY_DECL:b'original'};host.recovery=SimpleNamespace(DECL=act.RECOVERY_DECL,
            contract_from_bytes=MagicMock(return_value={'external_configuration_ack':{'retained':'original'}}))
        host.git=MagicMock(return_value=b'foreign')
        with self.assertRaisesRegex(act.Refusal,'recovery_declaration'):host.foreign()
        host.recovery.contract_from_bytes.assert_not_called()
        host.git.return_value=b'original';host.acceptance=SimpleNamespace()
        with self.assertRaisesRegex(act.Refusal,'checked_current_external_boundary'):host.foreign()

    def test_foreign_observation_requires_own_live_normal_controller_through_reread(self):
        host=object.__new__(act.NativeHost);host.served=PRIOR
        host.buffers={act.RECOVERY_DECL:b'original'};host.git=MagicMock(return_value=b'original')
        host.recovery=SimpleNamespace(DECL=act.RECOVERY_DECL,
            contract_from_bytes=lambda _: {'external_configuration_ack':{'retained':'original'}})
        observer=MagicMock(return_value={'voiceassist_actions':0})
        host.acceptance=SimpleNamespace(current_external_boundary=observer)
        host.check_hold=MagicMock(side_effect=act.Refusal('normal443_kernel_five_locks'))
        with self.assertRaisesRegex(act.Refusal,'kernel_five_locks'):host.foreign()
        observer.assert_not_called();host.git.assert_not_called()
        host.check_hold=MagicMock(side_effect=[None,act.Refusal('normal443_kernel_five_locks')])
        with self.assertRaisesRegex(act.Refusal,'kernel_five_locks'):host.foreign()
        observer.assert_called_once();self.assertEqual(host.check_hold.call_count,2)

if __name__=='__main__':unittest.main()
