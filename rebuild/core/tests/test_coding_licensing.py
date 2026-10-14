"""Synthetic documents exercise the entitlement gate, never a real CPT grant."""
import ast
from copy import deepcopy
from datetime import date
import hashlib
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.core.management.base import CommandError
from django.test import SimpleTestCase, override_settings

from core import coding_licensing as licensing


def synthetic_rules(release):
    return {'format': 'quillmd-cpt-rules-v1', 'release': deepcopy(release),
        'index': [{'code': '00000', 'terms': ['synthetic procedure'], 'reference': 'SYNTHETIC index A'},
                  {'code': '00001', 'terms': ['synthetic office'], 'reference': 'SYNTHETIC index B'}],
        'tabular': {'codes': {
            '00000': {'description': 'SYNTHETIC procedure fixture; not a CPT descriptor', 'kind': 'procedure',
                'reference': 'SYNTHETIC rule A', 'instructions': ['SYNTHETIC documentation condition.'],
                'requirements': {'performed_terms': ['synthetic procedure performed'],
                    'required_details': [{'name': 'side', 'terms': ['left'], 'reference': 'SYNTHETIC side rule'}]}},
            '00001': {'description': 'SYNTHETIC office fixture; not a CPT descriptor', 'kind': 'office_em',
                'reference': 'SYNTHETIC rule B', 'instructions': [],
                'requirements': {'setting': 'outpatient_office', 'patient_status': 'established',
                    'mdm': {'required_elements': 2, 'problems': ['moderate', 'high'], 'data': ['moderate', 'high'], 'risk': ['moderate', 'high'],
                            'evidence_terms': {'problems': ['problem evidence'], 'data': ['data evidence'], 'risk': ['risk evidence']}},
                    'time': {'minimum': 41, 'maximum': 47, 'basis': 'total_practitioner_same_day',
                             'total_time_terms': ['total practitioner time'], 'excluded_activities': ['SYNTHETIC separately reported activity']}}}}}}


