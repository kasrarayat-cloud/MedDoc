"""Expand-then-contract for the previous release's mapping writes (MIG-1).

The cutover plan allows a code rollback to a release whose migrations are a prefix of those applied. The installed
release dedac162 applies core 0001-0018; on this schema its template upload and mapping edit raised IntegrityError,
because 0021/0022 added TemplateVersion.contract, corrections and assistance NOT NULL, and Django drops an AddField
default once it has backfilled, so the release's INSERT (which omits the three columns) wrote NULL.

- contract, corrections and assistance get DATABASE defaults ('', {}, {}), the values every legacy mapping already
  records. The application's own writes are unchanged: the model default still supplies each value explicitly.
- A version whose fields carry a contract v3 locator must record contract 'v3'. Only v3 inspection makes such fields,
  and this code always records their contract; the previous release does not know the column, and its mapping edit of
  a v3 mapping copies the v3 fields into a new version. With the default alone that row would read as a legacy mapping
  that needs no confirmation (MIG-2's harm, reached without any down-migration). The CHECK refuses it instead.
  Mapping versions are immutable, so checking at INSERT is enough; adding the constraint validates every existing row.
- A contract v3 mapping starts no document until a clinician has confirmed it, whoever writes the row. The previous
  release has no confirmation gate: during a rollback it started a draft on a never-confirmed v3 mapping, and after
  this code was re-installed that draft was finalized and exported (this code checked confirmation only in its form).
  quillmd_encounter_guard, already run BEFORE INSERT OR UPDATE on core_encounter, now also refuses a new document, or
  a document moved, onto an unconfirmed v3 mapping. Confirmations are append-only, so a confirmed mapping stays usable.
- A document on an unconfirmed contract v3 mapping is never finalized, however it was started (R1). A draft started
  while this gate was missing survives re-applying it (the gate fires only when a document is placed), so the same
  guard refuses the move to 'finalized' until a clinician confirms the mapping: a hold, not a refusal to migrate, so the
  clinician's work on the draft is kept and finalizes once the mapping is confirmed. This code's finalize says so first.

Reversing drops the three defaults, the constraint, the gate and the hold (restoring 0003's encounter guard body); no
row changes. It is refused while any v3 mapping evidence exists (0021's own count, R1): 0031 is the first step of every
rollback toward the previous release, and 0021 refused such a rollback only after 0022-0031 had been reversed and
committed, so the gate was gone and the previous release started a draft on a never-confirmed v3 mapping. A database
without that evidence (legacy mappings only) still reverses.
"""
import importlib

from django.db import migrations, models
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
     AND v.contract='v3' AND NOT EXISTS(SELECT 1 FROM core_mappingconfirmation c WHERE c.version_id=v.id)) THEN
  IF placed THEN RAISE EXCEPTION 'An unconfirmed contract v3 mapping cannot start a document'; END IF;
  RAISE EXCEPTION 'A document on an unconfirmed contract v3 mapping cannot be finalized';
 END IF;
 RETURN NEW;
END; $$;"""

# The reverse restores 0003's reviewed body, read from 0003 itself rather than restated here.
_0003 = importlib.import_module('core.migrations.0003_immutable_records')
UNGATE = ('CREATE OR REPLACE FUNCTION quillmd_encounter_guard()'
          + _0003.SQL.split('CREATE FUNCTION quillmd_encounter_guard()', 1)[1].split('CREATE TRIGGER encounter_scope', 1)[0])
_0021 = importlib.import_module('core.migrations.0021_word_v3_mapping_review')


def refuse_to_drop_the_gate(apps, schema_editor):
    """Reverse only: refuse while any v3 mapping evidence exists, counted exactly as 0021 counts it. Counts only."""
    confirmations, versions = _0021.v3_mapping_evidence(apps, schema_editor.connection.alias)
    if confirmations or versions:
        raise IrreversibleError(
            f'0031_previous_release_mapping_writes cannot be reversed: {confirmations} mapping confirmation(s) and '
            f'{versions} mapping version(s) recorded under a mapping contract or with clinician corrections. Reversing '
            'it removes the database gate that keeps a contract v3 mapping no clinician has confirmed from starting or '
            'finalizing a document, and 0021 cannot be reversed while this evidence exists either. 0031 was not '
            'reversed and its defaults, constraint and gate are in place; any migration after 0031 that was applied has '
            'already been reversed and stays reversed: run migrate forward to the latest migration before starting any '
            'release. A target of zero also unapplies otp_totp before 0031, which drops every TOTP enrollment; the '
            'supported rollback target is core 0018.')


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0030_empty_draft_disposition'),
    ]

    operations = [
        migrations.AlterField(
            model_name='templateversion',
            name='contract',
            field=models.CharField(blank=True, db_default='', default='', max_length=12),
        ),
        migrations.AlterField(
            model_name='templateversion',
            name='corrections',
            field=models.JSONField(blank=True, db_default={}, default=dict),
        ),
        migrations.AlterField(
            model_name='templateversion',
            name='assistance',
            field=models.JSONField(blank=True, db_default={}, default=dict),
        ),
        migrations.AddConstraint(
            model_name='templateversion',
            constraint=models.CheckConstraint(
                condition=models.Q(('contract', 'v3'), models.Q(('fields__contains', [{'locator': {'contract': 'v3'}}]),
                                                                _negated=True), _connector='OR'),
                name='mapping_v3_fields_record_v3_contract'),
        ),
        migrations.RunSQL(GATE, UNGATE),
        # Last, so that on the way back it runs FIRST, before the gate, the constraint or any default is dropped.
        migrations.RunPython(migrations.RunPython.noop, refuse_to_drop_the_gate),
    ]
