# Completion repair (2026-11-06, U11): a member's answer binds to the question it answered, and a question is closed with
# the answer it was answered by. Additive only (ops/install.py migration_verdict): a column with a database default and
# a nullable foreign key; the previous release's web and worker never read either, and a row they insert stays valid.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('studio', '0012_cux_worker_beat'),
    ]

    operations = [
        migrations.AddField(
            model_name='memberanswer',
            name='question',
            field=models.CharField(blank=True, db_default='', default='', max_length=64),
        ),
        migrations.AddField(
            model_name='clarification',
            name='answer',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                                    related_name='+', to='studio.memberanswer'),
        ),
    ]
