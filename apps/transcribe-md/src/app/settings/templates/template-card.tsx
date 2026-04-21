'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import * as Dialog from '@radix-ui/react-dialog';
import { AlertTriangle, Loader2, Trash2, X, FileText } from 'lucide-react';
import { toast } from 'sonner';

interface TemplateCardProps {
  template: {
    id: string;
    name: string;
    originalFileName: string;
    tokens: string[];
    createdAt: string;
  };
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}

export function TemplateCard({ template }: TemplateCardProps) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [pending, setPending] = useState(false);

  async function onConfirmDelete() {
    setPending(true);
    try {
      const res = await fetch(`/api/templates/${template.id}`, {
        method: 'DELETE',
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        toast.error('Could not delete template', {
          description: body?.error ?? `Server returned ${res.status}.`,
        });
        return;
      }
      toast.success('Template deleted');
      setOpen(false);
      router.refresh();
    } catch {
      toast.error('Could not delete template', {
        description: 'Network error.',
      });
    } finally {
      setPending(false);
    }
  }

  const visibleTokens = template.tokens.slice(0, 5);
  const remaining = template.tokens.length - visibleTokens.length;

  return (
    <div className="flex flex-col justify-between rounded-xl border border-border-default bg-bg-surface-1/60 p-5 transition-colors hover:border-border-emphasis">
      <div>
        <div className="flex items-start justify-between gap-2">
          <div className="flex items-start gap-2.5 min-w-0">
            <div
              aria-hidden
              className="mt-0.5 flex h-8 w-8 flex-none items-center justify-center rounded-lg bg-violet-500/10 text-violet-300"
            >
              <FileText className="h-4 w-4" aria-hidden />
            </div>
            <div className="min-w-0">
              <div className="truncate text-[14px] font-medium text-text-primary">
                {template.name}
              </div>
              <div className="truncate text-[11px] text-text-muted">
                {template.originalFileName}
              </div>
            </div>
          </div>

          <Dialog.Root open={open} onOpenChange={setOpen}>
            <Dialog.Trigger asChild>
              <button
                type="button"
                aria-label={`Delete ${template.name}`}
                className="flex-none rounded-md p-1.5 text-text-muted transition-colors hover:bg-red-500/10 hover:text-red-300 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-500/50"
              >
                <Trash2 className="h-4 w-4" aria-hidden />
              </button>
            </Dialog.Trigger>
            <Dialog.Portal>
              <Dialog.Overlay className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm animate-in fade-in duration-150" />
              <Dialog.Content className="fixed left-1/2 top-1/2 z-50 w-[min(460px,calc(100vw-32px))] -translate-x-1/2 -translate-y-1/2 rounded-xl border border-border-default bg-bg-surface-1 p-6 shadow-2xl animate-in fade-in zoom-in-95 duration-150">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <Dialog.Title className="flex items-center gap-2 text-[15px] font-semibold text-text-primary">
                      <AlertTriangle className="h-4 w-4 text-red-400" />
                      Delete this template?
                    </Dialog.Title>
                    <Dialog.Description className="mt-1.5 text-[13px] leading-relaxed text-text-tertiary">
                      “{template.name}” will no longer be available on new visits.
                      Visits that were already generated with this template keep
                      their filled .docx downloads.
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
                <div className="mt-6 flex items-center justify-end gap-2">
                  <Dialog.Close asChild>
                    <button
                      type="button"
                      disabled={pending}
                      className="rounded-lg border border-border-default bg-bg-surface-1/60 px-4 py-2 text-[13px] font-medium text-text-secondary transition-colors hover:bg-bg-surface-1 disabled:opacity-50"
                    >
                      Cancel
                    </button>
                  </Dialog.Close>
                  <button
                    type="button"
                    disabled={pending}
                    onClick={onConfirmDelete}
                    className="inline-flex items-center justify-center gap-2 rounded-lg bg-red-500 px-4 py-2 text-[13px] font-medium text-white shadow-[0_0_0_1px_rgba(239,68,68,0.4),0_8px_24px_-8px_rgba(239,68,68,0.5)] transition-all hover:bg-red-600 disabled:opacity-50 disabled:pointer-events-none"
                  >
                    {pending ? (
                      <>
                        <Loader2 className="h-4 w-4 animate-spin" />
                        Deleting…
                      </>
                    ) : (
                      'Delete'
                    )}
                  </button>
                </div>
              </Dialog.Content>
            </Dialog.Portal>
          </Dialog.Root>
        </div>

        <div className="mt-4">
          <div className="text-[11px] uppercase tracking-wider text-text-muted">
            Placeholders ({template.tokens.length})
          </div>
          {template.tokens.length === 0 ? (
            <div className="mt-1.5 text-[12px] text-text-tertiary">
              No placeholders — renders as-is every time.
            </div>
          ) : (
            <div className="mt-1.5 flex flex-wrap gap-1.5">
              {visibleTokens.map((t) => (
                <span
                  key={t}
                  className="inline-flex items-center rounded-md border border-border-subtle bg-bg-surface-2/70 px-2 py-0.5 font-mono text-[11px] text-text-secondary"
                >
                  {'{{'}
                  {t}
                  {'}}'}
                </span>
              ))}
              {remaining > 0 && (
                <span className="inline-flex items-center px-2 py-0.5 text-[11px] text-text-muted">
                  +{remaining} more
                </span>
              )}
            </div>
          )}
        </div>
      </div>

      <div className="mt-5 border-t border-border-subtle pt-3 text-[11px] text-text-muted">
        Uploaded {formatDate(template.createdAt)}
      </div>
    </div>
  );
}
