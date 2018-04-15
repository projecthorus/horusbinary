# Project Horus's Low-Speed Binary Telemetry System
This repository contains documentation and scripts to work with the new `horus_demod` MFSK/RTTY demodulator, developed by [David Rowe](http://rowetel.com). Currently this demodulator provides ~2.5dB better RTTY decode performance than dl-fldigi 3.21.50, and ~0.5dB better performance than fldigi 4.0.1. 

It also adds support for a binary-packet 4FSK mode, designed specifically for high-altitude balloon telemetry, and which is intended to supercede RTTY for all Project Horus launches. Preliminary testing shows it has ~6dB improved demodulation performance over RTTY at the same baud rate.

Currently we are developing the modem under Linux & OSX, with the eventual aim to produce a cross-platform GUI. For now, the demodulator is available as a command-line utility, with additional binary packet processing and uploading of data to Habitat performed by the `horusbinary.py` python script.

## Modes Supported
The `horus_demod` modem (located within the codec2-dev repo) is in very early development, and currently only supports:

### RTTY (UKHAS-Standard Sentences)
[UKHAS-standard](https://ukhas.org.uk/communication:protocol) telemetry sentences, sent via RTTY can be decoded. These take the general form:
```
$$$$$CALLSIGN,other,fields,here*CRC16\n
```
Note the use of five (5) '$' symbols at the start of the sentence. This is used as a 'unique word' for packet dection, and must be present. Other quantities of '$'s will *not* be detected.

Only RTTY telemetry with the following parameters are supported:
* Baud Rate: 100
* Tone Spacing: 150 to ~1 kHz will work
* Encoding: ASCII 7N2 (7-bit ASCII, no parity, 2 stop bits)
* CRC: CRC16-CCITT

### MFSK - Horus Binary Packets
Horus Binary packets take the form:
```
<preamble><unique word><payload>
where
<preamble> = 0x1B1B1B1B
<unique word> = 0x2424
```
The payload consists of a 22-byte long binary packet, encoded with a Golay (23,12) code, and then interleaved and scrambled, for a total encoded length of 43 bytes. The binary packet format is [available here](https://github.com/darksidelemm/RS41HUP/blob/master/main.c#L75), and the golay-encoding/interleaving/scrambling is performed by [horus_l2_encode_packet](https://github.com/darksidelemm/RS41HUP/blob/master/horus_l2.c#L117).

These packets are then transmitted using **4FSK modulation**, at **100 baud**.

A worked example for generating encoding these packets is available in the [RS41HUP](https://github.com/darksidelemm/RS41HUP/blob/master/main.c#L401) repository.

## Dependencies
We require a few dependencies to be able to use the new modem. Some can be obtained via the system package manager, others can be installed via the python package manager.

### System Packages
Under Ubuntu/Debian, you can install the required packages using:
```
$ sudo apt-get install git subversion cmake build-essential python-numpy python-pyqtgraph python-crcmod python-requests python-pip libfftw3-dev libspeexdsp-dev libsamplerate0-dev libusb-1.0-0-dev
```

If the python-pyqtgraph, python-crcmod and python-requests packages are not available via your package manager, you can try installing them via pip using `sudo pip install pyqtgraph crcmod requests`.

### horus_demod (via the codec2-dev repository)
We need to compile the horus_demod binary from within the codec2-dev repository. This can be accomplished by performing (within this directory):
```
$ svn checkout https://svn.code.sf.net/p/freetel/code/codec2-dev
$ cd codec2-dev
$ mkdir build
$ cd build
$ cmake ..
$ cd src
$ make horus_demod
$ cp horus_demod ../../../
$ cd ../../../
```

Note that we do not build all the binaries within codec2-dev, just the one we need!

TODO: Bring the necessary source code into this repository, to avoid needing to checkout all of codec2-dev.

## Usage
The `horus_demod` binary accepts 48khz 16-bit signed-integer samples via stdin, and can decode either RTTY or the MFSK (binary) packets. Successfuly decoded packets are output via stdout, and debug information is provided via stderr.

Suitable audio inputs could be from a sound card input, or from a SDR receiver application such as [GQRX](http://gqrx.dk/).

The `horusbinary.py` python script will accept decoded packets from `horus_demod`, and upload them to the HabHub tracker, for display on a map. Uploading to Habitat can be inhibited using the `--noupload` option.

We can string these applications together in the command shell using 'pipes', as follows:

### Demodulating from a Sound Card
```
sox -d -r 48k -c 1 -t s16 - | ./horus_demod -m RTTY - - | python horusbinary.py --mycall YOURCALLSIGN
```
The above command records from the default sound device.

### Demodulating using GQRX 
This assumes you have GQRX installed (`sudo apt-get install gqrx`) and working, have set up a USB demodulator over the signal of interest, and have enabled the [UDP output option](http://gqrx.dk/doc/streaming-audio-over-udp) by clicking the UDP button at the bottom-right of the GQRX window.

```
nc -l -u localhost 7355 | ./horus_demod -m RTTY - - | python horusbinary.py --mycall YOURCALLSIGN
```
Replace `RTTY` in the above command with `binary` to demodulate 4FSK binary telemetry.

