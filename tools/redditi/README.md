# I redditi del territorio piombinese

Dashboard sulle dichiarazioni dei redditi dal 2000: reddito medio reale, stipendi e pensioni,
composizione del reddito, IRPEF versata, disuguaglianza (top 10%, top 1%, Gini), redditi bassi e alti,
e la fotografia dell'ultimo anno tra i comuni di confronto.

Pagina pubblicata: `redditi/index.html` (e `docs/redditi/` per GitHub Pages).

## Aggiornare

Il doppio clic su `Aggiorna sito.command` fa tutto. A mano:

```
python3 tools/redditi/aggiorna_redditi.py   # scarica dal Ministero gli anni nuovi (e l'indice FOI)
python3 tools/redditi/build_redditi.py      # ricostruisce la pagina
```

`aggiorna_redditi.py --tutti` riscarica tutti gli anni dal 2000.

## File

| file | contenuto |
|---|---|
| `raw/irpef_comuni.csv` | dati IRPEF per comune e anno (comuni toscani, gruppi di confronto, totali Italia/Toscana/provincia di Livorno) |
| `raw/foi.csv` | variazioni medie annue dell'indice ISTAT FOI senza tabacchi (deflatore) |
| `raw/nomi.csv` | nomi dei comuni |
| `build_redditi.py` | calcola medie, quote, IRPEF, stime di disuguaglianza e scrive la pagina |
| `template.html` | la pagina |

I gruppi di confronto vengono da `tools/lente/gruppi.json`, prodotto dalla dashboard "Piombino in numeri".
