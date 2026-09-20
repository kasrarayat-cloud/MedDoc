# Controlled private email verification — declared 2026-09-20

Owner authorization: send one invitation and one password-recovery message only
to the explicitly approved owner-controlled inbox, using existing Resend
credentials. Preserve all existing accounts, records, Stripe evidence, public
maintenance, synthetic-only operation and inactive reviewer access.

## Authorized engineering changes

- Add the dedicated password-protected `https://app.quillmd.com:9443` listener
  from `rebuild/deploy/email-private-https.conf`. Reuse the existing valid TLS
  certificate. Install only the named `quillmd-email-preview` nginx config,
  password hash and enabled symlink; validate then gracefully reload nginx.
  Existing vhost bytes and public responses must remain unchanged. No DNS,
  certificate, firewall, shared SSH policy or external reviewer access change.
- Generate one temporary private-preview credential in an operator-owned 0600
  JSON file. Its password is never printed or passed on command lines. Include
  it only in the two approved account emails so the owner can enter the private
  HTTPS gate. Keep gate credentials out of application and proxy logs.
- Copy only the existing Resend key/sender from protected retained configuration
  into the fresh `.env`; preserve all other entries and claude/0600 ownership.
  Configure the exact HTTPS origin, sole approved recipient, private access
  instructions and explicit doctor-only trusted proxy setting. The nginx edge
  replaces forwarding headers, strips Basic authorization upstream and adds
  Secure/HttpOnly/SameSite=Strict to cookies. Backend loopback access and separate
  administrator MFA remain intact.
- Activate the cited merged code, changing only the declared email/settings
  source and release stamp. Restart only the three fresh private services.
  Reuse existing all-table fingerprints, private storage inventories and actual
  service-identity proofs. Preserve every database row, file, email and unit
  policy during activation. No schema, SDK, static asset or clinical generation
  change is authorized here.

## Verification flow and bounds

Before any send: verify normal public maintenance, exact private TLS hostname,
unauthenticated denial, authenticated health and cookies; obtain the owner's
specific confirmation that the HTTPS password prompt opens without TLS warning.
The operator's successful HTTPS probe alone is not browser access evidence.

Independently establish no existing account at the approved address. Snapshot
existing identities/MFA, memberships, wallets and Stripe records. Send through
the normal synthetic owner's team form, pinned to the existing X-ray department
and Employee role. Do not silently choose another department. The recipient
accepts the genuine link, with a synthetic name and their own password.

Only after acceptance, request the single recovery email for that new verified
account through the normal recovery form. Confirm receipt/use with the owner;
do not extract outbox tokens and call that inbox evidence. Check one welcome
grant, exact role/department isolation, password change limited to this account,
old-session rejection, unaffected owner/admin sessions and MFA, and safe link
reuse. Existing isolated expiry/substitution tests remain separately labelled.

All real provider acceptance, delivery-status availability, owner-reported inbox
receipt, link use and application state checks must be recorded separately and
additively. Preserve failures and never automatically resend after an uncertain
outcome. No extra email, live charge, AI call or purchase is authorized by this
verification. No public-release or completed-penetration-test claim.

## Preservation and recovery

Record before/after fingerprints and redacted reports in the protected fresh
runtime. If activation fails, capture actual service/configuration state before
repair; never erase evidence or treat a nonzero exit as proof of no effects.
Keep maintenance and the independent private gate in place throughout. Remove
or disable only the dedicated preview entry when this controlled session is
finished; retain the new synthetic account, audit rows and provider evidence.
