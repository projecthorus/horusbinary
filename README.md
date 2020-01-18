# Project Horus's Low-Speed Binary Telemetry System
This repository contains documentation and scripts to work with the new `horus_demod` MFSK/RTTY demodulator, developed by [David Rowe](http://rowetel.com). Currently this demodulator provides ~2.5dB better RTTY decode performance than dl-fldigi 3.21.50, and ~0.5dB better performance than fldigi 4.0.1.

More importantly, it also adds support for a binary-packet 4FSK mode, designed specifically for high-altitude balloon telemetry, and which is intended to supercede RTTY for all Project Horus launches. Preliminary testing shows it has ~6dB improved demodulation performance over RTTY at the same baud rate.

Currently we are developing the modem under Linux & OSX, with the eventual aim to produce a cross-platform GUI. For now, the demodulator is available as a command-line utility, with additional binary packet processing and uploading of data to Habitat performed by the `horusbinary.py` python script.

These modems have recently been added to the FreeDV GUI, to allow easier usage. Refer to this guide for instructions on using FreeDV to decode Horus Binary telemetry: https://github.com/projecthorus/horusbinary/wiki/FreeDV---HorusBinary-Setup-&-Usage-Instructions

## Modes Supported
The `horus_demod` modem (located within the codec2-dev repo) is in early development, and currently only supports:

### MFSK - Horus Binary Packets
Horus Binary packets take the form:
```
<preamble><unique word><payload>
where
<preamble> = 0x1B1B1B1B
<unique word> = 0x2424
```
The payload consists of a 22-byte long binary packet, encoded with a Golay (23,12) code, and then interleaved and scrambled, for a total encoded length of 43 bytes. The binary packet format is [available here](https://github.com/darksidelemm/RS41HUP/blob/master/main.c#L72), and the golay-encoding/interleaving/scrambling is performed by [horus_l2_encode_packet](https://github.com/darksidelemm/RS41HUP/blob/master/horus_l2.c#L117).

At the start of a packet is a Payload ID (one byte). A lookup table for payload IDs is [located here](https://github.com/projecthorus/horusbinary/blob/master/payload_id_list.txt). **If you are going to fly your own payload using this mode, you must get a payload ID allocated for your use. This can be done by submitting an issue or a pull request to this repository, or e-mailing me at vk5qi (at) rfhead.net**

Packets are then transmitted using **4FSK modulation**, at **100 baud**.

A worked example for generating and encoding these packets is available in the [RS41HUP](https://github.com/darksidelemm/RS41HUP/blob/master/main.c#L401) repository.

### RTTY (UKHAS-Standard Sentences)
[UKHAS-standard](https://ukhas.org.uk/communication:protocol) telemetry sentences sent via RTTY can be decoded. These take the general form:
```
$$$$$CALLSIGN,other,fields,here*CRC16\n
```
Note the use of five (5) '$' symbols at the start of the sentence. This is used as a 'unique word' for packet dection, and must be present. Other quantities of '$'s will *not* be detected.

Only RTTY telemetry with the following parameters are supported:
* Baud Rate: 100
* Tone Spacing: 150 to ~1 kHz will work
* Encoding: ASCII 7N2 (7-bit ASCII, no parity, 2 stop bits)
* CRC: CRC16-CCITT

The RTTY decoding functionality of this repository should be considered 'experimental', and was added more for legacy reasons.

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
$ sudo apt-get install git python-crcmod python-requests python-pip sox bc
```
Under OSX, Macports or Homebrew should be able to provide the above packages.

If the python-crcmod and python-requests packages are not available via your package manager, you can try installing them via pip using `sudo pip install crcmod requests`.

### Windows
Under Windows, the [Anaconda Python](https://www.anaconda.com/download/) distribution provides almost everything you need. Download and install the latest version of Anaconda. When installing make sure the 'Add Anaconda Python to system PATH' tickbox is checked, else the below commands will not work.

Once Anaconda is installed, grab the rest of the required dependencies by opening an *administrator* command prompt, and running:
```
> pip install crcmod
```

You may wish to set the python interpreter (which should be located at C:\ProgramData\Anaconda3\python.exe) as the default program to open .py files.


## Downloading this Repository
You can either clone this repository using git:
```
$ git clone https://github.com/projecthorus/horusbinary.git
```
or download a zip file of the repository [from here](https://github.com/projecthorus/horusbinary/archive/master.zip).


## Building Horus-Demod
If you wish to use the command-line demodulator (Linux/OSX only) instead of FreeDV, follow these instructions. Otherwise, skip to the next section.

### Build Dependencies
We may require a few dependencies to be able to use the new modem. Under Ubuntu/Debian, you can install the required packages using:
```
$ sudo apt-get install subversion cmake build-essential libfftw3-dev libspeexdsp-dev libsamplerate0-dev libusb-1.0-0-dev
```

### Compiling horus_demod
We need to compile the horus_demod binary (taken from the codec2 repository). This can be accomplished by performing (within this directory):
```
$ cd src
$ make
$ cp horus_demod ../
$ cd ../
```

## Configuration File
Copy the example configuration file `user.cfg.example` to `user.cfg`, i.e.:
```
$ cp user.cfg.example user.cfg
```

The file `user.cfg` should then be modified to reflect the callsign you wish to use when uploading data to Habitat.
Simply change the following section as appropriate:
```
[user]
# Your callsign -  used when uploading to the HabHub Tracker.
callsign = YOUR_CALL_HERE

# Your station latitude/longitude, which will show up on tracker.habhub.org.
# These values must be in Decimal Degree format.
# Leave the lat/lon at 0.0 if you do not wish your station plotted on the map,
# or if you are uploading your position via other means (i.e. using chasemapper)
station_lat = 0.0
station_lon = 0.0
# Radio/Antenna descriptions.
# An optional short decription of your radio/antenna setup.
radio_comment = Your Radio Description Here
antenna_comment = Your Antenna Description Here
```


## Receiving Using FreeDV
**NOTE: Horus Binary support is only available in very recent versions of FreeDV.**

Instructions on decoding Horus Binary telemetry using FreeDV are available here: https://github.com/projecthorus/horusbinary/wiki/FreeDV---HorusBinary-Setup-&-Usage-Instructions

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

### Demodulating using rtl_fm
This assumes you want to use an rtl-sdr dongle on a headless Linux machine.
```
rtl_fm -M raw -s 48000 -p 0 -f 434648400 | ./horus_demod -q -m binary - - | python horusbinary.py --stdin
```
Tune 1600 Hz below the expected centre frequency (i.e. 434.650 MHz - 1600 Hz = 434.648400 MHz = 434648400 Hz, as above), and make sure that your dongle has a known ppm adjustment.

### Demodulating using GQRX 
This assumes you have GQRX installed (`sudo apt-get install gqrx` or similar) and working, have set up a USB demodulator over the signal of interest, and have enabled the [UDP output option](http://gqrx.dk/doc/streaming-audio-over-udp) by clicking the UDP button at the bottom-right of the GQRX window.

```
$ nc -l -u localhost 7355 | ./horus_demod -m binary - - | python horusbinary.py --stdin
```
Replace `binary` in the above command with `RTTY` to demodulate RTTY telemetry.

On some platforms nc requires the listen port to be specified with the -p argument. In those cases, use:
```
$ nc -l -u -p 7355 localhost | ./horus_demod -m binary - - | python horusbinary.py --stdin
```

### Headless Demodulation of 4FSK and RTTY Simulataneously
The [start_dual_rtty_mfsk_rx.sh](https://github.com/projecthorus/horusbinary/blob/master/start_dual_rtty_mfsk_rx.sh) script is specifically designed for simultaneous reception of the 4FSK and RTTY payloads that are commonly flown on Project Horus launches. It uses careful selection of FSK demodulator frequency estimator settings to run two demodulators in parallel - one decoding 4FSK, one decoding RTTY. 
This makes the assumption that the RTTY payload is on 434.650 MHz, and the 4FSK payload is on 434.660 MHz. 

Check the various options throughout the script for your use-case. In particular, you may want to adjust the gain settings.
By default this script will output telemetry for both 4FSK and RTTY payloads in horus_udp format on port 55672. This can be received and plotted using chasemapper (when configured correctly).