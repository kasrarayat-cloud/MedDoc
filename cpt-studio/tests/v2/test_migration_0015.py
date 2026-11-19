"""Migration 0015 (docs/gemini-migration/FINAL-V2.md 6.3; step 1d of its 8.1), as FINAL-V2 amendment 1 extends it
(docs/gemini-migration/AMENDMENT-1.md, adopted as DECISIONS D208; its section 10's first row, step 1d-A1):
EventInventory.appraisal_run, EncounterContext.earlier_assessment (4.5, A5), and the ProviderHold and
ProviderHoldRelease tables (7.3, A16), and nothing else. Synthetic data only.

What is proved here:
- the installer's own gate (ops/install.py migration_verdict) reads 0015 as additive - two "nullable" columns and two
  new tables - and planted NOT NULL controls on either column are refused by the same gate, so the verdict is not
  vacuous;
- 0015 is two AddField and two CreateModel and nothing else: no existing column changed, no default of any kind on an
  added column, no NOT NULL on an existing table, no backfill, no RunPython or SQL, no constraint or index of its own;
  it is the leaf after 0014, and the models agree with it (makemigrations --check);
- appraisal_run: ForeignKey(ProviderRun, on_delete=PROTECT, null=True, related_name='+'), in the model, in the
  migration and in PostgreSQL (nullable uuid, no default, a foreign key to studio_providerrun, never unique);
- earlier_assessment: ForeignKey(Assessment, on_delete=PROTECT, null=True, blank=True, related_name='+'), likewise
  (nullable uuid, no default, a foreign key to studio_assessment, never unique); it is set at insert and never after
  (the context is immutable), and Assessment gets no reverse accessor for it;
- the unique key (revision, interpretation_version, inventory_version, provider_run) and the version index are
  unchanged, so a refused pass-1 row (appraisal_run NULL) and a read row of a retry are separate keys, and a second read
  row for one pass-1 run and version pair is refused whatever its appraisal run;
- an older release's insert (its models at 0014) leaves both columns NULL, its SELECT still reads a row that sets
  them, and it knows neither provider-hold table;
- PROTECT: a run that is a row's appraisal run, and an assessment that is a context's earlier assessment, cannot be
  deleted;
- ProviderHold and ProviderHoldRelease are shaped like InterpreterHold and InterpreterHoldRelease (A16): append-only;
  installation-wide (no workspace, no encounter); a hold names its provider, reason, HTTP status and run, the provider
  and the reason plain columns with no choices; a hold stands until one release names it, one release per hold; every
  foreign key PROTECT, so neither a run's deletion nor an operator's ends or revives a hold with no release recorded.
"""
from __future__ import annotations

import ast
import hashlib
import io

from django.apps import apps
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import IntegrityError, connection, transaction
from django.db import models as django_models
from django.db.migrations import AddField, CreateModel
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
# what the installer's gate says of 0015, line for line (amendment 1 added the last three)
WHY = ['eventinventory.appraisal_run: nullable',
       'encountercontext.earlier_assessment: nullable',
       'ProviderHold: a new table no older revision reads',
       'ProviderHoldRelease: a new table no older revision reads']
# 0015's operations, in order: (kind, what)
OPERATIONS = [('AddField', 'eventinventory.appraisal_run'), ('AddField', 'encountercontext.earlier_assessment'),
              ('CreateModel', 'ProviderHold'), ('CreateModel', 'ProviderHoldRelease')]
# the two columns 0015 adds to existing tables: (model, field, table, column, the table its foreign key names)
NEW_COLUMNS = (('eventinventory', 'appraisal_run', 'studio_eventinventory', 'appraisal_run_id', 'studio_providerrun'),
               ('encountercontext', 'earlier_assessment', 'studio_encountercontext', 'earlier_assessment_id',
                'studio_assessment'))
