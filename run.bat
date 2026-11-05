@echo off
setlocal
chcp 65001 > nul

echo ============================================================
echo    Comparateur QCM PDF - Lancement
echo ============================================================
echo.

set UV=%USERPROFILE%\.local\bin\uv.exe

REM --- Verifier uv ---
if not exist "%UV%" (
    echo [INFO] uv non trouve, recherche de Python...
    goto :find_python
)

REM --- Creer le venv avec uv si absent ---
if not exist ".venv\Scripts\python.exe" (
    echo Creation de l'environnement virtuel avec uv...
    "%UV%" venv .venv --python 3.11
    echo Installation des dependances...
    "%UV%" pip install --python .venv\Scripts\python.exe PyMuPDF opencv-python Pillow numpy reportlab
    if errorlevel 1 (
        echo [ERREUR] Installation echouee.
        pause
        exit /b 1
    )
    echo [OK] Dependances installees.
)
goto :launch

:find_python
REM --- Recherche de Python sans uv ---
set PYTHON=
for %%P in (
    "%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
    "C:\Python313\python.exe"
    "C:\Python312\python.exe"
    "C:\Python311\python.exe"
    "C:\Python310\python.exe"
) do (
    if exist %%P (
        set PYTHON=%%P
        goto :create_venv
    )
)

where py >nul 2>&1
if %errorlevel%==0 (
    set PYTHON=py
    goto :create_venv
)

echo [ERREUR] Python 3.10+ requis. Telechargez-le sur https://www.python.org/
pause
exit /b 1

:create_venv
if not exist ".venv\Scripts\python.exe" (
    echo Creation du venv avec %PYTHON%...
    %PYTHON% -m venv .venv
    echo Installation des dependances...
    .venv\Scripts\python.exe -m pip install --upgrade pip --quiet
    .venv\Scripts\python.exe -m pip install PyMuPDF opencv-python Pillow numpy reportlab --quiet
)

:launch
echo.
echo Lancement du Comparateur QCM PDF...
echo.
set PYTHONUTF8=1
.venv\Scripts\python.exe main.py
