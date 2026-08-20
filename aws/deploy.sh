#!/bin/bash
# ============================================
# Inter-Agent Trust Verifier — AWS ECS Deploy
# ============================================
set -euo pipefail

AWS_REGION="${AWS_REGION:-us-east-1}"
ECR_REPO="${ECR_REPO:-trust-verifier-api}"
ECS_CLUSTER="${ECS_CLUSTER:-trust-verifier-cluster}"
ECS_SERVICE="${ECS_SERVICE:-trust-verifier-service}"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

echo "╔══════════════════════════════════════╗"
echo "║  Trust Verifier — ECS Deployment     ║"
echo "╚══════════════════════════════════════╝"

# 1. Authenticate with ECR
echo "→ Authenticating with ECR..."
aws ecr get-login-password --region "$AWS_REGION" | \
  docker login --username AWS --password-stdin "$ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com"

# 2. Build and push API image
echo "→ Building API Docker image..."
docker build -t "$ECR_REPO:latest" .
docker tag "$ECR_REPO:latest" "$ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO:latest"
docker push "$ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO:latest"
echo "✓ Image pushed to ECR"

# 3. Replace placeholder ACCOUNT_ID in task definition
echo "→ Preparing task definition..."
sed "s/ACCOUNT_ID/$ACCOUNT_ID/g" aws/task-definition.json > /tmp/task-def.json

# 4. Register new task definition
echo "→ Registering task definition..."
TASK_DEF_ARN=$(aws ecs register-task-definition \
  --cli-input-json file:///tmp/task-def.json \
  --region "$AWS_REGION" \
  --query 'taskDefinition.taskDefinitionArn' \
  --output text)
echo "✓ Task definition: $TASK_DEF_ARN"

# 5. Update service
echo "→ Updating ECS service..."
aws ecs update-service \
  --cluster "$ECS_CLUSTER" \
  --service "$ECS_SERVICE" \
  --task-definition "$TASK_DEF_ARN" \
  --force-new-deployment \
  --region "$AWS_REGION" > /dev/null
echo "✓ Service updated — rolling deployment started"

# 6. Wait for stability
echo "→ Waiting for deployment to stabilize (timeout: 5min)..."
aws ecs wait services-stable \
  --cluster "$ECS_CLUSTER" \
  --services "$ECS_SERVICE" \
  --region "$AWS_REGION"

echo ""
echo "═══════════════════════════════════"
echo "✓ Deployment complete!"
echo "═══════════════════════════════════"
