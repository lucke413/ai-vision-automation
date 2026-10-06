# Nuovo magazine: stato e utilizzo

Implementazione preparatoria separata per videogiochi multipiattaforma, manga/fumetti,
anime, fiere e collezionismo. Il nome «Nerd Magazine» è provvisorio.
Non converte il sito AI Vision né cambia i suoi workflow, orari o social.

## Workflow manuale

Dopo l'integrazione in main: Actions → Nerd Magazine - articoli → Run workflow.
La modalità iniziale è simulazione: genera fino a cinque articoli e tre riserve,
prepara un report WordPress e salva i materiali negli artifact `nerd-materiali`.
Usa il secret GEMINI_API_KEY e la variabile GEMINI_MODEL già previsti dal progetto.
La simulazione usa comunque Gemini: può consumare quota o credito del provider.

Per pubblicare, definire prima il sito: nuovo WordPress oppure una sezione di
AI Vision. La variabile NERD_TARGET_URL deve coincidere con WP_BASE_URL.
Il workflow usa WP_USERNAME e WP_APP_PASSWORD. Non cambiare i secret condivisi
per un nuovo dominio senza separare prima anche le credenziali del workflow AI Vision.
La casella publish attiva il publisher con gli orari esistenti Europe/Rome.

## Garanzie e limiti

- File dati e registro degli artifact separati da AI Vision.
- Nessun cron: esecuzione solo manuale.
- Stesse dipendenze e funzioni della pipeline attuale, con profilo dedicato.
- Fonti in config/nerd.json, modificabili. La copertura iniziale è gaming/fumetti;
  fiere, anime e collezionismo dipendono dalle notizie incluse in quelle fonti.
  Per un calendario esaustivo servono fonti ufficiali specifiche, da integrare.
- Prove altrui attribuite; nessuna esperienza diretta inventata. Le istruzioni al
  modello non equivalgono a verifica indipendente della veridicità.
- Copertine grafiche astratte originali del publisher esistente; non screenshot
  dei giochi e non immagini prelevate automaticamente da altri siti.
- Articoli con quality_warnings esclusi. I fallimenti parziali danno workflow rosso
  e report consultabile; un lotto può contenere meno di cinque articoli.
- La deduplica storica riusa i report degli ultimi sette giorni; il publisher
  controlla anche lo slug. Non è una garanzia contro ogni riformulazione di notizie.
- La modalità simulazione non pubblica e non carica media su WordPress.

## Lavoro ancora necessario prima del lancio

Scelta della destinazione e del nome, allestimento del sito/struttura/menu,
collegamento della destinazione confermata e test completo Gemini → WordPress.
I test locali non utilizzano credenziali remote e non provano il consumo API.
Non attivare la pubblicazione pensando che il nuovo sito sia già stato creato.
