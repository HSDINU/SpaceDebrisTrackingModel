# Çok aşamalı imaj: Cloud Run / docker compose → runtime hedefi
#   docker build --target runtime -t TAG .
# Yerel pipeline profili de runtime kullanır (kaynak kod builder'da yoktur).

# ── Build aşaması (yalnızca pip bağımlılıkları) ────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /app

# Sistem bağımlılıkları (LightGBM derleme için libgomp)
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -r requirements.txt

# ── Çalışma aşaması ─────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

WORKDIR /app

# Sadece runtime bağımlılığı (LightGBM OpenMP)
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Python paketlerini builder'dan kopyala
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Uygulama kaynak kodunu kopyala
# Not: data/ klasörü .dockerignore'da dahil edilmiş; eğer model + çıktılar
#      image içinde olmasın istiyorsanız volume mount kullanın (docker-compose.yml).
COPY . .

# Streamlit port
EXPOSE 8501

# Sağlık kontrolü
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health')" \
    || exit 1

# Streamlit yapılandırması (sunucu tarafı)
ENV STREAMLIT_SERVER_PORT=8501 \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0 \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false \
    PYTHONUNBUFFERED=1

ENTRYPOINT ["streamlit", "run", "app.py", \
            "--server.port=8501", \
            "--server.address=0.0.0.0", \
            "--server.headless=true", \
            "--browser.gatherUsageStats=false"]
