"""Synthetic imports test provenance, completeness, atomicity and licensing gates."""
from datetime import date
from copy import deepcopy
import hashlib

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, TestCase, override_settings

from core.management.commands.import_terminology import parse_cpt, parse_icd, save_release
from core.models import AuditEvent, Code, CodeSet
from core.tests.test_coding_imports import LicensedCptImportFixture


class TerminologyParsingTests(SimpleTestCase):
    def test_icd_preserves_full_description_and_decimal(self):
        self.assertEqual(parse_icd(b'M25532  Synthetic left wrist description\r\n'),
                         {'M25.532': 'Synthetic left wrist description'})

    def test_invalid_utf8_is_not_silently_replaced(self):
        with self.assertRaises(CommandError):
            parse_icd(b'M25532  Synthetic \xff\n')

    def test_current_alphanumeric_category_and_u_codes_are_retained(self):
        self.assertEqual(parse_icd(b'QA00101 Synthetic current category\nU071    Synthetic U category\n'),
                         {'QA0.0101': 'Synthetic current category', 'U07.1': 'Synthetic U category'})

    def test_order_file_and_addenda_are_rejected(self):
        for payload in [b'00001 A00     0 Synthetic heading\n', b'Add: M25532 Synthetic\n']:
            with self.assertRaises(CommandError):
                parse_icd(payload)

    def test_duplicates_and_oversized_descriptions_are_rejected(self):
        for payload in [b'M25532  Synthetic\nM25532  Different\n', b'M25532  ' + b'X' * 501]:
            with self.assertRaises(CommandError):
                parse_icd(payload)

    def test_cpt_csv_does_not_accept_extra_columns_or_hcpcs(self):
        for payload in [b'code,description,unexpected\n99999,Synthetic,extra\n',
                        b'code,description\nJ0000,Synthetic\n']:
            with self.assertRaises(CommandError):
                parse_cpt(payload)


class TerminologyImportTests(LicensedCptImportFixture, TestCase):
    def setUp(self):
        self.set_up_licensed_cpt()

    @override_settings(CPT_LICENSE_ID='', CPT_LICENSE_EXPIRY='', CPT_ENTITLEMENT_MANIFEST='')
    def test_unlicensed_cpt_is_refused_before_any_database_write(self):
        with self.assertRaises(CommandError):
            call_command('import_terminology', **self.args)
        self.assertEqual(CodeSet.objects.count(), 0)
        self.assertEqual(AuditEvent.objects.count(), 0)

    @override_settings(CPT_LICENSE_ID='synthetic-license', CPT_LICENSE_EXPIRY='2020-01-01')
    def test_expired_license_is_refused(self):
        self.manifest['validity']['until'] = '2020-01-01'
        self.write_entitlement()
        with self.assertRaises(CommandError):
            call_command('import_terminology', **self.args)
        self.assertEqual(Code.objects.count(), 0)

    @override_settings(CPT_LICENSE_ID='synthetic-license', CPT_LICENSE_EXPIRY='2099-01-01')
    def test_environment_id_and_expiry_without_owner_documents_cannot_enable_import(self):
        self.entitlement_path.unlink()
        with self.assertRaises(CommandError):
            call_command('import_terminology', **self.args)
        self.assertEqual(CodeSet.objects.count(), 0)
        self.assertEqual(AuditEvent.objects.count(), 0)

    @override_settings(CPT_LICENSE_ID='unrelated-environment-id', CPT_LICENSE_EXPIRY='2099-01-01')
    def test_reimport_is_idempotent_and_unchanged_release_is_verified(self):
        call_command('import_terminology', **self.args)
        call_command('import_terminology', **self.args)
        self.assertEqual(Code.objects.count(), 1)
        self.assertEqual(CodeSet.objects.get().license_reference, 'synthetic-license')
        self.assertEqual(AuditEvent.objects.filter(action='terminology.import').count(), 1)
        self.assertEqual(AuditEvent.objects.get().details['license_expiry'], '2027-12-31')

    @override_settings(CPT_LICENSE_ID='synthetic-license', CPT_LICENSE_EXPIRY='2099-01-01')
    def test_checksum_and_count_mismatch_are_atomic(self):
        original_manifest, original_rules = deepcopy(self.manifest), deepcopy(self.rules)
        for changes in [{'sha256': '0' * 64}, {'expected_count': 2}]:
            # Admit the exact reviewed metadata first, so the feed checks (not
            # an earlier entitlement mismatch) reject the actual bad bytes/count.
            self.manifest, self.rules = deepcopy(original_manifest), deepcopy(original_rules)
            if 'sha256' in changes:
                self.manifest['content_release']['sha256'] = changes['sha256']
            else:
                self.manifest['content_release']['code_count'] = 2
                self.rules['tabular']['codes']['00001'] = deepcopy(self.rules['tabular']['codes']['00000'])
                self.rules['index'].append({'code':'00001','terms':['another synthetic procedure'],
                                            'reference':'SYNTHETIC additional index'})
            self.write_entitlement()
            with self.assertRaises(CommandError):
                call_command('import_terminology', **{**self.args, **changes})
        self.assertEqual(CodeSet.objects.count(), 0)

    @override_settings(CPT_LICENSE_ID='synthetic-license', CPT_LICENSE_EXPIRY='2099-01-01')
    def test_existing_release_cannot_be_rewritten(self):
        call_command('import_terminology', **self.args)
        changed = b'code,description\n00000,Changed synthetic description\n'
        self.path.write_bytes(changed)
        self.manifest['content_release']['sha256'] = hashlib.sha256(changed).hexdigest()
        self.rules['tabular']['codes']['00000']['description'] = 'Changed synthetic description'
        self.write_entitlement()
        with self.assertRaises(CommandError):
            call_command('import_terminology', **{**self.args, 'sha256': hashlib.sha256(changed).hexdigest()})
        self.assertEqual(Code.objects.get().description, 'Synthetic procedure for testing only')

    def test_icd_subset_and_unofficial_source_are_refused(self):
        for changes in [{'expected_count': 1, 'source_url': 'https://www.cms.gov/files/full.txt'},
                        {'expected_count': 74719, 'source_url': 'https://not-cdc.example/full.txt'}]:
            with self.assertRaises(CommandError):
                call_command('import_terminology', **{**self.args, 'system': 'ICD-10-CM', **changes})
        self.assertEqual(CodeSet.objects.count(), 0)

    def test_overlapping_releases_are_refused(self):
        metadata = dict(system='ICD-10-CM', version='synthetic-first',
                        effective_from=date(2026, 4, 1), effective_until=date(2026, 9, 30),
                        source_url='https://www.cms.gov/files/synthetic.txt', sha256='1' * 64,
                        license_reference='')
        save_release({'M25.532': 'Synthetic'}, metadata)
        with self.assertRaises(CommandError):
            save_release({'M25.532': 'Synthetic'}, {**metadata, 'version': 'synthetic-second'})
        self.assertEqual(CodeSet.objects.count(), 1)
