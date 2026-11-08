@echo off
rem Comandos (chcp, powershell, timeout) so das pastas do Windows, nunca um arquivo de mesmo nome deixado na pasta atual
rem (ex.: um chcp.exe falso nos Downloads).
set "NoDefaultCurrentDirectoryInExePath=1"
chcp 65001 >nul
rem Este arquivo e UTF-8 sem BOM: depois do chcp 65001 o cmd le os acentos das mensagens corretamente.
setlocal
cd /d "%~dp0"
rem Pasta padrao dos apps da RLA.dev: C:\rla-lab\<app> (sem permissao para gravar la: %USERPROFILE%\rla-lab\<app>).
rem Em qualquer outro lugar (zip extraido nos Downloads, aberto de dentro do zip sem extrair...), este arquivo se copia
rem para a pasta padrao e instala de la (nao precisa de nada do zip: o resto e baixado). Rodado numa instalacao que ja
rem existe em outro lugar (tem o programa ou o Python dele): atualiza ali mesmo, e o programa se muda sozinho para a
rem pasta padrao ao abrir. --na-pasta: ja e a copia feita aqui; nunca muda de pasta duas vezes.
set "PADRAO=%SystemDrive%\rla-lab\Vídeo Lab IA"
set "RESERVA=%USERPROFILE%\rla-lab\Vídeo Lab IA"
if /i "%~1"=="--na-pasta" goto instalar
if exist "videolab.pyw" goto instalar
if exist "enxuto.pyw" goto instalar
if exist "python\python.exe" goto instalar
if exist ".venv\" goto instalar
if /i "%~dp0"=="%PADRAO%\" goto instalar
if /i "%~dp0"=="%RESERVA%\" goto instalar
set "DESTINO=%PADRAO%"
if not exist "%DESTINO%\" mkdir "%DESTINO%" 2>nul
copy /y "%~f0" "%DESTINO%\%~nx0" >nul 2>nul
if exist "%DESTINO%\%~nx0" goto ir_para_destino
set "DESTINO=%RESERVA%"
if not exist "%DESTINO%\" mkdir "%DESTINO%" 2>nul
copy /y "%~f0" "%DESTINO%\%~nx0" >nul 2>nul
if exist "%DESTINO%\%~nx0" goto ir_para_destino
goto sem_pasta
:ir_para_destino
echo.
echo  Instalando o Vídeo Lab IA em:
echo  %DESTINO%
call "%DESTINO%\%~nx0" --na-pasta
exit /b
:instalar
title Vídeo Lab IA - Instalação
echo.
echo  Vídeo Lab IA - Conversão, compressão e otimização de vídeos diretamente no seu computador
echo.
echo  A internet é usada só durante a instalação, para baixar os componentes do programa.
echo  Depois de instalado, o Vídeo Lab IA funciona sem internet.
echo.
set "REPO=https://raw.githubusercontent.com/rla-devv/VideoLabIA-versoes/main/"
if defined ENXUTO_REPO_VERSOES set "REPO=%ENXUTO_REPO_VERSOES%"
if defined VIDEOLAB_REPO_VERSOES set "REPO=%VIDEOLAB_REPO_VERSOES%"
rem Testes com outro repositorio: nada da Release (o programa baixa de la so os arquivos desta versao publicada).
if defined ENXUTO_REPO_VERSOES set "REPO_TESTE=1"
if defined VIDEOLAB_REPO_VERSOES set "REPO_TESTE=1"
rem Confere a internet antes de baixar qualquer coisa: sem ela, avisa na hora em vez de parar no meio.
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ProgressPreference='SilentlyContinue'; [Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; try { Invoke-WebRequest -UseBasicParsing -Method Head -TimeoutSec 20 -Uri ($env:REPO + 'atualizacao.json') | Out-Null } catch { exit 1 }" || goto sem_internet
echo  Instalando o Vídeo Lab IA...
echo.
rem Python so do Video Lab IA: o portatil oficial do python.org, em python\ (nao mexe no resto do computador).
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
  echo  Baixando o Python do Vídeo Lab IA ^(cerca de 13 MB, só na primeira vez^)...
  powershell -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='Stop'; $ProgressPreference='SilentlyContinue'; [Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; $z=Join-Path $env:TEMP 'videolab-python.zip'; Invoke-WebRequest -UseBasicParsing -TimeoutSec 60 -Uri $env:PY_URL -OutFile $z; if ((Get-FileHash -Algorithm SHA256 $z).Hash -ne $env:PY_SHA) { Remove-Item $z; throw 'o arquivo baixado nao confere com o esperado (SHA-256)' }; Expand-Archive -Force $z 'python'; Remove-Item $z; $pth=(Get-ChildItem 'python\python*._pth')[0].FullName; (Get-Content $pth) -replace '^#\s*import site','import site' | Set-Content -Encoding ascii $pth" || goto erro
)
rem O pacote so traz este arquivo: o programa vem do repositorio de versoes, conferido (tamanho e SHA-256) pelo
rem atualizacao.json, como nas atualizacoes. Pasta sem o videolab.pyw (ou com um sem o --instalar): baixa um novo.
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='Stop'; $ProgressPreference='SilentlyContinue'; [Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; if ((Test-Path 'videolab.pyw') -and (Select-String -Quiet -SimpleMatch 'def instalar_programa' 'videolab.pyw')) { exit 0 }; Write-Host ' Baixando o Video Lab IA...'; $m=(Invoke-WebRequest -UseBasicParsing -TimeoutSec 60 -Headers @{'Cache-Control'='no-cache'} -Uri ($env:REPO + 'atualizacao.json?t=' + [DateTimeOffset]::Now.ToUnixTimeMilliseconds())).Content | ConvertFrom-Json; $it=@($m.janela.arquivos | Where-Object { $_.caminho -eq 'videolab.pyw' })[0]; if (-not $it -or $it.origem -match '\.\.' -or $it.origem -match '^[/\\]') { throw 'o atualizacao.json nao traz o programa' }; $f='videolab.pyw.novo'; $ok=$false; $rel='https://github.com/rla-devv/VideoLabIA-versoes/releases/download/'; if (-not $env:REPO_TESTE -and $it.url -and $it.url.StartsWith($rel)) { try { Invoke-WebRequest -UseBasicParsing -TimeoutSec 60 -Uri $it.url -OutFile $f; $ok=((Get-Item $f).Length -eq $it.tamanho -and (Get-FileHash -Algorithm SHA256 $f).Hash -eq $it.sha256) } catch { $ok=$false } }; if (-not $ok) { Invoke-WebRequest -UseBasicParsing -TimeoutSec 60 -Uri ($env:REPO + $it.origem) -OutFile $f; if ((Get-Item $f).Length -ne $it.tamanho -or (Get-FileHash -Algorithm SHA256 $f).Hash -ne $it.sha256) { Remove-Item $f; throw 'o programa baixado nao confere com o esperado (SHA-256)' } }; Move-Item -Force $f 'videolab.pyw'" || goto erro
"%PYEXE%" videolab.pyw --instalar || goto erro
echo.
echo  Pronto! O Vídeo Lab IA está abrindo.
echo  Para abrir depois, use o atalho 'Vídeo Lab IA' na Área de Trabalho e no Menu Iniciar,
echo  ou o 'Abrir Vídeo Lab IA' na pasta %~dp0
echo.
start "" "%~dp0%PYW%" "%~dp0videolab.pyw"
timeout /t 6 >nul
exit /b 0
:sem_internet
echo  Sem conexão com a internet.
echo  A instalação precisa de internet para baixar os componentes do programa (só desta vez).
echo  Conecte o computador à internet e rode este arquivo de novo.
echo.
pause
exit /b 1
:sem_pasta
echo.
echo  Não consegui criar a pasta do Vídeo Lab IA em %PADRAO%
echo  nem em %RESERVA%.
echo  Confira se há espaço no disco e rode este arquivo de novo.
echo.
pause
exit /b 1
:erro
echo.
echo  A instalação não terminou. Veja a mensagem acima.
echo  Confira a internet (ela é usada só durante a instalação) e rode este arquivo de novo.
echo.
pause
exit /b 1
