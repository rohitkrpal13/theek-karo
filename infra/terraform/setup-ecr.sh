#!/usr/bin/env bash
# ECR Repository Setup for Theek Karo
# Usage: ./setup-ecr.sh [region]

set -euo pipefail

AWS_REGION="${1:-ap-south-1}"

echo "Setting up ECR repositories in ${AWS_REGION}..."

for REPO in tk-api tk-web; do
    if aws ecr describe-repositories --repository-names "$REPO" --region "$AWS_REGION" >/dev/null 2>&1; then
        echo "✓ Repository $REPO already exists"
    else
        aws ecr create-repository \
            --repository-name "$REPO" \
            --image-scanning-configuration scanOnPush=true \
            --encryption-configuration encryptionType=AES256 \
            --region "$AWS_REGION" >/dev/null
        echo "✓ Created repository $REPO"
    fi
done

# Set lifecycle policy to keep only last 10 images
for REPO in tk-api tk-web; do
    aws ecr put-lifecycle-policy \
        --repository-name "$REPO" \
        --lifecycle-policy-text '{
            "rules": [
                {
                    "rulePriority": 1,
                    "description": "Keep only last 10 images",
                    "selection": {
                        "tagStatus": "any",
                        "countType": "imageCountMoreThan",
                        "countNumber": 10
                    },
                    "action": {
                        "type": "expire"
                    }
                }
            ]
        }' \
        --region "$AWS_REGION" >/dev/null
    echo "✓ Set lifecycle policy for $REPO"
done

echo ""
echo "ECR repositories ready!"
echo ""
echo "Login command:"
echo "  aws ecr get-login-password --region ${AWS_REGION} | docker login --username AWS --password-stdin $(aws sts get-caller-identity --query Account --output text).dkr.ecr.${AWS_REGION}.amazonaws.com"
