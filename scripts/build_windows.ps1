param([switch]$SkipInstall)
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)
if (-not $IsWindows -and $env:OS -ne "Windows_NT") {
    throw "Portable Windows builds must run on Windows."
}
if (-not $SkipInstall) {
    python -m pip install -r requirements-dev.txt
    if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed." }
}
python -m PyInstaller --noconfirm --clean Screen.spec
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed." }
Copy-Item README.md, THIRD_PARTY_NOTICES.md dist/Screen/
Copy-Item licenses dist/Screen/licenses -Recurse -Force
python scripts/collect_notices.py dist/Screen/licenses
if ($LASTEXITCODE -ne 0) { throw "Collecting dependency notices failed." }
$report = Join-Path (Get-Location) "dist/smoke-report.json"
$process = Start-Process -FilePath "dist/Screen/Screen.exe" -ArgumentList @(
    "--smoke-test", "--smoke-report", "`"$report`""
) -PassThru
if (-not $process.WaitForExit(30000)) {
    $process.Kill()
    throw "Packaged Screen.exe did not exit within 30 seconds."
}
if ($process.ExitCode -ne 0 -or -not (Test-Path $report)) {
    throw "Packaged Screen.exe smoke test failed (exit $($process.ExitCode))."
}
$smoke = Get-Content $report -Raw | ConvertFrom-Json
if (-not $smoke.ok) { throw $smoke.error }
Compress-Archive -Path dist/Screen -DestinationPath dist/Screen-windows-x64.zip -Force
$hash = (Get-FileHash dist/Screen-windows-x64.zip -Algorithm SHA256).Hash.ToLowerInvariant()
Set-Content -Path dist/Screen-windows-x64.zip.sha256 -Value "$hash  Screen-windows-x64.zip"
Write-Output "Portable build and packaged smoke test passed: dist/Screen-windows-x64.zip"
