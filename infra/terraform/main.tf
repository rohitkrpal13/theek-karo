# Theek Karo — AWS production/staging infrastructure (Phase 11, ADR-034)
#
# Deployment shape: ECS Fargate (api, worker, web) behind an ALB; RDS
# Postgres+PostGIS; ElastiCache Redis; S3 + CloudFront for media; Secrets
# Manager for runtime secrets. GitHub Actions assumes the deploy role via OIDC.
#
# NOTE: this environment has no AWS credentials — `terraform validate` is the
# gate here; the first real `terraform apply` happens from the pipeline once
# the account + OIDC provider exist (see docs/SLOs.md + ROADMAP Phase 11).

terraform {
  required_version = ">= 1.5"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.60"
    }
  }
  backend "s3" {
    # populated at bootstrap: bucket = "tk-tfstate-<account-id>"
    key = "tk/{environment}/terraform.tfstate"
  }
}

variable "environment" {
  type        = string
  description = "staging | prod"
}

variable "region" {
  type    = string
  default = "ap-south-1"
}

variable "domain" {
  type        = string
  description = "Route53 domain for the apps (staging=*.staging.example.in)"
}

variable "db_password" {
  type      = string
  sensitive = true
}

variable "jwt_secret" {
  type      = string
  sensitive = true
}

variable "ai_api_key" {
  type      = string
  sensitive = true
  default   = null
}

locals {
  name       = "tk-${var.environment}"
  common_tags = {
    project = "theek-karo"
    env     = var.environment
  }
}

provider "aws" {
  region = var.region
  default_tags {
    tags = local.common_tags
  }
}

data "aws_availability_zones" "available" {
  state = "available"
}

# --- network ---------------------------------------------------------------
resource "aws_vpc" "main" {
  cidr_block           = var.environment == "prod" ? "10.0.0.0/16" : "10.1.0.0/16"
  enable_dns_support   = true
  enable_dns_hostnames = true
}

resource "aws_subnet" "public" {
  count                   = 2
  vpc_id                  = aws_vpc.main.id
  cidr_block              = cidrsubnet(aws_vpc.main.cidr_block, 8, count.index)
  availability_zone       = data.aws_availability_zones.available.names[count.index]
  map_public_ip_on_launch = true
}

resource "aws_subnet" "private" {
  count             = 2
  vpc_id            = aws_vpc.main.id
  cidr_block        = cidrsubnet(aws_vpc.main.cidr_block, 8, count.index + 10)
  availability_zone = data.aws_availability_zones.available.names[count.index]
}

resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id
}

resource "aws_route" "public_internet" {
  route_table_id         = aws_route_table.public.id
  destination_cidr_block = "0.0.0.0/0"
  gateway_id             = aws_internet_gateway.main.id
}

resource "aws_route_table_association" "public" {
  count          = 2
  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

resource "aws_route_table" "private" {
  vpc_id = aws_vpc.main.id
}

resource "aws_route_table_association" "private" {
  count          = 2
  subnet_id      = aws_subnet.private[count.index].id
  route_table_id = aws_route_table.private.id
}

resource "aws_security_group" "alb" {
  name        = "${local.name}-alb"
  vpc_id      = aws_vpc.main.id
  description = "ALB ingress (443/80) + egress to services"

  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_security_group" "services" {
  name        = "${local.name}-services"
  vpc_id      = aws_vpc.main.id
  description = "App services; ingress only from the ALB SG"

  ingress {
    from_port       = 0
    to_port         = 65535
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# --- compute (ECS Fargate) --------------------------------------------------
resource "aws_ecs_cluster" "main" {
  name = local.name
  setting {
    name  = "containerInsights"
    value = "enabled"
  }
}

resource "aws_cloudwatch_log_group" "app" {
  name              = "/ecs/${local.name}"
  retention_in_days = 14
}

resource "aws_iam_role" "task_execution" {
  name = "${local.name}-exec"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "task_execution" {
  role       = aws_iam_role.task_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role_policy" "task_secrets" {
  name = "read-secrets"
  role = aws_iam_role.task_execution.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["secretsmanager:GetSecretValue"]
      Resource = [aws_secretsmanager_secret.runtime.arn]
    }]
  })
}

