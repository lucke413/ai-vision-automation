import copy
import importlib.util
import tempfile
import unittest
from datetime import datetime,timezone
from pathlib import Path
from unittest.mock import Mock,patch
from scripts.magazine.content import week,select,safe_url,validate,sha,download
from scripts.magazine.wordpress import WordPress,extend_widget,SOCIALS,START,newsletter_url

def fixture():
    """Synthetic offline layout fixture, never eligible for live publication."""
    sentence='Questa pagina serve al collaudo della griglia editoriale e contiene testo dimostrativo per verificare la leggibilità delle colonne.'
    def words(n):return ' '.join((sentence.split()*20)[:n])+'.'
    source={'id':'wp-1','kind':'weekly','title':'Fonte dimostrativa','url':'https://aivision.altervista.org/test/','text':sentence*8}
    primary={**source,'id':'firefox','kind':'primary','url':'https://support.mozilla.org/it/kb/Stampare%20una%20pagina%20web'}
    def evidence(sid):return {'sources':[sid],'evidence':[{'source':sid,'quote':sentence[:80]}]}
    feature={'title':'Una locandina che si fa leggere','deck':'Immagini, gerarchie e piccoli controlli per passare da una prima idea al progetto finito.',
      'columns':[{'title':s,'body':words(95)} for s in ('Parti dal messaggio','Scegli una buona immagine','Controlla il risultato')],
      'box':'Prima il messaggio, poi la grafica: un titolo chiaro orienta tutta la composizione.',**evidence('firefox')}
    data={'cover_title':'Le tue idee prendono forma','cover_deck':'Un progetto creativo in sei passaggi, consigli pratici e risposte ai dubbi più comuni. Numero di collaudo, non destinato alla pubblicazione.',
      'editorial':words(95),'news':[{'title':'Una notizia per provare la griglia','body':words(85),**evidence('wp-1')}],
      'feature':feature,'original':{**copy.deepcopy(feature),'title':'Una risposta non è una prova'},
      'guide':{'title':'Dalla bozza al manifesto','deck':'Sei passaggi illustrati: una prova della composizione editoriale e dello spazio disponibile.',
        'steps':[{'title':s,'body':words(30)} for s in ('Scrivi il brief','Scegli il soggetto','Riserva lo spazio','Dai ordine al testo','Controlla i dettagli','Esporta il risultato')],**evidence('firefox')},
      'tips':{'items':[{'title':'Un consiglio da provare','body':words(42)} for _ in range(5)],**evidence('firefox')},
      'qa':{'items':[{'title':'Come si controlla la leggibilità della pagina?','body':words(58)} for _ in range(3)],**evidence('firefox')},
      'art':{k:'Editorial image for layout testing, with a detailed modern desk composition and blue orange lighting.' for k in ('cover','feature','guide','original','tips')}}
    return data,[source,primary]

class SelectionTests(unittest.TestCase):
    def test_dst_boundaries_and_sunday_before_nine(self):
        start,end=week(datetime(2026,10,25,9,tzinfo=timezone.utc))
        self.assertEqual(start.hour,9);self.assertEqual(end.hour,9)
        self.assertEqual((end.astimezone(timezone.utc)-start.astimezone(timezone.utc)).total_seconds()/3600,169)
        s,e=week(datetime(2026,3,29,8,tzinfo=timezone.utc))
        self.assertEqual((e.astimezone(timezone.utc)-s.astimezone(timezone.utc)).total_seconds()/3600,167)
        self.assertEqual(week(datetime(2026,10,25,7,tzinfo=timezone.utc))[1].day,18)
    def test_half_open_dates_promotion_terms_and_duplicates(self):
        start,end=week(datetime(2026,10,26,tzinfo=timezone.utc))
        p={'id':1,'status':'publish','date_gmt':'2026-10-20T10:00:00','title':{'rendered':'Software utile'},'content':{'rendered':'Un approfondimento documentato. '*50},'link':'https://aivision.altervista.org/software/','slug':'software'}
        offer=copy.deepcopy(p);offer.update(id=2,link='https://aivision.altervista.org/offerta/');offer['title']['rendered']='Coupon speciale'
        edge=copy.deepcopy(p);edge.update(id=3,date_gmt=end.astimezone(timezone.utc).replace(tzinfo=None).isoformat())
        self.assertEqual(len(select([p,copy.deepcopy(p),offer,edge],start,end)),1)
    def test_credentials_and_foreign_origins_rejected(self):
        for url in ('http://aivision.altervista.org/x','https://evil.test/x','https://user:pw@aivision.altervista.org/x','https://aivision.altervista.org:444/x'):
            with self.assertRaises(ValueError):safe_url(url,{'aivision.altervista.org'})
    def test_redirect_cannot_escape_allowlist(self):
        response=Mock();response.__enter__=Mock(return_value=response);response.__exit__=Mock(return_value=False)
        response.is_redirect=True;response.headers={'Location':'http://127.0.0.1/secret'}
        with patch('scripts.magazine.content.requests.get',return_value=response) as get:
            with self.assertRaises(ValueError):download('https://support.mozilla.org/ok',{'support.mozilla.org'})
            self.assertEqual(get.call_count,1)

