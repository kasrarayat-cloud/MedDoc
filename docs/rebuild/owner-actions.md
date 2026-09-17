# Owner actions for the next private beta release

Updated 2026-09-17. Continue the existing new application and preserve its data.
The engineering choices below are fixed for this stage; they are not an options
menu. Public app/admin routes stay in maintenance and real patient data remains
disabled. A configured credential is not proof that an integration passed.

## 1. Provide Stripe sandbox access securely

**Blocks:** actual Stripe-hosted checkout, signed event delivery, refund and
payment retry verification. Existing locally signed fixtures are simulated tests.

1. In the Stripe Dashboard, select a dedicated **sandbox** for QuillMD. Use its
   API keys page, choose **Create restricted key**, name it
   `QuillMD private beta checkout`, and start with no permissions.
2. Set **Checkout Sessions → Write**. Leave every other resource and connected
   account permission at **None**. This matches the application's sole outbound
   Stripe operation, `POST /v1/checkout/sessions`. Receiving signed payment and
   refund events does not require an API permission. Stripe documents the
   Checkout permission in its [resource permission reference](https://docs.stripe.com/stripe-apps/reference/permissions#object).
3. Store the resulting `rk_test_…` value as `STRIPE_SECRET_KEY` in the protected
   `/opt/meddoc-pro/rebuild/.env` using an SSH/SFTP editor or the existing secure
   secret-management channel. Preserve owner `claude` and mode `0600`; do not put
   the value into chat, a shell command, a Git file, or a screenshot. Existing
   `sk_test_…` credentials are accepted, but the selected setup uses a restricted
   key. Live and publishable keys are rejected. The naming and creation steps
   follow Stripe's [API key guide](https://docs.stripe.com/keys) and
   [restricted-key guide](https://docs.stripe.com/keys/restricted-api-keys).
4. Authorize the official Stripe CLI against that same sandbox in the operator's
   protected session. Engineering will use secure CLI forwarding to
   `http://127.0.0.1:9130/billing/webhook/`; no public ingress needs to open. The
   listener's `whsec_…` signing secret must be saved securely as
   `STRIPE_WEBHOOK_SECRET` in the same protected environment. It is distinct from
   the API key and from a Dashboard endpoint's signing secret. Keep listener
   output private. [Stripe local webhook testing](https://docs.stripe.com/webhooks#test-webhook)

Forward only these events: `checkout.session.completed`,
`checkout.session.async_payment_succeeded`,
`checkout.session.async_payment_failed`, `checkout.session.expired`,
`refund.created`, `refund.updated`, and `refund.failed`.

Engineering will validate the restricted key with the actual Checkout request
before treating its permissions as proven for this account. The current request
uses inline price/product data. If Stripe identifies an additional required
permission, record the exact denied operation and grant only that requirement;
do not silently substitute an unrestricted key or claim the minimum was tested.

During the controlled sandbox exercise, issue the specified refund in the
**sandbox Dashboard**. The application currently receives refund events; it has
no refund-creation API. An operator performing the equivalent API operation
would need **Charges and Refunds → Write**; retrieving recorded events needs
**Events → Read**. Those are separate operator capabilities, not required
permissions for the application key. The relevant resources are defined in
Stripe's [permissions reference](https://docs.stripe.com/stripe-apps/reference/permissions#object),
and refunds use the [Refund API](https://docs.stripe.com/api/refunds/create).

The verification record must cover payment success, one credit despite duplicate
delivery, failed payment, retry after temporary receiver failure, out-of-order
delivery, refund and concurrent spending. Record Stripe IDs and QuillMD ledger
links. Test mode does not process real card payments. No subscription or
automatic top-up is enabled.

## 2. Supply one controlled email recipient

**Blocks:** real invitation and password-recovery delivery evidence.

Provide one inbox you control and will check, with permission for the synthetic
invitation and recovery messages. The preserved Resend credential and sender
configuration already exist; do not recreate credentials just because the
current key cannot read the provider's domain-status endpoint.

Engineering will check the configured sender against current DNS/provider
evidence, send to the controlled inbox, record the provider message identifiers,
and verify usable, expiring invitation/recovery links. A successful API response
alone is not inbox delivery. The recipient must confirm receipt and follow the
test links through the private access arrangement. Until then, the private
outbox remains clearly labelled. A link sent to someone without working private
access is not a completed recovery workflow.

## 3. Approve the existing Backblaze B2 destination and provide scoped access

**Blocks:** encrypted offsite upload/download and an offsite restoration proof.
No approved destination or usable backup credentials were found in the inspected
secure configuration. The legacy backup scripts do not back up the new system.

The selected transport is **Backblaze B2's S3-compatible API**, consistent with
the recorded project direction. Use an owner-approved private bucket dedicated
to the **new** QuillMD system, with prefix `quillmd-fresh/synthetic/`. Provide its
S3 endpoint, region and bucket name. If no approved bucket exists, its creation
and any account spending are owner actions; the agent will not purchase or
provision them automatically. [Backblaze S3 API](https://www.backblaze.com/docs/cloud-storage-s3-compatible-api)

Create a standard application key restricted to that bucket and prefix, with
`listFiles`, `readFiles` and `writeFiles` capabilities. Keep `deleteFiles`, bucket
administration and key administration absent. Use Backblaze's Native API/CLI
custom capabilities if the Dashboard's broad Read and Write preset includes
delete permission. The scoped S3 workflow will address the known bucket directly
and does not need permission to list all bucket names. Backblaze supports bucket
and filename-prefix restrictions; use a standard key, not the master key.
[Application keys](https://www.backblaze.com/docs/cloud-storage-application-keys)

Transfer the key ID and application key through the same protected SSH/SFTP or
secret-manager channel into an operator-only file under
`/opt/meddoc-pro/rebuild/.runtime/backup-secrets/`. The application service must
not receive these credentials. Engineering will provide the exact adapter
configuration template before activation, validate the scope, and never print
the values.

Engineering defaults for this synthetic beta are one encrypted backup daily at
04:30 UTC, a 24-hour recovery-point target, a two-hour recovery-time target and
30 days of recoverable daily snapshots. These are targets until measured.
Retention deletion stays disabled until the first remote round trip and restore
pass, then uses a reviewed rule restricted to the dedicated prefix. The uploader
retains no delete capability. A Backblaze lifecycle rule must account for both
hiding and deletion; merely deleting old versions does not expire unique backup
names. [Lifecycle rules](https://www.backblaze.com/docs/cloud-storage-lifecycle-rules)

Place a recovery copy of the encryption key in your existing owner-controlled
encrypted password vault, separate from both the VPS and the backup bucket.
Record the responsible custodian and vault item reference, not the key itself.
The restore exercise must demonstrate recovery using that separately held copy.
Use the designated controlled owner inbox for backup-failure alerts once delivery
is verified. No backup is called offsite-restorable until downloaded ciphertext,
authenticated manifest, every file hash, restored table hashes and invariants
have passed. Patient-data agreements and processing controls must be verified
before this destination receives anything beyond synthetic data.

## 4. Supply authentic provider cost evidence

**Blocks:** provider-cost reconciliation, not further synthetic implementation.

Securely supply Anthropic and Deepgram usage/cost exports or authorized
billing-report access covering the recorded synthetic jobs, together with the
applicable account rates, discounts and promotional-credit treatment. Invoice
evidence should cover the same billing period. No general administrator key is
requested when an authentic export can answer the question.

Engineering will match a small batch by provider request/resource ID, timestamps,
usage quantities and charged amount. Configured-rate arithmetic, provider-reported
cost and invoice reconciliation remain separate evidence levels. The two early
missing receipts remain unreconciled exceptions unless authentic provider
evidence can recover them; no replacement history will be invented. Confirm the
business definition of billable provider cost before paid use, including how
account credits/discounts, refunds and taxes affect disclosures.

## 5. Supply only launch-specific content rights or blank forms

**CPT stays unavailable.** To enable it, provide the licensed dataset or licensed
terminology API access and the contract granting QuillMD's actual use, display,
distribution and user scope. A license identifier alone is insufficient. No CPT
license is being purchased automatically.

Word templates, including all 28 WM IOV content controls and completed-document
formatting, are already required for the first release. Scanned forms are
deferred. The qualified Word implementation covers the accepted WM IOV original with
28 content controls, 90 answer locations and 14 evidence-bound review
requirements, alongside the existing DOCX subset and visible text-field AcroForm
PDFs. Check the latest private checkpoint for activation status. Native Word
appearance acceptance remains a release check; evaluation rendering uses
substituted fonts and is recorded with that limit. No further template-scope decision
or SDK purchase is currently requested; any purchase recommendation must name
the specific required case that cannot be met by the qualified implementation.

## 6. Arrange the independent test and patient-data release evidence

Provide the independent tester's name, SSH public key, UTC test window and
emergency contact for the prepared [private scope](pentest-scope.md). Testing
uses fresh synthetic accounts on the exact deployed release. Internal automated
checks do not substitute for an independent test or finding retest.

Before real patient data or public release, supply the signed patient-data
agreements and approved processing-region/retention controls for the actual
providers and storage, then close the documented security, storage, backup and
independent-test gates. These are external evidence requirements, not grounds
to pause unrelated implementation. Public maintenance and the synthetic-only
gate remain active until the release evidence supports changing them.
