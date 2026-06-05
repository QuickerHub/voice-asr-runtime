#!/usr/bin/env pwsh
# Build (optional), publish GitHub Release, optional Bitiful mirror, optional channel.json sync.
#
# Examples:
#   pwsh ./publish/Publish-VoiceAsrRelease.ps1
#   pwsh ./publish/Publish-VoiceAsrRelease.ps1 -SkipBuild -UploadBitiful -UpdateChannelJson
#   pwsh ./publish/Publish-VoiceAsrRelease.ps1 -DryRun

[CmdletBinding()]
param(
    [string]$Repo = 'QuickerHub/voice-asr-runtime',
    [string]$Version = '',
    [string]$TagName = '',
    [string]$ReleaseTitle = '',
    [string]$MonorepoRoot = '',
    [switch]$SkipBuild,
    [switch]$UploadBitiful,
    [switch]$UpdateChannelJson,
    [switch]$ForceRetag,
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

function Publish-GitHubReleaseAssets {
    param(
        [string]$Tag,
        [string]$Title,
        [string]$Notes,
        [string[]]$Assets,
        [string]$Repository,
        [switch]$IsDraft,
        [switch]$AllowRetag
    )

    if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
        throw 'GitHub CLI (gh) is required.'
    }

    $existing = gh release view $Tag --repo $Repository 2>$null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "==> Release $Tag exists — uploading assets (--clobber)" -ForegroundColor Cyan
        & gh release upload $Tag @Assets --repo $Repository --clobber
        if ($LASTEXITCODE -ne 0) {
            throw 'gh release upload failed'
        }
        return
    }

    if ($AllowRetag) {
        gh api -X DELETE "repos/$Repository/git/refs/tags/$Tag" 2>$null | Out-Null
    }

    $createArgs = @('release', 'create', $Tag) + $Assets + @(
        '--repo', $Repository,
        '--title', $Title,
        '--notes', $Notes
    )
    if ($IsDraft) {
        $createArgs += '--draft'
    }

    & gh @createArgs
    if ($LASTEXITCODE -ne 0) {
        throw 'gh release create failed'
    }
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
if (-not $MonorepoRoot) {
    $candidate = Join-Path $RepoRoot '..'
    $channelProbe = Join-Path $candidate 'agent-gui/src-tauri/resources/voice-plugin-channel.json'
    if (Test-Path -LiteralPath $channelProbe) {
        $MonorepoRoot = (Resolve-Path -LiteralPath $candidate).Path
    }
}

$PublishDir = Join-Path $RepoRoot 'publish'
$RuntimeZip = Join-Path $PublishDir "voice-asr-runtime-$Version-win-x64.zip"
$ModelZip = Join-Path $PublishDir "voice-asr-model-sensevoice-$Version-win-x64.zip"
$ManifestPath = Join-Path $PublishDir 'voice-plugin-channel.generated.json'
$BitifulPrefix = 'https://s3.bitiful.net/quicker-pkgs/quicker-rpc/voice-asr'
$manifestScript = Join-Path $PSScriptRoot 'Write-VoicePluginChannelManifest.ps1'

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

& pwsh -NoProfile -File $manifestScript -Version $Version -Tag $TagName -OutputPath $ManifestPath | Out-Null

$runtimeMb = [math]::Round((Get-Item $RuntimeZip).Length / 1MB, 1)
$modelMb = [math]::Round((Get-Item $ModelZip).Length / 1MB, 1)

$notes = @"
Windows voice plugin assets for QuickerAgent (quicker-voice-v1).

| Asset | Size (approx) |
|-------|---------------|
| ``voice-asr-runtime-$Version-win-x64.zip`` | ~$runtimeMb MB |
| ``voice-asr-model-sensevoice-$Version-win-x64.zip`` | ~$modelMb MB |

Domestic mirror (Bitiful): ``$BitifulPrefix/``

Attach ``voice-plugin-channel.generated.json`` for QuickerAgent ``voice-plugin-channel.json`` sync.
"@

Write-Host "==> Release $TagName -> $Repo" -ForegroundColor Cyan
Write-Host "    Runtime: $RuntimeZip"
Write-Host "    Model:   $ModelZip"
Write-Host "    Manifest: $ManifestPath"

if ($DryRun) {
    Write-Host 'DryRun: skipping GitHub / Bitiful / channel sync' -ForegroundColor Yellow
    exit 0
}

Publish-GitHubReleaseAssets `
    -Tag $TagName `
    -Title $ReleaseTitle `
    -Notes $notes `
    -Assets @($RuntimeZip, $ModelZip, $ManifestPath) `
    -Repository $Repo `
    -IsDraft:$Draft `
    -AllowRetag:$ForceRetag

Write-Host "==> Published https://github.com/$Repo/releases/tag/$TagName" -ForegroundColor Green

if ($UpdateChannelJson) {
    if (-not $MonorepoRoot) {
        throw '-UpdateChannelJson requires quicker-rpc monorepo (agent-gui/src-tauri/resources/voice-plugin-channel.json).'
    }
    $syncScript = Join-Path $MonorepoRoot 'publish/Sync-VoicePluginChannel.ps1'
    if (-not (Test-Path -LiteralPath $syncScript)) {
        throw "Missing sync script: $syncScript"
    }
    Write-Host '==> Syncing voice-plugin-channel.json in quicker-rpc' -ForegroundColor Cyan
    & pwsh -NoProfile -File $syncScript -Version $Version -Tag $TagName -VoiceRoot $RepoRoot
    if ($LASTEXITCODE -ne 0) {
        throw 'Sync-VoicePluginChannel failed'
    }
}
elseif ($MonorepoRoot) {
    Write-Host ""
    Write-Host "Tip: sync channel.json:" -ForegroundColor Yellow
    Write-Host "  pwsh -NoProfile -File `"$(Join-Path $MonorepoRoot 'publish/Sync-VoicePluginChannel.ps1')`" -Version $Version -Tag $TagName"
}

if ($UploadBitiful) {
    $uploadScript = Join-Path $PSScriptRoot 'Upload-VoiceAsrToBitiful.ps1'
    if (-not (Test-Path -LiteralPath $uploadScript)) {
        $uploadScript = Join-Path $MonorepoRoot 'publish/Upload-VoiceAsrToBitiful.ps1'
    }
    if (-not (Test-Path -LiteralPath $uploadScript)) {
        throw 'Upload-VoiceAsrToBitiful.ps1 not found (voice-asr-runtime/publish or quicker-rpc/publish).'
    }
    Write-Host ""
    Write-Host '==> Uploading to Bitiful (domestic mirror)' -ForegroundColor Cyan
    if ($MonorepoRoot) {
        & pwsh -NoProfile -File $uploadScript -RepoRoot $MonorepoRoot -Version $Version -Tag $TagName -UseLocalVoiceRoot
    }
    else {
        & pwsh -NoProfile -File $uploadScript -Version $Version -Tag $TagName -UseLocalVoiceRoot
    }
    if ($LASTEXITCODE -ne 0) {
        throw 'Bitiful upload failed'
    }
}
