param(
    [string]$LocalSource = ".\demo-data",
    [string]$RemoteTarget = "/backups/demo-data",
    [string]$RestoreTarget = ".\demo-restore",
    [switch]$SkipCompare,
    [switch]$SkipRestore
)

function Assert-BypyInstalled {
    $command = Get-Command bypy -ErrorAction SilentlyContinue
    if (-not $command) {
        throw "bypy is not installed or not available on PATH. Run 'pip install bypy' first."
    }
}

function Invoke-BypyCommand {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )

    Write-Host ("`n> bypy " + ($Arguments -join " ")) -ForegroundColor Cyan
    & bypy @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "bypy command failed with exit code $LASTEXITCODE"
    }
}

Assert-BypyInstalled

Write-Host "This demo assumes bypy has already been authorized." -ForegroundColor Yellow
Write-Host "Remote operations are limited to the /apps/bypy directory on Baidu Netdisk." -ForegroundColor Yellow

if (-not (Test-Path $LocalSource)) {
    throw "Local source path not found: $LocalSource"
}

if (-not $SkipCompare) {
    Invoke-BypyCommand -Arguments @("compare", $RemoteTarget, $LocalSource)
}

Invoke-BypyCommand -Arguments @("mkdir", "/backups")
Invoke-BypyCommand -Arguments @("syncup", $LocalSource, $RemoteTarget)

if (-not $SkipRestore) {
    if (-not (Test-Path $RestoreTarget)) {
        New-Item -ItemType Directory -Path $RestoreTarget | Out-Null
    }
    Invoke-BypyCommand -Arguments @("syncdown", $RemoteTarget, $RestoreTarget)
}

Write-Host "`nBackup and restore demo completed." -ForegroundColor Green
