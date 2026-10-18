"""One explicitly admitted v20 source recheck; historical v1/v2 guards remain exact."""
from django.db import migrations

REVALIDATION_SQL = r'''
CREATE OR REPLACE FUNCTION quillmd_ai_stage_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE configuration jsonb; actor uuid; department uuid; preceding text; prior_count integer; list_cost numeric; discounted numeric; integral numeric; fraction numeric;
BEGIN
 IF TG_OP='DELETE' THEN RAISE EXCEPTION 'AI stage history is retained'; END IF;
 IF TG_OP='UPDATE' THEN
  IF OLD.finished_at IS NOT NULL OR NEW.id<>OLD.id OR NEW.created_at<>OLD.created_at
   OR NEW.job_id IS DISTINCT FROM OLD.job_id OR NEW.definition_preparation_id IS DISTINCT FROM OLD.definition_preparation_id
   OR NEW.stage<>OLD.stage OR NEW.attempt<>OLD.attempt OR NEW.config IS DISTINCT FROM OLD.config
   OR NEW.request_path<>OLD.request_path OR NEW.request_sha256<>OLD.request_sha256
   OR NEW.provider<>OLD.provider OR NEW.requested_model<>OLD.requested_model OR NEW.quote_maximum<>OLD.quote_maximum
   OR NEW.simulated<>OLD.simulated
  THEN RAISE EXCEPTION 'AI stage request and completed evidence are immutable'; END IF;
  IF NOT ((OLD.state='reserved' AND NEW.state IN ('sending','failed')) OR (OLD.state='sending' AND (NEW.state IN ('received','unknown') OR (NEW.state='sending' AND OLD.result_path='' AND NEW.result_path<>'' AND NEW.actual_cost IS NULL))) OR (OLD.state='received' AND NEW.state IN ('succeeded','failed')))
  THEN RAISE EXCEPTION 'AI stage cannot replay or skip its send boundary'; END IF;
  IF NEW.state IN ('succeeded','failed','unknown') AND NEW.finished_at IS NULL THEN RAISE EXCEPTION 'Terminal AI stage requires its completion time'; END IF;
  IF NEW.state IN ('received','succeeded','failed') AND NEW.actual_cost IS NULL THEN RAISE EXCEPTION 'Known AI stage requires recorded provider cost'; END IF;
  IF NEW.state IN ('received','succeeded') AND (NEW.result_path='' OR NEW.result_sha256 !~ '^[a-f0-9]{64}$') THEN RAISE EXCEPTION 'Successful AI stage requires retained response'; END IF;
  IF OLD.result_path<>'' AND (NEW.result_path<>OLD.result_path OR NEW.result_sha256<>OLD.result_sha256 OR (OLD.provider_request_id<>'' AND NEW.provider_request_id<>OLD.provider_request_id) OR (OLD.provider_resource_id<>'' AND NEW.provider_resource_id<>OLD.provider_resource_id) OR NEW.returned_model<>OLD.returned_model) THEN RAISE EXCEPTION 'Retained raw provider response is immutable'; END IF;
  IF OLD.actual_cost IS NOT NULL AND (NEW.actual_cost IS DISTINCT FROM OLD.actual_cost OR NEW.usage IS DISTINCT FROM OLD.usage OR NEW.rates IS DISTINCT FROM OLD.rates OR NEW.result_path<>OLD.result_path OR NEW.result_sha256<>OLD.result_sha256 OR NEW.provider_request_id<>OLD.provider_request_id OR NEW.provider_resource_id<>OLD.provider_resource_id OR NEW.returned_model<>OLD.returned_model)
  THEN RAISE EXCEPTION 'Received provider accounting and raw response are immutable'; END IF;
  IF NEW.state IN ('sending','received','succeeded','unknown') AND NEW.started_at IS NULL THEN RAISE EXCEPTION 'AI send boundary requires a timestamp'; END IF;
  IF NEW.state IN ('sending','received') AND NEW.finished_at IS NOT NULL THEN RAISE EXCEPTION 'Active AI stage cannot be completed'; END IF;
  IF NEW.state='unknown' AND NEW.actual_cost IS NOT NULL THEN RAISE EXCEPTION 'Unknown AI stage cannot claim known cost'; END IF;
  IF OLD.state='reserved' AND NEW.state='failed' AND (NEW.actual_cost<>0 OR NEW.started_at IS NOT NULL OR NEW.error_code<>'not_sent') THEN RAISE EXCEPTION 'Unsent AI refusal has zero provider cost'; END IF;
  IF NEW.result_path<>'' AND (NEW.result_path !~ '^receipts/[a-f0-9]{48}[.]json$' OR NEW.result_sha256 !~ '^[a-f0-9]{64}$') THEN RAISE EXCEPTION 'AI response requires a valid retained reference'; END IF;
  IF (NEW.result_path='')<>(NEW.result_sha256='') THEN RAISE EXCEPTION 'AI response reference is incomplete'; END IF;
  IF OLD.started_at IS NOT NULL AND NEW.started_at IS DISTINCT FROM OLD.started_at THEN RAISE EXCEPTION 'AI send timestamp is immutable'; END IF;
  IF NOT NEW.simulated AND (NEW.provider_request_id<>'' OR NEW.provider_resource_id<>'') AND (
    EXISTS(SELECT 1 FROM core_usage u WHERE split_part(u.provider,':',1)=NEW.provider
      AND ((NEW.provider_request_id<>'' AND NEW.provider_request_id IN (u.provider_request_id,u.provider_resource_id))
        OR (NEW.provider_resource_id<>'' AND NEW.provider_resource_id IN (u.provider_request_id,u.provider_resource_id))))
    OR EXISTS(SELECT 1 FROM core_providerreceipt p WHERE split_part(p.provider,':',1)=NEW.provider
      AND ((NEW.provider_request_id<>'' AND NEW.provider_request_id IN (p.provider_request_id,p.provider_resource_id))
        OR (NEW.provider_resource_id<>'' AND NEW.provider_resource_id IN (p.provider_request_id,p.provider_resource_id)))))
   THEN RAISE EXCEPTION 'Actual provider evidence already belongs to a retained legacy request'; END IF;
  IF NEW.state IN ('received','succeeded','failed') THEN
   IF NEW.simulated THEN
    IF NEW.actual_cost<>0 THEN RAISE EXCEPTION 'Simulated stages have zero provider cost'; END IF;
   ELSIF NEW.started_at IS NOT NULL THEN
    IF NEW.result_path='' OR NEW.provider_resource_id='' OR NEW.provider NOT IN ('anthropic','openai')
      OR NOT NEW.usage ?& ARRAY['input_tokens','output_tokens','cached_input_tokens']
      OR EXISTS(SELECT 1 FROM jsonb_each(NEW.usage) x WHERE x.key IN ('input_tokens','output_tokens','cached_input_tokens','cache_creation_tokens') AND (x.value#>>'{}') !~ '^[0-9]{1,20}$')
      OR NOT NEW.rates ?& ARRAY['input_per_million','output_per_million','cached_per_million','list_cost_usd','discount_rate']
      OR EXISTS(SELECT 1 FROM jsonb_each(NEW.rates) x WHERE x.key IN ('input_per_million','output_per_million','cached_per_million','list_cost_usd','discount_rate') AND ((x.value#>>'{}') !~ '^[+]?[0-9]*[.]?[0-9]+([eE][+-]?[0-9]{1,3})?$' OR length(x.value#>>'{}')>100))
     THEN RAISE EXCEPTION 'Known stage requires valid original provider accounting'; END IF;
    IF (NEW.rates->>'input_per_million')::numeric<>(NEW.config->>'input_rate')::numeric
      OR (NEW.rates->>'output_per_million')::numeric<>(NEW.config->>'output_rate')::numeric
      OR (NEW.rates->>'cached_per_million')::numeric<>(NEW.config->>'cached_rate')::numeric
      OR (NEW.rates->>'discount_rate')::numeric<>COALESCE((NEW.config->>'discount_rate')::numeric,0)
      OR (NEW.rates->>'discount_rate')::numeric NOT BETWEEN 0 AND 1
      OR (NEW.provider='openai' AND (NEW.usage->>'cached_input_tokens')::numeric>(NEW.usage->>'input_tokens')::numeric)
     THEN RAISE EXCEPTION 'Stage meter must use its immutable configured rates'; END IF;
    list_cost=(((NEW.usage->>'input_tokens')::numeric-CASE WHEN NEW.provider='openai' THEN (NEW.usage->>'cached_input_tokens')::numeric ELSE 0 END)*(NEW.rates->>'input_per_million')::numeric
      +(NEW.usage->>'cached_input_tokens')::numeric*(NEW.rates->>'cached_per_million')::numeric
      +COALESCE((NEW.usage->>'cache_creation_tokens')::numeric,0)*(NEW.rates->>'input_per_million')::numeric*1.25
      +(NEW.usage->>'output_tokens')::numeric*(NEW.rates->>'output_per_million')::numeric)/1000000;
    discounted=list_cost*(1-(NEW.rates->>'discount_rate')::numeric)*100000000000;
    integral=floor(discounted);fraction=discounted-integral;
    IF fraction>0.5 OR (fraction=0.5 AND mod(integral,2)=1) THEN integral=integral+1; END IF;
    IF list_cost<>(NEW.rates->>'list_cost_usd')::numeric OR NEW.actual_cost<>integral/100000000000
     THEN RAISE EXCEPTION 'Stage provider cost must equal its independently rounded meter'; END IF;
   END IF;
  END IF;
  RETURN NEW;
 END IF;
 IF NEW.state<>'reserved' OR NEW.started_at IS NOT NULL OR NEW.finished_at IS NOT NULL OR NEW.actual_cost IS NOT NULL
  OR NEW.request_sha256 !~ '^[a-f0-9]{64}$' OR NEW.request_path !~ '^receipts/[a-f0-9]{48}[.]json$'
  OR (NEW.job_id IS NULL)=(NEW.definition_preparation_id IS NULL)
 THEN RAISE EXCEPTION 'AI stage requires one unsent retained request'; END IF;
 IF NEW.job_id IS NOT NULL THEN
  SELECT j.config,j.user_id,e.department_id INTO configuration,actor,department FROM core_job j JOIN core_encounter e ON e.id=j.encounter_id WHERE j.id=NEW.job_id AND j.kind='generation' AND j.state='running';
  IF configuration ? 'semantic_revalidation_contract' THEN
   IF (configuration->>'semantic_revalidation_contract') IS NULL OR configuration->>'semantic_revalidation_contract' NOT IN ('retained-facts-independent-check-v1','retained-facts-independent-check-v2','retained-facts-independent-check-v3')
    OR NEW.stage<>'revalidation_checker' OR NEW.attempt<>1
   THEN RAISE EXCEPTION 'Retained revalidation permits one independent checker only'; END IF;
  ELSE
  IF NOT ((NEW.stage='extractor' AND NEW.attempt=1) OR (NEW.stage IN ('assigner','checker') AND NEW.attempt IN (1,2)))
  THEN RAISE EXCEPTION 'Generation AI stages exceed the bounded pipeline'; END IF;
  END IF;
 ELSE
  SELECT p.config,p.requested_by_id,t.department_id INTO configuration,actor,department FROM core_templatedefinitionpreparation p JOIN core_templateversion v ON v.id=p.source_version_id JOIN core_template t ON t.id=v.template_id WHERE p.id=NEW.definition_preparation_id AND p.state IN ('proposer','checker');
  IF NEW.stage NOT IN ('definition_proposer','definition_checker') OR NEW.attempt<>1 THEN RAISE EXCEPTION 'Definition AI stages exceed the bounded preparation'; END IF;
 END IF;
 IF configuration IS NULL OR NEW.config IS DISTINCT FROM configuration OR NEW.provider IS DISTINCT FROM configuration->>'provider'
  OR NEW.requested_model IS DISTINCT FROM configuration->>'model' OR NEW.simulated IS DISTINCT FROM (configuration->>'mode'<>'live')
 THEN RAISE EXCEPTION 'AI stage must match its immutable authorized parent'; END IF;
 IF NEW.job_id IS NOT NULL THEN
  PERFORM 1 FROM core_job WHERE id=NEW.job_id FOR UPDATE;
  IF configuration->>'semantic_revalidation_contract'='retained-facts-independent-check-v2' THEN
   -- One v2 across jobs, serialized by the immutable original generation.
   PERFORM 1 FROM core_job WHERE id::text=configuration->'semantic_revalidation'->>'parent_job_id' FOR UPDATE;
   IF configuration->'semantic_revalidation'->>'contract' IS DISTINCT FROM 'retained-facts-independent-check-v2'
    OR EXISTS(SELECT 1 FROM core_job other WHERE other.id<>NEW.job_id
      AND other.config->>'semantic_revalidation_contract'='retained-facts-independent-check-v2'
      AND other.config->'semantic_revalidation'->>'parent_job_id'=configuration->'semantic_revalidation'->>'parent_job_id')
    OR NOT EXISTS(
      SELECT 1 FROM core_job child JOIN core_job prior
       ON prior.id::text=configuration->'semantic_revalidation'->'prior_revalidation'->>'job_id'
      JOIN core_aistagereceipt receipt ON receipt.job_id=prior.id
      JOIN core_usage usage ON usage.job_id=prior.id
      WHERE child.id=NEW.job_id AND prior.state='failed' AND prior.finished_at IS NOT NULL
       AND prior.kind='generation' AND prior.encounter_id=child.encounter_id
       AND prior.user_id=child.user_id AND prior.revision=child.revision
       AND prior.config->>'semantic_revalidation_contract'='retained-facts-independent-check-v1'
       AND prior.config->'semantic_revalidation'->>'parent_job_id'=configuration->'semantic_revalidation'->>'parent_job_id'
       AND prior.config->'semantic_revalidation'->>'parent_run_id'=configuration->'semantic_revalidation'->>'parent_run_id'
       AND prior.config->'semantic_revalidation'=((configuration->'semantic_revalidation')-'contract'-'prior_revalidation')
       AND (SELECT count(*) FROM core_job p WHERE p.config->>'semantic_revalidation_contract'='retained-facts-independent-check-v1'
         AND p.config->'semantic_revalidation'->>'parent_job_id'=configuration->'semantic_revalidation'->>'parent_job_id')=1
       AND prior.result_sha256=configuration->'semantic_revalidation'->'prior_revalidation'->>'result_sha256'
       AND prior.result_sha256 ~ '^[a-f0-9]{64}$' AND prior.result_path<>''
       AND md5(prior.config::text)=configuration->'semantic_revalidation'->'prior_revalidation'->>'config_database_md5'
       AND configuration->'semantic_revalidation'->'prior_revalidation'->>'config_sha256' ~ '^[a-f0-9]{64}$'
       AND configuration->'semantic_revalidation'->'prior_revalidation'->>'receipt_config_sha256'=configuration->'semantic_revalidation'->'prior_revalidation'->>'config_sha256'
       AND configuration->'semantic_revalidation'->'prior_revalidation'->>'contract'='retained-facts-independent-check-v1'
       AND configuration->'semantic_revalidation'->'prior_revalidation'->>'state'='failed'
       AND (SELECT count(*) FROM core_aistagereceipt r WHERE r.job_id=prior.id)=1
       AND receipt.id::text=configuration->'semantic_revalidation'->'prior_revalidation'->>'receipt_id'
       AND receipt.stage='revalidation_checker' AND receipt.attempt=1 AND receipt.state='succeeded'
       AND receipt.finished_at IS NOT NULL AND receipt.config=prior.config AND receipt.actual_cost IS NOT NULL
       AND receipt.request_sha256=configuration->'semantic_revalidation'->'prior_revalidation'->>'request_sha256'
       AND receipt.result_sha256=configuration->'semantic_revalidation'->'prior_revalidation'->>'response_sha256'
       AND usage.id::text=configuration->'semantic_revalidation'->'prior_revalidation'->>'usage_id'
       AND usage.actual_cost=receipt.actual_cost
       AND usage.actual_cost::text=configuration->'semantic_revalidation'->'prior_revalidation'->>'actual_cost'
       AND usage.user_id=child.user_id)
   THEN RAISE EXCEPTION 'A distinct v2 check requires the one failed v1 receipt, known usage and unchanged bindings'; END IF;
  END IF;
  IF configuration->>'semantic_revalidation_contract'='retained-facts-independent-check-v3' THEN
   -- Serialize every v3 send for this immutable original generation, across jobs.
   PERFORM 1 FROM core_job WHERE id::text=configuration->'semantic_revalidation'->>'parent_job_id' FOR UPDATE;
   IF configuration->>'semantic_stage_protocol' IS DISTINCT FROM 'quillmd-ai-stages-v1'
    OR configuration->>'semantic_max_calls' IS DISTINCT FROM '1'
    OR NOT quillmd_standing_config(configuration)
    OR configuration->>'semantic_fact_scope_contract' IS DISTINCT FROM 'positioned-complete-assertions-v20'
    OR configuration->'semantic_revalidation'->>'target_scope_contract' IS DISTINCT FROM 'positioned-complete-assertions-v20'
    OR configuration->'semantic_revalidation'->>'contract' IS DISTINCT FROM 'retained-facts-independent-check-v3'
    OR jsonb_typeof(configuration->'semantic_revalidation') IS DISTINCT FROM 'object'
    OR (SELECT count(*) FROM jsonb_object_keys(configuration->'semantic_revalidation'))<>14
    OR NOT (configuration->'semantic_revalidation') ?& ARRAY['parent_job_id','parent_run_id','parent_answers_sha256',
      'source_sha256','definitions_sha256','template_version_id','encounter_id','patient_id','revision',
      'parent_result_sha256','parent_receipts_digest','target_scope_contract','actor_id','contract']
    OR EXISTS(SELECT 1 FROM core_aistagereceipt WHERE job_id=NEW.job_id)
    OR EXISTS(SELECT 1 FROM core_job other WHERE other.id<>NEW.job_id
      AND other.config->>'semantic_revalidation_contract'='retained-facts-independent-check-v3'
      AND other.config->'semantic_revalidation'->>'parent_job_id'=configuration->'semantic_revalidation'->>'parent_job_id')
    OR NOT EXISTS(
      SELECT 1 FROM core_job child JOIN core_job parent
       ON parent.id::text=configuration->'semantic_revalidation'->>'parent_job_id'
      JOIN core_encounter e ON e.id=child.encounter_id
      JOIN core_codingrun source_run ON source_run.id::text=configuration->'semantic_revalidation'->>'parent_run_id'
      WHERE child.id=NEW.job_id AND parent.kind='generation' AND parent.state='succeeded'
       AND parent.finished_at IS NOT NULL AND parent.result_path<>''
       AND parent.encounter_id=child.encounter_id AND parent.user_id=child.user_id
       AND parent.revision=child.revision AND e.revision=child.revision
       AND e.revision::text=configuration->'semantic_revalidation'->>'revision'
       AND e.status='review' AND e.template_review='{}'::jsonb
       AND e.id::text=configuration->'semantic_revalidation'->>'encounter_id'
       AND e.patient_id::text=configuration->'semantic_revalidation'->>'patient_id'
       AND e.template_version_id::text=configuration->'semantic_revalidation'->>'template_version_id'
       AND child.user_id::text=configuration->'semantic_revalidation'->>'actor_id'
       AND child.request_key='semantic-revalidation:'||parent.id::text||':retained-facts-independent-check-v3'
       AND parent.result_sha256=configuration->'semantic_revalidation'->>'parent_result_sha256'
       AND parent.result_sha256 ~ '^[a-f0-9]{64}$'
       AND parent.config->>'semantic_source_sha256'=configuration->'semantic_revalidation'->>'source_sha256'
       AND encode(sha256(convert_to(e.notes,'UTF8')),'hex')=configuration->'semantic_revalidation'->>'source_sha256'
       AND parent.config->>'semantic_definitions_sha256'=configuration->'semantic_revalidation'->>'definitions_sha256'
       AND parent.config->>'semantic_template_version'=e.template_version_id::text
       AND configuration->>'semantic_source_sha256'=configuration->'semantic_revalidation'->>'source_sha256'
       AND configuration->>'semantic_definitions_sha256'=configuration->'semantic_revalidation'->>'definitions_sha256'
       AND configuration->>'semantic_template_version'=e.template_version_id::text
       AND configuration->'semantic_revalidation'->>'parent_answers_sha256' ~ '^[a-f0-9]{64}$'
       AND configuration->'semantic_revalidation'->>'parent_receipts_digest' ~ '^[a-f0-9]{64}$'
       AND source_run.encounter_id=e.id AND source_run.user_id=child.user_id
       AND source_run.config->>'provider'='corti'
       AND (source_run.config->>'mode'='live' OR (source_run.config->>'mode'='retained_live'
         AND source_run.config->'retained_prediction'->>'contract'='retained-live-context-review-v1'))
       AND source_run.state IN ('succeeded','needs_detail')
       AND source_run.inputs->>'notes'=e.notes AND source_run.inputs->'answers'=e.answers
       AND NOT parent.config ? 'semantic_revalidation_contract'
       AND (SELECT count(*) FROM core_aistagereceipt r WHERE r.job_id=parent.id)=5
       AND NOT EXISTS(SELECT 1 FROM core_aistagereceipt r WHERE r.job_id=parent.id
         AND (r.state<>'succeeded' OR r.finished_at IS NULL OR r.actual_cost IS NULL OR r.config IS DISTINCT FROM parent.config)))
   THEN RAISE EXCEPTION 'One v3 check requires its unchanged original source, actor, revision and complete five-stage chain'; END IF;
  ELSIF configuration ? 'semantic_revalidation_contract' THEN
   IF configuration->>'semantic_stage_protocol' IS DISTINCT FROM 'quillmd-ai-stages-v1'
    OR configuration->>'semantic_max_calls' IS DISTINCT FROM '1'
    OR NOT quillmd_standing_config(configuration)
    OR configuration->'semantic_revalidation'->>'target_scope_contract' IS DISTINCT FROM 'positioned-objective-negation-v12'
    OR EXISTS(SELECT 1 FROM core_aistagereceipt WHERE job_id=NEW.job_id)
    OR NOT EXISTS(
      SELECT 1 FROM core_job child JOIN core_job parent
       ON parent.id::text=configuration->'semantic_revalidation'->>'parent_job_id'
      JOIN core_encounter e ON e.id=child.encounter_id
      WHERE child.id=NEW.job_id AND parent.kind='generation' AND parent.state='succeeded'
       AND parent.encounter_id=child.encounter_id AND parent.user_id=child.user_id
       AND parent.revision=child.revision AND e.revision=child.revision
       AND e.id::text=configuration->'semantic_revalidation'->>'encounter_id'
       AND e.patient_id::text=configuration->'semantic_revalidation'->>'patient_id'
       AND e.template_version_id::text=configuration->'semantic_revalidation'->>'template_version_id'
       AND child.user_id::text=configuration->'semantic_revalidation'->>'actor_id'
       AND parent.result_sha256=configuration->'semantic_revalidation'->>'parent_result_sha256'
       AND parent.config->>'semantic_source_sha256'=configuration->'semantic_revalidation'->>'source_sha256'
       AND parent.config->>'semantic_definitions_sha256'=configuration->'semantic_revalidation'->>'definitions_sha256'
       AND NOT parent.config ? 'semantic_revalidation_contract'
       AND (SELECT count(*) FROM core_aistagereceipt r WHERE r.job_id=parent.id AND r.state='succeeded')=5)
   THEN RAISE EXCEPTION 'Retained revalidation requires its immutable source, parent and one-call authority'; END IF;
  ELSE
  IF configuration->>'semantic_stage_protocol'<>'quillmd-ai-stages-v1' OR configuration->>'semantic_max_calls'<>'5'
   THEN RAISE EXCEPTION 'Generation requires its immutable five-call quote'; END IF;
  SELECT count(*) INTO prior_count FROM core_aistagereceipt WHERE job_id=NEW.job_id;
  preceding=CASE WHEN NEW.stage='assigner' AND NEW.attempt=1 THEN 'extractor'
   WHEN NEW.stage='checker' THEN 'assigner' WHEN NEW.stage='assigner' AND NEW.attempt=2 THEN 'checker' ELSE NULL END;
  IF prior_count>=5 OR EXISTS(SELECT 1 FROM core_aistagereceipt WHERE job_id=NEW.job_id AND state<>'succeeded')
   OR (NEW.stage='extractor' AND prior_count<>0)
   OR (preceding IS NOT NULL AND NOT EXISTS(SELECT 1 FROM core_aistagereceipt WHERE job_id=NEW.job_id AND stage=preceding AND attempt=CASE WHEN NEW.stage='assigner' THEN 1 ELSE NEW.attempt END AND state='succeeded'))
  THEN RAISE EXCEPTION 'Generation AI stage predecessor is unavailable or unresolved'; END IF;
  END IF;
 ELSE
  PERFORM 1 FROM core_templatedefinitionpreparation WHERE id=NEW.definition_preparation_id FOR UPDATE;
  IF configuration->>'definition_stage_protocol'<>'quillmd-ai-stages-v1' OR configuration->>'definition_max_calls'<>'2' OR configuration->>'definition_output_token_limit'<>'16000' THEN RAISE EXCEPTION 'Definitions require their immutable two-call quote'; END IF;
  SELECT count(*) INTO prior_count FROM core_aistagereceipt WHERE definition_preparation_id=NEW.definition_preparation_id;
  IF prior_count>=2 OR EXISTS(SELECT 1 FROM core_aistagereceipt WHERE definition_preparation_id=NEW.definition_preparation_id AND state<>'succeeded')
   OR (NEW.stage='definition_proposer' AND prior_count<>0)
   OR (NEW.stage='definition_checker' AND NOT EXISTS(SELECT 1 FROM core_aistagereceipt WHERE definition_preparation_id=NEW.definition_preparation_id AND stage='definition_proposer' AND state='succeeded'))
  THEN RAISE EXCEPTION 'Definition stage predecessor is unavailable or unresolved'; END IF;
 END IF;
 IF quillmd_standing_config(configuration) THEN PERFORM quillmd_standing_actor(actor,department,configuration); END IF;
 RETURN NEW;
END; $$;
'''

