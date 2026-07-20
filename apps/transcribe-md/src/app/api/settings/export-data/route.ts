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

import { NextResponse } from "next/server";
import { PassThrough, Readable } from "node:stream";
import archiver from "archiver";

import prisma from "@meddoc/db";
import { apiError, withApiHandler } from "@/lib/api-error";
import { auth } from "@/lib/nextauth";
import { RATE_LIMITS, rateLimitOr429 } from "@/lib/rate-limit";
import { downloadAudio } from "@/lib/minio";
import {
  loadVisitExportData,
  loadVisitExportObjectManifest,
} from "@/lib/visit-export-server";
import { generateVisitPdf } from "@/lib/pdf-generator";
import { redactPhi } from "@meddoc/ai";
import { log } from "@/lib/log";
import { isDataExportEnabled } from "@/lib/data-export-feature";
import { listTemplateTwinVisibleVisitIdentities } from "@/lib/template-twin/read-authority";
import {
  authorizeVisitDeliveryFinalClaim,
  TemplateTwinDeliveryAuthorizationError,
} from "@/lib/template-twin/delivery-authorization";
import { loadCurrentVisitExportActor } from "@/lib/visit-export-authority";
import { TEMPLATE_TWIN_DURABLE_VISIT_EXCLUSION_WHERE } from "@/lib/template-twin/durable-visit-exclusion";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
// Heavy users with lots of visits + audio can push past the default
// 60s. Cap at 300s which matches Playwright's own job timeout.
export const maxDuration = 300;

