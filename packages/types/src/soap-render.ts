// ============================================================================
// @meddoc/types — SOAP JSON → Markdown renderer
// ----------------------------------------------------------------------------
// Used by apps/meddoc-pro at DISPLAY time when `Document.content` is a
// Scribe-authored SOAP JSON. We never persist the rendered markdown —
// the JSON stays the source of truth so re-renders can pick up schema
// improvements without rewriting old documents.
// ============================================================================

import type { SoapNote } from './soap';
import { SoapNoteSchema } from './soap';

/**
 * Best-effort JSON sniff. Cheap enough to run on every Document render.
 * Returns the parsed + validated SoapNote, or null if `content` is the
 * pre-Scribe plain-text / markdown format.
 */
export function parseSoapNote(content: string | null | undefined): SoapNote | null {
  if (!content) return null;
  const trimmed = content.trim();
  if (!trimmed.startsWith('{')) return null;
  try {
    const parsed = JSON.parse(trimmed);
    const result = SoapNoteSchema.safeParse(parsed);
    return result.success ? result.data : null;
  } catch {
    return null;
  }
}

function humanize(key: string): string {
  return key
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

function renderRecord(section: Record<string, string>): string {
  const keys = Object.keys(section);
  if (keys.length === 0) return '_Not documented._';
  return keys
    .map((k) => `**${humanize(k)}:** ${section[k]}`)
    .join('\n\n');
}

/**
 * Render a SoapNote as markdown for display. Stable output — same input
 * always gives the same markdown so snapshot tests can rely on it.
 */
export function renderSoapMarkdown(soap: SoapNote): string {
  const lines: string[] = [];

  lines.push(`_AI-generated from a Scribe visit. Confidence: **${soap.confidence}**._`);
  lines.push('');

  if (soap.missing_required_elements.length > 0) {
    lines.push('> ⚠️ Missing documented elements: ' + soap.missing_required_elements.map(humanize).join(', '));
    lines.push('');
  }

  if (soap.ambiguities.length > 0) {
    lines.push('> Ambiguities flagged by the model:');
    for (const a of soap.ambiguities) lines.push(`> - ${a}`);
    lines.push('');
  }

  lines.push('## Subjective');
  lines.push(renderRecord(soap.subjective));
  lines.push('');

  lines.push('## Objective');
  lines.push(renderRecord(soap.objective));
  lines.push('');

  lines.push('## Assessment');
  if (soap.assessment.length === 0) {
    lines.push('_No assessment items._');
  } else {
    for (const item of soap.assessment) {
      lines.push(`- **${item.icd10_candidate}** — ${item.description} _(${item.confidence} confidence)_`);
      lines.push(`  > ${item.evidence_quote}`);
    }
  }
  lines.push('');

  lines.push('## Plan');
  lines.push(renderRecord(soap.plan));

  return lines.join('\n');
}
