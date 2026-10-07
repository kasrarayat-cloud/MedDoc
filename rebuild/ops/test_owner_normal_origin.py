"""Focused fictional controls; no installed state or provider/login action."""
import ast
from contextlib import contextmanager
from copy import deepcopy
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
        self.preservation=MagicMock(return_value={'full_original_and_new_records_verified':True})
        self.full_preservation=self.preservation
        self.routes=MagicMock(return_value={'https://app.quillmd.com':503})
    @contextmanager
    def hold(self):
        self.events.append('five-locks-held');yield;self.events.append('five-locks-released')
    def check(self,*a): pass
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
    def test_default_and_unqualified_execute_never_read_or_act(self):
        with patch.object(act.source_files,'protected',side_effect=AssertionError('installed read')), \
             patch.object(act.old,'git',side_effect=AssertionError('Git read')),patch('sys.stdout',new=io.StringIO()):
            self.assertEqual(act.main([]),0)
            for mode in ('--execute','--preflight'):
                with self.assertRaisesRegex(act.Refusal,'source_protocol_unqualified'):
                    act.main([mode,'--operations-revision',TARGET])
        self.assertFalse(act.ACTIVE_PROTOCOL_QUALIFIED);self.assertFalse(act.PRIVATE_ACCEPTANCE_QUALIFIED)
        self.assertFalse(act.INGRESS_PUBLICATION_QUALIFIED)
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
    def test_execute_is_one_forward_transition_of_own_services_then_one_file(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);_,host,policy=self.fixture(root)
            result=self.run_transition(root,host,policy,True)
            self.assertTrue(result['complete']);self.assertEqual(result['served_revision'],TARGET)
            self.assertEqual(host.events[1:4],['stop:worker','stop:admin','stop:doctor'])
            self.assertLess(host.events.index('fast-forward'),host.events.index('start:doctor'))
            self.assertLess(host.events.index('start:worker'),host.events.index('only-quillmd-ingress'))
            self.assertEqual(host.events.count('fast-forward'),1)
            self.assertEqual(set(host.records),{'environment-before.fernet','environment-enabled.fernet','environment-disabled.fernet',
                'original-ingress.conf','prepared.json','attempt','complete.json'})
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
    def test_native_constructor_cannot_be_opened_by_a_policy_flag(self):
        with patch.object(act,'private_receipts',side_effect=AssertionError('private input')):
            with self.assertRaisesRegex(act.Refusal,'source_protocol_unqualified'):
                act.NativeHost({'active_protocol_qualified':True},TARGET,{},0)
    def test_source_gate_authenticates_each_dependency_and_exact_intermediate_operations_scope(self):
        policy={'private_accepted_revision':PRIOR,**{key:True for key in (
            'active_protocol_qualified','private_acceptance_qualified','ingress_publication_qualified')}}
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
        health={'id':b'fictional-uuid','created_at':b'original','key':b'backup'}
        original={str(i):{} for i in range(35)}
        original['core_servicehealth']={'columns':list(health),'rows':[b'fictional COPY row']}
        full={'id':'fictional-uuid','all_eleven_fields':'source-verified-fictional'}
        host.verifier=SimpleNamespace(original_continuation_capture=lambda *_:(None,None,{'tables':{'django_session':{'rows':212}}},original),
            row_mapping=lambda *_:{'fictional-uuid':dict(health)},service_health_original=lambda _:full)
        host.publisher_admission=MagicMock(return_value={'current_full_row':full})
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
        module.protected=lambda *args:(_ for _ in ()).throw(AssertionError('installed read'))
        verify,namespace=act.memory_verifier(module)
        self.assertIs(namespace['v3_execution_gate'],gate)
        with self.assertRaisesRegex(act.Refusal,'source_protocol_unqualified'):
            verify(SimpleNamespace(progress='unused',output=None))
        self.assertEqual(act.sha(path.read_bytes()),act.FROZEN_V3)
        module.__dict__['__authenticated_source']=raw+b'\n# counterexample'
        with self.assertRaisesRegex(act.Refusal,'frozen_verifier_hash'):act.memory_verifier(module)


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
            real_read=Path.read_bytes
            try:
                for name in names:
                    fd=os.open(root/name,os.O_RDWR|os.O_CREAT|os.O_EXCL,0o600);fds.append(fd)
                    fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB);info=os.fstat(fd)
                    host.lock_rows.append({'path':str(root/name),'fd':fd,'device':info.st_dev,'inode':info.st_ino})
                def observed(path):
                    return self.argv() if str(path)==f'/proc/{os.getpid()}/cmdline' else real_read(path)
                with patch.object(act,'RUNTIME',root),patch.object(Path,'read_bytes',observed):
                    self.assertTrue(host.check_hold()['same_five_kernel_locks_verified'])
                    fcntl.flock(fds[-1],fcntl.LOCK_UN)
                    with self.assertRaisesRegex(act.Refusal,'kernel_five_locks'):host.check_hold()
                    fcntl.flock(fds[-1],fcntl.LOCK_EX|fcntl.LOCK_NB)
                    (root/names[-1]).rename(root/'detached-actual-lock')
                    (root/names[-1]).write_bytes(b'foreign replacement')
                    with self.assertRaisesRegex(act.Refusal,'kernel_five_locks'):host.check_hold()
            finally:
                for fd in fds:os.close(fd)

if __name__=='__main__':unittest.main()
