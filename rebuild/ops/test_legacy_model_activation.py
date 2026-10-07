"""Refusal/preservation proofs using invented bytes; no installed state access."""
from contextlib import ExitStack, contextmanager, nullcontext, redirect_stdout
from copy import deepcopy
from io import StringIO
import json
import errno
import os
import hashlib
import gzip
import subprocess
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import Mock, patch

try:
    from ops import legacy_model_activation as act
except ImportError:
    import legacy_model_activation as act


def environment():
    return (('QUILLMD_RELEASE_SHA=' + act.BASELINE + '\n') +
            'QUILLMD_AI_MODE=live\nQUILLMD_AI_PROVIDER=anthropic\nQUILLMD_DATA_MODE=synthetic\n'
            'QUILLMD_PREVIEW_AUTH_ENABLED=1\nQUILLMD_APP_BASE_URL=https://app.quillmd.com:9443\n'
            'QUILLMD_AI_MODEL=gpt-4.1-mini\nQUILLMD_AI_INPUT_RATE=0.4\n'
            'QUILLMD_AI_OUTPUT_RATE=1.6\nQUILLMD_AI_CACHED_RATE=0.1\n'
            'QUILLMD_AI_MODEL=claude-sonnet-4-6\nQUILLMD_AI_INPUT_RATE=3\n'
            'QUILLMD_AI_OUTPUT_RATE=15\nQUILLMD_AI_CACHED_RATE=0.3\n'
            'FICTIONAL_SECRET="literal $value #quoted"\n# retain this exact comment\n').encode()


def qualification():
    value = {'format': 1, 'source_sha': act.BASELINE, 'qualified_for_legacy_config_demo': True,
             'model': 'claude-sonnet-5-5', 'provider': 'anthropic', 'request_profile': dict(act.PROFILE),
             'rates': dict(act.MODEL_VALUES), 'unsafe_findings': 0,
             'outcomes': {name: True for name in act.OUTCOMES},
             'candidate_install': False, 'patient_admission': False, 'public_launch': False}
    request = {'method': 'POST', 'url': 'https://api.anthropic.com/v1/messages',
               'body_json': {'model': 'claude-sonnet-5-5', 'max_tokens': 6000,
                             'system': 'Fictional source mapping only', 'messages': [{'role': 'user', 'content': 'fiction'}],
                             'output_config': {'format': {'type': 'json_schema', 'schema': {'type': 'object'}}}}}
    response = {'status_code': 200, 'request_id': 'req_fictional',
                'body_json': {'model': 'claude-sonnet-5-5', 'id': 'msg_fictional',
                              'stop_reason': 'end_turn', 'usage': {'input_tokens': 2, 'output_tokens': 1}}}
    evidence = {name: b'{"fictional":true}\n' for name in act.EVIDENCE_ROLES}
    evidence.update(request=act.encode(request), response=act.encode(response))
    return value, evidence, request, response


def public_write(path, raw):
    path.parent.mkdir(parents=True, exist_ok=True)
    for parent in (path.parent, *path.parents):
        if parent.name in ('source', 'stage', 'staticfiles', 'fonts', 'django_otp', 'otp_totp', 'css', 'js'):
            parent.chmod(0o755)
    path.write_bytes(raw);path.chmod(0o644)


def static_fixture(root):
    source, stage = root / 'source', root / 'stage'
    stage.mkdir(mode=0o755)
    inputs, manifest = {}, {'version': '1.1', 'paths': {}}
    values = {name: ('fictional ' + name).encode() for name in act.STATIC_INPUTS}
    values['app.css'] = b'@font-face{src:url("fonts/dm-sans.ttf")}body{color:#123}'
    font_name = 'fonts/dm-sans.' + hashlib.md5(values['fonts/dm-sans.ttf']).hexdigest()[:12] + '.ttf'
    for name, raw in values.items():
        inputs[name] = source / name;public_write(inputs[name], raw)
        compiled_bytes = raw.replace(b'fonts/dm-sans.ttf', font_name.encode()) if name == 'app.css' else raw
        path = act.PurePosixPath(name)
        compiled = str(path.with_suffix('')) + '.' + hashlib.md5(compiled_bytes).hexdigest()[:12] + path.suffix
        manifest['paths'][name] = compiled
        public_write(stage / name, raw);public_write(stage / compiled, compiled_bytes)
        public_write(stage / (compiled + '.gz'), gzip.compress(compiled_bytes, mtime=0))
    manifest['hash'] = hashlib.md5(json.dumps(sorted(manifest['paths'].items())).encode()).hexdigest()[:12]
    public_write(stage / 'staticfiles.json', act.encode(manifest))
    return inputs, stage, manifest


class EnvironmentPreservation(unittest.TestCase):
    def test_all_duplicate_occurrences_and_unrelated_literal_bytes(self):
        original = environment()
        updated, report = act.render(original, act.BASELINE)
        self.assertEqual(report['assignment_counts'], {key: 2 for key in act.MODEL_VALUES})
        self.assertEqual(updated.count(b'QUILLMD_AI_MODEL="claude-sonnet-5-5"\n'), 2)
        self.assertIn(b'FICTIONAL_SECRET="literal $value #quoted"\n# retain this exact comment\n', updated)
        self.assertIn(('QUILLMD_RELEASE_SHA=' + act.BASELINE + '\n').encode(), updated)

    def test_gate_profile_model_serialization_and_missing_assignment_refuse(self):
        original = environment()
        unsafe = [original.replace(b'AUTH_ENABLED=1', b'AUTH_ENABLED=0'),
                  original + b'QUILLMD_V3_GENERATION_BATCHES=1\n',
                  original.replace(b'claude-sonnet-4-6', b'claude-sonnet-5-5'),
                  original.replace(b'QUILLMD_AI_CACHED_RATE=', b'OTHER_CACHED_RATE='), original[:-1]]
        for raw in unsafe:
            with self.subTest(raw_sha256=act.sha(raw)), self.assertRaises(act.Refusal):
                act.render(raw, act.BASELINE)
        with self.assertRaises(act.Refusal):
            act.render(original, 'abbreviated')

    def test_rollback_recovers_exact_original_population_and_only_safe_source_stamp(self):
        original = environment()
        target = '1' * 40
        changed, _ = act.render(original, target)
        self.assertEqual(act.restore_environment(original, changed, act.BASELINE), original)
        recovered = act.restore_environment(original, changed, target)
        self.assertIn(b'QUILLMD_AI_MODEL=gpt-4.1-mini\n', recovered)
        self.assertIn(b'QUILLMD_AI_MODEL=claude-sonnet-4-6\n', recovered)
        self.assertEqual(recovered.replace(('QUILLMD_RELEASE_SHA="' + target + '"\n').encode(),
                                           ('QUILLMD_RELEASE_SHA=' + act.BASELINE + '\n').encode()), original)
        with self.assertRaises(act.Refusal):
            act.restore_environment(original, changed.replace(b'$value', b'$intervening'), target)


class QualificationRefusals(unittest.TestCase):
    def test_positive_control_and_independent_raw_model_response_checks(self):
        value, evidence, _, response = qualification()
        self.assertEqual(act.validate_qualification(value, evidence)['response_model'], 'claude-sonnet-5-5')
        for field, bad in (('model', 'claude-sonnet-4-6'), ('stop_reason', 'max_tokens')):
            changed = deepcopy(response)
            changed['body_json'][field] = bad
            with self.subTest(field=field), self.assertRaises(act.Refusal):
                act.validate_qualification(value, {**evidence, 'response': act.encode(changed)})

    def test_newer_profile_corpus_receipt_or_missing_workflow_cannot_qualify_legacy(self):
        value, evidence, request, _ = qualification()
        for changes in ({'max_tokens': 20000}, {'thinking': {'type': 'adaptive'}},
                        {'output_config': {'format': {'type': 'json_schema'}, 'effort': 'medium'}}):
            changed = deepcopy(request)
            changed['body_json'].update(changes)
            with self.subTest(changes=changes), self.assertRaises(act.Refusal):
                act.validate_qualification(value, {**evidence, 'request': act.encode(changed)})
        for changed in ({**value, 'unsafe_findings': False}, {**value, 'candidate_install': True},
                        {**value, 'outcomes': {**value['outcomes'], 'voice': False}},
                        {**value, 'source_sha': '2' * 40}):
            with self.assertRaises(act.Refusal):
                act.validate_qualification(changed, evidence)

    def test_protected_evidence_hash_failure_refuses_before_parsing(self):
        with patch.object(act, 'protected', return_value=b'fictional bytes'), self.assertRaises(act.Refusal):
            act.read_qualification(act.RUNTIME / 'fictional.json', '0' * 64)


