# Dashboard turismo Toscana

Pagina: `turismo/index.html` (sorgente) e `docs/turismo/index.html` (pubblicata su GitHub Pages).

## Aggiornare con un clic

- **Su GitHub**: scheda *Actions* → *Aggiorna dashboard turismo* → *Run workflow*. Gira da solo anche ogni lunedì.
  Scarica i dati nuovi, rigenera la dashboard e la pubblica (solo se la Regione ha pubblicato qualcosa di nuovo).
- **Sul Mac**: doppio clic su `Aggiorna sito.command` (nella cartella principale). Aggiorna la dashboard,
  rigenera il blog con R e fa commit e push.

## Fonti scaricate da `build_dashboard.py`

| File | Contenuto | Fonte |
|---|---|---|
| `raw/mov*.csv`, `raw/con*.csv` | arrivi, presenze, posti letto per comune | open data Regione Toscana (dati.toscana.it) |
| `raw_saiku/consistenza_tipi.txt` | posti letto per tipo di struttura, 2005– | banca dati turismo regionale |
| `raw_saiku/provenienze_comuni.txt` | arrivi e presenze per regione/paese, 2012– | banca dati turismo regionale |
| `raw_saiku/presenze_trimestri.csv` | presenze per trimestre, 2012– | banca dati turismo regionale |
| `raw_saiku/bilancio_demografico.csv` | residenti, nati−morti, iscritti−cancellati, famiglie, 2002– | ISTAT, banca dati Demografia Regione Toscana (Saiku) |
| `raw_saiku/indicatori_eta_2024.csv` | età media, indice di vecchiaia (2024) | open data Regione Toscana |
| `raw_saiku/popolazione_comuni.csv` | residenti (riserva, se manca il bilancio) | open data Regione Toscana |
| `raw_saiku/asia_addetti_comuni.csv` | sedi di imprese (unità locali) e addetti per settore, 2017– | ISTAT ASIA, open data Regione Toscana |

Il link d'accesso pubblico alla banca dati turismo viene letto ogni volta dalla pagina della Regione.
Se una fonte non risponde, restano i dati precedenti e lo script lo segnala.

Comandi:

    python3 tools/turismo/build_dashboard.py            # scarica e rigenera
    python3 tools/turismo/build_dashboard.py --offline  # rigenera senza scaricare

`template.html` è la pagina, `toscana_comuni.topo.json` i confini dei comuni (openpolis/geojson-italy).
`piombino/` contiene gli Excel originali usati in passato dal post R sul turismo.
