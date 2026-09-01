import { createHash } from "node:crypto";

import { canonicalSha256 } from "../template-twin/canonical";
import {
  TEMPLATE_TWIN_COMPILER_VERSION,
  TEMPLATE_TWIN_IR_SCHEMA_VERSION,
  TemplateDocIRSchema,
  type RendererBinding,
  type TemplateDocIR,
  type TemplateField,
  type TemplateTable,
  type UnsupportedElement,
} from "../template-twin/ir";
import { failTemplateDocx } from "./errors";
import {
  detectFieldHygiene,
  fieldHygieneDetail,
  FIELD_LEFTOVER_CONTENT,
} from "./field-hygiene";
import type { TemplateDocxLimits } from "./limits";
import { withoutPlaceholderOptions } from "./placeholder-option";
import {
  inspectDocxPackage,
  type InspectedDocxPackage,
} from "./package-security";
import {
  childrenOf,
  descendants,
  directChild,
  directChildren,
  getAttribute,
  localName,
  parseOrderedXml,
  tagOf,
  visibleText,
  type OrderedXmlNode,
} from "./xml";

const DOCX_MIME =
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document" as const;
const MAX_TABLE_ROWS = 100;

type TemplateDocNode = TemplateDocIR["nodes"][number];
type TemplateDocPart = TemplateDocIR["parts"][number];
type TemplateTableCell = TemplateTable["cells"][number];

export interface CompileTemplateDocxOptions {
  limits?: Partial<TemplateDocxLimits>;
}

interface MutableTableContext {
  tableId: string;
  tableIndex: number;
  rowIndex: number;
  /** Laterality of the CURRENT row, stamped from the document's own leg
   *  heading rows. 'unknown' when the document gives no signal — never
   *  inferred from row ordering, because a template that orders legs
   *  differently would then silently mis-place every measurement. */
  rowLaterality: 'right' | 'left' | 'unknown';
  cellIndex: number;
  cellFieldIds: string[];
  repeatAncestorPath: string | null;
}

interface WalkContext {
  partName: string;
  table: MutableTableContext | null;
  repeatAncestorPath: string | null;
  containerText: string | null;
  insideFieldContent: boolean;
}

interface CompilerState {
  sourceSha256: string;
  limits: TemplateDocxLimits;
  fields: TemplateField[];
  tables: TemplateTable[];
  nodes: TemplateDocNode[];
  unsupported: UnsupportedElement[];
  unsupportedKeys: Set<string>;
  nextDisplayOrder: number;
  nextBindingOrdinal: number;
  tableCountByPart: Map<string, number>;
  comboBoxes: number;
}

interface TableRowLocation {
  node: OrderedXmlNode;
  path: string;
  repeatAncestorPath: string | null;
}

export function compileTemplateDocx(
  source: Uint8Array,
  options: CompileTemplateDocxOptions = {},
): TemplateDocIR {
  const inspected = inspectDocxPackage(source, options.limits);
  const state: CompilerState = {
    sourceSha256: inspected.sourceSha256,
    limits: inspected.limits,
    fields: [],
    tables: [],
    nodes: [],
    unsupported: [],
    unsupportedKeys: new Set(),
    nextDisplayOrder: 0,
    nextBindingOrdinal: 0,
    tableCountByPart: new Map(),
    comboBoxes: 0,
  };

  const parsedParts = new Map<string, OrderedXmlNode[]>();
  const structuralParts = [
    inspected.mainPartName,
    ...inspected.headerPartNames,
    ...inspected.footerPartNames,
  ];

  for (const partName of structuralParts) {
    const entry = inspected.zip.entries.get(partName);
    if (!entry) failTemplateDocx("OPC_REQUIRED_PART_MISSING");
    const tree = parseOrderedXml(entry.bytes, inspected.limits);
    parsedParts.set(partName, tree);
    walkNodes(tree, "", defaultContext(partName), state);
  }

  const parts = buildPartManifest(inspected, parsedParts);
  const staticContentSha256 = canonicalSha256(
    parts.map((part) => ({
      partName: part.partName,
      staticSha256: part.staticSha256,
    })),
  );
  // ⚠️ THE HYGIENE FINDINGS ARE EXCLUDED FROM THE STRUCTURE HASH, AND THIS IS
  // NOT AN OPTIMISATION — IT IS THE DIFFERENCE BETWEEN A NEW ADVISORY AND AN
  // OUTAGE.
  //
  // `structureSha256` is what `assertSourceMatchesIr` compares on EVERY fill,
  // against the STORED IR of every template already compiled. Moving it does
  // not stale a fixture: it makes every CERTIFIED TWIN IN THE DATABASE
  // unfillable — production's included — and each recompute path degrades
  // SILENTLY to the styled export. `gate-twin-certified-pin-matches-compiler`
  // caught this the moment #163's findings joined the register, and its own
  // remediation is the rule followed here: *if the change is only about what a
  // READER shows, filter at the reader and leave the stored identity alone.*
  //
  // A hygiene finding IS a reader concern. It describes what a doctor will SEE
  // in an unfilled field; it says nothing about the document's STRUCTURE, which
  // is what this hash identifies. Two templates differing only in whether a
  // placeholder was cleaned are structurally the same template.
  const structureSha256 = canonicalSha256({
    fields: state.fields,
    tables: state.tables,
    nodes: state.nodes,
    unsupported: state.unsupported.filter(
      (item) => item.code !== FIELD_LEFTOVER_CONTENT,
    ),
  });

  const candidate: TemplateDocIR = {
    irSchemaVersion: TEMPLATE_TWIN_IR_SCHEMA_VERSION,
    compilerVersion: TEMPLATE_TWIN_COMPILER_VERSION,
    source: {
      sha256: inspected.sourceSha256,
      sizeBytes: inspected.zip.source.length,
      mimeType: DOCX_MIME,
    },
    parts,
    nodes: state.nodes,
    fields: state.fields,
    tables: state.tables,
    unsupported: state.unsupported,
    structureSha256,
    staticContentSha256,
    stats: {
      totalFields: state.fields.length,
      dropdowns:
        state.fields.filter((field) => field.kind === "single_select").length -
        state.comboBoxes,
      comboBoxes: state.comboBoxes,
      checkboxes: state.fields.filter((field) => field.kind === "checkbox")
        .length,
      dateControls: state.fields.filter((field) => field.kind === "date")
        .length,
      tables: state.tables.length,
      repeatingTables: state.tables.filter(
        (table) => table.kind === "repeating_table",
      ).length,
      headers: inspected.headerPartNames.length,
      footers: inspected.footerPartNames.length,
      unsupported: state.unsupported.length,
      blockingUnsupported: state.unsupported.filter(
        (item) => item.blocksCertification,
      ).length,
    },
  };

  const result = TemplateDocIRSchema.safeParse(candidate);
  if (!result.success) failTemplateDocx("IR_VALIDATION_FAILED");
  return result.data;
}

