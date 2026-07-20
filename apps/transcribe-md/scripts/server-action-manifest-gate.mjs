#!/usr/bin/env node

import { createHash } from "node:crypto";
import { promises as fs } from "node:fs";
import { createRequire } from "node:module";
import path from "node:path";
import { fileURLToPath } from "node:url";

import ts from "typescript";

const SCRIPT_DIR = path.dirname(fileURLToPath(import.meta.url));
const DEFAULT_PROJECT_DIR = path.resolve(SCRIPT_DIR, "..");
const DEFAULT_POLICY_PATH = path.join(SCRIPT_DIR, "server-action-policy.json");
const MANIFEST_WORKSPACE_PREFIX = "apps/transcribe-md/";
const VALID_CLASSIFICATIONS = new Set([
  "AUTH_ENTRYPOINT",
  "SELF_SESSION",
  "PHYSICIAN_CLINICAL",
]);

// Review lock for the canonicalized policy. This is change detection, not a
// signature: any update requires a visible two-file diff and fresh review.
export const APPROVED_POLICY_SHA256 =
  "8d6b2f16cea34e558b77aa7487e02f95b4b4cbce0a158d3964962f60ceafd0df";

function fail(message) {
  throw new Error(`[server-action-manifest-gate] ${message}`);
}

function isRecord(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function exactKeys(value, expected, label) {
  const actual = Object.keys(value).sort();
  const wanted = [...expected].sort();
  if (JSON.stringify(actual) !== JSON.stringify(wanted)) {
    fail(
      `${label} keys changed (expected ${wanted.join(", ")}; received ${actual.join(", ")})`,
    );
  }
}

function actionKey(moduleName, exportedName) {
  return `${moduleName}#${exportedName}`;
}

function normalizeModuleName(raw, projectDir) {
  if (typeof raw !== "string" || raw.trim() === "" || raw.includes("\0")) {
    fail("encountered an empty or invalid Server Function filename");
  }

  let normalized = raw.replaceAll("\\", "/");
  if (path.isAbsolute(raw)) {
    normalized = path.relative(projectDir, raw).replaceAll("\\", "/");
  }
  normalized = path.posix.normalize(normalized.replace(/^\.\//, ""));
  if (normalized.startsWith(MANIFEST_WORKSPACE_PREFIX)) {
    normalized = normalized.slice(MANIFEST_WORKSPACE_PREFIX.length);
  }

  if (
    normalized === "." ||
    normalized === ".." ||
    normalized.startsWith("../") ||
    path.posix.isAbsolute(normalized)
  ) {
    fail(`Server Function filename escapes the application root: ${raw}`);
  }
  return normalized;
}

function canonicalPolicy(policy) {
  return JSON.stringify({
    schemaVersion: policy.schemaVersion,
    nextMajor: policy.nextMajor,
    expectedModuleCount: policy.expectedModuleCount,
    expectedActionCount: policy.expectedActionCount,
    expectedCompiledActionCount: policy.expectedCompiledActionCount,
    expectedCompiledExclusions: [...policy.expectedCompiledExclusions].sort(
      (left, right) =>
        actionKey(left.module, left.exportedName).localeCompare(
          actionKey(right.module, right.exportedName),
        ),
    ),
    expectedClassificationCounts: Object.fromEntries(
      Object.entries(policy.expectedClassificationCounts).sort(
        ([left], [right]) => left.localeCompare(right),
      ),
    ),
    actions: [...policy.actions].sort((left, right) =>
      actionKey(left.module, left.exportedName).localeCompare(
        actionKey(right.module, right.exportedName),
      ),
    ),
  });
}

export function policySha256(policy) {
  return createHash("sha256").update(canonicalPolicy(policy)).digest("hex");
}

export async function loadPolicy(
  policyPath = DEFAULT_POLICY_PATH,
  { expectedPolicySha256 = APPROVED_POLICY_SHA256 } = {},
) {
  let policy;
  try {
    policy = JSON.parse(await fs.readFile(policyPath, "utf8"));
  } catch (error) {
    fail(
      `cannot read policy ${policyPath}: ${error instanceof Error ? error.message : String(error)}`,
    );
  }

  if (!isRecord(policy)) fail("policy root must be an object");
  exactKeys(
    policy,
    [
      "schemaVersion",
      "nextMajor",
      "expectedModuleCount",
      "expectedActionCount",
      "expectedCompiledActionCount",
      "expectedCompiledExclusions",
      "expectedClassificationCounts",
      "actions",
    ],
    "policy root",
  );
  if (policy.schemaVersion !== 2) fail("unsupported policy schema version");
  if (policy.nextMajor !== 16)
    fail("policy must target the installed Next 16 manifest contract");
  if (!Array.isArray(policy.actions)) fail("policy actions must be an array");
  if (!Array.isArray(policy.expectedCompiledExclusions)) {
    fail("policy compiled exclusions must be an array");
  }
  if (!isRecord(policy.expectedClassificationCounts)) {
    fail("policy classification counts must be an object");
  }
  exactKeys(
    policy.expectedClassificationCounts,
    VALID_CLASSIFICATIONS,
    "policy classification counts",
  );

  const seen = new Set();
  const modules = new Set();
  const actualClassificationCounts = Object.fromEntries(
    [...VALID_CLASSIFICATIONS].map((classification) => [classification, 0]),
  );
  for (const action of policy.actions) {
    if (!isRecord(action)) fail("each policy action must be an object");
    exactKeys(
      action,
      ["module", "exportedName", "classification"],
      "policy action",
    );
    const moduleName = normalizeModuleName(action.module, DEFAULT_PROJECT_DIR);
    if (moduleName !== action.module || !moduleName.startsWith("src/")) {
      fail(`policy module must be a canonical src/ path: ${action.module}`);
    }
    if (
      typeof action.exportedName !== "string" ||
      action.exportedName.trim() === ""
    ) {
      fail("policy exportedName must be a non-empty string");
    }
    if (!VALID_CLASSIFICATIONS.has(action.classification)) {
      fail(
        `unknown policy classification for ${actionKey(moduleName, action.exportedName)}`,
      );
    }
    const key = actionKey(moduleName, action.exportedName);
    if (seen.has(key)) fail(`duplicate policy action: ${key}`);
    seen.add(key);
    modules.add(moduleName);
    actualClassificationCounts[action.classification] += 1;
  }

  if (policy.actions.length !== policy.expectedActionCount) {
    fail(
      `policy action count is ${policy.actions.length}, expected ${policy.expectedActionCount}`,
    );
  }
  if (modules.size !== policy.expectedModuleCount) {
    fail(
      `policy module count is ${modules.size}, expected ${policy.expectedModuleCount}`,
    );
  }

  const compiledExclusionKeys = new Set();
  for (const exclusion of policy.expectedCompiledExclusions) {
    if (!isRecord(exclusion)) fail("each compiled exclusion must be an object");
    exactKeys(exclusion, ["module", "exportedName"], "compiled exclusion");
    const moduleName = normalizeModuleName(
      exclusion.module,
      DEFAULT_PROJECT_DIR,
    );
    if (moduleName !== exclusion.module || !moduleName.startsWith("src/")) {
      fail(
        `compiled exclusion module must be a canonical src/ path: ${exclusion.module}`,
      );
    }
    if (
      typeof exclusion.exportedName !== "string" ||
      exclusion.exportedName.trim() === ""
    ) {
      fail("compiled exclusion exportedName must be a non-empty string");
    }
    const key = actionKey(moduleName, exclusion.exportedName);
    if (!seen.has(key))
      fail(`compiled exclusion is not in the source policy: ${key}`);
    if (compiledExclusionKeys.has(key))
      fail(`duplicate compiled exclusion: ${key}`);
    compiledExclusionKeys.add(key);
  }
  if (
    !Number.isSafeInteger(policy.expectedCompiledActionCount) ||
    policy.expectedCompiledActionCount < 0 ||
    policy.actions.length - compiledExclusionKeys.size !==
      policy.expectedCompiledActionCount
  ) {
    fail("policy compiled action count does not match its exact exclusions");
  }
  for (const classification of VALID_CLASSIFICATIONS) {
    if (
      actualClassificationCounts[classification] !==
      policy.expectedClassificationCounts[classification]
    ) {
      fail(`policy ${classification} count changed`);
    }
  }

  const digest = policySha256(policy);
  if (expectedPolicySha256 !== null && digest !== expectedPolicySha256) {
    fail(`policy classification or census changed (review lock ${digest})`);
  }

  return { policy, digest };
}

async function sourceFiles(root) {
  const result = [];
  for (const entry of await fs.readdir(root, { withFileTypes: true })) {
    const candidate = path.join(root, entry.name);
    if (entry.isDirectory()) {
      result.push(...(await sourceFiles(candidate)));
    } else if (/\.(?:[cm]?[jt]sx?)$/.test(entry.name)) {
      result.push(candidate);
    }
  }
  return result.sort();
}

function hasModifier(node, kind) {
  return node.modifiers?.some((modifier) => modifier.kind === kind) ?? false;
}

function isUseServerDirective(statement) {
  return (
    ts.isExpressionStatement(statement) &&
    ts.isStringLiteral(statement.expression) &&
    statement.expression.text === "use server"
  );
}

function hasUseServerDirective(statements) {
  for (const statement of statements) {
    if (
      !ts.isExpressionStatement(statement) ||
      !ts.isStringLiteral(statement.expression)
    ) {
      return false;
    }
    if (isUseServerDirective(statement)) return true;
  }
  return false;
}

function unwrapExpression(expression) {
  let current = expression;
  while (
    ts.isParenthesizedExpression(current) ||
    ts.isAsExpression(current) ||
    ts.isSatisfiesExpression(current)
  ) {
    current = current.expression;
  }
  return current;
}

function exportedRuntimeNames(sourceFile, moduleName) {
  const names = [];
  for (const statement of sourceFile.statements) {
    if (ts.isExportDeclaration(statement)) {
      const isTypeOnly =
        statement.isTypeOnly ||
        (statement.exportClause &&
          ts.isNamedExports(statement.exportClause) &&
          statement.exportClause.elements.every(
            (element) => element.isTypeOnly,
          ));
      if (!isTypeOnly) {
        fail(
          `runtime export lists are not allowed in use-server module ${moduleName}`,
        );
      }
      continue;
    }
    if (ts.isExportAssignment(statement)) {
      fail(
        `runtime export assignments are not allowed in use-server module ${moduleName}`,
      );
    }
    if (!hasModifier(statement, ts.SyntaxKind.ExportKeyword)) continue;

    if (
      ts.isInterfaceDeclaration(statement) ||
      ts.isTypeAliasDeclaration(statement) ||
      (ts.isImportDeclaration(statement) && statement.importClause?.isTypeOnly)
    ) {
      continue;
    }

    if (ts.isFunctionDeclaration(statement)) {
      if (!hasModifier(statement, ts.SyntaxKind.AsyncKeyword)) {
        fail(`non-async runtime export in use-server module ${moduleName}`);
      }
      if (hasModifier(statement, ts.SyntaxKind.DefaultKeyword)) {
        names.push("default");
      } else if (statement.name) {
        names.push(statement.name.text);
      } else {
        fail(`anonymous runtime export in use-server module ${moduleName}`);
      }
      continue;
    }

    if (ts.isVariableStatement(statement)) {
      for (const declaration of statement.declarationList.declarations) {
        if (!ts.isIdentifier(declaration.name) || !declaration.initializer) {
          fail(
            `unsupported runtime variable export in use-server module ${moduleName}`,
          );
        }
        const initializer = unwrapExpression(declaration.initializer);
        if (
          !(
            ts.isArrowFunction(initializer) ||
            ts.isFunctionExpression(initializer)
          ) ||
          !hasModifier(initializer, ts.SyntaxKind.AsyncKeyword)
        ) {
          fail(
            `non-async runtime variable export in use-server module ${moduleName}`,
          );
        }
        names.push(declaration.name.text);
      }
      continue;
    }

    fail(`unsupported runtime export kind in use-server module ${moduleName}`);
  }
  return names;
}

function assertNoInlineServerFunctions(sourceFile, moduleName) {
  function visit(node) {
    if (
      ts.isFunctionLike(node) &&
      node.body &&
      ts.isBlock(node.body) &&
      hasUseServerDirective(node.body.statements)
    ) {
      fail(
        `inline Server Function is not allowed by the auditable module policy: ${moduleName}`,
      );
    }
    ts.forEachChild(node, visit);
  }
  visit(sourceFile);
}

export async function collectSourceServerFunctions(
  projectDir = DEFAULT_PROJECT_DIR,
) {
  const srcDir = path.join(projectDir, "src");
  const actions = [];
  for (const filename of await sourceFiles(srcDir)) {
    const sourceText = await fs.readFile(filename, "utf8");
    const sourceFile = ts.createSourceFile(
      filename,
      sourceText,
      ts.ScriptTarget.Latest,
      true,
      filename.endsWith("x") ? ts.ScriptKind.TSX : ts.ScriptKind.TS,
    );
    const moduleName = normalizeModuleName(filename, projectDir);
    if (sourceFile.parseDiagnostics.length > 0) {
      fail(
        `cannot parse source while censusing Server Functions: ${moduleName}`,
      );
    }
    assertNoInlineServerFunctions(sourceFile, moduleName);
    if (!hasUseServerDirective(sourceFile.statements)) continue;
    for (const exportedName of exportedRuntimeNames(sourceFile, moduleName)) {
      actions.push({ module: moduleName, exportedName });
    }
  }
  return actions.sort((left, right) =>
    actionKey(left.module, left.exportedName).localeCompare(
      actionKey(right.module, right.exportedName),
    ),
  );
}

export async function verifySourceCensus({
  projectDir = DEFAULT_PROJECT_DIR,
  policyPath = DEFAULT_POLICY_PATH,
  expectedPolicySha256 = APPROVED_POLICY_SHA256,
} = {}) {
  const { policy, digest } = await loadPolicy(policyPath, {
    expectedPolicySha256,
  });
  const sourceActions = await collectSourceServerFunctions(projectDir);
  const policyByKey = new Map(
    policy.actions.map((action) => [
      actionKey(action.module, action.exportedName),
      action,
    ]),
  );
  const sourceKeys = new Set(
    sourceActions.map((action) =>
      actionKey(action.module, action.exportedName),
    ),
  );
  const unknown = [...sourceKeys].filter((key) => !policyByKey.has(key));
  const missing = [...policyByKey.keys()].filter((key) => !sourceKeys.has(key));
  if (unknown.length > 0 || missing.length > 0) {
    fail(
      `source census differs from policy; unknown=[${unknown.join(", ")}], missing=[${missing.join(", ")}]`,
    );
  }

  const compiledExclusionKeys = new Set(
    policy.expectedCompiledExclusions.map((exclusion) =>
      actionKey(exclusion.module, exclusion.exportedName),
    ),
  );
  const expectedCompiledKeys = new Set(
    [...policyByKey.keys()].filter((key) => !compiledExclusionKeys.has(key)),
  );

  return {
    policy,
    policyByKey,
    policyDigest: digest,
    compiledExclusionKeys,
    expectedCompiledKeys,
    sourceActionCount: sourceActions.length,
    sourceModuleCount: new Set(sourceActions.map((action) => action.module))
      .size,
  };
}

function validateManifestRoot(manifest) {
  if (!isRecord(manifest)) fail("compiled manifest root must be an object");
  exactKeys(
    manifest,
    ["node", "edge", "encryptionKey"],
    "compiled manifest root",
  );
  if (!isRecord(manifest.node) || !isRecord(manifest.edge)) {
    fail("compiled manifest node and edge entries must be objects");
  }
  if (
    typeof manifest.encryptionKey !== "string" ||
    manifest.encryptionKey.trim() === ""
  ) {
    fail("compiled manifest encryption key is absent");
  }
}

function manifestActions(manifest, projectDir) {
  const byActionId = new Map();
  const byIdentity = new Map();
  for (const runtime of ["node", "edge"]) {
    for (const [actionId, entry] of Object.entries(manifest[runtime])) {
      if (
        typeof actionId !== "string" ||
        actionId.trim() === "" ||
        !isRecord(entry)
      ) {
        fail(`malformed ${runtime} manifest action entry`);
      }
      const allowedKeys = new Set([
        "filename",
        "exportedName",
        "workers",
        "layer",
      ]);
      const unknownKeys = Object.keys(entry).filter(
        (key) => !allowedKeys.has(key),
      );
      if (unknownKeys.length > 0) {
        fail(
          `compiled ${runtime} action entry schema changed: ${unknownKeys.join(", ")}`,
        );
      }
      if (
        typeof entry.exportedName !== "string" ||
        entry.exportedName.trim() === "" ||
        !isRecord(entry.workers) ||
        Object.keys(entry.workers).length === 0
      ) {
        fail(`compiled ${runtime} action entry is missing identity or workers`);
      }
      if (entry.layer !== undefined && !isRecord(entry.layer)) {
        fail(`compiled ${runtime} action layer is malformed`);
      }
      const moduleName = normalizeModuleName(entry.filename, projectDir);
      const identity = actionKey(moduleName, entry.exportedName);
      const priorIdentity = byActionId.get(actionId);
      if (priorIdentity !== undefined && priorIdentity !== identity) {
        fail("one compiled action ID resolves to multiple Server Functions");
      }
      const priorActionId = byIdentity.get(identity);
      if (priorActionId !== undefined && priorActionId !== actionId) {
        fail(
          `one Server Function resolves to multiple compiled action IDs: ${identity}`,
        );
      }
      byActionId.set(actionId, identity);
      byIdentity.set(identity, actionId);
    }
  }
  if (byIdentity.size === 0)
    fail("compiled manifest contains no Server Functions");
  return [...byIdentity.keys()].sort();
}

async function assertInstalledNextMajor(projectDir, expectedMajor) {
  let packageJson;
  try {
    const projectRequire = createRequire(path.join(projectDir, "package.json"));
    const nextPackagePath = projectRequire.resolve("next/package.json");
    packageJson = JSON.parse(await fs.readFile(nextPackagePath, "utf8"));
  } catch (error) {
    fail(
      `cannot read installed Next version: ${error instanceof Error ? error.message : String(error)}`,
    );
  }
  const major = Number.parseInt(String(packageJson.version).split(".")[0], 10);
  if (major !== expectedMajor) {
    fail(
      `installed Next major ${major} differs from reviewed manifest contract ${expectedMajor}`,
    );
  }
  return packageJson.version;
}

export async function verifyServerActionManifest({
  projectDir = DEFAULT_PROJECT_DIR,
  policyPath = DEFAULT_POLICY_PATH,
  manifestPath = path.join(
    projectDir,
    ".next",
    "server",
    "server-reference-manifest.json",
  ),
  expectedPolicySha256 = APPROVED_POLICY_SHA256,
  verifyInstalledNext = true,
} = {}) {
  const source = await verifySourceCensus({
    projectDir,
    policyPath,
    expectedPolicySha256,
  });
  const installedNextVersion = verifyInstalledNext
    ? await assertInstalledNextMajor(projectDir, source.policy.nextMajor)
    : null;
  let manifest;
  try {
    manifest = JSON.parse(await fs.readFile(manifestPath, "utf8"));
  } catch (error) {
    fail(
      `cannot read compiled manifest ${manifestPath}: ${error instanceof Error ? error.message : String(error)}`,
    );
  }
  validateManifestRoot(manifest);
  const compiledIdentities = manifestActions(manifest, projectDir);
  const compiledIdentitySet = new Set(compiledIdentities);
  const unknownCompiled = compiledIdentities.filter(
    (identity) => !source.policyByKey.has(identity),
  );
  const unexpectedlyCompiled = compiledIdentities.filter(
    (identity) =>
      source.policyByKey.has(identity) &&
      !source.expectedCompiledKeys.has(identity),
  );
  const missingCompiled = [...source.expectedCompiledKeys]
    .filter((identity) => !compiledIdentitySet.has(identity))
    .sort();
  if (
    unknownCompiled.length > 0 ||
    unexpectedlyCompiled.length > 0 ||
    missingCompiled.length > 0
  ) {
    fail(
      `compiled manifest differs from classified source; unclassified=[${unknownCompiled.join(", ")}], unexpected=[${unexpectedlyCompiled.join(", ")}], missing=[${missingCompiled.join(", ")}]`,
    );
  }

  const compiledClassificationCounts = Object.fromEntries(
    [...VALID_CLASSIFICATIONS].map((classification) => [classification, 0]),
  );
  for (const identity of compiledIdentities) {
    compiledClassificationCounts[
      source.policyByKey.get(identity).classification
    ] += 1;
  }

  return {
    ...source,
    installedNextVersion,
    manifestPath,
    compiledActionCount: compiledIdentities.length,
    compiledClassificationCounts,
  };
}

function parseArguments(argv) {
  const options = {};
  for (let index = 0; index < argv.length; index += 1) {
    const argument = argv[index];
    const value = argv[index + 1];
    if (
      !["--project-dir", "--policy", "--manifest"].includes(argument) ||
      value === undefined
    ) {
      fail(`unsupported or incomplete argument: ${argument}`);
    }
    index += 1;
    if (argument === "--project-dir") options.projectDir = path.resolve(value);
    if (argument === "--policy") options.policyPath = path.resolve(value);
    if (argument === "--manifest") options.manifestPath = path.resolve(value);
  }
  return options;
}

if (
  process.argv[1] &&
  path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)
) {
  try {
    const result = await verifyServerActionManifest(
      parseArguments(process.argv.slice(2)),
    );
    console.log(
      `[server-action-manifest-gate] PASS Next ${result.installedNextVersion}; ` +
        `${result.sourceActionCount} classified source exports in ${result.sourceModuleCount} modules; ` +
        `${result.compiledActionCount} compiled exports classified`,
    );
  } catch (error) {
    console.error(error instanceof Error ? error.message : String(error));
    process.exitCode = 1;
  }
}
