"""Migration 0015 (docs/gemini-migration/FINAL-V2.md 6.3; step 1d of its 8.1): EventInventory.appraisal_run, and nothing
else. Synthetic data only.

What is proved here:
- the installer's own gate (ops/install.py migration_verdict) reads 0015 as additive - "nullable" - and a planted NOT
  NULL control is refused by the same gate, so the verdict is not vacuous;
- 0015 is one AddField and nothing else: no existing column changed, no default of any kind, no NOT NULL, no backfill,
  no RunPython or SQL; it is the leaf after 0014, and the models agree with it (makemigrations --check);
- the column: ForeignKey(ProviderRun, on_delete=PROTECT, null=True, related_name='+'), in the model, in the migration
  and in PostgreSQL (nullable uuid, no default, a foreign key to studio_providerrun, never unique);
- the unique key (revision, interpretation_version, inventory_version, provider_run) and the version index are
  unchanged, so a refused pass-1 row (appraisal_run NULL) and a read row of a retry are separate keys, and a second read
  row for one pass-1 run and version pair is refused whatever its appraisal run;
- an older release's insert (its models at 0014) leaves the column NULL, and its SELECT still reads a row that sets it;
- PROTECT: a run that is a row's appraisal run cannot be deleted, and ProviderRun gets no reverse accessor for it.
"""
from __future__ import annotations

import ast
import hashlib
import io

from django.apps import apps
from django.core.management import call_command
from django.db import IntegrityError, connection, transaction
from django.db import models as django_models
from django.db.migrations import AddField
from django.db.migrations.loader import MigrationLoader
from django.db.models import NOT_PROVIDED, PROTECT, ProtectedError
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from studio import models
from studio.types import sha256_json
from tests.support import factories as f
from tests.test_models_event_inventory import MIGRATIONS, ROOT, install_gate

NAME = '0015_inventory_appraisal'
PREVIOUS = ('studio', '0014_event_inventory')
SOURCE = (MIGRATIONS / f'{NAME}.py').read_text(encoding='utf-8')
TEXT = ('SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\n'
        'Date of service: 2026-11-09\n'
        'Colonoscopy: The colonoscope was advanced to the cecum. A 5 mm polyp was removed with a cold snare.\n')
UNIQUE = ('revision', 'interpretation_version', 'inventory_version', 'provider_run')


def loaded_migration():
    """0015 as Django loads it (no database needed)."""
    return MigrationLoader(None, ignore_no_migrations=True).get_migration('studio', NAME)


