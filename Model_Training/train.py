"""
SentinelBank — Fraud Detection Model Training Pipeline
Trains a RandomForestClassifier on the PaySim dataset and logs results to MLflow.
"""

import os
import sys
import json
import pickle
import datetime

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score,
    confusion_matrix,
)
import mlflow
import mlflow.sklearn


# ──────────────────────────── Configuration ────────────────────────────

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)

DATASET_PATH = os.path.join(PROJECT_ROOT, "Model_Training", "Dataset", "paysim_sample.csv")
ARTIFACTS_DIR = os.path.join(BASE_DIR, "artifacts")
MODEL_PATH = os.path.join(ARTIFACTS_DIR, "model.pkl")
METADATA_PATH = os.path.join(ARTIFACTS_DIR, "model_metadata.json")

SAMPLE_SIZE = 50_000
TEST_SIZE = 0.20
RANDOM_STATE = 42

MLFLOW_TRACKING_URI = "http://localhost:5000"
EXPERIMENT_NAME = "sentinelbank-fraud-detection"
MODEL_REGISTRY_NAME = "SentinelBankFraudModel"

DROP_COLUMNS = ["nameOrig", "nameDest", "isFlaggedFraud"]
TYPE_CATEGORIES = ["CASH_IN", "CASH_OUT", "DEBIT", "PAYMENT", "TRANSFER"]

RF_PARAMS = {
    "n_estimators": 100,
    "max_depth": 10,
    "random_state": RANDOM_STATE,
    "class_weight": "balanced",
}


# ──────────────────────────── Helpers ──────────────────────────────────


def load_data(path: str, sample_size: int) -> pd.DataFrame:
    """Load the PaySim CSV and take a random sample."""
    print(f"[*] Loading dataset from {path}")
    df = pd.read_csv(path)
    print(f"    Total rows in file: {len(df):,}")

    if len(df) > sample_size:
        df = df.sample(n=sample_size, random_state=RANDOM_STATE)
        print(f"    Sampled down to {sample_size:,} rows")
    else:
        print(f"    Using all {len(df):,} rows (below sample threshold)")

    return df.reset_index(drop=True)


def preprocess(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series, list[str]]:
    """
    Drop unnecessary columns, one-hot encode 'type', and feature-engineer
    error-balance columns.  Returns (X, y, feature_names).
    """
    print("[*] Preprocessing …")

    # Drop columns
    df = df.drop(columns=DROP_COLUMNS, errors="ignore")

    # One-hot encode 'type'
    for cat in TYPE_CATEGORIES:
        df[f"type_{cat}"] = (df["type"] == cat).astype(int)
    df = df.drop(columns=["type"])

    # Feature engineering
    df["errorBalanceOrig"] = df["newbalanceOrig"] - df["oldbalanceOrg"] + df["amount"]
    df["errorBalanceDest"] = df["newbalanceDest"] - df["oldbalanceDest"] - df["amount"]

    # Separate target
    y = df["isFraud"]
    X = df.drop(columns=["isFraud"])

    feature_names = X.columns.tolist()
    print(f"    Features ({len(feature_names)}): {feature_names}")
    print(f"    Fraud distribution:\n{y.value_counts().to_string()}")

    return X, y, feature_names


def train_model(X_train, y_train) -> RandomForestClassifier:
    """Train a RandomForestClassifier with balanced class weights."""
    print("[*] Training RandomForestClassifier …")
    clf = RandomForestClassifier(**RF_PARAMS)
    clf.fit(X_train, y_train)
    print("    Training complete.")
    return clf


