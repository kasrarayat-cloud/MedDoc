# Agent 07 — Infrastructure & Operational Security · Summary

## Severity counts
**P0: 3 · P1: 7 · P2: 5 · P3: 3 · Total: 18**

## Top 3 findings
1. **A07-P0-001** — `/etc/ssh/sshd_config` sets `PermitRootLogin yes`, `PasswordAuthentication` is not explicitly disabled, no `AllowUsers`/`AllowGroups`. `last` confirms `root@76.174.150.33` is the active operator account (incl. live session at audit time). Combined with no UFW + no fail2ban, one credential compromise = total host loss.
2. **A07-P0-002** — UFW is installed but `inactive`/`disabled`; no nftables rules. Public listeners include orphan 9010/9020 (no Caddy block matches them), 18789-90 (openclaw sandbox), and 8000 (root uvicorn for an unrelated app). SSH on :22 has no edge throttle.
3. **A07-P0-003** — `/root/ai-deal-hunter/.../uvicorn` runs as **root** on `0.0.0.0:8000` on the same VPS as PHI. Any compromise pivots into the LUKS key file, docker socket, .env. Tenancy boundary broken at host level.

## Coverage
No sampling per brief: full read of all 4 Dockerfiles, Caddyfile (288 lines), docker-compose.yml (588 lines), all 3 GitHub workflows, all infra/scripts (`setup-encrypted-volume.sh`, `backup-offsite-sync.sh`, `minio-offsite-sync.sh`, `postgres-backup/postscript.sh`, `postgres-offsite-cron.sh`, `minio-offsite-cron.sh`, `restore-drill.sh`, `h8-post-reboot.sh`); host config (`/etc/ssh/*`, `/etc/cron.{d,daily,hourly,weekly,monthly}`, `/etc/logrotate.{conf,d/*}`, `/etc/sysctl.{conf,d/*}`, `/etc/modprobe.d/*`, `/etc/fstab`, `/etc/security/limits.conf`, `/etc/apt/apt.conf.d/{20auto-upgrades,50unattended-upgrades}`); `ss -tlnp/-ulnp`, `docker inspect` per-container security flags, `last`, sysctl readout, swap/LUKS state, /etc/meddoc visible at parent layer (interior 750 root-only).

## Positives
1. **Container-runtime hygiene is excellent.** Every production container has `cap_drop: [ALL]`, runs non-root, no `privileged`, no docker.sock mounts, deliberate `mem_limit`/`cpus`/`nofile` ulimits. compose.yml is the strongest single artefact in this audit.
2. **Encryption-at-rest done correctly.** `setup-encrypted-volume.sh` uses LUKS2 + aes-xts-plain64 + 512-bit key + argon2id, generates key with strict umask before writing bytes, atomic moves on partial failure, ERR-trap rollback distinguishes "we created it" vs "pre-existed", systemd unit ordered `Before=docker.service`, fully idempotent. Phase 6.2 age keypair flow (private key offline) is the right threat model.
3. **Strong security headers.** MODE B Caddyfile: HSTS preload max-age=31536000, X-Content-Type-Options, X-Frame-Options SAMEORIGIN, Referrer-Policy strict-origin-when-cross-origin, tight Permissions-Policy, `-Server` removed, CSP enforced (not Report-Only). One caveat in P2-002 about `unsafe-inline`/`unsafe-eval`.
4. **Phase 6.2 cron scripts are well-engineered.** Both have 30-day log rotation, 24h activation grace period, idempotent dirs, per-UTC-date log files, exit-code propagation to Slack. `restore-drill.sh` is a real proof-of-restore (spins ephemeral pgvector on :5433, restores, sanity counts, EXIT-trap cleanup). Activation cron-line wiring is the only outstanding operator step (P2-004).

## Cross-domain hooks
- **Agent 05 (HIPAA, crypto):** P0-003 + P1-006 (unencrypted swap) undermine encryption-at-rest claim.
- **Agent 01 (CI/CD, secrets):** P3-001 (.env perms) + credential-rotation list overlap; workflows otherwise clean (no pull_request_target, no head_ref checkout).
- **Agent 02/05 (network/TLS):** P1-001 (orphan 9010/9020) + P2-003 (no edge rate-limit) are edge-layer fixes.
- **Agent 11 (logging):** P1-007 (3.8 GB journal, 76 MB syslog) is logging-hygiene with security impact.
- **Agent 12 (runbooks/launch):** P2-004 (Phase 6.2 cron not wired) plus all three P0s belong on the launch-readiness gating checklist.
