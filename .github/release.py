# Monta a Release da versão do release.json (tag vX.Y.Z, criada no commit ALVO) com os arquivos listados nele, conferindo o
# SHA-256 de cada um.
# Rodado pelo GitHub Actions (.github/workflows/release.yml); a lista é escrita pelo publicar.py do código-fonte.
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
    sys.exit(f'tag inválida no release.json: {tag!r}')
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
existe = subprocess.run(['gh', 'release', 'view', tag, '--json', 'assets', '--jq', '.assets[].name', *repo],
                       capture_output=True, text=True)
if existe.returncode == 0:
    # Já existe (rodou de novo): só acrescenta o que falta. Nunca substitui um arquivo publicado, porque isso zera a
    # contagem de downloads dele.
    ja = set(existe.stdout.split())
    faltam = [a for a in arquivos if pathlib.Path(a.split('#')[0]).name not in ja]
    if faltam:
        subprocess.run(['gh', 'release', 'upload', tag, *faltam, *repo], check=True)
    print(f'Release {tag} já existia; acrescentados {len(faltam)} arquivos')
    sys.exit(0)
else:
    subprocess.run(['gh', 'release', 'create', tag, '--title', r['titulo'], '--notes', r['notas'], '--latest',
                    '--target', os.environ['ALVO'], *arquivos, *repo], check=True)
print(f'Release {tag}: {len(arquivos)} arquivos')
