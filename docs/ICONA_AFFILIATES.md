# AIVision — link Amazon tramite IconA Altervista

Sui blog Altervista sono consentiti **solo** link affiliati generati dal servizio
**IconA**, non i link Amazon Associates personali. Il workflow di AIVision non
può convertire autonomamente URL commerciali in IconA: non è documentata
un'API pubblica per farlo. Questa integrazione riutilizza **solo link già
generati e confermati** nel tuo pannello Altervista, senza manipolarli.

## Attivazione, quando IconA è disponibile
1. Nella bacheca WordPress apri **Guadagna > Affiliazioni IconA** e accetta
   il contratto. Se la voce non compare, il servizio non è disponibile
   per quel sito: **non attivare** l'integrazione con il tag personale.
2. In **Cerca** o **Genera**, recupera e copia un link IconA per un prodotto
   esatto, annotandone marca e modello.
3. Nel repository GitHub aggiungi un **Actions secret** chiamato
   `ICONA_LINKS_JSON` con un array di voci come questo (URL solo illustrativo):
   ```json
   [
     {
       "product_name": "Nome marca Modello 123",
       "url": "https://www.amazon.it/dp/ESEMPIO_NON_REALE",
       "source": "altervista_icona",
       "confirmed": true
     }
   ]
   ```
   L'URL illustrativo **non** è un link affiliato. Sostituiscilo con
   l'URL IconA reale prodotto dalla bacheca, copiato senza modifiche.
4. Aggiungi una **Actions variable** `ICONA_ENABLED` con valore `true`.
   La variabile non abilita link finché manca un catalogo valido.
5. Quando esegui un **test** con `publish_live=false`, controlla nel report
   WordPress il campo `affiliate_links_inserted` e le anteprime dei post.

## Regole automatiche
- **Nessun link per impostazione predefinita**. La presenza di URL, un tag
  personale o una parola "Amazon" nel testo non basta.
- Un link è aggiunto solo agli articoli su prodotti con una corrispondenza
  precisa fra il nome del modello **nel titolo** e il catalogo IconA.
  Max 2 per articolo; guide e tutorial esclusi.
- Solo HTTPS su `www.amazon.it`, `amazon.it` o `amzn.to`.
  Non vengono generati, accorciati o modificati URL.
- Link chiaramente indicati come commerciali, con `rel="sponsored nofollow"`.
  Non mostra prezzi non aggiornati, disponibilità garantite o sconti inventati.
- Dopo la pubblicazione, verificare periodicamente il catalogo: i prodotti
  possono esaurirsi o cambiare prezzo.

Questa è un'**automazione dell'inserimento**, non della generazione o ricerca
di link IconA. L'attivazione potrebbe essere possibile solo su account
Altervista per cui è presente la voce Affiliazioni IconA.

Fonti:
- https://tutorial.altervista.org/link-di-affiliazione-icona/
- https://tutorial.altervista.org/chiariamo-tutti-i-dubbi-sul-servizio-di-affiliazione-icona/
- https://tutorial.altervista.org/come-sfruttare-il-servizio-di-affiliazioni-icona-in-caso-di-prime-day-festa-delle-offerte-o-black-friday/
