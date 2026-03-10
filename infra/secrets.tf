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