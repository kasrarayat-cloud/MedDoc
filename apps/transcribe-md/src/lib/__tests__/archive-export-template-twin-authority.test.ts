import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

function source(relativePath: string): string {
  return readFileSync(resolve(process.cwd(), relativePath), "utf8");
}

describe("long-running archive Template Twin authority contract", () => {
  const account = source("src/app/api/settings/export-data/route.ts");
  const patient = source("src/app/api/patients/[id]/export/route.ts");
  const readAuthority = source("src/lib/template-twin/read-authority.ts");
  const exportAuthority = source("src/lib/visit-export-authority.ts");

  it("enumerates only exact query-native visit identities before streaming", () => {
    for (const route of [account, patient]) {
      expect(route).toContain("listTemplateTwinVisibleVisitIdentities");
      expect(route).not.toContain("prisma.transcribeVisit.findMany");
      expect(
        route.indexOf("listTemplateTwinVisibleVisitIdentities"),
      ).toBeLessThan(route.indexOf("const archive = archiver"));
    }
    const censusStart = readAuthority.indexOf(
      "export async function listTemplateTwinVisibleVisitIdentities",
    );
    const census = readAuthority.slice(censusStart);
    expect(census).toContain('SELECT visit."id", visit."createdAt"');
    expect(census).not.toContain('visit."audioKey"');
    expect(census).toContain("templateTwinVisitReadVisibilitySql");
  });

  it("loads object keys per visit and rechecks after every audio download before append", () => {
    for (const route of [account, patient]) {
      expect(route).toContain("loadVisitExportObjectManifest(v.id, userId)");
      expect(route).not.toContain("if (!manifest) continue");
      expect(route).toContain(
        'throw new Error("Visit export object manifest is unavailable.")',
      );
      expect(route).toContain(
        "if (err instanceof TemplateTwinDeliveryAuthorizationError)",
      );
      expect(route).toMatch(
        /downloadAudio\(manifest\.audioKey\);\s*await authorizeVisitDeliveryFinalClaim\(/,
      );
      expect(route).toMatch(
        /downloadAudio\(manifest\.dictationAudioKey\);\s*await authorizeVisitDeliveryFinalClaim\(/,
      );
      expect(route).toMatch(
        /generateVisitPdf\(exportData\);\s*await authorizeVisitDeliveryFinalClaim\(/,
      );
    }
  });

  it("never preloads SOAP edit pairs and emits them only after per-visit claims", () => {
    expect(account).not.toContain("where: { doctorId: userId },");
    const helperStart = account.indexOf(
      "async function loadAuthorizedEditPatterns",
    );
    const helper = account.slice(helperStart);
    const firstClaim = helper.indexOf("authorizeVisitDeliveryFinalClaim");
    const clinicalQuery = helper.indexOf("doctorEditPattern.findMany");
    const secondClaim = helper.indexOf(
      "authorizeVisitDeliveryFinalClaim",
      firstClaim + 1,
    );
    expect(firstClaim).toBeGreaterThanOrEqual(0);
    expect(firstClaim).toBeLessThan(clinicalQuery);
    expect(secondClaim).toBeGreaterThan(clinicalQuery);
    expect(account).toContain("visits/${v.id}/doctor_edit_patterns.json");
  });

  it("uses one current physician/practice lifecycle gate without coupling ordinary export to rollout", () => {
    expect(exportAuthority).toContain('actor.role !== "DOCTOR"');
    expect(exportAuthority).toContain("actor.isActive !== true");
    expect(exportAuthority).toContain("actor.deactivatedAt !== null");
    expect(exportAuthority).toContain("actor.suspendedAt !== null");
    expect(exportAuthority).toContain("actor.softDeletedAt !== null");
    expect(exportAuthority).toContain(
      '!actor.products.includes("TRANSCRIBE_MD")',
    );
    expect(exportAuthority).toContain("actor.practice.isActive !== true");
    expect(exportAuthority).not.toMatch(/rolloutToken|templateTwinEnabled/i);
  });

  it("rechecks actor authority after enumeration and before the first archive byte", () => {
    for (const route of [account, patient]) {
      const handler = route.indexOf("export const GET");
      const census = route.indexOf(
        "listTemplateTwinVisibleVisitIdentities",
        handler,
      );
      const firstIdentity = route.indexOf(
        "loadCurrentVisitExportActor(userId)",
        handler,
      );
      const secondIdentity = route.indexOf(
        "loadCurrentVisitExportActor(userId)",
        firstIdentity + 1,
      );
      const firstAppend = route.indexOf("archive.append(", secondIdentity);
      expect(firstIdentity).toBeGreaterThanOrEqual(0);
      expect(firstIdentity).toBeLessThan(census);
      expect(secondIdentity).toBeGreaterThan(census);
      expect(secondIdentity).toBeLessThan(firstAppend);
    }
  });

  it("rebinds patient tenant, reserved identity, and deletion epoch before patient PHI append", () => {
    const handler = patient.indexOf("export const GET");
    const firstPatient = patient.indexOf(
      "loadCurrentPatientExportRecord(",
      handler,
    );
    const secondPatient = patient.indexOf(
      "loadCurrentPatientExportRecord(",
      firstPatient + 1,
    );
    const firstAppend = patient.indexOf("archive.append(", secondPatient);
    expect(firstPatient).toBeGreaterThanOrEqual(0);
    expect(secondPatient).toBeGreaterThan(firstPatient);
    expect(secondPatient).toBeLessThan(firstAppend);
    expect(patient).toContain("currentClinicalPatientWhere({");
    expect(patient).toContain("practiceId: identity.practiceId");
    expect(patient).toContain("includeDeleted: true");
    expect(patient).toContain(
      "currentPatient.deletedAt?.getTime() !== patient.deletedAt?.getTime()",
    );
    expect(patient).not.toContain("const safeName = patient.name");
  });
});
