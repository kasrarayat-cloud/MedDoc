-- Add briefHistory String[] to Patient. Default empty array — existing rows
-- get [] without backfill. Editable via the Edit Patient flow + the AI
-- assistant's update_patient tool.
ALTER TABLE "patients"
  ADD COLUMN "briefHistory" TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[];
