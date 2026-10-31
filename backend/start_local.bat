@echo off
setlocal
if /I "%~1"=="docker" (
  cd /d "%~dp0.."
  docker compose -f docker-compose.yml up -d db backend
  exit /b
)

cd /d "%~dp0"

set "DJANGO_DEBUG=true"
set "SERVIPROX_DATABASE=sqlite"
set "SERVIPROX_MEDIA_STORAGE=filesystem"

echo ======================================================
echo    SERVIPROX - INICIANDO BACKEND Y BASE DE DATOS
echo ======================================================

if not exist ".venv\Scripts\python.exe" (
  echo [1/4] Creando entorno virtual Python...
  py -3.13 -m venv .venv 2>nul || py -3 -m venv .venv 2>nul || python -m venv .venv
  if errorlevel 1 (
    echo ERROR: No se pudo crear el entorno virtual. Asegurate de tener Python instalado.
    pause
    exit /b 1
  )
)

call ".venv\Scripts\activate.bat"

:: Solo instalar dependencias si Django no esta presente o si se solicita explicitamente
python -c "import django" >nul 2>&1
if errorlevel 1 (
  echo [2/4] Instalando dependencias de Serviprox ^(primera ejecucion^)...
  python -m pip install -r requirements.txt
  if errorlevel 1 (
    echo ERROR: Fallo la instalacion de dependencias.
    pause
    exit /b 1
  )
) else (
  echo [2/4] Dependencias de Python verificadas OK.
)

echo [3/4] Verificando base de datos SQLite y migraciones...
python manage.py migrate --check >nul 2>&1
if errorlevel 1 (
  echo Aplicando migraciones pendientes...
  python manage.py migrate --no-input
  if errorlevel 1 (
    echo ERROR: Fallo la migracion de base de datos.
    pause
    exit /b 1
  )
  del ".seed_done" >nul 2>&1
)

findstr /B "EMAIL_HOST=" "%~dp0..\.env" >nul 2>&1
if errorlevel 1 (
  echo AVISO: Los correos de recuperacion saldran en consola ^(no hay SMTP configurado^).
)

:: Los datos demo solo se cargan una vez (el seed es lento por el hash de contrasenas).
:: Para recargarlos: borrar backend\.seed_done o ejecutar python seed_demo.py
if exist ".seed_done" (
  echo [4/4] Datos demo ya cargados.
) else (
  echo [4/4] Cargando datos demo de la base de datos ^(solo la primera vez^)...
  python seed_demo.py >nul 2>&1
  if not errorlevel 1 echo ok>".seed_done"
)

echo.
echo ======================================================
echo Base de datos conectada: SQLite (Modo WAL de alta velocidad)
echo API Backend escuchando en: http://127.0.0.1:8000/
echo Salud de base de datos en: http://127.0.0.1:8000/api/v1/health/
echo ======================================================
echo.

python manage.py runserver 0.0.0.0:8000

endlocal
