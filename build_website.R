# Rigenera tutto il sito "The Mind Walker" nella cartella docs/.
# Da RStudio: apri questo file e premi "Source" (oppure Cmd+Shift+S).

for (p in c("distill", "rmarkdown")) {
  if (!requireNamespace(p, quietly = TRUE)) install.packages(p)
}
library(distill)

# la cartella di lavoro deve essere quella del progetto (dove sta _site.yml)
if (!file.exists("_site.yml")) stop("Apri il progetto Marco_Rispoli_blog in RStudio prima di lanciare questo file.")

rmarkdown::render_site(encoding = "UTF-8")

# GitHub Pages: senza questo file ignorerebbe alcune cartelle
file.create("docs/.nojekyll")
message("Sito rigenerato in docs/. Ora fai commit e push.")

# Per creare un nuovo post:
# distill::create_post("Titolo del post")
