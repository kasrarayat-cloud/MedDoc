"""Reference importers and lookups. Synthetic fixtures in the real CMS layouts; the real files are never needed."""
import hashlib
import io
import json
import tempfile
import zipfile
from datetime import date, datetime, timezone
from pathlib import Path
from unittest import mock

from django.core.management import CommandError, call_command
from django.test import SimpleTestCase, TestCase

from studio.models import ReferenceCodeFact, ReferenceSource
from studio.reference import importers
from studio.reference.importers import (LICENSE_NOTE, ReferenceImportError, import_cms_mue_practitioner,
                                        import_cms_pfs, parse_mue, parse_pfs, source_key)
from studio.reference.store import (UNKNOWN_DATE_NOTE, DbReferenceLookup, InMemoryReferenceLookup,
                                    source_applies)
from studio.types import ReferenceSourceInfo

FIXTURES = Path(__file__).resolve().parent / 'fixtures' / 'reference'
PFS_MEMBER = 'PPRRVU2026_Oct_nonQPP.csv'
MUE_MEMBER = 'MCR_MUE_PractitionerServices_Eff_10-01-2026.csv'
PFS_URL = 'https://www.cms.gov/files/zip/rvu26d-updated-08-26-2026.zip'
MUE_URL = 'https://www.cms.gov/files/zip/medicare-ncci-2026-q4-practitioner-services-mue-table.zip'
RETRIEVED = datetime(2026, 10, 23, 20, 59, tzinfo=timezone.utc)
Q4 = {'effective_start': date(2026, 10, 1), 'effective_end': date(2026, 12, 31)}
PFS_FACT_KEYS = {'status', 'global_days', 'mult_proc', 'endo_base', 'pctc'}


