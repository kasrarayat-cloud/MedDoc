# Private activation judgment — 2026-09-17

Declaration: `docs/foundation/mutations/20260917-quillmd-private-activation.md`, committed in f2012ea0 before execution. Implementation PR #1173 merged as **61879a61f56eaf85e8e8f764f748355abbc53906**. Exact merge citation: CI35203116442 and secrets-scan35203116365, both attempt1/success; fresh application, marketing and browser/accessibility jobs passed. The four replacement branch-protection contexts were read back; all other settings were unchanged.

## Result

Private activation completed **09:13:12 UTC**. Shared main advanced by fast-forward and has zero tracked changes. The fresh runtime moved from its implementation worktree into `/opt/meddoc-pro/rebuild`; only newly created synthetic data and its own new credentials moved. Three fresh systemd units are enabled and active under claude. Their doctor/admin sockets bind only127.0.0.1:9130/9131; PostgreSQL binds only127.0.0.1:55438. No real reboot was performed.

All six declared preserved container IDs, image IDs and mount source/destination lists compare unchanged. Marketing/www respond200; app/admin503; retired pro410. The old PostgreSQL database still contains exactly7 preserved marketing waitlist entries. Fresh environment/seed credentials are0600, runtime0700. DNS, certificates, nginx and shared service configurations were not repointed.

The post-activation browser proof passed **11 checks**,09:13:32–09:14:01UTC: new synthetic DOCX upload, real kernel-isolated parser under systemd restrictions, mappingv2, live Anthropic source evidence, clinician review/finalization/export, original question/full-answer checks, separate admin MFA and receipt visibility. Configured-rate provider cost **$0.003270**, exact charge **$0.004905**, disclosed reservation **$0.1912635**, paid entirely from the synthetic user's personal promotional balance. Download/scratch files were removed; only sanitized JSON remains.

A separate real Deepgram test used6.43seconds of locally synthesized speech. Wrist pain, no-fracture negation and follow-up were retained. Eleven receipt/adoption/ledger assertions passed: configured-rate cost **$0.000460816700**, exact charge **$0.000691225050**. One sample is not a clinical accuracy validation.

## Failures repaired and retested

1. The root installer initially lacked the host PID namespace and could not connect to the host systemd socket. No unit started. A read-only probe with `--pid=host` reached the actual manager; then all installed unit/drop-in bytes were checked against reviewed source and the three exact units were enabled/started. The installer now carries that flag. No privileged mode or network access was needed by this helper; the host bind was read-only except the unit directory.
2. A first resume attempt supplied a heredoc through the mutation wrapper; the wrapper did not forward stdin. Its zero exit did not start anything. Explicit `systemctl is-active` showed all three inactive, so this was not accepted as success. The resume code was then executed from a private file and actual active/enabled states were verified.
3. Git checkout replaced the host Caddyfile inode, while the running single-file Docker bind still held the old inode. Hash comparison caught this before a misleading reload. Caddy validated and loaded the exact tracked shared-tree bytes through stdin. Live HTTP responses and protected container/mount identities were verified. Shared ingress was not recreated. Future reloads must also use current tracked bytes, not assume the running bind already sees a newly checked-out inode.
4. Final source inspection found Dependabot still watching removed workspaces. Its configuration now targets current marketing/shared/npm, Actions, marketing Docker, and the fresh Python manifest. The Python manifest was renamed to standard `requirements.txt` with **byte-identical pins**, so it can be maintained by standard tooling. No installed dependency version changed.

## Final artifact retirement

Under the same committed scope, **7,431 pinned old build/artifact leaves** (~383.9MB logical regular-file bytes) were removed from the seven deleted app/package/sidecar directories at09:14:28UTC. No matching live Docker mounts or readable process references existed. One differing service-credential copy was preserved, hash-verified, at `.retained-service-credentials/.env.old-standalone` (0600/0700 directory); root.env remained unchanged. Shared root node_modules was excluded because two other worktrees link to it. An apparent writer process was verified to contain only echo/sleep and was left alone.

## Durable evidence

Private, gitignored runtime files: `activation-result.json`, `activated-browser-verification.json`, `voice-speech-verification.json`, `activation-artifacts-cleanup-result.json`, `branch-protection-before.json`, `branch-protection-after.json`, and `resend-domain-verification.json`. Deployment logs in `docs/deploy-logs/` retain the initial failure and final success. These contain no published credentials or filled clinical documents. Tracked initial cleanup manifests/results remain in docs/rebuild.

Resend's existing key was recognized as send-only by a read-only API request; domain-list permission was denied. No email was sent. Stripe test payments, CPT licensed content, advanced document SDK support, account-specific invoice reconciliation and patient-data agreements/controls remain explicit external gates in CHECKPOINT.md. Public promotion remains unauthorized by this private activation record.
