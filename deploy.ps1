Set-Location "$PSScriptRoot\terraform"
terraform init -upgrade
if ($LASTEXITCODE) { exit $LASTEXITCODE }
terraform apply
Set-Location "$PSScriptRoot"