function defaultContext(partName: string): WalkContext {
  return {
    partName,
    table: null,
    repeatAncestorPath: null,
    containerText: null,
    insideFieldContent: false,
  };
}

function walkNodes(
  nodes: OrderedXmlNode[],
  parentPath: string,
  context: WalkContext,
  state: CompilerState,
): void {
  const siblingCounts = new Map<string, number>();

  for (const node of nodes) {
    const tag = tagOf(node);
    if (!tag || tag === "?xml" || tag === "#text") continue;
    const siblingIndex = siblingCounts.get(tag) ?? 0;
    siblingCounts.set(tag, siblingIndex + 1);
    const nodePath = structuralPath(parentPath, tag, siblingIndex, state);
    const local = localName(tag);

    if (local === "tbl") {
      processTable(node, nodePath, context, state);
      continue;
    }
    if (local === "sdt") {
      processContentControl(node, nodePath, context, state);
      continue;
    }
    if (local === "p") {
      processParagraph(node, nodePath, context, state);
      continue;
    }
    if (local === "fldChar" && getAttribute(node, "fldCharType") === "begin") {
      processLegacyField(node, nodePath, context, state);
      continue;
    }
    if (local === "fldSimple") {
      inspectDynamicField(
        getAttribute(node, "instr") ?? "",
        node,
        nodePath,
        context,
        state,
      );
    } else if (local === "instrText") {
      inspectDynamicField(visibleText(node), node, nodePath, context, state);
    } else if (local === "altChunk") {
      addUnsupported(state, {
        code: "ALT_CHUNK_UNSUPPORTED",
        partName: context.partName,
        path: nodePath,
        label: null,
        detail:
          "Imported alternative-format content is not supported in Template Twin v1.",
        clinicallyMaterial: true,
        blocksCertification: true,
      });
    }

    walkNodes(childrenOf(node), nodePath, context, state);
  }
}

function processParagraph(
  node: OrderedXmlNode,
  nodePath: string,
  context: WalkContext,
  state: CompilerState,
): void {
  const text = normalizeLabel(visibleText(node));
  const hasFillableDescendant =
    descendants(node, "sdt").length > 0 ||
    descendants(node, "fldChar").some(
      (field) => getAttribute(field, "fldCharType") === "begin",
    );

  if (text && !hasFillableDescendant && !context.insideFieldContent) {
    addNode(state, {
      partName: context.partName,
      path: nodePath,
      kind: "static",
      fieldId: null,
      tableId: context.table?.tableId ?? null,
      staticTextSha256: hashText(text),
      bookmarkNames: bookmarkNames(node),
    });
  }

  walkNodes(
    childrenOf(node),
    nodePath,
    { ...context, containerText: text || null },
    state,
  );
}

