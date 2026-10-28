#!/bin/sh
# Regenerates the UI's bitmap fonts.
#
#   fonts/gen_fonts.sh /path/to/fonts
#
# The directory holds (all SIL Open Font License):
#   NotoSansSC-Medium.otf  Chinese, Simplified and Traditional:
#     https://github.com/notofonts/noto-cjk/raw/main/Sans/SubsetOTF/SC/NotoSansSC-Medium.otf
#   Saira-Thin.ttf, Saira-ExtraLight.ttf, Saira-Light.ttf and
#   BarlowCondensed-ExtraBoldItalic.ttf: the dashboards' digits (Google Fonts).
#
# cjk_*: only the non-ASCII characters found in the sources; Latin, digits
# and symbols come from the Montserrat fallback.
# Needs Node (npx lv_font_conv). Only the non-ASCII characters found in the
# sources go in; Latin, digits and symbols come from the Montserrat fallback.
set -e
cd "$(dirname "$0")"
DIR=${1:?usage: gen_fonts.sh /path/to/fonts}
FONT="$DIR/NotoSansSC-Medium.otf"
CHARS=$(python3 -c '
import sys
s = "".join(open(f, encoding="utf-8").read() for f in sys.argv[1:])
print("".join(sorted({c for c in s if ord(c) > 127})))
' ../display_p4.c ../dash_p4.c ../radio.c)
for size in 14 16 20 24 32; do
    npx -y lv_font_conv@1.5.3 --font "$FONT" --symbols "$CHARS" --size $size --bpp 4 --no-compress \
        --format lvgl --lv-include lvgl.h --lv-font-name cjk_$size --lv-fallback lv_font_montserrat_$size \
        -o cjk_$size.c
done
# Dashboard digits and gear letters (dash_p4.c), each only the glyphs it shows.
digits() { # name font size symbols
    npx -y lv_font_conv@1.5.3 --font "$DIR/$2" --symbols "$4" --size $3 --bpp 4 --no-compress \
        --format lvgl --lv-include lvgl.h --lv-font-name $1 -o $1.c
}
digits saira_thin_132 Saira-Thin.ttf 132 "0123456789"
digits saira_xl_30 Saira-ExtraLight.ttf 30 "0123456789"
digits saira_l_30 Saira-Light.ttf 30 "RN123"
digits barlow_58 BarlowCondensed-ExtraBoldItalic.ttf 58 "RN123"
digits barlow_64 BarlowCondensed-ExtraBoldItalic.ttf 64 "0123456789"
digits barlow_28 BarlowCondensed-ExtraBoldItalic.ttf 28 "0123456789LR°"
echo "$(printf %s "$CHARS" | wc -m | tr -d ' ') characters"
