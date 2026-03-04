resource "random_id" "bucket_suffix" {
  byte_length = 4
}

locals {
  bucket_name = "${var.app_name}-${random_id.bucket_suffix.hex}"
}

resource "aws_s3_bucket" "main" {
  bucket = local.bucket_name
}

# Block all public access — CloudFront uses OAC, not public URLs
resource "aws_s3_bucket_public_access_block" "main" {
  bucket = aws_s3_bucket.main.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# CORS: allow browsers to PUT directly to S3 via presigned URLs
resource "aws_s3_bucket_cors_configuration" "main" {
  bucket = aws_s3_bucket.main.id

  cors_rule {
    allowed_headers = ["*"]
    allowed_methods = ["PUT", "GET", "HEAD"]
    allowed_origins = ["*"]
    expose_headers  = ["ETag"]
    max_age_seconds = 3000
  }
}

# Lifecycle: auto-delete uploaded files after 2 days
resource "aws_s3_bucket_lifecycle_configuration" "main" {
  bucket = aws_s3_bucket.main.id

  rule {
    id     = "expire-uploads"
    status = "Enabled"

    filter {
      prefix = "uploads/"
    }

    expiration {
      days = 2
    }
  }
}

# CloudFront Origin Access Control — only CloudFront can read S3 objects
resource "aws_cloudfront_origin_access_control" "main" {
  name                              = "${var.app_name}-oac"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

# Bucket policy: allow CloudFront OAC to read all objects
resource "aws_s3_bucket_policy" "main" {
  bucket = aws_s3_bucket.main.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid    = "AllowCloudFrontOAC"
      Effect = "Allow"
      Principal = { Service = "cloudfront.amazonaws.com" }
      Action   = "s3:GetObject"
      Resource = "${aws_s3_bucket.main.arn}/*"
      Condition = {
        StringEquals = {
          "AWS:SourceArn" = aws_cloudfront_distribution.main.arn
        }
      }
    }]
  })

  depends_on = [aws_cloudfront_distribution.main]
}

# ---------------------------------------------------------------------------
# Static frontend files
# ---------------------------------------------------------------------------

resource "aws_s3_object" "style" {
  bucket       = aws_s3_bucket.main.id
  key          = "style.css"
  source       = "${path.module}/../static/style.css"
  content_type = "text/css"
  etag         = filemd5("${path.module}/../static/style.css")
}

resource "aws_s3_object" "index_html" {
  bucket       = aws_s3_bucket.main.id
  key          = "index.html"
  content      = templatefile("${path.module}/../static/index.html", { domain = var.domain })
  content_type = "text/html"
  etag         = md5(templatefile("${path.module}/../static/index.html", { domain = var.domain }))
}

resource "aws_s3_object" "auth_html" {
  bucket       = aws_s3_bucket.main.id
  key          = "auth.html"
  source       = "${path.module}/../static/auth.html"
  content_type = "text/html"
  etag         = filemd5("${path.module}/../static/auth.html")
}

resource "aws_s3_object" "share_html" {
  bucket       = aws_s3_bucket.main.id
  key          = "share.html"
  source       = "${path.module}/../static/share.html"
  content_type = "text/html"
  etag         = filemd5("${path.module}/../static/share.html")
}

resource "aws_s3_object" "not_found_html" {
  bucket       = aws_s3_bucket.main.id
  key          = "404.html"
  source       = "${path.module}/../static/404.html"
  content_type = "text/html"
  etag         = filemd5("${path.module}/../static/404.html")
}

resource "aws_s3_object" "privacy_html" {
  bucket       = aws_s3_bucket.main.id
  key          = "privacy.html"
  source       = "${path.module}/../static/privacy.html"
  content_type = "text/html"
  etag         = filemd5("${path.module}/../static/privacy.html")
}

resource "aws_s3_object" "robots_txt" {
  bucket       = aws_s3_bucket.main.id
  key          = "robots.txt"
  source       = "${path.module}/../static/robots.txt"
  content_type = "text/plain"
  etag         = filemd5("${path.module}/../static/robots.txt")
}
