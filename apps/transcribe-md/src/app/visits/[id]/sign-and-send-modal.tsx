'use client';

import { useCallback, useState, useTransition } from 'react';
import { useRouter } from 'next/navigation';
import * as Dialog from '@radix-ui/react-dialog';
import { Check, Loader2, Lock, Send, X } from 'lucide-react';
import { toast } from 'sonner';

import { cn } from '@/lib/cn';
import { SpecularButton } from '@/components/specular-button';

export type Destination =
  | 'clipboard_epic'
  | 'clipboard_athena'
  | 'clipboard_cerner'
  | 'clipboard_eclinicalworks'
  | 'clipboard_generic'
  | 'pdf'
  | 'docx'
  | 'email';

const DESTINATIONS: {
  key: Destination;
  label: string;
  group: 'clipboard' | 'download' | 'email';
}[] = [
  { key: 'clipboard_epic', label: 'Copy for Epic', group: 'clipboard' },
  { key: 'clipboard_athena', label: 'Copy for Athena', group: 'clipboard' },
  { key: 'clipboard_cerner', label: 'Copy for Cerner', group: 'clipboard' },
  {
    key: 'clipboard_eclinicalworks',
    label: 'Copy for eClinicalWorks',
    group: 'clipboard',
  },
  { key: 'clipboard_generic', label: 'Copy as plain text', group: 'clipboard' },
  { key: 'pdf', label: 'Download PDF', group: 'download' },
  { key: 'docx', label: 'Download DOCX', group: 'download' },
  { key: 'email', label: 'Email to me', group: 'email' },
];

interface SignResponse {
  signedAt: string | null;
  clipboardTexts?: Partial<Record<Destination, string>>;
  pdfDownloadUrl?: string;
  docxDownloadUrl?: string;
  emailQueued?: boolean;
  deliveryErrors?: Record<string, string>;
}

interface SignAndSendModalProps {
  visitId: string;
  doctorEmail: string;
  /** When `signOnSubmit=true`, submitting calls /sign. When false, it
   *  calls the individual export routes directly (used on already-
   *  SIGNED visits so "Export again" doesn't try to re-sign). */
  signOnSubmit: boolean;
  /** The trigger button's label — "Sign & Send" vs "Export again". */
  triggerLabel: string;
  /** Icon shown on the trigger. */
  triggerIcon: React.ReactNode;
  /** Variant of the trigger button — primary for sign, secondary for
   *  re-export. */
  triggerVariant?: 'primary' | 'secondary';
  /** Disable the trigger while parent is saving edits, etc. */
  disabled?: boolean;
}

