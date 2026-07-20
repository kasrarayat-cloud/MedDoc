import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

function source(path: string): string {
  return readFileSync(resolve(process.cwd(), path), "utf8");
}

function occurrenceCount(contents: string, token: string): number {
  return contents.split(token).length - 1;
}

describe("generic visit mutation policy census", () => {
  const liveClinicalMutations = [
    ["SOAP save", "src/actions/soap.ts", 'operation: "soap_save"'],
    [
      "Rx warning override",
      "src/lib/rx-warning-audit.ts",
      'operation: "rx_warning_override"',
    ],
    [
      "typed input",
      "src/app/api/visits/[id]/text/route.ts",
      'operation: "text_submit"',
    ],
    [
      "bulk audio upload",
      "src/app/api/visits/[id]/upload/route.ts",
      'operation: "audio_upload"',
    ],
    [
      "dictation upload",
      "src/app/api/visits/[id]/dictation/upload/route.ts",
      'operation: "dictation_upload"',
    ],
    ["retry", "src/app/api/visits/[id]/retry/route.ts", 'operation: "retry"'],
    [
      "E/M override",
      "src/app/api/visits/[id]/em-score/override/route.ts",
      'operation: "em_override"',
    ],
    [
      "draft metadata PATCH",
      "src/app/api/visits/[id]/route.ts",
      'operation: "generic_patch"',
    ],
  ] as const;

  it.each(liveClinicalMutations)(
    "%s has admission, final live lock, transactional outbox, and ordinary final fence",
    (_label, path, operation) => {
      const contents = source(path);
      expect(contents).toContain("pinTemplateTwinClinicalMutation");
      expect(contents).toContain("lockAndAssertTemplateTwinClinicalMutation");
      expect(contents).toContain("enqueueTemplateTwinClinicalMutationAudit");
      expect(contents).toContain("lockAndAssertOrdinaryClinicalMutation");
      expect(contents).toContain("TEMPLATE_TWIN_DURABLE_VISIT_EXCLUSION_WHERE");
      expect(contents).toContain(operation);
    },
  );

  it.each([
    [
      "suggestion adopt/dismiss",
      "src/actions/suggestion-actions.ts",
      "const emDelta = await computeEmLevelDelta({",
    ],
    [
      "E/M apply-additions",
      "src/app/api/visits/[id]/em-score/apply-additions/route.ts",
      "const engineScore = await computeEmScore(",
    ],
  ] as const)(
    "%s remains ordinary-only and fences provider egress plus final commit",
    (_label, path, providerToken) => {
      const contents = source(path);
      expect(contents).toContain(
        "hasDurableTemplateTwinClinicalMutationProvenance",
      );
      expect(contents).toContain("TEMPLATE_TWIN_DURABLE_VISIT_EXCLUSION_WHERE");
      expect(contents).toContain(providerToken);
      // Import plus three calls: immediate pre-egress, immediate post-return,
      // and the final write transaction. These are separate fences so a
      // durable marker appearing in either provider window fails closed.
      expect(
        occurrenceCount(contents, "lockAndAssertOrdinaryClinicalMutation"),
      ).toBeGreaterThanOrEqual(4);

      const providerIndex = contents.indexOf(providerToken);
      const firstFenceIndex = contents.indexOf(
        "lockAndAssertOrdinaryClinicalMutation",
        contents.indexOf("lockAndAssertOrdinaryClinicalMutation") + 1,
      );
      const postReturnFenceIndex = contents.indexOf(
        "lockAndAssertOrdinaryClinicalMutation",
        firstFenceIndex + 1,
      );
      const finalFenceIndex = contents.indexOf(
        "lockAndAssertOrdinaryClinicalMutation",
        postReturnFenceIndex + 1,
      );
      expect(firstFenceIndex).toBeLessThan(providerIndex);
      expect(postReturnFenceIndex).toBeGreaterThan(providerIndex);
      expect(finalFenceIndex).toBeGreaterThan(postReturnFenceIndex);
    },
  );

  it("speaker reassignment is unsupported for Twin and has an atomic ordinary-only CAS", () => {
    const contents = source("src/actions/soap.ts");
    expect(contents).toContain(
      "Speaker reassignment is unavailable for Template Twin visits",
    );
    expect(contents).toContain("TEMPLATE_TWIN_DURABLE_VISIT_EXCLUSION_WHERE");
    expect(contents).toContain("speakerMap:");
    expect(contents).toContain("transcribeVisit.updateMany");
  });

  it.each([
    ["archive", "src/app/api/visits/[id]/archive/route.ts"],
    ["unarchive", "src/app/api/visits/[id]/unarchive/route.ts"],
    ["restore", "src/app/api/visits/[id]/restore/route.ts"],
    ["delete", "src/app/api/visits/[id]/delete/route.ts"],
  ] as const)(
    "%s lifecycle has live and ordinary final authority",
    (_label, path) => {
      const contents = source(path);
      expect(contents).toContain("pinTemplateTwinDataLifecycleMutation");
      expect(contents).toContain(
        "lockAndAssertTemplateTwinDataLifecycleMutation",
      );
    expect(contents).toContain("lockAndAssertOrdinaryDataLifecycleMutation");
    expect(contents).toContain("TEMPLATE_TWIN_DURABLE_VISIT_EXCLUSION_WHERE");
      expect(contents).toContain(
        "enqueueTemplateTwinDataLifecycleMutationAudit",
      );
    },
  );

  it.each([
    "src/worker/cleanup/stale-visits.ts",
    "src/worker/cleanup/retention-sweep.ts",
  ])(
    "%s excludes every durable Twin marker at selection and final CAS",
    (path) => {
      const contents = source(path);
      expect(contents).toContain("TEMPLATE_TWIN_DURABLE_VISIT_EXCLUSION_WHERE");
    },
  );

  it("generic note-template lifecycle excludes Twin on every target mutation", () => {
    const contents = source("src/actions/note-template-lifecycle.ts");
    expect(contents).toMatch(
      /templateKind:\s*\{\s*not:\s*["']template_twin_docx["']\s*\}/u,
    );
    expect(contents).toContain("templateTwinCompiledVersion: { is: null }");
    expect(contents).toContain(
      'FROM "template_twin_compiled_versions" compiled',
    );
    expect(contents).toContain("generic template authority changed");
    expect(contents).toContain("FOR UPDATE");
  });

  it.each([
    "src/app/api/visits/[id]/export/docx/route.ts",
    "src/app/api/visits/[id]/export/pdf/route.ts",
    "src/app/api/visits/[id]/export/email/route.ts",
    "src/app/api/visits/[id]/export/clipboard/route.ts",
  ])(
    "%s remains owned by the dedicated delivery authorization contract",
    (path) => {
      expect(source(path)).toContain("authorizeVisitDeliveryFinalClaim");
    },
  );

  it("sign remains a separately locked signing/delivery workflow", () => {
    const contents = source("src/app/api/visits/[id]/sign/route.ts");
    expect(contents).toContain("lockTemplateTwinRolloutForFinalClaim");
    expect(contents).toContain("lockAndAssertOrdinaryClinicalMutation");
    expect(contents).toContain("enqueueTemplateTwinAudit");
  });
});