def evaluate(clf, X_test, y_test) -> dict:
    """Compute all evaluation metrics."""
    print("[*] Evaluating model …")
    y_pred = clf.predict(X_test)
    y_proba = clf.predict_proba(X_test)[:, 1]

    metrics = {
        "accuracy": float(accuracy_score(y_test, y_pred)),
        "precision": float(precision_score(y_test, y_pred, zero_division=0)),
        "recall": float(recall_score(y_test, y_pred, zero_division=0)),
        "f1": float(f1_score(y_test, y_pred, zero_division=0)),
        "roc_auc": float(roc_auc_score(y_test, y_proba)),
    }

    cm = confusion_matrix(y_test, y_pred)
    print("\n── Evaluation Metrics ──")
    for k, v in metrics.items():
        print(f"    {k:>12s}: {v:.4f}")
    print(f"\n    Confusion Matrix:\n{cm}\n")

    return metrics


def save_artifacts(clf, feature_names, metrics, dataset_row_count):
    """Persist model pickle and metadata JSON."""
    os.makedirs(ARTIFACTS_DIR, exist_ok=True)

    # Save model
    print(f"[*] Saving model to {MODEL_PATH}")
    with open(MODEL_PATH, "wb") as f:
        pickle.dump(clf, f)

    # Save metadata
    import sklearn

    metadata = {
        "training_date": datetime.datetime.utcnow().isoformat() + "Z",
        "dataset_row_count": dataset_row_count,
        "feature_names": feature_names,
        "metrics": metrics,
        "model_parameters": RF_PARAMS,
        "python_version": sys.version,
        "scikit_learn_version": sklearn.__version__,
    }

    print(f"[*] Saving metadata to {METADATA_PATH}")
    with open(METADATA_PATH, "w") as f:
        json.dump(metadata, f, indent=2)


def log_to_mlflow(clf, metrics, feature_names, dataset_row_count):
    """Log params, metrics, and artifacts to MLflow; register model."""
    print(f"[*] Logging to MLflow at {MLFLOW_TRACKING_URI}")

    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    mlflow.set_experiment(EXPERIMENT_NAME)

    with mlflow.start_run(run_name="rf-fraud-detection") as run:
        # Log parameters
        mlflow.log_params(RF_PARAMS)
        mlflow.log_param("dataset_row_count", dataset_row_count)
        mlflow.log_param("feature_count", len(feature_names))
        mlflow.log_param("test_size", TEST_SIZE)

        # Log metrics
        for k, v in metrics.items():
            mlflow.log_metric(k, v)

        # Log artifacts
        mlflow.log_artifact(MODEL_PATH)
        mlflow.log_artifact(METADATA_PATH)

        # Log and register the sklearn model
        mlflow.sklearn.log_model(
            sk_model=clf,
            artifact_path="model",
            registered_model_name=MODEL_REGISTRY_NAME,
        )

        print(f"    MLflow Run ID: {run.info.run_id}")
        print(f"    Registered model: {MODEL_REGISTRY_NAME}")


# ──────────────────────────── Main ─────────────────────────────────────


def main():
    print("=" * 60)
    print("  SentinelBank — Fraud Detection Training Pipeline")
    print("=" * 60)

    # 1. Load
    df = load_data(DATASET_PATH, SAMPLE_SIZE)

    # 2. Preprocess
    X, y, feature_names = preprocess(df)

    # 3. Split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=TEST_SIZE, random_state=RANDOM_STATE, stratify=y
    )
    print(f"[*] Split: train={len(X_train):,}  test={len(X_test):,}")

    # 4. Train
    clf = train_model(X_train, y_train)

    # 5. Evaluate
    metrics = evaluate(clf, X_test, y_test)

    # 6. Save artifacts
    save_artifacts(clf, feature_names, metrics, dataset_row_count=len(df))

    # 7. Log to MLflow (best-effort; training succeeds even if MLflow is down)
    try:
        log_to_mlflow(clf, metrics, feature_names, dataset_row_count=len(df))
    except Exception as exc:
        print(f"[!] MLflow logging failed (non-fatal): {exc}")
        print("    Model artifacts were saved locally; you can log to MLflow later.")

    print("\n[✓] Pipeline complete.")


if __name__ == "__main__":
    main()
