-- ============================================================================
-- Capture Anthropic cache_read / cache_creation token counts on every AI
-- call. Anthropic bills cache reads at 0.10x base input and 5-min cache
-- writes at 1.25x; without these columns those tokens silently dropped
-- on the floor and the admin dashboard couldn't honour the discount.
--
-- Default 0 lets existing rows backfill clean + lets the cost dispatcher
-- treat "absent" the same as "no caching attached" (current state for 11
-- of 12 layers — only the LLM-MDM judge attaches cache_control today).
-- ============================================================================

-- AlterTable
ALTER TABLE "ai_calls" ADD COLUMN     "cacheCreationInputTokens" INTEGER NOT NULL DEFAULT 0,
ADD COLUMN     "cacheReadInputTokens" INTEGER NOT NULL DEFAULT 0;

-- AlterTable
ALTER TABLE "api_usage_events" ADD COLUMN     "cacheCreationInputTokens" INTEGER NOT NULL DEFAULT 0,
ADD COLUMN     "cacheReadInputTokens" INTEGER NOT NULL DEFAULT 0;
