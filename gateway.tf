resource "yandex_api_gateway" "main" {
  name = "${local.prefix}api"
  spec = templatefile("${path.module}/openapi.yaml", {
    gateway_account = yandex_iam_service_account.service["gateway"].id
    folder_id       = var.folder_id
    queue_url       = yandex_message_queue.tasks.id
    database        = yandex_ydb_database_serverless.main.database_path
    table_name      = aws_dynamodb_table.archives.name
    bucket          = yandex_storage_bucket.archives.bucket
  })
}

output "api_url" {
  description = "Public HTTPS entry point for the archiving API."
  value       = "https://${yandex_api_gateway.main.domain}"
}
