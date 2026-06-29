# SentinalBank — Hardened Fraud Detection API

<!-- AGENT NOTE: The project name is intentionally spelled "SentinalBank" (with an 'a'), NOT "SentinelBank". Do NOT correct the spelling back to "SentinelBank" in any documentation, comments, variables, or configs. -->

> **MLSecOps Reference Architecture** — A production-grade fraud detection platform demonstrating the full lifecycle of building, securing, and deploying an ML-powered API with automated CI/CD, Infrastructure as Code, and Kubernetes orchestration.

---

## What Is This?

SentinalBank is a **hardened, end-to-end ML fraud detection system** built on real-world DevSecOps practices. It takes a RandomForestClassifier trained on the PaySim synthetic financial dataset, wraps it in a FastAPI inference API, and deploys it through a fully automated pipeline — from code commit to running Kubernetes pods — with security scanning gates at every stage.

The project covers **five major infrastructure pillars**:

| Pillar | Technology | Purpose |
|---|---|---|
| **ML Training & Tracking** | MLflow + MinIO | Experiment tracking, model registry, S3-compatible artifact storage |
| **Containerization** | Docker + Docker Compose | Reproducible builds, multi-stage images, local service orchestration |
| **Infrastructure as Code** | Terraform (AWS) | Automated provisioning of VPC, subnets, security groups, and EC2 instances |
| **CI/CD Pipeline** | Jenkins (Declarative) | 12-stage security-gated pipeline from checkout to production deploy |
| **Container Orchestration** | Kubernetes (minikube) | Production serving with RBAC, NetworkPolicies, Ingress, and rolling updates |

📘 **[Setup & Deployment Instructions →](INSTRUCTIONS.md)** — Full manual walkthrough for provisioning infrastructure and deploying the platform from scratch.

🔧 **[Debug Commands Reference →](debug_commands.md)** — Troubleshooting commands for every layer: SSH, Terraform, Docker, Kubernetes, Jenkins, and the API.

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────────────────┐
│                        AWS VPC (10.0.0.0/16)                           │
│                     ap-south-2 · Public Subnet                         │
│                                                                        │
│  ┌────────────────┐   SSH    ┌────────────────┐   SSH    ┌───────────────────┐
│  │ Jenkins Server │────────► │ Jenkins Agent  │────────► │   Prod Server     │
│  │  10.0.1.10     │          │  10.0.1.20     │          │   10.0.1.30       │
│  │                │          │                │          │                   │
│  │ • Jenkins UI   │          │ • Docker       │          │ • MinIO (S3)      │
│  │   (port 8080)  │          │ • Build+Scan   │          │ • MLflow Tracking │
│  │ • Pipeline     │          │ • Image Push   │          │ • minikube        │
│  │   Controller   │          │ • Cosign Sign  │          │   └─ fraud-api    │
│  └────────────────┘          └────────────────┘          └───────────────────┘
│                                                                        │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## Project Structure

