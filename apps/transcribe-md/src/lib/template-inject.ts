// ============================================================================
// Auto-token injector (T-M24.smart — Phase 2)
// ----------------------------------------------------------------------------
// Consumes detectSections + the raw .docx buffer, walks word/document.xml
// block-by-block, and rewrites each clinical_narrative section's body so
// docxtemplater's existing fill step can treat the template as a normal
// {{token}} template.
//
// Preservation rules (hard):
//   - letterhead / metadata / salutation — verbatim
//   - sub_section paragraphs (no mappedToken) — verbatim
//   - clinical_table — verbatim
//   - signature range — verbatim (findSignatureRange carved this out)
//   - disclaimer / boilerplate — verbatim
//
// Rewrite rules (only clinical_narrative with a mappedToken):
//   1. Heading on its own line + N body paragraphs → keep heading,
//      replace body with a single `<w:p>{{token}}</w:p>`.
//   2. Heading with inline tail ("Medications This Visit:\tGabapentin…")
//      → replace the whole paragraph with a synthesised
//      `<w:p><heading>\t{{token}}</w:p>` so the doctor's old inline
//      value goes away but the heading text + tab layout stays.
//   3. Heading with no body paragraphs (empty section) → keep heading,
//      insert `<w:p>{{token}}</w:p>` immediately after it.
//
// Slice-based emission (vs. DOM surgery) means we preserve every byte
// of non-rewritten XML — pPr defaults, numPr (numbered-list refs),
// nested SDT blocks, section breaks — without needing to reconstruct
// them. Only the targeted body ranges get swapped.
// ============================================================================

import PizZip from 'pizzip';

import { detectSections, bodyRange, parseBlocks } from './template-sections';
import type { DetectedSection, Block } from './template-sections';
import type { SupportedToken } from './template-tokens';

export interface InjectionResult {
  /** Rewritten .docx buffer. Identical to input when no injections
   *  were performed (e.g. template already has {{tokens}} or has no
   *  clinical_narrative sections). */
  injected: Buffer;
  /** Every SUPPORTED_TOKEN we wrote into the binary, in document
   *  order. May contain duplicates (e.g. both "Medications:" and
   *  "Medications This Visit:" map to "medications"). */
  tokensInjected: SupportedToken[];
  /** Sections we left verbatim but which had a mapped clinical token.
   *  Currently none — but reserved for future "skipped because
   *  clashes with already-injected neighbour" diagnostics. */
  tokensSkipped: SupportedToken[];
  /** Rich section report, useful for the upload API to echo back in
   *  the confirmation UI AND for smoke-test diffing. */
  sections: DetectedSection[];
}

interface InjectionAction {
  kind: 'replace_inline' | 'keep_heading_replace_body' | 'append_after_heading';
  /** Start block index in `blocks` (inclusive). */
  startBlock: number;
  /** End block index in `blocks` (inclusive). */
  endBlock: number;
  token: SupportedToken;
  /** Used only for replace_inline — the heading text to preserve. */
  headingText?: string;
}

export function injectTokens(docxBuffer: Buffer): InjectionResult {
  const zip = new PizZip(docxBuffer);
  const xml = zip.file('word/document.xml')?.asText();
  if (!xml) throw new Error('word/document.xml missing');

  const body = xmlBody(xml);
  const blocks = parseBlocks(xml);
  const sections = detectSections(docxBuffer);

  const actions = planInjection(sections);

  if (actions.length === 0) {
    return {
      injected: docxBuffer,
      tokensInjected: [],
      tokensSkipped: [],
      sections,
    };
  }

  const rewritten = splice(xml, body, blocks, actions);

  // Replace the document XML inside the zip and re-emit.
  zip.file('word/document.xml', rewritten);
  const out = zip.generate({
    type: 'nodebuffer',
    compression: 'DEFLATE',
  });

  return {
    injected: out as Buffer,
    tokensInjected: actions.map((a) => a.token),
    tokensSkipped: [],
    sections,
  };
}

function xmlBody(xml: string) {
  return bodyRange(xml);
}

