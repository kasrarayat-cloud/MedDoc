'use client';

// ============================================================================
// Template Twin — certify-once workspace (Stage 4). Flag-gated; rendered only
// when NEXT_PUBLIC_TEMPLATE_NATIVE_DOCX is ON.
// ----------------------------------------------------------------------------
// Upload your Word .docx ONCE → it compiles → you review the field mapping →
// certify. From then on every visit on that template fills + exports in your own
// document automatically. You never review per-note. Uncertified templates keep
// the standard styled export.
// ============================================================================

import { useRef, useState, useTransition } from 'react';

import {
  uploadNativeTemplateAction,
  certifyNativeTemplateAction,
} from '@/actions/template-twin-certify';
import {
  openNativeTemplateWorkspaceAction,
  updateTemplateTwinMappingsAction,
} from '@/actions/template-twin-mappings';
import type { TemplateTwinWorkspace } from '@/lib/template-twin/client-types';
import { REGISTRY_CONCEPTS } from '@/lib/template-twin/concept-registry';
import type { SemanticMapping } from '@/lib/template-twin/ir';

export interface NativeTemplateListItem {
  noteTemplateId: string;
  name: string;
  certificationStatus: string; // 'certified' | 'recognized' | 'needs_confirmation' | 'unsupported' | 'quarantined'
  fieldCount: number;
  version: number;
  /** RULING #127 — auto-certification is running for this twin. Derived and
   *  BOUNDED at the settings query; see its comment for why it is not stored. */
  preparing?: boolean;
}

const mono = 'var(--font-mono)';
const sans = 'var(--font-sans)';

type CertStatus =
  | 'certified'
  | 'recognized'
  | 'needs_confirmation'
  | 'unsupported'
  | 'quarantined';

const PILL_CLASS: Record<CertStatus, string> = {
  certified: 'qm-lin-pill qm-lin-pill--ready',
  recognized: 'qm-lin-pill',
  needs_confirmation: 'qm-lin-pill',
  unsupported: 'qm-lin-pill qm-lin-pill--review',
  quarantined: 'qm-lin-pill qm-lin-pill--review',
};
const PILL_LABEL: Record<CertStatus, string> = {
  certified: 'Certified',
  recognized: 'Draft',
  needs_confirmation: 'Needs review',
  unsupported: 'Unsupported',
  quarantined: 'Unsupported',
};

function StatusPill({ status }: { status: string }) {
  const s = (status in PILL_CLASS ? status : 'recognized') as CertStatus;
  return <span className={PILL_CLASS[s]}>{PILL_LABEL[s]}</span>;
}

