// ============================================================================
// Template Twin — BULLET GROUPS, ruling #313 ("ONE ITEM PER BULLET").
// ----------------------------------------------------------------------------
// A form that repeats one list-valued control as bullets ("Past Medical
// History" ×3, "Plan" ×5) wants each dictated item on its own bullet. Before
// anything can be placed, the controls that form ONE list have to be found —
// and this module is the only place that decides that. It has two readers:
//
//   · `list-distribution.ts` — the pass that places one item per bullet;
//   · `validation/index.ts`  — which checks, over a STORED manifest, that no
//                              item was dropped or printed twice and that
//                              every unused bullet is a legitimate one.
//
// ⚠️ ONE RULE, TWO READERS, AND THEY MUST NOT DISAGREE. If the validator
// grouped differently from the writer, a correct distribution would be refused
// (a withheld document) or a lossy one accepted (a signed note missing an
// item). Both import `bulletGroups`; nobody re-states it.
//
// ⚠️ NARROW, AND A DOUBT REFUSES THE WHOLE GROUP. Every rule below must hold for
// EVERY member, or no member is grouped and each keeps its per-field
// resolution — today's output, byte for byte. A group is never SPLIT: two
// sub-runs would each get "item 1", which is a repeat by construction.
//
// ⚠️ MEMBERSHIP IS RECOMPUTED FROM THE IR ON EVERY FILL AND NEVER STORED.
// `fieldId` is salted with the whole-package sha, so a membership list keyed
// by it would describe a different document after any re-upload.
//
// ⚠️ IT IMPORTS `ir.ts` (AND SO ZOD) FOR ONE REASON: rule G7's compared key set
// is DERIVED from `SemanticMappingSchema`'s own keys. A hand-written key list
// would silently stop comparing the next attribute somebody adds to a mapping.
// No input is parsed here; the module is pure.
// ============================================================================

import {
  SemanticMappingSchema,
  type SemanticMapping,
  type TemplateField,
} from './ir';
import { isListValuedNarrative } from './field-value-derivation';
import { normalizeConcept } from './fact-mapping-match';
import { FILL_IN_LABEL } from './prose-form/derive-prose-twin';

/**
 * The mapping keys that name WHICH control a mapping belongs to, rather than
 * what it means. They differ between members by definition, so they are the
 * only keys G7 does not compare.
 */
export const BULLET_GROUP_IDENTITY_KEYS: readonly string[] = ['fieldId'];

/**
 * Every OTHER key of `SemanticMappingSchema` — DERIVED, never listed. A key
 * added to the schema tomorrow is compared by default (the fail-closed
 * direction: members must then agree on it too). An arm pins the derived list
 * so the addition is also SEEN, not merely absorbed.
 */
export const BULLET_GROUP_COMPARED_MAPPING_KEYS: readonly string[] = Object.keys(
  SemanticMappingSchema.shape,
).filter((key) => !BULLET_GROUP_IDENTITY_KEYS.includes(key));

export type BulletGroupRefusal =
  /** G1 — a member is not a plain narrative content control (table cell,
   *  repeating row, legacy field, unsupported, laterality-critical). */
  | 'member_kind'
  /** G2 — members live in different parts (header vs body). */
  | 'member_part'
  /** G3 — a member's identity is not a DECLARED alias + tag shared byte-for-
   *  byte by every member. */
  | 'member_identity'
  /** G4 — a member is not the only control in its paragraph, or the IR
   *  predates the property (absent means no group). */
  | 'member_not_sole_in_paragraph'
  /** G5 — members are not one unbroken run of display order. */
  | 'members_not_one_run'
  /** G6 — members carry different scaffold text. */
  | 'member_scaffold_differs'
  /** G7 — a member has no mapping, or one that is not list-valued. */
  | 'member_mapping_not_list_valued'
  /** G7 — members' mappings differ on a compared key. */
  | 'member_mappings_differ';

export interface BulletGroup {
  /** Members in DISPLAY ORDER, which is the order items are placed in. */
  readonly memberFieldIds: readonly string[];
  readonly partName: string;
  readonly alias: string;
  readonly tag: string;
}

export interface BulletGroupAnalysis {
  readonly groups: readonly BulletGroup[];
  /** Candidates that shared a declared identity and were refused IN FULL. */
  readonly refused: ReadonlyArray<{
    readonly memberFieldIds: readonly string[];
    readonly reason: BulletGroupRefusal;
    /** The first mapping key that differed, for `member_mappings_differ`. */
    readonly key?: string;
  }>;
}

