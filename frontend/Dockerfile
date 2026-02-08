FROM node:20.11-alpine AS deps

WORKDIR /app

# Install dependencies
COPY package*.json ./
RUN npm ci

# =============================================================================
# Stage 2: Builder - Build the application
# =============================================================================
FROM node:20.11-alpine AS builder

WORKDIR /app

# Copy dependencies from deps stage
COPY --from=deps /app/node_modules ./node_modules

# Copy application source
COPY . .

# Set backend URL for build-time rewrites (Docker internal networking)
ENV BACKEND_URL=http://backend:8000
ENV NEXT_PUBLIC_API_URL=http://backend:8000

# Auth bypass disabled by default (set NEXT_PUBLIC_AUTH_BYPASS=true to bypass)
ARG NEXT_PUBLIC_AUTH_BYPASS=false
ENV NEXT_PUBLIC_AUTH_BYPASS=${NEXT_PUBLIC_AUTH_BYPASS}

# Build
RUN npm run build

# =============================================================================
# Stage 3: Runner - Minimal production image
# =============================================================================
FROM node:20.11-alpine AS runner

WORKDIR /app

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME="0.0.0.0"

# Create non-root user
RUN addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 nextjs

# Copy built application from builder
COPY --from=builder /app/public ./public

# Copy Next.js standalone output and static files
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

# Switch to non-root user
USER nextjs

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD wget -q --spider http://localhost:3000/ || exit 1

# Expose port
EXPOSE 3000

# Run standalone server
CMD ["node", "server.js"]
