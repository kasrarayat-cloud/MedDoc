-- Completed-candidate redacted structural review proof v1.
-- Additive over the accepted completed-candidate tables. Existing converter
-- 1.0 rows remain readable as historical synthetic evidence but fail closed:
-- only converter 1.1 rows with a persisted canonical projection may receive a
-- preview receipt or a terminal physician decision.

BEGIN;
SET LOCAL lock_timeout = '2s';
SET LOCAL statement_timeout = '30s';

ALTER TYPE "AuditAction" ADD VALUE IF NOT EXISTS 'TEMPLATE_TWIN_COMPLETED_CANDIDATE_REVIEW_PREVIEWED';

ALTER TABLE "template_twin_completed_candidates"
  ADD COLUMN "reviewProjection" JSONB,
  ADD COLUMN "reviewProjectionSha256" CHAR(64),
  ADD COLUMN "reviewReceiptId" TEXT;

ALTER TABLE "template_twin_completed_candidates"
  DROP CONSTRAINT "template_twin_completed_candidate_identity",
  DROP CONSTRAINT "template_twin_completed_candidate_review_state",
  ADD CONSTRAINT "template_twin_completed_candidate_identity" CHECK (
    char_length(btrim("name")) BETWEEN 3 AND 120
    AND char_length(btrim("encounterScope")) BETWEEN 3 AND 120
    AND char_length(btrim("versionDescription")) BETWEEN 3 AND 500
    AND char_length(btrim("candidateObjectVersionId")) > 0
    AND char_length(btrim("candidateObjectEtag")) > 0
    AND "candidateSizeBytes" > 0
    AND "candidateSha256" ~ '^[a-f0-9]{64}$'
    AND "candidateStructureSha256" ~ '^[a-f0-9]{64}$'
    AND "inventorySha256" ~ '^[a-f0-9]{64}$'
    AND "privacyEvidence"->>'providerEgress' = 'false'
    AND "privacyEvidence"->>'sentinelVerified' = 'true'
  ),
  ADD CONSTRAINT "template_twin_completed_candidate_projection_v1_1" CHECK (
    "createdById" IS NOT NULL
    AND "converterVersion" = 'completed-document-candidate/1.1.0'
    AND "reviewProjection" IS NOT NULL
    AND jsonb_typeof("reviewProjection") = 'object'
    AND "reviewProjectionSha256" ~ '^[a-f0-9]{64}$'
    AND "reviewProjection"->>'profileVersion' = 'completed-candidate-redacted-structural-review/1.0.0'
    AND "reviewProjection"->>'valuesRedacted' = 'true'
    AND "reviewProjection"->>'sourceBytesReturned' = 'false'
    AND "reviewProjection"->>'providerEgress' = 'false'
    AND "reviewProjection"->>'paginationRepresented' = 'false'
    AND "reviewProjection"->>'candidateSha256' = "candidateSha256"
    AND "reviewProjection"->>'candidateStructureSha256' = "candidateStructureSha256"
    AND "reviewProjection"->>'inventorySha256' = "inventorySha256"
    AND "reviewProjection"->>'sourceStructureSha256' ~ '^[a-f0-9]{64}$'
    AND "reviewProjection"->>'candidateStructureSha256' ~ '^[a-f0-9]{64}$'
    AND CASE
      WHEN jsonb_typeof("reviewProjection"->'sourceExampleSha256s') = 'array'
        THEN jsonb_array_length("reviewProjection"->'sourceExampleSha256s') BETWEEN 2 AND 3
      ELSE false
    END
    AND CASE
      WHEN jsonb_typeof("reviewProjection"->'blocks') = 'array'
        THEN jsonb_array_length("reviewProjection"->'blocks') BETWEEN 1 AND 600
      ELSE false
    END
    AND ("reviewProjection"->>'regionCount')::INTEGER BETWEEN 1 AND 2000
  ) NOT VALID,
  ADD CONSTRAINT "template_twin_completed_candidate_review_state" CHECK (
    ("status" = 'PENDING_REVIEW'
      AND "reviewedAt" IS NULL AND "reviewReceiptId" IS NULL)
    OR ("status" IN ('APPROVED', 'REJECTED')
      AND "reviewedAt" IS NOT NULL AND "reviewReceiptId" IS NOT NULL)
  ) NOT VALID;

