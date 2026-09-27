# Independent finished ordinary-context refutation — 2026-09-27

Reviewer: Astra `/root/word_recovery`. Read-only candidate worktree `/opt/meddoc-pro/.worktrees/v1-ordinary-context`, clean HEAD `6388a22e98fe84bfbf8e2ac0a6ce9a1fd9f24196`, source commit `0825ba8a04e37082e91e7280225394bf1b314611`, base `ebcddc2a0fc09630ab96c62ef84028f3c567cf03`.

Exact reviewed SHA256:

- `rebuild/core/generation.py`: `fda33a9985894eab4f99d64007ab1c6b516b0d5348a5455d9bf54d9e1ef4efcf`
- `rebuild/core/views.py`: `0f50d70f76ae4132062d95c1d4f892fe44019e1f5b13171427f058e1a074bbed`
- `rebuild/core/tests/test_v3_ordinary_context.py`: `aa34a9725212645b4c047e17c0e1a980d1d22f0fd0ea57b5782ec0258d019f57`

## One demonstrated introduced defect

**Unresolved treatment question becomes supported and passes the shared finalization reader.**

Input note, exactly:

```
Plan: amoxicillin? Return if symptoms worsen.
```

Fields include one unique `Plan` long-text v3 field; the provider simulation selects the complete offered source unit for Plan. At `generation.py:2496-2500`, `conditional_tail` bypasses the unit's `inner_sentence_end` hold because its second sentence is a complete Return-if instruction. The extra `v3_shape_holds` check examines the whole combined value. `ASKS_OR_TRAILS_OFF` at line 1940 recognizes questioning punctuation only at the end, so the question mark before the return instruction is missed.

Actual candidate output:

```
status = supported
text = amoxicillin? Return if symptoms worsen.
```

The complete candidate answer with `reviewed=True` returns `[]` from `governed_decisions(notes, fields, stored)`, the shared review/finalization governance check. No contextual decision is required for the unresolved treatment question. Exact base code holds the same source selection as `conflict` with blank text. This is introduced by the conditional-tail exception. The question mark remains in the text, but the supported status falsely certifies an unresolved proposed treatment and lets an ordinary review tick through the shared gate.

The root independently reran this exact probe using an unreachable synthetic database configuration and confirmed candidate supported output plus empty finalization refusals. Root retains its independent JSON proof. No merge should occur until the repair is verified in both selection and stored-draft governance paths.

## Bounded remaining lenses

Eight synthetic inputs were exercised in `probe.py`/`probe.json`, then identically against exact base source in `compare-base.py`/`base.json`. They cover questioning versus negative Plan text, patient/family/other-person context, a useful complete patient/allergy/conditional-plan positive, repeated instruction order and explicit differing side context. The useful complete patient/allergy/Plan example becomes supported with intact text, as intended. Negative wording remains verbatim. The repeated imperative case remains held; existing B-G1 excessive holds remain open. Explicit right-history/left-plan wording remains intact; the source itself names both sides, so this is not a demonstrated destination mutation.

The aunt/nurse allergy examples also produce supported answers on the base, so they are not reported as regressions from this finished diff. Their subject-context uncertainty must not be turned into a blanket safety claim; general clinical-context qualification remains open in the candidate report.

No additional introduced data-loss, wrong-destination or generation-versus-draft divergence was demonstrated in the inspected diff and bounded probes. This is not a clinical semantic qualification or an assertion that all ordinary notes work. No provider, corpus/holdout, desktop Word, AWS, production or paid action was used. No candidate source was edited and no broad suite was rerun.

## Reproduction / retained artifacts

From any directory, using the candidate venv and a synthetic settings environment:

```
/opt/meddoc-pro/.worktrees/v1-ordinary-context/rebuild/.venv/bin/python \
  /opt/meddoc-pro/.worktrees/v1-host-readiness/rebuild/.runtime/ordinary-context-refutation-20260927/probe.py
```

The script sets `DJANGO_SETTINGS_MODULE`, a dummy secret and fixture AI mode only when absent; it invokes pure selection/governance code and does not open a database or provider transport. `probe.json` is the original output. Exact base source is `generation-base.py`; `TASK_GENERATION_BASE` selects it for `compare-base.py`. Source-base output JSON's disk hash still identifies the candidate import location, so the executed comparison authority is the preserved base file and the stated full base commit, not that JSON hash field.

Next safe action: notes agent repairs the confirmed question/conditional-tail defect; root replays the exact proof, then reviewer inspects only the final changed delta and relevant positive/refusal evidence. Retain all originals.
