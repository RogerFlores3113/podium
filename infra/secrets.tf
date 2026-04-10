resource "aws_secretsmanager_secret" "openai_api_key" {
  name                    = "${var.project_name}/openai-api-key"
  recovery_window_in_days = 0 # Allow immediate deletion for dev

  tags = {
    Name = "${var.project_name}-openai-key"
  }
}

resource "aws_secretsmanager_secret_version" "openai_api_key" {
  secret_id     = aws_secretsmanager_secret.openai_api_key.id
  secret_string = var.openai_api_key
}

resource "aws_secretsmanager_secret" "db_password" {
  name                    = "${var.project_name}/db-password"
  recovery_window_in_days = 0

  tags = {
    Name = "${var.project_name}-db-password"
  }
}

resource "aws_secretsmanager_secret_version" "db_password" {
  secret_id     = aws_secretsmanager_secret.db_password.id
  secret_string = var.db_password
}

resource "aws_secretsmanager_secret" "clerk_secret_key" {
  name                    = "${var.project_name}/clerk-secret-key"
  recovery_window_in_days = 0

  tags = {
    Name = "${var.project_name}-clerk-secret-key"
  }
}

resource "aws_secretsmanager_secret_version" "clerk_secret_key" {
  secret_id     = aws_secretsmanager_secret.clerk_secret_key.id
  secret_string = var.clerk_secret_key
}

resource "aws_secretsmanager_secret" "tavily_api_key" {
  name                    = "${var.project_name}/tavily-api-key"
  recovery_window_in_days = 0

  tags = {
    Name = "${var.project_name}-tavily-api-key"
  }
}

resource "aws_secretsmanager_secret_version" "tavily_api_key" {
  secret_id     = aws_secretsmanager_secret.tavily_api_key.id
  secret_string = var.tavily_api_key
}

resource "aws_secretsmanager_secret" "e2b_api_key" {
  name                    = "${var.project_name}/e2b-api-key"
  recovery_window_in_days = 0

  tags = {
    Name = "${var.project_name}-e2b-api-key"
  }
}

resource "aws_secretsmanager_secret_version" "e2b_api_key" {
  secret_id     = aws_secretsmanager_secret.e2b_api_key.id
  secret_string = var.e2b_api_key
}