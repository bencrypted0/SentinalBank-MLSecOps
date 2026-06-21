# SentinelBank — Fraud Detection Platform

> ⚠️ **This is a vulnerable-by-design repository for security training and CI/CD pipeline testing.**
> It contains intentional security vulnerabilities marked with `# VULNERABILITY:` comments.
> **Do NOT deploy this to production.**

## Overview

SentinelBank is a fintech fraud detection boilerplate with two components:

1. **Model Training** (`model_training/`) — An ML pipeline that trains a RandomForestClassifier on the PaySim synthetic financial dataset, evaluates it, and logs results to MLflow.
2. **Serving API** (`app/`) — A FastAPI application that loads the trained model and exposes real-time fraud scoring endpoints.

## Project Structure

```
SentinelBank/
├── app/
│   ├── main.py              # FastAPI application
│   ├── schemas.py            # Pydantic request/response models
│   ├── model_loader.py       # Pickle model loader
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .env.example
├── model_training/
│   ├── train.py              # Training pipeline
│   ├── requirements.txt
│   ├── dataset/              # Place paysim_sample.csv here
│   └── artifacts/            # model.pkl + model_metadata.json
├── docker-compose.yml
├── .gitignore
└── README.md
```

## Quick Start

### 1. Train the Model

```bash
python model_training/train.py
```

This will:
- Load 50,000 rows from the PaySim dataset
- Train a RandomForestClassifier
- Save `model.pkl` and `model_metadata.json` to `model_training/artifacts/`
- Attempt to log to MLflow (non-fatal if MLflow server is not running)

### 2. Run the API

```bash
uvicorn app.main:app --reload
```

The API will be available at `http://localhost:8000`.

### 3. Run with Docker Compose

```bash
docker-compose up
```

This starts three services:
- **app** — FastAPI serving API on port `8000`
- **mlflow** — MLflow tracking server on port `5000`
- **minio** — MinIO object storage on port `9000`

## API Endpoints

| Method | Path          | Description                       |
|--------|---------------|-----------------------------------|
| GET    | `/health`     | Health check                      |
| POST   | `/predict`    | Score a transaction for fraud     |
| GET    | `/model-info` | Return model training metadata    |

### Example Prediction Request

```bash
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{
    "step": 1,
    "type": "TRANSFER",
    "amount": 181000.0,
    "oldbalanceOrg": 181000.0,
    "newbalanceOrig": 0.0,
    "oldbalanceDest": 0.0,
    "newbalanceDest": 0.0,
    "errorBalanceOrig": 0.0,
    "errorBalanceDest": -181000.0,
    "type_CASH_IN": 0,
    "type_CASH_OUT": 0,
    "type_DEBIT": 0,
    "type_PAYMENT": 0,
    "type_TRANSFER": 1
  }'
```

## Intentional Vulnerabilities

All vulnerabilities are marked with `# VULNERABILITY:` comments in the source code. They include:

- No authentication or rate limiting on API endpoints
- Raw model probabilities returned (model extraction risk)
- Pickle deserialization without integrity checks
- No input validation beyond basic Pydantic types
- Hardcoded database credentials in source code
- Unpinned Docker base image without digest
- Container runs as root
- `COPY . .` in Dockerfile (copies secrets)
- `--reload` flag in production CMD
- Weak MinIO credentials (minioadmin/minioadmin)
- DEBUG mode enabled in uvicorn

These are designed to be detected by security scanning tools such as Bandit, Trivy, Snyk, Semgrep, and Hadolint.

## 📋 API Testing Scenarios (from `app/api_testing.md`)

Below are the PowerShell snippets you can run against the locally-running API.

