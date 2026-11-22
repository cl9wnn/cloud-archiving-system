resource "yandex_message_queue" "failed" {
  name                      = "${local.prefix}failed"
  access_key                = yandex_iam_service_account_static_access_key.provisioner.access_key
  secret_key                = yandex_iam_service_account_static_access_key.provisioner.secret_key
  message_retention_seconds = 14 * 86400
}

resource "yandex_message_queue" "tasks" {
  name                       = "${local.prefix}tasks"
  access_key                 = yandex_iam_service_account_static_access_key.provisioner.access_key
  secret_key                 = yandex_iam_service_account_static_access_key.provisioner.secret_key
  message_retention_seconds  = 86400
  visibility_timeout_seconds = 900
  receive_wait_time_seconds  = 20

  redrive_policy = jsonencode({
    deadLetterTargetArn = yandex_message_queue.failed.arn
    maxReceiveCount     = 1
  })
}
