#!/usr/bin/env bash
#
#	Dual RTTY / Horus Binary Decoder Script
#	Intended for use on Horus flights, with the following payload frequencies:
#	RTTY: 434.650 MHz - Callsign 'HORUS'
#	MFSK: 434.660 MHz - Callsign 'HORUSBINARY'
#
#	The SDR is tuned 5 kHz below the RTTY frequency, and the frequency estimators are set across the two frequencies.
# 	Modem statistics are sent out via a new 'MODEM_STATS' UDP broadcast message every second.
#

# Receive requency, in Hz. This is the frequency the SDR is tuned to.
RXFREQ=434645000

# Where in the passband we expect to find the RTTY signal, in Hz.
# For Horus flights, this is on 434.650 MHz, so with a SDR frequency of 434.645 MHz,
# we expect to find the RTTY signal at approx +5 kHz.
RTTY_SIGNAL=5000

# Where in the receiver passband we expect to find the Horus Binary (MFSK) signal, in Hz.
# For Horus flights, this is on 434.660 MHz, so with a SDR frequency of 434.645 MHz,
# we expect to find the RTTY signal at approx +15 kHz.
MFSK_SIGNAL=15000

# Frequency estimator bandwidth. The wider the bandwidth, the more drift and frequency error the modem can tolerate,
# but the higher the chance that the modem will lock on to a strong spurious signal.
RXBANDWIDTH=8000

# Receiver Gain. Set this to 0 to use automatic gain control, otherwise if running a
# preamplifier, you may want to experiment with different gain settings to optimize
# your receiver setup.
# You can find what gain range is valid for your RTLSDR by running: rtl_test
GAIN=0

# Bias Tee Enable (1) or Disable (0)
# NOTE: This uses the -T bias-tee option which is only available on recent versions
# of rtl-sdr. Check if your version has this option by running rtl_fm --help and looking
# for it in the option list.
# If not, you may need to uninstall that version, and then compile from source: https://github.com/osmocom/rtl-sdr
BIAS=0

# Receiver PPM offset
PPM=0



# Enable (1) or disable (0) modem statistics output.
# Stats are received by the fskstatsudp.py script, averaged, and then emitted into the network at STATS_RATE Hz (set below).
STATS_OUTPUT=1
# Stats UDP output update rate.
STATS_RATE=1

# UDP Output Ports
# With the below settings, chasemapper can be configured to display positions by creating a profile with
# the following settings: 
# telemetry_source_type = horus_udp
# telemetry_source_port = 55672
RTTY_OZIMUX_PORT=55684
RTTY_SUMMARY_PORT=55672

MFSK_OZIMUX_PORT=55683
MFSK_SUMMARY_PORT=55672

# Callsign information for the modem stats output
# As the stats output does not include any information about callsign, if we want to fuse the modem stats
# with payload information in another application, we need to manually add in the callsign information.
# For Horus flights, this is easy: RTTY = HORUS, MFSK = HORUSBINARY.
# For other flights, you will need to change these to match your callsigns.
RTTY_CALLSIGN=HORUS
MFSK_CALLSIGN=HORUSBINARY


# Check that the horus_demod decoder has been compiled.
FILE=./src/horus_demod
if [ -f "$FILE" ]; then
    echo "Found horus_demod."
else 
    echo "ERROR - $FILE does not exist - have you compiled it yet?"
	exit 1
fi

# Check that bc is available on the system path.
if echo "1+1" | bc > /dev/null; then
    echo "Found bc."
else 
    echo "ERROR - Cannot find bc - Did you install it?"
	exit 1
fi


# Calculate the frequency estimator limits
# Note - these are somewhat hard-coded for this dual-RX application.
RTTY_LOWER=$(echo "$RTTY_SIGNAL - $RXBANDWIDTH/2" | bc)
RTTY_UPPER=$(echo "$RTTY_SIGNAL + $RXBANDWIDTH/2" | bc)

MFSK_LOWER=$(echo "$MFSK_SIGNAL - $RXBANDWIDTH/2" | bc)
MFSK_UPPER=$(echo "$MFSK_SIGNAL + $RXBANDWIDTH/2" | bc)

echo "Using SDR Centre Frequency: $RXFREQ Hz."
echo "Using RTTY estimation range: $RTTY_LOWER - $RTTY_UPPER Hz"
echo "Using MFSK estimation range: $MFSK_LOWER - $MFSK_UPPER Hz"

BIAS_SETTING=""

if [ "$BIAS" = "1" ]; then
	echo "Enabling Bias Tee."
	BIAS_SETTING=" -T"
fi

GAIN_SETTING=""
if [ "$GAIN" = "0" ]; then
	echo "Using AGC."
	GAIN_SETTING=""
else
	echo "Using Manual Gain"
	GAIN_SETTING=" -g $GAIN"
fi

STATS_SETTING=""

if [ "$STATS_OUTPUT" = "1" ]; then
	echo "Enabling Modem Statistics."
	STATS_SETTING=" --stats=100"
fi

# Start the receive chain.
rtl_fm -M raw -F9 -s 48000 -p $PPM $GAIN_SETTING$BIAS_SETTING -f $RXFREQ | tee >(./src/horus_demod -q -m RTTY --fsk_lower=$RTTY_LOWER --fsk_upper=$RTTY_UPPER $STATS_SETTING - - 2> >(python ./webui/fskstatsudp.py -s $RTTY_CALLSIGN -p $RTTY_SUMMARY_PORT --rate $STATS_RATE) | python horusbinary.py --rtty --stdin --summary $RTTY_SUMMARY_PORT --ozimux $RTTY_OZIMUX_PORT --debuglog rtty_decode.log) >(./src/horus_demod -q -m binary --fsk_lower=$MFSK_LOWER --fsk_upper=$MFSK_UPPER $STATS_SETTING - -  2> >(python ./webui/fskstatsudp.py -s $MFSK_CALLSIGN -p $MFSK_SUMMARY_PORT --rate $STATS_RATE)| python horusbinary.py --stdin --summary $MFSK_SUMMARY_PORT --ozimux $MFSK_OZIMUX_PORT --debuglog fsk_decode.log) > /dev/null
