#!/usr/bin/env sh
nc -l -u localhost 7355 | ./horus_demod -m binary --fsk_lower=100 --fsk_upper=10000 - - | python horusbinary.py --stdin $@
