"""Separate delivery counters without resetting the closed pilot or old records.

Discriminators are appended only to NEW configuration snapshots. Old rows,
approval seals, failure evidence and the unknown $0.10 reservation are untouched.
Scope fe387adcfb7f9397a7c54c342270063f9fc7f6cdd45b357e6ab16e47d16670c8.
"""
from django.db import migrations

CAMPAIGN = 'word-milestone-delivery-20261008-v1'
SCOPE = 'fe387adcfb7f9397a7c54c342270063f9fc7f6cdd45b357e6ab16e47d16670c8'
ACTOR_SCOPE = 'd37378667422a1d36c5559dec32475af8435f822bfbb2c01eba4e6ac420fd77b'
WM = 'c1852a492221cfa0d144c9c0a60b700a7363a2cca7630aa988ee8b6329e1868b'
SHORT = 'b2b78348f8735bddb75433d7b0cd720d1a0f416c1fbae7ac51b896fbf0fa5193'
UNDERSCORE = 'a2a70a3b087077e55401030fd9a592958d0064402a3b12d107b132f563111102'

SQL = r"""
CREATE FUNCTION quillmd_delivery_config(config jsonb) RETURNS boolean LANGUAGE plpgsql AS $$
BEGIN
 IF jsonb_typeof(config) IS DISTINCT FROM 'object'
 THEN RAISE EXCEPTION 'Provider configuration must be a recorded object'; END IF;
 IF NOT (config ? 'campaign') AND NOT (config ? 'campaign_scope_sha256')
    AND NOT(config ? 'campaign_actor_scope_sha256') THEN RETURN false; END IF;
 IF jsonb_typeof(config->'campaign') IS DISTINCT FROM 'string'
    OR jsonb_typeof(config->'campaign_scope_sha256') IS DISTINCT FROM 'string'
    OR config->>'campaign' IS DISTINCT FROM '@CAMPAIGN@'
    OR config->>'campaign_scope_sha256' IS DISTINCT FROM '@SCOPE@'
    OR jsonb_typeof(config->'campaign_actor_scope_sha256') IS DISTINCT FROM 'string'
    OR config->>'campaign_actor_scope_sha256' IS DISTINCT FROM '@ACTOR_SCOPE@'
 THEN RAISE EXCEPTION 'Delivery campaign does not match the recorded authority'; END IF;
 RETURN true;
END; $$;

CREATE FUNCTION quillmd_delivery_actor(actor uuid, department uuid) RETURNS void LANGUAGE plpgsql AS $$
BEGIN
 IF NOT ((actor='71dc60e3-ca1e-40c7-ad49-4a2612ed8d1a' AND department='d41ad441-987c-4e68-bb0e-b885ec4b642a')
       OR (actor='2247e403-a830-4807-9a34-6903b95a0f50' AND department='46a5abdd-36f1-41f0-968f-8c09c39d9daa'))
    OR actor IS NULL OR department IS NULL
    OR NOT EXISTS(SELECT 1 FROM core_membership m JOIN core_user u ON u.id=m.user_id
      WHERE m.user_id=actor AND m.department_id=department AND m.active AND u.is_active
        AND u.verified_at IS NOT NULL AND m.role IN ('owner','clinician','manager'))
 THEN RAISE EXCEPTION 'Delivery requires the exact active synthetic doctor and department'; END IF;
END; $$;

CREATE FUNCTION quillmd_delivery_exposure() RETURNS numeric LANGUAGE sql AS $$
 SELECT COALESCE((SELECT sum(GREATEST(r.quote_maximum,COALESCE(r.computed_cost,r.quote_maximum)))
   FROM core_preparationreceipt r JOIN core_templatepreparation p ON p.id=r.preparation_id
   WHERE p.config->>'campaign'='@CAMPAIGN@'),0)
   + COALESCE((SELECT sum(GREATEST((j.config->>'campaign_quote_usd')::numeric,
       COALESCE(r.actual_cost,(j.config->>'campaign_quote_usd')::numeric)))
     FROM core_job j LEFT JOIN core_providerreceipt r ON r.job_id=j.id
     WHERE j.config->>'campaign'='@CAMPAIGN@'),0);
$$;

CREATE OR REPLACE FUNCTION quillmd_preparation_pilot_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE original_sha text; attempts integer; department uuid;
BEGIN
 PERFORM pg_advisory_xact_lock(717844900619);
 SELECT sha256,department_id INTO original_sha,department FROM core_template WHERE id=NEW.template_id;
 IF quillmd_delivery_config(NEW.config) THEN
  PERFORM quillmd_delivery_actor(NEW.requested_by_id,department);
  IF original_sha NOT IN ('@SHORT@','@UNDERSCORE@','@WM@') OR original_sha IS NULL
  THEN RAISE EXCEPTION 'Original is outside the exact three delivery forms'; END IF;
  IF (SELECT count(*) FROM core_templatepreparation WHERE config->>'campaign'='@CAMPAIGN@')>=3
     OR EXISTS(SELECT 1 FROM core_templatepreparation p JOIN core_template t ON t.id=p.template_id
       WHERE p.config->>'campaign'='@CAMPAIGN@' AND t.sha256=original_sha)
  THEN RAISE EXCEPTION 'Delivery permits one attempt per original and three total'; END IF;
 ELSE
  SELECT count(*) INTO attempts FROM core_templatepreparation
   WHERE NOT(config ? 'campaign') AND NOT(config ? 'campaign_scope_sha256') AND NOT(config ? 'campaign_actor_scope_sha256');
  IF attempts>=8 THEN RAISE EXCEPTION 'The eight recorded preparation attempts are exhausted'; END IF;
  IF attempts>=7 AND original_sha IS DISTINCT FROM '@WM@'
  THEN RAISE EXCEPTION 'The eighth legacy attempt is reserved for the exact WM original'; END IF;
  IF NOT EXISTS(SELECT 1 FROM core_templatepreparation p JOIN core_template t ON p.template_id=t.id
       WHERE NOT(p.config ? 'campaign') AND NOT(p.config ? 'campaign_scope_sha256')
         AND NOT(p.config ? 'campaign_actor_scope_sha256') AND t.sha256=original_sha)
     AND (SELECT count(DISTINCT t.sha256) FROM core_templatepreparation p JOIN core_template t ON p.template_id=t.id
       WHERE NOT(p.config ? 'campaign') AND NOT(p.config ? 'campaign_scope_sha256')
         AND NOT(p.config ? 'campaign_actor_scope_sha256'))>=6
  THEN RAISE EXCEPTION 'The six legacy blank original limit is exhausted'; END IF;
 END IF;
 RETURN NEW;
END; $$;

CREATE OR REPLACE FUNCTION quillmd_preparation_send_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE original_sha text; inv jsonb; configuration jsonb; sends integer; cap numeric; actor uuid; department uuid;
BEGIN
 PERFORM pg_advisory_xact_lock(717844900619);
 SELECT t.sha256,p.inventory,p.config,p.requested_by_id,t.department_id INTO original_sha,inv,configuration,actor,department
   FROM core_templatepreparation p JOIN core_template t ON t.id=p.template_id WHERE p.id=NEW.preparation_id;
 IF configuration IS NULL THEN RAISE EXCEPTION 'Preparation reservation requires its immutable source'; END IF;
 IF quillmd_delivery_config(configuration) THEN
  PERFORM quillmd_delivery_actor(actor,department);
  IF original_sha NOT IN ('@SHORT@','@UNDERSCORE@','@WM@') OR original_sha IS NULL
  THEN RAISE EXCEPTION 'Delivery receipt source is outside its recorded forms'; END IF;
  cap=CASE WHEN original_sha='@WM@' THEN 0.16 ELSE 0.10 END;
  IF NEW.role NOT IN ('proposer','checker') OR NEW.quote_maximum<0 OR NEW.quote_maximum>cap
     OR (configuration->>'mode'='live' AND NEW.quote_maximum IS DISTINCT FROM cap)
     OR (configuration->>'mode'='fixture' AND NEW.quote_maximum IS DISTINCT FROM 0::numeric)
     OR configuration->>'mode' NOT IN ('live','fixture') OR configuration->>'mode' IS NULL
  THEN RAISE EXCEPTION 'Delivery receipt role or quote differs from its exact cap'; END IF;
  IF NEW.role='checker' AND NOT EXISTS(SELECT 1 FROM core_preparationreceipt
    WHERE preparation_id=NEW.preparation_id AND role='proposer' AND state='succeeded')
  THEN RAISE EXCEPTION 'Delivery checker requires the retained successful proposal'; END IF;
  IF (SELECT count(*) FROM core_preparationreceipt r JOIN core_templatepreparation p ON p.id=r.preparation_id
    WHERE p.config->>'campaign'='@CAMPAIGN@')>=6
  THEN RAISE EXCEPTION 'The six delivery preparation sends are exhausted'; END IF;
  IF quillmd_delivery_exposure()+GREATEST(NEW.quote_maximum,COALESCE(NEW.computed_cost,NEW.quote_maximum))>1.75
  THEN RAISE EXCEPTION 'Delivery computed or reserved exposure exceeds its cap'; END IF;
 ELSE
  SELECT count(*) INTO sends FROM core_preparationreceipt r JOIN core_templatepreparation p ON p.id=r.preparation_id
    WHERE NOT(p.config ? 'campaign') AND NOT(p.config ? 'campaign_scope_sha256')
      AND NOT(p.config ? 'campaign_actor_scope_sha256');
  IF sends>=14 THEN RAISE EXCEPTION 'The fourteen recorded preparation sends are exhausted'; END IF;
  IF sends>=12 AND (original_sha IS DISTINCT FROM '@WM@'
     OR inv->>'source_sha256' IS DISTINCT FROM original_sha
     OR jsonb_array_length(inv->'anchors') IS DISTINCT FROM 90
     OR jsonb_array_length(inv->'fields') IS DISTINCT FROM 90
     OR jsonb_array_length(inv->'stories') IS DISTINCT FROM 16
     OR inv->'document_backend'->>'backend' IS DISTINCT FROM 'wm-iov-foss-v2'
     OR inv->'document_backend'->>'source_sha256' IS DISTINCT FROM original_sha
     OR EXISTS(SELECT 1 FROM jsonb_array_elements(inv->'anchors') a WHERE a->>'kind' IS DISTINCT FROM 'existing'))
  THEN RAISE EXCEPTION 'The final legacy sends belong to the exact qualified WM follow-up'; END IF;
 END IF;
 RETURN NEW;
END; $$;

CREATE FUNCTION quillmd_delivery_job_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE count_limit integer; quote numeric; department uuid;
BEGIN
 IF NOT quillmd_delivery_config(NEW.config) THEN RETURN NEW; END IF;
 PERFORM pg_advisory_xact_lock(717844900619);
 SELECT department_id INTO department FROM core_encounter WHERE id=NEW.encounter_id;
 PERFORM quillmd_delivery_actor(NEW.user_id,department);
 IF jsonb_typeof(NEW.config->'campaign_quote_usd') IS DISTINCT FROM 'string'
    OR NEW.config->>'campaign_quote_usd' !~ '^0[.]20$'
 THEN RAISE EXCEPTION 'Delivery clinical job requires its exact recorded exposure quote'; END IF;
 quote=(NEW.config->>'campaign_quote_usd')::numeric;
 count_limit=CASE WHEN NEW.kind='generation' THEN 3 WHEN NEW.kind='transcription' THEN 1 ELSE 0 END;
 IF count_limit=0 OR (SELECT count(*) FROM core_job WHERE config->>'campaign'='@CAMPAIGN@' AND kind=NEW.kind)>=count_limit
 THEN RAISE EXCEPTION 'Delivery clinical request count is exhausted or kind is not authorized'; END IF;
 IF quillmd_delivery_exposure()+quote>1.75
 THEN RAISE EXCEPTION 'Delivery computed or reserved exposure exceeds its cap'; END IF;
 RETURN NEW;
END; $$;
CREATE TRIGGER delivery_job_guard BEFORE INSERT ON core_job FOR EACH ROW EXECUTE FUNCTION quillmd_delivery_job_guard();

CREATE FUNCTION quillmd_delivery_settlement_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE configuration jsonb;
BEGIN
 PERFORM pg_advisory_xact_lock(717844900619);
 IF TG_TABLE_NAME='core_preparationreceipt' THEN
  SELECT config INTO configuration FROM core_templatepreparation WHERE id=NEW.preparation_id;
  IF NOT quillmd_delivery_config(configuration) THEN RETURN NEW; END IF;
 ELSE
  SELECT config INTO configuration FROM core_job WHERE id=NEW.job_id;
  IF NOT quillmd_delivery_config(configuration) THEN RETURN NEW; END IF;
 END IF;
 -- A returned cost is evidence, even if it exceeds the reservation. Serialize
 -- its retention; admission uses max(quote,actual) and refuses subsequent sends.
 -- The application records the over-cap failure rather than hiding the usage.
 RETURN NEW;
END; $$;
CREATE TRIGGER delivery_preparation_settlement_guard BEFORE UPDATE ON core_preparationreceipt
 FOR EACH ROW EXECUTE FUNCTION quillmd_delivery_settlement_guard();
CREATE TRIGGER delivery_clinical_settlement_guard BEFORE INSERT OR UPDATE ON core_providerreceipt
 FOR EACH ROW EXECUTE FUNCTION quillmd_delivery_settlement_guard();
"""
for key, value in {'CAMPAIGN': CAMPAIGN, 'SCOPE': SCOPE, 'ACTOR_SCOPE': ACTOR_SCOPE, 'SHORT': SHORT, 'UNDERSCORE': UNDERSCORE, 'WM': WM}.items():
    SQL = SQL.replace('@' + key + '@', value)

