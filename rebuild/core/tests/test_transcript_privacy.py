"""Immutable synthetic transcript evidence is visible to custody tools and never falsely redacted."""
import hashlib
import importlib
import json
import threading
import uuid
from unittest.mock import patch

from django.apps import apps
from django.core.exceptions import ValidationError
from django.db import DatabaseError, connection, transaction
from django.db.migrations.exceptions import IrreversibleError
from django.db.migrations.executor import MigrationExecutor
from django.db.migrations.recorder import MigrationRecorder
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone

from core import disposition as d, models as m, redaction, retention, retention_readiness as readiness
from core.tests.test_redaction import RedactionFixture, REASON
from core.tests.test_retention_flow_locks import in_thread, wait_for_blocked_backend
from core.tests.test_retention_preservation import ISOLATED
from core.tests.test_word_v3_workflow import V3, V3Fixture, build_questionnaire
from core.tests.test_security import SyntheticFixture


class TranscriptFixture(RedactionFixture):
    def setup_transcript(self):
        self.setup_journal()
        self.row=self.scope[5]
        self.job=m.Job.objects.create(encounter=self.row,user=self.scope[0],kind='transcription',state='succeeded',
            request_key=str(uuid.uuid4()),config={'transcript_review_required':True},result_sha256='b'*64)

    def review_values(self):
        text=self.row.notes
        return dict(encounter=self.row,job=self.job,reviewed_by=self.scope[0],source_revision=self.row.revision,
            source_sha256=hashlib.sha256(text.encode()).hexdigest(),raw_sha256='a'*64,result_sha256=self.job.result_sha256,
            reviewed_sha256=hashlib.sha256(text.encode()).hexdigest(),reviewed_text=text,span_start=0,span_end=len(text),
            patient_context=False,context_token='')

    def finish(self,*threads):
        for thread in threads:
            thread.join(20)
            self.assertFalse(thread.is_alive(),'bounded synthetic preservation race did not finish')


