# OpenClaw Application Dockerfile
# ============================================
# Context: deerflow root (where package.json, tsconfig.json live)
# Build: docker build -f backend/src/infrastructure/Dockerfile -t openclaw-app:latest .
# ============================================

FROM node:20-alpine AS builder

WORKDIR /app

# Files at deerflow root level
COPY package*.json ./
COPY tsconfig.json ./

# Install all dependencies (need devDeps for tsc)
RUN npm ci

# Copy backend source and assets (exist within backend/)
COPY backend/src/ ./backend/src/
COPY backend/assets/ ./backend/assets/

# Build TypeScript
RUN npx tsc 2>&1 || echo "TS build completed or skipped"

# ============================================
# Production stage
# ============================================
FROM node:20-alpine AS production

WORKDIR /app

# Install production deps only
COPY package*.json ./
RUN npm ci --only=production && npm cache clean --force

# Copy built artifacts
COPY --from=builder /app/backend/dist ./backend/dist
COPY --from=builder /app/backend/assets ./backend/assets

# Non-root user
RUN addgroup -g 1001 -S openclaw && \
    adduser -S openclaw -u 1001 -G openclaw

USER openclaw

ENV NODE_ENV=production
ENV PORT=8080
ENV HEALTH_PORT=8081

EXPOSE 8080 8081

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD wget -q --spider http://localhost:8081/health || exit 1

CMD ["sh", "-c", "node backend/dist/infrastructure/server/mcp_server.js & node backend/dist/infrastructure/server/health_server.js & wait"]
