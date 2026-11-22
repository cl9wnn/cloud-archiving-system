locals {
  prefix = "vvot27-"
  roles = {
    gateway     = ["ymq.writer", "ydb.viewer", "storage.viewer"]
    worker      = ["storage.uploader", "ydb.editor"]
    trigger     = ["ymq.reader", "functions.functionInvoker"]
    provisioner = ["ymq.admin", "ydb.editor", "storage.admin"]
  }
  grants = merge([
    for account, roles in local.roles : {
      for role in roles : "${account}/${role}" => { account = account, role = role }
    }
  ]...)
}

resource "yandex_iam_service_account" "service" {
  for_each = local.roles
  name     = "${local.prefix}${each.key}"
}

resource "yandex_resourcemanager_folder_iam_member" "grant" {
  for_each  = local.grants
  folder_id = var.folder_id
  role      = each.value.role
  member    = "serviceAccount:${yandex_iam_service_account.service[each.value.account].id}"
}

resource "yandex_iam_service_account_static_access_key" "provisioner" {
  service_account_id = yandex_iam_service_account.service["provisioner"].id
  description        = "Terraform access to S3-compatible, SQS-compatible and Document APIs"

  depends_on = [yandex_resourcemanager_folder_iam_member.grant]
}
