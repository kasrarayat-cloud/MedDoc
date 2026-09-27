# Independent clinical union refutation — 2026-09-27

**REFUTED: one union-introduced scope failure, plus an existing Unicode guard gap.**
No implementation changes were made. Root received the concrete inputs before
this report and independently reproduced the two primary union failures.

## Exact subject and method

- Union: `aa4e8c0d0c0f935bdc35012263e5881bbd703ace`.
- First parent: `11d075646b28dfd52df89cbfdbd9551d314ba358`.
- Second parent: `0557b6bde225ab456d8a2d9fde840f58153c4d59`.
- Union `rebuild/core/generation.py` SHA-256:
  `923439aed9bde6eba34a26bf551b2d583a247a6bec7ba00e8679b2632d6c6f41`.

Thirty bounded synthetic configurations were preserved and run against all
three exact source versions: 24 exploratory configurations and six minimal
verifications, **90 version runs, zero probe errors**. These exercised source
selection validation, adoption, page governance, and the pure
`governed_decisions` function. No full application finalization was run.
Shared pure helper identities match across both parents and the union.

The probes disabled socket/process operations and configured no database.
There were zero forbidden-operation attempts. No provider, Word document,
render, corpus original, prior map, qualification content, or unfinished
`v1-patient-topics` diff was accessed. No full suite was run.

## F1 — P1: a nominal Plan releases the new source subject past its correction

Source: `aa4e8c0d:rebuild/core/generation.py:2472`, `:2481`, `:2499`,
`:2588`, `:2627`; new ownership at `:2203` and `:2220`.

Exact input, unique unscoped text fields `Allergies`, `Examination`, `Plan`:

```text
No known drug allergies.
Plan: removal of erroneous NKA entry.
```

Select **only the first complete source unit for Allergies**. Plan is unselected
and remains missing. The union emits:

```json
{"status":"supported","text":"No known drug allergies.","evidence":[{"quote":"No known drug allergies.","start":0,"end":24}]}
```

The note calls that NKA entry erroneous and requests its removal. It must remain
under review instead of becoming a ready answer. A forced existing `supported`
answer with the same exact evidence also stays `supported` in page governance;
`governed_supported` returns `null` and `governed_decisions` returns `[]`.

| Version | Generated affected answer | Page reader | Finalization governance labels |
| --- | --- | --- | --- |
| First parent | conflict, empty text | conflict | `Allergies` |
| Second parent | conflict, empty text | conflict | `Allergies` |
| Union | supported, exact NKA text | supported | none |

Two independently preserved one-selection variants show the same new failure:

```text
Neurological examination is normal.
Plan: deletion of erroneous normal neurological entry.
```

```text
Heart and lung examination was normal.
Plan: deletion of inaccurate cardiopulmonary entry.
```

For each, selecting only the first unit for `Examination` yields supported exact
text and no stored-answer governance warning in the union. Both parents hold
the same answer in generation and both stored readers.

The nominal Plan passes the bounded keyword veto and becomes a safe source
boundary. The new subject establishes a complete earlier block, so `after`
suppresses the following-unit warning. Literal reference coupling at `:2253`
and `:2263` recognizes the form label, but not NKA or the new anatomical subject
wording. Positive diagnostic control: changing the first Plan to
`Plan: removal of erroneous allergies entry.` holds on all three versions.
This failure therefore does not depend on a provider selecting the Plan or on
malformed evidence. Evidence: cases03/07/08 and minimal V01–V04.

The preserved exploration also contains case05,
`No known drug allergies.\nPlan: penicillin avoidance for documented anaphylaxis.`
Both parents hold NKA; the union supports it without a stored-reader warning.
This is a clinical relationship beyond literal label matching and is not
automatically resolved by a record-retraction vocabulary change. It was sent
to the repair owner separately as an observed semantic contradiction residual;
no claim that such a change closes it is made here.

## F2 — P1, already in the second parent: compatibility spelling bypasses guards

Source: `aa4e8c0d:rebuild/core/generation.py:2223`, `:2494`, `:2501`,
and the correction collection in `governance_for`. These paths use raw and
invisible-stripped readings without the NFKC veto applied to plain/nominal
values. A finite narrative can bypass that nominal veto.

```text
No known drug allergies.
Plan: ａｃｔｕａｌｌｙ there is a penicillin reaction.
```

Union and second parent support the exact NKA declaration; page governance
leaves it supported and finalization governance returns no labels. The first
parent holds it. Replacing fullwidth `ａｃｔｕａｌｌｙ` with ASCII `actually` holds
on all three versions. V05/V06 reproduce this with only Allergies selected.

Two further preserved cases have the same existing gap:

- Case13: `Neurological examination is normal for her ｍｏｔｈｅｒ.\nNo known drug allergies.`
  Both Examination and Allergies become supported, with no stored-reader hold,
  in union and second parent. ASCII `mother` holds both (case14).
- Case23: `Neurological examination is normal.\nPlan: ａｃｔｕａｌｌｙ focal weakness is present.`
  The examination becomes supported with no stored-reader hold in union and
  second parent. The first parent holds it.

These are existing second-parent defects, **not newly attributed to the merge**.

## Bounds and evidence

Sampled ASCII/fullwidth/invisible nominal denial controls remained held. The
extra-source nonsmoker controls, malformed/subspan stored evidence, repeated
NKA, and scoped destinations did not yield an additional union failure in these
probes. This is bounded refutation, not a completeness or qualification claim.

Private runtime:
`/opt/meddoc-pro/rebuild/.runtime/v1-word-corpus/custodian-20260927/clinical-union-aa4e8c0d-20260927/`.
Every case, source snapshot, raw result, comparison and probe is retained there.
The append-only custody delta seal is
`metadata/057-CLINICAL-UNION-REFUTATION-DELTA-SEAL.json` under the custody root.

| Artifact | SHA-256 |
| --- | --- |
| `predeclared-cases.json` | `551e787a5da1a1200cc4cf5b351606e39b40cd61005c193936e853d3d9fba037` |
| `union-results.json` | `839fb9d4321fe2eed2a7298eecc8db58c7a7a306689680304bf23bca4d8878fc` |
| `parent1-results.json` | `eda2d4e815a0a852fa30ab698cb1a5e2d7af7067dfa547fe8f9c9425b4939272` |
| `parent2-results.json` | `512547e0ca41cf535f9224a15d3b19f793d62a3cefca86916656a642eab2d36e` |
| `minimal-verification-results.json` | `17fb90a000ffd76c9428dc067eccab2235501e2d4f20320bd7522bf0114cdb35` |
| `verification-summary.json` | `e2f0e36b9e076bb98aa7af33179c3d1d7b325475a6ab06e0cb765629c4700eea` |
