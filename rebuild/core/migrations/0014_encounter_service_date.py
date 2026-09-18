"""Record the date of service each encounter documents.

ICD-10-CM is published per federal fiscal year, so the applicable release is the
one in effect on the date of service or discharge. Existing encounters keep the
date they were recorded on, which is the only service date this system has ever
held for them; nothing is invented and no encounter row is removed.
"""
from django.db import migrations, models
from django.utils import timezone


def adopt_recorded_date(apps, schema_editor):
    Encounter = apps.get_model('core', 'Encounter')
    for encounter in Encounter.objects.filter(service_date__isnull=True).only('id', 'created_at').iterator():
        Encounter.objects.filter(pk=encounter.pk).update(
            service_date=timezone.localtime(encounter.created_at).date())


def keep_the_dates(apps, schema_editor):
    """Reversing drops the column; the values cannot be restored by writing them back."""


class Migration(migrations.Migration):
    dependencies = [('core', '0013_recording_charge_limit')]
    operations = [
        migrations.AddField(model_name='encounter', name='service_date',
                            field=models.DateField(null=True)),
        migrations.RunPython(adopt_recorded_date, keep_the_dates),
        migrations.AlterField(model_name='encounter', name='service_date',
                              field=models.DateField()),
    ]
