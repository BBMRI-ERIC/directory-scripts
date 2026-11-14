# Real device measurements and exact geometry assertions for survey maps.
root <- commandArgs(trailingOnly = TRUE)[[1]]
source(file.path(root, "R-maps", "survey_participation_common.R"))
if(requireNamespace("sf",quietly=TRUE)) {
  outer <- matrix(c(0,0,2,0,2,2,0,2),ncol=2,byrow=TRUE)
  hole <- matrix(c(.5,.5,1,.5,1,1,.5,1),ncol=2,byrow=TRUE)
  island <- matrix(c(3,0,4,0,4,1,3,1,3,0),ncol=2,byrow=TRUE)
  malformed <- structure(list(list(outer,hole),list(island)),class=c("XY","MULTIPOLYGON","sfg"))
  countries <- sf::st_sf(iso_a2="AT",name="Synthetic country",geometry=sf::st_sfc(malformed,crs=3857))
  fixed <- bbmri_survey_valid_countries(countries)
  stopifnot(all(sf::st_is_valid(fixed)),fixed$iso_a2=="AT",fixed$name=="Synthetic country",
            abs(as.numeric(sf::st_area(fixed))-4.75)<1e-9)
  script_dir <- file.path(root,"R-maps")
  source(file.path(script_dir,"map_config.R")); source(file.path(script_dir,"map_common.R"))
  fixed$iso_a2 <- "NO"
  cfg <- bbmri_map_config()
  expected <- bbmri_country_label_df(fixed,cfg,3857,label_codes="NO")
  anchors <- bbmri_survey_anchor_data(list(countries=fixed,crs=3857),cfg,"bbmri-members","NO")
  stopifnot(identical(anchors$x,expected$x),identical(anchors$y,expected$y))
  plain <- bbmri_country_anchor_df(fixed,3857,label_codes="NO")
  oec <- bbmri_survey_anchor_data(list(countries=fixed,crs=3857),cfg,"oec","NO")
  stopifnot(identical(oec$x,plain$x),identical(oec$y,plain$y))
}
device <- c(width = 240, height = 135)
file <- tempfile(fileext = ".pdf")
grDevices::pdf(file, width = 240/25.4, height = 135/25.4)
counts <- data.frame(country = c("AT", "BE", "NL", "CH", "DE", "CZ", "SI", "IT", "MT", "QA"),
                     directory_count = c(2, 0, 4, 6, 8, 5, 2, 60, 0, 1),
                     so2_count = c(3, 2, 0, 2, 4, 3, 1, 40, 1, 1),
                     mucp_count = c(2, 1, 1, 3, 4, 2, 0, 55, 1, 0),
                     shared_count = c(1, 1, 0, 1, 2, 1, 0, 20, 1, 0),
                     x = 120, y = 60)
groups <- bbmri_survey_glyphs(counts, "mucp", 0.4, device)
stopifnot(groups[[1]]$bars$upper[groups[[1]]$bars$role == "directory"] == 2)
stopifnot(groups[[1]]$bars$upper[groups[[1]]$bars$role == "so2"] == 3)
stopifnot(all(groups[[1]]$bars$upper[groups[[1]]$bars$role == "shared"] == 1))
stopifnot("3 of 2" %in% groups[[1]]$labels$text)
placed <- bbmri_place_survey_glyphs(groups, device, list(c(0,240,0,15),c(0,240,122,135)))
stopifnot(length(placed) == nrow(counts))
for (i in seq_along(placed)) {
  box <- placed[[i]]$box
  stopifnot(box[[1]] >= 0, box[[2]] <= 240, box[[3]] >= 15, box[[4]] <= 122)
  if (i > 1) for (j in seq_len(i-1)) stopifnot(!bbmri_survey_boxes_overlap(box, placed[[j]]$box))
}
again <- bbmri_place_survey_glyphs(groups, device, list(c(0,240,0,15),c(0,240,122,135)))
stopifnot(identical(placed, again))
remote <- data.frame(country=c("AU","CA","EU","NO","UG","US","VN"),
  directory_count=c(1,3,1,13,1,7,1),so2_count=c(0,0,0,2,0,0,0),
  mucp_count=c(0,0,0,3,0,0,0),shared_count=c(0,0,0,1,0,0,0),x=218,y=100,outside=TRUE)