export function NativeTemplateManager({
  existing,
  showUpload = true,
}: {
  existing: NativeTemplateListItem[];
  /** The selective fold. FALSE retires the upload ritual (Replace-on-the-row
   *  does that job) while keeping the CONFIRM surface, which is the half that
   *  has no other door. See `settings/page.tsx`. */
  showUpload?: boolean;
}) {
  const [workspace, setWorkspace] = useState<TemplateTwinWorkspace | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [certifiedName, setCertifiedName] = useState<string | null>(null);
  const [uploading, startUpload] = useTransition();
  const [certifying, startCertify] = useTransition();
  const [opening, startOpen] = useTransition();
  const fileRef = useRef<HTMLInputElement>(null);

  // THE READ DOOR'S CALLER. Without this the only route into a compiled
  // template was to upload the same file again — see the action's own header.
  function onOpen(noteTemplateId: string) {
    setError(null);
    setCertifiedName(null);
    startOpen(async () => {
      const res = await openNativeTemplateWorkspaceAction(noteTemplateId);
      if (res.ok) {
        setWorkspace(res.data);
      } else {
        setError(res.error);
        setWorkspace(null);
      }
    });
  }

  function onFile(file: File) {
    setError(null);
    setCertifiedName(null);
    const fd = new FormData();
    fd.append('file', file);
    startUpload(async () => {
      const res = await uploadNativeTemplateAction(fd);
      if (res.ok) {
        setWorkspace(res.data);
      } else {
        setError(res.error);
        setWorkspace(null);
      }
      if (fileRef.current) fileRef.current.value = '';
    });
  }

  function onCertify() {
    if (!workspace) return;
    setError(null);
    startCertify(async () => {
      const res = await certifyNativeTemplateAction(
        workspace.template.id,
        workspace.mappingsSha256,
      );
      if (res.ok) {
        setCertifiedName(res.data.template.name);
        setWorkspace(null);
      } else {
        setError(res.error);
      }
    });
  }

  const busy = uploading || certifying || opening;

  // ⚠️ FOLDED **AND** NOTHING TO CONFIRM → RENDER NOTHING. Under the simple row
  // the upload ritual is retired, so a doctor with no compiled template has no
  // action available here; a "Native template (beta)" heading over an empty box
  // is a section asserting a capability it is not offering. This is the one
  // case where the fold's original behaviour (null) is still the right answer.
  if (!showUpload && existing.length === 0 && !workspace && !certifiedName && !error) {
    return null;
  }

  return (
    <div
      style={{
        marginTop: 22,
        paddingTop: 18,
        borderTop: '1px solid var(--color-linear-hairline)',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
        <span
          style={{ fontFamily: sans, fontSize: 13, fontWeight: 500, color: 'var(--color-linear-text)' }}
        >
          Native template (beta)
        </span>
        <span className="qm-lin-pill">Opt-in</span>
      </div>
      <p
        style={{
          margin: '0 0 14px',
          fontFamily: sans,
          fontSize: 12.5,
          color: 'var(--color-linear-text-2)',
          lineHeight: 1.55,
          maxWidth: 620,
        }}
      >
        {/* The copy follows the fold. Telling a doctor to "upload your own Word
            template" where no upload control is rendered describes a door that
            is not there — the same illegibility this item exists to fix. */}
        {showUpload ? (
          <>
            Upload your own Word template with dropdowns and tables. You review the
            field mapping <strong>once</strong> and certify it; after that, every
            visit on this template comes back as your exact document, filled in — no
            per-note review. Until you certify, exports use the standard format.
          </>
        ) : (
          <>
            Your uploaded Word templates are prepared for native fill
            automatically. Confirm what each field means <strong>once</strong> and
            certify; after that, every visit on that template comes back as your
            exact document, filled in — no per-note review. Until you certify,
            exports use the standard format.
          </>
        )}
      </p>

      {/* Existing native templates */}
      {existing.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginBottom: 16 }}>
          {existing.map((t) => (
            <div
              key={t.noteTemplateId}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                gap: 12,
                padding: '9px 12px',
                borderRadius: 8,
                border: '1px solid var(--color-linear-border)',
                background: 'var(--color-linear-surface-1)',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, minWidth: 0 }}>
                <span
                  style={{
                    fontFamily: sans,
                    fontSize: 13,
                    color: 'var(--color-linear-text)',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                  }}
                >
                  {t.name}
                </span>
                <span style={{ fontFamily: mono, fontSize: 11, color: 'var(--color-linear-text-3)' }}>
                  {t.fieldCount} fields
                </span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0 }}>
                {/* ⚠️ RULING #127 — "Preparing your format…" REPLACES the pill
                    while auto-certification runs, because "Needs review" during
                    that window is FALSE and it is the exact false instruction
                    #713 was opened for: it sends a doctor to do work the system
                    is already doing. The state is bounded (see the settings
                    query), so it always resolves to something actionable. */}
                {t.preparing ? (
                  <span
                    className="qm-lin-pill"
                    data-testid={`twin-preparing-${t.noteTemplateId}`}
                    style={{ whiteSpace: 'nowrap' }}
                  >
                    Preparing your format…
                  </span>
                ) : (
                  <StatusPill status={t.certificationStatus} />
                )}
                <button
                  type="button"
                  className="qm-lin-btn qm-tap-44"
                  data-testid={`twin-open-workspace-${t.noteTemplateId}`}
                  disabled={busy}
                  onClick={() => onOpen(t.noteTemplateId)}
                  style={{ opacity: busy ? 0.55 : 1, whiteSpace: 'nowrap' }}
                >
                  {/* A CERTIFIED template is IMMUTABLE — the writer throws
                      IMMUTABLE on any edit. Saying "Review" rather than
                      "Confirm fields" is the honest label for a door that
                      opens onto a read-only record. */}
                  {t.certificationStatus === 'certified'
                    ? 'Review'
                    : t.preparing
                      ? 'Review anyway'
                      : 'Confirm fields'}
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Just-certified confirmation */}
      {certifiedName && (
        <div
          role="status"
          style={{
            padding: '11px 14px',
            borderRadius: 8,
            border: '1px solid var(--color-linear-sage-edge)',
            background: 'var(--color-linear-row-hover)',
            marginBottom: 14,
            fontFamily: sans,
            fontSize: 13,
            color: 'var(--color-linear-text)',
          }}
        >
          <strong>{certifiedName}</strong> is certified. New visits on this
          template will fill and export natively.
        </div>
      )}

      {/* Error */}
      {error && (
        <div
          role="alert"
          style={{
            padding: '11px 14px',
            borderRadius: 8,
            border: '1px solid color-mix(in srgb, var(--color-linear-coral) 35%, transparent)',
            background: 'color-mix(in srgb, var(--color-linear-coral) 6%, transparent)',
            marginBottom: 14,
            fontFamily: sans,
            fontSize: 12.5,
            color: 'var(--color-linear-text)',
            lineHeight: 1.5,
          }}
        >
          {error}
        </div>
      )}

      {/* Review workspace (post-upload, pre-certify) */}
      {workspace ? (
        <ReviewWorkspace
          /* ⚠️ THE KEY IS LOAD-BEARING, NOT COSMETIC. The confirm draft is
             seeded from the workspace, and `mappingsSha256` is exactly the
             identity of that seed — it is the optimistic-concurrency token the
             writer checks. Re-keying on it discards a draft the moment the
             server's mappings move, so a stale draft can never be re-submitted
             against a hash it was not built from. */
          key={workspace.mappingsSha256}
          workspace={workspace}
          certifying={certifying}
          onCertify={onCertify}
          onSaved={(next) => {
            setWorkspace(next);
            setError(null);
          }}
          onError={setError}
          onCancel={() => {
            setWorkspace(null);
            setError(null);
          }}
        />
      ) : !showUpload ? null : (
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
          <input
            ref={fileRef}
            type="file"
            accept=".docx"
            aria-label="Upload a Word .docx template to certify"
            disabled={busy}
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) onFile(f);
            }}
            style={{ display: 'none' }}
            id="native-template-file"
          />
          <label
            htmlFor="native-template-file"
            className="qm-lin-btn qm-tap-44"
            aria-disabled={busy}
            style={{
              cursor: busy ? 'not-allowed' : 'pointer',
              opacity: busy ? 0.55 : 1,
              display: 'inline-flex',
              alignItems: 'center',
              gap: 8,
            }}
          >
            {uploading ? 'Compiling…' : 'Upload .docx to certify'}
          </label>
          <span
            aria-live="polite"
            style={{ fontFamily: mono, fontSize: 11, color: 'var(--color-linear-text-3)' }}
          >
            {uploading ? 'Securing + compiling your template…' : '.docx, max 5 MB'}
          </span>
        </div>
      )}
    </div>
  );
}

