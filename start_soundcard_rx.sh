#!/usr/bin/env sh
sox -d -r 48k -c 1 -t s16 - | ./horus_demod -m binary - - | python horusbinary.py --stdin $@
