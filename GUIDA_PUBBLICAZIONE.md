# Come pubblicare il sito (guida passo passo)

## Una volta sola
1. Apri **GitHub Desktop** → File → Add local repository → scegli la cartella `Marco_Rispoli_blog`.
2. Su github.com, nel repository: **Settings → Pages** → Source "Deploy from a branch", Branch `main`, cartella `/docs` → Save. (Il repository deve essere pubblico.)
3. **Settings → Actions → General → Workflow permissions** → "Read and write permissions" → Save. Serve all'aggiornamento automatico settimanale.
4. Puoi cancellare la vecchia cartella `mind_walker/` (ormai vuota) e `tools/turismo/_doppioni/`.

## Ogni volta che vuoi aggiornare
- **Il modo più semplice:** doppio clic su `Aggiorna sito.command`. Scarica i dati nuovi, ricostruisce dashboard e blog, fa commit e push. (La prima volta macOS potrebbe chiedere conferma: tasto destro → Apri.)
- **Se hai modificato un post:** apri `mind_walker.Rproj` in RStudio, apri `build_website.R` e premi **Source**. Poi in GitHub Desktop scrivi un messaggio (es. "Nuovo post") → **Commit to main** → **Push origin**.

## Dove si vede
- Blog: https://marcus2794.github.io/Marco_Rispoli_blog/
- Dashboard: https://marcus2794.github.io/Marco_Rispoli_blog/turismo/
- Nella dashboard il pulsante **Copia link** copia il link con il comune scelto (utile da mandare a qualcuno).

Dopo un push servono 1–2 minuti perché GitHub Pages pubblichi la nuova versione. Nella scheda **Actions** del repository puoi lanciare a mano l'aggiornamento dei dati con **Run workflow**.
