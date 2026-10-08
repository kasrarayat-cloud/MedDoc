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
CI_BEFORE = b'{"fictional-marketing-next":"16.3.6"}\n'
CI_AFTER = b'{"fictional-marketing-next":"16.3.8"}\n'
CI_MANIFEST = b'{"fictional-workspace":"marketing-only"}\n'
CI_FIXTURE_PINS = {'CI_LOCK_BEFORE_SHA': v3.sha(CI_BEFORE), 'CI_LOCK_AFTER_SHA': v3.sha(CI_AFTER),
                  'CI_MANIFEST_PINS': {name: v3.sha(CI_MANIFEST) for name in v3.CI_MANIFEST_PINS}}


def contract():
    return {'format': 3, 'origin': v3.ORIGIN, 'approved_source_paths': sorted(v3.ALLOWED),
            'source_base': v3.M6, 'dependency_sha256': v3.DEPENDENCIES,
            'ci_only_dependency_lock': v3.ci_dependency_lock_contract(),
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
    def read_source(self, path):
        if Path(path).name == v3.CI_LOCK:
            return CI_AFTER if Path(path).is_relative_to(self.source) else CI_BEFORE
        if Path(path).name == 'package.json': return CI_MANIFEST
        return declaration(self.contract) if str(path).endswith(v3.DECL) else b'fictional tracked bytes'
    def readability(self, path): self.events.append(('readability', str(path)))
    def read_ci_original(self, relative): return self.read_source(v3.ROOT / relative)
    def git(self, tree, *args):
        if args == ('rev-parse', 'HEAD'): return (self.ops if tree == self.source else self.served).encode() + b'\n'
        if args == ('rev-parse', 'origin/main'): return self.ops.encode() + b'\n'
        if args == ('branch', '--show-current'): return b'main\n'
        if args[:1] == ('status',): return b''
        if args[:1] == ('merge-base',): return b''
        if args[:1] == ('diff',): return '\n'.join(self.changed).encode()
        if args[:1] == ('log',): return COMMIT.encode() + b'\n'
        if args[:1] == ('ls-files',): return b'rebuild/core/generation.py\n'
        if args[:1] == ('show',):
            revision, relative = args[1].split(':', 1)
            if relative == v3.CI_LOCK: return CI_BEFORE if revision in (v3.M6, self.served) else CI_AFTER
            if relative in v3.CI_MANIFEST_PINS: return CI_MANIFEST
            return declaration(self.contract) if relative == v3.DECL else b'fictional tracked bytes'
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
    def recheck_phase_preservation(self):
        assert self.inside; self.events.append('phase-preservation')
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


@patch.multiple(v3, **CI_FIXTURE_PINS)
class InertAndSourceTests(unittest.TestCase):
    @patch.multiple(v3, EXECUTION_QUALIFIED=False, NATIVE_AUTHORIZATION_PROTOCOL_QUALIFIED=False,
                    FIXED_CHILD_PROTOCOL_QUALIFIED=False)
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

    @patch.multiple(v3, EXECUTION_QUALIFIED=False, NATIVE_AUTHORIZATION_PROTOCOL_QUALIFIED=False,
                    FIXED_CHILD_PROTOCOL_QUALIFIED=False)
    def test_declaration_flags_cannot_enable_source_gate(self):
        with patch.dict(os.environ, {'V3_EXECUTION_QUALIFIED': '1'}):
            for _ in (False, True):
                with self.assertRaises(v3.Refusal): v3.execution_gate()
        self.assertFalse(v3.EXECUTION_QUALIFIED)
        self.assertFalse(v3.NATIVE_AUTHORIZATION_PROTOCOL_QUALIFIED)
        self.assertFalse(v3.FIXED_CHILD_PROTOCOL_QUALIFIED)

    def test_qualified_default_still_describes_without_installed_access(self):
        with (patch.object(v3, 'protected', side_effect=AssertionError('installed read')),
              patch.object(socket, 'create_connection', side_effect=AssertionError('network')),
              patch.object(subprocess, 'Popen', side_effect=AssertionError('child')),
              patch('sys.stdout', new=io.StringIO()) as stream):
            self.assertEqual(v3.main([]), 0)
        result = json.loads(stream.getvalue())
        self.assertFalse(result['installed_state_accessed'])
        self.assertEqual((result['provider_calls'], result['authentication_submissions'], result['database_writes']), (0, 0, 0))
        self.assertTrue(all(result[name] for name in ('execution_qualified',
            'native_authorization_protocol_qualified', 'fixed_child_protocol_qualified', 'phase_preservation_protocol_qualified')))

    def test_each_source_qualification_is_independently_required(self):
        names = ('EXECUTION_QUALIFIED', 'NATIVE_AUTHORIZATION_PROTOCOL_QUALIFIED', 'FIXED_CHILD_PROTOCOL_QUALIFIED',
                 'PHASE_PRESERVATION_PROTOCOL_QUALIFIED')
        for name in names:
            values = dict.fromkeys(names, True); values[name] = False
            with self.subTest(name=name), patch.multiple(v3, **values), patch.dict(os.environ, {name: '1'}):
                with self.assertRaisesRegex(v3.Refusal, 'source_protocol_unqualified'):
                    v3.execution_gate()

    @patch.multiple(v3, EXECUTION_QUALIFIED=False, NATIVE_AUTHORIZATION_PROTOCOL_QUALIFIED=False,
                    FIXED_CHILD_PROTOCOL_QUALIFIED=False)
    def test_installed_collectors_refuse_before_roles_key_socket_or_db(self):
        with patch.object(v3, 'frozen_modules', side_effect=AssertionError('source read')), \
             patch.object(socket, 'create_connection', side_effect=AssertionError('socket')) as sock:
            for call in (lambda: v3.installed_database_admission({}), v3.installed_auth_packet):
                with self.assertRaises(v3.Refusal): call()
            self.assertEqual(sock.call_count, 0)

    @patch.multiple(v3, EXECUTION_QUALIFIED=False, NATIVE_AUTHORIZATION_PROTOCOL_QUALIFIED=False,
                    FIXED_CHILD_PROTOCOL_QUALIFIED=False)
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
            lambda h:h.normal_changes.add(v3.CI_LOCK),
            lambda h:h.normal_changes.remove('rebuild/core/tests/test_preview_access.py'),
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
            write(root,v3.CI_LOCK,CI_BEFORE)
            for relative in v3.CI_MANIFEST_PINS:write(root,relative,CI_MANIFEST)
            git(root,'add','.');git(root,'commit','-m','Fictional served baseline')
            served=git(root,'rev-parse','HEAD').strip().decode()
            source=root/'.worktrees/operations';normal=root/'.worktrees/normal'
            git(root,'worktree','add','-b','fictional-operations',str(source),served)
            host,_=self.normal_descendant_host();policy=host.normal_policy
            current=host.contract;current.update(source_base=served,served_revision=served)
            for relative in v3.ALLOWED:write(source,relative,b'fictional changed operations\n')
            write(source,v3.CI_LOCK,CI_AFTER)
            write(source,v3.DECL,declaration(current));git(source,'add','.');git(source,'commit','-m','Fictional acceptance operations')
            operations=git(source,'rev-parse','HEAD').strip().decode()
            git(root,'worktree','add','-b','fictional-normal',str(normal),operations)
            for relative in v3.NORMAL_ALLOWED:write(normal,relative,b'fictional prospective normal bytes\n')
            policy.update(source_base=operations,private_accepted_revision=served)
            write(normal,v3.NORMAL_DECL,b'<!-- owner-normal443-contract -->\n```json\n'+v3.encode(policy)+b'\n```')
            write(normal,v3.NORMAL_SELF,host.normal_module.replace(OPS.encode(),operations.encode()))
            write(normal,'rebuild/core/preview_access.py',b'OWNER_NORMAL_ORIGIN_PROTOCOL_QUALIFIED=True\n')
            write(normal,'rebuild/quillmd/settings.py',b"QUILLMD_OWNER_NORMAL_ORIGIN_ENABLED=os.getenv('QUILLMD_OWNER_NORMAL_ORIGIN_ENABLED', '0') == '1'\n")
            git(normal,'add','.');git(normal,'commit','-m','Fictional exact nine-path normal descendant')
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
                # A genuine later Git commit with a tenth used path cannot pass.
                write(normal,v3.SELF,b'changed acceptance operator in later main\n')
                git(normal,'add',v3.SELF);git(normal,'commit','-m','Fictional forbidden tenth path')
                drift=git(normal,'rev-parse','HEAD').strip().decode();git(root,'update-ref','refs/remotes/origin/main',drift)
                with self.assertRaisesRegex(v3.Refusal,'exact_nine_path_scope'):
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
            'before-auth', 'exclusive-preparation', 'after-auth', 'inside-source-idle', 'attempt', 'phase-preservation', 'phase-preservation', 'complete', 'phase-preservation', 'locks-exit'])
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


