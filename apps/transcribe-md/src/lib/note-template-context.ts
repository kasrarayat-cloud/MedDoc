// ============================================================================
// Context-field defaults for custom structured templates.
// ----------------------------------------------------------------------------
// A real imaging template (WM_IOV) has CONTEXT dropdowns a doctor never
// dictates — clinic address, referring/interpreting physician, sonographer /
// technologist, ultrasound machine, location/city. These must NOT be filled by
// the AI (no transcript basis). Instead they are filled DETERMINISTICALLY from
// per-doctor defaults stored on the template (styleProfile.contextDefaults),
// BEFORE the prompt is built — the model never sees a context {{one of}} slot,
// only the resolved value (or "[not documented]" when unset). Pure + isomorphic
// (no server/AI deps) so both the worker (generation) and the review UI
// (settings) import it.
//
// Sonographer/technologist is PER-VISIT, so it carries no fixed default and
// always resolves to "[not documented]" — the one field the doctor completes in
// the note per visit. (A per-visit picker would need a visit-schema / record-
// flow change, out of the settings/generation-side scope.)
// ============================================================================

/** The canonical "no value" token — already exempt in the verifier's
 *  isExemptLine ("Label: [not documented]"), so a resolved-but-unset context
 *  line never enters the anchor path. */
export const NOT_DOCUMENTED = '[not documented]';

export interface ContextFieldDescriptor {
  /** Stable key used in styleProfile.contextDefaults. */
  key: string;
  /** Human label for the settings UI. */
  label: string;
  /** Matches the marker's on-line LABEL prefix (e.g. "REFERRING PHYSICIAN:"). */
  labelRe: RegExp;
  /** Fallback: matches the marker's OWN options (for a label-less field such
   *  as the letterhead clinic address). */
  optionRe?: RegExp;
  /** True → per-visit, no fixed default (sonographer). */
  perVisit?: boolean;
}

export const CONTEXT_FIELDS: ContextFieldDescriptor[] = [
  {
    key: 'clinicAddress',
    label: 'Clinic address',
    labelRe: /\b(clinic\s+)?address\b/i,
    // a US street address option: "…, CA 92604"
    optionRe: /,\s*[A-Z]{2}\s+\d{5}\b/,
  },
  {
    key: 'referringPhysician',
    label: 'Referring / interpreting physician',
    labelRe: /\b(referring|interpreting|reading)\s+(physician|provider|md)\b/i,
  },
  {
    key: 'sonographer',
    label: 'Sonographer / technologist',
    labelRe: /\b(ultrasound\s+)?(technologist|sonographer|sonograph\w*)\b/i,
    perVisit: true,
  },
  {
    key: 'machine',
    // NOTE: deliberately does NOT match "transducer" alone — that word recurs
    // in dictatable findings; a context field must name the machine/unit label.
    label: 'Ultrasound machine',
    labelRe: /\b(machine|ultrasound\s+(unit|system))\b/i,
  },
  {
    key: 'location',
    // NOTE: "site" is deliberately excluded — a dictatable "Biopsy site:" /
    // "puncture site" line must never be misread as a context field and blanked.
    label: 'Location / city',
    labelRe: /\b(location|city)\b/i,
  },
];

const MARKER_G = /\{\{one of:\s*([^}]*)\}\}/g;

/** Which context field (if any) a marker belongs to, matched by its on-line
 *  label prefix first, then by its option shape (the label-less address). */
export function matchContextField(
  label: string,
  options: string[]
): ContextFieldDescriptor | null {
  for (const f of CONTEXT_FIELDS) {
    if (f.labelRe.test(label)) return f;
  }
  for (const f of CONTEXT_FIELDS) {
    if (f.optionRe && options.some((o) => f.optionRe!.test(o))) return f;
  }
  return null;
}

export interface DetectedContextField {
  key: string;
  label: string;
  /** Descriptor label for the UI. */
  fieldLabel: string;
  options: string[];
  perVisit: boolean;
}

/** Find every context marker across the template's section defaultText, with
 *  its own enumerated options — drives the settings UI (a default may only be
 *  chosen from these) and dedupes by key (first occurrence wins). */
export function detectContextFields(
  sections: ReadonlyArray<{ defaultText?: string | null }>
): DetectedContextField[] {
  const byKey = new Map<string, DetectedContextField>();
  for (const s of sections) {
    const dt = s.defaultText;
    if (!dt) continue;
    for (const line of dt.split('\n')) {
      let last = 0;
      for (const m of line.matchAll(MARKER_G)) {
        const label = line.slice(last, m.index).trim();
        last = m.index! + m[0].length;
        const options = m[1].split('|').map((o) => o.trim()).filter(Boolean);
        const f = matchContextField(label, options);
        if (!f || byKey.has(f.key)) continue;
        byKey.set(f.key, {
          key: f.key,
          label: label || f.label,
          fieldLabel: f.label,
          options,
          perVisit: !!f.perVisit,
        });
      }
    }
  }
  // preserve CONTEXT_FIELDS order
  return CONTEXT_FIELDS.map((f) => byKey.get(f.key)).filter(
    (d): d is DetectedContextField => d != null
  );
}

/** Replace every CONTEXT marker in the sections with the doctor's default
 *  (only when it is one of that marker's OWN options) or "[not documented]".
 *  DICTATABLE markers (side of exam, indications, diagnosis, findings/impression
 *  chains) are left untouched for the model to fill. Returns NEW sections;
 *  input is not mutated. When contextDefaults is null/empty, context markers
 *  resolve to "[not documented]" — today's safe blank, no regression. */
export function applyContextDefaults<
  T extends { defaultText?: string | null },
>(sections: readonly T[], contextDefaults: Record<string, string> | null | undefined): T[] {
  const defaults = contextDefaults ?? {};
  return sections.map((s) => {
    const dt = s.defaultText;
    if (!dt || !dt.includes('{{one of:')) return s;
    const lines = dt.split('\n').map((line) => {
      let cursor = 0;
      let out = '';
      let changed = false;
      // Rebuild the line, resolving only context markers.
      const markers = [...line.matchAll(MARKER_G)];
      for (const m of markers) {
        const label = line.slice(cursor, m.index).trim();
        const options = m[1].split('|').map((o) => o.trim()).filter(Boolean);
        const f = matchContextField(label, options);
        out += line.slice(cursor, m.index! + (f ? 0 : m[0].length));
        if (f) {
          const chosen = f.perVisit ? undefined : defaults[f.key];
          const value = chosen && options.includes(chosen) ? chosen : NOT_DOCUMENTED;
          out += value;
          changed = true;
        }
        cursor = m.index! + m[0].length;
      }
      out += line.slice(cursor);
      return changed ? out : line;
    });
    return { ...s, defaultText: lines.join('\n') };
  });
}
