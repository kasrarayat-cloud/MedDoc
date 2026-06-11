// ============================================================================
// READY-view review banner — structural pin (2026-06-11 L6-gate prod smoke).
// ----------------------------------------------------------------------------
// The smoke found the pipeline review flag (fabrication-gate rejection,
// unfixable critique criticals, 02.8 allergy-conflict) was written to the DB
// but NEVER rendered on READY visits — the doctor saw a bare "Needs review"
// pill with no reason. These source-level assertions (same pattern as
// admin-gate-coverage / auth-schemas) pin the wire-through so a refactor
// can't silently disconnect it again. The live rendering itself is verified
// by the prod smoke; this is the cheap CI tripwire.
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

describe('READY-view review banner wiring', () => {
  it('page.tsx passes needsReview + reviewReason into VisitReadyView', () => {
    const invocation = page.slice(page.indexOf('<VisitReadyView'));
    expect(invocation).toMatch(/needsReview=\{props\.needsReview\}/);
    expect(invocation).toMatch(/reviewReason=\{props\.reviewReason\}/);
  });

  it('VisitReadyView declares the props and renders the banner conditionally', () => {
    expect(readyView).toMatch(/needsReview\?: boolean/);
    expect(readyView).toMatch(/reviewReason\?: string \| null/);
    expect(readyView).toMatch(/data-testid="review-reason-banner"/);
    // Suppressed once signed — the doctor has reviewed by definition.
    expect(readyView).toMatch(
      /props\.needsReview && props\.reviewReason && !props\.signedAt/
    );
  });
});
