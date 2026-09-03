// ============================================================================
// GET /api/settings/export-data (T-M16.2)
// ----------------------------------------------------------------------------
// Streams a ZIP containing everything the user owns:
//   /user.json                      — profile (no secrets)
//   /visits/<id>.json               — full visit metadata + SOAP text
//   /visits/<id>/audio.<ext>        — original upload, if present
//   /visits/<id>/dictation.<ext>    — dictation audio, if present
//   /visits/<id>/signed.pdf         — generated from signed visits
//   /doctor_edit_patterns.json      — per-doctor edit patterns (T-M14.1)
//   /README.txt                     — inventory + format notes
//
// Synchronous streaming design (per T-M16.2 scope):
//   - Archiver instance in Node land.
//   - Its output Readable is piped into a Web ReadableStream and
//     returned as the Response body.
//   - No intermediate file on disk → no cleanup concern.
//   - Memory bounded by the largest single object we touch (audio
//     files up to 500 MB). For users with hundreds of visits the
//     total response size can get large but Node streams it through.
//
// Kill-switch: ENABLE_DATA_EXPORT env (default true). Flip to false
// to disable the feature on a specific deployment without a redeploy.
// The Settings-page button is also hidden server-side when off.
// ============================================================================

import { NextResponse } from 'next/server';
import { PassThrough, Readable } from 'node:stream';
// archiver v8 is pure ESM and no longer exports a callable factory: v7's
// `module.exports = archiver` became named class exports
// ({ Archiver, JsonArchive, TarArchive, ZipArchive }), so `import archiver from
// 'archiver'` has no default export and `archiver('zip', opts)` is not callable.
// The rest of our surface is unchanged — Archiver still extends stream.Transform,
// so pipe/append/finalize behave identically, and on('error'|'warning') is now
// properly typed as ArchiverError instead of implicit any.
import { ZipArchive } from 'archiver';

import prisma from '@meddoc/db';
import { apiError, withApiHandler } from '@/lib/api-error';
import { logAudit } from '@/lib/audit';
import { getSession } from '@/lib/auth';
import { RATE_LIMITS, rateLimitOr429 } from '@/lib/rate-limit';
import { downloadAudio } from '@/lib/minio';
import { loadVisitExportData } from '@/lib/visit-export-server';
import { renderVisitPdf, unavailableNote } from '@/lib/visit-pdf';
import { createArchivePdfBudget, skippedNote } from '@/lib/archive-pdf-budget';
import { redactPhi } from '@meddoc/ai';
import { log } from '@/lib/log';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';
// ⚠️ F6.3 — THIS LINE IS INERT AND ITS OLD COMMENT CLAIMED OTHERWISE.
// It used to read: *"Heavy users with lots of visits + audio can push past the
// default 60s. Cap at 300s which matches Playwright's own job timeout."*
// `maxDuration` is a SERVERLESS directive; `next.config.ts` sets
// `output: 'standalone'`, so this deployment is a plain `node server.js` with
// no platform to honour it. **There was no cap.** Kept because it is correct
// and load-bearing anywhere this is deployed serverlessly, and because
// removing it would silently lower a real ceiling on such a host — but it is
// NOT what bounds the render loop here. That is `archive-pdf-budget.ts`.
export const maxDuration = 300;

export function isDataExportEnabled(): boolean {
  const raw = process.env.ENABLE_DATA_EXPORT?.trim().toLowerCase();
  // Default true — absence or unset = feature on.
  return raw !== 'false' && raw !== '0';
}