/**
 * One mapping attribute, in the form two members must agree on.
 *
 * ⚠️ THE COMPARISON IS THE MATCHER'S OWN, NEVER A LOOSER ONE. The concept (and
 * the synonym and scope sets) are compared after `normalizeConcept` — exactly
 * the spelling comparison `conceptMatches` performs — and NOT after the
 * registry's `canonicalConcept`: two members mapped to registry SYNONYMS
 * (`impression` / `assessment`) admit DIFFERENT fact sets at the matcher, so a
 * fact placed on one could fail `SOURCE_FACT_CONCEPT_MISMATCH` on the other.
 * Absent, `undefined` and `null` compare equal, because every reader of these
 * keys treats them the same (`unmentionedPolicy` is read as `=== 'omit'`, a
 * `conceptScope` is read only when non-empty).
 */
function comparable(key: string, mapping: SemanticMapping): unknown {
  const value = (mapping as unknown as Record<string, unknown>)[key];
  switch (key) {
    case 'clinicalConcept':
      return typeof value === 'string' ? normalizeConcept(value) : null;
    case 'approvedSynonyms':
    case 'conceptScope':
      return [
        ...new Set(
          (Array.isArray(value) ? (value as unknown[]) : []).map((entry) =>
            normalizeConcept(String(entry)),
          ),
        ),
      ].sort();
    default:
      return value === undefined ? null : value;
  }
}

/** G1 — a plain, body-or-part narrative content control and nothing else. */
function isPlainNarrativeControl(field: TemplateField): boolean {
  const binding = field.rendererBinding;
  return (
    field.kind === 'narrative_text' &&
    field.rowPrototype === false &&
    field.tableId === null &&
    binding.bindingType === 'content_control' &&
    binding.repeatAncestorPath === null &&
    binding.tableIndex === null &&
    binding.rowIndex === null &&
    binding.cellIndex === null &&
    field.detectionStatus !== 'unsupported' &&
    field.criticality !== 'laterality'
  );
}

function refuse(
  members: readonly TemplateField[],
  reason: BulletGroupRefusal,
  key?: string,
): BulletGroupAnalysis['refused'][number] {
  return {
    memberFieldIds: members.map((field) => field.fieldId),
    reason,
    ...(key ? { key } : {}),
  };
}

/**
 * The first rule a candidate set of controls breaks, or `null` when every rule
 * holds for every member. `members` is in display order.
 */
function firstBrokenRule(
  members: readonly TemplateField[],
  allFields: readonly TemplateField[],
  mappingById: ReadonlyMap<string, SemanticMapping>,
): { reason: BulletGroupRefusal; key?: string } | null {
  // G1 — kind.
  if (!members.every(isPlainNarrativeControl)) return { reason: 'member_kind' };

  // G2 — part.
  const partName = members[0]!.rendererBinding.partName;
  if (!members.every((field) => field.rendererBinding.partName === partName)) {
    return { reason: 'member_part' };
  }

  // G3 — declared identity: the label comes FROM the alias, and alias and tag
  // are both present and byte-equal. A label derived from surrounding text, a
  // table header or a counter is not an identity the document declares.
  const { alias, tag } = members[0]!.rendererBinding;
  if (
    alias === null ||
    tag === null ||
    !members.every(
      (field) =>
        field.labelSource === 'alias' &&
        field.rendererBinding.alias === alias &&
        field.rendererBinding.tag === tag,
    )
  ) {
    return { reason: 'member_identity' };
  }

  // G4 — sole control in its paragraph. ABSENT MEANS NO GROUP: every IR stored
  // before #313 keeps today's behaviour until its IR carries the property.
  if (!members.every((field) => field.soleParagraphControl === true)) {
    return { reason: 'member_not_sole_in_paragraph' };
  }

  // G5 — one unbroken run. The compiler's display counter is shared by fields,
  // tables, static paragraphs and refused controls, so consecutive integers
  // mean nothing at all sits between two members. Duplicated or interleaved
  // orders (which the compiler never emits) are refused rather than trusted.
  const orders = members.map((field) => field.displayOrder);
  for (let index = 1; index < orders.length; index += 1) {
    if (orders[index] !== orders[index - 1]! + 1) return { reason: 'members_not_one_run' };
  }
  const memberIds = new Set(members.map((field) => field.fieldId));
  const low = orders[0]!;
  const high = orders[orders.length - 1]!;
  if (
    allFields.some(
      (field) =>
        !memberIds.has(field.fieldId) &&
        field.displayOrder >= low &&
        field.displayOrder <= high,
    )
  ) {
    return { reason: 'members_not_one_run' };
  }

  // G6 — same scaffold. Side or relation words written INSIDE the control
  // ("Right: ___" / "Left: ___") are what this catches.
  const first = members[0]!;
  if (
    !members.every(
      (field) =>
        field.scaffolded === first.scaffolded && field.scaffoldText === first.scaffoldText,
    )
  ) {
    return { reason: 'member_scaffold_differs' };
  }

  // G7 — a list-valued mapping, identical on every compared key.
  const mappings: SemanticMapping[] = [];
  for (const field of members) {
    const mapping = mappingById.get(field.fieldId);
    if (!mapping || !isListValuedNarrative(field, mapping)) {
      return { reason: 'member_mapping_not_list_valued' };
    }
    mappings.push(mapping);
  }
  for (const key of BULLET_GROUP_COMPARED_MAPPING_KEYS) {
    const expected = JSON.stringify(comparable(key, mappings[0]!));
    if (mappings.some((mapping) => JSON.stringify(comparable(key, mapping)) !== expected)) {
      return { reason: 'member_mappings_differ', key };
    }
  }
  return null;
}