@override_settings(**ISOLATED)
class TranscriptPrivacy(TranscriptFixture,TestCase):
    def setUp(self):
        self.setup_transcript()
        self.review=m.TranscriptReview.objects.create(**self.review_values())

    def test_review_content_blocks_actual_redaction_and_direct_sql_tombstone(self):
        before=list(m.TranscriptReview.objects.values())
        self.assertIn('transcript_review_content',redaction.refusals(self.row))
        with self.assertRaisesMessage(ValidationError,'transcript_review_content'):
            redaction.request(self.admin,self.row.pk,REASON,uuid.uuid4())
        body={'id':str(uuid.uuid4()),'target_id':str(self.row.pk),'department_id':str(self.row.department_id),
            'request_id':str(uuid.uuid4()),'content_sha256':'e'*64,'files':[],
            'requested_by':str(self.admin.pk),'approved_by':str(self.second.pk)}
        entry={'key_id':'writer','signature':'0'*128,'body':{'contract':'redaction-journal-entry-v1','redaction':body}}
        with self.assertRaisesMessage(DatabaseError,'Immutable transcript review keeps clinical content'),transaction.atomic():
            m.RedactionTombstone.objects.create(id=body['id'],target_id=self.row.pk,department_id=self.row.department_id,
                request_id=body['request_id'],content_sha256='e'*64,files=[],journal_entry=entry,entry_sha256='f'*64)
        self.assertEqual(list(m.TranscriptReview.objects.values()),before)
        self.assertFalse(m.RedactionTombstone.objects.exists())
        self.assertFalse(m.RedactionRequest.objects.exists())
        self.row.refresh_from_db()
        self.assertEqual(self.row.notes,self.review.reviewed_text)
        # Authorized unreviewed documents still have the existing explicit two-custodian redaction route.
        self.assertEqual(self.redact(self.other[5])[1].target_id,self.other[5].pk)

    def test_graph_and_readiness_include_only_hashes_and_protected_counts(self):
        request=d.submit(self.admin,self.row.department_id,'encounter',self.row.pk,'c'*64,uuid.uuid4())
        report=d.prepare(self.admin,request.pk).graph
        self.assertEqual(report['nodes']['TranscriptReview'][0]['id'],str(self.review.pk))
        self.assertIn('transcript_review_content',report['blockers'])
        self.assertIn('immutable_evidence',report['blockers'])
        self.assertFalse(report['deletion_authorized'])
        self.assertNotIn(self.review.reviewed_text,json.dumps(report))
        policy=readiness.parse_policy(json.dumps(readiness.unresolved_policy()).encode())
        count=readiness.count_class('reviewed_transcripts',policy.classes['reviewed_transcripts'],timezone.now())
        self.assertEqual(count['records'],1)
        self.assertTrue(count['protected_by_this_tool'])
        self.assertIsNone(count['deletion_eligible_count'])
        self.assertNotIn(self.review.reviewed_text,json.dumps(count))
        forbidden=readiness.unresolved_policy()
        forbidden['schedule_document_sha256']='d'*64
        forbidden['classes']['reviewed_transcripts']={'mode':'review_window','anchor':'created_at','days':1}
        with self.assertRaises(readiness.PolicyError):readiness.parse_policy(json.dumps(forbidden).encode())

    def test_every_hold_scope_keeps_exact_immutable_transcript_rows(self):
        before=list(m.TranscriptReview.objects.values())
        targets=[('encounter',self.row.pk),('patient',self.row.patient_id),('department',self.row.department_id),
                 ('organization',self.scope[1].pk),('global',None)]
        for scope,target in targets:
            with self.subTest(scope=scope):
                retention.create_hold(self.admin,scope,target,'c'*64,uuid.uuid4())
                self.assertTrue(retention.active_holds(encounter_id=self.row.pk).exists())
                for action in (lambda:m.TranscriptReview.objects.filter(pk=self.review.pk).update(reviewed_text='SYNTHETIC REPLACED'),
                               lambda:m.TranscriptReview.objects.filter(pk=self.review.pk).delete()):
                    with self.assertRaises(DatabaseError),transaction.atomic():action()
                self.assertEqual(list(m.TranscriptReview.objects.values()),before)
        with self.assertRaises(DatabaseError),transaction.atomic(),connection.cursor() as cursor:
            cursor.execute('TRUNCATE core_transcriptreview CASCADE')
        self.assertEqual(list(m.TranscriptReview.objects.values()),before)

    def test_review_evidence_refuses_schema_reversal_before_guards_are_removed(self):
        for name in ('0036_transcript_review','0037_transcript_redaction_boundary'):
            with self.subTest(name=name),self.assertRaises(IrreversibleError):
                importlib.import_module('core.migrations.'+name).refuse_evidence(apps,None)

    def test_release_contract_detects_review_guard_disable_and_redaction_guard_replacement(self):
        from ops import integrity_contract
        def report():
            with connection.cursor() as cursor:
                cursor.execute(integrity_contract.CATALOG);rows=cursor.fetchall()
                cursor.execute(integrity_contract.CONTEXT);context=cursor.fetchall()
            return integrity_contract.assess(rows,context,len(integrity_contract.GUARDS))
        self.assertTrue(report()['passed'])
        # TestCase keeps the review INSERT open; validate deferred FK events before this deliberate DDL mutation.
        with connection.cursor() as cursor:cursor.execute('SET CONSTRAINTS ALL IMMEDIATE')
        for sql in (
            'ALTER TABLE core_transcriptreview DISABLE TRIGGER transcript_review_preservation',
            'CREATE OR REPLACE FUNCTION quillmd_transcript_redaction_guard() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RETURN NEW; END; $$;',
        ):
            with self.subTest(sql=sql),transaction.atomic():
                with connection.cursor() as cursor:cursor.execute(sql)
                self.assertFalse(report()['passed'])
                transaction.set_rollback(True)
        self.assertTrue(report()['passed'])


@override_settings(**ISOLATED)
class TranscriptHoldSerialization(TranscriptFixture,TransactionTestCase):
    def setUp(self):self.setup_transcript()

    def test_direct_review_insert_waits_for_encounter_hold_without_deadlock(self):
        """Direct SQL trigger ordering: hold owns row, then insert starts before hold acquires preservation lock."""
        paused,resume=threading.Event(),threading.Event()
        real_lock=retention.lock_preservation
        def pause_hold():
            paused.set()
            if not resume.wait(15):raise RuntimeError('Synthetic hold deadline expired')
            return real_lock()
        with patch('core.retention.lock_preservation',side_effect=pause_hold):
            holding,held=in_thread(lambda:retention.create_hold(self.admin,'encounter',self.row.pk,'c'*64,uuid.uuid4()))
            try:
                self.assertTrue(paused.wait(10),'hold never acquired the encounter row')
                inserting,inserted=in_thread(lambda:m.TranscriptReview.objects.create(**self.review_values()))
                blocked=wait_for_blocked_backend(timeout=2)
            finally:
                resume.set()
            self.finish(holding,inserting)
        self.assertTrue(blocked,'direct review insert never waited for held encounter')
        self.assertNotIn('error',held,held.get('error'))
        self.assertNotIn('error',inserted,inserted.get('error'))
        self.assertEqual(inserted['value'].reviewed_text,self.row.notes)
        self.assertTrue(retention.active_holds(encounter_id=self.row.pk).filter(pk=held['value'].pk).exists())


