'use client';

// ============================================================================
// VisitReadyView — visit-detail body for READY/SIGNED states.
// ----------------------------------------------------------------------------
// Phase 5.1 V3 Split Pane edition. The horizontal tab bar drives the
// SOAP / Transcript / Codes / Rx / Extras / Pipeline panels; the SOAP
// and Transcript tabs each render their own V3 split-pane (sections |
// sources rail, and turns | audio rail respectively). For audio_upload
// visits we route to the new TranscriptTab; voice_dictation and
// text_notes still use the simple inline blocks below. The `theme` prop
// is preserved as a no-op for caller back-compat.
// ============================================================================

import { useCallback, useMemo, useState } from 'react';
import type { EmScore } from '@/lib/em-coding-ui/types';
import {
  FileText as FileTextIcon,
  MessageSquare as MessageSquareIcon,
  Layers as LayersIcon,
  Stethoscope,
  Pill,
  Sparkles,
  ChevronDown,
  Lock,
} from 'lucide-react';

import { cn } from '@/lib/cn';
import { isSkinBeta } from '@/config/skin-beta';
import { criticalWarningRefs } from '@/lib/rx-warnings';
import { placeholderSections } from '@/lib/parse-note-sections';
import { ReviewTabsV2, type V2Tab } from './review-tabs-v2';
// UX simplification pack (B) — flag-gated signed-visit document view.
import { isUxSimplify } from '@/config/ux-simplify';
// Pre-sign review as one document — flag-gated, UNSIGNED visits.
import { isReviewDocView } from '@/config/review-doc-view';
import { ReviewDocumentView } from './review-document-view';
import { SignedDocumentView } from './signed-document-view';
import { extractIcdRows } from '@/lib/em-coding/icd-rows';
import { BillingCardC3 } from './billing-card-c3';
import { SoapEditor } from './soap-editor';
import { SuggestionsLane, type SuggestedClaimView } from './suggestions-lane';
import { CodesTab, codesTabHasWarnings } from './codes-tab';
import { RxTab, rxTabHasContent, rxTabWarningLevel } from './rx-tab';
import { ExtrasTab, extrasTabHasFlag } from './extras-tab';
import { CopySectionButton } from './copy-section-button';
import { TranscriptTab, utterancesToSources } from './transcript-tab';
import { projectEmForDisplay, projectDisplayedEmCode } from '@/lib/visit-export';
import type { VisitExportData, CptEm } from '@/lib/visit-export';
import {
  sectionSoap,
  sectionCodes,
  sectionRx,
  sectionExtras,
} from '@/lib/ehr-formatters';
import { formatLocalDateTime } from '@/lib/format-time';
import { isVisitDocPage } from '@/config/visit-doc-page';
import { isChatEditor } from '@/config/chat-editor';
import { ChatEditorPanel } from './chat-editor-panel';
import { saveNoteSectionAction } from '@/actions/save-note-section';
import { rescoreEmAction } from '@/actions/rescore-em';
import { readNoteSection } from '@/lib/splice-note-section';
import { SectionEditCard } from './section-edit-card';
import { parseNoteSections } from '@/lib/parse-note-sections';
import {
  VisitDocumentSurface,
  VISIT_DOCUMENT_MISS_TEXT,
} from './visit-document-surface';

type VisitReadyViewTheme = 'legacy' | 'clinician';

// T-M6: six tabs — SOAP, Transcript/Input, Codes, Rx, Extras, Pipeline.
type TabKey = 'soap' | 'transcript' | 'codes' | 'rx' | 'extras' | 'pipeline';

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
  /** 2026-06-11 (L6-gate prod smoke finding): READY visits can carry a
   *  pipeline review flag (fabrication-gate rejection, unfixable critique
   *  criticals, allergy-conflict) — previously written to the DB but never
   *  rendered, so the doctor saw a bare "Needs review" pill with no reason.
   *  Rendered as a banner above the tabs; suppressed once signed. */
  needsReview?: boolean;
  reviewReason?: string | null;
  /** Hybrid anchored generation (2026-06-11) — claims the L4b fail-closed
   *  verifier demoted from the note body, rendered in the "Suggested by AI —
   *  not stated in this visit" lane below the SOAP editor for explicit
   *  doctor adoption. Null/empty (or signed) → lane hidden. */
  suggestedClaims?: SuggestedClaimView[] | null;
  /** Determines which "input" tab is shown + whether speaker reassignment
   *  is available. */
  inputMode: string;
  /** The note shown in the SOAP tab — soapFinal when READY, signedSoap
   *  when SIGNED. The caller picks. */
  soapText: string;
  /** Round 3 PR-E (A09-P0-003) — optimistic-concurrency token. The
   *  RSC loads `transcribe_visits.soapVersion` and forwards it to the
   *  client editor; saves include this version so two-tab edits
   *  conflict-detect instead of last-write-wins. */
  soapVersion: number;
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
  /** Round 4 critical-Rx-override fix: warningIds with existing
   *  RxWarningOverride rows. Threaded into RxTab → RxWarningsRail so
   *  ✓ Overridden chips persist across reload. */
  rxOverriddenWarningIds: string[];
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
  /** Phase 5.1 — pretty-printed specialty for the Transcript V3
   *  metadata rail. Optional for back-compat. */
  specialtyLabel?: string;
  /** Phase 5.1 — display name shown in the Transcript V3 "Recorded by"
   *  metadata row. Optional for back-compat. */
  recordedByName?: string | null;

  /** Phase 5.2 — server-rendered initial E&M score for the Coding Coach
   *  rail. Null when the engine fail-soft'd (rail renders skeleton). */
  initialEmScore?: EmScore | null;

  /** Ultrasound (flag-gated) — true when this visit is an IMAGING REPORT, for
   *  which an office-visit E/M level does not apply. The Billing tab then
   *  renders a clear "not applicable" note instead of a coding score. */
  emNotApplicable?: boolean;

  /** E/M visible-confirm (prod smoke #311) — the UNACKNOWLEDGED
   *  suggestion-caused E/M level change ({from, to} codes only — no PHI),
   *  or null when there is nothing to confirm. Hydrates the Sign & Send
   *  modal's confirm control; the sign route enforces it server-side. */
  emPendingChange?: { from: string; to: string } | null;
  /** The note changed since the E/M level was scored — signing is refused
   *  until the codes row re-checks it. */
  emStale?: boolean;

  // Phase 5.1.1 — V4 Extras card-stream wiring.
  // Patient identity (powers DemographicsCard) + problem list (powers
  // ProblemsCard) come from the patient row; the rest is derived from
  // visit fields below. Optional for back-compat.
  patientName?: string | null;
  patientDob?: string | null;
  patientMrn?: string | null;
  patientInsurance?: string | null;
  patientExternalId?: string | null;
  patientProblemList?: unknown;
  /** ISO 8601 — visit creation moment (powers AuditLogCard's first row). */
  visitCreatedAt?: string | null;

  /** @deprecated kept for back-compat; Linear V1 is single-theme. */
  theme?: VisitReadyViewTheme;
}

