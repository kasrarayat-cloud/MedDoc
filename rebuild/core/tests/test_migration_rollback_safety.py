"""Rolling back: the previous release keeps working on this schema, and no down-migration erases v3 mapping evidence.

MIG-1 (verified; it decides the production rollback plan): the cutover plan allows a code rollback to a release whose
migrations are a prefix of those applied. The installed release dedac162 applies core 0001-0018, byte-identical here,
but on this schema its template upload and mapping edit raised IntegrityError: 0021/0022 added
TemplateVersion.contract, corrections and assistance NOT NULL with no database default, and the release's INSERT omits
them. The historical models at 0018 are exactly what that release's ORM writes, so they reproduce it here. A release
write must either work or be refused; it may never record a v3-located mapping as a legacy one, which is MIG-2's harm
reached without any down-migration.

MIG-2 (verified MEDIUM): 0021_word_v3_mapping_review reversed with no evidence guard. `migrate core 0020` dropped
core_mappingconfirmation (append-only clinician confirmations) and TemplateVersion.contract/corrections, printing only
'OK'; re-applying recorded every version contract='' and no confirmation. TemplateVersion rows are immutable (a trigger
refuses UPDATE), so nothing can relabel them afterwards: a never-confirmed automatic v3 mapping then read as a legacy
mapping, lost its confirmation gate and produced a finalized export. Like 0020, 0025-0028 and 0030, the reverse must
refuse while that evidence exists (counts only, nothing changed at 0021's node) and still run on a database without it.

No provider, network or real record is involved: every row below is synthetic and made directly.
"""
from django.core.management import call_command
from django.db import DatabaseError, IntegrityError, connection, transaction
from django.db.migrations.exceptions import IrreversibleError
from django.db.migrations.executor import MigrationExecutor
from django.db.migrations.loader import MigrationLoader
from django.db.migrations.recorder import MigrationRecorder
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone

from core.models import Department, Encounter, MappingConfirmation, Organization, Patient, Template, TemplateVersion, User
from core.security import private_path

from .test_word_v3_workflow import V3, V3EncounterFixture, V3Fixture

BEFORE_0021 = [('core', '0020_payment_livemode')]
#: The installed private-beta release (dedac162) applies core 0001-0018; every later migration is this candidate's.
PREVIOUS_RELEASE = ('core', '0018_servicehealth')
MIGRATION_0021 = ('core', '0021_word_v3_mapping_review')
BEFORE_0031 = ('core', '0030_empty_draft_disposition')
GATE = 'An unconfirmed contract v3 mapping cannot start a document'
HOLD = 'A document on an unconfirmed contract v3 mapping cannot be finalized'


def to_leaf():
    executor = MigrationExecutor(connection)
    executor.migrate(executor.loader.graph.leaf_nodes())


def applied():
    return {key for key in MigrationRecorder(connection).applied_migrations() if key[0] == 'core'}


def gate_installed():
    """Whether quillmd_encounter_guard, as it stands in the database now, holds 0031's confirmation gate."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT prosrc FROM pg_proc WHERE proname = 'quillmd_encounter_guard'")
        return GATE in cursor.fetchone()[0]


def release_encounter(version, patient, user):
    """The INSERT dedac162's encounter_new makes (its model at 0018): it knows no contract and no confirmation."""
    encounter = MigrationLoader(connection).project_state(PREVIOUS_RELEASE).apps.get_model('core', 'Encounter')
    return encounter.objects.create(department_id=patient.department_id, patient_id=patient.pk, template_version_id=version.pk,
                                    created_by_id=user.pk, notes='Pain: yes.', service_date=timezone.localdate(), answers={})


def v3_fields(*keys):
    return [{'key': key, 'label': key.title(), 'kind': 'text', 'origin': 'automatic',
             'locator': {'contract': 'v3', 'part': 'word/document.xml', 'slot': f'p{i}'}} for i, key in enumerate(keys)]


LEGACY_FIELDS = [{'key': 'symptoms', 'label': 'Symptoms', 'kind': 'text', 'locator': {'cell': 0}}]


