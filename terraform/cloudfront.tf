# CloudFront Function: rewrite clean URLs to S3 object keys
resource "aws_cloudfront_function" "url_rewrite" {
  name    = "${var.app_name}-url-rewrite"
  runtime = "cloudfront-js-2.0"
  publish = true

  code = <<-EOF
    function handler(event) {
      var request = event.request;
      var uri = request.uri;

      // Pass through known static assets unchanged
      if (uri === '/style.css' ||
          uri === '/index.html' ||
          uri === '/auth.html' ||
          uri === '/share.html' ||
          uri === '/404.html' ||
          uri === '/privacy.html' ||
          uri === '/robots.txt') {
        return request;
      }

      // Clean URL mappings
      if (uri === '/' || uri === '') {
        request.uri = '/index.html';
      } else if (uri === '/auth') {
        request.uri = '/auth.html';
      } else if (uri === '/privacy') {
        request.uri = '/privacy.html';
      } else {
        // Any other single-segment path is a slug → serve share.html
        // The JS on share.html reads the slug from window.location.pathname
        request.uri = '/share.html';
      }

      return request;
    }
  EOF
}

resource "aws_cloudfront_distribution" "main" {
  enabled             = true
  default_root_object = "index.html"
  price_class         = "PriceClass_100"  # US + Europe only (cheapest)
  aliases             = [var.domain, "www.${var.domain}"]

  # Origin 1: S3 bucket (static HTML/CSS)
  origin {
    domain_name              = aws_s3_bucket.main.bucket_regional_domain_name
    origin_id                = "S3"
    origin_access_control_id = aws_cloudfront_origin_access_control.main.id
  }

  # Origin 2: API Gateway (Lambda-backed API)
  origin {
    # invoke_url is "https://id.execute-api.region.amazonaws.com/" — strip scheme and trailing slash
    domain_name = trimprefix(trimsuffix(aws_apigatewayv2_stage.default.invoke_url, "/"), "https://")
    origin_id   = "API"

    custom_origin_config {
      http_port              = 80
      https_port             = 443
      origin_protocol_policy = "https-only"
      origin_ssl_protocols   = ["TLSv1.2"]
    }
  }

  # Default: serve static files from S3 with URL rewriting
  default_cache_behavior {
    allowed_methods        = ["GET", "HEAD"]
    cached_methods         = ["GET", "HEAD"]
    target_origin_id       = "S3"
    viewer_protocol_policy = "redirect-to-https"

    # Managed CachingOptimized policy
    cache_policy_id = "658327ea-f89d-4fab-a63d-7e88639e58f6"

    function_association {
      event_type   = "viewer-request"
      function_arn = aws_cloudfront_function.url_rewrite.arn
    }
  }

  # /api/* → API Gateway (no caching, forward all headers + cookies)
  ordered_cache_behavior {
    path_pattern           = "/api/*"
    allowed_methods        = ["DELETE", "GET", "HEAD", "OPTIONS", "PATCH", "POST", "PUT"]
    cached_methods         = ["GET", "HEAD"]
    target_origin_id       = "API"
    viewer_protocol_policy = "redirect-to-https"

    # Managed CachingDisabled policy
    cache_policy_id = "4135ea2d-6df8-44a3-9df3-4b5a84be39ad"

    # Managed AllViewerExceptHostHeader — forwards cookies, headers, query strings
    origin_request_policy_id = "b689b0a8-53d0-40ab-baf2-68738e2966ac"
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    acm_certificate_arn      = aws_acm_certificate_validation.main.certificate_arn
    ssl_support_method       = "sni-only"
    minimum_protocol_version = "TLSv1.2_2021"
  }
}
