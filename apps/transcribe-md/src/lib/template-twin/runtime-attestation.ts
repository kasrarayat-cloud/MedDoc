import "server-only";

import { Prisma } from "@prisma/client";

import { isTemplateTwinKillSwitchExplicitlyOff } from "@/lib/runtime-protocol";

import {
  TEMPLATE_TWIN_RUNTIME_ATTESTATION_VERSION,
  TEMPLATE_TWIN_RUNTIME_COMPONENTS,
  type TemplateTwinRuntimeComponent,
} from "./release-control-contracts";

export const TEMPLATE_TWIN_RUNTIME_ATTESTATION_ENV =
  "TEMPLATE_TWIN_RUNTIME_ATTESTATION" as const;
export const QUILLMD_IMAGE_REVISION_ENV = "QUILLMD_IMAGE_REVISION" as const;
export const QUILLMD_RUNTIME_COMPONENT_ENV =
  "QUILLMD_RUNTIME_COMPONENT" as const;

const SHA256 = /^[0-9a-f]{64}$/u;
const COMMIT_SHA = /^[0-9a-f]{40}$/u;
const IMAGE_DIGEST = /^sha256:[0-9a-f]{64}$/u;
const UUID =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/u;

interface RuntimeAttestationClient {
  $queryRaw<T>(query: Prisma.Sql): Promise<T>;
}

export interface TemplateTwinRuntimeAttestationEnvelope {
  readonly version: typeof TEMPLATE_TWIN_RUNTIME_ATTESTATION_VERSION;
  readonly keyId: string;
  readonly nonce: string;
  readonly releaseIdentitySha256: string;
  readonly instanceId: string;
  readonly component: TemplateTwinRuntimeComponent;
  readonly sourceCommitSha: string;
  readonly imageDigest: string;
  readonly issuedAtEpochSeconds: number;
  readonly expiresAtEpochSeconds: number;
  readonly signature: string;
}

export class TemplateTwinRuntimeAttestationError extends Error {
  readonly code = "TEMPLATE_TWIN_RUNTIME_ATTESTATION_INVALID";
}

type RuntimeAttestationSubmission =
  | { readonly status: "READY"; readonly envelope: TemplateTwinRuntimeAttestationEnvelope }
  | {
      readonly status: "RELEASE_NOT_CONFIGURED";
      readonly envelope: TemplateTwinRuntimeAttestationEnvelope;
    };

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

export function parseTemplateTwinRuntimeAttestation(
  env: Readonly<Record<string, string | undefined>> = process.env,
): TemplateTwinRuntimeAttestationEnvelope {
  const encoded = env[TEMPLATE_TWIN_RUNTIME_ATTESTATION_ENV];
  if (
    !encoded ||
    encoded.length > 8_192 ||
    !/^[A-Za-z0-9_-]+$/u.test(encoded)
  ) {
    throw new TemplateTwinRuntimeAttestationError(
      "A bounded deployment-signed runtime attestation is required.",
    );
  }
  let value: unknown;
  try {
    value = JSON.parse(Buffer.from(encoded, "base64url").toString("utf8"));
  } catch {
    throw new TemplateTwinRuntimeAttestationError(
      "The deployment runtime attestation is malformed.",
    );
  }
  const expectedKeys = [
    "component",
    "expiresAtEpochSeconds",
    "imageDigest",
    "instanceId",
    "issuedAtEpochSeconds",
    "keyId",
    "nonce",
    "releaseIdentitySha256",
    "signature",
    "sourceCommitSha",
    "version",
  ];
  if (
    !isRecord(value) ||
    Object.keys(value).sort().join("\n") !== expectedKeys.sort().join("\n") ||
    value.version !== TEMPLATE_TWIN_RUNTIME_ATTESTATION_VERSION ||
    typeof value.keyId !== "string" ||
    !/^[A-Za-z0-9][A-Za-z0-9._:-]{2,79}$/u.test(value.keyId) ||
    typeof value.nonce !== "string" ||
    !UUID.test(value.nonce) ||
    typeof value.releaseIdentitySha256 !== "string" ||
    !SHA256.test(value.releaseIdentitySha256) ||
    typeof value.instanceId !== "string" ||
    !/^[a-z0-9][a-z0-9._-]{1,127}$/u.test(value.instanceId) ||
    typeof value.component !== "string" ||
    !TEMPLATE_TWIN_RUNTIME_COMPONENTS.includes(
      value.component as TemplateTwinRuntimeComponent,
    ) ||
    typeof value.sourceCommitSha !== "string" ||
    !COMMIT_SHA.test(value.sourceCommitSha) ||
    typeof value.imageDigest !== "string" ||
    !IMAGE_DIGEST.test(value.imageDigest) ||
    typeof value.issuedAtEpochSeconds !== "number" ||
    !Number.isSafeInteger(value.issuedAtEpochSeconds) ||
    typeof value.expiresAtEpochSeconds !== "number" ||
    !Number.isSafeInteger(value.expiresAtEpochSeconds) ||
    typeof value.signature !== "string" ||
    !SHA256.test(value.signature)
  ) {
    throw new TemplateTwinRuntimeAttestationError(
      "The deployment runtime attestation has an unsupported shape.",
    );
  }
  if (
    env[QUILLMD_IMAGE_REVISION_ENV] !== value.sourceCommitSha ||
    env[QUILLMD_RUNTIME_COMPONENT_ENV] !== value.component
  ) {
    throw new TemplateTwinRuntimeAttestationError(
      "The signed deployment identity does not match this image's baked revision and component.",
    );
  }
  return value as unknown as TemplateTwinRuntimeAttestationEnvelope;
}

