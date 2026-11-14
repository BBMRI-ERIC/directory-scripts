# Render a prepared SO2/MuCP map bundle without reading private source questionnaires.
file_arg <- grep("^--file=",commandArgs(trailingOnly=FALSE),value=TRUE)
script_dir <- normalizePath(dirname(sub("^--file=","",file_arg[[1]])),winslash="/",mustWork=TRUE)
source(file.path(script_dir,"map_config.R"))
source(file.path(script_dir,"map_common.R"))
source(file.path(script_dir,"render_bbmri_members_oec_all.R"))
source(file.path(script_dir,"survey_participation_common.R"))

main <- function() {
  args <- bbmri_parse_args(list(bundle="",kind="",overwrite=FALSE))
  bbmri_require_packages(c("ggplot2","sf","cowplot","jsonlite","digest"))
  bundle <- normalizePath(args$bundle,winslash="/",mustWork=TRUE)
  input_path <- file.path(bundle,"input-manifest.json")
  manifest <- jsonlite::fromJSON(input_path,simplifyVector=FALSE)
  if (!identical(manifest$schema_version,1L) || !identical(manifest$kind,args$kind)) stop("Incompatible map input manifest")
  hash <- function(path) digest::digest(file=path,algo="sha256")
  for (name in names(manifest$files)) if (!identical(hash(file.path(bundle,name)),manifest$files[[name]])) stop("Changed map input: ",name)
  root <- dirname(script_dir)
  for(name in names(manifest$renderer_sources)) if(!identical(hash(file.path(root,name)),manifest$renderer_sources[[name]]))
    stop("Renderer/config changed since export; regenerate map inputs: ",name)
  targets <- c("output-manifest.json",unlist(lapply(manifest$figure_keys,function(key) paste0(key,c(".pdf",".png")))))
  if(!isTRUE(args$overwrite) && any(file.exists(file.path(bundle,targets)))) stop("Map outputs exist; use --overwrite")
  stage <- tempfile(pattern=".render-",tmpdir=bundle)
  dir.create(stage)
  on.exit(unlink(stage,recursive=TRUE),add=TRUE)
  counts <- utils::read.csv(file.path(bundle,"country-counts.csv"),stringsAsFactors=FALSE,na.strings="")
  cfg <- bbmri_map_config()
  outputs <- list()
  for(key in manifest$figure_keys) {
    layout <- if(grepl("-oec-",key,fixed=TRUE)) "oec" else "bbmri-members"
    percentage <- endsWith(key,"-percentage")
    diagnostics <- list()
    for(format in c("pdf","png")) {
      path <- file.path(stage,paste0(key,".",format))
      if(format=="pdf") grDevices::pdf(path,width=240/25.4,height=135/25.4,useDingbats=FALSE)
      else grDevices::png(path,width=240,height=135,units="mm",res=300)
      diagnostics[[format]] <- tryCatch(bbmri_survey_draw(counts,args$kind,layout,cfg,percentage,
        list(scope=jsonlite::fromJSON(file.path(bundle,"directory-inventory.json"))$scope,
             unknown_so2=manifest$counts$unknown_country$so2_count,
             unknown_mucp=manifest$counts$unknown_country$mucp_count)),finally=grDevices::dev.off())
    }
    outputs[[key]] <- list(pdf=paste0(key,".pdf"),png=paste0(key,".png"),
      pdf_sha256=hash(file.path(stage,paste0(key,".pdf"))),png_sha256=hash(file.path(stage,paste0(key,".png"))),
      devices=diagnostics)
  }
  output <- list(schema_version=1,canonical_sha256=manifest$canonical_sha256,input_manifest_sha256=hash(input_path),
    counts=manifest$counts,render_spec=manifest$render_spec,outputs=outputs,
    provenance=list(R=R.version.string,packages=lapply(c("ggplot2","sf","cowplot","jsonlite","digest"),
      function(p) as.character(utils::packageVersion(p))),renderer_sources=manifest$renderer_sources,
      basemap=lapply(list.files(bbmri_map_cache_dir(),pattern="\\.zip$",full.names=TRUE),hash)))
  jsonlite::write_json(output,file.path(stage,"output-manifest.json"),auto_unbox=TRUE,pretty=TRUE,
                       digits=17,null="null",na="null")
  bbmri_survey_publish(stage,bundle,targets)
  message("Rendered ",length(outputs)," maps in ",bundle)
}

if(sys.nframe()==0) main()
