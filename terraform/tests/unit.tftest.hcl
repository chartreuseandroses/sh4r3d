# Terraform unit tests — run with: cd terraform && terraform test
#
# Uses mock providers so no real AWS credentials or API calls are needed.
# Requires Terraform >= 1.6.

mock_provider "aws" {}
mock_provider "archive" {}
mock_provider "random" {}
mock_provider "null" {}

variables {
  secret_key = "test-secret-key-for-unit-tests"
  domain     = "test.example.com"
}

# ---------------------------------------------------------------------------
# DynamoDB
# ---------------------------------------------------------------------------

run "dynamodb_all_tables_use_on_demand_billing" {
  command = plan

  assert {
    condition     = aws_dynamodb_table.tokens.billing_mode == "PAY_PER_REQUEST"
    error_message = "Tokens table must use PAY_PER_REQUEST billing"
  }
  assert {
    condition     = aws_dynamodb_table.slugs.billing_mode == "PAY_PER_REQUEST"
    error_message = "Slugs table must use PAY_PER_REQUEST billing"
  }
  assert {
    condition     = aws_dynamodb_table.files.billing_mode == "PAY_PER_REQUEST"
    error_message = "Files table must use PAY_PER_REQUEST billing"
  }
}

run "dynamodb_ttl_enabled_on_slugs_and_files" {
  command = plan

  assert {
    condition     = one(aws_dynamodb_table.slugs.ttl).enabled
    error_message = "Slugs table must have TTL enabled"
  }
  assert {
    condition     = one(aws_dynamodb_table.slugs.ttl).attribute_name == "ttl"
    error_message = "Slugs table TTL attribute must be named 'ttl'"
  }
  assert {
    condition     = one(aws_dynamodb_table.files.ttl).enabled
    error_message = "Files table must have TTL enabled"
  }
  assert {
    condition     = one(aws_dynamodb_table.files.ttl).attribute_name == "ttl"
    error_message = "Files table TTL attribute must be named 'ttl'"
  }
}

run "dynamodb_files_table_has_slug_index_gsi" {
  command = plan

  assert {
    condition = anytrue([
      for gsi in aws_dynamodb_table.files.global_secondary_index : gsi.name == "slug-index"
    ])
    error_message = "Files table must have a GSI named 'slug-index'"
  }
}

# ---------------------------------------------------------------------------
# Lambda
# ---------------------------------------------------------------------------

run "lambda_both_use_python312" {
  command = plan

  assert {
    condition     = aws_lambda_function.api.runtime == "python3.12"
    error_message = "API Lambda must use python3.12 runtime"
  }
  assert {
    condition     = aws_lambda_function.cleanup.runtime == "python3.12"
    error_message = "Cleanup Lambda must use python3.12 runtime"
  }
}

run "lambda_timeouts_are_correct" {
  command = plan

  assert {
    condition     = aws_lambda_function.api.timeout == 30
    error_message = "API Lambda timeout must be 30 seconds"
  }
  assert {
    condition     = aws_lambda_function.cleanup.timeout == 300
    error_message = "Cleanup Lambda timeout must be 300 seconds (5 minutes)"
  }
}

run "lambda_memory_is_correct" {
  command = plan

  assert {
    condition     = aws_lambda_function.api.memory_size == 512
    error_message = "API Lambda must have 512 MB memory"
  }
  assert {
    condition     = aws_lambda_function.cleanup.memory_size == 256
    error_message = "Cleanup Lambda must have 256 MB memory"
  }
}

run "lambda_handlers_are_correct" {
  command = plan

  assert {
    condition     = aws_lambda_function.api.handler == "app.lambda_handler.handler"
    error_message = "API Lambda handler must be app.lambda_handler.handler"
  }
  assert {
    condition     = aws_lambda_function.cleanup.handler == "app.services.cleanup_service.lambda_handler"
    error_message = "Cleanup Lambda handler must be app.services.cleanup_service.lambda_handler"
  }
}

# ---------------------------------------------------------------------------
# CloudFront
# ---------------------------------------------------------------------------

