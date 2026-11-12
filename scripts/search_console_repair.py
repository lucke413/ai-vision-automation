"""Narrow, backed-up improvements for the Search Console URLs of 2026-11-12."""
import json
import os
import sys
from pathlib import Path
import requests

BASE = 'https://aivision.altervista.org'
PLAN = Path('data/search_console_plan.json')
RESULT = Path('data/search_console_result.json')
TARGET = BASE + '/mappa-di-gta-6-aperta-da-subito/'
POST_SLUG = 'preload-di-gta-6-disponibile-ps5-xbox-orari'
LINK = '<p>Leggi anche il nostro approfondimento sulla <a href="' + TARGET + '">mappa di GTA 6 e l’esplorazione di Leonida</a>.</p>'
DESCRIPTIONS = {
    'ps5': 'Notizie e approfondimenti su PlayStation 5: giochi, servizi PlayStation Plus e indicazioni su download e disponibilità dei titoli. Le date e le condizioni riportate si riferiscono ai singoli articoli e possono cambiare nel tempo.',
    'guida-autonoma': 'Articoli sui sistemi di guida automatizzata e sulle funzioni di assistenza alla guida. Assistenza e autonomia non sono equivalenti: per comprendere il ruolo del conducente occorre distinguere le funzioni descritte, i limiti operativi e le condizioni di utilizzo.',
    'auricolari-wireless': 'Approfondimenti sugli auricolari wireless: caratteristiche, cancellazione del rumore, riparabilità e batterie sostituibili. Gli articoli aiutano a confrontare le funzioni descritte; prezzi e disponibilità vanno verificati alla data di acquisto.',
}


def request(session, method, resource, **kwargs):
    r = session.request(method, BASE + '/wp-json/wp/v2/' + resource,
                        timeout=(8, 30), allow_redirects=False, **kwargs)
    if r.status_code != 200:
        raise RuntimeError(f'{resource}: HTTP {r.status_code}')
    return r.json()


def value(item, field):
    return item['content']['raw'] if field == 'content' else item[field]


def prepare(session):
    rows = []
    for slug, description in DESCRIPTIONS.items():
        items = request(session, 'GET', 'tags', params={'slug': slug, 'context': 'edit'})
        if len(items) != 1 or items[0]['count'] < 1:
            raise RuntimeError('Tag missing or empty: ' + slug)
        item = items[0]
        if not item['description'].strip():
            rows.append({'resource': f"tags/{item['id']}", 'slug': slug,
                         'field': 'description', 'before': item['description'], 'after': description})
    items = request(session, 'GET', 'posts', params={'slug': POST_SLUG, 'context': 'edit'})
    target = request(session, 'GET', 'posts', params={'slug': TARGET.rstrip('/').split('/')[-1]})
    if len(target) != 1 or target[0]['status'] != 'publish' or target[0]['link'] != TARGET:
        raise RuntimeError('Link destination is not the expected published post')
    if len(items) != 1 or items[0]['status'] != 'publish':
        raise RuntimeError('Source post is not published or unique')
    item = items[0]
    before = item['content']['raw']
    if TARGET not in before:
        rows.append({'resource': f"posts/{item['id']}", 'slug': POST_SLUG,
                     'field': 'content', 'before': before, 'after': before.rstrip() + '\n' + LINK + '\n'})
    PLAN.parent.mkdir(exist_ok=True)
    PLAN.write_text(json.dumps({'site': BASE, 'changes': rows}, ensure_ascii=False, indent=2))
    print('Prepared changes:', len(rows))


def apply(session):
    plan = json.loads(PLAN.read_text())
    if plan['site'] != BASE:
        raise RuntimeError('Unexpected site')
    results = []
    try:
        for row in plan['changes']:
            field = row['field']
            if field == 'description' and row['slug'] in DESCRIPTIONS and not row['before'].strip():
                expected = DESCRIPTIONS[row['slug']]
                prefix = 'tags/'
            elif field == 'content' and row['slug'] == POST_SLUG and TARGET not in row['before']:
                expected = row['before'].rstrip() + '\n' + LINK + '\n'
                prefix = 'posts/'
            else:
                raise RuntimeError('Unapproved transformation')
            if row['after'] != expected or not row['resource'].startswith(prefix) or not row['resource'][len(prefix):].isdigit():
                raise RuntimeError('Invalid plan')
            live = request(session, 'GET', row['resource'], params={'context': 'edit'})
            if live['slug'] != row['slug'] or value(live, field) != row['before']:
                raise RuntimeError('Concurrent edit: ' + row['resource'])
            if field == 'content' and live['status'] != 'publish':
                raise RuntimeError('Source post changed status')
            request(session, 'POST', row['resource'], json={field: expected})
            saved = request(session, 'GET', row['resource'], params={'context': 'edit'})
            if value(saved, field).strip() != expected.strip():
                raise RuntimeError('Verification failed: ' + row['resource'])
            results.append({'resource': row['resource'], 'slug': row['slug'], 'status': 'updated_and_verified'})
            print('Updated and verified:', row['resource'], row['slug'])
    finally:
        RESULT.write_text(json.dumps(results, indent=2))


if __name__ == '__main__':
    if os.environ.get('WP_BASE_URL', '').rstrip('/').removesuffix('/wp-json') != BASE:
        raise SystemExit('Unexpected WordPress site')
    session = requests.Session()
    session.auth = (os.environ['WP_USERNAME'], os.environ['WP_APP_PASSWORD'])
    {'prepare': prepare, 'apply': apply}[sys.argv[1]](session)
