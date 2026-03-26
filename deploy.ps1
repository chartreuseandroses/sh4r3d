Set-Location "$PSScriptRoot\terraform"
terraform init -upgrade
if ($LASTEXITCODE) { exit $LASTEXITCODE }
terraform apply
if ($LASTEXITCODE) { exit $LASTEXITCODE }
$distId = terraform output -raw cloudfront_distribution_id
if ($LASTEXITCODE) { exit $LASTEXITCODE }
Write-Host "Invalidating CloudFront cache ($distId)..."
aws cloudfront create-invalidation --distribution-id $distId --paths "/*"
Set-Location "$PSScriptRoot"
