# Private application hosting and preserved infrastructure

The root compose file now describes only the existing PostgreSQL, Redis, MinIO,
Caddy and marketing services. Their existing environment expressions, ports,
mounts, images, limits and health checks are preserved. Caddy depends only on
marketing. Existing legacy/mixed volume declarations remain to avoid treating a
configuration edit as proof that their contents are disposable. The old backup
scheduler and application/worker services are retired. Old QA compose overrides
are removed because the replacement does not use the old application.

The worktree `Caddyfile` retains public hostname blocks and internal TLS, and
preserves the marketing route. Doctor/admin hosts return HTTP 503 with
`Retry-After: 3600` and `Cache-Control: no-store`; the retired CRM host returns
HTTP 410. Activation completed on 2026-09-17; public app/admin now return these maintenance responses. **Editing a worktree does not deploy configuration.** The
running Caddy container binds `/opt/meddoc-pro/Caddyfile`. Review and declare future changes before applying them through the repository process. Git can replace a file inode while a running Docker bind retains the old one: validate/load exact tracked shared-tree bytes through stdin and compare live responses. Never recreate the
shared stack from a worktree: relative binds would point at that worktree.

The fresh Django application has separate doctor/admin processes:

| Surface | Private listener | Process setting |
| --- | --- | --- |
| Doctor | `127.0.0.1:9130` | `QUILLMD_ADMIN_SITE=0` |
| Administrator | `127.0.0.1:9131` | `QUILLMD_ADMIN_SITE=1` |

Both use the fresh application datastore and private file storage. Neither uses
the old production `meddoc` database. Administrator MFA and host-specific
session/CSRF cookies remain enforced by the application. The worker uses the
same fresh database and private files, with independent systemd process supervision. All three `quillmd-fresh-*` units are active/enabled; see activation-judged.md.

Reach the listeners through an SSH tunnel from a trusted workstation:

```bash
ssh -N -L 9130:127.0.0.1:9130 -L 9131:127.0.0.1:9131 <vps-user>@<vps-host>
```

Then open `http://localhost:9130` and `http://localhost:9131`. Synthetic accounts
still authenticate at these addresses. Provider credentials stay in the private
environment and are never passed in command arguments or copied into git.

For eventual public promotion, the intended hosts remain `app.quillmd.com` and
`admin.quillmd.com`. Promotion requires a reviewed deployment that routes each
host to its corresponding process, enables secure cookies/HTTPS, preserves
the nginx trust boundary, and keeps PostgreSQL and file paths private. Host
nginx can reach the loopback listeners; Caddy's container loopback cannot reach
the host listeners. Do not substitute `127.0.0.1:9130` inside a Caddy container
and assume it refers to this VPS. Choose and verify one explicit ingress path
at promotion time. No public proxy to either preview port is installed here.

CI defines fresh Django checks/tests, isolated document tests, Python dependency
audit, marketing production build/audit, a private browser/accessibility workflow,
and the existing secret scan. The browser gate uses a fresh synthetic PostgreSQL
database and a loopback server, runs the document workflow through export, and
checks desktop/mobile accessibility. All 12 browser checks passed locally; a
remote CI result is a separate requirement. Only the nonclinical JSON check
report is uploaded, using an exact file path; screenshots, exports, credentials,
and provider response payloads are excluded.

The old clinical app E2E/accessibility/nightly workflows have been retired.
Required GitHub protection contexts were changed and re-read from the GitHub API on 2026-09-17. They now require these four actual job names: `Fresh application tests`, `Marketing build`, `Private browser
and accessibility`, and `TruffleHog (verified-only, diff-scan)`. Otherwise GitHub
continues waiting for obsolete old-application job names. The exact deployed main commit has passing CI and secret-scan evidence in activation-judged.md; future releases require a fresh citation on their own merge commit.
