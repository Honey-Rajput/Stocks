# PowerShell script to create virtualenv and install dependencies
if (-not (Test-Path -Path .venv)) {
    python -m venv .venv
}
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
.\.venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -r requirements.txt
Write-Host "Installation complete.`nTo start the app: streamlit run 'src\app.py'"
