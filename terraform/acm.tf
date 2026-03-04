# ACM certificate — must be in us-east-1 for CloudFront (already our region)
resource "aws_acm_certificate" "main" {
  domain_name               = var.domain
  subject_alternative_names = ["www.${var.domain}"]
  validation_method         = "DNS"

  lifecycle {
    create_before_destroy = true
  }
}

# Blocks until ACM confirms the certificate is issued.
# Add the CNAME records from the acm_dns_validation_records output to Cloudflare first.
resource "aws_acm_certificate_validation" "main" {
  certificate_arn = aws_acm_certificate.main.arn
}
