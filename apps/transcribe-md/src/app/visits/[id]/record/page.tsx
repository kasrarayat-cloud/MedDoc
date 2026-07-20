// ============================================================================
// /visits/[id]/record — Linear V1 live-recording shell.
// Reference: docs/design-directions-v8-linear/recording.html
// ----------------------------------------------------------------------------
// 440px left column (mic + halo + waveform + status + actions) ‖ live
// transcript on the right. MediaRecorder flow reuses the existing
// /api/visits/[id]/dictation/upload endpoint so the worker pipeline
// runs unchanged. The scribe-ws live-transcript integration is a
// follow-up — the transcript area shows a "listening…" placeholder
// until the worker produces a transcript.
//
// 🔴 PROTECTED: All MediaRecorder lifecycle code lives in
// recording-client.tsx and is preserved byte-for-byte across the
// Linear V1 visual migration.
// ============================================================================

import type { Metadata } from "next";
import { notFound, redirect } from "next/navigation";

import prisma from "@meddoc/db";
import { auth } from "@/lib/nextauth";
import { logRequiredAudit } from "@/lib/audit";
import {
  requireTemplateTwinVisitReadAuthority,
  TemplateTwinVisitReadAuthorityError,
} from "@/lib/template-twin/read-authority";
import { TEMPLATE_TWIN_DURABLE_VISIT_EXCLUSION_WHERE } from "@/lib/template-twin/durable-visit-exclusion";
import { currentClinicalVisitActorWhere } from "@/lib/clinical-visit-authority";
import { isSkinBeta } from "@/config/skin-beta";
import { AppFrame } from "@/components/ui/app-frame";
import { RecordingClient } from "./recording-client";
import { RecordingClientC3 } from "./recording-client-c3";

export const metadata: Metadata = { title: "Recording" };

export default async function RecordVisitPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const session = await auth();
  if (!session?.user?.id) redirect("/login");

  let preReadAuthority;
  try {
    preReadAuthority = await requireTemplateTwinVisitReadAuthority({
      db: prisma,
      visitId: id,
      actorUserId: session.user.id,
    });
  } catch (error) {
    if (error instanceof TemplateTwinVisitReadAuthorityError) notFound();
    throw error;
  }
  if (
    preReadAuthority.isSyntheticTemplateTwin ||
    (preReadAuthority.isTemplateTwin && !preReadAuthority.practiceId)
  ) {
    notFound();
  }

  type VisitRow = {
    id: string;
    userId: string;
    status: string;
    patient: { name: string } | null;
    specialty: string;
  };
  const visit: VisitRow | null = await prisma.transcribeVisit.findFirst({
    where: {
      id,
      ...currentClinicalVisitActorWhere(session.user.id),
      ...(preReadAuthority.isTemplateTwin
        ? {}
        : TEMPLATE_TWIN_DURABLE_VISIT_EXCLUSION_WHERE),
    },
    select: {
      id: true,
      userId: true,
      status: true,
      patient: { select: { name: true } },
      specialty: true,
    },
  });
  if (!visit || visit.userId !== session.user.id) notFound();

  let readAuthority;
  try {
    readAuthority = await requireTemplateTwinVisitReadAuthority({
      db: prisma,
      visitId: id,
      actorUserId: session.user.id,
      ...(preReadAuthority.isTemplateTwin
        ? {
            expectedPracticeId: preReadAuthority.practiceId!,
            requireTemplateTwin: true,
          }
        : {}),
    });
  } catch (error) {
    if (error instanceof TemplateTwinVisitReadAuthorityError) notFound();
    throw error;
  }
  // Synthetic QA owns its own admitted execution/review surface; the generic
  // live recorder must never expose or mutate a synthetic encounter.
  if (readAuthority.isSyntheticTemplateTwin) notFound();
  if (readAuthority.isTemplateTwin) {
    if (!readAuthority.practiceId) notFound();
    try {
      await logRequiredAudit({
        action: "VIEWED_VISIT",
        targetId: visit.id,
        targetType: "TranscribeVisit",
        userId: session.user.id,
        practiceId: readAuthority.practiceId,
        metadata: { source: "rsc:/visits/[id]/record" },
        templateTwinReadAuthority: {
          expectedPracticeId: readAuthority.practiceId,
        },
      });
    } catch (error) {
      if (error instanceof TemplateTwinVisitReadAuthorityError) notFound();
      throw error;
    }
  }

  // Only QUEUED visits are eligible for recording. Anything further
  // along the pipeline sends the doctor to the regular visit page.
  if (visit.status !== "QUEUED") {
    redirect(`/visits/${id}`);
  }

  return (
    <AppFrame>
      {isSkinBeta() ? (
        // Stage 1c calm-skin recorder (flag-gated). Same MediaRecorder
        // lifecycle + same /api/visits/[id]/dictation/upload endpoint; only
        // the presentation differs. Old UI is the default.
        <RecordingClientC3
          visitId={visit.id}
          patientName={visit.patient?.name ?? "Patient"}
          specialty={visit.specialty}
        />
      ) : (
        <RecordingClient
          visitId={visit.id}
          patientName={visit.patient?.name ?? "Patient"}
          specialty={visit.specialty}
        />
      )}
    </AppFrame>
  );
}
