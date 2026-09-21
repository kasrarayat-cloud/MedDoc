"""Provider-free permission/bytecode/failure resume guards using disposable files."""
import copy
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from ops import source_module

ROOT=Path(__file__).resolve().parents[3]
r=source_module.load('business_recovery_tested',ROOT/'scripts/resume-business-readiness.py')
a=r.a;b=r.b

class RecoveryTests(unittest.TestCase):
 def test_actual_git_ff_with_restrictive_caller_umask_keeps_runtime_readable(self):
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory)
   def git(*args):return subprocess.check_output(['git',*args],cwd=root,stderr=subprocess.DEVNULL,text=True).strip()
   git('init','-b','main');git('config','user.email','fixture@synthetic.invalid');git('config','user.name','Synthetic activation fixture')
   (root/'runtime.py').write_text('original=1\n');git('add','runtime.py');git('commit','-m','initial')
   git('checkout','-b','candidate');(root/'runtime.py').write_text('changed=2\n');(root/'added.py').write_text('new=3\n');git('add','.');git('commit','-m','candidate');target=git('rev-parse','HEAD');git('checkout','main')
   secret=root/'.env';secret.write_text('synthetic-only');secret.chmod(0o600)
   previous=os.umask(0o077)
   try:
    a.run(['git','merge','--ff-only',target],cwd=root,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    self.assertEqual(os.umask(0o077),0o077)
    self.assertEqual(stat.S_IMODE((root/'runtime.py').stat().st_mode),0o644)
    self.assertEqual(stat.S_IMODE((root/'added.py').stat().st_mode),0o644)
    self.assertEqual(stat.S_IMODE(secret.stat().st_mode),0o600)
   finally:os.umask(previous)

 def test_git_failure_restores_original_umask(self):
  previous=os.umask(0o077)
  try:
   with patch.object(a,'_original_run',side_effect=RuntimeError('fixture')):
    with self.assertRaises(RuntimeError):a.run(['git','merge','--ff-only','a'*40])
   self.assertEqual(os.umask(0o077),0o077)
  finally:os.umask(previous)

 def test_both_management_channels_preserve_no_bytecode_through_execve(self):
  code="import os,sys;os.execve(sys.executable,[sys.executable,'-c','import os,sys;print(str(sys.dont_write_bytecode)+\":\"+os.environ.get(\"PYTHONDONTWRITEBYTECODE\",\"missing\"))'],dict(os.environ))"
  command=[sys.executable,'-B','-c',code]
  self.assertEqual(a.output(command),'True:1')
  actual=a.run(command,capture_output=True,text=True)
  self.assertEqual(actual.stdout.strip(),'True:1')

 def fixture_sources(self,root):
  specs={}
  for name in r.CHANGED_RUNTIME:
   path=root/name;path.parent.mkdir(parents=True,exist_ok=True);data=('synthetic '+name).encode();path.write_bytes(data);path.chmod(0o600)
   specs[name]={'sha256':hashlib.sha256(data).hexdigest(),'mode':0o644}
  return specs

 def test_exact_mode_repair_preserves_bytes_and_refuses_wrong_hash_or_population(self):
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory);specs=self.fixture_sources(root)
   result=r.repair_modes(root,specs,execute=True)
   self.assertEqual(len(result),14);self.assertTrue(all(x['after_mode']=='0o644' for x in result.values()))
   bad=copy.deepcopy(specs);bad.pop(next(iter(bad)))
   with self.assertRaises(RuntimeError):r.repair_modes(root,bad,execute=True)
   name=next(iter(specs));(root/name).write_bytes(b'replaced')
   with self.assertRaises(RuntimeError):r.repair_modes(root,specs,execute=True)

 def test_mode_repair_refuses_symlink_and_hardlink(self):
  for kind in ('symlink','hardlink'):
   with self.subTest(kind=kind),tempfile.TemporaryDirectory() as directory:
    root=Path(directory);specs=self.fixture_sources(root);name=next(iter(specs));path=root/name;other=root/'other';other.write_bytes(path.read_bytes());other.chmod(0o600)
    if kind=='symlink':path.unlink();path.symlink_to(other)
    else:os.link(path,root/'extra-link')
    with self.assertRaises(RuntimeError):r.repair_modes(root,specs,execute=True)

 def fixture_caches(self,root):
  self.fixture_sources(root);specs={}
  for name in r.CACHE_SOURCES:
   source=root/name;path=source.parent/'__pycache__'/(source.stem+'.cpython-312.pyc');path.parent.mkdir(exist_ok=True);path.parent.chmod(0o700)
   data=('synthetic compiler cache '+name).encode();path.write_bytes(data);path.chmod(0o600);info=path.stat()
   specs[str(path.relative_to(root))]={'source':name,'source_sha256':r.sha(source.read_bytes()),'sha256':r.sha(data),
    'uid':os.getuid(),'gid':info.st_gid,'mode':'0600','size':len(data),'mtime_ns':info.st_mtime_ns}
  return specs

 def test_only_six_exact_caches_removed_other_private_file_preserved(self):
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory);specs=self.fixture_caches(root);sentinel=root/'unrelated.pyc';sentinel.write_bytes(b'unrelated')
   report=r.cleanup_caches(root,specs,execute=True)
   self.assertEqual(len(report),6);self.assertTrue(all(x['removed'] for x in report.values()))
   self.assertEqual(sentinel.read_bytes(),b'unrelated');self.assertTrue(all((root/x['source']).exists() for x in specs.values()))

 def test_cache_cleanup_refuses_replacement_symlink_hardlink_foreign_metadata(self):
  for kind in ('replaced','symlink','hardlink','owner','source'):
   with self.subTest(kind=kind),tempfile.TemporaryDirectory() as directory:
    root=Path(directory);specs=self.fixture_caches(root);name=sorted(specs)[0];path=root/name
    if kind=='replaced':path.write_bytes(b'not the observed cache')
    elif kind=='symlink':other=root/'other';other.write_bytes(path.read_bytes());path.unlink();path.symlink_to(other)
    elif kind=='hardlink':os.link(path,root/'extra-link')
    elif kind=='owner':specs[name]['uid']=os.getuid()+1
    else:(root/specs[name]['source']).write_bytes(b'new source')
    with self.assertRaises((RuntimeError,OSError)):r.cleanup_caches(root,specs,execute=True)
    self.assertTrue(path.exists())

 def test_stopped_state_json_normalization_preserves_values_not_just_types(self):
  expected={'constraints':[['table','check']],'rows':{'wallet':'preserved'},'operations':{'budget':'old'}}
  actual={'constraints':[('table','check')],'rows':{'wallet':'preserved'},'operations':{'budget':'old'}}
  r.equal_stopped(expected,actual)
  for key in ('rows','operations'):
   bad=copy.deepcopy(actual);bad[key]={'changed':True}
   with self.assertRaises(RuntimeError):r.equal_stopped(expected,bad)

 def test_duplicate_or_absent_projected_migration_history_is_rejected(self):
  from types import SimpleNamespace
  old=SimpleNamespace(PSQL=['fixture-psql'])
  with patch.object(r.b,'output',side_effect=['1','0','16']):r.verify_applied_once(old)
  for count in ('0','2'):
   with patch.object(r.b,'output',return_value=count),patch.object(r.a,'verify_evidence_column') as verify:
    with self.assertRaises(RuntimeError):r.verify_applied_once(old)
    verify.assert_not_called()

 def test_recovery_scope_refuses_migration_application_or_configuration_edits(self):
  r.validate_recovery_paths(r.RECOVERY_ALLOWED)
  for extra in ('rebuild/core/models.py','rebuild/core/migrations/0017_reconciliation_evidence_kind.py','rebuild/ops/with_db_role.py','rebuild/.env','docs/rebuild/../escape.md'):
   with self.subTest(path=extra),self.assertRaises(RuntimeError):r.validate_recovery_paths(r.RECOVERY_ALLOWED|{extra})

if __name__=='__main__':unittest.main()
