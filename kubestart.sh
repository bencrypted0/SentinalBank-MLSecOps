#!/usr/bin/env bash
set -euo pipefail

# ==================================================================
# SentinalBank — Kubernetes Bootup and pod setup script
# Run from the project root (where the k8s/ directory lives).
# ==================================================================

echo "========================================"
echo "  SentinalBank — Kubernetes Setup"
echo "========================================"

# => 1. Detect Host/Prod EC2 Private IP
echo ""
echo "Detecting host/Prod EC2 Private IP..."
# Tryng AWS IMDSv2, fallback to hostname -I, fallback to standard docker gateway
PROD_IP=$(curl -s --timeout 2 http://169.254.169.254/latest/meta-data/local-ipv4 || hostname -I | awk '{print $1}' || echo "172.17.0.1")
echo "Using Private IP: $PROD_IP"

# => 2. RBAC & NetworkPolicy
echo ""
echo "[1/4] Applying RBAC & NetworkPolicy..."
kubectl apply -f k8s/rbac.yaml
kubectl apply -f k8s/networkpolicy.yaml
echo "ServiceAccount and NetworkPolicies applied."

# => 3. Secrets
echo ""
echo "[2/4] Applying Secrets..."
kubectl apply -f k8s/secret.yaml

# => 4. Deploy App API (configured to point to Prod EC2 Private IP)
echo ""
echo "[3/4] Deploying App API (substituting host IP)..."
sed "s/PROD_EC2_PRIVATE_IP/$PROD_IP/g" k8s/app.yaml | kubectl apply -f -
kubectl wait --for=condition=ready pod -l app=fraud-api --timeout=120s
echo "App is ready."

# => 5. Verify NetworkPolicies are active
echo ""
echo "[4/4] Verifying NetworkPolicies..."
kubectl get networkpolicy
echo "All policies active."

# Done Deploying
echo ""
echo "  ✓ App deployed to Kubernetes!"
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

