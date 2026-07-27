'use client';

// ============================================================================
// UX simplification pack (A) — staged processing + the ONE confirm card.
// ----------------------------------------------------------------------------
// Replaces "spinner → full review editor" with
//   staged processing → one confirm card → done.
//
// HONESTY CONTRACT (the reason there is no progress bar):
// every stage below corresponds to a REAL awaited step, and a stage only
// advances when that step has actually completed. Nothing is timed, nothing is
// interpolated, and no percentage is invented:
//
//   read     ← extractNoteFileAction resolved      (file path only)
//   sections ← parseNoteTemplateAction resolved    (count comes from the result)
//   fields   ← header fields read off that SAME result (no extra call)
//   sample   ← previewNoteTemplateAction resolved  (the filled sample below)
//
// The motion is a shimmer on the IN-FLIGHT row — it communicates "still
// working", not "this much is done". If a step is slow, the row keeps
// shimmering; it never creeps toward a fake 90%.
//
// SKIN/FLOW-ONLY: this component calls existing server actions only. The parse
// backend, its PHI gate, the verifier and every sign gate are untouched.
// ============================================================================

import { useEffect, useRef, useState } from 'react';
import { Check, FileText, Loader2, ShieldAlert, Sparkles } from 'lucide-react';

import { NativeDocumentPreview } from '@/components/native-preview/native-document-preview';
import type {
  NativePreviewError,
  NativePreviewKind,
} from '@/actions/preview-native-document';

const sans = 'var(--font-sans)';
const mono = 'var(--font-mono)';

export type StageKey = 'read' | 'sections' | 'fields' | 'sample';
export type StageState = 'pending' | 'active' | 'done' | 'skipped';

export interface StageModel {
  key: StageKey;
  label: string;
  /** Filled in once the step completes — e.g. "12 sections". Never a guess. */
  detail?: string | null;
  state: StageState;
}

/** The ordered stage list. `fromFile` drops the read step for the paste path,
 *  where there is genuinely no file to read. */
export function initialStages(fromFile: boolean): StageModel[] {
  return [
    { key: 'read', label: 'Reading your form', state: fromFile ? 'active' : 'skipped' },
    { key: 'sections', label: 'Finding the sections', state: fromFile ? 'pending' : 'active' },
    { key: 'fields', label: 'Capturing the header fields', state: 'pending' },
    { key: 'sample', label: 'Filling in a sample', state: 'pending' },
  ];
}

export function advance(
  stages: StageModel[],
  key: StageKey,
  next: StageState,
  detail?: string | null
): StageModel[] {
  const i = stages.findIndex((s) => s.key === key);
  if (i < 0) return stages;
  const out = stages.map((s, idx) =>
    idx === i ? { ...s, state: next, detail: detail ?? s.detail } : s
  );
  // Completing a step lights the next real one. Skipped rows never light.
  if (next === 'done') {
    for (let j = i + 1; j < out.length; j += 1) {
      if (out[j].state === 'skipped') continue;
      if (out[j].state === 'pending') out[j] = { ...out[j], state: 'active' };
      break;
    }
  }
  return out;
}

// ──────────────────────────────────────────────────────────────────────
// Staged processing
// ──────────────────────────────────────────────────────────────────────

export function ProcessingStages({ stages }: { stages: StageModel[] }) {
  const visible = stages.filter((s) => s.state !== 'skipped');
  const liveRow = visible.find((s) => s.state === 'active');

  return (
    <div className="qm-ux-proc" role="status" aria-live="polite">
      {/* One honest sentence for screen readers — mirrors the visible rows. */}
      <span className="sr-only">
        {liveRow ? `${liveRow.label}…` : 'Reading your form'}
      </span>

      <div className="qm-ux-proc-mark" aria-hidden>
        <FileText className="h-5 w-5" />
      </div>

      <h3 className="qm-ux-proc-title">Reading your form</h3>
      <p className="qm-ux-proc-sub">
        This takes a few seconds. Nothing is saved until you confirm.
      </p>

      <ol className="qm-ux-stages">
        {visible.map((s, i) => (
          <li
            key={s.key}
            className={`qm-ux-stage is-${s.state}`}
            style={{ ['--i' as string]: String(i) }}
          >
            <span className="qm-ux-stage-icon" aria-hidden>
              {s.state === 'done' ? (
                <Check className="h-3.5 w-3.5" />
              ) : s.state === 'active' ? (
                <Loader2 className="h-3.5 w-3.5 qm-ux-spin" />
              ) : (
                <span className="qm-ux-stage-dot" />
              )}
            </span>
            <span className="qm-ux-stage-label">{s.label}</span>
            {s.detail && <span className="qm-ux-stage-detail">{s.detail}</span>}
          </li>
        ))}
      </ol>
    </div>
  );
}

