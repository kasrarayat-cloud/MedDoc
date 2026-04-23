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
        title={
          <>
            RxWarningCard <em style={{ color: 'var(--accent-bright)' }}>preview</em>
          </>
        }
        subtitle="Dev-only route. 404s in production. Use the chips to cycle variants."
      />

      <div
        style={{
          padding: '4px 32px 0',
          display: 'flex',
          gap: 6,
          flexWrap: 'wrap',
          alignItems: 'center',
          marginBottom: 20,
        }}
      >
        <span className="qm-sectlabel" style={{ marginRight: 8 }}>
          § Variant
        </span>
        {chips.map((c) => {
          const isActive = c.id === variant;
          return (
            <Link
              key={c.id}
              href={`/dev/rx-warnings?variant=${c.id}`}
              scroll={false}
              className={`qm-chip${isActive ? ' qm-chip-accent' : ''}`}
              aria-current={isActive ? 'page' : undefined}
              style={{ textDecoration: 'none', cursor: 'pointer' }}
            >
              {c.label}
            </Link>
          );
        })}
      </div>

      <div
        style={{
          padding: '0 32px 48px',
          maxWidth: 820,
          display: 'flex',
          flexDirection: 'column',
          gap: 20,
        }}
      >
        <DevRxWarningsClient variant={variant} />
      </div>
    </AppFrame>
  );
}
