"""Journaled WP publication; ambiguous creates never get blindly retried."""
from __future__ import annotations
import base64
import copy
import json
import os
import re
from html import escape
from pathlib import Path
from urllib.parse import urlsplit
import requests
from .content import BASE, download, safe_url, sha

START='<!-- aivision-connect:start -->';END='<!-- aivision-connect:end -->'
SOCIALS=('https://www.facebook.com/share/1EjXMnhx7D/','https://t.me/aivision_tech')
class Journal:
    def __init__(self):
        self.repo=os.environ.get('GITHUB_REPOSITORY','lucke413/ai-vision-automation')
        if self.repo!='lucke413/ai-vision-automation':raise ValueError('Unexpected repository')
        self.branch='magazine-state';self.path='data/magazine.json';self.file_sha=None
        self.session=requests.Session();self.session.headers['Authorization']='Bearer '+os.environ['GITHUB_TOKEN']
        self.session.headers['Accept']='application/vnd.github+json'
        root=self.api('GET','/git/ref/heads/'+self.branch,optional=True)
        if root is None:
            main=self.api('GET','/git/ref/heads/main')
            self.api('POST','/git/refs',json={'ref':'refs/heads/'+self.branch,'sha':main['object']['sha']})
        data=self.api('GET','/contents/'+self.path,params={'ref':self.branch},optional=True)
        if data:
            self.file_sha=data['sha'];self.data=json.loads(base64.b64decode(data['content']))
            if self.data.get('version')!=1 or not isinstance(self.data.get('issues'),dict):raise ValueError('Invalid journal')
        else:self.data={'version':1,'issues':{},'operations':{}}
    def api(self,method,path,optional=False,**kw):
        try:r=self.session.request(method,'https://api.github.com/repos/'+self.repo+path,timeout=45,allow_redirects=False,**kw)
        except requests.RequestException:raise RuntimeError('Magazine journal network error') from None
        if optional and r.status_code==404:return None
        if not 200<=r.status_code<300:raise RuntimeError(f'Magazine journal HTTP {r.status_code}')
        return r.json()
    def save(self):
        payload={'message':'Update magazine journal [skip ci]','branch':self.branch,
          'content':base64.b64encode(json.dumps(self.data,ensure_ascii=False,indent=2).encode()).decode()}
        if self.file_sha:payload['sha']=self.file_sha
        result=self.api('PUT','/contents/'+self.path,json=payload);self.file_sha=result['content']['sha']

