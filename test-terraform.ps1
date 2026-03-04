Set-Location "$PSScriptRoot\terraform"
terraform init -upgrade
if ($LASTEXITCODE) { exit $LASTEXITCODE }
terraform test
Set-Location "$PSScriptRoot"
