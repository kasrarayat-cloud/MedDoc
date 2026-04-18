import { cn } from '@/lib/cn';

/**
 * Small pill used for hero taglines ("Now in private beta"), status
 * chips, and section section labels. Dot on the left is optional +
 * coloured via the `dot` prop.
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
      ? 'bg-cyan-400'
      : dot === 'violet'
        ? 'bg-violet-400'
        : dot === 'success'
          ? 'bg-success'
          : 'bg-transparent';
  return (
    <span
      className={cn(
        'inline-flex items-center gap-2 rounded-full border border-border-default',
        'bg-bg-surface-2/60 backdrop-blur px-3 py-1 text-[12px]',
        'font-medium tracking-tight text-text-tertiary',
        className
      )}
    >
      {dot !== 'none' && (
        <span
          className={cn(
            'inline-block h-1.5 w-1.5 rounded-full',
            dotColor,
            dot === 'cyan' && 'shadow-[0_0_8px_rgba(34,211,238,0.6)]'
          )}
          aria-hidden
        />
      )}
      {children}
    </span>
  );
}
