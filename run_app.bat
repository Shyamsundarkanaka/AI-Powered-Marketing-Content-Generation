@echo off
cd /d "%~dp0"

if not exist venv\Scripts\activate.bat (
    echo Virtual environment not found at venv\
    echo Run setup first:
    echo   python -m venv venv
    echo   venv\Scripts\activate
    echo   pip install -r requirements.txt
    pause
    exit /b 1
)

if not exist .env (
    echo No .env found. Copying .env.example - add your API key before running.
    copy .env.example .env >nul
    notepad .env
)

call venv\Scripts\activate.bat

rem Seeding is idempotent: the url column is UNIQUE, so a re-run adds nothing.
python -m database.seed_products

streamlit run streamlit_app\app.py

echo.
echo Streamlit has stopped. Press any key to close this window.
pause >nul