// ──────────────────────────────────────────────────────────────────────
// The ONE confirm card
// ──────────────────────────────────────────────────────────────────────

export interface ConfirmCardProps {
  name: string;
  sectionCount: number;
  headerFieldCount: number;
  /** THE DOCTOR'S OWN PAGE (flag NEXT_PUBLIC_DOC_PREVIEW). Null while still
   *  rendering. `sampleFailed` means we could not draw it — never a substitute
   *  mock in our own fonts. */
  sample: {
    kind: NativePreviewKind | null;
    data: string | null;
    reason: NativePreviewError | null;
  } | null;
  /** Flag OFF: the previous markdown sample, byte-identical. */
  sampleMarkdown: string | null;
  docPreview: boolean;
  sampleFailed: boolean;
  /** True when the uploaded file was a flat PDF we can also certify for
   *  native export — the confirm then doubles as the preview-once. */
  nativeCandidate: boolean;
  busy: boolean;
  /** Non-null after a confirm attempt where activation succeeded but native
   *  certification did not. Never silent — shown with a retry. */
  certError: string | null;
  /** Non-null when the confirm itself was REJECTED (nothing was activated).
   *  Rendered in the card, not just toasted: a toast auto-dismisses after 4s,
   *  and a failure that leaves no trace is indistinguishable from a dead
   *  button — the exact misreading this pack exists to stop repeating. */
  saveError: string | null;
  onConfirm: () => void;
  onRetryCert: () => void;
  onAdvanced: () => void;
  onCancel: () => void;
}

