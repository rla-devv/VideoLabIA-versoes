@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
echo.
echo  Instalando o Enxuto IA...
echo.
rem Python so do Enxuto IA: o portatil oficial do python.org, em python\ (nao mexe no resto do computador).
rem Instalacoes de antes da 1.10.2 continuam com o .venv.
set "PY_URL=https://www.python.org/ftp/python/3.14.8/python-3.14.8-embed-amd64.zip"
set "PY_SHA=a93abe456ab01bd96d7a085b3cdb6566b3063f4241360d114142fbdb07f0a310"
set "PYEXE=python\python.exe"
set "PYW=python\pythonw.exe"
if exist ".venv\Scripts\python.exe" (
  set "PYEXE=.venv\Scripts\python.exe"
  set "PYW=.venv\Scripts\pythonw.exe"
)
if not exist "%PYEXE%" (
  echo  Baixando o Python do Enxuto IA ^(cerca de 13 MB, so na primeira vez^)...
  powershell -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='Stop'; $ProgressPreference='SilentlyContinue'; [Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; $z=Join-Path $env:TEMP 'enxuto-python.zip'; Invoke-WebRequest -UseBasicParsing -Uri $env:PY_URL -OutFile $z; if ((Get-FileHash -Algorithm SHA256 $z).Hash -ne $env:PY_SHA) { Remove-Item $z; throw 'o arquivo baixado nao confere com o esperado (SHA-256)' }; Expand-Archive -Force $z 'python'; Remove-Item $z; $pth=(Get-ChildItem 'python\python*._pth')[0].FullName; (Get-Content $pth) -replace '^#\s*import site','import site' | Set-Content -Encoding ascii $pth" || goto erro
)
"%PYEXE%" enxuto.pyw --instalar || goto erro
echo.
echo  Pronto! O Enxuto IA esta abrindo. Das proximas vezes, abra pelo atalho "Enxuto IA"
echo  na Area de Trabalho ou no Menu Iniciar.
echo.
start "" "%~dp0%PYW%" "%~dp0enxuto.pyw"
timeout /t 6 >nul
exit /b 0
:erro
echo.
echo  A instalacao nao terminou. Veja a mensagem acima.
echo  Precisa de internet so durante a instalacao. Depois e so rodar este arquivo de novo.
echo.
pause
exit /b 1
