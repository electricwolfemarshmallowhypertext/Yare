$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location -LiteralPath $repoRoot

$stickyDir = Join-Path $repoRoot ".sticky"
foreach ($target in @("current-state.json", "current-state.md")) {
    $path = Join-Path $stickyDir $target
    if (Test-Path -LiteralPath $path) {
        Remove-Item -LiteralPath $path -Force
    }
}

$args = @(
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

$output = & .\agentmd.cmd @args 2>&1
$exitCode = $LASTEXITCODE
$output | ForEach-Object { Write-Output $_ }

if ($exitCode -ne 0) {
    throw "agentmd lead compile failed with exit code $exitCode"
}

$deterministicHash = $null
foreach ($line in $output) {
    $text = [string]$line
    if ($text -match "deterministic_hash:\s*(\S+)") {
        $deterministicHash = $matches[1]
        break
    }
}

$currentStateJson = Join-Path $stickyDir "current-state.json"
$currentStateMd = Join-Path $stickyDir "current-state.md"
$latestReceipt = Get-ChildItem -Path (Join-Path $stickyDir "receipts\*.jsonl") -File -ErrorAction SilentlyContinue |
    Sort-Object LastWriteTime |
    Select-Object -Last 1

Write-Output ""
Write-Output "current_state_json: $currentStateJson"
Write-Output "current_state_md: $currentStateMd"
if ($null -ne $latestReceipt) {
    Write-Output "latest_receipt: $($latestReceipt.FullName)"
} else {
    Write-Output "latest_receipt: <none>"
}

if ($deterministicHash) {
    Write-Output "deterministic_hash: $deterministicHash"
} else {
    Write-Output "deterministic_hash: <not found in CLI output>"
}
