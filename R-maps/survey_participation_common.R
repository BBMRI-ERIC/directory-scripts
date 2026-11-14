# Physical-device glyph geometry shared by both survey participation map layouts.

bbmri_survey_boxes_overlap <- function(a, b, gap = 0.5) {
  a[[1]] < b[[2]] + gap && a[[2]] > b[[1]] - gap &&
    a[[3]] < b[[4]] + gap && a[[4]] > b[[3]] - gap
}

bbmri_survey_text_width <- function(text, size = 9) {
  grid::convertWidth(grid::grobWidth(grid::textGrob(text,
    gp = grid::gpar(fontsize = size, fontfamily = "sans"))), "mm", valueOnly = TRUE)
}

bbmri_survey_glyphs <- function(counts, kind, scale, device) {
  if (!kind %in% c("so2", "mucp") || !is.finite(scale) || scale <= 0) stop("Invalid glyph kind/scale")
  lapply(seq_len(nrow(counts)), function(i) {
    row <- counts[i,,drop=FALSE]
    d <- row$directory_count; s <- row$so2_count; m <- row$mucp_count; b <- row$shared_count
    if (any(!is.finite(c(d,s,m,b))) || min(d,s,m,b) < 0 || b > min(s,m)) stop("Invalid country participation counts")
    x <- if ("x" %in% names(row)) row$x else device[["width"]]/2
    y <- if ("y" %in% names(row)) row$y else device[["height"]]/2
    offsets <- if (kind == "mucp") c(-3.2,3.2) else 0
    bars <- list()
    add <- function(offset, lower, upper, fill, role) {
      bars[[length(bars)+1L]] <<- data.frame(xmin=offset-1.3,xmax=offset+1.3,
        lower=lower,upper=upper,fill=fill,role=role,stringsAsFactors=FALSE)
    }
    if (kind == "mucp") {
      add(offsets[[1]], b, m, "#008568", "mucp")
      add(offsets[[1]], 0, b, "#d55e00", "shared")
    }
    sx <- tail(offsets,1)
    add(sx, if (kind == "mucp") b else 0, s, "#326aab", "so2")
    if (kind == "mucp") add(sx,0,b,"#d55e00","shared")
    add(sx,0,d,NA_character_,"directory")
    labels <- data.frame(x=sx,y=max(d,s)*scale+3,text=paste(s,"of",d),stringsAsFactors=FALSE)
    if (kind == "mucp") {
      labels <- rbind(labels,data.frame(x=offsets[[1]],y=m*scale+3,text=as.character(m)),
        data.frame(x=offsets,y=-3,text=c("M","S")))
      # A small total may extend horizontally into its taller neighbouring bar.
      for(j in 1:2) {
        half <- (bbmri_survey_text_width(labels$text[[j]])+1)/2
        neighbours <- vapply(bars,function(bar)
          labels$x[[j]]-half < bar$xmax && labels$x[[j]]+half > bar$xmin,logical(1))
        top <- max(vapply(bars[neighbours],function(bar) bar$upper*scale,numeric(1)))
        labels$y[[j]] <- max(labels$y[[j]],top+3)
      }
      # Put the two totals on separate levels if their measured extents intersect.
      if (diff(offsets) < (bbmri_survey_text_width(labels$text[[1]]) +
                          bbmri_survey_text_width(labels$text[[2]])+2)/2 + 0.5 &&
          abs(labels$y[[1]]-labels$y[[2]]) < 4) labels$y[[1]] <- max(labels$y[1:2])+4
    }
    labels <- rbind(labels,data.frame(x=0,y=if (kind=="mucp") -7 else -4,text=row$country))
    widths <- vapply(labels$text,bbmri_survey_text_width,numeric(1))
    box <- c(min(labels$x-widths/2,-5)-1,max(labels$x+widths/2,5)+1,
             min(labels$y)-2.1,max(labels$y)+2.1)
    list(country=row$country,anchor=c(x,y),x=x,y=y,box=box+c(x,x,y,y),
         bars=do.call(rbind,bars),labels=labels,scale=scale,
         outside=isTRUE(row$outside),bounds=if (isTRUE(row$outside)) c(196,240,15,122) else c(0,195,15,122))
  })
}

