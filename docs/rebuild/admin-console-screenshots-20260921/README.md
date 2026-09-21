# Administration console — screenshots, 2026-09-21

Captured with a real Chromium against the **isolated** verification stack: worktree
`.worktrees/admin-console`, dedicated PostgreSQL on `127.0.0.1:55441` (`quillmd_admin_ci`),
gunicorn on `127.0.0.1:9161` with `QUILLMD_ADMIN_SITE=1`. Production `:9130`/`:9131` was untouched
throughout.

Signed in as `admin@synthetic.quillmd.invalid` with a **real TOTP code** against the confirmed
authenticator `seed_private` creates — administrator MFA was not relaxed for any of these.

All data is synthetic, built by `manage.py seed_private` and `manage.py seed_admin_demo`. No
screen in this console renders clinical text, patient names or note content, and none of these
images contains any.

Full page at 1440px wide, then downscaled to 960px JPEG so a reviewer can read them in the pull
request without the repository carrying 8 MB of lossless PNG.

| file | what it shows |
|---|---|
| `01-overview.jpg` | The console with money on it: charged to paid vs promotional balances, provider cost as configured estimate **and** evidence-reconciled, costs carried by QuillMD, paid in, refunded out, promotional credit granted; position as of now; "needs someone"; and the Processing panel reporting **"No worker has run recently"** with $17.55 of customer funds still reserved. |
| `02-overview-dated.jpg` | The same page under `?from=2026-09-21&to=2026-09-21`. This request used to return a **500** — `User` extends `AbstractUser` and has no `created_at`. |
| `03-services.jpg` | Configured separated from Observed. Backup status read from a **published** row; ffprobe/ffmpeg presence measured in-process; account-email delivery counted from the audit rows every send already writes; private credentials reported by shape only, never value. |
| `04-organizations.jpg` | The organization tree, effective access per membership, the `organization_pays` flag, outstanding invitations with a revoke control, and the **"This department has no active owner"** warning firing on a real synthetic condition. |
| `05-account.jpg` | One account: enabled/verified/**MFA enrolment**, promotional vs paid vs reserved vs charged, the organization wallet that pays, memberships with effective access, a payment showing `paid · refunded` with gross/refunded/net, and the audit trail of actions **by** the account and **on** it. |
| `06-charge-evidence.jpg` | The charge explained end to end: `$0.02562` at recorded rates → `×1.5 = $0.03843` charged → invoice evidence `$0.18` → adjustment `+$0.23157` applied → ledger movements naming the promotional and paid balances with before/after → **net charge `$0.27`**, both wallets "Ledger agrees". |
| `07-audit.jpg` | Audit history with a date range, an **exact** action picker beside the substring box, organization/department columns, pivots to the actor and the target, and `details` rendered as a readable list. |
| `08-jobs-awaiting-decision.jpg` | `?job_state=reconciliation` — the jobs waiting on the owner, reached in one click from the "Awaiting your decision" tile. |
| `09-unreadable-date.jpg` | `?from=banana&to=2026-09-21`. The window is **not** applied and the page says so. Previously the readable bound stayed in force, so the page narrowed every figure while displaying "these figures cover every record". |