class ContinuationPreservation(unittest.TestCase):
    def test_continuation_source_gate_requires_only_four_repairs_and_all_exact_citations(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary);source = root/'.worktrees/proposed';source.mkdir(parents=True)
            installed = root/act.SELF;installed.parent.mkdir(parents=True);installed.write_bytes(b'invented-installed-M')
            decl = source/act.DECL;decl.parent.mkdir(parents=True);decl.write_bytes(b'invented-committed-authority')
            target = '8' * 40;extra = [False]
            paths = sorted(act.CONTINUATION_REPAIRS)
            def git(tree, *args):
                if args == ('rev-parse', 'HEAD'):return (target if tree == source else act.CONTINUATION_RELEASE).encode()
                if args == ('rev-parse', 'origin/main'):return target.encode()
                if args == ('branch', '--show-current'):return b'main'
                if args[:2] == ('status', '--porcelain'):return b''
                if args[:2] == ('merge-base', '--is-ancestor'):return b''
                if args[:2] == ('diff', '--name-only'):
                    return '\n'.join(paths + (['rebuild/templates/encounter_form.html'] if extra[0] else [])).encode()
                if args == ('ls-files', 'rebuild'):return act.SELF.encode()
                if args[:3] == ('log', '-1', '--format=%H'):return target.encode()
                if args == ('show', target + ':' + act.DECL):return decl.read_bytes()
                if args == ('show', act.CONTINUATION_RELEASE + ':' + act.SELF):return installed.read_bytes()
                raise AssertionError((tree, args))
            contract = {'execution_qualified': True, 'baseline': act.BASELINE, 'approved_source_paths': paths}
            with patch.multiple(act, ROOT=root, SOURCE=source, DEPENDENCIES=()), \
                    patch.object(act, 'git', side_effect=git), \
                    patch.object(act, 'continuation_policy', return_value={'repair_source_paths': paths}), \
                    patch.object(act, 'command') as command, \
                    patch.dict(act.os.environ, RULED_MUTATION_DECLARATION=act.DECL, RULED_MUTATION_DECL_COMMIT=target):
                self.assertEqual(act.source_gate(target, contract, executing=True, resuming=True)['shared_head'],
                                 act.CONTINUATION_RELEASE)
                self.assertEqual([call.args[0][-1] for call in command.call_args_list],
                                 [target, act.BASELINE, act.CONTINUATION_RELEASE])
                command.reset_mock();extra[0] = True
                with self.assertRaisesRegex(act.Refusal, 'continuation_source_scope'):
                    act.source_gate(target, contract, executing=True, resuming=True)
                command.assert_not_called()

    def test_only_exact_prospective_qualified_phase_and_reviewed_children_are_admitted(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary);auth = root/'auth.mjs';verifier = root/'verify.py'
            for path in (auth, verifier):path.write_bytes(b'reviewed invented child');path.chmod(0o600)
            policy = {'qualified': True, 'original_activation': str(act.CONTINUATION_ORIGINAL),
                      'original_release': act.CONTINUATION_RELEASE, 'original_receipts': act.CONTINUATION_RECEIPTS,
                      'repair_source_paths': sorted(act.CONTINUATION_REPAIRS), 'resume_output': str(root/'resume'),
                      'resume_attempt_marker': str(root/'marker'), 'admin_evidence_directory': str(root/'admin'),
                      'admin_preparation_path': str(auth), 'admission_verifier_path': str(verifier),
                      'admin_preparation_sha256': act.sha(auth.read_bytes()),
                      'admission_verifier_sha256': act.sha(verifier.read_bytes()),
                      'preparation_maximum_seconds': 180, 'original_backup_reused': True, 'new_capture': False,
                      'provider_calls': 0, 'automatic_retries': False, 'publisher_admission_policy': {'qualified': True}}
            with patch.multiple(act, CONTINUATION_OUTPUT=root/'resume', CONTINUATION_ATTEMPT=root/'marker',
                                CONTINUATION_ADMIN=root/'admin', CONTINUATION_PREPARATION=auth, ACCEPTANCE_VERIFIER=verifier):
                self.assertEqual(act.continuation_policy({'continuation_contract': policy}), policy)
                for name, value in (('qualified', False), ('original_activation', '/wrong/attempt'),
                                    ('resume_output', str(root/'alias')), ('new_capture', True),
                                    ('provider_calls', 1), ('automatic_retries', True),
                                    ('repair_source_paths', sorted(act.CONTINUATION_REPAIRS | {'rebuild/core/jobs.py'})),
                                    ('publisher_admission_policy', {'qualified': False})):
                    changed = dict(policy);changed[name] = value
                    with self.subTest(name=name), self.assertRaises(act.Refusal):
                        act.continuation_policy({'continuation_contract': changed})
                verifier.write_bytes(b'changed after review')
                with self.assertRaisesRegex(act.Refusal, 'reviewed_artifact'):
                    act.continuation_policy({'continuation_contract': policy})

    def test_fixed_adjudicator_is_target_bound_and_current_population_and_every_nondatabase_field_are_rechecked(self):
        for fault in (None, 'release', 'old-proof', 'catalog-race', 'file-race', 'mail-race', 'static-race', 'security-race'):
            with self.subTest(fault=fault), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary);verifier = root/'verify.py';verifier.write_bytes(b'qualified');verifier.chmod(0o600)
                population = {'database': {'tables': {}, 'catalog': {'columns': 'exact'}, 'invariants': {},
                                          'pending_jobs': 0, 'held': 0, 'referenced_files': {}},
                              'files': {}, 'mail': {}, 'static': {}, 'configuration': {}}
                report = {'format': 1, 'complete': True, 'phase': 'before-auth', 'release': '8' * 40,
                          'original_activation': str(act.CONTINUATION_ORIGINAL),
                          'original_failed_sha256': act.CONTINUATION_RECEIPTS['failed.json'],
                          'original_backup_manifest_cipher_sha256': 'a' * 64, 'original_records_adjudicated': True,
                          'provider_calls': 0, 'database_writes': 0, 'current_database_fingerprint': population['database']}
                if fault == 'release':report['release'] = '9' * 40
                if fault == 'old-proof':report['original_failed_sha256'] = '0' * 64
                report_path = root/'admission-before-auth.json';raw = act.encode(report)
                report_path.write_bytes(raw);report_path.chmod(0o600)
                summary = {'complete': True, 'phase': 'before-auth', 'release': '8' * 40,
                           'report': str(report_path), 'sha256': act.sha(raw), 'provider_calls': 0,
                           'database_writes': 0, 'current_database_fingerprint': population['database']}
                stdout = act.encode(summary);stdout_path = root/'admission-before-auth-stdout.log'
                stdout_path.write_bytes(stdout);stdout_path.chmod(0o600)
                actual = deepcopy(population)
                if fault == 'catalog-race':actual['database']['catalog']['columns'] = 'unknown'
                for key, label in (('files', 'file-race'), ('mail', 'mail-race'), ('static', 'static-race'),
                                   ('configuration', 'security-race')):
                    if fault == label:actual[key]['unknown'] = {'sha256': 'new'}
                child = Mock(return_value={'stdout_sha256': act.sha(stdout)})
                with patch.multiple(act, CONTINUATION_OUTPUT=root, ACCEPTANCE_VERIFIER=verifier), \
                        patch.object(act, 'acceptance_child', child), patch.object(act, 'snapshot', return_value=actual):
                    args = ('before-auth', '8' * 40, root, {'admission_verifier_sha256': act.sha(verifier.read_bytes())},
                            {'backup': {'manifest_cipher_sha256': 'a' * 64}, 'expected_population': population})
                    kwargs = dict(host=Mock(), backup=Mock(), storage=Mock(), deadline=act.time.monotonic()+10)
                    if fault:
                        with self.assertRaises(act.Refusal):act.continuation_admission(*args, **kwargs)
                    else:
                        evidence, current = act.continuation_admission(*args, **kwargs)
                        self.assertEqual(current, population);self.assertEqual(evidence['sha256'], act.sha(raw))
                    self.assertEqual(child.call_count, 1)
                    self.assertEqual(child.call_args.args[0][-4:], ['--phase', 'before-auth', '--continuation-directory', str(root)])

    def test_structural_health_never_creates_an_anonymous_preview_session(self):
        target = '4' * 40
        def get(url, **kwargs):
            if ':9130/' in url or ':9131/' in url:
                return SimpleNamespace(status_code=200, json=lambda: {
                    'release': target, 'surface': 'doctor' if ':9130/' in url else 'admin',
                    'data_mode': 'synthetic-only'})
            status = 200 if url == 'https://quillmd.com/' else 410 if url == 'https://pro.quillmd.com/' else 503
            return SimpleNamespace(status_code=status, headers={'retry-after': '3600', 'cache-control': 'no-store'})
        with patch('httpx.get', side_effect=get), patch('httpx.Client') as client:
            act.health(target)
            client.assert_not_called()
            response = SimpleNamespace(status_code=302, headers={'location': '/preview/sign-in/?flow=' + 'a' * 32})
            client.return_value.__enter__.return_value.get.return_value = response
            act.health(target, probe_preview=True)
            client.return_value.__enter__.return_value.get.assert_called_once_with('/health/')

    @contextmanager
    def fixture(self, failure=None, diagnostic_enospc=False, first_stop_failure=False):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary);runtime = root / 'runtime';runtime.mkdir(mode=0o700)
            output = runtime / 'continuation';marker = runtime / 'attempt.json'
            original_environment = environment()
            current = [act.render(original_environment, act.CONTINUATION_RELEASE)[0]]
            target = '8' * 40;head = [act.CONTINUATION_RELEASE];held = [False];trace = []
            population = {'database': {'tables': {'django_session': {'rows': 213, 'sha256': 'preserved-plus-health'},
                                                 'core_servicehealth': {'rows': 1, 'sha256': 'adjudicated-publisher'}},
                                      'catalog': {}, 'invariants': {}, 'pending_jobs': 0, 'held': 0, 'referenced_files': {}},
                          'files': {'old-file': {'sha256': 'unchanged'}}, 'mail': {}, 'static': {}, 'configuration': {}}
            original = {'backup': {'capture_attempts': 1, 'provider_calls': 0},
                        'before': {'original': 'authenticated-212'}, 'expected_population': deepcopy(population)}
            policy = {'original_receipts': {'failed.json': 'a' * 64}, 'health_session': {'kind': 'anonymous'},
                      'admin_preparation_sha256': act.sha(b'qualified-auth'), 'preparation_maximum_seconds': 180}
            states = {unit: {'ActiveState': 'inactive', 'MainPID': '0'} for unit in act.UNITS + act.OPERATIONS}
            host = Mock();host.state.side_effect = lambda unit: dict(states[unit])
            def service(action, unit):
                trace.append((action, unit, held[0]))
                if action == 'stop' and first_stop_failure and unit == act.UNITS[0]:
                    raise RuntimeError('invented-first-stop-error')
                states[unit] = {'ActiveState': 'active' if action == 'start' else 'inactive',
                                'MainPID': str(100 + act.UNITS.index(unit)) if action == 'start' else '0'}
            host.service.side_effect = service
            host.worker_configuration.return_value = {'values': {**act.MODEL_VALUES, 'QUILLMD_RELEASE_SHA': target}}
            @contextmanager
            def hold(owner):
                held[0] = True;trace.append(('hold-enter',))
                try: yield
                finally:
                    trace.append(('hold-exit', tuple(states[u]['ActiveState'] for u in act.UNITS)))
                    held[0] = False
            exclusion = SimpleNamespace(bind_runtime=Mock(), hold=hold)
            cipher = SimpleNamespace(encrypt=lambda raw: raw)
            backup = Mock();writer = Mock()
            def replace(path, before, after):
                self.assertEqual(current[0], before);self.assertTrue(held[0]);current[0] = after
                trace.append(('env-published',))
            writer.replace_environment.side_effect = replace
            def git(tree, *args):
                if args == ('rev-parse', 'HEAD'):return head[0].encode()
                if args[:2] == ('merge', '--ff-only'):
                    self.assertTrue(held[0]);head[0] = args[2];trace.append(('source-published',));return b''
                raise AssertionError(args)
            def admission(phase, *args, **kwargs):
                self.assertTrue(held[0]);trace.append(('admission', phase))
                if failure == phase:raise act.Refusal('invented-unexplained-population')
                return {'path': str(output / ('admission-' + phase + '.json')), 'sha256': 'f' * 64}, deepcopy(population)
            def child(argv, directory, label, deadline, **kwargs):
                self.assertTrue(held[0]);self.assertEqual(label, 'normal-authentication')
                self.assertEqual(states[act.UNITS[2]]['MainPID'], '0')
                self.assertTrue(all(states[u]['ActiveState'] == 'active' for u in act.UNITS[:2]))
                trace.append(('normal-auth',))
                population['database']['tables']['django_session'] = {'rows': 215, 'sha256': 'known-auth-retained'}
                if failure == 'auth':raise act.Refusal('unknown-auth-outcome')
                return {'exit_code': 0}
            def acceptance(*args, **kwargs):
                self.assertTrue(held[0]);trace.append(('acceptance',))
                population['files']['new-result'] = {'sha256': 'retain-provider-outcome'}
                if failure == 'acceptance':raise act.Refusal('unknown-provider-outcome')
                return {'complete': True}
            def health(release, **kwargs):
                if failure == 'post-start' and states[act.UNITS[2]]['ActiveState'] == 'active':
                    raise act.Refusal('invented-health-refusal')
                return [{'data_mode': 'synthetic-only'}]
            actual_write = act.write_new
            def write(path, raw):
                if diagnostic_enospc and path.name == 'failed.json':raise OSError(errno.ENOSPC, 'invented-full-disk')
                return actual_write(path, raw)
            replacements = dict(continuation_policy=Mock(return_value=policy),
                continuation_original=Mock(return_value=(original, original_environment, current[0], {'original': True}, cipher)),
                continuation_admission=Mock(side_effect=admission), snapshot=Mock(side_effect=lambda *args: deepcopy(population)),
                protected=Mock(side_effect=lambda path, *args: current[0] if path.name == '.env' else b'qualified-auth'),
                storage_admission=Mock(return_value={}), git=Mock(side_effect=git), operation_locks=nullcontext,
                await_service_boundary=Mock(side_effect=lambda *args, **kwargs: {u: dict(states[u]) for u in act.UNITS
                    if kwargs.get('worker_required', True) or u != act.UNITS[2]}),
                await_health=Mock(side_effect=health), acceptance_child=Mock(side_effect=child),
                acceptance_preparation=Mock(return_value={'qualified': True}), installed_acceptance=Mock(side_effect=acceptance),
                write_new=Mock(side_effect=write))
            with patch.multiple(act, CONTINUATION_OUTPUT=output, CONTINUATION_ATTEMPT=marker,
                                ACCEPTANCE_OUTPUT=runtime/'campaign', RUNTIME=runtime), patch.multiple(act, **replacements):
                yield SimpleNamespace(args=SimpleNamespace(operator_commit=target, acceptance_v2=True,
                                                           fresh_backup=False, rollback=False),
                    host=host, backup=backup, storage=Mock(), exclusion=exclusion, writer=writer, output=output,
                    marker=marker, held=held, states=states, trace=trace, replacements=replacements,
                    population=population, target=target, head=head)

    def invoke(self, f):
        return act.resume_pre_acceptance(f.args, {}, {}, {'operator_commit': f.target},
            host=f.host, backup=f.backup, storage=f.storage, exclusion=f.exclusion, env_writer=f.writer)

    def test_known_auth_and_acceptance_retain_original_receipts_without_capture_or_replay(self):
        with self.fixture() as f:
            receipt = self.invoke(f)
            self.assertTrue(receipt['complete']);self.assertTrue(f.marker.exists())
            self.assertFalse(receipt['continuation']['new_capture'])
            self.assertEqual(receipt['before']['database']['tables']['django_session']['rows'], 215)
            self.assertEqual(sum(row[0] == 'normal-auth' for row in f.trace), 1)
            self.assertEqual(sum(row[0] == 'acceptance' for row in f.trace), 1)
            self.assertEqual(f.trace[-1][1], ('active', 'active', 'active'))
            f.backup.backup.assert_not_called()
            with self.assertRaisesRegex(act.Refusal, 'replay'):self.invoke(f)

    def test_unexplained_initial_population_refuses_before_marker_source_env_or_unit_mutation(self):
        with self.fixture('before-auth') as f:
            with self.assertRaises(act.Refusal):self.invoke(f)
            self.assertFalse(f.marker.exists());f.host.service.assert_not_called()
            f.writer.replace_environment.assert_not_called()
            self.assertEqual(f.head[0], act.CONTINUATION_RELEASE)

    def test_auth_unknown_population_and_restart_failures_stop_inside_original_hold_even_with_enospc(self):
        for failure in ('auth', 'after-auth', 'post-start'):
            with self.subTest(failure=failure), self.fixture(failure, diagnostic_enospc=True) as f:
                with self.assertRaises(act.Refusal):self.invoke(f)
                self.assertEqual(f.trace[-1][1], ('inactive', 'inactive', 'inactive'))
                self.assertTrue(all(row[2] for row in f.trace if row[0] == 'stop'))
                self.assertNotIn(('acceptance',), f.trace)
                self.assertEqual(f.population['database']['tables']['django_session']['rows'], 215)

    def test_first_stop_error_does_not_skip_admin_worker_or_delay_cleanup_until_hold_release(self):
        with self.fixture('post-start', diagnostic_enospc=True, first_stop_failure=True) as f:
            with self.assertRaises(act.Refusal):self.invoke(f)
            self.assertEqual(f.trace[-1][1], ('active', 'inactive', 'inactive'))
            self.assertTrue(all(row[2] for row in f.trace if row[0] == 'stop'))
            for unit in act.UNITS:self.assertTrue(any(row[:2] == ('stop', unit) for row in f.trace))

    def test_acceptance_unknown_outcome_preserves_all_started_units_and_new_record(self):
        with self.fixture('acceptance') as f:
            with self.assertRaises(act.Refusal):self.invoke(f)
            self.assertIn('new-result', f.population['files'])
            self.assertEqual(f.trace[-1][1], ('active', 'active', 'active'))
            self.assertFalse(any(row[0] == 'stop' for row in f.trace))
            self.assertEqual(sum(row[0] == 'acceptance' for row in f.trace), 1)

    def test_expired_preparation_or_mutation_budget_never_begins_a_later_action_and_cleanup_still_runs(self):
        for crossing in ('before-auth', 'source', 'environment', 'first-web', 'auth', 'after-auth', 'complete-checkpoint'):
            with self.subTest(crossing=crossing), self.fixture() as f:
                clock = [0.0];actions = []
                admission = f.replacements['continuation_admission'].side_effect
                git = f.replacements['git'].side_effect
                replace = f.writer.replace_environment.side_effect
                service = f.host.service.side_effect
                child = f.replacements['acceptance_child'].side_effect
                write = f.replacements['write_new'].side_effect
                def admit(phase, *args, **kwargs):
                    result = admission(phase, *args, **kwargs)
                    if crossing == phase:clock[0] = 241.0
                    return result
                def source(tree, *args):
                    if args[:2] == ('merge', '--ff-only'):actions.append(('source', clock[0]))
                    result = git(tree, *args)
                    if crossing == 'source' and args[:2] == ('merge', '--ff-only'):clock[0] = 241.0
                    return result
                def environment(*args):
                    actions.append(('environment', clock[0]));result = replace(*args)
                    if crossing == 'environment':clock[0] = 241.0
                    return result
                def unit(action, name):
                    if action == 'start':actions.append((name, clock[0]))
                    result = service(action, name)
                    if crossing == 'first-web' and action == 'start' and name == act.UNITS[0]:clock[0] = 241.0
                    return result
                def authentication(*args, **kwargs):
                    actions.append(('auth', clock[0]));result = child(*args, **kwargs)
                    if crossing == 'auth':clock[0] = 241.0
                    return result
                def checkpoint(path, raw):
                    result = write(path, raw)
                    if crossing == 'complete-checkpoint' and path.name == 'complete.json':clock[0] = 241.0
                    return result
                f.replacements['continuation_admission'].side_effect = admit
                f.replacements['git'].side_effect = source
                f.writer.replace_environment.side_effect = environment
                f.host.service.side_effect = unit
                f.replacements['acceptance_child'].side_effect = authentication
                f.replacements['write_new'].side_effect = checkpoint
                with patch.object(act.time, 'monotonic', side_effect=lambda: clock[0]), self.assertRaises(act.Refusal):
                    self.invoke(f)
                self.assertTrue(all(at < 240 for _, at in actions), actions)
                self.assertEqual(f.trace[-1][1], ('inactive', 'inactive', 'inactive'))
                self.assertTrue(all(row[2] for row in f.trace if row[0] == 'stop'))
                self.assertFalse(any(row[0] == 'acceptance' for row in f.trace))
                if crossing == 'before-auth':
                    self.assertFalse(f.marker.exists());self.assertEqual(actions, [])
                elif crossing == 'after-auth':
                    self.assertFalse(any(row[:2] == ('start', act.UNITS[2]) for row in f.trace))


