"""
SentinelBank — Model Loader

Loads the trained scikit-learn model from a pickle file.

# VULNERABILITY: Pickle deserialization without any integrity or signature check.
# A tampered pickle file can execute arbitrary code on load.
"""

import os
import pickle  # VULNERABILITY: using pickle without integrity verification


def load_model(model_path: str | None = None):
    """
    Load the fraud-detection model from disk.

    # VULNERABILITY: No hash/checksum verification of the pickle file.
    # An attacker who can replace model.pkl can achieve remote code execution.

    Args:
        model_path: Path to the pickle file.  Falls back to MODEL_PATH env var
                     or a default relative path.

    Returns:
        The deserialized scikit-learn model object.

    Raises:
        FileNotFoundError: If the model file does not exist.
        RuntimeError: If deserialization fails.
    """
    if model_path is None:
        model_path = os.getenv("MODEL_PATH", "../model_training/artifacts/model.pkl")

    abs_path = os.path.abspath(model_path)

    if not os.path.isfile(abs_path):
        raise FileNotFoundError(
            f"Model file not found at '{abs_path}'. "
            "Train the model first or set the MODEL_PATH environment variable."
        )

    try:
        # VULNERABILITY: pickle.load on untrusted file — no checksum, no signature
        with open(abs_path, "rb") as f:
            model = pickle.load(f)
    except Exception as exc:
        raise RuntimeError(f"Failed to deserialize model from '{abs_path}': {exc}") from exc

    print(f"[✓] Model loaded from {abs_path}")
    return model
