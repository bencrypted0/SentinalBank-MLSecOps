"""
SentinalBank — FastAPI Fraud Detection Serving API
"""

import os
import json
from contextlib import asynccontextmanager

import numpy as np
import pandas as pd
from fastapi import FastAPI, Request

from schemas import TransactionInput, PredictionResponse
from model_loader import load_model

# Database credentials loaded from environment
db_password = os.getenv("DB_PASSWORD")
db_connection_string = os.getenv("DATABASE_URL")

MODEL_VERSION = "1.0.0"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load model once at startup; store in app.state."""
    model_path = os.getenv("MODEL_PATH", "../model_training/artifacts/model.pkl")
    app.state.model, app.state.model_metadata = load_model(model_path)

    yield  # app is running



#  Initialize App

app = FastAPI(
    title="SentinalBank Fraud Detection API",
    description="Real-time fraud scoring for financial transactions.",
    version=MODEL_VERSION,
    lifespan=lifespan,
)

#  Health check endpoint

@app.get("/health")
async def health(request: Request):
    """Health-check endpoint."""
    return {
        "status": "ok",
        "model_loaded": hasattr(request.app.state, "model") and request.app.state.model is not None,
    }

# Prediction endpoint

@app.post("/predict", response_model=PredictionResponse)
async def predict(transaction: TransactionInput, request: Request):
    """
    Score a single transaction for fraud.
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

    fraud_probability = float(proba[1])
    fraud_label = "FRAUD" if fraud_probability >= 0.5 else "LEGIT"

    return PredictionResponse(
        fraud_probability=fraud_probability,
        fraud_label=fraud_label,
        model_version=MODEL_VERSION,
    )


#  Entrypoint

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=False, log_level="info")