class StaticPreservation(unittest.TestCase):
    def test_font_rewrite_and_compressed_payloads_are_exact_not_only_manifest_names(self):
        with tempfile.TemporaryDirectory() as temporary:
            inputs, stage, manifest = static_fixture(Path(temporary))
            primitives = act.static_primitives()
            self.assertIn(manifest['paths']['app.css'], act.validate_static_stage(stage, inputs, primitives))
            compiled = stage / manifest['paths']['app.css'];original = compiled.read_bytes()
            compiled.write_bytes(original + b'foreign bytes')
            with self.assertRaisesRegex(act.Refusal, 'static_compiled_source_identity'):
                act.validate_static_stage(stage, inputs, primitives)
            compiled.write_bytes(original)
            public_write(stage / 'unexpected.js', b'extra')
            with self.assertRaisesRegex(act.Refusal, 'static_undeclared_output'):
                act.validate_static_stage(stage, inputs, primitives)

    def test_full_and_partial_static_rollback_retain_every_old_hash(self):
        for partial in (False, True):
            with self.subTest(partial=partial), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                inputs, stage, manifest = static_fixture(root)
                app = root / 'app';static = app / 'staticfiles';static.mkdir(parents=True, mode=0o755)
                old_manifest = {'version': '1.1', 'paths': {}}
                for name in sorted(act.STATIC_INPUTS - {'fonts/dm-sans.ttf', 'fonts/OFL-DM-Sans.txt'}):
                    raw = b'old public source ' + name.encode() if name in ('app.css', 'app.js') else inputs[name].read_bytes()
                    p = act.PurePosixPath(name)
                    compiled = str(p.with_suffix('')) + '.' + hashlib.md5(raw).hexdigest()[:12] + p.suffix
                    old_manifest['paths'][name] = compiled
                    public_write(static / name, raw);public_write(static / compiled, raw)
                    public_write(static / (compiled + '.gz'), gzip.compress(raw, mtime=0))
                old_manifest['hash'] = hashlib.md5(json.dumps(sorted(old_manifest['paths'].items())).encode()).hexdigest()[:12]
                public_write(static / 'staticfiles.json', act.encode(old_manifest))
                primitives = act.static_primitives();before = primitives.static_inventory(static)
                runtime = root / 'runtime';runtime.mkdir(mode=0o700)
                primitives.retain_static(static, runtime / 'public-assets-before.tar', before)
                preparation = {'before': before, 'stage': str(stage),
                               'staged': act.validate_static_stage(stage, inputs, primitives),
                               'prior_assets_archive_sha256': act.sha((runtime / 'public-assets-before.tar').read_bytes())}
                with patch.object(act, 'APP', app), patch.object(act, 'static_sources', return_value=inputs):
                    if partial:
                        primitives.create_static_stage(static / 'fonts')
                        name = manifest['paths']['app.css'];public_write(static / name, (stage / name).read_bytes())
                    else:
                        result = act.install_static(preparation)
                        self.assertTrue(result['old_immutable_assets_retained'])
                    recovered = act.restore_static(preparation, runtime)
                    self.assertTrue(recovered['previous_manifest_aliases_restored'])
                    self.assertEqual((static / 'staticfiles.json').read_bytes(), act.encode(old_manifest))
                    self.assertEqual((static / 'app.css').read_bytes(), b'old public source app.css')
                    for name, row in before.items():
                        if name not in {'staticfiles.json', 'app.css', 'app.js'}:
                            self.assertEqual(recovered['after'][name], row)
                    old_hash = static / old_manifest['paths']['app.css']
                    old_hash.write_bytes(b'corrupt immutable old CSS')
                    with self.assertRaisesRegex(act.Refusal, 'rollback_static_immutable_drift'):
                        act.restore_static(preparation, runtime)

    def test_storage_exception_keeps_red_and_refuses_reserve_erosion(self):
        raw = b'fictional explicit owner exception'
        contract = {'storage_authority_path': act.STORAGE_AUTHORITY, 'storage_authority_sha256': act.sha(raw),
                    'storage_allowances': act.STORAGE_ALLOWANCES, 'storage_minimum_reserve_bytes': act.STORAGE_RESERVE}
        measured = SimpleNamespace(f_bavail=42 * 1024 ** 3, f_frsize=1, f_favail=100000, f_blocks=591 * 1024 ** 3,
                                   f_bfree=42 * 1024 ** 3)
        with patch.object(Path, 'read_bytes', return_value=raw), patch.object(act.os, 'statvfs', return_value=measured):
            report = act.storage_admission(contract, 'fictional checkpoint')
            self.assertEqual(report['original_preflight_percentage_verdict'], 'RED')
            self.assertEqual(report['projected_available_bytes'], 28 * 1024 ** 3)
            self.assertEqual(report['conservative_remaining_allowances']['background_bytes'], 8 * 1024 ** 3)
            measured.f_bavail = 34 * 1024 ** 3
            self.assertEqual(act.storage_admission(contract, 'exact reserve')['projected_available_bytes'],
                             act.STORAGE_RESERVE)
            # The old4GiB estimate would admit this33GiB observation; the measured8GiB forecast refuses it.
            measured.f_bavail = 33 * 1024 ** 3
            with self.assertRaisesRegex(act.Refusal, 'task_storage_reserve'):
                act.storage_admission(contract, 'fictional later checkpoint')
            stale = dict(contract, storage_allowances={**act.STORAGE_ALLOWANCES, 'background_bytes': 4 * 1024 ** 3})
            with self.assertRaisesRegex(act.Refusal, 'storage_exception_scope'):
                act.storage_admission(stale, 'stale projection')


