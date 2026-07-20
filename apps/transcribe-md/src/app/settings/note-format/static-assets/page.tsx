import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { recordTemplateTwinStaticAssetInventoryAccess } from "@/lib/template-twin/static-asset-access-audit";
import { isTemplateTwinStagingQaRequested } from "@/lib/template-twin/staging-qa-gate";
import { requireTemplateTwinStaticAssetAdmin } from "@/lib/template-twin/static-asset-admin";

import styles from "./static-asset-review.module.css";
import { StaticAssetReviewWorkspace } from "./static-asset-review-workspace";

export const metadata: Metadata = { title: "Reusable template images" };
export const dynamic = "force-dynamic";
export const revalidate = 0;

export default async function TemplateTwinStaticAssetSettingsPage() {
  // This surface manages arbitrary reusable practice media. A process
  // explicitly requested as synthetic-only must not disclose the page or even
  // evaluate its admin/service dependencies, including during partial staging
  // configuration.
  if (isTemplateTwinStagingQaRequested(process.env)) notFound();

  const actor = await requireTemplateTwinStaticAssetAdmin().catch(() => null);
  if (!actor) notFound();

  try {
    await recordTemplateTwinStaticAssetInventoryAccess({
      actor,
      surface: "page",
    });
  } catch {
    console.error(
      "[template-twin-static-assets-page] access audit failed closed",
    );
    notFound();
  }

  return (
    <main className={styles.adminSurface}>
      <div className={styles.shell}>
        <header className={styles.header}>
          <div className={styles.eyebrow}>
            Template Twin · practice administration
          </div>
          <h1 className={styles.title}>Reusable template images</h1>
          <p className={styles.subtitle}>
            Review a blank practice logo or mark once, then bind only those
            exact approved bytes to new Word-template versions. This does not
            approve patient images, signatures, or completed forms.
          </p>
        </header>
        <StaticAssetReviewWorkspace />
      </div>
    </main>
  );
}