resource "aws_ecs_service" "api" {
  name            = "tk-api"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.api.arn
  desired_count   = var.environment == "prod" ? 2 : 1
  launch_type     = "FARGATE"
  network_configuration {
    subnets          = aws_subnet.private[*].id
    security_groups  = [aws_security_group.services.id]
    assign_public_ip = false
  }
  load_balancer {
    target_group_arn = aws_lb_target_group.api.arn
    container_name   = "api"
    container_port   = 8000
  }
}

resource "aws_ecs_task_definition" "api" {
  family                   = "tk-api-task"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "512"
  memory                   = "1024"
  execution_role_arn       = aws_iam_role.task_execution.arn
  container_definitions = jsonencode([
    {
      name  = "api"
      image = "${var.region}.dkr.ecr.${var.region}.amazonaws.com/tk-api:latest"
      portMappings = [{ containerPort = 8000, protocol = "tcp" }]
      environment = [
        { name = "TK_ENV", value = var.environment },
        { name = "TK_REDIS_URL", value = "redis://${aws_elasticache_cluster.main.cache_nodes[0].address}:6379/0" },
        { name = "TK_CELERY_BROKER_URL", value = "redis://${aws_elasticache_cluster.main.cache_nodes[0].address}:6379/1" },
        { name = "TK_CELERY_ENABLED", value = "true" },
        { name = "TK_AI_AUTO_ANALYSIS", value = "true" },
        { name = "TK_MEDIA_STORAGE_MODE", value = "minio" },
        { name = "TK_MEDIA_MINIO_ENDPOINT", value = "s3.${var.region}.amazonaws.com" },
        # browsers receive presigned URLs signed against the regional S3
        # endpoint (the private bucket is only reachable with valid signatures;
        # SigV4 region must match the bucket region)
        { name = "TK_MEDIA_MINIO_PUBLIC_ENDPOINT", value = "s3.${var.region}.amazonaws.com" },
        { name = "TK_MEDIA_MINIO_REGION", value = var.region },
        { name = "TK_MEDIA_MINIO_SECURE", value = "true" },
        { name = "TK_MEDIA_MINIO_BUCKET", value = aws_s3_bucket.media.id },
        { name = "TK_MEDIA_MINIO_ACCESS_KEY", value = aws_iam_access_key.media.id },
      ],
      secrets = [
        { name = "TK_DATABASE_URL", valueFrom = "${aws_secretsmanager_secret.runtime.arn}:secret_string:db_url" },
        { name = "TK_MEDIA_MINIO_SECRET_KEY", valueFrom = "${aws_secretsmanager_secret.runtime.arn}:secret_string:media_secret_key" },
        { name = "TK_JWT_SECRET", valueFrom = "${aws_secretsmanager_secret.runtime.arn}:secret_string:jwt_secret" },
        { name = "TK_AI_API_KEY", valueFrom = "${aws_secretsmanager_secret.runtime.arn}:secret_string:ai_api_key" },
      ],
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.app.name
          "awslogs-region"        = var.region
          "awslogs-stream-prefix" = "api"
        }
      }
    }
  ])
}

resource "aws_ecs_service" "worker" {
  name            = "tk-worker"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.worker.arn
  desired_count   = 1
  launch_type     = "FARGATE"
  network_configuration {
    subnets          = aws_subnet.private[*].id
    security_groups  = [aws_security_group.services.id]
    assign_public_ip = false
  }
}

