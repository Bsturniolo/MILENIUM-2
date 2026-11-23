@echo off
rem Arranca la tienda en esta compu (Windows). Doble clic en este archivo.
rem La primera vez instala lo necesario y crea la clave del panel. Los datos quedan en la carpeta "datos".
cd /d "%~dp0"
if not exist .venv (
  py -3.12 -m venv .venv 2>nul || py -m venv .venv 2>nul || python -m venv .venv
)
call .venv\Scripts\activate.bat
python -m pip install -q -r servidor\requirements.txt
if not exist datos mkdir datos
if not exist datos\clave.txt python -c "import secrets; print(secrets.token_hex(12))" > datos\clave.txt
if not exist datos\config.env copy config.ejemplo.env datos\config.env >nul
for /f "usebackq eol=# tokens=1,* delims==" %%a in ("datos\config.env") do set "%%a=%%b"
set /p TIENDA_ADMIN_TOKEN=<datos\clave.txt
set "TIENDA_DB=%cd%\datos\tienda.db"
echo.
echo   Tienda: http://localhost:8000
echo   Panel:  http://localhost:8000/panel
echo   Clave del panel: %TIENDA_ADMIN_TOKEN%
echo   (para cerrar: cerrar esta ventana)
echo.
start "" http://localhost:8000/panel
cd servidor
python -m uvicorn app:app --host 127.0.0.1 --port 8000
pause