bbmri_survey_publish <- function(stage,bundle,targets,rename=file.rename) {
  # Backups live outside stage so its owner's cleanup cannot delete recovery data.
  backup <- tempfile(pattern=".map-backup-",tmpdir=bundle)
  if(!dir.create(backup)) stop("Cannot create map backup directory")
  moved <- character(); saved <- character(); success <- FALSE
  on.exit({
    restored <- TRUE
    if(!success) {
      unlink(file.path(bundle,moved))
      for(name in saved) if(!rename(file.path(backup,name),file.path(bundle,name))) restored <- FALSE
    }
    if(success || restored) unlink(backup,recursive=TRUE)
    else warning("Map rollback incomplete; preserved original outputs in ",backup)
  })
  for(name in targets) {
    target <- file.path(bundle,name)
    if(file.exists(target)) {
      if(!rename(target,file.path(backup,name))) stop("Cannot back up map output: ",target)
      saved <- c(saved,name)
    }
    if(!rename(file.path(stage,name),target)) stop("Cannot publish map output: ",target)
    moved <- c(moved,name)
  }
  success <- TRUE
  invisible(NULL)
}

bbmri_place_survey_glyphs <- function(groups, panels, reserved_boxes) {
  if (!length(groups)) return(groups)
  result <- list()
  order <- order(-vapply(groups,function(g) diff(g$box[3:4]),numeric(1)),
                 vapply(groups,function(g) g$country,character(1)))
  for (idx in order) {
    group <- groups[[idx]]
    relative <- group$box-c(group$x,group$x,group$y,group$y)
    bounds <- group$bounds
    if (is.null(bounds)) bounds <- c(0,panels[["width"]],0,panels[["height"]])
    candidates <- expand.grid(x=seq(bounds[[1]]+1,bounds[[2]]-1,by=2),
                              y=seq(bounds[[3]]+1,bounds[[4]]-1,by=2))
    candidates <- rbind(data.frame(x=group$x,y=group$y),candidates)
    placement_order <- if(isTRUE(group$outside)) order(-candidates$y,candidates$x) else
      order((candidates$x-group$x)^2+(candidates$y-group$y)^2,candidates$y,candidates$x)
    candidates <- candidates[placement_order,,drop=FALSE]
    found <- FALSE
    obstacles <- c(reserved_boxes,lapply(result,function(g) g$box))
    for (j in seq_len(nrow(candidates))) {
      x <- candidates$x[[j]]; y <- candidates$y[[j]]
      box <- relative+c(x,x,y,y)
      if (box[[1]] < bounds[[1]] || box[[2]] > bounds[[2]] ||
          box[[3]] < bounds[[3]] || box[[4]] > bounds[[4]]) next
      if (any(vapply(obstacles,function(other) bbmri_survey_boxes_overlap(box,other),logical(1)))) next
      group$x <- x; group$y <- y; group$box <- box
      result[[length(result)+1L]] <- group
      found <- TRUE
      break
    }
    if (!found) stop("Cannot place country glyph without overlap: ",group$country,
                      ". Review layout; no maps published.")
  }
  result[order(vapply(result,function(g) g$country,character(1)))]
}

bbmri_survey_valid_countries <- function(countries) {
  # Legacy Natural Earth rings may be unclosed; GEOS cannot repair them directly.
  close_ring <- function(ring) {
    if(!is.matrix(ring) || nrow(ring)<3 || any(!is.finite(ring)))
      stop("Invalid country polygon ring in survey basemap")
    if(!all(ring[1,]==ring[nrow(ring),])) ring <- rbind(ring,ring[1,,drop=FALSE])
    ring
  }
  geometry <- lapply(sf::st_geometry(countries),function(shape) {
    if(inherits(shape,"MULTIPOLYGON"))
      sf::st_multipolygon(lapply(shape,function(polygon) lapply(polygon,close_ring)),dim=class(shape)[[1]])
    else if(inherits(shape,"POLYGON")) sf::st_polygon(lapply(shape,close_ring),dim=class(shape)[[1]])
    else stop("Unsupported country geometry in survey basemap")
  })
  sf::st_geometry(countries) <- sf::st_sfc(geometry,crs=sf::st_crs(countries))
  sf::st_make_valid(countries)
}

