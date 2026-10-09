# QuillMD: owner-authorized direct account sign-in

Recorded prospectively on 2026-10-09, before native installation. The owner
explicitly authorized removal of the separate shared private-preview gate from
the complete request path and authorized installation and normal-HTTPS tests.
This decision supersedes earlier instructions to retain that gate. It does not
certify historical unrelated deployment approval or replace earlier evidence.

The exact owner record is
`/opt/meddoc-pro/rebuild/.runtime/direct-account-signin-20261009/owner-direct-account-access-decision-v1.json`,
SHA-256 `de60ffef89828163607f26d8b32ed1d6d1fde0e3c948442e30bc30738cec1db7`.
The installed starting revision is `0042cf7f7f0b437b3baeaf1c40dab66912294fef`.
The installer binds the exact descendant on merged `origin/main`, its complete
changed-path manifest and required successful CI before any service action.

## Expected changes

- Normal `https://app.quillmd.com/` enters ordinary individual email/password
  login. Existing account credentials are retained; there is no shared key,
  preview grant or preview-cookie prerequisite.
- Shared-gate middleware, credential settings, form and email instructions are
  removed. Retired preview paths discard obsolete tokens and redirect safely to
  `/login/`; logout returns there. Old preview browser cookies may be expired,
  but historical preview session/audit rows are not deleted or rewritten.
- Standalone registration is unavailable; valid invitations remain supported.
- The exact QuillMD suffix in `/etc/nginx/sites-available/quillmd` switches its
  trusted transport header to `X-QuillMD-Account: 1`. All preceding host rules
  remain byte-identical. The separate fixed
  `/etc/nginx/sites-available/quillmd-email-preview` listener becomes a canonical
  redirect to normal account login. Existing enabled links remain unchanged.
- Exactly these environment keys may change: `QUILLMD_RELEASE_SHA`,
  `QUILLMD_DIRECT_ACCOUNT_ACCESS_ENABLED=1`, `QUILLMD_PREVIEW_AUTH_ENABLED=0`,
  `QUILLMD_OWNER_NORMAL_ORIGIN_ENABLED=1`,
  `QUILLMD_APP_BASE_URL=https://app.quillmd.com`. The obsolete
  `QUILLMD_EMAIL_PRIVATE_ACCESS_USERNAME` and
  `QUILLMD_EMAIL_PRIVATE_ACCESS_PASSWORD` assignments are removed. All other
  environment bytes and effective values remain unchanged.
- Historical shared-gate activation/recovery executors refuse when the direct
  account policy is installed. A missing decision record never authorizes
  restoring the obsolete gate. Read-only evidence and backup helpers remain
  usable. The co-tenant check expects the authorized account-login redirect.

## Required preservation and execution controls

Only the three native QuillMD units may stop/start. Nginx is syntax checked and
reloaded only to activate the two declared QuillMD route changes. No VoiceAssist
or other project files, services, deployments, accounts or shared Docker
resources are modified. Foreign configuration and service observations are
compared through the existing bounded preservation procedure, including its
recorded retention witness; unexplained differences remain failures.

Invite-only access, administrator MFA, account verification, tenant permissions,
CSRF, rate limits, synthetic-only enforcement, databases, approved template
versions, originals, exports, Word implementation, static assets, mail, API
accounting, historical failure records and rollback assets are preserved. No
migration, source reset, password reset, public signup or paid provider request
is authorized. The separate `09e58cf9c46217321549e7ff59f2d9c217958333` private
demonstration and the unknown request's `$0.10` reservation remain unchanged.

Capture an authenticated fresh encrypted QuillMD backup and operation baseline
before stopping services. Keep original environment encrypted and ingress bytes
protected. Require at least 28 GiB available space before and after installation.
Publish source through a fast-forward from the clean shared `main` tree, using
umask `022` only for the Git child while evidence remains private under `077`.
Verify Git bytes, index/file modes and service-identity readability before every
start, including recovery. Do not start a partial or incoherent installation.

Compare all 38 application tables, schema, sequences and referenced files around
installation. Accept only the declared environment/source/ingress delta. Retain
the initial baseline and every failure. Interrupted publication must recover a
verified coherent known revision with its matching account policy and ingress;
do not silently weaken checks or reset source.

## Acceptance

Use existing authorized synthetic accounts with unchanged credentials. Check
fresh browsers and old preview cookies; valid and invalid login; anonymous
protected pages, APIs and downloads; invitation-only enrollment; logout;
administrator password followed by required MFA; and authenticated doctor/admin
surfaces on normal HTTPS. Inspect existing approved templates and downloaded
synthetic export bytes without creating provider work. Record served revision,
screenshots and precise results. Public DNS/TLS checks from outside the VPS must
use normal port 443, without a tunnel or hostname override. Distinguish those
outside observations from authenticated browser execution on the VPS.
