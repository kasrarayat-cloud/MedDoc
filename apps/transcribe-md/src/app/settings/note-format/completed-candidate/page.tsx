import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { AppFrame } from "@/components/ui/app-frame";
import { requireDoctorSession } from "@/lib/auth";
import { logAudit } from "@/lib/audit";
import { completedCandidateSyntheticModeEnabled } from "@/lib/template-twin/completed-candidate-access";
import { isTemplateTwinStagingQaRequested } from "@/lib/template-twin/staging-qa-gate";

import styles from "./completed-candidate.module.css";
import { CompletedCandidateUploadWorkspace } from "./completed-candidate-workspace";

export const metadata: Metadata = {
  title: "Completed document candidate",
};
export const dynamic = "force-dynamic";
export const revalidate = 0;

export default async function CompletedCandidatePage() {
  if (
    !completedCandidateSyntheticModeEnabled(process.env) ||
    isTemplateTwinStagingQaRequested(process.env)
  ) {
    notFound();
  }
  const session = await requireDoctorSession().catch(() => null);
  if (!session) notFound();

  void logAudit({
    action: "VIEWED_SETTINGS",
    targetType: "TemplateTwinCompletedCandidateIntake",
    targetId: session.user.practiceId,
    userId: session.user.id,
    userEmail: session.user.email,
    practiceId: session.user.practiceId,
    metadata: {
      source: "rsc:/settings/note-format/completed-candidate",
      mode: "synthetic-review-v1",
      providerEgress: false,
    },
  });

  return (
    <AppFrame>
      <main className={styles.shell}>
        <Link className={styles.backLink} href="/settings#note-format">
          ← Back to note format
        </Link>
        <header className={styles.header}>
          <div className={styles.eyebrow}>
            Template Twin · candidate laboratory
          </div>
          <h1>Completed examples to blank candidate</h1>
          <p>
            A deliberately narrow, synthetic-only workflow for converting
            deterministic structure—not report prose—into a new reviewable Word
            candidate.
          </p>
        </header>
        <CompletedCandidateUploadWorkspace />
      </main>
    </AppFrame>
  );
}