```
SentinalBank/
├── app/                        # FastAPI Fraud Detection API
│   ├── main.py                 #   Application entrypoint & endpoints
│   ├── schemas.py              #   Pydantic request/response models
│   ├── model_loader.py         #   MLflow model loader with fallback
│   ├── config.py               #   Configuration module
│   ├── Dockerfile              #   Multi-stage production image
│   ├── .dockerignore            #   Build context exclusions
│   ├── .env.example            #   Environment template
│   └── requirements.txt        #   Python dependencies
│
├── Model_Training/             # ML Training Pipeline
│   ├── train.py                #   Full training pipeline (MLflow logging)
│   ├── save_model.py           #   CI-only: build model artifact for scanning
│   ├── Dockerfile              #   Trainer container image
│   ├── Dataset/                #   PaySim synthetic financial dataset
│   ├── artifacts/              #   Local model.pkl + metadata output
│   └── requirements.txt
│
├── k8s/                        # Kubernetes Manifests
│   ├── app.yaml                #   Deployment (2 replicas) + ClusterIP Service
│   ├── ingress.yaml            #   Nginx Ingress routing
│   ├── networkpolicy.yaml      #   Default-deny + per-app allow rules
│   ├── rbac.yaml               #   Least-privilege ServiceAccount
│   └── secret.yaml             #   MinIO credential references
│
├── terraform/                  # Infrastructure as Code
│   └── main.tf                 #   VPC, subnets, SGs, 3× EC2 instances
│
├── jenkins/                    # Jenkins Server Setup
│   └── docker-compose.yml      #   Jenkins controller container
│
├── Jenkinsfile                 # CI/CD Pipeline (12 stages)
├── Jenkinsfile.test            # Lightweight test pipeline
├── docker-compose.yml          # Local dev: MinIO + MLflow + Trainer
├── kubestart.sh                # One-command K8s bootstrap script
├── .trivyignore                # CVE suppression list (unfixable OS vulns)
├── .gitignore
├── secret.env.example          # Credential template
├── INSTRUCTIONS.md             # Full manual setup guide
└── README.md                   # ← You are here
```

---

## CI/CD Pipeline — Jenkins

The Jenkinsfile defines a **12-stage declarative pipeline** that runs on a dedicated EC2 agent node. Every stage runs in an isolated Docker container (pinned by SHA256 digest) to guarantee reproducible, hermetic builds.

```
Checkout → GitLeaks → Pip Audit → Bandit → API Image Push → SBOM Gen
   → Trivy Scan → Checkov IaC → Build Model → ModelScan → Cosign Sign
   → Verify Signature → Deploy
```

### Stage Breakdown