@patch.multiple(v3, **CI_FIXTURE_PINS)
class ExactCILockTests(unittest.TestCase):
    def test_only_four_operations_and_one_exact_ci_lock_are_admitted(self):
        self.assertEqual(v3.ALLOWED, v3.OPERATIONS_ALLOWED | {v3.CI_LOCK})
        self.assertEqual(len(v3.OPERATIONS_ALLOWED), 4)
        host = FakeHost()
        with patch.object(socket, 'create_connection', side_effect=AssertionError('network')), \
             patch.object(subprocess, 'Popen', side_effect=AssertionError('installer')):
            proof = v3.source_gate(host, host.contract, OPS, SERVED, host.environment)
        self.assertEqual(proof['ci_only_dependency_lock'], v3.ci_dependency_lock_contract())
        self.assertEqual(proof['ci_only_dependency_lock']['native_dependency_installs'], 0)
        self.assertFalse(proof['ci_only_dependency_lock']['future_lock_changes_admitted'])
        for change in (set(v3.OPERATIONS_ALLOWED), v3.ALLOWED | {'apps/marketing/package.json'},
                       v3.ALLOWED | {'rebuild/requirements.txt'}):
            host = FakeHost(); host.changed = sorted(change)
            with self.subTest(change=change), self.assertRaisesRegex(v3.Refusal, 'exact_ci_lock_scope'):
                v3.source_gate(host, host.contract, OPS, SERVED, host.environment)

    def test_lock_git_and_actual_worktree_before_after_bytes_are_each_required(self):
        for revision in (v3.M6, SERVED, OPS):
            host = FakeHost(); original = host.git
            def changed(tree, *args):
                if args == ('show', revision + ':' + v3.CI_LOCK): return b'unreviewed lock'
                return original(tree, *args)
            host.git = changed
            with self.subTest(revision=revision), self.assertRaisesRegex(v3.Refusal, 'exact_ci_lock_git_artifacts'):
                v3.source_gate(host, host.contract, OPS, SERVED, host.environment)
        for root in (v3.ROOT, FakeHost.source):
            host = FakeHost(); original = host.read_source
            host.read_source = lambda path: b'unreviewed or future lock' if path == root / v3.CI_LOCK else original(path)
            with self.subTest(root=root), self.assertRaisesRegex(v3.Refusal, 'exact_ci_lock_worktree_artifacts'):
                v3.source_gate(host, host.contract, OPS, SERVED, host.environment)

    def test_unchanged_workspace_manifests_are_bound_in_both_trees_and_git_history(self):
        for relative in v3.CI_MANIFEST_PINS:
            for revision in (v3.M6, SERVED, OPS):
                host = FakeHost(); original = host.git
                def changed(tree, *args):
                    if args == ('show', revision + ':' + relative): return b'changed dependency manifest'
                    return original(tree, *args)
                host.git = changed
                with self.subTest(relative=relative, revision=revision), \
                     self.assertRaisesRegex(v3.Refusal, 'unchanged_ci_workspace_manifests'):
                    v3.source_gate(host, host.contract, OPS, SERVED, host.environment)
            for root in (v3.ROOT, FakeHost.source):
                host = FakeHost(); original = host.read_source
                host.read_source = lambda path: b'changed dependency manifest' if path == root / relative else original(path)
                with self.subTest(relative=relative, root=root), \
                     self.assertRaisesRegex(v3.Refusal, 'unchanged_ci_workspace_manifests'):
                    v3.source_gate(host, host.contract, OPS, SERVED, host.environment)

    def test_missing_extended_or_typed_mismatch_ci_declaration_refuses(self):
        for mutate in (lambda value: value.pop('ci_only_dependency_lock'),
                       lambda value: value['ci_only_dependency_lock'].update(after_sha256='f' * 64),
                       lambda value: value['ci_only_dependency_lock'].update(path='another-lock.json'),
                       lambda value: value['ci_only_dependency_lock'].update(native_dependency_installs=False),
                       lambda value: value['ci_only_dependency_lock'].update(future_lock_changes_admitted=0),
                       lambda value: value['ci_only_dependency_lock'].update(unreviewed_artifact='allowed')):
            value = contract(); mutate(value)
            with self.subTest(value=value), self.assertRaisesRegex(v3.Refusal, 'exact_declared_ci_lock_correction'):
                v3.declaration_contract(declaration(value))

    def test_added_ci_sources_require_the_same_canonical_readability(self):
        for path in (FakeHost.source / v3.CI_LOCK,
                     *(FakeHost.source / relative for relative in v3.CI_MANIFEST_PINS)):
            host = FakeHost()
            host.readability = lambda current: v3.require(current != path, 'v3_fictional_ci_source_mode')
            with self.subTest(path=path), self.assertRaisesRegex(v3.Refusal, 'ci_source_mode'):
                v3.source_gate(host, host.contract, OPS, SERVED, host.environment)


class PublishedCILockPinTests(unittest.TestCase):
    def test_current_public_lock_and_unchanged_manifests_match_reviewed_raw_pins(self):
        self.assertEqual(v3.sha((v3.SOURCE / v3.CI_LOCK).read_bytes()), v3.CI_LOCK_AFTER_SHA)
        for relative, expected in v3.CI_MANIFEST_PINS.items():
            self.assertEqual(v3.sha((v3.SOURCE / relative).read_bytes()), expected)


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


