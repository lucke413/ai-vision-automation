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
    def test_evidence_repair_preserves_articles_and_rechecks_literal_source(self):
        from scripts.magazine.content import repair_evidence,source_excerpts
        data,sources=fixture();expected=copy.deepcopy(data)
        data['original']['evidence'][0]['quote']='An invented translation of the original source passage.'
        expected['original']['evidence']=[{'source':'firefox','quote':source_excerpts(sources[1]['text'])['e0']}]
        client=Mock();client.json.return_value={'firefox':'e0'}
        self.assertEqual(repair_evidence(client,data,sources),expected)
        self.assertEqual(client.json.call_count,1);validate(data,sources)
    def test_invented_evidence_cannot_pass_repair(self):
        from scripts.magazine.content import repair_evidence
        data,sources=fixture();data['original']['evidence'][0]['quote']='An invented translation of the original source passage.'
        client=Mock();client.json.return_value={'firefox':'invented-id'}
        repair_evidence(client,data,sources)
        self.assertEqual(client.json.call_count,2)
        with self.assertRaises(ValueError):validate(data,sources)
    def test_excerpt_windows_are_verbatim_and_bounded(self):
        from scripts.magazine.content import source_excerpts
        text=('Prima frase italiana con dettagli verificabili.\n' * 70)+'Fine del documento con informazioni utili.'
        normalized=' '.join(text.split());choices=source_excerpts(text)
        self.assertGreater(len(choices),5)
        for value in choices.values():
            self.assertTrue(25<=len(value)<=240);self.assertIn(value,normalized)
        self.assertTrue(list(choices.values())[-1].endswith('informazioni utili.'))
    def test_length_repair_changes_only_invalid_fields(self):
        from scripts.magazine.content import repair_lengths
        data,sources=fixture();expected=copy.deepcopy(data)
        data['guide']['steps'][2]['body']='Testo troppo breve.'
        data['news'][0]['title']='Un titolo decisamente troppo lungo '*4
        client=Mock();client.json.side_effect=[{'text0':expected['news'][0]['title']},{'text1':expected['guide']['steps'][2]['body'].split()}]
        self.assertEqual(repair_lengths(client,data,sources),expected)
        self.assertEqual(client.json.call_count,2)
        for call in client.json.call_args_list:
            self.assertEqual(len(call.kwargs['schema']['properties']),1)
        validate(data,sources)
    def test_bad_length_repair_is_bounded_and_still_rejected(self):
        from scripts.magazine.content import repair_lengths
        data,sources=fixture();data['editorial']='Troppo breve.'
        client=Mock();client.json.return_value={'text0':['Ancora','breve.']}
        repair_lengths(client,data,sources)
        self.assertEqual(client.json.call_count,2)
        with self.assertRaises(ValueError):validate(data,sources)
    def test_counted_repair_recovers_one_word_short_qa(self):
        from scripts.magazine.content import repair_lengths
        data,sources=fixture();expected=copy.deepcopy(data)
        data['qa']['items'][0]['body']=' '.join(expected['qa']['items'][0]['body'].split()[:54])
        client=Mock();client.json.return_value={'text0':expected['qa']['items'][0]['body'].split()}
        self.assertEqual(repair_lengths(client,data,sources),expected)
        schema=client.json.call_args.kwargs['schema']['properties']['text0']
        self.assertEqual((schema['minItems'],schema['maxItems']),(55,70))
        validate(data,sources)
    def test_counted_repair_rejects_embedded_spaces(self):
        from scripts.magazine.content import repair_lengths
        data,sources=fixture();data['editorial']='Breve.'
        client=Mock();client.json.return_value={'text0':['two words']*95}
        with self.assertRaisesRegex(ValueError,'tokens'):repair_lengths(client,data,sources)
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
    def test_feed_identity_fills_only_empty_fields_and_saves_backup(self):
        self.wp.api=Mock(side_effect=[{'title':'','description':'Existing description'}, {}, {'title':'AIVision','description':'Existing description'}])
        self.wp.repair_feed_identity()
        self.assertEqual(self.wp.api.call_args_list[1].kwargs['json'],{'title':'AIVision'})
        self.assertEqual(self.j.data['rss_identity_backup'],{'title':''})
        self.j.save.assert_called_once()
    def test_feed_identity_preserves_existing_brand(self):
        self.wp.api=Mock(return_value={'title':'My brand','description':'My description'})
        self.wp.repair_feed_identity()
        self.assertEqual(self.wp.api.call_count,1)
        self.j.save.assert_not_called()
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

