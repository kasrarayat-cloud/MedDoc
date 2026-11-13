# Design v2 (docs/gemini-migration/FINAL-V2.md 6.3, adopted as DECISIONS D178; step 1d of its 8.1):
# EventInventory.appraisal_run, the appraisal ProviderRun (pass 2) whose verdicts a gemini-events@2 inventory settled,
# so a v2 row binds both of its Gemini runs (interpretation.store.BINDINGS_V2). Written from
# `makemigrations --dry-run` (Django 5.2.17).
#
# Additive only (ops/install.py migration_verdict: "nullable"), and nothing else: no existing column changes, no default
# of any kind, no NOT NULL, no backfill and no RunPython. The unique key (revision, interpretation_version,
# inventory_version, provider_run) is unchanged and stays sufficient (FINAL-V2 6.3): a read row is written only when
# both passes are settled; a refused pass-1 answer writes a refused row with appraisal_run NULL; a refused or unhealthy
# pass-2 answer is recorded on its ProviderRun and the stage, never as a row. The previous release's web and worker
# never read the column, and a row they insert names none of it, so it is NULL there and the row stays valid.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('studio', '0014_event_inventory'),
    ]

    operations = [
        migrations.AddField(
            model_name='eventinventory',
            name='appraisal_run',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, related_name='+',
                                    to='studio.providerrun'),
        ),
    ]
