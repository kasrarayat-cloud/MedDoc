# CERTIFICATION SHOULD RE-VERIFY THE OUTPUT SPAN, NOT JUST THE STORED LABEL

**Filed 2026-09-02, ruling #165. Found by the finished-diff adversarial pass, on
#165's own change, and MEASURED rather than reasoned.**

## The gap

`certifyAndActivateTemplateTwin` reads the round-trip proof back from the
`latest_test_round_trip` JSON column and gates on `isVerifiedSyntheticProof`.
That function compares exactly five per-field properties — `status`, `partName`,
`bindingPath`, `valueSha256`, `occurrences` — and reads `kind` and
`expectedSha256` **zero** times.

So the two fields that decide *whether a clearing actually happened* are the two
nobody re-checks at the point of use.

**Measured:** relabelling the genuine `emptied` entries to `filled`, and forging
one `filled` entry into `emptied` with `expectedSha256` deleted, still produced
`CERTIFIED`.

⚠️ **THIS IS #165's OWN DEFECT SHAPE, ONE BOUNDARY DOWN.** #164 counted a label
the writer had not earned. #165 makes the renderer earn it — and then the
certification path trusts the label read from a database where no renderer ran.

## What was done now, and what it does not buy

`countsAsBlankProof` refuses an `emptied` entry that does not carry a
well-formed 64-hex `expectedSha256` (`blank-proof-count.ts`). That closes the
measured case: a stored label that could not have come from the real writer.

**It does NOT re-verify the document.** A forger who also supplies a plausible
hex string passes it. The check proves the proof is well-formed, never that it
is true.

## Definition of done

Re-fetch the stored output artifact at certification time, re-scan the part, and
re-compare each `emptied` proof's binding span against its `expectedSha256` —
the same single comparison the renderer's verifier already performs, moved to
the read path where the trust decision is actually made.

Cost: one object fetch and one XML scan per certification, which happens once per
template version.

## Threat-model note, so severity is not overstated

Exploiting the remaining gap requires **write access to the
`latest_test_round_trip` column**. It is not a remote path and not reachable
through the product's own surfaces. The reason to close it is that the persisted
proof is not self-consistent — a proof that cannot be checked where it is used
is the exact thing this programme keeps paying for.
