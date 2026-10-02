"""Preserve both additive migration branches; neither supersedes the other."""
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("core", "0027_generation_batches"), ("core", "0028_disposition_preparation")]
    operations = []