resource "aws_ecs_task_definition" "worker" {
  family                   = "tk-worker-task"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "512"
  memory                   = "1024"
  execution_role_arn       = aws_iam_role.task_execution.arn
  container_definitions = jsonencode([
    {
      name  = "worker"
      image = "${var.region}.dkr.ecr.${var.region}.amazonaws.com/tk-api:latest"
      command = [
        "celery", "-A", "tk_api.worker:celery_app", "worker", "--beat",
        "--pool=solo", "-l", "info",
      ]
      environment = [
        { name = "TK_ENV", value = var.environment },
        { name = "TK_CELERY_BROKER_URL", value = "redis://${aws_elasticache_cluster.main.cache_nodes[0].address}:6379/1" },
        { name = "TK_MEDIA_STORAGE_MODE", value = "minio" },
        { name = "TK_MEDIA_MINIO_ENDPOINT", value = "s3.${var.region}.amazonaws.com" },
        { name = "TK_MEDIA_MINIO_REGION", value = var.region },
        { name = "TK_MEDIA_MINIO_SECURE", value = "true" },
        { name = "TK_MEDIA_MINIO_BUCKET", value = aws_s3_bucket.media.id },
        { name = "TK_MEDIA_MINIO_ACCESS_KEY", value = aws_iam_access_key.media.id },
      ],
      secrets = [
        { name = "TK_DATABASE_URL", valueFrom = "${aws_secretsmanager_secret.runtime.arn}:secret_string:db_url" },
        { name = "TK_MEDIA_MINIO_SECRET_KEY", valueFrom = "${aws_secretsmanager_secret.runtime.arn}:secret_string:media_secret_key" },
        { name = "TK_JWT_SECRET", valueFrom = "${aws_secretsmanager_secret.runtime.arn}:secret_string:jwt_secret" },
      ],
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.app.name
          "awslogs-region"        = var.region
          "awslogs-stream-prefix" = "worker"
        }
      }
    }
  ])
}

resource "aws_ecs_service" "web" {
  name            = "tk-web"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.web.arn
  desired_count   = 1
  launch_type     = "FARGATE"
  network_configuration {
    subnets          = aws_subnet.private[*].id
    security_groups  = [aws_security_group.services.id]
    assign_public_ip = false
  }
  load_balancer {
    target_group_arn = aws_lb_target_group.web.arn
    container_name   = "web"
    container_port   = 3000
  }
}

resource "aws_ecs_task_definition" "web" {
  family                   = "tk-web-task"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "256"
  memory                   = "512"
  execution_role_arn       = aws_iam_role.task_execution.arn
  container_definitions = jsonencode([
    {
      name  = "web"
      image = "${var.region}.dkr.ecr.${var.region}.amazonaws.com/tk-web:latest"
      portMappings = [{ containerPort = 3000, protocol = "tcp" }]
      environment = [
        { name = "NEXT_PUBLIC_API_URL", value = "https://api.${var.domain}" },
      ]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.app.name
          "awslogs-region"        = var.region
          "awslogs-stream-prefix" = "web"
        }
      }
    }
  ])
}

# --- load balancer + routing -------------------------------------------------
resource "aws_lb" "main" {
  name               = "${local.name}-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = aws_subnet.public[*].id
}

resource "aws_lb_target_group" "api" {
  name        = "${local.name}-api"
  port        = 8000
  protocol    = "HTTP"
  vpc_id      = aws_vpc.main.id
  target_type = "ip"
  health_check {
    path                = "/healthz"
    healthy_threshold   = 2
    unhealthy_threshold = 3
    interval            = 30
  }
}

resource "aws_lb_target_group" "web" {
  name        = "${local.name}-web"
  port        = 3000
  protocol    = "HTTP"
  vpc_id      = aws_vpc.main.id
  target_type = "ip"
  health_check {
    path                = "/healthz"
    healthy_threshold   = 2
    unhealthy_threshold = 3
    interval            = 30
  }
}

resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.main.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type = "redirect"
    redirect {
      port        = "443"
      protocol    = "HTTPS"
      status_code = "HTTP_301"
    }
  }
}