/**
 * Every bullet group in this IR under these mappings, plus every candidate that
 * was refused and why.
 *
 * CANDIDATES are found by DECLARED IDENTITY ONLY: two controls sharing an alias
 * OR a tag (anywhere in the package) belong to one candidate, transitively. A
 * candidate is then accepted whole or refused whole. Linking by either key is
 * the narrow direction — a control that shares only a tag with a bullet run is
 * a doubt about that run, and a doubt refuses it.
 */
export function analyzeBulletGroups(
  fields: readonly TemplateField[],
  mappings: readonly SemanticMapping[],
): BulletGroupAnalysis {
  const mappingById = new Map<string, SemanticMapping>();
  const duplicated = new Set<string>();
  for (const mapping of mappings) {
    if (mappingById.has(mapping.fieldId)) duplicated.add(mapping.fieldId);
    else mappingById.set(mapping.fieldId, mapping);
  }
  // A duplicated mapping is a doubt (the validator reports it as
  // DUPLICATE_MAPPING); the id is removed so no group can form through it.
  for (const fieldId of duplicated) mappingById.delete(fieldId);

  // Union-find over declared identity keys.
  const parent = new Map<string, string>();
  const find = (id: string): string => {
    let root = id;
    while (parent.get(root) !== root) root = parent.get(root)!;
    let cursor = id;
    while (parent.get(cursor) !== root) {
      const next = parent.get(cursor)!;
      parent.set(cursor, root);
      cursor = next;
    }
    return root;
  };
  const union = (a: string, b: string): void => {
    const rootA = find(a);
    const rootB = find(b);
    if (rootA !== rootB) parent.set(rootB, rootA);
  };
  const ownerOfKey = new Map<string, string>();
  for (const field of fields) {
    parent.set(field.fieldId, field.fieldId);
  }
  for (const field of fields) {
    const keys = [
      // ⚠️ #325 — the generic `Fill-in` alias is NOT an identity for grouping. It is
      // shared by EVERY bare slot in a form, so linking on it would merge all of them
      // into one component (which G5 then refuses). The S2 numbered slots of one
      // section instead share a `pdfsec:<concept>` TAG and link on THAT. G3 still
      // demands alias+tag byte-equal across a group, which the identical Fill-in
      // alias + identical section tag satisfy.
      field.rendererBinding.alias !== null && field.rendererBinding.alias !== FILL_IN_LABEL
        ? `alias\0${field.rendererBinding.alias}`
        : null,
      field.rendererBinding.tag !== null ? `tag\0${field.rendererBinding.tag}` : null,
    ].filter((key): key is string => key !== null);
    for (const key of keys) {
      const owner = ownerOfKey.get(key);
      if (owner === undefined) ownerOfKey.set(key, field.fieldId);
      else union(owner, field.fieldId);
    }
  }

  const components = new Map<string, TemplateField[]>();
  for (const field of fields) {
    // Only controls that declare an identity can be linked at all.
    if (field.rendererBinding.alias === null && field.rendererBinding.tag === null) continue;
    const root = find(field.fieldId);
    const list = components.get(root) ?? [];
    list.push(field);
    components.set(root, list);
  }

  const groups: BulletGroup[] = [];
  const refused: Array<BulletGroupAnalysis['refused'][number]> = [];
  for (const component of components.values()) {
    if (component.length < 2) continue;
    const members = [...component].sort(
      (a, b) => a.displayOrder - b.displayOrder || a.fieldId.localeCompare(b.fieldId),
    );
    const broken = firstBrokenRule(members, fields, mappingById);
    if (broken) {
      refused.push(refuse(members, broken.reason, broken.key));
      continue;
    }
    const binding = members[0]!.rendererBinding;
    groups.push({
      memberFieldIds: members.map((field) => field.fieldId),
      partName: binding.partName,
      alias: binding.alias!,
      tag: binding.tag!,
    });
  }

  const firstOrder = (ids: readonly string[]): number =>
    fields.find((field) => field.fieldId === ids[0])?.displayOrder ?? 0;
  groups.sort((a, b) => firstOrder(a.memberFieldIds) - firstOrder(b.memberFieldIds));
  refused.sort((a, b) => firstOrder(a.memberFieldIds) - firstOrder(b.memberFieldIds));
  return { groups, refused };
}

/** Every accepted bullet group, members in display order. THE shared rule. */
export function bulletGroups(
  fields: readonly TemplateField[],
  mappings: readonly SemanticMapping[],
): readonly BulletGroup[] {
  return analyzeBulletGroups(fields, mappings).groups;
}
