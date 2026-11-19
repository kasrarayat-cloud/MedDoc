# Gemini migration (FINAL.md section 4, D6, D11, D22): the persisted event inventory every new-path consumer reads, the
# installation-wide interpreter hold and its release, and three nullable columns that bind a context and an assessment
# to the inventory they were made from. Written from `makemigrations --dry-run` (Django 5.2.17), operations reordered
# for reading.
#
# Additive only (ops/install.py migration_verdict), with no backfill and no RunPython: three new tables (their
# constraint and index are on a table this migration creates) and three columns added to existing tables, each nullable
# with no database default. The previous release's web and worker never read any of them, and a row they insert names
# none of the new columns, so it leaves them NULL and stays valid.

import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('studio', '0013_completion_answer_binding'),
    ]

    operations = [
        migrations.CreateModel(
            name='EventInventory',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('interpretation_version', models.CharField(max_length=40)),
                ('inventory_version', models.CharField(max_length=40)),
                ('text_sha256', models.CharField(max_length=64)),
                ('request_sha256', models.CharField(max_length=64)),
                ('response_sha256', models.CharField(max_length=64)),
                ('state', models.CharField(max_length=12)),
                ('events', models.JSONField()),
                ('encounter_facts', models.JSONField()),
                ('open_questions', models.JSONField()),
                ('verification', models.JSONField()),
                ('sha256', models.CharField(max_length=64)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('encounter', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                                                related_name='event_inventories', to='studio.encounter')),
                ('provider_run', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                                                   related_name='event_inventories', to='studio.providerrun')),
                ('revision', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                                               related_name='event_inventories', to='studio.sourcerevision')),
            ],
            options={
                'ordering': ['created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='eventinventory',
            index=models.Index(fields=['revision', 'interpretation_version', 'inventory_version'],
                               name='studio_inventory_versions'),
        ),
        migrations.AddConstraint(
            model_name='eventinventory',
            constraint=models.UniqueConstraint(
                fields=('revision', 'interpretation_version', 'inventory_version', 'provider_run'),
                name='one_inventory_per_revision_versions_run'),
        ),
        migrations.AddField(
            model_name='encountercontext',
            name='event_inventory',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                                    related_name='+', to='studio.eventinventory'),
        ),
        migrations.AddField(
            model_name='assessment',
            name='event_inventory',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                                    related_name='+', to='studio.eventinventory'),
        ),
        migrations.AddField(
            model_name='assessment',
            name='interpretation',
            field=models.JSONField(blank=True, null=True),
        ),
        migrations.CreateModel(
            name='InterpreterHold',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('reason', models.CharField(max_length=20)),
                ('http_status', models.PositiveIntegerField(blank=True, null=True)),
                ('vendor_status', models.CharField(blank=True, max_length=40)),
                ('violations', models.JSONField(blank=True, default=list)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('run', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                                          related_name='interpreter_holds', to='studio.providerrun')),
            ],
            options={
                'ordering': ['created_at'],
            },
        ),
        migrations.CreateModel(
            name='InterpreterHoldRelease',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('note', models.TextField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('hold', models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name='release',
                                              to='studio.interpreterhold')),
                ('released_by', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='+',
                                                  to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'abstract': False,
            },
        ),
    ]
