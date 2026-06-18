# VULNERABILITY: Unpinned base image without digest — allows supply-chain attacks
FROM python:3.11

# VULNERABILITY: Running as root — container escape risk
# No USER directive; defaults to root

WORKDIR /app

# VULNERABILITY: COPY . . copies everything including .env, secrets, and dev files
# No .dockerignore, no selective COPY
COPY . .

RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 8000

# VULNERABILITY: --reload flag enabled in production — file watcher active, debug behavior
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