class ReversingTheV3MappingReviewMigration(TransactionTestCase):
    """The verifier's MIG-2 input: two contract v3 mappings, A confirmed (one MappingConfirmation row) and B never
    confirmed, beside a legacy mapping; then `migrate core 0020`.

    Since R1, 0031 refuses the same evidence first, at the leaf, with nothing reversed (next class). To exercise 0021's
    own guard, each evidence test first reverses 0031 while no evidence exists and writes its rows at 0030, as this code
    would there; the reverse then reaches 0021, which must still refuse."""

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
        # The four tests at0030 deliberately reversed later columns. Write with that actual historical model,
        # rather than asking today's ORM to INSERT a column the test just proved does not exist there.
        node = max(applied())
        version = MigrationLoader(connection).project_state(node).apps.get_model('core', 'TemplateVersion')
        return version.objects.create(template_id=template.pk, number=1, fields=fields, created_by_id=self.user.pk, **extra)

    @staticmethod
    def at_0030():
        """Reverse 0031 while no v3 evidence exists (allowed), so the rows written next reach 0021's own guard."""
        MigrationExecutor(connection).migrate([BEFORE_0031])
        assert not gate_installed() and BEFORE_0031 in applied() and ('core', '0031_previous_release_mapping_writes') not in applied()

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
        self.at_0030()
        a = self.version(self.templates[0], v3_fields('pain', 'side'), contract='v3')
        b = self.version(self.templates[1], v3_fields('pain', 'side'), contract='v3')
        self.version(self.templates[2], LEGACY_FIELDS)
        MappingConfirmation.objects.create(version_id=a.pk, confirmed_by=self.user)
        self.assertEqual(b.contract, 'v3')
        self.assertFalse(MappingConfirmation.objects.filter(version_id=b.pk).exists())
        with self.assertRaisesRegex(IrreversibleError, r'1 mapping confirmation\(s\) and 2 mapping version\(s\)') as refused:
            MigrationExecutor(connection).migrate(BEFORE_0021)
        # Counts only: no identifier, name or account reaches the operator's terminal or log.
        for private in (str(a.pk), str(b.pk), str(self.user.pk), self.user.email, 'Synthetic A', 'Synthetic B'):
            self.assertNotIn(private, str(refused.exception))
        # Refused inside 0021's own transaction: the database stands at 0021 with every row and column intact.
        self.assertEqual(self.evidence(), (True, True, 1, 2))
        # And the message says what the executor did before it (R1): every later migration is reversed, and stays so.
        self.assertEqual(max(key[1] for key in applied()), MIGRATION_0021[1])
        self.assertIn('has already been reversed and stays reversed: run migrate forward', str(refused.exception))
        self.assertNotIn('Nothing was changed', str(refused.exception))
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
        self.at_0030()
        self.version(self.templates[1], v3_fields('pain'), contract='v3')
        self.refused(r'0 mapping confirmation\(s\) and 1 mapping version\(s\)')

    def test_recorded_corrections_alone_refuse(self):
        # Corrections are recorded only on v3 versions; a row carrying them would still be erased by the reverse.
        self.at_0030()
        self.version(self.templates[2], LEGACY_FIELDS, corrections={'base_version': 1, 'removed': [], 'added': ['x'],
                                                                    'kind_changed': {}, 'renamed': []})
        self.refused(r'0 mapping confirmation\(s\) and 1 mapping version\(s\)')

    def test_a_confirmation_alone_refuses(self):
        self.at_0030()
        MappingConfirmation.objects.create(version_id=self.version(self.templates[2], LEGACY_FIELDS).pk, confirmed_by=self.user)
        self.refused(r'1 mapping confirmation\(s\) and 0 mapping version\(s\)')

    def test_a_database_without_v3_evidence_still_reverses_and_reapplies(self):
        """Positive control: only legacy mappings (contract '', no corrections, no confirmation) lose nothing, so the
        reverse runs from the leaf (0031's guard included) and re-applying restores the same rows."""
        legacy = self.version(self.templates[2], LEGACY_FIELDS)
        self.assertTrue(gate_installed())
        MigrationExecutor(connection).migrate(BEFORE_0021)
        self.assertEqual(self.evidence(), (False, False, None, None))
        to_leaf()
        legacy = TemplateVersion.objects.get(pk=legacy.pk)
        self.assertEqual((legacy.contract, legacy.corrections, legacy.fields), ('', {}, LEGACY_FIELDS))
        self.assertFalse(legacy.needs_confirmation)


