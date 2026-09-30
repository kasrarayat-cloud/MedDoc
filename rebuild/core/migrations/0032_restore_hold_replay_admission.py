"""Journaled holds replayed into a quarantined restore, and the append-only restore admission (1a, 1d).

- core_retentionholdreplay is the imported-hold marker: one row per journaled hold or release replayed into a
  quarantined restored database, with the outcome that database now holds for it. A release is recorded only after its
  hold's own marker. 'target_absent' is accepted only while the journaled target row is absent here; 'present' only
  when the matching row exists; 'imported' only before the row it announces.
- core_restoreadmission is the record against which quarantine may be lifted. The database re-checks what it can see:
  a passing restore check and complete replay claimed in the report, the checkpoint naming the recorded journal head,
  and every hold or release a marker says was imported or present actually here. Signatures are checked by the
  application against independently configured keys, as for tombstones (0030).
- quillmd_hold_instruction keeps 0025's body and adds one path: a hold replayed from the journal keeps its journaled
  custodian, whose account may be inactive in an older restored database, when its 'imported' marker (inserted first)
  names exactly this hold. A release never takes that path; it still needs an active second custodian.

Reversal refuses while any replay marker or admission exists. It also refuses first, with 0031's own message, while v3
mapping evidence exists: every rollback toward the previous release is refused at 0031, and refusing here keeps that
refusal from reversing and committing this migration first (R1: a refused rollback reverses nothing). A code rollback to
the release before this one needs no schema reversal: this migration only adds tables, triggers and one function path.
"""
import importlib

import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models
from django.db.migrations.exceptions import IrreversibleError

