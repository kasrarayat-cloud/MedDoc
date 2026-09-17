import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from . import sdk_sandbox as sandbox


class SdkNativeBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.workspace = self.root / 'workspace'; self.workspace.mkdir(mode=0o700)
        self.runtime = self.root / 'runtime'; self.runtime.mkdir(mode=0o700)
        self.canary = self.root / 'outside'; self.canary.write_text('SYNTHETIC CONTROL')
        self.canary.chmod(0o600)

    def test_clone_mask_only_allows_threads_with_required_shared_memory(self):
        self.assertTrue(sandbox.clone_allowed(sandbox.CLONE_REQUIRED))
        self.assertTrue(sandbox.clone_allowed(sandbox.CLONE_ALLOWED))
        for flags in (0, 17, sandbox.CLONE_REQUIRED | 17, sandbox.CLONE_ALLOWED | 0x10000000,
                      sandbox.CLONE_ALLOWED | 0x20000000, sandbox.CLONE_ALLOWED | 0x40000000,
                      sandbox.CLONE_ALLOWED | 0x8000000000000000):
            with self.subTest(flags=flags):
                self.assertFalse(sandbox.clone_allowed(flags))
        for required in (0x100, 0x800, 0x10000):
            self.assertFalse(sandbox.clone_allowed(sandbox.CLONE_ALLOWED & ~required))

    def test_clean_environment_does_not_inherit_application_keys_or_runtime_hooks(self):
        os.environ['SYNTHETIC_PROVIDER_KEY'] = 'test-only'
        self.addCleanup(os.environ.pop, 'SYNTHETIC_PROVIDER_KEY', None)
        result = sandbox.clean_environment(self.workspace)
        self.assertNotIn('SYNTHETIC_PROVIDER_KEY', result)
        self.assertNotIn('LD_PRELOAD', result)
        self.assertNotIn('DOTNET_STARTUP_HOOKS', result)
        self.assertEqual(result['DOTNET_EnableDiagnostics'], '0')
        self.assertEqual(result['DOTNET_GCHeapHardLimit'], '10000000')

    def test_managed_process_cannot_select_qualification_mode(self):
        argv = ['sdk_sandbox.py', '--runtime', str(self.runtime), '--manifest', str(self.root / 'manifest'),
                '--manifest-sha', 'a' * 64, '--workspace', str(self.workspace), '--qualification']
        with patch('sys.argv', argv), patch.dict(os.environ, {'QUILLMD_ENV_MANAGED': '1',
                      'QUILLMD_WORD_QUALIFICATION': '1'}), patch.object(sandbox, 'verified_runtime') as verify:
            with self.assertRaisesRegex(RuntimeError, 'Managed service'):
                sandbox.main()
        verify.assert_not_called()

    def manifest(self):
        for name in ('ProbeHost', 'libcoreclr.so', 'System.Private.CoreLib.dll'):
            path = self.runtime / name
            path.write_bytes(b'SYNTHETIC runtime fixture ' + name.encode())
            path.chmod(0o700 if name == 'ProbeHost' else 0o600)
        files = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in self.runtime.iterdir()}
        payload = json.dumps({'format': 1, 'runtime': 'dotnet8-self-contained-linux-x64',
                              'executable': 'ProbeHost', 'files': files}).encode()
        path = self.root / 'runtime-manifest.json'; path.write_bytes(payload)
        return path, hashlib.sha256(payload).hexdigest()

    def test_pinned_runtime_rejects_modified_or_extra_file_and_unpinned_manifest(self):
        path, expected = self.manifest()
        self.assertEqual(sandbox.verified_runtime(self.runtime, path, expected, qualification=True).name, 'ProbeHost')
        with self.assertRaises(RuntimeError):
            sandbox.verified_runtime(self.runtime, path, expected)
        with self.assertRaises(RuntimeError):
            sandbox.verified_runtime(self.runtime, path, '0' * 64, qualification=True)
        (self.runtime / 'extra.so').write_bytes(b'SYNTHETIC')
        with self.assertRaises(RuntimeError):
            sandbox.verified_runtime(self.runtime, path, expected, qualification=True)
        (self.runtime / 'extra.so').unlink()
        (self.runtime / 'libcoreclr.so').write_bytes(b'changed')
        with self.assertRaises(RuntimeError):
            sandbox.verified_runtime(self.runtime, path, expected, qualification=True)

    def test_runtime_rejects_symlinks_even_to_same_bytes(self):
        path, expected = self.manifest()
        target = self.runtime / 'libcoreclr.so'
        content = self.root / 'outside-library'; content.write_bytes(target.read_bytes())
        target.unlink(); target.symlink_to(content)
        with self.assertRaises(RuntimeError):
            sandbox.verified_runtime(self.runtime, path, expected, qualification=True)

    def test_actual_kernel_policy_denies_secrets_network_forks_and_foreign_signals(self):
        # Execute only in a fresh child: Landlock and seccomp are irreversible.
        module_dir = str(Path(sandbox.__file__).resolve().parent)
        code = r'''
import ctypes,errno,json,os,sys,threading
sys.path.insert(0,sys.argv[1]);import sdk_sandbox
workspace,runtime,canary=sys.argv[2:5]
assert open(canary).read()=='SYNTHETIC CONTROL'
parent=os.getppid();libc=ctypes.CDLL(None,use_errno=True)
sdk_sandbox.isolate(workspace,runtime)
results={}
try: open(canary).read();results['outside_denied']=False
except PermissionError: results['outside_denied']=True
try: open('/etc/passwd').read();results['passwd_denied']=False
except PermissionError: results['passwd_denied']=True
fd=libc.socket(2,1,0);results['socket_denied']=fd==-1 and ctypes.get_errno()==errno.EPERM
if fd>=0:os.close(fd)
try:
 child=os.fork()
 if child==0:os._exit(88)
 os.waitpid(child,0);results['fork_denied']=False
except PermissionError:results['fork_denied']=True
ctypes.set_errno(0);result=libc.syscall(435,0,0)
results['clone3_enosys']=result==-1 and ctypes.get_errno()==errno.ENOSYS
ctypes.set_errno(0);result=libc.syscall(29,0,0,0)
results['sysv_ipc_denied']=result==-1 and ctypes.get_errno()==errno.EPERM
libc.mmap.restype=ctypes.c_void_p
libc.mmap.argtypes=[ctypes.c_void_p,ctypes.c_size_t,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_long]
ctypes.set_errno(0);mapped=libc.mmap(None,600*1024*1024,3,0x22,-1,0)
results['native_private_allocation_bounded']=mapped==ctypes.c_void_p(-1).value and ctypes.get_errno()==errno.ENOMEM
if mapped!=ctypes.c_void_p(-1).value:
 libc.munmap.argtypes=[ctypes.c_void_p,ctypes.c_size_t];libc.munmap(mapped,600*1024*1024)
ctypes.set_errno(0);result=libc.syscall(234,parent,parent,0)
results['foreign_thread_signal_denied']=result==-1 and ctypes.get_errno()==errno.EPERM
results['own_thread_signal_permitted']=libc.syscall(234,os.getpid(),os.getpid(),0)==0
def work():
 try:open(canary).read();results['new_thread_denied']=False
 except PermissionError:results['new_thread_denied']=True
thread=threading.Thread(target=work);thread.start();thread.join()
with open(workspace+'/allowed','w') as output:output.write('SYNTHETIC')
results['workspace_write']=True
print(json.dumps(results))
'''
        result = subprocess.run([sys.executable, '-I', '-B', '-c', code, module_dir,
                                 str(self.workspace), str(self.runtime), str(self.canary)],
                                capture_output=True, text=True, timeout=15, check=False,
                                env={'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8'})
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(len(report), 11)
        self.assertTrue(all(report.values()), report)

    def test_refuses_native_boundary_when_thread_already_exists(self):
        module_dir = str(Path(sandbox.__file__).resolve().parent)
        code = r'''
import sys,threading
sys.path.insert(0,sys.argv[1]);import sdk_sandbox
event=threading.Event();worker=threading.Thread(target=event.wait);worker.start()
try:
 try:sdk_sandbox.isolate(sys.argv[2],sys.argv[3]);raise AssertionError('accepted existing thread')
 except RuntimeError as error:assert 'before any CLR' in str(error)
finally:event.set();worker.join()
'''
        result = subprocess.run([sys.executable, '-I', '-B', '-c', code, module_dir,
                                 str(self.workspace), str(self.runtime)], capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
