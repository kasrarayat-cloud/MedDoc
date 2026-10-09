"""Prospective standing authority, preserving every finite approval and record.

There is no funding balance or ceiling. New immutable request discriminators
select owner-sponsored accounting; legacy database guards retain their bounds.
"""
import importlib
import re
import uuid

import django.db.models.deletion
from django.db import migrations, models

AUTHORITY_ID = 'quillmd-standing-testing-20261009-v1'
AUTHORITY_SHA256 = 'eb04bade3d212ebdc06dfc44095f0ba56fecfacd0d3d1dbcec97279865d0a7a5'

SQL = r"""
CREATE FUNCTION quillmd_standing_config(config jsonb) RETURNS boolean LANGUAGE plpgsql AS $$
BEGIN
 IF jsonb_typeof(config) IS DISTINCT FROM 'object' THEN RAISE EXCEPTION 'Provider configuration must be a recorded object'; END IF;
 IF NOT (config ?| ARRAY['testing_authority_mode','testing_authority_id','testing_authority_sha256','testing_purpose']) THEN RETURN false; END IF;
 IF NOT(config ?& ARRAY['testing_authority_mode','testing_authority_id','testing_authority_sha256','testing_purpose'])
  OR config ?| ARRAY['campaign','campaign_scope_sha256','campaign_actor_scope_sha256','campaign_quote_usd']
  OR config->>'testing_authority_mode' IS DISTINCT FROM 'standing_authority'
  OR config->>'testing_authority_id' IS DISTINCT FROM '@ID@'
  OR config->>'testing_authority_sha256' IS DISTINCT FROM '@SHA@'
  OR jsonb_typeof(config->'testing_purpose') IS DISTINCT FROM 'string'
  OR config->>'testing_purpose' NOT IN ('word-template-preparation','typed-or-reviewed-voice-generation','reviewed-synthetic-voice-transcription')
  OR config->>'mode' IS NULL OR config->>'mode' NOT IN ('live','fixture')
  OR config->>'provider' IS NULL OR config->>'provider' NOT IN ('anthropic','openai')
  OR jsonb_typeof(config->'model') IS DISTINCT FROM 'string'
  OR length(config->>'model') NOT BETWEEN 1 AND 100
 THEN RAISE EXCEPTION 'Testing configuration differs from recorded standing authority'; END IF;
 RETURN true;
END; $$;

CREATE FUNCTION quillmd_standing_job_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE department uuid; purpose text;
BEGIN
 IF NOT quillmd_standing_config(NEW.config) THEN RETURN NEW; END IF;
 IF TG_OP='UPDATE' THEN
  IF OLD.state<>'queued' AND NEW.state='queued'
  THEN RAISE EXCEPTION 'A standing testing attempt cannot be replayed'; END IF;
  IF NEW.encounter_id IS DISTINCT FROM OLD.encounter_id OR NEW.user_id IS DISTINCT FROM OLD.user_id
    OR NEW.kind IS DISTINCT FROM OLD.kind OR NEW.revision IS DISTINCT FROM OLD.revision
    OR NEW.input_path IS DISTINCT FROM OLD.input_path OR NEW.id IS DISTINCT FROM OLD.id
    OR NEW.created_at IS DISTINCT FROM OLD.created_at
  THEN RAISE EXCEPTION 'Standing testing request identity and source are immutable'; END IF;
  RETURN NEW;
 END IF;
 SELECT department_id INTO department FROM core_encounter WHERE id=NEW.encounter_id;
 PERFORM quillmd_delivery_actor(NEW.user_id,department);
 purpose=CASE NEW.kind WHEN 'generation' THEN 'typed-or-reviewed-voice-generation'
   WHEN 'transcription' THEN 'reviewed-synthetic-voice-transcription' ELSE '' END;
 IF purpose='' OR NEW.config->>'testing_purpose' IS DISTINCT FROM purpose
   OR jsonb_typeof(NEW.config->'testing_quote_usd') IS DISTINCT FROM 'string'
   OR NEW.config->>'testing_quote_usd' !~ '^[0-9]+([.][0-9]{1,12})?$'
   OR length(split_part(NEW.config->>'testing_quote_usd','.',1))>12
   OR (NEW.config->>'mode'='fixture' AND (NEW.config->>'testing_quote_usd')::numeric<>0)
 THEN RAISE EXCEPTION 'Standing testing job requires its exact purpose and finite provider estimate'; END IF;
 RETURN NEW;
END; $$;
CREATE TRIGGER standing_job_guard BEFORE INSERT OR UPDATE ON core_job FOR EACH ROW EXECUTE FUNCTION quillmd_standing_job_guard();

CREATE FUNCTION quillmd_testing_reservation_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE configuration jsonb; actor uuid; department uuid;
BEGIN
 IF TG_OP='DELETE' THEN RAISE EXCEPTION 'Testing reservations are retained'; END IF;
 IF TG_OP='UPDATE' THEN
  IF NEW.job_id IS DISTINCT FROM OLD.job_id OR NEW.authority_id IS DISTINCT FROM OLD.authority_id
    OR NEW.quoted_provider_cost IS DISTINCT FROM OLD.quoted_provider_cost
    OR NEW.id IS DISTINCT FROM OLD.id OR NEW.created_at IS DISTINCT FROM OLD.created_at
    OR OLD.state<>'held' OR NEW.state NOT IN ('settled','released')
  THEN RAISE EXCEPTION 'Testing reservation identity, estimate and completed state are immutable'; END IF;
  RETURN NEW;
 END IF;
 SELECT j.config,j.user_id,e.department_id INTO configuration,actor,department
   FROM core_job j JOIN core_encounter e ON e.id=j.encounter_id WHERE j.id=NEW.job_id;
 IF configuration IS NULL OR NOT quillmd_standing_config(configuration)
   OR NEW.authority_id IS DISTINCT FROM '@ID@' OR NEW.state<>'held'
   OR NEW.quoted_provider_cost IS DISTINCT FROM (configuration->>'testing_quote_usd')::numeric
   OR EXISTS(SELECT 1 FROM core_reservation WHERE job_id=NEW.job_id)
 THEN RAISE EXCEPTION 'Testing reservation must match its immutable authorized request'; END IF;
 PERFORM quillmd_delivery_actor(actor,department);
 RETURN NEW;
END; $$;
CREATE TRIGGER testing_reservation_guard BEFORE INSERT OR UPDATE OR DELETE ON core_testingreservation
 FOR EACH ROW EXECUTE FUNCTION quillmd_testing_reservation_guard();

CREATE FUNCTION quillmd_standing_usage_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE configuration jsonb; payer text; actor uuid; department uuid; organization uuid;
BEGIN
 SELECT j.config,j.payer,j.user_id,e.department_id,d.organization_id INTO configuration,payer,actor,department,organization
  FROM core_job j JOIN core_encounter e ON e.id=j.encounter_id JOIN core_department d ON d.id=e.department_id WHERE j.id=NEW.job_id;
 IF NOT quillmd_standing_config(configuration) THEN
  IF NEW.payer LIKE 'standing:%' THEN RAISE EXCEPTION 'A standing payer requires its immutable authority'; END IF;
  RETURN NEW;
 END IF;
 IF payer IS DISTINCT FROM 'standing:@ID@' OR NEW.payer IS DISTINCT FROM payer
  OR NEW.user_id IS DISTINCT FROM actor OR NEW.department_id IS DISTINCT FROM department
  OR NEW.organization_id IS DISTINCT FROM organization OR NEW.charged_cost IS DISTINCT FROM 0::numeric
  OR NOT EXISTS(SELECT 1 FROM core_testingreservation WHERE job_id=NEW.job_id AND state='held' AND authority_id='@ID@')
  OR EXISTS(SELECT 1 FROM core_reservation WHERE job_id=NEW.job_id)
  OR EXISTS(SELECT 1 FROM core_ledgerentry WHERE job_id=NEW.job_id)
 THEN RAISE EXCEPTION 'Standing testing usage must preserve sponsor accounting without wallet movements'; END IF;
 RETURN NEW;
END; $$;
CREATE TRIGGER standing_usage_guard BEFORE INSERT ON core_usage FOR EACH ROW EXECUTE FUNCTION quillmd_standing_usage_guard();

CREATE FUNCTION quillmd_standing_wallet_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE configuration jsonb;
BEGIN
 SELECT config INTO configuration FROM core_job WHERE id=NEW.job_id;
 IF quillmd_standing_config(configuration) THEN RAISE EXCEPTION 'Owner-sponsored testing cannot reserve or debit user wallet funds'; END IF;
 RETURN NEW;
END; $$;
CREATE TRIGGER standing_wallet_reservation_guard BEFORE INSERT ON core_reservation FOR EACH ROW EXECUTE FUNCTION quillmd_standing_wallet_guard();
CREATE TRIGGER standing_wallet_ledger_guard BEFORE INSERT ON core_ledgerentry FOR EACH ROW WHEN (NEW.job_id IS NOT NULL)
 EXECUTE FUNCTION quillmd_standing_wallet_guard();
"""
SQL = SQL.replace('@ID@', AUTHORITY_ID).replace('@SHA@', AUTHORITY_SHA256)

