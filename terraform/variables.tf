variable "app_name" {
  description = "Prefix used for all resource names."
  type        = string
  default     = "sh4r3d"
}

variable "aws_region" {
  description = "AWS region for all resources."
  type        = string
  default     = "us-east-1"
}

variable "secret_key" {
  description = "Secret key used to sign session cookies. Must be set."
  type        = string
  sensitive   = true
}

variable "beta_mode" {
  description = "Set to 'true' to enable the invite-token gate."
  type        = string
  default     = "false"
}

variable "domain" {
  description = "Primary domain name for the app (e.g. example.com). CloudFront and ACM will be configured for this domain and www.<domain>."
  type        = string
}

variable "budget_alert_email" {
  description = "Email address to receive monthly budget alarm notifications."
  type        = string
}
