variable "project_name" {
  description = "Project name used for resource naming"
  type        = string
}

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "db_username" {
  description = "RDS master username"
  type        = string
  default     = "assistant"
}

variable "db_password" {
  description = "RDS master password"
  type        = string
  sensitive   = true
}

variable "openai_api_key" {
  description = "OpenAI API key"
  type        = string
  sensitive   = true
}

variable "domain_name" {
  description = "Domain name for the API (optional, leave empty to skip HTTPS)"
  type        = string
  default     = ""
}

variable "aws_email" {
  description = "Email for AWS"
  type        = string
  default     = ""
}

variable "clerk_secret_key" {
  description = "Clerk secret key"
  type        = string
  sensitive   = true
}

variable "clerk_jwks_url" {
  description = "Clerk JWKS URL for JWT verification"
  type        = string
}

variable "tavily_api_key" {
  description = "Tavily API key for web search"
  type        = string
  sensitive   = true
}

variable "e2b_api_key" {
  description = "E2B API key for code interpreter sandboxes"
  type        = string
  sensitive   = true
}