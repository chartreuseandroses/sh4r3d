resource "aws_dynamodb_table" "tokens" {
  name         = "${var.app_name}-tokens"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "token"

  attribute {
    name = "token"
    type = "S"
  }
}

resource "aws_dynamodb_table" "slugs" {
  name         = "${var.app_name}-slugs"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "slug"

  attribute {
    name = "slug"
    type = "S"
  }

  ttl {
    attribute_name = "ttl"
    enabled        = true
  }
}

resource "aws_dynamodb_table" "notes" {
  name         = "${var.app_name}-notes"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "note_id"

  attribute {
    name = "note_id"
    type = "S"
  }

  attribute {
    name = "slug"
    type = "S"
  }

  attribute {
    name = "created_at"
    type = "N"
  }

  global_secondary_index {
    name            = "slug-index"
    hash_key        = "slug"
    range_key       = "created_at"
    projection_type = "ALL"
  }

  ttl {
    attribute_name = "ttl"
    enabled        = true
  }
}

resource "aws_dynamodb_table" "files" {
  name         = "${var.app_name}-files"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "file_id"

  attribute {
    name = "file_id"
    type = "S"
  }

  attribute {
    name = "slug"
    type = "S"
  }

  attribute {
    name = "uploaded_at"
    type = "N"
  }

  global_secondary_index {
    name            = "slug-index"
    hash_key        = "slug"
    range_key       = "uploaded_at"
    projection_type = "ALL"
  }

  ttl {
    attribute_name = "ttl"
    enabled        = true
  }
}
