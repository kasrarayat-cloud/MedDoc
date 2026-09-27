# Ordinary typed or dictated notes on any custom form (B-G1) — design

## The defect

At the installed release, only two kinds of form accept notes without labels:

- the colonoscopy form (underlined-tab "natural" contract);
- the WM IOV form (labelled lines plus prewritten statements).

Every other uploaded form accepts labelled `Label: value` lines only. `validate_selections` treats a note of
several lines that are not all labelled as inheriting context, and returns **every** answer as a conflict.
A doctor who types or dictates ordinary prose gets a page of conflicts. The owner has ruled this out: ordinary
notes must not be replaced by a mandatory labelled-note workaround.

## The approach: generalise the most-refuted contract that already exists

The colonoscopy path's natural contract already works for ordinary prose:

- `source_units` splits notes into complete sentences with exact offsets;
- the model selects **unit ids** only and never composes text;
- `validate_tab_selections` inserts complete source sentences;
- governance holds cover headings, pointers, corrections, inherited negative scope and inline corrections.

Very little of it is tab-specific:

| part | tab-specific? | generalisation |
|---|---|---|
| `tab_evidence_contract(fields)` gate | yes (locator `tab_form`) | a form-level `evidence_contract='natural-v1'` recorded on the template version (v3 templates by default; legacy templates only by explicit opt-in, never by silent change) |
| prompt text | partly (procedure-description examples) | a generic natural prompt with its own `CURRENT_PROMPT_VERSION` (tripwire test pins the digest) |
| `validate_tab_selections` | no — label parsing, subject guards, numbered groups and governance are form-agnostic | reused unchanged |
| choice/checkbox/table kinds | n/a | explicit-option-only rule from the Word integration; everything else held |
| voice transcripts | unpunctuated (`smart_format=false`) → one giant "sentence" → held | `smart_format` becomes a per-deployment setting (blockers stream); the natural contract holds rather than splits a run-on unit |

## Safety bar (same as every clinical-path change here)

- Each change gets adversarial refutation over the finished diff, repeated in rounds until a round finds no
  release-blocking defect.
- Refutation lenses: negation and scope; wrong field (paired and repeated labels); corrections; voice run-ons;
  cost bound.
- Every guard is mutation-proved.
- Fixture-mode tests on synthetic notes: explicit positives fill; denied, missing, corrected and ambiguous
  findings are held; holding everything is a failure.
- A bounded live synthetic evaluation (≤ $10, in `V1-EXTERNAL-REQUEST.md`) before activation. The legacy and tab
  contracts stay byte-identical: pricing versions and request bytes are pinned by tests.

## Status

Designed, not built. It is scheduled on top of the Word integration's generation phase, so `core/generation.py`
changes land once instead of conflicting three ways with the Sonnet 5 profile and the v3 kinds.
