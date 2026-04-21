'use client';

import { useState } from 'react';
import * as Dialog from '@radix-ui/react-dialog';
import { BookOpen, X } from 'lucide-react';

import { SUPPORTED_TOKENS } from '@/lib/template-tokens';

const TOKEN_DESCRIPTIONS: Record<string, string> = {
  chief_complaint: 'Single-line complaint, e.g. “knee pain for 3 days”.',
  hpi: 'History of present illness — SOAP narrative.',
  pmh: 'Past medical history summary.',
  medications: 'Current medications at time of visit.',
  allergies: 'Known allergies + reactions.',
  ros: 'Review of systems findings.',
  exam: 'Physical exam findings.',
  assessment: 'Clinical impression / diagnoses.',
  plan: 'Treatment plan + follow-up.',
};

export function TemplateGuideButton() {
  const [open, setOpen] = useState(false);
  return (
    <Dialog.Root open={open} onOpenChange={setOpen}>
      <Dialog.Trigger asChild>
        <button
          type="button"
          className="inline-flex items-center gap-1.5 rounded-full border border-border-default bg-bg-surface-1/60 px-3 py-1.5 text-[12px] text-text-secondary transition-colors hover:border-border-emphasis hover:text-text-primary"
        >
          <BookOpen className="h-3.5 w-3.5" aria-hidden />
          Template guide
        </button>
      </Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm animate-in fade-in duration-150" />
        <Dialog.Content className="fixed left-1/2 top-1/2 z-50 w-[min(640px,calc(100vw-32px))] max-h-[85vh] -translate-x-1/2 -translate-y-1/2 overflow-y-auto rounded-xl border border-border-default bg-bg-surface-1 p-6 shadow-2xl animate-in fade-in zoom-in-95 duration-150">
          <div className="flex items-start justify-between gap-4">
            <div>
              <Dialog.Title className="text-[16px] font-semibold text-text-primary">
                How templates work
              </Dialog.Title>
              <Dialog.Description className="mt-1.5 text-[13px] leading-relaxed text-text-tertiary">
                Write a Word document exactly the way you want your final note
                to look — fonts, headings, tables, letterhead, all preserved.
                Drop a placeholder anywhere you want AI-generated content.
              </Dialog.Description>
            </div>
            <Dialog.Close asChild>
              <button
                type="button"
                aria-label="Close"
                className="text-text-muted transition-colors hover:text-text-primary"
              >
                <X className="h-4 w-4" aria-hidden />
              </button>
            </Dialog.Close>
          </div>

          <section className="mt-6">
            <h3 className="text-[13px] font-semibold text-text-primary">
              Placeholder syntax
            </h3>
            <p className="mt-1 text-[12px] text-text-tertiary">
              Use double-brace mustache tokens —{' '}
              <code className="font-mono text-text-secondary">
                {'{{placeholder_name}}'}
              </code>
              . Lowercase and underscores only. Anywhere the token appears
              gets replaced with the AI-generated content for that slot.
            </p>
            <pre className="mt-3 rounded-lg border border-border-subtle bg-bg-surface-2/70 p-3 font-mono text-[12px] leading-relaxed text-text-secondary">{`Chief Complaint: {{chief_complaint}}

History of Present Illness:
{{hpi}}

Assessment and Plan:
{{assessment}}

{{plan}}`}</pre>
          </section>

          <section className="mt-6">
            <h3 className="text-[13px] font-semibold text-text-primary">
              Supported placeholders
            </h3>
            <p className="mt-1 text-[12px] text-text-tertiary">
              These nine tokens are filled from the visit transcript and
              polished SOAP note. Other placeholder names you add will render
              blank in the downloaded copy.
            </p>
            <ul className="mt-3 space-y-2">
              {SUPPORTED_TOKENS.map((t) => (
                <li key={t} className="flex items-start gap-3">
                  <span className="inline-flex w-44 flex-none font-mono text-[12px] text-violet-300">
                    {'{{'}
                    {t}
                    {'}}'}
                  </span>
                  <span className="text-[12px] text-text-tertiary">
                    {TOKEN_DESCRIPTIONS[t] ?? ''}
                  </span>
                </li>
              ))}
            </ul>
          </section>

          <section className="mt-6">
            <h3 className="text-[13px] font-semibold text-text-primary">
              Tips
            </h3>
            <ul className="mt-2 list-disc space-y-1.5 pl-5 text-[12px] leading-relaxed text-text-tertiary">
              <li>
                Use plain text for placeholders — no bold, italics, or colour
                on the token itself. Formatting around the token is preserved
                as you laid it out.
              </li>
              <li>
                Tables, headers, footers, and letterhead images are fine —
                they survive the fill step unchanged.
              </li>
              <li>
                If a visit doesn&apos;t have content for a placeholder, the
                slot renders blank. You can always sign a visit and manually
                fill in anything the AI left empty.
              </li>
            </ul>
          </section>

          <div className="mt-6 flex justify-end">
            <Dialog.Close asChild>
              <button
                type="button"
                className="rounded-lg border border-border-default bg-bg-surface-1/60 px-4 py-2 text-[13px] font-medium text-text-secondary transition-colors hover:bg-bg-surface-1"
              >
                Close
              </button>
            </Dialog.Close>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
