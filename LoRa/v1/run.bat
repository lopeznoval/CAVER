@echo off
set VENV_DIR=venv

echo ==============================
echo   INICIANDO ENTORNO PYTHON
echo ==============================

REM Crear entorno virtual si no existe
if not exist %VENV_DIR% (
    echo Creando entorno virtual...
    python -m venv %VENV_DIR%
)

echo Activando entorno virtual...
call %VENV_DIR%\Scripts\activate

echo ==============================
echo  INSTALANDO DEPENDENCIAS...
echo ==============================
pip install --upgrade pip
pip install -r requirements.txt

echo ==============================
echo  INICIANDO LA APLICACION
echo ==============================
python main.py

echo ==============================
echo    FINALIZADO
echo ==============================
pause

