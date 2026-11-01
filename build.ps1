param(
    [string]$Python = "python",
    [switch]$OneFile,
    [string]$Icon = ""
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Push-Location $root
try {
    & $Python -m PyInstaller --version *> $null
    if ($LASTEXITCODE -ne 0) {
        throw "找不到 PyInstaller。請先執行：$Python -m pip install pyinstaller"
    }

    $arguments = @(
        "--noconfirm",
        "--clean",
        "--windowed",
        "--name", "PeripheralDock",
        "--paths", (Join-Path $root "src")
    )
    if ($OneFile) {
        $arguments = @("--onefile") + $arguments
    }
    if ($Icon) {
        $arguments += @("--icon", $Icon)
    }
    $arguments += (Join-Path $root "main.py")

    & $Python -m PyInstaller @arguments
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller 建置失敗（exit code $LASTEXITCODE）"
    }

    if ($OneFile) {
        Write-Host "完成：$root\dist\PeripheralDock.exe"
    }
    else {
        Write-Host "完成：$root\dist\PeripheralDock\PeripheralDock.exe"
    }
}
finally {
    Pop-Location
}
