# Atualização do Enxuto em janela — mesmo modelo do DegravaIA.
#
# verificar()  consulta atualizacao.json no repositório PÚBLICO de versões.
# instalar()   baixa os arquivos do app listados no manifesto, confere tudo e só então troca.
# restaurar()  volta para a versão anterior (guardada em versoes-anteriores/).
#
# Só os arquivos do app (os listados no manifesto) são trocados. Nunca são tocados:
# .venv/, ffmpeg/ (a não ser que o manifesto o liste), logs/, dados-janela/ e versoes-anteriores/.
import hashlib
import json
import os
import re
import shutil
import ssl
import subprocess
import sys
import time
import urllib.request
from pathlib import Path, PurePosixPath

APP = Path(__file__).resolve().parent
REPO_VERSOES = os.environ.get('ENXUTO_REPO_VERSOES', 'https://raw.githubusercontent.com/rla-devv/enxuto-versoes/main/')
PAGINA = APP / 'index.html'
ANTERIORES = APP / 'versoes-anteriores'
LISTA = APP / 'arquivos-do-app.txt'
PROTEGIDAS = {'.venv', 'logs', 'dados-janela', 'versoes-anteriores'}
VER_RE = re.compile(r'^\d+(\.\d+){1,3}$')
_cache = {'quando': 0.0, 'manifesto': None}


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


def _baixar(url, limite):
    req = urllib.request.Request(url, headers={'User-Agent': 'Enxuto', 'Cache-Control': 'no-cache'})
    with urllib.request.urlopen(req, timeout=60, context=ssl.create_default_context()) as r:
        dados = r.read(limite + 1)
    if len(dados) > limite:
        raise ValueError('arquivo maior que o esperado')
    return dados


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


def verificar(forcar=False):
    atual = versao_instalada()
    m = _manifesto(forcar)
    nova = {'versao': m['versao'], 'novidades': m['novidades']} if _ver(m['versao']) > _ver(atual) else None
    return {'atual': atual, 'nova': nova}


def _python_console():
    exe = Path(sys.executable)
    alt = exe.with_name('python.exe')
    return str(alt) if exe.name.lower() == 'pythonw.exe' and alt.exists() else str(exe)


def instalar():
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
        if len(dados) != it['tamanho'] or hashlib.sha256(dados).hexdigest() != it['sha256']:
            raise ValueError(f'{it["caminho"]}: o conteúdo baixado não confere com o anunciado (SHA-256)')
        novos[it['caminho']] = dados
    pagina = novos['index.html'].decode('utf-8')
    if not pagina.lower().startswith('<!doctype html>') or versao_de(pagina) != m['versao'] \
            or f"const APP_VERSION = '{m['versao']}'" not in pagina:
        raise ValueError('a versão escrita dentro do pacote não é a anunciada')

    # 2. Troca só o que mudou, guardando a versão atual de cada arquivo para poder voltar.
    copia = ANTERIORES / atual
    trocados, criados = [], []
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
        if 'requirements.txt' in trocados + criados:
            subprocess.run([_python_console(), '-m', 'pip', 'install', '-r', str(APP / 'requirements.txt')],
                           check=True, cwd=APP, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    except Exception:
        for caminho in trocados:
            if (copia / caminho).exists():
                os.replace(copia / caminho, _caminho_seguro(caminho))
        for caminho in criados:
            _caminho_seguro(caminho).unlink(missing_ok=True)
        if copia.is_dir() and not (copia / 'versao.txt').exists():
            shutil.rmtree(copia, ignore_errors=True)   # cópia de uma tentativa desfeita
        raise
    (copia / 'versao.txt').parent.mkdir(parents=True, exist_ok=True)
    (copia / 'versao.txt').write_text(json.dumps({'versao': atual, 'trocados': trocados, 'criados': criados}), encoding='utf-8')
    LISTA.write_text('\n'.join(sorted(novos)) + '\n', encoding='utf-8')
    _cache.update(quando=0.0, manifesto=None)
    mudou = set(trocados + criados)
    return {
        'versao': m['versao'],
        # .py/.pyw novos só valem depois de abrir o programa de novo
        'reiniciar': any(c.endswith(('.py', '.pyw')) or c == 'requirements.txt' for c in mudou),
        'atalhos': any(c.startswith('assets/') or c == 'criar-atalhos.ps1' for c in mudou),
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
    shutil.rmtree(pasta)
    return versao_instalada()
