# OpenClaw Application Dockerfile
# ============================================
# Multi-stage build for production deployment
# ============================================

FROM node:20-alpine AS builder

WORKDIR /app

# Copy package files
COPY package*.json ./
COPY tsconfig.json ./

# Install dependencies
RUN npm ci --only=production

# Copy source code
COPY src/ ./src/
COPY assets/ ./assets/

# Build TypeScript
RUN npx tsc || echo "TS build skipped (no tsc config)"

# ============================================
# Production stage
# ============================================
FROM node:20-alpine AS production

WORKDIR /app

# Install production dependencies only
COPY package*.json ./
RUN npm ci --only=production && npm cache clean --force

# Copy built artifacts from builder
COPY --from=builder /app/dist ./dist
COPY --from=builder /app/assets ./assets

# Create non-root user for security
RUN addgroup -g 1001 -S openclaw && \
    adduser -S openclaw -u 1001 -G openclaw

USER openclaw

# Environment
ENV NODE_ENV=production
ENV PORT=8080
ENV HEALTH_PORT=8081

# Expose ports
EXPOSE 8080 8081

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD wget -q --spider http://localhost:8081/health || exit 1

# Start both the app and health server
# Note: In production, consider running these as separate processes with a proper init system
CMD ["sh", "-c", "node dist/infrastructure/server/mcp_server.js & node dist/infrastructure/server/health_server.js & wait"]
