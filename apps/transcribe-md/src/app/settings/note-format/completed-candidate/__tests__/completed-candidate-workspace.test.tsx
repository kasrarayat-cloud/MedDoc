import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { CompletedCandidateReviewDto } from "@/lib/template-twin/completed-candidate-contract";

import {
  CompletedCandidateReviewWorkspace,
  CompletedCandidateUploadWorkspace,
} from "../completed-candidate-workspace";

const routerPush = vi.fn();
const routerRefresh = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: routerPush, refresh: routerRefresh }),
}));

const REGION_ONE = "tccr_111111111111111111111111";
const REGION_TWO = "tccr_222222222222222222222222";
const SHA = "a".repeat(64);

function review(
  status: CompletedCandidateReviewDto["status"] = "PENDING_REVIEW",
): CompletedCandidateReviewDto {
  const decision = status === "PENDING_REVIEW" ? "PENDING" : "APPROVED";
  return {
    id: "123e4567-e89b-42d3-a456-426614174000",
    name: "Synthetic follow-up candidate",
    encounterScope: "Synthetic follow-up encounter",
    versionDescription: "Two identical synthetic structures",
    status,
    candidateSha256: SHA,
    inventorySha256: "b".repeat(64),
    comparison: {
      exampleCount: 2,
      identicalStructure: true,
      sourceBlockCount: 7,
      candidateFieldCount: 2,
      preservedStaticBlockCount: 5,
      sourceSummary: "Two isolated examples with one structure",
      candidateSummary: "New blank DOCX with two stable bindings",
    },
    privacy: {
      profileVersion: "completed-candidate-local-synthetic-privacy/1.1.0",
      providerEgress: false,
      exampleCount: 2,
      sentinelVerified: true,
      structuredIdentifierClasses: [],
      sourceBinding: "minimized-package-structure-visible-text-digests",
      exampleEvidenceSha256s: ["f".repeat(64), "1".repeat(64)],
      evidenceSha256: "c".repeat(64),
    },
    regions: [
      {
        regionId: REGION_ONE,
        displayOrder: 0,
        label: "Finding",
        evidenceType: "stable_label_changed_scalar_cell",
        location: "Table 1, row 1, column 2",
        candidateTag: "qmd:candidate:111111111111111111111111",
        sourceEvidenceSha256: "d".repeat(64),
        sourceDescription: "Values changed beside this stable label.",
        candidateDescription: "Blank Word text control.",
        decision,
      },
      {
        regionId: REGION_TWO,
        displayOrder: 1,
        label: "Plan",
        evidenceType: "stable_label_changed_scalar_cell",
        location: "Table 1, row 2, column 2",
        candidateTag: "qmd:candidate:222222222222222222222222",
        sourceEvidenceSha256: "e".repeat(64),
        sourceDescription: "Values changed beside this stable label.",
        candidateDescription: "Blank Word text control.",
        decision,
      },
    ],
  };
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.clearAllMocks();
});

describe("CompletedCandidateUploadWorkspace", () => {
  it("sends only the explicitly attested two-file synthetic intake", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          ok: true,
          reviewUrl:
            "/settings/note-format/completed-candidate/123e4567-e89b-42d3-a456-426614174000",
        }),
        { status: 201, headers: { "Content-Type": "application/json" } },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);
    render(<CompletedCandidateUploadWorkspace />);

    const files = [
      new File(["first"], "synthetic-one.docx", {
        type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      }),
      new File(["second"], "synthetic-two.docx", {
        type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      }),
    ];
    fireEvent.change(
      screen.getByLabelText(/Choose two or three DOCX examples/i),
      { target: { files } },
    );
    fireEvent.change(screen.getByLabelText("Candidate name"), {
      target: { value: "Synthetic follow-up candidate" },
    });
    fireEvent.change(screen.getByLabelText("Encounter scope"), {
      target: { value: "Synthetic follow-up encounter" },
    });
    fireEvent.change(screen.getByLabelText("Version description"), {
      target: { value: "Two structurally identical synthetic examples" },
    });
    fireEvent.click(screen.getByRole("checkbox"));
    fireEvent.click(
      screen.getByRole("button", { name: "Generate blank candidate" }),
    );

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    const [endpoint, request] = fetchMock.mock.calls[0] as [
      string,
      RequestInit,
    ];
    expect(endpoint).toBe(
      "/api/note-templates/template-twin/completed-candidate",
    );
    expect(request.method).toBe("POST");
    const body = request.body as FormData;
    expect(body.getAll("examples")).toHaveLength(2);
    expect(body.get("syntheticAttestation")).toBe("true");
    expect(routerPush).toHaveBeenCalledWith(
      "/settings/note-format/completed-candidate/123e4567-e89b-42d3-a456-426614174000",
    );
  });

  it("rejects a one-file intake before any request", () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    render(<CompletedCandidateUploadWorkspace />);
    fireEvent.change(
      screen.getByLabelText(/Choose two or three DOCX examples/i),
      { target: { files: [new File(["one"], "one.docx")] } },
    );
    expect(
      screen.getByText("Choose exactly two or three synthetic DOCX examples."),
    ).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });
});

describe("CompletedCandidateReviewWorkspace", () => {
  it("keeps every suggestion visible and submits an exact reversible decision set", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ ok: true, status: "REJECTED" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    render(<CompletedCandidateReviewWorkspace initial={review()} />);

    expect(screen.getAllByText("Finding").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Plan").length).toBeGreaterThan(0);
    fireEvent.click(
      screen.getByRole("button", {
        name: "Approve all 2 visible regions",
      }),
    );
    fireEvent.click(screen.getByRole("button", { name: /Plan/ }));
    fireEvent.click(screen.getByLabelText(/Reject candidate/i));
    fireEvent.click(screen.getByLabelText(/I reviewed every visible region/i));
    fireEvent.click(
      screen.getByRole("button", {
        name: "Save final physician decision",
      }),
    );

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    const [, request] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(JSON.parse(String(request.body))).toEqual({
      decisions: [
        { regionId: REGION_ONE, decision: "APPROVED" },
        { regionId: REGION_TWO, decision: "REJECTED" },
      ],
      physicianAttestation: true,
    });
    expect(
      await screen.findByText(/candidate was rejected/i),
    ).toBeInTheDocument();
    expect(routerRefresh).toHaveBeenCalled();
  });

  it("offers an approved candidate only as a separate download", () => {
    render(<CompletedCandidateReviewWorkspace initial={review("APPROVED")} />);
    const link = screen.getByRole("link", {
      name: "Download blank candidate DOCX",
    });
    expect(link).toHaveAttribute(
      "href",
      "/api/note-templates/template-twin/completed-candidate/123e4567-e89b-42d3-a456-426614174000/download",
    );
    expect(
      screen.getByText(/remains separate from active templates/i),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Save final physician decision" }),
    ).not.toBeInTheDocument();
  });
});
