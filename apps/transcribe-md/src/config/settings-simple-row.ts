// ============================================================================
// Settings › My Note Format — the simple row. Build-time, fail-closed, OFF.
// ----------------------------------------------------------------------------
// UX simplification (A) already made the UPLOAD do everything: activate,
// certify for native export, set form-only, preview once. What it could not
// reach was rows that existed BEFORE it — those still carry the old ritual:
//
//     "Exports use a styled re-creation. Finish setup to fill your own form
//      instead."          [ Set up native export ]
//
// A doctor who uploaded their form months ago is told, on a settings page they
// did not come to for this, that the thing they already did is unfinished, and
// handed a second upload to do it again. There is nothing for them to decide
// here: we have their template, and whether we can fill their own page is our
// problem, not a task to delegate back to them.
//
// So flag ON:
//   • the CTA and the setup prose are GONE — permanently, not hidden behind a
//     condition. Absorption runs automatically when the page opens.
//   • the row is: name · Active · Replace · Delete. Everything else (the full
//     review editor, duplicate) moves behind an overflow menu.
//   • a failure is a one-line status ON the row, in the doctor's language, not
//     a call to action. "Exports use a styled copy" is a fact they may want to
//     know; it is not a job.
//
// SKIN/FLOW-ONLY. Nothing here changes what certification requires, what the
// verifier demotes, what the sign route enforces, or what is audited. It
// changes which of those a doctor is asked to think about.
//
// Rollback: unset NEXT_PUBLIC_SETTINGS_SIMPLE_ROW (or set it to anything but
// 'true') and rebuild.
// ============================================================================

export function isSettingsSimpleRow(): boolean {
  return process.env.NEXT_PUBLIC_SETTINGS_SIMPLE_ROW === 'true';
}

export const SETTINGS_SIMPLE_ROW_FLAG = 'NEXT_PUBLIC_SETTINGS_SIMPLE_ROW';
