bbmri_map_config <- function() {
  list(
    render_scale = 2,
    standard_bbox = c(
      xmin = -32.4316,
      ymin = 22.0,
      xmax = 56.6895,
      ymax = 72.1009
    ),
    oec_bbox = c(
      xmin = -14.0,
      ymin = 22.0,
      xmax = 56.6895,
      ymax = 67.0
    ),
    standard_crs = 3857,
    oec_crs = "+proj=tmerc +a=6378137 +b=6378137 +lat_ts=0.0 +lon_0=10.0 +lat_0=-10.0 +x_0=0.0 +y_0=0 +k=1.0 +units=m +nadgrids=@null +wktext +no_defs +over",
    export_sizes = list(
      png = list(
        small = c(width = 1200, height = 1018),
        med = c(width = 3000, height = 2544),
        big = c(width = 8002, height = 6786)
      ),
      vector = c(width = 3000, height = 2544)
    ),
    standard_country_labels = c(
      "AT", "BE", "BG", "CH", "CY", "CZ", "DE", "DK", "EE", "ES",
      "FI", "GR", "HU", "IT", "LT", "LV", "MT", "NL", "NO", "PL",
      "SE", "SI", "SK", "TR"
    ),
    standard_label_offsets = data.frame(
      iso_a2 = c("BE", "CH", "CY", "CZ", "GB", "MT", "NL"),
      dx = c(0, 120000, 0, 80000, 0, 0, 0),
      dy = c(20000, 40000, -110000, 0, -320000, -110000, -120000),
      stringsAsFactors = FALSE
    ),
    standard_label_style = list(
      size = 2.35,
      inner_halo_px = 1.0,
      outer_halo_px = 3.0,
      alpha = 0.95
    ),
    standard_iarc_symbol = list(
      halo_size = 3.45,
      observer_size = 2.8,
      observer_stroke = 0.5,
      biobank_size = 1.05,
      biobank_stroke = 0.3
    ),
    sized_biobank_label_style = list(
      size = 0.95,
      alpha = 0.95
    ),
    standard_iarc_label_placement = list(
      hjust = 1,
      vjust = 0,
      nudge_x = -20000,
      nudge_y = 25000
    ),
    standard_country_groups = list(
      member = c(
        "AT", "BE", "BG", "CH", "CZ", "DE", "EE", "ES", "FI", "GR",
        "HU", "IT", "LT", "LV", "MT", "NL", "NO", "PL", "SE", "SI",
        "SK"
      ),
      observer = c("CY", "DK", "QA", "TR")
    ),
    oec_country_groups = list(
      member = c(
        "AT", "BE", "BG", "CH", "CZ", "DE", "EE", "ES", "FI", "GR",
        "HU", "IT", "LT", "LV", "MT", "NL", "NO", "PL", "SE", "SI",
        "SK"
      ),
      observer = c("CY", "DK", "QA", "TR"),
      gray = c(
        "AL", "BA", "BY", "FR", "GB", "HR", "IE", "IL", "IS", "LU",
        "MD", "ME", "MK", "PT", "RO", "RS", "UA"
      )
    ),
    standard_colors = list(
      water = "#ddeeff",
      line = "#226688",
      member = "#0098cc",
      observer = "#7fdfff",
      default_country = "#cccccc",
      biobank = "#FF0066",
      standalone = "#FFCCCC",
      biobank_line = "#813",
      iarc = "#7fdfff"
    ),
    oec_colors = list(
      background = "#ffffff",
      member = "#003674",
      observer = "#7fdfff",
      default_country = "#ffffff",
      gray_country = "#d3d3d3",
      biobank = "#e95713",
      biobank_fill = "#f49b71",
      hq = "#e95713"
    ),
    oec_iarc_symbol = list(
      halo_size = 4.15,
      observer_size = 3.45,
      observer_stroke = 0.5,
      node_size = 1.5,
      node_stroke = 0.55,
      node_dx = -9000,
      node_dy = 7000,
      biobank_size = 0.85,
      biobank_stroke = 0.28,
      biobank_dx = 10000,
      biobank_dy = -8000
    ),
    biobank_size_widths = c(
      "0" = 5,
      "1" = 6,
      "2" = 8,
      "3" = 12,
      "4" = 20,
      "5" = 32,
      "6" = 48,
      "7" = 64,
      "8" = 72
    )
  )
}