def fixture(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def edited(name: str, old: str, new: str, encoding='iso-8859-1') -> bytes:
    text = fixture(name).decode(encoding)
    assert text.count(old) == 1, f'{old!r} must occur once in {name}'
    return text.replace(old, new).encode(encoding)


def zip_bytes(members: dict) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, data in members.items():
            archive.writestr(zipfile.ZipInfo(name, date_time=(2026, 10, 1, 0, 0, 0)), data)
    return buffer.getvalue()


def pfs_members(csv_bytes=None) -> dict:
    # Decoys mirror the real archive: the QPP table and the PDF must not be read.
    return {PFS_MEMBER: csv_bytes if csv_bytes is not None else fixture(PFS_MEMBER),
            'PPRRVU2026_Oct_QPP.csv': b'not,this,one\r\n', 'RVU26D.pdf': b'%PDF-1.4 synthetic'}


def mue_members(csv_bytes=None) -> dict:
    return {MUE_MEMBER: csv_bytes if csv_bytes is not None else fixture(MUE_MEMBER),
            MUE_MEMBER.replace('.csv', '.xlsx'): b'PK synthetic workbook'}


class ArchiveMixin:
    def setUp(self):
        super().setUp()
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.tmp = Path(directory.name)

    def archive(self, members: dict, name='reference.zip') -> tuple[Path, str]:
        data = zip_bytes(members)
        path = self.tmp / name
        path.write_bytes(data)
        return path, hashlib.sha256(data).hexdigest()

    def load_pfs(self, members=None, *, name='rvu.zip', **overrides):
        path, sha = self.archive(members or pfs_members(), name)
        kwargs = {'expected_sha256': sha, 'release': 'RVU26D', 'url': PFS_URL, 'retrieved_at': RETRIEVED, **Q4}
        kwargs.update(overrides)
        return import_cms_pfs(path, **kwargs)

    def load_mue(self, members=None, *, name='mue.zip', **overrides):
        path, sha = self.archive(members or mue_members(), name)
        kwargs = {'expected_sha256': sha, 'release': '2026-Q4', 'url': MUE_URL, 'retrieved_at': RETRIEVED, **Q4}
        kwargs.update(overrides)
        return import_cms_mue_practitioner(path, **kwargs)


class ParserTests(SimpleTestCase):
    def test_pfs_parser_reads_the_composite_header_and_drops_descriptors(self):
        table = parse_pfs(zip_bytes(pfs_members()), date(2026, 10, 1))
        self.assertEqual(table.member, PFS_MEMBER)
        rows = {(code, modifier): facts for code, modifier, facts in table.rows}
        self.assertEqual(len(rows), 15)
        self.assertEqual(rows[('43239', '')], {'status': 'A', 'global_days': '000', 'mult_proc': '3',
                                               'endo_base': '43235', 'pctc': '0'})
        self.assertEqual(rows[('43235', '')]['endo_base'], None)
        self.assertIn(('45378', '53'), rows)
        self.assertIn(('74328', 'TC'), rows)
        self.assertTrue(all(set(facts) == PFS_FACT_KEYS for facts in rows.values()))
        self.assertNotIn('SYNTHETIC DESCRIPTOR', json.dumps(table.rows))

    def test_mue_parser_reads_iso_8859_1_and_splits_the_indicator(self):
        table = parse_mue(zip_bytes(mue_members()), date(2026, 10, 1))
        rows = {code: facts for code, _, facts in table.rows}
        self.assertEqual(rows['43239'], {'value': 1, 'mai': {'indicator': 2, 'label': 'Date of Service Edit: Policy'},
                                         'rationale': 'Anatomic Consideration'})
        self.assertEqual(rows['99213']['value'], 2)
        self.assertEqual(rows['J9999']['mai'], {'indicator': 1, 'label': 'Line Edit'})
        self.assertTrue(all(modifier == '' for _, modifier, _ in table.rows))

    def test_pfs_member_month_must_match_the_declared_start(self):
        with self.assertRaisesRegex(ReferenceImportError, 'is the Oct 2026 release'):
            parse_pfs(zip_bytes(pfs_members()), date(2026, 7, 1))

    def test_mue_member_date_must_equal_the_declared_start(self):
        with self.assertRaisesRegex(ReferenceImportError, 'is effective 2026-10-01'):
            parse_mue(zip_bytes(mue_members()), date(2026, 10, 2))

    def test_exactly_one_matching_member_is_required(self):
        with self.assertRaisesRegex(ReferenceImportError, 'found none'):
            parse_pfs(zip_bytes({'RVU26D.pdf': b'%PDF'}), date(2026, 10, 1))
        both = dict(pfs_members(), **{'PPRRVU2026_OCT_NONQPP.csv': fixture(PFS_MEMBER)})
        with self.assertRaisesRegex(ReferenceImportError, 'Expected exactly one'):
            parse_pfs(zip_bytes(both), date(2026, 10, 1))

    def test_not_a_zip_is_refused(self):
        with self.assertRaisesRegex(ReferenceImportError, 'Not a valid zip archive'):
            parse_pfs(b'plain bytes', date(2026, 10, 1))

    def test_oversized_member_is_refused(self):
        with mock.patch.object(importers, 'MAX_MEMBER_BYTES', 100):
            with self.assertRaisesRegex(ReferenceImportError, 'larger than 100 bytes'):
                parse_pfs(zip_bytes(pfs_members()), date(2026, 10, 1))

    def test_any_malformed_pfs_row_refuses_the_whole_table(self):
        cases = {
            'global days': ('43239,,SYNTHETIC DESCRIPTOR 3,A,,1.00,2.00,,1.00,,0.10,3.10,2.10,0,000,',
                            '43239,,SYNTHETIC DESCRIPTOR 3,A,,1.00,2.00,,1.00,,0.10,3.10,2.10,0,0-0,',
                            'GLOB DAYS value'),
            'code': ('43239,,SYNTHETIC DESCRIPTOR 3', '4323,,SYNTHETIC DESCRIPTOR 3', "code '4323'"),
            'modifier': ('45378,53,', '45378,5,', "modifier '5'"),
            'duplicate': ('43249,,SYNTHETIC', '43239,,SYNTHETIC', 'appears twice'),
            'endoscopic base': (',43235,33.4009', ',4323X1,33.4009', 'ENDO BASE value'),
            'cell count': ('99214,,SYNTHETIC DESCRIPTOR 14,', '99214,,SYNTHETIC DESCRIPTOR 14,,',
                           'cells where the header'),
        }
        for label, (old, new, message) in cases.items():
            with self.subTest(label):
                text = fixture(PFS_MEMBER).decode('ascii')
                self.assertGreaterEqual(text.count(old), 1)
                bad = text.replace(old, new, 1).encode('ascii')
                with self.assertRaisesRegex(ReferenceImportError, message):
                    parse_pfs(zip_bytes(pfs_members(bad)), date(2026, 10, 1))

    def test_a_changed_header_layout_is_refused_by_name(self):
        bad = edited(PFS_MEMBER, ',ENDO,', ',ENDOSCOPIC,')
        with self.assertRaisesRegex(ReferenceImportError, "expected one column 'ENDO BASE', found 0"):
            parse_pfs(zip_bytes(pfs_members(bad)), date(2026, 10, 1))
        no_header = edited(PFS_MEMBER, 'HCPCS,MOD,', 'CODE,MODIFIER,')
        with self.assertRaisesRegex(ReferenceImportError, 'no two-row header block'):
            parse_pfs(zip_bytes(pfs_members(no_header)), date(2026, 10, 1))

    def test_any_malformed_mue_row_refuses_the_whole_table(self):
        cases = {
            'value': ('43239,1,2 Date', '43239,one,2 Date', "MUE value 'one'"),
            'indicator': ('43239,1,2 Date of Service Edit: Policy', '43239,1,Date of Service Edit: Policy',
                          'adjudication indicator'),
            'indicator digit': ('43239,1,2 Date of Service Edit: Policy', '43239,1,4 Date of Service Edit: Policy',
                                'adjudication indicator'),
            'label conflict': ('45380,1,2 Date of Service Edit: Policy', '45380,1,2 Date of Service Edit: Other',
                               'indicator 2 is labelled'),
            'duplicate': ('43249,1,', '43239,1,', 'appears twice'),
        }
        for label, (old, new, message) in cases.items():
            with self.subTest(label):
                bad = edited(MUE_MEMBER, old, new)
                with self.assertRaisesRegex(ReferenceImportError, message):
                    parse_mue(zip_bytes(mue_members(bad)), date(2026, 10, 1))


class ImporterTests(ArchiveMixin, TestCase):
    def test_pfs_import_records_provenance_and_code_keyed_facts(self):
        source = self.load_pfs()
        self.assertEqual(source.key, 'cms-pfs-rvu26d')
        self.assertEqual((source.kind, source.release, source.url), ('cms-pfs', 'RVU26D', PFS_URL))
        self.assertEqual((source.effective_start, source.effective_end), (date(2026, 10, 1), date(2026, 12, 31)))
        self.assertEqual(source.retrieved_at, RETRIEVED)
        self.assertEqual(source.license_note, LICENSE_NOTE)
        self.assertEqual(source.scope_note,
                         'Medicare Physician Fee Schedule indicators (not a CPT edition; not payer-specific)')
        self.assertIn(PFS_MEMBER, source.title)
        self.assertEqual(source.row_count, 15)
        self.assertEqual(source.facts.count(), 15)
        fact = ReferenceCodeFact.objects.get(source=source, code='45385', modifier='')
        self.assertEqual(fact.facts, {'status': 'A', 'global_days': '000', 'mult_proc': '3', 'endo_base': '45378',
                                      'pctc': '0'})
        stored = json.dumps(list(ReferenceCodeFact.objects.values_list('facts', flat=True)))
        self.assertNotIn('DESCRIPTOR', stored)
        self.assertNotIn('DESCRIPTOR', json.dumps([source.title, source.scope_note, source.license_note]))

    def test_mue_import_records_scope_and_values(self):
        source = self.load_mue()
        self.assertEqual(source.key, 'cms-mue-practitioner-2026q4')
        self.assertEqual(source.scope_note, 'Medicare NCCI practitioner MUE values (units per day; not every payer)')
        self.assertEqual(source.row_count, 11)
        fact = ReferenceCodeFact.objects.get(source=source, code='45385')
        self.assertEqual(fact.facts['mai'], {'indicator': 2, 'label': 'Date of Service Edit: Policy'})

    def test_sha_mismatch_is_refused_before_the_archive_is_parsed(self):
        path, _ = self.archive(pfs_members())
        with mock.patch.object(importers, 'parse_pfs') as parser:
            with self.assertRaisesRegex(ReferenceImportError, 'not the expected'):
                import_cms_pfs(path, expected_sha256='0' * 64, release='RVU26D', url=PFS_URL,
                               retrieved_at=RETRIEVED, **Q4)
        parser.assert_not_called()
        self.assertFalse(ReferenceSource.objects.exists())

    def test_reimporting_the_same_file_is_a_no_op(self):
        first = self.load_pfs()
        second = self.load_pfs(retrieved_at=datetime(2026, 10, 24, tzinfo=timezone.utc))
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(ReferenceSource.objects.count(), 1)
        self.assertEqual(ReferenceCodeFact.objects.count(), 15)

    def test_a_different_file_under_a_loaded_release_is_refused(self):
        self.load_pfs()
        changed = edited(PFS_MEMBER, 'SYNTHETIC DESCRIPTOR 1,', 'SYNTHETIC DESCRIPTOR ONE,')
        with self.assertRaisesRegex(ReferenceImportError, 'already loaded from a different file'):
            self.load_pfs(pfs_members(changed), name='rvu-changed.zip')
        self.assertEqual(ReferenceCodeFact.objects.count(), 15)

    def test_the_same_file_with_different_metadata_is_refused(self):
        self.load_pfs()
        with self.assertRaisesRegex(ReferenceImportError, 'different metadata: url'):
            self.load_pfs(url='https://example.org/other.zip')
        with self.assertRaisesRegex(ReferenceImportError, 'effective_end'):
            self.load_pfs(effective_end=date(2026, 12, 30))

    def test_the_same_file_under_another_release_is_refused(self):
        self.load_pfs()
        with self.assertRaisesRegex(ReferenceImportError, 'already loaded as cms-pfs-rvu26d'):
            self.load_pfs(release='RVU26D-copy')

    def test_overlapping_windows_of_one_kind_are_refused(self):
        self.load_pfs()
        changed = edited(PFS_MEMBER, 'SYNTHETIC DESCRIPTOR 1,', 'SYNTHETIC DESCRIPTOR ONE,')
        with self.assertRaisesRegex(ReferenceImportError, 'two sources of one kind may not cover the same date'):
            self.load_pfs(pfs_members(changed), name='rvu-e.zip', release='RVU26E', effective_end=date(2027, 3, 31))
        self.assertEqual(ReferenceSource.objects.count(), 1)

    def test_a_malformed_table_writes_nothing(self):
        bad = edited(PFS_MEMBER, '99214,,SYNTHETIC DESCRIPTOR 14,A', '99214,,SYNTHETIC DESCRIPTOR 14,ab')
        with self.assertRaises(ReferenceImportError):
            self.load_pfs(pfs_members(bad))
        self.assertFalse(ReferenceSource.objects.exists())
        self.assertFalse(ReferenceCodeFact.objects.exists())

    def test_declared_metadata_is_validated(self):
        cases = {
            'sha256': ({'expected_sha256': 'abc'}, '64 hexadecimal'),
            'url scheme': ({'url': 'http://www.cms.gov/x.zip'}, 'https://'),
            'window order': ({'effective_start': date(2027, 1, 1)}, 'after the effective end'),
            'naive retrieval time': ({'retrieved_at': datetime(2026, 10, 23, 20, 59)}, 'timezone-aware'),
            'datetime as date': ({'effective_end': datetime(2026, 12, 31, tzinfo=timezone.utc)}, 'must be a date'),
            'release': ({'release': 'RVU 26D'}, 'Release'),
        }
        path, sha = self.archive(pfs_members())
        for label, (override, message) in cases.items():
            with self.subTest(label):
                kwargs = {'expected_sha256': sha, 'release': 'RVU26D', 'url': PFS_URL, 'retrieved_at': RETRIEVED,
                          **Q4, **override}
                with self.assertRaisesRegex(ReferenceImportError, message):
                    import_cms_pfs(path, **kwargs)
        self.assertFalse(ReferenceSource.objects.exists())

    def test_missing_file_is_refused(self):
        with self.assertRaisesRegex(ReferenceImportError, 'not a readable file'):
            import_cms_pfs(self.tmp / 'absent.zip', expected_sha256='a' * 64, release='RVU26D', url=PFS_URL,
                           retrieved_at=RETRIEVED, **Q4)

    def test_source_keys_are_derived_from_kind_and_release(self):
        self.assertEqual(source_key('cms-pfs', 'RVU26D'), 'cms-pfs-rvu26d')
        self.assertEqual(source_key('cms-mue-practitioner', '2026-Q4'), 'cms-mue-practitioner-2026q4')


class ImportCommandTests(ArchiveMixin, TestCase):
    def run_command(self, path, sha, **extra):
        out = io.StringIO()
        args = {'kind': 'cms-pfs', 'zip_path': str(path), 'expected_sha256': sha, 'release': 'RVU26D', 'url': PFS_URL,
                'effective_start': '2026-10-01', 'effective_end': '2026-12-31',
                'retrieved_at': '2026-10-23T20:59:00Z', **extra}
        argv = [item for key, value in args.items() for item in (f'--{key.replace("_", "-")}', value)]
        argv[argv.index('--zip-path')] = '--zip'
        call_command('import_reference', *argv, stdout=out)
        return out.getvalue()

    def test_command_loads_once_then_reports_no_change(self):
        path, sha = self.archive(pfs_members())
        self.assertIn('Loaded cms-pfs-rvu26d: 15 rows', self.run_command(path, sha))
        self.assertIn('already loaded from this file', self.run_command(path, sha))
        self.assertEqual(ReferenceCodeFact.objects.count(), 15)

    def test_command_reports_refusals_as_command_errors(self):
        path, _ = self.archive(pfs_members())
        with self.assertRaisesRegex(CommandError, 'not the expected'):
            self.run_command(path, 'f' * 64)
        with self.assertRaisesRegex(CommandError, 'no UTC offset'):
            self.run_command(path, 'f' * 64, retrieved_at='2026-10-23T20:59:00')
        with self.assertRaises(CommandError):
            self.run_command(path, 'f' * 64, effective_start='01/10/2026')
        self.assertFalse(ReferenceSource.objects.exists())


class DbLookupTests(ArchiveMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.pfs = self.load_pfs()
        self.mue = self.load_mue()

    def test_a_covered_date_returns_both_sources_facts(self):
        ref = DbReferenceLookup().lookup('45378', date(2026, 10, 21))
        self.assertEqual(ref.applicable_sources, ('cms-pfs-rvu26d', 'cms-mue-practitioner-2026q4'))
        self.assertEqual(ref.pfs['status'], 'A')
        self.assertEqual(ref.pfs['modifier_rows'], ['53'])
        self.assertEqual(ref.pfs['source_key'], 'cms-pfs-rvu26d')
        self.assertEqual(ref.mue['value'], 1)
        self.assertEqual(ref.mue['source_key'], 'cms-mue-practitioner-2026q4')
        self.assertEqual(ref.notes, ())

    def test_window_boundaries_are_inclusive(self):
        lookup = DbReferenceLookup()
        for day, applies in ((date(2026, 9, 30), False), (date(2026, 10, 1), True), (date(2026, 12, 31), True),
                             (date(2027, 1, 1), False)):
            with self.subTest(day=day):
                ref = lookup.lookup('43239', day)
                self.assertEqual(ref.pfs is not None, applies)
                self.assertEqual(ref.mue is not None, applies)
                if not applies:
                    self.assertIn(f'43239: no installed CMS Physician Fee Schedule source covers {day.isoformat()}.',
                                  ref.notes)

    def test_an_unknown_date_applies_no_source(self):
        ref = DbReferenceLookup().lookup('43239', None)
        self.assertEqual((ref.pfs, ref.mue, ref.applicable_sources), (None, None, ()))
        self.assertEqual(ref.notes, (UNKNOWN_DATE_NOTE,))

    def test_absent_and_modifier_only_codes_are_noted(self):
        lookup = DbReferenceLookup()
        absent = lookup.lookup('45999', date(2026, 10, 21))
        self.assertIsNone(absent.pfs)
        self.assertIn('45999 is not listed in RVU26D.', absent.notes)
        self.assertIn('45999 is not listed in 2026-Q4.', absent.notes)
        modifier_only = lookup.lookup('86153', date(2026, 10, 21))
        self.assertIsNone(modifier_only.pfs)
        self.assertIn('86153 is listed in RVU26D only with modifier(s) 26; it has no unmodified row.',
                      modifier_only.notes)

    def test_two_sources_of_one_kind_covering_a_date_are_not_used(self):
        other = ReferenceSource.objects.create(
            key='cms-pfs-overlap', kind='cms-pfs', publisher='CMS', title='Overlapping synthetic', release='RVU26X',
            url=PFS_URL, sha256='b' * 64, retrieved_at=RETRIEVED, effective_start=date(2026, 12, 1),
            effective_end=date(2027, 2, 28), license_note=LICENSE_NOTE, scope_note='x', row_count=1)
        ReferenceCodeFact.objects.create(source=other, code='43239', facts={'status': 'X'})
        lookup = DbReferenceLookup()
        inside = lookup.lookup('43239', date(2026, 12, 15))
        self.assertIsNone(inside.pfs)
        self.assertNotIn('cms-pfs-rvu26d', inside.applicable_sources)
        self.assertTrue(any('ambiguous' in note for note in inside.notes))
        self.assertEqual(lookup.lookup('43239', date(2027, 1, 15)).pfs['status'], 'X')
        self.assertEqual(lookup.lookup('43239', date(2026, 10, 21)).pfs['status'], 'A')

    def test_sources_are_a_snapshot_with_iso_dates(self):
        lookup = DbReferenceLookup()
        keys = [s.key for s in lookup.sources()]
        self.assertEqual(keys, ['cms-mue-practitioner-2026q4', 'cms-pfs-rvu26d'])
        self.assertEqual(lookup.sources()[1].effective_start, '2026-10-01')
        ReferenceSource.objects.create(
            key='cms-pfs-later', kind='cms-pfs', publisher='CMS', title='Later synthetic', release='RVU27A',
            url=PFS_URL, sha256='c' * 64, retrieved_at=RETRIEVED, effective_start=date(2027, 1, 1),
            effective_end=date(2027, 3, 31), license_note=LICENSE_NOTE, scope_note='x')
        self.assertEqual(len(lookup.sources()), 2)


def info(key, kind, start='2026-10-01', end='2026-12-31', release='R1'):
    return ReferenceSourceInfo(key=key, kind=kind, publisher='CMS', title=key, release=release, url='https://x',
                               sha256='0' * 64, effective_start=start, effective_end=end, license_note='',
                               scope_note='')


class InMemoryLookupTests(SimpleTestCase):
    def test_in_memory_lookup_matches_the_database_semantics(self):
        lookup = InMemoryReferenceLookup(
            [info('pfs', 'cms-pfs', release='RVU26D'), info('mue', 'cms-mue-practitioner', release='2026-Q4')],
            {'pfs': {('45378', ''): {'status': 'A', 'endo_base': None}, ('45378', '53'): {'status': 'A'}},
             'mue': {('45378', ''): {'value': 1}}})
        ref = lookup.lookup('45378', date(2026, 11, 2))
        self.assertEqual(ref.pfs, {'status': 'A', 'endo_base': None, 'source_key': 'pfs', 'modifier_rows': ['53']})
        self.assertEqual(ref.mue, {'value': 1, 'source_key': 'mue'})
        self.assertEqual(lookup.lookup('45378', None).notes, (UNKNOWN_DATE_NOTE,))
        self.assertIsNone(lookup.lookup('45378', date(2027, 1, 1)).pfs)

    def test_facts_for_unlisted_sources_are_refused(self):
        with self.assertRaisesRegex(ValueError, 'not listed'):
            InMemoryReferenceLookup([info('pfs', 'cms-pfs')], {'other': {}})

    def test_source_applies_needs_a_date(self):
        source = info('pfs', 'cms-pfs')
        self.assertFalse(source_applies(source, None))
        self.assertTrue(source_applies(source, date(2026, 10, 1)))
