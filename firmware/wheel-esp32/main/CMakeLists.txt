set(srcs "main.c" "wheel.c" "display.c" "control.c" "crsf.c" "multi.c" "radio.c")
set(embed "")
if(IDF_TARGET STREQUAL "esp32p4")
    # The 7" dashboard: its fonts (fonts/gen_fonts.sh) and images
    # (design/render/build_assets.py).
    list(APPEND srcs "display_p4.c" "dash_p4.c"
         "fonts/cjk_14.c" "fonts/cjk_16.c" "fonts/cjk_20.c" "fonts/cjk_24.c" "fonts/cjk_32.c"
         "fonts/saira_thin_132.c" "fonts/saira_xl_30.c" "fonts/saira_l_30.c" "fonts/saira_l_15.c"
         "fonts/barlow_58.c" "fonts/barlow_64.c" "fonts/barlow_28.c")
    set(embed "assets/a_bg.bin" "assets/a_arc.bin" "assets/a_tip.bin"
              "assets/b_bg.bin" "assets/b_needle.bin" "assets/b_wheel.bin")
endif()

idf_component_register(SRCS ${srcs}
                       INCLUDE_DIRS "."
                       EMBED_FILES ${embed}
                       PRIV_REQUIRES esp_timer esp_lcd driver esp_driver_uart esp_driver_gpio esp_driver_rmt nvs_flash)
