idf_component_register(SRCS "main.c"
                       REQUIRES driver esp_driver_rmt esp_driver_ledc esp_driver_uart nvs_flash esp_timer)
