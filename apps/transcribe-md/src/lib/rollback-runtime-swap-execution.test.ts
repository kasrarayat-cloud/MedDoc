import {
  chmodSync,
  mkdirSync,
  mkdtempSync,
  readFileSync,
  readdirSync,
  rmSync,
  statSync,
  writeFileSync,
} from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { spawnSync } from "node:child_process";

import { afterEach, describe, expect, it } from "vitest";

const ROOT = path.resolve(__dirname, "../../../..");
const SWAP = path.join(ROOT, "scripts/template-twin-runtime-swap.sh");
const COMPOSE = path.join(ROOT, "docker-compose.yml");
const APP_ID = `sha256:${"a".repeat(64)}`;
const WORKER_ID = `sha256:${"b".repeat(64)}`;
const RELEASE_SHA = "c".repeat(40);

const services = [
  ["transcribe-md", "app", "physician-app"],
  ["template-twin-admin-app", "app", "template-twin-admin-app"],
  ["template-twin-admin-control", "app", "template-twin-admin-control"],
  ["transcribe-md-worker", "worker", "transcribe-md-worker"],
  [
    "template-twin-audit-dispatcher",
    "worker",
    "template-twin-audit-dispatcher",
  ],
  ["auth-email-dispatcher", "worker", "auth-email-dispatcher"],
] as const;

const temporaryRoots: string[] = [];

afterEach(() => {
  for (const root of temporaryRoots.splice(0)) {
    rmSync(root, { recursive: true, force: true });
  }
});

function composeModel(
  bridge: boolean,
  options: {
    includeDrift?: boolean;
    unsafeMock?: boolean;
    unsafeAuth?: boolean;
  } = {},
): string {
  const modelServices: Record<string, unknown> = {};
  for (const [name, artifact, role] of services) {
    modelServices[name] = {
      image: bridge
        ? artifact === "app"
          ? APP_ID
          : WORKER_ID
        : `\${TRANSCRIBE_MD_${artifact === "app" ? "" : "WORKER_"}IMAGE:-mutable}`,
      build: {
        dockerfile:
          artifact === "app"
            ? "apps/transcribe-md/Dockerfile"
            : "apps/transcribe-md/Dockerfile.worker",
      },
      labels: {
        "com.quillmd.rollback-runtime-managed": "true",
        "com.quillmd.rollback-runtime-artifact": artifact,
        ...(bridge
          ? { "com.quillmd.rollback-runtime-capability": "six-runtime-v1" }
          : {}),
      },
      environment: {
        ...(role ? { QUILLMD_SERVICE_ROLE: role } : {}),
        QUILLMD_DATABASE_PRINCIPAL_PROFILE: "exact-production-v1",
        QUILLMD_REQUIRED_RUNTIME_PROTOCOL_EPOCH:
          "template-twin-final-schema-v2",
        TEMPLATE_TWIN_RUNTIME_MODE: bridge
          ? "rollback-compat-v2"
          : "${TEMPLATE_TWIN_RUNTIME_MODE:-standard}",
        TEMPLATE_TWIN_KILL_SWITCH: bridge
          ? "true"
          : "${TEMPLATE_TWIN_KILL_SWITCH:-true}",
        MOCK_AI_CALLS:
          options.unsafeMock && name === "transcribe-md-worker"
            ? "true"
            : "false",
        MOCK_TEMPLATE_TWIN_E2E: "false",
        MOCK_TEMPLATE_PHI_FLAG: "false",
        MOCK_RX_WARNINGS: "false",
        AUTH_USE_MOCK:
          options.unsafeAuth && name === "transcribe-md" ? "true" : "false",
        EMAIL_AUTO_CONFIRM_DOMAINS: "",
        EMAIL_AUTO_CONFIRM_ALLOW_IN_PROD: "false",
        RATE_LIMIT_DISABLED: "false",
        RATE_LIMIT_DISABLE_ALLOW_IN_PROD: "false",
        QUILLMD_AUTH_SESSION_VERIFIER_PROFILE:
          role === "template-twin-admin-control"
            ? "template-twin-admin-control-v1"
            : "",
        ...(bridge
          ? {
              TEMPLATE_TWIN_RUNTIME_ATTESTATION: "",
              TEMPLATE_TWIN_APP_RUNTIME_ATTESTATION: "",
              TEMPLATE_TWIN_ADMIN_APP_RUNTIME_ATTESTATION: "",
              TEMPLATE_TWIN_ADMIN_CONTROL_RUNTIME_ATTESTATION: "",
              TEMPLATE_TWIN_WORKER_RUNTIME_ATTESTATION: "",
            }
          : {}),
      },
    };
  }
  if (options.includeDrift) {
    modelServices["unreviewed-worker-clone"] = {
      build: { dockerfile: "apps/transcribe-md/Dockerfile.worker" },
      labels: {
        "com.quillmd.rollback-runtime-managed": "true",
        "com.quillmd.rollback-runtime-artifact": "worker",
      },
      environment: {
        QUILLMD_REQUIRED_RUNTIME_PROTOCOL_EPOCH:
          "template-twin-final-schema-v2",
        TEMPLATE_TWIN_RUNTIME_MODE: "${TEMPLATE_TWIN_RUNTIME_MODE:-standard}",
        TEMPLATE_TWIN_KILL_SWITCH: "${TEMPLATE_TWIN_KILL_SWITCH:-true}",
        MOCK_AI_CALLS: "false",
        MOCK_TEMPLATE_TWIN_E2E: "false",
        MOCK_TEMPLATE_PHI_FLAG: "false",
        MOCK_RX_WARNINGS: "false",
      },
    };
  }
  modelServices["db-migrate"] = {
    build: {
      dockerfile: "apps/transcribe-md/Dockerfile",
      target: "builder",
    },
    profiles: ["migrations"],
  };
  return JSON.stringify({ services: modelServices });
}

