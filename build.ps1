<#
.SYNOPSIS
    Build a Windows release of Spoteye: release\Spoteye-<version>-win64.zip

.DESCRIPTION
    1. Python deps + backend tests       5. PyInstaller (backend\spoteye.spec, onedir)
    2. Frontend build (npm ci + build)   6. Copy tools into dist\Spoteye\bin, collect licenses, README
    3. Download + verify tools            7. Smoke test the built exe with a throwaway data folder
       (yt-dlp, Deno, FFmpeg LGPL)        8. Zip + SHA-256
    4. Optional baked-in Client ID

    Works in Windows PowerShell 5.1 and PowerShell 7. Run from anywhere:  .\build.ps1

.PARAMETER ClientId
    32-hex Spotify Client ID to ship as the default (for friends you added under User Management).
.PARAMETER RefreshTools
    Re-download yt-dlp, Deno and FFmpeg even if build\tools already has them.
.PARAMETER SkipTests
    Skip the backend test suite (not recommended for a release).
.PARAMETER SkipSmoke
    Skip starting the built exe for the health check.
#>
[CmdletBinding()]
param(
    [ValidatePattern('^([0-9a-f]{32})?$')]
    [string]$ClientId = '',
    [switch]$RefreshTools,
    [switch]$SkipTests,
    [switch]$SkipSmoke
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'   # Invoke-WebRequest is ~10x slower with the progress bar in 5.1
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$Root      = $PSScriptRoot
$Backend   = Join-Path $Root 'backend'
$Frontend  = Join-Path $Root 'frontend'
$BuildDir  = Join-Path $Root 'build'
$ToolsDir  = Join-Path $BuildDir 'tools'
$ToolLic   = Join-Path $ToolsDir 'licenses'
$DistDir   = Join-Path $Root 'dist'
$AppDir    = Join-Path $DistDir 'Spoteye'
$ReleaseDir = Join-Path $Root 'release'
$Py        = Join-Path $Backend '.venv\Scripts\python.exe'

function Step([string]$text) { Write-Host "`n==> $text" -ForegroundColor Cyan }
function Fail([string]$text) { throw "BUILD FAILED: $text" }

function Invoke-Checked {
    # Run a native command and stop on a non-zero exit code (5.1 doesn't do this by itself).
    param([string]$What, [scriptblock]$Command)
    & $Command
    if ($LASTEXITCODE -ne 0) { Fail "$What (exit code $LASTEXITCODE)" }
}

function Get-Url([string]$Url, [string]$OutFile) {
    Write-Host "    download $Url"
    Invoke-WebRequest -Uri $Url -OutFile $OutFile -UseBasicParsing -Headers @{ 'User-Agent' = 'spoteye-build' }
}

function Get-Text([string]$Url) {
    $content = (Invoke-WebRequest -Uri $Url -UseBasicParsing -Headers @{ 'User-Agent' = 'spoteye-build' }).Content
    # Windows PowerShell 5.1 returns byte[] for application/octet-stream (GitHub release assets).
    if ($content -is [byte[]]) { return [System.Text.Encoding]::UTF8.GetString($content) }
    return [string]$content
}

function Find-Sha256([string]$Text, [string]$FileName) {
    # Works for "hash  name" lines (sha256sum) and Get-FileHash style output: the first 64-hex
    # token on the line that names the file, or anywhere if no line names it.
    $lines = $Text -split "`r?`n"
    if ($FileName) {
        $named = $lines | Where-Object { $_ -match [regex]::Escape($FileName) }
        foreach ($line in $named) {
            if ($line -match '\b([0-9a-fA-F]{64})\b') { return $Matches[1].ToLower() }
        }
    }
    if ($Text -match '\b([0-9a-fA-F]{64})\b') { return $Matches[1].ToLower() }
    Fail "no SHA-256 found in checksum text for $FileName"
}

function Assert-Sha256([string]$Path, [string]$Expected) {
    $actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $Path).Hash.ToLower()
    if ($actual -ne $Expected) { Fail "checksum mismatch for $(Split-Path $Path -Leaf): expected $Expected, got $actual" }
    Write-Host "    sha256 ok  $(Split-Path $Path -Leaf)"
}

function Get-FreePort {
    $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, 0)
    $listener.Start(); $port = $listener.LocalEndpoint.Port; $listener.Stop()
    return $port
}

