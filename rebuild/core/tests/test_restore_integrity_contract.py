"""The production drill contract agrees with this release's actual fresh PostgreSQL schema."""
from django.test import TestCase
from django.db import connection, transaction
from ops import integrity_contract


class ReleaseIntegrityContract(TestCase):
    def test_fresh_migrations_have_exact_release_bound_guards(self):
        with connection.cursor() as cursor:
            cursor.execute(integrity_contract.CATALOG)
            rows = cursor.fetchall()
            cursor.execute(integrity_contract.CONTEXT)
            context = cursor.fetchall()
        report = integrity_contract.assess(rows,context,len(integrity_contract.GUARDS))
        self.assertTrue(report['passed'],report)
        self.assertEqual(report['found'],63)
        self.assertEqual(len(integrity_contract.FUNCTION_SHA256),18)

    def test_batch_guards_and_composed_preservation_body_fail_closed_when_changed(self):
        def read():
            with connection.cursor() as cursor:
                cursor.execute(integrity_contract.CATALOG);rows=cursor.fetchall()
                cursor.execute(integrity_contract.CONTEXT);context=cursor.fetchall()
            return integrity_contract.assess(rows,context,63)
        self.assertTrue(read()['passed'])
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute('ALTER TABLE core_generationbatchresponse DISABLE TRIGGER generationbatchresponse_append_only')
            self.assertFalse(read()['passed'])
            transaction.set_rollback(True)
        self.assertTrue(read()['passed'])
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute('CREATE OR REPLACE FUNCTION quillmd_batch_job_guard() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RETURN NEW; END; $$;')
            self.assertFalse(read()['passed'])
            transaction.set_rollback(True)
        self.assertTrue(read()['passed'])

    def test_release_restore_reference_queries_include_immutable_batch_response(self):
        from ops.production_restore_check import FILE_QUERIES
        batch=[sql for kind,sql in FILE_QUERIES if kind=='batch_response']
        self.assertEqual(batch,["SELECT result_path,result_sha256 FROM core_generationbatchresponse WHERE result_path<>''"])
        with connection.cursor() as cursor:
            for _,sql in FILE_QUERIES:
                cursor.execute(sql);cursor.fetchall()
