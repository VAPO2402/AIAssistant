param(
  [switch]$Run
)

$ErrorActionPreference = 'Stop'

function Write-Info($msg){ Write-Host "[INFO] $msg" -ForegroundColor Cyan }
function Write-Err($msg){ Write-Host "[ERROR] $msg" -ForegroundColor Red }

# Ensure Python is available
$python = (Get-Command python -ErrorAction SilentlyContinue)
if(-not $python){
  Write-Err "Python not found on PATH. Install Python 3.9+ and re-run."
  exit 1
}

# Create venv
if(-not (Test-Path ".venv")){
  Write-Info "Creating virtual environment (.venv)"
  python -m venv .venv
}

# Activate venv for this session
$venvActivate = Join-Path ".venv" "Scripts\Activate.ps1"
if(Test-Path $venvActivate){
  . $venvActivate
}else{
  Write-Err "Failed to find venv activation script at $venvActivate"
  exit 1
}

# Upgrade pip
Write-Info "Upgrading pip"
python -m pip install --upgrade pip wheel setuptools

# Try installing PyAudio via pip; if it fails, try prebuilt wheel guidance
$pyaudioInstalled = $false
try{
  Write-Info "Installing dependencies from requirements.txt"
  pip install -r requirements.txt
  $pyaudioInstalled = $true
}catch{
  Write-Info "Standard install hit an error; attempting PyAudio fallback"
}

if(-not $pyaudioInstalled){
  try{
    pip install PyAudio
    $pyaudioInstalled = $true
  }catch{
    Write-Info "PyAudio installation failed. On Windows, install prebuilt wheel from https://www.lfd.uci.edu/~gohlke/pythonlibs/#pyaudio that matches your Python version and architecture, then re-run this script with -Run."
  }
}

Write-Info "Setup complete."

if($Run){
  Write-Info "Starting app"
  python inter_ass.py
}else{
  Write-Info "To run: ./setup.ps1 -Run or activate venv and python inter_ass.py"
}
