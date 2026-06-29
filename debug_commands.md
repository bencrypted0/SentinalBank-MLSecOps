# SentinalBank — Debug Commands Reference

← Back to **[README.md](README.md)** · **[INSTRUCTIONS.md](INSTRUCTIONS.md)**

A quick-reference guide for diagnosing issues at every layer of the SentinalBank stack. Start from the section that matches where you're stuck.

---

## Table of Contents

1. [SSH & EC2 Connectivity](#1-ssh--ec2-connectivity)
2. [Terraform](#2-terraform)
3. [Docker & Docker Compose](#3-docker--docker-compose)
4. [MinIO (Object Storage)](#4-minio-object-storage)
5. [MLflow (Tracking Server)](#5-mlflow-tracking-server)
6. [Kubernetes — Cluster & Node](#6-kubernetes--cluster--node)
7. [Kubernetes — Pods & Deployments](#7-kubernetes--pods--deployments)
8. [Kubernetes — Networking & Ingress](#8-kubernetes--networking--ingress)
9. [Kubernetes — Secrets & RBAC](#9-kubernetes--secrets--rbac)
10. [Jenkins — Server & Agent](#10-jenkins--server--agent)
11. [Jenkins — Pipeline Debugging](#11-jenkins--pipeline-debugging)
12. [FastAPI Application](#12-fastapi-application)
13. [Model Training & MLflow Integration](#13-model-training--mlflow-integration)
14. [Common Failure Patterns](#14-common-failure-patterns)

---

## 1. SSH & EC2 Connectivity

### Can't SSH into an instance

```bash
# Basic SSH (replace IP with the actual public IP from terraform output)
ssh -i sentinalbank-deployer-key.pem ubuntu@<PUBLIC_IP>

# Verbose mode — shows exactly where the handshake fails
ssh -vvv -i sentinalbank-deployer-key.pem ubuntu@<PUBLIC_IP>

# Check key file permissions (Linux/macOS only — must be 600)
ls -la sentinalbank-deployer-key.pem
chmod 600 sentinalbank-deployer-key.pem
```

### Common SSH issues

| Symptom | Likely Cause | Fix |
|---|---|---|
| `Permission denied (publickey)` | Wrong key file or wrong username | Confirm you're using `ubuntu@` (not `ec2-user@`) and the correct `.pem` file |
| `Connection timed out` | Security group doesn't allow port 22, or instance is stopped | Check AWS console → Security Groups → Inbound rules for port 22 |
| `Host key verification failed` | IP changed after instance restart | Remove the old entry: `ssh-keygen -R <IP>` |
| `WARNING: UNPROTECTED PRIVATE KEY FILE` | Key file permissions too open (Linux/macOS) | `chmod 600 sentinalbank-deployer-key.pem` |

### Verify instance is running

```bash
# From your local machine (requires AWS CLI configured)
aws ec2 describe-instance-status --region ap-south-2

# Quick check — just get public IPs
cd terraform
terraform output
```

---

## 2. Terraform

### State & plan inspection

```bash
cd terraform

# View current state (what Terraform thinks exists)
terraform show

# List all resources in state
terraform state list

# Inspect a specific resource
terraform state show aws_instance.jenkins_server
terraform state show aws_instance.prod_server

# Re-read current infrastructure state from AWS
terraform refresh

# Preview what would change on next apply
terraform plan
```

### Outputs (get IPs)

```bash
terraform output
terraform output jenkins_server_public_ip
terraform output prod_server_public_ip
terraform output jenkins_agent_public_ip
```

### Recovering from a bad state

```bash
# Force re-create a specific resource
terraform taint aws_instance.prod_server
terraform apply

# Remove a resource from state (doesn't destroy it in AWS)
terraform state rm aws_instance.jenkins_agent

# Import an existing AWS resource into state
terraform import aws_instance.jenkins_agent <INSTANCE_ID>
```

### Common Terraform errors

| Error | Fix |
|---|---|
| `PendingVerification` on `RunInstances` | New AWS account/region — wait up to 4 hours, then re-run `apply` |
| `InvalidKeyPair.NotFound` | The TLS key pair hasn't been created yet — run `apply` again (Terraform creates it) |
| `Error acquiring state lock` | Previous `apply` crashed — run `terraform force-unlock <LOCK_ID>` |
| `docker: invalid reference format` (Docker-based Terraform on Windows) | Use `${PWD}` instead of `$(pwd)` in PowerShell |

---

## 3. Docker & Docker Compose

### Container status

```bash
# List running containers
docker ps

# List ALL containers (including stopped/exited)
docker ps -a

# Check why a container exited
docker logs <CONTAINER_NAME_OR_ID>

# Follow logs in real-time
docker logs -f <CONTAINER_NAME_OR_ID>

# Show last 50 lines
docker logs --tail 50 <CONTAINER_NAME_OR_ID>
```

### Container inspection

```bash
# Full container details (env vars, mounts, network, etc.)
docker inspect <CONTAINER_NAME_OR_ID>

# Just the environment variables
docker inspect --format='{{range .Config.Env}}{{println .}}{{end}}' <CONTAINER_NAME_OR_ID>

# Just the network settings
docker inspect --format='{{json .NetworkSettings.Networks}}' <CONTAINER_NAME_OR_ID>

# Get the container's IP address
docker inspect --format='{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' <CONTAINER_NAME_OR_ID>
```

### Shell into a running container

```bash
# Bash shell
docker exec -it <CONTAINER_NAME_OR_ID> bash

# If bash isn't available (minimal images)
docker exec -it <CONTAINER_NAME_OR_ID> sh

# Run a one-off command
docker exec <CONTAINER_NAME_OR_ID> env
docker exec <CONTAINER_NAME_OR_ID> cat /etc/os-release
```

### Docker Compose (on Prod Server)

```bash
cd /home/ubuntu   # or wherever docker-compose.yml lives

# Status of all services
docker compose ps

# Logs for all services
docker compose logs

# Logs for a specific service
docker compose logs mlflow
docker compose logs minio

# Follow logs
docker compose logs -f mlflow

# Restart a single service
docker compose restart mlflow

# Tear down and rebuild everything
docker compose down
docker compose up -d

# Rebuild images and restart
docker compose up -d --build
```

### Disk & image cleanup

```bash
# Check disk usage
docker system df

# Remove all stopped containers, unused networks, dangling images
docker system prune

# Nuclear option — remove everything unused (images, volumes, etc.)
docker system prune -a --volumes
```

---

## 4. MinIO (Object Storage)

### Health check

```bash
# From the prod server (or any machine that can reach it)
curl -f http://localhost:9000/minio/health/live
# Expected: 200 OK

# Check the MinIO console is responding
curl -f http://localhost:9001
```

### Verify the mlflow bucket exists

```bash
# Using the MinIO client (mc) from a temporary container
docker run --rm --network host \
  minio/mc \
  alias set local http://localhost:9000 minioadmin minioadmin

docker run --rm --network host \
  minio/mc \
  ls local/

docker run --rm --network host \
  minio/mc \
  ls local/mlflow/
```

### MinIO container logs

```bash
docker logs $(docker ps -qf "ancestor=minio/minio")
```

### Common MinIO issues

| Symptom | Cause | Fix |
|---|---|---|
| `Connection refused` on port 9000 | MinIO container isn't running | `docker compose up -d minio` |
| `Access Denied` | Wrong credentials | Check `MINIO_ROOT_USER` / `MINIO_ROOT_PASSWORD` in your `.env` or `secrets.env` |
| `Bucket not found: mlflow` | `createbucket` service didn't run | `docker compose up createbucket` |

---

## 5. MLflow (Tracking Server)

### Health check

```bash
curl http://localhost:5000/health
# Expected: {"status": "OK"}

# Or the full UI
curl -s http://localhost:5000 | head -20
```

### MLflow container logs

```bash
docker logs $(docker ps -qf "ancestor=ghcr.io/mlflow/mlflow")
```

### Check MLflow can reach MinIO

```bash
# Shell into the MLflow container and test S3 connectivity
docker exec -it $(docker ps -qf "ancestor=ghcr.io/mlflow/mlflow") bash

# Inside the container:
python -c "
import boto3, os
s3 = boto3.client('s3',
    endpoint_url=os.getenv('MLFLOW_S3_ENDPOINT_URL'),
    aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
    aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'))
print(s3.list_buckets()['Buckets'])
"
```

### Common MLflow issues

| Symptom | Cause | Fix |
|---|---|---|
| `Connection refused` on port 5000 | MLflow container crashed or not started | Check logs: `docker logs <mlflow-container>` |
| `Unable to connect to S3 endpoint` | MinIO isn't running or wrong `MLFLOW_S3_ENDPOINT_URL` | Ensure MinIO is healthy first; check env vars |
| MLflow UI loads but shows no experiments | Training hasn't run, or different tracking URI | Confirm `MLFLOW_TRACKING_URI` matches |

---

## 6. Kubernetes — Cluster & Node

### minikube status

```bash
# Is minikube running?
minikube status

# Cluster info
kubectl cluster-info

# Node details
kubectl get nodes
kubectl describe node minikube
```

### minikube won't start

```bash
# Check Docker is running (minikube uses Docker driver)
docker ps

# Delete and restart minikube from scratch
minikube delete
minikube start --driver=docker

# Check minikube logs
minikube logs
minikube logs --file=minikube-logs.txt
```

### Enable required addons

```bash
# Ingress controller (required for ingress.yaml)
minikube addons enable ingress

# Verify ingress controller is running
kubectl get pods -n ingress-nginx

# List all addons and their status
minikube addons list
```

---

## 7. Kubernetes — Pods & Deployments

### Pod status overview

```bash
# All pods in default namespace
kubectl get pods

# With more details (node, IP, restarts)
kubectl get pods -o wide

# All namespaces
kubectl get pods -A

# Watch pods in real-time
kubectl get pods -w
```

### Diagnosing a failing pod

```bash
# Step 1: Check pod status and restart count
kubectl get pods

# Step 2: Describe the pod (events, conditions, container state)
kubectl describe pod <POD_NAME>

# Step 3: Check container logs
kubectl logs <POD_NAME>

# If the pod has restarted, check PREVIOUS container's logs
kubectl logs <POD_NAME> --previous

# Step 4: If multi-container pod, specify the container
kubectl logs <POD_NAME> -c app
```

### Common pod states and what they mean

| Status | Meaning | Debug Action |
|---|---|---|
| `Pending` | Pod can't be scheduled (resource limits, node selector, etc.) | `kubectl describe pod <NAME>` → check Events |
| `ContainerCreating` | Image pull in progress or volume mount issue | `kubectl describe pod <NAME>` → check Events for pull errors |
| `ImagePullBackOff` | Can't pull the Docker image (wrong name, no auth, doesn't exist) | Verify image name: `kubectl describe pod <NAME>` → check `Image:` field |
| `CrashLoopBackOff` | Container starts and immediately crashes, repeatedly | `kubectl logs <NAME> --previous` → check the error output |
| `Running` but unhealthy | App is up but failing readiness/liveness probes | `kubectl describe pod <NAME>` → check probe config and endpoints |
| `OOMKilled` | Container exceeded memory limit | Increase `resources.limits.memory` in `app.yaml` |
| `Error` | Container exited with non-zero code | `kubectl logs <NAME>` |

### Deployment status

```bash
# Check deployment status
kubectl get deployment app
kubectl describe deployment app

# Check rollout status
kubectl rollout status deployment/app

# Check rollout history
kubectl rollout history deployment/app

# Undo last rollout (rollback)
kubectl rollout undo deployment/app

# Scale up/down
kubectl scale deployment app --replicas=3
```

### Shell into a running pod

```bash
# Interactive shell
kubectl exec -it <POD_NAME> -- bash

# If bash isn't available
kubectl exec -it <POD_NAME> -- sh

# Run a single command
kubectl exec <POD_NAME> -- env
kubectl exec <POD_NAME> -- cat /app/requirements.txt

# Check what the pod can resolve via DNS
kubectl exec <POD_NAME> -- nslookup mlflow
kubectl exec <POD_NAME> -- nslookup minio
```

### Check pod environment variables

```bash
# Verify env vars are injected correctly (especially MLflow/MinIO URLs)
kubectl exec <POD_NAME> -- env | grep -E "MLFLOW|MINIO|AWS"
```

> **Critical**: The pod's `MLFLOW_TRACKING_URI` and `MLFLOW_S3_ENDPOINT_URL` must point to the **prod server's private IP** (e.g., `http://10.0.1.30:5000`), NOT `localhost` — pods have their own network namespace.

---

## 8. Kubernetes — Networking & Ingress

### Service connectivity

```bash
# List services
kubectl get svc

# Describe the fraud-api service
kubectl describe svc fraud-api

# Test service from inside the cluster
kubectl run debug --rm -it --image=curlimages/curl -- \
  curl -s http://fraud-api:8000/health
```

### Ingress debugging

```bash
# Check ingress resource
kubectl get ingress
kubectl describe ingress fraud-api-ingress

# Check ingress controller pods
kubectl get pods -n ingress-nginx

# Check ingress controller logs
kubectl logs -n ingress-nginx -l app.kubernetes.io/name=ingress-nginx

# Get minikube IP (for accessing the ingress externally)
minikube ip

# Test the ingress endpoint
curl http://$(minikube ip)/health
```

### NetworkPolicy debugging

```bash
# List all network policies
kubectl get networkpolicy

# Describe a specific policy
kubectl describe networkpolicy default-deny-ingress
kubectl describe networkpolicy allow-app-ingress

# Test connectivity between pods (if traffic is blocked)
# Temporarily delete the default-deny to test:
kubectl delete networkpolicy default-deny-ingress
# Test, then re-apply:
kubectl apply -f k8s/networkpolicy.yaml
```

### DNS resolution inside the cluster

```bash
# Test DNS from a debug pod
kubectl run dns-test --rm -it --image=busybox -- nslookup fraud-api
kubectl run dns-test --rm -it --image=busybox -- nslookup kubernetes

# Check CoreDNS pods
kubectl get pods -n kube-system -l k8s-app=kube-dns
kubectl logs -n kube-system -l k8s-app=kube-dns
```

### Can pods reach MinIO/MLflow on the host?

```bash
# From inside a pod, test connectivity to host services
kubectl exec <POD_NAME> -- curl -s http://<PROD_PRIVATE_IP>:5000/health
kubectl exec <POD_NAME> -- curl -s http://<PROD_PRIVATE_IP>:9000/minio/health/live

# If these fail, check:
# 1. The correct private IP is being used (not localhost)
# 2. Docker Compose services are actually running on the host
# 3. Security group allows traffic on ports 5000/9000
```

---

## 9. Kubernetes — Secrets & RBAC

### Secrets

```bash
# List secrets
kubectl get secrets

# View secret details (base64 encoded)
kubectl get secret minio-creds -o yaml

# Decode a specific key from a secret
kubectl get secret minio-creds -o jsonpath='{.data.MINIO_ROOT_USER}' | base64 -d

# Verify secrets match what Docker Compose is using
# Compare with the host's secrets.env:
cat /home/ubuntu/secrets.env
```

### RBAC

```bash
# List service accounts
kubectl get serviceaccount

# Describe the app's service account
kubectl describe serviceaccount sa-app

# Check if a service account can perform an action
kubectl auth can-i get pods --as=system:serviceaccount:default:sa-app
```

---

## 10. Jenkins — Server & Agent

### Jenkins server container

```bash
# SSH into Jenkins Server EC2
ssh -i sentinalbank-deployer-key.pem ubuntu@<JENKINS_SERVER_PUBLIC_IP>

# Check Jenkins container is running
docker ps

# Jenkins logs
docker logs jenkins-server

# Follow Jenkins logs
docker logs -f jenkins-server

# Get initial admin password (first-time setup)
docker exec jenkins-server cat /var/jenkins_home/secrets/initialAdminPassword
```

### Jenkins agent connectivity

```bash
# From the Jenkins Server, test SSH to the agent
ssh -i /home/ubuntu/.ssh/jenkins_agent_key ubuntu@<JENKINS_AGENT_PUBLIC_IP> "echo connected"

# If that fails, check on the agent:
ssh -i sentinalbank-deployer-key.pem ubuntu@<JENKINS_AGENT_PUBLIC_IP>
cat ~/.ssh/authorized_keys       # Does it contain the Jenkins server's public key?
ls -la ~/.ssh/                   # Permissions: .ssh=700, authorized_keys=600
```

### Agent shows offline in Jenkins UI

1. Go to **Manage Jenkins → Nodes → ec2-agent → Log**
2. Common causes:

| Symptom in log | Fix |
|---|---|
| `Connection refused` | Agent's security group doesn't allow SSH from Jenkins server, or sshd isn't running |
| `Auth fail` | Public key not in agent's `~/.ssh/authorized_keys`, or wrong username |
| `No such file: /home/ubuntu/jenkins-agent` | Create the directory: `mkdir -p ~/jenkins-agent` on the agent |
| `java: command not found` | Install Java on the agent: `sudo apt-get install -y openjdk-17-jdk` |

### Jenkins can't reach Docker Hub

```bash
# On the agent, test Docker Hub connectivity
docker pull hello-world
docker login -u <DOCKER_USER>

# If "permission denied" for docker commands:
groups   # Does it show "docker"?
sudo usermod -aG docker $USER
# Log out and back in
```

---

## 11. Jenkins — Pipeline Debugging

### Pipeline won't parse

```bash
# Error: "Invalid agent type 'docker'"
# → Install the Docker Pipeline plugin (docker-workflow)
# Manage Jenkins → Plugins → Available → search "Docker Pipeline" → Install

# Error: "No such DSL method 'sshagent'"
# → Install the SSH Agent plugin
```

### Stage-specific debugging

#### Gitleaks stage fails

```bash
# Run Gitleaks manually on the agent
docker run --rm -v "$(pwd)":/repo \
  ghcr.io/gitleaks/gitleaks:latest \
  detect --source /repo --report-format json --verbose
```

#### Trivy stage fails

```bash
# Run Trivy scan manually against the image
docker run --rm \
  -v /var/run/docker.sock:/var/run/docker.sock \
  aquasec/trivy:latest image <IMAGE_NAME>

# Check which CVEs are being flagged
docker run --rm \
  -v /var/run/docker.sock:/var/run/docker.sock \
  aquasec/trivy:latest image --severity CRITICAL <IMAGE_NAME>

# With the .trivyignore file
docker run --rm \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v "$(pwd)/.trivyignore":/root/.trivyignore \
  aquasec/trivy:latest image --severity CRITICAL --show-suppressed <IMAGE_NAME>
```

#### Checkov stage fails

```bash
# Scan K8s manifests manually
docker run --rm -v $(pwd):/work -w /work \
  bridgecrew/checkov:latest \
  --directory /work/k8s --framework kubernetes --quiet

# Scan Terraform
docker run --rm -v $(pwd):/work -w /work \
  bridgecrew/checkov:latest \
  --directory /work/terraform --framework terraform --quiet

# Scan Dockerfile
docker run --rm -v $(pwd):/work -w /work \
  bridgecrew/checkov:latest \
  --file /work/app/Dockerfile --framework dockerfile --quiet
```

#### Cosign sign/verify fails

```bash
# Verify image exists and has a digest
docker inspect --format='{{index .RepoDigests 0}}' <IMAGE_NAME>

# Sign manually (for testing)
docker run --rm \
  -e COSIGN_PASSWORD=<PASSWORD> \
  -v /path/to/cosign.key:/tmp/cosign.key \
  gcr.io/projectsigstore/cosign:latest \
  sign --key /tmp/cosign.key --yes \
  --tlog-upload=false \
  --registry-username <USER> --registry-password <PASS> \
  <IMAGE_DIGEST>

# Verify manually
docker run --rm \
  -v /path/to/cosign.pub:/tmp/cosign.pub \
  gcr.io/projectsigstore/cosign:latest \
  verify --key /tmp/cosign.pub \
  --insecure-ignore-tlog=true \
  --registry-username <USER> --registry-password <PASS> \
  <IMAGE_DIGEST>
```

#### Deploy stage fails

```bash
# Test SSH from agent to prod server (using the same key Jenkins would use)
ssh -o StrictHostKeyChecking=no -i <KEY> ubuntu@10.0.1.30 "kubectl get pods"

# Manually run the deploy command
ssh ubuntu@10.0.1.30 \
  "kubectl set image deployment/app app=<NEW_IMAGE_DIGEST> && \
   kubectl rollout status deployment/app --timeout=120s"

# If rollout times out, rollback
ssh ubuntu@10.0.1.30 "kubectl rollout undo deployment/app"
```

### Checking archived scan reports

All scan reports are archived as Jenkins artifacts. Find them at:
```
http://<JENKINS_IP>:8080/job/<JOB_NAME>/<BUILD_NUMBER>/artifact/reports/
```

Reports generated per build:
- `gitleaks-report.json`
- `pip-audit-app.json` / `pip-audit-training.json`
- `bandit-report.json`
- `sbom-app.json`
- `trivy-app-report.json`
- `checkov-k8s-report.json` / `checkov-dockerfile-report.json` / `checkov-terraform-report.json`
- `modelscan-report.json`

---

## 12. FastAPI Application

### Health check

```bash
# Local
curl http://localhost:8000/health

# Via minikube ingress
curl http://$(minikube ip)/health

# Via NodePort (if configured)
kubectl port-forward svc/fraud-api 8000:8000 &
curl http://localhost:8000/health
```

### Model loading issues

```bash
# Check if model loaded successfully
curl http://localhost:8000/health
# Look for: "model_loaded": true

# If model_loaded is false, check the pod logs
kubectl logs <POD_NAME>

# Common errors in logs:
# "Could not connect to MLflow" → MLFLOW_TRACKING_URI is wrong or MLflow is down
# "No model found" → Model hasn't been trained/registered yet
# "Connection refused" → Pod can't reach the host (private IP issue)
```

### Test a prediction

```bash
# Quick fraud test
curl -s -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{
    "step": 1, "type": "TRANSFER", "amount": 3500000.0,
    "oldbalanceOrg": 3500000.0, "newbalanceOrig": 0.0,
    "oldbalanceDest": 0.0, "newbalanceDest": 0.0,
    "errorBalanceOrig": 0.0, "errorBalanceDest": -3500000.0,
    "type_CASH_IN": 0, "type_CASH_OUT": 0, "type_DEBIT": 0,
    "type_PAYMENT": 0, "type_TRANSFER": 1
  }'

# Expected: {"fraud_probability": ~0.9+, "fraud_label": "FRAUD", ...}
```

### Check model metadata

```bash
curl http://localhost:8000/model-info
```

---

## 13. Model Training & MLflow Integration

### Run training locally

```bash
cd Model_Training
pip install -r requirements.txt
python train.py
```

### Run training via Docker

```bash
docker compose up trainer
docker compose logs trainer
```

### Check if model is registered in MLflow

```bash
# MLflow REST API — list registered models
curl http://localhost:5000/api/2.0/mlflow/registered-models/search

# List experiments
curl http://localhost:5000/api/2.0/mlflow/experiments/search

# List runs in default experiment
curl "http://localhost:5000/api/2.0/mlflow/runs/search" \
  -H "Content-Type: application/json" \
  -d '{"experiment_ids": ["0"]}'
```

### Training fails to connect to MLflow

```bash
# Verify MLflow is reachable from the training environment
curl http://mlflow:5000/health          # inside Docker network
curl http://localhost:5000/health       # from the host

# Check environment variables
echo $MLFLOW_TRACKING_URI
echo $MLFLOW_S3_ENDPOINT_URL
echo $AWS_ACCESS_KEY_ID
```

---

## 14. Common Failure Patterns

### Pattern: Pod is in `CrashLoopBackOff`

```bash
# 1. Get the error
kubectl logs <POD_NAME> --previous

# 2. Most common cause: model can't load
#    → Pod can't reach MLflow because MLFLOW_TRACKING_URI points to localhost
#    → Fix: use the host's private IP (10.0.1.30) instead

# 3. Check env vars are correct
kubectl exec <POD_NAME> -- env | grep MLFLOW

# 4. From inside the pod, can it reach MLflow?
kubectl exec <POD_NAME> -- curl -s http://10.0.1.30:5000/health
```

### Pattern: Jenkins pipeline passes but deploy doesn't update pods

```bash
# 1. Check if the deploy stage actually ran (only runs on 'main' branch)
#    Look for: when { branch 'main' }

# 2. Check the current image on the deployment
kubectl get deployment app -o jsonpath='{.spec.template.spec.containers[0].image}'

# 3. Force a rollout
kubectl rollout restart deployment/app
kubectl rollout status deployment/app
```

### Pattern: Image push fails in Jenkins

```bash
# 1. Check Docker Hub credentials in Jenkins
#    Manage Jenkins → Credentials → dockerhubcreds

# 2. Test login from the agent
docker login -u <DOCKER_USER>

# 3. Check disk space on the agent (full disk = push fails)
df -h
docker system df
```

### Pattern: Ingress returns 404 or 502

```bash
# 1. Is the ingress controller running?
kubectl get pods -n ingress-nginx

# 2. Is the service healthy?
kubectl get endpoints fraud-api
# Should show pod IPs — if empty, no pods match the service selector

# 3. Is the ingress correctly configured?
kubectl describe ingress fraud-api-ingress

# 4. Check ingress controller logs for errors
kubectl logs -n ingress-nginx -l app.kubernetes.io/name=ingress-nginx --tail=50
```

### Pattern: Everything was working, now nothing connects

```bash
# After an EC2 reboot, public IPs change (unless using Elastic IPs)
# 1. Get new IPs
cd terraform && terraform output

# 2. On prod server: Docker containers and minikube may not auto-restart
ssh -i sentinalbank-deployer-key.pem ubuntu@<NEW_PROD_IP>
docker compose up -d
minikube start --driver=docker
kubectl get pods

# 3. Update Jenkins agent node config with new agent IP
#    Manage Jenkins → Nodes → ec2-agent → Configure → Host
```

---

> **Tip**: When debugging, always work bottom-up: **infrastructure → containers → services → application**. If the pod can't start, check Docker first. If the pod starts but crashes, check logs. If the pod runs but can't serve traffic, check networking.