// ============================================================================
// THE THREE CONFIRM CLASSES. Measured on the real customer form (80 fields):
// manual 5 · proposed 53 · unproposed 22. They are not cosmetic groupings —
// each names a DIFFERENT act by the doctor, and the readiness predicate in
// `certification-lifecycle.ts:598-618` treats them differently:
//
//   attest (sourceType 'manual', 5)  -> No concept exists to choose; nothing
//            can produce a value, so it renders blank and `fieldsReady` does
//            not ask for a concept.
//   confirm (53)  -> confirm or change. The compiler decided the concept from
//            the document's own structure (F5-a). A PROPOSAL is not a
//            confirmation — the doctor still has to say yes.
//   choose (sourceType 'verified_note_selection', 22)  -> Only the physician
//            can answer these. Never bulk-confirmable, WITH OR WITHOUT a
//            concept present: a guess at an enumerated dropdown is worse than
//            an empty one, and on production a guess is exactly what may be
//            sitting there.
// ============================================================================
// ⚠️ NAMED AFTER THE DOCTOR'S ACT, NOT AFTER THE DATA'S SHAPE — and that is a
// correction, not a preference. The first version classified on CONCEPT
// PRESENCE (`clinicalConcept ? 'proposed' : 'unproposed'`), which is right in
// the FALLBACK universe and WRONG in production's:
//
//   fallback (provider down, and every QA fixture)  -> the 22 enumerated picks
//                                                     carry clinicalConcept null
//   model proposer (production, provider up)        -> it MAY propose a concept
//                                                     for those same 22
//
// So on production a `verified_note_selection` field could arrive carrying a
// concept, classify as "proposed", and be swept by the bulk confirm — which is
// precisely the class the recorded design rule reserves for full per-field
// control. A model's guess at an enumerated dropdown is not a high-confidence
// mapping; it is the thing only the physician can answer.
//
// The discriminator is therefore STRUCTURAL (`sourceType`, set by
// `classifyFieldSource` from the field's kind and options) and never the
// presence of a concept.
type ConfirmClass = 'attest' | 'confirm' | 'choose';

