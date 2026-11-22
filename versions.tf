terraform {
  required_version = ">= 1.5, < 2.0"

  required_providers {
    yandex = {
      source  = "yandex-cloud/yandex"
      version = "~> 0.243.0"
    }
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.100.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.7"
    }
  }
}

provider "yandex" {
  cloud_id  = var.cloud_id
  folder_id = var.folder_id
}

# Only the YDB Document API uses the DynamoDB-compatible provider.
provider "aws" {
  region                      = "ru-central1"
  access_key                  = yandex_iam_service_account_static_access_key.provisioner.access_key
  secret_key                  = yandex_iam_service_account_static_access_key.provisioner.secret_key
  skip_credentials_validation = true
  skip_requesting_account_id  = true
  skip_metadata_api_check     = true
  skip_region_validation      = true

  endpoints {
    dynamodb = yandex_ydb_database_serverless.main.document_api_endpoint
  }
}
