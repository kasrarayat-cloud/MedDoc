'use client';

// ============================================================================
// SignAndSendModal — Sign & Send / Export-again destination picker
// ----------------------------------------------------------------------------
// Phase 5 — Linear V1 Faithful. Renders inside a `.qm-lin-spotlight`
// scrim with a centered surface-1 panel. Destination groups are
// rows of selectable surface-2 chips with a sage-tint-strong
// active state. The trigger button uses `.qm-lin-btn-primary` for
// the sign path and `.qm-lin-btn` for re-export. Server actions and
// browser delivery semantics are unchanged from Phase 2.
// ============================================================================

import { useCallback, useState, useTransition } from 'react';
import { useRouter } from 'next/navigation';
import * as Dialog from '@radix-ui/react-dialog';
import { Check, Loader2, Lock, Send, ShieldCheck, TrendingUp, X } from 'lucide-react';
import { toast } from 'sonner';

import { cn } from '@/lib/cn';

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

type SignAndSendModalTheme = 'legacy' | 'clinician';

interface SignAndSendModalProps {
  visitId: string;
  doctorEmail: string;
  /** When `signOnSubmit=true`, submitting calls /sign. When false, it
   *  calls the individual export routes directly (used on already-
   *  SIGNED visits so "Export again" doesn't try to re-sign). */
  signOnSubmit: boolean;
  /** T-M9 — whether Email is a selectable destination. When false the
   *  "Email to me" checkbox is hidden entirely and 'email' is stripped
   *  from any submission payload as belt-and-braces. Set from the
   *  server based on RESEND_API_KEY + RESEND_FROM_VERIFIED. */
  emailEnabled: boolean;
  /** The trigger button's label — "Sign & Send" vs "Export again". */
  triggerLabel: string;
  /** Whether the doctor has ALREADY attested upstream (Rounds Gate 3 collects
   *  it). When true this modal renders no attestation control of its own and
   *  simply forwards it — the doctor attests once, not twice. When undefined,
   *  this modal is the place it gets collected, which is what keeps the
   *  non-Rounds paths signable now that the route requires it. */
  attested?: boolean;
  /** Icon shown on the trigger. */
  triggerIcon: React.ReactNode;
  /** Variant of the trigger button — primary for sign, secondary for
   *  re-export. */
  triggerVariant?: 'primary' | 'secondary';
  /** Disable the trigger while parent is saving edits, etc. */
  disabled?: boolean;
  /** Phase 5.2 stub completion — optional controlled-open mode. When
   *  `controlledOpen` is provided, the modal honors it as the source
   *  of truth and ignores its internal state; the `Dialog.Trigger` and
   *  any external opener (e.g. the CodingRail "Confirm <code> · sign"
   *  button calling `onControlledOpenChange(true)`) both flip the
   *  same parent state. When undefined, the modal uses its internal
   *  state (existing behavior — backward compatible). */
  controlledOpen?: boolean;
  onControlledOpenChange?: (open: boolean) => void;
  /** E/M visible-confirm (prod smoke #311) — the UNACKNOWLEDGED
   *  suggestion-caused E/M level change ({from, to} CPT codes — no PHI).
   *  When set (and signOnSubmit), the modal renders a "Documentation
   *  level changed" notice + an explicit confirm control; Sign & Deliver
   *  stays disabled until confirmed, and the confirmation is echoed to
   *  POST /sign as `acknowledgedEmChange`. The server gate is the
   *  enforcement — this is the visible half. Null = nothing to confirm. */
  emPendingChange?: { from: string; to: string } | null;
  /** @deprecated kept for back-compat; Linear V1 is single-theme. */
  theme?: SignAndSendModalTheme;
}

