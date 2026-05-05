---
id: A07-P1-005
title: MinIO container uses :latest image tag (unpinned)
severity: P1
domain: infrastructure-opsec
date: 2026-05-04
---

## Issue

`docker-compose.yml` line 165 declares `image: minio/minio:latest`. Every
other production container is pinned to a major-version tag
(`pgvector/pgvector:pg16`, `redis:7-alpine`, `caddy:2-alpine`,
`prodrigestivill/postgres-backup-local:16`). MinIO is the outlier.

`docker compose up -d --force-recreate minio` will silently roll forward
to whatever the registry's `latest` points at the moment, with no
operator review. Currently resolved digest:
`sha256:69b2ec208575b69597784255eec6fa6a2985ee9e1a47f4411a51f7f5fdd193a9`.

## Evidence

```
$ grep -nE 'image:' /opt/meddoc-pro/docker-compose.yml
21:    image: pgvector/pgvector:pg16
137:   image: redis:7-alpine
165:   image: minio/minio:latest                 # ← unpinned
205:   image: caddy:2-alpine
515:   image: prodrigestivill/postgres-backup-local:16
```

```
$ docker inspect meddoc-pro-minio-1 --format '{{.Config.Image}} → {{.Image}}'
minio/minio:latest → sha256:69b2ec208575b69597784255eec6fa6a2985ee9e1a47f4411a51f7f5fdd193a9
```

## Risk

- Reproducibility: a colleague rebuilding from this compose tomorrow gets
  whatever MinIO ships that day, possibly with breaking changes (MinIO
  has had API-deprecation breakages in `mc` syntax and SSE-S3 default
  changes in past months — Phase 6.2 explicitly comments on `mc` syntax
  shifts).
- Unreviewed upgrade: a `force-recreate` (used elsewhere in runbooks)
  pulls in possibly-vulnerable or possibly-incompatible binaries with
  zero pre-deploy review.
- MinIO is the PHI-audio store. Silent upgrades that change SSE-S3
  defaults could degrade encryption-at-rest posture without alerting.

## Recommended fix

Pin to a release tag. MinIO publishes timestamped tags in the form
`RELEASE.YYYY-MM-DDTHH-MM-SSZ`:

```diff
-    image: minio/minio:latest
+    image: minio/minio:RELEASE.2026-04-22T17-44-22Z   # current released GA
```

Or pin to digest (most deterministic):
```diff
-    image: minio/minio:latest
+    image: minio/minio@sha256:69b2ec208575b69597784255eec6fa6a2985ee9e1a47f4411a51f7f5fdd193a9
```

Add a quarterly cadence to `docs/runbooks/IMAGE_UPGRADE.md` for reviewing
+ bumping each pinned tag, with smoke-test gates (mc client syntax sanity
+ presigned URL roundtrip + SSE-S3 default check).

Same pattern should apply to all `:NN-alpine` / `:NN` tags — they are
better than `:latest` but still float on patch versions. Pinning by
digest gets you bit-for-bit reproducibility.
