resource "aws_ecs_cluster" "main" {
  name = "${var.project_name}-cluster"

  setting {
    name  = "containerInsights"
    value = "disabled" # Enable later if you want detailed metrics ($$$)
  }

  tags = {
    Name = "${var.project_name}-cluster"
  }
}

# CloudWatch log group for container logs
resource "aws_cloudwatch_log_group" "app" {
  name              = "/ecs/${var.project_name}"
  retention_in_days = 14

  tags = {
    Name = "${var.project_name}-logs"
  }
}

# Construct the DATABASE_URL from RDS outputs
locals {
  database_url = "postgresql+asyncpg://${var.db_username}:${var.db_password}@${aws_db_instance.main.endpoint}/assistant"
  redis_url    = "redis://${aws_elasticache_cluster.main.cache_nodes[0].address}:6379"
}

# --- API Service ---

resource "aws_ecs_task_definition" "app" {
  family                   = "${var.project_name}-app"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "512"
  memory                   = "1024"
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([
    {
      name  = "app"
      image = "${aws_ecr_repository.app.repository_url}:latest"

      portMappings = [
        {
          containerPort = 8000
          protocol      = "tcp"
        }
      ]

      environment = [
        { name = "DATABASE_URL", value = local.database_url },
        { name = "REDIS_URL", value = local.redis_url },
        { name = "S3_BUCKET_NAME", value = aws_s3_bucket.uploads.id },
        { name = "AWS_DEFAULT_REGION", value = var.aws_region },
        { name = "KMS_KEY_ID", value = aws_kms_key.user_keys.key_id },
        { name = "CLERK_JWKS_URL", value = var.clerk_jwks_url },
        { name = "KMS_KEY_ID", value = aws_kms_key.user_keys.key_id },
      ]

      secrets = [
        {
          name      = "OPENAI_API_KEY"
          valueFrom = aws_secretsmanager_secret.openai_api_key.arn
        },
        {
          name      = "CLERK_SECRET_KEY"
          valueFrom = aws_secretsmanager_secret.clerk_secret_key.arn
        },
        {
          name      = "TAVILY_API_KEY"
          valueFrom = aws_secretsmanager_secret.tavily_api_key.arn
        },
        {
          name      = "E2B_API_KEY"
          valueFrom = aws_secretsmanager_secret.e2b_api_key.arn
        }
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.app.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "app"
        }
      }

      healthCheck = {
        command     = ["CMD-SHELL", "curl -f http://localhost:8000/health || exit 1"]
        interval    = 30
        timeout     = 5
        retries     = 3
        startPeriod = 60
      }
    }
  ])
}

resource "aws_ecs_service" "app" {
  name            = "${var.project_name}-app"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.app.arn
  desired_count   = 1
  launch_type     = "FARGATE"
  enable_execute_command = true

  network_configuration {
    subnets          = aws_subnet.private[*].id
    security_groups  = [aws_security_group.ecs.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.app.arn
    container_name   = "app"
    container_port   = 8000
  }

  # Allow service to stabilize before marking unhealthy
  health_check_grace_period_seconds = 120

  # Force new deployment when task definition changes
  force_new_deployment = true

  depends_on = [aws_lb_listener.http]
}

# --- Worker Service ---

resource "aws_ecs_task_definition" "worker" {
  family                   = "${var.project_name}-worker"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "512"
  memory                   = "1024"
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([
    {
      name    = "worker"
      image   = "${aws_ecr_repository.app.repository_url}:latest"
      command = ["uv", "run", "arq", "app.services.worker.WorkerSettings"]

      environment = [
        { name = "DATABASE_URL", value = local.database_url },
        { name = "REDIS_URL", value = local.redis_url },
        { name = "S3_BUCKET_NAME", value = aws_s3_bucket.uploads.id },
        { name = "AWS_DEFAULT_REGION", value = var.aws_region },
        { name = "KMS_KEY_ID", value = aws_kms_key.user_keys.key_id },
        { name = "CLERK_JWKS_URL", value = var.clerk_jwks_url },
        { name = "KMS_KEY_ID", value = aws_kms_key.user_keys.key_id },
      ]

      secrets = [
        {  
          name      = "OPENAI_API_KEY"
          valueFrom = aws_secretsmanager_secret.openai_api_key.arn
        },
        {
          name      = "CLERK_SECRET_KEY"
          valueFrom = aws_secretsmanager_secret.clerk_secret_key.arn
        },
        {
          name      = "TAVILY_API_KEY"
          valueFrom = aws_secretsmanager_secret.tavily_api_key.arn
        },
        {
          name      = "E2B_API_KEY"
          valueFrom = aws_secretsmanager_secret.e2b_api_key.arn
        }
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.app.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "worker"
        }
      }
    }
  ])
}

resource "aws_ecs_service" "worker" {
  name            = "${var.project_name}-worker"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.worker.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = aws_subnet.private[*].id
    security_groups  = [aws_security_group.ecs.id]
    assign_public_ip = false
  }

  force_new_deployment = true
}