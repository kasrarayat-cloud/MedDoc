import { cn } from '@/lib/cn';

/**
 * Sub-page eyebrow pill — Linear V1 (Faithful).
 *
 * Sage-tint background, sage-bright text, hairline sage border. The
 * `dot` prop is kept for back-compat with all the existing call sites
 * but every value resolves to a single Linear V1 sage chip.
 */
export function Badge({
  children,
  dot = 'cyan',
  className,
}: {
  children: React.ReactNode;
  dot?: 'cyan' | 'violet' | 'success' | 'none';
  className?: string;
}) {
  return (
    <span
      className={cn('qm-lin-pill qm-lin-pill--sage', className)}
      style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}
    >
      {dot !== 'none' && (
        <span
          aria-hidden
          style={{
            display: 'inline-block',
            width: 5,
            height: 5,
            borderRadius: '50%',
            background: 'var(--color-linear-sage-bright)',
          }}
        />
      )}
      {children}
    </span>
  );
}
