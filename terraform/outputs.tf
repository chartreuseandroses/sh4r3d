output "cloudfront_url" {
  description = "The public URL of the app (use this as your domain)."
  value       = "https://${aws_cloudfront_distribution.main.domain_name}"
}

output "acm_dns_validation_records" {
  description = "Add these CNAME records to Cloudflare DNS to validate the ACM certificate."
  value = {
    for dvo in aws_acm_certificate.main.domain_validation_options : dvo.domain_name => {
      name  = dvo.resource_record_name
      value = dvo.resource_record_value
    }
  }
}

output "api_gateway_url" {
  description = "Direct API Gateway URL (bypasses CloudFront — for debugging only)."
  value       = aws_apigatewayv2_stage.default.invoke_url
}

output "s3_bucket_name" {
  description = "Name of the S3 bucket used for static files and uploads."
  value       = aws_s3_bucket.main.id
}
