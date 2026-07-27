-- The anchored verifier becomes AUDIT-ONLY: it still runs and still records
-- what it found, but no longer demotes content into a pending-suggestion lane.
-- This is the durable record of a run. Metadata carries category counts only
-- (visitId + {reason: n}) — never note text.
ALTER TYPE "AuditAction" ADD VALUE IF NOT EXISTS 'ANCHOR_FLAGS_RECORDED';
