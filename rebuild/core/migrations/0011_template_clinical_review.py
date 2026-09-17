from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('core', '0010_canonical_provider_settlement')]
    operations = [
        migrations.AddField(
            model_name='templateversion', name='review_requirements',
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name='templateversion', name='document_backend',
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name='encounter', name='template_review',
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
