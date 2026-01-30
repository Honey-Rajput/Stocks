@echo off
REM Creates a virtual environment and installs requirements on Windows (cmd)
if not exist .venv (
    python -m venv .venv
)
.venv\Scripts\pip install --upgrade pip
.venv\Scripts\pip install -r requirements.txt
echo.
echo Installation complete. To activate the venv in this shell run:
echo    .venv\Scripts\activate
echo Then run Streamlit:
echo    streamlit run "src\app.py"
pause
