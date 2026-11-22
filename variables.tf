variable "cloud_id" {
  description = "Yandex Cloud cloud ID."
  type        = string
}

variable "folder_id" {
  description = "Folder in which to create the archiving service."
  type        = string
}

variable "bucket_name" {
  description = "Globally unique name for the private archive bucket."
  type        = string

  validation {
    condition     = can(regex("^vvot27-[a-z0-9-]*[a-z0-9]$", var.bucket_name)) && length(var.bucket_name) <= 63
    error_message = "Use a bucket name starting with vvot27-, up to 63 lowercase letters, digits or hyphens."
  }
}
