@echo off
cd /d "%~dp0"
title MeCam
where python >nul 2>&1
if errorlevel 1 goto sinpython
if exist ".instalado-v2" goto abrir
echo.
echo Primera vez: instalando lo necesario. Puede tardar varios minutos.
echo No cierres esta ventana.
echo.
python -m pip install -r requirements.txt
if errorlevel 1 goto errorpip
echo listo> .instalado-v2
:abrir
where pythonw >nul 2>&1
if errorlevel 1 (
  python mecam_gui.py
) else (
  start "" pythonw mecam_gui.py
)
exit /b

:sinpython
echo.
echo No se encontro Python en este equipo.
echo Instalalo desde https://www.python.org/downloads
echo y marca la casilla "Add python.exe to PATH". Luego abre este archivo otra vez.
echo.
pause
exit /b

:errorpip
echo.
echo Hubo un error al instalar. Copia el mensaje de arriba y consulta las preguntas frecuentes.
echo.
pause
exit /b