class FreshCapturePreservation(unittest.TestCase):
    @contextmanager
    def fixture(self, variant='valid'):
        from ops import backup_restore as primitive
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary);source = root / 'source';app = root / 'app'
            (source / 'rebuild/ops').mkdir(parents=True);app.mkdir()
            module = b'# fictional immutable capture primitive\n'
            (source / 'rebuild/ops/backup_restore.py').write_bytes(module)
            captures = root / 'backups';captures.mkdir(mode=0o700)
            old = captures / '20261006T192011Z-c6f27e26';old.mkdir(mode=0o700)
            (old / 'old-ciphertext').write_bytes(b'preserve');(old / 'old-ciphertext').chmod(0o600)
            runtime = root / 'runtime';runtime.mkdir(mode=0o700)
            destination = runtime / 'activation';destination.mkdir(mode=0o700)
            marker = runtime / 'one-capture-attempt.json'
            key = runtime / 'fictional.key';key.write_bytes(primitive.Fernet.generate_key());key.chmod(0o600)
            roles = runtime / 'fictional-roles.json';roles.write_bytes(b'{}');roles.chmod(0o600)
            snapshot = {'database': {'tables': {name: {'rows': 1, 'sha256': act.sha(name.encode())} for name in act.TABLES},
                                    'invariants': {}, 'referenced_files': {'receipt/fiction.json': None}},
                        'files': {'receipt/fiction.json': {'sha256': act.sha(b'fiction'), 'size': 7}}}
            policy = {'source': str(app), 'output': str(captures), 'source_commit': act.BASELINE,
                      'key_file': str(key), 'database_credentials': str(roles), 'maximum_attempts': 1,
                      'exclusive_attempt_marker': str(marker),
                      'timing': 'inside_exclusion_after_private_drain_before_publication',
                      'primitive_sha256': act.sha(module), 'offsite_upload': False, 'provider_calls': 0}
            container = {'Id': 'fictional', 'Image': 'sha256:' + 'a' * 64,
                         'State': {'Running': True}, 'HostConfig': {'PortBindings': {
                             '5432/tcp': [{'HostIp': '127.0.0.1', 'HostPort': '55438'}]}}}
            run = captures / '20261006T235959Z-aaaaaaaa'
            def capture(args):
                self.assertEqual(vars(args), {'source': app, 'output': captures, 'key_file': key, 'database_credentials': roles})
                run.mkdir(mode=0o700);(run / 'objects').mkdir(mode=0o700)
                cipher = primitive.key_at(key)
                manifest = {'format': 1, 'complete': True, 'run_id': run.name, 'source_commit': act.BASELINE,
                            'database': 'quillmd_fresh', 'container_id': container['Id'], 'image_id': container['Image'],
                            'tables': deepcopy(snapshot['database']['tables']), 'invariants': {}, 'files': []}
                for label, plain in (('receipt/fiction.json', b'fiction'), ('database.dump', b'fictional database')):
                    name = ('objects/' + act.sha(label.encode()) + '.fernet') if label.startswith('receipt') else 'database.dump.fernet'
                    encrypted = cipher.encrypt(plain);primitive.write_private(run / name, encrypted)
                    entry = {'sha256': act.sha(plain), 'size': len(plain), 'cipher_sha256': act.sha(encrypted)}
                    if label.startswith('receipt'):
                        manifest['files'].append(dict(entry, path=label, object=name))
                    else:
                        manifest['dump'] = entry
                if variant == 'stale_table':
                    manifest['tables']['core_servicehealth']['rows'] = 2
                primitive.write_private(run / 'manifest.json.fernet', cipher.encrypt(act.encode(manifest)))
                if variant == 'corrupt_ciphertext':
                    (run / manifest['files'][0]['object']).write_bytes(b'corrupted encrypted object')
                if variant == 'previous_capture_changed':
                    (old / 'old-ciphertext').write_bytes(b'intervening corruption')
                if variant == 'primitive_failure':
                    raise OSError(errno.ENOSPC, 'fictional capture failed after beginning')
                print(json.dumps({'complete': True, 'run_id': run.name,
                                  'backup_directory': str(root / 'foreign' / run.name) if variant == 'foreign_path' else str(run),
                                  'manifest_cipher_sha256': act.sha((run / 'manifest.json.fernet').read_bytes())}))
            backup = SimpleNamespace(private_dir=primitive.private_dir, key_at=primitive.key_at,
                                     load_backup=primitive.load_backup, decrypt_checked=primitive.decrypt_checked,
                                     inspect_container=Mock(return_value=container), backup=Mock(side_effect=capture))
            restore = act.encode({'complete': True, 'independent_key_restore_verified': True,
                                  'isolated_restore': {'complete': True, 'all_table_hashes_match': True,
                                                       'all_file_hashes_match': True, 'workers_started': 0}})
            original_protected = act.protected
            def protected(path, *args):
                return restore if path == act.RESTORE else original_protected(path, *args)
            with patch.object(act, 'SOURCE', source), patch.object(act, 'APP', app), \
                    patch.object(act, 'BACKUPS', captures), patch.object(act, 'CAPTURE_ATTEMPT', marker), \
                    patch.object(act, 'KEY', key), patch.object(act, 'ROLES', roles), \
                    patch.object(act, 'git', return_value=module), patch.object(act, 'protected', side_effect=protected), \
                    patch.object(act, 'RESTORE_SHA', act.sha(restore)):
                yield backup, snapshot, destination, {'fresh_capture_policy': policy}, marker

    def test_one_current_capture_authenticates_all_tables_and_cannot_be_replayed_in_another_directory(self):
        with self.fixture() as (backup, baseline, destination, contract, marker):
            result = act.capture_current_backup(backup, baseline, destination, contract)
            self.assertTrue(result['all_current_tables_covered'])
            self.assertTrue(result['authenticated_dump_and_objects'])
            self.assertTrue(result['previous_captures_preserved'])
            self.assertEqual(result['stopped_before_fingerprint_sha256'], act.sha(act.encode(baseline)))
            self.assertEqual(marker.read_bytes(), (destination / 'fresh-backup-attempt.json').read_bytes())
            another = destination.parent / 'another-activation';another.mkdir(mode=0o700)
            with self.assertRaises(FileExistsError):
                act.capture_current_backup(backup, baseline, another, contract)
            self.assertEqual(backup.backup.call_count, 1)

    def test_stale_servicehealth_foreign_destination_corruption_and_previous_capture_delta_refuse(self):
        for variant, message in (('stale_table', 'backup_current_row_coverage'),
                                 ('foreign_path', 'fresh_capture_output_identity'),
                                 ('corrupt_ciphertext', 'Ciphertext integrity check failed'),
                                 ('previous_capture_changed', 'previous_capture_preservation')):
            with self.subTest(variant=variant), self.fixture(variant) as (backup, baseline, destination, contract, marker):
                with self.assertRaisesRegex(RuntimeError, message):
                    act.capture_current_backup(backup, baseline, destination, contract)
                self.assertEqual(backup.backup.call_count, 1)
                self.assertTrue(marker.exists())

    def test_primitive_failure_consumes_one_attempt_and_unqualified_scope_never_captures(self):
        with self.fixture('primitive_failure') as (backup, baseline, destination, contract, marker):
            with self.assertRaises(OSError):
                act.capture_current_backup(backup, baseline, destination, contract)
            with self.assertRaises(FileExistsError):
                act.capture_current_backup(backup, baseline, destination, contract)
            self.assertEqual(backup.backup.call_count, 1)
        with self.fixture() as (backup, baseline, destination, contract, marker):
            contract['fresh_capture_policy']['maximum_attempts'] = 2
            with self.assertRaisesRegex(act.Refusal, 'prospective_fresh_capture_scope'):
                act.capture_current_backup(backup, baseline, destination, contract)
            backup.backup.assert_not_called();self.assertFalse(marker.exists())


class InExclusionRecovery(unittest.TestCase):
    @contextmanager
    def fixture(self, failure='static', diagnostic_enospc=False, population_drift=None, stop_failure=False, recovery_health_failure=False):
        with tempfile.TemporaryDirectory() as temporary, ExitStack() as patches:
            runtime = Path(temporary);target = '4' * 40;original = environment()
            updated, _ = act.render(original, target)
            current = [original];head = [act.BASELINE];held = [False];trace = []
            static = {'alias': 'old', 'immutable-old': 'old-hash'}
            population = {'database': {'tables': {'core_servicehealth': {'sha256': 'same-cadence'},
                                                'core_encounter': {'sha256': 'existing-history'}}},
                          'files': {'existing': {'sha256': 'existing'}}, 'mail': {}, 'configuration': {'policy': 'original'}}
            states = {unit: {'ActiveState': 'active', 'MainPID': str(index + 1),
                             'ExecMainStartTimestampMonotonic': '1'} for index, unit in enumerate(act.UNITS)}
            old_units = deepcopy(states)
            host, backup, storage, exclusion, writer = Mock(), Mock(), Mock(), Mock(), Mock()
            backup.key_at.return_value.encrypt.side_effect = lambda value: b'fictional encrypted ' + value
            storage.inventory.return_value = {}
            def state(unit):
                return deepcopy(states[unit]) if unit in states else {'ActiveState': 'inactive', 'MainPID': '0'}
            def service(action, unit):
                trace.append((action, unit, held[0]))
                if stop_failure and action == 'stop' and unit == act.UNITS[0]:
                    raise OSError('fictional first-unit stop refusal')
                states[unit] = {'ActiveState': 'inactive' if action == 'stop' else 'active',
                                'MainPID': '0' if action == 'stop' else str(11 + act.UNITS.index(unit)),
                                'ExecMainStartTimestampMonotonic': '2'}
                if failure == 'startup' and head[0] == target and action == 'start':
                    raise OSError(errno.ENOSPC, 'fictional partial startup')
            host.state.side_effect, host.service.side_effect = state, service
            def worker_proof(raw, release, boundary):
                self.assertEqual(raw, current[0]);self.assertEqual(release, head[0]);self.assertTrue(held[0])
                return {'values': act.dotenv_values(stream=StringIO(raw.decode()), interpolate=False)}
            host.worker_configuration.side_effect = worker_proof
            @contextmanager
            def hold(*args):
                held[0] = True;trace.append(('exclusion-enter',))
                try: yield
                finally:
                    trace.append(('exclusion-exit',));held[0] = False
                    # Publication becomes possible only after coherent guarded recovery is finished.
                    if head[0] == act.BASELINE and all(row['ActiveState'] == 'active' for row in states.values()):
                        population['database']['tables']['core_servicehealth']['sha256'] = 'next-normal-cadence'
            exclusion.hold.side_effect = hold
            def snapshot(*args):
                self.assertTrue(held[0]);return dict(deepcopy(population), static=deepcopy(static))
            def git(tree, *args):
                if args[:2] == ('merge', '--ff-only'):
                    self.assertTrue(held[0]);head[0] = target;trace.append(('source-target',))
                return head[0].encode()
            def environment_write(path, before, after):
                self.assertTrue(held[0]);self.assertEqual(before, current[0]);current[0] = after
                trace.append(('environment', 'baseline' if after == original else 'target'))
                if failure == 'configuration' and after == updated:
                    raise OSError(errno.ENOSPC, 'fictional partial configuration publication')
            writer.replace_environment.side_effect = environment_write
            def install_static(prepared):
                self.assertTrue(held[0]);static.update(alias='new', **{'immutable-new': 'new-hash'})
                trace.append(('static-target',))
                if population_drift == 'database': population['database']['tables']['core_encounter']['sha256'] = 'changed-history'
                elif population_drift == 'servicehealth': population['database']['tables']['core_servicehealth']['sha256'] = 'unexpected-writer'
                elif population_drift == 'files': population['files']['existing']['sha256'] = 'changed-file'
                elif population_drift == 'mail': population['mail']['unknown'] = {'sha256': 'changed-mail'}
                elif population_drift == 'configuration': population['configuration']['policy'] = 'changed-security'
                if failure == 'static': raise OSError(errno.ENOSPC, 'fictional partial static publication')
                return {}
            def restore_static(prepared, directory):
                self.assertTrue(held[0]);static['alias'] = 'old';trace.append(('static-baseline',));return {}
            def restore_source(commit):
                self.assertTrue(held[0]);self.assertEqual(commit, target)
                head[0] = act.BASELINE;trace.append(('source-baseline',));return {}
            def boundary(*args):
                self.assertTrue(held[0]);return deepcopy(states)
            def health(release, **kwargs):
                self.assertEqual(release, head[0]);self.assertTrue(all(row['ActiveState'] == 'active' for row in states.values()))
                if recovery_health_failure and ('source-baseline',) in trace:
                    raise act.Refusal('fictional_recovery_http_failure')
            original_write = act.write_new
            def write(path, raw):
                if recovery_health_failure and path.name in ('failed.json', 'recovery.json'):
                    self.assertTrue(all(row['ActiveState'] == 'inactive' for row in states.values()),
                                    'Failed recovery must stop inside exclusion before diagnostics')
                if diagnostic_enospc and path.name in ('failed.json', 'recovery.json'):
                    raise OSError(errno.ENOSPC, 'fictional unavailable diagnostics')
                if failure == 'complete_checkpoint' and path.name == 'complete.json':
                    raise OSError(errno.ENOSPC, 'fictional complete evidence failure')
                original_write(path, raw)
            replacements = {'RUNTIME': runtime, 'CAPTURE_ATTEMPT': runtime / 'attempt.json',
                            'protected': Mock(side_effect=lambda *args: current[0]),
                            'storage_admission': Mock(return_value={}), 'prepare_static': Mock(return_value={'before': {}}),
                            'install_static': Mock(side_effect=install_static), 'inventory': Mock(side_effect=lambda *args: deepcopy(static)),
                            'write_new': Mock(side_effect=write), 'health': Mock(side_effect=health),
                            'await_health': Mock(side_effect=health), 'service_boundary': Mock(return_value=old_units),
                            'await_service_boundary': Mock(side_effect=boundary), 'database': Mock(return_value={}),
                            'snapshot': Mock(side_effect=snapshot), 'capture_current_backup': Mock(return_value={'capture_attempts': 1}),
                            'operation_locks': Mock(return_value=nullcontext()), 'git': Mock(side_effect=git),
                            'restore_static': Mock(side_effect=restore_static), 'restore_source': Mock(side_effect=restore_source)}
            patches.enter_context(patch.multiple(act, **replacements));patches.enter_context(patch('sys.stdout', new=StringIO()))
            yield SimpleNamespace(runtime=runtime, target=target, original=original, updated=updated, current=current,
                                  head=head, held=held, trace=trace, population=population, states=states,
                                  host=host, backup=backup, storage=storage, exclusion=exclusion, writer=writer,
                                  replacements=replacements)

    def invoke(self, fixture):
        with self.assertRaisesRegex(act.Refusal, 'activation_failed_recovery_required'):
            act.execute(SimpleNamespace(operator_commit=fixture.target, fresh_backup=True),
                        {'rollback_qualified': True, 'environment_before_sha256': act.sha(fixture.original)}, {},
                        {'operator_commit': fixture.target, 'shared_head': act.BASELINE}, host=fixture.host,
                        backup=fixture.backup, storage=fixture.storage, exclusion=fixture.exclusion, env_writer=fixture.writer)

    def test_configuration_static_startup_and_completion_failures_recover_under_original_exclusion_but_never_pass(self):
        for failure in ('configuration', 'static', 'startup', 'complete_checkpoint'):
            with self.subTest(failure=failure), self.fixture(failure) as fixture:
                self.invoke(fixture)
                self.assertEqual(fixture.head[0], act.BASELINE);self.assertEqual(fixture.current[0], fixture.original)
                self.assertTrue(all(row['ActiveState'] == 'active' for row in fixture.states.values()))
                self.assertEqual(fixture.population['database']['tables']['core_servicehealth']['sha256'], 'next-normal-cadence')
                receipt = json.loads(next(fixture.runtime.glob('legacy-model-demo-*/failed.json')).read_bytes())
                self.assertFalse(receipt['complete']);self.assertEqual(receipt['failure_kind'], 'OSError')
                self.assertTrue(receipt['recovery']['complete']);self.assertEqual(receipt['provider_calls'], 0)
                self.assertLess(fixture.trace.index(('source-baseline',)), fixture.trace.index(('exclusion-exit',)))
                fixture.backup.backup.assert_not_called()
                self.assertEqual(fixture.replacements['capture_current_backup'].call_count, 1)

    def test_enospc_diagnostics_do_not_prevent_coherent_guarded_recovery(self):
        with self.fixture(diagnostic_enospc=True) as fixture:
            self.invoke(fixture)
            self.assertEqual(fixture.current[0], fixture.original);self.assertEqual(fixture.head[0], act.BASELINE)
            self.assertTrue(all(row['ActiveState'] == 'active' for row in fixture.states.values()))
            self.assertEqual(fixture.replacements['restore_source'].call_count, 1)
            self.assertFalse(list(fixture.runtime.glob('legacy-model-demo-*/complete.json')))

    def test_every_clinical_servicehealth_file_mail_and_security_delta_refuses_recovery_without_erasing_it(self):
        for drift in ('database', 'servicehealth', 'files', 'mail', 'configuration'):
            with self.subTest(drift=drift), self.fixture(population_drift=drift) as fixture:
                self.invoke(fixture)
                fixture.replacements['restore_static'].assert_not_called();fixture.replacements['restore_source'].assert_not_called()
                self.assertEqual(fixture.head[0], fixture.target);self.assertEqual(fixture.current[0], fixture.updated)
                self.assertTrue(all(row['ActiveState'] == 'inactive' for row in fixture.states.values()))
                receipt = json.loads(next(fixture.runtime.glob('legacy-model-demo-*/failed.json')).read_bytes())
                self.assertFalse(receipt['complete']);self.assertNotIn('recovery', receipt)
                self.assertEqual(receipt['recovery_capture_failure'], 'Refusal')

    def test_first_unit_stop_failure_never_skips_other_units_or_claims_recovery(self):
        with self.fixture(stop_failure=True) as fixture:
            self.invoke(fixture)
            self.assertTrue(all(fixture.states[unit]['ActiveState'] == 'inactive' for unit in act.UNITS[1:]))
            self.assertEqual(fixture.states[act.UNITS[0]]['ActiveState'], 'active')
            fixture.replacements['restore_source'].assert_not_called()
            for unit in act.UNITS:
                self.assertTrue(any(row[:2] == ('stop', unit) for row in fixture.trace))

    def test_recovery_health_failure_failstops_inside_exclusion_before_diagnostics_or_publisher_entry(self):
        with self.fixture(recovery_health_failure=True) as fixture:
            self.invoke(fixture)
            self.assertTrue(all(row['ActiveState'] == 'inactive' for row in fixture.states.values()))
            self.assertEqual(fixture.population['database']['tables']['core_servicehealth']['sha256'], 'same-cadence')
            receipt = json.loads(next(fixture.runtime.glob('legacy-model-demo-*/failed.json')).read_bytes())
            self.assertFalse(receipt['complete']);self.assertEqual(receipt['recovery_capture_failure'], 'Refusal')
            self.assertTrue(all(row['stopped_verified'] for row in receipt['recovery_fail_stop'].values()))

    def test_standalone_rollback_health_refusal_stops_inside_hold_even_when_diagnostics_fail(self):
        for diagnostic_enospc in (False, True):
            with self.subTest(diagnostic_enospc=diagnostic_enospc), \
                    self.fixture(recovery_health_failure=True, diagnostic_enospc=diagnostic_enospc) as fixture:
                directory = fixture.runtime / 'legacy-model-demo-fictional';directory.mkdir(mode=0o700)
                fixture.current[0] = fixture.updated;fixture.head[0] = fixture.target
                baseline = dict(deepcopy(fixture.population), static=fixture.replacements['inventory']())
                prepared = {'source': {'operator_commit': fixture.target},
                            'configuration': {'before_sha256': act.sha(fixture.original)},
                            'before': baseline, 'static_preparation': {}}
                def read(path, *args):
                    if path.name == 'prepared.json': return act.encode(prepared)
                    if path.name == 'environment-before.fernet': return fixture.original
                    if path.name == 'environment-after.fernet': return fixture.updated
                    return fixture.current[0]
                fixture.replacements['protected'].side_effect = read
                fixture.backup.key_at.return_value.decrypt.side_effect = lambda raw: raw
                with self.assertRaisesRegex(act.Refusal, 'rollback_failed_recovery_required'):
                    act.rollback(SimpleNamespace(operator_commit=fixture.target, activation_directory=directory), {},
                                 contract={'rollback_qualified': True}, host=fixture.host, backup=fixture.backup,
                                 storage=fixture.storage, exclusion=fixture.exclusion, env_writer=fixture.writer)
                self.assertTrue(all(row['ActiveState'] == 'inactive' for row in fixture.states.values()))
                self.assertEqual(fixture.population['database']['tables']['core_servicehealth']['sha256'], 'same-cadence')
                self.assertTrue(all(row[2] for row in fixture.trace if row[0] == 'stop'))
                self.assertFalse(list(fixture.runtime.glob('legacy-model-rollback-*/complete.json')))

    def test_standalone_rollback_partial_stop_failure_attempts_all_units_before_exclusion_exit(self):
        with self.fixture(stop_failure=True) as fixture:
            directory = fixture.runtime / 'legacy-model-demo-fictional';directory.mkdir(mode=0o700)
            fixture.current[0] = fixture.updated;fixture.head[0] = fixture.target
            prepared = {'source': {'operator_commit': fixture.target},
                        'configuration': {'before_sha256': act.sha(fixture.original)},
                        'before': dict(deepcopy(fixture.population), static=fixture.replacements['inventory']()),
                        'static_preparation': {}}
            def read(path, *args):
                if path.name == 'prepared.json': return act.encode(prepared)
                if path.name == 'environment-before.fernet': return fixture.original
                if path.name == 'environment-after.fernet': return fixture.updated
                return fixture.current[0]
            fixture.replacements['protected'].side_effect = read
            fixture.backup.key_at.return_value.decrypt.side_effect = lambda raw: raw
            with self.assertRaisesRegex(act.Refusal, 'rollback_failed_recovery_required'):
                act.rollback(SimpleNamespace(operator_commit=fixture.target, activation_directory=directory), {},
                             contract={'rollback_qualified': True}, host=fixture.host, backup=fixture.backup,
                             storage=fixture.storage, exclusion=fixture.exclusion, env_writer=fixture.writer)
            self.assertTrue(all(fixture.states[unit]['ActiveState'] == 'inactive' for unit in act.UNITS[1:]))
            self.assertEqual(fixture.states[act.UNITS[0]]['ActiveState'], 'active')
            for unit in act.UNITS:
                self.assertTrue(any(row[:2] == ('stop', unit) and row[2] for row in fixture.trace))
            fixture.replacements['restore_source'].assert_not_called()
            receipt = json.loads(next(fixture.runtime.glob('legacy-model-rollback-*/failed.json')).read_bytes())
            self.assertFalse(receipt['complete']);self.assertFalse(receipt['fail_stop'][act.UNITS[0]]['stopped_verified'])


