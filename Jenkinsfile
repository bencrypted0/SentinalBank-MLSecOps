pipeline {
    agent none
    environment {
        REGISTRY = "my-docker-registry" 
    }

    stages {
        stage('Checkout') {             // Pulls the image from the repository
            steps {
                checkout scm
            }
        }
        stage('Bandit SAST Scan') {
            agent {
                docker {
                    image 'ghcr.io/pycqa/bandit/bandit:latest'
                    label 'ec2-agent'
                    args '-v ${WORKSPACE}:/src -w /src'
                    reuseNode true
                }
            }
            steps {
                sh 'bandit -r . --severity-level high -f json -o bandit-report.json || true'
            }
            post {
                always {
                    archiveArtifacts artifacts: 'bandit-report.json', allowEmptyArchive: true
                }
            }
        }
        stage('Secrets - Gitleaks') { steps { echo 'Secrets - Gitleaks' } }
        stage('SCA')                { steps { echo 'SCA' } }
        stage('Build Image')        { steps { echo 'Build Image' } }
        stage('Container Scan')     { steps { echo 'Container Scan' } }
        stage('IaC Scan')           { steps { echo 'IaC Scan' } }
        stage('Model Scan')         { steps { echo 'Model Scan' } }
        stage('Sign Image') {
            when { branch 'main' }
            steps { echo 'Sign Image' }
        }
        stage('Push Image') {
            when { branch 'main' }
            steps { echo 'Push Image' }
        }
        stage('Update Manifest') {
            when { branch 'main' }
            steps { echo 'Update Manifest' }
        }
        // No deploy stages — ArgoCD handles that
    }
}