CREATE TABLE "template_twin_completed_candidate_review_receipts" (
  "id" TEXT NOT NULL,
  "candidateId" TEXT NOT NULL,
  "practiceId" TEXT NOT NULL,
  "reviewedById" TEXT NOT NULL,
  "tokenSha256" CHAR(64) NOT NULL,
  "candidateSha256" CHAR(64) NOT NULL,
  "candidateStructureSha256" CHAR(64) NOT NULL,
  "inventorySha256" CHAR(64) NOT NULL,
  "reviewProjectionSha256" CHAR(64) NOT NULL,
  "converterVersion" TEXT NOT NULL,
  "globalRolloutGeneration" BIGINT NOT NULL,
  "practiceRolloutGeneration" BIGINT NOT NULL,
  "createdAt" TIMESTAMPTZ(6) NOT NULL,
  "expiresAt" TIMESTAMPTZ(6) NOT NULL,
  "consumedAt" TIMESTAMPTZ(6),
  CONSTRAINT "template_twin_completed_candidate_review_receipts_pkey" PRIMARY KEY ("id"),
  CONSTRAINT "tt_completed_candidate_receipt_identity" CHECK (
    "id" ~ '^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'
    AND "tokenSha256" ~ '^[a-f0-9]{64}$'
    AND "candidateSha256" ~ '^[a-f0-9]{64}$'
    AND "candidateStructureSha256" ~ '^[a-f0-9]{64}$'
    AND "inventorySha256" ~ '^[a-f0-9]{64}$'
    AND "reviewProjectionSha256" ~ '^[a-f0-9]{64}$'
    AND "converterVersion" = 'completed-document-candidate/1.1.0'
  ),
  CONSTRAINT "tt_completed_candidate_receipt_generations" CHECK (
    "globalRolloutGeneration" >= 1 AND "practiceRolloutGeneration" >= 1
  ),
  CONSTRAINT "tt_completed_candidate_receipt_window" CHECK (
    "expiresAt" = "createdAt" + INTERVAL '15 minutes'
    AND ("consumedAt" IS NULL
      OR ("consumedAt" >= "createdAt" AND "consumedAt" <= "expiresAt"))
  ),
  CONSTRAINT "tt_completed_candidate_receipt_candidate_fkey"
    FOREIGN KEY ("candidateId") REFERENCES "template_twin_completed_candidates"("id")
    ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT "tt_completed_candidate_receipt_practice_fkey"
    FOREIGN KEY ("practiceId") REFERENCES "practices"("id")
    ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT "tt_completed_candidate_receipt_reviewer_fkey"
    FOREIGN KEY ("reviewedById") REFERENCES "users"("id")
    ON DELETE RESTRICT ON UPDATE CASCADE
);

CREATE UNIQUE INDEX "tt_completed_candidate_receipt_token_key"
  ON "template_twin_completed_candidate_review_receipts"("tokenSha256");
CREATE INDEX "tt_completed_candidate_receipt_candidate_reviewer_expiry_idx"
  ON "template_twin_completed_candidate_review_receipts"("candidateId", "reviewedById", "expiresAt");
CREATE INDEX "tt_completed_candidate_receipt_expiry_idx"
  ON "template_twin_completed_candidate_review_receipts"("expiresAt")
  WHERE "consumedAt" IS NULL;
CREATE UNIQUE INDEX "template_twin_completed_candidates_reviewReceiptId_key"
  ON "template_twin_completed_candidates"("reviewReceiptId");

ALTER TABLE "template_twin_completed_candidates"
  ADD CONSTRAINT "tt_completed_candidate_review_receipt_fkey"
    FOREIGN KEY ("reviewReceiptId")
    REFERENCES "template_twin_completed_candidate_review_receipts"("id")
    ON DELETE RESTRICT ON UPDATE CASCADE;