function processContentControl(
  node: OrderedXmlNode,
  nodePath: string,
  context: WalkContext,
  state: CompilerState,
): void {
  const properties = directChild(node, "sdtPr");
  const content = directChild(node, "sdtContent");
  if (!properties || !content) {
    addUnsupported(state, {
      code: "MALFORMED_CONTENT_CONTROL",
      partName: context.partName,
      path: nodePath,
      label: null,
      detail:
        "A content control is missing its properties or content container.",
      clinicallyMaterial: true,
      blocksCertification: true,
    });
    if (content) {
      walkNodes(
        childrenOf(content),
        childPath(nodePath, content, node, state),
        context,
        state,
      );
    }
    return;
  }

  const contentPath = childPath(nodePath, content, node, state);
  const isRepeatingSection =
    descendants(properties, "repeatingSection").length > 0;
  const isRepeatingItem =
    descendants(properties, "repeatingSectionItem").length > 0;
  if (isRepeatingSection || isRepeatingItem) {
    const repeatPath = isRepeatingSection
      ? nodePath
      : (context.repeatAncestorPath ?? nodePath);
    if (isRepeatingSection && descendants(content, "tbl").length === 0) {
      addUnsupported(state, {
        code: "NON_TABLE_REPEATING_SECTION",
        partName: context.partName,
        path: nodePath,
        label: contentControlIdentity(properties).label,
        detail:
          "Only table-backed repeating sections are supported in Template Twin v1.",
        clinicallyMaterial: true,
        blocksCertification: true,
      });
    }
    walkNodes(
      childrenOf(content),
      contentPath,
      { ...context, repeatAncestorPath: repeatPath },
      state,
    );
    return;
  }

  const identity = contentControlIdentity(properties);
  const dataBound = descendants(properties, "dataBinding").length > 0;
  const dropdown = directChild(properties, "dropDownList");
  const comboBox = directChild(properties, "comboBox");
  const checkBox = descendants(properties, "checkbox")[0];
  const date = directChild(properties, "date");
  const plainText = directChild(properties, "text");
  const unsupportedType = [
    "picture",
    "group",
    "docPartObj",
    "bibliography",
    "citation",
    "equation",
  ].find((name) => descendants(properties, name).length > 0);

  if (unsupportedType) {
    addUnsupportedContentControl(
      state,
      context,
      nodePath,
      identity.label,
      "UNSUPPORTED_CONTENT_CONTROL",
      "This Word content-control type cannot be populated in Template Twin v1.",
    );
    walkNodes(
      childrenOf(content),
      contentPath,
      { ...context, insideFieldContent: true },
      state,
    );
    return;
  }

  let kind: TemplateField["kind"];
  let allowedOptions: TemplateField["allowedOptions"] = [];
  let ambiguousChoiceOptions = false;
  if (dropdown || comboBox) {
    const optionContainer = dropdown ?? comboBox!;
    // ⚠️ THE ORDINAL IS THE DOCUMENT'S OWN INDEX, ASSIGNED BEFORE ANY FILTERING.
    // It is persisted on manifests and overrides and, on the legacy path, is
    // written back as `w:result val` — an index into the document's untouched
    // list. It must never be renumbered. See `placeholder-option.ts`.
    allowedOptions = directChildren(optionContainer, "listItem").map(
      (item, ordinal) => {
        const displayText =
          getAttribute(item, "displayText") ??
          getAttribute(item, "value") ??
          "";
        return {
          ordinal,
          displayText,
          value: getAttribute(item, "value") ?? displayText,
        };
      },
    );
    // ⚠️ THE PERSISTED ARRAY IS THE DOCUMENT'S, VERBATIM. THE FILTER IS A LOCAL
    // VIEW FOR THE VALIDATION DECISION ONLY — AND THAT DISTINCTION IS THE WHOLE
    // POINT OF THIS SHAPE.
    //
    // An earlier version assigned `withoutPlaceholderOptions(...)` straight into
    // `allowedOptions`, so the placeholder never reached the IR. It read as the
    // safest possible change and it BROKE EVERY TEMPLATE ALREADY COMPILED.
    //
    // `renderer.ts:assertSourceMatchesIr` RE-COMPILES the immutable source on
    // EVERY fill and compares the result against the STORED IR — by
    // `structureSha256` and by `canonicalSha256(fields)`. Shrinking the option
    // array moves both (structureSha256 is `canonicalSha256({fields, tables,
    // nodes, unsupported})`, so one change fires two legs), while
    // `compilerVersion` stays `1.0.0` and says nothing. Measured on QA:
    // **10 of 10** CERTIFIED twins began failing `SOURCE_IR_MISMATCH`, options
    // 153 -> 125 — exactly the 28 single-selects, one placeholder each. The only
    // certified twin in production carries the identical 80/153/28, so it would
    // have stopped filling the moment this shipped: every recompute path
    // degrades silently to the STYLED export, and a signature freezes a NULL
    // pointer, permanently.
    //
    // ⚠️ AND THE FEATURE THIS SHIPPED WITH WAS ITS OWN TRIGGER — a clinician's
    // form-control correction moves `overridesSha256`, which is precisely what
    // forces the recompute that then refuses.
    //
    // So the placeholder is excluded WHERE IT IS READ, never where it is
    // STORED. A compile-time filter is not another layer of safety — it is a
    // change to an artifact other code has already hashed.
    //
    // ⚠️ AND THE READER LIST IS ENUMERATED, NEVER REMEMBERED. An earlier
    // version of this note said "three readers", named three, and the SAME
    // DIFF touched five — while a SIXTH went unfiltered and unnoticed. Naming
    // a class is not enumerating it. The filtering readers today are:
    //
    //   1. `set-template-control.ts`        the clinician's door
    //   2. `clinician-override.ts`          the override overlay
    //   3. `editable-controls.ts`           the list the edit door addresses
    //   4. `picks-bridge.ts`                writes a clinical value
    //   5. `resolver/index.ts`              selects a clinical value
    //   6. `semantic-mapping/index.ts`      the payload SENT TO THE MODEL
    //
    // ⚠️ #6 was missed because the arm that appeared to cover it —
    // "never OFFERS the placeholder to the model" — measured
    // `listEditableFormControls` (#3), a DIFFERENT surface that merely also
    // has a model on the other end. Two things named "the model" is what hid
    // it. `gate-f24-s5-compiled-ir-is-stable.test.ts` now asserts both by name.
    //
    // ⚠️ THE ENUMERATION IS A HAND-KEPT LIST AND HAND-KEPT LISTS GO STALE.
    // The structural answer is a single `selectableOptions(field)` accessor
    // that every reader is forced through — filed as a follow-up rather than
    // done here, because it is a wider refactor than an IR-stability fix
    // should carry. Until then: the predicate for a reader that needs this is
    // *"does it put an option in front of a human, a model, or a document?"*
    // — grep `allowedOptions` and classify, never recall.
    const selectableOptions = withoutPlaceholderOptions(allowedOptions);
    // Validation runs on the REAL option set, with the placeholder discounted: a
    // control whose only entry was Word's placeholder offers no clinical choice
    // at all, and SELECT_OPTIONS_INVALID is the honest verdict for it. This
    // decision is UNCHANGED by the shape above — it just reads the local view.
    if (
      selectableOptions.length === 0 ||
      selectableOptions.some((option) => !option.displayText)
    ) {
      addUnsupportedContentControl(
        state,
        context,
        nodePath,
        identity.label,
        "SELECT_OPTIONS_INVALID",
        "A native choice control has no complete, ordered option list.",
      );
      walkNodes(
        childrenOf(content),
        contentPath,
        { ...context, insideFieldContent: true },
        state,
      );
      return;
    }
    ambiguousChoiceOptions = hasDuplicateChoiceOptions(allowedOptions);
    if (ambiguousChoiceOptions) {
      addUnsupported(state, {
        code: "AMBIGUOUS_SELECT_OPTIONS",
        partName: context.partName,
        path: nodePath,
        label: identity.label,
        detail:
          "A native choice control contains duplicate display text or values and requires physician review.",
        clinicallyMaterial: true,
        blocksCertification: true,
      });
    }
    kind = "single_select";
    if (comboBox) state.comboBoxes += 1;
  } else if (checkBox) {
    kind = "checkbox";
  } else if (date) {
    kind = "date";
  } else if (plainText || childrenOf(content).length > 0) {
    // Rich-text content controls have no dedicated type child in w:sdtPr.
    kind = inferTextKind(identity.label ?? context.containerText ?? "");
  } else {
    addUnsupportedContentControl(
      state,
      context,
      nodePath,
      identity.label,
      "UNRECOGNIZED_CONTENT_CONTROL",
      "The content-control type could not be identified deterministically.",
    );
    return;
  }

  if (dataBound) {
    addUnsupported(state, {
      code: "DATA_BOUND_CONTENT_CONTROL",
      partName: context.partName,
      path: nodePath,
      label: identity.label,
      detail:
        "Data-bound controls require an explicit physician-approved replacement mapping.",
      clinicallyMaterial: true,
      blocksCertification: true,
    });
  }

  const fieldId = stableId(
    "ttf_",
    24,
    state.sourceSha256,
    context.partName,
    nodePath,
    kind,
  );
  const label = chooseFieldLabel(
    identity,
    context.containerText,
    state.fields.length + 1,
  );
  const binding: RendererBinding = {
    partName: context.partName,
    bindingType: "content_control",
    path: nodePath,
    ordinal: state.nextBindingOrdinal++,
    sdtId: trimNullable(identity.id, 80),
    tag: trimNullable(identity.tag, 240),
    alias: trimNullable(identity.alias, 240),
    legacyName: null,
    tableIndex: context.table?.tableIndex ?? null,
    rowIndex: context.table?.rowIndex ?? null,
    rowLaterality: context.table?.rowLaterality ?? 'unknown',
    cellIndex: context.table?.cellIndex ?? null,
    repeatAncestorPath: context.repeatAncestorPath,
    sourceControlSha256: canonicalSha256(node),
    originalContentSha256: canonicalSha256(content),
  };
  const field: TemplateField = {
    fieldId,
    kind,
    originalLabel: label.label,
    labelSource: label.source,
    displayOrder: state.nextDisplayOrder++,
    detectionStatus:
      dataBound || ambiguousChoiceOptions
        ? "unsupported"
        : comboBox ||
            label.source === "generated" ||
            label.source === "same_container"
          ? "needs_confirmation"
          : "recognized",
    allowedOptions,
    rendererBinding: binding,
    required: false,
    unknownPolicy: "blank",
    clinicallyMaterial: true,
    criticality: inferCriticality(label.label, kind),
    tableId: context.table?.tableId ?? null,
    rowPrototype: context.repeatAncestorPath !== null,
  };
  pushField(field, context, state, content);
  addNode(
    state,
    {
      partName: context.partName,
      path: nodePath,
      kind,
      fieldId,
      tableId: context.table?.tableId ?? null,
      staticTextSha256: null,
      bookmarkNames: bookmarkNames(node),
    },
    field.displayOrder,
  );

  walkNodes(
    childrenOf(content),
    contentPath,
    { ...context, insideFieldContent: true },
    state,
  );
}