resource "aws_lb_listener" "https" {
  load_balancer_arn = aws_lb.main.arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = var.environment == "prod" ? aws_acm_certificate.main[0].arn : aws_acm_certificate.main[0].arn
  default_action {
    type = "fixed-response"
    fixed_response {
      content_type = "application/json"
      message_body = jsonencode({ status = "not found", detail = "no route" })
      status_code  = "404"
    }
  }
  # routing rules applied via aws_lb_listener_rule resources (web & api paths)
}

resource "aws_acm_certificate" "main" {
  count             = 1
  domain_name       = "*.${var.domain}"
  validation_method = "DNS"
  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_lb_listener_rule" "web" {
  listener_arn = aws_lb_listener.https.arn
  priority     = 10
  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.web.arn
  }
  condition {
    path_pattern { values = ["/*"] }
  }
}

resource "aws_lb_listener_rule" "api" {
  listener_arn = aws_lb_listener.https.arn
  priority     = 90
  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api.arn
  }
  condition {
    path_pattern { values = ["/api/*", "/healthz", "/readyz", "/metrics"] }
  }
}

# --- data (RDS + ElastiCache + S3/CloudFront) ------------------------------ 
resource "aws_db_instance" "main" {
  identifier                  = "${local.name}-pg"
  engine                      = "postgres"
  engine_version              = "16.4"
  instance_class              = "db.t4g.micro"
  allocated_storage           = 20
  username                    = "tk_app"
  password                    = var.db_password
  db_name                     = "theek_karo"
  vpc_security_group_ids      = [aws_security_group.rds.id]
  db_subnet_group_name        = aws_db_subnet_group.main.name
  backup_retention_period     = 7   # PITR window; automated daily snapshots
  backup_window               = "03:00-04:00"
  maintenance_window          = "sun:04:30-sun:05:00"
  # DR (Step 10): prod runs multi-AZ (RTO ≈ minutes on AZ loss); non-prod
  # stays single-AZ to contain cost. Failover is transparent to the API
  # (asyncpg reconnect via pool_pre_ping).
  multi_az                    = var.environment == "prod"
  deletion_protection         = var.environment == "prod"
  skip_final_snapshot         = var.environment != "prod"
  storage_encrypted           = true
  performance_insights_enabled = false
}

# RDS Postgres 16 ships PostGIS + pgvector natively (ADR-034)
resource "aws_db_subnet_group" "main" {
  name       = "${local.name}-db"
  subnet_ids = aws_subnet.private[*].id
}

resource "aws_security_group" "rds" {
  name        = "${local.name}-rds"
  vpc_id      = aws_vpc.main.id
  description = "Postgres; ingress from app services only"
  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.services.id]
  }
}

resource "aws_elasticache_cluster" "main" {
  cluster_id           = "${local.name}-redis"
  engine               = "redis"
  node_type            = "cache.t4g.micro"
  num_cache_nodes      = 1
  parameter_group_name = "default.redis7"
  subnet_group_name    = aws_elasticache_subnet_group.main.name
  security_group_ids   = [aws_security_group.redis.id]
  # Redis is a cache + job broker (non-authoritative): keep one daily snapshot
  # so queue state survives a node replacement with minimal cost
  snapshot_retention_limit = 1
  snapshot_window          = "05:00-06:00"
}

resource "aws_elasticache_subnet_group" "main" {
  name       = "${local.name}-redis"
  subnet_ids = aws_subnet.private[*].id
}

resource "aws_security_group" "redis" {
  name        = "${local.name}-redis"
  vpc_id      = aws_vpc.main.id
  ingress {
    from_port       = 6379
    to_port         = 6379
    protocol        = "tcp"
    security_groups = [aws_security_group.services.id]
  }
}

resource "aws_s3_bucket" "media" {
  bucket        = "tk-media-${var.environment}"
  force_destroy = var.environment != "prod"
}

