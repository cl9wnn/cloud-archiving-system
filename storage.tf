resource "yandex_storage_bucket" "archives" {
  bucket        = var.bucket_name
  access_key    = yandex_iam_service_account_static_access_key.provisioner.access_key
  secret_key    = yandex_iam_service_account_static_access_key.provisioner.secret_key
  max_size      = 10 * 1024 * 1024 * 1024
  force_destroy = true

  anonymous_access_flags {
    read        = false
    list        = false
    config_read = false
  }
}

resource "yandex_ydb_database_serverless" "main" {
  name = "${local.prefix}archives"

  serverless_database {
    enable_throttling_rcu_limit = true
    throttling_rcu_limit        = 10
    storage_size_limit          = 1 # GiB in the Yandex Terraform provider
  }
}

resource "aws_dynamodb_table" "archives" {
  name         = "archives"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "key"

  attribute {
    name = "key"
    type = "S"
  }
}
