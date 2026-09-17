from django.db import migrations
SQL='''
CREATE FUNCTION quillmd_append_only() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'QuillMD audit/ledger records are append-only'; END; $$;
CREATE TRIGGER ledger_append_only BEFORE UPDATE OR DELETE ON core_ledgerentry FOR EACH ROW EXECUTE FUNCTION quillmd_append_only();
CREATE TRIGGER audit_append_only BEFORE UPDATE OR DELETE ON core_auditevent FOR EACH ROW EXECUTE FUNCTION quillmd_append_only();
CREATE TRIGGER usage_append_only BEFORE UPDATE OR DELETE ON core_usage FOR EACH ROW EXECUTE FUNCTION quillmd_append_only();
CREATE TRIGGER mapping_immutable BEFORE UPDATE OR DELETE ON core_templateversion FOR EACH ROW EXECUTE FUNCTION quillmd_append_only();
CREATE FUNCTION quillmd_encounter_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE patient_department uuid; template_department uuid;
BEGIN
 IF TG_OP='UPDATE' AND OLD.status='finalized' THEN RAISE EXCEPTION 'Finalized document is immutable'; END IF;
 SELECT department_id INTO patient_department FROM core_patient WHERE id=NEW.patient_id;
 SELECT t.department_id INTO template_department FROM core_template t JOIN core_templateversion v ON v.template_id=t.id WHERE v.id=NEW.template_version_id;
 IF NEW.department_id IS DISTINCT FROM patient_department OR NEW.department_id IS DISTINCT FROM template_department THEN RAISE EXCEPTION 'Department mismatch'; END IF;
 RETURN NEW;
END; $$;
CREATE TRIGGER encounter_scope BEFORE INSERT OR UPDATE ON core_encounter FOR EACH ROW EXECUTE FUNCTION quillmd_encounter_guard();
'''
REVERSE='''DROP TRIGGER encounter_scope ON core_encounter; DROP FUNCTION quillmd_encounter_guard(); DROP TRIGGER mapping_immutable ON core_templateversion; DROP TRIGGER usage_append_only ON core_usage; DROP TRIGGER audit_append_only ON core_auditevent; DROP TRIGGER ledger_append_only ON core_ledgerentry; DROP FUNCTION quillmd_append_only();'''
class Migration(migrations.Migration):
    dependencies=[('core','0002_job_payer')]
    operations=[migrations.RunSQL(SQL,REVERSE)]