class OriginalCIArtifactReaderTests(unittest.TestCase):
    def setUp(self):
        owner = patch.object(v3, 'os', FixtureOwnerOS())
        owner.start(); self.addCleanup(owner.stop)

    def inputs(self, root):
        for relative, mode in v3.CI_INSTALLED_MODES.items():
            path = root / relative; path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(CI_BEFORE if relative == v3.CI_LOCK else CI_MANIFEST); path.chmod(mode)

    def test_original_inert_inputs_keep_exact_existing_modes_and_closed_paths(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(v3, 'ROOT', Path(temp)):
            self.inputs(Path(temp))
            for relative, mode in v3.CI_INSTALLED_MODES.items():
                before = (Path(temp) / relative).stat()
                self.assertEqual(v3.ci_original_artifact(relative), CI_BEFORE if relative == v3.CI_LOCK else CI_MANIFEST)
                after = (Path(temp) / relative).stat()
                self.assertEqual((before.st_ino, stat.S_IMODE(before.st_mode)), (after.st_ino, stat.S_IMODE(after.st_mode)))
                self.assertEqual(stat.S_IMODE(after.st_mode), mode)
            with patch.object(v3, 'nofollow_file', side_effect=AssertionError('unknown artifact opened')):
                for relative in ('../package-lock.json', '/package-lock.json', 'another.json', True):
                    with self.assertRaisesRegex(v3.Refusal, 'fixed_original_ci_artifact'):
                        v3.ci_original_artifact(relative)

    def test_wrong_owner_group_mode_xattr_and_size_refuse_before_read(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(v3, 'ROOT', Path(temp)):
            self.inputs(Path(temp)); observed = v3.os.fstat
            for change in ({'st_uid': 1001}, {'st_gid': 1001}, {'st_size': 2 * 1024 * 1024 + 1}):
                def altered(fd):
                    original = observed(fd); values = vars(original).copy(); values.update(change)
                    return types.SimpleNamespace(**values)
                with self.subTest(change=change), patch.object(v3.os, 'fstat', side_effect=altered), \
                     patch.object(v3.os, 'fdopen', side_effect=AssertionError('refused bytes read')), \
                     self.assertRaisesRegex(v3.Refusal, 'original_ci_artifact_identity'):
                    v3.ci_original_artifact(v3.CI_LOCK)
            with patch.object(v3.os, 'listxattr', return_value=['user.unexpected']), \
                 self.assertRaisesRegex(v3.Refusal, 'original_ci_artifact_identity'):
                v3.ci_original_artifact(v3.CI_LOCK)
            for relative in v3.CI_INSTALLED_MODES:
                path = Path(temp) / relative; path.chmod(0o644)
                with self.subTest(relative=relative), self.assertRaisesRegex(v3.Refusal, 'original_ci_artifact_identity'):
                    v3.ci_original_artifact(relative)

    def test_links_and_replaced_inode_refuse_without_changing_original_bytes(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(v3, 'ROOT', Path(temp)):
            root = Path(temp); self.inputs(root); path = root / v3.CI_LOCK
            os.link(path, root / 'other-link')
            with self.assertRaisesRegex(v3.Refusal, 'original_ci_artifact_identity'):
                v3.ci_original_artifact(v3.CI_LOCK)
            (root / 'other-link').unlink()
            path.rename(root / 'original'); path.symlink_to(root / 'original')
            with self.assertRaises(OSError): v3.ci_original_artifact(v3.CI_LOCK)
            path.unlink(); (root / 'original').rename(path)
            actual = v3.nofollow_file; calls = []
            @contextmanager
            def replaced(current):
                calls.append(current)
                if len(calls) == 2:
                    path.rename(root / 'retained-original')
                    path.write_bytes(CI_BEFORE); path.chmod(v3.CI_INSTALLED_MODES[v3.CI_LOCK])
                with actual(current) as fd: yield fd
            with patch.object(v3, 'nofollow_file', replaced), \
                 self.assertRaisesRegex(v3.Refusal, 'original_ci_artifact_race'):
                v3.ci_original_artifact(v3.CI_LOCK)
            self.assertEqual((root / 'retained-original').read_bytes(), CI_BEFORE)


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

    @patch.multiple(v3, EXECUTION_QUALIFIED=False, NATIVE_AUTHORIZATION_PROTOCOL_QUALIFIED=False,
                    FIXED_CHILD_PROTOCOL_QUALIFIED=False)
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
        check = {'argv':['-B','-c','fictional checked native admission'], 'source_fd':9,
                 'merged_main_revision': OPS}
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

    def test_normal_auth_queries_real_main_and_compares_exact_admitted_revision(self):
        blobs = {name: v3.protected(v3.FROZEN / name) for name in v3.DEPENDENCIES}
        authority = v3.derive_authority(contract(), self.common, OPS, SERVED, {})
        for expected in (OPS, '4' * 40):
            check = {'argv':['fictional'], 'source_fd':9, 'merged_main_revision':expected}
            adapted = v3.javascript_adapter(blobs, 'normal-auth', declaration(), authority, check)
            begin = adapted.index(b" const main=execFileSync('gh'")
            end = adapted.index(b'\n', begin)
            statement = adapted[begin:end]
            for observed in (expected, '5' * 40, OPS if expected != OPS else '6' * 40):
                with self.subTest(expected=expected, observed=observed):
                    source = (b"const repository='fictional/repository',operations=" + v3.encode(OPS)
                        + b";let calls=[];function must(v,m){if(!v)throw new Error(m);};"
                        + b"function execFileSync(command,args,options){calls.push({command,args,options});return "
                        + v3.encode(observed + '\n') + b";}try{" + statement
                        + b"console.log(JSON.stringify({accepted:true,calls}));}catch(error){"
                        + b"console.log(JSON.stringify({accepted:false,calls}));}")
                    run = subprocess.run(['/usr/bin/node','--input-type=module'], input=source,
                                         cwd=v3.SOURCE, capture_output=True, timeout=15, check=True)
                    result = json.loads(run.stdout)
                    self.assertEqual(result['accepted'], observed == expected)
                    self.assertEqual(result['calls'], [{'command':'gh',
                        'args':['api','repos/fictional/repository/git/ref/heads/main','--jq','.object.sha'],
                        'options':{'cwd':str(v3.SOURCE),'encoding':'utf8','timeout':30000}}])
        for invalid in (None, '', '7' * 39, '7' * 40 + '\n'):
            with self.subTest(invalid=invalid), self.assertRaises(v3.Refusal):
                v3.javascript_adapter(blobs, 'normal-auth', declaration(), authority,
                    {'argv':['fictional'], 'source_fd':9, 'merged_main_revision':invalid})

    def test_native_bind_replaces_pin_only_after_successful_fresh_source_admission(self):
        host = v3.InstalledHost.__new__(v3.InstalledHost)
        host.environment = {}
        proof = {'merged_main':{'revision':'4' * 40}}
        with patch.object(v3, 'source_gate', return_value=proof) as gate:
            self.assertIs(host.bind(contract(), OPS, SERVED), proof)
            self.assertEqual(host.admitted_main_revision, '4' * 40)
            gate.assert_called_once_with(host, contract(), OPS, SERVED, {})
        with patch.object(v3, 'source_gate', side_effect=v3.Refusal('fresh_source_failed')):
            with self.assertRaisesRegex(v3.Refusal, 'fresh_source_failed'):
                host.bind(contract(), OPS, SERVED)
        self.assertIsNone(host.admitted_main_revision)

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

    @patch.multiple(v3, EXECUTION_QUALIFIED=False, NATIVE_AUTHORIZATION_PROTOCOL_QUALIFIED=False,
                    FIXED_CHILD_PROTOCOL_QUALIFIED=False)
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
        def adapter(raw,common,authority,verifier,completion,publisher,phase):
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


    def test_actual_frozen_configuration_adapter_preserves_raw_report_and_unrelated_checks(self):
        controls = PostRestorationConfigurationTests(); controls.setUp()
        try:
            common, _, _ = v3.frozen_modules()
            database = {'pending_jobs': 0, 'held': 0}
            before = {'configuration': controls.before, 'files': {}, 'mail': {}, 'static': {}, 'database': database}
            units = {name: {'MainPID': '123', 'ExecMainStartTimestampMonotonic': '456'} for name in common.UNITS}
            receipt = {'before': before, 'units_after': units, 'completed_at': START.isoformat(),
                       'admission': {'allowed_deltas': {'health_session': {}}}}
            report = {'format': 3, 'complete': True, 'phase': 'before-auth', 'operations_revision': OPS,
                'served_revision': SERVED, 'availability_receipt_sha256': v3.sha(v3.encode(receipt)),
                'original_activation': common.ORIGINAL, 'original_failed_sha256': common.ORIGINAL_SHA,
                'original_backup_manifest_cipher_sha256': common.BACKUP_SHA, 'original_records_adjudicated': True,
                'provider_calls': 0, 'database_writes_by_verifier': 0,
                'current_snapshot': dict(before, configuration=controls.after), 'current_database_fingerprint': database,
                'service_identities': units, 'worker_running_idle': {'unit': common.UNITS[2], 'pid': 123,
                    'start_monotonic_usec': '456', 'pending_jobs': 0, 'held_reservations': 0,
                    'unresolved_reaper_paths': 0, 'existing_job_receipt_usage_rows_unchanged': True},
                'allowed_deltas': {'health_session': {}, 'publisher': {'all_eleven_columns_accounted_for': True,
                    'publication': {'publication_verified': True}}, 'original_row_transitions': [], 'added_rows': [],
                    'normal_mfa': None}, 'started_at': START.isoformat(), 'finished_at': START.isoformat(),
                'co_tenant_preservation_admission': controls.proof}
            def check(value, hash_override=None):
                raw = v3.encode(value)
                authority = {'admissions': {'before-auth': {'path': common.PREPARATION+'/admission-before-auth.json',
                    'sha256': v3.sha(raw) if hash_override is None else hash_override}}}
                return common.admission(raw, 'before-auth', authority, receipt, OPS, SERVED, v3.sha(v3.encode(receipt)))
            self.assertEqual(check(report), report)
            self.assertEqual(report['current_snapshot']['configuration'], controls.after)
            self.assertEqual(receipt['before']['configuration'], controls.before)
            for key, value in [('complete', False), ('provider_calls', 1), ('service_identities', {}),
                               ('original_failed_sha256', 'a'*64)]:
                bad = copy.deepcopy(report); bad[key] = value
                with self.subTest(key=key), self.assertRaises(RuntimeError): check(bad)
            for label in ('files', 'mail', 'static'):
                bad = copy.deepcopy(report); bad['current_snapshot'][label]['foreign'] = True
                with self.subTest(label=label), self.assertRaises(RuntimeError): check(bad)
            with self.assertRaises(RuntimeError): check(report, 'a'*64)
            # Exercise the actual embedded Python program from the checked JS
            # adapter, importing only its pure contract module. The fictional
            # native gate is never invoked; no installed or network I/O runs.
            import re
            blobs = {name: v3.protected(v3.FROZEN/name) for name in v3.DEPENDENCIES}
            adapted = v3.javascript_adapter(blobs, 'browser', declaration(), {},
                {'argv': ['-B', '-c', 'fictional gate must never execute'], 'source_fd': 9})
            match = re.search(rb'from ("data:text/javascript;base64,[^"]+")', adapted)
            self.assertIsNotNone(match)
            uri = json.loads(match.group(1))
            javascript = ("import fs from 'node:fs';import {validateV3} from " + json.dumps(uri)
                + ";console.log(JSON.stringify(validateV3('admission',JSON.parse(fs.readFileSync(0,'utf8')))));" )
            def javascript_check(value):
                raw = v3.encode(value)
                arguments = {'phase': 'before-auth', 'authority': {'admissions': {'before-auth': {
                    'path': common.PREPARATION+'/admission-before-auth.json', 'sha256': v3.sha(raw)}}},
                    'receipt': receipt, 'operations': OPS, 'served': SERVED, 'availability_sha': v3.sha(v3.encode(receipt))}
                return subprocess.run(['/usr/bin/node', '--input-type=module', '-e', javascript],
                    input=v3.encode({'raw_hex': raw.hex(), 'receipt_raw_hex': v3.encode(receipt).hex(), 'args': arguments}), capture_output=True, timeout=15)
            passed = javascript_check(report)
            self.assertEqual(passed.returncode, 0, passed.stderr.decode())
            self.assertEqual(json.loads(passed.stdout), report)
            bad = copy.deepcopy(report); bad['current_snapshot']['configuration']['/fictional/unchanged']['inode'] = 43
            self.assertNotEqual(javascript_check(bad).returncode, 0)
        finally:
            controls.doCleanups()


    def test_actual_frozen_phase_admission_and_embedded_bridge_require_lossless_exact_packet(self):
        import re
        original, observation, _ = phase_fixture()
        database = {'pending_jobs': 0, 'held': 0}
        before = {'configuration': original, 'files': {}, 'mail': {}, 'static': {}, 'database': database}
        units = {name: {'MainPID': '123', 'ExecMainStartTimestampMonotonic': '456'} for name in self.common.UNITS}
        receipt = {'before': before, 'units_after': units, 'completed_at': START.isoformat(),
            'admission': {'allowed_deltas': {'health_session': {}}}}
        availability_sha = v3.sha(v3.encode(receipt))
        observation['binding']['availability_receipt_sha256'] = availability_sha
        proof = v3.phase_configuration_packet(original, observation)
        report = {'format': 3, 'complete': True, 'phase': 'before-auth', 'operations_revision': OPS,
            'served_revision': SERVED, 'availability_receipt_sha256': availability_sha,
            'original_activation': self.common.ORIGINAL, 'original_failed_sha256': self.common.ORIGINAL_SHA,
            'original_backup_manifest_cipher_sha256': self.common.BACKUP_SHA, 'original_records_adjudicated': True,
            'provider_calls': 0, 'database_writes_by_verifier': 0,
            'current_snapshot': dict(before, configuration=observation['configuration']),
            'current_database_fingerprint': database, 'service_identities': units,
            'worker_running_idle': {'unit': self.common.UNITS[2], 'pid': 123, 'start_monotonic_usec': '456',
                'pending_jobs': 0, 'held_reservations': 0, 'unresolved_reaper_paths': 0,
                'existing_job_receipt_usage_rows_unchanged': True},
            'allowed_deltas': {'health_session': {}, 'publisher': {'all_eleven_columns_accounted_for': True,
                'publication': {'publication_verified': True}}, 'original_row_transitions': [], 'added_rows': [],
                'normal_mfa': None}, 'started_at': START.isoformat(), 'finished_at': START.isoformat(),
            'co_tenant_preservation_admission': proof}
        phase_authority = {'path': str(v3.PHASE_PRESERVATION_PATH),
            'sha256': proof['phase_observation_sha256'], 'binding': observation['binding']}
        def arguments(value):
            raw = v3.encode(value)
            return {'phase': 'before-auth', 'authority': {'phase_preservation': phase_authority,
                'admissions': {'before-auth': {'path': str(v3.PREPARATION/'admission-before-auth.json'),
                    'sha256': v3.sha(raw)}}}, 'receipt': receipt, 'operations': OPS, 'served': SERVED,
                'availability_sha': availability_sha}
        self.assertEqual(self.common.admission(v3.encode(report), **arguments(report)), report)
        blobs = {name: v3.protected(v3.FROZEN/name) for name in v3.DEPENDENCIES}
        adapted = v3.javascript_adapter(blobs, 'browser', declaration(), {},
            {'argv': ['-B', '-c', 'fictional gate never invoked'], 'source_fd': 9})
        uri = json.loads(re.search(rb'from ("data:text/javascript;base64,[^"]+")', adapted).group(1))
        javascript = ("import fs from 'node:fs';import {validateV3} from " + json.dumps(uri)
            + ";console.log(JSON.stringify(validateV3('admission',JSON.parse(fs.readFileSync(0,'utf8')))));" )
        def checked(value):
            return subprocess.run(['/usr/bin/node', '--input-type=module', '-e', javascript],
                input=v3.encode({'raw_hex': v3.encode(value).hex(), 'receipt_raw_hex': v3.encode(receipt).hex(),
                    'args': arguments(value)}), capture_output=True, timeout=15)
        result = checked(report)
        self.assertEqual(result.returncode, 0, result.stderr.decode()[-500:])
        self.assertEqual(json.loads(result.stdout), report)
        for mutate in (lambda row: row.pop('co_tenant_preservation_admission'),
            lambda row: row.__setitem__('co_tenant_preservation_admission', {'protocol':'post-restoration-exact-owner-preservation-v1'}),
            lambda row: row['co_tenant_preservation_admission']['phase_observation']['binding'].__setitem__('parent_pid', 999)):
            bad = copy.deepcopy(report); bad['current_snapshot']['configuration'] = original; mutate(bad)
            with self.assertRaises((v3.Refusal, RuntimeError)):
                self.common.admission(v3.encode(bad), **arguments(bad))
            self.assertNotEqual(checked(bad).returncode, 0)


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


class PostRestorationConfigurationTests(unittest.TestCase):
    """Exact finite boundary controls; all inputs are fictional in-memory copies."""
    def setUp(self):
        patcher = patch.object(v3, 'POST_RESTORE_OWNER_REPLY_SHA', 'b' * 64)
        patcher.start(); self.addCleanup(patcher.stop)
        self.scope = v3.configuration_helpers({'need': v3.require})
        changes = copy.deepcopy(v3.POST_RESTORE_PINS['configuration_differences'])
        self.before = {item['path']: copy.deepcopy(item['before']) for item in changes}
        self.after = {item['path']: copy.deepcopy(item['current']) for item in changes}
        self.before['/fictional/unchanged'] = self.after['/fictional/unchanged'] = {'inode': 42, 'sha256': 'fixed'}
        self.proof = {'format': 1, 'protocol': 'post-restoration-exact-owner-preservation-v1',
            'proposal_sha256': v3.POST_RESTORE_PROPOSAL_SHA, 'owner_reply_sha256': 'b' * 64,
            'availability_receipt_sha256': v3.POST_RESTORE_PINS['availability_receipt_sha256'],
            'configuration_differences': changes,
            'product_loaded_state': copy.deepcopy(v3.POST_RESTORE_PINS['product_loaded_state']),
            'historical_deployment_authorization_verified': False,
            'current_owner_preservation_authorized': True, 'original_baseline_replaced': False,
            'voiceassistmain_changes_authorized': False}

    def check(self, before=None, after=None, proof=None):
        return self.scope['current_configuration_proof'](
            self.before if before is None else before, self.after if after is None else after,
            self.proof if proof is None else proof)

    def test_exact_four_rows_pass_without_modifying_any_input(self):
        original = copy.deepcopy((self.before, self.after, self.proof))
        self.assertTrue(self.check())
        self.assertEqual((self.before, self.after, self.proof), original)

    def test_each_undeclared_path_addition_deletion_or_change_refuses(self):
        for mode in ('add', 'delete', 'change'):
            after = copy.deepcopy(self.after)
            if mode == 'add': after['/foreign/new'] = {'inode': 1}
            elif mode == 'delete': del after['/fictional/unchanged']
            else: after['/fictional/unchanged']['inode'] = 43
            with self.subTest(mode=mode), self.assertRaises(v3.Refusal): self.check(after=after)

    def test_each_pinned_before_after_metadata_field_is_strict(self):
        for side in ('before', 'after'):
            for item in v3.POST_RESTORE_PINS['configuration_differences']:
                for field in item['current']:
                    value = copy.deepcopy(self.before if side == 'before' else self.after)
                    prior = value[item['path']][field]
                    value[item['path']][field] = prior + 1 if type(prior) is int else prior + 'foreign'
                    with self.subTest(side=side, path=item['path'], field=field), self.assertRaises(v3.Refusal):
                        self.check(**{side: value})

    def test_metadata_booleans_cannot_stand_in_for_integer_owners(self):
        after = copy.deepcopy(self.after); after[next(iter(after))]['uid'] = False
        with self.assertRaises(v3.Refusal): self.check(after=after)

    def test_unadmitted_metadata_types_and_key_population_are_preserved(self):
        self.before['/fictional/unchanged'] = {'uid': 0, 'gid': 0, 'inode': 42, 'sha256': 'fixed'}
        self.after['/fictional/unchanged'] = copy.deepcopy(self.before['/fictional/unchanged'])
        self.after['/fictional/unchanged']['uid'] = False
        with self.assertRaises(v3.Refusal): self.check()
        self.before['/fictional/unchanged'] = None
        del self.after['/fictional/unchanged']
        with self.assertRaises(v3.Refusal): self.check()
        self.assertFalse(self.scope['configuration_same']({1: 'value'}, {True: 'value'}))
        self.before[1] = 'value'; self.after[True] = 'value'
        with self.assertRaisesRegex(v3.Refusal, 'string_paths'): self.check()

    def test_unchanged_legacy_configuration_cannot_bypass_typed_comparison(self):
        before = {'configuration': {'unadmitted': {'uid': 0}}, 'files': {}, 'mail': {}, 'static': {}}
        current = dict(before, configuration={'unadmitted': {'uid': False}})
        report = {'complete': True, 'current_snapshot': current}
        raw = v3.encode(report)
        with self.assertRaises(v3.Refusal):
            self.adapter()(raw, 'before-auth', {'sha256': v3.sha(raw)}, {'before': before}, OPS, SERVED, 'c'*64)
        before['database'] = current['database'] = {'unchanged': 1}
        with self.assertRaises(v3.Refusal):
            v3.preserved_snapshot(before, current, before['database'])

    def test_original_boundary_cannot_be_replaced_by_current(self):
        with self.assertRaises(v3.Refusal): self.check(before=copy.deepcopy(self.after))

    def test_earlier_or_missing_owner_reply_and_expanded_authority_refuse(self):
        for key, value in [('owner_reply_sha256', 'a' * 64), ('proposal_sha256', 'a' * 64),
            ('availability_receipt_sha256', 'a' * 64), ('current_owner_preservation_authorized', False),
            ('historical_deployment_authorization_verified', True), ('original_baseline_replaced', True),
            ('voiceassistmain_changes_authorized', True), ('format', True)]:
            proof = copy.deepcopy(self.proof); proof[key] = value
            with self.subTest(key=key), self.assertRaises(v3.Refusal): self.check(proof=proof)
        for key in self.proof:
            proof = copy.deepcopy(self.proof); del proof[key]
            with self.subTest(missing=key), self.assertRaises(v3.Refusal): self.check(proof=proof)
        proof = copy.deepcopy(self.proof); proof['unreviewed'] = True
        with self.assertRaises(v3.Refusal): self.check(proof=proof)

    def test_product_invocation_and_unit_state_are_bound(self):
        for key in self.proof['product_loaded_state']:
            proof = copy.deepcopy(self.proof); proof['product_loaded_state'][key] += 'foreign'
            with self.subTest(key=key), self.assertRaises(v3.Refusal): self.check(proof=proof)

    def test_missing_new_reply_denies_native_before_any_input_read(self):
        with patch.object(v3, 'POST_RESTORE_OWNER_REPLY_SHA', None), \
             patch.object(v3, 'protected', side_effect=AssertionError('input read')):
            with self.assertRaisesRegex(v3.Refusal, 'owner_reply_required'):
                v3.historical_exact_external_boundary(object(), {})

    def adapter(self, raw=None):
        if raw is None:
            raw = b'''def admission(raw, phase, authority, receipt, operations, served, availability_sha):
 report = json.loads(raw)
 need(report['complete'] is True, 'original_complete')
 need(sha(raw) == authority['sha256'], 'original_raw_hash')
 snapshot = report['current_snapshot']
 for name in ('files','mail','static','configuration'):
  need(snapshot.get(name)==receipt['before'].get(name), 'original_preserved_'+name)
 return report
'''
        scope = v3.configuration_helpers({'need': v3.require, 'json': json, 'sha': v3.sha})
        exec(compile(raw, '<fictional-frozen-admission>', 'exec'), scope)
        scope['adapt_configuration_admission'](scope, raw)
        return scope['admission']

    def test_adapter_retains_original_report_hash_and_other_predicates(self):
        before = {'configuration': self.before, 'mail': {'old': 1}, 'files': {'old': 2}, 'static': {'old': 3}}
        report = {'complete': True, 'current_snapshot': dict(before, configuration=self.after),
                  'co_tenant_preservation_admission': self.proof}
        adapter = self.adapter()
        raw = v3.encode(report); authority = {'sha256': v3.sha(raw)}
        self.assertEqual(adapter(raw, 'before-auth', authority, {'before': before}, OPS, SERVED, 'c'*64), report)
        for label in ('files', 'mail', 'static'):
            bad = copy.deepcopy(report); bad['current_snapshot'][label]['old'] += 1
            raw = v3.encode(bad)
            with self.subTest(label=label), self.assertRaises(v3.Refusal):
                adapter(raw, 'before-auth', {'sha256': v3.sha(raw)}, {'before': before}, OPS, SERVED, 'c'*64)
        bad = copy.deepcopy(report); bad['complete'] = False; raw = v3.encode(bad)
        with self.assertRaises(v3.Refusal):
            adapter(raw, 'before-auth', {'sha256': v3.sha(raw)}, {'before': before}, OPS, SERVED, 'c'*64)
        with self.assertRaises(v3.Refusal):
            adapter(v3.encode(report), 'before-auth', {'sha256': 'a'*64}, {'before': before}, OPS, SERVED, 'c'*64)

    def test_adapter_rejects_frozen_predicate_drift(self):
        raw = b"def admission(*args):\n return True\n"
        with self.assertRaises(v3.Refusal): self.adapter(raw)

    def test_admission_keeps_actual_configuration_and_explicit_proof(self):
        before = {'database': {'unchanged': 1}, 'configuration': self.before, 'mail': {}, 'static': {}, 'files': {}}
        current = dict(before, configuration=self.after)
        self.assertTrue(v3.preserved_snapshot(before, current, before['database'], self.proof))
        self.assertEqual(current['configuration'], self.after)
        self.assertEqual(before['configuration'], self.before)
        with self.assertRaises(v3.Refusal): v3.preserved_snapshot(before, current, before['database'])


class PostRestorationNativeTests(unittest.TestCase):
    """Disposable descriptor fixtures; no host unit, root record or authentication access."""
    @contextmanager
    def fixture(self, receipt_change=None, reply_change=None, unit_change=None, detach=False):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); pins = copy.deepcopy(v3.POST_RESTORE_PINS)
            product = copy.deepcopy(pins['product_loaded_state'])
            manifest = {'installation_id': '8c13fe1a-5bda-4bdf-bc73-4b5cac49b1f4',
                'source_sha256': 'ee71e3c32364ca06a3a25c60f7ac45861dc1942db36565b6875be8a7e008aa26',
                'release_root': product['WorkingDirectory']}
            manifest_raw = v3.encode(manifest)
            receipt = dict(manifest, manifest_sha256=v3.sha(manifest_raw), main_pid=int(product['MainPID']),
                           installed=True, calls_started=0, provider_writes=0, nginx_changed=False)
            if receipt_change: receipt_change(receipt)
            files = {}; calls = {}; root_stat = FixtureOwnerOS()
            def represented(fd):
                info = root_stat.fstat(fd); info.st_uid = info.st_gid = 0
                return info
            metadata = lambda info: [info.st_dev, info.st_ino, info.st_uid, info.st_gid,
                stat.S_IMODE(info.st_mode), info.st_size, info.st_mtime_ns, info.st_ctime_ns]
            stable = lambda info: tuple(metadata(info))
            for index, item in enumerate(pins['current_public_records']):
                path = root / str(index)
                if item['path'].endswith('voiceassistmain-product.service'):
                    raw = b'[Service]\nWorkingDirectory=' + product['WorkingDirectory'].encode() + b'\n'
                elif item['path'] == '/etc/voiceassistmain-product.json': raw = manifest_raw
                elif item['path'].endswith('.json'): raw = v3.encode(receipt)
                else: raw = b'fictional unchanged callback configuration'
                path.write_bytes(raw); path.chmod(0o644); files[item['path'][1:]] = path
                fd = os.open(path, os.O_RDONLY)
                try: item['metadata'] = metadata(represented(fd))
                finally: os.close(fd)
                item['sha256'] = v3.sha(raw)
            proposal = {key: copy.deepcopy(value) for key, value in pins.items()}
            proposal_raw = v3.encode(proposal); proposal_sha = v3.sha(proposal_raw)
            reply = {'format': 1, 'decision': 'authorize_exact_post_restoration_preservation_boundary',
                'proposal_sha256': proposal_sha, 'owner_reply': 'fictional explicit owner reply',
                'historical_deployment_authorization_verified': False, 'voiceassistmain_changes_authorized': False}
            if reply_change: reply_change(reply)
            reply_raw = v3.encode(reply)
            @contextmanager
            def open_root(path):
                self.assertEqual(path, Path('/')); yield 123
            def open_relative(root_fd, relative):
                self.assertEqual(root_fd, 123); path = files[relative]
                calls[relative] = calls.get(relative, 0) + 1
                if detach and calls[relative] == 2:
                    replacement = root / 'detached'; replacement.write_bytes(path.read_bytes()); replacement.chmod(0o644)
                    path = replacement
                return os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
            additional = {'exact_added_files': [], 'exact_added_enablement_links': [], 'loaded_states': []}
            native = {'fixture': 'explicitly fictional native identity'}
            recovery = types.SimpleNamespace(EXTERNAL_UNIT='/etc/systemd/system/voiceassistmain-product.service',
                owner_boundary_inputs=lambda ack: ({'native_host_proof': native,
                    'additional_configuration_evidence': additional}, {'before': {}, 'after': {}}),
                acknowledge_current_owner_configuration=lambda *args: {'fictional': True},
                native_boundary_identity=lambda: copy.deepcopy(native),
                owner_unit_state=lambda name, fields: unit_change(copy.deepcopy(product)) if unit_change else copy.deepcopy(product),
                full_native_metadata=metadata,
                source_files=types.SimpleNamespace(open_root=open_root, open_relative=open_relative,
                    bytes_at=lambda fd, limit: os.read(fd, limit), stable=stable))
            shim = types.SimpleNamespace(fstat=represented, listxattr=os.listxattr, close=os.close)
            def private(path, *args):
                if path == v3.POST_RESTORE_PROPOSAL: return proposal_raw
                if path == v3.POST_RESTORE_OWNER_REPLY: return reply_raw
                raise AssertionError('unlisted private input')
            with patch.object(v3, 'POST_RESTORE_PINS', pins), \
                 patch.object(v3, 'POST_RESTORE_PROPOSAL_SHA', proposal_sha), \
                 patch.object(v3, 'POST_RESTORE_OWNER_REPLY_SHA', v3.sha(reply_raw)), \
                 patch.object(v3, 'protected', private), patch.object(v3, 'os', shim):
                yield recovery, calls

    def test_real_disposable_descriptor_bytes_and_reopens_prove_current_native_fragment(self):
        with self.fixture() as (recovery, calls):
            proof = v3.historical_exact_external_boundary(recovery, {})
            self.assertTrue(proof['configuration_admission']['current_owner_preservation_authorized'])
            self.assertFalse(proof['configuration_admission']['historical_deployment_authorization_verified'])
            self.assertEqual(len(calls), 6)
            self.assertTrue(all(count == 2 for count in calls.values()))

    def test_actual_installation_semantics_refuse_despite_matching_artifact_hash(self):
        for key, value in [('main_pid', 999), ('manifest_sha256', 'a'*64), ('installed', False),
            ('source_sha256', 'a'*64), ('release_root', '/wrong'), ('calls_started', 1),
            ('calls_started', False), ('provider_writes', 1), ('nginx_changed', True)]:
            with self.subTest(key=key), self.fixture(receipt_change=lambda row: row.update({key:value})) as (recovery, _):
                with self.assertRaisesRegex(v3.Refusal, 'installation_binding'):
                    v3.historical_exact_external_boundary(recovery, {})

    def test_native_product_identity_refuses_before_public_descriptor_access(self):
        with self.fixture(unit_change=lambda row: dict(row, InvocationID='a'*32)) as (recovery, calls):
            with self.assertRaisesRegex(v3.Refusal, 'product_state'): v3.historical_exact_external_boundary(recovery, {})
            self.assertEqual(calls, {})

    def test_native_reopen_cannot_adopt_a_replacement_inode(self):
        with self.fixture(detach=True) as (recovery, _):
            with self.assertRaisesRegex(v3.Refusal, 'public_race'): v3.historical_exact_external_boundary(recovery, {})

    def test_reply_cannot_manufacture_historical_or_mutation_authority(self):
        for key, value in [('format', True), ('decision', 'generic approval'), ('proposal_sha256', 'a'*64),
                           ('historical_deployment_authorization_verified', True), ('voiceassistmain_changes_authorized', True)]:
            with self.subTest(key=key), self.fixture(reply_change=lambda row: row.update({key:value})) as (recovery, calls):
                with self.assertRaisesRegex(v3.Refusal, 'owner_reply_scope'): v3.historical_exact_external_boundary(recovery, {})
                self.assertEqual(calls, {})


def phase_fixture(availability_sha='c' * 64):
    """Fictional full-population packet, including large measured-ns representation."""
    product = copy.deepcopy(v3.POST_RESTORE_PINS['product_loaded_state'])
    product['WorkingDirectory'] = '/opt/voiceassistmain-product/releases/' + 'd' * 24
    native = {'hostname': 'fictional-host', 'machine_id_sha256': 'a'*64, 'pid1_comm': 'systemd',
        'boot_id': 'fictional-boot', 'mount_namespace': 'mnt:[123]', 'pid_namespace': 'pid:[123]'}
    installation = '11111111-2222-4333-8444-555555555555'
    receipt_path = '/var/lib/voiceassistmain-product-installation/' + installation + '.json'
    records = {}
    for index, path in enumerate((*v3.PHASE_CONFIGURATION_PATHS, '/etc/voiceassistmain-product.json', receipt_path)):
        link = path in v3.PHASE_LINK_TARGETS
        records[path] = {'metadata': [2050, 100 + index, 0, 0, 0o777 if link else 0o644, 100,
            '1791399914209634909', '1791399914211634948'], 'nlink': 1,
            'link' if link else 'sha256': v3.PHASE_LINK_TARGETS[path] if link else 'a'*64}
    units = {name: {field: {'Id': name, 'FragmentPath': '/etc/systemd/system/' + name,
        'DropInPaths': '', 'LoadState': 'loaded', 'NeedDaemonReload': 'no', 'UnitFileState': 'enabled',
        'User': 'voiceassistmain', 'Group': 'voiceassistmain', 'WorkingDirectory': '/fictional/foreign'}[field]
        for field in fields} for name, fields in v3.PHASE_OTHER_UNIT_FIELDS.items()}
    facts = {'manifest_path': '/etc/voiceassistmain-product.json', 'installation_receipt_path': receipt_path,
        'installation_id': installation, 'current_release': product['WorkingDirectory'],
        'receipt_belongs_to_manifest_release': False, 'manifest_release_matches_loaded_unit': False,
        'receipt_manifest_hash_matches_current': False, 'receipt_pid_matches_loaded_unit': False,
        'recorded_manifest_sha256': 'b'*64, 'recorded_main_pid': '999',
        'historical_deployment_authorization_verified': False,
        'manifest_pid_mismatches_are_historical_approval_prerequisites': False}
    boundary = {'protocol': v3.PHASE_PRESERVATION_PROTOCOL, 'owner_scope_reply_sha256': v3.PRESERVATION_SCOPE_REPLY_SHA,
        'owner_history': copy.deepcopy(v3.PHASE_OWNER_HISTORY), 'native_host_proof': native,
        'product_loaded_state': product, 'additional_unit_configuration': units,
        'protected_public_records': records, 'deployment_record_facts': facts, 'voiceassist_actions': 0,
        'historical_deployment_authorization_verified': False}
    current = {}
    for path in v3.PHASE_CONFIGURATION_PATHS:
        item = records[path]; key = 'link' if path in v3.PHASE_LINK_TARGETS else 'sha256'
        current[path] = dict(zip(('device', 'inode', 'uid', 'gid', 'mode'), item['metadata'][:5]), **{key: item[key]})
    current['/opt/meddoc-pro/Caddyfile'] = {'uid': 0, 'gid': 0, 'mode': 0o644, 'device': 2050,
        'inode': 42, 'sha256': 'f'*64}
    original = copy.deepcopy(current)
    original[v3.PHASE_CONFIGURATION_PATHS[0]]['sha256'] = 'b'*64
    observation = {'format': 1, 'protocol': v3.PHASE_PRESERVATION_PROTOCOL,
        'owner_scope_reply_sha256': v3.PRESERVATION_SCOPE_REPLY_SHA,
        'historical_original_configuration_sha256': v3.sha(v3.encode(original)),
        'configuration': current, 'external_boundary': boundary,
        'captured_at': (START-timedelta(seconds=1)).isoformat(),
        'binding': {'operations_revision': OPS, 'served_revision': SERVED,
            'availability_receipt_sha256': availability_sha, 'parent_pid': 123, 'parent_start_ticks': 456,
            'preparation_directory': str(v3.PREPARATION)}}
    return original, observation, v3.phase_configuration_packet(original, observation)


class PhasePreservationTests(unittest.TestCase):
    def setUp(self):
        self.original, self.observation, self.proof = phase_fixture()
        self.helpers = v3.configuration_helpers({'need': v3.require})

    def test_whole_population_and_decimal_ns_survive_json_roundtrip_without_historical_approval(self):
        for item in self.observation['external_boundary']['protected_public_records'].values():
            for value in item['metadata'][6:]:
                self.assertIs(type(value), str)
                self.assertEqual(str(int(value)), value)
                self.assertGreater(int(value), 9007199254740991)
        after = json.loads(v3.encode(self.proof))
        self.assertEqual(after, self.proof)
        self.assertTrue(self.helpers['phase_configuration_proof'](
            self.original, self.observation['configuration'], after))
        self.assertFalse(after['historical_manifest_mismatch_resolved'])
        self.assertFalse(after['historical_deployment_authorization_verified'])

    def test_all_ten_resources_native_fields_and_meaningful_metadata_are_required(self):
        for mutate in (lambda row: row['external_boundary']['protected_public_records'].pop(v3.PHASE_CONFIGURATION_PATHS[7]),
            lambda row: row['external_boundary']['additional_unit_configuration'][next(iter(v3.PHASE_OTHER_UNIT_FIELDS))].pop('User'),
            lambda row: row['external_boundary']['protected_public_records'][v3.PHASE_CONFIGURATION_PATHS[0]]['metadata'].__setitem__(2, False),
            lambda row: row['external_boundary']['protected_public_records'][v3.PHASE_CONFIGURATION_PATHS[0]]['metadata'].__setitem__(6, 1791399914209634909),
            lambda row: row['external_boundary']['product_loaded_state'].__setitem__('NeedDaemonReload', 'yes'),
            lambda row: row['external_boundary']['protected_public_records'][v3.PHASE_CONFIGURATION_PATHS[0]].__setitem__('sha256', 'f'*64)):
            bad = copy.deepcopy(self.observation); mutate(bad)
            with self.subTest(mutation=mutate), self.assertRaises(v3.Refusal):
                v3.phase_configuration_packet(self.original, bad)

    def test_outside_scope_changed_before_phase_is_not_admitted(self):
        bad = copy.deepcopy(self.observation)
        bad['configuration']['/opt/meddoc-pro/Caddyfile']['inode'] += 1
        with self.assertRaisesRegex(v3.Refusal, 'only_scoped_external_history'):
            v3.phase_configuration_packet(self.original, bad)

    def test_reversion_to_old_configuration_never_bypasses_phase_comparison(self):
        snapshot = {'configuration': self.original, 'database': {}, 'files': {}, 'mail': {}, 'static': {}}
        before = copy.deepcopy(snapshot)
        with self.assertRaisesRegex(v3.Refusal, 'configuration_drift'):
            v3.preserved_snapshot(before, snapshot, {}, self.proof, phase_required=True)
        for missing in (None, {'protocol': 'post-restoration-exact-owner-preservation-v1'}):
            with self.assertRaisesRegex(v3.Refusal, 'phase_proof_required'):
                v3.preserved_snapshot(before, snapshot, {}, missing, phase_required=True)

    def test_actual_frozen_comparison_cannot_short_circuit_missing_or_old_phase_proof(self):
        raw = b'''def admission(raw, phase, authority, receipt, operations, served, availability_sha):
    report=json.loads(raw); snapshot=report['current_snapshot']
    for name in ('files','mail','static','configuration'):
        need(snapshot.get(name)==receipt['before'].get(name),'preserved_'+name)
    return report
'''
        scope = v3.configuration_helpers({'need': v3.require, 'json': json})
        scope['adapt_configuration_admission'](scope, raw)
        authority = {'phase_preservation': {'path': str(v3.PHASE_PRESERVATION_PATH),
            'sha256': self.proof['phase_observation_sha256'], 'binding': self.observation['binding']}}
        report = {'operations_revision': OPS, 'served_revision': SERVED, 'availability_receipt_sha256': 'c'*64,
            'started_at': START.isoformat(), 'finished_at': START.isoformat(),
            'current_snapshot': {'configuration': self.observation['configuration']},
            'co_tenant_preservation_admission': self.proof}
        receipt = {'before': {'configuration': self.original}}
        check = lambda value: scope['admission'](v3.encode(value), 'before-auth', authority, receipt, OPS, SERVED, 'c'*64)
        self.assertEqual(check(report), report)
        for proof in (None, {'protocol': 'post-restoration-exact-owner-preservation-v1'}):
            bad = copy.deepcopy(report); bad['current_snapshot']['configuration'] = self.original
            bad['co_tenant_preservation_admission'] = proof
            with self.assertRaises(v3.Refusal): check(bad)
        bad = copy.deepcopy(report); bad['co_tenant_preservation_admission']['phase_observation']['binding']['parent_pid'] += 1
        with self.assertRaises(v3.Refusal): check(bad)

    def test_child_adopts_only_exact_parent_packet_and_all_report_cross_hashes(self):
        raw = v3.encode(self.observation)
        host = types.SimpleNamespace(co_tenant_phase_observation=None, co_tenant_phase_raw=None,
            operations=OPS, served=SERVED, availability_raw=b'fictional availability',
            receipt={'before': {'configuration': self.original}}, admission_raws={})
        observation = copy.deepcopy(self.observation)
        observation['binding']['availability_receipt_sha256'] = v3.sha(host.availability_raw)
        proof = v3.phase_configuration_packet(self.original, observation); raw = v3.encode(observation)
        host.admission_raws = {'before-auth': v3.encode({'co_tenant_preservation_admission': proof})}
        context = {'parent_pid': 123, 'parent_start_ticks': 456, 'phase_preservation_sha256': v3.sha(raw),
            'authority': {'phase_preservation': {'path': str(v3.PHASE_PRESERVATION_PATH),
                'sha256': v3.sha(raw), 'binding': observation['binding']}}}
        self.assertEqual(v3.adopt_phase_observation(host, raw, context), proof)
        with self.assertRaisesRegex(v3.Refusal, 'child_phase_packet_hash'):
            v3.adopt_phase_observation(host, raw, context)
        for mutate in (lambda row: row.__setitem__('parent_pid', 999),
                       lambda row: row.__setitem__('phase_preservation_sha256', 'f'*64)):
            host.co_tenant_phase_observation = None; bad = copy.deepcopy(context); mutate(bad)
            with self.assertRaises(v3.Refusal): v3.adopt_phase_observation(host, raw, bad)

    def test_new_source_flag_is_required_before_any_installed_access(self):
        with (patch.object(v3, 'PHASE_PRESERVATION_PROTOCOL_QUALIFIED', False),
              patch.object(v3, 'protected', side_effect=AssertionError('installed read')),
              patch.object(v3, 'preservation_scope_authority', side_effect=AssertionError('owner record read'))):
            with self.assertRaisesRegex(v3.Refusal, 'source_protocol_unqualified'):
                v3.current_external_boundary(object(), {})
            with self.assertRaisesRegex(v3.Refusal, 'source_protocol_unqualified'): v3.InstalledHost()
        self.assertFalse(v3.plan()['installed_state_accessed'])

    def snapshot_host(self, observation=None, *, child=False):
        host = v3.InstalledHost.__new__(v3.InstalledHost)
        host.inside = True; host.own_hold_mode = None if child else '--execute'
        host.parent_lock_context = {'parent_pid': os.getpid(),
            'parent_start_ticks': v3.process_start(Path('/proc/self/stat').read_text())}
        host.check_publication_hold = lambda: True
        host.operations = OPS; host.served = SERVED; host.availability_raw = b'fictional availability'
        host.receipt = {'before': {'configuration': self.original}}
        host.source = Path('/fictional/source'); host.read_source = lambda path: b'fictional declaration'
        host.recovery = types.SimpleNamespace(DECL='fictional.md', contract_from_bytes=lambda raw: {'external_configuration_ack': {}})
        host.native = types.SimpleNamespace(configuration=lambda: copy.deepcopy(self.observation['configuration']))
        host.backup = object(); host.storage = object()
        host.old = types.SimpleNamespace(snapshot=lambda *args: {'configuration': copy.deepcopy(self.observation['configuration'])})
        host.co_tenant_phase_observation = observation
        host.co_tenant_phase_raw = v3.encode(observation) if observation else None
        return host

    def test_self_owned_parent_captures_once_and_child_cannot_recapture(self):
        host = self.snapshot_host()
        with patch.object(v3, 'current_external_boundary', return_value=self.observation['external_boundary']):
            first = host.snapshot(); raw = host.co_tenant_phase_raw
            self.assertEqual(host.snapshot(), first)
            self.assertEqual(host.co_tenant_phase_raw, raw)
            child = self.snapshot_host(child=True)
            with self.assertRaisesRegex(v3.Refusal, 'child_cannot_capture_new_phase_baseline'): child.snapshot()

    def test_during_and_after_configuration_native_and_saved_packet_drift_refuse(self):
        observation = copy.deepcopy(self.observation)
        host = self.snapshot_host(observation)
        with patch.object(v3, 'current_external_boundary', return_value=observation['external_boundary']), \
             patch.object(v3.os.path, 'lexists', return_value=False):
            self.assertEqual(host.recheck_phase_preservation()['phase_observation'], observation)
            host.native.configuration = lambda: copy.deepcopy(self.original)
            with self.assertRaisesRegex(v3.Refusal, 'phase_preservation_drift'): host.recheck_phase_preservation()
        host = self.snapshot_host(observation)
        bad = copy.deepcopy(observation['external_boundary']); bad['product_loaded_state']['MainPID'] = '999'
        with patch.object(v3, 'current_external_boundary', return_value=bad):
            with self.assertRaisesRegex(v3.Refusal, 'phase_preservation_drift'): host.recheck_phase_preservation()

    @patch.multiple(v3, **CI_FIXTURE_PINS)
    def test_drift_during_completion_write_preserves_stop_and_blocks_success_without_replay(self):
        host = FakeHost(); checked = []
        def phase_check():
            checked.append('check')
            if len(checked) == 3: raise v3.Refusal('v3_phase_preservation_drift')
        host.recheck_phase_preservation = phase_check
        with self.assertRaisesRegex(v3.Refusal, 'phase_preservation_drift'):
            v3.protocol_pipeline(host, contract(), OPS, SERVED)
        self.assertEqual(len(checked), 3)
        self.assertLess(host.events.index('complete'), host.events.index('STOP'))
        self.assertEqual(sum(isinstance(row, tuple) and row[0] == 'browser' for row in host.events), 1)


class PhaseNativeObservationTests(unittest.TestCase):
    """Real disposable descriptors and fictional root/unit views; no host-native reads."""
    @contextmanager
    def fixture(self, *, receipt_mismatch=False, final_invocation_race=False, detach=False, timer_transition=False,
                final_invalid_lifecycle=False):
        _, observation, _ = phase_fixture()
        expected = observation['external_boundary']; product = expected['product_loaded_state']
        paths = list(v3.PHASE_CONFIGURATION_PATHS[:8])
        additional = {'exact_added_files': [{'path': path} for path in paths[4:]],
            'exact_added_enablement_links': [{'path': path} for path in v3.PHASE_CONFIGURATION_PATHS[-2:]],
            'loaded_states': [dict(value, ActiveState='active', SubState='running')
                for value in expected['additional_unit_configuration'].values()]}
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = {'installation_id': expected['deployment_record_facts']['installation_id'],
                'release_root': product['WorkingDirectory'], 'source_sha256': 'd'*64}
            manifest_raw = v3.encode(manifest)
            receipt = dict(manifest, manifest_sha256=v3.sha(manifest_raw), main_pid=int(product['MainPID']))
            if receipt_mismatch: receipt.update(manifest_sha256='e'*64, main_pid=999, source_sha256='e'*64)
            json_files = {'/etc/voiceassistmain-product.json': manifest_raw,
                expected['deployment_record_facts']['installation_receipt_path']: v3.encode(receipt)}
            for path in (*paths, *json_files):
                target = root / path[1:]; target.parent.mkdir(parents=True, exist_ok=True)
                raw = json_files.get(path, b'fictional foreign configuration\n')
                if path == product['FragmentPath']:
                    raw = b'[Service]\nWorkingDirectory=' + product['WorkingDirectory'].encode() + b'\n'
                target.write_bytes(raw); target.chmod(0o644)
            for path, target in v3.PHASE_LINK_TARGETS.items():
                link = root/path[1:]; link.parent.mkdir(parents=True, exist_ok=True); link.symlink_to(target)
            def root_view(info):
                values = {name: getattr(info, name) for name in dir(info) if name.startswith('st_')}
                values.update(st_uid=0, st_gid=0)
                return types.SimpleNamespace(**values)
            shim = types.SimpleNamespace(fstat=lambda fd: root_view(os.fstat(fd)),
                stat=lambda *args, **kwargs: root_view(os.stat(*args, **kwargs)),
                listxattr=os.listxattr, close=os.close, readlink=os.readlink)
            metadata = lambda info: [info.st_dev, info.st_ino, info.st_uid, info.st_gid,
                stat.S_IMODE(info.st_mode), info.st_size, info.st_mtime_ns, info.st_ctime_ns]
            @contextmanager
            def open_root(path):
                self.assertEqual(path, Path('/'))
                fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
                try: yield fd
                finally: os.close(fd)
            reads = []; counts = {}
            def open_relative(root_fd, relative, directory=False):
                reads.append(relative); counts[relative] = counts.get(relative, 0) + 1
                if detach and relative == paths[0][1:] and counts[relative] == 2:
                    target=root/relative; replacement=root/'replacement'
                    replacement.write_bytes(target.read_bytes()); replacement.chmod(0o644); replacement.replace(target)
                return os.open(relative, os.O_RDONLY | os.O_NOFOLLOW | (os.O_DIRECTORY if directory else 0), dir_fd=root_fd)
            unit_counts = {}
            def unit_state(name, fields):
                unit_counts[name] = unit_counts.get(name, 0) + 1
                if name == 'voiceassistmain-product.service':
                    result = copy.deepcopy(product)
                    if final_invocation_race and unit_counts[name] == 3: result['InvocationID'] = 'f'*32
                else:
                    result = dict(expected['additional_unit_configuration'][name], ActiveState='active',
                        SubState='waiting' if name.endswith('.timer') else 'running')
                    if timer_transition and name.endswith('.timer') and unit_counts[name] > 1:
                        result.update(ActiveState='inactive', SubState='elapsed')
                    if final_invalid_lifecycle and name.endswith('.timer') and unit_counts[name] == 3:
                        result['SubState'] = 'unrecognized-state'
                self.assertEqual(set(result), set(fields))
                return result
            recovery = types.SimpleNamespace(EXTERNAL_UNIT=product['FragmentPath'],
                CURRENT_OWNER_PINS={'added_links': v3.PHASE_LINK_TARGETS},
                owner_boundary_inputs=lambda ack: ({'native_host_proof': expected['native_host_proof'],
                    'additional_configuration_evidence': additional}, {'before': {}, 'after': {}}),
                acknowledge_current_owner_configuration=lambda *args: None,
                native_boundary_identity=lambda: copy.deepcopy(expected['native_host_proof']),
                owner_unit_state=unit_state, full_native_metadata=metadata,
                source_files=types.SimpleNamespace(open_root=open_root, open_relative=open_relative,
                    bytes_at=lambda fd, bound: os.read(fd, bound), stable=lambda info: tuple(metadata(info))))
            with patch.object(v3, 'os', shim), patch.object(v3, 'preservation_scope_authority', return_value=v3.PHASE_OWNER_HISTORY):
                yield recovery, reads

    def test_finite_disposable_reader_reopens_each_record_and_does_not_scan_release(self):
        with self.fixture() as (recovery, reads):
            proof = v3.current_external_boundary(recovery, {})
            self.assertEqual(len(proof['protected_public_records']), 12)
            self.assertTrue(proof['deployment_record_facts']['receipt_pid_matches_loaded_unit'])
            self.assertFalse(proof['historical_deployment_authorization_verified'])
            self.assertFalse(any('/releases/' in path for path in reads))
            for path, item in proof['protected_public_records'].items():
                if 'sha256' in item: self.assertEqual(reads.count(path[1:]), 4)
                self.assertTrue(all(type(value) is str for value in item['metadata'][6:]))

    def test_current_receipt_hash_pid_and_source_mismatches_remain_recorded_nonprerequisites(self):
        with self.fixture(receipt_mismatch=True) as (recovery, _):
            proof = v3.current_external_boundary(recovery, {})
            facts = proof['deployment_record_facts']
            self.assertFalse(facts['receipt_belongs_to_manifest_release'])
            self.assertFalse(facts['receipt_manifest_hash_matches_current'])
            self.assertFalse(facts['receipt_pid_matches_loaded_unit'])
            self.assertFalse(facts['manifest_pid_mismatches_are_historical_approval_prerequisites'])

    def test_replaced_inode_and_invocation_during_final_file_reopen_refuse(self):
        for value, label in (({'detach': True}, 'public_race'),
                             ({'final_invocation_race': True}, 'final_loaded_identity_race')):
            with self.subTest(value=value), self.fixture(**value) as (recovery, _):
                with self.assertRaisesRegex(v3.Refusal, label): v3.current_external_boundary(recovery, {})

    def test_natural_timer_lifecycle_is_explicit_and_preserves_configuration(self):
        with self.fixture(timer_transition=True) as (recovery, _):
            proof = v3.current_external_boundary(recovery, {})
            timer = proof['additional_unit_configuration']['voiceassist-restaurant-tajrish-20261007-retention.timer']
            self.assertEqual(set(timer), set(v3.PHASE_OTHER_UNIT_FIELDS['voiceassist-restaurant-tajrish-20261007-retention.timer']))
            self.assertNotIn('ActiveState', timer); self.assertNotIn('SubState', timer)

    def test_final_reread_does_not_hide_an_unrecognized_lifecycle_state(self):
        with self.fixture(final_invalid_lifecycle=True) as (recovery, _):
            with self.assertRaisesRegex(v3.Refusal, 'other_unit_population'):
                v3.current_external_boundary(recovery, {})


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
