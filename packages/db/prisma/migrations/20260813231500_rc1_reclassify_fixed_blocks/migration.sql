-- ===========================================================================
-- RC-1 — RECLASSIFY THE DOCTOR'S FIXED BLOCKS TO `always_include`.
-- Ruling #106(a)/(e), SPEC §4.3a. Data only: no DDL, no new object.
-- ---------------------------------------------------------------------------
-- WHAT THIS REPAIRS, AND FOR WHOM
--
-- A doctor uploaded a blank form, activated it, and the fixed TECHNIQUE
-- paragraph came back paraphrased — `500 milliseconds` as `0.5 seconds`. The
-- bytes were never lost; they sit verbatim in `note_templates.sections`. They
-- were lost at RENDER time, because a `scaffold_confirm` default is injected
-- INTO THE PROMPT as text to reproduce, and a model asked to reproduce prose
-- normalises it.
--
-- `always_include` sections no longer reach the model at all: the model returns
-- slot VALUES and code stitches the doctor's own bytes around them. So flipping
-- the mode is what moves an existing template onto the assembled path —
-- WITHOUT a re-upload, which is why this runs first among the three fixes.
--
-- ---------------------------------------------------------------------------
-- WHY IT IS NARROW, AND WHY THE NARROWNESS IS A SAFETY PROPERTY
-- ---------------------------------------------------------------------------
-- ⚠️ `defaultText` IS TWO DIFFERENT THINGS AND THE SCHEMA CANNOT TELL THEM
-- APART. Measured on the real imaging templates:
--
--   * a WHOLE FIXED BLOCK — the scan-protocol paragraph; the label:value field
--     header. The section IS its default text. Assembling it is the fix.
--   * a SCAFFOLD THE MODEL EXTENDS — a per-leg FINDINGS stub, a per-side
--     IMPRESSION stub. The visit's real content is written AROUND it.
--
-- ⚠️ FLIPPING THE SECOND KIND WOULD REPLACE THE VISIT'S CLINICAL FINDINGS WITH
-- AN EMPTY SKELETON — while satisfying every static-fidelity check this
-- programme has, because the doctor's bytes would be preserved perfectly and
-- only the patient's would be gone. A worse failure than the one being fixed,
-- and a silent one. So the predicate is an ALLOWLIST of the two section kinds
-- that were READ and confirmed to be whole fixed blocks, mirroring
-- `classify-default-text-mode.ts` exactly. That file is the source; this is its
-- copy for rows that already exist, and the pair is named in both directions.
--
-- ---------------------------------------------------------------------------
-- THE GUARDS ARE PREDICATE-SHAPED, NOT COUNT-SHAPED — deliberately
-- ---------------------------------------------------------------------------
-- ⚠️ A MIGRATION THAT ABORTS ON AN ABSOLUTE COUNT IS A MIGRATION THAT REFUSES
-- TO RUN ON QA. Production's figures (templates touched, sections flipped) are
-- DECLARED IN THE DEPLOY DECLARATION under §2.5, where they are checked against
-- the run. What is asserted HERE is what must be true in every environment:
--
--   G1  no STRUCTURED section ends up `always_include`      (data integrity)
--   G2  not one byte of `defaultText` changed anywhere      (this is a mode
--                                                            migration, and a
--                                                            migration that
--                                                            edited a doctor's
--                                                            prose while fixing
--                                                            prose-fidelity
--                                                            would be beyond
--                                                            irony)
--   G3  no section was added, removed or reordered
--   G4  every mode change is `scaffold_confirm` → `always_include`; nothing
--       else moved, in either direction
--
-- ⚠️ G2 AND G3 EXIST BECAUSE THE UPDATE REBUILDS THE WHOLE `sections` ARRAY.
-- `jsonb_agg` is an easy way to lose an element's order or a key's value, and
-- neither loss raises anything by itself.
--
-- RE-RUNNABLE: applying it twice is a no-op — the second pass matches nothing,
-- because the predicate requires `scaffold_confirm`. It writes no new
-- information, so #106's reversal path ("re-runnable from stored sections")
-- holds.
-- ===========================================================================

-- Snapshot BEFORE, so the guards compare against something rather than against
-- an expectation. A temp table dies with the transaction.
CREATE TEMP TABLE _rc1_before ON COMMIT DROP AS
SELECT t.id AS template_id,
       e.ord,
       e.s->>'key'             AS section_key,
       e.s->>'defaultTextMode' AS mode,
       e.s->>'defaultText'     AS default_text
FROM note_templates t,
     LATERAL jsonb_array_elements(t.sections) WITH ORDINALITY AS e(s, ord);

