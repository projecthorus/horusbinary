#!/usr/bin/env bash
echo "Launching horus_demod with rtl_fm in raw IQ mode"

# Receive *centre* frequency
# Note: The SDR will be tuned 
RXFREQ=434650000


# Receiver Gain. Set this to 0 to use automatic gain control, otherwise if running a
# preamplifier, you may want to experiment with different gain settings to optimize
# your receiver setup.
# You can find what gain range is valid for your RTLSDR by running: rtl_test
GAIN=0

# Bias Tee Enable (1) or Disable (0)
BIAS=1

# Receiver PPM offset
PPM=0

# Frequency estimator bandwidth. The wider the bandwidth, the more drift and frequency error the modem can tolerate,
# but the higher the chance that the modem will lock on to a strong spurious signal.
# Note: The SDR will be tuned to RXFREQ-RXBANDWIDTH/2, and the estimator set to look at 0-RXBANDWIDTH Hz.
RXBANDWIDTH=10000

# Enable (1) or disable (0) modem statistics output.
# If enabled, modem statistics are written to stats.txt, and can be observed
# during decoding by running: tail -f stats.txt | python fskstats.py
STATS_OUTPUT=1

# Calculate the SDR tuning frequency
SDR_RX_FREQ=$(echo "$RXFREQ - $RXBANDWIDTH/2 - 1000" | bc)

# Calculate the frequency estimator limits
FSK_LOWER=1000
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
rtl_fm -M raw -F9 -s 48000 -p $PPM -g $GAIN$BIAS_SETTING -f $SDR_RX_FREQ | ./horus_demod -q -m binary --fsk_lower=$FSK_LOWER --fsk_upper=$FSK_UPPER $STATS_SETTING - -  2> stats.txt| python horusbinary.py --stdin $@
