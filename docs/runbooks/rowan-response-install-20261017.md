# Rowan coding review response installation

This is prepared installation machinery, not an installation record. The lead
owns deployment and all browser actions. Earlier Rowan controllers are consumed.
The new entrypoint is `python -B -m ops.activate_rowan_response`; without
`--execute` it reads no operational inputs and performs no action.

The exact installed base is `057d65db7ddb97289e01e85da42cb48eb475c76f`. The
prospective source delta is limited to coding views/output, `coding.js`, focused
coding tests and this operator's files. No migration, settings, provider, billing,
credential, service or unrelated runtime file is admitted. Configuration changes
only the release line; every other environment byte remains fixed.

The operator reuses existing source/static publishers, locks, native service
transport and read-only snapshots. It executes no historical controller. Its
lifecycle contains no migration or provider operation. Only the doctor, admin
and worker units may stop/restart. Normal HTTPS ingress and unrelated services,
including VoiceAssistMain and the separate Corti preview, remain unchanged.

Before stopping and before resuming, every current database table fingerprint,
migration ledger row, watched catalog/function/sequence property and clinical
file inventory must match exactly. This preserves the finalized synthetic
encounter, current coding selection revision and every failure, receipt, usage,
decision and audit row. It does not restore earlier selections or create an
approval. Historical Word files and original-format exports remain fixed.

The catalog comparison covers the existing snapshot's named properties; it is
not a claim to fingerprint every PostgreSQL property. Source admission excludes
all migrations, and installation runs no DDL or row mutation. Current pending
jobs, coding runs or active stage receipts refuse installation.

1. Finish the focused runtime checks and review. Merge through the existing
   guarded PR procedure and wait for required workflows on the exact merged
   revision. The candidate worktree must be clean and exactly that revision.
2. Keep `/opt/meddoc-pro` on clean installed `main` at the exact base. Prepare a
   new private closed plan with format
   `quillmd-rowan-review-response-native-install-v1`, base, candidate, every
   changed tracked source path/hash, candidate source worktree, exclusive private
   evidence directory, current environment hash and changed static aliases.
   `static` is exactly `[]` or `["coding.js"]`, matching the actual source delta.
3. Commit a new prospective declaration in a separate execution worktree directly
   descended from the candidate. Name the full candidate, private plan hash,
   format, permitted changes and current-state preservation requirements.
4. From that **execution worktree's cwd**, use
   `scripts/run-ruled-mutation.sh --declaration <absolute committed declaration>`
   with `env PYTHONPATH=<clean candidate>/rebuild` and installed venv Python
   executing `-B -m ops.activate_rowan_response --execute --plan <private plan>
   --plan-sha256 <exact hash>`. Preserve wrapper/watchdog supervision. Do not run
   operator code from the declaration-only child or bind the declaration to a
   different cwd.
5. Inspect the new installation receipt and normal HTTPS health revision before
   resuming the ordinary synthetic review/download flow. Read persisted selection
   state first: a timed-out browser response may already have saved its decision.
   Installation does not retry that action or approve anything.

Only declared static aliases may be replaced; old hashed assets remain. Before
source publication a failure may resume the unchanged original units. After
publication it leaves stopped units stopped for an explicit diagnosed recovery.
It never retries, overwrites an existing attempt directory or rolls back saved
clinical state. Strict data/file comparison ends before services resume.

Focused offline operator checks:
`python -B -m unittest ops.test_activate_rowan_response`.