HOLD_FIELDS = ('id', 'provider', 'reason', 'http_status', 'run', 'created_at')
RELEASE_FIELDS = ('id', 'hold', 'released_by', 'note', 'created_at')


def loaded_migration():
    """0015 as Django loads it (no database needed)."""
    return MigrationLoader(None, ignore_no_migrations=True).get_migration('studio', NAME)


def added_field(model_name, name):
    """The field 0015's AddField for (model_name, name) adds."""
    (operation,) = [operation for operation in loaded_migration().operations if isinstance(operation, AddField)
                    and (operation.model_name, operation.name) == (model_name, name)]
    return operation.field


def created_fields(model_name):
    """{name: field} of 0015's CreateModel for ``model_name``."""
    (operation,) = [operation for operation in loaded_migration().operations
                    if isinstance(operation, CreateModel) and operation.name == model_name]
    return dict(operation.fields)


def concrete(model):
    """The model's own fields, by name, in declaration order (no reverse relation)."""
    return {field.name: field for field in model._meta.get_fields() if field.concrete}


def shape(field):
    """What a field is, without the model it belongs to or the model a relation names (compared apart)."""
    relation = (field.remote_field.on_delete, field.remote_field.related_name) if field.is_relation else None
    return (type(field), field.null, field.blank, field.max_length, field.primary_key, field.unique,
            field.has_default(), field.db_default is NOT_PROVIDED, bool(field.choices),
            getattr(field, 'auto_now_add', None), relation)


