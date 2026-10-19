# Cria o atalho do Enxuto na Area de Trabalho e no Menu Iniciar.
# Com -SoAtualizar, so troca o icone (e o destino) dos atalhos que ja existem.
param([switch]$SoAtualizar)
$ErrorActionPreference = 'Stop'
$app = Split-Path -Parent $MyInvocation.MyCommand.Path
$icone = Join-Path $app 'assets\enxuto-v2.ico'
$shell = New-Object -ComObject WScript.Shell
foreach ($pasta in @([Environment]::GetFolderPath('Desktop'), [Environment]::GetFolderPath('Programs'))) {
  $caminho = Join-Path $pasta 'Enxuto.lnk'
  if ($SoAtualizar -and -not (Test-Path $caminho)) { continue }
  $atalho = $shell.CreateShortcut($caminho)
  $atalho.TargetPath = Join-Path $app '.venv\Scripts\pythonw.exe'
  $atalho.Arguments = '"' + (Join-Path $app 'enxuto.pyw') + '"'
  $atalho.WorkingDirectory = $app
  $atalho.IconLocation = $icone + ',0'
  $atalho.Description = 'Enxuto - conversao, compressao e otimizacao de videos'
  $atalho.Save()
}
# Pede ao Windows para redesenhar os icones (sem isto o icone antigo pode continuar aparecendo).
try { Start-Process -FilePath "$env:SystemRoot\System32\ie4uinit.exe" -ArgumentList '-show' -WindowStyle Hidden -Wait } catch { }
Write-Host ' Atalhos prontos.'