CREATE OR REPLACE FUNCTION template_twin_completed_candidate_immutable() RETURNS trigger AS $$
BEGIN
  IF TG_OP = 'DELETE' THEN
    RAISE EXCEPTION 'Template Twin completed candidates are append-only';
  END IF;
  IF OLD."practiceId" IS DISTINCT FROM NEW."practiceId"
     OR OLD."createdById" IS DISTINCT FROM NEW."createdById"
     OR OLD."name" IS DISTINCT FROM NEW."name"
     OR OLD."encounterScope" IS DISTINCT FROM NEW."encounterScope"
     OR OLD."versionDescription" IS DISTINCT FROM NEW."versionDescription"
     OR OLD."candidateObjectKey" IS DISTINCT FROM NEW."candidateObjectKey"
     OR OLD."candidateObjectVersionId" IS DISTINCT FROM NEW."candidateObjectVersionId"
     OR OLD."candidateObjectEtag" IS DISTINCT FROM NEW."candidateObjectEtag"
     OR OLD."candidateSha256" IS DISTINCT FROM NEW."candidateSha256"
     OR OLD."candidateSizeBytes" IS DISTINCT FROM NEW."candidateSizeBytes"
     OR OLD."candidateStructureSha256" IS DISTINCT FROM NEW."candidateStructureSha256"
     OR OLD."inventorySha256" IS DISTINCT FROM NEW."inventorySha256"
     OR OLD."converterVersion" IS DISTINCT FROM NEW."converterVersion"
     OR OLD."comparisonEvidence" IS DISTINCT FROM NEW."comparisonEvidence"
     OR OLD."privacyEvidence" IS DISTINCT FROM NEW."privacyEvidence"
     OR OLD."reviewProjection" IS DISTINCT FROM NEW."reviewProjection"
     OR OLD."reviewProjectionSha256" IS DISTINCT FROM NEW."reviewProjectionSha256"
     OR OLD."createdAt" IS DISTINCT FROM NEW."createdAt" THEN
    RAISE EXCEPTION 'Template Twin completed candidate identity is immutable';
  END IF;
  IF OLD."status" IN ('APPROVED', 'REJECTED') AND OLD IS DISTINCT FROM NEW THEN
    RAISE EXCEPTION 'Template Twin completed candidate review is terminal';
  END IF;
  IF NOT (
    (OLD."status" = NEW."status"
      AND OLD."reviewedAt" IS NOT DISTINCT FROM NEW."reviewedAt"
      AND OLD."reviewReceiptId" IS NOT DISTINCT FROM NEW."reviewReceiptId")
    OR (OLD."status" = 'PENDING_REVIEW'
      AND NEW."status" IN ('APPROVED', 'REJECTED')
      AND OLD."reviewedAt" IS NULL AND NEW."reviewedAt" IS NOT NULL
      AND OLD."reviewReceiptId" IS NULL AND NEW."reviewReceiptId" IS NOT NULL)
  ) THEN
    RAISE EXCEPTION 'Template Twin completed candidate transition is invalid';
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION template_twin_completed_candidate_receipt_immutable() RETURNS trigger AS $$
BEGIN
  IF TG_OP = 'DELETE' THEN
    RAISE EXCEPTION 'Template Twin completed candidate review receipts are append-only';
  END IF;
  IF TG_OP = 'INSERT' THEN
    IF NEW."consumedAt" IS NOT NULL THEN
      RAISE EXCEPTION 'Template Twin completed candidate review receipt must start unused';
    END IF;
    RETURN NEW;
  END IF;
  IF OLD."id" IS DISTINCT FROM NEW."id"
     OR OLD."candidateId" IS DISTINCT FROM NEW."candidateId"
     OR OLD."practiceId" IS DISTINCT FROM NEW."practiceId"
     OR OLD."reviewedById" IS DISTINCT FROM NEW."reviewedById"
     OR OLD."tokenSha256" IS DISTINCT FROM NEW."tokenSha256"
     OR OLD."candidateSha256" IS DISTINCT FROM NEW."candidateSha256"
     OR OLD."candidateStructureSha256" IS DISTINCT FROM NEW."candidateStructureSha256"
     OR OLD."inventorySha256" IS DISTINCT FROM NEW."inventorySha256"
     OR OLD."reviewProjectionSha256" IS DISTINCT FROM NEW."reviewProjectionSha256"
     OR OLD."converterVersion" IS DISTINCT FROM NEW."converterVersion"
     OR OLD."globalRolloutGeneration" IS DISTINCT FROM NEW."globalRolloutGeneration"
     OR OLD."practiceRolloutGeneration" IS DISTINCT FROM NEW."practiceRolloutGeneration"
     OR OLD."createdAt" IS DISTINCT FROM NEW."createdAt"
     OR OLD."expiresAt" IS DISTINCT FROM NEW."expiresAt"
     OR OLD."consumedAt" IS NOT NULL
     OR NEW."consumedAt" IS NULL
     OR OLD."expiresAt" <= clock_timestamp()
     OR NEW."consumedAt" > clock_timestamp() THEN
    RAISE EXCEPTION 'Template Twin completed candidate review receipt is immutable';
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER tt_completed_candidate_receipt_immutable_guard
  BEFORE INSERT OR UPDATE OR DELETE
  ON "template_twin_completed_candidate_review_receipts"
  FOR EACH ROW EXECUTE FUNCTION template_twin_completed_candidate_receipt_immutable();

