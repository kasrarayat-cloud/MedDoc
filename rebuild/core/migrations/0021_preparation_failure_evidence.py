"""Retain closed provider failures and the prospectively bounded follow-up.

Scope SHA3f1f99421f07c72370a030a57174d5f5c9194ac6b3b8b7292e42a7bb4b3a3895:
seven attempts over six blank originals / thirteen preparation sends including
the original unknown reservation. Dollar caps, one stream and zero retries stay.
Existing rows gain empty diagnostic fields; no failure or receipt is rewritten.
"""
from django.db import migrations,models

CAPS = """
CREATE OR REPLACE FUNCTION quillmd_preparation_pilot_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE original_sha text;
BEGIN
 PERFORM pg_advisory_xact_lock(717844900619);
 IF (SELECT count(*) FROM core_templatepreparation)>=7 THEN RAISE EXCEPTION 'The seven recorded preparation attempts are exhausted'; END IF;
 SELECT sha256 INTO original_sha FROM core_template WHERE id=NEW.template_id;
 IF NOT EXISTS(SELECT 1 FROM core_templatepreparation p JOIN core_template t ON p.template_id=t.id WHERE t.sha256=original_sha)
    AND (SELECT count(DISTINCT t.sha256) FROM core_templatepreparation p JOIN core_template t ON p.template_id=t.id)>=6
 THEN RAISE EXCEPTION 'The six unique blank original limit is exhausted'; END IF;
 RETURN NEW;
END; $$;
CREATE FUNCTION quillmd_preparation_send_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 PERFORM pg_advisory_xact_lock(717844900619);
 IF (SELECT count(*) FROM core_preparationreceipt)>=13 THEN RAISE EXCEPTION 'The thirteen recorded preparation sends are exhausted'; END IF;
 RETURN NEW;
END; $$;
CREATE TRIGGER preparation_send_guard BEFORE INSERT ON core_preparationreceipt
 FOR EACH ROW EXECUTE FUNCTION quillmd_preparation_send_guard();
"""

PREVIOUS = """
DROP TRIGGER preparation_send_guard ON core_preparationreceipt;
DROP FUNCTION quillmd_preparation_send_guard();
CREATE OR REPLACE FUNCTION quillmd_preparation_pilot_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 PERFORM pg_advisory_xact_lock(717844900619);
 IF (SELECT count(*) FROM core_templatepreparation)>=6 THEN RAISE EXCEPTION 'The six-run preparation pilot is exhausted'; END IF;
 RETURN NEW;
END; $$;
"""

class Migration(migrations.Migration):
    dependencies=[('core','0020_preparation_initial_state')]
    operations=[
        migrations.AddField(model_name='preparationreceipt',name='failure',field=models.JSONField(default=dict)),
        migrations.AddField(model_name='preparationreceipt',name='failure_path',field=models.CharField(blank=True,default='',max_length=100),preserve_default=False),
        migrations.AddField(model_name='preparationreceipt',name='failure_sha256',field=models.CharField(blank=True,default='',max_length=64),preserve_default=False),
        migrations.RunSQL(CAPS,PREVIOUS),
    ]
