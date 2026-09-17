# Declared recovery of stopped private Word activation — 2026-09-17

The owner authorizes completing the existing private beta and repairing failed
verification while preserving its application and data. This separate act
continues the specifically inspected partial Word deployment at
`429283dfb71aa389bccef48976ee0dce2936e0bc`. Do not rerun the original activator.
Public routes remain in maintenance and real patient data remains disabled.

## Recorded starting state

The private failed report `word-beta-activation-20260917-repaired.json` has SHA256
`b1e157455bbf089655a10c05866fbddb235e15364ef7b0f692eb10f8f9a9bafb`.
It records the installed SDK and applied core0011 migration, all33 full table
hashes after that migration, every original row/column hash, schema metadata,
and private file/mail and retained report inventories. All three private units
are stopped. Its stage remains `applying_three_json_columns` because the later
static-permission guard failed before the next stage marker.

The independent private partial-state audit `word-partial-state-audit-20260917.json`
has SHA256 `088065ee0becdfdea70de3e2008269d4fe4277818ece8423fb90b1ea90ff5589`.
It confirms unchanged rows, applied schema,28 file objects,4 mail objects, stopped
services and no Word environment variables. Its environment hash describes the
inspected state after failure; no earlier unrecorded environment hash is claimed.

Only `staticfiles/app.279720c6eccc.css.gz` has incorrect0664 mode. Its bytes hash to
`097328d627f54b8e026520cce973058f351d32674c0d2523545cc49557f10f3d`.
The inherited WhiteNoise compressor created this output without applying the
configured static-storage file mode. The separately tested replacement backend
creates compressed output with0644 and preserves the compression algorithm.

## Required read-only gates

Run `scripts/resume-word-beta.py` from permanent clean shared main, supplying the
full merged recovery target and a previously unused permanent private result
path. Default mode performs verification only. Its own bytes must match the
target, which must be origin/main with a merged PR and complete exact-commit
citation. The entire diff is restricted to the new static backend, settings,
focused static/recovery tests, recovery script and this declaration.

Invoke the ruled-mutation runner from the committed recovery worktree with an
absolute path to this declaration. Its child command must change directory to
permanent `/opt/meddoc-pro` before running the byte-verified recovery script.
The declaration does not yet exist in permanent429 before the fast-forward;
a relative declaration path from that tree must not be used.

Verify the pinned failed report, original activation lock, independent partial
audit, every full table/schema/file/mail/report fingerprint, current environment
hash, no queued/running jobs and three inactive services with zero MainPID.
Verify unchanged tracked installed units and protected container IDs, images and
mounts against the existing committed activation baseline. No credentials,
domain, certificate, shared service or host protection may change.

The existing SDK stays in `rebuild/.word-sdk/429283dfb71aa389bccef48976ee0dce2936e0bc`.
Revalidate all192 runtime files against final8 manifest
`2a2ab5e1ba63e041dfd087e7f2c205999ccf8ff6bc41f9409cfd1d99e4537680`
and its authentic locked-build proof. All17 compiled input hashes must match
both the partial deployment and recovery target. No SDK file is installed,
replaced, rebuilt or republished by this operation.

## Exact authorized continuation

1. Under the committed declaration through `run-ruled-mutation.sh`, create an
   exclusive private recovery lock and recheck the stopped, unchanged state.
2. Fast-forward shared main to the cited recovery target. Run Django checks and
   the qualified `collectstatic` while all three application units stay stopped.
   No migration command runs; core0011 and all existing data remain unchanged.
3. Require all static directories0755 and files0644. Require every existing
   static path, size and content hash to remain identical; only the observed
   gzip permission changes. No broad chmod, static deletion or private-file
   permission repair is authorized. Verify source readability for the actual
   dedicated application identity.
4. Change only the release SHA and append three Word runtime/manifest/pin
   variables to the operator-private0600 environment. They reference the
   already installed429 runtime. Preserve every other line and credential;
   retain managed service environment mode and forbid qualification bypass.
5. Start only the same three private units through the existing locally pinned,
   network-disabled root helper with read-only host bind. No image pull,
   privileged/unconfined mode, added capabilities or host-policy change.
6. Verify synthetic-only health at the recovery release, same-PID application
   boundary proofs, actual login pages and full served stylesheet bytes. Repeat
   every table/schema/file/mail/report, SDK, environment, installed-unit and
   shared/public maintenance preservation check.

## Evidence and failure behavior

Write a new exclusive0600 recovery result. Preserve the failed report, partial
audit and original activation lock byte-for-byte. Successful recovery adds a
separate private `.word-beta-activation.recovery.json` linking their hashes to
the completed recovery result; it does not rewrite the failed attempt's history.
Completion requires both the result and its valid hash-bound link. A publication
failure also stops the services and attempts an additional exclusive failure
marker; an earlier result is never overwritten to conceal that failure.
An existing recovery lock/result/link refuses a repeat. Any act failure stops
the three private services and retains partial evidence for inspection. No
automatic rollback, migration replay, provider retry or repeated activation.

This act establishes structural recovery only. The authenticated synthetic
browser workflow, document-content verification, real-provider cost evidence
and remaining external release gates retain their separate requirements.