class ThePreviousReleaseWritesOnThisSchema(TestCase):
    """dedac162's writes, made with its own model shapes (the historical models at 0018) against this schema."""

    def setUp(self):
        self.release = MigrationLoader(connection).project_state(PREVIOUS_RELEASE).apps
        self.user = User.objects.create_user(username='mig1', email='mig1@synthetic.invalid', verified_at=timezone.now())
        department = Department.objects.create(organization=Organization.objects.create(name='Synthetic MIG-1'), name='mig1')
        self.template = Template.objects.create(department=department, name='Synthetic MIG-1', format='docx',
                                                original_name='synthetic.docx', original_path='originals/mig1.docx',
                                                sha256='1' * 64, created_by=self.user)

    def release_version(self, fields, number):
        """The INSERT dedac162's template_upload (views.py:216) and mapping edit (views.py:315) make."""
        version = self.release.get_model('core', 'TemplateVersion')
        return version.objects.create(template_id=self.template.pk, number=number, fields=fields, review_requirements=[],
                                      document_backend={}, created_by_id=self.user.pk)

    def test_reproduce_MIG1_the_release_upload_and_mapping_edit_record_legacy_versions(self):
        """Reproduce: the release's upload, then its mapping edit (a new version with a revised label), on this schema.
        RED on bf8f7b78: IntegrityError, null value in column "contract" of relation "core_templateversion"."""
        uploaded = self.release_version(LEGACY_FIELDS, 1)
        edited = self.release_version([{**LEGACY_FIELDS[0], 'label': 'Presenting symptoms'}], 2)
        for row in (uploaded, edited):
            version = TemplateVersion.objects.get(pk=row.pk)
            self.assertEqual((version.contract, version.corrections, version.assistance, version.generation_constraints),
                             ('', {}, {}, None))
            self.assertFalse(version.needs_confirmation)
        self.assertEqual(self.template.versions.count(), 2)

    def test_every_column_added_since_the_release_accepts_its_inserts(self):
        """Expand-then-contract: on every table the release writes, a column it does not know is nullable or has a
        database default. Read from the database itself, so a later migration that adds one without a default fails."""
        offending = []
        with connection.cursor() as cursor:
            for model in self.release.get_models(include_auto_created=True):
                known = {field.column for field in model._meta.local_fields}
                cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_schema = current_schema() "
                               "AND table_name = %s AND is_nullable = 'NO' AND column_default IS NULL",
                               [model._meta.db_table])
                offending += [f'{model._meta.db_table}.{column}' for (column,) in cursor.fetchall() if column not in known]
        self.assertEqual(offending, [])

    def test_a_release_edit_of_a_v3_mapping_is_refused_not_recorded_as_legacy(self):
        """The release knows no contract: its mapping edit of a v3 mapping copies the v3 fields into a new version. Were
        that recorded contract='' (the default), re-installing this code would read an unconfirmed automatic mapping as
        a legacy one with no confirmation gate. The database refuses it by name instead."""
        v3 = TemplateVersion.objects.create(template=self.template, number=1, fields=v3_fields('pain', 'side'),
                                            contract='v3', created_by=self.user)
        with self.assertRaisesMessage(IntegrityError, 'mapping_v3_fields_record_v3_contract'), transaction.atomic():
            self.release_version([{**field, 'label': 'Renamed'} for field in v3.fields], 2)
        with self.assertRaisesMessage(IntegrityError, 'mapping_v3_fields_record_v3_contract'), transaction.atomic():
            # One v3-located field among legacy ones is refused too.
            self.release_version(LEGACY_FIELDS + v3_fields('pain'), 2)
        self.assertEqual(list(self.template.versions.values_list('number', 'contract')), [(1, 'v3')])

    def release_encounter(self, version, patient):
        """The INSERT dedac162's encounter_new makes: it knows no contract and no confirmation."""
        encounter = self.release.get_model('core', 'Encounter')
        return encounter.objects.create(department_id=self.template.department_id, patient_id=patient.pk,
                                        template_version_id=version.pk, created_by_id=self.user.pk, notes='Pain: yes.',
                                        service_date=timezone.localdate(), answers={})

    def test_a_release_document_on_an_unconfirmed_v3_mapping_is_refused(self):
        """Reproduce (rollback path to MIG-2's harm): during an image rollback the release started a draft on a v3
        mapping nobody had confirmed (it has no confirmation gate); after this code was re-installed that draft was
        saved, finalized and exported with the mapping still unconfirmed. Measured end to end: release POST
        /encounters/new/ 302, then this code's save 302, finalize 302, status finalized, export 200. The confirmation
        gate must hold for every writer, so the database refuses the document instead."""
        patient = Patient.objects.create(department=self.template.department, display_name='SYNTHETIC MIG-1',
                                         reference='mig1', created_by=self.user)
        v3 = TemplateVersion.objects.create(template=self.template, number=1, fields=v3_fields('pain'), contract='v3',
                                            created_by=self.user)
        message = 'An unconfirmed contract v3 mapping cannot start a document'
        with self.assertRaisesMessage(DatabaseError, message), transaction.atomic():
            self.release_encounter(v3, patient)
        with self.assertRaisesMessage(DatabaseError, message), transaction.atomic():
            # Any writer: this code's own ORM, bypassing the form's check, is refused the same way.
            Encounter.objects.create(department=self.template.department, patient=patient, template_version=v3,
                                     created_by=self.user, notes='Pain: yes.', service_date=timezone.localdate())
        legacy = TemplateVersion.objects.create(template=self.template, number=2, fields=LEGACY_FIELDS, created_by=self.user)
        draft = self.release_encounter(legacy, patient)
        with self.assertRaisesMessage(DatabaseError, message), transaction.atomic():
            # Nor can an existing document be moved onto it.
            Encounter.objects.filter(pk=draft.pk).update(template_version=v3)
        self.assertEqual(list(Encounter.objects.values_list('template_version__contract', flat=True)), [''])
        # Positive control: once a clinician confirms it, the same release INSERT and a move onto it both work.
        MappingConfirmation.objects.create(version=v3, confirmed_by=self.user)
        self.release_encounter(v3, patient)
        Encounter.objects.filter(pk=draft.pk).update(template_version=v3)
        self.assertEqual(Encounter.objects.filter(template_version=v3).count(), 2)

    def test_this_code_s_own_mapping_versions_are_unaffected(self):
        """Positive control: every shape this code writes (legacy, v3 with its contract, corrections, assistance, a
        tab/PDF/WM mapping with its own locators) still inserts."""
        rows = [dict(fields=LEGACY_FIELDS), dict(fields=[]),
                dict(fields=[{'key': 'q', 'label': 'Q', 'kind': 'text', 'locator': {'tab_form': {'paragraph': 3}}}]),
                dict(fields=[{'key': 'q', 'label': 'Q', 'kind': 'text', 'locator': {'pdf_field': 'Q'}}],
                     document_backend={'adapter': 'synthetic'}),
                dict(fields=v3_fields('pain'), contract='v3'),
                dict(fields=v3_fields('pain', 'side'), contract='v3', assistance={'unresolved': [], 'assisted': True},
                     corrections={'base_version': 5, 'removed': [], 'added': ['side'], 'kind_changed': {}, 'renamed': []})]
        for number, extra in enumerate(rows, start=1):
            TemplateVersion.objects.create(template=self.template, number=number, created_by=self.user, **extra)
        self.assertEqual(self.template.versions.count(), len(rows))


