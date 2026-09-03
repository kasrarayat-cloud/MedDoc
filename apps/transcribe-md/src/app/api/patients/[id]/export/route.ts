// ============================================================================
// GET /api/patients/[id]/export (T-M17.2 Phase 3 Commit 8)
// ----------------------------------------------------------------------------
// Streams a ZIP containing every visit linked to a single
// TranscribeMdPatient that belongs to the caller's practice.
//
// Archive layout mirrors the per-user export (T-M16.2) — the JSON
// shape per visit is identical so clients written against either
// endpoint Just Work. Patient-level metadata is added as patient.json
// at the root so the archive is self-describing.
//
// Scope rules:
//   - 401 on unauthed
//   - 404 when the patient doesn't exist OR isn't in the caller's
//     practice (anti-enumeration)
//   - Visits are filtered to userId = caller. A shared patient in a
//     multi-seat practice can belong to multiple doctors' visits;
//     we only export the CALLER's visits, not every doctor's.
//   - Soft-deleted patients export fine — the page-level "Export
//     visits" button remains active so the doctor can archive a
//     deleted patient's history before any future hard-delete tool.
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
import { patientScope, visitScope } from '@/lib/practice-scope';
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
// ⚠️ F6.3 — INERT ON THIS DEPLOYMENT, and nothing here ever said so.
// `maxDuration` is a SERVERLESS directive and `next.config.ts` sets
// `output: 'standalone'`, so there is no platform to honour it. The render
// loop below is bounded by `archive-pdf-budget.ts`, not by this line. Kept
// because it is correct wherever this IS deployed serverlessly.
export const maxDuration = 300;