// ⚠️ EXPORTED FOR ITS OWN TEST, AND THAT IS NOT A STYLE CHOICE. A mutation
// proof replacing the ternary in `confirmed()` with an unconditional
// `clinicalConcept: concept` left all 17 UI arms GREEN — because the attest
// button passes `m.clinicalConcept` as `concept`, so both versions compute the
// same value through every route the UI offers. The branch is a real guard
// against a future edit that gives manual fields a picker, and it was
// UNOBSERVABLE. Testing the pure function directly is what makes it fire.
export function confirmClassOf(mapping: SemanticMapping): ConfirmClass {
  if (mapping.sourceType === 'manual') return 'attest';
  // ⚠️ STRUCTURAL, AND IT OUTRANKS CONCEPT PRESENCE. An enumerated pick stays
  // the doctor's to answer even when the model proposer has already put a
  // concept in the box.
  if (mapping.sourceType === 'verified_note_selection') return 'choose';
  return mapping.clinicalConcept ? 'confirm' : 'choose';
}

/** The doctor's confirmation, applied. Mirrors `fieldsReady`'s two demands:
 *  a concept (except manual) and `status === 'certified'`. Nothing else moves —
 *  in particular `practiceDefault` is never written, because the writer refuses
 *  a non-null one outright until the flagged-review lane exists. */
export function confirmed(mapping: SemanticMapping, concept: string | null): SemanticMapping {
  return {
    ...mapping,
    clinicalConcept: mapping.sourceType === 'manual' ? mapping.clinicalConcept : concept,
    status: 'certified',
  };
}

