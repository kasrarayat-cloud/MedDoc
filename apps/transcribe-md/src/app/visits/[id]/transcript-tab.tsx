'use client';

// ============================================================================
// TranscriptTab — visit-detail Transcript V3 Split Pane.
// ----------------------------------------------------------------------------
// Mockup: docs/design-directions-v9-tabs/transcript-v3.html.
//
// LAYOUT — left ~62% (turns) / 1px hairline / right ~38% (audio + meta).
//   Left pane:
//     - mono search input (⌘F-style, pinned at top)
//     - diarised turns: 76px meta column (mono ts + role chip) | Inter body
//     - active turn marked with a 2px sage left-border + sage-tinted bg
//     - hover row tint, click selects (no audio jump until the wire-up
//       lands in Phase 5.2)
//   Right pane:
//     - "Now playing" / audio metadata card with native <audio>, the
//       lightweight 40-bar static waveform, scrubber, transport controls,
//       and speed picker.
//     - "Jump to section" nav (placeholder for Phase 5.2 — currently
//       skipped because we don't yet derive section anchors from
//       transcript turns)
//     - "Visit metadata" block — specialty / duration / recorded by /
//       encounter id
//     - Speaker-role reassign UI (collapsible) for audio_upload only.
//   Mobile: collapses to single column at <=960px.
//
// PRESERVED CONTRACTS:
//   - Utterance / SpeakerInfo shapes — unchanged
//   - reassignSpeakerAction — unchanged
//   - Audio playback uses a native <audio> element with the same MinIO
//     stream URL pattern used elsewhere; no hooks are added.
//   - The Download .txt button is preserved.
// ============================================================================

import { useMemo, useState, useTransition } from 'react';
import { useRouter } from 'next/navigation';
import {
  ChevronDown,
  Download,
  Search,
  Pause,
  Play,
  RotateCcw,
  RotateCw,
} from 'lucide-react';
import { toast } from 'sonner';

import { cn } from '@/lib/cn';
import { reassignSpeakerAction } from '@/actions/soap';
import type { Utterance, SpeakerInfo } from './visit-ready-view';

const ROLE_OPTIONS: { value: string; label: string }[] = [
  { value: 'doctor', label: 'Doctor' },
  { value: 'patient', label: 'Patient' },
  { value: 'family', label: 'Family' },
  { value: 'other', label: 'Other clinical staff' },
  { value: 'unknown', label: 'Unknown' },
];

const PLAYBACK_SPEEDS = [0.75, 1, 1.25, 1.5, 2] as const;
type PlaybackSpeed = (typeof PLAYBACK_SPEEDS)[number];

interface TranscriptTabProps {
  visitId: string;
  utterances: Utterance[];
  speakerMap: Record<string, SpeakerInfo>;
  readonly: boolean;
  /** Optional audio source — when provided we render the audio rail
   *  with a native <audio> element pointing at it. The visit page
   *  threads this only for audio_upload visits. */
  audioSrc?: string | null;
  /** Mono "MM:SS" total length string for the scrubber metadata. */
  durationLabel?: string | null;
  /** Visit metadata for the right rail. */
  specialtyLabel?: string;
  recordedByName?: string | null;
  encounterId?: string;
}

