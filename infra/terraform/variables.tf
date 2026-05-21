variable "project" {
  type        = string
  description = "Project name used for resource naming."
  default     = "logiq"
}

variable "region" {
  type        = string
  description = "AWS region."
  default     = "us-east-1"
}

variable "environment" {
  type        = string
  description = "Deployment environment."
  default     = "production"
}

variable "vpc_cidr" {
  type        = string
  description = "VPC CIDR block."
  default     = "10.42.0.0/16"
}

variable "database_instance_class" {
  type        = string
  description = "RDS instance class."
  default     = "db.t4g.medium"
}