export function SignAndSendModal(props: SignAndSendModalProps) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [selected, setSelected] = useState<Set<Destination>>(
    () => new Set(['clipboard_epic', 'pdf'])
  );
  const [pending, startTransition] = useTransition();
  // Selections persist across open/close so a doctor who always picks
  // the same two targets doesn't re-check them every time.

  const toggle = useCallback((key: Destination) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }, []);

  const submit = useCallback(() => {
    const destinations = Array.from(selected);
    if (destinations.length === 0) {
      toast.error('Pick at least one destination.');
      return;
    }
    startTransition(async () => {
      try {
        // Step 1: the server-side work (sign + collect clipboard text /
        // URLs / email-queued status). This is the ONLY thing awaited
        // inside the transition — once it returns, the visit is signed
        // in the DB and we know what to hand to the browser.
        const payload = props.signOnSubmit
          ? await fetchSignAndDeliver(props.visitId, destinations)
          : await prepareDeliverOnly(props.visitId, destinations);

        // Step 2: close the modal + refresh the page BEFORE firing any
        // browser-side delivery. `pending` (useTransition) clears here,
        // so even if a download stalls or navigator.clipboard hangs on
        // an expired user-activation, the spinner never gets stuck.
        setOpen(false);
        router.refresh();

        // Step 3: classify outcome. Previously we ALWAYS fired the
        // green "Signed" toast and then a tiny "some destinations
        // failed" one — users missed the second toast and assumed
        // email was sent. Now we branch: setup errors get a loud
        // persistent error toast; partial failures get a warning;
        // only clean runs show the green success.
        const deliveryErrors = payload.deliveryErrors ?? {};
        const failedEntries = Object.entries(deliveryErrors);
        const setupErrors = failedEntries.filter(([, msg]) =>
          /isn't set up|not configured|EMAIL_NOT_CONFIGURED/i.test(msg)
        );
        const failureSummary = failedEntries
          .map(([k, v]) => `${k}: ${v}`)
          .join('\n');

        if (setupErrors.length > 0) {
          toast.error('Email delivery not configured', {
            description: `${setupErrors[0][1]}\n\nAll other destinations ran normally — PDF/DOCX/clipboard have been delivered. Download the PDF if you need the record immediately.`,
            duration: 15_000,
          });
          if (failedEntries.length > setupErrors.length) {
            const rest = failedEntries
              .filter(([k]) => !setupErrors.some(([sk]) => sk === k))
              .map(([k, v]) => `${k}: ${v}`)
              .join('\n');
            toast.error('Other destinations also failed', {
              description: rest,
              duration: 10_000,
            });
          }
        } else if (failedEntries.length > 0) {
          toast.warning(
            props.signOnSubmit
              ? 'Signed — some destinations failed'
              : 'Partial export',
            {
              description: failureSummary,
              duration: 10_000,
            }
          );
        } else {
          toast.success(props.signOnSubmit ? 'Signed' : 'Exported', {
            description: props.signOnSubmit
              ? 'Your note is locked. Delivered to the chosen destinations.'
              : 'Delivered to the chosen destinations.',
          });
        }

        // Step 4: fire-and-forget the browser-side deliveries. Errors
        // surface as toasts, but crucially they don't block the modal.
        void applyBrowserSideDeliveries(payload, destinations).catch(
          (err: unknown) => {
            console.error('[sign] browser-side delivery failed:', err);
            toast.error('Some deliveries were blocked by the browser', {
              description:
                'Try copy/download again from the signed-visit view.',
            });
          }
        );
      } catch (err) {
        const msg = err instanceof Error ? err.message : 'Unknown error';
        toast.error('Could not deliver', { description: msg });
      }
    });
  }, [props.visitId, props.signOnSubmit, router, selected]);

  return (
    <Dialog.Root open={open} onOpenChange={setOpen}>
      <Dialog.Trigger asChild>
        <SpecularButton
          variant={props.triggerVariant ?? 'primary'}
          size="md"
          disabled={props.disabled}
        >
          {props.triggerIcon}
          {props.triggerLabel}
        </SpecularButton>
      </Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Overlay
          className={cn(
            'fixed inset-0 z-[200] bg-black/60 backdrop-blur-sm',
            'data-[state=open]:animate-in data-[state=open]:fade-in-0',
            'data-[state=closed]:animate-out data-[state=closed]:fade-out-0'
          )}
        />
        <Dialog.Content
          aria-describedby={undefined}
          className={cn(
            'fixed left-1/2 top-[10vh] z-[201] w-[min(94vw,560px)] -translate-x-1/2',
            'rounded-2xl border border-border-default bg-bg-surface-1/95 backdrop-blur-xl',
            'shadow-[0_32px_96px_-24px_rgba(0,0,0,0.9),0_0_0_1px_rgba(139,92,246,0.15)]',
            'focus:outline-none',
            'data-[state=open]:animate-in data-[state=open]:fade-in-0',
            'data-[state=open]:zoom-in-95 data-[state=open]:slide-in-from-top-2',
            'data-[state=closed]:animate-out data-[state=closed]:fade-out-0',
            'data-[state=closed]:zoom-out-95'
          )}
        >
          <div className="flex items-start justify-between gap-4 p-6">
            <div>
              <Dialog.Title className="text-[16px] font-semibold text-text-primary">
                {props.signOnSubmit
                  ? 'Sign and deliver your note'
                  : 'Export signed note'}
              </Dialog.Title>
              <p className="mt-1 text-[13px] text-text-tertiary">
                Pick one or more destinations.{' '}
                {props.signOnSubmit && 'The note locks after signing.'}
              </p>
            </div>
            <Dialog.Close asChild>
              <button
                type="button"
                aria-label="Close"
                className="rounded-md p-1 text-text-muted transition-colors hover:bg-bg-surface-2 hover:text-text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500"
              >
                <X className="h-4 w-4" aria-hidden />
              </button>
            </Dialog.Close>
          </div>

          <div className="max-h-[60vh] overflow-y-auto px-6 pb-2">
            <Group
              title="Copy to clipboard"
              hint="Paste the formatted note into your EHR's note field."
              items={DESTINATIONS.filter((d) => d.group === 'clipboard')}
              selected={selected}
              onToggle={toggle}
            />
            <Group
              title="Download"
              hint="Save a PDF for records or a DOCX to edit in Word."
              items={DESTINATIONS.filter((d) => d.group === 'download')}
              selected={selected}
              onToggle={toggle}
            />
            <Group
              title="Email"
              hint={`Send a PDF to ${props.doctorEmail} for your records. Don't use for patient communication.`}
              items={DESTINATIONS.filter((d) => d.group === 'email')}
              selected={selected}
              onToggle={toggle}
            />
          </div>

          <div className="flex items-center justify-between gap-3 border-t border-border-subtle bg-bg-surface-2/40 px-6 py-3">
            <p className="text-[11px] text-text-muted">
              {props.signOnSubmit
                ? 'Locked notes can still be re-exported later.'
                : 'This visit is already signed.'}
            </p>
            <div className="flex items-center gap-3">
              <Dialog.Close asChild>
                <SpecularButton variant="secondary" size="sm" sweep={false}>
                  Cancel
                </SpecularButton>
              </Dialog.Close>
              <SpecularButton
                variant="primary"
                size="sm"
                onClick={submit}
                disabled={pending}
              >
                {pending ? (
                  <>
                    <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden />
                    {props.signOnSubmit ? 'Signing…' : 'Exporting…'}
                  </>
                ) : (
                  <>
                    {props.signOnSubmit ? (
                      <Lock className="h-3.5 w-3.5" aria-hidden />
                    ) : (
                      <Send className="h-3.5 w-3.5" aria-hidden />
                    )}
                    {props.signOnSubmit ? 'Sign & Deliver' : 'Deliver'}
                  </>
                )}
              </SpecularButton>
            </div>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function Group({
  title,
  hint,
  items,
  selected,
  onToggle,
}: {
  title: string;
  hint: string;
  items: { key: Destination; label: string }[];
  selected: Set<Destination>;
  onToggle: (k: Destination) => void;
}) {
  return (
    <div className="py-3">
      <div className="mb-1 text-[11px] font-semibold uppercase tracking-wider text-text-muted">
        {title}
      </div>
      <div className="mb-2 text-[12px] text-text-tertiary">{hint}</div>
      <div className="space-y-1.5">
        {items.map((it) => (
          <CheckboxRow
            key={it.key}
            label={it.label}
            checked={selected.has(it.key)}
            onToggle={() => onToggle(it.key)}
          />
        ))}
      </div>
    </div>
  );
}

function CheckboxRow({
  label,
  checked,
  onToggle,
}: {
  label: string;
  checked: boolean;
  onToggle: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onToggle}
      aria-pressed={checked}
      className={cn(
        'flex w-full items-center gap-3 rounded-lg border px-3 py-2 text-left',
        'transition-colors duration-150 ease-[cubic-bezier(0.4,0,0.2,1)]',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 focus-visible:ring-offset-2 focus-visible:ring-offset-bg-base',
        checked
          ? 'border-violet-500/50 bg-violet-500/10 text-text-primary'
          : 'border-border-subtle bg-bg-surface-2/40 text-text-secondary hover:border-border-default hover:text-text-primary'
      )}
    >
      <span
        aria-hidden
        className={cn(
          'flex h-4 w-4 flex-none items-center justify-center rounded-[4px] border',
          checked
            ? 'border-violet-500 bg-violet-500 text-white'
            : 'border-border-emphasis bg-transparent'
        )}
      >
        {checked && <Check className="h-3 w-3" strokeWidth={3} aria-hidden />}
      </span>
      <span className="flex-1 text-[13px]">{label}</span>
    </button>
  );
}

