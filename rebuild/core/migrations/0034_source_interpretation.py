"""Add one append-only interpretation table; do not alter historical rows."""
import uuid

import django.db.models.deletion
from django.db import migrations, models


SQL = '''
CREATE TRIGGER source_interpretation_append_only
BEFORE UPDATE OR DELETE ON core_sourceinterpretation
FOR EACH ROW EXECUTE FUNCTION quillmd_append_only();
REVOKE ALL ON TABLE core_sourceinterpretation FROM PUBLIC;
DO $$ BEGIN
 IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='quillmd_runtime') THEN
  REVOKE UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER ON TABLE core_sourceinterpretation FROM quillmd_runtime;
  GRANT SELECT,INSERT ON TABLE core_sourceinterpretation TO quillmd_runtime;
 END IF;
END; $$;
'''
REVERSE = '''
DO $$ BEGIN
 IF EXISTS (SELECT 1 FROM core_sourceinterpretation) THEN
  RAISE EXCEPTION 'Retained source interpretations forbid reversing this migration';
 END IF;
END; $$;
DROP TRIGGER source_interpretation_append_only ON core_sourceinterpretation;
'''


class Migration(migrations.Migration):
    dependencies = [('core', '0033_retained_semantic_revalidation_v3')]
    operations = [
        migrations.CreateModel(
            name='SourceInterpretation',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('contract', models.CharField(max_length=100)),
                ('interpretation_sha256', models.CharField(max_length=64)),
                ('source_sha256', models.CharField(max_length=64)),
                ('bindings', models.JSONField(default=dict)),
                ('interpretation', models.JSONField(default=dict)),
                ('stage_receipts', models.JSONField(default=list)),
                ('encounter', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                    related_name='source_interpretations', to='core.encounter')),
                ('job', models.OneToOneField(on_delete=django.db.models.deletion.PROTECT,
                    related_name='source_interpretation', to='core.job')),
            ],
        ),
        migrations.RunSQL(SQL, REVERSE),
    ]
