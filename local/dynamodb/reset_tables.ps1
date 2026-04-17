$ErrorActionPreference = "Stop"

$endpoint = if ($env:DYNAMODB_ENDPOINT) { $env:DYNAMODB_ENDPOINT } else { "http://localhost:4566" }
$regions = @("ap-southeast-1", "us-east-1")
$tables = @("RescueRequestTable", "IdempotencyTable", "IncidentCatalogTable")
$originalRegion = $env:AWS_REGION
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

function Remove-TableIfExists {
  param(
    [string]$TableName,
    [string]$Region
  )

  try {
    $exitCode = Invoke-AwsCli -Quiet -Arguments @("dynamodb", "delete-table", "--table-name", $TableName, "--endpoint-url", $endpoint, "--region", $Region)
    if ($exitCode -eq 0) {
      Write-Host "Deleted $TableName in $Region."
      return
    }
  } catch {
    # ignore and print friendly status below
  }

  Write-Host "$TableName does not exist in $Region."
}

Write-Host "Using AWS invocation mode: $awsInvocationMode"
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
