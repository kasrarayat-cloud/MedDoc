# ============================================================================
# TranscribeMD Solo App — Multi-stage Production Dockerfile (monorepo)
# ----------------------------------------------------------------------------
# Listens on PORT 3011 (matches the dev script in package.json + compose
# service mapping). Build context is the monorepo root — `context: .` in
# docker-compose.yml.
#
# Mirrors apps/scribe/Dockerfile. Every workspace's package.json is copied
# before `npm ci` so the workspace graph is complete (cf. ioredis regression
# caught in commit 1efd1b2).
# ============================================================================

# PR-K supply-chain hardening: every external base image pinned to a
# specific manifest digest so an upstream `node:22-alpine` rebuild
# can't change the bytes we ship without us reviewing it first.
# Bumps land via Dependabot's docker ecosystem.
#   node:22-alpine — pinned 2026-05-06 (linux/amd64)
ARG NODE_BASE=node@sha256:8ea2348b068a9544dae7317b4f3aafcdc032df1647bb7d768a05a5cad1a7683f

# ── Stage 1: Dependencies (production only) ──
FROM ${NODE_BASE} AS deps
WORKDIR /app
COPY package.json package-lock.json ./
COPY apps/meddoc-pro/package.json ./apps/meddoc-pro/package.json
COPY apps/marketing/package.json ./apps/marketing/package.json
COPY apps/transcribe-md/package.json ./apps/transcribe-md/package.json
COPY packages/db/package.json ./packages/db/package.json
COPY packages/auth/package.json ./packages/auth/package.json
COPY packages/types/package.json ./packages/types/package.json
COPY packages/ai/package.json ./packages/ai/package.json
RUN npm ci --omit=dev

# ── Stage 2: Build ──
FROM ${NODE_BASE} AS builder
WORKDIR /app
COPY package.json package-lock.json ./
COPY apps/meddoc-pro/package.json ./apps/meddoc-pro/package.json
COPY apps/marketing/package.json ./apps/marketing/package.json
COPY apps/transcribe-md/package.json ./apps/transcribe-md/package.json
COPY packages/db/package.json ./packages/db/package.json
COPY packages/auth/package.json ./packages/auth/package.json
COPY packages/types/package.json ./packages/types/package.json
COPY packages/ai/package.json ./packages/ai/package.json
RUN npm ci

COPY . .

# Prisma client must be generated before the Next build — @meddoc/db's
# default export is the instantiated client, so the .prisma/client
# artifacts must exist at import time. Same pattern as apps/scribe.
RUN npm run db:generate

# T-M19.2: mirror of apps/marketing/Dockerfile — NEXT_PUBLIC_* must be
# in the builder env so `next build` inlines them into client bundles
# + ISR HTML. See docker-compose.yml `build.args:` for the wiring.
ARG NEXT_PUBLIC_TRANSCRIBE_MD_APP_URL
ARG NEXT_PUBLIC_MARKETING_URL
ENV NEXT_PUBLIC_TRANSCRIBE_MD_APP_URL=${NEXT_PUBLIC_TRANSCRIBE_MD_APP_URL}
ENV NEXT_PUBLIC_MARKETING_URL=${NEXT_PUBLIC_MARKETING_URL}

# T-M20.3: NEXT_PUBLIC_SHOW_PIPELINE_TAB gates the dev-facing Pipeline
# tab on /visits/[id]. The gate is read in the server page at request
# time — a dev can flip the runtime env (via compose `environment:`)
# and reload without rebuilding. Default here is "false" so an image
# built with no override ships the tab hidden (production posture).
ARG NEXT_PUBLIC_SHOW_PIPELINE_TAB=false
ENV NEXT_PUBLIC_SHOW_PIPELINE_TAB=${NEXT_PUBLIC_SHOW_PIPELINE_TAB}

# Stage-1 core-flow redesign (C3 calm skin) gate. NEXT_PUBLIC_* must be set in
# the BUILDER env so `next build` inlines it into the client bundle (it is a
# build-time constant; a runtime override cannot flip it). Default "false" so
# an image built with no override ships the existing UI — production posture.
# Promote by building with `--build-arg NEXT_PUBLIC_SKIN_BETA=true`.
ARG NEXT_PUBLIC_SKIN_BETA=false
ENV NEXT_PUBLIC_SKIN_BETA=${NEXT_PUBLIC_SKIN_BETA}

# Ultrasound specialty gate. Like SKIN_BETA, NEXT_PUBLIC_* must be set in the
# BUILDER env so `next build` inlines it into the frontend bundle (the specialty
# pickers read it at build time; the worker reads the same var at runtime).
# Default "false" so an image built with no override never offers Ultrasound —
# production-byte-identical until promoted. Promote by building with
# `--build-arg NEXT_PUBLIC_ULTRASOUND_SPECIALTY=true`.
# ROLLBACK: NEXT_PUBLIC_ULTRASOUND_SPECIALTY=false docker compose build transcribe-md
#           && docker compose up -d --no-deps transcribe-md  (→ Ultrasound hidden).
ARG NEXT_PUBLIC_ULTRASOUND_SPECIALTY=false
ENV NEXT_PUBLIC_ULTRASOUND_SPECIALTY=${NEXT_PUBLIC_ULTRASOUND_SPECIALTY}

ENV NEXT_TELEMETRY_DISABLED=1
ENV QUILLMD_RUNTIME_PROTOCOL_EPOCH=template-twin-final-schema-v2

