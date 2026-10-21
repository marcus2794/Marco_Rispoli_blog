# Una lente sul territorio piombinese

Dashboard che mette Piombino accanto ai comuni della provincia di Livorno, ai comuni costieri
tra 20 e 50 mila abitanti e a tutti i comuni italiani della stessa taglia, su una sessantina di
indicatori per abitante (popolazione, redditi, lavoro, agricoltura, cultura, servizi, mobilità, ambiente).

Pagina pubblicata: `lente/index.html` (e la copia in `docs/lente/` per GitHub Pages).

## Aggiornare

Il doppio clic su `Aggiorna sito.command` (nella cartella principale) fa tutto. A mano:

```
python3 tools/lente/aggiorna_dati.py   # scarica i dati più recenti dall'ISTAT (se non risponde, restano i vecchi)
python3 tools/lente/build_lente.py     # ricostruisce la pagina
```

Lo stesso avviene ogni lunedì con la GitHub Action "Aggiorna turismo".

## File

| file | cosa contiene |
|---|---|
| `aggiorna_dati.py` | scarica i dati dall'Atlante statistico dei comuni (aster.istat.it) e la classificazione dei comuni costieri (SITUAS) |
| `indicatori.py` | **definizione di ogni indicatore**: formula, unità, se un valore alto è meglio o peggio, descrizione. Per aggiungere o togliere un indicatore basta modificare questo file |
| `build_lente.py` | calcola gli indicatori, i gruppi di confronto, Toscana e Italia, e scrive la pagina |
| `template.html` | la pagina (grafica e interazione) |
| `raw/aster_comuni.csv` | i dati grezzi di tutti i comuni italiani |
| `raw/anni.json` | l'anno di riferimento di ogni fonte |
| `raw/situas_caratteristiche.csv` | comuni costieri, isolani, zona altimetrica (ISTAT, SITUAS) |
| `livorno.topo.json` | i confini dei comuni della provincia di Livorno |
