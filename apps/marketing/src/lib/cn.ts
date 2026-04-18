import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

/**
 * Conditional + merge class utility.
 *
 *   cn('px-4', isOn && 'bg-violet-500', className)
 *
 * twMerge resolves Tailwind conflicts (last-wins on same utility family)
 * so downstream `className` props can override without fighting.
 */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}
