import { cn } from '@/lib/cn';

/**
 * Small pill used for sub-page eyebrows ("About us", "Compliance",
 * "Coming soon", etc.). Soft sage-tint background + sage-deep text by
 * default. The optional `dot` keeps the discriminant API but every dot
 * tone now resolves to a Clinician token — there is no violet on the
 * Clinician palette so the legacy `dot="violet"` value falls through to
 * the same warm sage chip.
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
  const dotColor =
    dot === 'cyan'
      ? 'bg-[#5BA3B4]'
      : dot === 'violet'
        ? 'bg-[#7AA68C]'
        : dot === 'success'
          ? 'bg-[#7AA68C]'
          : 'bg-transparent';
  return (
    <span
      className={cn(
        'inline-flex items-center gap-2 rounded-full',
        'bg-[rgba(122,166,140,0.14)] px-3 py-1 text-[12.5px]',
        'font-medium tracking-[0.01em] text-[#2F5040]',
        className
      )}
    >
      {dot !== 'none' && (
        <span
          className={cn('inline-block h-1.5 w-1.5 rounded-full', dotColor)}
          aria-hidden
        />
      )}
      {children}
    </span>
  );
}
