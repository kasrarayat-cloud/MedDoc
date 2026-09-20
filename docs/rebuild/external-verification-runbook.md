# External integration verification runbook

Prepared 2026-09-17 for the three credential-gated checks in
[owner-actions.md](owner-actions.md) §2–§4. **Nothing here has been executed
against live Stripe, Resend or Backblaze.** Each runner refuses until the
owner-supplied inputs are present in the protected environment, and none of
them prints, stores or transmits a credential.

Common rules for every step below:

- Run from the permanent reviewed release, `/opt/meddoc-pro/rebuild`, after the
  runner's branch is merged. The application must be on a reviewed active release;
  `--release` names the actual `/health/` revision. Record the runner Git revision
  separately when only operational tooling changed. Do not restart the application
  for a runner/documentation change. The runners refuse to run from a worktree or
  against a different served revision.
- Evidence is a private, owner-only `0600` JSON file created exclusively under
  `/opt/meddoc-pro/rebuild/.runtime/`. An existing evidence file blocks a new
  attempt until a person has read it: an uncertain paid or emailed action is
  inspected, never re-run by a script.
- Commands carry only paths and nonsecret identifiers. Secrets travel through
  the protected SSH/SFTP or secret-manager channel and are never pasted into a
  shell, chat, Git file or screenshot.
- Report file paths, never their contents, in checkpoints and pull requests.

## 1. Stripe sandbox — `rebuild/stripe-sandbox-verify.mjs`

### 2026-09-20 return-chain and attempt evidence amendment

The runner now observes the actual success navigation before the application's
unauthenticated login redirect. It also accepts an optional `--attempt
LOWERCASE_LABEL` to retain a separately named, exclusively created report after
engineering inspects an earlier attempt. The original report is never replaced;
the label does not authorize repeated uncertain checkouts. See
[the focused repair and executed browser evidence](stripe-return-verification-20260920.md).
The older preparation statements below remain dated historical context; real
execution and currently installed configuration are recorded in the checkpoint.

### 2026-09-19 verification correction

Real sandbox execution remains blocked: the protected application has no Stripe
key/signing secret and the installed CLI is unpaired. The existing dry run reached
the actual receiver and correctly stopped on HTTP503 before login or checkout.
See [the readiness evidence](stripe-readiness-20260919.md). Earlier reports remain
unchanged. This runbook describes future execution, not completed evidence.

The runner now requires `STRIPE_CLI` for `--execute`. Completing the automated
checks with unverified/manual cases gives `passed:false`, `sandbox_acceptance:
"incomplete"`, exit2. Exit1 is a stopped/failed attempt. A successful dry run is
only readiness (`sandbox_acceptance:"not attempted"`). `executed` means a checkout
submission was attempted; `execution_completed` means the automated sequence ended.
No partial failure may be assumed to have made no payment. Never overwrite an
attempt report or rerun an uncertain checkout; record later evidence in an additive
close-out after inspecting the existing attempt and payment identifiers.

### Owner supplies

Current sole Stripe action in owner-actions.md: the Stripe CLI on the VPS (`/home/claude/.local/bin/stripe`,
v1.51.0) paired with the QuillMD sandbox by the owner (`stripe login`; its
test-mode keys live in `/home/claude/.config/stripe/config.toml`, 0600), and a
sandbox restricted key (`rk_test_…`, Checkout Sessions → Write only; an
`sk_test_…` is accepted) stored as `STRIPE_SECRET_KEY` in the protected
`rebuild/.env` (owner `claude`, mode `0600`). Engineering stores the listener's
own signing secret as `STRIPE_WEBHOOK_SECRET` in the same file. The service must be
restarted through the checkpoint's documented procedure so the running process
loads them; a value in the file is not a value in the process.

### Operator steps

1. Confirm the VPS CLI is paired with the same sandbox with a read that prints no
   key material, for example `stripe balance retrieve`, which shows only the
   sandbox balance. Never print the CLI configuration: it holds its keys. Its pairing key is an
   operator capability: listing events needs Events → Read and creating the
   refund needs Charges and Refunds → Write on the CLI login, not on the
   application key.
