// ============================================================================
// TOKEN-1 GATE — scan RENDERED .docx bytes for a residual brace placeholder.
// ----------------------------------------------------------------------------
// The owner ruling: "a brace placeholder never reaches a rendered document
// (arm on the export bytes)." This is that arm. It runs in the certification
// self-test (so a template that could emit a residual token cannot certify) and
// in a standalone gate test.
//
// It reads VISIBLE text across ALL rendered parts — document, headers, footers —
// because {patient}/{age} controls can live in a header/footer, which the
// body-only `docxToTextWithControls` would miss. Within a part, `w:t` run text
// is concatenated with NO separator, so a token Word split across runs
// (`{`,`patient`,`}`) still reads as `{patient}`. The placeholder predicate
// itself (scaffold-text.ts) ignores the `{{one of: …}}` choice marker.
// ============================================================================
import JSZip from 'jszip';
import { residualPlaceholders } from './scaffold-text';

const PART_RE = /^word\/(document|header\d*|footer\d*|footnotes|endnotes)\.xml$/;
const WT_RE = /<w:t\b[^>]*>([\s\S]*?)<\/w:t>/g;

function decodeXml(s: string): string {
  return s
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&apos;/g, "'")
    .replace(/&amp;/g, '&');
}

/** Every brace placeholder (`{word}`, never `{{one of}}`) surviving in the
 *  visible text of the rendered document, across all parts. Empty is the pass. */
export async function residualPlaceholdersInDocx(bytes: Uint8Array): Promise<string[]> {
  const zip = await JSZip.loadAsync(Buffer.from(bytes));
  const found = new Set<string>();
  for (const name of Object.keys(zip.files)) {
    if (!PART_RE.test(name)) continue;
    const xml = await zip.files[name].async('string');
    let text = '';
    for (const m of xml.matchAll(WT_RE)) text += decodeXml(m[1]);
    for (const p of residualPlaceholders(text)) found.add(p);
  }
  return Array.from(found);
}
