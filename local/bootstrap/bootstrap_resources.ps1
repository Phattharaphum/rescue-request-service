$ErrorActionPreference = "Stop"

$endpoint = if ($env:DYNAMODB_ENDPOINT) { $env:DYNAMODB_ENDPOINT } elseif ($env:AWS_ENDPOINT_URL) { $env:AWS_ENDPOINT_URL } else { "http://localhost:4566" }
$region = if ($env:AWS_REGION) { $env:AWS_REGION } else { "ap-southeast-1" }
$localstackContainerName = if ($env:LOCALSTACK_CONTAINER_NAME) { $env:LOCALSTACK_CONTAINER_NAME } else { "localstack" }

$incidentSyncSecretName = if ($env:INCIDENT_SYNC_SECRET_ID) { $env:INCIDENT_SYNC_SECRET_ID } else { "rescue-request-service/incident-tracking/local" }
$incidentSyncApiUrl = if ($env:INCIDENT_SYNC_API_URL) { $env:INCIDENT_SYNC_API_URL } else { "http://host.docker.internal:3000/api/v1/incidents" }
$incidentSyncApiKey = if ($env:INCIDENT_SYNC_API_KEY) { $env:INCIDENT_SYNC_API_KEY } else { "123" }
$incidentSyncAccept = if ($env:INCIDENT_SYNC_ACCEPT) { $env:INCIDENT_SYNC_ACCEPT } else { "application/json" }
$incidentSyncTxnHeader = if ($env:INCIDENT_SYNC_TRANSACTION_ID_HEADER) { $env:INCIDENT_SYNC_TRANSACTION_ID_HEADER } else { "X-IncidentTNX-Id" }

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

function Invoke-AwsCliCapture {
  param([string[]]$Arguments)

  $output = $null
  if ($awsInvocationMode -eq "host-aws") {
    $output = & aws @Arguments
    $exitCode = $LASTEXITCODE
  } else {
    $output = & docker exec $localstackContainerName awslocal @Arguments
    $exitCode = $LASTEXITCODE
  }

  if ($exitCode -ne 0) {
    throw "AWS CLI command failed: aws $($Arguments -join ' ')"
  }

  return [string]($output | Out-String).Trim()
}

function New-TempJsonFile {
  param([string]$Content)
  $path = [System.IO.Path]::GetTempFileName()
  Set-Content -Path $path -Value $Content -NoNewline
  return $path
}

function Wait-ForServices {
  param(
    [int]$MaxRetries = 30,
    [int]$DelaySeconds = 2
  )

  Write-Host "Waiting for LocalStack services at $endpoint ..."
  for ($i = 1; $i -le $MaxRetries; $i++) {
    $snsReady = Invoke-AwsCli -Quiet -Arguments @("sns", "list-topics", "--endpoint-url", $endpoint, "--region", $region)
    $sqsReady = Invoke-AwsCli -Quiet -Arguments @("sqs", "list-queues", "--endpoint-url", $endpoint, "--region", $region)
    $secretsReady = Invoke-AwsCli -Quiet -Arguments @("secretsmanager", "list-secrets", "--endpoint-url", $endpoint, "--region", $region)

    if ($snsReady -eq 0 -and $sqsReady -eq 0 -and $secretsReady -eq 0) {
      Write-Host "SNS, SQS, and Secrets Manager are ready."
      return
    }

    Start-Sleep -Seconds $DelaySeconds
  }

  throw "LocalStack services are not ready after $($MaxRetries * $DelaySeconds) seconds."
}

function Ensure-Topic {
  param([string]$TopicName)
  $topicArn = Invoke-AwsCliCapture -Arguments @(
    "sns", "create-topic",
    "--name", $TopicName,
    "--endpoint-url", $endpoint,
    "--region", $region,
    "--query", "TopicArn",
    "--output", "text"
  )
  Write-Host "Topic ready: $topicArn"
  return $topicArn
}

