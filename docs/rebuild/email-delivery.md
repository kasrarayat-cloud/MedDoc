# Optional account email delivery

**2026-09-20 continuation:** the controlled owner recipient is now established.
Private HTTPS and separate real invitation/recovery verification are being
prepared; see [the current runbook](private-email-verification-20260920.md).
The following entries preserve the earlier outbox-only baseline. They do not
describe later execution unless the continuation checkpoint records it.

Current state: the private file outbox remains the default. The Resend adapter
is implemented and tested with mocked HTTP only. No email was sent. A read-only domain-list request recognized the existing key as send-only and refused the requested read permission; that is not sender-verification evidence.
Successful API acceptance does not establish inbox delivery.

The preserved `/opt/meddoc-pro/.env` contains the variable names
`RESEND_API_KEY`, `RESEND_FROM`, and `RESEND_FROM_VERIFIED`. Values were not
printed. The fresh application does not import old account data or application
settings. Sending acceptance, sender domain status and inbox delivery remain unverified. The key was recognized by the provider as restricted to sending; no send was attempted.

## Explicit activation

Set these in the fresh application's protected environment only after the sender
domain is verified and the chosen application URL is reachable by recipients:

```dotenv
QUILLMD_EMAIL_MODE=resend
QUILLMD_EMAIL_FROM=QuillMD <verification@YOUR_VERIFIED_DOMAIN>
QUILLMD_EMAIL_VERIFIED_DOMAIN=YOUR_VERIFIED_DOMAIN
QUILLMD_APP_BASE_URL=https://app.quillmd.com
RESEND_API_KEY=YOUR_EXISTING_PROVIDER_KEY
```

Instead of copying the existing key, set
`QUILLMD_RESEND_ENV_FILE=/opt/meddoc-pro/.env`. The adapter reads only
`RESEND_API_KEY` and `RESEND_FROM` from that file when the corresponding new
setting is absent. It refuses symlink files and files readable by group/others;
the file must be a private regular file. It never imports the old database URL,
email auto-confirm rules, or other old application settings. The old
`RESEND_FROM_VERIFIED` value is not treated as current verification evidence.

`QUILLMD_EMAIL_VERIFIED_DOMAIN` must equal the configured sender address's
domain. This setting is an operator assertion after checking Resend, not an API
domain verification result. `QUILLMD_APP_BASE_URL` must be HTTPS, must use an
allowed application hostname, and cannot be localhost in Resend mode. DNS and
private-access routing are unchanged by these settings. Recipients still need
authorized access to the private preview.

With `QUILLMD_EMAIL_MODE=file` or the setting absent, account messages stay in
`.runtime/mail`. Direct use of the Resend backend also refuses unless mode is
explicitly `resend`. No configuration or credentials are changed by tests.

## Behavior and recovery

Verification, invitation and recovery messages use Django's backend interface with
HTTPX and Resend's documented `POST https://api.resend.com/emails` API. Only
one-recipient plain-text account emails are accepted by this adapter; attachments,
CC/BCC, HTML alternatives and oversized messages are rejected explicitly. The
API request uses a deterministic idempotency key derived from the complete
payload, a bounded timeout, and no redirects or automatic retries. Resend's
idempotency window is 24 hours. [Send Email API](https://resend.com/docs/api-reference/emails/send-email),
[idempotency documentation](https://resend.com/docs/dashboard/emails/idempotency-keys).

The application records provider acceptance separately from private-outbox
creation and failure. Audit metadata contains the purpose, resource ID,
provider message ID or error class; it excludes email bodies, tokens,
credentials and provider error responses.

A failed or uncertain send leaves the newly created account unverified and
does not grant credit. It attempts to stage the same link in the private
outbox for administrator recovery. Invitations similarly remain unaccepted.
The user receives an honest failure message instead of HTTP 500. Outbox files
are mode 0600 and the directory is mode 0700 before sensitive content is written.
If both provider and local storage fail, the audit says recovery was not staged;
an administrator must issue a new verification token after repairing delivery.
There is no automatic resend or claim of completed inbox delivery.

Remaining external checks: confirm the existing key has sending access; verify
the exact chosen sender domain and required DNS records in Resend; select the
sender address and recipient-accessible HTTPS application origin; then perform
an explicitly authorized synthetic recipient delivery check. The required DNS
records are those issued for the chosen domain by Resend, not assumed values.
[Verified domains](https://resend.com/docs/dashboard/domains/introduction).

Tests: `core.tests.test_email` plus the existing registration/invitation workflow
tests. They use synthetic addresses and mock every provider HTTP request.

## Private beta sandbox restriction

The hardened app units hide the preserved root environment and operational credentials. Before enabling Resend, copy only the chosen provider key/sender into the fresh protected environment; do not broaden service filesystem access to old/shared credentials. The existing protected-file adapter remains useful to an authorized operator during configuration, but its legacy file path is unavailable inside the hardened app service. Public app/admin remain in maintenance, so a recipient-accessible authenticated HTTPS origin is also needed before live account-email links are usable outside the SSH-tunnel preview.
