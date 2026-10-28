idf_component_register(SRCS "main.c" "wheel.c" "display.c" "display_p4.c" "control.c" "crsf.c" "multi.c" "radio.c"
                       INCLUDE_DIRS "."
                       PRIV_REQUIRES esp_timer esp_lcd driver esp_driver_uart esp_driver_gpio esp_driver_rmt nvs_flash)