export function ConfirmCard(props: ConfirmCardProps) {
  return (
    <div className="qm-ux-confirm">
      <header className="qm-ux-confirm-head">
        <div className="qm-ux-confirm-eyebrow" style={{ fontFamily: mono }}>
          YOUR FORMAT
        </div>
        <h2 className="qm-ux-confirm-title">{props.name || 'Your note format'}</h2>
        <p className="qm-ux-confirm-meta">
          {props.sectionCount} section{props.sectionCount === 1 ? '' : 's'}
          {props.headerFieldCount > 0 && (
            <>
              {' · '}
              {props.headerFieldCount} header field
              {props.headerFieldCount === 1 ? '' : 's'}
            </>
          )}
          {props.nativeCandidate && (
            <>
              {' · '}
              <span style={{ color: 'var(--color-linear-sage)' }}>
                your own PDF page
              </span>
            </>
          )}
        </p>
      </header>

      {/* THE DOCTOR'S OWN PAGE. A flat PDF is shown FILLED — sample answers
          sitting in their actual blanks, which is the whole question they came
          to ask. A .docx is shown as the form itself; we can honestly render
          the page at this point, not the fill, and we say which. What used to
          be here was markdown in our fonts: it answered "did we read your
          sections", which is our question, not theirs. */}
      <div className="qm-ux-sample-wrap">
        <div className="qm-ux-sample-label" style={{ fontFamily: mono }}>
          {!props.docPreview
            ? 'SAMPLE — SYNTHETIC PATIENT, NOT A REAL VISIT'
            : props.nativeCandidate
              ? 'YOUR FORM — SAMPLE ANSWERS, NOT A REAL VISIT'
              : 'YOUR FORM'}
        </div>
        <div
          className={props.docPreview ? undefined : 'qm-ux-sample'}
          data-testid="confirm-filled-sample"
        >
          {(props.docPreview ? props.sample : props.sampleMarkdown) === null ? (
            <div className="qm-ux-sample-loading">
              <Loader2 className="h-4 w-4 qm-ux-spin" aria-hidden />
              <span>{props.docPreview ? 'Opening your form…' : 'Filling in a sample…'}</span>
            </div>
          ) : props.docPreview && props.sampleFailed ? (
            // Render through the same component so the NAMED reason reaches the
            // doctor. Dropping it here made a 1 MB overflow, a dead MinIO and a
            // failed fill all read as the same shrug.
            <NativeDocumentPreview
              kind={props.sample?.kind ?? null}
              data={props.sample?.data ?? null}
              reason={props.sample?.reason ?? 'sample_unavailable'}
              label="your note format"
            />
          ) : props.sampleFailed ? (
            <p className="qm-ux-sample-fallback">
              {props.docPreview ? (
                <>
                  We couldn&rsquo;t open your form just now — it was still read
                  correctly. You can confirm and check a real visit, or open the
                  advanced editor to review it section by section.
                </>
              ) : (
                <>
                  We couldn&rsquo;t render a sample just now — your format was
                  still read correctly. You can confirm and check a real visit,
                  or open the advanced editor to review it section by section.
                </>
              )}
            </p>
          ) : props.docPreview && props.sample ? (
            <NativeDocumentPreview
              kind={props.sample.kind}
              data={props.sample.data}
              reason={props.sample.reason}
              label="your note format"
              caption={
                props.nativeCandidate
                  ? 'Sample answers, in your own blanks. A real visit fills these from what you dictate.'
                  : 'Your form, as you uploaded it. The empty fields are where your answers go on a real visit.'
              }
            />
          ) : (
            <pre className="qm-ux-sample-pre">{props.sampleMarkdown}</pre>
          )}
        </div>
      </div>

      {props.saveError && (
        <div className="qm-ux-cert-warn" role="alert" data-testid="confirm-save-error">
          <ShieldAlert className="h-4 w-4 flex-none" aria-hidden />
          <div>
            <strong>We couldn&rsquo;t use this format</strong> — {props.saveError}
            <br />
            <span className="qm-ux-cert-note">
              Nothing was changed. Open the advanced editor to adjust it, or cancel.
            </span>
          </div>
        </div>
      )}

      {props.certError && (
        <div className="qm-ux-cert-warn" role="alert">
          <ShieldAlert className="h-4 w-4 flex-none" aria-hidden />
          <div>
            <strong>Your format is active</strong> — but setting it up to export on
            your own PDF page didn&rsquo;t finish: {props.certError}
            <br />
            <span className="qm-ux-cert-note">
              Exports will use the QuillMD-styled layout until this succeeds.
            </span>
            <button
              type="button"
              className="qm-ux-cert-retry qm-tap-44"
              onClick={props.onRetryCert}
              disabled={props.busy}
            >
              Try that again
            </button>
          </div>
        </div>
      )}

      <div className="qm-ux-confirm-actions">
        <button
          type="button"
          className="qm-ux-primary qm-tap-44"
          onClick={props.onConfirm}
          disabled={props.busy}
          data-testid="confirm-use-format"
        >
          {props.busy ? (
            <>
              <Loader2 className="h-4 w-4 qm-ux-spin" aria-hidden /> Setting it up…
            </>
          ) : (
            <>
              <Sparkles className="h-4 w-4" aria-hidden /> Looks right — use this format
            </>
          )}
        </button>
        <button
          type="button"
          className="qm-ux-quiet qm-tap-44"
          onClick={props.onAdvanced}
          disabled={props.busy}
          data-testid="confirm-something-off"
        >
          Something&rsquo;s off
        </button>
        <button
          type="button"
          className="qm-ux-quiet qm-tap-44"
          onClick={props.onCancel}
          disabled={props.busy}
        >
          Cancel
        </button>
      </div>

      <p className="qm-ux-confirm-foot">
        Confirming activates this format for matching visits, sets it up for export
        on your own page, and turns on form-only export. You can change any of it in
        Settings.
      </p>
    </div>
  );
}

/** Focus the confirm card's primary action when it mounts, so the keyboard path
 *  after a long processing wait lands somewhere useful instead of at <body>. */
export function useAutoFocus<T extends HTMLElement>(active: boolean) {
  const ref = useRef<T | null>(null);
  useEffect(() => {
    if (active) ref.current?.focus();
  }, [active]);
  return ref;
}

export function useStages(fromFile: boolean) {
  const [stages, setStages] = useState<StageModel[]>(() => initialStages(fromFile));
  const reset = (nextFromFile: boolean) => setStages(initialStages(nextFromFile));
  const step = (key: StageKey, state: StageState, detail?: string | null) =>
    setStages((prev) => advance(prev, key, state, detail));
  return { stages, step, reset };
}
