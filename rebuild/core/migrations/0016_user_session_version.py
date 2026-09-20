from django.db import migrations, models


def revoke_preexisting_suspended_accounts(apps, schema_editor):
    user = apps.get_model('core', 'User')
    user.objects.using(schema_editor.connection.alias).filter(
        is_active=False, session_version=0).update(session_version=1)


class Migration(migrations.Migration):
    dependencies = [('core', '0015_reconciliation_evidence_guard')]
    operations = [
        migrations.AddField(
            model_name='user', name='session_version',
            field=models.PositiveBigIntegerField(default=0, editable=False),
        ),
        migrations.RunPython(revoke_preexisting_suspended_accounts, migrations.RunPython.noop),
    ]