function processLegacyField(
  node: OrderedXmlNode,
  nodePath: string,
  context: WalkContext,
  state: CompilerState,
): void {
  const formData = descendants(node, "ffData")[0];
  if (!formData) return;
  const legacyName =
    descendants(formData, "name")
      .map((name) => getAttribute(name, "val"))
      .find(Boolean) ?? null;
  const dropdown = descendants(formData, "ddList")[0];
  const checkbox = descendants(formData, "checkBox")[0];
  const textInput = descendants(formData, "textInput")[0];

  let kind: TemplateField["kind"];
  let allowedOptions: TemplateField["allowedOptions"] = [];
  let ambiguousChoiceOptions = false;
  if (dropdown) {
    kind = "single_select";
    // Same rule as the content-control path above, and applied HERE rather than
    // on that path alone so a future legacy template cannot inherit the defect
    // by being the case somebody forgot. ⚠️ POPULATION FACT: production holds
    // ZERO legacy `ffData` choice fields today (measured 2026-08-24 — all 28
    // single-selects on the certified twin are content controls), so this arm
    // is currently UNEXERCISED. It re-arms the first time a doctor uploads a
    // .doc-era template carrying `w:ddList` form fields, with no code change.
    allowedOptions = descendants(dropdown, "listEntry").map((entry, ordinal) => {
      const value = getAttribute(entry, "val") ?? "";
      return { ordinal, displayText: value, value };
    });
    // ⚠️ SAME SHAPE AS THE CONTENT-CONTROL PATH, AND FOR THE SAME REASON —
    // persist the document's array, filter only the local view. See the long
    // note there. Applied HERE TOO rather than on that path alone so a legacy
    // template cannot inherit the IR-instability defect by being the case
    // somebody forgot. It is also strictly MORE faithful on this path: the
    // ordinal is written back as `w:result val`, an index into the document's
    // own untouched `listEntry` array, so the IR now carries exactly what the
    // renderer indexes into.
    const selectableOptions = withoutPlaceholderOptions(allowedOptions);
    if (
      selectableOptions.length === 0 ||
      selectableOptions.some((option) => !option.value)
    ) {
      addUnsupportedLegacy(state, context, nodePath, legacyName);
      return;
    }
    ambiguousChoiceOptions = hasDuplicateChoiceOptions(selectableOptions);
    if (ambiguousChoiceOptions) {
      addUnsupported(state, {
        code: "AMBIGUOUS_SELECT_OPTIONS",
        partName: context.partName,
        path: nodePath,
        label: trimNullable(legacyName, 240),
        detail:
          "A legacy choice field contains duplicate options and requires physician review.",
        clinicallyMaterial: true,
        blocksCertification: true,
      });
    }
  } else if (checkbox) {
    kind = "checkbox";
  } else if (textInput) {
    const typeValue = descendants(textInput, "type")
      .map((type) => getAttribute(type, "val")?.toLowerCase())
      .find(Boolean);
    kind = typeValue?.includes("number")
      ? "number"
      : typeValue?.includes("date")
        ? "date"
        : inferTextKind(legacyName ?? "");
  } else {
    addUnsupportedLegacy(state, context, nodePath, legacyName);
    return;
  }

  const label =
    normalizeLabel(legacyName ?? "") ||
    `Legacy field ${state.fields.length + 1}`;
  const labelSource = legacyName ? "legacy_name" : "generated";
  const fieldId = stableId(
    "ttf_",
    24,
    state.sourceSha256,
    context.partName,
    nodePath,
    kind,
  );
  const binding: RendererBinding = {
    partName: context.partName,
    bindingType: "legacy_form_field",
    path: nodePath,
    ordinal: state.nextBindingOrdinal++,
    sdtId: null,
    tag: null,
    alias: null,
    legacyName: trimNullable(legacyName, 240),
    tableIndex: context.table?.tableIndex ?? null,
    rowIndex: context.table?.rowIndex ?? null,
    rowLaterality: context.table?.rowLaterality ?? 'unknown',
    cellIndex: context.table?.cellIndex ?? null,
    repeatAncestorPath: context.repeatAncestorPath,
    sourceControlSha256: canonicalSha256(node),
    originalContentSha256: canonicalSha256(formData),
  };
  const displayOrder = state.nextDisplayOrder++;
  const field: TemplateField = {
    fieldId,
    kind,
    originalLabel: label.slice(0, 240),
    labelSource,
    displayOrder,
    detectionStatus: ambiguousChoiceOptions
      ? "unsupported"
      : legacyName
        ? "recognized"
        : "needs_confirmation",
    allowedOptions,
    rendererBinding: binding,
    required: false,
    unknownPolicy: "blank",
    clinicallyMaterial: true,
    criticality: inferCriticality(label, kind),
    tableId: context.table?.tableId ?? null,
    rowPrototype: context.repeatAncestorPath !== null,
  };
  pushField(field, context, state, formData);
  addNode(
    state,
    {
      partName: context.partName,
      path: nodePath,
      kind,
      fieldId,
      tableId: context.table?.tableId ?? null,
      staticTextSha256: null,
      bookmarkNames: bookmarkNames(node),
    },
    displayOrder,
  );
}

