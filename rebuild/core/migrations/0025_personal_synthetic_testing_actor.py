"""Prospective enrollment of one existing synthetic clinician, with no row rewrite.

The finite actor helper and every finite branch remain unchanged. The immutable
enrollment discriminator belongs only to new requests from the exact added pair.
"""
import importlib
import re

from django.db import migrations

ACTOR = 'e1a20625-455d-4603-a874-794327b19d10'
DEPARTMENT = '46a5abdd-36f1-41f0-968f-8c09c39d9daa'
ENROLLMENT = 'quillmd-actual-clinician-20261010-v1'
_previous = importlib.import_module('core.migrations.0024_standing_testing_authority')
_pattern = r'CREATE (?:OR REPLACE )?FUNCTION (quillmd_[a-z_]+)\([^)]*\) RETURNS [^$]*?AS \$\$.*?\$\$;'
ORIGINALS = {match.group(1): match.group(0) for match in re.finditer(_pattern, _previous.SQL, re.S)}

SQL = r"""
CREATE FUNCTION quillmd_standing_actor(actor uuid, department uuid, config jsonb) RETURNS void LANGUAGE plpgsql AS $$
BEGIN
 IF NOT quillmd_standing_config(config)
 THEN RAISE EXCEPTION 'Standing actor requires its complete immutable testing authority'; END IF;
 IF actor='@ACTOR@' AND department='@DEPARTMENT@' THEN
  IF jsonb_typeof(config->'testing_actor_enrollment') IS DISTINCT FROM 'string'
    OR config->>'testing_actor_enrollment' IS DISTINCT FROM '@ENROLLMENT@'
    OR NOT EXISTS(SELECT 1 FROM core_membership m JOIN core_user u ON u.id=m.user_id
      WHERE m.user_id=actor AND m.department_id=department AND m.active AND u.is_active
        AND u.verified_at IS NOT NULL AND m.role IN ('owner','clinician','manager'))
  THEN RAISE EXCEPTION 'Standing clinician requires its exact prospective enrollment and active synthetic access'; END IF;
 ELSE
  IF config ? 'testing_actor_enrollment'
  THEN RAISE EXCEPTION 'The clinician enrollment cannot be used by another testing actor'; END IF;
  PERFORM quillmd_delivery_actor(actor,department);
 END IF;
END; $$;
""".replace('@ACTOR@', ACTOR).replace('@DEPARTMENT@', DEPARTMENT).replace('@ENROLLMENT@', ENROLLMENT)

REPLACEMENTS = {}
_config = ORIGINALS['quillmd_standing_config']
_selector = "ARRAY['testing_authority_mode','testing_authority_id','testing_authority_sha256','testing_purpose']"
assert _config.count(_selector) == 2
_config = _config.replace(_selector, _selector[:-1] + ",'testing_actor_enrollment']", 1)
_check = " IF NOT(config ?& " + _selector + ")"
assert _config.count(_check) == 1
_config = _config.replace(_check,
    " IF (config ? 'testing_actor_enrollment' AND (jsonb_typeof(config->'testing_actor_enrollment') IS DISTINCT FROM 'string'\n"
    "     OR config->>'testing_actor_enrollment' IS DISTINCT FROM '" + ENROLLMENT + "'))\n"
    "  OR NOT(config ?& " + _selector + ")", 1)
REPLACEMENTS['quillmd_standing_config'] = _config

for _name, _old, _new in (
    ('quillmd_standing_job_guard',
     'PERFORM quillmd_delivery_actor(NEW.user_id,department);',
     'PERFORM quillmd_standing_actor(NEW.user_id,department,NEW.config);'),
    ('quillmd_testing_reservation_guard',
     'PERFORM quillmd_delivery_actor(actor,department);',
     'PERFORM quillmd_standing_actor(actor,department,configuration);'),
    ('quillmd_preparation_pilot_guard',
     'PERFORM quillmd_delivery_actor(NEW.requested_by_id,department);',
     'PERFORM quillmd_standing_actor(NEW.requested_by_id,department,NEW.config);'),
    ('quillmd_preparation_send_guard',
     'PERFORM quillmd_delivery_actor(actor,department);',
     'PERFORM quillmd_standing_actor(actor,department,configuration);'),
):
    _original = ORIGINALS[_name]
    # Preparation callers also retain their later finite-campaign actor call.
    # Change the first, standing-only call and preserve the remaining bytes.
    assert _old in _original
    REPLACEMENTS[_name] = _original.replace(_old, _new, 1)
    if _name == 'quillmd_standing_job_guard':
        REPLACEMENTS[_name] = REPLACEMENTS[_name].replace(_new,
            _new + "\n IF NEW.user_id='" + ACTOR + "' AND NOT EXISTS(SELECT 1 FROM core_encounter\n"
            "   WHERE id=NEW.encounter_id AND created_by_id=NEW.user_id)\n"
            " THEN RAISE EXCEPTION 'The enrolled clinician requires their own synthetic document'; END IF;", 1)

def replace_statement(statement):
    return re.sub(r'^CREATE (?:OR REPLACE )?FUNCTION ', 'CREATE OR REPLACE FUNCTION ', statement, count=1)

SQL += '\n' + '\n'.join(replace_statement(statement) for statement in REPLACEMENTS.values())
REVERSE = r"""
DO $$ BEGIN
 IF EXISTS(SELECT 1 FROM core_templatepreparation WHERE config ? 'testing_actor_enrollment')
 OR EXISTS(SELECT 1 FROM core_job WHERE config ? 'testing_actor_enrollment')
 THEN RAISE EXCEPTION 'Retained clinician testing requests forbid reversing enrollment controls'; END IF;
END; $$;
""" + '\n'.join(replace_statement(ORIGINALS[name]) for name in REPLACEMENTS) + '\nDROP FUNCTION quillmd_standing_actor(uuid,uuid,jsonb);'


class Migration(migrations.Migration):
    dependencies = [('core', '0024_standing_testing_authority')]
    operations = [migrations.RunSQL(SQL, REVERSE)]