class EntitlementFixture(SimpleTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.root.chmod(0o700)
        self.path = self.root / 'entitlement.json'
        self.release = {'version': 'SYNTHETIC-2026', 'effective_from': '2026-01-01', 'effective_until': '2026-12-31',
                        'source_url': 'https://example.invalid/synthetic-licensed-feed', 'sha256': 'a' * 64, 'code_count': 2}
        self.rules = synthetic_rules(self.release)
        self.manifest = {'format': 'quillmd-cpt-entitlement-v1',
            'agreement': self.artifact('agreement.txt', b'SYNTHETIC executed-agreement fixture; conveys no actual rights.'),
            'issuer': 'SYNTHETIC licensing test issuer', 'license_id': 'SYNTHETIC-test-reference', 'product': 'QuillMD',
            'users': {'scope': 'all_authorized_quillmd_users', 'terms_reference': 'SYNTHETIC users clause'},
            'distribution': {'uses': ['application_display', 'clinical_export', 'coding_suggestions'], 'terms_reference': 'SYNTHETIC distribution clause'},
            'intended_ai_use': {'uses': ['provider_processing', 'coding_assistance'], 'training': 'not_authorized_by_this_application', 'terms_reference': 'SYNTHETIC AI clause'},
            'validity': {'from': '2025-01-01', 'until': '2027-12-31'}, 'content_release': self.release,
            'rules': self.artifact('rules.json', licensing.canonical(self.rules)), 'permission_review': {}}
        self.write_manifest()
        self.settings = override_settings(CPT_ENTITLEMENT_MANIFEST=str(self.path), CPT_LICENSE_ID='environment-only', CPT_LICENSE_EXPIRY='2099-01-01')
        self.settings.enable()
        self.addCleanup(self.settings.disable)
        self.clock = patch.object(licensing.timezone, 'localdate', return_value=date(2026, 10, 14))
        self.clock.start()
        self.addCleanup(self.clock.stop)

    def artifact(self, name, raw):
        path = self.root / name
        path.write_bytes(raw)
        path.chmod(0o600)
        return {'filename': name, 'sha256': hashlib.sha256(raw).hexdigest()}

    def write_manifest(self, rereview=True):
        if rereview:
            review = {'format': 'quillmd-cpt-permission-review-v1', 'reviewed_by': 'SYNTHETIC permission reviewer',
                      'reviewed_at': '2026-10-14', 'decision': 'approved',
                      'coverage': {key: deepcopy(self.manifest[key]) for key in ('agreement', 'issuer', 'license_id', 'product', 'users', 'distribution', 'intended_ai_use', 'validity', 'content_release', 'rules')}}
            self.manifest['permission_review'] = self.artifact('review.json', licensing.canonical(review))
        self.artifact(self.path.name, licensing.canonical(self.manifest))


class CPTLicensingTests(EntitlementFixture):
    def configured_manifest(self, environment):
        # Execute the real settings assignment without loading any application
        # environment file, credential or database configuration.
        source = Path(__file__).resolve().parents[2] / 'quillmd' / 'settings.py'
        assignments = [node for node in ast.parse(source.read_text()).body
            if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name)
                and target.id == 'CPT_ENTITLEMENT_MANIFEST' for target in node.targets)]
        self.assertEqual(len(assignments), 1)
        namespace = {'os': SimpleNamespace(getenv=lambda key, default=None: environment.get(key, default))}
        exec(compile(ast.Module(body=assignments, type_ignores=[]), str(source), 'exec'), namespace)
        return namespace['CPT_ENTITLEMENT_MANIFEST']

    def test_explicit_environment_selects_protected_evidence_and_default_is_unchanged(self):
        self.assertEqual(self.configured_manifest({}), licensing.DEFAULT_MANIFEST)
        self.assertEqual(self.configured_manifest({'CPT_ENTITLEMENT_MANIFEST': '/unrecognized'}),
                         licensing.DEFAULT_MANIFEST)
        selected = self.configured_manifest({'QUILLMD_CPT_ENTITLEMENT_MANIFEST': str(self.path)})
        with override_settings(CPT_ENTITLEMENT_MANIFEST=selected):
            self.assertEqual(licensing.verified_entitlement()['manifest'], self.manifest)
        for value in ('', 'relative.json', str(self.root / 'missing.json')):
            with self.subTest(path=value), override_settings(CPT_ENTITLEMENT_MANIFEST=self.configured_manifest(
                    {'QUILLMD_CPT_ENTITLEMENT_MANIFEST': value})):
                with self.assertRaises(licensing.EntitlementUnavailable):
                    licensing.verified_entitlement()

    def test_separate_private_copies_preserve_proof_and_require_readable_identity(self):
        source_proof = licensing.verified_entitlement()
        other = self.root / 'runtime-copy'
        other.mkdir(mode=0o700)
        for original in self.root.iterdir():
            if original.is_file():
                target = other / original.name
                target.write_bytes(original.read_bytes()); target.chmod(0o600)
        selected = self.configured_manifest({'QUILLMD_CPT_ENTITLEMENT_MANIFEST': str(other / self.path.name)})
        with override_settings(CPT_ENTITLEMENT_MANIFEST=selected):
            self.assertEqual(licensing.verified_entitlement(), source_proof)
            (other / self.path.name).chmod(0o640)
            with self.assertRaises(licensing.EntitlementUnavailable):
                licensing.verified_entitlement()
            (other / self.path.name).chmod(0o600)
            other.chmod(0o750)
            with self.assertRaises(licensing.EntitlementUnavailable):
                licensing.verified_entitlement()
            other.chmod(0o700)
            # Model an unreadable foreign-identity copy without impersonation
            # or chown; this remains valid when the test runner itself is root.
            original_fstat = os.fstat
            def foreign_owner(fd):
                info = original_fstat(fd)
                fields = {key: getattr(info, key) for key in dir(info) if key.startswith('st_')}
                fields['st_uid'] = os.geteuid() + 12345
                return SimpleNamespace(**fields)
            with patch.object(licensing.os, 'fstat', side_effect=foreign_owner):
                with self.assertRaises(licensing.EntitlementUnavailable):
                    licensing.verified_entitlement()
            with patch.object(licensing.os, 'open', side_effect=PermissionError('synthetic unreadable copy')):
                with self.assertRaises(licensing.EntitlementUnavailable):
                    licensing.verified_entitlement()

    def test_exact_documented_scope_qualifies_only_the_supplied_release(self):
        proof = licensing.entitlement_for_release(version=self.release['version'], effective_from=date(2026, 1, 1),
            effective_until=date(2026, 12, 31), source_url=self.release['source_url'], sha256=self.release['sha256'], code_count=2)
        self.assertEqual(proof['manifest']['license_id'], 'SYNTHETIC-test-reference')
        self.assertEqual(proof['rules'], self.rules)
        with self.assertRaises(licensing.EntitlementUnavailable):
            licensing.entitlement_for_release(version='different', effective_from=date(2026, 1, 1),
                effective_until=date(2026, 12, 31), source_url=self.release['source_url'], sha256=self.release['sha256'], code_count=2)

    def test_environment_flags_cannot_replace_missing_manifest(self):
        self.path.unlink()
        status = licensing.cpt_status(date(2026, 10, 14))
        self.assertFalse(status['available'])
        self.assertFalse(status['license_verified'])
        self.assertEqual(status['missing_requirements'], ['protected_entitlement_manifest'])

    def test_current_license_expiry_is_independent_of_historical_service_date(self):
        self.manifest['validity']['until'] = '2026-10-01'
        self.write_manifest()
        status = licensing.cpt_status(date(2026, 9, 1))
        self.assertEqual(status['missing_requirements'], ['current_validity'])

    def test_product_users_distribution_ai_and_review_cannot_be_bare_booleans(self):
        original = deepcopy(self.manifest)
        for key in ('product', 'users', 'distribution', 'intended_ai_use', 'permission_review'):
            with self.subTest(key=key):
                self.manifest = deepcopy(original)
                self.manifest[key] = True
                self.write_manifest(rereview=key != 'permission_review')
                self.assertFalse(licensing.cpt_status()['available'])

    def test_changed_grant_without_reviewer_reapproval_refuses(self):
        self.manifest['users']['terms_reference'] = 'Different scope'
        self.write_manifest(rereview=False)
        with self.assertRaises(licensing.EntitlementUnavailable) as failure:
            licensing.verified_entitlement()
        self.assertEqual(failure.exception.requirement, 'documented_permission_review')

    def test_hash_permissions_links_and_duplicate_json_keys_refuse(self):
        original = self.path.read_bytes()
        self.path.chmod(0o644)
        self.assertFalse(licensing.cpt_status()['available'])
        self.path.chmod(0o600)
        agreement = self.root / 'agreement.txt'
        agreement.write_bytes(b'Changed synthetic contract')
        self.assertFalse(licensing.cpt_status()['available'])
        agreement.unlink()
        agreement.symlink_to(self.path)
        self.assertFalse(licensing.cpt_status()['available'])
        self.path.write_bytes(b'{"format":"x","format":"y"}')
        self.assertFalse(licensing.cpt_status()['available'])
        self.path.write_bytes(original)

    def test_missing_or_unknown_rule_language_never_claims_licensed_readiness(self):
        for change in ('missing', 'unknown', 'threshold'):
            with self.subTest(change=change):
                rules = deepcopy(self.rules)
                if change == 'missing':
                    rules['tabular']['codes'] = {}
                elif change == 'unknown':
                    rules['tabular']['codes']['00000']['requirements']['infer_performance'] = True
                else:
                    rules['tabular']['codes']['00001']['requirements']['time']['minimum'] = True
                self.manifest['rules'] = self.artifact('rules.json', licensing.canonical(rules))
                self.write_manifest()
                self.assertEqual(licensing.cpt_status()['missing_requirements'], ['licensed_rule_criteria'])

    def test_proof_is_not_loaded_release_or_permission_for_a_different_date(self):
        from core.models import CodeSet
        with patch.object(CodeSet.objects, 'filter') as rows:
            rows.return_value.first.return_value = None
            status = licensing.cpt_status(date(2025, 9, 1))
        self.assertFalse(status['available'])
        self.assertTrue(status['license_verified'])
        self.assertFalse(status['dated_release_verified'])

    def test_exact_imported_reference_is_required_after_entitlement(self):
        from core.models import CodeSet, CodingRelease
        release = SimpleNamespace(pk='release', version=self.release['version'], sha256=self.release['sha256'],
            license_reference=self.manifest['license_id'], effective_from=date(2026, 1, 1), effective_until=date(2026, 12, 31), code_set=Mock())
        release.code_set.count.return_value = 2
        proof = licensing.verified_entitlement()
        content = {'index': self.rules['index'], 'tabular': self.rules['tabular']}
        reference = SimpleNamespace(**content, digest=hashlib.sha256(licensing.canonical(content)).hexdigest(),
            provenance={'entitlement_sha256': proof['manifest_sha256'], 'rules_sha256': proof['rules_sha256'],
                        'agreement_sha256': proof['agreement_sha256'], 'permission_review_sha256': proof['permission_review_sha256']})
        with patch.object(CodeSet.objects, 'filter') as rows, patch.object(CodingRelease.objects, 'filter') as refs:
            rows.return_value.first.return_value = release
            refs.return_value.first.return_value = reference
            self.assertTrue(licensing.cpt_status(date(2026, 10, 14))['available'])
            reference.digest = 'f' * 64
            self.assertEqual(licensing.cpt_status()['missing_requirements'], ['licensed_rule_criteria'])

    def test_import_command_requires_manifest_before_reading_feed_or_writing(self):
        from core.management.commands import import_terminology as command
        self.path.unlink()
        db = SimpleNamespace(settings_dict={'NAME': 'test_quillmd_offline'})
        options = dict(system='CPT', path='/not-read', sha256='a' * 64, release_version=self.release['version'],
                       effective_from='2026-01-01', effective_until='2026-12-31', source_url=self.release['source_url'], expected_count=2)
        with patch.object(command, 'connection', db), patch.object(command, 'save_release') as save:
            with self.assertRaises(CommandError):
                command.Command().handle(**options)
            save.assert_not_called()

    def test_import_command_passes_exact_verified_feed_and_rules_to_atomic_writer(self):
        from core.management.commands import import_terminology as command
        lines = ['code,description'] + [code + ',' + row['description'] for code, row in self.rules['tabular']['codes'].items()]
        csv = ('\n'.join(lines) + '\n').encode()
        self.release['sha256'] = hashlib.sha256(csv).hexdigest()
        self.rules['release'] = deepcopy(self.release)
        self.manifest['rules'] = self.artifact('rules.json', licensing.canonical(self.rules))
        self.write_manifest()
        feed = self.root / 'synthetic-feed.csv'
        self.artifact(feed.name, csv)
        db = SimpleNamespace(settings_dict={'NAME': 'test_quillmd_offline'})
        options = dict(system='CPT', path=str(feed), sha256=self.release['sha256'], release_version=self.release['version'],
                       effective_from='2026-01-01', effective_until='2026-12-31', source_url=self.release['source_url'], expected_count=2)
        result = SimpleNamespace(system='CPT', version=self.release['version'], sha256=self.release['sha256'])
        with patch.object(command, 'connection', db), patch.object(licensing, 'save_licensed_release', return_value=(result, True)) as save:
            instance = command.Command()
            instance.stdout = Mock()
            instance.handle(**options)
        rows, metadata, proof = save.call_args.args
        self.assertEqual(rows, {code: row['description'] for code, row in self.rules['tabular']['codes'].items()})
        self.assertEqual(metadata['license_reference'], self.manifest['license_id'])
        self.assertEqual(proof['rules'], self.rules)
