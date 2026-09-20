# Private preview form activation — declared 2026-09-20

The owner authorizes replacing browser-native Basic authentication with a normal
private-preview sign-in page, testing and activating the repair with rollback
protection, and continuing the previously approved two-email verification.

## Intended changes

- Activate the reviewed, CI-cited merged application code on the existing three
  private services. Add only the explicit preview-form enable setting and update
  the honest served revision in the protected environment. Preserve every other
  environment value, its owner and0600 permissions, and all service policies.
- Replace only the dedicated `/etc/nginx/sites-available/quillmd-email-preview`
  file. Keep the9443 listener, certificate, upstream, host restriction and
  disabled access logs. Remove native Basic authentication only after the
  application gate is running and verified. Overwrite the preview marker at the
  proxy. Preserve Secure/HttpOnly cookies; use Lax only for the separate preview
  cookie so email navigations work, retaining existing account-cookie policy.
- Use existing Django sessions, forms, CSRF protection and atomic rate limiting.
  Keep preview authentication distinct from individual accounts and administrator
  MFA. Return destinations and email tokens stay server-side during preview
  sign-in. Never replay an intercepted POST or accept external return paths.
- No schema migration, SDK change, clinical generation change, asset redesign,
  public443 change, firewall/SSH/DNS change, reviewer activation or provider call.

## Preservation and rollback

Before mutation, retain an operator-owned0600 environment snapshot and the exact
old dedicated nginx bytes/checksum. Verify exact release CI. While services are
stopped, capture every table/row, schema/constraints/indexes and private-file
inventory. After restart, verify those unchanged before any browser test can
create normal sessions/audit records. Verify dedicated UID and process boundary
proofs, unchanged service policies and public maintenance.

Rollback restores the previous dedicated Basic-auth configuration first, then
disables the new preview gate and restarts only the private services on the same
reviewed code. The running revision must continue to identify that actual code;
never label new code as the older revision. This is a protection/configuration
rollback, not a database rollback. Existing records and audit history are never
rewritten. Test the rollback configuration path and retain its evidence.

If activation fails, capture actual state and restore the prior gate before any
further attempt. Keep every failed attempt/report. No global cleanup or pruning.

## Verification and email bounds

Use isolated synthetic candidate fixtures for genuine invitation/recovery
acceptance and replay tests. Check Chrome and Edge, wrong credentials, refresh,
expiry, CSRF, return paths, API/file protection and application/MFA independence.
Label operator-driven browser tests separately from owner inbox interaction.

Served verification may create normal preview sessions and audit/rate-limit rows
and must identify those additions explicitly. Preserve existing clinical/account,
welcome-credit and Stripe records. The already emailed owner invitation remains
unchanged and must not be replaced or consumed by operator tests. Continue its
normal owner acceptance and the one approved recovery only after access works.
Provider acceptance, delivery, inbox receipt and completed workflows are separate
evidence. No live charge, purchase or additional clinical provider job.
