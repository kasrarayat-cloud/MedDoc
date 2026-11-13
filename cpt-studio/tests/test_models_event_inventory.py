"""Gemini migration S05 (FINAL.md section 4, D6, D11, D15): the EventInventory, InterpreterHold and
InterpreterHoldRelease tables and the three nullable columns migration 0014 adds - EncounterContext.event_inventory,
Assessment.event_inventory and Assessment.interpretation. Synthetic data only.

What each class proves:
- the migration is additive, read safe by the installer's own gate (ops/install.py migration_verdict), carries no
  backfill, and matches the models (makemigrations --check);
- the three columns are nullable with NO database default, so a row an older release inserts - which names none of
  them - holds NULL there: that NULL is what keeps a legacy row a legacy row on the rollback image and in the new
  image's dispatch;
- the new rows are append-only, one inventory per (revision, interpretation version, inventory version, run), and an
  inventory referenced by a context or an assessment cannot be deleted;
- every foreign key on the new tables and columns is PROTECT. For the hold tables the refusal is also shown through the
  parents' own delete(): ProviderRun and User are plain models, and a cascade removes child rows with a raw delete that
  ImmutableModel never sees.
"""
import ast
import hashlib
import io
from pathlib import Path

from django.apps import apps
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import IntegrityError, connection, transaction
from django.db import models as django_models
from django.db.migrations import AddConstraint, AddField, AddIndex, CreateModel
from django.db.migrations.loader import MigrationLoader
from django.db.models import NOT_PROVIDED, PROTECT, ProtectedError
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from studio import models
from studio.types import sha256_json
from tests.support import factories as f

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / 'studio' / 'migrations'
NAME = '0014_event_inventory'
PREVIOUS = ('studio', '0013_completion_answer_binding')
SOURCE = (MIGRATIONS / f'{NAME}.py').read_text(encoding='utf-8')

# the three columns 0014 adds to existing tables: (model, field, column)
NEW_COLUMNS = (('encountercontext', 'event_inventory', 'event_inventory_id'),
               ('assessment', 'event_inventory', 'event_inventory_id'),
               ('assessment', 'interpretation', 'interpretation'))

TEXT = ('SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\n'
        'Date of service: 2026-10-21\n'
        'Colonoscopy: The colonoscope was advanced to the cecum. A 6 mm polyp was removed with a cold snare.\n')
# FINAL 3.1's labels, written out: studio.interpretation is another slice's
INTERPRETATION_VERSION = 'gemini-events@1'
INVENTORY_VERSION = 'gemini-inventory@1'
ADAPTER_VERSION = 'gemini-generate@cptstudio-1'


def install_gate():
    from ops import install
    return install


def verdict_of(source):
    return install_gate().migration_verdict(source)


def loaded_migration():
    """0014 as Django loads it (no database needed)."""
    return MigrationLoader(None, ignore_no_migrations=True).get_migration('studio', NAME)


# --- the migration, read without a database --------------------------------------------------------------------------

