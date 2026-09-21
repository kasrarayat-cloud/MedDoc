"""Narrow preserving activation adapter guards; no host/provider mutation."""
import copy
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from ops import source_module

ROOT = Path(__file__).resolve().parents[3]
a = source_module.load('business_activation_tested', ROOT / 'scripts/activate-business-readiness.py')
b = a.configured_driver()


class BusinessActivationTests(unittest.TestCase):
    def test_exact_driver_migration_and_historical_operations_are_pinned(self):
        self.assertEqual(a.sha((ROOT / a.DRIVER).read_bytes()), a.DRIVER_SHA256)
        a.validate_migration((ROOT / a.MIGRATION_PATH).read_bytes())
        with self.assertRaises(RuntimeError): a.validate_migration((ROOT / a.MIGRATION_PATH).read_bytes() + b'\n')
        actual = set(subprocess.check_output(['git','diff','--name-only',a.RUNNING_RELEASE,a.BASELINE,'--','rebuild'],cwd=ROOT,text=True).splitlines())
        self.assertEqual(actual,a.BASELINE_OPERATION_PATHS)
        self.assertFalse(any(name.startswith(('rebuild/core/','rebuild/templates/','rebuild/quillmd/')) for name in actual))

    def test_target_refuses_extra_runtime_settings_or_migration(self):
        paths=a.RUNTIME_ALLOWED | {a.DECL,'docs/rebuild/production-activation-checklist-20260921.md'}
        a.validate_changed(paths)
        for bad in (paths-{a.SELF},paths-{a.MIGRATION_PATH},paths-{a.DECL},paths|{'rebuild/quillmd/settings.py'},
                    paths|{'rebuild/ops/automatic_offsite.py'},paths|{'rebuild/core/migrations/0018_unreviewed.py'},paths|{'docs/rebuild/../outside.md'}):
            with self.subTest(paths=bad),self.assertRaises(RuntimeError):a.validate_changed(bad)

    def test_config_stamp_only_and_only0017_migration_plan(self):
        original=b'SYNTHETIC_TEST_VALUE=unchanged\nQUILLMD_RELEASE_SHA='+a.RUNNING_RELEASE.encode()+b'\n'
        self.assertEqual(b.updated_environment(original,'a'*40),b'SYNTHETIC_TEST_VALUE=unchanged\nQUILLMD_RELEASE_SHA="'+b'a'*40+b'"\n')
        plan='[X] core.'+a.PREVIOUS_MIGRATION+'\n[ ] core.'+a.MIGRATION
        b.verify_migration_plan(plan,applied=False)
        for bad in (plan+'\n[ ] core.0018_bad',plan+'\nunparsed'):
            with self.assertRaises(RuntimeError):b.verify_migration_plan(bad,applied=False)

    def snapshots(self):
        before={'schema':[{'table_name':'core_costreconciliation','column_name':'ledger_status','ordinal_position':13}],
                'constraints':[],'rows':{'core_costreconciliation':{'rows':0,'sha256':'original'}},
                'storage':{'files':'original'},'catalog':{'triggers':'original'},'indexes':['original'],
                'preserved_operations':{'ledger':'unchanged','ticket':'unchanged','timer':'unchanged'}}
        after=copy.deepcopy(before)
        after['schema'].append({'table_name':'core_costreconciliation','column_name':'evidence_kind','ordinal_position':14,
            'data_type':'character varying','udt_name':'varchar','is_nullable':'NO','column_default':None,
            'numeric_precision':None,'numeric_scale':None})
        after['constraints'].append(a.EXPECTED_CHECK)
        return before,after

    def test_only_exact_additive_schema_and_preserved_rows_files_operations_pass(self):
        before,after=self.snapshots();b.validate_after(before,after)
        for key in ('rows','storage','catalog','indexes','preserved_operations'):
            wrong=copy.deepcopy(after);wrong[key]='changed'
            with self.subTest(key=key),self.assertRaises(RuntimeError):b.validate_after(before,wrong)
        for key,value in (('column_default',"'invoice'"),('is_nullable','YES'),('data_type','text'),('ordinal_position',99)):
            wrong=copy.deepcopy(after);wrong['schema'][-1][key]=value
            with self.subTest(key=key),self.assertRaises(RuntimeError):b.validate_after(before,wrong)
        wrong=copy.deepcopy(after);wrong['constraints'].append(('unplanned','check','c','-','true'))
        with self.assertRaises(RuntimeError):b.validate_after(before,wrong)

    def test_row_projection_never_excludes_existing_financial_or_session_fields(self):
        old=SimpleNamespace(tables=lambda:['core_costreconciliation','core_user','core_usage','django_migrations'],PSQL=['fixture-psql'])
        with patch.object(a.subprocess,'check_output',return_value=b'{}\n') as query:a.rows(old,exclude_new=True)
        statements=[call.args[0][-1] for call in query.call_args_list]
        self.assertIn("to_jsonb(t) - 'evidence_kind'",statements[0])
        self.assertNotIn(' - ',statements[1]);self.assertNotIn(' - ',statements[2])
        self.assertIn("name='0017_reconciliation_evidence_kind'",statements[3]);self.assertNotIn('0016_',statements[3])

    def test_unclassified_values_and_varchar_length_are_measured(self):
        old=SimpleNamespace(PSQL=['fixture-psql'])
        with patch.object(b,'output',side_effect=['0','16']):a.verify_evidence_column(old)
        for values in (['1'],['0','15']):
            with patch.object(b,'output',side_effect=values),self.assertRaises(RuntimeError):a.verify_evidence_column(old)

    def test_receipt_does_not_claim_fresh_backup_or_session_migration(self):
        raw={'baseline':a.BASELINE,'stage':'apply_only_declared_session_generation','only_session_column_and_nonnegative_check_added':True}
        actual=a.receipt(raw)
        self.assertEqual(actual['stage'],'apply_only_declared_reconciliation_evidence_kind')
        self.assertTrue(actual['only_reconciliation_evidence_column_and_enum_check_added'])
        self.assertNotIn('only_session_column_and_nonnegative_check_added',actual)
        self.assertFalse(actual['fresh_backup_or_restore_performed'])
        self.assertIn('not asserted to cover current rows',actual['recovery_basis'])
        self.assertIn('only_session_column_and_nonnegative_check_added',raw)

    def test_root_action_is_fixed_and_uses_managed_cleanup_transport(self):
        helper=SimpleNamespace(IMAGE='sha256:'+'b'*64,run_helper=Mock())
        with patch.object(a,'managed',return_value=helper):
            a.managed_systemd('stop',helper.IMAGE)
            for action,image in (('restart',helper.IMAGE),('stop','sha256:'+'c'*64)):
                with self.assertRaises(RuntimeError):a.managed_systemd(action,image)
        call=helper.run_helper.call_args
        self.assertIn('--log-driver=none',call.args[0]);self.assertEqual(call.kwargs['timeout'],200)
        self.assertIn('quillmd-fresh-doctor.service',call.kwargs['input'].decode());self.assertNotIn('production',call.kwargs['input'].decode())
        self.assertEqual(call.kwargs['failure_directory'],a.EVIDENCE);self.assertEqual(helper.run_helper.call_count,1)

    def test_hash_helper_uses_bounded_transport_and_original_result_validation(self):
        helper=SimpleNamespace(IMAGE='sha256:'+'b'*64,run_helper=Mock(return_value=SimpleNamespace(returncode=0,stdout=json.dumps({
            '/etc/ssh/sshd_config':{'resolved':'/etc/ssh/sshd_config','sha256':'a'*64},
            '/etc/nginx/nginx.conf':{'resolved':'/etc/nginx/nginx.conf','sha256':'c'*64}}).encode())))
        with patch.object(a,'managed',return_value=helper):result=a.shared_configs(helper.IMAGE)
        self.assertEqual(len(result),2);call=helper.run_helper.call_args
        self.assertIn('--read-only',call.args[0]);self.assertIn('--log-driver=none',call.args[0]);self.assertEqual(call.kwargs['timeout'],60)

    def test_driver_routes_both_subprocess_channels_through_bytecode_guard(self):
        self.assertIs(b.run,a.run)
        self.assertIs(b.output,a.output)
        with patch.object(a,'_original_output',return_value='ok') as output:
            self.assertEqual(a.output(['synthetic-command'],env={'ONLY':'preserved'}),'ok')
            self.assertEqual(output.call_args.kwargs['env'],{'ONLY':'preserved','PYTHONDONTWRITEBYTECODE':'1'})

    def test_current_backup_helper_must_match_both_baseline_and_target(self):
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);path=root/'helper.py';path.write_text('qualified=True\n')
            with patch.object(a,'ROOT',root),patch.object(b,'blob',side_effect=lambda rev,rel:path.read_bytes() if rev==a.BASELINE else b'changed=True\n'):
                with self.assertRaises(RuntimeError):a.load('backup','helper.py','a'*40)

    def test_historical_capture_differences_are_recorded_not_claimed_current(self):
        from unittest.mock import MagicMock
        import psycopg
        manifest={'run_id':a.CAPTURE_RUN,'tables':{'core_usage':{'rows':1,'sha256':'historical'}},
                  'files':[{'path':'retained','sha256':'filehash','size':8}]}
        current={'core_usage':{'rows':2,'sha256':'current'}}
        backup=SimpleNamespace(source_options=Mock(return_value={}),fingerprint=Mock(return_value=current),
                               invariant_counts=Mock(return_value={'usage_multiplier':0}))
        modules={'old':SimpleNamespace(PSQL=['fixture-psql']),'backup':backup}
        storage={'retained':{'sha256':'filehash','size':8}}
        conn=MagicMock()
        with patch.object(b,'output',return_value='0'),patch.object(psycopg,'connect',return_value=conn),patch.object(a,'BACKUP_COMPARISONS',[]):
            a.assert_retained_backup(manifest,modules,storage)
            report=a.BACKUP_COMPARISONS[0]
            self.assertFalse(report['all_current_table_hashes_match_capture'])
            self.assertEqual(report['differing_tables'],['core_usage'])
            self.assertFalse(report['fresh_capture_performed'])
        before,after=self.snapshots();after['rows']={'new':'changed-current-row'}
        with self.assertRaises(RuntimeError):b.validate_after(before,after)
        with patch.object(b,'output',return_value='1'),patch.object(psycopg,'connect') as connect:
            with self.assertRaises(RuntimeError):a.assert_retained_backup(manifest,modules,storage)
            connect.assert_not_called()
        with patch.object(b,'output',return_value='0'),patch.object(psycopg,'connect') as connect:
            with self.assertRaises(RuntimeError):a.assert_retained_backup(manifest,modules,{'retained':{'sha256':'changed','size':8}})
            connect.assert_not_called()

    def test_driver_still_owns_stop_before_source_advance_and_failure_stop(self):
        import inspect
        source=inspect.getsource(b.main)
        self.assertLess(source.index("word.systemd('stop', helper)"),source.index("run(['git', 'merge', '--ff-only'"))
        self.assertIn("declaration.read_bytes() == blob(args.target, DECL) == blob(commit, DECL)",source)
        self.assertIn("scripts/check-citation.sh",source)
        self.assertIn("identity.verify_live(args.target, storage)",source)
        self.assertIn("except BaseException as error",source)
        self.assertEqual(source.count("word.systemd('stop', helper)"),2)
        self.assertIs(b.assert_backup_current,a.assert_retained_backup)
        self.assertIs(b.verify_session_versions,a.verify_evidence_column)

    def test_recovery_policy_retains_evidence_schema_and_current_history(self):
        import io,tarfile
        stream=io.BytesIO()
        with tarfile.open(fileobj=stream,mode='w') as bundle:
            data=b'# harmless fixture\n';entry=tarfile.TarInfo('rebuild/manage.py');entry.size=len(data);bundle.addfile(entry,io.BytesIO(data))
        result=a.retained_source_manifest(stream.getvalue())
        self.assertEqual(result['commit'],a.BASELINE)
        self.assertIn('Retain0017',' '.join(result['recovery_policy']));self.assertIn('does not include every later row',' '.join(result['recovery_policy']))


if __name__=='__main__':unittest.main()
