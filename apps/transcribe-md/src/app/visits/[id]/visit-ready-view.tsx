'use client';

import { useMemo, useState, useTransition } from 'react';
import { useRouter } from 'next/navigation';
import { toast } from 'sonner';
import {
  FileText as FileTextIcon,
  MessageSquare as MessageSquareIcon,
  Layers as LayersIcon,
  Stethoscope,
  Pill,
  Sparkles,
  Download,
  ChevronDown,
} from 'lucide-react';

import { cn } from '@/lib/cn';
import { SoapEditor } from './soap-editor';
import { reassignSpeakerAction } from '@/actions/soap';
import { CodesTab, codesTabHasWarnings } from './codes-tab';
import { RxTab, rxTabWarningLevel } from './rx-tab';
import { ExtrasTab, extrasTabHasFlag } from './extras-tab';
import { CopySectionButton } from './copy-section-button';
import type { VisitExportData } from '@/lib/visit-export';
import {
  sectionSoap,
  sectionCodes,
  sectionRx,
  sectionExtras,
} from '@/lib/ehr-formatters';

// T-M6: six tabs — SOAP, Transcript/Input, Codes, Rx, Extras, Pipeline.
type TabKey = 'soap' | 'transcript' | 'codes' | 'rx' | 'extras' | 'pipeline';

// Keep in sync with Layer 2's role enum. Changing this breaks the
// speaker-reassign dropdown; update both.
const ROLE_OPTIONS: { value: string; label: string }[] = [
  { value: 'doctor', label: 'Doctor' },
  { value: 'patient', label: 'Patient' },
  { value: 'family', label: 'Family' },
  { value: 'other', label: 'Other clinical staff' },
  { value: 'unknown', label: 'Unknown' },
];

export interface Utterance {
  speaker?: number;
  start: number;
  end: number;
  transcript: string;
}

export interface SpeakerInfo {
  role: string;
  confidence: number;
  reasoning: string;
}

export interface VisitReadyViewProps {
  visitId: string;
  /** Determines which "input" tab is shown + whether speaker reassignment
   *  is available. */
  inputMode: string;
  /** The note shown in the SOAP tab — soapFinal when READY, signedSoap
   *  when SIGNED. The caller picks. */
  soapText: string;
  readonly: boolean;
  needsReview: boolean;
  reviewReason: string | null;
  overallQuality: 'high' | 'medium' | 'low' | null;
  /** audio_upload only — full diarized utterance list from Deepgram. */
  utterances: Utterance[];
  /** audio_upload only — per-speaker role assignments from Layer 2. */
  speakerMap: Record<string, SpeakerInfo>;
  /** voice_dictation only — flat transcript of the doctor's dictation. */
  dictationTranscript: string | null;
  /** text_notes only — the raw shorthand the doctor typed. */
  rawTextInput: string | null;
  entities: unknown;
  critique: {
    issues: { severity: string; location: string; description: string; suggested_fix: string }[];
    overall_quality: string;
    safe_to_sign_without_review: boolean;
  } | null;
  /** T-M6 automation-layer outputs. All unknown-typed — the tab
   *  components own their wire-types so the server page doesn't have
   *  to import them. */
  icdCodes: unknown;
  cptCodes: unknown;
  rxDrafts: unknown;
  referrals: unknown;
  patientSummary: string | null;
  confidenceScores: unknown;
  /** Display-only pipeline metadata. */
  durationSec: number | null;
  costCents: number | null;
  processingStartedAt: string | null;
  processingFinishedAt: string | null;
  /** T-M7 — passed into SoapEditor so the Sign & Send modal knows
   *  where the "Email to me" destination points. */
  doctorEmail: string;
  /** T-M9 — whether the "Email to me" checkbox is visible in Sign &
   *  Send. Hidden by default until ops verifies the from-domain on
   *  Resend (RESEND_FROM_VERIFIED=true). */
  emailEnabled: boolean;
  /** T-M20.3 — Pipeline tab is developer/debug UI (raw entities JSON,
   *  wall-time, cost). Hidden from doctors in production; shown when
   *  the server page reads `NEXT_PUBLIC_SHOW_PIPELINE_TAB=true` from
   *  the runtime env. */
  showPipelineTab: boolean;
}