run "cloudfront_uses_cheapest_price_class" {
  command = plan

  assert {
    condition     = aws_cloudfront_distribution.main.price_class == "PriceClass_100"
    error_message = "CloudFront must use PriceClass_100 (US + Europe, cheapest tier)"
  }
}

run "cloudfront_enforces_tls12" {
  command = plan

  assert {
    condition     = one(aws_cloudfront_distribution.main.viewer_certificate).minimum_protocol_version == "TLSv1.2_2021"
    error_message = "CloudFront must enforce TLSv1.2_2021 as minimum protocol"
  }
  assert {
    condition     = one(aws_cloudfront_distribution.main.viewer_certificate).ssl_support_method == "sni-only"
    error_message = "CloudFront must use sni-only SSL support"
  }
}

run "cloudfront_aliases_include_both_domains" {
  command = plan

  assert {
    condition     = contains(tolist(aws_cloudfront_distribution.main.aliases), var.domain)
    error_message = "CloudFront aliases must include the configured domain"
  }
  assert {
    condition     = contains(tolist(aws_cloudfront_distribution.main.aliases), "www.${var.domain}")
    error_message = "CloudFront aliases must include the www subdomain"
  }
}

run "cloudfront_is_enabled" {
  command = plan

  assert {
    condition     = aws_cloudfront_distribution.main.enabled
    error_message = "CloudFront distribution must be enabled"
  }
}

# ---------------------------------------------------------------------------
# S3
# ---------------------------------------------------------------------------

run "s3_all_public_access_blocked" {
  command = plan

  assert {
    condition     = aws_s3_bucket_public_access_block.main.block_public_acls
    error_message = "S3 must block public ACLs"
  }
  assert {
    condition     = aws_s3_bucket_public_access_block.main.block_public_policy
    error_message = "S3 must block public bucket policies"
  }
  assert {
    condition     = aws_s3_bucket_public_access_block.main.ignore_public_acls
    error_message = "S3 must ignore public ACLs"
  }
  assert {
    condition     = aws_s3_bucket_public_access_block.main.restrict_public_buckets
    error_message = "S3 must restrict public bucket access"
  }
}

run "s3_lifecycle_targets_uploads_prefix" {
  command = plan

  assert {
    condition = anytrue([
      for rule in aws_s3_bucket_lifecycle_configuration.main.rule :
      rule.status == "Enabled" && anytrue([
        for f in rule.filter : f.prefix == "uploads/"
      ])
    ])
    error_message = "S3 must have an enabled lifecycle rule targeting the uploads/ prefix"
  }
}

run "s3_lifecycle_expires_after_2_days" {
  command = plan

  assert {
    condition = anytrue([
      for rule in aws_s3_bucket_lifecycle_configuration.main.rule :
      anytrue([for exp in rule.expiration : exp.days == 2])
    ])
    error_message = "S3 lifecycle rule must expire objects after 2 days"
  }
}

# ---------------------------------------------------------------------------
# ACM certificate
# ---------------------------------------------------------------------------

run "acm_certificate_covers_correct_domains" {
  command = plan

  assert {
    condition     = aws_acm_certificate.main.domain_name == var.domain
    error_message = "ACM certificate primary domain must match var.domain"
  }
  assert {
    condition     = contains(tolist(aws_acm_certificate.main.subject_alternative_names), "www.${var.domain}")
    error_message = "ACM certificate must include the www subdomain as a SAN"
  }
  assert {
    condition     = aws_acm_certificate.main.validation_method == "DNS"
    error_message = "ACM certificate must use DNS validation"
  }
}

# ---------------------------------------------------------------------------
# API Gateway
# ---------------------------------------------------------------------------

run "api_gateway_uses_http_protocol" {
  command = plan

  assert {
    condition     = aws_apigatewayv2_api.main.protocol_type == "HTTP"
    error_message = "API Gateway must use the HTTP protocol type"
  }
}

# ---------------------------------------------------------------------------
# EventBridge
# ---------------------------------------------------------------------------

run "cleanup_runs_every_5_minutes" {
  command = plan

  assert {
    condition     = aws_cloudwatch_event_rule.cleanup.schedule_expression == "rate(5 minutes)"
    error_message = "Cleanup EventBridge rule must be scheduled every 5 minutes"
  }
}
