// ============================================================================
// OWNER FINDING (blocking) — THE EXPORT SURFACE IS NEVER HIDDEN.
// ----------------------------------------------------------------------------
// A blocked or failed twin fill returned a BARE miss, and a bare miss makes
// `VisitDocumentSurface` render nothing and step aside to the chromeless SOAP
// editor — so a certified Operative Note visit showed the note with NO PDF/Word
// export at all. The fix DEGRADES those outcomes to the styled document (the
// same paginated surface, the same export the doctor would download) and speaks
// the reason beside it.
//
// The action cannot be unit-mounted (it pulls next-auth + the fill engine), so
// this pins the contract at the SOURCE — the same technique
// `gate-actionable-miss-is-spoken` uses on this very surface — with a
// non-vacuity arm so it can always see its own subject. The rendered behaviour
// is exercised end-to-end in tests/e2e/scenarios/visit-document.spec.ts, and
// that every new miss SPEAKS is enforced by the spoken-miss gate.
// ============================================================================
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

const ACTION = readFileSync(
  join(__dirname, '..', '..', '..', '..', 'actions', 'preview-visit-document.ts'),
  'utf8',
);
const SURFACE = readFileSync(
  join(__dirname, '..', 'visit-document-surface.tsx'),
  'utf8',
);

// The three certified-path outcomes that used to hide the surface. Each must
// now reach `styledDocument(...)`, and NONE may be returned as a bare `miss()`.
// (`no_render` is deliberately NOT in this list: it survives as a real miss for
// styledDocument's own build failure and the browser's draw failure.)
const DEGRADED = ['native_fill_blocked', 'fill_failed', 'no_tenant_template'] as const;

describe('a blocked/failed fill degrades to the styled document, never a hidden surface', () => {
  it('NON-VACUITY — the gate can see its subjects', () => {
    expect(ACTION).toContain('previewVisitDocumentAction');
    expect(ACTION).toContain('styledDocument(');
    expect(SURFACE).toContain('styledReasonText');
  });

  it.each(DEGRADED)('%s is DEGRADED to styledDocument, not returned as a bare miss', (reason) => {
    // Reaches styledDocument (the reason travels as its 4th argument, within a
    // few lines of the call).
    expect(
      new RegExp(`styledDocument\\([\\s\\S]{0,160}?'${reason}'`).test(ACTION),
      `${reason} must be handed to styledDocument so the document still renders`,
    ).toBe(true);
    // And is never a bare miss — a bare miss is exactly what hid the surface.
    expect(
      new RegExp(`miss\\(\\s*['"]${reason}['"]`).test(ACTION),
      `${reason} must not be returned as miss() — that hides the export surface`,
    ).toBe(false);
  });

  it('the withheld-render branch no longer returns miss(no_render)', () => {
    // The owner's exact case: `!prepared.render?.document` (a BLOCKING validation
    // issue withholds the native page). It degraded to a miss; it must now hand
    // 'native_fill_blocked' to styledDocument.
    const branch = ACTION.match(/!prepared\.render\?\.document[\s\S]{0,600}/)?.[0] ?? '';
    expect(branch, 'the withheld-render branch was not found').not.toBe('');
    expect(branch).toContain('styledDocument(');
    expect(branch).toContain('native_fill_blocked');
    expect(branch).not.toMatch(/miss\(\s*['"]no_render['"]/);
  });

  it('the degrade reason SURVIVES the Word toggle / a down converter', () => {
    // Adversarial finding: in Word mode converted={pdf:null,reason:null} and a
    // down converter yields a reason with no doctor text, so `reason:
    // converted.reason` alone dropped the passed degrade note -> the surface
    // showed the wrong "set up a form" hint. The docx_fallback branch must keep
    // the note.
    expect(ACTION).toContain('reason: note ?? converted.reason');
    expect(ACTION).not.toMatch(/kind: 'docx_fallback',[\s\S]{0,80}?reason: converted\.reason,[\s\S]{0,80}?fillSha: `styled:/);
  });

  it('the surface does not speak the reason twice (no empty/duplicate figcaption)', () => {
    // When the toolbar shows the styled reason, NativeDocumentPreview must not
    // also render it (or an empty status line for a reason it has no text for).
    expect(SURFACE).toContain('reason={styledReasonText ? null : result.reason}');
  });

  it('the surface SPEAKS the reason on a rendered styled document', () => {
    // On the ok:true styled path `onUnavailable` never fires, so the caller's
    // miss line never draws — the surface is the only place left to say why this
    // is the styled layout. It reads the reason it already holds.
    expect(SURFACE).toContain('visitDocumentMissText(result.reason)');
    expect(SURFACE).toContain('visit-document-styled-reason');
    // The generic "no form yet" hint still stands for the genuine no-form case
    // (reason === null), which the e2e pins.
    expect(SURFACE).toContain('visit-document-styled-note');
  });
});