2. In a dedicated terminal that stays open for the whole exercise, start
   forwarding with exactly this command and keep its output private:

   ```bash
   stripe listen --forward-to http://127.0.0.1:9130/billing/webhook/ \
     --events checkout.session.completed,checkout.session.async_payment_succeeded,checkout.session.async_payment_failed,checkout.session.expired,refund.created,refund.updated,refund.failed
   ```

   The `whsec_…` it prints is stored as `STRIPE_WEBHOOK_SECRET` without echoing
   it. A later public HTTPS endpoint gets its own, different secret from the
   Dashboard. Stripe documents that the CLI signing secret stays the same across
   listener restarts. Verify the current listener/configuration match after setup
   or account/key changes; reload the application only if configuration changes.
   [Official listen reference](https://docs.stripe.com/cli/listen).
3. Dry run. This proves the preconditions without submitting anything:

   ```bash
   cd /opt/meddoc-pro/rebuild
   node stripe-sandbox-verify.mjs --release FULL_SHA --dry-run
   ```

   It refuses unless: both `127.0.0.1:9130` and `localhost:9130` report the exact
   release, `synthetic-only` and the doctor surface; an unsigned probe of
   `/billing/webhook/` is answered `400` (a `503` means the signing secret is
   not loaded); the synthetic doctor can sign in; the billing page's Payments
   row reads **Stripe sandbox key configured** and offers the checkout form.
   Evidence: `.runtime/stripe-sandbox-verification-<release12>-dry-run.json`
   with `executed:false` and the wallet baseline.
4. Execute, with the CLI path supplied so the duplicate and refund cases run:

   ```bash
   STRIPE_CLI=/home/claude/.local/bin/stripe node stripe-sandbox-verify.mjs --release FULL_SHA --execute
   ```

   `STRIPE_CLI` must be the absolute real path of the binary. Set
   `PLAYWRIGHT_MODULE_DIR` if Playwright is installed outside the default
   module resolution, as for the other browser runners.
5. Retain a protected, secret-redacted transcript of the listener's event IDs,
   delivery timestamps and HTTP statuses. Correlate the original and duplicate
   receipt with the application's stored event ID, attempts, status and unchanged
   ledger. A successful resend command or unchanged wallet alone proves no receipt.
   Bare `stripe events resend <evt_id>` targets the CLI listener; a registered
   public endpoint is not required. [Official resend reference](https://docs.stripe.com/cli/events/resend).
6. Read `.runtime/stripe-sandbox-verification-<release12>.json`. Then, without
   MFA-free shortcuts, an administrator confirms the same identifiers in the
   console's payments, refunds and Stripe events tables (attempts and status).

### What the runner does

| case | action | assertion |
| --- | --- | --- |
| payment success | one $5.00 personal checkout through the real form; Stripe-hosted Checkout filled with test card `4242 4242 4242 4242`, a future expiry and `stripe-sandbox@synthetic.quillmd.invalid` | Stripe redirects to `/billing/?payment=processing`; polled on `127.0.0.1` until the new payment row reads `paid`, the personal paid wallet rose by exactly `5.000000`, exactly one new `payment` ledger entry exists, promotional balance unchanged |
| duplicate delivery | `stripe events list --type checkout.session.completed --limit 20` to find the event and payment intent; `stripe events resend <evt_id>` | paid wallet, payment ledger count and payment rows unchanged after 12 s; **receipt unverified by runner, acceptance incomplete** |
| refund | `stripe refunds create --payment-intent <pi_id> --amount 200` | a `refund` ledger entry of `-2.000000` appears and the paid wallet falls by exactly `2.000000` |
| failed payment | second $5.00 checkout with test card `4000 0000 0000 0002` | Stripe shows a decline; the new payment row stays `pending`, no balance or ledger change |

Guard rails that hold throughout: the browser context aborts every request that
is not to the application (`127.0.0.1:9130` / `localhost:9130`) or to a
Stripe-operated host (`*.stripe.com`, `*.stripecdn.com`, `*.stripe.network`;
hosted Checkout serves its assets and fraud-signal frames from the latter two),
and counts what it blocked and what it allowed per host; checkout `POST`s are
allowed only when armed and at most twice in total; no checkout is ever
repeated; the report holds Stripe object identifiers (`cs_test_…`, `pi_…`,
`evt_…`, `re_…`) and the application's payment ids, never card data, the
hosted checkout URL, the key or the signing secret.

Why `localhost` appears: the application fixes Stripe's `success_url` to
`http://localhost:9130/billing/?payment=processing`. Cookies are host-scoped and
`SameSite=Strict`, so the browser lands there unauthenticated by design; the
runner records the landing URL and reads balances back on `127.0.0.1`, where its
session lives. The health check on both names proves they are one listener.

### What remains manual

- **Retry after a temporary forwarding failure.** Engineering records one failed
  forwarding attempt at a temporary closed project loopback port, then forwards
  and resends the same authentic event to the application. Preserve the non-2xx
  and successful receipt plus attempts/status/wallet/ledger invariants. Do not
  stop the doctor service. This demonstrates controlled resend after a failure;
  it does not prove Stripe's automatic retry schedule.
- **Out-of-order delivery.** Not automated here. Engineering will filter delivery
  so an authentic successful refund reaches the application before its completion
  event, then enable/resend that authentic completion and inspect the early-refund
  reconciliation, retry, final balance and exactly-one ledger rows. Use a separately
  declared synthetic checkout with a recorded spending bound; do not repeat this
  runner's checkout. This is an unexecuted engineering procedure, not sandbox proof.
  Existing locally signed lifecycle tests remain isolated evidence only.
- **Concurrent spending against a refund.** Not exercised by this runner.
- **Receiver attempts and reconciliation rows** are administrator-console facts
  under MFA; the runner records only what the doctor UI shows.
- The declined session stays open at Stripe for up to 24 h; its
  `checkout.session.expired` event should move that payment row to `expired`.
  Re-read the billing page afterwards and note it in the checkpoint.

The synthetic doctor's paid wallet ends the exercise `3.000000` higher than it
started (5.00 credited, 2.00 refunded). That is sandbox money on a synthetic
account; leave it, and cite the report path when the balance is later audited.

## 2. Controlled email recipient — `rebuild/email-delivery-verify.py`

### Owner supplies

Per owner-actions §3: one inbox the owner controls and will check, with
permission to receive synthetic invitation and recovery messages; the preserved
Resend credential and verified sender activated as described in
[email-delivery.md](email-delivery.md) (`QUILLMD_EMAIL_MODE=resend`,
`QUILLMD_EMAIL_FROM`, `QUILLMD_EMAIL_VERIFIED_DOMAIN`, an HTTPS
`QUILLMD_APP_BASE_URL`, and `RESEND_API_KEY` or `QUILLMD_RESEND_ENV_FILE`),
followed by a service restart through the documented procedure.

### Operator steps

1. Obtain the recipient address from the owner directly. The script has no
   default and refuses synthetic, reserved-TLD and placeholder addresses. The
   confirmation phrase must be passed verbatim: `I control this inbox`.
2. Dry run (public DNS and configuration presence only; no login, no send):

   ```bash
   cd /opt/meddoc-pro/rebuild
   .venv/bin/python email-delivery-verify.py --release FULL_SHA \
     --recipient ADDRESS --recipient-confirmation "I control this inbox" \
     --stage invitation --dry-run
   ```

   Configuration presence is read inside a subprocess running the
   application's own settings; it prints booleans and the sender domain only.
   DNS is resolved with Cloudflare's DNS-over-HTTPS JSON API at `1.1.1.1`
   (SPF at the domain and at `send.<domain>`, MX at `send.<domain>`, DKIM at
   `resend._domainkey.<domain>`, DMARC at `_dmarc.<domain>`). These are the
   conventional Resend names; the authoritative list is the one Resend shows for
   the domain.
3. Execute the invitation stage:

   ```bash
   .venv/bin/python email-delivery-verify.py --release FULL_SHA \
     --recipient ADDRESS --recipient-confirmation "I control this inbox" \
     --stage invitation --execute
   ```

   It refuses unless Resend mode is enabled and configured, the link origin is
   HTTPS, and the provider (when readable) does not report the domain as
   unverified. A `401` from `GET https://api.resend.com/domains` is recorded as
   `domain_status_readable:false` and is not a failure: the preserved key is
   send-only. It then signs in as the synthetic owner through the real login
   form, submits the real invitation form (department X-ray, role employee),
   records the HTTP outcome and the application's own notice
   (`accepted-by-provider`, `private-outbox-only`, `delivery-failed` or
   `rate-limited`), and signs out. It never reads the outbox, a token or a link.
4. Recipient, from the controlled inbox: confirm receipt by replying (never
   forward the message or paste its link). Open the invitation link **only
   through the SSH tunnel** (`ssh -N -L 9130:127.0.0.1:9130 <vps-user>@<vps-host>`,
   see [private-hosting.md](private-hosting.md)): the emailed link carries the
   public origin, which is still in maintenance, so replace that origin with
   `http://localhost:9130` and keep the path unchanged. Accept with a synthetic
   name and a new password.
5. Execute the recovery stage after acceptance (a recovery message is only
   produced for an existing verified account):

   ```bash
   .venv/bin/python email-delivery-verify.py --release FULL_SHA \
     --recipient ADDRESS --recipient-confirmation "I control this inbox" \
     --stage recovery --execute
   ```

   The recipient opens the recovery link through the tunnel the same way,
   completes the new-password form within 30 minutes, signs in with the new
   password, and replies again confirming both messages and that the link
   worked once.
6. Under MFA, an administrator reads the `email.accepted` audit rows and records
   the provider message identifiers beside the report path. The runner does not
   read the administrator console.
7. A person who saw both messages sets `inbox_receipt_confirmed` to `true` in
   the report file together with `inbox_receipt_confirmed_by` and
   `inbox_receipt_confirmed_at`. The script always writes `false`.

Evidence: `.runtime/email-delivery-verification-<release12>-<stage>.json`
(`-dry-run` suffix for dry runs; no stage suffix for `--stage both`). Fields:
`sender_domain_dns`, `provider_domain_status`, `app_email_configuration`,
`invitation_http_status`, `invitation_outcome`, `recovery_http_status`,
`recovery_outcome`, `recipient` masked as `ab***@domain`, `tokens_exposed:false`,
`inbox_receipt_confirmed:false`, `next_steps`.

### What it proves and does not

Proves: the sender domain's public records as seen by a public resolver; that
the running application is in Resend mode with a configured sender and HTTPS
link origin; that the real invitation and recovery flows accepted the request
and what the application reported. Does not prove: inbox delivery, link
usability or message content. Those come only from the recipient's replies and
the administrator's audit read, recorded by people.

## 3. Offsite backup round trip — existing `rebuild/ops/offsite_backup.py`

No new adapter. The existing CLI performs one explicit encrypted upload,
download, authentication and isolated restore; it never schedules, deletes,
provisions or widens permissions. Its full design is in
[offsite-backup.md](offsite-backup.md); this section is the operator sequence.

### Owner supplies

Per owner-actions §4: an owner-approved private B2 bucket dedicated to the new
system, its S3 endpoint, region, name and 24-character bucket id, and a standard
application key restricted to that bucket and to the prefix
`quillmd-fresh/synthetic/` with exactly `listFiles`, `readFiles` and
`writeFiles`. No `deleteFiles`, `listAllBucketNames`, bucket or key
administration. The adapter verifies this scope from Backblaze's authorization
response before any upload and refuses a wider or narrower key.

### Configuration template

Create, through the protected channel, the operator-only `0600` file
`/opt/meddoc-pro/rebuild/.runtime/backup-secrets/b2-offsite.json` with exactly
these fields (the adapter rejects extra or missing keys):

```json
{
  "version": 1,
  "endpoint": "https://s3.REGION.backblazeb2.com",
  "region": "REGION",
  "bucket": "APPROVED-BUCKET-NAME",
  "bucket_id": "APPROVED-24-CHARACTER-HEX-ID",
  "prefix": "quillmd-fresh/synthetic/",
  "application_key_id": "REPLACE-THROUGH-SECURE-CHANNEL",
  "application_key": "REPLACE-THROUGH-SECURE-CHANNEL",
  "owner_approval_reference": "REFERENCE-TO-RECORDED-DESTINATION-APPROVAL",
  "private_bucket_confirmed": true,
  "synthetic_only": true
}
```

`REGION` has the form `us-west-004`; the endpoint must be exactly
`https://s3.<region>.backblazeb2.com`. Bucket privacy is owner-confirmed, not
API-verified, because the scoped key deliberately cannot read bucket settings.

### Operator steps

1. Keep the encryption key outside both the backup and the output directories
   (`.runtime/backup-secrets/<name>.key`, `0600`), and place a recovery copy in
   the owner's separate vault; record the custodian and vault item reference,
   never the key.
2. Create the output directory once, operator-owned `0700`:
   `/opt/meddoc-pro/rebuild/.runtime/offsite-checks`.
3. Prepare with zero network calls. It authenticates the manifest and every
   encrypted object locally and validates the configuration file's shape:

   ```bash
   cd /opt/meddoc-pro/rebuild
   .venv/bin/python ops/offsite_backup.py \
     --config /opt/meddoc-pro/rebuild/.runtime/backup-secrets/b2-offsite.json \
     --backup /opt/meddoc-pro/rebuild/.runtime/new-system-backups/BACKUP-RUN-ID \
     --key-file /opt/meddoc-pro/rebuild/.runtime/backup-secrets/KEY-FILE \
     --output /opt/meddoc-pro/rebuild/.runtime/offsite-checks
   ```

   `BACKUP-RUN-ID` is an existing encrypted backup produced by
   `ops/backup_restore.py backup` ([backup-restore.md](backup-restore.md)).
4. Execute the round trip by adding `--execute`. The adapter authorizes and
   verifies key scope, uploads every encrypted object and the manifest last to
   `quillmd-fresh/synthetic/<run-id>/<manifest-ciphertext-sha256>/`, downloads
   everything back, verifies ciphertext hashes and authenticated plaintext
   hashes, and hands the download to the existing isolated restore (networkless
   container, no workers, no provider credentials).
5. Repeat recovery without the local backup, using the separately held key copy
   and the nonsecret identifiers from the receipt:

   ```bash
   .venv/bin/python ops/offsite_backup.py \
     --config /opt/meddoc-pro/rebuild/.runtime/backup-secrets/b2-offsite.json \
     --download-run-id BACKUP-RUN-ID \
     --manifest-sha MANIFEST-CIPHERTEXT-SHA256 \
     --key-file /opt/meddoc-pro/rebuild/.runtime/backup-secrets/RECOVERED-KEY-FILE \
     --output /opt/meddoc-pro/rebuild/.runtime/offsite-recovery-checks \
     --execute
   ```

### Evidence

Each execution writes `<output>/offsite-<run-id>.json` (`0600`) with `mode`
(`upload-roundtrip` or `download-only-recovery`), `scope` (provider-verified
single bucket, prefix and capabilities), `transport_verified`, `object_count`,
`manifest_cipher_sha256`, `remote_prefix`, `all_ciphertext_hashes_match`,
`all_objects_authenticated`, `encryption_key_uploaded:false`,
`plaintext_uploaded:false`, `restore_verified`, the isolated restore summary
and `complete`. An existing report for the same run id blocks another attempt
until inspected. `vault_recovery_demonstrated` is always written `false`: only
independent evidence that the key copy was obtained from the vault establishes
escrow, and a person records that beside the report path.

### What remains after the first round trip

RPO/RTO measurement; the 04:30 UTC daily schedule and verified failure alerts
to the controlled inbox; a separately reviewed B2 lifecycle rule for the agreed
30-day history that accounts for both hiding and deletion. None of these are
installed by the adapter, and retention deletion stays disabled until the first
restore pass has been judged.
