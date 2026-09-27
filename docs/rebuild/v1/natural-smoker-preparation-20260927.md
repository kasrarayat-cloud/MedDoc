# Exact current-patient nonsmoker option — bounded preparation

**Draft preparation; independent finished-diff refutation pending.** Worktree
`/opt/meddoc-pro/.worktrees/v1-natural-smoker`, branch `v1/natural-smoker`, base
`90808d5a3032286bedd9be2961dcabb6480a0358`. No release edits or deployment.

## Exact supported boundary

The v3 option reader now supports one ordinary, unlabelled source statement:
`The patient is a nonsmoker.` or `Patient is a nonsmoker.` The entire note,
except surrounding whitespace, must be this one complete statement. Its one
exact evidence span is retained unchanged. Only a unique literal **Smoker**
choice field, with no structural context and exactly **Yes / No** printed options,
can convert it to the literal **No** option. This records current smoking state;
it does not assert never-smoking or reconstruct a smoking history.

This is deliberately not a clinical synonym mapper. Other casing, hyphenated
wording, pronouns, former/never-smoker formulations, temporal modifiers, questions,
negations, extra statements, extra options and contextual/repeated destinations
are not admitted by this relation. They remain visible for review. The existing
labelled-option path remains available, but labels are not required for this
specific ordinary positive.

Only already-supported candidates reach conversion. Held candidates and suggestions
are not promoted. Source-topic segmentation, ownership, patient/relative rules and
all previous source guards remain. The separate helper contains this contract;
`v3_option_answer` invokes it, and a small shared `judged_context` hook enforces the
same full-note proof on stored choice evidence before page/save/finalization.
No prompt, model profile, pricing, schema or historical record was changed.

**Retained note4 is not fixed.** Its `She is a nonsmoker.` remains held because the
pronoun and surrounding source block have no reviewed ownership relationship for
this conversion. No sentence was rewritten to substitute Patient for She. The
historical **22 supported / 77 selected** result and every original selection stay
unchanged. B-G1 remains open; this limited relation is not general ordinary-note
compatibility or a new corpus result.

## Refutation and finite checks

All inputs and wallets were synthetic. Workflow network connections were denied;
Anthropic SDK responses were explicitly mocked. No actual model request, tokenizer
call, patient data, purchase or real financial operation occurred.

| Evidence | Result |
|---|---|
| `01-red.log` | Before implementation, two selected tests produced three failing assertions: both literal patient wordings and the full worker workflow were held. |
| `02-focused.log` | 11 checks passed after the first bridge: 9 new plus 2 existing workflow tests imported by discovery. |
| `03-stored-opposite-probe.json`, `stored_opposite_probe.py` | A directly constructed stored No with exact nonsmoker evidence and a blank-paragraph opposing statement remained supported under the previous reader. Root independently reproduced it before the hook. |
| `04-final-focused.log` | First shared-guard candidate passed 12 checks. This run is not the final candidate citation. |
| `05-text-control-red.log` | An additional preservation control found that the first hook also held an ordinary text-kind Smoker field. The guard was narrowed to choice fields. |
| `06-final-focused.log` | Final **14 checks passed in 7.815 seconds**: 12 new plus 2 existing workflows. Includes full source offsets, exact field/options, malformed spans, scope/history/polarity/opposite/duplicate controls, prior labelled/text behavior, and stored page/save/finalization refusal. |
| `07-artifact-workflow.log`, `08-workflow-proof.json` | The same positive workflow reran once to retain its original and finalized Word output: **1 passed in 2.941 seconds**. |
| `09-stored-opposite-after.log` | Exact original constructed-state probe now shows conflict/empty answer and finalization governed by Smoker. |

The stored-state counterexample was **not an observed normal-path note mutation**.
Ordinary note-save clears answers; the probe directly constructed an inconsistent
stored draft. Its pre-fix evidence is retained. The new hook ensures the same
literal relation cannot be trusted on a stored supported answer or offer if its
whole-note proof is absent. It displays the additional source rather than classifying
words by a blacklist. The existing clinician correction path remains available.

The final complete positive goes through upload and mapping confirmation, note
save, queue/reservation, mocked Sonnet5-shaped source selection, worker adoption,
page review, clinician save, finalization and export of the original Word form.
It preserves exact evidence and writes `Smoker  ☐ Yes  ☒ No`. The source original
remains unchanged; exported SHA matches the finalized record. Its synthetic receipt
cost was $0.0003 and synthetic charge $0.00045. These are mocked accounting facts,
not endpoint or clinical-model qualification.

- Synthetic original SHA256: `44c816b30f7cbba701d7aeb9ad8c7a5c6a77fa1147552b186d5cdd88b52e4ff7`
- Synthetic finalized SHA256: `cdce78af8fc92387ecdfba725f52f8b682d08dcb0315631442e1abb90e21e519`
- Final generation SHA256: `bb81dd8117dfe53737b5f37cf5482801260ac7655316dabf424908c68463996f`
- Helper SHA256: `953f75c941311eb64e4efff7429b107656be148924b8b38f3a634c182546fb48`
- Test SHA256: `126a13c5e7b443b5456a08999138160369dca8b2677e9de11eba3cf875a4aadb`

Full artifacts live at `rebuild/.runtime/natural-smoker-20260927/` in this worktree.
The two synthetic DOCX files remain there, outside tracked clinical artifacts.
Logs, scripts, JSON proof and artifact hashes are committed under
`docs/rebuild/v1/evidence/natural-smoker-20260927/`. The evidence manifest preserves
all failed/intermediate runs separately. No unseen templates or qualifications were
opened or rerun. No full suite was restarted. Every DB run asserted isolated port
55702 first, and each test database was destroyed by its runner.

## Next safe action

Root independently refutes the exact finished diff, preserving the existing
source-topic changes as a union at integration. Broader ordinary notes, pronoun
ownership, independent-topic work, real Sonnet5 selection, native Word acceptance
and launch gates remain separate unfinished requirements. This preparation does
not establish V1 readiness, broad Word compatibility or actual endpoint behavior.
