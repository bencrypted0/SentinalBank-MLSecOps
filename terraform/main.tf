# ==============================================================================
# SentinalBank Infrastructure Deployment 
# ==============================================================================
# 3 EC2 instances in the ap-south-2 region:
#   1. Jenkins Server
#   2. Jenkins Agent
#   3. Prod Server
# ==============================================================================


terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

# AWS Provider Configuration
provider "aws" {
  region = var.region
}


# Terraform Variables
variable "region" {
  type        = string
  default     = "ap-south-2"
  description = "Target AWS region for deploying SentinalBank infrastructure"
}

variable "instance_type" {
  type        = string
  default     = "m7i-flex.large"
  description = "EC2 instance size for the servers"
}

variable "environment" {
  type        = string
  default     = "development"
  description = "Deployment environment name"
}



# Locals
locals {
  # Common tags merged across all resources
  common_tags = {
    Environment = var.environment
    ManagedBy   = "terraform"
    Project     = "SentinalBank"
  }
}



# Data Sources

# retrieve the latest official Ubuntu 24.04 LTS AMI
data "aws_ami" "ubuntu_24_04" {
  most_recent = true
  owners      = ["099720109477"] # Canonical

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-amd64-server-*"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}



# SSH Key Pair Generation

# Dynamically generate private key
resource "tls_private_key" "sentinalbank_key" {
  algorithm = "RSA"
  rsa_bits  = 4096
}

# Upload public key to AWS
resource "aws_key_pair" "sentinalbank_key" {
  key_name   = "sentinalbank-deployer-key"
  public_key = tls_private_key.sentinalbank_key.public_key_openssh
}

# Save the private key locally for SSH access
resource "local_file" "private_key" {
  content         = tls_private_key.sentinalbank_key.private_key_pem
  filename        = "${path.module}/sentinalbank-deployer-key.pem"
  file_permission = "0600"
}



# VPC Infrastructure

resource "aws_vpc" "main" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = merge(local.common_tags, {
    Name = "sentinalbank-vpc"
  })
}

resource "aws_subnet" "public" {
  vpc_id                  = aws_vpc.main.id
  cidr_block              = "10.0.1.0/24"
  map_public_ip_on_launch = true

  tags = merge(local.common_tags, {
    Name = "sentinalbank-public-subnet"
  })
}

resource "aws_internet_gateway" "igw" {
  vpc_id = aws_vpc.main.id

  tags = merge(local.common_tags, {
    Name = "sentinalbank-igw"
  })
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.igw.id
  }

  tags = merge(local.common_tags, {
    Name = "sentinalbank-public-rt"
  })
}

resource "aws_route_table_association" "public_association" {
  subnet_id      = aws_subnet.public.id
  route_table_id = aws_route_table.public.id
}



# Security Groups