export const GET = withApiHandler("api:settings:export-data", async () => {
  if (!isDataExportEnabled()) {
    return apiError("Data export is disabled on this deployment.", 503);
  }

  const session = await auth();
  const userId = session?.user?.id;
  if (!userId) return apiError("unauthorized", 401);

  const blocked = rateLimitOr429(RATE_LIMITS.SETTINGS, userId);
  if (blocked) return blocked;

  const exportActor = await loadCurrentVisitExportActor(userId);
  if (!exportActor) return apiError("not found", 404);

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
  if (!user) return apiError("user not found", 404);

  // Identifier-only, query-native exact census. Object keys, SOAP, and edit
  // pairs are loaded per visit only between current delivery claims below.
  const visits = await listTemplateTwinVisibleVisitIdentities({
    db: prisma,
    actorUserId: userId,
  });

  // Do not begin a streaming 200 response until every Template Twin visit in
  // the archive has a current signed/review/provider-owned delivery claim.
  // Ordinary visits are a no-op in the shared authorizer.
  try {
    for (const visit of visits) {
      await authorizeVisitDeliveryFinalClaim({
        visitId: visit.id,
        actorUserId: userId,
      });
    }
  } catch (error) {
    if (error instanceof TemplateTwinDeliveryAuthorizationError) {
      return apiError(error.message, error.status, {
        code: error.code,
        retry: false,
      });
    }
    throw error;
  }

  const stamp = new Date().toISOString().replace(/[:.]/g, "-");
  const filename = `transcribemd-export-${userId}-${stamp}.zip`;

  const archive = archiver("zip", { zlib: { level: 6 } });
  // Pipe archiver into a PassThrough we can wrap as a Web stream.
  const passThrough = new PassThrough();
  archive.pipe(passThrough);

  // Archiver's 'warning' is non-fatal (missing file, etc.); 'error' is.
  archive.on("warning", (err) => {
    console.warn(
      `[api:settings:export-data] archiver warning user=${userId}:`,
      redactPhi(err.message),
    );
  });
  archive.on("error", (err) => {
    console.error(
      `[api:settings:export-data] archiver error user=${userId}:`,
      redactPhi(err.message),
    );
    passThrough.destroy(err);
  });

  // Async build — do it in the background so we return the response
  // immediately and bytes start flowing. The archiver pipes to
  // passThrough as content gets appended.
  void (async () => {
    try {
      // Revoke the stream before its first byte if the physician or practice
      // lifecycle changed after enumeration/preflight.
      const currentExportActor = await loadCurrentVisitExportActor(userId);
      if (
        !currentExportActor ||
        currentExportActor.practiceId !== exportActor.practiceId
      ) {
        throw new Error("Current physician authorization changed.");
      }

      // README (inventory + format notes)
      archive.append(
        readmeText({
          userId,
          email: user.email,
          visitCount: visits.length,
          generatedAt: new Date().toISOString(),
        }),
        { name: "README.txt" },
      );

      // user.json
      archive.append(JSON.stringify(user, null, 2), {
        name: "user.json",
      });

      // Per-visit: JSON metadata + audio blobs + signed PDF.
      for (const v of visits) {
        const manifest = await loadVisitExportObjectManifest(v.id, userId);
        if (!manifest) {
          throw new Error("Visit export object manifest is unavailable.");
        }

        const exportData = await loadVisitExportData(v.id, userId);
        if (!exportData) {
          throw new Error("Visit export data is unavailable.");
        }
        await authorizeVisitDeliveryFinalClaim({
          visitId: v.id,
          actorUserId: userId,
        });
        archive.append(JSON.stringify(exportData, null, 2), {
          name: `visits/${v.id}.json`,
        });

        const editPatterns = await loadAuthorizedEditPatterns(v.id, userId);
        if (editPatterns.length > 0) {
          archive.append(JSON.stringify(editPatterns, null, 2), {
            name: `visits/${v.id}/doctor_edit_patterns.json`,
          });
        }

        if (manifest.audioKey) {
          try {
            await authorizeVisitDeliveryFinalClaim({
              visitId: v.id,
              actorUserId: userId,
            });
            const buf = await downloadAudio(manifest.audioKey);
            await authorizeVisitDeliveryFinalClaim({
              visitId: v.id,
              actorUserId: userId,
            });
            const ext = inferAudioExt(manifest.audioMimeType, "audio");
            archive.append(buf, {
              name: `visits/${v.id}/audio.${ext}`,
            });
          } catch (err) {
            if (err instanceof TemplateTwinDeliveryAuthorizationError) {
              throw err;
            }
            console.warn(
              `[api:settings:export-data] audio download failed visit=${v.id}:`,
              redactPhi(err instanceof Error ? err.message : err),
            );
          }
        }

        if (manifest.dictationAudioKey) {
          try {
            await authorizeVisitDeliveryFinalClaim({
              visitId: v.id,
              actorUserId: userId,
            });
            const buf = await downloadAudio(manifest.dictationAudioKey);
            await authorizeVisitDeliveryFinalClaim({
              visitId: v.id,
              actorUserId: userId,
            });
            const ext = inferAudioExt(null, "dictation");
            archive.append(buf, {
              name: `visits/${v.id}/dictation.${ext}`,
            });
          } catch (err) {
            if (err instanceof TemplateTwinDeliveryAuthorizationError) {
              throw err;
            }
            console.warn(
              `[api:settings:export-data] dictation download failed visit=${v.id}:`,
              redactPhi(err instanceof Error ? err.message : err),
            );
          }
        }

        if (manifest.status === "SIGNED" && exportData) {
          try {
            const pdf = await generateVisitPdf(exportData);
            await authorizeVisitDeliveryFinalClaim({
              visitId: v.id,
              actorUserId: userId,
            });
            archive.append(pdf, {
              name: `visits/${v.id}/signed.pdf`,
            });
          } catch (err) {
            if (err instanceof TemplateTwinDeliveryAuthorizationError) {
              throw err;
            }
            console.warn(
              `[api:settings:export-data] pdf render failed visit=${v.id}:`,
              redactPhi(err instanceof Error ? err.message : err),
            );
          }
        }
      }

      await archive.finalize();
      log.info("api:settings:export-data", "archive finalized", {
        userId,
        visitCount: visits.length,
      });
    } catch (err) {
      console.error(
        `[api:settings:export-data] unhandled user=${userId}:`,
        redactPhi(err instanceof Error ? err.message : err),
      );
      passThrough.destroy(err instanceof Error ? err : new Error(String(err)));
    }
  })();

  // Readable.toWeb() adapts the Node stream to a Web ReadableStream
  // that NextResponse accepts as body. Streaming = no memory spike.
  const webStream = Readable.toWeb(passThrough) as ReadableStream<Uint8Array>;

  return new NextResponse(webStream, {
    status: 200,
    headers: {
      "Content-Type": "application/zip",
      "Content-Disposition": `attachment; filename="${filename}"`,
      "Cache-Control": "no-store, no-cache, must-revalidate",
    },
  });
});

