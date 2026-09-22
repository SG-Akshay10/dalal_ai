# Stage 1: Build Next.js Frontend
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend

COPY frontend/package*.json ./
RUN npm ci

COPY frontend ./
# Build Next.js app in standalone mode
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

# Stage 2: Final combined runner
FROM python:3.11-slim

# Install Node.js, Supervisor, and process runner tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    supervisor \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Set up Python backend
COPY backend/requirements.txt ./backend/
RUN pip install --no-cache-dir -r ./backend/requirements.txt

COPY backend ./backend

# Set up Next.js frontend standalone server and static assets
COPY --from=frontend-builder /app/frontend/.next/standalone ./frontend/
COPY --from=frontend-builder /app/frontend/.next/static ./frontend/.next/static
COPY --from=frontend-builder /app/frontend/public ./frontend/public

# Configure supervisord to manage both processes
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Environment defaults
ENV PORT=3000
ENV BACKEND_PORT=8000
ENV HOST=0.0.0.0

EXPOSE 3000 8000

CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
