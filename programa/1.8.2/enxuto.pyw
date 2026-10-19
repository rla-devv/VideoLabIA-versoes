# Enxuto (Windows): a página do app numa janela do pywebview (WebView2), aberta pelo atalho.
#
#   pythonw enxuto.pyw              abre na janela (é o que o atalho faz)
#   pythonw enxuto.pyw --navegador  abre no navegador padrão
#
# Sobe um servidor só em 127.0.0.1 (nada fica acessível pela rede) que entrega a página (index.html)
# e o conversor extra (ffmpeg/), e responde à consulta e à instalação de atualizações (/api/atualizacao).
# Se o pywebview faltar, abre no navegador. As mensagens vão para logs/enxuto.log.
import html
import json
import logging
import mimetypes
import os
import secrets
import subprocess
import sys
import threading
import traceback
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

APP = Path(__file__).resolve().parent
PORTA = 47811            # fixa, para o tema e as preferências (guardados por endereço) não se perderem
TITULO = 'Enxuto'
DADOS_JANELA = APP / 'dados-janela'   # preferências da janela; a atualização nunca mexe aqui
ICONE = APP / 'assets' / 'enxuto-v2.ico'   # nome novo a cada troca de ícone: o Windows guarda ícones em cache pelo nome
NO_WINDOW = getattr(subprocess, 'CREATE_NO_WINDOW', 0)

(APP / 'logs').mkdir(exist_ok=True)
logging.basicConfig(filename=APP / 'logs' / 'enxuto.log', level=logging.INFO, encoding='utf-8',
                    format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger('enxuto')
if sys.stdout is None or sys.stderr is None:    # pythonw: sem janela preta, tudo vai para o log
    sys.stdout = sys.stderr = open(APP / 'logs' / 'enxuto.log', 'a', encoding='utf-8', buffering=1)

sys.path.insert(0, str(APP))
import atualizacao  # noqa: E402

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
                return self._json(200, atualizacao.verificar(forcar='forcar=1' in (urlsplit(self.path).query or '')))
            except Exception as e:  # sem internet etc.: a página decide o que mostrar
                log.warning('consulta de atualização falhou: %s', e)
                return self._json(200, {'atual': atualizacao.versao_instalada(), 'nova': None, 'erro': str(e)})
        if path in ('/', '/index.html'):
            pagina = (APP / 'index.html').read_text(encoding='utf-8')
            marca = f'<script>window.__ENXUTO_APP = {{ token: {json.dumps(TOKEN)}, api: 2 }};</script>\n'
            pagina = pagina.replace('<head>\n', '<head>\n' + marca, 1)
            return self._send(200, pagina.encode('utf-8'), 'text/html; charset=utf-8')
        # Só entrega o conversor extra e o ícone; nada mais da pasta do app.
        if path.startswith('/ffmpeg/') or path.startswith('/assets/'):
            alvo = (APP / path.lstrip('/')).resolve()
            if alvo.is_file() and alvo.parent in ((APP / 'ffmpeg').resolve(), (APP / 'assets').resolve()):
                ctype = mimetypes.guess_type(alvo.name)[0] or 'application/octet-stream'
                return self._send(200, alvo.read_bytes(), ctype)
        return self._send(404, 'Não encontrado'.encode('utf-8'), 'text/plain; charset=utf-8')

    def do_POST(self):
        if not self._host_ok() or self.headers.get('X-Enxuto-Token') != TOKEN:
            return self._json(403, {'erro': 'sem permissão'})
        path = urlsplit(self.path).path
        try:
            if path == '/api/atualizacao':
                r = atualizacao.instalar()
                if r['atalhos']:
                    atualizar_atalhos(forcar=True)
                self._json(200, {'ok': True, **r})
                if r['reiniciar']:   # código novo do programa: abre de novo, já na versão nova
                    threading.Timer(0.8, reiniciar).start()
                return
            if path == '/api/atualizacao/restaurar':
                return self._json(200, {'ok': True, 'versao': atualizacao.restaurar()})
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


def atualizar_atalhos(forcar=False):
    """Põe o ícone atual nos atalhos que já existem (Área de Trabalho e Menu Iniciar). Só no Windows."""
    if os.name != 'nt' or not ICONE.is_file():
        return
    marca = DADOS_JANELA / 'icone-dos-atalhos.txt'
    try:
        if not forcar and marca.is_file() and marca.read_text(encoding='utf-8').strip() == ICONE.name:
            return
        subprocess.run(['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
                        str(APP / 'criar-atalhos.ps1'), '-SoAtualizar'],
                       check=True, timeout=60, creationflags=NO_WINDOW, capture_output=True)
        DADOS_JANELA.mkdir(exist_ok=True)
        marca.write_text(ICONE.name, encoding='utf-8')
        log.info('atalhos atualizados com %s', ICONE.name)
    except Exception:
        log.exception('não consegui atualizar o ícone dos atalhos')


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
    return f'''<!doctype html><html lang="pt-BR"><meta charset="utf-8"><title>Enxuto</title>
<body style="font:16px system-ui,sans-serif;max-width:640px;margin:48px auto;padding:0 20px;color:#13201f">
<h1 style="font-size:1.4rem">O Enxuto não conseguiu abrir</h1>
<p>Tente fechar e abrir de novo pelo atalho. Se continuar, rode o <b>instalar.bat</b> outra vez.</p>
<p>Os detalhes ficaram em <b>{html.escape(str(APP / 'logs' / 'enxuto.log'))}</b>.</p>
<pre style="white-space:pre-wrap;background:#eef3f2;padding:12px;border-radius:8px;font-size:13px">{html.escape(detalhe)}</pre>
</body></html>'''


def abrir_no_navegador(url):
    log.info('abrindo no navegador: %s', url)
    webbrowser.open(url)
    threading.Event().wait()   # mantém o servidor no ar enquanto a página estiver aberta


def main():
    navegador = '--navegador' in sys.argv
    try:
        if not (APP / 'index.html').is_file():
            raise FileNotFoundError(f'index.html não encontrado em {APP}')
        srv, url = subir_servidor()
        log.info('Enxuto %s em %s', atualizacao.versao_instalada(), url)
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

    threading.Thread(target=atualizar_atalhos, daemon=True).start()
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
