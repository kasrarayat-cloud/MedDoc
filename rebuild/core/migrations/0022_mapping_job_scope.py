"""Add blank-template jobs without a synthetic patient or a second financial ledger."""
from django.db import migrations, models
import django.db.models.deletion

SCOPE = '''
CREATE FUNCTION quillmd_mapping_job_scope_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE source_hash text; scope_id uuid;
BEGIN
 IF TG_OP='UPDATE' AND (NEW.encounter_id IS DISTINCT FROM OLD.encounter_id
   OR NEW.mapping_version_id IS DISTINCT FROM OLD.mapping_version_id OR NEW.user_id IS DISTINCT FROM OLD.user_id
   OR NEW.kind IS DISTINCT FROM OLD.kind) THEN RAISE EXCEPTION 'Job scope is immutable'; END IF;
 IF NEW.kind='mapping' THEN
   SELECT t.sha256,t.department_id INTO source_hash,scope_id FROM core_template t
     JOIN core_templateversion v ON v.template_id=t.id WHERE v.id=NEW.mapping_version_id;
   IF NEW.config->>'source_sha256' IS DISTINCT FROM source_hash
     OR NEW.config->>'department_id' IS DISTINCT FROM scope_id::text
     OR NEW.config->>'mapping_version_id' IS DISTINCT FROM NEW.mapping_version_id::text
   THEN RAISE EXCEPTION 'Mapping job source and tenant binding mismatch'; END IF;
 END IF;
 RETURN NEW;
END; $$;
CREATE TRIGGER mapping_job_scope BEFORE INSERT OR UPDATE ON core_job
 FOR EACH ROW EXECUTE FUNCTION quillmd_mapping_job_scope_guard();
CREATE FUNCTION quillmd_mapping_template_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF (NEW.department_id IS DISTINCT FROM OLD.department_id OR NEW.sha256 IS DISTINCT FROM OLD.sha256
     OR NEW.original_path IS DISTINCT FROM OLD.original_path OR NEW.format IS DISTINCT FROM OLD.format)
   AND EXISTS(SELECT 1 FROM core_job j JOIN core_templateversion v ON j.mapping_version_id=v.id WHERE v.template_id=OLD.id)
 THEN RAISE EXCEPTION 'Mapping job source and tenant are immutable'; END IF;
 RETURN NEW;
END; $$;
CREATE TRIGGER mapping_template_source BEFORE UPDATE ON core_template
 FOR EACH ROW EXECUTE FUNCTION quillmd_mapping_template_guard();
'''
REVERSE = '''
DO $$ BEGIN IF EXISTS(SELECT 1 FROM core_job WHERE kind='mapping') THEN
 RAISE EXCEPTION 'Mapping jobs exist; preserve operation and financial history with a forward migration'; END IF; END $$;
DROP TRIGGER mapping_template_source ON core_template;
DROP FUNCTION quillmd_mapping_template_guard();
DROP TRIGGER mapping_job_scope ON core_job;
DROP FUNCTION quillmd_mapping_job_scope_guard();
'''

class Migration(migrations.Migration):
    dependencies=[('core','0021_word_v3_mapping_review')]
    operations=[
        migrations.AddField(model_name='templateversion',name='assistance',field=models.JSONField(default=dict,blank=True)),
        migrations.AlterField(model_name='job',name='encounter',field=models.ForeignKey(null=True,on_delete=django.db.models.deletion.PROTECT,to='core.encounter')),
        migrations.AddField(model_name='job',name='mapping_version',field=models.ForeignKey(null=True,on_delete=django.db.models.deletion.PROTECT,related_name='mapping_jobs',to='core.templateversion')),
        migrations.AddConstraint(model_name='job',constraint=models.CheckConstraint(name='job_exactly_one_scope',condition=(
            models.Q(kind='mapping',encounter__isnull=True,mapping_version__isnull=False)
            | (~models.Q(kind='mapping') & models.Q(encounter__isnull=False,mapping_version__isnull=True))))),
        migrations.RunSQL(SCOPE,REVERSE),
    ]
