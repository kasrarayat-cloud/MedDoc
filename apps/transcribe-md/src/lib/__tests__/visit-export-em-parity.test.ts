// ============================================================================
// E/M PARITY at the PRINT/EXPORT surface (#315 obs#2).
// ----------------------------------------------------------------------------
// loadVisitExportData feeds EVERY artifact (PDF, DOCX, all EHR clipboard
// formats) via `em`. It must project the AUTHORITATIVE displayed level onto
// em.code so the printed/exported claim equals what the doctor reviewed —
// never the raw L7b suggestion. prisma is mocked; the projection is REAL.
// ============================================================================

import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  findUnique: vi.fn(),
  assessAutomation: vi.fn(),
  authorizeDelivery: vi.fn(),
}));
vi.mock("@meddoc/db", () => ({
  default: { transcribeVisit: { findFirst: mocks.findUnique } },
}));
vi.mock("@meddoc/shared/specialties", () => ({
  findSpecialty: (s: string) => ({ label: s, id: s }),
}));
vi.mock("@/worker/automation-finalization", () => ({
  assessVisitAutomationProof: mocks.assessAutomation,
}));
vi.mock("@/lib/template-twin/delivery-authorization", () => ({
  authorizeVisitDeliveryFinalClaim: mocks.authorizeDelivery,
}));

import {
  loadVisitExportData,
  loadVisitExportObjectManifest,
} from "../visit-export-server";
import { projectDisplayedEmCode } from "../visit-export";

const DOCTOR = "doc1";
const EM = {
  code: "99213", // the raw L7b suggestion
  description: "Established, low",
  reasoning: { problems: [], data: "", risk: "" },
  evidence_quote: "",
};

function row(over: Record<string, unknown> = {}) {
  return {
    id: "v1",
    userId: DOCTOR,
    patientName: "P",
    specialty: "primary-care",
    chiefComplaint: null,
    status: "SIGNED",
    createdAt: new Date("2026-06-13T09:00:00Z"),
    signedAt: new Date("2026-06-13T10:00:00Z"),
    soapFinal: "## Plan\nx",
    signedSoap: "## Plan\nx",
    icdCodes: null,
    cptCodes: { em: EM },
    rxDrafts: null,
    referrals: null,
    patientSummary: null,
    user: {
      name: "Dr",
      email: "doctor@synthetic.test",
      practiceId: "practice-synthetic",
    },
    ...over,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  mocks.assessAutomation.mockReturnValue({ ready: true, blockerCodes: [] });
  mocks.authorizeDelivery.mockResolvedValue({ templateTwin: false });
});

describe("loadVisitExportData — printed E/M code === confirmed displayed level", () => {
  it("does not select SOAP/codes/Rx before the shared delivery authority boundary", async () => {
    mocks.authorizeDelivery.mockRejectedValue(
      new Error("synthetic current authority denial"),
    );

    await expect(loadVisitExportData("v1", DOCTOR)).rejects.toThrow(
      "synthetic current authority denial",
    );
    expect(mocks.findUnique).not.toHaveBeenCalled();
  });

  it("does not project ordinary clinical data when durable lineage appears after delivery admission", async () => {
    mocks.findUnique.mockImplementationOnce(async (query) => {
      expect(query.where).toMatchObject({ id: "v1" });
      expect(JSON.stringify(query.where)).toContain(
        "templateTwinCompiledVersion",
      );
      return null;
    });

    await expect(loadVisitExportData("v1", DOCTOR)).resolves.toBeNull();
    expect(mocks.authorizeDelivery).toHaveBeenCalledTimes(1);
  });

  it("SIGNED visit prints the FROZEN signedCode, not the raw L7b suggestion (the obs#2 bug)", async () => {
    mocks.findUnique.mockResolvedValue(
      row({ cptCodes: { em: { ...EM, code: "99213", signedCode: "99214" } } }),
    );
    const data = await loadVisitExportData("v1", DOCTOR);
    expect(data?.em?.code).toBe("99214"); // confirmed, not 99213
  });

  it("does not return projected clinical data when the final post-load claim is revoked", async () => {
    mocks.findUnique.mockResolvedValue(row());
    mocks.authorizeDelivery
      .mockResolvedValueOnce({ templateTwin: true })
      .mockRejectedValueOnce(new Error("synthetic final claim revoked"));

    await expect(loadVisitExportData("v1", DOCTOR)).rejects.toThrow(
      "synthetic final claim revoked",
    );
    expect(mocks.findUnique).toHaveBeenCalledTimes(1);
    expect(mocks.authorizeDelivery).toHaveBeenCalledTimes(2);
  });

  it("SIGNED visit with an override but NO signedCode (pre-fix) falls back to the override level", async () => {
    mocks.findUnique.mockResolvedValue(
      row({
        cptCodes: { em: { ...EM, code: "99213", override: { code: "99215" } } },
      }),
    );
    const data = await loadVisitExportData("v1", DOCTOR);
    expect(data?.em?.code).toBe("99215");
  });

  it("SIGNED visit, signedCode present, wins even over a stale override", async () => {
    mocks.findUnique.mockResolvedValue(
      row({
        cptCodes: {
          em: { ...EM, signedCode: "99214", override: { code: "99212" } },
        },
      }),
    );
    const data = await loadVisitExportData("v1", DOCTOR);
    expect(data?.em?.code).toBe("99214");
  });

  it("UNSIGNED draft export projects override ?? raw (respects the doctor override)", async () => {
    mocks.findUnique.mockResolvedValue(
      row({
        status: "READY",
        signedSoap: null,
        cptCodes: { em: { ...EM, override: { code: "99215" } } },
      }),
    );
    const data = await loadVisitExportData("v1", DOCTOR);
    expect(data?.em?.code).toBe("99215");
  });

  it("UNSIGNED, no override → raw code (unchanged behavior)", async () => {
    mocks.findUnique.mockResolvedValue(
      row({ status: "READY", signedSoap: null }),
    );
    const data = await loadVisitExportData("v1", DOCTOR);
    expect(data?.em?.code).toBe("99213");
  });

  it("a visit with no em block exports em=null (no crash)", async () => {
    mocks.findUnique.mockResolvedValue(row({ cptCodes: { procedures: [] } }));
    const data = await loadVisitExportData("v1", DOCTOR);
    expect(data?.em).toBeNull();
  });

  it("returns no export data when the durable automation proof is incomplete", async () => {
    mocks.findUnique.mockResolvedValue(row());
    mocks.assessAutomation.mockReturnValue({
      ready: false,
      blockerCodes: ["VISIT_AUTOMATION_PROOF_MISSING"],
    });
    await expect(loadVisitExportData("v1", DOCTOR)).resolves.toBeNull();
  });
});

