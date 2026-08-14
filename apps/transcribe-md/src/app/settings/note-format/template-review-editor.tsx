'use client';

// ============================================================================
// Note-format customization — Phase 2b: review / edit a parsed (or existing)
// template, then Save as draft / Save & activate.
// ----------------------------------------------------------------------------
// Mirrors docs/design-directions-v9-note-format/3-review.html using the live
// Linear V1 tokens (inline style + --color-linear-*, the settings convention).
// The default-text SAFETY callout + the per-default scaffold microcopy are
// non-optional. The right column shows a LIVE sample note generated in the
// doctor's format from a fixed SYNTHETIC demo visit (SamplePreview) — it
// degrades to a structural outline on failure and NEVER blocks save. The save
// payload is stripped to the strict schema shape (no defaultTextMode — the
// server coerces it to scaffold_confirm).
// ============================================================================

import { useEffect, useMemo, useRef, useState, useTransition } from 'react';
import { toast } from 'sonner';

import { SPECIALTIES, SPECIALTY_IDS, visibleSpecialties } from '@meddoc/shared/specialties';
import {
  saveNoteTemplateAction,
} from '@/actions/note-template-lifecycle';
import { previewNoteTemplateAction } from '@/actions/preview-note-template';
import { detectContextFields } from '@/lib/note-template-context';
import type {
  NoteTemplateSection,
  SectionFormatHint,
} from '@/lib/note-template-parse/note-template-schema';
import type { TemplateReviewModel } from '@/lib/note-template-persist/types';

// ── tokens-as-style helpers (settings convention) ───────────────────────────
const mono = 'var(--font-mono)';
const sans = 'var(--font-sans)';
const subLabel: React.CSSProperties = {
  fontFamily: mono,
  fontSize: 9.5,
  letterSpacing: '0.06em',
  textTransform: 'uppercase',
  color: 'var(--color-linear-text-3)',
  marginBottom: 5,
};
const input: React.CSSProperties = {
  width: '100%',
  height: 32,
  padding: '0 10px',
  background: 'var(--color-linear-surface-2)',
  border: '1px solid var(--color-linear-border)',
  borderRadius: 6,
  color: 'var(--color-linear-text)',
  fontFamily: sans,
  fontSize: 13,
  outline: 'none',
};
const textarea: React.CSSProperties = {
  ...input,
  height: 'auto',
  minHeight: 64,
  padding: '8px 10px',
  lineHeight: 1.5,
  resize: 'vertical',
};
const btn: React.CSSProperties = {
  display: 'inline-flex',
  alignItems: 'center',
  justifyContent: 'center',
  gap: 6,
  padding: '6px 12px',
  borderRadius: 6,
  fontSize: 12,
  fontWeight: 500,
  fontFamily: sans,
  cursor: 'pointer',
  background: 'transparent',
  color: 'var(--color-linear-text-2)',
  border: '1px solid var(--color-linear-border)',
};
// C1-f: `color` and the ring were literals — see note-format-manager.tsx. This
// is the "Save & activate" button, and it sits inside `.qm-tpl-actionbar`,
// which shielded it from the axe gate as well as from the bridge.
const btnPrimary: React.CSSProperties = {
  ...btn,
  background: 'var(--color-linear-sage)',
  color: 'var(--color-linear-on-sage)',
  border: 'none',
  boxShadow: '0 0 0 1px var(--color-linear-sage-ring)',
};

const FORMATS: { value: SectionFormatHint; label: string }[] = [
  { value: 'prose', label: 'Prose' },
  { value: 'bullets', label: 'Bullets' },
  { value: 'numbered', label: 'Numbered' },
];

// Encounter options: catch-all (null) + the live specialty taxonomy the worker
// matches against (visit.specialty). 'unspecified' is dropped — null IS the
// "applies to everything" choice.
const ENCOUNTER_OPTIONS: { value: string; label: string }[] = [
  { value: '', label: 'All my visits' },
  // flag-aware: Ultrasound appears only when NEXT_PUBLIC_ULTRASOUND_SPECIALTY
  // is on; forVisitCreate drops 'unspecified' (null IS "applies to everything").
  ...visibleSpecialties({ forVisitCreate: true }).map((s) => ({
    value: s.id,
    label: s.label,
  })),
];

interface EditableSection extends NoteTemplateSection {
  _uid: string;
  _open: boolean;
}

let uidSeq = 0;
function toEditable(s: NoteTemplateSection): EditableSection {
  return { ...s, _uid: `s${uidSeq++}`, _open: !!s.defaultText };
}

export interface TemplateReviewEditorProps {
  initial: TemplateReviewModel;
  parseFlags?: string[];
  /**
   * RC-2 (#106(b)) — the reference to the doctor's ORIGINAL uploaded .docx,
   * when this editor was opened on a fresh upload.
   *
   * ⚠️ THIS PROP EXISTS BECAUSE THERE ARE TWO SAVE CALLERS, NOT ONE. The confirm
   * card and this editor build their payloads INDEPENDENTLY, so threading the
   * ref through the confirm path alone would leave every Advanced-path save
   * silently dropping it — the doctor takes the one route that offers more
   * control and loses their file for it. That is R3.4's "coverage assumed"
   * shape: wire one caller, verify it there, correctly and incompletely.
   *
   * Optional and absent on an EDIT of an existing template, where the server
   * carries the ref forward from the stored row and never trusts the client.
   */
  source?: { objectKey: string; sha256: string } | null;
  onCancel: () => void;
  onSaved: (status: 'draft' | 'active') => void;
}