class WordPress:
    def __init__(self,journal):
        self.journal=journal;self.session=requests.Session()
        base=os.environ.get('WP_BASE_URL',BASE).rstrip('/')
        if base!=BASE:raise ValueError('Unexpected WordPress origin')
        self.session.auth=(os.environ['WP_USERNAME'],os.environ['WP_APP_PASSWORD'])
    def api(self,method,path,**kw):
        try:r=self.session.request(method,BASE+'/wp-json/wp/v2/'+path,timeout=(10,90),allow_redirects=False,**kw)
        except requests.RequestException:raise RuntimeError('WordPress network error; inspect pending journal before retry') from None
        if not 200<=r.status_code<300:raise RuntimeError(f'WordPress HTTP {r.status_code}; operation stopped')
        return r.json()
    def exact(self,kind,slug):
        params={'slug':slug,'context':'edit','per_page':100}
        if kind in ('posts','pages'):params['status']='publish,draft,pending,private,future'
        matches=[x for x in self.api('GET',kind,params=params) if x.get('slug')==slug]
        if len(matches)>1:raise ValueError('Ambiguous WordPress slug')
        return matches[0] if matches else None
    def once(self,key,lookup,create):
        ops=self.journal.data['operations'];existing=lookup()
        if existing is not None:
            ops[key]={'status':'done','id':existing['id']};self.journal.save();return existing
        if key in ops:raise RuntimeError('Unresolved or deleted remote object: '+key)
        ops[key]={'status':'pending'};self.journal.save()
        value=create() # No retry after timeout, HTTP error or crash.
        ops[key]={'status':'done','id':value['id']};self.journal.save();return value
    def media(self,path,slug,mime):
        path=Path(path);expected=sha(path.read_bytes())
        result=self.once('media/'+slug,lambda:self.exact('media',slug),lambda:self.api('POST','media',
          headers={'Content-Disposition':f'attachment; filename="{slug}{path.suffix}"','Content-Type':mime},data=path.read_bytes()))
        raw,_,_=download(result['source_url'],{'aivision.altervista.org'},20_000_000)
        if sha(raw)!=expected:raise ValueError('Uploaded file differs from validated artifact')
        return result
    def issue(self,manifest,directory):
        issue=manifest['issue'];slug='aivision-magazine-'+issue
        record=self.journal.data['issues'].get(issue)
        if record and record['pdf_sha256']!=manifest['pdf_sha256']:raise ValueError('Different PDF for reserved issue; restore original run artifact')
        if not record:
            for previous in self.journal.data['issues'].values():
                if previous.get('manifest',{}).get('art_hashes',{}).get('cover')==manifest.get('art_hashes',{}).get('cover'):
                    raise ValueError('Cover illustration already used')
            self.journal.data['issues'][issue]={'status':'reserved','pdf_sha256':manifest['pdf_sha256'],'manifest':manifest};self.journal.save()
        pdf=self.media(Path(directory)/manifest['pdf'],slug+'-'+manifest['pdf_sha256'][:12],'application/pdf')
        cover=self.media(Path(directory)/'cover.jpg',slug+'-cover-'+manifest['cover_sha256'][:12],'image/jpeg')
        draft=self.once('posts/'+slug,lambda:self.exact('posts',slug),lambda:self.api('POST','posts',json={'slug':slug,'status':'draft','title':manifest['title']}))
        category=self.once('categories/aivision-magazine',lambda:self.exact('categories','aivision-magazine'),lambda:self.api('POST','categories',json={'slug':'aivision-magazine','name':'AIVision Magazine'}))
        content=issue_html(manifest,pdf['source_url'],cover['source_url'])
        if draft['status']!='publish':
            draft=self.api('POST',f'posts/{draft["id"]}',json={'title':manifest['title'],'content':content,'featured_media':cover['id'],
                'excerpt':manifest['deck'],'categories':[category['id']],'status':'publish','comment_status':'closed','ping_status':'closed'})
        # Published issue itself feeds the EXISTING Telegram/Facebook jobs, once per WP ID.
        record=self.journal.data['issues'][issue]
        record.update(status='published',post_id=draft['id'],url=draft['link'],pdf_url=pdf['source_url'],cover_url=cover['source_url'])
        self.journal.save();return record
    def archive(self):
        records=[v for k,v in sorted(self.journal.data['issues'].items(),reverse=True) if v.get('status')=='published']
        if not records:return None
        page=self.once('pages/aivision-magazine',lambda:self.exact('pages','aivision-magazine'),lambda:self.api('POST','pages',json={'slug':'aivision-magazine','status':'draft','title':'AIVision Magazine'}))
        body='<p>Il settimanale AIVision: notizie, approfondimenti originali, guide e idee da provare.</p>'
        for i,record in enumerate(records):
            m=record['manifest'];body+=f'<h2>{"Ultimo numero · " if i==0 else ""}{escape(m["title"])}</h2>'+issue_html(m,record['pdf_url'],record['cover_url'])
            body+=f'<p><a href="{escape(record["url"],quote=True)}">Pagina del numero</a></p>'
        body+=f'<p><a href="{BASE}/feed/">Segui AIVision via RSS</a></p>'
        form=newsletter_url()
        if form:
            body+=f'<section style="margin:24px 0;padding:18px;border-radius:12px;background:#eef7ff"><h2>Newsletter AIVision</h2><p>Ricevi il nuovo numero via email. Conferma l’iscrizione dal messaggio che riceverai; la disiscrizione è sempre disponibile.</p><p><a href="{escape(form,quote=True)}">Iscriviti alla newsletter</a></p></section>'
        else:
            body+='<section style="margin:24px 0;padding:18px;border-radius:12px;background:#eef7ff"><h2>Newsletter AIVision</h2><p>Il modulo di iscrizione è in configurazione. Al momento il sito non raccoglie indirizzi email. La newsletter sarà attivata dopo la verifica del consenso, della conferma email e della disiscrizione.</p></section>'
        page=self.api('POST',f'pages/{page["id"]}',json={'content':body,'status':'publish'})
        return page['link'],records[0]['url']
    def repair_feed_identity(self):
        """Fill only missing public site identity used by WordPress RSS."""
        settings=self.api('GET','settings')
        defaults={'title':'AIVision','description':'Intelligenza artificiale, tecnologia e guide pratiche.'}
        changes={key:value for key,value in defaults.items() if key in settings and isinstance(settings[key],str) and not settings[key].strip()}
        if not changes:return
        self.journal.data.setdefault('rss_identity_backup',{key:settings[key] for key in changes})
        self.journal.save()
        self.api('POST','settings',json=changes)
        check=self.api('GET','settings')
        if any(check.get(key)!=value for key,value in changes.items()):raise ValueError('RSS identity readback failed')

    def widget(self,latest=None):
        import xml.etree.ElementTree as ET
        feed,_,_=download(BASE+'/feed/',{'aivision.altervista.org'})
        if ET.fromstring(feed).tag!='rss':raise ValueError('RSS feed invalid')
        widget=self.api('GET','widgets/block-20',params={'context':'edit'})
        raw=widget.get('instance',{}).get('raw')
        if widget.get('id')!='block-20' or widget.get('id_base')!='block' or not isinstance(raw,dict):raise ValueError('Unexpected existing widget structure')
        old=raw.get('content','');new=extend_widget(old,latest,newsletter_url())
        if old==new:return
        # Journal keeps a recoverable original, never replaces it with an updated variant.
        self.journal.data.setdefault('widget_backup',{'id':'block-20','sidebar':widget['sidebar'],'instance':copy.deepcopy(raw)})
        self.journal.save()
        updated={**raw,'content':new}
        self.api('POST','widgets/block-20',json={'instance':{'raw':updated}})
        check=self.api('GET','widgets/block-20',params={'context':'edit'})
        actual=check.get('instance',{}).get('raw',{}).get('content','')
        if any(url not in actual for url in SOCIALS) or START not in actual or BASE+'/feed/' not in actual or (newsletter_url() and '<iframe' not in actual):raise ValueError('Widget readback failed; original preserved in journal')

