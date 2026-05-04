# Çok aşamalı imaj: Cloud Run → Next.js (frontend/) + Python ML pipeline
#   docker build --target runtime -t TAG .
# Çalışma dizini: Node server /app/frontend → process.cwd()/.. = /app (REPO_ROOT).
#
# ── Python bağımlılıkları ───────────────────────────────────────────────────
FROM python:3.11-slim AS py-builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -r requirements.txt

# ── Next.js üretim derlemesi ─────────────────────────────────────────────────
FROM node:20-bookworm-slim AS frontend-builder

WORKDIR /app/frontend

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

# ── Çalışma: Python + Node (standalone server) ─────────────────────────────
FROM python:3.11-slim AS runtime

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
        libgomp1 \
        curl \
        ca-certificates \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

COPY --from=py-builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=py-builder /usr/local/bin /usr/local/bin

COPY . /app/

WORKDIR /app/frontend
RUN rm -rf .next node_modules

COPY --from=frontend-builder /app/frontend/.next/standalone ./
COPY --from=frontend-builder /app/frontend/.next/static ./.next/static
COPY --from=frontend-builder /app/frontend/public ./public

ENV NODE_ENV=production \
    PYTHONUNBUFFERED=1 \
    HOSTNAME=0.0.0.0

EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD sh -c 'curl -fsS "http://127.0.0.1:${PORT:-3000}/api/health" >/dev/null || exit 1'

CMD ["sh", "-c", "exec node server.js"]
