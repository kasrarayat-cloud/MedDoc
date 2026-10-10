# QuillMD account recovery and cross-site link repair — 2026-10-10

Prospective declaration. Installed baseline:
`da468e559573ad8b0eed506cb6809f8471593a4d`. Direct owner authority is recorded in
`../rulings/2026-10-10-quillmd-account-recovery.md`.

## Demonstrated defect and expected change

A current valid recovery token for the actual existing account opens the password
form through direct fresh-browser navigation. The same token opened by a link
from another origin returns "Recovery link unavailable": Django's immediate
redirect does not receive the Strict session cookie in the cross-site navigation
chain. Retained served reproduction is protected in
`rebuild/.runtime/account-access-recovery-20261010/served-recovery-get-reproduction-v1.json`.

Replace only the valid raw-token redirect with a non-cacheable confirmation page
whose explicit same-origin continuation uses Django's existing session-held token
and clean set-password URL. Suppress referrers on the token-bearing page and
preserve that stricter per-response policy through the account-origin middleware.
Do not weaken global Strict cookies or alter CSRF, token validation/expiry/reuse,
account eligibility, rate limiting, invite-only registration, MFA or session
invalidation. Invalid/expired tokens remain refused. Existing tests are adapted
to the deliberate continuation; add a real-browser cross-origin regression to
the isolated CI server. No migrations, static assets or provider integrations.

## Installation and account recovery

After focused tests, independent finished-diff refutation and exact-candidate CI,
merge through the reviewed wrapper and cite the exact merge. Use a newly bound
code-only native adapter with the existing drain, encrypted preservation snapshot,
unchanged-schema/reference checks, source permission checks and supported forward
recovery. No ingress change or shared-tree feature checkout. Environment changes
only by release identity; all backup/source pins and rollback assets survive.
Maintain the 28 GiB execution reserve. Runtime code changes are confined to
`rebuild/core/recovery.py`, `rebuild/core/preview_access.py` and
`rebuild/templates/recovery.html`; tests/CI and this authority record may change.

Recover only account `e1a20625-455d-4603-a874-794327b19d10` through the ordinary
canonical HTTPS token reset. A temporary high-entropy password may exist only in
process memory to verify this exact account's login/dashboard/forms, invalid login
and logout in fresh browsers. Deliver a final unused 30-minute password-setting
link through the existing Resend transport to `kasra.rayat@gmail.com` only. Do not
export tokens/passwords or retain them in screenshots, traces, argv or reports.
Preserve accounts, memberships/MFA, documents, approved versions, all accounting
and unknown holds. Expected mutable account fields are password and ordinary
last_login; ordinary sessions/rate-limit/audit rows may change. No model requests,
clinical edits, resets of history, public launch or other-project actions.

Record provider acceptance separately from owner inbox receipt and password choice.
Never claim recovery completed merely because a different QA account signed in.
