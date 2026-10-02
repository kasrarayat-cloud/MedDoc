import json
from pathlib import Path
from django.test import TestCase
from django.db import connection
from ops import integrity_contract as contract

class RootRestoreContract(TestCase):
    def test_intact_batch_migration_matches_production_restore_contract(self):
        with connection.cursor() as cursor:
            cursor.execute(contract.CATALOG);rows=cursor.fetchall()
            cursor.execute(contract.CONTEXT);context=cursor.fetchall()
        result=contract.assess(rows,context,len(contract.GUARDS))
        Path(__file__).with_name('restore-after.json').write_text(json.dumps(result,indent=2)+'\n')
        self.assertTrue(result['passed'],result)
