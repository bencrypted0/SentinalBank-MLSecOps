#!/usr/bin/env bash
set -euo pipefail

echo "========================================"
echo "  SentinalBank — Kubernetes Setup"
echo "========================================"

# => 1. Detect Host/Prod EC2 Private IP
echo ""
echo "Detecting host/Prod EC2 Private IP..."
# Tryng AWS IMDSv2, fallback to hostname -I, fallback to standard docker gateway
PROD_IP=$(hostname -I | awk '{print $1}' || echo "172.17.0.1")
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

# => 4. Deploy App API and Ingress (configured to point to Prod EC2 Private IP)
echo ""
echo "[3/4] Deploying App API (substituting host IP) and Ingress..."
sed "s/PROD_EC2_PRIVATE_IP/$PROD_IP/g" k8s/app.yaml | kubectl apply -f -
kubectl apply -f k8s/ingress.yaml
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

# If running on Minikube, print Ingress info
if command -v minikube &> /dev/null; then
  MINIKUBE_IP=$(minikube ip 2>/dev/null || true)
  if [ -n "$MINIKUBE_IP" ]; then
    echo "Minikube Ingress configured."
    echo "Access URL: http://${MINIKUBE_IP}/health"
    echo "  (Note: Ensure 'minikube addons enable ingress' is run to activate the ingress controller)"
    echo ""
  fi
fi

