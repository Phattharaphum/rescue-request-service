$ErrorActionPreference = "Stop"

$endpoint = if ($env:DYNAMODB_ENDPOINT) { $env:DYNAMODB_ENDPOINT } else { "http://localhost:4566" }
$region = if ($env:AWS_REGION) { $env:AWS_REGION } else { "ap-southeast-1" }

function Wait-ForDynamoDb {
  param(
    [int]$MaxRetries = 30,
    [int]$DelaySeconds = 2
  )

  Write-Host "Waiting for DynamoDB endpoint at $endpoint ..."
  for ($i = 1; $i -le $MaxRetries; $i++) {
    try {
      aws dynamodb list-tables --endpoint-url $endpoint --region $region 1>$null 2>$null
      if ($LASTEXITCODE -eq 0) {
        Write-Host "DynamoDB endpoint is ready."
        return
      }
    } catch {
      # keep retrying until timeout
    }
    Start-Sleep -Seconds $DelaySeconds
  }

  throw "DynamoDB endpoint is not ready after $($MaxRetries * $DelaySeconds) seconds."
}

function Test-TableExists {
  param([string]$TableName)
  try {
    aws dynamodb describe-table --table-name $TableName --endpoint-url $endpoint --region $region 1>$null 2>$null
    return ($LASTEXITCODE -eq 0)
  } catch {
    return $false
  }
}

function Ensure-RescueRequestTable {
  if (Test-TableExists -TableName "RescueRequestTable") {
    Write-Host "RescueRequestTable already exists."
    return
  }

  Write-Host "Creating RescueRequestTable..."
  aws dynamodb create-table `
    --table-name RescueRequestTable `
    --attribute-definitions AttributeName=PK,AttributeType=S AttributeName=SK,AttributeType=S `
    --key-schema AttributeName=PK,KeyType=HASH AttributeName=SK,KeyType=RANGE `
    --billing-mode PAY_PER_REQUEST `
    --endpoint-url $endpoint `
    --region $region 1>$null
  if ($LASTEXITCODE -ne 0) {
    throw "Failed to create RescueRequestTable."
  }
  Write-Host "RescueRequestTable created."
}

function Ensure-IdempotencyTable {
  if (Test-TableExists -TableName "IdempotencyTable") {
    Write-Host "IdempotencyTable already exists."
    return
  }

  Write-Host "Creating IdempotencyTable..."
  aws dynamodb create-table `
    --table-name IdempotencyTable `
    --attribute-definitions AttributeName=idempotencyKeyHash,AttributeType=S `
    --key-schema AttributeName=idempotencyKeyHash,KeyType=HASH `
    --billing-mode PAY_PER_REQUEST `
    --endpoint-url $endpoint `
    --region $region 1>$null
  if ($LASTEXITCODE -ne 0) {
    throw "Failed to create IdempotencyTable."
  }
  Write-Host "IdempotencyTable created."
}

Wait-ForDynamoDb
Ensure-RescueRequestTable
Ensure-IdempotencyTable
Write-Host "Tables are ready."
