// ============================================================================
// THE KIND -> EXPECTED-TYPE SWITCH. A TRUE LEAF: NO VALUE IMPORTS, ZERO RUNTIME.
// ----------------------------------------------------------------------------
// ⚠️ THIS FILE EXISTS BECAUSE THE FIRST ATTEMPT AT THIS FIX MADE IT WORSE, AND
// A PEER SESSION'S PASS MEASURED IT.
//
// `unmentioned-policy.ts` is imported as a VALUE by the `'use client'` confirm
// surface, so everything it reaches lands in the browser bundle. The function
// below started in `semantic-mapping/index.ts`, which pulls `@meddoc/ai`
// (`modelClient`) — clearly wrong for the client. It was therefore moved to
// `ir.ts`, "which imports zod and nothing else".
//
// ⚠️ THAT REASONING WAS WRONG IN THE ONE WAY THAT MATTERED. `ir.ts` imports zod
// AS A VALUE and builds ~105 schemas at module scope, so the move traded a
// server import for a 105-schema runtime. MEASURED with the repo's own esbuild,
// browser target, minified, importing only the symbols the client component
// uses:
//
//     before the move   746 bytes, no zod
//     after the move    320,991 bytes, zod runtime present     ← 429x
//
// And the module header three lines above the import still claimed
// "NO RUNTIME IMPORTS — TYPES ONLY", which is the only thing a reader consults.
//
// So the switch lives HERE, where its only imports are `import type` and are
// erased at compile time. `ir.ts` and `semantic-mapping/index.ts` both
// re-export it, so every existing caller resolves unchanged.
//
// ⚠️ THE RULE THIS ENCODES: "leaf-safe" is a property of a module's VALUE
// imports, transitively. It is not established by the module being small, being
// types-heavy, or being called `ir`. Measure the bundle; do not reason about it.
// ============================================================================

import type { SemanticMapping, TemplateTwinFieldKind } from './ir';

export function expectedDataTypeForFieldKind(
  kind: TemplateTwinFieldKind,
): SemanticMapping['expectedDataType'] | null {
  switch (kind) {
    case 'narrative_text':
      return 'text';
    case 'single_select':
      return 'single_select';
    case 'multi_select':
      return 'multi_select';
    case 'checkbox':
      return 'boolean';
    case 'date':
      return 'date';
    case 'number':
      return 'number';
    case 'measurement':
      return 'measurement';
    case 'fixed_table':
    case 'repeating_table':
      return 'table';
    case 'static':
    case 'conditional_block':
    case 'unsupported':
      return null;
  }
}
