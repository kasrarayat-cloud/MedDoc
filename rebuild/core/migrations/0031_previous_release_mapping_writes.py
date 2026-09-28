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
  this code was re-installed that draft was finalized and exported (this code checks confirmation only in its form).
  quillmd_encounter_guard, already run BEFORE INSERT OR UPDATE on core_encounter, now also refuses a new document, or
  a document moved, onto an unconfirmed v3 mapping. Confirmations are append-only, so a confirmed mapping stays usable.

Reversing loses nothing: it drops the three defaults and the constraint and restores 0003's encounter guard body, and no
row changes.
"""
import importlib

from django.db import migrations, models

GATE = """CREATE OR REPLACE FUNCTION quillmd_encounter_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE patient_department uuid; template_department uuid; placed boolean;
BEGIN
 IF TG_OP='UPDATE' AND OLD.status='finalized' THEN RAISE EXCEPTION 'Finalized document is immutable'; END IF;
 SELECT department_id INTO patient_department FROM core_patient WHERE id=NEW.patient_id;
 SELECT t.department_id INTO template_department FROM core_template t JOIN core_templateversion v ON v.template_id=t.id WHERE v.id=NEW.template_version_id;
 IF NEW.department_id IS DISTINCT FROM patient_department OR NEW.department_id IS DISTINCT FROM template_department THEN RAISE EXCEPTION 'Department mismatch'; END IF;
 IF TG_OP='INSERT' THEN placed=true; ELSE placed=NEW.template_version_id IS DISTINCT FROM OLD.template_version_id; END IF;
 IF placed AND EXISTS(SELECT 1 FROM core_templateversion v WHERE v.id=NEW.template_version_id AND v.contract='v3'
     AND NOT EXISTS(SELECT 1 FROM core_mappingconfirmation c WHERE c.version_id=v.id))
 THEN RAISE EXCEPTION 'An unconfirmed contract v3 mapping cannot start a document'; END IF;
 RETURN NEW;
END; $$;"""

# The reverse restores 0003's reviewed body, read from 0003 itself rather than restated here.
_0003 = importlib.import_module('core.migrations.0003_immutable_records')
UNGATE = ('CREATE OR REPLACE FUNCTION quillmd_encounter_guard()'
          + _0003.SQL.split('CREATE FUNCTION quillmd_encounter_guard()', 1)[1].split('CREATE TRIGGER encounter_scope', 1)[0])


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
    ]
