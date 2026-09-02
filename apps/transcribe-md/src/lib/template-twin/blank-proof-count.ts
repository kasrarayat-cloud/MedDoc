// ============================================================================
// #165 — THE BLANK PROOF COUNTS TWO KINDS, AND `emptied` IS EARNED BY THE WRITE.
// ----------------------------------------------------------------------------
// Certification requires at least one field proven blank. Two proof kinds
// satisfy that:
//
//   · `blank`   — the field was NOT patched at all, and the verifier compared
//                 the rendered bytes at its binding against the SOURCE's bytes.
//                 Source-byte-identity: the one proof in this programme that
//                 has never been falsified.
//   · `emptied` — the field WAS patched, by WHOLE-SUBTREE REPLACEMENT of its
//                 `w:sdtContent`, and the output at that binding is
//                 byte-identical to what the writer recorded it would leave
//                 (`expectedSpanSha256`).
//
// ⚠️ WHY IT TOOK FOUR ATTEMPTS, BECAUSE THE PATTERN IS THE LESSON. #162(c),
// #163 and #164 each tried to establish emptiness by READING the output —
// "does it contain a `w:t`", "walk separate→end", "is the region free of [list
// of visible elements]", "count the label". Each was falsified by the next
// carrier nobody enumerated: `w:sym`, `w:pict`, `w:drawing`, `w:object`,
// `w:delText`, `w:instrText`. The list never closes, so the instrument was
// never going to converge.
//
// #165 stops reading and makes the WRITE correct instead. The boundary is the
// control's own element, so nothing inside it can survive; and the proof is a
// comparison against bytes we wrote, which is the one instrument that was never
// falsified. Neither half suffices alone — byte-equality on its own is
// writer-blind, and a correct write with no proof is an assertion.
//
// ⚠️ AND `emptied` STILL COUNTS ONLY FOR BINDINGS WITH A BOUNDED CONTAINER.
// That is now a SECOND lock rather than the only one: the renderer refuses to
// label anything `emptied` unless it actually performed the whole-subtree
// replacement, so this set cannot admit a binding the writer never cleared.
// It is kept because it is where `table_cell` will be added when its `w:tc`
// gets the same treatment, and it fails closed if the two ever disagree.
// ============================================================================

/**
 * Binding types cleared by WHOLE-SUBTREE REPLACEMENT of a bounded container,
 * and therefore whose `emptied` proof may satisfy the blank requirement.
 *
 * ⚠️ ADDING A ROW HERE IS A CLAIM THAT THAT BINDING HAS SUCH A CONTAINER AND
 * THAT THE RENDERER USES IT. `table_cell` has one (`w:tc`) and is the next
 * candidate; `legacy_form_field` has NONE — its result is a span between two
 * `fldChar`s, which is precisely why every attempt to bound it by walking was
 * falsified — so it cannot join this set until its slice gives it a real
 * container.
 */
export const PROVEN_EMPTIABLE_BINDINGS: ReadonlySet<string> = new Set([
  'content_control',
]);

export interface BlankProofEntry {
  readonly kind?: unknown;
  readonly fieldId?: unknown;
  readonly expectedSpanSha256?: unknown;
}

/** A sha256 as the renderer writes it: 64 lowercase hex characters. */
const SHA256_HEX = /^[0-9a-f]{64}$/;

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
  resolvedNull: (fieldId: string) => boolean,
): boolean {
  if (entry.kind !== 'blank' && entry.kind !== 'emptied') return false;
  if (typeof entry.fieldId !== 'string') return false;

  // ⚠️ THE STRONGEST READ-PATH CHECK AVAILABLE, AND THE GATE ALREADY HELD THE
  // DATA FOR IT — WHICH IS WHY THIS COSTS NOTHING.
  //
  // Both labels are claims that the encounter said NOTHING about this field. So
  // cross-check the claim against the synthetic manifest, which records what the
  // encounter actually resolved. A field the manifest says was FILLED cannot
  // honestly be blank or emptied, whatever its stored label says.
  //
  // ⚠️ IT CLOSES A CHEAPER FORGERY THAN THE ONE THE EXPECTATION CHECK CLOSED,
  // AND THE PASS FOUND IT BY GOING ROUND THE SIDE. `blank` had NO read-path
  // check at all — no binding, no expectation, nothing — so relabelling one
  // genuinely-filled entry to `blank` certified a template outright. Measured:
  // a field whose rendered value was "Bilateral leg heaviness", relabelled
  // `blank`, produced CERTIFIED. Guarding only `emptied` was guarding the door
  // the previous finding happened to come through.
  //
  // It also kills the forged-`emptied`-on-a-filled-field case that a
  // well-formed but meaningless hash (`deadbeef` x8) otherwise walked straight
  // past, because shape was all the expectation check could judge.
  if (!resolvedNull(entry.fieldId)) return false;

  if (entry.kind === 'blank') return true;
  // ⚠️ THE EXPECTATION IS REQUIRED HERE TOO, NOT ONLY AT RENDER TIME — and this
  // line exists because the adversarial pass MEASURED its absence.
  //
  // The renderer's type system cannot construct an `emptied` proof without an
  // expectation, and the verifier refuses one that lacks it. But THIS function
  // reads a proof back out of the `latest_test_round_trip` JSON column, where no
  // compiler and no verifier was present — and `isVerifiedSyntheticProof`, the
  // gate that decides whether a stored proof is trustworthy, compares exactly
  // five properties (`status`, `partName`, `bindingPath`, `valueSha256`,
  // `occurrences`) and reads `kind` and `expectedSpanSha256` ZERO times.
  //
  // Measured: relabelling the genuine `emptied` entries to `filled` and forging
  // one `filled` into `emptied` with `expectedSpanSha256` deleted still certified.
  // That is the label-versus-write defect #165 exists to kill, reappearing one
  // boundary down at persistence.
  //
  // ⚠️ HONEST LIMIT, STATED SO NOBODY READS THIS AS MORE THAN IT IS. This
  // refuses a stored label that could NOT have come from the real writer. It
  // does NOT re-verify the document: a forger who also supplies a plausible
  // 64-hex string still passes here. Closing that requires re-fetching the
  // output artifact and re-comparing the span at certification time — filed as
  // `docs/backlog/recertify-reverifies-the-output-span.md`, not done here.
  if (typeof entry.expectedSpanSha256 !== 'string' || !SHA256_HEX.test(entry.expectedSpanSha256)) {
    return false;
  }
  const binding = bindingOf(entry.fieldId);
  return binding !== undefined && PROVEN_EMPTIABLE_BINDINGS.has(binding);
}