REVALIDATION_REVERSE = r'''
CREATE OR REPLACE FUNCTION quillmd_ai_stage_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE configuration jsonb; actor uuid; department uuid; preceding text; prior_count integer; list_cost numeric; discounted numeric; integral numeric; fraction numeric;
BEGIN
 IF TG_OP='DELETE' THEN RAISE EXCEPTION 'AI stage history is retained'; END IF;
 IF TG_OP='UPDATE' THEN
  IF OLD.finished_at IS NOT NULL OR NEW.id<>OLD.id OR NEW.created_at<>OLD.created_at
   OR NEW.job_id IS DISTINCT FROM OLD.job_id OR NEW.definition_preparation_id IS DISTINCT FROM OLD.definition_preparation_id
   OR NEW.stage<>OLD.stage OR NEW.attempt<>OLD.attempt OR NEW.config IS DISTINCT FROM OLD.config
   OR NEW.request_path<>OLD.request_path OR NEW.request_sha256<>OLD.request_sha256
   OR NEW.provider<>OLD.provider OR NEW.requested_model<>OLD.requested_model OR NEW.quote_maximum<>OLD.quote_maximum
   OR NEW.simulated<>OLD.simulated
  THEN RAISE EXCEPTION 'AI stage request and completed evidence are immutable'; END IF;
  IF NOT ((OLD.state='reserved' AND NEW.state IN ('sending','failed')) OR (OLD.state='sending' AND (NEW.state IN ('received','unknown') OR (NEW.state='sending' AND OLD.result_path='' AND NEW.result_path<>'' AND NEW.actual_cost IS NULL))) OR (OLD.state='received' AND NEW.state IN ('succeeded','failed')))
  THEN RAISE EXCEPTION 'AI stage cannot replay or skip its send boundary'; END IF;
  IF NEW.state IN ('succeeded','failed','unknown') AND NEW.finished_at IS NULL THEN RAISE EXCEPTION 'Terminal AI stage requires its completion time'; END IF;
  IF NEW.state IN ('received','succeeded','failed') AND NEW.actual_cost IS NULL THEN RAISE EXCEPTION 'Known AI stage requires recorded provider cost'; END IF;
  IF NEW.state IN ('received','succeeded') AND (NEW.result_path='' OR NEW.result_sha256 !~ '^[a-f0-9]{64}$') THEN RAISE EXCEPTION 'Successful AI stage requires retained response'; END IF;
  IF OLD.result_path<>'' AND (NEW.result_path<>OLD.result_path OR NEW.result_sha256<>OLD.result_sha256 OR (OLD.provider_request_id<>'' AND NEW.provider_request_id<>OLD.provider_request_id) OR (OLD.provider_resource_id<>'' AND NEW.provider_resource_id<>OLD.provider_resource_id) OR NEW.returned_model<>OLD.returned_model) THEN RAISE EXCEPTION 'Retained raw provider response is immutable'; END IF;
  IF OLD.actual_cost IS NOT NULL AND (NEW.actual_cost IS DISTINCT FROM OLD.actual_cost OR NEW.usage IS DISTINCT FROM OLD.usage OR NEW.rates IS DISTINCT FROM OLD.rates OR NEW.result_path<>OLD.result_path OR NEW.result_sha256<>OLD.result_sha256 OR NEW.provider_request_id<>OLD.provider_request_id OR NEW.provider_resource_id<>OLD.provider_resource_id OR NEW.returned_model<>OLD.returned_model)
  THEN RAISE EXCEPTION 'Received provider accounting and raw response are immutable'; END IF;
  IF NEW.state IN ('sending','received','succeeded','unknown') AND NEW.started_at IS NULL THEN RAISE EXCEPTION 'AI send boundary requires a timestamp'; END IF;
  IF NEW.state IN ('sending','received') AND NEW.finished_at IS NOT NULL THEN RAISE EXCEPTION 'Active AI stage cannot be completed'; END IF;
  IF NEW.state='unknown' AND NEW.actual_cost IS NOT NULL THEN RAISE EXCEPTION 'Unknown AI stage cannot claim known cost'; END IF;
  IF OLD.state='reserved' AND NEW.state='failed' AND (NEW.actual_cost<>0 OR NEW.started_at IS NOT NULL OR NEW.error_code<>'not_sent') THEN RAISE EXCEPTION 'Unsent AI refusal has zero provider cost'; END IF;
  IF NEW.result_path<>'' AND (NEW.result_path !~ '^receipts/[a-f0-9]{48}[.]json$' OR NEW.result_sha256 !~ '^[a-f0-9]{64}$') THEN RAISE EXCEPTION 'AI response requires a valid retained reference'; END IF;
  IF (NEW.result_path='')<>(NEW.result_sha256='') THEN RAISE EXCEPTION 'AI response reference is incomplete'; END IF;
  IF OLD.started_at IS NOT NULL AND NEW.started_at IS DISTINCT FROM OLD.started_at THEN RAISE EXCEPTION 'AI send timestamp is immutable'; END IF;
  IF NOT NEW.simulated AND (NEW.provider_request_id<>'' OR NEW.provider_resource_id<>'') AND (
    EXISTS(SELECT 1 FROM core_usage u WHERE split_part(u.provider,':',1)=NEW.provider
      AND ((NEW.provider_request_id<>'' AND NEW.provider_request_id IN (u.provider_request_id,u.provider_resource_id))
        OR (NEW.provider_resource_id<>'' AND NEW.provider_resource_id IN (u.provider_request_id,u.provider_resource_id))))
    OR EXISTS(SELECT 1 FROM core_providerreceipt p WHERE split_part(p.provider,':',1)=NEW.provider
      AND ((NEW.provider_request_id<>'' AND NEW.provider_request_id IN (p.provider_request_id,p.provider_resource_id))
        OR (NEW.provider_resource_id<>'' AND NEW.provider_resource_id IN (p.provider_request_id,p.provider_resource_id)))))
   THEN RAISE EXCEPTION 'Actual provider evidence already belongs to a retained legacy request'; END IF;
  IF NEW.state IN ('received','succeeded','failed') THEN
   IF NEW.simulated THEN
    IF NEW.actual_cost<>0 THEN RAISE EXCEPTION 'Simulated stages have zero provider cost'; END IF;
   ELSIF NEW.started_at IS NOT NULL THEN
    IF NEW.result_path='' OR NEW.provider_resource_id='' OR NEW.provider NOT IN ('anthropic','openai')
      OR NOT NEW.usage ?& ARRAY['input_tokens','output_tokens','cached_input_tokens']
      OR EXISTS(SELECT 1 FROM jsonb_each(NEW.usage) x WHERE x.key IN ('input_tokens','output_tokens','cached_input_tokens','cache_creation_tokens') AND (x.value#>>'{}') !~ '^[0-9]{1,20}$')
      OR NOT NEW.rates ?& ARRAY['input_per_million','output_per_million','cached_per_million','list_cost_usd','discount_rate']
      OR EXISTS(SELECT 1 FROM jsonb_each(NEW.rates) x WHERE x.key IN ('input_per_million','output_per_million','cached_per_million','list_cost_usd','discount_rate') AND ((x.value#>>'{}') !~ '^[+]?[0-9]*[.]?[0-9]+([eE][+-]?[0-9]{1,3})?$' OR length(x.value#>>'{}')>100))
     THEN RAISE EXCEPTION 'Known stage requires valid original provider accounting'; END IF;
    IF (NEW.rates->>'input_per_million')::numeric<>(NEW.config->>'input_rate')::numeric
      OR (NEW.rates->>'output_per_million')::numeric<>(NEW.config->>'output_rate')::numeric
      OR (NEW.rates->>'cached_per_million')::numeric<>(NEW.config->>'cached_rate')::numeric
      OR (NEW.rates->>'discount_rate')::numeric<>COALESCE((NEW.config->>'discount_rate')::numeric,0)
      OR (NEW.rates->>'discount_rate')::numeric NOT BETWEEN 0 AND 1
      OR (NEW.provider='openai' AND (NEW.usage->>'cached_input_tokens')::numeric>(NEW.usage->>'input_tokens')::numeric)
     THEN RAISE EXCEPTION 'Stage meter must use its immutable configured rates'; END IF;
    list_cost=(((NEW.usage->>'input_tokens')::numeric-CASE WHEN NEW.provider='openai' THEN (NEW.usage->>'cached_input_tokens')::numeric ELSE 0 END)*(NEW.rates->>'input_per_million')::numeric
      +(NEW.usage->>'cached_input_tokens')::numeric*(NEW.rates->>'cached_per_million')::numeric
      +COALESCE((NEW.usage->>'cache_creation_tokens')::numeric,0)*(NEW.rates->>'input_per_million')::numeric*1.25
      +(NEW.usage->>'output_tokens')::numeric*(NEW.rates->>'output_per_million')::numeric)/1000000;
    discounted=list_cost*(1-(NEW.rates->>'discount_rate')::numeric)*100000000000;
    integral=floor(discounted);fraction=discounted-integral;
    IF fraction>0.5 OR (fraction=0.5 AND mod(integral,2)=1) THEN integral=integral+1; END IF;
    IF list_cost<>(NEW.rates->>'list_cost_usd')::numeric OR NEW.actual_cost<>integral/100000000000
     THEN RAISE EXCEPTION 'Stage provider cost must equal its independently rounded meter'; END IF;
   END IF;
  END IF;
  RETURN NEW;
 END IF;
 IF NEW.state<>'reserved' OR NEW.started_at IS NOT NULL OR NEW.finished_at IS NOT NULL OR NEW.actual_cost IS NOT NULL
  OR NEW.request_sha256 !~ '^[a-f0-9]{64}$' OR NEW.request_path !~ '^receipts/[a-f0-9]{48}[.]json$'
  OR (NEW.job_id IS NULL)=(NEW.definition_preparation_id IS NULL)
 THEN RAISE EXCEPTION 'AI stage requires one unsent retained request'; END IF;
 IF NEW.job_id IS NOT NULL THEN
  SELECT j.config,j.user_id,e.department_id INTO configuration,actor,department FROM core_job j JOIN core_encounter e ON e.id=j.encounter_id WHERE j.id=NEW.job_id AND j.kind='generation' AND j.state='running';
  IF configuration ? 'semantic_revalidation_contract' THEN
   IF (configuration->>'semantic_revalidation_contract') IS NULL OR configuration->>'semantic_revalidation_contract' NOT IN ('retained-facts-independent-check-v1','retained-facts-independent-check-v2')
    OR NEW.stage<>'revalidation_checker' OR NEW.attempt<>1
   THEN RAISE EXCEPTION 'Retained revalidation permits one independent checker only'; END IF;
  ELSE
  IF NOT ((NEW.stage='extractor' AND NEW.attempt=1) OR (NEW.stage IN ('assigner','checker') AND NEW.attempt IN (1,2)))
  THEN RAISE EXCEPTION 'Generation AI stages exceed the bounded pipeline'; END IF;
  END IF;
 ELSE
  SELECT p.config,p.requested_by_id,t.department_id INTO configuration,actor,department FROM core_templatedefinitionpreparation p JOIN core_templateversion v ON v.id=p.source_version_id JOIN core_template t ON t.id=v.template_id WHERE p.id=NEW.definition_preparation_id AND p.state IN ('proposer','checker');
  IF NEW.stage NOT IN ('definition_proposer','definition_checker') OR NEW.attempt<>1 THEN RAISE EXCEPTION 'Definition AI stages exceed the bounded preparation'; END IF;
 END IF;
 IF configuration IS NULL OR NEW.config IS DISTINCT FROM configuration OR NEW.provider IS DISTINCT FROM configuration->>'provider'
  OR NEW.requested_model IS DISTINCT FROM configuration->>'model' OR NEW.simulated IS DISTINCT FROM (configuration->>'mode'<>'live')
 THEN RAISE EXCEPTION 'AI stage must match its immutable authorized parent'; END IF;
 IF NEW.job_id IS NOT NULL THEN
  PERFORM 1 FROM core_job WHERE id=NEW.job_id FOR UPDATE;
  IF configuration->>'semantic_revalidation_contract'='retained-facts-independent-check-v2' THEN
   -- One v2 across jobs, serialized by the immutable original generation.
   PERFORM 1 FROM core_job WHERE id::text=configuration->'semantic_revalidation'->>'parent_job_id' FOR UPDATE;
   IF configuration->'semantic_revalidation'->>'contract' IS DISTINCT FROM 'retained-facts-independent-check-v2'
    OR EXISTS(SELECT 1 FROM core_job other WHERE other.id<>NEW.job_id
      AND other.config->>'semantic_revalidation_contract'='retained-facts-independent-check-v2'
      AND other.config->'semantic_revalidation'->>'parent_job_id'=configuration->'semantic_revalidation'->>'parent_job_id')
    OR NOT EXISTS(
      SELECT 1 FROM core_job child JOIN core_job prior
       ON prior.id::text=configuration->'semantic_revalidation'->'prior_revalidation'->>'job_id'
      JOIN core_aistagereceipt receipt ON receipt.job_id=prior.id
      JOIN core_usage usage ON usage.job_id=prior.id
      WHERE child.id=NEW.job_id AND prior.state='failed' AND prior.finished_at IS NOT NULL
       AND prior.kind='generation' AND prior.encounter_id=child.encounter_id
       AND prior.user_id=child.user_id AND prior.revision=child.revision
       AND prior.config->>'semantic_revalidation_contract'='retained-facts-independent-check-v1'
       AND prior.config->'semantic_revalidation'->>'parent_job_id'=configuration->'semantic_revalidation'->>'parent_job_id'
       AND prior.config->'semantic_revalidation'->>'parent_run_id'=configuration->'semantic_revalidation'->>'parent_run_id'
       AND prior.config->'semantic_revalidation'=((configuration->'semantic_revalidation')-'contract'-'prior_revalidation')
       AND (SELECT count(*) FROM core_job p WHERE p.config->>'semantic_revalidation_contract'='retained-facts-independent-check-v1'
         AND p.config->'semantic_revalidation'->>'parent_job_id'=configuration->'semantic_revalidation'->>'parent_job_id')=1
       AND prior.result_sha256=configuration->'semantic_revalidation'->'prior_revalidation'->>'result_sha256'
       AND prior.result_sha256 ~ '^[a-f0-9]{64}$' AND prior.result_path<>''
       AND md5(prior.config::text)=configuration->'semantic_revalidation'->'prior_revalidation'->>'config_database_md5'
       AND configuration->'semantic_revalidation'->'prior_revalidation'->>'config_sha256' ~ '^[a-f0-9]{64}$'
       AND configuration->'semantic_revalidation'->'prior_revalidation'->>'receipt_config_sha256'=configuration->'semantic_revalidation'->'prior_revalidation'->>'config_sha256'
       AND configuration->'semantic_revalidation'->'prior_revalidation'->>'contract'='retained-facts-independent-check-v1'
       AND configuration->'semantic_revalidation'->'prior_revalidation'->>'state'='failed'
       AND (SELECT count(*) FROM core_aistagereceipt r WHERE r.job_id=prior.id)=1
       AND receipt.id::text=configuration->'semantic_revalidation'->'prior_revalidation'->>'receipt_id'
       AND receipt.stage='revalidation_checker' AND receipt.attempt=1 AND receipt.state='succeeded'
       AND receipt.finished_at IS NOT NULL AND receipt.config=prior.config AND receipt.actual_cost IS NOT NULL
       AND receipt.request_sha256=configuration->'semantic_revalidation'->'prior_revalidation'->>'request_sha256'
       AND receipt.result_sha256=configuration->'semantic_revalidation'->'prior_revalidation'->>'response_sha256'
       AND usage.id::text=configuration->'semantic_revalidation'->'prior_revalidation'->>'usage_id'
       AND usage.actual_cost=receipt.actual_cost
       AND usage.actual_cost::text=configuration->'semantic_revalidation'->'prior_revalidation'->>'actual_cost'
       AND usage.user_id=child.user_id)
   THEN RAISE EXCEPTION 'A distinct v2 check requires the one failed v1 receipt, known usage and unchanged bindings'; END IF;
  END IF;
  IF configuration ? 'semantic_revalidation_contract' THEN
   IF configuration->>'semantic_stage_protocol' IS DISTINCT FROM 'quillmd-ai-stages-v1'
    OR configuration->>'semantic_max_calls' IS DISTINCT FROM '1'
    OR NOT quillmd_standing_config(configuration)
    OR configuration->'semantic_revalidation'->>'target_scope_contract' IS DISTINCT FROM 'positioned-objective-negation-v12'
    OR EXISTS(SELECT 1 FROM core_aistagereceipt WHERE job_id=NEW.job_id)
    OR NOT EXISTS(
      SELECT 1 FROM core_job child JOIN core_job parent
       ON parent.id::text=configuration->'semantic_revalidation'->>'parent_job_id'
      JOIN core_encounter e ON e.id=child.encounter_id
      WHERE child.id=NEW.job_id AND parent.kind='generation' AND parent.state='succeeded'
       AND parent.encounter_id=child.encounter_id AND parent.user_id=child.user_id
       AND parent.revision=child.revision AND e.revision=child.revision
       AND e.id::text=configuration->'semantic_revalidation'->>'encounter_id'
       AND e.patient_id::text=configuration->'semantic_revalidation'->>'patient_id'
       AND e.template_version_id::text=configuration->'semantic_revalidation'->>'template_version_id'
       AND child.user_id::text=configuration->'semantic_revalidation'->>'actor_id'
       AND parent.result_sha256=configuration->'semantic_revalidation'->>'parent_result_sha256'
       AND parent.config->>'semantic_source_sha256'=configuration->'semantic_revalidation'->>'source_sha256'
       AND parent.config->>'semantic_definitions_sha256'=configuration->'semantic_revalidation'->>'definitions_sha256'
       AND NOT parent.config ? 'semantic_revalidation_contract'
       AND (SELECT count(*) FROM core_aistagereceipt r WHERE r.job_id=parent.id AND r.state='succeeded')=5)
   THEN RAISE EXCEPTION 'Retained revalidation requires its immutable source, parent and one-call authority'; END IF;
  ELSE
  IF configuration->>'semantic_stage_protocol'<>'quillmd-ai-stages-v1' OR configuration->>'semantic_max_calls'<>'5'
   THEN RAISE EXCEPTION 'Generation requires its immutable five-call quote'; END IF;
  SELECT count(*) INTO prior_count FROM core_aistagereceipt WHERE job_id=NEW.job_id;
  preceding=CASE WHEN NEW.stage='assigner' AND NEW.attempt=1 THEN 'extractor'
   WHEN NEW.stage='checker' THEN 'assigner' WHEN NEW.stage='assigner' AND NEW.attempt=2 THEN 'checker' ELSE NULL END;
  IF prior_count>=5 OR EXISTS(SELECT 1 FROM core_aistagereceipt WHERE job_id=NEW.job_id AND state<>'succeeded')
   OR (NEW.stage='extractor' AND prior_count<>0)
   OR (preceding IS NOT NULL AND NOT EXISTS(SELECT 1 FROM core_aistagereceipt WHERE job_id=NEW.job_id AND stage=preceding AND attempt=CASE WHEN NEW.stage='assigner' THEN 1 ELSE NEW.attempt END AND state='succeeded'))
  THEN RAISE EXCEPTION 'Generation AI stage predecessor is unavailable or unresolved'; END IF;
  END IF;
 ELSE
  PERFORM 1 FROM core_templatedefinitionpreparation WHERE id=NEW.definition_preparation_id FOR UPDATE;
  IF configuration->>'definition_stage_protocol'<>'quillmd-ai-stages-v1' OR configuration->>'definition_max_calls'<>'2' OR configuration->>'definition_output_token_limit'<>'16000' THEN RAISE EXCEPTION 'Definitions require their immutable two-call quote'; END IF;
  SELECT count(*) INTO prior_count FROM core_aistagereceipt WHERE definition_preparation_id=NEW.definition_preparation_id;
  IF prior_count>=2 OR EXISTS(SELECT 1 FROM core_aistagereceipt WHERE definition_preparation_id=NEW.definition_preparation_id AND state<>'succeeded')
   OR (NEW.stage='definition_proposer' AND prior_count<>0)
   OR (NEW.stage='definition_checker' AND NOT EXISTS(SELECT 1 FROM core_aistagereceipt WHERE definition_preparation_id=NEW.definition_preparation_id AND stage='definition_proposer' AND state='succeeded'))
  THEN RAISE EXCEPTION 'Definition stage predecessor is unavailable or unresolved'; END IF;
 END IF;
 IF quillmd_standing_config(configuration) THEN PERFORM quillmd_standing_actor(actor,department,configuration); END IF;
 RETURN NEW;
END; $$;
'''


class Migration(migrations.Migration):
    dependencies = [('core', '0032_coding_source_decision')]
    operations = [migrations.RunSQL(REVALIDATION_SQL, REVALIDATION_REVERSE)]