# ---------------------------------------------------------------------------------------------
Step 'Checks'
$Version = (Get-Content (Join-Path $Root 'VERSION') -Raw).Trim()
if ($Version -notmatch '^\d+\.\d+\.\d+$') { Fail "VERSION must look like 1.2.3, got '$Version'" }
if (-not (Test-Path $Py)) { Fail "backend venv not found: $Py (cd backend; python -m venv .venv)" }
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) { Fail 'npm not found (install Node 20+)' }
$License = Join-Path $Root 'LICENSE'
if (-not (Test-Path $License)) {
    Fail ("LICENSE is missing. Spoteye bundles mutagen (GPL-2.0+), so ship it under GPL-3.0:`n" +
          "    Invoke-WebRequest https://www.gnu.org/licenses/gpl-3.0.txt -OutFile LICENSE   (then commit it)")
}
Write-Host "    Spoteye $Version"

# ---------------------------------------------------------------------------------------------
Step 'Python dependencies'
Invoke-Checked 'pip install' { & $Py -m pip install --disable-pip-version-check -q -r (Join-Path $Backend 'requirements-dev.txt') }

if (-not $SkipTests) {
    Step 'Backend tests'
    Push-Location $Backend
    try { Invoke-Checked 'pytest' { & $Py -m pytest -q } } finally { Pop-Location }
}

# ---------------------------------------------------------------------------------------------
Step 'Frontend build'
Invoke-Checked 'npm ci'        { npm --prefix $Frontend ci --no-audit --no-fund }
Invoke-Checked 'npm run build' { npm --prefix $Frontend run build }
if (-not (Test-Path (Join-Path $Frontend 'dist\index.html'))) { Fail 'frontend\dist\index.html was not produced' }

# ---------------------------------------------------------------------------------------------
Step 'Tools (yt-dlp, Deno, FFmpeg)'
New-Item -ItemType Directory -Force -Path $ToolsDir, $ToolLic | Out-Null
$YtDlp  = Join-Path $ToolsDir 'yt-dlp.exe'
$Deno   = Join-Path $ToolsDir 'deno.exe'
$Ffmpeg = Join-Path $ToolsDir 'ffmpeg.exe'
$Versions = @{}
$VersionsFile = Join-Path $ToolsDir 'versions.json'
if ((Test-Path $VersionsFile) -and -not $RefreshTools) {
    $saved = Get-Content $VersionsFile -Raw | ConvertFrom-Json
    $saved.PSObject.Properties | ForEach-Object { $Versions[$_.Name] = $_.Value }
}
$Tmp = Join-Path $BuildDir 'tmp'
if (Test-Path $Tmp) { Remove-Item $Tmp -Recurse -Force }
New-Item -ItemType Directory -Force -Path $Tmp | Out-Null

# yt-dlp: single exe + SHA2-256SUMS from the same release. Downloaded to $Tmp and moved into
# build\tools only after the checksum and license succeed, so a failed run never leaves a cached,
# unverified exe that the next run would reuse.
if ($RefreshTools -or -not (Test-Path $YtDlp) -or -not (Test-Path (Join-Path $ToolLic 'yt-dlp-LICENSE.txt'))) {
    $base = 'https://github.com/yt-dlp/yt-dlp/releases/latest/download'
    $download = Join-Path $Tmp 'yt-dlp.exe'
    Get-Url "$base/yt-dlp.exe" $download
    Assert-Sha256 $download (Find-Sha256 (Get-Text "$base/SHA2-256SUMS") 'yt-dlp.exe')
    Get-Url 'https://raw.githubusercontent.com/yt-dlp/yt-dlp/master/LICENSE' (Join-Path $ToolLic 'yt-dlp-LICENSE.txt')
    Move-Item $download $YtDlp -Force
}
$Versions['yt-dlp'] = (& $YtDlp --version).Trim()

# Deno: zip + .sha256sum next to it
if ($RefreshTools -or -not (Test-Path $Deno)) {
    $asset = 'deno-x86_64-pc-windows-msvc.zip'
    $base = 'https://github.com/denoland/deno/releases/latest/download'
    $zip = Join-Path $Tmp $asset
    Get-Url "$base/$asset" $zip
    Assert-Sha256 $zip (Find-Sha256 (Get-Text "$base/$asset.sha256sum") $asset)
    Expand-Archive -LiteralPath $zip -DestinationPath (Join-Path $Tmp 'deno') -Force
    Copy-Item (Join-Path $Tmp 'deno\deno.exe') $Deno -Force
    Get-Url 'https://raw.githubusercontent.com/denoland/deno/main/LICENSE.md' (Join-Path $ToolLic 'deno-LICENSE.md')
}
$Versions['deno'] = ((& $Deno --version) | Select-Object -First 1).Trim()

