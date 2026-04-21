'use client';

import { useState } from 'react';
import * as Select from '@radix-ui/react-select';
import { ChevronDown, Check } from 'lucide-react';

import { cn } from '@/lib/cn';

export interface TemplateOption {
  id: string;
  name: string;
  tokenCount: number;
}

interface Props {
  options: TemplateOption[];
  /** Form field name — value is either '' (standard only) or the
   *  TranscribeTemplate id. Matches SpecialtyDropdown's hidden-input
   *  pattern so the server action reads it off formData.entries(). */
  name: string;
}

const STANDARD_ONLY_VALUE = '__standard_only__';

export function TemplateDropdown({ options, name }: Props) {
  const [value, setValue] = useState<string>(STANDARD_ONLY_VALUE);

  const submitValue = value === STANDARD_ONLY_VALUE ? '' : value;

  return (
    <>
      <input type="hidden" name={name} value={submitValue} />

      <Select.Root value={value} onValueChange={setValue}>
        <Select.Trigger
          className={cn(
            'inline-flex w-full items-center justify-between gap-2 rounded-lg',
            'border border-border-default bg-bg-surface-1/60 px-3.5 py-2.5',
            'text-[14px] text-text-primary',
            'transition-colors duration-200 ease-[cubic-bezier(0.4,0,0.2,1)]',
            'hover:border-border-emphasis',
            'focus:outline-none focus:border-violet-500 focus:ring-2 focus:ring-violet-500/30'
          )}
          aria-label="Output template"
        >
          <Select.Value />
          <Select.Icon>
            <ChevronDown className="h-3.5 w-3.5 text-text-tertiary" aria-hidden />
          </Select.Icon>
        </Select.Trigger>

        <Select.Portal>
          <Select.Content
            position="popper"
            sideOffset={6}
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
              <Select.Item
                value={STANDARD_ONLY_VALUE}
                className={cn(
                  'relative flex cursor-pointer select-none items-center',
                  'rounded-md px-2 py-1.5 pr-8 text-[13px] text-text-secondary outline-none',
                  'data-[highlighted]:bg-bg-surface-2 data-[highlighted]:text-text-primary',
                  'data-[state=checked]:text-text-primary'
                )}
              >
                <Select.ItemText>Standard only</Select.ItemText>
                <Select.ItemIndicator className="absolute right-2">
                  <Check className="h-3.5 w-3.5 text-violet-400" aria-hidden />
                </Select.ItemIndicator>
              </Select.Item>

              {options.length > 0 && (
                <div className="my-1 h-px bg-border-subtle" aria-hidden />
              )}

              {options.map((opt) => (
                <Select.Item
                  key={opt.id}
                  value={opt.id}
                  className={cn(
                    'relative flex cursor-pointer select-none items-center justify-between gap-4',
                    'rounded-md px-2 py-1.5 pr-8 text-[13px] text-text-secondary outline-none',
                    'data-[highlighted]:bg-bg-surface-2 data-[highlighted]:text-text-primary',
                    'data-[state=checked]:text-text-primary'
                  )}
                >
                  <Select.ItemText>{opt.name}</Select.ItemText>
                  <span className="text-[11px] text-text-muted">
                    {opt.tokenCount} {opt.tokenCount === 1 ? 'slot' : 'slots'}
                  </span>
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
