"""Redaction tombstones: one unfinalized document's clinical content removed while its accounting skeleton stays.

A document with jobs, a generation batch or code suggestions cannot be deleted (every reference to an encounter is
PROTECT). core.redaction removes its content instead and records who, when and why here:

- core_redactionrequest: a verified custodian's request naming the exact content by its digest, for an unfinalized
  document of its own department. Append-only.
- core_redactiontombstone: the executed redaction, holding the signed independent-journal entry verbatim (two distinct
  custodians, the reason hash, the removed files' storage keys and digests). Scalar identities, as for a disposition
  tombstone (0030), so a restore of an older backup can import it from the journal without the request row. Refused
  while an unreleased retention hold covers the document, and for a finalized one. Append-only.
- quillmd_redaction_guard on core_encounter (BEFORE INSERT OR UPDATE): a document with a tombstone keeps status
  'redacted' and empty notes, answers, review state and export, so its content cannot come back by an edit or by a
  reconcile that inserts the row again. On core_job, core_generationbatch and core_codesuggestion (BEFORE INSERT): no
  new clinical work for a redacted document.

Reversal refuses while any redaction request or tombstone exists. Like 0032, it refuses first with 0031's own message
while v3 mapping evidence exists, so a rollback that 0031 would refuse reverses nothing (R1). It adds tables, one
function and triggers only; no existing row or function changes.
"""
import importlib

import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models
from django.db.migrations.exceptions import IrreversibleError

SQL = '''CREATE FUNCTION quillmd_redaction_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE target core_encounter; body jsonb; org uuid;
BEGIN
 IF current_setting('transaction_isolation') <> 'read committed' THEN
  RAISE EXCEPTION 'Redaction requires read committed isolation';
 END IF;
 IF TG_TABLE_NAME='core_redactionrequest' THEN
  IF NOT EXISTS(SELECT 1 FROM core_user WHERE id=NEW.created_by_id AND is_active AND is_staff AND verified_at IS NOT NULL)
  THEN RAISE EXCEPTION 'A verified redaction custodian is required'; END IF;
  SELECT * INTO target FROM core_encounter WHERE id=NEW.encounter_id;
  IF target.id IS NULL OR target.department_id IS DISTINCT FROM NEW.department_id OR target.status NOT IN ('draft','review')
     OR NEW.reason_sha256 !~ '^[0-9a-f]{64}$' OR NEW.content_sha256 !~ '^[0-9a-f]{64}$'
  THEN RAISE EXCEPTION 'Only an unfinalized document of its own department can be requested for redaction'; END IF;
  RETURN NEW;
 END IF;
 IF TG_TABLE_NAME='core_redactiontombstone' THEN
  -- Source row first, then the preservation lock: the global lock order of core/retention.py.
  PERFORM id FROM core_encounter WHERE id=NEW.target_id FOR UPDATE;
  PERFORM pg_advisory_xact_lock(716849203517);
  body=NEW.journal_entry->'body'->'redaction';
  IF NEW.entry_sha256 !~ '^[0-9a-f]{64}$' OR COALESCE(NEW.journal_entry->>'signature','') !~ '^[0-9a-f]{128}$'
     OR NEW.journal_entry->'body'->>'contract' IS DISTINCT FROM 'redaction-journal-entry-v1'
     OR body->>'id' IS DISTINCT FROM NEW.id::text OR body->>'target_id' IS DISTINCT FROM NEW.target_id::text
     OR body->>'department_id' IS DISTINCT FROM NEW.department_id::text
     OR body->>'request_id' IS DISTINCT FROM NEW.request_id::text
     OR body->>'content_sha256' IS DISTINCT FROM NEW.content_sha256 OR (body->'files') IS DISTINCT FROM NEW.files
     OR body->>'requested_by' IS NOT DISTINCT FROM body->>'approved_by'
  THEN RAISE EXCEPTION 'Invalid redaction tombstone identity'; END IF;
  SELECT * INTO target FROM core_encounter WHERE id=NEW.target_id;
  IF target.id IS NOT NULL THEN
   IF target.status NOT IN ('draft','review') OR target.department_id IS DISTINCT FROM NEW.department_id
   THEN RAISE EXCEPTION 'Only an unfinalized document of its own department can be redacted'; END IF;
   SELECT organization_id INTO org FROM core_department WHERE id=target.department_id;
   IF EXISTS(SELECT 1 FROM core_retentionhold h WHERE NOT EXISTS(SELECT 1 FROM core_retentionholdrelease r WHERE r.hold_id=h.id)
      AND (h.scope='global' OR h.organization_id=org OR h.department_id=target.department_id
           OR h.patient_id=target.patient_id OR h.encounter_id=target.id))
   THEN RAISE EXCEPTION 'A retention hold applies; this content cannot be redacted'; END IF;
  END IF;
  RETURN NEW;
 END IF;
 IF TG_TABLE_NAME='core_encounter' THEN
  IF EXISTS(SELECT 1 FROM core_redactiontombstone WHERE target_id=NEW.id) AND (NEW.status IS DISTINCT FROM 'redacted'
     OR NEW.notes<>'' OR NEW.answers IS DISTINCT FROM '{}'::jsonb OR NEW.template_review IS DISTINCT FROM '{}'::jsonb
     OR NEW.export_path<>'' OR NEW.export_sha256<>'')
  THEN RAISE EXCEPTION 'A redacted document cannot regain clinical content'; END IF;
  RETURN NEW;
 END IF;
 IF NEW.encounter_id IS NOT NULL THEN
  PERFORM id FROM core_encounter WHERE id=NEW.encounter_id FOR KEY SHARE;
  IF EXISTS(SELECT 1 FROM core_redactiontombstone WHERE target_id=NEW.encounter_id)
  THEN RAISE EXCEPTION 'A redacted document cannot acquire clinical work'; END IF;
 END IF;
 RETURN NEW;
END; $$;
CREATE TRIGGER redactionrequest_insert BEFORE INSERT ON core_redactionrequest FOR EACH ROW EXECUTE FUNCTION quillmd_redaction_guard();
CREATE TRIGGER redactionrequest_append_only BEFORE UPDATE OR DELETE ON core_redactionrequest FOR EACH ROW EXECUTE FUNCTION quillmd_append_only();
CREATE TRIGGER redactionrequest_no_truncate BEFORE TRUNCATE ON core_redactionrequest FOR EACH STATEMENT EXECUTE FUNCTION quillmd_preservation_no_truncate();
CREATE TRIGGER redactiontombstone_insert BEFORE INSERT ON core_redactiontombstone FOR EACH ROW EXECUTE FUNCTION quillmd_redaction_guard();
CREATE TRIGGER redactiontombstone_append_only BEFORE UPDATE OR DELETE ON core_redactiontombstone FOR EACH ROW EXECUTE FUNCTION quillmd_append_only();
CREATE TRIGGER redactiontombstone_no_truncate BEFORE TRUNCATE ON core_redactiontombstone FOR EACH STATEMENT EXECUTE FUNCTION quillmd_preservation_no_truncate();
CREATE TRIGGER encounter_redaction BEFORE INSERT OR UPDATE ON core_encounter FOR EACH ROW EXECUTE FUNCTION quillmd_redaction_guard();
CREATE TRIGGER job_redaction BEFORE INSERT ON core_job FOR EACH ROW EXECUTE FUNCTION quillmd_redaction_guard();
CREATE TRIGGER batch_redaction BEFORE INSERT ON core_generationbatch FOR EACH ROW EXECUTE FUNCTION quillmd_redaction_guard();
CREATE TRIGGER code_redaction BEFORE INSERT ON core_codesuggestion FOR EACH ROW EXECUTE FUNCTION quillmd_redaction_guard();
'''

