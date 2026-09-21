from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('core', '0016_user_session_version')]
    # Existing evidence remains unclassified; no historical cost, ledger movement,
    # evidence reference, or declared invoice status is inferred or rewritten.
    operations = [
        migrations.AddField(
            model_name='costreconciliation', name='evidence_kind',
            field=models.CharField(max_length=16, default='unclassified', choices=[
                ('unclassified', 'Unclassified evidence · invoice status unknown'),
                ('provider_report', 'Provider-reported actual · not invoice reconciled'),
                ('invoice', 'Invoice-reconciled actual'),
            ]),
        ),
        migrations.AddConstraint(
            model_name='costreconciliation',
            constraint=models.CheckConstraint(
                condition=models.Q(evidence_kind__in=['unclassified', 'provider_report', 'invoice']),
                name='reconciliation_evidence_kind_known',
            ),
        ),
    ]
