data "aws_ami" "amazon_linux_2023_arm" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-*-arm64"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

resource "aws_security_group" "valkey" {
  name        = "${var.project_name}-valkey-sg"
  description = "Valkey: inbound from ECS only, outbound for package install"
  vpc_id      = aws_vpc.main.id

  ingress {
    description     = "Redis/Valkey from ECS"
    from_port       = 6379
    to_port         = 6379
    protocol        = "tcp"
    security_groups = [aws_security_group.ecs.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.project_name}-valkey-sg"
  }
}

resource "aws_instance" "valkey" {
  ami                    = data.aws_ami.amazon_linux_2023_arm.id
  instance_type          = "t4g.nano"
  subnet_id              = aws_subnet.public[0].id
  vpc_security_group_ids = [aws_security_group.valkey.id]

  # Public IP needed only for outbound package install (no inbound traffic accepted)
  associate_public_ip_address = true

  user_data = <<-EOF
    #!/bin/bash
    dnf install -y valkey
    systemctl enable valkey
    # Bind to all interfaces so ECS tasks can reach it over the VPC
    sed -i 's/^bind 127\.0\.0\.1.*/bind 0.0.0.0/' /etc/valkey/valkey.conf
    sed -i 's/^protected-mode yes/protected-mode no/' /etc/valkey/valkey.conf
    systemctl start valkey
  EOF

  tags = {
    Name = "${var.project_name}-valkey"
  }
}
