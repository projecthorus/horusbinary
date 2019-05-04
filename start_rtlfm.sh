#!/usr/bin/env sh
echo "Launching horus_demod with rtl_fm in raw IQ mode"
# tune 1600 HZ below expected centre frequency:
rtl_fm -M raw -s 48000 -p 0 -f 434410000 | ./horus_demod -q -m binary - - | python horusbinary.py --stdin
