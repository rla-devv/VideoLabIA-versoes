# Enxuto IA (Windows): a página do app numa janela do pywebview (WebView2), aberta pelo atalho.
#
#   pythonw enxuto.pyw              abre na janela (é o que o atalho faz)
#   pythonw enxuto.pyw --navegador  abre no navegador padrão
#   python  enxuto.pyw --instalar   o que o instalar.bat roda: pip, pywebview, conversor extra e atalhos
#
# O Python é o portátil oficial do python.org, só do Enxuto IA, em python/ (o instalar.bat baixa e confere);
# instalações de antes da 1.10.2 usam o .venv, feito com o Python do computador.
#
# Sobe um servidor só em 127.0.0.1 (nada fica acessível pela rede) que entrega a página (index.html)
# e o conversor extra (ffmpeg/), e responde à consulta e à instalação de atualizações (/api/atualizacao).
# Se o pywebview faltar, abre no navegador. As mensagens vão para logs/enxuto.log.
#
# Atualização — mesmo modelo do DegravaIA:
#   verificar()            consulta atualizacao.json no repositório PÚBLICO de versões.
#   instalar_atualizacao() baixa os arquivos do app listados no manifesto, confere tudo e só então troca.
#   restaurar()            volta para a versão anterior (guardada em versoes-anteriores/).
# arquivos-do-app.txt lista o que é código do app (vem no pacote e é refeito a cada atualização): a atualização
# troca o que o manifesto traz e remove só o que estava na lista e saiu do pacote. Nunca são tocados: python/, .venv/,
# logs/, dados-janela/, versoes-anteriores/ e o conversor extra (ffmpeg/).
import ast
import gzip
import hashlib
import html
import json
import logging
import mimetypes
import os
import re
import secrets
import shutil
import ssl
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlsplit

APP = Path(__file__).resolve().parent
PORTA = 47811            # fixa, para o tema e as preferências (guardados por endereço) não se perderem
TITULO = 'Enxuto IA'
REQUISITOS = ['pywebview>=6.2,<7']   # se mudarem numa atualização, o pip roda de novo
DADOS_JANELA = APP / 'dados-janela'   # preferências da janela; a atualização nunca mexe aqui
ICONE = APP / 'enxuto.ico'   # nome novo a cada troca de ícone: o Windows guarda ícones em cache pelo caminho
NO_WINDOW = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
MARCA_ATALHOS = f'{ICONE.name} Enxuto IA.lnk'   # mudou o ícone ou o nome do atalho: refaz os atalhos ao abrir

REPO_VERSOES = os.environ.get('ENXUTO_REPO_VERSOES', 'https://raw.githubusercontent.com/rla-devv/enxuto-versoes/main/')
PAGINA = APP / 'index.html'
ANTERIORES = APP / 'versoes-anteriores'
LISTA = APP / 'arquivos-do-app.txt'
LISTA_CABECALHO = '# Arquivos do Enxuto IA. A atualização troca e remove só o que está nesta lista.\n'
# Arquivos do app nas versões de antes da lista (1.7 a 1.9): saem na atualização se o pacote novo não os traz.
LEGADO = {'Enxuto.bat', 'atualizacao.py', 'criar-atalhos.ps1', 'requirements.txt', 'assets/enxuto.ico', 'assets/enxuto-v2.ico'}
PROTEGIDAS = {'python', '.venv', 'logs', 'dados-janela', 'versoes-anteriores', 'ffmpeg'}

# O Python portátil vem sem pip: instala o pacote oficial do pip (PyPI), conferido pelo SHA-256.
PIP = ('https://files.pythonhosted.org/packages/f3/6e/1736e5b4ae2b778ef2f81c47d797de9f891d4d8acb047a24ca37a60294dd/'
       'pip-26.2.1-py3-none-any.whl', '71138adf1f4ca900cdb7d289c21b7494329f2332b6d85f0e1c42108c0384ed3e', 1_816_632)
# O pip só usa pacotes prontos (.whl): o Python portátil não monta pacote que só existe como código-fonte.
# O proxy_tools (exigido pelo pywebview) é assim no PyPI; a versão pronta fica no repositório de versões.
BIBLIOTECAS = {'proxy_tools-0.1.0-py3-none-any.whl': ('5715de0f918322bba8ae5a4320af457fc5aed17b6b7d214a1438768c9cc67f8f', 2_936)}
VER_RE = re.compile(r'^\d+(\.\d+){1,3}$')

