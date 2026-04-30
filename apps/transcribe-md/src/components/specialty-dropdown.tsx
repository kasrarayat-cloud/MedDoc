'use client';

import { useState } from 'react';
import * as Select from '@radix-ui/react-select';
import { ChevronDown, Check } from 'lucide-react';

import { cn } from '@/lib/cn';

export interface SpecialtyOption {
  slug: string;
  displayName: string;
}

type DropdownTheme = 'legacy' | 'clinician';

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
  /** Visual theme. `'legacy'` (default) keeps the dark-glass + violet
   *  focus ring. `'clinician'` reskins to `.qm-cl-input` chrome (warm
   *  cream surface + sage focus ring + cream-card popper). */
  theme?: DropdownTheme;
}

const LEGACY_TRIGGER = [
  'inline-flex w-full items-center justify-between gap-2 rounded-lg',
  'border border-border-default bg-bg-surface-1/60 px-3.5 py-2.5',
  'text-[14px] text-text-primary',
  'transition-colors duration-200 ease-[cubic-bezier(0.4,0,0.2,1)]',
  'hover:border-border-emphasis',
  'focus:outline-none focus:border-violet-500 focus:ring-2 focus:ring-violet-500/30',
  'data-[placeholder]:text-text-muted',
].join(' ');

const CLINICIAN_TRIGGER = [
  'qm-cl-input',
  // Layout overrides for the trigger (qm-cl-input is sized for text
  // inputs; the dropdown trigger needs flex + gap)
  'inline-flex w-full items-center justify-between gap-2',
  'data-[placeholder]:text-clinician-ink-4',
].join(' ');

const LEGACY_CONTENT = [
  'z-[100] overflow-hidden rounded-lg',
  'border border-border-default bg-bg-surface-1/95 backdrop-blur',
  'shadow-[0_16px_48px_-16px_rgba(0,0,0,0.7)]',
  'min-w-[var(--radix-select-trigger-width)]',
  'max-h-[var(--radix-select-content-available-height)]',
  'data-[state=open]:animate-in data-[state=open]:fade-in-0',
  'data-[state=open]:zoom-in-95 data-[state=open]:slide-in-from-top-2',
].join(' ');

const CLINICIAN_CONTENT = [
  'z-[100] overflow-hidden rounded-xl',
  'border border-clinician-line bg-clinician-cream-card',
  'shadow-[0_8px_24px_rgba(43,38,32,0.06)]',
  'min-w-[var(--radix-select-trigger-width)]',
  'max-h-[var(--radix-select-content-available-height)]',
  'data-[state=open]:animate-in data-[state=open]:fade-in-0',
  'data-[state=open]:zoom-in-95 data-[state=open]:slide-in-from-top-2',
].join(' ');

const LEGACY_ITEM = [
  'relative flex cursor-pointer select-none items-center',
  'rounded-md px-2 py-1.5 pr-8 text-[13px] text-text-secondary outline-none',
  'data-[highlighted]:bg-bg-surface-2 data-[highlighted]:text-text-primary',
  'data-[state=checked]:text-text-primary',
].join(' ');

const CLINICIAN_ITEM = [
  'relative flex cursor-pointer select-none items-center',
  'rounded-md px-2 py-1.5 pr-8 text-[13px] text-clinician-ink-2 outline-none',
  'data-[highlighted]:bg-clinician-cream-2 data-[highlighted]:text-clinician-ink',
  'data-[state=checked]:text-clinician-ink',
].join(' ');

export function SpecialtyDropdown({
  options,
  name,
  defaultValue,
  placeholder = 'Pick a specialty',
  onChange,
  theme = 'legacy',
}: SpecialtyDropdownProps) {
  // Radix Select treats value="" as the placeholder state, so we only
  // pass a real string through `value` once the user actually picks
  // something. Before that, Radix is uncontrolled and the placeholder
  // shows correctly.
  const [value, setValue] = useState<string>(defaultValue ?? '');

  const isClinician = theme === 'clinician';

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
          className={cn(isClinician ? CLINICIAN_TRIGGER : LEGACY_TRIGGER)}
          aria-label="Specialty"
        >
          <Select.Value placeholder={placeholder} />
          <Select.Icon>
            <ChevronDown
              className={cn(
                'h-3.5 w-3.5',
                isClinician ? 'text-clinician-ink-3' : 'text-text-tertiary'
              )}
              aria-hidden
            />
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
            className={cn(isClinician ? CLINICIAN_CONTENT : LEGACY_CONTENT)}
          >
            <Select.Viewport className="p-1">
              {options.map((opt) => (
                <Select.Item
                  key={opt.slug}
                  value={opt.displayName}
                  className={cn(isClinician ? CLINICIAN_ITEM : LEGACY_ITEM)}
                >
                  <Select.ItemText>{opt.displayName}</Select.ItemText>
                  <Select.ItemIndicator className="absolute right-2">
                    <Check
                      className={cn(
                        'h-3.5 w-3.5',
                        isClinician ? 'text-clinician-sage' : 'text-violet-400'
                      )}
                      aria-hidden
                    />
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
