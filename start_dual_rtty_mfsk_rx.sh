#!/usr/bin/env bash
#
#	Dual RTTY / Horus Binary Decoder Script
#	Intended for use on Horus flights, with the following payload frequencies:
#	RTTY: 434.650 MHz
#	MFSK: 434.660 MHz
#
#	The SDR is tuned 5 kHz below the RTTY frequency, and the frequency estimators are set across the two frequencies.

# Receive requency, in Hz
RXFREQ=434645000

# Receiver Gain. Set this to 0 to use automatic gain control, otherwise if running a
# preamplifier, you may want to experiment with different gain settings to optimize
# your receiver setup.
# You can find what gain range is valid for your RTLSDR by running: rtl_test
GAIN=30

# Bias Tee Enable (1) or Disable (0)
BIAS=0

# Receiver PPM offset
PPM=0

# Frequency estimator bandwidth. The wider the bandwidth, the more drift and frequency error the modem can tolerate,
# but the higher the chance that the modem will lock on to a strong spurious signal.
# Note: The SDR will be tuned to RXFREQ-RXBANDWIDTH/2, and the estimator set to look at 0-RXBANDWIDTH Hz.
RXBANDWIDTH=8000

# Enable (1) or disable (0) modem statistics output.
# If enabled, modem statistics are written to stats.txt, and can be observed
# during decoding by running: tail -f stats.txt | python fskstats.py
STATS_OUTPUT=0

# UDP Output Ports
RTTY_OZIMUX_PORT=55684
RTTY_SUMMARY_PORT=55672

MFSK_OZIMUX_PORT=55683
MFSK_SUMMARY_PORT=55672

# Calculate the frequency estimator limits
# Note - these are somewhat hard-coded for this dual-RX application.
RTTY_LOWER=1000
RTTY_UPPER=$(echo "$RTTY_LOWER + $RXBANDWIDTH" | bc)

FSK_LOWER=12000
FSK_UPPER=$(echo "$FSK_LOWER + $RXBANDWIDTH" | bc)

echo "Using SDR Centre Frequency: $SDR_RX_FREQ Hz."
echo "Using FSK estimation range: $FSK_LOWER - $FSK_UPPER Hz"

BIAS_SETTING=""

if [ "$BIAS" = "1" ]; then
	echo "Enabling Bias Tee."
	BIAS_SETTING=" -T"
fi

STATS_SETTING=""

if [ "$STATS_OUTPUT" = "1" ]; then
	echo "Enabling Modem Statistics."
	STATS_SETTING=" --stats=100"
fi

# Start the receive chain.
rtl_fm -M raw -F9 -s 48000 -p $PPM -g $GAIN$BIAS_SETTING -f $RXFREQ | tee >(./horus_demod -q -m RTTY --fsk_lower=$RTTY_LOWER --fsk_upper=$RTTY_UPPER $STATS_SETTING - - 2> stats_rtty.txt | python horusbinary.py --rtty --stdin --summary $RTTY_SUMMARY_PORT --ozimux $RTTY_OZIMUX_PORT --debuglog rtty_decode.log) >(./horus_demod -q -m binary --fsk_lower=$FSK_LOWER --fsk_upper=$FSK_UPPER $STATS_SETTING - -  2> stats_fsk.txt| python horusbinary.py --stdin --summary $MFSK_SUMMARY_PORT --ozimux $MFSK_OZIMUX_PORT --debuglog fsk_decode.log) > /dev/null
