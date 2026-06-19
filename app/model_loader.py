"""
SentinelBank — Secure Model Loader

Loads the trained scikit-learn model with two security layers:
  1. SHA-256 hash verification — ensures the model file hasn't been tampered with
  2. RestrictedUnpickler — whitelists only the sklearn/numpy classes needed,
     blocking arbitrary code execution even if a malicious pickle is loaded.

Mitigates:
  - CWE-502: Deserialization of Untrusted Data
  - CWE-354: Improper Validation of Integrity Check Value
  - Bandit B301: pickle.load on untrusted file
"""

import os
import pickle
import hashlib

import numpy


# ── RestrictedUnpickler — Class Whitelist ──────────────────────────────

# Only these classes are allowed during deserialization.
# Discovered by scanning the actual model.pkl with ClassDiscoverer.
# A RandomForestClassifier pickle contains sklearn tree internals and numpy arrays.
# If you change the model type (e.g., to XGBoost), update this whitelist.
ALLOWED_CLASSES = {
    # sklearn — RandomForest and its internal tree structures
    ("sklearn.ensemble._forest", "RandomForestClassifier"),
    ("sklearn.tree._classes", "DecisionTreeClassifier"),
    ("sklearn.tree._tree", "Tree"),
    # numpy — arrays, dtypes, scalars, and reconstruction helpers
    ("numpy", "ndarray"),
    ("numpy", "dtype"),
    ("numpy.core.multiarray", "_reconstruct"),
    ("numpy.core.multiarray", "scalar"),
}


class RestrictedUnpickler(pickle.Unpickler):
    """
    A pickle unpickler that only allows whitelisted classes.

    Any class not in ALLOWED_CLASSES will raise an UnpicklingError,
    preventing arbitrary code execution via malicious pickle payloads.
    """

    def find_class(self, module: str, name: str):
        if (module, name) not in ALLOWED_CLASSES:
            raise pickle.UnpicklingError(
                f"Blocked unauthorized class: {module}.{name} — "
                f"not in the allowed model class whitelist. "
                f"This may indicate a tampered or malicious model file."
            )
        return super().find_class(module, name)


# ── SHA-256 Hash Verification ─────────────────────────────────────────


def _verify_hash(model_path: str) -> None:
    """
    Verify the SHA-256 hash of the model file against the expected hash.

    The expected hash is read from a .sha256 sidecar file generated at
    training time. This ensures the model file has not been modified
    since it was produced by the trusted training pipeline.

    Raises:
        FileNotFoundError: If the .sha256 hash file is missing (fail closed).
        RuntimeError: If the hash does not match (file was tampered with).
    """
    hash_path = model_path + ".sha256"

    if not os.path.isfile(hash_path):
        raise FileNotFoundError(
            f"Model hash file not found at '{hash_path}'. "
            "Cannot verify model integrity without a hash file. "
            "Re-run training to generate it, or check the deployment."
        )

    # Read expected hash
    with open(hash_path, "r") as f:
        expected_hash = f.read().strip()

    # Compute actual hash
    sha256 = hashlib.sha256()
    with open(model_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    actual_hash = sha256.hexdigest()

    if actual_hash != expected_hash:
        raise RuntimeError(
            f"Model integrity check FAILED for '{model_path}'.\n"
            f"  Expected SHA-256: {expected_hash}\n"
            f"  Actual SHA-256:   {actual_hash}\n"
            "The model file may have been tampered with. Refusing to load."
        )

    print(f"[✓] Model integrity verified (SHA-256: {actual_hash[:16]}…)")


# ── Model Loading ─────────────────────────────────────────────────────


def load_model(model_path: str | None = None):
    """
    Load the fraud-detection model from disk with security verification.

    Security layers applied:
      1. SHA-256 hash check — verifies file integrity against training-time hash
      2. RestrictedUnpickler — blocks any class not in the whitelist

    Args:
        model_path: Path to the pickle file. Falls back to MODEL_PATH env var
                     or a default relative path.

    Returns:
        The deserialized scikit-learn model object.

    Raises:
        FileNotFoundError: If the model file or hash file does not exist.
        RuntimeError: If hash verification fails or deserialization fails.
        pickle.UnpicklingError: If a blocked class is encountered.
    """
    if model_path is None:
        model_path = os.getenv("MODEL_PATH", "../model_training/artifacts/model.pkl")

    abs_path = os.path.abspath(model_path)

    if not os.path.isfile(abs_path):
        raise FileNotFoundError(
            f"Model file not found at '{abs_path}'. "
            "Train the model first or set the MODEL_PATH environment variable."
        )

    # Layer 1: Verify file integrity
    _verify_hash(abs_path)

    # Layer 2: Load with class whitelist restriction
    try:
        with open(abs_path, "rb") as f:
            model = RestrictedUnpickler(f).load()
    except pickle.UnpicklingError:
        raise  # Re-raise whitelist violations as-is
    except Exception as exc:
        raise RuntimeError(
            f"Failed to deserialize model from '{abs_path}': {exc}"
        ) from exc

    print(f"[✓] Model loaded from {abs_path}")
    return model