describe("loadVisitExportObjectManifest — storage-key authority", () => {
  it("does not select object keys before the first delivery claim", async () => {
    mocks.authorizeDelivery.mockRejectedValue(new Error("revoked before key"));

    await expect(loadVisitExportObjectManifest("v1", DOCTOR)).rejects.toThrow(
      "revoked before key",
    );
    expect(mocks.findUnique).not.toHaveBeenCalled();
  });

  it("does not project an ordinary object key when durable lineage appears after delivery admission", async () => {
    mocks.findUnique.mockImplementationOnce(async (query) => {
      expect(query.where).toMatchObject({ id: "v1" });
      expect(JSON.stringify(query.where)).toContain(
        "templateTwinCompiledVersion",
      );
      return null;
    });

    await expect(
      loadVisitExportObjectManifest("v1", DOCTOR),
    ).resolves.toBeNull();
    expect(mocks.authorizeDelivery).toHaveBeenCalledTimes(1);
  });

  it("does not return an object key when the post-load claim is revoked", async () => {
    mocks.findUnique.mockResolvedValue(
      row({
        audioKey: "private/audio-key",
        dictationAudioKey: "private/dictation-key",
        audioMimeType: "audio/webm",
      }),
    );
    mocks.authorizeDelivery
      .mockResolvedValueOnce({ templateTwin: true })
      .mockRejectedValueOnce(new Error("revoked after key"));

    await expect(loadVisitExportObjectManifest("v1", DOCTOR)).rejects.toThrow(
      "revoked after key",
    );
    expect(mocks.authorizeDelivery).toHaveBeenCalledTimes(2);
  });
});

describe("projectDisplayedEmCode — the one projection all surfaces share", () => {
  const base = {
    code: "99213",
    description: "",
    reasoning: { problems: [], data: "", risk: "" },
    evidence_quote: "",
  };
  it("signed → frozen signedCode wins", () => {
    expect(
      projectDisplayedEmCode(
        { ...base, signedCode: "99214", override: { code: "99212" } },
        true,
      ),
    ).toBe("99214");
  });
  it("signed, no signedCode → override", () => {
    expect(
      projectDisplayedEmCode({ ...base, override: { code: "99215" } }, true),
    ).toBe("99215");
  });
  it("signed, neither → raw", () => {
    expect(projectDisplayedEmCode(base, true)).toBe("99213");
  });
  it("unsigned → override ?? raw (signedCode ignored while unsigned)", () => {
    expect(
      projectDisplayedEmCode(
        { ...base, signedCode: "99214", override: { code: "99215" } },
        false,
      ),
    ).toBe("99215");
    expect(projectDisplayedEmCode(base, false)).toBe("99213");
  });
  it("null em → null", () => {
    expect(projectDisplayedEmCode(null, true)).toBeNull();
  });
});
