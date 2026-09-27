from django.db import migrations

SQL='''
CREATE FUNCTION quillmd_preservation_no_truncate() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'Preservation and clinical records cannot be truncated'; END; $$;
CREATE FUNCTION quillmd_hold_instruction() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE maker uuid;
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
 IF NEW.authority_sha256 !~ '^[0-9a-f]{64}$' OR NOT EXISTS (
  SELECT 1 FROM core_user WHERE id=NEW.created_by_id AND is_active AND is_staff AND verified_at IS NOT NULL
 ) THEN RAISE EXCEPTION 'Invalid preservation authority'; END IF;
 IF TG_TABLE_NAME='core_retentionholdrelease' THEN
  SELECT created_by_id INTO maker FROM core_retentionhold WHERE id=NEW.hold_id;
  IF maker IS NULL OR maker=NEW.created_by_id THEN RAISE EXCEPTION 'A second custodian must release preservation'; END IF;
 END IF;
 RETURN NEW;
END; $$;

CREATE FUNCTION quillmd_preserve_clinical_row() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE prior jsonb; dept uuid; pat uuid; enc uuid; org uuid; held jsonb;
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
 SELECT jsonb_agg(h.id ORDER BY h.id) INTO held FROM core_retentionhold h
 WHERE NOT EXISTS (SELECT 1 FROM core_retentionholdrelease r WHERE r.hold_id=h.id)
 AND (h.scope='global' OR h.organization_id=org OR h.department_id=dept OR h.patient_id=pat OR h.encounter_id=enc);
 IF held IS NOT NULL THEN
  -- A move cannot detach future changes from the original hold scope.
  IF TG_OP='UPDATE' AND (
    (prior->'department_id') IS DISTINCT FROM (to_jsonb(NEW)->'department_id') OR
    (prior->'organization_id') IS DISTINCT FROM (to_jsonb(NEW)->'organization_id') OR
    (prior->'patient_id') IS DISTINCT FROM (to_jsonb(NEW)->'patient_id') OR
    (prior->'encounter_id') IS DISTINCT FROM (to_jsonb(NEW)->'encounter_id') OR
    (prior->'mapping_version_id') IS DISTINCT FROM (to_jsonb(NEW)->'mapping_version_id')
  ) THEN RAISE EXCEPTION 'Held clinical scope cannot move'; END IF;
  INSERT INTO core_preservedrecord(id,created_at,source_table,source_id,operation,hold_ids,prior_record)
   VALUES(gen_random_uuid(),clock_timestamp(),TG_TABLE_NAME,OLD.id,TG_OP,held,prior);
 END IF;
 IF TG_OP='DELETE' THEN RETURN OLD; END IF;
 RETURN NEW;
END; $$;

CREATE TRIGGER retention_hold_insert BEFORE INSERT ON core_retentionhold FOR EACH ROW EXECUTE FUNCTION quillmd_hold_instruction();
CREATE TRIGGER retention_release_insert BEFORE INSERT ON core_retentionholdrelease FOR EACH ROW EXECUTE FUNCTION quillmd_hold_instruction();
CREATE TRIGGER retention_hold_append_only BEFORE UPDATE OR DELETE ON core_retentionhold FOR EACH ROW EXECUTE FUNCTION quillmd_append_only();
CREATE TRIGGER retention_release_append_only BEFORE UPDATE OR DELETE ON core_retentionholdrelease FOR EACH ROW EXECUTE FUNCTION quillmd_append_only();
CREATE TRIGGER preserved_record_append_only BEFORE UPDATE OR DELETE ON core_preservedrecord FOR EACH ROW EXECUTE FUNCTION quillmd_append_only();
CREATE TRIGGER preserved_file_append_only BEFORE UPDATE OR DELETE ON core_preservedfile FOR EACH ROW EXECUTE FUNCTION quillmd_append_only();
CREATE TRIGGER retention_hold_no_truncate BEFORE TRUNCATE ON core_retentionhold FOR EACH STATEMENT EXECUTE FUNCTION quillmd_preservation_no_truncate();
CREATE TRIGGER retention_release_no_truncate BEFORE TRUNCATE ON core_retentionholdrelease FOR EACH STATEMENT EXECUTE FUNCTION quillmd_preservation_no_truncate();
CREATE TRIGGER preserved_record_no_truncate BEFORE TRUNCATE ON core_preservedrecord FOR EACH STATEMENT EXECUTE FUNCTION quillmd_preservation_no_truncate();
CREATE TRIGGER preserved_file_no_truncate BEFORE TRUNCATE ON core_preservedfile FOR EACH STATEMENT EXECUTE FUNCTION quillmd_preservation_no_truncate();
CREATE TRIGGER encounter_preservation BEFORE UPDATE OR DELETE ON core_encounter FOR EACH ROW EXECUTE FUNCTION quillmd_preserve_clinical_row();
CREATE TRIGGER patient_preservation BEFORE UPDATE OR DELETE ON core_patient FOR EACH ROW EXECUTE FUNCTION quillmd_preserve_clinical_row();
CREATE TRIGGER template_preservation BEFORE UPDATE OR DELETE ON core_template FOR EACH ROW EXECUTE FUNCTION quillmd_preserve_clinical_row();
CREATE TRIGGER department_preservation BEFORE UPDATE OR DELETE ON core_department FOR EACH ROW EXECUTE FUNCTION quillmd_preserve_clinical_row();
CREATE TRIGGER job_preservation BEFORE UPDATE OR DELETE ON core_job FOR EACH ROW EXECUTE FUNCTION quillmd_preserve_clinical_row();
CREATE TRIGGER code_preservation BEFORE UPDATE OR DELETE ON core_codesuggestion FOR EACH ROW EXECUTE FUNCTION quillmd_preserve_clinical_row();
CREATE TRIGGER encounter_no_truncate BEFORE TRUNCATE ON core_encounter FOR EACH STATEMENT EXECUTE FUNCTION quillmd_preservation_no_truncate();
CREATE TRIGGER patient_no_truncate BEFORE TRUNCATE ON core_patient FOR EACH STATEMENT EXECUTE FUNCTION quillmd_preservation_no_truncate();
CREATE TRIGGER template_no_truncate BEFORE TRUNCATE ON core_template FOR EACH STATEMENT EXECUTE FUNCTION quillmd_preservation_no_truncate();
CREATE TRIGGER department_no_truncate BEFORE TRUNCATE ON core_department FOR EACH STATEMENT EXECUTE FUNCTION quillmd_preservation_no_truncate();
CREATE TRIGGER job_no_truncate BEFORE TRUNCATE ON core_job FOR EACH STATEMENT EXECUTE FUNCTION quillmd_preservation_no_truncate();
CREATE TRIGGER code_no_truncate BEFORE TRUNCATE ON core_codesuggestion FOR EACH STATEMENT EXECUTE FUNCTION quillmd_preservation_no_truncate();
'''

# No instruction or evidence may be erased to make rollback easier. An empty
# installation can reverse normally; an admitted hold needs a forward repair.
REVERSE='''DO $$ BEGIN
 IF EXISTS(SELECT 1 FROM core_retentionhold) OR EXISTS(SELECT 1 FROM core_retentionholdrelease)
 OR EXISTS(SELECT 1 FROM core_preservedrecord) OR EXISTS(SELECT 1 FROM core_preservedfile)
 THEN RAISE EXCEPTION 'Preservation evidence prevents migration reversal'; END IF;
END; $$;
'''
for _statement in SQL.split(';'):
    if 'CREATE TRIGGER ' in _statement:
        _words=_statement.split()
        _start=_words.index('TRIGGER');_on=_words.index('ON')
        REVERSE+='DROP TRIGGER '+_words[_start+1]+' ON '+_words[_on+1]+';\n'
REVERSE+='DROP FUNCTION quillmd_hold_instruction(); DROP FUNCTION quillmd_preserve_clinical_row(); DROP FUNCTION IF EXISTS quillmd_preservation_no_truncate();'

class Migration(migrations.Migration):
    dependencies=[('core','0024_preserved_file')]
    operations=[migrations.RunSQL(SQL,REVERSE)]
