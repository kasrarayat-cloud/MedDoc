#!/usr/bin/env node

import process from "node:process";

const EXPECTED_EPOCH = "template-twin-final-schema-v2";
const MANAGED_LABEL = "com.quillmd.rollback-runtime-managed";
const ARTIFACT_LABEL = "com.quillmd.rollback-runtime-artifact";
const CAPABILITY_LABEL = "com.quillmd.rollback-runtime-capability";
const EXPECTED_ROLLBACK_CAPABILITY = "six-runtime-v1";
const deterministicProviderEnvironments = [
  "MOCK_AI_CALLS",
  "MOCK_TEMPLATE_TWIN_E2E",
  "MOCK_TEMPLATE_PHI_FLAG",
  "MOCK_RX_WARNINGS",
];
const inactiveSyntheticAuthEnvironments = new Map([
  ["AUTH_USE_MOCK", "false"],
  ["EMAIL_AUTO_CONFIRM_DOMAINS", ""],
  ["EMAIL_AUTO_CONFIRM_ALLOW_IN_PROD", "false"],
  ["RATE_LIMIT_DISABLED", "false"],
  ["RATE_LIMIT_DISABLE_ALLOW_IN_PROD", "false"],
]);
const ADMIN_CONTROL_SESSION_VERIFIER_PROFILE = "template-twin-admin-control-v1";

const expectedServices = new Map([
  ["transcribe-md", { artifact: "app", role: "physician-app" }],
  [
    "template-twin-admin-app",
    { artifact: "app", role: "template-twin-admin-app" },
  ],
  [
    "template-twin-admin-control",
    { artifact: "app", role: "template-twin-admin-control" },
  ],
  [
    "transcribe-md-worker",
    { artifact: "worker", role: "transcribe-md-worker" },
  ],
  [
    "template-twin-audit-dispatcher",
    { artifact: "worker", role: "template-twin-audit-dispatcher" },
  ],
  [
    "auth-email-dispatcher",
    { artifact: "worker", role: "auth-email-dispatcher" },
  ],
]);

let expectedAppImage = null;
let expectedWorkerImage = null;
let requireBridge = false;
for (let index = 2; index < process.argv.length; index += 1) {
  const argument = process.argv[index];
  if (argument === "--expected-app-image") {
    expectedAppImage = process.argv[index + 1] ?? null;
    index += 1;
  } else if (argument === "--expected-worker-image") {
    expectedWorkerImage = process.argv[index + 1] ?? null;
    index += 1;
  } else if (argument === "--require-bridge") {
    requireBridge = true;
  } else {
    fail("unexpected census argument");
  }
}
if ((expectedAppImage === null) !== (expectedWorkerImage === null)) {
  fail("both expected artifact images must be supplied together");
}

function fail(message) {
  process.stderr.write(`runtime-census: ${message}\n`);
  process.exit(65);
}

function artifactFor(service) {
  const dockerfile = service?.build?.dockerfile;
  if (dockerfile === "apps/transcribe-md/Dockerfile.worker") return "worker";
  if (
    dockerfile === "apps/transcribe-md/Dockerfile" &&
    service?.build?.target !== "builder"
  ) {
    return "app";
  }
  if (
    (expectedWorkerImage !== null && service?.image === expectedWorkerImage) ||
    service?.image?.includes("TRANSCRIBE_MD_WORKER_IMAGE") ||
    service?.labels?.[ARTIFACT_LABEL] === "worker"
  ) {
    return "worker";
  }
  if (
    (expectedAppImage !== null && service?.image === expectedAppImage) ||
    service?.image?.includes("TRANSCRIBE_MD_IMAGE") ||
    service?.labels?.[ARTIFACT_LABEL] === "app"
  ) {
    return "app";
  }
  return null;
}

let raw = "";
for await (const chunk of process.stdin) raw += chunk;

let model;
try {
  model = JSON.parse(raw);
} catch {
  fail("resolved Compose model is not valid JSON");
}

const services = model?.services;
if (!services || typeof services !== "object" || Array.isArray(services)) {
  fail("resolved Compose service map is unavailable");
}

const discovered = Object.entries(services)
  .filter(([, service]) => artifactFor(service) !== null)
  .map(([name]) => name)
  .sort();
const expectedNames = [...expectedServices.keys()].sort();
if (JSON.stringify(discovered) !== JSON.stringify(expectedNames)) {
  fail(
    "same-artifact service census drifted from the reviewed six-service set",
  );
}

