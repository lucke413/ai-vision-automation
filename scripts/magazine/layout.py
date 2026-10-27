"""A4 magazine grid derived from the approved Computer Idea / Idea Web pilot."""
from __future__ import annotations
from html import escape
from pathlib import Path
import fitz
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.utils import ImageReader

W,H=595.276,841.89
NAVY='#082C4B';RED='#E52528';BLUE='#009DCB';YELLOW='#FFE326';INK='#152939';GRAY='#E9F0F3'
class Layout:
    def __init__(self,out,issue,period,art):
        for name,file in [('Body','DejaVuSans.ttf'),('Bold','DejaVuSans-Bold.ttf')]:
            pdfmetrics.registerFont(TTFont(name,'/usr/share/fonts/truetype/dejavu/'+file))
        self.c=canvas.Canvas(str(out),pagesize=(W,H),pageCompression=1)
        self.c.setTitle(f'AIVision Magazine | {issue} | {period}')
        self.c.setAuthor('AIVision');self.c.setSubject('Tecnologia e IA: notizie, approfondimenti e guide pratiche')
        self.c.setKeywords('AIVision, tecnologia, IA, magazine');self.c._doc.Catalog.Lang='it-IT'
        self.issue=issue;self.period=period;self.art=art;self.regions=[]
    def rect(self,x,y,w,h,color):
        self.c.setFillColor(HexColor(color));self.c.rect(x,H-y-h,w,h,fill=1,stroke=0)
    def text(self,s,x,y,w,h,size=9,color=INK,bold=False,markup=False,fit=False,min_size=None):
        # Preserve strict overflow checking by default. Selected variable-length editorial
        # excerpts may shrink gently to fit their assigned box rather than aborting the issue.
        font_size=float(size)
        floor=float(min_size if min_size is not None else max(5.5,font_size*0.82))
        while True:
            style=ParagraphStyle('p',fontName='Bold' if bold else 'Body',fontSize=font_size,
                                 leading=font_size*(1.05 if bold and font_size>=16 else 1.31),
                                 textColor=HexColor(color))
            p=Paragraph(s if markup else escape(s),style);_,height=p.wrap(w,h)
            if height<=h+.01:break
            if not fit or font_size<=floor+.001:
                raise ValueError(f'Text overflow on page {self.c.getPageNumber()}: {s[:35]} ({height:.1f}>{h})')
            font_size=max(floor,font_size*0.96)
        box=fitz.Rect(x,y,x+w,y+height)
        if x<0 or y<0 or box.x1>W+.01 or box.y1>H:raise ValueError('Text outside page')
        for page,other in self.regions:
            if page==self.c.getPageNumber() and (box&other).get_area()>1:raise ValueError(f'Text collision on page {page}')
        self.regions.append((self.c.getPageNumber(),box));p.drawOn(self.c,x,H-y-height)
        return y+height
    def title(self,s,x,y,w,h,size=34,color=NAVY):
        return self.text(s.upper(),x,y,w,h,size,color,True)
    def tag(self,s,x,y,w,color=RED):
        self.rect(x,y,w,21,color);self.text(s,x+7,y+4,w-14,14,8,'#FFFFFF',True)
    def photo(self,key,x,y,w,h):
        img=ImageReader(str(self.art[key]));iw,ih=img.getSize();scale=max(w/iw,h/ih)
        self.c.saveState();p=self.c.beginPath();p.rect(x,H-y-h,w,h);self.c.clipPath(p,stroke=0,fill=0)
        self.c.drawImage(img,x+(w-iw*scale)/2,H-y-h+(h-ih*scale)/2,iw*scale,ih*scale);self.c.restoreState()
    def start(self,key,title):
        c=self.c;c.bookmarkPage(key);c.addOutlineEntry(title,key,0)
        self.rect(0,0,W,9,BLUE);self.text('AIVISION',26,22,100,18,11,NAVY,True)
        self.tag(title.upper(),310,19,259)
        self.rect(26,810,543,1,NAVY);self.text(f'AIVISION MAGAZINE / {self.issue}',26,819,320,12,7,NAVY,True)
        self.text(f'{c.getPageNumber():02}',540,812,30,25,17,RED,True)
        c.linkRect('','contents',(26,H-832,340,H-810),relative=0,thickness=0)
    def end(self):self.c.showPage()
    def sources(self,item,sources,y=780):
        for i,sid in enumerate(item['sources']):
            s=sources[sid]
            self.text(f'<link href="{escape(s["url"],quote=True)}" color="{BLUE}">Fonte {i+1}: {escape(s["title"][:70])}</link>',26,y+i*9,543,10,6.5,markup=True)