function processTable(
  node: OrderedXmlNode,
  nodePath: string,
  context: WalkContext,
  state: CompilerState,
): void {
  if (state.tables.length >= state.limits.maxTables) {
    failTemplateDocx("DOCUMENT_STRUCTURE_LIMIT_EXCEEDED");
  }
  const tableIndex = state.tableCountByPart.get(context.partName) ?? 0;
  state.tableCountByPart.set(context.partName, tableIndex + 1);
  const tableId = stableId(
    "ttb_",
    20,
    state.sourceSha256,
    context.partName,
    nodePath,
  );
  const rows = collectTableRows(
    node,
    nodePath,
    context.partName,
    context.repeatAncestorPath,
    state,
  );
  const repeatPrototypeRow = rows.findIndex(
    (row) => row.repeatAncestorPath !== null,
  );
  const kind: TemplateTable["kind"] =
    context.repeatAncestorPath || repeatPrototypeRow >= 0
      ? "repeating_table"
      : "fixed_table";
  const displayOrder = state.nextDisplayOrder++;
  const cells: TemplateTableCell[] = [];
  const table: TemplateTable = {
    tableId,
    partName: context.partName,
    path: nodePath,
    kind,
    displayOrder,
    gridColumnWidths: directChild(node, "tblGrid")
      ? directChildren(directChild(node, "tblGrid")!, "gridCol").map((column) =>
          nonnegativeInteger(getAttribute(column, "w")),
        )
      : [],
    rowCount: rows.length,
    repeatPrototypeRow:
      kind === "repeating_table" ? Math.max(0, repeatPrototypeRow) : null,
    maxRows: MAX_TABLE_ROWS,
    cells,
  };
  state.tables.push(table);
  addNode(
    state,
    {
      partName: context.partName,
      path: nodePath,
      kind,
      fieldId: null,
      tableId,
      staticTextSha256: null,
      bookmarkNames: bookmarkNames(node),
    },
    displayOrder,
  );

  const tableHeaderLabels = new Map<number, string>();
  // Leg heading rows ("RIGHT LEG", "DIAMETER AND REFLUX TIME — Left Leg") split
  // a single grid into per-leg blocks. Read them in document order and carry
  // the current leg forward; a row before any heading stays 'unknown'.
  const rowLegs = new Map<number, 'right' | 'left' | 'unknown'>();
  let currentLeg: 'right' | 'left' | 'unknown' = 'unknown';
  rows.forEach((row, rowIndex) => {
    const rowText = normalizeLabel(visibleText(row.node)).toLowerCase();
    // Require the word "leg"/"extremity" or a standalone side token so an
    // incidental "left" inside prose cannot flip the block.
    if (/\b(right)\b/.test(rowText) && !/\bleft\b/.test(rowText)) currentLeg = 'right';
    else if (/\bleft\b/.test(rowText) && !/\bright\b/.test(rowText)) currentLeg = 'left';
    rowLegs.set(rowIndex, currentLeg);
    let logicalColumnStart = 0;
    const rowCells = directChildrenWithPaths(row.node, row.path, "tc", state);
    rowCells.forEach((cellLocation, cellIndex) => {
      const cell = cellLocation.node;
      const properties = directChild(cell, "tcPr");
      const gridSpan = Math.max(
        1,
        positiveInteger(
          properties
            ? getAttribute(directChild(properties, "gridSpan") ?? {}, "val")
            : undefined,
        ),
      );
      const verticalMergeNode = properties
        ? directChild(properties, "vMerge")
        : undefined;
      const verticalMerge: TemplateTableCell["verticalMerge"] =
        !verticalMergeNode
          ? "none"
          : getAttribute(verticalMergeNode, "val") === "restart"
            ? "restart"
            : "continue";
      const fieldIds: string[] = [];
      const nestedTableCount = countNestedTables(cell);
      const cellText = normalizeLabel(visibleText(cell));
      cells.push({
        rowIndex,
        cellIndex,
        logicalColumnStart,
        gridSpan,
        verticalMerge,
        nestedTableCount,
        fieldIds,
        staticTextSha256: computeStaticXmlSha256([cell]),
      });

      const repeatAncestorPath =
        row.repeatAncestorPath ?? context.repeatAncestorPath;
      const cellContext: WalkContext = {
        ...context,
        table: {
          tableId,
          tableIndex,
          rowIndex,
          rowLaterality: rowLegs.get(rowIndex) ?? 'unknown',
          cellIndex,
          cellFieldIds: fieldIds,
          repeatAncestorPath,
        },
        repeatAncestorPath,
        containerText: cellText || context.containerText,
      };
      walkNodes(childrenOf(cell), cellLocation.path, cellContext, state);

      if (
        fieldIds.length === 0 &&
        !cellText &&
        nestedTableCount === 0 &&
        verticalMerge !== "continue"
      ) {
        const leftLabel =
          cellIndex > 0
            ? normalizeLabel(visibleText(rowCells[cellIndex - 1]!.node))
            : "";
        const headerLabel = tableHeaderLabels.get(logicalColumnStart) ?? "";
        createAmbiguousTableCellField(
          cell,
          cellLocation.path,
          cellContext,
          leftLabel
            ? { label: leftLabel, source: "left_cell" }
            : headerLabel
              ? { label: headerLabel, source: "table_header" }
              : {
                  label: `Table ${tableIndex + 1}, row ${rowIndex + 1}, column ${logicalColumnStart + 1}`,
                  source: "generated",
                },
          state,
        );
      }

      if (rowIndex === 0 && cellText) {
        for (
          let column = logicalColumnStart;
          column < logicalColumnStart + gridSpan;
          column += 1
        ) {
          tableHeaderLabels.set(column, cellText);
        }
      }
      logicalColumnStart += gridSpan;
    });
  });
}

