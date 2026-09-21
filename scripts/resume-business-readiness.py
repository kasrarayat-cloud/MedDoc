#!/usr/bin/env python3
"""Resume only the authenticated post0017/source-permission activation failure.

No remigration, backup, provider call, generic chmod, data restore or automatic
retry. Default is read-only; execution needs a new exact merged/cited declaration.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import time
import types

ROOT=Path('/opt/meddoc-pro')
SOURCE=Path(__file__).resolve().parents[1]
SELF='scripts/resume-business-readiness.py'
ADAPTER='scripts/activate-business-readiness.py'
DECL='docs/foundation/mutations/20260921-quillmd-business-activation-recovery.md'
FAILED='4944cc906b67d08d3ea48b77e3bbbdab4086817c'
ORIGINAL_ADAPTER_SHA='0b2bb746ea3b7e5001d1da951d85ef4af8190c9c95836ac638949bb393ad4777'
PRIVATE=ROOT/'rebuild/.runtime'
EVIDENCE=PRIVATE/'business-readiness-20260921'
FAILURE=EVIDENCE/'private-readiness-activation-4944cc906b67.json'
FAILURE_SHA='1a88f5cf61596f395312cbdbaebbdc8f9117e82fd0f9486ecc7f4a03d5a25e69'
ORIGINAL_LOCK=PRIVATE/'.private-readiness-activation.lock'
ORIGINAL_LOCK_SHA='09c4d6a4b3f164944e280ccc2ab22348c20d22771c1f54ab247de9db9ca1e488'
CACHE_INVENTORY=EVIDENCE/'failed-activation-cache-inventory.json'
CACHE_INVENTORY_SHA='b4a8d4f1c6868f6bddc4e476a1d8c181832400d4036bf845f74d72d6be329329'
CACHE_SOURCES={'rebuild/core/'+name+'.py' for name in ('billing','forms','models','stripe_validation','views')} | {'rebuild/core/migrations/0017_reconciliation_evidence_kind.py'}
CHANGED_RUNTIME={
 'rebuild/core/billing.py','rebuild/core/forms.py','rebuild/core/management/commands/audit_billing.py',
 'rebuild/core/migrations/0017_reconciliation_evidence_kind.py','rebuild/core/models.py',
 'rebuild/core/stripe_validation.py','rebuild/core/tests/test_billing_policy.py',
 'rebuild/core/tests/test_business_activation.py','rebuild/core/tests/test_reconciliation_evidence_kind.py',
 'rebuild/core/tests/test_stripe_environment.py','rebuild/core/views.py',
 'rebuild/templates/admin_dashboard.html','rebuild/templates/billing.html','rebuild/templates/financial_detail.html',
}
RECOVERY_ALLOWED={SELF,ADAPTER,DECL,'rebuild/core/tests/test_business_activation.py',
                  'rebuild/core/tests/test_business_activation_recovery.py'}

def require(value,message):
 if not value:raise RuntimeError(message)

def sha(data):return hashlib.sha256(data).hexdigest()

def canonical(value):return json.loads(json.dumps(value,sort_keys=True))

def source_module(name,path):
 module=types.ModuleType(name);module.__file__=str(path);sys.modules[name]=module
 exec(compile(path.read_bytes(),str(path),'exec'),module.__dict__);return module

a=source_module('_business_resume_adapter',SOURCE/ADAPTER)
b=a.configured_driver()

def validate_failure(raw,lock):
 require(sha(raw)==FAILURE_SHA and sha(lock)==ORIGINAL_LOCK_SHA,'Original failure or lock differs.')
 failure=json.loads(raw);held=json.loads(lock)
 require(failure.get('complete') is False and failure.get('target')==FAILED
  and failure.get('stage')=='apply_only_declared_reconciliation_evidence_kind'
  and failure.get('failure_kind')=='RuntimeError' and failure.get('failure_services_stopped') is True
  and failure.get('served_before')==a.RUNNING_RELEASE and failure.get('stopped_after_migration')
  and 'proofs_after' not in failure and held.get('target')==FAILED
  and type(held.get('pid')) is int and held['pid']>0,'Only the recorded pre-restart failure can resume.')
 require({p for p in failure['changed_paths'] if p.startswith('rebuild/')}==CHANGED_RUNTIME,'Repair population differs.')
 before=canonical(failure['stopped_before']);after=canonical(failure['stopped_after_migration'])
 before['constraints']=[tuple(x) for x in before['constraints']];after['constraints']=[tuple(x) for x in after['constraints']]
 b.validate_after(before,after)
 return failure,held

def validate_recovery_paths(changed):
 require(RECOVERY_ALLOWED<=changed and all(p in RECOVERY_ALLOWED or
  (p.startswith('docs/rebuild/') and p.endswith('.md') and '..' not in Path(p).parts) for p in changed),
  'Recovery changes exceed the exact permission/resume/test scope.')

def target_file_specs():
 specs={}
 for relative in sorted(CHANGED_RUNTIME):
  row=b.git('ls-tree',FAILED,'--',relative).split()
  require(len(row)==4 and row[0]=='100644' and row[1]=='blob' and row[3]==relative,
          'Every affected runtime file must be a regular nonexecutable tracked blob.')
  specs[relative]={'sha256':sha(b.blob(FAILED,relative)),'mode':0o644}
 return specs

def repair_modes(root,specs,*,execute=False):
 require(set(specs)==CHANGED_RUNTIME,'Permission repair must name the exact14 affected source files.')
 result={}
 for relative,spec in sorted(specs.items()):
  path=root/relative
  require(path.resolve()==path and path.parent.resolve()==path.parent,'Repair path is not canonical.')
  fd=os.open(path,os.O_RDONLY|os.O_CLOEXEC|os.O_NOFOLLOW)
  try:
   info=os.fstat(fd)
   require(stat.S_ISREG(info.st_mode) and info.st_nlink==1 and info.st_uid==os.getuid()
    and stat.S_IMODE(info.st_mode) in (0o600,0o644) and spec['mode']==0o644,
    'Repair requires owned single-link source with only the recorded mode defect.')
   digest=hashlib.sha256()
   while data:=os.read(fd,65536):digest.update(data)
   require(digest.hexdigest()==spec['sha256'],'Source changed before permission repair.')
   if execute:os.fchmod(fd,0o644)
   after=os.fstat(fd)
   require((after.st_dev,after.st_ino,after.st_uid,after.st_gid,after.st_nlink,after.st_size)==
     (info.st_dev,info.st_ino,info.st_uid,info.st_gid,info.st_nlink,info.st_size),'Repair file identity changed.')
   require(not execute or stat.S_IMODE(after.st_mode)==0o644,'Permission repair failed.')
   result[relative]={'sha256':digest.hexdigest(),'before_mode':oct(stat.S_IMODE(info.st_mode)),
                    'after_mode':oct(stat.S_IMODE(after.st_mode)),'content_unchanged':True}
  finally:os.close(fd)
 return result

def cache_specs(raw):
 require(sha(raw)==CACHE_INVENTORY_SHA,'Task cache inventory changed.')
 rows=json.loads(raw)['files']
 require(type(rows) is dict and len(rows)==6 and {item['source'] for item in rows.values()}==CACHE_SOURCES,
         'Only the six measured management caches are eligible.')
 for relative,item in rows.items():
  source=Path(item['source'])
  require(relative==str(source.parent/'__pycache__'/(source.stem+'.cpython-312.pyc'))
   and item['source'] in CHANGED_RUNTIME and item['mode']=='0600'
   and re.fullmatch('[a-f0-9]{64}',item['sha256']) and re.fullmatch('[a-f0-9]{64}',item['source_sha256']),
   'Cache/source relationship differs.')
 return rows

def cleanup_caches(root,specs,*,execute=False):
 require(len(specs)==6 and {item['source'] for item in specs.values()}==CACHE_SOURCES,
         'Cache cleanup population differs.')
 result={}
 for relative,item in sorted(specs.items()):
  source=root/item['source'];path=root/relative
  expected=source.parent/'__pycache__'/(source.stem+'.cpython-312.pyc')
  require(source.resolve()==source and path==expected and path.resolve()==path,
          'Cache path is not the exact canonical source cache.')
  require(sha(source.read_bytes())==item['source_sha256'],'Cache source bytes differ.')
  parent=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
  fd=None
  try:
   parent_info=os.fstat(parent)
   require(parent_info.st_uid==os.getuid() and not stat.S_IMODE(parent_info.st_mode)&0o002,
           'Cache directory must remain operator-owned and not world writable.')
   fd=os.open(path.name,os.O_RDONLY|os.O_CLOEXEC|os.O_NOFOLLOW,dir_fd=parent);info=os.fstat(fd)
   require(stat.S_ISREG(info.st_mode) and info.st_nlink==1 and info.st_uid==item['uid']==os.getuid()
    and info.st_gid==item['gid'] and stat.S_IMODE(info.st_mode)==0o600 and info.st_size==item['size']
    and info.st_mtime_ns==item['mtime_ns'],'Cache metadata differs from the retained failed attempt.')
   digest=hashlib.sha256()
   while data:=os.read(fd,65536):digest.update(data)
   require(digest.hexdigest()==item['sha256'],'Cache contents changed after inspection.')
   current=os.stat(path.name,dir_fd=parent,follow_symlinks=False)
   require((current.st_dev,current.st_ino,current.st_mtime_ns,current.st_size)==
    (info.st_dev,info.st_ino,info.st_mtime_ns,info.st_size),'Cache replaced during cleanup.')
   if execute:
    os.unlink(path.name,dir_fd=parent);os.fsync(parent)
    require(not path.exists() and not path.is_symlink(),'Cache removal not confirmed.')
   result[relative]={'sha256':item['sha256'],'source':item['source'],'removed':execute}
  finally:
   if fd is not None:os.close(fd)
   os.close(parent)
 return result


def verify_applied_once(old):
 require(b.output(old.PSQL+["SELECT count(*) FROM django_migrations WHERE app='core' AND name='0017_reconciliation_evidence_kind'"])=='1',
         'Exactly one retained0017 migration-history row is required.')
 a.verify_evidence_column(old)


def state_now(modules,helper):
 result=a.snapshot(modules,helper);result['rows']=a.rows(modules['old'],exclude_new=True)
 return canonical(result)

def equal_stopped(expected,actual):
 require(canonical(expected)==canonical(actual),'Current database/files/catalog/config/timer/accounting differ from the recorded stopped state.')

def retire_original_lock(word,state):
 original=word.checked_file(ORIGINAL_LOCK,private=True)
 require(sha(original)==ORIGINAL_LOCK_SHA,'Original lock changed before retirement.')
 info=ORIGINAL_LOCK.lstat();path=state/'original-failed-lock.json'
 fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
 with os.fdopen(fd,'wb') as stream:stream.write(original);stream.flush();os.fsync(stream.fileno())
 require(path.read_bytes()==original,'Failed lock evidence was not retained.')
 current=ORIGINAL_LOCK.lstat()
 require((current.st_dev,current.st_ino)==(info.st_dev,info.st_ino)
  and ORIGINAL_LOCK.read_bytes()==original,'Original lock identity changed during retirement.')
 ORIGINAL_LOCK.unlink();require(not ORIGINAL_LOCK.exists(),'Original failed lock remains active.')
 return {'retained_at':str(path),'sha256':ORIGINAL_LOCK_SHA,'active_lock_removed':True}

def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--target',required=True)
 parser.add_argument('--result',required=True);parser.add_argument('--execute',action='store_true');args=parser.parse_args()
 require(re.fullmatch('[a-f0-9]{40}',args.target) and SOURCE.is_relative_to(ROOT/'.worktrees') and SOURCE.resolve()==SOURCE,
         'Exact target and retained reviewed worktree required.')
 require(b.git('rev-parse','HEAD')==FAILED and b.git('branch','--show-current')=='main'
  and b.git('rev-parse','origin/main')==args.target and not b.git('status','--porcelain','--untracked-files=no'),
  'Shared main must remain clean at the failed target.')
 b.run(['git','merge-base','--is-ancestor',FAILED,args.target],cwd=ROOT)
 changed=set(b.git('diff','--name-only',FAILED,args.target).splitlines());validate_recovery_paths(changed)
 require((SOURCE/SELF).read_bytes()==b.blob(args.target,SELF)
  and (SOURCE/ADAPTER).read_bytes()==b.blob(args.target,ADAPTER)
  and sha(b.blob(FAILED,ADAPTER))==ORIGINAL_ADAPTER_SHA,'Recovery/adapter source identity differs.')
 pulls=json.loads(b.output(['gh','api',f'repos/kasrarayat-cloud/MedDoc/commits/{args.target}/pulls']))
 require(any(p.get('merged_at') and p.get('merge_commit_sha')==args.target and p.get('base',{}).get('ref')=='main' for p in pulls),'Exact merged recovery PR required.')
 b.run(['bash',str(ROOT/'scripts/check-citation.sh'),args.target],cwd=ROOT)
 modules={name:a.load(name,relative,args.target) for name,relative in b.HELPERS.items()}
 old,word,identity,storage,previous=(modules[k] for k in ('old','word','identity','storage','previous'))
 failure,held=validate_failure(word.checked_file(FAILURE,private=True),word.checked_file(ORIGINAL_LOCK,private=True))
 require(not Path('/proc',str(held['pid'])).exists(),'Original activation PID still exists; do not take over.')
 b.stopped();a.validate_migration((ROOT/a.MIGRATION_PATH).read_bytes())
 b.verify_migration_plan(b.output(b.management('showmigrations','--plan'),cwd=b.APP),applied=True)
 verify_applied_once(old)
 require(b.output(old.PSQL+["SELECT count(*) FROM core_job WHERE state IN ('queued','running','reconciliation')"])=='0','Unresolved job appeared.')
 helper=json.loads(word.checked_file(PRIVATE/'word-beta-recovery-20260917-final.json',private=True))['helper_image']
 require(helper==a.managed().IMAGE and b.output(['docker','image','inspect',helper,'--format','{{.Id}}'])==helper,'Qualified helper unavailable.')
 before=state_now(modules,helper);equal_stopped(failure['stopped_after_migration'],before)
 original=word.checked_file(b.APP/'.env',private=True)
 require(sha(original)==failure['environment_before_sha256'],'Original release/integration environment changed.')
 updated=b.updated_environment(original,args.target);protected=previous.protected()
 inputs=word.expected_inputs(args.target);require(inputs==word.expected_inputs(FAILED),'Word SDK input changed.')
 installed=b.APP/'.word-sdk'/modules['billing'].SDK_RELEASE
 artifact=word.verify_artifact(installed/'runtime',installed/'runtime-manifest.json',installed/'build-proof.json',modules['billing'].PIN,inputs)
 specs=target_file_specs();modes=repair_modes(ROOT,specs)
 caches=cache_specs(word.checked_file(CACHE_INVENTORY,private=True));cache_before=cleanup_caches(ROOT,caches)
 result_path=Path(args.result);state=EVIDENCE/('recovery-state-'+args.target[:12]);lock=PRIVATE/'.business-readiness-recovery.lock'
 require(result_path.is_absolute() and result_path.resolve()==result_path and result_path.parent==EVIDENCE
  and re.fullmatch(r'business-readiness-recovery-[a-zA-Z0-9_-]+\.json',result_path.name)
  and not any(p.exists() or p.is_symlink() for p in (result_path,state,lock)), 'Unused recovery result/state/lock required.')
 b.run(['bash',str(ROOT/'scripts/check-cotenants.sh')],cwd=ROOT)
 print('Read-only pinned recovery checks passed; original failure and all stopped state preserved.',flush=True)
 if not args.execute:return
 declaration=Path(os.environ.get('RULED_MUTATION_DECLARATION',''));commit=os.environ.get('RULED_MUTATION_DECL_COMMIT','')
 require(declaration==SOURCE/DECL and declaration.resolve()==declaration and re.fullmatch('[a-f0-9]{40}',commit)
  and declaration.read_bytes()==b.blob(args.target,DECL)==b.blob(commit,DECL),'Exact committed recovery declaration required.')
 b.run(['git','merge-base','--is-ancestor',commit,args.target],cwd=ROOT)
 identity.private_write(lock,{'target':args.target,'pid':os.getpid(),'failed_target':FAILED});state.mkdir(mode=0o700)
 result={'complete':False,'failed_target':FAILED,'target':args.target,'original_failure':str(FAILURE),
  'original_failure_sha256':FAILURE_SHA,'original_lock_sha256':ORIGINAL_LOCK_SHA,
  'started_at':datetime.now(timezone.utc).isoformat(),'provider_calls':0,'fresh_backup_or_restore_performed':False,
  'migration_executed':False,'stopped_before':before,'modes_before':modes,'caches_before':cache_before,'cache_inventory_sha256':CACHE_INVENTORY_SHA,'stage':'repair_exact_source_permissions'}
 phase=0
 def checkpoint(stage):
  nonlocal phase
  result['stage']=stage;identity.private_write(state/f'phase-{phase:02d}.json',result);phase+=1
 try:
  checkpoint('repair_exact_source_permissions');b.stopped()
  equal_stopped(before,state_now(modules,helper))
  require(word.checked_file(b.APP/'.env',private=True)==original,'Environment changed before repair.')
  result['modes_repaired']=repair_modes(ROOT,specs,execute=True)
  result['task_caches_removed']=cleanup_caches(ROOT,caches,execute=True)
  result['source_readability_before_ff']=identity.source_readability(helper)
  checkpoint('advance_stopped_recovery_source');b.stopped()
  a.run(['git','merge','--ff-only',args.target],cwd=ROOT,stdout=subprocess.DEVNULL)
  require(b.git('rev-parse','HEAD')==args.target and not b.git('status','--porcelain','--untracked-files=no'),'Recovery source advance differs.')
  result['source_readability_after_ff']=identity.source_readability(helper)
  b.verify_migration_plan(b.output(b.management('showmigrations','--plan'),cwd=b.APP),applied=True)
  verify_applied_once(old);equal_stopped(before,state_now(modules,helper))
  b.run(b.management('check'),cwd=b.APP,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
  checkpoint('stamp_release_only');modules['env'].replace_environment(b.APP/'.env',original,updated)
  checkpoint('start_exact_private_release');word.systemd('start',helper)
  for _ in range(45):
   try:live=b.health(args.target);break
   except (subprocess.CalledProcessError,json.JSONDecodeError,RuntimeError):time.sleep(1)
  else:raise RuntimeError('Recovered private application did not become healthy.')
  result['proofs_after']=identity.verify_live(args.target,storage);result['interfaces_after']=identity.verify_interfaces()
  worker=old.worker_process();require(worker['systemd_start']!=failure['worker_before']['systemd_start']
   and worker['kernel_start_utc']>failure['worker_before']['kernel_start_utc'],'Worker restart lacks actual process proof.')
  result['worker_after']=worker;result['health']=live
  after=state_now(modules,helper);equal_stopped(before,after);verify_applied_once(old)
  require(word.checked_file(b.APP/'.env',private=True)==updated and previous.protected()==protected,'Release/configuration/protected services changed.')
  require(word.verify_artifact(installed/'runtime',installed/'runtime-manifest.json',installed/'build-proof.json',modules['billing'].PIN,inputs)==artifact,'Word artifact changed.')
  b.run(['bash',str(ROOT/'scripts/check-cotenants.sh')],cwd=ROOT)
  require(sha(word.checked_file(FAILURE,private=True))==FAILURE_SHA,'Original failed result changed.')
  result['stopped_state_preserved_after_restart']=after;checkpoint('retire_verified_failed_locks')
  result['original_lock_retirement']=retire_original_lock(word,state)
  lock.unlink();require(not lock.exists(),'Recovery lock cleanup failed.')
  result.update(complete=True,stage='complete',finished_at=datetime.now(timezone.utc).isoformat(),
    existing_rows_files_catalog_units_controls_unchanged=True,original_failure_preserved=True,only_exact_source_modes_repaired=True,only_six_recorded_caches_removed=True)
  checkpoint('complete');identity.private_write(result_path,result)
 except BaseException as error:
  result.update(complete=False,failure_kind=type(error).__name__,finished_at=datetime.now(timezone.utc).isoformat())
  try:word.systemd('stop',helper);b.stopped();result['failure_services_stopped']=True
  except BaseException as stop_error:result['failure_services_stopped']=False;result['stop_failure_kind']=type(stop_error).__name__
  identity.private_write(result_path,result)
  raise RuntimeError('Recovery failed closed; inspect preserved evidence before another declared act.') from None
 print('Private recovery verified; original failure retained: '+str(result_path),flush=True)

if __name__=='__main__':main()
