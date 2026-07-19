import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { AppFrame } from "@/components/ui/app-frame";
import { requireDoctorSession } from "@/lib/auth";
import { logAudit } from "@/lib/audit";
import { completedCandidateSyntheticModeEnabled } from "@/lib/template-twin/completed-candidate-access";
import {
  CompletedCandidateServiceError,
  getCompletedCandidateReview,
} from "@/lib/template-twin/completed-candidate-service";
import { isTemplateTwinStagingQaRequested } from "@/lib/template-twin/staging-qa-gate";

import styles from "../completed-candidate.module.css";
import { CompletedCandidateReviewWorkspace } from "../completed-candidate-workspace";

export const metadata: Metadata = { title: "Review blank candidate" };
export const dynamic = "force-dynamic";
export const revalidate = 0;

export default async function CompletedCandidateReviewPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  if (
    !completedCandidateSyntheticModeEnabled(process.env) ||
    isTemplateTwinStagingQaRequested(process.env)
  ) {
    notFound();
  }
  const session = await requireDoctorSession().catch(() => null);
  if (!session) notFound();
  const { id } = await params;
  if (
    !/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/iu.test(
      id,
    )
  ) {
    notFound();
  }

  let review;
  try {
    review = await getCompletedCandidateReview({
      candidateId: id,
      actor: {
        userId: session.user.id,
        practiceId: session.user.practiceId,
      },
    });
  } catch (error) {
    if (
      error instanceof CompletedCandidateServiceError &&
      error.code === "NOT_FOUND"
    ) {
      notFound();
    }
    throw error;
  }

  void logAudit({
    action: "VIEWED_SETTINGS",
    targetType: "TemplateTwinCompletedCandidate",
    targetId: review.id,
    userId: session.user.id,
    userEmail: session.user.email,
    practiceId: session.user.practiceId,
    metadata: {
      source: "rsc:/settings/note-format/completed-candidate/[id]",
      candidateStatus: review.status,
      inventorySha256: review.inventorySha256,
    },
  });

  return (
    <AppFrame>
      <main className={styles.shell}>
        <Link
          className={styles.backLink}
          href="/settings/note-format/completed-candidate"
        >
          ← New candidate
        </Link>
        <CompletedCandidateReviewWorkspace initial={review} />
      </main>
    </AppFrame>
  );
}