@override_settings(**V3)
class ImportedEvidenceRollback(V3Fixture,TestCase):
    def test_leaf_refuses_existing_import_evidence_even_without_transcript_rows(self):
        _,version=self.uploaded(data=build_questionnaire(1),name='Synthetic retained import')
        self.assertTrue(version.import_manifest)
        self.assertFalse(m.TranscriptReview.objects.exists())
        with self.assertRaisesMessage(IrreversibleError,'Import selection evidence exists'):
            importlib.import_module('core.migrations.0037_transcript_redaction_boundary').refuse_evidence(apps,None)
        from ops import integrity_contract
        with connection.cursor() as cursor:
            cursor.execute(integrity_contract.CATALOG);rows=cursor.fetchall()
            cursor.execute(integrity_contract.CONTEXT);context=cursor.fetchall()
        self.assertTrue(integrity_contract.assess(rows,context,len(integrity_contract.GUARDS))['passed'])


class CodingEvidenceAtTranscriptLeaf(SyntheticFixture,TransactionTestCase):
    """A real multi-migration reverse must refuse at the leaf, preserving every newer guard, or finish cleanly."""
    def setUp(self):
        self.scope=self.make_scope('transcript-rollback',historical_empty_import=True)
        today=timezone.localdate()
        self.release=m.CodeSet.objects.create(system='ICD-10-CM',version='synthetic-transcript-rollback',
            effective_from=today,effective_until=today,source_url='https://example.invalid/synthetic',sha256='d'*64)
        self.code=m.Code.objects.create(release=self.release,code='R00.0',description='Synthetic rollback evidence')

    def tearDown(self):
        executor=MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())
        super().tearDown()

    def contract(self):
        from ops import integrity_contract
        with connection.cursor() as cursor:
            cursor.execute(integrity_contract.CATALOG);rows=cursor.fetchall()
            cursor.execute(integrity_contract.CONTEXT);context=cursor.fetchall()
        return integrity_contract.assess(rows,context,len(integrity_contract.GUARDS))

    def refusal_keeps_exact_schema(self,**columns):
        suggestion=m.CodeSuggestion.objects.create(encounter=self.scope[5],terminology=self.code,
            explanation='Synthetic evidence',evidence='Synthetic source',**columns)
        before=set(MigrationRecorder(connection).applied_migrations())
        rows=list(m.CodeSuggestion.objects.values())
        self.assertFalse(m.TranscriptReview.objects.exists())
        self.assertFalse(m.TemplateVersion.objects.exclude(import_manifest={}).exists())
        with self.assertRaisesMessage(IrreversibleError,'Coding ledger evidence requires a forward migration'):
            MigrationExecutor(connection).migrate([('core','0033_redaction_tombstone')])
        self.assertEqual(set(MigrationRecorder(connection).applied_migrations()),before)
        self.assertEqual(list(m.CodeSuggestion.objects.values()),rows)
        self.assertTrue(self.contract()['passed'])
        self.assertEqual(m.CodeSuggestion.objects.get(pk=suggestion.pk).evidence,'Synthetic source')

    def test_release_identity_refuses_before_any_newer_guard_is_removed(self):
        self.refusal_keeps_exact_schema(release_sha256=self.release.sha256)

    def test_review_mark_alone_refuses_before_any_newer_guard_is_removed(self):
        self.refusal_keeps_exact_schema(review_required=True)

    def test_without_protected_columns_reverse_and_forward_keep_legacy_rows(self):
        suggestion=m.CodeSuggestion.objects.create(encounter=self.scope[5],terminology=self.code,
            explanation='Synthetic legacy evidence',evidence='Synthetic legacy source')
        MigrationExecutor(connection).migrate([('core','0033_redaction_tombstone')])
        self.assertNotIn(('core','0037_transcript_redaction_boundary'),MigrationRecorder(connection).applied_migrations())
        with connection.cursor() as cursor:
            cursor.execute('SELECT evidence FROM core_codesuggestion WHERE id=%s',[suggestion.pk])
            self.assertEqual(cursor.fetchone()[0],'Synthetic legacy source')
        executor=MigrationExecutor(connection);executor.migrate(executor.loader.graph.leaf_nodes())
        kept=m.CodeSuggestion.objects.get(pk=suggestion.pk)
        self.assertEqual((kept.release_sha256,kept.review_required,kept.evidence),('',False,'Synthetic legacy source'))
        self.assertTrue(self.contract()['passed'])
