idf_component_register(SRCS "main.c" "ir_decode.c" "laps.c"
                       REQUIRES esp_driver_gpio esp_driver_ledc esp_driver_usb_serial_jtag esp_timer)
