#!/usr/bin/env bash
#
#	Horus Binary GQRX Helper Script
#
#   Accepts data from GQRX's UDP output, and passes it into horus_demod.
#

# Check that the horus_demod decoder has been compiled.
FILE=./src/horus_demod
if [ -f "$FILE" ]; then
    echo "Found horus_demod."
else 
    echo "ERROR - $FILE does not exist - have you compiled it yet?"
	exit 1
fi



if [[ $OSTYPE == darwin* ]]; then
    # OSX's netcat utility uses a different, incompatible syntax. Sigh.
    nc -l -u localhost 7355 | ./src/horus_demod -m binary --fsk_lower=100 --fsk_upper=10000 - - | python horusbinary.py --stdin $@
else
    # Start up!
    nc -l -u -p 7355 localhost | ./src/horus_demod -m binary --fsk_lower=100 --fsk_upper=10000 - - | python horusbinary.py --stdin $@
fi