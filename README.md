# sh4r3d

Instant, temporary file sharing. Pick a short slug, get a shareable link. Anyone with the link can upload and download files for 24 hours — then everything is deleted automatically.

Live at **[sh4r3d.com](https://sh4r3d.com)**

---

## How it works

```
Browser
  └─► CloudFront (HTTPS, sh4r3d.com)
        ├─ /          → S3 (static HTML/CSS)
        └─ /api/*     → API Gateway → Lambda (FastAPI)
                                        ├─ DynamoDB  (slugs, files, tokens)
                                        └─ S3        (file storage, presigned URLs)

EventBridge (every 5 min) → Cleanup Lambda → delete expired files + slugs
```

- Files up to 500 MB upload directly from the browser to S3 via a presigned PUT URL — they never pass through Lambda.
- Downloads are a 302 redirect to a presigned S3 GET URL.
- Everything expires after 24 hours. DynamoDB TTL and the cleanup Lambda both handle deletion independently.

---

## Project structure

```
app/                    Python backend (FastAPI)
  config.py             Settings (env vars via pydantic-settings)
  database.py           DynamoDB data layer
  models.py             Pydantic request/response models
  main.py               FastAPI app + session middleware
  lambda_handler.py     Mangum adapter (Lambda entry point)
  routes/api.py         All API endpoints
  services/
    slug_service.py     Slug business logic
    file_service.py     S3 presigned URL generation
    cleanup_service.py  Cleanup Lambda handler

static/                 Static frontend (served from S3 via CloudFront)
  index.html            Slug creation page
  auth.html             Beta token login page
  share.html            File upload/download page
  privacy.html          Privacy policy
  style.css             Shared styles
  robots.txt            Search engine directives

terraform/              Infrastructure as code (AWS)
  main.tf               Provider config
  variables.tf          Input variables
  s3.tf                 S3 bucket, CORS, lifecycle, static file objects
  dynamodb.tf           3 DynamoDB tables
  lambda.tf             Lambda functions + build steps
  apigateway.tf         HTTP API Gateway
  cloudfront.tf         CloudFront distribution + URL rewriting function
  acm.tf                ACM TLS certificate (us-east-1)
  eventbridge.tf        Scheduled cleanup trigger
  iam.tf                Lambda execution role + policy
  outputs.tf            CloudFront URL, API Gateway URL, ACM validation records
  tests/unit.tftest.hcl Terraform unit tests (mock providers)

tests/                  Python unit tests (pytest + moto)
  conftest.py           Fixtures: moto AWS mocks, env vars
  test_models.py        Pydantic model validation
  test_database.py      DynamoDB operations
  test_slug_service.py  Slug service logic
  test_file_service.py  File service logic
  test_cleanup.py       Cleanup Lambda logic
  test_routes.py        API endpoints (FastAPI TestClient)
  integration/          Integration tests (run against live app)
    test_api_flow.py    Full end-to-end API flow

manage.py               Token management CLI (DynamoDB)
requirements.txt        Local dev dependencies
requirements-lambda.txt Lambda packaging dependencies
requirements-dev.txt    Test dependencies
```

---

## Deploying

### Prerequisites

- [Terraform](https://developer.hashicorp.com/terraform/downloads) >= 1.6
- Python 3.12 + pip
- AWS credentials configured (`~/.aws/credentials` or environment variables)
- Domain managed in Cloudflare (or any DNS provider)

### First deploy

```powershell
# 1. Deploy infrastructure (certificate + everything else)
.\deploy.ps1
```

Terraform will pause waiting for ACM certificate validation. Complete DNS setup first:

**DNS records to add in Cloudflare:**

| Type | Name | Value |
|---|---|---|
| CNAME | _(from `acm_dns_validation_records` output)_ | _(from output)_ |
| CNAME | `sh4r3d.com` → DNS only (grey cloud) | _(from `cloudfront_url` output)_ |
| CNAME | `www` → DNS only (grey cloud) | _(from `cloudfront_url` output)_ |

Once the certificate validates, Terraform will complete. The app is live at `sh4r3d.com`.

### Subsequent deploys

```powershell
.\deploy.ps1
```

### Makefile (Linux / macOS / Git Bash)

```bash
make deploy
```

---

## Managing invite tokens (beta mode)

Beta mode gates access behind invite tokens. Set `beta_mode = "true"` in your Terraform variables to enable it.

```bash
# Issue a token
python manage.py add-token --label "Alice"

# List all tokens
python manage.py list-tokens

# Revoke a token
python manage.py revoke-token <token>
```

Requires AWS credentials and the same environment variables used by the Lambda (or a `.env` file).

---

## Running tests

### Python unit tests

```bash
pip install -r requirements-dev.txt
pytest --tb=short -q

# With coverage
pytest --cov=app --cov-report=term-missing
```

No AWS credentials needed — DynamoDB and S3 are mocked with [moto](https://github.com/getmoto/moto).

### Terraform unit tests

```powershell
.\test-terraform.ps1
```

```bash
# or directly
cd terraform && terraform test
```

No AWS credentials needed — all providers are mocked.

### Integration tests (requires live app)

```bash
INTEGRATION_BASE_URL=https://sh4r3d.com \
INTEGRATION_TOKEN=<your-token> \
pytest tests/integration/ -v
```

`INTEGRATION_TOKEN` is only required if beta mode is enabled. Integration tests create uniquely-named slugs and clean up after themselves automatically via the 24-hour TTL.

---

## Privacy

Files are deleted automatically after 24 hours. The operator does not examine uploaded content and does not track users. See [sh4r3d.com/privacy](https://sh4r3d.com/privacy) for the full policy.
