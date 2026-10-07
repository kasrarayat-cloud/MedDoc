"""Fictional offline controls. No installed/auth/provider/DB/service access."""
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch
import copy
import fcntl
import io
import json
import os
import socket
import subprocess
import sys
import stat
import tempfile
import types
import unittest
import zipfile

from ops import owner_acceptance_v3 as v3

OPS = '1' * 40
SERVED = '2' * 40
COMMIT = '3' * 40
START = datetime(2026, 10, 7, 12, 0, tzinfo=timezone.utc)


def contract():
    return {'format': 3, 'origin': v3.ORIGIN, 'approved_source_paths': sorted(v3.ALLOWED),
            'source_base': v3.M6, 'dependency_sha256': v3.DEPENDENCIES,
            'maximum_generations': 5, 'maximum_transcriptions': 1, 'maximum_provider_exposure': '0.70',
            'concurrency': 1, 'provider_retries': 0, 'authentication_seconds': 180,
            'browser_verifier_seconds': 1200, 'operations_revision': None,
            'operations_revision_policy': v3.OPERATIONS_REVISION_POLICY, 'served_revision': SERVED,
            'protocol_qualified': True}


def declaration(value=None):
    return b'<!-- owner-acceptance-v3-contract -->\n```json\n' + v3.encode(value or contract()) + b'\n```\n'


class FakeHost:
    """Invented source/phase instrument, never native lock or installation proof."""
    source = v3.ROOT / '.worktrees/fictional-v3'
    environment = {'RULED_MUTATION_DECLARATION': v3.DECL, 'RULED_MUTATION_DECL_COMMIT': COMMIT}

    def __init__(self):
        self.events = []; self.inside = False; self.now = 0; self.fail_phase = None
        self.changed = sorted(v3.ALLOWED); self.served = SERVED; self.ops = OPS
        self.contract = contract()

    def canonical(self, path): return path
    def read_source(self, path): return declaration(self.contract) if str(path).endswith(v3.DECL) else b'fictional tracked bytes'
    def readability(self, path): self.events.append(('readability', str(path)))
    def git(self, tree, *args):
        if args == ('rev-parse', 'HEAD'): return (self.ops if tree == self.source else self.served).encode() + b'\n'
        if args == ('rev-parse', 'origin/main'): return self.ops.encode() + b'\n'
        if args == ('branch', '--show-current'): return b'main\n'
        if args[:1] == ('status',): return b''
        if args[:1] == ('merge-base',): return b''
        if args[:1] == ('diff',): return '\n'.join(self.changed).encode()
        if args[:1] == ('log',): return COMMIT.encode() + b'\n'
        if args[:1] == ('ls-files',): return b'rebuild/core/generation.py\n'
        if args[:1] == ('show',): return declaration(self.contract) if args[1].endswith(':' + v3.DECL) else b'fictional tracked bytes'
        raise AssertionError(args)
    def citation(self, revision): self.events.append(('citation', revision))
    def authenticate_dependencies(self): self.events.append('dependencies')
    def authenticate_availability(self, *args): self.events.append('availability'); return {'complete': True}
    def fresh_paths_absent(self): return True
    def clock(self): self.now += .01; return self.now
    @contextmanager
    def exclusions(self, *args):
        self.inside = True; self.events.append('locks-enter')
        try: yield
        finally: self.events.append('locks-exit'); self.inside = False
    def recheck_source_and_idle(self, *args):
        assert self.inside; self.events.append('inside-source-idle')
    def admit(self, phase, *args):
        assert self.inside; self.events.append(phase); return {'complete': True}
    def create_exclusive_preparation(self, *args): assert self.inside; self.events.append('exclusive-preparation')
    def child(self, phase, operations, served, deadline):
        assert self.inside; self.events.append((phase, deadline))
        if phase == self.fail_phase: raise v3.Refusal('fictional failed child')
    def normal_auth_evidence(self): return {'fictional': True}
    def write_attempt(self, *args): assert self.inside; self.events.append('attempt')
    def independent_report(self): return {'complete': True, 'operations_revision': OPS, 'served_revision': SERVED}
    def write_complete(self, *args): assert self.inside; self.events.append('complete')
    def write_stop(self, *args): assert self.inside; self.events.append('STOP')


def docx(values):
    from lxml import etree
    ns = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
    root = etree.Element('{%s}document' % ns, nsmap={'w': ns}); body = etree.SubElement(root, '{%s}body' % ns)
    table = etree.SubElement(body, '{%s}tbl' % ns)
    for label, answer in values.items():
        row = etree.SubElement(table, '{%s}tr' % ns)
        for text in (label, answer):
            cell = etree.SubElement(row, '{%s}tc' % ns); para = etree.SubElement(cell, '{%s}p' % ns)
            run = etree.SubElement(para, '{%s}r' % ns); etree.SubElement(run, '{%s}t' % ns).text = text
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w') as archive:
        archive.writestr('word/document.xml', etree.tostring(root))
        archive.writestr('word/header1.xml', b'unchanged fictional letterhead')
    return stream.getvalue()