// ---------------------------------------------------------------------------
// Delivery runners — separated so the sign vs re-export flows share the
// browser-side actions (copy to clipboard / trigger download) while the
// server call differs.
// ---------------------------------------------------------------------------

async function fetchSignAndDeliver(
  visitId: string,
  destinations: Destination[]
): Promise<SignResponse> {
  const res = await fetch(`/api/visits/${visitId}/sign`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ destinations }),
  });
  const body = (await res.json()) as SignResponse & { error?: string };
  if (!res.ok) {
    throw new Error(body?.error ?? `sign failed (${res.status})`);
  }
  return body;
}

async function prepareDeliverOnly(
  visitId: string,
  destinations: Destination[]
): Promise<SignResponse> {
  // Already-signed path: hit the per-channel routes + collect into a
  // SignResponse-shaped payload so the caller can hand it to
  // applyBrowserSideDeliveries exactly like the sign path does.
  const clipboardTexts: Partial<Record<Destination, string>> = {};
  let pdfDownloadUrl: string | undefined;
  let docxDownloadUrl: string | undefined;
  let emailQueued = false;

  for (const dest of destinations) {
    if (dest === 'pdf') {
      pdfDownloadUrl = `/api/visits/${visitId}/export/pdf`;
    } else if (dest === 'docx') {
      docxDownloadUrl = `/api/visits/${visitId}/export/docx`;
    } else if (dest === 'email') {
      const res = await fetch(`/api/visits/${visitId}/export/email`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
      });
      if (!res.ok) {
        const body = (await res.json().catch(() => ({}))) as { error?: string };
        throw new Error(body.error ?? `email failed (${res.status})`);
      }
      emailQueued = true;
    } else {
      const format = dest.replace('clipboard_', '');
      const res = await fetch(`/api/visits/${visitId}/export/clipboard`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ format }),
      });
      if (!res.ok) {
        const body = (await res.json().catch(() => ({}))) as { error?: string };
        throw new Error(body.error ?? `clipboard failed (${res.status})`);
      }
      const body = (await res.json()) as { text: string };
      clipboardTexts[dest] = body.text;
    }
  }

  return {
    signedAt: null,
    clipboardTexts,
    pdfDownloadUrl,
    docxDownloadUrl,
    emailQueued,
  };
}