# Append a strictly validated prospective branch to the retained definitions.
# Historical finite branches/caps remain verbatim except excluding NEW standing
# discriminators from their historical counters. No historical row is changed.
_previous = importlib.import_module('core.migrations.0023_delivery_campaign')
_pre_wm = importlib.import_module('core.migrations.0022_wm_output_followup')
FUNCTION_PATTERN = r'CREATE OR REPLACE FUNCTION {}\(\) RETURNS trigger LANGUAGE plpgsql AS \$\$.*?END; \$\$;'
ORIGINALS = {}
for name, source in [('quillmd_preparation_pilot_guard', _previous.SQL),
                     ('quillmd_preparation_send_guard', _previous.SQL),
                     ('quillmd_preparation_wm_cap_guard', _pre_wm.CAPS)]:
    ORIGINALS[name] = re.search(FUNCTION_PATTERN.format(name), source, re.S).group(0)

branches = {
 'quillmd_preparation_pilot_guard': r"""
 IF quillmd_standing_config(NEW.config) THEN
  PERFORM quillmd_delivery_actor(NEW.requested_by_id,department);
  IF NEW.config->>'testing_purpose' IS DISTINCT FROM 'word-template-preparation'
    OR NOT EXISTS(SELECT 1 FROM core_template WHERE id=NEW.template_id AND format='docx')
  THEN RAISE EXCEPTION 'Standing preparation requires its exact blank Word purpose'; END IF;
  RETURN NEW;
 END IF;
""",
 'quillmd_preparation_send_guard': r"""
 IF quillmd_standing_config(configuration) THEN
  PERFORM quillmd_delivery_actor(actor,department);
  IF configuration->>'testing_purpose' IS DISTINCT FROM 'word-template-preparation'
    OR NEW.role NOT IN ('proposer','checker') OR NEW.provider IS DISTINCT FROM configuration->>'provider'
    OR NEW.requested_model IS DISTINCT FROM configuration->>'model'
    OR (configuration->>'mode'='fixture' AND NEW.quote_maximum IS DISTINCT FROM 0::numeric)
    OR (NEW.role='checker' AND NOT EXISTS(SELECT 1 FROM core_preparationreceipt
        WHERE preparation_id=NEW.preparation_id AND role='proposer' AND state='succeeded'))
  THEN RAISE EXCEPTION 'Standing preparation role requires its original provider, purpose and successful proposal'; END IF;
  RETURN NEW;
 END IF;
""",
 'quillmd_preparation_wm_cap_guard': r"""
 SELECT config INTO configuration FROM core_templatepreparation WHERE id=NEW.preparation_id;
 IF quillmd_standing_config(configuration) THEN RETURN NEW; END IF;
 IF NEW.quote_maximum>0.16 THEN RAISE EXCEPTION 'Historical preparation quote exceeds its retained cap'; END IF;
""",
}
for name, original in ORIGINALS.items():
    revised = original
    if name == 'quillmd_preparation_pilot_guard':
        revised = revised.replace(' IF quillmd_delivery_config(NEW.config) THEN', branches[name] + '\n IF quillmd_delivery_config(NEW.config) THEN', 1)
    elif name == 'quillmd_preparation_send_guard':
        revised = revised.replace(' IF quillmd_delivery_config(configuration) THEN', branches[name] + '\n IF quillmd_delivery_config(configuration) THEN', 1)
    else:
        revised = revised.replace('DECLARE original_sha text; inv jsonb;', 'DECLARE original_sha text; inv jsonb; configuration jsonb;', 1)
        revised = revised.replace('BEGIN\n', 'BEGIN\n' + branches[name], 1)
    revised = revised.replace("WHERE NOT(config ? 'campaign')", "WHERE NOT(config ?| ARRAY['testing_authority_mode','testing_authority_id','testing_authority_sha256','testing_purpose']) AND NOT(config ? 'campaign')")
    revised = revised.replace("WHERE NOT(p.config ? 'campaign')", "WHERE NOT(p.config ?| ARRAY['testing_authority_mode','testing_authority_id','testing_authority_sha256','testing_purpose']) AND NOT(p.config ? 'campaign')")
    SQL += '\n' + revised

