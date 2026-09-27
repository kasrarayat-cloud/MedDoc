"""The core test package.

TransactionTestCase empties every table between tests with one TRUNCATE (Django's flush). Migration 0020's statement-
level TRUNCATE guards refuse that, exactly as they refuse any other TRUNCATE of the payment evidence. So, for the test
database only, the flush lifts the enabled TRUNCATE triggers and restores them in the same transaction: a flush that
fails rolls back with them still enabled, and no other statement ever runs without them. ALTER TABLE ... DISABLE TRIGGER
needs ownership of the table, which the test role has (it created the test database) and the runtime role never does.
"""
from django.db import transaction
from django.db.backends.postgresql.operations import DatabaseOperations

TRUNCATE_GUARDS = ("SELECT c.relname, t.tgname FROM pg_trigger t JOIN pg_class c ON c.oid = t.tgrelid "
                   "JOIN pg_namespace n ON n.oid = c.relnamespace WHERE n.nspname = current_schema() "
                   "AND NOT t.tgisinternal AND t.tgenabled = 'O' AND (t.tgtype::int & 32) <> 0")
_flush = DatabaseOperations.execute_sql_flush


def flush_past_truncate_guards(self, sql_list):
    if not sql_list:
        return _flush(self, sql_list)
    quote = self.quote_name
    with transaction.atomic(using=self.connection.alias):
        with self.connection.cursor() as cursor:
            cursor.execute(TRUNCATE_GUARDS)
            guards = cursor.fetchall()
            for table, name in guards:
                cursor.execute(f'ALTER TABLE {quote(table)} DISABLE TRIGGER {quote(name)}')
        _flush(self, sql_list)
        with self.connection.cursor() as cursor:
            for table, name in guards:
                cursor.execute(f'ALTER TABLE {quote(table)} ENABLE TRIGGER {quote(name)}')


DatabaseOperations.execute_sql_flush = flush_past_truncate_guards
