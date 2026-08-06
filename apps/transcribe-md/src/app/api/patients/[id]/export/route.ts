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
import { generateVisitPdf } from '@/lib/pdf-generator';
import { redactPhi } from '@meddoc/ai';
import { log } from '@/lib/log';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';
export const maxDuration = 300;

export const GET = withApiHandler<{ id: string }>(
  'api:patients:export',
  async (_req, { params }) => {
    const session = await getSession();
    const userId = session?.user.id;
    if (!userId) return apiError('unauthorized', 401);

    const blocked = rateLimitOr429(RATE_LIMITS.SETTINGS, userId);
    if (blocked) return blocked;

    const { id: patientId } = await params;

    // Resolve the caller's practiceId so we can gate the patient
    // lookup on it. Cheaper than pulling the full session helper.
    const user = await prisma.user.findUnique({
      where: { id: userId },
      select: { practiceId: true },
    });
    if (!user) return apiError('user not found', 404);

    const patient = await prisma.transcribeMdPatient.findUnique({
      where: { id: patientId, ...patientScope(user.practiceId) },
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
    if (!patient || patient.practiceId !== user.practiceId) {
      return apiError('not found', 404);
    }

    const visits = await prisma.transcribeVisit.findMany({
      where: {
        patientId,
        // READ — §4.1b: the patient's chart is the PRACTICE's, so an export
        // of it carries every visit on that chart, not only the viewer's.
        ...visitScope(user.practiceId),
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
            try {
              const pdf = await generateVisitPdf(exportData);
              archive.append(pdf, { name: `visits/${v.id}/signed.pdf` });
            } catch (err) {
              console.warn(
                `[api:patients:export] pdf render failed visit=${v.id}:`,
                redactPhi(err instanceof Error ? err.message : err)
              );
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
    'Scope',
    '-----',
    '  This archive includes only the visits YOU created for this',
    '  patient. If the patient has been seen by other doctors in the',
    '  practice, their visits are NOT in this file.',
    '',
    'Questions: privacy@ashtechgroup.com',
  ].join('\n');
}
