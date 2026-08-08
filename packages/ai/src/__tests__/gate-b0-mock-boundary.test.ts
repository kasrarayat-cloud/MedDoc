// @vitest-environment node
// ============================================================================
// B0 GATE — a mocked run METERS. Zero events is the failure this kills.
// ----------------------------------------------------------------------------
// ⚠️ THE FAILURE MODE THIS ITEM EXISTS TO KILL, STATED SO IT CANNOT BE
// RE-INTRODUCED QUIETLY:
//
//     ZERO USAGE EVENTS LOOKS EXACTLY LIKE A WORKING METER THAT FOUND
//     NOTHING TO RECORD.
//
// Before B0 the mock short-circuited the whole STAGE in `model-client.ts`, so a
// mocked QA pipeline never reached `logApiUsage` and emitted nothing at all.
// B1's gate ("prove a usage row exists on QA") and B4's ("one event per stage")
// were therefore unsatisfiable — and they would have failed by returning
// nothing, which reads as "no problems found" rather than "the meter is not
// wired". A check that cannot distinguish those two states is not a check.
//
// So the mock now substitutes only the VENDOR CALL (`createMessage` in
// anthropic.ts). Everything below it runs for real under mock: parsing,
// validation, token extraction, and the meter.
//
// ── WHAT THIS GATE ASSERTS, IN BOTH DIRECTIONS ────────────────────────────
//   EMITS      a mocked complete()/completeText() writes a usage event
//   MARKED     that event carries unitsSource='mock', never 'vendor'
//   FREE       its money columns are ZERO — no vendor was called
//   QUIET      `ai_calls` gets NOTHING under mock (ruled: real vendors only)
//   REAL       an unmocked run still writes 'vendor' and a real cost
//
// The last one is not decoration: a change that made EVERY row 'mock' would
// satisfy the first four perfectly. Both directions, or the gate is a
// rubber stamp.
// ============================================================================

import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest';

const usageWrites: Record<string, unknown>[] = [];
const aiCallWrites: Record<string, unknown>[] = [];

vi.mock('@meddoc/db', () => {
  const client = {
    apiUsageEvent: {
      create: (a: { data: Record<string, unknown> }) => {
        usageWrites.push(a.data);
        return Promise.resolve(a.data);
      },
    },
    aiCall: {
      create: (a: { data: Record<string, unknown> }) => {
        aiCallWrites.push(a.data);
        return Promise.resolve(a.data);
      },
    },
  };
  return { __esModule: true, default: client, prisma: client };
});

/** logApiUsage defers via setImmediate — drain it before asserting. */
const drain = () => new Promise((r) => setImmediate(r));

describe('B0 — the mock boundary sits BELOW the meter', () => {
  beforeEach(() => {
    usageWrites.length = 0;
    aiCallWrites.length = 0;
    vi.resetModules();
    process.env.MOCK_AI_CALLS = 'true';
    // ⚠️ A KEY IS STILL REQUIRED UNDER MOCK, ON PURPOSE. `getClient()` stays the
    // first statement of both public functions and OUTSIDE their try — B0 did
    // not move it. That keeps the two-condition doctrine intact: the flag stops
    // the call, and the dummy credential is what survives a code path that
    // forgets the flag.
    process.env.ANTHROPIC_API_KEY = 'test-dummy-never-valid';
  });
  afterEach(() => {
    delete process.env.MOCK_AI_CALLS;
    delete process.env.ANTHROPIC_API_KEY;
  });

  it('EMITS + MARKED + FREE: a mocked completeText writes a mock-marked, zero-cost usage event', async () => {
    const { anthropicCompleteText } = await import('../anthropic');
    await anthropicCompleteText({
      practiceId: 'prac_1',
      visitId: 'vis_1',
      userId: 'usr_1',
      purpose: 'tm_polish',
      model: 'claude-sonnet-4-6',
      system: 's',
      user: 'u',
    } as never);
    await drain();

    expect(usageWrites.length, 'a mocked run emitted NO usage event — the exact failure B0 kills').toBeGreaterThan(0);
    const row = usageWrites[usageWrites.length - 1];
    expect(row.unitsSource, 'a mock row must not claim vendor provenance').toBe('mock');
    expect(row.totalCostUsd, 'no vendor was called, so the true cost is zero').toBe(0);
    expect(row.unitCostUsd).toBe(0);
  });

  it('THROUGH THE PIPELINE ENTRY: modelClient.completeText meters under mock', async () => {
    // ⚠️ THIS ARM EXISTS BECAUSE THE FIRST VERSION OF THIS GATE DID NOT CATCH
    // THE ORIGINAL BUG. It called `anthropicCompleteText` directly, so
    // restoring the stage-level short-circuit in `model-client.ts` — the exact
    // regression B0 fixes — left the gate GREEN. The bug lived one layer above
    // the layer under test.
    //
    // `modelClient` is what the worker layers actually call, so that is the
    // entry point the gate has to watch. Mutation-proven: reinstating the
    // short-circuit here reds this test.
    const { modelClient } = await import('../model-client');
    await modelClient.completeText({
      practiceId: 'prac_1',
      visitId: 'vis_1',
      userId: 'usr_1',
      purpose: 'tm_polish',
      provider: 'anthropic',
      model: 'claude-sonnet-4-6',
      system: 's',
      user: 'u',
    } as never);
    await drain();

    expect(
      usageWrites.length,
      'the PIPELINE entry emitted no usage event — a stage-level mock short-circuit is back',
    ).toBeGreaterThan(0);
    expect(usageWrites[usageWrites.length - 1].unitsSource).toBe('mock');
  });

  it('QUIET: ai_calls gets NOTHING under mock — it is a real-vendor-calls-only table', async () => {
    const { anthropicCompleteText } = await import('../anthropic');
    await anthropicCompleteText({
      practiceId: 'prac_1',
      visitId: 'vis_1',
      userId: 'usr_1',
      purpose: 'tm_polish',
      model: 'claude-sonnet-4-6',
      system: 's',
      user: 'u',
    } as never);
    await drain();

    expect(
      aiCallWrites.length,
      'a mock run wrote to ai_calls — that table asserts a real vendor was called',
    ).toBe(0);
  });

  it('REAL (the direction that stops this being a rubber stamp): unmocked rows say vendor', async () => {
    // Proven at the builder rather than by calling a live vendor: the writer is
    // what decides the marker and the zeroing, and it is the thing under test.
    process.env.MOCK_AI_CALLS = 'false';
    const { logApiUsage } = await import('../api-usage');
    logApiUsage({
      unitsSource: 'vendor',
      provider: 'anthropic',
      operation: 'test',
      unitCount: 10,
      unitType: 'tokens_in',
      unitCostUsd: 0.5,
      totalCostUsd: 1.25,
      requestId: 'req_real',
    });
    await drain();

    const row = usageWrites[usageWrites.length - 1];
    expect(row.unitsSource).toBe('vendor');
    expect(row.totalCostUsd, 'a vendor row must keep its real cost — zeroing everything would pass the mock tests too').toBe(1.25);
  });
});