class ARefusedRollbackKeepsTheConfirmationGate(TransactionTestCase):
    """R1 (refuter of the MIG-1/MIG-2 repair): 0021's refusal is atomic for 0021 only. `migrate core 0018` first reversed
    and committed 0022-0031, then 0021 refused saying 'Nothing was changed.'; 0031's confirmation gate was gone, the
    previous release started a draft on a never-confirmed v3 mapping, re-applying 0031 did not look at that draft, and
    this code saved it to review and finalized it. No step toward the previous release's schema may drop the gate while
    v3 mapping evidence exists, and a document on an unconfirmed v3 mapping is never finalized, however it was started."""

    def setUp(self):
        self.user = User.objects.create_user(username='r1', email='r1@synthetic.invalid', verified_at=timezone.now())
        department = Department.objects.create(organization=Organization.objects.create(name='Synthetic R1'), name='r1')
        self.template = Template.objects.create(department=department, name='Synthetic R1', format='docx',
                                                original_name='synthetic.docx', original_path='originals/r1.docx',
                                                sha256='1' * 64, created_by=self.user)
        self.patient = Patient.objects.create(department=department, display_name='SYNTHETIC R1', reference='r1',
                                              created_by=self.user)

    def tearDown(self):
        to_leaf()
        super().tearDown()

    def v3(self, number=1):
        return TemplateVersion.objects.create(template=self.template, number=number, fields=v3_fields('pain'),
                                              contract='v3', created_by=self.user)

    def assert_refused_with_nothing_reversed(self, migrate, counts):
        before = applied()
        with self.assertRaisesRegex(IrreversibleError, counts) as refused:
            migrate()
        for private in (str(self.user.pk), self.user.email, 'Synthetic R1', str(self.template.pk)):
            self.assertNotIn(private, str(refused.exception))
        self.assertEqual(applied(), before)
        self.assertTrue(gate_installed())
        return str(refused.exception)

    def test_reproduce_R1_a_rollback_toward_the_previous_release_refuses_before_dropping_the_gate(self):
        """Reproduce, the refuter's input: one contract v3 mapping that no clinician has confirmed, at the leaf; then
        MigrationExecutor.migrate([0018]), which is what `migrate core 0018` runs. RED on cb240141: 0021 refused only
        after 0022-0031 had been reversed and committed, and the gate was gone (0031 no longer applied)."""
        unconfirmed = self.v3()
        message = self.assert_refused_with_nothing_reversed(
            lambda: MigrationExecutor(connection).migrate([PREVIOUS_RELEASE]),
            r'0 mapping confirmation\(s\) and 1 mapping version\(s\)')
        self.assertNotIn('Nothing was changed', message)
        self.assertIn('0031_previous_release_mapping_writes cannot be reversed', message)
        # MIG-R-2: `migrate core zero` unapplies otp_totp (it depends on core 0001) before 0031 is reached; the message
        # names that and the supported target, so an operator reading a refusal after `zero` knows MFA was dropped.
        self.assertIn('zero also unapplies otp_totp before 0031, which drops every TOTP enrollment', message)
        self.assertIn('the supported rollback target is core 0018', message)
        # Since 0032 the refusal comes from the leaf, before anything is reversed, and says so.
        self.assertIn('neither 0032 nor 0031 was reversed', message)
        # The previous release's draft on that mapping is refused exactly as at the leaf.
        with self.assertRaisesMessage(DatabaseError, GATE), transaction.atomic():
            release_encounter(unconfirmed, self.patient, self.user)
        self.assertFalse(Encounter.objects.exists())

    def test_reproduce_R1_the_migrate_command_and_a_rollback_to_0030_refuse_the_same_way(self):
        """`migrate core 0018` and `migrate core 0030` through the command. RED on cb240141: the first reversed
        0022-0031 before 0021 refused; the second reversed 0031 with no refusal at all ('Reversing loses nothing')."""
        self.v3()
        for target in ('0018_servicehealth', '0020_payment_livemode', BEFORE_0031[1]):
            to_leaf()  # each attempt starts at the leaf, whatever an earlier one left behind
            with self.subTest(target=target):
                self.assert_refused_with_nothing_reversed(
                    lambda: call_command('migrate', 'core', target, verbosity=0, interactive=False),
                    r'0 mapping confirmation\(s\) and 1 mapping version\(s\)')

    def test_reproduce_R1_confirmed_v3_evidence_alone_refuses_before_anything_is_reversed(self):
        """A rollback that 0021 will refuse is refused before anything is dropped, even when every v3 mapping is
        confirmed. RED on cb240141: 0022-0031 were reversed and committed first."""
        MappingConfirmation.objects.create(version=self.v3(), confirmed_by=self.user)
        self.assert_refused_with_nothing_reversed(
            lambda: call_command('migrate', 'core', PREVIOUS_RELEASE[1], verbosity=0, interactive=False),
            r'1 mapping confirmation\(s\) and 1 mapping version\(s\)')

    def test_recorded_corrections_alone_refuse_at_the_leaf(self):
        TemplateVersion.objects.create(template=self.template, number=1, fields=LEGACY_FIELDS, created_by=self.user,
                                       corrections={'base_version': 1, 'removed': [], 'added': ['x'], 'kind_changed': {},
                                                    'renamed': []})
        self.assert_refused_with_nothing_reversed(lambda: MigrationExecutor(connection).migrate([PREVIOUS_RELEASE]),
                                                  r'0 mapping confirmation\(s\) and 1 mapping version\(s\)')

    def test_a_confirmation_alone_refuses_at_the_leaf(self):
        legacy = TemplateVersion.objects.create(template=self.template, number=1, fields=LEGACY_FIELDS, created_by=self.user)
        MappingConfirmation.objects.create(version=legacy, confirmed_by=self.user)
        self.assert_refused_with_nothing_reversed(lambda: MigrationExecutor(connection).migrate([PREVIOUS_RELEASE]),
                                                  r'1 mapping confirmation\(s\) and 0 mapping version\(s\)')

    def test_reproduce_R1_a_draft_started_while_the_gate_was_missing_cannot_be_finalized(self):
        """The window, made the only way it can still be made: 0031 reversed while no v3 mapping exists, then an
        automatic v3 mapping recorded at 0030 (this code's own write there), the previous release's draft on it (no gate
        at 0030), and `migrate` forward. RED on cb240141: re-applying 0031 did not look at the draft, and this code's
        saves moved it to review and then to finalized with the mapping still unconfirmed."""
        MigrationExecutor(connection).migrate([BEFORE_0031])
        self.assertFalse(gate_installed())
        unconfirmed = self.v3()
        draft = release_encounter(unconfirmed, self.patient, self.user)
        to_leaf()
        self.assertTrue(gate_installed())
        self.assertTrue(TemplateVersion.objects.get(pk=unconfirmed.pk).needs_confirmation)
        # A hold, not a refusal: the clinician's work on the draft is still saved.
        Encounter.objects.filter(pk=draft.pk).update(answers={'pain': {'text': 'yes', 'reviewed': True}}, status='review',
                                                     revision=1)
        with self.assertRaisesMessage(DatabaseError, HOLD), transaction.atomic():
            Encounter.objects.filter(pk=draft.pk).update(status='finalized', finalized_at=timezone.now(),
                                                         finalized_by=self.user)
        self.assertEqual(Encounter.objects.get(pk=draft.pk).status, 'review')
        # Positive control: once a clinician confirms the mapping, the same document finalizes.
        MappingConfirmation.objects.create(version=unconfirmed, confirmed_by=self.user)
        Encounter.objects.filter(pk=draft.pk).update(status='finalized', finalized_at=timezone.now(), finalized_by=self.user)
        self.assertEqual(Encounter.objects.get(pk=draft.pk).status, 'finalized')