// ---------------------------------------------------------------------------
// helpers
// ---------------------------------------------------------------------------

async function loadAuthorizedEditPatterns(visitId: string, userId: string) {
  const initialDeliveryClaim = await authorizeVisitDeliveryFinalClaim({
    visitId,
    actorUserId: userId,
  });
  const patterns = await prisma.doctorEditPattern.findMany({
    where: {
      doctorId: userId,
      visitId,
      ...(initialDeliveryClaim.templateTwin
        ? {}
        : {
            visit: { is: TEMPLATE_TWIN_DURABLE_VISIT_EXCLUSION_WHERE },
          }),
    },
    select: {
      id: true,
      visitId: true,
      originalSoap: true,
      editedSoap: true,
      editDistance: true,
      createdAt: true,
    },
    orderBy: { createdAt: "asc" },
  });
  const finalDeliveryClaim = await authorizeVisitDeliveryFinalClaim({
    visitId,
    actorUserId: userId,
  });
  if (finalDeliveryClaim.templateTwin !== initialDeliveryClaim.templateTwin) {
    throw new Error("Visit delivery authority changed.");
  }
  return patterns;
}

function inferAudioExt(mime: string | null, fallback: string): string {
  if (!mime) {
    // Dictations are always webm from the browser's MediaRecorder.
    return fallback === "dictation" ? "webm" : "bin";
  }
  const m = mime.toLowerCase();
  if (m.includes("webm")) return "webm";
  if (m.includes("mp4")) return "m4a";
  if (m.includes("mpeg") || m.includes("mp3")) return "mp3";
  if (m.includes("wav")) return "wav";
  if (m.includes("ogg")) return "ogg";
  return "bin";
}

interface ReadmeArgs {
  userId: string;
  email: string;
  visitCount: number;
  generatedAt: string;
}

function readmeText(a: ReadmeArgs): string {
  return [
    "QuillMD — data export",
    "================================",
    "",
    `Generated:          ${a.generatedAt}`,
    `Account:            ${a.email} (${a.userId})`,
    `Visits included:    ${a.visitCount}`,
    "",
    "Contents",
    "--------",
    "  user.json                     — Your profile. No passwords, no",
    "                                   MFA secrets — those are never",
    "                                   exported.",
    "",
    "  visits/<id>.json              — Visit metadata + SOAP text (raw",
    "                                   + signed), ICD/CPT codes, Rx",
    "                                   drafts, referrals, patient",
    "                                   summary. When the visit is",
    "                                   SIGNED the signedSoap is the",
    "                                   one-source-of-truth copy.",
    "",
    "  visits/<id>/audio.<ext>       — Original uploaded audio, if any.",
    "  visits/<id>/dictation.<ext>   — Voice-dictation audio, if any.",
    "  visits/<id>/signed.pdf        — Final PDF for SIGNED visits.",
    "",
    "  visits/<id>/doctor_edit_patterns.json",
    "                                — Per-visit pairs of (AI original,",
    "                                   your edit) captured at sign",
    "                                   time. Used locally to improve",
    "                                   prompting for your account.",
    "                                   The vector embeddings are NOT",
    "                                   exported (re-computable from",
    "                                   originalSoap if you need them).",
    "",
    "Format",
    "------",
    "  JSON files: UTF-8, human-readable (2-space indent).",
    "  Audio:      Byte-identical to what was uploaded or recorded.",
    '  PDF:        Byte-identical to what "Download PDF" would produce',
    "              for the same signed visit.",
    "",
    "This export is complete as of the Generated timestamp above.",
    "New activity after that point is not included. Request a fresh",
    "export any time from Settings → Your data.",
    "",
    "Questions: privacy@ashtechgroup.com",
  ].join("\n");
}
