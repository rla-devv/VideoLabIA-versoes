# Monta a Release da tag (TAG) com os arquivos listados no release.json, conferindo o SHA-256 de cada um.
# Rodado pelo GitHub Actions (.github/workflows/release.yml); a lista é escrita pelo publicar.py do código-fonte.
import hashlib
import json
import os
import pathlib
import subprocess
import sys
import tempfile

tag = os.environ['TAG']
r = json.loads(pathlib.Path('release.json').read_text(encoding='utf-8'))
if r['tag'] != tag:
    sys.exit(f"release.json é da {r['tag']}, não da {tag}")
pasta = pathlib.Path(tempfile.mkdtemp())
arquivos = []
for a in r['arquivos']:
    dados = pathlib.Path(a['origem']).read_bytes()
    if hashlib.sha256(dados).hexdigest() != a['sha256'] or len(dados) != a['tamanho']:
        sys.exit(f"{a['origem']}: o arquivo não confere com o release.json")
    alvo = pasta / a['nome']
    alvo.write_bytes(dados)
    arquivos.append(f"{alvo}#{a['rotulo']}")
repo = ['--repo', os.environ['GITHUB_REPOSITORY']]
if subprocess.run(['gh', 'release', 'view', tag, *repo], capture_output=True).returncode == 0:
    subprocess.run(['gh', 'release', 'upload', tag, '--clobber', *arquivos, *repo], check=True)   # rodou de novo
else:
    subprocess.run(['gh', 'release', 'create', tag, '--title', r['titulo'], '--notes', r['notas'], '--latest',
                    '--verify-tag', *arquivos, *repo], check=True)
print(f'Release {tag}: {len(arquivos)} arquivos')
