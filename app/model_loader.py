"""
SentinalBank — Secure Model Loader

Loads the trained scikit-learn model with two security layers:
  1. SHA-256 hash verification — ensures the model file hasn't been tampered with
  2. RestrictedUnpickler — whitelists only the sklearn/numpy classes needed,
     blocking arbitrary code execution even if a malicious pickle is loaded.

Supports loading either from:
  1. MLflow Model Registry (Production): fetches from MinIO (S3) via MLflow,
     verifies against the run's 'model_sha256' tag, and deserializes securely.
  2. Local File (Fallback/Dev): verifies local file against .sha256 sidecar.
"""

import os
import pickle
import hashlib
import json

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


def _compute_hash(file_path: str) -> str:
    """Compute the SHA-256 hash of a file."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def _verify_hash(model_path: str, expected_hash: str) -> None:
    """Verify file integrity by comparing its hash to the expected hash."""
    actual_hash = _compute_hash(model_path)
    if actual_hash != expected_hash:
        raise RuntimeError(
            f"Model integrity check FAILED for '{model_path}'.\n"
            f"  Expected SHA-256: {expected_hash}\n"
            f"  Actual SHA-256:   {actual_hash}\n"
            "The model file may have been tampered with. Refusing to load."
        )
    print(f"[✓] Model integrity verified (SHA-256: {actual_hash[:16]}…)")


def load_model(model_path: str | None = None) -> tuple:
    """
    Load the fraud-detection model and its metadata with security verification.

    If MODEL_NAME environment variable is set, loads from the MLflow model registry.
    Otherwise, falls back to loading from a local file path.

    Args:
        model_path: Path to the local pickle file. Falls back to MODEL_PATH env var.

    Returns:
        tuple: (model_object, metadata_dict)
    """
    model_name = os.getenv("MODEL_NAME")

    if model_name:
        print(f"[*] Loading model '{model_name}' from MLflow Model Registry...")
        import mlflow
        from mlflow.tracking import MlflowClient

        # Configure client and fetch latest model version
        tracking_uri = os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000")
        mlflow.set_tracking_uri(tracking_uri)
        client = MlflowClient()

        try:
            # Get latest version (stages include "None", "Staging", "Production")
            versions = client.get_latest_versions(model_name, stages=["None", "Staging", "Production"])
            if not versions:
                raise RuntimeError(f"No versions found for registered model '{model_name}'")
            latest_version = versions[0]
            run_id = latest_version.run_id
            model_version = latest_version.version
            print(f"    Found model version {model_version} (Run ID: {run_id})")

            # Retrieve integrity hash from run tags (stored in DB — separate trust boundary)
            run = client.get_run(run_id)
            expected_hash = run.data.tags.get("model_sha256")
            if not expected_hash:
                raise RuntimeError(
                    f"Model run {run_id} does not have a 'model_sha256' tag. "
                    "Cannot verify model integrity."
                )

            # Download model.pkl artifact (from MinIO via MLflow)
            local_dir = mlflow.artifacts.download_artifacts(artifact_uri=f"models:/{model_name}/{model_version}")
            downloaded_model_path = os.path.join(local_dir, "model.pkl")

            if not os.path.isfile(downloaded_model_path):
                raise FileNotFoundError(f"model.pkl not found in downloaded artifacts directory: {local_dir}")

            # Verify integrity
            _verify_hash(downloaded_model_path, expected_hash)

            # Unpickle securely
            with open(downloaded_model_path, "rb") as f:
                model = RestrictedUnpickler(f).load()

            # Attempt to download and parse metadata
            metadata = {"error": "No metadata found"}
            try:
                metadata_path = mlflow.artifacts.download_artifacts(run_id=run_id, artifact_path="model_metadata.json")
                with open(metadata_path, "r") as f:
                    metadata = json.load(f)
            except Exception as e:
                print(f"[!] Warning: Could not retrieve model metadata: {e}")

            print(f"[✓] Successfully loaded model version {model_version} from MLflow/MinIO")
            return model, metadata

        except Exception as exc:
            raise RuntimeError(f"Failed to load model from MLflow registry: {exc}") from exc

    else:
        # Fallback to local file loading
        if model_path is None:
            model_path = os.getenv("MODEL_PATH", "../model_training/artifacts/model.pkl")

        abs_path = os.path.abspath(model_path)
        print(f"[*] Loading model from local path '{abs_path}'...")

        if not os.path.isfile(abs_path):
            raise FileNotFoundError(
                f"Model file not found at '{abs_path}'. "
                "Train the model first or set the MODEL_PATH/MODEL_NAME environment variables."
            )

        # Retrieve local expected hash
        hash_path = abs_path + ".sha256"
        if not os.path.isfile(hash_path):
            raise FileNotFoundError(
                f"Model hash file not found at '{hash_path}'. "
                "Cannot verify model integrity without a sidecar hash file."
            )
        with open(hash_path, "r") as f:
            expected_hash = f.read().strip()

        # Verify integrity
        _verify_hash(abs_path, expected_hash)

        # Unpickle securely
        try:
            with open(abs_path, "rb") as f:
                model = RestrictedUnpickler(f).load()
        except pickle.UnpicklingError:
            raise
        except Exception as exc:
            raise RuntimeError(f"Failed to deserialize model from '{abs_path}': {exc}") from exc

        # Load metadata
        metadata_path = os.path.join(os.path.dirname(abs_path), "model_metadata.json")
        metadata = {"error": "model_metadata.json not found"}
        if os.path.isfile(metadata_path):
            try:
                with open(metadata_path, "r") as f:
                    metadata = json.load(f)
            except Exception as e:
                print(f"[!] Warning: Could not load local metadata file: {e}")

        print(f"[✓] Model loaded from {abs_path}")
        return model, metadata