def newsletter_url():
    url=os.environ.get('NEWSLETTER_FORM_URL','').strip()
    if not url:return ''
    # The provider owns email input, consent, errors, DOI and unsubscribe; never post subscriber data to GitHub.
    if os.environ.get('NEWSLETTER_DOI_VERIFIED')!='true':raise ValueError('Newsletter form must pass DOI/consent/unsubscribe test')
    host=urlsplit(url).hostname or ''
    if not (host=='sibforms.com' or host.endswith('.sibforms.com')):raise ValueError('Only configured Brevo hosted forms supported')
    return safe_url(url,{host})

def extend_widget(content,latest=None,form=''):
    if 'aiv-social-box' not in content or any(s not in content for s in SOCIALS):raise ValueError('Original social widget not recognized')
    if content.count(START)!=content.count(END) or content.count(START)>1:raise ValueError('Malformed widget markers')
    clean=re.sub(re.escape(START)+r'.*?'+re.escape(END),'',content,flags=re.S)
    # Insert within the existing widget's outer final div, preserving every social link and style.
    pos=clean.rfind('</div>')
    if pos<0:raise ValueError('Widget container missing')
    extra=START+'<div class="aiv-connect-extra" style="display:grid;gap:10px;margin-top:14px">'
    extra+=f'''<details style="padding:12px;border-radius:10px;background:#fff3e6;color:#082c4b;border:1px solid #f68b24">
<summary style="cursor:pointer;font-weight:700">RSS · Segui gli aggiornamenti</summary>
<p style="margin:10px 0">Ricevi i nuovi articoli nel tuo lettore RSS. Copia questo indirizzo e aggiungilo come nuova fonte:</p>
<code style="display:block;overflow-wrap:anywhere;user-select:all;background:#fff;padding:8px;color:#082c4b">{BASE}/feed/</code>
<p style="margin:10px 0 0"><a href="{BASE}/feed/" type="application/rss+xml" style="color:#082c4b;text-decoration:underline">Apri il feed RSS (XML)</a></p>
<small>Se nel browser vedi codice XML, è normale: il feed va aperto con un lettore RSS.</small>
</details>'''
    if latest:
        safe_url(latest,{'aivision.altervista.org'})
        extra+=f'<a href="{escape(latest,quote=True)}" style="display:block;padding:12px;border-radius:10px;background:#ffe326;color:#082c4b;font-weight:700">Leggi l’ultimo Magazine</a>'
    if form:
        # Lazy hosted form provides the email field, provider errors, consent and DOI. No local email storage.
        extra+=f'<iframe src="{escape(form,quote=True)}" title="Iscriviti alla newsletter AIVision" loading="lazy" style="width:100%;height:480px;border:0;background:white;border-radius:10px"></iframe>'
        extra+=f'<a href="{escape(form,quote=True)}" style="display:block;padding:12px;border-radius:10px;background:#fff;color:#082c4b;font-weight:700">Iscriviti alla newsletter</a><small>Inserisci l’email nel modulo e conferma dal messaggio ricevuto. Puoi disiscriverti in ogni momento.</small>'
    else:
        extra+='<div style="padding:14px;border-radius:10px;background:#eef7ff;color:#082c4b"><strong>Newsletter AIVision</strong><p style="margin:8px 0 0">Iscrizione via email in configurazione. Al momento non raccogliamo indirizzi: il modulo sarà attivato dopo il collaudo di consenso, conferma e disiscrizione.</p></div>'
    extra+='</div>'+END
    return clean[:pos]+extra+clean[pos:]

def issue_html(m,pdf,cover):
    safe_url(pdf,{'aivision.altervista.org'});safe_url(cover,{'aivision.altervista.org'})
    return (f'<p>{escape(m["period"])}</p><img src="{escape(cover,quote=True)}" alt="Copertina {escape(m["title"],quote=True)}" width="595" height="842" loading="lazy" style="max-width:100%;height:auto">'
      f'<p>{escape(m["deck"])}</p><p><a href="{escape(pdf,quote=True)}">Leggi il numero</a> · <a href="{escape(pdf,quote=True)}" download>Scarica PDF</a></p>')
