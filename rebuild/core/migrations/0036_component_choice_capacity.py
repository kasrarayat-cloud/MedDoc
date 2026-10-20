"""Allow the explicit component-choice profile under unchanged definition bounds."""
from importlib import import_module
from django.db import migrations

PREVIOUS_SQL = import_module('core.migrations.0035_definition_capacity_profile').CAPACITY_SQL
OLD_CONDITION = "AND configuration->>'semantic_component_contract' IS NOT DISTINCT FROM 'field-components-v2'"
NEW_CONDITION = """AND (configuration->>'semantic_component_contract' IS NOT DISTINCT FROM 'field-components-v2'
      OR configuration->>'semantic_component_contract' IS NOT DISTINCT FROM 'field-components-v3')"""
if PREVIOUS_SQL.count(OLD_CONDITION) != 1:
    raise RuntimeError('The historical component capacity condition must match exactly once.')
CAPACITY_SQL = PREVIOUS_SQL.replace(OLD_CONDITION, NEW_CONDITION)


class Migration(migrations.Migration):
    dependencies = [('core', '0035_definition_capacity_profile')]
    operations = [migrations.RunSQL(CAPACITY_SQL, PREVIOUS_SQL)]