SQL = '''CREATE FUNCTION quillmd_restore_import() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE body jsonb; held jsonb; present boolean;
BEGIN
 IF current_setting('transaction_isolation') <> 'read committed' THEN
  RAISE EXCEPTION 'Restore import requires read committed isolation';
 END IF;
 PERFORM pg_advisory_xact_lock(716849203517);
 IF NOT EXISTS(SELECT 1 FROM core_user WHERE id=NEW.created_by_id AND is_active AND is_staff AND verified_at IS NOT NULL)
 THEN RAISE EXCEPTION 'A verified restore custodian is required'; END IF;
 IF TG_TABLE_NAME='core_restoreadmission' THEN
  IF NEW.report->>'contract' IS DISTINCT FROM 'restore-admission-v1'
     OR NEW.report->>'instance_id' IS DISTINCT FROM NEW.instance_id::text
     OR (NEW.report->'admissible') IS DISTINCT FROM 'true'::jsonb
     OR (NEW.report->'restore_check'->'passed') IS DISTINCT FROM 'true'::jsonb
     OR (NEW.report->'restore_check'->'holds'->'missing') IS DISTINCT FROM '0'::jsonb
     OR (NEW.report->'missing_holds') IS DISTINCT FROM '0'::jsonb
     OR (NEW.report->'unreplayed') IS DISTINCT FROM '0'::jsonb
     OR (NEW.report->'visible_targets') IS DISTINCT FROM '0'::jsonb
     OR (NEW.report->'journal'->'sequence') IS DISTINCT FROM to_jsonb(NEW.journal_sequence)
     OR NEW.report->'journal'->>'head_sha256' IS DISTINCT FROM NEW.journal_head_sha256
     OR (NEW.checkpoint->'body'->'sequence') IS DISTINCT FROM to_jsonb(NEW.journal_sequence)
     OR NEW.checkpoint->'body'->>'head_sha256' IS DISTINCT FROM NEW.journal_head_sha256
     OR NEW.checkpoint->'body'->>'contract' IS DISTINCT FROM 'disposition-journal-checkpoint-v1'
     OR COALESCE(NEW.checkpoint->>'signature','') !~ '^[0-9a-f]{128}$'
     OR NEW.journal_head_sha256 !~ '^[0-9a-f]{64}$' OR NEW.report_sha256 !~ '^[0-9a-f]{64}$'
     OR EXISTS(SELECT 1 FROM core_retentionholdreplay r WHERE r.event='hold' AND r.outcome IN ('imported','present')
               AND NOT EXISTS(SELECT 1 FROM core_retentionhold h WHERE h.id=r.record_id))
     OR EXISTS(SELECT 1 FROM core_retentionholdreplay r WHERE r.event='release' AND r.outcome IN ('imported','present')
               AND NOT EXISTS(SELECT 1 FROM core_retentionholdrelease x WHERE x.id=r.record_id))
  THEN RAISE EXCEPTION 'Restore admission requires a passing check, the verified journal head and complete replay'; END IF;
  RETURN NEW;
 END IF;
 body=NEW.journal_entry->'body';
 IF NEW.entry_sha256 !~ '^[0-9a-f]{64}$' OR COALESCE(NEW.journal_entry->>'signature','') !~ '^[0-9a-f]{128}$'
 THEN RAISE EXCEPTION 'Invalid preservation replay entry'; END IF;
 IF NEW.event='hold' THEN
  held=body->'hold';
  IF body->>'contract' IS DISTINCT FROM 'retention-hold-entry-v1' OR held->>'id' IS DISTINCT FROM NEW.record_id::text
     OR NEW.hold_id IS DISTINCT FROM NEW.record_id
  THEN RAISE EXCEPTION 'Invalid hold replay identity'; END IF;
  IF NEW.outcome='present' THEN
   IF NOT EXISTS(SELECT 1 FROM core_retentionhold h WHERE h.id=NEW.record_id AND h.scope=held->>'scope'
       AND h.authority_sha256=held->>'authority_sha256' AND h.request_key::text=held->>'request_key'
       AND h.created_by_id::text=held->>'created_by'
       AND COALESCE(h.organization_id,h.department_id,h.patient_id,h.encounter_id)::text IS NOT DISTINCT FROM held->>'target_id')
   THEN RAISE EXCEPTION 'A present hold must match its journal entry'; END IF;
  ELSIF NEW.outcome='imported' THEN
   IF EXISTS(SELECT 1 FROM core_retentionhold WHERE id=NEW.record_id)
   THEN RAISE EXCEPTION 'An imported hold is recorded before its row'; END IF;
  ELSIF NEW.outcome='target_absent' THEN
   present = CASE held->>'scope'
     WHEN 'organization' THEN EXISTS(SELECT 1 FROM core_organization WHERE id::text=held->>'target_id')
     WHEN 'department' THEN EXISTS(SELECT 1 FROM core_department WHERE id::text=held->>'target_id')
     WHEN 'patient' THEN EXISTS(SELECT 1 FROM core_patient WHERE id::text=held->>'target_id')
     WHEN 'encounter' THEN EXISTS(SELECT 1 FROM core_encounter WHERE id::text=held->>'target_id')
     ELSE true END;
   IF present OR EXISTS(SELECT 1 FROM core_retentionhold WHERE id=NEW.record_id)
   THEN RAISE EXCEPTION 'Only a hold whose target is absent from this database is recorded without its row'; END IF;
  ELSE RAISE EXCEPTION 'Invalid hold replay outcome'; END IF;
 ELSIF NEW.event='release' THEN
  IF body->>'contract' IS DISTINCT FROM 'retention-release-entry-v1' OR body->'release'->>'id' IS DISTINCT FROM NEW.record_id::text
     OR body->'release'->>'hold_id' IS DISTINCT FROM NEW.hold_id::text
  THEN RAISE EXCEPTION 'Invalid release replay identity'; END IF;
  -- A release replays only after its hold.
  IF NOT EXISTS(SELECT 1 FROM core_retentionholdreplay r WHERE r.record_id=NEW.hold_id AND r.event='hold')
  THEN RAISE EXCEPTION 'A release replays only after its hold'; END IF;
  IF NEW.outcome='present' THEN
   IF NOT EXISTS(SELECT 1 FROM core_retentionholdrelease x WHERE x.id=NEW.record_id AND x.hold_id=NEW.hold_id
       AND x.authority_sha256=body->'release'->>'authority_sha256' AND x.created_by_id::text=body->'release'->>'created_by')
   THEN RAISE EXCEPTION 'A present release must match its journal entry'; END IF;
  ELSIF NEW.outcome='imported' THEN
   IF EXISTS(SELECT 1 FROM core_retentionholdrelease WHERE hold_id=NEW.hold_id)
   THEN RAISE EXCEPTION 'An imported release is recorded before its row'; END IF;
  ELSIF NEW.outcome='deferred' THEN
   IF NOT EXISTS(SELECT 1 FROM core_retentionhold WHERE id=NEW.hold_id)
      OR EXISTS(SELECT 1 FROM core_retentionholdrelease WHERE hold_id=NEW.hold_id)
   THEN RAISE EXCEPTION 'A deferred release leaves its restored hold active'; END IF;
  ELSIF NEW.outcome='target_absent' THEN
   IF NOT EXISTS(SELECT 1 FROM core_retentionholdreplay r WHERE r.record_id=NEW.hold_id AND r.event='hold' AND r.outcome='target_absent')
   THEN RAISE EXCEPTION 'Only the release of an absent target is recorded without its row'; END IF;
  ELSE RAISE EXCEPTION 'Invalid release replay outcome'; END IF;
 ELSE RAISE EXCEPTION 'Invalid preservation replay event'; END IF;
 RETURN NEW;
END; $$;

CREATE OR REPLACE FUNCTION quillmd_hold_instruction() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE maker uuid; imported boolean := false;
BEGIN
 IF current_setting('transaction_isolation') <> 'read committed' THEN
  RAISE EXCEPTION 'Preservation requires read committed isolation';
 END IF;
 -- Match source-row-before-preservation-lock ordering, including direct SQL.
 IF TG_TABLE_NAME='core_retentionhold' THEN
  IF NEW.encounter_id IS NOT NULL THEN PERFORM id FROM core_encounter WHERE id=NEW.encounter_id FOR KEY SHARE; END IF;
  IF NEW.patient_id IS NOT NULL THEN PERFORM id FROM core_patient WHERE id=NEW.patient_id FOR KEY SHARE; END IF;
  IF NEW.department_id IS NOT NULL THEN PERFORM id FROM core_department WHERE id=NEW.department_id FOR KEY SHARE; END IF;
  IF NEW.organization_id IS NOT NULL THEN PERFORM id FROM core_organization WHERE id=NEW.organization_id FOR KEY SHARE; END IF;
 END IF;
 PERFORM pg_advisory_xact_lock(716849203517);
 -- A hold replayed from the independent journal keeps its journaled custodian, whose account may be inactive in an
 -- older restored database: its 'imported' marker, validated by its own guard and inserted first, names this exact
 -- hold. Only a hold (more preservation) takes this path; a release needs an active second custodian here.
 IF TG_TABLE_NAME='core_retentionhold' THEN
  imported := EXISTS(SELECT 1 FROM core_retentionholdreplay r WHERE r.record_id=NEW.id AND r.event='hold'
   AND r.outcome='imported' AND r.journal_entry->'body'->'hold'->>'created_by'=NEW.created_by_id::text
   AND r.journal_entry->'body'->'hold'->>'authority_sha256'=NEW.authority_sha256
   AND r.journal_entry->'body'->'hold'->>'request_key'=NEW.request_key::text
   AND r.journal_entry->'body'->'hold'->>'scope'=NEW.scope
   AND (r.journal_entry->'body'->'hold'->>'target_id') IS NOT DISTINCT FROM
       COALESCE(NEW.organization_id,NEW.department_id,NEW.patient_id,NEW.encounter_id)::text);
 END IF;
 IF NEW.authority_sha256 !~ '^[0-9a-f]{64}$' OR NOT (imported OR EXISTS (
  SELECT 1 FROM core_user WHERE id=NEW.created_by_id AND is_active AND is_staff AND verified_at IS NOT NULL
 )) THEN RAISE EXCEPTION 'Invalid preservation authority'; END IF;
 IF TG_TABLE_NAME='core_retentionholdrelease' THEN
  SELECT created_by_id INTO maker FROM core_retentionhold WHERE id=NEW.hold_id;
  IF maker IS NULL OR maker=NEW.created_by_id THEN RAISE EXCEPTION 'A second custodian must release preservation'; END IF;
 END IF;
 RETURN NEW;
END; $$;

CREATE TRIGGER retentionholdreplay_insert BEFORE INSERT ON core_retentionholdreplay FOR EACH ROW EXECUTE FUNCTION quillmd_restore_import();
CREATE TRIGGER retentionholdreplay_append_only BEFORE UPDATE OR DELETE ON core_retentionholdreplay FOR EACH ROW EXECUTE FUNCTION quillmd_append_only();
CREATE TRIGGER retentionholdreplay_no_truncate BEFORE TRUNCATE ON core_retentionholdreplay FOR EACH STATEMENT EXECUTE FUNCTION quillmd_preservation_no_truncate();
CREATE TRIGGER restoreadmission_insert BEFORE INSERT ON core_restoreadmission FOR EACH ROW EXECUTE FUNCTION quillmd_restore_import();
CREATE TRIGGER restoreadmission_append_only BEFORE UPDATE OR DELETE ON core_restoreadmission FOR EACH ROW EXECUTE FUNCTION quillmd_append_only();
CREATE TRIGGER restoreadmission_no_truncate BEFORE TRUNCATE ON core_restoreadmission FOR EACH STATEMENT EXECUTE FUNCTION quillmd_preservation_no_truncate();
'''

