#!/usr/bin/env python3
"""Repairs only the public defects verified on 2026-11-04.

Prepare a narrowly scoped backup/plan; upload it before applying. Refuse stale
content. No post deletion, new content generation, theme or AdSense changes.
"""
import argparse
import copy
import json
import os
import re
from pathlib import Path

import requests

BASE = 'https://aivision.altervista.org'
PLAN = Path('data/site_public_fixes.json')
REPORT = Path('data/site_public_fixes_result.json')
SLUG = 'gta-6-su-ps5-212-gb-e-copie-fisiche-senza-disco'
OLD = 'con due giorni di anticipo rispetto alla data di uscita ufficiale, precisamente a partire da martedì 10 novembre'
NEW = 'a partire da martedì 10 novembre'


def clean_social(value):
    # Match only a single fenced HTML snippet belonging to this social widget.
    if 'Seguici sui social' not in value or 'https://t.me/aivision_tech' not in value:
        return value
    match = re.fullmatch(r'(\s*)```html[ \t]*\r?\n(.*)\r?\n```(\s*)', value, re.S)
    if not match or '```' in match[2]:
        return value
    return match[1] + match[2] + match[3]


def fix_post(value):
    # Only remove the contradictory relative interval. Do not invent a date.
    if '19 novembre' not in value or value.count(OLD) != 1:
        return value
    return value.replace(OLD, NEW, 1)


def widget_change(widget):
    raw = widget.get('instance', {}).get('raw')
    if not isinstance(raw, dict) or widget.get('id_base') not in {'custom_html', 'block', 'text'}:
        return None
    after = copy.deepcopy(raw)
    for key in ('content', 'text'):
        if isinstance(raw.get(key), str):
            after[key] = clean_social(raw[key])
    if after == raw:
        return None
    return {'resource': 'widgets/' + widget['id'], 'kind': 'widget',
            'before': raw, 'after': after}


def request(session, method, resource, **kwargs):
    if not re.fullmatch(r'(?:widgets(?:/[\w-]+)?|posts(?:/\d+)?)', resource):
        raise ValueError('Unexpected resource')
    r = session.request(method, BASE + '/wp-json/wp/v2/' + resource,
                        timeout=(8, 30), allow_redirects=False, **kwargs)
    if r.status_code != 200:
        raise RuntimeError(f'{resource}: HTTP {r.status_code}')
    return r.json()


def current_value(row, data):
    if row['kind'] == 'widget':
        return data.get('instance', {}).get('raw')
    return data.get('content', {}).get('raw')


def prepare(session):
    rows, skipped = [], []
    try:
        widgets = request(session, 'GET', 'widgets', params={'context': 'edit'})
        for widget in widgets:
            row = widget_change(widget)
            if row:
                rows.append(row)
    except RuntimeError as exc:
        skipped.append(str(exc))
    posts = request(session, 'GET', 'posts', params={'slug': SLUG, 'context': 'edit'})
    if len(posts) == 1 and posts[0].get('status') == 'publish':
        before = posts[0].get('content', {}).get('raw')
        if isinstance(before, str) and fix_post(before) != before:
            rows.append({'resource': f"posts/{posts[0]['id']}", 'kind': 'post',
                         'slug': SLUG, 'before': before, 'after': fix_post(before)})
    PLAN.parent.mkdir(parents=True, exist_ok=True)
    PLAN.write_text(json.dumps({'site': BASE, 'changes': rows, 'skipped': skipped},
                               ensure_ascii=False, indent=2))
    print(f'Prepared {len(rows)} exact changes; skipped: {skipped}')


def apply(session):
    plan = json.loads(PLAN.read_text())
    if plan['site'] != BASE:
        raise ValueError('Wrong site')
    results = []
    try:
        for row in plan['changes']:
            # Recompute the change instead of trusting arbitrary plan contents.
            if row['kind'] == 'widget':
                candidate = copy.deepcopy(row['before'])
                for key in ('content', 'text'):
                    if isinstance(candidate.get(key), str):
                        candidate[key] = clean_social(candidate[key])
                payload = {'instance': {'raw': candidate}}
            elif row['kind'] == 'post' and row.get('slug') == SLUG:
                candidate = fix_post(row['before'])
                payload = {'content': candidate}
            else:
                raise ValueError('Unexpected change')
            if candidate != row['after'] or candidate == row['before']:
                raise ValueError('Plan does not match allowed transformation')
            live = request(session, 'GET', row['resource'], params={'context': 'edit'})
            if current_value(row, live) != row['before']:
                raise RuntimeError('Concurrent edit: ' + row['resource'])
            if row['kind'] == 'post' and (live.get('slug') != SLUG or live.get('status') != 'publish'):
                raise RuntimeError('Post changed status/slug')
            request(session, 'POST', row['resource'], json=payload)
            saved = request(session, 'GET', row['resource'], params={'context': 'edit'})
            if current_value(row, saved) != candidate:
                raise RuntimeError('Verification failed: ' + row['resource'])
            results.append({'resource': row['resource'], 'status': 'updated_and_verified'})
            print('Updated and verified:', row['resource'])
    finally:
        REPORT.write_text(json.dumps(results, indent=2))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['prepare', 'apply'])
    args = parser.parse_args()
    base = os.environ.get('WP_BASE_URL', '').rstrip('/').removesuffix('/wp-json')
    user, password = os.environ.get('WP_USERNAME'), os.environ.get('WP_APP_PASSWORD')
    if base != BASE or not user or not password:
        raise SystemExit('Expected existing WordPress configuration for AI Vision')
    session = requests.Session()
    session.auth = (user, password)
    if args.mode == 'prepare':
        prepare(session)
    else:
        apply(session)


if __name__ == '__main__':
    main()
