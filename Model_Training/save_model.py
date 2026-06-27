"""
SentinalBank — CI-Only Model Serialisation
Trains the same fraud-detection model as train.py but saves the pickle
to a workspace-relative path for ModelScan instead of logging to MLflow.

Usage (CI):
    WORKSPACE=/app python Model_Training/save_model.py

Usage (local dev):
    python Model_Training/save_model.py
    # → writes ./artifacts/modelscan/model.pkl
"""

import os
import sys
import pickle

# ── Make the Model_Training package importable when invoked from project root ──
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from train import (                # noqa: E402  — path hack above is intentional
    load_data,
    preprocess,
    train_model,
    evaluate,
    DATASET_PATH,
    SAMPLE_SIZE,
    TEST_SIZE,
    RANDOM_STATE,
)
from sklearn.model_selection import train_test_split


def resolve_output_path() -> str:
    """
    Return the absolute path where the CI model artifact should be saved.

    * If $WORKSPACE is set (Jenkins) → ${WORKSPACE}/artifacts/modelscan/model.pkl
    * Otherwise (local dev)          → ./artifacts/modelscan/model.pkl
    """
    workspace = os.environ.get("WORKSPACE", ".")
    return os.path.join(workspace, "artifacts", "modelscan", "model.pkl")


def main():
    print("  SentinalBank — CI Model Build (for ModelScan)")

    # 1. Load
    df = load_data(DATASET_PATH, SAMPLE_SIZE)

    # 2. Preprocess
    X, y, feature_names = preprocess(df)

    # 3. Split  (identical to train.py)
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=TEST_SIZE, random_state=RANDOM_STATE, stratify=y
    )

    # 4. Train
    clf = train_model(X_train, y_train)

    # 5. Evaluate  (keeps parity with production — also acts as a sanity check)
    evaluate(clf, X_test, y_test)

    # 6. Save model to workspace-relative path
    output_path = resolve_output_path()
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    print(f"[*] Saving CI model artifact to {output_path}")
    with open(output_path, "wb") as f:
        pickle.dump(clf, f)

    print(f"[✓] Model artifact written ({os.path.getsize(output_path):,} bytes)")
    print("[✓] CI model build complete.")


if __name__ == "__main__":
    main()
