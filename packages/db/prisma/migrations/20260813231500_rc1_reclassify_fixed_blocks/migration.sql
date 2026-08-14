-- ===========================================================================
-- RC-1 — RECLASSIFY THE DOCTOR'S FIXED BLOCKS TO `always_include`.
-- Ruling #106(a)/(e), SPEC §4.3a. Data only: no DDL, no new object.
-- ---------------------------------------------------------------------------
-- WHAT THIS REPAIRS, AND FOR WHOM
--
-- A doctor uploaded a blank form, activated it, and the fixed TECHNIQUE
-- paragraph came back with `500 milliseconds` rendered as `0.5 seconds`. The
-- bytes were never lost; they sit verbatim in `note_templates.sections`. They
-- were lost on the way INTO the prompt.
--
-- `always_include` sections no longer reach the model at all: the model returns
-- slot VALUES and code stitches the doctor's own bytes around them. So flipping
-- the mode is what moves an existing template onto the assembled path — WITHOUT
-- a re-upload, which is why it runs first among the three fixes.
--
-- ---------------------------------------------------------------------------
-- ⚠️ IT IS ONE `DO` BLOCK, AND THAT IS A BUG FIX, NOT A STYLE CHOICE
-- ---------------------------------------------------------------------------
-- The first version was `UPDATE …;` followed by a separate `DO $$` guard block.
-- psql commits each statement on its own, so the UPDATE COMMITTED BEFORE THE
-- GUARDS RAN: the abort announced the fault and kept the damage, and with
-- default settings psql still exited 0. `prisma migrate deploy` wraps each
-- migration in a transaction, so it would have shipped working and stayed
-- latent until somebody applied the file by hand — which this programme does,
-- to QA, routinely.
--
-- A single `DO` block is a single statement. An exception inside it unwinds
-- everything it did, in every caller, with no enclosing transaction required.
--
-- ---------------------------------------------------------------------------
-- ⚠️ AND THE WRITE CANNOT DAMAGE WHAT IT DOES NOT TOUCH — BY CONSTRUCTION
-- ---------------------------------------------------------------------------
-- The first version rebuilt the whole `sections` array with `jsonb_agg` and
-- then CHECKED that nothing was lost. Two of those checks were sound and one
-- was not: `EXCEPT ALL` is one-directional, so a section GAINED at the end —
-- exactly what a botched aggregate produces — passed every guard and reported
-- the expected figure.
--
-- This version writes `jsonb_set(sections, ARRAY[idx,'defaultTextMode'], …)`
-- per matching element. One scalar changes. Order, count, keys, labels and
-- every byte of `defaultText` are untouchable, so the class those guards
-- existed to catch is no longer representable. That is strictly better than a
-- check: a check has to be right about a failure, and this cannot fail.
--
-- ---------------------------------------------------------------------------
-- WHY THE PREDICATE IS AN ALLOWLIST, AND WHY IT IS NARROWER THAN IT LOOKS
-- ---------------------------------------------------------------------------
-- ⚠️ `defaultText` IS TWO DIFFERENT THINGS AND THE SCHEMA CANNOT TELL THEM
-- APART. Measured on the real imaging templates:
--
--   * a WHOLE FIXED BLOCK — the scan-protocol paragraph; a `LABEL: {{slot}}`
--     field header. The section IS its default text. Assembling it is the fix.
--   * a SCAFFOLD THE MODEL EXTENDS — a per-leg FINDINGS stub, a per-side
--     IMPRESSION stub. The visit's real content is written AROUND it.
--
-- Flipping the second kind REPLACES THE VISIT'S CLINICAL FINDINGS WITH AN EMPTY
-- SKELETON while satisfying every static-fidelity check in this programme: the
-- doctor's bytes preserved perfectly, the patient's gone. So the predicate is
-- an allowlist of the two kinds that were READ and confirmed, mirroring
-- `classify-default-text-mode.ts` exactly.
--
-- ⚠️ `exam_metadata` ADDITIONALLY REQUIRES AT LEAST ONE SLOT, and that clause
-- was added after an adversarial pass found the premise false on one real row.
-- The allowlist justifies that key as "every line is `LABEL: <slot>`; there is
-- no free prose for a model to add" — but one production template's
-- `exam_metadata` is SEVEN LINES WITH ZERO SLOTS, labels awaiting values the
-- model fills as text. Flipping that one freezes seven fields at the blank
-- form's bytes forever, which is the very class this predicate exists to
-- exclude. A field block is a fixed block only when its fields are SLOTS.
-- (A protocol paragraph is fixed prose whether or not it carries one, so
-- `technique` has no such requirement.)
--
-- ⚠️ `btrim(x, E' \t\n\r\f\v')`, NOT BARE `btrim`. Postgres `btrim/1` strips
-- SPACES ONLY, so `E'\n'` reads as non-empty while JS `.trim()` calls it empty
-- — a demonstrated disagreement between two implementations whose whole purpose
-- is to agree. Latent today (no persist path stores untrimmed text) and fixed
-- anyway, because the pair is only worth having if it is exact.
--
-- RE-RUNNABLE: the predicate requires `scaffold_confirm`, so a second pass
-- matches nothing and writes nothing at all.
-- ===========================================================================

