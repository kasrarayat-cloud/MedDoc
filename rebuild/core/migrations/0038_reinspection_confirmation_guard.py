"""Keep the explicit review gate for a freshly reinspected legacy mapping.

0031 already protects contract v3 mappings from an older image that knows no
confirmation workflow. A linked reinspection can select the legacy engine, so
its immutable import_manifest marker must require the same exact-version
confirmation. This changes only 0031's predicate in the existing encounter
function: no new trigger, schema, data rewrite or import-provenance exception.

Key presence deliberately holds malformed/empty markers as well. Reversal
refuses before replacing the function while any such mapping exists, confirmed
or otherwise. An ordinary legacy database can restore the unchanged 0031 body.
"""
import importlib

from django.db import migrations
from django.db.migrations.exceptions import IrreversibleError


GATE = """CREATE OR REPLACE FUNCTION quillmd_encounter_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE patient_department uuid; template_department uuid; placed boolean;
BEGIN
 IF TG_OP='UPDATE' AND OLD.status='finalized' THEN RAISE EXCEPTION 'Finalized document is immutable'; END IF;
 SELECT department_id INTO patient_department FROM core_patient WHERE id=NEW.patient_id;
 SELECT t.department_id INTO template_department FROM core_template t JOIN core_templateversion v ON v.template_id=t.id WHERE v.id=NEW.template_version_id;
 IF NEW.department_id IS DISTINCT FROM patient_department OR NEW.department_id IS DISTINCT FROM template_department THEN RAISE EXCEPTION 'Department mismatch'; END IF;
 IF TG_OP='INSERT' THEN placed=true; ELSE placed=NEW.template_version_id IS DISTINCT FROM OLD.template_version_id; END IF;
 IF (placed OR NEW.status='finalized') AND EXISTS(SELECT 1 FROM core_templateversion v WHERE v.id=NEW.template_version_id
     AND (v.contract='v3' OR v.import_manifest ? 'reinspection') AND NOT EXISTS(SELECT 1 FROM core_mappingconfirmation c WHERE c.version_id=v.id)) THEN
  IF placed THEN RAISE EXCEPTION 'An unconfirmed contract v3 mapping cannot start a document'; END IF;
  RAISE EXCEPTION 'A document on an unconfirmed contract v3 mapping cannot be finalized';
 END IF;
 RETURN NEW;
END; $$;"""

_0031 = importlib.import_module('core.migrations.0031_previous_release_mapping_writes')


def preserve_reinspection_review(apps, schema_editor):
    """Reverse first; counts only, using the executor's actual database alias."""
    count = (apps.get_model('core', 'TemplateVersion').objects.using(schema_editor.connection.alias)
             .filter(import_manifest__has_key='reinspection').count())
    if count:
        raise IrreversibleError(
            f'0038_reinspection_confirmation_guard cannot be reversed: {count} mapping version(s) '
            'retain reinspection evidence. Preserve the exact-version clinician review gate and use a '
            'reviewed forward repair or compatible code rollback. 0038 was not reversed; its guard '
            'and all retained mapping and document records are unchanged.')


class Migration(migrations.Migration):
    dependencies = [('core', '0037_transcript_redaction_boundary')]
    operations = [
        migrations.RunSQL(GATE, _0031.GATE),
        # Reverse operations run backwards: refuse before replacing the guard.
        migrations.RunPython(migrations.RunPython.noop, preserve_reinspection_review),
    ]
