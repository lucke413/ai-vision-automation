#!/usr/bin/env python3
"""Invia i post pubblici a Telegram; registro persistente sul ramo telegram-state.
Il primo avvio registra gli articoli esistenti senza inviarli. Un invio con
esito incerto resta pending e richiede verifica manuale, per evitare doppioni.
"""
import base64
import html
import json
import os
import re
import sys
import uuid
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser

BRANCH = 'telegram-state'
STATE_PATH = 'data/telegram_state.json'

class APIError(Exception):
    def __init__(self, service, code, description=''):
        self.code = code
        self.description = (description or '').strip()
        detail = f' - {self.description}' if self.description else ''
        super().__init__(f'{service}: errore HTTP/API {code}{detail}')

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None

def request_json(url, service, method='GET', payload=None, token=None):
    headers = {'User-Agent': 'AI-Vision-Telegram/1.0', 'Accept': 'application/json'}
    if service == 'WordPress' and method == 'GET':
        headers.update({'Cache-Control': 'no-cache, no-store, max-age=0', 'Pragma': 'no-cache'})
    if token:
        headers['Authorization'] = f'Bearer {token}'
        headers['X-GitHub-Api-Version'] = '2022-11-28'
    body = None
    if payload is not None:
        body = json.dumps(payload).encode()
        headers['Content-Type'] = 'application/json'
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.build_opener(NoRedirect()).open(req, timeout=30) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        # Telegram restituisce quasi sempre una descrizione utile nel JSON
        # (es. immagine non scaricabile). Non includiamo mai URL/token nel log.
        description = ''
        try:
            error_data = json.loads(exc.read().decode('utf-8', errors='replace'))
            description = str(error_data.get('description', ''))
        except Exception:
            pass
        raise APIError(service, exc.code, description) from None
    except Exception:
        # Non stampare eccezioni urllib: possono contenere il token nell'URL.
        raise RuntimeError(f'{service}: risposta non disponibile o non valida') from None

class TextParser(HTMLParser):
    def __init__(self):
        super().__init__(); self.parts = []; self.hidden = 0
    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'): self.hidden += 1
        elif tag in ('p', 'br', 'div'): self.parts.append(' ')
    def handle_endtag(self, tag):
        if tag in ('script', 'style'): self.hidden = max(0, self.hidden - 1)
        elif tag in ('p', 'div'): self.parts.append(' ')
    def handle_data(self, text):
        if not self.hidden: self.parts.append(text)

def plain(value):
    parser = TextParser(); parser.feed(value or '')
    return re.sub(r'\s+', ' ', html.unescape(''.join(parser.parts))).strip()

def short(text, limit):
    return text if len(text) <= limit else text[:limit-1].rstrip() + '…'

def caption(post):
    title = short(plain(post['title']['rendered']), 200)
    excerpt = short(plain(post.get('excerpt', {}).get('rendered', '')), 260)
    return f'<b>{html.escape(title)}</b>\n\n{html.escape(excerpt)}\n\n<a href="{html.escape(post["link"], quote=True)}">Leggi su AI Vision →</a>'

def public_ready(post, base):
    url = urllib.parse.urlsplit(post.get('link', ''))
    expected = urllib.parse.urlsplit(base)
    if post.get('status') != 'publish' or url.scheme != 'https' or url.netloc != expected.netloc:
        return False
    try:
        req = urllib.request.Request(post['link'], headers={'User-Agent': 'AI-Vision-Telegram/1.0'})
        with urllib.request.urlopen(req, timeout=30) as response:
            if response.status != 200 or urllib.parse.urlsplit(response.url).netloc != expected.netloc:
                return False
            page = response.read(3_000_000).decode('utf-8', errors='replace')
        # Un 200 di una pagina d'errore non basta: deve esserci il titolo del post.
        return plain(post['title']['rendered']).casefold() in plain(page).casefold()
    except Exception:
        return False

class State:
    def __init__(self, repository, token):
        self.root = f'https://api.github.com/repos/{repository}'
        self.token = token; self.sha = None
    def api(self, path, method='GET', payload=None):
        return request_json(self.root + path, 'GitHub', method, payload, self.token)
    def load(self):
        try:
            self.api(f'/git/ref/heads/{BRANCH}')
        except APIError as exc:
            if exc.code != 404: raise
            repo = self.api('')
            default = urllib.parse.quote(repo['default_branch'], safe='')
            ref = self.api(f'/git/ref/heads/{default}')
            self.api('/git/refs', 'POST', {'ref': f'refs/heads/{BRANCH}', 'sha': ref['object']['sha']})
        try:
            result = self.api(f'/contents/{STATE_PATH}?ref={BRANCH}')
        except APIError as exc:
            if exc.code == 404: return None
            raise
        self.sha = result['sha']
        data = json.loads(base64.b64decode(result['content']))
        if data.get('version') != 1 or not isinstance(data.get('posts'), dict):
            raise RuntimeError('Registro Telegram non valido: invio interrotto.')
        return data
    def save(self, data):
        payload = {'message': 'Aggiorna registro Telegram [skip ci]', 'branch': BRANCH,
                   'content': base64.b64encode(json.dumps(data, ensure_ascii=False, indent=2).encode()).decode()}
        if self.sha: payload['sha'] = self.sha
        result = self.api(f'/contents/{STATE_PATH}', 'PUT', payload)
        self.sha = result['content']['sha']

