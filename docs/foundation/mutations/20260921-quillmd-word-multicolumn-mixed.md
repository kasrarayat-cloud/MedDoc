# Declaration — multi-column question rows and mixed table/underline Word forms, September 21, 2026

This candidate adds real import, mapping and export support for two documented Word gaps, and
carries the clinical-path repairs the mandatory refutation gate found while proving it. It is
written **before** integration, against baseline
`875ee6e2a0836c37fcb293c228664186c1106291` — the source revision Tab 2 published as healthy
after recovering its admin-console activation (served release
`21809ef408a5f7b6691beb338a7640da82fcfb97`).

It authorizes **no** deployment, no migration, no public-asset move, no service start, no
payment and no provider call. Tab 2 remains the sole integration and deployment lead.

## Why this candidate has its own declaration

Tab 2's activation guard `scripts/activate-admin-console.py` is pinned to the range it actually
installed, and its allowlist is exhaustive for that range. Its own test states the consequence:

> *"A later, unrelated candidate must bring its own declaration; this allowlist stays
> exhaustive."*

⚠️ **The earlier collision is recorded here rather than dropped, because it is the reason this
file exists.** Before that recovery, `DeclaredSourceScope` diffed its baseline against the
branch under test, so this candidate's seven then-undeclared files made CI red on a guard that
was working exactly as designed on a tree it was never scoped for. The fix was theirs to make
and they made it. **Nothing in this candidate widens, relaxes, re-scopes or rewrites Tab 2's
guard or its historical declaration.** The instrument below is separate, and it refuses the same
protected classes on its own account.

## The declared source scope

Thirteen files. Exhaustive — anything not named here is not part of this candidate.

<!-- declared-source-scope -->

```text
docs/foundation/mutations/20260921-quillmd-word-multicolumn-mixed.md
rebuild/core/generation.py
rebuild/core/tab_review.py
rebuild/core/tests/test_tab_independent_sections.py
rebuild/core/tests/test_unlabelled_source_scope.py
rebuild/core/views.py
rebuild/documents/engine.py
rebuild/documents/tab_form.py
rebuild/documents/test_multicolumn_and_mixed.py
rebuild/documents/test_tab_form.py
rebuild/documents/test_unmapped_areas.py
rebuild/ops/test_word_multicolumn_scope.py
scripts/ci/verify-fresh.sh
```

| file | what it carries |
|---|---|
| `documents/engine.py` | multi-column answer rows; mixed table + underline mapping; structural `validate_mapping`; the legacy-contract fallback at fill time |
| `documents/tab_form.py` | `also_changed`, so the tab writer emits the other writer's parts instead of the original bytes |
| `core/generation.py` | prompt version `extractive-v6-source-scope-attestation`; the consent/attestation guidance on **both** providers; the subject guards ported into the legacy validator |
| `core/tab_review.py` | a signature answer area is recognised by its label as well as its policy, wherever it sits on the form |
| `core/views.py` | `finalize` fills through the **stored** mapping, not a fresh inspection |
| `scripts/ci/verify-fresh.sh` | names the new documents module, because that list is explicit and an unnamed module is inert |
| `ops/test_word_multicolumn_scope.py` | this declaration's instrument |
| the four `test_*` modules | the proofs, including the ones that caught two defects this candidate introduced |

## What is NOT declared, and is refused rather than merely absent

`rebuild/ops/test_word_multicolumn_scope.py` refuses each of these **against the declared set
itself**, so writing a path into this document is not a way past them:

| class | status |
|---|---|
| `rebuild/core/migrations/**` | **none.** No schema change. A migration needs its own reviewed act |
| `rebuild/static/**` | **none.** No public asset moves |
| `rebuild/ops/**` other than the instrument | **none.** No operations helper changes |
| `rebuild/deploy/**`, `deploy/**` | **none.** No service policy or unit changes |
| `.github/**` | **none.** No workflow changes |
| non-canonical or absolute paths | refused |

Each refusal is proved by a test that asserts it raises, alongside a positive control proving
the harness is not simply refusing everything, and a parse test proving an unreadable
declaration raises instead of quietly reading as the empty set.

## Preservation

Accounts, originals, stored mappings, finalized records, exports, audit history, credentials,
MFA, department isolation, inactive reviewer access, financial history and backups are
untouched. Legacy mappings created before this candidate fill **byte-identically** under the new
code, and the owner's colonoscopy template still exports byte-identically at 24 logical fields
over 28 physical anchors. A mapping matching neither contract is still refused. Settlements,
receipts and the pricing fingerprint are unaffected — `prompt_version` is not in the price
whitelist, and a queued job keeps its stored config.

## Known limitation, stated plainly

**This candidate does not establish universal Word compatibility, and must not be described as
doing so.** It adds support for two specific, unambiguous layouts: ordinary multi-column
question/answer tables where the answer cell is unambiguous, and forms combining supported
tables with underlined answer blanks. Genuinely ambiguous layouts remain **explicitly
unsupported** and are reported as omitted or unsupported answer areas rather than guessed at:
two or more blanks after one label, a blank in a label position, merged cells, content controls,
text boxes, legacy Word fields, tracked changes, and scanned forms.

## Activation conditions

1. Tab 2 coordinates integration. This candidate stays **unmerged and undeployed** until then.
2. One purposeful provider verification is held for the coordinated activation, scenario fixed
   in advance — see `HANDOFF.md` §1e. No repeat transcription, no new spending authority.
3. The clinical-generation review gate runs over the finished diff before merge, as standing
   authority requires, and its findings are repaired before the candidate is offered.
