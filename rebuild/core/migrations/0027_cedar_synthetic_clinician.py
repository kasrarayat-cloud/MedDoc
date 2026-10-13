"""Prospective standing-test enrollment; no historical or clinical row changes."""
import importlib
import re
from django.db import migrations

ACTOR = '5f4d1a3d-eeb6-4207-b1df-4597dc696e82'
DEPARTMENT = '46a5abdd-36f1-41f0-968f-8c09c39d9daa'
ENROLLMENT = 'quillmd-cedar-clinician-20261013-v1'
_previous = importlib.import_module('core.migrations.0025_personal_synthetic_testing_actor')
_pattern = r'CREATE (?:OR REPLACE )?FUNCTION (quillmd_[a-z_]+)\([^)]*\) RETURNS [^$]*?AS \$\$.*?\$\$;'
_all = {m.group(1): m.group(0) for m in re.finditer(_pattern, _previous.SQL, re.S)}
ORIGINALS = {name: _all[name] for name in (
    'quillmd_standing_config', 'quillmd_standing_actor', 'quillmd_standing_job_guard')}
REPLACEMENTS = dict(ORIGINALS)

def change(name, old, new):
    assert REPLACEMENTS[name].count(old) == 1, (name, old)
    REPLACEMENTS[name] = REPLACEMENTS[name].replace(old, new, 1)

change('quillmd_standing_config',
    "config->>'testing_actor_enrollment' IS DISTINCT FROM '" + _previous.ENROLLMENT + "'",
    "config->>'testing_actor_enrollment' NOT IN ('" + _previous.ENROLLMENT + "','" + ENROLLMENT + "')")
change('quillmd_standing_actor',
    " IF actor='" + _previous.ACTOR + "' AND department='" + DEPARTMENT + "' THEN",
    " IF actor IN ('" + _previous.ACTOR + "','" + ACTOR + "') AND department='" + DEPARTMENT + "' THEN")
change('quillmd_standing_actor',
    "config->>'testing_actor_enrollment' IS DISTINCT FROM '" + _previous.ENROLLMENT + "'",
    "config->>'testing_actor_enrollment' IS DISTINCT FROM (CASE WHEN actor='" + ACTOR + "' THEN '" + ENROLLMENT + "' ELSE '" + _previous.ENROLLMENT + "' END)")
change('quillmd_standing_job_guard',
    "IF NEW.user_id='" + _previous.ACTOR + "' AND NOT EXISTS",
    "IF NEW.user_id IN ('" + _previous.ACTOR + "','" + ACTOR + "') AND NOT EXISTS")
SQL = '\n'.join(_previous.replace_statement(s) for s in REPLACEMENTS.values())
REVERSE = "DO $$ BEGIN\n" + '\n'.join(
    (" IF" if i == 0 else " OR") + " EXISTS(SELECT 1 FROM " + table +
    " WHERE config->>'testing_actor_enrollment'='" + ENROLLMENT + "')"
    for i, table in enumerate(('core_job', 'core_templatepreparation', 'core_templatedefinitionpreparation'))
) + " THEN RAISE EXCEPTION 'Retained clinician requests forbid reversing enrollment'; END IF;\nEND; $$;\n" + '\n'.join(
    _previous.replace_statement(s) for s in ORIGINALS.values())

class Migration(migrations.Migration):
    dependencies = [('core', '0026_semantic_stage_receipts')]
    operations = [migrations.RunSQL(SQL, REVERSE)]