function createAmbiguousTableCellField(
  cell: OrderedXmlNode,
  cellPath: string,
  context: WalkContext,
  label: { label: string; source: "left_cell" | "table_header" | "generated" },
  state: CompilerState,
): void {
  const kind = inferTextKind(label.label);
  const fieldId = stableId(
    "ttf_",
    24,
    state.sourceSha256,
    context.partName,
    cellPath,
    kind,
  );
  const displayOrder = state.nextDisplayOrder++;
  const field: TemplateField = {
    fieldId,
    kind,
    originalLabel: normalizeLabel(label.label),
    labelSource: label.source,
    displayOrder,
    detectionStatus: "needs_confirmation",
    allowedOptions: [],
    rendererBinding: {
      partName: context.partName,
      bindingType: "table_cell",
      path: cellPath,
      ordinal: state.nextBindingOrdinal++,
      sdtId: null,
      tag: null,
      alias: null,
      legacyName: null,
      tableIndex: context.table?.tableIndex ?? null,
      rowIndex: context.table?.rowIndex ?? null,
    rowLaterality: context.table?.rowLaterality ?? 'unknown',
      cellIndex: context.table?.cellIndex ?? null,
      repeatAncestorPath: context.repeatAncestorPath,
      sourceControlSha256: canonicalSha256(cell),
      originalContentSha256: canonicalSha256(cell),
    },
    required: false,
    unknownPolicy: "blank",
    clinicallyMaterial: true,
    criticality: inferCriticality(label.label, kind),
    tableId: context.table?.tableId ?? null,
    rowPrototype: context.repeatAncestorPath !== null,
  };
  pushField(field, context, state, cell);
  addNode(
    state,
    {
      partName: context.partName,
      path: cellPath,
      kind,
      fieldId,
      tableId: context.table?.tableId ?? null,
      staticTextSha256: null,
      bookmarkNames: bookmarkNames(cell),
    },
    displayOrder,
  );
}

function collectTableRows(
  table: OrderedXmlNode,
  tablePath: string,
  partName: string,
  inheritedRepeatPath: string | null,
  state: CompilerState,
): TableRowLocation[] {
  const rows: TableRowLocation[] = [];

  const walk = (
    nodes: OrderedXmlNode[],
    parentPath: string,
    repeatPath: string | null,
  ): void => {
    const siblingCounts = new Map<string, number>();
    for (const node of nodes) {
      const tag = tagOf(node);
      if (!tag || tag === "#text") continue;
      const index = siblingCounts.get(tag) ?? 0;
      siblingCounts.set(tag, index + 1);
      const nodePath = structuralPath(parentPath, tag, index, state);
      const local = localName(tag);
      if (local === "tbl") continue;
      if (local === "tr") {
        rows.push({ node, path: nodePath, repeatAncestorPath: repeatPath });
        continue;
      }
      let nextRepeatPath = repeatPath;
      if (local === "sdt") {
        const properties = directChild(node, "sdtPr");
        if (properties) {
          const isRepeatingSection =
            descendants(properties, "repeatingSection").length > 0;
          const isRepeatingItem =
            descendants(properties, "repeatingSectionItem").length > 0;
          if (isRepeatingSection || (isRepeatingItem && !nextRepeatPath)) {
            nextRepeatPath = nodePath;
          } else if (!isRepeatingItem && descendants(node, "tr").length > 0) {
            addUnsupported(state, {
              code: "ROW_CONTAINER_CONTENT_CONTROL",
              partName,
              path: nodePath,
              label: contentControlIdentity(properties).label,
              detail:
                "A non-repeating content control wraps a table row and requires physician review.",
              clinicallyMaterial: true,
              blocksCertification: true,
            });
          }
        }
      }
      walk(childrenOf(node), nodePath, nextRepeatPath);
    }
  };

  walk(childrenOf(table), tablePath, inheritedRepeatPath);
  return rows;
}

function directChildrenWithPaths(
  parent: OrderedXmlNode,
  parentPath: string,
  wantedLocalName: string,
  state: CompilerState,
): Array<{ node: OrderedXmlNode; path: string }> {
  const matches: Array<{ node: OrderedXmlNode; path: string }> = [];
  const siblingCounts = new Map<string, number>();
  for (const node of childrenOf(parent)) {
    const tag = tagOf(node);
    if (!tag || tag === "#text") continue;
    const index = siblingCounts.get(tag) ?? 0;
    siblingCounts.set(tag, index + 1);
    if (localName(tag) === wantedLocalName) {
      matches.push({
        node,
        path: structuralPath(parentPath, tag, index, state),
      });
    }
  }
  return matches;
}

