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

class ImageSourceFallbackTests(unittest.TestCase):
    def _commons_info(self,thumburl,descriptionurl='https://commons.wikimedia.org/wiki/File:Test_photo.jpg'):
        return {
            'descriptionurl':descriptionurl,
            'thumburl':thumburl,
            'url':'https://upload.wikimedia.org/wikipedia/commons/test.jpg',
            'mime':'image/jpeg','width':1200,'height':1200,
            'extmetadata':{
                'LicenseShortName':{'value':'CC BY 4.0'},
                'LicenseUrl':{'value':'https://creativecommons.org/licenses/by/4.0/'},
                'Restrictions':{'value':''},
                'Artist':{'value':'Test photographer'},
                'ObjectName':{'value':'Test technology photograph'},
                'Copyrighted':{'value':'true'}
            }
        }

    def test_untrusted_description_origin_is_rejected_without_crashing(self):
        from scripts.magazine.images import rights
        info=self._commons_info('https://upload.wikimedia.org/test.jpg','https://evil.example/file')
        self.assertIsNone(rights(info))

    def test_missing_licensed_image_uses_original_artwork_instead_of_aborting(self):
        from scripts.magazine.images import free_images
        client=Mock()
        client.json.return_value={'feature':['unavailable photo query','second unavailable query']}
        with tempfile.TemporaryDirectory() as folder,patch('scripts.magazine.images.candidates',return_value=[]):
            images,credits=free_images(client,{'feature':'A technology feature illustration'},folder)
            self.assertTrue(images['feature'].exists())
            self.assertGreater(images['feature'].stat().st_size,1000)
            self.assertEqual(credits['feature']['kind'],'original_artwork')
            self.assertEqual(credits['feature']['artist'],'AIVision')
            self.assertFalse(credits['feature']['source'])

    def test_commons_api_rejection_falls_back_to_original_artwork(self):
        from scripts.magazine.images import free_images
        client=Mock()
        client.json.return_value={'feature':['query one','query two']}
        with tempfile.TemporaryDirectory() as folder,patch('scripts.magazine.images.candidates',side_effect=ValueError('Commons query rejected')):
            images,credits=free_images(client,{'feature':'A technology feature illustration'},folder)
            self.assertTrue(images['feature'].exists())
            self.assertGreater(images['feature'].stat().st_size,1000)
            self.assertEqual(credits['feature']['kind'],'original_artwork')
            self.assertFalse(credits['feature']['source'])

    def test_invalid_image_host_is_skipped_when_valid_candidate_exists(self):
        import io
        from PIL import Image
        from scripts.magazine.images import free_images
        bad=self._commons_info('https://evil.example/image.jpg')
        good=self._commons_info('https://upload.wikimedia.org/wikipedia/commons/thumb/test.jpg')
        buffer=io.BytesIO()
        Image.new('RGB',(1200,900),(40,100,160)).save(buffer,format='JPEG')
        image_bytes=buffer.getvalue()
        client=Mock()
        client.json.side_effect=[
            {'cover':['technology workspace','laptop desk']},
            {'passed':True,'issues':[]}
        ]
        def fake_download(url,hosts,limit):
            if 'evil.example' in url:raise ValueError('Source origin is not allowed')
            return image_bytes,'image/jpeg',url
        with tempfile.TemporaryDirectory() as folder,patch('scripts.magazine.images.candidates',return_value=[bad,good]),patch('scripts.magazine.images.download',side_effect=fake_download):
            images,credits=free_images(client,{'cover':'Laptop and technology workspace'},folder)
            self.assertTrue(images['cover'].exists())
            self.assertEqual(credits['cover']['source'],'https://commons.wikimedia.org/wiki/File:Test_photo.jpg')
            self.assertEqual(credits['cover']['kind'],'licensed')

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
    def test_missing_weekly_news_is_filled_from_unused_real_source(self):
        from scripts.magazine.content import repair_news_count
        data,sources=fixture()
        source_template=next(s for s in sources if s['id']=='wp-1')
        for sid,title in (('wp-2','Second weekly source'),('wp-3','Third weekly source'),('wp-4','Fourth weekly source')):
            sources.append({**source_template,'id':sid,'title':title,'url':f'https://aivision.altervista.org/{sid}/',
                            'text':source_template['text']+' '+title+'.'})
        body=data['news'][0]['body']
        data['news'].extend([
            {'title':'Second existing news','body':body,'sources':['wp-2'],'evidence':[]},
            {'title':'Third existing news','body':body,'sources':['wp-3'],'evidence':[]}
        ])
        client=Mock()
        client.json.return_value={'title':'Moulinex: una superficie di cottura diversa',
                                  'body':body}
        repair_news_count(client,data,sources)
        self.assertEqual(len(data['news']),4)
        self.assertEqual([item['sources'][0] for item in data['news']],['wp-1','wp-2','wp-3','wp-4'])
        self.assertEqual(data['news'][3]['title'],'Moulinex: una superficie di cottura diversa')
        self.assertEqual(client.json.call_count,1)
        prompt=client.json.call_args.args[0]
        self.assertIn('wp-4',prompt)
        self.assertIn('Fourth weekly source',prompt)

    def test_missing_weekly_news_fails_closed_if_no_usable_source_remains(self):
        from scripts.magazine.content import repair_news_count
        data,sources=fixture()
        for sid in ('wp-2','wp-3'):
            sources.append({'id':sid,'kind':'weekly','title':sid,'url':f'https://aivision.altervista.org/{sid}/','text':''})
        client=Mock()
        with self.assertRaisesRegex(ValueError,'Not enough unused weekly sources'):
            repair_news_count(client,data,sources)
        client.json.assert_not_called()

    def test_targeted_editorial_repair_changes_only_flagged_guide_step(self):
        from scripts.magazine.content import repair_review_issues
        data,sources=fixture()
        data['guide']['steps'][1]['body']='Questa frase è incompleta per'
        before=copy.deepcopy(data)
        replacement='Raccogli i fatti essenziali e verifica le date, il destinatario e lo scopo della comunicazione prima di scrivere una frase completa che indichi con chiarezza cosa deve essere fatto e quando.'
        review={'passed':False,'issues':["La guida 'Dalla bozza al manifesto', nel passaggio 'Scegli il soggetto', termina con la preposizione sospesa 'per'."]}
        client=Mock();client.json.return_value={'repairs':[{'field':'guide.steps.1.body','text':replacement}]}
        repair_review_issues(client,data,sources,review)
        self.assertEqual(data['guide']['steps'][1]['body'],replacement)
        self.assertEqual(data['guide']['steps'][0],before['guide']['steps'][0])
        self.assertEqual(data['guide']['title'],before['guide']['title'])
        self.assertEqual(data['guide']['sources'],before['guide']['sources'])
        self.assertEqual(client.json.call_count,1)
        field_schema=client.json.call_args.kwargs['schema']['properties']['repairs']['items']['properties']['field']
        self.assertIn('guide.steps.1.body',field_schema['enum'])
        self.assertNotIn('guide.steps.0.body',field_schema['enum'])

    def test_unknown_source_id_remaps_only_from_unique_exact_quote(self):
        from scripts.magazine.content import repair_evidence
        data,sources=fixture()
        weekly=next(s for s in sources if s['id']=='wp-1')
        quote='Passaggio univoco: verifica le impostazioni di impaginazione e controlla la gerarchia visuale prima di esportare il progetto.'
        weekly['text']=quote+' '+weekly['text']
        data['feature']['sources']=['wp-1207']
        data['feature']['evidence']=[{'source':'wp-1207','quote':quote}]
        client=Mock()
        repair_evidence(client,data,sources)
        self.assertEqual(data['feature']['sources'],['wp-1'])
        self.assertEqual(data['feature']['evidence'],[{'source':'wp-1','quote':quote}])
        validate(data,sources)

    def test_unknown_source_id_with_unmatched_quote_stays_invalid(self):
        from scripts.magazine.content import repair_evidence
        data,sources=fixture()
        data['feature']['sources']=['wp-1207']
        data['feature']['evidence']=[{'source':'wp-1207','quote':'This invented quotation is not present in any supplied source.'}]
        repair_evidence(Mock(),data,sources)
        self.assertEqual(data['feature']['sources'],[])
        self.assertEqual(data['feature']['evidence'],[])
        with self.assertRaisesRegex(ValueError,'Invalid source IDs'):
            validate(data,sources)

    def test_evidence_repair_preserves_articles_and_rechecks_literal_source(self):
        from scripts.magazine.content import repair_evidence
        data,sources=fixture();expected=copy.deepcopy(data)
        data['original']['evidence'][0]['quote']='An invented translation of the original source passage.'
        client=Mock();client.json.return_value={'evidence':expected['original']['evidence']}
        self.assertEqual(repair_evidence(client,data,sources),expected)
        self.assertEqual(client.json.call_count,1);validate(data,sources)
    def test_evidence_repair_caps_sources_at_three(self):
        from scripts.magazine.content import repair_evidence
        data,sources=fixture()
        extra2={**sources[1],'id':'extra-two','kind':'primary'}
        extra3={**sources[1],'id':'extra-three','kind':'primary'}
        sources.extend([extra2,extra3])
        ids=['firefox','wp-1','extra-two','extra-three']
        byid={s['id']:s for s in sources}
        data['tips']['sources']=ids
        data['tips']['evidence']=[
            {'source':sid,'quote':' '.join(byid[sid]['text'].split())[:90]}
            for sid in ids
        ]
        client=Mock()
        repair_evidence(client,data,sources)
        self.assertEqual(data['tips']['sources'],ids[:3])
        self.assertEqual([e['source'] for e in data['tips']['evidence']],ids[:3])
        self.assertLessEqual(len(data['tips']['sources']),3)
        client.json.assert_not_called()
        validate(data,sources)

    def test_missing_source_evidence_uses_exact_relevant_excerpt(self):
        from scripts.magazine.content import repair_evidence
        data,sources=fixture()
        source=next(s for s in sources if s['id']=='wp-1')
        source['text'] += ' La leggibilità delle colonne dipende da frasi brevi e margini sufficienti.'
        data['qa']['sources']=['firefox','wp-1']
        data['qa']['evidence']=[{'source':'firefox','quote':data['qa']['evidence'][0]['quote']}]
        client=Mock()
        client.json.return_value={'evidence':[{'source':'wp-1','quote':'Passaggio inventato che non compare nella fonte.'}]}
        repair_evidence(client,data,sources)
        evidence=next(e for e in data['qa']['evidence'] if e['source']=='wp-1')
        normalized=' '.join(source['text'].split())
        self.assertGreaterEqual(len(evidence['quote']),25)
        self.assertLessEqual(len(evidence['quote']),240)
        self.assertIn(evidence['quote'],normalized)
        self.assertEqual(client.json.call_count,2)
        validate(data,sources)

    def test_overlong_exact_evidence_is_shortened_without_model_call(self):
        from scripts.magazine.content import repair_evidence
        data,sources=fixture()
        exact=' '.join(['passaggio documentato']*18)+'. Il resto della fonte resta verificabile.'
        source=next(s for s in sources if s['id']=='firefox')
        source['text'] += ' '+exact+' Altra frase della fonte.'
        data['original']['evidence']=[{'source':'firefox','quote':exact}]
        client=Mock()
        repair_evidence(client,data,sources)
        quote=data['original']['evidence'][0]['quote']
        normalized_source=' '.join(source['text'].split())
        self.assertGreaterEqual(len(quote),25)
        self.assertLessEqual(len(quote),240)
        self.assertIn(quote,normalized_source)
        client.json.assert_not_called()
        validate(data,sources)

    def test_overlong_invented_evidence_is_replaced_with_exact_source_text(self):
        from scripts.magazine.content import repair_evidence
        data,sources=fixture()
        invented='passaggio inventato non presente nella fonte '*8
        data['original']['evidence']=[{'source':'firefox','quote':invented}]
        client=Mock(return_value=None)
        client.json.return_value={'evidence':[{'source':'firefox','quote':invented}]}
        repair_evidence(client,data,sources)
        quote=data['original']['evidence'][0]['quote']
        source=next(s for s in sources if s['id']=='firefox')['text']
        self.assertNotEqual(quote,invented)
        self.assertGreaterEqual(len(quote),25)
        self.assertLessEqual(len(quote),240)
        self.assertIn(quote,' '.join(source.split()))
        self.assertEqual(client.json.call_count,2)
        validate(data,sources)

    def test_multisource_evidence_is_repaired_one_source_at_a_time(self):
        from scripts.magazine.content import repair_evidence
        data,sources=fixture()
        sentence='La verifica puntuale delle impostazioni aiuta a esportare il documento senza perdere i dettagli.'
        q2='Questa guida descrive un secondo metodo documentato per esportare il documento in formato PDF.'
        q3='La valutazione dei rischi dell’intelligenza artificiale richiede procedure e verifiche appropriate.'
        s2={'id':'libreoffice','kind':'primary','title':'Guida PDF','url':'https://help.libreoffice.org/latest/it/text/shared/01/ref_pdf_export.html','text':q2+' '+(sentence+' ')*10}
        s3={'id':'nist','kind':'primary','title':'Rischi IA','url':'https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.600-1.pdf','text':q3+' '+(sentence+' ')*10}
        sources.extend([s2,s3])
        data['tips']['sources']=['firefox','libreoffice','nist']
        first=data['tips']['evidence'][0]['quote']
        client=Mock()
        client.json.side_effect=[
          {'evidence':[{'source':'libreoffice','quote':q2}]},
          {'evidence':[{'source':'nist','quote':q3}]}
        ]
        repair_evidence(client,data,sources)
        self.assertEqual([e['source'] for e in data['tips']['evidence']],['firefox','libreoffice','nist'])
        self.assertEqual(data['tips']['evidence'][0]['quote'],first)
        self.assertEqual(client.json.call_count,2)
        validate(data,sources)

    def test_invented_evidence_is_replaced_with_literal_source_excerpt(self):
        from scripts.magazine.content import repair_evidence
        data,sources=fixture()
        invented='An invented translation of the original source passage.'
        data['original']['evidence'][0]['quote']=invented
        client=Mock();client.json.return_value={'evidence':[{'source':'firefox','quote':invented}]}
        repair_evidence(client,data,sources)
        quote=data['original']['evidence'][0]['quote']
        source=next(s for s in sources if s['id']=='firefox')['text']
        self.assertNotEqual(quote,invented)
        self.assertGreaterEqual(len(quote),25)
        self.assertLessEqual(len(quote),240)
        self.assertIn(quote,' '.join(source.split()))
        self.assertEqual(client.json.call_count,2)
        validate(data,sources)
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
    def test_counted_repair_normalizes_phrase_tokens_and_rechecks_word_count(self):
        from scripts.magazine.content import repair_lengths
        data,sources=fixture();expected=copy.deepcopy(data)
        expected_words=expected['qa']['items'][0]['body'].split()
        data['qa']['items'][0]['body']=' '.join(expected_words[:54])
        # Simulate a model returning two words in one array token. Flattening
        # should preserve the exact repaired prose while the count gate remains.
        returned=[' '.join(expected_words[:2]),*expected_words[2:]]
        client=Mock();client.json.return_value={'text0':returned}
        self.assertEqual(repair_lengths(client,data,sources),expected)
        self.assertEqual(client.json.call_count,1)
        validate(data,sources)

    def test_counted_repair_still_rejects_out_of_range_after_normalization(self):
        from scripts.magazine.content import repair_lengths
        data,sources=fixture();data['editorial']='Breve.'
        client=Mock();client.json.return_value={'text0':['two words']*95}
        repair_lengths(client,data,sources)
        with self.assertRaises(ValueError):validate(data,sources)
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
        self.assertIn('Newsletter AIVision',new)
        self.assertIn('Al momento non raccogliamo indirizzi',new)
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
        d,s=fixture()
        # Reproduce the live issue's long feature copy that previously overflowed by 3 pt.
        d['feature']['columns'][0]['body']=(
            'Nel panorama dei piccoli elettrodomestici e dei dispositivi connessi, '
            'le nuove funzioni software stanno cambiando il modo in cui le persone '
            'scelgono, configurano e usano i prodotti. Prima di acquistare conviene '
            'controllare quali funzioni dipendono da un account, quali dati vengono '
            'raccolti e per quanto tempo sono conservati. È utile anche verificare '
            'la disponibilità degli aggiornamenti, la compatibilità con il telefono '
            'e la possibilità di usare le funzioni essenziali senza servizi cloud. '
        )*2
        root=Path(__file__).resolve().parents[1]/'magazine/art'
        art={k:root/v for k,v in {'cover':'cover.jpg','feature':'creative.jpg','guide':'creative.jpg','original':'factcheck.jpg','tips':'archive.jpg'}.items()}
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'test.pdf';report=render(d,s,out,art,'COLLAUDO','18/10/2026 – 25/10/2026')
            self.assertEqual(report['pages'],8);self.assertGreaterEqual(report['links'],15)
            self.assertEqual(len(list(Path(tmp).glob('page-*.png'))),8)
            p=Layout(Path(tmp)/'bad.pdf','test','test',art)
            with self.assertRaises(ValueError):p.text('overflow '*100,10,10,50,10)
            # Real production failure: a news excerpt was only a few points too tall.
            p.text('Il fondatore Eric Migicovsky ha annunciato nuovi dettagli. '*12,
                   10,40,263,131,8.6,fit=True,min_size=7)
            p.text('first',10,200,100,20)
            with self.assertRaises(ValueError):p.text('overlap',10,200,100,20)
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
            self.assertEqual(post.call_count,6)
        limited=Mock(status_code=429,headers={'Retry-After':'1'})
        with patch('scripts.magazine.content.requests.post',side_effect=[limited,ok]) as post,patch('scripts.magazine.content.time.sleep'):
            self.assertEqual(client.call([{'text':'test'}]),[{'text':'{}'}])
            self.assertEqual(post.call_count,2)
        with patch('scripts.magazine.content.requests.post',return_value=Mock(status_code=429,headers={})) as post,patch('scripts.magazine.content.time.sleep'):
            with self.assertRaises(RuntimeError):client.call([{'text':'test'}])
            # One request on the rate-limited primary, then the fallback's three retries.
            self.assertEqual(post.call_count,4)

    def test_network_timeout_retries_then_uses_fallback_model(self):
        from requests import Timeout
        from scripts.magazine.content import Gemini
        client=Gemini.__new__(Gemini);client.key='test';client.model='test-model';client.last_request=0
        ok=Mock(status_code=200)
        ok.json.return_value={'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':'{}'}]}}]}
        with patch.dict('os.environ',{'GEMINI_FALLBACK_MODEL':'gemini-3.1-flash-lite'}),patch('scripts.magazine.content.requests.post',side_effect=[Timeout('one'),Timeout('two'),Timeout('three'),ok]) as post,patch('scripts.magazine.content.time.sleep'):
            self.assertEqual(client.call([{'text':'test'}]),[{'text':'{}'}])
        self.assertEqual(post.call_count,4)
        self.assertTrue(all(call.kwargs['timeout']==(10,60) for call in post.call_args_list))
        self.assertEqual(post.call_args_list[-1].args[0],'https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-lite:generateContent')

    def test_429_switches_to_fallback_model_immediately(self):
        from scripts.magazine.content import Gemini
        client=Gemini.__new__(Gemini);client.key='test';client.model='gemini-3.5-flash-lite';client.last_request=0
        limited=Mock(status_code=429,headers={});ok=Mock(status_code=200)
        ok.json.return_value={'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':'{}'}]}}]}
        with patch.dict('os.environ',{'GEMINI_FALLBACK_MODEL':'gemini-3.1-flash-lite'}),patch('scripts.magazine.content.requests.post',side_effect=[limited,ok]) as post,patch('scripts.magazine.content.time.sleep'):
            self.assertEqual(client.call([{'text':'test'}]),[{'text':'{}'}])
        self.assertEqual(post.call_count,2)
        urls=[call.args[0] for call in post.call_args_list]
        self.assertEqual(urls,[
            'https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent',
            'https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-lite:generateContent'
        ])

    def test_503_uses_low_cost_fallback_model(self):
        from scripts.magazine.content import Gemini
        client=Gemini.__new__(Gemini);client.key='test';client.model='gemini-3.5-flash-lite';client.last_request=0
        busy=Mock(status_code=503,headers={});ok=Mock(status_code=200)
        ok.json.return_value={'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':'{}'}]}}]}
        with patch.dict('os.environ',{'GEMINI_FALLBACK_MODEL':'gemini-3.1-flash-lite'}),patch('scripts.magazine.content.requests.post',side_effect=[busy,busy,busy,ok]) as post,patch('scripts.magazine.content.time.sleep'):
            self.assertEqual(client.call([{'text':'test'}]),[{'text':'{}'}])
        urls=[c.args[0] for c in post.call_args_list]
        self.assertEqual(urls[:3],[f'https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent']*3)
        self.assertEqual(urls[3],'https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-lite:generateContent')

    def test_explicit_model_does_not_silently_fallback(self):
        from scripts.magazine.content import Gemini
        client=Gemini.__new__(Gemini);client.key='test';client.model='gemini-3.5-flash-lite';client.last_request=0
        busy=Mock(status_code=503,headers={})
        with patch.dict('os.environ',{'GEMINI_FALLBACK_MODEL':'gemini-3.1-flash-lite'}),patch('scripts.magazine.content.requests.post',return_value=busy) as post,patch('scripts.magazine.content.time.sleep'):
            with self.assertRaises(RuntimeError):client.call([{'text':'test'}],model='gemini-3.1-flash-image')
        self.assertEqual(post.call_count,3)
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