UPDATE note_templates t
SET sections = sub.new_sections
FROM (
  SELECT t2.id,
         jsonb_agg(
           CASE
             WHEN e.s->>'defaultTextMode' = 'scaffold_confirm'
              AND e.s->>'key' IN ('technique', 'exam_metadata')
              AND COALESCE(btrim(e.s->>'defaultText'), '') <> ''
              AND (e.s->'structure' IS NULL OR jsonb_typeof(e.s->'structure') = 'null')
             THEN jsonb_set(e.s, '{defaultTextMode}', '"always_include"')
             ELSE e.s
           END
           ORDER BY e.ord
         ) AS new_sections
  FROM note_templates t2,
       LATERAL jsonb_array_elements(t2.sections) WITH ORDINALITY AS e(s, ord)
  -- The FAMILY clause: slot-bearing / imaging only. Plain SOAP keeps today's
  -- classification and therefore today's byte-identical prompts (#106(e)).
  WHERE EXISTS (
    SELECT 1
    FROM jsonb_array_elements(t2.sections) f
    WHERE f->>'defaultText' LIKE '%{{one of:%'
       OR f->>'defaultText' LIKE '%500 milliseconds%'
  )
  GROUP BY t2.id
) sub
WHERE t.id = sub.id;

DO $$
DECLARE
  bad_structured int;
  bad_text       int;
  bad_shape      int;
  bad_move       int;
  flipped        int;
  templates      int;
BEGIN
  -- G1 — no structured section may be `always_include`.
  SELECT count(*) INTO bad_structured
  FROM note_templates t, LATERAL jsonb_array_elements(t.sections) s
  WHERE s->>'defaultTextMode' = 'always_include'
    AND s->'structure' IS NOT NULL
    AND jsonb_typeof(s->'structure') <> 'null';
  IF bad_structured > 0 THEN
    RAISE EXCEPTION 'RC-1 ABORT: % structured section(s) carry always_include — a table is a fill surface, not a static region', bad_structured;
  END IF;

  -- G2 — not one byte of defaultText moved.
  SELECT count(*) INTO bad_text
  FROM _rc1_before b
  JOIN (
    SELECT t.id AS template_id, e.ord, e.s->>'defaultText' AS default_text
    FROM note_templates t, LATERAL jsonb_array_elements(t.sections) WITH ORDINALITY AS e(s, ord)
  ) a ON a.template_id = b.template_id AND a.ord = b.ord
  WHERE a.default_text IS DISTINCT FROM b.default_text;
  IF bad_text > 0 THEN
    RAISE EXCEPTION 'RC-1 ABORT: % section(s) had defaultText altered — this migration changes MODE only', bad_text;
  END IF;

  -- G3 — same sections, same order, same count.
  SELECT count(*) INTO bad_shape
  FROM (
    SELECT template_id, ord, section_key FROM _rc1_before
    EXCEPT ALL
    SELECT t.id, e.ord, e.s->>'key'
    FROM note_templates t, LATERAL jsonb_array_elements(t.sections) WITH ORDINALITY AS e(s, ord)
  ) d;
  IF bad_shape > 0 THEN
    RAISE EXCEPTION 'RC-1 ABORT: % section(s) added, removed or reordered', bad_shape;
  END IF;

  -- G4 — every move is scaffold_confirm -> always_include, and nothing else.
  SELECT count(*) INTO bad_move
  FROM _rc1_before b
  JOIN (
    SELECT t.id AS template_id, e.ord, e.s->>'defaultTextMode' AS mode
    FROM note_templates t, LATERAL jsonb_array_elements(t.sections) WITH ORDINALITY AS e(s, ord)
  ) a ON a.template_id = b.template_id AND a.ord = b.ord
  WHERE a.mode IS DISTINCT FROM b.mode
    AND NOT (b.mode = 'scaffold_confirm' AND a.mode = 'always_include');
  IF bad_move > 0 THEN
    RAISE EXCEPTION 'RC-1 ABORT: % section(s) changed mode in an unexpected direction', bad_move;
  END IF;

  SELECT count(*), count(DISTINCT a.template_id) INTO flipped, templates
  FROM _rc1_before b
  JOIN (
    SELECT t.id AS template_id, e.ord, e.s->>'defaultTextMode' AS mode
    FROM note_templates t, LATERAL jsonb_array_elements(t.sections) WITH ORDINALITY AS e(s, ord)
  ) a ON a.template_id = b.template_id AND a.ord = b.ord
  WHERE b.mode = 'scaffold_confirm' AND a.mode = 'always_include';

  -- NOT an assertion — an observation, printed so the deploy transcript carries
  -- the number the §2.5 declaration is judged against.
  RAISE NOTICE 'RC-1: % section(s) flipped to always_include across % template(s)', flipped, templates;
END $$;
