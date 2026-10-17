#!/bin/bash
# Doppio clic per aggiornare la dashboard, rigenerare il blog e pubblicarlo su GitHub.
cd "$(dirname "$0")"
echo "== 1/3  Scarico i dati aggiornati della Regione Toscana..."
python3 tools/turismo/build_dashboard.py || { echo "Aggiornamento dati non riuscito."; read -p "Premi Invio per chiudere"; exit 1; }
echo
echo "== 2/3  Rigenero il blog..."
if command -v Rscript >/dev/null 2>&1; then
  Rscript build_website.R || echo "Attenzione: il blog non si è rigenerato (la dashboard sì)."
else
  echo "R non trovato: salto il blog, aggiorno solo la dashboard."
fi
echo
echo "== 3/3  Pubblico su GitHub..."
git add -A
if git diff --cached --quiet; then
  echo "Niente di nuovo da pubblicare."
else
  git commit -m "Aggiornamento del sito $(date +%Y-%m-%d)" && git push && echo "Fatto: tra un paio di minuti il sito online è aggiornato."
fi
read -p "Premi Invio per chiudere"
