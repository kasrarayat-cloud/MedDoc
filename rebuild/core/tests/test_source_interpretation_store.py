"""Exact lineage, retained transport, and database append-only boundaries."""
from copy import deepcopy
from datetime import date
from decimal import Decimal
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace as N
from unittest.mock import MagicMock, patch
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.db import DatabaseError, connection, transaction
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from core import ai_stages, source_assertion_generation as generation, source_assertion_graph as graph
from core import source_interpretation_store as store
from core.models import Department, Encounter, Job, Organization, Patient, SourceInterpretation, Template, TemplateVersion, User
from documents.component_contracts import fixture
from documents.semantic_preparation_roles import default_definitions


def form():
    field = {'key': 'summary', 'label': 'Clinical summary', 'kind': 'text', 'locator': {'cell': 0}}
    definition = default_definitions([field])['summary']
    definition.update(version=4, answer_mode='narrative', patient_name_requirement='none')
    definition['component_contract'] = fixture(field, definition)
    return [field], {'summary': definition}


class InterpretationStoreTests(SimpleTestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(); self.addCleanup(directory.cleanup)
        setting = override_settings(MEDIA_ROOT=Path(directory.name)); setting.enable(); self.addCleanup(setting.disable)
        fields, self.definitions = form()
        dept = uuid4(); patient = N(pk=uuid4(), department_id=dept, display_name='Synthetic Ada Lane', reference='')
        template = N(department_id=dept, sha256='a'*64)
        version = N(pk=uuid4(), fields=fields, template=template, prepared_sha256='b'*64)
        self.encounter = e = N(pk=uuid4(), department_id=dept, patient=patient, patient_id=patient.pk,
            template_version=version, template_version_id=version.pk, notes='Synthetic source retained exactly.\r\n',
            service_date=date(2026, 10, 19), status='draft', revision=0, answers={})
        patcher = patch.object(store, '_definitions', return_value=self.definitions)
        patcher.start(); self.addCleanup(patcher.stop)
        self.job = job = N(pk=uuid4(), encounter_id=e.pk, revision=0, kind='generation', state='running',
            result_path='', result_sha256='', config={'mode':'fixture'})
        identity = store.identity_for(e, self.definitions, generation_job_id=str(job.pk))
        job.config.update(semantic_fact_scope_contract=graph.CONTRACT,
            semantic_template_version=str(version.pk), semantic_source_sha256=graph.source_digest(e.notes),
            semantic_definitions_sha256=graph.digest(self.definitions),
            semantic_encounter_binding={k:v for k,v in identity.items() if k!='generation_job_id'})
        self.rows = []; self.requests = []
        def send(role, attempt, payload, schema, instructions):
            output = generation.fixture_stage(role, payload)
            limit, _ = ai_stages.generation_limits(job.config)
            request = {'protocol':ai_stages.PROTOCOL, 'stage':role, 'attempt':attempt, 'payload':payload,
                'schema':schema, 'instructions':instructions, 'max_output_tokens':limit}
            self.requests.append(deepcopy(request))
            request_path, request_sha = ai_stages.retain(request)
            result_path, result_sha = ai_stages.retain({'simulated':True, 'output':output})
            now = timezone.now()
            self.rows.append(N(pk=uuid4(), job_id=job.pk, definition_preparation_id=None, stage=role, attempt=attempt,
                state='succeeded', actual_cost=Decimal('0E-12'), config=deepcopy(job.config), started_at=now, finished_at=now,
                request_path=request_path, request_sha256=request_sha, result_path=result_path, result_sha256=result_sha,
                provider='fixture', requested_model='fixture', returned_model='fixture', provider_request_id='',
                provider_resource_id='', simulated=True))
            return output
        output = generation.run(e.notes, fields, self.definitions, send, identity=identity)
        self.interpretation = output['interpretation']; self.answers = output['answers']
        job.ai_stage_receipts = N(order_by=lambda *args: self.rows)
        from core.semantic_generation import CONTRACT
        job.result_path, job.result_sha256 = ai_stages.retain({'contract':CONTRACT, **output,
            'stages':[str(row.pk) for row in self.rows]})
        self.bindings, _ = store._validate(e, job, self.interpretation)
        self.manifest = store._retained(job, self.interpretation, self.answers)
        self.stored = N(job=job, contract=graph.CONTRACT, interpretation_sha256=self.interpretation['sha256'],
            source_sha256=self.bindings['source_sha256'], bindings=deepcopy(self.bindings),
            interpretation=deepcopy(self.interpretation), stage_receipts=deepcopy(self.manifest))

    def load(self, answer=None):
        self.job.state = 'succeeded'
        with patch.object(SourceInterpretation.objects, 'select_related') as query, \
             patch.object(store, '_current_for_read', side_effect=lambda e: deepcopy(e)):
            query.return_value.get.return_value = self.stored
            result = store.load_for_answer(self.encounter, self.encounter.template_version.fields[0],
                self.definitions['summary'], answer or self.answers['summary'])
            self.assertEqual(query.return_value.get.call_args.kwargs,
                {'job_id':self.job.pk, 'encounter_id':self.encounter.pk})
            return result

    def test_exact_three_stage_lineage_round_trip_without_provider(self):
        self.assertEqual(len(self.manifest), 3)
        self.assertEqual(self.load(), self.interpretation)
        self.assertEqual(self.answers['summary']['source_interpretation'], {
            'generation_job_id':str(self.job.pk), 'interpretation_sha256':self.interpretation['sha256']})

    def transport_lineage(self, *, marked=True, marker=ai_stages.ANTHROPIC_SCHEMA_TRANSPORT,
                          config_changes=None, provider='anthropic', simulated=False, capacity=False):
        """Write new synthetic receipts; never alter the bytes of an existing receipt."""
        outputs = [store._output(store._read(row.result_path, row.result_sha256), row) for row in self.rows]
        config = {**self.job.config, 'mode': 'live', 'provider': 'anthropic', 'model': 'synthetic-model'}
        if capacity:
            config.update(semantic_capacity_profile=ai_stages.GENERATION_CAPACITY_PROFILE,
                semantic_output_token_limit=16000, semantic_timeout_seconds=120)
        else:
            for key in ('semantic_capacity_profile', 'semantic_output_token_limit', 'semantic_timeout_seconds'):
                config.pop(key, None)
        config.update(config_changes or {})
        self.job.config = config
        limit, timeout = ai_stages.generation_limits(config)
        for row, original, output in zip(self.rows, self.requests, outputs):
            request = deepcopy(original); request['max_output_tokens'] = limit
            if capacity:
                request['timeout_seconds'] = timeout
            if marked:
                request['schema_transport'] = marker
            row.config = deepcopy(config); row.provider = provider; row.simulated = simulated
            row.requested_model = row.returned_model = 'synthetic-model'
            row.provider_request_id = 'req_' + str(row.pk); row.provider_resource_id = 'msg_' + str(row.pk)
            if simulated:
                wrapper = {'simulated': True, 'output': output}
            else:
                response = ({'content': [{'type': 'text', 'text': json.dumps(output)}]} if provider == 'anthropic'
                    else {'output': [{'content': [{'type': 'output_text', 'text': json.dumps(output)}]}]})
                wrapper = {'provider_output': response, 'provider_request_id': row.provider_request_id,
                    'provider_resource_id': row.provider_resource_id, 'returned_model': row.returned_model}
            row.request_path, row.request_sha256 = ai_stages.retain(request)
            row.result_path, row.result_sha256 = ai_stages.retain(wrapper)
        return [(row.request_path, row.request_sha256, store.private_path(row.request_path).read_bytes()) for row in self.rows]

    def assert_request_bytes_unchanged(self, snapshots):
        for path, expected_hash, raw in snapshots:
            self.assertEqual(store.private_path(path).read_bytes(), raw)
            self.assertEqual(store._read(path, expected_hash), json.loads(raw))

    def test_historical_and_shared_live_lineage_reload_without_rewriting_receipts(self):
        for marked in (False, True):
            for capacity in (False, True):
                with self.subTest(marked=marked, capacity=capacity):
                    snapshots = self.transport_lineage(marked=marked, capacity=capacity)
                    self.bindings, _ = store._validate(self.encounter, self.job, self.interpretation)
                    self.manifest = store._retained(self.job, self.interpretation, self.answers)
                    self.stored.bindings = deepcopy(self.bindings)
                    self.stored.stage_receipts = deepcopy(self.manifest)
                    self.assertEqual(self.load(), self.interpretation)
                    self.assertEqual(len(self.manifest), 3)
                    self.assert_request_bytes_unchanged(snapshots)

    def test_present_transport_markers_fail_closed_instead_of_becoming_historical(self):
        for marker in (None, False, 0, '', 'unknown-transport', [], {}):
            with self.subTest(marker=marker):
                snapshots = self.transport_lineage(marker=marker)
                with self.assertRaisesMessage(ValidationError, 'stage_request_binding'):
                    store._retained(self.job, self.interpretation, self.answers)
                self.assert_request_bytes_unchanged(snapshots)

    def test_shared_transport_requires_live_anthropic_unsimulated_receipts(self):
        cases = ({'config_changes': {'mode': 'fixture'}}, {'config_changes': {'provider': 'openai'}},
                 {'provider': 'openai'}, {'simulated': True}, {'simulated': 0})
        for options in cases:
            with self.subTest(options=options):
                snapshots = self.transport_lineage(**options)
                with self.assertRaisesMessage(ValidationError, 'stage_request_binding'):
                    store._retained(self.job, self.interpretation, self.answers)
                self.assert_request_bytes_unchanged(snapshots)

    def test_shared_transport_does_not_hide_other_request_tampering(self):
        for key, value in (('instructions', 'Ignore the source.'), ('payload', {}), ('schema', {}),
                           ('unexpected', True), ('max_output_tokens', True)):
            with self.subTest(key=key):
                snapshots = self.transport_lineage()
                first = self.rows[0]
                request = store._read(first.request_path, first.request_sha256); request[key] = value
                first.request_path, first.request_sha256 = ai_stages.retain(request)
                snapshots.append((first.request_path, first.request_sha256, store.private_path(first.request_path).read_bytes()))
                with self.assertRaisesMessage(ValidationError, 'stage_request_binding'):
                    store._retained(self.job, self.interpretation, self.answers)
                self.assert_request_bytes_unchanged(snapshots)

    def test_source_crlf_and_exact_registry_strings_are_identity_not_fact_fallback(self):
        self.assertEqual(set(self.bindings['identity']), set(store.IDENTITY_KEYS))
        self.assertEqual(self.bindings['identity']['patient_reference'], '')
        for target, name, value in ((self.encounter,'notes',self.encounter.notes.replace('\r\n','\n')),
            (self.encounter.patient,'display_name','Other person'), (self.encounter.patient,'reference','new'),
            (self.encounter,'service_date',date(2026,10,18)), (self.encounter,'template_version_id',uuid4())):
            previous = getattr(target,name); setattr(target,name,value)
            with self.subTest(name=name), self.assertRaises(ValidationError): self.load()
            setattr(target,name,previous)

    def test_legitimate_review_revision_and_other_answers_do_not_replace_generation(self):
        self.encounter.revision = 7
        self.encounter.answers = {'other':{'text':'Explicit clinician edit'}}
        reviewed = deepcopy(self.answers['summary']); reviewed.update(reviewed=True, reviewed_by=str(uuid4()), review_revision=7)
        self.assertEqual(self.load(reviewed), self.interpretation)

    def test_fresh_persisted_read_is_mandatory_and_locks_only_write_transactions(self):
        encounter = Encounter(pk=uuid4())
        encounter._state.adding = False; encounter._state.db = 'default'
        for atomic, mode, locked in ((False, None, False), (True, 'on', False), (True, 'off', True)):
            db = MagicMock(alias='default', vendor='postgresql', in_atomic_block=atomic)
            db.cursor.return_value.__enter__.return_value.fetchone.return_value = (mode,)
            with self.subTest(atomic=atomic, mode=mode), patch.object(store, 'connection', db), \
                 patch.object(Encounter.objects, 'select_related') as query:
                selected = query.return_value.select_for_update.return_value if locked else query.return_value
                selected.get.return_value = self.encounter
                self.assertIs(store._current_for_read(encounter), self.encounter)
                self.assertEqual(query.return_value.select_for_update.called, locked)
                if locked:
                    query.return_value.select_for_update.assert_called_once_with(
                        of=('self','patient','template_version','template_version__template'))
                if atomic:
                    db.cursor.return_value.__enter__.return_value.execute.assert_called_once_with('SHOW transaction_read_only')
                else:
                    db.cursor.assert_not_called()
        with self.assertRaisesMessage(ValidationError, 'persisted_encounter'):
            store._current_for_read(self.encounter)
        with self.assertRaisesMessage(ValidationError, 'persisted_encounter'):
            store._current_for_read(Encounter(pk=uuid4()))

    def test_stale_caller_source_does_not_replace_fresh_persisted_bindings(self):
        current = deepcopy(self.encounter)
        self.encounter.notes += ' Unsaved source.'
        self.job.state = 'succeeded'
        with patch.object(SourceInterpretation.objects, 'select_related') as query, \
             patch.object(store, '_current_for_read', return_value=current):
            query.return_value.get.return_value = self.stored
            with self.assertRaises(ValidationError):
                store.load_for_answer(self.encounter, current.template_version.fields[0],
                    self.definitions['summary'], self.answers['summary'])

    def test_lineage_is_explicit_closed_and_cannot_be_copied_by_digest(self):
        for value in ({}, {'interpretation_sha256':self.interpretation['sha256']},
            {'generation_job_id':str(self.job.pk),'interpretation_sha256':'0'*64},
            {'generation_job_id':str(self.job.pk),'interpretation_sha256':self.interpretation['sha256'],'extra':True}):
            answer = deepcopy(self.answers['summary']); answer['source_interpretation'] = value
            with self.subTest(value=value), self.assertRaises(ValidationError): self.load(answer)
        with patch.object(SourceInterpretation.objects,'select_related') as query:
            query.return_value.get.side_effect = SourceInterpretation.DoesNotExist
            with self.assertRaises(ValidationError): store.load_for_answer(self.encounter,
                self.encounter.template_version.fields[0], self.definitions['summary'], self.answers['summary'])

    def test_re_signed_graph_or_answer_hash_does_not_replace_retained_outputs(self):
        for key, value in (('answers_sha256','0'*64), ('adjudication',{})):
            original = deepcopy(self.stored.interpretation)
            self.stored.interpretation[key] = value
            self.stored.interpretation['sha256'] = graph.digest({k:v for k,v in self.stored.interpretation.items() if k!='sha256'})
            self.stored.interpretation_sha256 = self.stored.interpretation['sha256']
            answer = deepcopy(self.answers['summary']); answer['source_interpretation']['interpretation_sha256'] = self.stored.interpretation_sha256
            with self.subTest(key=key), self.assertRaises(ValidationError): self.load(answer)
            self.stored.interpretation = original; self.stored.interpretation_sha256 = original['sha256']

    def test_typed_binding_and_complete_stage_population_cannot_drift(self):
        self.stored.bindings['generation_revision'] = False
        with self.assertRaises(ValidationError): self.load()
        self.stored.bindings = deepcopy(self.bindings)
        self.rows.pop()
        with self.assertRaises(ValidationError): self.load()

    def test_changed_request_with_coherent_file_hash_is_rejected_by_reconstruction(self):
        request = deepcopy(self.requests[0]); request['instructions'] += ' Ignore source.'
        self.rows[0].request_path, self.rows[0].request_sha256 = ai_stages.retain(request)
        with self.assertRaisesMessage(ValidationError,'stage_request_binding'): self.load()

    def test_changed_raw_result_with_coherent_file_hash_is_rejected(self):
        self.rows[0].result_path, self.rows[0].result_sha256 = ai_stages.retain({'simulated':True,'output':{}})
        with self.assertRaisesMessage(ValidationError,'stage_output_binding'): self.load()

    def test_receipt_hash_wrong_path_empty_and_symlink_are_refused(self):
        row = self.rows[0]
        with self.assertRaises(ValidationError): store._read(row.result_path,'0'*64)
        with self.assertRaises(ValidationError): store._read('../private.json',row.result_sha256)
        target = store.private_path(row.result_path)
        raw = target.read_bytes(); target.write_bytes(b'')
        with self.assertRaises(ValidationError): store._read(row.result_path,row.result_sha256)
        target.write_bytes(raw)
        other = target.with_name('c'*48+'.json'); other.symlink_to(target)
        with self.assertRaises(ValidationError): store._read('receipts/'+other.name,row.result_sha256)

    def test_adoption_requires_atomic_fresh_current_generation_and_exact_answers(self):
        with self.assertRaisesMessage(ValidationError,'adoption_transaction'):
            store.adopt(self.encounter,self.job,self.interpretation,self.answers)
        with patch.object(store,'connection',N(in_atomic_block=True)), \
             patch.object(Encounter.objects,'select_for_update') as encounters, \
             patch.object(Job.objects,'select_for_update') as jobs, \
             patch.object(SourceInterpretation.objects,'filter') as query, \
             patch.object(SourceInterpretation.objects,'create') as create:
            encounters.return_value.select_related.return_value.get.return_value = self.encounter
            jobs.return_value.get.return_value = self.job
            query.return_value.exists.return_value = False
            store.adopt(self.encounter,self.job,self.interpretation,self.answers)
            self.assertEqual(create.call_args.kwargs['stage_receipts'],self.manifest)
            self.encounter.revision = 1
            with self.assertRaisesMessage(ValidationError,'adoption_freshness'):
                store.adopt(self.encounter,self.job,self.interpretation,self.answers)
            self.encounter.revision = 0
            answers = deepcopy(self.answers); answers['summary']['text'] = 'Invented'
            with self.assertRaisesMessage(ValidationError,'adoption_answers'):
                store.adopt(self.encounter,self.job,self.interpretation,answers)
            query.return_value.exists.return_value = True
            with self.assertRaisesMessage(ValidationError,'already_adopted'):
                store.adopt(self.encounter,self.job,self.interpretation,self.answers)


class InterpretationDatabaseGuards(TestCase):
    """Run only in the isolated PostgreSQL test database, never native state."""
    def setUp(self):
        self.user = User.objects.create_user(username='interpretation-unit')
        organization = Organization.objects.create(name='Synthetic interpretation unit')
        department = Department.objects.create(name='Synthetic', organization=organization)
        patient = Patient.objects.create(department=department, display_name='Synthetic', reference='UNIT', created_by=self.user)
        template = Template.objects.create(department=department, name='Synthetic', format='docx',
            original_name='unit.docx', original_path='unit.docx', sha256='a'*64, created_by=self.user)
        version = TemplateVersion.objects.create(template=template, number=1, fields=[], created_by=self.user)
        self.encounter = Encounter.objects.create(department=department, patient=patient, template_version=version,
            created_by=self.user, service_date=date(2026,10,19), notes='Synthetic')
        self.job = Job.objects.create(encounter=self.encounter,user=self.user,request_key='interpretation-unit')
        self.row = SourceInterpretation.objects.create(job=self.job, encounter=self.encounter,
            contract=graph.CONTRACT, interpretation_sha256='a'*64, source_sha256='b'*64)

    def test_queryset_and_raw_update_delete_are_database_refused(self):
        for operation in (lambda: SourceInterpretation.objects.filter(pk=self.row.pk).update(contract='changed'),
                          lambda: SourceInterpretation.objects.filter(pk=self.row.pk).delete()):
            with self.assertRaises(DatabaseError), transaction.atomic(): operation()
        with self.assertRaises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
            cursor.execute('DELETE FROM core_sourceinterpretation WHERE id=%s',[self.row.pk])
        self.assertTrue(SourceInterpretation.objects.filter(pk=self.row.pk).exists())

    def test_single_job_and_protected_parents(self):
        with self.assertRaises(DatabaseError), transaction.atomic():
            SourceInterpretation.objects.create(job=self.job, encounter=self.encounter,
                contract=graph.CONTRACT, interpretation_sha256='c'*64, source_sha256='b'*64)
        from django.db.models.deletion import ProtectedError
        with self.assertRaises(ProtectedError): self.job.delete()
        with self.assertRaises(ProtectedError): self.encounter.delete()

    def test_populated_reverse_refuses_before_trigger_is_removed(self):
        import importlib
        migration = importlib.import_module('core.migrations.0034_source_interpretation')
        with self.assertRaises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
            cursor.execute(migration.REVERSE)
        with connection.cursor() as cursor:
            cursor.execute("SELECT count(*) FROM pg_trigger WHERE tgrelid='core_sourceinterpretation'::regclass AND tgname='source_interpretation_append_only'")
            self.assertEqual(cursor.fetchone()[0],1)

    def test_runtime_grants_are_narrow_when_installed_role_exists(self):
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1 FROM pg_roles WHERE rolname='quillmd_runtime'")
            if not cursor.fetchone(): self.skipTest('Native runtime role does not exist in this isolated test cluster.')
            for privilege in ('SELECT','INSERT','UPDATE','DELETE','TRUNCATE','REFERENCES','TRIGGER'):
                cursor.execute("SELECT has_table_privilege('quillmd_runtime','core_sourceinterpretation',%s)",[privilege])
                self.assertEqual(cursor.fetchone()[0], privilege in ('SELECT','INSERT'))


@override_settings(WORD_PREPARATION_ENABLED=True, AI_MODE='fixture', ADMIN_SITE=False,
    TESTING_AUTHORITY_MODE='', TESTING_AUTHORITY_ID='', TESTING_AUTHORITY_SHA256='',
    STORAGES={'default':{'BACKEND':'django.core.files.storage.FileSystemStorage'},
              'staticfiles':{'BACKEND':'django.contrib.staticfiles.storage.StaticFilesStorage'}})
class InterpretationFreshReadTests(TestCase):
    """Use real fixture generation/adoption, then mutate only the isolated database."""
    def setUp(self):
        from core.tests.test_source_assertion_worker import SourceAssertionWorkerTests
        from core.jobs import enqueue
        SourceAssertionWorkerTests.setUp(self)
        enqueue(self.encounter, self.user)
        SourceAssertionWorkerTests.execute(self)
        self.encounter.refresh_from_db()
        self.encounter.patient.display_name
        self.encounter.template_version.template.sha256
        self.field = self.version.fields[0]
        self.answer = deepcopy(self.encounter.answers[self.field['key']])
        self.validate()

    def validate(self):
        from core import semantic_review
        self.assertEqual(semantic_review.validate_answer(self.encounter, self.field, self.answer), self.answer)

    def test_cached_registry_name_and_reference_cannot_accept_changed_patient(self):
        for key, value in (('display_name','Synthetic Registry Changed'), ('reference','OTHER-REFERENCE')):
            original = getattr(self.patient, key)
            Patient.objects.filter(pk=self.patient.pk).update(**{key:value})
            with self.subTest(key=key), self.assertRaises(ValidationError): self.validate()
            Patient.objects.filter(pk=self.patient.pk).update(**{key:original})
            self.validate()

    def test_cached_template_fields_definitions_and_file_hashes_are_not_authority(self):
        fields = deepcopy(self.version.fields); fields[0]['label'] += ' Changed'
        definitions = deepcopy(self.version.semantic_definitions)
        definitions[self.field['key']]['meaning'] += ' Changed'
        Encounter.objects.filter(pk=self.encounter.pk).update(template_version=self.source)
        with self.assertRaises(ValidationError): self.validate()
        Encounter.objects.filter(pk=self.encounter.pk).update(template_version=self.version)
        self.validate()
        # Existing versions are append-only in PostgreSQL. Caller caches can
        # still be changed, and must not substitute for the persisted version.
        for target, key, value in (
            (self.encounter.template_version,'fields',fields),
            (self.encounter.template_version,'semantic_definitions',definitions),
            (self.encounter.template_version,'prepared_sha256','f'*64),
            (self.encounter.template_version.template,'sha256','e'*64)):
            original = getattr(target,key)
            setattr(target,key,value)
            with self.subTest(key=key), self.assertRaises(ValidationError): self.validate()
            setattr(target,key,original)
            self.validate()

    def test_cached_source_and_service_date_cannot_accept_current_database_changes(self):
        for key, value in (('notes',self.encounter.notes+' Added source.'), ('service_date',date(2026,10,18))):
            original = getattr(self.encounter,key)
            Encounter.objects.filter(pk=self.encounter.pk).update(**{key:value})
            with self.subTest(key=key), self.assertRaises(ValidationError): self.validate()
            Encounter.objects.filter(pk=self.encounter.pk).update(**{key:original})
            self.validate()
        self.encounter.notes += ' Unsaved caller source.'
        with self.assertRaises(ValidationError): self.validate()

    def test_write_transaction_locks_all_binding_rows_and_allows_review_metadata_revision(self):
        from django.test.utils import CaptureQueriesContext
        Encounter.objects.filter(pk=self.encounter.pk).update(revision=7)
        with CaptureQueriesContext(connection) as queries:
            current = store._current_for_read(self.encounter)
        self.assertEqual(current.revision,7)
        locking = [q['sql'] for q in queries if 'FOR UPDATE' in q['sql']]
        self.assertEqual(len(locking),1)
        clause = locking[0].split('FOR UPDATE OF ',1)[1]
        for table in ('core_encounter','core_patient','core_templateversion','core_template'):
            self.assertIn('"'+table+'"',clause)
        self.validate()
