# ============================================================================
# Scribe WebSocket sidecar image — runs src/ws-server.ts via tsx
# ----------------------------------------------------------------------------
# Separate container from the web + worker so the WS path can own its own
# port (SCRIBE_WS_PORT, default 3003) without conflicting with Next's
# standalone server on :3000. No ffmpeg here — the WS server doesn't
# touch audio files; audio is proxied straight through to Deepgram.
#
# Build context is the monorepo root (context: . in docker-compose.yml).
# ============================================================================

FROM node:22-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
COPY apps/meddoc-pro/package.json ./apps/meddoc-pro/package.json
COPY apps/scribe/package.json ./apps/scribe/package.json
COPY packages/db/package.json ./packages/db/package.json
COPY packages/auth/package.json ./packages/auth/package.json
COPY packages/types/package.json ./packages/types/package.json
COPY packages/ai/package.json ./packages/ai/package.json
# Server runs from source via tsx → needs full deps (no --omit=dev).
RUN npm ci

FROM node:22-alpine AS runner
WORKDIR /app

ENV NODE_ENV=production

# Whole workspace — tsx resolves imports from source paths, and the WS
# server touches apps/scribe/src/**, packages/db/src/**, packages/ai/src/**.
COPY --from=deps /app/node_modules ./node_modules
COPY . .

# Prisma client (generated into node_modules/@prisma/client by db package).
RUN npm run db:generate

RUN addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 wsuser
USER wsuser

EXPOSE 3003
CMD ["npx", "tsx", "apps/scribe/src/ws-server.ts"]
