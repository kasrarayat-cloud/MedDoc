"""Prospective definition capacity only; retain every other immutable stage guard."""
from importlib import import_module
from django.db import migrations

PREVIOUS_SQL=import_module('core.migrations.0033_retained_semantic_revalidation_v3').REVALIDATION_SQL
OLD_CONDITION="  IF configuration->>'definition_stage_protocol'<>'quillmd-ai-stages-v1' OR configuration->>'definition_max_calls'<>'2' OR configuration->>'definition_output_token_limit'<>'16000' THEN RAISE EXCEPTION 'Definitions require their immutable two-call quote'; END IF;"
NEW_CONDITION="""  IF configuration->>'definition_stage_protocol' IS DISTINCT FROM 'quillmd-ai-stages-v1'
   OR configuration->>'definition_max_calls' IS DISTINCT FROM '2'
   OR configuration->>'definition_request_byte_limit' IS DISTINCT FROM '512000'
   OR NOT (
    (NOT configuration ? 'definition_capacity_profile' AND NOT configuration ? 'definition_timeout_seconds'
     AND configuration->>'definition_output_token_limit' IS NOT DISTINCT FROM '16000')
    OR (configuration->>'definition_capacity_profile' IS NOT DISTINCT FROM 'bounded-definition-output-32k-v1'
     AND configuration->>'provider' IS NOT DISTINCT FROM 'anthropic'
     AND configuration->>'model' IS NOT DISTINCT FROM 'claude-sonnet-5-5'
     AND configuration->>'semantic_definition_version' IS NOT DISTINCT FROM '4'
     AND jsonb_typeof(configuration->'semantic_definition_version') IS NOT DISTINCT FROM 'number'
     AND configuration->>'semantic_component_contract' IS NOT DISTINCT FROM 'field-components-v2'
     AND configuration->>'definition_output_token_limit' IS NOT DISTINCT FROM '32000'
     AND jsonb_typeof(configuration->'definition_output_token_limit') IS NOT DISTINCT FROM 'number'
     AND configuration->>'definition_timeout_seconds' IS NOT DISTINCT FROM '240'
     AND jsonb_typeof(configuration->'definition_timeout_seconds') IS NOT DISTINCT FROM 'number'
     AND jsonb_typeof(configuration->'definition_max_calls') IS NOT DISTINCT FROM 'number'
     AND jsonb_typeof(configuration->'definition_request_byte_limit') IS NOT DISTINCT FROM 'number'))
  THEN RAISE EXCEPTION 'Definitions require their immutable two-call quote'; END IF;"""
if PREVIOUS_SQL.count(OLD_CONDITION)!=1:
    raise RuntimeError('The historical definition capacity guard must match exactly once.')
CAPACITY_SQL=PREVIOUS_SQL.replace(OLD_CONDITION,NEW_CONDITION)


class Migration(migrations.Migration):
    dependencies=[('core','0034_source_interpretation')]
    operations=[migrations.RunSQL(CAPACITY_SQL,PREVIOUS_SQL)]