export function VisitReadyView(props: VisitReadyViewProps) {
  const [tab, setTab] = useState<TabKey>('soap');

  // The second tab is labelled "Input" for text_notes, "Transcript" for
  // the other two modes. Everything else renders identically.
  const secondTabLabel =
    props.inputMode === 'text_notes' ? 'Input' : 'Transcript';

  // Extract Layer 7e readability metadata for the Extras-tab chip.
  const cs =
    (props.confidenceScores as Record<
      string,
      { status?: string; metadata?: { flesch_kincaid?: number; flagged?: boolean } }
    > | null) ?? {};
  const fleschKincaid =
    typeof cs.patient_summary?.metadata?.flesch_kincaid === 'number'
      ? cs.patient_summary.metadata.flesch_kincaid
      : null;
  const summaryFlagged = Boolean(cs.patient_summary?.metadata?.flagged);

  // Per-tab warning badges driven by confidenceScores + wire-data.
  const codesWarn = codesTabHasWarnings(props.confidenceScores);
  const rxWarn = rxTabWarningLevel(props.rxDrafts);
  const extrasWarn = extrasTabHasFlag(
    props.confidenceScores,
    Boolean(props.patientSummary)
  );

  // Synthesize the minimum VisitExportData shape the section-copy
  // helpers need. sectionSoap / sectionCodes / sectionRx /
  // sectionExtras don't touch patient header or clinician info, so
  // the placeholder fields below are never read.
  const sectionData = buildSectionData(props);

  return (
    <div className="w-full">
      <Tabs
        tab={tab}
        onChange={setTab}
        secondTabLabel={secondTabLabel}
        showPipelineTab={props.showPipelineTab}
        warnings={{
          codes: codesWarn ? 'any' : null,
          rx: rxWarn,
          extras: extrasWarn ? 'any' : null,
        }}
      />
      <div className="mt-6">
        {tab === 'soap' && (
          <div className="space-y-3">
            <div className="flex justify-end">
              <CopySectionButton
                text={sectionSoap(sectionData)}
                label="Copy SOAP"
                section="SOAP note"
              />
            </div>
            <SoapEditor
              visitId={props.visitId}
              doctorEmail={props.doctorEmail}
              emailEnabled={props.emailEnabled}
              initialText={props.soapText}
              readonly={props.readonly}
              needsReview={props.needsReview}
              reviewReason={props.reviewReason}
              overallQuality={props.overallQuality}
            />
          </div>
        )}
        {tab === 'transcript' &&
          (props.inputMode === 'audio_upload' ? (
            <TranscriptView
              visitId={props.visitId}
              utterances={props.utterances}
              speakerMap={props.speakerMap}
              readonly={props.readonly}
            />
          ) : props.inputMode === 'voice_dictation' ? (
            <DictationTranscriptView
              visitId={props.visitId}
              transcript={props.dictationTranscript}
            />
          ) : (
            <RawTextInputView text={props.rawTextInput} />
          ))}
        {tab === 'codes' && (
          <div className="space-y-3">
            <div className="flex justify-end">
              <CopySectionButton
                text={sectionCodes(sectionData)}
                label="Copy codes"
                section="Codes"
              />
            </div>
            <CodesTab icd={props.icdCodes} cpt={props.cptCodes} />
          </div>
        )}
        {tab === 'rx' && (
          <div className="space-y-3">
            <div className="flex justify-end">
              <CopySectionButton
                text={sectionRx(sectionData)}
                label="Copy Rx"
                section="Prescriptions"
              />
            </div>
            <RxTab rx={props.rxDrafts} />
          </div>
        )}
        {tab === 'extras' && (
          <div className="space-y-3">
            <div className="flex justify-end">
              <CopySectionButton
                text={sectionExtras(sectionData)}
                label="Copy extras"
                section="Referrals + patient summary"
              />
            </div>
            <ExtrasTab
              referrals={props.referrals}
              patientSummary={props.patientSummary}
              fleschKincaid={fleschKincaid}
              flagged={summaryFlagged}
            />
          </div>
        )}
        {props.showPipelineTab && tab === 'pipeline' && (
          <PipelineView
            entities={props.entities}
            critique={props.critique}
            durationSec={props.durationSec}
            costCents={props.costCents}
            processingStartedAt={props.processingStartedAt}
            processingFinishedAt={props.processingFinishedAt}
          />
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Minimal VisitExportData for the section-copy helpers. Placeholder
// fields are never read by sectionSoap/Codes/Rx/Extras; centralising
// this keeps the ehr-formatters module the single source of truth for
// section formatting.
// ---------------------------------------------------------------------------
function buildSectionData(props: VisitReadyViewProps): VisitExportData {
  // Unpack the unknown-typed blob columns the same way the tab
  // components do. The section helpers in ehr-formatters expect the
  // shape VisitExportData defines.
  const cptBlob =
    (props.cptCodes as {
      em?: VisitExportData['em'];
      procedures?: VisitExportData['procedures'];
      modifiers?: VisitExportData['modifiers'];
    } | null) ?? null;
  const rxBlob =
    (props.rxDrafts as {
      prescriptions?: VisitExportData['prescriptions'];
      warnings?: VisitExportData['rxWarnings'];
    } | null) ?? null;
  const icdBlob =
    (props.icdCodes as { codes?: VisitExportData['icdCodes'] } | null) ?? null;
  const refBlob =
    (props.referrals as { referrals?: VisitExportData['referrals'] } | null) ??
    null;

  return {
    visitId: props.visitId,
    patientName: null,
    specialty: '',
    chiefComplaint: null,
    status: 'READY',
    createdAt: new Date(0),
    signedAt: null,
    clinicianName: null,
    clinicianEmail: props.doctorEmail,
    soapText: props.soapText,
    icdCodes: icdBlob?.codes ?? [],
    em: cptBlob?.em ?? null,
    procedures: cptBlob?.procedures ?? [],
    modifiers: cptBlob?.modifiers ?? [],
    prescriptions: rxBlob?.prescriptions ?? [],
    rxWarnings: rxBlob?.warnings ?? [],
    referrals: refBlob?.referrals ?? [],
    patientSummary: props.patientSummary,
  };
}

// ---------------------------------------------------------------------------
// Tabs — simple role=tab buttons, no Radix (3 static options, not worth
// the bundle). Labels collapse to icon-only on mobile.
// ---------------------------------------------------------------------------
interface TabDescriptor {
  key: TabKey;
  label: string;
  icon: React.ReactNode;
  /** When set, Tabs draws a dot badge — red for 'critical', amber for
   *  anything else. */
  warning?: 'critical' | 'any' | null;
}

function Tabs({
  tab,
  onChange,
  secondTabLabel,
  showPipelineTab,
  warnings,
}: {
  tab: TabKey;
  onChange: (t: TabKey) => void;
  secondTabLabel: string;
  showPipelineTab: boolean;
  warnings: {
    codes: 'critical' | 'any' | null;
    rx: 'critical' | 'any' | null;
    extras: 'critical' | 'any' | null;
  };
}) {
  const tabs: TabDescriptor[] = [
    { key: 'soap', label: 'SOAP Note', icon: <FileTextIcon className="h-3.5 w-3.5" aria-hidden /> },
    { key: 'transcript', label: secondTabLabel, icon: <MessageSquareIcon className="h-3.5 w-3.5" aria-hidden /> },
    { key: 'codes', label: 'Codes', icon: <Stethoscope className="h-3.5 w-3.5" aria-hidden />, warning: warnings.codes },
    { key: 'rx', label: 'Rx', icon: <Pill className="h-3.5 w-3.5" aria-hidden />, warning: warnings.rx },
    { key: 'extras', label: 'Extras', icon: <Sparkles className="h-3.5 w-3.5" aria-hidden />, warning: warnings.extras },
    // T-M20.3: Pipeline tab carries developer/debug UI (raw entities
    // JSON, wall-time, cost). Hidden from doctors by default; surfaced
    // only when NEXT_PUBLIC_SHOW_PIPELINE_TAB=true in the server env.
    ...(showPipelineTab
      ? [{ key: 'pipeline' as const, label: 'Pipeline', icon: <LayersIcon className="h-3.5 w-3.5" aria-hidden /> }]
      : []),
  ];
  return (
    <div
      role="tablist"
      className="inline-flex max-w-full flex-wrap gap-0.5 rounded-full border border-border-subtle bg-bg-surface-2/60 p-1"
    >
      {tabs.map((t) => (
        <button
          key={t.key}
          type="button"
          role="tab"
          aria-selected={tab === t.key}
          onClick={() => onChange(t.key)}
          className={cn(
            'relative inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-[12px] font-medium tracking-tight',
            'transition-colors duration-150 ease-[cubic-bezier(0.4,0,0.2,1)]',
            'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 focus-visible:ring-offset-2 focus-visible:ring-offset-bg-base',
            tab === t.key
              ? 'bg-bg-surface-3 text-text-primary shadow-[0_0_0_1px_rgba(139,92,246,0.3)]'
              : 'text-text-tertiary hover:text-text-primary'
          )}
          aria-label={t.label}
        >
          {t.icon}
          <span className="hidden sm:inline">{t.label}</span>
          {t.warning && (
            <span
              aria-hidden
              className={cn(
                'absolute right-1.5 top-1 inline-block h-1.5 w-1.5 rounded-full',
                t.warning === 'critical' ? 'bg-danger' : 'bg-warning'
              )}
            />
          )}
        </button>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Transcript view — role-alternating layout, role reassign dropdown per
// speaker, download-as-txt button.
// ---------------------------------------------------------------------------
function TranscriptView({
  visitId,
  utterances,
  speakerMap,
  readonly,
}: {
  visitId: string;
  utterances: Utterance[];
  speakerMap: Record<string, SpeakerInfo>;
  readonly: boolean;
}) {
  const [pending, startTransition] = useTransition();
  const router = useRouter();

  const speakerIds = useMemo(() => {
    const set = new Set<string>();
    for (const u of utterances) {
      if (typeof u.speaker === 'number') set.add(String(u.speaker));
    }
    return Array.from(set).sort();
  }, [utterances]);

  const reassign = (speakerId: string, role: string) => {
    startTransition(async () => {
      const res = await reassignSpeakerAction(visitId, speakerId, role);
      if (!res.ok) {
        toast.error('Could not reassign speaker', { description: res.error });
        return;
      }
      toast.success('Speaker role updated', {
        description: 'Re-running the SOAP pipeline will pick up the new roles.',
      });
      router.refresh();
    });
  };

  const downloadTxt = () => {
    const lines = utterances.map((u) => {
      const key = typeof u.speaker === 'number' ? String(u.speaker) : 'unknown';
      const role = speakerMap[key]?.role ?? 'unknown';
      const ts = Math.max(0, Math.floor(u.start ?? 0));
      const mm = Math.floor(ts / 60);
      const ss = (ts % 60).toString().padStart(2, '0');
      return `[${role} #${key}, ${mm}:${ss}]: ${u.transcript.trim()}`;
    });
    const blob = new Blob([lines.join('\n')], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `transcript-${visitId}.txt`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex-1 text-[12px] text-text-tertiary">
          {speakerIds.length} speaker{speakerIds.length === 1 ? '' : 's'}, {utterances.length} utterances
        </div>
        <button
          type="button"
          onClick={downloadTxt}
          className="inline-flex items-center gap-1.5 rounded-full border border-border-subtle bg-bg-surface-2/60 px-3 py-1.5 text-[12px] text-text-tertiary hover:border-border-default hover:text-text-secondary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 focus-visible:ring-offset-2 focus-visible:ring-offset-bg-base"
        >
          <Download className="h-3.5 w-3.5" aria-hidden />
          Download .txt
        </button>
      </div>

      {!readonly && speakerIds.length > 0 && (
        <div className="rounded-xl border border-border-subtle bg-bg-surface-1/40 p-4">
          <div className="mb-2 text-[11px] font-medium uppercase tracking-wider text-text-muted">
            Speaker roles
          </div>
          <div className="flex flex-wrap gap-3">
            {speakerIds.map((sid) => {
              const info = speakerMap[sid];
              return (
                <label key={sid} className="flex items-center gap-2 text-[12px] text-text-secondary">
                  <span className="font-medium text-text-primary">Speaker #{sid}</span>
                  <div className="relative">
                    <select
                      disabled={pending}
                      value={info?.role ?? 'unknown'}
                      onChange={(e) => reassign(sid, e.target.value)}
                      className="appearance-none rounded-md border border-border-default bg-bg-surface-2 py-1 pl-2 pr-6 text-[12px] text-text-primary outline-none focus:border-violet-500 focus:ring-2 focus:ring-violet-500/30"
                    >
                      {ROLE_OPTIONS.map((r) => (
                        <option key={r.value} value={r.value}>
                          {r.label}
                        </option>
                      ))}
                    </select>
                    <ChevronDown
                      className="pointer-events-none absolute right-1.5 top-1/2 h-3 w-3 -translate-y-1/2 text-text-muted"
                      aria-hidden
                    />
                  </div>
                  <span className="text-text-muted">
                    · conf {(info?.confidence ?? 0).toFixed(2)}
                  </span>
                </label>
              );
            })}
          </div>
        </div>
      )}

      <div className="space-y-2">
        {utterances.map((u, i) => {
          const key = typeof u.speaker === 'number' ? String(u.speaker) : 'unknown';
          const role = speakerMap[key]?.role ?? 'unknown';
          const isDoctor = role === 'doctor';
          const ts = Math.max(0, Math.floor(u.start ?? 0));
          const mm = Math.floor(ts / 60);
          const ss = (ts % 60).toString().padStart(2, '0');
          return (
            <div
              key={i}
              className={cn(
                'flex gap-3',
                isDoctor ? 'justify-end sm:justify-end' : 'justify-start'
              )}
            >
              <div
                className={cn(
                  'max-w-[85%] rounded-2xl px-4 py-2.5 text-[13px] leading-relaxed',
                  isDoctor
                    ? 'bg-violet-500/15 text-text-primary ring-1 ring-violet-500/30'
                    : 'bg-bg-surface-2 text-text-secondary ring-1 ring-border-subtle'
                )}
              >
                <div className="mb-1 text-[10px] font-medium uppercase tracking-wider text-text-muted">
                  {role} #{key} · {mm}:{ss}
                </div>
                {u.transcript}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Pipeline view — inspection + debug.
// ---------------------------------------------------------------------------
function PipelineView({
  entities,
  critique,
  durationSec,
  costCents,
  processingStartedAt,
  processingFinishedAt,
}: {
  entities: unknown;
  critique: VisitReadyViewProps['critique'];
  durationSec: number | null;
  costCents: number | null;
  processingStartedAt: string | null;
  processingFinishedAt: string | null;
}) {
  const processingMs =
    processingStartedAt && processingFinishedAt
      ? new Date(processingFinishedAt).getTime() -
        new Date(processingStartedAt).getTime()
      : null;

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <Stat
          label="Audio duration"
          value={durationSec ? `${Math.round(durationSec / 60)} min ${durationSec % 60}s` : '—'}
        />
        <Stat
          label="Pipeline wall-time"
          value={processingMs ? `${Math.round(processingMs / 1000)}s` : '—'}
        />
        <Stat
          label="Compute cost"
          value={costCents != null ? `$${(costCents / 100).toFixed(2)}` : '—'}
        />
      </div>

      <CollapsibleSection title="Critique">
        {critique ? (
          <div className="space-y-3">
            <div className="text-[12px] text-text-tertiary">
              Overall quality: <span className="font-medium text-text-primary">{critique.overall_quality}</span>
              {' · '}
              Safe to sign without review:{' '}
              <span className="font-medium text-text-primary">
                {critique.safe_to_sign_without_review ? 'yes' : 'no'}
              </span>
            </div>
            {critique.issues.length === 0 ? (
              <div className="text-[12px] text-text-muted">No issues flagged.</div>
            ) : (
              <ul className="space-y-2">
                {critique.issues.map((i, idx) => (
                  <li
                    key={idx}
                    className="rounded-lg border border-border-subtle bg-bg-surface-1/40 p-3 text-[12px]"
                  >
                    <div className="mb-1 flex items-center gap-2">
                      <span
                        className={cn(
                          'inline-flex items-center rounded-full border px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wider',
                          i.severity === 'critical'
                            ? 'border-danger/40 bg-danger/10 text-danger'
                            : i.severity === 'major'
                              ? 'border-warning/40 bg-warning/10 text-warning'
                              : 'border-border-default bg-bg-surface-2 text-text-tertiary'
                        )}
                      >
                        {i.severity}
                      </span>
                      <span className="text-text-primary">{i.location}</span>
                    </div>
                    <div className="text-text-secondary">{i.description}</div>
                    <div className="mt-1 text-text-muted">
                      Fix: {i.suggested_fix}
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        ) : (
          <div className="text-[12px] text-text-muted">No critique available.</div>
        )}
      </CollapsibleSection>

      <CollapsibleSection title="Extracted entities">
        {entities ? (
          <pre className="overflow-x-auto rounded-lg border border-border-subtle bg-bg-surface-1/40 p-3 font-mono text-[11px] text-text-tertiary">
            {JSON.stringify(entities, null, 2)}
          </pre>
        ) : (
          <div className="text-[12px] text-text-muted">Not available.</div>
        )}
      </CollapsibleSection>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-border-subtle bg-bg-surface-1/40 px-4 py-3">
      <div className="text-[10px] font-medium uppercase tracking-wider text-text-muted">
        {label}
      </div>
      <div className="mt-1 text-[15px] font-medium text-text-primary">{value}</div>
    </div>
  );
}

function CollapsibleSection({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(true);
  return (
    <div className="rounded-xl border border-border-default bg-bg-surface-1/40">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between px-4 py-3 text-left text-[12px] font-medium uppercase tracking-wider text-text-muted hover:text-text-secondary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 focus-visible:ring-offset-2 focus-visible:ring-offset-bg-base"
      >
        {title}
        <ChevronDown
          className={cn('h-3 w-3 transition-transform', open && 'rotate-180')}
          aria-hidden
        />
      </button>
      {open && <div className="border-t border-border-subtle px-4 py-3">{children}</div>}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Dictation transcript view (T-M5) — single-speaker block + audio replay.
// ---------------------------------------------------------------------------
function DictationTranscriptView({
  visitId,
  transcript,
}: {
  visitId: string;
  transcript: string | null;
}) {
  // Audio is fetched from our own route — keeps the object private
  // behind the session cookie rather than handing out a MinIO presign.
  const audioSrc = `/api/visits/${visitId}/dictation/audio`;

  return (
    <div className="space-y-4">
      <div className="rounded-xl border border-border-default bg-bg-surface-1/60 p-3">
        <audio
          src={audioSrc}
          controls
          preload="metadata"
          className="w-full"
          aria-label="Replay dictation"
        />
      </div>

      {transcript ? (
        <div className="rounded-xl border border-border-subtle bg-bg-surface-1/40 p-5 leading-relaxed text-[14px] text-text-secondary whitespace-pre-wrap">
          {transcript}
        </div>
      ) : (
        <div className="rounded-xl border border-border-subtle bg-bg-surface-1/40 p-5 text-[13px] text-text-muted">
          Dictation transcript not available.
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Raw typed input view (T-M5) — text_notes. Monospace block so the
// doctor sees exactly what they typed.
// ---------------------------------------------------------------------------
function RawTextInputView({ text }: { text: string | null }) {
  if (!text) {
    return (
      <div className="rounded-xl border border-border-subtle bg-bg-surface-1/40 p-5 text-[13px] text-text-muted">
        No input text stored.
      </div>
    );
  }
  return (
    <pre className="overflow-x-auto rounded-xl border border-border-default bg-bg-surface-1/60 p-5 font-mono text-[12.5px] leading-relaxed text-text-secondary whitespace-pre-wrap">
      {text}
    </pre>
  );
}