bbmri_survey_country_panels <- function(layout, cfg, canvas_mm) {
  bbmri_require_packages(c("ggplot2","sf","cowplot"))
  countries <- bbmri_survey_valid_countries(bbmri_load_countries())
  oec <- identical(layout,"oec")
  crs <- if (oec) cfg$oec_crs else cfg$standard_crs
  bbox <- if (oec) cfg$oec_bbox else cfg$standard_bbox
  countries <- if (oec) bbmri_assign_oec_country_fill(countries,cfg) else bbmri_assign_standard_country_fill(countries,cfg)
  insets <- if (oec) cfg$oec_insets else list()
  inset_codes <- unique(unlist(lapply(insets,function(inset) inset$mask_country_codes)))
  main <- countries[!countries$iso_a2 %in% inset_codes,,drop=FALSE]
  projected_bbox <- NULL
  if(oec) {
    visible <- unique(unlist(cfg$oec_country_groups[c("member","observer","gray")]))
    main <- main[main$iso_a2 %in% visible,,drop=FALSE]
    for(exclusion in cfg$oec_geographic_exclusions) main <- bbmri_exclude_bbox(main,exclusion)
    main <- bbmri_clip_to_projected_bbox(main,bbox,crs)
    content <- sf::st_bbox(sf::st_transform(main,sf::st_crs(crs)))
    if(!is.null(cfg$oec_main_north_cap_lat) && is.finite(cfg$oec_main_north_cap_lat))
      content[["ymax"]] <- min(content[["ymax"]],bbmri_projected_parallel_y_cap(cfg$oec_main_north_cap_lat,bbox,crs))
    projected_bbox <- bbmri_expand_projected_bbox_to_aspect(
      bbmri_expand_projected_bbox(content,cfg$oec_content_margins),195/101,cfg$oec_content_trim_bias)
  } else main <- bbmri_crop_to_bbox(main,bbox)
  panels <- list(list(id="main",countries=main,bbox=bbox,crs=crs,box=c(0,18,195,101),
                      projected_bbox=projected_bbox,frame=NULL))
  for (inset in insets) {
    bbmri_oec_validate_inset_cfg(inset,countries)
    selected <- bbmri_clip_to_bbox(bbmri_crop_to_bbox(countries,inset$bbox),inset$bbox)
    if (!nrow(selected)) stop("Empty survey map inset: ",inset$id)
    p <- inset$placement
    projected <- bbmri_projected_bbox(inset$bbox,crs)
    fitted <- bbmri_fit_box_to_aspect(p$x,p$y,p$width,p$height,
      (projected[["xmax"]]-projected[["xmin"]])/(projected[["ymax"]]-projected[["ymin"]]),195/101)
    panels[[length(panels)+1L]] <- list(id=inset$id,countries=selected,bbox=inset$bbox,crs=crs,
      box=c(fitted$x*195,18+fitted$y*101,fitted$width*195,fitted$height*101),label=inset$label,
      projected_bbox=NULL,frame=inset$frame)
  }
  panels
}

bbmri_survey_panel_plot <- function(panel, cfg, percentage, counts) {
  countries <- panel$countries
  if (percentage) {
    maximum <- max(c(100,counts$so2_percent),na.rm=TRUE)
    values <- counts$so2_percent[match(countries$iso_a2,counts$country)]
    palette <- grDevices::colorRampPalette(c("#f0f9e8","#006d2c"))(101)
    countries$fill_group <- ifelse(is.na(values),"#bdbdbd",palette[pmin(101,1+floor(values/maximum*100))])
  }
  empty <- sf::st_sf(geometry=sf::st_sfc(crs=4326))
  if (identical(panel$crs,cfg$oec_crs)) {
    bbmri_oec_panel_plot(countries,empty,empty,empty,cfg,panel$bbox,draw_node_lines=FALSE,
      projected_bbox=panel$projected_bbox,frame=panel$frame,
      line_scale=bbmri_line_scale_for_output(cfg,"med"))
  } else {
    ggplot2::ggplot()+ggplot2::geom_sf(data=countries,ggplot2::aes(fill=fill_group),
      colour="white",linewidth=0.15)+ggplot2::scale_fill_identity()+
      bbmri_coord_sf(panel$bbox,panel$crs)+bbmri_void_theme(cfg$standard_colors$water)
  }
}

