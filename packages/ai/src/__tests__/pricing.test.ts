// ============================================================================
// Fix-Pack 1 / audit Finding 04.1 + 04.3 — per-model cost dispatcher.
// ----------------------------------------------------------------------------
// Guard test that the per-model pricing dispatcher used by anthropic.ts
// + buildAnthropicUsage prices each Claude model according to its own
// rate card (rather than the legacy "always Sonnet" hardcode). Opus
// 4.7 has a 5x higher input rate and 5x higher output rate than Sonnet
// 4.6; if the dispatcher silently routes Opus calls to Sonnet's
// pricing, AiCall + ApiUsageEvent rows drift and the admin dashboard
// is wrong.
//
// Defaults asserted here mirror the constants in pricing.ts:
//   Sonnet 4.6  $3 / M input, $15 / M output  → 300 / 1500 cents
//   Opus 4.7    $15 / M input, $75 / M output → 1500 / 7500 cents
// Tests intentionally use 1_000_000-token round numbers so the
// per-million rates show up as exact integer cents (no rounding noise).
// ============================================================================

import { describe, expect, it } from 'vitest';

import { claudeCostCents } from '../pricing';

describe('claudeCostCents — per-model dispatcher', () => {
  it('prices claude-opus-4-7 input at $15 / M tokens (1500 cents)', () => {
    expect(claudeCostCents('claude-opus-4-7', 1_000_000, 0)).toBe(1500);
  });

  it('prices claude-sonnet-4-6 input at $3 / M tokens (300 cents)', () => {
    expect(claudeCostCents('claude-sonnet-4-6', 1_000_000, 0)).toBe(300);
  });

  it('returns 0 for an unknown model rather than fabricating cost', () => {
    expect(claudeCostCents('unknown-model', 100, 100)).toBe(0);
  });

  it('prices claude-opus-4-7 output at $75 / M tokens (7500 cents)', () => {
    expect(claudeCostCents('claude-opus-4-7', 0, 1_000_000)).toBe(7500);
  });

  it('prices claude-sonnet-4-6 output at $15 / M tokens (1500 cents)', () => {
    expect(claudeCostCents('claude-sonnet-4-6', 0, 1_000_000)).toBe(1500);
  });

  it('sums input + output when both are nonzero (Opus mixed call)', () => {
    // 1M input @ 1500 cents + 1M output @ 7500 cents = 9000 cents
    expect(claudeCostCents('claude-opus-4-7', 1_000_000, 1_000_000)).toBe(9000);
  });
});
