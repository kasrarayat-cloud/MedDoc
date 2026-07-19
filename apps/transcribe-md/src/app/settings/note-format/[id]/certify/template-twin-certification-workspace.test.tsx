import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const navigation = vi.hoisted(() => ({
  push: vi.fn(),
  replace: vi.fn(),
  refresh: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => navigation,
}));

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

import type { TemplateTwinWorkspace } from "@/lib/template-twin/client-types";
import { TEMPLATE_TWIN_STAGING_QA_TYPED_STARTER } from "@/lib/template-twin/staging-qa-fixtures";

import { TemplateTwinCertificationWorkspace } from "./template-twin-certification-workspace";

const FIELD_ID = `ttf_${"a".repeat(24)}`;
const SECOND_FIELD_ID = `ttf_${"b".repeat(24)}`;

function workspace(
  certificationStatus: TemplateTwinWorkspace["template"]["certificationStatus"] = "needs_confirmation",
  stagingQaFixtureSource = false,
): TemplateTwinWorkspace {
  const hash = "b".repeat(64);
  return {
    template: {
      id: "template-synthetic-1",
      lineageId: "lineage-synthetic-1",
      version: 2,
      name: "Synthetic follow-up template",
      encounterType: "Synthetic QA",
      status: certificationStatus === "certified" ? "active" : "draft",
      certificationStatus,
    },
    source: {
      sha256: "a".repeat(64),
      sizeBytes: 4096,
      mimeType:
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      compiledAtIso: "2026-07-17T00:00:00.000Z",
      compilerVersion: "template-docx-compiler/1.3.0",
    },
    stagingQaFixtureSource,
    stats: {
      totalFields: 1,
      dropdowns: 0,
      comboBoxes: 0,
      checkboxes: 0,
      dateControls: 0,
      tables: 0,
      repeatingTables: 0,
      headers: 0,
      footers: 0,
      unsupported: 0,
      blockingUnsupported: 0,
    },
    fields: [
      {
        definitionId: "definition-synthetic-1",
        field: {
          fieldId: FIELD_ID,
          kind: "narrative_text",
          originalLabel: "Synthetic bounded placeholder",
          labelSource: "preceding_text",
          displayOrder: 0,
          detectionStatus: "needs_confirmation",
          allowedOptions: [],
          rendererBinding: {
            partName: "word/document.xml",
            bindingType: "ordinary_placeholder",
            bindingProfile: "ORDINARY_PLACEHOLDER_TOKEN_V1",
            ordinaryPlaceholder: {
              contractVersion: "ordinary-placeholder-token-binding/1.0.0",
              tokenSyntax: "angle",
              tokenTextSha256: hash,
              tokenTextLength: 20,
              span: {
                startTextNodeIndex: 0,
                startOffset: 0,
                endTextNodeIndex: 0,
                endOffset: 20,
                paragraphTextNodeCount: 1,
              },
              staticPrefixLength: 0,
              staticSuffixLength: 0,
              staticPrefixSha256: hash,
              staticSuffixSha256: hash,
              staticContextSha256: hash,
              sourceParagraphShapeSha256: hash,
              clinicalMappingStatus: "needs_confirmation",
            },
            path: "/document/body/p[1]/r[1]/t[1]",
            canonicalPath: "/w:document[1]/w:body[1]/w:p[1]/w:r[1]/w:t[1]",
            ordinal: 0,
            sdtId: null,
            tag: null,
            alias: null,
            legacyName: null,
            tableIndex: null,
            rowIndex: null,
            cellIndex: null,
            repeatAncestorPath: null,
            canonicalRepeatAncestorPath: null,
            sourceControlSha256: hash,
            sourceBindingIdentitySha256: hash,
            certifiedBindingSha256: hash,
            originalContentSha256: hash,
          },
          required: false,
          unknownPolicy: "blank",
          clinicallyMaterial: true,
          criticality: "routine",
          tableId: null,
          rowPrototype: false,
        },
        mapping: {
          fieldId: FIELD_ID,
          clinicalConcept: null,
          expectedDataType: "text",
          polarityBehavior: "value_only",
          temporality: "any",
          laterality: "not_applicable",
          unitPolicy: "not_applicable",
          approvedSynonyms: [],
          required: false,
          blankPolicy: "blank",
          unknownPolicy: "blank",
          practiceDefault: null,
          status: "needs_confirmation",
        },
        intent: {
          intentKind: "unresolved",
          decisionId: null,
          version: null,
          supportedConcept: null,
          customConceptId: null,
          customSpec: null,
          reason: null,
          decidedAtIso: null,
          lockedInVersion: false,
        },
        customConceptScaffold: {
          templateLineageId: "lineage-synthetic-1",
          compiledVersionId: "compiled-synthetic-1",
          fieldId: FIELD_ID,
          conceptId: `ttcustom_${"c".repeat(24)}`,
        },
      },
    ],
    unsupported: [],
    mappingsSha256: "d".repeat(64),
    fieldIntentsSha256: "e".repeat(64),
    admissionChecks: [
      {
        id: "upload",
        label: "Immutable upload",
        status: "passed",
        detail: "Synthetic source admitted.",
      },
      {
        id: "malware",
        label: "Malware scan",
        status: "not_attested",
        detail: "No separate antivirus result is attested.",
      },
      {
        id: "ooxml",
        label: "OOXML package safety",
        status: "passed",
        detail: "OOXML safety passed.",
      },
      {
        id: "privacy",
        label: "PHI and privacy inspection",
        status: "passed",
        detail: "Privacy inspection passed.",
      },
      {
        id: "media",
        label: "Embedded media",
        status: "passed",
        detail: "No unapproved media.",
      },
      {
        id: "structure",
        label: "Document structure",
        status: "passed",
        detail: "Structure recognized.",
      },
    ],
    customExampleCoverage: null,
    latestSyntheticTest: null,
    canEdit: certificationStatus !== "certified",
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  window.sessionStorage.clear();
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

function selectSupportedConcept(concept = "chief_complaint") {
  fireEvent.change(screen.getByLabelText("Field intent"), {
    target: { value: "supported_concept" },
  });
  fireEvent.change(screen.getByLabelText("Clinical detail to fill"), {
    target: { value: concept },
  });
}

function savedSupportedWorkspace(
  input: TemplateTwinWorkspace,
  id = input.template.id,
) {
  const next = structuredClone(input);
  next.template.id = id;
  next.template.version += id === input.template.id ? 0 : 1;
  next.fields[0]!.mapping = {
    ...next.fields[0]!.mapping,
    clinicalConcept: "chief_complaint",
    status: "certified",
  };
  next.fields[0]!.intent = {
    intentKind: "supported_concept",
    decisionId: "decision-synthetic-1",
    version: 1,
    supportedConcept: "chief_complaint",
    customConceptId: null,
    customSpec: null,
    reason: null,
    decidedAtIso: "2026-07-19T00:00:00.000Z",
    lockedInVersion: true,
  };
  next.mappingsSha256 = "f".repeat(64);
  next.fieldIntentsSha256 = "1".repeat(64);
  return next;
}

function workspaceWithSecondField(input: TemplateTwinWorkspace) {
  const next = structuredClone(input);
  const second = structuredClone(next.fields[0]!);
  second.definitionId = "definition-synthetic-2";
  second.field.fieldId = SECOND_FIELD_ID;
  second.field.originalLabel = "Synthetic remote-only placeholder";
  second.field.displayOrder = 1;
  second.mapping.fieldId = SECOND_FIELD_ID;
  second.intent = {
    intentKind: "unresolved",
    decisionId: null,
    version: null,
    supportedConcept: null,
    customConceptId: null,
    customSpec: null,
    reason: null,
    decidedAtIso: null,
    lockedInVersion: false,
  };
  second.customConceptScaffold = second.customConceptScaffold
    ? {
        ...second.customConceptScaffold,
        fieldId: SECOND_FIELD_ID,
        conceptId: `ttcustom_${"d".repeat(24)}`,
      }
    : null;
  next.fields.push(second);
  next.stats.totalFields = 2;
  return next;
}

function setRemoteSupportedConcept(
  input: TemplateTwinWorkspace,
  fieldId: string,
  concept: string,
) {
  const field = input.fields.find((item) => item.field.fieldId === fieldId)!;
  field.mapping = {
    ...field.mapping,
    clinicalConcept: concept,
    status: "certified",
  };
  field.intent = {
    intentKind: "supported_concept",
    decisionId: `decision-${fieldId}`,
    version: 1,
    supportedConcept: concept,
    customConceptId: null,
    customSpec: null,
    reason: null,
    decidedAtIso: "2026-07-19T00:00:00.000Z",
    lockedInVersion: false,
  };
}

describe("TemplateTwinCertificationWorkspace staging integration", () => {
  it("keeps staging controls hidden when the server gate is off", () => {
    render(
      <TemplateTwinCertificationWorkspace
        initial={workspace("needs_confirmation", true)}
        stagingQaGateAllowed={false}
      />,
    );

    expect(
      screen.queryByText("Synthetic test only — not for patient care"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Start mocked-voice visit" }),
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole("option", {
        name: "Define a template-specific scalar detail",
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Approved synonyms · comma separated"),
    ).toBeInTheDocument();
  });

  it("keeps staging controls hidden for an ordinary Twin when the deployment gate is on", () => {
    render(
      <TemplateTwinCertificationWorkspace
        initial={workspace("needs_confirmation", false)}
        stagingQaGateAllowed
      />,
    );

    expect(
      screen.queryByText("Synthetic test only — not for patient care"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Start mocked-voice visit" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", {
        name: "Load reviewed synthetic mappings",
      }),
    ).not.toBeInTheDocument();
  });

  it("uses native keyboard-focusable navigation and leaves intent unresolved", () => {
    render(
      <TemplateTwinCertificationWorkspace
        initial={workspace("needs_confirmation", true)}
        stagingQaGateAllowed
      />,
    );

    const navigationRegion = screen.getByRole("navigation", {
      name: "Detected fields",
    });
    const fieldButton = within(navigationRegion).getByRole("button", {
      name: /Synthetic bounded placeholder/,
    });
    fieldButton.focus();

    expect(fieldButton).toHaveFocus();
    expect(fieldButton).toHaveAttribute("aria-current", "true");
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
    expect(
      within(navigationRegion).queryByRole("option"),
    ).not.toBeInTheDocument();
    expect(screen.getByLabelText("Field intent")).toHaveValue("unresolved");
    expect(
      screen.getAllByText(/No clinical answer is preselected/).length,
    ).toBeGreaterThan(0);
    expect(
      screen.queryByRole("option", {
        name: "Define a template-specific scalar detail",
      }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText("Approved synonyms · comma separated"),
    ).not.toBeInTheDocument();
    expect(
      screen.getByText(/accepts only the exact supported clinical detail/i),
    ).toBeInTheDocument();
  });

  it("never confirms or counts a supported-concept field with no clinical detail", () => {
    const initial = workspace("needs_confirmation", true);
    initial.fields[0]!.intent = {
      ...initial.fields[0]!.intent,
      intentKind: "supported_concept",
      supportedConcept: "",
    };
    initial.fields[0]!.mapping.status = "certified";

    render(
      <TemplateTwinCertificationWorkspace
        initial={initial}
        stagingQaGateAllowed
      />,
    );

    const summary = screen.getByRole("region", {
      name: "Detected structure summary",
    });
    expect(
      within(summary).getByText("Confirmed").parentElement,
    ).toHaveTextContent("Confirmed0/1");
    expect(
      screen.getAllByText("Needs clinical detail", { selector: "span" }).length,
    ).toBeGreaterThan(0);
    expect(
      screen.getByRole("button", { name: "Confirm this field" }),
    ).toBeDisabled();
    expect(
      screen.getByText(
        /Synthetic bounded placeholder — Clinical detail to fill:/,
      ),
    ).toBeInTheDocument();
  });

  it("keeps a native field unconfirmed until a clinical detail is selected", () => {
    const initial = workspace("needs_confirmation", false);
    initial.fields[0]!.field.rendererBinding.bindingType = "content_control";

    render(
      <TemplateTwinCertificationWorkspace
        initial={initial}
        stagingQaGateAllowed={false}
      />,
    );

    expect(screen.getByLabelText("Clinical detail to fill")).toHaveValue("");
    expect(
      screen.getByRole("button", { name: "Confirm this field" }),
    ).toBeDisabled();
    const summary = screen.getByRole("region", {
      name: "Detected structure summary",
    });
    expect(
      within(summary).getByText("Confirmed").parentElement,
    ).toHaveTextContent("Confirmed0/1");
  });

  it("allows an unconfirmed native field to remain in a partial saved draft", async () => {
    const initial = workspace("needs_confirmation", false);
    initial.fields[0]!.field.rendererBinding.bindingType = "content_control";
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      headers: new Headers(),
      json: async () => ({ ok: true, workspace: initial }),
    });
    vi.stubGlobal("fetch", fetchMock);
    render(
      <TemplateTwinCertificationWorkspace
        initial={initial}
        stagingQaGateAllowed={false}
      />,
    );

    fireEvent.change(screen.getByLabelText("Clinical detail to fill"), {
      target: { value: "chief_complaint" },
    });
    fireEvent.change(screen.getByLabelText("Clinical detail to fill"), {
      target: { value: "" },
    });
    expect(
      screen.getByRole("button", { name: "Confirm this field" }),
    ).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Save draft" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
  });

  it("identifies the exact incomplete field and setting before saving", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    render(
      <TemplateTwinCertificationWorkspace
        initial={workspace("needs_confirmation", true)}
        stagingQaGateAllowed
      />,
    );

    fireEvent.change(screen.getByLabelText("Field intent"), {
      target: { value: "supported_concept" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save draft" }));

    expect(fetchMock).not.toHaveBeenCalled();
    expect(
      await screen.findByRole("button", {
        name: "Synthetic bounded placeholder — Clinical detail to fill",
      }),
    ).toBeInTheDocument();
    expect(
      screen.getAllByText(
        "Choose a supported clinical detail before confirming this field.",
      ).length,
    ).toBeGreaterThan(0);
  });

  it("replaces the URL with the authoritative fork returned by a successful save", async () => {
    const initial = workspace("needs_confirmation", true);
    const saved = savedSupportedWorkspace(initial, "template-synthetic-2");
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      headers: new Headers(),
      json: async () => ({ ok: true, workspace: saved }),
    });
    vi.stubGlobal("fetch", fetchMock);
    render(
      <TemplateTwinCertificationWorkspace
        initial={initial}
        stagingQaGateAllowed
      />,
    );

    selectSupportedConcept();
    fireEvent.click(screen.getByRole("button", { name: "Confirm this field" }));
    fireEvent.click(screen.getByRole("button", { name: "Save draft" }));

    await waitFor(() =>
      expect(navigation.replace).toHaveBeenCalledWith(
        "/settings/note-format/template-synthetic-2/certify",
        { scroll: false },
      ),
    );
    expect(navigation.refresh).not.toHaveBeenCalled();
    expect(screen.getByText(/Version 3/)).toBeInTheDocument();
    expect(
      window.sessionStorage.getItem(
        "template-twin:certification-draft:v1:lineage-synthetic-1",
      ),
    ).toBeNull();
  });

  it("preserves and rebases an unsaved draft after a recoverable version conflict", async () => {
    const initial = workspace("needs_confirmation", true);
    const latest = workspace("needs_confirmation", true);
    latest.template.id = "template-synthetic-3";
    latest.template.version = 3;
    latest.mappingsSha256 = "7".repeat(64);
    latest.fieldIntentsSha256 = "8".repeat(64);
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 409,
      headers: new Headers(),
      json: async () => ({
        ok: false,
        code: "VERSION_CONFLICT",
        error: "This mapping draft changed in another tab.",
        recoverable: true,
        latestWorkspace: latest,
        latestTemplateId: latest.template.id,
      }),
    });
    vi.stubGlobal("fetch", fetchMock);
    render(
      <TemplateTwinCertificationWorkspace
        initial={initial}
        stagingQaGateAllowed
      />,
    );

    selectSupportedConcept();
    fireEvent.click(screen.getByRole("button", { name: "Save draft" }));

    const rebase = await screen.findByRole("button", {
      name: "Refresh and rebase unsaved draft",
    });
    expect(
      window.sessionStorage.getItem(
        "template-twin:certification-draft:v1:lineage-synthetic-1",
      ),
    ).toContain("chief_complaint");
    fireEvent.click(rebase);

    expect(screen.getByLabelText("Clinical detail to fill")).toHaveValue(
      "chief_complaint",
    );
    expect(navigation.replace).toHaveBeenCalledWith(
      "/settings/note-format/template-synthetic-3/certify",
      { scroll: false },
    );
    expect(navigation.refresh).not.toHaveBeenCalled();
    expect(
      screen.getByText("Rebased your unsaved changes onto version 3."),
    ).toBeInTheDocument();
  });

  it("three-way rebases local deltas without erasing a disjoint remote field change", async () => {
    const initial = workspaceWithSecondField(
      workspace("needs_confirmation", true),
    );
    const latest = structuredClone(initial);
    latest.template.id = "template-synthetic-3";
    latest.template.version = 3;
    latest.mappingsSha256 = "7".repeat(64);
    latest.fieldIntentsSha256 = "8".repeat(64);
    setRemoteSupportedConcept(latest, SECOND_FIELD_ID, "assessment");
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 409,
      headers: new Headers(),
      json: async () => ({
        ok: false,
        code: "VERSION_CONFLICT",
        error: "This mapping draft changed in another tab.",
        recoverable: true,
        latestWorkspace: latest,
        latestTemplateId: latest.template.id,
      }),
    });
    vi.stubGlobal("fetch", fetchMock);
    render(
      <TemplateTwinCertificationWorkspace
        initial={initial}
        stagingQaGateAllowed
      />,
    );

    selectSupportedConcept("chief_complaint");
    fireEvent.click(screen.getByRole("button", { name: "Confirm this field" }));
    fireEvent.click(screen.getByRole("button", { name: "Save draft" }));
    fireEvent.click(
      await screen.findByRole("button", {
        name: "Refresh and rebase unsaved draft",
      }),
    );

    expect(screen.getByLabelText("Clinical detail to fill")).toHaveValue(
      "chief_complaint",
    );
    fireEvent.click(
      screen.getByRole("button", {
        name: /Synthetic remote-only placeholder/,
      }),
    );
    expect(screen.getByLabelText("Clinical detail to fill")).toHaveValue(
      "assessment",
    );
    expect(
      screen.queryByText("Resolve concurrent field changes"),
    ).not.toBeInTheDocument();
  });

  it("surfaces a divergent same-field change without overwriting either value", async () => {
    const initial = workspace("needs_confirmation", true);
    const latest = structuredClone(initial);
    latest.template.id = "template-synthetic-3";
    latest.template.version = 3;
    latest.mappingsSha256 = "7".repeat(64);
    latest.fieldIntentsSha256 = "8".repeat(64);
    setRemoteSupportedConcept(latest, FIELD_ID, "assessment");
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 409,
      headers: new Headers(),
      json: async () => ({
        ok: false,
        code: "VERSION_CONFLICT",
        error: "This mapping draft changed in another tab.",
        recoverable: true,
        latestWorkspace: latest,
        latestTemplateId: latest.template.id,
      }),
    });
    vi.stubGlobal("fetch", fetchMock);
    render(
      <TemplateTwinCertificationWorkspace
        initial={initial}
        stagingQaGateAllowed
      />,
    );

    selectSupportedConcept("chief_complaint");
    fireEvent.click(screen.getByRole("button", { name: "Confirm this field" }));
    fireEvent.click(screen.getByRole("button", { name: "Save draft" }));
    fireEvent.click(
      await screen.findByRole("button", {
        name: "Refresh and rebase unsaved draft",
      }),
    );

    expect(screen.getByText("Resolve concurrent field changes")).toBeVisible();
    expect(screen.getByLabelText("Clinical detail to fill")).toHaveValue(
      "assessment",
    );
    expect(screen.getByRole("button", { name: "Save draft" })).toBeDisabled();
    expect(
      window.sessionStorage.getItem(
        "template-twin:certification-draft:v1:lineage-synthetic-1",
      ),
    ).toContain("chief_complaint");

    fireEvent.click(
      screen.getByRole("button", {
        name: "Use my unsaved draft for Synthetic bounded placeholder",
      }),
    );

    expect(screen.getByLabelText("Clinical detail to fill")).toHaveValue(
      "chief_complaint",
    );
    expect(
      screen.queryByText("Resolve concurrent field changes"),
    ).not.toBeInTheDocument();
    await waitFor(() => {
      const stored = JSON.parse(
        window.sessionStorage.getItem(
          "template-twin:certification-draft:v1:lineage-synthetic-1",
        ) ?? "null",
      ) as {
        baseTemplateId?: string;
        baseMappings?: Array<{ clinicalConcept: string | null }>;
      } | null;
      expect(stored?.baseTemplateId).toBe("template-synthetic-3");
      expect(stored?.baseMappings?.[0]?.clinicalConcept).toBe("assessment");
    });
  });

  it("ignores an immutable old workspace and navigates to its editable successor", async () => {
    const initial = workspace("needs_confirmation", true);
    const immutableOldWorkspace = structuredClone(initial);
    immutableOldWorkspace.template.status = "active";
    immutableOldWorkspace.template.certificationStatus = "certified";
    immutableOldWorkspace.canEdit = false;
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 409,
      headers: new Headers(),
      json: async () => ({
        ok: false,
        code: "VERSION_IMMUTABLE",
        error: "This version is immutable.",
        recoverable: true,
        latestWorkspace: immutableOldWorkspace,
        latestTemplateId: "template-synthetic-successor",
      }),
    });
    vi.stubGlobal("fetch", fetchMock);
    render(
      <TemplateTwinCertificationWorkspace
        initial={initial}
        stagingQaGateAllowed
      />,
    );

    selectSupportedConcept("chief_complaint");
    fireEvent.click(screen.getByRole("button", { name: "Save draft" }));
    fireEvent.click(
      await screen.findByRole("button", {
        name: "Refresh and rebase unsaved draft",
      }),
    );

    expect(navigation.replace).toHaveBeenCalledWith(
      "/settings/note-format/template-synthetic-successor/certify",
      { scroll: false },
    );
    expect(screen.getByText(/Version 2/)).toBeInTheDocument();
    expect(screen.getByLabelText("Clinical detail to fill")).toHaveValue(
      "chief_complaint",
    );
    expect(
      window.sessionStorage.getItem(
        "template-twin:certification-draft:v1:lineage-synthetic-1",
      ),
    ).toContain("chief_complaint");
    expect(navigation.refresh).not.toHaveBeenCalled();
  });

  it("restores an unsaved draft after a browser refresh", async () => {
    const initial = workspace("needs_confirmation", true);
    const first = render(
      <TemplateTwinCertificationWorkspace
        initial={initial}
        stagingQaGateAllowed
      />,
    );
    selectSupportedConcept();
    await waitFor(() =>
      expect(
        window.sessionStorage.getItem(
          "template-twin:certification-draft:v1:lineage-synthetic-1",
        ),
      ).toContain("chief_complaint"),
    );
    first.unmount();

    render(
      <TemplateTwinCertificationWorkspace
        initial={workspace("needs_confirmation", true)}
        stagingQaGateAllowed
      />,
    );

    await waitFor(() =>
      expect(screen.getByLabelText("Clinical detail to fill")).toHaveValue(
        "chief_complaint",
      ),
    );
    expect(
      screen.getByText(
        /Recovered unsaved mapping changes from this browser tab/,
      ),
    ).toBeInTheDocument();
  });

  it("uses the reviewed staging static reason without exposing free text", () => {
    render(
      <TemplateTwinCertificationWorkspace
        initial={workspace("needs_confirmation", true)}
        stagingQaGateAllowed
      />,
    );

    fireEvent.change(screen.getByLabelText("Field intent"), {
      target: { value: "static" },
    });

    expect(
      screen.getByText(
        "Physician marked this reviewed synthetic fixture field as intentionally static.",
      ),
    ).toBeInTheDocument();
    expect(
      screen.queryByPlaceholderText(
        "Explain why this visible token is intentional fixed text.",
      ),
    ).not.toBeInTheDocument();
  });

  it("loads reviewed mappings only as an unsaved synthetic-fixture draft", async () => {
    const initial = workspace("needs_confirmation", true);
    const reviewedMapping = {
      ...initial.fields[0]!.mapping,
      clinicalConcept: "chief_complaint",
      status: "certified" as const,
      unknownPolicy: "requires_input" as const,
      blankPolicy: "blank" as const,
      required: true,
    };
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      headers: new Headers(),
      json: async () => ({
        ok: true,
        reviewed: {
          contractVersion: "template-twin-staging-reviewed-mappings/1.0.0",
          fixture: {
            sha256: initial.source.sha256,
            sizeBytes: initial.source.sizeBytes,
          },
          template: {
            id: initial.template.id,
            version: initial.template.version,
          },
          expectedMappingsSha256: initial.mappingsSha256,
          expectedFieldIntentsSha256: initial.fieldIntentsSha256,
          mappings: [reviewedMapping],
          fieldIntents: [
            {
              fieldId: FIELD_ID,
              intentKind: "supported_concept",
              supportedConcept: "chief_complaint",
            },
          ],
          physicianReviewSummary: {
            title: "Physician review of the synthetic mapping set",
            fixtureLabel: "Template Twin Synthetic QA Fixture",
            fieldCount: 8,
            fields: [
              {
                fieldId: FIELD_ID,
                fieldLabel: "Synthetic bounded placeholder",
                clinicalConcept: "chief_complaint",
                clinicalDetailLabel: "Chief concern",
                settings: {
                  expectedDataType: "text",
                  polarityBehavior: "not_applicable",
                  temporality: "any",
                  laterality: "not_applicable",
                  unitPolicy: "not_applicable",
                  whenNotStated: "requires_input",
                  requiredBeforeSigning: true,
                },
              },
            ],
            settings: {
              approvedSynonyms: "none",
              practiceDefaults: "none",
              blankPolicy: "blank",
              missingClinicalDetail: "requires_input",
              requiredBeforeSigning: true,
            },
            explicitConfirmationRequired: true,
            activationPerformed: false,
          },
        },
      }),
    });
    vi.stubGlobal("fetch", fetchMock);
    render(
      <TemplateTwinCertificationWorkspace
        initial={initial}
        stagingQaGateAllowed
      />,
    );

    fireEvent.click(
      screen.getByRole("button", { name: "Load reviewed synthetic mappings" }),
    );

    expect(
      await screen.findByText("Physician review of the synthetic mapping set"),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Clinical detail to fill")).toHaveValue(
      "chief_complaint",
    );
    expect(screen.getByRole("button", { name: "Save draft" })).toBeEnabled();
    expect(
      screen.getAllByText(/Activation has not occurred/).length,
    ).toBeGreaterThan(0);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0]![0]).toBe(
      "/api/note-templates/template-twin/template-synthetic-1/staging-qa/reviewed-mappings",
    );
    expect(navigation.replace).not.toHaveBeenCalled();
    expect(navigation.refresh).not.toHaveBeenCalled();
  });

  it("anchors the server-provided retry duration despite workstation clock skew and preserves the draft", async () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-07-19T05:00:00.000Z"));
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 429,
      headers: new Headers({ "Retry-After": "60" }),
      json: async () => ({
        ok: false,
        code: "RATE_LIMITED",
        error: "Mapping saves are temporarily paused.",
        retryAfterSec: 60,
        limitType: "mapping_save",
        resetAtIso: "2026-07-19T01:01:00.000Z",
      }),
    });
    vi.stubGlobal("fetch", fetchMock);
    render(
      <TemplateTwinCertificationWorkspace
        initial={workspace("needs_confirmation", true)}
        stagingQaGateAllowed
      />,
    );

    selectSupportedConcept();
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Save draft" }));
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(
      screen.getByRole("button", { name: "Retry save in 1m 00s" }),
    ).toBeDisabled();
    expect(
      screen.getByText("Mapping save available in 1m 00s"),
    ).toBeInTheDocument();
    expect(
      window.sessionStorage.getItem(
        "template-twin:certification-draft:v1:lineage-synthetic-1",
      ),
    ).toContain("chief_complaint");
  });

  it("shows a short retry state when the Redis safety check is unavailable", async () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-07-19T01:00:00.000Z"));
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 503,
      headers: new Headers({ "Retry-After": "5" }),
      json: async () => ({
        ok: false,
        code: "RATE_LIMIT_UNAVAILABLE",
        error: "Mapping saves are temporarily unavailable.",
        retryAfterSec: 5,
      }),
    });
    vi.stubGlobal("fetch", fetchMock);
    render(
      <TemplateTwinCertificationWorkspace
        initial={workspace("needs_confirmation", true)}
        stagingQaGateAllowed
      />,
    );

    selectSupportedConcept();
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Save draft" }));
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(
      screen.getByRole("button", { name: "Retry save in 5s" }),
    ).toBeDisabled();
    expect(screen.getByText("Mapping save available in 5s")).toBeInTheDocument();
    expect(screen.getByText(/safety check retry state resets/u)).toBeInTheDocument();
    expect(
      window.sessionStorage.getItem(
        "template-twin:certification-draft:v1:lineage-synthetic-1",
      ),
    ).toContain("chief_complaint");
  });

  it("keeps structural inventory categories disjoint", () => {
    render(
      <TemplateTwinCertificationWorkspace
        initial={workspace("needs_confirmation", true)}
        stagingQaGateAllowed
      />,
    );

    const summary = screen.getByRole("region", {
      name: "Detected structure summary",
    });
    expect(
      within(summary).getByText("Text controls").parentElement,
    ).toHaveTextContent("Text controls0");
    expect(
      within(summary).getByText("Placeholders").parentElement,
    ).toHaveTextContent("Placeholders1");
  });

  it("launches a certified typed visit through the authenticated staging route", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        ok: true,
        run: {
          runId: "run-synthetic-1",
          visitId: "visit-synthetic-1",
          reused: false,
        },
        visitUrl: "/visits/visit-synthetic-1",
      }),
    });
    vi.stubGlobal("fetch", fetchMock);
    render(
      <TemplateTwinCertificationWorkspace
        initial={workspace("certified", true)}
        stagingQaGateAllowed
      />,
    );

    const input = screen.getByLabelText("Typed synthetic encounter");
    expect(input).toHaveValue(TEMPLATE_TWIN_STAGING_QA_TYPED_STARTER);
    fireEvent.change(input, { target: { value: "" } });
    fireEvent.click(
      screen.getByRole("button", {
        name: "Restore reviewed visit evidence",
      }),
    );
    expect(input).toHaveValue(TEMPLATE_TWIN_STAGING_QA_TYPED_STARTER);
    fireEvent.click(
      screen.getByRole("button", { name: "Start typed synthetic visit" }),
    );

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    const [url, request] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/note-templates/template-twin/staging-qa/runs");
    expect(JSON.parse(String(request.body))).toMatchObject({
      templateId: "template-synthetic-1",
      mode: "typed",
      idempotencyKey: expect.stringMatching(/^[A-Za-z0-9._~-]{16,128}$/),
      expectedTemplateVersion: 2,
      encounterText: TEMPLATE_TWIN_STAGING_QA_TYPED_STARTER,
    });
    expect(navigation.push).toHaveBeenCalledWith("/visits/visit-synthetic-1");
  });

  it("offers the exact reviewed certification evidence without confirming field intent", () => {
    render(
      <TemplateTwinCertificationWorkspace
        initial={workspace("needs_confirmation", true)}
        stagingQaGateAllowed
      />,
    );

    const evidence = screen.getByLabelText("Synthetic encounter text");
    expect(evidence).toHaveValue(TEMPLATE_TWIN_STAGING_QA_TYPED_STARTER);
    fireEvent.change(evidence, { target: { value: "" } });
    fireEvent.click(
      screen.getByRole("button", {
        name: "Restore reviewed certification evidence",
      }),
    );

    expect(evidence).toHaveValue(TEMPLATE_TWIN_STAGING_QA_TYPED_STARTER);
    expect(screen.getByLabelText("Field intent")).toHaveValue("unresolved");
    expect(
      screen.getByText(
        /does not confirm any field meaning or physician mapping/i,
      ),
    ).toBeInTheDocument();
  });
});
