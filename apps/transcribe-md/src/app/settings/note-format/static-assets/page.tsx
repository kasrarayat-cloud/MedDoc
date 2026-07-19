import type { Metadata } from 'next';
import Link from 'next/link';
import { notFound } from 'next/navigation';

import { AppFrame } from '@/components/ui/app-frame';
import { logAudit } from '@/lib/audit';
import { isTemplateTwinStagingQaRequested } from '@/lib/template-twin/staging-qa-gate';
import { requireTemplateTwinStaticAssetAdmin } from '@/lib/template-twin/static-asset-admin';

import styles from './static-asset-review.module.css';
import { StaticAssetReviewWorkspace } from './static-asset-review-workspace';

export const metadata: Metadata = { title: 'Reusable template images' };
export const dynamic = 'force-dynamic';
export const revalidate = 0;

export default async function TemplateTwinStaticAssetSettingsPage() {
  // This surface manages arbitrary reusable practice media. A process
  // explicitly requested as synthetic-only must not disclose the page or even
  // evaluate its admin/service dependencies, including during partial staging
  // configuration.
  if (isTemplateTwinStagingQaRequested(process.env)) notFound();

  const actor = await requireTemplateTwinStaticAssetAdmin().catch(() => null);
  if (!actor) notFound();

  void logAudit({
    action: 'VIEWED_SETTINGS',
    targetType: 'TemplateTwinStaticAssetIndex',
    targetId: actor.practiceId,
    userId: actor.userId,
    userEmail: actor.userEmail,
    practiceId: actor.practiceId,
    metadata: { source: 'rsc:/settings/note-format/static-assets' },
  });

  return (
    <AppFrame>
      <div className={styles.shell}>
        <Link className={styles.backLink} href="/settings#note-format">
          ← Back to note format
        </Link>
        <header className={styles.header}>
          <div className={styles.eyebrow}>Template Twin · practice administration</div>
          <h1 className={styles.title}>Reusable template images</h1>
          <p className={styles.subtitle}>
            Review a blank practice logo or mark once, then bind only those exact
            approved bytes to new Word-template versions. This does not approve
            patient images, signatures, or completed forms.
          </p>
        </header>
        <StaticAssetReviewWorkspace />
      </div>
    </AppFrame>
  );
}
