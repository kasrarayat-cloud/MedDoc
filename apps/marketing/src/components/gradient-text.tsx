import { cn } from '@/lib/cn';

/**
 * Sage italic accent inside a heading — the Clinician way to mark a
 * highlighted phrase ("doctor at the desk", "60-second", "slipped
 * through" etc.). The actual gradient + serif italic styling lives in
 * globals.css as .text-gradient-violet (legacy class name kept so call
 * sites in about/demo/signup/not-found don't need editing).
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