# ── Build heap (incident 2026-06-04) ──
# `next build` of this app hit V8's DEFAULT old-space ceiling and heap-OOM'd
# mid-build (a pure V8 heap limit — no kernel OOM in dmesg). The box has ~10GB
# free + 4GB swap, so a 6GB old-space builds comfortably. Builder-stage ENV
# only — the runner stage (512MB mem_limit) is a separate FROM and never
# inherits this.
ENV NODE_OPTIONS=--max-old-space-size=6144
RUN npm run build -w transcribe-md

# ── Stage 3: Production Runner ──
FROM ${NODE_BASE} AS runner
WORKDIR /app

ARG QUILLMD_RELEASE_SHA=development
LABEL org.opencontainers.image.revision="${QUILLMD_RELEASE_SHA}" \
      com.quillmd.runtime-protocol-epoch="template-twin-final-schema-v2" \
      com.quillmd.rollback-runtime-capability="six-runtime-v1" \
      com.quillmd.runtime-component="transcribe-md-app"

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
ENV QUILLMD_RUNTIME_PROTOCOL_EPOCH=template-twin-final-schema-v2
ENV QUILLMD_IMAGE_REVISION=${QUILLMD_RELEASE_SHA}
ENV QUILLMD_RUNTIME_COMPONENT=APP

# Template Twin static practice assets require bounded, local-only OCR before
# any extracted text may reach the independent privacy scan. Pin both the
# executable and English data to the reviewed Alpine 3.23 package revision;
# a repository drift removes the package and fails the image build closed.
RUN apk add --no-cache \
      tesseract-ocr=5.5.1-r0 \
      tesseract-ocr-data-eng=5.5.1-r0 && \
    test "$(tesseract --version | sed -n '1s/^tesseract //p')" = "5.5.1"

RUN addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 nextjs

COPY --from=builder /app/apps/transcribe-md/public ./apps/transcribe-md/public
COPY --from=builder /app/apps/transcribe-md/.next/standalone ./
COPY --from=builder /app/apps/transcribe-md/.next/static ./apps/transcribe-md/.next/static
COPY --from=builder /app/scripts/quillmd-next-runtime-entrypoint.mjs ./scripts/quillmd-next-runtime-entrypoint.mjs

# T-M21: PDF generator embeds Charter (body) + Inter Tight (labels)
# at request time via pdfkit's registerFont. The font files must be
# present in the runner image at the path lib/pdf-generator.ts
# resolves via join(process.cwd(), …). Standalone server runs with
# WORKDIR /app, so the relative join below lands on these COPY'd
# files. ~1MB total (4 Charter weights + 3 Inter Tight weights).
COPY --from=builder /app/apps/transcribe-md/fonts ./apps/transcribe-md/fonts

# Prisma runtime artifacts. Required because the standalone bundle loads
# @prisma/client at runtime and that module reads from node_modules/.prisma.
COPY --from=builder /app/packages/db/prisma ./packages/db/prisma
COPY --from=builder /app/node_modules/.prisma ./node_modules/.prisma
COPY --from=builder /app/node_modules/@prisma ./node_modules/@prisma
# Migrations don't run from this image — @prisma/config pulls ~75MB of
# transitive deps (effect, c12, jiti, …) that have no business in a
# runtime container. The dedicated `db-migrate` compose service targets
# the `builder` stage which already has the full toolchain. See
# docker-compose.yml and the "Migrations" note at the top of this file.

# unpdf (.pdf text extraction) — copied EXPLICITLY (incident 2026-06-04).
# node-file-trace does NOT pull unpdf into .next/standalone (it's an ESM dual-
# package; the shipped #277 image had MODULE_NOT_FOUND so .pdf advertised-but-
# failed). unpdf is self-contained (zero deps, vendored pdfjs) and extracts
# fine once present, so copy its single dir into the runtime node_modules —
# same pattern as the Prisma artifacts above. (pdf-parse traces on its own but
# its 2018 pdfjs hangs on Node 22, so a lib swap was rejected for this COPY.)
COPY --from=builder /app/node_modules/unpdf ./node_modules/unpdf

# ── Bundling assertion (incident 2026-06-04 — the permanent guardrail) ──
# Load every server-external extractor lib FROM the FINAL runtime node_modules
# (unpdf copied above + mammoth traced into the standalone). It ALSO imports
# `unpdf/pdfjs` — the import-only ESM subpath unpdf lazy-loads at parse time
# (dist/pdfjs.mjs) — so a partial COPY that dropped pdfjs can't slip through a
# require()-only check. A miss exits non-zero → the docker build FAILS, so an
# image that advertises .pdf/.docx upload but can't load its extractor can never
# ship again. Same class-kill as the #275 mammoth lesson; add new libs here.
RUN node --input-type=module -e "import{createRequire}from'module';const require=createRequire('/app/apps/transcribe-md/server.js');const fail=(m,e)=>{console.error('[bundle-assert] FAILED: '+m+' is not loadable from the runtime node_modules ('+((e&&(e.code||e.message))||e)+'); refusing to ship.');process.exit(1)};for(const m of ['unpdf','mammoth']){try{require(m)}catch(e){fail(m,e)}}try{await import('unpdf/pdfjs')}catch(e){fail('unpdf/pdfjs (lazy pdfjs subpath)',e)}console.log('[bundle-assert] OK -> unpdf, mammoth, unpdf/pdfjs')"

USER nextjs

EXPOSE 3011
ENV PORT=3011
ENV HOSTNAME="0.0.0.0"

# Standalone `docker run` healthcheck (compose-level healthcheck in
# docker-compose.yml provides the same signal for the orchestrator;
# this line covers `docker run` users + makes the image self-describing).
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD wget --quiet --tries=1 --spider http://127.0.0.1:3011/api/health || exit 1

CMD ["node", "scripts/quillmd-next-runtime-entrypoint.mjs", "node", "apps/transcribe-md/server.js"]