export const GET = withApiHandler('api:settings:export-data', async (req) => {
  if (!isDataExportEnabled()) {
    return apiError('Data export is disabled on this deployment.', 503);
  }

  const session = await getSession();
  const userId = session?.user.id;
  if (!userId) return apiError('unauthorized', 401);

  const blocked = rateLimitOr429(RATE_LIMITS.SETTINGS, userId);
  if (blocked) return blocked;

  // Load user profile (strict PII only — no secrets).
  const user = await prisma.user.findUnique({
    where: { id: userId },
    select: {
      id: true,
      email: true,
      name: true,
      role: true,
      products: true,
      createdAt: true,
      updatedAt: true,
      emailVerified: true,
    },
  });
  if (!user) return apiError('user not found', 404);

  // Light visit list — we fetch full bytes per-visit as we stream.
  const visits = await prisma.transcribeVisit.findMany({
    where: { userId },
    select: {
      id: true,
      audioKey: true,
      dictationAudioKey: true,
      audioMimeType: true,
      status: true,
      createdAt: true,
    },
    orderBy: { createdAt: 'asc' },
  });

  const editPatterns = await prisma.doctorEditPattern.findMany({
    where: { doctorId: userId },
    select: {
      id: true,
      visitId: true,
      originalSoap: true,
      editedSoap: true,
      editDistance: true,
      createdAt: true,
    },
    orderBy: { createdAt: 'asc' },
  });

  const stamp = new Date().toISOString().replace(/[:.]/g, '-');
  const filename = `transcribemd-export-${userId}-${stamp}.zip`;

  const archive = new ZipArchive({ zlib: { level: 6 } });
  // Pipe archiver into a PassThrough we can wrap as a Web stream.
  const passThrough = new PassThrough();
  archive.pipe(passThrough);

  // Archiver's 'warning' is non-fatal (missing file, etc.); 'error' is.
  archive.on('warning', (err) => {
    console.warn(
      `[api:settings:export-data] archiver warning user=${userId}:`,
      redactPhi(err.message)
    );
  });
  archive.on('error', (err) => {
    console.error(
      `[api:settings:export-data] archiver error user=${userId}:`,
      redactPhi(err.message)
    );
    passThrough.destroy(err);
  });

  // Async build — do it in the background so we return the response
  // immediately and bytes start flowing. The archiver pipes to
  // passThrough as content gets appended.
  // F6.3 — the render bound. Created HERE, where the detached builder begins,
  // so the clock covers exactly this archive's render phase and one doctor's
  // export can never spend another's budget.
  const pdfBudget = createArchivePdfBudget({ signal: req.signal });

  void (async () => {
    try {
      // README (inventory + format notes)
      archive.append(
        readmeText({
          userId,
          email: user.email,
          visitCount: visits.length,
          editPatternCount: editPatterns.length,
          generatedAt: new Date().toISOString(),
        }),
        { name: 'README.txt' }
      );

      // user.json
      archive.append(JSON.stringify(user, null, 2), {
        name: 'user.json',
      });

      // doctor_edit_patterns.json
      archive.append(JSON.stringify(editPatterns, null, 2), {
        name: 'doctor_edit_patterns.json',
      });

      // Per-visit: JSON metadata + audio blobs + signed PDF.
      for (const v of visits) {
        const exportData = await loadVisitExportData(v.id, session.user.practiceId);
        if (exportData) {
          archive.append(JSON.stringify(exportData, null, 2), {
            name: `visits/${v.id}.json`,
          });
        }

        if (v.audioKey) {
          try {
            const buf = await downloadAudio(v.audioKey);
            const ext = inferAudioExt(v.audioMimeType, 'audio');
            archive.append(buf, {
              name: `visits/${v.id}/audio.${ext}`,
            });
          } catch (err) {
            console.warn(
              `[api:settings:export-data] audio download failed visit=${v.id}:`,
              redactPhi(err instanceof Error ? err.message : err)
            );
          }
        }

        if (v.dictationAudioKey) {
          try {
            const buf = await downloadAudio(v.dictationAudioKey);
            const ext = inferAudioExt(null, 'dictation');
            archive.append(buf, {
              name: `visits/${v.id}/dictation.${ext}`,
            });
          } catch (err) {
            console.warn(
              `[api:settings:export-data] dictation download failed visit=${v.id}:`,
              redactPhi(err instanceof Error ? err.message : err)
            );
          }
        }

        if (v.status === 'SIGNED' && exportData) {
          // F6.3 — the render goes THROUGH the bound, which yields the shared
          // sidecar between visits, charges what this archive consumes, and
          // refuses once it has had its share.
          const outcome = await pdfBudget.render(() =>
            renderVisitPdf(exportData)
          );

          if (outcome.status === 'rendered') {
            // ⚠️ RULED 2026-09-03 — A DEGRADED PDF IS NAMED, NOT SHIPPED
            // QUIETLY. `failed` means flattening threw and this render may
            // carry EMPTY content controls. Same reasoning as the skip branch
            // below: a file nobody flagged cannot be told apart from a good one.
            if (outcome.value.flatten === 'failed') {
              log.error('api:settings:export-data', 'pdf rendered UNFLATTENED', {
                userId,
                visitId: v.id,
              });
            }
            archive.append(outcome.value.pdf, {
              name: `visits/${v.id}/signed.pdf`,
            });
          } else if (outcome.status === 'skipped') {
            // NAMED, never dropped — an absent file is indistinguishable from
            // a visit that was never signed, which is the reasoning ruling
            // #113/#116 already recorded for the failure case below.
            log.info('api:settings:export-data', 'pdf render skipped', {
              userId,
              visitId: v.id,
              reason: outcome.reason,
              rendered: pdfBudget.rendered,
              spentMs: pdfBudget.spentMs,
            });
            archive.append(skippedNote(v.id, outcome.reason), {
              name: `visits/${v.id}/signed.pdf.UNAVAILABLE.txt`,
            });
          } else {
            // Ruling #113/#116 — same reasoning as the patient archive: with no
            // fallback builder, a silently-absent signed.pdf is indistinguishable
            // from a visit that was never signed. Name the absence in place, and
            // let `unavailableNote` say WHICH failure it was — a renderer outage
            // and an unbuildable document need different advice.
            console.warn(
              `[api:settings:export-data] pdf render failed visit=${v.id}:`,
              redactPhi(
                outcome.error instanceof Error
                  ? outcome.error.message
                  : outcome.error
              )
            );
            archive.append(unavailableNote(v.id, outcome.error), {
              name: `visits/${v.id}/signed.pdf.UNAVAILABLE.txt`,
            });
          }
        }
      }

      await archive.finalize();
      log.info('api:settings:export-data', 'archive finalized', {
        userId,
        visitCount: visits.length,
        editPatternCount: editPatterns.length,
      });
    } catch (err) {
      console.error(
        `[api:settings:export-data] unhandled user=${userId}:`,
        redactPhi(err instanceof Error ? err.message : err)
      );
      passThrough.destroy(
        err instanceof Error ? err : new Error(String(err))
      );
    }
  })();

  // S4b — record the disclosure BEFORE handing back the stream.
  //
  // This is the single largest PHI egress the product has: every visit the
  // user owns, with SOAP text, the original audio, and generated PDFs. It ran
  // unaudited from T-M16.2 until 2026-07-25.
  //
  // Logged at RESPONSE time, not on completion. A streamed download has no
  // reliable completion signal server-side — the client can disconnect
  // mid-transfer and we would never hear about it. Recording at the point the
  // bytes start flowing can therefore over-report a fully-completed download,
  // but it can never MISS one, and for an audit trail a false positive is the
  // safe direction. `visitCount` is what the archive was built to contain.
  await logAudit({
    action: 'EXPORT_ACCOUNT_ARCHIVE_DOWNLOADED',
    userId,
    targetType: 'User',
    targetId: userId,
    metadata: {
      visitCount: visits.length,
      editPatternCount: editPatterns.length,
      scope: 'full_account',
    },
  });

  // Readable.toWeb() adapts the Node stream to a Web ReadableStream
  // that NextResponse accepts as body. Streaming = no memory spike.
  const webStream = Readable.toWeb(passThrough) as ReadableStream<Uint8Array>;

  return new NextResponse(webStream, {
    status: 200,
    headers: {
      'Content-Type': 'application/zip',
      'Content-Disposition': `attachment; filename="${filename}"`,
      'Cache-Control': 'no-store, no-cache, must-revalidate',
    },
  });
});

