param(
    [string]$DatabaseUrl,
    [string]$S3Bucket,
    [string]$S3Prefix
)

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location -LiteralPath $repoRoot

function Invoke-Yare {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )

    $output = @(& python -m cli.yare @Arguments 2>&1)
    $exitCode = $LASTEXITCODE

    if ($exitCode -ne 0) {
        throw "python -m cli.yare $($Arguments -join ' ') failed with exit code $exitCode"
    }

    return $output
}

function Find-OutputValue {
    param(
        [Parameter(Mandatory = $true)]
        [object[]]$Output,
        [Parameter(Mandatory = $true)]
        [string]$Name
    )

    foreach ($line in $Output) {
        $text = [string]$line
        if ($text -match "^$([regex]::Escape($Name)):\s*(.+)$") {
            return $matches[1].Trim()
        }
    }

    return $null
}

function Test-AwsCredentials {
    $previousMetadataSetting = $env:AWS_EC2_METADATA_DISABLED
    if ([string]::IsNullOrWhiteSpace($previousMetadataSetting)) {
        $env:AWS_EC2_METADATA_DISABLED = "true"
    }

    $check = @(& python -c "import boto3; print('true' if boto3.Session().get_credentials() else 'false')" 2>$null)
    $exitCode = $LASTEXITCODE

    if ([string]::IsNullOrWhiteSpace($previousMetadataSetting)) {
        Remove-Item Env:AWS_EC2_METADATA_DISABLED -ErrorAction SilentlyContinue
    } else {
        $env:AWS_EC2_METADATA_DISABLED = $previousMetadataSetting
    }

    return ($exitCode -eq 0 -and ($check | Select-Object -Last 1) -eq "true")
}

Write-Output "Yare Handoff Integrity Bench"
Write-Output ""
Write-Output "inputs:"
Write-Output "- examples/lead-artifacts/run-codex.jsonl"
Write-Output "- examples/lead-artifacts/run-claude.json"
Write-Output "- examples/lead-artifacts/run-gemini.jsonl"
Write-Output ""

if (-not [string]::IsNullOrWhiteSpace($DatabaseUrl)) {
    $env:YARE_DATABASE_URL = $DatabaseUrl
}

if (-not [string]::IsNullOrWhiteSpace($S3Bucket)) {
    $env:YARE_S3_BUCKET = $S3Bucket
}

if (-not [string]::IsNullOrWhiteSpace($S3Prefix)) {
    $env:YARE_S3_PREFIX = $S3Prefix
}

$hasDatabase = -not [string]::IsNullOrWhiteSpace($env:YARE_DATABASE_URL)
$hasS3Bucket = -not [string]::IsNullOrWhiteSpace($env:YARE_S3_BUCKET)
$hasAwsCredentials = $false
if ($hasS3Bucket) {
    $hasAwsCredentials = Test-AwsCredentials
}
$hasS3 = $hasS3Bucket -and $hasAwsCredentials
$s3BucketValue = $env:YARE_S3_BUCKET

if ($hasDatabase) {
    Write-Output "cockroach: enabled via YARE_DATABASE_URL"
    $storageOutput = Invoke-Yare -Arguments @("storage", "init")
    $storageOutput | ForEach-Object { Write-Output $_ }
} else {
    Write-Output "cockroach: skipped (YARE_DATABASE_URL not set)"
}

if ($hasS3) {
    Write-Output "s3: enabled via YARE_S3_BUCKET"
} elseif ($hasS3Bucket) {
    Write-Output "s3: skipped (YARE_S3_BUCKET set, but AWS credentials unavailable)"
    Remove-Item Env:YARE_S3_BUCKET -ErrorAction SilentlyContinue
} else {
    Write-Output "s3: skipped (YARE_S3_BUCKET not set)"
}

Write-Output ""
Write-Output "compile:"
$compileOutput = Invoke-Yare -Arguments @(
    "lead",
    "compile",
    "--task",
    "compile ai work lead state",
    "--artifact",
    "examples/lead-artifacts/run-codex.jsonl",
    "--artifact",
    "examples/lead-artifacts/run-claude.json",
    "--artifact",
    "examples/lead-artifacts/run-gemini.jsonl"
)
$compileOutput | ForEach-Object { Write-Output $_ }

$deterministicHash = Find-OutputValue -Output $compileOutput -Name "deterministic_hash"
$receipt = Find-OutputValue -Output $compileOutput -Name "receipt"
$receiptHash = Find-OutputValue -Output $compileOutput -Name "receipt_hash"
$s3Uris = @($compileOutput | ForEach-Object { [string]$_ } | Where-Object { $_ -match "^s3_uri:\s*" })

Write-Output ""
Write-Output "bench summary:"
Write-Output "current_state_hash: $(if ($deterministicHash) { $deterministicHash } else { '<not found>' })"
Write-Output "receipt: $(if ($receipt) { $receipt } else { '<not found>' })"
Write-Output "receipt_hash: $(if ($receiptHash) { $receiptHash } else { '<not found>' })"

if ($s3Uris.Count -gt 0) {
    Write-Output "s3_objects:"
    $s3Uris | ForEach-Object { Write-Output "- $($_ -replace '^s3_uri:\s*', '')" }
} elseif ($hasS3) {
    Write-Output "s3_objects: <none reported>"
} else {
    Write-Output "s3_objects: skipped"
}

if ($hasS3Bucket -and -not $hasS3) {
    $env:YARE_S3_BUCKET = $s3BucketValue
}

if ($hasDatabase) {
    Write-Output ""
    Write-Output "memory search:"
    $searchOutput = Invoke-Yare -Arguments @("memory", "search", "--query", "what still needs human review?", "--limit", "3")
    $searchOutput | ForEach-Object { Write-Output $_ }

    Write-Output ""
    Write-Output "memory timeline:"
    $timelineOutput = Invoke-Yare -Arguments @("memory", "timeline")
    $timelineOutput | ForEach-Object { Write-Output $_ }

    Write-Output ""
    Write-Output "memory diff:"
    $diffOutput = Invoke-Yare -Arguments @("memory", "diff", "--latest")
    $diffOutput | ForEach-Object { Write-Output $_ }
} else {
    Write-Output ""
    Write-Output "memory search: skipped"
    Write-Output "memory timeline: skipped"
    Write-Output "memory diff: skipped"
}

Write-Output ""
Write-Output "bench: complete"
