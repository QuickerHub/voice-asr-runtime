#!/usr/bin/env pwsh
# Generate voice-plugin-channel.json payload (URLs + sha256) for QuickerAgent Tauri embed.

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Version,

    [string]$Tag = '',
    [string]$GitHubRepo = 'QuickerHub/voice-asr-runtime',
    [string]$BitifulPrefix = 'https://s3.bitiful.net/quicker-pkgs/quicker-rpc/voice-asr',
    [string]$PublishDir = '',
    [string]$OutputPath = ''
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$RepoRoot = Split-Path -Parent $PSScriptRoot
if (-not $PublishDir) {
    $PublishDir = Join-Path $RepoRoot 'publish'
}
if (-not $Tag) {
    $Tag = "v$($Version.Trim())"
}
elseif (-not $Tag.Trim().StartsWith('v')) {
    $Tag = "v$($Tag.Trim())"
}

$runtimeZipName = "voice-asr-runtime-$Version-win-x64.zip"
$modelZipName = "voice-asr-model-sensevoice-$Version-win-x64.zip"
$runtimeZip = Join-Path $PublishDir $runtimeZipName
$modelZip = Join-Path $PublishDir $modelZipName

foreach ($path in @($runtimeZip, $modelZip)) {
    if (-not (Test-Path -LiteralPath $path)) {
        throw "Missing zip for manifest: $path"
    }
}

function Get-HexSha256 {
    param([string]$Path)
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}

$githubBase = "https://github.com/$GitHubRepo/releases/download/$Tag"
$manifest = [ordered]@{
    runtimeVersion       = $Version
    runtimeZipUrl        = "$githubBase/$runtimeZipName"
    modelZipUrl          = "$githubBase/$modelZipName"
    runtimeZipMirrorUrl  = "$BitifulPrefix/$runtimeZipName"
    modelZipMirrorUrl    = "$BitifulPrefix/$modelZipName"
    runtimeZipSha256     = Get-HexSha256 -Path $runtimeZip
    modelZipSha256       = Get-HexSha256 -Path $modelZip
}

$json = ($manifest | ConvertTo-Json -Depth 4) + [Environment]::NewLine
if (-not $OutputPath) {
    $OutputPath = Join-Path $PublishDir 'voice-plugin-channel.generated.json'
}

Set-Content -LiteralPath $OutputPath -Value $json -Encoding utf8NoBOM
Write-Host "Wrote $OutputPath" -ForegroundColor Green
