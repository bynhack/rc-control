idf_component_register(
    SRCS "main.c" "power.c" "crsf.c" "drive.c" "battery.c" "ir.c" "imu.c" "led.c" "settings.c" "console.c"
    INCLUDE_DIRS "."
    REQUIRES driver esp_adc esp_driver_rmt esp_driver_ledc esp_driver_uart esp_driver_i2c esp_driver_gpio
             esp_driver_usb_serial_jtag nvs_flash app_update esp_timer)
