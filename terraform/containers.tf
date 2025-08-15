resource "aws_ecr_repository" "client_image" {
  for_each = local.clientData
  name     = "${each.key}-image"
}

data "aws_ecr_image" "shared" {
  repository_name = aws_ecr_repository.client_image["rearc"].id
  image_tag       = var.shared_image_tag
}

output "rearc_image_repo_url" {
  value = aws_ecr_repository.client_image["rearc"].repository_url
}
