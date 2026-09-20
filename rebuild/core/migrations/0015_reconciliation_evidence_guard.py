from django.db import migrations


SQL = """
CREATE FUNCTION quillmd_reconciliation_evidence_guard() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'QuillMD reconciliation evidence is append-only';
    END IF;
    IF (to_jsonb(NEW) - 'ledger_status') IS DISTINCT FROM
       (to_jsonb(OLD) - 'ledger_status') THEN
        RAISE EXCEPTION 'QuillMD reconciliation evidence is immutable';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER reconciliation_evidence_immutable
BEFORE UPDATE OR DELETE ON core_costreconciliation
FOR EACH ROW EXECUTE FUNCTION quillmd_reconciliation_evidence_guard();
"""

REVERSE = """
DROP TRIGGER reconciliation_evidence_immutable ON core_costreconciliation;
DROP FUNCTION quillmd_reconciliation_evidence_guard();
"""


class Migration(migrations.Migration):
    dependencies = [('core', '0014_encounter_service_date')]
    # No historical row is updated. Existing ledger-status updates keep working.
    operations = [migrations.RunSQL(SQL, REVERSE)]
