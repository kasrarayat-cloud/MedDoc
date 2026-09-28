# Document source relationships — 2026-09-28

Candidate work only; production and the original files are unchanged. This is
development evidence on authorized D30, not corpus or native Word qualification.

The integrated `9f2bdad0` baseline maps 62 fields but misses four of the 62
independently identified answer areas and creates four extra guidance fields.
The repaired detector maps 61 expected areas without extras: the separate Other
box retains its complete question/options, the follow-up question retains its
exact preceding question and both source fingerprints, and the line-manager box
is explicitly protected. Fixed contact/guidance introductions and the annex
heading are no longer answer fields. Existing mappings are not regenerated.

**D30 still fails the whole-document gate.** Its plain accommodation bullets do
not declare selection cardinality; this repair does not invent it. Patient-author
scope and document-review attestation remain a separate clinical/source-contract
follow-up. An author-protected field is not counted as an automatically completed
answer. Full ordinary/long authenticated workflow and rendered/native acceptance
remain outstanding on the final combined candidate.

The independent finished-diff pass found four concrete defects in the initial
patch. Root replay confirmed all four. The repaired implementation retains an
explicit conditional clinical choice, re-derives question ownership before an
export, propagates author protection into Other boxes, and protects existing
author statements even against a forged writable mapping. The same independent
probes now report no demonstrated wrong outputs. Both results remain here.

Validation: 60 affected engine checks pass without skips or expected failures.
The new controls were also run against the old engine: five assertions failed
and two expected destination lookups failed because those fields were absent.
These are preserved first results, not newly labelled expected failures.
Missing/ordinary/long deterministic A35 exports using the old 62-field mapping
are byte-identical before/after. This does not establish ordinary-model or
full-document success. Original hashes, baseline map and destination trace stay
in the private runtime path recorded by the manifest; no filled file is tracked.
