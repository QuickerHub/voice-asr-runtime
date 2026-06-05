#!/usr/bin/env pwsh
# Upload voice-asr runtime + model zips to Bitiful (standalone or monorepo).

[CmdletBinding()]
param(
    [string]$RepoRoot = '',
    [string]$Version = '0.1.0',
    [string]$Tag = '',
    [switch]$UseLocalVoiceRoot,
    [switch]$DryRun
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$ScriptDir = $PSScriptRoot
$VoiceRoot = Split-Path -Parent $ScriptDir

function Import-DotEnvFile {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) { return }
    Get-Content -LiteralPath $Path | ForEach-Object {
        $line = $_.Trim()
        if (-not $line -or $line.StartsWith('#')) { return }
        $idx = $line.IndexOf('=')
        if ($idx -lt 1) { return }
        $key = $line.Substring(0, $idx).Trim()
        $value = $line.Substring($idx + 1).Trim().Trim('"').Trim("'")
        if ($key) { Set-Item -Path "env:$key" -Value $value }
    }
}

Import-DotEnvFile -Path (Join-Path $ScriptDir '.env')
if ($RepoRoot) {
    Import-DotEnvFile -Path (Join-Path $RepoRoot 'publish/.env')
}
else {
    Import-DotEnvFile -Path (Join-Path $VoiceRoot '..' 'publish' '.env')
}

$uploadPy = Join-Path $ScriptDir 'bitiful_upload.py'
if (-not (Test-Path -LiteralPath $uploadPy)) {
    $uploadPy = Join-Path $VoiceRoot '..' 'publish' 'bitiful_upload.py'
}
if (-not (Test-Path -LiteralPath $uploadPy)) {
    throw "bitiful_upload.py not found under $ScriptDir or quicker-rpc/publish"
}

function Test-BitifulConfigured {
    return -not [string]::IsNullOrWhiteSpace($env:BITIFUL_ACCESS_KEY) -and
        -not [string]::IsNullOrWhiteSpace($env:BITIFUL_SECRET_KEY) -and
        -not [string]::IsNullOrWhiteSpace($env:BITIFUL_BUCKET_NAME)
}

if (-not (Test-BitifulConfigured)) {
    throw @'
Bitiful credentials not configured.
Set BITIFUL_ACCESS_KEY, BITIFUL_SECRET_KEY, BITIFUL_BUCKET_NAME in publish/.env
(or quicker-rpc/publish/.env when using monorepo).
'@
}

$Version = $Version.Trim()
if (-not $Version) { throw 'Version is required.' }

if (-not $Tag) { $Tag = "v$Version" }
elseif (-not $Tag.Trim().StartsWith('v')) { $Tag = "v$($Tag.Trim())" }

$PublishDir = Join-Path $VoiceRoot 'publish'
$RuntimeZipName = "voice-asr-runtime-$Version-win-x64.zip"
$ModelZipName = "voice-asr-model-sensevoice-$Version-win-x64.zip"
$RuntimeZip = Join-Path $PublishDir $RuntimeZipName
$ModelZip = Join-Path $PublishDir $ModelZipName

$endpointUrl = if ([string]::IsNullOrWhiteSpace($env:BITIFUL_ENDPOINT_URL)) {
    'https://s3.bitiful.net'
} else { $env:BITIFUL_ENDPOINT_URL.Trim() }

$objectPrefix = if ([string]::IsNullOrWhiteSpace($env:BITIFUL_VOICE_ASR_OBJECT_PREFIX)) {
    'quicker-rpc/voice-asr'
} else { $env:BITIFUL_VOICE_ASR_OBJECT_PREFIX.Trim() }

function Resolve-Asset {
    param([string]$LocalPath, [string]$AssetName)
    if (Test-Path -LiteralPath $LocalPath) {
        return (Resolve-Path -LiteralPath $LocalPath).Path
    }
    if ($DryRun) {
        Write-Host "[DryRun] Would download $AssetName from GitHub release $Tag" -ForegroundColor DarkGray
        return $LocalPath
    }
    if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
        throw "Missing $LocalPath and gh is not installed."
    }
    New-Item -ItemType Directory -Path $PublishDir -Force | Out-Null
    gh release download $Tag --repo 'QuickerHub/voice-asr-runtime' --pattern $AssetName -D $PublishDir
    if ($LASTEXITCODE -ne 0) { throw "gh release download failed for $AssetName" }
    return (Resolve-Path -LiteralPath $LocalPath).Path
}

function Invoke-BitifulPython {
    param([string[]]$Args)
    if (Get-Command uv -ErrorAction SilentlyContinue) {
        & uv run --no-sync --with boto3 python @Args
    }
    else {
        & python -m pip install --disable-pip-version-check --quiet boto3
        if ($LASTEXITCODE -ne 0) { throw 'Failed to install boto3' }
        & python @Args
    }
    if ($LASTEXITCODE -ne 0) { throw "Bitiful upload failed ($LASTEXITCODE)" }
}

$runtimePath = Resolve-Asset -LocalPath $RuntimeZip -AssetName $RuntimeZipName
$modelPath = Resolve-Asset -LocalPath $ModelZip -AssetName $ModelZipName

if ($DryRun) {
    Write-Host "[DryRun] Would upload runtime + model; version.txt -> $Version" -ForegroundColor DarkGray
    exit 0
}

Invoke-BitifulPython @(
    $uploadPy, $runtimePath,
    '--asset', '--endpoint-url', $endpointUrl, '--object-prefix', $objectPrefix
)
Invoke-BitifulPython @(
    $uploadPy, $modelPath,
    '--asset', '--endpoint-url', $endpointUrl, '--object-prefix', $objectPrefix
)
Invoke-BitifulPython @(
    $uploadPy, $runtimePath,
    '--write-version-only', '--endpoint-url', $endpointUrl, '--object-prefix', $objectPrefix,
    '--version', $Version
)

$base = "$endpointUrl/$($env:BITIFUL_BUCKET_NAME)/$objectPrefix"
Write-Host ''
Write-Host "Bitiful upload OK ($Version)." -ForegroundColor Green
Write-Host "  Runtime: $base/$RuntimeZipName" -ForegroundColor Cyan
Write-Host "  Model:   $base/$ModelZipName" -ForegroundColor Cyan
Write-Host "  version.txt: $base/version.txt" -ForegroundColor Cyan
