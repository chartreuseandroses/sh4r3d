Set-Location "$PSScriptRoot"
pytest tests/ --ignore=tests/integration -v
if ($LASTEXITCODE) { exit $LASTEXITCODE }

Set-Location "$PSScriptRoot\terraform"
terraform init -upgrade
if ($LASTEXITCODE) { exit $LASTEXITCODE }
terraform test
Set-Location "$PSScriptRoot"
