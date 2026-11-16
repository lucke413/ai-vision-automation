# AI Vision Automation

Pipeline Python che raccoglie notizie RSS, seleziona e genera articoli con Gemini e li pubblica o pianifica su WordPress: https://aivision.altervista.org.
Il tema WordPress, le impostazioni AlterVista, il consenso e il collegamento dell'account AdSense non sono distribuiti da questo repository.

## Flussi

- `ai-vision.yml`: generazione giornaliera; push/PR eseguono soltanto test isolati.
- `adsense-audit.yml`: diagnosi pubblica giornaliera o manuale, senza Gemini e senza credenziali WordPress.
- `full-seo-audit.yml`: inventario SEO pubblico.
- `seo-archive-recovery.yml`: manutenzione metadescrizioni e diagnosi archivio, con protezioni proprie.
- `telegram.yml` e `social-growth.yml`: automazioni social esistenti.

## AdSense: proprietà e approvazione sono controlli diversi

Il workflow usa per impostazione predefinita l'ID `pub-7248850124367665`, confermato dal proprietario il 4 novembre 2026 e rilevato in ads.txt. Per sostituirlo, in Settings → Secrets and variables → Actions → Variables aggiungere `ADSENSE_PUBLISHER_ID`, copiando l'ID dal proprio account AdSense (`pub-` seguito da 16 cifre; accettato anche `ca-pub-`). Non usare automaticamente un codice trovato nel sito: AlterVista può esporre identificativi della piattaforma e di altri venditori.

Eseguire **AI Vision AdSense Audit** e leggere l'artefatto `ai-vision-adsense-audit`:

- `not_configured`: account atteso sconosciuto; nessuna conclusione sulla proprietà.
- `invalid_configuration`: formato dell'ID non valido.
- `not_found`: ID atteso non trovato nei tag di integrazione o nelle righe DIRECT di ads.txt.
- `public_match`: corrispondenza pubblica rilevata; NON equivale a proprietà confermata o sito approvato da Google.

Il report è diagnostico: un workflow verde indica che il controllo è stato eseguito, non che AdSense abbia approvato il sito. Lo user-agent simulato non dimostra l'accesso dai veri IP Google; l'audit non valuta tutte le regole robots, JavaScript, consenso o qualità editoriale.

Per un problema di proprietà controllare URL e ID nell'account e l'integrazione nel pannello AlterVista/WordPress. Un ads.txt aggiunto qui non viene pubblicato sul dominio AlterVista. Per un rifiuto editoriale occorre leggere la motivazione esatta di Google e valutare utilità, originalità, attribuzione delle fonti e navigazione degli articoli già online. Aumentare parole o numero di articoli non garantisce l'approvazione.

Riferimenti ufficiali:
- https://support.google.com/adsense/answer/12131223?hl=it
- https://support.google.com/adsense/answer/12176698?hl=it
- https://support.google.com/adsense/answer/12171612?hl=it

## Originalità editoriale e blocco di pubblicazione

Il generatore 5.0 esegue un controllo locale prima di inserire una bozza nel lotto pubblicabile:

- confronta l'articolo con il testo integrale estratto dalla fonte usando sequenze esatte di sette parole, sovrapposizione dei paragrafi e similarità dell'ordine lessicale;
- blocca o mette in revisione manuale le bozze con sovrapposizione sospetta;
- richiede una revisione se il testo integrale della fonte non è stato recuperato: il solo titolo o un breve estratto RSS non bastano per dichiarare verificata l'originalità;
- rileva marcatori di contenuto sponsorizzato nella fonte e richiede che la disclosure commerciale sia conservata nell'articolo;
- conserva le bozze respinte nell'array `rejected_items` dell'artefatto, senza inviarle a WordPress.

Il publisher 3.0 verifica nuovamente il risultato prima di creare il post. Le bozze prodotte dal nuovo generatore devono avere `originality_check.status` uguale a `pass` o `not_applicable` e `publishable=true`.

Il controllo è deterministico e non usa servizi antiplagio esterni. È un filtro di somiglianza testuale, non una certificazione legale né una prova di originalità semantica: parafrasi profonde, fatti copiati senza frasi identiche e qualità/accuratezza delle analisi richiedono ancora una revisione editoriale umana. I metadati di provenienza (URL fonte e risultato del controllo) sono conservati nel report WordPress; gli artefatti delle bozze e del report sono trattenuti 90 giorni per facilitare gli audit successivi.

## Verifiche locali

```sh
python -m pip install -r requirements.txt
python -m compileall -q scripts tests
python -m unittest discover -s tests -p 'test_*.py' -v
python scripts/adsense_audit.py
```

I dati generati, le cache Python e gli ambienti locali sono esclusi da Git. Conservare gli artefatti diagnostici tramite GitHub Actions.


## Audit editoriale completo e controlli di pubblicazione (5.0 / 3.0)

Il workflow `editorial-content-audit.yml` esegue una scansione pubblica, in sola lettura, di tutti gli articoli pubblicati e produce un JSON e un CSV articolo per articolo. Cerca segnali di offerte datate, contenuti promozionali potenzialmente scaduti, attribuzioni di prove/recensioni, note redazionali residue, dichiarazioni affiliate, assenza di link interni/esterni, struttura H2 e possibili corpi quasi duplicati. I segnali sono priorità di revisione, non verdetti automatici né regole Google.

Il controllo di originalità 1.1 confronta anche la sovrapposizione tematica dei paragrafi e il loro ordine. Un testo che cambia le parole ma conserva la stessa scaletta può essere bloccato o inviato a revisione. Il test resta un filtro deterministico prudenziale: non certifica l'originalità semantica.

Il publisher 3.0 aggiunge un link HTTPS alla fonte originale, quando valido, e non riutilizza immagini RSS/OpenGraph se la bozza non contiene una prova esplicita dei diritti. In assenza di licenza/permesso verificabile usa la copertina grafica generata localmente. Per licenze Creative Commons con attribuzione richiede anche il campo `image_attribution`. Le dichiarazioni di link affiliati/commissioni sono bloccate finché il contenuto non implementa realmente tali link.

Il lettore delle fonti 5.0 esclude anche contenitori sidebar, articoli correlati, widget, pubblicità e newsletter, oltre ai tag di navigazione già ignorati.

Per eseguire localmente il nuovo audit:

```sh
python -m pip install requests
python scripts/editorial_content_audit.py
```

L'audit è read-only. Le modifiche agli articoli esistenti devono essere preparate con backup, controlli di concorrenza e verifica dopo la scrittura; non si applicano riscritture in massa sulla sola base del conteggio parole.
