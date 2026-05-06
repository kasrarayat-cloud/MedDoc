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

ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build -w transcribe-md

# ── Stage 3: Production Runner ──
FROM ${NODE_BASE} AS runner
WORKDIR /app

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

RUN addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 nextjs

COPY --from=builder /app/apps/transcribe-md/public ./apps/transcribe-md/public
COPY --from=builder /app/apps/transcribe-md/.next/standalone ./
COPY --from=builder /app/apps/transcribe-md/.next/static ./apps/transcribe-md/.next/static

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

USER nextjs

EXPOSE 3011
ENV PORT=3011
ENV HOSTNAME="0.0.0.0"

# Standalone `docker run` healthcheck (compose-level healthcheck in
# docker-compose.yml provides the same signal for the orchestrator;
# this line covers `docker run` users + makes the image self-describing).
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD wget --quiet --tries=1 --spider http://127.0.0.1:3011/api/health || exit 1

CMD ["node", "apps/transcribe-md/server.js"]