class EditorialTests(unittest.TestCase):
    def test_contract_and_fabricated_evidence(self):
        data,sources=fixture();validate(data,sources)
        data['original']['evidence'][0]['quote']='This is an invented passage that does not exist in the source.'
        with self.assertRaises(ValueError):validate(data,sources)
    def test_missing_sections_duplicates_and_promotions(self):
        for mutate in (lambda d:d['guide']['steps'].pop(),lambda d:d['news'].append(d['news'][0]),lambda d:d.update(cover_title='Coupon esclusivo per tutti')):
            d,s=fixture();mutate(d)
            with self.assertRaises(ValueError):validate(d,s)

class PublicationTests(unittest.TestCase):
    def setUp(self):
        self.j=Mock();self.j.data={'operations':{}}
        self.wp=WordPress.__new__(WordPress);self.wp.journal=self.j
    def test_pending_precedes_create_and_timeout_never_retries(self):
        def fail():
            self.assertEqual(self.j.data['operations']['x']['status'],'pending')
            raise TimeoutError()
        with self.assertRaises(TimeoutError):self.wp.once('x',lambda:None,fail)
        create=Mock()
        with self.assertRaises(RuntimeError):self.wp.once('x',lambda:None,create)
        create.assert_not_called()
    def test_reconcile_after_remote_success_without_local_response(self):
        self.j.data['operations']['x']={'status':'pending'}
        create=Mock();result=self.wp.once('x',lambda:{'id':4},create)
        self.assertEqual(result['id'],4);create.assert_not_called()
    def test_widget_preserves_socials_and_updates_same_block(self):
        old='<style>.aiv-social-box{color:white}</style><div class="aiv-social-box">'+''.join(f'<a href="{s}">Social</a>' for s in SOCIALS)+'</div>'
        new=extend_widget(old,'https://aivision.altervista.org/aivision-magazine-2026-10-25/')
        self.assertEqual(new.count(START),1)
        self.assertEqual(extend_widget(new,'https://aivision.altervista.org/aivision-magazine-2026-10-25/'),new)
        for s in SOCIALS:self.assertIn(s,new)
        self.assertIn('/feed/',new)
        with self.assertRaises(ValueError):extend_widget('<div>Another widget</div>')
    def test_newsletter_disabled_until_doi_verified(self):
        with patch.dict('os.environ',{'NEWSLETTER_FORM_URL':'https://example.sibforms.com/serve/x','NEWSLETTER_DOI_VERIFIED':'false'}):
            with self.assertRaises(ValueError):newsletter_url()

@unittest.skipUnless(importlib.util.find_spec('fitz') and importlib.util.find_spec('reportlab'),'Dedicated magazine dependencies required')
class LayoutTests(unittest.TestCase):
    def test_complete_pdf_links_images_and_overflow(self):
        from scripts.magazine.layout import render,Layout
        d,s=fixture();root=Path(__file__).resolve().parents[1]/'magazine/art'
        art={k:root/v for k,v in {'cover':'cover.jpg','feature':'creative.jpg','guide':'creative.jpg','original':'factcheck.jpg','tips':'archive.jpg'}.items()}
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'test.pdf';report=render(d,s,out,art,'COLLAUDO','18/10/2026 – 25/10/2026')
            self.assertEqual(report['pages'],8);self.assertGreaterEqual(report['links'],15)
            self.assertEqual(len(list(Path(tmp).glob('page-*.png'))),8)
            p=Layout(Path(tmp)/'bad.pdf','test','test',art)
            with self.assertRaises(ValueError):p.text('overflow '*100,10,10,50,10)
            p.text('first',10,10,100,20)
            with self.assertRaises(ValueError):p.text('overlap',10,10,100,20)
    def test_no_weekly_news_reduces_pages(self):
        from scripts.magazine.layout import render
        d,s=fixture();d['news']=[];s=s[1:];validate(d,s)
        root=Path(__file__).resolve().parents[1]/'magazine/art'
        art={k:root/'creative.jpg' for k in d['art']}
        with tempfile.TemporaryDirectory() as tmp:self.assertEqual(render(d,s,Path(tmp)/'test.pdf',art,'COLLAUDO','18–25 ottobre')['pages'],7)

if __name__=='__main__':unittest.main()
