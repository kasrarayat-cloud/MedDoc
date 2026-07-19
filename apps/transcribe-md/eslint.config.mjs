import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  {
    files: ["src/**/*.{js,jsx,ts,tsx}"],
    ignores: [
      "src/**/*.test.{js,jsx,ts,tsx}",
      "src/**/*.spec.{js,jsx,ts,tsx}",
      "src/**/__tests__/**",
      "src/lib/note-template-docx/office-docx-byte-readback.ts",
      "src/lib/note-template-docx/office-roundtrip-qa.ts",
      "src/lib/note-template-docx/office-schema-evidence.ts",
    ],
    rules: {
      "no-restricted-imports": [
        "error",
        {
          patterns: [
            {
              group: [
                "**/office-docx-byte-readback*",
                "**/office-roundtrip-qa*",
                "**/office-schema-evidence*",
              ],
              message:
                "Office round-trip evidence is synthetic QA-only and must never enter production signing, certification, worker, correction, import, export, or download code.",
            },
          ],
        },
      ],
    },
  },
  globalIgnores([
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
  ]),
]);

export default eslintConfig;