# DR (Step 10): versioning gives point-in-time recovery of media objects
# (accidental overwrite/delete). Noncurrent versions are cleaned by lifecycle
# after 30 days to bound storage cost.
resource "aws_s3_bucket_versioning" "media" {
  bucket = aws_s3_bucket.media.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "media" {
  bucket = aws_s3_bucket.media.id
  rule {
    id     = "expire-noncurrent-versions"
    status = "Enabled"
    filter {}
    noncurrent_version_expiration {
      noncurrent_days = 30
    }
  }
}

resource "aws_iam_access_key" "media" {
  user = aws_iam_user.media.name
}

resource "aws_iam_user" "media" {
  name = "${local.name}-media"
}

resource "aws_iam_user_policy" "media" {
  name = "media-rw"
  user = aws_iam_user.media.name
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      # object-level operations only: the app never lists objects, so
      # ListBucket is excluded to keep the blast radius of this key minimal
      Effect   = "Allow"
      Action   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
      Resource = ["${aws_s3_bucket.media.arn}/*"]
    }]
  })
}

resource "aws_cloudfront_response_headers_policy" "security_headers" {
  name    = "${local.name}-security-headers"
  comment = "Security headers including strict HSTS for Theek Karo CDN"

  security_headers_config {
    strict_transport_security {
      access_control_max_age_sec = 31536000
      include_subdomains         = true
      preload                    = true
      override                   = true
    }
    content_type_options {
      override = true
    }
    frame_options {
      frame_option = "DENY"
      override     = true
    }
    referrer_policy {
      referrer_policy = "strict-origin-when-cross-origin"
      override        = true
    }
  }
}

resource "aws_cloudfront_distribution" "media" {
  origin {
    domain_name = aws_s3_bucket.media.bucket_regional_domain_name
    origin_id   = "media"
    s3_origin_config {
      origin_access_identity = aws_cloudfront_origin_access_identity.media.cloudfront_access_identity_path
    }
  }
  enabled             = true
  default_cache_behavior {
    target_origin_id       = "media"
    viewer_protocol_policy = "redirect-to-https"
    allowed_methods        = ["GET", "HEAD"]
    cached_methods         = ["GET", "HEAD"]
    response_headers_policy_id = aws_cloudfront_response_headers_policy.security_headers.id
    forwarded_values {
      # SigV4 presigned URLs carry their signature in the query string; it must
      # reach S3 unchanged or every signed request returns 403
      query_string = true
      cookies {
        forward = "none"
      }
    }
    min_ttl     = 0
    default_ttl = 300
    max_ttl     = 86400
  }
  viewer_certificate {
    cloudfront_default_certificate = true
  }
  restrictions {
    geo_restriction { restriction_type = "none" }
  }
}

resource "aws_cloudfront_origin_access_identity" "media" {
  comment = "tk media"
}

# --- secrets ------------------------------------------------------------------
resource "aws_secretsmanager_secret" "runtime" {
  name = "${local.name}-runtime"
}

resource "aws_secretsmanager_secret_version" "runtime" {
  secret_id = aws_secretsmanager_secret.runtime.id
  secret_string = jsonencode({
    db_url           = "postgresql+asyncpg://${aws_db_instance.main.username}:${var.db_password}@${aws_db_instance.main.endpoint}/${aws_db_instance.main.db_name}"
    jwt_secret       = var.jwt_secret
    ai_api_key       = var.ai_api_key != null ? var.ai_api_key : ""
    media_secret_key = aws_iam_access_key.media.secret
  })
}

# --- outputs ------------------------------------------------------------------
output "api_url" {
  value = "https://api.${var.domain}"
}

output "web_url" {
  value = var.environment == "prod" ? "https://${var.domain}" : "https://web.${var.domain}"
}

output "ecs_cluster" {
  value = aws_ecs_cluster.main.name
}