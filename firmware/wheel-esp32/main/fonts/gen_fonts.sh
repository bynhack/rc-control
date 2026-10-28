#!/bin/sh
# Regenerates the Chinese subset fonts (cjk_*.c) from the text the UI uses.
#
#   fonts/gen_fonts.sh /path/to/NotoSansSC-Medium.otf
#
# Font: Noto Sans SC (SIL Open Font License); it covers the Traditional
# characters too:
# https://github.com/notofonts/noto-cjk/raw/main/Sans/SubsetOTF/SC/NotoSansSC-Medium.otf
# Needs Node (npx lv_font_conv). Only the non-ASCII characters found in the
# sources go in; Latin, digits and symbols come from the Montserrat fallback.
set -e
cd "$(dirname "$0")"
FONT=${1:?usage: gen_fonts.sh NotoSansSC-Medium.otf}
CHARS=$(python3 -c '
import sys
s = "".join(open(f, encoding="utf-8").read() for f in sys.argv[1:])
print("".join(sorted({c for c in s if ord(c) > 127})))
' ../display_p4.c ../radio.c)
for size in 14 16 20 24 32; do
    npx -y lv_font_conv@1.5.3 --font "$FONT" --symbols "$CHARS" --size $size --bpp 4 --no-compress \
        --format lvgl --lv-include lvgl.h --lv-font-name cjk_$size --lv-fallback lv_font_montserrat_$size \
        -o cjk_$size.c
done
echo "$(printf %s "$CHARS" | wc -m | tr -d ' ') characters"