class MigrationGateTests(SimpleTestCase):
    def test_0015_is_read_additive_by_the_installers_gate(self):
        verdict = install_gate().migration_verdict(SOURCE)
        self.assertEqual(verdict, {'safe': True, 'why': WHY})
        verdicts = install_gate().migration_safety(MIGRATIONS)
        self.assertEqual(verdicts[NAME], verdict)
        self.assertTrue(all(found['safe'] for found in verdicts.values()), verdicts)

    def test_control_the_gate_refuses_0015_made_not_null(self):
        # the same file with either column NOT NULL: an older release's insert names no value for it and is refused,
        # so the gate must say so - or the verdict above proves nothing
        for anchor, column in (
                ('field=models.ForeignKey(null=True, ', 'eventinventory.appraisal_run'),
                ('field=models.ForeignKey(blank=True, null=True, ', 'encountercontext.earlier_assessment')):
            with self.subTest(column):
                self.assertEqual(SOURCE.count(anchor), 1)
                found = install_gate().migration_verdict(SOURCE.replace(anchor, anchor.replace('null=True, ', '')))
                # an unsafe verdict names only what is unsafe
                self.assertEqual(found, {'safe': False, 'why': [
                    f"{column}: NOT NULL with no database default, so an older pair's insert is refused"]})
        # the gate reads any nullable column as "nullable", a default or not, so "no default of any kind" (6.3; A5's
        # "no default, no NOT NULL") is read from the file itself: each added field's keywords are exactly these
        keywords: dict[str, list[str]] = {}
        for node in ast.walk(ast.parse(SOURCE)):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == 'AddField'):
                arguments = {keyword.arg: keyword.value for keyword in node.keywords}
                field = arguments['field']
                if isinstance(field, ast.Call):
                    self.assertEqual((node.args, field.args), ([], []))
                    named = sorted(str(keyword.arg) for keyword in field.keywords)
                    keywords[ast.literal_eval(arguments['name'])] = named
                else:
                    self.fail(f'an AddField whose field is not a call: {ast.dump(field)}')
        self.assertEqual(keywords, {'appraisal_run': ['null', 'on_delete', 'related_name', 'to'],
                                    'earlier_assessment': ['blank', 'null', 'on_delete', 'related_name', 'to']})

    def test_0015_adds_two_columns_and_two_tables_and_nothing_else(self):
        migration = loaded_migration()
        self.assertEqual(migration.dependencies, [PREVIOUS])
        self.assertIs(migration.atomic, True)
        shapes = []
        for operation in migration.operations:
            if isinstance(operation, AddField):
                shapes.append(('AddField', f'{operation.model_name}.{operation.name}'))
            elif isinstance(operation, CreateModel):
                shapes.append(('CreateModel', operation.name))
            else:
                self.fail(f'not an operation 0015 may hold: {operation!r}')
        self.assertEqual(shapes, OPERATIONS)
        calls = {node.func.attr for node in ast.walk(ast.parse(SOURCE))
                 if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)}
        # no RunPython, SQL, AlterField, constraint or index: the operations and the field classes of their columns
        self.assertEqual(calls, {'AddField', 'CreateModel', 'ForeignKey', 'OneToOneField', 'UUIDField', 'CharField',
                                 'PositiveIntegerField', 'DateTimeField', 'TextField'})
        leaves = MigrationLoader(None, ignore_no_migrations=True).graph.leaf_nodes('studio')
        self.assertEqual(leaves, [('studio', NAME)])

    def test_the_column_is_exactly_the_designs(self):
        for where, field in (('migration', added_field('eventinventory', 'appraisal_run')),
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

    def test_the_earlier_assessment_column_is_exactly_the_amendments(self):
        # AMENDMENT-1.md 4.5: ForeignKey(Assessment, on_delete=PROTECT, null=True, blank=True, related_name='+'), no
        # default, no NOT NULL
        for where, field in (('migration', added_field('encountercontext', 'earlier_assessment')),
                             ('model', models.EncounterContext._meta.get_field('earlier_assessment'))):
            with self.subTest(where):
                self.assertIsInstance(field, django_models.ForeignKey)
                self.assertEqual(field.remote_field.model if where == 'model' else field.remote_field.model.lower(),
                                 models.Assessment if where == 'model' else 'studio.assessment')
                self.assertIs(field.remote_field.on_delete, PROTECT)
                self.assertIs(field.null, True)
                self.assertIs(field.blank, True)
                self.assertIs(field.has_default(), False)
                self.assertIs(field.db_default, NOT_PROVIDED)
                self.assertIs(field.unique, False)
                self.assertIs(field.db_constraint, True)
                self.assertEqual(field.remote_field.related_name, '+')
        # Assessment gets no reverse accessor for it ('+')
        self.assertFalse([relation for relation in models.Assessment._meta.related_objects
                          if relation.field.name == 'earlier_assessment' and not relation.hidden])
        self.assertEqual([relation.name for relation in models.Assessment._meta.related_objects
                          if relation.related_model is models.EncounterContext and not relation.hidden], [])
        self.assertTrue(issubclass(models.EncounterContext, models.ImmutableModel))  # set at insert, never after

    def test_the_provider_hold_tables_are_shaped_like_the_interpreter_holds(self):
        hold, release = concrete(models.ProviderHold), concrete(models.ProviderHoldRelease)
        self.assertEqual(tuple(hold), HOLD_FIELDS)  # its provider, reason, HTTP status and run (7.3's Shape)
        self.assertEqual(tuple(release), RELEASE_FIELDS)
        for model in (models.ProviderHold, models.ProviderHoldRelease):
            with self.subTest(model.__name__):
                self.assertTrue(issubclass(model, models.ImmutableModel))  # append-only
                self.assertIsInstance(model.objects.all(), models.ImmutableQuerySet)
        # installation-wide: no workspace and no encounter, as InterpreterHold
        self.assertFalse([name for name, field in hold.items() if name in ('workspace', 'encounter')
                          or getattr(field, 'related_model', None) in (models.Workspace, models.Encounter)])
        # every field it shares with InterpreterHold is that field's shape; its provider is a run's provider column
        interpreter = concrete(models.InterpreterHold)
        for name in ('id', 'reason', 'http_status', 'run', 'created_at'):
            with self.subTest(field=name):
                expected = shape(interpreter[name])
                if name == 'run':  # its own reverse accessor, beside InterpreterHold's
                    expected = expected[:-1] + ((PROTECT, 'provider_holds'),)
                self.assertEqual(shape(hold[name]), expected)
        self.assertEqual(shape(hold['provider']), shape(concrete(models.ProviderRun)['provider']))
        self.assertIs(hold['run'].remote_field.model, models.ProviderRun)
        self.assertIs(hold['run'].null, False)  # a hold names the run that set it
        # plain columns with no choices: the classification owns the values, so a new one needs no migration
        self.assertFalse(hold['reason'].choices)
        self.assertFalse(hold['provider'].choices)
        self.assertEqual((models.ProviderHold.AUTH, models.ProviderHold.PERMISSION, models.ProviderHold.QUOTA,
                          models.ProviderHold.REFUSED), ('auth', 'permission', 'quota', 'refused'))
        self.assertTrue(all(len(reason) <= hold['reason'].max_length for reason in (
            models.ProviderHold.AUTH, models.ProviderHold.PERMISSION, models.ProviderHold.QUOTA,
            models.ProviderHold.REFUSED)))
        # the release is InterpreterHoldRelease's shape, field for field, naming a ProviderHold
        interpreter_release = concrete(models.InterpreterHoldRelease)
        self.assertEqual(tuple(interpreter_release), RELEASE_FIELDS)
        for name in RELEASE_FIELDS:
            with self.subTest(release_field=name):
                self.assertEqual(shape(release[name]), shape(interpreter_release[name]))
        self.assertIsInstance(release['hold'], django_models.OneToOneField)  # one release per hold
        self.assertIs(release['hold'].remote_field.model, models.ProviderHold)
        self.assertIs(release['released_by'].remote_field.model, models.User)
        self.assertEqual((models.ProviderHold._meta.ordering, models.ProviderHoldRelease._meta.ordering),
                         (models.InterpreterHold._meta.ordering, models.InterpreterHoldRelease._meta.ordering))
        # every foreign key PROTECT in 0015's CreateModel too, and each names its table
        created = {'ProviderHold': created_fields('ProviderHold'),
                   'ProviderHoldRelease': created_fields('ProviderHoldRelease')}
        self.assertEqual((tuple(created['ProviderHold']), tuple(created['ProviderHoldRelease'])),
                         (('id', 'provider', 'reason', 'http_status', 'created_at', 'run'),
                          ('id', 'note', 'created_at', 'hold', 'released_by')))
        for model_name, name, target in (('ProviderHold', 'run', 'studio.providerrun'),
                                         ('ProviderHoldRelease', 'hold', 'studio.providerhold'),
                                         ('ProviderHoldRelease', 'released_by', 'studio.user')):
            field = created[model_name][name]
            with self.subTest(f'0015 {model_name}.{name}'):
                self.assertIs(field.remote_field.on_delete, PROTECT)
                self.assertIs(field.null, False)
                self.assertEqual(str(field.remote_field.model).lower(), target)
        self.assertFalse(created['ProviderHold']['reason'].choices)
        self.assertFalse(created['ProviderHold']['provider'].choices)

    def test_models_still_import_nothing_but_django_and_the_standard_library(self):
        tree = ast.parse((ROOT / 'studio' / 'models.py').read_text(encoding='utf-8'))
        imported: set[str | None] = set()
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


def refused_run(enc, rev, provider, status, *, sent=True):
    """A synthetic run a provider refused with ``status`` (a Corti token refusal is recorded not sent)."""
    body = {'synthetic': provider, 'status': status}
    return models.ProviderRun.objects.create(
        encounter=enc, revision=rev, provider=provider, adapter_version=f'{provider}@synthetic', purpose='primary',
        request_sha256=sha256_json(body), request_body=body, contexts=[],
        state=models.ProviderRun.FAILED if sent else models.ProviderRun.NOT_SENT, sent=sent, http_status=status,
        started_at=timezone.now(), finished_at=timezone.now())


def inventory(enc, rev, run, *, appraisal_run=None, state=models.EventInventory.READ,
              interpretation_version='gemini-events@2/appraisal@1', inventory_version='gemini-inventory@2'):
    parts = {'events': {}, 'encounter_facts': {}, 'open_questions': [], 'verification': {'refused': state == 'refused'}}
    return models.EventInventory.objects.create(
        encounter=enc, revision=rev, provider_run=run, appraisal_run=appraisal_run,
        interpretation_version=interpretation_version, inventory_version=inventory_version,
        text_sha256=rev.text_sha256, request_sha256=run.request_sha256, response_sha256=run.response_sha256,
        state=state, sha256=sha256_json(parts), **parts)


def context_row(enc, rev, **extra):
    facts = {'service_date': {'value': '2026-11-09', 'origin': 'document', 'evidence': [], 'note': ''}}
    return models.EncounterContext.objects.create(encounter=enc, revision=rev, facts=facts, version='gemini-context@1',
                                                  sha256=sha256_json(facts), **extra)


def assessment_row(enc, rev, ctx):
    result = {'version': 'gemini-routing@1', 'document_kind': '', 'findings': []}
    routing = models.RoutingRun.objects.create(revision=rev, version='gemini-routing@1', result=result,
                                               sha256=sha256_json(result))
    return models.Assessment.objects.create(encounter=enc, revision=rev, context=ctx, routing=routing,
                                            profiles_version='gi-profiles@test', engine_version='cpt-studio-events@2',
                                            sha256='0' * 64)


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

    def test_the_database_columns_are_nullable_foreign_keys_with_no_default(self):
        for _, _, table, column, target in NEW_COLUMNS:
            with self.subTest(column), connection.cursor() as cursor:
                cursor.execute('SELECT is_nullable, column_default, data_type FROM information_schema.columns '
                               'WHERE table_schema = current_schema() AND table_name = %s AND column_name = %s',
                               [table, column])
                self.assertEqual(cursor.fetchall(), [('YES', None, 'uuid')])
                found = connection.introspection.get_constraints(cursor, table)
                on_column = [item for item in found.values() if item['columns'] == [column]]
                self.assertIn((target, 'id'), [item['foreign_key'] for item in on_column])
                self.assertFalse([item for item in on_column if item['unique']])
        with connection.cursor() as cursor:
            found = connection.introspection.get_constraints(cursor, models.EventInventory._meta.db_table)
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

    def test_an_older_releases_context_leaves_the_earlier_assessment_null_and_reads_one_that_names_it(self):
        # the previous release's models (its migration state at 0014) know no such column, so the INSERT they issue
        # names none of it - what the rollback image writes after a switch-back (AMENDMENT-1.md 4.5, 9.4)
        old = MigrationLoader(connection).project_state(PREVIOUS).apps
        OldContext = old.get_model('studio', 'EncounterContext')
        self.assertNotIn('earlier_assessment', {field.name for field in OldContext._meta.concrete_fields})
        facts = {'service_date': {'value': '2026-11-09', 'origin': 'document', 'evidence': [], 'note': ''}}
        older = OldContext.objects.create(encounter_id=self.enc.pk, revision_id=self.rev.pk, facts=facts,
                                          version='gi-context@5', sha256=sha256_json(facts))
        self.assertIsNone(models.EncounterContext.objects.get(pk=older.pk).earlier_assessment_id)
        with connection.cursor() as cursor:  # NULL in the database itself
            cursor.execute('SELECT earlier_assessment_id IS NULL FROM studio_encountercontext WHERE id = %s',
                           [older.pk])
            self.assertEqual(cursor.fetchone(), (True,))
        # this release's context naming the earlier codes is still read by the previous release's SELECT
        shown = assessment_row(self.enc, self.rev, models.EncounterContext.objects.get(pk=older.pk))
        newer = context_row(self.enc, self.rev, earlier_assessment=shown)
        self.assertEqual(OldContext.objects.get(pk=newer.pk).sha256, newer.sha256)
        # and it knows neither provider-hold table (A16's tables are 0015's)
        for name in ('ProviderHold', 'ProviderHoldRelease'):
            with self.subTest(name), self.assertRaises(LookupError):
                old.get_model('studio', name)

    def test_a_context_names_its_earlier_assessment_at_insert_and_never_after(self):
        first = context_row(self.enc, self.rev)  # a first processing: nothing shown yet
        self.assertIsNone(first.earlier_assessment_id)
        shown = assessment_row(self.enc, self.rev, first)
        later = context_row(self.enc, self.rev, earlier_assessment=shown)  # a save after the codes were shown
        stored = models.EncounterContext.objects.get(pk=later.pk)
        self.assertEqual(stored.earlier_assessment, shown)
        # the context is immutable: the earlier codes cannot be named, renamed or cleared after the insert
        other = assessment_row(self.enc, self.rev, later)
        for row, value in ((first, shown), (stored, other), (stored, None)):
            with self.subTest(context=row.pk, value=getattr(value, 'pk', None)):
                row.earlier_assessment = value
                with self.assertRaises(ValidationError):
                    row.save()
                with self.assertRaises(ValidationError):
                    models.EncounterContext.objects.filter(pk=row.pk).update(earlier_assessment=value)
        self.assertIsNone(models.EncounterContext.objects.get(pk=first.pk).earlier_assessment_id)
        self.assertEqual(models.EncounterContext.objects.get(pk=later.pk).earlier_assessment_id, shown.pk)
        # every context of one update may name the same earlier codes (4.5: rapid saves S1, S2 on a final E)
        again = context_row(self.enc, self.rev, earlier_assessment=shown)
        self.assertEqual(sorted(str(pk) for pk in models.EncounterContext.objects.filter(earlier_assessment=shown)
                                .values_list('pk', flat=True)), sorted([str(later.pk), str(again.pk)]))

    def test_an_earlier_assessment_cannot_be_deleted_from_under_its_context(self):
        made_on = context_row(self.enc, self.rev)
        earlier = assessment_row(self.enc, self.rev, made_on)
        naming = context_row(self.enc, self.rev, earlier_assessment=earlier)
        # past the immutable manager: Assessment's own delete() refuses first, so the raw queryset shows PROTECT
        with self.assertRaises(ProtectedError) as refused, transaction.atomic():
            django_models.QuerySet(models.Assessment).filter(pk=earlier.pk).delete()
        self.assertEqual(set(refused.exception.protected_objects), {naming})
        self.assertTrue(models.Assessment.objects.filter(pk=earlier.pk).exists())
        self.assertEqual(models.EncounterContext.objects.get(pk=naming.pk).earlier_assessment_id, earlier.pk)

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


class ProviderHoldRowTests(TestCase):
    """A16's tables as rows (AMENDMENT-1.md 7.3's Shape). What sets, reads and releases a hold is
    studio.provider_holds' (step 5b) and the provider_hold command's (step 6b); here only what the tables guarantee."""

    def setUp(self):
        self.ws = f.workspace()
        self.usr = f.member(self.ws)
        self.enc = f.encounter(self.ws, self.usr)
        self.rev = f.pasted_revision(self.enc, self.usr, TEXT)
        self.corti = refused_run(self.enc, self.rev, 'corti', 402)
        self.operator = f.user('synthetic-provider-operator')

    def hold(self, run=None, **extra):
        run = run or self.corti
        values = {'provider': run.provider, 'reason': models.ProviderHold.QUOTA, 'http_status': run.http_status,
                  'run': run}
        return models.ProviderHold.objects.create(**{**values, **extra})

    def standing(self, provider=None):
        rows = models.ProviderHold.objects.filter(release__isnull=True)
        return list(rows.filter(provider=provider) if provider else rows)

    def test_a_hold_stands_until_one_release_names_it(self):
        hold = self.hold()
        astra = self.hold(refused_run(self.enc, self.rev, 'astra', 400), reason=models.ProviderHold.REFUSED)
        self.assertEqual(self.standing(), [hold, astra])
        self.assertEqual((self.standing('corti'), self.standing('astra'), self.standing('fable')),
                         ([hold], [astra], []))
        release = models.ProviderHoldRelease.objects.create(hold=hold, released_by=self.operator,
                                                            note='The synthetic payment was restored.')
        self.assertEqual((self.standing('corti'), self.standing('astra')), ([], [astra]))  # per provider
        self.assertEqual(models.ProviderHold.objects.get(pk=hold.pk).release, release)
        with self.assertRaises(IntegrityError), transaction.atomic():  # one release per hold
            models.ProviderHoldRelease.objects.create(hold=hold, released_by=self.operator, note='Again.')
        later = self.hold(refused_run(self.enc, self.rev, 'corti', 401), reason=models.ProviderHold.AUTH,
                          http_status=401)
        self.assertEqual(self.standing('corti'), [later])  # a refusal after the release sets a new hold
        self.assertEqual(list(self.corti.provider_holds.all()), [hold])

    def test_holds_and_releases_refuse_updates_and_deletes(self):
        hold = self.hold()
        release = models.ProviderHoldRelease.objects.create(hold=hold, released_by=self.operator, note='Released.')
        for row, field, value in ((hold, 'reason', models.ProviderHold.AUTH), (hold, 'provider', 'fable'),
                                  (release, 'note', 'Rewritten.')):
            with self.subTest(f'{type(row).__name__}.{field}'):
                setattr(row, field, value)
                with self.assertRaises(ValidationError):
                    row.save()
                with self.assertRaises(ValidationError):
                    row.delete()
                with self.assertRaises(ValidationError):
                    type(row).objects.filter(pk=row.pk).update(**{field: value})
                with self.assertRaises(ValidationError):
                    type(row).objects.filter(pk=row.pk).delete()
        stored = models.ProviderHold.objects.get(pk=hold.pk)
        self.assertEqual((stored.provider, stored.reason, stored.http_status, stored.run_id),
                         ('corti', models.ProviderHold.QUOTA, 402, self.corti.pk))
        self.assertEqual(models.ProviderHoldRelease.objects.get(pk=release.pk).note, 'Released.')

    # The three below delete a parent through its own delete(). ProviderRun and User are plain models, and the cascade
    # any on_delete but PROTECT would run removes a hold row with a raw batch delete that ImmutableModel never sees.

    def test_a_run_cannot_be_deleted_from_under_the_provider_hold_it_set(self):
        # a standing hold: its run's deletion would otherwise end the installation-wide hold with no release recorded,
        # and every encounter's next request of that provider would be sent
        standing = self.hold()
        with self.assertRaises(ProtectedError) as refused, transaction.atomic():
            self.corti.delete()
        self.assertEqual(set(refused.exception.protected_objects), {standing})
        self.assertTrue(models.ProviderRun.objects.filter(pk=self.corti.pk).exists())
        self.assertEqual(self.standing(), [standing])

    def test_a_released_provider_hold_cannot_be_deleted_even_past_the_immutable_manager(self):
        hold = self.hold()
        release = models.ProviderHoldRelease.objects.create(hold=hold, released_by=self.operator, note='Released.')
        with self.assertRaises(ProtectedError) as refused, transaction.atomic():
            django_models.QuerySet(models.ProviderHold).filter(pk=hold.pk).delete()
        self.assertEqual(set(refused.exception.protected_objects), {release})
        self.assertEqual(models.ProviderHold.objects.get(pk=hold.pk).release, release)

    def test_the_operator_who_released_a_provider_hold_cannot_be_deleted(self):
        # the operator's deletion would otherwise delete the release and so stand the hold again, with no record why
        hold = self.hold()
        release = models.ProviderHoldRelease.objects.create(hold=hold, released_by=self.operator, note='Released.')
        with self.assertRaises(ProtectedError) as refused, transaction.atomic():
            self.operator.delete()
        self.assertEqual(set(refused.exception.protected_objects), {release})
        self.assertTrue(models.User.objects.filter(pk=self.operator.pk).exists())
        self.assertEqual(self.standing(), [])

    def test_a_provider_hold_names_its_run_and_a_token_refusals_run_was_not_sent(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            models.ProviderHold.objects.create(provider='corti', reason=models.ProviderHold.AUTH, http_status=401)
        # Corti's token endpoint refusal: the adapter records the status on its not-sent run, and the hold names it
        token = refused_run(self.enc, self.rev, 'corti', 403, sent=False)
        hold = self.hold(token, reason=models.ProviderHold.PERMISSION)
        stored = models.ProviderHold.objects.get(pk=hold.pk)
        self.assertEqual((stored.run.sent, stored.run.state, stored.http_status), (False, 'not_sent', 403))
        # the status is the run's, recorded beside it; the table needs none (shaped like InterpreterHold)
        bare = models.ProviderHold.objects.create(provider='fable', reason=models.ProviderHold.REFUSED,
                                                  run=refused_run(self.enc, self.rev, 'fable', 400))
        self.assertIsNone(models.ProviderHold.objects.get(pk=bare.pk).http_status)

    def test_the_database_holds_the_tables_as_the_models_say(self):
        expected = {
            'studio_providerhold': [('created_at', 'NO', 'timestamp with time zone'), ('http_status', 'YES', 'integer'),
                                    ('id', 'NO', 'uuid'), ('provider', 'NO', 'character varying'),
                                    ('reason', 'NO', 'character varying'), ('run_id', 'NO', 'uuid')],
            'studio_providerholdrelease': [('created_at', 'NO', 'timestamp with time zone'), ('hold_id', 'NO', 'uuid'),
                                           ('id', 'NO', 'uuid'), ('note', 'NO', 'text'),
                                           ('released_by_id', 'NO', 'uuid')]}
        for table, columns in expected.items():
            with self.subTest(table), connection.cursor() as cursor:
                cursor.execute('SELECT column_name, is_nullable, data_type, column_default '
                               'FROM information_schema.columns WHERE table_schema = current_schema() '
                               'AND table_name = %s ORDER BY column_name', [table])
                rows = cursor.fetchall()
                self.assertEqual([row[:3] for row in rows], columns)
                self.assertEqual({row[3] for row in rows}, {None})  # no database default anywhere
        with connection.cursor() as cursor:
            hold = connection.introspection.get_constraints(cursor, 'studio_providerhold')
            release = connection.introspection.get_constraints(cursor, 'studio_providerholdrelease')
        self.assertEqual({tuple(item['columns']): item['foreign_key'] for item in hold.values() if item['foreign_key']},
                         {('run_id',): ('studio_providerrun', 'id')})
        self.assertFalse([item for item in hold.values() if item['unique'] and item['columns'] != ['id']])
        self.assertEqual({tuple(item['columns']): item['foreign_key'] for item in release.values()
                          if item['foreign_key']},
                         {('hold_id',): ('studio_providerhold', 'id'), ('released_by_id',): ('studio_user', 'id')})
        self.assertTrue([item for item in release.values() if item['unique'] and item['columns'] == ['hold_id']])
        lengths = {name: models.ProviderHold._meta.get_field(name).max_length for name in ('provider', 'reason')}
        with connection.cursor() as cursor:
            cursor.execute('SELECT column_name, character_maximum_length FROM information_schema.columns '
                           "WHERE table_schema = current_schema() AND table_name = 'studio_providerhold' "
                           "AND column_name IN ('provider', 'reason') ORDER BY column_name")
            self.assertEqual(dict(cursor.fetchall()), lengths)