function ReviewWorkspace({
  workspace,
  certifying,
  onCertify,
  onCancel,
  onSaved,
  onError,
}: {
  workspace: TemplateTwinWorkspace;
  certifying: boolean;
  onCertify: () => void;
  onCancel: () => void;
  onSaved: (next: TemplateTwinWorkspace) => void;
  onError: (message: string) => void;
}) {
  const fields = workspace.fields;
  const [draft, setDraft] = useState<SemanticMapping[]>(() =>
    fields.map((f) => f.mapping),
  );
  const [saving, startSave] = useTransition();
  const draftById = new Map(draft.map((m) => [m.fieldId, m]));
  const readOnly = !workspace.canEdit || workspace.template.certificationStatus === 'certified';

  function setMapping(fieldId: string, next: SemanticMapping) {
    setDraft((prev) => prev.map((m) => (m.fieldId === fieldId ? next : m)));
  }

  // ⚠️ THE WRITER DEMANDS THE EXACT COMPILER FIELD SET (`FIELD_SET_MISMATCH`,
  // certification-lifecycle.ts:413-421) — every field, once, no additions. So
  // the whole draft goes every time; there is no partial submit to get wrong.
  function onSave() {
    startSave(async () => {
      const res = await updateTemplateTwinMappingsAction(
        workspace.template.id,
        workspace.mappingsSha256,
        draft,
      );
      if (res.ok) onSaved(res.data);
      else onError(res.error);
    });
  }

  const unconfirmed = draft.filter((m) => m.status !== 'certified');
  // A field the doctor has confirmed in this draft but which still has no
  // concept cannot be saved as certified — the writer throws MAPPING_INVALID.
  // Surfacing it here means the refusal is legible before the round trip.
  const incomplete = draft.filter(
    (m) => m.status === 'certified' && !m.clinicalConcept && m.sourceType !== 'manual',
  );
  const dirty = draft.some((m, i) => m !== fields[i]?.mapping);
  const proposedPending = unconfirmed.filter((m) => confirmClassOf(m) === 'confirm');
  const byStatus = fields.reduce<Record<string, number>>((acc, f) => {
    const s = f.field.detectionStatus;
    acc[s] = (acc[s] ?? 0) + 1;
    return acc;
  }, {});
  const blockingUnsupported = workspace.unsupported.filter((u) => u.blocksCertification);
  const canCertify = workspace.template.certificationStatus !== 'unsupported' &&
    blockingUnsupported.length === 0;

  return (
    <div
      style={{
        border: '1px solid var(--color-linear-border)',
        borderRadius: 10,
        overflow: 'hidden',
        background: 'var(--color-linear-surface-1)',
      }}
    >
      <div
        style={{
          padding: '13px 16px',
          borderBottom: '1px solid var(--color-linear-hairline)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 12,
          flexWrap: 'wrap',
        }}
      >
        <div>
          <div style={{ fontFamily: sans, fontSize: 14, fontWeight: 500, color: 'var(--color-linear-text)' }}>
            {workspace.template.name}
          </div>
          <div style={{ fontFamily: mono, fontSize: 11, color: 'var(--color-linear-text-3)', marginTop: 3 }}>
            {fields.length} fields · {workspace.stats.dropdowns} dropdowns · {workspace.stats.tables} table
            {workspace.stats.tables === 1 ? '' : 's'}
          </div>
        </div>
        <StatusPill status={workspace.template.certificationStatus} />
      </div>

      {/* WHY it is not certified — and therefore why exports still come back in
          the QuillMD layout rather than the doctor's own document.
          The pill alone said "Needs review" without saying review of WHAT, and
          the export silently degraded to styled, so the two facts never met.
          Anything short of certified states the blocker in the doctor's terms
          and offers the action that clears it. */}
      {workspace.template.certificationStatus !== 'certified' && (
        <div
          style={{
            padding: '11px 16px',
            borderBottom: '1px solid var(--color-linear-hairline)',
            background: 'color-mix(in srgb, var(--color-linear-amber) 8%, transparent)',
            fontFamily: sans,
            fontSize: 12.5,
            lineHeight: 1.5,
            color: 'var(--color-linear-text-2)',
          }}
          data-testid="twin-not-certified-reason"
        >
          <strong style={{ color: 'var(--color-linear-text)' }}>
            Exports use the QuillMD layout until this form is confirmed.
          </strong>{' '}
          {blockingUnsupported.length > 0
            ? `${blockingUnsupported.length} element${blockingUnsupported.length === 1 ? '' : 's'} in this document can't be filled safely, so it can't be certified as-is.`
            : (byStatus.needs_confirmation ?? 0) > 0
              ? `${byStatus.needs_confirmation} of ${fields.length} fields still need a quick confirmation of what they mean.`
              : 'Run the sample check below to confirm the filled document matches your form.'}
        </div>
      )}

      {/* Detection summary */}
      <div
        style={{
          padding: '12px 16px',
          display: 'flex',
          gap: 18,
          flexWrap: 'wrap',
          borderBottom: '1px solid var(--color-linear-hairline)',
        }}
      >
        {(['recognized', 'needs_confirmation', 'certified', 'unsupported'] as const).map((s) =>
          byStatus[s] ? (
            <div key={s} style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
              <span style={{ fontFamily: mono, fontSize: 18, color: 'var(--color-linear-text)' }}>
                {byStatus[s]}
              </span>
              <span style={{ fontFamily: mono, fontSize: 10.5, letterSpacing: '0.05em', textTransform: 'uppercase', color: 'var(--color-linear-text-3)' }}>
                {s.replace('_', ' ')}
              </span>
            </div>
          ) : null,
        )}
      </div>

      {/* Bulk confirm for the PROPOSED class only — the recorded design rule is
          "cheap confirms for high-confidence mappings, full control retained,
          WITHOUT weakening per-field confirmation".
          ⚠️ It is deliberately NOT offered for the unproposed class. A button
          that confirmed those would be confirming nothing — they have no
          concept to agree with — and it would satisfy `fieldsReady` by
          certifying fields no physician had actually read. */}
      {!readOnly && proposedPending.length > 0 && (
        <div
          style={{
            padding: '10px 16px',
            borderBottom: '1px solid var(--color-linear-hairline)',
            display: 'flex',
            alignItems: 'center',
            gap: 10,
            flexWrap: 'wrap',
          }}
        >
          <button
            type="button"
            className="qm-lin-btn qm-tap-44"
            data-testid="twin-confirm-all-proposed"
            disabled={saving}
            onClick={() =>
              setDraft((prev) =>
                prev.map((m) =>
                  m.status !== 'certified' && confirmClassOf(m) === 'confirm'
                    ? confirmed(m, m.clinicalConcept)
                    : m,
                ),
              )
            }
          >
            Confirm all {proposedPending.length} proposed
          </button>
          <span style={{ fontFamily: mono, fontSize: 11, color: 'var(--color-linear-text-3)' }}>
            these carry a concept the form itself determines — change any below
          </span>
        </div>
      )}

      {/* Field mapping list (scrollable) */}
      <div style={{ maxHeight: 320, overflowY: 'auto' }} role="list" aria-label="Field mapping proposal">
        {fields.map((f) => {
          const m = draftById.get(f.mapping.fieldId) ?? f.mapping;
          const klass = confirmClassOf(m);
          const isConfirmed = m.status === 'certified';
          return (
            <div
              key={f.definitionId}
              role="listitem"
              data-testid={`twin-field-row-${m.fieldId}`}
              data-confirm-class={klass}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                gap: 12,
                padding: '8px 16px',
                borderBottom: '1px solid var(--color-linear-hairline)',
              }}
            >
              <div style={{ minWidth: 0 }}>
                <div
                  style={{
                    fontFamily: sans,
                    fontSize: 12.5,
                    color: 'var(--color-linear-text)',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                  }}
                >
                  {f.field.originalLabel}
                </div>
                <div style={{ fontFamily: mono, fontSize: 10.5, color: 'var(--color-linear-text-3)', marginTop: 2 }}>
                  {f.field.kind.replace('_', ' ')}
                  {klass === 'attest'
                    ? ' · filled by hand each visit'
                    : m.clinicalConcept
                      ? ` → ${m.clinicalConcept}`
                      : ' · no concept yet'}
                </div>
                {/* ⚠️ #193 — THE KEEP OFFER IS SHOWN WITH ITS SENTENCE, AND
                    WITHOUT THIS THE RULING'S SAFETY IS UNDELIVERABLE. The
                    ruling routes a keep to a HUMAN precisely because printing
                    template prose on a signed note is a clinical assertion no
                    automated step may make. Round two measured this screen
                    rendering NEITHER the policy NOR the sentence — zero hits
                    for `unmentionedPolicy` or `scaffoldText` in any .tsx — so
                    `confirmed()` carried the keep through on the same click
                    that confirmed the CONCEPT. A doctor authorised text they
                    had never been shown: consent theatre rather than consent.
                    The sentence is quoted verbatim, because "this field keeps
                    its default" is not a thing anyone can evaluate. */}
                {m.unmentionedPolicy === 'keep' && (
                  <div
                    data-testid={`twin-keep-offer-${m.fieldId}`}
                    style={{
                      fontFamily: sans,
                      fontSize: 10.5,
                      color: 'var(--color-linear-text-2)',
                      marginTop: 3,
                      whiteSpace: 'normal',
                    }}
                  >
                    Keeps your template’s own wording when nothing is dictated:{' '}
                    <span style={{ fontFamily: mono }}>
                      “{f.field.scaffoldText ?? '(no default text compiled)'}”
                    </span>
                  </div>
                )}
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0 }}>
                {/* The CHOOSE control, for the class only a physician can
                    answer. Rendered for proposed fields too, because "confirm
                    or CHANGE" is the recorded rule — a proposal the doctor
                    disagrees with must be correctable in place. */}
                {!readOnly && klass !== 'attest' && (
                  <select
                    aria-label={`Clinical concept for ${f.field.originalLabel}`}
                    data-testid={`twin-concept-select-${m.fieldId}`}
                    disabled={saving}
                    value={m.clinicalConcept ?? ''}
                    onChange={(e) => {
                      const concept = e.target.value || null;
                      // ⚠️ CHANGING A CONCEPT UN-CONFIRMS THE FIELD. The
                      // doctor confirmed the OLD concept; carrying the
                      // certified status across would certify a value nobody
                      // agreed to — the mapping's status is a statement about
                      // the concept beside it, not about the row.
                      setMapping(m.fieldId, { ...m, clinicalConcept: concept, status: 'needs_confirmation' });
                    }}
                    style={{
                      fontFamily: mono,
                      fontSize: 11,
                      maxWidth: 190,
                      padding: '4px 6px',
                      borderRadius: 6,
                      border: '1px solid var(--color-linear-border)',
                      background: 'var(--color-linear-surface-1)',
                      color: 'var(--color-linear-text)',
                    }}
                  >
                    <option value="">— choose a concept —</option>
                    {REGISTRY_CONCEPTS.map((c) => (
                      <option key={c} value={c}>
                        {c}
                      </option>
                    ))}
                    {/* The compiler can decide PATTERNED concepts
                        (`exam.*`, `test.*.result`) that are registry-legal but
                        not enumerable. Keeping the current value selectable
                        means opening the picker cannot silently drop one. */}
                    {m.clinicalConcept && !REGISTRY_CONCEPTS.includes(m.clinicalConcept) && (
                      <option value={m.clinicalConcept}>{m.clinicalConcept}</option>
                    )}
                  </select>
                )}

                {isConfirmed ? (
                  <span className="qm-lin-pill qm-lin-pill--ready">Confirmed</span>
                ) : readOnly ? (
                  <span className="qm-lin-pill">{m.status.replace('_', ' ')}</span>
                ) : (
                  <button
                    type="button"
                    className="qm-lin-btn qm-tap-44"
                    data-testid={`twin-confirm-field-${m.fieldId}`}
                    // A field with no concept cannot be confirmed — except a
                    // MANUAL one, which is attested and has no concept by
                    // construction. Same carve-out `fieldsReady` makes.
                    disabled={saving || (klass !== 'attest' && !m.clinicalConcept)}
                    onClick={() => setMapping(m.fieldId, confirmed(m, m.clinicalConcept))}
                    style={{ whiteSpace: 'nowrap' }}
                  >
                    {klass === 'attest' ? 'Attest' : 'Confirm'}
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Save — the write half. Separate from Certify DELIBERATELY: confirming
          mappings and certifying the template are two different acts, and
          `updateTemplateTwinMappings` refuses outright once a version is
          certified (IMMUTABLE). */}
      {!readOnly && (
        <div
          style={{
            padding: '11px 16px',
            borderTop: '1px solid var(--color-linear-hairline)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 10,
            flexWrap: 'wrap',
          }}
        >
          <span
            aria-live="polite"
            style={{ fontFamily: mono, fontSize: 11, color: 'var(--color-linear-text-3)' }}
          >
            {incomplete.length > 0
              ? `${incomplete.length} confirmed field${incomplete.length === 1 ? '' : 's'} still need a concept`
              : `${unconfirmed.length} of ${draft.length} still to confirm`}
          </span>
          <button
            type="button"
            className="qm-lin-btn qm-tap-44"
            data-testid="twin-save-mappings"
            disabled={saving || !dirty || incomplete.length > 0}
            onClick={onSave}
            style={{ opacity: saving || !dirty || incomplete.length > 0 ? 0.5 : 1 }}
          >
            {saving ? 'Saving…' : 'Save confirmations'}
          </button>
        </div>
      )}

      {blockingUnsupported.length > 0 && (
        <div
          style={{
            padding: '11px 16px',
            fontFamily: sans,
            fontSize: 12,
            color: 'var(--color-linear-coral)',
            borderTop: '1px solid var(--color-linear-hairline)',
          }}
        >
          {blockingUnsupported.length} element{blockingUnsupported.length === 1 ? '' : 's'} can&apos;t be
          safely reproduced and block certification. Simplify the template in Word and re-upload.
          {/*
            ⚠️ #175(2) — THE REFUSAL NAMES ITSELF. Until now this block rendered
            a COUNT and nothing else, while the compiler's finding — the
            control's label and the reason it was refused — sat unused in the
            payload. A doctor was told "simplify the template in Word" without
            being told WHICH control, which is a refusal that cannot be acted
            on. Listed from `unsupported`, never from `fields`: a refused
            control is deliberately absent from the field list, which is exactly
            why the count was all the old chrome could reach.
          */}
          <ul
            data-testid="twin-unsupported-findings"
            style={{ margin: '8px 0 0', paddingLeft: 18, listStyle: 'disc' }}
          >
            {blockingUnsupported.map((finding, index) => (
              <li
                key={`${finding.partName}\u0000${finding.path}\u0000${finding.code}`}
                data-testid="twin-unsupported-finding"
                style={{ marginTop: index === 0 ? 0 : 4 }}
              >
                <strong style={{ color: 'var(--color-linear-text)' }}>
                  {finding.label ?? 'Unnamed control'}
                </strong>{' '}
                — {finding.detail} Simplify this control in Word.
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Certify actions */}
      <div
        style={{
          padding: '13px 16px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'flex-end',
          gap: 10,
          borderTop: '1px solid var(--color-linear-hairline)',
        }}
      >
        <button type="button" className="qm-lin-btn qm-tap-44" onClick={onCancel} disabled={certifying}>
          Cancel
        </button>
        <button
          type="button"
          className="qm-lin-btn qm-tap-44"
          onClick={onCertify}
          disabled={certifying || !canCertify}
          title={canCertify ? 'Certify this mapping — fills every future visit' : 'Resolve blocking elements first'}
          style={{
            opacity: canCertify ? 1 : 0.5,
            background: 'var(--color-linear-sage)',
            borderColor: 'var(--color-linear-sage)',
            color: 'var(--color-linear-on-sage)',
            fontWeight: 500,
          }}
        >
          {certifying ? 'Verifying & certifying…' : 'Certify & activate'}
        </button>
      </div>
    </div>
  );
}
