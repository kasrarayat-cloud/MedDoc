-- Phase 8 — pilot-followup HIPAA findings
-- ----------------------------------------------------------------------------
-- Two new HIPAA findings tracking work that's deliberately deferred to
-- the post-pilot window. Both seeded as `open` so they appear on the
-- /admin/hipaa Open tab as the canonical "what's still left" list.
--
-- h8-h3-pilot-followup  — H3 disk encryption full implementation.
--                         The pilot launches with documented accepted
--                         risk (Hetzner data-center physical access
--                         controls + auditor sign-off). Full Hetzner-
--                         managed encrypted volumes (Option A) planned
--                         for the first 30 days post-pilot.
--
-- h8-h4-pilot-followup  — H4 non-root containers, deferred portion.
--                         Phase 8 converted MinIO + the four Node app
--                         containers (transcribe-md, transcribe-md-
--                         worker, meddoc-pro, marketing) to non-root.
--                         Postgres, Redis, Caddy, and the postgres-
--                         backup sidecar still run as root and are
--                         covered by this finding for the post-pilot
--                         hardening sweep. Postgres especially — its
--                         data-volume migration is the riskiest of the
--                         remaining four and warrants its own change
--                         window with a tested restore procedure.

INSERT INTO hipaa_findings (id, control, severity, title, detail, status, "createdAt", "updatedAt")
VALUES
  (
    'h8-h3-pilot-followup',
    'H3 / §164.312(a)(2)(iv)',
    'high',
    'Disk encryption at rest — post-pilot full implementation',
    E'Pilot launches with documented accepted risk per Phase 8 H3 review.\n\nCurrent posture:\n- Hetzner CX22 host in Germany; physical access controls per Hetzner data-center compliance.\n- Filesystem-level access controls on the host (postgres + minio volumes are owned by root + 1000 respectively, not world-readable).\n- All transit is TLS (Caddy + HSTS + Let''s Encrypt).\n- PHI-bearing audio in MinIO is in a private bucket requiring the MinIO root credentials (not committed; in .env on the host).\n\nPost-pilot work (Option A from Phase 8 review):\n- Provision Hetzner managed encrypted volume.\n- Stop services; rsync postgres + minio data to encrypted mount.\n- Update compose mounts; restart.\n- Estimated 30-45 min downtime; needs Hetzner snapshot beforehand.\n- Target: first 30 days post-pilot.\n\nOptions B (LUKS in-place) and C (column-level pgcrypto) considered and rejected; Option A is the simplest path that gets full HIPAA Safe Harbor coverage without rewriting query patterns.',
    'open',
    NOW(),
    NOW()
  ),
  (
    'h8-h4-pilot-followup',
    'H4 / §164.312(a)(1)',
    'high',
    'Non-root containers — postgres, redis, caddy, postgres-backup deferred',
    E'Phase 8 H4 work converted the high-traffic + PHI-bearing containers to non-root:\n- minio:        root → 1000:1000 (chown then user: directive)\n- transcribe-md, transcribe-md-worker, meddoc-pro, marketing:\n                already non-root (uid 1001 nextjs/worker)\n\nDeferred to a post-pilot hardening sweep:\n- postgres:     uid 0 (root). Migration is the highest-risk of the\n                remaining four — data dir chown needs a tested restore\n                procedure + change window.\n- redis:        uid 0 (root). Holds session tokens but no PHI; lower\n                stakes but folded into the same sweep for simplicity.\n- caddy:        uid 0 (root). TLS termination only; no PHI on the\n                container itself. Caddy needs root to bind 80/443\n                without setcap.\n- postgres-backup: uid 0 (root). Reads from postgres volume; tied to\n                postgres conversion above.\n\nPlan: schedule a post-pilot maintenance window. Postgres + postgres-\nbackup convert together (shared volume). Caddy needs CAP_NET_BIND_\nSERVICE if dropping root. Redis is straightforward (volume chown +\nuser: 999:999, the official redis image user).',
    'open',
    NOW(),
    NOW()
  );
