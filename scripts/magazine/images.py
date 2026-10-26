"""Free, attributed Commons imagery. No billing, scraping credentials or vague licenses."""
from __future__ import annotations
import io
import json
import re
from pathlib import Path
from urllib.parse import urlsplit
import requests
from PIL import Image,ImageOps
from .content import download,plain,safe_url,sha

UA='AIVisionMagazine/1.0 (+https://aivision.altervista.org/)'
LICENSES={
 'CC BY 2.0':'https://creativecommons.org/licenses/by/2.0/',
 'CC BY 3.0':'https://creativecommons.org/licenses/by/3.0/',
 'CC BY 4.0':'https://creativecommons.org/licenses/by/4.0/',
 'CC0':'https://creativecommons.org/publicdomain/zero/1.0/',
}
def rights(info):
    meta=info.get('extmetadata',{})
    def value(key):return plain(meta.get(key,{}).get('value','')).strip()
    license=value('LicenseShortName');url=value('LicenseUrl').replace('http://','https://')
    url=re.sub(r'/deed\.[a-zA-Z_-]+/?$','/',url)
    if value('Restrictions'):return None
    if license=='Public domain' and value('Copyrighted').lower()=='false':url='https://creativecommons.org/publicdomain/mark/1.0/'
    elif license not in LICENSES or url.rstrip('/')!=LICENSES[license].rstrip('/'):return None
    artist=value('Artist')
    if not artist or len(artist)>180 or not value('ObjectName') or len(value('ObjectName'))>160:return None
    source=info.get('descriptionurl','')
    safe_url(source,{'commons.wikimedia.org'})
    return {'license':license,'license_url':url,'artist':artist,'source':source,'title':value('ObjectName')}

def candidates(query):
    if not isinstance(query,str) or not 3<=len(query)<=100:raise ValueError('Invalid image query')
    response=requests.get('https://commons.wikimedia.org/w/api.php',params={
      'action':'query','format':'json','generator':'search','gsrsearch':query+' filetype:bitmap',
      'gsrnamespace':6,'gsrlimit':12,'prop':'imageinfo','iiprop':'url|size|mime|extmetadata',
      'iiurlwidth':1600,'iiextmetadatafilter':'LicenseShortName|LicenseUrl|Copyrighted|Restrictions|Artist|ObjectName'},
      headers={'User-Agent':UA},timeout=45,allow_redirects=False)
    if response.status_code!=200:raise ValueError(f'Commons API HTTP {response.status_code}')
    result=response.json()
    if result.get('error'):raise ValueError('Commons query rejected')
    pages=result.get('query',{}).get('pages',{})
    return [p['imageinfo'][0] for p in sorted(pages.values(),key=lambda p:p.get('index',999)) if p.get('imageinfo')]

def free_images(client,briefs,folder,previous_covers=()):
    """Fail closed if rights, relevance or visual quality cannot be established."""
    query_data=client.json('Converti ogni brief in 2 ricerche fotografiche inglesi per Wikimedia Commons, 2-5 parole ciascuna. Soggetti concreti, attuali, pertinenti, non loghi o schermate. Evita concetti astratti impossibili da trovare. Restituisci JSON {chiave:[ricerca1,ricerca2]} con esattamente le chiavi in input. INPUT '+json.dumps(briefs))
    if not isinstance(query_data,dict) or set(query_data)!=set(briefs):raise ValueError('Invalid image search plan')
    images={};credits={};seen=set();cache={}
    for key,brief in briefs.items():
        queries=query_data[key]
        if not isinstance(queries,list) or len(queries)!=2:raise ValueError('Image search plan needs two queries')
        selected=False
        for query in queries:
            if query not in cache:cache[query]=candidates(query)
            attempts=0
            for info in cache[query]:
                credit=rights(info)
                if not credit or info.get('mime') not in ('image/jpeg','image/png') or min(info.get('width',0),info.get('height',0))<1000:continue
                source=info.get('thumburl') or info['url']
                if source in seen:continue
                raw,_,_=download(source,{'upload.wikimedia.org'},12_000_000)
                # Decode before review, bound dimensions and normalize orientation.
                with Image.open(io.BytesIO(raw)) as im:
                    if im.width*im.height>36_000_000 or min(im.size)<800:continue
                    normalized=ImageOps.exif_transpose(im).convert('RGB');normalized.thumbnail((1600,1600))
                    path=Path(folder)/(key+'-art.jpg');normalized.save(path,quality=91)
                fingerprint=sha(path.read_bytes())
                if key=='cover' and fingerprint in previous_covers:continue
                review_path=Path(folder)/'image-review.png';normalized.save(review_path)
                verdict=client.json('Valuta la foto per una rivista tecnologica moderna e curata. Deve essere pertinente al brief, nitida, visivamente ricca e utilizzabile come illustrazione; respingi immagini datate fuori contesto, loghi, schermate poco leggibili, diagrammi illeggibili, foto brutte o soggetti non pertinenti. Non deve sembrare una prova del prodotto/evento trattato. Restituisci {"passed":boolean,"issues":[string]}. Brief: '+brief,images=[review_path])
                attempts+=1
                if verdict.get('passed') is not True or verdict.get('issues')!=[]:
                    if attempts>=2:break
                    continue
                credit.update(image_sha256=fingerprint,download_url=source,changes='Ritaglio editoriale e ridimensionamento',kind='licensed')
                images[key]=path;credits[key]=credit;seen.add(source);selected=True;break
            if selected:break
        if not selected:raise ValueError('No suitable licensed image for '+key)
    return images,credits
