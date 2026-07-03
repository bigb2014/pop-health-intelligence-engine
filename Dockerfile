# ── Stage 1: Builder ────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

# Install build deps for any compiled packages
RUN apt-get update && apt-get install -y --no-install-recommends gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy only requirements first for layer caching
COPY requirements.txt .

# Install to a prefix we can copy cleanly
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Stage 2: Runtime ────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

LABEL org.opencontainers.image.title="Pop-Health Intelligence Engine"
LABEL org.opencontainers.image.description="SDOH + Clinical risk scoring, prescriptive care plans, ROI quantification"
LABEL org.opencontainers.image.version="0.1.0"

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Create non-root user for security
RUN useradd -m -u 1000 appuser

WORKDIR /app

# Copy application source
COPY --chown=appuser:appuser src/ ./src/
COPY --chown=appuser:appuser app.py .

# Switch to non-root
USER appuser

EXPOSE 8501

# Streamlit config: bind all interfaces, no browser auto-open, fixed port
ENV STREAMLIT_SERVER_ADDRESS=0.0.0.0
ENV STREAMLIT_SERVER_PORT=8501
ENV STREAMLIT_SERVER_HEADLESS=true
ENV STREAMLIT_BROWSER_GATHER_USAGE_STATS=false
ENV PYTHONPATH=/app/src

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health')" || exit 1

CMD ["streamlit", "run", "app.py", \
     "--server.address=0.0.0.0", \
     "--server.port=8501", \
     "--server.headless=true", \
     "--browser.gatherUsageStats=false"]