// ---------------------------------------------------------------------------
// helpers
// ---------------------------------------------------------------------------

function inferAudioExt(mime: string | null, fallback: string): string {
  if (!mime) {
    // Dictations are always webm from the browser's MediaRecorder.
    return fallback === 'dictation' ? 'webm' : 'bin';
  }
  const m = mime.toLowerCase();
  if (m.includes('webm')) return 'webm';
  if (m.includes('mp4')) return 'm4a';
  if (m.includes('mpeg') || m.includes('mp3')) return 'mp3';
  if (m.includes('wav')) return 'wav';
  if (m.includes('ogg')) return 'ogg';
  return 'bin';
}

interface ReadmeArgs {
  userId: string;
  email: string;
  visitCount: number;
  editPatternCount: number;
  generatedAt: string;
}

function readmeText(a: ReadmeArgs): string {
  return [
    'QuillMD — data export',
    '================================',
    '',
    `Generated:          ${a.generatedAt}`,
    `Account:            ${a.email} (${a.userId})`,
    `Visits included:    ${a.visitCount}`,
    `Edit patterns:      ${a.editPatternCount}`,
    '',
    'Contents',
    '--------',
    '  user.json                     — Your profile. No passwords, no',
    '                                   MFA secrets — those are never',
    '                                   exported.',
    '',
    '  visits/<id>.json              — Visit metadata + SOAP text (raw',
    '                                   + signed), ICD/CPT codes, Rx',
    '                                   drafts, referrals, patient',
    '                                   summary. When the visit is',
    '                                   SIGNED the signedSoap is the',
    '                                   one-source-of-truth copy.',
    '',
    '  visits/<id>/audio.<ext>       — Original uploaded audio, if any.',
    '  visits/<id>/dictation.<ext>   — Voice-dictation audio, if any.',
    '  visits/<id>/signed.pdf        — Final PDF for SIGNED visits.',
    '',
    '  visits/<id>/signed.pdf.UNAVAILABLE.txt',
    '                                — Appears INSTEAD of signed.pdf when',
    '                                   that one PDF could not be included.',
    '                                   The file says which of the reasons',
    '                                   it was and what to do about it. The',
    '                                   visit itself is unaffected either',
    '                                   way, and its full record is still in',
    '                                   visits/<id>.json.',
    '',
    '  doctor_edit_patterns.json     — Per-visit pairs of (AI original,',
    '                                   your edit) captured at sign',
    '                                   time. Used locally to improve',
    '                                   prompting for your account.',
    '                                   The vector embeddings are NOT',
    '                                   exported (re-computable from',
    '                                   originalSoap if you need them).',
    '',
    'Format',
    '------',
    '  JSON files: UTF-8, human-readable (2-space indent).',
    '  Audio:      Byte-identical to what was uploaded or recorded.',
    '  PDF:        The same styled document "Download PDF" produces for',
    '              that visit. If your practice uses a certified native',
    '              PDF template, the download gives you your own form and',
    '              this archive gives you the styled render instead — the',
    '              clinical content is the same, the layout is not.',
    '',
    'This export is complete as of the Generated timestamp above.',
    'New activity after that point is not included. Request a fresh',
    'export any time from Settings → Your data.',
    '',
    'Questions: privacy@ashtechgroup.com',
  ].join('\n');
}
