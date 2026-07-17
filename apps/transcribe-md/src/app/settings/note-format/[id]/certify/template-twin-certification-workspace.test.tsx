import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const navigation = vi.hoisted(() => ({
  push: vi.fn(),
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
});

afterEach(() => {
  vi.unstubAllGlobals();
});

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