def posts(base):
    result = []
    refresh = uuid.uuid4().hex
    for page in range(1, 101):
        query = urllib.parse.urlencode({'status': 'publish', 'per_page': 100, 'page': page,
                                       'orderby': 'date', 'order': 'asc', '_embed': 'wp:featuredmedia',
                                       '_aivision_refresh': refresh})
        try:
            batch = request_json(f'{base}/wp-json/wp/v2/posts?{query}', 'WordPress')
        except APIError as exc:
            if exc.code == 400 and page > 1 and result: return result
            raise
        if not isinstance(batch, list): raise RuntimeError('Elenco WordPress non valido')
        result.extend(batch)
        if len(batch) < 100: return result
    raise RuntimeError('Troppi articoli: ampliare la paginazione prima di inviare.')

def telegram_call(token, method, payload):
    result = request_json(f'https://api.telegram.org/bot{token}/{method}', 'Telegram', 'POST', payload)
    if not result.get('ok'):
        raise APIError('Telegram', result.get('error_code', 'unknown'), result.get('description', ''))
    return result['result']['message_id']

def send(post, token, chat):
    text = caption(post)
    media = post.get('_embedded', {}).get('wp:featuredmedia', [])
    photo = media[0].get('source_url') if media and isinstance(media[0], dict) else None

    if photo:
        try:
            return telegram_call(token, 'sendPhoto', {
                'chat_id': chat, 'parse_mode': 'HTML', 'photo': photo, 'caption': text
            })
        except APIError as exc:
            # Un 400 su sendPhoto è quasi sempre legato all'immagine WordPress
            # (URL/formato/dimensioni/fetch Telegram). Il post può comunque
            # essere pubblicato in modo sicuro come messaggio testuale.
            if exc.code != 400:
                raise
            print(f'::warning::Immagine rifiutata da Telegram per post {post["id"]}: '
                  f'{exc.description or "HTTP 400"}. Invio il link senza immagine.')

    return telegram_call(token, 'sendMessage', {
        'chat_id': chat, 'parse_mode': 'HTML', 'text': text,
        'disable_web_page_preview': False
    })

def sync(store, published, base, token, chat):
    data = store.load()
    if data is None:
        data = {'version': 1, 'site': base, 'chat': chat, 'posts': {
            str(p['id']): {'status': 'baseline'} for p in published if p.get('status') == 'publish'}}
        store.save(data)
        print(f'Inizializzazione OK: {len(data["posts"])} articoli esistenti esclusi. Nessun messaggio inviato.')
        return
    if data.get('site') != base or data.get('chat') != chat:
        raise RuntimeError('Sito o canale diverso dal registro: verificare configurazione.')
    print(f'WordPress: {len(published)} articoli pubblicati trovati. Registro: {len(data["posts"])} articoli.')
    print('ID ricevuti da WordPress: ' + ', '.join(str(p['id']) for p in published))
    sent_count = 0
    for post in published:
        key = str(post['id'])
        record = data['posts'].get(key)
        if record:
            if record['status'] == 'pending':
                print(f'::warning::Post {key}: invio incerto. Verificare il canale e il registro; non reinviato.')
            continue
        if not public_ready(post, base):
            print(f'Post {key}: pagina non pronta, riprovo al prossimo controllo.'); continue
        data['posts'][key] = {'status': 'pending', 'at': datetime.now(timezone.utc).isoformat()}
        store.save(data)  # Prima dell'invio: niente doppioni dopo un crash.
        try:
            message_id = send(post, token, chat)
        except APIError as exc:
            # Rifiuto esplicito: nessun messaggio creato. Riprovabile.
            if exc.code in (400, 401, 403, 404, 429):
                del data['posts'][key]; store.save(data)
            raise
        data['posts'][key].update(status='sent', message_id=message_id)
        store.save(data)
        sent_count += 1
        print(f'OK: articolo {key} inviato a Telegram, messaggio {message_id}.')
    print(f'Controllo Telegram completato. Nuovi messaggi inviati: {sent_count}.')

def main():
    names = ('WP_BASE_URL', 'GITHUB_REPOSITORY', 'GITHUB_TOKEN', 'TELEGRAM_BOT_TOKEN', 'TELEGRAM_CHAT_ID')
    env = {name: os.environ.get(name, '').strip() for name in names}
    if not all(env.values()): raise RuntimeError('Configurare tutti i secret e le variabili richiesti.')
    base = env['WP_BASE_URL'].rstrip('/')
    if urllib.parse.urlsplit(base).scheme != 'https': raise RuntimeError('WP_BASE_URL deve usare HTTPS.')
    store = State(env['GITHUB_REPOSITORY'], env['GITHUB_TOKEN'])
    sync(store, posts(base), base, env['TELEGRAM_BOT_TOKEN'], env['TELEGRAM_CHAT_ID'])

if __name__ == '__main__':
    try: main()
    except Exception as exc:
        print(f'ERRORE: {exc}', file=sys.stderr); sys.exit(1)
