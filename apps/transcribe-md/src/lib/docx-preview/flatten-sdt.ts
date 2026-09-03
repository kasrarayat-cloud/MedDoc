// ============================================================================
// UNWRAP CONTENT CONTROLS FOR PDF CONVERSION — BY DOM, NOT BY STRING.
// ----------------------------------------------------------------------------
// ⚠️ THE DEFECT THIS EXISTS FOR, MEASURED ON THE OWNER'S OWN VISIT. His signed
// export served byte-identical DOCX to Word and to the PDF converter. The DOCX
// carried 22 filled content controls and 7,603 visible characters. The PDF
// carried **0 of the 22** and 2,199 characters: every paragraph OUTSIDE a
// control rendered, every filled control rendered EMPTY. On the real customer
// template only **1 of 28** control texts render — the single BLOCK-level one.
// The LibreOffice question is FILED, not diagnosed: `DEPLOYMENT_RUNBOOK.md`
// §11.2.
//
// ── WHY A PARSER, AND WHY THAT WAS RULED RATHER THAN CHOSEN ────────────────
// Four refutation rounds over this change produced defects in three different
// string-level designs, and EVERY ONE was the same class — a regex reading XML:
//
//   R1  selecting a subtree deleted a run that followed `w:sdtContent`
//       inside the same control; a drug name vanished from a well-formed doc.
//   R1  two `w:sdtContent` children → greedy capture → orphan/unclosed tags.
//   R1  `<w:sdt />` (self-closing WITH a space) matched the opening pattern.
//   R2  deleting the `w:sdtPr` subtree removed a Wingdings `w:sym`, a
//       signature `w:drawing`, and raw text.
//   R2  whitespace inside a wrapper tag shipped malformed XML silently.
//   R3  `<w:t xml:space="preserve"/>` read as an unclosed open → FALSE
//       REFUSAL → the hollow PDF, i.e. the defect itself. Also quadratic:
//       65 seconds of blocked event loop.
//   R4  a comment guard whose regex spanned BETWEEN two comments; a carrier
//       check reading comment text as markup; a prefix check reading a
//       PREFIX SPELLING so a default-namespace document was a silent no-op.
//
// ⚠️ THE TELL IS THAT THE LAST TWO ROUNDS FOUND DEFECTS IN THE GUARDS, NOT IN
// THE UNWRAPPING. Round four fuzzed 728 well-formed variants against the
// string version's tag removal and could not break it; every surviving failure
// was in the hand-written machinery that tried to recognise comments, CDATA and
// namespace prefixes — the things a parser already knows.
//
//     A DETERMINISTIC HEURISTIC DOING SYNTAX WILL ALWAYS HAVE ONE MORE
//     COUNTEREXAMPLE. STOP WRITING PARSERS.
//
// So the instrument changed rather than the regex. This parses with the same
// `fast-xml-parser` the template compiler uses, MOVES nodes, and serializes.
//
// ── WHY IT IS CONTENT-PRESERVING BY CONSTRUCTION ───────────────────────────
// Nodes are MOVED, never re-created, matched, classified or rebuilt. A child of
// `w:sdtContent` is pushed into the control's parent as the SAME OBJECT; every
// other child of the control — `w:sdtPr`, `w:sdtEndPr`, and the trailing runs
// ruling #174 keeps as static content — is pushed through untouched. There is
// no list of things to delete and no shape to recognise, so there is no
// enumeration that can be incomplete.
//
// ── WHAT IT COSTS, NAMED SO IT IS NOT DISCOVERED LATER ─────────────────────
// 1 · SERIALIZATION IS NOT BYTE-IDENTICAL. A parse/build round trip re-emits
//     the part; measured on the real form, a no-op round trip changes 163,002
//     bytes to 196,270 while preserving all 138 `w:t` runs in identical
//     sequence. That is acceptable HERE and nowhere else: this output is the
//     converter's input only, a presentation artifact. The bytes served to
//     Word are never touched. The run-sequence check below is the guard that
//     makes the trade safe rather than hopeful.
// 2 · Unwrapping removes the STRUCTURE marking which text is a filled field.
//     For a PDF that is correct — it is a RENDERING, not a data carrier — but
//     nothing may re-read a generated PDF expecting controls. The DOCX remains
//     the structured artifact.
//
// MEASURED, through the real converter on the real customer form, BEFORE this
// replaced the string version — with a no-op round trip as the positive
// control so the comparison could fail:
//     string flatten          28/28 fills   54,821 B   2,329 chars
//     DOM unwrap              28/28 fills   54,821 B   2,329 chars
//     no-op round trip only    1/28 fills   82,061 B   2,154 chars
// The rendered PDF is byte-identical to the design it replaces.
// ============================================================================
import { XMLBuilder, XMLParser } from 'fast-xml-parser';