export function SignAndSendModal(props: SignAndSendModalProps) {
  const router = useRouter();
  // Phase 5.2 stub completion — controlled-open mode lets the parent
  // (soap-editor.tsx) lift state and open the modal from another
  // button (CodingRail's "Confirm <code> · sign"). When the controlled
  // props are absent, fall back to internal state (existing behavior).
  const isControlled = props.controlledOpen !== undefined;
  const [internalOpen, setInternalOpen] = useState(false);
  const open = isControlled ? props.controlledOpen! : internalOpen;
  const setOpen = useCallback(
    (next: boolean) => {
      if (isControlled) {
        props.onControlledOpenChange?.(next);
      } else {
        setInternalOpen(next);
      }
    },
    [isControlled, props]
  );
  const [selected, setSelected] = useState<Set<Destination>>(
    () => new Set(['clipboard_epic', 'pdf'])
  );
  const [pending, startTransition] = useTransition();
  // Selections persist across open/close so a doctor who always picks
  // the same two targets doesn't re-check them every time.

  // E/M visible-confirm — the explicit checkbox. Deliberately NOT
  // persisted across open/close (unlike destination selections): each
  // open of the sign dialog requires a fresh, conscious confirmation.
  // Reset uses the adjust-state-during-render pattern (not an effect)
  // so the checkbox is already cleared in the same render that closes.
  const emChangeRequired =
    props.signOnSubmit && props.emPendingChange != null;
  const [emChangeConfirmed, setEmChangeConfirmed] = useState(false);
  // Collected HERE only when nobody upstream did. `POST /sign` refuses without
  // it (400 ATTESTATION_REQUIRED), so this is the UI half of a real gate rather
  // than a courtesy checkbox.
  const [modalAttested, setModalAttested] = useState(false);
  const attestationNeededHere = props.signOnSubmit && props.attested !== true;
  const attestationSatisfied = props.attested === true || modalAttested;
  const [prevOpen, setPrevOpen] = useState(open);
  if (prevOpen !== open) {
    setPrevOpen(open);
    if (!open) setEmChangeConfirmed(false);
  }

  const toggle = useCallback((key: Destination) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }, []);

  const submit = useCallback(() => {
    // Strip 'email' defensively — if emailEnabled flips off between
    // renders, or a stale entry somehow lingers in `selected`, don't
    // send it to the server.
    const destinations = Array.from(selected).filter(
      (d) => d !== 'email' || props.emailEnabled
    );
    if (destinations.length === 0) {
      toast.error('Pick at least one destination.');
      return;
    }
    // E/M visible-confirm: belt to the disabled button — never submit a
    // sign while an unconfirmed level change is showing. The server gate
    // would reject it anyway (fail-closed); this just keeps the UX clean.
    if (emChangeRequired && !emChangeConfirmed) {
      toast.error('Confirm the documentation level change before signing.');
      return;
    }
    if (props.signOnSubmit && !attestationSatisfied) {
      toast.error('Attest to this note before signing.');
      return;
    }
    startTransition(async () => {
      try {
        // Step 1: the server-side work (sign + collect clipboard text /
        // URLs / email-queued status). This is the ONLY thing awaited
        // inside the transition — once it returns, the visit is signed
        // in the DB and we know what to hand to the browser.
        const payload = props.signOnSubmit
          ? await fetchSignAndDeliver(
              props.visitId,
              destinations,
              emChangeRequired && emChangeConfirmed
                ? (props.emPendingChange ?? undefined)
                : undefined,
              attestationSatisfied
            )
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
  }, [
    props.visitId,
    props.signOnSubmit,
    props.emailEnabled,
    props.emPendingChange,
    emChangeRequired,
    emChangeConfirmed,
    // ⚠️ WITHOUT THIS THE CALLBACK CAPTURES `false` FOREVER, and the symptom is
    // a button that looks ready and does nothing. `disabled` reads the fresh
    // value from JSX on every render, so the control ENABLES the moment the
    // doctor ticks the box — while `submit`, memoised without this dep, still
    // holds the value from first render and returns at the attestation guard.
    // No request, no audit row, no toast the test could see: three specs failed
    // 10s later on "waiting for event download".
    // A real doctor would have ticked the box, seen the button light up,
    // clicked, and had nothing happen.
    attestationSatisfied,
    router,
    selected,
  ]);

  const triggerVariant = props.triggerVariant ?? 'primary';

  return (
    <Dialog.Root open={open} onOpenChange={setOpen}>
      <Dialog.Trigger asChild>
        <button
          type="button"
          className={
            triggerVariant === 'primary' ? 'qm-lin-btn-primary' : 'qm-lin-btn'
          }
          disabled={props.disabled}
          style={{ padding: '8px 14px', height: 32 }}
        >
          {props.triggerIcon}
          {props.triggerLabel}
        </button>
      </Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Overlay
          className={cn(
            'qm-lin-spotlight',
            'data-[state=open]:animate-in data-[state=open]:fade-in-0',
            'data-[state=closed]:animate-out data-[state=closed]:fade-out-0'
          )}
        />
        <Dialog.Content
          aria-describedby={undefined}
          className={cn(
            'qm-lin-spotlight-panel',
            'fixed left-1/2 top-[12vh] z-[201] -translate-x-1/2',
            // ⚠️ BOUNDED + FLEX COLUMN, so the footer can be PINNED.
            // The dialog used to have no height bound at all and the body a
            // fixed `max-h-[60vh]`. Total height was therefore
            // 12vh + header + 60vh + gates + action row, which overflows the
            // viewport — and the overflow lands on the BOTTOM, i.e. on the
            // control that signs. Adding a required attestation above the
            // action row pushed "Sign & Deliver" off-screen entirely at 720px
            // and three signing specs failed on a button they could not reach.
            // Bounded here, body flexes, footer never scrolls away.
            'flex max-h-[76vh] flex-col',
            // ⚠️ THE BOUNDED FLEX COLUMN IS LOAD-BEARING, NOT DECORATION, and
            // `29-sign-modal-geometry.spec.ts` is why: it asserts the submit's
            // bottom edge is inside a 640px viewport with NO scrolling. The T4
            // skin adds ground, border and radius; it must not touch the
            // height bound or the column.
            'qm-t4-card',
            'focus:outline-none qm-lin-blur-in',
            'data-[state=closed]:animate-out data-[state=closed]:fade-out-0',
            'data-[state=closed]:zoom-out-95'
          )}
          /* width now comes from `.qm-t4-card` — the frames' 496. */
        >
          <div className="qm-t4-head flex flex-none items-start justify-between gap-4">
            <div>
              {/* ⚠️ THE POST-SIGN BADGE — `sign-deliver-post`'s 16×16
                  shield-check + "DOCUMENT SIGNED". The rows do NOT become
                  actions in this change; that shift is its own diff, per
                  ruling #188(4). */}
              {!props.signOnSubmit && (
                <div className="qm-t4-badge" data-testid="t4-signed-badge">
                  <ShieldCheck className="h-4 w-4" strokeWidth={2} aria-hidden />
                  Document signed
                </div>
              )}
              <Dialog.Title className="qm-t4-title">
                {/* ⚠️ THE PRE-SIGN TITLE STAYS "Sign and deliver your note",
                    AND THAT IS A DELIBERATE DEPARTURE FROM THE FRAMES, which
                    title the card "Sign & deliver".

                    `29-sign-modal-geometry.spec.ts:123-130` matches this
                    heading with `exact: true` — no substring tolerance — and
                    that spec exists because a required attestation once pushed
                    the submit off-screen at 720px. Changing the copy here
                    would red a geometry gate over a word, on the surface that
                    signs a clinical record.

                    The frames' title is a NAME for the card, not a claim about
                    behaviour, so keeping the tested string costs nothing a
                    doctor can see. Recorded in the T4 spec as a departure
                    rather than taken silently. */}
                {props.signOnSubmit
                  ? 'Sign and deliver your note'
                  : 'Export signed note'}
              </Dialog.Title>
              <p className="qm-t4-sub">
                {props.signOnSubmit
                  ? 'Confirm destination settings and sign off this progress note.'
                  : 'The progress note has been successfully locked. Deliver to required destinations.'}
              </p>
            </div>
            <Dialog.Close asChild>
              <button
                type="button"
                aria-label="Close"
                className="rounded-md p-1 text-linear-text-3 transition-colors hover:bg-linear-surface-2 hover:text-linear-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-linear-sage"
              >
                <X className="h-4 w-4" aria-hidden />
              </button>
            </Dialog.Close>
          </div>

          <div
            className="min-h-0 flex-1 overflow-y-auto"
            style={{ padding: '4px 24px 8px' }}
          >
            <Group
              title="Copy to clipboard"
              hint="Paste the formatted note into your EHR's note field."
              groupKey="clipboard"
              items={DESTINATIONS.filter((d) => d.group === 'clipboard')}
              selected={selected}
              onToggle={toggle}
            />
            <Group
              title="Download"
              hint="Save a PDF for records or a DOCX to edit in Word."
              groupKey="download"
              items={DESTINATIONS.filter((d) => d.group === 'download')}
              selected={selected}
              onToggle={toggle}
            />
            {props.emailEnabled && (
              <Group
                title="Email"
                hint={`Send a PDF to ${props.doctorEmail} for your records. Don't use for patient communication.`}
                groupKey="email"
              items={DESTINATIONS.filter((d) => d.group === 'email')}
                selected={selected}
                onToggle={toggle}
              />
            )}
          </div>

          {/* E/M visible-confirm (prod smoke #311) — an adopted/dismissed
              AI suggestion changed the computed E/M level; signing requires
              an explicit confirmation. Amber review-surface recipe (same
              color-mix family as the suggestions lane / review banner).
              Rendered OUTSIDE the scroll area so it can never scroll out
              of sight behind a long destination list. */}
          {attestationNeededHere && (
            <div
              role="group"
              aria-label="Attestation required"
              data-testid="sign-attestation"
              className="flex-none rounded-lg border"
              style={{
                margin: '4px 24px 12px',
                padding: '10px 12px',
                borderColor: 'var(--color-linear-border)',
                background: 'var(--color-linear-surface-2)',
              }}
            >
              <p
                className="mb-0 text-[12px] leading-relaxed"
                style={{ color: 'var(--color-linear-text-3)' }}
              >
                Signing is an attestation. Confirm that you have reviewed this
                note and that it reflects the encounter.
              </p>
              <hr className="qm-t4-divider" />
              {/* The frames draw the attestation as a checkbox row, not a
                  bordered card — the same row unit as a destination, so it
                  reads as one more thing you tick. `sign-attestation-toggle`
                  and `aria-pressed` are unchanged: the geometry gate and the
                  accessible state both key on them. */}
              <button
                type="button"
                onClick={() => setModalAttested((a) => !a)}
                aria-pressed={modalAttested}
                data-checked={modalAttested ? 'true' : 'false'}
                data-testid="sign-attestation-toggle"
                className="qm-t4-row"
              >
                <span aria-hidden className="qm-t4-box">
                  {modalAttested && (
                    <Check className="h-3 w-3" strokeWidth={3} aria-hidden />
                  )}
                </span>
                <span className="qm-t4-attest-text">
                  I have reviewed this note and attest to it
                </span>
              </button>
            </div>
          )}

          {emChangeRequired && props.emPendingChange && (
            <div
              role="group"
              aria-label="Documentation level changed — confirmation required"
              data-testid="em-change-confirm"
              className="flex-none rounded-lg border"
              style={{
                margin: '4px 24px 12px',
                padding: '10px 12px',
                borderColor:
                  'color-mix(in srgb, var(--color-linear-amber) 35%, transparent)',
                background:
                  'color-mix(in srgb, var(--color-linear-amber) 8%, transparent)',
              }}
            >
              <div className="flex items-center gap-2">
                <TrendingUp
                  className="h-3.5 w-3.5 flex-none"
                  aria-hidden
                  style={{ color: 'var(--color-linear-amber)' }}
                />
                <span
                  className="text-[13px] font-medium"
                  style={{ color: 'var(--color-linear-amber)' }}
                >
                  Documentation level changed:{' '}
                  <span style={{ fontFamily: 'var(--font-mono)' }}>
                    {props.emPendingChange.from} → {props.emPendingChange.to}
                  </span>
                </span>
              </div>
              <p
                className="mb-0 mt-1.5 text-[12px] leading-relaxed"
                style={{ color: 'var(--color-linear-text-3)' }}
              >
                An AI-suggestion you adopted or dismissed changed the
                suggested E/M level. Signing requires confirming the
                updated level.
              </p>
              <button
                type="button"
                onClick={() => setEmChangeConfirmed((c) => !c)}
                aria-pressed={emChangeConfirmed}
                data-testid="em-change-confirm-toggle"
                className="mt-2 flex w-full items-center gap-3 rounded-md border px-3 py-2 text-left transition-colors duration-150 ease-out focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-linear-sage focus-visible:ring-offset-2 focus-visible:ring-offset-linear-bg"
                style={{
                  borderColor: emChangeConfirmed
                    ? 'color-mix(in srgb, var(--color-linear-amber) 45%, transparent)'
                    : 'var(--color-linear-border)',
                  background: emChangeConfirmed
                    ? 'color-mix(in srgb, var(--color-linear-amber) 14%, transparent)'
                    : 'var(--color-linear-surface-2)',
                  color: emChangeConfirmed
                    ? 'var(--color-linear-text)'
                    : 'var(--color-linear-text-2)',
                }}
              >
                <span
                  aria-hidden
                  className="flex h-4 w-4 flex-none items-center justify-center rounded-[4px] border"
                  style={{
                    borderColor: emChangeConfirmed
                      ? 'var(--color-linear-amber)'
                      : 'var(--color-linear-border-strong)',
                    background: emChangeConfirmed
                      ? 'var(--color-linear-amber)'
                      : 'transparent',
                    color: '#16120a',
                  }}
                >
                  {emChangeConfirmed && (
                    <Check className="h-3 w-3" strokeWidth={3} aria-hidden />
                  )}
                </span>
                <span className="flex-1 text-[13px]">
                  I&apos;ve reviewed the change and confirm{' '}
                  <span style={{ fontFamily: 'var(--font-mono)' }}>
                    {props.emPendingChange.to}
                  </span>{' '}
                  as the documentation level
                </span>
              </button>
            </div>
          )}

          <div
            className="flex flex-none items-center justify-between gap-3"
            style={{
              borderTop: '1px solid var(--color-linear-hairline)',
              background: 'var(--color-linear-surface-2)',
              padding: '12px 24px',
            }}
          >
            {/* ⚠️ THE DELIVERY SUMMARY REFLECTS THE CHECKED SET — the frames
                are explicit that it mirrors the ticked rows, so it is COMPUTED
                and never written down. A summary that can disagree with the
                checkboxes above it is worse than no summary. */}
            <p className="qm-t4-summary" data-testid="t4-delivery-summary">
              {selected.size === 0
                ? 'No destinations selected.'
                : `Delivery summary: ${DESTINATIONS.filter((d) => selected.has(d.key))
                    .map((d) => d.label)
                    .join(' • ')}`}
            </p>
            <div className="qm-t4-actions">
              <Dialog.Close asChild>
                <button type="button" className="qm-t4-btn qm-t4-btn-cancel">
                  Cancel
                </button>
              </Dialog.Close>
              <button
                type="button"
                className="qm-t4-btn qm-t4-btn-primary"
                data-testid="t4-submit"
                onClick={submit}
                // E/M visible-confirm: the sign CTA stays disabled until
                // the doctor explicitly confirms a recorded level change.
                // The server gate rejects unconfirmed signs regardless.
                disabled={
                  pending ||
                  (emChangeRequired && !emChangeConfirmed) ||
                  (props.signOnSubmit && !attestationSatisfied)
                }
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
              </button>
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
  groupKey,
  items,
  selected,
  onToggle,
}: {
  title: string;
  hint: string;
  groupKey: string;
  items: { key: Destination; label: string }[];
  selected: Set<Destination>;
  onToggle: (k: Destination) => void;
}) {
  return (
    <div className="qm-t4-group-wrap">
      <div className="qm-t4-section-label">{title}</div>
      {/* ⚠️ THE CAPTION IS A SAFETY SURFACE — RULING #188(2).
          The email group's reads "Don't use for patient communication." The
          frames' flat DELIVER TO list has no slot for a per-group line, and
          building them literally would have deleted the one instruction that
          stops a doctor mailing a note to a patient.
          A LITERAL FRAME THAT DELETES A SAFETY INSTRUCTION IS NOT THE SPEC. */}
      <p className="qm-t4-caption" data-testid={`t4-caption-${groupKey}`}>
        {hint}
      </p>
      {/* ⚠️ ONE ROW PER DESTINATION — ruling #188(1). The frames draw four rows
          and the product has eight, five of them EHR clipboard formats. The
          frames' ROW is the design; the four drawn are examples. Collapsing
          them would mean a doctor on Epic could not pick the Epic format. */}
      <div className="qm-t4-group" data-testid={`t4-group-${groupKey}`}>
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
    // ⚠️ `aria-pressed` STAYS. It is what makes this a checkable control to a
    // screen reader, and the frames' visual checkbox is `aria-hidden` — the
    // state lives on the button, not on the decoration.
    <button
      type="button"
      onClick={onToggle}
      aria-pressed={checked}
      data-checked={checked ? 'true' : 'false'}
      className="qm-t4-row"
    >
      <span aria-hidden className="qm-t4-box">
        {checked && <Check className="h-3 w-3" strokeWidth={3} aria-hidden />}
      </span>
      <span className="qm-t4-row-label">{label}</span>
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
  destinations: Destination[],
  /** E/M visible-confirm — the doctor's explicit acknowledgement of a
   *  suggestion-caused level change, echoing the recorded {from, to}.
   *  Omitted when there is nothing to confirm. The server rejects the
   *  sign (400, EM_CHANGE_UNACKNOWLEDGED) if a recorded change exists
   *  and this is absent or stale. */
  acknowledgedEmChange?: { from: string; to: string },
  /** The doctor's attestation. Required by the route since 2026-08-02 —
   *  omitted only by a caller that has not collected it, which the server then
   *  refuses (400 ATTESTATION_REQUIRED) rather than signing. */
  attested?: boolean
): Promise<SignResponse> {
  const res = await fetch(`/api/visits/${visitId}/sign`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      destinations,
      ...(acknowledgedEmChange ? { acknowledgedEmChange } : {}),
      ...(attested ? { attestation: { acknowledged: true as const } } : {}),
    }),
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
