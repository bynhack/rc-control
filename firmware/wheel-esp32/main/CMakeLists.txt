idf_component_register(SRCS "main.c" "wheel.c" "display.c"
                       INCLUDE_DIRS "."
                       PRIV_REQUIRES esp_timer esp_lcd driver)
