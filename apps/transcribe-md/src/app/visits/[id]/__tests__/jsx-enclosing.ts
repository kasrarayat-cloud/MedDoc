// ============================================================================
// `enclosingOpenTags` — the ANCESTORS of a JSX mount, not its NEIGHBOURS.
//
// ⚠️ WHY THIS EXISTS. The "no caller supplies the bridge" guards used to slice
// a ±400-character window around the mount and assert `qm-rounds-host` was not
// in it. That worked while the mount had no hosted siblings. The moment
// `review-document-view` gained two inline `.qm-rdoc-gate` panels that
// correctly carry their own bridge, the window saw one of them and reported a
// wrapper that does not exist — a FALSE POSITIVE on a correct tree.
//
// PROXIMITY IN SOURCE IS NOT PARENTHOOD. The question the guard means to ask is
// structural, so it is answered structurally: walk the tag stack up to the
// mount and return the attribute text of every element still OPEN there. A
// sibling has been closed by then; a wrapper has not.
//
// One implementation, used by both card guards. A second copy would drift from
// the first the day either is fixed.
// ============================================================================

/** Attribute text of every JSX element still open at `index`, outermost first. */
export function enclosingOpenTags(code: string, index: number): string[] {
  const stack: { name: string; attrs: string }[] = [];
  let i = 0;
  while (i < index && i < code.length) {
    if (code[i] !== '<') {
      i += 1;
      continue;
    }
    // Closing tag: `</Name>` or `</>`.
    if (code[i + 1] === '/') {
      const end = code.indexOf('>', i);
      if (end === -1) break;
      stack.pop();
      i = end + 1;
      continue;
    }
    // An opening tag must start with a letter, `_`, or be a fragment `<>`.
    if (!/[A-Za-z_>]/.test(code[i + 1] ?? '')) {
      i += 1;
      continue;
    }
    // Read the tag name.
    let j = i + 1;
    while (j < code.length && /[\w.:-]/.test(code[j])) j += 1;
    const name = code.slice(i + 1, j);

    // Walk attributes to the tag's own `>`, respecting quotes and braces so a
    // `>` inside `className={cond ? 'a' : 'b'}` or a template literal does not
    // end the tag early.
    let depth = 0;
    let quote: string | null = null;
    let k = j;
    for (; k < code.length; k += 1) {
      const c = code[k];
      if (quote) {
        if (c === quote) quote = null;
        continue;
      }
      if (c === '"' || c === "'" || c === '`') {
        quote = c;
        continue;
      }
      if (c === '{') depth += 1;
      else if (c === '}') depth -= 1;
      else if (c === '>' && depth === 0) break;
    }
    if (k >= code.length) break;
    const attrs = code.slice(j, k);
    const selfClosing = code[k - 1] === '/';
    if (!selfClosing) stack.push({ name, attrs });
    i = k + 1;
  }
  return stack.map((s) => s.attrs);
}
