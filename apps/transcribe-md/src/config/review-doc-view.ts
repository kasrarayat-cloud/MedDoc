// ============================================================================
// Pre-sign review as ONE document — flag. Build-time, fail-closed, DEFAULT OFF.
// ----------------------------------------------------------------------------
// Extends the established skin-flag pattern (config/skin-beta.ts,
// config/ux-simplify.ts). UX simplification pack (B) linearised the SIGNED
// visit and deliberately stopped there:
//
//   "UNSIGNED review is untouched — the tabbed sign-gate workspace stays
//    exactly as-is, because that is where the gates live and they are frozen."
//
// This flag is the other half, and it takes that sentence seriously. The gates
// are not moved, weakened, or re-implemented: they are SURFACED. Today a
// blocker can sit behind an unvisited tab; here every one of them renders in
// the document, at the position it belongs to, and the doctor cannot reach the
// sign action without having scrolled past it.
//
// When ON, an UNSIGNED review renders as the filled document:
//   • the note top-to-bottom, one column, reading layout
//   • each verifier-demoted claim IN PLACE as its proposed text — softly
//     highlighted, "suggested — tap to accept" — instead of a bracket
//     placeholder in the note and a separate lane below it
//   • critical-Rx and E/M as individual inline cards at their natural position
//   • one pinned bottom bar: "N suggestions remaining" until every suggestion
//     has been rendered on screen IN FULL, then "Accept remaining · Sign"
//   • codes + billing as one slim read-only row, Rx row only on a warning,
//     dictation behind a small link, no tab strip
//
// SKIN/FLOW-ONLY CONTRACT — nothing behind this flag modifies:
//   • the anchored-generation verifier (04b) or what it demotes
//   • adoptSuggestionAction / dismissSuggestionAction — same actions, same
//     payloads, same per-claim identity check; bulk-accept is a loop over the
//     SAME per-claim call, so the audit records individual adoptions exactly
//     as it does today
//   • the critical-Rx override gate (RxWarningsRail → OverrideConfirmModal →
//     recordOverride) — rendered inline, unchanged, one card per warning,
//     never bulk-able
//   • the E/M confirm-before-sign gate — SignAndSendModal keeps its own
//     confirmation and remains the enforcement; the inline card is an
//     ADDITIONAL visible blocker in front of it, never a replacement
//   • POST /api/visits/[id]/sign (the sole SIGNED-writer) or the export routes
//   • audit logging or auth
//
// Rollback: unset NEXT_PUBLIC_REVIEW_DOC_VIEW (or set it to anything but
// 'true') and rebuild. Both branches are in the bundle; OFF renders the
// existing ReviewTabsV2 workspace byte-for-byte.
// ============================================================================

export function isReviewDocView(): boolean {
  return process.env.NEXT_PUBLIC_REVIEW_DOC_VIEW === 'true';
}

export const REVIEW_DOC_VIEW_FLAG = 'NEXT_PUBLIC_REVIEW_DOC_VIEW';