/** The WordprocessingML namespace. The prefix bound to it is read, never assumed. */
const W_NS = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main';

/**
 * ⚠️ THESE OPTIONS ARE THE CONTRACT AND MUST MATCH ON BOTH SIDES.
 * `preserveOrder` keeps mixed content in document order; `processEntities:
 * false` leaves `&amp;` and friends exactly as authored, so an escaped
 * character cannot be silently decoded into a different document;
 * `trimValues: false` keeps significant whitespace, which `xml:space="preserve"`
 * exists to protect; `suppressEmptyNode: true` re-emits `<w:x/>` rather than
 * inflating it to `<w:x></w:x>`.
 */
const XML_OPTIONS = {
  preserveOrder: true as const,
  ignoreAttributes: false as const,
  attributeNamePrefix: '@_',
  trimValues: false as const,
  parseTagValue: false as const,
  parseAttributeValue: false as const,
  processEntities: false as const,
  suppressEmptyNode: true as const,
};

type Node = Record<string, unknown>;

/** The element name of an ordered-XML node (the one key that is not `:@`). */
function tagOf(node: Node): string | undefined {
  for (const key of Object.keys(node)) if (key !== ':@') return key;
  return undefined;
}

function localName(tag: string): string {
  const colon = tag.indexOf(':');
  return colon === -1 ? tag : tag.slice(colon + 1);
}

/**
 * The prefix bound to the WordprocessingML namespace on the root element, or
 * `null` for a default binding.
 *
 * ⚠️ READ, NEVER ASSUMED — and the previous version's defect is why. It tested
 * for the literal text `w:sdt` and reported a clean success on any document
 * using another prefix: a SILENT no-op, which is the outcome its own comment
 * claimed to prevent. A default-namespace document defeated it entirely.
 */
function wordPrefix(tree: Node[]): { prefix: string | null; bound: boolean } {
  for (const node of tree) {
    const tag = tagOf(node);
    if (!tag || tag === '?xml' || tag === '#text' || tag === '#comment') continue;
    const attrs = (node[':@'] ?? {}) as Record<string, string>;
    for (const [name, value] of Object.entries(attrs)) {
      if (value !== W_NS) continue;
      if (name === '@_xmlns') return { prefix: null, bound: true };
      if (name.startsWith('@_xmlns:')) return { prefix: name.slice('@_xmlns:'.length), bound: true };
    }
    // only the root element is inspected; a part that does not declare the
    // namespace at all is reported unbound so the caller can refuse it
    return { prefix: null, bound: false };
  }
  return { prefix: null, bound: false };
}

/** Every text value in the tree, in document order. Comments are NOT text. */
function textNodes(nodes: Node[], out: string[] = []): string[] {
  for (const node of nodes) {
    const tag = tagOf(node);
    if (tag === undefined) continue;
    if (tag === '#text') {
      out.push(String(node[tag]));
      continue;
    }
    const kids = node[tag];
    if (Array.isArray(kids)) textNodes(kids as Node[], out);
  }
  return out;
}

