---
id: A04-P1-002
title: Audio upload accepts attacker-controlled Content-Type with no magic-bytes / ffprobe verification
severity: P1
domain: Input validation / file uploads
status: open
---

## Summary

Both PHI-handling audio-upload endpoints (`/api/visits/[id]/upload`, `/api/visits/[id]/dictation/upload`) check only the request's `Content-Type` header against an allow-list. There is no magic-byte sniff, no `ffprobe` validation, and no library-level format check. A user can declare `Content-Type: audio/wav` and upload arbitrary bytes — including an EICAR test file, a binary that exploits a downstream parser, or a polyglot — and the system stores it in MinIO, persists `audioMimeType` from the same header, and hands the bytes to Deepgram.

Practical attack surface:

1. **Storage poisoning** — files claimed as audio land in the user's MinIO prefix and are exported in the user's data dump (`/api/settings/export-data`) using `inferAudioExt(mime, ...)` which derives the file extension from the *attacker-claimed* MIME (`route.ts:225-234`). A `.exe` payload labelled `audio/mpeg` becomes `<visitId>/audio.mp3` in the export ZIP — the user's own ZIP, but still a confused-deputy primitive.
2. **Deepgram fan-out** — `packages/ai/src/deepgram-batch.ts:213-225` forwards the bytes to Deepgram with the user-supplied MIME. Deepgram will reject it server-side for non-audio, but a slow-reject still burns the worker's process_visit slot and trips the queue's retry path.
3. **MinIO put with wrong content-type metadata** — a `.svg` payload labelled `audio/wav` would be stored as `audio/wav` in MinIO; if anything ever serves the dictation audio with a permissive `Content-Type` override (the dictation-audio replay route at `apps/transcribe-md/src/app/api/visits/[id]/dictation/audio/route.ts:62` re-uses the stored MIME), the SVG would be rendered XSS-style. Today the route only sets `Content-Type: audio/webm` (default), but the line is `visit.audioMimeType ?? 'audio/webm'` — i.e. uses the stored MIME if present. So an attacker who uploaded `audio/wav`-labelled HTML would get it served back as `audio/wav` (browser ignores HTML), but `image/svg+xml`-labelled bytes would also be served back as `image/svg+xml` if the upload path's allow-list ever broadens. The current allow-list does NOT include svg, so today this is contained.

The path-traversal angle is closed: `apps/transcribe-md/src/lib/minio.ts:197-202` sanitizes filenames to `[A-Za-z0-9._-]` and slices to 80 chars, then prepends `userId/visitId/timestamp-`. Good.

## Evidence

`apps/transcribe-md/src/app/api/visits/[id]/upload/route.ts:41-52`:
```ts
const ALLOWED_MIME = new Set([
  'audio/mpeg', 'audio/mp3', 'audio/mp4', 'audio/m4a', 'audio/x-m4a',
  'audio/wav', 'audio/x-wav', 'audio/ogg', 'audio/webm', 'audio/flac',
]);
```

Lines 127-134:
```ts
const mimeType = req.headers.get('content-type')?.trim() ?? '';
if (!mimeType || !ALLOWED_MIME.has(mimeType.split(';')[0]!.trim())) {
  return apiError(`Unsupported file format: ${mimeType || '(missing)'}...`, 415, ...);
}
```

That is the entire format check. The bytes are then streamed straight to MinIO (line 148: `await putAudioStream(objectKey, nodeReadable, contentLength, mimeType)`), and the `audioMimeType` column is set from the same header (line 181: `audioMimeType: mimeType.split(';')[0]!.trim()`).

`apps/transcribe-md/src/app/api/visits/[id]/dictation/upload/route.ts:38-46, 112-120`: identical pattern with a smaller allow-list and a 50 MB cap (vs 500 MB on the bulk route).

## Why this is P1

The MIME spoof itself is not a direct RCE vector against the platform — Deepgram is the next consumer and will reject malformed audio. But:

- The bytes sit in MinIO under the doctor's prefix and are exported back to them in the data-export ZIP labelled with the attacker's chosen extension. A future "view audio" feature that trusts the stored MIME would inherit the spoof.
- Without content sniffing the system has no defence against a future expansion of `ALLOWED_MIME` (e.g. adding `audio/x-aiff` or anything image-adjacent). Defence-in-depth on PHI uploads is HIPAA hygiene.
- The `audioSizeBytes` and `audioDurationSec` columns derive from the upload header / Deepgram response — neither is validated against actual media content. A 0-byte file claiming `Content-Length: 1000` would propagate.

## Recommended fixes

1. Add a magic-bytes sniff inline as the stream is received (e.g. read the first 4 KB into a buffer, check against the file-type signature, prepend the buffer to the rest of the stream). The `file-type` npm package handles this for every codec in the allow-list.
2. Once L1 (Deepgram) reports `durationSec`, require it be > 0; reject the visit otherwise. (Today the check is implicit — an empty transcript falls through L2's "no-speakers" branch.)
3. When serving stored audio back (`/api/visits/[id]/dictation/audio/route.ts:62`), do NOT use the stored MIME verbatim — re-validate against the same allow-list, and force `Content-Disposition: attachment` if it ever becomes possible to upload non-audio.

## Cross-domain hooks

- Agent 02 (auth/PHI): if the dictation-audio replay route ever gets exposed cross-tenant the spoof becomes more severe.
- Agent 03 (filesystem/storage): MinIO bucket policy and object lifecycle.

## Files

- `/opt/meddoc-pro/apps/transcribe-md/src/app/api/visits/[id]/upload/route.ts`
- `/opt/meddoc-pro/apps/transcribe-md/src/app/api/visits/[id]/dictation/upload/route.ts`
- `/opt/meddoc-pro/apps/transcribe-md/src/app/api/visits/[id]/dictation/audio/route.ts`
- `/opt/meddoc-pro/apps/transcribe-md/src/app/api/patients/[id]/export/route.ts`
- `/opt/meddoc-pro/apps/transcribe-md/src/lib/minio.ts`
