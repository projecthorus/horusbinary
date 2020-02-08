#!/usr/bin/env bash
#
#	Horus Binary Sound Card Helper Script
#
#   Receive audio from a sound card input, and pass into horus_demod.
#
sox -d -r 48k -c 1 -t s16 - | ./src/horus_demod -m binary --fsk_lower=100 --fsk_upper=4000 - - | python horusbinary.py --stdin $@
