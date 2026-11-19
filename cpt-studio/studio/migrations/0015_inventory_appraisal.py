# Design v2 (docs/gemini-migration/FINAL-V2.md 6.3, adopted as DECISIONS D178; step 1d of its 8.1):
# EventInventory.appraisal_run, the appraisal ProviderRun (pass 2) whose verdicts a gemini-events@2 inventory settled,
# so a v2 row binds both of its Gemini runs (interpretation.store.BINDINGS_V2). Written from
# `makemigrations --dry-run` (Django 5.2.17).
#
# FINAL-V2 amendment 1 (docs/gemini-migration/AMENDMENT-1.md, adopted as DECISIONS D208; its section 10's first row,
# step 1d-A1): 0015 is installed nowhere, so the amendment's schema is an edit of 0015, beside appraisal_run:
# - EncounterContext.earlier_assessment (4.5, A5): the earlier codes a context was made after, set at insert;
# - ProviderHold and ProviderHoldRelease (7.3, A16 and A20): Corti's, Astra's and Fable's installation-wide holds and
#   their recorded releases, shaped like 0014's InterpreterHold and InterpreterHoldRelease.
# Those three operations were written from `makemigrations --dry-run` (Django 5.2.17) over 0015 as it stood.
#
# Additive only (ops/install.py migration_verdict: two nullable columns and two new tables), and nothing else: no
# existing column changes, no default of any kind on an added column, no NOT NULL on an existing table, no backfill and
# no RunPython. The unique key (revision, interpretation_version, inventory_version, provider_run) is unchanged and
# stays sufficient (FINAL-V2 6.3): a read row is written only when both passes are settled; a refused pass-1 answer
# writes a refused row with appraisal_run NULL; a refused or unhealthy pass-2 answer is recorded on its ProviderRun and
# the stage, never as a row. The previous release's web and worker never read the new columns or tables, and a row
# they insert names neither column, so both are NULL there and the row stays valid.

import django.db.models.deletion
import uuid
from django.conf import settings
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
        migrations.AddField(
            model_name='encountercontext',
            name='earlier_assessment',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                                    related_name='+', to='studio.assessment'),
        ),
        migrations.CreateModel(
            name='ProviderHold',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('provider', models.CharField(max_length=20)),
                ('reason', models.CharField(max_length=20)),
                ('http_status', models.PositiveIntegerField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('run', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='provider_holds',
                                          to='studio.providerrun')),
            ],
            options={
                'ordering': ['created_at'],
            },
        ),
        migrations.CreateModel(
            name='ProviderHoldRelease',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('note', models.TextField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('hold', models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name='release',
                                              to='studio.providerhold')),
                ('released_by', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='+',
                                                  to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'abstract': False,
            },
        ),
    ]
