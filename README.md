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

In Settings → Secrets and variables → Actions → Variables aggiungere `ADSENSE_PUBLISHER_ID`, copiando l'ID dal proprio account AdSense (`pub-` seguito da 16 cifre; accettato anche `ca-pub-`). Non usare automaticamente un codice trovato nel sito: AlterVista può esporre identificativi della piattaforma e di altri venditori.

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

## Verifiche locali

```sh
python -m pip install -r requirements.txt
python -m compileall -q scripts tests
python -m unittest discover -s tests -p 'test_*.py' -v
python scripts/adsense_audit.py
```

I dati generati, le cache Python e gli ambienti locali sono esclusi da Git. Conservare gli artefatti diagnostici tramite GitHub Actions.
