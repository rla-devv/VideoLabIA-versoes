# Cria a Release da versão do release.json (etiqueta vX.Y.Z, no commit ALVO) com os arquivos listados nele, conferindo o
# tamanho e o SHA-256 de cada um. Rodado pelo GitHub Actions (.github/workflows/release.yml); a lista é escrita pelo
# publicar.py do código-fonte. Os arquivos vão com o nome que têm (o GitHub troca espaços por pontos sozinho).
# Nunca apaga nem reescreve: se a Release da versão já existe, para sem mexer em nada.
import hashlib
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile

r = json.loads(pathlib.Path('release.json').read_text(encoding='utf-8'))
tag = r['tag']
if not re.fullmatch(r'v\d+(\.\d+){1,3}', tag):
    sys.exit(f'etiqueta inválida no release.json: {tag!r}')
repo = ['--repo', os.environ['GITHUB_REPOSITORY']]
if subprocess.run(['gh', 'release', 'view', tag, *repo], capture_output=True).returncode == 0:
    print(f'A Release {tag} já existe: nada a fazer (Releases publicadas nunca são reescritas).')
    sys.exit(0)
pasta = pathlib.Path(tempfile.mkdtemp())
arquivos = []
for a in r['arquivos']:
    dados = pathlib.Path(a['origem']).read_bytes()
    if hashlib.sha256(dados).hexdigest() != a['sha256'] or len(dados) != a['tamanho']:
        sys.exit(f"{a['origem']}: o arquivo não confere com o release.json")
    if '/' in a['nome'] or '\\' in a['nome'] or a['nome'] in ('', '.', '..'):
        sys.exit(f"nome inválido: {a['nome']!r}")
    alvo = pasta / a['nome']
    alvo.write_bytes(dados)
    arquivos.append(f"{alvo}#{a['rotulo']}")
subprocess.run(['gh', 'release', 'create', tag, '--title', r['titulo'], '--notes', r['notas'], '--latest',
                '--target', os.environ['ALVO'], *arquivos, *repo], check=True)
print(f'Release {tag}: {len(arquivos)} arquivos')
