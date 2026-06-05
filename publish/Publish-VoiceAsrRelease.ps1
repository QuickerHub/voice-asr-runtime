#!/usr/bin/env pwsh
# Build (optional) and publish voice-asr runtime + model zips to GitHub Releases.
#
# Examples:
#   pwsh ./publish/Publish-VoiceAsrRelease.ps1
#   pwsh ./publish/Publish-VoiceAsrRelease.ps1 -SkipBuild
#   pwsh ./publish/Publish-VoiceAsrRelease.ps1 -DryRun

[CmdletBinding()]
param(
    [string]$Repo = 'QuickerHub/voice-asr-runtime',
    [string]$Version = '',
    [string]$TagName = '',
    [string]$ReleaseTitle = '',
    [switch]$SkipBuild,
    [switch]$Draft,
    [switch]$DryRun
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

function Get-ProjectVersion {
    param([string]$Root)
    $DistVersionFile = Join-Path $Root 'dist' 'quicker-voice-runtime' 'runtime-version.txt'
    if (Test-Path -LiteralPath $DistVersionFile) {
        return (Get-Content -Raw -Path $DistVersionFile).Trim()
    }
    $PyProject = Join-Path $Root 'pyproject.toml'
    if (-not (Test-Path -LiteralPath $PyProject)) {
        throw "pyproject.toml not found: $PyProject"
    }
    foreach ($line in Get-Content -Path $PyProject) {
        if ($line -match '^\s*version\s*=\s*"(.+)"\s*$') {
            return $Matches[1]
        }
    }
    throw "Could not read version from pyproject.toml"
}

if (-not $Version) {
    $Version = Get-ProjectVersion -Root $RepoRoot
}
if (-not $TagName) {
    $TagName = "v$Version"
}
if (-not $ReleaseTitle) {
    $ReleaseTitle = "quicker-voice-runtime $TagName"
}

$PublishDir = Join-Path $RepoRoot 'publish'
$RuntimeZip = Join-Path $PublishDir "voice-asr-runtime-$Version-win-x64.zip"
$ModelZip = Join-Path $PublishDir "voice-asr-model-sensevoice-$Version-win-x64.zip"

if (-not $SkipBuild) {
    Write-Host '==> Building runtime (PyInstaller)' -ForegroundColor Cyan
    & (Join-Path $RepoRoot 'scripts' 'build-win.ps1')
    Write-Host '==> Packaging release zips' -ForegroundColor Cyan
    & (Join-Path $RepoRoot 'scripts' 'package-release.ps1') -Version $Version
}

foreach ($path in @($RuntimeZip, $ModelZip)) {
    if (-not (Test-Path -LiteralPath $path)) {
        throw "Missing release asset: $path (run without -SkipBuild or place zips under publish/)"
    }
}

$notes = @"
Windows voice plugin assets for QuickerAgent (quicker-voice-v1).

- ``voice-asr-runtime-$Version-win-x64.zip`` — PyInstaller runtime (~80 MB unpacked)
- ``voice-asr-model-sensevoice-$Version-win-x64.zip`` — SenseVoice int8 model (~160 MB)

Tauri one-click install reads URLs from ``agent-gui/src-tauri/resources/voice-plugin-channel.json`` in quicker-rpc.
"@

Write-Host "==> Release $TagName -> $Repo" -ForegroundColor Cyan
Write-Host "    Runtime: $RuntimeZip"
Write-Host "    Model:   $ModelZip"

if ($DryRun) {
    Write-Host 'DryRun: skipping gh release create' -ForegroundColor Yellow
    exit 0
}

if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    throw 'GitHub CLI (gh) is required.'
}

$ghArgs = @(
    'release', 'create', $TagName,
    $RuntimeZip, $ModelZip,
    '--repo', $Repo,
    '--title', $ReleaseTitle,
    '--notes', $notes
)
if ($Draft) {
    $ghArgs += '--draft'
}

& gh @ghArgs
Write-Host "==> Published https://github.com/$Repo/releases/tag/$TagName" -ForegroundColor Green