@override_settings(**V3)
class AStrayDraftOnAnUnconfirmedV3Mapping(V3EncounterFixture, TestCase):
    """This code's own finalize, end to end, on the draft R1's window leaves behind: a real automatic v3 mapping that no
    clinician confirmed and a draft the previous release started on it while 0031's gate was missing (the gate is
    switched off for that one INSERT only; its window is reproduced through the migrations above)."""

    def setUp(self):
        V3Fixture.setUp(self)
        self.template, self.version = self.uploaded()
        self.assertTrue(self.version.needs_confirmation)
        with connection.cursor() as cursor:
            # The INSERT's deferred checks are fired before the trigger is switched back on (ALTER TABLE refuses a table
            # with pending trigger events), then returned to their declared DEFERRED.
            cursor.execute("SELECT string_agg(quote_ident(conname), ', ') FROM pg_constraint "
                           "WHERE conrelid = 'core_encounter'::regclass AND condeferrable AND condeferred")
            deferred = cursor.fetchone()[0]
            cursor.execute('ALTER TABLE core_encounter DISABLE TRIGGER encounter_scope')
            try:
                self.encounter = release_encounter(self.version, self.patient, self.user)
                cursor.execute(f'SET CONSTRAINTS {deferred} IMMEDIATE')
            finally:
                cursor.execute('ALTER TABLE core_encounter ENABLE TRIGGER encounter_scope')
                cursor.execute(f'SET CONSTRAINTS {deferred} DEFERRED')
        self.encounter = Encounter.objects.get(pk=self.encounter.pk)
        self.by = self.by_label(self.version)

    def exports(self):
        folder = private_path('exports')
        return sorted(path.name for path in folder.iterdir()) if folder.exists() else []

    def test_reproduce_R1_finalizing_is_refused_with_a_clear_message_and_writes_no_export(self):
        """RED on cb240141: the clinician's save and finalize succeeded and the export downloaded (200) with the mapping
        still unconfirmed. Now the review is saved, finalization is refused with a message saying why and what to do,
        and no filled export is written."""
        self.assertEqual(self.save(self.FULL).status_code, 302)
        self.assertEqual(Encounter.objects.get(pk=self.encounter.pk).status, 'review')
        response = self.finalize()
        self.assertEqual(response.status_code, 200)
        messages = ' '.join(str(message) for message in response.context['messages'])
        self.assertIn('has not been confirmed by a clinician', messages)
        self.assertIn('Nothing was finalized', messages)
        self.assertEqual(Encounter.objects.get(pk=self.encounter.pk).status, 'review')
        self.assertEqual(self.exports(), [])
        self.assertEqual(self.client.get(f'/encounters/{self.encounter.pk}/export/').status_code, 404)
        # Positive control: the clinician confirms the mapping on the form's page, and the same document finalizes.
        self.confirm(self.template, self.version)
        response = self.finalize()
        self.assertEqual(Encounter.objects.get(pk=self.encounter.pk).status, 'finalized',
                         [str(message) for message in response.context['messages']])
        self.assertEqual(len(self.exports()), 1)
