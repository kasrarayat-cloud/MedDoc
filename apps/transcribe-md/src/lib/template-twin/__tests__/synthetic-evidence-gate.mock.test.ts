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

import { afterEach, beforeEach, describe, expect, it } from 'vitest';

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
afterEach(() => {
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
