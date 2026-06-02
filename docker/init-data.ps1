$ErrorActionPreference = "Stop"

$RawBase = if ($env:OSYSHOME_RAW_BASE) { $env:OSYSHOME_RAW_BASE } else { "https://raw.githubusercontent.com/Anisan/osysHome/master" }

if ($PSScriptRoot -match '[\\/]docker$') {
    $RootDir = Resolve-Path (Join-Path $PSScriptRoot "..")
} else {
    $RootDir = $PSScriptRoot
}

Set-Location $RootDir

function Get-RemoteFileIfMissing {
    param([string]$FileName, [string]$Url)
    if (-not (Test-Path $FileName)) {
        Write-Host "[init-data] Downloading ${FileName}..."
        Invoke-WebRequest -Uri $Url -OutFile $FileName -UseBasicParsing
    }
}

New-Item -ItemType Directory -Force -Path logs, cache, files/public, files/private, files/secure, plugins | Out-Null

Get-RemoteFileIfMissing -FileName "sample_config.yaml" -Url "$RawBase/sample_config.yaml"
Get-RemoteFileIfMissing -FileName "docker-compose.yml" -Url "$RawBase/docker-compose.yml"

if (-not (Test-Path config.yaml)) {
    Copy-Item sample_config.yaml config.yaml
    Write-Host "[init-data] Created config.yaml from sample_config.yaml"
}

if (-not (Test-Path app.db)) {
    New-Item -ItemType File -Path app.db | Out-Null
    Write-Host "[init-data] Created empty app.db (SQLite will initialize on first start)"
}

Write-Host "[init-data] Data directories are ready in: $RootDir"
Write-Host "[init-data] Next: edit config.yaml, then run: docker compose up -d"
