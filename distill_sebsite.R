# Create distill package

library(distill)
# gh_pages is true because it should be automatically linked with github.
create_website(dir = ".", title = "The Mind Walker", gh_pages = T)

#  Create a new index file  
create_article(file = "index", template = "Onofre", package = "postcards")