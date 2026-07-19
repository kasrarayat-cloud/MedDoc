BEGIN;

SET LOCAL lock_timeout = '2s';
SET LOCAL statement_timeout = '30s';

-- A fill manifest is the immutable lineage boundary between one physician
-- encounter and the exact compiled template version used for that encounter.
-- Mutable review, render, and signing state may advance on the row, but its
-- tenant/visit/template identity must never be reassigned. Besides preserving
-- evidence lineage, this closes an indirect rollback-fence entry path where an
-- archived unsigned fill could be moved away from a nonterminal Twin visit
-- after PREPARE and thereby expose a newly pinned visit.
CREATE OR REPLACE FUNCTION template_twin_guard_fill_identity_immutable_v4()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF OLD."practiceId" IS DISTINCT FROM NEW."practiceId"
    OR OLD."visitId" IS DISTINCT FROM NEW."visitId"
    OR OLD."compiledVersionId" IS DISTINCT FROM NEW."compiledVersionId"
    OR OLD."noteTemplateId" IS DISTINCT FROM NEW."noteTemplateId"
    OR OLD."noteTemplateVersion" IS DISTINCT FROM NEW."noteTemplateVersion"
  THEN
    RAISE EXCEPTION 'Template Twin fill identity is immutable';
  END IF;

  RETURN NEW;
END;
$$;

CREATE TRIGGER aaa_template_twin_fill_identity_immutability_v4
BEFORE UPDATE OF
  "practiceId", "visitId", "compiledVersionId",
  "noteTemplateId", "noteTemplateVersion"
ON "template_twin_fill_manifests"
FOR EACH ROW EXECUTE FUNCTION template_twin_guard_fill_identity_immutable_v4();

COMMIT;
