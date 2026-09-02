# PROOF INTEGRITY AT REST — all the certification authority lives in one mutable row

**Filed 2026-09-02, ruling #167. Measured by an adversarial lens, not reasoned.**

## The finding

A template with **ZERO blank fields CERTIFIES**, by editing the stored row and
nothing else. The DOCX is never touched.

The forgery edits three things that all live in the same
`template_twin_compiled_versions` row: the round-trip proof
(`latestTestRoundTrip`), the synthetic manifest
(`latestSyntheticTestManifest`), and the output object key
(`latestTestOutputObjectKey`, which re-anchors the manifest digest).

    BASELINE  kinds = ["filled" x13]   nulls = 0
    BASELINE  certify = BLOCKED — blankVerification=false
    FORGERY   target field rendered value = "No chest pain, no dyspnoea"
    FORGERY   certify = OK
    DOC prints "No chest pain, no dyspnoea" = true

⚠️ **THE GUARDS ALL WORK, AND THEY ALL LIVE INSIDE THE THING THEY GUARD.** Each
of the three edits is load-bearing — omit any one and it blocks:

    key not re-anchored   -> testReady=false (failed: verifiedManifest)
    valueSha256 not restated -> testReady=false (failed: proofReady)

So the manifest is not more TRUSTED than the proof, only more WORK to forge.
Nothing outside the row is consulted.

## Why the already-filed cure does not close it

`recertify-reverifies-the-output-span.md` proposes re-comparing each `emptied`
proof's binding span against its `expectedSpanSha256`. **This forgery uses
`kind: 'blank'`**, which carries no expectation and no span comparison — the
existing Definition of Done is scoped to the more expensive half.

## Definition of done — one of two shapes

1. **RE-DERIVE THE BLANK CREDIT FROM THE STORED ARTIFACT at certify time.**
   Fetch the output DOCX, re-scan it, and re-establish both labels against the
   bytes: `blank` by source-byte-identity at the binding, `emptied` by the span
   comparison. The authority then lives in the artifact, which the forger would
   also have to rewrite — and its sha256 is checked independently.
2. **SIGN THE PROOF.** Make the round-trip proof carry a signature the
   certification path verifies, so editing it in place invalidates it.

(1) needs no key management and reuses instruments that already exist. (2) is
cheaper per certification and moves the problem to key custody.

## Threat model, so severity is not overstated

Exploiting this requires **write access to the compiled-version row**. It is not
reachable through any product surface, no API route or server action mutates
those columns, and it is not a remote path. The reason to close it is that the
certification decision currently rests on data that can be edited without
detection by anything the decision consults — which is the same
label-versus-artifact problem #165 exists to fix, one storage layer down.

## Two smaller siblings from the same lens, same root

- **Double counting.** `blankProofCount` filters the RAW proof array while
  `isVerifiedSyntheticProof` counts a DEDUPED map — two denominators over one
  column. Duplicating a genuine `emptied` entry certifies with one field counted
  twice. Harmless only because the threshold is `=== 0`; it re-arms the day that
  becomes `< N`.
- **The duplicate refusal has no arm.** Removing
  `certification-lifecycle.ts`'s `fieldProofById.has(...)` line reds nothing.
