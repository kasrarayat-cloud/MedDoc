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
  placeholder?: string;
  /** Optional controlled-value callback. When set, fires on every
   *  pick — callers inside a dialog (T-M17.3 Edit Draft) need to
   *  mirror the value into their own form-state-gated Save button
   *  instead of relying on the hidden input + form submission. */
  onChange?: (value: string) => void;
}

export function SpecialtyDropdown({
  options,
  name,
  defaultValue,
  placeholder = 'Pick a specialty',
  onChange,
}: SpecialtyDropdownProps) {
  // Radix Select treats value="" as the placeholder state, so we only
  // pass a real string through `value` once the user actually picks
  // something. Before that, Radix is uncontrolled and the placeholder
  // shows correctly.
  const [value, setValue] = useState<string>(defaultValue ?? '');

  return (
    <>
      {/* Hidden input carries the value to the server action. Radix's
          <Select.Value> only renders the display text, not a form field. */}
      <input type="hidden" name={name} value={value} />

      <Select.Root
        value={value || undefined}
        onValueChange={(v) => {
          setValue(v);
          onChange?.(v);
        }}
      >
        <Select.Trigger
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
            // z-100 clears the glassy NavBar (z-40) on /dashboard.
            // T-M3: tailwindcss-animate plugin (or the fallback utilities
            // in globals.css) now supplies animate-in/fade-in-0/
            // zoom-in-95, restoring the entry animation the T-M2 fix had
            // to strip when the plugin wasn't installed.
            className={cn(
              'z-[100] overflow-hidden rounded-lg',
              'border border-border-default bg-bg-surface-1/95 backdrop-blur',
              'shadow-[0_16px_48px_-16px_rgba(0,0,0,0.7)]',
              'min-w-[var(--radix-select-trigger-width)]',
              'max-h-[var(--radix-select-content-available-height)]',
              'data-[state=open]:animate-in data-[state=open]:fade-in-0',
              'data-[state=open]:zoom-in-95 data-[state=open]:slide-in-from-top-2'
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
