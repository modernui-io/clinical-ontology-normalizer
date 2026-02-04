FROM node:20-alpine

WORKDIR /app

# Install dependencies
COPY package*.json ./
RUN npm ci

# Copy application
COPY . .

# Set backend URL for build-time rewrites (Docker internal networking)
ENV BACKEND_URL=http://backend:8000
ENV NEXT_PUBLIC_API_URL=http://backend:8000

# Auth bypass disabled by default (set NEXT_PUBLIC_AUTH_BYPASS=true to bypass)
ARG NEXT_PUBLIC_AUTH_BYPASS=false
ENV NEXT_PUBLIC_AUTH_BYPASS=${NEXT_PUBLIC_AUTH_BYPASS}

# Build
RUN npm run build

# Copy public and static files for standalone
RUN cp -r public .next/standalone/ 2>/dev/null || true
RUN cp -r .next/static .next/standalone/.next/ 2>/dev/null || true

# Expose port
EXPOSE 3000

# Run standalone server
CMD ["node", ".next/standalone/server.js"]