remote_groups <- bbmri_survey_glyphs(remote,"mucp",28/69,device)
remote_placed <- bbmri_place_survey_glyphs(remote_groups,device,list(c(0,240,0,15),c(0,240,122,135)))
stopifnot(length(remote_placed)==nrow(remote))
long <- counts[1,,drop=FALSE]
long$directory_count <- 100000
long$so2_count <- 123456
large <- bbmri_survey_glyphs(long,"so2",0.0002,device)[[1]]
stopifnot(diff(large$box[1:2]) > diff(groups[[1]]$box[1:2]))
long$mucp_count <- 1000000; long$shared_count <- 1
for(pair in list(c(900,1000),c(1,10))) {
  long$directory_count <- pair[[1]]; long$so2_count <- pair[[2]]
  extreme <- bbmri_survey_glyphs(long,"mucp",28/1000000,device)[[1]]
  for(i in 1:2) {
  label <- extreme$labels[i,,drop=FALSE]
  width <- bbmri_survey_text_width(label$text)+1
  box <- c(label$x-width/2,label$x+width/2,label$y-1.9,label$y+1.9)
  for(j in seq_len(nrow(extreme$bars))) {
    bar <- extreme$bars[j,,drop=FALSE]
    stopifnot(!bbmri_survey_boxes_overlap(box,c(bar$xmin,bar$xmax,
      bar$lower*extreme$scale,bar$upper*extreme$scale),gap=0))
  }
  }
}
grDevices::dev.off()
unlink(file)
bundle <- tempfile(); dir.create(bundle)
stage <- tempfile(tmpdir=bundle); dir.create(stage)
writeLines("old-a",file.path(bundle,"a")); writeLines("old-b",file.path(bundle,"b"))
writeLines("new-a",file.path(stage,"a")); writeLines("new-b",file.path(stage,"b"))
n <- 0
fail_once <- function(from,to) {
  n <<- n+1
  if(n==4) return(FALSE)
  file.rename(from,to)
}
error <- try(bbmri_survey_publish(stage,bundle,c("a","b"),rename=fail_once),silent=TRUE)
stopifnot(inherits(error,"try-error"),readLines(file.path(bundle,"a"))=="old-a",
          readLines(file.path(bundle,"b"))=="old-b")
writeLines("new-a",file.path(stage,"a")); writeLines("new-b",file.path(stage,"b"))
n <- 0
fail_restore <- function(from,to) {
  n <<- n+1
  if(n %in% c(4,5)) return(FALSE)
  file.rename(from,to)
}
error <- suppressWarnings(try(bbmri_survey_publish(stage,bundle,c("a","b"),rename=fail_restore),silent=TRUE))
backups <- list.dirs(bundle,full.names=TRUE,recursive=FALSE)
backups <- backups[grepl(".map-backup-",basename(backups),fixed=TRUE)]
stopifnot(inherits(error,"try-error"),length(backups)==1,
          readLines(file.path(backups[[1]],"a"))=="old-a",
          readLines(file.path(bundle,"b"))=="old-b")
unlink(bundle,recursive=TRUE)
file <- tempfile(fileext=".pdf")
grDevices::pdf(file,width=240/25.4,height=135/25.4)
original_panels <- bbmri_survey_country_panels
bbmri_survey_country_panels <- function(...) list()
empty <- counts[FALSE,c("country","directory_count","so2_count","mucp_count","shared_count")]
empty$so2_percent <- numeric(0)
audit <- bbmri_survey_draw(empty,"so2","bbmri-members",list())
stopifnot(length(audit$countries)==0,length(audit$boxes)==0)
bbmri_survey_country_panels <- original_panels
grDevices::dev.off(); unlink(file)
cat("glyph and collision assertions passed\n")
