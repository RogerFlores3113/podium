# create KMS master key, for encrypting and deciphering API tokens. Stored in AWS, never leaves.
resource "aws_kms_key" "user_keys" {
    description = "Encrypt user API keys"
    deletion_window_in_days = 7
    enable_key_rotation = true 

    tags = {
      Name = "${var.project_name}-user-keys"
    }
}

# Human-accessible way of accessing the master key. not technically neccessary but easier than uid access.
resource "aws_kms_alias" "user_keys" {
    name = "alias/${var.project_name}-user-keys"
    target_key_id = aws_kms_key.user_keys.key_id 
}