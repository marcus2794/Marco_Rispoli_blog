install.packages(c("distill", "rmarkdown"))

library("distill")
library("markdown")


rmarkdown::clean_site()
rmarkdown::render_site()

# create a new post
create_post("self-respect")