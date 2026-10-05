param(
    [Parameter(Mandatory = $true)][string]$Python,
    [Parameter(Mandatory = $true)][string]$TorchIndexUrl
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$Venv = Join-Path $ProjectRoot '.venv'

& $Python -m venv $Venv
if ($LASTEXITCODE -ne 0) { throw 'Virtual environment creation failed.' }
$VenvPython = Join-Path $Venv 'Scripts\python.exe'
& $VenvPython -m pip install --upgrade pip setuptools wheel
if ($LASTEXITCODE -ne 0) { throw 'pip bootstrap failed.' }
& $VenvPython -m pip install torch --index-url $TorchIndexUrl
if ($LASTEXITCODE -ne 0) { throw 'CUDA PyTorch installation failed.' }
& $VenvPython -m pip install -e "$ProjectRoot[test]"
if ($LASTEXITCODE -ne 0) { throw 'shape-ai installation failed.' }
& $VenvPython -c "import torch; print('torch=', torch.__version__); print('cuda=', torch.cuda.is_available()); assert torch.cuda.is_available(), 'CUDA-enabled PyTorch is required'; print('gpu=', torch.cuda.get_device_name(0))"
if ($LASTEXITCODE -ne 0) { throw 'PyTorch runtime verification failed.' }
& $VenvPython -m pytest $ProjectRoot
if ($LASTEXITCODE -ne 0) { throw 'Synthetic contract/model tests failed.' }
