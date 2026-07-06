// ============================================================================
// Note-format customization — Word CONTENT-CONTROL dropdown extraction.
// ----------------------------------------------------------------------------
// mammoth.extractRawText() renders a Word dropdown content control
// (`<w:sdt><w:dropDownList>`) as ONLY its current display text — for an
// unfilled template that is the placeholder "Choose an item.", so every
// option list is silently lost (verified on the real WM_IOV venous-duplex
// template: 28 dropdowns → 28× "Choose an item.", 0 options survive).
//
// A real practice template built with native Word dropdowns therefore reaches
// the note-format parser with NO options at all. This module walks the docx
// body in document order and reconstructs the note text with each dropdown
// rendered INLINE as a constrained-choice marker:
//
//     SIDE OF EXAM: {{one of: Bilateral Detailed | Bilateral Screening | ...}}
//     The {{one of: great saphenous vein | ...}} from the {{one of: ...}} ...
//
// Inline markers (rather than lifting each dropdown into a standalone
// option-set section) preserve the carrier sentence, so an interdependent
// finding chain — "The <vein> from the <segment> to the <segment> ..." — stays
// one linked sentence the model fills as a set. The fixed prose, headings,
// tabs and paragraph breaks are preserved so the parser sees the real layout.
//
// Server-only. Never persists. Pure text reconstruction — no PHI (a template
// has no patient data).
// ============================================================================

import JSZip from 'jszip';
import { XMLParser } from 'fast-xml-parser';

const W = 'w:';
/** Word's unfilled-dropdown placeholder; never a real clinical option. */
const PLACEHOLDER_RE = /^\s*choose an item\.?\s*$/i;

/** The inline marker a dropdown becomes. Distinct from the anchor delimiters
 *  (⟦ ⟧) the verifier uses, and from markdown, so nothing downstream collides. */
export function choiceMarker(options: string[]): string {
  return `{{one of: ${options.join(' | ')}}}`;
}

// fast-xml-parser preserveOrder node: { 'w:t': [...] , ':@': {attrs} } etc.
type OrderedNode = Record<string, unknown> & { ':@'?: Record<string, string> };

function tagOf(node: OrderedNode): string {
  return Object.keys(node).find((k) => k !== ':@') ?? '';
}

/** Extract the non-placeholder option display-texts of a `<w:sdt>` dropdown,
 *  or null when the sdt is not a dropdown content control. */
function dropdownOptions(sdtChildren: OrderedNode[]): string[] | null {
  const prNode = sdtChildren.find((c) => tagOf(c) === W + 'sdtPr');
  if (!prNode) return null;
  const pr = prNode[W + 'sdtPr'] as OrderedNode[];
  const ddNode = pr.find((c) => tagOf(c) === W + 'dropDownList');
  if (!ddNode) return null;
  const dd = ddNode[W + 'dropDownList'] as OrderedNode[];
  return dd
    .filter((c) => tagOf(c) === W + 'listItem')
    .map((c) => c[':@']?.['@_w:displayText'] ?? '')
    .filter((v) => v && !PLACEHOLDER_RE.test(v));
}

/** Walk ordered wordprocessingml nodes, appending text + choice markers. */
function walk(nodes: OrderedNode[], out: string[], counter: { n: number }): void {
  for (const node of nodes) {
    const tag = tagOf(node);
    const children = node[tag];

    if (tag === W + 'sdt') {
      const sdtChildren = children as OrderedNode[];
      const opts = dropdownOptions(sdtChildren);
      if (opts && opts.length > 0) {
        out.push(choiceMarker(opts));
        counter.n += 1;
        continue; // skip the placeholder text inside sdtContent
      }
      // Non-dropdown content control (plain/rich text, date): descend so its
      // current text still appears.
      const content = sdtChildren.find((c) => tagOf(c) === W + 'sdtContent');
      if (content) walk(content[W + 'sdtContent'] as OrderedNode[], out, counter);
      continue;
    }
    if (tag === W + 't') {
      // Text node value can be a string or a #text-bearing array.
      const v =
        typeof children === 'string'
          ? children
          : ((children as OrderedNode[])?.[0]?.['#text'] as string) ?? '';
      out.push(v);
      continue;
    }
    if (tag === '#text') {
      // Meaningful Word text always lives inside `<w:t>`; a bare #text node is
      // inter-element whitespace (only present in pretty-printed XML, never in
      // real Word output). Drop whitespace-only; keep any real stray text.
      const v = String(node['#text'] ?? '');
      if (v.trim()) out.push(v);
      continue;
    }
    if (tag === W + 'tab') {
      out.push('\t');
      continue;
    }
    if (tag === W + 'br' || tag === W + 'cr') {
      out.push('\n');
      continue;
    }
    if (tag === W + 'p') {
      walk(children as OrderedNode[], out, counter);
      out.push('\n');
      continue;
    }
    if (Array.isArray(children)) walk(children as OrderedNode[], out, counter);
  }
}

/**
 * Reconstruct a .docx's body text with dropdown content controls rendered as
 * inline `{{one of: ...}}` choice markers. Returns the text and the number of
 * dropdowns found (0 → caller should fall back to mammoth for a normal docx).
 */
export async function docxToTextWithControls(
  bytes: Uint8Array
): Promise<{ text: string; dropdownCount: number }> {
  const zip = await JSZip.loadAsync(Buffer.from(bytes));
  const docXml = zip.file('word/document.xml');
  if (!docXml) return { text: '', dropdownCount: 0 };
  const xml = await docXml.async('string');

  const parser = new XMLParser({
    preserveOrder: true,
    ignoreAttributes: false,
    attributeNamePrefix: '@_',
    trimValues: false,
  });
  const tree = parser.parse(xml) as OrderedNode[];

  const out: string[] = [];
  const counter = { n: 0 };
  walk(tree, out, counter);

  const text = out
    .join('')
    .replace(/[ \t]+\n/g, '\n') // strip trailing whitespace per line
    .replace(/\n{3,}/g, '\n\n') // collapse >2 blank lines
    .trim();

  return { text, dropdownCount: counter.n };
}