function inspectDynamicField(
  instruction: string,
  node: OrderedXmlNode,
  nodePath: string,
  context: WalkContext,
  state: CompilerState,
): void {
  const normalized = instruction.trim().toUpperCase();
  if (
    !normalized ||
    /^(?:PAGE|NUMPAGES|SECTION|SECTIONPAGES|DATE|TIME)\b/.test(normalized)
  ) {
    return;
  }
  if (!/^(?:IF|FILLIN|ASK)\b/.test(normalized) && !normalized.startsWith("="))
    return;

  addUnsupported(state, {
    code: "DYNAMIC_FIELD_UNSUPPORTED",
    partName: context.partName,
    path: nodePath,
    label: null,
    detail:
      "A dynamic Word field requires physician review and is not fillable in Template Twin v1.",
    clinicallyMaterial: true,
    blocksCertification: true,
  });
  addNode(state, {
    partName: context.partName,
    path: nodePath,
    kind: "conditional_block",
    fieldId: null,
    tableId: context.table?.tableId ?? null,
    staticTextSha256: canonicalSha256(node),
    bookmarkNames: bookmarkNames(node),
  });
}

function buildPartManifest(
  inspected: InspectedDocxPackage,
  parsedParts: ReadonlyMap<string, OrderedXmlNode[]>,
): TemplateDocPart[] {
  const headers = new Set(inspected.headerPartNames);
  const footers = new Set(inspected.footerPartNames);
  return [...inspected.zip.entries]
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([partName, entry]) => {
      const sha256 = hashBytes(entry.bytes);
      const tree = parsedParts.get(partName);
      return {
        partName,
        contentType: inspected.contentTypes.get(partName)!,
        kind: partKind(partName, headers, footers),
        sha256,
        staticSha256: tree ? computeStaticXmlSha256(tree) : sha256,
        relationshipCount: inspected.relationshipCounts.get(partName) ?? 0,
      };
    });
}

/** Hashes OOXML structure while masking only content-control result bodies. */
export function computeStaticXmlSha256(tree: OrderedXmlNode[]): string {
  return canonicalSha256(tree.map(maskMutableContent));
}

function maskMutableContent(node: OrderedXmlNode): unknown {
  const tag = tagOf(node);
  const attributes = node[":@"] ? { ...node[":@"] } : undefined;
  const local = localName(tag);
  const rawValue = node[tag];
  let value: unknown;

  if (local === "sdtContent") {
    value = [{ "#template-twin-mutable": "" }];
  } else if (Array.isArray(rawValue)) {
    value = (rawValue as OrderedXmlNode[]).map(maskMutableContent);
  } else {
    value = rawValue ?? "";
  }
  return attributes ? { [tag]: value, ":@": attributes } : { [tag]: value };
}

function pushField(
  field: TemplateField,
  context: WalkContext,
  state: CompilerState,
  /**
   * ⚠️ #163 RULE (2) — THE FIELD'S OWN CONTENT REGION, PASSED BY ITS EMITTER.
   *
   * Each emitter already knows where its field lives: the `w:sdtContent` of a
   * content control, the `w:tc` of a table cell, the `w:ffData` of a legacy
   * form field. It is passed in rather than re-derived here, and that is the
   * lesson of #162(b) rather than a style preference — a second implementation
   * of "where does this field live" drifted from the first and hard-failed
   * every empty legacy field in a shipped build.
   */
  locus: OrderedXmlNode | null,
): void {
  if (state.fields.length >= state.limits.maxFields) {
    failTemplateDocx("DOCUMENT_STRUCTURE_LIMIT_EXCEEDED");
  }
  state.fields.push(field);
  context.table?.cellFieldIds.push(field.fieldId);

  // ⚠️ RAISED AT THE ONE CHOKE POINT EVERY FIELD PASSES THROUGH, so a future
  // field kind cannot be added without the check coming with it. A hygiene
  // sweep wired per-emitter is a sweep that is one emitter short the day
  // somebody adds the fourth.
  const hygiene = detectFieldHygiene(locus);
  if (hygiene) {
    addUnsupported(state, {
      code: FIELD_LEFTOVER_CONTENT,
      partName: field.rendererBinding.partName,
      path: field.rendererBinding.path,
      label: field.originalLabel,
      detail: fieldHygieneDetail(field.originalLabel, hygiene),
      // ⚠️ BOTH FALSE, DELIBERATELY, AND THE SECOND IS THE LOAD-BEARING ONE.
      // This does not block certification — #163 ruled it loud, not fatal — and
      // `clinicallyMaterial` is what the generic validator arm reads to decide
      // severity, so `true` here would make it blocking. `validation/index.ts`
      // grades this code BY NAME instead, and carries `detail` verbatim, so the
      // honest sentence survives the false flag.
      clinicallyMaterial: false,
      blocksCertification: false,
    });
  }
}

function addNode(
  state: CompilerState,
  input: Omit<TemplateDocNode, "nodeId" | "displayOrder">,
  displayOrder = state.nextDisplayOrder++,
): void {
  if (state.nodes.length >= state.limits.maxNodes) {
    failTemplateDocx("DOCUMENT_STRUCTURE_LIMIT_EXCEEDED");
  }
  state.nodes.push({
    nodeId: stableId(
      "ttn_",
      20,
      state.sourceSha256,
      input.partName,
      input.path,
      input.kind,
    ),
    displayOrder,
    ...input,
  });
}

function addUnsupported(state: CompilerState, item: UnsupportedElement): void {
  const key = `${item.partName}\0${item.path}\0${item.code}`;
  if (state.unsupportedKeys.has(key)) return;
  state.unsupportedKeys.add(key);
  state.unsupported.push(item);
}

function addUnsupportedContentControl(
  state: CompilerState,
  context: WalkContext,
  path: string,
  label: string | null,
  code: string,
  detail: string,
): void {
  addUnsupported(state, {
    code,
    partName: context.partName,
    path,
    label,
    detail,
    clinicallyMaterial: true,
    blocksCertification: true,
  });
  addNode(state, {
    partName: context.partName,
    path,
    kind: "unsupported",
    fieldId: null,
    tableId: context.table?.tableId ?? null,
    staticTextSha256: null,
    bookmarkNames: [],
  });
}