def render(data,sources,out,art,issue,period,credits=None):
    out=Path(out);out.parent.mkdir(parents=True,exist_ok=True)
    p=Layout(out,issue,period,art);c=p.c;byid={s['id']:s for s in sources}
    sections=[('contents','Sommario'),*([('news','La settimana')] if data['news'] else []),('feature','Il tema'),('guide','Passo a passo'),('original','Tecnologia da capire'),('tips','Tips & Tricks'),('qa','Domande e risorse')]
    credits=credits or {}
    if credits:sections.append(('credits','Crediti immagini'))
    pages={k:i+2 for i,(k,_) in enumerate(sections)}
    # Cover retains the approved red masthead, left teaser rail and yellow footer.
    c.bookmarkPage('cover');c.addOutlineEntry('Copertina','cover',0)
    p.rect(0,0,W,H,NAVY);p.rect(0,0,W,38,BLUE)
    p.text('GUIDE PRATICHE',14,8,200,24,16,'#FFFFFF',True)
    p.text('WEB / SOFTWARE / INTELLIGENZA ARTIFICIALE',222,13,360,18,9,'#FFFFFF',True)
    p.rect(0,38,W,134,RED);p.text('AIVISION',15,40,565,106,94,'#FFFFFF',True)
    p.text('MAGAZINE',20,144,155,24,18,YELLOW,True);p.text(f'{issue} | {period}',180,150,400,15,7.5,'#FFFFFF',True)
    p.photo('cover',132,172,463,557);p.rect(132,172,463,190,NAVY)
    p.text('IL TEMA DEL NUMERO',148,183,425,17,10,YELLOW,True)
    p.title(data['cover_title'],146,211,431,144,32,'#FFFFFF')
    p.rect(0,172,132,557,'#FFFFFF');p.tag('DENTRO IL NUMERO',7,181,118)
    p.title('PASSO A PASSO',10,215,112,102,24)
    p.text(data['guide']['title'],10,328,110,112,12,NAVY,True)
    p.rect(10,450,111,24,YELLOW);p.text(f'LA GUIDA / {pages["guide"]}',15,455,101,17,9,RED,True)
    p.title('IDEE DA PROVARE',10,497,110,100,19)
    p.text('Cinque consigli pratici e le risposte ai dubbi più comuni.',10,621,110,90,10)
    p.rect(146,594,429,112,NAVY);p.text(data['cover_deck'],159,608,402,90,14,'#FFFFFF',True)
    p.rect(0,729,W,87,YELLOW);p.title('TECNOLOGIA DA USARE',13,739,569,45,31)
    p.text('NOTIZIE / APPROFONDIMENTI ORIGINALI / GUIDE / RISORSE',15,788,565,20,10,NAVY,True)
    p.text('aivision.altervista.org',13,824,290,12,8,'#FFFFFF',True)
    p.text('Immagine illustrativa: crediti nel numero' if credits else 'Copertina: illustrazione generata con IA',329,824,253,12,7,'#FFFFFF');p.end()
    # Photo-led contents with editorial rail and clickable navigation.
    p.start('contents','Sommario');p.title('DENTRO LE IDEE',26,58,543,59,42)
    p.rect(26,121,543,25,YELLOW);p.text('IL TUO SETTIMANALE DI TECNOLOGIA E INTELLIGENZA ARTIFICIALE',34,128,527,16,8.5,NAVY,True)
    p.photo('feature',26,160,354,200);p.tag(f'{pages["feature"]:02} / IL TEMA',26,339,354,NAVY)
    p.text(data['feature']['title'],26,375,354,55,18,NAVY,True)
    p.photo('original',26,448,168,115);p.photo('guide',212,448,168,115)
    p.tag(f'{pages["original"]:02} / APPROFONDIMENTO',26,563,168);p.tag(f'{pages["guide"]:02} / LA GUIDA',212,563,168,BLUE)
    p.text(data['original']['title'],26,597,168,75,12,NAVY,True);p.text(data['guide']['title'],212,597,168,75,12,NAVY,True)
    p.rect(399,160,170,514,GRAY);p.tag('L’EDITORIALE',408,170,152,NAVY);p.text(data['editorial'],411,211,146,445,9.4)
    for x,y,w,h,key in [(26,160,354,270,'feature'),(26,448,168,224,'original'),(212,448,168,224,'guide')]:
        c.linkRect('',key,(x,H-y-h,x+w,H-y),relative=0,thickness=0)
    y=695
    for key,label in sections[1:]:
        p.text(f'{pages[key]:02} / {label}',26+(0 if y<750 else 280),y if y<750 else y-55,260,16,9,NAVY,True)
        c.linkRect('',key,(26+(0 if y<750 else 280),H-(y if y<750 else y-55)-16,286+(0 if y<750 else 280),H-(y if y<750 else y-55)),relative=0,thickness=0)
        y+=18
    p.text('Immagini illustrative: fonti, autori e licenze nei crediti. Domande a cura della redazione.' if credits else 'Illustrazioni generate con IA: rappresentazioni editoriali, non schermate reali o fotografie di prodotti. Domande a cura della redazione.',26,782,543,23,7);p.end()
    if data['news']:
        p.start('news','La settimana');p.title('LE NOTIZIE DA CAPIRE',26,58,543,56,32)
        p.text('Articoli AIVision del periodo. Immagini illustrative, crediti nel numero. Link alla lettura completa.',26,116,543,33,10)
        for i,n in enumerate(data['news']):
            key=f'news{i}' if f'news{i}' in art else ('feature' if i%2==0 else 'original')
            s=byid[n['sources'][0]]
            if len(data['news'])==1:
                p.photo(key,26,166,543,332)
                p.text(n['title'],26,518,543,75,24,NAVY,True)
                p.text(n['body'],26,612,543,137,12,fit=True,min_size=9)
                p.text(f'<link href="{escape(s["url"],quote=True)}" color="{BLUE}">Leggi l’articolo completo →</link>',26,770,543,15,9,markup=True)
            elif len(data['news'])==2 or (len(data['news'])==3 and i==2):
                y=174+(1 if i==2 else i)*300;p.photo(key,26,y,205,244)
                p.text(n['title'],250,y,319,75,19,NAVY,True)
                p.text(n['body'],250,y+90,319,141,10,fit=True,min_size=8)
                p.text(f'<link href="{escape(s["url"],quote=True)}" color="{BLUE}">Leggi l’articolo completo →</link>',250,y+246,319,13,8,markup=True)
            else:
                x=26+(i%2)*280;y=166+(i//2)*313
                p.photo(key,x,y,263,90)
                p.text(n['title'],x,y+102,263,53,13,NAVY,True)
                p.text(n['body'],x,y+163,263,131,8.6,fit=True,min_size=7)
                p.text(f'<link href="{escape(s["url"],quote=True)}" color="{BLUE}">Leggi l’articolo completo →</link>',x,y+298,263,12,7,markup=True)
        p.end()
    for key,label in [('feature','Il tema'),('guide','Passo a passo'),('original','Tecnologia da capire')]:
        item=data[key];p.start(key,label)
        if key=='guide':
            size=min(30,543/pdfmetrics.stringWidth(item['title'].upper(),'Bold',1))
            p.title(item['title'],26,58,543,44,size);p.text(item['deck'],26,111,543,39,10)
        else:
            p.title(item['title'],26,58,543,89,30);p.text(item['deck'],26,151,543,44,10.5)
        if key!='guide':
            p.photo(key,26,206,543,228)
            p.text('Immagine illustrativa; fonti e licenze nei crediti, non una prova del prodotto citato.' if credits else 'Illustrazione editoriale generata con IA; non rappresenta una prova o una schermata reale.',26,440,543,18,7)
            for i,col in enumerate(item['columns']):
                x=26+i*186;p.text(col['title'].upper(),x,471,171,40,11,RED,True)
                p.text(col['body'],x,520,171,222,8.6,fit=True,min_size=7.2)
            p.rect(26,749,543,28,YELLOW);p.text(item['box'],34,754,527,22,7.8)
        else:
            p.rect(18,159,559,610,BLUE);p.rect(25,166,545,596,'#FFFFFF')
            for i,step in enumerate(item['steps']):
                x=38+(i%2)*270;y=177+(i//2)*192
                p.text(str(i+1),x,y,27,37,27,RED,True);p.text(step['title'],x+33,y+5,211,33,11,NAVY,True)
                p.photo(f'step{i}' if f'step{i}' in art else 'guide',x,y+43,244,76)
                p.text(step['body'],x,y+128,244,57,8.2)
            p.text('Illustrazione concettuale: i numeri indicano l’ordine dei passaggi, non comandi sullo schermo.',33,768,530,10,6)
        p.sources(item,byid);p.end()
    p.start('tips','Tips & Tricks');p.title('5 IDEE DA METTERE IN PRATICA',26,58,543,90,30)
    p.photo('tips',26,158,543,185);p.text('Immagine illustrativa: fonte e licenza nei crediti.' if credits else 'Illustrazione editoriale generata con IA.',26,350,543,15,7)
    for i,item in enumerate(data['tips']['items']):
        y=384+i*76;p.text(str(i+1),26,y,34,40,28,RED,True)
        p.text(item['title'],70,y,499,24,12,NAVY,True);p.text(item['body'],70,y+26,499,44,9)
    p.sources(data['tips'],byid);p.end()
    p.start('qa','Domande e risorse');p.title('RISPONDE LA REDAZIONE',26,58,543,90,31)
    p.tag('DOMANDE REDAZIONALI / NESSUN LETTORE INVENTATO',26,150,543,BLUE)
    for i,item in enumerate(data['qa']['items']):
        y=195+i*140;p.rect(26,y,5,123,YELLOW)
        p.text(item['title'],43,y,526,44,14,NAVY,True);p.text(item['body'],43,y+50,526,78,9.4)
    p.tag('TUTTE LE FONTI DEL NUMERO',26,630,543,NAVY)
    used=list(dict.fromkeys(sid for item in [*data['news'],*[data[k] for k in ('feature','guide','original','tips','qa')]] for sid in item['sources']))
    for i,sid in enumerate(used):
        s=byid[sid];p.text(f'<link href="{escape(s["url"],quote=True)}" color="{BLUE}">{escape(s["title"][:65])}</link>',26+(i%2)*280,665+(i//2)*23,263,22,7,markup=True)
    p.end()
    if credits:
        p.start('credits','Crediti immagini');p.title('LE IMMAGINI DEL NUMERO',26,58,543,80,30)
        p.text('Fotografie e illustrazioni usate a scopo editoriale. Ritaglio e ridimensionamento per la pagina. Le immagini non attestano prove o eventi descritti negli articoli.',26,143,543,44,9)
        if len(credits)>9:raise ValueError('Too many image credits for the page')
        labels={'cover':'Copertina','feature':'Il tema','guide':'Passo a passo','original':'Approfondimento','tips':'Tips & Tricks'}
        for i,(key,credit) in enumerate(credits.items()):
            x=26+(i%3)*186;y=208+(i//3)*190
            p.photo(key,x,y,171,55)
            p.text(labels.get(key,'Notizia '+key.removeprefix('news')),x,y+63,171,16,9,NAVY,True)
            p.text(credit['title'],x,y+84,171,36,7)
            p.text(credit['artist'],x,y+124,171,36,6.8)
            p.text(f'<link href="{escape(credit["source"],quote=True)}" color="{BLUE}">Fonte originale</link> · <link href="{escape(credit["license_url"],quote=True)}" color="{BLUE}">{escape(credit["license"])}</link>',x,y+164,171,24,6.8,markup=True)
        p.end()
    c.save()
    return check_pdf(out,len(sections)+1)

def check_pdf(path,expected):
    path=Path(path)
    if not 100_000<=path.stat().st_size<=18_000_000:raise ValueError('PDF size outside bounds')
    with fitz.open(path) as doc:
        if len(doc)!=expected:raise ValueError('Incorrect PDF page count')
        total_links=0
        for i,page in enumerate(doc):
            if abs(page.rect.width-W)>1 or abs(page.rect.height-H)>1:raise ValueError('Not A4')
            if len(page.get_text())<180:raise ValueError('Empty PDF page')
            for b in page.get_text('blocks'):
                if not page.rect.contains(fitz.Rect(b[:4])):raise ValueError('Clipped PDF text')
            links=page.get_links();total_links+=len(links)
            for link in links:
                if link['kind']==fitz.LINK_GOTO and not 0<=link['page']<len(doc):raise ValueError('Broken PDF navigation')
            if i and f'{i+1:02}' not in page.get_text():raise ValueError('Missing page number')
            page.get_pixmap(matrix=fitz.Matrix(1.35,1.35)).save(path.parent/f'page-{i+1:02}.png')
        if total_links<10 or len(doc.get_toc())!=expected:raise ValueError('Missing PDF links or outlines')
        return {'pages':len(doc),'links':total_links,'size_bytes':path.stat().st_size,'geometry_passed':True}
