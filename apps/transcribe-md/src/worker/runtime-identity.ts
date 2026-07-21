import { requiresExactQuillmdRuntimeIdentity } from "@meddoc/auth/runtime-identity";

export const TRANSCRIBE_MD_WORKER_SERVICE_ROLE =
  "transcribe-md-worker" as const;

export class TranscribeMdWorkerRuntimeIdentityError extends Error {
  readonly code = "TRANSCRIBE_MD_WORKER_RUNTIME_IDENTITY_INVALID";

  constructor() {
    super("The TranscribeMD worker runtime identity is invalid.");
    this.name = "TranscribeMdWorkerRuntimeIdentityError";
  }
}

/**
 * Bind this executable to its one reviewed service identity before it proves
 * database authority or constructs any external runtime resource. Truly
 * identity-free local development remains available; production and every
 * partially/configured identity must be exact.
 */
export function assertTranscribeMdWorkerRuntimeIdentity(
  environment: Readonly<Record<string, string | undefined>>,
): void {
  if (!requiresExactQuillmdRuntimeIdentity(environment)) return;
  if (
    environment.QUILLMD_SERVICE_ROLE !== TRANSCRIBE_MD_WORKER_SERVICE_ROLE
  ) {
    throw new TranscribeMdWorkerRuntimeIdentityError();
  }
}