bbmri_survey_anchor_data <- function(panel,cfg,layout,country_codes) {
  if(identical(layout,"bbmri-members")) bbmri_country_label_df(
    panel$countries,cfg,panel$crs,label_codes=country_codes)
  else bbmri_country_anchor_df(panel$countries,panel$crs,label_codes=country_codes)
}

bbmri_survey_draw <- function(counts,kind,layout,cfg,percentage=FALSE,audit=list()) {
  device <- c(width=240,height=135)
  panels <- bbmri_survey_country_panels(layout,cfg,device)
  anchors <- data.frame(country=counts$country,x=rep(218,nrow(counts)),y=rep(100,nrow(counts)),
                        outside=rep(TRUE,nrow(counts)),stringsAsFactors=FALSE)
  grid::grid.newpage()
  for (panel in panels) {
    plot <- bbmri_survey_panel_plot(panel,cfg,percentage,counts)
    box <- panel$box
    spec <- bbmri_oec_panel_spec(plot)
    inner <- bbmri_resolve_plot_panel_box(plot,box[[3]]/25.4,box[[4]]/25.4)
    grid::pushViewport(grid::viewport(x=grid::unit(box[[1]],"mm"),y=grid::unit(box[[2]],"mm"),
      width=grid::unit(box[[3]],"mm"),height=grid::unit(box[[4]],"mm"),just=c("left","bottom")))
    grid::grid.draw(ggplot2::ggplotGrob(plot))
    grid::popViewport()
    points <- bbmri_survey_anchor_data(panel,cfg,layout,counts$country)
    for (i in seq_len(nrow(points))) {
      idx <- match(points$iso_a2[[i]],anchors$country)
      if (is.na(idx)) next
      npc <- bbmri_oec_projected_xy_to_npc(c(points$x[[i]],points$y[[i]]),spec)
      if (any(npc < 0 | npc > 1)) next
      anchors$x[[idx]] <- box[[1]]+(inner$x+npc[[1]]*inner$width)*box[[3]]
      anchors$y[[idx]] <- box[[2]]+(inner$y+npc[[2]]*inner$height)*box[[4]]
      anchors$outside[[idx]] <- FALSE
    }
  }
  counts <- merge(counts,anchors,by="country",sort=FALSE)
  maximum <- max(c(1,counts$directory_count,counts$so2_count,if (kind=="mucp") counts$mucp_count else 0))
  groups <- bbmri_survey_glyphs(counts,kind,28/maximum,device)
  if (percentage) for (i in seq_along(groups)) {
    group <- groups[[i]]; row <- counts[counts$country==group$country,,drop=FALSE]
    text <- paste0(group$country," ",if(is.na(row$so2_percent)) "N/A" else paste0(round(row$so2_percent),"%"))
    width <- bbmri_survey_text_width(text)
    group$bars <- group$bars[FALSE,,drop=FALSE]
    group$labels <- data.frame(x=0,y=0,text=text)
    group$box <- c(group$x-width/2-1,group$x+width/2+1,group$y-2.5,group$y+2.5)
    groups[[i]] <- group
  }
  reserved <- list(c(0,240,0,15),c(0,240,122,135))
  if(any(anchors$outside)) reserved[[length(reserved)+1L]] <- c(196,240,116,122)
  # Insets are geographic panels, not places where neighbouring country's bars may land.
  if (length(panels)>1) for (p in panels[-1]) reserved[[length(reserved)+1L]] <-
    c(p$box[[1]],p$box[[1]]+p$box[[3]],p$box[[2]],p$box[[2]]+p$box[[4]])
  placed <- bbmri_place_survey_glyphs(groups,device,reserved)
  if(any(anchors$outside)) grid::grid.text("Outside extent",x=grid::unit(218,"mm"),y=grid::unit(119,"mm"),
    gp=grid::gpar(fontsize=9,fontfamily="sans",fontface="bold"))
  for (g in placed) {
    if (!g$outside && sum((g$anchor-c(g$x,g$y))^2)>4) grid::grid.lines(
      x=grid::unit(c(g$anchor[[1]],g$x),"mm"),y=grid::unit(c(g$anchor[[2]],g$y),"mm"),
      gp=grid::gpar(col="#55555580",lwd=0.5))
    for (i in seq_len(nrow(g$bars))) {
      r <- g$bars[i,,drop=FALSE]
      grid::grid.rect(x=grid::unit(g$x+(r$xmin+r$xmax)/2,"mm"),
        y=grid::unit(g$y+(r$lower+r$upper)*g$scale/2,"mm"),
        width=grid::unit(r$xmax-r$xmin,"mm"),height=grid::unit((r$upper-r$lower)*g$scale,"mm"),
        gp=grid::gpar(fill=r$fill,col=if(r$role=="directory") "#222222" else NA,lwd=0.65))
    }
    for (i in seq_len(nrow(g$labels))) {
      x <- grid::unit(g$x+g$labels$x[[i]],"mm")
      y <- grid::unit(g$y+g$labels$y[[i]],"mm")
      grid::grid.rect(x=x,y=y,width=grid::unit(bbmri_survey_text_width(g$labels$text[[i]])+1,"mm"),
        height=grid::unit(3.8,"mm"),gp=grid::gpar(fill="#FFFFFFE6",col=NA))
      grid::grid.text(g$labels$text[[i]],x=x,y=y,
        gp=grid::gpar(fontsize=9,fontfamily="sans",col="#111111"))
    }
  }
  title <- if(percentage) "SO2 responses relative to Directory inventory (%)" else
    if(kind=="so2") "SO2 responses and Directory inventory" else "MuCP and SO2 survey participation"
  grid::grid.text(paste(title,"-",layout),x=grid::unit(4,"mm"),y=grid::unit(130,"mm"),just="left",
    gp=grid::gpar(fontsize=12,fontfamily="sans",fontface="bold"))
  if (percentage) {
    top <- max(c(100,counts$so2_percent),na.rm=TRUE)
    colours <- grDevices::colorRampPalette(c("#f0f9e8","#006d2c"))(30)
    for(i in seq_along(colours)) grid::grid.rect(x=grid::unit(10+i*1.5,"mm"),y=grid::unit(9,"mm"),
      width=grid::unit(1.6,"mm"),height=grid::unit(3,"mm"),gp=grid::gpar(fill=colours[[i]],col=NA))
    legend <- paste0("0 to ",round(top),"%; grey/N/A: no denominator. Includes unresolved respondents.")
  } else legend <- if(kind=="so2") "Blue: SO2 respondents. Outline: Directory biobanks. Includes unresolved respondents." else
    "M: MuCP (green); S: SO2 (blue); orange: confirmed shared responses; outline: Directory."
  grid::grid.text(legend,x=grid::unit(if(percentage) 62 else 4,"mm"),y=grid::unit(9,"mm"),just="left",
    gp=grid::gpar(fontsize=8,fontfamily="sans"))
  outside <- paste(anchors$country[anchors$outside],collapse=", ")
  notes <- paste0("Inventory: ",audit$scope %||% "unknown","; country unknown: SO2 ",
    audit$unknown_so2 %||% 0," / MuCP ",audit$unknown_mucp %||% 0,
    if(nzchar(outside)) paste0("; outside-extent callouts: ",outside) else "")
  grid::grid.text(paste(strwrap(notes,width=150),collapse="\n"),x=grid::unit(4,"mm"),y=grid::unit(3,"mm"),
    just="left",gp=grid::gpar(fontsize=8,fontfamily="sans"))
  list(boxes=lapply(placed,function(g) unname(g$box)),collision_count=0,
       reserved_boxes=reserved,
       countries=as.list(vapply(placed,function(g) g$country,character(1))))
}

`%||%` <- function(a,b) if(is.null(a)) b else a
