// ============================================================================
// /dev/rx-warnings — dev-only preview of RxWarningCard variants.
// ----------------------------------------------------------------------------
// 404s in production builds. Exposes every severity + collapsed/expanded
// state against hardcoded fixtures so designers + QA can eyeball the
// card without needing a real worker-emitted warning in the DB.
//
// Override flow runs against `recordOverride()` with a "dev-preview"
// sentinel visitId that short-circuits the DB write (see
// lib/rx-warning-audit.ts §Dev preview).
//
// Phase 5 (Linear V1 Faithful) — chrome around the warning card uses
// the dark canvas + sage active chip pattern. The `.qm-warn-*` family
// inside the cards themselves is owned by Stage 2 and stays as-is.
// ============================================================================

import type { Metadata } from 'next';
import Link from 'next/link';
import { notFound } from 'next/navigation';

import { AppFrame } from '@/components/ui/app-frame';
import { PageHeader } from '@/components/ui/page-header';
import { DevRxWarningsClient } from './client';

export const metadata: Metadata = { title: 'Rx warning card — preview' };

type SearchParams = Record<string, string | string[] | undefined>;

type Variant =
  | 'critical'
  | 'warning'
  | 'info'
  | 'collapsed'
  | 'expanded'
  | 'in-context';

function resolveVariant(raw: string | undefined): Variant {
  switch (raw) {
    case 'warning':
    case 'info':
    case 'collapsed':
    case 'expanded':
    case 'in-context':
      return raw;
    default:
      return 'critical';
  }
}

export default async function DevRxWarningsPage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  if (process.env.NODE_ENV === 'production') notFound();

  const sp = await searchParams;
  const variantParam = Array.isArray(sp.variant) ? sp.variant[0] : sp.variant;
  const variant = resolveVariant(variantParam);

  const chips: { id: Variant; label: string }[] = [
    { id: 'critical', label: 'Critical' },
    { id: 'warning', label: 'Warning' },
    { id: 'info', label: 'Info' },
    { id: 'collapsed', label: 'Collapsed' },
    { id: 'expanded', label: 'Expanded' },
    { id: 'in-context', label: 'In context' },
  ];

  return (
    <AppFrame>
      <PageHeader
        eyebrow="§ Dev / Rx warnings"
        title="Rx Warning Card Reference (DEV)"
        subtitle="Dev-only route. 404s in production. Use the chips to cycle variants."
      />

      <div className="mb-5 flex flex-wrap items-center gap-1.5 px-8">
        <span className="mr-2 font-mono text-[10px] font-medium uppercase tracking-[0.08em] text-linear-text-3">
          § Variant
        </span>
        {chips.map((c) => {
          const isActive = c.id === variant;
          return (
            <Link
              key={c.id}
              href={`/dev/rx-warnings?variant=${c.id}`}
              scroll={false}
              aria-current={isActive ? 'page' : undefined}
              className={
                'inline-flex h-7 items-center rounded-full px-3 text-xs font-medium transition-colors no-underline ' +
                (isActive
                  ? 'bg-linear-sage-tint text-linear-sage-bright'
                  : 'bg-linear-surface-2 text-linear-text-2 hover:bg-linear-surface-3 hover:text-linear-text')
              }
            >
              {c.label}
            </Link>
          );
        })}
      </div>

      <div className="flex max-w-[820px] flex-col gap-5 px-8 pb-12">
        <DevRxWarningsClient variant={variant} />
      </div>
    </AppFrame>
  );
}
