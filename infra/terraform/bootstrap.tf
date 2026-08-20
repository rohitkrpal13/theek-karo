# Bootstrap: Create S3 bucket for Terraform state
# Run this FIRST: terraform init && terraform apply -target=aws_s3_bucket.tfstate

terraform {
  required_version = ">= 1.5"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.60"
    }
  }
}

variable "bootstrap_region" {
  type    = string
  default = "ap-south-1"
}

variable "aws_account_id" {
  type        = string
  description = "12-digit AWS account ID"
}

provider "aws" {
  region = var.bootstrap_region
}

# S3 bucket for Terraform state
resource "aws_s3_bucket" "tfstate" {
  bucket = "tk-tfstate-${var.aws_account_id}"
}

resource "aws_s3_bucket_versioning" "tfstate" {
  bucket = aws_s3_bucket.tfstate.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "tfstate" {
  bucket = aws_s3_bucket.tfstate.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "aws:kms"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "tfstate" {
  bucket                  = aws_s3_bucket.tfstate.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# IAM user for Terraform deployments (or use OIDC with GitHub Actions)
resource "aws_iam_user" "terraform" {
  name = "tk-terraform"
}

resource "aws_iam_user_policy" "terraform" {
  name = "tk-terraform-deploy"
  user = aws_iam_user.terraform.name
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ecs:*",
          "ec2:*",
          "vpc:*",
          "rds:*",
          "elasticache:*",
          "s3:*",
          "cloudfront:*",
          "iam:*",
          "secretsmanager:*",
          "logs:*",
          "route53:*",
          "acm:*",
          "cloudwatch:*",
          "ssm:*",
          "lambda:*",
        ]
        Resource = "*"
      },
      {
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
        Resource = ["${aws_s3_bucket.tfstate.arn}/*"]
      }
    ]
  })
}

resource "aws_iam_access_key" "terraform" {
  user = aws_iam_user.terraform.name
}

# GitHub OIDC Provider for CI/CD
resource "aws_iam_openid_connect_provider" "github" {
  url             = "https://token.actions.githubusercontent.com"
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = ["ffffffffffffffffffffffffffffffffffffffff"]
}

# GitHub Actions deploy role
resource "aws_iam_role" "github_deploy" {
  name = "tk-github-deploy"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = { Federated = aws_iam_openid_connect_provider.github.arn }
      Action = "sts:AssumeRoleWithWebIdentity"
      Condition = {
        StringEquals = {
          "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com"
        }
        StringLike = {
          "token.actions.githubusercontent.com:sub" = "repo:*/theek-karo:*"
        }
      }
    }]
  })
}

resource "aws_iam_role_policy" "github_deploy" {
  name = "deploy"
  role = aws_iam_role.github_deploy.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ecr:GetAuthorizationToken",
          "ecr:BatchCheckLayerAvailability",
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchGetImage",
          "ecr:PutImage",
          "ecr:InitiateLayerUpload",
          "ecr:UploadLayerPart",
          "ecr:CompleteLayerUpload",
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "ecs:UpdateService",
          "ecs:DescribeServices",
          "ecs:DescribeTaskDefinition",
          "ecs:RegisterTaskDefinition",
        ]
        Resource = "*"
      },
      {
        Effect   = "Allow"
        Action   = ["iam:PassRole"]
        Resource = "*"
      },
    ]
  })
}

output "terraform_user_access_key" {
  value = aws_iam_access_key.terraform.id
}

output "terraform_user_secret_key" {
  value     = aws_iam_access_key.terraform.secret
  sensitive = true
}

output "github_deploy_role_arn" {
  value = aws_iam_role.github_deploy.arn
}

output "tfstate_bucket" {
  value = aws_s3_bucket.tfstate.id
}
