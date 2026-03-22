$ErrorActionPreference = "Stop"

$endpoint = if ($env:DYNAMODB_ENDPOINT) { $env:DYNAMODB_ENDPOINT } else { "http://localhost:4566" }
$regions = @("ap-southeast-1", "us-east-1")
$tables = @("RescueRequestTable", "IdempotencyTable")
$originalRegion = $env:AWS_REGION

function Remove-TableIfExists {
  param(
    [string]$TableName,
    [string]$Region
  )

  try {
    aws dynamodb delete-table --table-name $TableName --endpoint-url $endpoint --region $Region 1>$null 2>$null
    if ($LASTEXITCODE -eq 0) {
      Write-Host "Deleted $TableName in $Region."
      return
    }
  } catch {
    # ignore and print friendly status below
  }

  Write-Host "$TableName does not exist in $Region."
}

Write-Host "Resetting local DynamoDB tables at $endpoint ..."

foreach ($region in $regions) {
  foreach ($table in $tables) {
    Remove-TableIfExists -TableName $table -Region $region
  }
}

foreach ($region in $regions) {
  $env:AWS_REGION = $region
  & "$PSScriptRoot/create_tables.ps1"
}

if ($null -ne $originalRegion) {
  $env:AWS_REGION = $originalRegion
} else {
  Remove-Item Env:AWS_REGION -ErrorAction SilentlyContinue
}

Write-Host "Local DynamoDB reset complete."
