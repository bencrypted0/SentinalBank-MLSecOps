pipeline {
    agent none
    environment {
        REGISTRY = "my-docker-registry" 
    }

    stages {

        stage('Checkout') {
            agent { label 'ec2-agent' }
            steps {
                checkout scm
            }
        }

        stage('Bandit SAST Scan') {
            agent {
                docker {
                    image 'ghcr.io/pycqa/bandit/bandit:latest'
                    label 'ec2-agent'
                    args '-v ${WORKSPACE}:/src -w /src --entrypoint=""'

                }
            }
            steps {
                sh 'bandit -r app/ model_training/ --severity-level high -f json -o bandit-report.json || true'
            }
            post {
                always {
                    archiveArtifacts artifacts: 'bandit-report.json', allowEmptyArchive: true
                }
            }
        }

        stage('Secrets - Gitleaks') {
            agent { label 'ec2-agent' }
            steps { echo 'Secrets - Gitleaks' }
        }

        stage('SCA') {
            agent { label 'ec2-agent' }
            steps { echo 'SCA' }
        }

        stage('Build Image') {
            agent { label 'ec2-agent' }
            steps { echo 'Build Image' }
        }

        stage('Container Scan') {
            agent { label 'ec2-agent' }
            steps { echo 'Container Scan' }
        }

        stage('IaC Scan') {
            agent { label 'ec2-agent' }
            steps { echo 'IaC Scan' }
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

        stage('Push Image') {
            agent { label 'ec2-agent' }
            when { branch 'main' }
            steps { echo 'Push Image' }
        }

        stage('Update Manifest') {
            agent { label 'ec2-agent' }
            when { branch 'main' }
            steps { echo 'Update Manifest' }
        }

        // No deploy stages — ArgoCD handles that
    }
}