function Ensure-Queue {
  param(
    [string]$QueueName,
    [hashtable]$Attributes = @{}
  )

  $queueUrl = $null
  try {
    $queueUrl = Invoke-AwsCliCapture -Arguments @(
      "sqs", "get-queue-url",
      "--queue-name", $QueueName,
      "--endpoint-url", $endpoint,
      "--region", $region,
      "--query", "QueueUrl",
      "--output", "text"
    )
    Write-Host "Queue already exists: $queueUrl"
  } catch {
    $args = @(
      "sqs", "create-queue",
      "--queue-name", $QueueName,
      "--endpoint-url", $endpoint,
      "--region", $region
    )

    $tempFile = $null
    try {
      if ($Attributes.Count -gt 0) {
        $tempFile = New-TempJsonFile -Content ($Attributes | ConvertTo-Json -Compress)
        $args += @("--attributes", "file://$tempFile")
      }
      $args += @("--query", "QueueUrl", "--output", "text")
      $queueUrl = Invoke-AwsCliCapture -Arguments $args
    } finally {
      if ($tempFile -and (Test-Path $tempFile)) {
        Remove-Item -LiteralPath $tempFile -Force
      }
    }

    Write-Host "Queue ready: $queueUrl"
  }

  if ($Attributes.Count -gt 0) {
    $attributesFile = New-TempJsonFile -Content ($Attributes | ConvertTo-Json -Compress)
    try {
      $exitCode = Invoke-AwsCli -Arguments @(
        "sqs", "set-queue-attributes",
        "--queue-url", $queueUrl,
        "--attributes", "file://$attributesFile",
        "--endpoint-url", $endpoint,
        "--region", $region
      )
      if ($exitCode -ne 0) {
        throw "Failed to set attributes on queue $QueueName"
      }
    } finally {
      if (Test-Path $attributesFile) {
        Remove-Item -LiteralPath $attributesFile -Force
      }
    }
    Write-Host "Queue attributes ensured: $QueueName"
  }

  return $queueUrl
}

function Get-QueueArn {
  param([string]$QueueUrl)
  return Invoke-AwsCliCapture -Arguments @(
    "sqs", "get-queue-attributes",
    "--queue-url", $QueueUrl,
    "--attribute-names", "QueueArn",
    "--endpoint-url", $endpoint,
    "--region", $region,
    "--query", "Attributes.QueueArn",
    "--output", "text"
  )
}

function Set-QueuePolicy {
  param(
    [string]$QueueUrl,
    [hashtable]$Policy
  )

  $attributes = @{ Policy = ($Policy | ConvertTo-Json -Depth 12 -Compress) }
  $tempFile = New-TempJsonFile -Content ($attributes | ConvertTo-Json -Compress)
  try {
    $exitCode = Invoke-AwsCli -Arguments @(
      "sqs", "set-queue-attributes",
      "--queue-url", $QueueUrl,
      "--attributes", "file://$tempFile",
      "--endpoint-url", $endpoint,
      "--region", $region
    )
    if ($exitCode -ne 0) {
      throw "Failed to set queue policy for $QueueUrl"
    }
  } finally {
    if (Test-Path $tempFile) {
      Remove-Item -LiteralPath $tempFile -Force
    }
  }
}

function Ensure-SnsSubscription {
  param(
    [string]$TopicArn,
    [string]$QueueArn
  )

  $query = "Subscriptions[?Endpoint=='$QueueArn' && Protocol=='sqs'].SubscriptionArn | [0]"
  $existing = Invoke-AwsCliCapture -Arguments @(
    "sns", "list-subscriptions-by-topic",
    "--topic-arn", $TopicArn,
    "--endpoint-url", $endpoint,
    "--region", $region,
    "--query", $query,
    "--output", "text"
  )

  if ($existing -and $existing -ne "None" -and $existing -ne "null") {
    Write-Host "Subscription already exists: $existing"
    return
  }

  $subArn = Invoke-AwsCliCapture -Arguments @(
    "sns", "subscribe",
    "--topic-arn", $TopicArn,
    "--protocol", "sqs",
    "--notification-endpoint", $QueueArn,
    "--endpoint-url", $endpoint,
    "--region", $region,
    "--query", "SubscriptionArn",
    "--output", "text"
  )
  Write-Host "Subscription created: $subArn"
}

function Ensure-IncidentSyncSecret {
  $secretPayload = @{
    apiUrl = $incidentSyncApiUrl
    apiKey = $incidentSyncApiKey
    accept = $incidentSyncAccept
    transactionIdHeader = $incidentSyncTxnHeader
  } | ConvertTo-Json -Compress

  $payloadFile = New-TempJsonFile -Content $secretPayload
  try {
    $exists = Invoke-AwsCli -Quiet -Arguments @(
      "secretsmanager", "describe-secret",
      "--secret-id", $incidentSyncSecretName,
      "--endpoint-url", $endpoint,
      "--region", $region
    )

    if ($exists -eq 0) {
      [void](Invoke-AwsCliCapture -Arguments @(
        "secretsmanager", "put-secret-value",
        "--secret-id", $incidentSyncSecretName,
        "--secret-string", "file://$payloadFile",
        "--endpoint-url", $endpoint,
        "--region", $region
      ))
      Write-Host "Secret updated: $incidentSyncSecretName"
      return
    }

    [void](Invoke-AwsCliCapture -Arguments @(
      "secretsmanager", "create-secret",
      "--name", $incidentSyncSecretName,
      "--secret-string", "file://$payloadFile",
      "--endpoint-url", $endpoint,
      "--region", $region
    ))
    Write-Host "Secret created: $incidentSyncSecretName"
  } finally {
    if (Test-Path $payloadFile) {
      Remove-Item -LiteralPath $payloadFile -Force
    }
  }
}

