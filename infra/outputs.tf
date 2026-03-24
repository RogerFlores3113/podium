# Purely display. helps find keys and information after terraform apply. Can also run "terraform output OUTPUTNAME" in console.
output "alb_dns_name" {
  description = "DNS name of the load balancer (your API URL)"
  value       = aws_lb.main.dns_name
}

output "ecr_repository_url" {
  description = "ECR repository URL for pushing Docker images"
  value       = aws_ecr_repository.app.repository_url
}

output "s3_bucket_name" {
  description = "S3 bucket for document uploads"
  value       = aws_s3_bucket.uploads.id
}

output "rds_endpoint" {
  description = "RDS database endpoint"
  value       = aws_db_instance.main.endpoint
}

output "kms_key_id" {
  description = "KMS key ID for encrypting user API keys"
  value       = aws_kms_key.user_keys.key_id
}