async function applyBrowserSideDeliveries(
  res: SignResponse,
  destinations: Destination[]
): Promise<void> {
  // 1. Download URLs fire FIRST — so if the clipboard write fails the
  //    doctor has already gotten the file as a fallback. When both PDF
  //    and DOCX are selected we gap them: Chrome drops the second
  //    programmatic download if two anchors click inside the same tick.
  if (res.pdfDownloadUrl) triggerDownload(res.pdfDownloadUrl, 'pdf');
  if (res.docxDownloadUrl) {
    if (res.pdfDownloadUrl) {
      await new Promise((r) => setTimeout(r, 600));
    }
    triggerDownload(res.docxDownloadUrl, 'docx');
  }

  // 2. Clipboard writes — navigator.clipboard only holds ONE payload
  //    at a time. If the user picked multiple clipboard formats, the
  //    last one selected wins automatically, and we toast offering the
  //    others via the dedicated "Copy other format" buttons on the
  //    signed-state page.
  //
  //    writeText() can hang indefinitely when the browser decides
  //    user-activation has expired — wrap in a 3s timeout so a silent
  //    hang can't block the rest of the deliveries (email toast below,
  //    and more importantly, the calling promise's completion).
  const clipboardChoices = destinations.filter(
    (d) => d.startsWith('clipboard_')
  ) as Array<Extract<Destination, `clipboard_${string}`>>;
  if (clipboardChoices.length > 0 && res.clipboardTexts) {
    const lastKey = clipboardChoices[clipboardChoices.length - 1];
    const text = res.clipboardTexts[lastKey];
    if (text) {
      try {
        await Promise.race([
          navigator.clipboard.writeText(text),
          new Promise<never>((_, reject) =>
            setTimeout(() => reject(new Error('clipboard-timeout')), 3_000)
          ),
        ]);
      } catch {
        toast.error('Copy blocked', {
          description:
            'Your browser blocked clipboard access. Re-open the export modal and try again.',
        });
      }
    }
  }

  // 3. Email — just a toast confirmation.
  if (res.emailQueued) {
    // Resend doesn't guarantee inbox delivery, but it guarantees
    // accepted-for-delivery at this point.
    toast.success('Email sent');
  }
}

function triggerDownload(href: string, kind: 'pdf' | 'docx') {
  const a = document.createElement('a');
  a.href = href;
  a.rel = 'noopener';
  // Setting `download` tells the browser "this is a download, not a
  // navigation", so even if the server's Content-Disposition is
  // missed (proxy strip, browser quirk) the current tab doesn't
  // navigate away from the visit page mid-sign. Empty string lets
  // the server's filename win via Content-Disposition.
  a.download = '';
  // Hint for tooling/accessibility; the browser doesn't strictly need
  // it but it helps if something along the way inspects the element.
  a.setAttribute('data-download-kind', kind);
  document.body.appendChild(a);
  a.click();
  a.remove();
}
