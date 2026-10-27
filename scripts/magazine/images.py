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
    try:
        safe_url(source,{'commons.wikimedia.org','commons.m.wikimedia.org'})
    except (ValueError,TypeError):
        # One malformed/untrusted Commons record must not abort the entire issue.
        return None
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

def _original_artwork(folder,key,brief):
    """Create a distinct, locally generated abstract illustration if Commons has no usable image.

    This is deliberately illustrative rather than a fake photograph or purported evidence
    of a product/event. It keeps publication resilient without relaxing image-license checks.
    """
    from PIL import ImageDraw
    import hashlib
    width,height=1600,1200
    digest=hashlib.sha256((key+' '+brief).encode('utf-8')).digest()
    accents=[(91,190,255),(155,112,255),(60,220,190),(255,170,80),(255,105,145)]
    accent=accents[digest[0]%len(accents)]
    image=Image.new('RGB',(width,height))
    pixels=image.load()
    for y in range(height):
        for x in range(width):
            glow=max(0,1-(((x-(800+digest[1]*2))/950)**2+((y-(250+digest[2]*2))/780)**2)**0.5)
            pixels[x,y]=(int(5+18*glow),int(15+25*glow),int(38+80*glow))
    draw=ImageDraw.Draw(image,'RGBA')
    # A distinct geometric editorial motif; no text, logo, UI screenshot or external asset.
    cx=780+(digest[3]-128)*2
    cy=510+(digest[4]-128)
    for i in range(6):
        inset=i*52
        draw.ellipse((cx-120-inset,cy-120-inset,cx+120+inset,cy+120+inset),
                     outline=(*accent,max(28,125-i*14)),width=5)
    for i in range(12):
        x=100+i*125
        draw.line((x,100,x+((digest[i+5]-128)*2),height-100),
                  fill=(*accent,28+i*3),width=3 if i%3==0 else 1)
    for i in range(9):
        x=150+(i*173+digest[10])%1300
        y=100+(i*97+digest[11])%1000
        radius=8+(digest[(i+12)%len(digest)]%24)
        draw.ellipse((x-radius,y-radius,x+radius,y+radius),fill=(*accent,150))
    path=Path(folder)/(key+'-original-art.jpg')
    image.save(path,quality=92)
    return path

def free_images(client,briefs,folder,previous_covers=()):
    """Fail closed if rights, relevance or visual quality cannot be established."""
    schema={'type':'object','properties':{k:{'type':'array','items':{'type':'string'},'minItems':2,'maxItems':2} for k in briefs},'required':list(briefs)}
    query_data=client.json('Converti ogni brief in 2 ricerche fotografiche inglesi per Wikimedia Commons, 2-5 parole ciascuna. Soggetti concreti, attuali, pertinenti, non loghi o schermate. Evita concetti astratti impossibili da trovare. Restituisci JSON {chiave:[ricerca1,ricerca2]} con esattamente le chiavi in input. INPUT '+json.dumps(briefs),schema=schema)
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
                try:
                    raw,_,_=download(source,{'upload.wikimedia.org'},12_000_000)
                    # Decode before review, bound dimensions and normalize orientation.
                    with Image.open(io.BytesIO(raw)) as im:
                        if im.width*im.height>36_000_000 or min(im.size)<800:continue
                        normalized=ImageOps.exif_transpose(im).convert('RGB');normalized.thumbnail((1600,1600))
                        path=Path(folder)/(key+'-art.jpg');normalized.save(path,quality=91)
                except (ValueError,TypeError,KeyError,OSError,requests.RequestException):
                    # Skip this individual candidate (including untrusted redirect origins)
                    # and continue with other openly licensed Commons images.
                    continue
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
        if not selected:
            # Commons is optional: retain strict license validation for sourced photos, but
            # use clearly credited original artwork instead of aborting the entire issue.
            path=_original_artwork(folder,key,brief)
            images[key]=path
            credits[key]={'kind':'original_artwork','artist':'AIVision','license':'Original artwork created for this issue','license_url':'','source':'','title':f'Original abstract illustration: {key}','changes':'Generated locally; no third-party image used'}
            selected=True
    return images,credits
