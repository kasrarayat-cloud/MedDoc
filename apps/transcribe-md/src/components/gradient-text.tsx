import { cn } from '@/lib/cn';

/**
 * Violet gradient text, used for emphasis inside headings.
 * The gradient itself lives in globals.css as .text-gradient-violet so
 * we get consistent stops everywhere the brand accent shows up.
 */
export function GradientText({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <span className={cn('text-gradient-violet', className)}>{children}</span>
  );
}