class MigrationGateTests(SimpleTestCase):
    def test_0014_is_read_safe_by_the_installers_gate_and_says_why(self):
        verdict = verdict_of(SOURCE)
        self.assertEqual(verdict, {'safe': True, 'why': [
            'EventInventory: a new table no older revision reads',
            'eventinventory: an index (writes are not refused)',
            'eventinventory: a constraint on a table this migration creates',
            'encountercontext.event_inventory: nullable',
            'assessment.event_inventory: nullable',
            'assessment.interpretation: nullable',
            'InterpreterHold: a new table no older revision reads',
            'InterpreterHoldRelease: a new table no older revision reads']})
        # the installer reads the committed directory the same way, and every migration after its baseline stays safe
        verdicts = install_gate().migration_safety(MIGRATIONS)
        self.assertEqual(verdicts[NAME], verdict)
        self.assertTrue(all(found['safe'] for found in verdicts.values()), verdicts)

    def test_control_the_gate_refuses_0014_with_a_column_an_older_insert_cannot_satisfy(self):
        # the same file with Assessment.interpretation made NOT NULL (a Python default only): an older release's insert
        # names no value for it, so the database refuses it - the gate must say so, or the test above proves nothing
        anchor = "name='interpretation',\n            field=models.JSONField(blank=True, null=True),"
        self.assertEqual(SOURCE.count(anchor), 1)
        mutated = SOURCE.replace(anchor, "name='interpretation',\n            field=models.JSONField(blank=True, "
                                         "default=dict),")
        found = verdict_of(mutated)
        self.assertFalse(found['safe'], found)
        self.assertEqual(found['why'], ['assessment.interpretation: NOT NULL with no database default, so an older '
                                        "pair's insert is refused"])

    def test_0014_has_no_backfill_and_only_additive_operations(self):
        migration = loaded_migration()
        self.assertEqual(migration.dependencies, [PREVIOUS])
        self.assertIs(migration.atomic, True)
        shapes = []
        for operation in migration.operations:
            if isinstance(operation, CreateModel):
                shapes.append(('CreateModel', operation.name))
            elif isinstance(operation, AddField):
                shapes.append(('AddField', f'{operation.model_name}.{operation.name}'))
            elif isinstance(operation, (AddIndex, AddConstraint)):
                shapes.append((type(operation).__name__, operation.model_name))
            else:
                self.fail(f'not an additive operation: {operation!r}')
        self.assertEqual(shapes, [('CreateModel', 'EventInventory'), ('AddIndex', 'eventinventory'),
                                  ('AddConstraint', 'eventinventory'), ('AddField', 'encountercontext.event_inventory'),
                                  ('AddField', 'assessment.event_inventory'), ('AddField', 'assessment.interpretation'),
                                  ('CreateModel', 'InterpreterHold'), ('CreateModel', 'InterpreterHoldRelease')])
        # no SQL and no Python step anywhere in the file (nothing is backfilled, nothing is rewritten)
        calls = {node.func.attr for node in ast.walk(ast.parse(SOURCE))
                 if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)}
        self.assertFalse(calls & {'RunPython', 'RunSQL', 'SeparateDatabaseAndState', 'AlterField', 'RemoveField',
                                  'RenameField', 'DeleteModel', 'AlterModelTable'}, calls)

    def test_the_three_added_columns_are_nullable_with_no_default_of_any_kind(self):
        added = {(operation.model_name, operation.name): operation.field for operation in loaded_migration().operations
                 if isinstance(operation, AddField)}
        self.assertEqual(sorted(added), sorted((model, field) for model, field, _ in NEW_COLUMNS))
        for (model, name), field in added.items():
            with self.subTest(f'{model}.{name}'):
                self.assertIs(field.null, True)
                self.assertIs(field.has_default(), False)  # no Python default: the ORM writes NULL when unnamed
                self.assertIs(field.db_default, NOT_PROVIDED)  # no database default: an older insert gets NULL
                self.assertIs(field.unique, False)
        # and the models say the same, field by field (makemigrations --check below proves they match the file)
        for model, name, _ in NEW_COLUMNS:
            field = apps.get_model('studio', model)._meta.get_field(name)
            with self.subTest(model=model, name=name):
                self.assertIs(field.null, True)
                self.assertIs(field.has_default(), False)
                self.assertIs(field.db_default, NOT_PROVIDED)
                if field.is_relation:
                    self.assertIs(field.remote_field.model, models.EventInventory)
                    self.assertIs(field.remote_field.on_delete, PROTECT)
                    self.assertEqual(field.remote_field.related_name, '+')