class InertAndSourceTests(unittest.TestCase):
    def test_default_and_every_real_entry_refuse_before_io(self):
        with (patch.object(v3, 'protected', side_effect=AssertionError('installed read')),
              patch.object(socket, 'create_connection', side_effect=AssertionError('network')),
              patch.object(subprocess, 'Popen', side_effect=AssertionError('child'))):
            with patch('sys.stdout', new=io.StringIO()) as stream:
                self.assertEqual(v3.main([]), 0)
                self.assertFalse(json.loads(stream.getvalue())['installed_state_accessed'])
            for mode in ('execute', 'preflight', 'admit-before-auth', 'admit-after-auth', 'verify',
                         'dispatch-normal-auth', 'dispatch-browser', 'child-check-normal-auth', 'child-check-browser'):
                with self.subTest(mode=mode), self.assertRaisesRegex(v3.Refusal, 'source_protocol_unqualified'):
                    v3.main(['--' + mode, '--operations-revision', OPS, '--served-revision', SERVED])
            with self.assertRaises(v3.Refusal): v3.InstalledHost()

    def test_declaration_flags_cannot_enable_source_gate(self):
        with patch.dict(os.environ, {'V3_EXECUTION_QUALIFIED': '1'}):
            for _ in (False, True):
                with self.assertRaises(v3.Refusal): v3.execution_gate()
        self.assertFalse(v3.EXECUTION_QUALIFIED)
        self.assertFalse(v3.NATIVE_AUTHORIZATION_PROTOCOL_QUALIFIED)
        self.assertFalse(v3.FIXED_CHILD_PROTOCOL_QUALIFIED)

    def test_installed_collectors_refuse_before_roles_key_socket_or_db(self):
        with patch.object(v3, 'frozen_modules', side_effect=AssertionError('source read')), \
             patch.object(socket, 'create_connection', side_effect=AssertionError('socket')) as sock:
            for call in (lambda: v3.installed_database_admission({}), v3.installed_auth_packet):
                with self.assertRaises(v3.Refusal): call()
            self.assertEqual(sock.call_count, 0)

    def test_default_native_locks_and_child_refuse_before_os_calls(self):
        with (patch.object(os, 'open', side_effect=AssertionError('installed lock')),
              patch.object(subprocess, 'Popen', side_effect=AssertionError('native child'))):
            with self.assertRaises(v3.Refusal):
                with v3.existing_operation_locks(): pass
            with self.assertRaises(v3.Refusal):
                v3.child_process(['arbitrary'], FakeHost.source, Path('/fictional'), 'child', 20, ruled=True)

    def test_exact_contract_bounds_and_duplicate_refuse(self):
        self.assertEqual(v3.declaration_contract(declaration()), contract())
        for key, value in [('maximum_generations', 6), ('maximum_provider_exposure', '1'),
                           ('provider_retries', 1), ('concurrency', 2), ('browser_verifier_seconds', 2400),
                           ('approved_source_paths', sorted(v3.ALLOWED) + ['rebuild/core/generation.py'])]:
            bad = contract(); bad[key] = value
            with self.subTest(key=key), self.assertRaises(v3.Refusal): v3.declaration_contract(declaration(bad))
        with self.assertRaises(v3.Refusal): v3.declaration_contract(declaration() * 2)

    def test_separate_source_revisions_and_exact_citations(self):
        host = FakeHost(); result = v3.source_gate(host, contract(), OPS, SERVED, host.environment)
        self.assertEqual(result['operations_revision'], OPS); self.assertEqual(result['served_revision'], SERVED)
        self.assertEqual([row[1] for row in host.events if isinstance(row, tuple) and row[0] == 'citation'], [v3.M6, OPS, SERVED])
        for mutate in (lambda host: setattr(host, 'served', OPS), lambda host: setattr(host, 'changed', list(v3.ALLOWED) + ['rebuild/core/generation.py'])):
            host = FakeHost(); mutate(host)
            with self.assertRaises(v3.Refusal): v3.source_gate(host, contract(), OPS, SERVED, host.environment)
        for value in ('1' * 8, '1' * 40 + ' ', 'f' * 39):
            with self.assertRaises(v3.Refusal): v3.full_revision(value)
        with self.assertRaises(v3.Refusal): v3.source_gate(FakeHost(), contract(), OPS, SERVED, {})

    def normal_descendant_host(self):
        target='4'*40
        class NormalHost(FakeHost):
            def __init__(self):
                super().__init__();self.contract['availability_receipt_sha256']='5'*64
                self.normal_changes=set(v3.NORMAL_ALLOWED);self.normal_source_drift=False
                self.normal_policy={'format':1,'source_base':OPS,'private_accepted_revision':SERVED,
                    'approved_source_paths':sorted(v3.NORMAL_ALLOWED),
                    'availability':{'path':str(v3.AVAILABILITY/'complete.json'),'sha256':'5'*64},
                    'origin':'https://app.quillmd.com','private_origin':v3.ORIGIN,
                    'ingress_path':'/etc/nginx/sites-available/quillmd',
                    'original_ingress_sha256':'ff7320480fe823cbc1564e3c104ee41bac1dd5e1336f8772274af36a541a7a0a',
                    'private_ingress_sha256':'cbc81159b1505fd566625062517bb18dd8d4706cd30b0e334e7fdceec659f21a',
                    'caddy_sha256':'bf0c14729a4ae86ecf2e8ff34d9b5e68aeba55a0bb0c06879580bc73e3a23c87',
                    'runtime_receipt_binding_protocol':v3.NORMAL_RUNTIME_BINDING,'private_acceptance_completed':False,
                    'active_protocol_qualified':True,'private_acceptance_protocol_qualified':True,
                    'ingress_publication_qualified':True,'authentication_submissions':0,'provider_calls':0,
                    'database_writes':0,'automatic_retries':False,'outer_ceiling_seconds':2400,
                    'session_forward_reserve_seconds':600,'session_completion_reserve_seconds':60}
                for name,path in [('private_acceptance',v3.CAMPAIGN/'complete.json'),('private_report',v3.REPORT),
                                  ('private_authority',v3.PREPARATION/'parent-phase-verify.json')]:
                    self.normal_policy[name]={'path':str(path),'binding':v3.NORMAL_RUNTIME_BINDING}
                self.normal_module=("BASE="+repr(OPS)+"\nRUNTIME_BINDING="+repr(v3.NORMAL_RUNTIME_BINDING)+
                    "\nACTIVE_PROTOCOL_QUALIFIED=True\nPRIVATE_ACCEPTANCE_PROTOCOL_QUALIFIED=True\nINGRESS_PUBLICATION_QUALIFIED=True\n").encode()
            def git(self,tree,*args):
                if args==('rev-parse','origin/main'):return target.encode()+b'\n'
                if args[:3]==('diff','--name-only',OPS):return '\n'.join(sorted(self.normal_changes)).encode()
                if args[:1]==('show',):
                    revision,relative=args[1].split(':',1)
                    if relative==v3.NORMAL_DECL:return b'<!-- owner-normal443-contract -->\n```json\n'+v3.encode(self.normal_policy)+b'\n```'
                    if revision==target and relative==v3.NORMAL_SELF:return self.normal_module
                    if revision==target and relative=='rebuild/core/preview_access.py':return b'OWNER_NORMAL_ORIGIN_PROTOCOL_QUALIFIED=True\n'
                    if revision==target and relative=='rebuild/quillmd/settings.py':return b"QUILLMD_OWNER_NORMAL_ORIGIN_ENABLED=os.getenv('QUILLMD_OWNER_NORMAL_ORIGIN_ENABLED', '0') == '1'\n"
                    if revision==target and self.normal_source_drift and relative==v3.SELF:return b'changed used acceptance bytes'
                return super().git(tree,*args)
        return NormalHost(),target

    def test_only_exact_cited_normal_descendant_prospective_contract_is_admitted(self):
        host,target=self.normal_descendant_host()
        result=v3.source_gate(host,host.contract,OPS,SERVED,host.environment)
        self.assertEqual(result['merged_main']['revision'],target)
        self.assertFalse(result['merged_main']['private_acceptance_completed_claimed'])
        self.assertIn(('citation',target),host.events)
        changes=[lambda h:h.normal_changes.add('rebuild/core/generation.py'),
            lambda h:h.normal_changes.remove(v3.NORMAL_SELF),lambda h:setattr(h,'normal_source_drift',True),
            lambda h:setattr(h,'served',OPS),lambda h:h.normal_policy.update(source_base='6'*40),
            lambda h:h.normal_policy.update(private_accepted_revision=OPS),
            lambda h:h.normal_policy.update(runtime_receipt_binding_protocol='trust_future_success'),
            lambda h:h.normal_policy.update(private_acceptance_completed=True),
            lambda h:h.normal_policy.update(active_protocol_qualified=False),
            lambda h:h.normal_policy.update(private_acceptance_protocol_qualified=False),
            lambda h:h.normal_policy.update(ingress_publication_qualified=False),
            lambda h:h.normal_policy['availability'].update(sha256='6'*64),
            lambda h:h.normal_policy['private_report'].update(path='/elsewhere/report.json'),
            lambda h:h.normal_policy['private_acceptance'].update(binding='future-unbound-receipt'),
            lambda h:setattr(h,'normal_module',h.normal_module.replace(b'ACTIVE_PROTOCOL_QUALIFIED=True',b'ACTIVE_PROTOCOL_QUALIFIED=False')),
            lambda h:setattr(h,'normal_module',h.normal_module.replace(OPS.encode(),('6'*40).encode()))]
        for position,change in enumerate(changes):
            bad,_=self.normal_descendant_host();change(bad)
            with self.subTest(counterexample=position),self.assertRaises(v3.Refusal):
                v3.source_gate(bad,bad.contract,OPS,SERVED,bad.environment)
        bad,_=self.normal_descendant_host()
        bad.citation=lambda revision:v3.require(revision!=target,'fictional_missing_exact_target_citation')
        with self.assertRaisesRegex(v3.Refusal,'target_citation'):
            v3.source_gate(bad,bad.contract,OPS,SERVED,bad.environment)
        bad,_=self.normal_descendant_host();original_git=bad.git;observations=[]
        def moving_main(tree,*args):
            if args==('rev-parse','origin/main'):
                observations.append(True)
                if len(observations)>1:return ('7'*40).encode()+b'\n'
            return original_git(tree,*args)
        bad.git=moving_main
        with self.assertRaisesRegex(v3.Refusal,'unchanged_during_source_admission'):
            v3.source_gate(bad,bad.contract,OPS,SERVED,bad.environment)

    def test_genuine_git_normal_descendant_scope_ancestry_and_installed_revision_controls(self):
        """Real disposable Git trees; fictional citation callback never claims CI."""
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/'installed';root.mkdir()
            def git(tree,*args):
                return subprocess.run(['/usr/bin/git','-C',str(tree),*args],check=True,
                    capture_output=True,timeout=15).stdout
            def write(tree,relative,raw):
                path=tree/relative;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw);path.chmod(0o644)
            git(root,'init','-b','main');git(root,'config','user.name','Fictional offline control')
            git(root,'config','user.email','fictional@example.invalid')
            for relative in v3.USED_SOURCE|v3.NORMAL_ALLOWED:write(root,relative,b'fictional original bytes\n')
            git(root,'add','.');git(root,'commit','-m','Fictional served baseline')
            served=git(root,'rev-parse','HEAD').strip().decode()
            source=root/'.worktrees/operations';normal=root/'.worktrees/normal'
            git(root,'worktree','add','-b','fictional-operations',str(source),served)
            host,_=self.normal_descendant_host();policy=host.normal_policy
            current=host.contract;current.update(source_base=served,served_revision=served)
            for relative in v3.ALLOWED:write(source,relative,b'fictional changed operations\n')
            write(source,v3.DECL,declaration(current));git(source,'add','.');git(source,'commit','-m','Fictional acceptance operations')
            operations=git(source,'rev-parse','HEAD').strip().decode()
            git(root,'worktree','add','-b','fictional-normal',str(normal),operations)
            for relative in v3.NORMAL_ALLOWED:write(normal,relative,b'fictional prospective normal bytes\n')
            policy.update(source_base=operations,private_accepted_revision=served)
            write(normal,v3.NORMAL_DECL,b'<!-- owner-normal443-contract -->\n```json\n'+v3.encode(policy)+b'\n```')
            write(normal,v3.NORMAL_SELF,host.normal_module.replace(OPS.encode(),operations.encode()))
            write(normal,'rebuild/core/preview_access.py',b'OWNER_NORMAL_ORIGIN_PROTOCOL_QUALIFIED=True\n')
            write(normal,'rebuild/quillmd/settings.py',b"QUILLMD_OWNER_NORMAL_ORIGIN_ENABLED=os.getenv('QUILLMD_OWNER_NORMAL_ORIGIN_ENABLED', '0') == '1'\n")
            git(normal,'add','.');git(normal,'commit','-m','Fictional exact eight-path normal descendant')
            target=git(normal,'rev-parse','HEAD').strip().decode();git(root,'update-ref','refs/remotes/origin/main',target)
            class GitHost(FakeHost):
                def git(self,tree,*args):return git(tree,*args)
                def read_source(self,path):return path.read_bytes()
                def canonical(self,path):return path.resolve(strict=True)
            actual=GitHost();actual.source=source;actual.contract=current
            actual.environment={'RULED_MUTATION_DECLARATION':v3.DECL,'RULED_MUTATION_DECL_COMMIT':operations}
            with patch.object(v3,'ROOT',root),patch.object(v3,'M6',served):
                result=v3.source_gate(actual,current,operations,served,actual.environment)
                self.assertEqual(result['merged_main']['revision'],target)
                # An unstated installed revision fails even with exact descendant source.
                git(root,'update-ref','refs/heads/main',operations)
                with self.assertRaisesRegex(v3.Refusal,'clean_served_revision'):
                    v3.source_gate(actual,current,operations,served,actual.environment)
                git(root,'update-ref','refs/heads/main',served)
                # A genuine later Git commit with a ninth used path cannot pass.
                write(normal,v3.SELF,b'changed acceptance operator in later main\n')
                git(normal,'add',v3.SELF);git(normal,'commit','-m','Fictional forbidden ninth path')
                drift=git(normal,'rev-parse','HEAD').strip().decode();git(root,'update-ref','refs/remotes/origin/main',drift)
                with self.assertRaisesRegex(v3.Refusal,'exact_eight_path_scope'):
                    v3.source_gate(actual,current,operations,served,actual.environment)
                # A real unrelated commit cannot be made an ancestor by policy claims.
                tree=git(root,'rev-parse',served+'^{tree}').strip().decode()
                unrelated=git(root,'commit-tree',tree,'-m','Fictional unrelated root').strip().decode()
                git(root,'update-ref','refs/remotes/origin/main',unrelated)
                with self.assertRaises(subprocess.CalledProcessError):
                    v3.source_gate(actual,current,operations,served,actual.environment)

    def test_cgroup_whitespace_and_foreign_unit_refuse(self):
        unit = v3.UNITS[2]
        v3.exact_cgroup('0::/system.slice/' + unit + '\n', unit)
        for raw in ('0::/system.slice/' + unit + ' \n', '0::/system.slice/' + unit + '\t\n',
                    '0::/system.slice/foreign.service\n', '0::/system.slice/' + unit):
            with self.assertRaises(v3.Refusal): v3.exact_cgroup(raw, unit)

    def test_operations_revision_derives_from_qualified_head_without_self_pin(self):
        host = FakeHost()
        result = v3.source_gate(host, host.contract, OPS, SERVED, host.environment)
        self.assertIsNone(host.contract['operations_revision'])
        self.assertEqual(result['operations_revision'], host.ops)
        self.assertEqual(result['operations_revision_policy'], v3.OPERATIONS_REVISION_POLICY)
        self.assertIn(('citation', OPS), host.events)
        with self.assertRaisesRegex(v3.Refusal, 'caller_operations_revision_matches_derived_head'):
            v3.source_gate(FakeHost(), contract(), '4' * 40, SERVED, FakeHost.environment)

    def test_operations_derivation_policy_missing_tampered_or_literal_self_pin_refuses(self):
        for mutate in (lambda value: value.pop('operations_revision_policy'),
                       lambda value: value.pop('operations_revision'),
                       lambda value: value.update(operations_revision_policy='trust_caller_head'),
                       lambda value: value.update(operations_revision=OPS)):
            host = FakeHost(); mutate(host.contract)
            with self.assertRaisesRegex(v3.Refusal, 'exact_operations_revision_derivation_policy'):
                v3.source_gate(host, host.contract, OPS, SERVED, host.environment)
        host = FakeHost(); host.contract['served_revision'] = None
        with self.assertRaisesRegex(v3.Refusal, 'separate_declared_served_revision'):
            v3.source_gate(host, host.contract, OPS, SERVED, host.environment)

    def test_pipeline_same_hold_fixed_sequence_shared_deadline(self):
        host = FakeHost(); v3.protocol_pipeline(host, contract(), OPS, SERVED)
        phases = [row for row in host.events if isinstance(row, str)]
        self.assertEqual(phases, ['dependencies', 'availability', 'locks-enter', 'inside-source-idle',
            'before-auth', 'exclusive-preparation', 'after-auth', 'inside-source-idle', 'attempt', 'complete', 'locks-exit'])
        child = {row[0]: row[1] for row in host.events if isinstance(row, tuple) and row[0] in ('normal-auth', 'browser', 'verify')}
        self.assertEqual(child['browser'], child['verify']); self.assertLess(child['normal-auth'], child['browser'])

    def test_campaign_failure_stops_without_rollback_or_second_send(self):
        host = FakeHost(); host.fail_phase = 'browser'
        with self.assertRaises(v3.Refusal): v3.protocol_pipeline(host, contract(), OPS, SERVED)
        self.assertIn('STOP', host.events); self.assertEqual(host.events[-1], 'locks-exit')
        self.assertEqual(sum(isinstance(row, tuple) and row[0] == 'browser' for row in host.events), 1)
        self.assertFalse(any(isinstance(row, tuple) and row[0] == 'verify' for row in host.events))

    def test_postauth_recheck_deadline_expiry_precedes_attempt_marker(self):
        class LateHost(FakeHost):
            checks = 0
            def recheck_source_and_idle(self, *args):
                super().recheck_source_and_idle(*args); self.checks += 1
                if self.checks == 2: self.now = 1700
        host = LateHost()
        with self.assertRaisesRegex(v3.Refusal, 'phase_deadline'):
            v3.protocol_pipeline(host, contract(), OPS, SERVED)
        self.assertNotIn('attempt', host.events); self.assertNotIn('STOP', host.events)
        self.assertFalse(any(isinstance(row, tuple) and row[0] == 'browser' for row in host.events))
        self.assertEqual(host.events[-1], 'locks-exit')

    def test_arbitrary_child_or_swapped_revision_refuse(self):
        command = v3.fixed_child_argv(FakeHost.source, 'browser', OPS, SERVED)
        self.assertEqual(command[-4:], ['--operations-revision', OPS, '--served-revision', SERVED])
        self.assertIn('--dispatch-browser', command)
        with self.assertRaises(v3.Refusal): v3.fixed_child_argv(FakeHost.source, 'shell', OPS, SERVED)
        with self.assertRaises(v3.Refusal): v3.fixed_child_argv(FakeHost.source, 'browser', 'abc', SERVED)

    def test_unknown_authentication_stops_before_clinical_marker(self):
        host = FakeHost(); host.fail_phase = 'normal-auth'
        with self.assertRaises(v3.Refusal): v3.protocol_pipeline(host, contract(), OPS, SERVED)
        self.assertIn('STOP', host.events)
        self.assertNotIn('attempt', host.events)
        self.assertFalse(any(isinstance(row, tuple) and row[0] in ('browser', 'verify') for row in host.events))


class FixtureOwnerOS:
    """Private fixture view; real modes/inodes/bytes are never altered by this shim."""
    def __init__(self):
        self.creator_uid, self.creator_gid = os.getuid(), os.getgid()
    def __getattr__(self, name): return getattr(os, name)
    def getuid(self): return 1000
    def getgid(self): return 1000
    def fstat(self, fd):
        info = os.fstat(fd)
        values = {name: getattr(info, name) for name in dir(info) if name.startswith('st_')}
        if info.st_uid == self.creator_uid: values['st_uid'] = 1000
        if info.st_gid == self.creator_gid: values['st_gid'] = 1000
        return types.SimpleNamespace(**values)