export function TemplateReviewEditor({
  initial,
  parseFlags = [],
  source = null,
  onCancel,
  onSaved,
}: TemplateReviewEditorProps) {
  const [name, setName] = useState(initial.name);
  // The parse LLM emits a free-text encounterType ("Follow-up progress note")
  // that matches no <option>; the browser would DISPLAY "All my visits" while
  // the state kept the free text — saving a template the resolver can never
  // match against visit.specialty (silently inert). Coerce anything outside
  // the FULL static catalog to the catch-all so what the doctor sees is what
  // gets saved. Valid-but-flag-hidden slugs (an ultrasound-scoped template
  // opened in a flag-off build) are KEPT — never silently widened to
  // "All my visits" — and surfaced as an extra option so display = state.
  const [encounterType, setEncounterType] = useState<string>(() => {
    const parsed = initial.encounterType ?? '';
    return (SPECIALTY_IDS as readonly string[]).includes(parsed) ? parsed : '';
  });
  const encounterOptions = useMemo(() => {
    if (!encounterType || ENCOUNTER_OPTIONS.some((o) => o.value === encounterType)) {
      return ENCOUNTER_OPTIONS;
    }
    const label = SPECIALTIES.find((s) => s.id === encounterType)?.label ?? encounterType;
    return [...ENCOUNTER_OPTIONS, { value: encounterType, label }];
  }, [encounterType]);
  const [sections, setSections] = useState<EditableSection[]>(() =>
    [...initial.sections].sort((a, b) => a.order - b.order).map(toEditable),
  );
  const [flags, setFlags] = useState<string[]>(parseFlags);
  const [pending, startTransition] = useTransition();

  // styleProfile (tense/tone/abbreviations) carries through unchanged — no
  // dedicated UI in CORE; the immutable safety layer is never here regardless.
  const styleProfile = initial.styleProfile;

  // Context-field defaults (feat/template-context-defaults): the never-dictated
  // dropdowns (clinic / referring physician / machine / location) fill from
  // these per-doctor picks at generation, deterministically — the AI never
  // touches them. Sonographer is per-visit (no default). Detected live from the
  // parsed section dropdowns; a default may only be one of the field's own
  // options.
  const contextFields = useMemo(
    () => detectContextFields(sections),
    [sections],
  );
  // feat/form-only-export: per-template preference — when ON, the exported DOCX/
  // styled-PDF renders ONLY the doctor's form (no QuillMD chrome, no appended
  // coding/summary blocks). In-app review + the standard export are unchanged.
  const [formOnlyExport, setFormOnlyExport] = useState<boolean>(
    styleProfile.formOnlyExport ?? false
  );
  const [contextDefaults, setContextDefaults] = useState<Record<string, string>>(
    () => ({ ...(styleProfile.contextDefaults ?? {}) }),
  );
  const setContextDefault = (key: string, value: string) =>
    setContextDefaults((prev) => {
      const next = { ...prev };
      if (value) next[key] = value;
      else delete next[key];
      return next;
    });

  function patch(uid: string, next: Partial<EditableSection>) {
    setSections((prev) => prev.map((s) => (s._uid === uid ? { ...s, ...next } : s)));
  }
  function move(uid: string, dir: -1 | 1) {
    setSections((prev) => {
      const i = prev.findIndex((s) => s._uid === uid);
      const j = i + dir;
      if (i < 0 || j < 0 || j >= prev.length) return prev;
      const next = [...prev];
      [next[i], next[j]] = [next[j], next[i]];
      return next;
    });
  }
  function removeSection(uid: string) {
    setSections((prev) => (prev.length <= 1 ? prev : prev.filter((s) => s._uid !== uid)));
  }
  function addSection() {
    setSections((prev) => [
      ...prev,
      toEditable({
        key: `section_${prev.length + 1}`,
        label: 'New section',
        order: prev.length + 1,
        formatHint: 'prose',
        styleInstructions: null,
        defaultText: null,
        defaultTextMode: 'omit_unless_supported',
      }),
    ]);
  }

  function buildPayload() {
    // Strip to the STRICT schema shape: no defaultTextMode (server coerces),
    // no _uid/_open. order is re-derived from position.
    return {
      ...(initial.id ? { id: initial.id } : {}),
      // Carried verbatim; the server validates it against the caller's own
      // practice before any write. Omitted when absent — the schema is
      // .strict() and  is not a value here.
      ...(source ? { source } : {}),
      name: name.trim(),
      encounterType: encounterType ? encounterType : null,
      sections: sections.map((s, i) => ({
        key: s.key,
        label: s.label.trim() || 'Section',
        order: i + 1,
        formatHint: s.formatHint,
        styleInstructions: s.styleInstructions,
        defaultText: s.defaultText,
        // feat/structured-templates: tables/option-sets round-trip verbatim
        // (read-only in v1 — parsed structure is displayed, not edited).
        structure: s.structure ?? null,
      })),
      styleProfile: {
        tense: styleProfile.tense,
        tone: styleProfile.tone,
        abbreviations: styleProfile.abbreviations,
        // Only keep defaults for the NON-per-visit context fields the current
        // template actually has (drop stale keys if the template changed).
        contextDefaults: (() => {
          const keys = new Set(contextFields.filter((f) => !f.perVisit).map((f) => f.key));
          const out: Record<string, string> = {};
          for (const [k, v] of Object.entries(contextDefaults)) if (keys.has(k) && v) out[k] = v;
          return Object.keys(out).length > 0 ? out : null;
        })(),
        // feat/template-header-fields: parsed header fields + form-only pref
        // round-trip READ-ONLY (v1 — no editor UI). The server re-derives keys +
        // re-PHI-scans on save, so this is a pure passthrough.
        headerFields: styleProfile.headerFields ?? null,
        formOnlyExport,
      },
    };
  }

  function save(activate: boolean) {
    if (!name.trim()) {
      toast.error('Give your format a name');
      return;
    }
    startTransition(async () => {
      const res = await saveNoteTemplateAction(buildPayload(), activate);
      if (res.ok) {
        toast.success(
          activate ? 'Format activated' : 'Draft saved',
          {
            description: activate
              ? 'New visits that match will be written in this format.'
              : 'Saved as a draft — activate it when you’re ready.',
          },
        );
        if (res.flags.length > 0) {
          toast.message('A couple of defaults were tidied', {
            description: res.flags[0],
          });
        }
        onSaved(res.status);
      } else {
        toast.error('Could not save', { description: res.error });
      }
    });
  }

  const defaultCount = useMemo(
    () => sections.filter((s) => !!s.defaultText?.trim()).length,
    [sections],
  );

  return (
    /* C1-f — the ownership anchor. Every node in this 927-line file is
       classless, so `ownedByDom` walked past all of them and halted on
       `.qm-c3-set-content`: not a Rounds class, so every violation in the
       densest file in C1 filed as "inherited" and none could block. One class
       here makes the whole subtree measurable. It also lifts the faintest text
       tiers, which the section cards and the structure outline write over a
       surface-2 ground (4.18:1 before, 5.97:1 after). */
    <div className="qm-rounds-tmpl-editor">
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 16, flexWrap: 'wrap' }}>
        <div>
          <div style={{ ...subLabel, marginBottom: 6 }}>Review the parsed format</div>
          <div style={{ fontSize: 18, fontWeight: 500, letterSpacing: '-0.012em', color: 'var(--color-linear-text)' }}>
            Here’s the format I understood — edit anything.
          </div>
        </div>
        <button type="button" style={btn} onClick={onCancel} disabled={pending}>Cancel</button>
      </div>

      {/* Name + encounter type */}
      <div style={{ display: 'grid', gridTemplateColumns: '1.4fr 1fr', gap: 14, margin: '16px 0 4px' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <label style={subLabel} htmlFor="nf-name">Template name</label>
          <input id="nf-name" style={input} value={name} onChange={(e) => setName(e.target.value)} maxLength={120} />
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <label style={subLabel} htmlFor="nf-enc">Use for</label>
          <select
            id="nf-enc"
            style={{ ...input, appearance: 'auto' }}
            value={encounterType}
            onChange={(e) => setEncounterType(e.target.value)}
          >
            {encounterOptions.map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
        </div>
      </div>
      <p style={{ fontSize: 11.5, color: 'var(--color-linear-text-3)', margin: '2px 0 0', lineHeight: 1.5 }}>
        QuillMD uses this format for visits whose specialty matches. “All my visits” applies it to every note that
        doesn’t have a more specific match.
      </p>

      {/* DEFAULT-TEXT SAFETY CALLOUT (verbatim, non-optional) */}
      <SafetyCallout />

      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0,1fr) minmax(0,400px)', gap: 16, marginTop: 16 }}>
        {/* LEFT — editor */}
        <div>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
            <span style={subLabel}>Sections · use ▲▼ to reorder</span>
            <span style={{ fontSize: 11.5, color: 'var(--color-linear-text-3)' }}>
              {sections.length} section{sections.length === 1 ? '' : 's'}
            </span>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {sections.map((s, i) => (
              <SectionCard
                key={s._uid}
                section={s}
                isFirst={i === 0}
                isLast={i === sections.length - 1}
                onPatch={(next) => patch(s._uid, next)}
                onMove={(dir) => move(s._uid, dir)}
                onRemove={() => removeSection(s._uid)}
                canRemove={sections.length > 1}
              />
            ))}
          </div>

          <button type="button" style={{ ...btn, marginTop: 10 }} onClick={addSection}>
            + Add a section
          </button>

          {/* Context defaults — never-dictated dropdowns filled from your
              settings, not the AI (feat/template-context-defaults). */}
          {contextFields.length > 0 && (
            <div style={{ marginTop: 22 }}>
              <div style={{ ...subLabel, marginBottom: 4 }}>Context fields — filled from your settings, never from the recording</div>
              <p style={{ fontSize: 11.5, color: 'var(--color-linear-text-3)', margin: '0 0 10px', lineHeight: 1.5 }}>
                These never come from what you say. Pick a default for each; it fills automatically on every note. Sonographer changes per visit, so it stays blank for you to complete in the note.
              </p>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                {contextFields.map((f) => (
                  <div key={f.key} style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
                    <label style={subLabel} htmlFor={`ctx-${f.key}`}>{f.fieldLabel}</label>
                    {f.perVisit ? (
                      <div style={{ ...input, display: 'flex', alignItems: 'center', color: 'var(--color-linear-text-3)', fontStyle: 'italic' }}>
                        Per visit — you complete this in the note
                      </div>
                    ) : (
                      <select
                        id={`ctx-${f.key}`}
                        style={{ ...input, appearance: 'auto' }}
                        value={contextDefaults[f.key] ?? ''}
                        onChange={(e) => setContextDefault(f.key, e.target.value)}
                      >
                        <option value="">Leave blank ([not documented])</option>
                        {f.options.map((o) => (
                          <option key={o} value={o}>{o}</option>
                        ))}
                      </select>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Opt-in suggestions (nothing pre-filled) */}
          {flags.length > 0 && (
            <div style={{ marginTop: 22 }}>
              <div style={{ ...subLabel, marginBottom: 9 }}>
                Suggestions — you opt in by editing the sections yourself; nothing was pre-filled
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {flags.map((f, idx) => (
                  <div
                    key={idx}
                    style={{
                      display: 'grid',
                      gridTemplateColumns: '1fr auto',
                      gap: 11,
                      alignItems: 'center',
                      padding: '11px 13px',
                      border: '1px solid var(--color-linear-sage-edge-soft)',
                      borderRadius: 9,
                      background: 'var(--color-linear-sage-tint)',
                    }}
                  >
                    <div style={{ fontSize: 12, color: 'var(--color-linear-text-2)', lineHeight: 1.5 }}>{f}</div>
                    <button
                      type="button"
                      style={btn}
                      onClick={() => setFlags((prev) => prev.filter((_, j) => j !== idx))}
                      aria-label={`Dismiss suggestion: ${f}`}
                    >
                      Dismiss
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* RIGHT — live sample note generated in the doctor's format (synthetic) */}
        <SamplePreview sections={sections} getPayload={buildPayload} />
      </div>

      {/* Form-only export toggle (feat/form-only-export) */}
      <label
        style={{
          display: 'flex',
          alignItems: 'flex-start',
          gap: 10,
          marginTop: 16,
          padding: '12px 14px',
          borderRadius: 8,
          border: '1px solid var(--color-linear-border)',
          background: 'var(--color-linear-surface-2)',
          cursor: 'pointer',
        }}
      >
        <input
          type="checkbox"
          checked={formOnlyExport}
          onChange={(e) => setFormOnlyExport(e.target.checked)}
          style={{ marginTop: 2, accentColor: 'var(--color-linear-sage)' }}
        />
        <span style={{ fontSize: 13, color: 'var(--color-linear-text)', lineHeight: 1.5 }}>
          Form-only export
          <span style={{ display: 'block', fontSize: 12, color: 'var(--color-linear-text-3)', marginTop: 2 }}>
            Exported Word/PDF documents contain only your form — its title, header, sections, and
            signature line. No QuillMD banner, and no appended diagnoses, billing, or patient
            summary. Your review screen and the standard export are unchanged.
          </span>
        </span>
      </label>

      {/* Sticky action bar.
          `qm-tpl-actionbar` lifts it above the fixed mobile bottom nav
          (`.qm-c3-mobilenav`, position:fixed, z-index:40) below 980px — without
          it the nav paints over this bar and "Save & activate" is literally
          unclickable on a phone. Same treatment `.qm-c3-rev2-signbar` already
          gets on the review screen. See globals.css. */}
      <div
        /* `qm-tpl-actionbar` is a SECOND shield: it is a class, so ownership
           stops here and never reaches the root anchor above — and what it
           shields is the primary CTA, the one node carrying the 3.43:1
           failure. The Rounds class is what makes the fix checkable. */
        className="qm-tpl-actionbar qm-rounds-tmpl-actionbar"
        style={{
          position: 'sticky',
          bottom: 0,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 12,
          padding: '14px 0 2px',
          marginTop: 18,
          borderTop: '1px solid var(--color-linear-hairline)',
          background: 'linear-gradient(180deg, transparent, var(--color-linear-surface-1) 40%)',
        }}
      >
        <div style={{ fontSize: 11.5, color: 'var(--color-linear-text-3)' }}>
          {defaultCount} default{defaultCount === 1 ? '' : 's'} · confirmed at sign time
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button type="button" style={btn} onClick={onCancel} disabled={pending}>Cancel</button>
          <button type="button" style={btn} onClick={() => save(false)} disabled={pending}>
            Save as draft
          </button>
          <button type="button" style={{ ...btnPrimary, padding: '9px 16px', fontSize: 13 }} onClick={() => save(true)} disabled={pending}>
            {pending ? 'Saving…' : 'Save & activate'}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Section card ────────────────────────────────────────────────────────────
function SectionCard({
  section,
  isFirst,
  isLast,
  onPatch,
  onMove,
  onRemove,
  canRemove,
}: {
  section: EditableSection;
  isFirst: boolean;
  isLast: boolean;
  onPatch: (n: Partial<EditableSection>) => void;
  onMove: (dir: -1 | 1) => void;
  onRemove: () => void;
  canRemove: boolean;
}) {
  const hasDefault = !!section.defaultText?.trim();
  return (
    <div style={{ border: '1px solid var(--color-linear-border)', borderRadius: 10, background: 'var(--color-linear-surface-2)', overflow: 'hidden' }}>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr auto', gap: 10, alignItems: 'center', padding: '11px 12px' }}>
        <div style={{ minWidth: 0 }}>
          <input
            style={{ ...input, fontWeight: 500, fontSize: 14, border: '1px solid transparent', background: 'transparent', height: 28, padding: '4px 8px' }}
            value={section.label}
            aria-label="Section label"
            onChange={(e) => onPatch({ label: e.target.value })}
          />
          <div style={{ fontFamily: mono, fontSize: 9.5, letterSpacing: '0.05em', textTransform: 'uppercase', color: 'var(--color-linear-text-4)', paddingLeft: 8, marginTop: 2 }}>
            key: {section.key}{hasDefault ? ' · has default' : ''}
            {section.structure?.kind === 'table'
              ? ` · table: ${section.structure.columns.join(' | ')}${section.structure.rowLabels ? ` (${section.structure.rowLabels.length} fixed rows)` : ''}`
              : null}
            {section.structure?.kind === 'options'
              ? ` · ${section.structure.multi ? 'check-all' : 'pick-one'}: ${section.structure.options.length} options`
              : null}
          </div>
          {section.structure?.kind === 'options' ? (
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, paddingLeft: 8, marginTop: 4 }}>
              {section.structure.options.map((o) => (
                <span key={o} style={{ fontSize: 11, padding: '1px 7px', borderRadius: 9, border: '1px solid var(--color-linear-border)', color: 'var(--color-linear-text-2)', background: 'var(--color-linear-surface-1)' }}>
                  {o}
                </span>
              ))}
            </div>
          ) : null}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          {/* format segmented toggle */}
          <div role="group" aria-label={`Format for ${section.label}`} style={{ display: 'inline-flex', border: '1px solid var(--color-linear-border)', borderRadius: 7, overflow: 'hidden', background: 'var(--color-linear-surface-1)' }}>
            {FORMATS.map((f) => {
              const on = section.formatHint === f.value;
              return (
                <button
                  key={f.value}
                  type="button"
                  aria-pressed={on}
                  onClick={() => onPatch({ formatHint: f.value })}
                  style={{
                    padding: '5px 9px',
                    fontSize: 11.5,
                    border: 'none',
                    borderRight: '1px solid var(--color-linear-border)',
                    cursor: 'pointer',
                    background: on ? 'var(--color-linear-sage-tint)' : 'transparent',
                    color: on ? 'var(--color-linear-sage-bright)' : 'var(--color-linear-text-3)',
                  }}
                >
                  {f.label}
                </button>
              );
            })}
          </div>
          {/* reorder */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            <button type="button" aria-label={`Move ${section.label} up`} disabled={isFirst} onClick={() => onMove(-1)} style={{ ...miniBtn, opacity: isFirst ? 0.3 : 1 }}>▲</button>
            <button type="button" aria-label={`Move ${section.label} down`} disabled={isLast} onClick={() => onMove(1)} style={{ ...miniBtn, opacity: isLast ? 0.3 : 1 }}>▼</button>
          </div>
          {/* expand/collapse */}
          <button type="button" aria-label={section._open ? `Collapse ${section.label}` : `Expand ${section.label}`} aria-expanded={section._open} onClick={() => onPatch({ _open: !section._open })} style={{ ...miniBtn, width: 24, height: 24 }}>
            {section._open ? '▾' : '▸'}
          </button>
        </div>
      </div>

      {section._open && (
        <div style={{ borderTop: '1px solid var(--color-linear-hairline)', padding: 12, display: 'flex', flexDirection: 'column', gap: 12, background: 'var(--color-linear-surface-1)' }}>
          <div>
            <div style={subLabel}>Style notes</div>
            <input
              style={input}
              value={section.styleInstructions ?? ''}
              placeholder="How this section is written (structure / tone) — format only, no patient details."
              aria-label={`Style notes for ${section.label}`}
              onChange={(e) => onPatch({ styleInstructions: e.target.value || null })}
            />
          </div>

          <div>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 5 }}>
              <div style={subLabel}>Default (“normal”) text · confirmed at sign time</div>
              {hasDefault && (
                <span style={{ ...pillInfo }}>Scaffold · confirm</span>
              )}
            </div>
            <textarea
              style={textarea}
              rows={3}
              value={section.defaultText ?? ''}
              placeholder="Optional boilerplate, e.g. a normal-exam line. Leave blank to write this section entirely from the visit."
              aria-label={`Default text for ${section.label}`}
              onChange={(e) => onPatch({ defaultText: e.target.value || null })}
            />
            <div style={{ display: 'flex', gap: 7, alignItems: 'flex-start', fontSize: 11, color: 'var(--color-linear-text-3)', marginTop: 7, lineHeight: 1.5 }}>
              <span aria-hidden style={{ color: 'var(--color-linear-info)' }}>ⓘ</span>
              <span>
                Lines here are a template, not a record. Any line the visit didn’t support is{' '}
                <b style={{ color: 'var(--color-linear-text-2)', fontWeight: 500 }}>held back and flagged</b> on the
                note for you to confirm or drop before signing.
              </span>
            </div>
          </div>

          {canRemove && (
            <button type="button" style={{ ...btn, alignSelf: 'flex-start', color: 'var(--color-linear-text-3)' }} onClick={onRemove} aria-label={`Remove ${section.label}`}>
              Remove section
            </button>
          )}
        </div>
      )}
    </div>
  );
}

const miniBtn: React.CSSProperties = {
  width: 22,
  height: 16,
  border: '1px solid var(--color-linear-border)',
  background: 'var(--color-linear-surface-1)',
  borderRadius: 4,
  color: 'var(--color-linear-text-3)',
  cursor: 'pointer',
  padding: 0,
  fontSize: 9,
  lineHeight: 1,
};
const pillInfo: React.CSSProperties = {
  display: 'inline-flex',
  alignItems: 'center',
  padding: '2px 8px',
  borderRadius: 4,
  fontSize: 10,
  fontWeight: 500,
  background: 'var(--color-linear-info-wash)',
  color: 'var(--color-linear-info)',
  border: '1px solid var(--color-linear-info-edge)',
};

// ── Safety callout (verbatim from the mockup) ───────────────────────────────
function SafetyCallout() {
  return (
    <div
      role="note"
      style={{
        position: 'relative',
        border: '1px solid var(--color-linear-info-edge)',
        background: 'var(--color-linear-info-wash-soft)',
        borderRadius: 9,
        padding: '11px 13px 11px 15px',
        display: 'flex',
        gap: 10,
        alignItems: 'flex-start',
        overflow: 'hidden',
        marginTop: 16,
      }}
    >
      <span aria-hidden style={{ position: 'absolute', left: 0, top: 0, bottom: 0, width: 3, background: 'var(--color-linear-info)' }} />
      <div style={{ minWidth: 0 }}>
        <div style={{ fontSize: 12.5, fontWeight: 600, color: 'var(--color-linear-text)', marginBottom: 2 }}>
          How your default (“normal”) text is used — safely
        </div>
        <p style={{ margin: 0, fontSize: 11.5, color: 'var(--color-linear-text-2)', lineHeight: 1.55 }}>
          Default text is a <b style={{ color: 'var(--color-linear-text)', fontWeight: 500 }}>starting point</b>. QuillMD only
          states findings the visit actually supports —{' '}
          <b style={{ color: 'var(--color-linear-text)', fontWeight: 500 }}>anything from your defaults that wasn’t discussed is flagged for your review before you sign</b>,
          never silently asserted. You stay in control of every finding.
        </p>
      </div>
    </div>
  );
}

// ── Structure outline rows (fallback shown while the sample renders) ─────────
function StructureOutline({ sections }: { sections: EditableSection[] }) {
  return (
    <div style={{ padding: '14px 16px', display: 'flex', flexDirection: 'column', gap: 10, maxHeight: 460, overflow: 'auto' }}>
      {sections.map((s, i) => (
        <div key={s._uid} style={{ display: 'flex', gap: 10, alignItems: 'flex-start' }}>
          <span style={{ fontFamily: mono, fontSize: 10, color: 'var(--color-linear-text-4)', marginTop: 2 }}>{String(i + 1).padStart(2, '0')}</span>
          <div style={{ minWidth: 0 }}>
            <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--color-linear-text)' }}>{s.label || 'Section'}</div>
            <div style={{ fontSize: 11, color: 'var(--color-linear-text-3)', marginTop: 1 }}>
              {s.formatHint}
              {s.defaultText?.trim() ? ' · has a confirm-before-sign default' : ' · written from the visit'}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

// ── Minimal SOAP-markdown render (## headings, **bold**, bullets, paragraphs).
//    Deliberately no markdown lib + no dangerouslySetInnerHTML — clinicians
//    need headings + bold, nothing more (mirrors SoapSection's SoapMarkdown). ──
function renderInlineBold(text: string, keyBase: string): React.ReactNode[] {
  return text.split(/(\*\*[^*]+\*\*)/g).map((part, i) =>
    part.startsWith('**') && part.endsWith('**') ? (
      <strong key={`${keyBase}-${i}`} style={{ fontWeight: 600, color: 'var(--color-linear-text)' }}>{part.slice(2, -2)}</strong>
    ) : (
      <span key={`${keyBase}-${i}`}>{part}</span>
    ),
  );
}
// Structure-aware note line shapes (mirrors SoapSection's SoapMarkdown):
// GitHub-style pipe rows buffer into a real <table>; task-list lines render
// a ☒/☐ glyph row. Prose-only samples never hit either branch.
// NOTE: this preview intentionally forks the .qm-lin-soap-md-* utilities at
// miniature scale (10px headers / 4px padding vs the note view's 10.5/6) —
// the sample renders inside a compact settings card. If the note-view
// utilities change shape (not just size), update this fork to match.
const SAMPLE_TABLE_ROW_RE = /^\s*\|.*\|\s*$/;
const SAMPLE_TABLE_SEPARATOR_ROW_RE = /^\s*\|[\s:|-]+\|\s*$/;
const SAMPLE_TASK_LINE_RE = /^\s*[-*]\s+\[( |x|X)\]\s+(.*)$/;
function splitSampleTableRow(line: string): string[] {
  return line.trim().replace(/^\|/, '').replace(/\|$/, '').split('|').map((c) => c.trim());
}
const sampleCellStyle: React.CSSProperties = {
  padding: '4px 10px',
  borderBottom: '1px solid var(--color-linear-hairline)',
  fontSize: 12,
  lineHeight: 1.5,
  color: 'var(--color-linear-text-2)',
  textAlign: 'left',
  verticalAlign: 'top',
};
function SampleMarkdown({ text }: { text: string }) {
  const lines = text.split('\n');
  const out: React.ReactNode[] = [];
  let tableBuffer: string[] = [];
  const flushTable = (k: string) => {
    if (tableBuffer.length === 0) return;
    const rows = tableBuffer
      .filter((r) => !SAMPLE_TABLE_SEPARATOR_ROW_RE.test(r))
      .map(splitSampleTableRow);
    tableBuffer = [];
    if (rows.length === 0) return;
    const [header, ...body] = rows;
    out.push(
      // overflow-x scroll container must be keyboard-reachable
      // (axe scrollable-region-focusable)
      <div
        key={`tbl-${k}`}
        tabIndex={0}
        role="region"
        aria-label={header.filter(Boolean).join(' / ') || 'Sample table'}
        style={{ overflowX: 'auto', margin: '6px 0', border: '1px solid var(--color-linear-border)', borderRadius: 6 }}
      >
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr>
              {header.map((cell, ci) => (
                <th key={ci} style={{ ...sampleCellStyle, background: 'var(--color-linear-surface-2)', borderBottom: '1px solid var(--color-linear-border)', fontFamily: mono, fontSize: 10, letterSpacing: '0.1em', textTransform: 'uppercase', color: 'var(--color-linear-text-3)', fontWeight: 500, whiteSpace: 'nowrap' }}>
                  {renderInlineBold(cell, `tbl-${k}-h${ci}`)}
                </th>
              ))}
            </tr>
          </thead>
          {body.length > 0 ? (
            <tbody>
              {body.map((cells, ri) => (
                <tr key={ri}>
                  {cells.map((cell, ci) => (
                    <td key={ci} style={sampleCellStyle}>{renderInlineBold(cell, `tbl-${k}-r${ri}c${ci}`)}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          ) : null}
        </table>
      </div>
    );
  };
  lines.forEach((raw, i) => {
    const l = raw.trimEnd();
    const k = `ln${i}`;
    if (SAMPLE_TABLE_ROW_RE.test(l)) {
      tableBuffer.push(l);
      return;
    }
    flushTable(k);
    const task = l.match(SAMPLE_TASK_LINE_RE);
    if (task) {
      const checked = task[1].toLowerCase() === 'x';
      out.push(
        <div key={k} style={{ display: 'flex', gap: 6, alignItems: 'baseline', fontSize: 12, color: 'var(--color-linear-text-2)', lineHeight: 1.55 }}>
          <span aria-hidden="true" style={{ flex: 'none', color: checked ? 'var(--color-linear-sage-bright)' : 'var(--color-linear-text-3)' }}>{checked ? '☒' : '☐'}</span>
          <span className="sr-only">{checked ? 'Checked:' : 'Not checked:'}</span>
          <span>{renderInlineBold(task[2], k)}</span>
        </div>
      );
    } else if (l.startsWith('## ')) {
      out.push(<div key={k} style={{ fontSize: 12.5, fontWeight: 600, color: 'var(--color-linear-text)', marginTop: i === 0 ? 0 : 12, marginBottom: 2 }}>{l.slice(3)}</div>);
    } else if (l.startsWith('# ')) {
      out.push(<div key={k} style={{ fontSize: 13.5, fontWeight: 600, color: 'var(--color-linear-text)', marginTop: i === 0 ? 0 : 12 }}>{l.slice(2)}</div>);
    } else if (l.startsWith('- ') || l.startsWith('* ')) {
      out.push(<div key={k} style={{ display: 'flex', gap: 6, fontSize: 12, color: 'var(--color-linear-text-2)', lineHeight: 1.55 }}><span aria-hidden style={{ color: 'var(--color-linear-text-4)' }}>•</span><span>{renderInlineBold(l.slice(2), k)}</span></div>);
    } else if (l === '') {
      out.push(<div key={k} style={{ height: 6 }} />);
    } else {
      out.push(<div key={k} style={{ fontSize: 12, color: 'var(--color-linear-text-2)', lineHeight: 1.55 }}>{renderInlineBold(l, k)}</div>);
    }
  });
  flushTable('end');
  return <div style={{ display: 'flex', flexDirection: 'column' }}>{out}</div>;
}

// ── Live sample-note preview ─────────────────────────────────────────────────
// Generates a sample note IN THE DOCTOR'S FORMAT from a FIXED SYNTHETIC demo
// visit (never a real patient). ADDITIVE: a generation failure degrades to the
// structural outline + a quiet message and NEVER blocks save/activate.
type PreviewStatus = 'loading' | 'ready' | 'error';
function SamplePreview({
  sections,
  getPayload,
}: {
  sections: EditableSection[];
  getPayload: () => unknown;
}) {
  const [status, setStatus] = useState<PreviewStatus>('loading');
  const [markdown, setMarkdown] = useState<string | null>(null);
  const [, startPreview] = useTransition();
  // StrictMode double-invokes effects in dev; guard the initial auto-generate.
  const didInit = useRef(false);

  function generate() {
    setStatus('loading');
    startPreview(async () => {
      try {
        const res = await previewNoteTemplateAction(getPayload());
        if (res.ok) {
          setMarkdown(res.markdown);
          setStatus('ready');
        } else {
          setStatus('error');
        }
      } catch {
        // The preview is additive — a thrown error must never reach the page
        // boundary or block the editor. Degrade to the outline.
        setStatus('error');
      }
    });
  }

  // Auto-generate once after parse (the review screen mounts post-parse).
  useEffect(() => {
    if (didInit.current) return;
    didInit.current = true;
    generate();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div style={{ position: 'sticky', top: 64, alignSelf: 'start' }}>
      <div style={{ border: '1px solid var(--color-linear-border)', borderRadius: 10, background: 'var(--color-linear-surface-1)', overflow: 'hidden' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '11px 14px', borderBottom: '1px solid var(--color-linear-hairline)' }}>
          <span style={{ fontSize: 12.5, fontWeight: 500, color: 'var(--color-linear-text)' }}>Sample note in your format</span>
          <span
            title="Generated from a synthetic demo visit — not a real patient."
            /* C1-f: `color` was the sage FILL token — 3.22:1 bridged, and this
               is real text at 9.5px. The text variant is 7.60:1. This is one of
               the two sites `gate-rounds-bridge`'s deferred-fork entry named. */
            style={{ fontFamily: mono, fontSize: 9.5, letterSpacing: '0.05em', textTransform: 'uppercase', color: 'var(--color-linear-sage-bright)', border: '1px solid var(--color-linear-sage-edge)', borderRadius: 5, padding: '2px 6px' }}
          >
            Demo visit · synthetic
          </span>
        </div>

        <div style={{ padding: status === 'ready' ? '14px 16px' : 0, maxHeight: 460, overflow: 'auto' }}>
          {status === 'ready' && markdown ? (
            <SampleMarkdown text={markdown} />
          ) : status === 'loading' ? (
            <>
              <div style={{ padding: '10px 16px 0', fontSize: 11.5, color: 'var(--color-linear-text-3)', display: 'flex', alignItems: 'center', gap: 7 }}>
                <span aria-hidden style={{ width: 11, height: 11, border: '1.5px solid var(--color-linear-text-4)', borderTopColor: 'var(--color-linear-sage)', borderRadius: '50%', display: 'inline-block', animation: 'qm-spin 1.1s linear infinite' }} />
                Rendering a sample in your format…
              </div>
              <StructureOutline sections={sections} />
            </>
          ) : (
            <>
              <div style={{ padding: '10px 16px 0', fontSize: 11.5, color: 'var(--color-linear-text-3)' }}>
                Couldn’t render a sample right now — your structure is below. This doesn’t affect saving or activating.
              </div>
              <StructureOutline sections={sections} />
            </>
          )}
        </div>

        <div style={{ display: 'flex', gap: 8, alignItems: 'center', justifyContent: 'space-between', padding: '10px 14px', borderTop: '1px solid var(--color-linear-hairline)' }}>
          <span style={{ fontSize: 11, color: 'var(--color-linear-text-3)', lineHeight: 1.45 }}>
            <span aria-hidden style={{ color: 'var(--color-linear-info)' }}>ⓘ</span>{' '}
            A synthetic demo visit — not a real patient. Default lines a visit doesn’t support are flagged, never asserted.
          </span>
          <button
            type="button"
            style={{ ...btn, padding: '4px 9px', fontSize: 11 }}
            onClick={generate}
            disabled={status === 'loading'}
          >
            {status === 'loading' ? 'Rendering…' : 'Regenerate'}
          </button>
        </div>
      </div>
      <style>{`@keyframes qm-spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}