# FFmpeg: BtbN static LGPL build from a stable branch (never "gpl", never "shared")
if ($RefreshTools -or -not (Test-Path $Ffmpeg)) {
    $release = Invoke-RestMethod -Uri 'https://api.github.com/repos/BtbN/FFmpeg-Builds/releases/tags/latest' `
                                 -Headers @{ 'User-Agent' = 'spoteye-build' }
    $candidates = foreach ($a in $release.assets) {
        if ($a.name -match '^ffmpeg-n(\d+)\.(\d+)-latest-win64-lgpl-\d+\.\d+\.zip$') {
            [pscustomobject]@{ Asset = $a; Major = [int]$Matches[1]; Minor = [int]$Matches[2] }
        }
    }
    $pick = $candidates | Sort-Object Major, Minor -Descending | Select-Object -First 1
    if (-not $pick) { Fail 'no ffmpeg-n*-latest-win64-lgpl-*.zip asset found in BtbN/FFmpeg-Builds latest release' }
    $name = $pick.Asset.name
    $sums = $release.assets | Where-Object { $_.name -eq 'checksums.sha256' } | Select-Object -First 1
    if (-not $sums) { Fail 'checksums.sha256 not found in the BtbN release' }
    $zip = Join-Path $Tmp $name
    Get-Url $pick.Asset.browser_download_url $zip
    Assert-Sha256 $zip (Find-Sha256 (Get-Text $sums.browser_download_url) $name)
    $out = Join-Path $Tmp 'ffmpeg'
    Expand-Archive -LiteralPath $zip -DestinationPath $out -Force
    $exe = Get-ChildItem $out -Recurse -Filter 'ffmpeg.exe' | Where-Object { $_.Directory.Name -eq 'bin' } | Select-Object -First 1
    if (-not $exe) { Fail "ffmpeg.exe not found inside $name" }
    Copy-Item $exe.FullName $Ffmpeg -Force
    $lic = Get-ChildItem $out -Recurse -Filter 'LICENSE*' | Select-Object -First 1
    if ($lic) { Copy-Item $lic.FullName (Join-Path $ToolLic 'ffmpeg-LICENSE.txt') -Force }
    @(
        "FFmpeg build: $name",
        'Licensed under the GNU LGPL v2.1 or later (this is an LGPL build: no GPL-only components).',
        'Build scripts: https://github.com/BtbN/FFmpeg-Builds',
        'FFmpeg source code: https://ffmpeg.org/download.html',
        "Downloaded: $(Get-Date -Format 'yyyy-MM-dd')"
    ) | Set-Content (Join-Path $ToolLic 'ffmpeg-BUILD.txt') -Encoding UTF8
    $Versions['ffmpeg-asset'] = $name
}
$encoders = (& $Ffmpeg -hide_banner -encoders) -join "`n"
foreach ($enc in 'libmp3lame', 'libopus', 'aac') {
    if ($encoders -notmatch "(?m)^\s*A\S*\s+$enc\s") { Fail "ffmpeg is missing the '$enc' encoder (Spoteye needs libmp3lame, libopus and aac)" }
}
$Versions['ffmpeg'] = ((& $Ffmpeg -hide_banner -version) | Select-Object -First 1).Trim()
$Versions | ConvertTo-Json | Set-Content $VersionsFile -Encoding UTF8
$Versions.GetEnumerator() | Sort-Object Name | ForEach-Object { Write-Host ("    {0,-13} {1}" -f $_.Name, $_.Value) }

# ---------------------------------------------------------------------------------------------
Step 'Baked-in defaults'
$Defaults = Join-Path $BuildDir 'defaults.json'
if ($ClientId) {
    @{ spotify_client_id = $ClientId } | ConvertTo-Json | Set-Content $Defaults -Encoding UTF8
    Write-Host '    Client ID will ship as the default (friends must be added under User Management).'
} elseif (Test-Path $Defaults) {
    Remove-Item $Defaults -Force
    Write-Host '    No Client ID: users enter their own on first run.'
} else {
    Write-Host '    No Client ID: users enter their own on first run.'
}

# ---------------------------------------------------------------------------------------------
Step 'PyInstaller'
if (Test-Path $AppDir) { Remove-Item $AppDir -Recurse -Force }
Invoke-Checked 'PyInstaller' {
    & $Py -m PyInstaller (Join-Path $Backend 'spoteye.spec') --noconfirm --clean `
        --distpath $DistDir --workpath (Join-Path $BuildDir 'pyi')
}
if (-not (Test-Path (Join-Path $AppDir 'Spoteye.exe'))) { Fail 'dist\Spoteye\Spoteye.exe was not produced' }

# ---------------------------------------------------------------------------------------------
Step 'Assemble dist\Spoteye'
$Bin = Join-Path $AppDir 'bin'
New-Item -ItemType Directory -Force -Path $Bin | Out-Null
Copy-Item $YtDlp, $Deno, $Ffmpeg $Bin -Force

$Licenses = Join-Path $AppDir 'licenses'
New-Item -ItemType Directory -Force -Path (Join-Path $Licenses 'tools') | Out-Null
Copy-Item (Join-Path $ToolLic '*') (Join-Path $Licenses 'tools') -Force
Invoke-Checked 'collect licenses' {
    & $Py -I (Join-Path $Root 'packaging\collect_licenses.py') (Join-Path $Backend 'requirements.txt') (Join-Path $Licenses 'python')
}
Copy-Item $License (Join-Path $AppDir 'LICENSE.txt') -Force

$readme = (Get-Content (Join-Path $Root 'packaging\README.txt') -Raw).Replace('{VERSION}', $Version)
Set-Content (Join-Path $AppDir 'README.txt') $readme -Encoding UTF8
$Version | Set-Content (Join-Path $AppDir 'VERSION.txt') -Encoding ASCII

# ---------------------------------------------------------------------------------------------
if (-not $SkipSmoke) {
    Step 'Smoke test'
    $port = Get-FreePort
    $home_ = Join-Path ([System.IO.Path]::GetTempPath()) ("spoteye-smoke-" + [guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $home_ | Out-Null
    $oldHome = $env:SPOTEYE_HOME
    $env:SPOTEYE_HOME = $home_
    $proc = $null
    try {
        $proc = Start-Process -FilePath (Join-Path $AppDir 'Spoteye.exe') `
            -ArgumentList 'serve', '--no-browser', '--port', "$port" -PassThru -WindowStyle Hidden `
            -RedirectStandardOutput (Join-Path $home_ 'stdout.txt') -RedirectStandardError (Join-Path $home_ 'stderr.txt')
        $health = $null
        $deadline = (Get-Date).AddSeconds(45)
        while ((Get-Date) -lt $deadline -and -not $health) {
            if ($proc.HasExited) { break }
            try { $health = Invoke-RestMethod "http://127.0.0.1:$port/api/health" -TimeoutSec 3 } catch { Start-Sleep -Milliseconds 500 }
        }
        if (-not $health) {
            $log = (Get-Content (Join-Path $home_ 'stderr.txt'), (Join-Path $home_ 'stdout.txt') -ErrorAction SilentlyContinue) -join "`n"
            Fail "the built exe did not answer /api/health on port $port within 45 s.`n$log"
        }
        $checks = [ordered]@{
            'app is spoteye'      = ($health.app -eq 'spoteye')
            'frozen'              = ($health.frozen -eq $true)
            'ffmpeg found'        = ($health.ffmpeg -eq $true)
            'deno found'          = ($health.deno -eq $true)
            'yt-dlp binary mode'  = ($health.yt_dlp_mode -eq 'binary')
            'sign-in is missing'  = ($health.spotify_auth -eq 'missing')   # fresh data folder
        }
        $page = Invoke-WebRequest "http://127.0.0.1:$port/" -UseBasicParsing -TimeoutSec 5
        $checks['UI served'] = ($page.StatusCode -eq 200 -and $page.Content -match '<div id="root">')
        $checks['data in SPOTEYE_HOME'] = (Test-Path (Join-Path $home_ 'spoteye.db'))
        $bad = @($checks.GetEnumerator() | Where-Object { -not $_.Value } | ForEach-Object { $_.Key })
        $checks.GetEnumerator() | ForEach-Object { Write-Host ("    {0} {1}" -f ($(if ($_.Value) { 'ok  ' } else { 'FAIL' })), $_.Key) }
        Write-Host "    yt-dlp $($health.yt_dlp_version)"
        if ($bad.Count) { Fail "smoke test: $($bad -join ', ')" }
    } finally {
        if ($proc -and -not $proc.HasExited) {
            Stop-Process -Id $proc.Id -Force
            $proc.WaitForExit(10000) | Out-Null
        }
        $env:SPOTEYE_HOME = $oldHome
        for ($i = 0; $i -lt 10 -and (Test-Path $home_); $i++) {
            try { Remove-Item $home_ -Recurse -Force -ErrorAction Stop } catch { Start-Sleep -Milliseconds 500 }
        }
    }
}

# ---------------------------------------------------------------------------------------------
Step 'Zip'
New-Item -ItemType Directory -Force -Path $ReleaseDir | Out-Null
$Zip = Join-Path $ReleaseDir "Spoteye-$Version-win64.zip"
if (Test-Path $Zip) { Remove-Item $Zip -Force }
Compress-Archive -Path $AppDir -DestinationPath $Zip -CompressionLevel Optimal
$hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $Zip).Hash.ToLower()
"$hash  $(Split-Path $Zip -Leaf)" | Set-Content "$Zip.sha256" -Encoding ASCII
Remove-Item $Tmp -Recurse -Force -ErrorAction SilentlyContinue

$sizeMb = [math]::Round((Get-Item $Zip).Length / 1MB, 1)
Write-Host ''
Write-Host "Built $Zip ($sizeMb MB)" -ForegroundColor Green
Write-Host "SHA-256 $hash"