### 1. Not Fraud — Small normal payment, balances match:
```powershell
$legit = @{
    step = 200
    type = "PAYMENT"
    amount = 50.0
    oldbalanceOrg = 5000.0
    newbalanceOrig = 4950.0
    oldbalanceDest = 10000.0
    newbalanceDest = 10050.0
    errorBalanceOrig = 0.0
    errorBalanceDest = 0.0
    type_CASH_IN = 0
    type_CASH_OUT = 0
    type_DEBIT = 0
    type_PAYMENT = 1
    type_TRANSFER = 0
} | ConvertTo-Json

Invoke-RestMethod -Uri http://localhost:8000/predict -Method Post -Body $legit -ContentType "application/json"
```

### 2. Slightly Suspicious — Medium cash-out, small balance error:
```powershell
$suspicious = @{
    step = 1
    type = "CASH_OUT"
    amount = 62000.0
    oldbalanceOrg = 62000.0
    newbalanceOrig = 0.0
    oldbalanceDest = 0.0
    newbalanceDest = 0.0
    errorBalanceOrig = 0.0
    errorBalanceDest = -62000.0
    type_CASH_IN = 0
    type_CASH_OUT = 1
    type_DEBIT = 0
    type_PAYMENT = 0
    type_TRANSFER = 0
} | ConvertTo-Json

Invoke-RestMethod -Uri http://localhost:8000/predict -Method Post -Body $suspicious -ContentType "application/json"
```

### 3. Definitely Fraud — Huge transfer, account fully drained, massive balance errors:
```powershell
$fraud = @{
    step = 1
    type = "TRANSFER"
    amount = 3500000.0
    oldbalanceOrg = 3500000.0
    newbalanceOrig = 0.0
    oldbalanceDest = 0.0
    newbalanceDest = 0.0
    errorBalanceOrig = 0.0
    errorBalanceDest = -3500000.0
    type_CASH_IN = 0
    type_CASH_OUT = 0
    type_DEBIT = 0
    type_PAYMENT = 0
    type_TRANSFER = 1
} | ConvertTo-Json

Invoke-RestMethod -Uri http://localhost:8000/predict -Method Post -Body $fraud -ContentType "application/json"
```

The key fraud signals the model learned from the PaySim data are:
- **Transaction type**: TRANSFER and CASH_OUT are riskier
- **Amount**: Very large amounts
- **Account draining**: `newbalanceOrig = 0` (entire balance sent out)
- **Destination doesn't update**: `newbalanceDest = 0` despite receiving money → large negative `errorBalanceDest`

## 🛠️ Command Summary for Training

```bash
# From the repository root
python model_training/train.py
```

### Running the Training Model with Docker

You can run the training pipeline inside a disposable Docker container that connects to the local MLflow and MinIO services.

Make sure you run docker compose up for the services to be available.

#### PowerShell (Windows)
```powershell
docker run -it --rm `
  --network sentinalbank_default `
  -v "${PWD}:/workspace" `
  -w /workspace `
  -e MLFLOW_TRACKING_URI=http://mlflow:5000 `
  -e MLFLOW_S3_ENDPOINT_URL=http://minio:9000 `
  -e AWS_ACCESS_KEY_ID=minioadmin `
  -e AWS_SECRET_ACCESS_KEY=minioadmin `
  python:3.11-slim `
  sh -c "pip install --no-cache-dir -r Model_Training/requirements.txt && python Model_Training/train.py"
```

#### Windows Command Prompt (CMD) / Bash (Linux/macOS)
```bash
docker run -it --rm \
  --network sentinalbank_default \
  -v "$(pwd):/workspace" \
  -w /workspace \
  -e MLFLOW_TRACKING_URI=http://mlflow:5000 \
  -e MLFLOW_S3_ENDPOINT_URL=http://minio:9000 \
  -e AWS_ACCESS_KEY_ID=minioadmin \
  -e AWS_SECRET_ACCESS_KEY=minioadmin \
  python:3.11-slim \
  sh -c "pip install --no-cache-dir -r Model_Training/requirements.txt && python Model_Training/train.py"
```

> **Note:** Ensure you install the updated dependencies if running locally:
```bash
pip install -r app/requirements.txt
pip install -r Model_Training/requirements.txt
```
