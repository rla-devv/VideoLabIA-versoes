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
rem O pacote so traz este arquivo: o programa vem do repositorio de versoes, conferido (tamanho e SHA-256) pelo
rem atualizacao.json, como nas atualizacoes. Pasta com um enxuto.pyw antigo (sem o --instalar): troca por um novo.
set "REPO=https://raw.githubusercontent.com/rla-devv/enxuto-versoes/main/"
if defined ENXUTO_REPO_VERSOES set "REPO=%ENXUTO_REPO_VERSOES%"
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='Stop'; $ProgressPreference='SilentlyContinue'; [Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; if ((Test-Path 'enxuto.pyw') -and (Select-String -Quiet -SimpleMatch 'def instalar_programa' 'enxuto.pyw')) { exit 0 }; Write-Host ' Baixando o Enxuto IA...'; $m=(Invoke-WebRequest -UseBasicParsing -Uri ($env:REPO + 'atualizacao.json?t=' + [DateTimeOffset]::Now.ToUnixTimeMilliseconds())).Content | ConvertFrom-Json; $it=@($m.janela.arquivos | Where-Object { $_.caminho -eq 'enxuto.pyw' })[0]; if (-not $it -or $it.origem -match '\.\.' -or $it.origem -match '^[/\\]') { throw 'o atualizacao.json nao traz o programa' }; $f='enxuto.pyw.novo'; Invoke-WebRequest -UseBasicParsing -Uri ($env:REPO + $it.origem) -OutFile $f; if ((Get-Item $f).Length -ne $it.tamanho -or (Get-FileHash -Algorithm SHA256 $f).Hash -ne $it.sha256) { Remove-Item $f; throw 'o programa baixado nao confere com o esperado (SHA-256)' }; Move-Item -Force $f 'enxuto.pyw'" || goto erro
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
