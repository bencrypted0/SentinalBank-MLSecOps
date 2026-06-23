# Run this file using docker run and while connected to the 

# ── Stage 1: Build — install deps into an isolated prefix ──────────────
FROM python:3.11-slim@sha256:ae52c5bef62a6bdd42cd1e8dffef86b9cd284bde9427da79839de7a4b983e7ca AS builder

WORKDIR /build

COPY requirements.txt .

# --no-cache-dir keeps pip from leaving wheel cache in this layer
# --user installs to /root/.local, which we copy cleanly into final stage
RUN pip install --no-cache-dir --user -r requirements.txt

# ── Stage 2: Final — minimal runtime, no build tools, non-root ────────
FROM python:3.11-slim@sha256:ae52c5bef62a6bdd42cd1e8dffef86b9cd284bde9427da79839de7a4b983e7ca AS final

# Create dedicated non-root user/group (no shell, no home dir bloat)
RUN groupadd --gid 1000 trainer && \
    useradd --uid 1000 --gid trainer --no-create-home --shell /usr/sbin/nologin trainer

WORKDIR /app

# Copy installed packages from builder stage (no pip/build tools in final image)
COPY --from=builder /root/.local /home/trainer/.local

# Copy only what's needed to train — not the whole repo
COPY --chown=trainer:trainer train.py .
COPY --chown=trainer:trainer Dataset/paysim_trimmed.csv Dataset/paysim_trimmed.csv
COPY --chown=trainer:trainer artifacts/model.pkl artifacts/model.pkl

# Make pip --user installed packages discoverable
ENV PATH=/home/trainer/.local/bin:$PATH \
    PYTHONPATH=/home/trainer/.local/lib/python3.11/site-packages \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DATASET_PATH=/app/Dataset/paysim_trimmed.csv

# Artifacts dir needs to be writable by trainer user
RUN mkdir -p /app/artifacts && chown trainer:trainer /app/artifacts

USER trainer

ENTRYPOINT ["python", "train.py"]