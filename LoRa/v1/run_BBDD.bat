@echo off
color 0B
echo ========================================================
echo      INICIANDO ESTACION BASE (MODO WEB) - CAVER
echo ========================================================
echo.

:: 1. Iniciar Servidor FastAPI (Video y Dashboard)
echo [1/2] Lanzando Servidor API y Web...
:: "start" abre una nueva ventana. 
:: "cmd /k" mantiene la ventana abierta para ver logs o errores.
start "SERVIDOR API (FastAPI)" cmd /k "uvicorn main:app --host 0.0.0.0 --port 8000"

:: Esperar 3 segundos para asegurar que el servidor arranque antes de abrir el navegador
timeout /t 3 /nobreak >nul

:: 2. (OMITIDO) El Puente LoRa no se inicia en este modo

:: 3. Abrir el Dashboard en el navegador
echo [2/2] Abriendo Dashboard en Chrome/Edge...
timeout /t 1 /nobreak >nul
start http://127.0.0.1:8000

echo.
echo ========================================================
echo   SISTEMA WEB LISTO
echo ========================================================
echo.
echo   Se ha abierto 1 ventana negra nueva:
echo     1. El Servidor API (Recibe videos y sirve la web)
echo.
echo   NO LA CIERRES. Si la cierras, la web dejara de funcionar.
echo.
pause