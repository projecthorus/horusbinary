# Project Horus's Low-Speed Binary Telemetry System
This repository contains documentation and scripts to work with the new `horus_demod` MFSK/RTTY demodulator, developed by [David Rowe](http://rowetel.com). Currently this demodulator provides ~2.5dB better RTTY decode performance than dl-fldigi 3.21.50, and ~0.5dB better performance than fldigi 4.0.1.

It also adds support for a binary-packet 4FSK mode, designed specifically for high-altitude balloon telemetry, and which is intended to supercede RTTY for all Project Horus launches. Preliminary testing shows it has ~6dB improved demodulation performance over RTTY at the same baud rate.

Currently we are developing the modem under Linux & OSX, with the eventual aim to produce a cross-platform GUI. For now, the demodulator is available as a command-line utility, with additional binary packet processing and uploading of data to Habitat performed by the `horusbinary.py` python script.

These modems have recently been added to the [FreeDV GUI](http://freedv.org), to allow easier usage.

## Modes Supported
The `horus_demod` modem (located within the codec2-dev repo) is in early development, and currently only supports:

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


## Hardware Requirements
Both the RTTY and MFSK modes are narrow bandwidth, and can be received using a regular single-sideband (SSB) radio receiver. This could be a 'traditional' receiver (like a Icom IC-7000, Yaesu FT-817 to name but a few), or a software-defined radio receiver. The point is we need to receive the on-air signal (we usually transmit on 70cm) with an Upper-Sideband (USB) demodulator, and then get that audio into your computer.

If you are using a traditional receiver, you'll likely either have some kind of audio interface for it, or will be able to connect an audio cable between it and your computer's sound card. Easy!

With a RTLSDR, you will need to use software like [GQRX](http://gqrx.dk/) (Linux/OSX), [SDR#](https://airspy.com/download/), or [SDR Console](http://www.sdr-radio.com/) to perform the USB demodulation. You'll then need some kind of loop-back audio interface to present that audio as a virtual sound card. This can be done using:
* Linux - via the snd-aloop module. Some information on this is [here](https://blog.getreu.net/_downloads/snd-aloop-device.pdf).
* OSX - Using the [SoundFlower](https://github.com/mattingalls/Soundflower) application.
* Windows - Use [VBCable](http://vb-audio.pagesperso-orange.fr/Cable/index.htm)

You're also going to need some sort of antenna to receive the signal from the balloon payload, but I figure that's a bit out of scope for this readme!

## Software Dependencies
To be able to use the horusbinary.py Python script, you will need a Python interpreter and a few libraries.

### Linux / OSX
Under Linux (Ubuntu/Debian) install the required packages using:
```
$ sudo apt-get install git python-numpy python-pyqtgraph python-crcmod python-requests python-pip
```
Under OSX, Macports or Homebrew should be able to provide the above packages.

If the python-pyqtgraph, python-crcmod and python-requests packages are not available via your package manager, you can try installing them via pip using `sudo pip install pyqtgraph crcmod requests`.

### Windows
Under Windows, the [Anaconda Python](https://www.anaconda.com/download/) distribution provides almost everything you need. Download and install the *Python 2.7* version of Anaconda. When installing make sure the 'Add Anaconda Python to system PATH' tickbox is checked, else the below commands will not work.

Once Anaconda is installed, grab the rest of the required dependencies by opening an *administrator* command prompt, and running:
```
> pip install crcmod python-dateutil
```

You may wish to set the python interpreter (which should be located at C:\ProgramData\Anaconda2\python.exe) as the default program to open .py files.


## Building Horus-Demod
If you wish to use the command-line demodulator (Linux/OSX only) instead of FreeDV, follow these instructions. Otherwise, skip to the next section.

### Build Dependencies
We require a few dependencies to be able to use the new modem. Some can be obtained via the system package manager, others can be installed via the python package manager.

#### System Packages
Under Ubuntu/Debian, you can install the required packages using:
```
$ sudo apt-get install subversion cmake build-essential libfftw3-dev libspeexdsp-dev libsamplerate0-dev libusb-1.0-0-dev
```

### Compiling horus_demod (via the codec2-dev repository)
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

## Downloading this Repository
You can either clone this repository using git:
```
$ git clone https://github.com/projecthorus/horusbinary.git
```
or download a zip file of the repository [from here](https://github.com/projecthorus/horusbinary/archive/master.zip). 

## Configuration File
The file `user.cfg` should be modified to reflect the callsign you wish to use when uploading data to Habitat.
Simply change the following section as appropriate:
```
[user]
# Your callsign -  used when uploading to the HabHub Tracker.
callsign = YOUR_CALL_HERE
```
Leave the other options in the configuration file at their defaults.

## Receiving Using FreeDV
**NOTE: Horus Binary support in FreeDV is still under development.**
FreeDV now has the Horus Binary MFSK modem included. Download and install FreeDV from http://freedv.org/.

Once installed, start up FreeDV and:
* In `Tools -> Audio Config`, go to the 'Receive' tab, and set the 'From Radio' sound card as appropriate (i.e. the one which the modem signal will be received on, from your radio output). Set the 'To Speakers/Headphones' to your default sound card output. (TODO: How to mute the audio?).
* In `Tools -> Audio Config`, go to the 'Transmit' tab, and set both the 'From Microphone' and 'To Radio' devices to 'none'.
* In `Tools -> Options`, tick 'Enable UDP Messages', and set the UDP port to 55690.

You should now be able to select 'HorusB' (Horus Binary) from the mode list at the right of the main FreeDV window, and click Start to see a waterfall display.

Run `horusbinary.py` either from a terminal/command prompt, or by double-clicking the python file. You should see the following:
```
$ python horusbinary.py
2018-06-17 16:18:27,477 INFO: Using User Callsign: YOUR_CALL_HERE
2018-06-17 16:18:27,477 INFO: Using Payload Callsign: HORUSBINARY
2018-06-17 16:18:27,477 INFO: Started Habitat Uploader Thread.
2018-06-17 16:18:27,477 INFO: Opened UDP socket on port 55690.
2018-06-17 16:18:27,478 INFO: Started Horus Binary Uploader. Hit CTRL-C to exit.
```
This will be followed by telemetry data as it is received. Telemetry will be automatically uploaded to the Habitat database, and will be visible on http://tracker.habhub.org/ 


## Usage - Horus Demod
The `horus_demod` binary accepts 48khz 16-bit signed-integer samples via stdin, and can decode either RTTY or the MFSK (binary) packets. Successfuly decoded packets are output via stdout, and debug information is provided via stderr.

Suitable audio inputs could be from a sound card input, or from a SDR receiver application such as [GQRX](http://gqrx.dk/).

The `horusbinary.py` python script will accept decoded packets from `horus_demod`, and upload them to the HabHub tracker, for display on a map. Uploading to Habitat can be inhibited using the `--noupload` option. The `--stdin` option tells horusbinary.py to listen for data via stdin, instead of from UDP packets.

We can string these applications together in the command shell using 'pipes', as follows:

### Demodulating from a Sound Card
```
$ sox -d -r 48k -c 1 -t s16 - | ./horus_demod -m binary - - | python horusbinary.py --stdin
```
The above command records from the default sound device.

### Demodulating using GQRX 
This assumes you have GQRX installed (`sudo apt-get install gqrx`) and working, have set up a USB demodulator over the signal of interest, and have enabled the [UDP output option](http://gqrx.dk/doc/streaming-audio-over-udp) by clicking the UDP button at the bottom-right of the GQRX window.

```
$ nc -l -u localhost 7355 | ./horus_demod -m binary - - | python horusbinary.py --stdin
```
Replace `binary` in the above command with `RTTY` to demodulate RTTY telemetry.

