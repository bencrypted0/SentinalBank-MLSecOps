pipeline {
    agent none
    environment {
        REGISTRY = "my-docker-registry" 
    }

    stages {

        //Checkout Stage
        stage('Checkout') {
            agent { label 'ec2-agent' }
            steps {
                checkout scm
            }
        }

        // Secrets Scan - Gitleaks
        stage('Secrets Scan - Gitleaks') {
            agent {label 'ec2-agent'}
            steps {
                sh '''
                    mkdir -p reports
                    docker run --rm -v $(pwd):/repo ghcr.io/gitleaks/gitleaks:latest \
                        detect --source /repo --report-path /repo/reports/gitleaks-report.json \
                        --report-format json --exit-code 1
                '''
            }
            post {
                always {
                    archiveArtifacts artifacts: 'reports/gitleaks-report.json', allowEmptyArchive: true
                }
                failure {
                    echo 'Gitleaks detected secrets in the repository. Build failed.'
                }
            }
        }

        // SCA - pip-audit
        stage('SCA - pip-audit') {
            agent {
                docker {
                    image 'python:3.11-slim'
                    label 'ec2-agent'
                    args '-v ${WORKSPACE}:/app -w /app'
                }
            }
            steps {
                sh '''
                    export HOME=/tmp
                    python -m pip install --no-cache-dir --break-system-packages pip-audit
                    export PATH=$HOME/.local/bin:$PATH
                    mkdir -p reports

                    echo "Scanning app/requirements.txt..."
                    pip-audit -r app/requirements.txt --format json --output reports/pip-audit-app.json || true

                    echo "Scanning Model_Training/requirements.txt..."
                    pip-audit -r Model_Training/requirements.txt --format json --output reports/pip-audit-training.json || true
                '''
            }
            post {
                always {
                    archiveArtifacts artifacts: 'reports/pip-audit-*.json', allowEmptyArchive: true
                }
                failure {
                    echo 'pip-audit SCA scan failed. Build failed.'
                }
            }
        }

        // Bandit SAST Scan
        stage('Bandit SAST Scan') {
            agent {
                docker {
                    image 'ghcr.io/pycqa/bandit/bandit:latest'
                    label 'ec2-agent'
                    args '-v ${WORKSPACE}:/src -w /src --entrypoint=""'

                }
            }
            steps {
                sh '''
                    mkdir -p reports
                    bandit -r app/ Model_Training/ --severity-level high -f json -o reports/bandit-report.json
                '''
            }
            post {
                always {
                    archiveArtifacts artifacts: 'reports/bandit-report.json', allowEmptyArchive: true
                }
                failure {
                    echo 'Bandit SAST scan failed. Build failed.'
                }
            }
        }

        // Build & Push — API image
        stage('Build & Push API') {
            agent { label 'ec2-agent' }
            steps {
                script {
                    docker.withRegistry('https://index.docker.io/v1/', 'dockerhubcreds') {
                        sh 'docker build -t bennetsharwin/sentinelbank-app:${BUILD_ID} -f app/Dockerfile .'
                        sh 'docker push bennetsharwin/sentinelbank-app:${BUILD_ID}'
                    }
                }
            }
        }

        // Build & Push — Trainer image
        stage('Build & Push Trainer') {
            agent { label 'ec2-agent' }
            steps {
                script {
                    docker.withRegistry('https://index.docker.io/v1/', 'dockerhubcreds') {
                        sh 'cd Model_Training && docker build -t bennetsharwin/sentinelbank-trainer:${BUILD_ID} .'
                        sh 'docker push bennetsharwin/sentinelbank-trainer:${BUILD_ID}'
                    }
                }
            }
        }

        // Container Scan — Trivy (both images)
        stage('Container Scan - Trivy') {
            agent { label 'ec2-agent' }
            steps {
                sh '''
                    mkdir -p reports

                    echo "=== Scanning API image ==="
                    docker run --rm \
                        -v /var/run/docker.sock:/var/run/docker.sock \
                        -v $(pwd)/reports:/reports \
                        aquasec/trivy:latest image \
                        --format json \
                        --output /reports/trivy-app-report.json \
                        bennetsharwin/sentinelbank-app:${BUILD_ID}

                    echo "=== Scanning Trainer image ==="
                    docker run --rm \
                        -v /var/run/docker.sock:/var/run/docker.sock \
                        -v $(pwd)/reports:/reports \
                        aquasec/trivy:latest image \
                        --format json \
                        --output /reports/trivy-trainer-report.json \
                        bennetsharwin/sentinelbank-trainer:${BUILD_ID}
                '''
            }
            post {
                always {
                    archiveArtifacts artifacts: 'reports/trivy-*-report.json', allowEmptyArchive: true
                }
                failure {
                    echo 'Trivy container scan failed. Build failed.'
                }
            }
        }

        stage('IaC Scan - Checkov') {
            agent { label 'ec2-agent' }
            steps {
                sh '''
                    mkdir -p reports
                    docker run --rm \
                        -v $(pwd):/work \
                        -w /work \
                        bridgecrew/checkov:latest \
                        --directory /work/k8s \
                        --framework kubernetes \
                        --output json \
                        --output-file-path /work/reports \
                        --soft-fail
                    
                    # Rename the output to a descriptive name
                    mv reports/results_json.json reports/checkov-k8s-report.json || true

                    # Also scan Dockerfiles
                    docker run --rm \
                        -v $(pwd):/work \
                        -w /work \
                        bridgecrew/checkov:latest \
                        --file /work/app/Dockerfile \
                        --framework dockerfile \
                        --output json \
                        --output-file-path /work/reports \
                        --soft-fail
                    
                    mv reports/results_json.json reports/checkov-dockerfile-report.json || true
                '''
            }
            post {
                always {
                    archiveArtifacts artifacts: 'reports/checkov-*.json', allowEmptyArchive: true
                }
                failure {
                    echo 'Checkov IaC scan failed. Build failed.'
                }
            }
        }

        stage('Model Scan') {
            agent { label 'ec2-agent' }
            steps { echo 'Model Scan' }
        }

        stage('Sign Image') {
            agent { label 'ec2-agent' }
            when { branch 'main' }
            steps { echo 'Sign Image' }
        }

        stage('Update Manifest') {
            agent { label 'ec2-agent' }
            when { branch 'main' }
            steps { echo 'Update Manifest' }
        }

        // No deploy stages — ArgoCD handles that
    }
}