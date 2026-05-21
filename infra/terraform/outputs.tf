output "vpc_id" {
  value       = aws_vpc.this.id
  description = "VPC ID."
}

output "private_subnet_ids" {
  value       = aws_subnet.private[*].id
  description = "Private subnet IDs for Kubernetes nodes."
}

output "database_endpoint" {
  value       = aws_db_instance.postgres.address
  description = "PostgreSQL endpoint."
}

output "eks_cluster_name" {
  value       = aws_eks_cluster.this.name
  description = "EKS cluster name."
}