class AcceptanceBoundary(unittest.TestCase):
    fixture = InExclusionRecovery.fixture
    def test_accepted_children_use_completed_installer_under_same_exclusion_and_campaign_failure_preserves_new_rows(self):
        for failed in (False, True):
            with self.subTest(failed=failed), self.fixture(failure='none') as fixture:
                preparation = {'scope': {'maximum_generations': 5, 'maximum_transcriptions': 1, 'provider_usd_limit': '0.70'}}
                def campaign(target, directory, prepared):
                    self.assertTrue(fixture.held[0]);self.assertEqual(target, fixture.target)
                    self.assertTrue(all(row['ActiveState'] == 'active' for row in fixture.states.values()))
                    self.assertEqual(fixture.head[0], fixture.target);self.assertEqual(fixture.current[0], fixture.updated)
                    self.assertTrue(json.loads((directory / 'complete.json').read_bytes())['complete'])
                    fixture.population['database']['tables']['new-synthetic-job'] = {'sha256': 'accepted-new-job'}
                    fixture.population['files']['new-provider-result'] = {'sha256': 'retained-unknown-or-known-response'}
                    fixture.trace.append(('acceptance-children',))
                    if failed: raise act.Refusal('fictional_unknown_acceptance_outcome')
                    return {'complete': True, 'delegated_maximum_generations': 5, 'delegated_maximum_transcriptions': 1}
                with patch.object(act, 'acceptance_preparation', return_value=preparation), \
                        patch.object(act, 'installed_acceptance', side_effect=campaign) as child:
                    args = SimpleNamespace(operator_commit=fixture.target, fresh_backup=True, acceptance_v2=True)
                    kwargs = dict(host=fixture.host, backup=fixture.backup, storage=fixture.storage,
                                  exclusion=fixture.exclusion, env_writer=fixture.writer)
                    contract = {'rollback_qualified': True, 'environment_before_sha256': act.sha(fixture.original)}
                    if failed:
                        with self.assertRaises(act.Refusal):
                            act.execute(args, contract, {}, {'shared_head': act.BASELINE}, **kwargs)
                        receipt = json.loads(next(fixture.runtime.glob('legacy-model-demo-*/failed.json')).read_bytes())
                        self.assertFalse(receipt['complete']);self.assertTrue(receipt['acceptance_started'])
                    else:
                        receipt = act.execute(args, contract, {}, {'shared_head': act.BASELINE}, **kwargs)
                        self.assertTrue(receipt['complete']);self.assertTrue(receipt['acceptance']['complete'])
                    self.assertEqual(child.call_count, 1)
                    self.assertTrue(all(row['ActiveState'] == 'active' for row in fixture.states.values()))
                    self.assertEqual(fixture.head[0], fixture.target);self.assertEqual(fixture.current[0], fixture.updated)
                    self.assertIn('new-synthetic-job', fixture.population['database']['tables'])
                    self.assertIn('new-provider-result', fixture.population['files'])
                    fixture.replacements['restore_static'].assert_not_called();fixture.replacements['restore_source'].assert_not_called()
                    self.assertLess(fixture.trace.index(('acceptance-children',)), fixture.trace.index(('exclusion-exit',)))
                    self.assertEqual(sum(row[0] == 'stop' for row in fixture.trace), 3)

    def test_bad_acceptance_admission_refuses_before_environment_or_private_mutation(self):
        with self.fixture(failure='none') as fixture, patch.object(act, 'acceptance_preparation', side_effect=act.Refusal('bad-pin')):
            with self.assertRaisesRegex(act.Refusal, 'bad-pin'):
                act.execute(SimpleNamespace(operator_commit=fixture.target, fresh_backup=True, acceptance_v2=True),
                            {'rollback_qualified': True}, {}, {}, host=fixture.host, backup=fixture.backup,
                            storage=fixture.storage, exclusion=fixture.exclusion, env_writer=fixture.writer)
            fixture.host.service.assert_not_called();fixture.replacements['protected'].assert_not_called()

    def test_fixed_nested_ruled_browser_then_readonly_verifier_share_one_separate_deadline_and_never_retry(self):
        for failed_child in (None, 'browser', 'verifier'):
            with self.subTest(failed_child=failed_child), tempfile.TemporaryDirectory() as temporary:
                directory = Path(temporary);prepared = {'fictional': 'protected scoped artifacts'}
                def child(argv, destination, label, deadline, *, ruled):
                    self.assertEqual(destination, directory)
                    self.assertEqual(ruled, label == 'acceptance-browser')
                    self.assertGreater(deadline, act.time.monotonic())
                    if failed_child == label.split('-')[1]: raise act.Refusal('fictional child failure')
                    return {'exit_code': 0, 'automatic_retries': 0}
                with patch.object(act, 'declaration', return_value=(b'fictional declaration', {})), \
                        patch.object(act, 'acceptance_preparation', return_value=prepared), \
                        patch.object(act, 'acceptance_child', side_effect=child) as children, \
                        patch.object(act, 'protected', return_value=act.encode({'complete': True})):
                    if failed_child:
                        with self.assertRaises(act.Refusal):act.installed_acceptance('4' * 40, directory, prepared)
                        self.assertFalse((directory / 'acceptance-complete.json').exists())
                    else:
                        self.assertTrue(act.installed_acceptance('4' * 40, directory, prepared)['complete'])
                    self.assertEqual(children.call_count, 1 if failed_child == 'browser' else 2)
                    browser = children.call_args_list[0]
                    self.assertEqual(browser.args[0], ['bash', str(act.SOURCE / 'scripts/run-ruled-mutation.sh'),
                                                       '--declaration', act.DECL, '--', '/usr/bin/node',
                                                       str(act.ACCEPTANCE_BROWSER), '--execute', '4' * 40, str(directory)])
                    if children.call_count == 2:
                        verifier = children.call_args_list[1]
                        self.assertEqual(verifier.args[0], [str(act.APP / '.venv/bin/python'), '-B', str(act.ACCEPTANCE_VERIFIER), '--verify'])
                        self.assertEqual(browser.args[3], verifier.args[3])

    def test_child_timeout_terminates_only_its_process_group_and_never_restarts_or_repeats(self):
        process = Mock();process.pid = 12345;process.__enter__ = Mock(return_value=process);process.__exit__ = Mock(return_value=False)
        process.communicate.side_effect = [subprocess.TimeoutExpired('fictional child', 1), (b'', b'')]
        with tempfile.TemporaryDirectory() as temporary, patch.object(act.subprocess, 'Popen', return_value=process) as launch, \
                patch.object(act.os, 'killpg') as terminate, self.assertRaisesRegex(act.Refusal, 'acceptance_child_stopped_unknown_outcome'):
            act.acceptance_child(['bash', 'fixed-reviewed-child'], Path(temporary), 'browser', act.time.monotonic() + 1200, ruled=True)
        self.assertEqual(launch.call_count, 1);terminate.assert_called_once_with(12345, act.signal.SIGTERM)
        self.assertTrue(launch.call_args.kwargs['start_new_session'])
        self.assertLessEqual(int(launch.call_args.kwargs['env']['RULED_ACT_MAX_SECS']), act.ACCEPTANCE_SECONDS)

    def test_hash_scope_private_artifacts_normal_mfa_and_exclusive_campaign_admission(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary);browser = root / 'browser.mjs';verifier = root / 'verifier.py';output = root / 'campaign'
            paths = {'acceptance_browser_sha256': browser, 'acceptance_verifier_sha256': verifier,
                     'acceptance_options_sha256': root / 'prepared-options.json',
                     'acceptance_allergy_manifest_sha256': root / 'acceptance-v2-inputs/manifest.json',
                     'acceptance_allergy_form_sha256': root / 'acceptance-v2-inputs/allergy-review.docx'}
            for label, path in paths.items():
                path.parent.mkdir(parents=True, exist_ok=True);path.write_bytes(label.encode());path.chmod(0o600)
            admin = root / 'installed-admin-before-activation';admin.mkdir(mode=0o700)
            session = admin / 'browser-session.json';session.write_bytes(b'fictional private browser session');session.chmod(0o600)
            auth = {'format': 1, 'complete': True, 'release': '4' * 40, 'csrf403_no_OTP_noauththrottle': True,
                    'normal_mfa_login': True, 'auth_reset': False,
                    'origin': 'https://app.quillmd.com:9443', 'session_cookie_name': 'quillmd_doctor_session',
                    'actor_id': '11111111-1111-1111-1111-111111111111',
                    'authenticated_at': act.datetime.now(act.timezone.utc).isoformat(),
                    'session_file': str(session), 'session_sha256': act.sha(session.read_bytes())}
            auth_file = admin / 'normal-authentication.json';auth_file.write_bytes(act.encode(auth));auth_file.chmod(0o600)
            scope = {'browser_path': str(browser), 'verifier_path': str(verifier), 'output_path': str(output),
                     'origin': 'https://app.quillmd.com:9443', 'maximum_generations': 5, 'maximum_transcriptions': 1,
                     'provider_usd_limit': '0.70', 'concurrency': 1, 'automatic_retries': False, 'maximum_seconds': 1200,
                     'retains_original_publication_exclusion': True, 'baseline_recovery_after_acceptance_start': False}
            contract = {'acceptance_phase': scope}
            raw = ''.join(label + ': ' + act.sha(path.read_bytes()) + '\n' for label, path in paths.items()).encode()
            with patch.multiple(act, ACCEPTANCE_ROOT=root, ACCEPTANCE_BROWSER=browser, ACCEPTANCE_VERIFIER=verifier, ACCEPTANCE_OUTPUT=output), \
                    patch.object(act, 'declaration', side_effect=lambda: (raw, contract)):
                self.assertEqual(act.acceptance_preparation(contract, '4' * 40)['scope'], scope)
                browser.write_bytes(b'unreviewed changed child')
                with self.assertRaisesRegex(act.Refusal, 'acceptance_reviewed_artifact_identity'):act.acceptance_preparation(contract, '4' * 40)
                browser.write_bytes(b'acceptance_browser_sha256')
                for field, value in (('complete', False), ('release', '5' * 40), ('csrf403_no_OTP_noauththrottle', False),
                                     ('normal_mfa_login', False), ('auth_reset', True), ('authenticated_at', '2999-01-01T00:00:00Z'),
                                     ('authenticated_at', '2020-01-01T00:00:00Z'),
                                     ('session_file', str(root / 'other-session.json')), ('origin', 'https://different.example'),
                                     ('session_cookie_name', 'quillmd_admin_session')):
                    changed = dict(auth);changed[field] = value;auth_file.write_bytes(act.encode(changed))
                    with self.subTest(field=field), self.assertRaises((act.Refusal, ValueError)):
                        act.acceptance_preparation(contract, '4' * 40)
                auth_file.write_bytes(act.encode(auth));output.mkdir()
                with self.assertRaisesRegex(act.Refusal, 'acceptance_campaign_replay'):act.acceptance_preparation(contract, '4' * 40)
                output.rmdir();scope['maximum_generations'] = 6
                with self.assertRaisesRegex(act.Refusal, 'prospective_acceptance_scope'):act.acceptance_preparation(contract, '4' * 40)