# Conversor extra para formatos antigos (ffmpeg.wasm 0.12.10). Não vem no pacote: a instalação baixa
# (ou, se faltar, o app baixa ao abrir) e só grava depois de conferir tamanho e SHA-256.
FFMPEG = APP / 'ffmpeg'
FFMPEG_ORIGENS = ('https://cdn.jsdelivr.net/npm/@ffmpeg/core@0.12.10/dist/umd/',
                  'https://unpkg.com/@ffmpeg/core@0.12.10/dist/umd/')
FFMPEG_ARQUIVOS = {
    'ffmpeg-core.js': ('b266ab5b952555881dd6310663986994a182acb2b7ff25cf10a25f7a37ac2b21', 112_059),
    'ffmpeg-core.wasm': ('9f57947a5bd530d8f00c5b3f2cb2a3492faa7e5d823315342d6a8656d0a6b7b7', 32_232_419),
}

(APP / 'logs').mkdir(exist_ok=True)
logging.basicConfig(filename=APP / 'logs' / 'enxuto.log', level=logging.INFO, encoding='utf-8',
                    format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger('enxuto')
if sys.stdout is None or sys.stderr is None:    # pythonw: sem janela preta, tudo vai para o log
    sys.stdout = sys.stderr = open(APP / 'logs' / 'enxuto.log', 'a', encoding='utf-8', buffering=1)

if os.name == 'nt':
    # Barra de tarefas: sem isto o Windows agrupa a janela com o pythonw.exe e mostra o ícone do Python.
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('RLAdev.Enxuto')
    except Exception:
        log.exception('não consegui definir o ID do app na barra de tarefas')

TOKEN = secrets.token_urlsafe(24)   # só a página entregue por este servidor pode pedir atualização
mimetypes.add_type('text/javascript', '.js')
mimetypes.add_type('application/wasm', '.wasm')
_cache = {'quando': 0.0, 'manifesto': None}


# ---------- downloads ----------

def _sha(dados):
    return hashlib.sha256(dados).hexdigest()


def _baixar(url, limite, progresso=None):
    req = urllib.request.Request(url, headers={'User-Agent': 'Enxuto', 'Cache-Control': 'no-cache',
                                               'Accept-Encoding': 'gzip'})
    with urllib.request.urlopen(req, timeout=60, context=ssl.create_default_context()) as r:
        fonte = gzip.GzipFile(fileobj=r) if r.headers.get('Content-Encoding') == 'gzip' else r
        partes, total = [], 0
        while total <= limite:
            bloco = fonte.read(1 << 20)
            if not bloco:
                break
            partes.append(bloco)
            total += len(bloco)
            if progresso:
                progresso(total)
    if total > limite:
        raise ValueError('arquivo maior que o esperado')
    return b''.join(partes)


# ---------- atualização ----------

def _ver(v):
    return tuple(int(x) for x in v.split('.'))


def versao_de(texto):
    m = re.search(r'<span id="app-version">([^<]+)</span>', texto)
    return m.group(1) if m else '0.0.0'


def versao_instalada():
    try:
        return versao_de(PAGINA.read_text(encoding='utf-8'))
    except OSError:
        return '0.0.0'


def _caminho_seguro(caminho):
    """Todo caminho tem de ficar dentro da pasta do app: sem .., sem caminho absoluto, sem ':'."""
    p = PurePosixPath(caminho)
    if (not caminho or '\\' in caminho or ':' in caminho or p.is_absolute() or '..' in p.parts
            or p.parts[0] in PROTEGIDAS):
        raise ValueError(f'caminho não permitido no pacote: {caminho!r}')
    alvo = (APP / p).resolve()
    if APP not in alvo.parents:
        raise ValueError(f'caminho fora da pasta do app: {caminho!r}')
    return alvo


def _manifesto(forcar=False):
    # Guarda a resposta por 5 min (o GitHub também guarda cópia por uns 5 min); "Buscar atualização" força.
    if not forcar and _cache['manifesto'] and time.time() - _cache['quando'] < 300:
        return _cache['manifesto']
    # ?t= muda o endereço (o GitHub guarda cópia de cada um por uns 5 min); ao forçar, um endereço único.
    chave = int(time.time() * 1000) if forcar else int(time.time() // 60)
    m = json.loads(_baixar(REPO_VERSOES + f'atualizacao.json?t={chave}', 256_000))
    ok = (isinstance(m, dict) and VER_RE.match(str(m.get('versao', '')))
          and re.fullmatch(r'Enxuto-\d+(\.\d+){1,3}\.html', str(m.get('arquivo', '')))
          and re.fullmatch(r'[0-9a-f]{64}', str(m.get('sha256', '')))
          and isinstance(m.get('tamanho'), int) and 100_000 < m['tamanho'] < 64_000_000)
    if not ok:
        raise ValueError('atualizacao.json inválido')
    nov = m.get('novidades') or []
    m['novidades'] = [n for n in (nov if isinstance(nov, list) else [nov]) if isinstance(n, str) and n.strip()][:8]
    _cache.update(quando=time.time(), manifesto=m)
    return m


def _lista_de_arquivos(m):
    """Arquivos do app nesta versão: os do manifesto 'janela' ou, em manifesto antigo, só a página."""
    janela = m.get('janela') if isinstance(m.get('janela'), dict) else None
    itens = janela.get('arquivos') if janela else None
    if not itens:
        return [{'caminho': 'index.html', 'origem': 'versoes/' + m['arquivo'], 'sha256': m['sha256'], 'tamanho': m['tamanho']}]
    lista = []
    for it in itens:
        if not (isinstance(it, dict) and isinstance(it.get('caminho'), str) and isinstance(it.get('origem'), str)
                and re.fullmatch(r'[0-9a-f]{64}', str(it.get('sha256', ''))) and isinstance(it.get('tamanho'), int)
                and 0 <= it['tamanho'] < 64_000_000 and not it['origem'].startswith(('/', '.')) and '..' not in it['origem']):
            raise ValueError('lista de arquivos do manifesto inválida')
        _caminho_seguro(it['caminho'])
        lista.append(it)
    if not any(it['caminho'] == 'index.html' for it in lista):
        raise ValueError('o pacote não traz a página do app')
    return lista


def _lista_atual():
    try:
        linhas = LISTA.read_text(encoding='utf-8').splitlines()
    except OSError:
        linhas = []
    return {l.strip() for l in linhas if l.strip() and not l.lstrip().startswith('#')}


def _escrever_lista(caminhos):
    novo = LISTA.with_name(LISTA.name + '.novo')
    novo.write_text(LISTA_CABECALHO + ''.join(c + '\n' for c in sorted(caminhos)), encoding='utf-8')
    os.replace(novo, LISTA)


def _saem_do_pacote(novos):
    """Arquivos do app (da lista ou de versões anteriores a ela) que o pacote novo não traz mais."""
    saem = []
    for caminho in sorted((_lista_atual() | LEGADO) - set(novos)):
        try:
            alvo = _caminho_seguro(caminho)
        except ValueError:
            log.warning('arquivos-do-app.txt: caminho ignorado: %r', caminho)
            continue
        if alvo.is_file():
            saem.append(caminho)
    return saem


def _limpar_pastas_vazias(caminhos):
    for caminho in caminhos:
        pasta = (APP / caminho).parent
        while pasta != APP and pasta.is_dir() and not any(pasta.iterdir()):
            pasta.rmdir()
            pasta = pasta.parent
    cache = APP / '__pycache__'   # .pyc de módulos que saíram
    for pyc in cache.glob('*.pyc'):
        if not (APP / (pyc.name.split('.')[0] + '.py')).exists():
            pyc.unlink(missing_ok=True)
    if cache.is_dir() and not any(cache.iterdir()):
        cache.rmdir()


def verificar(forcar=False):
    atual = versao_instalada()
    m = _manifesto(forcar)
    nova = {'versao': m['versao'], 'novidades': m['novidades']} if _ver(m['versao']) > _ver(atual) else None
    return {'atual': atual, 'nova': nova}


def _requisitos_de(programa):
    """A lista REQUISITOS escrita no enxuto.pyw baixado (só lida, nunca executada)."""
    m = re.search(r'^REQUISITOS = (\[[^\]\n]*\])', programa, re.M)
    req = ast.literal_eval(m.group(1)) if m else REQUISITOS
    if not (isinstance(req, list) and all(isinstance(r, str) and re.fullmatch(r'[A-Za-z0-9_.\-\[\]<>=!~, ]+', r) for r in req)):
        raise ValueError('requisitos inválidos no programa novo')
    return req


def _python_console():
    exe = Path(sys.executable)
    alt = exe.with_name('python.exe')
    return str(alt) if exe.name.lower() == 'pythonw.exe' and alt.exists() else str(exe)


def garantir_pip():
    if subprocess.run([sys.executable, '-m', 'pip', '--version'], capture_output=True).returncode == 0:
        return
    url, sha, tamanho = PIP
    dados = _baixar(url, tamanho)
    if len(dados) != tamanho or _sha(dados) != sha:
        raise ValueError('pip: o arquivo baixado não confere com o esperado (SHA-256)')
    with tempfile.TemporaryDirectory(prefix='enxuto-') as pasta:
        whl = Path(pasta, url.rsplit('/', 1)[1])
        whl.write_bytes(dados)
        # o próprio pacote do pip roda o pip que o instala, como "python -m pip" (no Windows, o pip só
        # aceita trocar a si mesmo assim); o Python portátil ignora PYTHONPATH, daí o sys.path.insert
        roda = 'import runpy, sys; sys.path.insert(0, sys.argv.pop(1)); runpy.run_module("pip", run_name="__main__", alter_sys=True)'
        subprocess.run([sys.executable, '-c', roda, str(whl), 'install', '--no-index', '--quiet',
                        '--no-warn-script-location', str(whl)], check=True)


def instalar_requisitos(requisitos, console=False):
    with tempfile.TemporaryDirectory(prefix='enxuto-') as pasta:
        for nome, (sha, tamanho) in BIBLIOTECAS.items():
            dados = _baixar(REPO_VERSOES + 'bibliotecas/' + nome, tamanho)
            if len(dados) != tamanho or _sha(dados) != sha:
                raise ValueError(f'{nome}: o arquivo baixado não confere com o esperado (SHA-256)')
            Path(pasta, nome).write_bytes(dados)
        subprocess.run([_python_console(), '-m', 'pip', 'install', '--only-binary=:all:', '--find-links', pasta,
                        '--quiet', '--disable-pip-version-check', '--no-warn-script-location', *requisitos],
                       check=True, cwd=APP, creationflags=0 if console else NO_WINDOW)


def instalar_atualizacao():
    """Baixa e confere todos os arquivos; só então troca. Se qualquer passo falhar, tudo volta como estava."""
    atual = versao_instalada()
    m = _manifesto(forcar=True)
    if _ver(m['versao']) <= _ver(atual):
        raise ValueError(f'a versão publicada ({m["versao"]}) não é mais nova que a instalada ({atual})')
    lista = _lista_de_arquivos(m)

    # 1. Baixa e confere tudo antes de tocar em qualquer arquivo.
    novos = {}
    for it in lista:
        dados = _baixar(REPO_VERSOES + it['origem'], it['tamanho'])
        if len(dados) != it['tamanho'] or _sha(dados) != it['sha256']:
            raise ValueError(f'{it["caminho"]}: o conteúdo baixado não confere com o anunciado (SHA-256)')
        novos[it['caminho']] = dados
    pagina = novos['index.html'].decode('utf-8')
    if not pagina.lower().startswith('<!doctype html>') or versao_de(pagina) != m['versao'] \
            or f"const APP_VERSION = '{m['versao']}'" not in pagina:
        raise ValueError('a versão escrita dentro do pacote não é a anunciada')
    requisitos = _requisitos_de(novos['enxuto.pyw'].decode('utf-8')) if 'enxuto.pyw' in novos else REQUISITOS

    # 2. Troca só o que mudou e remove o que saiu do pacote, guardando a versão atual de cada arquivo para poder voltar.
    copia = ANTERIORES / atual
    trocados, criados, removidos = [], [], []
    try:
        for caminho, dados in novos.items():
            alvo = _caminho_seguro(caminho)
            if alvo.is_file() and alvo.read_bytes() == dados:
                continue   # igual ao atual: não reescreve (no Windows, reescrever um .bat em uso dá problema)
            if alvo.is_file():
                guarda = copia / caminho
                guarda.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(alvo, guarda)
                trocados.append(caminho)
            else:
                criados.append(caminho)
            alvo.parent.mkdir(parents=True, exist_ok=True)
            novo = alvo.with_name(alvo.name + '.novo')   # escreve ao lado e renomeia: nunca fica pela metade
            novo.write_bytes(dados)
            os.replace(novo, alvo)
        for caminho in _saem_do_pacote(novos):
            guarda = copia / caminho
            guarda.parent.mkdir(parents=True, exist_ok=True)
            os.replace(_caminho_seguro(caminho), guarda)
            removidos.append(caminho)
        if requisitos != REQUISITOS:
            instalar_requisitos(requisitos)
    except Exception:
        for caminho in trocados:
            if (copia / caminho).exists():
                os.replace(copia / caminho, _caminho_seguro(caminho))
        for caminho in criados:
            _caminho_seguro(caminho).unlink(missing_ok=True)
        for caminho in removidos:
            alvo = _caminho_seguro(caminho)
            alvo.parent.mkdir(parents=True, exist_ok=True)
            os.replace(copia / caminho, alvo)
        if copia.is_dir() and not (copia / 'versao.txt').exists():
            shutil.rmtree(copia, ignore_errors=True)   # cópia de uma tentativa desfeita
        raise
    (copia / 'versao.txt').parent.mkdir(parents=True, exist_ok=True)
    (copia / 'versao.txt').write_text(json.dumps({'versao': atual, 'trocados': trocados, 'criados': criados,
                                                  'removidos': removidos}), encoding='utf-8')
    _escrever_lista(novos)
    _limpar_pastas_vazias(removidos)
    _cache.update(quando=0.0, manifesto=None)
    mudou = set(trocados + criados)
    return {
        'versao': m['versao'],
        # .py/.pyw novos só valem depois de abrir o programa de novo
        'reiniciar': any(c.endswith(('.py', '.pyw')) for c in mudou) or requisitos != REQUISITOS,
        'atalhos': any(c.endswith('.ico') for c in mudou | set(removidos)),
    }


def restaurar():
    """Volta para a versão anterior mais recente guardada em versoes-anteriores/."""
    guardadas = sorted((d for d in ANTERIORES.glob('*') if d.is_dir() and (d / 'versao.txt').is_file()),
                       key=lambda d: _ver(d.name) if VER_RE.match(d.name) else (0,))
    if not guardadas:
        # instalações antigas guardavam só a página
        paginas = sorted(ANTERIORES.glob('Enxuto-*.html'), key=lambda p: _ver(p.stem.split('-', 1)[1]))
        if not paginas:
            raise ValueError('não há versão anterior guardada')
        novo = PAGINA.with_name('index.html.novo')
        shutil.copy2(paginas[-1], novo)
        os.replace(novo, PAGINA)
        paginas[-1].unlink()
        return versao_instalada()
    pasta = guardadas[-1]
    info = json.loads((pasta / 'versao.txt').read_text(encoding='utf-8'))
    for caminho in info.get('trocados', []):
        alvo = _caminho_seguro(caminho)
        novo = alvo.with_name(alvo.name + '.novo')
        shutil.copy2(pasta / caminho, novo)
        os.replace(novo, alvo)
    for caminho in info.get('criados', []):
        _caminho_seguro(caminho).unlink(missing_ok=True)
    for caminho in info.get('removidos', []):
        alvo = _caminho_seguro(caminho)
        alvo.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(pasta / caminho, alvo)
    _escrever_lista((_lista_atual() - set(info.get('criados', []))) | set(info.get('removidos', [])))
    shutil.rmtree(pasta)
    return versao_instalada()


# ---------- conversor extra (ffmpeg) ----------

def preparar_ffmpeg(avisar=None):
    """Deixa o conversor extra pronto em ffmpeg/: confere o que já existe, junta as 3 partes que as instalações
    antigas guardavam e baixa o que faltar. Devolve False se não conseguiu (a página usa então a CDN)."""
    FFMPEG.mkdir(exist_ok=True)
    for nome, (sha, tamanho) in FFMPEG_ARQUIVOS.items():
        alvo = FFMPEG / nome
        if alvo.is_file() and alvo.stat().st_size == tamanho and _sha(alvo.read_bytes()) == sha:
            continue
        dados = b''.join(p.read_bytes() for p in sorted(FFMPEG.glob(nome + '.[0-9]')))
        if len(dados) != tamanho or _sha(dados) != sha:
            dados = None
        for origem in FFMPEG_ORIGENS:
            if dados:
                break
            try:
                baixado = _baixar(origem + nome, tamanho, avisar and (lambda n: avisar(nome, n / tamanho)))
            except Exception as e:
                log.warning('conversor extra: %s%s: %s', origem, nome, e)
                continue
            if len(baixado) == tamanho and _sha(baixado) == sha:
                dados = baixado
            else:
                log.warning('conversor extra: %s%s não confere (SHA-256)', origem, nome)
        if not dados:
            return False
        novo = alvo.with_name(nome + '.novo')
        novo.write_bytes(dados)
        os.replace(novo, alvo)
        log.info('conversor extra: %s pronto', nome)
    for parte in FFMPEG.glob('ffmpeg-core.wasm.[0-9]'):   # já está inteiro no ffmpeg-core.wasm
        try:
            parte.unlink()
        except OSError:
            pass
    return True


# ---------- atalhos (Área de Trabalho e Menu Iniciar) ----------

# Só ASCII: o PowerShell do Windows lê o script com a página de código do sistema. Os caminhos chegam
# pelas variáveis de ambiente, então pastas com acento funcionam.
PS_ATALHOS = r'''
$ErrorActionPreference = 'Stop'
$app = $env:ENXUTO_PASTA
$shell = New-Object -ComObject WScript.Shell
foreach ($pasta in @([Environment]::GetFolderPath('Desktop'), [Environment]::GetFolderPath('Programs'))) {
  $caminho = Join-Path $pasta 'Enxuto IA.lnk'
  $antigo = Join-Path $pasta 'Enxuto.lnk'   # nome de antes da 1.11.0
  if ($env:ENXUTO_SO_ATUALIZAR -eq '1' -and -not (Test-Path $caminho) -and -not (Test-Path $antigo)) { continue }
  $atalho = $shell.CreateShortcut($caminho)
  $atalho.TargetPath = $env:ENXUTO_PYTHONW
  $atalho.Arguments = '"' + (Join-Path $app 'enxuto.pyw') + '"'
  $atalho.WorkingDirectory = $app
  $atalho.IconLocation = $env:ENXUTO_ICONE + ',0'
  $atalho.Description = 'Enxuto IA - conversao, compressao e otimizacao de videos'
  $atalho.Save()
  if (Test-Path $antigo) { Remove-Item $antigo }
}
# Pede ao Windows para redesenhar os icones (sem isto o icone antigo pode continuar aparecendo).
try { Start-Process -FilePath (Join-Path $env:SystemRoot 'System32\ie4uinit.exe') -ArgumentList '-show' -WindowStyle Hidden -Wait } catch { }
'''


def criar_atalhos(so_atualizar=False):
    """Cria o atalho Enxuto IA na Área de Trabalho e no Menu Iniciar (com so_atualizar, só refaz os que existem)."""
    fd, script = tempfile.mkstemp(prefix='enxuto-atalhos-', suffix='.ps1')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8-sig') as f:
            f.write(PS_ATALHOS)
        env = dict(os.environ, ENXUTO_PASTA=str(APP), ENXUTO_ICONE=str(ICONE),
                   ENXUTO_PYTHONW=str(Path(sys.executable).with_name('pythonw.exe')),
                   ENXUTO_SO_ATUALIZAR='1' if so_atualizar else '0')
        r = subprocess.run(['powershell', '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-File', script],
                           env=env, timeout=60, creationflags=NO_WINDOW, capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError((r.stderr or r.stdout).strip() or f'PowerShell terminou com código {r.returncode}')
    finally:
        os.unlink(script)
    DADOS_JANELA.mkdir(exist_ok=True)
    (DADOS_JANELA / 'icone-dos-atalhos.txt').write_text(MARCA_ATALHOS, encoding='utf-8')


def atualizar_atalhos(forcar=False):
    """Põe o ícone atual nos atalhos que já existem. Só no Windows."""
    if os.name != 'nt' or not ICONE.is_file():
        return
    marca = DADOS_JANELA / 'icone-dos-atalhos.txt'
    try:
        if not forcar and marca.is_file() and marca.read_text(encoding='utf-8').strip() == MARCA_ATALHOS:
            return
        criar_atalhos(so_atualizar=True)
        log.info('atalhos atualizados com %s', ICONE.name)
    except Exception:
        log.exception('não consegui atualizar o ícone dos atalhos')


# ---------- instalação (instalar.bat) ----------

def instalar_programa():
    """Roda com o python.exe do Enxuto IA, numa janela de console: as mensagens são para a pessoa."""
    print(' Instalando o pywebview (abre o Enxuto IA como um programa)...', flush=True)
    garantir_pip()
    instalar_requisitos(REQUISITOS, console=True)

    print(' Baixando o conversor para formatos antigos (cerca de 10 MB)...', flush=True)

    def avisar(nome, fracao):
        if nome.endswith('.wasm'):
            print(f'\r   {min(fracao, 1):4.0%}', end='', flush=True)
    try:
        pronto = preparar_ffmpeg(avisar)
    except Exception:
        log.exception('conversor extra')
        pronto = False
    print('\r   pronto' if pronto else '\r   Não consegui baixar agora: o Enxuto IA tenta de novo sozinho quando abrir.', flush=True)

    if os.name == 'nt':
        print(' Criando o atalho na Área de Trabalho e no Menu Iniciar...', flush=True)
        criar_atalhos()


# ---------- servidor local ----------

class Handler(BaseHTTPRequestHandler):
    server_version = 'Enxuto'

    def log_message(self, fmt, *args):
        log.info('%s %s', self.address_string(), fmt % args)

    def _host_ok(self):
        # Só aceita pedidos endereçados a este computador (evita outro site se passar pelo app).
        return self.headers.get('Host', '') in (f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}')

    def _send(self, code, body, ctype, extra=None):
        self.send_response(code)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != 'HEAD':
            self.wfile.write(body)

    def _json(self, code, data):
        self._send(code, json.dumps(data, ensure_ascii=False).encode('utf-8'), 'application/json; charset=utf-8')

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        if not self._host_ok():
            return self._send(403, b'', 'text/plain')
        path = unquote(urlsplit(self.path).path)
        if path == '/api/atualizacao':
            if self.headers.get('X-Enxuto-Token') != TOKEN:
                return self._json(403, {'erro': 'sem permissão'})
            try:
                return self._json(200, verificar(forcar='forcar=1' in (urlsplit(self.path).query or '')))
            except Exception as e:  # sem internet etc.: a página decide o que mostrar
                log.warning('consulta de atualização falhou: %s', e)
                return self._json(200, {'atual': versao_instalada(), 'nova': None, 'erro': str(e)})
        if path in ('/', '/index.html'):
            pagina = PAGINA.read_text(encoding='utf-8')
            marca = f'<script>window.__ENXUTO_APP = {{ token: {json.dumps(TOKEN)}, api: 2 }};</script>\n'
            pagina = pagina.replace('<head>\n', '<head>\n' + marca, 1)
            return self._send(200, pagina.encode('utf-8'), 'text/html; charset=utf-8')
        # Só entrega o conversor extra; nada mais da pasta do app.
        if path.startswith('/ffmpeg/'):
            alvo = (APP / path.lstrip('/')).resolve()
            if alvo.is_file() and alvo.parent == FFMPEG.resolve() and not alvo.name.endswith('.novo'):
                ctype = mimetypes.guess_type(alvo.name)[0] or 'application/octet-stream'
                return self._send(200, alvo.read_bytes(), ctype)
        return self._send(404, 'Não encontrado'.encode('utf-8'), 'text/plain; charset=utf-8')

    def do_POST(self):
        if not self._host_ok() or self.headers.get('X-Enxuto-Token') != TOKEN:
            return self._json(403, {'erro': 'sem permissão'})
        path = urlsplit(self.path).path
        try:
            if path == '/api/atualizacao':
                r = instalar_atualizacao()
                if r['atalhos']:
                    atualizar_atalhos(forcar=True)
                self._json(200, {'ok': True, **r})
                if r['reiniciar']:   # código novo do programa: abre de novo, já na versão nova
                    threading.Timer(0.8, reiniciar).start()
                return
            if path == '/api/atualizacao/restaurar':
                return self._json(200, {'ok': True, 'versao': restaurar()})
        except Exception as e:
            log.exception('atualização falhou')
            return self._json(200, {'ok': False, 'erro': str(e)})
        return self._json(404, {'erro': 'não encontrado'})


def subir_servidor():
    srv = None
    # Depois de atualizar, a versão anterior ainda pode estar soltando a porta: espera um pouco.
    for _ in range(40 if '--aguardar' in sys.argv else 1):
        try:
            srv = ThreadingHTTPServer(('127.0.0.1', PORTA), Handler)
            break
        except OSError:
            threading.Event().wait(0.25)
    if srv is None:
        log.warning('porta %s ocupada; usando outra (o tema escolhido pode voltar ao padrão)', PORTA)
        srv = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f'http://127.0.0.1:{srv.server_port}/'


def em_segundo_plano():
    """Ao abrir: ícone dos atalhos em dia e conversor extra pronto (baixa se a instalação não conseguiu)."""
    atualizar_atalhos()
    try:
        if not preparar_ffmpeg():
            log.warning('conversor extra indisponível por enquanto; a página usa a CDN')
    except Exception:
        log.exception('conversor extra')


def reiniciar():
    """Abre o programa de novo (já com o código novo) e fecha este."""
    args = [sys.executable, str(APP / 'enxuto.pyw'), '--aguardar', '--reiniciado'] + [a for a in sys.argv[1:] if a == '--navegador']
    log.info('reiniciando para a versão nova')
    subprocess.Popen(args, cwd=APP, close_fds=True,
                     creationflags=getattr(subprocess, 'DETACHED_PROCESS', 0) | NO_WINDOW)
    try:
        import webview
        for w in list(webview.windows):
            w.destroy()
    except Exception:
        pass
    os._exit(0)


def pagina_de_erro(detalhe):
    return f'''<!doctype html><html lang="pt-BR"><meta charset="utf-8"><title>Enxuto IA</title>
<body style="font:16px system-ui,sans-serif;max-width:640px;margin:48px auto;padding:0 20px;color:#13201f">
<h1 style="font-size:1.4rem">O Enxuto IA não conseguiu abrir</h1>
<p>Tente fechar e abrir de novo pelo atalho. Se continuar, rode o <b>instalar.bat</b> outra vez.</p>
<p>Os detalhes ficaram em <b>{html.escape(str(APP / 'logs' / 'enxuto.log'))}</b>.</p>
<pre style="white-space:pre-wrap;background:#eef3f2;padding:12px;border-radius:8px;font-size:13px">{html.escape(detalhe)}</pre>
</body></html>'''


def abrir_no_navegador(url):
    log.info('abrindo no navegador: %s', url)
    webbrowser.open(url)
    threading.Event().wait()   # mantém o servidor no ar enquanto a página estiver aberta


def main():
    if '--instalar' in sys.argv:
        try:
            instalar_programa()
        except Exception as e:
            log.exception('instalação')
            print(f'\n Erro: {e}', flush=True)
            sys.exit(1)
        return

    navegador = '--navegador' in sys.argv
    try:
        if not PAGINA.is_file():
            raise FileNotFoundError(f'index.html não encontrado em {APP}')
        srv, url = subir_servidor()
        log.info('Enxuto IA %s em %s', versao_instalada(), url)
    except Exception:
        detalhe = traceback.format_exc()
        log.error(detalhe)
        try:
            import webview
            webview.create_window(TITULO, html=pagina_de_erro(detalhe), width=760, height=520)
            webview.start()
        except Exception:
            erro = APP / 'logs' / 'erro.html'
            erro.write_text(pagina_de_erro(detalhe), encoding='utf-8')
            webbrowser.open(erro.as_uri())
        return

    threading.Thread(target=em_segundo_plano, daemon=True).start()
    if navegador:
        if '--reiniciado' in sys.argv:   # a aba aberta recarrega sozinha
            log.info('reiniciado no modo navegador')
            return threading.Event().wait()
        return abrir_no_navegador(url)
    try:
        import webview
    except ImportError:
        log.warning('pywebview não instalado; abrindo no navegador')
        return abrir_no_navegador(url)

    try:
        webview.settings['ALLOW_DOWNLOADS'] = True      # "Baixar" abre a janela Salvar como
        webview.create_window(TITULO, url, width=1400, height=900, min_size=(900, 620),
                              background_color='#f2f6f5', text_select=True)
        DADOS_JANELA.mkdir(exist_ok=True)
        webview.start(private_mode=False, storage_path=str(DADOS_JANELA),
                      icon=str(ICONE) if ICONE.is_file() else None)
    except Exception:
        log.exception('a janela não abriu; abrindo no navegador')
        return abrir_no_navegador(url)
    srv.shutdown()


if __name__ == '__main__':
    main()
