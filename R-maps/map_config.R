bbmri_map_config <- function() {
  scale_export_sizes <- function(small, med, big, scale = 2) {
    list(
      png = list(
        small = c(width = small[[1]] * scale, height = small[[2]] * scale),
        med = c(width = med[[1]] * scale, height = med[[2]] * scale),
        big = c(width = big[[1]] * scale, height = big[[2]] * scale)
      ),
      vector = c(width = med[[1]] * scale, height = med[[2]] * scale)
    )
  }

  make_export_sizes <- function(small, med, big, vector = med) {
    list(
      png = list(
        small = c(width = small[[1]], height = small[[2]]),
        med = c(width = med[[1]], height = med[[2]]),
        big = c(width = big[[1]], height = big[[2]])
      ),
      vector = c(width = vector[[1]], height = vector[[2]])
    )
  }

  # Seed positions are the geographic centers of the countries.
  # They are intended as a human-editable starting point for manual per-size tuning.
  so_global_bar_position_seed <- list(
    DE = c(lon = 10.392360, lat = 51.218588),
    IT = c(lon = 12.007595, lat = 42.954625),
    ES = c(lon = -3.632857, lat = 40.348739),
    PL = c(lon = 19.380227, lat = 52.187936),
    NL = c(lon = 5.357191, lat = 52.186263),
    GR = c(lon = 22.970991, lat = 39.108193),
    BE = c(lon = 4.636528, lat = 50.643486),
    CZ = c(lon = 15.310535, lat = 49.741379),
    HU = c(lon = 19.404981, lat = 47.175034),
    SE = c(lon = 17.002863, lat = 63.415060),
    AT = c(lon = 14.138867, lat = 47.595876),
    CH = c(lon = 8.216605, lat = 46.804176),
    BG = c(lon = 25.220918, lat = 42.780797),
    DK = c(lon = 10.043369, lat = 55.984666),
    FI = c(lon = 26.306482, lat = 64.905896),
    NO = c(lon = 16.777994, lat = 73.309406),
    LT = c(lon = 23.883398, lat = 55.341185),
    LV = c(lon = 24.905259, lat = 56.861583),
    SI = c(lon = 14.810122, lat = 46.119189),
    EE = c(lon = 25.534850, lat = 58.681223),
    QA = c(lon = 51.187645, lat = 25.314758),
    CY = c(lon = 32.990284, lat = 34.915276),
    MT = c(lon = 14.404172, lat = 35.920902)
  )

  list(
    render_scale = 2,
    marker_width_scale = 8.7,
    standard_bbox = c(
      xmin = -32.4316,
      ymin = 22.0,
      xmax = 56.6895,
      ymax = 72.1009
    ),
    classic_europe_bbox = c(
      xmin = -32.4316,
      ymin = 28.9985,
      xmax = 56.6895,
      ymax = 72.1009
    ),
    global_bbox = c(
      xmin = -180.0,
      ymin = -50.0,
      xmax = 180.0,
      ymax = 78.0
    ),
    oec_bbox = c(
      xmin = -32.4316,
      ymin = 27.0,
      xmax = 56.6895,
      ymax = 72.1009
    ),
    oec_geographic_exclusions = list(
      atlantic_islands = c(
        xmin = -32.5,
        ymin = 20.0,
        xmax = -10.5,
        ymax = 42.0
      ),
      arctic_islands = c(
        xmin = 5.0,
        ymin = 72.0,
        xmax = 40.0,
        ymax = 90.0
      )
    ),
    oec_content_margins = c(
      left = 0.025,
      right = 0.025,
      bottom = 0.025,
      top = 0.025
    ),
    oec_content_trim_bias = c(
      x = 0.50,
      y = 0.50
    ),
    oec_main_north_cap_lat = 71.20,
    oec_basemap_target_margins = c(
      left = 0.095,
      right = 0.075,
      bottom = 0.045,
      top = 0.030
    ),
    oec_basemap_fit_iterations = 2,
    oec_basemap_fit_damping = 0.85,
    oec_canvas = list(
      main_x = 0.02,
      main_y = 0.02,
      main_width = 0.96,
      main_height = 0.96
    ),
    standard_crs = 3857,
    oec_crs = "+proj=tmerc +a=6378137 +b=6378137 +lat_ts=0.0 +lon_0=10.0 +lat_0=-10.0 +x_0=0.0 +y_0=0 +k=1.0 +units=m +nadgrids=@null +wktext +no_defs +over",
    export_sizes = scale_export_sizes(
      small = c(600, 509),
      med = c(1500, 1272),
      big = c(4001, 3393)
    ),
    oec_export_sizes = make_export_sizes(
      small = c(1920, 1120),
      med = c(4800, 2800),
      big = c(12840, 7490),
      vector = c(2400, 1400)
    ),
    global_export_sizes = scale_export_sizes(
      small = c(918, 509),
      med = c(2300, 1272),
      big = c(6140, 3393)
    ),
    crc_export_sizes = scale_export_sizes(
      small = c(918, 509),
      med = c(2300, 1272),
      big = c(6140, 3393)
    ),
    standard_country_labels = c(
      "AT", "BE", "BG", "CH", "CY", "CZ", "DE", "DK", "EE", "ES",
      "FI", "GR", "HU", "IT", "LT", "LV", "MT", "NL", "NO", "PL",
      "QA",
      "SE", "SI", "SK", "TR"
    ),
    fedplat_country_labels = c(
      "AT", "CH", "CZ", "DE", "FI", "GB", "IT", "LV", "MT", "QA", "SE"
    ),
    standard_label_offsets = data.frame(
      iso_a2 = c("BE", "CH", "CY", "CZ", "DE", "GB", "MT", "NL", "NO"),
      dx = c(0, 120000, 0, 80000, 120000, 0, 0, -120000, 0),
      dy = c(20000, 40000, -110000, 0, 30000, -320000, -110000, -120000, -4000000),
      stringsAsFactors = FALSE
    ),
    standard_small_label_offsets = data.frame(
      iso_a2 = c("AT", "CH", "CZ", "DE", "HU", "NO", "QA", "SI"),
      dx = c(-90000, -140000, 130000, -140000, 120000, 0, 80000, 100000),
      dy = c(90000, 90000, -20000, 110000, -30000, -200000, 30000, -80000),
      stringsAsFactors = FALSE
    ),
    fedplat_label_offsets = data.frame(
      iso_a2 = c("BE", "CH", "CZ", "GB", "NL"),
      dx = c(0, 120000, 80000, 0, 0),
      dy = c(20000, 40000, 0, -320000, -120000),
      stringsAsFactors = FALSE
    ),
    standard_label_style = list(
      size = 2.35,
      inner_halo_px = 1.0,
      outer_halo_px = 3.0,
      alpha = 0.95
    ),
    country_label_scale_by_output = c(
      small = 0.6,
      med = 1.0,
      big = 4.0,
      vector = 1.0
    ),
    country_label_halo_scale_by_output = c(
      small = 0.5,
      med = 1.0,
      big = 4.0,
      vector = 1.0
    ),
    symbol_scale_by_output = c(
      small = 1.0,
      med = 1.0,
      big = 3.0,
      vector = 1.0
    ),
    line_scale_by_output = c(
      small = 1.0,
      med = 1.0,
      big = 2.0,
      vector = 1.0
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
      alpha = 0.95,
      colour = "#4a4a4a"
    ),
    sized_marker_scale_by_output = c(
      small = 0.5,
      med = 1.0,
      big = 2.0,
      vector = 1.0
    ),
    sized_marker_min_by_output = c(
      small = 10 / 17,
      med = 5 / 17,
      big = 10 / 17,
      vector = 5 / 17
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
    fedplat_country_groups = list(
      member = c("BE", "CH", "FI", "GR", "LT", "NL", "NO", "PL", "BG", "HU", "SI"),
      observer = c("DK", "TR", "QA"),
      fedplat = c("AT", "CZ", "DE", "EE", "IT", "MT", "CY", "LV", "SE")
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
      iarc = "#7fdfff",
      geo_line = "#226688",
      glacier = "#ffffff"
    ),
    quality_colors = list(
      eric = "#f36f21",
      accredited = "#004685",
      other = "#6f7687",
      line = "#004685"
    ),
    fedplat_colors = list(
      member = "#0098cc",
      observer = "#7fdfff",
      fedplat = "#05B10F",
      default_country = "#cccccc",
      locator = "#ce7e00",
      finder = "#c90076",
      point_line = "#813"
    ),
    crc_colors = list(
      cohort = "#FF0066",
      cohort_line = "#813",
      standalone = "#FFCCCC",
      imaging = "#00CC00"
    ),
    rd_colors = list(
      non_member = "#00AA00",
      member = "#FF0066"
    ),
    so_colors = list(
      lead = "#E66101",
      contributor = "#5E3C99",
      base_member = "#0098cc",
      base_observer = "#7fdfff",
      base_nonmember = "#cccccc",
      bar_border = "#333333",
      bar_background = "#ffffff"
    ),
    so_bar_style = list(
      cluster_width_frac = 0.18,
      bar_width_frac = 0.015,
      bar_gap_frac = 0.004,
      unit_height_frac = 0.020,
      baseline_offset_frac = 0.010,
      outline_linewidth = 0.18,
      alpha = 0.88
    ),
    so_global_bar_style = list(
      width_scale = 0.42,
      height_scale = 0.80,
      show_slots = FALSE,
      resolve_positions = FALSE
    ),
    so_global_bar_positions = list(
      small = so_global_bar_position_seed,
      med = list(
    AT = c(lon = 14.99, lat = 43.90),
    BE = c(lon = 1.50, lat = 48.64),
    BG = c(lon = 30.28, lat = 43.87),
    CH = c(lon = 8.216605, lat = 46.804176),
    CY = c(lon = 32.990284, lat = 34.915276),
    CZ = c(lon = 16.80, lat = 49.88),
    DE = c(lon = 10.00, lat = 51.218588),
    DK = c(lon = 10.00, lat = 56.00),
    EE = c(lon = 29.31, lat = 59.14),
    ES = c(lon = -3.632857, lat = 40.348739),
    FI = c(lon = 26.306482, lat = 64.905896),
    GR = c(lon = 22.970991, lat = 39.108193),
    HU = c(lon = 25.58, lat = 48.00),
    IT = c(lon = 6.99, lat = 39.30),
    LT = c(lon = 27.82, lat = 53.71),
    LV = c(lon = 21.4, lat = 57.80),
    MT = c(lon = 14.404172, lat = 33.62),
    NL = c(lon = 2.00, lat = 54.48),
    NO = c(lon = 8.70, lat = 60.79),
    PL = c(lon = 18.16, lat = 54.87),
    QA = c(lon = 51.187645, lat = 25.314758),
    SE = c(lon = 17.002863, lat = 63.415060),
    SI = c(lon = 14.90, lat = 40.03)
  ),
      big = so_global_bar_position_seed
    ),
    oec_colors = list(
      background = "#ffffff",
      member = "#003674",
      observer = "#7fdfff",
      default_country = "#ffffff",
      country_line = "#d5d5d5",
      gray_country = "#d3d3d3",
      biobank = "#e95713",
      biobank_fill = "#f49b71",
      hq = "#e95713"
    ),
    fedplat_label_style = list(
      size = 1.4,
      alpha = 0.95,
      colour = "#4a4a4a"
    ),
    fedplat_legend_box = list(
      x = 0.03,
      y = 0.05,
      width = 0.22,
      height = 0.13
    ),
    quality_legend_box = list(
      x = 0.03,
      y = 0.05,
      width = 0.24,
      height = 0.18
    ),
    quality_marker_style = list(
      collection_width = 10,
      biobank_width = 50,
      alpha_collection = 0.8,
      alpha_biobank = 0.5
    ),
    crc_marker_style = list(
      main_alpha = 0.8,
      imaging_alpha = 0.9,
      imaging_width = 12,
      cohort_min_width = 7,
      cohort_high_base = 9,
      cohort_high_slope = 0.10
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
    oec_insets = list(
      list(
        id = "qa",
        label = "Qatar",
        mask_country_codes = c("QA"),
        require_node = TRUE,
        bbox = c(
          xmin = 49.625,
          ymin = 24.10,
          xmax = 52.525,
          ymax = 26.90
        ),
        placement = list(
          x = 0.850,
          y = 0.070,
          width = 0.036,
          height = 0.057
        ),
        connector = list(
          source_node_type = "HQ",
          source_name = NA_character_,
          source_dx = 0.0,
          source_dy = 0.0,
          target_x = 0.1,
          target_y = 0.5,
          linewidth = 0.12
        ),
        frame = list(
          border_colour = "#e95713",
          border_linewidth = 0.8,
          background_fill = "#fbfdff"
        )
      )
    ),
    biobank_size_widths = c(
      "0" = 5,
      "1" = 6,
      "2" = 10,
      "3" = 18,
      "4" = 36,
      "5" = 64,
      "6" = 96,
      "7" = 128,
      "8" = 144
    )
  )
}
