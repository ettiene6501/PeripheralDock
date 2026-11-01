param(
    [string]$Python = "python",
    [switch]$Minimized
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Push-Location $root
try {
    $env:PYTHONPATH = Join-Path $root "src"
    $arguments = @((Join-Path $root "main.py"), "run")
    if ($Minimized) {
        $arguments += "--minimized"
    }
    & $Python @arguments
}
finally {
    Pop-Location
}
