# Release 2 (RELEASE-2-SPEC R2-23 and section 6; D-R2-15): a coding round's runs and the runs in flight, on
# studio_providerrun alone.
#
# studio.jobs finds a round's runs by scope -> 'round' with the coding purposes (awaiting_reconcile, _reused,
# abandoned_outcome, the sweep) and so does the console (studio.operator.round_runs): studio_run_round is that
# expression, over the coding runs only, so each lookup reads its round's runs instead of every run. The 60-second sweep
# settles runs left sending or reserved: studio_run_in_flight holds those alone, by when they were made. No line of
# studio/jobs.py changes: the lookups already compile to (scope -> 'round') = value with the coding purposes, and an
# index serves them with identical results by construction. Django's own non-unique Index, refusing no write; one table.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('studio', '0019_r2_document_lists'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='providerrun',
            index=models.Index(models.F('scope__round'), condition=models.Q(('purpose__in', ['coding_reader', 'coding_checker'])), name='studio_run_round'),
        ),
        migrations.AddIndex(
            model_name='providerrun',
            index=models.Index(condition=models.Q(('state__in', ['sending', 'reserved'])), fields=['created_at'], name='studio_run_in_flight'),
        ),
    ]
