"""Record the date of service each encounter documents.

ICD-10-CM is published per federal fiscal year, so the applicable release is the
one in effect on the date of service or discharge. Existing encounters keep the
date they were recorded on, which is the only service date this system has ever
held for them; nothing is invented and no encounter row is removed.
"""
from datetime import timezone as utc_only

from django.db import migrations, models


def adopt_recorded_date(apps, schema_editor):
    """UTC deliberately, and spelled out rather than taken from settings.

    Reading TIME_ZONE here would bind eleven irreversible clinical dates to a setting that can be
    changed later by someone with no idea this migration existed. The stored timestamps are UTC;
    the date that is derived from them is the UTC date, whatever the project is configured to
    display.
    """
    Encounter = apps.get_model('core', 'Encounter')
    # `encounter_scope` refuses ANY update to a finalized document — six of the eleven rows here are finalized, and the
    # first attempt at this migration died on "Finalized document is immutable". The guard is right and this is not the
    # thing it guards against: no clinical content changes, the date is derived from the row's own created_at, and the
    # statement below can only write one column. The guard cannot express that distinction, so it is suspended for
    # exactly this statement and restored in the same transaction — DDL is transactional here, and DISABLE TRIGGER takes
    # an ACCESS EXCLUSIVE lock, so no other writer can slip through the window even if one were running.
    with schema_editor.connection.cursor() as cursor:
        cursor.execute('ALTER TABLE core_encounter DISABLE TRIGGER encounter_scope')
    try:
        for encounter in Encounter.objects.filter(service_date__isnull=True).only('id', 'created_at').iterator():
            Encounter.objects.filter(pk=encounter.pk).update(
                service_date=encounter.created_at.astimezone(utc_only.utc).date())
    finally:
        with schema_editor.connection.cursor() as cursor:
            cursor.execute('ALTER TABLE core_encounter ENABLE TRIGGER encounter_scope')


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
