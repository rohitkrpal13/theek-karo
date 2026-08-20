#!/usr/bin/env bash
# Theek Karo — Full Cloud Deployment Script
# Usage: ./deploy.sh [staging|prod]
#
# Prerequisites:
#   1. AWS CLI configured with credentials (aws configure)
#   2. Docker running
#   3. Terraform >= 1.5 installed
#   4. ECR repositories created (run setup-ecr.sh first)

set -euo pipefail

ENVIRONMENT="${1:-staging}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
TERRAFORM_DIR="$SCRIPT_DIR"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log() { echo -e "${BLUE}[$(date +'%H:%M:%S')]${NC} $1"; }
success() { echo -e "${GREEN}[✓]${NC} $1"; }
warn() { echo -e "${YELLOW}[⚠]${NC} $1"; }
error() { echo -e "${RED}[✗]${NC} $1"; exit 1; }

# --- Validation ---
[[ "$ENVIRONMENT" == "staging" || "$ENVIRONMENT" == "prod" ]] || error "Usage: $0 [staging|prod]"

log "Deploying Theek Karo to ${ENVIRONMENT}..."

# --- Step 1: Check prerequisites ---
log "Step 1: Checking prerequisites..."

command -v aws >/dev/null 2>&1 || error "AWS CLI not found. Install: https://aws.amazon.com/cli/"
command -v terraform >/dev/null 2>&1 || error "Terraform not found. Install: https://terraform.io"
command -v docker >/dev/null 2>&1 || error "Docker not found. Install: https://docker.com"

AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text 2>/dev/null) || error "AWS credentials not configured. Run: aws configure"
log "AWS Account: $AWS_ACCOUNT_ID"

# --- Step 2: Bootstrap Terraform state ---
log "Step 2: Bootstrapping Terraform state bucket..."

cd "$TERRAFORM_DIR"

if ! aws s3api head-bucket --bucket "tk-tfstate-${AWS_ACCOUNT_ID}" 2>/dev/null; then
    log "Creating Terraform state bucket..."
    terraform init -input=false
    terraform apply -auto-approve \
        -var="aws_account_id=${AWS_ACCOUNT_ID}" \
        -target=aws_s3_bucket.tfstate \
        -target=aws_s3_bucket_versioning.tfstate \
        -target=aws_s3_bucket_server_side_encryption_configuration.tfstate \
        -target=aws_s3_bucket_public_access_block.tfstate \
        -input=false
    success "Terraform state bucket created"
else
    success "Terraform state bucket exists"
fi

# --- Step 3: Initialize Terraform ---
log "Step 3: Initializing Terraform..."

# Update backend config
cat > backend.tf << EOF
terraform {
  backend "s3" {
    bucket         = "tk-tfstate-${AWS_ACCOUNT_ID}"
    key            = "tk/${ENVIRONMENT}/terraform.tfstate"
    region         = "ap-south-1"
    encrypt        = true
    dynamodb_table = "terraform-lock"
  }
}
EOF

# Create DynamoDB table for state locking
if ! aws dynamodb describe-table --table-name terraform-lock --region ap-south-1 >/dev/null 2>&1; then
    log "Creating DynamoDB table for state locking..."
    aws dynamodb create-table \
        --table-name terraform-lock \
        --attribute-definitions AttributeName=LockID,AttributeType=S \
        --key-schema AttributeName=LockID,KeyType=HASH \
        --billing-mode PAY_PER_REQUEST \
        --region ap-south-1 >/dev/null
    sleep 5
    success "DynamoDB table created"
fi

terraform init -input=false -reconfigure
success "Terraform initialized"

# --- Step 4: Create secrets ---
log "Step 4: Creating secrets in AWS Secrets Manager..."

SECRET_NAME="tk-${ENVIRONMENT}-runtime"

# Generate strong secrets if not set
DB_PASSWORD="${DB_PASSWORD:-$(openssl rand -base64 32 | tr -dc 'A-Za-z0-9!@#$%^&*' | head -c 24)}"
JWT_SECRET="${JWT_SECRET:-$(openssl rand -base64 32 | tr -dc 'A-Za-z0-9' | head -c 32)}"

if ! aws secretsmanager describe-secret --secret-id "$SECRET_NAME" --region ap-south-1 >/dev/null 2>&1; then
    log "Creating secret: $SECRET_NAME"
    aws secretsmanager create-secret \
        --name "$SECRET_NAME" \
        --secret-string "{\"db_url\":\"postgresql+asyncpg://tk_app:${DB_PASSWORD}@placeholder/theek_karo\",\"jwt_secret\":\"${JWT_SECRET}\",\"ai_api_key\":\"\",\"media_secret_key\":\"placeholder\"}" \
        --region ap-south-1 >/dev/null
    success "Secret created"
else
    warn "Secret $SECRET_NAME already exists (skipping)"
fi