DO $$
DECLARE
  bad_structured int;
  bad_mode       int;
  r              record;
  flipped        int := 0;
  touched        text[] := '{}';
BEGIN
  -- ── PRE-FLIGHT. Before any write, so an abort PREVENTS rather than reports.
  --
  -- G1 — nothing anywhere may already hold a structured `always_include`. That
  -- is an illegal state for the render path (`staticSections` ignores it), so
  -- finding one means something else wrote a mode this codebase does not
  -- honour, and this migration must not add to it.
  SELECT count(*) INTO bad_structured
  FROM note_templates t, LATERAL jsonb_array_elements(t.sections) s
  WHERE s->>'defaultTextMode' = 'always_include'
    AND s->'structure' IS NOT NULL
    AND jsonb_typeof(s->'structure') <> 'null';
  IF bad_structured > 0 THEN
    RAISE EXCEPTION 'RC-1 ABORT (pre-flight): % structured section(s) already carry always_include — a table is a fill surface, not a static region. Nothing has been written.', bad_structured;
  END IF;

  -- G2 — every mode in the table is one this migration understands. An unknown
  -- value means the vocabulary moved and this predicate is reasoning about a
  -- world that no longer exists.
  SELECT count(*) INTO bad_mode
  FROM note_templates t, LATERAL jsonb_array_elements(t.sections) s
  WHERE s->>'defaultTextMode' NOT IN
        ('always_include', 'scaffold_confirm', 'omit_unless_supported');
  IF bad_mode > 0 THEN
    RAISE EXCEPTION 'RC-1 ABORT (pre-flight): % section(s) carry an unrecognised defaultTextMode. Nothing has been written.', bad_mode;
  END IF;

  -- ── THE WRITE. One scalar per matching element; nothing else is expressible.
  FOR r IN
    SELECT t.id AS template_id, (e.ord - 1) AS idx
    FROM note_templates t,
         LATERAL jsonb_array_elements(t.sections) WITH ORDINALITY AS e(s, ord)
    WHERE e.s->>'defaultTextMode' = 'scaffold_confirm'
      AND COALESCE(btrim(e.s->>'defaultText', E' \t\n\r\f\v'), '') <> ''
      AND (e.s->'structure' IS NULL OR jsonb_typeof(e.s->'structure') = 'null')
      AND (
        e.s->>'key' = 'technique'
        OR (e.s->>'key' = 'exam_metadata' AND e.s->>'defaultText' LIKE '%{{one of:%')
      )
      -- The FAMILY clause: slot-bearing / imaging only. Plain SOAP keeps
      -- today's classification and therefore today's byte-identical prompts.
      AND EXISTS (
        SELECT 1 FROM jsonb_array_elements(t.sections) f
        WHERE f->>'defaultText' LIKE '%{{one of:%'
           OR f->>'defaultText' LIKE '%500 milliseconds%'
      )
  LOOP
    UPDATE note_templates
       SET sections = jsonb_set(
             sections,
             ARRAY[r.idx::text, 'defaultTextMode'],
             '"always_include"'::jsonb
           )
     WHERE id = r.template_id;
    flipped := flipped + 1;
    -- ⚠️ TEMPLATES TOUCHED BY *THIS RUN*, not templates that happen to hold an
    -- always_include section. The first version counted the latter and reported
    -- `0 section(s) flipped across 44 template(s)` on a re-run — a figure that
    -- describes the database rather than the act, in a line the §2.5
    -- declaration is judged against.
    IF NOT (r.template_id = ANY(touched)) THEN
      touched := touched || r.template_id;
    END IF;
  END LOOP;

  -- An observation, not an assertion: the deploy transcript carries the number
  -- the §2.5 declaration is judged against.
  RAISE NOTICE 'RC-1: % section(s) flipped to always_include across % template(s)', flipped, coalesce(array_length(touched, 1), 0);
END $$;
