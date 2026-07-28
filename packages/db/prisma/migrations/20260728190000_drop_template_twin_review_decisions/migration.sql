-- Drop template_twin_review_decisions.
--
-- The table shipped with the Template Twin schema and NO CODE EVER TOUCHED IT:
-- no Prisma client call, no raw SQL, no writer, no reader. It held 0 rows in
-- production and 0 in QA. A table that models a review lane nobody built reads,
-- to the next person, as a feature that exists.
--
-- ABORT IF IT IS NOT EMPTY. The audit that justified this drop was taken at plan
-- time; this runs at migration time, possibly on a database nobody has looked at.
-- A clinical review decision is a physician's recorded judgement — if one exists
-- anywhere, this migration must fail loudly rather than delete it.
DO $$
DECLARE n bigint;
BEGIN
  IF to_regclass('public.template_twin_review_decisions') IS NULL THEN
    RAISE NOTICE 'template_twin_review_decisions already absent — nothing to drop';
    RETURN;
  END IF;
  EXECUTE 'SELECT count(*) FROM template_twin_review_decisions' INTO n;
  IF n <> 0 THEN
    RAISE EXCEPTION
      'REFUSING to drop template_twin_review_decisions: % row(s) present. These are physician review decisions. Export and adjudicate them before dropping.', n;
  END IF;
  EXECUTE 'DROP TABLE template_twin_review_decisions';
  RAISE NOTICE 'template_twin_review_decisions dropped (was empty)';
END
$$;
