"""The ICD coding ledger: release identity on every suggestion, append-only releases and codes, frozen finalized codes.

- core_codeset and core_code become append-only (UPDATE, DELETE and TRUNCATE refused): a suggestion's release can no
  longer change under it. Importing adds releases; nothing ever rewrote one (core/management/commands/import_terminology).
- core_codesuggestion gains release_sha256 (the release's imported-file sha256, checked against that release at INSERT
  when given; '' on rows written before this migration or by the previous release, whose INSERT omits it) and
  review_required (a changed notes save marks an accepted code for re-review instead of deleting it).
- quillmd_coding_guard on core_codesuggestion (BEFORE INSERT OR UPDATE OR DELETE): no code is added to, changed on or
  removed from a finalized document (codes are frozen at finalization with the document); a suggestion's code, release
  identity, evidence and explanation never change; an accepted code is never deleted (its acceptance is withdrawn first,
  an explicit clinician act) except while redacting the document (0033's tombstone).

Both new columns have database defaults, so the previous release's INSERT still works on this schema (MIG-1). Reversal
refuses while any suggestion carries a release identity or a re-review mark (they would be lost), and, like 0032/0033,
refuses first at the leaf with 0031's R1 message while v3 mapping evidence exists.
"""
import importlib

from django.db import migrations, models
from django.db.migrations.exceptions import IrreversibleError

SQL = '''CREATE FUNCTION quillmd_coding_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE state text; release_hash text;
BEGIN
 IF TG_OP='INSERT' THEN
  SELECT status INTO state FROM core_encounter WHERE id=NEW.encounter_id;
  IF state='finalized' THEN RAISE EXCEPTION 'The codes of a finalized document are frozen'; END IF;
  IF NEW.release_sha256<>'' THEN
   SELECT s.sha256 INTO release_hash FROM core_code c JOIN core_codeset s ON s.id=c.release_id WHERE c.id=NEW.terminology_id;
   IF release_hash IS DISTINCT FROM NEW.release_sha256 THEN RAISE EXCEPTION 'A code suggestion must name its release identity'; END IF;
  END IF;
  RETURN NEW;
 END IF;
 SELECT status INTO state FROM core_encounter WHERE id=OLD.encounter_id;
 IF state='finalized' THEN RAISE EXCEPTION 'The codes of a finalized document are frozen'; END IF;
 IF TG_OP='DELETE' THEN
  IF OLD.accepted_by_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM core_redactiontombstone WHERE target_id=OLD.encounter_id)
  THEN RAISE EXCEPTION 'An accepted code is never deleted; its acceptance is withdrawn first'; END IF;
  RETURN OLD;
 END IF;
 IF NEW.encounter_id IS DISTINCT FROM OLD.encounter_id OR NEW.terminology_id IS DISTINCT FROM OLD.terminology_id
    OR NEW.release_sha256 IS DISTINCT FROM OLD.release_sha256 OR NEW.evidence IS DISTINCT FROM OLD.evidence
    OR NEW.explanation IS DISTINCT FROM OLD.explanation OR NEW.created_at IS DISTINCT FROM OLD.created_at
 THEN RAISE EXCEPTION 'A code suggestion keeps its code, release identity and evidence'; END IF;
 RETURN NEW;
END; $$;
CREATE TRIGGER terminology_release_append_only BEFORE UPDATE OR DELETE ON core_codeset FOR EACH ROW EXECUTE FUNCTION quillmd_append_only();
CREATE TRIGGER terminology_release_no_truncate BEFORE TRUNCATE ON core_codeset FOR EACH STATEMENT EXECUTE FUNCTION quillmd_preservation_no_truncate();
CREATE TRIGGER terminology_code_append_only BEFORE UPDATE OR DELETE ON core_code FOR EACH ROW EXECUTE FUNCTION quillmd_append_only();
CREATE TRIGGER terminology_code_no_truncate BEFORE TRUNCATE ON core_code FOR EACH STATEMENT EXECUTE FUNCTION quillmd_preservation_no_truncate();
CREATE TRIGGER code_ledger BEFORE INSERT OR UPDATE OR DELETE ON core_codesuggestion FOR EACH ROW EXECUTE FUNCTION quillmd_coding_guard();
'''

REVERSE = '''DO $$ BEGIN IF EXISTS(SELECT 1 FROM core_codesuggestion WHERE release_sha256<>'' OR review_required)
THEN RAISE EXCEPTION 'Coding ledger evidence requires a forward migration'; END IF; END; $$;
DROP TRIGGER terminology_release_append_only ON core_codeset;
DROP TRIGGER terminology_release_no_truncate ON core_codeset;
DROP TRIGGER terminology_code_append_only ON core_code;
DROP TRIGGER terminology_code_no_truncate ON core_code;
DROP TRIGGER code_ledger ON core_codesuggestion;
DROP FUNCTION quillmd_coding_guard();'''

_0033 = importlib.import_module('core.migrations.0033_redaction_tombstone')


def refuse_a_rollback_0031_refuses(apps, schema_editor):
    """Reverse only, and first: 0031's R1 count of v3 mapping evidence (through 0032's check), raised here at the leaf so a
    rollback 0031 would refuse reverses nothing, this migration included. Counts only."""
    try:
        _0033._0032.refuse_a_rollback_0031_refuses(apps, schema_editor)
    except IrreversibleError as refused:
        raise IrreversibleError(f'{refused} The refusal was raised at the leaf, 0034_coding_ledger, before it was reversed '
                                'either.') from None


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0033_redaction_tombstone'),
    ]

    operations = [
        migrations.AddField(
            model_name='codesuggestion',
            name='release_sha256',
            field=models.CharField(blank=True, db_default='', default='', max_length=64),
        ),
        migrations.AddField(
            model_name='codesuggestion',
            name='review_required',
            field=models.BooleanField(db_default=False, default=False),
        ),
        migrations.RunSQL(SQL, REVERSE),
        # Last, so that on the way back it runs FIRST, before any trigger, function or column is dropped.
        migrations.RunPython(migrations.RunPython.noop, refuse_a_rollback_0031_refuses),
    ]
