'use client';

import { useState } from 'react';
import * as Select from '@radix-ui/react-select';
import { ChevronDown, Check } from 'lucide-react';

import { cn } from '@/lib/cn';

export interface SpecialtyOption {
  slug: string;
  displayName: string;
}

interface SpecialtyDropdownProps {
  options: SpecialtyOption[];
  /** Form field name — the selected displayName is what gets submitted so
   *  the TranscribeVisit.specialty column stays human-readable. */
  name: string;
  defaultValue?: string;
  /** When true, the trigger takes focus on mount — used on /visits/new
   *  where specialty is the first decision the clinician makes. */
  autoFocus?: boolean;
  placeholder?: string;
}

export function SpecialtyDropdown({
  options,
  name,
  defaultValue,
  autoFocus,
  placeholder = 'Pick a specialty',
}: SpecialtyDropdownProps) {
  const [value, setValue] = useState<string>(defaultValue ?? '');

  return (
    <>
      {/* Hidden input carries the value to the server action. Radix Select's
          own <Select.Value> only renders the display text, not a form field. */}
      <input type="hidden" name={name} value={value} />

      <Select.Root value={value} onValueChange={setValue}>
        <Select.Trigger
          autoFocus={autoFocus}
          className={cn(
            'inline-flex w-full items-center justify-between gap-2 rounded-lg',
            'border border-border-default bg-bg-surface-1/60 px-3.5 py-2.5',
            'text-[14px] text-text-primary',
            'transition-colors duration-200 ease-[cubic-bezier(0.4,0,0.2,1)]',
            'hover:border-border-emphasis',
            'focus:outline-none focus:border-violet-500 focus:ring-2 focus:ring-violet-500/30',
            'data-[placeholder]:text-text-muted'
          )}
          aria-label="Specialty"
        >
          <Select.Value placeholder={placeholder} />
          <Select.Icon>
            <ChevronDown className="h-3.5 w-3.5 text-text-tertiary" aria-hidden />
          </Select.Icon>
        </Select.Trigger>

        <Select.Portal>
          <Select.Content
            position="popper"
            sideOffset={6}
            className={cn(
              'z-50 overflow-hidden rounded-lg',
              'border border-border-default bg-bg-surface-1/95 backdrop-blur',
              'shadow-[0_16px_48px_-16px_rgba(0,0,0,0.7)]',
              'min-w-[var(--radix-select-trigger-width)]',
              'data-[state=open]:animate-in data-[state=open]:fade-in-0'
            )}
          >
            <Select.Viewport className="p-1">
              {options.map((opt) => (
                <Select.Item
                  key={opt.slug}
                  value={opt.displayName}
                  className={cn(
                    'relative flex cursor-pointer select-none items-center',
                    'rounded-md px-2 py-1.5 pr-8 text-[13px] text-text-secondary outline-none',
                    'data-[highlighted]:bg-bg-surface-2 data-[highlighted]:text-text-primary',
                    'data-[state=checked]:text-text-primary'
                  )}
                >
                  <Select.ItemText>{opt.displayName}</Select.ItemText>
                  <Select.ItemIndicator className="absolute right-2">
                    <Check className="h-3.5 w-3.5 text-violet-400" aria-hidden />
                  </Select.ItemIndicator>
                </Select.Item>
              ))}
            </Select.Viewport>
          </Select.Content>
        </Select.Portal>
      </Select.Root>
    </>
  );
}
