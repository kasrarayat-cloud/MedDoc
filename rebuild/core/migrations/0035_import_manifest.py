"""Append-only import provenance; old code writes the empty database default.

Reversal refuses once any manifest is retained, because dropping this column
would destroy the only binding of that import choice and its coverage evidence.
"""
from django.db import migrations, models
from django.db.migrations.exceptions import IrreversibleError


GUARD = r'''CREATE FUNCTION quillmd_import_manifest_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE prior jsonb; source_hash text;
BEGIN
 SELECT import_manifest INTO prior FROM core_templateversion
   WHERE template_id=NEW.template_id AND import_manifest<>'{}'::jsonb ORDER BY number LIMIT 1;
 IF prior IS NOT NULL AND (NEW.import_manifest-'mapping_sha256') IS DISTINCT FROM (prior-'mapping_sha256') THEN
   RAISE EXCEPTION 'An imported mapping keeps its original import choice and coverage evidence';
 END IF;
 IF NEW.import_manifest<>'{}'::jsonb THEN
   SELECT sha256 INTO source_hash FROM core_template WHERE id=NEW.template_id;
   IF jsonb_typeof(NEW.import_manifest)<>'object'
      OR NEW.import_manifest->>'source_sha256' IS DISTINCT FROM source_hash
      OR NEW.import_manifest->>'engine' IS DISTINCT FROM (CASE WHEN NEW.contract='v3' THEN 'v3' ELSE 'legacy' END)
      OR coalesce(NEW.import_manifest->>'mapping_sha256','') !~ '^[0-9a-f]{64}$'
      OR coalesce(NEW.import_manifest->>'initial_mapping_sha256','') !~ '^[0-9a-f]{64}$'
      OR coalesce(NEW.import_manifest->>'engine_code_sha256','') !~ '^[0-9a-f]{64}$' THEN
     RAISE EXCEPTION 'The import manifest does not bind this original and engine';
   END IF;
 END IF;
 RETURN NEW;
END; $$;
CREATE TRIGGER quillmd_import_manifest_guard BEFORE INSERT ON core_templateversion
 FOR EACH ROW EXECUTE FUNCTION quillmd_import_manifest_guard();'''


def preserve(apps, schema_editor):
    if apps.get_model('core', 'TemplateVersion').objects.exclude(import_manifest={}).exists():
        raise IrreversibleError('Import selection evidence exists; preserve import_manifest before any rollback.')


class Migration(migrations.Migration):
    dependencies = [('core', '0034_coding_ledger')]
    operations = [
        migrations.AddField(model_name='templateversion', name='import_manifest',
                            field=models.JSONField(default=dict, blank=True, db_default={})),
        migrations.RunSQL(GUARD, 'DROP TRIGGER quillmd_import_manifest_guard ON core_templateversion; '
                                'DROP FUNCTION quillmd_import_manifest_guard();'),
        migrations.RunPython(migrations.RunPython.noop, preserve),
    ]