function planInjection(sections: DetectedSection[]): InjectionAction[] {
  const actions: InjectionAction[] = [];
  for (const s of sections) {
    if (s.contentType !== 'clinical_narrative') continue;
    if (!s.mappedToken) continue;
    if (!s.blockRange) continue;
    const { start, end } = s.blockRange;
    if (s.headingHasInlineContent) {
      // The heading paragraph has the body content inlined ("Label:\tvalue").
      // Replace that paragraph wholesale with a synthesised one.
      actions.push({
        kind: 'replace_inline',
        startBlock: start,
        endBlock: start,
        token: s.mappedToken,
        headingText: s.heading ?? '',
      });
    } else if (end > start) {
      // Heading on its own line + N body paragraphs. Keep heading,
      // replace [start+1..end] with a single token paragraph.
      actions.push({
        kind: 'keep_heading_replace_body',
        startBlock: start,
        endBlock: end,
        token: s.mappedToken,
      });
    } else {
      // Heading with no body paragraphs — the next heading landed
      // immediately after. Keep the heading and drop a token
      // paragraph immediately afterwards.
      actions.push({
        kind: 'append_after_heading',
        startBlock: start,
        endBlock: start,
        token: s.mappedToken,
      });
    }
  }
  return actions;
}

function splice(
  xml: string,
  body: { start: number; end: number },
  blocks: Block[],
  actions: InjectionAction[]
): string {
  /** Convert a body-relative offset (as stored on Block) to an absolute
   *  index in the full XML. */
  const abs = (off: number) => body.start + off;
  const blockStartAbs = (i: number) => abs(blocks[i].startOffset);
  const blockEndAbs = (i: number) => abs(blocks[i].endOffset);

  let out = '';
  let cursor = 0;

  // 1. Head through <w:body> open tag untouched.
  out += xml.slice(cursor, body.start);
  cursor = body.start;

  // 2. Walk actions in block order. Between actions, slice the original
  //    XML verbatim — that's where letterhead / sub_sections / tables /
  //    signature / disclaimer live, all of which we preserve.
  for (const action of actions) {
    const headingStart = blockStartAbs(action.startBlock);
    const headingEnd = blockEndAbs(action.startBlock);
    const lastEnd = blockEndAbs(action.endBlock);

    switch (action.kind) {
      case 'replace_inline':
        // Write everything up to (not including) the heading paragraph,
        // then drop our synthesised paragraph that carries both the
        // heading text and the {{token}}.
        out += xml.slice(cursor, headingStart);
        out += makeHeadingWithToken(action.headingText ?? '', action.token);
        cursor = headingEnd;
        break;

      case 'keep_heading_replace_body':
        // Write everything up to the END of the heading paragraph
        // (inclusive), then drop a fresh token paragraph, then skip
        // past the last body block.
        out += xml.slice(cursor, headingEnd);
        out += makeTokenParagraph(action.token);
        cursor = lastEnd;
        break;

      case 'append_after_heading':
        // Write through the heading paragraph; insert a token
        // paragraph; continue. `lastEnd === headingEnd` here.
        out += xml.slice(cursor, headingEnd);
        out += makeTokenParagraph(action.token);
        cursor = headingEnd;
        break;
    }
  }

  // 3. Tail: remainder of XML (rest of body + </w:body> + everything
  //    after, including <w:sectPr> and the closing <w:document> tag).
  out += xml.slice(cursor);
  return out;
}

/** Minimal paragraph carrying a single token. No pPr — inherits default
 *  paragraph formatting from the surrounding document. docxtemplater's
 *  fill step replaces {{token}} with the filled text using the same
 *  run's formatting (none, in our case), so filled content comes out
 *  in the template's default body style. */
function makeTokenParagraph(token: SupportedToken): string {
  return `<w:p><w:r><w:t xml:space="preserve">{{${token}}}</w:t></w:r></w:p>`;
}

/** Heading line + tab + token, in one paragraph. Used when the
 *  original template had `Label:\tvalue` on a single line — we mirror
 *  the layout so the filled output still reads "Label: <content>"
 *  with the label preserved. */
function makeHeadingWithToken(headingText: string, token: SupportedToken): string {
  const safe = escapeXml(headingText);
  return `<w:p><w:r><w:t xml:space="preserve">${safe}</w:t><w:tab/><w:t xml:space="preserve">{{${token}}}</w:t></w:r></w:p>`;
}

function escapeXml(s: string): string {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&apos;');
}
