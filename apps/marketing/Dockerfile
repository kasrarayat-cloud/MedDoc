# ============================================================================
# TranscribeMD Marketing — Multi-stage Production Dockerfile (monorepo)
# ----------------------------------------------------------------------------
# Standalone Next.js output. Listens on PORT 3010 (matches the compose
# service mapping + the dev script in package.json). Build context is
# the monorepo root — `context: .` in docker-compose.yml.
#
# IMPORTANT: we COPY every workspace's package.json before `npm ci` so
# the workspace graph is complete. Omitting a sibling workspace's
# package.json is what caused the ioredis regression (see commit
# 1efd1b2); don't repeat that here.
# ============================================================================

# PR-K supply-chain hardening: every external base image pinned to a
# specific manifest digest so an upstream `node:22-alpine` rebuild
# can't change the bytes we ship without us reviewing it first.
# Bumps land via Dependabot's docker ecosystem.
#   node:22-alpine — pinned 2026-05-06 (linux/amd64)
ARG NODE_BASE=node@sha256:8ea2348b068a9544dae7317b4f3aafcdc032df1647bb7d768a05a5cad1a7683f

# ── Stage 1: Dependencies (prod only, for runtime copy) ──
FROM ${NODE_BASE} AS deps
WORKDIR /app
COPY package.json package-lock.json ./
COPY apps/meddoc-pro/package.json ./apps/meddoc-pro/package.json
COPY apps/marketing/package.json ./apps/marketing/package.json
COPY packages/db/package.json ./packages/db/package.json
COPY packages/auth/package.json ./packages/auth/package.json
COPY packages/types/package.json ./packages/types/package.json
COPY packages/ai/package.json ./packages/ai/package.json
RUN npm ci --omit=dev

# ── Stage 2: Build (full deps, runs next build) ──
FROM ${NODE_BASE} AS builder
WORKDIR /app
COPY package.json package-lock.json ./
COPY apps/meddoc-pro/package.json ./apps/meddoc-pro/package.json
COPY apps/marketing/package.json ./apps/marketing/package.json
COPY packages/db/package.json ./packages/db/package.json
COPY packages/auth/package.json ./packages/auth/package.json
COPY packages/types/package.json ./packages/types/package.json
COPY packages/ai/package.json ./packages/ai/package.json
RUN npm ci

COPY . .

# T-M19.2: NEXT_PUBLIC_* need to be in the build environment so the
# `next build` step inlines them into the client bundle + ISR'd HTML.
# Compose passes these via `build.args:` so a domain cutover is a
# single edit at the compose level — no .env-in-monorepo-root
# contamination dance required (npm workspaces runs `next build` from
# apps/marketing/ where root .env files aren't picked up).
ARG NEXT_PUBLIC_TRANSCRIBE_MD_APP_URL
ARG NEXT_PUBLIC_MARKETING_URL
ENV NEXT_PUBLIC_TRANSCRIBE_MD_APP_URL=${NEXT_PUBLIC_TRANSCRIBE_MD_APP_URL}
ENV NEXT_PUBLIC_MARKETING_URL=${NEXT_PUBLIC_MARKETING_URL}

ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build -w marketing

# ── Stage 3: Production Runner ──
FROM ${NODE_BASE} AS runner
WORKDIR /app

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

RUN addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 nextjs

# Standalone output bundles just what the runtime needs — no deps dir
# copy required. public/ + static/ live alongside the server.
COPY --from=builder /app/apps/marketing/public ./apps/marketing/public
COPY --from=builder /app/apps/marketing/.next/standalone ./
COPY --from=builder /app/apps/marketing/.next/static ./apps/marketing/.next/static

USER nextjs

EXPOSE 3010
ENV PORT=3010
ENV HOSTNAME="0.0.0.0"

# Standalone `docker run` healthcheck (compose-level healthcheck in
# docker-compose.yml provides the same signal for the orchestrator;
# this line covers `docker run` users + makes the image self-describing).
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD wget --quiet --tries=1 --spider http://127.0.0.1:3010/ || exit 1

CMD ["node", "apps/marketing/server.js"]
