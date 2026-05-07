# DokuCheck – lokální testovací web (Windows)
# Spusťte: pravý klik → Spustit v PowerShellu, nebo dvojklik na start_local_test.bat

$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
Set-Location $Root

function Find-PythonExe {
    foreach ($name in @("python", "python3")) {
        $cmd = Get-Command $name -ErrorAction SilentlyContinue
        if ($cmd -and $cmd.Source -notmatch "WindowsApps") {
            return $cmd.Source
        }
    }
    foreach ($ver in @(313, 312, 311, 310)) {
        $p = Join-Path $env:LOCALAPPDATA "Programs\Python\Python$ver\python.exe"
        if (Test-Path -LiteralPath $p) { return $p }
    }
    $pf = @(
        "${env:ProgramFiles}\Python312\python.exe",
        "${env:ProgramFiles}\Python311\python.exe",
        "${env:ProgramFiles(x86)}\Python312-32\python.exe"
    )
    foreach ($p in $pf) {
        if (Test-Path -LiteralPath $p) { return $p }
    }
    return $null
}

$py = Find-PythonExe
if (-not $py) {
    Write-Host ""
    Write-Host "Není nalezen Python (nebo jen zástupce ze Store)." -ForegroundColor Red
    Write-Host "Nainstalujte z https://www.python.org/downloads/" -ForegroundColor Yellow
    Write-Host "Při instalaci zaškrtněte: Add python.exe to PATH" -ForegroundColor Yellow
    Write-Host ""
    Read-Host "Stiskněte Enter pro zavření"
    exit 1
}

Write-Host "Používám: $py" -ForegroundColor Green

$venv = Join-Path $Root ".venv"
$venvPy = Join-Path $venv "Scripts\python.exe"

if (-not (Test-Path -LiteralPath $venvPy)) {
    Write-Host "Vytvářím virtuální prostředí .venv ..." -ForegroundColor Cyan
    & $py -m venv $venv
    if (-not (Test-Path -LiteralPath $venvPy)) {
        Write-Host "Nepodařilo se vytvořit .venv" -ForegroundColor Red
        Read-Host "Enter"
        exit 1
    }
}

Write-Host "Aktualizuji pip a balíčky z requirements.txt ..." -ForegroundColor Cyan
& $venvPy -m pip install -q --upgrade pip
& $venvPy -m pip install -q -r (Join-Path $Root "requirements.txt")

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  Po startu otevřete v prohlížeči:" -ForegroundColor White
Write-Host "  Náhled varianty landingu:  http://127.0.0.1:5000/landing-draft" -ForegroundColor Yellow
Write-Host "  Běžný landing:            http://127.0.0.1:5000/" -ForegroundColor Gray
Write-Host "  Ukončení: Ctrl+C" -ForegroundColor Gray
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

& $venvPy (Join-Path $Root "pdf_check_web_main.py")