Write-Host "Using AWS invocation mode: $awsInvocationMode"
Wait-ForServices

Write-Host "Bootstrapping local messaging resources..."
$eventsTopicArn = Ensure-Topic -TopicName "rescue-request-events-v1"
$eventsStreamQueueUrl = Ensure-Queue -QueueName "rescue-request-events-v1-stream"
$eventsStreamQueueArn = Get-QueueArn -QueueUrl $eventsStreamQueueUrl

$priorCreatedTopicArn = Ensure-Topic -TopicName "rescue-prioritization-created-v1"
$priorUpdatedTopicArn = Ensure-Topic -TopicName "rescue-prioritization-updated-v1"
$priorDlqUrl = Ensure-Queue -QueueName "rescue-prioritization-evaluated-dlq"
$priorDlqArn = Get-QueueArn -QueueUrl $priorDlqUrl
$redrivePolicy = @{
  deadLetterTargetArn = $priorDlqArn
  maxReceiveCount = "3"
} | ConvertTo-Json -Compress
$priorQueueUrl = Ensure-Queue -QueueName "rescue-prioritization-evaluated" -Attributes @{
  VisibilityTimeout = "60"
  RedrivePolicy = $redrivePolicy
}
$priorQueueArn = Get-QueueArn -QueueUrl $priorQueueUrl

$eventsQueuePolicy = @{
  Version = "2012-10-17"
  Statement = @(
    @{
      Sid = "AllowRescueRequestEventsTopic"
      Effect = "Allow"
      Principal = "*"
      Action = "sqs:SendMessage"
      Resource = $eventsStreamQueueArn
      Condition = @{
        ArnEquals = @{
          "aws:SourceArn" = $eventsTopicArn
        }
      }
    }
  )
}
Set-QueuePolicy -QueueUrl $eventsStreamQueueUrl -Policy $eventsQueuePolicy
Ensure-SnsSubscription -TopicArn $eventsTopicArn -QueueArn $eventsStreamQueueArn

$priorQueuePolicy = @{
  Version = "2012-10-17"
  Statement = @(
    @{
      Sid = "AllowPrioritizationCreatedTopicPublish"
      Effect = "Allow"
      Principal = "*"
      Action = "sqs:SendMessage"
      Resource = $priorQueueArn
      Condition = @{
        ArnEquals = @{
          "aws:SourceArn" = $priorCreatedTopicArn
        }
      }
    },
    @{
      Sid = "AllowPrioritizationUpdatedTopicPublish"
      Effect = "Allow"
      Principal = "*"
      Action = "sqs:SendMessage"
      Resource = $priorQueueArn
      Condition = @{
        ArnEquals = @{
          "aws:SourceArn" = $priorUpdatedTopicArn
        }
      }
    }
  )
}
Set-QueuePolicy -QueueUrl $priorQueueUrl -Policy $priorQueuePolicy
Ensure-SnsSubscription -TopicArn $priorCreatedTopicArn -QueueArn $priorQueueArn
Ensure-SnsSubscription -TopicArn $priorUpdatedTopicArn -QueueArn $priorQueueArn

Write-Host "Bootstrapping incident sync secret..."
Ensure-IncidentSyncSecret

Write-Host "LocalStack bootstrap complete."
Write-Host "Resource summary:"
Write-Host "  rescue-request-events-v1 => $eventsTopicArn"
Write-Host "  rescue-request-events-v1-stream => $eventsStreamQueueUrl"
Write-Host "  rescue-prioritization-created-v1 => $priorCreatedTopicArn"
Write-Host "  rescue-prioritization-updated-v1 => $priorUpdatedTopicArn"
Write-Host "  rescue-prioritization-evaluated => $priorQueueUrl"
Write-Host "  rescue-prioritization-evaluated-dlq => $priorDlqUrl"
Write-Host "  incident secret => $incidentSyncSecretName"
