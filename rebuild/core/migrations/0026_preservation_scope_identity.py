from django.db import migrations
import importlib

SQL='''
CREATE OR REPLACE FUNCTION quillmd_preserve_clinical_row() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE prior jsonb; dept uuid; pat uuid; enc uuid; org uuid; held jsonb; matched uuid[];
BEGIN
 IF current_setting('transaction_isolation') <> 'read committed' THEN
  RAISE EXCEPTION 'Preservation requires read committed isolation';
 END IF;
 PERFORM pg_advisory_xact_lock(716849203517);
 prior=to_jsonb(OLD);
 IF TG_TABLE_NAME='core_encounter' THEN
  IF TG_OP='DELETE' AND OLD.status='finalized' THEN RAISE EXCEPTION 'Finalized document cannot be deleted'; END IF;
  dept=OLD.department_id; pat=OLD.patient_id; enc=OLD.id;
 ELSIF TG_TABLE_NAME='core_patient' THEN dept=OLD.department_id; pat=OLD.id;
 ELSIF TG_TABLE_NAME='core_template' THEN dept=OLD.department_id;
 ELSIF TG_TABLE_NAME='core_department' THEN dept=OLD.id; org=OLD.organization_id;
 ELSIF TG_TABLE_NAME='core_job' THEN
  enc=OLD.encounter_id;
  IF enc IS NULL THEN
   SELECT t.department_id INTO dept FROM core_templateversion v JOIN core_template t ON t.id=v.template_id WHERE v.id=OLD.mapping_version_id;
  END IF;
 ELSIF TG_TABLE_NAME='core_codesuggestion' THEN enc=OLD.encounter_id;
 END IF;
 IF enc IS NOT NULL AND dept IS NULL THEN SELECT department_id,patient_id INTO dept,pat FROM core_encounter WHERE id=enc; END IF;
 IF org IS NULL AND dept IS NOT NULL THEN SELECT organization_id INTO org FROM core_department WHERE id=dept; END IF;
 -- Historical identity remains fixed: releasing a hold is not an instruction
 -- to transfer its evidence to another patient/department. Include ancestor
 -- metadata whose movement would detach a held descendant from its old scope.
 SELECT array_agg(h.id ORDER BY h.id) INTO matched FROM core_retentionhold h
 WHERE h.scope='global' OR h.organization_id=org OR h.department_id=dept OR h.patient_id=pat OR h.encounter_id=enc
 OR (TG_TABLE_NAME='core_patient' AND h.encounter_id IN (SELECT id FROM core_encounter WHERE patient_id=pat))
 OR (TG_TABLE_NAME='core_department' AND (
   h.patient_id IN (SELECT id FROM core_patient WHERE department_id=dept)
   OR h.encounter_id IN (SELECT id FROM core_encounter WHERE department_id=dept)))
 OR (TG_TABLE_NAME='core_template' AND (
   h.encounter_id IN (SELECT e.id FROM core_encounter e JOIN core_templateversion v ON v.id=e.template_version_id WHERE v.template_id=OLD.id)
   OR h.patient_id IN (SELECT e.patient_id FROM core_encounter e JOIN core_templateversion v ON v.id=e.template_version_id WHERE v.template_id=OLD.id)));
 IF matched IS NOT NULL AND TG_OP='UPDATE' AND (
    (prior->'department_id') IS DISTINCT FROM (to_jsonb(NEW)->'department_id') OR
    (prior->'organization_id') IS DISTINCT FROM (to_jsonb(NEW)->'organization_id') OR
    (prior->'patient_id') IS DISTINCT FROM (to_jsonb(NEW)->'patient_id') OR
    (prior->'encounter_id') IS DISTINCT FROM (to_jsonb(NEW)->'encounter_id') OR
    (prior->'mapping_version_id') IS DISTINCT FROM (to_jsonb(NEW)->'mapping_version_id')
 ) THEN RAISE EXCEPTION 'Preserved clinical scope cannot move'; END IF;
 SELECT jsonb_agg(h.id ORDER BY h.id) INTO held FROM core_retentionhold h
 WHERE h.id=ANY(matched) AND NOT EXISTS (SELECT 1 FROM core_retentionholdrelease r WHERE r.hold_id=h.id);
 IF held IS NOT NULL THEN
  INSERT INTO core_preservedrecord(id,created_at,source_table,source_id,operation,hold_ids,prior_record)
   VALUES(gen_random_uuid(),clock_timestamp(),TG_TABLE_NAME,OLD.id,TG_OP,held,prior);
 END IF;
 IF TG_OP='DELETE' THEN RETURN OLD; END IF;
 RETURN NEW;
END; $$;
'''

# Preserve every earlier migration and refuse reversal once evidence exists.
_previous=importlib.import_module('core.migrations.0025_preservation_guards')
REVERSE=(_previous.REVERSE.split('DROP TRIGGER',1)[0]+
    'CREATE OR REPLACE FUNCTION quillmd_preserve_clinical_row()'+_previous.SQL.split('CREATE FUNCTION quillmd_preserve_clinical_row()',1)[1].split('CREATE TRIGGER',1)[0])

class Migration(migrations.Migration):
    dependencies=[('core','0025_preservation_guards')]
    operations=[migrations.RunSQL(SQL,REVERSE)]
