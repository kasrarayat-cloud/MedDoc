"""The production drill contract agrees with this release's actual fresh PostgreSQL schema."""
from django.test import TestCase
from django.db import connection
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
        self.assertEqual(report['found'],17)
