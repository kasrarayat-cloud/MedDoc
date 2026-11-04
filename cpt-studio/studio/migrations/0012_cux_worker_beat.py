# Core repair and customer interface (2026-11-03), decision (j): the worker heartbeat. Additive only (ops/install.py
# migration_verdict): one new table no older revision reads; the previous release's web and worker never touch it.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('studio', '0011_cux_flow'),
    ]

    operations = [
        migrations.CreateModel(
            name='WorkerBeat',
            fields=[
                ('name', models.CharField(max_length=20, primary_key=True, serialize=False)),
                ('beat_at', models.DateTimeField()),
                ('revision', models.CharField(blank=True, max_length=64)),
                ('pid', models.PositiveIntegerField(blank=True, null=True)),
            ],
        ),
    ]