export function TranscriptTab({
  visitId,
  utterances,
  speakerMap,
  readonly,
  audioSrc,
  durationLabel,
  specialtyLabel,
  recordedByName,
  encounterId,
}: TranscriptTabProps) {
  const [pending, startTransition] = useTransition();
  const [activeIdx, setActiveIdx] = useState<number | null>(null);
  const [search, setSearch] = useState('');
  const [speed, setSpeed] = useState<PlaybackSpeed>(1);
  const router = useRouter();

  const speakerIds = useMemo(() => {
    const set = new Set<string>();
    for (const u of utterances) {
      if (typeof u.speaker === 'number') set.add(String(u.speaker));
    }
    return Array.from(set).sort();
  }, [utterances]);

  // Filter turns by search query (case-insensitive substring match).
  const visibleTurns = useMemo(() => {
    if (!search.trim()) return utterances;
    const q = search.toLowerCase();
    return utterances.filter((u) => u.transcript.toLowerCase().includes(q));
  }, [utterances, search]);

  const reassign = (speakerId: string, role: string) => {
    startTransition(async () => {
      const res = await reassignSpeakerAction(visitId, speakerId, role);
      if (!res.ok) {
        toast.error('Could not reassign speaker', { description: res.error });
        return;
      }
      toast.success('Speaker role updated', {
        description:
          'Re-running the SOAP pipeline will pick up the new roles.',
      });
      router.refresh();
    });
  };

  const downloadTxt = () => {
    const lines = utterances.map((u) => {
      const key = typeof u.speaker === 'number' ? String(u.speaker) : 'unknown';
      const role = speakerMap[key]?.role ?? 'unknown';
      const ts = formatMmSs(u.start);
      return `[${role} #${key}, ${ts}]: ${u.transcript.trim()}`;
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

  const onAudioRef = (el: HTMLAudioElement | null) => {
    if (el && el.playbackRate !== speed) el.playbackRate = speed;
  };

  return (
    <div className="qm-lin-split">
      {/* LEFT — transcript stream + search */}
      <div className="qm-lin-split-left">
        <label className="qm-lin-tx-search" aria-label="Search transcript">
          <Search className="h-3.5 w-3.5 text-linear-text-3" aria-hidden />
          <input
            type="search"
            placeholder="Search transcript…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <kbd>⌘F</kbd>
        </label>

        <div className="mb-3 flex flex-wrap items-center gap-3">
          <div className="flex-1 font-mono text-[10px] uppercase tracking-[0.08em] text-linear-text-3">
            {speakerIds.length} speaker{speakerIds.length === 1 ? '' : 's'} ·{' '}
            {visibleTurns.length} of {utterances.length} turns
          </div>
          <button type="button" onClick={downloadTxt} className="qm-lin-btn">
            <Download className="h-3.5 w-3.5" aria-hidden />
            Download .txt
          </button>
        </div>

        <section className="qm-lin-tx-stream" aria-label="Visit transcript">
          {visibleTurns.length === 0 ? (
            <div className="px-5 py-12 text-center font-mono text-[10px] uppercase tracking-[0.1em] text-linear-text-3">
              {utterances.length === 0 ? 'No transcript' : 'No matches'}
            </div>
          ) : (
            visibleTurns.map((u) => {
              // Find original index so the active highlight survives
              // search filtering.
              const idx = utterances.indexOf(u);
              const key =
                typeof u.speaker === 'number' ? String(u.speaker) : 'unknown';
              const role = speakerMap[key]?.role ?? 'unknown';
              const isDoctor = role === 'doctor';
              const isPatient = role === 'patient';
              const ts = formatMmSs(u.start);
              const isActive = idx === activeIdx;
              return (
                <div
                  key={`${idx}-${u.start}`}
                  className={cn(
                    'qm-lin-tx-turn',
                    isActive && 'qm-lin-tx-turn--active'
                  )}
                  onClick={() => setActiveIdx(idx)}
                  role="button"
                  tabIndex={0}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      setActiveIdx(idx);
                    }
                  }}
                >
                  <div className="qm-lin-tx-meta">
                    <span className="qm-lin-tx-ts">{ts}</span>
                    <span
                      className={cn(
                        'qm-lin-tx-role',
                        isDoctor && 'qm-lin-tx-role--doctor',
                        isPatient && 'qm-lin-tx-role--patient',
                        !isDoctor && !isPatient && 'qm-lin-tx-role--other'
                      )}
                    >
                      {role}
                    </span>
                  </div>
                  <div className="qm-lin-tx-body">{u.transcript}</div>
                </div>
              );
            })
          )}
        </section>

        {!readonly && speakerIds.length > 0 && (
          <SpeakerRoleReassign
            speakerIds={speakerIds}
            speakerMap={speakerMap}
            pending={pending}
            onReassign={reassign}
          />
        )}
      </div>

      <div className="qm-lin-split-divider" aria-hidden />

      {/* RIGHT — audio + metadata rail */}
      <aside
        className="qm-lin-split-right"
        aria-label="Audio playback and visit metadata"
      >
        {audioSrc && (
          <div className="qm-lin-rail-card">
            <div className="qm-lin-rail-card-head">
              <span className="qm-lin-rail-title">Audio</span>
              <span className="qm-lin-rail-meta">
                {durationLabel || 'mm:ss'}
              </span>
            </div>

            <StaticWaveform />

            <audio
              ref={onAudioRef}
              src={audioSrc}
              controls
              preload="metadata"
              className="w-full"
              aria-label="Replay visit audio"
            />

            {/* Round 3 PR-I — A09-P1 a11y. The audio element above is
                native <audio controls> — keyboard support (Space=play/
                pause, ←/→=seek, M=mute, ↑/↓=volume) is handled by the
                browser when the player has focus. The speed buttons
                form a toggle group: aria-pressed surfaces the active
                state to screen readers, group role gives them a
                labeled container. */}
            <div
              role="group"
              aria-label="Playback speed"
              className="mt-3 flex items-center justify-between border-t border-linear-hairline pt-3 font-mono text-[10px] uppercase tracking-[0.08em] text-linear-text-3"
            >
              <span aria-hidden>Speed</span>
              <span className="flex items-center gap-1">
                {PLAYBACK_SPEEDS.map((s) => (
                  <button
                    type="button"
                    key={s}
                    onClick={() => setSpeed(s)}
                    aria-pressed={s === speed}
                    aria-label={`Set playback speed to ${s}×`}
                    className={cn(
                      'rounded-sm px-1.5 py-0.5 transition-colors',
                      s === speed
                        ? 'bg-linear-sage-tint text-linear-sage-bright'
                        : 'text-linear-text-3 hover:text-linear-text'
                    )}
                  >
                    {s}×
                  </button>
                ))}
              </span>
            </div>
          </div>
        )}

        <div className="qm-lin-rail-card">
          <div className="qm-lin-rail-card-head">
            <span className="qm-lin-rail-title">Visit metadata</span>
            <span className="qm-lin-rail-meta">v3</span>
          </div>
          <div className="space-y-1">
            {specialtyLabel && (
              <MetaRow label="Specialty" value={specialtyLabel} />
            )}
            {durationLabel && (
              <MetaRow label="Duration" value={durationLabel} mono />
            )}
            {recordedByName && (
              <MetaRow label="Recorded by" value={recordedByName} />
            )}
            {encounterId && (
              <MetaRow label="Encounter" value={encounterId} mono />
            )}
            {speakerIds.length > 0 && (
              <MetaRow
                label="Speakers"
                value={`${speakerIds.length} detected`}
              />
            )}
          </div>
        </div>

        {/* Decorative scrubber preview — referenced by the mockup but
            we don't yet read playback state from <audio>. Kept as a
            visual anchor so the layout matches the mockup proportions. */}
        <div className="qm-lin-rail-card" aria-hidden>
          <div className="qm-lin-rail-card-head">
            <span className="qm-lin-rail-title">Transport</span>
            <span className="qm-lin-rail-meta">use ▶ above</span>
          </div>
          <div className="flex items-center justify-between text-linear-text-3">
            <button
              type="button"
              className="grid h-7 w-7 place-items-center rounded-md border border-transparent text-linear-text-3 transition-colors hover:border-linear-border hover:text-linear-text"
              aria-label="Skip back 10 seconds"
              tabIndex={-1}
            >
              <RotateCcw className="h-3 w-3" />
            </button>
            <button
              type="button"
              className="grid h-8 w-8 place-items-center rounded-full bg-linear-sage text-[#0d1611]"
              aria-label="Play"
              tabIndex={-1}
            >
              <Play className="h-3 w-3 fill-current" />
            </button>
            <button
              type="button"
              className="grid h-7 w-7 place-items-center rounded-md border border-transparent text-linear-text-3 transition-colors hover:border-linear-border hover:text-linear-text"
              aria-label="Skip forward 10 seconds"
              tabIndex={-1}
            >
              <RotateCw className="h-3 w-3" />
            </button>
          </div>
        </div>
      </aside>
    </div>
  );
}

