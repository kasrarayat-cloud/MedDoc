# Finished clinical diff refutation: source 6580593

Reviewer: Astra, `/root/word_recovery`. Read-only source worktree `/opt/meddoc-pro/.worktrees/v1-ordinary-context`; source commit `6580593899eb7931fedea9fccaf38c233e0d3625`. Exact `rebuild/core/generation.py` SHA-256 before and after probes: `166947914409a575269c2bd5e174bdc62b2ae73239ab0754900b85d32c84c24f`.

## One demonstrated introduced regression: unresolved repeated source disappears from the ambiguity check

`generation.py:2167-2172` marks an unsupported subject prefix unresolved and leaves its subject unset. At `generation.py:2202`, `v3_related_source_blocks` skips every block with no owner before examining its text for literal actual-label references. This removes that block both from the repeated-source check at lines 2178-2184 and from the continuation exception's required no-other-reference check at lines 2221-2222.

Exact synthetic input:

```
Current medications are aspirin daily.

Patient medications are warfarin.

Plan: continue current medications.
```

The simulated provider selects the first unit for the unique Medications text field and the third unit for Plan. Candidate output:

- Medications: `supported`, `Current medications are aspirin daily.`
- Plan: `supported`, `continue current medications.`
- Both ordinary reviewed answers and separately forced stored supported answers produce `[]` from the shared finalization decision reader. The page reader likewise retains supported answers.

The second medication statement is omitted without visible review. It uses the literal actual form label, so recognizing this reference does not require a medical synonym or contradiction classifier. The candidate already recognizes it as an unresolved medication statement when that unit itself is selected; ignoring it when another medication unit is selected is the inconsistency.

Exact refuted prior candidate `1747bb2dbce6a8799af08c477164e2ac0d5a5976` holds Medications as conflict with blank text and rejects the forced stored Medications answer. Thus this is introduced by the latest ownership narrowing. Original base `ebcddc2a0fc09630ab96c62ef84028f3c567cf03` also passed this separated-paragraph case; the latest candidate reintroduces a behavior that 1747's repeated-source guard had closed. Plan itself passes on all three revisions; the introduced regression is the medication answer and its shared stored governance.

Related demonstrations of the same incomplete watched set replace the middle statement with `A medication was discontinued.` or `Warfarin is another medication.` Both medication and Plan answers remain supported. These also pass the original base and 1747, so they are residual gaps in the newly stated single-safe-referent/no-other-reference claim, not newly introduced behavior. Preserve this distinction.

Next safe action: retain unresolved and unowned literal target references in the context/ambiguity decision, without assigning them a write destination or broadening the owner prefix grammar; retain the positive exact continuation when no such extra reference exists. Root must independently verify this finding before treating it as accepted.

## Existing findings closed on this exact source

The retained sibling, donor, future examination, allergy negation, probable allergy and questioned treatment examples are all held during generation. A crafted stored supported answer is also held by the page reader and rejected by `governed_decisions`. The positive complete conditional Plan remains supported.

Missing and repeated recognized medication sources, an explicit continuation modifier and an instruction-shaped continuation remain held. The exact positive continuation retains the complete medication statement and Plan text. `No current medications are recorded.` remains intact. The retained authorized synthetic `r1-note9` example produces all seven supported answers with their original wording, including both drug doses, and has no finalization refusals.

## Remaining union scope observation

`Medications are warfarin for the donor.` and `Examination is scheduled for Friday.` become supported after ordinary unrelated labelled context on both 1747 and this candidate. They go through existing `tab_source_value` ownership and bypass the new source-prefix check at line 2157. Original base generation held them, while its forced stored reader did not. These are not introduced by the latest 1747-to-658 delta and are retained in the probe output as limits on a broad claim that all foreign/future ownership is now handled. The narrowly implemented prefix repair does close the exact earlier examples. No general clinical semantic qualification is claimed.

## Bounded method and evidence

`probe.py` exercises 21 predefined synthetic cases on the finished source and exact preserved sources for the original base and 1747. The source-unit selection, deterministic adoption, page governance and stored-answer decision readers run directly. No database transport, provider call, app mutation, unseen corpus read, native Word step or broad suite was used. The Django configuration uses managed environment, a synthetic key/password and an unreachable database port 1. All raw outputs are retained:

- `candidate.json`: source 6580593.
- `base.json`: original base, executed from the previously retained `generation-base.py`.
- `prior1747.json`: refuted prior, executed from `generation-1747.py`.
- `generation-658.py`: exact reviewed source snapshot.

Each output records disk and executed override hashes separately; an override run's disk hash is not the executed-source identity. No candidate source was edited. All probes completed with exit 0 and no running probe remains.

Reproduce the candidate from any directory:

```
/opt/meddoc-pro/.worktrees/v1-ordinary-context/rebuild/.venv/bin/python \
 /opt/meddoc-pro/.worktrees/v1-host-readiness/rebuild/.runtime/ordinary-context-refutation-20260927/final658/probe.py
```

No additional introduced loss of wording or generation/page/stored-decision divergence was demonstrated within these bounded cases. B-G1 and broader clinical qualification remain open; this report is not a release approval.