function addUnsupportedLegacy(
  state: CompilerState,
  context: WalkContext,
  path: string,
  label: string | null,
): void {
  addUnsupportedContentControl(
    state,
    context,
    path,
    trimNullable(label, 240),
    "UNSUPPORTED_LEGACY_FORM_FIELD",
    "A legacy Word form field could not be mapped safely.",
  );
}

function contentControlIdentity(properties: OrderedXmlNode): {
  alias: string | null;
  tag: string | null;
  id: string | null;
  label: string | null;
} {
  const alias = trimNullable(
    getAttribute(directChild(properties, "alias") ?? {}, "val"),
    240,
  );
  const tag = trimNullable(
    getAttribute(directChild(properties, "tag") ?? {}, "val"),
    240,
  );
  const id = trimNullable(
    getAttribute(directChild(properties, "id") ?? {}, "val"),
    80,
  );
  return { alias, tag, id, label: alias ?? tag };
}

function chooseFieldLabel(
  identity: ReturnType<typeof contentControlIdentity>,
  containerText: string | null,
  generatedOrdinal: number,
): { label: string; source: TemplateField["labelSource"] } {
  if (identity.alias) return { label: identity.alias, source: "alias" };
  if (identity.tag) return { label: identity.tag, source: "tag" };
  const normalizedContainer = normalizeLabel(containerText ?? "");
  if (normalizedContainer) {
    return { label: normalizedContainer, source: "same_container" };
  }
  return { label: `Field ${generatedOrdinal}`, source: "generated" };
}

function inferTextKind(label: string): TemplateField["kind"] {
  const normalized = label.toLowerCase();
  if (
    /\b(?:measurement|height|weight|length|width|diameter|temperature)\b/.test(
      normalized,
    )
  ) {
    return "measurement";
  }
  if (/\b(?:number|count|score|quantity|age)\b/.test(normalized))
    return "number";
  return "narrative_text";
}

function inferCriticality(
  label: string,
  kind: TemplateField["kind"],
): TemplateField["criticality"] {
  const normalized = label.toLowerCase();
  if (
    /\b(?:medication|medicine|drug|dose|dosage|route|frequency)\b/.test(
      normalized,
    )
  ) {
    return "medication";
  }
  if (/\b(?:allergy|allergies|adverse reaction)\b/.test(normalized))
    return "allergy";
  if (/\b(?:laterality|side|left|right|bilateral)\b/.test(normalized))
    return "laterality";
  if (
    kind === "number" ||
    kind === "measurement" ||
    /\bunit\b/.test(normalized)
  ) {
    return "number_unit";
  }
  if (kind === "date" || /\b(?:date|duration|onset)\b/.test(normalized)) {
    return "date_duration";
  }
  return "routine";
}

function hasDuplicateChoiceOptions(
  options: TemplateField["allowedOptions"],
): boolean {
  const displayTexts = new Set<string>();
  const values = new Set<string>();
  for (const option of options) {
    if (displayTexts.has(option.displayText) || values.has(option.value)) {
      return true;
    }
    displayTexts.add(option.displayText);
    values.add(option.value);
  }
  return false;
}

function childPath(
  parentPath: string,
  child: OrderedXmlNode,
  parent: OrderedXmlNode,
  state: CompilerState,
): string {
  const childTag = tagOf(child);
  let matchingIndex = 0;
  for (const candidate of childrenOf(parent)) {
    if (candidate === child) break;
    if (tagOf(candidate) === childTag) matchingIndex += 1;
  }
  return structuralPath(parentPath, childTag, matchingIndex, state);
}

function structuralPath(
  parentPath: string,
  tag: string,
  siblingIndex: number,
  state: CompilerState,
): string {
  const value = `${parentPath}/${tag}[${siblingIndex}]`;
  if (value.length > state.limits.maxStructuralPathLength) {
    failTemplateDocx("DOCUMENT_STRUCTURE_LIMIT_EXCEEDED");
  }
  return value;
}

function bookmarkNames(node: OrderedXmlNode): string[] {
  return [
    ...new Set(
      descendants(node, "bookmarkStart")
        .map((bookmark) => getAttribute(bookmark, "name"))
        .filter((name): name is string => Boolean(name) && name !== "_GoBack")
        .map((name) => name.slice(0, 240)),
    ),
  ];
}

function countNestedTables(cell: OrderedXmlNode): number {
  return descendants(cell, "tbl").length;
}

function partKind(
  partName: string,
  headers: ReadonlySet<string>,
  footers: ReadonlySet<string>,
): TemplateDocPart["kind"] {
  if (partName === "word/document.xml") return "document";
  if (headers.has(partName)) return "header";
  if (footers.has(partName)) return "footer";
  if (/^word\/styles[^/]*\.xml$/i.test(partName)) return "styles";
  if (/^word\/numbering[^/]*\.xml$/i.test(partName)) return "numbering";
  if (partName.endsWith(".rels")) return "relationships";
  if (/^word\/media\//i.test(partName)) return "media";
  return "other";
}

function stableId(prefix: string, length: number, ...parts: string[]): string {
  return `${prefix}${createHash("sha256").update(parts.join("\0"), "utf8").digest("hex").slice(0, length)}`;
}

function hashBytes(bytes: Uint8Array): string {
  return createHash("sha256").update(bytes).digest("hex");
}

function hashText(value: string): string {
  return createHash("sha256").update(value, "utf8").digest("hex");
}

function normalizeLabel(value: string): string {
  return value.replace(/\s+/g, " ").trim().slice(0, 240);
}

function trimNullable(
  value: string | null | undefined,
  maxLength: number,
): string | null {
  const normalized = value?.trim();
  return normalized ? normalized.slice(0, maxLength) : null;
}

function nonnegativeInteger(value: string | undefined): number {
  const parsed = Number.parseInt(value ?? "", 10);
  return Number.isSafeInteger(parsed) && parsed >= 0 ? parsed : 0;
}

function positiveInteger(value: string | undefined): number {
  const parsed = Number.parseInt(value ?? "", 10);
  return Number.isSafeInteger(parsed) && parsed > 0 ? parsed : 1;
}
