"""Refuse false redaction while immutable reviewed clinical text remains.

Additive only. This guard complements the application refusal and holds the
same encounter-before-preservation locks as transcript insert and redaction.
No clinical content or financial history is deleted by this migration.
"""
import importlib

from django.db import migrations
from django.db.migrations.exceptions import IrreversibleError

SQL='''CREATE FUNCTION quillmd_transcript_redaction_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF current_setting('transaction_isolation') <> 'read committed' THEN
  RAISE EXCEPTION 'Transcript redaction requires read committed isolation';
 END IF;
 PERFORM id FROM core_encounter WHERE id=NEW.target_id FOR UPDATE;
 PERFORM pg_advisory_xact_lock(716849203517);
 IF EXISTS(SELECT 1 FROM core_transcriptreview WHERE encounter_id=NEW.target_id)
 THEN RAISE EXCEPTION 'Immutable transcript review keeps clinical content; this document cannot be redacted'; END IF;
 RETURN NEW;
END; $$;
CREATE TRIGGER redactiontombstone_transcript BEFORE INSERT ON core_redactiontombstone
 FOR EACH ROW EXECUTE FUNCTION quillmd_transcript_redaction_guard();'''

REVERSE='''DROP TRIGGER redactiontombstone_transcript ON core_redactiontombstone;
DROP FUNCTION quillmd_transcript_redaction_guard();'''

def refuse_evidence(apps,schema_editor):
    if apps.get_model('core','TranscriptReview').objects.exists():
        raise IrreversibleError('Immutable transcript review evidence requires its redaction boundary; use code rollback.')
    # Refuse first at the leaf, preserving every guard if an older protected mapping would stop rollback later.
    importlib.import_module('core.migrations.0035_import_manifest').preserve(apps,schema_editor)
    importlib.import_module('core.migrations.0034_coding_ledger').refuse_a_rollback_0031_refuses(apps,schema_editor)

class Migration(migrations.Migration):
    dependencies=[('core','0036_transcript_review')]
    operations=[migrations.RunSQL(SQL,REVERSE),migrations.RunPython(migrations.RunPython.noop,refuse_evidence)]
