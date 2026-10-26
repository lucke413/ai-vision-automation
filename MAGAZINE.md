# AIVision Magazine e Connect

## Stato e confini

Implementazione separata dalle automazioni quotidiane. Template derivato dal pilota approvato: A4, testata rossa, colonna laterale in copertina, grandi immagini, tre colonne editoriali, sei passi numerati, box gialli, indice e fonti cliccabili. Il formato automatico produce 8 pagine, 7 quando mancano notizie settimanali. Gli articoli originali sono distinti dalle notizie WordPress.

Il merge installa **solo RSS nel widget esistente** (e newsletter/ultimo numero solo se realmente disponibili). Non crea un secondo widget e non pubblica un PDF dimostrativo. La schedulazione live resta disabilitata finché `MAGAZINE_ENABLED` non è `true`.

## Esecuzione

```sh
pip install -r requirements-magazine.txt
python -m unittest discover -s tests -p 'test_*.py'
python -m scripts.magazine.run --preview-art magazine/art
```

Serve `GEMINI_API_KEY` per i testi e la revisione visuale. Preview riutilizza le illustrazioni del pilota; il manifest ne impedisce la pubblicazione. Non serve una credenziale WordPress in preview. Le fixture dei test sono esclusivamente dimostrative e non attraversano il percorso live.

Workflow `AIVision Magazine`, manuale: `preview`, `connect` o `live`. Programmazione domenica alle 09:00 `Europe/Rome`; GitHub può ritardare l'avvio dei job. Intervallo editoriale: dalla domenica precedente alle 09:00 incluse alla domenica corrente alle 09:00 escluse. Un rilancio usa lo stesso identificativo ISO del numero, non genera una seconda edizione.

## Variabili e segreti

Riutilizza esclusivamente i segreti già previsti dal progetto: `GEMINI_API_KEY`, `WP_BASE_URL`, `WP_USERNAME`, `WP_APP_PASSWORD`. `GITHUB_TOKEN` è fornito automaticamente. La chiave WordPress deve permettere media, articoli, pagine, categorie e modifica dei widget. Un ruolo capace di pubblicare articoli può non avere il permesso di modificare widget: HTTP 401/403 ferma quella fase.

| Variabile | Significato |
|---|---|
| `GEMINI_MODEL` | Modello testuale e multimodale già usato dal progetto |
| `MAGAZINE_IMAGE_MODEL` | Modello immagini con accesso effettivamente disponibile nell'account; nessun valore di default |
| `MAGAZINE_ENABLED` | `true` solo dopo collaudo completo del primo numero reale |
| `NEWSLETTER_FORM_URL` | URL HTTPS del modulo ospitato Brevo, dominio `sibforms.com` |
| `NEWSLETTER_DOI_VERIFIED` | `true` solo dopo prova di consenso, conferma e disiscrizione |

Il sistema **non attiva fatturazione né acquista servizi**. Al 26/10/2026 la documentazione Google indica che la generazione immagini via API non è inclusa nel piano gratuito. Il live richiede un modello immagini abilitato; finché manca, non deve essere attivato. L'account newsletter è separato e non è configurato da questo repository. Modelli e tariffe vanno verificati prima dell'attivazione: https://ai.google.dev/gemini-api/docs/pricing .

## Fonti e qualità

- Selezione WordPress con controllo finale su `date_gmt`, paginazione limitata, esclusione offerte per categorie, titolo e testo; filtro prudente che può scartare anche articoli che menzionano offerte in altro contesto.
- Deduplica URL canonico, titolo e hash del contenuto. I numeri della rivista non rientrano nelle selezioni successive.
- Ricerca primaria evergreen iniziale: LibreOffice e Chrome (stampa/PDF) e NIST AI 600-1. Aggiornare `PRIMARY` in `content.py` per ampliare i temi e ruotare le risorse. Questa prima versione non esegue ricerca aperta senza limiti.
- JSON validato: rubriche, lunghezze, fonti per ID, estratti probatori esatti. Secondo passaggio editoriale del modello; non è una garanzia matematica di accuratezza. Un errore, fonte irraggiungibile o JSON incompleto interrompe il numero.
- Immagini live generate, dichiarate illustrative. Nessuna immagine WordPress viene riutilizzata senza un accertamento dei diritti; non basta che sia tecnicamente scaricabile.
- PDF: A4, numero pagine, testo entro i limiti, collisioni tra riquadri testuali, pagine non vuote, link interni, outline, numero pagina, file 100 KB–18 MB. Ogni pagina viene renderizzata e sottoposta a revisione visuale multimodale. Le immagini sono verificate per formato, dimensioni e peso.
- Preview locale ispezionata visivamente; test automatici distinti dalla prova live con credenziali. La prima esecuzione completa in Actions va controllata prima di abilitare lo schedule.