class ModelShapeTests(SimpleTestCase):
    def test_the_new_tables_are_append_only_records(self):
        for model in (models.EventInventory, models.InterpreterHold, models.InterpreterHoldRelease):
            with self.subTest(model.__name__):
                self.assertTrue(issubclass(model, models.ImmutableModel))
                self.assertIsInstance(model.objects.all(), models.ImmutableQuerySet)

    def test_an_inventory_names_its_encounter_revision_and_run_and_none_may_be_missing(self):
        meta = models.EventInventory._meta
        for name, target, related in (('encounter', models.Encounter, 'event_inventories'),
                                      ('revision', models.SourceRevision, 'event_inventories'),
                                      ('provider_run', models.ProviderRun, 'event_inventories')):
            field = meta.get_field(name)
            with self.subTest(name):
                self.assertIs(field.null, False)
                self.assertIs(field.remote_field.model, target)
                self.assertIs(field.remote_field.on_delete, PROTECT)
                self.assertEqual(field.remote_field.related_name, related)
        (constraint,) = meta.constraints
        self.assertEqual((constraint.name, tuple(constraint.fields)),
                         ('one_inventory_per_revision_versions_run',
                          ('revision', 'interpretation_version', 'inventory_version', 'provider_run')))
        self.assertIsNone(constraint.condition)  # over every row, not a subset
        (index,) = meta.indexes
        self.assertEqual((index.name, tuple(index.fields)),
                         ('studio_inventory_versions', ('revision', 'interpretation_version', 'inventory_version')))
        self.assertEqual({name: meta.get_field(name).max_length for name in (
            'interpretation_version', 'inventory_version', 'text_sha256', 'request_sha256', 'response_sha256', 'state',
            'sha256')}, {'interpretation_version': 40, 'inventory_version': 40, 'text_sha256': 64, 'request_sha256': 64,
                         'response_sha256': 64, 'state': 12, 'sha256': 64})
        self.assertEqual((models.EventInventory.READ, models.EventInventory.REFUSED), ('read', 'refused'))
        # the JSON parts have no default: a writer that forgets one is refused by the database, never stored empty
        for name in ('events', 'encounter_facts', 'open_questions', 'verification'):
            self.assertIs(meta.get_field(name).has_default(), False, name)

    def test_the_hold_is_installation_wide_and_its_release_is_one_to_one(self):
        hold = models.InterpreterHold._meta
        self.assertFalse([field.name for field in hold.get_fields() if getattr(field, 'related_model', None)
                          is models.Workspace or field.name in ('workspace', 'encounter')])
        self.assertEqual(hold.get_field('vendor_status').max_length, 40)
        self.assertFalse(hold.get_field('reason').choices)  # holds.classify owns them: a new one needs no migration
        release = models.InterpreterHoldRelease._meta.get_field('hold')
        self.assertIsInstance(release, django_models.OneToOneField)
        self.assertEqual(release.remote_field.related_name, 'release')
        # every foreign key PROTECT, in the models and in 0014 alike (FINAL 4.1; as OperatorGrant and
        # OperatorRevocation). Under any other on_delete, deleting a run would end a standing hold and deleting an
        # operator would revive a hold they released, with no release row saying who or why (InterpreterHoldRowTests
        # shows the refusals)
        created = {operation.name: dict(operation.fields) for operation in loaded_migration().operations
                   if isinstance(operation, CreateModel)}
        for model, name, target in ((models.InterpreterHold, 'run', models.ProviderRun),
                                    (models.InterpreterHoldRelease, 'hold', models.InterpreterHold),
                                    (models.InterpreterHoldRelease, 'released_by', models.User)):
            field = model._meta.get_field(name)
            with self.subTest(f'{model.__name__}.{name}'):
                self.assertIs(field.null, False)
                self.assertIs(field.remote_field.model, target)
                self.assertIs(field.remote_field.on_delete, PROTECT)
                self.assertIs(created[model.__name__][name].remote_field.on_delete, PROTECT)

    def test_models_still_import_nothing_but_django_and_the_standard_library(self):
        # ADJUDICATION R-1 rests on this: AppConfig.ready (the sentinel's install point) imports studio.models, which
        # must bring in no legacy module
        tree = ast.parse((ROOT / 'studio' / 'models.py').read_text(encoding='utf-8'))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.add(node.module if not node.level else f'.{node.module}')
        self.assertEqual(imported, {'uuid', 'django.contrib.auth.models', 'django.core.exceptions', 'django.db',
                                    'django.db.models'})


