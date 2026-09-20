# Controlled invitation and recovery verification — 2026-09-20

## Preparation state

The owner has supplied the controlled recipient. It has no existing fresh
application account. The selected new account will be an **Employee** in the
existing **X-ray** department; existing owner/admin identities are preserved.
The initial read-only baseline records all account-password and MFA-key hashes,
the eligible department, and the unchanged Stripe counts (three Payment rows,
seven webhook events, 26 ledger entries). No message was sent during preparation.

The existing Resend sender/key are retained in protected configuration. Current
DNS has the sender's SPF, MX, DKIM and DMARC records. The key's last authenticated
domain-list request was denied as send-only. DNS and the historical verification
flag are not an independently readable Resend domain-status result. Record this
limit and actual provider acceptance separately; do not request a new sending key
or claim inbox delivery from an API response.

## Private browser access

The dedicated planned origin is `https://app.quillmd.com:9443`. It reuses the
existing trusted certificate (valid through 2026-10-31), fixed doctor upstream,
and an independent HTTP Basic access gate. Public app/admin on port443 remain in
maintenance. Marketing staging is a separate site and is not repurposed.

The approved recipient receives the private gate login in each of the two
account emails. It is distinct from the new account password. The exact original
HTTPS link must work without rewriting its hostname or path. Before sending,
the operator verifies TLS and gate behavior, then asks the owner only to confirm
the browser opens the password prompt without a certificate warning.

Nginx overwrites forwarding headers, strips the Basic credential upstream,
marks cookies Secure/HttpOnly/SameSite=Strict, and disables request logs on this
dedicated listener. Only the doctor process explicitly trusts the approved
loopback proxy's scheme header. The backend loopback listeners and separate
administrator MFA remain available. No DNS, firewall, certificate, shared SSH
policy or external reviewer activation is part of this change.

## Separate evidence stages

1. Private HTTPS reachability: operator TLS/gate checks **and** actual owner
   browser confirmation before any email.
2. One real invitation through the normal synthetic owner's team form, pinned
   to the independently checked X-ray UUID and Employee role.
3. Record provider acceptance/message ID; provider delivery event if readable;
   owner-confirmed inbox receipt; owner acceptance through the genuine link.
4. Verify one new nonstaff verified account, one intended membership, no foreign
   department/organization access, and exactly one personal $10 welcome grant.
5. Establish a real authenticated session for the new user, then request one
   recovery email through the normal recovery form. Preserve owner/admin sessions.
6. Record recovery receipt and successful link use; verify password change limited
   to that account, old-session rejection, unchanged unrelated sessions/MFA and
   no duplicate credit. Test safe reuse; label isolated expiry tests separately.

The runner's `passed` field is explicitly **submission-checks-only**. Recovery's
generic acknowledgment does not prove any email was sent. Final acceptance needs
the separate inbox/application evidence above. Reports and execution claims are
exclusive; later owner confirmations are appended as new records. An uncertain
send requires inspection, not another automatic send.

## Focused repairs and verification limits

- Replaced the runner's localhost instructions and HTTPS boolean-only check with
  exact-origin, certificate-validated, gated HTTPS checks and owner browser proof.
- Removed silent department fallback, combined invitation/recovery execution,
  and passing results after failed or rate-limited invitation delivery.
- Added a recipient allowlist at the real transport boundary. Optional private
  gate credentials go only to the sole approved invitation/recovery recipient;
  they never enter audit metadata or failure outbox records.
- A configuration-writer refutation reproduced a dotenv/systemd quoting mismatch.
  The repair is exercised against both dotenv and the installed systemd parser
  using anonymous synthetic data. No real environment was used by that test.
- Pre-execution review found and repaired premature HTTPS completion reporting
  and incomplete schema-preservation checks in private activation scripts.

Local isolated evidence: 21 transport/settings tests, 17 runner tests, and eight
configuration tests passed without skips. A first configuration test invocation
used the repository root rather than `rebuild` and failed module import; the
corrected invocation passed. An optional SQLite attempt could not run existing
PostgreSQL-specific migrations; nothing was bypassed. Required PostgreSQL CI is
separate evidence and must pass on the exact release before activation.

Protected evidence root: `rebuild/.runtime/email-verification-20260920/`.
The continuation checkpoint records actual activation, owner interaction and
provider results as they happen; this preparation report does not assert them.
