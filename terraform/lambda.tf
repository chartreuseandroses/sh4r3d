# ---------------------------------------------------------------------------
# Build the API Lambda package
# ---------------------------------------------------------------------------

resource "null_resource" "build_api" {
  triggers = {
    src_hash = sha256(join("", [
      for f in sort(fileset("${path.module}/../app", "**/*.py")) :
      filesha256("${path.module}/../app/${f}")
    ]))
    req_hash = filesha256("${path.module}/../requirements-lambda.txt")
  }

  provisioner "local-exec" {
    interpreter = ["PowerShell", "-Command"]
    command     = "Remove-Item -Recurse -Force '${path.module}/../build/api' -ErrorAction Ignore; pip install -r '${path.module}/../requirements-lambda.txt' -t '${path.module}/../build/api' --platform manylinux2014_x86_64 --only-binary=:all: --python-version 3.12 --implementation cp --quiet; if ($LASTEXITCODE) { exit $LASTEXITCODE }; Copy-Item -Recurse '${path.module}/../app' '${path.module}/../build/api/app'"
  }
}

data "archive_file" "api" {
  depends_on  = [null_resource.build_api]
  type        = "zip"
  source_dir  = "${path.module}/../build/api"
  output_path = "${path.module}/../build/api.zip"
}

resource "aws_lambda_function" "api" {
  function_name    = "${var.app_name}-api"
  filename         = data.archive_file.api.output_path
  source_code_hash = data.archive_file.api.output_base64sha256
  role             = aws_iam_role.lambda.arn
  handler          = "app.lambda_handler.handler"
  runtime          = "python3.12"
  timeout          = 30
  memory_size      = 512

  environment {
    variables = {
      SECRET_KEY            = var.secret_key
      BETA_MODE             = var.beta_mode
      S3_BUCKET             = aws_s3_bucket.main.id
      DYNAMODB_TABLE_TOKENS = aws_dynamodb_table.tokens.name
      DYNAMODB_TABLE_SLUGS  = aws_dynamodb_table.slugs.name
      DYNAMODB_TABLE_FILES  = aws_dynamodb_table.files.name
    }
  }

  depends_on = [data.archive_file.api]
}

# ---------------------------------------------------------------------------
# Build the cleanup Lambda package
# ---------------------------------------------------------------------------

resource "null_resource" "build_cleanup" {
  triggers = {
    src_hash = sha256(join("", [
      for f in sort(fileset("${path.module}/../app", "**/*.py")) :
      filesha256("${path.module}/../app/${f}")
    ]))
    req_hash = filesha256("${path.module}/../requirements-lambda.txt")
  }

  provisioner "local-exec" {
    interpreter = ["PowerShell", "-Command"]
    command     = "Remove-Item -Recurse -Force '${path.module}/../build/cleanup' -ErrorAction Ignore; pip install -r '${path.module}/../requirements-lambda.txt' -t '${path.module}/../build/cleanup' --platform manylinux2014_x86_64 --only-binary=:all: --python-version 3.12 --implementation cp --quiet; if ($LASTEXITCODE) { exit $LASTEXITCODE }; Copy-Item -Recurse '${path.module}/../app' '${path.module}/../build/cleanup/app'"
  }
}

data "archive_file" "cleanup" {
  depends_on  = [null_resource.build_cleanup]
  type        = "zip"
  source_dir  = "${path.module}/../build/cleanup"
  output_path = "${path.module}/../build/cleanup.zip"
}

resource "aws_lambda_function" "cleanup" {
  function_name    = "${var.app_name}-cleanup"
  filename         = data.archive_file.cleanup.output_path
  source_code_hash = data.archive_file.cleanup.output_base64sha256
  role             = aws_iam_role.lambda.arn
  handler          = "app.services.cleanup_service.lambda_handler"
  runtime          = "python3.12"
  timeout          = 300
  memory_size      = 256

  environment {
    variables = {
      S3_BUCKET             = aws_s3_bucket.main.id
      DYNAMODB_TABLE_TOKENS = aws_dynamodb_table.tokens.name
      DYNAMODB_TABLE_SLUGS  = aws_dynamodb_table.slugs.name
      DYNAMODB_TABLE_FILES  = aws_dynamodb_table.files.name
    }
  }

  depends_on = [data.archive_file.cleanup]
}
