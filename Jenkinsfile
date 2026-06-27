pipeline {
    agent none
    environment {
        REGISTRY      = "my-docker-registry"
        GITLEAKS_IMG  = "ghcr.io/gitleaks/gitleaks@sha256:c00b6bd0aeb3071cbcb79009cb16a60dd9e0a7c60e2be9ab65d25e6bc8abbb7f"
        TRIVY_IMG     = "aquasec/trivy@sha256:f5d0e600ecda7449e2a9b272805aef698631d3bb3f3a739a750de2c6819acdc9"
        CHECKOV_IMG   = "bridgecrew/checkov@sha256:655c1f563d5c834d27d3884e46925939ea9abd234961c07f32fa997b01d927c2"
        SYFT_IMG      = "anchore/syft@sha256:c6d5719f48f5a5986acf2847eb1ed7c53176e712d5721fcd156184cfb262f6eb"
        COSIGN_IMG    = "gcr.io/projectsigstore/cosign@sha256:6bbe0d281d955c79f85b325f0f7e651c1bcab5a4fa4ad4903d74955178a3b2eb"
        BANDIT_IMG    = "ghcr.io/pycqa/bandit/bandit@sha256:5cfa0381199ecebc07ca4b5322c853faaea6f4d7fc4940f7a74890a91c194d9b"
        APP_IMAGE     = "bennetsharwin/sentinalbank-app:1.${BUILD_ID}"
        TRAINER_IMAGE = "bennetsharwin/sentinalbank-trainer:1.${BUILD_ID}"
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
                    docker run --rm -v "$(pwd)":/repo $GITLEAKS_IMG \
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
                    image "${env.BANDIT_IMG}"
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
                        sh 'docker build -t $APP_IMAGE app/'
                        sh 'docker push $APP_IMAGE'
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
                        sh 'cd Model_Training && docker build -t $TRAINER_IMAGE .'
                        sh 'docker push $TRAINER_IMAGE'
                    }
                }
            }
        }

        // SBOM Generation - Syft
        stage('SBOM Generation - Syft') {
            agent { label 'ec2-agent' }
            steps {
                sh '''
                    mkdir -p reports
                    
                    echo "=== Generating SBOM for API image ==="
                    docker run --rm \
                        -v /var/run/docker.sock:/var/run/docker.sock \
                        $SYFT_IMG \
                        $APP_IMAGE \
                        -o cyclonedx-json > reports/sbom-app.json

                    echo "=== Generating SBOM for Trainer image ==="
                    docker run --rm \
                        -v /var/run/docker.sock:/var/run/docker.sock \
                        $SYFT_IMG \
                        $TRAINER_IMAGE \
                        -o cyclonedx-json > reports/sbom-trainer.json
                '''
            }
            post {
                always {
                    archiveArtifacts artifacts: 'reports/sbom-*.json', allowEmptyArchive: true
                }
                failure {
                    echo 'Syft SBOM generation failed. Build failed.'
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
                        -v "$(pwd)/reports":/reports \
                        -v "$(pwd)/.trivyignore":/root/.trivyignore \
                        $TRIVY_IMG image \
                        --format json \
                        --output /reports/trivy-app-report.json \
                        $APP_IMAGE

                    echo "=== Scanning Trainer image ==="
                    docker run --rm \
                        -v /var/run/docker.sock:/var/run/docker.sock \
                        -v "$(pwd)/reports":/reports \
                        -v "$(pwd)/.trivyignore":/root/.trivyignore \
                        $TRIVY_IMG image \
                        --format json \
                        --output /reports/trivy-trainer-report.json \
                        $TRAINER_IMAGE

                    echo "=== Gating on CRITICAL ==="
                    docker run --rm \
                        -v /var/run/docker.sock:/var/run/docker.sock \
                        -v "${WORKSPACE}/.trivyignore":/tmp/.trivyignore \
                        $TRIVY_IMG image \
                        --severity CRITICAL --exit-code 1 \
                        --ignorefile /tmp/.trivyignore \
                        --show-suppressed \
                        $APP_IMAGE

                    docker run --rm \
                        -v /var/run/docker.sock:/var/run/docker.sock \
                        -v "${WORKSPACE}/.trivyignore":/tmp/.trivyignore \
                        $TRIVY_IMG image \
                        --severity CRITICAL --exit-code 1 \
                        --ignorefile /tmp/.trivyignore \
                        --show-suppressed \
                        $TRAINER_IMAGE
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

        // IaC Scan - Checkov
        stage('IaC Scan - Checkov') {
            agent { label 'ec2-agent' }
            steps {
                sh '''
                    mkdir -p reports
                    docker run --rm \
                        -v $(pwd):/work \
                        -w /work \
                        $CHECKOV_IMG \
                        --directory /work/k8s \
                        --framework kubernetes \
                        --output json \
                        --output-file-path /work/reports \
                        --quiet \
                        --soft-fail --hard-fail-on HIGH
                    
                    # Rename the output to a descriptive name
                    mv reports/results_json.json reports/checkov-k8s-report.json
 
                    # Also scan Dockerfiles
                    docker run --rm \
                        -v $(pwd):/work \
                        -w /work \
                        $CHECKOV_IMG \
                        --file /work/app/Dockerfile \
                        --framework dockerfile \
                        --output json \
                        --output-file-path /work/reports \
                        --quiet \
                        --soft-fail --hard-fail-on HIGH
                    
                    mv reports/results_json.json reports/checkov-dockerfile-report.json

                    # Also scan Terraform
                    docker run --rm \
                        -v $(pwd):/work \
                        -w /work \
                        $CHECKOV_IMG \
                        --directory /work/terraform \
                        --framework terraform \
                        --output json \
                        --output-file-path /work/reports \
                        --quiet \
                        --soft-fail --hard-fail-on HIGH
                    
                    mv reports/results_json.json reports/checkov-terraform-report.json
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

        // Build Temporary Model — CI-only: train the model and save to workspace for scanning
        stage('Build Temporary Model for Scans') {
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
                    pip install --no-cache-dir scikit-learn==1.5.0 pandas==2.1.4 numpy==1.26.2
                    export PATH=$HOME/.local/bin:$PATH
                    export WORKSPACE=/app
                    python Model_Training/save_model.py
                '''
            }
            post {
                failure {
                    echo 'CI model build failed. Pipeline aborted.'
                }
            }
        }

        // Model Scan — scans the workspace-resident model artifact
        stage('Model Scan') {
            agent { label 'ec2-agent' }
            steps {
                sh '''
                    mkdir -p reports

                    docker run --rm \
                        -v "$(pwd)/artifacts/modelscan":/scan \
                        -v "$(pwd)/reports":/reports \
                        python:3.11-slim \
                        bash -c "pip install --no-cache-dir modelscan -q && \
                                modelscan scan -p /scan/model.pkl -of json -o /reports/modelscan-report.json"
                '''
            }
            post {
                always {
                    archiveArtifacts artifacts: 'reports/modelscan-report.json', allowEmptyArchive: true
                    sh 'rm -rf artifacts/modelscan || true'
                }
                failure {
                    echo 'ModelScan detected issues in the ML model. Build failed.'
                }
            }
        }

        // Sign Image - Cosign
        stage('Sign Image') {
            agent { label 'ec2-agent' }
            when { branch 'main' }
            steps {
                withCredentials([
                    file(credentialsId: 'cosign-key', variable: 'COSIGN_KEY_FILE'),
                    string(credentialsId: 'cosign-password', variable: 'COSIGN_PASSWORD'),
                    usernamePassword(credentialsId: 'dockerhubcreds', usernameVariable: 'DOCKER_USER', passwordVariable: 'DOCKER_PASS')
                ]) {
                    sh '''
                        mkdir -p $(pwd)/docker-config
                        echo $DOCKER_PASS | docker --config $(pwd)/docker-config login -u $DOCKER_USER --password-stdin

                        docker run --rm \
                            -e COSIGN_PASSWORD=$COSIGN_PASSWORD \
                            -v $COSIGN_KEY_FILE:/tmp/cosign.key \
                            -v $(pwd)/docker-config:/root/.docker \
                            ${COSIGN_IMG} \
                            sign --key /tmp/cosign.key --yes \
                            ${APP_IMAGE}

                        docker run --rm \
                            -e COSIGN_PASSWORD=$COSIGN_PASSWORD \
                            -v $COSIGN_KEY_FILE:/tmp/cosign.key \
                            -v $(pwd)/docker-config:/root/.docker \
                            ${COSIGN_IMG} \
                            sign --key /tmp/cosign.key --yes \
                            ${TRAINER_IMAGE}
                    '''
                }
            }
            post {
                always {
                    sh 'rm -rf $(pwd)/docker-config || true'
                }
            }
        }

        // Verify Signature - Cosign
        stage('Verify Signature') {
            agent { label 'ec2-agent' }
            when { branch 'main' }
            steps {
                withCredentials([
                    file(credentialsId: 'cosign-pub', variable: 'COSIGN_PUB_FILE'),
                    usernamePassword(credentialsId: 'dockerhubcreds', usernameVariable: 'DOCKER_USER', passwordVariable: 'DOCKER_PASS')
                ]) {
                    sh '''
                        mkdir -p $(pwd)/docker-config
                        echo $DOCKER_PASS | docker --config $(pwd)/docker-config login -u $DOCKER_USER --password-stdin

                        docker run --rm \
                            -v $COSIGN_PUB_FILE:/tmp/cosign.pub \
                            -v $(pwd)/docker-config:/root/.docker \
                            ${COSIGN_IMG} \
                            verify --key /tmp/cosign.pub ${APP_IMAGE}

                        docker run --rm \
                            -v $COSIGN_PUB_FILE:/tmp/cosign.pub \
                            -v $(pwd)/docker-config:/root/.docker \
                            ${COSIGN_IMG} \
                            verify --key /tmp/cosign.pub ${TRAINER_IMAGE}
                    '''
                }
            }
            post {
                always { sh 'rm -rf $(pwd)/docker-config || true' }
                failure { echo 'Signature verification failed — image may be tampered or unsigned. Build failed.' }
            }
        }
        // Deploy Stage
        stage('Deploy') {
            agent { label 'ec2-agent' }
            when { branch 'main' }
            environment {
                PROD_SERVER_IP = credentials('prod-server-ip') // or hardcode if static
            }
            steps {
                sshagent(credentials: ['prod-server-ssh']) {
                    sh '''
                        ssh -o StrictHostKeyChecking=no ubuntu@${PROD_SERVER_IP} \
                          "kubectl set image deployment/app app=bennetsharwin/sentinalbank-app:1.${BUILD_ID} && \
                           kubectl rollout status deployment/app --timeout=120s || \
                           (kubectl rollout undo deployment/app && exit 1)"
                    '''
                }
            }
        }
    }
}