/**
 * Move every control's content into the control's parent and drop the control.
 *
 * The recursion runs INNERMOST-FIRST by construction — a control's children are
 * unwrapped before the control itself is dissolved — so nesting needs no
 * special case and there is no pairing to get wrong.
 */
function unwrap(nodes: Node[], isSdt: (t: string) => boolean, isContent: (t: string) => boolean): Node[] {
  const out: Node[] = [];
  for (const node of nodes) {
    const tag = tagOf(node);
    if (tag === undefined) {
      out.push(node);
      continue;
    }
    const kids = node[tag];
    const walked = Array.isArray(kids)
      ? unwrap(kids as Node[], isSdt, isContent)
      : null;

    if (isSdt(tag)) {
      // dissolve: hoist w:sdtContent's children, keep every OTHER child as-is
      for (const child of walked ?? []) {
        const childTag = tagOf(child);
        if (childTag !== undefined && isContent(childTag) && Array.isArray(child[childTag])) {
          out.push(...(child[childTag] as Node[]));
        } else {
          out.push(child);
        }
      }
      continue;
    }
    out.push(walked ? ({ ...node, [tag]: walked } as Node) : node);
  }
  return out;
}

function anyControlRemains(nodes: Node[], isSdt: (t: string) => boolean, isContent: (t: string) => boolean): boolean {
  for (const node of nodes) {
    const tag = tagOf(node);
    if (tag === undefined) continue;
    if (isSdt(tag) || isContent(tag)) return true;
    const kids = node[tag];
    if (Array.isArray(kids) && anyControlRemains(kids as Node[], isSdt, isContent)) return true;
  }
  return false;
}

/**
 * Unwrap every content control in a WordprocessingML part.
 *
 * @throws when the part cannot be unwrapped safely — the caller keeps the
 * ORIGINAL bytes for that part. A hollow PDF is the defect being fixed; a PDF
 * missing a drug name is worse than either, and a FALSE refusal lands on the
 * hollow PDF, so both directions are held to the same standard.
 */
export function flattenContentControls(xml: string): string {
  const tree = new XMLParser(XML_OPTIONS).parse(xml, true) as Node[];

  const { prefix, bound } = wordPrefix(tree);
  if (!bound) {
    throw new Error('flattenContentControls: the part does not declare the WordprocessingML namespace');
  }
  const qualified = (name: string) => (prefix === null ? name : `${prefix}:${name}`);
  const sdtTag = qualified('sdt');
  const contentTag = qualified('sdtContent');
  const isSdt = (t: string) => t === sdtTag;
  const isContent = (t: string) => t === contentTag;

  // Fast path AFTER parsing, so it is a fact about the DOCUMENT rather than
  // about a spelling. The string version's equivalent check read literal text
  // and no-opped silently on any other prefix.
  if (!anyControlRemains(tree, isSdt, isContent)) return xml;

  const before = textNodes(tree);
  const unwrapped = unwrap(tree, isSdt, isContent);
  const after = textNodes(unwrapped);

  // ⚠️ THE GUARD THAT MAKES SERIALIZATION DRIFT SAFE RATHER THAN HOPEFUL. It
  // compares the ORDERED text sequence BOTH ways, because a rule about
  // faithfulness forbids REMOVING as well as manufacturing, and it reads the
  // PARSED tree — so a comment, a CDATA section or an escaped entity is
  // whatever the parser says it is, not whatever a pattern guessed. Every
  // round-four string-level defect lived in the version of this check that
  // read raw text.
  if (after.length !== before.length || after.some((t, i) => t !== before[i])) {
    throw new Error(
      `flattenContentControls: text changed (${before.length} -> ${after.length}); refusing to convert this part`,
    );
  }
  if (anyControlRemains(unwrapped, isSdt, isContent)) {
    throw new Error('flattenContentControls: a control survived unwrapping');
  }
  return new XMLBuilder(XML_OPTIONS).build(unwrapped) as string;
}
