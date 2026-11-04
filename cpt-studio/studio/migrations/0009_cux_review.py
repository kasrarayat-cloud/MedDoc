# Core repair and customer interface (2026-11-03), package P3 REVIEW: the reviewer's chosen modifier on a decision.
# Additive only (ops/install.py migration_verdict): a NOT NULL JSON column with a database-level default as well (the
# 0007 pattern), so a decision the previous release inserts in the seconds between this migration and the replacement of
# its web and worker containers (it names no such column) is valid and reads as no modifier chosen.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('studio', '0008_harness2_exchanges_tools_confirmations'),
    ]

    operations = [
        migrations.AddField(
            model_name='decision',
            name='modifiers',
            field=models.JSONField(default=list),
        ),
        migrations.RunSQL(
            sql=["ALTER TABLE studio_decision ALTER COLUMN modifiers SET DEFAULT '[]'::jsonb"],
            reverse_sql=['ALTER TABLE studio_decision ALTER COLUMN modifiers DROP DEFAULT'],
        ),
    ]