# The reverse restores 0025's reviewed hold guard, read from 0025 itself rather than restated here.
_0025 = importlib.import_module('core.migrations.0025_preservation_guards')
REVERSE = ('''DO $$ BEGIN IF EXISTS(SELECT 1 FROM core_retentionholdreplay) OR EXISTS(SELECT 1 FROM core_restoreadmission)
THEN RAISE EXCEPTION 'Restore replay and admission evidence requires a forward migration'; END IF; END; $$;
DROP TRIGGER retentionholdreplay_insert ON core_retentionholdreplay;
DROP TRIGGER retentionholdreplay_append_only ON core_retentionholdreplay;
DROP TRIGGER retentionholdreplay_no_truncate ON core_retentionholdreplay;
DROP TRIGGER restoreadmission_insert ON core_restoreadmission;
DROP TRIGGER restoreadmission_append_only ON core_restoreadmission;
DROP TRIGGER restoreadmission_no_truncate ON core_restoreadmission;
''' + 'CREATE OR REPLACE FUNCTION quillmd_hold_instruction()'
    + _0025.SQL.split('CREATE FUNCTION quillmd_hold_instruction()', 1)[1].split('CREATE FUNCTION quillmd_preserve_clinical_row()', 1)[0]
    + 'DROP FUNCTION quillmd_restore_import();')