for (const [name, expected] of expectedServices) {
  const service = services[name];
  const labels = service?.labels ?? {};
  const environment = service?.environment ?? {};
  if (artifactFor(service) !== expected.artifact) {
    fail(`${name} uses an unexpected build artifact`);
  }
  if (
    labels[MANAGED_LABEL] !== "true" ||
    labels[ARTIFACT_LABEL] !== expected.artifact
  ) {
    fail(`${name} lacks its exact rollback census labels`);
  }
  if (
    expected.role !== null &&
    environment.QUILLMD_SERVICE_ROLE !== expected.role
  ) {
    fail(`${name} has an unexpected service role`);
  }
  if (
    environment.QUILLMD_DATABASE_PRINCIPAL_PROFILE !== "exact-production-v1"
  ) {
    fail(`${name} lacks the exact production database-principal profile`);
  }
  if (environment.QUILLMD_REQUIRED_RUNTIME_PROTOCOL_EPOCH !== EXPECTED_EPOCH) {
    fail(`${name} lacks the required runtime protocol epoch`);
  }
  if (
    !["${TEMPLATE_TWIN_RUNTIME_MODE:-standard}", "rollback-compat-v2"].includes(
      environment.TEMPLATE_TWIN_RUNTIME_MODE,
    )
  ) {
    fail(`${name} has an unexpected runtime mode contract`);
  }
  if (
    !["${TEMPLATE_TWIN_KILL_SWITCH:-true}", "true"].includes(
      environment.TEMPLATE_TWIN_KILL_SWITCH,
    )
  ) {
    fail(`${name} has an unexpected kill-switch contract`);
  }
  for (const key of deterministicProviderEnvironments) {
    if (environment[key] !== "false") {
      fail(`${name} does not force ${key} off`);
    }
  }
  for (const [key, expectedValue] of inactiveSyntheticAuthEnvironments) {
    if (environment[key] !== expectedValue) {
      fail(`${name} does not force ${key} to its production-safe value`);
    }
  }
  const expectedSessionVerifier =
    expected.role === "template-twin-admin-control"
      ? ADMIN_CONTROL_SESSION_VERIFIER_PROFILE
      : "";
  if (
    environment.QUILLMD_AUTH_SESSION_VERIFIER_PROFILE !==
    expectedSessionVerifier
  ) {
    fail(`${name} has an unexpected authentication session-verifier profile`);
  }
  if (expectedAppImage !== null) {
    const expectedImage =
      expected.artifact === "app" ? expectedAppImage : expectedWorkerImage;
    if (service.image !== expectedImage) {
      fail(`${name} does not use the immutable rollback image`);
    }
  }
  if (
    requireBridge &&
    (environment.TEMPLATE_TWIN_RUNTIME_MODE !== "rollback-compat-v2" ||
      environment.TEMPLATE_TWIN_KILL_SWITCH !== "true")
  ) {
    fail(`${name} does not resolve to the fail-closed rollback state`);
  }
  if (
    requireBridge &&
    labels[CAPABILITY_LABEL] !== EXPECTED_ROLLBACK_CAPABILITY
  ) {
    fail(`${name} lacks the reviewed six-runtime rollback capability`);
  }
  if (requireBridge) {
    for (const attestationEnvironment of [
      "TEMPLATE_TWIN_RUNTIME_ATTESTATION",
      "TEMPLATE_TWIN_APP_RUNTIME_ATTESTATION",
      "TEMPLATE_TWIN_ADMIN_APP_RUNTIME_ATTESTATION",
      "TEMPLATE_TWIN_ADMIN_CONTROL_RUNTIME_ATTESTATION",
      "TEMPLATE_TWIN_WORKER_RUNTIME_ATTESTATION",
    ]) {
      if (environment[attestationEnvironment] !== "") {
        fail(`${name} retains a standard-mode runtime attestation`);
      }
    }
  }
}

const migrator = services["db-migrate"];
if (
  !migrator ||
  migrator?.build?.dockerfile !== "apps/transcribe-md/Dockerfile" ||
  migrator?.build?.target !== "builder" ||
  migrator?.labels?.[MANAGED_LABEL] === "true"
) {
  fail("the one-shot database migrator boundary drifted");
}

process.stdout.write(
  `runtime-census: PASS services=${expectedServices.size} migrator=excluded\n`,
);
