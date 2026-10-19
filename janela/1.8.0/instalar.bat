@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
echo.
echo  Instalando o Enxuto (janela propria)...
echo.
set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY (
  where python >nul 2>nul && set "PY=python"
)
if not defined PY (
  echo  Nao encontrei o Python neste computador.
  echo  Instale pelo site python.org ^(marque "Add python.exe to PATH"^) e rode este arquivo de novo.
  goto erro
)
if not exist ".venv\Scripts\pythonw.exe" (
  %PY% -m venv .venv || goto erro
)
".venv\Scripts\python.exe" -m pip install --upgrade pip >nul 2>nul
".venv\Scripts\python.exe" -m pip install -r requirements.txt || goto erro
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0criar-atalhos.ps1" || goto erro
echo.
echo  Pronto! Abra o Enxuto pelo atalho na Area de Trabalho ou no Menu Iniciar.
echo.
pause
exit /b 0
:erro
echo.
echo  A instalacao nao terminou. Veja a mensagem acima.
echo.
pause
exit /b 1