class MigrationGateTests(SimpleTestCase):
    def test_0015_is_read_additive_by_the_installers_gate(self):
        verdict = install_gate().migration_verdict(SOURCE)
        self.assertEqual(verdict, {'safe': True, 'why': ['eventinventory.appraisal_run: nullable']})
        verdicts = install_gate().migration_safety(MIGRATIONS)
        self.assertEqual(verdicts[NAME], verdict)
        self.assertTrue(all(found['safe'] for found in verdicts.values()), verdicts)

    def test_control_the_gate_refuses_0015_made_not_null(self):
        # the same file with the column NOT NULL: an older release's insert names no value for it and is refused, so
        # the gate must say so - or the verdict above proves nothing
        anchor = 'field=models.ForeignKey(null=True, '
        self.assertEqual(SOURCE.count(anchor), 1)
        found = install_gate().migration_verdict(SOURCE.replace(anchor, 'field=models.ForeignKey('))
        self.assertEqual(found, {'safe': False, 'why': ['eventinventory.appraisal_run: NOT NULL with no database '
                                                        "default, so an older pair's insert is refused"]})
        # the gate reads any nullable column as "nullable", a default or not, so "no default of any kind" (6.3) is read
        # from the file itself: the field's keywords are exactly these four
        (call,) = [node for node in ast.walk(ast.parse(SOURCE)) if isinstance(node, ast.Call)
                   and isinstance(node.func, ast.Attribute) and node.func.attr == 'ForeignKey']
        self.assertEqual(sorted(keyword.arg for keyword in call.keywords), ['null', 'on_delete', 'related_name', 'to'])
        self.assertEqual(call.args, [])

    def test_0015_adds_one_column_and_nothing_else(self):
        migration = loaded_migration()
        self.assertEqual(migration.dependencies, [PREVIOUS])
        self.assertIs(migration.atomic, True)
        self.assertEqual([type(operation) for operation in migration.operations], [AddField])
        (operation,) = migration.operations
        self.assertEqual((operation.model_name, operation.name), ('eventinventory', 'appraisal_run'))
        calls = {node.func.attr for node in ast.walk(ast.parse(SOURCE))
                 if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)}
        self.assertEqual(calls, {'AddField', 'ForeignKey'})  # no RunPython, SQL, AlterField, constraint or index
        leaves = MigrationLoader(None, ignore_no_migrations=True).graph.leaf_nodes('studio')
        self.assertEqual(leaves, [('studio', NAME)])

    def test_the_column_is_exactly_the_designs(self):
        (operation,) = loaded_migration().operations
        for where, field in (('migration', operation.field),
                             ('model', apps.get_model('studio', 'EventInventory')._meta.get_field('appraisal_run'))):
            with self.subTest(where):
                self.assertIsInstance(field, django_models.ForeignKey)
                self.assertEqual(field.remote_field.model if where == 'model' else field.remote_field.model.lower(),
                                 models.ProviderRun if where == 'model' else 'studio.providerrun')
                self.assertIs(field.remote_field.on_delete, PROTECT)
                self.assertIs(field.null, True)
                self.assertIs(field.has_default(), False)
                self.assertIs(field.db_default, NOT_PROVIDED)
                self.assertIs(field.unique, False)
                self.assertIs(field.db_constraint, True)
                self.assertEqual(field.remote_field.related_name, '+')
        # the unique key and the version index are 0014's, unchanged (6.3: the key stays sufficient)
        meta = models.EventInventory._meta
        (constraint,) = meta.constraints
        self.assertEqual((constraint.name, tuple(constraint.fields), constraint.condition),
                         ('one_inventory_per_revision_versions_run', UNIQUE, None))
        (index,) = meta.indexes
        self.assertEqual((index.name, tuple(index.fields)),
                         ('studio_inventory_versions', ('revision', 'interpretation_version', 'inventory_version')))
        # ProviderRun gets no reverse accessor for it ('+'): a run's event_inventories stay pass 1's
        self.assertFalse([relation for relation in models.ProviderRun._meta.related_objects
                          if relation.field.name == 'appraisal_run' and not relation.hidden])

    def test_models_still_import_nothing_but_django_and_the_standard_library(self):
        tree = ast.parse((ROOT / 'studio' / 'models.py').read_text(encoding='utf-8'))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.add(node.module if not node.level else f'.{node.module}')
        self.assertEqual(imported, {'uuid', 'django.contrib.auth.models', 'django.core.exceptions', 'django.db',
                                    'django.db.models'})


def gemini_run(enc, rev, purpose, response):
    body = {'contents': [{'parts': [{'text': 'synthetic'}]}], 'purpose': purpose}
    return models.ProviderRun.objects.create(
        encounter=enc, revision=rev, provider='gemini', adapter_version='gemini-generate@cptstudio-2', purpose=purpose,
        request_sha256=sha256_json(body), request_body=body, contexts=[], state=models.ProviderRun.SUCCEEDED, sent=True,
        http_status=200, response_bytes=response, response_sha256=hashlib.sha256(response).hexdigest(),
        started_at=timezone.now(), finished_at=timezone.now())


def inventory(enc, rev, run, *, appraisal_run=None, state=models.EventInventory.READ,
              interpretation_version='gemini-events@2/appraisal@1', inventory_version='gemini-inventory@2'):
    parts = {'events': {}, 'encounter_facts': {}, 'open_questions': [], 'verification': {'refused': state == 'refused'}}
    return models.EventInventory.objects.create(
        encounter=enc, revision=rev, provider_run=run, appraisal_run=appraisal_run,
        interpretation_version=interpretation_version, inventory_version=inventory_version,
        text_sha256=rev.text_sha256, request_sha256=run.request_sha256, response_sha256=run.response_sha256,
        state=state, sha256=sha256_json(parts), **parts)


class MakemigrationsTests(TestCase):
    def test_the_models_and_the_migrations_agree(self):
        out, err = io.StringIO(), io.StringIO()
        try:
            call_command('makemigrations', check=True, dry_run=True, stdout=out, stderr=err)
        except SystemExit as exit:
            self.fail(f'makemigrations --check wants a migration ({exit.code}): {out.getvalue()} {err.getvalue()}')
        self.assertIn('No changes detected', out.getvalue())