export const GET = withApiHandler<{ id: string }>(
  'api:patients:export',
  async (req, { params }) => {
    const session = await getSession();
    const userId = session?.user.id;
    if (!userId) return apiError('unauthorized', 401);

    const blocked = rateLimitOr429(RATE_LIMITS.SETTINGS, userId);
    if (blocked) return blocked;

    const { id: patientId } = await params;

    // ⚠️ F-TYPE 2026-08-07 — THE TENANCY PREDICATE IS BUILT FROM THE SESSION,
    // NOT FROM A SECOND `user` READ.
    //
    // `PracticeId` is branded and minted at exactly one place, `getSession()`.
    // The `user.practiceId` this route used to pass is a plain `string` off a
    // re-read of the SAME ROW `getSession()` already refreshed on this request
    // (`auth.ts` sets `practiceId = dbUser.practiceId` from
    // `user.findUnique({ where: { id: session.user.id } })`), so the two values
    // are the same column of the same row and nothing observable changes — the
    // brand was simply absent on this path. Sourcing it from the session is
    // what makes it a `PracticeId` honestly rather than by cast.
    const practiceId = session.user.practiceId;

    // Kept for its own sake: a 404 when the caller's user row has gone away
    // between the session read and now. It no longer supplies the practice.
    const user = await prisma.user.findUnique({
      where: { id: userId },
      select: { practiceId: true },
    });
    if (!user) return apiError('user not found', 404);

    // ⚠️ `findFirst`, not `findUnique`. Spreading a `…WhereInput` (whose
    // `id` is `string | StringFilter`) into a `…WhereUniqueInput` (whose `id`
    // must be a bare `string`) widens `id` past the unique key's type. The
    // query itself is unchanged — Prisma's extended where-unique accepted the
    // `practiceId` conjunct and emitted the same predicate — and `findFirst`
    // is the shape `practice-scope.ts` documents for a scoped read, and the
    // one the sibling `patients/[id]/page.tsx` already uses.
    const patient = await prisma.transcribeMdPatient.findFirst({
      where: { id: patientId, ...patientScope(practiceId) },
      select: {
        id: true,
        practiceId: true,
        name: true,
        dateOfBirth: true,
        externalId: true,
        deletedAt: true,
        createdAt: true,
      },
    });
    if (!patient || patient.practiceId !== practiceId) {
      return apiError('not found', 404);
    }

    const visits = await prisma.transcribeVisit.findMany({
      where: {
        patientId,
        // READ — §4.1b: the patient's chart is the PRACTICE's, so an export
        // of it carries every visit on that chart, not only the viewer's.
        ...visitScope(practiceId),
        deletedAt: null,
        archivedAt: null,
      },
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

    const stamp = new Date().toISOString().replace(/[:.]/g, '-');
    const safeName = patient.name.replace(/[^a-zA-Z0-9_-]+/g, '_').slice(0, 40);
    const filename = `patient-${safeName}-${patient.id}-${stamp}.zip`;

    const archive = new ZipArchive({ zlib: { level: 6 } });
    const passThrough = new PassThrough();
    archive.pipe(passThrough);

    archive.on('warning', (err) => {
      console.warn(
        `[api:patients:export] archiver warning patient=${patientId}:`,
        redactPhi(err.message)
      );
    });
    archive.on('error', (err) => {
      console.error(
        `[api:patients:export] archiver error patient=${patientId}:`,
        redactPhi(err.message)
      );
      passThrough.destroy(err);
    });

    // F6.3 — the render bound, created where the detached builder begins so
    // the clock covers exactly this archive's render phase.
    const pdfBudget = createArchivePdfBudget({ signal: req.signal });

    void (async () => {
      try {
        archive.append(
          readmeText({
            patientName: patient.name,
            patientId: patient.id,
            visitCount: visits.length,
            generatedAt: new Date().toISOString(),
          }),
          { name: 'README.txt' }
        );

        archive.append(
          JSON.stringify(
            {
              id: patient.id,
              name: patient.name,
              dateOfBirth: patient.dateOfBirth,
              externalId: patient.externalId,
              deletedAt: patient.deletedAt,
              createdAt: patient.createdAt,
            },
            null,
            2
          ),
          { name: 'patient.json' }
        );

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
              archive.append(buf, { name: `visits/${v.id}/audio.${ext}` });
            } catch (err) {
              console.warn(
                `[api:patients:export] audio download failed visit=${v.id}:`,
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
                `[api:patients:export] dictation download failed visit=${v.id}:`,
                redactPhi(err instanceof Error ? err.message : err)
              );
            }
          }

          if (v.status === 'SIGNED' && exportData) {
            // F6.3 — the render goes THROUGH the bound: it yields the shared
            // sidecar between visits, charges what this archive consumes, and
            // refuses once it has had its share. A refusal is NAMED rather
            // than dropped, for the same reason the failure branch names a
            // failure: a missing file cannot be told apart from a visit that
            // was never signed.
            const outcome = await pdfBudget.render(() =>
              renderVisitPdf(exportData)
            );

            if (outcome.status === 'rendered') {
              // ⚠️ RULED 2026-09-03 — see the sibling archive route. A PDF
              // whose controls may be empty is NAMED, never appended silently.
              if (outcome.value.flatten === 'failed') {
                log.error('api:patients:export', 'pdf rendered UNFLATTENED', {
                  userId,
                  patientId,
                  visitId: v.id,
                });
              }
              archive.append(outcome.value.pdf, {
                name: `visits/${v.id}/signed.pdf`,
              });
            } else if (outcome.status === 'skipped') {
              log.info('api:patients:export', 'pdf render skipped', {
                userId,
                patientId,
                visitId: v.id,
                reason: outcome.reason,
                rendered: pdfBudget.rendered,
                spentMs: pdfBudget.spentMs,
              });
              archive.append(skippedNote(v.id, outcome.reason), {
                name: `visits/${v.id}/signed.pdf.UNAVAILABLE.txt`,
              });
            } else {
              const err = outcome.error;
              // Ruling #113/#116 — the PDF is now a Gotenberg render and has no
              // fallback builder. An archive that silently omits a signed
              // visit's PDF is a silent half-document: the doctor unzips it,
              // sees files for every OTHER visit, and has no way to tell a
              // render failure from a visit that was never signed. So the
              // absence is NAMED, in the archive, at the path the PDF would
              // have occupied.
              console.warn(
                `[api:patients:export] pdf render failed visit=${v.id}:`,
                redactPhi(err instanceof Error ? err.message : err)
              );
              archive.append(unavailableNote(v.id, err), {
                name: `visits/${v.id}/signed.pdf.UNAVAILABLE.txt`,
              });
            }
          }
        }

        await archive.finalize();
        log.info('api:patients:export', 'archive finalized', {
          userId,
          patientId,
          visitCount: visits.length,
        });
      } catch (err) {
        console.error(
          `[api:patients:export] unhandled patient=${patientId}:`,
          redactPhi(err instanceof Error ? err.message : err)
        );
        passThrough.destroy(
          err instanceof Error ? err : new Error(String(err))
        );
      }
    })();

    // S4b — record the disclosure BEFORE handing back the stream. Every visit
    // this doctor holds for ONE patient, leaving as a single file. Ran
    // unaudited until 2026-07-25. See the sibling settings/export-data route
    // for why this is logged at response time rather than on completion.
    await logAudit({
      action: 'EXPORT_PATIENT_ARCHIVE_DOWNLOADED',
      userId,
      targetType: 'TranscribeMdPatient',
      targetId: patientId,
      metadata: { visitCount: visits.length, scope: 'single_patient' },
    });

    const webStream = Readable.toWeb(passThrough) as ReadableStream<Uint8Array>;

    return new NextResponse(webStream, {
      status: 200,
      headers: {
        'Content-Type': 'application/zip',
        'Content-Disposition': `attachment; filename="${filename}"`,
        'Cache-Control': 'no-store, no-cache, must-revalidate',
      },
    });
  }
);

