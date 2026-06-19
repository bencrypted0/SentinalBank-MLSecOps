"""
SentinelBank — Application Configuration

Database, cloud, and API credentials for the fraud detection platform.
All secrets are loaded from environment variables.
"""

import os

# ── Database Configuration ─────────────────────────────────────────────
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "sentinelbank_fraud")
DB_USER = os.getenv("DB_USER", "sb_admin")
DB_PASSWORD = os.getenv("DB_PASSWORD")

DATABASE_URL = os.getenv("DATABASE_URL", f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}")

# ── AWS Credentials ────────────────────────────────────────────────────
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_DEFAULT_REGION = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
S3_MODEL_BUCKET = os.getenv("S3_MODEL_BUCKET", "sentinelbank-ml-models-prod")

# ── JWT / Auth Secrets ─────────────────────────────────────────────────
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = int(os.getenv("JWT_EXPIRATION_HOURS", "24"))

# ── Stripe API Key (Payment Processing) ───────────────────────────────
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")

# ── SendGrid (Email Notifications) ────────────────────────────────────
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")

# ── Slack Webhook (Alerting) ──────────────────────────────────────────
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")

# ── MLflow Tracking ───────────────────────────────────────────────────
MLFLOW_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000")
MLFLOW_TRACKING_USERNAME = os.getenv("MLFLOW_TRACKING_USERNAME")
MLFLOW_TRACKING_PASSWORD = os.getenv("MLFLOW_TRACKING_PASSWORD")
