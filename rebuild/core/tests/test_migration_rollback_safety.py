"""Rolling back is never allowed to erase v3 mapping evidence.

MIG-2 (verified MEDIUM): 0021_word_v3_mapping_review reversed with no evidence guard. `migrate core 0020` dropped
core_mappingconfirmation (append-only clinician confirmations) and TemplateVersion.contract/corrections, printing only
'OK'; re-applying recorded every version contract='' and no confirmation. TemplateVersion rows are immutable (a trigger
refuses UPDATE), so nothing can relabel them afterwards: a never-confirmed automatic v3 mapping then read as a legacy
mapping, lost its confirmation gate and produced a finalized export. Like 0020, 0025-0028 and 0030, the reverse must
refuse while that evidence exists (counts only, nothing changed at 0021's node) and still run on a database without it.

No provider, network or real record is involved: every row below is synthetic and made directly.
"""
from django.db import connection
from django.db.migrations.exceptions import IrreversibleError
from django.db.migrations.executor import MigrationExecutor
from django.db.migrations.recorder import MigrationRecorder
from django.test import TransactionTestCase
from django.utils import timezone

from core.models import Department, MappingConfirmation, Organization, Template, TemplateVersion, User

BEFORE_0021 = [('core', '0020_payment_livemode')]
MIGRATION_0021 = ('core', '0021_word_v3_mapping_review')


def to_leaf():
    executor = MigrationExecutor(connection)
    executor.migrate(executor.loader.graph.leaf_nodes())


def v3_fields(*keys):
    return [{'key': key, 'label': key.title(), 'kind': 'text', 'origin': 'automatic',
             'locator': {'contract': 'v3', 'part': 'word/document.xml', 'slot': f'p{i}'}} for i, key in enumerate(keys)]


LEGACY_FIELDS = [{'key': 'symptoms', 'label': 'Symptoms', 'kind': 'text', 'locator': {'cell': 0}}]


class ReversingTheV3MappingReviewMigration(TransactionTestCase):
    """The verifier's MIG-2 input: two contract v3 mappings, A confirmed (one MappingConfirmation row) and B never
    confirmed, beside a legacy mapping; then `migrate core 0020`."""

    def setUp(self):
        self.user = User.objects.create_user(username='mig2', email='mig2@synthetic.invalid', verified_at=timezone.now())
        department = Department.objects.create(organization=Organization.objects.create(name='Synthetic MIG-2'), name='mig2')
        self.templates = [Template.objects.create(department=department, name=f'Synthetic {name}', format='docx',
                                                  original_name='synthetic.docx', original_path=f'originals/{name}.docx',
                                                  sha256=f'{i}' * 64, created_by=self.user)
                          for i, name in enumerate(['A', 'B', 'legacy'])]

    def tearDown(self):
        # Whatever happened above, leave the whole schema in place for the tests that follow.
        to_leaf()
        super().tearDown()

    def version(self, template, fields, **extra):
        return TemplateVersion.objects.create(template=template, number=1, fields=fields, created_by=self.user, **extra)

    @staticmethod
    def evidence():
        """(0021 applied, confirmation table present, its rows, versions recorded 'v3'), read without the ORM: after a
        refusal the database stands at 0021's node, where later columns (0022's assistance) do not exist."""
        with connection.cursor() as cursor:
            cursor.execute("SELECT to_regclass('core_mappingconfirmation') IS NOT NULL")
            table = cursor.fetchone()[0]
            confirmations = versions = None
            if table:
                cursor.execute('SELECT count(*) FROM core_mappingconfirmation')
                confirmations = cursor.fetchone()[0]
                cursor.execute("SELECT count(*) FROM core_templateversion WHERE contract = 'v3'")
                versions = cursor.fetchone()[0]
        return MIGRATION_0021 in MigrationRecorder(connection).applied_migrations(), table, confirmations, versions

    def test_reproduce_MIG2_confirmed_and_unconfirmed_v3_mappings_refuse_the_reverse(self):
        """Reproduce: A confirmed, B unconfirmed, then migrate core 0020. Before the repair this printed 'OK', dropped the
        confirmation and both contracts, and after re-applying B no longer needed confirmation (RED: no refusal)."""
        a = self.version(self.templates[0], v3_fields('pain', 'side'), contract='v3')
        b = self.version(self.templates[1], v3_fields('pain', 'side'), contract='v3')
        self.version(self.templates[2], LEGACY_FIELDS)
        MappingConfirmation.objects.create(version=a, confirmed_by=self.user)
        self.assertTrue(b.needs_confirmation)
        with self.assertRaisesRegex(IrreversibleError, r'1 mapping confirmation\(s\) and 2 mapping version\(s\)') as refused:
            MigrationExecutor(connection).migrate(BEFORE_0021)
        # Counts only: no identifier, name or account reaches the operator's terminal or log.
        for private in (str(a.pk), str(b.pk), str(self.user.pk), self.user.email, 'Synthetic A', 'Synthetic B'):
            self.assertNotIn(private, str(refused.exception))
        # Refused inside 0021's own transaction: the database stands at 0021 with every row and column intact.
        self.assertEqual(self.evidence(), (True, True, 1, 2))
        to_leaf()
        a, b = TemplateVersion.objects.get(pk=a.pk), TemplateVersion.objects.get(pk=b.pk)
        self.assertEqual((a.contract, b.contract), ('v3', 'v3'))
        self.assertIsNotNone(a.confirmed)
        self.assertTrue(b.needs_confirmation)

    def refused(self, message):
        with self.assertRaisesRegex(IrreversibleError, message):
            MigrationExecutor(connection).migrate(BEFORE_0021)
        self.assertTrue(self.evidence()[0])

    def test_an_unconfirmed_v3_mapping_alone_refuses(self):
        self.version(self.templates[1], v3_fields('pain'), contract='v3')
        self.refused(r'0 mapping confirmation\(s\) and 1 mapping version\(s\)')

    def test_recorded_corrections_alone_refuse(self):
        # Corrections are recorded only on v3 versions; a row carrying them would still be erased by the reverse.
        self.version(self.templates[2], LEGACY_FIELDS, corrections={'base_version': 1, 'removed': [], 'added': ['x'],
                                                                    'kind_changed': {}, 'renamed': []})
        self.refused(r'0 mapping confirmation\(s\) and 1 mapping version\(s\)')

    def test_a_confirmation_alone_refuses(self):
        MappingConfirmation.objects.create(version=self.version(self.templates[2], LEGACY_FIELDS), confirmed_by=self.user)
        self.refused(r'1 mapping confirmation\(s\) and 0 mapping version\(s\)')

    def test_a_database_without_v3_evidence_still_reverses_and_reapplies(self):
        """Positive control: only legacy mappings (contract '', no corrections, no confirmation) lose nothing, so the
        reverse runs and re-applying restores the same rows."""
        legacy = self.version(self.templates[2], LEGACY_FIELDS)
        MigrationExecutor(connection).migrate(BEFORE_0021)
        self.assertEqual(self.evidence(), (False, False, None, None))
        to_leaf()
        legacy = TemplateVersion.objects.get(pk=legacy.pk)
        self.assertEqual((legacy.contract, legacy.corrections, legacy.fields), ('', {}, LEGACY_FIELDS))
        self.assertFalse(legacy.needs_confirmation)
