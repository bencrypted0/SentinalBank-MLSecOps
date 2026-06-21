# =============================================
# STAGE 1: Builder (install dependencies)
# =============================================
FROM python@sha256:ae52c5bef62a6bdd42cd1e8dffef86b9cd284bde9427da79839de7a4b983e7ca AS builder

WORKDIR /app

# Install build deps only in builder stage
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# =============================================
# STAGE 2: Final minimal runtime image
# =============================================
FROM python@sha256:ae52c5bef62a6bdd42cd1e8dffef86b9cd284bde9427da79839de7a4b983e7ca

WORKDIR /app

# Copy only Python packages from builder
COPY --from=builder /root/.local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /root/.local/bin /usr/local/bin

# Copy only necessary application files (selective COPY)
COPY . .

# Create non-root user and switch to it
RUN useradd -m -u 1001 appuser && \
    chown -R appuser:appuser /app
USER 1001

EXPOSE 8000

# Production-ready command (no --reload)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]