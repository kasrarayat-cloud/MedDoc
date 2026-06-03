'use client';

// ============================================================================
// Note-format customization — Phase 2b: review / edit a parsed (or existing)
// template, then Save as draft / Save & activate.
// ----------------------------------------------------------------------------
// Mirrors docs/design-directions-v9-note-format/3-review.html using the live
// Linear V1 tokens (inline style + --color-linear-*, the settings convention).
// The default-text SAFETY callout + the per-default scaffold microcopy are
// non-optional. The preview is a STRUCTURAL outline (live sample DEFERRED — no
// generation here). The save payload is stripped to the strict schema shape
// (no defaultTextMode — the server coerces it to scaffold_confirm).
// ============================================================================

import { useMemo, useState, useTransition } from 'react';
import { toast } from 'sonner';

import { SPECIALTIES } from '@meddoc/shared/specialties';
import {
  saveNoteTemplateAction,
} from '@/actions/note-template-lifecycle';
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
const btnPrimary: React.CSSProperties = {
  ...btn,
  background: 'var(--color-linear-sage)',
  color: '#0d1611',
  border: 'none',
  boxShadow: '0 0 0 1px rgba(122,166,140,0.3)',
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
  ...SPECIALTIES.filter((s) => s.id !== 'unspecified').map((s) => ({
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
  onCancel: () => void;
  onSaved: (status: 'draft' | 'active') => void;
}

export function TemplateReviewEditor({
  initial,
  parseFlags = [],
  onCancel,
  onSaved,
}: TemplateReviewEditorProps) {
  const [name, setName] = useState(initial.name);
  const [encounterType, setEncounterType] = useState<string>(initial.encounterType ?? '');
  const [sections, setSections] = useState<EditableSection[]>(() =>
    [...initial.sections].sort((a, b) => a.order - b.order).map(toEditable),
  );
  const [flags, setFlags] = useState<string[]>(parseFlags);
  const [pending, startTransition] = useTransition();

  // styleProfile (tense/tone/abbreviations) carries through unchanged — no
  // dedicated UI in CORE; the immutable safety layer is never here regardless.
  const styleProfile = initial.styleProfile;

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
      name: name.trim(),
      encounterType: encounterType ? encounterType : null,
      sections: sections.map((s, i) => ({
        key: s.key,
        label: s.label.trim() || 'Section',
        order: i + 1,
        formatHint: s.formatHint,
        styleInstructions: s.styleInstructions,
        defaultText: s.defaultText,
      })),
      styleProfile: {
        tense: styleProfile.tense,
        tone: styleProfile.tone,
        abbreviations: styleProfile.abbreviations,
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
    <div>
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
            {ENCOUNTER_OPTIONS.map((o) => (
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
                      border: '1px solid rgba(122,166,140,0.22)',
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

        {/* RIGHT — structural preview (live sample DEFERRED) */}
        <StructuralPreview sections={sections} />
      </div>

      {/* Sticky action bar */}
      <div
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
          </div>
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
  background: 'rgba(91,141,184,0.08)',
  color: 'var(--color-linear-info)',
  border: '1px solid rgba(91,141,184,0.25)',
};

// ── Safety callout (verbatim from the mockup) ───────────────────────────────
function SafetyCallout() {
  return (
    <div
      role="note"
      style={{
        position: 'relative',
        border: '1px solid rgba(91,141,184,0.25)',
        background: 'rgba(91,141,184,0.06)',
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

// ── Structural preview (live sample DEFERRED — no generation) ───────────────
function StructuralPreview({ sections }: { sections: EditableSection[] }) {
  return (
    <div style={{ position: 'sticky', top: 64, alignSelf: 'start' }}>
      <div style={{ border: '1px solid var(--color-linear-border)', borderRadius: 10, background: 'var(--color-linear-surface-1)', overflow: 'hidden' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '11px 14px', borderBottom: '1px solid var(--color-linear-hairline)' }}>
          <span style={{ fontSize: 12.5, fontWeight: 500, color: 'var(--color-linear-text)' }}>Your note structure</span>
          <span style={{ fontFamily: mono, fontSize: 9.5, letterSpacing: '0.05em', textTransform: 'uppercase', color: 'var(--color-linear-text-4)' }}>Outline</span>
        </div>
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
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', padding: '10px 14px', borderTop: '1px solid var(--color-linear-hairline)', fontSize: 11.5, color: 'var(--color-linear-text-3)' }}>
          <span aria-hidden style={{ color: 'var(--color-linear-info)' }}>ⓘ</span>
          A live sample of a note in your format is coming soon. Default lines a visit doesn’t support are always flagged, never asserted.
        </div>
      </div>
    </div>
  );
}