function fixture(options?: {
  drift?: boolean;
  mode?: string;
  unsafeMock?: boolean;
  unsafeAuth?: boolean;
}) {
  const root = mkdtempSync(path.join(tmpdir(), "quillmd-runtime-swap-test-"));
  temporaryRoots.push(root);
  const bin = path.join(root, "bin");
  const state = path.join(root, "state");
  const log = path.join(root, "docker.log");
  const baseModel = path.join(root, "base.json");
  const bridgeModel = path.join(root, "bridge.json");
  mkdirSync(bin, { mode: 0o700 });
  mkdirSync(state, { mode: 0o700 });
  writeFileSync(
    baseModel,
    composeModel(false, {
      includeDrift: options?.drift,
      unsafeMock: options?.unsafeMock,
      unsafeAuth: options?.unsafeAuth,
    }),
  );
  writeFileSync(bridgeModel, composeModel(true));

  const docker = `#!/usr/bin/env bash
set -euo pipefail
args=" $* "
if [[ "\${1:-}" == "compose" ]]; then
  if [[ "$args" == *" config "* ]]; then
    if [[ "$args" == *".override.yml"* ]]; then
      command cat "$FAKE_BRIDGE_MODEL"
    else
      command cat "$FAKE_BASE_MODEL"
    fi
    exit 0
  fi
  if [[ "$args" == *" ps "* ]]; then
    service="\${!#}"
    if [[ "\${FAKE_MODE:-ok}" == "missing" && "$service" == "auth-email-dispatcher" ]]; then
      exit 0
    fi
    printf 'container-%s\\n' "$service"
    exit 0
  fi
  if [[ "$args" == *" exec "* ]]; then
    if [[ "$args" == *"template_twin_lineage_migration_progress"* ]]; then
      printf 'CONTRACTED\\n'
    elif [[ "$args" == *"template_twin_rollout_controls"* ]]; then
      printf 'false\\n'
    else
      printf '0\\n'
    fi
    exit 0
  fi
  if [[ "$args" == *" stop "* || "$args" == *" up "* ]]; then
    printf '%s\\n' "$args" >> "$FAKE_LOG"
    if [[ "\${FAKE_MODE:-ok}" == "up-fail" && "$args" == *" up "* ]]; then
      exit 17
    fi
    exit 0
  fi
fi
if [[ "\${1:-}" == "image" && "\${2:-}" == "inspect" ]]; then
  format="\${4:-}"
  ref="\${5:-}"
  if [[ "$format" == *".Id"* ]]; then
    printf '%s\\n' "$ref"
  elif [[ "$format" == *"runtime-protocol-epoch"* ]]; then
    printf 'template-twin-final-schema-v2\\n'
  elif [[ "$format" == *"image.revision"* ]]; then
    printf '%s\\n' "$FAKE_RELEASE_SHA"
  elif [[ "$format" == *"runtime-component"* ]]; then
    if [[ "$ref" == "$FAKE_APP_ID" ]]; then
      printf 'transcribe-md-app\\n'
    else
      printf 'transcribe-md-worker\\n'
    fi
  elif [[ "$format" == *"rollback-runtime-capability"* ]]; then
    if [[ "\${FAKE_MODE:-ok}" == "old-same-epoch" ]]; then
      printf 'single-runtime-v1\\n'
    else
      printf 'six-runtime-v1\\n'
    fi
  fi
  exit 0
fi
if [[ "\${1:-}" == "inspect" ]]; then
  format="\${3:-}"
  container="\${4:-}"
  service="\${container#container-}"
  artifact=worker
  case "$service" in
    transcribe-md|template-twin-admin-app|template-twin-admin-control) artifact=app ;;
  esac
  if [[ "$format" == *".State.Health"* ]]; then
    if [[ "\${FAKE_MODE:-ok}" == "unhealthy" ]]; then printf 'unhealthy\\n'; else printf 'healthy\\n'; fi
  elif [[ "$format" == *".State.Status"* ]]; then
    printf 'running\\n'
  elif [[ "$format" == *".Image"* ]]; then
    if [[ "$artifact" == app ]]; then printf '%s\\n' "$FAKE_APP_ID"; else printf '%s\\n' "$FAKE_WORKER_ID"; fi
  elif [[ "$format" == *"com.docker.compose.service"* ]]; then
    printf '%s\\n' "$service"
  elif [[ "$format" == *"rollback-runtime-managed"* ]]; then
    printf 'true\\n'
  elif [[ "$format" == *"rollback-runtime-artifact"* ]]; then
    printf '%s\\n' "$artifact"
  elif [[ "$format" == *"rollback-state-version"* ]]; then
    printf 'six-runtime-v1\\n'
  elif [[ "$format" == *"rollback-runtime-capability"* ]]; then
    printf 'six-runtime-v1\\n'
  elif [[ "$format" == *"rollback-release-sha"* ]]; then
    printf '%s\\n' "$FAKE_RELEASE_SHA"
  elif [[ "$format" == *"QUILLMD_SERVICE_ROLE=template-twin-admin-app"* && "\${FAKE_MODE:-ok}" == "wrong-role" ]]; then
    exit 0
  elif [[ "$format" == *"MOCK_AI_CALLS=false"* && "\${FAKE_MODE:-ok}" == "mock-enabled" && "$service" == "transcribe-md-worker" ]]; then
    exit 0
  elif [[ "$format" == *"AUTH_USE_MOCK=false"* && "\${FAKE_MODE:-ok}" == "auth-enabled" && "$service" == "transcribe-md" ]]; then
    exit 0
  elif [[ "$format" == *"QUILLMD_AUTH_SESSION_VERIFIER_PROFILE=template-twin-admin-control-v1"* && "\${FAKE_MODE:-ok}" == "wrong-verifier" && "$service" == "template-twin-admin-control" ]]; then
    exit 0
  elif [[ "$format" == *"QUILLMD_REQUIRED_RUNTIME_PROTOCOL_EPOCH=template-twin-final-schema-v2"* ||
          "$format" == *"TEMPLATE_TWIN_RUNTIME_MODE=standard"* ||
          "$format" == *"TEMPLATE_TWIN_RUNTIME_MODE=rollback-compat-v2"* ||
          "$format" == *"TEMPLATE_TWIN_KILL_SWITCH=true"* ||
          "$format" == *"QUILLMD_DATABASE_PRINCIPAL_PROFILE=exact-production-v1"* ||
          "$format" == *"TEMPLATE_TWIN_RELEASE_COMMIT_SHA=$FAKE_RELEASE_SHA"* ||
          "$format" == *"TEMPLATE_TWIN_RUNTIME_ATTESTATION="* ||
          "$format" == *"TEMPLATE_TWIN_APP_RUNTIME_ATTESTATION="* ||
          "$format" == *"TEMPLATE_TWIN_ADMIN_APP_RUNTIME_ATTESTATION="* ||
          "$format" == *"TEMPLATE_TWIN_ADMIN_CONTROL_RUNTIME_ATTESTATION="* ||
          "$format" == *"TEMPLATE_TWIN_WORKER_RUNTIME_ATTESTATION="* ||
          "$format" == *"MOCK_AI_CALLS=false"* ||
          "$format" == *"MOCK_TEMPLATE_TWIN_E2E=false"* ||
          "$format" == *"MOCK_TEMPLATE_PHI_FLAG=false"* ||
          "$format" == *"MOCK_RX_WARNINGS=false"* ||
          "$format" == *"AUTH_USE_MOCK=false"* ||
          "$format" == *"EMAIL_AUTO_CONFIRM_DOMAINS="* ||
          "$format" == *"EMAIL_AUTO_CONFIRM_ALLOW_IN_PROD=false"* ||
          "$format" == *"RATE_LIMIT_DISABLED=false"* ||
          "$format" == *"RATE_LIMIT_DISABLE_ALLOW_IN_PROD=false"* ||
          "$format" == *"QUILLMD_AUTH_SESSION_VERIFIER_PROFILE="* ||
          "$format" == *"QUILLMD_SERVICE_ROLE="* ]]; then
    printf 'MATCH\\n'
  fi
  exit 0
fi
printf 'unexpected fake docker invocation: %s\\n' "$args" >&2
exit 97
`;
  writeFileSync(path.join(bin, "docker"), docker, { mode: 0o700 });
  writeFileSync(path.join(bin, "sleep"), "#!/bin/sh\nexit 0\n", {
    mode: 0o700,
  });
  chmodSync(path.join(bin, "docker"), 0o700);

  const result = spawnSync(
    "bash",
    [
      SWAP,
      "--app-image",
      APP_ID,
      "--worker-image",
      WORKER_ID,
      "--release-sha",
      RELEASE_SHA,
      "--compose-file",
      COMPOSE,
      "--state-dir",
      state,
      "--execute",
    ],
    {
      cwd: ROOT,
      encoding: "utf8",
      env: {
        ...process.env,
        PATH: `${bin}:${process.env.PATH ?? ""}`,
        FAKE_APP_ID: APP_ID,
        FAKE_WORKER_ID: WORKER_ID,
        FAKE_RELEASE_SHA: RELEASE_SHA,
        FAKE_BASE_MODEL: baseModel,
        FAKE_BRIDGE_MODEL: bridgeModel,
        FAKE_LOG: log,
        FAKE_MODE: options?.mode ?? "ok",
      },
    },
  );
  return { result, state, log };
}

