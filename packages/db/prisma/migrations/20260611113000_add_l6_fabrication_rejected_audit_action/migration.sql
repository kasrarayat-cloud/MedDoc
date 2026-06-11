-- L6 fabrication gate (2026-06-11 — hallucination-reconciliation RED finding).
-- ----------------------------------------------------------------------------
-- Add the `L6_FABRICATION_REJECTED` enum value to AuditAction. Emitted when
-- the post-polish fidelity gate rejects L6's output (new clinical claims
-- relative to its input, a negation/meaning flip, or any gate/verifier
-- failure — fail-closed) and the visit falls back to the pre-L6 (L4) draft.
-- Metadata carries counts + enum-class strings only, never note content.
-- Additive enum value — safe on a live database.
ALTER TYPE "AuditAction" ADD VALUE 'L6_FABRICATION_REJECTED';