_0021 = importlib.import_module('core.migrations.0021_word_v3_mapping_review')


def refuse_a_rollback_0031_refuses(apps, schema_editor):
    """Reverse only: 0031 refuses every rollback past it while v3 mapping evidence exists, counted exactly as 0021 and
    0031 count it; refuse here first so that refusal reverses nothing (R1). This also refuses a rollback to 0031 itself
    while that evidence exists; a code rollback to the previous candidate needs no schema reversal. Counts only."""
    confirmations, versions = _0021.v3_mapping_evidence(apps, schema_editor.connection.alias)
    if confirmations or versions:
        raise IrreversibleError(
            f'0031_previous_release_mapping_writes cannot be reversed: {confirmations} mapping confirmation(s) and '
            f'{versions} mapping version(s) recorded under a mapping contract or with clinician corrections. Reversing '
            'it removes the database gate that keeps a contract v3 mapping no clinician has confirmed from starting or '
            'finalizing a document, and 0021 cannot be reversed while this evidence exists either. '
            '0032_restore_hold_replay_admission refused this rollback first, so neither 0032 nor 0031 was reversed. A '
            'target of zero also unapplies otp_totp before 0031, which drops every TOTP enrollment: run migrate forward '
            'to the latest migration before starting any release; the supported rollback target is core 0018.')


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0031_previous_release_mapping_writes'),
    ]

    operations = [
        migrations.CreateModel(
            name='RetentionHoldReplay',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('record_id', models.UUIDField(unique=True)),
                ('hold_id', models.UUIDField()),
                ('event', models.CharField(max_length=8)),
                ('outcome', models.CharField(max_length=16)),
                ('journal_entry', models.JSONField()),
                ('entry_sha256', models.CharField(max_length=64, unique=True)),
                ('created_by', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='RestoreAdmission',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('instance_id', models.UUIDField(unique=True)),
                ('checkpoint', models.JSONField()),
                ('journal_sequence', models.PositiveIntegerField()),
                ('journal_head_sha256', models.CharField(max_length=64)),
                ('report', models.JSONField()),
                ('report_sha256', models.CharField(max_length=64)),
                ('created_by', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.RunSQL(SQL, REVERSE),
        # Last, so that on the way back it runs FIRST, before any trigger, function or table is dropped.
        migrations.RunPython(migrations.RunPython.noop, refuse_a_rollback_0031_refuses),
    ]