# Never reverse away a live paid cohort's audit/caps. An empty isolated schema
# can still be returned exactly to the original 0022 guard definitions.
REVERSE = r"""
DO $$ BEGIN
 IF EXISTS(SELECT 1 FROM core_templatepreparation WHERE config ? 'campaign' OR config ? 'campaign_scope_sha256' OR config ? 'campaign_actor_scope_sha256')
    OR EXISTS(SELECT 1 FROM core_job WHERE config ? 'campaign' OR config ? 'campaign_scope_sha256' OR config ? 'campaign_actor_scope_sha256')
 THEN RAISE EXCEPTION 'Retained campaign records forbid reversing the delivery guards'; END IF;
END; $$;
DROP TRIGGER delivery_clinical_settlement_guard ON core_providerreceipt;
DROP TRIGGER delivery_preparation_settlement_guard ON core_preparationreceipt;
DROP TRIGGER delivery_job_guard ON core_job;
DROP FUNCTION quillmd_delivery_settlement_guard();
DROP FUNCTION quillmd_delivery_job_guard();
DROP FUNCTION quillmd_delivery_exposure();
DROP FUNCTION quillmd_delivery_actor(uuid,uuid);
"""


class Migration(migrations.Migration):
    dependencies = [('core', '0022_wm_output_followup')]
    # Use precisely the retained 0022 functions, not a copied approximation.
    _previous = __import__('importlib').import_module('core.migrations.0022_wm_output_followup').CAPS
    operations = [migrations.RunSQL(SQL, REVERSE + _previous + '\nDROP FUNCTION quillmd_delivery_config(jsonb);')]