| # | Stage | Tool | What It Does |
|---|---|---|---|
| 1 | **Checkout** | Git | Clones the repo onto the Jenkins agent workspace |
| 2 | **GitLeaks** | [Gitleaks](https://github.com/gitleaks/gitleaks) | Scans commit history for hardcoded secrets, API keys, and passwords |
| 3 | **Pip Audit** | [pip-audit](https://github.com/pypa/pip-audit) | SCA — checks `requirements.txt` for known vulnerable Python packages |
| 4 | **Bandit** | [Bandit](https://github.com/PyCQA/bandit) | SAST — static analysis for common Python security anti-patterns |
| 5 | **API Image Push** | Docker | Builds the multi-stage app image and pushes to Docker Hub |
| 6 | **SBOM Generation** | [Syft](https://github.com/anchore/syft) | Generates a CycloneDX Software Bill of Materials for the built image |
| 7 | **Container Scan** | [Trivy](https://github.com/aquasecurity/trivy) | Scans the container image for OS and library CVEs; gates on CRITICAL severity |
| 8 | **IaC Scan** | [Checkov](https://github.com/bridgecrewio/checkov) | Scans Kubernetes manifests, Dockerfiles, and Terraform configs for misconfigurations |
| 9 | **Build Temporary Model** | Python | Trains a temporary model artifact in the workspace for scanning (does not push to MLflow) |
| 10 | **Model Scan** | [ModelScan](https://github.com/protectai/modelscan) | Scans the serialized `.pkl` model for malicious payloads (pickle deserialization attacks) |
| 11 | **Cosign Sign** | [Cosign](https://github.com/sigstore/cosign) | Cryptographically signs the Docker image digest with a private key |
| 12 | **Verify Signature** | Cosign | Verifies the image signature with the public key before deployment |
| 13 | **Deploy** | SSH + kubectl | SSHs into the prod server and performs a rolling update on the Kubernetes deployment; auto-rollback on failure |

Every scanner tool image is **pinned by SHA256 digest** (not mutable tags) to prevent supply chain tampering. All scan reports are archived as Jenkins artifacts for audit trails.

---

## Terraform — Infrastructure as Code

Terraform provisions the entire AWS infrastructure in a single `terraform apply`:

### What Gets Created

| Resource | Details |
|---|---|
| **VPC** | `10.0.0.0/16` CIDR block with DNS support enabled |
| **Public Subnet** | `10.0.1.0/24` with auto-assign public IPs |
| **Internet Gateway** | Attached to the VPC for outbound internet access |
| **Route Table** | Default route `0.0.0.0/0` → Internet Gateway |
| **3 Security Groups** | Per-server ingress rules (Jenkins UI, SSH, MLflow, MinIO, FastAPI) |
| **3 EC2 Instances** | Jenkins Server (`10.0.1.10`), Jenkins Agent (`10.0.1.20`), Prod Server (`10.0.1.30`) |
| **SSH Key Pair** | Auto-generated 4096-bit RSA key; private key saved locally as `.pem` |

### How It Works

1. **`terraform init`** — Downloads the AWS, TLS, and Local providers
2. **`terraform plan`** — Previews exactly what will be created/modified/destroyed
3. **`terraform apply`** — Provisions all resources; outputs the public IPs of each server
4. **`terraform destroy`** — Tears down everything when you're done (stops EC2 billing)

All instances use Ubuntu 24.04 LTS (auto-resolved latest AMI), `m7i-flex.large` instance type, and 30 GB gp3 root volumes. Static private IPs are assigned to ensure stable internal addressing for SSH and `kubectl` deploy commands.

---

## Kubernetes — Container Orchestration

The FastAPI fraud detection API runs inside a **minikube** cluster on the Prod Server, providing production-grade orchestration features even in a single-node lab environment.

### Manifest Breakdown

| Manifest | Purpose |
|---|---|
| **`app.yaml`** | `Deployment` with 2 replicas + `ClusterIP` Service. Containers run as non-root (`UID 1001`), drop all Linux capabilities, enforce `allowPrivilegeEscalation: false`, and set CPU/memory requests and limits. |
| **`ingress.yaml`** | Nginx Ingress Controller routing. Routes all HTTP traffic on `/` to the `fraud-api` service on port 8000. |
| **`networkpolicy.yaml`** | **Default-deny ingress** across the entire namespace, then a targeted allow rule opening only port 8000 for the `fraud-api` pods. This is a zero-trust networking model. |
| **`rbac.yaml`** | A dedicated `ServiceAccount` (`sa-app`) with `automountServiceAccountToken: false` — the pod has no access to the Kubernetes API. Least-privilege by default. |
| **`secret.yaml`** | Kubernetes Secret for MinIO credentials, injected as environment variables into the app pods. |

### How Deployments Work

1. The `kubestart.sh` script auto-detects the host's private IP, substitutes it into the pod environment variables (so pods can reach MinIO/MLflow on the host), applies all manifests, and waits for pod readiness.
2. On each CI/CD run, the **Deploy** stage SSHs into the prod server and runs `kubectl set image` with the new image digest, triggering a **rolling update** — zero-downtime, with automatic rollback if the new pods fail health checks.

---

## Containers — Docker

Containerization is used at every layer of the project:

### Application Image (`app/Dockerfile`)

- **Multi-stage build** — Stage 1 installs build dependencies (gcc) and pip packages; Stage 2 copies only the compiled packages into a clean runtime image. This reduces the final image size and attack surface.
- **Pinned base image** — Uses `python:3.11-slim` pinned by SHA256 digest, not a mutable tag, preventing silent base image changes.
- **Non-root execution** — Creates `appuser` (UID 1001) and runs the app as that user, not root.
- **Selective COPY** — Uses `.dockerignore` to exclude secrets, caches, and dev files from the build context.
- **Production CMD** — `uvicorn` runs without `--reload` or debug flags.

### Docker Compose Services (`docker-compose.yml`)

| Service | Image | Purpose |
|---|---|---|
| **minio** | `minio/minio` | S3-compatible object storage for ML model artifacts |
| **createbucket** | `minio/mc` | One-shot init container that creates the `mlflow` bucket |
| **mlflow** | `ghcr.io/mlflow/mlflow` | Experiment tracking server with SQLite backend + S3 artifact store |
| **trainer** | Custom build | One-shot container that trains the model and logs to MLflow |

All services use **health checks** (`healthcheck` directives) and **dependency ordering** (`depends_on` with `condition`) to ensure correct startup sequencing: MinIO → bucket creation → MLflow → trainer.

### Jenkins Server (`jenkins/docker-compose.yml`)

Jenkins runs as a Docker container with the Docker socket mounted (`/var/run/docker.sock`), allowing the controller to manage builds that themselves spawn Docker containers — "Docker-in-Docker" via socket sharing.

---

## ML Model & API

### Training Pipeline

- **Dataset**: PaySim synthetic financial dataset (50,000 transactions)
- **Algorithm**: `RandomForestClassifier` from scikit-learn
- **Features**: Transaction type (one-hot encoded), amount, balance fields, and computed balance error features
- **Tracking**: Metrics, parameters, and the serialized model are logged to MLflow; artifacts stored in MinIO (S3)
- **CI Variant**: `save_model.py` trains a lightweight model artifact purely for pipeline security scanning without pushing to MLflow

### API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Returns API health and model-loaded status |
| `POST` | `/predict` | Scores a transaction and returns fraud probability + label |
| `GET` | `/model-info` | Returns model training metadata (metrics, parameters, timestamp) |

### Example — Score a Transaction

```bash
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{
    "step": 1,
    "type": "TRANSFER",
    "amount": 3500000.0,
    "oldbalanceOrg": 3500000.0,
    "newbalanceOrig": 0.0,
    "oldbalanceDest": 0.0,
    "newbalanceDest": 0.0,
    "errorBalanceOrig": 0.0,
    "errorBalanceDest": -3500000.0,
    "type_CASH_IN": 0,
    "type_CASH_OUT": 0,
    "type_DEBIT": 0,
    "type_PAYMENT": 0,
    "type_TRANSFER": 1
  }'
```

**Key fraud signals** the model has learned:
- **Transaction type**: `TRANSFER` and `CASH_OUT` are highest risk
- **Amount**: Very large amounts correlate with fraud
- **Account draining**: `newbalanceOrig = 0` (entire balance sent out)
- **Destination anomaly**: `newbalanceDest = 0` despite receiving funds → large negative `errorBalanceDest`

---

## Security Scanning Summary

The pipeline integrates **seven distinct security tools** across the entire stack:

| Layer | Tool | Scan Type |
|---|---|---|
| Source Code | **Gitleaks** | Secrets detection in git history |
| Source Code | **Bandit** | Python SAST (static analysis) |
| Dependencies | **pip-audit** | SCA (known vulnerable packages) |
| Container Image | **Trivy** | OS + library CVE scanning |
| Container Image | **Syft** | SBOM generation (CycloneDX) |
| Infrastructure | **Checkov** | IaC misconfiguration (Terraform, K8s, Dockerfile) |
| ML Model | **ModelScan** | Malicious pickle payload detection |
| Supply Chain | **Cosign** | Cryptographic image signing + verification |

---

## Quick Start (Local Development)

### 1. Train the Model

```bash
docker-compose up
```

This starts MinIO, creates the `mlflow` bucket, starts MLflow, and runs the trainer — all automatically orchestrated via health checks and dependency ordering.

### 2. Run the API Standalone

```bash
cd app
pip install -r requirements.txt
uvicorn main:app --reload
```

The API will be available at `http://localhost:8000`.

### 3. Full Infrastructure Deployment

For the complete AWS deployment with Terraform, Jenkins, and Kubernetes, follow the **[INSTRUCTIONS.md](INSTRUCTIONS.md)** guide — it walks through every step from `terraform init` to a running Kubernetes cluster with automated CI/CD.

---

## Teardown

```bash
cd terraform
terraform destroy
```

This removes all EC2 instances, VPC, subnet, security groups, and the key pair. Your local `.pem` and `.env` files are not affected.