## Pubblicazione e recupero

Gli artifact Actions conservano PDF, pagine PNG, copertina, JSON editoriale, fonti, rapporto e manifest per 90 giorni. Non contengono segreti o indirizzi di iscritti. Il PDF e la copertina pubblicati restano nei media WordPress; il registro persistente è nel branch `magazine-state`.

Ogni POST di creazione viene preceduto da un record `pending`. Prima di creare, si riconcilia lo slug esatto remoto. Timeout o risposta ambigua **non** causano tentativi ciechi. PDF e copertina sono verificati via hash dopo l'upload. Una modifica manuale o cancellazione del media blocca la riconciliazione, invece di produrre copie.

Un numero pubblicato usa un solo articolo `aivision-magazine-AAAA-MM-GG`, copertina come immagine in evidenza e categoria AIVision Magazine. La pagina `/aivision-magazine/` contiene ultimo numero e archivio. Le automazioni esistenti Facebook e Telegram vedono il nuovo ID WordPress e usano i propri registri anti-duplicazione; non esiste un secondo sender. Si rispettano le loro modalità e i loro limiti già configurati.

Se il numero è pubblicato ma archivio/widget falliscono, il rilancio riconcilia questi ultimi. Se è `reserved`, scaricare l'artifact originale del run fallito e rieseguire, con le credenziali in ambiente:

```sh
python -m scripts.magazine.run --live --resume /percorso/artifact
```

Non ricreare il PDF: gli hash devono coincidere con il numero riservato. Non cancellare record pending senza aver verificato il risultato remoto. Se un'operazione pending non ha un oggetto remoto, serve riconciliazione manuale documentata prima di riabilitarla.

Il backup iniziale di `block-20` è in `widget_backup` nel registro. Ripristino: aggiornare **lo stesso** widget con `instance.raw` del backup; non creare un altro blocco. Il contenuto social originale viene conservato integralmente; solo il segmento tra marker `aivision-connect` viene aggiornato.

## Newsletter: attivazione concreta

1. Creare o collegare l'account Brevo scelto dal proprietario; nessuna password nel repository.
2. Creare lista e modulo con campo email obbligatorio, informativa privacy effettiva del sito, consenso esplicito, double opt-in, pagina di conferma e messaggi di errore.
3. Configurare mittente e autenticazione del dominio secondo le istruzioni del provider. Altervista può limitare la gestione DNS: verificare il mittente consentito prima degli invii.
4. Fare una prova con un indirizzo del proprietario: email non valida, iscrizione, nessuna attivazione prima della conferma, conferma, disiscrizione e iscrizione ripetuta.
5. Impostare `NEWSLETTER_FORM_URL` e `NEWSLETTER_DOI_VERIFIED=true`, eseguire `connect` e verificare modulo su mobile. Il widget incorpora il modulo Brevo con caricamento differito e mantiene un link alternativo. Se WordPress elimina l'iframe, il readback segnala il problema; non dichiara installazione riuscita.
6. Il file `newsletter-draft.json` prepara oggetto e introduzione del numero; l'invio non è attivo. Una futura integrazione invio dovrà usare un ID campagna persistente e i contatti del provider, mai elenchi email in GitHub.

## Manutenzione

Controllare il report dopo ogni errore, le quote Gemini e le fonti primarie. Ampliare/ruotare temi prima che le rubriche evergreen diventino ripetitive. Aggiornare dipendenze tramite PR con la suite completa. Controllare la conservazione degli artifact e fare backup WordPress. La revisione automatica non sostituisce una verifica editoriale umana del primo numero o dopo modifiche sostanziali al modello/template.

Riferimenti tecnici: https://developer.wordpress.org/rest-api/reference/widgets/ ; https://github.blog/changelog/2026-03-19-github-actions-late-march-2026-updates/ . Le scansioni delle riviste storiche usate per lo studio non sono incluse né ridistribuite.