# --- rows -------------------------------------------------------------------------------------------------------------

def scene():
    ws = f.workspace()
    usr = f.member(ws)
    enc = f.encounter(ws, usr)
    rev = f.pasted_revision(enc, usr, TEXT)
    return ws, usr, enc, rev


def gemini_run(enc, rev, response=b'{"candidates": []}'):
    body = {'systemInstruction': {'parts': [{'text': 'synthetic'}]}, 'contents': [{'parts': [{'text': rev.text}]}],
            'generationConfig': {'temperature': 0}}
    return models.ProviderRun.objects.create(
        encounter=enc, revision=rev, provider='gemini', adapter_version=ADAPTER_VERSION, purpose='interpretation',
        request_sha256=sha256_json(body), request_body=body, contexts=[], state=models.ProviderRun.SUCCEEDED, sent=True,
        http_status=200, response_bytes=response, response_sha256=hashlib.sha256(response).hexdigest(),
        started_at=timezone.now(), finished_at=timezone.now())


def inventory(enc, rev, run, *, interpretation_version=INTERPRETATION_VERSION, inventory_version=INVENTORY_VERSION,
              state=models.EventInventory.READ):
    parts = {'events': {'passages': [], 'lesions': [], 'events': [], 'relations': []}, 'encounter_facts': {},
             'open_questions': [], 'verification': {'problems': [], 'refused': state == models.EventInventory.REFUSED}}
    return models.EventInventory.objects.create(
        encounter=enc, revision=rev, provider_run=run, interpretation_version=interpretation_version,
        inventory_version=inventory_version, text_sha256=rev.text_sha256, request_sha256=run.request_sha256,
        response_sha256=run.response_sha256, state=state, sha256=sha256_json(parts), **parts)


def context_row(enc, rev, **extra):
    facts = {'service_date': {'value': '2026-10-21', 'origin': 'document', 'evidence': [], 'note': ''}}
    return models.EncounterContext.objects.create(encounter=enc, revision=rev, facts=facts, version='gemini-context@1',
                                                  sha256=sha256_json(facts), **extra)


def routing_row(rev):
    result = {'version': 'gemini-routing@1', 'document_kind': '', 'findings': []}
    return models.RoutingRun.objects.create(revision=rev, version='gemini-routing@1', result=result,
                                            sha256=sha256_json(result))


def assessment_row(enc, rev, ctx, routing, **extra):
    return models.Assessment.objects.create(encounter=enc, revision=rev, context=ctx, routing=routing,
                                            profiles_version='gi-profiles@test', engine_version='cpt-studio-events@1',
                                            sha256='0' * 64, **extra)


class MakemigrationsTests(TestCase):
    def test_the_models_and_the_migrations_agree(self):
        out, err = io.StringIO(), io.StringIO()
        try:
            call_command('makemigrations', check=True, dry_run=True, stdout=out, stderr=err)
        except SystemExit as exit:  # --check exits non-zero when a model change has no migration
            self.fail(f'makemigrations --check wants a migration ({exit.code}): {out.getvalue()} {err.getvalue()}')
        self.assertIn('No changes detected', out.getvalue())


