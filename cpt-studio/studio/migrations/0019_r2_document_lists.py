# Release 2 (RELEASE-2-SPEC R2-23 and section 6; D-R2-15): the paged lists' two indexes, on studio_encounter alone.
#
# GET /api/encounters reads one page of a practice's documents, newest first - created_at descending, then id - by
# keyset (R2-19): studio_enc_ws_time over the practice's live rows (destroyed_at IS NULL) for Documents, the Overview and
# the search, and studio_enc_ws_queue over those waiting on a member (the three states of studio.customer.QUEUE_STATES)
# for the Review queue. Both are Django's own non-unique Index, which refuses no write, so release 1's web and worker run
# on this schema unchanged (ops/install.py migration_verdict). An index on an existing table lives in a migration that
# touches that table only: CREATE INDEX takes a SHARE lock on its one table, and a migration locking two tables can
# deadlock against a worker writing both, which migrate_bounded does not retry (ops/test_install.py pins the rule).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('studio', '0018_r1_availability'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='encounter',
            index=models.Index(condition=models.Q(('destroyed_at__isnull', True)), fields=['workspace', 'created_at', 'id'], name='studio_enc_ws_time'),
        ),
        migrations.AddIndex(
            model_name='encounter',
            index=models.Index(condition=models.Q(('destroyed_at__isnull', True), ('state__in', ['awaiting_answer', 'needs_review', 'ready'])), fields=['workspace', 'created_at', 'id'], name='studio_enc_ws_queue'),
        ),
    ]
