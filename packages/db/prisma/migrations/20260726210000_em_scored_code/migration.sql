-- The E/M code the level was last validated at.
--
-- Without it, a re-score has no "before": it scores the current note, treats
-- that as the baseline, and concludes nothing moved. NULL = never validated;
-- the first re-score establishes the baseline rather than asserting a change
-- it cannot substantiate.
ALTER TABLE "transcribe_visits" ADD COLUMN "emScoredCode" TEXT;
