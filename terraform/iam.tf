resource "aws_iam_role" "api_lambda" {
  name = "${var.app_name}-api-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy" "api_lambda" {
  name = "${var.app_name}-api-lambda-policy"
  role = aws_iam_role.api_lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "Logs"
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents",
        ]
        Resource = "arn:aws:logs:*:*:*"
      },
      {
        Sid    = "DynamoDB"
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:UpdateItem",
          "dynamodb:DeleteItem",
          "dynamodb:Query",
        ]
        Resource = [
          aws_dynamodb_table.tokens.arn,
          aws_dynamodb_table.slugs.arn,
          aws_dynamodb_table.files.arn,
          "${aws_dynamodb_table.files.arn}/index/*",
          aws_dynamodb_table.notes.arn,
          "${aws_dynamodb_table.notes.arn}/index/*",
        ]
      },
      {
        Sid    = "S3Uploads"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:HeadObject",
        ]
        Resource = "${aws_s3_bucket.main.arn}/uploads/*"
      },
    ]
  })
}

resource "aws_iam_role" "cleanup_lambda" {
  name = "${var.app_name}-cleanup-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy" "cleanup_lambda" {
  name = "${var.app_name}-cleanup-lambda-policy"
  role = aws_iam_role.cleanup_lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "Logs"
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents",
        ]
        Resource = "arn:aws:logs:*:*:*"
      },
      {
        Sid    = "DynamoDB"
        Effect = "Allow"
        Action = [
          "dynamodb:Scan",
          "dynamodb:DeleteItem",
        ]
        Resource = [
          aws_dynamodb_table.slugs.arn,
          aws_dynamodb_table.files.arn,
          aws_dynamodb_table.notes.arn,
        ]
      },
      {
        Sid    = "S3Uploads"
        Effect = "Allow"
        Action = [
          "s3:DeleteObject",
        ]
        Resource = "${aws_s3_bucket.main.arn}/uploads/*"
      },
    ]
  })
}
