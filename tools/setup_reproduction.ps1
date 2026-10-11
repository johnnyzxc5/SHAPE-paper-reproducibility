param(
    [Parameter(Mandatory = $true)][string]$Python,
    [Parameter(Mandatory = $true)][string]$Venv,
    [switch]$Install
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$VenvPath = [IO.Path]::GetFullPath($Venv)
$LockPath = Join-Path $RepoRoot 'requirements\reproduction-win64-py312.lock'
if (-not $Install) {
    Write-Output "PLAN ONLY: create Python 3.12 Windows x64 environment at $VenvPath"
    Write-Output 'Install torch==2.14.0+cu130 from https://download.pytorch.org/whl/cu130'
    Write-Output "Install pinned dependencies from $LockPath, then this checkout's shape-ai package."
    Write-Output 'No environment created, dependencies installed, MATLAB called, or training started.'
    exit 0
}
if (Test-Path -LiteralPath $VenvPath) { throw 'Choose a new environment directory; existing environments are preserved.' }
& $Python -c "import struct,sys; assert sys.platform=='win32' and sys.version_info[:2]==(3,12) and struct.calcsize('P')==8, 'Requires Windows x64 Python 3.12'"
if ($LASTEXITCODE -ne 0) { throw 'Python platform/version differs from the selected version profile.' }
& $Python -m venv $VenvPath
if ($LASTEXITCODE -ne 0) { throw 'Environment creation failed.' }
$VenvPython = Join-Path $VenvPath 'Scripts\python.exe'
& $VenvPython -m pip install 'torch==2.14.0+cu130' --index-url 'https://download.pytorch.org/whl/cu130'
if ($LASTEXITCODE -ne 0) { throw 'Pinned CUDA PyTorch installation failed.' }
& $VenvPython -m pip install -r $LockPath
if ($LASTEXITCODE -ne 0) { throw 'Pinned dependency installation failed.' }
$PackageRoot = Join-Path $RepoRoot 'Fault_Diagnosis\shape_ai'
& $VenvPython -m pip install --no-deps --no-build-isolation -e $PackageRoot
if ($LASTEXITCODE -ne 0) { throw 'Local package installation failed.' }
& $VenvPython -m pip check
if ($LASTEXITCODE -ne 0) { throw 'Dependency consistency check failed.' }
& $VenvPython (Join-Path $PSScriptRoot 'check_reproduction.py') --environment
if ($LASTEXITCODE -ne 0) { throw 'Static environment audit failed.' }
