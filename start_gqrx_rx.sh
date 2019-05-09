#!/usr/bin/env sh
nc -l -u localhost 7355 | ./horus_demod -m binary - - | python horusbinary.py --stdin $@
