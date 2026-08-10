// @vitest-environment node
// ⚠️ B0 — PINNED TO NODE. These exercise server-side parsing, but inherited the
// app suite jsdom default. Since B0 the mock runs BELOW getClient(), so the
// Anthropic SDK is constructed even under mock — and it refuses to load in a
// browser-like environment. The env pin is the honest fix: nothing here touches
// the DOM, and the alternative (skipping client construction under mock) would
// collapse the two-condition doctrine to one.
// ============================================================================
// parseNoteToTemplate under MOCK_AI_CALLS — fixture validation (full-qa F7).
// ----------------------------------------------------------------------------
// Unlike parse-note-to-template.test.ts (which vi.mocks modelClient to feed
// crafted outputs), this file uses the REAL modelClient.complete() and flips
// MOCK_AI_CALLS=true so the engine resolves through packages/ai/src/mock.ts.
// It proves the committed note-format fixtures (tm_template_parse +
// tm_template_phi_scan) are schema-valid and that the full
// parse→gate flow runs under MOCK — which it could not before (the mock threw
// on an unknown purpose), so upload→parse→review→activate was untestable.
// Also exercises the PHI-gate REJECT path via MOCK_TEMPLATE_PHI_FLAG.
// ============================================================================

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

// ⚠️ THE METER RUNS UNDER MOCK — BY DESIGN (B0) — AND IT WRITES TO POSTGRES.
// This file uses the REAL modelClient, so complete() reaches logApiUsage
// (packages/ai/src/api-usage.ts:146), which defers `apiUsageEvent.create` via
// setImmediate (:172) and, on failure, emits console.warn (:204) from a callback
// NOTHING awaits. The `unit` CI job leaves DATABASE_URL unset on purpose — so the
// db-guard tests can assert the fail-closed path — which means that write can
// never succeed and the warn ALWAYS fires. Vitest forwards every console write
// over the worker RPC; when the warn lands after this file's tests have finished,
// the RPC closes at environment teardown with the call still pending and rejects:
//
//     EnvironmentTeardownError: Closing rpc while "onUserConsoleLog" was pending
//
// which is an unhandled error, so the run exits 1 WITH EVERY TEST GREEN. Observed
// on run 31351013424 attempt 1 (head 6247aa33): five such warns, two lost the race.
//
// Stubbing the DB seam keeps the write in-process — it resolves, the catch never
// runs, nothing outlives the file. The REAL modelClient, which is the whole point
// of this file, is untouched. The factory matches
// packages/ai/src/__tests__/gate-b0-mock-boundary.test.ts:39-55 exactly: no extra
// surface, so a future module importing a model this stub lacks fails LOUDLY
// rather than reading `undefined`.
vi.mock('@meddoc/db', () => {
  const client = {
    apiUsageEvent: { create: (a: unknown) => Promise.resolve(a) },
    aiCall: { create: (a: unknown) => Promise.resolve(a) },
  };
  return { __esModule: true, default: client, prisma: client };
});

import { parseNoteToTemplate } from '../parse-note-to-template';

const ctx = { practiceId: 'p1', userId: 'u1' };
// Plain note — no angle-bracket delimiter tokens (those reject pre-LLM).
const NOTE =
  'Follow-up. Subjective: doing well. Objective: vitals stable, exam unremarkable. Assessment: stable. Plan: continue current management.';

const prevMock = process.env.MOCK_AI_CALLS;
const prevFlag = process.env.MOCK_TEMPLATE_PHI_FLAG;

beforeEach(() => {
  process.env.MOCK_AI_CALLS = 'true';
    // ⚠️ B0 — MOCK MODE REQUIRES A KEY, DELIBERATELY. `getClient()` stays the
    // first statement of the Anthropic wrappers and OUTSIDE their try, so the
    // two-condition doctrine holds: the FLAG stops the call, and the DUMMY
    // CREDENTIAL is what survives a code path that forgets the flag. A mock
    // that runs with no key at all is one condition, not two.
    process.env.ANTHROPIC_API_KEY = 'test-dummy-never-valid';
  delete process.env.MOCK_TEMPLATE_PHI_FLAG;
});
afterEach(async () => {
  // logApiUsage defers via setImmediate — drain it so no metering work outlives
  // this file, whatever the stub does. Defence in depth against the same race.
  await new Promise((r) => setImmediate(r));
  if (prevMock === undefined) delete process.env.MOCK_AI_CALLS;
  else process.env.MOCK_AI_CALLS = prevMock;
  if (prevFlag === undefined) delete process.env.MOCK_TEMPLATE_PHI_FLAG;
  else process.env.MOCK_TEMPLATE_PHI_FLAG = prevFlag;
});

describe('parseNoteToTemplate — MOCK_AI_CALLS fixtures (F7)', () => {
  it('parses to a clean, activatable template (clean PHI scan is the default)', async () => {
    const r = await parseNoteToTemplate(NOTE, ctx);

    expect(r.rejected).toBe(false);
    if (!r.rejected) {
      expect(r.template.name).toBe('[MOCK] General Follow-up');
      expect(r.template.sections.map((s) => s.key)).toEqual([
        'subjective',
        'objective',
        'assessment',
        'plan',
      ]);
      // A parsed default is never always_include; the one generic default
      // (objective normal-exam line) survives as scaffold_confirm.
      expect(
        r.template.sections.every((s) => s.defaultTextMode !== 'always_include'),
      ).toBe(true);
      const objective = r.template.sections.find((s) => s.key === 'objective');
      expect(objective?.defaultText).toContain('well-appearing');
      expect(objective?.defaultTextMode).toBe('scaffold_confirm');
    }
  });

  it('rejects via the PHI gate when MOCK_TEMPLATE_PHI_FLAG=true (reject path testable)', async () => {
    process.env.MOCK_TEMPLATE_PHI_FLAG = 'true';
    const r = await parseNoteToTemplate(NOTE, ctx);
    // The flagged scan sets anyUncertain → fail-safe gate rejects.
    expect(r.rejected).toBe(true);
  });
});
