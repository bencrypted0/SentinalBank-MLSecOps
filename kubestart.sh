#!/usr/bin/env bash
set -euo pipefail

# ──────────────────────────────────────────────────────────────────
# SentinelBank — Kubernetes Bootstrap Script
# Run from the project root (where the k8s/ directory lives).
# ──────────────────────────────────────────────────────────────────

echo "========================================"
echo "  SentinelBank — Kubernetes Bootstrap"
echo "========================================"

# ── 1. Secrets ────────────────────────────────────────────────────
echo ""
echo "[1/6] Applying Secrets..."
kubectl apply -f k8s/secret.yaml

# ── 2. MinIO (object storage) ────────────────────────────────────
echo ""
echo "[2/6] Deploying MinIO..."
kubectl apply -f k8s/minio.yaml
kubectl wait --for=condition=ready pod -l app=minio --timeout=120s
echo "      MinIO is ready."

# ── 3. Create the MLflow bucket in MinIO ─────────────────────────
echo ""
echo "[3/6] Running createbucket Job..."
kubectl delete job createbucket --ignore-not-found
kubectl apply -f k8s/createbucket-job.yaml
kubectl wait --for=condition=complete job/createbucket --timeout=60s
echo "      Bucket created."

# ── 4. MLflow (experiment tracker) ───────────────────────────────
echo ""
echo "[4/6] Deploying MLflow..."
kubectl apply -f k8s/mlflow.yaml
kubectl wait --for=condition=ready pod -l app=mlflow --timeout=120s
echo "      MLflow is ready."

# ── 5. Train the model (MUST complete before App starts) ─────────
echo ""
echo "[5/6] Running trainer Job..."
kubectl delete job train-model --ignore-not-found
kubectl apply -f k8s/trainer.yaml
echo "      Waiting for training to complete (up to 5 min)..."
kubectl wait --for=condition=complete job/train-model --timeout=300s
echo ""
echo "      ── Training Logs ──"
kubectl logs job/train-model
echo "      ────────────────────"

# ── 6. App API (needs the model in MLflow registry) ──────────────
echo ""
echo "[6/6] Deploying App API..."
kubectl apply -f k8s/app.yaml
kubectl wait --for=condition=ready pod -l app=fraud-api --timeout=120s
echo "      App is ready."

# ── Done ─────────────────────────────────────────────────────────
echo ""
echo "========================================"
echo "  ✓ All components deployed!"
echo "========================================"
echo ""
echo "Useful commands:"
echo "  kubectl get pods                         # check pod status"
echo "  kubectl logs -l app=fraud-api            # app logs"
echo "  kubectl port-forward svc/fraud-api 8000:8000   # expose API locally"
echo ""

# If running on Minikube with NodePort, print the access URL
if command -v minikube &> /dev/null; then
  NODE_PORT=$(kubectl get svc fraud-api -o jsonpath='{.spec.ports[0].nodePort}' 2>/dev/null || true)
  if [ -n "$NODE_PORT" ]; then
    MINIKUBE_IP=$(minikube ip 2>/dev/null || true)
    echo "NodePort access: http://${MINIKUBE_IP}:${NODE_PORT}/health"
    echo ""
  fi
fi
