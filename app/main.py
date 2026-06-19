"""
SentinelBank — FastAPI Fraud Detection Serving API

# VULNERABILITY: No authentication on any endpoint
# VULNERABILITY: No rate limiting on any endpoint
# VULNERABILITY: Hardcoded database credentials (see below)
"""

import os
import json
from contextlib import asynccontextmanager

import numpy as np
import pandas as pd
from fastapi import FastAPI, Request

from schemas import TransactionInput, PredictionResponse
from model_loader import load_model

# VULNERABILITY: Hardcoded database password in source code
db_password = os.getenv("DB_PASSWORD")
db_connection_string = os.getenv("DATABASE_URL")

MODEL_VERSION = "1.0.0"


# ──────────────────────────── Lifespan ─────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load model once at startup; store in app.state."""
    model_path = os.getenv("MODEL_PATH", "../model_training/artifacts/model.pkl")
    app.state.model = load_model(model_path)

    # Try to load metadata (non-fatal if missing)
    metadata_path = os.path.join(
        os.path.dirname(os.path.abspath(model_path)),
        "model_metadata.json",
    )
    try:
        with open(metadata_path, "r") as f:
            app.state.model_metadata = json.load(f)
    except FileNotFoundError:
        app.state.model_metadata = {"error": "model_metadata.json not found"}

    yield  # app is running

    # Cleanup (nothing needed)


# ──────────────────────────── App ──────────────────────────────────────

# VULNERABILITY: No authentication middleware
# VULNERABILITY: No rate-limiting middleware
app = FastAPI(
    title="SentinelBank Fraud Detection API",
    description="Real-time fraud scoring for financial transactions.",
    version=MODEL_VERSION,
    lifespan=lifespan,
)


# ──────────────────────────── Endpoints ────────────────────────────────

@app.get("/health")
async def health(request: Request):
    """Health-check endpoint."""
    return {
        "status": "ok",
        "model_loaded": hasattr(request.app.state, "model") and request.app.state.model is not None,
    }


@app.post("/predict", response_model=PredictionResponse)
async def predict(transaction: TransactionInput, request: Request):
    """
    Score a single transaction for fraud.

    # VULNERABILITY: Returns raw (unrounded) float probability,
    # enabling model extraction / membership-inference attacks.
    """
    model = request.app.state.model

    # Build feature vector in the same column order the model was trained on
    feature_names = [
        "step", "amount", "oldbalanceOrg", "newbalanceOrig",
        "oldbalanceDest", "newbalanceDest",
        "type_CASH_IN", "type_CASH_OUT", "type_DEBIT", "type_PAYMENT", "type_TRANSFER",
        "errorBalanceOrig", "errorBalanceDest",
    ]

    row = {
        "step": transaction.step,
        "amount": transaction.amount,
        "oldbalanceOrg": transaction.oldbalanceOrg,
        "newbalanceOrig": transaction.newbalanceOrig,
        "oldbalanceDest": transaction.oldbalanceDest,
        "newbalanceDest": transaction.newbalanceDest,
        "type_CASH_IN": transaction.type_CASH_IN,
        "type_CASH_OUT": transaction.type_CASH_OUT,
        "type_DEBIT": transaction.type_DEBIT,
        "type_PAYMENT": transaction.type_PAYMENT,
        "type_TRANSFER": transaction.type_TRANSFER,
        "errorBalanceOrig": transaction.errorBalanceOrig,
        "errorBalanceDest": transaction.errorBalanceDest,
    }

    X = pd.DataFrame([row], columns=feature_names)
    proba = model.predict_proba(X)[0]

    # VULNERABILITY: Raw float probability returned without rounding
    fraud_probability = float(proba[1])
    fraud_label = "FRAUD" if fraud_probability >= 0.5 else "LEGIT"

    return PredictionResponse(
        fraud_probability=fraud_probability,
        fraud_label=fraud_label,
        model_version=MODEL_VERSION,
    )


@app.get("/model-info")
async def model_info(request: Request):
    """Return model metadata loaded from model_metadata.json."""
    return request.app.state.model_metadata


# ──────────────────────────── Entrypoint ───────────────────────────────

if __name__ == "__main__":
    import uvicorn

    # VULNERABILITY: DEBUG mode enabled — exposes stack traces and reload watcher
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True, log_level="debug")