// ---------------------------------------------------------------------------
// MetaRow — single labelled row in the metadata card.
// ---------------------------------------------------------------------------
function MetaRow({
  label,
  value,
  mono = false,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div className="qm-lin-vm-row">
      <span className="qm-lin-vm-label">{label}</span>
      <span className={cn('qm-lin-vm-value', mono && 'qm-lin-vm-value--mono')}>
        {value}
      </span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// StaticWaveform — 40 bars of SVG-ish noise, no real audio analysis.
// Pure decoration for the V3 layout; clicking the underlying <audio>
// scrubber drives playback.
// ---------------------------------------------------------------------------
function StaticWaveform() {
  // Deterministic heights so SSR + client match. Pseudo-random pattern
  // derived from a sine table — purely visual.
  const heights = useMemo(() => {
    const out: number[] = [];
    for (let i = 0; i < 40; i++) {
      const v = Math.abs(Math.sin(i * 1.3 + 0.7)) * 0.7 + 0.2;
      out.push(Math.round(v * 100));
    }
    return out;
  }, []);
  return (
    <div className="qm-lin-wave" aria-hidden>
      {heights.map((h, i) => (
        <span
          key={i}
          className={cn(
            'qm-lin-wave-bar-static',
            i < 14 && 'qm-lin-wave-bar-static--played',
            i === 14 && 'qm-lin-wave-bar-static--cur'
          )}
          style={{ height: `${h}%` }}
        />
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// SpeakerRoleReassign — collapsible list of mis-assigned speaker fixes.
// ---------------------------------------------------------------------------
function SpeakerRoleReassign({
  speakerIds,
  speakerMap,
  pending,
  onReassign,
}: {
  speakerIds: string[];
  speakerMap: Record<string, SpeakerInfo>;
  pending: boolean;
  onReassign: (speakerId: string, role: string) => void;
}) {
  const [open, setOpen] = useState(false);
  return (
    <div className="mt-4 rounded-lg border border-linear-border bg-linear-surface-1">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between px-4 py-3 text-left font-mono text-[10.5px] font-medium uppercase tracking-[0.07em] text-linear-text-3 hover:text-linear-text-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-linear-sage focus-visible:ring-offset-2 focus-visible:ring-offset-linear-bg"
        aria-expanded={open}
      >
        Speaker roles · {speakerIds.length}
        <ChevronDown
          className={cn('h-3 w-3 transition-transform', open && 'rotate-180')}
          aria-hidden
        />
      </button>
      {open && (
        <div className="border-t border-linear-hairline px-4 py-3">
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
                      onChange={(e) => onReassign(sid, e.target.value)}
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
    </div>
  );
}

// ---------------------------------------------------------------------------
// Build a SoapSource[] feed for the SOAP V3 right rail from the same
// utterance / speaker-map data — exported so visit-ready-view can keep
// the wiring contained in one spot.
// ---------------------------------------------------------------------------
import type { SoapSource } from './soap-editor';

export function utterancesToSources(
  utterances: Utterance[],
  speakerMap: Record<string, SpeakerInfo>
): SoapSource[] {
  return utterances.map((u, i) => {
    const key = typeof u.speaker === 'number' ? String(u.speaker) : 'unknown';
    const role = speakerMap[key]?.role ?? 'unknown';
    return {
      id: `t${i}`,
      speaker: role === 'unknown' ? `#${key}` : role,
      timestamp: formatMmSs(u.start),
      text: u.transcript,
      isDoctor: role === 'doctor',
    };
  });
}

function formatMmSs(seconds: number): string {
  const ts = Math.max(0, Math.floor(seconds ?? 0));
  const mm = Math.floor(ts / 60);
  const ss = (ts % 60).toString().padStart(2, '0');
  return `${mm}:${ss}`;
}

// suppress unused-import warning for Pause when audio play state isn't wired
void Pause;
