---
id: A09-P2-001
title: Upload routes do MinIO put → DB update → BullMQ enqueue across three separate transactions — partial-failure orphans
severity: P2
domain: data-integrity / atomicity
---

## Issue
The three input-shape routes (`POST /api/visits/[id]/upload`,
`POST /api/visits/[id]/dictation/upload`, `POST /api/visits/[id]/text`) all
follow the same three-step write pattern:

1. PUT object into MinIO (or write rawTextInput at step 2).
2. UPDATE the visit row (audioKey, status, mime type, …).
3. ENQUEUE the BullMQ job.

These are three separate atomicity boundaries (S3 PUT + Postgres TX + Redis
ZADD). Failure modes:

- **MinIO put succeeds, DB update fails**: object orphaned in bucket. The
  T-M12 orphan sweep eventually catches it, but only when
  MINIO_ORPHAN_CLEANUP_ENABLED=true (currently false in prod per the env
  conventions).
- **MinIO put + DB update succeed, enqueue fails**: visit is QUEUED with
  an audioKey but no job in Redis. The user sees "QUEUED" forever. The
  upload route does return 502 here, but the row stays. There is no cron
  that re-enqueues stale-QUEUED visits.
- **MinIO put succeeds, DB update partially writes (network blip)**:
  Prisma single-row update is atomic at the row level so this case is
  benign — but if a future maintainer changes the update to a
  multi-statement transaction, partial writes become possible.

The /upload route handles the orphan-from-reupload case
(`apps/transcribe-md/src/app/api/visits/[id]/upload/route.ts:199-206`)
by deleting the previous audioKey AFTER the DB update lands — which is
correct (delete-orphan-after-success). But there's no compensating
delete for case (a) above.

## Evidence
`apps/transcribe-md/src/app/api/visits/[id]/upload/route.ts:147-234`:
```ts
try {
  await putAudioStream(objectKey, nodeReadable, contentLength, mimeType);
} catch (err) { … }

await prisma.transcribeVisit.update({
  where: { id: visitId },
  data: { audioKey: objectKey, … },
});
// no try/catch around update — relies on withApiHandler

// best-effort orphan delete of PREVIOUS audioKey

void logAudit(…);

try {
  await enqueueProcessVisit(visitId, userId);
} catch (err) {
  return apiError('Upload stored, but the worker queue is unreachable. Please refresh and try again.', 502, …);
}
```

If `prisma.transcribeVisit.update` throws (Postgres unreachable, FK
constraint, etc), `withApiHandler` catches it, returns 500, but the MinIO
object is in the bucket. The audioKey on the visit is unchanged (still
null or the old key). T-M12 orphan sweep is the only thing that recovers.

## Risk
P2 — orphan rows in MinIO + occasional zombie QUEUED visits. Severity P2
because:
- The data isn't lost, just stranded. T-M12 cleanup eventually reconciles.
- The user can re-upload, which overwrites audioKey + (now correctly)
  deletes the previous orphan via the lines 199-206 fallback.
- Zero PHI exposure.

But: at pre-pilot scale, ops will see "QUEUED-but-no-job" rows occasionally
and not have a clean recovery path. There's also the cost angle — orphan
audio in MinIO sits there for 30 days (CLEANUP_RETENTION_DAYS), accumulating.

## Recommended fix
Restructure the upload routes to do:

1. Generate the audioKey (deterministic from visitId).
2. INSERT/UPDATE the DB row first with the audioKey (row reservation).
3. PUT to MinIO.
4. UPDATE status + audioUploadedAt to mark the upload complete.
5. ENQUEUE.

If step 3 fails, step 4 doesn't run and a separate sweep can detect "row
has audioKey but audioUploadedAt is null" and force a retry. If step 5
fails, a separate cron re-enqueues based on `status=QUEUED AND
audioUploadedAt IS NOT NULL`.

Lower-effort variant: keep the current ordering but add a "reaper" cron
that runs every 5 min:

```sql
SELECT id FROM transcribe_visits
WHERE status = 'QUEUED'
  AND (
    -- no audio uploaded but we passed the upload step somehow
    (audio_key IS NULL AND created_at < now() - interval '5 min')
    OR
    -- audio uploaded but apparently no BullMQ job
    (audio_uploaded_at < now() - interval '5 min'
     AND processing_started_at IS NULL)
  )
LIMIT 50
```

For each row, attempt a re-enqueue with the existing visit data. The
T-M13 resume logic on the worker side will pick up where it left off.

This is *also* the right place to delete orphan MinIO objects whose
visit row is stuck — wait for the 30-day T-M12 sweep to handle, OR
proactively attempt reconciliation here.
