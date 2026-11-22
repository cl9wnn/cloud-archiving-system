data "archive_file" "worker" {
  type        = "zip"
  source_dir  = "${path.module}/function"
  output_path = "${path.module}/.build/worker.zip"
  excludes    = ["__pycache__"]
}

resource "yandex_function" "worker" {
  name               = "${local.prefix}archiver"
  runtime            = "python312"
  entrypoint         = "main.handler"
  memory             = 256
  execution_timeout  = "600"
  user_hash          = data.archive_file.worker.output_base64sha256
  service_account_id = yandex_iam_service_account.service["worker"].id

  content {
    zip_filename = data.archive_file.worker.output_path
  }

  environment = {
    BUCKET_NAME       = yandex_storage_bucket.archives.bucket
    DOCUMENT_ENDPOINT = yandex_ydb_database_serverless.main.document_api_endpoint
    TABLE_NAME        = aws_dynamodb_table.archives.name
  }
}

resource "yandex_function_trigger" "tasks" {
  name = "${local.prefix}on-task"

  message_queue {
    queue_id           = yandex_message_queue.tasks.arn
    service_account_id = yandex_iam_service_account.service["trigger"].id
    batch_size         = "1"
    batch_cutoff       = "0"
  }

  function {
    id                 = yandex_function.worker.id
    service_account_id = yandex_iam_service_account.service["trigger"].id
  }
}
