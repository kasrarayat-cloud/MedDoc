// ============================================================================
// Fix-Pack 1 / audit Finding 04.1 + 04.3 — per-model cost dispatcher.
// ----------------------------------------------------------------------------
// Guard test that the per-model pricing dispatcher used by anthropic.ts
// + buildAnthropicUsage prices each Claude model according to its own
// rate card (rather than the legacy "always Sonnet" hardcode). If the
// dispatcher silently routes Opus calls to Sonnet's pricing — or
// retains stale Opus 4.x rates after Anthropic cuts them — AiCall +
// ApiUsageEvent rows drift and the admin dashboard is wrong.
//
// Rates refreshed 2026-05-12 from docs.anthropic.com/en/docs/about-
// claude/pricing. Opus 4.7 was previously asserted at $15/$75 (the
// 4.x family rate); Anthropic cut it to $5/$25 alongside 4.5/4.6, and
// these test values were updated to match. The prior $15/$75 had been
// 3x stale and was the single biggest source of the admin-dashboard
// cost overcount.
//
// Rate card (current):
//   Sonnet 4.6  $3 / M input, $15 / M output  → 300 / 1500 cents
//   Opus 4.7    $5 / M input, $25 / M output  → 500 / 2500 cents
//   Haiku 4.5   $1 / M input, $5  / M output  → 100 /  500 cents
// Cache multipliers (relative to base input):
//   read  0.10x   write_5m  1.25x   write_1h  2.00x
// ============================================================================

import { describe, expect, it } from 'vitest';

import { claudeCostCents } from '../pricing';

describe('claudeCostCents — per-model dispatcher', () => {
  it('prices claude-opus-4-7 input at $5 / M tokens (500 cents)', () => {
    expect(claudeCostCents('claude-opus-4-7', 1_000_000, 0)).toBe(500);
  });

  it('prices claude-sonnet-4-6 input at $3 / M tokens (300 cents)', () => {
    expect(claudeCostCents('claude-sonnet-4-6', 1_000_000, 0)).toBe(300);
  });

  it('prices claude-haiku-4-5 input at $1 / M tokens (100 cents)', () => {
    expect(claudeCostCents('claude-haiku-4-5', 1_000_000, 0)).toBe(100);
  });

  it('returns 0 for an unknown model rather than fabricating cost', () => {
    expect(claudeCostCents('unknown-model', 100, 100)).toBe(0);
  });

  it('prices claude-opus-4-7 output at $25 / M tokens (2500 cents)', () => {
    expect(claudeCostCents('claude-opus-4-7', 0, 1_000_000)).toBe(2500);
  });

  it('prices claude-sonnet-4-6 output at $15 / M tokens (1500 cents)', () => {
    expect(claudeCostCents('claude-sonnet-4-6', 0, 1_000_000)).toBe(1500);
  });

  it('sums input + output when both are nonzero (Opus mixed call)', () => {
    // 1M input @ 500 cents + 1M output @ 2500 cents = 3000 cents
    expect(claudeCostCents('claude-opus-4-7', 1_000_000, 1_000_000)).toBe(3000);
  });

  it('prices claude-opus-4-8 identically to 4.7 (stacked case, same rate card)', () => {
    // Locks the stacked opus-4-8 case so a future un-stack can't silently drop
    // it into `default: return 0` (zeroed cost attribution).
    expect(claudeCostCents('claude-opus-4-8', 1_000_000, 0)).toBe(500);
    expect(claudeCostCents('claude-opus-4-8', 0, 1_000_000)).toBe(2500);
    expect(claudeCostCents('claude-opus-4-8', 1_000_000, 1_000_000)).toBe(3000);
    // cache-multiplier path resolves the opus base rate (not the 0 default)
    expect(claudeCostCents('claude-opus-4-8', 0, 0, 0, 1_000_000)).toBe(625);
  });

  it('applies the 0.1x cache-read multiplier on top of base input', () => {
    // 1M Sonnet input ($3) + 1M cache reads ($0.30) = 330 cents
    expect(claudeCostCents('claude-sonnet-4-6', 1_000_000, 0, 1_000_000, 0)).toBe(330);
  });

  it('applies the 1.25x 5-minute cache-write multiplier', () => {
    // 1M cache_creation_input on Opus ($5 * 1.25 = $6.25 = 625 cents) only
    expect(claudeCostCents('claude-opus-4-7', 0, 0, 0, 1_000_000)).toBe(625);
  });
});