async function submitTemplateTwinRuntimeAttestation(input: {
  readonly tx: RuntimeAttestationClient;
  readonly env?: Readonly<Record<string, string | undefined>>;
}): Promise<RuntimeAttestationSubmission> {
  const envelope = parseTemplateTwinRuntimeAttestation(input.env);
  try {
    const rows = await input.tx.$queryRaw<Array<{ receiptId: string | null }>>(
      Prisma.sql`
      SELECT template_twin_register_runtime_attestation(
        ${envelope.version}, ${envelope.keyId}, ${envelope.nonce}::UUID,
        ${envelope.releaseIdentitySha256}::CHAR(64), ${envelope.instanceId},
        ${envelope.component}, ${envelope.sourceCommitSha}::CHAR(40),
        ${envelope.imageDigest}, ${envelope.issuedAtEpochSeconds}::BIGINT,
        ${envelope.expiresAtEpochSeconds}::BIGINT,
        ${envelope.signature}::CHAR(64)
      ) AS "receiptId"
    `,
    );
    if (rows.length !== 1) throw new Error("invalid receipt cardinality");
    return rows[0]!.receiptId
      ? { status: "READY", envelope }
      : { status: "RELEASE_NOT_CONFIGURED", envelope };
  } catch {
    throw new TemplateTwinRuntimeAttestationError(
      "The database rejected this deployment runtime attestation.",
    );
  }
}

export async function registerTemplateTwinRuntimeAttestation(input: {
  readonly tx: RuntimeAttestationClient;
  readonly env?: Readonly<Record<string, string | undefined>>;
}): Promise<TemplateTwinRuntimeAttestationEnvelope> {
  const submission = await submitTemplateTwinRuntimeAttestation(input);
  if (submission.status !== "READY") {
    throw new TemplateTwinRuntimeAttestationError(
      "The signed deployment is not present in an eligible release manifest.",
    );
  }
  return submission.envelope;
}

export async function refreshTemplateTwinRuntimeAttestation(input: {
  readonly tx: RuntimeAttestationClient;
  readonly env?: Readonly<Record<string, string | undefined>>;
}): Promise<"READY" | "NOT_CONFIGURED"> {
  const env = input.env ?? process.env;
  if (!env[TEMPLATE_TWIN_RUNTIME_ATTESTATION_ENV]) {
    if (isTemplateTwinKillSwitchExplicitlyOff(env)) {
      throw new TemplateTwinRuntimeAttestationError(
        "A live production gate requires a signed runtime attestation.",
      );
    }
    return "NOT_CONFIGURED";
  }
  const submission = await submitTemplateTwinRuntimeAttestation({
    tx: input.tx,
    env,
  });
  if (submission.status === "READY") return "READY";
  if (!isTemplateTwinKillSwitchExplicitlyOff(env)) {
    return "NOT_CONFIGURED";
  }
  throw new TemplateTwinRuntimeAttestationError(
    "A live production gate requires this signed deployment in the eligible release manifest.",
  );
}
