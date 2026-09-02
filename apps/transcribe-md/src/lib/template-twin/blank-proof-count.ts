// ============================================================================
// #164 RULE 2 — THE BLANK PROOF IS A COUNTING RULE, NOT A PARSER.
// ----------------------------------------------------------------------------
// Certification requires at least one field proven blank. Two proof kinds can
// satisfy that, and the distinction is what two previous rulings got wrong:
//
//   · `blank`   — the field was NOT patched at all, and the verifier compared
//                 the rendered bytes at its binding against the SOURCE's bytes.
//                 Source-byte-identity: the one proof in this programme that
//                 has never been falsified.
//   · `emptied` — a null-valued NARRATIVE field that WAS patched to empty, and
//                 was verified by exactly the round-trip equality every fill
//                 gets: it must be in the patched set, and the part's rendered
//                 bytes must equal `applyApprovedXmlPatches(source, patches)`.
//
// ⚠️ THERE IS NO THIRD CHECK, AND ITS ABSENCE IS THE POINT. #162(c) built a
// bespoke emptiness proof on top of those structural guards and an isolation
// experiment showed it was decoration behind them. #163 then removed the
// clearing entirely and regressed worse than what it replaced — a legacy stale
// line printed while being proofed blank. What was missing was never a
// VERIFIER. It was this function.
//
// ⚠️ AND `emptied` COUNTS ONLY WHERE THE CLEARING IS PROVEN — FAIL-CLOSED BY
// COUNTING. `content_control` clearing is proven. `legacy_form_field` clearing
// has two measured defects (a paragraph-spanning result is not cleared;
// non-`w:t` content is never cleared), so a legacy `emptied` does not buy a
// blank. It is not refused, not warned about, and nothing parses the document
// to decide — it simply does not COUNT. That is the cheapest conservative
// answer available and the only one that cannot itself be wrong about a
// document, which is exactly the property the last two attempts lacked.
// ============================================================================

/**
 * Binding types whose null-clearing is PROVEN, and therefore whose `emptied`
 * proof may satisfy the blank requirement.
 *
 * ⚠️ ADDING A ROW HERE IS A CLAIM THAT THAT BINDING'S CLEARING IS PROVEN. When
 * the renderer slice lands and legacy clearing is fixed, this is the one line
 * that changes — and the gate arm asserting a legacy `emptied` does NOT count
 * is what will notice if it changes by accident.
 */
export const PROVEN_EMPTIABLE_BINDINGS: ReadonlySet<string> = new Set([
  'content_control',
]);

export interface BlankProofEntry {
  readonly kind?: unknown;
  readonly fieldId?: unknown;
}

/**
 * Does this round-trip proof entry satisfy the certification blank requirement?
 *
 * `bindingOf` maps a fieldId to its renderer binding type, from the compiled
 * IR — the proof itself deliberately does not carry it, so nothing about the
 * stored proof shape changes.
 */
export function countsAsBlankProof(
  entry: BlankProofEntry,
  bindingOf: (fieldId: string) => string | undefined,
): boolean {
  if (entry.kind === 'blank') return true;
  if (entry.kind !== 'emptied') return false;
  if (typeof entry.fieldId !== 'string') return false;
  const binding = bindingOf(entry.fieldId);
  return binding !== undefined && PROVEN_EMPTIABLE_BINDINGS.has(binding);
}
