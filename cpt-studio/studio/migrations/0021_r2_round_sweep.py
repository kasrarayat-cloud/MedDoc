# Release 2 (RELEASE-2-SPEC R2-23 and section 6; D-R2-15): the open rounds, on studio_codinground alone.
#
# The 60-second sweep settles a round left queued or running with no job of its encounter (studio.jobs): its read of
# Round.objects.filter(state__in=(queued, running), created_at__lt=...) is served by studio_round_open, which holds the
# open rounds alone. Django's own non-unique Index, refusing no write; one table.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('studio', '0020_r2_run_lookups'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='codinground',
            index=models.Index(condition=models.Q(('state__in', ['queued', 'running'])), fields=['created_at'], name='studio_round_open'),
        ),
    ]
