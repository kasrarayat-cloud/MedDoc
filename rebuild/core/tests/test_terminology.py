"""Synthetic imports test provenance, completeness, atomicity and licensing gates."""
from datetime import date
import hashlib
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from unittest.mock import patch
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, TestCase, override_settings

from core.management.commands.import_terminology import parse_cpt, parse_icd, save_release
from core.models import AuditEvent, Code, CodeSet


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


class TerminologyImportTests(TestCase):
    def setUp(self):
        # These tests exercise the environment licence gate of a CPT import. The product-use lock in code
        # (core.coding.CPT_PRODUCT_USE_RIGHTS, None in this release) is lifted here with synthetic rights so that gate is
        # what refuses or admits; core.tests.test_coding_ledger proves the lock itself refuses every import.
        rights = patch('core.coding.CPT_PRODUCT_USE_RIGHTS', {'synthetic': 'product-use rights for tests only'})
        rights.start(); self.addCleanup(rights.stop)
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'licensed-synthetic.csv'
        self.payload = b'code,description\n99999,Synthetic procedure for testing only\n'
        self.path.write_bytes(self.payload)
        self.args = dict(system='CPT', path=str(self.path), sha256=hashlib.sha256(self.payload).hexdigest(),
                         release_version='synthetic-test', effective_from='2026-01-01', effective_until='2099-01-01',
                         source_url='https://example.com/licensed-feed', expected_count=1, stdout=StringIO())

    @override_settings(CPT_LICENSE_ID='', CPT_LICENSE_EXPIRY='')
    def test_unlicensed_cpt_is_refused_before_any_database_write(self):
        with self.assertRaises(CommandError):
            call_command('import_terminology', **self.args)
        self.assertEqual(CodeSet.objects.count(), 0)
        self.assertEqual(AuditEvent.objects.count(), 0)

    @override_settings(CPT_LICENSE_ID='synthetic-license', CPT_LICENSE_EXPIRY='2020-01-01')
    def test_expired_license_is_refused(self):
        with self.assertRaises(CommandError):
            call_command('import_terminology', **self.args)
        self.assertEqual(Code.objects.count(), 0)

    @override_settings(CPT_LICENSE_ID='synthetic-license', CPT_LICENSE_EXPIRY='2099-01-01')
    def test_reimport_is_idempotent_and_unchanged_release_is_verified(self):
        call_command('import_terminology', **self.args)
        call_command('import_terminology', **self.args)
        self.assertEqual(Code.objects.count(), 1)
        self.assertEqual(CodeSet.objects.get().license_reference, 'synthetic-license')
        self.assertEqual(AuditEvent.objects.filter(action='terminology.import').count(), 1)
        self.assertEqual(AuditEvent.objects.get().details['license_expiry'], '2099-01-01')

    @override_settings(CPT_LICENSE_ID='synthetic-license', CPT_LICENSE_EXPIRY='2099-01-01')
    def test_checksum_and_count_mismatch_are_atomic(self):
        for changes in [{'sha256': '0' * 64}, {'expected_count': 2}]:
            with self.assertRaises(CommandError):
                call_command('import_terminology', **{**self.args, **changes})
        self.assertEqual(CodeSet.objects.count(), 0)

    @override_settings(CPT_LICENSE_ID='synthetic-license', CPT_LICENSE_EXPIRY='2099-01-01')
    def test_existing_release_cannot_be_rewritten(self):
        call_command('import_terminology', **self.args)
        changed = b'code,description\n99999,Changed synthetic description\n'
        self.path.write_bytes(changed)
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