/** E/M visible-confirm — value equality for the {from, to} pair (the RSC
 *  payload re-creates the object on every refresh, so reference equality
 *  would re-sync forever). */
function pendingEmChangeEq(
  a: { from: string; to: string } | null,
  b: { from: string; to: string } | null
): boolean {
  if (a === null || b === null) return a === b;
  return a.from === b.from && a.to === b.to;
}

export function VisitReadyView(props: VisitReadyViewProps) {
  const [tab, setTab] = useState<TabKey>('soap');

  // Hybrid anchored generation (2026-06-11) — when the doctor adopts a
  // suggestion the server appends to soapFinal + bumps soapVersion; the
  // lane reports the new state back here and we REMOUNT the editor (seq
  // in its key) so its useState(initialText) re-initializes with the
  // adopted line. Normal section saves never change the key, so the
  // editor's in-flight state is untouched outside adoption.
  const [adoption, setAdoption] = useState<{
    text: string;
    version: number;
    seq: number;
  } | null>(null);

  // ── PHASE 2 — the visit page IS the document ────────────────────────────
  const docPage = isVisitDocPage();

  const chatEditor = isChatEditor();
  /** Set once the document turns out to be unavailable (not certified, fill
   *  failed, could not be drawn). Latched so the page does not flicker between
   *  two surfaces while the doctor is reading — and so the styled note, once
   *  chosen, stays chosen for this visit. */
  /** Mirrors the server's `emStale`. Every content mutation on this page sets
   *  it server-side; the re-score clears it. Held locally so the badge and the
   *  sign bar react without a round trip. */
  const [emStale, setEmStale] = useState(props.emStale ?? false);
  const [docPageMiss, setDocPageMiss] = useState<string | null>(null);
  const docPageUnavailable = docPageMiss !== null;
  const handleDocPageUnavailable = useCallback((reason: string | null) => {
    setDocPageMiss(reason ?? 'no_render');
  }, []);
  /** The anchors cards are placed against. The KEY IS THE SECTION LABEL, which
   *  is exactly what the suggestion map is keyed by — so a card placed on a
   *  page and a card placed under a heading resolve through the same lookup. */
  /** Save one section. Goes through saveNoteSectionAction (which splices and
   *  delegates to the existing draft save), then bumps the same `adoption`
   *  state an adopt does — so the document re-fills through one path, not two. */
  const saveSection = useCallback(
    async (label: string, body: string, expectedVersion: number) => {
      const r = await saveNoteSectionAction(props.visitId, label, body, expectedVersion);
      if (!r.ok || !r.soapFinal) return { ok: false, error: r.error };
      setEmStale(true);
      setAdoption((prev) => ({
        text: r.soapFinal as string,
        version: r.soapVersion ?? (prev?.version ?? props.soapVersion) + 1,
        seq: (prev?.seq ?? 0) + 1,
      }));
      return { ok: true };
    },
    [props.visitId, props.soapVersion],
  );

  const docAnchors = useMemo(
    () =>
      (docPage ? parseNoteSections(adoption?.text ?? props.soapText) : []).map((sec) => ({
        key: sec.label,
        text: sec.label,
      })),
    [docPage, adoption?.text, props.soapText],
  );
  // E/M visible-confirm (prod smoke #311) — the unacknowledged change the
  // Sign & Send modal must surface. Server-rendered prop is the source of
  // truth (re-synced on every RSC refresh via the adjust-state-during-
  // render pattern, compared by VALUE — the RSC payload re-creates the
  // object); the adopt action's response updates it immediately so the
  // confirm control appears without waiting for the refresh round-trip.
  const propPendingEm = props.emPendingChange ?? null;
  const [pendingEmChange, setPendingEmChange] = useState<
    { from: string; to: string } | null
  >(propPendingEm);
  const [syncedPendingEm, setSyncedPendingEm] = useState(propPendingEm);
  if (!pendingEmChangeEq(syncedPendingEm, propPendingEm)) {
    setSyncedPendingEm(propPendingEm);
    setPendingEmChange(propPendingEm);
  }

  const rescoreEm = useCallback(async () => {
    const r = await rescoreEmAction(props.visitId);
    if (!r.ok) return;
    setEmStale(r.stale);
    // The level moved: hand it to the SAME confirm card an adopt would arm.
    if (r.pending) setPendingEmChange(r.pending);
  }, [props.visitId]);


  const handleSuggestionAdopted = useCallback(
    (r: {
      soapFinal: string;
      soapVersion: number;
      emPendingChange?: { from: string; to: string } | null;
    }) => {
      // Adopting changes the note, so the server marked the level stale.
      // Mirror it: the badge and the lazy re-score both key off this.
      setEmStale(true);
      setAdoption((prev) => ({
        text: r.soapFinal,
        version: r.soapVersion,
        seq: (prev?.seq ?? 0) + 1,
      }));
      if (r.emPendingChange !== undefined) {
        setPendingEmChange(r.emPendingChange);
      }
    },
    []
  );

  // V2 review (skin-only, flag-gated) — live mirror of the server's fail-closed
  // critical-Rx sign gate, so the V2 shell can disable the Sign trigger until
  // every critical interaction is overridden (the VISIBLE half; POST /sign 422
  // remains the enforcement). Seeded from the persisted override rows using the
  // SAME criticalWarningRefs identity the sign route validates, then kept live
  // by RxTab's onResolvedChange. Computed unconditionally (hooks rule); only the
  // flag-ON branch consumes it.
  const initialRxResolved = useMemo(
    () =>
      criticalWarningRefs(props.rxDrafts).every((ref) =>
        (props.rxOverriddenWarningIds ?? []).includes(ref.id)
      ),
    [props.rxDrafts, props.rxOverriddenWarningIds]
  );
  const [rxResolved, setRxResolved] = useState(initialRxResolved);

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
  /** Anything to show at all — medications or warnings. Distinct from rxWarn,
   *  which is what makes a gate fire. */
  const rxHasContent = rxTabHasContent(props.rxDrafts);
  const extrasWarn = extrasTabHasFlag(
    props.confidenceScores,
    Boolean(props.patientSummary)
  );

  // Synthesize the minimum VisitExportData shape the section-copy
  // helpers need. sectionSoap / sectionCodes / sectionRx /
  // sectionExtras don't touch patient header or clinician info, so
  // the placeholder fields below are never read.
  const sectionData = buildSectionData(props);

  // Phase 5.1 — feed the SOAP V3 sources rail with diarised turns.
  // For non-audio inputs this is empty and the rail collapses to the
  // empty-state hint.
  // F-7: sections still carrying the verifier's set-aside placeholder,
  // computed from the freshest client-side text (adoption strips the
  // placeholder server-side and returns fresh text; manual edits re-sync
  // via the RSC refresh on save). Feeds the pre-sign ADVISORY only —
  // memoized top-level (unconditional hook) so child callback deps get a
  // stable identity (auditor N-1/N-6).
  const setAsideSections = useMemo(() => {
    if (props.readonly || props.signedAt !== null) return [];
    return placeholderSections(adoption?.text ?? props.soapText);
  }, [props.readonly, props.signedAt, adoption?.text, props.soapText]);

  const soapSources = useMemo(
    () =>
      props.inputMode === 'audio_upload'
        ? utterancesToSources(props.utterances, props.speakerMap)
        : [],
    [props.inputMode, props.utterances, props.speakerMap]
  );

  // Phase 5.1 — Transcript V3 audio source URL + duration label.
  // audio_upload visits don't currently expose a streaming audio
  // endpoint (only voice_dictation does, via /api/visits/[id]/dictation/
  // audio). Until an audio_upload streaming route lands, the right
  // rail still renders the metadata + waveform decoration without an
  // <audio> element — visit-ready-view passes audioSrc=null in that
  // case and TranscriptTab handles the fallback gracefully.
  const audioSrc = null;
  const durationLabel =
    typeof props.durationSec === 'number' && props.durationSec > 0
      ? formatDurationLabel(props.durationSec)
      : null;

  // ── V2 "Tabbed sign-gate workspace" review skin (flag-gated) ──────────────
  // SKIN-ONLY: replaces the C3 review drawer AND the side coding rail. The note
  // (SoapEditor, chromeless) and every secondary surface live on their OWN
  // full-width tab — nothing is ever beside the note, at any screen size. The
  // ONE Sign action moves into ReviewTabsV2's persistent bottom bar (the SAME
  // SignAndSendModal, with the E/M confirm gate intact). Every tab child is the
  // SAME gate-bearing component the legacy tabs render; only the container
  // changes. No sign / Rx / E/M / audit logic is touched. Both sign gates keep
  // firing — critical-Rx (server POST /sign 422; visible half = Sign trigger
  // disabled until rxResolved) and E/M confirm (inside SignAndSendModal). Flag
  // OFF → the legacy tabs below run verbatim.
  if (isSkinBeta()) {
    const isSigned = props.readonly || props.signedAt !== null;
    const showSuggestions =
      !props.readonly &&
      !props.signedAt &&
      (props.suggestedClaims?.length ?? 0) > 0;
    const suggestionCount = showSuggestions
      ? (props.suggestedClaims?.length ?? 0)
      : 0;

    const transcriptInner =
      props.inputMode === 'audio_upload' ? (
        <TranscriptTab
          visitId={props.visitId}
          utterances={props.utterances}
          speakerMap={props.speakerMap}
          readonly={props.readonly}
          audioSrc={audioSrc}
          durationLabel={durationLabel}
          specialtyLabel={props.specialtyLabel}
          recordedByName={props.recordedByName ?? null}
          encounterId={props.visitId.slice(0, 8)}
        />
      ) : props.inputMode === 'voice_dictation' ? (
        <DictationTranscriptView
          visitId={props.visitId}
          transcript={props.dictationTranscript}
        />
      ) : (
        <RawTextInputView text={props.rawTextInput} />
      );

    const rxBadge: V2Tab['badge'] =
      rxWarn === 'critical'
        ? rxResolved
          ? { tone: 'ok', text: '✓' }
          : { tone: 'danger', text: '!' }
        : rxWarn === 'any'
          ? { tone: 'warn', text: '!' }
          : null;

    // Tabs — each child is the SAME gate-bearing component the legacy tabs
    // render; only the container is the V2 full-width tab strip. Built with
    // pushes so each literal is contextually typed as V2Tab.
    const tabs: V2Tab[] = [];
    tabs.push({
      key: 'note',
      label: isSigned ? 'Note · signed' : 'Note',
      node: (
        <>
          {props.signedAt && (
            <SignedStateCard
              signedAt={props.signedAt}
              signedByName={props.signedByName}
            />
          )}
          <div className={props.signedAt ? 'mt-3' : undefined}>
            <SoapEditor
              key={`soap-editor-${adoption?.seq ?? 0}`}
              visitId={props.visitId}
              doctorEmail={props.doctorEmail}
              emailEnabled={props.emailEnabled}
              initialText={adoption?.text ?? props.soapText}
              initialSoapVersion={adoption?.version ?? props.soapVersion}
              readonly={props.readonly}
              signedAt={props.signedAt}
              sources={soapSources}
              initialScore={props.initialEmScore}
              emPendingChange={pendingEmChange}
              chromeless
            />
          </div>
        </>
      ),
    });
    if (showSuggestions) {
      tabs.push({
        key: 'review',
        label: 'Review',
        badge: { tone: 'info', text: String(suggestionCount) },
        node: (
          <SuggestionsLane
            visitId={props.visitId}
            claims={props.suggestedClaims ?? []}
            onAdopted={handleSuggestionAdopted}
          />
        ),
      });
    }
    tabs.push({
      key: 'rx',
      label: 'Rx',
      badge: rxBadge,
      node: (
        <RxTab
          rx={props.rxDrafts}
          visitId={props.visitId}
          readonly={props.readonly}
          initialOverriddenIds={props.rxOverriddenWarningIds}
          onResolvedChange={setRxResolved}
        />
      ),
    });
    tabs.push({
      key: 'billing',
      label: 'Billing',
      badge:
        props.emNotApplicable ? null : pendingEmChange ? { tone: 'warn', text: '!' } : null,
      node: (
        <BillingCardC3
          initialScore={props.initialEmScore ?? null}
          visitId={props.visitId}
          readonly={props.readonly}
          emPendingChange={pendingEmChange}
          notApplicable={props.emNotApplicable}
        />
      ),
    });
    tabs.push({
      key: 'codes',
      label: 'Codes',
      badge: codesWarn ? { tone: 'warn', text: '!' } : null,
      node: (
        <CodesTab
          icd={props.icdCodes}
          cpt={props.cptCodes}
          readonly={props.readonly}
        />
      ),
    });
    tabs.push({
      key: 'extras',
      label: 'Extras',
      badge: extrasWarn ? { tone: 'warn', text: '!' } : null,
      node: (
        <ExtrasTab
              visitId={props.visitId}
          referrals={props.referrals}
          patientSummary={props.patientSummary}
          fleschKincaid={fleschKincaid}
          flagged={summaryFlagged}
          readonly={props.readonly}
          demographics={
            props.patientName
              ? {
                  name: props.patientName,
                  dateOfBirth: props.patientDob ?? null,
                  externalId: props.patientExternalId ?? null,
                  address: null,
                  insurance: props.patientInsurance ?? null,
                  insuranceVerified: null,
                  preferredLanguage: null,
                  emergencyContact: null,
                  emergencyRelation: null,
                }
              : undefined
          }
          vitals={{}}
          allergies={[]}
          chronicMedications={[]}
          problems={parseProblemList(props.patientProblemList)}
          visitMeta={{
            specialty:
              props.specialtyLabel ?? props.inputMode ?? 'Encounter',
            durationSec: props.durationSec,
            audioDurationSec: props.durationSec,
            inputMode: props.inputMode,
            billingProvider: props.recordedByName ?? null,
            providerNpi: null,
            encounterId: props.visitId,
          }}
          auditEvents={synthesizeAuditEvents({
            createdAt: props.visitCreatedAt,
            processingStartedAt: props.processingStartedAt,
            processingFinishedAt: props.processingFinishedAt,
            signedAt: props.signedAt,
            signedByName: props.signedByName,
            doctorName: props.recordedByName,
          })}
        />
      ),
    });
    tabs.push({
      key: 'transcript',
      label: secondTabLabel,
      node: transcriptInner,
    });
    if (props.showPipelineTab) {
      tabs.push({
        key: 'pipeline',
        label: 'Pipeline',
        node: (
          <PipelineView
            entities={props.entities}
            critique={props.critique}
            durationSec={props.durationSec}
            costCents={props.costCents}
            processingStartedAt={props.processingStartedAt}
            processingFinishedAt={props.processingFinishedAt}
          />
        ),
      });
    }

    // ── UX simplification pack (B): a SIGNED note is a finished record, so it
    //    renders as ONE scrolling document instead of six tabs. Flag-gated and
    //    scoped to signed/readonly ONLY — the unsigned path below keeps
    //    ReviewTabsV2 verbatim, because that is where the critical-Rx and E/M
    //    gates live and those are frozen.
    //
    //    The nodes are pulled straight out of the tab list that was just built,
    //    so the note and the transcript render byte-for-byte what the tabs
    //    render. Only the container changes.
    // 3b. PRE-SIGN REVIEW AS THE DOCUMENT — flag NEXT_PUBLIC_REVIEW_DOC_VIEW.
    //     The other half of the linearisation, for UNSIGNED visits. The gates
    //     are NOT moved: RxTab is handed to the document verbatim (same
    //     override modal, same recordOverride, one button per warning), the E/M
    //     confirmation inside SignAndSendModal stays exactly where it is and
    //     stays the enforcement, and POST /sign is untouched. What changes is
    //     that a blocker can no longer hide behind a tab nobody opened.
    if (isReviewDocView() && !isSigned) {
      const dictationNode = tabs.find((t) => t.key === 'transcript')?.node ?? null;
      const emBlob = (props.cptCodes as { em?: CptEm } | null | undefined)?.em ?? null;
      const displayedEm = projectDisplayedEmCode(emBlob, false);

      return (
        <div className="w-full qm-c3-rev2-root">
          {/* The PIPELINE review-reason banner — not the set-aside advisory the
              inline highlights replace. It names why the pipeline flagged the
              visit, which nothing else on this surface says, so it stays. */}
        {props.needsReview && props.reviewReason && !props.signedAt && (
          <div
            role="status"
            data-testid="review-reason-banner"
            className="mb-4 rounded-lg border px-4 py-3 text-[13px] leading-relaxed"
            style={{
              borderColor:
                'color-mix(in srgb, var(--color-linear-amber) 35%, transparent)',
              background:
                'color-mix(in srgb, var(--color-linear-amber) 8%, transparent)',
              color: 'var(--color-linear-amber)',
            }}
          >
            <span className="font-medium">Review before signing — </span>
            <span style={{ color: 'var(--color-linear-text-2)' }}>
              {props.reviewReason}
            </span>
          </div>
        )}
          {/* WHY the document is not on screen. The reason was carried all the
              way here and then read as a boolean — so a doctor whose template
              is not certified watched "Opening your document…" turn into a
              styled note with no explanation. Silence is illegal. */}
          {docPage && docPageMiss && VISIT_DOCUMENT_MISS_TEXT[docPageMiss] && (
            <p
              className="qm-vdoc-counts"
              role="status"
              data-testid="visit-document-miss"
            >
              {VISIT_DOCUMENT_MISS_TEXT[docPageMiss]}
            </p>
          )}
          {chatEditor && !props.signedAt && (
            <ChatEditorPanel
              visitId={props.visitId}
              disabled={props.readonly}
              onNoteChanged={(r) => {
                // The server marked the level stale for this change; mirror it
                // locally or the badge never appears, the codes row never
                // re-scores, and the doctor meets the sign gate with no visible
                // way to resolve it.
                setEmStale(true);
                setAdoption((prev) => ({
                  text: r.soapFinal,
                  version: r.soapVersion ?? (prev?.version ?? props.soapVersion) + 1,
                  seq: (prev?.seq ?? 0) + 1,
                }));
              }}
              onHeaderChanged={() => {
                // Bump the revision ONLY. The note is byte-identical — a header
                // edit changes the drawn page, not the clinical content — so
                // the text is carried forward untouched and the level is NOT
                // marked stale: nothing that E/M scores on has moved.
                setAdoption((prev) => ({
                  text: prev?.text ?? props.soapText,
                  version: prev?.version ?? props.soapVersion,
                  seq: (prev?.seq ?? 0) + 1,
                }));
              }}
              onScrollTo={(target) => {
                // EVERY target the schema allows must resolve to something.
                // `em_gate` and `suggestions` had no anchor at all, so the chat
                // said "Took you to the E/M gate" and the page did not move —
                // a navigation aid that lies about having navigated.
                const el =
                  target === 'rx_gate'
                    ? document.querySelector('[data-testid="review-doc-rx-gate"]')
                    : target === 'document'
                      ? document.querySelector('[data-testid="visit-document"]')
                      : target === 'suggestions'
                        ? // The first outstanding card; the lane has no single
                          // container, and scrolling to a group that may not
                          // exist is the same failure one level down.
                          document.querySelector('[data-testid="review-doc-suggestion"]')
                        : document.querySelector(`[data-chat-target="${target}"]`);
                // "Show billing" has to OPEN it, not scroll to a collapsed row.
                // Now that codes and billing live behind one on-demand panel,
                // taking the doctor to a shut drawer and calling it done would
                // be the reachability ruling honoured in letter only. The panel
                // is its own toggle, so ask it to open rather than mirroring
                // its state up here where the two could drift apart.
                if (
                  el instanceof HTMLElement &&
                  el.getAttribute('aria-expanded') === 'false'
                ) {
                  el.click();
                }
                el?.scrollIntoView({ behavior: 'smooth', block: 'center' });
              }}
            />
          )}
          <ReviewDocumentView
            visitId={props.visitId}
            doctorEmail={props.doctorEmail}
            emailEnabled={props.emailEnabled}
            soapFinal={adoption?.text ?? props.soapText}
            /* PHASE 2 — the page becomes the doctor's own form. Returns null
               when there is nothing to draw, and ReviewDocumentView then falls
               back to renderNote below, unchanged. */
            renderDocument={
              docPage && !props.signedAt && !docPageUnavailable
                ? (afterLabel) => (
                    <VisitDocumentSurface
                      visitId={props.visitId}
                      revision={adoption?.seq ?? 0}
                      anchors={docAnchors}
                      renderAfterSection={(keys) => (
                        <>
                          {keys.map((k) => (
                            /* Named, because "which section is this suggestion
                               under" is the invariant that matters clinically:
                               a claim reviewed under one heading and signed
                               under another is the failure this placement
                               exists to prevent. Nothing reads it at runtime. */
                            <div key={k} data-section={k}>
                              {afterLabel(k)}
                              {/* Under the page the section appears on — the
                                  only place this view can honestly offer it. */}
                              <SectionEditCard
                                label={k}
                                body={readNoteSection(adoption?.text ?? props.soapText, k)}
                                disabled={props.readonly || props.signedAt !== null}
                                soapVersion={adoption?.version ?? props.soapVersion}
                                onSave={saveSection}
                              />
                            </div>
                          ))}
                        </>
                      )}
                      renderUnplaced={(keys) => (
                        <>
                          {keys.map((k) => (
                            <div key={k}>{afterLabel(k)}</div>
                          ))}
                        </>
                      )}
                      onUnavailable={handleDocPageUnavailable}
                    />
                  )
                : undefined
            }
            renderNote={(afterSection) => (
              <SoapEditor
                key={`soap-editor-${adoption?.seq ?? 0}`}
                visitId={props.visitId}
                doctorEmail={props.doctorEmail}
                emailEnabled={props.emailEnabled}
                initialText={adoption?.text ?? props.soapText}
                initialSoapVersion={adoption?.version ?? props.soapVersion}
                readonly={props.readonly}
                signedAt={props.signedAt}
                sources={soapSources}
                initialScore={props.initialEmScore}
                emPendingChange={pendingEmChange}
                chromeless
                afterSection={afterSection}
              />
            )}
            claims={props.suggestedClaims ?? []}
            rxGateNode={
              // PRESCRIPTIONS **OR** WARNINGS. Warnings alone was the old
              // condition, which meant a visit with medications and no
              // interaction had nowhere to show them; and an imaging study with
              // neither still drew a "Prescription safety" heading over an empty
              // panel. The GATE behaviour is untouched — it keys on
              // `rxBlocking`, below, exactly as before.
              rxHasContent ? (
                <RxTab
                  rx={props.rxDrafts}
                  visitId={props.visitId}
                  readonly={props.readonly}
                  initialOverriddenIds={props.rxOverriddenWarningIds}
                  onResolvedChange={setRxResolved}
                />
              ) : null
            }
            rxBlocking={!rxResolved}
            rxHasWarnings={rxWarn !== null}
            emPendingChange={pendingEmChange}
            summary={{
              icd: extractIcdRows(props.icdCodes),
              emCode: displayedEm,
              emNotApplicable: !!props.emNotApplicable,
            }}
            emStale={emStale}
            onRescoreEm={rescoreEm}
            billingNode={tabs.find((t) => t.key === 'billing')?.node ?? null}
            codesNode={tabs.find((t) => t.key === 'codes')?.node ?? null}
            dictationNode={dictationNode}
            dictationLabel={secondTabLabel}
            onAdopted={handleSuggestionAdopted}
          />
        </div>
      );
    }

    if (isUxSimplify() && isSigned) {
      const noteNode = tabs.find((t) => t.key === 'note')?.node ?? null;
      const dictationNode = tabs.find((t) => t.key === 'transcript')?.node ?? null;
      // Authoritative displayed level — the SAME projection every exported
      // artifact uses (signed ⇒ the frozen signedCode, else override ?? raw),
      // so the summary row can never disagree with the exported document.
      const emBlob = (props.cptCodes as { em?: CptEm } | null | undefined)?.em ?? null;
      const displayedEm = projectDisplayedEmCode(emBlob, true);
      const overrodeCount = props.rxOverriddenWarningIds?.length ?? 0;

      return (
        <div className="w-full qm-c3-rev2-root">
          <SignedDocumentView
              documentNode={
                docPage && !docPageUnavailable ? (
                  <VisitDocumentSurface
                    visitId={props.visitId}
                    revision={adoption?.seq ?? 0}
                    anchors={[]}
                    renderAfterSection={() => null}
                    renderUnplaced={() => null}
                    onUnavailable={handleDocPageUnavailable}
                  />
                ) : undefined
              }
            visitId={props.visitId}
            doctorEmail={props.doctorEmail}
            emailEnabled={props.emailEnabled}
            // The signed-lock banner already rides inside the note node
            // (SignedStateCard), so it is not duplicated here.
            lockBanner={null}
            noteNode={noteNode}
            dictationNode={dictationNode}
            // Name the source the doctor actually produced, rather than
            // reusing a tab noun: "View original dictation" / "…transcript" /
            // "…typed notes" all read as the thing they are.
            dictationLabel={
              props.inputMode === 'voice_dictation'
                ? 'original dictation'
                : props.inputMode === 'text_notes'
                  ? 'the original typed notes'
                  : 'the original transcript'
            }
            summary={{
              icd: extractIcdRows(props.icdCodes),
              emCode: displayedEm,
              emNotApplicable: !!props.emNotApplicable,
              // Shown ONLY when an override was actually recorded — otherwise
              // the row would assert "no overrides" on every ordinary note.
              rxOverrideNote:
                overrodeCount > 0
                  ? `${overrodeCount} critical interaction${overrodeCount === 1 ? '' : 's'} overridden before signing`
                  : null,
            }}
          />
        </div>
      );
    }

    return (
      <div className="w-full qm-c3-rev2-root">
        {props.needsReview && props.reviewReason && !props.signedAt && (
          <div
            role="status"
            data-testid="review-reason-banner"
            className="mb-4 rounded-lg border px-4 py-3 text-[13px] leading-relaxed"
            style={{
              borderColor:
                'color-mix(in srgb, var(--color-linear-amber) 35%, transparent)',
              background:
                'color-mix(in srgb, var(--color-linear-amber) 8%, transparent)',
              color: 'var(--color-linear-amber)',
            }}
          >
            <span className="font-medium">Review before signing — </span>
            <span style={{ color: 'var(--color-linear-text-2)' }}>
              {props.reviewReason}
            </span>
          </div>
        )}
        <ReviewTabsV2
          tabs={tabs}
          rxCritical={rxWarn === 'critical'}
          rxResolved={rxResolved}
          pendingEmChange={pendingEmChange}
          rxTabKey="rx"
          reviewTabKey="review"
          visitId={props.visitId}
          doctorEmail={props.doctorEmail}
          emailEnabled={props.emailEnabled}
          signed={isSigned}
          placeholderSections={setAsideSections}
          suggestionCount={suggestionCount}
        />
      </div>
    );
  }

  return (
    <div className="w-full">
      {/* Pipeline review banner — the WHY behind the "Needs review" pill.
          Suppressed once signed (the doctor has reviewed by definition). */}
      {props.needsReview && props.reviewReason && !props.signedAt && (
        <div
          role="status"
          data-testid="review-reason-banner"
          className="mb-4 rounded-lg border px-4 py-3 text-[13px] leading-relaxed"
          style={{
            borderColor: 'color-mix(in srgb, var(--color-linear-amber) 35%, transparent)',
            background: 'color-mix(in srgb, var(--color-linear-amber) 8%, transparent)',
            color: 'var(--color-linear-amber)',
          }}
        >
          <span className="font-medium">Review before signing — </span>
          <span style={{ color: 'var(--color-linear-text-2)' }}>
            {props.reviewReason}
          </span>
        </div>
      )}
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
                visitId={props.visitId}
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
              key={`soap-editor-${adoption?.seq ?? 0}`}
              visitId={props.visitId}
              doctorEmail={props.doctorEmail}
              emailEnabled={props.emailEnabled}
              initialText={adoption?.text ?? props.soapText}
              initialSoapVersion={adoption?.version ?? props.soapVersion}
              readonly={props.readonly}
              signedAt={props.signedAt}
              sources={soapSources}
              initialScore={props.initialEmScore}
              emPendingChange={pendingEmChange}
            />
            {/* Hybrid anchored generation — verifier-demoted claims for
                explicit doctor adoption. Hidden once signed (the note is
                locked; the lane's actions reject SIGNED anyway) and on
                readonly views. */}
            {!props.readonly &&
              !props.signedAt &&
              (props.suggestedClaims?.length ?? 0) > 0 && (
                <SuggestionsLane
                  visitId={props.visitId}
                  claims={props.suggestedClaims ?? []}
                  onAdopted={handleSuggestionAdopted}
                />
              )}
          </div>
        )}
        {tab === 'transcript' &&
          (props.inputMode === 'audio_upload' ? (
            <TranscriptTab
              visitId={props.visitId}
              utterances={props.utterances}
              speakerMap={props.speakerMap}
              readonly={props.readonly}
              audioSrc={audioSrc}
              durationLabel={durationLabel}
              specialtyLabel={props.specialtyLabel}
              recordedByName={props.recordedByName ?? null}
              encounterId={props.visitId.slice(0, 8)}
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
                visitId={props.visitId}
                text={sectionCodes(sectionData)}
                label="Copy codes"
                section="Codes"
              />
            </div>
            <CodesTab
              icd={props.icdCodes}
              cpt={props.cptCodes}
              readonly={props.readonly}
            />
          </div>
        )}
        {tab === 'rx' && (
          <div className="space-y-3">
            <div className="flex justify-end">
              <CopySectionButton
                visitId={props.visitId}
                text={sectionRx(sectionData)}
                label="Copy Rx"
                section="Prescriptions"
              />
            </div>
            <RxTab
              rx={props.rxDrafts}
              visitId={props.visitId}
              readonly={props.readonly}
              initialOverriddenIds={props.rxOverriddenWarningIds}
            />
          </div>
        )}
        {tab === 'extras' && (
          <div className="space-y-3">
            <div className="flex justify-end">
              <CopySectionButton
                visitId={props.visitId}
                text={sectionExtras(sectionData)}
                label="Copy extras"
                section="Referrals + patient summary"
              />
            </div>
            <ExtrasTab
              visitId={props.visitId}
              referrals={props.referrals}
              patientSummary={props.patientSummary}
              fleschKincaid={fleschKincaid}
              flagged={summaryFlagged}
              readonly={props.readonly}
              // Phase 5.1.1 — wire 7 V4 cards
              demographics={
                props.patientName
                  ? {
                      name: props.patientName,
                      dateOfBirth: props.patientDob ?? null,
                      externalId: props.patientExternalId ?? null,
                      address: null,
                      insurance: props.patientInsurance ?? null,
                      insuranceVerified: null,
                      preferredLanguage: null,
                      emergencyContact: null,
                      emergencyRelation: null,
                    }
                  : undefined
              }
              vitals={{}}
              allergies={[]}
              chronicMedications={[]}
              problems={parseProblemList(props.patientProblemList)}
              visitMeta={{
                specialty:
                  props.specialtyLabel ?? props.inputMode ?? 'Encounter',
                durationSec: props.durationSec,
                audioDurationSec: props.durationSec,
                inputMode: props.inputMode,
                billingProvider: props.recordedByName ?? null,
                providerNpi: null,
                encounterId: props.visitId,
              }}
              auditEvents={synthesizeAuditEvents({
                createdAt: props.visitCreatedAt,
                processingStartedAt: props.processingStartedAt,
                processingFinishedAt: props.processingFinishedAt,
                signedAt: props.signedAt,
                signedByName: props.signedByName,
                doctorName: props.recordedByName,
              })}
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
// Phase 5.1.1 — V4 Extras card helpers.
//
// `parseProblemList` accepts the patient.problemList jsonb in either of two
// shapes: a string array of names, or an array of `{ code, name?|label?,
// status? }` objects (the Phase-1 free-text shape per schema comment). We
// normalize to the ProblemsCard `Problem` shape with sensible status fallback.
//
// `synthesizeAuditEvents` derives a 5-event timeline from the visit's own
// timestamp fields (createdAt → processingStartedAt → processingFinishedAt
// → signedAt). No new Prisma query required — we never touch the audit_logs
// table from this read-only display surface.
// ---------------------------------------------------------------------------

import type { Problem } from './extras/ProblemsCard';
import type { AuditEvent } from './extras/AuditLogCard';

function parseProblemList(raw: unknown): Problem[] {
  if (!Array.isArray(raw)) return [];
  return raw.map((entry, i) => {
    if (typeof entry === 'string') {
      return { icd: null, name: entry, status: 'active' as const, detail: null };
    }
    if (entry && typeof entry === 'object') {
      const obj = entry as Record<string, unknown>;
      const name =
        (typeof obj.name === 'string' && obj.name) ||
        (typeof obj.label === 'string' && obj.label) ||
        (typeof obj.title === 'string' && obj.title) ||
        `Problem ${i + 1}`;
      const code =
        (typeof obj.icd === 'string' && obj.icd) ||
        (typeof obj.icd10 === 'string' && obj.icd10) ||
        (typeof obj.code === 'string' && obj.code) ||
        null;
      const status = (() => {
        const s = typeof obj.status === 'string' ? obj.status.toLowerCase() : '';
        if (s === 'resolved' || s === 'inactive') return 'resolved' as const;
        if (s === 'draft' || s === 'pending') return 'draft' as const;
        return 'active' as const;
      })();
      const detail =
        (typeof obj.detail === 'string' && obj.detail) ||
        (typeof obj.note === 'string' && obj.note) ||
        null;
      return { icd: code, name, status, detail };
    }
    return { icd: null, name: `Problem ${i + 1}`, status: 'active' as const, detail: null };
  });
}

function initialsOf(name: string | null | undefined): string {
  if (!name) return '·';
  return (
    name
      .split(/\s+/)
      .filter(Boolean)
      .slice(0, 2)
      .map((s) => s[0]?.toUpperCase() ?? '')
      .join('') || '·'
  );
}

function synthesizeAuditEvents(args: {
  createdAt?: string | null;
  processingStartedAt: string | null;
  processingFinishedAt: string | null;
  signedAt: string | null;
  signedByName?: string | null;
  doctorName?: string | null;
}): AuditEvent[] {
  const events: AuditEvent[] = [];
  const doctor = args.doctorName ?? args.signedByName ?? 'Doctor';
  const doctorInits = initialsOf(doctor);
  if (args.createdAt) {
    events.push({
      at: args.createdAt,
      actorInitials: doctorInits,
      actorName: doctor,
      verb: 'created visit',
      obj: null,
    });
  }
  if (args.processingStartedAt) {
    events.push({
      at: args.processingStartedAt,
      actorInitials: '·',
      actorName: 'System',
      system: true,
      verb: 'started processing pipeline',
      obj: null,
    });
  }
  if (args.processingFinishedAt) {
    events.push({
      at: args.processingFinishedAt,
      actorInitials: '·',
      actorName: 'System',
      system: true,
      verb: 'completed transcription + draft',
      obj: null,
    });
  }
  if (args.signedAt) {
    events.push({
      at: args.signedAt,
      actorInitials: initialsOf(args.signedByName ?? doctor),
      actorName: args.signedByName ?? doctor,
      verb: 'signed visit',
      obj: null,
    });
  }
  // Most-recent first
  return events.sort((a, b) => (a.at < b.at ? 1 : -1));
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
    // #315 obs#2: project the displayed E/M code so the "Copy codes"
    // clipboard prints what the doctor reviewed, not the raw L7b suggestion.
    em: projectEmForDisplay(cptBlob?.em ?? null, !!props.signedAt),
    procedures: cptBlob?.procedures ?? [],
    modifiers: cptBlob?.modifiers ?? [],
    prescriptions: rxBlob?.prescriptions ?? [],
    rxWarnings: rxBlob?.warnings ?? [],
    referrals: refBlob?.referrals ?? [],
    patientSummary: props.patientSummary,
    // Header fields + form-only are a STYLED-export (DOCX/PDF) concern, loaded
    // server-side in loadVisitExportData; the client clipboard/EHR path omits
    // them (the EHR already carries patient demographics).
    headerFields: [],
    formOnly: false,
    formTitle: null,
    formSignature: null,
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
            className="qm-tap-44"
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
// Phase 5.1 — the legacy inline TranscriptView (role-alternating bubbles
// for audio_upload visits) was extracted into ./transcript-tab.tsx as
// the V3 split-pane TranscriptTab. Voice-dictation and text-notes
// inputs still use the simple components further down.
// ---------------------------------------------------------------------------

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

// ---------------------------------------------------------------------------
// Phase 5.1 — pretty-print a duration in seconds for the Transcript V3
// metadata rail. Mirrors the "6m 04s" pattern from the mockup.
// ---------------------------------------------------------------------------
function formatDurationLabel(totalSec: number): string {
  const t = Math.max(0, Math.floor(totalSec));
  const m = Math.floor(t / 60);
  const s = (t % 60).toString().padStart(2, '0');
  return `${m}m ${s}s`;
}
