"""Close the independently demonstrated initial approval INSERT invariant gap.

0019 and its failed isolated-QA observation remain unchanged. This migration
requires a genuinely empty queued preparation at creation, and independently
requires approval metadata before an immutable prepared version is inserted.
The application still authenticates the exact doctor's approval seal.
"""
from django.db import migrations

INITIAL = """
CREATE FUNCTION quillmd_preparation_initial_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF NEW.state IS DISTINCT FROM 'queued' OR NEW.revision IS DISTINCT FROM 0
    OR NEW.inventory IS DISTINCT FROM '{}'::jsonb OR NEW.proposal IS DISTINCT FROM '{}'::jsonb
    OR NEW.checker IS DISTINCT FROM '{}'::jsonb OR NEW.corrections IS DISTINCT FROM '{}'::jsonb
    OR NEW.correction_history IS DISTINCT FROM '[]'::jsonb OR NEW.candidate_history IS DISTINCT FROM '[]'::jsonb
    OR NEW.changes IS DISTINCT FROM '[]'::jsonb OR NEW.candidate_info IS DISTINCT FROM '{}'::jsonb
    OR NEW.candidate_path IS DISTINCT FROM '' OR NEW.candidate_sha256 IS DISTINCT FROM ''
    OR NEW.error_code IS DISTINCT FROM '' OR NEW.started_at IS NOT NULL OR NEW.finished_at IS NOT NULL
    OR NEW.approved_at IS NOT NULL OR NEW.approved_by_id IS NOT NULL OR NEW.approval_sha256 IS DISTINCT FROM ''
 THEN RAISE EXCEPTION 'A new preparation must begin as an empty queued request'; END IF;
 RETURN NEW;
END; $$;
CREATE TRIGGER preparation_initial_guard BEFORE INSERT ON core_templatepreparation
 FOR EACH ROW EXECUTE FUNCTION quillmd_preparation_initial_guard();
"""

VERSION = """
CREATE OR REPLACE FUNCTION quillmd_prepared_version_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE preparation core_templatepreparation%ROWTYPE;
BEGIN
 IF NEW.preparation_id IS NULL THEN
  IF NEW.prepared_path<>'' OR NEW.prepared_sha256<>'' THEN RAISE EXCEPTION 'Prepared version needs layout approval'; END IF;
 ELSE
  SELECT * INTO preparation FROM core_templatepreparation WHERE id=NEW.preparation_id;
  IF preparation.id IS NULL OR preparation.state<>'approved' OR preparation.template_id<>NEW.template_id
     OR preparation.approved_at IS NULL OR preparation.approved_by_id IS NULL
     OR preparation.approval_sha256 !~ '^[0-9a-f]{64}$'
     OR preparation.candidate_path='' OR preparation.candidate_sha256 !~ '^[0-9a-f]{64}$'
     OR preparation.candidate_path<>NEW.prepared_path OR preparation.candidate_sha256<>NEW.prepared_sha256
     THEN RAISE EXCEPTION 'Prepared version does not match its exact approved original and candidate'; END IF;
 END IF;
 RETURN NEW;
END; $$;
"""

# Restores exactly the prior 0019 function when an isolated unshipped schema is
# rolled back. No existing preparation, receipt or original row is rewritten.
PREVIOUS_VERSION = """
CREATE OR REPLACE FUNCTION quillmd_prepared_version_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE preparation core_templatepreparation%ROWTYPE;
BEGIN
 IF NEW.preparation_id IS NULL THEN
  IF NEW.prepared_path<>'' OR NEW.prepared_sha256<>'' THEN RAISE EXCEPTION 'Prepared version needs layout approval'; END IF;
 ELSE
  SELECT * INTO preparation FROM core_templatepreparation WHERE id=NEW.preparation_id;
  IF preparation.id IS NULL OR preparation.state<>'approved' OR preparation.template_id<>NEW.template_id
     OR preparation.candidate_path<>NEW.prepared_path OR preparation.candidate_sha256<>NEW.prepared_sha256
     THEN RAISE EXCEPTION 'Prepared version does not match its approved original and candidate'; END IF;
 END IF;
 RETURN NEW;
END; $$;
"""

class Migration(migrations.Migration):
    dependencies = [('core', '0019_template_preparation')]
    operations = [
        migrations.RunSQL(INITIAL, 'DROP TRIGGER preparation_initial_guard ON core_templatepreparation; DROP FUNCTION quillmd_preparation_initial_guard();'),
        migrations.RunSQL(VERSION, PREVIOUS_VERSION),
    ]