class ImageRightsTests(unittest.TestCase):
    def test_exact_license_and_deed_url_normalization(self):
        from scripts.magazine.images import rights
        def meta(license,url):
            return {'descriptionurl':'https://commons.wikimedia.org/wiki/File:Photo.jpg','extmetadata':{k:{'value':v} for k,v in {'ObjectName':'Modern desk','Artist':'Author','LicenseShortName':license,'LicenseUrl':url,'Copyrighted':'True','Restrictions':''}.items()}}
        self.assertEqual(rights(meta('CC0','http://creativecommons.org/publicdomain/zero/1.0/deed.en'))['license'],'CC0')
        self.assertIsNotNone(rights(meta('CC BY 4.0','https://creativecommons.org/licenses/by/4.0/')))
        self.assertIsNone(rights(meta('CC BY-NC 4.0','https://creativecommons.org/licenses/by-nc/4.0/')))
        self.assertIsNone(rights(meta('CC BY 4.0','https://evil.test/by/4.0/')))

@unittest.skipUnless(importlib.util.find_spec('fitz') and importlib.util.find_spec('reportlab'),'Dedicated magazine dependencies required')
class ExtendedLayoutTests(unittest.TestCase):
    def test_two_three_four_news_and_credits(self):
        from scripts.magazine.layout import render
        d,s=fixture();root=Path(__file__).resolve().parents[1]/'magazine/art'
        art={k:root/'creative.jpg' for k in d['art']}
        for count in (2,3,4):
            data=copy.deepcopy(d);data['news']=[copy.deepcopy(d['news'][0]) for _ in range(count)]
            with tempfile.TemporaryDirectory() as tmp:
                self.assertEqual(render(data,s,Path(tmp)/'test.pdf',art,'COLLAUDO','18–25 ottobre')['pages'],8)
        credits={k:{'artist':'Nome autore','title':'Titolo originale della fotografia','source':'https://commons.wikimedia.org/wiki/File:Photo.jpg','license':'CC BY 4.0','license_url':'https://creativecommons.org/licenses/by/4.0/'} for k in art}
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(render(d,s,Path(tmp)/'test.pdf',art,'COLLAUDO','18–25 ottobre',credits)['pages'],9)
    def test_preview_bundle_never_publishes(self):
        from scripts.magazine.run import verify_bundle
        import json
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp,'manifest.json').write_text(json.dumps({'issue':'2026-10-25','ready_to_publish':False}))
            with self.assertRaises(ValueError):verify_bundle(tmp)

class StructuredOutputTests(unittest.TestCase):
    def test_transient_provider_retry_and_quota_fail_closed(self):
        from scripts.magazine.content import Gemini
        client=Gemini.__new__(Gemini);client.key='test';client.model='test-model';client.last_request=0
        busy=Mock(status_code=503);ok=Mock(status_code=200)
        ok.json.return_value={'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':'{}'}]}}]}
        with patch('scripts.magazine.content.requests.post',side_effect=[busy,ok]) as post,patch('scripts.magazine.content.time.sleep'):
            self.assertEqual(client.call([{'text':'test'}]),[{'text':'{}'}]);self.assertEqual(post.call_count,2)
        with patch('scripts.magazine.content.requests.post',return_value=busy) as post,patch('scripts.magazine.content.time.sleep'):
            with self.assertRaises(RuntimeError):client.call([{'text':'test'}])
            self.assertEqual(post.call_count,3)
        with patch('scripts.magazine.content.requests.post',return_value=Mock(status_code=429)) as post,patch('scripts.magazine.content.time.sleep'):
            with self.assertRaises(RuntimeError):client.call([{'text':'test'}])
            self.assertEqual(post.call_count,1)
    def test_provider_schema_and_malformed_retry(self):
        from scripts.magazine.content import Gemini,output_schema,SCHEMA
        client=Gemini.__new__(Gemini)
        client.call=Mock(side_effect=[[{'text':'{"partial":'}],[{'text':'{"cover_title":"Complete"}'}]])
        schema=output_schema(SCHEMA)
        result=client.json('Generate',schema=schema)
        self.assertEqual(result['cover_title'],'Complete')
        self.assertEqual(client.call.call_count,2)
        sent=client.call.call_args.kwargs['config']['responseFormat']['text']
        self.assertEqual(sent['mimeType'],'APPLICATION_JSON');self.assertIn('guide',sent['schema']['required'])
    def test_invalid_json_still_fails_closed(self):
        from scripts.magazine.content import Gemini
        client=Gemini.__new__(Gemini);client.call=Mock(return_value=[{'text':'invalid'}])
        with self.assertRaises(ValueError):client.json('Generate')
        self.assertEqual(client.call.call_count,2)