describe("six-service rollback runtime swap", () => {
  it("persists a credential-free immutable overlay and recreates the exact census", () => {
    const { result, state, log } = fixture();
    expect(result.status).toBe(0);
    expect(result.stdout).toContain("services=6 migrator=excluded");
    expect(result.stdout).toContain("immutable rollback state ready");
    expect(result.stdout).toContain("bridge services healthy count=6");

    const overlays = readdirSync(state);
    expect(overlays).toHaveLength(1);
    const overlayPath = path.join(state, overlays[0]);
    expect(statSync(overlayPath).mode & 0o777).toBe(0o444);
    const overlay = readFileSync(overlayPath, "utf8");
    expect(overlay.match(/TEMPLATE_TWIN_RUNTIME_MODE:/g)).toHaveLength(6);
    expect(overlay.match(/TEMPLATE_TWIN_KILL_SWITCH:/g)).toHaveLength(6);
    expect(
      overlay.match(
        /QUILLMD_DATABASE_PRINCIPAL_PROFILE: "exact-production-v1"/g,
      ),
    ).toHaveLength(6);
    expect(
      overlay.match(
        /MOCK_(?:AI_CALLS|TEMPLATE_TWIN_E2E|TEMPLATE_PHI_FLAG|RX_WARNINGS): "false"/g,
      ),
    ).toHaveLength(24);
    expect(
      overlay.match(
        /(?:AUTH_USE_MOCK|EMAIL_AUTO_CONFIRM_ALLOW_IN_PROD|RATE_LIMIT_DISABLED|RATE_LIMIT_DISABLE_ALLOW_IN_PROD): "false"/g,
      ),
    ).toHaveLength(24);
    expect(overlay.match(/EMAIL_AUTO_CONFIRM_DOMAINS: ""/g)).toHaveLength(6);
    expect(
      overlay.match(
        /QUILLMD_AUTH_SESSION_VERIFIER_PROFILE: "template-twin-admin-control-v1"/g,
      ),
    ).toHaveLength(1);
    expect(
      overlay.match(/QUILLMD_AUTH_SESSION_VERIFIER_PROFILE: ""/g),
    ).toHaveLength(5);
    expect(
      overlay.match(/TEMPLATE_TWIN_RUNTIME_ATTESTATION: ""/g),
    ).toHaveLength(6);
    expect(
      overlay.match(
        /TEMPLATE_TWIN_(?:APP|ADMIN_APP|ADMIN_CONTROL|WORKER)_RUNTIME_ATTESTATION: ""/g,
      ),
    ).toHaveLength(24);
    expect(overlay).not.toMatch(
      /TEMPLATE_TWIN_RUNTIME_ATTESTATION: "[^"\n]+"/u,
    );
    expect(overlay.match(/pull_policy: never/g)).toHaveLength(6);
    expect(
      overlay.match(
        /com\.quillmd\.rollback-runtime-capability: "six-runtime-v1"/g,
      ),
    ).toHaveLength(6);
    expect(overlay).not.toMatch(
      /DATABASE_URL|PASSWORD|AUTH_SECRET|API_KEY|ACCESS_TOKEN|REFRESH_TOKEN/u,
    );
    expect(overlay).not.toContain("db-migrate:");

    const operations = readFileSync(log, "utf8");
    expect(operations).toContain(" stop ");
    expect(operations).toContain(" up ");
    for (const [service] of services) expect(operations).toContain(service);
    expect(operations).not.toContain("db-migrate");
  });

  it.each([
    ["a missing managed container", "missing"],
    ["a wrong fixed service role", "wrong-role"],
  ])("fails before mutation for %s", (_description, mode) => {
    const { result, log } = fixture({ mode });
    expect(result.status).not.toBe(0);
    expect(() => readFileSync(log, "utf8")).toThrow();
  });

  it("fails closed on same-artifact census drift", () => {
    const { result, log } = fixture({ drift: true });
    expect(result.status).not.toBe(0);
    expect(result.stderr).toContain("same-artifact service census drifted");
    expect(() => readFileSync(log, "utf8")).toThrow();
  });

  it("fails closed when the static six-runtime census enables a deterministic provider flag", () => {
    const { result, log } = fixture({ unsafeMock: true });
    expect(result.status).not.toBe(0);
    expect(result.stderr).toContain("does not force MOCK_AI_CALLS off");
    expect(() => readFileSync(log, "utf8")).toThrow();
  });

  it("fails closed when the static census enables a synthetic authentication control", () => {
    const { result, log } = fixture({ unsafeAuth: true });
    expect(result.status).not.toBe(0);
    expect(result.stderr).toContain(
      "does not force AUTH_USE_MOCK to its production-safe value",
    );
    expect(() => readFileSync(log, "utf8")).toThrow();
  });

  it("fails before mutation when a live runtime enables a deterministic provider flag", () => {
    const { result, log } = fixture({ mode: "mock-enabled" });
    expect(result.status).not.toBe(0);
    expect(result.stderr).toContain(
      "current deterministic provider state is unsafe",
    );
    expect(() => readFileSync(log, "utf8")).toThrow();
  });

  it.each([
    ["a live synthetic authentication bypass", "auth-enabled"],
    ["a mismatched control-session verifier", "wrong-verifier"],
  ])("fails before mutation for %s", (_description, mode) => {
    const { result, log } = fixture({ mode });
    expect(result.status).not.toBe(0);
    expect(() => readFileSync(log, "utf8")).toThrow();
  });

  it("rejects an old same-epoch target image without the six-runtime capability before mutation", () => {
    const { result, log, state } = fixture({ mode: "old-same-epoch" });
    expect(result.status).not.toBe(0);
    expect(result.stderr).toContain(
      "image lacks the reviewed six-runtime rollback capability",
    );
    expect(readdirSync(state)).toHaveLength(0);
    expect(() => readFileSync(log, "utf8")).toThrow();
  });

  it.each(["up-fail", "unhealthy"])(
    "retains the immutable kill-switch overlay after %s",
    (mode) => {
      const { result, state, log } = fixture({ mode });
      expect(result.status).not.toBe(0);
      expect(result.stderr).toContain("persisted rollout remains revoked");
      const overlays = readdirSync(state);
      expect(overlays).toHaveLength(1);
      expect(statSync(path.join(state, overlays[0])).mode & 0o777).toBe(0o444);
      const operations = readFileSync(log, "utf8");
      expect(operations).toContain(" stop ");
      expect(operations).toContain(" up ");
      expect(operations).not.toContain("db-migrate");
    },
    15_000,
  );
});