REVERSE = '''DO $$ BEGIN IF EXISTS(SELECT 1 FROM core_redactionrequest) OR EXISTS(SELECT 1 FROM core_redactiontombstone)
THEN RAISE EXCEPTION 'Redaction evidence requires a forward migration'; END IF; END; $$;
DROP TRIGGER redactionrequest_insert ON core_redactionrequest;
DROP TRIGGER redactionrequest_append_only ON core_redactionrequest;
DROP TRIGGER redactionrequest_no_truncate ON core_redactionrequest;
DROP TRIGGER redactiontombstone_insert ON core_redactiontombstone;
DROP TRIGGER redactiontombstone_append_only ON core_redactiontombstone;
DROP TRIGGER redactiontombstone_no_truncate ON core_redactiontombstone;
DROP TRIGGER encounter_redaction ON core_encounter;
DROP TRIGGER job_redaction ON core_job;
DROP TRIGGER batch_redaction ON core_generationbatch;
DROP TRIGGER code_redaction ON core_codesuggestion;
DROP FUNCTION quillmd_redaction_guard();'''

_0032 = importlib.import_module('core.migrations.0032_restore_hold_replay_admission')


def refuse_a_rollback_0031_refuses(apps, schema_editor):
    """Reverse only, and first: 0032's own R1 check (0031's count of v3 mapping evidence), raised here at the leaf so a
    rollback 0031 would refuse reverses nothing, this migration included. Counts only."""
    try:
        _0032.refuse_a_rollback_0031_refuses(apps, schema_editor)
    except IrreversibleError as refused:
        raise IrreversibleError(f'{refused} The refusal was raised at the leaf, 0033_redaction_tombstone, before it was '
                                'reversed either.') from None


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0032_restore_hold_replay_admission'),
    ]

    operations = [
        migrations.CreateModel(
            name='RedactionRequest',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('reason_sha256', models.CharField(max_length=64)),
                ('content_sha256', models.CharField(max_length=64)),
                ('request_key', models.UUIDField(unique=True)),
                ('created_by', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='+', to=settings.AUTH_USER_MODEL)),
                ('department', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='+', to='core.department')),
                ('encounter', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='+', to='core.encounter')),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='RedactionTombstone',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('target_id', models.UUIDField(unique=True)),
                ('department_id', models.UUIDField()),
                ('request_id', models.UUIDField(unique=True)),
                ('content_sha256', models.CharField(max_length=64)),
                ('files', models.JSONField()),
                ('journal_entry', models.JSONField()),
                ('entry_sha256', models.CharField(max_length=64, unique=True)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.RunSQL(SQL, REVERSE),
        # Last, so that on the way back it runs FIRST, before any trigger, function or table is dropped.
        migrations.RunPython(migrations.RunPython.noop, refuse_a_rollback_0031_refuses),
    ]
