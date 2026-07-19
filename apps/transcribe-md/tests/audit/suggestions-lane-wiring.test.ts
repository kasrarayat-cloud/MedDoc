// ============================================================================
// Suggestions-lane wiring — structural pin (hybrid anchored generation,
// 2026-06-11).
// ----------------------------------------------------------------------------
// The L4b verifier persists demoted claims on transcribe_visits.
// suggestedClaims; the "Suggested by AI — not stated in this visit" lane is
// the doctor-adoption surface. Same source-level pattern as
// ready-view-review-banner.test.ts: pin the page → ready-view → lane →
// actions wire-through so a refactor can't silently disconnect it. Behavior
// is verified by the unit tests in
// src/actions/__tests__/suggestion-actions.test.ts; this is the cheap CI
// tripwire for the wiring itself.
// ============================================================================

import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

const APP = resolve(__dirname, '../..');
const page = readFileSync(
  resolve(APP, 'src/app/visits/[id]/page.tsx'),
  'utf8'
);
const readyView = readFileSync(
  resolve(APP, 'src/app/visits/[id]/visit-ready-view.tsx'),
  'utf8'
);
const lane = readFileSync(
  resolve(APP, 'src/app/visits/[id]/suggestions-lane.tsx'),
  'utf8'
);
const actions = readFileSync(
  resolve(APP, 'src/actions/suggestion-actions.ts'),
  'utf8'
);

describe('Suggestions-lane wiring', () => {
  it('page.tsx selects suggestedClaims and passes it into VisitReadyView', () => {
    // The visit query must keep selecting the column…
    expect(page).toMatch(/suggestedClaims: true/);
    // …and the VisitReadyView invocation must keep forwarding it (via the
    // strict coercion helper so lane indices always match the DB array).
    const invocation = page.slice(page.indexOf('<VisitReadyView'));
    expect(invocation).toMatch(
      /suggestedClaims=\{extractSuggestedClaims\(props\.suggestedClaims\)\}/
    );
  });

  it('VisitReadyView declares the typed prop and renders the lane conditionally', () => {
    expect(readyView).toMatch(/suggestedClaims\?: SuggestedClaimView\[\] \| null/);
    expect(readyView).toMatch(/<SuggestionsLane/);
    // Hidden when signed / readonly / empty — the lane is a READY-only,
    // unsigned-only surface.
    expect(readyView).toMatch(
      /\{!syntheticQaMode &&\s*!props\.readonly &&\s*!props\.signedAt &&\s*\(props\.suggestedClaims\?\.length \?\? 0\) > 0 &&/
    );
  });

  it('the lane carries the e2e hooks + the honest header', () => {
    expect(lane).toMatch(/data-testid="suggestions-lane"/);
    expect(lane).toMatch(/data-testid="suggestion-item"/);
    expect(lane).toMatch(/Suggested by AI — not stated in this visit/);
    // Adopt updates the editor in place + re-syncs the RSC payload.
    expect(lane).toMatch(/adoptSuggestionAction/);
    expect(lane).toMatch(/dismissSuggestionAction/);
    expect(lane).toMatch(/router\.refresh\(\)/);
  });

  it('the server actions exist, reject SIGNED, and audit with PHI-safe metadata', () => {
    expect(actions).toMatch(/export async function adoptSuggestionAction/);
    expect(actions).toMatch(/export async function dismissSuggestionAction/);
    // Read-only after signing.
    expect(actions).toMatch(/TranscribeVisitStatus\.SIGNED/);
    // Both audit rows exist…
    expect(actions).toMatch(/SUGGESTION_ADOPTED/);
    expect(actions).toMatch(/SUGGESTION_DISMISSED/);
    // …with metadata pinned to { section, reason, remaining } — NEVER the
    // claim text (PHI). The unit test asserts the exact runtime key-set;
    // this pins the source shape.
    expect(actions).toMatch(
      /metadata: \{\s*section: claim\.section,\s*reason: claim\.reason,\s*remaining: remaining\.length,?\s*\}/
    );
    expect(actions).not.toMatch(/metadata:[^}]*claim\.text/);
  });
});
