"""One separately bounded WM follow-up; retain every earlier failure and row.

Prospective scope SHA812817c06f8b5d686e4aa93a1662409e7d48d56d08870659a3d0d9851b4b5add:
eight attempts over the same six originals, fourteen total sends, and $0.16
per exact WM role. The prior twelve sends include the retained max-token
failure. No old attempt, result, reservation, or source record is updated.
"""
from decimal import Decimal
from django.db import migrations,models

CAPS = """
CREATE OR REPLACE FUNCTION quillmd_preparation_pilot_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE original_sha text; attempts integer;
BEGIN
 PERFORM pg_advisory_xact_lock(717844900619);
 SELECT count(*) INTO attempts FROM core_templatepreparation;
 IF attempts>=8 THEN RAISE EXCEPTION 'The eight recorded preparation attempts are exhausted'; END IF;
 SELECT sha256 INTO original_sha FROM core_template WHERE id=NEW.template_id;
 IF attempts>=7 AND original_sha IS DISTINCT FROM 'c1852a492221cfa0d144c9c0a60b700a7363a2cca7630aa988ee8b6329e1868b'
 THEN RAISE EXCEPTION 'The eighth attempt is reserved for the exact WM blank original'; END IF;
 IF NOT EXISTS(SELECT 1 FROM core_templatepreparation p JOIN core_template t ON p.template_id=t.id WHERE t.sha256=original_sha)
    AND (SELECT count(DISTINCT t.sha256) FROM core_templatepreparation p JOIN core_template t ON p.template_id=t.id)>=6
 THEN RAISE EXCEPTION 'The six unique blank original limit is exhausted'; END IF;
 RETURN NEW;
END; $$;
CREATE OR REPLACE FUNCTION quillmd_preparation_send_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE original_sha text; inv jsonb; sends integer;
BEGIN
 PERFORM pg_advisory_xact_lock(717844900619);
 SELECT count(*) INTO sends FROM core_preparationreceipt;
 IF sends>=14 THEN RAISE EXCEPTION 'The fourteen recorded preparation sends are exhausted'; END IF;
 IF sends>=12 THEN
  SELECT t.sha256,p.inventory INTO original_sha,inv FROM core_templatepreparation p JOIN core_template t ON t.id=p.template_id WHERE p.id=NEW.preparation_id;
  IF original_sha IS DISTINCT FROM 'c1852a492221cfa0d144c9c0a60b700a7363a2cca7630aa988ee8b6329e1868b'
   OR inv->>'source_sha256' IS DISTINCT FROM original_sha
   OR jsonb_array_length(inv->'anchors') IS DISTINCT FROM 90 OR jsonb_array_length(inv->'fields') IS DISTINCT FROM 90
   OR jsonb_array_length(inv->'stories') IS DISTINCT FROM 16 OR inv->'document_backend'->>'backend' IS DISTINCT FROM 'wm-iov-foss-v2'
   OR inv->'document_backend'->>'source_sha256' IS DISTINCT FROM original_sha
   OR EXISTS(SELECT 1 FROM jsonb_array_elements(inv->'anchors') a WHERE a->>'kind' IS DISTINCT FROM 'existing')
   THEN RAISE EXCEPTION 'The final two sends are reserved for the exact qualified WM follow-up'; END IF;
 END IF;
 RETURN NEW;
END; $$;
CREATE OR REPLACE FUNCTION quillmd_preparation_wm_cap_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE original_sha text; inv jsonb;
BEGIN
 IF NEW.quote_maximum>0.10 THEN
  SELECT t.sha256,p.inventory INTO original_sha,inv FROM core_templatepreparation p JOIN core_template t ON t.id=p.template_id WHERE p.id=NEW.preparation_id;
  IF original_sha IS DISTINCT FROM 'c1852a492221cfa0d144c9c0a60b700a7363a2cca7630aa988ee8b6329e1868b'
   OR inv->>'source_sha256' IS DISTINCT FROM original_sha
   OR jsonb_array_length(inv->'anchors') IS DISTINCT FROM 90 OR jsonb_array_length(inv->'fields') IS DISTINCT FROM 90
   OR jsonb_array_length(inv->'stories') IS DISTINCT FROM 16 OR inv->'document_backend'->>'backend' IS DISTINCT FROM 'wm-iov-foss-v2'
   OR inv->'document_backend'->>'source_sha256' IS DISTINCT FROM original_sha
   OR EXISTS(SELECT 1 FROM jsonb_array_elements(inv->'anchors') a WHERE a->>'kind' IS DISTINCT FROM 'existing')
   THEN RAISE EXCEPTION 'Only the exact WM90 purpose has the extended per-role cap'; END IF;
 END IF;
 RETURN NEW;
END; $$;
"""

PREVIOUS = """
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
CREATE OR REPLACE FUNCTION quillmd_preparation_send_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 PERFORM pg_advisory_xact_lock(717844900619);
 IF (SELECT count(*) FROM core_preparationreceipt)>=13 THEN RAISE EXCEPTION 'The thirteen recorded preparation sends are exhausted'; END IF;
 RETURN NEW;
END; $$;
CREATE OR REPLACE FUNCTION quillmd_preparation_wm_cap_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE original_sha text; inv jsonb;
BEGIN
 IF NEW.quote_maximum>0.10 THEN
  SELECT t.sha256,p.inventory INTO original_sha,inv FROM core_templatepreparation p JOIN core_template t ON t.id=p.template_id WHERE p.id=NEW.preparation_id;
  IF original_sha IS DISTINCT FROM 'c1852a492221cfa0d144c9c0a60b700a7363a2cca7630aa988ee8b6329e1868b'
   OR jsonb_array_length(inv->'anchors') IS DISTINCT FROM 90 OR jsonb_array_length(inv->'fields') IS DISTINCT FROM 90
   OR jsonb_array_length(inv->'stories') IS DISTINCT FROM 16 OR inv->'document_backend'->>'backend' IS DISTINCT FROM 'wm-iov-foss-v2'
   THEN RAISE EXCEPTION 'Only the exact WM90 purpose has the extended per-role cap'; END IF;
 END IF;
 RETURN NEW;
END; $$;
"""

class Migration(migrations.Migration):
    dependencies=[('core','0021_preparation_failure_evidence')]
    operations=[
        migrations.RemoveConstraint(model_name='preparationreceipt',name='preparation_receipt_role_cap'),
        migrations.AddConstraint(model_name='preparationreceipt',constraint=models.CheckConstraint(
            condition=models.Q(role__in=['proposer','checker'],quote_maximum__gte=0,quote_maximum__lte=Decimal('0.16')),
            name='preparation_receipt_role_cap')),
        migrations.RunSQL(CAPS,PREVIOUS),
    ]
