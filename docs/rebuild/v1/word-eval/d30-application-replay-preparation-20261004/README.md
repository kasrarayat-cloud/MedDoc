# Original D30 application replay — prepared, not executed

This is a prospective fixture-only application replay, not a new D30 result.
The integration owner must freeze the coherent candidate and grant the serialized
QA/layout slot. The first eligible DEV partition D01/D02/D03 precedes this replay.
No test runner, original upload, database, renderer or provider was launched during
preparation. Only Python AST parsing, source inspection and retained evidence reads
were performed. Application source, fixed ground truth and scorer are unchanged.

The original is D30-fdeafbee872f.docx, SHA-256
`fdeafbee872f987325e544953ad930e8e8db8ed6bd30ccab0375f2b50ecbff2f`.
Its immutable ground truth has 62 destinations and SHA-256
`9328d7dbbe820f11f00e6c76f99f2f38e7c01fc971b3bc2789ef71ab3cb14b53`.
The retained a7 automatic mapping was 61/62, with A20 missed and A21 correct;
the explicit A20 manual correction was 62/62. The retained first fixture worker
had 57 conflicts, five missing answers and zero useful supported answers.
These are historical results, not assumed outcomes on the candidate being frozen.

The new inner harness is derived from the already archived original D10/D30
workflow, whose SHA-256 is recorded in the seal. The preserved historical source
remains untouched. The new copy selects only D30 and adds the following evidence:

- Initial automatic mapping and coverage are retained and scored before correction.
- A20 is added through the actual `v3_add` POST at
  `word/document.xml#b/p[72]`, with kind `multi_choice` and label
  `Accommodation selections`. Its eight destinations remain b/p[73]–b/p[80].
- A21 remains a separate narrative at b/tbl[4]/tr[0]/tc[0]. Its mapped field
  must be unchanged, and the original full-document XML comparison verifies its
  exported content remains unchanged. A21 is never substituted for A20.
- Any required source-bound coverage exclusions are explicitly reviewed through
  the normal application route and retained separately from automatic mapping.
- The unchanged synthetic notes reach the real fixture worker. Raw input/result,
  first answers and qualified Sonnet 5.5/v4 job configuration are archived before
  clinician corrections. Provider construction is mocked and asserted unused.
- Explicit clinician review selects `own flat/house` and `with partner` and marks
  every other eligible answer blank and reviewed. The final DOCX, mapping,
  reviewed answers and hash are retained before final-status/fidelity assertions.
- The existing eight-state option check and canonical document comparison retain
  all other body content. Every non-document ZIP part must be byte-identical.
  The actual downloaded DOCX is archived and must equal the private final export;
  the uploaded original must remain byte-identical.

Execute only after the integration owner supplies the freeze and QA grant:

```bash
/opt/meddoc-pro/.worktrees/v1-workflow-candidate/rebuild/.venv/bin/python -B \
  /opt/meddoc-pro/rebuild/.runtime/v1-sol-continuation-20261002/storage-resume-20261003T215613Z/word/run_d30_archived_word_workflow.py \
  /opt/meddoc-pro/.worktrees/ROOT_FROZEN_READONLY \
  FULL_40_CHARACTER_COMMIT \
  --freeze /ABSOLUTE/ROOT_QUALIFIED_FREEZE.json
```

The freeze file must set `frozen_for_word_acceptance` to true, bind that exact
commit, preserve the original thresholds (54/60 overall, 18/20 holdout and
family fraction 0.75), and set `provider_calls` to zero. The outer runner checks
it before opening the original. Existing offline rights are verified from the
fixed ledger; D30 remains provider-denied. No original or field catalogue is
uploaded to a provider.

Every invocation uses fresh output, a PID-specific `quillmd_qa_sol_word_d30_…`
database and owned Unix socket, the existing protected QA wrapper and qualified
nonsecret Word-runtime metadata. The test child is bounded to 900 seconds within
a declared 1200-second outer envelope. Sandbox CPU 12 seconds, wall 20 seconds,
layout fidelity requirements and acceptance thresholds remain unchanged.
After the real child exits, verify direct normal/test database catalog absence,
renderer reap, socket absence, read-only absence of task layout containers and
unchanged clean source/harness hashes before releasing the slot. Do not infer
those facts from a finished log line alone.

`prepared-seal.json` binds the operational sources, historical inputs and
prerequisites; `source-manifest.json` binds the committed literal source archives.
Restore a missing operational copy only from matching archived bytes. Never
overwrite divergent prior attempts or results. This manual recovery replay is
separate from the DEV automatic first-pass adapter: manual A20 success never
counts toward the 54/60 or 18/20 gates, and a fixture workflow never establishes
clinical model usefulness, native Word acceptance or real-patient readiness.