class ColumnTests(TestCase):
    def setUp(self):
        self.ws = f.workspace()
        self.usr = f.member(self.ws)
        self.enc = f.encounter(self.ws, self.usr)
        self.rev = f.pasted_revision(self.enc, self.usr, TEXT)
        self.run = gemini_run(self.enc, self.rev, 'interpretation', b'{"candidates": [1]}')
        self.appraisal = gemini_run(self.enc, self.rev, 'appraisal', b'{"candidates": [2]}')

    def test_the_database_column_is_a_nullable_foreign_key_with_no_default(self):
        with connection.cursor() as cursor:
            cursor.execute('SELECT is_nullable, column_default, data_type FROM information_schema.columns '
                           'WHERE table_schema = current_schema() AND table_name = %s AND column_name = %s',
                           ['studio_eventinventory', 'appraisal_run_id'])
            self.assertEqual(cursor.fetchall(), [('YES', None, 'uuid')])
            found = connection.introspection.get_constraints(cursor, models.EventInventory._meta.db_table)
        on_column = [item for item in found.values() if item['columns'] == ['appraisal_run_id']]
        self.assertIn(('studio_providerrun', 'id'), [item['foreign_key'] for item in on_column])
        self.assertFalse([item for item in on_column if item['unique']])
        unique = found['one_inventory_per_revision_versions_run']
        self.assertEqual((unique['unique'], unique['columns']),
                         (True, ['revision_id', 'interpretation_version', 'inventory_version', 'provider_run_id']))

    def test_an_older_releases_insert_leaves_it_null_and_its_select_reads_a_row_that_sets_it(self):
        old = MigrationLoader(connection).project_state(PREVIOUS).apps
        OldInventory = old.get_model('studio', 'EventInventory')
        self.assertNotIn('appraisal_run', {field.name for field in OldInventory._meta.concrete_fields})
        parts = {'events': {'passages': [], 'lesions': [], 'events': [], 'relations': []}, 'encounter_facts': {},
                 'open_questions': [], 'verification': {}}
        older = OldInventory.objects.create(
            encounter_id=self.enc.pk, revision_id=self.rev.pk, provider_run_id=self.run.pk,
            interpretation_version='gemini-events@1', inventory_version='gemini-inventory@1',
            text_sha256=self.rev.text_sha256, request_sha256=self.run.request_sha256,
            response_sha256=self.run.response_sha256, state='read', sha256=sha256_json(parts), **parts)
        self.assertIsNone(models.EventInventory.objects.get(pk=older.pk).appraisal_run_id)
        with connection.cursor() as cursor:
            cursor.execute('SELECT appraisal_run_id IS NULL FROM studio_eventinventory WHERE id = %s', [older.pk])
            self.assertEqual(cursor.fetchone(), (True,))
        newer = inventory(self.enc, self.rev, gemini_run(self.enc, self.rev, 'interpretation', b'{"c": 3}'),
                          appraisal_run=self.appraisal)
        self.assertEqual(OldInventory.objects.get(pk=newer.pk).sha256, newer.sha256)

    def test_the_unique_key_is_unchanged_and_stays_sufficient(self):
        refused = inventory(self.enc, self.rev, self.run, state=models.EventInventory.REFUSED)  # pass 1 refused
        self.assertIsNone(refused.appraisal_run_id)
        with self.assertRaises(IntegrityError), transaction.atomic():  # one row per pass-1 run and version pair
            inventory(self.enc, self.rev, self.run, appraisal_run=self.appraisal)
        retry = gemini_run(self.enc, self.rev, 'interpretation', b'{"candidates": [3]}')
        read = inventory(self.enc, self.rev, retry, appraisal_run=self.appraisal)  # the retry is a new pass-1 run
        with self.assertRaises(IntegrityError), transaction.atomic():
            inventory(self.enc, self.rev, retry,
                      appraisal_run=gemini_run(self.enc, self.rev, 'appraisal', b'{"candidates": [4]}'))
        self.assertEqual(models.EventInventory.objects.get(pk=read.pk).appraisal_run, self.appraisal)
        self.assertEqual(list(self.run.event_inventories.all()), [refused])  # pass 1's relation, unchanged

    def test_a_run_that_is_an_appraisal_run_cannot_be_deleted(self):
        row = inventory(self.enc, self.rev, self.run, appraisal_run=self.appraisal)
        with self.assertRaises(ProtectedError) as refused, transaction.atomic():
            self.appraisal.delete()
        self.assertEqual(set(refused.exception.protected_objects), {row})
        self.assertTrue(models.ProviderRun.objects.filter(pk=self.appraisal.pk).exists())
