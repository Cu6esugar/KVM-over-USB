# Nuitka onefile build script for Mini-KVM.
#
# Nuitka / depends.exe / MSVC link.exe corrupt non-ASCII (e.g. Chinese) paths,
# so when the project lives under such a path this script transparently:
#   1. syncs the source tree to a pure-ASCII copy (D:\MyWorkspace\KVM-over-USB),
#   2. makes sure a venv exists there (copied once from the original),
#   3. runs the build there,
#   4. copies the resulting exe back into the original Mini-KVM-Client folder.
# When the current path is already pure ASCII it builds in place as before.

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir

$AsciiBuildRoot = "D:\MyWorkspace\KVM-over-USB"
$AsciiBuildClient = Join-Path $AsciiBuildRoot "client"

function Test-AsciiPath([string]$path) {
    foreach ($ch in $path.ToCharArray()) {
        if ([int]$ch -gt 127) { return $false }
    }
    return $true
}

$BuildDir = $ScriptDir
$SyncNeeded = $false

if (-not (Test-AsciiPath $ScriptDir)) {
    Write-Host "[compiler] Source path contains non-ASCII characters:"
    Write-Host "  $ScriptDir"
    Write-Host "[compiler] Building in ASCII copy: $AsciiBuildClient"
    $SyncNeeded = $true
    $BuildDir = $AsciiBuildClient
}

if ($SyncNeeded) {
    # Sync source tree (keep venv / build output / .git out)
    robocopy $ProjectRoot $AsciiBuildRoot /E /XD venv build_console Mini-KVM-Client .git /NFL /NDL /NJH /NP /R:1 /W:1 | Out-Null
    if ($LASTEXITCODE -ge 8) { throw "robocopy source sync failed ($LASTEXITCODE)" }

    # Make sure the ASCII copy has a venv (copy once from the original)
    if (-not (Test-Path (Join-Path $AsciiBuildClient "venv\Scripts\python.exe"))) {
        Write-Host "[compiler] Copying venv to ASCII path (first run only)..."
        robocopy (Join-Path $ScriptDir "venv") (Join-Path $AsciiBuildClient "venv") /E /NFL /NDL /NJH /NP /R:1 /W:1 | Out-Null
        if ($LASTEXITCODE -ge 8) { throw "robocopy venv sync failed ($LASTEXITCODE)" }
    }
}

$Python = Join-Path $BuildDir "venv\Scripts\python.exe"
if (-not (Test-Path $Python)) { throw "venv python not found: $Python" }

$NuitkaArgs = @(
    "-m", "nuitka",
    "--windows-disable-console",
    "--show-progress",
    "--standalone",
    "--enable-plugin=pyside6",
    "--output-dir=build_console",
    "--windows-icon-from-ico=.\icons\icon.ico",
    "--jobs=16",
    ".\Mini-KVM.py",
    "--include-data-dir=.\icons=icons",
    "--include-data-dir=.\web=web",
    "--include-data-dir=.\web_s=web_s",
    "--include-data-dir=.\data=data",
    "--onefile-windows-splash-screen-image=booting.png",
    "--include-data-files=trans_cn.qm=trans_cn.qm",
    "--include-data-files=qtbase_cn.qm=qtbase_cn.qm",
    "--include-qt-plugins=multimedia",
    "--onefile",
    "--quiet",
    "--noinclude-qt-translations",
    "--noinclude-dlls=libQt6Charts*",
    "--noinclude-dlls=libQt6Quick3D*",
    "--noinclude-dlls=libQt6Sensors*",
    "--noinclude-dlls=libQt6Test*",
    "--noinclude-dlls=libQt6WebEngine*",
    "--noinclude-dlls=qt6web*",
    "--noinclude-dlls=qt6pdf*",
    "--include-package=pyWinhook"
)

Push-Location $BuildDir
try {
    & $Python @NuitkaArgs
    if ($LASTEXITCODE -ne 0) { throw "Nuitka build failed with exit code $LASTEXITCODE" }
}
finally {
    Pop-Location
}

$BuiltExe = Join-Path $BuildDir "build_console\Mini-KVM.exe"
if (-not (Test-Path $BuiltExe)) { throw "expected output not found: $BuiltExe" }

$OutputDir = Join-Path $ScriptDir "Mini-KVM-Client"
New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null
Copy-Item -Path $BuiltExe -Destination (Join-Path $OutputDir "Mini-KVM.exe") -Force
Write-Host "[compiler] Done: $OutputDir\Mini-KVM.exe"