CREATE OR REPLACE FUNCTION template_twin_assert_completed_candidate_projection() RETURNS trigger AS $$
DECLARE example_hashes JSONB;
DECLARE example_structure TEXT;
DECLARE example_count INTEGER;
DECLARE example_hash_count INTEGER;
DECLARE example_structure_count INTEGER;
DECLARE minimum_ordinal INTEGER;
DECLARE maximum_ordinal INTEGER;
DECLARE relational_region_count INTEGER;
DECLARE block_count INTEGER;
DECLARE block_key_count INTEGER;
DECLARE block_order_count INTEGER;
DECLARE table_count INTEGER;
DECLARE table_index_count INTEGER;
BEGIN
  IF NEW."converterVersion" <> 'completed-document-candidate/1.1.0'
     OR NEW."reviewProjection" IS NULL
     OR NEW."reviewProjectionSha256" !~ '^[a-f0-9]{64}$' THEN
    RAISE EXCEPTION 'Template Twin completed candidate projection version mismatch';
  END IF;

  SELECT jsonb_agg(to_jsonb(e."minimizedSha256") ORDER BY e."ordinal"),
         min(e."documentStructureSha256"),
         count(*), count(DISTINCT e."minimizedSha256"),
         count(DISTINCT e."documentStructureSha256"),
         min(e."ordinal"), max(e."ordinal")
    INTO example_hashes, example_structure, example_count, example_hash_count,
         example_structure_count, minimum_ordinal, maximum_ordinal
    FROM "template_twin_completed_candidate_examples" e
    WHERE e."candidateId" = NEW."id";
  IF example_hashes IS NULL
     OR example_count NOT BETWEEN 2 AND 3
     OR example_hash_count <> example_count
     OR example_structure_count <> 1
     OR minimum_ordinal <> 1 OR maximum_ordinal <> example_count
     OR NEW."reviewProjection"->'sourceExampleSha256s' IS DISTINCT FROM example_hashes
     OR NEW."reviewProjection"->>'sourceStructureSha256' IS DISTINCT FROM example_structure
     OR NEW."reviewProjection"->>'candidateSha256' IS DISTINCT FROM NEW."candidateSha256"
     OR NEW."reviewProjection"->>'candidateStructureSha256' IS DISTINCT FROM NEW."candidateStructureSha256"
     OR NEW."reviewProjection"->>'inventorySha256' IS DISTINCT FROM NEW."inventorySha256" THEN
    RAISE EXCEPTION 'Template Twin completed candidate projection source binding mismatch';
  END IF;

  SELECT count(*), count(DISTINCT block->>'blockKey'),
         count(DISTINCT (block->>'displayOrder')::INTEGER)
    INTO block_count, block_key_count, block_order_count
    FROM jsonb_array_elements(NEW."reviewProjection"->'blocks') AS b(block);
  IF block_count < 1 OR block_count <> block_key_count OR block_count <> block_order_count
     OR EXISTS (
       SELECT 1
       FROM jsonb_array_elements(NEW."reviewProjection"->'blocks')
         WITH ORDINALITY AS b(block, ordinal)
       WHERE (b.block->>'displayOrder')::INTEGER <> b.ordinal - 1
     ) THEN
    RAISE EXCEPTION 'Template Twin completed candidate projection block identity mismatch';
  END IF;

  SELECT count(*), count(DISTINCT (block->>'tableIndex')::INTEGER)
    INTO table_count, table_index_count
    FROM jsonb_array_elements(NEW."reviewProjection"->'blocks') AS b(block)
    WHERE block->>'kind' = 'table';
  IF table_count < 1 OR table_count <> table_index_count
     OR EXISTS (
       WITH tables AS (
         SELECT block, ordinal,
                row_number() OVER (ORDER BY ordinal) - 1 AS expected_index
         FROM jsonb_array_elements(NEW."reviewProjection"->'blocks')
           WITH ORDINALITY AS b(block, ordinal)
         WHERE block->>'kind' = 'table'
       )
       SELECT 1 FROM tables
       WHERE (block->>'tableIndex')::INTEGER <> expected_index
     ) THEN
    RAISE EXCEPTION 'Template Twin completed candidate projection table identity mismatch';
  END IF;

  IF EXISTS (
    WITH tables AS (
      SELECT block
      FROM jsonb_array_elements(NEW."reviewProjection"->'blocks') AS b(block)
      WHERE block->>'kind' = 'table'
    )
    SELECT 1 FROM tables
    WHERE jsonb_typeof(block->'gridColumnBasisPoints') IS DISTINCT FROM 'array'
       OR jsonb_array_length(block->'gridColumnBasisPoints') NOT BETWEEN 1 AND 64
       OR jsonb_typeof(block->'rows') IS DISTINCT FROM 'array'
       OR jsonb_array_length(block->'rows') NOT BETWEEN 1 AND 500
       OR EXISTS (
         SELECT 1
         FROM jsonb_array_elements(block->'gridColumnBasisPoints') AS g(width)
         WHERE jsonb_typeof(width) IS DISTINCT FROM 'number'
            OR (width #>> '{}')::INTEGER NOT BETWEEN 1 AND 10000
       )
       OR (
         SELECT sum((width #>> '{}')::INTEGER)
         FROM jsonb_array_elements(block->'gridColumnBasisPoints') AS g(width)
       ) <> 10000
  ) THEN
    RAISE EXCEPTION 'Template Twin completed candidate projection table grid mismatch';
  END IF;

  IF EXISTS (
    WITH blocks AS (
      SELECT block
      FROM jsonb_array_elements(NEW."reviewProjection"->'blocks') AS b(block)
      WHERE block->>'kind' = 'table'
    ), cells AS (
      SELECT cell_value, cell_value->'role' AS role
      FROM blocks
      CROSS JOIN LATERAL jsonb_array_elements(block->'rows') AS r(row_value)
      CROSS JOIN LATERAL jsonb_array_elements(row_value->'cells') AS c(cell_value)
    )
    SELECT 1 FROM cells
    WHERE CASE
      WHEN jsonb_typeof(role) IS DISTINCT FROM 'object' THEN true
      WHEN role->>'kind' = 'static_redacted' THEN
        role IS DISTINCT FROM '{"kind":"static_redacted"}'::JSONB
      WHEN role->>'kind' = 'stable_label' THEN
        (SELECT count(*) FROM jsonb_object_keys(role)) <> 3
        OR role->>'label' IS NULL
        OR char_length(role->>'label') NOT BETWEEN 1 AND 120
        OR role->>'forRegionId' !~ '^tccr_[a-f0-9]{24}$'
      WHEN role->>'kind' = 'candidate_region' THEN
        (SELECT count(*) FROM jsonb_object_keys(role)) <> 6
        OR role->>'regionId' !~ '^tccr_[a-f0-9]{24}$'
        OR role->>'candidateTag' !~ '^qmd:candidate:[a-f0-9]{24}$'
        OR role->>'controlKind' IS DISTINCT FROM 'plain_text'
        OR role->>'sourceState' IS DISTINCT FROM 'VALUE_WITHHELD'
        OR role->>'candidateState' IS DISTINCT FROM 'BLANK_CONTROL'
      ELSE true
    END
  ) THEN
    RAISE EXCEPTION 'Template Twin completed candidate projection role mismatch';
  END IF;

  IF EXISTS (
    WITH tables AS (
      SELECT block AS table_block
      FROM jsonb_array_elements(NEW."reviewProjection"->'blocks') AS b(block)
      WHERE block->>'kind' = 'table'
    ), rows AS (
      SELECT table_block,
             (table_block->>'tableIndex')::INTEGER AS table_index,
             row_value, row_ordinal
      FROM tables
      CROSS JOIN LATERAL jsonb_array_elements(table_block->'rows')
        WITH ORDINALITY AS r(row_value, row_ordinal)
    ), cells AS (
      SELECT table_block, table_index,
             (row_value->>'rowIndex')::INTEGER AS row_index,
             row_ordinal, cell_value, cell_ordinal,
             (cell_value->>'cellIndex')::INTEGER AS cell_index,
             (cell_value->>'columnStart')::INTEGER AS column_start,
             (cell_value->>'columnSpan')::INTEGER AS column_span,
             sum((cell_value->>'columnSpan')::INTEGER) OVER (
               PARTITION BY table_index, row_ordinal
               ORDER BY cell_ordinal ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
             ) AS preceding_span
      FROM rows
      CROSS JOIN LATERAL jsonb_array_elements(row_value->'cells')
        WITH ORDINALITY AS c(cell_value, cell_ordinal)
    )
    SELECT 1 FROM cells
    WHERE row_index <> row_ordinal - 1
       OR cell_index <> cell_ordinal - 1
       OR cell_value->>'cellKey' <>
          format('table:%s:row:%s:cell:%s', table_index, row_index, cell_index)
       OR column_start <> COALESCE(preceding_span, 0)
       OR column_span < 1
       OR (cell_value->>'rowSpan')::INTEGER <> 1
    UNION ALL
    SELECT 1
    FROM cells
    GROUP BY table_index, row_index, table_block
    HAVING sum(column_span) <> jsonb_array_length(table_block->'gridColumnBasisPoints')
    UNION ALL
    SELECT 1
    FROM cells
    GROUP BY cell_value->>'cellKey'
    HAVING count(*) <> 1
  ) THEN
    RAISE EXCEPTION 'Template Twin completed candidate projection cell topology mismatch';
  END IF;

  SELECT count(*) INTO relational_region_count
    FROM "template_twin_completed_candidate_regions" r
    WHERE r."candidateId" = NEW."id";
  IF relational_region_count < 1
     OR (NEW."reviewProjection"->>'regionCount')::INTEGER <> relational_region_count
     OR EXISTS (
       WITH blocks AS (
         SELECT block, block_ordinal
         FROM jsonb_array_elements(NEW."reviewProjection"->'blocks')
           WITH ORDINALITY AS b(block, block_ordinal)
         WHERE block->>'kind' = 'table'
       ), cells AS (
         SELECT (block->>'tableIndex')::INTEGER AS table_index,
                (row_value->>'rowIndex')::INTEGER AS row_index,
                (cell_value->>'cellIndex')::INTEGER AS cell_index,
                cell_value->'role' AS role,
                block_ordinal, row_ordinal, cell_ordinal
         FROM blocks
         CROSS JOIN LATERAL jsonb_array_elements(block->'rows')
           WITH ORDINALITY AS r(row_value, row_ordinal)
         CROSS JOIN LATERAL jsonb_array_elements(row_value->'cells')
           WITH ORDINALITY AS c(cell_value, cell_ordinal)
       ), candidate_roles AS (
         SELECT role->>'regionId' AS region_id,
                role->>'candidateTag' AS candidate_tag,
                table_index, row_index, cell_index,
                row_number() OVER (
                  ORDER BY block_ordinal, row_ordinal, cell_ordinal
                ) - 1 AS display_order
         FROM cells WHERE role->>'kind' = 'candidate_region'
       ), label_roles AS (
         SELECT role->>'forRegionId' AS region_id,
                role->>'label' AS label,
                table_index, row_index, cell_index
         FROM cells WHERE role->>'kind' = 'stable_label'
       ), relational AS (
         SELECT r."regionId" AS region_id, r."candidateTag" AS candidate_tag,
                r."label" AS label, r."tableIndex" AS table_index,
                r."rowIndex" AS row_index, r."cellIndex" AS cell_index,
                r."displayOrder" AS display_order
         FROM "template_twin_completed_candidate_regions" r
         WHERE r."candidateId" = NEW."id"
       )
       SELECT 1
       FROM relational r
       LEFT JOIN candidate_roles c ON c.region_id = r.region_id
       LEFT JOIN label_roles l ON l.region_id = r.region_id
       WHERE c.region_id IS NULL OR l.region_id IS NULL
          OR c.candidate_tag IS DISTINCT FROM r.candidate_tag
          OR c.table_index IS DISTINCT FROM r.table_index
          OR c.row_index IS DISTINCT FROM r.row_index
          OR c.cell_index IS DISTINCT FROM r.cell_index
          OR c.display_order IS DISTINCT FROM r.display_order
          OR l.label IS DISTINCT FROM r.label
          OR l.table_index IS DISTINCT FROM r.table_index
          OR l.row_index IS DISTINCT FROM r.row_index
          OR l.cell_index IS DISTINCT FROM r.cell_index - 1
       UNION ALL
       SELECT 1 FROM candidate_roles c
       LEFT JOIN relational r ON r.region_id = c.region_id
       WHERE r.region_id IS NULL
       UNION ALL
       SELECT 1 FROM label_roles l
       LEFT JOIN relational r ON r.region_id = l.region_id
       WHERE r.region_id IS NULL
       UNION ALL
       SELECT 1 FROM candidate_roles GROUP BY region_id HAVING count(*) <> 1
       UNION ALL
       SELECT 1 FROM candidate_roles GROUP BY candidate_tag HAVING count(*) <> 1
       UNION ALL
       SELECT 1 FROM label_roles GROUP BY region_id HAVING count(*) <> 1
     ) THEN
    RAISE EXCEPTION 'Template Twin completed candidate projection inventory mismatch';
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE CONSTRAINT TRIGGER tt_completed_candidate_projection_consistency
  AFTER INSERT OR UPDATE ON "template_twin_completed_candidates"
  DEFERRABLE INITIALLY DEFERRED
  FOR EACH ROW EXECUTE FUNCTION template_twin_assert_completed_candidate_projection();

CREATE OR REPLACE FUNCTION template_twin_assert_completed_candidate_review() RETURNS trigger AS $$
DECLARE total_count INTEGER;
DECLARE pending_count INTEGER;
DECLARE rejected_count INTEGER;
DECLARE wrong_actor_count INTEGER;
DECLARE wrong_time_count INTEGER;
DECLARE example_count INTEGER;
DECLARE example_structure_count INTEGER;
DECLARE minimum_ordinal INTEGER;
DECLARE maximum_ordinal INTEGER;
DECLARE receipt RECORD;
BEGIN
  SELECT count(*), count(DISTINCT e."documentStructureSha256"),
         min(e."ordinal"), max(e."ordinal")
    INTO example_count, example_structure_count, minimum_ordinal, maximum_ordinal
    FROM "template_twin_completed_candidate_examples" e
    WHERE e."candidateId" = NEW."id";
  IF example_count NOT BETWEEN 2 AND 3
     OR example_structure_count <> 1
     OR minimum_ordinal <> 1 OR maximum_ordinal <> example_count
     OR (NEW."comparisonEvidence"->>'exampleCount')::INTEGER <> example_count
     OR (NEW."privacyEvidence"->>'exampleCount')::INTEGER <> example_count THEN
    RAISE EXCEPTION 'Template Twin completed candidate example census mismatch';
  END IF;
  SELECT count(*), count(*) FILTER (WHERE r."decision" = 'PENDING'),
         count(*) FILTER (WHERE r."decision" = 'REJECTED'),
         count(*) FILTER (
           WHERE r."decision" <> 'PENDING'
             AND r."decidedById" IS DISTINCT FROM NEW."createdById"
         ),
         count(*) FILTER (
           WHERE r."decision" <> 'PENDING'
             AND r."decidedAt" IS DISTINCT FROM NEW."reviewedAt"
         )
    INTO total_count, pending_count, rejected_count,
         wrong_actor_count, wrong_time_count
    FROM "template_twin_completed_candidate_regions" r
    WHERE r."candidateId" = NEW."id";
  IF total_count < 1
     OR (NEW."comparisonEvidence"->>'candidateFieldCount')::INTEGER <> total_count
     OR (NEW."reviewProjection"->>'regionCount')::INTEGER <> total_count THEN
    RAISE EXCEPTION 'Template Twin completed candidate has no field inventory';
  END IF;
  IF (NEW."status" = 'PENDING_REVIEW'
        AND (pending_count <> total_count OR NEW."reviewReceiptId" IS NOT NULL))
     OR (NEW."status" = 'APPROVED'
        AND (pending_count <> 0 OR rejected_count <> 0))
     OR (NEW."status" = 'REJECTED'
        AND (pending_count <> 0 OR rejected_count < 1))
     OR (NEW."status" <> 'PENDING_REVIEW'
        AND (wrong_actor_count <> 0 OR wrong_time_count <> 0)) THEN
    RAISE EXCEPTION 'Template Twin completed candidate review inventory mismatch';
  END IF;
  IF NEW."status" <> 'PENDING_REVIEW' THEN
    SELECT r.* INTO receipt
    FROM "template_twin_completed_candidate_review_receipts" r
    WHERE r."id" = NEW."reviewReceiptId";
    IF NOT FOUND
       OR receipt."candidateId" IS DISTINCT FROM NEW."id"
       OR receipt."practiceId" IS DISTINCT FROM NEW."practiceId"
       OR receipt."reviewedById" IS DISTINCT FROM NEW."createdById"
       OR receipt."candidateSha256" IS DISTINCT FROM NEW."candidateSha256"
       OR receipt."candidateStructureSha256" IS DISTINCT FROM NEW."candidateStructureSha256"
       OR receipt."inventorySha256" IS DISTINCT FROM NEW."inventorySha256"
       OR receipt."reviewProjectionSha256" IS DISTINCT FROM NEW."reviewProjectionSha256"
       OR receipt."converterVersion" IS DISTINCT FROM NEW."converterVersion"
       OR receipt."consumedAt" IS NULL
       OR receipt."consumedAt" IS DISTINCT FROM NEW."reviewedAt"
       OR receipt."consumedAt" > receipt."expiresAt" THEN
      RAISE EXCEPTION 'Template Twin completed candidate review receipt mismatch';
    END IF;
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION template_twin_assert_completed_candidate_review_from_region() RETURNS trigger AS $$
DECLARE candidate_status TEXT;
DECLARE candidate_reviewed_at TIMESTAMPTZ(6);
DECLARE candidate_receipt_id TEXT;
DECLARE pending_count INTEGER;
DECLARE rejected_count INTEGER;
BEGIN
  SELECT c."status", c."reviewedAt", c."reviewReceiptId"
    INTO candidate_status, candidate_reviewed_at, candidate_receipt_id
    FROM "template_twin_completed_candidates" c
    WHERE c."id" = NEW."candidateId";
  SELECT count(*) FILTER (WHERE r."decision" = 'PENDING'),
         count(*) FILTER (WHERE r."decision" = 'REJECTED')
    INTO pending_count, rejected_count
    FROM "template_twin_completed_candidate_regions" r
    WHERE r."candidateId" = NEW."candidateId";
  IF (candidate_status = 'PENDING_REVIEW' AND pending_count <> (
        SELECT count(*) FROM "template_twin_completed_candidate_regions" r
        WHERE r."candidateId" = NEW."candidateId"
      ))
     OR (candidate_status = 'APPROVED'
        AND (pending_count <> 0 OR rejected_count <> 0
          OR candidate_reviewed_at IS NULL OR candidate_receipt_id IS NULL))
     OR (candidate_status = 'REJECTED'
        AND (pending_count <> 0 OR rejected_count < 1
          OR candidate_reviewed_at IS NULL OR candidate_receipt_id IS NULL)) THEN
    RAISE EXCEPTION 'Template Twin completed candidate review inventory mismatch';
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE CONSTRAINT TRIGGER tt_completed_candidate_region_parent_consistency
  AFTER INSERT OR UPDATE ON "template_twin_completed_candidate_regions"
  DEFERRABLE INITIALLY DEFERRED
  FOR EACH ROW EXECUTE FUNCTION template_twin_assert_completed_candidate_review_from_region();

CREATE OR REPLACE FUNCTION template_twin_assert_completed_candidate_receipt() RETURNS trigger AS $$
DECLARE candidate RECORD;
DECLARE reviewer_practice TEXT;
DECLARE reviewer_role TEXT;
DECLARE reviewer_active BOOLEAN;
DECLARE global_enabled BOOLEAN;
DECLARE global_generation BIGINT;
DECLARE practice_enabled BOOLEAN;
DECLARE practice_generation BIGINT;
BEGIN
  SELECT c.* INTO candidate
    FROM "template_twin_completed_candidates" c
    WHERE c."id" = NEW."candidateId";
  SELECT u."practiceId", u."role"::TEXT, u."isActive"
    INTO reviewer_practice, reviewer_role, reviewer_active
    FROM "users" u WHERE u."id" = NEW."reviewedById";
  SELECT r."enabled", r."generation" INTO global_enabled, global_generation
    FROM "template_twin_rollout_controls" r WHERE r."id" = 'global';
  SELECT p."templateTwinEnabled", p."templateTwinRolloutGeneration"
    INTO practice_enabled, practice_generation
    FROM "practices" p WHERE p."id" = NEW."practiceId";
  IF candidate."id" IS NULL
     OR candidate."practiceId" IS DISTINCT FROM NEW."practiceId"
     OR candidate."createdById" IS DISTINCT FROM NEW."reviewedById"
     OR candidate."converterVersion" IS DISTINCT FROM NEW."converterVersion"
     OR candidate."candidateSha256" IS DISTINCT FROM NEW."candidateSha256"
     OR candidate."candidateStructureSha256" IS DISTINCT FROM NEW."candidateStructureSha256"
     OR candidate."inventorySha256" IS DISTINCT FROM NEW."inventorySha256"
     OR candidate."reviewProjectionSha256" IS DISTINCT FROM NEW."reviewProjectionSha256"
     OR reviewer_practice IS DISTINCT FROM NEW."practiceId"
     OR reviewer_role IS DISTINCT FROM 'DOCTOR'
     OR reviewer_active IS DISTINCT FROM true
     OR global_enabled IS DISTINCT FROM true
     OR practice_enabled IS DISTINCT FROM true
     OR global_generation IS DISTINCT FROM NEW."globalRolloutGeneration"
     OR practice_generation IS DISTINCT FROM NEW."practiceRolloutGeneration"
     OR (NEW."consumedAt" IS NULL AND (
       candidate."status" <> 'PENDING_REVIEW'
       OR candidate."reviewReceiptId" IS NOT NULL
     ))
     OR (NEW."consumedAt" IS NOT NULL AND (
       candidate."status" NOT IN ('APPROVED', 'REJECTED')
       OR candidate."reviewReceiptId" IS DISTINCT FROM NEW."id"
       OR candidate."reviewedAt" IS DISTINCT FROM NEW."consumedAt"
     )) THEN
    RAISE EXCEPTION 'Template Twin completed candidate review receipt invalid';
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE CONSTRAINT TRIGGER tt_completed_candidate_receipt_consistency
  AFTER INSERT OR UPDATE
  ON "template_twin_completed_candidate_review_receipts"
  DEFERRABLE INITIALLY DEFERRED
  FOR EACH ROW EXECUTE FUNCTION template_twin_assert_completed_candidate_receipt();

COMMIT;