function inferAudioExt(mime: string | null, fallback: string): string {
  if (!mime) return fallback === 'dictation' ? 'webm' : 'bin';
  const m = mime.toLowerCase();
  if (m.includes('webm')) return 'webm';
  if (m.includes('mp4')) return 'm4a';
  if (m.includes('mpeg') || m.includes('mp3')) return 'mp3';
  if (m.includes('wav')) return 'wav';
  if (m.includes('ogg')) return 'ogg';
  return 'bin';
}

interface ReadmeArgs {
  patientName: string;
  patientId: string;
  visitCount: number;
  generatedAt: string;
}

function readmeText(a: ReadmeArgs): string {
  return [
    'QuillMD — patient export',
    '================================',
    '',
    `Generated:          ${a.generatedAt}`,
    `Patient:            ${a.patientName} (${a.patientId})`,
    `Visits included:    ${a.visitCount}`,
    '',
    'Contents',
    '--------',
    '  patient.json                  — Patient record (id, name, DOB,',
    '                                   externalId, createdAt,',
    '                                   deletedAt if archived).',
    '',
    '  visits/<id>.json              — Visit metadata + SOAP text, codes,',
    '                                   Rx drafts, referrals, summary.',
    '                                   Same schema as the full data',
    '                                   export (Settings → Your data).',
    '',
    '  visits/<id>/audio.<ext>       — Original uploaded audio, if any.',
    '  visits/<id>/dictation.<ext>   — Voice-dictation audio, if any.',
    '  visits/<id>/signed.pdf        — Final PDF for SIGNED visits.',
    '',
    '  visits/<id>/signed.pdf.UNAVAILABLE.txt',
    '                                — Appears INSTEAD of signed.pdf when',
    '                                   that one PDF could not be included.',
    '                                   The file says which reason it was',
    '                                   and what to do about it. The visit',
    '                                   itself is unaffected either way, and',
    '                                   its full record is still in',
    '                                   visits/<id>.json.',
    '',
    'Scope',
    '-----',
    '  This archive includes only the visits YOU created for this',
    '  patient. If the patient has been seen by other doctors in the',
    '  practice, their visits are NOT in this file.',
    '',
    'Questions: privacy@ashtechgroup.com',
  ].join('\n');
}
