// @vitest-environment node
// ⚠️ B0 — PINNED TO NODE. These exercise server-side parsing, but inherited the
// app suite jsdom default. Since B0 the mock runs BELOW getClient(), so the
// Anthropic SDK is constructed even under mock — and it refuses to load in a
// browser-like environment. The env pin is the honest fix: nothing here touches
// the DOM, and the alternative (skipping client construction under mock) would
// collapse the two-condition doctrine to one.
// ============================================================================
// The synthetic-evidence gate under MOCK_AI_CALLS — fixture validation.
// ----------------------------------------------------------------------------
// WHY THIS FILE EXISTS
//
// The committed mock fixture for `tm_template_synthetic_phi_scan` was a copy of
// the `tm_template_phi_scan` shape — `{ phiFields, anyUncertain }` — but this
// gate parses with SyntheticEvidencePrivacyScanSchema, which is .strict() and
// requires `directIdentifierClasses` + `appearsExplicitlySynthetic`. So every
// call threw inside mockComplete, the gate turned that into
// SCAN_UNAVAILABLE, and runTemplateTwinSyntheticTest rethrew it as
// SYNTHETIC_EVIDENCE_REJECTED — "use clearly labeled synthetic test evidence".
//
// That message names the ONE cause the failure did not have. The evidence was
// perfectly well labeled; the fixture could not parse. Certification was
// therefore unreachable under MOCK for any input at all, which is why CI could
// never produce the CERTIFIED twin the visit-doc project requires.
//
// Nothing caught it because no test ever parsed that fixture against the
// schema that consumes it. This file does, through the REAL modelClient with
// MOCK_AI_CALLS=true — the same shape as parse-note-to-template.mock.test.ts.
//
// It also pins the half of the gate that is NOT mocked, so a future "make the
// mock permissive" change cannot quietly disable it: the explicit-synthetic
// marker and the deterministic structured-identifier scan still reject.
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

import {
  assertTemplateTwinSyntheticEvidencePhiFree,
  TemplateTwinSyntheticEvidenceRejectedError,
} from '../synthetic-evidence-gate';

const ctx = { practiceId: 'p1', userId: 'u1' };

/** The committed certification encounter — explicitly labeled, no identifiers. */
const CLEAN =
  'SYNTHETIC TEST ENCOUNTER — fictional data, not a real patient. ' +
  'Bilateral lower extremity venous duplex reflux study, bilateral detailed. ' +
  'Right great saphenous vein at the knee: diameter 5.1 millimeters, reflux 1.6 seconds.';

const prevMock = process.env.MOCK_AI_CALLS;

beforeEach(() => {
  process.env.MOCK_AI_CALLS = 'true';
    // ⚠️ B0 — MOCK MODE REQUIRES A KEY, DELIBERATELY. `getClient()` stays the
    // first statement of the Anthropic wrappers and OUTSIDE their try, so the
    // two-condition doctrine holds: the FLAG stops the call, and the DUMMY
    // CREDENTIAL is what survives a code path that forgets the flag. A mock
    // that runs with no key at all is one condition, not two.
    process.env.ANTHROPIC_API_KEY = 'test-dummy-never-valid';
});
afterEach(async () => {
  // logApiUsage defers via setImmediate — drain it so no metering work outlives
  // this file, whatever the stub does. Defence in depth against the same race.
  await new Promise((r) => setImmediate(r));
  if (prevMock === undefined) delete process.env.MOCK_AI_CALLS;
  else process.env.MOCK_AI_CALLS = prevMock;
});

describe('synthetic-evidence gate — MOCK_AI_CALLS fixture', () => {
  it('ACCEPTS clean, explicitly-labeled synthetic evidence', async () => {
    // Before the fixture fix this rejected — not because the evidence was
    // bad, but because the mock could not satisfy the gate's own schema.
    await expect(
      assertTemplateTwinSyntheticEvidencePhiFree({ encounterText: CLEAN, ...ctx }),
    ).resolves.toBeUndefined();
  });

  it('still REJECTS evidence with no explicit synthetic marker', async () => {
    // Deterministic half — not mocked, and must not be softened by the fixture.
    await expect(
      assertTemplateTwinSyntheticEvidencePhiFree({
        encounterText:
          'Bilateral lower extremity venous duplex reflux study. ' +
          'Right great saphenous vein at the knee: diameter 5.1 millimeters.',
        ...ctx,
      }),
    ).rejects.toBeInstanceOf(TemplateTwinSyntheticEvidenceRejectedError);
  });

  it('still REJECTS labeled evidence that carries a structured identifier', async () => {
    // A clean model verdict must not be able to wave through text that the
    // deterministic detector flags.
    await expect(
      assertTemplateTwinSyntheticEvidencePhiFree({
        encounterText: `${CLEAN} Contact the referrer at 555-867-5309.`,
        ...ctx,
      }),
    ).rejects.toBeInstanceOf(TemplateTwinSyntheticEvidenceRejectedError);
  });
});