class ChildAndPrivateFileTests(unittest.TestCase):
    def setUp(self):
        self.owner_patch = patch.object(v3, 'os', FixtureOwnerOS())
        self.owner_patch.start(); self.addCleanup(self.owner_patch.stop)

    def test_private_parent_symlink_refuses_without_canary_read(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); secret = root / 'private'; secret.mkdir()
            (secret / 'canary').write_bytes(b'fictional unread private canary')
            (secret / 'canary').chmod(0o600)
            (root / 'replacement').symlink_to(secret, target_is_directory=True)
            with patch.object(v3.os, 'fdopen', side_effect=AssertionError('canary read')):
                with self.assertRaises(OSError): v3.protected(root / 'replacement/canary')

    def test_sealed_child_source_keeps_checked_bytes_after_path_replacement(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'source.py'; path.write_bytes(b'fictional checked source')
            with v3.sealed_buffer(path.read_bytes()) as fd:
                path.write_bytes(b'fictional replacement source')
                self.assertEqual(os.pread(fd, 4096, 0), b'fictional checked source')
                with self.assertRaises(OSError): os.write(fd, b'changed')

    def test_fixture_owner_representation_preserves_all_nonowner_fields(self):
        shim = FixtureOwnerOS()
        with tempfile.TemporaryFile() as stream:
            original = os.fstat(stream.fileno()); represented = shim.fstat(stream.fileno())
            self.assertEqual((represented.st_uid, represented.st_gid), (1000, 1000))
            for name in dir(original):
                if name.startswith('st_') and name not in ('st_uid', 'st_gid'):
                    self.assertEqual(getattr(original, name), getattr(represented, name))
            # An explicit represented hosted-runner creator does not relax the
            # production gate; a foreign owner remains foreign in the view.
            shim.creator_uid = 1001; shim.creator_gid = 1001
            fixture = types.SimpleNamespace(st_uid=1001, st_gid=1001, st_mode=stat.S_IFREG|0o600,
                st_ino=7, st_dev=3, st_nlink=1, st_size=9, st_mtime_ns=13, st_ctime_ns=17)
            with patch.object(os, 'fstat', return_value=fixture):
                represented = shim.fstat(9)
            self.assertEqual((represented.st_uid, represented.st_gid), (1000, 1000))
            fixture.st_uid = 1002
            with patch.object(os, 'fstat', return_value=fixture):
                self.assertEqual(shim.fstat(9).st_uid, 1002)

    def test_owned_temp_locks_single_holder_and_release(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for relative in v3.LOCKS:
                path = root / relative; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(b''); path.chmod(0o600)
            with v3.existing_operation_locks(root):
                with self.assertRaises(BlockingIOError):
                    with v3.existing_operation_locks(root): pass
            with v3.existing_operation_locks(root): pass
            (root / v3.LOCKS[0]).chmod(0o644)
            with self.assertRaises(v3.Refusal):
                with v3.existing_operation_locks(root): pass

    def test_no_lock_creation_or_symlink_adoption(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with self.assertRaises(FileNotFoundError):
                with v3.existing_operation_locks(root): pass
            self.assertFalse((root / v3.LOCKS[0]).exists())
            target = root / 'target'; target.write_bytes(b''); target.chmod(0o600)
            (root / v3.LOCKS[0]).symlink_to(target)
            with self.assertRaises(OSError):
                with v3.existing_operation_locks(root): pass

    def test_protected_bytes_mode_links_bound_and_exclusive_write(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'proof.json'; v3.write_new(path, {'fictional': True})
            self.assertEqual(json.loads(v3.protected(path)), {'fictional': True})
            with self.assertRaises(FileExistsError): v3.write_new(path, {})
            with self.assertRaises(v3.Refusal): v3.protected(path, 1)
            os.link(path, Path(temp) / 'second')
            with self.assertRaises(v3.Refusal): v3.protected(path)

    def test_timeout_group_reaped_before_diagnostic_failure(self):
        events = []; alive = {'value': True}
        class Process:
            pid = 42; returncode = None
            def communicate(self, timeout):
                events.append(('communicate', timeout))
                if timeout != 10: raise subprocess.TimeoutExpired('fictional', timeout)
                self.returncode = -9; return b'raw retained stdout', b'raw retained stderr'
            def poll(self): return self.returncode
        def popen(*args, **kwargs):
            self.assertTrue(kwargs['start_new_session']); self.assertEqual(kwargs['cwd'], FakeHost.source)
            return Process()
        def kill(pid, value):
            events.append(('kill', pid, value))
            if value == v3.signal.SIGKILL: alive['value'] = False
        def writer(*args):
            self.assertEqual(events[-1], ('communicate', 10)); raise OSError('fictional ENOSPC')
        with self.assertRaises(OSError):
            v3.child_process(['fixed fictional argv'], FakeHost.source, Path('/fictional'), 'browser', 20,
                             ruled=True, clock=lambda: 0, popen=popen, killpg=kill,
                             group_identity=lambda pid: (pid, pid), group_alive=lambda pid: alive['value'], writer=writer)
        self.assertEqual([row[2] for row in events if row[0] == 'kill'], [v3.signal.SIGTERM, v3.signal.SIGKILL])

    def test_failed_and_expired_child_no_second_invocation(self):
        calls = []
        class Process:
            pid = 42; returncode = 2
            def communicate(self, timeout): return b'failure', b'bounded'
            def poll(self): return self.returncode
        def popen(*args, **kwargs): calls.append(args); return Process()
        with self.assertRaises(v3.Refusal):
            v3.child_process(['fixed'], FakeHost.source, Path('/fictional'), 'browser', 20, ruled=True,
                             clock=lambda: 0, popen=popen, killpg=lambda *args: None,
                             group_identity=lambda pid: (pid, pid), group_alive=lambda pid: False, writer=lambda *args: None)
        self.assertEqual(len(calls), 1)
        with self.assertRaises(v3.Refusal):
            v3.child_process(['fixed'], FakeHost.source, Path('/fictional'), 'browser', 0, ruled=True,
                             clock=lambda: 0, popen=popen, killpg=lambda *args: None,
                             group_identity=lambda pid: (pid, pid), group_alive=lambda pid: False, writer=lambda *args: None)
        self.assertEqual(len(calls), 1)

    def test_exited_leader_residual_owned_descendant_drained_before_logs(self):
        events = []; alive = {'value': True}
        class Process:
            pid = 42; returncode = None; communications = 0
            def communicate(self, timeout):
                self.communications += 1
                if self.communications == 1: raise subprocess.TimeoutExpired('fictional', timeout)
                self.returncode = 0; return b'leader closed stdout', b'leader closed stderr'
            def poll(self): return self.returncode
        def popen(*args, **kwargs):
            self.assertTrue(kwargs['start_new_session']); return Process()
        def kill(group, value):
            self.assertEqual(group, 42); events.append(('signal', value))
            if value == v3.signal.SIGKILL: alive['value'] = False
        def writer(path, raw):
            self.assertFalse(alive['value']); events.append(('diagnostic', path.name))
        with self.assertRaisesRegex(v3.Refusal, 'unknown_outcome_no_retry'):
            v3.child_process(['fixed'], FakeHost.source, Path('/fictional'), 'browser', 20, ruled=True,
                clock=lambda: 0, popen=popen, killpg=kill, group_identity=lambda pid: (pid, pid),
                group_alive=lambda pid: alive['value'], writer=writer)
        self.assertEqual(events[:2], [('signal', v3.signal.SIGTERM), ('signal', v3.signal.SIGKILL)])
        self.assertEqual(len([row for row in events if row[0] == 'diagnostic']), 2)

    def test_wrong_spawned_group_never_receives_group_signal(self):
        signals = []
        class Process:
            pid = 42; returncode = 0
            def communicate(self, timeout): raise AssertionError('unverified group should not communicate')
            def poll(self): return self.returncode
        with self.assertRaisesRegex(v3.Refusal, 'spawned_session_group_identity'):
            v3.child_process(['fixed'], FakeHost.source, Path('/fictional'), 'browser', 20, ruled=True,
                clock=lambda: 0, popen=lambda *args, **kwargs: Process(), killpg=lambda *args: signals.append(args),
                group_identity=lambda pid: (999, 999), group_alive=lambda pid: True, writer=lambda *args: None)
        self.assertFalse(signals)

    def test_ordinary_leader_success_with_descendant_is_drained_and_refused(self):
        events = []; alive = {'value': True}
        class Process:
            pid = 42; returncode = 0
            def communicate(self, timeout): return b'leader returned success', b''
            def poll(self): return self.returncode
        def kill(group, value):
            self.assertEqual(group, 42); events.append(('signal', value))
            if value == v3.signal.SIGKILL: alive['value'] = False
        def writer(path, raw):
            self.assertFalse(alive['value']); events.append(('diagnostic', path.name))
        with self.assertRaisesRegex(v3.Refusal, 'unknown_outcome_no_retry'):
            v3.child_process(['fixed'], FakeHost.source, Path('/fictional'), 'browser', 20, ruled=True,
                clock=lambda: 0, popen=lambda *args, **kwargs: Process(), killpg=kill,
                group_identity=lambda pid: (pid, pid), group_alive=lambda pid: alive['value'], writer=writer)
        self.assertEqual(events[:2], [('signal', v3.signal.SIGTERM), ('signal', v3.signal.SIGKILL)])
        self.assertEqual(len([row for row in events if row[0] == 'diagnostic']), 2)

    def test_genuinely_empty_group_ordinary_success_remains_success(self):
        signals = []; diagnostics = []
        class Process:
            pid = 42; returncode = 0
            def communicate(self, timeout): return b'complete', b''
            def poll(self): return self.returncode
        result = v3.child_process(['fixed'], FakeHost.source, Path('/fictional'), 'browser', 20, ruled=True,
            clock=lambda: 0, popen=lambda *args, **kwargs: Process(), killpg=lambda *args: signals.append(args),
            group_identity=lambda pid: (pid, pid), group_alive=lambda pid: False,
            writer=lambda path, raw: diagnostics.append((path.name, raw)))
        self.assertEqual(result['exit_code'], 0); self.assertFalse(signals)
        self.assertEqual(len(diagnostics), 2)

    def test_undrained_owned_group_deadline_refuses_without_diagnostics(self):
        now = {'value': 0}; diagnostics = []; signals = []
        class Process:
            pid = 42; returncode = 0
            def communicate(self, timeout): return b'incomplete', b''
            def poll(self): return self.returncode
        with self.assertRaisesRegex(v3.Refusal, 'owned_group_drain_unknown_outcome'):
            v3.child_process(['fixed'], FakeHost.source, Path('/fictional'), 'browser', 20, ruled=True,
                clock=lambda: now['value'], popen=lambda *args, **kwargs: Process(),
                killpg=lambda *args: signals.append(args), group_identity=lambda pid: (pid, pid),
                group_alive=lambda pid: True, sleep=lambda elapsed: now.update(value=now['value'] + elapsed),
                writer=lambda *args: diagnostics.append(args))
        self.assertEqual([row[1] for row in signals], [v3.signal.SIGTERM, v3.signal.SIGKILL])
        self.assertFalse(diagnostics); self.assertGreaterEqual(now['value'], 10)

    def test_injected_transport_cannot_fall_back_to_native_group_io(self):
        with (patch.object(os, 'killpg', side_effect=AssertionError('native signal')),
              patch.object(os, 'getpgid', side_effect=AssertionError('native group read'))):
            with self.assertRaisesRegex(v3.Refusal, 'injected_transport_requires'):
                v3.child_process(['fixed'], FakeHost.source, Path('/fictional'), 'browser', 20, ruled=True,
                                 popen=lambda *args, **kwargs: None, writer=lambda *args: None)


class NativeAdapterTests(unittest.TestCase):
    def publication_fixture(self, runtime, *, drift=None, fail_wait=False, late=False, occupied=False):
        for relative in (*v3.LOCKS, v3.PUBLICATION_LOCK):
            path = runtime / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b'')
            path.chmod(0o600)
        host = v3.InstalledHost.__new__(v3.InstalledHost)
        host.inside = False; host.lock_rows = []; host.publication_alignment = None
        host.operations = OPS; host.served = SERVED; host.source = Path('/fictional/source'); host.backup = object()
        host.own_hold_mode = '--execute'
        clock = [100.0]; host.clock = lambda: clock[0]
        host.read_source = lambda path: b'fictional reviewed declaration'
        selected = {'row': {'key': 'backup', 'computed_at': '2026-10-07T16:00:00+00:00'},
            'unit': {'InvocationID': 'a'*32}, 'timer': {'SubState': 'waiting'},
            'journal': [('a'*32, 'fictional genuine publication')], 'coherent_unit': True}
        current = copy.deepcopy(selected)
        if drift == 'coherent_unit': current['coherent_unit'] = False
        elif drift in ('row', 'unit', 'timer'): current[drift]['changed'] = True
        elif drift == 'journal': current['journal'].append(('b'*32, 'fictional other invocation'))
        sources = {'publisher.service': {'sha256': 'c'*64}}
        calls = []
        def source_pins():
            calls.append('sources')
            return {'changed': True} if drift == 'source' and len(calls) > 2 else sources
        def wait(contract, observe):
            self.assertFalse(host.inside)
            self.assertEqual([row['path'] for row in host.lock_rows], [str(runtime/r) for r in v3.LOCKS])
            for relative in v3.LOCKS:
                fd = os.open(runtime/relative, os.O_RDWR)
                try:
                    with self.assertRaises(BlockingIOError): fcntl.flock(fd, fcntl.LOCK_EX|fcntl.LOCK_NB)
                finally: os.close(fd)
            if not occupied:
                fd = os.open(runtime/v3.PUBLICATION_LOCK, os.O_RDWR)
                try: fcntl.flock(fd, fcntl.LOCK_EX|fcntl.LOCK_NB)
                finally: os.close(fd)
            calls.append('wait')
            if fail_wait: raise v3.Refusal('v3_fixture_no_natural_publication')
            if late: clock[0] = 1001
            return selected
        host.recovery = types.SimpleNamespace(DECL='reviewed.md', contract_from_bytes=lambda raw: {'fixture': True},
            publisher_unit_sources=source_pins, publisher_observer=lambda backup: lambda: current,
            await_natural_publication=wait)
        return host, clock

    def test_natural_publication_wait_holds_four_inputs_before_fifth_lock(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(v3, 'os', FixtureOwnerOS()):
            runtime = Path(temp)
            with patch.object(v3, 'RUNTIME', runtime):
                host, _ = self.publication_fixture(runtime)
                with host.exclusions(OPS, 1000):
                    self.assertTrue(host.inside)
                    self.assertEqual(len(host.lock_rows), 5)
                    self.assertEqual(host.publication_alignment['manual_publications'], 0)
                    self.assertEqual(host.publication_alignment['timer_or_service_actions'], 0)
                self.assertFalse(host.inside)
                self.assertEqual(host.lock_rows, [])
                self.assertIsNone(host.publication_alignment)

    def test_selected_publication_or_source_drift_refuses_before_authentication(self):
        for drift in ('row', 'unit', 'timer', 'journal', 'coherent_unit', 'source'):
            with self.subTest(drift=drift), tempfile.TemporaryDirectory() as temp, patch.object(v3, 'os', FixtureOwnerOS()):
                runtime = Path(temp)
                with patch.object(v3, 'RUNTIME', runtime):
                    host, _ = self.publication_fixture(runtime, drift=drift)
                    with self.assertRaises(v3.Refusal), host.exclusions(OPS, 1000):
                        self.fail('Entered authentication boundary after publisher drift')
                    self.assertFalse(host.inside)
                    self.assertEqual(host.lock_rows, [])

    def test_failed_late_publication_and_bounded_drain_release_input_locks(self):
        for kind in ('failed_wait', 'late_wait', 'occupied_publication'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as temp, patch.object(v3, 'os', FixtureOwnerOS()):
                runtime = Path(temp)
                with patch.object(v3, 'RUNTIME', runtime):
                    host, clock = self.publication_fixture(runtime, fail_wait=kind=='failed_wait',
                        late=kind=='late_wait', occupied=kind=='occupied_publication')
                    blocker = os.open(runtime/v3.PUBLICATION_LOCK, os.O_RDWR)
                    try:
                        if kind=='occupied_publication': fcntl.flock(blocker, fcntl.LOCK_EX|fcntl.LOCK_NB)
                        with patch.object(v3.time, 'sleep', side_effect=lambda seconds: clock.__setitem__(0,clock[0]+seconds)):
                            with self.assertRaises(v3.Refusal), host.exclusions(OPS, 1000):
                                self.fail('Entered authentication after unknown publication')
                        self.assertLessEqual(clock[0], 1001)
                        self.assertFalse(host.inside); self.assertEqual(host.lock_rows, [])
                        for relative in v3.LOCKS:
                            fd = os.open(runtime/relative, os.O_RDWR)
                            try: fcntl.flock(fd, fcntl.LOCK_EX|fcntl.LOCK_NB)
                            finally: os.close(fd)
                    finally: os.close(blocker)

    def test_actual_checked_native_namespace_has_closed_transitive_imports(self):
        names = ('managed_helper','private_storage','backup_restore','email_activation','activation_exclusion',
                 'legacy_model_activation','repair_source_permissions','publisher_verification','private_availability_recovery')
        blobs = {name:(v3.SOURCE/'rebuild/ops'/f'{name}.py').read_bytes() for name in names}
        class SourceHost:
            source = v3.SOURCE
            operations = OPS
            def read_source(self,path):return blobs[Path(path).stem]
            def git(self,tree,*args):return blobs[Path(args[1].split(':',1)[1]).stem]
        with (patch.object(subprocess,'run',side_effect=AssertionError('native helper')),
              patch.object(socket,'create_connection',side_effect=AssertionError('network'))):
            package = v3.checked_native_modules(SourceHost())
        self.assertEqual(package.__path__,[])
        scope={'__package__':package.__name__}
        exec('from . import repair_source_permissions as source_files\nfrom . import publisher_verification as publisher_judge',scope)
        self.assertIs(scope['source_files'],package.repair_source_permissions)
        self.assertIs(scope['publisher_judge'],package.publisher_verification)
        self.assertIs(package.private_availability_recovery.old,package.legacy_model_activation)
        self.assertIs(package.legacy_model_activation.modules()[1],package.backup_restore)
        self.assertEqual(v3.DEPENDENCIES['verify_installed_acceptance_v3.py'],
                         '34d4d3bf0b9641a2f642717b33833beb7a7f49a0c043bc095e592c41a78b0023')

    def test_derived_authority_does_not_adopt_current_baseline_or_modify_declaration(self):
        value = contract(); before = copy.deepcopy(value)
        common = types.SimpleNamespace(ORIGINAL_RECEIPTS={'failed.json': 'old'}, FAILED_CONTINUATION={'failed.json': 'old-continuation'})
        raw = b'fictional independently admitted original population'
        result = v3.derive_authority(value, common, OPS, SERVED, {'before-auth': raw})
        self.assertEqual(value, before)
        self.assertEqual(result['operations_revision'], OPS)
        self.assertEqual(result['original_activation'], str(v3.ORIGINAL))
        self.assertEqual(result['original_receipts'], common.ORIGINAL_RECEIPTS)
        self.assertEqual(result['admissions']['before-auth']['sha256'], v3.sha(raw))
        self.assertNotIn('current_baseline', result)
        with self.assertRaises(v3.Refusal): v3.derive_authority(value, common, OPS, SERVED, {'fresh-baseline': raw})
        with self.assertRaises(v3.Refusal): v3.derive_authority(value, common, OPS, OPS, {})

    def test_parent_observation_requires_exact_kernel_five_lock_holder(self):
        device = os.makedev(8, 3); pid = 12345
        rows = [{'path': str(v3.RUNTIME / relative), 'fd': index + 10, 'device': device, 'inode': index + 200}
                for index, relative in enumerate((*v3.LOCKS, v3.PUBLICATION_LOCK))]
        context = {'format': 3, 'phase': 'browser', 'operations_revision': OPS, 'served_revision': SERVED,
            'parent_pid': pid, 'parent_uid': 1000, 'parent_start_ticks': 42, 'deadline_monotonic': 1000, 'locks': rows}
        infos = {row['fd']: types.SimpleNamespace(st_mode=stat.S_IFREG|0o600, st_uid=1000, st_gid=1000,
            st_nlink=1, st_dev=device, st_ino=row['inode']) for row in rows}
        lock_text = '\n'.join(f'{i}: FLOCK ADVISORY WRITE {pid} 08:03:{row["inode"]} 0 EOF' for i, row in enumerate(rows))
        command = [str(v3.PYTHON), '-B', str(FakeHost.source / v3.ENTRY), '--execute',
                   '--operations-revision', OPS, '--served-revision', SERVED]
        def read_text(path): return lock_text if str(path) == '/proc/locks' else '123 (fictional worker) ' + ' '.join(['0']*19+['42'])
        def fd_stat(path): return infos[int(Path(path).name)]
        @contextmanager
        def attached(path): yield next(row['fd'] for row in rows if row['path'] == str(path))
        original_observer = v3.parent_phase_admission
        def admit(value=context, **kw):
            return original_observer(value, 'browser', OPS, SERVED, monotonic=lambda: 900,
                stat_fd=fd_stat, read_text=read_text, read_bytes=lambda p: b'\0'.join(s.encode() for s in command)+b'\0',
                source=FakeHost.source, **kw)
        with patch.object(v3, 'nofollow_file', attached), patch.object(v3.os, 'fstat', side_effect=lambda fd: infos[fd]):
            self.assertIs(admit(), context)
            own_context={**context,'parent_pid':os.getpid()}
            own_locks=lock_text.replace(str(pid),str(os.getpid()))
            def own_admit(mode,actual_mode):
                actual=list(command);actual[3]=actual_mode
                return original_observer(own_context,'browser',OPS,SERVED,monotonic=lambda:900,
                    stat_fd=fd_stat,read_text=lambda path:own_locks if str(path)=='/proc/locks' else read_text(path),
                    read_bytes=lambda path:b'\0'.join(value.encode() for value in actual)+b'\0',
                    source=FakeHost.source,self_mode=mode)
            for mode in ('--execute','--preflight','--admit-before-auth'):
                self.assertIs(own_admit(mode,mode),own_context)
                with self.assertRaisesRegex(v3.Refusal,'parent_fixed_command'):own_admit(mode,'--verify')
            with self.assertRaisesRegex(v3.Refusal,'exact_own_holder_mode'):own_admit('--verify','--verify')
            with self.assertRaisesRegex(v3.Refusal,'exact_own_holder_mode'):
                original_observer(context,'browser',OPS,SERVED,monotonic=lambda:900,self_mode='--preflight')
            host=v3.InstalledHost.__new__(v3.InstalledHost);host.inside=True
            host.parent_lock_context=context;host.operations=OPS;host.served=SERVED;host.source=FakeHost.source
            host.clock=lambda:900.0
            host.publication_alignment={'hold':{'acquired_monotonic':500.0,'deadline_monotonic':1100.0,
                'parent_pid':pid,'parent_start_ticks':42,'locks':copy.deepcopy(rows),'own_mode':'--execute'}}
            with patch.object(v3,'parent_phase_admission',side_effect=lambda value,*args,**kw:admit(value)):
                host.check_publication_hold()
                hold=host.publication_alignment['hold']
                for key,value in [('parent_pid',pid+1),('parent_start_ticks',43),('acquired_monotonic',901.0),
                                  ('deadline_monotonic',800.0),('locks',rows[:-1])]:
                    before=hold[key];hold[key]=value
                    with self.subTest(hold=key),self.assertRaises(v3.Refusal):host.check_publication_hold()
                    hold[key]=before
                context['deadline_monotonic']=1101.0
                with self.assertRaisesRegex(v3.Refusal,'hash_bound_parent_hold_identity'):host.check_publication_hold()
                context['deadline_monotonic']=1000
            for key, value in (('parent_start_ticks', 43), ('deadline_monotonic', 800), ('phase', 'verify'),
                               ('operations_revision', SERVED), ('served_revision', OPS), ('parent_uid', 1001)):
                with self.subTest(key=key), self.assertRaises(v3.Refusal): admit({**context,key:value})
            with self.assertRaises(v3.Refusal): admit({**context,'locks':rows[:-1]})
            old = lock_text; lock_text = '\n'.join(old.splitlines()[:-1])
            with self.assertRaises(v3.Refusal): admit()
            lock_text = old
            infos[10].st_uid = 1001
            with self.assertRaises(v3.Refusal): admit()
            infos[10].st_uid = 1000
            command[2] = '/fictional/unreviewed-parent.py'
            with self.assertRaisesRegex(v3.Refusal, 'parent_fixed_command'): admit()

    def test_child_auth_environment_excludes_application_provider_credentials(self):
        env = v3.child_environment({'HOME':'/fictional/native-home','GH_TOKEN':'fictional-gh',
            'RULED_MUTATION_DECL_COMMIT':COMMIT,'ANTHROPIC_API_KEY':'fictional-never-copied',
            'QUILLMD_SECRET_KEY':'fictional-never-copied','STRIPE_SECRET_KEY':'fictional-never-copied',
            'PATH':'/fictional/unsafe'})
        self.assertEqual(env['HOME'], '/fictional/native-home')
        self.assertEqual(env['GH_TOKEN'], 'fictional-gh')
        self.assertNotIn('fictional-never-copied', env.values())
        self.assertEqual(env['PATH'], '/usr/sbin:/usr/bin:/sbin:/bin')

    def test_cli_installed_modes_reach_fixed_adapter_only_after_source_gate(self):
        host = FakeHost(); calls = []
        host.bind = lambda c,o,s: calls.append(('bind',o,s))
        with patch.object(v3, 'execution_gate'), patch.object(v3, 'InstalledHost', return_value=host), \
                patch.object(v3, 'installed_contract', return_value=(declaration(), contract())), \
                patch.object(v3, 'protocol_pipeline', return_value={'complete':True}) as pipeline, \
                patch('sys.stdout', new=io.StringIO()):
            self.assertEqual(v3.main(['--execute','--operations-revision',OPS,'--served-revision',SERVED]), 0)
        pipeline.assert_called_once_with(host, contract(), OPS, SERVED)
        self.assertEqual(calls, [('bind',OPS,SERVED)])
        self.assertIn('dependencies', host.events)

    def test_unqualified_declaration_cannot_enable_even_present_native_adapter(self):
        with self.assertRaisesRegex(v3.Refusal, 'declaration_source_qualification'):
            v3.installed_contract(FakeHost())

    def test_refusal_reports_known_early_zero_and_unknown_entered_phase(self):
        clean = {'installed_state_accessed':False,'authentication_possible':False,'provider_possible':False}
        with patch.dict(v3.ENTRY_OBSERVATIONS, clean, clear=True):
            with self.assertRaises(v3.Refusal) as caught: v3.execution_gate()
            early = v3.failure_summary(caught.exception)
            self.assertFalse(early['installed_state_accessed'])
            self.assertEqual((early['provider_calls'],early['authentication_submissions'],early['database_writes']),(0,0,0))
            v3.ENTRY_OBSERVATIONS.update(installed_state_accessed=True, authentication_possible=True, provider_possible=True)
            entered = v3.failure_summary(v3.Refusal('v3_child_unknown_outcome_no_retry'))
            self.assertTrue(entered['installed_state_accessed'])
            self.assertTrue(entered['phase_outcomes_require_protected_receipts'])
            self.assertEqual((entered['provider_calls'],entered['authentication_submissions'],entered['database_writes']),(None,None,None))
            for error in (v3.Refusal('v3_fictional_private_patient_name'),RuntimeError('fictional private record')):
                self.assertEqual(v3.failure_summary(error)['reason'],'v3_fixed_protocol_failure')

    def test_measured_service_invocations_are_separate_from_legacy_unit_map(self):
        legacy = {unit:{'ActiveState':'active','SubState':'running','MainPID':str(index+10),
            'FragmentPath':'/etc/systemd/system/'+unit,'DropInPaths':'','UnitFileState':'enabled',
            'ExecMainStartTimestampMonotonic':'100'} for index,unit in enumerate(v3.UNITS)}
        measured = {unit:{**row,'InvocationID':'a'*32,'NeedDaemonReload':'no'} for unit,row in legacy.items()}
        proof = {'values':{'QUILLMD_RELEASE_SHA':SERVED,'QUILLMD_AI_MODEL':v3.MODEL},'actual_provider_model_verified':False}
        receipt = {'units_after':legacy,'completion_unit_provenance':measured,'worker_configuration_provenance':proof}
        current = {'units':{unit:{**row,'release':SERVED} for unit,row in measured.items()},
            'cgroups':{unit:'0::/system.slice/'+unit+'\n' for unit in v3.UNITS},
            'kernel_start_ticks':{unit:1 for unit in v3.UNITS},'worker_configuration_provenance':proof,
            'pending_jobs':0,'held':0,'unresolved_reaper_paths':0,'old_job_receipt_usage_unchanged':True,
            'private_origin':v3.ORIGIN,'public_status':503,'ingress_sha256':'a'*64,'expected_ingress_sha256':'a'*64}
        self.assertTrue(v3.live_identity(receipt,current,SERVED)['same_pid_start_source_and_configuration'])
        self.assertEqual(set(legacy[v3.UNITS[0]]),{'ActiveState','SubState','MainPID','FragmentPath','DropInPaths','UnitFileState','ExecMainStartTimestampMonotonic'})
        with self.assertRaises(v3.Refusal):v3.live_identity({**receipt,'completion_unit_provenance':None},current,SERVED)
        for key,value in (('InvocationID','b'*32),('NeedDaemonReload','yes'),('UnitFileState','disabled')):
            bad = copy.deepcopy(current);bad['units'][v3.UNITS[0]][key] = value
            with self.subTest(key=key),self.assertRaises(v3.Refusal):v3.live_identity(receipt,bad,SERVED)


class FinancialAndExportTests:
    """Explicit manual suite; actual pinned host inputs are not remote fixtures.

    This mixin is deliberately outside ordinary unittest TestCase discovery.
    --local-qualification creates its TestCase and fails on unavailable inputs;
    it never skips or replaces the actual frozen evidence with an invented copy.
    """
    @classmethod
    def setUpClass(cls):
        from django.conf import settings
        if not settings.configured:
            settings.configure(SECRET_KEY='fictional test-only key', SECRET_KEY_FALLBACKS=[])
        cls.common, cls.verifier, cls.policy = v3.frozen_modules()

    def test_actual_frozen_javascript_adapters_parse_without_execution(self):
        blobs = {name: v3.protected(v3.FROZEN / name) for name in v3.DEPENDENCIES}
        authority = v3.derive_authority(contract(), self.common, OPS, SERVED, {'before-auth': b'fictional report'})
        declaration_raw = declaration() + b'\n'.join((key+': '+value).encode() for key,value in v3.FIXTURE_PINS.items())
        check = {'argv':['-B','-c','fictional checked native admission'], 'source_fd':9}
        for phase in ('normal-auth','browser'):
            with self.subTest(phase=phase):
                adapted = v3.javascript_adapter(blobs,phase,declaration_raw,authority,check)
                result = subprocess.run(['/usr/bin/node','--check','--input-type=module'], input=adapted,
                                        capture_output=True, timeout=15)
                self.assertEqual(result.returncode,0,result.stderr.decode())
                self.assertNotIn(b"from './acceptance-v3-contract.mjs'",adapted)
                self.assertNotIn(b'privateRead(new URL(import.meta.url).pathname)',adapted)
                self.assertNotIn(b'fs.readFileSync(path.join(process.cwd(),DECLARATION))',adapted)
                self.assertNotIn(b"execFileSync('bash',[path.join(process.cwd(),'scripts/check-citation.sh')",adapted)
        wrong = dict(blobs);wrong['acceptance_v3_contract.py'] += b'\n# unreviewed change'
        with self.assertRaisesRegex(v3.Refusal,'dependency_drift'):
            v3.javascript_adapter(wrong,'browser',declaration_raw,authority,check)
        self.assertEqual({name:v3.sha(v3.protected(v3.FROZEN/name)) for name in v3.DEPENDENCIES},v3.DEPENDENCIES)

    def final_admin_storage_fixture(self, root):
        admin=root/'admin';campaign=root/'campaign';admin.mkdir(mode=0o700);campaign.mkdir(mode=0o700)
        state={'cookies':[{'name':name,'value':'fictional-'+name,'secure':True,'httpOnly':True,'sameSite':site,
            'domain':'app.quillmd.com','path':'/','expires':1000.0} for name,site in
            [('__Host-quillmd_preview','Lax'),('quillmd_doctor_session','Strict'),('quillmd_doctor_csrf','Strict')]],'origins':[]}
        original=v3.encode(state);final=copy.deepcopy(state)
        for cookie in final['cookies']:cookie['expires']=2000.0
        final_raw=v3.encode(final);final_path=campaign/'admin-browser-session-after-readback.json'
        authentication={'actor_id':'fictional-staff','session_file':str(admin/'browser-session.json'),
                        'session_sha256':v3.sha(original)}
        auth_raw=v3.encode(authentication)
        for path,raw in [(admin/'browser-session.json',original),(admin/'normal-authentication.json',auth_raw),
                         (final_path,final_raw)]:path.write_bytes(raw);path.chmod(0o600)
        progress={'started':'2026-10-07T12:00:00Z','clinical_workflows_completed_at':'2026-10-07T12:05:00Z',
            'finished':'2026-10-07T12:05:11Z','cases':[{'name':name,'browser_complete':True} for name in v3.CASES],
            'admin_readback':{'actor_id':'fictional-staff','started_at':'2026-10-07T12:05:01Z',
                'finished_at':'2026-10-07T12:05:10Z','final_storage_state_captured_at':'2026-10-07T12:05:09Z',
                'final_storage_state_path':str(final_path),'final_storage_state_sha256':v3.sha(final_raw),
                'protected_session_sha256':v3.sha(original),'preparation_evidence_sha256':v3.sha(auth_raw)}}
        return admin,campaign,final_path,original,final_raw,progress

    def test_genuine_final_admin_state_files_bind_original_cookie_identity_and_real_interval(self):
        with tempfile.TemporaryDirectory() as temp:
            admin,campaign,final,original,final_raw,progress=self.final_admin_storage_fixture(Path(temp))
            with patch.object(v3,'ADMIN',admin),patch.object(v3,'FINAL_ADMIN_STATE',final):
                proof=v3.validate_admin_final_storage(progress)
                self.assertTrue(proof['complete']);self.assertEqual(proof['sha256'],v3.sha(final_raw))
                self.assertEqual((admin/'browser-session.json').read_bytes(),original)
                self.assertFalse(proof['expiry_modified_by_adapter'])
                for field,value in [('final_storage_state_captured_at','2026-10-07T12:04:59Z'),
                    ('final_storage_state_captured_at','2026-10-07T12:05:12Z'),
                    ('final_storage_state_sha256','0'*64),('final_storage_state_path',str(admin/'browser-session.json'))]:
                    bad=copy.deepcopy(progress);bad['admin_readback'][field]=value
                    with self.subTest(field=field),self.assertRaises(v3.Refusal):v3.validate_admin_final_storage(bad)
                bad=copy.deepcopy(progress);bad['clinical_workflows_completed_at']='2026-10-07T12:05:02Z'
                with self.assertRaises(v3.Refusal):v3.validate_admin_final_storage(bad)
                for name in ('quillmd_doctor_session','__Host-quillmd_preview'):
                    state=json.loads(final_raw);next(row for row in state['cookies'] if row['name']==name)['value']='counterfeit'
                    changed=v3.encode(state);final.write_bytes(changed)
                    bad=copy.deepcopy(progress);bad['admin_readback']['final_storage_state_sha256']=v3.sha(changed)
                    with self.assertRaisesRegex(v3.Refusal,'same_authenticated_cookie_identity'):v3.validate_admin_final_storage(bad)
                final.write_bytes(final_raw);final.unlink();final.symlink_to(admin/'browser-session.json')
                with self.assertRaises((v3.Refusal,OSError)):v3.validate_admin_final_storage(progress)
                self.assertEqual((admin/'browser-session.json').read_bytes(),original)

    def test_actual_js_block_moves_after_clinical_loop_and_captures_before_context_close(self):
        blobs={name:v3.protected(v3.FROZEN/name) for name in v3.DEPENDENCIES}
        authority=v3.derive_authority(contract(),self.common,OPS,SERVED,{})
        adapted=v3.javascript_adapter(blobs,'browser',declaration(),authority,{'argv':['fictional'],'source_fd':9})
        beginning=b'  const adminContext=await browser.newContext({storageState:JSON.parse(adminSessionBytes)});let readback;\n'
        ending=b'  }finally{await adminContext.close();if(readback){readback.finished_at=new Date().toISOString();save();}}\n'
        self.assertGreater(adapted.index(beginning),adapted.index(b'result.clinical_workflows_completed_at='))
        self.assertGreater(adapted.index(beginning),adapted.index(b'for(const [name,index,voice,spec] of cases)'))
        block=adapted[adapted.index(beginning):adapted.index(ending)+len(ending)].decode()
        self.assertEqual(adapted.count(beginning),1);self.assertEqual(adapted.count(b'const population=await adminContext.request.get'),1)
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);admin=root/'admin';campaign=root/'campaign';admin.mkdir(mode=0o700);campaign.mkdir(mode=0o700)
            state={'cookies':[{'name':name,'value':'fictional-'+name,'secure':True,'httpOnly':True,'sameSite':site,
                'domain':'app.quillmd.com','path':'/'} for name,site in [('__Host-quillmd_preview','Lax'),
                 ('quillmd_doctor_session','Strict'),('quillmd_doctor_csrf','Strict')]],'origins':[]}
            original=v3.encode(state);(admin/'browser-session.json').write_bytes(original);(admin/'browser-session.json').chmod(0o600)
            prelude=("import fs from 'node:fs';import path from 'node:path';import crypto from 'node:crypto';"
                "const require={resolve:()=>'/fictional/axe'},ORIGIN='https://app.quillmd.com:9443';"
                "const ADMIN="+json.dumps(str(admin))+",CAMPAIGN="+json.dumps(str(campaign))+",OUTPUT=CAMPAIGN;"
                "function must(value,label){if(!value)throw new Error(label)};"+v3.JS_OWNED_IO.decode()+
                "const digest=value=>crypto.createHash('sha256').update(value).digest('hex');"
                "const adminSessionBytes=privateRead(ADMIN+'/browser-session.json'),adminEvidenceBytes=Buffer.from('{}'),adminEvidence={actor_id:'fictional-staff'};"
                "const result={},events=[];let pageURL='',width=1440;function save(){};function validateCookies(value){must(value.length===3,'cookies')};"
                "function fixtureRead(file,encoding){must(file==='/fictional/axe','fixture read');return 'fictional axe'};"
                "const page={setDefaultTimeout(){},async goto(url){events.push('GET '+url);pageURL=url;return {status:()=>200}},url:()=>pageURL,"
                "async setViewportSize(value){width=value.width},async evaluate(value){if(typeof value==='string')return;const text=String(value);"
                "if(text.includes('scrollWidth'))return {width,documentWidth:width,labels:['System health']};if(text.includes('axe.run'))return [];},"
                "async screenshot({path:filename}){fs.writeFileSync(filename,Buffer.from('fictional screenshot'),{mode:0o600,flag:'wx'})}};"
                "const context={async route(){},async newPage(){return page},request:{async get(url){events.push('GET '+url);return {status:()=>200,json:async()=>({patients:[]})}}},"
                "async cookies(){return JSON.parse(adminSessionBytes).cookies},async storageState(){events.push('capture');return JSON.parse(adminSessionBytes)},async close(){events.push('close')}};"
                "const browser={async newContext({storageState}){must(JSON.stringify(storageState)===adminSessionBytes.toString(),'actual original state');return context}};\n")
            script=prelude+block.replace('reviewedRead(require.resolve','fixtureRead(require.resolve')+\
                "must(events.filter(value=>value.startsWith('GET ')).length===4,'same existing GET population');"\
                "must(events.indexOf('capture')<events.indexOf('close'),'capture before close');"\
                "must(result.admin_readback.checks.length===9&&result.admin_readback.complete,'nine checks');"\
                "must(result.admin_readback.final_storage_state_sha256===digest(privateRead(result.admin_readback.final_storage_state_path)),'genuine hash');"\
                "must(privateRead(ADMIN+'/browser-session.json').equals(adminSessionBytes),'original MFA file unchanged');"\
                "console.log(JSON.stringify({events,readback:result.admin_readback}));"
            completed=subprocess.run(['/usr/bin/node','--input-type=module','-'],input=script.encode(),capture_output=True,timeout=15)
            self.assertEqual(completed.returncode,0,completed.stderr.decode())
            report=json.loads(completed.stdout)['readback'];self.assertEqual(report['final_storage_state_path'],str(campaign/'admin-browser-session-after-readback.json'))
            self.assertEqual((admin/'browser-session.json').read_bytes(),original)

    def test_genuine_existing_doctor_final_state_hash_and_capture_are_bound(self):
        with tempfile.TemporaryDirectory() as temp:
            campaign=Path(temp);path=campaign/'browser-session.json';raw=v3.encode({'cookies':[],'origins':[]})
            path.write_bytes(raw);path.chmod(0o600)
            progress={'started':'2026-10-07T12:00:00Z','finished':'2026-10-07T12:05:11Z',
                'doctor_final_storage_state':{'path':str(path),'sha256':v3.sha(raw),'captured_at':'2026-10-07T12:05:10Z'}}
            with patch.object(v3,'CAMPAIGN',campaign):
                self.assertTrue(v3.validate_doctor_final_storage(progress)['complete'])
                for field,value in [('sha256','0'*64),('path',str(campaign/'elsewhere.json')),
                    ('captured_at','2026-10-07T11:59:59Z'),('captured_at','2026-10-07T12:05:12Z')]:
                    bad=copy.deepcopy(progress);bad['doctor_final_storage_state'][field]=value
                    with self.subTest(field=field),self.assertRaises(v3.Refusal):v3.validate_doctor_final_storage(bad)
                path.write_bytes(raw+b' ')
                with self.assertRaisesRegex(v3.Refusal,'actual_hash'):v3.validate_doctor_final_storage(progress)
                path.unlink();path.symlink_to(campaign/'elsewhere.json')
                with self.assertRaises((v3.Refusal,OSError)):v3.validate_doctor_final_storage(progress)

    def test_actual_independent_verifier_calls_both_final_storage_checks_before_database(self):
        raw=v3.protected(v3.FROZEN/'verify_installed_acceptance_v3.py')
        authority=v3.derive_authority(contract(),self.common,OPS,SERVED,{})
        adapted=v3.verifier_adapter(raw,self.common,authority,self.verifier,publisher_admission=lambda *args:None)
        progress={'origin':v3.ORIGIN,'browser_workflows_complete':True,'independent_readback_pending':True,
            'complete':False,'existing_records_edited':0,'release':SERVED,'started':'2026-10-07T12:00:00Z',
            'finished':'2026-10-07T12:05:11Z','cases':[{'name':name} for name in v3.CASES],
            'doctor_final_storage_state':{},'admin_readback':{'complete':True,'origin':v3.ORIGIN,
                'normal_MFA_session_reused':True,'fresh_MFA_submissions':0,'auth_reset':False,
                'department_privacy_verified':True,'started_at':'2026-10-07T12:05:01Z','finished_at':'2026-10-07T12:05:10Z',
                'checks':[{'name':name,'width':width,'status':200,'no_page_overflow':True,'accessibility_violations':[]}
                          for name in ('overview','services','organizations') for width in (1440,768,390)]}}
        events=[]
        def admin(value):events.append('admin-final');return {'complete':True}
        def doctor(value):events.append('doctor-final');return {'complete':True}
        def stop(value):events.append('database-boundary');raise v3.Refusal('fictional_stop_before_database')
        with patch.object(adapted,'v3_execution_gate',lambda:None),\
             patch.object(adapted,'protected',lambda path:v3.encode(progress)),\
             patch.object(adapted,'validate_admin_final_storage',admin),\
             patch.object(adapted,'validate_doctor_final_storage',doctor),\
             patch.object(adapted,'activation_inputs',stop):
            with self.assertRaisesRegex(v3.Refusal,'fictional_stop_before_database'):
                adapted.verify(types.SimpleNamespace(progress=str(v3.CAMPAIGN/'progress.json')))
        self.assertEqual(events,['admin-final','doctor-final','database-boundary'])

    def test_actual_frozen_verifier_adapter_retains_gate_and_full_verifier(self):
        raw = v3.protected(v3.FROZEN/'verify_installed_acceptance_v3.py')
        authority = v3.derive_authority(contract(),self.common,OPS,SERVED,{})
        publisher = lambda *args: None
        adapted = v3.verifier_adapter(raw,self.common,authority,self.verifier,publisher_admission=publisher)
        with patch.object(v3,'protected',side_effect=AssertionError('installed read')):
            with self.assertRaisesRegex(v3.Refusal,'source_protocol_unqualified'):
                adapted.verify(types.SimpleNamespace(progress=str(v3.CAMPAIGN/'progress.json'),output=str(v3.REPORT)))
        self.assertEqual(adapted.load_v3_authority(OPS,SERVED),authority)
        self.assertIs(adapted.publisher_source_admission,publisher)
        with self.assertRaises(v3.Refusal):adapted.load_v3_authority(SERVED,OPS)
        with self.assertRaisesRegex(v3.Refusal,'dependency_hash'):
            v3.verifier_adapter(raw+b'\n# foreign change',self.common,authority,self.verifier,publisher_admission=publisher)

    def publication_proof_fixture(self, workspace, deferred=False):
        from ops import publisher_verification
        root = workspace/'source'
        for relative in self.verifier.PUBLISHER_SOURCE_GRAPH:
            path = root/relative; path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes((v3.SOURCE/relative).read_bytes())
        pins = {str(root/name):v3.sha((root/name).read_bytes()) for name in self.verifier.PUBLISHER_SOURCE_GRAPH}
        inputs = [workspace/name for name in ('monitor.json','offsite.json')]
        for path in inputs: path.write_bytes(b'fictional retained operational input')
        backup = types.SimpleNamespace(__file__=str(root/'rebuild/ops/backup_restore.py'),
                                       read_private=lambda path:Path(path).read_bytes())
        offsite = types.SimpleNamespace(__file__=str(root/'rebuild/ops/offsite_backup.py'),
                                        read_private=lambda path:Path(path).read_bytes())
        status = {'condition':'fictional_backup_warning','severity':'failure','healthy':False,
            'action':'Fictional source action.','clinical_content_included':False,'monitor_age_seconds':5,
            'local_capture':{'age_seconds':100,'last_success_at':(START-timedelta(seconds=100)).isoformat()},'offsite':{}}
        def read_state():
            backup.read_private(inputs[0]); return {'last_check_at':(START-timedelta(seconds=5)).isoformat()}
        def source_status(*,at):
            backup.read_private(inputs[0]); offsite.read_private(inputs[1]); value = copy.deepcopy(status)
            value['monitor_age_seconds'] = int((at-START+timedelta(seconds=5)).total_seconds())
            value['local_capture']['age_seconds'] = int((at-START+timedelta(seconds=100)).total_seconds())
            return value,1
        alerts = types.SimpleNamespace(__file__=str(root/'rebuild/ops/backup_alerts.py'),
                                      read_state=read_state,status=source_status)
        row = {'id':'01111111-2222-4333-8444-555555555555','created_at':(START-timedelta(days=1)).isoformat(),
            'key':'backup','condition':status['condition'],'severity':'failure','healthy':False,
            'action':status['action'],'payload':{name:copy.deepcopy(status[name]) for name in
                ('clinical_content_included','monitor_age_seconds','local_capture','offsite')},
            'computed_at':'2026-10-07T12:00:00.123450+00:00','published_at':'2026-10-07T12:00:00.234560+00:00',
            'expected_interval_seconds':300}
        original = {**row,'computed_at':(START-timedelta(seconds=300)).isoformat(),
                    'published_at':(START-timedelta(seconds=299)).isoformat()}
        unit = {'InvocationID':'a'*32,'Result':'exit-code','ExecMainStatus':'1','MainPID':'0',
            'ActiveState':'failed','SubState':'failed','LoadState':'loaded',
            'FragmentPath':'/etc/systemd/system/'+v3.PUBLISHER,'DropInPaths':'','NeedDaemonReload':'no',
            'ExecMainStartTimestamp':START.strftime('%a %Y-%m-%d %H:%M:%S UTC'),
            'ExecMainExitTimestamp':(START+timedelta(seconds=1)).strftime('%a %Y-%m-%d %H:%M:%S UTC')}
        journal = [('a'*32,'Published backup status: fictional_backup_warning (failure).')]
        selected = {'row':row,'unit':unit,'journal':journal,'coherent_unit':True,
            'timer':{'ActiveState':'active','SubState':'waiting','LoadState':'loaded','UnitFileState':'enabled',
                     'FragmentPath':'/etc/systemd/system/'+v3.PUBLISHER_TIMER,'DropInPaths':'','NeedDaemonReload':'no'}}
        current = copy.deepcopy(selected)
        current.update(unit_sources={'pinned':'fictional'},selected_journal=copy.deepcopy(journal),
            unit_monotonic={'ExecMainStartTimestampMonotonic':'101000000','ExecMainExitTimestampMonotonic':'102000000'})
        current['row']['computed_at'] = '2026-10-07T12:00:00.12345+00:00'
        if deferred:
            current['unit'].update(InvocationID='b'*32,Result='success',ExecMainStatus='0',ActiveState='inactive',SubState='dead',
                ExecMainStartTimestamp=(START+timedelta(seconds=300)).strftime('%a %Y-%m-%d %H:%M:%S UTC'),
                ExecMainExitTimestamp=(START+timedelta(seconds=301)).strftime('%a %Y-%m-%d %H:%M:%S UTC'))
            current['journal'] = [('b'*32,v3.DEFERRAL_STDOUT)]
        host = v3.InstalledHost.__new__(v3.InstalledHost); host.clock = lambda:103.0
        host.publication_alignment = {'selected':selected,'unit_sources':copy.deepcopy(current['unit_sources']),
            'hold':{'acquired_monotonic':100.0,'deadline_monotonic':1000.0,'parent_pid':12345,
                    'parent_start_ticks':42,'locks':[{'path':name} for name in (*v3.LOCKS,v3.PUBLICATION_LOCK)]}}
        host.check_publication_hold = lambda:None
        host.observe_held_publication = lambda:copy.deepcopy(current)
        host.availability_verifier = self.verifier
        bridges = []; host.recovery = types.SimpleNamespace(publisher_observation_connection=lambda conn:bridges.append(conn) or conn)
        args = (original,current['row'],{key:current['unit'][key] for key in v3.PUBLISHER_JUDGE_FIELDS},current['journal'])
        def real_recheck():
            return {'row':copy.deepcopy(current['row']),
                    'unit':{key:current['unit'][key] for key in v3.PUBLISHER_JUDGE_FIELDS},'journal':copy.deepcopy(current['journal'])}
        kwargs = {'alerts':alerts,'backup':backup,'offsite':offsite,'judge':publisher_verification.judge,
            'publisher_path':root/'rebuild/core/management/commands/publish_operations_status.py',
            'expected_source_pins':pins,'recheck':real_recheck}
        return host,current,args,kwargs,bridges

    def test_full_publisher_reproduction_keeps_UUID_and_three_timestamp_representations(self):
        with tempfile.TemporaryDirectory() as temp:
            host,current,args,kwargs,bridges = self.publication_proof_fixture(Path(temp))
            unit = {key:current['unit'][key] for key in v3.PUBLISHER_JUDGE_FIELDS}
            proof = self.verifier.adjudicate_publisher(args[0],args[1],unit,current['journal'],**kwargs)
            self.assertEqual(proof['current_full_row']['id'],'01111111-2222-4333-8444-555555555555')
            self.assertTrue(proof['all_eleven_columns_accounted_for'])
            self.assertEqual(len(proof['consumed_private_inputs']),2)
            self.assertFalse(proof['publication']['backup_healthy'])
            for name,value in [('computed_at','2026-10-07T12:00:00.123451+00:00'),
                               ('action','changed'),('id','02222222-2222-4333-8444-555555555555'),
                               ('published_at','malformed'),('created_at','2026-10-06T12:00:00')]:
                def changed_recheck(name=name,value=value):
                    result = kwargs['recheck'](); result['row'][name] = value; return result
                with self.subTest(name=name),self.assertRaises((AssertionError,v3.Refusal)):
                    self.verifier.adjudicate_publisher(args[0],args[1],unit,current['journal'],
                                                       **{**kwargs,'recheck':changed_recheck})

    def test_central_wrapper_reproduces_full_previous_publication_and_actual_deferral(self):
        for deferred in (False,True):
            with self.subTest(deferred=deferred),tempfile.TemporaryDirectory() as temp:
                host,current,args,kwargs,bridges = self.publication_proof_fixture(Path(temp),deferred)
                with patch.object(v3,'captured_publisher_factory',return_value=(args,kwargs)):
                    conn = object(); proof = host.publisher_admission(conn,{}, {})
                self.assertEqual(bridges,[conn]);self.assertTrue(proof['all_eleven_columns_accounted_for'])
                self.assertEqual(len(proof['consumed_private_inputs']),2)
                self.assertEqual(proof['publication']['invocation'],'a'*32)
                self.assertEqual(proof['latest_invocation_assessment']['latest_kind'],
                    'completed_deferred_tick' if deferred else 'selected_genuine_publication')
                self.assertEqual(proof['latest_invocation_assessment']['intermediate_invocation_exit_history'],'not_assessed')
                self.assertFalse(proof['publication']['backup_healthy'])

    def test_counterfeit_deferral_current_or_selected_journal_source_and_hold_drift_refuse(self):
        changes = [('row',lambda h,c:c['row'].__setitem__('action','changed')),
            ('uuid',lambda h,c:c['row'].__setitem__('id','02222222-2222-4333-8444-555555555555')),
            ('selected_journal',lambda h,c:c['selected_journal'].clear()),
            ('latest_journal',lambda h,c:c['journal'].append(('b'*32,'Traceback (most recent call last)'))),
            ('counterfeit',lambda h,c:c.__setitem__('journal',[('c'*32,v3.DEFERRAL_STDOUT)])),
            ('result',lambda h,c:c['unit'].__setitem__('Result','exit-code')),
            ('source',lambda h,c:c['unit_sources'].__setitem__('changed',True)),
            ('timer',lambda h,c:c['timer'].__setitem__('SubState','running')),
            ('before_hold',lambda h,c:c['unit_monotonic'].__setitem__('ExecMainStartTimestampMonotonic','99000000')),
            ('after_now',lambda h,c:c['unit_monotonic'].__setitem__('ExecMainExitTimestampMonotonic','104000000'))]
        for label,change in changes:
            with self.subTest(label=label),tempfile.TemporaryDirectory() as temp:
                host,current,args,kwargs,_ = self.publication_proof_fixture(Path(temp),True);change(host,current)
                with patch.object(v3,'captured_publisher_factory',return_value=(args,kwargs)),self.assertRaises(v3.Refusal):
                    host.publisher_admission(object(),{}, {})

    def test_final_actual_callback_drift_refuses_after_full_source_reproduction(self):
        with tempfile.TemporaryDirectory() as temp:
            host,current,args,kwargs,_ = self.publication_proof_fixture(Path(temp),True)
            original = kwargs['recheck']
            def changed():
                value = original();value['unit']['InvocationID']='c'*32;return value
            with patch.object(v3,'captured_publisher_factory',return_value=(args,{**kwargs,'recheck':changed})),\
                 self.assertRaisesRegex(v3.Refusal,'actual_final_observer_binding'):
                host.publisher_admission(object(),{}, {})

    def test_full_selected_source_graph_drift_still_refuses_under_a_real_deferral(self):
        with tempfile.TemporaryDirectory() as temp:
            host,current,args,kwargs,_=self.publication_proof_fixture(Path(temp),True)
            wrong=dict(kwargs['expected_source_pins']);wrong[next(iter(wrong))]='0'*64
            with patch.object(v3,'captured_publisher_factory',return_value=(args,{**kwargs,'expected_source_pins':wrong})),\
                 self.assertRaisesRegex(AssertionError,'publisher_immutable_source'):
                host.publisher_admission(object(),{}, {})

    def test_actual_native_dependency_path_sets_unmangled_authenticated_frozen_source(self):
        host = v3.InstalledHost.__new__(v3.InstalledHost)
        host.source = v3.SOURCE; host.operations = OPS
        host.read_source = lambda path:Path(path).read_bytes()
        host.git = lambda tree,*args:Path(tree/args[1].split(':',1)[1]).read_bytes()
        host.authenticate_dependencies()
        self.assertEqual(getattr(host.availability_verifier,'__authenticated_source'),
                         v3.protected(v3.BASE/'verify_installed_acceptance_v2.py'))
        fixture = self.no_auth_fixture()
        with patch.object(socket,'create_connection',side_effect=AssertionError('socket')):
            result = v3.authenticated_rows_admission(host.availability_verifier,*fixture,'fictional fingerprint',None,{})
        self.assertIsNone(result['normal_mfa'])
        mangled = types.SimpleNamespace(_InstalledHost__authenticated_source=getattr(host.availability_verifier,'__authenticated_source'))
        with self.assertRaisesRegex(v3.Refusal,'authenticated_copy_source_required'):
            v3.authenticated_rows_admission(mangled,*fixture,'fictional fingerprint',None,{})

    def test_every_installed_admission_caller_binds_the_same_checked_publisher_wrapper(self):
        host = v3.InstalledHost.__new__(v3.InstalledHost);host.inside=True
        host.contract=contract();host.availability_raw=b'fictional availability';host.availability_verifier=self.verifier
        host.admission_raws={};host.old=types.SimpleNamespace(service_boundary=lambda *args,**kw:
            {unit:{'MainPID':str(os.getpid())} for unit in v3.UNITS})
        host.backup=object();host.storage=object();host.native=types.SimpleNamespace(worker_configuration=lambda *args:{})
        host.bind=lambda *args:None;host.command=lambda *args:b'InvocationID=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\nNeedDaemonReload=no\n'
        host.clock=lambda:100.0;host.source=v3.SOURCE;host.operations=OPS;host.served=SERVED
        host.blobs={'verify_installed_acceptance_v3.py':v3.protected(v3.FROZEN/'verify_installed_acceptance_v3.py')}
        host.common=self.common;host.authority=lambda:v3.derive_authority(contract(),self.common,OPS,SERVED,{})
        class Reached(RuntimeError):pass
        def admission(*args,**kwargs):
            self.assertEqual(kwargs['publisher_admission'],host.publisher_admission)
            self.assertIs(kwargs['verifier_override'],host.availability_verifier)
            raise Reached()
        with patch.object(v3,'installed_database_admission',side_effect=admission),\
             patch.object(v3,'installed_auth_packet',return_value={}),patch.object(v3,'protected',return_value=b'fictional env'):
            for phase in ('before-auth','after-auth'):
                with self.subTest(phase=phase),self.assertRaises(Reached):host.admit(phase,contract(),{},OPS,SERVED)
            with self.assertRaises(Reached):host.recheck_source_and_idle({},OPS,SERVED)
        def adapter(raw,common,authority,verifier,completion,publisher):
            self.assertEqual(publisher,host.publisher_admission)
            return types.SimpleNamespace(verify=lambda args:(_ for _ in ()).throw(Reached()))
        with patch.object(v3,'execution_gate'),patch.object(v3,'admit_parent_child',return_value={}),\
             patch.object(v3,'verifier_adapter',side_effect=adapter),self.assertRaises(Reached):
            v3.dispatch_verification(host,'a'*64)

    def test_raw_connection_remains_for_all_copy_catalog_work_and_checked_publisher_is_required(self):
        conn=types.SimpleNamespace(rollback=lambda:None)
        row={'id':b'01111111-2222-4333-8444-555555555555','key':b'backup'}
        original={'core_servicehealth':{'columns':list(row),'rows':[b'\t'.join(row.values())+b'\n']}}
        verifier=types.SimpleNamespace(row_mapping=self.verifier.row_mapping,
            current_copy_tables=lambda actual,*args:(self.assertIs(actual,conn) or (original,{'core_servicehealth':['id']},{})),
            continuation_database_fingerprint=lambda actual,*args:(self.assertIs(actual,conn) or {'catalog':'same'}))
        calls=[];proof={'full':'source proof'}
        def publisher(actual,old,policy):
            self.assertIs(actual,conn);self.assertEqual(old['id'],row['id']);calls.append('checked');return proof
        def semantic(*args):
            self.assertIs(args[-2],proof);return {'publisher':proof}
        with patch.object(v3,'readonly_connection_flags'),patch.object(v3,'authenticated_rows_admission',side_effect=semantic):
            result=v3.readonly_copy_admission(conn,verifier,{},original,{}, {'tables':{}},{},'fictional key','fingerprint',
                                               publisher_admission=publisher)
            self.assertTrue(result['complete']);self.assertEqual(calls,['checked'])
            with self.assertRaisesRegex(v3.Refusal,'checked_publisher_admission_required'):
                v3.readonly_copy_admission(conn,verifier,{},original,{}, {'tables':{}},{},'fictional key','fingerprint')

    def test_javascript_descriptor_io_refuses_symlink_and_replaced_output(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); canary = root/'private-canary';canary.write_bytes(b'fictional private bytes');canary.chmod(0o600)
            script = ("import fs from 'node:fs';import path from 'node:path';"
                "const must=(value,label)=>{if(!value)throw new Error(label)};"
                + 'const ADMIN='+json.dumps(str(root/'admin'))+',CAMPAIGN='+json.dumps(str(root/'campaign'))+';\n'
                + v3.JS_OWNED_IO.decode()
                + '\nconst canary='+json.dumps(str(canary))+';\n'
                + "let refused=0;function deny(fn){try{fn();}catch{refused++;return;}throw new Error('control admitted');}"
                "checkedNewDir(ADMIN,{mode:0o700});checkedNewDir(CAMPAIGN,{mode:0o700});"
                "durable(ADMIN+'/normal.json',{complete:true});deny(()=>durable(ADMIN+'/normal.json',{complete:false}));"
                "durable(CAMPAIGN+'/progress.json',{stage:1});durable(CAMPAIGN+'/progress.json',{stage:2});"
                "must(JSON.parse(privateRead(CAMPAIGN+'/progress.json')).stage===2,'own repeated progress');"
                "const progressFD=ownedOutputs.get(CAMPAIGN+'/progress.json'),priorSize=fs.fstatSync(progressFD).size;"
                "fs.unlinkSync(CAMPAIGN+'/progress.json');fs.symlinkSync(canary,CAMPAIGN+'/progress.json');"
                "deny(()=>durable(CAMPAIGN+'/progress.json',{stage:3}));must(fs.fstatSync(progressFD).size===priorSize,'no truncate before path check');"
                "const link=ADMIN+'/parent-link';fs.symlinkSync(path.dirname(canary),link);deny(()=>privateRead(link+'/private-canary'));"
                "const originalRead=fs.readFileSync;fs.readFileSync=()=>{throw new Error('private payload read');};"
                "deny(()=>reviewedRead(canary));fs.readFileSync=originalRead;"
                "fs.symlinkSync(canary,ADMIN+'/new-output');deny(()=>checkedNewRaw(ADMIN+'/new-output',Buffer.from('changed'),{mode:0o600,flag:'wx'}));"
                "deny(()=>checkedNewDir(ADMIN+'/unknown-child',{mode:0o700}));"
                "must(refused===6,'all fixed controls refused');console.log(JSON.stringify({refused,own_progress_passed:true}));")
            result = subprocess.run(['/usr/bin/node','--input-type=module','-'],input=script.encode(),capture_output=True,timeout=15)
            self.assertEqual(result.returncode,0,result.stderr.decode())
            self.assertEqual(json.loads(result.stdout)['refused'],6)
            self.assertEqual(canary.read_bytes(),b'fictional private bytes')
            self.assertEqual(canary.stat().st_mode&0o777,0o600)

    def financial(self):
        message = {'model': v3.MODEL, 'id': 'msg_Fictional', 'stop_reason': 'end_turn',
                   'usage': {'input_tokens': 100, 'output_tokens': 50, 'cache_read_input_tokens': 10,
                             'cache_creation_input_tokens': 4}}
        cost = Decimal('.000712')
        record = {'provider': 'anthropic:' + v3.MODEL, 'provider_request_id': 'req_Fictional',
                  'provider_resource_id': message['id'], 'actual_cost': cost, 'simulated': False,
                  'units': {'input_tokens': 100, 'output_tokens': 50, 'cached_input_tokens': 10, 'cache_creation_tokens': 4},
                  'rates': {'input_per_million': '2', 'output_per_million': '10', 'cached_per_million': '.20',
                            'discount_rate': '0', 'list_cost_usd': str(cost)}}
        usage = dict(record, charged_cost=cost * Decimal('1.5'))
        metadata = {key: record[key] for key in ('provider_request_id', 'provider_resource_id')}
        return message, metadata, record, usage, -usage['charged_cost'], 0

    def test_real_financial_helper_positive_and_substantive_faults(self):
        args = self.financial(); self.assertEqual(self.verifier.check_generation_financial(*args), Decimal('.000712'))
        for mutate in (lambda a: a[0].update(model='claude-sonnet-4-6'),
                       lambda a: a[0].update(stop_reason='max_tokens'), lambda a: a[0]['usage'].update(output_tokens=6001),
                       lambda a: a[2].update(provider_resource_id='msg_Other'), lambda a: a[3].update(charged_cost=Decimal('99')),
                       lambda a: a.__setitem__(4, Decimal('0')), lambda a: a.__setitem__(5, 1)):
            bad = list(copy.deepcopy(args)); mutate(bad)
            with self.subTest(fault=mutate), self.assertRaises(RuntimeError): self.verifier.check_generation_financial(*bad)

    def generation_packet(self):
        message, metadata, receipt, usage, ledger, holds = self.financial()
        values = {'History': 'Complete fictional fact.', 'Plan': 'Follow-up documented.'}
        original = docx({key: '' for key in values}); exported = docx(values)
        fields = [{'key': 'cell_' + str(index), 'label': label} for index, label in enumerate(values)]
        notes = '\n'.join(label + ': ' + value for label, value in values.items())
        selected = [{'key': field['key'], 'quotes': [values[field['label']]], 'conflict': False} for field in fields]
        message['content'] = [{'type': 'text', 'text': json.dumps({'fields': selected})}]
        raw = v3.encode({'provider_output': message})
        config = {'provider': 'anthropic', 'model': v3.MODEL, 'mode': 'live', 'pricing_version': v3.PRICING,
                  'input_rate': '2', 'output_rate': '10', 'cached_rate': '0.20',
                  'voice_rate_minute': '0.0043', 'discount_rate': '0'}
        expected = {'name': 'custom-word-typed', 'job_id': 'job', 'encounter': 'encounter', 'actor': 'doctor',
                    'department_id': 'department', 'patient_id': 'patient', 'mapping_id': 'mapping',
                    'template_id': 'template', 'sha256': v3.sha(original), 'notes_sha256': v3.sha(notes.encode()),
                    'notes': notes, 'fields': fields, 'expected': values, 'served_revision': SERVED}
        metadata.update(form_sha256=expected['sha256'], template_version_id='mapping', template_id='template',
                        department_id='department', patient_id='patient', mapping_version=1,
                        export_sha256=v3.sha(exported), fields=fields, id='job', encounter_id='encounter',
                        user_id='doctor', config=copy.deepcopy(config), result_sha256=v3.sha(raw))
        receipt['job_id'] = usage['job_id'] = 'job'
        answers = {field['key']: {'text': values[field['label']], 'status': 'supported',
                   'reviewed': True, 'reviewed_by': 'doctor'} for field in fields}
        packet = {'job': {'kind': 'generation', 'state': 'succeeded', 'id': 'job', 'encounter_id': 'encounter',
                         'user_id': 'doctor', 'config': config, 'result_sha256': v3.sha(raw)},
                  'metadata': metadata, 'receipt': receipt, 'usage': usage, 'ledger': ledger, 'holds': holds,
                  'content': {'notes': notes, 'answers': answers, 'status': 'finalized', 'finalized_by_id': 'doctor'},
                  'signed_quote_configuration': copy.deepcopy(config), 'attempt_count': 1,
                  'served_client_profile': v3.PROFILE, 'served_source_revision': SERVED, 'provider_raw': raw,
                  'selections': selected, 'accepted_values': values, 'original_docx': original, 'exported_docx': exported,
                  'normal_review_decisions_recorded': True, 'empty_finalize_refused': True, 'premature_export_refused': True}
        return packet, expected

    def test_complete_generation_admission_actual_schema_and_faults(self):
        packet, expected = self.generation_packet()
        proof = v3.generation_admission(self.verifier, packet, expected)
        self.assertEqual(proof['returned_model'], v3.MODEL)
        self.assertFalse(proof['on_wire_capture_available'])
        for mutate in (lambda p: p['job']['config'].update(model='claude-sonnet-4-6'),
                       lambda p: p['job']['config'].update(input_rate='3'),
                       lambda p: p['content']['answers']['cell_0'].update(reviewed=False),
                       lambda p: p['content']['answers']['cell_0'].update(reviewed_by='foreign'),
                       lambda p: p['content'].update(notes='changed source'),
                       lambda p: p['metadata'].update(patient_id='foreign'),
                       lambda p: p['receipt'].update(job_id='foreign-job'),
                       lambda p: p.__setitem__('attempt_count', 2),
                       lambda p: p.__setitem__('premature_export_refused', False),
                       lambda p: p.__setitem__('served_source_revision', OPS)):
            bad = copy.deepcopy(packet); mutate(bad)
            with self.subTest(fault=mutate), self.assertRaises(RuntimeError): v3.generation_admission(self.verifier, bad, expected)

    def test_original_policy_is_exact_historical_git_contract_value(self):
        raw = b'<!-- legacy-model-contract -->\n```json\n' + v3.encode({'continuation_contract': self.policy}) + b'\n```'
        self.assertEqual(v3.original_policy_admission(self.common, self.policy, {'original_policy': self.policy}, raw), self.policy)
        bad = copy.deepcopy(self.policy); bad['health_session']['expiry_seconds'] = 3600
        with self.assertRaises(v3.Refusal): v3.original_policy_admission(self.common, bad, {'original_policy': bad}, raw)

    def normal_admin_packet(self, audit_at='2026-10-07T12:00:10+00:00', last_login=None):
        before = {'read_only': True, 'database': 'quillmd_fresh', 'actor': {'id': 'fictional-staff',
            'session_version': 1, 'is_staff': True, 'is_active': True, 'last_login': '2026-10-07T11:00:00+00:00',
            'verified_at': '2026-01-01T00:00:00+00:00'}, 'device': {'id': 1, 'user_id': 'fictional-staff',
            'confirmed': True, 'step': 30, 't0': 0, 'digits': 6, 'tolerance': 1, 'drift': 0, 'last_t': 100,
            'throttling_failure_count': 0, 'throttling_failure_timestamp': None,
            'created_at': '2026-01-01T00:00:00+00:00', 'last_used_at': '2026-10-07T11:00:00+00:00'}, 'auth_audits': []}
        original = {'core_user': [{key: str(value).encode() for key, value in before['actor'].items()
                                  if key not in ('is_staff', 'is_active')}],
                    'otp_totp_totpdevice': [{key: (b'\\N' if value is None else b't' if value is True else str(value).encode())
                                           for key, value in before['device'].items()}]}
        original['core_user'][0].update(is_staff=b't', is_active=b't')
        cookies = [{'name': name, 'secure': True, 'httpOnly': True, 'sameSite': site,
                    'domain': 'app.quillmd.com', 'path': '/', 'value': 'fictional-' + name}
                   for name, site in [('__Host-quillmd_preview', 'Lax'), ('quillmd_doctor_session', 'Strict'), ('quillmd_doctor_csrf', 'Strict')]]
        session = v3.encode({'cookies': cookies}); after = copy.deepcopy(before)
        after['actor']['last_login'] = audit_at if last_login is None else last_login
        after['device'].update(last_t=101, last_used_at='2026-10-07T12:00:10+00:00')
        audit = {'actor_id': 'fictional-staff', 'action': 'auth.login', 'created_at': audit_at}
        after['auth_audits'] = [audit]; raws = [v3.encode(value) for value in (before, before, after)]
        admin = {'format': 1, 'complete': True, 'availability_first': True, 'operations_revision': OPS,
            'served_revision': SERVED, 'release': SERVED, 'origin': v3.ORIGIN, 'normal_mfa_login': True,
            'auth_reset': False, 'csrf403_no_OTP_noauththrottle': True, 'availability_receipt_sha256': '4' * 64,
            'session_cookie_name': 'quillmd_doctor_session', 'session_file': str(v3.ADMIN / 'browser-session.json'),
            'session_sha256': v3.sha(session), 'cookie_contract': {'installed_ingress_identity_verified': True,
                'HTTPS_ingress_CSRF_httpOnly': True, 'source_sha256': {'rebuild/deploy/email-private-https.conf':
                    'cbc81159b1505fd566625062517bb18dd8d4706cd30b0e334e7fdceec659f21a'}},
            'authentication_metadata': dict(zip(('before_sha256', 'invalid_csrf_sha256', 'normal_mfa_sha256'), map(v3.sha, raws))),
            'normal_login_audit': audit, 'actor_id': 'fictional-staff', 'started': '2026-10-07T12:00:00+00:00',
            'finished_at': '2026-10-07T12:00:20+00:00', 'authenticated_at': '2026-10-07T12:00:10+00:00'}
        return {'normal_raw': v3.encode(admin), 'session_raw': session,
                **dict(zip(('before_raw', 'invalid_raw', 'after_raw'), raws))}, original

    def test_auth_actual_packet_in_window_and_before_after_window_refusal(self):
        packet, original = self.normal_admin_packet()
        auth = v3.authenticated_admin(self.verifier, packet, original, OPS, SERVED, '4' * 64)
        self.assertEqual(auth['admin']['normal_login_audit']['created_at'], '2026-10-07T12:00:10+00:00')
        for date in ('1900-01-01T00:00:00+00:00', '2026-10-07T11:59:59.999999+00:00',
                     '2026-10-07T12:00:20.000001+00:00', '2126-01-01T00:00:00+00:00'):
            bad, original = self.normal_admin_packet(date)
            with self.subTest(date=date), self.assertRaisesRegex(v3.Refusal, 'measured_normal_mfa_interval'):
                v3.authenticated_admin(self.verifier, bad, original, OPS, SERVED, '4' * 64)

    def test_last_login_must_be_inside_same_window_even_when_close_to_audit(self):
        for audit_at, login_at in [('2026-10-07T12:00:00+00:00', '2026-10-07T11:59:59.5+00:00'),
                                   ('2026-10-07T12:00:20+00:00', '2026-10-07T12:00:20.5+00:00')]:
            packet, original = self.normal_admin_packet(audit_at, login_at)
            with self.assertRaisesRegex(v3.Refusal, 'measured_normal_mfa_interval'):
                v3.authenticated_admin(self.verifier, packet, original, OPS, SERVED, '4' * 64)

    def no_auth_fixture(self):
        from django.core import signing
        secret = 'fictional historical key'; health_key = b'h' * 32
        payload = {'kind': 'quillmd-preview-v1', 'flows': {'f' * 32: {'created': START.timestamp(), 'destination': '/health/'}},
                   '_session_expiry': 1800}
        with patch('django.core.signing.time.time', return_value=START.timestamp() + .25):
            data = signing.dumps(payload, key=secret, salt='django.contrib.sessions.SessionStore').encode()
        expiry = (START + timedelta(seconds=1800.5)).isoformat().encode()
        old = {'django_session': {'columns': ['session_key', 'session_data', 'expire_date'], 'rows': []},
               'core_encounter': {'columns': ['id', 'notes'], 'rows': [b'old\tunaltered original clinical fact\n']}}
        current = copy.deepcopy(old); current['django_session']['rows'] = [health_key + b'\t' + data + b'\t' + expiry + b'\n']
        keys = {'django_session': ['session_key'], 'core_encounter': ['id']}
        policy = {'original_tables': {name: {'rows': len(table['rows']), 'sha256': v3.sha(b''.join(table['rows']))} for name, table in old.items()},
                  'health_session': {'key_sha256': v3.sha(health_key), 'session_data_sha256': v3.sha(data),
                    'expire_date': expiry.decode(), 'kind': 'quillmd-preview-v1', 'expiry_seconds': 1800,
                    'no_grant_no_account_auth': True, 'destination': '/health/', 'created_at': START.isoformat(),
                    'signed_at': START.isoformat()}}
        return old, current, keys, policy, secret

    def test_actual_noauth_copy_admission_historical_signature_and_original_bytes(self):
        args = self.no_auth_fixture()
        with patch.object(socket, 'create_connection', side_effect=AssertionError('socket')) as sock:
            result = v3.authenticated_rows_admission(self.verifier, *args, 'fictional fingerprint', None, {})
            self.assertIsNone(result['normal_mfa']); self.assertEqual(sock.call_count, 0)
            self.assertEqual(result['health_session']['destination'], '/health/')
        for fault in ('changed', 'deleted', 'extra-clinical', 'second-health', 'wrong-expiry'):
            old, current, keys, policy, secret = self.no_auth_fixture()
            if fault == 'changed': current['core_encounter']['rows'] = [b'old\tchanged clinical fact\n']
            if fault == 'deleted': current['core_encounter']['rows'] = []
            if fault == 'extra-clinical': current['core_encounter']['rows'].append(b'new\tunlisted encounter\n')
            if fault == 'second-health': current['django_session']['rows'].append(b'i' * 32 + b'\tx\t' + START.isoformat().encode() + b'\n')
            if fault == 'wrong-expiry':
                parts = current['django_session']['rows'][0].split(b'\t'); parts[2] = b'2126-10-07T12:00:00+00:00\n'
                current['django_session']['rows'][0] = b'\t'.join(parts)
            with self.subTest(fault=fault), self.assertRaises(RuntimeError):
                v3.authenticated_rows_admission(self.verifier, old, current, keys, policy, secret, 'fictional fingerprint', None, {})

    def test_readonly_connection_real_statements_and_privilege_refusals(self):
        class Result:
            def __init__(self, value): self.value = value
            def fetchone(self): return self.value
        class Connection:
            def __init__(self): self.statements = []; self.read_only = 'on'; self.superuser = False
            def execute(self, statement):
                self.statements.append(statement)
                if 'current_user,current_database' in statement:
                    return Result({'current_user': 'quillmd_backup', 'current_database': 'quillmd_fresh', 'read_only': self.read_only})
                return Result({'rolsuper': self.superuser, 'rolcreatedb': False, 'rolcreaterole': False, 'rolreplication': False})
        connection = Connection(); v3.readonly_connection_flags(connection)
        self.assertEqual(connection.statements[0], 'SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
        self.assertIn("SET LOCAL statement_timeout='90s'", connection.statements)
        for name, value in (('read_only', 'off'), ('superuser', True)):
            bad = Connection(); setattr(bad, name, value)
            with self.assertRaises(v3.Refusal): v3.readonly_connection_flags(bad)

    def test_speech_duration_submission_and_cost_faults(self):
        duration = Decimal('25.636'); cost = (duration * Decimal('.0043') / 60).quantize(Decimal('.0000000001'))
        metadata = {'provider_request_id': '00000000-0000-4000-8000-000000000001', 'provider_resource_id': 'fictional-resource'}
        record = dict(metadata, provider='deepgram:nova-3-medical', actual_cost=cost, simulated=False,
            units={'duration_seconds': str(duration), 'submitted_seconds': str(duration), 'decoded_seconds': str(duration),
                   'submission_sha256': '4' * 64}, rates={'usd_per_minute': '.0043', 'discount_rate': '0', 'list_cost_usd': str(cost)})
        usage = dict(record, charged_cost=cost * Decimal('1.5'))
        args = (metadata, record, usage, -usage['charged_cost'], 0)
        self.assertEqual(self.verifier.check_speech_financial(*args), cost)
        for field, value in [('submitted_seconds', '500'), ('duration_seconds', 'NaN'), ('submission_sha256', 'short')]:
            bad = list(copy.deepcopy(args)); bad[1]['units'][field] = bad[2]['units'][field] = value
            with self.assertRaises(RuntimeError):
                self.verifier.check_speech_financial(*bad)

    def test_original_questions_and_nonanswer_parts_unchanged(self):
        values = {'History': 'Complete fictional fact.', 'Allergies': ''}
        original = docx({key: '' for key in values}); exported = docx(values)
        self.assertTrue(self.verifier.verify_export(original, exported, values)['complete_answer_values_match'])
        with self.assertRaises(RuntimeError): self.verifier.verify_export(original, docx({'Wrong question': 'Complete fictional fact.', 'Allergies': ''}), values)
        with self.assertRaises(RuntimeError): self.verifier.verify_export(original, docx({'History': 'Complete', 'Allergies': ''}), values)
        parts = self.verifier.docx_parts(exported); parts['word/header1.xml'] = b'altered letterhead'
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, 'w') as archive:
            for name, raw in parts.items(): archive.writestr(name, raw)
        with self.assertRaises(RuntimeError): self.verifier.verify_export(original, stream.getvalue(), values)

    def test_full_quotes_bare_or_labelled_and_missing_hold(self):
        case = {'notes': 'History: Complete fictional fact.\nAllergies: No known drug allergies.',
                'fields': [{'key': 'cell_0', 'label': 'History'}, {'key': 'cell_1', 'label': 'Allergies'}],
                'expected': {'History': 'Complete fictional fact.', 'Allergies': 'No known drug allergies.'}}
        bare = [{'key': field['key'], 'quotes': [case['expected'][field['label']]], 'conflict': False} for field in case['fields']]
        full = copy.deepcopy(bare)
        for row, field in zip(full, case['fields']): row['quotes'] = [field['label'] + ': ' + case['expected'][field['label']]]
        for selected in (bare, full): self.verifier.validate_first_quotes(case, selected)
        shortened = copy.deepcopy(bare); shortened[0]['quotes'] = ['fictional fact']
        with self.assertRaises(RuntimeError): self.verifier.validate_first_quotes(case, shortened)
        missing = copy.deepcopy(case); missing['notes'] = case['notes'].splitlines()[0]; missing['expected']['Allergies'] = ''
        selections = copy.deepcopy(bare); selections[1]['quotes'] = []
        self.verifier.validate_first_quotes(missing, selections)
        with self.assertRaises(RuntimeError): self.verifier.validate_first_quotes(missing, bare)

    def test_source_auth_route_adapter_no_socket_even_auth_branch(self):
        import types
        # Actual qualified function reaches its auth branch with a valid COPY
        # user row; a missing table later refuses. No substituted fake function.
        old = {'core_user': {'columns': ['id', 'email'], 'rows': [b'actor\tfictional@example.invalid\n']}}
        policy = {'original_tables': {'core_user': {'rows': 1, 'sha256': v3.sha(old['core_user']['rows'][0])}}}
        auth = {'admin': {'actor_id': 'actor', 'normal_login_audit': {'created_at': START.isoformat()}},
                'interval': (START, START + timedelta(seconds=1))}
        with patch.object(socket, 'create_connection', side_effect=AssertionError('network')) as sock:
            with self.assertRaisesRegex(RuntimeError, 'Exactly one diagnosed health'):
                v3.authenticated_rows_admission(self.verifier, old, copy.deepcopy(old), {'core_user': ['id']}, policy,
                                               'fictional secret', 'fictional fingerprint', auth, {}, '192.0.2.10')
            self.assertEqual(sock.call_count, 0)
            with self.assertRaises(v3.Refusal):
                v3.authenticated_rows_admission(self.verifier, old, copy.deepcopy(old), {'core_user': ['id']}, policy,
                                               'fictional secret', 'fictional fingerprint', auth, {}, 'invalid-ip')
            self.assertEqual(sock.call_count, 0)

    def test_final_join_refuses_missing_case_before_any_collection(self):
        with patch.object(v3, 'generation_admission', side_effect=AssertionError('should not reach cases')):
            with self.assertRaises(v3.Refusal): v3.final_admission(self.verifier, {'generation': {}}, {}, {}, OPS, SERVED)

    def test_original_session_renewal_century_and_out_of_block_refuse(self):
        from django.core import signing
        secret = 'fictional secret'; begin = datetime.now(timezone.utc) - timedelta(seconds=1)
        payload = {'_auth_user_id': 'fictional', 'otp_device_id': 'otp_totp.totpdevice/1'}
        signed = signing.dumps(payload, key=secret, salt='django.contrib.sessions.SessionStore', compress=True)
        end = datetime.now(timezone.utc) + timedelta(seconds=1)
        row = {'session_data': signed.encode(), 'expire_date': (begin + timedelta(seconds=1800.5)).isoformat().encode()}
        decoded = self.verifier.normal_session(row['session_data'], secret)
        # Use an actual timestamp from this fictional signed value; the measured
        # interval admits normal precision without a scheduler-delay assumption.
        saved = datetime.now(timezone.utc); row['expire_date'] = (saved + timedelta(seconds=1800)).isoformat().encode()
        self.verifier.validate_admin_renewal(row, decoded, (begin, end))
        for seconds in (100 * 365 * 86400, 1790, 1810, -1):
            bad = dict(row, expire_date=(saved + timedelta(seconds=seconds)).isoformat().encode())
            with self.assertRaises(RuntimeError): self.verifier.validate_admin_renewal(bad, decoded, (begin, end))


class ExposureAndFilesTests(unittest.TestCase):
    def attempts(self):
        return [{'job_id': str(index), 'kind': 'transcription' if index == 2 else 'generation',
                 'send_sequence': index + 1, 'retries': 0, 'passed': True,
                 'actual_cost': '.01', 'quote_maximum': '.20' if index == 2 else '.10'} for index in range(6)]
    def test_exact_six_attempts_and_every_unknown_stops(self):
        self.assertEqual(v3.exposure_admission(self.attempts(), complete=True)['generations'], 5)
        for key, value in [('passed', False), ('actual_cost', None), ('actual_cost', 'NaN'), ('retries', 1),
                           ('quote_maximum', '.11'), ('quote_maximum', '-1'), ('quote_maximum', '.001'),
                           ('quote_maximum', 'NaN'), ('actual_cost', '.11'), ('send_sequence', 3)]:
            rows = self.attempts(); rows[0][key] = value
            with self.subTest(key=key, value=value), self.assertRaises(v3.Refusal): v3.exposure_admission(rows)
        rows = self.attempts(); rows[-1]['job_id'] = rows[0]['job_id']
        with self.assertRaises(v3.Refusal): v3.exposure_admission(rows)
        with self.assertRaises(v3.Refusal): v3.exposure_admission(self.attempts()[:-1], complete=True)
    def test_no_current_state_baseline_replacement_and_foreign_file_refuse(self):
        before = {'files': {'old': {'sha256': 'a'}}, 'mail': {}, 'static': {'x': 'old'}, 'configuration': {'cfg': 'old'},
                  'database': {'catalog': {'columns': 'original'}, 'invariants': {'held': 0}}}
        current = copy.deepcopy(before); current['files']['new'] = {'sha256': 'b'}
        result = v3.file_catalog_admission(before, current, before['database']['catalog'], {'new': 'b'}, {'held': 0})
        self.assertTrue(result['all_old_file_metadata_bytes_preserved'])
        for label in ('configuration', 'static', 'mail', 'files'):
            bad = copy.deepcopy(current); bad[label]['unexpected'] = {'sha256': 'foreign'}
            with self.subTest(label=label), self.assertRaises(v3.Refusal):
                v3.file_catalog_admission(before, bad, before['database']['catalog'], {'new': 'b'}, {'held': 0})
        with self.assertRaises(v3.Refusal): v3.file_catalog_admission(before, current, {'columns': 'changed'}, {'new': 'b'}, {'held': 0})


def local_qualification_suite():
    """Manual host suite adds the real pinned closure to portable controls."""
    portable = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    local = type('PinnedLocalQualificationTests', (FinancialAndExportTests, unittest.TestCase), {})
    return unittest.TestSuite((portable, unittest.defaultTestLoader.loadTestsFromTestCase(local)))


if __name__ == '__main__':
    if sys.argv[1:] == ['--local-qualification']:
        result = unittest.TextTestRunner(verbosity=2).run(local_qualification_suite())
        raise SystemExit(0 if result.wasSuccessful() else 1)
    unittest.main()