# 1. Security Group for Jenkins Server
resource "aws_security_group" "jenkins_server" {
  name        = "sentinalbank-jenkins-server-sg"
  description = "Inbound traffic control for SentinalBank Jenkins Server"
  vpc_id      = aws_vpc.main.id

  # Administration SSH
  ingress {
    description = "SSH Administration"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # Jenkins Web UI Console
  ingress {
    description = "Jenkins Web Interface"
    from_port   = 8080
    to_port     = 8080
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # Jenkins inbound agent communication port (JNLP)
  ingress {
    description = "Jenkins Agent Connection Port"
    from_port   = 50000
    to_port     = 50000
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # Full internet outbound for package downloads, plugin installation, etc.
  egress {
    description = "Allow all outbound traffic"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(local.common_tags, {
    Name = "sentinalbank-jenkins-server-sg"
    Role = "jenkins-server"
  })
}

# 2. Security Group for Jenkins Agent
resource "aws_security_group" "jenkins_agent" {
  name        = "sentinalbank-jenkins-agent-sg"
  description = "Inbound traffic control for SentinalBank Jenkins Agent"
  vpc_id      = aws_vpc.main.id

  # SSH for management (or Jenkins master outbound initiator connection)
  ingress {
    description = "SSH Access"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # Outbound for pulling docker images, software updates, master connection
  egress {
    description = "Allow all outbound traffic"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(local.common_tags, {
    Name = "sentinalbank-jenkins-agent-sg"
    Role = "jenkins-agent"
  })
}

# 3. Security Group for Prod Server
resource "aws_security_group" "prod_server" {
  name        = "sentinalbank-prod-server-sg"
  description = "Inbound traffic control for SentinalBank Production Server"
  vpc_id      = aws_vpc.main.id

  # Administration SSH
  ingress {
    description = "SSH Administration"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # FastAPI Fraud Detection API app (port 8000 in docker-compose.yml)
  ingress {
    description = "SentinalBank FastAPI App"
    from_port   = 8000
    to_port     = 8000
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # MLflow Tracking Server UI/API (port 5000 in docker-compose.yml)
  ingress {
    description = "MLflow Tracking Server"
    from_port   = 5000
    to_port     = 5000
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # MinIO API Server (port 9000 in docker-compose.yml)
  ingress {
    description = "MinIO S3 API"
    from_port   = 9000
    to_port     = 9000
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # MinIO Console Web UI (port 9001 in docker-compose.yml)
  ingress {
    description = "MinIO Web Console"
    from_port   = 9001
    to_port     = 9001
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # Outbound for container engine image fetch & dependency resolution
  egress {
    description = "Allow all outbound traffic"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(local.common_tags, {
    Name = "sentinalbank-prod-server-sg"
    Role = "prod-server"
  })
}



# EC2 Instances

# #1 Jenkins Server
resource "aws_instance" "jenkins_server" {
  ami           = data.aws_ami.ubuntu_24_04.id
  instance_type = var.instance_type
  key_name      = aws_key_pair.sentinalbank_key.key_name
  subnet_id     = aws_subnet.public.id
  private_ip    = "10.0.1.10"

  vpc_security_group_ids = [aws_security_group.jenkins_server.id]

  # Root disk gp3 30GB configuration
  root_block_device {
    volume_type           = "gp3"
    volume_size           = 30
    delete_on_termination = true
  }

  tags = merge(local.common_tags, {
    Name = "Jenkins Server"
    Role = "jenkins-server"
  })
}

# #2 Jenkins Agent
resource "aws_instance" "jenkins_agent" {
  ami           = data.aws_ami.ubuntu_24_04.id
  instance_type = var.instance_type
  key_name      = aws_key_pair.sentinalbank_key.key_name
  subnet_id     = aws_subnet.public.id
  private_ip    = "10.0.1.20"

  vpc_security_group_ids = [aws_security_group.jenkins_agent.id]

  # Root disk gp3 30GB configuration
  root_block_device {
    volume_type           = "gp3"
    volume_size           = 30
    delete_on_termination = true
  }

  tags = merge(local.common_tags, {
    Name = "Jenkins Agent"
    Role = "jenkins-agent"
  })
}

# #3 Prod Server
resource "aws_instance" "prod_server" {
  ami           = data.aws_ami.ubuntu_24_04.id
  instance_type = var.instance_type
  key_name      = aws_key_pair.sentinalbank_key.key_name
  subnet_id     = aws_subnet.public.id
  private_ip    = "10.0.1.30"

  vpc_security_group_ids = [aws_security_group.prod_server.id]

  # Root disk gp3 30GB configuration
  root_block_device {
    volume_type           = "gp3"
    volume_size           = 30
    delete_on_termination = true
  }

  tags = merge(local.common_tags, {
    Name = "Prod Server"
    Role = "prod-server"
  })
}



# Outputs

output "jenkins_server_id" {
  description = "The EC2 Instance ID of the Jenkins Server"
  value       = aws_instance.jenkins_server.id
}

output "jenkins_server_public_ip" {
  description = "The public IP address of the Jenkins Server"
  value       = aws_instance.jenkins_server.public_ip
}

output "jenkins_agent_id" {
  description = "The EC2 Instance ID of the Jenkins Agent"
  value       = aws_instance.jenkins_agent.id
}

output "jenkins_agent_public_ip" {
  description = "The public IP address of the Jenkins Agent"
  value       = aws_instance.jenkins_agent.public_ip
}

output "prod_server_id" {
  description = "The EC2 Instance ID of the Prod Server"
  value       = aws_instance.prod_server.id
}

output "prod_server_public_ip" {
  description = "The public IP address of the Prod Server"
  value       = aws_instance.prod_server.public_ip
}
