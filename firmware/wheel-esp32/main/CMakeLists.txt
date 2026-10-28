idf_component_register(SRCS "main.c" "wheel.c" "display.c" "display_p4.c" "control.c" "crsf.c" "multi.c" "radio.c"
                       "fonts/cjk_14.c" "fonts/cjk_16.c" "fonts/cjk_20.c" "fonts/cjk_24.c" "fonts/cjk_32.c" "fonts/gear_160.c"
                       INCLUDE_DIRS "."
                       PRIV_REQUIRES esp_timer esp_lcd driver esp_driver_uart esp_driver_gpio esp_driver_rmt nvs_flash)