class EventInventoryRowTests(TestCase):
    def setUp(self):
        self.ws, self.usr, self.enc, self.rev = scene()
        self.run = gemini_run(self.enc, self.rev)

    def test_an_inventory_row_refuses_updates_and_deletes(self):
        inv = inventory(self.enc, self.rev, self.run)
        inv.state = models.EventInventory.REFUSED
        with self.assertRaises(ValidationError):
            inv.save()
        with self.assertRaises(ValidationError):
            inv.delete()
        with self.assertRaises(ValidationError):
            models.EventInventory.objects.filter(pk=inv.pk).update(state=models.EventInventory.REFUSED)
        with self.assertRaises(ValidationError):
            models.EventInventory.objects.filter(pk=inv.pk).delete()
        stored = models.EventInventory.objects.get(pk=inv.pk)
        self.assertEqual(stored.state, models.EventInventory.READ)
        self.assertEqual(stored.events, {'passages': [], 'lesions': [], 'events': [], 'relations': []})
        self.assertEqual(list(self.enc.event_inventories.all()), [stored])  # scoped by encounter (tenancy)
        self.assertEqual(list(models.EventInventory.objects.filter(encounter__workspace=self.ws)), [stored])
        self.assertEqual(list(self.rev.event_inventories.all()), [stored])
        self.assertEqual(list(self.run.event_inventories.all()), [stored])

    def test_one_inventory_per_revision_versions_and_run(self):
        first = inventory(self.enc, self.rev, self.run)
        with self.assertRaises(IntegrityError), transaction.atomic():
            inventory(self.enc, self.rev, self.run)
        with self.assertRaises(IntegrityError), transaction.atomic():  # a refused reading is the same key
            inventory(self.enc, self.rev, self.run, state=models.EventInventory.REFUSED)
        # a new inventory version re-reads the same stored bytes into a row beside the first, with no new request
        renormalized = inventory(self.enc, self.rev, self.run, inventory_version='gemini-inventory@2')
        # a new interpretation version is a new request, so a new run; and a recorded retry is a new run too
        reread = inventory(self.enc, self.rev, gemini_run(self.enc, self.rev, b'{"candidates": [1]}'),
                           interpretation_version='gemini-events@2')
        retried = inventory(self.enc, self.rev, gemini_run(self.enc, self.rev, b'{"candidates": [2]}'))
        self.assertEqual(models.EventInventory.objects.filter(revision=self.rev).count(), 4)
        self.assertEqual(len({first.pk, renormalized.pk, reread.pk, retried.pk}), 4)

    def test_an_inventory_needs_its_run(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            models.EventInventory.objects.create(
                encounter=self.enc, revision=self.rev, interpretation_version=INTERPRETATION_VERSION,
                inventory_version=INVENTORY_VERSION, text_sha256=self.rev.text_sha256, request_sha256='0' * 64,
                response_sha256='0' * 64, state=models.EventInventory.READ, events={}, encounter_facts={},
                open_questions=[], verification={}, sha256='0' * 64)

    def test_a_writer_that_omits_a_part_is_refused_not_stored_empty(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            models.EventInventory.objects.create(
                encounter=self.enc, revision=self.rev, provider_run=self.run,
                interpretation_version=INTERPRETATION_VERSION, inventory_version=INVENTORY_VERSION,
                text_sha256=self.rev.text_sha256, request_sha256=self.run.request_sha256,
                response_sha256=self.run.response_sha256, state=models.EventInventory.READ, events={},
                encounter_facts={}, open_questions=[], sha256='0' * 64)  # no verification

    def test_the_database_holds_the_unique_key_and_the_version_index(self):
        with connection.cursor() as cursor:
            found = connection.introspection.get_constraints(cursor, models.EventInventory._meta.db_table)
        unique = found['one_inventory_per_revision_versions_run']
        self.assertTrue(unique['unique'])
        self.assertEqual(unique['columns'], ['revision_id', 'interpretation_version', 'inventory_version',
                                             'provider_run_id'])
        index = found['studio_inventory_versions']
        self.assertTrue(index['index'])
        self.assertFalse(index['unique'])
        self.assertEqual(index['columns'], ['revision_id', 'interpretation_version', 'inventory_version'])
        foreign = {tuple(item['columns']): item['foreign_key'] for item in found.values() if item['foreign_key']}
        self.assertEqual(foreign, {('encounter_id',): ('studio_encounter', 'id'),
                                   ('revision_id',): ('studio_sourcerevision', 'id'),
                                   ('provider_run_id',): ('studio_providerrun', 'id'),
                                   # FINAL-V2 6.3, migration 0015: a v2 row's appraisal run (nullable)
                                   ('appraisal_run_id',): ('studio_providerrun', 'id')})

    def test_a_referenced_inventory_cannot_be_deleted_even_past_the_immutable_manager(self):
        inv = inventory(self.enc, self.rev, self.run)
        context_row(self.enc, self.rev, event_inventory=inv)
        with self.assertRaises(ProtectedError), transaction.atomic():
            django_models.QuerySet(models.EventInventory).filter(pk=inv.pk).delete()
        unreferenced = inventory(self.enc, self.rev, self.run, inventory_version='gemini-inventory@2')
        ctx = context_row(self.enc, self.rev)
        assessment_row(self.enc, self.rev, ctx, routing_row(self.rev), event_inventory=unreferenced)
        with self.assertRaises(ProtectedError), transaction.atomic():
            django_models.QuerySet(models.EventInventory).filter(pk=unreferenced.pk).delete()
        self.assertEqual(models.EventInventory.objects.count(), 2)


class NewColumnTests(TestCase):
    def setUp(self):
        self.ws, self.usr, self.enc, self.rev = scene()
        self.run = gemini_run(self.enc, self.rev)

    def test_the_columns_are_nullable_with_no_database_default(self):
        with connection.cursor() as cursor:
            cursor.execute(
                'SELECT table_name, column_name, is_nullable, column_default, data_type '
                'FROM information_schema.columns WHERE table_schema = current_schema() '
                'AND ((table_name = %s AND column_name IN (%s, %s)) OR (table_name = %s AND column_name = %s)) '
                'ORDER BY table_name, column_name',
                ['studio_assessment', 'event_inventory_id', 'interpretation', 'studio_encountercontext',
                 'event_inventory_id'])
            rows = cursor.fetchall()
        self.assertEqual(rows, [('studio_assessment', 'event_inventory_id', 'YES', None, 'uuid'),
                                ('studio_assessment', 'interpretation', 'YES', None, 'jsonb'),
                                ('studio_encountercontext', 'event_inventory_id', 'YES', None, 'uuid')])
        for table in ('studio_assessment', 'studio_encountercontext'):
            with connection.cursor() as cursor:
                found = connection.introspection.get_constraints(cursor, table)
            references = [item for item in found.values() if item['columns'] == ['event_inventory_id']]
            self.assertIn(('studio_eventinventory', 'id'), [item['foreign_key'] for item in references], table)
            self.assertFalse([item for item in references if item['unique']], table)

    def test_an_older_releases_inserts_leave_the_three_columns_null(self):
        # the models of the previous release (its migration state at 0013) know none of the three columns, so the
        # INSERT they issue names none of them - exactly what the rollback image and the blue/green overlap write
        old = MigrationLoader(connection).project_state(PREVIOUS).apps
        OldContext, OldAssessment = old.get_model('studio', 'EncounterContext'), old.get_model('studio', 'Assessment')
        self.assertFalse({'event_inventory'} & {field.name for field in OldContext._meta.concrete_fields})
        self.assertFalse({'event_inventory', 'interpretation'}
                         & {field.name for field in OldAssessment._meta.concrete_fields})
        facts = {'service_date': {'value': '2026-10-21', 'origin': 'document', 'evidence': [], 'note': ''}}
        old_context = OldContext.objects.create(encounter_id=self.enc.pk, revision_id=self.rev.pk, facts=facts,
                                                version='gi-context@5', sha256=sha256_json(facts))
        routing = routing_row(self.rev)
        old_assessment = OldAssessment.objects.create(
            encounter_id=self.enc.pk, revision_id=self.rev.pk, context_id=old_context.pk, routing_id=routing.pk,
            profiles_version='gi-profiles@test', engine_version='cpt-studio-validation@10', sha256='1' * 64)
        context = models.EncounterContext.objects.get(pk=old_context.pk)
        assessment = models.Assessment.objects.get(pk=old_assessment.pk)
        self.assertIsNone(context.event_inventory_id)
        self.assertIsNone(assessment.event_inventory_id)
        self.assertIsNone(assessment.interpretation)
        with connection.cursor() as cursor:  # NULL in the database itself, not a JSON null or an empty object
            cursor.execute('SELECT interpretation IS NULL, event_inventory_id IS NULL FROM studio_assessment '
                           'WHERE id = %s', [old_assessment.pk])
            self.assertEqual(cursor.fetchone(), (True, True))

    def test_this_releases_legacy_inserts_leave_them_null_too(self):
        # the new image's legacy path names none of them either (no Python default): a legacy row stays legacy
        ctx = context_row(self.enc, self.rev)
        assessment = assessment_row(self.enc, self.rev, ctx, routing_row(self.rev))
        ctx.refresh_from_db()
        assessment.refresh_from_db()
        self.assertIsNone(ctx.event_inventory_id)
        self.assertIsNone(assessment.event_inventory_id)
        self.assertIsNone(assessment.interpretation)

    def test_a_new_path_context_and_assessment_bind_the_inventory_and_the_older_release_still_reads_them(self):
        inv = inventory(self.enc, self.rev, self.run)
        ctx = context_row(self.enc, self.rev, event_inventory=inv)
        record = {'engine_version': 'cpt-studio-events@1', 'interpretation_version': INTERPRETATION_VERSION,
                  'inventory_version': INVENTORY_VERSION, 'inventory': str(inv.pk), 'inventory_sha256': inv.sha256,
                  'run': str(self.run.pk), 'context': str(ctx.pk),
                  'sentinel': {'legacy_calls': 0, 'scope': 'assess', 'tool': 'sys.monitoring'}}
        assessment = assessment_row(self.enc, self.rev, ctx, routing_row(self.rev), event_inventory=inv,
                                    interpretation=record)
        stored = models.Assessment.objects.get(pk=assessment.pk)
        self.assertEqual(stored.event_inventory, inv)
        self.assertEqual(stored.interpretation, record)
        self.assertEqual(models.EncounterContext.objects.get(pk=ctx.pk).event_inventory_id, inv.pk)
        # D15 / P8: the previous release's models read both rows without error (their SELECT names no new column)
        old = MigrationLoader(connection).project_state(PREVIOUS).apps
        old_assessment = old.get_model('studio', 'Assessment').objects.get(pk=assessment.pk)
        self.assertEqual((old_assessment.sha256, old_assessment.engine_version), ('0' * 64, 'cpt-studio-events@1'))
        self.assertEqual(old.get_model('studio', 'EncounterContext').objects.get(pk=ctx.pk).version, 'gemini-context@1')


class InterpreterHoldRowTests(TestCase):
    def setUp(self):
        self.ws, self.usr, self.enc, self.rev = scene()
        self.run = gemini_run(self.enc, self.rev, b'{"error": {"code": 429, "status": "RESOURCE_EXHAUSTED"}}')
        self.operator = f.user('synthetic-operator')

    def hold(self, **extra):
        values = {'reason': models.InterpreterHold.QUOTA, 'http_status': 429, 'vendor_status': 'RESOURCE_EXHAUSTED',
                  'violations': [{'quotaId': 'GenerateRequestsPerDayPerProjectPerModel-FreeTier'}], 'run': self.run}
        return models.InterpreterHold.objects.create(**{**values, **extra})

    def active(self):
        return list(models.InterpreterHold.objects.filter(release__isnull=True))

    def test_a_hold_stands_until_one_release_names_it(self):
        hold = self.hold()
        self.assertEqual(self.active(), [hold])
        release = models.InterpreterHoldRelease.objects.create(hold=hold, released_by=self.operator,
                                                              note='Billing restored on the synthetic project.')
        self.assertEqual(self.active(), [])
        self.assertEqual(models.InterpreterHold.objects.get(pk=hold.pk).release, release)
        with self.assertRaises(IntegrityError), transaction.atomic():
            models.InterpreterHoldRelease.objects.create(hold=hold, released_by=self.operator, note='Again.')
        later = self.hold(reason=models.InterpreterHold.AUTH, http_status=401, vendor_status='UNAUTHENTICATED',
                          violations=[])
        self.assertEqual(self.active(), [later])

    def test_holds_and_releases_refuse_updates_and_deletes(self):
        hold = self.hold()
        release = models.InterpreterHoldRelease.objects.create(hold=hold, released_by=self.operator, note='Released.')
        for row, field, value in ((hold, 'reason', models.InterpreterHold.AUTH), (release, 'note', 'Rewritten.')):
            with self.subTest(type(row).__name__):
                setattr(row, field, value)
                with self.assertRaises(ValidationError):
                    row.save()
                with self.assertRaises(ValidationError):
                    row.delete()
                with self.assertRaises(ValidationError):
                    type(row).objects.filter(pk=row.pk).update(**{field: value})
                with self.assertRaises(ValidationError):
                    type(row).objects.filter(pk=row.pk).delete()
        self.assertEqual(models.InterpreterHold.objects.get(pk=hold.pk).reason, models.InterpreterHold.QUOTA)
        self.assertEqual(models.InterpreterHoldRelease.objects.get(pk=release.pk).note, 'Released.')

    # The three below delete a parent through its own delete(). ProviderRun and User are plain models, and the cascade
    # any on_delete but PROTECT would run removes a hold row with a raw batch delete that ImmutableModel never sees.

    def test_a_run_cannot_be_deleted_from_under_the_hold_it_set(self):
        # a standing hold: its run's deletion would otherwise end the installation-wide pause with no release recorded,
        # and the next interpret stage would send again
        standing = self.hold()
        with self.assertRaises(ProtectedError) as refused, transaction.atomic():
            self.run.delete()
        self.assertEqual(set(refused.exception.protected_objects), {standing})
        self.assertTrue(models.ProviderRun.objects.filter(pk=self.run.pk).exists())
        self.assertEqual(self.active(), [standing])

    def test_a_released_hold_cannot_be_deleted_even_past_the_immutable_manager(self):
        hold = self.hold()
        release = models.InterpreterHoldRelease.objects.create(hold=hold, released_by=self.operator, note='Released.')
        with self.assertRaises(ProtectedError) as refused, transaction.atomic():
            django_models.QuerySet(models.InterpreterHold).filter(pk=hold.pk).delete()
        self.assertEqual(set(refused.exception.protected_objects), {release})
        self.assertEqual(models.InterpreterHold.objects.get(pk=hold.pk).release, release)

    def test_the_operator_who_released_a_hold_cannot_be_deleted(self):
        # the operator's deletion would otherwise delete the release and so stand the hold again: interpretation paused
        # once more, with no record why
        hold = self.hold()
        release = models.InterpreterHoldRelease.objects.create(hold=hold, released_by=self.operator, note='Released.')
        with self.assertRaises(ProtectedError) as refused, transaction.atomic():
            self.operator.delete()
        self.assertEqual(set(refused.exception.protected_objects), {release})
        self.assertTrue(models.User.objects.filter(pk=self.operator.pk).exists())
        self.assertEqual(models.InterpreterHoldRelease.objects.get(pk=release.pk).released_by, self.operator)
        self.assertEqual(self.active(), [])

    def test_a_hold_names_its_run_and_needs_no_status_body(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            models.InterpreterHold.objects.create(reason=models.InterpreterHold.AUTH, http_status=401)
        bare = models.InterpreterHold.objects.create(reason=models.InterpreterHold.MODEL, run=self.run)
        stored = models.InterpreterHold.objects.get(pk=bare.pk)
        self.assertEqual((stored.http_status, stored.vendor_status, stored.violations), (None, '', []))
        self.assertEqual(list(self.run.interpreter_holds.all()), [stored])
