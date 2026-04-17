$ErrorActionPreference = "Stop"

$endpoint = if ($env:DYNAMODB_ENDPOINT) { $env:DYNAMODB_ENDPOINT } else { "http://localhost:4566" }
$region = if ($env:AWS_REGION) { $env:AWS_REGION } else { "ap-southeast-1" }
$localstackContainerName = if ($env:LOCALSTACK_CONTAINER_NAME) { $env:LOCALSTACK_CONTAINER_NAME } else { "localstack" }

function Test-CommandAvailable {
  param([string]$CommandName)
  return $null -ne (Get-Command $CommandName -ErrorAction SilentlyContinue)
}

function Test-LocalStackContainerRunning {
  if (-not (Test-CommandAvailable -CommandName "docker")) {
    return $false
  }

  $container = docker ps --filter "name=^$localstackContainerName$" --format "{{.Names}}"
  return $container -contains $localstackContainerName
}

function Get-AwsInvocationMode {
  if (Test-CommandAvailable -CommandName "aws") {
    return "host-aws"
  }

  if (Test-LocalStackContainerRunning) {
    return "docker-awslocal"
  }

  throw "Neither AWS CLI nor a running '$localstackContainerName' container is available. Install AWS CLI or start LocalStack first."
}

$awsInvocationMode = Get-AwsInvocationMode

function Invoke-AwsCli {
  param(
    [switch]$Quiet,
    [string[]]$Arguments
  )

  if ($awsInvocationMode -eq "host-aws") {
    if ($Quiet) {
      & aws @Arguments 1>$null 2>$null
    } else {
      & aws @Arguments
    }
    return $LASTEXITCODE
  }

  if ($Quiet) {
    & docker exec $localstackContainerName awslocal @Arguments 1>$null 2>$null
  } else {
    & docker exec $localstackContainerName awslocal @Arguments
  }
  return $LASTEXITCODE
}

function Wait-ForDynamoDb {
  param(
    [int]$MaxRetries = 30,
    [int]$DelaySeconds = 2
  )

  Write-Host "Waiting for DynamoDB endpoint at $endpoint ..."
  $healthUrl = "$endpoint/_localstack/health"
  for ($i = 1; $i -le $MaxRetries; $i++) {
    try {
      $healthResponse = Invoke-WebRequest -UseBasicParsing -Uri $healthUrl -TimeoutSec 3
      if ($healthResponse.StatusCode -eq 200) {
        $health = $healthResponse.Content | ConvertFrom-Json
        if ($health.services.dynamodb -eq "available" -or $health.services.dynamodb -eq "running") {
          Write-Host "DynamoDB endpoint is ready."
          return
        }
      }
    } catch {
      # keep retrying until timeout
    }

    # Fallback probe if health endpoint shape differs.
    try {
      $exitCode = Invoke-AwsCli -Quiet -Arguments @("dynamodb", "list-tables", "--endpoint-url", $endpoint, "--region", $region)
      if ($exitCode -eq 0) {
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
    $exitCode = Invoke-AwsCli -Quiet -Arguments @("dynamodb", "describe-table", "--table-name", $TableName, "--endpoint-url", $endpoint, "--region", $region)
    return ($exitCode -eq 0)
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
  $exitCode = Invoke-AwsCli -Quiet -Arguments @(
    "dynamodb", "create-table",
    "--table-name", "RescueRequestTable",
    "--attribute-definitions", "AttributeName=PK,AttributeType=S", "AttributeName=SK,AttributeType=S",
    "--key-schema", "AttributeName=PK,KeyType=HASH", "AttributeName=SK,KeyType=RANGE",
    "--billing-mode", "PAY_PER_REQUEST",
    "--endpoint-url", $endpoint,
    "--region", $region
  )
  if ($exitCode -ne 0) {
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
  $exitCode = Invoke-AwsCli -Quiet -Arguments @(
    "dynamodb", "create-table",
    "--table-name", "IdempotencyTable",
    "--attribute-definitions", "AttributeName=idempotencyKeyHash,AttributeType=S",
    "--key-schema", "AttributeName=idempotencyKeyHash,KeyType=HASH",
    "--billing-mode", "PAY_PER_REQUEST",
    "--endpoint-url", $endpoint,
    "--region", $region
  )
  if ($exitCode -ne 0) {
    throw "Failed to create IdempotencyTable."
  }
  Write-Host "IdempotencyTable created."
}

function Ensure-IncidentCatalogTable {
  if (Test-TableExists -TableName "IncidentCatalogTable") {
    Write-Host "IncidentCatalogTable already exists."
    return
  }

  Write-Host "Creating IncidentCatalogTable..."
  $gsi = '[{"IndexName":"CatalogOrderIndex","KeySchema":[{"AttributeName":"catalogPartition","KeyType":"HASH"},{"AttributeName":"catalogSortKey","KeyType":"RANGE"}],"Projection":{"ProjectionType":"ALL"}}]'
  $exitCode = Invoke-AwsCli -Quiet -Arguments @(
    "dynamodb", "create-table",
    "--table-name", "IncidentCatalogTable",
    "--attribute-definitions", "AttributeName=incidentId,AttributeType=S", "AttributeName=catalogPartition,AttributeType=S", "AttributeName=catalogSortKey,AttributeType=S",
    "--key-schema", "AttributeName=incidentId,KeyType=HASH",
    "--global-secondary-indexes", $gsi,
    "--billing-mode", "PAY_PER_REQUEST",
    "--endpoint-url", $endpoint,
    "--region", $region
  )
  if ($exitCode -ne 0) {
    throw "Failed to create IncidentCatalogTable."
  }
  Write-Host "IncidentCatalogTable created."
}

Write-Host "Using AWS invocation mode: $awsInvocationMode"
Wait-ForDynamoDb
Ensure-RescueRequestTable
Ensure-IdempotencyTable
Ensure-IncidentCatalogTable
Write-Host "Tables are ready."
