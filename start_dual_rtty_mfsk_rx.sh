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

# Receive requency, in Hz
RXFREQ=434645000

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

# Frequency estimator bandwidth. The wider the bandwidth, the more drift and frequency error the modem can tolerate,
# but the higher the chance that the modem will lock on to a strong spurious signal.
# Note: The SDR will be tuned to RXFREQ-RXBANDWIDTH/2, and the estimator set to look at 0-RXBANDWIDTH Hz.
RXBANDWIDTH=8000

# Enable (1) or disable (0) modem statistics output.
# Stats are received by the fskstatsudp.py script, averaged, and then emitted into the network at STATS_RATE Hz (set below).
STATS_OUTPUT=1
# Stats UDP output update rate.
STATS_RATE=1

# UDP Output Ports
RTTY_OZIMUX_PORT=55684
RTTY_SUMMARY_PORT=55672

MFSK_OZIMUX_PORT=55683
MFSK_SUMMARY_PORT=55672

# Callsign information for the modem stats output
# As the stats output does not include any information about callsign, if we want to fuse the modem stats
# with payload information in another application, we need to manually add in the callsign information.
# For Horus flights, this is easy: RTTY = HORUS, MFSK = HORUSBINARY.
RTTY_CALLSIGN=HORUS
MFSK_CALLSIGN=HORUSBINARY

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
rtl_fm -M raw -F9 -s 48000 -p $PPM $GAIN_SETTING$BIAS_SETTING -f $RXFREQ | tee >(./horus_demod -q -m RTTY --fsk_lower=$RTTY_LOWER --fsk_upper=$RTTY_UPPER $STATS_SETTING - - 2> >(python ./webui/fskstatsudp.py -s $RTTY_CALLSIGN -p $RTTY_SUMMARY_PORT --rate $STATS_RATE) | python horusbinary.py --rtty --stdin --summary $RTTY_SUMMARY_PORT --ozimux $RTTY_OZIMUX_PORT --debuglog rtty_decode.log) >(./horus_demod -q -m binary --fsk_lower=$FSK_LOWER --fsk_upper=$FSK_UPPER $STATS_SETTING - -  2> >(python ./webui/fskstatsudp.py -s $MFSK_CALLSIGN -p $MFSK_SUMMARY_PORT --rate $STATS_RATE)| python horusbinary.py --stdin --summary $MFSK_SUMMARY_PORT --ozimux $MFSK_OZIMUX_PORT --debuglog fsk_decode.log) > /dev/null
