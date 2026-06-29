# SentinalBank — Manual Setup Instructions

← Back to **[README.md](README.md)**

This document walks through setting up the entire SentinalBank infrastructure **from scratch, manually**, with no automation beyond Terraform provisioning the raw infrastructure. Use this if you're doing a fresh deployment, debugging a broken environment, or just want to understand exactly what's happening at each layer before any of it gets scripted.

---

## Table of Contents

1. [Prerequisites](#0-prerequisites)
2. [Clone the Repository](#1-clone-the-repository)
3. [Set Up AWS Credentials](#2-set-up-aws-credentials-for-terraform)
4. [Provision Infrastructure with Terraform](#3-provision-infrastructure-with-terraform)
5. [Set Up the Prod Server](#4-set-up-the-prod-server-minio--mlflow--minikube)
6. [Set Up the Jenkins Server](#5-set-up-the-jenkins-server)
7. [Set Up the Jenkins Agent](#6-set-up-the-jenkins-agent)
8. [Add Required Jenkins Credentials](#7-add-required-jenkins-credentials)
9. [Deploy to minikube](#8-deploy-the-fastapi-inference-api-to-minikube)
10. [Run the Pipeline End-to-End](#9-run-the-pipeline-end-to-end)
11. [Teardown](#10-teardown)
12. [Troubleshooting](#troubleshooting-notes)

**Architecture recap:**
- **Jenkins Server** (EC2) — runs Jenkins via Docker Compose
- **Jenkins Agent** (EC2) — connects to Jenkins Server over SSH, runs builds
- **Prod Server** (EC2) — runs MinIO + MLflow via Docker Compose, and minikube (Kubernetes) hosting the FastAPI inference API

---

## 0. Prerequisites

Before you start, make sure you have:

- An AWS account with an IAM user that has the `AmazonEC2FullAccess` managed policy, or the scoped custom `TerraformDeployerPolicy` (see earlier setup) attached — not your root/admin credentials
- AWS Access Key ID + Secret Access Key for that IAM user
- **Terraform**, available one of two ways (pick whichever you prefer — both are used interchangeably in this guide):
  - Installed directly on your local machine, so you can run commands like:
    ```bash
    terraform init
    ```
  - Or, if you'd rather not install anything locally, run it via Docker instead:
    ```powershell
    docker run --rm -it -v ${PWD}:/workspace -w /workspace --env-file .env hashicorp/terraform:latest init
    ```
    (macOS/Linux: replace `${PWD}` with `$(pwd)`)
- Docker installed on your **local machine** (used to build/push images, and to run Terraform in a container if you're going that route)
- A **Docker Hub account and API token** — Jenkins needs this to push the built app image to Docker Hub during the CI/CD pipeline. Generate one at Docker Hub → Account Settings → Security → New Access Token, and keep it handy for Step 7 (you'll store it as the `dockerhubcreds` Jenkins credential, using your Docker Hub username and this token as the password)
- Git installed locally
- An SSH client (built into PowerShell/macOS/Linux terminals)

---

## 1. Clone the Repository

```bash
git clone https://github.com/bencrypted0/SentinalBank-MLSecOps.git
cd SentinalBank-MLSecOps
```

---

## 2. Set Up AWS Credentials for Terraform

Navigate to the `terraform/` directory and create a `.env` file (this is git-ignored — never commit it):

```bash
cd terraform
```

Create `.env` with the following content:

```env
AWS_ACCESS_KEY_ID=your-access-key-id
AWS_SECRET_ACCESS_KEY=your-secret-access-key
AWS_DEFAULT_REGION=ap-south-2
```

---

## 3. Provision Infrastructure with Terraform

Run these commands using **either** Terraform installed locally **or** via Docker — pick one and stick with it for the rest of this process (mixing the two is fine too, since both read/write the same local state file).

### 3.1 Initialize Terraform

Host-installed:
```bash
terraform init
```

Via Docker:
```powershell
docker run --rm -it -v ${PWD}:/workspace -w /workspace --env-file .env hashicorp/terraform:latest init
```

> macOS/Linux users running the Docker version: replace `${PWD}` with `$(pwd)`.

This downloads the `aws`, `tls`, and `local` providers.

### 3.2 Validate the Configuration

Host-installed:
```bash
terraform validate
```

Via Docker:
```powershell
docker run --rm -it -v ${PWD}:/workspace -w /workspace --env-file .env hashicorp/terraform:latest validate
```

Fix any syntax errors before continuing.

### 3.3 Review the Plan

Host-installed:
```bash
terraform plan
```

Via Docker:
```powershell
docker run --rm -it -v ${PWD}:/workspace -w /workspace --env-file .env hashicorp/terraform:latest plan
```

Confirm it shows 3 EC2 instances, 1 VPC, 1 subnet, 3 security groups, and the key pair resources. Nothing should show `0 to add` — if it does, double check you're in the right directory.

### 3.4 Apply

Host-installed:
```bash
terraform apply
```

Via Docker:
```powershell
docker run --rm -it -v ${PWD}:/workspace -w /workspace --env-file .env hashicorp/terraform:latest apply
```

Type `yes` when prompted. This takes a few minutes. When it finishes, note the outputs:

```
jenkins_server_public_ip = "x.x.x.x"
jenkins_agent_public_ip  = "x.x.x.x"
prod_server_public_ip    = "x.x.x.x"
```

Write these IPs down — you'll need them constantly for the rest of this guide.

> **If `apply` fails partway through:** don't run `destroy`. Just fix the issue and re-run `apply` — Terraform only creates what's missing from state. See the troubleshooting note at the bottom of this doc if you hit an AWS "PendingVerification" error on a new account/region.

### 3.5 Locate Your Private Key

Terraform generated `sentinalbank-deployer-key.pem` in the `terraform/` directory. On Linux/macOS, lock down its permissions:

```bash
chmod 600 sentinalbank-deployer-key.pem
```

(On Windows, this isn't strictly enforced by NTFS — just don't share the file.)

---

## 4. Set Up the Prod Server (MinIO + MLflow + minikube)

### 4.1 SSH In

```bash
ssh -i sentinalbank-deployer-key.pem ubuntu@<PROD_SERVER_PUBLIC_IP>
```

### 4.2 Update Packages

```bash
sudo apt-get update && sudo apt-get upgrade -y
```

### 4.3 Install Docker

```bash
sudo apt-get install -y docker.io
sudo systemctl enable docker
sudo systemctl start docker
sudo usermod -aG docker $USER
```

Log out and back in (or run `newgrp docker`) for the group change to take effect:

```bash
exit
ssh -i sentinalbank-deployer-key.pem ubuntu@<PROD_SERVER_PUBLIC_IP>
```

Verify:

```bash
docker --version
docker ps
```

### 4.4 Install Docker Compose Plugin

```bash
sudo apt-get install -y docker-compose-plugin
docker compose version
```

> Use `docker compose` (with a space, the plugin) rather than the old standalone `docker-compose` binary — confirm which syntax your `docker-compose.yml` file expects.

### 4.5 Install kubectl

```bash
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
sudo install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl
kubectl version --client
```

### 4.6 Install minikube

```bash
curl -LO https://storage.googleapis.com/minikube/releases/latest/minikube-linux-amd64
sudo install minikube-linux-amd64 /usr/local/bin/minikube
minikube version
```

### 4.7 Start minikube

Since this is a cloud VM without guaranteed nested virtualization, use the Docker driver:

```bash
minikube start --driver=docker
```

Verify the cluster is up:

```bash
kubectl get nodes
```

### 4.8 Copy the Project Files to the Prod Server

From your **local machine** (not the SSH session), copy the repo's relevant folders over:

```bash
scp -i sentinalbank-deployer-key.pem -r ../docker-compose.yml ../mlflow ../minio ubuntu@<PROD_SERVER_PUBLIC_IP>:/home/ubuntu/
```

> Adjust paths to match your actual repo structure — this assumes a `docker-compose.yml` at the repo root and config folders for `mlflow`/`minio`.

### 4.9 Create the Shared Credentials File

Back in the SSH session, create one `.env` file that both Docker Compose and the K8s Secret (next step) will read from:

```bash
nano /home/ubuntu/secrets.env
```

Add:

```env
MINIO_ROOT_USER=your-minio-username
MINIO_ROOT_PASSWORD=your-minio-password
MLFLOW_TRACKING_URI=http://localhost:5000
```

Save and exit (`Ctrl+O`, `Enter`, `Ctrl+X` in nano).

### 4.10 Start MinIO + MLflow

```bash
cd /home/ubuntu
docker compose --env-file secrets.env up -d
```

Verify both containers are running:

```bash
docker ps
```

Check MLflow is reachable:

```bash
curl http://localhost:5000
```

Check MinIO console:

```bash
curl http://localhost:9001
```

### 4.11 Create the Matching K8s Secret

Use the **same** `secrets.env` file so credentials never drift out of sync between Docker Compose and the cluster:

```bash
kubectl create secret generic minio-creds --from-env-file=secrets.env
```

Verify:

```bash
kubectl get secrets
```

---

## 5. Set Up the Jenkins Server

### 5.1 SSH In

```bash
ssh -i sentinalbank-deployer-key.pem ubuntu@<JENKINS_SERVER_PUBLIC_IP>
```

### 5.2 Update Packages

```bash
sudo apt-get update && sudo apt-get upgrade -y
```

### 5.3 Install Docker + Compose Plugin

```bash
sudo apt-get install -y docker.io docker-compose-plugin
sudo systemctl enable docker
sudo systemctl start docker
sudo usermod -aG docker $USER
exit
```

Reconnect:

```bash
ssh -i sentinalbank-deployer-key.pem ubuntu@<JENKINS_SERVER_PUBLIC_IP>
```

### 5.4 Copy the Jenkins docker-compose File

Rather than copying files over from your local machine, clone the repo directly onto the Jenkins server and use the compose file from there:

```bash
git clone https://github.com/bencrypted0/SentinalBank-MLSecOps.git /home/ubuntu/SentinalBank-MLSecOps
cd /home/ubuntu/SentinalBank-MLSecOps/jenkins
```

> Adjust the path (`jenkins/`) to wherever your Jenkins-specific compose file actually lives in the repo.

### 5.5 Start Jenkins

```bash
cd /home/ubuntu/SentinalBank-MLSecOps/jenkins
docker compose up -d
```

### 5.6 Get the Initial Admin Password

```bash
docker exec -it <jenkins-container-name> cat /var/jenkins_home/secrets/initialAdminPassword
```

(Find the container name with `docker ps` if you don't already have it.)

### 5.7 Complete the Jenkins Setup Wizard

In a browser, go to:

```
http://<JENKINS_SERVER_PUBLIC_IP>:8080
```

- Paste the initial admin password
- Install suggested plugins (this includes the SSH-based agent plugins you'll need)
- Create your first admin user

### 5.7.1 Install Required Jenkins Plugins

After the setup wizard, go to **Manage Jenkins → Plugins → Available plugins** and install the following (if not already installed):

| Plugin | Why It's Needed |
|---|---|
| **Docker Pipeline** (`docker-workflow`) | Enables the `docker` agent type in declarative pipelines — without this, stages using `agent { docker { ... } }` will fail with `Invalid agent type "docker"` |
| **SSH Agent** | Provides `sshagent()` for the Deploy stage to SSH into the prod server |
| **Pipeline: Stage View** | Visual stage-by-stage pipeline view (optional but recommended) |

> **Critical**: The `Docker Pipeline` plugin is required. Without it, the Jenkinsfile will not parse — the `docker` agent type is not built-in to Jenkins core.

### 5.8 Generate an SSH Key Pair for Jenkins → Agent Communication

Since the agent connects via **SSH** (master initiates the connection out to the agent), Jenkins needs its own key pair separate from your `sentinalbank-deployer-key.pem`.

On the Jenkins server:

```bash
ssh-keygen -t rsa -b 4096 -f /home/ubuntu/.ssh/jenkins_agent_key -N ""
cat /home/ubuntu/.ssh/jenkins_agent_key.pub
```

Copy that public key output — you'll add it to the agent's `authorized_keys` in the next section.

### 5.9 Add the SSH Credential in Jenkins

In the Jenkins web UI:

1. **Manage Jenkins → Credentials → System → Global credentials → Add Credentials**
2. Kind: **SSH Username with private key**
3. ID: `jenkins-agent-ssh` (or similar — you'll reference this ID when defining the agent node)
4. Username: `ubuntu`
5. Private Key: paste the contents of `/home/ubuntu/.ssh/jenkins_agent_key` (the private key, not `.pub`)

---

## 6. Set Up the Jenkins Agent

### 6.1 SSH In (using your original Terraform-generated key)

```bash
ssh -i sentinalbank-deployer-key.pem ubuntu@<JENKINS_AGENT_PUBLIC_IP>
```

### 6.2 Update Packages

```bash
sudo apt-get update && sudo apt-get upgrade -y
```

### 6.3 Install Java

Jenkins agents need a JDK matching what your Jenkins controller requires. Check your Jenkins LTS version's documented requirement before assuming — at the time of writing, Java 17 or 21 both work for recent LTS releases:

```bash
sudo apt-get install -y openjdk-17-jdk
java -version
```

### 6.4 Install Docker (if your builds need to build/push images from the agent)

```bash
sudo apt-get install -y docker.io
sudo systemctl enable docker
sudo systemctl start docker
sudo usermod -aG docker $USER
exit
```

Reconnect:

```bash
ssh -i sentinalbank-deployer-key.pem ubuntu@<JENKINS_AGENT_PUBLIC_IP>
```

### 6.5 Authorize Jenkins' SSH Key

Add the public key you generated on the Jenkins server (Step 5.8) to this agent's authorized keys:

```bash
mkdir -p /home/ubuntu/.ssh
echo "<paste-the-jenkins-public-key-here>" >> /home/ubuntu/.ssh/authorized_keys
chmod 700 /home/ubuntu/.ssh
chmod 600 /home/ubuntu/.ssh/authorized_keys
```

### 6.6 Test the Connection from the Jenkins Server

Back on the **Jenkins server**, confirm it can SSH into the agent using the new key:

```bash
ssh -i /home/ubuntu/.ssh/jenkins_agent_key ubuntu@<JENKINS_AGENT_PUBLIC_IP> "echo connected"
```

You should see `connected` printed with no password prompt.

### 6.7 Register the Agent Node in Jenkins

In the Jenkins web UI:

1. **Manage Jenkins → Nodes → New Node**
2. Name it (e.g. `ec2-agent`), select **Permanent Agent**
3. Remote root directory: `/home/ubuntu/jenkins-agent` (create this dir on the agent first: `mkdir -p ~/jenkins-agent`)
4. Labels: `ec2-agent` (matches the `label 'ec2-agent'` used in your Jenkinsfile stages)
5. Launch method: **Launch agents via SSH**
6. Host: `<JENKINS_AGENT_PUBLIC_IP>`
7. Credentials: select `jenkins-agent-ssh` (created in Step 5.9)
8. Host Key Verification Strategy: "Non verifying" is simplest for a lab setup (not recommended for real production)
9. Save

Check the node's status — it should show as **online** within a few seconds. If not, click into the node and check the log for the SSH error.

---

## 7. Add Required Jenkins Credentials

In **Manage Jenkins → Credentials**, add the following (referenced by your Jenkinsfile):

| Credential ID | Type | Purpose |
|---|---|---|
| `dockerhubcreds` | Username with password | Push images to Docker Hub |
| `cosign-key` | Secret file | Cosign private key for image signing |
| `cosign-pub` | Secret file | Cosign public key for verification |
| `cosign-password` | Secret text | Password protecting the cosign private key |
| `prod-server-ssh` | SSH Username with private key | Deploy stage SSH access to prod server (use `sentinalbank-deployer-key.pem`) |

Generate the cosign keypair (on your local machine or the Jenkins server, wherever you'll run the upload from):

```bash
docker run --rm -v ${PWD}:/work -w /work gcr.io/projectsigstore/cosign:latest generate-key-pair
```

> macOS/Linux users: replace `${PWD}` with `$(pwd)`.

You'll be prompted for a password — remember it, you'll store it as the `cosign-password` credential. This produces two files:
- `cosign.key` → upload as the `cosign-key` **secret file** credential
- `cosign.pub` → upload as the `cosign-pub` **secret file** credential

---

## 8. Deploy the FastAPI Inference API to minikube

### 8.1 Push the App Image (manually, for first-time setup)

From your local machine, in the app's directory:

```bash
docker build -t bennetsharwin/sentinalbank-app:initial .
docker push bennetsharwin/sentinalbank-app:initial
```

### 8.2 SSH into the Prod Server and Apply K8s Manifests

```bash
ssh -i sentinalbank-deployer-key.pem ubuntu@<PROD_SERVER_PUBLIC_IP>
```

Copy your `k8s/` manifests over first (from local machine, separate terminal):

```bash
scp -i sentinalbank-deployer-key.pem -r ../k8s ubuntu@<PROD_SERVER_PUBLIC_IP>:/home/ubuntu/
```

Back in the SSH session:

```bash
cd /home/ubuntu/k8s
kubectl apply -f .
```

### 8.3 Verify the Deployment

```bash
kubectl get pods
kubectl get deployment app
kubectl rollout status deployment/app
```

### 8.4 Confirm the API Can Reach MinIO/MLflow

Check the pod's environment points at the correct address. Since MinIO/MLflow run on the **host**, not inside the cluster, the pod needs the host's private IP, not `localhost`:

```bash
kubectl exec -it <pod-name> -- env | grep -E "MLFLOW|MINIO"
```

These should point to the prod server's **private IP** (find it via `hostname -I` on the prod server, or the AWS console), not `127.0.0.1` — pods have their own network namespace and cannot reach the host via loopback.

### 8.5 Confirm Security Group Rules

The prod server's security group must allow inbound traffic on ports `5000` (MLflow) and `9000`/`9001` (MinIO) from the K8s pod network/node — not from `0.0.0.0/0` in a real production setup, though your current Terraform config allows this broadly for lab simplicity. Tighten this before calling the project "production-hardened" in your report.

---

## 9. Run the Pipeline End-to-End

Once everything above is wired up:

1. Push a commit to the `main` branch of your repo
2. In Jenkins, trigger the pipeline (or confirm your webhook trigger fires automatically)
3. Watch each stage: build → scan → sign → verify → deploy
4. Confirm the deploy stage successfully updates the running pod via `kubectl set image` and `kubectl rollout status`

---

## 10. Teardown

When you're done and want to stop paying for EC2:

Host-installed:
```bash
cd terraform
terraform destroy
```

Via Docker:
```powershell
cd terraform
docker run --rm -it -v ${PWD}:/workspace -w /workspace --env-file .env hashicorp/terraform:latest destroy
```

Type `yes` when prompted. This removes all three EC2 instances, the VPC, subnet, security groups, and key pair — but **does not** delete your local `.pem` file or `.env`, which you can remove manually if you want a fully clean slate.

---

## Troubleshooting Notes

- **`InvalidKeyPair.NotFound` on `apply`:** the key pair name in your Terraform config doesn't exist in AWS yet. If you're using the `tls_private_key` + `aws_key_pair` pattern, this shouldn't happen — Terraform creates it for you. If you see this, check you're not still referencing an old hardcoded key name somewhere.
- **`PendingVerification` error on `RunInstances`:** new AWS account/region, AWS is running an automated verification check. Wait up to 4 hours, then re-run `apply` — already-created resources won't be touched.
- **`docker: invalid reference format` running Terraform via Docker on Windows:** PowerShell doesn't expand `$(pwd)` the way bash does — use `${PWD}` instead.
- **Jenkins agent shows offline after SSH setup:** check `~/.ssh/authorized_keys` permissions on the agent (`700` for `.ssh`, `600` for `authorized_keys`) — SSH silently refuses overly permissive directories.
- **Pod can't reach MinIO/MLflow:** confirm you're using the prod server's **private IP**, not `127.0.0.1` or `localhost` — pod and host network namespaces are separate even when running on the same physical instance.