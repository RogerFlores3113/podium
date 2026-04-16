resource "aws_ssm_parameter" "openai_api_key" {
  name  = "/${var.project_name}/openai-api-key"
  type  = "SecureString"
  value = var.openai_api_key

  tags = {
    Name = "${var.project_name}-openai-key"
  }
}

resource "aws_ssm_parameter" "db_password" {
  name  = "/${var.project_name}/db-password"
  type  = "SecureString"
  value = var.db_password

  tags = {
    Name = "${var.project_name}-db-password"
  }
}

resource "aws_ssm_parameter" "clerk_secret_key" {
  name  = "/${var.project_name}/clerk-secret-key"
  type  = "SecureString"
  value = var.clerk_secret_key

  tags = {
    Name = "${var.project_name}-clerk-secret-key"
  }
}

resource "aws_ssm_parameter" "tavily_api_key" {
  name  = "/${var.project_name}/tavily-api-key"
  type  = "SecureString"
  value = var.tavily_api_key

  tags = {
    Name = "${var.project_name}-tavily-api-key"
  }
}

resource "aws_ssm_parameter" "e2b_api_key" {
  name  = "/${var.project_name}/e2b-api-key"
  type  = "SecureString"
  value = var.e2b_api_key

  tags = {
    Name = "${var.project_name}-e2b-api-key"
  }
}
