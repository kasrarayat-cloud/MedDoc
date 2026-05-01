'use client';

// ============================================================================
// SpecialtyDropdown — Phase 5 Linear V1 select.
// ----------------------------------------------------------------------------
// Hairline-bordered surface-2 trigger with a sage focus ring; the
// popper renders on a surface-1 panel with hairline borders. The
// `theme` prop is preserved as a no-op.
// ============================================================================

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
  /** Optional controlled-value callback. */
  onChange?: (value: string) => void;
  /** @deprecated kept for back-compat; Linear V1 is single-theme. */
  theme?: DropdownTheme;
}

const TRIGGER = [
  'inline-flex w-full items-center justify-between gap-2 rounded-md',
  'border border-linear-border bg-linear-surface-2 px-3 py-2.5',
  'text-[14px] text-linear-text',
  'transition-colors duration-150 ease-out',
  'hover:border-linear-border-strong',
  'focus:outline-none focus:border-linear-sage focus:ring-2 focus:ring-linear-sage/30',
  'data-[placeholder]:text-linear-text-3',
].join(' ');

const CONTENT = [
  'z-[100] overflow-hidden rounded-md',
  'border border-linear-border bg-linear-surface-1',
  'shadow-[0_16px_48px_-16px_rgba(0,0,0,0.7)]',
  'min-w-[var(--radix-select-trigger-width)]',
  'max-h-[var(--radix-select-content-available-height)]',
  'data-[state=open]:animate-in data-[state=open]:fade-in-0',
  'data-[state=open]:zoom-in-95 data-[state=open]:slide-in-from-top-2',
].join(' ');

const ITEM = [
  'relative flex cursor-pointer select-none items-center',
  'rounded-sm px-2 py-1.5 pr-8 text-[13px] text-linear-text-2 outline-none',
  'data-[highlighted]:bg-linear-row-hover data-[highlighted]:text-linear-text',
  'data-[state=checked]:text-linear-text',
].join(' ');

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
      {/* Hidden input carries the value to the server action. */}
      <input type="hidden" name={name} value={value} />

      <Select.Root
        value={value || undefined}
        onValueChange={(v) => {
          setValue(v);
          onChange?.(v);
        }}
      >
        <Select.Trigger className={TRIGGER} aria-label="Specialty">
          <Select.Value placeholder={placeholder} />
          <Select.Icon>
            <ChevronDown
              className="h-3.5 w-3.5 text-linear-text-3"
              aria-hidden
            />
          </Select.Icon>
        </Select.Trigger>

        <Select.Portal>
          <Select.Content position="popper" sideOffset={6} className={CONTENT}>
            <Select.Viewport className="p-1">
              {options.map((opt) => (
                <Select.Item
                  key={opt.slug}
                  value={opt.displayName}
                  className={cn(ITEM)}
                >
                  <Select.ItemText>{opt.displayName}</Select.ItemText>
                  <Select.ItemIndicator className="absolute right-2">
                    <Check
                      className="h-3.5 w-3.5 text-linear-sage-bright"
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