REVERSE = r"""
DO $$ BEGIN
 IF EXISTS(SELECT 1 FROM core_templatepreparation WHERE config ?| ARRAY['testing_authority_mode','testing_authority_id','testing_authority_sha256','testing_purpose'])
 OR EXISTS(SELECT 1 FROM core_job WHERE config ?| ARRAY['testing_authority_mode','testing_authority_id','testing_authority_sha256','testing_purpose'])
 OR EXISTS(SELECT 1 FROM core_testingreservation)
 THEN RAISE EXCEPTION 'Retained standing testing records forbid reversing authority controls'; END IF;
END; $$;
DROP TRIGGER standing_wallet_ledger_guard ON core_ledgerentry;
DROP TRIGGER standing_wallet_reservation_guard ON core_reservation;
DROP TRIGGER standing_usage_guard ON core_usage;
DROP TRIGGER testing_reservation_guard ON core_testingreservation;
DROP TRIGGER standing_job_guard ON core_job;
DROP FUNCTION quillmd_standing_wallet_guard();
DROP FUNCTION quillmd_standing_usage_guard();
DROP FUNCTION quillmd_testing_reservation_guard();
DROP FUNCTION quillmd_standing_job_guard();
""" + '\n'.join(ORIGINALS.values()) + '\nDROP FUNCTION quillmd_standing_config(jsonb);'


class Migration(migrations.Migration):
    dependencies = [('core', '0023_delivery_campaign')]
    operations = [
        migrations.CreateModel(name='TestingReservation', fields=[
            ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
            ('created_at', models.DateTimeField(auto_now_add=True)),
            ('authority_id', models.CharField(max_length=100)),
            ('quoted_provider_cost', models.DecimalField(decimal_places=12, max_digits=24)),
            ('state', models.CharField(default='held', max_length=12)),
            ('job', models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name='testing_reservation', to='core.job')),
        ], options={'constraints': [
            models.CheckConstraint(condition=models.Q(quoted_provider_cost__gte=0), name='testing_quote_nonnegative'),
            models.CheckConstraint(condition=models.Q(state__in=['held','settled','released']), name='testing_reservation_state_known'),
        ]}),
        migrations.RemoveConstraint(model_name='preparationreceipt', name='preparation_receipt_role_cap'),
        migrations.AddConstraint(model_name='preparationreceipt', constraint=models.CheckConstraint(
            condition=models.Q(role__in=['proposer','checker'], quote_maximum__gte=0), name='preparation_receipt_role_cap')),
        migrations.RunSQL(SQL, REVERSE),
    ]
