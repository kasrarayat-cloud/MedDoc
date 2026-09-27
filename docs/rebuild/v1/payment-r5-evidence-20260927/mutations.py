"""Bounded R5 proofs: mutate only a scratch billing copy, restore SHA256, retain every attempt."""
import hashlib,json,subprocess,sys
from pathlib import Path
root=Path('/opt/meddoc-pro/.worktrees/v1-blockers/rebuild')
scratch=Path(__file__).resolve().parent
source=root/'core/billing.py'
original=source.read_bytes()
before=hashlib.sha256(original).hexdigest()
target=scratch/'billing-copy.py'
target.write_bytes(original)
module='core.tests.test_v1_payment_refutation_r5'
financial=module+'.PaymentBehaviorPins.'
guards=module+'.GuardDefinitionPins.'
replication=module+'.RuntimeReplicationPins.'
refusal="""    if real_mode_refuses(wallet):
        audit(actor,'usage.reconciliation_sandbox_refused',row.usage.job_id,department=row.usage.department,wallet=str(wallet.pk),
              charge_delta=str(row.charge_delta))
        return False
    if wallet.balance-wallet.reserved<row.charge_delta: return False
"""
mutants=[
 ('r5-1-refuse-live-money','    if real_mode_refuses(wallet):\n','    if real_data_mode():\n',financial+'test_live_funded_real_mode_reconciliation_collects_the_supported_difference'),
 ('r5-3-ignore-organization',"field={'user':'user_id','organization':'organization_id'}.get(scope)","field={'user':'user_id'}.get(scope)",financial+'test_an_organization_payers_sandbox_money_refuses_a_promotional_hold_before_the_worker_sends'),
 ('r5-4-check-balance-before-audit',refusal,"    if wallet.balance-wallet.reserved<row.charge_delta: return False\n"+refusal.removesuffix('    if wallet.balance-wallet.reserved<row.charge_delta: return False\n'),financial+'test_each_sandbox_reconciliation_refusal_is_audited_even_when_available_balance_is_short'),
 ('r5-2-ignore-definition',' and definition==expected','',guards+'test_an_update_column_list_cannot_narrow_the_payment_guard'),
 ('r5-2-ignore-function-schema',' and namespace==schema','',guards+'test_the_same_function_name_and_body_in_another_schema_is_not_the_installed_function'),
 ('r5-2-ignore-function-body','and hashlib.sha256(body.encode()).hexdigest()==PAYMENT_GUARD_FUNCTION_SHA256[function]','and True',guards+'test_replacing_each_guard_function_body_with_a_noop_is_reported'),
 ('r5-2-ignore-extra-triggers','        if extra: failed.append(', '        if False: failed.append(',guards+'test_extra_before_and_after_row_triggers_are_reported_without_printing_their_names'),
 ('r5-2-ignore-current-replication',"if replication!='origin' or default is not None and default[0]!='origin':", "if default is not None and default[0]!='origin':",replication+'test_current_replication_mode_must_be_origin'),
 ('r5-2-ignore-persistent-replication',"if replication!='origin' or default is not None and default[0]!='origin':", "if replication!='origin':",replication+'test_persistent_defaults_are_checked_for_the_database_and_runtime_role'),
 ('r5-2-inspect-login-instead-of-runtime-role','rolname=current_user','rolname=session_user',replication+'test_set_role_does_not_hide_the_runtime_roles_persistent_replication_mode'),
]

def run(name,label):
    result=subprocess.run([sys.executable,'-B',str(scratch/'mutation-tests.py'),label],cwd=root,capture_output=True,text=True,timeout=180)
    output=result.stdout+'\n'+result.stderr
    (scratch/(name+'.txt')).write_text(output)
    return result.returncode,output

baseline,output=run('mutation-baseline',module)
assert baseline==0,output
print('baseline:',baseline,'11 tests pass',flush=True)
results=[]
for name,old,new,label in mutants:
    text=original.decode()
    assert text.count(old)==1,(name,text.count(old))
    changed=text.replace(old,new)
    try:
        target.write_text(changed)
        assert target.read_text()==changed and target.read_bytes()!=original
        code,output=run(name,label)
        killed=code!=0 and 'FAIL:' in output and 'FAILED (failures=' in output and 'ERROR:' not in output
        results.append({'name':name,'exit_code':code,'killed':killed})
        print(name,'applied:',True,'killed:',killed,'exit:',code,flush=True)
    finally:
        target.write_bytes(original)
        restored=hashlib.sha256(target.read_bytes()).hexdigest()==before
        print('restored:',restored,before,flush=True)
        assert restored
    assert killed,name
assert hashlib.sha256(source.read_bytes()).hexdigest()==before
print('worktree untouched:',True,flush=True)
(scratch/'mutation-summary.json').write_text(json.dumps({'source_sha256':before,'baseline_tests':11,'mutants':results,'worktree_untouched':True},indent=2)+'\n')
