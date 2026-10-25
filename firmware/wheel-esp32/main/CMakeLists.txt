idf_component_register(SRCS "main.c" "wheel.c" "display.c" "control.c" "crsf.c"
                       INCLUDE_DIRS "."
                       PRIV_REQUIRES esp_timer esp_lcd driver esp_driver_uart esp_driver_gpio)