class OperatorBoundary(unittest.TestCase):
    def test_reaper_owned_unreferenced_clips_refuse_at_every_age_across_acceptance_horizon(self):
        for extension in ('wav', 'webm', 'mp3', 'm4a'):
            for age_seconds in (1, 2099, 2400, 86400, 8 * 86400):
                with self.subTest(extension=extension, age_seconds=age_seconds):
                    path = 'audio/' + 'a' * 48 + '.' + extension
                    def query(statement):
                        self.assertNotIn('created_at', statement)
                        self.assertIn("action='voice.over_limit_quoted'", statement)
                        self.assertIn("j.input_path=a.details->>'path'", statement)
                        # Model the old cutoff's false-green rather than returning the same canned answer.
                        return [] if '35 minutes' in statement and age_seconds <= 2100 else [(path,)]
                    with self.assertRaisesRegex(act.Refusal, 'worker_reaper_targets'):
                        act.reaper_admission(query, {path: {'sha256': 'existing-original'}})
        for returned, files in (([], {'audio/' + 'b' * 48 + '.wav': {}}),
                                ([('audio/' + 'c' * 48 + '.wav',)], {}),
                                ([('audio/non-reaper-owned.wav',)], {'audio/non-reaper-owned.wav': {}}),
                                ([(None,)], {'existing-custom-form.docx': {}})):
            # A job-referenced clip is absent from the SQL's NOT EXISTS result; missing/non-owned files are safe.
            act.reaper_admission(lambda statement: returned, files)
        with self.assertRaisesRegex(act.Refusal, 'worker_reaper_targets'):
            act.reaper_admission(lambda statement: [], {'submissions/old-normalized-artifact.wav': {}})

    def test_worker_provenance_never_reads_environment_and_refuses_stale_start(self):
        state = {'ActiveState': 'active', 'MainPID': '123', 'ExecMainStartTimestampMonotonic': '5000000'}
        raw = environment()
        unit = b'EnvironmentFile=/opt/meddoc-pro/rebuild/.env\n'
        values = {'/proc/123/cmdline': b'/opt/meddoc-pro/rebuild/.venv/bin/python\0/opt/meddoc-pro/rebuild/manage.py\0worker\0',
                  '/proc/123/cgroup': b'0::/system.slice/quillmd-fresh-worker.service\n',
                  '/proc/123/stat': '123 (python) ' + ' '.join(['0'] * 19 + ['500']),
                  str(act.APP / 'deploy' / act.UNITS[2]): unit}
        def path(value):
            return FakePath(str(value))
        class FakePath:
            def __init__(self, name): self.name = name
            def __truediv__(self, other): return FakePath(self.name + '/' + str(other))
            def joinpath(self, other): return self / other
            def read_bytes(self):
                self.assert_safe(); return values[self.name]
            def read_text(self):
                self.assert_safe(); value = values[self.name]
                return value.decode() if isinstance(value, bytes) else value
            def assert_safe(self):
                if self.name.endswith('/environ'): raise AssertionError('foreign environment read forbidden')
            def __str__(self): return self.name
        host = act.Host(Mock());host.state = Mock(return_value=state);host.helper = Mock(side_effect=AssertionError('no helper needed'))
        with patch.object(act, 'Path', side_effect=path), patch.object(act, 'APP', FakePath(str(act.APP))), \
                patch.object(act, 'protected', return_value=raw), \
                patch.object(act.os, 'sysconf', return_value=100), patch.object(act, 'git', return_value=unit):
            report = host.worker_configuration(raw, act.BASELINE, {act.UNITS[2]: state})
            self.assertFalse(report['direct_environment_readback'])
            self.assertFalse(report['actual_provider_model_verified'])
            self.assertEqual(report['values']['QUILLMD_AI_MODEL'], 'claude-sonnet-4-6')
            for cgroup in (b'0::/system.slice/quillmd-fresh-worker.service-unrelated\n',
                           b'0::/system.slice/quillmd-fresh-worker.service/child\n',
                           b'1:name=systemd:/system.slice/quillmd-fresh-worker.service\n',
                           b'0::/../quillmd-fresh-worker.service\n',
                           b'0::/system.slice/../system.slice/quillmd-fresh-worker.service\n',
                           b'0::/system.slice/quillmd-fresh-worker.service \n',
                           b'0::/system.slice/quillmd-fresh-worker.service\t\n',
                           b'0::/system.slice/quillmd-fresh-worker.service\r\n',
                           b' 0::/system.slice/quillmd-fresh-worker.service\n',
                           b'0::/system.slice/quillmd-fresh-worker.service\n\n',
                           b'0::/system.slice/quillmd-fresh-worker.service'):
                values['/proc/123/cgroup'] = cgroup
                with self.subTest(cgroup=cgroup), self.assertRaisesRegex(act.Refusal, 'worker_cgroup_identity'):
                    host.worker_configuration(raw, act.BASELINE, {act.UNITS[2]: state})
            values['/proc/123/cgroup'] = b'0::/system.slice/quillmd-fresh-worker.service\n'
            state['ExecMainStartTimestampMonotonic'] = '9000000'
            with self.assertRaisesRegex(act.Refusal, 'worker_kernel_systemd_start_identity'):
                host.worker_configuration(raw, act.BASELINE, {act.UNITS[2]: state})
        host.helper.assert_not_called()

    def test_backup_permanent_root_source_and_reference_population(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / 'backups';root.mkdir(mode=0o700)
            capture = root / '20261006T192011Z-c6f27e26';capture.mkdir(mode=0o700)
            raw = b'fictional encrypted manifest'
            manifest = {'run_id': capture.name, 'source_commit': act.BASELINE, 'database': 'quillmd_fresh',
                        'container_id': 'fictional', 'image_id': 'sha256:' + 'a' * 64,
                        'tables': {'fictional': {'rows': 1}}, 'invariants': {},
                        'files': [{'path': 'receipt/fake.json', 'sha256': 'a' * 64, 'size': 1, 'object': 'objects/fake.fernet'}], 'dump': {}}
            snapshot = {'database': {'tables': manifest['tables'], 'invariants': {},
                                    'referenced_files': {'receipt/fake.json': 'a' * 64}},
                        'files': {'receipt/fake.json': {'sha256': 'a' * 64, 'size': 1}}}
            backup = Mock();backup.load_backup.return_value = (capture, manifest)
            backup.inspect_container.return_value = {'Id': manifest['container_id'], 'Image': manifest['image_id'],
                                                      'State': {'Running': True}, 'HostConfig': {'PortBindings': {
                                                          '5432/tcp': [{'HostIp': '127.0.0.1', 'HostPort': '55438'}]}}}
            proof = act.encode({'complete': True, 'independent_key_restore_verified': True,
                                'isolated_restore': {'complete': True, 'all_table_hashes_match': True,
                                                     'all_file_hashes_match': True, 'workers_started': 0}})
            def read(path, *args): return proof if path == act.RESTORE else raw
            with patch.object(act, 'BACKUPS', root), patch.object(act, 'protected', side_effect=read), \
                    patch.object(act, 'RESTORE_SHA', act.sha(proof)):
                self.assertTrue(act.verify_backup(capture, act.sha(raw), snapshot, backup)['all_current_tables_covered'])
                manifest['source_commit'] = 'e' * 40
                with self.assertRaisesRegex(act.Refusal, 'backup_source_identity'):
                    act.verify_backup(capture, act.sha(raw), snapshot, backup)
                manifest['source_commit'] = act.BASELINE;manifest['files'] = []
                with self.assertRaisesRegex(act.Refusal, 'backup_current_reference_coverage'):
                    act.verify_backup(capture, act.sha(raw), snapshot, backup)
                alias = root / '20261006T192011Z-aaaaaaaa';alias.symlink_to(capture, target_is_directory=True)
                with self.assertRaisesRegex(act.Refusal, 'backup_destination'):
                    act.verify_backup(alias, act.sha(raw), snapshot, backup)

    def test_scoped_source_reverse_recovers_interrupted_index_and_refuses_foreign_bytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            def git(*args):
                return subprocess.check_output(['git', '-C', str(root), *args], stderr=subprocess.DEVNULL).strip().decode()
            git('init', '-q', '-b', 'main');git('config', 'user.name', 'Fictional');git('config', 'user.email', 'fixture@example.invalid')
            message = root / '.git/fixture-message'
            message.write_text('fictional baseline\n')
            root.joinpath('old').write_text('old\n');git('add', 'old');git('commit', '-q', '-F', str(message))
            baseline = git('rev-parse', 'HEAD')
            root.joinpath('old').write_text('new\n');root.joinpath('added').write_text('added\n')
            message.write_text('fictional target\n')
            git('add', 'old', 'added');git('commit', '-q', '-F', str(message));target = git('rev-parse', 'HEAD')
            with patch.object(act, 'ROOT', root), patch.object(act, 'BASELINE', baseline), patch.object(act, 'ALLOWED', {'old', 'added'}):
                root.joinpath('old').write_text('unrelated authored work\n')
                with self.assertRaisesRegex(act.Refusal, 'recovery_unqualified_source_bytes'):act.restore_source(target)
                root.joinpath('old').write_text('new\n')
                git('restore', '--source=' + baseline, '--staged', '--worktree', '--', 'old', 'added')
                root.joinpath('old').write_text('new\n')
                self.assertEqual(git('rev-parse', 'HEAD'), target)
                self.assertEqual(act.restore_source(target)['source'], baseline)
                self.assertEqual(git('status', '--porcelain'), '')
                self.assertFalse(root.joinpath('added').exists())

    def test_default_plan_does_not_read_installed_state(self):
        with patch.object(act, 'protected') as secret, patch.object(act, 'command') as command, \
                patch.object(act, 'modules') as modules, patch('sys.stdout', new=StringIO()):
            self.assertEqual(act.main([]), 0)
            secret.assert_not_called()
            command.assert_not_called()
            modules.assert_not_called()

    def test_systemctl_allowlist_refuses_database_public_timer_and_other_verb(self):
        host = act.Host(Mock())
        host.helper = Mock()
        for action, unit in (('restart', act.UNITS[0]), ('stop', 'quillmd-fresh-database.service'),
                             ('start', 'nginx.service'), ('stop', 'quillmd-fresh-backup.timer')):
            with self.assertRaises(act.Refusal):
                host.service(action, unit)
        host.helper.assert_not_called()

    def test_failed_state_read_and_stop_do_not_skip_other_units(self):
        host = Mock()
        stopped = []
        def state(unit):
            if unit == act.UNITS[0]:
                raise OSError('fictional state failure')
            return {'ActiveState': 'inactive' if unit in stopped else 'active',
                    'MainPID': '0' if unit in stopped else '12'}
        def service(action, unit):
            if unit == act.UNITS[0]:
                raise OSError('fictional stop failure')
            stopped.append(unit)
        host.state.side_effect, host.service.side_effect = state, service
        result = act.best_effort_private_stop(host)
        self.assertEqual(host.service.call_args_list, [unittest.mock.call('stop', unit) for unit in act.UNITS])
        self.assertEqual(stopped, list(act.UNITS[1:]))
        self.assertFalse(result[act.UNITS[0]]['stopped_verified'])
        self.assertTrue(all(result[unit]['stopped_verified'] for unit in act.UNITS[1:]))

    def test_static_root_mode_change_is_detected_and_root_symlink_refuses(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / 'static'
            root.mkdir(mode=0o755)
            root.chmod(0o755)
            root.joinpath('app.css').write_bytes(b'fictional css')
            before = act.inventory(root)
            root.chmod(0o777)
            after = act.inventory(root)
            self.assertEqual(before['app.css'], after['app.css'])
            self.assertNotEqual(before['.'], after['.'])
            alias = Path(temporary) / 'alias'
            alias.symlink_to(root, target_is_directory=True)
            with self.assertRaises(act.Refusal):
                act.inventory(alias)

    def test_actual_configuration_helper_includes_security_roots(self):
        with tempfile.TemporaryDirectory() as temporary:
            prefix = str(Path(temporary) / 'host')
            roots = [Path(prefix) / relative for relative in ('etc/systemd/system', 'etc/nginx', 'etc/ssh')]
            for root in roots:
                root.mkdir(parents=True, mode=0o755)
                root.chmod(0o755)
            caddy = Path(prefix) / 'opt/meddoc-pro/Caddyfile'
            caddy.parent.mkdir(parents=True)
            caddy.write_bytes(b'fictional caddy')
            host = act.Host(Mock())
            def fake_helper(code, timeout):
                output = StringIO()
                with redirect_stdout(output):
                    exec(compile(code.replace('/host', prefix), '<fictional-read-only-helper>', 'exec'), {})
                return output.getvalue().encode()
            host.helper = fake_helper
            before = host.configuration()
            roots[1].chmod(0o777)
            after = host.configuration()
            key = next(key for key in before if key.endswith('/etc/nginx'))
            self.assertEqual(before[key]['mode'], 0o755)
            self.assertEqual(after[key]['mode'], 0o777)
            self.assertNotEqual(before, after)
            roots[2].rename(roots[2].with_name('ssh-original'))
            roots[2].symlink_to(roots[2].with_name('ssh-original'), target_is_directory=True)
            with self.assertRaises(SystemExit):
                host.configuration()

    def test_simple_unit_start_waits_for_new_pid_proof_but_never_retries_bad_policy(self):
        expected = {'fictional_unit': {'MainPID': '12'}}
        with patch.object(act, 'service_boundary', side_effect=[act.Refusal('same_pid_boundary_proof'), expected]) as boundary, \
                patch.object(act.time, 'sleep'):
            self.assertEqual(act.await_service_boundary(Mock(), Mock(), act.BASELINE), expected)
            self.assertEqual(boundary.call_count, 2)
        with patch.object(act, 'service_boundary', side_effect=act.Refusal('private_unit_source_identity')) as boundary, \
                self.assertRaises(act.Refusal):
            act.await_service_boundary(Mock(), Mock(), act.BASELINE)
        self.assertEqual(boundary.call_count, 1)

    def test_http_startup_wait_is_read_only_and_contract_failure_stops_immediately(self):
        import httpx
        with patch.object(act, 'health', side_effect=[httpx.ConnectError('fictional startup'), []]) as health, \
                patch.object(act.time, 'sleep'):
            self.assertEqual(act.await_health(act.BASELINE), [])
            self.assertEqual(health.call_count, 2)
        with patch.object(act, 'health', side_effect=act.Refusal('public_maintenance')) as health, \
                self.assertRaises(act.Refusal):
            act.await_health(act.BASELINE)
        self.assertEqual(health.call_count, 1)

    def test_unrelated_main_passenger_refuses_before_any_act(self):
        source = act.ROOT / '.worktrees/fictional-operator'
        commit = '3' * 40
        def fake_git(tree, *args):
            if args == ('rev-parse', 'HEAD'):
                return commit.encode()
            if args[:2] == ('status', '--porcelain'):
                return b''
            if args[:2] == ('merge-base', '--is-ancestor'):
                return b''
            if args[:2] == ('diff', '--name-only'):
                return (act.SELF + '\n' + act.DECL + '\nrebuild/core/generation.py\n').encode()
            raise AssertionError('refusal failed to stop before downstream operation')
        with patch.object(act, 'SOURCE', source), patch.object(Path, 'resolve', return_value=source), \
                patch.object(act, 'git', side_effect=fake_git), self.assertRaises(act.Refusal):
            act.source_gate(commit, {}, executing=True)

    def test_baseline_and_one_capture_are_inside_exclusion_after_cadence_and_private_drain(self):
        for post_capture_drift in (False, True):
            with self.subTest(post_capture_drift=post_capture_drift), tempfile.TemporaryDirectory() as temporary:
                runtime = Path(temporary);target = '4' * 40;original = environment()
                updated, configuration = act.render(original, target)
                current_env = [original];held = [False];captured = [False];calls = []
                population = {'database': {'tables': {'core_servicehealth': {'sha256': 'previous-cadence'}}},
                              'files': {}, 'mail': {}, 'static': {}, 'configuration': {}}
                states = {unit: {'ActiveState': 'active', 'MainPID': str(index + 1),
                                 'ExecMainStartTimestampMonotonic': '1'} for index, unit in enumerate(act.UNITS)}
                old_units = deepcopy(states)
                host, backup, storage, exclusion, writer = Mock(), Mock(), Mock(), Mock(), Mock()
                backup.key_at.return_value.encrypt.side_effect = lambda value: b'fictional encrypted ' + value
                storage.inventory.return_value = {}
                host.state.side_effect = lambda unit: deepcopy(states[unit]) if unit in states else {'ActiveState': 'inactive', 'MainPID': '0'}
                def service(action, unit):
                    self.assertTrue(held[0]);calls.append((action, unit))
                    states[unit] = {'ActiveState': 'inactive' if action == 'stop' else 'active',
                                    'MainPID': '0' if action == 'stop' else str(11 + act.UNITS.index(unit)),
                                    'ExecMainStartTimestampMonotonic': '2'}
                host.service.side_effect = service
                host.worker_configuration.return_value = {'values': configuration['values']}
                @contextmanager
                def hold(*args):
                    # A normal publisher cadence finishes before this operation obtains exclusion.
                    population['database']['tables']['core_servicehealth']['sha256'] = 'current-cadence'
                    held[0] = True
                    try: yield
                    finally: held[0] = False
                exclusion.hold.side_effect = hold
                def snapshot(*args):
                    self.assertTrue(held[0], 'Authoritative baseline must not race the publisher before exclusion')
                    value = deepcopy(population)
                    if captured[0] and post_capture_drift:
                        value['database']['tables']['core_servicehealth']['sha256'] = 'unexpected-writer'
                    return value
                def capture(primitive, baseline, destination, contract):
                    self.assertTrue(held[0]);self.assertTrue(all(row['MainPID'] == '0' for row in states.values()))
                    self.assertEqual(baseline['database']['tables']['core_servicehealth']['sha256'], 'current-cadence')
                    captured[0] = True;calls.append(('capture',))
                    return {'run_id': '20261006T235959Z-aaaaaaaa', 'manifest_cipher_sha256': 'f' * 64,
                            'stopped_before_fingerprint_sha256': act.sha(act.encode(baseline)), 'capture_attempts': 1}
                def git(tree, *args):
                    if args[:2] == ('merge', '--ff-only'):
                        receipts = list(runtime.glob('legacy-model-demo-*/fresh_backup_verified.json'))
                        self.assertEqual(len(receipts), 1)
                        evidence = json.loads(receipts[0].read_bytes())
                        self.assertEqual(evidence['backup']['manifest_cipher_sha256'], 'f' * 64)
                        self.assertEqual(evidence['backup']['stopped_before_fingerprint_sha256'], act.sha(act.encode(population)))
                        self.assertTrue(held[0]);self.assertTrue(all(row['MainPID'] == '0' for row in states.values()))
                        calls.append(('source',))
                    return target.encode()
                writer.replace_environment.side_effect = lambda path, before, after: current_env.__setitem__(0, after)
                args = SimpleNamespace(operator_commit=target, fresh_backup=True)
                with patch.multiple(act, RUNTIME=runtime, CAPTURE_ATTEMPT=runtime / 'fresh-attempt.json'), patch.object(act, 'protected', side_effect=lambda *args: current_env[0]), \
                        patch.object(act, 'storage_admission', return_value={}), patch.object(act, 'prepare_static', return_value={}), \
                        patch.object(act, 'install_static', return_value={}), patch.object(act, 'inventory', return_value={}), \
                        patch.object(act, 'health'), patch.object(act, 'await_health'), \
                        patch.object(act, 'service_boundary', return_value=old_units), \
                        patch.object(act, 'await_service_boundary', side_effect=lambda *args: deepcopy(states)), \
                        patch.object(act, 'database', return_value={}), patch.object(act, 'snapshot', side_effect=snapshot), \
                        patch.object(act, 'capture_current_backup', side_effect=capture) as capture_call, \
                        patch.object(act, 'operation_locks', return_value=nullcontext()), patch.object(act, 'git', side_effect=git), \
                        patch('sys.stdout', new=StringIO()):
                    if post_capture_drift:
                        with self.assertRaisesRegex(act.Refusal, 'activation_failed_recovery_required'):
                            act.execute(args, {'rollback_qualified': True, 'environment_before_sha256': act.sha(original)}, {}, {'shared_head': act.BASELINE},
                                        host=host, backup=backup, storage=storage, exclusion=exclusion, env_writer=writer)
                        writer.replace_environment.assert_not_called();self.assertNotIn(('source',), calls)
                        self.assertTrue(all(row['MainPID'] == '0' for row in states.values()))
                    else:
                        outcome = act.execute(args, {'rollback_qualified': True, 'environment_before_sha256': act.sha(original)}, {}, {'shared_head': act.BASELINE},
                                              host=host, backup=backup, storage=storage, exclusion=exclusion, env_writer=writer)
                        self.assertTrue(outcome['complete']);self.assertEqual(outcome['provider_calls'], 0)
                        self.assertEqual(current_env[0], updated)
                        self.assertEqual(calls[:5], [('stop', unit) for unit in act.UNITS] + [('capture',), ('source',)])
                    self.assertEqual(capture_call.call_count, 1);backup.backup.assert_not_called()

    def test_failure_before_private_drain_leaves_previous_services_running(self):
        with tempfile.TemporaryDirectory() as temporary:
            runtime = Path(temporary);raw = environment()
            host, backup, storage, exclusion, writer = Mock(), Mock(), Mock(), Mock(), Mock()
            backup.key_at.return_value.encrypt.side_effect = lambda value: b'fictional ' + value
            exclusion.hold.return_value = nullcontext()
            host.state.return_value = {'ActiveState': 'active', 'MainPID': '123'}
            args = SimpleNamespace(operator_commit='4' * 40, fresh_backup=True)
            with patch.multiple(act, RUNTIME=runtime, CAPTURE_ATTEMPT=runtime / 'fresh-attempt.json'), patch.object(act, 'protected', return_value=raw), \
                    patch.object(act, 'storage_admission', return_value={}), patch.object(act, 'prepare_static', return_value={}), \
                    patch.object(act, 'health'), patch.object(act, 'service_boundary', return_value={}), \
                    patch.object(act, 'operation_locks', return_value=nullcontext()), \
                    patch.object(act, 'snapshot') as snapshot, patch.object(act, 'capture_current_backup') as capture, \
                    patch.object(act, 'git', return_value=act.BASELINE.encode()), patch('sys.stdout', new=StringIO()), \
                    self.assertRaises(act.Refusal):
                act.execute(args, {'rollback_qualified': True, 'environment_before_sha256': act.sha(raw)}, {}, {'shared_head': act.BASELINE},
                            host=host, backup=backup, storage=storage, exclusion=exclusion, env_writer=writer)
            host.service.assert_not_called();snapshot.assert_not_called();capture.assert_not_called()
            writer.replace_environment.assert_not_called()

    def test_spent_or_symlink_capture_attempt_refuses_before_environment_reads_and_private_stop(self):
        from ops import backup_restore as primitive
        for symlink in (False, True):
            with self.subTest(symlink=symlink), tempfile.TemporaryDirectory() as temporary:
                runtime = Path(temporary);runtime.chmod(0o700)
                marker = runtime / 'attempt.json'
                if symlink: marker.symlink_to(runtime / 'missing')
                else: marker.write_bytes(b'one consumed attempt');marker.chmod(0o600)
                host, backup, storage, exclusion, writer = Mock(), Mock(), Mock(), Mock(), Mock()
                backup.private_dir.side_effect = primitive.private_dir
                with patch.object(act, 'CAPTURE_ATTEMPT', marker), patch.object(act, 'storage_admission', return_value={}), \
                        patch.object(act, 'protected') as protected, patch.object(act, 'capture_current_backup') as capture, \
                        self.assertRaisesRegex(act.Refusal, 'fresh_capture_attempt_already_consumed'):
                    act.execute(SimpleNamespace(fresh_backup=True), {'rollback_qualified': True}, {}, {}, host=host, backup=backup,
                                storage=storage, exclusion=exclusion, env_writer=writer)
                protected.assert_not_called();host.service.assert_not_called();capture.assert_not_called()
                writer.replace_environment.assert_not_called()

    def test_population_drift_during_drain_never_writes_environment_or_advances_main(self):
        with tempfile.TemporaryDirectory() as temporary:
            runtime = Path(temporary)
            raw = environment()
            host = Mock()
            host.state.return_value = {'ActiveState': 'inactive', 'MainPID': '0'}
            backup = Mock()
            backup.key_at.return_value.encrypt.side_effect = lambda value: b'FICTIONAL_CIPHERTEXT:' + value
            storage = Mock()
            storage.inventory.return_value = {}
            exclusion = Mock()
            exclusion.hold.return_value = nullcontext()
            writer = Mock()
            units = {unit: {'MainPID': str(index + 1), 'ExecMainStartTimestampMonotonic': '1'}
                     for index, unit in enumerate(act.UNITS)}
            args = SimpleNamespace(operator_commit='4' * 40, fresh_backup=True)
            contract = {'rollback_qualified': True, 'environment_before_sha256': act.sha(raw), 'backup_manifest_sha256': '0' * 64}
            with patch.multiple(act, RUNTIME=runtime, CAPTURE_ATTEMPT=runtime / 'fresh-attempt.json'), patch.object(act, 'protected', return_value=raw), \
                    patch.object(act, 'storage_admission', return_value={}), \
                    patch.object(act, 'prepare_static', return_value={}), \
                    patch.object(act, 'health'), patch.object(act, 'service_boundary', return_value=units), \
                    patch.object(act, 'capture_current_backup', return_value={}) as capture, patch.object(act, 'database', return_value={}), \
                    patch.object(act, 'snapshot', side_effect=[{'population': 'before'}, {'population': 'drifted'}]), \
                    patch.object(act, 'operation_locks', return_value=nullcontext()), \
                    patch.object(act, 'git', return_value=act.BASELINE.encode()) as git, \
                    patch('sys.stdout', new=StringIO()), self.assertRaises(act.Refusal):
                act.execute(args, contract, {}, {'shared_head': act.BASELINE}, host=host, backup=backup,
                            storage=storage, exclusion=exclusion, env_writer=writer)
            writer.replace_environment.assert_not_called()
            capture.assert_not_called()
            self.assertEqual(host.service.call_args_list, [unittest.mock.call('stop', unit) for unit in act.UNITS])
            self.assertFalse(any(call.args[1:2] == ('merge',) for call in git.call_args_list))
            failure = list(runtime.glob('legacy-model-demo-*/failed.json'))
            self.assertEqual(len(failure), 1)
            self.assertFalse(json.loads(failure[0].read_bytes())['complete'])

    def test_activation_enospc_failure_evidence_cannot_leave_new_services_active(self):
        with tempfile.TemporaryDirectory() as temporary:
            runtime = Path(temporary)
            target = '4' * 40
            original = environment()
            updated, report = act.render(original, target)
            current = [original]
            states = {unit: {'ActiveState': 'active', 'MainPID': str(index + 1),
                             'ExecMainStartTimestampMonotonic': '1'} for index, unit in enumerate(act.UNITS)}
            old_units = deepcopy(states)
            host = Mock()
            def state(unit):
                return dict(states[unit]) if unit in states else {'ActiveState': 'inactive', 'MainPID': '0'}
            def service(action, unit):
                states[unit] = {'ActiveState': 'inactive' if action == 'stop' else 'active',
                                'MainPID': '0' if action == 'stop' else str(11 + act.UNITS.index(unit)),
                                'ExecMainStartTimestampMonotonic': '2'}
            host.state.side_effect, host.service.side_effect = state, service
            host.worker_configuration.return_value = {'values': report['values']}
            backup, storage, exclusion, writer = Mock(), Mock(), Mock(), Mock()
            backup.key_at.return_value.encrypt.side_effect = lambda value: b'FICTIONAL_CIPHER:' + value
            storage.inventory.return_value = {}
            exclusion.hold.return_value = nullcontext()
            writer.replace_environment.side_effect = lambda path, before, after: current.__setitem__(0, after)
            original_write = act.write_new
            def write(path, raw):
                if path.name.startswith('failed'):
                    raise OSError(errno.ENOSPC, 'fictional full evidence volume')
                original_write(path, raw)
            args = SimpleNamespace(operator_commit=target, fresh_backup=True)
            contract = {'rollback_qualified': True, 'environment_before_sha256': act.sha(original), 'backup_manifest_sha256': '0' * 64}
            with patch.multiple(act, RUNTIME=runtime, CAPTURE_ATTEMPT=runtime / 'fresh-attempt.json'), patch.object(act, 'protected', side_effect=lambda *args: current[0]), \
                    patch.object(act, 'storage_admission', return_value={}), \
                    patch.object(act, 'prepare_static', return_value={}), patch.object(act, 'install_static', return_value={}), \
                    patch.object(act, 'inventory', return_value={}), \
                    patch.object(act, 'write_new', side_effect=write), patch.object(act, 'health'), patch.object(act, 'await_health'), \
                    patch.object(act, 'service_boundary', return_value=old_units), \
                    patch.object(act, 'await_service_boundary', side_effect=lambda *args: deepcopy(states)), \
                    patch.object(act, 'capture_current_backup', return_value={}), patch.object(act, 'database', return_value={}), \
                    patch.object(act, 'snapshot', side_effect=[{'population': 1}, {'population': 1}, {'population': 1}, {'population': 1}, {'population': 1, 'static': {}}, {'population': 2}]), \
                    patch.object(act, 'operation_locks', return_value=nullcontext()), \
                    patch.object(act, 'git', return_value=target.encode()), patch('sys.stdout', new=StringIO()), \
                    self.assertRaises(act.Refusal):
                act.execute(args, contract, {}, {'shared_head': act.BASELINE}, host=host, backup=backup,
                            storage=storage, exclusion=exclusion, env_writer=writer)
            self.assertEqual(current[0], updated)
            self.assertTrue(all(value['ActiveState'] == 'inactive' and value['MainPID'] == '0' for value in states.values()))
            self.assertEqual(sum(call.args[0] == 'stop' for call in host.service.call_args_list), 6)

    def test_rollback_enospc_failure_evidence_still_invokes_independent_fail_stop(self):
        with tempfile.TemporaryDirectory() as temporary:
            runtime = Path(temporary)
            directory = runtime / 'legacy-model-demo-fictional'
            directory.mkdir(mode=0o700)
            target = '4' * 40
            original = environment()
            updated, _ = act.render(original, target)
            host, backup, storage, exclusion, writer = Mock(), Mock(), Mock(), Mock(), Mock()
            backup.key_at.return_value.decrypt.side_effect = lambda value: value
            exclusion.hold.return_value = nullcontext()
            host.state.return_value = {'ActiveState': 'inactive', 'MainPID': '0'}
            writer.replace_environment.side_effect = OSError('fictional restore failure')
            original_write = act.write_new
            def write(path, raw):
                if path.name == 'failed.json':
                    raise OSError(errno.ENOSPC, 'fictional full evidence volume')
                original_write(path, raw)
            def read(path, *args):
                if path.name == 'prepared.json':
                    return act.encode({'source': {'operator_commit': target}, 'configuration': {'before_sha256': act.sha(original)},
                                       'before': {}, 'static_preparation': {}})
                return original if path.name == 'environment-before.fernet' else updated
            args = SimpleNamespace(operator_commit=target, activation_directory=directory)
            with patch.multiple(act, RUNTIME=runtime, CAPTURE_ATTEMPT=runtime / 'fresh-attempt.json'), patch.object(act, 'protected', side_effect=read), \
                    patch.object(act, 'storage_admission', return_value={}), \
                    patch.object(act, 'write_new', side_effect=write), patch.object(act, 'snapshot', return_value={}), \
                    patch.object(act, 'restore_static', return_value={}), patch.object(act, 'restore_source', return_value={}), \
                    patch.object(act, 'operation_locks', return_value=nullcontext()), \
                    patch.object(act, 'git', return_value=target.encode()), \
                    patch.object(act, 'best_effort_private_stop', return_value={}) as stop, \
                    self.assertRaises(act.Refusal):
                act.rollback(args, {}, contract={'rollback_qualified': True}, host=host, backup=backup, storage=storage, exclusion=exclusion, env_writer=writer)
            stop.assert_called_once_with(host)

    def test_standalone_rollback_cadence_or_clinical_drift_refuses_before_stopping_coherent_services(self):
        for drift in ('core_servicehealth', 'core_encounter'):
            with self.subTest(drift=drift), tempfile.TemporaryDirectory() as temporary:
                runtime = Path(temporary);directory = runtime / 'legacy-model-demo-fictional';directory.mkdir(mode=0o700)
                target = '4' * 40;original = environment();updated, _ = act.render(original, target)
                before = {'database': {'tables': {name: {'sha256': 'before'} for name in ('core_servicehealth', 'core_encounter')}},
                          'files': {}, 'mail': {}, 'configuration': {}, 'static': {}}
                current = deepcopy(before);current['database']['tables'][drift]['sha256'] = 'new-real-row'
                host, backup, storage, exclusion, writer = Mock(), Mock(), Mock(), Mock(), Mock()
                backup.key_at.return_value.decrypt.side_effect = lambda raw: raw
                exclusion.hold.return_value = nullcontext()
                def read(path, *args):
                    if path.name == 'prepared.json':
                        return act.encode({'source': {'operator_commit': target}, 'configuration': {'before_sha256': act.sha(original)},
                                           'before': before, 'static_preparation': {}})
                    return original if path.name == 'environment-before.fernet' else updated
                with patch.object(act, 'RUNTIME', runtime), patch.object(act, 'protected', side_effect=read), \
                        patch.object(act, 'storage_admission', return_value={}), patch.object(act, 'snapshot', return_value=current), \
                        patch.object(act, 'operation_locks', return_value=nullcontext()), \
                        patch.object(act, 'restore_static') as restore_static, patch.object(act, 'restore_source') as restore_source, \
                        patch.object(act, 'git', return_value=target.encode()), self.assertRaises(act.Refusal):
                    act.rollback(SimpleNamespace(operator_commit=target, activation_directory=directory), {},
                                 contract={'rollback_qualified': True}, host=host, backup=backup, storage=storage,
                                 exclusion=exclusion, env_writer=writer)
                host.service.assert_not_called();writer.replace_environment.assert_not_called()
                restore_static.assert_not_called();restore_source.assert_not_called()


if __name__ == '__main__':
    unittest.main()