# --- Step 5: Apply Terraform ---
log "Step 5: Applying Terraform infrastructure..."

terraform plan \
    -var-file="${ENVIRONMENT}.tfvars" \
    -out=tfplan \
    -input=false

echo ""
read -p "Apply the above plan? (yes/no): " CONFIRM
if [[ "$CONFIRM" == "yes" ]]; then
    terraform apply -input=false tfplan
    success "Infrastructure applied"
else
    error "Deployment cancelled"
fi

# --- Step 6: Setup ECR repositories ---
log "Step 6: Setting up ECR repositories..."

AWS_REGION=$(terraform output -raw region 2>/dev/null || echo "ap-south-1")

for REPO in tk-api tk-web; do
    if ! aws ecr describe-repositories --repository-names "$REPO" --region "$AWS_REGION" >/dev/null 2>&1; then
        aws ecr create-repository --repository-name "$REPO" --region "$AWS_REGION" >/dev/null
        success "ECR repository created: $REPO"
    else
        success "ECR repository exists: $REPO"
    fi
done

ECR_REGISTRY="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"

# --- Step 7: Build and push Docker images ---
log "Step 7: Building and pushing Docker images..."

aws ecr get-login-password --region "$AWS_REGION" | docker login --username AWS --password-stdin "$ECR_REGISTRY"

# Build API
log "Building API..."
docker build -t "$ECR_REGISTRY/tk-api:latest" -t "$ECR_REGISTRY/tk-api:$(git -C "$PROJECT_ROOT" rev-parse --short HEAD 2>/dev/null || echo 'latest')" "$PROJECT_ROOT/services/api"
docker push "$ECR_REGISTRY/tk-api" --all-tags
success "API image pushed"

# Build Web
log "Building Web..."
docker build -t "$ECR_REGISTRY/tk-web:latest" -t "$ECR_REGISTRY/tk-web:$(git -C "$PROJECT_ROOT" rev-parse --short HEAD 2>/dev/null || echo 'latest')" "$PROJECT_ROOT/apps/web"
docker push "$ECR_REGISTRY/tk-web" --all-tags
success "Web image pushed"

# --- Step 8: Run database migrations ---
log "Step 8: Running database migrations..."

DB_ENDPOINT=$(terraform output -raw db_endpoint 2>/dev/null || echo "")
if [[ -n "$DB_ENDPOINT" ]]; then
    pip install "sqlalchemy[asyncio]" asyncpg alembic 2>/dev/null
    
    # Get DB URL from Secrets Manager
    DB_URL=$(aws secretsmanager get-secret-value --secret-id "$SECRET_NAME" --region "$AWS_REGION" --query 'SecretString' --output text | python3 -c "import sys,json; print(json.load(sys.stdin)['db_url'])")
    
    cd "$PROJECT_ROOT/services/api"
    TK_DATABASE_URL="$DB_URL" alembic upgrade head
    success "Migrations applied"
else
    warn "Could not get DB endpoint - run migrations manually"
fi

# --- Step 9: Update ECS services ---
log "Step 9: Updating ECS services..."

CLUSTER="tk-${ENVIRONMENT}"
for SERVICE in tk-api tk-web tk-worker; do
    if aws ecs describe-services --cluster "$CLUSTER" --services "$SERVICE" --region "$AWS_REGION" >/dev/null 2>&1; then
        aws ecs update-service \
            --cluster "$CLUSTER" \
            --service "$SERVICE" \
            --force-new-deployment \
            --region "$AWS_REGION" >/dev/null
        success "Updated service: $SERVICE"
    else
        warn "Service $SERVICE not found (may need initial deployment)"
    fi
done

# --- Step 10: Verify deployment ---
log "Step 10: Verifying deployment..."

sleep 10

API_URL=$(terraform output -raw api_url 2>/dev/null || echo "https://api.${ENVIRONMENT}.theekkar.in")
WEB_URL=$(terraform output -raw web_url 2>/dev/null || echo "https://${ENVIRONMENT}.theekkar.in")

echo ""
echo "========================================="
echo "  DEPLOYMENT COMPLETE"
echo "========================================="
echo ""
echo "  Environment: $ENVIRONMENT"
echo "  API URL:     $API_URL"
echo "  Web URL:     $WEB_URL"
echo ""
echo "  Next steps:"
echo "  1. Configure DNS (Route53) for ${ENVIRONMENT}.theekkar.in"
echo "  2. Verify SSL certificates are issued"
echo "  3. Test the API health: curl $API_URL/healthz"
echo "  4. Open the web app: $WEB_URL"
echo ""
echo "  Useful commands:"
echo "  - Check ECS services: aws ecs describe-services --cluster $CLUSTER --services tk-api tk-web tk-worker"
echo "  - View logs: aws logs tail /ecs/tk-${ENVIRONMENT} --follow"
echo "  - Terraform state: cd infra/terraform && terraform show"
echo ""
