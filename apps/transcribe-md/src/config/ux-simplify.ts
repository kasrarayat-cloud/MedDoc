// ============================================================================
// UX simplification pack — flag. Build-time, fail-closed, DEFAULT OFF.
// ----------------------------------------------------------------------------
// Extends the established skin-flag pattern (see config/skin-beta.ts). When OFF
// (production today), both surfaces render byte-for-byte what they render now.
// When ON:
//
//   A. Settings › My Note Format — a form upload becomes
//        pick file → staged processing → ONE confirm card → done
//      instead of  pick file → spinner → full review editor → save → activate
//      → (separately) "Set up native export" → (separately) form-only toggle.
//      The full review editor is NOT deleted: it is demoted to an Advanced
//      escape hatch behind "Something's off".
//
//   B. A SIGNED visit renders as one scrolling document instead of the
//      Note/Rx/Billing/Codes/Extras/Input tab strip. UNSIGNED review is
//      untouched — the tabbed sign-gate workspace stays exactly as-is,
//      because that is where the gates live and they are frozen.
//
// SKIN/FLOW-ONLY CONTRACT — this flag gates ONLY presentation and the ORDER of
// calls to server actions that already exist. Nothing behind it modifies:
//   • the note-template PARSE backend (parseNoteTemplateAction and its PHI gate)
//   • the anchored-generation verifier (04b)
//   • the critical-Rx override gate or the E/M confirm-before-sign gate
//   • POST /api/visits/[id]/sign  (the sole SIGNED-writer)
//   • audit logging (audit.ts) or auth config
// The confirm card calls the SAME saveNoteTemplateAction + certifyPdfTemplateAction
// the existing UI calls, in the same order, with the same payloads.
//
// Rollback: unset NEXT_PUBLIC_UX_SIMPLIFY (or set it to anything but 'true')
// and rebuild. Because it is a NEXT_PUBLIC_* build-time constant, both branches
// are in the bundle and tree-shaking keeps the inactive one off the hot path.
// ============================================================================

export function isUxSimplify(): boolean {
  return process.env.NEXT_PUBLIC_UX_SIMPLIFY === 'true';
}

export const UX_SIMPLIFY_FLAG = 'NEXT_PUBLIC_UX_SIMPLIFY';
