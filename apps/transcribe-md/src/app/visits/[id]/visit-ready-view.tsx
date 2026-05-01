'use client';

// ============================================================================
// VisitReadyView — visit-detail body for READY/SIGNED states.
// ----------------------------------------------------------------------------
// Phase 5 — Linear V1 Faithful. A horizontal Linear-style underlined
// tab bar drives the SOAP / Transcript / Codes / Rx / Extras /
// Pipeline panels. Surfaces are hairline-bordered surface-1 cards on
// the dark canvas; transcript turns render in floating doctor/patient
// bubbles tinted sage and surface-2 respectively. The `theme` prop
// is preserved as a no-op for caller back-compat.
// ============================================================================

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
  Lock,
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
import { formatLocalDateTime } from '@/lib/format-time';

type VisitReadyViewTheme = 'legacy' | 'clinician';

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

const SECTION_LABEL =
  'mb-2 text-[10px] font-medium uppercase tracking-[0.07em] font-mono text-linear-text-3';

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
  /** T-M6 automation-layer outputs. */
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
   *  Send. */
  emailEnabled: boolean;
  /** T-M20.3 — Pipeline tab is developer/debug UI. */
  showPipelineTab: boolean;
  /** Batch H — ISO 8601 UTC moment the doctor signed the note. */
  signedAt: string | null;
  /** Batch H — display name of the signer. */
  signedByName: string | null;
  /** @deprecated kept for back-compat; Linear V1 is single-theme. */
  theme?: VisitReadyViewTheme;
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
            {/* Batch H — when signedAt is set, surface a calm
                "Signed at … by …" card immediately above the SOAP
                editor. The Sign & Send CTA is hidden inside
                <SoapEditor> via the same signedAt gate. */}
            {props.signedAt && (
              <SignedStateCard
                signedAt={props.signedAt}
                signedByName={props.signedByName}
              />
            )}
            <SoapEditor
              visitId={props.visitId}
              doctorEmail={props.doctorEmail}
              emailEnabled={props.emailEnabled}
              initialText={props.soapText}
              readonly={props.readonly}
              signedAt={props.signedAt}
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
            <RxTab rx={props.rxDrafts} visitId={props.visitId} />
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
// Minimal VisitExportData for the section-copy helpers.
// ---------------------------------------------------------------------------
function buildSectionData(props: VisitReadyViewProps): VisitExportData {
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
// Tabs — Linear V1 underline tabs.
// ---------------------------------------------------------------------------
interface TabDescriptor {
  key: TabKey;
  label: string;
  icon: React.ReactNode;
  /** When set, draws a dot badge — danger for 'critical', warning otherwise. */
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
    ...(showPipelineTab
      ? [{ key: 'pipeline' as const, label: 'Pipeline', icon: <LayersIcon className="h-3.5 w-3.5" aria-hidden /> }]
      : []),
  ];
  return (
    <div
      role="tablist"
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 0,
        borderBottom: '1px solid var(--color-linear-hairline)',
      }}
    >
      {tabs.map((t, i) => {
        const active = tab === t.key;
        return (
          <button
            key={t.key}
            type="button"
            role="tab"
            aria-selected={active}
            onClick={() => onChange(t.key)}
            aria-label={t.label}
            style={{
              position: 'relative',
              padding: i === 0 ? '8px 14px 10px 0' : '8px 14px 10px',
              fontFamily: 'var(--font-mono)',
              fontSize: 11,
              letterSpacing: '0.07em',
              textTransform: 'uppercase',
              fontWeight: 500,
              color: active
                ? 'var(--color-linear-text)'
                : 'var(--color-linear-text-3)',
              cursor: 'pointer',
              background: 'transparent',
              border: 0,
              transition: 'color 100ms ease-out',
              display: 'inline-flex',
              alignItems: 'center',
              gap: 6,
            }}
            onMouseEnter={(e) => {
              if (!active)
                e.currentTarget.style.color = 'var(--color-linear-text)';
            }}
            onMouseLeave={(e) => {
              if (!active)
                e.currentTarget.style.color = 'var(--color-linear-text-3)';
            }}
          >
            {t.icon}
            <span className="hidden sm:inline">{t.label}</span>
            {t.warning && (
              <span
                aria-hidden
                style={{
                  display: 'inline-block',
                  width: 5,
                  height: 5,
                  borderRadius: 999,
                  background:
                    t.warning === 'critical'
                      ? 'var(--color-linear-danger)'
                      : 'var(--color-linear-warning)',
                }}
              />
            )}
            {active && (
              <span
                aria-hidden
                style={{
                  position: 'absolute',
                  left: i === 0 ? 0 : 0,
                  right: 0,
                  bottom: -1,
                  height: 1.5,
                  borderRadius: '1px 1px 0 0',
                  background: 'var(--color-linear-sage)',
                }}
              />
            )}
          </button>
        );
      })}
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
        <div className="flex-1 text-[12px] text-linear-text-3">
          {speakerIds.length} speaker{speakerIds.length === 1 ? '' : 's'},{' '}
          {utterances.length} utterances
        </div>
        <button type="button" onClick={downloadTxt} className="qm-lin-btn">
          <Download className="h-3.5 w-3.5" aria-hidden />
          Download .txt
        </button>
      </div>

      {!readonly && speakerIds.length > 0 && (
        <div className="rounded-lg border border-linear-border bg-linear-surface-1 p-4">
          <div className={SECTION_LABEL}>Speaker roles</div>
          <div className="flex flex-wrap gap-3">
            {speakerIds.map((sid) => {
              const info = speakerMap[sid];
              return (
                <label
                  key={sid}
                  className="flex items-center gap-2 text-[12px] text-linear-text-2"
                >
                  <span className="font-medium text-linear-text">
                    Speaker #{sid}
                  </span>
                  <div className="relative">
                    <select
                      disabled={pending}
                      value={info?.role ?? 'unknown'}
                      onChange={(e) => reassign(sid, e.target.value)}
                      className="appearance-none rounded-md border border-linear-border bg-linear-surface-2 py-1 pl-2 pr-6 text-[12px] text-linear-text outline-none focus:border-linear-sage focus:ring-2 focus:ring-linear-sage/30"
                    >
                      {ROLE_OPTIONS.map((r) => (
                        <option key={r.value} value={r.value}>
                          {r.label}
                        </option>
                      ))}
                    </select>
                    <ChevronDown
                      className="pointer-events-none absolute right-1.5 top-1/2 h-3 w-3 -translate-y-1/2 text-linear-text-3"
                      aria-hidden
                    />
                  </div>
                  <span className="text-linear-text-3">
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
                isDoctor ? 'justify-end' : 'justify-start'
              )}
            >
              <div
                className="max-w-[85%] rounded-lg px-4 py-2.5 text-[13px] leading-relaxed"
                style={{
                  background: isDoctor
                    ? 'var(--color-linear-sage-tint)'
                    : 'var(--color-linear-surface-2)',
                  border: isDoctor
                    ? '1px solid rgba(122,166,140,0.32)'
                    : '1px solid var(--color-linear-border)',
                  color: isDoctor
                    ? 'var(--color-linear-text)'
                    : 'var(--color-linear-text-2)',
                }}
              >
                <div
                  className="mb-1 font-mono text-[10px] font-medium uppercase tracking-[0.07em]"
                  style={{
                    color: isDoctor
                      ? 'var(--color-linear-sage-bright)'
                      : 'var(--color-linear-text-3)',
                  }}
                >
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
            <div className="text-[12px] text-linear-text-3">
              Overall quality:{' '}
              <span className="font-medium text-linear-text">
                {critique.overall_quality}
              </span>
              {' · '}
              Safe to sign without review:{' '}
              <span className="font-medium text-linear-text">
                {critique.safe_to_sign_without_review ? 'yes' : 'no'}
              </span>
            </div>
            {critique.issues.length === 0 ? (
              <div className="text-[12px] text-linear-text-3">
                No issues flagged.
              </div>
            ) : (
              <ul className="space-y-2">
                {critique.issues.map((i, idx) => (
                  <li
                    key={idx}
                    className="rounded-md border border-linear-border bg-linear-surface-1 p-3 text-[12px]"
                  >
                    <div className="mb-1 flex items-center gap-2">
                      <span
                        className={cn(
                          'qm-lin-pill',
                          i.severity === 'critical'
                            ? 'bg-linear-danger/15 text-linear-danger'
                            : i.severity === 'major'
                              ? 'bg-linear-warning/15 text-linear-warning'
                              : ''
                        )}
                      >
                        {i.severity}
                      </span>
                      <span className="text-linear-text">{i.location}</span>
                    </div>
                    <div className="text-linear-text-2">{i.description}</div>
                    <div className="mt-1 text-linear-text-3">
                      Fix: {i.suggested_fix}
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        ) : (
          <div className="text-[12px] text-linear-text-3">
            No critique available.
          </div>
        )}
      </CollapsibleSection>

      <CollapsibleSection title="Extracted entities">
        {entities ? (
          <pre className="overflow-x-auto rounded-md border border-linear-hairline bg-linear-surface-2 p-3 font-mono text-[11px] text-linear-text-2">
            {JSON.stringify(entities, null, 2)}
          </pre>
        ) : (
          <div className="text-[12px] text-linear-text-3">Not available.</div>
        )}
      </CollapsibleSection>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-linear-border bg-linear-surface-1 px-4 py-3">
      <div className="font-mono text-[10px] font-medium uppercase tracking-[0.07em] text-linear-text-3">
        {label}
      </div>
      <div className="mt-1 text-[15px] font-medium text-linear-text">
        {value}
      </div>
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
    <div className="rounded-lg border border-linear-border bg-linear-surface-1">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between px-4 py-3 text-left font-mono text-[10.5px] font-medium uppercase tracking-[0.07em] text-linear-text-3 hover:text-linear-text-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-linear-sage focus-visible:ring-offset-2 focus-visible:ring-offset-linear-bg"
      >
        {title}
        <ChevronDown
          className={cn('h-3 w-3 transition-transform', open && 'rotate-180')}
          aria-hidden
        />
      </button>
      {open && (
        <div className="border-t border-linear-hairline px-4 py-3">
          {children}
        </div>
      )}
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
  const audioSrc = `/api/visits/${visitId}/dictation/audio`;

  return (
    <div className="space-y-4">
      <div className="rounded-lg border border-linear-border bg-linear-surface-1 p-3">
        <audio
          src={audioSrc}
          controls
          preload="metadata"
          className="w-full"
          aria-label="Replay dictation"
        />
      </div>

      {transcript ? (
        <div className="rounded-lg border border-linear-border bg-linear-surface-1 p-5 text-[14px] leading-relaxed text-linear-text-2 whitespace-pre-wrap">
          {transcript}
        </div>
      ) : (
        <div className="rounded-lg border border-dashed border-linear-border bg-linear-surface-1 p-5 text-[13px] text-linear-text-3">
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
      <div className="rounded-lg border border-dashed border-linear-border bg-linear-surface-1 p-5 text-[13px] text-linear-text-3">
        No input text stored.
      </div>
    );
  }
  return (
    <pre className="overflow-x-auto rounded-lg border border-linear-border bg-linear-surface-2 p-5 font-mono text-[12.5px] leading-relaxed whitespace-pre-wrap text-linear-text-2">
      {text}
    </pre>
  );
}

// ---------------------------------------------------------------------------
// Batch H — SignedStateCard. Renders in place of the Sign & Send CTA
// on signed visits. Calm tone (no celebratory checkmark explosion):
// soft hairline-bordered surface-1 card, sage lock icon, single line
// of factual metadata.
// ---------------------------------------------------------------------------
function SignedStateCard({
  signedAt,
  signedByName,
}: {
  signedAt: string;
  signedByName: string | null;
}) {
  const formatted = formatLocalDateTime(signedAt);
  const signer = signedByName?.trim() || 'you';
  return (
    <div
      role="status"
      aria-label="This note is signed"
      className="flex items-center gap-3 rounded-lg border px-4 py-3"
      style={{
        background: 'var(--color-linear-surface-1)',
        borderColor: 'rgba(122,166,140,0.32)',
      }}
    >
      <div
        aria-hidden
        className="flex h-8 w-8 flex-none items-center justify-center rounded-md"
        style={{
          background: 'var(--color-linear-sage-tint)',
          color: 'var(--color-linear-sage-bright)',
        }}
      >
        <Lock className="h-4 w-4" aria-hidden />
      </div>
      <div className="min-w-0">
        <div className="text-[13px] text-linear-text">
          Signed at{' '}
          <span style={{ color: 'var(--color-linear-sage-bright)' }}>
            {formatted}
          </span>{' '}
          by <span style={{ color: 'var(--color-linear-text)' }}>{signer}</span>
        </div>
        <div className="mt-0.5 text-[11.5px] text-linear-text-3">
          This note is locked. Use Export again below to re-send a copy.
        </div>
      </div>
    </div>
  );
}
